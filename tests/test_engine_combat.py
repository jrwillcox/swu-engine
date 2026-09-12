"""Tests for combat, damage, defeat, upgrades, leaders."""
from __future__ import annotations

import pytest

from tests.dbpath import db_path
from conftest import ensure_affordable, make_game, run_through_setup

from swu.engine.actions import (
    AttackWithUnit, DeployLeader, PlayCard, Pass,
    legal_actions, apply, create_game,
)
from swu.engine.state import CardInstance, GameState, Zone
from swu.cards.models import Upgrade


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_unit_instance(iid: str, owner: str, power: int, hp: int, arena: str = "Ground") -> CardInstance:
    class FakeUnit:
        id = 0
        cost = 1
        aspects = ()
        type = "Unit"
        arenas = (arena,)
        display_name = iid
        is_unique = False

    FakeUnit.power = power
    FakeUnit.hp = hp
    ci = CardInstance(iid, FakeUnit(), owner, Zone.GROUND_ARENA if arena == "Ground" else Zone.SPACE_ARENA)
    return ci


def _make_minimal_state(p0_units=None, p1_units=None, seed=42):
    """Build a minimal ACTION-phase state with specified units in play."""
    # Use real decks for setup, then surgically add units
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import build_vanilla_deck
    db = db_path()
    if not db.exists():
        pytest.skip("swu.db not found")
    repo = CardRepository(db)
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db2 = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    state = run_through_setup(create_game("P0", da, "P1", db2, seed=seed))
    # Clear arenas and add specified fake units
    if p0_units:
        state.players[0].ground_arena = p0_units
    if p1_units:
        state.players[1].ground_arena = p1_units
    return state


# ── Combat tests ──────────────────────────────────────────────────────────────

def test_attack_base_deals_damage():
    atk = _make_unit_instance("atk", "P0", 3, 5)
    state = _make_minimal_state(p0_units=[atk])
    base_before = state.players[1].base_instance.damage
    state2 = apply(state, AttackWithUnit("atk", None))
    base_after = state2.players[1].base_instance.damage
    assert base_after == base_before + 3


def test_attack_base_exhausts_attacker():
    atk = _make_unit_instance("atk", "P0", 3, 5)
    state = _make_minimal_state(p0_units=[atk])
    state2 = apply(state, AttackWithUnit("atk", None))
    attacker_in_new_state = state2.players[0].ground_arena[0]
    assert attacker_in_new_state.exhausted


def test_unit_combat_simultaneous_damage():
    atk = _make_unit_instance("atk", "P0", 3, 5)
    dfd = _make_unit_instance("dfd", "P1", 2, 4)
    state = _make_minimal_state(p0_units=[atk], p1_units=[dfd])
    state2 = apply(state, AttackWithUnit("atk", "dfd"))
    p0 = state2.players[0]
    p1 = state2.players[1]
    atk_after = next((u for u in p0.ground_arena if u.instance_id == "atk"), None)
    dfd_after = next((u for u in p1.ground_arena if u.instance_id == "dfd"), None)
    # Attacker takes defender power (2), defender takes attacker power (3)
    assert atk_after is not None
    assert atk_after.damage == 2
    assert dfd_after is not None
    assert dfd_after.damage == 3


def test_unit_defeated_on_lethal_damage():
    atk = _make_unit_instance("atk", "P0", 5, 5)
    dfd = _make_unit_instance("dfd", "P1", 1, 3)
    state = _make_minimal_state(p0_units=[atk], p1_units=[dfd])
    state2 = apply(state, AttackWithUnit("atk", "dfd"))
    p1 = state2.players[1]
    # Defender had 3 hp, took 5 damage → defeated, goes to discard
    assert not any(u.instance_id == "dfd" for u in p1.ground_arena)
    assert any(u.instance_id == "dfd" for u in p1.discard)


