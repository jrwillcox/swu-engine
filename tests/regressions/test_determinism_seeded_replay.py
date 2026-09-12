"""Regression: non-deterministic games from non-seeded randomness.

Soak finding (10k campaign, determinism oracle): 30 games re-ran from the same
seed and produced a different result. Two independent root causes, both using
randomness OUTSIDE the game's seeded RNG (``state.make_rng()`` /
``state.rng_state``):

1. **Global ``random.shuffle``** (the gameplay fork). Grand Moff Tarkin
   (SOR_84) and Recruit (SOR_123) put the unsearched cards "on the bottom of
   the deck in a random order". The implementation built ``rng =
   state.make_rng()`` but then called the *global* ``random.shuffle(skipped)``
   and saved an *unadvanced* ``rng_state`` — so the deck reorder drew from
   Python's process-global RNG, diverging between two same-seed runs. Later
   draws then pulled different cards and the whole game forked (seed 1200:
   229 vs 231 actions).

2. **``uuid.uuid4()`` modifier ids** (serialization fork). ``_make_modifier`` /
   ``_make_kw_modifier`` and the SOR_130 / SOR_92 custom effects stamped
   ``modifier_id = uuid4()`` (drawn from os.urandom). A game that ended with a
   surviving modifier serialised a different id each run, so the determinism
   oracle's fingerprint (full state JSON) diverged even when winner and action
   count matched (seed 900).

Fixes: SOR_84/SOR_123 now call ``rng.shuffle``; all modifier ids come from the
new deterministic, serialised ``GameState.alloc_modifier_id()`` counter.

This test replays previously-failing seeds twice in one process and asserts an
identical fingerprint — exactly what the soak determinism oracle does.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.dbpath import require_db

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="module")
def repo():
    from swu.cards.repository import CardRepository
    return CardRepository(require_db())


def _starter(repo, name):
    from swu.cards.decklist import load_decklist
    return load_decklist(_FIXTURES / name, repo)


def _fingerprint(repo, seed: int):
    """Play a full random-vs-random starter game and return (winner, n, json)."""
    from swu.engine.actions import create_game, legal_actions, apply
    from swu.players.random_bot import RandomBot

    deck0 = _starter(repo, "starter_vader.json")
    deck1 = _starter(repo, "starter_luke.json")
    state = create_game("P0", deck0, "P1", deck1, seed=seed)
    bots = {"P0": RandomBot("P0", seed=seed), "P1": RandomBot("P1", seed=seed + 1)}
    n = 0
    while not state.is_terminal() and n < 2000:
        aid = state.active_player.player_id
        state = apply(state, bots[aid].choose_action(state.view_for(aid), legal_actions(state)))
        n += 1
    j = json.loads(state.to_json())
    j.pop("event_log", None)
    return state.winner, n, json.dumps(j, sort_keys=True)


# Seed 1200 forked in ACTION COUNT (the Tarkin/Recruit global-shuffle bug).
# Seed 1350 was a same-(winner,actions) divergence (the uuid modifier-id bug).
# Both were random/random on the starter decks in the failing campaign.
@pytest.mark.parametrize("seed", [1200, 1350, 5400])
def test_same_seed_game_is_deterministic(repo, seed):
    fp1 = _fingerprint(repo, seed)
    fp2 = _fingerprint(repo, seed)
    assert fp1 == fp2, (
        f"seed {seed} re-ran non-deterministically: "
        f"{fp1[:2]} vs {fp2[:2]}; json_equal={fp1[2] == fp2[2]}"
    )


def test_tarkin_deck_reorder_uses_seeded_rng(repo):
    """Grand Moff Tarkin's bottom-of-deck reorder must come from the seeded rng.

    Two states built with the same rng_state must reorder the skipped cards
    identically. (Pre-fix this used the global random module → divergent.)
    """
    import sqlite3
    from swu.engine.state import GameState, PlayerState, Phase, CardInstance, Zone
    from swu.abilities.registry import get_abilities
    from swu.abilities.resolver import execute_effect

    con = sqlite3.connect(require_db())
    con.row_factory = sqlite3.Row

    def card(num):
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?", ("SOR", num)
        ).fetchone()
        return repo._hydrate(con, row)

    try:
        tarkin = card("84")
        # Build a deck of >5 distinct non-Imperial cards so several get reordered.
        filler_nums = ["5", "53", "59", "74", "78", "84", "88", "92"]
        fillers = [card(n) for n in filler_nums]
    finally:
        con.close()

    def run_once():
        ps0 = PlayerState(player_id="P0")
        ps1 = PlayerState(player_id="P1")
        state = GameState(players=[ps0, ps1], phase=Phase.ACTION,
                          active_player_index=0, round_number=1, initiative_holder=0)
        # Fix the rng to a known state so both runs are comparable.
        import random as _r
        rng = _r.Random(12345)
        state.rng_state = rng.getstate()
        src = CardInstance(instance_id="P0_src", card_def=tarkin,
                           owner_id="P0", zone=Zone.GROUND_ARENA)
        ps0.ground_arena.append(src)
        for i, cd in enumerate(fillers):
            ci = CardInstance(instance_id=f"P0_d{i}", card_def=cd,
                              owner_id="P0", zone=Zone.DECK)
            ps0.deck.append(ci)
        spec = get_abilities("SOR", "84")[0]
        effect = spec.effects[0]
        state = execute_effect(state, effect, src, None, {})
        return [c.instance_id for c in ps0.deck]

    assert run_once() == run_once(), \
        "Tarkin deck reorder is non-deterministic (regression: global random.shuffle)"


def test_modifier_ids_are_deterministic(repo):
    """ModifyStats modifier ids must be deterministic counters, not uuid4."""
    import sqlite3
    from swu.engine.state import GameState, PlayerState, Phase, CardInstance, Zone
    from swu.abilities.registry import ModifyStats, TargetSpec, Duration, SELF
    from swu.abilities.resolver import execute_effect

    con = sqlite3.connect(require_db())
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?", ("SOR", "59")
        ).fetchone()
        unit_def = repo._hydrate(con, row)
    finally:
        con.close()

    def run_once():
        ps0 = PlayerState(player_id="P0")
        ps1 = PlayerState(player_id="P1")
        state = GameState(players=[ps0, ps1], phase=Phase.ACTION,
                          active_player_index=0, round_number=1, initiative_holder=0)
        src = CardInstance(instance_id="P0_u", card_def=unit_def,
                           owner_id="P0", zone=Zone.GROUND_ARENA)
        ps0.ground_arena.append(src)
        eff = ModifyStats(power=2, hp=0,
                          target=TargetSpec(fixed=SELF),
                          duration=Duration.THIS_ATTACK)
        state = execute_effect(state, eff, src, None, {})
        return [m.modifier_id for m in state.modifiers]

    ids1 = run_once()
    ids2 = run_once()
    assert ids1 and ids1 == ids2, f"modifier ids non-deterministic: {ids1} vs {ids2}"
    assert "uuid" not in ids1[0] and len(ids1[0]) < 40, \
        f"modifier id looks like a uuid, not a counter: {ids1[0]!r}"
