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
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

from swu.cards.models import AnyCard, Base, Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    AttackDeclared, CardPlayed, CardResourced,
    ControlChanged, DamageDealt, DecisionPushed, DecisionResolved, HandDrawn, HandKept, InitiativeTaken,
    LeaderDeployed, MulliganTaken, PlayerPassed, RegroupSkipped, UnitDefeated,
    UpgradeDetached,
)
from swu.engine.keywords import Keyword, has_keyword, keyword_value
from swu.engine.state import CardInstance, GameState, Phase, PlayerState, Zone, ability_suppressed
from swu.engine.tokens import attach_token
from swu.engine.triggers import get_bus

from swu.engine.actions.base import Action, IllegalActionError
from swu.engine.actions.deck import (
    push_deck_search,
)
from swu.engine.actions.hand import (
    push_play_from_hand,
)
from swu.engine.actions.scheduling import (
    push_may_discard_else_damage,
)
from swu.engine.actions.distribute import (
    push_distribute_heal,
)
from swu.engine.actions.modal import (
    push_modal,
)
from swu.engine.actions.shared import (
    _attach_pilot, _candidate_card_views, _deploy_leader_into_arena, _eligible_pilot_targets, _enumerate_discard_play_actions, _plot_eligible_resource_ids, _plot_play_actions, _resource_top_of_deck, _sacrifice_damage_targets, _take_from_hand, spend_force_token,
)
from swu.engine.actions.observers import (
    _fire_base_damage_observers, _fire_bounty_observers, _fire_deck_discard_observers, _fire_draw_observers, _fire_force_observers, _fire_hand_discard_observers, _fire_heal_observers, _fire_noncombat_damage_observers, _fire_ready_observers, _fire_reveal_discard_observers, _fire_self_discard_observers, _fire_token_creation_observers, _fire_unit_entry_observers, _fire_upgrade_attach_observers, _fire_upgrade_defeat_observers, note_unit_healed,
)
from swu.engine.actions.dispatch import (
    decision_handler, register_decisions,
)
from swu.engine.actions.turn import (
    _advance_mulligan, _advance_setup_resources, _check_regroup_complete, _enter_regroup, _starting_hand_modifier, _starting_hand_size,
)
from swu.engine.actions.combat import (
    _enumerate_attacks, _enumerate_two_unit_attacks, _filter_granted_attacks, _forced_attack_actions, _pre_attack_actions, _select_token_targets, note_hand_or_deck_discard, push_granted_attack, push_select_token, record_base_damage, record_hand_discard,
)
from swu.engine.actions.flow import (
    _assert_phase, _check_game_over, _switch_active_player,
)
from swu.engine.actions.zones import (
    _apply_capture, _attach_upgrade, _create_token_units, _defeat_unit, _draw_cards, _eligible_upgrade_targets, _find_in_arenas, _find_upgrade_host, _push_resolve_unique, _put_unit_in_play, _resolve_event_ability, _sweep_defeated_units, note_upgrade_defeated,
)
from swu.engine.actions.damage import (
    base_damage_after_prevention,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _consume_standing_discount, _defeat_credit, _discard_cost_candidates, _discard_cost_payable, _exhaust_resources, _pay_play_cost, _pilot_count, _pilot_limit, _piloting_cost, _piloting_discount_entry, _play_cost, _smuggle_cost, resource_cost_for,
)
from swu.engine.actions.stats import (
    compute_hp, compute_power,
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
class FinishPlot(Action):
    """Decline to play any (more) Plot cards off a leader deploy."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "plot"):
            raise IllegalActionError("No pending Plot decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="plot",
            choice="finish",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Finish Plot (play no more cards)"


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

@dataclass
class SelectDiscardCard(Action):
    """Select one eligible card from the discard pile to return to hand."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "return_from_discard"):
            raise IllegalActionError("No return_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_return_from_discard(s)
        return s

    def describe(self) -> str:
        return f"Return {self.instance_id} from the discard pile to hand"


@dataclass
class FinishReturnFromDiscard(Action):
    """Stop selecting discard-pile cards: return the chosen ones to hand.

    Always offered (these effects are "you may" / "up to N", so a zero-pick
    finish is legal)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "return_from_discard"):
            raise IllegalActionError("No return_from_discard decision pending")
        return _finish_return_from_discard(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish returning cards from the discard pile"


def _finish_return_from_discard(s: GameState) -> GameState:
    """Pop the return_from_discard decision: move the selected cards from the
    controller's discard pile to their hand (preserving discard order)."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected_set = set(ctx["selected_ids"])

    returned = [ci for ci in ps.discard if ci.instance_id in selected_set]
    for ci in returned:
        ps.discard.remove(ci)
        ci.zone = Zone.HAND
        # A unit defeated while exhausted lands in discard still exhausted (discard
        # carries no exhaust meaning); a card returned to HAND must be a clean card,
        # else it trips the zone/exhaust-sanity invariant (the Sarlacc LAW_163
        # discard→deck graduation fix, mirrored for the discard→hand path).
        ci.exhausted = False
        ci.damage = 0
        ps.hand.append(ci)

    returned_names = ", ".join(ci.card_def.display_name for ci in returned) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="return_from_discard",
        choice=f"returned {len(returned)} ({returned_names})",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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

@dataclass
class SelectResourceFromDiscard(Action):
    """Select one eligible discard-pile card to put into play as a resource."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_discard"):
            raise IllegalActionError("No resource_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a resource candidate")
        return _finish_resource_from_discard(s, self.instance_id)

    def describe(self) -> str:
        return f"Put {self.instance_id} into play as a resource"


@dataclass
class DeclineResourceFromDiscard(Action):
    """Decline to resource a discard card (offered only for a 'you may' variant)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_discard"):
            raise IllegalActionError("No resource_from_discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="resource_from_discard", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to resource a discard card"


def _finish_resource_from_discard(s: GameState, instance_id: str) -> GameState:
    """Pop the resource_from_discard decision: move the chosen card from the
    controller's discard pile into their resource zone (facedown + exhausted)."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    ci = next((c for c in ps.discard if c.instance_id == instance_id), None)
    name = "nothing"
    if ci is not None:
        ps.discard.remove(ci)
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ci.exhausted = True   # CR default: facedown + exhausted (no "ready it")
        ci.damage = 0
        ps.resources.append(ci)
        name = ci.card_def.display_name
        s.event_log.append(CardResourced(
            player_id=ps.player_id, instance_id=ci.instance_id, card_name=name))
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="resource_from_discard", choice=f"resourced {name}"))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_resource_from_discard(
    s: GameState, source_ci: CardInstance, *,
    eligible: Callable[["CardInstance"], bool], up_to: bool = False,
) -> None:
    """Push a 'resource_from_discard' decision: choose one card in the controller's
    discard pile matching ``eligible`` (a CardInstance predicate) and put it into
    play as a resource (facedown + exhausted).  Candidates are pre-filtered to the
    qualifying cards; fizzles cleanly (no prompt) if none qualify.  ``up_to`` adds a
    DeclineResourceFromDiscard for a "you may" variant (SHD_102/105 are mandatory
    among the qualifiers, so both pass up_to=False)."""
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [ci.instance_id for ci in ps.discard if eligible(ci)]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="resource_from_discard",
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
        deciding_player_id=source_ci.owner_id, kind="resource_from_discard"))


def _resource_from_discard_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top resource_from_discard decision."""
    ctx = top.context
    acts: list[Action] = [SelectResourceFromDiscard(cid) for cid in ctx["candidate_ids"]]
    if ctx.get("up_to"):
        acts.append(DeclineResourceFromDiscard())
    return acts


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

@dataclass
class CullRevealedCard(Action):
    """The OPPONENT discards one of the revealed cards."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cull_draw"):
            raise IllegalActionError("No reveal_cull_draw decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "cull":
            raise IllegalActionError("reveal_cull_draw is not in the cull stage")
        if self.instance_id not in ctx["remaining"]:
            raise IllegalActionError(f"{self.instance_id} is not a revealed card")
        ctx["remaining"].remove(self.instance_id)
        ctx["culled"].append(self.instance_id)
        if len(ctx["culled"]) >= int(ctx["cull_count"]) or not ctx["remaining"]:
            return _advance_reveal_cull_draw(s)
        return s

    def describe(self) -> str:
        return f"Discard revealed card {self.instance_id}"


@dataclass
class DrawRevealedCard(Action):
    """The CONTROLLER draws one survivor; the rest of the revealed cards are
    discarded."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cull_draw"):
            raise IllegalActionError("No reveal_cull_draw decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "draw":
            raise IllegalActionError("reveal_cull_draw is not in the draw stage")
        if self.instance_id not in ctx["remaining"]:
            raise IllegalActionError(f"{self.instance_id} is not a surviving card")
        return _finish_reveal_cull_draw(s, self.instance_id)

    def describe(self) -> str:
        return f"Draw revealed card {self.instance_id}"


def _advance_reveal_cull_draw(s: GameState) -> GameState:
    """The cull stage is done: discard the culled cards and hand the seat to the
    controller for the draw stage.  With nothing left to draw the decision resolves
    outright."""
    top = s.pending_decisions[-1]
    ctx = top.context
    _reveal_cull_discard(s, ctx, ctx["culled"])
    ctx["culled"] = []
    if not ctx["remaining"]:
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_cull_draw", choice="nothing left to draw"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    ctx["stage"] = "draw"
    top.deciding_player_id = ctx["controller_id"]
    s.active_player_index = s.player_index(ctx["controller_id"])
    return s


def _reveal_cull_discard(s: GameState, ctx: dict, ids: list) -> None:
    """Move the named revealed cards out of the controller's deck into their discard
    pile (they are still in the deck — the decision never touched it)."""
    from swu.engine.state import Zone
    ps = s.player_by_id(ctx["controller_id"])
    for iid in list(ids):
        ci = next((c for c in ps.deck if c.instance_id == iid), None)
        if ci is None:
            continue
        ps.deck.remove(ci)
        ci.zone = Zone.DISCARD
        ps.discard.append(ci)
        note_hand_or_deck_discard(s, ci, from_deck=True)


def _finish_reveal_cull_draw(s: GameState, instance_id: str) -> GameState:
    """Pop the decision: the chosen survivor is drawn, every other survivor is
    discarded."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    rest = [iid for iid in ctx["remaining"] if iid != instance_id]
    drawn = next((c for c in ps.deck if c.instance_id == instance_id), None)
    if drawn is not None:
        ps.deck.remove(drawn)
        drawn.zone = Zone.HAND
        ps.hand.append(drawn)
    _reveal_cull_discard(s, ctx, rest)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_cull_draw",
        choice=(f"drew {drawn.card_def.display_name}" if drawn is not None
                else "drew nothing"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_reveal_cull_draw(
    s: GameState, source_ci: CardInstance, *, count: int = 4, cull: int = 2,
) -> None:
    """Push a 'reveal_cull_draw' decision (Admiral Trench JTL_14): reveal the top
    ``count`` cards of the controller's deck; an opponent discards ``cull`` of them;
    the controller then draws 1 of the survivors and discards the rest.

    ``cull`` is capped so at least one card survives for the draw (a short deck
    still yields a legal, meaningful decision), and the whole effect fizzles cleanly
    with no prompt on an empty deck."""
    ps = s.player_by_id(source_ci.owner_id)
    revealed = ps.deck[:int(count)]
    if not revealed:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    opponent_id = s.players[1 - owner_idx].player_id
    cull_n = max(0, min(int(cull), len(revealed) - 1))
    ids = [c.instance_id for c in revealed]
    dec = PendingDecision(
        deciding_player_id=opponent_id if cull_n else source_ci.owner_id,
        kind="reveal_cull_draw",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "opponent_id": opponent_id,
            "stage": "cull" if cull_n else "draw",
            "cull_count": cull_n,
            "culled": [],
            "remaining": ids,
            # The card says "Reveal", so both players may see these identities.
            "revealed": _candidate_card_views(s, ids),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(dec.deciding_player_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=dec.deciding_player_id, kind="reveal_cull_draw"))


def _reveal_cull_draw_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top reveal_cull_draw decision — one per still-revealed
    card, in whichever stage is current.  Both stages are mandatory-if-able (the
    card gives neither player an opt-out)."""
    ctx = top.context
    if ctx.get("stage") == "cull":
        return [CullRevealedCard(cid) for cid in ctx["remaining"]]
    return [DrawRevealedCard(cid) for cid in ctx["remaining"]]


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

@dataclass
class SelectDiscardForExperience(Action):
    """Discard the chosen hand card and give 2 Experience to a same-named unit."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_experience"):
            raise IllegalActionError("No discard_for_experience decision pending")
        from swu.engine.state import Zone
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        ps = s.player_by_id(ctx["controller_id"])
        card = next(c for c in ps.hand if c.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(s, card)
        name = card.card_def.display_name
        target = None
        for arena in (ps.ground_arena, ps.space_arena):
            for u in arena:
                if u.card_def.display_name == name:
                    target = u
                    break
            if target is not None:
                break
        if target is not None:
            attach_token(s, ps, target, "Experience")
            attach_token(s, ps, target, "Experience")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_experience",
            choice=f"discarded {name}, gave 2 Experience"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} to give 2 Experience"


@dataclass
class DeclineDiscardForExperience(Action):
    """Decline Echo's optional discard ("You may discard a card")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_experience"):
            raise IllegalActionError("No discard_for_experience decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_experience", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to discard for Experience"


def push_discard_for_experience(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'discard_for_experience' decision (Echo SHD_99): the candidates are the
    controller's hand cards whose name matches a friendly unit in play.  Fizzles
    cleanly if no hand card matches (nothing to gain from the optional discard)."""
    ps = s.player_by_id(source_ci.owner_id)
    unit_names = {u.card_def.display_name
                  for arena in (ps.ground_arena, ps.space_arena) for u in arena}
    candidate_ids = [c.instance_id for c in ps.hand
                     if c.card_def.display_name in unit_names]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="discard_for_experience",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="discard_for_experience"))


def _discard_for_experience_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_for_experience decision (always includes a
    Decline for the "you may")."""
    ctx = top.context
    acts: list[Action] = [SelectDiscardForExperience(cid) for cid in ctx["candidate_ids"]]
    acts.append(DeclineDiscardForExperience())
    return acts


# ── Restock SOR_252: bottom up-to-N cards from a discard pile ─────────────────
#
# "Choose up to 4 cards in a discard pile.  Put them on the bottom of their owner's
# deck in a random order."  A select-up-to-N decision over BOTH players' discard
# piles (the card says "a discard pile" — either qualifies).  Each chosen card goes
# to the bottom of ITS OWNER's deck; the collected picks are shuffled first so the
# resulting bottom order is random (the deck_search bottoming pattern).

@dataclass
class SelectBottomDiscardCard(Action):
    """Select one card from a discard pile to bottom (Restock SOR_252)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_discard"):
            raise IllegalActionError("No bottom_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_bottom_from_discard(s)
        return s

    def describe(self) -> str:
        return f"Bottom {self.instance_id} from a discard pile"


@dataclass
class FinishBottomFromDiscard(Action):
    """Stop selecting: bottom the chosen discard cards (always offered — "up to N")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_discard"):
            raise IllegalActionError("No bottom_from_discard decision pending")
        return _finish_bottom_from_discard(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish bottoming cards from the discard pile"


def _finish_bottom_from_discard(s: GameState) -> GameState:
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    selected_set = set(ctx["selected_ids"])

    chosen: list[CardInstance] = []
    if ctx.get("disposition") == "choose_only":
        # "Choose another card in your discard pile" (Psychometry LOF_219) — the
        # decision is only a SELECTOR here; nothing moves.  The payoff reads the
        # chosen card's traits.
        for pl in s.players:
            for ci in pl.discard:
                if ci.instance_id in selected_set:
                    chosen.append(ci)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_discard",
            choice=("chose "
                    + (", ".join(c.card_def.display_name for c in chosen)
                       or "nothing")),
        ))
        window = ctx.get("then_deck_search_shared_trait")
        src_res = s.find_instance(ctx["source_id"])
        if window and chosen and src_res is not None:
            wanted = set()
            for c in chosen:
                wanted |= set(getattr(c.card_def, "traits", None) or ())
            push_deck_search(
                s, src_res[1], count=1, up_to=False, window=int(window),
                eligible=lambda cd: bool(
                    wanted & set(getattr(cd, "traits", None) or ())))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    for pl in s.players:
        for ci in list(pl.discard):
            if ci.instance_id in selected_set:
                pl.discard.remove(ci)
                chosen.append(ci)

    # Random bottom order (deck_search bottoming pattern).
    rng = s.make_rng()
    rng.shuffle(chosen)
    s.rng_state = rng.getstate()

    for ci in chosen:
        ci.zone = Zone.DECK
        ci.face_down = True
        ci.exhausted = False
        ci.damage = 0
        s.player_by_id(ci.owner_id).deck.append(ci)  # bottom

    names = ", ".join(ci.card_def.display_name for ci in chosen) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="bottom_from_discard",
        choice=f"bottomed {len(chosen)} ({names})",
    ))
    # "…and create that many <token> tokens" (Reprocess TWI_88) — the payoff scales
    # with how many cards were actually bottomed, so it is settled here, after the
    # pop, and yields nothing when the controller chose none.
    token = ctx.get("then_create_token")
    if token and chosen:
        _create_token_units(s, s.player_by_id(ctx["controller_id"]),
                            token, len(chosen))
    # "…on the bottom of your deck.  If you do, draw a card" (Fives TWI_216) — the
    # same shape: the payoff is bound to an actual bottoming, so choosing none
    # draws nothing.
    draw = int(ctx.get("then_draw") or 0)
    if draw and chosen:
        _draw_cards(s, s.player_by_id(ctx["controller_id"]), draw)
    # "…on the bottom of your deck.  If you do, create a Credit token" (Scavenging
    # Sandcrawler LAW_238) — the Credit sibling of the two payoffs above, likewise
    # bound to an actual bottoming, so choosing none creates nothing.
    credits = int(ctx.get("then_create_credit") or 0)
    if credits and chosen:
        from swu.engine.tokens import create_credit_token
        beneficiary = s.player_by_id(ctx["controller_id"])
        for _ in range(credits):
            create_credit_token(s, beneficiary)
    # "…If you do, play a unit from your hand and give 2 Experience tokens to it"
    # (The Burden of Masters LOF_125) — the third payoff in the same settle-at-the-
    # finish family, so bottoming nothing plays nothing.  The play itself carries
    # the Experience through push_play_from_hand's own ``then_select_token`` rider.
    play_cfg = ctx.get("then_play_from_hand")
    if play_cfg and chosen:
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            push_play_from_hand(s, source_result[1], **dict(play_cfg))
    # "…If you do, deal 1 damage to each enemy base" (0-0-0 LAW_174) — the same
    # settle-at-the-finish family; bottoming nothing deals nothing.  Routed through
    # ``base_damage_after_prevention`` like every other base-damage site.
    # "…put that card on the bottom of your deck and heal 3 damage from your base"
    # (Trask Walker ASH_133) — the heal flavour of the same settle-at-the-finish
    # family, routed through ``_apply_heal`` so the Wolffe SOR_160 base-heal lock and
    # the heal observers still see it.  Bottoming nothing heals nothing.
    heal_base = int(ctx.get("then_heal_base") or 0)
    if heal_base and chosen:
        src_res = s.find_instance(ctx["source_id"])
        beneficiary = s.player_by_id(ctx["controller_id"])
        if src_res is not None and beneficiary.base_instance is not None:
            from swu.abilities.resolver import _apply_heal
            _apply_heal(s, src_res[1], beneficiary.base_instance.instance_id,
                        heal_base)
    base_dmg = int(ctx.get("then_damage_enemy_base") or 0)
    if base_dmg and chosen:
        for p in s.players:
            if p.player_id == ctx["controller_id"] or p.base_instance is None:
                continue
            amt = base_damage_after_prevention(s, p.base_instance, base_dmg)
            if amt > 0:
                p.base_instance.damage += amt
                record_base_damage(s, p.player_id, amt)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_bottom_from_discard(
    s: GameState, source_ci: CardInstance, *, count: int,
    own_only: bool = False,
    eligible: Optional[Callable[[object], bool]] = None,
    then_create_token: Optional[str] = None,
    then_draw: int = 0,
    then_create_credit: int = 0,
    then_play_from_hand: Optional[dict] = None,
    then_damage_enemy_base: int = 0,
    then_heal_base: int = 0,
    exclude_ids: Optional[frozenset] = None,
    disposition: str = "bottom",
    then_deck_search_shared_trait: Optional[int] = None,
) -> None:
    """Push a 'bottom_from_discard' decision (Restock SOR_252): choose up to
    ``count`` cards across both players' discard piles; each goes to the bottom of
    its owner's deck in random order.  Fizzles cleanly if no discard card exists.

    ``own_only`` narrows the candidates to the CONTROLLER's own discard pile ("in
    YOUR discard pile") and ``eligible`` (a predicate on the card_def) narrows them
    by card type/trait ("choose up to 4 UNITS") — Reprocess TWI_88, whose
    ``then_create_token`` also creates one token unit of that name per card
    actually bottomed.  ``then_draw`` is the same shape for a draw payoff ("put a
    Clone unit from your discard pile on the bottom of your deck.  If you do, draw
    a card" — Fives TWI_216): it too is settled at the finish, so bottoming
    nothing draws nothing.  ``then_create_credit`` is the same shape again for the
    Credit economy ("If you do, create a Credit token" — Scavenging Sandcrawler
    LAW_238).

    ``then_damage_enemy_base`` is the same settle-at-the-finish shape for base
    damage — "You may put an Aggression card from your discard pile on the bottom of
    your deck.  If you do, deal 1 damage to each enemy base" (0-0-0 LAW_174) — and
    ``then_heal_base`` its heal mirror, "put that card on the bottom of your deck and
    heal 3 damage from your base" (Trask Walker ASH_133).

    ``then_play_from_hand`` is the same settle-at-the-finish shape for a whole
    ``push_play_from_hand`` (its kwargs as a dict) — "Put a Force unit from your
    discard pile on the bottom of your deck.  If you do, play a unit from your hand
    and give 2 Experience tokens to it" (The Burden of Masters LOF_125).

    ``disposition="choose_only"`` makes the decision a pure SELECTOR — nothing is
    moved — for "Choose another card in your discard pile.  Search the top N cards
    of your deck for a card that shares a trait with the chosen card, reveal it, and
    draw it" (Psychometry LOF_219), whose ``then_deck_search_shared_trait`` window
    runs an ordinary ``deck_search`` over the chosen card's traits.

    ``exclude_ids`` drops specific instances from the candidate set — an EVENT is
    already in its owner's discard by the time its own ability resolves, so "put
    ANOTHER card in a discard pile …" must exclude the event itself (Commence
    Patrol JTL_205) while still offering a second copy of the same card."""
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    piles = ([s.player_by_id(controller_id)] if own_only else list(s.players))
    skip = set(exclude_ids or ())
    candidate_ids = [ci.instance_id for pl in piles for ci in pl.discard
                     if ci.instance_id not in skip
                     and (eligible is None or eligible(ci.card_def))]
    if not candidate_ids or int(count) <= 0:
        return
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="bottom_from_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "then_create_token": then_create_token,
            "then_draw": int(then_draw),
            "then_create_credit": int(then_create_credit),
            "then_play_from_hand": dict(then_play_from_hand or {}) or None,
            "then_damage_enemy_base": int(then_damage_enemy_base),
            "then_heal_base": int(then_heal_base),
            "disposition": str(disposition),
            "then_deck_search_shared_trait": then_deck_search_shared_trait,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="bottom_from_discard"))


