"""
Audit card-image integrity for a SWU database.

`(set_code, card_number)` is NOT unique — every Leader (numbered 1, 2, 3, …)
collides with a Token reusing that low number, so images were once named by
number alone and two colliding cards pointed at the *same* physical file (the
"Iden Versio Leader renders as a Shield token" / "Ahsoka droid token shows a
lightsaber" class of bug).  `scripts/fix_image_collisions.py` repaired this by
giving every colliding card an id-based filename; this script is the *repeatable
check* that the repair held (and stays held), plus a stale-file report.

For the given DB (respecting the ``SWU_DB`` env var, or ``--db``) it reports:

  (a) COLLISIONS  — two card ids sharing an ``image_front_path``/``image_back_path``.
  (b) MISSING     — a referenced image file that is not on disk.
  (c) STALE       — an on-disk image file referenced by no card or variant
                    (e.g. the old number-only ``1_front.png`` scheme leftovers).
  (d) GROUPS      — an explicit per-(set, number)-collision-group check that every
                    Leader/Token in the group resolves to a distinct, on-disk file,
                    plus a dedicated check of Ahsoka's Padawan Lightsaber (TWI_248).

Exit code is non-zero if (a) or (b) is non-empty — collisions and missing files
are real corruption; stale files are informational only.

    python scripts/audit_images.py                 # audit the DEV DB (data/swu.db)
    SWU_DB=../swu-game-deployed/data/swu.db \
        python scripts/audit_images.py             # audit the DEPLOYED DB
    python scripts/audit_images.py --db path/to/swu.db

Repairing a dirty DEPLOYED DB (data is NOT code — deploy.ps1 mirrors code only,
so this is a manual data sync).  Either re-run the collision fix + image fetch
against the deployed data dir:

    SWU_DB=../swu-game-deployed/data/swu.db python scripts/fix_image_collisions.py
    SWU_DB=../swu-game-deployed/data/swu.db python scripts/fetch_images.py

…or, if the DEV data is known-good, copy the corrected DB + images across:

    cp swu-game/data/swu.db          swu-game-deployed/data/swu.db
    cp -r swu-game/data/images/*     swu-game-deployed/data/images/
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ahsoka's Padawan Lightsaber — the card named in the live bug report; its unique
# id must resolve to the TWI upgrade art, never a token's.
AHSOKA_LIGHTSABER = ("TWI", "248")

# Token card types (the collision counterpart of a Leader sharing its low number).
TOKEN_TYPES = frozenset({
    "Token Unit", "Token Upgrade", "Credit Token", "Force Token",
})


def _norm(rel: str) -> str:
    """DB paths use Windows separators; normalise to POSIX for on-disk lookup."""
    return rel.replace("\\", "/")


@dataclass
class Card:
    id: int
    set_code: str
    card_number: str
    name: str
    type: str
    front: str | None
    back: str | None


@dataclass
class ImageAudit:
    collisions: list[tuple[str, list[int]]] = field(default_factory=list)
    missing: list[tuple[int, str, str]] = field(default_factory=list)  # (id, side, rel)
    stale: list[str] = field(default_factory=list)                     # rel paths
    group_issues: list[str] = field(default_factory=list)             # (d) problems
    groups_checked: int = 0

    @property
    def ok(self) -> bool:
        """The gate: collisions and missing files are corruption."""
        return not self.collisions and not self.missing


def _load_cards(con: sqlite3.Connection) -> list[Card]:
    con.row_factory = sqlite3.Row
    return [
        Card(r["id"], r["set_code"], r["card_number"], r["name"], r["type"],
             r["image_front_path"], r["image_back_path"])
        for r in con.execute(
            "SELECT id, set_code, card_number, name, type, "
            "image_front_path, image_back_path FROM cards"
        )
    ]


def _referenced_files(con: sqlite3.Connection, data_dir: Path) -> set[Path]:
    """Every image path referenced by a card OR a variant, resolved absolute."""
    out: set[Path] = set()
    queries = [("cards", "image_front_path", "image_back_path")]
    has_variants = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_variants'"
    ).fetchone()
    if has_variants:
        queries.append(("card_variants", "image_front_path", "image_back_path"))
    for table, fcol, bcol in queries:
        for front, back in con.execute(f"SELECT {fcol}, {bcol} FROM {table}"):
            for rel in (front, back):
                if rel:
                    out.add((data_dir / _norm(rel)).resolve())
    return out


def audit_images(db_file: Path, data_dir: Path) -> ImageAudit:
    """Run the full image audit against one DB + its data dir. Pure (no printing)."""
    con = sqlite3.connect(str(db_file))
    try:
        cards = _load_cards(con)
        referenced = _referenced_files(con, data_dir)
    finally:
        con.close()

    audit = ImageAudit()

    # (a) COLLISIONS — two card ids sharing a physical image path.
    by_path: dict[str, list[int]] = defaultdict(list)
    for c in cards:
        for rel in (c.front, c.back):
            if rel:
                by_path[_norm(rel)].append(c.id)
    audit.collisions = sorted(
        (path, sorted(ids)) for path, ids in by_path.items() if len(ids) > 1
    )

    # (b) MISSING — a referenced file that is not on disk.
    for c in cards:
        for side, rel in (("front", c.front), ("back", c.back)):
            if rel and not (data_dir / _norm(rel)).exists():
                audit.missing.append((c.id, side, rel))
    audit.missing.sort()

    # (c) STALE — an on-disk image referenced by no card or variant.
    images_dir = data_dir / "images"
    if images_dir.is_dir():
        for p in images_dir.rglob("*"):
            if p.is_file() and p.suffix != ".tmp" and p.resolve() not in referenced:
                audit.stale.append(str(p.relative_to(data_dir)))
        audit.stale.sort()

    # (d) GROUPS — per (set, number) collision group, every card resolves to a
    # distinct on-disk file; plus the explicit Ahsoka-lightsaber check.
    groups: dict[tuple[str, str], list[Card]] = defaultdict(list)
    for c in cards:
        groups[(c.set_code, c.card_number)].append(c)
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        audit.groups_checked += 1
        seen: dict[str, int] = {}
        for c in members:
            for side, rel in (("front", c.front), ("back", c.back)):
                if not rel:
                    continue
                norm = _norm(rel)
                if norm in seen and seen[norm] != c.id:
                    audit.group_issues.append(
                        f"{c.set_code}_{c.card_number} group: ids {seen[norm]} and "
                        f"{c.id} ({c.name}) share {side} image {norm}"
                    )
                seen[norm] = c.id
                if not (data_dir / norm).exists():
                    audit.group_issues.append(
                        f"{c.set_code}_{c.card_number} {c.name} (id {c.id}) "
                        f"{side} image missing: {norm}"
                    )

    audit.group_issues.extend(_check_ahsoka_lightsaber(cards, data_dir))
    return audit


def _check_ahsoka_lightsaber(cards: list[Card], data_dir: Path) -> list[str]:
    """The named live-bug card: TWI_248's non-token row must resolve to real art."""
    sc, num = AHSOKA_LIGHTSABER
    matches = [c for c in cards if c.set_code == sc and c.card_number == num]
    non_token = [c for c in matches if c.type not in TOKEN_TYPES]
    if not non_token:
        return [f"{sc}_{num} (Ahsoka's Padawan Lightsaber) not found in DB"]
    issues: list[str] = []
    for c in non_token:
        if not c.front:
            issues.append(f"{sc}_{num} {c.name} (id {c.id}) has no front image path")
        elif not (data_dir / _norm(c.front)).exists():
            issues.append(
                f"{sc}_{num} {c.name} (id {c.id}) front image missing: {_norm(c.front)}"
            )
    return issues


