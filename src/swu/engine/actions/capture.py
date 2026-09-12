"""Capture: taking an enemy unit out of play without defeating it.

A captured card does not go to a zone of its own — it sits *under its captor*, which
creates the asymmetry that is the whole of this family's difficulty: the capturing player
controls something they do not own, and the card's fate is tied to a unit rather than to a
zone. Nothing else in the game is held that way.

The decisions here are the ways a capture gets chosen:

* ``capture_or_ready`` — the opponent chooses whether one of their units is captured or
  readied, so the deciding player is not the capturing one.
* ``combined_power_play`` — build a pool of friendly units whose combined **power**
  (``_combined_power_choices``, TWI_89) pays for the capture; ``max_units`` caps the pool
  for the Exploit variant and is left unset for "any number".
* ``multi_capture`` — pair several friendly units each against one enemy, so the legal
  pairings shrink as they are chosen.
* ``rescue_guarded`` — the defending player recovering a guarded captive.

**The release paths matter more than the capture paths, and they are deliberately not
here.** ``zones._release_captured_cards`` runs when a captor is defeated and
``zones._rescue_captured_card`` when a captive is recovered; both sit far down in the
kernel because unit defeat has to be able to release a captive without knowing anything
about how the capture was decided. A captured card returning to play must not remember
the captor's control, and getting that wrong leaks a card to the wrong player rather than
crashing — which is why ``invariants.py``'s card-conservation check counts
``ps.capture_pile`` alongside the arenas and the hand rather than treating a captive as
gone.

One thing that is *not* here despite its name: ``push_pay_resources_for_tokens`` sat under
a capture banner and was assigned to this family by proximity, but the kind it pushes is
handled in ``tokens``, so that is where it lives. A ``push_*`` entry point has no callers
inside the package -- the card modules call it -- so dependency closure cannot place it,
and the banner is exactly the wrong thing to fall back on. The rule that works is: a push
function belongs with the handler for the kind it pushes.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Leader
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.stats import (
    compute_power,
)
from swu.engine.actions.zones import (
    _apply_capture, _draw_cards, _rescue_captured_card,
)
from swu.engine.actions.shared import (
    _apply_defeat_unit_by_id,
)
from swu.engine.actions.hand import (
    push_play_from_hand,
)


# ── Opponent chooses one of their own non-leader units to be captured by the

@dataclass
class ChooseCaptureVictim(Action):
    """The opponent chooses one of their own non-leader units to be captured by the
    source (Grand Admiral Thrawn SEC_193 WhenPlayed)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "capture_or_ready"):
            raise IllegalActionError("No capture-or-ready decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _capture_or_ready_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal unit to capture")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="capture_or_ready",
            choice=f"captured {self.target_id}",
        ))
        _apply_capture(s, ctx["source_id"], self.target_id)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Choose unit to be captured {self.target_id}"