def test_attacker_also_defeated_if_lethal():
    atk = _make_unit_instance("atk", "P0", 3, 2)  # hp=2, takes 3 → dies
    dfd = _make_unit_instance("dfd", "P1", 3, 2)
    state = _make_minimal_state(p0_units=[atk], p1_units=[dfd])
    state2 = apply(state, AttackWithUnit("atk", "dfd"))
    assert not any(u.instance_id == "atk" for u in state2.players[0].ground_arena)
    assert not any(u.instance_id == "dfd" for u in state2.players[1].ground_arena)


def test_damage_persists_across_rounds(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b, seed=7))
    # Build a unit with damage
    atk = _make_unit_instance("durable", "P0", 2, 5)
    dfd = _make_unit_instance("dfd", "P1", 1, 10)
    state.players[0].ground_arena = [atk]
    state.players[1].ground_arena = [dfd]
    state.active_player_index = 0
    # Attack: atk takes 1 damage (switches to P1)
    state = apply(state, AttackWithUnit("durable", "dfd"))
    assert state.players[0].ground_arena[0].damage == 1
    # Both players pass to enter regroup
    state = apply(state, Pass())   # P1 passes (switches to P0)
    state = apply(state, Pass())   # P0 passes → enter REGROUP
    from swu.engine.actions import SkipResource
    state = apply(state, SkipResource())
    state = apply(state, SkipResource())
    # Should be round 2, damage still there
    assert state.round_number == 2
    assert state.players[0].ground_arena[0].damage == 1