def push_return_from_discard(
    s: GameState, source_ci: CardInstance,
    *,
    count: int,
    eligible: Callable[[object], bool],
    up_to: bool = True,
    eligible_instance: Callable[["CardInstance"], bool] | None = None,
) -> None:
    """Push a 'return_from_discard' decision: "Return up to ``count`` <eligible>
    cards from your discard pile to your hand."

    Parameters
    ----------
    count
        Maximum number of cards the controller may return.
    eligible
        Predicate on a card_def — only matching cards in the controller's discard
        pile are offered as candidates.  Evaluated once, at push time; the
        resulting ids are stored, so the decision context stays JSON-serialisable.
    up_to
        True (the only mode today) means a FinishReturnFromDiscard is always
        offered, so returning 0 is legal ("You may return …").
    eligible_instance
        Optional extra predicate on the *CardInstance* (not just its card_def), so
        an instance-level restriction can be applied alongside ``eligible`` — e.g.
        "units that were **defeated this phase**" (Admiral Trench TWI_86), which is
        a property of the instance (its id in ``game_memory.units_defeated_this_round``),
        not of the printed card.  Like ``eligible`` it is evaluated once at push
        time and only the resulting ids are stored.

    Pushed only when at least one eligible card is present; otherwise the effect
    fizzles cleanly with no prompt and the caller hands the turn over.
    """
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [ci.instance_id for ci in ps.discard
                     if eligible(ci.card_def)
                     and (eligible_instance is None or eligible_instance(ci))]
    if not candidate_ids or int(count) <= 0:
        return  # nothing eligible — fizzle cleanly
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="return_from_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "up_to": bool(up_to),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="return_from_discard",
    ))


def _return_from_discard_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top return_from_discard decision (never empty: a
    FinishReturnFromDiscard is always offered for the "up to" / "you may")."""
    ctx = top.context
    selected = set(ctx["selected_ids"])
    remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
    acts: list[Action] = [SelectDiscardCard(cid) for cid in remaining]
    acts.append(FinishReturnFromDiscard())
    return acts


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

@dataclass
class SelectDistinctDiscardCard(Action):
    """Select one differently-named card for Doctor Aphra SHD_15's deploy pick."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_distinct_return_random"):
            raise IllegalActionError("No select_distinct_return_random decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in _distinct_discard_candidates(s, ctx):
            raise IllegalActionError(f"{self.instance_id} is not a legal distinct-name pick")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["count"]):
            return _finish_distinct_return_random(s)
        return s

    def describe(self) -> str:
        return f"Choose {self.instance_id} (different name) from the discard pile"


def _distinct_discard_candidates(s: GameState, ctx: dict) -> list[str]:
    """Instance ids in the controller's discard that are still legal to pick: not
    already selected and bearing a name not shared by any already-selected card."""
    ps = s.player_by_id(ctx["controller_id"])
    selected = set(ctx["selected_ids"])
    chosen_names = {ci.card_def.display_name for ci in ps.discard
                    if ci.instance_id in selected}
    return [ci.instance_id for ci in ps.discard
            if ci.instance_id not in selected
            and ci.card_def.display_name not in chosen_names]


