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
from dataclasses import dataclass, field
from typing import Callable, Optional

from swu.cards.models import AnyCard, Base, Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    AttackDeclared, CardPlayed, CardResourced,
    ControlChanged, DamageDealt, DecisionPushed, DecisionResolved, HandDrawn, HandKept, InitiativeTaken,
    LeaderDeployed, MulliganTaken, PlayerPassed, RegroupSkipped, UnitDefeated,
    UnitReadied, UpgradeDetached,
    UpgradePlayed,
)
from swu.engine.keywords import Keyword, has_keyword, keyword_value
from swu.engine.state import CardInstance, GameState, Phase, PlayerState, Zone, ability_suppressed
from swu.engine.tokens import attach_token
from swu.engine.triggers import get_bus

from swu.engine.actions.base import Action, IllegalActionError
from swu.engine.actions.observers import (
    _fire_base_damage_observers, _fire_bounty_observers, _fire_deck_discard_observers, _fire_defeat_own_resource, _fire_draw_observers, _fire_force_observers, _fire_hand_discard_observers, _fire_heal_observers, _fire_noncombat_damage_observers, _fire_ready_observers, _fire_reveal_discard_observers, _fire_self_discard_observers, _fire_token_creation_observers, _fire_unit_entry_observers, _fire_upgrade_attach_observers, _fire_upgrade_defeat_observers, note_unit_healed,
)
from swu.engine.actions.dispatch import (
    decision_handler, register_decisions,
)
from swu.engine.actions.turn import (
    _advance_mulligan, _advance_setup_resources, _check_regroup_complete, _enter_regroup, _starting_hand_modifier, _starting_hand_size,
)
from swu.engine.actions.combat import (
    _enumerate_attacks, _enumerate_two_unit_attacks, _filter_granted_attacks, _forced_attack_actions, _pre_attack_actions, _select_damage_targets, _select_token_targets, note_hand_or_deck_discard, push_granted_attack, push_select_token, record_base_damage, record_hand_discard,
)
from swu.engine.actions.flow import (
    _assert_phase, _check_game_over, _switch_active_player,
)
from swu.engine.actions.zones import (
    _apply_capture, _apply_put_on_deck, _attach_upgrade, _create_token_units, _defeat_unit, _draw_cards, _eligible_upgrade_targets, _find_in_arenas, _find_upgrade_host, _push_resolve_unique, _put_unit_in_play, _rescue_captured_card, _resolve_event_ability, _sweep_defeated_units, _upgrade_target_spec, note_upgrade_attached, note_upgrade_defeated,
)
from swu.engine.actions.damage import (
    _bases_cannot_heal, base_damage_after_prevention, note_base_healed,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _consume_standing_discount, _defeat_credit, _discard_cost_candidates, _discard_cost_payable, _effective_cost, _event_aspect_waiver, _exhaust_resources, _ignorable_aspect_penalty, _pay_play_cost, _pilot_count, _pilot_limit, _piloting_cost, _piloting_discount_entry, _play_cost, _play_reduction_for, _play_upgrade_affordable, _play_upgrade_cost, _smuggle_cost, _usable_credits, _vehicle_has_pilot, resource_cost_for,
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
class PlayFromDiscard(Action):
    """Play a card from the active player's DISCARD pile, paying its printed
    cost, per a ``PlayFromDiscardAction`` ability (Brutal Traditions SHD_38:
    "Action: If an enemy unit was defeated this phase, play this upgrade from
    your discard pile (paying its cost)").

    The card leaves the discard pile, its cost is paid from ready resources, and
    it is played exactly like a hand play (upgrade → attach onto
    ``upgrade_target_id``; a unit enters play) — the ``CardPlayed`` / WhenPlayed /
    observer firing mirrors ``PlayCard`` so a discard-play is indistinguishable
    downstream.  ``free`` skips cost payment (Second Chance SHD_53's granted "play
    it from your discard pile for free" replay, whose one-shot per-phase
    permission is also consumed here).  Availability, affordability, the free
    permission and the legal host set are all re-validated against the live
    discard enumeration on apply, so a stale action cannot force an illegal or
    unearned free play.  ``discount`` is the DISCOUNTED sibling of ``free`` (Aid
    from the Innocent TWI_201's "for this phase, you may play the discarded cards,
    and they each cost 2 resources less"): the normal cost is paid minus that many
    resources (floored at 0) and the one-shot permission is likewise consumed."""
    instance_id: str
    upgrade_target_id: Optional[str] = None
    free: bool = False
    discount: int = 0

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        # Re-derive the legal discard plays and require this one to be among them
        # (guards the gate condition / free permission, affordability and host).
        if not any(
            isinstance(a, PlayFromDiscard)
            and a.instance_id == self.instance_id
            and a.upgrade_target_id == self.upgrade_target_id
            and a.free == self.free
            and a.discount == self.discount
            for a in _enumerate_discard_play_actions(s, ps)
        ):
            raise IllegalActionError(
                f"Cannot play {self.instance_id} from discard right now")
        # The card is normally in the active player's own discard, but a granted
        # CROSS-PILE free replay (Stolen AT-Hauler JTL_221) plays it out of its
        # OWNER's pile, so fall back to a scan of every discard.  The enumeration
        # guard above has already established that this play is legal.
        holder = ps
        ci = next((c for c in ps.discard if c.instance_id == self.instance_id), None)
        if ci is None:
            for other in s.players:
                found = next((c for c in other.discard
                              if c.instance_id == self.instance_id), None)
                if found is not None:
                    ci, holder = found, other
                    break
        holder.discard.remove(ci)

        if self.free:
            # Consume the one-shot per-phase free-replay permission (Second Chance
            # SHD_53, or the cross-pile JTL_221 grant) so it can't be spent twice.
            s.game_memory.free_discard_play_this_phase.discard(self.instance_id)
            foreign = s.game_memory.foreign_free_discard_play_this_phase
            if self.instance_id in (foreign.get(ps.player_id) or ()):
                foreign[ps.player_id] = [
                    i for i in foreign[ps.player_id] if i != self.instance_id]
            cost = 0
        else:
            cost = _play_cost(s, ci, ps, target_host_id=self.upgrade_target_id)
            if self.discount:
                # Consume the one-shot discounted permission (Aid from the Innocent
                # TWI_201) so the discount can't be spent twice.
                cost = max(0, cost - int(self.discount))
                s.game_memory.discard_play_discount_this_phase.pop(
                    self.instance_id, None)
            # Consume a cross-pile PAID permission (Obi-Wan Kenobi SEC_205), whose
            # waiver rides in ``discount`` and may legitimately be 0.
            foreign_paid = s.game_memory.foreign_discard_play_this_phase
            if self.instance_id in (foreign_paid.get(ps.player_id) or ()):
                foreign_paid[ps.player_id] = [
                    i for i in foreign_paid[ps.player_id] if i != self.instance_id]
            _pay_play_cost(s, ps, cost)

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

        if isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
        elif isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, play_source="discard", cost_paid=cost)
        elif isinstance(ci.card_def, Event):
            # An EVENT played from the discard pile (Aid from the Innocent TWI_201's
            # discounted permission) goes straight back to the discard and resolves
            # through the same chokepoint as a hand play.
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            _resolve_event_ability(s, ps, ci, after_idx)
        else:  # defensive — no other card type can reach a discard play today
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)

        get_bus().fire(s, card_played_evt)

        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx,
                                 event_ctx={"played_card_id": ci.instance_id})

        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id} from discard" + (
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
class PlotPlay(Action):
    """Play a card from your resource zone using its Plot keyword.

    Plot ("When you deploy a leader, you may play this card from your resources,
    paying its cost. Replace it with the top card of your deck.") is offered as a
    ``"plot"`` decision pushed by DeployLeader.  Resolving a PlotPlay pays the
    card's *printed* effective cost (aspect-adjusted, minus any cost reductions)
    from the OTHER ready resources, replaces the played card with the deck top
    (face down, ready — so the resource count is preserved, exactly like
    Smuggle), then plays the card normally (unit → arena, upgrade → attach, event
    → resolve) so its own keyword / "When Played" triggers fire.

    Unlike Smuggle, PlotPlay does NOT pop its decision or hand the turn over: a
    single leader deploy may trigger every Plot card in your resources, so the
    "plot" decision stays on the stack and re-offers the remaining Plot cards
    until the player resolves it with FinishPlot.  Any decision a played card
    pushes (e.g. a When Played target choice) lands on top of the still-pending
    plot decision and resolves first (LIFO), after which the plot decision is top
    again.
    """
    instance_id: str
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "plot"):
            raise IllegalActionError("No pending Plot decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ps = s.player_by_id(top.deciding_player_id)

        if self.instance_id not in top.context.get("plot_ids", []):
            raise IllegalActionError(
                f"{self.instance_id} is not an eligible Plot card")

        ci = None
        for i, r in enumerate(ps.resources):
            if r.instance_id == self.instance_id:
                ci = ps.resources.pop(i)
                break
        if ci is None:
            raise IllegalActionError(
                f"Plot source {self.instance_id} not in resource zone")
        if not has_keyword(s, ci, Keyword.PLOT):
            raise IllegalActionError(
                f"{ci.card_def.display_name} does not have Plot")

        # Plot pays the card's PRINTED cost (not a special bracketed cost like
        # Smuggle), from the OTHER ready resources (ci has already left the zone).
        # ``via_plot`` applies a "next card you play using Plot costs N less"
        # discount (Chancellor Palpatine SEC_1); it is consumed once here.
        cost = _play_cost(s, ci, ps, via_plot=True)
        if ps.available_resources < cost:
            raise IllegalActionError(
                f"Insufficient resources: need {cost}, have {ps.available_resources}")
        _exhaust_resources(ps, cost)
        _consume_play_discount(s, ci, ps, via_plot=True)

        # Replace the played card with the top of the deck (deterministic), as
        # Smuggle does, so the resource count is preserved.
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

        after_idx = top.after_resolve_player_index

        if isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, play_source="plot")
        elif isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
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

        # SEC_245 "When Has Become Now": an ability (not a leader deploy) that
        # plays ONE Plot card and — "if you do" — ramps.  Do the ramp now (net +1
        # resource, on top of Plot's own replace-with-deck-top), then remove THIS
        # plot decision (single-shot: it may no longer be on top if the played
        # card pushed its own decision, so remove it by identity).
        if top.context.get("plot_ability"):
            if top.context.get("ramp_after"):
                _resource_top_of_deck(s, ps)
            for i, d in enumerate(s.pending_decisions):
                if d is top:
                    del s.pending_decisions[i]
                    break
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = after_idx
            return s

        # Do NOT pop the plot decision or switch the active player: more Plot
        # cards may still be playable off this same leader deploy.  Any decision a
        # played card pushed sits on top of the plot decision and resolves first.
        return s

    def describe(self) -> str:
        return f"Plot {self.instance_id}" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


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


# ── Owner-may-replay a just-returned unit for free (Baylan Skoll LOF_185,
#    Rio Durant LAW_93) ──────────────────────────────────────────────────────
#
# "Return a non-leader unit to its owner's hand.  Then, its owner may play it for
# free."  A multi-decider decision: the returned unit's OWNER — who may be the
# source's opponent — decides whether to replay it (the say_no SOR_233 /
# opponent_chooses_target SHD_246 deciding-player shift).  The return has already
# happened inline (via _apply_return_to_hand) before the decision is pushed by
# push_owner_may_replay.

@dataclass
class ReplayReturnedUnit(Action):
    """Resolve an 'owner_may_replay' decision by playing the returned unit from the
    deciding player's hand for FREE (Baylan Skoll LOF_185 / Rio Durant LAW_93)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "owner_may_replay"):
            raise IllegalActionError("No owner_may_replay decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id != ctx.get("card_id"):
            raise IllegalActionError("Not the returned unit")
        owner_ps = s.player_by_id(top.deciding_player_id)
        if not any(c.instance_id == self.instance_id for c in owner_ps.hand):
            raise IllegalActionError("Returned unit is not in the owner's hand")
        ci = _take_from_hand(owner_ps, self.instance_id)
        if not isinstance(ci.card_def, Unit):
            raise IllegalActionError("Returned card is not a unit")
        grant_keyword = ctx.get("grant_keyword")
        after_idx = top.after_resolve_player_index
        s.pending_decisions.pop()

        card_played_evt = CardPlayed(
            player_id=owner_ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=0,
        )
        s.event_log.append(card_played_evt)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="owner_may_replay",
            choice=f"replayed {ci.card_def.display_name}",
        ))
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(owner_ps.player_id)
        # The decision is popped above BEFORE the unit enters play so the replayed
        # unit's own When Played / enter-play keyword triggers land on a clean
        # stack (the push_distribute_damage "pop, then act" gotcha).  It is played
        # for free (cost 0); ``grant_keyword`` (Rio's Shielded) is applied before
        # the enter-play keyword bus so a granted Shielded winks on immediately.
        _put_unit_in_play(
            s, owner_ps, ci, grant_keyword=grant_keyword,
            play_source="hand", cost_paid=0)
        get_bus().fire(s, card_played_evt)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play returned unit {self.instance_id} for free"


@dataclass
class DeclineReplay(Action):
    """Decline the optional 'owner_may_replay' replay ("may play it for free")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "owner_may_replay"):
            raise IllegalActionError("No owner_may_replay decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="owner_may_replay",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to replay the returned unit"


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


def _resolve_put_on_deck(state: GameState, instance_id: str, *, to_top: bool) -> GameState:
    if (not state.pending_decisions
            or state.pending_decisions[-1].kind != "put_on_deck"):
        raise IllegalActionError("No put_on_deck decision pending")
    ctx = state.pending_decisions[-1].context
    if instance_id != ctx.get("card_id"):
        raise IllegalActionError("Not the chosen unit")
    s = copy.deepcopy(state)
    top = s.pending_decisions.pop()
    # Pop BEFORE relocating so any state-based fallout (a buff source leaving play)
    # is swept by the top-level apply() on a clean stack (the "pop, then act" gotcha).
    s = _apply_put_on_deck(s, instance_id, to_top=to_top)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="put_on_deck",
        choice=("top" if to_top else "bottom"),
    ))
    # The buried resolve_effects decision (if the CustomEffect that pushed us was
    # mid-resolution) stays on the stack — only restore control when it is clear.
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class PutOnDeckTop(Action):
    """Resolve a 'put_on_deck' decision by putting the unit on TOP of its owner's
    deck (Qui-Gon Jinn LOF_200)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        return _resolve_put_on_deck(state, self.instance_id, to_top=True)

    def describe(self) -> str:
        return f"Put {self.instance_id} on top of its owner's deck"


@dataclass
class PutOnDeckBottom(Action):
    """Resolve a 'put_on_deck' decision by putting the unit on the BOTTOM of its
    owner's deck (Qui-Gon Jinn LOF_200)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        return _resolve_put_on_deck(state, self.instance_id, to_top=False)

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of its owner's deck"


def push_put_on_deck(s: GameState, source_ci: CardInstance, target_id: str) -> None:
    """Push a 'put_on_deck' decision (Qui-Gon Jinn LOF_200): the OWNER of the chosen
    in-play unit puts it on the top or bottom of THEIR deck.  The decider is that
    owner (who may be the source's opponent — the owner_may_replay LOF_185
    deciding-player shift), since only they should order their own deck.  A clean
    no-op if the target is not an in-play arena unit."""
    result = s.find_instance(target_id)
    if result is None:
        return
    ps, ci = result
    if not any(ci in arena for arena in (ps.ground_arena, ps.space_arena)):
        return
    owner_idx = s.player_index(ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=ci.owner_id,
        kind="put_on_deck",
        context={
            "source_id": source_ci.instance_id,
            "card_id": target_id,
            "owner_id": ci.owner_id,
        },
        after_resolve_player_index=s.player_index(source_ci.owner_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=ci.owner_id,
        kind="put_on_deck",
    ))


# ── Opponent "say no" reaction (say_no decision) ──────────────────────────────
#
# "Deal N damage to an enemy unit unless its controller says 'no.' If they do,
# draw M cards." (I Am Your Father, SOR_233).  The source's controller picks the
# enemy unit (via the CustomEffect.target seam); the chosen unit's controller —
# the OPPONENT — then resolves a 'say_no' decision: allow the effect (take the
# damage) or say "no" (no damage, and the source's controller draws).  See
# push_say_no.

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


# ── Recurring regroup upkeep: "pay 1 or return to hand" (Millennium Falcon
# SOR_193) ────────────────────────────────────────────────────────────────────
#
# "When you ready cards during the regroup phase: Either pay [1 resource] or
# return this unit to her owner's hand."  Fired at regroup start by a
# PhaseStartTrigger(phase="regroup") CustomEffect (the Contracted Hunter JTL_216
# site) which calls push_regroup_upkeep; the source's controller then chooses.

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
#
# Han Solo SOR_17: "… At the start of the next action phase, defeat a resource you
# control."  Composes the same scheduled_action_phase_effects seam as Eye of
# Aldhani — the leader's Action/On-Attack resolves in ACTION, so the delayed defeat
# is recorded by controller_id and drained once at the next action-phase start.
# Faithful simplification (the K-2SO SOR_145 auto-select precedent): resources are
# interchangeable face-down cards, so one is auto-defeated (a face-down, un-special
# resource is preferred) rather than prompting a choice.

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


# ── Player-directed damage distribution (distribute_damage decision) ──────────
#
# A reusable decision primitive for "deal damage divided as you choose" effects
# (Emperor Palpatine SOR_135, Overwhelming Barrage SOR_92, Maximum Firepower
# SOR_234).  See push_distribute_damage / push_distribute_source_power /
# push_sequence_damage for the three flavours and their context schema.

@dataclass
class AssignDamage(Action):
    """Assign one point of distributed damage to a target unit.

    Used by the pool-allocation flows (Palpatine, Overwhelming Barrage): the
    controller spends the damage pool one point at a time onto any legal target
    (piling several points onto a single unit is allowed).  Damage is only
    *dealt* once the whole pool is allocated — the division is announced first,
    then applied simultaneously via the resolver, so no target leaves play
    mid-allocation.
    """
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.target_id not in _distribution_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        alloc = ctx.setdefault("alloc", {})
        alloc[self.target_id] = alloc.get(self.target_id, 0) + 1
        ctx["pool"] = int(ctx.get("pool", 0)) - 1
        if ctx["pool"] <= 0:
            return _finish_distribution(s)
        return s

    def describe(self) -> str:
        return f"Assign 1 damage to {self.target_id}"


@dataclass
class FinishDamageDistribution(Action):
    """Stop an "up to N" damage distribution early (Boba Fett JTL_9).

    Offered only in ``pool`` mode when the decision was pushed with ``up_to=True``.
    Deals whatever has been allocated so far and pops the decision.
    """
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if ctx.get("mode") != "pool" or not ctx.get("up_to"):
            raise IllegalActionError("This distribution cannot be finished early")
        return _finish_distribution(s)

    def describe(self) -> str:
        return "Finish assigning damage"


@dataclass
class ChooseDamageTarget(Action):
    """Choose the single victim for a sequenced-damage effect (Maximum Firepower).

    Picked first; the sources then each deal their power to this same unit.
    """
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if ctx.get("mode") != "sequence" or ctx.get("stage") != "pick_target":
            raise IllegalActionError("Not awaiting a damage target")
        if self.target_id not in _distribution_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        ctx["target_id"] = self.target_id
        ctx["stage"] = "pick_source"
        if not _distribution_sources(s, ctx):
            return _finish_distribution(s)
        return s

    def describe(self) -> str:
        return f"Choose damage target {self.target_id}"


@dataclass
class ChooseDamageSource(Action):
    """Choose a source unit that deals its power as part of a distribution.

    * Overwhelming Barrage (``source_pool``): pick the friendly unit, apply its
      this-phase buff, then distribute its (buffed) power among other units.
    * Maximum Firepower (``sequence``): pick a friendly Imperial unit; it deals
      its power to the fixed target, then (if the target survives and another
      distinct source remains) the next source is chosen.
    """
    unit_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.unit_id not in _distribution_sources(s, ctx):
            raise IllegalActionError(f"{self.unit_id} is not a legal damage source")
        mode = ctx.get("mode")

        if mode == "source_pool":
            result = s.find_instance(self.unit_id)
            if result is None:
                return _finish_distribution(s)
            _, src = result
            bp = int(ctx.get("buff_power", 0) or 0)
            bh = int(ctx.get("buff_hp", 0) or 0)
            if bp or bh:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id("dist"),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.unit_id,
                    kind="stats",
                    value={"power": bp, "hp": bh},
                    duration="this_phase",
                ))
            ctx["pool"] = compute_power(s, src)
            if ctx.get("exclude_source_from_targets"):
                ctx.setdefault("exclude_ids", []).append(self.unit_id)
            ctx["stage"] = "allocate"
            if ctx["pool"] <= 0 or not _distribution_targets(s, ctx):
                return _finish_distribution(s)
            return s

        if mode == "sequence":
            top = s.pending_decisions[-1]
            after_idx = top.after_resolve_player_index
            target_id = ctx.get("target_id")
            ctx.setdefault("sources_used", []).append(self.unit_id)
            # Pop the distribute_damage decision BEFORE dealing damage: defeating
            # the target fires WhenDefeated triggers that push their own decisions
            # onto the stack, and they must land on a clean stack (not on top of
            # this decision, which a blind pop would then mishandle).
            s.pending_decisions.pop()
            result = s.find_instance(self.unit_id)
            power = compute_power(s, result[1]) if result is not None else 0
            if power > 0 and target_id is not None:
                from swu.abilities.resolver import _apply_deal_damage
                _apply_deal_damage(s, target_id, power)
            target_alive = (
                target_id is not None and _find_in_arenas_any(s, target_id) is not None
            )
            remaining = int(ctx.get("num_sources", 0)) - len(ctx["sources_used"])
            if target_alive and remaining > 0 and _distribution_sources(s, ctx):
                # Target survived → no defeat triggers were pushed, so the stack
                # top is clean; re-push for the next distinct source.
                ctx["stage"] = "pick_source"
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=top.deciding_player_id,
                    kind="distribute_damage",
                    context=ctx,
                    after_resolve_player_index=after_idx,
                ))
                s.active_player_index = s.player_index(top.deciding_player_id)
                return s
            # Sequence finished (target defeated, no more sources, or num_sources
            # reached).  Leave the active player to any triggers still resolving.
            s.event_log.append(DecisionResolved(
                deciding_player_id=top.deciding_player_id,
                kind="distribute_damage",
                choice="distributed",
            ))
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = after_idx
            return s

        raise IllegalActionError(f"ChooseDamageSource invalid for mode {mode}")

    def describe(self) -> str:
        return f"Choose damage source {self.unit_id}"


# ── Deck search-and-select (deck_search decision) ─────────────────────────────
#
# A reusable "search the top N cards of your deck for matching cards, reveal and
# draw the chosen ones, then put the rest on the bottom in a random order"
# primitive (Grand Moff Tarkin SOR_84, Recruit SOR_123).  The controller selects
# up to ``max_select`` of the eligible candidates; selection auto-finishes once
# the cap is reached.  ``up_to`` distinguishes "up to N" (a FinishSearch is always
# offered, so 0 picks is legal — Tarkin) from "for a <thing>" (mandatory if able,
# so a pick is forced while a candidate remains — Recruit).  See push_deck_search.

