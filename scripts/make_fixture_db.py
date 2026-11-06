"""Build ``tests/fixtures/swu_fixture.db`` — the small card database the test
suite falls back to when the full corpus hasn't been built.

Why this exists
---------------
The repository ships no card corpus: it is the publisher's IP and is
rebuilt locally by the pipeline (``docs/pipeline.md``).  That is the right
distribution model, but it meant ``git clone && pytest`` *skipped* most of the
suite — a reviewer saw "4,094 skipped" and had no way to tell a healthy engine
from a broken one without a 90-minute scrape first.

The fixture is the compromise: a few hundred card definitions — the ones the
engine, keyword, web and regression tests actually load — carried as a test
fixture so those tiers run for real on a fresh clone.  It is text and stats
only (no artwork, no flavour, no images) and is NOT a substitute for the corpus:
the per-set card tests, the coverage audit and the reprint sweep all still need
the real database and skip without it (see ``tests/dbpath.py``).

How the card list is chosen
---------------------------
Not by hand.  ``--record`` runs the fixture-eligible part of the suite against
the REAL database with ``CardRepository._hydrate`` instrumented, so the manifest
is exactly the set of cards those tests loaded — nothing aspirational, nothing
stale.  Re-record it after adding a test that needs a new card::

    python scripts/make_fixture_db.py --record     # rewrites the manifest
    python scripts/make_fixture_db.py              # rebuilds the .db

Both the manifest (``tests/fixtures/fixture_cards.json``) and the built database
are committed, so neither a contributor nor CI needs the real corpus to run the
fixture-backed tiers.

Card identity is the DB ``id`` — the Strapi id, stable across rebuilds — NOT
``(set_code, card_number)``, which is not unique: Leaders collide with
same-numbered Tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "fixture_cards.json"
FIXTURE_DB = REPO_ROOT / "tests" / "fixtures" / "swu_fixture.db"

# Child tables keyed on cards.id.  card_variants is deliberately EXCLUDED: it
# exists only to map alternate printings to artwork the fixture doesn't carry,
# and it is the largest child table (3,558 rows).
CHILD_TABLES = ("card_aspects", "card_keywords", "card_traits", "card_arenas")


def _source_db() -> Path:
    env = os.environ.get("SWU_DB")
    path = Path(env) if env else REPO_ROOT / "data" / "swu.db"
    if not path.exists():
        sys.exit(
            f"Source database not found at {path}.\n"
            "Building the fixture needs the real corpus — see docs/pipeline.md.\n"
            "(Running the tests does NOT: the built fixture is committed.)"
        )
    return path


# ── record mode ───────────────────────────────────────────────────────────────

_RECORDER = '''\
"""Run the fixture-eligible tests with card loads recorded (see make_fixture_db).

