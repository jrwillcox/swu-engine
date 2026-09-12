"""Paying with your own board, where the player chooses how much to pay.

A fixed cost is arithmetic. These are the effects whose cost is something the controller
gives up in an amount they choose, which makes each one a decision that accumulates rather
than a calculation: sacrifice a resource, exhaust any number of friendly units, exhaust
units up to a combined budget, cull cards from your own deck, reveal resources for ramp,
capture using combined HP, and Exploit. The payoff usually scales with what was paid, so
the cost and the effect cannot be settled separately.

The recurring correctness problem is that **the pool shrinks as it is spent**, and
``_exhaust_combined_targets`` is the clearest example of how that is handled: a unit already
chosen is excluded explicitly *and* falls out again naturally, because choosing it exhausts
it and the candidate predicate wants ready units. Two independent reasons for the same
exclusion is not redundancy worth removing -- it is why a bug in either one does not become
a double-spend.

Weight is not a fixed attribute either. ``_exhaust_combined_weight`` reads a unit's printed
cost *or* its effective power depending on the effect's ``budget_source``, so "units up to a
combined 5" means different sets for different cards.

Two neighbouring mechanics are deliberately in *different* modules, which looks arbitrary
until you see why. Capture-by-combined-**HP** is here, because the combined HP is a price
the controller pays. Capture-by-combined-**power** is in ``capture``, because there the
pooled power is what performs the capture. The split follows what the pooled number is
*for*, not what it is measured in -- and Exploit lives here for the same reason, since its
sacrifice is a cost rather than an effect.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, DecisionPushed, DecisionResolved, UnitDefeated,
)
from swu.engine.state import CardInstance, GameState, Zone
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.stats import (
    compute_hp, compute_power,
)
from swu.engine.actions.costs import (
    _exhaust_resources, _play_cost,
)
from swu.engine.actions.zones import (
    _apply_capture, _attach_upgrade, _create_token_units, _defeat_unit, _find_in_arenas, _put_unit_in_play, _resolve_event_ability,
)
from swu.engine.actions.shared import (
    _candidate_card_views, _resource_top_of_deck, _sacrifice_damage_targets,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, record_hand_discard,
)
from swu.engine.actions.modal import (
    push_modal,
)


# ── Sacrifice-a-resource as an optional cost ──────────────────────────────────

@dataclass
class SacrificeResource(Action):
    """Defeat one friendly resource to unlock the follow-up effect (Wrecker
    SHD_154).  Advances the 'sacrifice_resource' decision to its target stage."""
    resource_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "sacrifice_resource"):
            raise IllegalActionError("No sacrifice-resource decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "decide":
            raise IllegalActionError("Sacrifice-resource decision is past the decide stage")
        ps = s.player_by_id(ctx["controller_id"])
        res = next((r for r in ps.resources if r.instance_id == self.resource_id), None)
        if res is None:
            raise IllegalActionError(f"{self.resource_id} is not a friendly resource")
        ps.resources.remove(res)
        res.zone = Zone.DISCARD
        res.face_down = False
        res.exhausted = False
        ps.discard.append(res)
        s.event_log.append(UnitDefeated(
            player_id=ps.player_id,
            instance_id=res.instance_id,
            card_name=res.card_def.display_name,
        ))
        # The sacrifice is done — mark the stage before any early resolve so the
        # "if you do" payoff (the Credit token) still lands on the fizzle path.
        ctx["stage"] = "target"
        # If no damage target remains (none ever existed, since we only pushed when
        # one did — but recompute defensively), the damage fizzles: pop now.
        if not _sacrifice_damage_targets(s, ctx):
            return _resolve_sacrifice_resource(s, top, None)
        return s

    def describe(self) -> str:
        return f"Defeat resource {self.resource_id}"


@dataclass
class DeclineSacrifice(Action):
    """Decline the optional resource sacrifice — the ability does nothing
    (Wrecker SHD_154 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "sacrifice_resource"):
            raise IllegalActionError("No sacrifice-resource decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "decide":
            raise IllegalActionError("Sacrifice-resource decision is past the decide stage")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="sacrifice_resource",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline the resource sacrifice"


@dataclass
class ChooseSacrificeTarget(Action):
    """Choose the unit to receive the follow-up damage and resolve the
    'sacrifice_resource' decision (Wrecker SHD_154)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "sacrifice_resource"):
            raise IllegalActionError("No sacrifice-resource decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "target":
            raise IllegalActionError("Sacrifice-resource decision is not at the target stage")
        if self.target_id not in _sacrifice_damage_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        return _resolve_sacrifice_resource(s, top, self.target_id)

    def describe(self) -> str:
        return f"Deal damage to {self.target_id}"


# ── Reveal a resource, name-match a friendly unique unit, return it + ramp ─────

@dataclass
class RevealResourceForRamp(Action):
    """Reveal one of your matching resources: return it to its owner's hand and put
    the top card of your deck into play as a resource (Hunter SHD_9)."""
    resource_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_resource_ramp"):
            raise IllegalActionError("No reveal-resource decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        controller_id = ctx["controller_id"]
        if self.resource_id not in _reveal_ramp_candidates(s, controller_id):
            raise IllegalActionError(
                f"{self.resource_id} is not a name-matching resource")
        ps = s.player_by_id(controller_id)
        res = next(r for r in ps.resources if r.instance_id == self.resource_id)
        # Return the revealed resource to its owner's hand (resources are always
        # their controller's own cards, so owner == controller).
        owner_ps = s.player_by_id(res.owner_id)
        ps.resources.remove(res)
        res.zone = Zone.HAND
        res.face_down = False
        res.exhausted = False
        owner_ps.hand.append(res)
        name = res.card_def.display_name
        # Ramp: the controller puts the top of THEIR deck into play as a resource.
        _resource_top_of_deck(s, ps)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_resource_ramp",
            choice=f"revealed {name}, returned it and ramped",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Reveal resource {self.resource_id} (return it and ramp)"


@dataclass
class DeclineRevealResource(Action):
    """Decline the optional resource reveal — the ability does nothing (Hunter
    SHD_9 deployed "you may reveal")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_resource_ramp"):
            raise IllegalActionError("No reveal-resource decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if not top.context.get("optional"):
            raise IllegalActionError("This reveal is not optional")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_resource_ramp",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline the resource reveal"


# ── Exhaust any number of friendly units, deal base damage per unit exhausted

@dataclass
class SelectUnitToExhaust(Action):
    """Exhaust one eligible friendly unit toward the base-damage tally (The
    Invisible Hand TWI_234).  Keeps selecting until the controller finishes."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "exhaust_for_base_damage"):
            raise IllegalActionError("No exhaust_for_base_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _exhaust_for_base_damage_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible unit to exhaust")
        result = s.find_instance(self.target_id)
        if result is not None:
            _, unit = result
            unit.exhausted = True
        ctx["chosen"].append(self.target_id)
        # Stop automatically once no further eligible (ready) unit remains.
        if not _exhaust_for_base_damage_targets(s, ctx):
            return _resolve_exhaust_for_base_damage(s, top)
        return s

    def describe(self) -> str:
        return f"Exhaust {self.target_id} for base damage"


@dataclass
class FinishExhaustForBaseDamage(Action):
    """Stop exhausting units ("any number") and deal the accumulated base damage
    (The Invisible Hand TWI_234)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "exhaust_for_base_damage"):
            raise IllegalActionError("No exhaust_for_base_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_exhaust_for_base_damage(s, top)

    def describe(self) -> str:
        return "Finish exhausting units"


# ── Exhaust any number of units with combined cost ≤ N (Qui-Gon Jinn's Lightsaber

@dataclass
class SelectUnitToExhaustCombined(Action):
    """Exhaust one eligible unit (printed cost ≤ remaining budget) toward the
    combined-cost pool (Qui-Gon Jinn's Lightsaber LOF_201)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "exhaust_combined_cost"):
            raise IllegalActionError("No exhaust_combined_cost decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _exhaust_combined_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible unit to exhaust")
        result = s.find_instance(self.target_id)
        if result is not None:
            _, unit = result
            if ctx.get("remaining_budget") is not None:
                ctx["remaining_budget"] -= _exhaust_combined_weight(s, unit, ctx)
            unit.exhausted = True
        ctx["chosen"].append(self.target_id)
        # Stop automatically once no further eligible unit remains.
        if not _exhaust_combined_targets(s, ctx):
            return _resolve_exhaust_combined(s, top)
        return s

    def describe(self) -> str:
        return f"Exhaust {self.target_id} (combined cost)"


@dataclass
class FinishExhaustCombined(Action):
    """Stop exhausting units ("any number") for Qui-Gon Jinn's Lightsaber
    LOF_201 — the effect has no further payoff, so this just pops the decision."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "exhaust_combined_cost"):
            raise IllegalActionError("No exhaust_combined_cost decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_exhaust_combined(s, top)

    def describe(self) -> str:
        return "Finish exhausting units"


# ── Capture any number of enemy non-leader units with combined remaining HP ≤ N

@dataclass
class SelectUnitToCaptureCombined(Action):
    """Capture one eligible enemy non-leader unit (remaining HP ≤ remaining budget)
    under the pre-chosen friendly captor (Dismantle the Conspiracy SEC_106)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "capture_combined_hp"):
            raise IllegalActionError("No capture_combined_hp decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _capture_combined_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible unit to capture")
        result = s.find_instance(self.target_id)
        if result is not None:
            _, unit = result
            if ctx.get("remaining_budget") is not None:
                ctx["remaining_budget"] -= (compute_hp(s, unit) - unit.damage)
            # The DEFEAT disposition (Pre Vizsla ASH_53) records the pick and kills
            # it only once the decision has POPPED — a defeat pushes its own
            # triggers synchronously and must never run under an open decision
            # (the push_distribute_damage rule).  A capture is inert that way, so
            # it still happens inline.
            if ctx.get("disposition") != "defeat":
                _apply_capture(s, ctx["captor_id"], self.target_id)
        ctx["chosen"].append(self.target_id)
        # Stop automatically once no further eligible unit remains (or the captor
        # itself left play mid-capture).
        if not _capture_combined_targets(s, ctx):
            return _resolve_capture_combined(s, top)
        return s

    def describe(self) -> str:
        return f"Capture {self.target_id} (combined HP)"


@dataclass
class FinishCaptureCombined(Action):
    """Stop capturing units ("any number") for Dismantle the Conspiracy SEC_106 —
    captures happened inline, so this just pops the decision."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "capture_combined_hp"):
            raise IllegalActionError("No capture_combined_hp decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_capture_combined(s, top)

    def describe(self) -> str:
        return "Finish capturing units"


# ── Count Dooku TWI_138 — per-exploited-unit optional damage ──────────────────

def _per_exploit_enemy_targets(state: GameState, ctx: dict) -> list[str]:
    """Enemy (opponent-of-controller) arena units the controller may damage."""
    controller_id = ctx["controller_id"]
    opp = state.players[1 - state.player_index(controller_id)]
    return [u.instance_id for u in (opp.ground_arena + opp.space_arena)]


def push_per_exploit_damage(
    s: GameState, source_ci: CardInstance, amounts: list[int]
) -> None:
    """Push a 'per_exploit_damage' decision (Count Dooku TWI_138): for each amount
    in ``amounts`` (the powers of the units exploited to play this card), the
    controller may deal that much damage to one enemy unit, or skip it.

    Zero/negative amounts are dropped (a 0-power exploited unit deals nothing).
    Pushed only when ≥1 positive amount AND ≥1 enemy unit exist; otherwise the
    effect fizzles cleanly."""
    amts = [int(a) for a in amounts if int(a) > 0]
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "amounts": amts,
        "index": 0,
        "plan": [],  # list of [target_id, amount] recorded as chunks are decided
    }
    if not amts or not _per_exploit_enemy_targets(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="per_exploit_damage",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="per_exploit_damage"))


def _advance_per_exploit(s: GameState, top) -> GameState:
    """Advance to the next exploited-power chunk; once all are decided, pop the
    decision and deal every planned damage in order (pop-then-deal)."""
    ctx = top.context
    ctx["index"] += 1
    if ctx["index"] < len(ctx["amounts"]):
        return s  # more chunks remain — the decision stays up
    after_idx = top.after_resolve_player_index
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="per_exploit_damage",
        choice=f"dealt {len(ctx['plan'])} of {len(ctx['amounts'])} chunk(s)",
    ))
    from swu.abilities.resolver import _apply_deal_damage
    for tid, amt in ctx["plan"]:
        _apply_deal_damage(s, tid, amt)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = after_idx
    return s