def _finish_distinct_return_random(s: GameState) -> GameState:
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected = list(ctx["selected_ids"])
    chosen = [ci for ci in ps.discard if ci.instance_id in set(selected)]
    returned = None
    if chosen:
        rng = s.make_rng()
        returned = rng.choice(chosen)
        s.rng_state = rng.getstate()
        ps.discard.remove(returned)
        returned.zone = Zone.HAND
        returned.face_down = False
        ps.hand.append(returned)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_distinct_return_random",
        choice=(f"returned {returned.card_def.display_name} at random"
                if returned is not None else "returned nothing"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_select_distinct_return_random(
    s: GameState, source_ci: CardInstance, *, count: int) -> None:
    """Push Doctor Aphra SHD_15's deploy decision.  Pushed only when the controller
    has ≥ ``count`` distinct card names in their discard pile; otherwise "Choose N
    cards … with different names" cannot be satisfied, so the effect does nothing."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    distinct_names = {ci.card_def.display_name for ci in ps.discard}
    if int(count) <= 0 or len(distinct_names) < int(count):
        return
    owner_idx = s.player_index(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard]
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="select_distinct_return_random",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "count": int(count),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="select_distinct_return_random"))


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

@dataclass
class DiscardRevealed(Action):
    """Set aside one of the revealed top cards — to the discard pile (For a Cause
    I Believe In, SOR_152) or the bottom of the deck (Rogue One, LAW_119),
    according to the decision's ``disposition`` (default ``"discard"``)."""
    card_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_top"):
            raise IllegalActionError("No reveal_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.card_id not in ctx["pending"]:
            raise IllegalActionError(f"{self.card_id} is not a revealed card")
        ctx["pending"].remove(self.card_id)
        ps = s.player_by_id(ctx["controller_id"])
        disposition = ctx.get("disposition", "discard")
        for i, c in enumerate(ps.deck):
            if c.instance_id == self.card_id:
                card = ps.deck.pop(i)
                if disposition == "bottom":
                    card.zone = Zone.DECK
                    ps.deck.append(card)            # to the bottom of the deck
                else:
                    card.zone = Zone.DISCARD
                    ps.discard.append(card)
                    note_hand_or_deck_discard(s, card)
                break
        _maybe_finish_reveal_top(s, top)
        return s

    def describe(self) -> str:
        return f"Set aside revealed {self.card_id}"


@dataclass
class KeepRevealed(Action):
    """Keep one of the revealed top cards, placing it next on top of the deck
    (For a Cause I Believe In, SOR_152)."""
    card_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_top"):
            raise IllegalActionError("No reveal_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.card_id not in ctx["pending"]:
            raise IllegalActionError(f"{self.card_id} is not a revealed card")
        ctx["pending"].remove(self.card_id)
        ctx["kept_order"].append(self.card_id)
        _maybe_finish_reveal_top(s, top)
        return s

    def describe(self) -> str:
        return f"Keep revealed {self.card_id} on top"


def _maybe_finish_reveal_top(s: GameState, top: "PendingDecision") -> None:
    """When every revealed card is resolved, reorder the kept cards to the top of
    the deck (in the chosen order) and pop the decision."""
    ctx = top.context
    if ctx["pending"]:
        return
    ps = s.player_by_id(ctx["controller_id"])
    kept_set = set(ctx["kept_order"])
    by_id = {c.instance_id: c for c in ps.deck if c.instance_id in kept_set}
    below = [c for c in ps.deck if c.instance_id not in kept_set]
    new_top = [by_id[k] for k in ctx["kept_order"] if k in by_id]
    ps.deck = new_top + below
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_top",
        choice=f"kept {len(new_top)} on top",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index


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

def push_reveal_cost_damage(
    s: GameState, source_ci: CardInstance, target_id: Optional[str],
    *, max_reveals: int = 7, threshold: int = 7,
) -> None:
    """Push a 'reveal_cost_damage' decision (Don't Get Cocky SOR_223).

    ``target_id`` is the pre-chosen unit (via the CustomEffect.target seam).  The
    decision fizzles cleanly (no push) when the target is gone or the deck is
    empty — nothing to reveal, no damage.
    """
    if target_id is None or s.find_instance(target_id) is None:
        return
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return  # empty deck — nothing to reveal
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_cost_damage",
        context={
            "source_id": source_ci.instance_id,
            "source_name": source_ci.card_def.display_name,
            "controller_id": source_ci.owner_id,
            "target_id": target_id,
            "revealed_ids": [],
            "revealed": [],
            "tally": 0,
            "max_reveals": int(max_reveals),
            "threshold": int(threshold),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_cost_damage",
    ))


@dataclass
class RevealNextCard(Action):
    """Reveal the next top card of the deck for a reveal_cost_damage decision,
    adding its cost to the running tally (Don't Get Cocky SOR_223)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cost_damage"):
            raise IllegalActionError("No reveal_cost_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        idx = len(ctx["revealed_ids"])
        if idx >= len(ps.deck) or idx >= int(ctx["max_reveals"]):
            raise IllegalActionError("No more cards may be revealed")
        card = ps.deck[idx]
        ctx["revealed_ids"].append(card.instance_id)
        ctx["revealed"].append({
            "instance_id": card.instance_id,
            "card_id": card.card_def.id,
            "card_name": card.card_def.display_name,
            "cost": getattr(card.card_def, "cost", 0) or 0,
        })
        ctx["tally"] = int(ctx["tally"]) + (getattr(card.card_def, "cost", 0) or 0)
        # Auto-finish when the cap is hit or the deck is now exhausted.
        if (len(ctx["revealed_ids"]) >= int(ctx["max_reveals"])
                or len(ctx["revealed_ids"]) >= len(ps.deck)):
            return _finish_reveal_cost_damage(s)
        return s

    def describe(self) -> str:
        return "Reveal the next card"


@dataclass
class StopRevealing(Action):
    """Stop the reveal_cost_damage loop and resolve (Don't Get Cocky SOR_223)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cost_damage"):
            raise IllegalActionError("No reveal_cost_damage decision pending")
        return _finish_reveal_cost_damage(copy.deepcopy(state))

    def describe(self) -> str:
        return "Stop revealing"


def _finish_reveal_cost_damage(s: GameState) -> GameState:
    """Pop the reveal_cost_damage decision: deal the tallied damage (if within the
    threshold) to the chosen unit, then bottom every revealed card in a
    seeded-random order."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    n = len(ctx["revealed_ids"])
    tally = int(ctx["tally"])
    threshold = int(ctx["threshold"])

    # Pop-then-deal: the decision is already off the stack, so a defeat trigger
    # from this damage lands on a clean stack.
    if 0 < tally <= threshold:
        tid = ctx["target_id"]
        if tid and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, tid, tally, source_name=ctx.get("source_name"))

    # Bottom the revealed cards (the top ``n`` of the deck) in a seeded-random order.
    revealed = ps.deck[:n]
    rest = ps.deck[n:]
    rng = s.make_rng()
    rng.shuffle(revealed)
    s.rng_state = rng.getstate()
    for c in revealed:
        c.zone = Zone.DECK
    ps.deck = rest + revealed

    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_cost_damage",
        choice=(f"revealed {n} (cost {tally}); dealt {tally}"
                if 0 < tally <= threshold
                else f"revealed {n} (cost {tally}); dealt 0"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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
#    LOF_201) ───────────────────────────────────────────────────────────────────
#
# "You may exhaust any number of units with combined cost 6 or less."  A
# self-contained multi-select decision (the Invisible Hand TWI_234 select-shape,
# but budget-bounded instead of trait-filtered, with NO payoff and no
# friendly/enemy restriction — the controller points it at enemy units).  Each
# pick exhausts the unit inline and spends its printed cost against the budget; a
# unit is eligible only while it is ready and its printed cost ≤ the remaining
# budget.  "Any number" includes 0 — FinishExhaustCombined is always offered.

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
#    (Dismantle the Conspiracy SEC_106) ─────────────────────────────────────────
#
# "A friendly unit captures any number of enemy non-leader units with a total of
# 7 or less remaining HP."  The exhaust_combined_cost select-shape, but the weight
# is each candidate's *remaining* HP and the pick captures the unit (under the
# pre-chosen friendly captor) instead of exhausting it.  A unit is eligible only
# while it is an enemy non-leader whose remaining HP ≤ the remaining budget.  "Any
# number" includes 0 — FinishCaptureCombined is always offered.

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

@dataclass
class PayResourceForToken(Action):
    """Pay one ready resource toward Curious Flock LOF_255 — exhausts a resource and
    gives one Experience token to the source unit."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_resources_for_tokens"):
            raise IllegalActionError("No pay_resources_for_tokens decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if not _pay_resources_for_tokens_can_pay(s, ctx):
            raise IllegalActionError("Cannot spend another cost item")
        ps = s.player_by_id(ctx["controller_id"])
        if ctx.get("cost_source") == "credit":
            _defeat_credit(s, ps)          # defeat a friendly Credit token (Cad Bane)
        elif ctx.get("cost_source") == "return_resource":
            _return_one_resource_to_owner(s, ps)   # Intimidator LAW_140
        else:
            _exhaust_resources(ps, 1)
        ctx["paid"] = int(ctx.get("paid", 0)) + 1
        if ctx.get("payoff") == "credit":
            # "For each resource returned this way, create a Credit token"
            # (Intimidator LAW_140).  A Credit is a pile entry, not a card entering
            # play, so it needs no pop-then-act care and is granted inline.
            from swu.engine.tokens import create_credit_token
            create_credit_token(s, ps)
        # The token-upgrade payoff is granted inline; the damage (SOR_138) and
        # token-unit (TWI_125) payoffs are tallied via ``paid`` and settled once at
        # resolve (pop-then-act), so nothing is granted here for those.
        if ctx.get("payoff", "token") == "token":
            # ``token_target_id`` puts the tokens on a CHOSEN unit rather than the
            # source ("Choose a non-leader unit and pay any number of resources.
            # For each resource paid this way, give an Experience token to the
            # chosen unit" — Emergency Powers SEC_40).  A target that has left play
            # simply receives nothing.
            result = s.find_instance(ctx.get("token_target_id") or ctx["source_id"])
            if result is not None:
                owner_ps, token_host = result
                from swu.engine.tokens import attach_token
                attach_token(s, owner_ps, token_host, ctx.get("token_type", "Experience"))
        # Auto-resolve once the cap is hit or no ready resource remains.
        if not _pay_resources_for_tokens_can_pay(s, ctx):
            return _resolve_pay_resources_for_tokens(s, top)
        return s

    def describe(self) -> str:
        return "Pay a resource for an Experience token"


@dataclass
class FinishPayResources(Action):
    """Stop paying resources ("up to N") — tokens were given inline as each resource
    was paid, so this just pops the decision (Curious Flock LOF_255)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_resources_for_tokens"):
            raise IllegalActionError("No pay_resources_for_tokens decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_pay_resources_for_tokens(s, top)

    def describe(self) -> str:
        return "Finish paying resources"


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

@dataclass
class ChooseRevealDeck(Action):
    """Choose which player's deck top to reveal (Vermillion LAW_215, choose_deck
    stage)."""
    deck_owner_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_deck":
            raise IllegalActionError("reveal_play_credit decision is past the choose_deck stage")
        if self.deck_owner_id not in ctx.get("deck_player_ids", []):
            raise IllegalActionError(f"{self.deck_owner_id}'s deck cannot be revealed")
        deck = s.player_by_id(self.deck_owner_id).deck
        if not deck:
            raise IllegalActionError(f"{self.deck_owner_id}'s deck is empty")
        top_card = deck[0]
        ctx["deck_owner_id"] = self.deck_owner_id
        ctx["revealed_id"] = top_card.instance_id
        ctx["revealed_card_name"] = top_card.card_def.display_name
        ctx["revealed_card_def_id"] = top_card.card_def.id
        ctx["revealed_cost"] = int(getattr(top_card.card_def, "cost", 0) or 0)
        ctx["stage"] = "choose_player"
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["controller_id"],
            kind="reveal_play_credit",
            choice=f"revealed {top_card.card_def.display_name}",
        ))
        return s

    def describe(self) -> str:
        return f"Reveal the top of {self.deck_owner_id}'s deck"


@dataclass
class ChooseRevealPlayer(Action):
    """Choose the player who may play the revealed card (Vermillion LAW_215,
    choose_player stage)."""
    player_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_player":
            raise IllegalActionError("reveal_play_credit decision is not at the choose_player stage")
        if self.player_id not in (ctx["controller_id"], ctx["opponent_id"]):
            raise IllegalActionError(f"{self.player_id} is not a valid player to choose")
        ctx["play_player_id"] = self.player_id
        ctx["stage"] = "may_play"
        top.deciding_player_id = self.player_id
        s.active_player_index = s.player_index(self.player_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["controller_id"],
            kind="reveal_play_credit",
            choice=f"chose {self.player_id} to play",
        ))
        return s

    def describe(self) -> str:
        return f"Let {self.player_id} play the revealed card"


@dataclass
class PlayRevealedCard(Action):
    """Play the revealed card for free (Vermillion LAW_215, may_play stage).

    A unit/event resolves immediately (then the other player makes Credits); an
    upgrade advances to the choose_host stage so the playing player picks a host
    before the upgrade is attached."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "may_play":
            raise IllegalActionError("reveal_play_credit decision is not at the may_play stage")
        if not _revealed_is_playable(s, ctx):
            raise IllegalActionError("The revealed card cannot be played")
        ci = _find_revealed(s, ctx)
        if isinstance(ci.card_def, Upgrade):
            ctx["stage"] = "choose_host"
            return s   # the playing player picks a host next (decision stays)
        return _resolve_play_revealed(s, top, host_id=None)

    def describe(self) -> str:
        return "Play the revealed card for free"


@dataclass
class DeclineRevealedCard(Action):
    """Decline to play the revealed card — it stays on top of its deck (Vermillion
    LAW_215, the "may play")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") not in ("may_play", "choose_host"):
            raise IllegalActionError("reveal_play_credit decision is not at a play stage")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_play_credit",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = int(ctx["final_active_idx"])
        return s

    def describe(self) -> str:
        return "Decline to play the revealed card"


@dataclass
class ChooseRevealHost(Action):
    """Pick the host for a revealed upgrade being played for free (Vermillion
    LAW_215, choose_host stage)."""
    host_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_host":
            raise IllegalActionError("reveal_play_credit decision is not at the choose_host stage")
        if self.host_id not in _revealed_upgrade_hosts(s, ctx):
            raise IllegalActionError(f"{self.host_id} is not a legal host")
        return _resolve_play_revealed(s, top, host_id=self.host_id)

    def describe(self) -> str:
        return f"Attach the revealed upgrade to {self.host_id}"


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
class SelectTokenTarget(Action):
    """Give a token to one eligible unit and (if more remain) keep selecting
    (Medal Ceremony SOR_245)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_token"):
            raise IllegalActionError("No select-token decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _select_token_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible token target")
        result = s.find_instance(self.target_id)
        if result is not None:
            ps, ci = result
            if ctx.get("token_type"):
                from swu.engine import tokens
                # ``token_count`` gives MORE THAN ONE token per chosen unit —
                # "give 2 Experience tokens to it" (The Burden of Masters LOF_125);
                # 1 (the default) is every prior caller.
                for _ in range(max(1, int(ctx.get("token_count", 1) or 1))):
                    tokens.attach_token(s, ps, ci, ctx["token_type"])
            # A SECOND token of a DIFFERENT kind on each chosen unit — "give an
            # Experience token AND a Shield token to a unit" (The Ghost LAW_69);
            # ``token_count`` only repeats the one kind.
            if ctx.get("extra_token_type"):
                from swu.engine import tokens as _tk
                _tk.attach_token(s, ps, ci, ctx["extra_token_type"])
            # BUFF mode: instead of (or as well as) a token, each chosen unit takes
            # a stat modifier — "Give each chosen unit +2/+2 for this phase"
            # (Kalani TWI_85).  Same select-up-to-N flow; only the payoff differs.
            if ctx.get("power_bonus") or ctx.get("hp_bonus"):
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.target_id,
                    kind="stats",
                    value={"power": int(ctx.get("power_bonus", 0) or 0),
                           "hp": int(ctx.get("hp_bonus", 0) or 0)},
                    duration=ctx.get("duration", "this_phase"),
                ))
            # READY mode: "Ready up to 3 units.  Each of those units gets +1/+0
            # and gains Overwhelm for this phase" (Planetary Invasion TWI_178) —
            # the same select-up-to-N flow with two more payoffs stacked on the
            # buff.  A keyword grant rides the same ``duration`` as the stats.
            if ctx.get("ready"):
                ci.exhausted = False
            # EXHAUST mode (No One Ever Knew SEC_196), honouring Protection exactly
            # as the declarative ExhaustCard arm does.
            if ctx.get("exhaust"):
                from swu.abilities.resolver import _target_protected
                src = s.find_instance(ctx["source_id"])
                src_ci = src[1] if src is not None else None
                if src_ci is None or not _target_protected(
                        s, self.target_id, src_ci, "exhaust"):
                    ci.exhausted = True
            # SUPPRESS mode: "Choose any number of friendly units.  They lose all
            # abilities for this round" (Kazuda Xiono JTL_18) — the same
            # select-up-to-N flow whose payoff is the unified ability-suppression
            # read-layer flag (Mind Trick LOF_202), lifted at the round rollover.
            if ctx.get("suppress_abilities"):
                ci.abilities_suppressed = True
            for kw in ctx.get("grant_keywords") or []:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.target_id,
                    kind="keyword_grant",
                    value={"keyword": kw, "value": 0},
                    duration=ctx.get("duration", "this_phase"),
                ))
        ctx["chosen"].append(self.target_id)
        ctx["remaining"] = int(ctx["remaining"]) - 1
        # Stop when the cap is reached or no further eligible unit remains.
        if int(ctx["remaining"]) <= 0 or not _select_token_targets(s, ctx):
            return _resolve_select_token(s, top)
        return s

    def describe(self) -> str:
        return f"Choose {self.target_id}"