@dataclass
class SelectSearchCard(Action):
    """Select one revealed candidate from the searched top cards to draw."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "deck_search"):
            raise IllegalActionError("No deck_search decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a search candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        budget = ctx.get("budget")
        if budget is not None:
            # Combined-cost budget (Darth Vader SOR_87): the picked units' printed
            # costs may not exceed the budget.  Guard defensively — legal_actions
            # already hides an over-budget candidate.
            deck_by_id = {ci.instance_id: ci
                          for ci in s.player_by_id(ctx["controller_id"]).deck}
            spent = sum((deck_by_id[cid].card_def.cost or 0)
                        for cid in ctx["selected_ids"] if cid in deck_by_id)
            this_cost = (deck_by_id[self.instance_id].card_def.cost or 0
                         ) if self.instance_id in deck_by_id else 0
            if spent + this_cost > int(budget):
                raise IllegalActionError(
                    f"{self.instance_id} exceeds the combined-cost budget")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_deck_search(s)
        return s

    def describe(self) -> str:
        return f"Take {self.instance_id} from the searched cards"


@dataclass
class FinishSearch(Action):
    """Stop selecting searched cards: draw the chosen ones and bottom the rest.

    Offered whenever the effect is "up to N" (a zero-pick finish is always legal)
    or no eligible candidate remains (a mandatory search with nothing left to take).
    """
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "deck_search"):
            raise IllegalActionError("No deck_search decision pending")
        return _finish_deck_search(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish searching"


def _finish_deck_search(s: GameState) -> GameState:
    """Pop the deck_search decision: dispose of the selected top cards (draw them,
    the default, or PLAY them — Kelleran Beq LOF_100) and put the remaining
    searched cards on the bottom of the deck in a seeded-random order.

    The deck is untouched while the decision is open, so the searched window is
    simply ``deck[:window]`` again here.  Selected cards (preserving deck order)
    are revealed and either drawn to hand or played from the deck; the rest are
    shuffled with the game's seeded RNG (NOT the global ``random`` module) and
    appended below the un-searched remainder, and the advanced ``rng_state`` is
    persisted so two same-seed runs reorder identically.
    """
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    window = int(ctx.get("window", 5))
    selected_set = set(ctx["selected_ids"])

    searched = ps.deck[:window]
    rest = ps.deck[window:]
    selected = [ci for ci in searched if ci.instance_id in selected_set]
    skipped = [ci for ci in searched if ci.instance_id not in selected_set]

    skipped_in_order = list(skipped)
    rng = s.make_rng()
    rng.shuffle(skipped)
    s.rng_state = rng.getstate()

    # The selected cards leave the deck (they are neither in ``rest`` nor
    # ``skipped``).  The un-taken searched cards go to the bottom in random order
    # by default, or to the discard pile when ``rest_disposition == "discard"``
    # (I've Found Them IBH_9 — "discard the other revealed cards").
    if ctx.get("rest_disposition") == "discard":
        for ci in skipped:
            ci.zone = Zone.DISCARD
            # A deck discard, so it feeds the shared ledger (and with it the
            # WhenThisIsDiscarded observer drain — That's a Rock LAW_206), exactly
            # as the SELECTED-card "discard" disposition below does.  The cards
            # NOT skipped never reach a discard pile at all, which is why
            # Shipbreaking Yard LAW_26's rescued card correctly does not fire it.
            note_hand_or_deck_discard(s, ci, from_deck=True)
        ps.discard.extend(skipped)
        ps.deck = rest
    elif ctx.get("rest_disposition") == "top":
        # "(Put the other back on top.)" — Sabé SEC_17.  The un-taken searched
        # cards keep their original order (they never left the top), so the
        # shuffled copy is discarded and the in-order one used.
        ps.deck = skipped_in_order + rest
    else:
        ps.deck = rest + skipped

    if ctx.get("disposition") == "play":
        # Kelleran Beq: "Search the top N … for a unit, reveal it, and play it.
        # It costs 3 resources less."  The decision is already popped, so the
        # played unit's own When Played triggers land on a clean stack (the
        # push_distribute_damage "pop, then act" gotcha).
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        free = bool(ctx.get("free"))
        enters_ready = bool(ctx.get("enters_ready"))
        return_at_regroup = bool(ctx.get("return_at_regroup"))
        bottom_at_regroup = bool(ctx.get("bottom_at_regroup"))
        played_names: list[str] = []
        for ci in selected:
            cost = 0 if free else max(0, _effective_cost(ci.card_def, ps, s) - cost_reduction)
            _pay_play_cost(s, ps, cost)
            evt = CardPlayed(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
                cost_paid=cost,
            )
            s.event_log.append(evt)
            card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
            if "Villainy" in card_aspects:
                s.game_memory.villainy_players_this_phase.add(ps.player_id)
            _put_unit_in_play(s, ps, ci, play_source="deck", cost_paid=cost,
                              enters_ready=enters_ready)
            if return_at_regroup:
                ci.return_to_owner_hand_at_regroup = True
            if bottom_at_regroup:
                ci.bottom_at_regroup = True
            get_bus().fire(s, evt)
            played_names.append(ci.card_def.display_name)
        choice = f"played {', '.join(played_names) or 'nothing'}"
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "play_upgrade":
        # Reforge ASH_90: the chosen upgrade is PLAYED onto a pre-chosen host at
        # ``cost_reduction`` off.  The decision is already popped, so the upgrade's
        # own When Played trigger lands on a clean stack.
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        host_id = ctx.get("upgrade_host_id")
        played_names: list[str] = []
        for ci in selected:
            if host_id is None or s.find_instance(host_id) is None:
                # The host left play while the decision was open — the revealed
                # upgrade has nowhere to go, so it is discarded rather than lost.
                ci.zone = Zone.DISCARD
                ps.discard.append(ci)
                continue
            cost = max(0, _effective_cost(ci.card_def, ps, s) - cost_reduction)
            _pay_play_cost(s, ps, cost)
            evt = CardPlayed(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
                cost_paid=cost,
            )
            s.event_log.append(evt)
            card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
            if "Villainy" in card_aspects:
                s.game_memory.villainy_players_this_phase.add(ps.player_id)
            _attach_upgrade(s, ps, ci, host_id)
            get_bus().fire(s, evt)
            played_names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"played {', '.join(played_names) or 'nothing'}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard_free_replay":
        # Cobb Vanth SHD_115: the selected unit is DISCARDED (not drawn) and flagged
        # for a free replay from the discard pile this phase (the Second Chance
        # SHD_53 free-discard-replay seam).  The un-taken searched cards were already
        # sent to the bottom (rest_disposition default) above.
        names: list[str] = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            s.game_memory.free_discard_play_this_phase.add(ci.instance_id)
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"discarded for free replay ({', '.join(names) or 'nothing'})",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard_play_discount":
        # Aid from the Innocent TWI_201: the selected cards are DISCARDED and, for
        # the rest of this phase, may be played from the discard pile at
        # ``play_discount`` resources less (the discounted sibling of the free
        # permission above; any card type, since the cards searched for are
        # non-units).
        red = int(ctx.get("play_discount") or 0)
        names = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            note_hand_or_deck_discard(s, ci, from_deck=True)
            s.game_memory.discard_play_discount_this_phase[ci.instance_id] = red
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=(f"discarded for a {red}-cheaper replay "
                    f"({', '.join(names) or 'nothing'})"),
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard":
        # The plain discard of the SELECTED cards (no replay permission attached) —
        # "look at the top 2 cards of the defending player's deck.  Discard 1 of
        # those cards" (Sabé SEC_17).  ``ps`` is the DECK OWNER, so the card lands
        # in their own discard pile.
        names = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            note_hand_or_deck_discard(s, ci, from_deck=True)
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"discarded {', '.join(names) or 'nothing'}",
        ))
        # "Then, you may attack with this unit.  For this attack, this unit gains the
        # discarded unit's abilities" (Improvised Identity ASH_230) — the attack is
        # pushed AFTER the pop (the pop-then-act rule), with the card just discarded
        # as the BORROW lender; ``borrowed_ability_sources`` finds it through
        # ``find_instance``, which reaches the discard.
        attacker_id = ctx.get("then_borrowed_attack_by")
        if attacker_id and selected:
            att = s.find_instance(attacker_id)
            if att is not None:
                push_granted_attack(
                    s, att[1], optional=True, attacker_id=attacker_id,
                    allow_exhausted=False, borrow_abilities=True,
                    borrow_lender_id=selected[0].instance_id)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "resource":
        # Jendirian Valley TS26_18: "Search the top 8 cards of your deck for a card
        # and RESOURCE it."  The selected card goes straight into the searcher's
        # resource row rather than to hand — face down and EXHAUSTED, the CR default
        # for a resource put into play by an effect that does not say "and ready it"
        # (the same placement ``resource_from_discard`` uses, and the card's own
        # rules note: "Resources enter play exhausted").
        names = []
        for ci in selected:
            ci.zone = Zone.RESOURCES
            ci.face_down = True
            ci.exhausted = True
            ci.damage = 0
            ps.resources.append(ci)
            s.event_log.append(CardResourced(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
            ))
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"resourced {', '.join(names) or 'nothing'}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "top":
        # Following the Path LOF_103: "…reveal them, and put them on top of your
        # deck in any order."  The selected cards go back on TOP rather than being
        # drawn; SELECTION order is the chosen top-down order (the reveal_top
        # SOR_152 click-order convention), so re-sort by ``selected_ids`` — the
        # ``selected`` list above is in deck order.
        order = {iid: i for i, iid in enumerate(ctx["selected_ids"])}
        ordered = sorted(selected, key=lambda c: order.get(c.instance_id, 0))
        for ci in ordered:
            ci.zone = Zone.DECK
        ps.deck = ordered + ps.deck
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=(f"put {len(ordered)} on top ("
                    f"{', '.join(c.card_def.display_name for c in ordered) or 'nothing'})"),
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    for ci in selected:
        ci.zone = Zone.HAND
        ps.hand.append(ci)

    # "…reveal it, and draw it.  If it costs 2 or less, you may play it for free"
    # (The Invisible Hand JTL_89).  Pushed AFTER the draw and after this decision is
    # popped, so the free play lands on a clean stack; the whitelist pins the play to
    # exactly the just-drawn card.  DEVIATION: play_from_hand has no decline, so the
    # "you may" collapses to mandatory — a free ≤N-cost unit entering play is never
    # a downside, and declining the search entirely is still available upstream.
    play_cap = ctx.get("then_play_free_cost_max")
    replay_ids = [ci.instance_id for ci in selected
                  if play_cap is not None
                  and int(getattr(ci.card_def, "cost", None) or 0) <= int(play_cap)]

    drawn_names = ", ".join(ci.card_def.display_name for ci in selected) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="deck_search",
        choice=f"drew {len(selected)} ({drawn_names})",
    ))
    if replay_ids and not s.is_terminal():
        src = s.find_instance(ctx["source_id"])
        if src is not None:
            push_play_from_hand(s, src[1], free=True,
                                eligible_ids=frozenset(replay_ids))
    # "If its cost is the chosen number, you may give N <token> tokens to a <trait>
    # unit" (Sense Through the Force ASH_235) — the number came down from the
    # choose_number decision that pushed this search.  The "you may" is the
    # select_token loop's own always-legal finish.
    tok = ctx.get("then_tokens_if_cost")
    if tok and selected and not s.is_terminal():
        cost = getattr(selected[0].card_def, "cost", None)
        if cost is not None and int(cost) == int(tok.get("number", -1)):
            src = s.find_instance(ctx["source_id"])
            if src is not None:
                push_select_token(
                    s, src[1], token_type=str(tok.get("token") or "Advantage"),
                    max_targets=1, controller=str(tok.get("controller") or "any"),
                    traits=([tok["trait"]] if tok.get("trait") else None),
                    token_count=int(tok.get("count", 1)))
    # "Then, put a card from your hand on top of your deck" (Captain Vaughn TS26_39).
    # Settled HERE, after the pop and after the draw, so the card just drawn is in
    # hand and offered — pushing this decision up front would read an empty hand and
    # fizzle before the search had put anything there.
    if ctx.get("then_top_from_hand") and not s.is_terminal():
        src = s.find_instance(ctx["source_id"])
        if src is not None:
            push_bottom_from_hand(s, src[1], count=1, top_only=True)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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


def _candidate_card_views(s: GameState, instance_ids) -> list[dict]:
    """``[{instance_id, card_id, card_name}]`` for the given instance ids, so a
    "select one of these cards" decision can carry the candidates' identities in
    its context for the UI to render (images + names).

    Used for decisions whose candidate cards are NOT laid out as clickable board
    subjects in the web client — cards in the **deck** (deck_search: redacted to
    the deciding player, so only the searcher sees them) or in the **discard /
    hand** (return_from_discard, the Sarlacc's discard recycle, a discard-played
    play_from_hand — all already public).  Without this the web UI had no way to
    pick the card (the deck is hidden; the discard pile is a non-clickable pile),
    leaving those decisions unresolvable on a touch device."""
    out: list[dict] = []
    for iid in instance_ids:
        res = s.find_instance(iid)
        if res is None:
            continue
        ci = res[1]
        out.append({
            "instance_id": iid,
            "card_id": ci.card_def.id,
            "card_name": ci.card_def.display_name,
        })
    return out


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

@dataclass
class KeepTopCard(Action):
    """Resolve a 'peek_top' decision by leaving the top card on top (no change)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"):
            raise IllegalActionError("No peek_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="left on top",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Leave the top card on top"


@dataclass
class BottomTopCard(Action):
    """Resolve a 'peek_top' (may_bottom) decision by moving the top card to the
    bottom of the deck (R2-D2)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode") != "may_bottom"):
            raise IllegalActionError("No peek_top (may_bottom) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        if ps.deck:
            ps.deck.append(ps.deck.pop(0))
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="put on bottom",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Put the top card on the bottom"


@dataclass
class DrawTopCard(Action):
    """Resolve a 'peek_top' (may_draw) decision by revealing and drawing the top
    card (C-3PO, when the peeked card's cost matched the chosen number)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_draw", "may_draw_or_discard_heal")):
            raise IllegalActionError("No peek_top (may_draw) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        _draw_cards(s, ps, 1)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="revealed and drew",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Reveal and draw the top card"


@dataclass
class ChooseNumber(Action):
    """Resolve a 'choose_number' decision (C-3PO): name a number, then peek the
    top card.  If its cost equals the chosen number, a 'peek_top' (may_draw)
    decision follows; otherwise the card is left on top and the effect ends."""
    number: int

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "choose_number"):
            raise IllegalActionError("No choose_number decision pending")
        ctx = state.pending_decisions[-1].context
        if not (int(ctx["lo"]) <= self.number <= int(ctx["hi"])):
            raise IllegalActionError(f"{self.number} is out of range")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="choose_number",
            choice=f"chose {self.number}",
        ))
        ps = s.player_by_id(ctx["controller_id"])
        found = s.find_instance(ctx["source_id"])
        source_ci = found[1] if found else None
        then = ctx.get("then")
        if then and source_ci is not None:
            # Sense Through the Force ASH_235: the chosen number is carried into a
            # deck search, whose DRAW finish pays off only if the drawn card's cost
            # matches it.  The decision is already popped, so the search lands on a
            # clean stack.
            if then.get("kind") == "deck_search_tokens_if_cost":
                push_deck_search(
                    s, source_ci, count=1, eligible=lambda cd: True, up_to=False,
                    window=int(then.get("window", 5)),
                    then_tokens_if_cost={**then, "number": int(self.number)})
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
            return s
        if ps.deck and source_ci is not None:
            top_cost = getattr(ps.deck[0].card_def, "cost", None)
            matched = top_cost is not None and top_cost == self.number
            # Always reveal the top card to the controller so they can study it,
            # even on a miss (a "reveal_only" peek that just leaves it on top) —
            # on a match the "may_draw" peek additionally offers DrawTopCard.
            push_peek_top(s, source_ci, mode="may_draw" if matched else "reveal_only")
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Choose the number {self.number}"


@dataclass
class DiscardTopCard(Action):
    """Resolve a 'peek_top' decision by discarding the top card of the deck (Ezra
    Bridger SOR_192; Reanimated Night Trooper ASH_45's ``may_discard``)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_play_discard", "may_draw_or_discard_heal",
                        "may_discard")):
            raise IllegalActionError("No peek_top (may_play_discard) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        if ps.deck:
            card = ps.deck.pop(0)
            card.face_down = False
            card.zone = Zone.DISCARD
            ps.discard.append(card)
        # Reinforcement Walker SOR_119: discarding the top card also heals the
        # controller's base by ``discard_heal`` damage.
        heal = int(top.context.get("discard_heal", 0) or 0)
        if heal and ps.base_instance is not None and not _bases_cannot_heal(s):
            before = int(ps.base_instance.damage)
            ps.base_instance.damage = max(0, ps.base_instance.damage - heal)
            note_base_healed(s, ps.base_instance, before - ps.base_instance.damage)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="discarded",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Discard the top card"


@dataclass
class PlayTopCard(Action):
    """Resolve a 'peek_top' (may_play_discard) decision by playing the top card of
    the deck for its cost (Ezra Bridger SOR_192).  For an upgrade, ``upgrade_target_id``
    names the host.  The decision is popped FIRST so the played card's own keyword /
    When Played triggers land on a clean stack (the "pop, then act" gotcha)."""
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_play_discard", "may_play")):
            raise IllegalActionError("No peek_top play decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ps = s.player_by_id(top.context["controller_id"])
        if not ps.deck:
            raise IllegalActionError("Deck is empty; nothing to play")
        ci = ps.deck[0]
        reduction = int(top.context.get("cost_reduction", 0) or 0)
        free = bool(top.context.get("free"))
        base = _play_cost(s, ci, ps, target_host_id=self.upgrade_target_id)
        cost = 0 if free else max(0, base - reduction)
        if not _affordable_with_credits(ps, cost, s):
            raise IllegalActionError("Cannot afford the top card")
        # "You may use the Force … If you do, play that card" (As I Have Foreseen
        # LOF_188): the Force token is the price of THIS option.  Spent through the
        # single chokepoint, so the WhenYouUseForce observers see it.
        if top.context.get("force_cost"):
            if not spend_force_token(s, ps):
                raise IllegalActionError("No Force token to spend")
        # Pop the decision before the card enters play (so its own triggers land on
        # a clean stack), then remove it from the deck and play it.
        s.pending_decisions.pop()
        ps.deck.pop(0)
        ci.face_down = False
        _pay_play_cost(s, ps, cost)
        _consume_play_discount(s, ci, ps)
        _consume_standing_discount(s, ci, ps)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice=f"played {ci.card_def.display_name}",
        ))
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
        after_idx = top.after_resolve_player_index
        if isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, cost_paid=cost)
        elif isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
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
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return "Play the top card" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


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


# ── Modal "choose one" decision (Leia Organa SOR_189) ─────────────────────────
#
# A "modal" decision presents the controller with a "choose one" effect, then a
# target choice for the selected mode.  Leia Organa ("Either ready a resource or
# exhaust a unit") is the first user.  A mode whose legal targets are
# interchangeable (``_MODAL_FUNGIBLE_MODES``, e.g. "ready a resource") skips the
# target step and resolves on an arbitrary target.  See push_modal.

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
#
# "An opponent chooses one: [You ready up to 6 resources] / [You ready a friendly
# unit.  If it's a Wookiee unit, attack with it.  It gets +2/+0 for this attack]."
# A cross-decider two-stage decision (the opponent_chooses_target SHD_246 decider-
# shift precedent): stage "mode" is decided by the OPPONENT, stage "ready" (only for
# the second mode) by the CONTROLLER.  push_modal is controller-only and its modes
# don't chain a granted attack, so this is its own decision kind.

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

@dataclass
class ChooseOwnTarget(Action):
    """The opponent chooses one of their own units or base to be the potential
    damage target (Grey Squadron Y-Wing SHD_246).  Advances the
    'opponent_chooses_target' decision to its confirm stage."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose":
            raise IllegalActionError("Opponent-chooses-target decision is past the choose stage")
        if self.target_id not in _opponent_chosen_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal target to choose")
        ctx["chosen_id"] = self.target_id
        if ctx.get("disposition") in ("defeat", "exhaust"):
            # Single mandatory stage (LOF_43 "Defeat that unit" / LOF_15 "Exhaust
            # that unit"): resolve the instant the opponent chooses — no
            # controller confirm/decline.
            return _resolve_opponent_chooses_target(s, top, deal=True)
        ctx["stage"] = "confirm"
        controller_idx = s.player_index(ctx["controller_id"])
        top.deciding_player_id = ctx["controller_id"]
        s.active_player_index = controller_idx
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["opponent_id"],
            kind="opponent_chooses_target",
            choice=f"chose {self.target_id}",
        ))
        return s

    def describe(self) -> str:
        return f"Choose own target {self.target_id}"


@dataclass
class ConfirmOpponentDamage(Action):
    """Deal the stored damage to the opponent's chosen target (Grey Squadron
    Y-Wing SHD_246 "you may deal 2 damage to it")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "confirm":
            raise IllegalActionError("Opponent-chooses-target decision is not at the confirm stage")
        return _resolve_opponent_chooses_target(s, top, deal=True)

    def describe(self) -> str:
        return "Deal damage to the chosen target"


@dataclass
class DeclineOpponentDamage(Action):
    """Decline the optional damage — the ability does nothing (Grey Squadron
    Y-Wing SHD_246 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "confirm":
            raise IllegalActionError("Opponent-chooses-target decision is not at the confirm stage")
        return _resolve_opponent_chooses_target(s, top, deal=False)

    def describe(self) -> str:
        return "Decline dealing the damage"


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

@dataclass
class ChooseUnitToDefeat(Action):
    """The current player chooses one of their own matching units to be defeated
    (Merciless Contest TWI_238).  Advances the 'each_player_defeats' decision to
    the next player, or resolves it (defeats all chosen units) once everyone has
    chosen."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "each_player_defeats"):
            raise IllegalActionError("No each-player-defeats decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        current_player = ctx["order"][ctx["idx"]]
        if self.target_id not in _each_player_defeat_targets(s, ctx, current_player):
            raise IllegalActionError(f"{self.target_id} is not a legal unit to defeat")
        ctx["chosen_ids"].append(self.target_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=current_player,
            kind="each_player_defeats",
            choice=f"chose {self.target_id}",
        ))
        # Advance to the next player who has an eligible unit.
        ctx["idx"] += 1
        while (ctx["idx"] < len(ctx["order"])
               and not _each_player_defeat_targets(s, ctx, ctx["order"][ctx["idx"]])):
            ctx["idx"] += 1
        if ctx["idx"] < len(ctx["order"]):
            next_player = ctx["order"][ctx["idx"]]
            top.deciding_player_id = next_player
            s.active_player_index = s.player_index(next_player)
            return s
        return _resolve_each_player_defeats(s, top)

    def describe(self) -> str:
        return f"Choose unit to defeat {self.target_id}"


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


# ── Opponent may discard a random card, else the controller gets an effect
#    (Political Pressure TWI_222) ──────────────────────────────────────────────
#
# "Choose an opponent. They may discard a random card from their hand. If they
# don't, create 2 Battle Droid tokens."  A self-contained 'may_discard' decision
# handed to the OPPONENT (the say_no SOR_233 deciding-player-shift precedent): the
# opponent either discards a random card (RNG-chosen — the text says "random") to
# prevent the else-effect, or declines, in which case the source's controller gets
# the else-effect (create N token units).  See push_may_discard_else_tokens.

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
#    power, then defeat the chosen ones (Consolidation of Power TWI_89) ─────────
#
# A select-any-number loop (the multi_capture_pairing shape) whose payoff is a
# DYNAMIC cap: the combined effective power of the chosen units becomes the
# ``cost_max`` of a free ``play_from_hand``.  The chosen units are defeated AFTER
# that play — threaded through the play decision's new ``then_defeat_ids`` — so a
# unit's power still counts while it is being spent, which is the whole trade.

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


@dataclass
class SelectDamageTarget(Action):
    """Pick one unit to deal 1 damage to (IG-2000 JTL_140 select_damage decision).
    Chosen targets are recorded; damage is dealt after the decision pops."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_damage"):
            raise IllegalActionError("No select-damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _select_damage_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible damage target")
        ctx["chosen"].append(self.target_id)
        ctx["remaining"] = int(ctx["remaining"]) - 1
        if int(ctx["remaining"]) <= 0 or not _select_damage_targets(s, ctx):
            return _resolve_select_damage(s, top)
        return s

    def describe(self) -> str:
        return f"Deal 1 damage to {self.target_id}"


