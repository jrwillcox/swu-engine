"""
Card-explorer catalog tests — the backend surface behind the explorer screen.

Exercise the assembled catalog directly and over HTTP: every card carries the
filter facets and a ``playable`` flag, the canonical classifier is honoured,
tokens are excluded, and deck membership is wired to the catalog decks.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from fastapi.testclient import TestClient

from swu.web.app import app
from swu.web.explorer import build_catalog
from tests.dbpath import require_db


@pytest.fixture(autouse=True)
def _card_db():
    """Every test here reads the card database: skip cleanly without one."""
    require_db()


@pytest.fixture()
def client():
    return TestClient(app)


def test_catalog_assembles_with_facets():
    cat = build_catalog()
    assert cat["cards"], "expected a non-empty catalog"
    # Facets are present and non-empty.
    for facet in ("sets", "types", "aspects", "keywords", "traits", "decks"):
        assert cat[facet], f"facet {facet} should not be empty"
    # Every card has the explorer fields.
    sample = cat["cards"][0]
    for key in ("id", "set_code", "card_number", "name", "type",
                "aspects", "keywords", "traits", "status", "playable", "decks"):
        assert key in sample


def test_tokens_are_excluded():
    cat = build_catalog()
    token_types = {"Token Unit", "Token Upgrade", "Credit Token", "Force Token"}
    assert not any(c["type"] in token_types for c in cat["cards"])


def test_playable_matches_classifier():
    """``playable`` must agree with audit_coverage.is_playable on the status."""
    from scripts.audit_coverage import is_playable
    cat = build_catalog()
    for c in cat["cards"]:
        assert c["playable"] == is_playable(c["status"])


def test_known_implemented_card_is_playable():
    # Luke Skywalker (SOR 5) is an implemented leader → available to play.
    cat = build_catalog()
    luke = next(c for c in cat["cards"] if c["set_code"] == "SOR" and c["card_number"] == "5")
    assert luke["playable"] is True
    assert luke["name"] == "Luke Skywalker"


def test_deck_membership_links_to_catalog_decks():
    cat = build_catalog()
    deck_keys = {d["key"] for d in cat["decks"]}
    # At least one card should belong to the built-in luke starter, and every
    # recorded membership must reference a real catalog deck.
    seen = set()
    for c in cat["cards"]:
        for k in c["decks"]:
            seen.add(k)
            assert k in deck_keys
    assert "luke" in seen


def test_no_two_cards_share_an_image_file():
    """Leader-vs-Token (set, number) collisions must not map to the same art.

    Historically image files were named by card number, so a Leader and the Token
    sharing its number wrote / pointed at one physical file (Iden Versio rendering
    as a Shield token). ``scripts/fix_image_collisions.py`` gives every card its
    own id-based file; this guards against the regression.
    """
    import sqlite3
    from collections import Counter

    con = sqlite3.connect(str(require_db()))
    try:
        fronts = Counter(
            p for (p,) in con.execute(
                "SELECT image_front_path FROM cards WHERE image_front_path IS NOT NULL"
            )
        )
        backs = Counter(
            p for (p,) in con.execute(
                "SELECT image_back_path FROM cards WHERE image_back_path IS NOT NULL"
            )
        )
    finally:
        con.close()
    dup_front = [p for p, n in fronts.items() if n > 1]
    dup_back = [p for p, n in backs.items() if n > 1]
    assert not dup_front, f"shared front image files: {dup_front[:5]}"
    assert not dup_back, f"shared back image files: {dup_back[:5]}"


def test_catalog_endpoint(client):
    from tests.dbpath import skip_on_fixture
    skip_on_fixture("the catalog is assembled from every card in the DB")
    r = client.get("/api/catalog/cards")
    assert r.status_code == 200
    body = r.json()
    assert body["cards"] and body["sets"] and body["decks"]
    # The image endpoint key (card id) round-trips for a card that has art.
    with_img = next((c for c in body["cards"] if c["image_url"]), None)
    assert with_img is not None
    ri = client.get(f"/api/cards/{with_img['id']}/image")
    assert ri.status_code == 200
