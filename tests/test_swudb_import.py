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


def _first_unimplemented_text_bearing_unit() -> str | None:
    """A ``SET_NUM`` id for some unit that still has ability text and no registered
    ability, or None once the encoding campaign has covered them all.  Deterministic
    (sorted), so a failure always names the same card."""
    import swu.cards  # noqa: F401 — populates the ability registry
    from swu.abilities.registry import get_abilities
    from swu.cards.repository import CardRepository
    from scripts.audit_coverage import has_functional_text
    repo = CardRepository(require_corpus_db())
    cards = [cd for cd in repo.iter_all()
             if type(cd).__name__ == "Unit" and (cd.text or "").strip()]
    for cd in sorted(cards, key=lambda c: (c.set_code or "", c.card_number or "")):
        # FUNCTIONAL text, not merely any text: a pure-keyword card ("Ambush /
        # Restore 1") is correctly NOT reported as a gap by the importer, so
        # picking one would fail the caller's assertion — Pathfinder Sergeant
        # ASH_106 did exactly that once the campaign encoded past the ASH units
        # ahead of it.
        if not has_functional_text(cd.text, getattr(cd, "keywords", ()) or ()):
            continue
        if not get_abilities(cd.set_code or "", str(cd.card_number)):
            return f"{cd.set_code}_{cd.card_number}"
    return None


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


def test_import_reports_unimplemented_text_bearing_card(repo, tmp_path):
    """An imported deck containing a card with unimplemented ability text reports
    it as a gap (the core value of the import tool — it doesn't matter that this
    synthetic deck isn't construction-legal)."""
    from swu.web.swudb_import import import_deck
    # The stand-in gap card is DISCOVERED, not hard-coded: every hard-coded choice
    # so far (SOR_103 Rebel Assault, then TWI_47 Satine Kryze) has rotted the moment
    # the encoding campaign reached it.  Pick any unit that still has ability text
    # and no registration; skip once the campaign has encoded them all.
    card_id = _first_unimplemented_text_bearing_unit()
    if card_id is None:
        pytest.skip("no unimplemented text-bearing unit left to stand in for a gap")
    data = {"leader": {"id": "SHD_13"}, "base": {"id": "SHD_24"},
            "deck": [{"id": card_id, "count": 3}]}
    out = tmp_path / "synthetic.json"
    report = import_deck(data, repo, write_to=out, slug="synthetic")

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
