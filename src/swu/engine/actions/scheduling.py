"""Obligations and options the engine has to remember and present later.

Every other decision family answers a question the current effect is asking. These are
the ones where the question outlives the effect that raised it, which is a different
problem: something must be recorded on the state now and offered to a player at a moment
that has not arrived yet.

* **delayed effects** — ``push_eye_of_aldhani_schedule`` and
  ``push_defeat_own_resource_schedule`` record an effect that fires at the start of a
  future action phase rather than now.
* **recurring upkeep** — ``regroup_upkeep`` re-asks every round for as long as the unit
  is in play: pay, or return it.
* **optional riders** — ``use_force`` and the several ``may_discard_else_*`` shapes,
  where a player may pay something to change an outcome, and declining has its own
  defined consequence rather than simply being a no-op.
* **rules obligations rather than abilities** — ``resolve_unique``, where controlling two
  copies of a unique card forces you to defeat one. No card text asks for this; the rules
  do, which is why it is pushed by the engine and not by an ability.
* **trigger options** — ``trigger_option``, where an optional trigger must be offered
  before it is allowed to lapse.
* **naming a card** — stripping abilities from an opponent's copies of a named card,
  which needs ``_opponent_hand_names`` and so is the one place here that reads hidden
  information deliberately.

The delayed effects are why ``GameState`` carries ``scheduled_action_phase_effects``
(``state.py``) at all, and why it has to survive a round trip: it is written into the
save at ``to_dict`` and read back at ``from_dict``, because a game saved mid-round has to
remember what is still owed. An obligation the state cannot serialise is an obligation
that silently vanishes on reload, which is exactly the class of bug the invariant
oracle's round-trip check exists to catch.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from swu.cards.models import Leader
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
from swu.engine.actions.costs import (
    _exhaust_resources,
)
from swu.engine.actions.zones import (
    _create_token_units, _draw_cards,
)
from swu.engine.actions.shared import (
    _find_in_arenas_any, spend_force_token,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard,
)


# ── Recurring regroup upkeep: "pay 1 or return to hand" (Millennium Falcon

@dataclass
class PayRegroupUpkeep(Action):
    """Resolve a 'regroup_upkeep' decision by paying 1 resource to keep the unit
    in play.  Offered only when the controller has ≥1 resource.  Paying leaves one
    resource exhausted going into the next action phase (set exhausted + the
    existing ``cannot_ready_this_round`` flag, which ``_end_regroup`` honours then
    clears)."""

    source_id: str = ""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "regroup_upkeep"):
            raise IllegalActionError("No regroup_upkeep decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        if not ps.resources:
            raise IllegalActionError("No resource to pay the regroup upkeep")
        res = ps.resources[-1]
        res.exhausted = True
        res.cannot_ready_this_round = True
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="regroup_upkeep",
            choice="paid 1 resource",
        ))
        s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Pay 1 resource"


@dataclass
class ReturnRegroupUpkeepUnit(Action):
    """Resolve a 'regroup_upkeep' decision by returning the unit to its owner's
    hand (always available — the fallback when you won't/can't pay)."""

    source_id: str = ""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "regroup_upkeep"):
            raise IllegalActionError("No regroup_upkeep decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(s, top.context["source_id"])
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="regroup_upkeep",
            choice="returned to hand",
        ))
        s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Return to owner's hand"


def _regroup_upkeep_actions(state: GameState, top) -> list[Action]:
    ctx = top.context
    ps = state.player_by_id(ctx["controller_id"])
    acts: list[Action] = []
    if ps.resources:
        acts.append(PayRegroupUpkeep(ctx["source_id"]))
    acts.append(ReturnRegroupUpkeepUnit(ctx["source_id"]))
    return acts


def push_regroup_upkeep(s: GameState, source_ci: CardInstance, *, amount: int = 1) -> None:
    """Push a 'regroup_upkeep' decision for ``source_ci`` (Millennium Falcon
    SOR_193): its controller must either pay ``amount`` resources to keep it in
    play or return it to its owner's hand.  Addressed to the source's controller,
    restoring control to the initiative holder afterward so the regroup resource
    step continues.  No-op if the source has left play.

    Timing note: the ability text says "when you ready cards during the regroup
    phase", but this fires at regroup START (the PhaseStartTrigger site).  Paying
    marks one resource with ``cannot_ready_this_round`` + ``exhausted``, so it is
    down for the next action phase either way — the mechanical −1 cost is faithful
    regardless of the exact firing instant within regroup."""
    if s.find_instance(source_ci.instance_id) is None:
        return
    controller_id = source_ci.owner_id
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="regroup_upkeep",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "amount": int(amount),
        },
        after_resolve_player_index=s.initiative_holder,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(controller_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="regroup_upkeep",
    ))


# ── Delayed action-phase-start scheduler + per-enemy pay-or-exhaust ────────────

def push_eye_of_aldhani_schedule(s: GameState, source_ci: CardInstance) -> None:
    """Schedule the Eye of Aldhani pay-or-exhaust effect for the START of the next
    action phase (the effect resolves later, when the source is long gone to
    discard — so the caster's id is recorded, not the instance)."""
    s.scheduled_action_phase_effects.append(
        {"kind": "eye_of_aldhani", "controller_id": source_ci.owner_id})


def push_pay_or_exhaust(
    s: GameState, target_id: str, pay_amount: int = 1,
) -> None:
    """Push a single-unit ``pay_or_exhaust`` decision addressed to the target unit's
    controller: "Exhaust a unit unless its controller pays N resources" (Look the
    Other Way SHD_227).  The target's controller decides — pay ``pay_amount`` to keep
    the unit ready, or let it be exhausted.  Reuses the Eye of Aldhani SEC_73
    machinery (PayToAvoidExhaust/AcceptExhaust); the ``pay_amount`` context field
    generalises its formerly-fixed 1-resource cost.  No push for a gone/already-
    exhausted target (nothing to protect)."""
    found = s.find_instance(target_id)
    if found is None:
        return
    holder_ps, target_ci = found
    if target_ci.exhausted:
        return
    decider_id = holder_ps.player_id
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="pay_or_exhaust",
        context={
            "controller_id": decider_id,
            "pending_ids": [target_id],
            "pay_amount": int(pay_amount),
        },
        after_resolve_player_index=s.active_player_index,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id,
        kind="pay_or_exhaust",
    ))


