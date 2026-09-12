"""Re-runnable, offline reprint-duplicate detector.

Groups every non-token DB row by its printed-face identity (the shared
``swu.cards.reprints.face_key`` helper, so this detector and the alias-application
guard can never disagree), classifies every member with the exact
``audit_coverage`` rule the rest of the toolchain uses, and buckets each
multi-member group:

  mirror            — >=1 member registered AND >=1 not: the unregistered gap
                      members can be aliased onto an implemented twin for free.
  already_covered   — every member already registered (nothing to do).
  already_playable  — 0 registered, every member vanilla / keyword-complete.
  keyword_deferred  — 0 registered, some member needs a deferred keyword AND no
                      member carries functional ability text beyond its keywords
                      (a pure-keyword card — playable iff the keyword is
                      implemented engine-side; verified by ``--verify-playable``).
  needs_encoding    — 0 registered, >=1 member carries functional text (a genuine
                      per-card encode; overlaps the normal deck-encoding backlog).
                      NB: ``audit.classify`` masks a card's functional text behind
                      a ``keyword-deferred`` label whenever it carries a Phase-3
                      keyword (Coordinate/Bounty/…). Bucketing looks past that mask
                      (via ``has_functional_text``) so a keyword-deferred card that
                      ALSO has an unregistered ability lands here, not in
                      ``keyword_deferred`` — matching the docstrings above.

Writes ``docs/reprints_worklist.json`` and prints a summary. ``--check`` exits
non-zero if any ``mirror`` gap is not yet present in ``REPRINT_ALIASES`` (Stage-2
/ CI acceptance). ``--verify-playable`` (Stage-3 / CI acceptance) exits non-zero
if any ``already_playable`` / ``keyword_deferred`` member is not actually playable.

Usage::

    python scripts/find_reprints.py [--db data/swu.db] [--output docs/reprints_worklist.json]
    python scripts/find_reprints.py --check
    python scripts/find_reprints.py --verify-playable
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _relative_db(db_path: str) -> str:
    """Render a DB path relative to the repo root, with forward slashes.

    Falls back to the basename for a DB outside the repo, so the emitted JSON
    never carries an absolute home-directory path.
    """
    try:
        return Path(db_path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(db_path).name
sys.path.insert(0, str(Path(__file__).resolve().parent))   # for audit_coverage
sys.path.insert(0, str(ROOT / "src"))                       # for swu.*

import audit_coverage as audit  # noqa: E402
from swu.cards import reprints  # noqa: E402

# Shipped (non-promo) sets — a canonical is preferred here, since a shipped-set
# card is the one most likely to appear in real decks and get encoded anyway.
SHIPPED_SETS = frozenset({"SOR", "SHD", "TWI", "JTL", "LOF", "SEC", "LAW"})

_REGISTERED_LABELS = ("implemented", "escape-hatch")

# Keywords the engine handles WITHOUT a per-card ability encode: the Phase-2 set,
# which already folds in the Phase-7 keywords (Smuggle/Plot/Hidden/Piloting) and
# the two Phase-3 keywords implemented engine-side as ability *templates* —
# Coordinate (ahsoka-tano:01) and Bounty (shd-han-solo:02). Support stays
# unimplemented, so a Support-only card is a genuine keyword gap. A
# keyword-deferred reprint whose keywords are ALL in this set — and which carries
# no functional text beyond them — needs no work; ``--verify-playable`` asserts it.
# NB: Coordinate/Bounty cards almost always ALSO carry a per-card ability, which
# bucketing routes to needs_encoding (see ``_bucket``); this set governs only the
# pure-keyword residue.
IMPL_ENGINE_KEYWORDS = audit.PHASE2_KEYWORDS


def _num_key(n: str):
    """Sort key that orders numeric card numbers naturally, non-numeric last."""
    s = str(n)
    return (0, int(s)) if s.isdigit() else (1, s)


def _choose_canonical(reg_members):
    """Pick the canonical among a group's registered members: prefer
    non-escape-hatch, then a shipped set, then lowest (set, number)."""
    def sort_key(m):
        set_code, number, _face, label = m
        return (
            1 if label == "escape-hatch" else 0,
            0 if set_code in SHIPPED_SETS else 1,
            set_code,
            _num_key(number),
        )
    return min(reg_members, key=sort_key)


def _bucket(members, has_text_keys) -> str:
    """Classify a whole group. ``members`` is a list of (set, number, face, label).

    ``has_text_keys`` is the set of ``(set, number)`` keys whose card carries
    functional ability text beyond its own keywords (``has_functional_text``). It
    lets bucketing see the text that ``audit.classify`` masks behind a
    ``keyword-deferred`` label for any card bearing a Phase-3 keyword — so a
    keyword-deferred card that ALSO has an unregistered ability is routed to
    ``needs_encoding`` (a real per-card encode), leaving ``keyword_deferred`` for
    genuine pure-keyword residue only.
    """
    labels = [m[3] for m in members]
    registered = [m for m in members if m[3] in _REGISTERED_LABELS]
    gaps = [m for m in members if m[3] not in _REGISTERED_LABELS]
    if registered and gaps:
        return "mirror"
    if registered and not gaps:
        return "already_covered"
    # 0 registered from here on.
    if any(l == "text-bearing" for l in labels):
        return "needs_encoding"
    # A keyword-deferred member that still carries functional ability text is a
    # genuine encode (classify only hid it behind the keyword label).
    if any(m[3] == "keyword-deferred" and (m[0], m[1]) in has_text_keys
           for m in members):
        return "needs_encoding"
    if any(l == "keyword-deferred" for l in labels):
        return "keyword_deferred"
    return "already_playable"


def build_worklist(db_path: str) -> dict:
    # Single source of truth for token exclusion — refuse to run if it drifts.
    assert reprints.TOKEN_TYPES == audit.TOKEN_TYPES, (
        "reprints.TOKEN_TYPES and audit_coverage.TOKEN_TYPES have diverged"
    )

    registered, escape_hatch = audit._load_registry()
    card_index = audit.index_by_set_number(audit.load_cards(db_path))
    faces = reprints.load_faces(db_path)

    # Keys whose card carries functional ability text beyond its own keywords —
    # used by ``_bucket`` to see past classify's keyword-deferred mask.
    has_text_keys = {
        key for key, row in card_index.items()
        if audit.has_functional_text(row.full_text, row.keywords)
    }

    # Group non-token faces by printed-face identity.
    groups: dict[tuple, list] = defaultdict(list)
    for (set_code, number), face in faces.items():
        if face["type"] in audit.TOKEN_TYPES:
            continue
        groups[reprints.face_key(face)].append((set_code, number, face))

    def label_of(set_code: str, number: str) -> str:
        row = card_index.get((set_code, number))
        if row is None:
            return "not-in-db"
        return audit.classify(row, registered, escape_hatch)

    buckets: dict[str, list] = {
        "mirror": [], "already_covered": [], "already_playable": [],
        "keyword_deferred": [], "needs_encoding": [],
    }

    for identity, raw_members in groups.items():
        if len(raw_members) < 2:
            continue
        members = [
            (s, n, face, label_of(s, n)) for (s, n, face) in raw_members
        ]
        members.sort(key=lambda m: (m[0], _num_key(m[1])))
        name = members[0][2]["name"]
        subtitle = members[0][2]["subtitle"]
        card_type = members[0][2]["type"]
        cost = members[0][2]["cost"]

        entry = {
            "name": name,
            "subtitle": subtitle,
            "type": card_type,
            "cost": cost,
            "members": [
                {"set": s, "number": n, "label": lbl} for (s, n, _f, lbl) in members
            ],
        }
        bucket = _bucket(members, has_text_keys)
        if bucket == "mirror":
            canonical = _choose_canonical(
                [m for m in members if m[3] in _REGISTERED_LABELS]
            )
            cset, cnum = canonical[0], canonical[1]
            entry["gaps"] = [
                {"reprint": [s, n], "canonical": [cset, cnum]}
                for (s, n, _f, lbl) in members
                if lbl not in _REGISTERED_LABELS
            ]
        buckets[bucket].append(entry)

    # Deterministic ordering for a stable worklist file.
    for lst in buckets.values():
        lst.sort(key=lambda e: (e["name"] or "", e["members"][0]["set"],
                                _num_key(e["members"][0]["number"])))

    counts = {b: len(lst) for b, lst in buckets.items()}
    member_counts = {b: sum(len(e["members"]) for e in lst)
                     for b, lst in buckets.items()}
    return {
        # Relative to the repo root where possible: this artifact is committed-
        # adjacent and an absolute path would leak the author's home directory.
        "db": _relative_db(db_path),
        "group_counts": counts,
        "member_counts": member_counts,
        "buckets": buckets,
    }


def _all_mirror_gaps(worklist: dict) -> list[tuple[tuple, tuple]]:
    """Every (reprint_key, canonical_key) across the mirror bucket."""
    out = []
    for entry in worklist["buckets"]["mirror"]:
        for gap in entry["gaps"]:
            out.append((tuple(gap["reprint"]), tuple(gap["canonical"])))
    return out


def verify_playable(worklist: dict, db_path: str) -> list[dict]:
    """Re-verify the ``already_playable`` and ``keyword_deferred`` buckets need no
    per-card work, returning a list of members that are NOT actually playable.

    Freshly re-classifies every member (so the check never trusts the stored
    worklist labels):
      * ``already_playable`` — every member must ``is_playable(classify(...))``.
      * ``keyword_deferred`` — every member's keywords must ALL be implemented
        engine-side (:data:`IMPL_ENGINE_KEYWORDS`) AND it must carry no
        unregistered functional text beyond those keywords.
    An empty return means both buckets are clean (Stage-3 acceptance).
    """
    registered, escape_hatch = audit._load_registry()
    card_index = audit.index_by_set_number(audit.load_cards(db_path))
    problems: list[dict] = []

    def _record(bucket, s, n, card, reason):
        problems.append({
            "bucket": bucket, "set": s, "number": n,
            "name": card.name if card else f"{s}_{n}", "reason": reason,
        })

    for entry in worklist["buckets"]["already_playable"]:
        for m in entry["members"]:
            s, n = m["set"], m["number"]
            card = card_index.get((s, n))
            if card is None:
                _record("already_playable", s, n, None, "not in DB")
                continue
            label = audit.classify(card, registered, escape_hatch)
            if not audit.is_playable(label):
                _record("already_playable", s, n, card,
                        f"classifies as {label!r}, not playable")

    for entry in worklist["buckets"]["keyword_deferred"]:
        for m in entry["members"]:
            s, n = m["set"], m["number"]
            card = card_index.get((s, n))
            if card is None:
                _record("keyword_deferred", s, n, None, "not in DB")
                continue
            unimpl = card.keywords - IMPL_ENGINE_KEYWORDS
            if unimpl:
                _record("keyword_deferred", s, n, card,
                        f"keyword(s) not implemented engine-side: "
                        f"{', '.join(sorted(unimpl))}")
                continue
            if ((s, n) not in registered
                    and audit.has_functional_text(card.full_text, card.keywords)):
                _record("keyword_deferred", s, n, card,
                        "carries unregistered functional text beyond its keyword "
                        "(needs a per-card encode, not just the keyword)")
    return problems


def _print_summary(worklist: dict) -> None:
    gc, mc = worklist["group_counts"], worklist["member_counts"]
    total_groups = sum(gc.values())
    total_members = sum(mc.values())
    print(f"\nReprint groups (>1 member, tokens excluded): {total_groups} "
          f"/ {total_members} members\n")
    order = ["mirror", "already_covered", "already_playable",
             "keyword_deferred", "needs_encoding"]
    for b in order:
        print(f"  {b:18s}: {gc[b]:4d} groups / {mc[b]:4d} members")
    n_gaps = sum(len(e["gaps"]) for e in worklist["buckets"]["mirror"])
    print(f"\n  mirror-gap members to alias (Stage 2): {n_gaps}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SWU reprint-duplicate detector")
    parser.add_argument("--db", default=str(ROOT / "data" / "swu.db"))
    parser.add_argument("--output", default=str(ROOT / "docs" / "reprints_worklist.json"))
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if any mirror gap is not yet in "
                             "REPRINT_ALIASES")
    parser.add_argument("--verify-playable", action="store_true",
                        help="exit non-zero if any already_playable / "
                             "keyword_deferred member is not actually playable")
    args = parser.parse_args()

    if not Path(args.db).exists():
        sys.exit(f"DB not found: {args.db}")

    worklist = build_worklist(args.db)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(worklist, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    _print_summary(worklist)
    print(f"\nWorklist written to {out}")

    if args.check:
        missing = [
            (rep, can) for (rep, can) in _all_mirror_gaps(worklist)
            if rep not in reprints.REPRINT_ALIASES
        ]
        if missing:
            print(f"\n--check FAILED: {len(missing)} mirror gap(s) not yet in "
                  f"REPRINT_ALIASES:", file=sys.stderr)
            for rep, can in missing[:20]:
                print(f"    {rep[0]}_{rep[1]}  ->  {can[0]}_{can[1]}", file=sys.stderr)
            if len(missing) > 20:
                print(f"    … and {len(missing) - 20} more", file=sys.stderr)
            return 1
        print("\n--check OK: every mirror gap is aliased.")

    if args.verify_playable:
        problems = verify_playable(worklist, args.db)
        if problems:
            print(f"\n--verify-playable FAILED: {len(problems)} member(s) in the "
                  f"already_playable / keyword_deferred buckets are NOT actually "
                  f"playable:", file=sys.stderr)
            for p in problems:
                print(f"    [{p['bucket']}] {p['set']}_{p['number']} "
                      f"{p['name']} — {p['reason']}", file=sys.stderr)
            return 1
        ap = worklist["member_counts"]["already_playable"]
        kd = worklist["member_counts"]["keyword_deferred"]
        print(f"\n--verify-playable OK: all {ap} already_playable + {kd} "
              f"keyword_deferred members are playable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
