"""Tests for ACTION phase mechanics."""
from __future__ import annotations

import pytest
from conftest import ensure_affordable, inject_into_hand, make_game, run_through_setup

from swu.engine.actions import (
    Pass, ClaimInitiative, PlayCard, IllegalActionError,
    legal_actions, apply,
)
from swu.engine.state import Phase
from swu.cards.models import Unit, Event


def test_pass_switches_active_player(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    first = state.active_player_index
    state2 = apply(state, Pass())
    assert state2.active_player_index == 1 - first


def test_both_pass_enters_regroup(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    state = apply(state, Pass())
    state = apply(state, Pass())
    assert state.phase == Phase.REGROUP


def test_pass_always_legal(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    acts = legal_actions(state)
    assert any(isinstance(a, Pass) for a in acts)


def test_claim_initiative_sets_holder(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    claimer_idx = state.active_player_index
    state2 = apply(state, ClaimInitiative())
    assert state2.initiative_holder == claimer_idx
    assert state2.initiative_claimed_this_round


def test_claim_initiative_counts_as_pass(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    state = apply(state, ClaimInitiative())
    state = apply(state, Pass())  # other player passes
    assert state.phase == Phase.REGROUP


def test_cannot_claim_initiative_twice(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    state = apply(state, ClaimInitiative())
    # Now other player's turn — they also should not see ClaimInitiative
    acts = legal_actions(state)
    assert not any(isinstance(a, ClaimInitiative) for a in acts)


def test_illegal_action_raises(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    from swu.engine.actions import KeepHand
    with pytest.raises(IllegalActionError):
        apply(state, KeepHand())


def test_play_unit_exhausts_resources(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    playable = ensure_affordable(state, Unit)

    from swu.engine.actions import _effective_cost
    cost = _effective_cost(playable.card_def, ps)
    avail_before = ps.available_resources
    state2 = apply(state, PlayCard(playable.instance_id))
    ps2 = state2.players[state.active_player_index]
    assert ps2.available_resources == avail_before - cost


def test_play_unit_enters_arena_exhausted(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    ci = ensure_affordable(state, Unit)
    arena_name = (ci.card_def.arenas or ("Ground",))[0]
    state2 = apply(state, PlayCard(ci.instance_id))
    ps2 = state2.players[state.active_player_index]
    arena = ps2.ground_arena if arena_name == "Ground" else ps2.space_arena
    played = next((u for u in arena if u.instance_id == ci.instance_id), None)
    assert played is not None, "Unit not in arena after play"
    assert played.exhausted, "Unit must enter play exhausted"


def test_cannot_play_card_without_enough_resources(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    ps = state.active_player
    # Exhaust all resources
    for r in ps.resources:
        r.exhausted = True
    acts = legal_actions(state)
    play_acts = [a for a in acts if isinstance(a, PlayCard)]
    assert not play_acts or all(
        False for a in play_acts
    ), "Should not be able to play with no resources"


def test_aspect_penalty_calculation():
    """Double aspect card costs +2 per missing aspect."""
    from swu.engine.actions import _effective_cost
    from swu.cards.models import AspectPip
    from swu.engine.state import PlayerState, CardInstance, Zone

    # Make a fake card with 2x Villainy aspects
    class FakeCard:
        id = 0
        aspects = (
            AspectPip(0, "Villainy", "red", False),
            AspectPip(1, "Villainy", "red", True),
        )
        arenas = ("Ground",)
        type = "Unit"
        display_name = "Test"
        cost = 4

    ps = PlayerState(player_id="test")
    # No aspects in base_zone → both Villainy pips unmatched → +4
    assert _effective_cost(FakeCard(), ps) == 8

    # Add one Villainy to base_zone via a fake base
    class FakeBase:
        aspects = (AspectPip(0, "Villainy", "red", False),)
        id = 1
        type = "Base"
        display_name = "TestBase"

    base_ci = CardInstance("b0", FakeBase(), "test", Zone.BASE_ZONE)
    ps.base_zone.append(base_ci)
    # Now 1 Villainy matched, 1 unmatched → +2
    assert _effective_cost(FakeCard(), ps) == 6

    # Add second Villainy
    class FakeLeader:
        aspects = (AspectPip(0, "Villainy", "red", False),)
        id = 2
        type = "Leader"
        display_name = "TestLeader"

    leader_ci = CardInstance("l0", FakeLeader(), "test", Zone.BASE_ZONE)
    ps.base_zone.append(leader_ci)
    # Both matched → no penalty
    assert _effective_cost(FakeCard(), ps) == 4


def test_play_event_goes_to_discard(deck_a, deck_b, repo):
    state = run_through_setup(make_game(deck_a, deck_b))
    idx = state.active_player_index
    # The vanilla decks are Units and Upgrades only (build_vanilla_deck fills them
    # from those two types), so the Event has to be injected — this test skipped
    # itself on every seed until that was noticed.  Cheapest Event, to keep the
    # resource arrangement small.
    events = [c for c in repo.all_of_type("Event") if isinstance(c, Event)]
    assert events, "no Event cards in the database at all"
    iid = inject_into_hand(state, min(events, key=lambda c: c.cost or 0)).instance_id
    state2 = apply(state, PlayCard(iid))
    ps2 = state2.players[idx]
    assert any(c.instance_id == iid for c in ps2.discard)
    assert not any(c.instance_id == iid for c in ps2.hand)


def test_switched_active_player_after_nonpass_action(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    first_idx = state.active_player_index
    # After any action, active player should switch
    state2 = apply(state, Pass())
    assert state2.active_player_index != first_idx


def test_regroup_draw_two(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    hand_sizes = {ps.player_id: len(ps.hand) for ps in state.players}
    # Force regroup
    state = apply(state, Pass())
    state = apply(state, Pass())
    assert state.phase == Phase.REGROUP
    for ps in state.players:
        assert len(ps.hand) == hand_sizes[ps.player_id] + 2


def test_regroup_optional_resource(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    state = apply(state, Pass())
    state = apply(state, Pass())
    from swu.engine.actions import SkipResource, ResourceCard
    acts = legal_actions(state)
    assert any(isinstance(a, SkipResource) for a in acts)
    assert any(isinstance(a, ResourceCard) for a in acts)


def test_regroup_ready_all(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    # Play a unit to exhaust it via combat / card play
    # Just exhaust resources directly to verify readying
    for ps in state.players:
        for r in ps.resources:
            r.exhausted = True
    state = apply(state, Pass())
    state = apply(state, Pass())
    # Skip resource for both players
    from swu.engine.actions import SkipResource
    state = apply(state, SkipResource())
    state = apply(state, SkipResource())
    assert state.phase == Phase.ACTION
    assert state.round_number == 2
    for ps in state.players:
        assert all(not r.exhausted for r in ps.resources)


def test_initiative_holder_goes_first_next_round(deck_a, deck_b):
    state = run_through_setup(make_game(deck_a, deck_b))
    claimer_idx = 1 - state.active_player_index  # non-initiative player claims
    # First initiative holder passes, then other claims
    state = apply(state, Pass())
    state = apply(state, ClaimInitiative())
    # Now in regroup, skip both
    from swu.engine.actions import SkipResource
    state = apply(state, SkipResource())
    state = apply(state, SkipResource())
    assert state.phase == Phase.ACTION
    assert state.initiative_holder == claimer_idx
    assert state.active_player_index == claimer_idx


def test_determinism(deck_a, deck_b):
    """Same seed + same actions => identical serialised state."""
    from swu.engine.actions import apply

    def replay(seed):
        s = make_game(deck_a, deck_b, seed=seed)
        for _ in range(20):
            if s.is_terminal():
                break
            acts = legal_actions(s)
            s = apply(s, acts[0])
        return s.to_json()

    assert replay(99) == replay(99)
    assert replay(99) != replay(100)
