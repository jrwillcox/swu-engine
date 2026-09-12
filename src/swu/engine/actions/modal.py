"""Modal effects: "choose one", "choose two", and one option applied per card.

A modal effect is two questions wearing one decision — which mode, and then which
target for that mode — so every handler here is staged on ``top.context["stage"]`` and
the four kinds differ mainly in how they thread those stages:

* ``modal`` — choose one of the printed options.
* ``choose_modal`` / ``choose_two_modal`` — choose two, which is genuinely ordered
  rather than a set, because resolving the first can change what the second may target.
* ``repeated_modal`` — apply a mode per card processed, so the mode question recurs and
  ``_maybe_finish_repeated_modal`` decides each time whether the effect is done.
* ``let_wookiee_win`` — the interesting one, and the reason this family cannot assume a
  single deciding player: its ``mode`` stage is decided by the opponent, while its
  ``ready`` stage is decided by the controller, read back out of
  ``ctx["controller_id"]``. A stage is the unit of "whose choice is this", not a
  decision.

**A mode is only offered if it has at least one legal target.** An option whose effect
could not resolve is not a choice, so ``_modal_mode_targets`` is consulted while
enumerating rather than after choosing, and a "choose one" can legitimately present one
option or none.

That check pays for a second one. ``_MODAL_FUNGIBLE_MODES`` names the modes whose legal
targets are interchangeable — "ready a resource", where no resource differs from another
in any way the rules can see. Those skip the target stage entirely and resolve against
an arbitrary target, which is sound *only* because the mode was already proved to have
one. The saving is not cosmetic: without it every such effect would stop the game to ask
a question with exactly one meaningful answer.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, Zone

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.zones import (
    _create_token_units, _draw_cards,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, push_granted_attack,
)


# ── Modal "choose one" decision (Leia Organa SOR_189) ─────────────────────────

@dataclass
class ChooseModalOption(Action):
    """Select one mode of a 'modal' (choose one) decision.  A fungible mode (e.g.
    ready a resource) resolves immediately; otherwise advance to the target
    choice for that mode (Leia Organa, SOR_189)."""
    mode: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "modal"):
            raise IllegalActionError("No modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "mode":
            raise IllegalActionError("Modal decision is past the mode-choice stage")
        if self.mode not in ctx["modes"]:
            raise IllegalActionError(f"{self.mode!r} is not an available mode")
        if self.mode in _MODAL_FUNGIBLE_MODES:
            # No meaningful target choice — the legal targets are interchangeable
            # (e.g. any exhausted resource), so resolve immediately on an
            # arbitrary one rather than asking the player to pick.  The mode was
            # only offered because it has ≥1 legal target.
            targets = _modal_mode_targets(s, ctx["controller_id"], self.mode)
            return _resolve_modal_mode(s, top, self.mode, targets[0])
        ctx["chosen_mode"] = self.mode
        ctx["stage"] = "target"
        # An opponent-decided modal (Watto LOF_65) hands the target choice back to
        # the source's controller — every mode resolves for THEM.
        if top.deciding_player_id != ctx["controller_id"]:
            top.deciding_player_id = ctx["controller_id"]
            s.active_player_index = s.player_index(ctx["controller_id"])
        return s

    def describe(self) -> str:
        return f"Choose: {_MODAL_MODE_LABELS.get(self.mode, self.mode)}"


@dataclass
class ChooseModalTarget(Action):
    """Apply the chosen mode of a 'modal' decision to the chosen target and pop
    the decision (Leia Organa, SOR_189)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "modal"):
            raise IllegalActionError("No modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "target":
            raise IllegalActionError("Modal decision is not at the target stage")
        mode = ctx["chosen_mode"]
        targets = {t.instance_id: t
                   for t in _modal_mode_targets(s, ctx["controller_id"], mode)}
        target = targets.get(self.target_id)
        if target is None:
            raise IllegalActionError(
                f"{self.target_id} is not a legal target for mode {mode!r}")
        return _resolve_modal_mode(s, top, mode, target)

    def describe(self) -> str:
        return f"Modal target {self.target_id}"


# ── Let the Wookiee Win (SHD_205): an OPPONENT-decided modal ───────────────────

@dataclass
class ChooseWookieeMode(Action):
    """The opponent picks one mode of Let the Wookiee Win (SHD_205).

    ``ready_resources`` — the controller readies up to 6 of their exhausted
    resources (fungible; resolved immediately).  ``ready_attack`` — advance to a
    controller stage that readies a chosen friendly unit (then attacks if it is a
    Wookiee); if the controller has no unit to ready, it resolves as a no-op."""
    mode: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "let_wookiee_win"):
            raise IllegalActionError("No let_wookiee_win decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "mode":
            raise IllegalActionError("let_wookiee_win is past the mode stage")
        if self.mode not in ("ready_resources", "ready_attack"):
            raise IllegalActionError(f"{self.mode!r} is not a valid mode")
        controller = s.player_by_id(ctx["controller_id"])
        if self.mode == "ready_resources":
            readied = 0
            for r in controller.resources:
                if readied >= 6:
                    break
                if r.exhausted:
                    r.exhausted = False
                    readied += 1
            s.pending_decisions.pop()
            s.event_log.append(DecisionResolved(
                deciding_player_id=top.deciding_player_id, kind="let_wookiee_win",
                choice=f"opponent chose: controller readies {readied} resource(s)"))
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
            return s
        # ready_attack — hand the target choice to the CONTROLLER.
        units = controller.ground_arena + controller.space_arena
        if not units:
            s.pending_decisions.pop()
            s.event_log.append(DecisionResolved(
                deciding_player_id=top.deciding_player_id, kind="let_wookiee_win",
                choice="opponent chose: ready a unit (controller has none)"))
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
            return s
        ctx["stage"] = "ready"
        # Shift the decision to the CONTROLLER for the target stage.  Both the
        # deciding_player_id and active seat move (apply's decision-stack re-pin
        # reads deciding_player_id, so updating active alone would be reverted).
        top.deciding_player_id = ctx["controller_id"]
        s.active_player_index = s.player_index(ctx["controller_id"])
        return s

    def describe(self) -> str:
        label = ("ready up to 6 resources" if self.mode == "ready_resources"
                 else "ready a friendly unit (Wookiee attacks +2/+0)")
        return f"Opponent choice: {label}"


@dataclass
class ChooseWookieeReadyUnit(Action):
    """The controller readies a chosen friendly unit for Let the Wookiee Win
    (SHD_205); if it is a Wookiee, it then attacks with +2/+0 (via a chained
    push_granted_attack pinned to that unit)."""
    unit_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "let_wookiee_win"):
            raise IllegalActionError("No let_wookiee_win decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "ready":
            raise IllegalActionError("let_wookiee_win is not at the ready stage")
        controller = s.player_by_id(ctx["controller_id"])
        unit = next((u for u in controller.ground_arena + controller.space_arena
                     if u.instance_id == self.unit_id), None)
        if unit is None:
            raise IllegalActionError(f"{self.unit_id} is not a friendly unit")
        unit.exhausted = False
        from swu.engine.traits import has_trait
        is_wookiee = has_trait(s, unit, "Wookiee")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id, kind="let_wookiee_win",
            choice=(f"readied {unit.card_def.display_name}"
                    + (" and attacks +2/+0" if is_wookiee else ""))))
        if is_wookiee:
            # Chain into a granted attack pinned to the readied Wookiee (+2/+0 this
            # attack).  Pop first (above) so the granted_attack decision lands on a
            # clean stack; the unit is now ready, so the attack is offered.
            push_granted_attack(s, unit, power_bonus=2, attacker_id=unit.instance_id)
        elif not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Ready {self.unit_id}"