@dataclass
class FinishSelectToken(Action):
    """Stop selecting token targets ("up to N") — resolve the decision (Medal
    Ceremony SOR_245)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_token"):
            raise IllegalActionError("No select-token decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_select_token(s, top)

    def describe(self) -> str:
        return "Finish giving tokens"


@dataclass
class DiscloseSelectCard(Action):
    """Reveal one hand card toward a 'disclose' requirement (Karis Nemik SEC_148,
    Syril Karn SEC_133).  Each revealed card contributes its aspect icons; once the
    required aspect multiset is covered the payoff auto-resolves.  Revealing does
    not move the card — it is public info only."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "disclose"):
            raise IllegalActionError("No disclose decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id not in _disclose_selectable(s, ctx):
            raise IllegalActionError(
                f"{self.instance_id} cannot be disclosed here")
        result = s.find_instance(self.instance_id)
        _, ci = result
        ctx["revealed"].append(self.instance_id)
        needed = ctx["required"]
        if ctx.get("any_of"):
            # "Disclose Vigilance, Command, Aggression, Cunning, OR Heroism (reveal a
            # card from your hand with this aspect icon)" — Leia Organa SEC_4.  One
            # card bearing ANY listed icon satisfies the whole requirement, so the
            # remaining multiset is cleared outright.
            for a in list(needed):
                needed[a] = 0
        else:
            for a in ci.card_def.aspect_names:
                if int(needed.get(a, 0)) > 0:
                    needed[a] = int(needed[a]) - 1
        if not _disclose_needed(ctx):
            return _resolve_disclose(s, top, success=True)
        return s

    def describe(self) -> str:
        return f"Disclose {self.instance_id}"


@dataclass
class DeclineDisclose(Action):
    """Decline to disclose (the "you may") — no payoff."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "disclose"):
            raise IllegalActionError("No disclose decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_disclose(s, top, success=False)

    def describe(self) -> str:
        return "Don't disclose"


def deploy_leader_as_effect(s: GameState, leader_id: str) -> GameState:
    """Deploy a specific undeployed leader as the *result of a card ability*.

    Grogu ASH_18 "you may deploy him".  No resource / threshold cost is paid; a
    no-op if the leader is already deployed or not in its base zone.  The turn-flow
    switch is the resolver's job (this runs inside trigger resolution), so this
    only flips the leader in and fires the deploy bus via ``_deploy_leader_into_arena``.
    """
    for ps in s.players:
        leader_ci = ps.leader_instance
        if (leader_ci is not None and leader_ci.instance_id == leader_id
                and not leader_ci.deployed and leader_ci in ps.base_zone):
            return _deploy_leader_into_arena(s, ps, leader_ci)
    return s


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
def _select_distinct_return_random_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [SelectDistinctDiscardCard(cid)
            for cid in _distinct_discard_candidates(state, top.context)]

# ── Bottom up-to-N cards from a discard pile (Restock SOR_252) ─────────
def _bottom_from_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    selected = set(ctx["selected_ids"])
    acts = [SelectBottomDiscardCard(cid) for cid in ctx["candidate_ids"]
            if cid not in selected]
    acts.append(FinishBottomFromDiscard())
    return acts

# ── Select up to N units, give each a token (Medal Ceremony SOR_245) ──
def _select_token_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectTokenTarget(tid) for tid in _select_token_targets(state, top.context)]
    # "up to" — stopping early is always legal, EXCEPT for a mandatory clause
    # with a pick still available ("An opponent gives 2 Advantage tokens to a
    # unit they control", Sabine Wren ASH_6).  Still offered when nothing is
    # eligible, so legal_actions can never come back empty.
    if not (top.context.get("mandatory") and acts):
        acts.append(FinishSelectToken())
    return acts

# ── Disclose: reveal hand cards bearing aspect icons (Karis/Syril) ────
def _disclose_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [DiscloseSelectCard(tid)
            for tid in _disclose_selectable(state, top.context)]
    acts.append(DeclineDisclose())  # the "you may" — declining is always legal
    return acts

# ── Deal 1 damage to each of up to N units (IG-2000 JTL_140) ──────────

# ── Receiving player assigns all indirect damage to one target ──────────

# ── Peek at top of deck (R2-D2 SOR_236, C-3PO SOR_238) ────────────────

# ── Choose a number (C-3PO SOR_238) ───────────────────────────────────

# ── Look at an opponent's hand (Viper Probe Droid SOR_228) ────────────

# ── Modal "choose one" (Leia Organa SOR_189) ──────────────────────────

# ── Opponent-decided modal: Let the Wookiee Win (SHD_205) ──────────────

# ── Reveal top, discard any, reorder the rest on top (For a Cause I
#    Believe In, SOR_152) ─────────────────────────────────────────────────
def _reveal_top_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    for cid in top.context["pending"]:
        acts.append(KeepRevealed(cid))
        acts.append(DiscardRevealed(cid))
    return acts

# ── Reveal-until-stop, damage = combined cost (Don't Get Cocky SOR_223) ─
def _reveal_cost_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    ps = state.player_by_id(ctx["controller_id"])
    n = len(ctx["revealed_ids"])
    acts2: list[Action] = []
    if n < int(ctx["max_reveals"]) and n < len(ps.deck):
        acts2.append(RevealNextCard())
    acts2.append(StopRevealing())
    return acts2

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
#    SOR_185 On Attack) ─────────────────────────────────────────────────────
def _name_and_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    names = sorted(top.context.get("eligible_names")
                   or {c["card_name"] for c in top.context["revealed_hand"]})
    acts: list[Action] = [NameAndDiscard(n) for n in names]
    if top.context.get("optional"):
        acts.append(DeclineNameAndDiscard())
    return acts

# ── Opponent may discard a random card, else create tokens (Political

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

# ── The defending player may rescue one of their own cards guarded by the

# ── Choose any number of friendly units, each captures an enemy non-leader

# ── Choose any number of friendly units; their combined power caps a free

# ── For each exploited unit, you may deal its power to an enemy unit
#    (Count Dooku TWI_138) ──────────────────────────────────────────────────
def _per_exploit_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [DealExploitDamage(tid)
            for tid in _per_exploit_enemy_targets(state, top.context)]
    acts.append(DeclineExploitDamage())  # "you may" — skipping is legal
    return acts

# ── Pay up to N resources, give that many Experience tokens to this unit
#    (Curious Flock LOF_255) ─────────────────────────────────────────────────
def _pay_resources_for_tokens_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    if _pay_resources_for_tokens_can_pay(state, top.context):
        acts.append(PayResourceForToken())
    acts.append(FinishPayResources())  # "up to" — paying 0 is legal
    return acts

# ── Reveal a deck top, a chosen player plays it free, a different player
#    makes Credits = its cost (Vermillion LAW_215) ──────────────────────────
def _reveal_play_credit_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    stage = ctx.get("stage")
    if stage == "choose_deck":
        return [ChooseRevealDeck(pid)
                for pid in ctx.get("deck_player_ids", [])
                if state.player_by_id(pid).deck]
    if stage == "choose_player":
        return [ChooseRevealPlayer(ctx["controller_id"]),
                ChooseRevealPlayer(ctx["opponent_id"])]
    if stage == "may_play":
        acts: list[Action] = []
        if _revealed_is_playable(state, ctx):
            acts.append(PlayRevealedCard())
        acts.append(DeclineRevealedCard())
        return acts
    if stage == "choose_host":
        acts = [ChooseRevealHost(h) for h in _revealed_upgrade_hosts(state, ctx)]
        acts.append(DeclineRevealedCard())  # no legal host left → may still decline
        return acts
    return [DeclineRevealedCard()]

# ── Plot — play Plot cards from resources on a leader deploy (Garindan
#    SEC_186, Lurking Snub Fighter SEC_189) ────────────────────────────────
def _plot_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    allowed = set(top.context.get("plot_ids", []))
    acts = _plot_play_actions(state, deciding_ps, allowed)
    acts.append(FinishPlot())  # "you may" — declining the rest is always legal
    return acts


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

def push_reveal_top_discard_reorder(
    s: GameState, source_ci: CardInstance, *, count: int = 4, aspect: str = "Heroism",
    deal_aspect_damage: bool = True, disposition: str = "discard",
) -> None:
    """Reveal/look at the top ``count`` cards of the controller's deck, then push a
    'reveal_top' decision letting the controller set aside any of them and put the
    rest back on top in any order.

    ``deal_aspect_damage`` (default True) — before the decision, deal 1 damage to
    the enemy base for each revealed card carrying ``aspect`` (For a Cause I
    Believe In SOR_152).  Set False for a plain "look at the top N and reorder"
    (Rogue One LAW_119), which deals no damage.

    ``disposition`` (default ``"discard"``) — where a *not-kept* revealed card
    goes: ``"discard"`` to the discard pile (SOR_152, a literal "discard"), or
    ``"bottom"`` to the bottom of the deck (Rogue One LAW_119, "put any number on
    the bottom").  ``DiscardRevealed`` reads this from the decision context;
    ``KeepRevealed`` always puts a card back on top regardless.

    The damage is dealt immediately (deterministic, no choice) before the
    decision is pushed.  When the deck has no cards there is nothing to reveal —
    no damage, no decision.  When the damage ends the game, no decision is pushed.
    """
    ps = s.player_by_id(source_ci.owner_id)
    revealed = ps.deck[:count]
    if revealed and deal_aspect_damage:
        n_aspect = sum(
            1 for c in revealed
            if aspect in {a.name for a in (getattr(c.card_def, "aspects", None) or ())}
        )
        if n_aspect > 0:
            opp = s.players[1 - s.player_index(source_ci.owner_id)]
            if opp.base_instance is not None:
                from swu.abilities.resolver import _apply_deal_damage
                _apply_deal_damage(s, opp.base_instance.instance_id, n_aspect,
                                   source_ci.card_def.display_name)
    if not revealed or s.is_terminal():
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_top",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "disposition": disposition,
            "pending": [c.instance_id for c in revealed],
            "kept_order": [],
            # The revealed cards' true identities, in their revealed (top→down)
            # order.  Safe to surface: the decision context is sent only to the
            # deciding player (its own deck), so the opponent never sees it.  The
            # UI renders these so the player can study each card before choosing
            # to discard it or keep it on top (the kept order = the new top order).
            "revealed": [
                {
                    "instance_id": c.instance_id,
                    "card_id": c.card_def.id,
                    "card_name": c.card_def.display_name,
                }
                for c in revealed
            ],
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_top",
    ))


# ── Repeated-modal push helper (Poe Dameron SHD_153) ──────────────────────────


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

@dataclass
class SelectDiscardUnitForDamage(Action):
    """Pick a unit from your discard pile to put on the bottom of your deck; its
    power becomes the damage magnitude (The Sarlacc of Carkoon LAW_163)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_unit_damage"
                or state.pending_decisions[-1].context.get("stage") != "select"):
            raise IllegalActionError("No discard_unit_damage (select) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard-unit candidate")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        # Bottom the chosen unit (discard pile → bottom of deck, face-down).  A
        # unit defeated while exhausted lands in discard still exhausted; a card
        # in the deck must be reset (no exhaust/damage out of play), so clear both.
        unit = next(ci for ci in ps.discard if ci.instance_id == self.instance_id)
        ps.discard.remove(unit)
        unit.zone = Zone.DECK
        unit.face_down = True
        unit.exhausted = False
        unit.damage = 0
        ps.deck.append(unit)
        ctx["amount"] = int(getattr(unit.card_def, "power", 0) or 0)
        ctx["recycled_name"] = unit.card_def.display_name
        # Advance to the damage step only if there is a legal target.
        if _sacrifice_damage_targets(s, ctx):
            ctx["stage"] = "target"
            return s
        return _resolve_discard_unit_damage(s, top, None)

    def describe(self) -> str:
        return f"Recycle {self.instance_id} from discard (deal its power)"


@dataclass
class ChooseDiscardDamageTarget(Action):
    """Deal the recycled unit's power to the chosen enemy ground unit and pop the
    discard_unit_damage decision (The Sarlacc of Carkoon LAW_163)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_unit_damage"
                or state.pending_decisions[-1].context.get("stage") != "target"):
            raise IllegalActionError("No discard_unit_damage (target) decision pending")
        if self.target_id not in _sacrifice_damage_targets(
                state, state.pending_decisions[-1].context):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_discard_unit_damage(s, top, self.target_id)

    def describe(self) -> str:
        return f"Deal recycled-unit damage to {self.target_id}"


def _resolve_discard_unit_damage(
    s: GameState, top, target_id: Optional[str]
) -> GameState:
    """Pop the discard_unit_damage decision, then deal the stored damage (if any).

    Damage is dealt AFTER popping (like push_sacrifice_resource_for_damage) so a
    defeat trigger from the damage lands on a clean stack."""
    ctx = top.context
    amount = int(ctx.get("amount", 0))
    recycled = ctx.get("recycled_name", "a unit")
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="discard_unit_damage",
        choice=(f"recycled {recycled}, dealt {amount} to {target_id}"
                if target_id else f"recycled {recycled} (no target)"),
    ))
    if target_id is not None and amount > 0:
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        _apply_deal_damage(s, target_id, amount, source_name=source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_discard_unit_then_damage(
    s: GameState, source_ci: CardInstance, *,
    target_controller: str = "enemy",
    target_arena: Optional[str] = "ground",
) -> None:
    """Push a 'discard_unit_damage' decision (The Sarlacc of Carkoon LAW_163):
    "Put a unit from your discard pile on the bottom of your deck.  Deal damage
    equal to that unit's power to a <target_controller> <target_arena> unit."

    Pushed only when the controller's discard pile holds at least one unit (the
    recycle is mandatory-if-able); the damage step is conditional on a legal target
    existing at select time."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard if isinstance(ci.card_def, Unit)]
    if not candidate_ids:
        return  # no unit in the discard pile — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="discard_unit_damage",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "select",
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "amount": 0,
            "target_controller": target_controller,
            "target_arena": target_arena,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="discard_unit_damage",
    ))


def _discard_unit_damage_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_unit_damage decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "select":
        return [SelectDiscardUnitForDamage(cid) for cid in ctx["candidate_ids"]]
    # stage "target"
    return [ChooseDiscardDamageTarget(t) for t in _sacrifice_damage_targets(state, ctx)]


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