# ── Delayed "defeat a resource you control at the next action phase" ──────────

def push_defeat_own_resource_schedule(s: GameState, source_ci: CardInstance) -> None:
    """Schedule "defeat a resource you control" for the START of the next action
    phase (the source's controller is recorded; the source may be long gone)."""
    s.scheduled_action_phase_effects.append(
        {"kind": "defeat_own_resource", "controller_id": source_ci.owner_id})


def _pay_or_exhaust_current(state: GameState, ctx: dict) -> str:
    """The unit id currently being decided (the head of the pending list)."""
    return ctx["pending_ids"][0]


def _pay_or_exhaust_actions(state: GameState, top) -> list[Action]:
    ctx = top.context
    head = _pay_or_exhaust_current(state, ctx)
    ps = state.player_by_id(ctx["controller_id"])
    acts: list[Action] = []
    # Pay is offered only when the deciding player has a ready resource AND the unit
    # is still present and ready (paying to protect a gone/already-exhausted unit is
    # pointless — the double-schedule staleness case).
    found = state.find_instance(head)
    ready_unit = found is not None and not found[1].exhausted
    pay_amount = int(ctx.get("pay_amount", 1) or 1)
    if ready_unit and sum(1 for r in ps.resources if not r.exhausted) >= pay_amount:
        acts.append(PayToAvoidExhaust(head))
    # "Or exhaust that unit" is always available — on a present ready unit it
    # exhausts it; on a gone/already-exhausted unit it is a harmless no-op advance,
    # so the decision's action set is never empty.
    acts.append(AcceptExhaust(head))
    return acts


