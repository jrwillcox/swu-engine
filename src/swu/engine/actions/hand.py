"""Playing a card from somewhere the normal play step cannot reach, and the
opponent-facing decisions that turn out to be inseparable from it.

Two groups of decision live here, and the honest thing to say is that the first attempt
at this module tried to split them:

**Playing from an unusual source.** A card played during your action phase, paid for
normally, needs no decision at all. These are the cases that do: playing from hand
because an effect granted it rather than because you paid, ``play_via_smuggle``,
``play_via_piloting``, playing a unit out of your resource row, and playing a captured
card. Each has to re-derive what is actually playable -- ``_playable_units_from_hand``,
``_smuggle_eligible_from_resources``, ``_piloting_eligible_from_hand`` -- because a
granted play does not mean a free play, and affordability still has to be checked at the
moment the decision resolves rather than when it was pushed.

**The opponent acting, or being looked at.** ``say_no`` (the opponent may pay to refuse
an effect), ``opponent_ready`` (the opponent readies a unit), and looking at the
opponent's hand.

Those two read like separate modules, and splitting them was tried and measured before
this module was written. They are **mutually recursive**, in two places and in opposite
directions:

* ``SayNo.apply`` finishes by playing a named card free from hand or resources
  (*A Precarious Predicament*, LOF_222) -- so the opponent-facing half calls into the
  playing half.
* ``PlayFromHand`` and ``push_play_from_hand`` push an opponent-ready decision -- so the
  playing half calls into the opponent-facing half.

Either edge alone could have been broken by moving one helper. Both together cannot be,
and a module boundary drawn through a cycle is worse than no boundary: it would force one
of these two files to import the other at function scope and hide the coupling instead of
removing it. So they are one module, on purpose, and this paragraph is here so the next
person to notice the seam does not have to re-measure it.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, CardResourced,
    DecisionPushed, DecisionResolved, UnitReadied,
)
from swu.engine.state import CardInstance, GameState, PlayerState, Zone
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _effective_cost, _event_aspect_waiver, _exhaust_resources, _ignorable_aspect_penalty, _pay_play_cost, _piloting_cost, _piloting_discount_entry, _play_cost, _play_reduction_for, _smuggle_cost, _usable_credits,
)
from swu.engine.actions.zones import (
    _apply_capture, _attach_upgrade, _draw_cards, _eligible_upgrade_targets, _find_in_arenas, _put_unit_in_play, _resolve_event_ability,
)
from swu.engine.actions.shared import (
    _apply_defeat_unit_by_id, _attach_pilot, _candidate_card_views, _eligible_pilot_targets, _resource_top_of_deck, _take_from_hand,
)
from swu.engine.actions.combat import (
    push_select_token,
)
from swu.engine.actions.observers import (
    _fire_defeat_own_resource,
)


# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class PlayFromHand(Action):
    """Resolve a 'play_from_hand' decision by playing the chosen unit from hand,
    paying its effective cost (Admiral Ozzel, SOR_129).

    The unit enters play ready when the decision was pushed with
    ``enters_ready``; once it is in play, each opponent may ready a unit when the
    decision requested ``then_opponents_ready``.
    """
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_from_hand"):
            raise IllegalActionError("No play_from_hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        deciding_ps = s.player_by_id(top.deciding_player_id)

        from_discard = bool(ctx.get("from_discard"))
        played_from_discard = from_discard and any(
            c.instance_id == self.instance_id for c in deciding_ps.discard)
        resources_of = ctx.get("resources_of")
        if resources_of is not None:
            # "Play 1 of an opponent's resources" (Tear This Ship Apart LAW_66) —
            # the card leaves THEIR resource row and enters play under the
            # decider's control; ``owner_id`` is untouched, as at every control seam.
            robbed_ps = s.player_by_id(resources_of)
            ci = next((c for c in robbed_ps.resources
                       if c.instance_id == self.instance_id), None)
            if ci is None:
                raise IllegalActionError(
                    f"Card {self.instance_id} not found in that resource row")
            robbed_ps.resources.remove(ci)
            ci.face_down = False
            ci.exhausted = False
        elif from_discard:
            ci = _take_from_hand_or_discard(deciding_ps, self.instance_id)
        else:
            ci = _take_from_hand(deciding_ps, self.instance_id)
        if not isinstance(ci.card_def, Unit):
            raise IllegalActionError("Chosen card is not a unit")
        trait = ctx.get("trait")
        if trait is not None and trait not in (getattr(ci.card_def, "traits", ()) or ()):
            raise IllegalActionError(f"Chosen unit lacks required trait {trait}")
        aspect = ctx.get("aspect")
        if aspect is not None and aspect not in {
                a.name for a in (getattr(ci.card_def, "aspects", None) or ())}:
            raise IllegalActionError(f"Chosen unit lacks required aspect {aspect}")
        exclude_aspect = ctx.get("exclude_aspect")
        if exclude_aspect is not None and exclude_aspect in {
                a.name for a in (getattr(ci.card_def, "aspects", None) or ())}:
            raise IllegalActionError(f"Chosen unit has excluded aspect {exclude_aspect}")
        eligible_ids = ctx.get("eligible_ids")
        if eligible_ids is not None and self.instance_id not in set(eligible_ids):
            raise IllegalActionError("Chosen unit is not eligible to be played")
        cost_max = ctx.get("cost_max")
        if cost_max is not None and (getattr(ci.card_def, "cost", 0) or 0) > cost_max:
            raise IllegalActionError(
                f"Chosen unit costs more than {cost_max}")

        cost_reduction = _play_reduction_for(
            ci.card_def, int(ctx.get("cost_reduction", 0) or 0),
            ctx.get("cost_reduction_if_trait"))
        if bool(ctx.get("ignore_aspect_penalty")):
            cost_reduction += _ignorable_aspect_penalty(ci.card_def, deciding_ps, s)
        if bool(ctx.get("free")):
            cost = 0
        else:
            cost = max(0, _effective_cost(ci.card_def, deciding_ps, s) - cost_reduction)
        # Pay from ready resources, defeating Credit tokens for any shortfall
        # (jabba-the-hutt:07); credits_defeated drives the "if you defeated a
        # Credit while paying its cost" rider below.
        credits_defeated = _pay_play_cost(s, deciding_ps, cost)

        card_played_evt = CardPlayed(
            player_id=deciding_ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(deciding_ps.player_id)

        enters_ready = bool(ctx.get("enters_ready"))
        then_opp = bool(ctx.get("then_opponents_ready"))
        then_damage = int(ctx.get("then_damage", 0) or 0)
        then_damage_source = ctx.get("then_damage_source")
        # Galactic Ambition SOR_235: "Deal damage to your base equal to its cost."
        # Captured BEFORE the play so it reads the played unit's printed cost (the
        # paid cost is 0 under ``free``).
        self_base_dmg = (getattr(ci.card_def, "cost", 0) or 0) if bool(
            ctx.get("then_self_base_damage_cost")) else 0
        grant_keyword = ctx.get("grant_keyword")
        # "If you defeated a Credit while paying its cost, that unit gains <kw>
        # for this phase" — Jabba the Hutt LAW_15 deployed action.
        gk_if_credit = ctx.get("grant_keyword_if_credit_spent")
        if gk_if_credit and credits_defeated > 0:
            grant_keyword = gk_if_credit
        after_idx = top.after_resolve_player_index
        s.pending_decisions.pop()

        # "Play UP TO N units …" (Dathomiri Magicks ASH_104): re-push the loop with
        # one play fewer, BEFORE this unit enters play, so its own When Played
        # triggers land on TOP and resolve before the next pick — faithful "one at
        # a time" (the Endless Legions SHD_109 ordering).  The chosen card has
        # already left its zone, so it cannot be offered again, and nothing is
        # re-pushed once no candidate remains (a decision is never empty).
        repeat_left = int(ctx.get("repeat_max", 0) or 0)
        if repeat_left > 0:
            next_ctx = dict(ctx)
            next_ctx["repeat_max"] = repeat_left - 1
            if _play_from_hand_candidates(s, deciding_ps, next_ctx):
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=top.deciding_player_id,
                    kind="play_from_hand",
                    context=next_ctx,
                    after_resolve_player_index=after_idx,
                ))
                s.event_log.append(DecisionPushed(
                    deciding_player_id=top.deciding_player_id,
                    kind="play_from_hand",
                ))

        # Push the opponent-ready step first (bottom of stack) so the played
        # unit's own When Played triggers — pushed on top by _put_unit_in_play —
        # resolve before opponents react.
        if then_opp:
            _push_opponents_ready(s, deciding_ps, after_idx)
        if resources_of is not None and bool(
                ctx.get("then_owner_resources_deck_top")):
            # "If you do, that opponent resources the top card of their deck."
            # LAW_66's own rules note: "Resources enter play exhausted."
            robbed = s.player_by_id(resources_of)
            before = len(robbed.resources)
            _resource_top_of_deck(s, robbed)
            if len(robbed.resources) > before:
                robbed.resources[-1].exhausted = True
        _put_unit_in_play(
            s, deciding_ps, ci, enters_ready=enters_ready,
            then_damage=then_damage, then_damage_source=then_damage_source,
            grant_keyword=grant_keyword,
            play_source="discard" if played_from_discard else "hand",
            cost_paid=cost,
            defeat_at_regroup=bool(ctx.get("defeat_at_regroup")),
        )
        get_bus().fire(s, card_played_evt)

        # "Deal damage to your base equal to its cost" (Galactic Ambition SOR_235),
        # after the unit is in play and its play event fired.
        if self_base_dmg > 0 and deciding_ps.base_instance is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(
                s, deciding_ps.base_instance.instance_id, self_base_dmg,
                source_name=ctx.get("then_damage_source"))

        # "Then, defeat the chosen units" — the units whose combined power set this
        # play's cost ceiling (Consolidation of Power TWI_89).  After the play, so
        # the newly-played unit is never one of them.
        for _cid in (ctx.get("then_defeat_ids") or ()):
            if s.find_instance(_cid) is not None:
                _apply_defeat_unit_by_id(s, _cid)

        # "It gains Hidden … Give an Experience token and a Shield token to IT"
        # (Three Lessons LOF_225) — choice-free tokens on the just-played unit, and
        # a one-shot damage prevention on it (Shien Flurry LOF_220).  Both settle
        # before any decision-pushing payoff below.
        if s.find_instance(ci.instance_id) is not None:
            from swu.engine.tokens import attach_token
            for _tt in (ctx.get("then_tokens") or ()):
                attach_token(s, deciding_ps, ci, _tt)
            _prevent = int(ctx.get("then_prevent_next_damage", 0) or 0)
            if _prevent > 0:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=ci.instance_id,
                    kind="damage_prevention",
                    value={"amount": _prevent, "once": True},
                    duration="this_phase",
                ))

        # "If you do, give a Shield to a unit / give ANOTHER unit +1/+0" — the
        # settle payoff, so the just-played unit counts toward the gate and can be
        # excluded from the choice (Lando JTL_3 / Major Vonreg JTL_11).
        # "…play a unit from your hand.  The chosen unit CAPTURES it" (DJ SEC_18) —
        # a settle payoff like then_select_token, so the capture runs once the play
        # has really resolved.  DOCUMENTED ORDERING DEVIATION: the printed reminder
        # says When Played abilities resolve AFTER the capture, but a played unit's
        # own triggers are pushed on top and resolve first.
        captor_id = ctx.get("then_capture_by")
        if captor_id and not s.is_terminal():
            cap_res = s.find_instance(captor_id)
            prey_res = s.find_instance(ci.instance_id)
            if cap_res is not None and prey_res is not None:
                _apply_capture(s, captor_id, ci.instance_id)

        tok = ctx.get("then_select_token")
        if tok and not s.is_terminal():
            src_res = s.find_instance(ctx["source_id"])
            gate_ok = True
            if tok.get("require_both_arenas"):
                gate_ok = bool(deciding_ps.ground_arena and deciding_ps.space_arena)
            if src_res is not None and gate_ok:
                kwargs = {k: v for k, v in tok.items()
                          if k not in ("require_both_arenas", "exclude_played",
                                       "restrict_played")}
                if tok.get("exclude_played"):
                    kwargs["exclude_ids"] = [ci.instance_id]
                # "…play a unit from your hand and give 2 Experience tokens to IT"
                # (The Burden of Masters LOF_125) — the complement of
                # ``exclude_played``: the payoff lands only on the played unit.
                if tok.get("restrict_played"):
                    kwargs["restrict_ids"] = [ci.instance_id]
                push_select_token(s, src_res[1], **kwargs)

        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id} from hand"


@dataclass
class ReadyUnit(Action):
    """Resolve an 'opponent_ready' decision by readying one of the deciding
    player's exhausted units ("Each opponent may ready a unit", Admiral Ozzel).
    """
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_ready"):
            raise IllegalActionError("No opponent_ready decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.deciding_player_id)
        unit = _find_in_arenas(ps, self.instance_id)
        if unit is None:
            raise IllegalActionError(f"Unit {self.instance_id} not controlled by decider")
        if not unit.exhausted:
            raise IllegalActionError("Unit is already ready")
        unit.exhausted = False
        s.event_log.append(UnitReadied(
            player_id=ps.player_id,
            instance_id=unit.instance_id,
            card_name=unit.card_def.display_name,
        ))
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_ready",
            choice=f"readied {unit.card_def.display_name}",
        ))
        s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Ready {self.instance_id}"


@dataclass
class DeclineReadyUnit(Action):
    """Decline the optional 'opponent_ready' ready ("may ready a unit")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_ready"):
            raise IllegalActionError("No opponent_ready decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_ready",
            choice="declined",
        ))
        s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to ready a unit"