@dataclass
class DealExploitDamage(Action):
    """Assign the current exploited-power chunk to one enemy unit (Count Dooku
    TWI_138).  The damage is recorded and dealt once all chunks are decided."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "per_exploit_damage"):
            raise IllegalActionError("No per_exploit_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _per_exploit_enemy_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal enemy unit")
        amount = ctx["amounts"][ctx["index"]]
        ctx["plan"].append([self.target_id, amount])
        return _advance_per_exploit(s, top)

    def describe(self) -> str:
        return f"Deal exploited-power damage to {self.target_id}"


@dataclass
class DeclineExploitDamage(Action):
    """Skip the current exploited-power chunk ("you may") — Count Dooku TWI_138."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "per_exploit_damage"):
            raise IllegalActionError("No per_exploit_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _advance_per_exploit(s, top)

    def describe(self) -> str:
        return "Decline exploited-power damage"


# ── Decision-resolving actions ────────────────────────────────────────────────

@dataclass
class ExploitSacrifice(Action):
    """Sacrifice a friendly unit to reduce the cost of the card being played."""
    unit_id: str

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "exploit":
            raise IllegalActionError("No pending Exploit decision")
        top = state.pending_decisions[-1]
        if top.context["max_remaining"] <= 0:
            raise IllegalActionError("No more Exploit sacrifices available")
        if self.unit_id in top.context["sacrificed_ids"]:
            raise IllegalActionError("Unit already sacrificed in this Exploit")
        s = copy.deepcopy(state)
        top_d = s.pending_decisions[-1]
        deciding_ps = s.player_by_id(top_d.deciding_player_id)

        victim = _find_in_arenas(deciding_ps, self.unit_id)
        if victim is None:
            raise IllegalActionError(f"Exploit sacrifice target {self.unit_id} not found")

        # Snapshot the victim's effective power BEFORE defeating it (Count Dooku
        # TWI_138 reads "the power of the exploited unit" at its When Played, when
        # the sacrificed unit is already gone).
        victim_power = compute_power(s, victim)
        # Defeat the sacrificed unit
        _defeat_unit(s, deciding_ps, victim)

        top_d.context["sacrificed_ids"].append(self.unit_id)
        top_d.context.setdefault("sacrificed_powers", []).append(victim_power)
        top_d.context["max_remaining"] -= 1

        # Auto-commit if maximum sacrifices reached — but ONLY if the just-defeated
        # unit's WhenDefeated trigger did not push its own decision on top of the
        # exploit decision.  If it did, that decision must resolve first (it is on
        # top); the exploit decision then re-surfaces and legal_actions offers a
        # forced ExploitCommit.  Committing synchronously here would read the wrong
        # top decision's context (KeyError 'sacrificed_ids').
        if top_d.context["max_remaining"] == 0 and s.pending_decisions[-1] is top_d:
            return _resolve_exploit_commit(s)
        return s

    def describe(self) -> str:
        return f"Exploit: sacrifice {self.unit_id}"


@dataclass
class ExploitCommit(Action):
    """Done with Exploit sacrifices — proceed to pay cost and put card in play."""
    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "exploit":
            raise IllegalActionError("No pending Exploit decision")
        s = copy.deepcopy(state)
        return _resolve_exploit_commit(s)

    def describe(self) -> str:
        return "Exploit: commit (done sacrificing)"


# ── Exploit ───────────────────────────────────────────────────────────

def _exploit_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    acts = []
    sacrificed = top.context["sacrificed_ids"]
    if top.context["max_remaining"] > 0:
        already_sacrificed = set(sacrificed)
        for unit in deciding_ps.ground_arena + deciding_ps.space_arena:
            if unit.instance_id not in already_sacrificed:
                acts.append(ExploitSacrifice(unit.instance_id))
    # Only offer ExploitCommit when committing now is actually affordable.
    # If it is not, the player MUST sacrifice more first (committing would
    # raise IllegalActionError in _resolve_exploit_commit).  Auto-commit at
    # max sacrifices is always affordable by the PlayCard affordability gate,
    # and when there are no units to sacrifice the base cost was likewise
    # gated affordable — so this never leaves the action list empty.
    if deciding_ps.play_buffer:
        buffered = deciding_ps.play_buffer[0]
        cost_now = max(0, _play_cost(state, buffered, deciding_ps)
                       - 2 * len(sacrificed))
        if deciding_ps.available_resources >= cost_now:
            acts.append(ExploitCommit())
    else:
        acts.append(ExploitCommit())
    return acts


# ── Exhaust any number of friendly units, deal base damage per (The

#    Invisible Hand TWI_234) ──────────────────────────────────────────────
def _exhaust_for_base_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectUnitToExhaust(tid)
            for tid in _exhaust_for_base_damage_targets(state, top.context)]
    acts.append(FinishExhaustForBaseDamage())  # "any number" — stop is legal
    return acts

