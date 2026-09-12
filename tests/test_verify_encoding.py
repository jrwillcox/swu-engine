"""Tests for the Phase 7 verifier (scripts/verify_encoding.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import plan_encoding as P  # noqa: E402
import verify_encoding as V  # noqa: E402

DECK = str(_ROOT / "tests" / "fixtures" / "shd_han_solo.json")
DB = str(_ROOT / "data" / "swu.db")


@pytest.fixture
def info():
    _, groups, meta = P.plan(DECK, None, DB, slug_override="shd-han-solo")
    return {"groups": groups, "meta": meta}


def test_progress_accounting_matches_audit(info):
    """Verifier progress is consistent with the planner's strong classifier:
    every group has a positive card total and a done count within [0, total].

    (The Smuggle keyword group shd-han-solo:01 is now partly encoded, so a
    blanket 'all done == 0' no longer holds; the invariant that matters is that
    progress accounting stays internally consistent.)"""
    prog = info["meta"]["progress"]
    assert all(p["total"] > 0 for p in prog.values())
    assert all(0 <= p["done"] <= p["total"] for p in prog.values())


def test_next_group_respects_dependencies(info):
    groups = info["groups"]
    prog = {g.gid: {"done": 0, "total": len(g.cards)} for g in groups}
    nxt = V._next_group(groups, prog)
    # First suggestion is the lowest-seq group with no deps (a keyword group).
    assert nxt.kind == "keyword"
    assert nxt.depends_on == []

    # An ability group that depends on a keyword group is NOT suggested until the
    # keyword group is complete.
    dep_group = next((g for g in groups if g.depends_on), None)
    if dep_group:
        for d in dep_group.depends_on:
            prog[d] = {"done": prog[d]["total"], "total": prog[d]["total"]}
        # mark all earlier groups done except dep_group
        for g in groups:
            if g.seq < dep_group.seq and g.gid not in dep_group.depends_on:
                prog[g.gid] = {"done": prog[g.gid]["total"], "total": prog[g.gid]["total"]}
        nxt2 = V._next_group(groups, prog)
        assert all(d in {gg.gid for gg in groups
                         if prog[gg.gid]["done"] == prog[gg.gid]["total"]}
                   for d in nxt2.depends_on)


def test_graduation_blocks_when_incomplete(info, tmp_path, monkeypatch):
    """A deck that isn't 100% implemented must NOT graduate, and must reach that
    verdict WITHOUT shelling out to the fast/medium/soak subprocesses.

    This guard matters because _graduate's verification subprocesses run
    ``pytest tests/`` — which re-collects THIS test file.  If the incomplete
    short-circuit ever regressed (or, as happened when shd-han-solo reached 100%
    playable, the fixture deck became complete), _graduate would spawn a nested
    pytest run that re-invokes this test, recursing without bound and hanging the
    whole suite.  shd-han-solo is fully implemented today, so we synthesise the
    gap rather than relying on the demo deck being incomplete, and we assert no
    subprocess is launched on the incomplete path."""
    monkeypatch.setattr(V, "DECKS_STATUS", tmp_path / "decks_status.md")
    info["meta"]["playable_deck"] = info["meta"]["total_deck"] - 1

    def _no_subprocess(cmd):
        raise AssertionError(
            f"_graduate spawned a subprocess for an incomplete deck: {cmd}")

    monkeypatch.setattr(V, "_run", _no_subprocess)
    passed = V._graduate("shd-han-solo", info, soak_games=1)
    assert passed is False
    assert not (tmp_path / "decks_status.md").exists()


def test_graduation_passes_when_complete_and_green(info, tmp_path, monkeypatch):
    """A 100%-playable deck whose verification subprocesses all pass graduates
    and is marked shippable.  The subprocesses are mocked (`_run` returns a
    green result) — a real run would recursively invoke pytest from inside the
    suite, so this branch must never spawn the actual fast/medium/soak runs in a
    unit test."""
    monkeypatch.setattr(V, "DECKS_STATUS", tmp_path / "decks_status.md")
    info["meta"]["playable_deck"] = info["meta"]["total_deck"]  # force complete

    calls: list[list[str]] = []

    def _fake_run(cmd):
        calls.append(cmd)
        return 0, "0 failures"

    monkeypatch.setattr(V, "_run", _fake_run)
    passed = V._graduate("shd-han-solo", info, soak_games=1)
    assert passed is True
    assert calls, "graduation should have run the verification subprocesses"
    assert (tmp_path / "decks_status.md").exists()
    assert "shippable" in (tmp_path / "decks_status.md").read_text(encoding="utf-8")


def test_mark_shippable_writes_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "DECKS_STATUS", tmp_path / "decks_status.md")
    V._mark_shippable("my-deck", 52)
    txt = (tmp_path / "decks_status.md").read_text(encoding="utf-8")
    assert "my-deck" in txt and "shippable" in txt
    # Idempotent / additive: a second deck is appended, first preserved.
    V._mark_shippable("other-deck", 52)
    txt = (tmp_path / "decks_status.md").read_text(encoding="utf-8")
    assert "my-deck" in txt and "other-deck" in txt