# ── Opponent "say no" reaction (say_no decision) ──────────────────────────────

@dataclass
class AllowEffect(Action):
    """Resolve a 'say_no' decision by allowing the effect: deal the configured
    damage to the targeted unit (the controller does not say 'no')."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "say_no"):
            raise IllegalActionError("No say_no decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        target_id = ctx["target_id"]
        damage = int(ctx["damage"])
        # The buried resolve_effects decision remains on the stack; record its
        # depth so we only hand control back when the effect didn't push a
        # further decision (e.g. a defeated unit's WhenDefeated trigger).
        depth_before = len(s.pending_decisions)
        if ctx.get("effect") == "draw_top_card":
            # Cikatro Vizago SEC_218: the opponent did NOT pay, so the source's
            # controller draws the card revealed off the top of their own deck.
            controller_ps = s.player_by_id(ctx["controller_id"])
            drew = _draw_cards(s, controller_ps, 1)
            choice = f"did not pay — {controller_ps.player_id} drew {drew}"
        elif ctx.get("effect") == "opponent_heal_base":
            # Lom Pyke TS26_51: the decider took the option, so THEIR base is healed
            # and the source's controller collects the payoff.  Routed through
            # ``_apply_heal`` so the Wolffe SOR_160 lock and the base-heal ledger
            # (``note_base_healed``) both apply; the ``select_token`` payoff is
            # pushed AFTER the pop, addressed to the controller, so it lands on a
            # clean stack (the pop-then-act rule).
            from swu.abilities.resolver import _apply_heal
            src_res = s.find_instance(ctx["source_id"])
            decider_ps = s.player_by_id(top.deciding_player_id)
            amount = int(ctx.get("heal_amount", 0) or 0)
            base_ci = decider_ps.base_instance
            if base_ci is not None and src_res is not None:
                s = _apply_heal(s, src_res[1], base_ci.instance_id, amount)
            tokens = int(ctx.get("then_experience", 0) or 0)
            if tokens and src_res is not None and not s.is_terminal():
                push_select_token(
                    s, s.find_instance(ctx["source_id"])[1],
                    token_type="Experience", max_targets=1, token_count=tokens,
                    controller="any", mandatory=True,
                    decider_id=ctx["controller_id"],
                    after_resolve_idx=top.after_resolve_player_index,
                )
            choice = f"healed {amount} from their base"
        elif ctx.get("effect") == "return_to_hand":
            # "Return an enemy non-leader unit to its owner's hand unless its
            # controller says …" (A Precarious Predicament LOF_222).
            from swu.abilities.resolver import _apply_return_to_hand
            s = _apply_return_to_hand(s, target_id)
            choice = "allowed the bounce"
        else:
            from swu.abilities.resolver import _apply_deal_damage
            s = _apply_deal_damage(s, target_id, damage)
            choice = f"allowed {damage} damage"
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="say_no",
            choice=choice,
        ))
        if not s.is_terminal() and len(s.pending_decisions) == depth_before:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Allow the effect"


@dataclass
class SayNo(Action):
    """Resolve a 'say_no' decision by saying "no": the effect is prevented (no
    damage) and the effect's controller draws the configured number of cards."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "say_no"):
            raise IllegalActionError("No say_no decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        controller_ps = s.player_by_id(ctx["controller_id"])
        # A PRICED refusal (Cikatro Vizago SEC_218) — the decider pays to say no.
        price = int(ctx.get("pay_to_refuse", 0) or 0)
        if price:
            _exhaust_resources(s.player_by_id(top.deciding_player_id), price)
        drew = _draw_cards(s, controller_ps, int(ctx["draw"]))
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="say_no",
            choice=(f"paid {price} to refuse" if price
                    else f"said no — {controller_ps.player_id} drew {drew}"),
        ))
        # "If they do, you may play a card named X from your hand or resources for
        # free" (A Precarious Predicament LOF_222) — a refusal payoff settled here,
        # after the pop, so the play lands on a clean stack.
        payoff = ctx.get("refuse_play_named")
        if payoff and not s.is_terminal():
            src = s.find_instance(ctx["source_id"])
            if src is not None:
                _play_named_free_from_hand_or_resources(s, src[1], ctx["controller_id"],
                                                        str(payoff))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Say 'no'"