def _exhaust_combined_cost_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectUnitToExhaustCombined(tid)
            for tid in _exhaust_combined_targets(state, top.context)]
    acts.append(FinishExhaustCombined())  # "any number" — stop is legal
    return acts

def _capture_combined_hp_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectUnitToCaptureCombined(tid)
            for tid in _capture_combined_targets(state, top.context)]
    acts.append(FinishCaptureCombined())  # "any number" — stop is legal
    return acts


# ── For each exploited unit, you may deal its power to an enemy unit

#    (Count Dooku TWI_138) ──────────────────────────────────────────────────
def _per_exploit_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [DealExploitDamage(tid)
            for tid in _per_exploit_enemy_targets(state, top.context)]
    acts.append(DeclineExploitDamage())  # "you may" — skipping is legal
    return acts


# ── Plot — play Plot cards from resources on a leader deploy (Garindan

def _resolve_exploit_commit(s: GameState) -> GameState:
    """Shared commit logic for ExploitCommit and auto-commit at max sacrifices."""
    top_d = s.pending_decisions[-1]
    deciding_ps = s.player_by_id(top_d.deciding_player_id)

    # Retrieve the card from play_buffer
    if not deciding_ps.play_buffer:
        raise IllegalActionError("Exploit commit: no card in play buffer")
    ci = deciding_ps.play_buffer.pop(0)
    ci.zone = Zone.HAND  # temporary; will be set by put-in-play or discard below

    sacrificed_count = len(top_d.context["sacrificed_ids"])
    exploited_powers = list(top_d.context.get("sacrificed_powers", []))
    base_cost = _play_cost(s, ci, deciding_ps)
    actual_cost = max(0, base_cost - 2 * sacrificed_count)

    if deciding_ps.available_resources < actual_cost:
        raise IllegalActionError(
            f"Insufficient resources after Exploit: need {actual_cost}, "
            f"have {deciding_ps.available_resources}"
        )
    _exhaust_resources(deciding_ps, actual_cost)

    card_played_evt = CardPlayed(
        player_id=deciding_ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        cost_paid=actual_cost,
    )
    s.event_log.append(card_played_evt)

    upgrade_target_id = top_d.context.get("upgrade_target_id")
    after_idx = top_d.after_resolve_player_index

    # Pop the exploit decision FIRST, before the card enters play — otherwise the
    # played card's WhenPlayed / Ambush triggers push their own decisions onto the
    # stack and the pop below would remove one of *those*, leaving the (already
    # resolved) exploit decision on top with an empty play buffer (a second
    # ExploitCommit then raises "no card in play buffer").  This is the same
    # "pop, then act" gotcha as push_distribute_damage / each_player_defeats: the
    # play's triggers must land on a clean stack.
    s.event_log.append(DecisionResolved(
        deciding_player_id=top_d.deciding_player_id,
        kind="exploit",
        choice=f"sacrificed {sacrificed_count}",
    ))
    s.pending_decisions.pop()
    s.active_player_index = after_idx

    if isinstance(ci.card_def, (Unit, Leader)):
        # ``cost_paid`` is the POST-Exploit amount actually exhausted, which is what
        # "the number of resources paid to play this unit" means (Osi Sobeck
        # TWI_115) — every other play path already threads it into the When Played
        # event context; this one had not.
        _put_unit_in_play(s, deciding_ps, ci, cost_paid=actual_cost,
                          exploited_powers=exploited_powers)
    elif isinstance(ci.card_def, Upgrade):
        _attach_upgrade(s, deciding_ps, ci, upgrade_target_id)
    elif isinstance(ci.card_def, Event):
        ci.zone = Zone.DISCARD
        deciding_ps.discard.append(ci)
        _resolve_event_ability(s, deciding_ps, ci, after_idx)
    else:
        ci.zone = Zone.DISCARD
        deciding_ps.discard.append(ci)

    # Ambush / WhenPlayed triggers from the Exploit-played unit (above) push their
    # own decisions onto the now-clean stack.
    get_bus().fire(s, card_played_evt)

    return s