@dataclass
class DiscardForSearch(Action):
    """Discard the chosen card from your hand (the cost), then search your deck and
    draw the matching card (Great Pit of Carkoon LAW_23, R2-D2 TWI_193)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_search"):
            raise IllegalActionError("No discard_for_search decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discardable card")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        unit = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(unit)
        unit.zone = Zone.DISCARD
        ps.discard.append(unit)
        note_hand_or_deck_discard(s, unit)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_search",
            choice=f"discarded {unit.card_def.display_name}",
        ))
        # Run the search (push a deck_search decision).  ``search_name`` None means
        # "any card" (R2-D2 "search for a card"); a string means name-match (Great
        # Pit's tutor); the window/count/up_to params are carried in the context.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            search_name = ctx.get("search_name")
            ps_now = s.player_by_id(ctx["controller_id"])
            window = int(ctx.get("search_window", len(ps_now.deck)))
            count = int(ctx.get("search_count", 1))
            up_to = bool(ctx.get("search_up_to", False))

            def _eligible(cd, _name=search_name):
                if _name is None:
                    return True
                return (getattr(cd, "name", None) or "") == _name

            push_deck_search(s, source_result[1], count=count, eligible=_eligible,
                             up_to=up_to, window=window)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} to search the deck"


@dataclass
class FinishDiscardForSearch(Action):
    """Decline the optional "you may discard a card" of a discard_for_search
    decision (R2-D2 TWI_193) — pop with no discard, no search."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_search"):
            raise IllegalActionError("No discard_for_search decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_search",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to discard"


def push_discard_for_search(
    s: GameState, source_ci: CardInstance, *,
    search_window: int,
    search_count: int = 1,
    search_up_to: bool = False,
    search_name: str | None = None,
    discard_units_only: bool = True,
    optional: bool = False,
) -> None:
    """Push a 'discard_for_search' decision: "Discard a card from your hand, then
    search the top ``search_window`` cards of your deck and draw the matching
    card(s)."

    Parameters
    ----------
    search_window / search_count / search_up_to
        Forwarded to the follow-up ``push_deck_search`` (how deep to search, how
        many to take, and whether taking 0 is legal).
    search_name
        ``None`` (R2-D2 TWI_193 "search for a card") — any card is eligible.
        A string (Great Pit of Carkoon LAW_23) — only a card with that exact name.
    discard_units_only
        True (Great Pit) — only Units may be discarded as the cost.  False (R2-D2)
        — any card.
    optional
        False (Great Pit) — the discard is a mandatory cost (no decline).  True
        (R2-D2 "You may discard a card from your hand") — a FinishDiscardForSearch
        decline is offered.

    Pushed only when ≥1 eligible discard candidate is in hand; otherwise the effect
    fizzles cleanly with no prompt (so R2-D2's mandatory trigger no-ops on an empty
    hand without needing a hand-size condition)."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    if discard_units_only:
        candidate_ids = [ci.instance_id for ci in ps.hand if isinstance(ci.card_def, Unit)]
    else:
        candidate_ids = [ci.instance_id for ci in ps.hand]
    if not candidate_ids:
        return  # nothing to discard — fizzle cleanly (gated upstream)
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="discard_for_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "search_name": search_name,
            "search_window": int(search_window),
            "search_count": int(search_count),
            "search_up_to": bool(search_up_to),
            "optional": bool(optional),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="discard_for_search",
    ))


def push_discard_unit_for_search(
    s: GameState, source_ci: CardInstance, *, search_name: str,
) -> None:
    """Push a 'discard_for_search' decision (Great Pit of Carkoon LAW_23): discard a
    chosen unit from your hand, then search your deck for a card named
    ``search_name``, reveal it, and draw it.

    Pushed only when the controller holds ≥1 Unit in hand (the discard cost is
    mandatory-if-able and the only way out is to pick a unit); the epic action is
    additionally gated by CONTROLLER_HAS_UNIT_IN_HAND so it is not offered (and the
    once-per-game epic not wasted) when there is nothing to discard.

    A thin wrapper over the generalised ``push_discard_for_search`` (whole-deck
    window, name-match, units-only, mandatory)."""
    push_discard_for_search(
        s, source_ci,
        search_window=len(s.player_by_id(source_ci.owner_id).deck),
        search_count=1, search_up_to=False,
        search_name=search_name, discard_units_only=True, optional=False,
    )


def _discard_for_search_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_for_search decision.  Never empty — the
    decision is only pushed with ≥1 discardable card; a FinishDiscardForSearch
    decline is added when the discard is "you may" (R2-D2 TWI_193)."""
    acts: list[Action] = [DiscardForSearch(cid) for cid in top.context["candidate_ids"]]
    if top.context.get("optional"):
        acts.append(FinishDiscardForSearch())
    return acts


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

@dataclass
class SelectRecurUnit(Action):
    """Recur a matching unit from your discard pile (recur_and_buff stage 'recur',
    Luminous Beings LOF_104).  Auto-advances to the buff stage at the cap."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "recur"):
            raise IllegalActionError("No recur_and_buff (recur) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"] or self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a recurrable unit")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ctx["selected_ids"].append(self.instance_id)
        remaining = [cid for cid in ctx["candidate_ids"] if cid not in ctx["selected_ids"]]
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]) or not remaining:
            return _finish_recur(s, top)
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of your deck"


@dataclass
class FinishRecur(Action):
    """Stop recurring units ("up to N") and move to the buff stage (Luminous
    Beings LOF_104)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "recur"):
            raise IllegalActionError("No recur_and_buff (recur) decision pending")
        s = copy.deepcopy(state)
        return _finish_recur(s, s.pending_decisions[-1])

    def describe(self) -> str:
        return "Finish putting units on the bottom of the deck"


def _finish_recur(s: GameState, top) -> GameState:
    """Move the selected discard units to the bottom of the deck in a random order,
    then either advance to the buff stage (if any were recurred and there is a unit
    to buff) or pop the decision."""
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected_set = set(ctx["selected_ids"])
    recurred = [ci for ci in ps.discard if ci.instance_id in selected_set]
    # Random order onto the bottom of the deck (deterministic via the seeded rng).
    rng = s.make_rng()
    rng.shuffle(recurred)
    s.rng_state = rng.getstate()
    for ci in recurred:
        ps.discard.remove(ci)
        ci.zone = Zone.DECK
        ci.face_down = True
        ci.exhausted = False
        ci.damage = 0
        ps.deck.append(ci)
    k = len(recurred)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="recur_and_buff",
        choice=f"bottomed {k} unit(s)",
    ))
    ctx["stage"] = "buff"
    ctx["buff_remaining"] = k
    ctx["buffed_ids"] = []
    # Advance to the buff stage only if we recurred ≥1 unit AND there is an
    # eligible unit to buff; otherwise the effect is done.
    if k > 0 and _recur_buff_targets(s, ctx):
        return s
    s.pending_decisions.pop()
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _recur_buff_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible buff targets for the recur_and_buff 'buff' stage (any in-play unit
    not already buffed this resolution)."""
    from swu.abilities.resolver import _gather_legal_targets, _spec_matches_ci
    from swu.abilities.registry import TargetSpec
    spec = TargetSpec(controller=ctx.get("buff_controller", "any"), kind="unit")
    buffed = set(ctx.get("buffed_ids", []))
    source_result = state.find_instance(ctx["source_id"])
    if source_result is not None:
        _, source_ci = source_result
        ids = _gather_legal_targets(state, spec, source_ci, {})
    else:
        ids = [ci.instance_id
               for ps in state.players
               for ci in ps.ground_arena + ps.space_arena
               if _spec_matches_ci(spec, ci, ci, state, {})]
    return [tid for tid in ids if tid not in buffed]


@dataclass
class SelectBuffTarget(Action):
    """Give the chosen unit +P/+H for this phase (recur_and_buff stage 'buff',
    Luminous Beings LOF_104).  Auto-pops once K units are buffed / none remain."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "buff"):
            raise IllegalActionError("No recur_and_buff (buff) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in _recur_buff_targets(state, ctx):
            raise IllegalActionError(f"{self.instance_id} is not an eligible buff target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        from swu.abilities.resolver import _make_modifier
        from swu.abilities.registry import Duration
        mod = _make_modifier(
            s, ctx["source_id"], self.instance_id,
            power=int(ctx["power"]), hp=int(ctx["hp"]),
            duration=Duration.THIS_PHASE,
        )
        s.modifiers.append(mod)
        ctx["buffed_ids"].append(self.instance_id)
        ctx["buff_remaining"] = int(ctx["buff_remaining"]) - 1
        if int(ctx["buff_remaining"]) <= 0 or not _recur_buff_targets(s, ctx):
            return _finish_recur_buff(s, top)
        return s

    def describe(self) -> str:
        return f"Give {self.instance_id} a stat bonus for this phase"


@dataclass
class FinishRecurBuff(Action):
    """Stop buffing units ("that many", capped by available) — resolve (Luminous
    Beings LOF_104)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "buff"):
            raise IllegalActionError("No recur_and_buff (buff) decision pending")
        s = copy.deepcopy(state)
        return _finish_recur_buff(s, s.pending_decisions[-1])

    def describe(self) -> str:
        return "Finish buffing units"


def _finish_recur_buff(s: GameState, top) -> GameState:
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="recur_and_buff",
        choice=f"buffed {len(ctx.get('buffed_ids', []))} unit(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_recur_and_buff(
    s: GameState, source_ci: CardInstance, *,
    max_select: int, trait: str, power: int, hp: int,
    buff_controller: str = "any",
) -> None:
    """Push a 'recur_and_buff' decision (Luminous Beings LOF_104): "Put up to
    ``max_select`` ``trait`` units from your discard pile on the bottom of your
    deck in a random order.  Give that many units +``power``/+``hp`` for this
    phase."

    Candidates are the controller's discard-pile Units carrying ``trait``.  Pushed
    only when ≥1 such unit exists (with none, "put 0, buff 0" is a clean no-op so
    the caller hands the turn over).  The buff targets (``buff_controller="any"``
    by default, mirroring the literal "units") are recomputed live so the cap of K
    = the number recurred is honoured even as units leave play."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard
                     if isinstance(ci.card_def, Unit) and trait in ci.card_def.traits]
    if not candidate_ids or int(max_select) <= 0:
        return  # no recurrable unit — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="recur_and_buff",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "recur",
            "candidate_ids": candidate_ids,
            "selected_ids": [],
            "max_select": int(max_select),
            "power": int(power),
            "hp": int(hp),
            "buff_controller": buff_controller,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="recur_and_buff",
    ))


