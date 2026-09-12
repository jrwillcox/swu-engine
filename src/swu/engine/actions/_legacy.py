"""Transitional holding module for the not-yet-extracted parts of actions.

This file is the remains of the single 24,788-line engine/actions.py, kept
under one name while its sections are moved out into the layered kernel
(base, costs, stats, zones, combat, observers, turn,
api) and the per-family decisions/ modules.  It shrinks with every commit
of the split and is deleted when it reaches zero.

Nothing should import from here directly: the package facade in __init__.py
re-exports every public name, and scripts/refactor_parity.py proves that each
extraction moved code without changing it.  The real module documentation lives in
__init__.py.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import AnyCard, Base, Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    AttackDeclared, CardPlayed, CardResourced,
    ControlChanged, DamageDealt, DecisionPushed, DecisionResolved, HandDrawn, HandKept, InitiativeTaken,
    LeaderDeployed, MulliganTaken, PlayerPassed, RegroupSkipped, UpgradeDetached,
)
from swu.engine.keywords import Keyword, has_keyword, keyword_value
from swu.engine.state import CardInstance, GameState, Phase, PlayerState, Zone, ability_suppressed
from swu.engine.triggers import get_bus

from swu.engine.actions.base import Action, IllegalActionError
from swu.engine.actions.shared import (
    _attach_pilot, _deploy_leader_into_arena, _eligible_pilot_targets, _enumerate_discard_play_actions, _plot_eligible_resource_ids, _plot_play_actions, _take_from_hand, spend_force_token,
)
from swu.engine.actions.observers import (
    _fire_base_damage_observers, _fire_bounty_observers, _fire_deck_discard_observers, _fire_draw_observers, _fire_force_observers, _fire_hand_discard_observers, _fire_heal_observers, _fire_noncombat_damage_observers, _fire_ready_observers, _fire_reveal_discard_observers, _fire_self_discard_observers, _fire_token_creation_observers, _fire_unit_entry_observers, _fire_upgrade_attach_observers, _fire_upgrade_defeat_observers,
)
from swu.engine.actions.dispatch import (
    decision_handler, register_decisions,
)
from swu.engine.actions.turn import (
    _advance_mulligan, _advance_setup_resources, _check_regroup_complete, _enter_regroup, _starting_hand_modifier, _starting_hand_size,
)
from swu.engine.actions.combat import (
    _enumerate_attacks, _enumerate_two_unit_attacks, _filter_granted_attacks, _forced_attack_actions, _pre_attack_actions, note_hand_or_deck_discard, record_hand_discard,
)
from swu.engine.actions.flow import (
    _assert_phase, _check_game_over, _switch_active_player,
)
from swu.engine.actions.zones import (
    _attach_upgrade, _defeat_unit, _draw_cards, _eligible_upgrade_targets, _find_in_arenas, _find_upgrade_host, _push_resolve_unique, _put_unit_in_play, _resolve_event_ability, _sweep_defeated_units, note_upgrade_defeated,
)
from swu.engine.actions.damage import (
    base_damage_after_prevention,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _consume_standing_discount, _defeat_credit, _discard_cost_candidates, _discard_cost_payable, _exhaust_resources, _pay_play_cost, _pilot_count, _pilot_limit, _piloting_cost, _piloting_discount_entry, _play_cost, _smuggle_cost, resource_cost_for,
)


# ── Setup actions ─────────────────────────────────────────────────────────────


def _mulligan_forbidden(ps: "PlayerState") -> bool:
    """True if ``ps``'s base says "You can't take a mulligan" (Nabat Village
    JTL_28)."""
    spec = _starting_hand_modifier(ps)
    return bool(spec is not None and spec.no_mulligan)


@dataclass
class KeepHand(Action):
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.SETUP_MULLIGAN)
        s = copy.deepcopy(state)
        idx = s.active_player_index
        s.event_log.append(HandKept(player_id=s.active_player.player_id))
        s.mulligan_done[idx] = True
        _advance_mulligan(s)
        return s

    def describe(self) -> str:
        return "Keep hand"


@dataclass
class TakeMultiligan(Action):
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.SETUP_MULLIGAN)
        s = copy.deepcopy(state)
        ps = s.active_player
        if _mulligan_forbidden(ps):
            raise IllegalActionError(
                f"{ps.player_id} can't take a mulligan (base restriction)")
        for ci in ps.hand:
            ci.zone = Zone.DECK
        ps.deck.extend(ps.hand)
        ps.hand.clear()
        rng = s.make_rng()
        rng.shuffle(ps.deck)
        s.rng_state = rng.getstate()
        _draw_cards(s, ps, _starting_hand_size(ps))
        s.event_log.append(MulliganTaken(player_id=ps.player_id))
        s.event_log.append(HandDrawn(player_id=ps.player_id, card_count=len(ps.hand)))
        s.mulligan_done[s.active_player_index] = True
        _advance_mulligan(s)
        return s

    def describe(self) -> str:
        return "Take mulligan (redraw 6)"


@dataclass
class ResourceCard(Action):
    """Resource a card from hand (SETUP_RESOURCES and REGROUP phases)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if state.phase not in (Phase.SETUP_RESOURCES, Phase.REGROUP):
            raise IllegalActionError(f"ResourceCard not legal in phase {state.phase}")
        s = copy.deepcopy(state)
        ps = s.active_player
        ci = _take_from_hand(ps, self.instance_id)
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ci.exhausted = False
        ps.resources.append(ci)
        s.event_log.append(CardResourced(
            player_id=ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
        ))
        if s.phase == Phase.SETUP_RESOURCES:
            s.resources_chosen[s.active_player_index] += 1
            if s.resources_chosen[s.active_player_index] == 2:
                _advance_setup_resources(s)
        else:
            ps.regroup_done = True
            _check_regroup_complete(s)
        return s

    def describe(self) -> str:
        return f"Resource card {self.instance_id}"


@dataclass
class SkipResource(Action):
    """Decline to resource during regroup."""
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.REGROUP)
        s = copy.deepcopy(state)
        ps = s.active_player
        s.event_log.append(RegroupSkipped(player_id=ps.player_id))
        ps.regroup_done = True
        _check_regroup_complete(s)
        return s

    def describe(self) -> str:
        return "Skip resource (regroup)"


# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class Pass(Action):
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        idx = s.active_player_index
        s.event_log.append(PlayerPassed(player_id=s.active_player.player_id))
        s.passed_players.add(idx)
        if len(s.passed_players) == 2:
            _enter_regroup(s)
        else:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return "Pass"


def _consume_pending_initiative_effects(s: GameState, player_id: str) -> None:
    """Fire and clear every armed "the next time you take the initiative this phase,
    <effect>" charge belonging to ``player_id`` (Premonition of Doom LOF_203).

    The only effect today is ``exhaust_all_units`` — EVERY unit in play, both sides,
    as printed.  Kept next to ``ClaimInitiative`` (its only caller) so the initiative
    path stays the single consumption site."""
    pending = getattr(s.game_memory, "pending_initiative_effects", None)
    if not pending:
        return
    mine = [e for e in pending if e.get("player_id") == player_id]
    if not mine:
        return
    s.game_memory.pending_initiative_effects = [
        e for e in pending if e.get("player_id") != player_id]
    for entry in mine:
        if entry.get("effect") == "exhaust_all_units":
            for ps in s.players:
                for u in ps.ground_arena + ps.space_arena:
                    u.exhausted = True


@dataclass
class ClaimInitiative(Action):
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        if state.initiative_claimed_this_round:
            raise IllegalActionError("Initiative already claimed this round")
        s = copy.deepcopy(state)
        idx = s.active_player_index
        s.initiative_holder = idx
        s.initiative_claimed_this_round = True
        init_evt = InitiativeTaken(player_id=s.active_player.player_id)
        s.event_log.append(init_evt)
        _consume_pending_initiative_effects(s, s.active_player.player_id)
        # "When you take the initiative: …" printed abilities (Ziton Moj SEC_168),
        # fired after the pre-armed effect charges above.
        from swu.abilities.resolver import fire_triggered_abilities
        s = fire_triggered_abilities(s, init_evt, after_all_player_idx=idx)
        s.passed_players.add(idx)
        if len(s.passed_players) == 2:
            _enter_regroup(s)
        else:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return "Claim initiative"


@dataclass
class PlayCard(Action):
    instance_id: str
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        ci = _take_from_hand(ps, self.instance_id)

        # Regional Governor SOR_62: an enemy namer forbids playing the named card
        # (defensive guard; enumeration already omits it).
        if _named_card_play_forbidden(s, ci, ps):
            raise IllegalActionError("An opponent has forbidden playing this card")
        if _cannot_play_from_hand(ci):
            raise IllegalActionError("This card can't be played from your hand")
        if _events_locked(s, ci, ps):
            raise IllegalActionError("You can't play events this phase")
        if _play_only_as_first_action_blocked(s, ci, ps):
            raise IllegalActionError(
                "This card may only be played as your first action")

        # ── Exploit: push sacrifice decision before paying cost ────────────
        # A pending "the next <trait> card you play this phase gains Exploit N"
        # grant (Count Dooku TWI_5) is consumed here and ADDS to the printed value,
        # so a card with no printed Exploit gains one and a printed Exploit 2 that
        # gains Exploit 3 exploits up to 5 units (numeric keyword values stack).
        granted_exploit = _consume_exploit_grant(s, ci, ps)
        if granted_exploit or has_keyword(s, ci, Keyword.EXPLOIT):
            exploit_n = keyword_value(s, ci, Keyword.EXPLOIT) + granted_exploit
            if exploit_n > 0:
                ci.zone = Zone.PLAY_BUFFER
                ps.play_buffer.append(ci)
                opponent_idx = 1 - s.active_player_index
                decision = PendingDecision(
                    deciding_player_id=ps.player_id,
                    kind="exploit",
                    context={
                        "max_remaining": exploit_n,
                        "sacrificed_ids": [],
                        # The effective power of each sacrificed unit AT sacrifice
                        # time (it is defeated before commit, so its power must be
                        # snapshotted here) — read by Count Dooku TWI_138's When
                        # Played ("deal damage equal to the power of the exploited
                        # unit").  Parallel to sacrificed_ids.
                        "sacrificed_powers": [],
                        "upgrade_target_id": self.upgrade_target_id,
                    },
                    after_resolve_player_index=opponent_idx,
                )
                s.pending_decisions.append(decision)
                s.event_log.append(DecisionPushed(
                    deciding_player_id=ps.player_id,
                    kind="exploit",
                ))
                # Suspend turn alternation — decision takes over
                return s
        # ──────────────────────────────────────────────────────────────────

        cost = _play_cost(s, ci, ps, target_host_id=self.upgrade_target_id)
        # Pay from ready resources, defeating Credit tokens to cover any shortfall
        # (jabba-the-hutt:07).  With no credits this is identical to the old
        # resource-only payment.
        _pay_play_cost(s, ps, cost)
        # Consume one applicable pending "next <trait> unit costs N less" discount
        # (Khetanna LAW_158); _play_cost already accounted for it in ``cost``.
        _consume_play_discount(s, ci, ps)
        # Spend any standing per-round discount that applied (Director Krennic JTLP_1;
        # host-scoped for Guardian of the Whills SOR_61).
        _consume_standing_discount(s, ci, ps, self.upgrade_target_id)

        card_played_evt = CardPlayed(
            player_id=ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)

        # Track Villainy card played for Vader-style conditional abilities
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)

        after_idx = 1 - s.active_player_index

        if isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, cost_paid=cost)
        elif isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
        elif isinstance(ci.card_def, Event):
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            # Resolve EventAbility
            _resolve_event_ability(s, ps, ci, after_idx)
        else:
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)

        get_bus().fire(s, card_played_evt)

        # "When you play another <X> card" observers (Fighters for Freedom
        # SOR_143).  CardPlayed is the one event every play path emits, so it is
        # the uniform hook for observers that must fire on a unit / event /
        # upgrade play alike; WhenPlayed (matched only on UnitEntersPlay /
        # UpgradePlayed) is unaffected, so the played card's own trigger does not
        # double-fire.  Fired after the played card's own triggers are collected.
        from swu.abilities.resolver import fire_triggered_abilities
        # Thread the played card's id so a "When you play an upgrade …: deal to
        # THAT unit" observer can locate the played upgrade's host (Dengar SHD_133).
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx,
                                 event_ctx={"played_card_id": ci.instance_id})

        # Skip turn alternation if a decision was pushed (e.g. Ambush trigger or event ability)
        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id}" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


@dataclass
class SmugglePlay(Action):
    """Play a card from your resource zone using its Smuggle keyword.

    The card leaves the resource zone, you pay its smuggle cost from your OTHER
    ready resources, and you replace it with the top card of your deck (face
    down, ready) so your resource count is preserved.  The card is then played
    exactly as a hand play (unit → arena, upgrade → attach, event → resolve),
    with ``via_smuggle`` threaded so any "When played using Smuggle" trigger
    fires.
    """
    instance_id: str
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player

        ci = None
        for i, r in enumerate(ps.resources):
            if r.instance_id == self.instance_id:
                ci = ps.resources.pop(i)
                break
        if ci is None:
            raise IllegalActionError(
                f"Smuggle source {self.instance_id} not in resource zone")

        cost = _smuggle_cost(s, ci, ps)
        if cost is None:
            raise IllegalActionError(
                f"{ci.card_def.display_name} cannot be played using Smuggle")
        # Pay from the OTHER resources (ci is already removed from the zone).
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
                player_id=ps.player_id,
                instance_id=repl.instance_id,
                card_name=repl.card_def.display_name,
            ))

        ci.face_down = False
        card_played_evt = CardPlayed(
            player_id=ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)

        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)

        after_idx = 1 - s.active_player_index

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

        # "When you play another <X> card" observers (see PlayCard); a smuggled
        # card is still "played", so the same hook applies.
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)

        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"Smuggle {self.instance_id}" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


@dataclass
class PilotPlay(Action):
    """Play a Unit card as a Pilot upgrade onto a friendly Vehicle unit.

    A Unit with the Piloting keyword may be played either as a normal unit (via
    PlayCard) OR as a Pilot upgrade attached to a friendly Vehicle unit for the
    bracketed Piloting cost.  The pilot contributes its ``upgrade_power``/
    ``upgrade_hp`` as stat bonuses to the host (read by ``compute_power``/
    ``compute_hp`` via ``getattr(card_def, "upgrade_power", 0)``).

    The Piloting cost is in the card's ``epic_action`` field.  ``_attach_pilot``
    fires ``UpgradePlayed`` (with ``via_pilot=True`` in the event context) so
    any "When Played" upgrade trigger fires correctly.

    Residual text ("Attached unit gains: …") is NOT implemented here — it will
    be registered in a later ability group.
    """
    instance_id: str
    vehicle_target_id: str

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player

        # Remove from hand
        ci = None
        for i, c in enumerate(ps.hand):
            if c.instance_id == self.instance_id:
                ci = ps.hand.pop(i)
                break
        if ci is None:
            raise IllegalActionError(
                f"Pilot source {self.instance_id} not in hand")

        cost = _piloting_cost(s, ci, ps)
        if cost is None:
            raise IllegalActionError(
                f"{ci.card_def.display_name} cannot be played as a pilot")
        # Consume the pending Piloting-aware discount this cost already reflects
        # (Wedge Antilles JTL_8), so it applies to exactly one Pilot play.
        _disc_idx = _piloting_discount_entry(s, ci, ps)
        if _disc_idx is not None:
            del s.game_memory.pending_play_discounts[_disc_idx]
        _pay_play_cost(s, ps, cost)

        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)

        after_idx = 1 - s.active_player_index
        card_played_evt = CardPlayed(
            player_id=ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)

        _attach_pilot(s, ps, ci, self.vehicle_target_id)

        get_bus().fire(s, card_played_evt)
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)

        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"PilotPlay {self.instance_id} on {self.vehicle_target_id}"


