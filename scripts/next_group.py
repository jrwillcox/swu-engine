#!/usr/bin/env python
"""Global campaign queue walker for the gap-filling campaign.

Replans every set (offline, deterministic, free) from the DB + ability registry,
refreshes each set's manifest in place, and prints the next N incomplete encoding
groups in campaign order — each with its spec path, a ready-to-run focused VERIFY
command, the remaining (still-unplayable) cards, and progress.

It holds NO state of its own: every run re-derives the whole campaign from disk
(the card DB, the ability registry, and the pre-generated ``encoding/<slug>-set/``
manifests). So it behaves identically mid-session, after /compact, after /clear,
or after a laptop restart — there is nothing to "resume".

    python scripts/next_group.py            # the next 3 groups (a batch)
    python scripts/next_group.py --n 1      # just the next group (refresh + peek)
    python scripts/next_group.py --n 2      # a smaller batch (tight on usage)

Flags printed next to a pick:
    [ESCALATION]        group needs a not-yet-existing primitive → STOP & flag
                        (this whole group is the batch; do not co-mingle cards)
    [KEYWORD-ENGINE]    a still-unimplemented engine keyword (Support) → implement
                        the keyword engine-side once; NO residual card text this run
    [KEYWORD-RESIDUAL]  keyword already implemented; only the listed residual-text
                        cards remain — encode just those
    (no flag)           an ordinary ability batch — encode the listed cards
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

# Several status lines carry emoji (the QUEUE EMPTY banner, MILESTONE, the em
# dashes), and a Windows console defaults to cp1252 — which raises
# UnicodeEncodeError *after* printing the line, so the walker exits non-zero on a
# purely cosmetic failure.  That had never fired until the campaign finished and
# the 🎉 banner printed for the first time.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audit_coverage as audit  # noqa: E402
import plan_encoding as P       # noqa: E402

# Campaign order: the eight main expansions in release order, then the boxed/index
# set, the 2026 two-player starter, promo years, per-set promos, judge/convention
# promos, and finally the tiny weekly/misc sets. Set-by-set: an earlier set is
# fully exhausted before the walker offers a group from a later one.
SET_ORDER = [
    "SOR", "SHD", "TWI", "JTL", "LOF", "SEC", "LAW", "ASH",
    "IBH", "TS26",
    "P25", "P26",
    "JTLP", "SECP", "LOFP", "LAWP",
    "J24", "J25",
    "C24", "C25", "C26",
    "GG", "G25", "MV26",
]


def _complete(prog: dict, gid: str) -> bool:
    p = prog[gid]
    return bool(p["total"]) and p["done"] == p["total"]


def _remaining_cards(group, registered, escape_hatch) -> list[str]:
    """The group's cards that are still NOT playable, in card-number order."""
    out = []
    for c in group.cards:
        lbl = P.classify_card(c, registered, escape_hatch)
        if not audit.is_playable(lbl):
            out.append(c.cid)
    return out


def _flag(group, remaining) -> str:
    if group.new_primitives:
        return "ESCALATION"
    if group.kind == "keyword":
        if group.keyword in audit.PHASE3_KEYWORDS:
            return "KEYWORD-ENGINE"
        return "KEYWORD-RESIDUAL"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Campaign queue walker")
    ap.add_argument("--n", type=int, default=3, help="how many groups to offer (default 3)")
    ap.add_argument("--db", default=str(P.DEFAULT_DB))
    args = ap.parse_args()

    registered, escape_hatch = audit._load_registry()

    picks: list[tuple[str, object, dict]] = []   # (slug, group, prog)
    sets_total = len(SET_ORDER)
    sets_complete = 0
    groups_total = 0
    groups_complete = 0
    cards_remaining = 0
    active_slug = None
    active_stats = None                            # (playable, total, done_groups, n_groups)
    milestone_slug = None
    prev_slug = None
    prev_complete = False

    for code in SET_ORDER:
        slug, groups, meta = P.plan(None, code, args.db)
        P.emit(slug, groups, meta)                 # refresh manifest.json/MANIFEST.md
        prog = meta["progress"]
        n_groups = len(groups)
        done_groups = sum(1 for g in groups if _complete(prog, g.gid))
        groups_total += n_groups
        groups_complete += done_groups
        cards_remaining += meta["total_deck"] - meta["playable_deck"]

        set_done = all(_complete(prog, g.gid) for g in groups)   # True also when 0 groups
        if set_done:
            sets_complete += 1

        # Eligible incomplete groups for THIS set, in dependency-respecting seq order.
        if not set_done and len(picks) < args.n:
            done_ids = {g.gid for g in groups if _complete(prog, g.gid)}
            for g in sorted(groups, key=lambda x: x.seq):
                if len(picks) >= args.n:
                    break
                if g.gid in done_ids:
                    continue
                if not all(d in done_ids for d in g.depends_on):
                    continue                        # dep not done yet; wait for it
                # First eligible pick fixes the "active set" for the footer.
                if active_slug is None:
                    active_slug = slug
                    active_stats = (meta["playable_deck"], meta["total_deck"],
                                    done_groups, n_groups)
                    # We just crossed into `slug`; if the previous non-empty set is
                    # complete and this set has no completed groups yet, that prior
                    # set was just finished → milestone.
                    if prev_complete and done_groups == 0:
                        milestone_slug = prev_slug
                picks.append((slug, g, prog))

        # Track the previous *non-empty* set for milestone detection.
        if n_groups > 0:
            prev_slug = slug
            prev_complete = set_done

    # ── Emit the queue ────────────────────────────────────────────────────────
    if not picks:
        print("QUEUE EMPTY — every planned group is complete. Campaign done. 🎉")
    for i, (slug, g, prog) in enumerate(picks, start=1):
        remaining = _remaining_cards(g, registered, escape_hatch)
        flag = _flag(g, remaining)
        nn = g.gid.split(":")[1]
        shown = remaining[:7]
        overflow = f" (+{len(remaining) - 7} more)" if len(remaining) > 7 else ""
        p = prog[g.gid]
        flag_s = f" [{flag}]" if flag else ""
        spec = f"encoding/{slug}/{g.file_slug}.md"
        print(f"NEXT{i}: {g.gid} [{g.kind}] {g.theme}  {p['done']}/{p['total']}"
              f"  spec={spec}  cards={','.join(shown)}{overflow}{flag_s}")
        print(f"  VERIFY: .venv/Scripts/python.exe scripts/verify_encoding.py {slug} --group {nn}")

    # ── Footer ────────────────────────────────────────────────────────────────
    print()
    print(f"CAMPAIGN: sets complete {sets_complete}/{sets_total}; "
          f"groups complete {groups_complete}/{groups_total}; "
          f"cards remaining {cards_remaining}")
    if active_slug and active_stats:
        pl, tot, dg, ng = active_stats
        print(f"ACTIVE SET {active_slug}: {pl}/{tot} cards playable, {dg}/{ng} groups")
    if milestone_slug:
        print(f"MILESTONE: {milestone_slug} complete — run the medium tier "
              f"(pytest -m slow -q) + audit_coverage.py, then "
              f"regenerate docs/coverage_report.md")


if __name__ == "__main__":
    main()
