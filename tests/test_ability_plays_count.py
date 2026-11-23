"""Ability-driven plays are real plays (known-deviation fix, 2026-11-23).

Every play path must fire ``CardPlayed`` through the trigger system, not only the
keyword bus — that fire is what increments ``cards_played_this_phase`` /
``non_units_played_this_phase`` and runs every "when you play a card" observer.
Before the fix, play-from-hand, deck-search plays, Exploit / cost-route commits,
captured-card plays, resource-unit plays, owner replays and bounty replays all
fired only the bus, so none of them counted.

Each test plays an [Aggression] unit through one of those paths with Fighters for
Freedom (SOR_143, "When you play another [Aggression] card: You may deal 1 damage to
a base") in play, and checks both the counter and that the observer triggered.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _give_resources,
)
from tests.test_fortify import _unit_def, _to_hand
from tests.test_hmw_cards import _with_aspect, _resource_card


def _aggro_unit(name="Raider", number="71", cost=2):
    return dataclasses.replace(
        _with_aspect(_unit_def(name, number), "Aggression"), cost=cost)


def _setup(repo):
    state = _make_state()
    fighters = _place(state, "P0", _get_card(repo, "SOR", "143"))
    source = _place(state, "P0", _unit_def("Source", "72"))
    state.active_player_index = 0
    return state, fighters, source


def _played(state, pid="P0") -> int:
    return state.game_memory.cards_played_this_phase.get(pid, 0)


def _observer_fired(state, fighters) -> bool:
    """Fighters for Freedom's optional trigger is waiting on the stack."""
    return any(d.context.get("source_id") == fighters.instance_id
               for d in state.pending_decisions)


def test_play_from_hand_counts_as_a_play(repo):
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, fighters, source = _setup(repo)
    ci = _to_hand(state, "P0", _aggro_unit())
    push_play_from_hand(state, source, free=True)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert _played(state) == 1
    assert _observer_fired(state, fighters)


def test_deck_search_play_counts_as_a_play(repo):
    from swu.engine.actions import apply, legal_actions, push_deck_search
    from swu.engine.state import CardInstance, Zone
    state, fighters, source = _setup(repo)
    ci = CardInstance(instance_id="P0_deck_aggro", card_def=_aggro_unit(),
                      owner_id="P0", zone=Zone.DECK)
    state.players[0].deck.insert(0, ci)
    _give_resources(state, "P0", 5)
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
    assert _played(state) == 1
    assert _observer_fired(state, fighters)


def test_exploit_commit_counts_as_a_play(repo):
    from swu.engine.actions import apply, PlayCard, ExploitCommit
    state, fighters, _ = _setup(repo)
    exploit = dataclasses.replace(_aggro_unit("Exploiter", "73", cost=3),
                                  text="Exploit 1", keywords=("Exploit",))
    ci = _to_hand(state, "P0", exploit)
    _give_resources(state, "P0", 5)
    state = apply(state, PlayCard(ci.instance_id))
    assert state.pending_decisions[-1].kind == "exploit"
    state = apply(state, ExploitCommit())
    assert _played(state) == 1
    assert _observer_fired(state, fighters)


def test_play_resource_unit_counts_as_a_play(repo):
    from swu.engine.actions import apply, SelectResourceUnitToPlay
    from swu.engine.actions.hand import push_play_resource_units
    state, fighters, source = _setup(repo)
    res = _resource_card(state, "P0", _aggro_unit())
    push_play_resource_units(state, source)
    state = apply(state, SelectResourceUnitToPlay(res.instance_id))
    assert _played(state) == 1
    assert _observer_fired(state, fighters)


def test_owner_replay_counts_as_a_play(repo):
    from swu.engine.actions import apply, ReplayReturnedUnit
    from swu.engine.actions.targeting import push_owner_may_replay
    state, fighters, source = _setup(repo)
    ci = _to_hand(state, "P0", _aggro_unit())
    push_owner_may_replay(state, source, ci.instance_id)
    state = apply(state, ReplayReturnedUnit(ci.instance_id))
    assert _played(state) == 1
    assert _observer_fired(state, fighters)


def test_bounty_replay_counts_as_a_play_for_the_collector(repo):
    """Unrefusable Offer SHD_226: "Bounty — Play this unit for free (under your
    control)" — the collector played a card."""
    from swu.engine.actions import _defeat_unit
    from tests.test_shd_cards import _attach_bounty_upgrade
    state = _make_state()
    host = _place(state, "P1", _get_card(repo, "SOR", "46"))
    _attach_bounty_upgrade(state, host, _get_card(repo, "SHD", "226"), "P0")
    _defeat_unit(state, state.player_by_id("P1"), host)
    assert state.find_instance(host.instance_id)[1] in state.players[0].ground_arena
    assert _played(state, "P0") == 1
    assert _played(state, "P1") == 0


def test_ability_play_feeds_the_nth_unit_index(repo):
    """Origin Tree Shyyyo-style "Nth unit you play" reads cards_played − non-units
    played; an ability play must advance it like a hand play does."""
    from swu.engine.actions import apply, PlayFromHand, push_play_from_hand
    state, _, source = _setup(repo)
    for n in (1, 2):
        ci = _to_hand(state, "P0", _unit_def(f"U{n}", str(80 + n)))
        push_play_from_hand(state, source, free=True)
        state = apply(state, PlayFromHand(ci.instance_id))
    gm = state.game_memory
    assert (gm.cards_played_this_phase.get("P0", 0)
            - gm.non_units_played_this_phase.get("P0", 0)) == 2