@dataclass
class FinishSelectDamage(Action):
    """Stop selecting damage targets ("up to N") — deal recorded damage and pop."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_damage"):
            raise IllegalActionError("No select-damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_select_damage(s, top)

    def describe(self) -> str:
        return "Finish dealing damage"


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


@dataclass
class AssignIndirectDamage(Action):
    """Receiving player assigns all indirect damage to one of their targets
    (assign_indirect_damage decision — First Order Stormtrooper JTL_132, Dengar
    JTL_139, etc.)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "assign_indirect_damage"):
            raise IllegalActionError("No assign-indirect-damage decision pending")
        if self.target_id not in _assign_indirect_damage_targets(state, state.pending_decisions[-1].context):
            raise IllegalActionError(f"{self.target_id} is not a valid indirect-damage target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ctx["chosen_id"] = self.target_id
        return _resolve_assign_indirect_damage(s, top)

    def describe(self) -> str:
        return f"Assign indirect damage to {self.target_id}"


def _deploy_leader_into_arena(s: GameState, ps: PlayerState,
                              leader_ci: CardInstance) -> GameState:
    """Flip an undeployed leader into its arena, ready, and fire the deploy bus.

    The shared body of ``DeployLeader.apply`` (minus the resource/threshold check
    and the end-of-action active-player switch), so a card ability can deploy a
    leader *as an effect* (free, off-threshold) — Grogu ASH_18 "When you play a
    unique unit that costs 4 or more: you may deploy him".  Fires ``LeaderDeployed``
    + its ``WhenDeployed`` triggers and the Plot check, exactly like a normal
    deploy; the caller owns any turn-flow switch.
    """
    ps.base_zone.remove(leader_ci)
    target_zone = leader_ci.zone_for_arena()
    leader_ci.zone = target_zone
    leader_ci.deployed = True
    leader_ci.epic_action_spent = True
    # CR: a deployed leader enters the arena READY ("Flip him, ready him, and
    # move him to the ground arena"), even if it was exhausted before —
    # unlike a non-leader unit, which enters exhausted. So a freshly deployed
    # leader can attack the same round.
    leader_ci.exhausted = False
    arena_list = ps.ground_arena if target_zone == Zone.GROUND_ARENA else ps.space_arena
    arena_list.append(leader_ci)
    # A deployed leader ENTERED PLAY this phase, exactly like a played unit — the
    # cards that count "friendly units that entered play this phase (including
    # tokens and leaders)" say so explicitly (Anakin Skywalker TS26_2, Padmé
    # Amidala TS26_4), and so does Hidden's own leader reminder ("can't be attacked
    # if she was deployed this phase" — Asajj Ventress TS26_7), which reads this
    # same set through ``_hidden_protected``.  Recorded before the deploy bus fires,
    # so a WhenDeployed ability already sees it.
    s.game_memory.units_played_this_phase.add(leader_ci.instance_id)
    deploy_evt = LeaderDeployed(
        player_id=ps.player_id,
        instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name,
        arena=leader_ci.arena() or "Ground",
    )
    s.event_log.append(deploy_evt)
    get_bus().fire(s, deploy_evt)
    # Phase 3: "When Deployed" triggers (Leia Organa LAW_10).  The leader is
    # now in the arena (deployed), so _collect_triggers sees it as the
    # deployed-side source; fire_triggered_abilities may push a decision.
    from swu.abilities.resolver import fire_triggered_abilities
    after_idx = 1 - s.active_player_index
    s = fire_triggered_abilities(s, deploy_evt, after_all_player_idx=after_idx)
    # Plot: "When you deploy a leader, you may play this card from your
    # resources, paying its cost."  Snapshot the deploying player's Plot
    # resources and, if any can actually be played now, push a "plot"
    # decision.  (fire_triggered_abilities does not change active_player, so
    # s.active_player is still the deploying player.)
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
    return s


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


def _resolve_unique_candidates(state: GameState, ctx: dict) -> list[str]:
    """The still-in-play duplicate instance ids the controller may keep."""
    return [tid for tid in ctx["candidate_ids"] if state.find_instance(tid) is not None]


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
def _trigger_option_actions(state: GameState, top: PendingDecision) -> list[Action]:
    source_id = top.context.get("source_id", "")
    found = state.find_instance(source_id)
    card_name = found[1].card_def.display_name if found else ""
    return [
        AcceptTrigger(source_id, card_name),
        DeclineTrigger(source_id, card_name),
    ]

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
def _select_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectDamageTarget(tid) for tid in _select_damage_targets(state, top.context)]
    acts.append(FinishSelectDamage())  # "up to" — stopping early is always legal
    return acts

# ── Receiving player assigns all indirect damage to one target ──────────
def _assign_indirect_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [AssignIndirectDamage(tid)
            for tid in _assign_indirect_damage_targets(state, top.context)]

# ── Peek at top of deck (R2-D2 SOR_236, C-3PO SOR_238) ────────────────
def _peek_top_actions(state: GameState, top: PendingDecision) -> list[Action]:
    mode = top.context.get("mode")
    if mode == "may_draw_or_discard_heal":
        # Reinforcement Walker SOR_119: a mandatory binary — no KeepTopCard.
        return [DrawTopCard(), DiscardTopCard()]
    acts = [KeepTopCard()]
    if mode == "may_bottom":
        acts.append(BottomTopCard())
    elif mode == "may_discard":
        # "Look at the top card of a deck.  You may discard it" (Reanimated
        # Night Trooper ASH_45) — the discard sibling of ``may_bottom``.
        acts.append(DiscardTopCard())
    elif mode == "may_draw":
        acts.append(DrawTopCard())
    elif mode in ("may_play_discard", "may_play"):
        if mode == "may_play_discard":
            acts.append(DiscardTopCard())
        # The play cost may be reduced (or free) — apply the same reduction the
        # PlayTopCard resolution will, so affordability and the offer agree.
        reduction = int(top.context.get("cost_reduction", 0) or 0)
        free = bool(top.context.get("free"))
        ps = state.player_by_id(top.context["controller_id"])
        if ps.deck:
            ci = ps.deck[0]
            cd = ci.card_def
            if isinstance(cd, Upgrade):
                for host in _eligible_upgrade_targets(state, ci):
                    base = _play_cost(state, ci, ps, target_host_id=host.instance_id)
                    cost = 0 if free else max(0, base - reduction)
                    if _affordable_with_credits(ps, cost, state):
                        acts.append(PlayTopCard(host.instance_id))
            elif isinstance(cd, (Unit, Event)):
                base = _play_cost(state, ci, ps)
                cost = 0 if free else max(0, base - reduction)
                if _affordable_with_credits(ps, cost, state):
                    acts.append(PlayTopCard())
    return acts

# ── Choose a number (C-3PO SOR_238) ───────────────────────────────────
def _choose_number_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    return [ChooseNumber(n)
            for n in range(int(ctx["lo"]), int(ctx["hi"]) + 1)]

# ── Look at an opponent's hand (Viper Probe Droid SOR_228) ────────────
def _look_hand_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [AckLookHand()]

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
#    Squadron Y-Wing SHD_246) ────────────────────────────────────────────
def _opponent_chooses_target_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "choose":
        return [ChooseOwnTarget(t) for t in _opponent_chosen_targets(state, ctx)]
    # stage "confirm"
    return [ConfirmOpponentDamage(), DeclineOpponentDamage()]

# ── Controller picks up to 2 non-leader units; the opponent chooses which
#    returns to hand, the other is bottomed (I Had No Choice SOR_187) ──────
def _opponent_split_bounce_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "choose":
        acts: list[Action] = [SelectSplitBounceUnit(t)
                              for t in _split_bounce_candidates(state, ctx)]
        acts.append(FinishSplitBounce())
        return acts
    # stage "split" — opponent picks which of the two returns to hand
    return [ChooseSplitReturn(cid) for cid in ctx["selected_ids"]]

# ── Owner of a returned unit may replay it for free (Baylan Skoll
#    LOF_185, Rio Durant LAW_93) ────────────────────────────────────────
def _owner_may_replay_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    card_id = top.context.get("card_id")
    acts: list[Action] = []
    if any(c.instance_id == card_id for c in deciding_ps.hand):
        acts.append(ReplayReturnedUnit(card_id))
    acts.append(DeclineReplay())  # "may play it for free"
    return acts

# ── Owner of a chosen in-play unit puts it on top or bottom of their deck
#    (Qui-Gon Jinn LOF_200) ─────────────────────────────────────────────────
def _put_on_deck_actions(state: GameState, top: PendingDecision) -> list[Action]:
    card_id = top.context.get("card_id")
    return [PutOnDeckTop(card_id), PutOnDeckBottom(card_id)]

# ── Each player chooses one of their own non-leader units; defeat them
#    (Merciless Contest TWI_238) ────────────────────────────────────────────
def _each_player_defeats_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    current_player = ctx["order"][ctx["idx"]]
    return [ChooseUnitToDefeat(t)
            for t in _each_player_defeat_targets(state, ctx, current_player)]

# ── Name a card; opponent-owned non-leader copies lose all abilities while the
#    namer is in play (Galen Erso P25_31 WhenPlayed) ─────────────────────────
def _name_a_card_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [NameCard(n) for n in top.context["names"]]

# ── Opponent may give up a non-leader unit to be captured, else the source
#    readies (Grand Admiral Thrawn SEC_193 WhenPlayed) ─────────────────────
def _capture_or_ready_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = [ChooseCaptureVictim(t)
                          for t in _capture_or_ready_targets(state, top.context)]
    acts.append(DeclineCaptureVictim())  # "An opponent MAY choose …"
    return acts

# ── Choose N friendly units to spare, defeat all other friendly units
#    (Always Two LOF_42) ─────────────────────────────────────────────────────
def _choose_units_sacrifice_rest_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [ChooseUnitToSpare(t)
            for t in _choose_units_sacrifice_rest_targets(state, top.context)]

# ── Unique Rule: keep one duplicate copy, defeat the rest (state-based) ──────
def _resolve_unique_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [KeepUniqueCopy(t)
            for t in _resolve_unique_candidates(state, top.context)]

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
#    Pressure TWI_222) ──────────────────────────────────────────────────────
def _may_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    if state.player_by_id(top.context["opponent_id"]).hand:
        acts.append(DiscardRandomCard())
    acts.append(DeclineDiscard())
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
    # else: nothing playable and no follow-up — caller hands the turn over.


# ── Play an EVENT from hand as an ability (Bib Fortuna SOR_177) ────────────────
# The event sibling of the units-only ``push_play_from_hand`` subsystem.  Events
# never enter play — they resolve via ``_resolve_event_ability`` and go to discard —
# so this is a distinct decision kind rather than a flag on the unit path.


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
# The Smuggle sibling of ``push_play_event_from_hand``: an ability that plays a card
# from the RESOURCE zone using its Smuggle keyword at a cost reduction, WITHOUT handing
# the turn over (the ability's own resolution governs), then optionally defeats one of
# the controller's resources.  Reuses the SmugglePlay mechanics wholesale.

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
# The Piloting sibling of ``push_play_via_smuggle``: an ability that plays a card
# from HAND using its Piloting keyword at a cost reduction, WITHOUT handing the
# turn over.  Reuses the PilotPlay mechanics (``_piloting_cost`` / ``_attach_pilot``)
# wholesale, so the pilot's own upgrade triggers and stat contribution are
# unchanged.

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


# ── Deck search-and-select push helper (Tarkin SOR_84, Recruit SOR_123) ───────

def _search_window_doubled(s: GameState, searcher_id: str) -> bool:
    """Whether ``searcher_id`` has a ``SearchWindowDoubler`` in play (Arcana Star
    Map ASH_84).  Walks their arena units AND each unit's attached upgrades, so the
    marker works printed on a unit or conferred by an upgrade onto its host; a
    suppressed host (Mind Trick LOF_202 / Imprisoned SHD_72) confers nothing."""
    from swu.abilities.registry import get_abilities, SearchWindowDoubler
    ps = s.player_by_id(searcher_id)
    for host in ps.ground_arena + ps.space_arena:
        if ability_suppressed(s, host):
            continue
        for ci in (host, *host.attached_upgrades):
            if not hasattr(ci.card_def, "set_code"):
                continue
            if any(isinstance(spec, SearchWindowDoubler)
                   for spec in get_abilities(ci.card_def.set_code or "",
                                             ci.card_def.card_number or "")):
                return True
    return False


def push_deck_search(
    s: GameState, source_ci: CardInstance,
    *,
    count: int,
    eligible: Callable[[object], bool],
    up_to: bool,
    window: int = 5,
    rest_disposition: str = "bottom",
    disposition: Optional[str] = None,
    decider_id: Optional[str] = None,
    deck_owner_id: Optional[str] = None,
    play_discount: int = 0,
    then_play_free_cost_max: Optional[int] = None,
    budget: Optional[int] = None,
    then_borrowed_attack_by: Optional[str] = None,
    then_tokens_if_cost: Optional[dict] = None,
    then_top_from_hand: bool = False,
) -> None:
    """Push a 'deck_search' decision: "Search the top ``window`` cards of your deck
    for <eligible> cards, reveal and draw up to ``count`` of them, then put the
    rest on the bottom of your deck in a random order."

    ``disposition`` controls what happens to the SELECTED cards (default ``None`` —
    draw them to hand).  ``"discard_free_replay"`` (Cobb Vanth SHD_115: "search … for
    a unit that costs 2 or less and discard it.  For this phase, you may play that
    card from your discard pile for free") instead sends each selected card to the
    discard pile and flags it in ``game_memory.free_discard_play_this_phase`` (the
    Second Chance SHD_53 free-discard-replay seam).  ``"discard_play_discount"`` is
    its DISCOUNTED sibling (Aid from the Innocent TWI_201: "search the top 10 …
    for 2 Heroism non-unit cards and discard them.  For this phase, you may play
    the discarded cards, and they each cost 2 resources less") — each selected card
    is discarded and recorded in ``game_memory.discard_play_discount_this_phase``
    at ``play_discount`` resources off.

    ``rest_disposition`` controls where the un-taken searched cards go on finish:
    ``"bottom"`` (default — the Tarkin/Recruit convention: bottom in a seeded-random
    order) or ``"discard"`` (I've Found Them IBH_9: "discard the other revealed
    cards").  (The unrelated ``"play"`` disposition is set only by
    ``push_search_and_play`` and keys off ``ctx["disposition"]``.)

    Parameters
    ----------
    count
        Maximum number of cards the controller may take.
    eligible
        Predicate on a card_def — only matching cards among the searched window are
        offered as candidates.  Evaluated once, at push time; the resulting ids are
        stored, so the decision context stays JSON-serialisable.
    up_to
        True for "up to N" (Tarkin): a FinishSearch is always offered, so taking 0
        is legal.  False for "search for a <thing>" (Recruit): the take is mandatory
        if able — a pick is forced while an eligible candidate remains.
    window
        How many top cards to search (default 5).

    The decision is pushed whenever the deck has at least one card in the window
    (even with no eligible candidate — the un-taken searched cards must still be
    bottomed in a random order, which FinishSearch handles).  With an empty deck the
    effect fizzles cleanly and the caller hands the turn over.
    """
    # ``decider_id`` (default: the source's owner) is the player whose deck is
    # searched and who makes the selection — a collector-decided search (a bounty
    # whose "search YOUR deck" resolves for the OPPONENT of the dying host, the
    # push_select_token decider_id convention).  When overridden the turn resumes
    # with whoever is currently active (the attacker mid-combat), not the source's
    # opponent.
    #
    # ``deck_owner_id`` (default: the decider) separates WHOSE DECK is searched from
    # WHO decides — "look at the top 2 cards of the DEFENDING player's deck.  Discard
    # 1 of those cards" (Sabé SEC_17), where the searcher never owns the cards.  The
    # decision context's ``controller_id`` is the deck owner throughout (the window,
    # the finish, and any discard/draw land on their side); ``deciding_player_id``
    # is the searcher.
    searcher_id = decider_id or source_ci.owner_id
    deck_id = deck_owner_id or searcher_id
    ps = s.player_by_id(deck_id)
    # "If you would search a number of cards from your deck, search twice that
    # number of cards instead" (Arcana Star Map ASH_84).  Read HERE — the single
    # entry point where the window is still just a number — so every search route
    # (plain, search-and-play, search-and-play-an-upgrade, a foreign search) is
    # covered at once.  Only the window doubles; ``count`` is untouched.
    if _search_window_doubled(s, searcher_id):
        window = int(window) * 2
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids = [ci.instance_id for ci in searched if eligible(ci.card_def)]
    owner_idx = s.player_index(searcher_id)
    after_idx = (1 - owner_idx) if decider_id is None else s.active_player_index
    dec = PendingDecision(
        deciding_player_id=searcher_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": deck_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "up_to": bool(up_to),
            "window": int(window),
            "rest_disposition": str(rest_disposition),
            "play_discount": int(play_discount),
            # Combined-COST budget over the picks ("any number of Clone units with
            # combined cost 4 or less" — Sifo-Dyas LOF_117).  The ctx key and both
            # its guards (the enumeration filter and SelectSearchCard's defensive
            # re-check) were built for Darth Vader SOR_87's search-and-play; the
            # plain deck_search push simply had no way to set it before.
            **({"budget": int(budget)} if budget is not None else {}),
            # "…and draw it.  If it costs N or less, you may play it for free"
            # (The Invisible Hand JTL_89) — settled at the draw branch of
            # _finish_deck_search, which whitelists the drawn card into a free
            # push_play_from_hand.  None (the default) leaves the draw alone.
            "then_play_free_cost_max": (int(then_play_free_cost_max)
                                        if then_play_free_cost_max is not None
                                        else None),
            # "…and discard it.  Then, you may attack with this unit.  For this
            # attack, this unit gains the discarded unit's abilities" (Improvised
            # Identity ASH_230) — the named unit's granted attack is pushed at the
            # ``discard`` disposition's finish, borrowing from the discarded card.
            "then_borrowed_attack_by": then_borrowed_attack_by,
            # "If its cost is the chosen number, you may give 3 Advantage tokens to
            # a Force unit" (Sense Through the Force ASH_235) — settled at the DRAW
            # branch, which is the only place the drawn card's cost is known.
            "then_tokens_if_cost": (dict(then_tokens_if_cost)
                                    if then_tokens_if_cost else None),
            # "Then, put a card from your hand on top of your deck" (Captain Vaughn
            # TS26_39) — settled AFTER the search, because the card it just drew is
            # part of what may be put back and the hand may be empty until then.
            "then_top_from_hand": bool(then_top_from_hand),
            **({"disposition": str(disposition)} if disposition else {}),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=searcher_id,
        kind="deck_search",
    ))


def push_search_and_play(
    s: GameState, source_ci: CardInstance,
    *,
    window: int,
    cost_reduction: int = 0,
    eligible: Optional[Callable[[object], bool]] = None,
    enters_ready: bool = False,
    return_at_regroup: bool = False,
    bottom_at_regroup: bool = False,
    free: bool = False,
    decider_id: Optional[str] = None,
) -> None:
    """Push a 'deck_search' decision that PLAYS the chosen unit (Kelleran Beq
    LOF_100: "Search the top N cards of your deck for a unit, reveal it, and play
    it.  It costs ``cost_reduction`` resources less.").

    The search-and-play variant of ``push_deck_search`` (``disposition="play"``):
    candidates are the units in the top ``window`` cards that the controller can
    afford to play at their effective cost less ``cost_reduction`` (credits cover a
    shortfall, like every other play path).  Exactly one is chosen (``max_select``
    1, ``up_to`` False — mandatory if able, so the play is forced while an
    affordable unit remains); ``_finish_deck_search``'s play branch pays the
    reduced cost, puts the unit into play (firing its own keyword / When Played
    triggers), and bottoms the un-taken searched cards in a seeded-random order.
    With no affordable unit in the window the decision still resolves cleanly via
    FinishSearch (nothing played, the rest bottomed).  An empty deck is a no-op.

    ``eligible`` optionally narrows the searched-for units beyond "any Unit" (Triple
    Dark Raid SHD_194: "search … for a Vehicle").  ``enters_ready`` puts the played
    unit into play ready, and ``return_at_regroup`` flags it to bounce to its owner's
    hand at the start of the next regroup phase ("enters play ready.  Return it to
    its owner's hand at the end of the phase" — reusing the Commandeer JTL_235
    delayed-return flag, the action→regroup boundary).  ``bottom_at_regroup`` is that
    flag's DECK-bound sibling — "At the start of the regroup phase, put that unit on
    the bottom of your deck (if it is still in play)" (Maz Kanata LAW_74), a
    relocation rather than a defeat, so the lent unit's When Defeated never fires.
    """
    # ``decider_id`` (default: the source's owner) is the player whose deck is
    # searched and who plays the found unit under their control — a collector-decided
    # search-and-play (a bounty whose "search YOUR deck … and play it" resolves for
    # the OPPONENT of the dying host; Bounty Hunter's Quarry SHD_123, the
    # push_deck_search decider_id convention).  ``free`` plays the found unit at cost
    # 0 (candidates then need not be affordability-filtered).
    actor_id = decider_id or source_ci.owner_id
    ps = s.player_by_id(actor_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids: list[str] = []
    for ci in searched:
        cd = ci.card_def
        if not isinstance(cd, Unit):
            continue
        if eligible is not None and not eligible(cd):
            continue
        if free:
            candidate_ids.append(ci.instance_id)
            continue
        cost = max(0, _effective_cost(cd, ps, s) - cost_reduction)
        if cost <= ps.available_resources + _usable_credits(s, ps):
            candidate_ids.append(ci.instance_id)
    owner_idx = s.player_index(actor_id)
    after_idx = (1 - owner_idx) if decider_id is None else s.active_player_index
    dec = PendingDecision(
        deciding_player_id=actor_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": actor_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": 1,
            "up_to": False,
            "window": int(window),
            "disposition": "play",
            "cost_reduction": int(cost_reduction),
            "free": bool(free),
            "enters_ready": bool(enters_ready),
            "return_at_regroup": bool(return_at_regroup),
            "bottom_at_regroup": bool(bottom_at_regroup),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=actor_id,
        kind="deck_search",
    ))


