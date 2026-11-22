"""The hand-maintained base → planet table (``swu.cards.base_planets``).

The planet is printed only on a base's art, so the table is read by hand.  The
guard below makes a release that adds bases fail loudly until they are read and
added, rather than letting "If you control a Naboo base" quietly read False.
"""
from __future__ import annotations

import sqlite3

from swu.cards.base_planets import BASE_PLANETS, base_planet


def test_every_base_in_the_card_db_has_a_planet():
    from tests.dbpath import require_corpus_db
    con = sqlite3.connect(require_corpus_db())
    try:
        rows = con.execute(
            "SELECT set_code, card_number, name FROM cards WHERE type='Base'").fetchall()
    finally:
        con.close()
    assert rows, "the card DB holds no bases at all"
    missing = [f"{s}_{n} {name}" for s, n, name in rows if (s, str(n)) not in BASE_PLANETS]
    assert not missing, (
        "bases with no planet in swu/cards/base_planets.py — read the planet from "
        f"the card art and add them: {missing}")


def test_base_planet_reads_only_bases():
    from tests.test_sor_cards import _make_state
    from tests.test_fortify import _unit_def
    state = _make_state()
    test_base = state.player_by_id("P0").base_instance.card_def
    assert base_planet(test_base) is None          # the synthetic TST base
    assert base_planet(_unit_def()) is None        # not a base at all
