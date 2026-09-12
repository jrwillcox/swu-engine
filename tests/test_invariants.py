"""Unit tests for the invariant checker's structural checks."""
from __future__ import annotations

import uuid

import pytest

from swu.engine.invariants import (
    CheckContext, _check_zone_consistency, _check_upgrade_zone,
    _check_modifier_expiry, _check_phase_memory, _check_pass_consistency,
    _check_terminal_quiescence,
)
from swu.engine.state import (
    GameState, PlayerState, CardInstance, Zone, Phase, Modifier,
)
from swu.cards.models import Base


def _base(pid):
    bdef = Base(
        id=abs(hash(pid)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="99", name=f"Base {pid}", subtitle=None, type="Base",
        rarity="Common", is_unique=False, artist=None, text=None, text_styled=None,
        rules=None, rules_styled=None, aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, hp=30, epic_action=None,
    )
    return CardInstance(instance_id=f"{pid}_base", card_def=bdef,
                        owner_id=pid, zone=Zone.BASE_ZONE)


def _card(pid, zone):
    bdef = Base(
        id=12345, card_uid=None, set_code="TST", set_name="T", card_number="7",
        name="Filler", subtitle=None, type="Base", rarity="Common", is_unique=False,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(), image_front_url=None,
        image_back_url=None, image_front_path=None, image_back_path=None,
        hp=0, epic_action=None,
    )
    return CardInstance(instance_id=f"{pid}_{uuid.uuid4().hex[:6]}",
                        card_def=bdef, owner_id=pid, zone=zone)


def _state():
    ps0 = PlayerState(player_id="P0")
    ps1 = PlayerState(player_id="P1")
    ps0.base_zone.append(_base("P0"))
    ps1.base_zone.append(_base("P1"))
    return GameState(players=[ps0, ps1], phase=Phase.ACTION)


def _ctx():
    return CheckContext(initial_card_ids={}, action_count=1)


def test_clean_state_passes():
    state = _state()
    c = _card("P0", Zone.HAND)
    state.player_by_id("P0").hand.append(c)
    _check_zone_consistency(state, _ctx())  # must not raise


def test_zone_tag_mismatch_detected():
    state = _state()
    c = _card("P0", Zone.GROUND_ARENA)  # wrong tag for a card placed in hand
    state.player_by_id("P0").hand.append(c)
    with pytest.raises(AssertionError, match="Zone-tag mismatch"):
        _check_zone_consistency(state, _ctx())


def test_exhausted_in_hand_detected():
    state = _state()
    c = _card("P0", Zone.HAND)
    c.exhausted = True
    state.player_by_id("P0").hand.append(c)
    with pytest.raises(AssertionError, match="Exhausted card"):
        _check_zone_consistency(state, _ctx())


def test_resource_placement_is_covered():
    """A resource card must be tagged RESOURCES (resource-conservation check)."""
    state = _state()
    c = _card("P0", Zone.HAND)  # mis-tagged HAND but sitting in resources
    state.player_by_id("P0").resources.append(c)
    with pytest.raises(AssertionError, match="Zone-tag mismatch"):
        _check_zone_consistency(state, _ctx())


# ── upgrade-zone consistency ──────────────────────────────────────────────────

def _mod(mid, duration):
    return Modifier(modifier_id=mid, source_instance_id="P0_src",
                    target_instance_id=None, kind="stats",
                    value={"power": 1, "hp": 0}, duration=duration)


def test_upgrade_zone_matches_host():
    state = _state()
    host = _card("P0", Zone.GROUND_ARENA)
    upg = _card("P0", Zone.GROUND_ARENA)
    host.attached_upgrades.append(upg)
    state.player_by_id("P0").ground_arena.append(host)
    _check_upgrade_zone(state, _ctx())  # must not raise


def test_upgrade_zone_mismatch_detected():
    state = _state()
    host = _card("P0", Zone.GROUND_ARENA)
    upg = _card("P0", Zone.SPACE_ARENA)  # wrong zone tag vs host
    host.attached_upgrades.append(upg)
    state.player_by_id("P0").ground_arena.append(host)
    with pytest.raises(AssertionError, match="Upgrade"):
        _check_upgrade_zone(state, _ctx())


# ── modifier expiry ───────────────────────────────────────────────────────────

def test_this_attack_modifier_stale_in_settled_state():
    state = _state()
    state.modifiers.append(_mod("m1", "this_attack"))
    with pytest.raises(AssertionError, match="this_attack"):
        _check_modifier_expiry(state, _ctx())


def test_this_attack_modifier_ok_with_pending_decision():
    state = _state()
    state.modifiers.append(_mod("m1", "this_attack"))
    # Mid-attack (a pending decision is open) — not yet settled, so allowed.
    from swu.engine.decisions import PendingDecision
    state.pending_decisions.append(
        PendingDecision(deciding_player_id="P0", kind="pre_attack",
                        context={}, after_resolve_player_index=0)
    )
    _check_modifier_expiry(state, _ctx())  # must not raise


def test_this_round_modifier_must_not_survive_rollover():
    state = _state()
    state.round_number = 2
    state.modifiers.append(_mod("r1", "this_round"))
    ctx = CheckContext(initial_card_ids={}, action_count=1,
                       prev_round=1, prev_this_round_mod_ids=frozenset({"r1"}))
    with pytest.raises(AssertionError, match="this_round"):
        _check_modifier_expiry(state, ctx)


# ── phase-scoped memory ───────────────────────────────────────────────────────

def test_phase_memory_must_be_clear_after_rollover():
    state = _state()
    state.round_number = 2
    state.game_memory.units_played_this_phase.add("P0_x")
    ctx = CheckContext(initial_card_ids={}, action_count=1, prev_round=1)
    with pytest.raises(AssertionError, match="units_played_this_phase"):
        _check_phase_memory(state, ctx)


def test_phase_memory_persists_within_round_ok():
    state = _state()
    state.round_number = 1
    state.game_memory.units_played_this_phase.add("P0_x")  # legit during ACTION
    ctx = CheckContext(initial_card_ids={}, action_count=1, prev_round=1)
    _check_phase_memory(state, ctx)  # no rollover → must not raise


# ── pass / initiative consistency ─────────────────────────────────────────────

def test_both_passed_in_settled_action_detected():
    state = _state()
    state.passed_players = {0, 1}
    with pytest.raises(AssertionError, match="Both players passed"):
        _check_pass_consistency(state, _ctx())


def test_invalid_passed_index_detected():
    state = _state()
    state.passed_players = {5}
    with pytest.raises(AssertionError, match="invalid index"):
        _check_pass_consistency(state, _ctx())


def test_one_passed_is_fine():
    state = _state()
    state.passed_players = {1}
    _check_pass_consistency(state, _ctx())  # must not raise


# ── terminal quiescence ───────────────────────────────────────────────────────

def test_terminal_state_offers_no_actions():
    """A finished game must expose zero legal actions (loop stops on a win)."""
    state = _state()
    state.player_by_id("P1").base_zone[0].damage = 30  # lethal → P0 wins
    assert state.is_terminal()
    _check_terminal_quiescence(state, _ctx())  # must not raise
