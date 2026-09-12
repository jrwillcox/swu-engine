"""
Regression: GameMemory set fields serialized as unsorted lists produced
non-deterministic JSON (set iteration order is hash-dependent).  Fixed by
sorting all set-valued fields in GameMemory.to_dict() and _state_to_dict().

This test verifies that the to_json() / from_json() roundtrip is stable
regardless of the order in which instance_ids were added to the sets.
"""
from __future__ import annotations


def test_gamememory_to_dict_is_sorted():
    from swu.engine.state import GameMemory
    gm = GameMemory()
    # Add items in an order that (in CPython) produces a non-sorted list
    # when naively calling list(set)
    for iid in ["P1_98", "P1_66", "P1_69", "P0_5"]:
        gm.units_played_this_phase.add(iid)
    for iid in ["P1_96", "P0_0", "P1_62"]:
        gm.units_defeated_this_round.add(iid)

    d = gm.to_dict()
    assert d["units_played_this_phase"] == sorted(d["units_played_this_phase"])
    assert d["units_defeated_this_round"] == sorted(d["units_defeated_this_round"])


def test_gamememory_roundtrip_is_stable():
    from swu.engine.state import GameMemory
    gm = GameMemory()
    for iid in ["P1_98", "P1_66", "P1_69", "P0_5"]:
        gm.units_played_this_phase.add(iid)
    gm.villainy_players_this_phase.add("P0")

    d1 = gm.to_dict()
    gm2 = GameMemory.from_dict(d1)
    d2 = gm2.to_dict()
    assert d1 == d2, f"Round-trip mismatch: {d1} != {d2}"


def test_passed_players_serialization_is_sorted():
    """passed_players set in GameState serializes as sorted list."""
    import json
    from swu.engine.state import GameState, PlayerState

    # Create a minimal GameState with both players in passed_players
    ps0 = PlayerState(player_id="P0")
    ps1 = PlayerState(player_id="P1")
    gs = GameState(players=[ps0, ps1])
    gs.passed_players = {1, 0}  # deliberately out of order

    d = json.loads(gs.to_json())
    assert d["passed_players"] == sorted(d["passed_players"])