Records only cards a test actually USES, which is not the same as every card it
touches.  ``build_vanilla_deck`` scans every Unit and Upgrade in the corpus to
pick ~17 names for a deck: recording the scan would pull in 1,893 cards to
support a 50-card deck.  So bulk reads (``all_of_type``, ``iter_all``) are
excluded, and the cards the deck builders actually RETURN are recorded instead.
"""
import json, os, sys

sys.path.insert(0, os.getcwd())

from swu.cards import decklist
from swu.cards.repository import CardRepository

_seen = {}
_bulk = {"depth": 0}
_real_hydrate = CardRepository._hydrate


def _note(card):
    cid = getattr(card, "id", None)
    if cid is None:
        return
    _seen[int(cid)] = (getattr(card, "set_code", None),
                       getattr(card, "card_number", None),
                       getattr(card, "name", None))


def _hydrate(self, con, row):
    card = _real_hydrate(self, con, row)
    if not _bulk["depth"]:
        try:
            _seen[int(row["id"])] = (row["set_code"], row["card_number"], row["name"])
        except Exception:
            pass
    return card


CardRepository._hydrate = _hydrate


def _wrap_bulk(name):
    real = getattr(CardRepository, name)

    def wrapper(self, *a, **kw):
        _bulk["depth"] += 1
        try:
            result = real(self, *a, **kw)
            if name == "iter_all":       # a generator: materialise inside the guard
                result = list(result)
            return result
        finally:
            _bulk["depth"] -= 1

    setattr(CardRepository, name, wrapper)


for _name in ("all_of_type", "iter_all"):
    _wrap_bulk(_name)


def _wrap_deck(name):
    real = getattr(decklist, name)

    def wrapper(*a, **kw):
        cards = real(*a, **kw)
        for c in (cards or ()):
            _note(c)
        return cards

    setattr(decklist, name, wrapper)


for _name in ("build_vanilla_deck", "load_decklist"):
    if hasattr(decklist, _name):
        _wrap_deck(_name)

import pytest

code = pytest.main(sys.argv[1:])

with open(os.environ["FIXTURE_RECORD_OUT"], "w", encoding="utf-8") as fh:
    json.dump(
        [{"id": cid, "set_code": s, "card_number": n, "name": nm}
         for cid, (s, n, nm) in sorted(_seen.items())],
        fh, indent=1,
    )
raise SystemExit(code)
'''


def record(pytest_args: list[str]) -> None:
    """Run the fixture-eligible tests against the real DB and rewrite the manifest."""
    from tests.fixture_scope import fixture_eligible_args  # noqa: E402

    src = _source_db()
    runner = REPO_ROOT / "build" / "_record_fixture.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(_RECORDER, encoding="utf-8")

    env = {**os.environ, "SWU_DB": str(src), "FIXTURE_RECORD_OUT": str(MANIFEST)}
    args = pytest_args or fixture_eligible_args()
    print(f"Recording card loads over {len(args)} pytest target(s)...")
    proc = subprocess.run([sys.executable, str(runner), *args, "-q", "--no-header"],
                          cwd=REPO_ROOT, env=env)
    runner.unlink(missing_ok=True)
    if not MANIFEST.exists():
        sys.exit("Recorder wrote no manifest — the pytest run must have died early.")
    cards = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(f"\nRecorded {len(cards)} distinct cards -> {MANIFEST.relative_to(REPO_ROOT)}")
    if proc.returncode != 0:
        print(f"NOTE: pytest exited {proc.returncode}; the manifest still reflects "
              "every card that was loaded before it stopped.")


# ── build mode ────────────────────────────────────────────────────────────────

def build() -> None:
    if not MANIFEST.exists():
        sys.exit(f"No manifest at {MANIFEST} — run with --record first.")
    wanted = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids = {int(c["id"]) for c in wanted}
    src_path = _source_db()

    # Every token, always — all 31 rows.  The engine materialises tokens by NAME
    # at runtime (swu.engine.tokens, raw SQL, not via CardRepository), so any game
    # can need any of them and the recorder never sees those reads.  Cheap
    # insurance against a whole class of "Token card def 'Advantage' not found".
    _tok = sqlite3.connect(f"{src_path.as_uri()}?mode=ro", uri=True)
    try:
        ids |= {
            int(r[0]) for r in _tok.execute(
                "SELECT id FROM cards WHERE type IN "
                "('Token Unit', 'Token Upgrade', 'Credit Token', 'Force Token')"
            )
        }
    finally:
        _tok.close()
    ids = sorted(ids)

    # Never build in place: a half-written fixture that still imports is worse
    # than none at all.
    tmp = FIXTURE_DB.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    FIXTURE_DB.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(f"{src_path.as_uri()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    out = sqlite3.connect(tmp)
    try:
        # Copy the schema verbatim (tables, then indexes) so the fixture answers
        # every query the real database does.
        for kind in ("table", "index"):
            for (sql,) in src.execute(
                "SELECT sql FROM sqlite_master WHERE type=? AND sql IS NOT NULL "
                "AND name NOT LIKE 'sqlite_%'", (kind,)
            ):
                out.execute(sql)

        placeholders = ",".join("?" * len(ids))
        cards = src.execute(
            f"SELECT * FROM cards WHERE id IN ({placeholders}) ORDER BY id", ids
        ).fetchall()
        found = {int(r["id"]) for r in cards}
        missing = [c for c in wanted if int(c["id"]) not in found]
        if missing:
            names = ", ".join(f"{m['set_code']}_{m['card_number']} {m['name']}" for m in missing[:5])
            sys.exit(f"{len(missing)} manifest card(s) absent from the source DB: {names}")

        cols = [d[0] for d in src.execute("SELECT * FROM cards LIMIT 0").description]
        out.executemany(
            f"INSERT INTO cards ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [tuple(r[c] for c in cols) for r in cards],
        )
        for table in CHILD_TABLES:
            rows = src.execute(
                f"SELECT * FROM {table} WHERE card_id IN ({placeholders})", ids
            ).fetchall()
            if not rows:
                continue
            tcols = [d[0] for d in src.execute(f"SELECT * FROM {table} LIMIT 0").description]
            out.executemany(
                f"INSERT INTO {table} ({','.join(tcols)}) "
                f"VALUES ({','.join('?' * len(tcols))})",
                [tuple(r[c] for c in tcols) for r in rows],
            )

        # Artwork is never distributed: blank the paths so a fixture-backed run
        # can't appear to have images, and drop the upstream URLs with them.
        #
        # raw_json is the entire upstream API payload per card — 4.4 MB of the
        # 5 MB, nine tenths of the fixture — and nothing in src/swu reads it.
        # Only the campaign scripts (plan_encoding, verify_encoding) do, and both
        # are corpus-wide tools that need the real database anyway.
        out.execute(
            "UPDATE cards SET image_front_path=NULL, image_back_path=NULL, "
            "image_front_url=NULL, image_back_url=NULL, raw_json=NULL"
        )
        # Mark the database as a deliberate subset.  Code whose invariants are
        # corpus-wide reads this instead of assuming completeness — see
        # swu.cards.reprints.is_partial_db, which would otherwise refuse to import
        # because most reprint keys are absent here.
        out.execute(
            "CREATE TABLE fixture_meta ("
            " is_partial INTEGER NOT NULL,"
            " card_count INTEGER NOT NULL,"
            " built_by   TEXT NOT NULL,"
            " note       TEXT)"
        )
        out.execute(
            "INSERT INTO fixture_meta VALUES (1, ?, 'scripts/make_fixture_db.py', ?)",
            (len(ids),
             "Test fixture: a subset of the card corpus, text and stats only. "
             "NOT a card database — build the real one per docs/pipeline.md."),
        )
        out.commit()
        out.execute("VACUUM")
        out.commit()
    finally:
        out.close()
        src.close()

    tmp.replace(FIXTURE_DB)
    size_kb = FIXTURE_DB.stat().st_size / 1024
    print(f"Wrote {FIXTURE_DB.relative_to(REPO_ROOT)}: {len(ids)} cards, {size_kb:.0f} KB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true",
                    help="re-record the manifest by running the fixture-eligible tests")
    ap.add_argument("pytest_args", nargs="*",
                    help="with --record: pytest targets to record (default: the "
                         "fixture-eligible set from tests/fixture_scope.py)")
    args = ap.parse_args()
    sys.path.insert(0, str(REPO_ROOT))
    if args.record:
        record(args.pytest_args)
    build()


if __name__ == "__main__":
    main()
