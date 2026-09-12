"""
Bot win-rate sanity harness (Phase 6A).

Plays seeded games between two bot builders across the SOR starter decks,
alternating which seat each bot occupies to cancel first-player advantage, and
reports the first builder's win rate.  Used to sanity-check that:

  * the HeuristicBot beats the WeightedBot comfortably, and
  * Hard beats Easy clearly.

Usage:
    python scripts/bot_winrate.py [--games N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))


def _decks(repo):
    from swu.cards.decklist import load_decklist
    fx = _ROOT / "tests" / "fixtures"
    return (
        load_decklist(fx / "starter_vader.json", repo),
        load_decklist(fx / "starter_luke.json", repo),
    )


def _play(make_a, make_b, deck_a, deck_b, seed, a_is_p0, cap=3000):
    """Play one game; return True if builder A won."""
    from swu.engine.actions import create_game, legal_actions, apply
    a_id, b_id = ("P0", "P1") if a_is_p0 else ("P1", "P0")
    d0, d1 = (deck_a, deck_b) if a_is_p0 else (deck_b, deck_a)
    state = create_game("P0", d0, "P1", d1, seed=seed)
    bots = {
        a_id: make_a(a_id, seed),
        b_id: make_b(b_id, seed + 1),
    }
    n = 0
    while not state.is_terminal() and n < cap:
        pid = (state.pending_decisions[-1].deciding_player_id
               if state.pending_decisions else state.active_player.player_id)
        chosen = bots[pid].choose_action(state.view_for(pid), legal_actions(state))
        state = apply(state, chosen)
        n += 1
    return state.winner == a_id


def matchup(make_a, make_b, label, games):
    from swu.cards.repository import CardRepository
    repo = CardRepository(str(_ROOT / "data" / "swu.db"))
    deck_vader, deck_luke = _decks(repo)
    a_wins = decided = 0
    for i in range(games):
        # Alternate seat AND deck so neither bot is glued to one side/deck.
        a_is_p0 = (i % 2 == 0)
        deck_a, deck_b = (deck_vader, deck_luke) if (i % 4 < 2) else (deck_luke, deck_vader)
        won = _play(make_a, make_b, deck_a, deck_b, seed=1000 + i, a_is_p0=a_is_p0)
        decided += 1
        a_wins += int(won)
    pct = 100 * a_wins / max(1, decided)
    print(f"{label}: {a_wins}/{decided} = {pct:.1f}% for the first bot")
    return pct


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=200)
    args = p.parse_args(argv)

    from swu.players.heuristic_bot import HeuristicBot
    from swu.players.weighted_bot import WeightedBot
    from swu.players.difficulty import Difficulty, make_opponent

    heuristic = lambda pid, seed: HeuristicBot(pid, seed=seed)
    weighted = lambda pid, seed: WeightedBot(pid, seed=seed)
    easy = lambda pid, seed: make_opponent(Difficulty.EASY, player_id=pid, seed=seed)
    hard = lambda pid, seed: make_opponent(Difficulty.HARD, player_id=pid, seed=seed)
    normal = lambda pid, seed: make_opponent(Difficulty.NORMAL, player_id=pid, seed=seed)

    print(f"Games per matchup: {args.games}\n")
    matchup(heuristic, weighted, "Heuristic vs WeightedBot", args.games)
    matchup(hard, easy, "Hard vs Easy", args.games)
    matchup(normal, easy, "Normal vs Easy", args.games)
    matchup(hard, normal, "Hard vs Normal", args.games)


if __name__ == "__main__":
    main()