def _advance_pay_or_exhaust(s: GameState, top, choice: str) -> GameState:
    """Remove the just-decided head unit and either advance to the next unit or,
    when none remain, pop the decision and restore the action-phase active player."""
    ctx = top.context
    if ctx["pending_ids"]:
        ctx["pending_ids"].pop(0)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="pay_or_exhaust",
        choice=choice,
    ))
    if not ctx["pending_ids"]:
        s.pending_decisions.pop()
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class PayToAvoidExhaust(Action):
    """Resolve one enemy unit of an Eye of Aldhani SEC_73 pay-or-exhaust decision by
    paying 1 resource — the unit stays as it is."""

    unit_id: str = ""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_or_exhaust"):
            raise IllegalActionError("No pay_or_exhaust decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ps = s.player_by_id(top.context["controller_id"])
        pay_amount = int(top.context.get("pay_amount", 1) or 1)
        _exhaust_resources(ps, pay_amount)   # pay N resources
        return _advance_pay_or_exhaust(
            s, top, choice=f"paid {pay_amount} resource(s)")

    def describe(self) -> str:
        return "Pay resources to avoid exhaust"


@dataclass
class AcceptExhaust(Action):
    """Resolve one enemy unit of an Eye of Aldhani SEC_73 pay-or-exhaust decision by
    letting it be exhausted (the fallback when you won't/can't pay)."""

    unit_id: str = ""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_or_exhaust"):
            raise IllegalActionError("No pay_or_exhaust decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        found = s.find_instance(self.unit_id)
        if found is not None:
            found[1].exhausted = True
        return _advance_pay_or_exhaust(s, top, choice="exhausted the unit")

    def describe(self) -> str:
        return "Exhaust the unit"


# ── Opponent may discard a random card, else the controller gets an effect

@dataclass
class DiscardRandomCard(Action):
    """Resolve a 'may_discard' decision by discarding a random card from the
    deciding player's hand (Political Pressure TWI_222) — this prevents the
    else-effect, so no tokens are created."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "may_discard"):
            raise IllegalActionError("No may_discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        ps = s.player_by_id(ctx["opponent_id"])
        if not ps.hand:
            raise IllegalActionError("No card to discard")
        rng = s.make_rng()
        idx = rng.randrange(len(ps.hand))
        s.rng_state = rng.getstate()
        card = ps.hand.pop(idx)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        choice = "discarded a random card"
        # THEN-arm (Kouhun Assassination TS26_33): unlike every other may_discard
        # card the payoff sits on the ACCEPT branch — "If they DO, give a
        # non-Vehicle unit -8/-8 for this phase" — landing on the unit the source's
        # controller pinned into the decision before it was pushed.
        deb = ctx.get("then_debuff")
        if deb and ctx.get("target_id"):
            if s.find_instance(ctx["target_id"]) is not None:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx.get("source_id"),
                    target_instance_id=ctx["target_id"],
                    kind="stats",
                    value={"power": int(deb.get("power", 0)),
                           "hp": int(deb.get("hp", 0))},
                    duration=str(deb.get("duration", "this_phase")),
                ))
                choice = (f"discarded a random card — the chosen unit takes "
                          f"{deb.get('power', 0)}/{deb.get('hp', 0)}")
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="may_discard",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Discard a random card"


@dataclass
class DeclineDiscard(Action):
    """Resolve a 'may_discard' decision by declining to discard (Political Pressure
    TWI_222) — the source's controller gets the else-effect (creates N token
    units)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "may_discard"):
            raise IllegalActionError("No may_discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        if ctx.get("else_effect") == "damage":
            # Syril Karn SEC_133: didn't discard → take the damage on the chosen unit.
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, ctx["target_id"], int(ctx["amount"]))
            choice = f"declined — took {ctx['amount']} damage"
        elif ctx.get("then_debuff"):
            # TS26_33's payoff rides the ACCEPT arm, so declining simply does
            # nothing — there is no else-effect at all.
            choice = "declined"
        else:
            controller_ps = s.player_by_id(ctx["controller_id"])
            created = _create_token_units(
                s, controller_ps, ctx["token_name"], int(ctx["token_count"]))
            choice = (f"declined — {ctx['controller_id']} created "
                      f"{len(created)} token(s)")
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="may_discard",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Don't discard"


# ── Phase 3 decision-resolving actions ───────────────────────────────────────

@dataclass
class AcceptTrigger(Action):
    """Accept an optional triggered ability (trigger_option decision)."""
    source_id: str
    card_name: str = field(default="", compare=False)

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "trigger_option":
            raise IllegalActionError("No pending trigger_option decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="trigger_option",
            choice="accept",
        ))
        # A "use that ability again" re-use (resolver._schedule_ability_redo) charges
        # its cost HERE, on accept, not when the option was offered — declining a
        # "you may" is not a use.  Grand Admiral Thrawn JTL_2: his undeployed side
        # exhausts him ("You may exhaust this leader.  If you do, …"), his deployed
        # side burns the round's single use.  The redo is only ever offered while
        # the cost is payable, so this always succeeds.
        redo_src_id = ctx.get("redo_source_id")
        if redo_src_id:
            redo_found = s.find_instance(redo_src_id)
            if redo_found is not None:
                if ctx.get("redo_cost_exhaust"):
                    redo_found[1].exhausted = True
                # Enfys Nest LAW_14 undeployed also pays resources ("You may pay 2
                # resources AND exhaust this leader"); the redo is only offered
                # while both halves are payable, so this always succeeds.
                pay = int(ctx.get("redo_cost_resources") or 0)
                if pay:
                    _exhaust_resources(s.player_by_id(redo_found[0].player_id), pay)
                if ctx.get("redo_once_per_round"):
                    s.game_memory.when_defeated_redo_used_this_round.add(redo_src_id)
        # Push resolve_effects decision for the accepted trigger
        from swu.abilities.registry import get_abilities
        specs = get_abilities(ctx["set_code"], ctx["card_number"])
        ability_idx = ctx["ability_idx"]
        if ability_idx < len(specs):
            after_idx = ctx.get("after_all_player_idx", top.after_resolve_player_index)
            resolve_dec = PendingDecision(
                deciding_player_id=top.deciding_player_id,
                kind="resolve_effects",
                context={
                    "set_code": ctx["set_code"],
                    "card_number": ctx["card_number"],
                    "ability_idx": ability_idx,
                    "source_id": ctx["source_id"],
                    "effect_idx": 0,
                    "resolved_targets": {},
                    "event_ctx": ctx.get("event_ctx", {}),
                    "after_all_player_idx": after_idx,
                },
                after_resolve_player_index=after_idx,
            )
            s.pending_decisions.append(resolve_dec)
            s.event_log.append(DecisionPushed(
                deciding_player_id=top.deciding_player_id,
                kind="resolve_effects",
            ))
            # Accepting an optional ability is a "use" of it — arm any redo
            # (Aethersprite LOF_197 / Thrawn JTL_2), inserting the optional re-use
            # just below this resolve_effects decision so it resolves after the
            # ability (and anything it spawns) completes.  Declining
            # (DeclineTrigger) is not a use and never reaches here.
            src = s.find_instance(ctx["source_id"])
            if src is not None:
                from swu.abilities.resolver import _schedule_ability_redo
                s = _schedule_ability_redo(
                    s, src[1], ctx["set_code"], ctx["card_number"], ability_idx,
                    ctx.get("event_ctx", {}), after_idx,
                    len(s.pending_decisions) - 1)
        else:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Use {self.card_name}" if self.card_name else "Use triggered ability"


