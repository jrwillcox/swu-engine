"""
Replay a failure bundle produced by soak.py.

Usage
-----
python scripts/replay.py failures/<timestamp>_<seed>.json [options]

Options
-------
--verbose       Print each action's description before applying it
--stop-at N     Halt after N actions (for inspection, no failure check)
--no-invariants Skip invariant checks during replay (for speed)

The script deterministically re-runs the exact action sequence stored in the
bundle and reproduces the failure at the same point.  Exit code 0 means the
replay completed without re-triggering the failure (regression fixed).
Exit code 1 means the failure reproduced.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is importable regardless of cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import os
os.environ.setdefault("SWU_DB", str(_PROJECT_ROOT / "data" / "swu.db"))


# ── action reconstruction from serialised history ────────────────────────────

def _reconstruct_action(kind: str, legal: list) -> object:
    """Pick the legal action whose type name matches *kind*.

    For most kinds there is at most one such action in the legal list (Pass,
    KeepHand, …).  For kinds with multiple legal instances (AttackWithUnit,
    PlayCard, …) we rely on the caller supplying the full legal list and the
    matching logic in ``_drive_from_history``.
    """
    matches = [a for a in legal if type(a).__name__ == kind]
    if len(matches) == 1:
        return matches[0]
    return None


def _drive_from_history(
    state,
    action_history: list[dict],
    stop_at: int | None,
    verbose: bool,
    check_invariants: bool,
) -> tuple:
    """Re-drive the game using the recorded action history.

    Returns (final_state, failure_reproduced: bool, failure_msg: str).
    The action descriptions are used as a fallback hint but the primary
    matching is by action kind.  When multiple actions of the same kind are
    legal, we pick the one whose describe() matches the recorded description.
    """
    from swu.engine.actions import legal_actions, apply
    ctx = None
    if check_invariants:
        from swu.engine.invariants import CheckContext, check as inv_check
        ctx = CheckContext.from_state(state)

    limit = stop_at if stop_at is not None else len(action_history)
    for i, record in enumerate(action_history[:limit]):
        if state.is_terminal():
            print(f"[replay] Game ended early at action {i} (terminal state).")
            return state, False, ""

        acts = legal_actions(state)
        kind = record["kind"]
        desc = record.get("desc", "")

        # Match: exact describe() first, then first-of-kind fallback
        chosen = None
        for a in acts:
            if type(a).__name__ == kind and a.describe() == desc:
                chosen = a
                break
        if chosen is None:
            for a in acts:
                if type(a).__name__ == kind:
                    chosen = a
                    break

        if chosen is None:
            msg = (
                f"[replay] Cannot reproduce action {i}: kind={kind!r} desc={desc!r} "
                f"not in legal actions {[type(a).__name__ for a in acts]}"
            )
            print(msg, file=sys.stderr)
            return state, False, msg

        if verbose:
            print(f"  [{i}] {chosen.describe()}")

        try:
            state = apply(state, chosen)
        except Exception as exc:
            msg = f"[replay] Exception at action {i}: {exc}"
            print(msg, file=sys.stderr)
            return state, True, msg

        if check_invariants and ctx is not None:
            try:
                inv_check(state, ctx)
            except AssertionError as exc:
                msg = f"[replay] Invariant violation at action {i}: {exc}"
                print(msg, file=sys.stderr)
                return state, True, msg

    return state, False, ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Replay a soak.py failure bundle")
    p.add_argument("bundle", help="Path to the failure bundle JSON file")
    p.add_argument("--verbose", action="store_true", default=False)
    p.add_argument("--stop-at", type=int, default=None, dest="stop_at")
    p.add_argument("--no-invariants", dest="check_invariants",
                   action="store_false", default=True)
    args = p.parse_args(argv)

    bundle_path = Path(args.bundle)
    if not bundle_path.exists():
        print(f"ERROR: bundle not found: {bundle_path}", file=sys.stderr)
        return 1

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    seed = bundle["seed"]
    bot_p0_name = bundle["bot_p0"]
    bot_p1_name = bundle["bot_p1"]
    deck_p0_name = bundle["deck_p0"]
    deck_p1_name = bundle["deck_p1"]
    action_history = bundle.get("action_history", [])

    print(
        f"Replaying seed={seed} {bot_p0_name} vs {bot_p1_name} "
        f"({deck_p0_name} vs {deck_p1_name}), "
        f"{len(action_history)} actions recorded"
    )
    if bundle.get("error_msg"):
        print(f"Original failure: {bundle['error_msg'][:300]}")

    # Reconstruct starting game state
    from swu.cards.repository import CardRepository

    # Import deck loader from soak.py utilities
    sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))
    from soak import _load_deck

    db_path = str(_PROJECT_ROOT / "data" / "swu.db")
    repo = CardRepository(db_path)
    deck_p0 = _load_deck(repo, deck_p0_name)
    deck_p1 = _load_deck(repo, deck_p1_name)

    from swu.engine.actions import create_game
    state = create_game("P0", deck_p0, "P1", deck_p1, seed=seed)

    final_state, reproduced, msg = _drive_from_history(
        state,
        action_history,
        stop_at=args.stop_at,
        verbose=args.verbose,
        check_invariants=args.check_invariants,
    )

    if reproduced:
        print(f"\nFAILURE REPRODUCED: {msg}")
        return 1
    else:
        status = "STOPPED early" if args.stop_at is not None else "COMPLETED"
        terminal = final_state.is_terminal()
        print(f"\n{status} — terminal={terminal}, round={final_state.round_number}")
        if terminal:
            print(f"Winner: {final_state.winner}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