# ── Sacrifice-a-resource push helper (Wrecker SHD_154) ────────────────────────

def _reveal_ramp_candidates(s: GameState, controller_id: str) -> list[str]:
    """Instance ids of ``controller_id``'s resources whose name matches a friendly
    unique unit — the reveal candidates for Hunter SHD_9.

    "shares a name with a friendly unique unit": a resource whose card
    display_name equals that of some unique unit the controller has in an arena (a
    deployed leader is a unit and counts).  Recomputed each read (the board may
    have changed since the decision was pushed)."""
    ps = s.player_by_id(controller_id)
    unique_names = {
        u.card_def.display_name
        for u in ps.ground_arena + ps.space_arena
        if getattr(u.card_def, "is_unique", False)
    }
    if not unique_names:
        return []
    return [r.instance_id for r in ps.resources
            if r.card_def.display_name in unique_names]


def push_reveal_resource_ramp(
    s: GameState, source_ci: CardInstance, *, optional: bool,
) -> None:
    """Push a single-stage 'reveal_resource_ramp' decision: "Reveal a resource you
    control.  If it shares a name with a friendly unique unit, return it to its
    owner's hand and put the top card of your deck into play as a resource"
    (Hunter SHD_9).

    Only the name-matching resources are offered (a non-matching reveal does
    nothing); pushed only when ≥1 such candidate exists, so it is never a dead
    choice.  ``optional`` adds the DeclineRevealResource option (the deployed "you
    may reveal" side); the undeployed Action side passes ``optional=False`` and is
    itself gated by CONTROLLER_HAS_REVEAL_RAMP_RESOURCE so it is offered only when a
    match exists."""
    controller_id = source_ci.owner_id
    if not _reveal_ramp_candidates(s, controller_id):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="reveal_resource_ramp",
        context={"controller_id": controller_id, "optional": bool(optional)},
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="reveal_resource_ramp",
    ))


def _reveal_resource_ramp_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top reveal_resource_ramp decision."""
    ctx = top.context
    acts: list[Action] = [
        RevealResourceForRamp(rid)
        for rid in _reveal_ramp_candidates(state, ctx["controller_id"])
    ]
    if ctx.get("optional"):
        acts.append(DeclineRevealResource())
    return acts


def push_sacrifice_resource_for_damage(
    s: GameState, source_ci: CardInstance, *,
    amount: int,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    mandatory: bool = False,
    create_credit: bool = False,
) -> None:
    """Push a 'sacrifice_resource' decision: "You may defeat a friendly resource.
    If you do, deal ``amount`` damage to a <arena> unit" (Wrecker, SHD_154).

    Only pushed when the controller has at least one resource AND at least one
    legal damage target — sacrificing a resource for no effect is never offered
    (the ability is "may", so it simply does nothing in that case).

    ``mandatory`` drops the decline (the sacrifice is an activation COST rather
    than a "you may" rider — Chewbacca LAW_13's undeployed "Action [1 resource,
    Exhaust, defeat a friendly resource]"); the controller still chooses WHICH
    resource, which is the only reason the cost needs a decision at all.
    ``create_credit`` additionally creates a Credit token for the controller when
    the sacrifice happens ("… deal 2 damage to a unit **and create a Credit
    token**", both halves of LAW_13)."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "stage": "decide",
        "amount": int(amount),
        "target_controller": target_controller,
        "target_arena": target_arena,
        "mandatory": bool(mandatory),
        "create_credit": bool(create_credit),
    }
    if not ps.resources or not _sacrifice_damage_targets(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="sacrifice_resource",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="sacrifice_resource",
    ))