# ── Repeated-modal "discard up to N, a different option per card" ──────────────

@dataclass
class DiscardForModal(Action):
    """Discard one hand card to earn a modal option (Poe Dameron, SHD_153)."""
    card_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "repeated_modal"):
            raise IllegalActionError("No repeated-modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "discard":
            raise IllegalActionError("Repeated-modal decision is past the discard stage")
        ps = s.player_by_id(ctx["controller_id"])
        card = next((c for c in ps.hand if c.instance_id == self.card_id), None)
        if card is None:
            raise IllegalActionError(f"{self.card_id} is not in the controller's hand")
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(s, card)
        ctx["discarded"] += 1
        cap = min(int(ctx["max_discards"]), len(ctx["modes"]))
        if ctx["discarded"] >= cap or not ps.hand:
            _begin_repeated_modal_options(s, top)
        return s

    def describe(self) -> str:
        return f"Discard {self.card_id} for a modal option"


@dataclass
class FinishModalDiscard(Action):
    """Stop discarding ("up to" N) and move on to choosing options, or finish the
    repeated-modal decision immediately if nothing was discarded (Poe, SHD_153)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "repeated_modal"):
            raise IllegalActionError("No repeated-modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "discard":
            raise IllegalActionError("Repeated-modal decision is past the discard stage")
        _begin_repeated_modal_options(s, top)
        return s

    def describe(self) -> str:
        return "Finish discarding"


@dataclass
class ChooseRepeatedMode(Action):
    """Choose one not-yet-used option of a repeated-modal decision (Poe, SHD_153).
    A targeted option advances to the target stage; an option with no target (or
    no legal target) is recorded immediately."""
    mode: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "repeated_modal"):
            raise IllegalActionError("No repeated-modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_mode":
            raise IllegalActionError("Repeated-modal decision is not at the mode stage")
        if self.mode not in ctx["modes"] or self.mode in ctx["used_modes"]:
            raise IllegalActionError(f"{self.mode!r} is not an available option")
        if self.mode in _REPEATED_MODAL_TARGETED_MODES:
            targets = _repeated_modal_mode_targets(s, ctx["controller_id"], self.mode)
            if targets:
                ctx["chosen_mode"] = self.mode
                ctx["stage"] = "choose_target"
                return s
        # No target needed (opponent_discards) or no legal target — record as-is.
        ctx["plan"].append([self.mode, None])
        ctx["used_modes"].append(self.mode)
        return _maybe_finish_repeated_modal(s, top)

    def describe(self) -> str:
        return f"Choose option: {_REPEATED_MODAL_MODE_LABELS.get(self.mode, self.mode)}"


@dataclass
class ChooseRepeatedTarget(Action):
    """Choose the target for the current targeted option of a repeated-modal
    decision (Poe, SHD_153)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "repeated_modal"):
            raise IllegalActionError("No repeated-modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_target":
            raise IllegalActionError("Repeated-modal decision is not at the target stage")
        mode = ctx["chosen_mode"]
        legal = {t for t in _repeated_modal_mode_targets(s, ctx["controller_id"], mode)}
        if self.target_id not in legal:
            raise IllegalActionError(
                f"{self.target_id} is not a legal target for option {mode!r}")
        ctx["plan"].append([mode, self.target_id])
        ctx["used_modes"].append(mode)
        ctx["chosen_mode"] = None
        ctx["stage"] = "choose_mode"
        return _maybe_finish_repeated_modal(s, top)

    def describe(self) -> str:
        return f"Option target {self.target_id}"


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

@dataclass
class SelectModalOption(Action):
    """Choose one option of a "Choose two, in any order" modal event
    (choose_two_modal decision — the SOR aspect events Aggression SOR_155 /
    Command SOR_107 / Cunning SOR_203 / Vigilance SOR_58).

    Options are picked one at a time; the pick ORDER is the resolution order.
    Once ``pick`` options have been chosen the decision resolves, pushing one
    resolve_effects decision per chosen option (see _resolve_choose_two_modal).
    """
    option_idx: int

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "choose_two_modal"):
            raise IllegalActionError("No choose-two-modal decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if (self.option_idx not in ctx["option_indices"]
                or self.option_idx in ctx["chosen"]):
            raise IllegalActionError(
                f"option {self.option_idx} is not an available modal choice")
        ctx["chosen"].append(int(self.option_idx))
        if len(ctx["chosen"]) >= int(ctx["pick"]):
            return _resolve_choose_two_modal(s, top)
        return s

    def describe(self) -> str:
        return f"Choose modal option {self.option_idx}"


