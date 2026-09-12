"""Tests for game setup: mulligan, resources, initial state."""
from __future__ import annotations

from conftest import make_game, run_through_setup

from swu.engine.actions import (
    KeepHand, TakeMultiligan, ResourceCard, legal_actions, apply,
)
from swu.engine.state import Phase
from swu.engine.events import GameStarted


def test_initial_phase(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    assert state.phase == Phase.SETUP_MULLIGAN


def test_initial_hands(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    for ps in state.players:
        assert len(ps.hand) == 6


def test_decks_are_52_minus_hand(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    for ps in state.players:
        # 50 non-leader/base cards - 6 drawn = 44
        assert len(ps.deck) == 44


def test_leaders_and_bases_in_base_zone(deck_a, deck_b):
    from swu.cards.models import Leader, Base
    state = make_game(deck_a, deck_b)
    for ps in state.players:
        assert any(isinstance(ci.card_def, Leader) for ci in ps.base_zone)
        assert any(isinstance(ci.card_def, Base) for ci in ps.base_zone)
        assert len(ps.base_zone) == 2


def test_mulligan_legal_actions(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    acts = legal_actions(state)
    assert any(isinstance(a, KeepHand) for a in acts)
    assert any(isinstance(a, TakeMultiligan) for a in acts)
    assert len(acts) == 2


def test_keep_hand_advances_to_other_player(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    first_idx = state.active_player_index
    state2 = apply(state, KeepHand())
    assert state2.active_player_index != first_idx
    assert state2.mulligan_done[first_idx]


def test_both_keep_transitions_to_setup_resources(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    state = apply(state, KeepHand())
    state = apply(state, KeepHand())
    assert state.phase == Phase.SETUP_RESOURCES


def test_mulligan_redraws_six(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    state = apply(state, TakeMultiligan())
    ps = state.players[0]  # first player mulliganed
    assert len(ps.hand) == 6


def test_mulligan_event_logged(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    state = apply(state, TakeMultiligan())
    event_types = [type(e).__name__ for e in state.event_log]
    assert "MulliganTaken" in event_types


def test_immutability_of_apply(deck_a, deck_b):
    """apply() must not mutate the input state."""
    state = make_game(deck_a, deck_b)
    snapshot_hand_len = len(state.players[0].hand)
    snapshot_phase = state.phase
    _ = apply(state, KeepHand())
    assert len(state.players[0].hand) == snapshot_hand_len
    assert state.phase == snapshot_phase


def test_setup_resources_legal_actions(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    state = apply(state, KeepHand())
    state = apply(state, KeepHand())
    assert state.phase == Phase.SETUP_RESOURCES
    acts = legal_actions(state)
    assert all(isinstance(a, ResourceCard) for a in acts)
    # Each card in hand is a legal resource choice
    assert len(acts) == len(state.active_player.hand)


def test_two_resources_chosen_per_player(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    for ps in state.players:
        assert len(ps.resources) == 2
        assert all(ci.face_down for ci in ps.resources)


def test_action_phase_starts_with_initiative_holder(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    assert state.phase == Phase.ACTION
    assert state.active_player_index == state.initiative_holder


def test_leaders_not_exhausted_at_start(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    for ps in state.players:
        leader = ps.leader_instance
        assert leader is not None
        assert not leader.exhausted
        assert not leader.deployed


def test_game_started_event_logged(deck_a, deck_b):
    state = make_game(deck_a, deck_b)
    assert any(isinstance(e, GameStarted) for e in state.event_log)