@dataclass
class DeclineCaptureVictim(Action):
    """The opponent declines to give up a unit; the source readies instead (Grand
    Admiral Thrawn SEC_193 WhenPlayed "If they don't, ready this unit")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "capture_or_ready"):
            raise IllegalActionError("No capture-or-ready decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="capture_or_ready",
            choice="declined — source readied",
        ))
        src_res = s.find_instance(ctx["source_id"])
        if src_res is not None:
            src_res[1].exhausted = False
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to give up a unit"


# ── Multi-capture pairing: choose any number of friendly units, each captures an

@dataclass
class CaptureWithUnit(Action):
    """One (captor, prey) capture of the multi_capture_pairing decision (Finalizer
    SHD_92): the friendly ``captor_id`` captures the enemy non-leader ``prey_id`` in
    the same arena, under it, inline."""
    captor_id: str
    prey_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "multi_capture_pairing"):
            raise IllegalActionError("No multi_capture_pairing decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if (self.captor_id, self.prey_id) not in _multi_capture_pairs(s, ctx):
            raise IllegalActionError(
                f"{self.captor_id}->{self.prey_id} is not a legal capture pair")
        _apply_capture(s, self.captor_id, self.prey_id)
        ctx.setdefault("used_captors", []).append(self.captor_id)
        ctx.setdefault("captured", []).append(self.prey_id)
        # Auto-resolve once no further legal pair remains.
        if not _multi_capture_pairs(s, ctx):
            return _resolve_multi_capture(s, top)
        return s

    def describe(self) -> str:
        return f"Capture {self.prey_id} with {self.captor_id}"


@dataclass
class FinishMultiCapture(Action):
    """Stop the multi_capture_pairing decision ("any number") — captures happened
    inline as each pair was chosen, so this just pops the decision (Finalizer
    SHD_92)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "multi_capture_pairing"):
            raise IllegalActionError("No multi_capture_pairing decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("mandatory") and _multi_capture_pairs(s, top.context):
            raise IllegalActionError("Each friendly unit must capture if it can")
        return _resolve_multi_capture(s, top)

    def describe(self) -> str:
        return "Finish capturing with your units"


# ── Choose any number of friendly units, play a unit free up to their combined

@dataclass
class SelectCombinedPowerUnit(Action):
    """Add one friendly unit to the combined-power pool (TWI_89)."""
    unit_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "combined_power_play"):
            raise IllegalActionError("No combined_power_play decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.unit_id not in _combined_power_choices(s, ctx):
            raise IllegalActionError(f"{self.unit_id} is not an eligible unit")
        ctx.setdefault("chosen", []).append(self.unit_id)
        return s

    def describe(self) -> str:
        return f"Add {self.unit_id} to the combined power"


@dataclass
class FinishCombinedPowerPlay(Action):
    """Stop choosing ("any number", including none) and resolve TWI_89's payoff."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "combined_power_play"):
            raise IllegalActionError("No combined_power_play decision pending")
        s = copy.deepcopy(state)
        return _resolve_combined_power_play(s, s.pending_decisions[-1])

    def describe(self) -> str:
        return "Finish choosing units"


# ── Opponent may give up a non-leader unit to be captured, else the source

#    readies (Grand Admiral Thrawn SEC_193 WhenPlayed) ─────────────────────
def _capture_or_ready_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = [ChooseCaptureVictim(t)
                          for t in _capture_or_ready_targets(state, top.context)]
    acts.append(DeclineCaptureVictim())  # "An opponent MAY choose …"
    return acts


# ── The defending player may rescue one of their own cards guarded by the

#    attacker; if they do, the attacker's controller draws (Cad Bane TWI_187) ──
def _rescue_guarded_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [RescueGuardedCard(cid)
            for cid in _rescue_guarded_candidates(state, top.context)]
    acts.append(DeclineRescue())  # "MAY rescue"
    return acts


# ── Choose any number of friendly units, each captures an enemy non-leader

#    unit in the same arena (Finalizer SHD_92) ─────────────────────────────
def _multi_capture_pairing_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [CaptureWithUnit(cap, prey)
            for cap, prey in _multi_capture_pairs(state, top.context)]
    # "EACH friendly unit captures …" (Let's Talk SEC_131) has no "any number":
    # while a legal pair remains the controller must make it, so the stop is
    # withheld and the decision still auto-resolves when the pairs run out.
    if not (top.context.get("mandatory") and acts):
        acts.append(FinishMultiCapture())  # "any number" — stop is legal
    return acts


# ── Choose any number of friendly units; their combined power caps a free

#    play from hand, then they are defeated (Consolidation of Power TWI_89) ──
def _combined_power_play_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectCombinedPowerUnit(uid)
            for uid in _combined_power_choices(state, top.context)]
    acts.append(FinishCombinedPowerPlay())  # "any number" — stop is legal
    return acts


# ── Opponent chooses one of their own non-leader units to be captured, else the

def _capture_or_ready_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal instance ids the opponent may give up to be captured (recomputed from
    current state): the opponent's own non-leader arena units (a deployed leader is
    a Leader card_def and so excluded, mirroring the ``non_leader`` predicate)."""
    from swu.cards.models import Leader
    ps = state.player_by_id(ctx["opponent_id"])
    return [u.instance_id for u in ps.ground_arena + ps.space_arena
            if not isinstance(u.card_def, Leader)]


def push_opponent_capture_or_ready(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'capture_or_ready' decision (Grand Admiral Thrawn SEC_193 WhenPlayed):
    the OPPONENT of the source's controller may choose one of their own non-leader
    units to be captured by the source (ChooseCaptureVictim), or decline
    (DeclineCaptureVictim → the source readies).  The capture/ready happens after
    the decision pops (the "pop, then act" gotcha).

    When the opponent has no non-leader unit they cannot choose, so "they don't" ⇒
    the source readies **inline** and no decision is pushed."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
    }
    if not _capture_or_ready_targets(s, ctx):
        # Opponent has nothing to give up → "they don't" → ready the source now.
        source_ci.exhausted = False
        return
    opp_idx = s.player_index(opponent_id)
    dec = PendingDecision(
        deciding_player_id=opponent_id,
        kind="capture_or_ready",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = opp_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=opponent_id,
        kind="capture_or_ready",
    ))


# ── The DEFENDING player may rescue one of their own cards guarded by a unit;