def push_search_and_play_upgrade(
    s: GameState, source_ci: CardInstance,
    *, window: int, host_id: str, cost_reduction: int = 0,
) -> None:
    """Push a 'deck_search' decision that plays the chosen UPGRADE onto one
    pre-chosen host — "search the top ``window`` cards of your deck for an upgrade
    that can attach to that unit, reveal it, and play it on that unit.  It costs
    ``cost_reduction`` resources less" (Reforge ASH_90).

    The upgrade sibling of ``push_search_and_play``: candidates are the Upgrades in
    the window whose "Attach to …" restriction admits ``host_id`` (the same
    ``_upgrade_target_spec`` gate every other attachment site uses) and which the
    controller can afford at the reduced price.  ``_finish_deck_search``'s
    ``play_upgrade`` branch pays that price, emits CardPlayed and attaches — so the
    upgrade's own When Played trigger fires exactly as a hand play's would.  With no
    eligible upgrade the decision still resolves cleanly (nothing played, the window
    bottomed in a seeded-random order)."""
    from swu.abilities.resolver import _spec_matches_ci
    actor_id = source_ci.owner_id
    ps = s.player_by_id(actor_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    host_res = s.find_instance(host_id)
    if host_res is None:
        return
    _, host = host_res
    candidate_ids: list[str] = []
    for ci in searched:
        cd = ci.card_def
        if not isinstance(cd, Upgrade):
            continue
        spec = _upgrade_target_spec(cd)
        if spec is not None and not _spec_matches_ci(spec, host, ci, s, {}):
            continue
        cost = max(0, _effective_cost(cd, ps, s) - cost_reduction)
        if cost <= ps.available_resources + _usable_credits(s, ps):
            candidate_ids.append(ci.instance_id)
    owner_idx = s.player_index(actor_id)
    dec = PendingDecision(
        deciding_player_id=actor_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": actor_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": 1,
            "up_to": False,
            "window": int(window),
            "disposition": "play_upgrade",
            "upgrade_host_id": host_id,
            "cost_reduction": int(cost_reduction),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=actor_id,
        kind="deck_search",
    ))


def push_search_and_play_multiple(
    s: GameState, source_ci: CardInstance,
    *,
    window: int,
    budget: int,
    eligible: Callable[[object], bool],
    max_units: Optional[int] = None,
) -> None:
    """Push a 'deck_search' decision that PLAYS ANY NUMBER of chosen units FOR FREE
    under a combined-cost budget (Darth Vader SOR_87: "Search the top ``window``
    cards of your deck for any number of [Villainy] units with combined cost
    ``budget`` or less and play each of them for free").

    The multi-select, budgeted, free-play sibling of ``push_search_and_play``:
    ``disposition="play"`` + ``free=True`` (each chosen unit is played at cost 0)
    + ``budget`` (the picked units' combined *printed* cost may not exceed it; the
    ``deck_search`` legal-actions builder shrinks the offered candidates as units
    are taken).  ``up_to=True`` so a FinishSearch is always offered ("any number"
    includes 0).  Candidates are every card in the top ``window`` matching
    ``eligible`` regardless of individual cost — an unaffordable-within-budget one
    simply never becomes selectable.  ``max_select`` is the candidate count (or
    ``max_units`` when a "up to N units" cap applies — U-Wing Reinforcement SOR_104:
    "up to 3 units with combined cost 7 or less"), so the existing per-pick
    auto-finish fires once the cap (or everything) has been taken.
    ``_finish_deck_search``'s play branch pays 0 for each, puts it into play (firing
    its own keyword / When Played triggers), and bottoms the un-taken searched cards
    in a seeded-random order.  An empty deck is a no-op.
    """
    ps = s.player_by_id(source_ci.owner_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids = [ci.instance_id for ci in searched if eligible(ci.card_def)]
    max_select = (len(candidate_ids) if max_units is None
                  else min(len(candidate_ids), int(max_units)))
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": max_select,
            "up_to": True,
            "window": int(window),
            "disposition": "play",
            "free": True,
            "budget": int(budget),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="deck_search",
    ))


def _deck_search_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top deck_search decision (never empty: a forced
    FinishSearch is offered once no eligible candidate remains)."""
    ctx = top.context
    selected = set(ctx["selected_ids"])
    remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
    budget = ctx.get("budget")
    if budget is not None:
        # Combined-cost budget (Darth Vader SOR_87): only offer a candidate whose
        # printed cost fits within the budget left after the already-picked units.
        deck_by_id = {ci.instance_id: ci
                      for ci in state.player_by_id(ctx["controller_id"]).deck}
        spent = sum((deck_by_id[cid].card_def.cost or 0)
                    for cid in selected if cid in deck_by_id)
        left = int(budget) - spent
        remaining = [cid for cid in remaining
                     if cid in deck_by_id
                     and (deck_by_id[cid].card_def.cost or 0) <= left]
    acts: list[Action] = [SelectSearchCard(cid) for cid in remaining]
    if ctx.get("up_to") or not remaining:
        acts.append(FinishSearch())
    return acts


# ── Peek-at-top-of-deck push helpers (R2-D2 SOR_236, C-3PO SOR_238) ───────────

def push_peek_top(s: GameState, source_ci: CardInstance, *, mode: str,
                  cost_reduction: int = 0, free: bool = False,
                  discard_heal: int = 0, force_cost: bool = False) -> None:
    """Push a 'peek_top' decision: the controller looks at the top card of their
    deck and decides what to do with it.

    mode
        ``"may_bottom"`` — R2-D2: KeepTopCard (leave on top) vs BottomTopCard
        (put it on the bottom).
        ``"may_discard"`` — Reanimated Night Trooper ASH_45: KeepTopCard vs
        DiscardTopCard, the discard sibling of ``may_bottom``.
        ``"may_draw"`` — C-3PO, after a cost match: KeepTopCard (leave on top)
        vs DrawTopCard (reveal and draw it).
        ``"reveal_only"`` — C-3PO, after a cost miss: the card is just shown to
        the controller and stays on top (KeepTopCard is the only option, an
        acknowledgement) so the reveal is never invisible.
        ``"may_play_discard"`` — Ezra: KeepTopCard vs DiscardTopCard vs PlayTopCard.
        ``"may_play"`` — You're My Only Hope SOR_246: KeepTopCard vs PlayTopCard
        (no discard option); the play may carry a ``cost_reduction`` / ``free``.
        ``"may_draw_or_discard_heal"`` — Reinforcement Walker SOR_119: a *mandatory*
        binary DrawTopCard vs DiscardTopCard (no KeepTopCard) where discarding also
        heals ``discard_heal`` damage from the controller's base.

    ``cost_reduction`` / ``free`` apply to the play options in the may_play(_discard)
    modes (the top card costs that much less, or is free).  The deck is left
    untouched while the decision is open (the chosen action moves the card), so
    ``card_id`` (the top card's instance id) in the context is purely informational
    (for prompts/logging).  ``peeked_card_id`` / ``peeked_card_name`` carry the
    revealed card's identity so the UI can show it to the deciding player.  An empty
    deck is a clean no-op — no decision is pushed and the caller proceeds (the effect
    simply has nothing to look at)."""
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    top_ci = ps.deck[0]
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="peek_top",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "mode": mode,
            "cost_reduction": int(cost_reduction),
            "free": bool(free),
            "discard_heal": int(discard_heal),
            # "You may use the Force (lose your Force token).  If you do, play that
            # card" (As I Have Foreseen LOF_188) — the Force token is the PRICE of
            # the play option, spent by PlayTopCard and by nothing else, so keeping
            # the card on top costs nothing.
            "force_cost": bool(force_cost),
            "card_id": top_ci.instance_id,
            # The peeked card's true identity. Safe to surface: the decision
            # context is sent only to the deciding player (its own deck), so the
            # opponent never sees it. The UI renders this so the player can study
            # the card before choosing (KeepTopCard / BottomTopCard / DrawTopCard).
            "peeked_card_id": top_ci.card_def.id,
            "peeked_card_name": top_ci.card_def.display_name,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="peek_top",
    ))


def push_choose_number(
    s: GameState, source_ci: CardInstance, *, lo: int = 0, hi: int = 10,
    then: Optional[dict] = None,
) -> None:
    """Push a 'choose_number' decision (C-3PO): the controller names a number in
    ``lo..hi`` (inclusive).  On resolution (see ``ChooseNumber``) the top card is
    peeked; if its cost equals the chosen number a 'peek_top' (may_draw) decision
    follows, otherwise the card is left on top.

    The default range ``0..10`` covers every printed SOR card cost.  An empty
    deck is a clean no-op — there is nothing to peek, so no decision is pushed.

    ``then`` replaces that C-3PO tail with another continuation, dispatched in
    ``ChooseNumber.apply``.  Today the one arm is
    ``{"kind": "deck_search_tokens_if_cost", …}`` — "Choose a number, then search
    the top 5 … and draw it.  If its cost is the chosen number, you may give 3
    Advantage tokens to a Force unit" (Sense Through the Force ASH_235)."""
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="choose_number",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "lo": int(lo),
            "hi": int(hi),
            "then": dict(then) if then else None,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="choose_number",
    ))


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


# ── Sacrifice-a-resource push helper (Wrecker SHD_154) ────────────────────────

def _sacrifice_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal instance ids for the follow-up damage of a sacrifice_resource
    decision (recomputed from current state).  For Wrecker: any ground unit of
    either player (controller filter / arena come from the stored context)."""
    controller_id = ctx["controller_id"]
    target_controller = ctx.get("target_controller", "any")
    arena = ctx.get("target_arena")  # "ground" / "space" / None
    out: list[str] = []
    for p in state.players:
        if target_controller == "friendly" and p.player_id != controller_id:
            continue
        if target_controller == "enemy" and p.player_id == controller_id:
            continue
        units = []
        if arena in (None, "ground"):
            units += p.ground_arena
        if arena in (None, "space"):
            units += p.space_arena
        out.extend(u.instance_id for u in units)
    return out


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

def _opponent_chosen_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal instance ids the opponent may choose (recomputed from current state).

    By default any unit or base they control.  When ``ctx["ground_only"]`` is set
    (Jabba's Rancor LAW_216: "An opponent chooses a ground unit they control") the
    choice is restricted to the opponent's ground-arena units — no base, no space.
    When ``ctx["units_only"]`` is set (The Tragedy of Plagueis LOF_43: "An opponent
    chooses a unit they control") it is any unit in either arena — but no base.
    ``ctx["ready_only"]`` narrows any of those to READY units (Cal Kestis LOF_15:
    "An opponent chooses a READY unit they control").
    """
    opp = state.player_by_id(ctx["opponent_id"])
    ready_only = bool(ctx.get("ready_only"))

    def _ok(u) -> bool:
        return (not ready_only) or (not u.exhausted)

    if ctx.get("ground_only"):
        return [u.instance_id for u in opp.ground_arena if _ok(u)]
    if ctx.get("units_only"):
        return [u.instance_id
                for u in opp.ground_arena + opp.space_arena if _ok(u)]
    out = [u.instance_id for u in opp.ground_arena + opp.space_arena]
    base = opp.base_instance
    if base is not None:
        out.append(base.instance_id)
    return out


def push_opponent_chooses_target(
    s: GameState, source_ci: CardInstance, *, amount: int = 0,
    ground_only: bool = False, units_only: bool = False,
    disposition: str = "damage", ready_only: bool = False,
) -> None:
    """Push an 'opponent_chooses_target' decision: "An opponent chooses a unit or
    base they control. You may deal ``amount`` damage to it" (Grey Squadron
    Y-Wing SHD_246).

    Two stages with *different* deciding players (the say_no SOR_233 precedent):
    the opponent first picks one of their own cards (ChooseOwnTarget — mandatory,
    a base is always available), then control returns to the source's controller,
    who may ConfirmOpponentDamage / DeclineOpponentDamage.  The damage is dealt
    after the decision pops (the push_distribute_damage "pop, then deal" gotcha).
    Only pushed when the opponent has at least one card to choose.

    ``ground_only`` restricts the opponent's choice to their ground-arena units
    (Jabba's Rancor LAW_216: "An opponent chooses a ground unit they control") —
    no base, so the decision is skipped (the On Attack fizzles) when the opponent
    controls no ground units.

    ``disposition`` selects what happens to the chosen card:
      * ``"damage"`` (default) — the two-stage "you may deal ``amount``" flow above.
      * ``"defeat"`` — "Defeat that unit" (The Tragedy of Plagueis LOF_43): a
        *single* mandatory stage.  The opponent picks a unit (paired with
        ``units_only=True`` — no base is a legal choice) and it is defeated the
        instant they choose, with no controller confirm/decline stage.  Skipped
        (the event fizzles) when the opponent controls no eligible unit.
      * ``"exhaust"`` — "Exhaust that unit" (Cal Kestis LOF_15): the same single
        mandatory stage as ``"defeat"``, paired with ``units_only=True`` and
        ``ready_only=True`` so only a ready unit of theirs can be picked (an
        already-exhausted unit would be a no-op) — with none, nothing is pushed."""
    controller_id = source_ci.owner_id
    opponent_id = next(
        p.player_id for p in s.players if p.player_id != controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "stage": "choose",
        "amount": int(amount),
        "ground_only": bool(ground_only),
        "units_only": bool(units_only),
        "ready_only": bool(ready_only),
        "disposition": disposition,
    }
    if not _opponent_chosen_targets(s, ctx):
        return
    opp_idx = s.player_index(opponent_id)
    dec = PendingDecision(
        deciding_player_id=opponent_id,
        kind="opponent_chooses_target",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = opp_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=opponent_id,
        kind="opponent_chooses_target",
    ))


def _resolve_opponent_chooses_target(
    s: GameState, top, *, deal: bool
) -> GameState:
    """Pop the decision, then act on the opponent-chosen target.  For the
    ``"damage"`` disposition, (if ``deal``) deal the stored damage; for the
    ``"defeat"`` disposition (LOF_43), defeat the chosen unit outright.  The action
    happens AFTER popping (like push_sacrifice_resource_for_damage) so a resulting
    WhenDefeated trigger lands on a clean stack."""
    ctx = top.context
    chosen_id = ctx.get("chosen_id")
    disposition = ctx.get("disposition", "damage")
    s.pending_decisions.pop()
    if disposition == "defeat":
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"defeated {chosen_id}" if chosen_id is not None else "no target"),
        ))
        if chosen_id is not None:
            result = s.find_instance(chosen_id)
            if result is not None:
                ps, ci = result
                _defeat_unit(s, ps, ci)  # "Defeat that unit" — mandatory, ignores HP
    elif disposition == "exhaust":
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"exhausted {chosen_id}" if chosen_id is not None else "no target"),
        ))
        if chosen_id is not None:
            result = s.find_instance(chosen_id)
            if result is not None:
                result[1].exhausted = True  # "Exhaust that unit" (Cal Kestis LOF_15)
    else:
        amount = int(ctx["amount"])
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"dealt {amount} to {chosen_id}" if deal else "declined"),
        ))
        if deal and chosen_id is not None:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            source_name = (source_result[1].card_def.display_name
                           if source_result else None)
            _apply_deal_damage(s, chosen_id, amount, source_name=source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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

def _split_bounce_candidates(state: GameState, ctx: dict) -> list[str]:
    """Still-selectable candidates for the 'choose' stage: pushed non-leader unit
    ids that remain in-play arena units and are not already selected."""
    selected = set(ctx["selected_ids"])
    out: list[str] = []
    for cid in ctx["candidate_ids"]:
        if cid in selected:
            continue
        result = state.find_instance(cid)
        if result is None:
            continue
        ps, ci = result
        if any(ci in arena for arena in (ps.ground_arena, ps.space_arena)):
            out.append(cid)
    return out


def _resolve_split_bounce_choose(s: GameState) -> GameState:
    """Finish the 'choose' stage: 0 picked → clean fizzle; 1 picked → return it to
    its owner's hand; 2 picked → advance to the opponent's 'split' stage."""
    top = s.pending_decisions[-1]
    ctx = top.context
    selected = list(ctx["selected_ids"])
    if len(selected) >= 2:
        ctx["stage"] = "split"
        top.deciding_player_id = ctx["opponent_id"]
        s.active_player_index = s.player_index(ctx["opponent_id"])
        s.event_log.append(DecisionPushed(
            deciding_player_id=ctx["opponent_id"],
            kind="opponent_split_bounce",
        ))
        return s
    s.pending_decisions.pop()  # pop, then act
    if len(selected) == 1:
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(s, selected[0])
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="opponent_split_bounce",
        choice=(f"returned {selected[0]}" if len(selected) == 1 else "no units"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class SelectSplitBounceUnit(Action):
    """Stage 'choose' of opponent_split_bounce (I Had No Choice SOR_187): the
    source's controller adds a non-leader unit to the (up to 2) bounce pool.
    Reaching the max advances to the opponent's split stage."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose":
            raise IllegalActionError("opponent_split_bounce is past the choose stage")
        if self.instance_id not in _split_bounce_candidates(s, ctx):
            raise IllegalActionError(f"{self.instance_id} is not an eligible unit")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _resolve_split_bounce_choose(s)
        return s

    def describe(self) -> str:
        return f"Add {self.instance_id} to the bounce pool"


@dataclass
class FinishSplitBounce(Action):
    """Stop selecting units for opponent_split_bounce (I Had No Choice SOR_187).
    Always offered (the choice is "up to 2"), so a 0- or 1-pick finish is legal."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        return _resolve_split_bounce_choose(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish choosing units to bounce"


@dataclass
class ChooseSplitReturn(Action):
    """Stage 'split' of opponent_split_bounce (I Had No Choice SOR_187): the
    opponent picks which of the two chosen units returns to its owner's hand; the
    other is put on the bottom of its owner's deck."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "split":
            raise IllegalActionError("opponent_split_bounce is not at the split stage")
        selected = list(ctx["selected_ids"])
        if self.instance_id not in selected:
            raise IllegalActionError("Not one of the chosen units")
        other = next(cid for cid in selected if cid != self.instance_id)
        s.pending_decisions.pop()  # pop, then act
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(s, self.instance_id)      # to its owner's hand
        _apply_put_on_deck(s, other, to_top=False)      # the other → owner's deck bottom
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_split_bounce",
            choice=f"returned {self.instance_id}, bottomed {other}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Return {self.instance_id} to hand (bottom the other)"


def push_opponent_split_bounce(s: GameState, source_ci: CardInstance) -> None:
    """Push an 'opponent_split_bounce' decision (I Had No Choice SOR_187).  The
    source's controller chooses (stage "choose"); a two-pick pool later shifts to
    the opponent (stage "split").  Only pushed when at least one non-leader unit is
    in play (else the event fizzles cleanly)."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    candidate_ids: list[str] = []
    for p in s.players:
        for ci in p.ground_arena + p.space_arena:
            if isinstance(ci.card_def, Leader):
                continue  # "non-leader units"
            candidate_ids.append(ci.instance_id)
    if not candidate_ids:
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="opponent_split_bounce",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opponent_id,
            "stage": "choose",
            "candidate_ids": candidate_ids,
            "selected_ids": [],
            "max_select": 2,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="opponent_split_bounce",
    ))


def push_owner_may_replay(
    s: GameState, source_ci: CardInstance, returned_instance_id: str,
    *, grant_keyword: Optional[str] = None,
) -> None:
    """Push an 'owner_may_replay' decision (Baylan Skoll LOF_185 / Rio Durant
    LAW_93): the OWNER of a just-returned unit may play it from their hand for
    FREE ("return a non-leader unit to its owner's hand.  Then, its owner may play
    it for free").

    The unit must already have been returned to its owner's hand (via
    ``_apply_return_to_hand``) before calling this.  The decider is that owner,
    who may be the source's OPPONENT — the say_no SOR_233 / opponent_chooses_target
    SHD_246 deciding-player shift — so this cannot be expressed as an ordinary
    ``play_from_hand`` decision (which is always decided by the source's
    controller).  ``grant_keyword`` (e.g. "Shielded") is granted to the replayed
    unit for this phase, applied before its enter-play keyword bus fires (Rio's
    "It gains Shielded for this phase"; Baylan grants nothing).

    Only pushed when the returned card is actually in its owner's hand (a clean
    no-op otherwise — e.g. the target fizzled)."""
    result = s.find_instance(returned_instance_id)
    if result is None:
        return
    owner_ps, ci = result
    if ci not in owner_ps.hand or ci.owner_id != owner_ps.player_id:
        return
    owner_idx = s.player_index(ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=ci.owner_id,
        kind="owner_may_replay",
        context={
            "source_id": source_ci.instance_id,
            "card_id": returned_instance_id,
            "owner_id": ci.owner_id,
            "grant_keyword": grant_keyword,
        },
        after_resolve_player_index=s.player_index(source_ci.owner_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=ci.owner_id,
        kind="owner_may_replay",
    ))


# ── Each player chooses one of their own non-leader units; defeat them all
#    (Merciless Contest TWI_238) ──────────────────────────────────────────────

def _each_player_defeat_targets(state: GameState, ctx: dict, player_id: str) -> list[str]:
    """Legal instance ids ``player_id`` may choose (recomputed from current state):
    the player's own non-leader arena units (a deployed leader is a Leader card_def
    and so excluded, mirroring the ``non_leader`` predicate).

    Under the ``"spare_then_damage"`` disposition — or with ``include_leaders``,
    for a card that simply says "a unit they control" (Governor's Shuttle LAW_99) —
    the choice carries no such narrowing (Time of Crisis LOF_177), so a deployed
    leader is a legal — and often the obvious — pick."""
    from swu.cards.models import Leader
    ps = state.player_by_id(player_id)
    if ctx.get("disposition") == "spare_then_damage" or ctx.get("include_leaders"):
        return [u.instance_id for u in ps.ground_arena + ps.space_arena]
    return [u.instance_id for u in ps.ground_arena + ps.space_arena
            if not isinstance(u.card_def, Leader)]