# ── Modal "choose one" (Leia Organa SOR_189) ──────────────────────────

def _modal_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "mode":
        return [ChooseModalOption(m) for m in ctx["modes"]]
    # stage "target": targets for the chosen mode, recomputed from state.
    return [
        ChooseModalTarget(t.instance_id)
        for t in _modal_mode_targets(state, ctx["controller_id"], ctx["chosen_mode"])
    ]


# ── Opponent-decided modal: Let the Wookiee Win (SHD_205) ──────────────

def _let_wookiee_win_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "mode":
        return [ChooseWookieeMode("ready_resources"),
                ChooseWookieeMode("ready_attack")]
    # stage "ready": the controller picks which friendly unit to ready.
    controller = state.player_by_id(ctx["controller_id"])
    return [ChooseWookieeReadyUnit(u.instance_id)
            for u in controller.ground_arena + controller.space_arena]


# ── Modal "choose one" push helper (Leia Organa SOR_189) ──────────────────────

_MODAL_MODE_LABELS = {
    "ready_resource": "Ready a resource",
    "exhaust_resource": "Exhaust a resource",
    "exhaust_unit": "Exhaust a unit",
    "ready_unit": "Ready a unit",
    "give_experience_unit": "Give an Experience token to a unit",
    # K-2SO (SOR_145) "for each opponent, choose one":
    "kaytoo_damage_base": "Deal 3 damage to that player's base",
    "kaytoo_discard": "That player discards a card",
    # Bombing Run (SOR_173) "choose an arena, deal 3 to each unit in it":
    "bomb_ground": "Bomb the ground arena (3 to each unit there)",
    "bomb_space": "Bomb the space arena (3 to each unit there)",
    # Outmaneuver (SOR_221) "choose an arena, exhaust each unit in it":
    "exhaust_ground": "Exhaust each unit in the ground arena",
    "exhaust_space": "Exhaust each unit in the space arena",
    # Manufactured Soldiers (TWI_102) "choose one: create 2 Clone Troopers / 3
    # Battle Droids".  Neither mode targets anything, so both are fungible and
    # resolve on a throwaway proxy (the controller's base) — the bomb_ground shape.
    "create_clone_troopers_2": "Create 2 Clone Trooper tokens",
    "create_battle_droids_3": "Create 3 Battle Droid tokens",
    # Admiral Yularen (JTL_47) "Choose Grit, Restore 1, Sentinel, or Shielded":
    # the pick is recorded against the source instance and read back by
    # Condition.SOURCE_CHOSEN_KEYWORD.  Nothing is targeted, so all four are
    # fungible (the create_clone_troopers_2 throwaway-proxy shape).
    "choose_keyword_grit": "Choose Grit",
    "choose_keyword_restore_1": "Choose Restore 1",
    "choose_keyword_sentinel": "Choose Sentinel",
    "choose_keyword_shielded": "Choose Shielded",
    # Watto (LOF_65) "An opponent chooses one: [You give an Experience token to a
    # friendly unit] / [You draw a card]".
    "give_experience_friendly_unit": "They give an Experience token to a friendly unit",
    "draw_card": "They draw a card",
    # Alliance Outpost (LAW_19) "Give an Experience or Shield token to a unit, or
    # create a Credit token".  ``give_shield_unit`` is the Shield sibling of
    # ``give_experience_unit`` (non-fungible — which unit is shielded matters);
    # ``create_credit_token`` targets nothing, so it is fungible and resolves on a
    # throwaway proxy (the create_clone_troopers_2 shape).
    "give_shield_unit": "Give a Shield token to a unit",
    "create_credit_token": "Create a Credit token",
}