@dataclass
class RescueGuardedCard(Action):
    """Rescue one of your own cards guarded by the source unit; the source's
    controller then draws (Cad Bane TWI_187)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "rescue_guarded"):
            raise IllegalActionError("No rescue_guarded decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id not in _rescue_guarded_candidates(s, ctx):
            raise IllegalActionError(f"{self.instance_id} is not rescuable here")
        s.pending_decisions.pop()
        res = s.find_instance(self.instance_id)
        drew = 0
        if res is not None and _rescue_captured_card(s, res[1]):
            drew = _draw_cards(s, s.player_by_id(ctx["controller_id"]),
                               int(ctx.get("draw", 0)))
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="rescue_guarded",
            choice=f"rescued {self.instance_id} — {ctx['controller_id']} drew {drew}",
        ))
        # Hand the seat back to the source's controller even with decisions still
        # buried below (an On Attack leaves a pre_attack bookmark) — the say_no
        # AllowEffect/SayNo convention.
        if not s.is_terminal():
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Rescue {self.instance_id}"


@dataclass
class DeclineRescue(Action):
    """Decline the rescue ("MAY rescue") — nothing happens, and the source's
    controller draws nothing (Cad Bane TWI_187)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "rescue_guarded"):
            raise IllegalActionError("No rescue_guarded decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="rescue_guarded",
            choice="declined the rescue",
        ))
        if not s.is_terminal():
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline the rescue"


def _rescue_guarded_candidates(state: GameState, ctx: dict) -> list[str]:
    """Cards the DECIDER owns that are currently guarded by the source unit."""
    decider_id = ctx["decider_id"]
    guard_id = ctx["guard_id"]
    return [c.instance_id
            for ps in state.players
            for c in ps.capture_pile
            if c.captured_by == guard_id and c.owner_id == decider_id]


def push_rescue_guarded(
    s: GameState, source_ci: CardInstance, *, draw_on_rescue: int,
) -> None:
    """Push a 'rescue_guarded' decision (Cad Bane TWI_187): the source's OPPONENT
    may rescue one of their own cards guarded by the source; if they do, the
    source's controller draws ``draw_on_rescue`` cards.

    Pushed only when that player actually owns a card guarded by the source — with
    nothing to rescue the decision could only be declined."""
    controller_id = source_ci.owner_id
    ctrl_idx = s.player_index(controller_id)
    decider_id = s.players[1 - ctrl_idx].player_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "decider_id": decider_id,
        "guard_id": source_ci.instance_id,
        "draw": int(draw_on_rescue),
    }
    if not _rescue_guarded_candidates(s, ctx):
        return
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="rescue_guarded",
        context=ctx,
        after_resolve_player_index=ctrl_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id,
        kind="rescue_guarded",
    ))


def _multi_capture_pairs(state: GameState, ctx: dict) -> list[tuple[str, str]]:
    """Legal (captor_id, prey_id) pairs for the multi_capture_pairing decision
    (Finalizer SHD_92): a friendly unit not yet used as a captor paired with an enemy
    non-leader unit in the SAME arena not yet captured this resolution.  Recomputed
    each step, so a captor/prey that left play (a chained defeat) drops out."""
    controller_id = ctx["controller_id"]
    used_captors = set(ctx.get("used_captors", []))
    captured = set(ctx.get("captured", []))
    ctrl_idx = state.player_index(controller_id)
    ctrl = state.players[ctrl_idx]
    opp = state.players[1 - ctrl_idx]
    pairs: list[tuple[str, str]] = []
    for arena_name, friendly, enemy in (
        ("ground", ctrl.ground_arena, opp.ground_arena),
        ("space", ctrl.space_arena, opp.space_arena),
    ):
        preys = [e for e in enemy
                 if e.instance_id not in captured
                 and not isinstance(e.card_def, Leader)]
        if not preys:
            continue
        for cap in friendly:
            if cap.instance_id in used_captors:
                continue
            for prey in preys:
                pairs.append((cap.instance_id, prey.instance_id))
    return pairs


def push_multi_capture(s: GameState, source_ci: CardInstance, *,
                       mandatory: bool = False) -> None:
    """Push a 'multi_capture_pairing' decision (Finalizer SHD_92): "Choose any number
    of friendly units.  Each captures an enemy non-leader unit in the same arena."
    The controller repeatedly picks a (captor, prey) pair; each capture happens
    inline.  Pushed only when ≥1 legal pair exists; "any number" includes 0, so
    FinishMultiCapture is always offered while the decision is up.

    ``mandatory`` drops that stop while a legal pair remains — "EACH friendly unit
    captures an enemy non-leader unit in the same arena" (Let's Talk SEC_131), which
    is the same walk with no opt-out.  The decision still auto-resolves once the
    pairs run out, so the controller only ever chooses the PAIRING."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "used_captors": [],
        "captured": [],
        "mandatory": bool(mandatory),
    }
    if not _multi_capture_pairs(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="multi_capture_pairing",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="multi_capture_pairing",
    ))


def _resolve_multi_capture(s: GameState, top) -> GameState:
    """Pop the 'multi_capture_pairing' decision (captures happened inline) and hand
    the turn back (Finalizer SHD_92)."""
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="multi_capture_pairing",
        choice=f"captured {len(ctx.get('captured', []))} unit(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _combined_power_choices(state: GameState, ctx: dict) -> list[str]:
    """Friendly units still available to add to TWI_89's combined-power pool (each
    unit may be chosen at most once).

    ``max_units`` caps the pool ("defeat up to 1 unit you control" — the Exploit
    variant, Count Dooku TWI_5); TWI_89's own "any number" leaves it unset."""
    ps = state.player_by_id(ctx["controller_id"])
    already = set(ctx.get("chosen", []))
    cap = ctx.get("max_units")
    if cap is not None and len(already) >= int(cap):
        return []
    return [ci.instance_id for ci in ps.ground_arena + ps.space_arena
            if ci.instance_id not in already]


