"""Choices made in the middle of an ability (known deviation fixed 2026-11-25).

An ability's effects resolve in printed order.  When one effect pushes a choice
(a discard of choice, a deck search, a token pick …), the effects after it wait
for that choice: the resolver parks them in a ``resolve_effects`` decision just
below the choice and resumes once it is answered.  Before, they ran straight
away, ahead of the choice.

Also covered: a target picked for an effect that has automatic effects printed
before it is no longer lost (the player was asked twice).

The abilities here are synthetic, installed on a real card's registry key for the
duration of one test, so the tests pin the resolver rather than any one card.
"""
from __future__ import annotations

import pytest

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _push_deck_top,
)
from tests.test_shd_cards import _put_in_hand

KEY = ("SOR", "46")


def _legal(state):
    from swu.engine.actions import legal_actions
    return legal_actions(state)


def _apply(state, act):
    from swu.engine.actions import apply
    return apply(state, act)


@pytest.fixture
def install(monkeypatch):
    """Install a synthetic ability list on ``KEY`` for one test."""
    from swu.abilities import registry as R

    def _install(*specs):
        monkeypatch.setitem(R._REGISTRY, KEY, list(specs))
    return _install


def _discard_choice(state, source_ci, target_id, event_ctx):
    """CustomEffect: the controller discards a card of their choice."""
    from swu.engine.actions.discard import push_discard_of_choice
    push_discard_of_choice(state, "P0", 1, source_id=source_ci.instance_id,
                           after_idx=1)
    return state


def _setup(repo):
    state = _make_state()
    src = _place(state, "P0", _get_card(repo, "SOR", "46"))
    for _ in range(2):
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
    for _ in range(3):
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
    return state, src


def test_inline_ability_waits_for_a_mid_ability_choice(repo, install):
    """[discard a card of your choice, then draw a card]: the draw comes after
    the discard choice, and play passes as the choice said once it finishes."""
    from swu.abilities import registry as R
    from swu.abilities.resolver import _resolve_inline
    from swu.engine.actions import SelectExcessHandCardToDiscard
    install(R.TriggerAbility(trigger=None, effects=[
        R.CustomEffect(fn=_discard_choice), R.DrawCards(1)]))
    state, src = _setup(repo)
    p0 = state.player_by_id("P0")
    hand_before = len(p0.hand)
    ability = R._REGISTRY[KEY][0]
    state = _resolve_inline(state, ability, src, {}, resume={
        "set_code": KEY[0], "card_number": KEY[1], "ability_idx": 0,
        "decider_id": "P0"})

    kinds = [d.kind for d in state.pending_decisions]
    assert kinds == ["resolve_effects", "discard_excess_from_hand"]
    assert len(p0.hand) == hand_before, "the draw waits for the discard"

    pick = next(a for a in _legal(state)
                if isinstance(a, SelectExcessHandCardToDiscard))
    state = _apply(state, pick)
    # Only automatic effects remain: the lone AutoResolveEffects.
    from swu.engine.actions import AutoResolveEffects
    acts = _legal(state)
    assert len(acts) == 1 and isinstance(acts[0], AutoResolveEffects)
    state = _apply(state, acts[0])
    p0 = state.player_by_id("P0")
    assert len(p0.hand) == hand_before            # −1 discarded, +1 drawn
    assert not state.pending_decisions
    assert state.active_player_index == 1         # the choice's hand-off


def test_resolve_effects_decision_waits_for_a_mid_ability_choice(repo, install):
    """The decision path: [deal 1 damage to an enemy unit (chosen), discard of
    choice, draw] — the draw waits for the discard, then resumes."""
    from swu.abilities import registry as R
    from swu.engine.actions import (
        AutoResolveEffects, ChooseTarget, SelectExcessHandCardToDiscard)
    from swu.engine.decisions import PendingDecision
    install(R.TriggerAbility(trigger=None, effects=[
        R.DealDamage(1, R.TargetSpec(controller="enemy", kind="unit")),
        R.CustomEffect(fn=_discard_choice),
        R.DrawCards(1)]))
    state, src = _setup(repo)
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    hand_before = len(state.player_by_id("P0").hand)
    state.pending_decisions.append(PendingDecision(
        deciding_player_id="P0", kind="resolve_effects",
        context={"set_code": KEY[0], "card_number": KEY[1], "ability_idx": 0,
                 "source_id": src.instance_id, "effect_idx": 0,
                 "resolved_targets": {}, "event_ctx": {},
                 "after_all_player_idx": 1},
        after_resolve_player_index=1))

    state = _apply(state, ChooseTarget(enemy.instance_id))
    assert state.find_instance(enemy.instance_id)[1].damage == 1
    assert state.pending_decisions[-1].kind == "discard_excess_from_hand"
    assert len(state.player_by_id("P0").hand) == hand_before, "no draw yet"

    pick = next(a for a in _legal(state)
                if isinstance(a, SelectExcessHandCardToDiscard))
    state = _apply(state, pick)
    acts = _legal(state)
    assert len(acts) == 1 and isinstance(acts[0], AutoResolveEffects)
    state = _apply(state, acts[0])
    assert len(state.player_by_id("P0").hand) == hand_before
    assert not state.pending_decisions


def test_target_pick_behind_an_automatic_effect_is_kept(repo, install):
    """[draw, deal 1 damage to an enemy unit (chosen)]: the offered pick lands
    (it used to be dropped and asked again)."""
    from swu.abilities import registry as R
    from swu.engine.actions import ChooseTarget
    from swu.engine.decisions import PendingDecision
    install(R.TriggerAbility(trigger=None, effects=[
        R.DrawCards(1),
        R.DealDamage(1, R.TargetSpec(controller="enemy", kind="unit"))]))
    state, src = _setup(repo)
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    hand_before = len(state.player_by_id("P0").hand)
    state.pending_decisions.append(PendingDecision(
        deciding_player_id="P0", kind="resolve_effects",
        context={"set_code": KEY[0], "card_number": KEY[1], "ability_idx": 0,
                 "source_id": src.instance_id, "effect_idx": 0,
                 "resolved_targets": {}, "event_ctx": {},
                 "after_all_player_idx": 1},
        after_resolve_player_index=1))
    assert [a.target_id for a in _legal(state)
            if isinstance(a, ChooseTarget)] == [enemy.instance_id]
    state = _apply(state, ChooseTarget(enemy.instance_id))
    assert state.find_instance(enemy.instance_id)[1].damage == 1
    assert len(state.player_by_id("P0").hand) == hand_before + 1
    assert not state.pending_decisions