# The keyword a ``choose_keyword_*`` modal mode records (Admiral Yularen JTL_47).
_CHOOSE_KEYWORD_MODES = {
    "choose_keyword_grit": "Grit",
    "choose_keyword_restore_1": "Restore",
    "choose_keyword_sentinel": "Sentinel",
    "choose_keyword_shielded": "Shielded",
}

# Modes whose legal targets are interchangeable, so picking a specific one is
# busywork.  Choosing one of these resolves immediately on an arbitrary legal
# target instead of presenting a target step.  ``ready_resource`` qualifies — all
# of a player's exhausted resources are identical; ``exhaust_unit`` does not (it
# can hit any unit, friendly or enemy, and the choice matters).  K-2SO's two
# modes each act on a single fixed card (the opponent's base / the first card of
# their hand — the DiscardFromHand(chooser="opponent") simplification), so they
# are fungible too.
_MODAL_FUNGIBLE_MODES = {"ready_resource", "exhaust_resource", "kaytoo_damage_base", "kaytoo_discard",
                         "bomb_ground", "bomb_space", "exhaust_ground", "exhaust_space",
                         "create_clone_troopers_2", "create_battle_droids_3",
                         "draw_card", "create_credit_token",
                         *_CHOOSE_KEYWORD_MODES}


