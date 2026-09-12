"""
Minimal CLI driver for playing/watching SWU games.

Usage:
    python -m swu.cli [--deck0 PATH] [--deck1 PATH] [--p0 human|random] [--p1 human|random] [--seed N]

Defaults to random vs random with generated vanilla decks from the DB.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the package is importable when run directly
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

from swu.cards.repository import CardRepository
from swu.cards.decklist import build_vanilla_deck, load_decklist, validate_decklist
from swu.engine.actions import create_game, legal_actions, apply


_DB_PATH = os.environ.get("SWU_DB", str(_repo_root / "swu-game" / "data" / "swu.db"))
if not Path(_DB_PATH).exists():
    _DB_PATH = str(Path(__file__).resolve().parents[3] / "data" / "swu.db")


def _render_event(event) -> str:
    t = type(event).__name__
    d = event.__dict__ if hasattr(event, "__dict__") else {}
    parts = ", ".join(f"{k}={v!r}" for k, v in d.items() if k != "player_ids")
    return f"[{t}] {parts}"


def _make_player(kind: str, player_id: str):
    if kind == "human":
        from swu.players.human import HumanPlayer
        return HumanPlayer(player_id)
    else:
        from swu.players.random_bot import RandomBot
        return RandomBot(player_id)


def run_game(
    deck0: list,
    deck1: list,
    player0_kind: str,
    player1_kind: str,
    seed: int | None,
    action_cap: int = 5000,
    verbose: bool = True,
) -> str:
    """Play one game to completion; return winner player_id."""
    p0_id, p1_id = "Player1", "Player2"
    p0 = _make_player(player0_kind, p0_id)
    p1 = _make_player(player1_kind, p1_id)
    players = {p0_id: p0, p1_id: p1}

    state = create_game(p0_id, deck0, p1_id, deck1, seed=seed)
    if verbose:
        print(f"\n=== New game  seed={seed} ===")

    prev_log_len = 0
    actions_taken = 0

    while not state.is_terminal() and actions_taken < action_cap:
        # Print new events
        if verbose:
            for ev in state.event_log[prev_log_len:]:
                print(_render_event(ev))
            prev_log_len = len(state.event_log)

        acts = legal_actions(state)
        active_id = state.active_player.player_id
        active_player = players[active_id]

        view = state.view_for(active_id)

        if player0_kind == "human" or player1_kind == "human":
            chosen = active_player.choose_action(view, acts)
        else:
            chosen = active_player.choose_action(view, acts)

        # Notify both players
        for pid, p in players.items():
            p.observe(state, chosen, active_id)

        state = apply(state, chosen)
        actions_taken += 1

    if verbose:
        for ev in state.event_log[prev_log_len:]:
            print(_render_event(ev))

    winner = state.winner
    if winner is None:
        winner = "TIMEOUT"
    if verbose:
        print(f"\n=== Game over: {winner} wins after {actions_taken} actions ===\n")
    return winner


def main() -> None:
    parser = argparse.ArgumentParser(description="Star Wars Unlimited CLI")
    parser.add_argument("--deck0", help="Path to SWUDB JSON decklist for player 1")
    parser.add_argument("--deck1", help="Path to SWUDB JSON decklist for player 2")
    parser.add_argument("--p0", default="human", choices=["human", "random"],
                        help="Player 1 type (default: human)")
    parser.add_argument("--p1", default="random", choices=["human", "random"],
                        help="Player 2 type (default: random)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    parser.add_argument("--db", default=None, help="Path to swu.db")
    args = parser.parse_args()

    db_path = args.db or _DB_PATH
    if not Path(db_path).exists():
        # Try common relative paths
        for candidate in ["data/swu.db", "../data/swu.db", "swu-game/data/swu.db"]:
            if Path(candidate).exists():
                db_path = candidate
                break
        else:
            print("ERROR: Cannot find swu.db. Set SWU_DB env var or use --db.", file=sys.stderr)
            sys.exit(1)

    repo = CardRepository(db_path)

    def load(path: str | None, player_idx: int) -> list:
        if path and Path(path).exists():
            cards = load_decklist(path, repo)
            errs = validate_decklist(cards)
            if errs:
                print(f"Decklist warnings: {errs}", file=sys.stderr)
            return cards
        # Generate vanilla deck
        print(f"No deck{player_idx} provided — generating vanilla deck…")
        leaders = [("Darth Vader", "Bright Hope"), ("Luke Skywalker", "Administrator's Tower")]
        name, base = leaders[player_idx % len(leaders)]
        try:
            return build_vanilla_deck(repo, name, base)
        except Exception as e:
            # Fallback: any leader + base
            all_leaders = repo.all_of_type("Leader")
            all_bases = repo.all_of_type("Base")
            from swu.cards.models import Leader, Base
            leader = next((c for c in all_leaders if isinstance(c, Leader)), None)
            base_card = next((c for c in all_bases if isinstance(c, Base)), None)
            if leader is None or base_card is None:
                raise RuntimeError("No leaders/bases in DB") from e
            return build_vanilla_deck(repo, leader.name, base_card.name)

    deck0 = load(args.deck0, 0)
    deck1 = load(args.deck1, 1)

    run_game(deck0, deck1, args.p0, args.p1, seed=args.seed)


if __name__ == "__main__":
    main()