@dataclass
class DeclineTrigger(Action):
    """Decline an optional triggered ability."""
    source_id: str
    card_name: str = field(default="", compare=False)

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "trigger_option":
            raise IllegalActionError("No pending trigger_option decision")
        top = state.pending_decisions[-1]
        if top.context.get("source_id") != self.source_id:
            raise IllegalActionError("DeclineTrigger: wrong source_id")
        s = copy.deepcopy(state)
        top_d = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top_d.deciding_player_id,
            kind="trigger_option",
            choice="decline",
        ))
        s.active_player_index = top_d.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Decline {self.card_name}" if self.card_name else "Decline triggered ability"


# ── apply convenience wrapper ─────────────────────────────────────────────────

def _resolve_unique_candidates(state: GameState, ctx: dict) -> list[str]:
    """The still-in-play duplicate instance ids the controller may keep."""
    return [tid for tid in ctx["candidate_ids"] if state.find_instance(tid) is not None]


# ── Phase 3: trigger_option ───────────────────────────────────────────

def _trigger_option_actions(state: GameState, top: PendingDecision) -> list[Action]:
    source_id = top.context.get("source_id", "")
    found = state.find_instance(source_id)
    card_name = found[1].card_def.display_name if found else ""
    return [
        AcceptTrigger(source_id, card_name),
        DeclineTrigger(source_id, card_name),
    ]


# ── Name a card; opponent-owned non-leader copies lose all abilities while the

#    namer is in play (Galen Erso P25_31 WhenPlayed) ─────────────────────────
def _name_a_card_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [NameCard(n) for n in top.context["names"]]


# ── Unique Rule: keep one duplicate copy, defeat the rest (state-based) ──────

def _resolve_unique_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [KeepUniqueCopy(t)
            for t in _resolve_unique_candidates(state, top.context)]


# ── Opponent may discard a random card, else create tokens (Political

#    Pressure TWI_222) ──────────────────────────────────────────────────────
def _may_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    if state.player_by_id(top.context["opponent_id"]).hand:
        acts.append(DiscardRandomCard())
    acts.append(DeclineDiscard())
    return acts


# ── Name a card; each non-leader card an opponent owns with that name loses all

def _name_a_card_names(state: GameState, controller_id: str) -> list[str]:
    """Distinct non-leader card names among the OPPONENT of ``controller_id``'s cards
    in public zones (ground/space arenas + attached upgrades + discard + base)."""
    opponent = next(p for p in state.players if p.player_id != controller_id)
    names: set[str] = set()
    for pool in (opponent.ground_arena, opponent.space_arena,
                 opponent.discard, opponent.base_zone):
        for ci in pool:
            cd = ci.card_def
            if not isinstance(cd, Leader) and getattr(cd, "name", None):
                names.add(cd.name)
            for u in getattr(ci, "attached_upgrades", ()):  # a named upgrade counts too
                ucd = u.card_def
                if not isinstance(ucd, Leader) and getattr(ucd, "name", None):
                    names.add(ucd.name)
    return sorted(names)


def _opponent_hand_names(state: GameState, controller_id: str) -> list[str]:
    """Distinct non-leader card names in the OPPONENT of ``controller_id``'s HAND —
    the cards the naming player just looked at (Qi'ra SHD_202 "Look at an opponent's
    hand, then name a card").  A private option list for the naming player."""
    opponent = next(p for p in state.players if p.player_id != controller_id)
    names: set[str] = set()
    for ci in opponent.hand:
        cd = ci.card_def
        if not isinstance(cd, Leader) and getattr(cd, "name", None):
            names.add(cd.name)
    return sorted(names)