def push_each_player_defeats(
    s: GameState, source_ci: CardInstance, *, only_opponent: bool = False,
    disposition: str = "defeat", damage_amount: int = 0,
    include_leaders: bool = False,
) -> None:
    """Push an 'each_player_defeats' decision (Merciless Contest TWI_238): each
    player chooses one of their own non-leader units, then those units are
    defeated.  The source's controller chooses first, then the opponent; a player
    with no eligible unit is skipped, and if neither has one the decision is not
    pushed (the event fizzles).

    ``only_opponent`` restricts the choice to the OPPONENT of the source's
    controller ("An opponent chooses a non-leader unit they control.  Defeat that
    unit." — Avenger SOR_40); the controller never picks its own unit.

    ``disposition`` selects the payoff:
      * ``"defeat"`` (default) — defeat every chosen unit.
      * ``"spare_then_damage"`` — the INVERSE: the chosen units are the survivors,
        and ``damage_amount`` is dealt to every OTHER unit in play ("Each player
        chooses a unit they control.  Deal 3 damage to each unit not chosen this
        way" — Time of Crisis LOF_177).  The choice widens to any unit they
        control (a deployed leader included), and a player with no unit is simply
        skipped — all of their (zero) units are unchosen.

      * ``"return_then_defeat_all"`` — each player's chosen unit is RETURNED to its
        owner's hand, and then every non-leader unit still in play is defeated
        ("Each player may return a non-leader unit to its owner's hand.  Then,
        defeat all non-leader units." — Rhydonium Detonation LAW_96).
        OPTIMAL-PLAY COLLAPSE: the printed "may" is dropped, because the board is
        wiped immediately after — returning a unit that is about to be defeated is
        never worse than leaving it (the same card leaves play either way, but to
        hand rather than to the discard).  If NEITHER player has an eligible unit
        the decision is not pushed, which is also correct: the only units the wipe
        could defeat are exactly the ones that were eligible to be chosen.

    ``include_leaders`` widens the ``"defeat"`` choice the same way, for a card
    printed as plain "a unit they control" with no non-leader clause (Governor's
    Shuttle LAW_99)."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    order = [opponent_id] if only_opponent else [controller_id, opponent_id]
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "order": order,
        "idx": 0,
        "chosen_ids": [],
        "disposition": disposition,
        "damage_amount": int(damage_amount),
        "include_leaders": bool(include_leaders),
    }
    while ctx["idx"] < len(order) and not _each_player_defeat_targets(s, ctx, order[ctx["idx"]]):
        ctx["idx"] += 1
    if ctx["idx"] >= len(order):
        return  # neither player has an eligible unit → fizzle
    deciding = order[ctx["idx"]]
    dec = PendingDecision(
        deciding_player_id=deciding,
        kind="each_player_defeats",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(deciding)
    s.event_log.append(DecisionPushed(
        deciding_player_id=deciding,
        kind="each_player_defeats",
    ))


def _resolve_each_player_defeats(s: GameState, top) -> GameState:
    """Pop the decision, then act on the chosen units (the "pop, then act" gotcha —
    a defeat fires WhenDefeated triggers onto a clean stack)."""
    ctx = top.context
    chosen = list(ctx.get("chosen_ids", []))
    s.pending_decisions.pop()
    if ctx.get("disposition") == "spare_then_damage":
        amount = int(ctx.get("damage_amount", 0))
        spared = set(chosen)
        victims = [u.instance_id for p in s.players
                   for u in p.ground_arena + p.space_arena
                   if u.instance_id not in spared]
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="each_player_defeats",
            choice=f"spared {chosen}, dealt {amount} to {len(victims)} unit(s)",
        ))
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        for tid in victims:
            _apply_deal_damage(s, tid, amount, source_name=source_name)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    if ctx.get("disposition") == "return_then_defeat_all":
        # Rhydonium Detonation LAW_96: the picks are RESCUED to their owners' hands,
        # then everything else non-leader is wiped.  Both halves run after the pop
        # (the "pop, then act" rule) — the returns first, so a rescued unit is out of
        # the arena before the wipe reads it, which is the printed order.
        from swu.abilities.resolver import _apply_return_to_hand, _apply_defeat_unit
        from swu.cards.models import Leader
        for tid in chosen:
            if s.find_instance(tid) is not None:
                _apply_return_to_hand(s, tid)
        victims = [u.instance_id for p in s.players
                   for u in p.ground_arena + p.space_arena
                   if not isinstance(u.card_def, Leader)]
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="each_player_defeats",
            choice=f"returned {chosen}, defeated {len(victims)} unit(s)",
        ))
        for tid in victims:
            if s.find_instance(tid) is not None:
                _apply_defeat_unit(s, tid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="each_player_defeats",
        choice=f"defeat {chosen}",
    ))
    from swu.abilities.resolver import _apply_defeat_unit
    for tid in chosen:
        _apply_defeat_unit(s, tid)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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


# ── Opponent chooses one of their own non-leader units to be captured, else the
#    source readies (Grand Admiral Thrawn SEC_193 WhenPlayed) ──────────────────

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

def _choose_units_sacrifice_rest_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible instance ids to spare: the controller's arena units matching the
    stored trait/predicate filter, minus those already chosen.  Scans only the
    controller's own arenas (so "friendly" is intrinsic and a source event sitting
    in discard is a non-issue — the select_token fallback pattern)."""
    from swu.abilities.resolver import _spec_matches_ci
    from swu.abilities.registry import TargetSpec
    spec = TargetSpec(
        controller="any", kind="unit",
        traits=tuple(ctx.get("traits", []) or ()),
        predicates=tuple(ctx.get("predicates", []) or ()),
    )
    ps = state.player_by_id(ctx["controller_id"])
    chosen = set(ctx.get("chosen", []))
    return [ci.instance_id
            for ci in ps.ground_arena + ps.space_arena
            if ci.instance_id not in chosen
            and _spec_matches_ci(spec, ci, ci, state, {})]


def push_choose_units_sacrifice_rest(
    s: GameState, source_ci: CardInstance, *,
    required_count: int,
    traits: Optional[list[str]] = None,
    predicates: Optional[list[str]] = None,
    tokens: Optional[list] = None,
) -> None:
    """Push a 'choose_units_sacrifice_rest' decision (Always Two LOF_42): the
    controller chooses exactly ``required_count`` of their own units matching the
    trait/predicate filter; on completion each chosen unit receives ``tokens``
    (a list of ``[token_name, count]``) and every OTHER friendly arena unit is
    defeated.  Pushed only when ≥ ``required_count`` units are eligible (else the
    "If you do" fails and nothing happens)."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "required_count": int(required_count),
        "traits": list(traits or []),
        "predicates": list(predicates or []),
        "tokens": [list(t) for t in (tokens or [])],
        "chosen": [],
    }
    if len(_choose_units_sacrifice_rest_targets(s, ctx)) < int(required_count):
        return  # too few eligible units → fizzle (no defeats)
    controller_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="choose_units_sacrifice_rest",
        context=ctx,
        after_resolve_player_index=1 - controller_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = controller_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="choose_units_sacrifice_rest",
    ))


@dataclass
class ChooseUnitToSpare(Action):
    """Choose one eligible friendly unit to spare (Always Two LOF_42).  Keeps
    selecting until ``required_count`` are chosen, then resolves (buff the chosen,
    defeat all other friendly units)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "choose_units_sacrifice_rest"):
            raise IllegalActionError("No choose-units-sacrifice-rest decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _choose_units_sacrifice_rest_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible unit to spare")
        ctx["chosen"].append(self.target_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="choose_units_sacrifice_rest",
            choice=f"spare {self.target_id}",
        ))
        if len(ctx["chosen"]) >= int(ctx["required_count"]):
            return _resolve_choose_units_sacrifice_rest(s, top)
        return s

    def describe(self) -> str:
        return f"Spare {self.target_id}"


def _resolve_choose_units_sacrifice_rest(s: GameState, top) -> GameState:
    """Pop, give each chosen unit its tokens, then defeat every OTHER friendly
    arena unit (the "pop, then defeat" gotcha — WhenDefeated lands on a clean
    stack)."""
    from swu.abilities.resolver import _apply_defeat_unit
    ctx = top.context
    chosen = list(ctx.get("chosen", []))
    chosen_set = set(chosen)
    tokens = ctx.get("tokens", [])
    controller_id = ctx["controller_id"]
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="choose_units_sacrifice_rest",
        choice=f"spared {chosen}",
    ))
    # Buff the chosen units.
    for tid in chosen:
        result = s.find_instance(tid)
        if result is None:
            continue
        owner_ps, ci = result
        for token_name, count in tokens:
            for _ in range(int(count)):
                attach_token(s, owner_ps, ci, token_name)
    # Defeat all OTHER friendly units (snapshot first — defeats mutate arenas).
    ctrl = s.player_by_id(controller_id)
    victims = [u.instance_id for u in ctrl.ground_arena + ctrl.space_arena
               if u.instance_id not in chosen_set]
    for tid in victims:
        _apply_defeat_unit(s, tid)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Unique Rule: keep one of the duplicate copies, defeat the rest
#    (state-based, pushed by _resolve_unique_duplicates) ───────────────────────

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

@dataclass
class SelectHandCardToBottom(Action):
    """Put the chosen hand card on the bottom of your deck (Private Manufacturing
    TWI_257).  Auto-pops the decision once the required number have been placed."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_hand"):
            raise IllegalActionError("No bottom_from_hand decision pending")
        ctx = state.pending_decisions[-1].context
        ps0 = state.player_by_id(ctx["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DECK
        card.face_down = True
        ps.deck.append(card)  # the bottom of the deck
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_hand",
            choice=f"bottomed {card.card_def.display_name}",
        ))
        # Done once we've placed the required number (or the hand is empty).
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            s.pending_decisions.pop()
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of your deck"


@dataclass
class SelectHandCardToTop(Action):
    """Put the chosen hand card on the TOP of your deck — the other half of the
    "on the top or bottom of your deck" choice (Yoda TWI_4).  Offered only when the
    decision was pushed with ``allow_top=True``; otherwise identical to
    ``SelectHandCardToBottom`` (same decision kind, same placement accounting)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_hand"):
            raise IllegalActionError("No bottom_from_hand decision pending")
        ctx0 = state.pending_decisions[-1].context
        if not ctx0.get("allow_top"):
            raise IllegalActionError("This decision cannot place cards on top")
        ps0 = state.player_by_id(ctx0["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DECK
        card.face_down = True
        ps.deck.insert(0, card)  # the top of the deck
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_hand",
            choice=f"put {card.card_def.display_name} on top",
        ))
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            s.pending_decisions.pop()
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the top of your deck"


def push_bottom_from_hand(s: GameState, source_ci: CardInstance, *, count: int,
                          allow_top: bool = False,
                          top_only: bool = False) -> None:
    """Push a 'bottom_from_hand' decision (Private Manufacturing TWI_257): "Put
    ``count`` cards from your hand on the bottom of your deck in any order."

    Mandatory-if-able: the controller must bottom exactly ``min(count, hand size)``
    cards, picked one at a time (the pick order == bottom-placement order).  Pushed
    only when the controller holds ≥1 card and ``count`` ≥ 1; otherwise it fizzles
    cleanly with no prompt.

    ``allow_top`` additionally offers a ``SelectHandCardToTop`` per hand card, for
    "put a card from your hand on the top **or bottom** of your deck" (Yoda TWI_4) —
    the same decision, one more placement option per card.  ``top_only`` is its
    exclusive form: ONLY the top placement is offered, so "put a card from your hand
    on the top of your deck **and another card on the bottom**" (Kreia's Whispers
    SEC_232) is two pushes of this one decision rather than a new kind."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    cap = min(int(count), len(ps.hand))
    if cap <= 0:
        return  # nothing to bottom — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="bottom_from_hand",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "count": cap,
            "placed": 0,
            "allow_top": bool(allow_top or top_only),
            "top_only": bool(top_only),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="bottom_from_hand",
    ))


@dataclass
class SelectHandCardToResource(Action):
    """Resource the chosen hand card, READY (Sundari Palace TS26_12: "you may
    resource a card from your hand and ready it").

    The ordinary ``ResourceCard`` action enters a resource face-down and ready, but
    it is the *once-per-turn* regroup/setup move; this is the same placement reached
    from inside an ability, and — unlike Smuggle — the card is NOT replaced from the
    deck, so the row really grows.  Auto-pops the decision once ``count`` cards have
    been resourced or the hand runs out."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_hand"):
            raise IllegalActionError("No resource_from_hand decision pending")
        ctx0 = state.pending_decisions[-1].context
        ps0 = state.player_by_id(ctx0["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.RESOURCES
        card.face_down = True
        card.exhausted = False
        ps.resources.append(card)
        s.event_log.append(CardResourced(
            player_id=ps.player_id,
            instance_id=card.instance_id,
            card_name=card.card_def.display_name,
        ))
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="resource_from_hand",
            choice=f"resourced {card.card_def.display_name}",
        ))
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            _resolve_resource_from_hand(s)
        return s

    def describe(self) -> str:
        return f"Resource {self.instance_id} from your hand (it enters ready)"


@dataclass
class FinishResourceFromHand(Action):
    """Stop resourcing — the "up to"/"you may" half of the resource_from_hand
    decision.  Always legal while the decision is open (including at zero, which is
    the printed "you MAY resource a card ... for each friendly leader unit")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_hand"):
            raise IllegalActionError("No resource_from_hand decision pending")
        s = copy.deepcopy(state)
        _resolve_resource_from_hand(s)
        return s

    def describe(self) -> str:
        return "Stop resourcing cards from your hand"


def _resolve_resource_from_hand(s: GameState) -> None:
    """Pop the decision and settle its rider.  ``then_defeat_resources_at_regroup``
    schedules ONE resource defeat per card actually resourced ("If you do, defeat
    that many friendly resources at the start of the regroup phase" — TS26_12), so
    resourcing nothing schedules nothing."""
    top = s.pending_decisions.pop()
    ctx = top.context
    placed = int(ctx.get("placed", 0))
    if placed and ctx.get("then_defeat_resources_at_regroup"):
        pid = ctx["controller_id"]
        led = s.game_memory.defeat_resources_at_regroup
        led[pid] = int(led.get(pid, 0)) + placed
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index


def push_resource_from_hand(
    s: GameState, source_ci: CardInstance, *, count: int,
    then_defeat_resources_at_regroup: bool = False,
) -> None:
    """Push a 'resource_from_hand' decision: "You may resource up to ``count`` cards
    from your hand, each entering READY" (Sundari Palace TS26_12, whose count is the
    controller's friendly leader units).

    Always "up to" — ``FinishResourceFromHand`` is offered from the start, since the
    printed clause is a per-leader "you may" and ramping is a real cost (the card you
    give up, plus the scheduled resource defeat).  Fizzles cleanly with an empty hand
    or a non-positive count."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    cap = min(int(count), len(ps.hand))
    if cap <= 0:
        return  # nothing to resource — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="resource_from_hand",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "count": cap,
            "placed": 0,
            "then_defeat_resources_at_regroup": bool(
                then_defeat_resources_at_regroup),
        },
        # Using the ability is an action, so the seat passes once it settles (the
        # bottom_from_hand convention).
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="resource_from_hand",
    ))


def _resource_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top resource_from_hand decision — one per hand card,
    plus the always-offered finish (never empty)."""
    ps = state.player_by_id(top.context["controller_id"])
    return ([SelectHandCardToResource(ci.instance_id) for ci in ps.hand]
            + [FinishResourceFromHand()])


def _bottom_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top bottom_from_hand decision (never empty — the
    decision is only pushed with ≥1 hand card and the cost is mandatory, so a
    card is always available to place).  With ``allow_top`` each card is offered
    twice: bottom or top (Yoda TWI_4)."""
    ps = state.player_by_id(top.context["controller_id"])
    if top.context.get("top_only"):
        # The exclusive top placement (Kreia's Whispers SEC_232) — no bottom option.
        return [SelectHandCardToTop(ci.instance_id) for ci in ps.hand]
    acts: list["Action"] = [SelectHandCardToBottom(ci.instance_id) for ci in ps.hand]
    if top.context.get("allow_top"):
        acts += [SelectHandCardToTop(ci.instance_id) for ci in ps.hand]
    return acts


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


def _apply_defeat_unit_by_id(s: GameState, instance_id: str) -> None:
    """Defeat an in-play unit by id via the resolver's shared defeat path."""
    from swu.abilities.resolver import _apply_defeat_unit
    _apply_defeat_unit(s, instance_id)


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

def _upgrade_move_destinations(
    state: GameState, upgrade_ci: CardInstance, host_id: str, host_controller_id: str,
    dest_traits: "tuple[str, ...] | list[str]" = (),
    dest_controller_id: Optional[str] = None,
) -> list[str]:
    """Legal destination unit ids for relocating ``upgrade_ci``: units the upgrade
    may legally attach to (its "Attach to …" restriction), controlled by the same
    player as its current host, excluding the current host itself.

    ``dest_traits`` narrows the destinations to units carrying every named trait
    ("another eligible friendly **Vehicle** unit", U-Wing Lander JTL_70).

    ``dest_controller_id`` REPLACES the same-controller-as-the-current-host rule
    with a fixed controller — which is how "take control of an upgrade on a unit
    and attach it to a different eligible unit" is spelled (Hondo Ohnaka JTL_56):
    control follows the host, so landing the upgrade on one of the ability
    controller's units IS taking control of it, and the source may be an enemy
    unit's upgrade."""
    from swu.engine.traits import has_trait
    want_controller = dest_controller_id or host_controller_id
    out: list[str] = []
    for u in _eligible_upgrade_targets(state, upgrade_ci):
        if u.instance_id == host_id:
            continue
        located = state.find_instance(u.instance_id)
        if located is None:
            continue
        ps, _ = located
        if ps.player_id != want_controller:
            continue
        if any(not has_trait(state, u, t) for t in (dest_traits or ())):
            continue
        out.append(u.instance_id)
    return out


def _movable_upgrades(state: GameState,
                      filters: Optional[dict] = None) -> dict[str, dict]:
    """Map each movable in-play upgrade id → {host_id, controller_id, dests}.

    An upgrade is movable when it is a non-token upgrade attached to a unit that
    has at least one *other* legal host controlled by the same player.

    ``filters`` (carried in the decision's context so every re-derivation agrees)
    narrows the board-wide default for a card that only moves its OWN load
    (U-Wing Lander JTL_70, "an upgrade on **this** unit … to another eligible
    friendly **Vehicle** unit"):
      * ``from_host_id`` — only upgrades attached to that one host;
      * ``dest_traits``  — destinations must carry these traits;
      * ``include_tokens`` — admit Shield/Experience TOKEN upgrades, which the
        engine-wide ``kind="upgrade"`` convention otherwise excludes (JTL_70
        loads itself with 3 Experience tokens precisely to ferry them onward);
      * ``dest_controller_id`` — every destination must be controlled by this
        player rather than by the upgrade's current host's controller, i.e. the
        relocation TAKES CONTROL of the upgrade (Hondo Ohnaka JTL_56);
      * ``exclude_upgrade_traits`` — skip upgrades carrying any of these traits
        ("a **non-Pilot** upgrade", JTL_56).
      * ``tokens_only`` — admit ONLY Shield/Experience token upgrades ("a **token**
        upgrade on a unit", Shuttle ST-149 JTL_242).  Implies ``include_tokens``;
        the complement of the engine-wide non-token default.
      * ``only_upgrade_id`` — only this one upgrade may move ("The attacking player
        takes control of **this upgrade**", Death Star Plans JTL_260), which
        ``from_host_id`` cannot express when the host carries several upgrades.
      * ``host_controller_id`` — the upgrade's CURRENT host must be controlled by
        this player ("a friendly upgrade on a friendly unit", Jocasta Nu LOF_248).
        The board-wide default admits enemy hosts too; destinations are already
        pinned to the host's own controller, so this makes both ends friendly.
    """
    from swu.cards.models import TokenUpgrade
    f = filters or {}
    from_host_id = f.get("from_host_id")
    host_controller_id = f.get("host_controller_id")
    dest_traits = tuple(f.get("dest_traits") or ())
    tokens_only = bool(f.get("tokens_only"))
    include_tokens = bool(f.get("include_tokens")) or tokens_only
    dest_controller_id = f.get("dest_controller_id")
    exclude_upgrade_traits = tuple(f.get("exclude_upgrade_traits") or ())
    only_upgrade_id = f.get("only_upgrade_id")
    out: dict[str, dict] = {}
    for ps in state.players:
        if host_controller_id is not None and ps.player_id != host_controller_id:
            continue
        for host in ps.ground_arena + ps.space_arena:
            if from_host_id is not None and host.instance_id != from_host_id:
                continue
            for upg in host.attached_upgrades:
                if only_upgrade_id is not None and upg.instance_id != only_upgrade_id:
                    continue
                is_token = isinstance(upg.card_def, TokenUpgrade)
                if is_token and not include_tokens:
                    continue
                if tokens_only and not is_token:
                    continue
                if any(t in (getattr(upg.card_def, "traits", None) or ())
                       for t in exclude_upgrade_traits):
                    continue
                dests = _upgrade_move_destinations(
                    state, upg, host.instance_id, ps.player_id, dest_traits,
                    dest_controller_id)
                if dests:
                    out[upg.instance_id] = {
                        "host_id": host.instance_id,
                        "controller_id": ps.player_id,
                        "dests": dests,
                    }
    return out


@dataclass
class MoveUpgradeSelect(Action):
    """Choose an in-play upgrade to relocate (Survivors' Gauntlet SHD_64).
    Advances the 'move_upgrade' decision to its destination stage."""
    upgrade_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "pick_upgrade":
            raise IllegalActionError("Move-upgrade decision is past the pick stage")
        movable = _movable_upgrades(s, ctx.get("filters"))
        if self.upgrade_id not in movable:
            raise IllegalActionError(f"{self.upgrade_id} is not a movable upgrade")
        ctx["stage"] = "pick_dest"
        ctx["chosen_upgrade"] = self.upgrade_id
        return s

    def describe(self) -> str:
        return f"Move upgrade {self.upgrade_id}"


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


@dataclass
class DeclineMoveUpgrade(Action):
    """Decline to move an upgrade — the ability does nothing (Survivors' Gauntlet
    SHD_64 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "pick_upgrade":
            raise IllegalActionError("Move-upgrade decision is past the pick stage")
        if top.context.get("mandatory"):
            raise IllegalActionError("This move-upgrade decision cannot be declined")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="move_upgrade",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to move an upgrade"


@dataclass
class MoveUpgradeTo(Action):
    """Choose the destination unit and relocate the chosen upgrade, resolving the
    'move_upgrade' decision (Survivors' Gauntlet SHD_64)."""
    dest_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "pick_dest":
            raise IllegalActionError("Move-upgrade decision is not at the destination stage")
        upgrade_id = ctx["chosen_upgrade"]
        movable = _movable_upgrades(s, ctx.get("filters"))
        info = movable.get(upgrade_id)
        if info is None or self.dest_id not in info["dests"]:
            raise IllegalActionError(f"{self.dest_id} is not a legal destination")
        _relocate_upgrade(s, upgrade_id, info["host_id"], self.dest_id)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="move_upgrade",
            choice=f"moved {upgrade_id} to {self.dest_id}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Attach the upgrade to {self.dest_id}"


def _relocate_upgrade(s: GameState, upgrade_id: str, host_id: str, dest_id: str) -> None:
    """Detach ``upgrade_id`` from ``host_id`` and attach it to ``dest_id``.

    A pure relocation: no WhenPlayed re-fire (the upgrade was already played).
    The upgrade's zone tag is updated to the destination's arena so upgrade-zone
    invariants hold."""
    host = s.find_instance(host_id)
    dest = s.find_instance(dest_id)
    if host is None or dest is None:
        raise IllegalActionError("Move-upgrade host or destination not found")
    _, host_ci = host
    _, dest_ci = dest
    upg = next((u for u in host_ci.attached_upgrades
                if u.instance_id == upgrade_id), None)
    if upg is None:
        raise IllegalActionError(f"{upgrade_id} no longer attached to {host_id}")
    host_ci.attached_upgrades.remove(upg)
    upg.zone = dest_ci.zone
    upg.face_down = False
    dest_ci.attached_upgrades.append(upg)
    note_upgrade_attached(s, dest_ci)      # Sabine Wren ASH_208


def push_move_upgrade(s: GameState, source_ci: CardInstance, *,
                      from_host_id: Optional[str] = None,
                      dest_traits: Optional[list[str]] = None,
                      include_tokens: bool = False,
                      dest_controller_id: Optional[str] = None,
                      exclude_upgrade_traits: Optional[list[str]] = None,
                      tokens_only: bool = False,
                      only_upgrade_id: Optional[str] = None,
                      host_controller_id: Optional[str] = None,
                      decider_id: Optional[str] = None,
                      mandatory: bool = False) -> None:
    """Push a 'move_upgrade' decision: "You may attach an upgrade on a unit to
    another eligible unit controlled by the same player" (Survivors' Gauntlet
    SHD_64).

    Only pushed when at least one in-play upgrade can actually be relocated to a
    different same-controller legal host — so the optional ability is never
    offered when it could do nothing.

    The optional narrowings (``from_host_id`` / ``dest_traits`` /
    ``include_tokens`` / ``dest_controller_id`` / ``exclude_upgrade_traits``, all
    documented on ``_movable_upgrades``) are stored in the decision context so the
    action enumeration and both apply-guards re-derive exactly the same candidate
    set (U-Wing Lander JTL_70, Hondo Ohnaka JTL_56).

    ``decider_id`` hands the choice to a player other than the source's controller
    ("The ATTACKING PLAYER takes control of this upgrade …", Death Star Plans
    JTL_260); ``mandatory`` drops the decline, for a relocation that is not a
    "you may"."""
    filters = {
        "from_host_id": from_host_id,
        "dest_traits": list(dest_traits or []),
        "include_tokens": bool(include_tokens),
        "dest_controller_id": dest_controller_id,
        "exclude_upgrade_traits": list(exclude_upgrade_traits or []),
        "tokens_only": bool(tokens_only),
        "only_upgrade_id": only_upgrade_id,
        "host_controller_id": host_controller_id,
    }
    if not _movable_upgrades(s, filters):
        return
    controller_id = decider_id or source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="move_upgrade",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "pick_upgrade",
            "chosen_upgrade": None,
            "mandatory": bool(mandatory),
            "filters": filters,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="move_upgrade",
    ))