def _resolve_modal_mode(
    s: GameState, top: "PendingDecision", mode: str, target: CardInstance
) -> GameState:
    """Apply a chosen modal mode to ``target`` and pop the decision (shared by the
    fungible-mode fast path in ChooseModalOption and the explicit ChooseModalTarget)."""
    if mode == "ready_resource":
        target.exhausted = False
        choice = "readied a resource"
    elif mode == "exhaust_resource":
        target.exhausted = True
        choice = "exhausted a resource"
    elif mode == "exhaust_unit":
        target.exhausted = True
        choice = f"exhausted {target.card_def.display_name}"
    elif mode == "ready_unit":
        # "Ready or exhaust a unit" (Lux Bonteri TWI_210) — the ready sibling of
        # exhaust_unit, and just as non-fungible: which unit is readied matters.
        target.exhausted = False
        choice = f"readied {target.card_def.display_name}"
    elif mode == "draw_card":
        # "You draw a card" — the controller draws; the proxy target is ignored.
        _draw_cards(s, s.player_by_id(top.context["controller_id"]), 1)
        choice = "drew a card"
    elif mode in ("give_experience_unit", "give_experience_friendly_unit",
                  "give_shield_unit"):
        from swu.engine.tokens import attach_token
        token_name = "Shield" if mode == "give_shield_unit" else "Experience"
        host_ps = next(
            (p for p in s.players
             if target in p.ground_arena + p.space_arena), None)
        if host_ps is not None:
            attach_token(s, host_ps, target, token_name)
        choice = f"gave a{'' if token_name == 'Shield' else 'n'} {token_name} " \
                 f"token to {target.card_def.display_name}"
    elif mode == "create_credit_token":
        # "…or create a Credit token" (Alliance Outpost LAW_19) — the controller
        # gains it; the proxy target is ignored (a fungible mode).
        from swu.engine.tokens import create_credit_token
        create_credit_token(s, s.player_by_id(top.context["controller_id"]))
        choice = "created a Credit token"
    elif mode in ("bomb_ground", "bomb_space"):
        # Bombing Run (SOR_173): "Choose an arena. Deal 3 damage to each unit in
        # that arena."  The chosen ``target`` is a throwaway proxy (a unit in the
        # arena, needed only so the mode is offered — the effect ignores it and
        # hits every unit).  Pop-then-deal: pop the decision FIRST so any defeat
        # triggers from the multi-target damage land on a clean stack.
        from swu.abilities.resolver import _apply_deal_damage
        arena_attr = "ground_arena" if mode == "bomb_ground" else "space_arena"
        tids = [u.instance_id for p in s.players for u in getattr(p, arena_attr)]
        src = s.find_instance(top.context.get("source_id", ""))
        name = src[1].card_def.display_name if src is not None else None
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id, kind="modal",
            choice=f"dealt 3 to each unit in the "
                   f"{'ground' if mode == 'bomb_ground' else 'space'} arena"))
        for tid in tids:
            if s.find_instance(tid) is not None:
                _apply_deal_damage(s, tid, 3, source_name=name)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    elif mode in ("exhaust_ground", "exhaust_space"):
        # Outmaneuver (SOR_221): "Choose an arena. Exhaust each unit in that
        # arena."  Like bomb_ground/bomb_space the chosen ``target`` is a throwaway
        # proxy; the effect exhausts every unit (either player's) in the arena.
        arena_attr = "ground_arena" if mode == "exhaust_ground" else "space_arena"
        units = [u for p in s.players for u in getattr(p, arena_attr)]
        s.pending_decisions.pop()
        for u in units:
            u.exhausted = True
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id, kind="modal",
            choice=f"exhausted each unit in the "
                   f"{'ground' if mode == 'exhaust_ground' else 'space'} arena"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    elif mode in ("create_clone_troopers_2", "create_battle_droids_3"):
        # Manufactured Soldiers (TWI_102): "Choose one: create 2 Clone Trooper
        # tokens / create 3 Battle Droid tokens."  ``target`` is a throwaway proxy
        # (the controller's base) — the mode creates tokens for the controller.
        token, count = (("Clone Trooper", 2) if mode == "create_clone_troopers_2"
                        else ("Battle Droid", 3))
        _create_token_units(s, s.player_by_id(top.context["controller_id"]),
                            token, count)
        choice = f"created {count} {token} token(s)"
    elif mode in _CHOOSE_KEYWORD_MODES:
        # Admiral Yularen (JTL_47): record the chosen keyword against the SOURCE
        # instance.  ``target`` is a throwaway proxy (the controller's base) — the
        # mode grants nothing directly; the card's four parallel ConstantAbility
        # specs, each gated by Condition.SOURCE_CHOSEN_KEYWORD, read the record and
        # confer the keyword on every friendly Vehicle while the source is in play.
        kw = _CHOOSE_KEYWORD_MODES[mode]
        src_id = top.context.get("source_id")
        if src_id:
            s.game_memory.chosen_keywords[src_id] = kw
        choice = f"chose {kw}"
    elif mode == "kaytoo_damage_base":
        from swu.abilities.resolver import _apply_deal_damage
        _apply_deal_damage(s, target.instance_id, 3)
        choice = "dealt 3 damage to a base"
    elif mode == "kaytoo_discard":
        for p in s.players:
            if target in p.hand:
                p.hand.remove(target)
                target.zone = Zone.DISCARD
                p.discard.append(target)
                break
        choice = "an opponent discarded a card"
    else:
        raise IllegalActionError(f"Unknown modal mode {mode!r}")
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="modal",
        choice=choice,
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _modal_mode_targets(
    state: GameState, controller_id: str, mode: str
) -> list[CardInstance]:
    """Legal targets for a single modal mode (recomputed from current state).

    ``ready_resource`` — the controller's own exhausted resources (readying a
    ready resource is a no-op, so only exhausted ones are offered).
    ``exhaust_unit`` — any ready unit in play, friendly or enemy (the card says
    "a unit", not "an enemy unit"; an already-exhausted unit is excluded because
    exhausting it does nothing).
    """
    ps = state.player_by_id(controller_id)
    if mode == "ready_resource":
        return [r for r in ps.resources if r.exhausted]
    if mode == "exhaust_resource":
        return [r for r in ps.resources if not r.exhausted]
    if mode == "exhaust_unit":
        out: list[CardInstance] = []
        for p in state.players:
            for u in p.ground_arena + p.space_arena:
                if not u.exhausted:
                    out.append(u)
        return out
    if mode == "ready_unit":
        # Only EXHAUSTED units — readying a ready unit does nothing, the same
        # no-op exclusion exhaust_unit and ready_resource make (Lux Bonteri
        # TWI_210 "ready or exhaust a unit"; either arena, either player).
        out_r: list[CardInstance] = []
        for p in state.players:
            for u in p.ground_arena + p.space_arena:
                if u.exhausted:
                    out_r.append(u)
        return out_r
    if mode == "give_experience_friendly_unit":
        # "You give an Experience token to a friendly unit" (Watto LOF_65) — the
        # controller-only narrowing of ``give_experience_unit``.  Non-fungible: which
        # of the controller's units gets it matters.
        return list(ps.ground_arena + ps.space_arena)
    if mode == "draw_card":
        # "You draw a card" (Watto LOF_65) — nothing is targeted, so the mode is
        # fungible and resolves on a throwaway proxy (the controller's base, a pool
        # that can never be empty — the create_clone_troopers_2 shape).
        return [ps.base_instance] if ps.base_instance is not None else []
    if mode in ("give_experience_unit", "give_shield_unit"):
        # "Give an Experience [or Shield] token to a unit" — any unit in play (the
        # card says "a unit"; either token benefits its host, so the controller
        # never picks an enemy).  Alliance Outpost LAW_19 adds the Shield sibling.
        out2: list[CardInstance] = []
        for p in state.players:
            out2.extend(p.ground_arena + p.space_arena)
        return out2
    if mode == "create_credit_token":
        # Creating a Credit targets nothing — the controller's own base is the
        # throwaway proxy (a pool that can never be empty), so the mode is always
        # available (Alliance Outpost LAW_19).
        return [ps.base_instance] if ps.base_instance is not None else []
    if mode in ("bomb_ground", "bomb_space"):
        # Offer the mode only when the chosen arena holds ≥1 unit (either player);
        # the returned units are a proxy pool — the fungible fast-path resolves on
        # ``[0]`` and the effect ignores it, hitting every unit in the arena.
        arena_attr = "ground_arena" if mode == "bomb_ground" else "space_arena"
        return [u for p in state.players for u in getattr(p, arena_attr)]
    if mode in ("exhaust_ground", "exhaust_space"):
        # Offer the mode only when the chosen arena holds ≥1 unit (either player).
        # Returned units are a proxy pool; the fungible fast-path resolves on [0]
        # and the effect exhausts every unit in the arena.
        arena_attr = "ground_arena" if mode == "exhaust_ground" else "space_arena"
        return [u for p in state.players for u in getattr(p, arena_attr)]
    if mode in ("create_clone_troopers_2", "create_battle_droids_3") or mode in _CHOOSE_KEYWORD_MODES:
        # Token creation / recording a keyword choice targets nothing — offer the
        # controller's own base as a throwaway proxy so the mode is always
        # available (the bomb_ground pool trick, with a pool that can never be
        # empty).
        return [ps.base_instance] if ps.base_instance is not None else []
    if mode in ("kaytoo_damage_base", "kaytoo_discard"):
        # K-2SO's modes act on the OPPONENT (the player "that player" refers to).
        opp = state.players[1 - state.player_index(controller_id)]
        if mode == "kaytoo_damage_base":
            return [opp.base_instance] if opp.base_instance is not None else []
        return list(opp.hand)  # kaytoo_discard — opponent has ≥1 card to discard
    return []


