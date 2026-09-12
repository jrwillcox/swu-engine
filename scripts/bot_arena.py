"""
Bot arena — head-to-head strength measurement for heuristic bot changes.

Unlike ``bot_winrate.py`` (a 2-deck sanity check), this plays a *round-robin*
over the real precon deck fixtures with **paired seats**: every (deck pair,
seed) is played twice, once with A on each side, so seat and deck advantage
cancel exactly.  That makes a 2–3 point win-rate change meaningful instead of
noise.

Usage
-----
    python scripts/bot_arena.py --a heuristic --b heuristic --games 200
    python scripts/bot_arena.py --a heuristic --b baseline --games 400 --jobs 8

Selectable bots: ``heuristic`` / ``hard`` / ``easy`` (the live ones),
``easy:<rate>`` (an explicit mistake rate), ``w:<WEIGHT=value,...>`` (a weight
variant of the live heuristic — the form to use when comparing two candidate
tunings against each other), and ``baseline``/``baseline_easy``, the frozen
pre-tuning bot kept in ``benchmarks/heuristic_baseline.py``.
"""
from __future__ import annotations

import argparse
import itertools
import math
import multiprocessing
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

_DB = str(_ROOT / "data" / "swu.db")
_FX = _ROOT / "tests" / "fixtures"

# The deck pool: real, fully-encoded precon decks (excludes the two synthetic
# vanilla fixtures, which have no abilities and so measure nothing interesting).
DECKS = [
    "shd_han_solo", "sabine_mean_green", "the_mandalorian", "moff_gideon",
    "leia_organa", "ahsoka_tano", "general_grievous", "jabba_the_hutt",
    "boba_fett", "han_solo", "darth_maul", "qui_gon_jinn",
    "chancellor_palpatine", "padme_amidala", "emperor_palpatine",
    "luke_skywalker_ash",
]


def _apply_tuning() -> None:
    """Override HeuristicBot tuning constants from ``SWU_BOT_TUNE``.

    ``SWU_BOT_TUNE="W_ATTACK_BASE=6,BASE_RACE_URGENCY=1.5"`` patches the live
    heuristic module in each worker so a weight sweep needs no code edit.  The
    frozen baseline is loaded as a separate module and is never patched, so
    every tuned run is measured against the same fixed opponent and the numbers
    are comparable across the sweep.
    """
    import os
    spec = os.environ.get("SWU_BOT_TUNE", "").strip()
    if not spec:
        return
    from swu.players import heuristic_bot as hb
    for pair in spec.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        if not hasattr(hb, key):
            raise SystemExit(f"SWU_BOT_TUNE: no such constant {key!r}")
        setattr(hb, key, float(value))


def _parse_weights(spec: str) -> dict:
    """``"W_ATTACK_BASE=8,BASE_RACE_URGENCY=2"`` → ``{...}``."""
    out = {}
    for pair in spec.split(","):
        if not pair.strip():
            continue
        key, value = pair.split("=", 1)
        out[key.strip()] = float(value)
    return out