def _sacrifice_resource_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top sacrifice_resource decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "decide":
        ps = state.player_by_id(ctx["controller_id"])
        acts: list[Action] = [SacrificeResource(r.instance_id) for r in ps.resources]
        if not ctx.get("mandatory"):
            acts.append(DeclineSacrifice())  # "you may" — a cost has no decline
        return acts
    # stage "target"
    return [ChooseSacrificeTarget(t) for t in _sacrifice_damage_targets(state, ctx)]


def _resolve_sacrifice_resource(
    s: GameState, top, target_id: Optional[str]
) -> GameState:
    """Pop the decision, then deal the stored damage to ``target_id`` (if any).

    Damage is dealt AFTER popping (like push_distribute_damage) so a defeat
    trigger from the damage lands on a clean stack."""
    ctx = top.context
    amount = int(ctx["amount"])
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="sacrifice_resource",
        choice=(f"defeated a resource, dealt {amount} to {target_id}"
                if target_id else "defeated a resource (no target)"),
    ))
    # "… and create a Credit token" (Chewbacca LAW_13) — the credit is part of the
    # same "if you do" payoff, so it lands whenever a resource was actually
    # sacrificed (i.e. whenever we reached a resolve with a target chosen or the
    # target stage fizzled), never on a decline.
    if ctx.get("create_credit") and ctx.get("stage") == "target":
        from swu.engine.tokens import create_credit_token
        create_credit_token(s, s.player_by_id(ctx["controller_id"]))
    if target_id is not None:
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        _apply_deal_damage(s, target_id, amount, source_name=source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Cull any number of your own cards, then deal that many damage ─────────────

def _cull_pool(state: GameState, ctx: dict) -> list[CardInstance]:
    """The controller's cards still available to cull (chosen ones removed)."""
    ps = state.player_by_id(ctx["controller_id"])
    chosen = set(ctx.get("chosen", ()))
    if ctx["pool"] == "hand":
        pool = list(ps.hand)
    else:  # "tokens" — token units in the arenas plus token upgrades on them
        from swu.cards.models import TokenUnit, TokenUpgrade
        pool = []
        for ci in ps.ground_arena + ps.space_arena:
            if isinstance(ci.card_def, TokenUnit):
                pool.append(ci)
            pool.extend(u for u in ci.attached_upgrades
                        if isinstance(u.card_def, TokenUpgrade))
    return [ci for ci in pool if ci.instance_id not in chosen]


def _cull_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal recipients for the follow-up damage (units, plus bases when the card
    says "a unit or base" — Vader LAW_11)."""
    out = _sacrifice_damage_targets(state, ctx)
    if ctx.get("allow_base"):
        from swu.cards.models import Base
        controller_id = ctx["controller_id"]
        target_controller = ctx.get("target_controller", "any")
        for p in state.players:
            if target_controller == "friendly" and p.player_id != controller_id:
                continue
            if target_controller == "enemy" and p.player_id == controller_id:
                continue
            out.extend(b.instance_id for b in p.base_zone
                       if isinstance(b.card_def, Base))
    return out


def push_cull_for_damage(
    s: GameState, source_ci: CardInstance, *,
    pool: str,
    min_count: int = 0,
    max_count: Optional[int] = None,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    allow_base: bool = False,
    then_modal: Optional[list[str]] = None,
) -> None:
    """Push a 'cull_for_damage' decision (Darth Vader LAW_11, Han Solo LAW_17).

    ``pool`` is ``"hand"`` (discard cards from your hand) or ``"tokens"`` (defeat
    friendly tokens — token units and token upgrades alike).  ``min_count`` /
    ``max_count`` bound the "any number" (``None`` = the whole pool); a
    ``min_count`` of 1 makes it a cost with no decline.  Pushed only when the pool
    can meet ``min_count`` AND a damage target exists — culling for nothing is
    never offered.

    ``then_modal`` REPLACES the damage entirely: the cull is a pure COST and the
    payoff is a ``push_modal`` over the listed modes, pushed after the pop so the
    modal resolves on a clean stack ("Epic Action [defeat a friendly token]: Give an
    Experience or Shield token to a unit, or create a Credit token" — Alliance
    Outpost LAW_19).  With it set the damage-target stage is skipped and the
    damage-target push guard does not apply, since nothing is being damaged."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "stage": "select",
        "pool": pool,
        "chosen": [],
        "min_count": int(min_count),
        "max_count": max_count,
        "target_controller": target_controller,
        "target_arena": target_arena,
        "allow_base": bool(allow_base),
        "then_modal": list(then_modal) if then_modal else None,
    }
    available = _cull_pool(s, ctx)
    if len(available) < max(1, int(min_count)):
        return  # nothing to cull — fizzle cleanly, no prompt
    if not then_modal and not _cull_damage_targets(s, ctx):
        return  # nothing to hit — fizzle cleanly, no prompt
    ctx["candidates"] = _candidate_card_views(
        s, [ci.instance_id for ci in available])
    owner_idx = s.player_index(controller_id)
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=controller_id,
        kind="cull_for_damage",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    ))
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="cull_for_damage"))


