"""The coverage audit must never write a report from an empty ability registry.

``audit_coverage._load_registry`` returns empty sets when the card modules fail
to import.  Before the guard, ``main()`` then overwrote
``docs/coverage_report.md`` with "Registered in ability registry: 0" and every
card labelled unimplemented, without any warning.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_coverage as A  # noqa: E402


@pytest.fixture
def empty_registry(monkeypatch):
    monkeypatch.setattr(A, "_load_registry", lambda: (set(), set()))


def test_main_refuses_to_write_with_an_empty_registry(empty_registry, monkeypatch, tmp_path):
    db = tmp_path / "swu.db"
    db.write_bytes(b"")              # main() only checks the path exists before the guard
    out = tmp_path / "coverage_report.md"
    monkeypatch.setattr(sys, "argv", ["audit_coverage", "--db", str(db), "--output", str(out)])
    with pytest.raises(SystemExit) as exc:
        A.main()
    assert "registry is empty" in str(exc.value)
    assert not out.exists()


def test_deck_audit_refuses_an_empty_registry(empty_registry, tmp_path):
    with pytest.raises(SystemExit, match="registry is empty"):
        A.audit_deck(tmp_path / "deck.json", str(tmp_path / "swu.db"))


def test_guard_passes_a_populated_registry():
    A._require_registry({("SOR", "1")})   # returns without exiting
