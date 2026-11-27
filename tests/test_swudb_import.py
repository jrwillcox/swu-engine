"""SWUDB import tests (Phase 7, Part D)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.dbpath import require_corpus_db

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def repo():
    from swu.cards.repository import CardRepository
    return CardRepository(require_corpus_db())


def _load(name):
    return json.loads((_ROOT / "tests" / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gap_repo():
    """A repository over a copy of the corpus that also holds the made-up,
    unencoded unit ``ZZT_1`` (``tests/synthetic_gap.py``)."""
    from swu.cards.repository import CardRepository
    from tests.synthetic_gap import synthetic_gap_db
    return CardRepository(synthetic_gap_db())


def test_import_han_solo_deck_now_fully_playable(repo, tmp_path):
    """The shd-han-solo deck is fully encoded — every card is playable, including
    the former last gap Armed to the Teeth (SHD_175, the upgrade-grants-host-a-
    triggered-ability primitive).  Importing it reports zero gaps."""
    from swu.web.swudb_import import import_deck
    data = _load("shd_han_solo")
    out = tmp_path / "shd_han_solo.json"
    report = import_deck(data, repo, write_to=out, slug="shd-han-solo")

    assert report.legal is True            # 1 leader + 1 base + 50 cards
    assert report.total_cards == 52
    assert report.ok is True               # fully playable now
    assert report.unimplemented == []
    assert report.playable_cards == report.total_cards
    # Fixture written + planner hint emitted regardless of gaps.
    assert out.exists()
    assert report.planner_hint and "plan_encoding.py" in report.planner_hint


def test_import_reports_unimplemented_text_bearing_card(gap_repo, tmp_path):
    """An imported deck containing a card with unimplemented ability text reports
    it as a gap (the core value of the import tool — it doesn't matter that this
    synthetic deck isn't construction-legal).

    Every real stand-in (SOR_103, then TWI_47, then whatever was left) rotted as
    the campaign encoded it, and the whole corpus is encoded now, so the gap is
    the made-up unit ``ZZT_1``."""
    from swu.web.swudb_import import import_deck
    from tests.synthetic_gap import GAP_ID
    card_id = GAP_ID
    data = {"leader": {"id": "SHD_13"}, "base": {"id": "SHD_24"},
            "deck": [{"id": card_id, "count": 3}]}
    out = tmp_path / "synthetic.json"
    report = import_deck(data, gap_repo, write_to=out, slug="synthetic")

    ids = {u["id"] for u in report.unimplemented}
    assert card_id in ids
    gap = next(u for u in report.unimplemented if u["id"] == card_id)
    assert gap["label"] == "text-bearing" and gap["count"] == 3
    assert report.ok is False              # has a gap → not fully playable
    assert report.planner_hint and "plan_encoding.py" in report.planner_hint


def test_import_shipped_deck_is_fully_playable(repo):
    """The shipped Luke starter has zero unimplemented cards (the import's core
    value).  (Its `legal` flag may be False — these test fixtures aren't faithful
    precons and trip validate_decklist's uniqueness rule; that's orthogonal.)"""
    from swu.web.swudb_import import import_deck
    report = import_deck(_load("starter_luke"), repo)
    assert report.unimplemented == []
    assert report.playable_cards == report.total_cards


def test_fetch_swudb_deck_injectable():
    from swu.web.swudb_import import fetch_swudb_deck
    sentinel = {"leader": {"id": "SOR_5"}, "base": {"id": "SOR_29"}, "deck": []}
    got = fetch_swudb_deck("https://swudb.com/deck/abc123",
                           fetch_fn=lambda ref: sentinel)
    assert got is sentinel


def test_import_endpoint(tmp_path, monkeypatch):
    from tests.dbpath import require_db
    require_db()
    from tests.dbpath import skip_on_fixture
    skip_on_fixture("importing a real decklist needs every card it names")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from swu.web.app import app
    client = TestClient(app)
    resp = client.post("/api/import/swudb",
                       json={"deck": _load("shd_han_solo"), "name": "han demo"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # shd-han-solo is fully encoded now → legal and fully playable, no gaps.
    assert body["legal"] is True and body["ok"] is True
    assert body["unimplemented"] == []