def _cull_for_damage_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top cull_for_damage decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "target":
        return [ChooseCullDamageTarget(t) for t in _cull_damage_targets(state, ctx)]
    acts: list[Action] = []
    cap = ctx.get("max_count")
    if cap is None or len(ctx["chosen"]) < int(cap):
        acts.extend(SelectCullCard(ci.instance_id) for ci in _cull_pool(state, ctx))
    if len(ctx["chosen"]) >= int(ctx["min_count"]) or not acts:
        acts.append(FinishCull())
    return acts


def _resolve_cull_for_damage(
    s: GameState, top, target_id: Optional[str]
) -> GameState:
    """Pop the decision, cull the recorded cards, then deal that many damage.

    Everything happens after the pop so the defeats (and the damage's own defeat
    triggers) land on a clean stack."""
    ctx = top.context
    chosen = list(ctx.get("chosen", ()))
    amount = len(chosen)
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="cull_for_damage",
        choice=(f"culled {amount} → {amount} damage to {target_id}"
                if target_id else f"culled {amount} (no target)"),
    ))
    ps = s.player_by_id(ctx["controller_id"])
    if ctx["pool"] == "hand":
        for cid in chosen:
            card = next((c for c in ps.hand if c.instance_id == cid), None)
            if card is None:
                continue
            ps.hand.remove(card)
            card.zone = Zone.DISCARD
            ps.discard.append(card)
            note_hand_or_deck_discard(s, card)
            record_hand_discard(s, ps.player_id)
    else:
        from swu.abilities.resolver import _apply_defeat_unit
        for cid in chosen:
            _apply_defeat_unit(s, cid)
    if target_id is not None and amount > 0:
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        _apply_deal_damage(s, target_id, amount, source_name=source_name)
    # ``then_modal``: the cull was a COST, and this is its payoff (Alliance Outpost
    # LAW_19).  Pushed after the pop, so the modal sits on a clean stack.
    modes = ctx.get("then_modal")
    if modes and amount > 0 and not s.is_terminal():
        src = s.find_instance(ctx["source_id"])
        if src is not None:
            push_modal(s, src[1], list(modes))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class SelectCullCard(Action):
    """Mark one of your cards to be culled (discarded from hand / defeated as a
    token) by a cull_for_damage decision (Vader LAW_11, Han Solo LAW_17)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "cull_for_damage"):
            raise IllegalActionError("No cull_for_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "select":
            raise IllegalActionError("cull_for_damage is past the select stage")
        if self.instance_id not in {ci.instance_id for ci in _cull_pool(s, ctx)}:
            raise IllegalActionError(f"{self.instance_id} is not cullable")
        ctx["chosen"].append(self.instance_id)
        cap = ctx.get("max_count")
        if ((cap is not None and len(ctx["chosen"]) >= int(cap))
                or not _cull_pool(s, ctx)):
            return _advance_cull_to_target(s, top)
        return s

    def describe(self) -> str:
        return f"Cull {self.instance_id}"


@dataclass
class FinishCull(Action):
    """Stop choosing cards for a cull_for_damage decision ("any number" — this is
    the 'and no more' end of it)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "cull_for_damage"):
            raise IllegalActionError("No cull_for_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "select":
            raise IllegalActionError("cull_for_damage is past the select stage")
        return _advance_cull_to_target(s, top)

    def describe(self) -> str:
        return "Finish culling"


def _advance_cull_to_target(s: GameState, top) -> GameState:
    """Move a cull_for_damage decision from "select" to "target" — or resolve it
    straight away when nothing was culled (0 damage) or no target remains."""
    ctx = top.context
    ctx["stage"] = "target"
    # A ``then_modal`` cull has no damage stage at all — the cull IS the cost and
    # the modal is the payoff (Alliance Outpost LAW_19).
    if (ctx.get("then_modal") or not ctx["chosen"]
            or not _cull_damage_targets(s, ctx)):
        return _resolve_cull_for_damage(s, top, None)
    return s


@dataclass
class ChooseCullDamageTarget(Action):
    """Choose what takes the culled cards' worth of damage, resolving the
    cull_for_damage decision."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "cull_for_damage"):
            raise IllegalActionError("No cull_for_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "target":
            raise IllegalActionError("cull_for_damage is not at the target stage")
        if self.target_id not in _cull_damage_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        return _resolve_cull_for_damage(s, top, self.target_id)

    def describe(self) -> str:
        return f"Deal the culled damage to {self.target_id}"


# ── Exhaust any number of friendly units, deal base damage per (The Invisible

def _exhaust_for_base_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible ids: ready friendly units matching the stored trait filter, minus
    those already exhausted this way (a chosen unit becomes exhausted, so it falls
    out via the ``ready`` predicate — the chosen set is belt-and-braces)."""
    from swu.abilities.resolver import _gather_legal_targets
    from swu.abilities.registry import TargetSpec
    source_result = state.find_instance(ctx["source_id"])
    if source_result is None:
        return []
    _, source_ci = source_result
    spec = TargetSpec(
        controller="friendly", kind="unit",
        traits=tuple(ctx.get("traits", []) or ()),
        predicates=("ready",),
    )
    chosen = set(ctx.get("chosen", []))
    ids = _gather_legal_targets(state, spec, source_ci, {})
    return [tid for tid in ids if tid not in chosen]


def push_exhaust_for_base_damage(
    s: GameState, source_ci: CardInstance, *,
    traits: Optional[list[str]] = None, damage_per: int = 1,
) -> None:
    """Push an 'exhaust_for_base_damage' decision (The Invisible Hand TWI_234 On
    Attack): "Exhaust any number of friendly <trait> units.  Deal ``damage_per``
    damage to the defending player's base for each unit exhausted this way."

    The defending player is the opponent of the source's controller; its base id is
    recorded at push time.  Pushed only when at least one eligible ready unit
    exists (else the effect fizzles — exhausting nothing would deal no damage)."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    enemy_base = s.player_by_id(opponent_id).base_instance
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "traits": list(traits or []),
        "damage_per": int(damage_per),
        "base_id": enemy_base.instance_id if enemy_base is not None else None,
        "chosen": [],
    }
    if not _exhaust_for_base_damage_targets(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="exhaust_for_base_damage",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="exhaust_for_base_damage",
    ))


def _resolve_exhaust_for_base_damage(s: GameState, top) -> GameState:
    """Pop the decision, then deal ``damage_per`` × (units exhausted) to the
    defending base (the "pop, then deal" gotcha — a base-defeat trigger lands on a
    clean stack)."""
    ctx = top.context
    s.pending_decisions.pop()
    count = len(ctx.get("chosen", []))
    total = int(ctx.get("damage_per", 1)) * count
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="exhaust_for_base_damage",
        choice=f"exhausted {count} unit(s) → {total} base damage",
    ))
    base_id = ctx.get("base_id")
    if total > 0 and base_id is not None:
        from swu.abilities.resolver import _apply_deal_damage
        s = _apply_deal_damage(s, base_id, total)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _exhaust_combined_weight(state: GameState, ci: CardInstance, ctx: dict) -> int:
    """A unit's contribution to the combined-budget pool: its effective
    ``compute_power`` when ``budget_source == "power"`` (Mind Trick LOF_202,
    "combined power of 4 or less"), else its printed cost (the default, Qui-Gon
    Jinn's Lightsaber LOF_201, "combined cost")."""
    if ctx.get("budget_source") == "power":
        return compute_power(state, ci)
    return int(getattr(ci.card_def, "cost", 0) or 0)


def _exhaust_combined_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible ids: ready units (any controller), minus those already chosen (a
    chosen unit becomes exhausted, so it also falls out via the ``ready``
    predicate).  Filtered by the optional remaining budget (a unit's weight —
    printed cost or effective power per ``budget_source`` — ≤ remaining_budget when
    set) and the optional max-units cap (no candidates once ``max_units`` have been
    chosen)."""
    from swu.abilities.resolver import _gather_legal_targets
    from swu.abilities.registry import TargetSpec
    source_result = state.find_instance(ctx["source_id"])
    if source_result is None:
        return []
    _, source_ci = source_result
    chosen = ctx.get("chosen", [])
    max_units = ctx.get("max_units")
    if max_units is not None and len(chosen) >= int(max_units):
        return []
    spec = TargetSpec(controller=ctx.get("controller", "any"), kind="unit",
                      arena=ctx.get("arena"), predicates=("ready",))
    chosen_set = set(chosen)
    budget = ctx.get("remaining_budget")
    out: list[str] = []
    for tid in _gather_legal_targets(state, spec, source_ci, {}):
        if tid in chosen_set:
            continue
        if budget is not None:
            res = state.find_instance(tid)
            if res is None:
                continue
            _, ci = res
            if _exhaust_combined_weight(state, ci, ctx) > int(budget):
                continue
        out.append(tid)
    return out


def push_exhaust_combined_cost(
    s: GameState, source_ci: CardInstance, *,
    budget: Optional[int] = 6, max_units: Optional[int] = None,
    arena: Optional[str] = None, controller: str = "any",
    budget_source: str = "cost", then_suppress_if_trait: Optional[str] = None,
    then_create_token_per_unit: Optional[str] = None,
) -> None:
    """Push an 'exhaust_combined_cost' decision: "You may exhaust any number of
    units [with combined ``budget`` or less]".

    The decider is the source's controller; by default eligible units are any
    ready unit (``controller="any"`` — the controller points it at enemy units).
    ``controller`` ("friendly"/"enemy"/"any") narrows the eligible units to that
    side ("exhaust an enemy unit …" — Secret Battle of Pretend LAW_226).  Two
    optional caps: ``budget`` is a combined ceiling that shrinks as units are
    picked (``budget=6`` for Qui-Gon Jinn's Lightsaber LOF_201; ``None`` for no
    cap); ``max_units`` caps how MANY units may be exhausted (``max_units=1`` for
    "you may exhaust a unit" — Ahsoka Tano JTL_201's follow-up; ``None`` for
    unlimited).  ``arena`` ("ground"/"space") restricts the eligible units to that
    arena ("Exhaust up to 2 ground units" — The Mandalorian JTL_210; ``None`` for
    either arena).  ``budget_source`` selects what a unit's budget weight is:
    ``"cost"`` (printed cost, the default) or ``"power"`` (effective ``compute_power``
    — Mind Trick LOF_202, "combined power of 4 or less").  ``then_suppress_if_trait``
    (Mind Trick LOF_202): on resolve, IF the controller controls a unit with this
    trait, suppress each still-in-play chosen unit's abilities for this phase (the
    ability-suppression read-layer — ``CardInstance.abilities_suppressed``).
    ``then_create_token_per_unit`` (All Wings Report In JTL_122): on resolve, create
    one token unit of that name — under the DECIDER's control — for each unit
    actually exhausted ("For each unit exhausted this way, create an X-Wing token").
    Pushed only when ≥1 eligible unit exists; "any number" includes 0, so a
    FinishExhaustCombined is always offered while the decision is up."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "remaining_budget": (int(budget) if budget is not None else None),
        "max_units": (int(max_units) if max_units is not None else None),
        "arena": arena,
        "controller": controller,
        "budget_source": budget_source,
        "then_suppress_if_trait": then_suppress_if_trait,
        "then_create_token_per_unit": then_create_token_per_unit,
        "chosen": [],
    }
    if not _exhaust_combined_targets(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="exhaust_combined_cost",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="exhaust_combined_cost",
    ))


