"""The discarding player chooses which card (known-deviation fix 3, 2026-11-23).

"An opponent discards a card" / "Discard a card from your hand" used to discard
the FIRST card in hand with no choice (``DiscardFromHand``, K-2SO SOR_145's and Poe
SHD_153's modal discards).  They now push ``discard_excess_from_hand`` for the
discarding player via ``push_discard_of_choice`` — no prompt when there is no
choice.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import repo, _make_state, _place  # noqa: F401
from tests.test_fortify import _unit_def, _to_hand


def _card(name, number, cost=2):
    return dataclasses.replace(_unit_def(name, number), cost=cost)


def _run(state, effect):
    from swu.abilities.resolver import execute_effect
    src = state.player_by_id("P0").ground_arena[0]
    return execute_effect(state, effect, src, None, {})


def _setup():
    state = _make_state()
    _place(state, "P0", _unit_def("Source", "70"))
    state.active_player_index = 0
    return state


def _offered(state):
    from swu.engine.actions import legal_actions
    return {getattr(a, "instance_id", None) for a in legal_actions(state)}


def test_opponent_chooses_which_card_to_discard(repo):
    from swu.abilities.registry import DiscardFromHand
    from swu.engine.actions import apply, SelectExcessHandCardToDiscard
    state = _setup()
    first = _to_hand(state, "P1", _card("First", "71"))
    second = _to_hand(state, "P1", _card("Second", "72"))
    state = _run(state, DiscardFromHand(1, chooser="opponent"))
    top = state.pending_decisions[-1]
    assert top.kind == "discard_excess_from_hand" and top.deciding_player_id == "P1"
    assert _offered(state) == {first.instance_id, second.instance_id}
    state = apply(state, SelectExcessHandCardToDiscard(second.instance_id))
    p1 = state.player_by_id("P1")
    assert [c.instance_id for c in p1.hand] == [first.instance_id]
    assert [c.instance_id for c in p1.discard] == [second.instance_id]
    assert not state.pending_decisions


def test_no_prompt_when_the_whole_hand_goes(repo):
    from swu.abilities.registry import DiscardFromHand
    state = _setup()
    _to_hand(state, "P1", _card("Only", "71"))
    state = _run(state, DiscardFromHand(2, chooser="opponent"))
    assert not state.pending_decisions
    assert not state.player_by_id("P1").hand
    assert len(state.player_by_id("P1").discard) == 1


def test_empty_hand_is_a_clean_no_op(repo):
    from swu.abilities.registry import DiscardFromHand
    state = _setup()
    state = _run(state, DiscardFromHand(1, chooser="opponent"))
    assert not state.pending_decisions


def test_then_draw_happens_after_the_choice(repo):
    """Furtive Handmaiden SEC_197: "discard a card, if you do, draw a card" — the
    drawn card is not among the discard options."""
    from swu.abilities.registry import DiscardFromHand
    from swu.engine.state import CardInstance, Zone
    state = _setup()
    a = _to_hand(state, "P0", _card("A", "71"))
    b = _to_hand(state, "P0", _card("B", "72"))
    top = CardInstance(instance_id="P0_top", card_def=_card("Top", "73"),
                       owner_id="P0", zone=Zone.DECK)
    state.player_by_id("P0").deck.insert(0, top)
    state = _run(state, DiscardFromHand(1, chooser="controller", then_draw=1))
    assert _offered(state) == {a.instance_id, b.instance_id}
    from swu.engine.actions import apply, SelectExcessHandCardToDiscard
    state = apply(state, SelectExcessHandCardToDiscard(a.instance_id))
    hand = {c.instance_id for c in state.player_by_id("P0").hand}
    assert hand == {b.instance_id, top.instance_id}


def test_k2so_discard_mode_lets_the_opponent_choose(repo):
    from swu.engine.actions import apply, push_modal, ChooseModalOption
    state = _setup()
    src = state.player_by_id("P0").ground_arena[0]
    _to_hand(state, "P1", _card("First", "71"))
    second = _to_hand(state, "P1", _card("Second", "72"))
    push_modal(state, src, ["kaytoo_damage_base", "kaytoo_discard"])
    state = apply(state, ChooseModalOption("kaytoo_discard"))
    top = state.pending_decisions[-1]
    assert top.kind == "discard_excess_from_hand" and top.deciding_player_id == "P1"
    assert second.instance_id in _offered(state)


def test_bot_discards_its_least_valuable_card(repo):
    from swu.abilities.registry import DiscardFromHand
    from swu.engine.actions import legal_actions
    from swu.players.heuristic_bot import HeuristicBot
    state = _setup()
    _to_hand(state, "P1", _card("Cheap unit", "71", cost=2))
    pricey = _to_hand(state, "P1", _card("Expensive unit", "72", cost=8))
    state = _run(state, DiscardFromHand(1, chooser="opponent"))
    pick = HeuristicBot("P1", seed=0).choose_action(state.view_for("P1"),
                                                     legal_actions(state))
    assert getattr(pick, "instance_id", None) == pricey.instance_id