def _move_upgrade_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top move_upgrade decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "pick_upgrade":
        acts: list[Action] = [
            MoveUpgradeSelect(uid)
            for uid in sorted(_movable_upgrades(state, ctx.get("filters")))
        ]
        if not ctx.get("mandatory"):
            acts.append(DeclineMoveUpgrade())  # the "you may" (SHD_64)
        return acts
    # stage "pick_dest"
    upgrade_id = ctx["chosen_upgrade"]
    info = _movable_upgrades(state, ctx.get("filters")).get(upgrade_id)
    dests = info["dests"] if info else []
    return [MoveUpgradeTo(d) for d in dests]


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

def _stealable_upgrades(state: GameState, source_ci: CardInstance) -> dict[str, dict]:
    """Map each steal-eligible upgrade id → {host_id, cost}.

    An upgrade is steal-eligible for Pre Vizsla when it is a real (non-token)
    Upgrade attached to a NON-Vehicle unit OTHER than the source, and the source's
    controller can pay its printed cost from ready resources."""
    from swu.cards.models import Upgrade, TokenUpgrade
    from swu.engine.traits import has_trait
    located = state.find_instance(source_ci.instance_id)
    if located is None:
        return {}
    controller_ps, _ = located
    out: dict[str, dict] = {}
    for ps in state.players:
        for host in ps.ground_arena + ps.space_arena:
            if host.instance_id == source_ci.instance_id:
                continue  # "another" unit
            if has_trait(state, host, "Vehicle"):
                continue  # "non-Vehicle unit"
            for upg in host.attached_upgrades:
                if not isinstance(upg.card_def, Upgrade) or isinstance(
                        upg.card_def, TokenUpgrade):
                    continue
                cost = int(getattr(upg.card_def, "cost", 0) or 0)
                if controller_ps.available_resources < cost:
                    continue
                out[upg.instance_id] = {"host_id": host.instance_id, "cost": cost}
    return out


@dataclass
class StealUpgrade(Action):
    """Pay an upgrade's cost and take control of it, attaching it to the source
    (Pre Vizsla SHD_142) — or defeating it if it can't attach."""
    upgrade_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_and_steal_upgrade"):
            raise IllegalActionError("No pay_and_steal_upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        source_id = top.context["source_id"]
        located = s.find_instance(source_id)
        stealable = _stealable_upgrades(s, located[1]) if located is not None else {}
        info = stealable.get(self.upgrade_id)
        if info is None:
            raise IllegalActionError(f"{self.upgrade_id} is not a stealable upgrade")
        source_ci = located[1]
        controller_ps, _ = located
        # Pay the printed cost (ready resources — the Pre Vizsla payment is
        # resource-only, matching the credit-spend SCOPE exclusions).
        _exhaust_resources(controller_ps, info["cost"])
        upg = next((u for u in s.find_instance(info["host_id"])[1].attached_upgrades
                    if u.instance_id == self.upgrade_id), None)
        spec = _upgrade_target_spec(upg.card_def) if upg is not None else None
        can_attach = False
        if upg is not None:
            if spec is None:
                can_attach = True
            else:
                from swu.abilities.resolver import _spec_matches_ci
                can_attach = _spec_matches_ci(spec, source_ci, upg, s, {})
        if can_attach:
            _relocate_upgrade(s, self.upgrade_id, info["host_id"], source_id)
            choice = f"took control of {self.upgrade_id}"
        else:
            from swu.abilities.resolver import _apply_defeat_unit
            _apply_defeat_unit(s, self.upgrade_id)
            choice = f"defeated {self.upgrade_id} (can't attach)"
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pay_and_steal_upgrade",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Pay for and take control of upgrade {self.upgrade_id}"


@dataclass
class DeclineStealUpgrade(Action):
    """Decline the optional pay-and-steal-an-upgrade (Pre Vizsla SHD_142 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_and_steal_upgrade"):
            raise IllegalActionError("No pay_and_steal_upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pay_and_steal_upgrade",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to steal an upgrade"


def push_pay_and_steal_upgrade(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'pay_and_steal_upgrade' decision (Pre Vizsla SHD_142).

    Only pushed when at least one affordable steal-eligible upgrade exists, so the
    optional ability is never offered when it could do nothing."""
    if not _stealable_upgrades(s, source_ci):
        return
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=controller_id,
        kind="pay_and_steal_upgrade",
        context={"source_id": source_ci.instance_id},
        after_resolve_player_index=1 - owner_idx,
    ))
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pay_and_steal_upgrade",
    ))


def _pay_and_steal_upgrade_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top pay_and_steal_upgrade decision (never empty)."""
    located = state.find_instance(top.context["source_id"])
    stealable = _stealable_upgrades(state, located[1]) if located is not None else {}
    acts: list[Action] = [StealUpgrade(uid) for uid in sorted(stealable)]
    acts.append(DeclineStealUpgrade())
    return acts


# ── Attach an in-play unit as a Pilot upgrade (Poe Dameron JTLP_6) ────────────
#
# The unit-becomes-upgrade relocation primitive — the sibling of `_attach_pilot`
# (which attaches a HAND unit as a pilot) and `_relocate_upgrade` (move_upgrade,
# which relocates an in-play upgrade).  Here an IN-PLAY unit's CardInstance is
# relocated from its arena into a friendly Vehicle's `attached_upgrades` as a
# Pilot.  It is a relocation, NOT a play, so no UpgradePlayed re-fires.

def _pilot_self_attach_hosts(s: GameState, source_ci: CardInstance,
                             hosts: str = "friendly") -> list[str]:
    """Instance ids of the Vehicle units that ``source_ci`` may attach itself onto
    as a Pilot: Vehicles with no Pilot on them (Poe JTLP_6 "a friendly Vehicle unit
    without a Pilot on it"), excluding the source itself.

    ``hosts="enemy"`` looks at the OPPONENT's arenas instead — "attach this unit as
    an upgrade to an ENEMY Vehicle unit without a Pilot on it" (Sidon Ithano
    JTL_213), where the pilot ends up buffing a ship it does not control."""
    from swu.engine.traits import has_trait
    idx = s.player_index(source_ci.owner_id)
    ps = s.players[1 - idx] if hosts == "enemy" else s.players[idx]
    return [ci.instance_id for ci in ps.ground_arena + ps.space_arena
            if ci.instance_id != source_ci.instance_id
            and has_trait(s, ci, "Vehicle")
            and not _vehicle_has_pilot(ci)]


def _attach_unit_as_pilot(s: GameState, unit_id: str, vehicle_id: str) -> None:
    """Relocate the in-play unit ``unit_id`` into ``vehicle_id``'s attached
    upgrades as a Pilot.  A pure relocation (no WhenPlayed re-fire) mirroring
    `_relocate_upgrade`; the unit's `upgrade_power`/`upgrade_hp` then buff the
    host via the existing compute_power/hp reads, and on the host's defeat
    `_defeat_unit` detaches the unit (a non-token Unit) to its owner's discard
    like any pilot."""
    from swu.cards.models import TokenUpgrade
    ures = s.find_instance(unit_id)
    vres = s.find_instance(vehicle_id)
    if ures is None or vres is None:
        return
    unit_ps, unit_ci = ures
    _, vehicle_ci = vres
    # Remove the unit from whichever arena holds it (no-op if it already left).
    removed = False
    for arena in (unit_ps.ground_arena, unit_ps.space_arena):
        if unit_ci in arena:
            arena.remove(unit_ci)
            removed = True
            break
    if not removed:
        return
    # A unit becoming an upgrade sheds its own attachments (tokens vanish, real
    # upgrades → owner's discard), mirroring _apply_capture / _defeat_unit.  A
    # freshly-played Poe has none, but this keeps the relocation clean in general.
    for upgrade in list(unit_ci.attached_upgrades):
        if isinstance(upgrade.card_def, TokenUpgrade):
            continue
        upgrade_owner = s.player_by_id(upgrade.owner_id)
        upgrade.zone = Zone.DISCARD
        upgrade_owner.discard.append(upgrade)
    unit_ci.attached_upgrades.clear()
    # Modifiers that targeted it as a unit no longer apply.
    s.modifiers = [m for m in s.modifiers if m.target_instance_id != unit_ci.instance_id]
    unit_ci.damage = 0
    unit_ci.exhausted = False
    unit_ci.face_down = False
    unit_ci.deployed = False
    unit_ci.zone = vehicle_ci.zone
    vehicle_ci.attached_upgrades.append(unit_ci)
    note_upgrade_attached(s, vehicle_ci)      # Sabine Wren ASH_208
    s.event_log.append(UpgradePlayed(
        player_id=unit_ci.owner_id,
        instance_id=unit_ci.instance_id,
        card_name=unit_ci.card_def.display_name,
        attached_to_instance_id=vehicle_id,
    ))


def push_attach_unit_as_pilot(s: GameState, source_ci: CardInstance, *,
                              hosts: str = "friendly") -> None:
    """Push a 'pilot_self_attach' decision: "You may attach this unit as an
    upgrade to a friendly Vehicle unit without a Pilot on it" (Poe JTLP_6).

    ``hosts="enemy"`` offers the OPPONENT's pilotless Vehicles instead (Sidon
    Ithano JTL_213); the choice is carried in the decision context so the
    enumeration and the apply-guard re-derive the same host set.

    Only pushed when at least one eligible Vehicle host exists — so the optional
    ability auto-skips (does nothing) when it could not attach anywhere."""
    if not _pilot_self_attach_hosts(s, source_ci, hosts):
        return
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="pilot_self_attach",
        context={"source_id": source_ci.instance_id, "controller_id": controller_id,
                 "hosts": hosts},
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pilot_self_attach",
    ))


@dataclass
class AttachSelfAsPilot(Action):
    """Attach the source unit to a chosen friendly Vehicle as a Pilot, resolving
    the 'pilot_self_attach' decision (Poe JTLP_6)."""
    vehicle_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pilot_self_attach"):
            raise IllegalActionError("No pilot-self-attach decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        source_id = top.context["source_id"]
        source = s.find_instance(source_id)
        if source is None or self.vehicle_id not in _pilot_self_attach_hosts(
                s, source[1], top.context.get("hosts", "friendly")):
            raise IllegalActionError(f"{self.vehicle_id} is not a legal pilot host")
        _attach_unit_as_pilot(s, source_id, self.vehicle_id)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pilot_self_attach",
            choice=f"attached {source_id} to {self.vehicle_id}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Attach as a Pilot onto {self.vehicle_id}"


@dataclass
class DeclineAttachSelfAsPilot(Action):
    """Decline to attach the unit as a Pilot — it stays a unit (Poe JTLP_6 "you
    may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pilot_self_attach"):
            raise IllegalActionError("No pilot-self-attach decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pilot_self_attach",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to attach as a Pilot"


def _pilot_self_attach_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top pilot_self_attach decision (never empty — a
    decline is always offered)."""
    source = state.find_instance(top.context["source_id"])
    hosts = (_pilot_self_attach_hosts(state, source[1],
                                      top.context.get("hosts", "friendly"))
             if source else [])
    acts: list[Action] = [AttachSelfAsPilot(v) for v in sorted(hosts)]
    acts.append(DeclineAttachSelfAsPilot())
    return acts


# ── Play an upgrade from hand for free, choosing a host (Jabba the Hutt ASH_42) ─
#
# The upgrade sibling of the units-only ``push_play_from_hand`` subsystem: "play a
# specific upgrade from your hand for free, choosing a legal host".  A single-stage
# host-selection decision (the ``move_upgrade`` / ``pilot_self_attach`` shape) —
# the upgrade is fixed (the one just returned to hand); the player only picks its
# host, or declines ("you may play it for free").  Reuses ``_eligible_upgrade_targets``
# for legal hosts and ``_attach_upgrade`` for the play itself (which fires
# UpgradePlayed → the upgrade's own WhenPlayed triggers).

def _play_upgrade_source_zones(state: GameState, ctx: dict) -> list[list[CardInstance]]:
    """The zones a ``play_upgrade_from_hand`` decision may play an upgrade out of:
    the controller's hand, plus — with ``ctx['include_discards']`` — EVERY player's
    discard pile ("play an upgrade from your hand or from any player's discard
    pile", A Fine Addition TWI_40).  An upgrade played out of an opponent's discard
    keeps its owner (it returns there when defeated); control follows the host, the
    ``change_control`` convention.

    ``from_discard_only`` narrows the source to the controller's OWN discard pile,
    with the hand dropped entirely — "Play any number of upgrades from your discard
    pile on this unit" (Kylo Ren LOF_1).

    ``from_resources`` narrows it to the controller's own RESOURCE row — "Play an
    upgrade from your resources … (paying its cost)" (The Armorer ASH_1).  The card
    leaves the row when it is played (it is not replaced from the deck, unlike
    Smuggle), which is why the Armorer's own "If you do, resource the top card of
    your deck" rider exists."""
    ps = state.player_by_id(ctx["controller_id"])
    if ctx.get("from_resources"):
        return [ps.resources]
    if ctx.get("from_discard_only"):
        return [ps.discard]
    zones = [ps.hand]
    if ctx.get("include_discards"):
        zones += [p.discard for p in state.players]
    return zones


def _find_playable_upgrade(state: GameState, ctx: dict,
                           upgrade_id: str) -> Optional[CardInstance]:
    """Locate ``upgrade_id`` in any of the decision's legal source zones."""
    for zone in _play_upgrade_source_zones(state, ctx):
        for c in zone:
            if c.instance_id == upgrade_id:
                return c
    return None


def _play_upgrade_hosts_for(state: GameState, ctx: dict,
                            upgrade_ci: CardInstance) -> list[str]:
    """Legal host instance ids for ``upgrade_ci``, per its own "Attach to …"
    restriction, narrowed by ``ctx['host_id']`` when the card pins the host ("…on
    this unit" — Kylo Ren LOF_1).

    ``ctx['host_controller']`` / ``ctx['host_predicates']`` narrow the hosts by the
    ordinary TargetSpec matcher, evaluated with the UPGRADE as the source (so
    "friendly" reads from its owner — the player making the play): "on a unit that
    entered play this phase" / "on a friendly unit" (The Armorer ASH_1)."""
    hosts = [u.instance_id for u in _eligible_upgrade_targets(state, upgrade_ci)]
    pinned = ctx.get("host_id")
    if pinned is not None:
        hosts = [h for h in hosts if h == pinned]
    preds = tuple(ctx.get("host_predicates") or ())
    host_controller = ctx.get("host_controller")
    if preds or host_controller:
        from swu.abilities.registry import TargetSpec
        from swu.abilities.resolver import _spec_matches_ci
        spec = TargetSpec(controller=host_controller or "any", kind="unit",
                          predicates=preds)
        keep = []
        for hid in hosts:
            res = state.find_instance(hid)
            if res is None:
                continue
            if _spec_matches_ci(spec, res[1], upgrade_ci, state, {}):
                keep.append(hid)
        hosts = keep
    return hosts


def _play_upgrade_from_hand_hosts(state: GameState, ctx: dict) -> list[str]:
    """Legal host instance ids for the pending upgrade ``ctx['upgrade_id']`` — the
    units it may be attached to, per its own "Attach to …" restriction.  Empty
    if the upgrade has left its source zone (defensive)."""
    upgrade_ci = _find_playable_upgrade(state, ctx, ctx["upgrade_id"])
    if upgrade_ci is None:
        return []
    return _play_upgrade_hosts_for(state, ctx, upgrade_ci)


def _affordable_hand_upgrades(state: GameState, ctx: dict) -> list[str]:
    """Instance ids of Upgrade cards in the decision's source zones (the
    controller's hand, plus every discard pile when ``include_discards``) that are
    BOTH affordable (given ``ctx['free']`` / ``cost_reduction`` /
    ``ignore_aspect_penalty``) AND have ≥1 legal host — the candidate set for a
    "choose an upgrade to play" decision (Fenn Rau SHD_67, A Fine Addition TWI_40).
    Empty ⇒ the play can do nothing."""
    free = bool(ctx.get("free", True))
    out: list[str] = []
    trait = ctx.get("trait")
    for zone in _play_upgrade_source_zones(state, ctx):
        for c in zone:
            if not isinstance(c.card_def, Upgrade):
                continue
            # "…a Lightsaber upgrade from your hand" (Cin Drallig LOF_150) — the
            # printed-trait narrowing of the candidate set.
            if trait is not None and trait not in (
                    getattr(c.card_def, "traits", None) or ()):
                continue
            # An upgrade taken from an OPPONENT's discard keeps its owner, and the
            # "Attach to a friendly/enemy unit" restriction is evaluated from the
            # owner's perspective — which would invert for the player now playing
            # it.  Rather than mis-attach, such a card is simply not offered from a
            # foreign discard (a documented narrowing; controller-agnostic
            # restrictions — the overwhelming majority — are unaffected).
            if c.owner_id != ctx["controller_id"]:
                spec = _upgrade_target_spec(c.card_def)
                if spec is not None and getattr(spec, "controller", "any") != "any":
                    continue
            if not _play_upgrade_hosts_for(state, ctx, c):
                continue
            if not free and not _play_upgrade_affordable(
                    state, ctx, c, _play_upgrade_cost(state, ctx, c)):
                continue
            out.append(c.instance_id)
    return out


def push_play_upgrade_from_hand(
    s: GameState, source_ci: CardInstance, *, upgrade_id: Optional[str] = None,
    free: bool = True, cost_reduction: int = 0,
    include_discards: bool = False, ignore_aspect_penalty: bool = False,
    from_discard_only: bool = False, host_id: Optional[str] = None,
    repeat: bool = False, trait: Optional[str] = None,
    then_ready_source: bool = False, then_damage_host: int = 0,
    then_defeat_at_regroup: bool = False,
    from_resources: bool = False,
    host_controller: Optional[str] = None,
    host_predicates: Optional[tuple] = None,
    then_resource_top_of_deck: bool = False,
) -> None:
    """Push a 'play_upgrade_from_hand' decision: "You may play [the upgrade
    ``upgrade_id`` / an upgrade of your choice] from your hand [for free / at
    ``cost_reduction`` off], choosing a legal host".

    Two callers: Jabba the Hutt ASH_42 passes a specific ``upgrade_id`` (the
    just-returned upgrade, played for free); Fenn Rau SHD_67 passes
    ``upgrade_id=None`` (the controller CHOOSES an affordable hand upgrade) with
    ``free=False, cost_reduction=2``.

    ``include_discards`` widens the source zones to every player's discard pile and
    ``ignore_aspect_penalty`` waives the played upgrade's whole aspect penalty — "If
    an enemy unit was defeated this phase, play an upgrade from your hand or from any
    player's discard pile, ignoring its aspect penalty" (A Fine Addition TWI_40,
    which pays the cost in full otherwise: ``free=False, cost_reduction=0``).

    Three further knobs serve "Play any number of upgrades from your discard pile on
    this unit (one at a time, paying their costs)" (Kylo Ren LOF_1):
    ``from_discard_only`` drops the hand and reads only the controller's OWN discard;
    ``host_id`` pins every candidate's host to one unit ("on this unit"); and
    ``repeat`` makes each successful play RE-PUSH the loop — re-pushed BEFORE the
    upgrade attaches, so the just-played upgrade's own When Played triggers (pushed
    on top) resolve before the next pick, the faithful "one at a time" LIFO (the
    Endless Legions SHD_109 shape).  The always-offered decline is the "any number",
    including zero.

    Two more serve "When Played: You may play a Lightsaber upgrade from your hand for
    free on this unit.  If you do, ready him" (Cin Drallig LOF_150): ``trait`` narrows
    the candidate upgrades to a printed trait, and ``then_ready_source`` readies the
    SOURCE unit after a successful play ("if you do" — never on a decline).

    ``then_damage_host`` is the same-family "if you do" hook on the other side of the
    attachment: N damage dealt to the HOST the upgrade landed on ("Play an upgrade
    from your hand on a friendly non-Vehicle unit.  It costs 1 resource less.  If you
    do, deal 1 damage to that unit" — Lama Su SEC_3).  Like then_ready_source it runs
    only on a real play, never on the decline.

    ``then_defeat_at_regroup`` stamps the played upgrade with the long-standing
    per-instance ``defeat_at_regroup`` flag, swept in ``_enter_regroup`` — "Play an
    Item upgrade from your discard pile.  It costs 3 resources less.  At the start of
    the next regroup phase, defeat it" (Salvaged Materials LAW_245).  The flag is the
    same delayed-defeat family as the unit version, so a rental upgrade needs no new
    bookkeeping.

    Four knobs serve "Play an upgrade from your resources on a unit that entered play
    this phase (paying its cost).  If you do, resource the top card of your deck"
    (The Armorer ASH_1): ``from_resources`` swaps the source zone for the
    controller's RESOURCE row (the card leaves the row and is NOT replaced — unlike
    Smuggle — and cannot pay for itself, the ``_play_upgrade_affordable`` rule);
    ``host_controller`` / ``host_predicates`` narrow the legal hosts through the
    ordinary TargetSpec matcher; and ``then_resource_top_of_deck`` is the "if you do"
    ramp, run only on a real play (never on the decline).

    Only pushed when there is at least one affordable candidate upgrade with ≥1 legal
    host — so the optional play is never offered when it could do nothing.  The
    decider is the source's controller."""
    controller_id = source_ci.owner_id
    ctx = {
        "trait": trait,
        "from_resources": bool(from_resources),
        "host_controller": host_controller,
        "host_predicates": list(host_predicates or ()),
        "then_resource_top_of_deck": bool(then_resource_top_of_deck),
        "then_ready_source": bool(then_ready_source),
        "then_damage_host": int(then_damage_host),
        "then_defeat_at_regroup": bool(then_defeat_at_regroup),
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "upgrade_id": upgrade_id,
        "free": bool(free),
        "cost_reduction": int(cost_reduction),
        "include_discards": bool(include_discards),
        "ignore_aspect_penalty": bool(ignore_aspect_penalty),
        "from_discard_only": bool(from_discard_only),
        "host_id": host_id,
        "repeat": bool(repeat),
    }
    if upgrade_id is None:
        if not _affordable_hand_upgrades(s, ctx):
            return
    else:
        if not _play_upgrade_from_hand_hosts(s, ctx):
            return
        # A specific-upgrade paid play must also be affordable.
        if not bool(free):
            upg = _find_playable_upgrade(s, ctx, upgrade_id)
            if upg is None:
                return
            if not _play_upgrade_affordable(s, ctx, upg,
                                            _play_upgrade_cost(s, ctx, upg)):
                return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="play_upgrade_from_hand",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="play_upgrade_from_hand",
    ))


@dataclass
class PlayUpgradeFromHand(Action):
    """Play a pending hand upgrade onto a chosen host, resolving the
    'play_upgrade_from_hand' decision.  ``upgrade_id`` is carried on the action
    only in "choose an upgrade" mode (Fenn Rau SHD_67); it is ``None`` for the
    fixed-upgrade caller (Jabba the Hutt ASH_42), which reads the id from the
    decision context."""
    host_id: str
    upgrade_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_upgrade_from_hand"):
            raise IllegalActionError("No play-upgrade-from-hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        upg_id = self.upgrade_id or ctx.get("upgrade_id")
        if upg_id is None:
            raise IllegalActionError("No upgrade chosen")
        ps = s.player_by_id(ctx["controller_id"])
        upgrade_ci = _find_playable_upgrade(s, ctx, upg_id)
        if upgrade_ci is None:
            raise IllegalActionError("Upgrade no longer available to play")
        if self.host_id not in _play_upgrade_hosts_for(s, ctx, upgrade_ci):
            raise IllegalActionError(f"{self.host_id} is not a legal host")
        free = bool(ctx.get("free", True))
        cost = 0 if free else _play_upgrade_cost(s, ctx, upgrade_ci, self.host_id)
        if not free and not _play_upgrade_affordable(s, ctx, upgrade_ci, cost):
            raise IllegalActionError("Cannot afford the upgrade")
        # The upgrade may live in the controller's hand or (include_discards) in
        # ANY player's discard pile — remove it from whichever zone holds it.
        for zone in _play_upgrade_source_zones(s, ctx):
            if upgrade_ci in zone:
                zone.remove(upgrade_ci)
                break
        if cost:
            _pay_play_cost(s, ps, cost)
        # Pop the decision BEFORE attaching, so the upgrade's own WhenPlayed
        # triggers land on a clean stack (the "pop, then act" gotcha).
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_upgrade_from_hand",
            choice=f"played {upg_id} onto {self.host_id}",
        ))
        # "Any number … one at a time" (Kylo Ren LOF_1): re-push the loop BEFORE the
        # attach, so this upgrade's own When Played triggers land on top of it and
        # resolve first (the Endless Legions SHD_109 ordering).
        if ctx.get("repeat"):
            source_result = s.find_instance(ctx["source_id"])
            if source_result is not None:
                push_play_upgrade_from_hand(
                    s, source_result[1],
                    free=bool(ctx.get("free", True)),
                    cost_reduction=int(ctx.get("cost_reduction", 0) or 0),
                    include_discards=bool(ctx.get("include_discards")),
                    ignore_aspect_penalty=bool(ctx.get("ignore_aspect_penalty")),
                    from_discard_only=bool(ctx.get("from_discard_only")),
                    host_id=ctx.get("host_id"),
                    repeat=True,
                    trait=ctx.get("trait"),
                    then_ready_source=bool(ctx.get("then_ready_source")),
                    then_damage_host=int(ctx.get("then_damage_host", 0) or 0),
                    then_defeat_at_regroup=bool(ctx.get("then_defeat_at_regroup")),
                    from_resources=bool(ctx.get("from_resources")),
                    host_controller=ctx.get("host_controller"),
                    host_predicates=tuple(ctx.get("host_predicates") or ()),
                    then_resource_top_of_deck=bool(
                        ctx.get("then_resource_top_of_deck")),
                )
        # "At the start of the next regroup phase, defeat it" (Salvaged Materials
        # LAW_245) — stamped BEFORE the attach so the flag is already on the card
        # when its own When Played resolves.
        if ctx.get("then_defeat_at_regroup"):
            upgrade_ci.defeat_at_regroup = True
        # A card played out of the RESOURCE row (The Armorer ASH_1) may be exhausted
        # there; it is not an exhaustible card once attached, and leaving the flag on
        # would put an exhausted card in a hand if it is ever returned.
        if ctx.get("from_resources"):
            upgrade_ci.exhausted = False
        # _attach_upgrade fires UpgradePlayed + WhenPlayed
        _attach_upgrade(s, ps, upgrade_ci, self.host_id)
        # "If you do, resource the top card of your deck" (The Armorer ASH_1) — the
        # ramp that repays the resource row the play just spent, on a real play only.
        if ctx.get("then_resource_top_of_deck"):
            _resource_top_of_deck(s, ps)
        # "If you do, ready him" (Cin Drallig LOF_150) — only on a play, never on the
        # decline, and after the upgrade has landed.
        # "If you do, deal N damage to that unit" (Lama Su SEC_3) — the host-side
        # "if you do" hook, after the upgrade has landed (so the host's HP already
        # includes it, matching the printed ordering) and only on a real play.
        _thd = int(ctx.get("then_damage_host", 0) or 0)
        if _thd > 0:
            from swu.abilities.resolver import _apply_deal_damage
            src_res = s.find_instance(ctx["source_id"])
            _name = (src_res[1].card_def.display_name
                     if src_res is not None else upgrade_ci.card_def.display_name)
            _apply_deal_damage(s, self.host_id, _thd, _name)
        if ctx.get("then_ready_source"):
            src_res = s.find_instance(ctx["source_id"])
            if src_res is not None and src_res[1].exhausted:
                src_res[1].exhausted = False
                s.event_log.append(UnitReadied(
                    player_id=ps.player_id,
                    instance_id=src_res[1].instance_id,
                    card_name=src_res[1].card_def.display_name,
                ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Play the upgrade onto {self.host_id}"


@dataclass
class DeclinePlayUpgradeFromHand(Action):
    """Decline to play the returned upgrade — it stays in hand (Jabba the Hutt
    ASH_42 "you may play it for free")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_upgrade_from_hand"):
            raise IllegalActionError("No play-upgrade-from-hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_upgrade_from_hand",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to play the upgrade"


def _play_upgrade_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top play_upgrade_from_hand decision (never empty — a
    decline is always offered, as the play is a "you may").

    Fixed-upgrade mode (``ctx['upgrade_id']`` set, Jabba ASH_42): one action per
    legal host.  Choose-upgrade mode (``upgrade_id`` None, Fenn Rau SHD_67): one
    action per (affordable hand upgrade × its legal host) pair, each carrying the
    chosen upgrade id."""
    ctx = top.context
    acts: list[Action] = []
    if ctx.get("upgrade_id") is not None:
        acts += [PlayUpgradeFromHand(h)
                 for h in sorted(_play_upgrade_from_hand_hosts(state, ctx))]
    else:
        for uid in _affordable_hand_upgrades(state, ctx):
            upg = _find_playable_upgrade(state, ctx, uid)
            if upg is None:
                continue
            for host in sorted(_play_upgrade_hosts_for(state, ctx, upg)):
                acts.append(PlayUpgradeFromHand(host, upgrade_id=uid))
    acts.append(DeclinePlayUpgradeFromHand())
    return acts


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


def _resolve_select_damage(s: GameState, top) -> GameState:
    """Pop 'select_damage', then deal amount_each damage to every chosen target."""
    ctx = top.context
    chosen = list(ctx.get("chosen", []))
    amount_each = int(ctx.get("amount_each", 1))
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_damage",
        choice=f"dealt {amount_each} to {len(chosen)} unit(s)",
    ))
    # Deal damage AFTER pop so any defeat trigger lands on a clean stack.
    from swu.abilities.resolver import _apply_deal_damage
    source_result = s.find_instance(ctx["source_id"])
    source_name = source_result[1].card_def.display_name if source_result else None
    friendly_ids: set = set()
    if source_result is not None:
        _own = s.player_by_id(source_result[1].owner_id)
        friendly_ids = {u.instance_id
                        for u in _own.ground_arena + _own.space_arena}
    for tid in chosen:
        _apply_deal_damage(s, tid, amount_each, source_name=source_name,
                           dealer_id=top.deciding_player_id)
    # "Then, attack with the chosen unit" (Hotshot Maneuver JTL_174) — pushed
    # after the damage so the attack decision lands on a clean stack.  A unit that
    # died to its own card's damage (or has otherwise left play) simply cannot
    # attack: push_granted_attack finds no eligible attacker and fizzles.
    # "If no friendly units were damaged by this ability, deal N damage to your base"
    # (AAT Incinerator SEC_169).  Read from the chosen list against the SOURCE
    # controller's board, checked before the damage could remove anyone — a unit the
    # controller chose and killed still counts as damaged by this ability.
    self_burn = int(ctx.get("self_base_damage_if_no_friendly_hit", 0) or 0)
    if self_burn and source_result is not None:
        owner_id = source_result[1].owner_id
        own = s.player_by_id(owner_id)
        hit_friendly = any(tid in friendly_ids for tid in chosen)
        if not hit_friendly and own.base_instance is not None:
            _apply_deal_damage(s, own.base_instance.instance_id, self_burn,
                               source_name=source_name)
    attacker_id = ctx.get("then_attack_with")
    if attacker_id and source_result is not None and not s.is_terminal():
        push_granted_attack(s, source_result[1], attacker_id=attacker_id)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


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