def push_modal(s: GameState, source_ci: CardInstance, modes: list[str], *,
               decider_id: Optional[str] = None) -> None:
    """Push a 'modal' decision: the controller chooses one of ``modes`` (a "choose
    one" effect), then picks a target for the chosen mode (Leia Organa, SOR_189 —
    "Either ready a resource or exhaust a unit").

    Only modes that currently have at least one legal target are offered (you
    cannot "ready a resource" with no exhausted resource).  If no mode has a legal
    target the ability fizzles cleanly and no decision is pushed.  The choice is
    mandatory ("Either … or …", not "may") — no decline is offered once a mode is
    available.

    The decision proceeds in two stages within one 'modal' decision:
      * stage "mode"   — ``ChooseModalOption(mode)`` selects a mode and advances
                         to the target stage (the chosen mode always has ≥1 target).
      * stage "target" — ``ChooseModalTarget(target_id)`` applies the mode's
                         effect to the chosen target and pops the decision.

    ``decider_id`` hands the MODE stage to another player — "An opponent chooses
    one: [you give an Experience token to a friendly unit] / [you draw a card]"
    (Watto LOF_65).  Every mode still resolves for, and every target is still chosen
    by, the source's CONTROLLER: ``ChooseModalOption`` shifts both the deciding
    player and the seat back before the target stage (the say_no SOR_233 /
    let_wookiee_win SHD_205 decider shift).
    """
    owner_idx = s.player_index(source_ci.owner_id)
    controller_id = source_ci.owner_id
    decider = decider_id or controller_id
    available = [m for m in modes if _modal_mode_targets(s, controller_id, m)]
    if not available:
        return  # no mode has a legal target — fizzle cleanly
    dec = PendingDecision(
        deciding_player_id=decider,
        kind="modal",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "modes": available,
            "stage": "mode",
            "chosen_mode": None,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider,
        kind="modal",
    ))


# ── Let the Wookiee Win push helper (SHD_205) ─────────────────────────────────

def push_let_wookiee_win(s: GameState, source_ci: CardInstance) -> None:
    """Push the 'let_wookiee_win' decision (SHD_205): the OPPONENT chooses one of
    two modes, then the CONTROLLER executes it.

    Both modes are always available ("An opponent chooses one" — neither can be
    illegal: readying up to 6 resources readies 0..6, readying a friendly unit
    readies 0..1), so no fizzle filter is needed.  The opponent is the deciding
    player for the mode stage; ``ChooseWookieeMode`` shifts control back to the
    controller for the ``ready_attack`` target stage (the opponent_chooses_target
    SHD_246 decider-shift pattern)."""
    controller_id = source_ci.owner_id
    controller_idx = s.player_index(controller_id)
    opponent_idx = 1 - controller_idx
    opponent_id = s.players[opponent_idx].player_id
    dec = PendingDecision(
        deciding_player_id=opponent_id,
        kind="let_wookiee_win",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "mode",
        },
        after_resolve_player_index=controller_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = opponent_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=opponent_id,
        kind="let_wookiee_win",
    ))


# ── Repeated-modal push helper (Poe Dameron SHD_153) ──────────────────────────