def _apply_name_a_card_payoff(s: GameState, source_ci: CardInstance,
                              named: str, payoff: str) -> None:
    """A "then …" rider on a naming, encoded as a string key + args (the
    use_force / disclose dispatch shape).

    ``"mill_defender_match_buff:N"`` — discard the top card of the DEFENDING
    player's deck; if its name is the named one, the source gets +N/+0 for this
    attack (Zuckuss LOF_204).  The defending player is the source's opponent (this
    resolves from an On Attack, and in two-player they are the same seat).

    ``"experience_per_hand_copy"`` / ``"token_per_hand_copy:<TokenName>"`` — "an
    opponent reveals their hand.  For each copy of the named card in their hand,
    <give an Experience token to this unit / create a token>" (Inspector's Shuttle
    SEC_260, Stolen Starpath Unit SEC_210).  The count is read off the opponent's
    hand at resolution, i.e. after the naming, which is the printed order."""
    kind, _, raw = payoff.partition(":")
    if kind == "forbid_play_this_phase":
        # "Cards with that name can't be played this phase" (Transmission Jamming
        # LAW_243) — a phase-scoped, any-player ban read at the play-legality seam.
        s.game_memory.forbidden_card_names_this_phase.add(named)
        return
    if kind in ("experience_per_hand_copy", "token_per_hand_copy"):
        opponent = next(
            (p for p in s.players if p.player_id != source_ci.owner_id), None)
        if opponent is None:
            return
        copies = sum(1 for ci in opponent.hand
                     if getattr(ci.card_def, "name", None) == named)
        if copies <= 0:
            return
        if kind == "experience_per_hand_copy":
            from swu.engine import tokens
            ps = s.player_by_id(source_ci.owner_id)
            for _ in range(copies):
                tokens.attach_token(s, ps, source_ci, "Experience")
        else:
            _create_token_units(s, s.player_by_id(source_ci.owner_id),
                                raw or "Spy", copies)
        return
    if kind != "mill_defender_match_buff":
        return
    from swu.engine.state import Zone, Modifier
    defender = next((p for p in s.players if p.player_id != source_ci.owner_id), None)
    if defender is None or not defender.deck:
        return
    milled = defender.deck.pop(0)
    milled.zone = Zone.DISCARD
    milled.face_down = False
    defender.discard.append(milled)
    note_hand_or_deck_discard(s, milled, from_deck=True)
    if getattr(milled.card_def, "name", None) != named:
        return
    s.modifiers.append(Modifier(
        modifier_id=s.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=source_ci.instance_id,
        kind="stats",
        value={"power": int(raw), "hp": 0},
        duration="this_attack",
    ))


def push_name_a_card(s: GameState, source_ci: CardInstance,
                     from_hand: bool = False, *,
                     names: Optional[list[str]] = None,
                     then_payoff: Optional[str] = None) -> None:
    """Push a 'name_a_card' decision (Galen Erso P25_31 WhenPlayed).  The source's
    controller names one of the opponent's non-leader card names; the choice is
    recorded on the source's ``named_card`` field.  Pushed only when ≥1 such name
    exists (with none the naming fizzles).  ``from_hand`` names from the opponent's
    HAND instead of their public zones — "look at an opponent's hand, then name a
    card" (Qi'ra SHD_202); the optimal-play collapse to a card actually present."""
    controller_id = source_ci.owner_id
    if names is None:
        names = (_opponent_hand_names(s, controller_id) if from_hand
                 else _name_a_card_names(s, controller_id))
    if not names:
        return
    ctx = {"source_id": source_ci.instance_id, "names": names,
           "then_payoff": then_payoff}
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="name_a_card",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(controller_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="name_a_card",
    ))


@dataclass
class NameCard(Action):
    """The source's controller names a card (Galen Erso P25_31 WhenPlayed); records
    the name on the source so every opponent-owned non-leader copy of that card loses
    all abilities while the source is in play."""
    name: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "name_a_card"):
            raise IllegalActionError("No name-a-card decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if self.name not in top.context["names"]:
            raise IllegalActionError(f"{self.name!r} is not a legal card to name")
        source = _find_in_arenas_any(s, top.context["source_id"])
        s.pending_decisions.pop()
        if source is not None:
            source.named_card = self.name
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="name_a_card",
            choice=f"named {self.name}",
        ))
        # "…then discard the top card of the defending player's deck.  If a card
        # with that name is discarded, this unit gets +N/+0 for this attack"
        # (Zuckuss LOF_204) — settled after the pop, on a clean stack.
        payoff = top.context.get("then_payoff")
        if payoff:
            # An EVENT source is already in its owner's discard by the time its own
            # ability resolves, so the arena lookup above misses it — fall back to
            # the whole-state one for the payoff (Transmission Jamming LAW_243).
            payoff_source = source
            if payoff_source is None:
                res = s.find_instance(top.context["source_id"])
                payoff_source = res[1] if res else None
            if payoff_source is not None:
                _apply_name_a_card_payoff(s, payoff_source, self.name, str(payoff))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Name card {self.name}"


