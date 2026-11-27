"""A made-up, unencoded card for tests that need a gap in the card pool.

The planner, the reprint checker and the SWUDB importer all have tests that need
a card with ability text and no registered ability. Those tests used to find a
real one at run time, so they all skipped once the encoding campaign had covered
the whole database. Until the next set release adds real gaps, they would test
nothing.

:func:`synthetic_gap_db` copies the real card corpus to a temporary file and adds
one invented card to it, so these tests always have a gap to work with:

* set ``ZZT`` (no real set uses it), card number ``1``;
* a non-unique Unit with a When Played ability and no keywords;
* nothing in the ability registry, so every classifier calls it text-bearing.

The copy is made once per test session. It starts from
:func:`tests.dbpath.require_corpus_db`, so it still skips when there is no corpus
(the fixture DB and the no-DB CI step).
"""
from __future__ import annotations

import atexit
import functools
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tests.dbpath import require_corpus_db

GAP_SET = "ZZT"
GAP_NUMBER = "1"
GAP_ID = f"{GAP_SET}_{GAP_NUMBER}"
GAP_NAME = "Synthetic Gap Trooper"
GAP_TEXT = "When Played: Deal 2 damage to an enemy ground unit."


@functools.lru_cache(maxsize=1)
def _build() -> str:
    src = require_corpus_db()
    tmp_dir = Path(tempfile.mkdtemp(prefix="swu_synthetic_gap_"))
    atexit.register(shutil.rmtree, tmp_dir, ignore_errors=True)
    dst = tmp_dir / "swu_with_gap.db"

    with sqlite3.connect(src) as source, sqlite3.connect(dst) as target:
        source.backup(target)
    con = sqlite3.connect(dst)
    try:
        if con.execute("SELECT 1 FROM cards WHERE set_code=?", (GAP_SET,)).fetchone():
            raise RuntimeError(f"set code {GAP_SET} is now real; pick another for the synthetic gap")
        card_id = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM cards").fetchone()[0]
        con.execute(
            "INSERT INTO cards (id, card_uid, set_code, set_name, card_number, name, type,"
            " rarity, cost, power, hp, text, is_unique)"
            " VALUES (?, ?, ?, 'Synthetic Test Set', ?, ?, 'Unit', 'Common', 3, 2, 3, ?, 0)",
            (card_id, f"synthetic-{card_id}", GAP_SET, GAP_NUMBER, GAP_NAME, GAP_TEXT),
        )
        con.execute("INSERT INTO card_aspects (card_id, position, name) VALUES (?, 0, 'Command')",
                    (card_id,))
        con.execute("INSERT INTO card_traits (card_id, name) VALUES (?, 'Trooper')", (card_id,))
        con.execute("INSERT INTO card_arenas (card_id, name) VALUES (?, 'Ground')", (card_id,))
        con.commit()
    finally:
        con.close()
    return str(dst)


def synthetic_gap_db() -> str:
    """Path to a copy of the corpus that also holds the made-up gap card ``ZZT_1``."""
    return _build()
