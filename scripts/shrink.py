"""
Delta-debugging minimiser for SWU failure bundles.

Given a failure bundle from soak.py, repeatedly tries to shorten the action
history while keeping the failure reproducible.  Writes a minimised bundle.

Usage
-----
python scripts/shrink.py failures/<timestamp>_<seed>.json [options]

Options
-------
--out PATH      Output path for minimised bundle (default: <input>_min.json)
--timeout S     Give up after S seconds of shrinking (default: 120)
--passes N      Maximum shrink passes (default: 50)
--verbose       Print progress during shrinking

Algorithm: binary partition (delta-debugging variant)
  1. Try removing the first half of the action history → still fails? keep.
  2. Try removing the second half → still fails? keep.
  3. Repeat with smaller halves until each individual action is tried.
  4. Also try truncating at each possible prefix length.

Re-driving legality: removing an action changes future legal actions, so we
cannot simply replay the truncated history verbatim.  Instead we re-drive the
bots from any divergence point, using the same seeds, to regenerate a valid
continuation that still hits the same failure.

NOTE: the minimiser proves only that the shorter sequence is *also* a failure,
not necessarily the same bug.  Review the minimised repro before trusting it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import os
os.environ.setdefault("SWU_DB", str(_PROJECT_ROOT / "data" / "swu.db"))


# ── failure predicate ─────────────────────────────────────────────────────────

def _try_sequence(
    seed: int,
    deck_p0_name: str,
    deck_p1_name: str,
    bot_p0_name: str,
    bot_p1_name: str,
    action_history: list[dict],
    action_cap: int = 2000,
) -> bool:
    """Return True iff the given action_history (possibly truncated / modified)
    re-triggers the failure on the same game seed.

    Strategy: replay the recorded actions as far as they remain legal;
    when they diverge (or we run out), switch to bot play and check if
    the failure occurs within action_cap total steps.
    """
    sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))
    from soak import _load_deck, _make_bot

    db_path = str(_PROJECT_ROOT / "data" / "swu.db")
    from swu.cards.repository import CardRepository
    repo = CardRepository(db_path)
    deck_p0 = _load_deck(repo, deck_p0_name)
    deck_p1 = _load_deck(repo, deck_p1_name)

    from swu.engine.actions import create_game, legal_actions, apply
    from swu.engine.invariants import CheckContext, check as inv_check

    state = create_game("P0", deck_p0, "P1", deck_p1, seed=seed)
    ctx = CheckContext.from_state(state)
    bot_p0 = _make_bot(bot_p0_name, "P0", seed)
    bot_p1 = _make_bot(bot_p1_name, "P1", seed + 1)
    bots = {"P0": bot_p0, "P1": bot_p1}

    n = 0
    for record in action_history:
        if state.is_terminal():
            return False
        acts = legal_actions(state)
        kind = record["kind"]
        desc = record.get("desc", "")

        # Find matching action
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
            # History diverged — fall through to bot play
            break

        try:
            state = apply(state, chosen)
        except Exception:
            return True

        try:
            inv_check(state, ctx)
        except AssertionError:
            return True

        n += 1

    # Continue with bots up to action_cap
    while not state.is_terminal() and n < action_cap:
        acts = legal_actions(state)
        active_id = state.active_player.player_id
        view = state.view_for(active_id)
        chosen = bots[active_id].choose_action(view, acts)
        try:
            state = apply(state, chosen)
        except Exception:
            return True
        try:
            inv_check(state, ctx)
        except AssertionError:
            return True
        n += 1

    return False


# ── delta-debugging minimiser ─────────────────────────────────────────────────

def _ddmin(
    history: list[dict],
    predicate: Callable[[list[dict]], bool],
    timeout: float,
    max_passes: int,
    verbose: bool,
) -> list[dict]:
    """Simplified delta-debugging (ddmin) variant.

    Tries to find a minimal sub-sequence of *history* that still satisfies
    *predicate*.  Uses binary splitting and prefix truncation.
    """
    t0 = time.monotonic()
    current = list(history)
    passes = 0

    def _elapsed() -> float:
        return time.monotonic() - t0

    def _try(candidate: list[dict]) -> bool:
        if not candidate:
            return False
        return predicate(candidate)

    while passes < max_passes and _elapsed() < timeout:
        improved = False
        passes += 1
        n = len(current)
        if n <= 1:
            break

        if verbose:
            print(f"  Pass {passes}: {n} actions, {_elapsed():.1f}s elapsed")

        # Binary splitting: try removing each half
        mid = n // 2
        for candidate in [current[:mid], current[mid:]]:
            if _elapsed() > timeout:
                break
            if _try(candidate):
                current = candidate
                improved = True
                if verbose:
                    print(f"    Reduced to {len(current)} actions")
                break

        if improved:
            continue

        # Granular: try removing each individual action (if small enough)
        if n <= 64:
            for i in range(n - 1, -1, -1):
                if _elapsed() > timeout:
                    break
                candidate = current[:i] + current[i + 1:]
                if _try(candidate):
                    current = candidate
                    improved = True
                    if verbose:
                        print(f"    Removed action {i}, now {len(current)}")
                    break

        if not improved:
            # Try prefix truncation
            for trunc in range(n - 1, 0, -n // 4 or -1):
                if _elapsed() > timeout:
                    break
                candidate = current[:trunc]
                if _try(candidate):
                    current = candidate
                    improved = True
                    if verbose:
                        print(f"    Truncated to {len(current)} actions")
                    break

        if not improved:
            break

    return current


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Minimise a soak.py failure bundle")
    p.add_argument("bundle", help="Path to the failure bundle JSON file")
    p.add_argument("--out", default=None)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--passes", type=int, default=50)
    p.add_argument("--verbose", action="store_true", default=False)
    args = p.parse_args(argv)

    bundle_path = Path(args.bundle)
    if not bundle_path.exists():
        print(f"ERROR: bundle not found: {bundle_path}", file=sys.stderr)
        return 1

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    seed = bundle["seed"]
    bot_p0 = bundle["bot_p0"]
    bot_p1 = bundle["bot_p1"]
    deck_p0 = bundle["deck_p0"]
    deck_p1 = bundle["deck_p1"]
    original_history = bundle.get("action_history", [])

    if not original_history:
        print("Bundle has no action history — cannot shrink.")
        return 1

    print(
        f"Shrinking: seed={seed} {bot_p0} vs {bot_p1} "
        f"({deck_p0} vs {deck_p1}), "
        f"{len(original_history)} actions"
    )

    # Verify the original bundle still fails
    predicate = lambda h: _try_sequence(seed, deck_p0, deck_p1, bot_p0, bot_p1, h)
    if not predicate(original_history):
        print("WARNING: original bundle no longer reproduces the failure — bug may be fixed.")

    minimal = _ddmin(
        original_history,
        predicate,
        timeout=args.timeout,
        max_passes=args.passes,
        verbose=args.verbose,
    )

    reduction = len(original_history) - len(minimal)
    print(
        f"Minimised: {len(original_history)} → {len(minimal)} actions "
        f"(-{reduction}, {100*reduction/max(1,len(original_history)):.0f}% reduction)"
    )

    out_path = Path(args.out) if args.out else bundle_path.with_stem(bundle_path.stem + "_min")
    minimised_bundle = dict(bundle)
    minimised_bundle["action_history"] = minimal
    minimised_bundle["shrunk_from"] = len(original_history)
    out_path.write_text(json.dumps(minimised_bundle, indent=2), encoding="utf-8")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