def _recur_and_buff_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top recur_and_buff decision (never empty — a Finish is
    always offered for the 'up to' / 'that many' of each stage)."""
    ctx = top.context
    if ctx.get("stage") == "recur":
        selected = set(ctx["selected_ids"])
        remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
        acts: list[Action] = [SelectRecurUnit(cid) for cid in remaining]
        acts.append(FinishRecur())
        return acts
    acts = [SelectBuffTarget(tid) for tid in _recur_buff_targets(state, ctx)]
    acts.append(FinishRecurBuff())
    return acts


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

@dataclass
class SelectExcessHandCardToDiscard(Action):
    """The current player discards a chosen card from their hand toward the target
    hand size (Smoke and Cinders SOR_174).  Advances to the next player once the
    current player is down to ``keep`` cards, or resolves the decision."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_excess_from_hand"):
            raise IllegalActionError("No discard-excess decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        current = ctx["order"][ctx["idx"]]
        ps = s.player_by_id(current)
        card = next((ci for ci in ps.hand
                     if ci.instance_id == self.instance_id), None)
        if card is None or len(ps.hand) <= _discard_excess_keep(ctx, current):
            raise IllegalActionError(
                f"{self.instance_id} is not a discardable excess card")
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(s, card)
        tally = dict(ctx.get("discarded", {}))
        tally[current] = tally.get(current, 0) + 1
        ctx["discarded"] = tally
        s.event_log.append(DecisionResolved(
            deciding_player_id=current,
            kind="discard_excess_from_hand",
            choice=f"discarded {card.card_def.display_name}",
        ))
        # Advance past any players already down to (or below) the target size.
        while (ctx["idx"] < len(ctx["order"])
               and len(s.player_by_id(ctx["order"][ctx["idx"]]).hand)
               <= _discard_excess_keep(ctx, ctx["order"][ctx["idx"]])):
            ctx["idx"] += 1
        if ctx["idx"] < len(ctx["order"]):
            top.deciding_player_id = ctx["order"][ctx["idx"]]
            s.active_player_index = s.player_index(top.deciding_player_id)
            return s
        # Everyone is down to size — record the discard observers and pop.
        s.pending_decisions.pop()
        for pid, n in ctx["discarded"].items():
            if n:
                record_hand_discard(s, pid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} (down to hand size)"


def _discard_excess_keep(ctx: dict, player_id: str) -> int:
    """The target hand size for ``player_id`` in a discard_excess_from_hand decision.

    Two shapes share the walk: the printed "discard down to N" (a single ``keep``
    for everyone — Smoke and Cinders SOR_174) and "each player discards N cards"
    (Guerilla Insurgency TWI_177), which is per-player and so is pre-computed into
    a ``keeps`` map at push time from each hand's size.  Hand sizes only change
    through this decision itself, so pinning the targets up front is exact."""
    keeps = ctx.get("keeps")
    if keeps is not None:
        return int(keeps.get(player_id, 0))
    return int(ctx["keep"])


def push_discard_excess_from_hand(
    s: GameState, source_ci: CardInstance, *, keep: int = 2,
    count: Optional[int] = None,
) -> None:
    """Push a 'discard_excess_from_hand' decision (Smoke and Cinders SOR_174): each
    player discards down to ``keep`` cards of their choice, the source's controller
    first.  Pushed only when ≥1 player holds more than ``keep`` cards; otherwise it
    fizzles cleanly with no prompt.

    ``count`` switches to the sibling shape "each player discards ``count`` cards of
    their choice" (Guerilla Insurgency TWI_177) — each player's target hand size is
    their current size minus ``count``, floored at 0, so a short hand just discards
    all of it."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    order = [controller_id, opponent_id]
    keeps = None
    if count is not None:
        keeps = {pid: max(0, len(s.player_by_id(pid).hand) - int(count))
                 for pid in order}
    ctx = {
        "source_id": source_ci.instance_id,
        "order": order,
        "idx": 0,
        "keep": int(keep),
        "discarded": {},
    }
    if keeps is not None:
        ctx["keeps"] = keeps
    idx = 0
    while (idx < len(order)
           and len(s.player_by_id(order[idx]).hand)
           <= _discard_excess_keep(ctx, order[idx])):
        idx += 1
    if idx >= len(order):
        return  # nobody has excess — fizzle
    ctx["idx"] = idx
    dec = PendingDecision(
        deciding_player_id=order[idx],
        kind="discard_excess_from_hand",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(order[idx])
    s.event_log.append(DecisionPushed(
        deciding_player_id=order[idx],
        kind="discard_excess_from_hand",
    ))


def _discard_excess_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_excess_from_hand decision: the current
    player discards any one of their hand cards (never empty — the idx always points
    at a player still holding more than ``keep`` cards)."""
    ctx = top.context
    ps = state.player_by_id(ctx["order"][ctx["idx"]])
    if len(ps.hand) <= _discard_excess_keep(ctx, ps.player_id):
        return []
    return [SelectExcessHandCardToDiscard(ci.instance_id) for ci in ps.hand]


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

@dataclass
class NameAndDiscard(Action):
    """The controller names a card present in the opponent's revealed hand; one
    opponent card of that name is discarded (Chimaera SOR_185 On Attack)."""
    card_name: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "name_and_discard"):
            raise IllegalActionError("No name-and-discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        opp = s.player_by_id(ctx["opponent_id"])
        names = set(ctx.get("eligible_names")
                    or {c["card_name"] for c in ctx["revealed_hand"]})
        if self.card_name not in names:
            raise IllegalActionError(
                f"{self.card_name!r} is not a nameable card in the revealed hand")
        s.pending_decisions.pop()
        want_type = ctx.get("card_type")
        victim = next((ci for ci in opp.hand
                       if ci.card_def.display_name == self.card_name
                       and _name_discard_type_ok(ci.card_def, want_type)), None)
        if victim is not None:
            opp.hand.remove(victim)
            victim.zone = Zone.DISCARD
            opp.discard.append(victim)
            note_hand_or_deck_discard(s, victim)
            record_hand_discard(s, opp.player_id)
            # "If you do, that player draws a card" (Bazine Netal SHD_184).
            if ctx.get("discarder_draws"):
                _draw_cards(s, opp, 1)
            # "If the discarded card is a UNIT, for this phase you may play it from
            # their discard pile, ignoring its aspect penalties" (Mother Talzin
            # TS26_26) — the PAID cross-pile permission (Obi-Wan Kenobi SEC_205),
            # keyed to the naming player and pinned to this one instance.
            if ctx.get("then_foreign_discard_play"):
                from swu.cards.models import Unit
                if isinstance(victim.card_def, Unit):
                    led = s.game_memory.foreign_discard_play_this_phase
                    led.setdefault(ctx["controller_id"], []).append(
                        victim.instance_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="name_and_discard",
            choice=f"named {self.card_name}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Name {self.card_name}"


@dataclass
class DeclineNameAndDiscard(Action):
    """Decline an OPTIONAL name-and-discard (Bazine Netal SHD_184's "You may
    discard 1 of those cards")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "name_and_discard"):
            raise IllegalActionError("No name-and-discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="name_and_discard",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Discard nothing from the opponent's hand"


def _name_discard_type_ok(card_def, card_type: Optional[str]) -> bool:
    """Does ``card_def`` match a name_and_discard ``card_type`` filter?"""
    if not card_type:
        return True
    from swu.cards.models import Unit, Upgrade, Event
    if card_type == "non_unit":
        # "Discard a NON-UNIT card from it" (Tip the Scale LOF_226) — the
        # complement of the "unit" filter (an Upgrade or an Event).
        return not isinstance(card_def, Unit)
    cls = {"unit": Unit, "upgrade": Upgrade, "event": Event}.get(card_type)
    return cls is not None and isinstance(card_def, cls)


def push_name_and_discard(
    s: GameState, source_ci: CardInstance, *,
    optional: bool = False, discarder_draws: bool = False,
    card_type: Optional[str] = None, aspects_any: Optional[tuple] = None,
    then_foreign_discard_play: bool = False,
    namer_id: Optional[str] = None,
) -> None:
    """Push a 'name_and_discard' decision (Chimaera SOR_185 On Attack): the source's
    controller names a card in an opponent's hand and one copy is discarded.  Carries
    the opponent's hand identities (card_id + name only — never their hidden
    instance_ids, the look_hand precedent) in the controller's private context.
    Pushed only when the opponent holds ≥1 card; an empty hand fizzles with no
    prompt.

    ``optional`` adds a DeclineNameAndDiscard action ("You may discard 1 …");
    ``discarder_draws`` makes the discarding opponent draw a card after a discard
    ("If you do, that player draws a card") — Bazine Netal SHD_184, where the
    controller looks at the opponent's hand and may strip one card (the optimal-play
    collapse of a look-then-discard: the controller already sees the hand).

    ``card_type`` ("event" | "unit" | "upgrade") narrows what may be *named* while
    the whole hand is still revealed — "Look at an opponent's hand and discard an
    EVENT from it" (Jam Communications JTL_207).  With no card of that type in the
    hand the decision fizzles with no prompt, exactly as an empty hand does.

    ``aspects_any`` narrows it the other way: only a card sharing AT LEAST ONE of the
    listed aspects may be named — "discard a card from it that shares an aspect with
    that unit" (Hold For Questioning LAW_217, which passes the exhausted unit's own
    aspects).  Like ``card_type`` it filters what is NAMEABLE while the whole hand
    stays revealed, and an empty eligible set fizzles with no prompt (so the printed
    "If you do" costs nothing when their hand cannot match).

    ``then_foreign_discard_play`` is the settle-at-the-discard rider "If the discarded
    card is a unit, for this phase you may play it from their discard pile, ignoring
    its aspect penalties" (Mother Talzin TS26_26): the discarded instance is recorded
    in ``game_memory.foreign_discard_play_this_phase`` against the NAMING player — the
    PAID cross-pile permission built for Obi-Wan Kenobi SEC_205, whose branch of
    ``_enumerate_discard_play_actions`` already expresses the aspect waiver as a
    discount.  Pinned to that one instance, so a second copy already in the pile is
    not unlocked, and a non-unit discard unlocks nothing."""
    from swu.engine.events import HandInspected
    # ``namer_id`` shifts WHO names (and therefore whose hand is stripped) away from
    # the source's controller — the say_no SOR_233 decider shift.  "In player order,
    # each player discards a card from the hand of the player to their right"
    # (Reveal Intentions TS26_80) is two pushes of this decision, one per seat.
    controller_id = namer_id or source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    opp = s.players[1 - owner_idx]
    if not opp.hand:
        return
    want = {str(a) for a in (aspects_any or ())}
    eligible_names = sorted({
        ci.card_def.display_name for ci in opp.hand
        if _name_discard_type_ok(ci.card_def, card_type)
        and (not want or want & {getattr(a, "name", str(a))
                                 for a in (getattr(ci.card_def, "aspects", None) or ())})
    })
    if not eligible_names:
        return
    revealed = [
        {"card_id": ci.card_def.id, "card_name": ci.card_def.display_name}
        for ci in opp.hand
    ]
    s.event_log.append(HandInspected(
        inspecting_player_id=controller_id,
        revealed_player_id=opp.player_id,
        card_count=len(opp.hand),
    ))
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="name_and_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opp.player_id,
            "revealed_hand": revealed,
            "eligible_names": eligible_names,
            "card_type": card_type,
            "optional": bool(optional),
            "discarder_draws": bool(discarder_draws),
            "then_foreign_discard_play": bool(then_foreign_discard_play),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="name_and_discard",
    ))


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

def _disclose_needed(ctx: dict) -> dict:
    """The still-uncovered required aspect multiset (name -> remaining count > 0)."""
    return {a: int(c) for a, c in ctx.get("required", {}).items() if int(c) > 0}


def _disclose_selectable(state: GameState, ctx: dict) -> list[str]:
    """Hand cards of the discloser, not yet revealed, that carry ≥1 still-needed
    aspect icon (so every pick makes progress toward covering the requirement)."""
    needed = _disclose_needed(ctx)
    if not needed:
        return []
    ps = state.player_by_id(ctx["discloser_id"])
    revealed = set(ctx.get("revealed", []))
    out: list[str] = []
    for ci in ps.hand:
        if ci.instance_id in revealed:
            continue
        if any(a in needed for a in ci.card_def.aspect_names):
            out.append(ci.instance_id)
    return out


def _disclose_can_satisfy(state: GameState, discloser_id: str,
                          required: dict) -> bool:
    """Whether the discloser's hand collectively bears the required aspect multiset."""
    from collections import Counter
    pool: Counter = Counter()
    for ci in state.player_by_id(discloser_id).hand:
        pool += Counter(ci.card_def.aspect_names)
    return all(pool.get(a, 0) >= int(c) for a, c in required.items())


def push_disclose(
    s: GameState, source_ci: CardInstance, required_aspects: list[str], *,
    payoff: str, payoff_args: Optional[dict] = None,
    discloser_id: Optional[str] = None,
    decline_payoff: Optional[str] = None,
    decline_payoff_args: Optional[dict] = None,
    always_offer: bool = False,
    any_of: bool = False,
) -> None:
    """Push a 'disclose' decision (the disclose primitive).  ``required_aspects`` is
    the multiset of aspect-icon names to cover (e.g. ["Aggression","Heroism"]);
    ``payoff``/``payoff_args`` name the "if you do" effect (see
    ``_apply_disclose_payoff``).  Only pushed when the discloser CAN cover the
    requirement (else the "you may disclose" simply does nothing — no prompt).

    ``decline_payoff``/``decline_payoff_args`` are the mirror: an "If you DON'T, …"
    penalty run when the disclose is declined (Warrior of Clan Ordo SEC_164: "You may
    disclose [Aggression].  If you don't, deal 2 damage to your base").  Such a card
    also passes ``always_offer=True`` so the decision is pushed even when the hand
    cannot cover the requirement — the penalty must still land, and the discloser is
    simply left with only the Decline."""
    from collections import Counter
    discloser = discloser_id or source_ci.owner_id
    required = {a: int(c) for a, c in Counter(required_aspects).items()}
    if any_of:
        # DISJUNCTIVE requirement (Leia Organa SEC_4): one card bearing ANY of the
        # listed icons satisfies it, so "can satisfy" is an ANY test, not the
        # multiset one, and every listed aspect is needed=1 for candidate offering.
        required = dict.fromkeys(dict.fromkeys(required_aspects), 1)
        satisfiable = any(
            any(a in required for a in ci.card_def.aspect_names)
            for ci in s.player_by_id(discloser).hand)
        if not satisfiable and not always_offer:
            return
    elif not _disclose_can_satisfy(s, discloser, required) and not always_offer:
        return
    discloser_idx = s.player_index(discloser)
    dec = PendingDecision(
        deciding_player_id=discloser,
        kind="disclose",
        context={
            "source_id": source_ci.instance_id,
            "discloser_id": discloser,
            "required": required,
            "any_of": bool(any_of),
            "revealed": [],
            "payoff": payoff,
            "payoff_args": dict(payoff_args or {}),
            "decline_payoff": decline_payoff,
            "decline_payoff_args": dict(decline_payoff_args or {}),
        },
        # If disclose is the top decision when it resolves the discloser continues
        # (e.g. mid-attack); if a payoff pushes a further decision this is unused.
        after_resolve_player_index=discloser_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = discloser_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=discloser,
        kind="disclose",
    ))