# ── assign_indirect_damage: receiving player assigns unpreventable damage ─────

def _assign_indirect_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible targets for 'assign_indirect_damage': the receiving player's base
    and all their arena units (a base is always present, so the list is never
    empty while the game is live)."""
    receiving_id: str = ctx["receiving_player_id"]
    ps = state.player_by_id(receiving_id)
    targets = []
    if ps.base_instance is not None:
        targets.append(ps.base_instance.instance_id)
    targets.extend(u.instance_id for u in ps.ground_arena + ps.space_arena)
    return targets


def _indirect_damage_bonus(s: GameState, controller_id: str) -> int:
    """Sum of every in-play ``IndirectDamageBonus`` marker controlled by
    ``controller_id`` (Hunting Aggressor JTL_165: "Indirect damage you deal to
    opponents is increased by 1"; multiple copies stack).  Read only at the
    indirect-damage chokepoint; 0 for the overwhelming majority of boards."""
    from swu.abilities.registry import get_abilities, IndirectDamageBonus
    ps = s.player_by_id(controller_id)
    total = 0
    for u in ps.ground_arena + ps.space_arena:
        sc = getattr(u.card_def, "set_code", None) or ""
        cn = getattr(u.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, IndirectDamageBonus):
                total += spec.amount
    return total


def _controller_self_assigns_indirect(s: GameState, controller_id: str) -> bool:
    """True when ``controller_id`` controls any ``IndirectDamageSelfAssign`` marker
    (Devastator JTL_143: "You assign all indirect damage you deal to opponents").
    Read only at the indirect-damage chokepoint; False for the overwhelming
    majority of boards, so the receiving player assigns as before."""
    from swu.abilities.registry import get_abilities, IndirectDamageSelfAssign
    ps = s.player_by_id(controller_id)
    for u in ps.ground_arena + ps.space_arena:
        # The marker may sit on the unit itself (Devastator JTL_143) or on an
        # attached UPGRADE conferring it ("Attached unit gains: 'You assign all
        # indirect damage dealt by this unit'" — Targeting Computer JTL_171).
        # DOCUMENTED SIMPLIFICATION: the read is controller-scoped, as the
        # decision seam has always been, so an upgrade-borne marker flips the
        # decider for that controller's indirect damage generally rather than only
        # for damage dealt by its own host.
        for card in (u, *u.attached_upgrades):
            sc = getattr(card.card_def, "set_code", None) or ""
            cn = getattr(card.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if isinstance(spec, IndirectDamageSelfAssign):
                    return True
    return False


def push_assign_indirect_damage(
    s: GameState, source_ci: CardInstance, *, amount: int,
    then_draw_if_base: bool = False,
    then_ready_source_if_base: bool = False,
    then_exhaust_damaged: bool = False,
) -> None:
    """Push an 'assign_indirect_damage' decision: the OPPONENT of the source's
    controller must assign ``amount`` unpreventable damage among their base and
    units (First Order Stormtrooper JTL_132, Dengar JTL_139, etc.).

    Unlike normal damage this bypasses shields (indirect damage) and cannot be
    split — the receiving player picks ONE target that absorbs all ``amount``
    points.  Because the base is always a valid target the decision always has a
    legal action (no confirm step needed).  Damage is applied AFTER popping the
    decision ("pop, then deal").

    Three optional RIDERS settle at the same resolve point, once it is known what
    the receiving player actually hit (the "then_*" convention the other decisions
    already use).  They read off the single chosen target, which is exactly the
    granularity this decision models:

    ``then_draw_if_base``
        "If a base is damaged this way, draw a card" (Tactical Heavy Bomber
        JTL_152) — the SOURCE's controller draws.
    ``then_ready_source_if_base``
        "If a base is damaged this way, ready this unit" (Guerilla Soldier
        JTL_218) — a no-op if the source has since left play.
    ``then_exhaust_damaged``
        "Exhaust each unit damaged this way" (Kimogila Heavy Fighter JTL_222) —
        "each" is at most one unit here, and a unit defeated by the damage is no
        longer in an arena so nothing is exhausted.

    All three are inert by default, so every existing caller is unchanged.
    """
    controller_id = source_ci.owner_id
    receiving_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    amount = int(amount)
    # Static "indirect damage you deal is increased by N" markers (Hunting
    # Aggressor JTL_165) raise the amount — but only when there is damage to raise
    # (a 0-point deal stays 0, so a marker can never conjure damage from nothing).
    if amount > 0:
        amount += _indirect_damage_bonus(s, controller_id)
    ctx: dict = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "receiving_player_id": receiving_id,
        "amount": amount,
        "chosen_id": None,
    }
    if then_draw_if_base:
        ctx["then_draw_if_base"] = True
    if then_ready_source_if_base:
        ctx["then_ready_source_if_base"] = True
    if then_exhaust_damaged:
        ctx["then_exhaust_damaged"] = True
    if not _assign_indirect_damage_targets(s, ctx):
        return
    # "You assign all indirect damage you deal to opponents" (Devastator JTL_143):
    # the source's controller picks the target instead of the receiving player.
    # The eligible targets are unchanged (the receiving player's base/units); only
    # the decider flips.
    if _controller_self_assigns_indirect(s, controller_id):
        decider_id = controller_id
    else:
        decider_id = receiving_id
    decider_idx = s.player_index(decider_id)
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="assign_indirect_damage",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = decider_idx
    s.event_log.append(DecisionPushed(deciding_player_id=decider_id, kind="assign_indirect_damage"))


def _resolve_assign_indirect_damage(s: GameState, top) -> GameState:
    """Pop 'assign_indirect_damage', apply the indirect damage to the chosen
    target, then fire WhenIndirectDamageDealtToUnit if the target was a unit.

    Damage is dealt AFTER popping (the push_distribute_damage "pop, then deal"
    gotcha) so any WhenDefeated trigger — and the WhenIndirectDamageDealtToUnit
    observer (Allegiant General Pryde JTL_133) — lands on a clean stack.  The
    active player is set to the source controller only once nothing is pending."""
    from swu.abilities.resolver import _apply_indirect_damage, fire_triggered_abilities
    from swu.cards.models import Base
    ctx = top.context
    chosen_id: Optional[str] = ctx.get("chosen_id")
    amount = int(ctx["amount"])
    after_idx = top.after_resolve_player_index
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="assign_indirect_damage",
        choice=f"assigned {amount} indirect to {chosen_id}",
    ))
    if chosen_id is not None:
        source_result = s.find_instance(ctx["source_id"])
        source_name = source_result[1].card_def.display_name if source_result else None
        was_unit = False
        target_result = s.find_instance(chosen_id)
        if target_result is not None:
            was_unit = not isinstance(target_result[1].card_def, Base)
        _apply_indirect_damage(s, chosen_id, amount, source_name=source_name,
                               dealer_id=ctx.get("controller_id"))
        # Ledger for "If you dealt indirect damage this phase, …" (Decimator of
        # Dissidents JTL_138).  Only a real (non-zero) deal counts.
        if amount > 0 and ctx.get("controller_id"):
            s.game_memory.indirect_dealers_this_phase.add(ctx["controller_id"])
        # ── "then_*" riders (JTL_152 / JTL_218 / JTL_222) ──────────────────
        # Settled here, where it is known what the receiving player actually hit.
        # Only real damage counts as "damaged this way" (a 0-point deal does not).
        if amount > 0:
            if not was_unit and (ctx.get("then_draw_if_base")
                                 or ctx.get("then_ready_source_if_base")):
                if ctx.get("then_draw_if_base"):
                    _draw_cards(s, s.player_by_id(ctx["controller_id"]), 1)
                if ctx.get("then_ready_source_if_base") and source_result is not None:
                    source_result[1].exhausted = False
            if was_unit and ctx.get("then_exhaust_damaged"):
                # The unit may have been defeated by the damage — exhaust it only
                # while it is still in an arena.
                hit = s.find_instance(chosen_id)
                if hit is not None and hit[1].zone in (Zone.GROUND_ARENA,
                                                       Zone.SPACE_ARENA):
                    hit[1].exhausted = True
        # Fire WhenIndirectDamageDealtToUnit for any observer in play (Allegiant
        # General Pryde JTL_133) — fires whether or not the unit survived the
        # damage (indirect damage WAS dealt to a unit).
        if was_unit and not s.is_terminal():
            fire_triggered_abilities(
                s, None,
                after_all_player_idx=after_idx,
                event_ctx={"indirect_damage_unit_id": chosen_id},
            )
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = after_idx
    return s


# ── Player-directed damage distribution push helpers ──────────────────────────

def _push_distribute_decision(s: GameState, source_ci: CardInstance, ctx: dict) -> None:
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="distribute_damage",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="distribute_damage",
    ))


def push_distribute_damage(
    s: GameState, source_ci: CardInstance, amount: int,
    *,
    target_controller: str = "enemy",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
    exclude_ids: Optional[list[str]] = None,
    restrict_ids: Optional[list[str]] = None,
    up_to: bool = False,
    then_heal_base_if_survives: bool = False,
) -> None:
    """Push a 'distribute_damage' decision: "Deal ``amount`` damage divided as
    you choose among <filter> units" (Emperor Palpatine, SOR_135).

    The controller allocates the fixed pool one point at a time onto any legal
    target via ``AssignDamage`` (piling several points onto one unit is allowed);
    the damage is dealt simultaneously once the pool is spent.  If ``amount`` is
    non-positive or there are no legal targets, nothing is pushed and the effect
    fizzles cleanly (the caller hands the turn over normally).

    ``up_to=True`` makes it "deal UP TO ``amount`` damage" (Boba Fett JTL_9's
    "deal up to 4 damage divided … among any number of units"): a
    ``FinishDamageDistribution`` action is offered alongside the per-target
    ``AssignDamage`` options so the controller may stop before spending the whole
    pool (assigning 0 is allowed).

    ``restrict_ids`` is the WHITELIST complement of ``exclude_ids`` (the
    ``push_select_token`` LOF_147 field): only those instance ids may absorb the
    pool.  Pinned to ONE id it turns the pool into "deal up to N damage to <that
    unit>" — the way a card whose target is a single chosen unit still lets the
    controller pick the magnitude, since no choose-a-number decision exists (Choke
    on Aspirations LAW_102, whose target is chosen first by an ordinary
    ``CustomEffect.target``).

    ``then_heal_base_if_survives`` heals the controller's base for the damage
    actually dealt, but only while every damaged target is still in an arena —
    "If it survives, heal damage from your base equal to the damage dealt this
    way" (LAW_102).  Settled in ``_finish_distribution`` after the pop, so a
    defeat triggered by the damage lands on a clean stack first.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "pool",
        "pool": int(amount),
        "up_to": bool(up_to),
        "alloc": {},
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": list(exclude_ids or []),
        "restrict_ids": list(restrict_ids) if restrict_ids is not None else None,
        "heal_base_if_survives": bool(then_heal_base_if_survives),
    }
    if int(amount) <= 0 or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_distribute_heal(
    s: GameState, source_ci: CardInstance, amount: int,
    *,
    include_bases: bool = True,
    then_damage_self: bool = True,
    target_controller: str = "friendly",
    exclude_ids: Optional[list] = None,
) -> None:
    """Push an "up to ``amount``" heal distribution: "Heal up to N total damage from
    any number of units and/or bases" (Redemption SOR_52), reusing the
    ``distribute_damage`` pool machinery with a ``heal`` flag.

    The controller allocates the pool one point at a time onto its own damaged
    units/bases via ``AssignDamage`` (a target drops out once fully healed) and may
    stop early via ``FinishDamageDistribution`` (the pool is always "up to").  On
    finish, each allocation heals that much damage and — when ``then_damage_self`` —
    the total actually healed is dealt back to ``source_ci`` ("Deal that much damage
    to this unit").  Nothing is pushed when the pool is non-positive or the
    controller has nothing damaged to heal (the effect fizzles: 0 healed ⇒ 0 self
    damage).
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "pool",
        "heal": True,
        "include_bases": bool(include_bases),
        "heal_controller": str(target_controller),
        "exclude_ids": list(exclude_ids or []),
        "self_damage_source_id": source_ci.instance_id if then_damage_self else None,
        "pool": int(amount),
        "up_to": True,
        "alloc": {},
    }
    if int(amount) <= 0 or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_distribute_source_power(
    s: GameState, source_ci: CardInstance,
    *,
    source_controller: str = "friendly",
    source_arena: Optional[str] = None,
    source_traits: Optional[list[str]] = None,
    buff_power: int = 0,
    buff_hp: int = 0,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
    exclude_source_from_targets: bool = True,
) -> None:
    """Push a 'distribute_damage' decision: the controller picks a source unit
    (which may receive a this-phase stat buff), then that unit deals damage equal
    to its (buffed) power divided as the controller chooses among any number of
    OTHER units (Overwhelming Barrage, SOR_92).

    Pushes only when at least one source unit exists.  After the source is
    chosen, the distribution fizzles cleanly if its power is 0 or no other unit
    can be targeted.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "source_pool",
        "stage": "pick_source",
        "source_controller": source_controller,
        "source_arena": source_arena,
        "source_traits": list(source_traits or []),
        "buff_power": int(buff_power),
        "buff_hp": int(buff_hp),
        "exclude_source_from_targets": exclude_source_from_targets,
        "pool": 0,
        "alloc": {},
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": [],
    }
    if not _distribution_sources(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_sequence_damage(
    s: GameState, source_ci: CardInstance,
    *,
    num_sources: int = 2,
    source_controller: str = "friendly",
    source_arena: Optional[str] = None,
    source_traits: Optional[list[str]] = None,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
) -> None:
    """Push a 'distribute_damage' decision: the controller picks a single target
    unit, then up to ``num_sources`` distinct source units (filtered by trait)
    each deal damage equal to their power to that same target, in sequence
    (stopping early if the target is defeated) — Maximum Firepower, SOR_234.

    Pushes only when at least one source AND one legal target exist; otherwise
    the effect fizzles cleanly.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "sequence",
        "stage": "pick_target",
        "source_controller": source_controller,
        "source_arena": source_arena,
        "source_traits": list(source_traits or []),
        "num_sources": int(num_sources),
        "sources_used": [],
        "target_id": None,
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": [],
        "alloc": {},
    }
    if not _distribution_sources(s, ctx) or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def spend_force_token(s: GameState, ps: PlayerState) -> bool:
    """Use the Force for ``ps`` — spend their Force token (the single per-player
    boolean).  The one chokepoint for "use the Force": the ``UseForce`` ability
    cost, the ``use_force`` decision, and every card's force-spending
    ``CustomEffect`` route through here, so the WhenYouUseForce observer (Yoda
    LOF_101) sees every spend.

    Records the spender's player id in ``GameMemory.force_uses`` (drained at the
    settle-point by ``_fire_force_observers``).  Returns True if a token was spent,
    False if the player had none — so a caller can keep its "if you do" early-return
    (a spend that never happened must not trigger the observer)."""
    if not getattr(ps, "has_force_token", False):
        return False
    ps.has_force_token = False
    s.game_memory.force_uses.append(ps.player_id)
    return True


def _take_from_hand(ps: PlayerState, instance_id: str) -> CardInstance:
    for i, ci in enumerate(ps.hand):
        if ci.instance_id == instance_id:
            ps.hand.pop(i)
            return ci
    raise IllegalActionError(f"Card {instance_id} not found in hand")


def _take_from_hand_or_discard(ps: PlayerState, instance_id: str) -> CardInstance:
    """Remove and return a card from ``ps``'s hand or discard pile (Gideon's
    Light Cruiser SHD_242: "from your hand or discard pile")."""
    for zone in (ps.hand, ps.discard):
        for i, ci in enumerate(zone):
            if ci.instance_id == instance_id:
                zone.pop(i)
                return ci
    raise IllegalActionError(f"Card {instance_id} not found in hand or discard")


def _find_in_arenas_any(state: GameState, instance_id: str) -> Optional[CardInstance]:
    """Find a unit by id across both players' arenas (None once defeated)."""
    for ps in state.players:
        found = _find_in_arenas(ps, instance_id)
        if found is not None:
            return found
    return None