def _print_report(audit: ImageAudit, db_file: Path) -> None:
    print(f"Image audit: {db_file}")
    print(f"  (a) path collisions:        {len(audit.collisions)}")
    for path, ids in audit.collisions:
        print(f"        {path}  <-  ids {ids}")
    print(f"  (b) missing referenced:     {len(audit.missing)}")
    for cid, side, rel in audit.missing:
        print(f"        id {cid} {side}: {rel}")
    print(f"  (c) stale on-disk files:    {len(audit.stale)} (informational)")
    for rel in audit.stale[:20]:
        print(f"        {rel}")
    if len(audit.stale) > 20:
        print(f"        ... and {len(audit.stale) - 20} more")
    print(f"  (d) collision groups:       {audit.groups_checked} checked, "
          f"{len(audit.group_issues)} issue(s)")
    for issue in audit.group_issues:
        print(f"        {issue}")
    verdict = "CLEAN" if (audit.ok and not audit.group_issues) else (
        "OK (collisions+missing clean; see group issues)" if audit.ok else "FAIL"
    )
    print(f"  => {verdict}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--db", type=Path, default=None,
        help="path to swu.db (default: $SWU_DB, else <repo>/data/swu.db)",
    )
    args = ap.parse_args()

    db_file = args.db or (Path(os.environ["SWU_DB"]) if os.environ.get("SWU_DB")
                          else ROOT / "data" / "swu.db")
    if not db_file.exists():
        print(f"DB not found at {db_file}", file=sys.stderr)
        sys.exit(2)

    audit = audit_images(db_file, db_file.parent)
    _print_report(audit, db_file)
    sys.exit(0 if audit.ok else 1)


if __name__ == "__main__":
    main()