def _resolve_disclose(s: GameState, top, *, success: bool) -> GameState:
    """Pop the 'disclose' decision; run the payoff if the discloser disclosed."""
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="disclose",
        choice=("disclosed" if success else "declined"),
    ))
    if success:
        # A successful Disclose reveals 1+ cards from the discloser's hand — record
        # it for the WhenYouRevealOrDiscard observer (Padmé Amidala SEC_16) before
        # the payoff runs (the ledger is drained at the settle-point either way).  A
        # reveal is NOT a discard, so kind="reveal" keeps it out of the discard-only
        # ledger (Migs Mayfeld SHD_163 must not fire on a Disclose).
        if ctx.get("revealed"):
            record_hand_discard(s, ctx["discloser_id"], kind="reveal")
        _apply_disclose_payoff(s, ctx)
    elif ctx.get("decline_payoff"):
        # "If you DON'T, …" (Warrior of Clan Ordo SEC_164) — the same payoff
        # dispatcher, keyed off the decline arm.
        _apply_disclose_payoff(s, {**ctx,
                                   "payoff": ctx["decline_payoff"],
                                   "payoff_args": ctx.get("decline_payoff_args", {})})
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _apply_disclose_payoff(s: GameState, ctx: dict) -> None:
    """Dispatch a disclosed card's "if you do" payoff (string key + serialisable
    args).  Each payoff reuses an existing seam; new disclose cards add an arm."""
    payoff = ctx.get("payoff")
    args = ctx.get("payoff_args", {})
    discloser_id = ctx["discloser_id"]
    if payoff == "create_ready_token":
        # Karis Nemik SEC_148: create a Spy token and ready it.
        ps = s.player_by_id(discloser_id)
        created = _create_token_units(
            s, ps, args["token_name"], int(args.get("count", 1)))
        for ci in created:
            ci.exhausted = False
        return
    if payoff == "experience_off_aspect_unit":
        # Leia Organa SEC_4: "give an Experience token to a unit that doesn't share
        # an aspect with the disclosed card."  The disclosed card's aspects come off
        # ctx["revealed"]; every in-play unit sharing none of them is whitelisted
        # into a select_token.  DOCUMENTED DEVIATION: select_token is an "up to",
        # so the printed mandatory gift can be declined.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None or not ctx.get("revealed"):
            return
        disclosed = s.find_instance(ctx["revealed"][-1])
        if disclosed is None:
            return
        shown = set(disclosed[1].card_def.aspect_names)
        eligible = [
            u.instance_id
            for p in s.players
            for arena in (p.ground_arena, p.space_arena)
            for u in arena
            if not (shown & set(u.card_def.aspect_names))
        ]
        if not eligible:
            return
        push_select_token(s, source_result[1], token_type="Experience",
                          max_targets=1, restrict_ids=eligible,
                          decider_id=discloser_id)
        return
    if payoff == "name_and_discard":
        # Charged with Espionage SEC_230: "look at an opponent's hand and discard a
        # unit from it" — the Chimaera SOR_185 decision, which already carries the
        # whole hand to the discloser and offers only names present (that IS the
        # look), narrowed by ``card_type``.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            push_name_and_discard(s, source_result[1],
                                  card_type=args.get("card_type"))
        return
    if payoff == "opponents_discard_random":
        # Duchess's Investigators SEC_223: "each opponent discards a RANDOM card
        # from their hand" — drawn from the seeded RNG, so replays reproduce.
        rng = s.make_rng()
        for opp in s.players:
            if opp.player_id == discloser_id or not opp.hand:
                continue
            card = opp.hand.pop(rng.randrange(len(opp.hand)))
            card.zone = Zone.DISCARD
            opp.discard.append(card)
            note_hand_or_deck_discard(s, card)
            record_hand_discard(s, opp.player_id, kind="discard")
        s.rng_state = rng.getstate()
        return
    if payoff == "opponent_discard":
        # Luthen's Haulcraft SEC_153: "that opponent discards N cards from their
        # hand" — the first-card discard convention (K-2SO SOR_145).
        opp = next((p for p in s.players if p.player_id != discloser_id), None)
        if opp is None:
            return
        moved = 0
        for _ in range(int(args.get("count", 1))):
            if not opp.hand:
                break
            card = opp.hand.pop(0)
            card.zone = Zone.DISCARD
            opp.discard.append(card)
            note_hand_or_deck_discard(s, card)
            moved += 1
        if moved:
            # ONE record per discard instruction, however many cards moved.
            record_hand_discard(s, opp.player_id, kind="discard")
        return
    if payoff == "create_token":
        # Faith in Your Friends SEC_211: create N token units (the plain sibling of
        # ``create_ready_token`` — these enter exhausted, the CR default).
        ps = s.player_by_id(discloser_id)
        _create_token_units(s, ps, args["token_name"], int(args.get("count", 1)))
        return
    if payoff == "damage_unless_discard":
        # Syril Karn SEC_133: deal N to the chosen unit unless its controller
        # discards a card (reuses the may_discard else-damage seam).
        source_result = s.find_instance(ctx["source_id"])
        source_ci = source_result[1] if source_result is not None else None
        push_may_discard_else_damage(
            s, source_ci, args.get("target_id"), int(args.get("amount", 0)))
        return
    if payoff == "self_base_damage":
        # Warrior of Clan Ordo SEC_164's DECLINE arm: "If you don't, deal N damage to
        # your base."  Also usable as a normal payoff; the discloser's own base.
        ps = s.player_by_id(discloser_id)
        if ps.base_instance is not None:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            name = (source_result[1].card_def.display_name
                    if source_result is not None else None)
            _apply_deal_damage(s, ps.base_instance.instance_id,
                               int(args.get("amount", 1)), name)
        return
    if payoff == "damage_unit":
        # Charged with Treason SEC_182: "If you do, deal N damage to a unit" — the
        # target was chosen up front (the Syril Karn SEC_133 convention).
        target_id = args.get("target_id")
        if target_id:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            name = (source_result[1].card_def.display_name
                    if source_result is not None else None)
            _apply_deal_damage(s, target_id, int(args.get("amount", 1)), name)
        return
    if payoff == "draw":
        # Mina Bonteri SEC_94: draw N cards (reuses the _draw_cards seam).
        ps = s.player_by_id(discloser_id)
        _draw_cards(s, ps, int(args.get("count", 1)))
        return
    if payoff == "heal_base":
        # Captain Typho SEC_98: heal N damage from the discloser's own base.
        ps = s.player_by_id(discloser_id)
        if ps.base_instance is not None:
            ps.base_instance.damage = max(
                0, ps.base_instance.damage - int(args.get("amount", 0)))
        return
    if payoff == "granted_attack":
        # Ahsoka Tano SEC_96: attack with another unit (reuses push_granted_attack).
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_granted_attack(
            s, source_result[1],
            exclude_source=bool(args.get("exclude_source", True)),
            no_base=bool(args.get("no_base", False)),
            allow_exhausted=bool(args.get("allow_exhausted", False)),
            optional=bool(args.get("optional", False)),
        )
        return
    if payoff == "buff_unit":
        # With Thunderous Applause SEC_129: give the pre-chosen "another" unit a
        # +power/+hp modifier for this phase (reuses the stat-modifier seam).  The
        # target was chosen up front (a cosmetic reorder, the Syril Karn SEC_133
        # convention); no-op if it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _make_modifier
            from swu.abilities.registry import Duration
            # ``duration`` widens the arm to "for this ATTACK" (Ebon Hawk SEC_219,
            # which buffs itself and debuffs the defender mid-combat); the default
            # stays SEC_129's this-phase reading.
            dur = (Duration.THIS_ATTACK if args.get("duration") == "this_attack"
                   else Duration.THIS_PHASE)
            s.modifiers.append(_make_modifier(
                s, ctx.get("source_id", ""), tid,
                power=int(args.get("power", 0)), hp=int(args.get("hp", 0)),
                duration=dur))
        return
    if payoff == "exhaust_unit":
        # Bog Down in Procedure SEC_234: exhaust the pre-chosen "another" unit
        # (honours Protection, mirroring the declarative ExhaustCard arm).
        # ``lock_round`` also flags the unit ``cannot_ready_this_round`` — Cantwell
        # Arrestor Cruiser SEC_37 ("That unit can't ready while this unit is in
        # play"): a documented simplification to "this round" using the existing
        # No-Good-to-Me-Dead SOR_186 keep-tapped flag (the persistent while-in-play
        # lock would need a new ready-lock modifier kind, out of scope here).
        tid = args.get("target_id")
        res = s.find_instance(tid) if tid is not None else None
        if res is not None:
            src = s.find_instance(ctx.get("source_id", ""))
            src_ci = src[1] if src is not None else None
            from swu.abilities.resolver import _target_protected
            if src_ci is None or not _target_protected(s, tid, src_ci, "exhaust"):
                res[1].exhausted = True
                if args.get("lock_round"):
                    res[1].cannot_ready_this_round = True
        return
    if payoff == "select_token":
        # Vice Admiral Rampart SEC_85: "give an Experience token to each of up to
        # N other units" — the Medal Ceremony SOR_245 select_token decision, pushed
        # from the disclose payoff (the source's controller decides).
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_select_token(
            s, source_result[1],
            token_type=str(args.get("token_type", "Experience")),
            max_targets=int(args.get("max_targets", 1)),
            controller=str(args.get("controller", "any")),
            kind=str(args.get("kind", "unit")),
            traits=list(args.get("traits", []) or []),
            predicates=list(args.get("predicates", []) or []),
        )
        return
    if payoff == "grant_keyword":
        # Naboo Security Force SEC_120 / B2EMO SEC_248: give the pre-chosen unit a
        # keyword for this phase (reuses the keyword-grant modifier seam).  The
        # target was chosen up front (the SEC_129 pre-chosen convention); no-op if
        # it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _make_kw_modifier
            from swu.abilities.registry import Duration
            s.modifiers.append(_make_kw_modifier(
                s, ctx.get("source_id", ""), tid,
                keyword=str(args.get("keyword", "Sentinel")),
                value=int(args.get("value", 0)),
                duration=Duration.THIS_PHASE, kind="keyword_grant"))
        return
    if payoff == "ready_resources":
        # Soulless One SEC_190: "ready N resources" — the resource-ramp mirror of
        # the ``heal_base`` arm (readying fewer than N when only fewer are spent).
        ps = s.player_by_id(discloser_id)
        remaining = int(args.get("count", 1))
        for r in ps.resources:
            if remaining <= 0:
                break
            if r.exhausted:
                r.exhausted = False
                remaining -= 1
        return
    if payoff == "pending_keyword_grant":
        # Diplomatic Envoy SEC_109: "the next unit you play this phase gains K for
        # this phase" — one entry on the ``pending_keyword_grants`` ledger (Deceptive
        # Shade LOF_180), consumed by that player's next unit play.
        s.game_memory.pending_keyword_grants.append({
            "player_id": discloser_id,
            "trait": str(args.get("trait", "") or ""),
            "keyword": str(args.get("keyword", "Ambush")),
        })
        return
    if payoff == "resource_top_of_deck":
        # Chancellor Valorum SEC_107: "put the top card of your deck into play as a
        # resource" (the ``_resource_top_of_deck`` ramp seam, which enters ready).
        _resource_top_of_deck(s, s.player_by_id(discloser_id))
        return
    if payoff == "heal_unit":
        # Relief Request SEC_74: heal N damage from the pre-chosen "another" unit
        # (the SEC_129 pre-chosen convention); no-op if it has since left play.
        tid = args.get("target_id")
        res = s.find_instance(tid) if tid is not None else None
        if res is not None:
            healed = min(int(args.get("amount", 0)), int(res[1].damage))
            if healed > 0:
                res[1].damage -= healed
                note_unit_healed(s, res[1], healed)
        return
    if payoff == "distribute_heal":
        # Nala Se SEC_65: "heal up to 4 damage from among other units" — the
        # Redemption SOR_52 heal-pool decision, widened to either player's units
        # and excluding the source ("other"), with no self-damage kicker.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_distribute_heal(
            s, source_result[1], int(args.get("amount", 0)),
            include_bases=False, then_damage_self=False,
            target_controller="any",
            exclude_ids=[ctx["source_id"]],
        )
        return
    if payoff == "capture":
        # Charged with Corruption SEC_127: the pre-chosen friendly captor captures
        # the pre-chosen enemy non-leader unit (reuses _apply_capture).  Both ids
        # were chosen up front (the SEC_129 pre-chosen convention); no-op if either
        # has since left play.
        captor_id = args.get("captor_id")
        victim_id = args.get("victim_id")
        if (captor_id and victim_id
                and s.find_instance(captor_id) is not None
                and s.find_instance(victim_id) is not None):
            _apply_capture(s, captor_id, victim_id)
        return
    if payoff == "defeat":
        # Charged with Murder SEC_76: defeat the pre-chosen unit (reuses
        # _apply_defeat_unit).  The target (a damaged non-leader unit) was chosen up
        # front (the SEC_129 pre-chosen convention); no-op if it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_defeat_unit
            _apply_defeat_unit(s, tid)
        return


# ── Exhaust any number of friendly units, deal base damage per (The Invisible
#    Hand TWI_234 On Attack) ───────────────────────────────────────────────────

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


def _return_one_resource_to_owner(s: GameState, ps: PlayerState) -> None:
    """Return one of ``ps``'s resources to its OWNER's hand (Intimidator LAW_140).

    Resources are fungible and are not targetable cards, so the pick is automatic
    (the K-2SO SOR_145 convention): the EXHAUSTED ones go first, since a returned
    resource is equally a card in hand either way while a ready one left behind is
    still worth a resource this phase.  Ties break on the highest printed cost, the
    card most worth recovering (Citadel Research Center LAW_29).  The owner is not
    always the controller — a resource can change hands (DJ SHD_213)."""
    if not ps.resources:
        return
    res = max(ps.resources,
              key=lambda c: (1 if c.exhausted else 0,
                             getattr(c.card_def, "cost", 0) or 0))
    ps.resources.remove(res)
    res.zone = Zone.HAND
    res.face_down = False
    res.exhausted = False
    s.player_by_id(res.owner_id).hand.append(res)


def _pay_resources_for_tokens_can_pay(state: GameState, ctx: dict) -> bool:
    """Whether another cost item may be spent: below the cap (``None`` = unbounded)
    AND an item of the configured ``cost_source`` remains — a ready resource, a
    Credit token when ``cost_source == "credit"`` (Cad Bane LAW_32), or ANY resource
    (ready or not) when it is ``"return_resource"`` (Intimidator LAW_140, whose
    "return any number of friendly resources" does not ask them to be ready)."""
    cap = ctx.get("max_resources")
    if cap is not None and int(ctx.get("paid", 0)) >= int(cap):
        return False
    ps = state.player_by_id(ctx["controller_id"])
    if ctx.get("cost_source") == "credit":
        return len(ps.credits) > 0
    if ctx.get("cost_source") == "return_resource":
        return len(ps.resources) > 0
    return ps.available_resources > 0


def push_pay_resources_for_tokens(
    s: GameState, source_ci: CardInstance, *,
    max_resources: Optional[int] = 6, token_type: str = "Experience",
    cost_source: str = "resource",
    payoff: str = "token", damage_per: int = 0,
    damage_target_id: Optional[str] = None,
    token_unit_name: Optional[str] = None,
    opponent_token_unit_name: Optional[str] = None,
    token_target_id: Optional[str] = None,
) -> None:
    """Push a 'pay_resources_for_tokens' decision (Curious Flock LOF_255): "Pay up
    to ``max_resources`` resources.  For each resource paid this way, give a
    ``token_type`` token to this unit."

    ``payoff`` selects what each paid resource buys:
      * ``"token"`` (default) — one ``token_type`` token on the source, granted
        inline as each resource is paid (Curious Flock LOF_255).
      * ``"damage"`` — ``damage_per`` damage to ``damage_target_id``, tallied and
        dealt once at resolve (Force Lightning SOR_138 "pay any number of resources
        and deal 2 damage to the chosen unit for each resource paid").  Dealing at
        resolve keeps the "pop then deal" discipline so a resulting defeat lands on a
        clean stack; nothing is granted inline in this mode.  Pushed only when the
        target is still in play.
      * ``"token_units"`` — ``token_unit_name`` TOKEN UNITS for the controller and
        ``opponent_token_unit_name`` (if given) for each opponent, one each per
        resource paid (The Clone Wars TWI_125: "Pay any number of resources.
        Create that many Clone Trooper tokens.  Each opponent creates that many
        Battle Droid tokens").  Like the damage payoff these are tallied via
        ``paid`` and created once at resolve — after the pop — because a token
        entering play fires its own enter-play bus, which must land on a clean
        stack.

    The decider is the source's controller; cost items are fungible, so each payment
    just spends the next item and grants one token to the source inline.  Pushed only
    when the controller has at least one spendable item (spending 0 grants 0 tokens —
    a clean no-op); "up to" includes 0, so FinishPayResources is always offered while
    the decision is up.

    ``cost_source`` selects what is spent per token:
      * ``"resource"`` (default) — exhaust a ready resource (Curious Flock LOF_255).
      * ``"credit"`` — defeat a friendly Credit token (Cad Bane LAW_32 "Defeat any
        number of friendly Credit tokens").
      * ``"return_resource"`` — RETURN a resource to its owner's hand rather than
        spending it in place ("Return any number of friendly resources to their
        owners' hands.  For each resource returned this way, create a Credit token"
        — Intimidator LAW_140, paired with ``payoff="credit"``).  Readiness is not
        required, and the auto-pick prefers the exhausted ones.
    A fourth ``payoff``, ``"credit"``, creates one Credit token per item spent —
    granted inline, since a Credit is a pile entry and fires no enter-play bus.
    ``max_resources`` may be ``None`` for an unbounded "any number" (bounded only by
    the available cost items — Cad Bane)."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    if cost_source == "credit":
        if len(ps.credits) <= 0:
            return
    elif cost_source == "return_resource":
        if len(ps.resources) <= 0:
            return
    elif ps.available_resources <= 0:
        return
    if payoff == "damage" and s.find_instance(damage_target_id or "") is None:
        return  # no live target to damage — don't offer the pay decision
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "max_resources": None if max_resources is None else int(max_resources),
        "token_type": token_type,
        "cost_source": cost_source,
        "paid": 0,
        "payoff": payoff,
        "damage_per": int(damage_per),
        "damage_target_id": damage_target_id,
        "token_unit_name": token_unit_name,
        "opponent_token_unit_name": opponent_token_unit_name,
        "token_target_id": token_target_id,
    }
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="pay_resources_for_tokens",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pay_resources_for_tokens",
    ))


def _resolve_pay_resources_for_tokens(s: GameState, top) -> GameState:
    """Pop the 'pay_resources_for_tokens' decision and hand the turn over.  Token
    payoffs were granted inline as each resource was paid; a ``payoff == "damage"``
    payoff is dealt here — after the pop — so a resulting defeat lands on a clean
    stack (Force Lightning SOR_138)."""
    ctx = top.context
    s.pending_decisions.pop()
    unit = "credit" if ctx.get("cost_source") == "credit" else "resource"
    if ctx.get("cost_source") == "return_resource":
        unit = "returned resource"
    if ctx.get("payoff") == "damage":
        paid = int(ctx.get("paid", 0))
        amount = paid * int(ctx.get("damage_per", 0))
        tid = ctx.get("damage_target_id")
        if amount > 0 and tid and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            src = s.find_instance(ctx.get("source_id", ""))
            name = src[1].card_def.display_name if src is not None else None
            _apply_deal_damage(s, tid, amount, source_name=name)
    if ctx.get("payoff") == "token_units":
        # "Create that many <token> tokens.  Each opponent creates that many
        # <other token> tokens" (The Clone Wars TWI_125) — created after the pop so
        # each token's enter-play bus lands on a clean stack.
        paid = int(ctx.get("paid", 0))
        controller_id = ctx["controller_id"]
        if paid > 0:
            if ctx.get("token_unit_name"):
                _create_token_units(s, s.player_by_id(controller_id),
                                    ctx["token_unit_name"], paid)
            if ctx.get("opponent_token_unit_name"):
                for pl in s.players:
                    if pl.player_id != controller_id:
                        _create_token_units(s, pl,
                                            ctx["opponent_token_unit_name"], paid)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="pay_resources_for_tokens",
        choice=f"spent {ctx.get('paid', 0)} {unit}(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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

def push_reveal_play_credit(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'reveal_play_credit' decision (Vermillion LAW_215).

    The source's controller first chooses which deck's top card to reveal, then a
    player who may play it for free; if it is played, the OTHER player makes Credit
    tokens equal to the played card's printed cost.  Only pushed when at least one
    player's deck is non-empty (else the whole ability fizzles).  After the whole
    sequence the turn passes to the source controller's opponent (the attack is
    over), stored in ``final_active_idx``.
    """
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    deck_player_ids = [p.player_id for p in s.players if p.deck]
    if not deck_player_ids:
        return  # nothing to reveal
    controller_idx = s.player_index(controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "stage": "choose_deck",
        "deck_player_ids": deck_player_ids,
        "final_active_idx": s.player_index(opponent_id),
    }
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="reveal_play_credit",
        context=ctx,
        after_resolve_player_index=s.player_index(opponent_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = controller_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="reveal_play_credit",
    ))