_REPEATED_MODAL_MODE_LABELS = {
    "deal_2_damage": "Deal 2 damage to a unit or base",
    "defeat_upgrade": "Defeat an upgrade",
    "opponent_discards": "An opponent discards a card",
}

# Modes that require the controller to pick a target.  ``opponent_discards`` has
# no target (the opponent discards the first card of their hand, matching the
# DiscardFromHand(chooser="opponent") simplification), so it resolves without a
# target step.
_REPEATED_MODAL_TARGETED_MODES = {"deal_2_damage", "defeat_upgrade"}


def _repeated_modal_mode_targets(
    state: GameState, controller_id: str, mode: str
) -> list[str]:
    """Legal target instance ids for one repeated-modal option (recomputed from
    current state).

    ``deal_2_damage`` — any unit (either player) or either base (a base is always
    present, so this option always has a target).
    ``defeat_upgrade`` — any real (non-token) upgrade attached to a unit in play,
    matching the kind="upgrade" TargetSpec used by Disabling Fang Fighter SHD_166.
    """
    from swu.cards.models import Upgrade, TokenUpgrade
    if mode == "deal_2_damage":
        out: list[str] = []
        for p in state.players:
            for u in p.ground_arena + p.space_arena:
                out.append(u.instance_id)
            if p.base_instance is not None:
                out.append(p.base_instance.instance_id)
        return out
    if mode == "defeat_upgrade":
        out = []
        for p in state.players:
            for host in p.ground_arena + p.space_arena:
                for upg in host.attached_upgrades:
                    if (isinstance(upg.card_def, Upgrade)
                            and not isinstance(upg.card_def, TokenUpgrade)):
                        out.append(upg.instance_id)
        return out
    return []


def push_repeated_modal(
    s: GameState, source_ci: CardInstance, *,
    modes: Optional[list[str]] = None, max_discards: int = 3,
) -> None:
    """Push a 'repeated_modal' decision: "Discard up to ``max_discards`` cards from
    your hand; for each discarded card, choose a different option" (Poe Dameron,
    SHD_153).

    The controller first discards 0..cap cards (cap = min(max_discards, #modes)),
    then chooses one distinct option per card discarded.  Targeted options
    (deal_2_damage, defeat_upgrade) prompt for a target; opponent_discards needs
    none.  Choices are recorded and applied together once the last option is
    chosen (see ChooseRepeatedTarget / _resolve_repeated_modal).

    Fizzles cleanly (no decision pushed) when the controller's hand is empty —
    "discard up to N" with no cards discards nothing and so grants no options.
    """
    if modes is None:
        modes = ["deal_2_damage", "defeat_upgrade", "opponent_discards"]
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return  # nothing to discard → no options → ability does nothing
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="repeated_modal",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "modes": list(modes),
            "max_discards": int(max_discards),
            "stage": "discard",
            "discarded": 0,
            "plan": [],           # list of [mode, target_id_or_None]
            "used_modes": [],
            "chosen_mode": None,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="repeated_modal",
    ))


def _repeated_modal_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top repeated_modal decision (never empty)."""
    ctx = top.context
    stage = ctx.get("stage")
    if stage == "discard":
        ps = state.player_by_id(ctx["controller_id"])
        cap = min(int(ctx["max_discards"]), len(ctx["modes"]))
        acts: list[Action] = []
        if ctx["discarded"] < cap:
            acts.extend(DiscardForModal(c.instance_id) for c in ps.hand)
        acts.append(FinishModalDiscard())
        return acts
    if stage == "choose_mode":
        return [ChooseRepeatedMode(m) for m in ctx["modes"]
                if m not in ctx["used_modes"]]
    # stage "choose_target"
    return [ChooseRepeatedTarget(t)
            for t in _repeated_modal_mode_targets(
                state, ctx["controller_id"], ctx["chosen_mode"])]


def _begin_repeated_modal_options(s: GameState, top) -> None:
    """End the discard stage: if no card was discarded the ability does nothing
    (pop), otherwise advance to choosing one option per discarded card."""
    ctx = top.context
    if ctx["discarded"] == 0:
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="repeated_modal",
            choice="discarded 0 cards",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return
    ctx["stage"] = "choose_mode"


def _maybe_finish_repeated_modal(s: GameState, top) -> GameState:
    """If one option has been chosen for every discarded card, resolve them all;
    otherwise stay in the mode stage for the next option."""
    ctx = top.context
    if len(ctx["plan"]) >= ctx["discarded"]:
        return _resolve_repeated_modal(s, top)
    ctx["stage"] = "choose_mode"
    return s


def _resolve_repeated_modal(s: GameState, top) -> GameState:
    """Pop the decision, then apply each recorded option in order.

    Effects are applied AFTER popping (like push_distribute_damage) so that a
    defeat/damage trigger pushed by an option lands on a clean stack rather than
    burying an open repeated_modal decision."""
    ctx = top.context
    plan = list(ctx["plan"])
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="repeated_modal",
        choice=", ".join(_REPEATED_MODAL_MODE_LABELS.get(m, m) for m, _ in plan),
    ))
    source_result = s.find_instance(ctx["source_id"])
    source_ci = source_result[1] if source_result else None
    source_name = source_ci.card_def.display_name if source_ci is not None else None
    for mode, target_id in plan:
        _apply_repeated_modal_option(s, ctx["controller_id"], mode, target_id, source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _apply_repeated_modal_option(
    s: GameState, controller_id: str, mode: str,
    target_id: Optional[str], source_name: Optional[str],
) -> None:
    """Apply one chosen repeated-modal option (Poe Dameron SHD_153)."""
    from swu.abilities.resolver import _apply_deal_damage, _apply_defeat_unit
    if mode == "deal_2_damage":
        if target_id is not None:
            _apply_deal_damage(s, target_id, 2, source_name=source_name)
    elif mode == "defeat_upgrade":
        if target_id is not None:
            _apply_defeat_unit(s, target_id)
    elif mode == "opponent_discards":
        # The opponent of the controller discards the first card of their hand
        # (matches DiscardFromHand(chooser="opponent")); fizzles on empty hand.
        opp = s.players[1 - s.player_index(controller_id)]
        if opp.hand:
            ci = opp.hand.pop(0)
            ci.zone = Zone.DISCARD
            opp.discard.append(ci)


# ── choose_two_modal: "Choose two, in any order" aspect events ────────────────

def _choose_two_modal_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top choose_two_modal decision — pick any option not
    yet chosen (mandatory "choose two"; no decline)."""
    ctx = top.context
    chosen = set(ctx["chosen"])
    return [SelectModalOption(i)
            for i in ctx["option_indices"] if i not in chosen]