def test_win_condition_base_destroyed(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    # Set opponent base to 1 hp away from death
    base_ci = state.players[1].base_instance
    base_ci.damage = base_ci.card_def.hp - 1
    # Attack with 1-power unit
    atk = _make_unit_instance("finisher", "P0", 1, 5)
    state.players[0].ground_arena = [atk]
    state2 = apply(state, AttackWithUnit("finisher", None))
    assert state2.winner == "P0"
    assert state2.is_terminal()
    assert legal_actions(state2) == []


def test_attack_different_arena_illegal():
    """Can't attack a space unit from a ground attacker."""
    atk = _make_unit_instance("ground_atk", "P0", 2, 3)  # ground
    dfd = _make_unit_instance("space_dfd", "P1", 2, 3)   # space
    dfd.zone = Zone.SPACE_ARENA
    state = _make_minimal_state(p0_units=[atk])
    state.players[1].ground_arena = []
    state.players[1].space_arena = [dfd]
    # Ground attacker shouldn't see space defender as legal target
    acts = legal_actions(state)
    atk_acts = [a for a in acts if isinstance(a, AttackWithUnit) and a.attacker_id == "ground_atk"]
    target_ids = [a.defender_id for a in atk_acts]
    assert "space_dfd" not in target_ids


def test_exhausted_unit_cannot_attack():
    atk = _make_unit_instance("tired", "P0", 3, 5)
    atk.exhausted = True
    state = _make_minimal_state(p0_units=[atk])
    acts = legal_actions(state)
    assert not any(
        isinstance(a, AttackWithUnit) and a.attacker_id == "tired"
        for a in acts
    )


# ── Upgrade tests ─────────────────────────────────────────────────────────────

def test_upgrade_modifies_stats(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    upgrade_ci = ensure_affordable(state, Upgrade)
    # Put a unit in play on the same team as a target
    target = _make_unit_instance("tgt", ps.player_id, 2, 3)
    ps.ground_arena.append(target)
    # Apply upgrade
    upg_def = upgrade_ci.card_def
    power_mod = upg_def.upgrade_power or 0
    hp_mod = upg_def.upgrade_hp or 0
    state2 = apply(state, PlayCard(upgrade_ci.instance_id, "tgt"))
    ps2 = state2.players[state.active_player_index]
    unit_after = next(u for u in ps2.ground_arena if u.instance_id == "tgt")
    assert unit_after.effective_power() == 2 + power_mod
    assert unit_after.effective_hp() == 3 + hp_mod


def test_upgrade_detaches_to_owner_discard_on_host_defeat():
    atk = _make_unit_instance("atk", "P0", 10, 10)
    host = _make_unit_instance("host", "P1", 1, 5)
    # Attach a fake upgrade to host
    class FakeUpgrade:
        id = 99
        type = "Upgrade"
        arenas = ("Ground",)
        aspects = ()
        display_name = "FakeUpgrade"
        is_unique = False
        upgrade_power = 1
        upgrade_hp = 0
        cost = 0

    upg = CardInstance("upg1", FakeUpgrade(), "P1", Zone.GROUND_ARENA)
    host.attached_upgrades.append(upg)

    state = _make_minimal_state(p0_units=[atk], p1_units=[host])
    state2 = apply(state, AttackWithUnit("atk", "host"))
    p1 = state2.players[1]
    # Host should be dead
    assert not any(u.instance_id == "host" for u in p1.ground_arena)
    # Upgrade should be in P1's discard
    assert any(u.instance_id == "upg1" for u in p1.discard)


# ── Leader tests ──────────────────────────────────────────────────────────────

def test_deploy_leader_requires_resources(deck_a, deck_b):
    from swu.engine.actions import _deploy_threshold
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    leader_ci = ps.leader_instance
    threshold = _deploy_threshold(leader_ci.card_def)
    assert threshold is not None, (
        f"{leader_ci.card_def.name} deploys on something other than a resource "
        "threshold, so this test can't drive it — pick a different fixture deck"
    )
    # If threshold > total_resources, deploy shouldn't be legal
    if ps.total_resources < threshold:
        acts = legal_actions(state)
        assert not any(isinstance(a, DeployLeader) for a in acts)


def test_deploy_leader_places_in_arena(deck_a, deck_b):
    from swu.engine.actions import _deploy_threshold
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    leader_ci = ps.leader_instance
    threshold = _deploy_threshold(leader_ci.card_def)
    assert threshold is not None, (
        f"{leader_ci.card_def.name} deploys on something other than a resource "
        "threshold, so this test can't drive it — pick a different fixture deck"
    )
    # Give enough resources
    needed = max(0, threshold - len(ps.resources))
    for i in range(needed):
        ci = _make_unit_instance(f"res_{i}", ps.player_id, 0, 1)
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ps.resources.append(ci)
    state2 = apply(state, DeployLeader())
    ps2 = state2.players[state.active_player_index]
    leader_after = ps2.leader_instance
    assert leader_after is not None
    assert leader_after.deployed
    assert leader_after.epic_action_spent
    # CR: a deployed leader enters the arena READY (it can attack the same round),
    # unlike a non-leader unit which enters exhausted.
    assert not leader_after.exhausted
    assert leader_after not in ps2.base_zone


def test_deploy_leader_once_only(deck_a, deck_b):
    from swu.engine.actions import _deploy_threshold
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    leader_ci = ps.leader_instance
    threshold = _deploy_threshold(leader_ci.card_def)
    assert threshold is not None, (
        f"{leader_ci.card_def.name} deploys on something other than a resource "
        "threshold, so this test can't drive it — pick a different fixture deck"
    )
    # Give enough resources
    for i in range(threshold):
        ci = _make_unit_instance(f"res_{i}", ps.player_id, 0, 1)
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ps.resources.append(ci)
    state = apply(state, DeployLeader())
    # Both players pass to enter regroup
    state = apply(state, Pass())  # other player passes
    state = apply(state, Pass())  # deploying player passes → REGROUP
    from swu.engine.actions import SkipResource
    state = apply(state, SkipResource())
    state = apply(state, SkipResource())
    ps2 = state.players[state.active_player_index]
    acts = legal_actions(state)
    assert not any(isinstance(a, DeployLeader) for a in acts)


def test_defeated_leader_returns_to_base_zone():
    """Defeated deployed leader returns to base_zone, exhausted, cannot redeploy."""
    from swu.engine.state import Zone
    state = _make_minimal_state(seed=5)
    ps0 = state.players[0]
    ps1 = state.players[1]
    leader_ci = ps0.leader_instance

    # Forcibly deploy the leader
    ps0.base_zone.remove(leader_ci)
    leader_ci.deployed = True
    leader_ci.epic_action_spent = True
    leader_ci.exhausted = False
    leader_ci.zone = Zone.GROUND_ARENA
    ps0.ground_arena.append(leader_ci)
    # Make the leader easy to kill
    leader_ci.damage = leader_ci.effective_hp() - 1

    # Put a strong unit on P1's side
    killer = _make_unit_instance("killer", "P1", 99, 10)
    ps1.ground_arena = [killer]
    state.active_player_index = 1  # P1 goes

    state2 = apply(state, AttackWithUnit("killer", leader_ci.instance_id))
    ps0_after = state2.players[0]
    leader_after = ps0_after.leader_instance
    assert leader_after is not None
    assert not leader_after.deployed
    assert leader_after.zone == Zone.BASE_ZONE
    assert leader_after in ps0_after.base_zone
    assert leader_after.epic_action_spent  # cannot redeploy
    # Cannot deploy again
    state2.active_player_index = 0
    acts = legal_actions(state2)
    assert not any(isinstance(a, DeployLeader) for a in acts)


# ── Serialisation ─────────────────────────────────────────────────────────────

def test_state_serialisation_roundtrip(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    json_str = state.to_json()
    state2 = GameState.from_json(json_str)
    assert state2.phase == state.phase
    assert state2.round_number == state.round_number
    assert state2.initiative_holder == state.initiative_holder
    for i, ps in enumerate(state.players):
        ps2 = state2.players[i]
        assert ps2.player_id == ps.player_id
        assert len(ps2.hand) == len(ps.hand)
        assert len(ps2.deck) == len(ps.deck)
        assert len(ps2.resources) == len(ps.resources)


def test_player_view_serialisation(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    view = state.view_for("P0")
    json_str = view.to_json()
    import json
    d = json.loads(json_str)
    assert d["viewer_id"] == "P0"
    assert "my" in d
    assert "opponent" in d
    # Opponent hand cards should be hidden
    if d["opponent"]["hand"]:
        for c in d["opponent"]["hand"]:
            assert c["card_name"] == "[hidden]"
    # Own hand should be visible
    assert len(d["my"]["hand"]) == d["my"]["hand_count"]


def test_view_hides_opponent_hand(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    view = state.view_for("P0")
    # opponent's hand should be empty (hidden) in the view
    assert view.opponent.hand == []
    assert view.opponent.hand_count > 0  # but the count is correct


def test_own_resources_visible(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    view = state.view_for("P0")
    for r in view.my.resources:
        assert r.card_name != "[hidden]"


def test_opponent_resources_hidden(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    view = state.view_for("P0")
    for r in view.opponent.resources:
        assert r.card_name == "[hidden]"


# ── Card conservation invariant ───────────────────────────────────────────────

def _count_cards(state: GameState) -> dict:
    return {ps.player_id: len(state.all_instances_for_player(ps.player_id))
            for ps in state.players}


def test_card_conservation_across_game(deck_a, deck_b):
    """Total card count per player must stay constant."""
    state = make_game(deck_a, deck_b)
    initial_counts = _count_cards(state)
    for _ in range(100):
        if state.is_terminal():
            break
        acts = legal_actions(state)
        state = apply(state, acts[0])
    final_counts = _count_cards(state)
    for pid in initial_counts:
        assert final_counts[pid] == initial_counts[pid], (
            f"Card count changed for {pid}: {initial_counts[pid]} → {final_counts[pid]}"
        )