def _find_revealed(s: GameState, ctx: dict) -> Optional[CardInstance]:
    """The revealed card (still on top of / in its deck), or None if it has gone."""
    rid = ctx.get("revealed_id")
    if rid is None:
        return None
    for c in s.player_by_id(ctx["deck_owner_id"]).deck:
        if c.instance_id == rid:
            return c
    return None


def _revealed_upgrade_hosts(s: GameState, ctx: dict) -> list[str]:
    """Legal host ids for the revealed upgrade (empty if not an upgrade / no host)."""
    ci = _find_revealed(s, ctx)
    if ci is None or not isinstance(ci.card_def, Upgrade):
        return []
    return [u.instance_id for u in _eligible_upgrade_targets(s, ci)]


def _revealed_is_playable(s: GameState, ctx: dict) -> bool:
    """Whether the chosen player can play the revealed card: a unit or event is
    always playable; an upgrade needs at least one legal host on the board."""
    ci = _find_revealed(s, ctx)
    if ci is None:
        return False
    if isinstance(ci.card_def, Upgrade):
        return bool(_eligible_upgrade_targets(s, ci))
    return isinstance(ci.card_def, (Unit, Leader, Event))


def _play_revealed_card(s: GameState, ctx: dict, host_id: Optional[str]) -> None:
    """Play the revealed card for free under the chosen player's control.

    The card is removed from the revealed deck and played via the normal play
    paths (unit → arena, upgrade → attach, event → resolve) so its own keyword /
    When Played abilities fire.  ``owner_id`` is left unchanged (control is
    implicit — the Stolen Landspeeder SHD_161 convention), so when the chosen
    player does not own the card, its own abilities resolve from the OWNER's
    perspective (the documented control-change limitation); the common case (a
    player plays their own deck's card) is exact."""
    deck_owner = s.player_by_id(ctx["deck_owner_id"])
    play_ps = s.player_by_id(ctx["play_player_id"])
    rid = ctx.get("revealed_id")
    ci = None
    for i, c in enumerate(deck_owner.deck):
        if c.instance_id == rid:
            ci = deck_owner.deck.pop(i)
            break
    if ci is None:
        return  # gone (shouldn't happen)
    ci.face_down = False
    after_idx = int(ctx["final_active_idx"])

    card_played_evt = CardPlayed(
        player_id=play_ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        cost_paid=0,
    )
    s.event_log.append(card_played_evt)
    card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
    if "Villainy" in card_aspects:
        s.game_memory.villainy_players_this_phase.add(play_ps.player_id)

    if isinstance(ci.card_def, (Unit, Leader)):
        _put_unit_in_play(s, play_ps, ci, cost_paid=0)
    elif isinstance(ci.card_def, Upgrade):
        _attach_upgrade(s, play_ps, ci, host_id)
    elif isinstance(ci.card_def, Event):
        ci.zone = Zone.DISCARD
        play_ps.discard.append(ci)
        _resolve_event_ability(s, play_ps, ci, after_idx)
    else:
        ci.zone = Zone.DISCARD
        play_ps.discard.append(ci)

    get_bus().fire(s, card_played_evt)
    from swu.abilities.resolver import fire_triggered_abilities
    fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)


def _create_credits_for_other(s: GameState, ctx: dict) -> None:
    """The player who did NOT play the revealed card makes Credit tokens equal to
    its printed cost ("a different player creates Credit tokens equal to that
    card's cost").  In a 2-player game the "different player" is unambiguous."""
    cost = int(ctx.get("revealed_cost", 0) or 0)
    if cost <= 0:
        return
    other_id = next(p.player_id for p in s.players
                    if p.player_id != ctx["play_player_id"])
    from swu.engine.tokens import create_credit_token
    other_ps = s.player_by_id(other_id)
    for _ in range(cost):
        create_credit_token(s, other_ps)


def _resolve_play_revealed(s: GameState, top, host_id: Optional[str]) -> GameState:
    """Pop the decision, play the revealed card for free, then the other player
    makes Credits = its cost.  The decision is popped FIRST so the played card's
    own triggers land on a clean stack (the push_distribute_damage "pop, then act"
    gotcha)."""
    ctx = top.context
    final_idx = int(ctx["final_active_idx"])
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_play_credit",
        choice=f"played {ctx.get('revealed_card_name')}",
    ))
    _play_revealed_card(s, ctx, host_id=host_id)
    _create_credits_for_other(s, ctx)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = final_idx
    return s


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


def arm_when_played_redo(s: GameState, source_ci: CardInstance) -> None:
    """Arm one "the next time you use a When Played ability this phase, you may use
    that ability again" charge for the source's controller (Qui-Gon Jinn's
    Aethersprite LOF_197, On Attack).

    The charge is a phase-scoped per-player counter on ``game_memory``; the next
    qualifying WhenPlayed ability the controller uses consumes one charge and
    offers an optional re-use of that same ability (see
    ``resolver._schedule_when_played_redo``).  Multiple Aethersprites attacking
    arm multiple charges, each spent by a successive WhenPlayed ability — a faithful
    simplification of the rules' simultaneous delayed effects (vanishingly rare,
    needing two attacks before a When Played card in the same phase)."""
    charges = s.game_memory.when_played_redo_charges
    pid = source_ci.owner_id
    charges[pid] = charges.get(pid, 0) + 1


def _resolve_select_token(s: GameState, top) -> GameState:
    """Pop the 'select_token' decision and hand the turn over."""
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_token",
        choice=(f"defeated {len(ctx.get('chosen', []))} upgrade(s)"
                if ctx.get("defeat") else
                f"returned {len(ctx.get('chosen', []))} card(s) to hand"
                if ctx.get("return_to_hand") else
                f"gave {ctx['token_type'] or 'a bonus'} to "
                f"{len(ctx.get('chosen', []))} unit(s)"),
    ))
    # RETURN mode (Force Speed LOF_205: "return any number of non-unique upgrades
    # attached to the defender to their owners' hands") — resolved after the pop for
    # the same reason DEFEAT mode is: the return detaches cards and may fire
    # follow-on effects that would otherwise stack under this decision.
    if ctx.get("return_to_hand"):
        from swu.abilities.resolver import _apply_return_to_hand
        for tid in ctx.get("chosen", []):
            if s.find_instance(tid) is None:
                continue
            _apply_return_to_hand(s, tid)
    # DEFEAT mode (Kit Fisto's Aethersprite LOF_147) resolves HERE, after the pop:
    # defeating an upgrade fires its When Defeated triggers synchronously, which
    # would otherwise stack decisions underneath this one.
    if ctx.get("defeat"):
        from swu.abilities.resolver import _apply_defeat_unit
        defeated_here = 0
        for tid in ctx.get("chosen", []):
            if s.find_instance(tid) is None:
                continue  # already gone (a chained defeat took it)
            _apply_defeat_unit(s, tid)
            defeated_here += 1
        # "For each unit defeated this way, create a Credit token and draw a card"
        # (Tobias Beckett LAW_2) — paid after the defeats, so a unit that was
        # already gone when its turn came round pays nothing.
        if ctx.get("then_credit_and_draw") and defeated_here:
            from swu.engine.tokens import create_credit_token
            beneficiary = s.player_by_id(ctx.get("controller_id")
                                         or top.deciding_player_id)
            for _ in range(defeated_here):
                create_credit_token(s, beneficiary)
            _draw_cards(s, beneficiary, defeated_here)
    # "If they do, the next unit you play this phase gains Shielded for this phase"
    # (Sabine Wren ASH_6) — the "if they do" is literal: the entry is armed only when
    # the decider really gave a token, and it is armed for the SOURCE's controller
    # (the opponent made the choice, but the payoff is the source player's).
    # "Then, an opponent searches TWICE that many cards from the top of their deck
    # for an event, reveals it, and draws it" (Elzar Mann ASH_224) — the drawback
    # rider, scaled by how many tokens were really distributed, so giving none
    # searches nothing.  A FOREIGN deck_search (Sabé SEC_17): the opponent both owns
    # the deck and decides.
    if ctx.get("then_opponent_event_search") and ctx.get("chosen"):
        src_res = s.find_instance(ctx["source_id"])
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        opp = next((p for p in s.players if p.player_id != controller_id), None)
        if src_res is not None and opp is not None:
            from swu.cards.models import Event as _EventDef
            push_deck_search(
                s, src_res[1], count=1, up_to=False,
                window=2 * len(ctx["chosen"]),
                deck_owner_id=opp.player_id, decider_id=opp.player_id,
                eligible=lambda cd: isinstance(cd, _EventDef))
    # "If you give a Shield to an ENEMY unit this way, draw a card" (Secret Marriage
    # TS26_46) — settled after the pop, once it is known which units really took a
    # token.  ONE draw however many enemy units were chosen (the card says "a card"),
    # and none when every pick was friendly, which is the whole tension of the card.
    if ctx.get("then_draw_if_enemy_chosen") and ctx.get("chosen"):
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        hit_enemy = False
        for tid in ctx.get("chosen", []):
            res = s.find_instance(tid)
            if res is not None and res[0].player_id != controller_id:
                hit_enemy = True
                break
        if hit_enemy:
            _draw_cards(s, s.player_by_id(controller_id), 1)
    _pkw = ctx.get("then_pending_keyword")
    if _pkw and ctx.get("chosen"):
        s.game_memory.pending_keyword_grants.append({
            "player_id": ctx.get("source_controller_id") or top.deciding_player_id,
            "trait": str(_pkw.get("trait", "") or ""),
            "keyword": str(_pkw.get("keyword", "Shielded")),
        })
    # "Use any number of 'When Played' abilities on friendly Spectre units" (Fire
    # Across the Galaxy LAW_256).  Also resolved AFTER the pop — each re-use is a
    # fresh ``resolve_effects`` decision (the Chimaera JTL_39 / Shadow Caster
    # JTL_169 shape) and must not stack underneath this one.  Pushed in REVERSE, per
    # unit and per ability, so the first-chosen unit's first-registered ability
    # resolves first on the LIFO stack.
    if ctx.get("then_use_when_played") and ctx.get("chosen"):
        from swu.abilities.resolver import _when_played_ability_indices
        from swu.engine.decisions import PendingDecision
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        owner_idx = s.player_index(controller_id)
        pushed = False
        for tid in reversed(list(ctx.get("chosen", []))):
            res = s.find_instance(tid)
            if res is None:
                continue
            unit = res[1]
            for ability_idx in reversed(_when_played_ability_indices(s, unit)):
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=controller_id,
                    kind="resolve_effects",
                    context={
                        "set_code": unit.card_def.set_code,
                        "card_number": unit.card_def.card_number,
                        "ability_idx": ability_idx,
                        "source_id": unit.instance_id,
                        "effect_idx": 0,
                        "resolved_targets": {},
                        "event_ctx": {"ability_redo": True},
                        "after_all_player_idx": top.after_resolve_player_index,
                    },
                    after_resolve_player_index=top.after_resolve_player_index,
                ))
                s.event_log.append(DecisionPushed(
                    deciding_player_id=controller_id, kind="resolve_effects"))
                pushed = True
        if pushed:
            s.active_player_index = owner_idx
            return s
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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
    "exploit":                       _exploit_actions,
    "test":                          _test_actions,
    "resolve_effects":               _resolve_effects_actions,
    "granted_attack":                _granted_attack_actions,
    "pre_attack":                    _pre_attack_actions,
    "return_from_discard":           _return_from_discard_actions,
    "resource_from_discard":         _resource_from_discard_actions,
    "reveal_cull_draw":              _reveal_cull_draw_actions,
    "discard_for_experience":        _discard_for_experience_actions,
    "select_distinct_return_random": _select_distinct_return_random_actions,
    "bottom_from_discard":           _bottom_from_discard_actions,
    "select_token":                  _select_token_actions,
    "disclose":                      _disclose_actions,
    "reveal_top":                    _reveal_top_actions,
    "reveal_cost_damage":            _reveal_cost_damage_actions,
    "sacrifice_resource":            _sacrifice_resource_actions,
    "reveal_resource_ramp":          _reveal_resource_ramp_actions,
    "discard_unit_damage":           _discard_unit_damage_actions,
    "cull_for_damage":               _cull_for_damage_actions,
    "discard_for_search":            _discard_for_search_actions,
    "recur_and_buff":                _recur_and_buff_actions,
    "discard_excess_from_hand":      _discard_excess_from_hand_actions,
    "name_and_discard":              _name_and_discard_actions,
    "exhaust_for_base_damage":       _exhaust_for_base_damage_actions,
    "exhaust_combined_cost":         _exhaust_combined_cost_actions,
    "capture_combined_hp":           _capture_combined_hp_actions,
    "per_exploit_damage":            _per_exploit_damage_actions,
    "pay_resources_for_tokens":      _pay_resources_for_tokens_actions,
    "reveal_play_credit":            _reveal_play_credit_actions,
    "plot":                          _plot_actions,
})
