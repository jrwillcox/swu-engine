"""
Start-screen deck registry — the graduated-deck layer of the web catalog.

``scripts/verify_encoding.py <slug> --graduate`` calls
``swu.web.decks.register_ui_deck`` on a full pass so a newly shippable deck is
selectable on the start screen without a code edit.  These tests pin that seam:
the registry is read into ``catalog()``, built-ins win on a clash, missing
fixtures are dropped, and ``resolve_deck`` resolves a graduated key.

The registry file is redirected to a tmp path via ``SWU_UI_DECKS`` so the real
``data/ui_decks.json`` is never touched.
"""
from __future__ import annotations


import pytest

pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from swu.web import decks


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("SWU_UI_DECKS", str(tmp_path / "ui_decks.json"))
    return tmp_path / "ui_decks.json"


def _fixture_name() -> str:
    # Any real fixture that exists on disk so the existence filter passes.
    fixtures = decks._fixtures_dir()
    for cand in ("moff_gideon.json", "starter_luke.json"):
        if (fixtures / cand).exists():
            return cand
    pytest.skip("no deck fixture available")


def test_register_then_appears_in_catalog(registry):
    name = _fixture_name()
    decks.register_ui_deck(
        key="zzz-test-deck", label="Test Deck — Aspect (Set)",
        leader_name="Test Leader", base_name="Test Base", filename=name,
    )
    cat = {d.key: d for d in decks.catalog()}
    assert "zzz-test-deck" in cat
    assert cat["zzz-test-deck"].leader_name == "Test Leader"
    # built-ins still present
    assert "luke" in cat and "vader" in cat


def test_register_is_idempotent_upsert(registry):
    name = _fixture_name()
    decks.register_ui_deck(key="k", label="A", leader_name="L", base_name="B", filename=name)
    decks.register_ui_deck(key="k", label="B-updated", leader_name="L", base_name="B", filename=name)
    rows = [d for d in decks.catalog() if d.key == "k"]
    assert len(rows) == 1
    assert rows[0].label == "B-updated"


def test_builtin_wins_on_key_clash(registry):
    name = _fixture_name()
    # Re-register a built-in key pointing elsewhere; the built-in must win.
    decks.register_ui_deck(
        key="luke", label="HIJACKED", leader_name="X", base_name="Y", filename=name,
    )
    luke = next(d for d in decks.catalog() if d.key == "luke")
    assert luke.label != "HIJACKED"


def test_missing_fixture_is_dropped(registry):
    decks.register_ui_deck(
        key="ghost", label="Ghost", leader_name="L", base_name="B",
        filename="does_not_exist_xyz.json",
    )
    assert "ghost" not in {d.key for d in decks.catalog()}


def test_resolve_deck_resolves_graduated_key(registry):
    from tests.dbpath import require_db
    require_db()
    name = _fixture_name()
    decks.register_ui_deck(
        key="grad-key", label="Grad", leader_name="L", base_name="B", filename=name,
    )
    cards = decks.resolve_deck("grad-key")
    assert len(cards) > 0


def test_corrupt_registry_is_ignored(registry):
    registry.write_text("{ not json", encoding="utf-8")
    # Built-ins still resolve; no crash on a corrupt file.
    assert "luke" in {d.key for d in decks.catalog()}