# ── Play a captured card for free under your control (play_captured_card) ─────

@dataclass
class SelectCapturedToPlay(Action):
    """Select one captured Unit (guarded by a friendly unit) to play for free."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_captured_card"):
            raise IllegalActionError("No play_captured_card decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a captured candidate")
        return _finish_play_captured(s, self.instance_id)

    def describe(self) -> str:
        return f"Play captured {self.instance_id} for free"


@dataclass
class DeclineCapturedPlay(Action):
    """Decline to play a captured card (offered only for a 'you may' variant)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_captured_card"):
            raise IllegalActionError("No play_captured_card decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_captured_card", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to play a captured card"


def _finish_play_captured(s: GameState, instance_id: str) -> GameState:
    """Pop the play_captured_card decision: move the chosen captive out of the
    controller's capture pile and put it into play under their control for free."""
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    ci = next((c for c in ps.capture_pile if c.instance_id == instance_id), None)
    name = "nothing"
    if ci is not None:
        ps.capture_pile.remove(ci)
        ci.captured_by = None
        ci.face_down = False
        ci.damage = 0
        ci.exhausted = False
        name = ci.card_def.display_name
        evt = CardPlayed(
            player_id=ps.player_id, instance_id=ci.instance_id,
            card_name=name, cost_paid=0)
        s.event_log.append(evt)
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)
        _put_unit_in_play(s, ps, ci, play_source="capture", cost_paid=0)
        get_bus().fire(s, evt)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="play_captured_card", choice=f"played {name}"))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_play_captured_card(
    s: GameState, source_ci: CardInstance, *, up_to: bool = True,
) -> None:
    """Push a 'play_captured_card' decision: choose one Unit captive in the
    controller's capture pile and play it for free under their control (Dryden Vos
    SHD_192).  Candidates are the Unit captives (all guarded by the controller's
    units); fizzles cleanly (no prompt) if none.  ``up_to`` adds a decline."""
    from swu.cards.models import Unit
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [ci.instance_id for ci in ps.capture_pile
                     if isinstance(ci.card_def, Unit)]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="play_captured_card",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "up_to": bool(up_to),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="play_captured_card"))


def _play_captured_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top play_captured_card decision."""
    ctx = top.context
    acts: list[Action] = [SelectCapturedToPlay(cid) for cid in ctx["candidate_ids"]]
    if ctx.get("up_to"):
        acts.append(DeclineCapturedPlay())
    return acts


# ── Play unit-resources revealed for free, one at a time (play_resource_units) ────

@dataclass
class SelectResourceUnitToPlay(Action):
    """Play one revealed unit-resource for free, then re-offer the rest."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_resource_units"):
            raise IllegalActionError("No play_resource_units decision pending")
        s = copy.deepcopy(state)
        if self.instance_id not in s.pending_decisions[-1].context["candidate_ids"]:
            raise IllegalActionError(
                f"{self.instance_id} is not a revealable unit resource")
        return _finish_play_resource_unit(s, self.instance_id)

    def describe(self) -> str:
        return f"Play unit resource {self.instance_id} for free"


@dataclass
class DeclineResourceUnitPlay(Action):
    """Stop revealing/playing resources (the 'any number' lets the loop end)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_resource_units"):
            raise IllegalActionError("No play_resource_units decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_resource_units", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Stop playing revealed unit resources"


def _finish_play_resource_unit(s: GameState, instance_id: str) -> GameState:
    """Pop the decision, remove the chosen resource from the controller's resource
    row, re-push the loop with the remaining unit-resources, THEN play the chosen
    unit for free — so its triggers, pushed on top, resolve before the next pick."""
    from swu.cards.models import Unit
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    ci = next((c for c in ps.resources if c.instance_id == instance_id), None)
    if ci is None:  # already gone (shouldn't happen) — just settle the active player
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    ps.resources.remove(ci)
    # Re-offer the remaining unit-resources BEFORE playing, so the played unit's When
    # Played triggers land on top of this loop decision and resolve first.
    remaining = [r.instance_id for r in ps.resources if isinstance(r.card_def, Unit)]
    if remaining:
        s.pending_decisions.append(PendingDecision(
            deciding_player_id=top.deciding_player_id,
            kind="play_resource_units",
            context={
                "source_id": ctx["source_id"],
                "controller_id": ctx["controller_id"],
                "candidate_ids": remaining,
                "candidates": _candidate_card_views(s, remaining),
                "up_to": True,
            },
            after_resolve_player_index=top.after_resolve_player_index,
        ))
    ci.face_down = False
    ci.damage = 0
    ci.exhausted = False
    name = ci.card_def.display_name
    evt = CardPlayed(
        player_id=ps.player_id, instance_id=ci.instance_id,
        card_name=name, cost_paid=0)
    s.event_log.append(evt)
    card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
    if "Villainy" in card_aspects:
        s.game_memory.villainy_players_this_phase.add(ps.player_id)
    _put_unit_in_play(s, ps, ci, play_source="resource", cost_paid=0)
    get_bus().fire(s, evt)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="play_resource_units", choice=f"played {name}"))
    if not s.is_terminal():
        if s.pending_decisions:
            s.active_player_index = s.player_index(
                s.pending_decisions[-1].deciding_player_id)
        else:
            s.active_player_index = top.after_resolve_player_index
    return s


def push_play_resource_units(
    s: GameState, source_ci: CardInstance, *, up_to: bool = True,
) -> None:
    """Push a 'play_resource_units' loop: the controller may reveal any number of
    their Unit resources and play each for free, one at a time (Endless Legions
    SHD_109).  Candidates are the controller's Unit resources; fizzles cleanly (no
    prompt) if none.  ``up_to`` is accepted for symmetry — the loop can always be
    stopped (the "any number"), so a decline is always offered."""
    from swu.cards.models import Unit
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [r.instance_id for r in ps.resources
                     if isinstance(r.card_def, Unit)]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="play_resource_units",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "up_to": bool(up_to),
        },
        after_resolve_player_index=1 - owner_idx,
    ))
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="play_resource_units"))


def _play_resource_units_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top play_resource_units decision: play any offered
    unit-resource for free, or decline (stop)."""
    ctx = top.context
    acts: list[Action] = [SelectResourceUnitToPlay(cid) for cid in ctx["candidate_ids"]]
    acts.append(DeclineResourceUnitPlay())
    return acts


# ── Look at an opponent's hand (Viper Probe Droid SOR_228 / SEC_239) ──────────