# ── distribute_damage decision helpers ───────────────────────────────────────

def _distribution_units(
    state: GameState, controller_id: str, controller_filter: str,
    arena: Optional[str], traits: list[str], exclude_ids: list[str],
) -> list[str]:
    """Instance ids of arena units matching a distribution filter.

    ``controller_filter`` is "friendly" / "enemy" / "any" relative to
    ``controller_id``; ``arena`` is "ground" / "space" / None (both); ``traits``
    must all be present; ids in ``exclude_ids`` are skipped (e.g. the source unit
    when distributing among "other units").
    """
    owner_idx = state.player_index(controller_id)
    out: list[str] = []
    for i, ps in enumerate(state.players):
        is_friendly = (i == owner_idx)
        if controller_filter == "friendly" and not is_friendly:
            continue
        if controller_filter == "enemy" and is_friendly:
            continue
        arena_lists = []
        if arena in (None, "ground"):
            arena_lists.append(ps.ground_arena)
        if arena in (None, "space"):
            arena_lists.append(ps.space_arena)
        for arena_list in arena_lists:
            for ci in arena_list:
                if ci.instance_id in exclude_ids:
                    continue
                if traits:
                    from swu.engine.traits import get_traits
                    ctraits = get_traits(state, ci)
                    if any(t not in ctraits for t in traits):
                        continue
                out.append(ci.instance_id)
    return out


def _distribution_targets(state: GameState, ctx: dict) -> list[str]:
    if ctx.get("heal"):
        return _heal_distribution_targets(state, ctx)
    out = _distribution_units(
        state, ctx["controller_id"],
        ctx.get("target_controller", "any"), ctx.get("target_arena"),
        ctx.get("target_traits", []), ctx.get("exclude_ids", []),
    )
    allowed = ctx.get("restrict_ids")
    if allowed is not None:
        out = [t for t in out if t in allowed]
    return out


def _heal_distribution_targets(state: GameState, ctx: dict) -> list[str]:
    """Instance ids of the controller's own damaged units (and, when
    ``include_bases``, its damaged base) that can still absorb more of the heal
    pool — a target drops out once its allocation reaches its current damage, so a
    heal point is never wasted on an undamaged / already-fully-healed target.

    Backs the heal flavour of the ``distribute_damage`` decision (Redemption
    SOR_52: "Heal up to 8 total damage from any number of units and/or bases").
    Restricted to the controller's own cards — healing an enemy card while dealing
    the healed total back to Redemption is never useful, a documented simplification
    of the printed "any number of units and/or bases".
    """
    ps = state.player_by_id(ctx["controller_id"])
    alloc = ctx.get("alloc", {})
    # ``heal_controller`` widens the pool beyond the controller's own cards —
    # "heal up to 4 damage from among OTHER units" (Nala Se SEC_65) is unqualified,
    # so either player's units may absorb it; ``exclude_ids`` carries the "other"
    # (the source itself).  Defaults keep the Redemption SOR_52 reading.
    owners = ([ps] if ctx.get("heal_controller", "friendly") != "any"
              else list(state.players))
    cands = [ci for owner in owners
             for ci in list(owner.ground_arena) + list(owner.space_arena)]
    if ctx.get("include_bases") and not _bases_cannot_heal(state):
        for owner in owners:
            if owner.base_instance is not None:
                cands.append(owner.base_instance)
    excluded = set(ctx.get("exclude_ids") or ())
    out: list[str] = []
    for ci in cands:
        if ci.instance_id in excluded:
            continue
        if int(ci.damage) - int(alloc.get(ci.instance_id, 0)) > 0:
            out.append(ci.instance_id)
    return out


def _distribution_sources(state: GameState, ctx: dict) -> list[str]:
    return _distribution_units(
        state, ctx["controller_id"],
        ctx.get("source_controller", "friendly"), ctx.get("source_arena"),
        ctx.get("source_traits", []), ctx.get("sources_used", []),
    )


def _finish_distribution(s: GameState) -> GameState:
    """Pop the distribute_damage decision, applying any pooled allocation.

    Pool-allocation flows accumulate per-target amounts in ``alloc`` and deal
    them here (announce-then-deal); sequence flows deal damage as each source is
    chosen and reach here with an empty ``alloc``.
    """
    top = s.pending_decisions.pop()
    ctx = top.context
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="distribute_damage",
        choice="distributed",
    ))
    # Deal the announced division simultaneously, now that the decision is off
    # the stack — any WhenDefeated triggers stack cleanly on top.
    alloc = ctx.get("alloc", {})
    if ctx.get("heal"):
        # Heal flavour (Redemption SOR_52): reduce each target's damage by its
        # allocation, sum the damage actually removed, then deal that total to the
        # source unit ("Deal that much damage to this unit").
        total_healed = 0
        for tid in sorted(alloc):
            amt = int(alloc[tid])
            res = s.find_instance(tid)
            if res is None or amt <= 0:
                continue
            _, ci = res
            healed = min(amt, int(ci.damage))
            ci.damage -= healed
            note_unit_healed(s, ci, healed)
            total_healed += healed
        self_id = ctx.get("self_damage_source_id")
        if self_id and total_healed > 0 and s.find_instance(self_id) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, self_id, total_healed,
                               dealer_id=ctx.get("controller_id"))
    elif alloc:
        from swu.abilities.resolver import _apply_deal_damage
        dealer_id = ctx.get("controller_id")
        dealt = 0
        for tid in sorted(alloc):
            amt = int(alloc[tid])
            if amt > 0:
                _apply_deal_damage(s, tid, amt, dealer_id=dealer_id)
                dealt += amt
        if ctx.get("heal_base_if_survives") and dealt > 0:
            # "If it survives, heal damage from your base equal to the damage dealt
            # this way" (Choke on Aspirations LAW_102) — a target the damage
            # defeated has left its arena, and forfeits the heal.
            # ``find_instance`` reaches the discard, so survival is an ARENA test.
            in_arena = {ci.instance_id
                        for p in s.players
                        for ci in list(p.ground_arena) + list(p.space_arena)}
            survived = all(tid in in_arena
                           for tid in alloc if int(alloc[tid]) > 0)
            base = s.player_by_id(ctx["controller_id"]).base_instance
            if survived and base is not None and not _bases_cannot_heal(s):
                before_base = int(base.damage)
                base.damage = max(0, int(base.damage) - dealt)
                note_base_healed(s, base, before_base - base.damage)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _distribute_damage_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top distribute_damage decision (never empty: the
    push helpers only push when ≥1 option exists, and every stage transition
    auto-finishes when the next stage would be empty)."""
    ctx = top.context
    mode = ctx.get("mode")
    if mode == "pool":
        acts: list[Action] = [AssignDamage(t) for t in _distribution_targets(state, ctx)]
        if ctx.get("up_to"):
            acts.append(FinishDamageDistribution())
        return acts
    if mode == "source_pool":
        if ctx.get("stage") == "pick_source":
            return [ChooseDamageSource(u) for u in _distribution_sources(state, ctx)]
        return [AssignDamage(t) for t in _distribution_targets(state, ctx)]
    if mode == "sequence":
        if ctx.get("stage") == "pick_target":
            return [ChooseDamageTarget(t) for t in _distribution_targets(state, ctx)]
        return [ChooseDamageSource(u) for u in _distribution_sources(state, ctx)]
    return []


def _enumerate_discard_play_actions(
    state: GameState, ps: PlayerState
) -> list["Action"]:
    """Legal ``PlayFromDiscard`` actions for cards in ``ps``'s discard pile that
    carry a ``PlayFromDiscardAction`` spec (Brutal Traditions SHD_38).

    The discard pile is a new legal-action source, scanned here in the ACTION
    phase and mirroring the hand-play enumeration: the spec's ``condition`` must
    hold, and — for an Upgrade — the play is offered once per legal "Attach to …"
    host the controller can afford (cost can depend on the host).  Empty unless a
    discard card actually satisfies its gate and is playable, so the action never
    appears when it could do nothing."""
    from swu.abilities.registry import get_abilities, PlayFromDiscardAction
    out: list[Action] = []
    # (a) Cards carrying a printed play-from-discard Action (Brutal Traditions
    #     SHD_38): gated by ``condition``, played by paying the normal cost.
    for ci in ps.discard:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if not isinstance(spec, PlayFromDiscardAction):
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, ci):
                continue
            if isinstance(ci.card_def, Upgrade):
                for target in _eligible_upgrade_targets(state, ci):
                    cost = _play_cost(state, ci, ps, target_host_id=target.instance_id)
                    if _affordable_with_credits(ps, cost, state):
                        out.append(PlayFromDiscard(ci.instance_id, target.instance_id))
            else:
                cost = _play_cost(state, ci, ps)
                if _affordable_with_credits(ps, cost, state):
                    out.append(PlayFromDiscard(ci.instance_id))
    # (b) Units granted a FREE per-phase replay by Second Chance SHD_53 (a
    #     per-instance permission in game_memory).  A unit re-enters play with no
    #     host and no cost; leaders can never carry the grant (Attach to a
    #     non-leader unit), so this is Unit-only.
    free_ids = getattr(state.game_memory, "free_discard_play_this_phase", None) or set()
    for ci in ps.discard:
        if ci.instance_id in free_ids and isinstance(ci.card_def, Unit):
            out.append(PlayFromDiscard(ci.instance_id, free=True))
    # (b2) Units in ANOTHER player's discard pile that this player was granted a
    #      free replay of (Stolen AT-Hauler JTL_221 "Choose an opponent.  For this
    #      phase, they may play this unit from its owner's discard pile for free").
    #      The card never leaves its owner's pile until it is played, and it enters
    #      under the player who plays it (control follows the holder).
    foreign = (getattr(state.game_memory,
                       "foreign_free_discard_play_this_phase", None) or {})
    permitted = set(foreign.get(ps.player_id, ()))
    if permitted:
        for other in state.players:
            if other.player_id == ps.player_id:
                continue
            for ci in other.discard:
                if ci.instance_id in permitted and isinstance(ci.card_def, Unit):
                    out.append(PlayFromDiscard(ci.instance_id, free=True))
    # (b3) Cards in ANOTHER player's discard pile this player may play this phase by
    #      PAYING the cost, with the card's aspect penalties waived (Obi-Wan Kenobi
    #      SEC_205).  The waiver is expressed as a ``discount`` equal to the aspect
    #      penalty the payer would otherwise owe, so the cost path is the shared one.
    foreign_paid = (getattr(state.game_memory,
                            "foreign_discard_play_this_phase", None) or {})
    paid_ids = set(foreign_paid.get(ps.player_id, ()))
    if paid_ids:
        for other in state.players:
            if other.player_id == ps.player_id:
                continue
            for ci in other.discard:
                if ci.instance_id not in paid_ids:
                    continue
                penalty = max(0, _effective_cost(ci.card_def, ps, state)
                              - int(getattr(ci.card_def, "cost", None) or 0))
                if isinstance(ci.card_def, Upgrade):
                    for target in _eligible_upgrade_targets(state, ci):
                        cost = max(0, _play_cost(state, ci, ps,
                                                 target_host_id=target.instance_id)
                                   - penalty)
                        if _affordable_with_credits(ps, cost, state):
                            out.append(PlayFromDiscard(
                                ci.instance_id, target.instance_id,
                                discount=penalty))
                else:
                    cost = max(0, _play_cost(state, ci, ps) - penalty)
                    if _affordable_with_credits(ps, cost, state):
                        out.append(PlayFromDiscard(ci.instance_id, discount=penalty))
    # (c) Cards granted a DISCOUNTED per-phase play from the discard pile (Aid from
    #     the Innocent TWI_201).  Any card type — the granting card discards
    #     non-units — so an Upgrade is offered once per legal host, like (a).
    discounts = getattr(
        state.game_memory, "discard_play_discount_this_phase", None) or {}
    for ci in ps.discard:
        red = int(discounts.get(ci.instance_id, 0))
        if red <= 0:
            continue
        if isinstance(ci.card_def, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                cost = max(0, _play_cost(state, ci, ps,
                                         target_host_id=target.instance_id) - red)
                if _affordable_with_credits(ps, cost, state):
                    out.append(PlayFromDiscard(ci.instance_id, target.instance_id,
                                               discount=red))
        else:
            cost = max(0, _play_cost(state, ci, ps) - red)
            if _affordable_with_credits(ps, cost, state):
                out.append(PlayFromDiscard(ci.instance_id, discount=red))
    return out


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


def _eligible_pilot_targets(state: GameState, ps: PlayerState) -> list[CardInstance]:
    """Friendly Vehicle units the active player may attach a Pilot upgrade to."""
    from swu.engine.traits import has_trait
    targets = []
    for ci in ps.ground_arena + ps.space_arena:
        if has_trait(state, ci, "Vehicle"):
            targets.append(ci)
    return targets


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


def _attach_pilot(
    s: GameState, ps: PlayerState, pilot_ci: CardInstance, vehicle_target_id: str,
) -> None:
    """Attach a Unit pilot to a friendly Vehicle unit, firing UpgradePlayed."""
    pilot_ci.face_down = False
    for owner_ps in s.players:
        for unit_ci in owner_ps.ground_arena + owner_ps.space_arena:
            if unit_ci.instance_id == vehicle_target_id:
                pilot_ci.zone = unit_ci.zone
                unit_ci.attached_upgrades.append(pilot_ci)
                note_upgrade_attached(s, unit_ci)      # Sabine Wren ASH_208
                evt = UpgradePlayed(
                    player_id=ps.player_id,
                    instance_id=pilot_ci.instance_id,
                    card_name=pilot_ci.card_def.display_name,
                    attached_to_instance_id=vehicle_target_id,
                )
                s.event_log.append(evt)
                get_bus().fire(s, evt)
                from swu.abilities.resolver import fire_triggered_abilities
                after_idx = 1 - s.player_index(ps.player_id)
                fire_triggered_abilities(s, evt, after_all_player_idx=after_idx,
                                         event_ctx={"attached_to_id": vehicle_target_id,
                                                    "via_pilot": True})
                return
    raise IllegalActionError(f"Pilot vehicle target {vehicle_target_id} not found in any arena")


def _plot_eligible_resource_ids(state: GameState, ps: PlayerState) -> list[str]:
    """Instance ids of resources carrying the Plot keyword (the snapshot taken
    when a leader deploys — see DeployLeader / PlotPlay)."""
    return [ci.instance_id for ci in ps.resources
            if has_keyword(state, ci, Keyword.PLOT)]


def _plot_play_actions(
    state: GameState, ps: PlayerState, allowed_ids: "set[str]"
) -> list[Action]:
    """PlotPlay actions for every Plot resource the player may play right now.

    A resource is offered iff it is in ``allowed_ids`` (the set snapshotted at
    leader-deploy time, so a card later drawn into the zone as a replacement is
    not retroactively plottable), still carries Plot, and its printed effective
    cost is payable from the OTHER ready resources.  An upgrade additionally
    needs a legal host.
    """
    acts: list[Action] = []
    for ci in ps.resources:
        if ci.instance_id not in allowed_ids:
            continue
        if not has_keyword(state, ci, Keyword.PLOT):
            continue
        cost = _play_cost(state, ci, ps, via_plot=True)
        other_ready = sum(
            1 for r in ps.resources
            if not r.exhausted and r.instance_id != ci.instance_id
        )
        if other_ready < cost:
            continue
        if isinstance(ci.card_def, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                acts.append(PlotPlay(ci.instance_id, target.instance_id))
        else:
            acts.append(PlotPlay(ci.instance_id))
    return acts


def _resource_top_of_deck(s: GameState, ps: PlayerState) -> None:
    """Put the top card of ``ps``'s deck into play as a ready resource (face down).

    The shared ramp primitive behind "put the top card of your deck into play as a
    resource" (When Has Become Now SEC_245; mirrors the Price on Your Head SHD_125
    bounty).  No-op on an empty deck."""
    if not ps.deck:
        return
    ci = ps.deck.pop(0)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    s.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))


def _resource_card_from_hand(s: GameState, ps: PlayerState) -> None:
    """Put a card from ``ps``'s hand into play as a READY resource (face down).

    The from-hand sibling of ``_resource_top_of_deck``, behind "put a card from
    your hand into play as a resource and ready it" (Han Solo SOR_17's undeployed
    Action).  Faithful simplification (K-2SO SOR_145 auto-select precedent): the
    highest-cost hand card is chosen — the one least likely to be immediately
    playable, i.e. the natural card to resource — instead of prompting.  No-op on
    an empty hand."""
    if not ps.hand:
        return
    ci = max(ps.hand, key=lambda c: getattr(c.card_def, "cost", 0) or 0)
    ps.hand.remove(ci)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    s.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))


def push_plot_ability(s: GameState, source_ci: CardInstance, *,
                      ramp: bool = True) -> None:
    """Push a single-shot 'plot' decision: "Play a card with Plot from your
    resources (paying its cost)" (When Has Become Now SEC_245).

    Reuses the Plot decision / PlotPlay path (the chosen card is played via its
    Plot keyword — pay its printed cost, replace it with the deck top), but the
    context is marked ``plot_ability`` so PlotPlay resolves the decision after ONE
    play instead of re-offering the rest, and — when ``ramp`` — performs the
    errata's "if you do, put the top card of your deck into play as a resource".
    Pushed only when the controller has a Plot card in their resources they can
    actually afford right now; otherwise a no-op (you did not play a card, so no
    ramp)."""
    ps = s.player_by_id(source_ci.owner_id)
    plot_ids = [] if s.is_terminal() else _plot_eligible_resource_ids(s, ps)
    if not (plot_ids and _plot_play_actions(s, ps, set(plot_ids))):
        return
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=ps.player_id,
        kind="plot",
        context={"plot_ids": plot_ids, "plot_ability": True,
                 "ramp_after": bool(ramp)},
        after_resolve_player_index=1 - s.active_player_index,
    ))
    s.event_log.append(DecisionPushed(
        deciding_player_id=ps.player_id,
        kind="plot",
    ))


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
    "trigger_option":                _trigger_option_actions,
    "resolve_effects":               _resolve_effects_actions,
    "granted_attack":                _granted_attack_actions,
    "pre_attack":                    _pre_attack_actions,
    "play_from_hand":                _play_from_hand_actions,
    "play_event_from_hand":          _play_event_from_hand_actions,
    "play_via_smuggle":              _play_via_smuggle_actions,
    "play_via_piloting":             _play_via_piloting_actions,
    "opponent_ready":                _opponent_ready_actions,
    "say_no":                        _say_no_actions,
    "regroup_upkeep":                _regroup_upkeep_actions,
    "pay_or_exhaust":                _pay_or_exhaust_actions,
    "distribute_damage":             _distribute_damage_actions,
    "deck_search":                   _deck_search_actions,
    "return_from_discard":           _return_from_discard_actions,
    "resource_from_discard":         _resource_from_discard_actions,
    "play_captured_card":            _play_captured_actions,
    "play_resource_units":           _play_resource_units_actions,
    "reveal_cull_draw":              _reveal_cull_draw_actions,
    "discard_for_experience":        _discard_for_experience_actions,
    "select_distinct_return_random": _select_distinct_return_random_actions,
    "bottom_from_discard":           _bottom_from_discard_actions,
    "select_token":                  _select_token_actions,
    "disclose":                      _disclose_actions,
    "select_damage":                 _select_damage_actions,
    "assign_indirect_damage":        _assign_indirect_damage_actions,
    "peek_top":                      _peek_top_actions,
    "choose_number":                 _choose_number_actions,
    "look_hand":                     _look_hand_actions,
    "modal":                         _modal_actions,
    "let_wookiee_win":               _let_wookiee_win_actions,
    "reveal_top":                    _reveal_top_actions,
    "reveal_cost_damage":            _reveal_cost_damage_actions,
    "repeated_modal":                _repeated_modal_actions,
    "choose_two_modal":              _choose_two_modal_actions,
    "sacrifice_resource":            _sacrifice_resource_actions,
    "reveal_resource_ramp":          _reveal_resource_ramp_actions,
    "discard_unit_damage":           _discard_unit_damage_actions,
    "cull_for_damage":               _cull_for_damage_actions,
    "discard_for_search":            _discard_for_search_actions,
    "recur_and_buff":                _recur_and_buff_actions,
    "move_upgrade":                  _move_upgrade_actions,
    "pay_and_steal_upgrade":         _pay_and_steal_upgrade_actions,
    "pilot_self_attach":             _pilot_self_attach_actions,
    "play_upgrade_from_hand":        _play_upgrade_from_hand_actions,
    "opponent_chooses_target":       _opponent_chooses_target_actions,
    "opponent_split_bounce":         _opponent_split_bounce_actions,
    "owner_may_replay":              _owner_may_replay_actions,
    "put_on_deck":                   _put_on_deck_actions,
    "each_player_defeats":           _each_player_defeats_actions,
    "name_a_card":                   _name_a_card_actions,
    "capture_or_ready":              _capture_or_ready_actions,
    "choose_units_sacrifice_rest":   _choose_units_sacrifice_rest_actions,
    "resolve_unique":                _resolve_unique_actions,
    "bottom_from_hand":              _bottom_from_hand_actions,
    "resource_from_hand":            _resource_from_hand_actions,
    "discard_excess_from_hand":      _discard_excess_from_hand_actions,
    "name_and_discard":              _name_and_discard_actions,
    "may_discard":                   _may_discard_actions,
    "exhaust_for_base_damage":       _exhaust_for_base_damage_actions,
    "exhaust_combined_cost":         _exhaust_combined_cost_actions,
    "capture_combined_hp":           _capture_combined_hp_actions,
    "rescue_guarded":                _rescue_guarded_actions,
    "multi_capture_pairing":         _multi_capture_pairing_actions,
    "combined_power_play":           _combined_power_play_actions,
    "per_exploit_damage":            _per_exploit_damage_actions,
    "use_force":                     _use_force_actions,
    "pay_resources_for_tokens":      _pay_resources_for_tokens_actions,
    "reveal_play_credit":            _reveal_play_credit_actions,
    "plot":                          _plot_actions,
})
