"""Seeded-game trace fingerprints: the behavioural oracle for the actions split.

``scripts/refactor_parity.py`` proves that Phase A moved code without editing it.
It cannot prove anything about Phase B (which rewrites imports) or Phase C (which
changes decision dispatch), and it cannot catch a moved function whose *globals*
now resolve differently.  This script covers that gap from the other direction:
play a fixed set of seeded games, fingerprint everything the engine did, and
require the fingerprints to be identical afterwards.

A refactor that preserves behaviour cannot change a seeded game's event log.  If
one changes, the seed that changed *is* the reproduction case.

What is fingerprinted
---------------------
Per seed: the winner, the number of actions applied, a SHA-256 of the full
serialised end state (sorted keys), and a SHA-256 of the event log rendered as
``type|sorted-field-values`` lines.  The event log is the sensitive half — it
records the engine's decisions in order, so a reordered observer pipeline or a
changed dispatch shows up there even when the final board is identical.

Usage
-----
    python scripts/trace_oracle.py --write      # record the baseline
    python scripts/trace_oracle.py --check      # compare against it
    python scripts/trace_oracle.py --check --seeds 40   # wider, slower sweep

``--write`` refuses to overwrite an existing baseline unless ``--force`` is given:
re-recording a baseline is how a refactor silently blesses its own regression.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "actions_trace_baseline.json"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

# Seeds 1200 / 1350 / 5400 are the three that previously caught real
# non-determinism bugs (see tests/regressions/test_determinism_seeded_replay.py),
# so they lead the list; the rest are an arbitrary but fixed spread.
SEEDS = [1200, 1350, 5400, 1, 2, 3, 7, 11, 42, 99,
         101, 256, 512, 777, 900, 1024, 2048, 3141, 4096, 9001]

ACTION_CAP = 2000


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _render_event(ev) -> str:
    """One event as a stable line: class name plus its field values, sorted.

    Events are dataclasses; ``repr`` would embed object identities, so fields are
    rendered by name.  Values that are themselves objects fall back to ``repr``,
    which is stable for the card/instance types used here (they are dataclasses
    with value semantics).
    """
    name = type(ev).__name__
    if dataclasses.is_dataclass(ev):
        parts = [f"{f.name}={getattr(ev, f.name)!r}" for f in sorted(
            dataclasses.fields(ev), key=lambda f: f.name)]
    else:
        parts = [repr(ev)]
    return f"{name}|{'|'.join(parts)}"


def fingerprint(repo, seed: int) -> dict:
    from swu.cards.decklist import load_decklist
    from swu.engine.actions import apply, create_game, legal_actions
    from swu.players.random_bot import RandomBot

    deck0 = load_decklist(FIXTURES / "starter_vader.json", repo)
    deck1 = load_decklist(FIXTURES / "starter_luke.json", repo)
    state = create_game("P0", deck0, "P1", deck1, seed=seed)
    bots = {"P0": RandomBot("P0", seed=seed), "P1": RandomBot("P1", seed=seed + 1)}

    n = 0
    while not state.is_terminal() and n < ACTION_CAP:
        pid = state.active_player.player_id
        chosen = bots[pid].choose_action(state.view_for(pid), legal_actions(state))
        state = apply(state, chosen)
        n += 1

    blob = json.loads(state.to_json())
    events = blob.pop("event_log", None)
    if events is None:
        # The log lives on the state object rather than the serialised form.
        events = [_render_event(e) for e in getattr(state, "event_log", [])]
    else:
        events = [json.dumps(e, sort_keys=True) for e in events]

    return {
        "winner": state.winner,
        "actions": n,
        "state": _digest(json.dumps(blob, sort_keys=True)),
        "events": _digest("\n".join(events)),
        "event_count": len(events),
    }


def build(seed_count: int, verify_determinism: bool) -> dict:
    from swu.cards.repository import CardRepository
    from tests.dbpath import db_path

    db = db_path()
    if not db.exists():
        sys.exit(f"no card database at {db} - build it per docs/pipeline.md")
    repo = CardRepository(db)

    seeds = SEEDS[:seed_count]
    out = {}
    for i, seed in enumerate(seeds, 1):
        fp = fingerprint(repo, seed)
        if verify_determinism:
            again = fingerprint(repo, seed)
            if again != fp:
                sys.exit(
                    f"seed {seed} is not reproducible IN THIS BUILD, so it cannot "
                    f"serve as an oracle:\n  {fp}\n  {again}"
                )
        out[str(seed)] = fp
        print(f"  [{i}/{len(seeds)}] seed {seed}: {fp['actions']} actions, "
              f"winner={fp['winner']}, events={fp['event_count']} "
              f"({fp['events']})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="record the baseline")
    ap.add_argument("--check", action="store_true", help="compare against the baseline")
    ap.add_argument("--force", action="store_true", help="allow overwriting a baseline")
    ap.add_argument("--seeds", type=int, default=len(SEEDS),
                    help=f"how many of the {len(SEEDS)} fixed seeds to play")
    args = ap.parse_args()

    if args.write == args.check:
        ap.error("pass exactly one of --write / --check")

    if args.write:
        if BASELINE_FILE.exists() and not args.force:
            sys.exit(
                f"{BASELINE_FILE.name} already exists. Re-recording a baseline is how "
                "a refactor blesses its own regression - pass --force only if the "
                "behaviour change is intended and reviewed."
            )
        print("recording baseline (each seed played twice to prove reproducibility)")
        data = build(args.seeds, verify_determinism=True)
        BASELINE_FILE.write_text(json.dumps({
            "_comment": (
                "Seeded-game trace fingerprints, recorded before engine/actions.py was "
                "split into a package. A behaviour-preserving refactor reproduces these "
                "exactly. Regenerate only for an intended, reviewed behaviour change."
            ),
            "action_cap": ACTION_CAP,
            "decks": ["starter_vader.json", "starter_luke.json"],
            "games": data,
        }, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {len(data)} fingerprints to {BASELINE_FILE}")
        return 0

    if not BASELINE_FILE.exists():
        sys.exit(f"no baseline at {BASELINE_FILE} - run with --write first")
    golden = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))["games"]
    print(f"checking against {len(golden)} recorded fingerprints")
    live = build(args.seeds, verify_determinism=False)

    drift = {
        seed: {"was": golden[seed], "now": live[seed]}
        for seed in live if seed in golden and golden[seed] != live[seed]
    }
    print()
    if drift:
        print(f"TRACE DRIFT on {len(drift)} seed(s) - behaviour changed:")
        for seed, d in drift.items():
            fields = [k for k in d["was"] if d["was"][k] != d["now"][k]]
            print(f"  seed {seed}: {', '.join(fields)} differ")
            for k in fields:
                print(f"      {k}: {d['was'][k]}  ->  {d['now'][k]}")
        print("\nReproduce with: scripts/replay.py or the seed above.")
        return 1
    print(f"TRACE OK - {len(live)} seeded games reproduce the baseline exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