@dataclass
class AckLookHand(Action):
    """Acknowledge a 'look_hand' decision (you've finished looking at the hand)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "look_hand"):
            raise IllegalActionError("No look_hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="look_hand",
            choice="looked",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Done looking at the opponent's hand"


def push_look_opponent_hand(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'look_hand' decision: the source's controller looks at an opponent's
    hand (Viper Probe Droid).  Records the revealed cards' identities (card_id +
    name only — never the opponent's hidden instance_ids) in the inspecting
    player's decision context so the UI can display them; a single AckLookHand
    resolves it.  A HandInspected event still logs that the look happened."""
    from swu.engine.events import HandInspected
    owner_idx = s.player_index(source_ci.owner_id)
    opp = s.players[1 - owner_idx]
    revealed = [
        {"card_id": ci.card_def.id, "card_name": ci.card_def.display_name}
        for ci in opp.hand
    ]
    s.event_log.append(HandInspected(
        inspecting_player_id=source_ci.owner_id,
        revealed_player_id=opp.player_id,
        card_count=len(opp.hand),
    ))
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="look_hand",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "revealed_player_id": opp.player_id,
            "revealed_hand": revealed,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="look_hand",
    ))


# ── Play a unit from hand as an ability (Admiral Ozzel, SOR_129) ───────

def _play_from_hand_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    # Mandatory if able: only affordable matching units are offered (the
    # decision is pushed only when at least one such unit exists, and the
    # state is unchanged since, so this list is non-empty).  ``up_to`` adds
    # the decline, which is what makes "Play UP TO 3 units …" stoppable
    # (Dathomiri Magicks ASH_104).
    acts: list[Action] = [
        PlayFromHand(ci.instance_id)
        for ci in _play_from_hand_candidates(state, deciding_ps, top.context)
    ]
    if top.context.get("up_to"):
        acts.append(DeclinePlayFromHand())
    return acts


# ── Play an event from hand as an ability (Bib Fortuna, SOR_177) ──────

def _play_event_from_hand_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    ctx = top.context
    elig = ctx.get("eligible_ids")
    return [
        PlayEventFromHand(ci.instance_id)
        for ci in _playable_events_from_hand(
            state, deciding_ps, ctx.get("cost_reduction", 0),
            free=bool(ctx.get("free")),
            eligible_ids=set(elig) if elig is not None else None)
    ]


# ── Play a card using Smuggle as an ability (Lando Calrissian, SHD_17) ─