def push_choose_modal(
    s: GameState, source_ci: CardInstance, *,
    option_indices: list[int], pick: int = 2, decider_id: str | None = None,
) -> None:
    """Push a 'choose_two_modal' decision: "Choose ``pick`` of the given options,
    in any order" (the SOR aspect events).

    ``option_indices`` are the ability indices of the option specs registered on
    the card (each a spec — a TriggerAbility for the SOR events, an EventAbility
    for a unit card whose option specs must not be trigger-collected — whose
    ``.effects`` is that option's effect list).  The decider picks ``pick``
    distinct options one at a time (the pick order is the resolution order); once
    ``pick`` are chosen the decision resolves (_resolve_choose_two_modal), pushing
    one resolve_effects decision per chosen option in reverse pick order so the
    first-chosen resolves first via the LIFO stack.  All option targeting is
    delegated to the resolve_effects machinery, addressed to the CONTROLLER.

    ``decider_id`` (default = the source's controller) is who PICKS the option(s).
    Set it to the controller's opponent for "An opponent chooses one:" (Luke
    Skywalker LAW_80) — the say_no SOR_233 decider shift: the opponent picks the
    mode, then _resolve_choose_two_modal hands the chosen option's resolution back
    to the controller ("You may deal 5 …" is still the controller's choice)."""
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    pick = min(int(pick), len(option_indices))
    if pick <= 0:
        return
    if decider_id is None:
        decider_id = controller_id
    decider_idx = s.player_index(decider_id)
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="choose_two_modal",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "decider_id": decider_id,
            "set_code": source_ci.card_def.set_code or "",
            "card_number": source_ci.card_def.card_number or "",
            "option_indices": list(option_indices),
            "pick": pick,
            "chosen": [],
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = decider_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id, kind="choose_two_modal"))


def _resolve_choose_two_modal(s: GameState, top) -> GameState:
    """Pop the choose_two_modal decision, then push a resolve_effects decision per
    chosen option in REVERSE pick order (so the first-chosen option resolves first
    off the LIFO stack).  Each option resolves through the standard resolve_effects
    machinery addressed to its (set, number, ability_idx) with a fresh event_ctx,
    exactly as _resolve_event_ability pushes one resolve_effects per EventAbility."""
    ctx = top.context
    chosen = list(ctx["chosen"])
    set_code = ctx["set_code"]
    card_number = ctx["card_number"]
    source_id = ctx["source_id"]
    controller_id = ctx["controller_id"]
    after_idx = top.after_resolve_player_index
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="choose_two_modal",
        choice=f"options {chosen}",
    ))
    for opt_idx in reversed(chosen):
        dec = PendingDecision(
            deciding_player_id=controller_id,
            kind="resolve_effects",
            context={
                "set_code": set_code,
                "card_number": card_number,
                "ability_idx": int(opt_idx),
                "source_id": source_id,
                "effect_idx": 0,
                "resolved_targets": {},
                "event_ctx": {},
                "after_all_player_idx": after_idx,
            },
            after_resolve_player_index=after_idx,
        )
        s.pending_decisions.append(dec)
        s.event_log.append(DecisionPushed(
            deciding_player_id=controller_id, kind="resolve_effects"))
    if not s.is_terminal():
        s.active_player_index = s.player_index(controller_id)
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "modal":                         _modal_actions,
    "let_wookiee_win":               _let_wookiee_win_actions,
    "repeated_modal":                _repeated_modal_actions,
    "choose_two_modal":              _choose_two_modal_actions,
})