@dataclass
class DeclineGrantedAttack(Action):
    """Resolve a 'granted_attack' decision with no attack (the event fizzles).

    Only offered when the controller has no unit able to attack.
    """
    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "granted_attack":
            raise IllegalActionError("No granted_attack decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline granted attack"


# ── Owner-may-replay a just-returned unit for free (Baylan Skoll LOF_185,
#    Rio Durant LAW_93) ──────────────────────────────────────────────────────
#
# "Return a non-leader unit to its owner's hand.  Then, its owner may play it for
# free."  A multi-decider decision: the returned unit's OWNER — who may be the
# source's opponent — decides whether to replay it (the say_no SOR_233 /
# opponent_chooses_target SHD_246 deciding-player shift).  The return has already
# happened inline (via _apply_return_to_hand) before the decision is pushed by
# push_owner_may_replay.


# ── Put a chosen in-play unit on the top or bottom of its owner's deck
#    (Qui-Gon Jinn LOF_200) ─────────────────────────────────────────────────────
#
# "You may choose a non-leader ground unit.  Its owner puts it on the top or
# bottom of their deck."  A multi-decider decision: the source's controller picks
# the unit (via the CustomEffect.target seam), but the chosen unit's OWNER — who
# may be the source's OPPONENT — decides top vs bottom (only the owner should
# order their own deck; the say_no SOR_233 / owner_may_replay LOF_185
# deciding-player shift).  The unit leaves play as a RELOCATION (not a defeat — no
# WhenDefeated fires), mirroring _apply_return_to_hand but with the deck as the
# destination.


# ── Opponent "say no" reaction (say_no decision) ──────────────────────────────
#
# "Deal N damage to an enemy unit unless its controller says 'no.' If they do,
# draw M cards." (I Am Your Father, SOR_233).  The source's controller picks the
# enemy unit (via the CustomEffect.target seam); the chosen unit's controller —
# the OPPONENT — then resolves a 'say_no' decision: allow the effect (take the
# damage) or say "no" (no damage, and the source's controller draws).  See
# push_say_no.


# ── Recurring regroup upkeep: "pay 1 or return to hand" (Millennium Falcon
# SOR_193) ────────────────────────────────────────────────────────────────────
#
# "When you ready cards during the regroup phase: Either pay [1 resource] or
# return this unit to her owner's hand."  Fired at regroup start by a
# PhaseStartTrigger(phase="regroup") CustomEffect (the Contracted Hunter JTL_216
# site) which calls push_regroup_upkeep; the source's controller then chooses.


# ── Delayed action-phase-start scheduler + per-enemy pay-or-exhaust ────────────
#
# The Eye of Aldhani SEC_73/SECP_5 seam (a 1-cost Vigilance Event): "At the start
# of the next action phase, for each enemy unit, its controller must pay 1 resource
# or exhaust that unit."  Two primitives compose it:
#
#   (A) a DELAYED SCHEDULER — the event resolves in ACTION and goes to discard, so
#       there is no in-play host for a PhaseStartTrigger.  push_eye_of_aldhani_
#       schedule records a small serialisable entry in
#       state.scheduled_action_phase_effects; _fire_scheduled_action_phase_effects
#       drains it once at the next action-phase start (both _regroup_rollover and
#       _start_action_phase call it), mirroring the defeat_at_regroup / granted_
#       bounties "serialised flag swept at a phase boundary" shape.
#   (B) a PER-ENEMY PAY-OR-EXHAUST decision — a multi-unit sibling of the
#       regroup_upkeep decision (Millennium Falcon SOR_193), but the DECIDER is the
#       enemy (each unit's controller) and the consequence is exhaust, not bounce.


# ── Delayed "defeat a resource you control at the next action phase" ──────────
#
# Han Solo SOR_17: "… At the start of the next action phase, defeat a resource you
# control."  Composes the same scheduled_action_phase_effects seam as Eye of
# Aldhani — the leader's Action/On-Attack resolves in ACTION, so the delayed defeat
# is recorded by controller_id and drained once at the next action-phase start.
# Faithful simplification (the K-2SO SOR_145 auto-select precedent): resources are
# interchangeable face-down cards, so one is auto-defeated (a face-down, un-special
# resource is preferred) rather than prompting a choice.


# ── Player-directed damage distribution (distribute_damage decision) ──────────
#
# A reusable decision primitive for "deal damage divided as you choose" effects
# (Emperor Palpatine SOR_135, Overwhelming Barrage SOR_92, Maximum Firepower
# SOR_234).  See push_distribute_damage / push_distribute_source_power /
# push_sequence_damage for the three flavours and their context schema.


# ── Deck search-and-select (deck_search decision) ─────────────────────────────
#
# A reusable "search the top N cards of your deck for matching cards, reveal and
# draw the chosen ones, then put the rest on the bottom in a random order"
# primitive (Grand Moff Tarkin SOR_84, Recruit SOR_123).  The controller selects
# up to ``max_select`` of the eligible candidates; selection auto-finishes once
# the cap is reached.  ``up_to`` distinguishes "up to N" (a FinishSearch is always
# offered, so 0 picks is legal — Tarkin) from "for a <thing>" (mandatory if able,
# so a pick is forced while a candidate remains — Recruit).  See push_deck_search.


# ── Return cards from the discard pile to hand (return_from_discard decision) ──
#
# A reusable "return up to N matching cards from your discard pile to your hand"
# primitive (Razor Crest SHD_44 — "You may return an upgrade from your discard
# pile to your hand").  The discard pile is public, so the chosen cards are
# visible to both players; the controller picks up to ``max_select`` of the
# eligible cards, selection auto-finishes once the cap is reached, and a
# FinishReturnFromDiscard is always offered (these effects are "you may" / "up
# to", so taking 0 is legal).  See push_return_from_discard.  This is a
# self-contained decision kind — it touches no core resolution or trigger
# machinery (the deck_search / select_token "select up to N" pattern, but over
# the discard pile rather than the deck/arena).


# ── Put a chosen discard-pile card into play as a resource (resource_from_discard) ──
#
# The Marauder SHD_102 ("Choose a card in your discard pile.  Put it into play as a
# resource if it shares a name with a unit you control") and Spark of Hope SHD_105
# ("Choose a unit in your discard pile.  If it was defeated this phase, put it into
# play as a resource").  Both are "choose a discard card, THEN a gate decides whether
# it is resourced"; since choosing a non-qualifying card does nothing (there is no
# cost or downside to the choice), the candidates are PRE-FILTERED to the qualifying
# cards (the deck_search / return_from_discard "fizzle cleanly if none eligible"
# convention), collapsing the card to "choose one qualifying discard card → put it
# into play as a resource".  A self-contained decision kind (the return_from_discard
# select-one pattern, but the chosen card lands in the resource zone facedown +
# EXHAUSTED per CR §"PUT INTO PLAY AS A RESOURCE" — no "ready it" is printed — instead
# of returning to hand).


# ── Play a captured card for free under your control (play_captured_card) ─────
#
# Dryden Vos SHD_192 ("When Played: Choose a captured card guarded by a unit you
# control.  You may play it for free under your control").  A captive lives in the
# controller's own ``capture_pile`` (every captive there is guarded by one of their
# units), so the candidates are simply the Unit captives in that pile.  A
# self-contained decision kind mirroring the return_from_discard / resource_from_discard
# select-one-from-a-zone pattern: the chosen unit is removed from the capture pile and
# put into play under the controller (control follows the holder; owner unchanged) at
# cost 0, firing its own When Played / keyword triggers (pop-then-act, so those land on
# a clean stack).  ``up_to`` adds a decline for the "you may".


# ── Reveal the top N; an opponent culls some; you draw one (reveal_cull_draw) ────
#
# Admiral Trench JTL_14 ("Reveal the top 4 cards of your deck.  An opponent discards
# 2 of them.  Draw 1 of the remaining cards and discard the other.").  A two-stage
# DECIDER-SHIFT over one fixed set of revealed cards (the say_no SOR_233 seat-flip,
# but with a select-N stage on each side): the opponent culls first, then the
# controller takes one of the survivors and the rest are discarded.  Neither stage
# collapses to an optimal default — the opponent is denying the best cards while the
# controller is keeping the best of what is left — so both are real prompts.
#
# The revealed cards stay in the deck while the decision is open (the deck_search
# convention: nothing else can happen with a decision pending, and card conservation
# holds without a set-aside zone).  Both players see every revealed identity: the
# card says "Reveal", so the context carries them openly.


# ── Play unit-resources revealed for free, one at a time (play_resource_units) ────
#
# Endless Legions SHD_109 ("Reveal any number of resources you control.  Play each
# unit revealed this way for free (one at a time)").  Revealing a non-unit resource
# is strictly pointless — no unit is played and the identity leaks to the opponent —
# so the optimal-play collapse offers only the controller's Unit resources as
# candidates.  A repeated single-select loop (the "one at a time" wording): each pick
# removes that resource from the resource row and puts its unit into play for free
# under the controller, then RE-PUSHES the loop with the remaining unit-resources so
# the just-played unit's When Played / keyword triggers (pushed on top) fully resolve
# BEFORE the next pick — faithful LIFO ordering, unlike playing a whole batch in one
# apply().  DeclineResourceUnitPlay ends the loop (the "any number" — including zero —
# lets the controller stop early).  A played resource is NOT replaced from the deck
# (unlike Smuggle): the resource count genuinely drops, which is the card's tradeoff.


# ── Discard a same-named hand card to give 2 Experience (discard_for_experience) ──
#
# Echo SHD_99 "When Played: You may discard a card from your hand.  Give 2 Experience
# tokens to a unit in play with the same name as the discarded card." (Clone
# name-matching.)  Modelled as one decision: the candidates are the controller's hand
# cards whose name matches a FRIENDLY unit in play (discarding a non-matching card
# gives no benefit — the pre-filter/fizzle convention, and the never-buff-enemy
# principle keeps the token target friendly).  Selecting a hand card discards it and
# gives 2 Experience to a matching friendly unit (auto-pick one when several share the
# name — the K-2SO SOR_145 auto-select simplification); DeclineDiscardForExperience
# covers the "you may".


# ── Restock SOR_252: bottom up-to-N cards from a discard pile ─────────────────
#
# "Choose up to 4 cards in a discard pile.  Put them on the bottom of their owner's
# deck in a random order."  A select-up-to-N decision over BOTH players' discard
# piles (the card says "a discard pile" — either qualifies).  Each chosen card goes
# to the bottom of ITS OWNER's deck; the collected picks are shuffled first so the
# resulting bottom order is random (the deck_search bottoming pattern).


# ── Choose N different-named discard cards, return 1 of them at random ─────────
#
# Doctor Aphra SHD_15 "When Deployed: Choose 3 cards in your discard pile with
# different names.  If you do, return 1 of them at random to your hand."  Modelled
# as a mandatory forced-choice decision (``select_distinct_return_random``): the
# controller picks exactly ``count`` cards, each with a name distinct from those
# already picked (the remaining candidates are filtered by name after every pick),
# and on the last pick one of the chosen set is returned to hand at random.  Pushed
# only when ≥ ``count`` distinct names exist in the discard (else "if you do" fails
# and the effect does nothing) — so there is no decline/finish action; the player
# always completes a full selection.


# ── Peek at the top card of the deck (peek_top / choose_number decisions) ─────
#
# Two related "look at the top card of your deck" abilities (R2-D2 SOR_236,
# C-3PO SOR_238).  The engine has full information, but the DECISION is the
# player's, so each is modelled as a real choice point rather than auto-resolved:
#   - R2-D2: a binary "leave on top" (KeepTopCard) vs "put on the bottom"
#     (BottomTopCard) choice — a "peek_top" decision in mode "may_bottom".
#   - C-3PO: first a "choose_number" decision (ChooseNumber); on resolution the
#     top card is peeked and, only if its cost equals the chosen number, a
#     "peek_top" decision in mode "may_draw" offers KeepTopCard vs DrawTopCard.
#   - Ezra Bridger (SOR_192): mode "may_play_discard" — "Look at the top card of
#     your deck. You may play it, discard it, or leave it on top" offers
#     PlayTopCard (pay its cost, per legal host for an upgrade) / DiscardTopCard /
#     KeepTopCard (leave on top).
# See push_peek_top / push_choose_number.


# ── Look at an opponent's hand (Viper Probe Droid SOR_228 / SEC_239) ──────────
#
# "When Played: Look at an opponent's hand."  A pure information effect — the
# engine has full information already, but the *player* must actually be shown the
# opponent's hand.  The redacted PlayerView hides the opponent's hand entirely, so
# the old implementation (a HandInspected log entry with only a count) left the
# human unable to see anything.  Modelled as a private informational decision: the
# revealed hand's card identities are carried in the deciding (inspecting) player's
# decision context — which view_for only sends to that player — so the UI can show
# them, and the opponent never sees the reveal.  IMPORTANT: only card_id + name are
# stored, NOT the opponent's hand instance_ids (those are hidden info; surfacing an
# opponent hand instance_id in the inspector's view would trip the hidden-info
# leak invariant, which keys on instance_id).


# ── Modal "choose one" decision (Leia Organa SOR_189) ─────────────────────────
#
# A "modal" decision presents the controller with a "choose one" effect, then a
# target choice for the selected mode.  Leia Organa ("Either ready a resource or
# exhaust a unit") is the first user.  A mode whose legal targets are
# interchangeable (``_MODAL_FUNGIBLE_MODES``, e.g. "ready a resource") skips the
# target step and resolves on an arbitrary target.  See push_modal.


# ── Let the Wookiee Win (SHD_205): an OPPONENT-decided modal ───────────────────
#
# "An opponent chooses one: [You ready up to 6 resources] / [You ready a friendly
# unit.  If it's a Wookiee unit, attack with it.  It gets +2/+0 for this attack]."
# A cross-decider two-stage decision (the opponent_chooses_target SHD_246 decider-
# shift precedent): stage "mode" is decided by the OPPONENT, stage "ready" (only for
# the second mode) by the CONTROLLER.  push_modal is controller-only and its modes
# don't chain a granted attack, so this is its own decision kind.


# ── Reveal-top "discard any, reorder the rest on top" (For a Cause I Believe In,
#    SOR_152) ───────────────────────────────────────────────────────────────────
#
# After the reveal damage is dealt up front (see push_reveal_top_discard_reorder),
# the controller resolves the revealed top-N cards one at a time: DiscardRevealed
# sends a card to the discard pile; KeepRevealed marks it to be put back on top.
# The order of KeepRevealed calls is the resulting top order (first kept = top).
# When every revealed card has been resolved the kept cards are reordered to the
# top of the deck and the decision pops.


# ── Reveal-until-stop, damage equal to the combined cost (Don't Get Cocky,
#    SOR_223) ────────────────────────────────────────────────────────────────
#
# "Choose a unit.  One at a time, reveal cards from your deck until you choose to
# stop or have revealed ``max_reveals`` cards.  If the combined cost of the
# revealed cards is ``threshold`` or less, deal that much damage to the chosen
# unit.  Put the revealed cards on the bottom of your deck in a random order."
# A push-your-luck loop: RevealNextCard reveals the next top card (adding its cost
# to a running tally shown to the deciding player); StopRevealing (or hitting the
# cap / exhausting the deck) finishes.  On finish the tallied damage is dealt
# (pop-then-deal) only when the tally is within ``threshold``, then every revealed
# card is bottomed in a seeded-random order (the deck_search bottoming convention).


# ── Repeated-modal "discard up to N, a different option per card" ──────────────
#
# Poe Dameron (SHD_153): "On Attack: Discard up to 3 cards from your hand. For
# each card discarded this way, choose a different option: Deal 2 damage to a
# unit or base / Defeat an upgrade / An opponent discards a card."  One
# 'repeated_modal' decision drives three stages (see push_repeated_modal):
#   * stage "discard"       — DiscardForModal(card_id) discards a hand card (up to
#                             the cap = min(max_discards, #modes)); FinishModalDiscard
#                             stops early (the "up to" lets the controller take fewer).
#   * stage "choose_mode"   — ChooseRepeatedMode(mode) picks one not-yet-used
#                             option; a targeted mode advances to "choose_target",
#                             a no-target one is recorded immediately.
#   * stage "choose_target" — ChooseRepeatedTarget(target_id) records the target.
# Choices are RECORDED into ctx["plan"], not applied, until one option per discard
# has been chosen; then the decision is popped and the planned effects are applied
# in order — so a defeat/damage trigger lands on a clean stack (mirroring
# push_distribute_damage's "pop, then deal" gotcha).


# ── Sacrifice-a-resource as an optional cost ──────────────────────────────────
#
# Wrecker (SHD_154): "When Played: You may defeat a friendly resource. If you do,
# deal 5 damage to a ground unit."  One 'sacrifice_resource' decision drives two
# stages (see push_sacrifice_resource_for_damage):
#   * stage "decide" — SacrificeResource(resource_id) defeats one of the
#                      controller's resources and advances to the damage target;
#                      DeclineSacrifice() pops the decision and does nothing ("may").
#   * stage "target" — ChooseSacrificeTarget(target_id) deals the stored damage to
#                      the chosen unit and pops.
# The damage is dealt AFTER the decision pops (the "pop, then deal" gotcha shared
# with push_distribute_damage / push_repeated_modal) so a defeat trigger lands on
# a clean stack.  The decision is only pushed when the controller has ≥1 resource
# AND ≥1 legal damage target (sacrificing for nothing is never offered).


# ── Reveal a resource, name-match a friendly unique unit, return it + ramp ─────
#
# Hunter (SHD_9): both the undeployed "Action [1 resource, Exhaust]" and the
# deployed "On Attack: You may …" read the same text — "Reveal a resource you
# control. If it shares a name with a friendly unique unit, return the resource to
# its owner's hand and put the top card of your deck into play as a resource."
# One single-stage 'reveal_resource_ramp' decision drives it: the controller picks
# which matching resource to reveal (RevealResourceForRamp), which returns that
# resource to its owner's hand and ramps the controller's deck top; or declines
# (DeclineRevealResource, offered only on the optional "may" side).  Only resources
# that actually name-match a friendly unique unit are offered as candidates (a
# non-matching reveal accomplishes nothing), and the decision is pushed only when
# ≥1 such candidate exists — so it is never a dead choice.  No change to core
# resolution or the trigger machinery: a self-contained decision kind, like
# sacrifice_resource / opponent_chooses_target.


# ── New primitive: opponent-chooses-target (Grey Squadron Y-Wing SHD_246) ─────
#
# Grey Squadron Y-Wing (SHD_246): "On Attack: An opponent chooses a unit or base
# they control. You may deal 2 damage to it."  One 'opponent_chooses_target'
# decision drives two stages whose *deciding player differs* (the say_no SOR_233
# precedent of handing a decision to the opponent):
#   * stage "choose"  — the OPPONENT picks one of their own units or base via
#                       ChooseOwnTarget(target_id).  Mandatory (always ≥1: a base
#                       is always present), so no decline is offered.
#   * stage "confirm" — control returns to the source's controller, who MAY deal
#                       the stored damage via ConfirmOpponentDamage(), or pass it
#                       up with DeclineOpponentDamage() ("you may").
# The damage is dealt AFTER the decision pops (the "pop, then deal" gotcha shared
# with push_distribute_damage / push_sacrifice_resource_for_damage) so a defeat
# trigger lands on a clean stack.  This adds no change to core resolution or the
# trigger machinery — only a new self-contained decision kind that shifts the
# deciding player between its two stages, exactly as say_no does.


# ── New primitive: each-player-defeats-a-unit (Merciless Contest TWI_238) ─────
#
# "Each player chooses a non-leader unit they control. Defeat those units."  One
# 'each_player_defeats' decision walks the players in turn (the source's
# controller first, then the opponent), each choosing one of their OWN matching
# units via ChooseUnitToDefeat — a per-stage deciding-player shift (the say_no
# SOR_233 / opponent_chooses_target SHD_246 precedent).  A player with no eligible
# unit is skipped; if neither has one the decision is never pushed (the event
# fizzles).  After every eligible player has chosen, the decision pops and the
# chosen units are defeated together (the "pop, then defeat" gotcha shared with
# push_distribute_damage) so a WhenDefeated trigger lands on a clean stack.  This
# adds no change to core resolution or the trigger machinery — only a new
# self-contained decision kind that shifts the deciding player per stage.


# ── Opponent chooses one of their own non-leader units to be captured by the
#    source, or declines (then the source readies) — Grand Admiral Thrawn
#    SEC_193 WhenPlayed ──────────────────────────────────────────────────────
#
# "An opponent may choose a non-leader unit they control.  If they do, this unit
# captures that unit.  If they don't, ready this unit."  A self-contained
# 'capture_or_ready' decision decided by the OPPONENT (the deciding-player shift of
# each_player_defeats TWI_238 / opponent_chooses_target SHD_246), whose payoff is
# capture-or-ready rather than defeat/damage, and which the opponent may decline.
# The capture / ready happens after the decision pops (the "pop, then act" gotcha —
# a clean stack).  Pushed only when the opponent has ≥1 non-leader unit; with none
# they "can't choose" so "they don't" ⇒ the source readies inline (no decision).


# ── Opponent may discard a random card, else the controller gets an effect
#    (Political Pressure TWI_222) ──────────────────────────────────────────────
#
# "Choose an opponent. They may discard a random card from their hand. If they
# don't, create 2 Battle Droid tokens."  A self-contained 'may_discard' decision
# handed to the OPPONENT (the say_no SOR_233 deciding-player-shift precedent): the
# opponent either discards a random card (RNG-chosen — the text says "random") to
# prevent the else-effect, or declines, in which case the source's controller gets
# the else-effect (create N token units).  See push_may_discard_else_tokens.


# ── Exhaust any number of friendly units, deal base damage per unit exhausted
#    (The Invisible Hand TWI_234 On Attack) ───────────────────────────────────
#
# "Exhaust any number of friendly Separatist units. Deal 1 damage to the
# defending player's base for each unit exhausted this way."  A self-contained
# multi-select decision (the Medal Ceremony SOR_245 select_token "any number"
# shape, but exhausting instead of token-giving, with a scaling base-damage
# payoff): the controller picks ready friendly units matching the trait filter one
# at a time, each exhausted as it is chosen (so it falls out of the eligible set),
# or finishes early ("any number" includes 0).  On finish the decision pops and
# ``damage_per`` × (units exhausted) is dealt to the recorded defending base (the
# "pop, then deal" gotcha so a base-defeat trigger lands on a clean stack).


# ── Exhaust any number of units with combined cost ≤ N (Qui-Gon Jinn's Lightsaber
#    LOF_201) ───────────────────────────────────────────────────────────────────
#
# "You may exhaust any number of units with combined cost 6 or less."  A
# self-contained multi-select decision (the Invisible Hand TWI_234 select-shape,
# but budget-bounded instead of trait-filtered, with NO payoff and no
# friendly/enemy restriction — the controller points it at enemy units).  Each
# pick exhausts the unit inline and spends its printed cost against the budget; a
# unit is eligible only while it is ready and its printed cost ≤ the remaining
# budget.  "Any number" includes 0 — FinishExhaustCombined is always offered.


# ── Capture any number of enemy non-leader units with combined remaining HP ≤ N
#    (Dismantle the Conspiracy SEC_106) ─────────────────────────────────────────
#
# "A friendly unit captures any number of enemy non-leader units with a total of
# 7 or less remaining HP."  The exhaust_combined_cost select-shape, but the weight
# is each candidate's *remaining* HP and the pick captures the unit (under the
# pre-chosen friendly captor) instead of exhausting it.  A unit is eligible only
# while it is an enemy non-leader whose remaining HP ≤ the remaining budget.  "Any
# number" includes 0 — FinishCaptureCombined is always offered.


# ── Multi-capture pairing: choose any number of friendly units, each captures an
#    enemy non-leader unit in the same arena (Finalizer SHD_92) ──────────────────
#
# "When Played: Choose any number of friendly units.  Each of those units captures
# an enemy non-leader unit in the same arena."  A single-phase pair-selection
# decision: each step picks a (captor, prey) PAIR — a friendly unit not yet used as
# a captor and an enemy non-leader in its arena not yet captured — and captures the
# prey under the captor inline.  Each friendly unit captures at most one enemy (a
# used captor drops out); each enemy is captured once (a used prey drops out).  "Any
# number" includes 0, so FinishMultiCapture is always offered while up; the decision
# auto-resolves once no legal pair remains.


# ── Choose any number of friendly units, play a unit free up to their combined
#    power, then defeat the chosen ones (Consolidation of Power TWI_89) ─────────
#
# A select-any-number loop (the multi_capture_pairing shape) whose payoff is a
# DYNAMIC cap: the combined effective power of the chosen units becomes the
# ``cost_max`` of a free ``play_from_hand``.  The chosen units are defeated AFTER
# that play — threaded through the play decision's new ``then_defeat_ids`` — so a
# unit's power still counts while it is being spent, which is the whole trade.


# ── Pay up to N resources, give that many Experience tokens to this unit
#    (Curious Flock LOF_255) ─────────────────────────────────────────────────────
#
# "When Played: Pay up to 6 resources.  For each resource paid this way, give an
# Experience token to this unit."  A self-contained "pay any number up to N"
# decision: the controller repeatedly pays one ready resource (resources are
# fungible — no target choice), each payment exhausting a resource AND giving one
# Experience token to the source unit INLINE (an Experience token never triggers a
# defeat, so there is no "pop, then act" concern).  "Up to" includes 0, so a
# FinishPayResources is always offered.  The decision auto-resolves once the cap is
# reached or no ready resource remains.


# ── Count Dooku TWI_138 — per-exploited-unit optional damage ──────────────────
#
# "When Played: For each unit you exploited while playing this card, you may deal
# damage to an enemy unit equal to the power of the exploited unit."
#
# A self-contained "per_exploit_damage" decision: one chunk per exploited unit,
# each carrying a fixed damage amount (that unit's power, snapshotted at sacrifice
# time and threaded through the play event_ctx).  For each chunk in order, the
# controller may deal it to ONE enemy unit (``DealExploitDamage``) or skip it
# (``DeclineExploitDamage`` — the "you may").  Target choices are RECORDED into a
# plan while the decision walks the chunks (no damage dealt during choosing, so
# the board — and thus the enemy-target set — is static); once every chunk is
# decided the decision pops and all planned damage is dealt in order.  This
# "record, then pop, then deal" shape (cf. each_player_defeats / repeated_modal)
# keeps any defeat trigger off the stack until the decision is gone and avoids any
# mid-decision re-push on a dirty stack.


# ── New primitive: reveal-a-deck-top, a chosen player plays it free, a different
#    player makes Credits = its cost (Vermillion LAW_215) ─────────────────────
#
# "When Attack Ends: If this unit survived, reveal the top card of a deck, then
# choose a player.  They may play the revealed card for free.  If they do, a
# different player creates Credit tokens equal to that card's cost."
#
# One 'reveal_play_credit' decision drives up to four stages with a mid-sequence
# decider shift (the say_no SOR_233 / opponent_chooses_target SHD_246 precedent):
#   * "choose_deck"   — the source's controller picks which player's deck to
#                       reveal the top card of (ChooseRevealDeck), among the
#                       non-empty decks.
#   * "choose_player" — the controller picks the player who *may* play the
#                       revealed card (ChooseRevealPlayer); control shifts to that
#                       player.
#   * "may_play"      — the chosen player plays the card for free
#                       (PlayRevealedCard, offered only when it is playable) or
#                       declines (DeclineRevealedCard — the card stays on top of
#                       its deck).
#   * "choose_host"   — only when the revealed card is an Upgrade and it is being
#                       played: the chosen player picks a legal host
#                       (ChooseRevealHost).
# When the card is played, the OTHER player (the one who did not play it) creates
# Credit tokens equal to its printed cost.  The played card is removed from the
# revealed deck and played under the chosen player's *control* (its owner_id is
# unchanged — control is implicit in this engine, the Stolen Landspeeder SHD_161
# convention), for free (cost 0), routed through the normal play paths so its
# own keyword / When Played abilities fire.  See push_reveal_play_credit.


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───
#
# Medal Ceremony (SOR_245): "Give an Experience token to each of up to 3 REBEL
# units that attacked this phase."  A single 'select_token' decision lets the
# controller pick *distinct* units one at a time (SelectTokenTarget) up to the
# cap, or stop early (FinishSelectToken — the "up to").  A token is given the
# moment a unit is chosen (tokens are independent, so selection order is
# irrelevant); a chosen unit is excluded from later picks so a unit cannot be
# selected twice.  The eligible set is recomputed each step from the stored spec
# criteria via the resolver's target matcher, so the same predicate machinery
# ("attacked_this_phase", trait/controller filters) governs eligibility.  This
# adds no change to core resolution or the trigger machinery — only a new
# self-contained decision kind (the deck_search "select up to N" pattern, but
# over in-play units).


@dataclass
class DeployLeader(Action):
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        leader_ci = ps.leader_instance
        if leader_ci is None:
            raise IllegalActionError("No leader to deploy")
        if leader_ci.deployed:
            raise IllegalActionError("Leader already deployed")
        if leader_ci.epic_action_spent:
            raise IllegalActionError("Leader epic action already spent")
        if not _leader_deploy_allowed(s, ps, leader_ci):
            raise IllegalActionError(
                "Leader's deploy condition is not met (or is unsupported)")
        s = _deploy_leader_into_arena(s, ps, leader_ci)
        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return "Deploy leader (epic action)"


def attach_leader_as_pilot_upgrade(
    s: GameState, ps, leader_ci: CardInstance, host: CardInstance
) -> GameState:
    """Move an undeployed leader out of the base zone and onto ``host`` as a Pilot
    upgrade, firing ``LeaderDeployed`` with ``via_pilot_leader``.

    The shared body of the two ways a leader becomes a Pilot: the Epic Action
    (``DeployLeaderAsUpgrade``, Boba Fett JTL_9) and a printed Action that flips
    him straight onto a Vehicle for a smaller price (Poe Dameron JTL_13).  The
    caller owns the legality checks and whatever follows (Plot, turn hand-over)."""
    ps.base_zone.remove(leader_ci)
    leader_ci.deployed = True
    leader_ci.epic_action_spent = True
    # The leader-upgrade enters ready (its own exhaust flag drives its "you may
    # exhaust this leader" ability); it is not the host's exhaust state.
    leader_ci.exhausted = False
    leader_ci.face_down = False
    leader_ci.zone = host.zone
    host.attached_upgrades.append(leader_ci)

    deploy_evt = LeaderDeployed(
        player_id=ps.player_id,
        instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name,
        arena=host.arena() or "Ground",
    )
    s.event_log.append(deploy_evt)
    get_bus().fire(s, deploy_evt)
    from swu.abilities.resolver import fire_triggered_abilities
    after_idx = 1 - s.active_player_index
    return fire_triggered_abilities(
        s, deploy_evt, after_all_player_idx=after_idx,
        event_ctx={"via_pilot_leader": True,
                   "attached_to_id": host.instance_id})


@dataclass
class DeployLeaderAsUpgrade(Action):
    """Epic Action: deploy this leader as an upgrade on a friendly Vehicle unit.

    The second option of Boba Fett JTL_9's Epic Action ("Deploy this leader as an
    upgrade on a friendly Vehicle unit without a Pilot on it").  The leader is
    attached to the host as a Pilot upgrade — it leaves base_zone, is marked
    ``deployed`` and ``epic_action_spent``, and contributes its ``upgrade_power`` /
    ``upgrade_hp`` to the host (read by ``compute_power`` / ``compute_hp``, like any
    pilot).  A ``LeaderDeployed`` event fires with ``via_pilot_leader=True`` in the
    event context, so the leader's ``WhenDeployed(via_pilot_leader=True)`` ability
    ("When deployed as an upgrade: …") fires, while a normal deploy (which does not
    set the flag) does not.
    """
    vehicle_target_id: str

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        leader_ci = ps.leader_instance
        if leader_ci is None:
            raise IllegalActionError("No leader to deploy")
        if leader_ci.deployed:
            raise IllegalActionError("Leader already deployed")
        if leader_ci.epic_action_spent:
            raise IllegalActionError("Leader epic action already spent")
        if not _leader_can_deploy_as_upgrade(leader_ci.card_def):
            raise IllegalActionError("Leader cannot deploy as an upgrade")
        if not _leader_deploy_allowed(s, ps, leader_ci):
            raise IllegalActionError("Need enough resources to deploy")
        host = _find_in_arenas(ps, self.vehicle_target_id)
        if host is None or host not in _eligible_leader_upgrade_targets(s, ps):
            raise IllegalActionError(
                f"{self.vehicle_target_id} is not an eligible Vehicle host")

        s = attach_leader_as_pilot_upgrade(s, ps, leader_ci, host)
        # Plot: deploying a leader (in any mode) is still a leader deploy, so offer
        # any Plot resources (mirrors DeployLeader).
        ps = s.active_player
        plot_ids = [] if s.is_terminal() else _plot_eligible_resource_ids(s, ps)
        if plot_ids and _plot_play_actions(s, ps, set(plot_ids)):
            s.pending_decisions.append(PendingDecision(
                deciding_player_id=ps.player_id,
                kind="plot",
                context={"plot_ids": plot_ids},
                after_resolve_player_index=1 - s.active_player_index,
            ))
            s.event_log.append(DecisionPushed(
                deciding_player_id=ps.player_id,
                kind="plot",
            ))
        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"Deploy leader as upgrade on {self.vehicle_target_id}"


# ── Decision-resolving actions ────────────────────────────────────────────────


@dataclass
class AnswerTestDecision(Action):
    """Resolve a 'test' pending decision — only used in unit tests."""
    choice: str

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "test":
            raise IllegalActionError("No pending test decision")
        s = copy.deepcopy(state)
        top_d = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top_d.deciding_player_id,
            kind="test",
            choice=self.choice,
        ))
        s.active_player_index = top_d.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Answer test decision: {self.choice}"