def _play_via_smuggle_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    cost_reduction = top.context.get("cost_reduction", 0)
    acts: list[Action] = []
    for ci in _smuggle_eligible_from_resources(state, deciding_ps, cost_reduction):
        if isinstance(ci.card_def, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                acts.append(PlayViaSmuggle(ci.instance_id, target.instance_id))
        else:
            acts.append(PlayViaSmuggle(ci.instance_id))
    return acts


# ── Play a card using Piloting as an ability (Wedge Antilles, JTL_8) ───

def _play_via_piloting_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    cost_reduction = top.context.get("cost_reduction", 0)
    return [
        PlayViaPiloting(pilot.instance_id, host.instance_id)
        for pilot, host in _piloting_eligible_from_hand(
            state, deciding_ps, cost_reduction)
    ]


# ── Opponent may ready a unit (Admiral Ozzel, SOR_129) ────────────────

def _opponent_ready_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    acts: list[Action] = [
        ReadyUnit(u.instance_id)
        for u in deciding_ps.ground_arena + deciding_ps.space_arena
        if u.exhausted
    ]
    acts.append(DeclineReadyUnit())
    return acts


# ── Opponent may say "no" to an effect (I Am Your Father, SOR_233) ────

def _say_no_actions(state: GameState, top: PendingDecision) -> list[Action]:
    price = int(top.context.get("pay_to_refuse", 0) or 0)
    if price:
        decider = state.player_by_id(top.deciding_player_id)
        if sum(1 for r in decider.resources if not r.exhausted) < price:
            return [AllowEffect()]
    return [AllowEffect(), SayNo()]


# ── Look at an opponent's hand (Viper Probe Droid SOR_228) ────────────

def _look_hand_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [AckLookHand()]


# ── Play-a-card-from-hand-as-an-ability subsystem (Admiral Ozzel, SOR_129) ────

def _play_from_hand_candidates(
    state: GameState, ps: PlayerState, ctx: dict
) -> list[CardInstance]:
    """The units a pending ``play_from_hand`` decision may currently play, derived
    from its own context.  One place, so the legal-action enumeration and the
    "play up to N" re-push (``PlayFromHand.apply``) can never disagree."""
    return _playable_units_from_hand(
        state, ps, ctx.get("trait"),
        int(ctx.get("cost_reduction", 0) or 0), ctx.get("cost_max"),
        aspect=ctx.get("aspect"),
        free=bool(ctx.get("free")),
        include_discard=bool(ctx.get("from_discard")),
        ignore_aspect_penalty=bool(ctx.get("ignore_aspect_penalty")),
        eligible_ids=(frozenset(ctx["eligible_ids"])
                      if ctx.get("eligible_ids") is not None else None),
        exclude_aspect=ctx.get("exclude_aspect"),
        cost_reduction_if_trait=ctx.get("cost_reduction_if_trait"),
        shares_keyword_with_id=ctx.get("shares_keyword_with_id"),
        resources_of=ctx.get("resources_of"))


def _playable_units_from_hand(
    state: GameState, ps: PlayerState, trait: Optional[str],
    cost_reduction: int = 0, cost_max: Optional[int] = None,
    *, aspect: Optional[str] = None, free: bool = False,
    include_discard: bool = False, ignore_aspect_penalty: bool = False,
    exclude_aspect: Optional[str] = None,
    eligible_ids: Optional[frozenset] = None,
    cost_reduction_if_trait=None,
    shares_keyword_with_id: Optional[str] = None,
    resources_of: Optional[str] = None,
) -> list[CardInstance]:
    """Units in ``ps``'s hand that match ``trait`` (if given) and are currently
    affordable at their effective cost, less ``cost_reduction`` (floored at 0).

    Leaders are never in hand and ``Unit`` excludes ``Leader`` (distinct
    classes), so this naturally returns only ordinary units.  Exploit is *not*
    applied here — the cost reduction is ignored when a unit is played via an
    ability, so an Exploit unit must be affordable at full cost.

    ``cost_max`` (Energy Conversion Lab SOR_22: "a unit that costs 6 resources
    or less") restricts eligibility by the unit's **printed** cost (the cost
    printed on the card, before aspect penalties), per SWU's reading of "costs
    N or less"; affordability is still checked against the aspect-adjusted cost.

    ``aspect`` restricts eligibility to units carrying that aspect (Gideon's
    Light Cruiser SHD_242: "play a [villainy] unit").  ``free`` plays the unit
    for 0 (skips the affordability check entirely — "for free").
    ``include_discard`` also offers eligible units sitting in ``ps``'s discard
    pile ("from your hand or discard pile", SHD_242).

    ``ignore_aspect_penalty`` waives one V/C/A/Cunning aspect penalty (2 resources,
    only if the card carries such a penalty) before checking affordability —
    Daimyo's Palace LAW_20.
    """
    out: list[CardInstance] = []
    if resources_of is not None:
        # "Look at all of an opponent's resources.  You may play 1 of those cards"
        # (Tear This Ship Apart LAW_66) — a FOREIGN resource row replaces the
        # controller's own hand as the source zone.
        zones = [state.player_by_id(resources_of).resources]
    else:
        zones = [ps.hand] + ([ps.discard] if include_discard else [])
    for zone in zones:
        for ci in zone:
            cd = ci.card_def
            if not isinstance(cd, Unit):
                continue
            if eligible_ids is not None and ci.instance_id not in eligible_ids:
                continue
            if shares_keyword_with_id is not None:
                # "Play a unit from your hand that shares a keyword with the CHOSEN
                # unit" (Morgan Elsbeth LOF_5) — printed keywords both sides, the
                # ``_shares_keyword_with_a_unit`` basis pinned to one unit.
                other = state.find_instance(shares_keyword_with_id)
                if other is None:
                    continue
                mine = {str(k).split()[0]
                        for k in (getattr(cd, "keywords", None) or ())}
                theirs = {str(k).split()[0]
                          for k in (getattr(other[1].card_def, "keywords", None) or ())}
                if not (mine and mine & theirs):
                    continue
            if trait is not None and trait not in (getattr(cd, "traits", ()) or ()):
                continue
            if aspect is not None and aspect not in {
                    a.name for a in (getattr(cd, "aspects", None) or ())}:
                continue
            if exclude_aspect is not None and exclude_aspect in {
                    a.name for a in (getattr(cd, "aspects", None) or ())}:
                continue
            if cost_max is not None and (getattr(cd, "cost", 0) or 0) > cost_max:
                continue
            base_reduction = _play_reduction_for(cd, cost_reduction,
                                                 cost_reduction_if_trait)
            reduction = base_reduction + (
                _ignorable_aspect_penalty(cd, ps, state) if ignore_aspect_penalty else 0)
            # Credits can cover a shortfall when paying the played unit's cost
            # (jabba-the-hutt:07), so they count toward affordability here too.
            if free or (
                    max(0, _effective_cost(cd, ps, state) - reduction)
                    <= ps.available_resources + _usable_credits(state, ps)):
                out.append(ci)
    return out


def _push_opponents_ready(
    s: GameState, controller_ps: PlayerState, after_idx: int
) -> bool:
    """Push an 'opponent_ready' decision for each opponent that controls an
    exhausted unit ("Each opponent may ready a unit", Admiral Ozzel).

    Returns True if at least one decision was pushed.  This is a 2-player engine,
    so there is exactly one opponent; the loop keeps the wording faithful and is
    forward-compatible.  The (single) decision restores the active player to
    ``after_idx`` once resolved.
    """
    pushed = False
    opponents = [p for p in s.players if p.player_id != controller_ps.player_id]
    # LIFO push order: reversed so the first opponent in seating order is on top.
    for opp in reversed(opponents):
        if not any(u.exhausted for u in opp.ground_arena + opp.space_arena):
            continue
        dec = PendingDecision(
            deciding_player_id=opp.player_id,
            kind="opponent_ready",
            context={},
            after_resolve_player_index=after_idx,
        )
        s.pending_decisions.append(dec)
        s.active_player_index = s.player_index(opp.player_id)
        s.event_log.append(DecisionPushed(
            deciding_player_id=opp.player_id,
            kind="opponent_ready",
        ))
        pushed = True
    return pushed


def push_play_from_hand(
    s: GameState, source_ci: CardInstance,
    *,
    trait: Optional[str] = None,
    enters_ready: bool = False,
    then_opponents_ready: bool = False,
    cost_reduction: int = 0,
    then_damage: int = 0,
    cost_max: Optional[int] = None,
    grant_keyword: Optional[str] = None,
    aspect: Optional[str] = None,
    free: bool = False,
    from_discard: bool = False,
    ignore_aspect_penalty: bool = False,
    grant_keyword_if_credit_spent: Optional[str] = None,
    defeat_at_regroup: bool = False,
    exclude_aspect: Optional[str] = None,
    eligible_ids: Optional[frozenset] = None,
    then_self_base_damage_cost: bool = False,
    cost_reduction_if_trait=None,
    then_defeat_ids=None,
    then_select_token: Optional[dict] = None,
    then_capture_by: Optional[str] = None,
    shares_keyword_with_id: Optional[str] = None,
    then_tokens: Optional[list[str]] = None,
    then_prevent_next_damage: int = 0,
    resources_of: Optional[str] = None,
    then_owner_resources_deck_top: bool = False,
    repeat_max: int = 0,
    up_to: bool = False,
) -> None:
    """Push a 'play_from_hand' decision: the source's controller plays a unit
    (matching ``trait`` if given) from hand, paying its cost (Admiral Ozzel).

    ``resources_of`` swaps the source zone from the controller's own hand to
    ANOTHER player's RESOURCE row — "Look at all of an opponent's resources.  You
    may play 1 of those cards for free" (Tear This Ship Apart LAW_66).  The card
    leaves that row (so its owner really is a resource down) and enters play under
    whoever played it, ``owner_id`` unchanged, as every control seam does.
    ``then_owner_resources_deck_top`` is its "If you do" rider: the robbed player
    resources the top card of their deck.  Face-down resources are not modelled as
    hidden info by the engine's view layer (unlike a hand or deck), so listing them
    in the decision needs no invariant exemption — and the card's whole point is
    that the controller sees them.

    Parameters
    ----------
    trait
        If set, only hand units with this trait are playable (e.g. "Imperial").
    enters_ready
        The played unit enters play ready instead of exhausted.
    then_opponents_ready
        After the unit is played, each opponent may ready a unit.
    cost_reduction
        Resources subtracted (floored at 0) from the played unit's effective
        cost — "play a unit from your hand, it costs N less" (Han Solo SHD_13).
        Applied to both the affordability check and the actual payment.
    then_damage
        Damage dealt to the played unit immediately after it enters play, before
        its own "When Played" abilities resolve (Han Solo deals 2 to it).
    cost_max
        If set, only hand units whose **printed** cost is ≤ this are playable
        ("Play a unit that costs 6 resources or less" — Energy Conversion Lab
        SOR_22).
    grant_keyword
        If set, the played unit gains this keyword **for this phase**, applied
        as a ``keyword_grant`` modifier *before* its enter-play keyword bus
        fires — so a granted Ambush triggers immediately on entry (Energy
        Conversion Lab SOR_22 / Timely Intervention SHD_129: "Give it Ambush
        for this phase").
    aspect
        If set, only hand units carrying this aspect are playable ("play a
        [villainy] unit" — Gideon's Light Cruiser SHD_242).
    free
        Play the chosen unit for 0 resources ("for free"); the affordability
        check is skipped so any matching unit is eligible (SHD_242).
    from_discard
        Also offer eligible units from the controller's discard pile, not just
        hand ("from your hand or discard pile" — SHD_242).  A discard-played
        unit enters play exactly like a hand play (play_source "discard").
    ignore_aspect_penalty
        Ignore one Vigilance/Command/Aggression/Cunning aspect penalty (2
        resources, only if the card carries such a penalty) when computing the
        played unit's cost — Daimyo's Palace LAW_20.  Fully-matched cards and
        Heroism/Villainy penalties are unaffected; combines additively with
        ``cost_reduction`` (floored at 0).
    grant_keyword_if_credit_spent
        If a Credit token was defeated while paying the played unit's cost
        (jabba-the-hutt:07), the unit gains this keyword **for this phase** —
        Jabba the Hutt LAW_15: "Play an Underworld unit from your hand.  If you
        defeated a Credit while paying its cost, that unit gains Ambush for this
        phase."  Credit-spend is need-based (see ``_pay_play_cost``), so the
        keyword is granted only when the unit's cost exceeded the controller's
        ready resources and a credit covered the shortfall.
    defeat_at_regroup
        The played unit is defeated at the start of the next regroup phase —
        Sneak Attack SOR_219 ("Play a unit from your hand … At the start of the
        regroup phase, defeat it.").  Threaded onto the unit's
        ``defeat_at_regroup`` flag; the sweep lives in ``_enter_regroup``.
    exclude_aspect
        If set, hand units carrying this aspect are NOT playable ("Play a
        **non-Villainy** unit …" — Qui-Gon Jinn LOF_16).
    eligible_ids
        If set, only units whose ``instance_id`` is in this whitelist are
        playable — "play a unit **that was defeated this phase** from your discard
        pile" (Unnatural Life TWI_189, computed from
        ``game_memory.units_defeated_this_round`` at push time and stored as a list
        in the decision context).
    then_self_base_damage_cost
        After the unit enters play, deal damage to the CONTROLLER's own base equal
        to the played unit's **printed** cost — "Play a … unit from your hand for
        free.  Deal damage to your base equal to its cost." (Galactic Ambition
        SOR_235).  Read off the printed cost (not the paid cost, which is 0 under
        ``free``).

    The play is mandatory if able: ``legal_actions`` offers a ``PlayFromHand``
    for every affordable matching unit and no decline.  If no matching unit is
    affordable the play fizzles and we proceed straight to the opponent-ready
    step (when requested).  The decision carries no transient state, so it
    serialises cleanly.
    """
    owner_idx = s.player_index(source_ci.owner_id)
    owner_ps = s.player_by_id(source_ci.owner_id)
    after_idx = 1 - owner_idx
    candidates = _playable_units_from_hand(
        s, owner_ps, trait, cost_reduction, cost_max,
        aspect=aspect, free=free, include_discard=from_discard,
        ignore_aspect_penalty=ignore_aspect_penalty, exclude_aspect=exclude_aspect,
        eligible_ids=eligible_ids, cost_reduction_if_trait=cost_reduction_if_trait,
        shares_keyword_with_id=shares_keyword_with_id, resources_of=resources_of)
    if candidates:
        # Candidates sitting in the DISCARD pile are not clickable board subjects
        # in the web client (the discard is a non-interactive pile), so surface
        # their identities for a selection overlay; hand candidates stay clickable
        # on the board as normal (Gideon's Light Cruiser SHD_242 plays from hand
        # OR discard for free — a discard-only candidate was otherwise a hard stuck
        # since play_from_hand is mandatory with no decline).
        discard_ids = {c.instance_id for c in owner_ps.discard}
        discard_candidates = _candidate_card_views(
            s, [c.instance_id for c in candidates if c.instance_id in discard_ids])
        if resources_of is not None:
            # A face-down resource is no clickable board subject either — surface
            # the candidates for the same selection overlay the discard uses.
            discard_candidates = _candidate_card_views(
                s, [c.instance_id for c in candidates])
        dec = PendingDecision(
            deciding_player_id=source_ci.owner_id,
            kind="play_from_hand",
            context={
                "source_id": source_ci.instance_id,
                "discard_candidates": discard_candidates,
                "trait": trait,
                "enters_ready": enters_ready,
                "then_opponents_ready": then_opponents_ready,
                "cost_reduction": cost_reduction,
                "then_damage": then_damage,
                "then_damage_source": source_ci.card_def.display_name,
                "cost_max": cost_max,
                "grant_keyword": grant_keyword,
                "aspect": aspect,
                "free": free,
                "from_discard": from_discard,
                "ignore_aspect_penalty": ignore_aspect_penalty,
                "grant_keyword_if_credit_spent": grant_keyword_if_credit_spent,
                "defeat_at_regroup": defeat_at_regroup,
                "exclude_aspect": exclude_aspect,
                "eligible_ids": (list(eligible_ids)
                                 if eligible_ids is not None else None),
                "then_self_base_damage_cost": then_self_base_damage_cost,
                "cost_reduction_if_trait": (list(cost_reduction_if_trait)
                                            if cost_reduction_if_trait is not None
                                            else None),
                # Units defeated once this play resolves — "Then, defeat the chosen
                # units" (Consolidation of Power TWI_89), whose power paid for it.
                "then_defeat_ids": (list(then_defeat_ids)
                                    if then_defeat_ids is not None else None),
                # "…If you do, <give a token / buff a unit>" — kwargs for a
                # ``select_token`` pushed at the SETTLE, once the play has really
                # happened (Lando Calrissian JTL_3's Shield, Major Vonreg JTL_11's
                # +1/+0).  It cannot be a second effect of the ability: the
                # resolve_effects walker resolves a no-target effect only when the
                # LATER targeted one is chosen, so the payoff would land before the
                # play.  Two extra keys are settled here rather than passed on:
                # ``require_both_arenas`` (the play must leave the controller
                # holding a ground AND a space unit) and ``exclude_played`` (the
                # printed "ANOTHER unit").
                "then_select_token": (dict(then_select_token)
                                      if then_select_token else None),
                # "The chosen unit CAPTURES it" (DJ SEC_18) — a settle payoff
                # naming the captor, applied once the play has really happened.
                "then_capture_by": then_capture_by,
                # "Play a unit … that shares a keyword with the chosen unit"
                # (Morgan Elsbeth LOF_5) — a per-candidate filter re-derived by the
                # enumeration, so it stays exact if the board moves.
                "shares_keyword_with_id": shares_keyword_with_id,
                # "Give an Experience token and a Shield token to it" (Three Lessons
                # LOF_225) — tokens landed directly on the played unit, no choice to
                # make, which is why this is not the ``then_select_token`` rider.
                "then_tokens": list(then_tokens or []),
                # "Look at all of an opponent's resources.  You may play 1 of
                # those cards for free.  If you do, that opponent resources the
                # top card of their deck." (Tear This Ship Apart LAW_66.)
                "resources_of": resources_of,
                "then_owner_resources_deck_top": bool(then_owner_resources_deck_top),
                # "Play UP TO 3 … units" (Dathomiri Magicks ASH_104): how many
                # FURTHER plays this loop may offer after the current one, and the
                # decline that makes "up to" stoppable.  0/False = the long-standing
                # one-shot, mandatory-if-able decision.
                "repeat_max": int(repeat_max),
                "up_to": bool(up_to),
                # "The next time it would be dealt damage this phase, prevent 2 of
                # that damage" (Shien Flurry LOF_220) — a ONE-SHOT damage_prevention
                # modifier on the played unit.
                "then_prevent_next_damage": int(then_prevent_next_damage),
            },
            after_resolve_player_index=after_idx,
        )
        s.pending_decisions.append(dec)
        s.active_player_index = owner_idx
        s.event_log.append(DecisionPushed(
            deciding_player_id=source_ci.owner_id,
            kind="play_from_hand",
        ))
    elif then_opponents_ready:
        _push_opponents_ready(s, owner_ps, after_idx)


# ── Play an EVENT from hand as an ability (Bib Fortuna SOR_177) ────────────────

def _playable_events_from_hand(
    state: GameState, ps: PlayerState, cost_reduction: int = 0,
    *, free: bool = False, eligible_ids=None, ignore_aspect_penalty: bool = False,
) -> list[CardInstance]:
    """Events in ``ps``'s hand affordable at their effective cost less
    ``cost_reduction`` (floored at 0).  Mirrors ``_playable_units_from_hand``;
    credits count toward affordability as in the unit path.

    ``free`` waives the cost entirely and ``eligible_ids`` whitelists instances —
    together they are "you may play a card named X … for free" (A Precarious
    Predicament LOF_222), the event-side twin of ``push_play_from_hand``'s pair."""
    out: list[CardInstance] = []
    for ci in ps.hand:
        if not isinstance(ci.card_def, Event):
            continue
        if eligible_ids is not None and ci.instance_id not in eligible_ids:
            continue
        waived = _event_aspect_waiver(ci.card_def, ps, ignore_aspect_penalty, state)
        if free or (max(0, _effective_cost(ci.card_def, ps, state) - cost_reduction - waived)
                    <= ps.available_resources + _usable_credits(state, ps)):
            out.append(ci)
    return out


def push_play_event_from_hand(
    s: GameState, source_ci: CardInstance, *, cost_reduction: int = 0,
    free: bool = False, eligible_ids=None, optional: bool = False,
    ignore_aspect_penalty: bool = False,
) -> None:
    """Push a 'play_event_from_hand' decision: the source's controller plays an
    EVENT from hand at ``cost_reduction`` off (Bib Fortuna SOR_177: "Play an event
    from your hand.  It costs 1 resource less.").

    Mandatory if able and pushed only when ≥1 affordable event exists — Bib's
    activated ability is gated by ``CONTROLLER_CAN_PLAY_EVENT_FROM_HAND`` so the
    exhaust is never wasted; it fizzles silently if somehow none remain."""
    owner_idx = s.player_index(source_ci.owner_id)
    owner_ps = s.player_by_id(source_ci.owner_id)
    after_idx = 1 - owner_idx
    if not _playable_events_from_hand(
            s, owner_ps, cost_reduction, free=free, eligible_ids=eligible_ids,
            ignore_aspect_penalty=ignore_aspect_penalty):
        return
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="play_event_from_hand",
        context={
            "source_id": source_ci.instance_id,
            "cost_reduction": cost_reduction,
            "free": bool(free),
            "eligible_ids": (sorted(eligible_ids)
                             if eligible_ids is not None else None),
            "optional": bool(optional),
            # "…ignoring its aspect penalties" (Anakin Skywalker LOF_18) — the whole
            # penalty, waived in both the affordability gate and the payment.
            "ignore_aspect_penalty": bool(ignore_aspect_penalty),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="play_event_from_hand",
    ))


