"""Friendly/enemy by CONTROL, and control/captives revert on any leave-play
(known-deviation fix 4, 2026-11-23).

Control is implicit (a unit belongs to whichever arena holds it; ``owner_id`` never
changes).  The resolver used to judge "friendly"/"enemy" — and whose board an
ability reads, who draws, who makes tokens — by ``owner_id``, so a stolen unit was
an enemy of its thief.  And a source that stole a unit (Maul LAW_54) or captured
cards released them only when DEFEATED, not when bounced / put on a deck / captured.
"""
from __future__ import annotations

from tests.test_sor_cards import repo, _make_state, _place  # noqa: F401
from tests.test_fortify import _unit_def, _deck


def _stolen_board():
    """P0 controls ``mine`` and ``stolen`` (owned by P1); P1 controls ``theirs``."""
    from swu.engine.actions import change_control
    state = _make_state()
    mine = _place(state, "P0", _unit_def("Mine", "70"))
    theirs = _place(state, "P1", _unit_def("Theirs", "71"))
    stolen = _place(state, "P1", _unit_def("Stolen", "72"))
    change_control(state, stolen, "P0")
    assert stolen.owner_id == "P1"
    return state, mine, theirs, stolen


def _targets(state, source, controller):
    from swu.abilities.registry import TargetSpec
    from swu.abilities.resolver import _gather_legal_targets
    return set(_gather_legal_targets(
        state, TargetSpec(controller=controller, kind="unit"), source, {}))


def test_a_stolen_unit_is_friendly_to_its_thief(repo):
    state, mine, theirs, stolen = _stolen_board()
    assert _targets(state, mine, "friendly") == {mine.instance_id, stolen.instance_id}
    assert _targets(state, mine, "enemy") == {theirs.instance_id}


def test_a_stolen_unit_is_an_enemy_of_its_owner(repo):
    state, mine, theirs, stolen = _stolen_board()
    assert _targets(state, theirs, "enemy") == {mine.instance_id, stolen.instance_id}
    assert _targets(state, theirs, "friendly") == {theirs.instance_id}


def test_a_stolen_units_ability_acts_for_its_thief(repo):
    from swu.abilities.registry import DrawCards
    from swu.abilities.resolver import execute_effect
    state, _, _, stolen = _stolen_board()
    _deck(state, "P0", 2)
    _deck(state, "P1", 2)
    state = execute_effect(state, DrawCards(1), stolen, None, {})
    assert len(state.player_by_id("P0").hand) == 1
    assert len(state.player_by_id("P1").hand) == 0


def test_a_stolen_units_condition_reads_its_thiefs_board(repo):
    from swu.abilities.registry import Condition, ConditionCheck
    state, _, _, stolen = _stolen_board()
    # P0 controls 2 units (mine + stolen); P1 controls 1.  From the owner's (P1's)
    # board this would be false.
    check = ConditionCheck(Condition.CONTROLLER_MORE_UNITS_THAN_OPPONENT)
    assert check.evaluate(state, stolen)


def test_bouncing_the_thief_reverts_linked_control(repo):
    """Maul LAW_54: "When this unit leaves play, that unit's owner takes control"
    — leaving play by bounce, not only by defeat."""
    from swu.abilities.resolver import _apply_return_to_hand
    state, mine, _, stolen = _stolen_board()
    stolen.control_linked_to = mine.instance_id
    state = _apply_return_to_hand(state, mine.instance_id)
    p1 = state.player_by_id("P1")
    assert stolen.instance_id in {u.instance_id for u in p1.ground_arena}
    assert stolen.control_linked_to is None


def test_putting_the_thief_on_a_deck_reverts_linked_control(repo):
    from swu.engine.actions.zones import _apply_put_on_deck
    state, mine, _, stolen = _stolen_board()
    stolen.control_linked_to = mine.instance_id
    state = _apply_put_on_deck(state, mine.instance_id, to_top=True)
    assert stolen.instance_id in {
        u.instance_id for u in state.player_by_id("P1").ground_arena}


def test_bouncing_a_captor_releases_its_captives(repo):
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.engine.actions.zones import _apply_capture
    state = _make_state()
    captor = _place(state, "P0", _unit_def("Captor", "70"))
    prey = _place(state, "P1", _unit_def("Prey", "71"))
    state = _apply_capture(state, captor.instance_id, prey.instance_id)
    assert prey.instance_id in {c.instance_id for c in state.player_by_id("P0").capture_pile}
    state = _apply_return_to_hand(state, captor.instance_id)
    assert prey.instance_id in {
        u.instance_id for u in state.player_by_id("P1").ground_arena}
    assert not state.player_by_id("P0").capture_pile