# ── Phase 3 decision-resolving actions ───────────────────────────────────────


@dataclass
class ChooseTarget(Action):
    """Choose a target for the current effect in a resolve_effects decision."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "resolve_effects":
            raise IllegalActionError("No pending resolve_effects decision")
        from swu.abilities.resolver import apply_resolve_effects
        return apply_resolve_effects(state, self.target_id)

    def describe(self) -> str:
        return f"Choose target {self.target_id}"


@dataclass
class DeclineTarget(Action):
    """Decline an optional target choice in a resolve_effects decision."""
    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "resolve_effects":
            raise IllegalActionError("No pending resolve_effects decision")
        top = state.pending_decisions[-1]
        # Advance past the current optional effect
        ctx = top.context
        s = copy.deepcopy(state)
        ctx2 = s.pending_decisions[-1].context
        ctx2["effect_idx"] = ctx["effect_idx"] + 1
        from swu.abilities.resolver import apply_resolve_effects
        return apply_resolve_effects(s, None)

    def describe(self) -> str:
        return "Decline optional target"


@dataclass
class AutoResolveEffects(Action):
    """Auto-advance through all remaining auto-resolvable effects in a resolve_effects decision."""
    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "resolve_effects":
            raise IllegalActionError("No pending resolve_effects decision")
        from swu.abilities.resolver import apply_resolve_effects
        return apply_resolve_effects(state, None)

    def describe(self) -> str:
        return "Auto-resolve effects"


@dataclass
class AttackWithLeader(Action):
    """Use the undeployed leader's leader-unit-side to attack the opponent's base.

    The leader exhausts and deals leader_power damage.  Only legal when the
    leader is in base_zone (not deployed) and not exhausted.
    """
    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        inactive_ps = s.inactive_player
        leader_ci = ps.leader_instance
        if leader_ci is None or leader_ci.deployed:
            raise IllegalActionError("No undeployed leader to attack with")
        if leader_ci.exhausted:
            raise IllegalActionError("Leader is exhausted")
        if leader_ci.zone != Zone.BASE_ZONE:
            raise IllegalActionError("Leader is not in base zone")
        from swu.cards.models import Leader as LeaderModel
        if not isinstance(leader_ci.card_def, LeaderModel):
            raise IllegalActionError("Not a leader")
        leader_power = leader_ci.card_def.leader_power
        base_ci = inactive_ps.base_instance
        if base_ci is None:
            raise IllegalActionError("Opponent has no base")

        leader_ci.exhausted = True
        s.event_log.append(AttackDeclared(
            attacker_player_id=ps.player_id,
            attacker_instance_id=leader_ci.instance_id,
            attacker_name=leader_ci.card_def.display_name,
            defender_instance_id=None,
            defender_name=base_ci.card_def.display_name,
        ))
        leader_power = base_damage_after_prevention(s, base_ci, leader_power)
        if leader_power > 0:
            base_ci.damage += leader_power
            s.event_log.append(DamageDealt(
                target_instance_id=base_ci.instance_id,
                target_name=base_ci.card_def.display_name,
                owner_id=inactive_ps.player_id,
                amount=leader_power,
                is_base=True,
            ))
        _check_game_over(s)
        if not s.is_terminal():
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return "Attack base with leader unit"


@dataclass
class UseAbility(Action):
    """Use an activated ability from a card in play.

    ability_idx identifies which ActivatedAbility spec on the card to use.

    ``source_id`` addresses the card whose REGISTRY holds the spec, which is not
    always the card the ability acts as.  Three shapes:

    - plain — the source is also the actor (a unit/base/leader's own Action).
    - upgrade-granted (Heroic Resolve SHD_155) — the source is the UPGRADE and the
      actor is its single host, found by ``_find_upgrade_host``.
    - aura-granted (Satine Kryze TWI_47: "Each unit (including enemy units) gains:
      'Action [Exhaust]: …'") — ONE source grants to MANY units, so the host cannot
      be derived from the source.  ``actor_id`` names the unit using the ability;
      the ownership guard, the costs and the effect source all key on it, and the
      source is a spec address only (it may belong to the opponent).
    """
    source_id: str
    ability_idx: int
    actor_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        active_ps = s.active_player

        source_result = s.find_instance(self.source_id)
        if source_result is None:
            raise IllegalActionError(f"Source {self.source_id} not found")
        source_ps, source_ci = source_result

        from swu.abilities.registry import (
            get_abilities, ActivatedAbility, ExhaustSelf, PayResources, DefeatSelf,
            UseForce, DiscardCardCost, DefeatCreditCost, GrantedAbility, AuraGrantedAbility)
        specs = get_abilities(
            source_ci.card_def.set_code or "",
            source_ci.card_def.card_number or "",
        )
        if self.ability_idx >= len(specs):
            raise IllegalActionError("Ability index out of range")
        ability = specs[self.ability_idx]

        # An AURA-granted activated ability (Satine Kryze TWI_47): ``source_id`` is
        # only the spec's address — it may be an ENEMY card — and ``actor_id`` names
        # the unit that gained the ability and is using it now.  A unit's abilities
        # belong to whoever controls it, so the ownership guard checks the ACTOR, and
        # the aura's target is re-checked here (the board may have moved since the
        # action was enumerated).
        aura_actor: Optional[CardInstance] = None
        if self.actor_id is not None:
            if not isinstance(ability, AuraGrantedAbility):
                raise IllegalActionError("Ability is not aura-granted")
            actor_result = s.find_instance(self.actor_id)
            if actor_result is None:
                raise IllegalActionError(f"Actor {self.actor_id} not found")
            aura_actor_ps, aura_actor = actor_result
            if aura_actor_ps.player_id != active_ps.player_id:
                raise IllegalActionError("Cannot use opponent's ability")
            from swu.abilities.resolver import _spec_matches_ci
            if not _spec_matches_ci(ability.target, aura_actor, source_ci, s, {}):
                raise IllegalActionError("Actor does not match the aura's target")
            ability = ability.ability
        else:
            # Ownership guard, lifted for an "Any player may use this ability" spec
            # (Mercenary Gunship SHD_256) — the enumeration offers such an ability to
            # the opponent too, and its costs are paid by the player using it below.
            _any_player = getattr(
                ability.ability if isinstance(ability, GrantedAbility) else ability,
                "any_player", False)
            if source_ci.owner_id != active_ps.player_id and not _any_player:
                raise IllegalActionError("Cannot use opponent's ability")

        # A granted activated ability: an attached upgrade (``source_ci``) confers
        # an Action on its host unit (Heroic Resolve SHD_155).  The Action resolves
        # FROM THE HOST, and a DefeatSelf cost defeats the UPGRADE, not the host.
        granted = False
        host_ci: Optional[CardInstance] = None
        if isinstance(ability, GrantedAbility) and isinstance(ability.ability, ActivatedAbility):
            granted = True
            host_ci = _find_upgrade_host(s, source_ci.instance_id)
            if host_ci is None:
                raise IllegalActionError("Granted ability's host not found")
            ability = ability.ability
        if not isinstance(ability, ActivatedAbility):
            raise IllegalActionError("Specified ability is not an ActivatedAbility")
        # The ability's source for gating/effects is the host when granted by an
        # upgrade, the acting unit when granted by an aura, else self.
        res_ci = host_ci if granted else (aura_actor if aura_actor is not None else source_ci)
        if ability.condition is not None and not ability.condition.evaluate(s, res_ci):
            raise IllegalActionError("Ability condition not met")
        # An aura grants the SAME spec to many units, so its once-per-round
        # allowance is per ACTOR (each unit that gained it has its own).
        used_key = (f"{self.actor_id}:{self.source_id}:{self.ability_idx}"
                    if aura_actor is not None
                    else f"{self.source_id}:{self.ability_idx}")
        if (ability.once_per_round
                and used_key in s.game_memory.activated_abilities_used_this_round):
            raise IllegalActionError("Ability already used this round")

        # Pay costs
        for cost in ability.costs:
            if isinstance(cost, ExhaustSelf):
                # "Exhaust this unit" targets the host for an upgrade-granted
                # ability and the acting unit for an aura-granted one.
                exh_ci = res_ci
                if exh_ci.exhausted:
                    raise IllegalActionError("Source already exhausted")
                exh_ci.exhausted = True
            elif isinstance(cost, PayResources):
                due = resource_cost_for(s, active_ps, cost.n)
                if active_ps.available_resources < due:
                    raise IllegalActionError(f"Insufficient resources: need {due}")
                _exhaust_resources(active_ps, due)
            elif isinstance(cost, DefeatSelf):
                if granted:
                    _defeat_attached_upgrade(s, source_ci)  # defeat THIS upgrade
                elif aura_actor is not None:
                    _defeat_unit(s, active_ps, aura_actor)  # defeat the ACTOR
                else:
                    _defeat_unit(s, source_ps, source_ci)
            elif isinstance(cost, UseForce):
                if not spend_force_token(s, active_ps):
                    raise IllegalActionError("No Force token to spend")
            elif isinstance(cost, DefeatCreditCost):
                # "Action [defeat a friendly Credit token]" (Hunter For Hire
                # LAW_156).  Credits are fungible, so no choice is made; the payer
                # is the ACTIVE player, which for an ``any_player`` ability is
                # whoever is using it (Mercenary Gunship SHD_256).
                want = int(getattr(cost, "count", 1) or 1)
                if len(active_ps.credits) < want:
                    raise IllegalActionError("Not enough Credit tokens to defeat")
                for _ in range(want):
                    _defeat_credit(s, active_ps)
            elif isinstance(cost, DiscardCardCost):
                if not _discard_cost_payable(active_ps, cost):
                    raise IllegalActionError("No qualifying card in hand to discard")
                for _ in range(int(getattr(cost, "count", 1) or 1)):
                    dc = _discard_cost_candidates(active_ps, cost)[0]
                    active_ps.hand.remove(dc)
                    dc.zone = Zone.DISCARD
                    active_ps.discard.append(dc)
                    note_hand_or_deck_discard(s, dc)
                    record_hand_discard(s, active_ps.player_id)

        # Mark epic if applicable
        if ability.epic:
            s.game_memory.epic_actions_spent.add(self.source_id)
        # Mark once-per-round usage (MagnaGuard Wing Leader TWI_82)
        if ability.once_per_round:
            s.game_memory.activated_abilities_used_this_round.add(used_key)
        # Per-GAME use tally, keyed by the source card (Mystic Monastery LOF_22's
        # "no more than 3 times each game", read by SOURCE_ABILITY_USES_MAX).  Kept
        # for every activated ability so the ledger needs no per-card opt-in.
        s.game_memory.activated_ability_use_counts[self.source_id] = (
            s.game_memory.activated_ability_use_counts.get(self.source_id, 0) + 1)

        # Build resolution context and push effects.  "Take an extra action after
        # this one" (Kazuda Xiono JTL_18) keeps the seat instead of handing it
        # over — here for the deferred path (whoever is active once the decision
        # pops) and below for the inline one.
        after_idx = (s.active_player_index if getattr(ability, "extra_action", False)
                     else 1 - s.active_player_index)
        from swu.abilities.resolver import _ability_can_inline, _resolve_inline

        # Construct a TriggerAbility wrapper to reuse inline resolution logic.  The
        # effect resolves from the host for a granted ability (``res_ci``), so
        # "attack with this unit" / SELF references point at the host.
        from swu.abilities.registry import TriggerAbility
        trigger_wrapper = TriggerAbility(trigger=None, effects=ability.effects, optional=False)

        # The player USING the ability — normally the source's controller, but for an
        # "Any player may use this ability" spec (Mercenary Gunship SHD_256) it may be
        # the opponent, and the effect ("Take control of this unit") needs to know who.
        event_ctx: dict = {"ability_user_id": active_ps.player_id}
        if _ability_can_inline(trigger_wrapper, s, res_ci, event_ctx):
            s = _resolve_inline(s, trigger_wrapper, res_ci, event_ctx)
            # An inline effect may itself push a decision (e.g. Admiral Ozzel's
            # CustomEffect pushes a 'play_from_hand' decision).  Only hand the
            # turn over when the ability fully resolved with no decision pending —
            # and not at all for an ``extra_action`` ability (JTL_18).
            if (not s.is_terminal() and not s.pending_decisions
                    and not getattr(ability, "extra_action", False)):
                _switch_active_player(s)
        else:
            # Deferred path: address the spec by the card whose registry holds it
            # (the UPGRADE for a granted ability — ``self.source_id``) and resolve
            # from the host (``res_ci``).  ``unwrap_granted`` at the resolve site
            # yields the inner ActivatedAbility's effects.
            dec = PendingDecision(
                deciding_player_id=active_ps.player_id,
                kind="resolve_effects",
                context={
                    "set_code": source_ci.card_def.set_code or "",
                    "card_number": source_ci.card_def.card_number or "",
                    "ability_idx": self.ability_idx,
                    "source_id": res_ci.instance_id,
                    "effect_idx": 0,
                    "resolved_targets": {},
                    "event_ctx": event_ctx,
                    "after_all_player_idx": after_idx,
                },
                after_resolve_player_index=after_idx,
            )
            s.pending_decisions.append(dec)
            s.event_log.append(DecisionPushed(
                deciding_player_id=active_ps.player_id,
                kind="resolve_effects",
            ))
        return s

    def describe(self) -> str:
        # The actor must appear for an aura grant: one source offers the SAME
        # (source_id, ability_idx) once per unit, and the web/replay layers
        # disambiguate same-kind actions by describe().
        if self.actor_id is not None:
            return (f"Use ability {self.ability_idx} of {self.source_id} "
                    f"with {self.actor_id}")
        return f"Use ability {self.ability_idx} of {self.source_id}"


# ── legal_actions ─────────────────────────────────────────────────────────────

def legal_actions(state: GameState) -> list[Action]:
    """Return every action the active player may legally take right now.

    If a pending decision is on the stack, returns only that decision's
    options for the deciding player.  Turn alternation is suspended until
    the stack empties.

    Never returns an empty list while the game is live.
    """
    if state.is_terminal():
        return []

    # Pending decision takes priority over normal turn actions
    if state.pending_decisions:
        return _decision_legal_actions(state)

    phase = state.phase

    if phase == Phase.SETUP_MULLIGAN:
        # "You can't take a mulligan" (Nabat Village JTL_28) drops the redraw for
        # that player only — keeping is always legal, so they are never stuck.
        if _mulligan_forbidden(state.active_player):
            return [KeepHand()]
        return [KeepHand(), TakeMultiligan()]

    if phase == Phase.SETUP_RESOURCES:
        ps = state.active_player
        return [ResourceCard(ci.instance_id) for ci in ps.hand]

    if phase == Phase.REGROUP:
        ps = state.active_player
        acts: list[Action] = [ResourceCard(ci.instance_id) for ci in ps.hand]
        acts.append(SkipResource())
        return acts

    # ACTION phase
    ps = state.active_player
    inactive_ps = state.inactive_player

    # Give In to Your Anger SHD_144: while a forced-attack compulsion names this
    # player's able unit, their next action MUST be that unit's attack (a unit
    # target if any).  Returns None (no restriction) when the compulsion is vacuous.
    forced = _forced_attack_actions(state)
    if forced is not None:
        return forced

    acts = []

    # Play cards from hand
    for ci in ps.hand:
        card = ci.card_def
        # Regional Governor SOR_62: an enemy namer forbids playing the named card.
        if _named_card_play_forbidden(state, ci, ps):
            continue
        # "This card can't be played from your hand" (One in a Million SEC_53) —
        # a printed CannotPlayFromHand marker.  Only the HAND enumeration is
        # skipped, so the card is still playable from the resource zone via Plot
        # (which is the whole point of the restriction).
        if _cannot_play_from_hand(ci):
            continue
        # "They can't play events for this phase" (Trade Route Taxation SEC_126).
        if _events_locked(state, ci, ps):
            continue
        # "Play only as your first action in the action phase" (SEC_145).
        if _play_only_as_first_action_blocked(state, ci, ps):
            continue
        if isinstance(card, (Unit, Event)):
            cost = _play_cost(state, ci, ps)
            # For Exploit cards: check affordability at best-case (max sacrifices)
            if has_keyword(state, ci, Keyword.EXPLOIT):
                exploit_n = keyword_value(state, ci, Keyword.EXPLOIT)
                max_units = len(ps.ground_arena) + len(ps.space_arena)
                max_sacrifices = min(exploit_n, max_units)
                min_cost = max(0, cost - 2 * max_sacrifices)
                if ps.available_resources >= min_cost:
                    acts.append(PlayCard(ci.instance_id))
            elif _affordable_with_credits(ps, cost, state):
                acts.append(PlayCard(ci.instance_id))
        elif isinstance(card, Upgrade):
            # Cost can depend on the chosen host (Grievous's Wheel Bike TWI_236
            # "costs 2 less on General Grievous"), so check affordability per host.
            for target in _eligible_upgrade_targets(state, ci):
                cost = _play_cost(state, ci, ps, target_host_id=target.instance_id)
                if _affordable_with_credits(ps, cost, state):
                    acts.append(PlayCard(ci.instance_id, target.instance_id))

    # Smuggle: play a card from your own resource zone (Smuggle keyword)
    acts.extend(_enumerate_smuggle_plays(state, ps))

    # Piloting: play a hand Unit as a Pilot upgrade on a friendly Vehicle
    acts.extend(_enumerate_pilot_plays(state, ps))

    # Play a card from your own DISCARD pile (PlayFromDiscardAction — Brutal
    # Traditions SHD_38: an Action that replays the card from discard, gated).
    acts.extend(_enumerate_discard_play_actions(state, ps))

    # Attack with ready units (Sentinel-aware targeting)
    acts.extend(_enumerate_attacks(state, ps, inactive_ps))

    # Attack two units at once (Darth Maul C24_6 — MultiDefenderAttack marker)
    acts.extend(_enumerate_two_unit_attacks(state, ps, inactive_ps))

    # Deploy leader (epic action)
    leader_ci = ps.leader_instance
    if (
        leader_ci is not None
        and not leader_ci.deployed
        and not leader_ci.epic_action_spent
    ):
        if _leader_deploy_allowed(state, ps, leader_ci):
            acts.append(DeployLeader())
            # Boba Fett JTL_9: the same Epic Action may instead deploy the leader as
            # an upgrade on a friendly Vehicle unit without a Pilot on it.
            if _leader_can_deploy_as_upgrade(leader_ci.card_def):
                for host in _eligible_leader_upgrade_targets(state, ps):
                    acts.append(DeployLeaderAsUpgrade(host.instance_id))

    # Attack with undeployed leader (leader unit side)
    if (
        leader_ci is not None
        and not leader_ci.deployed
        and not leader_ci.exhausted
        and leader_ci.zone == Zone.BASE_ZONE
        and isinstance(leader_ci.card_def, Leader)
        and leader_ci.card_def.leader_power > 0
    ):
        acts.append(AttackWithLeader())

    # UseAbility: activated abilities from units/leaders in play
    from swu.abilities.registry import (
        get_abilities, ActivatedAbility, ExhaustSelf, PayResources, UseForce, DiscardCardCost, DefeatCreditCost)
    for ci in ps.ground_arena + ps.space_arena:
        if ability_suppressed(state, ci):
            continue  # a suppressed (Mind Trick LOF_202) / Galen-named (P25_31) /
                      # Imprisoned (SHD_72) unit has no activated ability
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        is_leader_card = isinstance(ci.card_def, Leader)
        is_deployed_leader = is_leader_card and ci.deployed
        for idx, spec in enumerate(get_abilities(sc, cn)):
            if not isinstance(spec, ActivatedAbility):
                continue
            # Deployment-side gating for leader abilities.  ``undeployed_only`` is
            # meaningful only ON a leader: a TOKEN UNIT shares its (set, number) with
            # a real card (the Clone Trooper token is TWI_2, the same key as the
            # leader Nute Gunray), so without the leader check the token would offer
            # that leader's undeployed action from the arena.
            if spec.undeployed_only and (is_deployed_leader or not is_leader_card):
                continue
            if spec.deployed_only and not is_deployed_leader:
                continue
            # Once-per-game epic check
            if spec.epic and ci.instance_id in state.game_memory.epic_actions_spent:
                continue
            # Once-per-round check (MagnaGuard Wing Leader TWI_82)
            if (spec.once_per_round
                    and f"{ci.instance_id}:{idx}" in state.game_memory.activated_abilities_used_this_round):
                continue
            # Conditional availability (e.g. Vader's "if you played a Villainy card")
            if spec.condition is not None and not spec.condition.evaluate(state, ci):
                continue
            can_afford = True
            for cost in spec.costs:
                if isinstance(cost, ExhaustSelf) and ci.exhausted:
                    can_afford = False
                    break
                if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                    can_afford = False
                    break
                if isinstance(cost, UseForce) and not ps.has_force_token:
                    can_afford = False
                    break
                if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                    can_afford = False
                    break
                if (isinstance(cost, DefeatCreditCost)
                        and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                    can_afford = False
                    break
            if can_afford:
                acts.append(UseAbility(ci.instance_id, idx))

    # UseAbility: an "Any player may use this ability" activated ability on an ENEMY
    # unit (Mercenary Gunship SHD_256: "Action [4 resources]: Take control of this
    # unit.  Any player may use this ability").  The arena scan above only walks the
    # active player's own units, so such an ability would otherwise be unreachable
    # for the opponent — which is the whole point of the card.  Costs come from the
    # ACTIVE player's own resources (the payment site already uses active_ps), and
    # it is still an action, so it is only offered on the user's own turn.
    for ci in inactive_ps.ground_arena + inactive_ps.space_arena:
        if ability_suppressed(state, ci):
            continue
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        for idx, spec in enumerate(get_abilities(sc, cn)):
            if not isinstance(spec, ActivatedAbility) or not spec.any_player:
                continue
            if spec.epic and ci.instance_id in state.game_memory.epic_actions_spent:
                continue
            if (spec.once_per_round
                    and f"{ci.instance_id}:{idx}" in state.game_memory.activated_abilities_used_this_round):
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, ci):
                continue
            can_afford = True
            for cost in spec.costs:
                if isinstance(cost, ExhaustSelf) and ci.exhausted:
                    can_afford = False
                    break
                if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                    can_afford = False
                    break
                if isinstance(cost, UseForce) and not ps.has_force_token:
                    can_afford = False
                    break
                if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                    can_afford = False
                    break
                if (isinstance(cost, DefeatCreditCost)
                        and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                    can_afford = False
                    break
            if can_afford:
                acts.append(UseAbility(ci.instance_id, idx))

    # UseAbility: an activated ability GRANTED to a unit by an attached upgrade
    # (Heroic Resolve SHD_155: "Attached unit gains: 'Action [2 resources, defeat a
    # Heroic Resolve on this unit]: …'").  The spec lives on the UPGRADE, so the
    # arena scan above never sees it; here each host's attached_upgrades are scanned
    # for a GrantedAbility wrapping an ActivatedAbility.  The action is addressed by
    # the UPGRADE's instance_id; a DefeatSelf cost is always payable (you can defeat
    # your own upgrade), and ExhaustSelf refers to the host.
    from swu.abilities.registry import GrantedAbility
    for host in ps.ground_arena + ps.space_arena:
        if ability_suppressed(state, host):
            continue
        for upg in host.attached_upgrades:
            usc = getattr(upg.card_def, "set_code", None) or ""
            ucn = getattr(upg.card_def, "card_number", None) or ""
            for idx, spec in enumerate(get_abilities(usc, ucn)):
                if not isinstance(spec, GrantedAbility):
                    continue
                inner = spec.ability
                if not isinstance(inner, ActivatedAbility):
                    continue
                if inner.epic and upg.instance_id in state.game_memory.epic_actions_spent:
                    continue
                if (inner.once_per_round
                        and f"{upg.instance_id}:{idx}" in state.game_memory.activated_abilities_used_this_round):
                    continue
                if inner.condition is not None and not inner.condition.evaluate(state, host):
                    continue
                can_afford = True
                for cost in inner.costs:
                    if isinstance(cost, ExhaustSelf) and host.exhausted:
                        can_afford = False
                        break
                    if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                        can_afford = False
                        break
                    if isinstance(cost, UseForce) and not ps.has_force_token:
                        can_afford = False
                        break
                    if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                        can_afford = False
                        break
                    if (isinstance(cost, DefeatCreditCost)
                            and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                        can_afford = False
                        break
                if can_afford:
                    acts.append(UseAbility(upg.instance_id, idx))

    # UseAbility: an activated ability an in-play AURA source grants to every unit
    # matching its target (Satine Kryze TWI_47: "Each unit (including enemy units)
    # gains: 'Action [Exhaust]: …'").  The spec lives on the SOURCE, so neither the
    # arena scan nor the upgrade scan above reaches it — and unlike the upgrade case
    # one source serves MANY actors, so each offer names both.
    #
    # Only the active player's OWN units are offered: a unit's abilities are used by
    # whoever controls it, which is exactly why an enemy Satine arms your units too.
    # Sources are gathered once and the actor loop is skipped entirely when no aura
    # is in play (the overwhelmingly common case), so this costs nothing normally.
    from swu.abilities.registry import AuraGrantedAbility
    aura_grants: list = []          # (source_ci, ability_idx, inner ActivatedAbility, target)
    for owner_ps in state.players:
        for src in owner_ps.ground_arena + owner_ps.space_arena:
            if ability_suppressed(state, src):
                continue
            ssc = getattr(src.card_def, "set_code", None) or ""
            scn = getattr(src.card_def, "card_number", None) or ""
            for idx, spec in enumerate(get_abilities(ssc, scn)):
                if isinstance(spec, AuraGrantedAbility) and isinstance(
                        spec.ability, ActivatedAbility):
                    aura_grants.append((src, idx, spec.ability, spec.target))
    if aura_grants:
        from swu.abilities.resolver import _spec_matches_ci
        for actor in ps.ground_arena + ps.space_arena:
            if ability_suppressed(state, actor):
                continue  # a unit that "can't gain abilities" gains nothing
            for src, idx, inner, target in aura_grants:
                if not _spec_matches_ci(target, actor, src, state, {}):
                    continue
                if (inner.once_per_round
                        and f"{actor.instance_id}:{src.instance_id}:{idx}"
                        in state.game_memory.activated_abilities_used_this_round):
                    continue
                if inner.condition is not None and not inner.condition.evaluate(state, actor):
                    continue
                can_afford = True
                for cost in inner.costs:
                    if isinstance(cost, ExhaustSelf) and actor.exhausted:
                        can_afford = False
                        break
                    if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                        can_afford = False
                        break
                    if isinstance(cost, UseForce) and not ps.has_force_token:
                        can_afford = False
                        break
                    if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                        can_afford = False
                        break
                    if (isinstance(cost, DefeatCreditCost)
                            and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                        can_afford = False
                        break
                if can_afford:
                    acts.append(UseAbility(src.instance_id, idx,
                                           actor_id=actor.instance_id))

    # UseAbility: activated abilities on the player's base (e.g. Energy
    # Conversion Lab SOR_22's Epic Action). Bases live in base_zone, which the
    # arena loop above does not scan; the undeployed leader (also in base_zone)
    # is handled by its own loop below, so we restrict this to Base cards.
    for ci in ps.base_zone:
        if not isinstance(ci.card_def, Base):
            continue
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        for idx, spec in enumerate(get_abilities(sc, cn)):
            if not isinstance(spec, ActivatedAbility):
                continue
            if spec.epic and ci.instance_id in state.game_memory.epic_actions_spent:
                continue
            if (spec.once_per_round
                    and f"{ci.instance_id}:{idx}" in state.game_memory.activated_abilities_used_this_round):
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, ci):
                continue
            can_afford = True
            for cost in spec.costs:
                if isinstance(cost, ExhaustSelf) and ci.exhausted:
                    can_afford = False
                    break
                if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                    can_afford = False
                    break
                if isinstance(cost, UseForce) and not ps.has_force_token:
                    can_afford = False
                    break
                if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                    can_afford = False
                    break
                if (isinstance(cost, DefeatCreditCost)
                        and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                    can_afford = False
                    break
            if can_afford:
                acts.append(UseAbility(ci.instance_id, idx))

    # UseAbility for undeployed leader activated abilities
    if leader_ci is not None and not leader_ci.deployed:
        sc = getattr(leader_ci.card_def, "set_code", None) or ""
        cn = getattr(leader_ci.card_def, "card_number", None) or ""
        # "Each leader loses all abilities EXCEPT FOR EPIC ACTIONS" (Brain Invaders
        # TWI_255): this is the one seam offering an undeployed leader's own
        # actions, so the epic carve-out lives here.  (The deployed side is covered
        # by the arena scan's whole-card ability_suppressed guard above; a deployed
        # leader has already spent its Epic Action to get there.)
        leader_suppressed = ability_suppressed(state, leader_ci)
        for idx, spec in enumerate(get_abilities(sc, cn)):
            if not isinstance(spec, ActivatedAbility):
                continue
            if leader_suppressed and not spec.epic:
                continue
            if spec.deployed_only:  # deployed-only abilities not available undeployed
                continue
            if spec.epic and leader_ci.instance_id in state.game_memory.epic_actions_spent:
                continue
            if (spec.once_per_round
                    and f"{leader_ci.instance_id}:{idx}" in state.game_memory.activated_abilities_used_this_round):
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, leader_ci):
                continue
            can_afford = True
            for cost in spec.costs:
                if isinstance(cost, ExhaustSelf) and leader_ci.exhausted:
                    can_afford = False
                    break
                if isinstance(cost, PayResources) and ps.available_resources < resource_cost_for(state, ps, cost.n):
                    can_afford = False
                    break
                if isinstance(cost, UseForce) and not ps.has_force_token:
                    can_afford = False
                    break
                if isinstance(cost, DiscardCardCost) and not _discard_cost_payable(ps, cost):
                    can_afford = False
                    break
                if (isinstance(cost, DefeatCreditCost)
                        and len(ps.credits) < int(getattr(cost, "count", 1) or 1)):
                    can_afford = False
                    break
            if can_afford:
                acts.append(UseAbility(leader_ci.instance_id, idx))

    # Claim initiative (only if not yet claimed this round and not already passed)
    if (
        not state.initiative_claimed_this_round
        and state.active_player_index not in state.passed_players
    ):
        acts.append(ClaimInitiative())

    acts.append(Pass())
    return acts


# ── apply convenience wrapper ─────────────────────────────────────────────────

def apply(state: GameState, action: Action) -> GameState:
    """Apply action, raising IllegalActionError if it is not legal."""
    legal = legal_actions(state)
    if action not in legal:
        raise IllegalActionError(
            f"Action {action.describe()!r} is not legal. "
            f"Legal: {[a.describe() for a in legal]}"
        )
    # Give In to Your Anger SHD_144: a forced-attack compulsion is consumed by the
    # flagged player's very next action (whether or not it was the constrained
    # attack).  It applies only on a clear stack (resolving a sub-decision isn't
    # "their next action"), and only to the flagged player's own turn — so playing
    # the event that SETS the flag (a different, active player) never self-clears it.
    fa = state.game_memory.forced_attack
    consuming = (fa is not None and not state.pending_decisions
                 and state.active_player.player_id == fa.get("player_id"))
    # A real TURN ACTION (taken on a clear stack during the action phase) is counted
    # per player, so "Play only as your first action in the action phase"
    # (Confidence in Victory SEC_145) is answerable.  Resolving a sub-decision is
    # not an action, hence the empty-stack guard.  Phase-cleared; a no-op read for
    # every card without the marker.
    counting_actor = (state.active_player.player_id
                      if not state.pending_decisions and state.phase == Phase.ACTION
                      else None)
    new_state = action.apply(state)
    if counting_actor is not None:
        gm = new_state.game_memory
        gm.actions_taken_this_phase[counting_actor] = (
            gm.actions_taken_this_phase.get(counting_actor, 0) + 1)
    _sweep_defeated_units(new_state)
    new_state = _fire_noncombat_damage_observers(new_state)
    new_state = _fire_draw_observers(new_state)
    new_state = _fire_force_observers(new_state)
    new_state = _fire_reveal_discard_observers(new_state)
    new_state = _fire_hand_discard_observers(new_state)
    new_state = _fire_self_discard_observers(new_state)
    new_state = _fire_deck_discard_observers(new_state)
    new_state = _fire_heal_observers(new_state)
    new_state = _fire_base_damage_observers(new_state)
    new_state = _fire_ready_observers(new_state)
    new_state = _fire_upgrade_defeat_observers(new_state)
    new_state = _fire_upgrade_attach_observers(new_state)
    new_state = _fire_unit_entry_observers(new_state)
    new_state = _fire_token_creation_observers(new_state)
    new_state = _fire_bounty_observers(new_state)
    _revert_orphaned_resource_control(new_state)
    _resolve_unique_duplicates(new_state)
    # Decision-stack invariant: while any decision is pending, the active player
    # is the top decision's deciding player.  Every *push* site upholds this, but
    # a *pop* unconditionally restores the popped decision's
    # after_resolve_player_index — correct only when the stack empties.  When a
    # decision pushed by one source (e.g. The Mandalorian SHD_18's "when you play
    # an upgrade" trigger) pops while a decision pushed independently (e.g.
    # Snapshot Reflexes SHD_223's granted attack) is still underneath, the active
    # player would otherwise flip to the wrong seat and the next actor would be
    # asked to resolve a decision that isn't theirs.  Re-pin it to the seat that
    # actually owns the surviving top decision.
    if new_state.pending_decisions:
        new_state.active_player_index = new_state.player_index(
            new_state.pending_decisions[-1].deciding_player_id
        )
    # Clear a consumed forced-attack compulsion (SHD_144), unless the action itself
    # re-armed a fresh one (a new dict for a different unit).
    if consuming:
        nfa = new_state.game_memory.forced_attack
        if nfa is None or (fa is not None and nfa.get("unit_id") == fa.get("unit_id")):
            new_state.game_memory.forced_attack = None
    return new_state


def _resolve_unique_duplicates(s: GameState) -> None:
    """State-based Unique Rule (SWU CR "resolving a duplicate").

    A player may not control two or more units *or* upgrades with the same full
    name (title + subtitle) that are unique.  When a duplicate comes under a
    player's control, that player chooses one copy to keep and the rest are
    defeated.

    Like ``_sweep_defeated_units`` this is a game-state-based action, checked here
    at the action settle-point (when a player would receive priority), so it
    catches *every* path that can create a duplicate — playing a unit, attaching
    an upgrade, taking control of an enemy unit, or a returned captured card —
    without wiring a check into each placement site.  Uniqueness is keyed on
    ``display_name`` (title + subtitle), so different-subtitle same-title cards
    never conflict and reprints (the same card across sets) do.  It is per-player:
    each player may control their own copy of a given unique card.

    Ordering note: because this runs at settle, the newly-played card's own
    "When Played" abilities have already resolved — matching the ruling that a
    card which entered play still triggers, regardless of which duplicate is kept.
    Only one violating group is resolved per call; the next settle re-checks for
    any further duplicate (as with the defeat sweep).
    """
    if s.pending_decisions or s.is_terminal():
        return
    for ps in s.players:
        groups: dict[str, list[str]] = {}
        for unit in ps.ground_arena + ps.space_arena:
            if getattr(unit.card_def, "is_unique", False):
                groups.setdefault(unit.card_def.display_name, []).append(unit.instance_id)
            for upg in unit.attached_upgrades:
                if getattr(upg.card_def, "is_unique", False):
                    groups.setdefault(upg.card_def.display_name, []).append(upg.instance_id)
        for name, ids in groups.items():
            if len(ids) >= 2:
                _push_resolve_unique(s, ps.player_id, name, ids)
                return


# ── Game creation ─────────────────────────────────────────────────────────────


# ── Effective-stats layer ─────────────────────────────────────────────────────


# ── Internal: decision helpers ────────────────────────────────────────────────

def _decision_legal_actions(state: GameState) -> list[Action]:
    """Return legal actions when a pending decision is on the stack.

    A lookup in ``dispatch``, whose docstring records why a table is exactly
    equivalent to the ``if top.kind == "..."`` chain this replaces: no arm fell
    through and no kind was handled twice, so ordering was never load-bearing.
    """
    top = state.pending_decisions[-1]
    # Validates the decision's player the way the old chain did, by computing the
    # deciding player up front for every kind. Only 10 of the 74 handlers actually
    # want it, but `player_by_id` raises KeyError on an unknown id, so dropping the
    # call for the other 64 would quietly stop a malformed decision from failing
    # here. Kept as a check rather than passed along.
    state.player_by_id(top.deciding_player_id)
    handler = decision_handler(top.kind)
    if handler is None:
        return [AnswerTestDecision("unknown")]  # fallback; shouldn't be reached
    return handler(state, top)


# ── Ambush ────────────────────────────────────────────────────────────

# ── Exploit ───────────────────────────────────────────────────────────

# ── Test (for unit-test infrastructure only) ──────────────────────────
def _test_actions(state: GameState, top: PendingDecision) -> list[Action]:
    options = top.context.get("options", ["yes", "no"])
    return [AnswerTestDecision(opt) for opt in options]

# ── Phase 3: trigger_option ───────────────────────────────────────────

# ── Phase 3: resolve_effects ──────────────────────────────────────────
def _resolve_effects_actions(state: GameState, top: PendingDecision) -> list[Action]:
    from swu.abilities.resolver import resolve_effects_actions
    return resolve_effects_actions(state, top)

# ── Effect-granted attack (e.g. Surprise Strike) ──────────────────────
def _granted_attack_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    owner_idx = state.player_index(top.deciding_player_id)
    enemy_ps = state.players[1 - owner_idx]
    attacks: list[Action] = list(
        _filter_granted_attacks(state, top.context, deciding_ps, enemy_ps))
    # "You may attack" (optional) always allows declining; a mandatory grant
    # only offers a decline when no unit can attack (fizzle).
    if top.context.get("optional") or not attacks:
        attacks.append(DeclineGrantedAttack())
    return attacks

# ── Phase 3: pre_attack continuation ──────────────────────────────────

# ── Play a unit from hand as an ability (Admiral Ozzel, SOR_129) ───────

# ── Play an event from hand as an ability (Bib Fortuna, SOR_177) ──────

# ── Play a card using Smuggle as an ability (Lando Calrissian, SHD_17) ─

# ── Play a card using Piloting as an ability (Wedge Antilles, JTL_8) ───

# ── Opponent may ready a unit (Admiral Ozzel, SOR_129) ────────────────

# ── Opponent may say "no" to an effect (I Am Your Father, SOR_233) ────

# ── Choose N different-named discard cards, return 1 at random (Aphra SHD_15) ─

# ── Bottom up-to-N cards from a discard pile (Restock SOR_252) ─────────

# ── Select up to N units, give each a token (Medal Ceremony SOR_245) ──

# ── Disclose: reveal hand cards bearing aspect icons (Karis/Syril) ────

# ── Deal 1 damage to each of up to N units (IG-2000 JTL_140) ──────────

# ── Receiving player assigns all indirect damage to one target ──────────

# ── Peek at top of deck (R2-D2 SOR_236, C-3PO SOR_238) ────────────────

# ── Choose a number (C-3PO SOR_238) ───────────────────────────────────

# ── Look at an opponent's hand (Viper Probe Droid SOR_228) ────────────

# ── Modal "choose one" (Leia Organa SOR_189) ──────────────────────────

# ── Opponent-decided modal: Let the Wookiee Win (SHD_205) ──────────────

# ── Reveal top, discard any, reorder the rest on top (For a Cause I

# ── Reveal-until-stop, damage = combined cost (Don't Get Cocky SOR_223) ─

# ── Opponent chooses one of their cards, you may damage it (Grey

# ── Controller picks up to 2 non-leader units; the opponent chooses which

# ── Owner of a returned unit may replay it for free (Baylan Skoll

# ── Owner of a chosen in-play unit puts it on top or bottom of their deck

# ── Each player chooses one of their own non-leader units; defeat them

# ── Name a card; opponent-owned non-leader copies lose all abilities while the

# ── Opponent may give up a non-leader unit to be captured, else the source

# ── Choose N friendly units to spare, defeat all other friendly units

# ── Unique Rule: keep one duplicate copy, defeat the rest (state-based) ──────

# ── Name a card in an opponent's hand; one copy is discarded (Chimaera

# ── Opponent may discard a random card, else create tokens (Political

# ── Exhaust any number of friendly units, deal base damage per (The


# ── The defending player may rescue one of their own cards guarded by the

# ── Choose any number of friendly units, each captures an enemy non-leader

# ── Choose any number of friendly units; their combined power caps a free

# ── For each exploited unit, you may deal its power to an enemy unit

# ── Pay up to N resources, give that many Experience tokens to this unit

# ── Reveal a deck top, a chosen player plays it free, a different player

# ── Plot — play Plot cards from resources on a leader deploy (Garindan


# ── Attack pipeline helpers ───────────────────────────────────────────────────


# ── Internal helpers ──────────────────────────────────────────────────────────


def _play_only_as_first_action_blocked(state: GameState, ci: CardInstance,
                                       ps: PlayerState) -> bool:
    """True if ``ci`` carries the ``PlayOnlyAsFirstAction`` marker and ``ps`` has
    already taken a turn action this action phase (Confidence in Victory SEC_145).

    The ``_cannot_play_from_hand`` shape: read at the hand-play enumeration and at
    ``PlayCard.apply`` as a defensive guard, over the phase-cleared per-player
    counter ``game_memory.actions_taken_this_phase``."""
    from swu.abilities.registry import get_abilities, PlayOnlyAsFirstAction
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    if not any(isinstance(sp, PlayOnlyAsFirstAction) for sp in get_abilities(sc, cn)):
        return False
    return state.game_memory.actions_taken_this_phase.get(ps.player_id, 0) > 0


def _events_locked(state: GameState, ci: CardInstance, ps: PlayerState) -> bool:
    """True if ``ps`` may not play ``ci`` because it is an Event and they are under
    a phase-scoped event lock (Trade Route Taxation SEC_126: "they can't play events
    for this phase").

    The ``_cannot_play_from_hand`` shape: read at the hand-play enumeration and at
    ``PlayCard.apply`` as a defensive guard, over the phase-cleared ledger
    ``game_memory.cannot_play_events_this_phase``.  DOCUMENTED NARROWING: only the
    hand-play route is barred, so an event played out of the resource zone via Plot
    still resolves."""
    from swu.cards.models import Event as _EventDef
    if not state.game_memory.cannot_play_events_this_phase:
        return False
    return (isinstance(ci.card_def, _EventDef)
            and ps.player_id in state.game_memory.cannot_play_events_this_phase)


def _cannot_play_from_hand(ci: CardInstance) -> bool:
    """True if ``ci``'s card carries the ``CannotPlayFromHand`` marker ("This card
    can't be played from your hand" — One in a Million SEC_53, which is playable only
    out of the resource zone via Plot).  Read at the hand-play enumeration only, and
    at ``PlayCard.apply`` as a defensive guard; a no-op for every other card."""
    from swu.abilities.registry import get_abilities, CannotPlayFromHand
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    return any(isinstance(sp, CannotPlayFromHand) for sp in get_abilities(sc, cn))


# ── Play-a-card-from-hand-as-an-ability subsystem (Admiral Ozzel, SOR_129) ────


    # else: nothing playable and no follow-up — caller hands the turn over.


# ── Play an EVENT from hand as an ability (Bib Fortuna SOR_177) ────────────────
# The event sibling of the units-only ``push_play_from_hand`` subsystem.  Events
# never enter play — they resolve via ``_resolve_event_ability`` and go to discard —
# so this is a distinct decision kind rather than a flag on the unit path.


# ── Play a card using Smuggle as an ability (Lando Calrissian SHD_17) ──────────
# The Smuggle sibling of ``push_play_event_from_hand``: an ability that plays a card
# from the RESOURCE zone using its Smuggle keyword at a cost reduction, WITHOUT handing
# the turn over (the ability's own resolution governs), then optionally defeats one of
# the controller's resources.  Reuses the SmugglePlay mechanics wholesale.


# ── Play a card using Piloting as an ability (Wedge Antilles JTL_8) ────────────
# The Piloting sibling of ``push_play_via_smuggle``: an ability that plays a card
# from HAND using its Piloting keyword at a cost reduction, WITHOUT handing the
# turn over.  Reuses the PilotPlay mechanics (``_piloting_cost`` / ``_attach_pilot``)
# wholesale, so the pilot's own upgrade triggers and stat contribution are
# unchanged.


# ── Deck search-and-select push helper (Tarkin SOR_84, Recruit SOR_123) ───────


# ── Peek-at-top-of-deck push helpers (R2-D2 SOR_236, C-3PO SOR_238) ───────────


# ── Modal "choose one" push helper (Leia Organa SOR_189) ──────────────────────


# ── Let the Wookiee Win push helper (SHD_205) ─────────────────────────────────


# ── Reveal-top push helper (For a Cause I Believe In, SOR_152) ────────────────


# ── Repeated-modal push helper (Poe Dameron SHD_153) ──────────────────────────


# ── Sacrifice-a-resource push helper (Wrecker SHD_154) ────────────────────────


# ── Cull any number of your own cards, then deal that many damage ─────────────
#
# "Discard any number of cards from your hand.  Deal damage to a unit or base equal
# to the number of cards discarded this way." (Darth Vader LAW_11, On Attack) and
# its token twin "Defeat any number of friendly tokens.  Deal damage to a unit equal
# to the number of tokens defeated this way." (Han Solo LAW_17, On Attack).  The
# same kind also drives Han's undeployed "Action [Exhaust, defeat a friendly token]:
# Deal 1 damage to a unit" with ``min_count=max_count=1`` — a cost whose only
# interesting part is WHICH token the controller gives up.
#
# One self-contained two-stage decision, modelled on ``discard_unit_damage``: stage
# "select" repeats (SelectCullCard) until the controller finishes (FinishCull,
# offered once ``min_count`` picks are in), then stage "target" picks the damage
# recipient (ChooseCullDamageTarget).  NOTHING is culled while the decision is open —
# the picks are recorded and the discards/defeats are applied after the pop, together
# with the damage, so a defeat trigger never lands on top of an open decision (the
# push_distribute_damage rule, and the same choice push_select_token's defeat mode
# makes).  No change to core resolution or the trigger machinery.


# ── Interactive combat-damage prevention (Queen Amidala SEC_101) ────────────────
#
# "If damage would be dealt to this unit, you may defeat another friendly unit that
# shares a trait with this unit.  If you do, prevent that damage."  THIS SESSION
# implements the COMBAT-damage half: a pre-step2 checkpoint (``_armed_combat_
# preventions``) fired from ``_resolve_unit_combat`` that, when a combatant carries
# the ``InteractiveDamagePrevention`` marker and would take >0 unshielded combat
# damage AND has an eligible trait-sharing friendly to sacrifice, pushes a
# ``combat_damage_prevention`` decision UNDER any OnAttack-trigger decisions and just
# ABOVE the existing ``pre_attack`` continuation.  The decision's controller either
# picks a friendly trait-sharing unit to defeat (arming the protected unit's one-shot
# ``prevent_next_combat_damage`` flag, read at ``_deal_damage_with_shield``) or
# declines.  The existing ``ContinueAttack`` then resumes ``_resolve_unit_combat_step2``
# — no combat-pipeline rewrite.  Ability/indirect damage prevention (the synchronous
# sinks) is the DEFERRED second half (see ``InteractiveDamagePrevention``'s docstring).


# ── Interactive ABILITY-damage prevention (Queen Amidala SEC_101 — the DAMAGE half's
# ability sink; combat is the flag mechanism above) ──────────────────────────────────
#
# Unlike combat (which has a natural pre-step2 checkpoint), ability damage is dealt
# SYNCHRONOUSLY from many call sites through the single sink ``resolver._apply_deal_
# damage``.  So prevention is DEFERRED, not pre-armed: when that sink is about to deal
# >0 damage to a marked, unshielded unit with an eligible sacrifice, it pushes an
# ``ability_damage_prevention`` decision (carrying the deferred damage payload) and
# returns WITHOUT dealing — the established nested-decision pattern (SOR_233 / Calculated
# Lethality SHD_39; ``apply_resolve_effects`` and every top-level "pop, then deal"
# resolver already resume a decision pushed mid-resolution).  On resolve the controller
# either defeats a friendly trait-sharing unit (the damage is DROPPED) or declines (the
# deferred damage is re-applied with ``_skip_prevention=True`` so it does not re-defer).
# Reuses the combat half's ``_has_interactive_damage_prevention`` /
# ``_prevention_sacrifice_targets`` helpers and the ``ChoosePreventionSacrifice`` /
# ``DeclineCombatPrevention`` actions (both broadened to this kind).


# ── Recycle-a-discarded-unit-for-scaling-damage (The Sarlacc of Carkoon LAW_163)
#
# "On Attack: Put a unit from your discard pile on the bottom of your deck.  Deal
# damage equal to that unit's power to an enemy ground unit."  A self-contained
# two-stage decision (the push_sacrifice_resource_for_damage shape — choose, then
# deal):
#   * stage "select" — SelectDiscardUnitForDamage(instance_id) bottoms a chosen
#     unit from the controller's discard pile and records its printed power as the
#     damage magnitude (a card in discard carries no in-play stats, so its printed
#     power is its power).  Mandatory if able: the decision is only pushed when the
#     discard pile holds ≥1 unit, and no decline is offered.
#   * stage "target" — ChooseDiscardDamageTarget(target_id) deals the recorded
#     damage to the chosen enemy ground unit, then pops.  If no enemy ground unit
#     exists the select stage pops directly (the recycle still happens, no damage).
# The damage is dealt AFTER the decision pops (the push_distribute_damage "pop,
# then deal" gotcha) so a defeat trigger lands on a clean stack.  No change to core
# resolution or the trigger/decision machinery (a new self-contained decision kind).


# ── Discard-a-unit-as-a-cost, then search the deck (Great Pit of Carkoon LAW_23)
#
# "Epic Action [discard a unit from your hand]: Search your deck for a card named
# <search_name>, reveal it, and draw it."  The discard cost lets the controller
# *choose* which unit to discard (the DiscardFromHand effect's first-card
# simplification is for opponent discards, not a self-paid cost), so it is a small
# self-contained decision kind: stage-less, one action per discardable hand unit.
# Choosing one discards it (the cost is mandatory — no decline; the epic is gated
# upstream by CONTROLLER_HAS_UNIT_IN_HAND so it is never activated with nothing to
# discard), pops this decision, then runs the deck search via push_deck_search
# (whole-deck window for a named tutor; the un-taken cards are bottomed in a
# seeded-random order, which doubles as the post-search shuffle).  No change to
# core resolution or the trigger/decision machinery.


# ── Recur-from-discard then buff (Luminous Beings LOF_104) ────────────────────
#
# "Put up to N <trait> units from your discard pile on the bottom of your deck in
# a random order.  Give that many units +P/+H for this phase."  A self-contained
# two-stage decision (the push_sacrifice_resource_for_damage "choose, then act"
# shape, extended to two select-up-to lists):
#   stage "recur"  — pick up to N matching units from the discard pile, one at a
#                    time, or finish early; on finish they go to the bottom of the
#                    deck in a random (rng) order and K = the number chosen.
#   stage "buff"   — pick up to K distinct in-play units, each gets a +P/+H
#                    this-phase modifier; finish (or auto-finish at K / when no
#                    eligible unit remains).
# No new decision-machinery — a new self-contained decision kind, the allowed
# small-primitive path.


# ── Opponent-chooses-target push helper (Grey Squadron Y-Wing SHD_246) ────────


# ── I Had No Choice SOR_187 — controller picks up to 2 non-leader units, the
#    opponent chooses which one returns to its owner's hand; the other is put on
#    the bottom of its owner's deck ("opponent_split_bounce") ──────────────────
#
# A two-stage decider-shift decision (the opponent_chooses_target SHD_246 / say_no
# SOR_233 pattern).  Stage "choose": the source's controller selects up to 2
# non-leader units (any controller).  Stage "split": when two were chosen, control
# shifts to the OPPONENT, who picks which returns to its owner's hand — the other
# is put on the bottom of its owner's deck.  Choosing 0 fizzles; choosing exactly 1
# returns that one to hand (there is no "other" to bottom) and skips the opponent
# stage.  The relocations reuse ``_apply_return_to_hand`` and ``_apply_put_on_deck``
# after the decision pops ("pop, then act", so any board fallout sweeps on a clean
# stack).


# ── Each player chooses one of their own non-leader units; defeat them all
#    (Merciless Contest TWI_238) ──────────────────────────────────────────────


# ── Name a card; each non-leader card an opponent owns with that name loses all
#    abilities while the namer is in play (Galen Erso P25_31 WhenPlayed) ─────────
#
# A self-contained 'name_a_card' decision decided by the source's controller.  The
# option list is the distinct NON-leader card names among the OPPONENT's cards in
# PUBLIC zones (arenas + their attached upgrades + discard + base).  Restricting to
# public copies keeps the option list bounded AND avoids leaking the opponent's
# hidden hand/deck to the naming player; the "including those not in play" clause is
# still honoured because the effect is a passive name-based read
# (state.is_name_suppressed), so a hidden copy of a publicly-named card is suppressed
# the instant it is played.  DOCUMENTED SIMPLIFICATION: a card with NO public copy
# cannot be named (the naming fizzles if the opponent has no public non-leader card).


# ── Opponent chooses one of their own non-leader units to be captured, else the
#    source readies (Grand Admiral Thrawn SEC_193 WhenPlayed) ──────────────────


# ── Choose N friendly units, buff each, then defeat all OTHER friendly units
#    (Always Two LOF_42) ───────────────────────────────────────────────────────
#
# "Choose 2 friendly unique Sith units.  If you do, give 2 Shield and 2 Experience
# tokens to each chosen unit.  Defeat all other friendly units."  A self-contained
# 'choose_units_sacrifice_rest' decision (the each_player_defeats TWI_238
# "select one at a time, then pop, then defeat" shape + the select_token
# recompute-eligible loop): the controller picks distinct matching units one at a
# time until ``required_count`` are chosen; then the decision pops, each chosen unit
# gets the tokens, and every OTHER friendly arena unit is defeated (the "pop, then
# defeat" gotcha so a WhenDefeated trigger lands on a clean stack).  Choosing is
# mandatory ("Choose 2", not "you may") — no decline; the decision is pushed only
# when ≥ required_count units are eligible, so with too few the whole thing fizzles
# (the "If you do" clause fails and nothing is defeated).


# ── Unique Rule: keep one of the duplicate copies, defeat the rest
#    (state-based, pushed by _resolve_unique_duplicates) ───────────────────────


# ── Put N cards from your hand on the bottom of your deck in any order
#    (Private Manufacturing TWI_257) ─────────────────────────────────────────
#
# "put 2 cards from your hand on the bottom of your deck in any order" lets the
# controller choose *which* cards and the *order* they go on the bottom.  A
# stage-less self-contained decision: one SelectHandCardToBottom per hand card,
# picked one at a time (the pick order == bottom-placement order, so "in any
# order" falls out).  The cost is mandatory (no decline) — the controller must
# bottom exactly ``min(count, hand size)`` cards; the decision auto-pops once that
# many have been placed.


# ── Each player discards down to a chosen hand size (Smoke and Cinders SOR_174) ─
#
# "Each player discards all but 2 cards (of their choice) from their hand."  A
# self-contained symmetric decision reusing the each_player_defeats TWI_238
# order/idx walk: one 'discard_excess_from_hand' decision walks the players in turn
# (the event's controller first, then the opponent), each discarding cards of their
# choice one at a time via SelectExcessHandCardToDiscard until their hand is down to
# ``keep`` cards.  A player already at/below ``keep`` is skipped; if neither has
# excess the decision is never pushed (the event fizzles).  Records the
# reveal/discard-observer instruction (Padmé SEC_16) once per player who discards
# ≥1.  Adds no change to core resolution or the trigger machinery — only a new
# self-contained decision kind that shifts the deciding player per stage.


# ── Name a card; an opponent reveals their hand and discards a card of that name
#    (Chimaera SOR_185 On Attack) ─────────────────────────────────────────────
#
# "Name a card.  An opponent reveals their hand and discards a card with that name
# from it."  Because the reveal is part of the effect (the controller sees the
# opponent's hand), this is modelled as the optimal-play collapse of "name blind,
# then reveal": a private 'name_and_discard' decision carrying the opponent's hand
# card identities (card_id + name only — never their hidden instance_ids, the
# look_hand precedent) lets the controller pick a name present in that hand; one
# opponent card of that name is then discarded.  A rational controller always names a
# card actually in hand, so offering only present names (never whiffing) is the
# strictly-optimal encoding — a documented simplification of the printed "name blind".
# Pushed only when the opponent holds ≥1 card; an empty hand fizzles.


# ── Opponent may discard a random card, else create token units (Political
#    Pressure TWI_222) ─────────────────────────────────────────────────────────


# ── Disclose (reveal cards from hand bearing aspect icons; if you do, a payoff) ─
#
# "You may disclose <aspects> (reveal cards from your hand with these aspect icons
#  among them). If you do, <payoff>."  A self-contained multi-select decision (the
#  select_token 'pick a covering set one at a time' shape): the discloser picks
#  hand cards, each contributing ≥1 still-needed aspect icon, until the required
#  aspect multiset is covered (auto-resolving the payoff), or declines (the "you
#  may").  Revealing does NOT move the cards — it is public info only; the
#  mechanical effect is the payoff.  Payoffs are dispatched by a small string key +
#  JSON-serialisable args so the decision context round-trips.  The primitive is the
#  disclose gate; individual payoffs reuse existing seams (create-token-unit /
#  may_discard-else-damage).  Serves Karis Nemik SEC_148 + Syril Karn SEC_133 and
#  broadly unblocks the ~40 other SEC "You may disclose …" cards.


# ── Exhaust any number of friendly units, deal base damage per (The Invisible
#    Hand TWI_234 On Attack) ───────────────────────────────────────────────────


# ── The DEFENDING player may rescue one of their own cards guarded by a unit;
#    if they do, that unit's controller draws (Cad Bane TWI_187 On Attack) ──────
#
# "On Attack: The defending player may rescue a card they own guarded by this unit.
# If they do, draw 2 cards."  A binary decision handed to the OPPONENT (the say_no
# SOR_233 / owner_may_replay LOF_185 deciding-player shift): a genuine tradeoff, so
# it cannot collapse to an optimal-play default — getting the card back costs the
# defender two cards of tempo for the attacker.  The candidates are only captives
# the DECIDER owns (rescuing an enemy's captive is never something they would do,
# and the card says "a card they own"), each guarded by the source.  The payoff
# ("draw 2") goes to the source's controller, the unattributed-subject convention.


# ── New primitive: "you may use the Force" optional rider (force-token,
#    qui-gon-jinn:06) ─────────────────────────────────────────────────────────
#
# "You may use the Force (lose your Force token).  If you do, <rider>."  A single
# 'use_force' decision (decided by the source's controller) lets them pay a cost —
# always the Force token, and for Impossible Escape ALSO the alternative "exhaust a
# friendly unit" — for a rider effect.  Two LOF cards use it:
#   * The Will of the Force LOF_227 — rider "discard_random": the player who owns
#     the just-returned unit discards a random card; resolves with no target.
#   * Impossible Escape LOF_218 — costs {force, exhaust_friendly}, rider
#     "exhaust_enemy_draw": draw a card, then exhaust an enemy unit if able (a
#     second "payoff" stage with a target).
# Stages: "choose" (UseForceOption / DeclineUseForce) → optionally "payoff"
# (ChooseUseForcePayoffTarget).  Declining is always legal (every use is "may").


# ── Reveal-a-deck-top / a chosen player plays it free / a different player makes
#    Credits = its cost (Vermillion LAW_215) ─────────────────────────────────


# ── New primitive: move-an-upgrade (Survivors' Gauntlet SHD_64) ───────────────
#
# Survivors' Gauntlet (SHD_64): "When Played/On Attack: You may attach an upgrade
# on a unit to another eligible unit controlled by the same player."  This is a
# *relocation* of an existing in-play upgrade (not a replay — no WhenPlayed
# re-fire): one 'move_upgrade' decision drives two stages:
#   * stage "pick_upgrade" — MoveUpgradeSelect(upgrade_id) chooses an upgrade in
#                            play that has at least one alternative legal host
#                            controlled by the same player as its current host;
#                            DeclineMoveUpgrade() pops and does nothing ("you may").
#   * stage "pick_dest"    — MoveUpgradeTo(dest_id) detaches the upgrade from its
#                            current host and attaches it to the chosen destination,
#                            then pops.
# The relocation reuses the existing attach-eligibility machinery
# (_eligible_upgrade_targets / _upgrade_target_spec).  Token upgrades
# (Shield/Experience) are excluded, matching the engine-wide kind="upgrade"
# convention (Disabling Fang Fighter SHD_166 etc.).  The decision is only pushed
# when at least one upgrade can actually be moved, so "you may" with nothing to do
# is never offered.  A self-contained new decision kind — no change to core
# resolution or the trigger/decision machinery.


# ── New primitive: pay-and-steal-an-upgrade (Pre Vizsla SHD_142) ──────────────
#
# Pre Vizsla (SHD_142): "When Played/On Attack: You may pay the cost of an upgrade
# attached to another non-Vehicle unit. If you do, take control of that upgrade and
# attach it to this unit, if able. If it can't attach to this unit, defeat it
# instead."  A single-stage 'pay_and_steal_upgrade' decision:
#   * StealUpgrade(upgrade_id) — pay the upgrade's printed cost (ready resources),
#     then RELOCATE it onto Pre Vizsla ("take control" is implicit — control follows
#     the host) if its "Attach to …" restriction admits Pre Vizsla, else DEFEAT it.
#   * DeclineStealUpgrade() — the "you may".
# Candidates are real (non-token) Upgrade cards on ANY unit other than the source
# whose host is not a Vehicle, restricted to those the source's controller can
# afford.  Pilots-as-upgrades (a Unit card_def living in attached_upgrades) are
# excluded — kind="upgrade" convention; stealing a pilot is a documented uncovered
# corner.  The decision is pushed only when at least one affordable candidate
# exists, so the optional ability is never offered when it could do nothing.  A
# relocation, not a play — no UpgradePlayed re-fires.  Reuses the attach-eligibility
# machinery (_upgrade_target_spec / _spec_matches_ci) and _apply_defeat_unit.


# ── Attach an in-play unit as a Pilot upgrade (Poe Dameron JTLP_6) ────────────
#
# The unit-becomes-upgrade relocation primitive — the sibling of `_attach_pilot`
# (which attaches a HAND unit as a pilot) and `_relocate_upgrade` (move_upgrade,
# which relocates an in-play upgrade).  Here an IN-PLAY unit's CardInstance is
# relocated from its arena into a friendly Vehicle's `attached_upgrades` as a
# Pilot.  It is a relocation, NOT a play, so no UpgradePlayed re-fires.


# ── Play an upgrade from hand for free, choosing a host (Jabba the Hutt ASH_42) ─
#
# The upgrade sibling of the units-only ``push_play_from_hand`` subsystem: "play a
# specific upgrade from your hand for free, choosing a legal host".  A single-stage
# host-selection decision (the ``move_upgrade`` / ``pilot_self_attach`` shape) —
# the upgrade is fixed (the one just returned to hand); the player only picks its
# host, or declines ("you may play it for free").  Reuses ``_eligible_upgrade_targets``
# for legal hosts and ``_attach_upgrade`` for the play itself (which fires
# UpgradePlayed → the upgrade's own WhenPlayed triggers).


# ── Select-up-to-N units, give each a token push helper (Medal Ceremony) ──────


# ── select_damage: deal 1 damage to each of up to N units (IG-2000 JTL_140) ─


# ── choose_two_modal: "Choose two, in any order" aspect events ────────────────
# The SOR aspect events (Aggression SOR_155, Command SOR_107, Cunning SOR_203,
# Vigilance SOR_58) each read "Choose two, in any order:" over four options.  Each
# card is registered with N+1 specs: idx 0 = the EventAbility controller (a thin
# CustomEffect calling push_choose_modal), idx 1..4 = the four options, each a
# TriggerAbility whose ``.effects`` is that option's effect list.  The option
# specs are NEVER fired as real triggers (an event card is never in play, so
# _collect_triggers can't reach them) and NEVER resolved by _resolve_event_ability
# (it only processes EventAbility specs) — they are reached ONLY from here, which
# delegates each chosen option to the standard resolve_effects machinery.  So this
# decision kind is purely a SELECTOR; all targeting is the existing resolver's.


# ── assign_indirect_damage: receiving player assigns unpreventable damage ─────


# ── Player-directed damage distribution push helpers ──────────────────────────


# ── distribute_damage decision helpers ───────────────────────────────────────


def _consume_exploit_grant(state: GameState, ci: CardInstance,
                           ps: PlayerState) -> int:
    """Remove and return the amount of the first pending "the next <trait> card you
    play this phase gains Exploit N" grant that applies to playing ``ci``, or 0
    (Count Dooku TWI_5 deployed: "On Attack: The next Separatist card you play this
    phase gains Exploit 3").

    The ``_consume_play_discount`` shape, one grant per matching play: the grant is
    owned by a player and (optionally) narrowed to a trait, and it applies to a card
    of ANY type — Exploit is granted to "a card", and the Exploit seam only ever
    fires for a card being played from hand.  Called once, at that seam."""
    traits = set(getattr(ci.card_def, "traits", ()) or ())
    for i, entry in enumerate(state.game_memory.pending_exploit_grants):
        if entry.get("player_id") != ps.player_id:
            continue
        trait = entry.get("trait")
        if trait is not None and trait not in traits:
            continue
        amt = int(entry.get("amount", 0) or 0)
        del state.game_memory.pending_exploit_grants[i]
        return amt
    return 0


def _named_card_play_forbidden(state: GameState, ci: CardInstance,
                               ps: PlayerState) -> bool:
    """True if an ENEMY in-play unit carrying a ``ForbidNamedCardPlay`` marker has
    named ``ci``'s card (Regional Governor SOR_62: "opponents can't play the named
    card").  Read at the play-legality seam (enumeration skip + PlayCard guard); the
    marker keeps this distinct from Galen Erso's ability-suppression naming."""
    from swu.abilities.registry import get_abilities, ForbidNamedCardPlay
    name = getattr(ci.card_def, "name", None)
    if not name:
        return False
    # "Name a card.  Cards with that name can't be played this phase"
    # (Transmission Jamming LAW_243) — an effect-granted, phase-scoped ban that
    # binds EVERY player, unlike the marker below (which bars only the namer's
    # opponents).  Cleared at the phase rollover.
    if name in getattr(state.game_memory, "forbidden_card_names_this_phase", ()):
        return True
    opp = state.players[1 - state.player_index(ps.player_id)]
    for src in opp.ground_arena + opp.space_arena:
        if getattr(src, "named_card", None) != name:
            continue
        sc = getattr(src.card_def, "set_code", None) or ""
        cn = getattr(src.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if isinstance(spec, ForbidNamedCardPlay):
                return True
    return False


def _enumerate_smuggle_plays(state: GameState, ps: PlayerState) -> list[Action]:
    """SmugglePlay actions for every resource the active player may smuggle now."""
    acts: list[Action] = []
    for ci in ps.resources:
        cost = _smuggle_cost(state, ci, ps)
        if cost is None:
            continue
        # Cost is paid from the OTHER resources (the smuggled card itself leaves
        # the zone and is replaced from the deck).
        other_ready = sum(
            1 for r in ps.resources
            if not r.exhausted and r.instance_id != ci.instance_id
        )
        if other_ready < cost:
            continue
        card = ci.card_def
        if isinstance(card, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                acts.append(SmugglePlay(ci.instance_id, target.instance_id))
        else:
            acts.append(SmugglePlay(ci.instance_id))
    return acts


_DEPLOY_AS_UPGRADE_RE = re.compile(r"as an upgrade", re.IGNORECASE)


def _leader_can_deploy_as_upgrade(card_def: AnyCard) -> bool:
    """True if the leader's Epic Action offers a "deploy … as an upgrade" option
    (Boba Fett JTL_9).  Read from the ``epic_action`` text — data-driven, so any
    future leader-as-upgrade card works without code changes."""
    from swu.cards.models import Leader
    if not isinstance(card_def, Leader):
        return False
    epic = (getattr(card_def, "epic_action", "") or "").replace("\xa0", " ")
    return bool(_DEPLOY_AS_UPGRADE_RE.search(epic))


def _eligible_leader_upgrade_targets(state: GameState, ps: PlayerState) -> list[CardInstance]:
    """Friendly Vehicle units with a free Pilot slot — legal hosts for deploying a
    leader as an upgrade (Boba Fett JTL_9's "friendly Vehicle unit without a Pilot
    on it").  A unit's slot count is the standard 1 plus any ``AdditionalPilotSlots``
    (Millennium Falcon JTL_249 hosts a second Pilot)."""
    from swu.engine.traits import has_trait
    return [ci for ci in ps.ground_arena + ps.space_arena
            if has_trait(state, ci, "Vehicle")
            and _pilot_count(ci) < _pilot_limit(ci)]


def _enumerate_pilot_plays(state: GameState, ps: PlayerState) -> list[Action]:
    """PilotPlay actions for every hand Unit with a Piloting cost the player can afford."""
    acts: list[Action] = []
    for ci in ps.hand:
        if not isinstance(ci.card_def, Unit):
            continue
        cost = _piloting_cost(state, ci, ps)
        if cost is None:
            continue
        if not _affordable_with_credits(ps, cost, state):
            continue
        for target in _eligible_pilot_targets(state, ps):
            acts.append(PilotPlay(ci.instance_id, target.instance_id))
    return acts


# ── Credit-token economy (jabba-the-hutt:07) ───────────────────────────────────
# A Credit token is defeated (removed) while paying a resource cost to pay 1 less.
# Credits live in their own pile (PlayerState.credits) and never count as normal
# resources.  Spending is NEED-BASED and automatic: ready resources are exhausted
# first, and a credit is defeated only to cover a shortfall (cost > ready
# resources).  This is deterministic (no decision kind) and strategically sound —
# a credit is never wasted on a play affordable from ready resources alone — at
# the cost of one minor agency simplification: a player cannot *choose* to spend a
# credit they do not strictly need (e.g. to keep a resource ready, or to
# deliberately trigger a "if you defeated a Credit" rider on an otherwise
# affordable play).  With zero credits the behaviour is byte-identical to the old
# resource-only payment, so the normal game is unaffected.
#
# SCOPE: credit-spend is wired into the card-play paths that pay from the
# controller's resources for value — PlayCard (units/upgrades/events; the
# non-Exploit branch) and the play-from-hand subsystem (PlayFromHand, e.g. Jabba
# the Hutt LAW_15's deployed action).  It is NOT wired into Smuggle/Plot (which
# pay from the *other* resources), the Exploit cost reduction, or activated-ability
# PayResources costs — no shipped card combines credits with those, and keeping
# them resource-only is the surgical choice.


def change_resource_control(
    s: GameState, resource_ci: CardInstance, new_controller_id: str,
    *, link_to: Optional[str] = None,
) -> None:
    """Move a resource between players' resource rows, preserving ownership (DJ
    SHD_213: "Take control of an enemy resource").

    Resource control is implicit exactly like unit control (change_control): a
    resource is controlled by whichever player's ``resources`` list holds it, while
    ``resource_ci.owner_id`` stays the (unchanging) owner.  The stolen resource
    keeps its exhausted state and now counts toward the new controller's
    ``available_resources``.  ``link_to`` records the instance id of the unit whose
    leaving play reverts the theft (stored on ``control_linked_to``, the same field
    Maul LAW_54's unit-control link uses — resources are never in an arena, so the
    unit-only ``_revert_linked_control`` never touches them; the resource backstop
    ``_revert_orphaned_resource_control`` owns their reversion).  No-op if the
    resource is not in a resource row or already controlled by new_controller_id.

    A resource is face-down (hidden information), so the ControlChanged event
    deliberately carries a neutral ``card_name`` rather than leaking its identity.
    """
    cur_ps = next((p for p in s.players if resource_ci in p.resources), None)
    if cur_ps is None or cur_ps.player_id == new_controller_id:
        return
    cur_ps.resources.remove(resource_ci)
    resource_ci.control_linked_to = link_to
    new_ps = s.player_by_id(new_controller_id)
    new_ps.resources.append(resource_ci)
    s.event_log.append(ControlChanged(
        instance_id=resource_ci.instance_id,
        card_name="a resource",  # face-down — do not leak the card's identity
        owner_id=resource_ci.owner_id,
        from_player_id=cur_ps.player_id,
        to_player_id=new_controller_id,
    ))


def _revert_orphaned_resource_control(s: GameState) -> None:
    """Settle-time backstop for DJ SHD_213 ("When this unit leaves play, that
    resource's owner takes control of it").

    A resource stolen via ``change_resource_control`` carries
    ``control_linked_to`` = the thief unit's instance_id.  Once that unit is no
    longer in an arena (defeated, bounced, captured — every leave-play path), the
    resource is returned to its owner's resource row and the link cleared.  Runs at
    the action settle-point in ``apply``; a cheap no-op (one set build) when no
    resource is linked, so existing decks are unaffected."""
    in_play = {ci.instance_id
               for p in s.players
               for ci in (*p.ground_arena, *p.space_arena)}
    for p in list(s.players):
        for r in list(p.resources):
            link = r.control_linked_to
            if link is not None and link not in in_play:
                r.control_linked_to = None
                if p.player_id != r.owner_id:
                    change_resource_control(s, r, r.owner_id, link_to=None)


# ── Capture ───────────────────────────────────────────────────────────────────
# Capture removes an enemy unit from play and places it facedown "under" the
# capturing unit (modelled as the capturing player's CAPTURE_PILE, with the
# captured card's instance tagged ``captured_by`` = the captor's instance_id and
# its owner_id unchanged).  When the captor leaves play the captured cards return
# to their owner's arena under their owner's control.  The CAPTURE_PILE zone and
# ``PlayerState.capture_pile`` already exist and are wired into conservation,
# serialisation, and lookup, so capture reuses all of that — it is purely a new
# effect (registry.CaptureUnit) + these two helpers + a release call on leave-play.
#
# ASSUMPTION (documented for review): a returned captured unit re-enters its
# owner's arena **ready** (exhausted=False) with damage cleared, and does NOT
# re-fire enter-play triggers (Ambush / WhenPlayed) — capture-return is treated
# as a relocation, not a fresh play.  The pre-Capture CR (v1.1) does not cover
# this; flip the exhausted flag below if a newer CR says otherwise.
#
# LIMITATIONS (no shipped card exercises these; flagged for a future session):
#   * Capture does NOT collect a captured unit's Bounty — the Bounty convention
#     models "when defeated or captured" as a WhenDefeated trigger only, so a
#     bounty fires on defeat but not on capture.
#   * Release is wired into _defeat_unit only.  The single shipped captor is The
#     Mandalorian (a Leader), which leaves play only by defeat; a future captor
#     bounced to hand / control-changed while holding captives would need a
#     release call on those paths too.


def _defeat_attached_upgrade(s: GameState, upgrade_ci: CardInstance) -> None:
    """Defeat a single attached upgrade: detach it from its host and send it to its
    owner's discard (a TokenUpgrade ceases to exist).  This is the "defeat a Heroic
    Resolve on this unit" activated-ability cost (SHD_155) — a one-upgrade slice of
    the detach branch of ``_defeat_unit``.  No shipped upgrade defeated this way
    carries its own When-Defeated trigger, so no trigger is fired here."""
    from swu.cards.models import TokenUpgrade
    host = _find_upgrade_host(s, upgrade_ci.instance_id)
    note_upgrade_defeated(s, upgrade_ci)   # "When a friendly upgrade is defeated"
    if host is not None and upgrade_ci in host.attached_upgrades:
        host.attached_upgrades.remove(upgrade_ci)
    # Expire any modifiers this upgrade was the source of (it has left play).
    s.modifiers = [m for m in s.modifiers
                   if m.source_instance_id != upgrade_ci.instance_id]
    if isinstance(upgrade_ci.card_def, TokenUpgrade):
        return  # tokens cease to exist — never enter a discard pile
    s.event_log.append(UpgradeDetached(
        upgrade_instance_id=upgrade_ci.instance_id,
        upgrade_name=upgrade_ci.card_def.display_name,
        former_host_name=host.card_def.display_name if host is not None else "",
        owner_id=upgrade_ci.owner_id,
    ))
    upgrade_ci.zone = Zone.DISCARD
    s.player_by_id(upgrade_ci.owner_id).discard.append(upgrade_ci)


# ── Deploy threshold extraction ───────────────────────────────────────────────

_DEPLOY_RE = re.compile(r"you\s+control\s+(\d+)\s+or\s+more\s+resources", re.IGNORECASE)
_DEPLOY_BRACKET_RE = re.compile(r"\[(\d+)\s+resources?\]", re.IGNORECASE)


def _leader_deploy_allowed(state: GameState, ps: PlayerState,
                           leader_ci: CardInstance) -> bool:
    """Is this leader's Epic Action deploy available right now?

    The single gate behind all three deploy seams (the ``legal_actions`` offer and
    both apply-guards).  A registered ``DeployCondition`` marker wins — the escape
    for a leader whose printed clause the ``_deploy_threshold`` regex cannot parse
    (Bo-Katan Kryze ASH_10: "If the number of resources you control plus the number
    of friendly Mandalorian units is 10 or more") — otherwise the long-standing
    resource threshold applies, and an unparsable clause with no marker still means
    "cannot deploy"."""
    from swu.abilities.registry import get_abilities, DeployCondition
    cd = leader_ci.card_def
    if isinstance(cd, Leader) and getattr(cd, "set_code", None):
        for spec in get_abilities(cd.set_code or "", cd.card_number or ""):
            if isinstance(spec, DeployCondition):
                if spec.condition is None:
                    return True
                return bool(spec.condition.evaluate(state, leader_ci))
    threshold = _deploy_threshold(cd)
    return threshold is not None and ps.total_resources >= threshold


def _deploy_threshold(card: AnyCard) -> Optional[int]:
    if not isinstance(card, Leader):
        return None
    epic = card.epic_action or ""
    epic = epic.replace("\xa0", " ")
    m = _DEPLOY_RE.search(epic)
    if m:
        return int(m.group(1))
    m = _DEPLOY_BRACKET_RE.search(epic)
    if m:
        return int(m.group(1))
    return None


# ── Decision-kind registration ─────────────────────────────────────────────
# Every kind the old if-chain handled, now claimed explicitly. This block is what
# moves with a family when it leaves this module: the handlers go, and so do their
# rows. When `_legacy` is empty this list is empty too.
register_decisions({
    "test":                          _test_actions,
    "resolve_effects":               _resolve_effects_actions,
    "granted_attack":                _granted_attack_actions,
    "pre_attack":                    _pre_attack_actions,
})