# ── Unique Rule: keep one of the duplicate copies, defeat the rest

@dataclass
class KeepUniqueCopy(Action):
    """Resolve a duplicate under the Unique Rule: the controller keeps this copy
    and every other copy with the same title + subtitle they control is defeated."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resolve_unique"):
            raise IllegalActionError("No resolve_unique decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in _resolve_unique_candidates(state, ctx):
            raise IllegalActionError(
                f"{self.instance_id} is not a duplicate copy to keep")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        losers = [tid for tid in _resolve_unique_candidates(s, ctx)
                  if tid != self.instance_id]
        # Pop first, THEN defeat, so a defeated copy's WhenDefeated trigger lands
        # on a clean stack (the shared "pop, then defeat" gotcha).
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="resolve_unique",
            choice=f"keep {self.instance_id}, defeat {losers}",
        ))
        from swu.abilities.resolver import _apply_defeat_unit
        for tid in losers:
            _apply_defeat_unit(s, tid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Keep unique copy {self.instance_id}"


# ── Opponent may discard a random card, else create token units (Political

def push_may_discard_else_tokens(
    s: GameState, source_ci: CardInstance, *,
    token_name: str, token_count: int,
) -> None:
    """Push a 'may_discard' decision (Political Pressure TWI_222): an opponent may
    discard a random card from their hand; if they don't, the source's controller
    creates ``token_count`` ``token_name`` token units.

    Handed to the OPPONENT (the say_no SOR_233 deciding-player-shift precedent).
    When the opponent's hand is empty they cannot discard ("if they don't"), so the
    tokens are created inline with no decision pushed."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    opp = s.player_by_id(opponent_id)
    if not opp.hand:
        _create_token_units(
            s, s.player_by_id(controller_id), token_name, int(token_count))
        return
    dec = PendingDecision(
        deciding_player_id=opponent_id,
        kind="may_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opponent_id,
            "token_name": token_name,
            "token_count": int(token_count),
        },
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(opponent_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=opponent_id,
        kind="may_discard",
    ))


def push_may_discard_for_debuff(
    s: GameState, source_ci: CardInstance, target_id: str,
    *, power: int = -8, hp: int = -8, duration: str = "this_phase",
) -> None:
    """Push a 'may_discard' decision whose payoff sits on the **accept** arm: "An
    opponent (of your choice) may discard a card from their hand.  **If they do**,
    give a non-Vehicle unit -8/-8 for this phase" (Kouhun Assassination TS26_33).

    Handed to the opponent (the say_no SOR_233 deciding-player shift).  The unit is
    chosen by the source's CONTROLLER before the push and pinned into the context, so
    the controller is prompted once and the debuff cannot drift.  An empty hand means
    they cannot discard, so nothing is pushed and nothing happens.

    ⚠️ DOCUMENTED ODDITY: every sibling in the engine puts the penalty on the DECLINE
    arm, which makes the choice real; here the payoff harms the decider, so a rational
    opponent always declines.  Implemented as printed — flipping the clause would be a
    rules judgement, not an encoding one."""
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    opp = s.players[1 - owner_idx]
    if not opp.hand:
        return
    dec = PendingDecision(
        deciding_player_id=opp.player_id,
        kind="may_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opp.player_id,
            "target_id": target_id,
            "then_debuff": {"power": int(power), "hp": int(hp),
                            "duration": str(duration)},
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(opp.player_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=opp.player_id, kind="may_discard"))


def push_may_discard_else_damage(
    s: GameState, source_ci: Optional[CardInstance], target_id: Optional[str],
    amount: int,
) -> None:
    """Push a 'may_discard' decision whose else-effect deals ``amount`` damage to
    ``target_id`` (Syril Karn SEC_133): the target's controller may discard a card
    (the established first-card/random discard simplification) to prevent the
    damage; if they don't, it is dealt.

    Handed to the target's controller (the say_no SOR_233 deciding-player shift).
    When that player's hand is empty they cannot discard ("unless … discards"), so
    the damage lands inline with no decision pushed.  Fizzles cleanly with no target
    or non-positive amount."""
    if target_id is None or int(amount) <= 0:
        return
    result = s.find_instance(target_id)
    if result is None:
        return
    target_ps, _ = result
    decider_id = target_ps.player_id
    controller_id = (source_ci.owner_id if source_ci is not None
                     else next(p.player_id for p in s.players
                               if p.player_id != decider_id))
    if not s.player_by_id(decider_id).hand:
        from swu.abilities.resolver import _apply_deal_damage
        _apply_deal_damage(s, target_id, int(amount))
        return
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="may_discard",
        context={
            "source_id": source_ci.instance_id if source_ci is not None else None,
            "controller_id": controller_id,
            "opponent_id": decider_id,   # whose hand is at risk / who decides
            "else_effect": "damage",
            "target_id": target_id,
            "amount": int(amount),
        },
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id,
        kind="may_discard",
    ))