def _resolve_exhaust_combined(s: GameState, top) -> GameState:
    """Pop the 'exhaust_combined_cost' decision (units were exhausted inline as
    they were chosen) and hand the turn over.  If a ``then_suppress_if_trait`` was
    set and the controller controls a unit with that trait, each still-in-play
    chosen unit loses all abilities for this phase (Mind Trick LOF_202 — the
    ability-suppression read-layer)."""
    ctx = top.context
    trait = ctx.get("then_suppress_if_trait")
    if trait:
        from swu.engine.traits import has_trait
        controller = s.player_by_id(ctx["controller_id"])
        controls_trait = any(
            has_trait(s, u, trait)
            for u in controller.ground_arena + controller.space_arena)
        if controls_trait:
            for tid in ctx.get("chosen", []):
                res = s.find_instance(tid)
                if res is not None:
                    _, unit = res
                    unit.abilities_suppressed = True
    # "For each unit exhausted this way, create an <X> token" (All Wings Report In
    # JTL_122) — settled here, where the final count of chosen units is known.  The
    # tokens go to the DECISION's controller, whatever side the exhausted units were
    # on.  Popped first so an entering token's own triggers land on a clean stack.
    token_name = ctx.get("then_create_token_per_unit")
    n_chosen = len(ctx.get("chosen", []))
    s.pending_decisions.pop()
    if token_name and n_chosen:
        _create_token_units(s, s.player_by_id(ctx["controller_id"]),
                            token_name, n_chosen)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="exhaust_combined_cost",
        choice=f"exhausted {n_chosen} unit(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _capture_combined_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible ids for the capture_combined_hp decision: non-leader units whose
    *remaining* HP ≤ the remaining budget and not already chosen this way.
    Fizzles entirely if the pre-chosen captor has left play (nothing to capture
    under), or once the optional ``max_captures`` cap is reached.

    ``target_controller`` (default ``"enemy"``, the capture reading) widens the pool
    to every non-leader unit for the DEFEAT disposition ("Defeat any number of
    non-leader units with a total of 6 or less remaining HP" — Pre Vizsla ASH_53)."""
    from swu.abilities.resolver import _gather_legal_targets
    from swu.abilities.registry import TargetSpec
    source_result = state.find_instance(ctx["source_id"])
    if source_result is None:
        return []
    _, source_ci = source_result
    captor_id = ctx.get("captor_id")
    if captor_id is not None and state.find_instance(captor_id) is None:
        return []
    cap = ctx.get("max_captures")
    if cap is not None and len(ctx.get("chosen", [])) >= int(cap):
        return []   # "captures UP TO 3 …" — the cap also auto-finishes the decision
    spec = TargetSpec(controller=str(ctx.get("target_controller", "enemy")),
                      kind="unit", predicates=("non_leader",))
    chosen_set = set(ctx.get("chosen", []))
    budget = ctx.get("remaining_budget")
    out: list[str] = []
    for tid in _gather_legal_targets(state, spec, source_ci, {}):
        if tid in chosen_set:
            continue
        res = state.find_instance(tid)
        if res is None:
            continue
        _, ci = res
        if budget is not None and (compute_hp(state, ci) - ci.damage) > int(budget):
            continue
        out.append(tid)
    return out


def push_capture_combined_hp(
    s: GameState, source_ci: CardInstance, *, captor_id: Optional[str] = None,
    budget: int = 7, max_captures: Optional[int] = None,
    disposition: str = "capture", target_controller: str = "enemy",
    then_create_token_per_unit: Optional[str] = None,
) -> None:
    """Push a 'capture_combined_hp' decision (Dismantle the Conspiracy SEC_106): "A
    friendly unit captures any number of enemy non-leader units with combined
    remaining HP ≤ ``budget``."  The captor is the pre-chosen friendly unit; each
    pick captures an enemy non-leader unit under it inline and spends its remaining
    HP against the budget.  Pushed only when ≥1 eligible enemy unit exists; "any
    number" includes 0, so FinishCaptureCombined is always offered while up.

    ``max_captures`` additionally caps how many units may be taken ("captures UP TO
    3 enemy non-leader units with a total of 8 or less remaining HP" — Cad Bane
    TWI_187); None is the unbounded "any number".

    ``disposition="defeat"`` turns the same select-under-a-budget walk into "Defeat
    any number of non-leader units with a total of ``budget`` or less remaining HP"
    (Pre Vizsla ASH_53): no captor is needed, ``target_controller="any"`` widens the
    pool to both players' units, and the picks are killed after the pop (a defeat
    fires triggers synchronously).  ``then_create_token_per_unit`` names a token unit
    created for the controller once per unit actually defeated this way ("Create a
    Mandalorian token for each unit defeated this way")."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "captor_id": captor_id,
        "remaining_budget": int(budget),
        "max_captures": None if max_captures is None else int(max_captures),
        "chosen": [],
        "disposition": str(disposition),
        "target_controller": str(target_controller),
        "then_create_token_per_unit": then_create_token_per_unit,
    }
    if not _capture_combined_targets(s, ctx):
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="capture_combined_hp",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="capture_combined_hp",
    ))


def _resolve_capture_combined(s: GameState, top) -> GameState:
    """Pop the 'capture_combined_hp' decision (units were captured inline as they
    were chosen) and hand the turn over.

    Under the DEFEAT disposition (Pre Vizsla ASH_53) nothing has happened yet: the
    recorded picks are defeated HERE, after the pop, so each defeat's own triggers
    land on a clean stack — and one token unit is then created per unit that really
    left play ("for each unit defeated this way")."""
    ctx = top.context
    s.pending_decisions.pop()
    defeated = 0
    if ctx.get("disposition") == "defeat":
        from swu.abilities.resolver import _apply_defeat_unit
        for tid in ctx.get("chosen", []):
            if s.find_instance(tid) is None:
                continue    # already gone (a co-pick's defeat trigger, say)
            s = _apply_defeat_unit(s, tid)
            defeated += 1
        token_name = ctx.get("then_create_token_per_unit")
        if token_name and defeated:
            _create_token_units(s, s.player_by_id(ctx["controller_id"]),
                                str(token_name), defeated)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="capture_combined_hp",
        choice=(f"defeated {defeated} unit(s)" if ctx.get("disposition") == "defeat"
                else f"captured {len(ctx.get('chosen', []))} unit(s)"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "exploit":                       _exploit_actions,
    "sacrifice_resource":            _sacrifice_resource_actions,
    "reveal_resource_ramp":          _reveal_resource_ramp_actions,
    "cull_for_damage":               _cull_for_damage_actions,
    "exhaust_for_base_damage":       _exhaust_for_base_damage_actions,
    "exhaust_combined_cost":         _exhaust_combined_cost_actions,
    "capture_combined_hp":           _capture_combined_hp_actions,
    "per_exploit_damage":            _per_exploit_damage_actions,
})