def _baseline_module():
    """The FROZEN pre-tuning heuristic, loaded from ``benchmarks/`` by path.

    It lives outside ``src/`` on purpose: it is a measurement artefact, not part
    of the game, and a second 1900-line near-copy of the bot sitting beside the
    real one in ``swu/players/`` is exactly the sort of thing that gets edited by
    accident.  Loading it by path also keeps it working in every multiprocessing
    worker without sys.path juggling.
    """
    import importlib.util
    global _BASELINE
    try:
        return _BASELINE
    except NameError:
        pass
    path = _ROOT / "benchmarks" / "heuristic_baseline.py"
    if not path.exists():
        raise SystemExit(
            f"no frozen baseline at {path} — 'baseline' needs it; compare two "
            f"live variants with the w:/easy: forms instead")
    spec = importlib.util.spec_from_file_location("swu_heuristic_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _BASELINE = module
    return module


def _make_bot(name: str, pid: str, seed: int):
    if name.startswith("w:"):
        # ``w:W_ATTACK_BASE=8,TRADE_SCALE=4`` — a weight variant.  Per-INSTANCE
        # weights (not module patching) so two differently-tuned bots can play
        # each other in one process; that head-to-head is the only honest test
        # that a weight change is better play rather than something the previous
        # bot merely loses to.
        from swu.players.heuristic_bot import HeuristicBot
        return HeuristicBot(pid, seed=seed, weights=_parse_weights(name[2:]))
    if name in ("heuristic", "normal"):
        from swu.players.heuristic_bot import HeuristicBot
        return HeuristicBot(pid, seed=seed)
    if name == "hard":
        from swu.players.heuristic_bot import HeuristicBot
        return HeuristicBot(pid, seed=seed, sharp_targeting=True)
    if name.startswith("easy:"):
        # ``easy:0.35`` — an explicit mistake rate, for tuning how beatable Easy is.
        from swu.players.heuristic_bot import HeuristicBot
        return HeuristicBot(pid, seed=seed, mistake_rate=float(name[5:]))
    if name == "easy":
        from swu.players.heuristic_bot import HeuristicBot
        from swu.players.difficulty import _EASY_MISTAKE_RATE
        return HeuristicBot(pid, seed=seed, mistake_rate=_EASY_MISTAKE_RATE)
    if name == "baseline":
        return _baseline_module().HeuristicBot(pid, seed=seed)
    if name == "baseline_easy":
        return _baseline_module().HeuristicBot(pid, seed=seed, mistake_rate=0.25)
    if name == "weighted":
        from swu.players.weighted_bot import WeightedBot
        return WeightedBot(pid, seed=seed)
    if name == "random":
        from swu.players.random_bot import RandomBot
        return RandomBot(pid, seed=seed)
    if name == "aggro":
        from swu.players.aggro_bot import AggroBot
        return AggroBot(pid, seed=seed)
    raise SystemExit(f"unknown bot: {name}")


def _run_pair(job: dict) -> dict:
    """Play ONE (deckA, deckB, seed) matchup four times: both seats x both decks.

    Returns {'a_wins': n, 'games': n, 'caps': n, 'errors': n, 'rounds': n}.
    """
    src = str(_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import load_decklist
    from swu.engine.actions import create_game, legal_actions, apply

    _apply_tuning()
    repo = CardRepository(_DB)
    d_a = load_decklist(_FX / f"{job['deck_a']}.json", repo)
    d_b = load_decklist(_FX / f"{job['deck_b']}.json", repo)
    seed = job["seed"]
    out = {"a_wins": 0, "games": 0, "caps": 0, "errors": 0, "rounds": 0}

    # Four games per job: A pilots each deck, from each seat.  Seat advantage AND
    # deck strength both cancel exactly, so the residual is bot skill.
    for a_deck, b_deck in ((d_a, d_b), (d_b, d_a)):
      for a_is_p0 in (True, False):
        a_id, b_id = ("P0", "P1") if a_is_p0 else ("P1", "P0")
        d0, d1 = (a_deck, b_deck) if a_is_p0 else (b_deck, a_deck)
        try:
            state = create_game("P0", d0, "P1", d1, seed=seed)
            bots = {a_id: _make_bot(job["a"], a_id, seed),
                    b_id: _make_bot(job["b"], b_id, seed + 7919)}
            n = 0
            while not state.is_terminal() and n < job["cap"]:
                pid = (state.pending_decisions[-1].deciding_player_id
                       if state.pending_decisions else state.active_player.player_id)
                chosen = bots[pid].choose_action(state.view_for(pid),
                                                 legal_actions(state))
                state = apply(state, chosen)
                n += 1
            if not state.is_terminal():
                out["caps"] += 1
                continue
            out["games"] += 1
            out["rounds"] += state.round_number
            if state.winner == a_id:
                out["a_wins"] += 1
        except Exception as exc:  # a crash is a real finding — surface it
            out["errors"] += 1
            out["error_msg"] = f"{type(exc).__name__}: {exc}"
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--a", default="heuristic")
    p.add_argument("--b", default="baseline")
    p.add_argument("--games", type=int, default=200,
                   help="approximate total games (each job plays 4: 2 seats x 2 decks)")
    p.add_argument("--jobs", type=int, default=max(1, (multiprocessing.cpu_count() or 4)))
    p.add_argument("--cap", type=int, default=3000)
    p.add_argument("--seed-start", type=int, default=4000)
    p.add_argument("--decks", default="", help="comma-separated deck subset")
    args = p.parse_args(argv)

    decks = [d.strip() for d in args.decks.split(",") if d.strip()] or DECKS
    pairs = [(x, y) for x, y in itertools.product(decks, decks) if x != y]
    rng = random.Random(12345)
    rng.shuffle(pairs)

    n_pairs = max(1, args.games // 4)
    jobs = []
    for i in range(n_pairs):
        da, db = pairs[i % len(pairs)]
        jobs.append({"deck_a": da, "deck_b": db, "seed": args.seed_start + i,
                     "a": args.a, "b": args.b, "cap": args.cap})

    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            results = pool.map(_run_pair, jobs)
    else:
        results = [_run_pair(j) for j in jobs]

    wins = sum(r["a_wins"] for r in results)
    games = sum(r["games"] for r in results)
    caps = sum(r["caps"] for r in results)
    errors = sum(r["errors"] for r in results)
    rounds = sum(r["rounds"] for r in results)
    pct = 100.0 * wins / max(1, games)
    # Binomial standard error on the win rate (paired seats, so this is honest).
    se = 100.0 * math.sqrt(max(pct / 100.0 * (1 - pct / 100.0), 1e-9) / max(1, games))
    print(f"{args.a} vs {args.b}: {wins}/{games} = {pct:.1f}%  (±{1.96*se:.1f} @95%)")
    print(f"  avg rounds {rounds / max(1, games):.1f}   caps {caps}   errors {errors}")
    for r in results:
        if r.get("error_msg"):
            print("  ERROR:", r["error_msg"])
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