def push_combined_power_play(
    s: GameState, source_ci: CardInstance, *,
    trait: Optional[str] = None,
    max_units: Optional[int] = None,
    cost_reduction_per_unit: Optional[int] = None,
) -> None:
    """Push a 'combined_power_play' decision (Consolidation of Power TWI_89):
    "Choose any number of friendly units.  You may play a unit from your hand if
    its cost is less than or equal to the combined power of the chosen units for
    free.  Then, defeat the chosen units."

    Pushed only when the controller has ≥1 unit — with none, the combined power is
    0 and nothing is spent, so the card has nothing to do.

    The EXPLOIT pricing variant (Count Dooku TWI_5's "Play a Separatist card from
    your hand.  It gains Exploit 1") sets ``cost_reduction_per_unit`` (and usually
    ``max_units`` and ``trait``): instead of a free play capped by combined power,
    the chosen units buy a DISCOUNT of that many resources each on an ordinary
    (paid) play of a matching card.  Under that variant the chosen units are
    defeated only if the play happens — exploiting is part of playing the card, so
    a fizzled play costs nothing, the opposite of TWI_89's unconditional "Then,
    defeat the chosen units"."""
    controller_id = source_ci.owner_id
    ctx = {"source_id": source_ci.instance_id,
           "controller_id": controller_id,
           "chosen": [],
           "trait": trait,
           "max_units": max_units,
           "cost_reduction_per_unit": cost_reduction_per_unit}
    if not _combined_power_choices(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=controller_id,
        kind="combined_power_play",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    ))
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="combined_power_play"))


def _resolve_combined_power_play(s: GameState, top) -> GameState:
    """Pop the 'combined_power_play' decision and cash the pool in: the combined
    effective power of the chosen units (read while they are still in play) becomes
    the ``cost_max`` of a FREE play_from_hand, which carries ``then_defeat_ids`` so
    the chosen units die once that play resolves.  When nothing in hand fits (no
    decision is pushed), the defeat happens here instead — the "Then, defeat the
    chosen units" clause is not conditional on the play."""
    ctx = top.context
    chosen = [cid for cid in ctx.get("chosen", []) if s.find_instance(cid) is not None]
    total = 0
    for cid in chosen:
        res = s.find_instance(cid)
        if res is not None:
            total += max(0, compute_power(s, res[1]))
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="combined_power_play",
        choice=f"combined power {total} from {len(chosen)} unit(s)",
    ))
    res = s.find_instance(ctx["source_id"])
    before = len(s.pending_decisions)
    per_unit = ctx.get("cost_reduction_per_unit")
    if res is not None and per_unit is not None:
        # Exploit pricing (TWI_5): a paid play of a matching card, 2 resources less
        # per unit given up.  The units still die via ``then_defeat_ids`` — after
        # the play, so their stats are intact while the card is being paid for.
        push_play_from_hand(s, res[1], trait=ctx.get("trait"),
                            cost_reduction=int(per_unit) * len(chosen),
                            then_defeat_ids=chosen)
    elif res is not None:
        push_play_from_hand(s, res[1], free=True, cost_max=total,
                            then_defeat_ids=chosen)
    if len(s.pending_decisions) == before:
        # Nothing playable.  Under exploit pricing the sacrifice is part of playing
        # the card, so no play means no defeat; TWI_89's "Then, defeat the chosen
        # units" is unconditional and settles here.
        for cid in ([] if per_unit is not None else chosen):
            if s.find_instance(cid) is not None:
                _apply_defeat_unit_by_id(s, cid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "capture_or_ready":              _capture_or_ready_actions,
    "rescue_guarded":                _rescue_guarded_actions,
    "multi_capture_pairing":         _multi_capture_pairing_actions,
    "combined_power_play":           _combined_power_play_actions,
})