# ── New primitive: "you may use the Force" optional rider (force-token,

def _use_force_enemy_exhaust_targets(state: GameState, ctx: dict) -> list[CardInstance]:
    """Ready enemy units the controller may exhaust (the "exhaust an enemy unit"
    payoff — exhausting an already-exhausted unit does nothing, so only ready ones
    are offered)."""
    opp = state.players[1 - state.player_index(ctx["controller_id"])]
    return [u for u in opp.ground_arena + opp.space_arena if not u.exhausted]


def _apply_use_force_decline_penalty(
    s: GameState, controller_id: str, penalty: str,
) -> None:
    """Apply the "if you don't" penalty of a use_force clause (Savage Opress
    LOF_137: "If you don't, deal 9 damage to your base").  Encoded as
    ``"self_base_damage:N"`` — deal N to the controller's own base."""
    kind, _, raw = penalty.partition(":")
    if kind == "draw":
        # The "if you do not" clause is not always a downside: "If you do not, draw
        # a card" (Do or Do Not LOF_175).  Same string-encoded dispatch.
        _draw_cards(s, s.player_by_id(controller_id), int(raw))
        return
    if kind == "self_base_damage":
        ps = s.player_by_id(controller_id)
        base = ps.base_instance
        if base is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, base.instance_id, int(raw))


