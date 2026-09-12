"""The engine's action API: what a player may do, and what happens when they do it.

Two functions matter to callers, and everything else in this module exists to serve them:

* ``legal_actions(state)`` — every action the acting player may legally take right now.
* ``apply(state, action)`` — take one, and return the resulting state.

Those two are the whole surface the bots, the web API and the tests drive the game
through. This module sits at the **top** of the package for that reason: it is allowed to
know about every mechanic, and nothing is allowed to know about it.

When a decision is on the stack the legal actions are whatever that *kind* of decision
allows, and ``_decision_legal_actions`` answers that with a single ``dispatch`` table
lookup. It used to be a 601-line ``if top.kind == …`` chain over seventy-five kinds, which
is the specific reason this file could not be split before: one function naming a handler
from every mechanic in the game forced the module holding it to depend on all of them. Now
each family module claims its own kinds and the dispatcher consults the table, which is
what let the families leave one at a time.

Also here: the actions available with no decision pending -- playing a card, passing,
resourcing, claiming initiative, mulliganing, deploying a leader (including as an upgrade)
-- together with the guards that make those enumerations correct rather than optimistic
(``_events_locked``, ``_cannot_play_from_hand``, ``_named_card_play_forbidden``,
``_play_only_as_first_action_blocked``, ``_mulligan_forbidden``).

⚠ **The Action class names in this module are a wire protocol, not an implementation
detail.** ``web/serializers.py`` sends ``type(action).__name__`` as an action's ``kind`` and
``asdict(action)`` as its ``params``, and the frontend hardcodes fourteen of those names --
``PlayCard``, ``KeepHand``, ``TakeMultiligan``, ``ResourceCard``, ``ClaimInitiative`` and
``ChooseTarget`` among them. Moving a class between modules is safe, because the name does
not change. **Renaming a class, or renaming one of its dataclass fields, is a breaking
frontend change** that no Python test will catch. ``tests/test_actions_contract.py`` pins
the sorted set of names and field names against a golden list precisely so that it does.
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

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    decision_handler, register_decisions,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _consume_standing_discount, _defeat_credit, _discard_cost_candidates, _discard_cost_payable, _exhaust_resources, _pay_play_cost, _pilot_count, _pilot_limit, _piloting_cost, _piloting_discount_entry, _play_cost, _smuggle_cost, resource_cost_for,
)
from swu.engine.actions.damage import (
    base_damage_after_prevention,
)
from swu.engine.actions.zones import (
    _attach_upgrade, _defeat_unit, _draw_cards, _eligible_upgrade_targets, _find_in_arenas, _find_upgrade_host, _push_resolve_unique, _put_unit_in_play, _resolve_event_ability, _sweep_defeated_units, note_upgrade_defeated,
)
from swu.engine.actions.flow import (
    _assert_phase, _check_game_over, _switch_active_player,
)
from swu.engine.actions.shared import (
    _attach_pilot, _deploy_leader_into_arena, _eligible_pilot_targets, _enumerate_discard_play_actions, _plot_eligible_resource_ids, _plot_play_actions, _take_from_hand, spend_force_token,
)
from swu.engine.actions.combat import (
    _enumerate_attacks, _enumerate_two_unit_attacks, _filter_granted_attacks, _forced_attack_actions, note_hand_or_deck_discard, record_hand_discard,
)
from swu.engine.actions.observers import (
    _fire_base_damage_observers, _fire_bounty_observers, _fire_deck_discard_observers, _fire_draw_observers, _fire_force_observers, _fire_hand_discard_observers, _fire_heal_observers, _fire_noncombat_damage_observers, _fire_ready_observers, _fire_reveal_discard_observers, _fire_self_discard_observers, _fire_token_creation_observers, _fire_unit_entry_observers, _fire_upgrade_attach_observers, _fire_upgrade_defeat_observers,
)
from swu.engine.actions.turn import (
    _advance_mulligan, _advance_setup_resources, _check_regroup_complete, _enter_regroup, _starting_hand_modifier, _starting_hand_size,
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


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

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


# ── Test (for unit-test infrastructure only) ──────────────────────────

def _test_actions(state: GameState, top: PendingDecision) -> list[Action]:
    options = top.context.get("options", ["yes", "no"])
    return [AnswerTestDecision(opt) for opt in options]


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
register_decisions({
    "test":                          _test_actions,
    "resolve_effects":               _resolve_effects_actions,
    "granted_attack":                _granted_attack_actions,
})
