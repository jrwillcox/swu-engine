"""Cost modifiers apply to ability-driven plays (known-deviation fix, 2026-11-23).

Every paid play prices through ``costs._play_cost`` (the playing ability's own "it
costs N less" folded in as ``extra_reduction``) and spends what it used through
``costs._spend_play_discounts``.  Before the fix, play-from-hand and deck-search
plays paid a raw ``_effective_cost`` (no pending / standing discount, no opponent
tax, no halving), and Exploit / play-from-discard / upgrade-decision plays read the
discounts without ever spending them.

The probe is a pending "the next unit you play costs 2 less" entry — the
``NextPlayDiscount`` record Khetanna LAW_158 writes.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _make_state, _place, _give_resources,
)
from tests.test_fortify import _unit_def, _to_hand


def _costed(name="Raider", number="71", cost=3):
    return dataclasses.replace(_unit_def(name, number), cost=cost)


def _setup(resources=5):
    state = _make_state()
    source = _place(state, "P0", _unit_def("Source", "72"))
    _give_resources(state, "P0", resources)
    state.active_player_index = 0
    return state, source


def _pend_discount(state, amount=2):
    state.game_memory.pending_play_discounts.append(
        {"player_id": "P0", "trait": "", "units_only": True, "amount": amount})


def _spent(state) -> int:
    return sum(1 for r in state.players[0].resources if r.exhausted)


def test_play_from_hand_uses_and_spends_a_pending_discount(repo):
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, source = _setup()
    _pend_discount(state)
    ci = _to_hand(state, "P0", _costed(cost=3))
    push_play_from_hand(state, source)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert _spent(state) == 1                              # 3 − 2
    assert state.game_memory.pending_play_discounts == []  # spent


def test_play_from_hand_stacks_ability_reduction_with_discount(repo):
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, source = _setup()
    _pend_discount(state)
    ci = _to_hand(state, "P0", _costed(cost=5))
    push_play_from_hand(state, source, cost_reduction=1)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert _spent(state) == 2                              # 5 − 1 − 2


def test_discount_makes_an_otherwise_unaffordable_card_a_candidate(repo):
    from swu.engine.actions import legal_actions, push_play_from_hand, PlayFromHand
    state, source = _setup(resources=1)
    _pend_discount(state)
    ci = _to_hand(state, "P0", _costed(cost=3))
    push_play_from_hand(state, source)
    assert any(isinstance(a, PlayFromHand) and a.instance_id == ci.instance_id
               for a in legal_actions(state))


def test_free_play_leaves_the_discount_unspent(repo):
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, source = _setup()
    _pend_discount(state)
    ci = _to_hand(state, "P0", _costed(cost=3))
    push_play_from_hand(state, source, free=True)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert _spent(state) == 0
    assert len(state.game_memory.pending_play_discounts) == 1


def test_deck_search_play_uses_and_spends_a_pending_discount(repo):
    from swu.engine.actions import apply, legal_actions, push_deck_search
    from swu.engine.state import CardInstance, Zone
    state, source = _setup()
    _pend_discount(state)
    ci = CardInstance(instance_id="P0_deck_unit", card_def=_costed(cost=3),
                      owner_id="P0", zone=Zone.DECK)
    state.players[0].deck.insert(0, ci)
    push_deck_search(state, source, count=1, eligible=lambda cd: True, up_to=False,
                     window=1, disposition="play")
    for _ in range(5):
        if not any(d.kind == "deck_search" for d in state.pending_decisions):
            break
        acts = legal_actions(state)
        pick = next((a for a in acts
                     if getattr(a, "instance_id", None) == ci.instance_id), acts[0])
        state = apply(state, pick)
    assert state.find_instance(ci.instance_id)[1].zone == Zone.GROUND_ARENA
    assert _spent(state) == 1
    assert state.game_memory.pending_play_discounts == []


def test_exploit_play_spends_the_discount_it_used(repo):
    """An Exploit hand play read the pending discount but never spent it, so the
    same discount applied to every later play."""
    from swu.engine.actions import apply, PlayCard, ExploitCommit
    state, _ = _setup()
    _pend_discount(state)
    exploit = dataclasses.replace(_costed("Exploiter", "73", cost=4),
                                  text="Exploit 1", keywords=("Exploit",))
    ci = _to_hand(state, "P0", exploit)
    state = apply(state, PlayCard(ci.instance_id))
    assert state.pending_decisions[-1].kind == "exploit"
    state = apply(state, ExploitCommit())
    assert _spent(state) == 2                              # 4 − 2
    assert state.game_memory.pending_play_discounts == []


def test_opponent_tax_applies_to_an_ability_play(repo):
    """Moff Gideon JTL_188's "each unit that opponent plays this phase costs 1
    more" is a play tax — an ability play pays it too."""
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, source = _setup()
    state.game_memory.unit_play_tax_this_phase["P0"] = 1
    ci = _to_hand(state, "P0", _costed(cost=3))
    push_play_from_hand(state, source)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert _spent(state) == 4