@dataclass
class PlayEventFromHand(Action):
    """Resolve a 'play_event_from_hand' decision by playing the chosen event from
    hand at the stored discount, then resolving its ability (Bib Fortuna SOR_177).

    Mirrors the ``PlayCard`` Event branch (pay cost → discard → resolve ability →
    fire CardPlayed observers), but takes the discount stored on the decision."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_event_from_hand"):
            raise IllegalActionError("No play_event_from_hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        deciding_ps = s.player_by_id(top.deciding_player_id)
        ci = next((c for c in deciding_ps.hand
                   if c.instance_id == self.instance_id), None)
        if ci is None or not isinstance(ci.card_def, Event):
            raise IllegalActionError("Chosen card is not a playable hand event")
        eligible = ctx.get("eligible_ids")
        if eligible is not None and self.instance_id not in set(eligible):
            raise IllegalActionError("Chosen event is not eligible")
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        cost_reduction += _event_aspect_waiver(
            ci.card_def, deciding_ps, bool(ctx.get("ignore_aspect_penalty")), s)
        cost = (0 if ctx.get("free")
                else max(0, _play_cost(s, ci, deciding_ps) - cost_reduction))
        deciding_ps.hand.remove(ci)
        _pay_play_cost(s, deciding_ps, cost)

        card_played_evt = CardPlayed(
            player_id=deciding_ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(deciding_ps.player_id)

        after_idx = top.after_resolve_player_index
        # Pop before resolving so the event's own resolve_effects lands on a clean
        # stack (the "pop, then act" gotcha).
        s.pending_decisions.pop()
        ci.zone = Zone.DISCARD
        deciding_ps.discard.append(ci)
        _resolve_event_ability(s, deciding_ps, ci, after_idx)
        get_bus().fire(s, card_played_evt)
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)

        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play event {self.instance_id} from hand"


# ── Play a card using Smuggle as an ability (Lando Calrissian SHD_17) ──────────

def _smuggle_eligible_from_resources(
    state: GameState, ps: PlayerState, cost_reduction: int = 0,
) -> list[CardInstance]:
    """Resource-zone cards ``ps`` may play via Smuggle at ``cost_reduction`` off,
    affordable from the OTHER ready resources (the smuggled card leaves the zone and is
    replaced from the deck top).  Mirrors ``_enumerate_smuggle_plays``' affordability;
    an eligible Upgrade must also have ≥1 legal host, so this list and the offered
    ``PlayViaSmuggle`` actions never disagree (no empty-decision stuck)."""
    out: list[CardInstance] = []
    for ci in ps.resources:
        base = _smuggle_cost(state, ci, ps)
        if base is None:
            continue
        cost = max(0, base - cost_reduction)
        other_ready = sum(
            1 for r in ps.resources
            if not r.exhausted and r.instance_id != ci.instance_id)
        if other_ready < cost:
            continue
        if isinstance(ci.card_def, Upgrade) and not _eligible_upgrade_targets(state, ci):
            continue
        out.append(ci)
    return out


def push_play_via_smuggle(
    s: GameState, source_ci: CardInstance, *,
    cost_reduction: int = 0, then_defeat_own_resource: bool = False,
) -> None:
    """Push a 'play_via_smuggle' decision: the source's controller plays a card from
    their resource zone using Smuggle at ``cost_reduction`` off, then (if
    ``then_defeat_own_resource``) defeats a resource they own (Lando SHD_17).

    Mandatory if able and pushed only when ≥1 smuggle-eligible resource exists (Lando's
    ability is gated by ``CONTROLLER_CAN_SMUGGLE`` so its Exhaust / once-per-round is
    not wasted); fizzles silently if somehow none remain."""
    owner_idx = s.player_index(source_ci.owner_id)
    owner_ps = s.player_by_id(source_ci.owner_id)
    after_idx = 1 - owner_idx
    if not _smuggle_eligible_from_resources(s, owner_ps, cost_reduction):
        return
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="play_via_smuggle",
        context={
            "source_id": source_ci.instance_id,
            "cost_reduction": cost_reduction,
            "then_defeat_own_resource": then_defeat_own_resource,
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="play_via_smuggle"))


@dataclass
class PlayViaSmuggle(Action):
    """Resolve a 'play_via_smuggle' decision by playing the chosen resource-zone card
    using Smuggle at the stored discount, then optionally defeating a resource the
    controller owns (Lando Calrissian SHD_17).

    Mirrors SmugglePlay's core (leave the zone → pay the reduced smuggle cost from the
    OTHER resources → replace from the deck top → play the card with ``via_smuggle``)
    but pops the decision first and does NOT hand the turn over itself (the after-index
    stored on the decision governs)."""
    instance_id: str
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_via_smuggle"):
            raise IllegalActionError("No play_via_smuggle decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(top.deciding_player_id)
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        after_idx = top.after_resolve_player_index

        ci = None
        for i, r in enumerate(ps.resources):
            if r.instance_id == self.instance_id:
                ci = ps.resources.pop(i)
                break
        if ci is None:
            raise IllegalActionError(
                f"Smuggle source {self.instance_id} not in resource zone")
        base = _smuggle_cost(s, ci, ps)
        if base is None:
            raise IllegalActionError(
                f"{ci.card_def.display_name} cannot be played using Smuggle")
        cost = max(0, base - cost_reduction)
        if ps.available_resources < cost:
            raise IllegalActionError(
                f"Insufficient resources: need {cost}, have {ps.available_resources}")
        _exhaust_resources(ps, cost)

        # Replace the smuggled card with the top card of the deck (deterministic).
        if ps.deck:
            repl = ps.deck.pop(0)
            repl.zone = Zone.RESOURCES
            repl.face_down = True
            repl.exhausted = False
            ps.resources.append(repl)
            s.event_log.append(CardResourced(
                player_id=ps.player_id, instance_id=repl.instance_id,
                card_name=repl.card_def.display_name))

        ci.face_down = False
        card_played_evt = CardPlayed(
            player_id=ps.player_id, instance_id=ci.instance_id,
            card_name=ci.card_def.display_name, cost_paid=cost)
        s.event_log.append(card_played_evt)
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)

        # Pop before playing so the card's own triggers/resolution land on a clean
        # stack (the "pop, then act" gotcha).
        s.pending_decisions.pop()

        if isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, via_smuggle=True, play_source="smuggle")
        elif isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id, via_smuggle=True)
        elif isinstance(ci.card_def, Event):
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            _resolve_event_ability(s, ps, ci, after_idx)
        else:
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)

        get_bus().fire(s, card_played_evt)
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)

        # "Defeat a resource you own and control" — auto-selected (resources are
        # fungible face-down cards; _fire_defeat_own_resource prefers a face-down one).
        if ctx.get("then_defeat_own_resource"):
            _fire_defeat_own_resource(s, ps.player_id)

        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id} using Smuggle" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else "")


# ── Play a card using Piloting as an ability (Wedge Antilles JTL_8) ────────────

def _piloting_eligible_from_hand(
    state: GameState, ps: PlayerState, cost_reduction: int = 0,
) -> list[tuple[CardInstance, CardInstance]]:
    """(pilot, host) pairs ``ps`` may play from hand using Piloting at
    ``cost_reduction`` off, affordable now.

    Enumerated as PAIRS so the offered actions and the gate never disagree: a
    Piloting card with no friendly Vehicle to ride is not playable this way."""
    hosts = _eligible_pilot_targets(state, ps)
    if not hosts:
        return []
    out: list[tuple[CardInstance, CardInstance]] = []
    for ci in ps.hand:
        base = _piloting_cost(state, ci, ps)
        if base is None:
            continue
        if not _affordable_with_credits(ps, max(0, base - cost_reduction), state):
            continue
        for host in hosts:
            out.append((ci, host))
    return out


def push_play_via_piloting(
    s: GameState, source_ci: CardInstance, *, cost_reduction: int = 0,
) -> None:
    """Push a 'play_via_piloting' decision: the source's controller plays a card
    from hand using Piloting at ``cost_reduction`` off (Wedge Antilles JTL_8).

    Mandatory if able and pushed only when ≥1 (pilot, host) pair exists — the
    activating ability is gated by ``CONTROLLER_CAN_PILOT`` so its Exhaust is never
    wasted; fizzles silently if somehow none remain."""
    owner_idx = s.player_index(source_ci.owner_id)
    owner_ps = s.player_by_id(source_ci.owner_id)
    if not _piloting_eligible_from_hand(s, owner_ps, cost_reduction):
        return
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="play_via_piloting",
        context={
            "source_id": source_ci.instance_id,
            "cost_reduction": int(cost_reduction),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="play_via_piloting"))


@dataclass
class PlayViaPiloting(Action):
    """Resolve a 'play_via_piloting' decision by playing the chosen hand card as a
    Pilot upgrade on the chosen friendly Vehicle at the stored discount.

    Mirrors ``PilotPlay``'s core (pay the reduced Piloting cost → ``_attach_pilot``
    → fire CardPlayed) but pops the decision first and does NOT hand the turn over
    itself (the after-index stored on the decision governs)."""
    instance_id: str
    vehicle_target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_via_piloting"):
            raise IllegalActionError("No play_via_piloting decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(top.deciding_player_id)
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        after_idx = top.after_resolve_player_index

        if not any(
            p.instance_id == self.instance_id
            and h.instance_id == self.vehicle_target_id
            for p, h in _piloting_eligible_from_hand(s, ps, cost_reduction)
        ):
            raise IllegalActionError(
                f"Cannot play {self.instance_id} using Piloting right now")

        ci = next(c for c in ps.hand if c.instance_id == self.instance_id)
        ps.hand.remove(ci)
        cost = max(0, _piloting_cost(s, ci, ps) - cost_reduction)
        # Consume any pending Piloting-aware discount the cost already reflects.
        _disc_idx = _piloting_discount_entry(s, ci, ps)
        if _disc_idx is not None:
            del s.game_memory.pending_play_discounts[_disc_idx]
        _pay_play_cost(s, ps, cost)

        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)

        card_played_evt = CardPlayed(
            player_id=ps.player_id, instance_id=ci.instance_id,
            card_name=ci.card_def.display_name, cost_paid=cost)
        s.event_log.append(card_played_evt)

        # Pop before attaching so the pilot's own triggers land on a clean stack
        # (the "pop, then act" gotcha).
        s.pending_decisions.pop()
        _attach_pilot(s, ps, ci, self.vehicle_target_id)

        get_bus().fire(s, card_played_evt)
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)

        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id} using Piloting on {self.vehicle_target_id}"


def _play_named_free_from_hand_or_resources(
    s: GameState, source_ci: CardInstance, player_id: str, card_name: str,
) -> None:
    """"You may play a card named ``card_name`` from your hand or resources for
    free" (A Precarious Predicament LOF_222).

    A resource is a face-down card the row treats as fungible, so a copy sitting
    there is returned to hand first (the K-2SO SOR_145 fungible-resource
    convention) and the whole thing then runs through the ONE free-play seam,
    ``push_play_from_hand``, whitelisted to the copies by instance id."""
    ps = s.player_by_id(player_id)
    ids = [c.instance_id for c in ps.hand
           if getattr(c.card_def, "name", None) == card_name]
    if not ids:
        from swu.engine.state import Zone
        moved = next((r for r in ps.resources
                      if getattr(r.card_def, "name", None) == card_name), None)
        if moved is None:
            return
        ps.resources.remove(moved)
        moved.zone = Zone.HAND
        moved.face_down = False
        moved.exhausted = False
        ps.hand.append(moved)
        ids = [moved.instance_id]
    # It's Worse LOF_264 is an EVENT, so the free play routes through the event
    # sibling of push_play_from_hand (which only ever plays units).
    push_play_event_from_hand(s, source_ci, free=True,
                              eligible_ids=frozenset(ids))


def push_say_no(
    s: GameState, source_ci: CardInstance, target_id: Optional[str],
    *,
    damage: int = 0,
    draw_on_refuse: int = 0,
    effect: str = "damage",
    refuse_play_named: Optional[str] = None,
    pay_to_refuse: int = 0,
    revealed_card: Optional[dict] = None,
    heal_amount: int = 0,
    then_experience: int = 0,
) -> None:
    """Push a 'say_no' decision: the controller of ``target_id`` may say "no" to
    an incoming effect ("Deal N damage to an enemy unit unless its controller
    says 'no.' If they do, draw M cards" — I Am Your Father, SOR_233).

    ``source_ci``'s controller has already chosen ``target_id`` (an enemy unit)
    via the CustomEffect.target seam.  This helper hands the decision to that
    unit's controller (the opponent):
      - AllowEffect → deal ``damage`` to the target unit;
      - SayNo       → no damage, and ``source_ci``'s controller draws
                      ``draw_on_refuse`` cards.

    The decision restores control to ``source_ci``'s controller so the buried
    resolve_effects decision can auto-finish and hand off the turn.  Fizzles
    cleanly (no decision pushed) when ``target_id`` is None or no longer in play.
    """
    controller_id = source_ci.owner_id
    if effect == "opponent_heal_base":
        # "Each opponent MAY heal N damage from their base.  For each player that
        # does, give M Experience tokens to a unit" (Lom Pyke TS26_51) — the OPT-IN
        # flavour of the seat shift: the decider's own base is the beneficiary, so
        # AllowEffect is the "may" and SayNo is the decline.  Both branches are real
        # (a damaged base is worth more than the tokens it concedes), so it does not
        # collapse to an optimal default.  Targetless, like ``draw_top_card``.
        decider_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    elif effect == "draw_top_card":
        # A TARGETLESS say_no (Cikatro Vizago SEC_218: "Reveal the top card of your
        # deck.  An opponent may pay 1 resource.  If they don't, draw that card") —
        # there is no unit to point at, so the decider is simply the opponent.
        # ``revealed_card`` carries the revealed card's card_id + name ONLY (never
        # its instance_id — the look_hand hidden-info shape), so the decider can see
        # what they are paying to deny without leaking a deck instance_id.
        decider_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    else:
        if target_id is None:
            return
        result = s.find_instance(target_id)
        if result is None:
            return
        target_ps, _ = result
        decider_id = target_ps.player_id
    after_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="say_no",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "target_id": target_id,
            "damage": damage,
            "draw": draw_on_refuse,
            "effect": effect,
            "refuse_play_named": refuse_play_named,
            "pay_to_refuse": int(pay_to_refuse),
            "revealed_card": dict(revealed_card) if revealed_card else None,
            "heal_amount": int(heal_amount),
            "then_experience": int(then_experience),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id,
        kind="say_no",
    ))


# ── New primitive: move-an-upgrade (Survivors' Gauntlet SHD_64) ───────────────

@dataclass
class DeclinePlayFromHand(Action):
    """Stop a "Play UP TO N units …" loop (Dathomiri Magicks ASH_104).

    The ordinary ``play_from_hand`` decision is mandatory-if-able — it is pushed
    only when something IS playable — so this is offered only while its context
    carries ``up_to``."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_from_hand"):
            raise IllegalActionError("No play_from_hand decision pending")
        if not state.pending_decisions[-1].context.get("up_to"):
            raise IllegalActionError("This play_from_hand decision is mandatory")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_from_hand",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to play a card"


# ── Player-directed damage distribution push helpers ──────────────────────────

def _take_from_hand_or_discard(ps: PlayerState, instance_id: str) -> CardInstance:
    """Remove and return a card from ``ps``'s hand or discard pile (Gideon's
    Light Cruiser SHD_242: "from your hand or discard pile")."""
    for zone in (ps.hand, ps.discard):
        for i, ci in enumerate(zone):
            if ci.instance_id == instance_id:
                zone.pop(i)
                return ci
    raise IllegalActionError(f"Card {instance_id} not found in hand or discard")

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "play_from_hand":                _play_from_hand_actions,
    "play_event_from_hand":          _play_event_from_hand_actions,
    "play_via_smuggle":              _play_via_smuggle_actions,
    "play_via_piloting":             _play_via_piloting_actions,
    "opponent_ready":                _opponent_ready_actions,
    "say_no":                        _say_no_actions,
    "play_captured_card":            _play_captured_actions,
    "play_resource_units":           _play_resource_units_actions,
    "look_hand":                     _look_hand_actions,
})