def push_use_force(
    s: GameState, source_ci: CardInstance, *,
    payoff: str, payoff_player_id: Optional[str] = None,
    allow_exhaust_friendly: bool = False,
    decline_penalty: Optional[str] = None,
) -> None:
    """Push a 'use_force' decision (force-token, qui-gon-jinn:06).

    ``payoff`` — what happens "if you do":
      * ``"discard_random"`` — ``payoff_player_id`` discards a random hand card
        (The Will of the Force LOF_227).
      * ``"exhaust_enemy_draw"`` — draw a card, then exhaust an enemy unit if able
        (Impossible Escape LOF_218).
      * ``"none"`` — using the Force has no rider; it only *avoids* the decline
        penalty (Savage Opress LOF_137).
    ``allow_exhaust_friendly`` — also offer "exhaust a friendly unit" as an
    alternative cost to using the Force (Impossible Escape's "either … or …").
    ``decline_penalty`` — an "if you don't" downside applied when the player
    declines (or cannot pay): encoded like ``"self_base_damage:9"`` (Savage
    Opress LOF_137).  When set, the clause is no longer a free "you may" — even
    with no payable cost the penalty still lands (applied inline here when no
    decision is pushed).

    Only pushed when at least one cost is payable (a Force token, or a ready
    friendly unit when ``allow_exhaust_friendly``); otherwise nothing happens
    (the whole clause is "you may") — except the ``decline_penalty``, which is
    applied inline when there is no cost to offer."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    options: list[str] = []
    if getattr(ps, "has_force_token", False):
        options.append("force")
    if allow_exhaust_friendly and any(
            not u.exhausted for u in ps.ground_arena + ps.space_arena):
        options.append("exhaust_friendly")
    if not options:
        if decline_penalty:
            _apply_use_force_decline_penalty(s, controller_id, decline_penalty)
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="use_force",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "choose",
            "cost_options": options,
            "payoff": payoff,
            "payoff_player_id": payoff_player_id,
            "decline_penalty": decline_penalty,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(deciding_player_id=controller_id, kind="use_force"))


def _use_force_actions(state: GameState, top) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "payoff":
        return [ChooseUseForcePayoffTarget(u.instance_id)
                for u in _use_force_enemy_exhaust_targets(state, ctx)]
    acts: list[Action] = []
    ps = state.player_by_id(ctx["controller_id"])
    for opt in ctx.get("cost_options", []):
        if opt == "force":
            acts.append(UseForceOption("force"))
        elif opt == "exhaust_friendly":
            for u in ps.ground_arena + ps.space_arena:
                if not u.exhausted:
                    acts.append(UseForceOption("exhaust_friendly", u.instance_id))
    acts.append(DeclineUseForce(decline_penalty=ctx.get("decline_penalty")))
    return acts


def _pop_use_force(s: GameState, top, choice: str) -> GameState:
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id, kind="use_force", choice=choice))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _resolve_use_force_payoff(s: GameState, top) -> GameState:
    """Apply the rider after a cost was paid, advancing to the payoff stage when it
    needs a target, else popping the decision."""
    ctx = top.context
    payoff = ctx.get("payoff")
    if payoff == "discard_random":
        pid = ctx.get("payoff_player_id")
        if pid is not None:
            tp = s.player_by_id(pid)
            if tp.hand:
                rng = s.make_rng()
                idx = rng.randrange(len(tp.hand))
                s.rng_state = rng.getstate()
                card = tp.hand.pop(idx)
                card.zone = Zone.DISCARD
                tp.discard.append(card)
        return _pop_use_force(s, top, "used the Force")
    if payoff.startswith("draw:"):
        # "…If you do, draw N cards" (Do or Do Not LOF_175) — no target, so the
        # decision pops immediately.  The count rides in the payoff string.
        _draw_cards(s, s.player_by_id(ctx["controller_id"]),
                    int(payoff.split(":", 1)[1]))
        return _pop_use_force(s, top, "used the Force")
    if payoff == "opponents_discard":
        # "…If you do, each opponent discards a card from their hand" (Jedi In
        # Hiding LOF_159).  No target, so the decision pops immediately.
        # DEVIATION: the established first-card discard simplification (K-2SO
        # SOR_145) — the opponent loses a card, just not one of their choosing.
        for pl in s.players:
            if pl.player_id != ctx["controller_id"] and pl.hand:
                card = pl.hand.pop(0)
                card.zone = Zone.DISCARD
                pl.discard.append(card)
                note_hand_or_deck_discard(s, card)
        return _pop_use_force(s, top, "used the Force")
    if payoff == "exhaust_enemy_draw":
        ctrl = s.player_by_id(ctx["controller_id"])
        _draw_cards(s, ctrl, 1)
        if not s.is_terminal() and _use_force_enemy_exhaust_targets(s, ctx):
            ctx["stage"] = "payoff"
            return s
        return _pop_use_force(s, top, "used the Force")
    return _pop_use_force(s, top, "used the Force")


@dataclass
class UseForceOption(Action):
    """Pay a cost in the 'use_force' decision ("force" = lose your Force token, or
    "exhaust_friendly" = exhaust the chosen friendly unit), then resolve the rider."""
    option: str
    target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "use_force"):
            raise IllegalActionError("No use_force decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose":
            raise IllegalActionError("use_force decision is past the choose stage")
        if self.option not in ctx.get("cost_options", []):
            raise IllegalActionError(f"Cost option {self.option!r} not available")
        ps = s.player_by_id(ctx["controller_id"])
        if self.option == "force":
            if not spend_force_token(s, ps):
                raise IllegalActionError("No Force token to spend")
        elif self.option == "exhaust_friendly":
            unit = next((u for u in ps.ground_arena + ps.space_arena
                         if u.instance_id == self.target_id and not u.exhausted), None)
            if unit is None:
                raise IllegalActionError("Not a ready friendly unit")
            unit.exhausted = True
        else:
            raise IllegalActionError(f"Unknown cost option {self.option!r}")
        return _resolve_use_force_payoff(s, top)

    def describe(self) -> str:
        return f"Use force option {self.option}"


@dataclass
class DeclineUseForce(Action):
    """Decline the optional "you may use the Force".  Nothing happens — unless the
    clause carries an "if you don't" penalty (Savage Opress LOF_137: deal 9 to your
    own base), in which case the penalty is applied after the decision pops (the
    "pop, then deal" gotcha, so a base-defeat trigger lands on a clean stack).
    ``decline_penalty`` is informational (the bot/web read it); the authoritative
    value is taken from the decision context."""
    decline_penalty: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "use_force"):
            raise IllegalActionError("No use_force decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "choose":
            raise IllegalActionError("use_force decision is past the choose stage")
        penalty = top.context.get("decline_penalty")
        controller_id = top.context.get("controller_id")
        s = _pop_use_force(s, top, "declined")
        if penalty:
            _apply_use_force_decline_penalty(s, controller_id, penalty)
        return s

    def describe(self) -> str:
        return "Decline using the Force"


@dataclass
class ChooseUseForcePayoffTarget(Action):
    """Choose the enemy unit to exhaust in the 'use_force' payoff stage (Impossible
    Escape LOF_218 — the draw already happened when the cost was paid)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "use_force"):
            raise IllegalActionError("No use_force decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "payoff":
            raise IllegalActionError("use_force decision is not at the payoff stage")
        unit = next((u for u in _use_force_enemy_exhaust_targets(s, ctx)
                     if u.instance_id == self.target_id), None)
        if unit is None:
            raise IllegalActionError("Not a legal enemy unit to exhaust")
        unit.exhausted = True
        return _pop_use_force(s, top, "exhausted an enemy unit")

    def describe(self) -> str:
        return f"Exhaust enemy unit {self.target_id}"

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "trigger_option":                _trigger_option_actions,
    "regroup_upkeep":                _regroup_upkeep_actions,
    "pay_or_exhaust":                _pay_or_exhaust_actions,
    "name_a_card":                   _name_a_card_actions,
    "resolve_unique":                _resolve_unique_actions,
    "may_discard":                   _may_discard_actions,
    "use_force":                     _use_force_actions,
})
