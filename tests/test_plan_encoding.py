"""Tests for the Phase 7 encoding planner (scripts/plan_encoding.py).

Verifies on a fixture deck with a known mix: correct classification, deterministic
clustering, group-size cap, separation of keyword/ability/new-primitive kinds,
dependency ordering, valid emitted artifacts, and re-run progress that doesn't
clobber a completed spec.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import plan_encoding as P  # noqa: E402
import audit_coverage as A  # noqa: E402

DECK = str(_ROOT / "tests" / "fixtures" / "shd_han_solo.json")
DB = str(_ROOT / "data" / "swu.db")


@pytest.fixture
def planned():
    slug, groups, meta = P.plan(DECK, None, DB)
    return slug, groups, meta


def test_slug_from_fixture(planned):
    slug, _, _ = planned
    assert slug == "shd-han-solo"


def test_determinism():
    """Same input ⇒ identical groups (ids, themes, membership)."""
    s1, g1, _ = P.plan(DECK, None, DB)
    s2, g2, _ = P.plan(DECK, None, DB)
    assert s1 == s2
    sig = lambda gs: [(g.gid, g.kind, g.theme, [c.cid for c in g.cards],
                       sorted(g.new_primitives), g.depends_on) for g in gs]
    assert sig(g1) == sig(g2)


def test_group_kinds_separated(planned):
    _, groups, _ = planned
    keyword_groups = [g for g in groups if g.kind == "keyword"]
    ability_groups = [g for g in groups if g.kind == "ability"]
    assert {g.keyword for g in keyword_groups} == {"Smuggle", "Bounty"}
    assert ability_groups, "expected at least one ability group"
    # Escalation group exists and is flagged with new primitives.
    esc = [g for g in ability_groups if g.new_primitives]
    assert esc, "expected a flagged new-primitive (escalation) group"


def test_group_size_cap(planned):
    _, groups, _ = planned
    for g in groups:
        if g.kind == "ability":
            assert len(g.cards) <= P.ABILITY_GROUP_CAP


def test_keyword_group_membership(planned):
    _, groups, _ = planned
    smuggle = next(g for g in groups if g.keyword == "Smuggle")
    cids = {c.cid for c in smuggle.cards}
    # Real Smuggle cards from the demo deck.
    assert {"SHD_148", "SHD_160", "SHD_252"} <= cids


def test_ordering_keyword_first_escalation_last(planned):
    _, groups, _ = planned
    seqs = [g.seq for g in groups]
    assert seqs == sorted(seqs), "groups must be in ascending seq order"
    kinds_in_order = [g.kind for g in groups]
    # All keyword groups precede all ability groups.
    last_kw = max((i for i, g in enumerate(groups) if g.kind == "keyword"), default=-1)
    first_ability = min((i for i, g in enumerate(groups) if g.kind == "ability"),
                        default=len(groups))
    assert last_kw < first_ability
    # The escalation (new-primitive) group is ordered last among ability groups.
    ability = [g for g in groups if g.kind == "ability"]
    assert ability[-1].new_primitives, "escalation group should sort last"


def test_dependency_recorded_for_keyword_blocked_cards(planned):
    """An ability card that also carries a deferred keyword depends on that
    keyword's group (if it surfaces as an ability group at all)."""
    _, groups, _ = planned
    by_gid = {g.gid: g for g in groups}
    for g in groups:
        for dep in g.depends_on:
            assert dep in by_gid
            assert by_gid[dep].kind == "keyword"


def _campaign_set_order():
    """The campaign's own set order, imported from the queue walker.

    Read from ``scripts/next_group.SET_ORDER`` rather than duplicated here, so the
    run-time set choices below follow the campaign automatically instead of rotting
    the moment their hand-written last entry is completed.
    """
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import next_group  # noqa: PLC0415 — deliberately late (path juggling above)
    return list(next_group.SET_ORDER)


def test_classification_strong_functional_text():
    """Plain-effect text (no trigger word) must classify text-bearing, not vanilla.

    This test used to pin two named cards and assert exactly "text-bearing", so it
    rotted every time the campaign encoded them — SHD_178, then SHD_247, SHD_159,
    SHD_180, SHD_144, SHD_112, SHD_212, SHD_205, SHD_109, and finally SHD_224/256
    when shd-set:22 completed the set.  Both causes of that rot are now gone: it
    *finds* cards exhibiting the property rather than naming them, and it asserts
    the property actually under test — such a card is never classified **vanilla**
    (the pre-2026-06-17 `_has_ability_text` trigger-word pattern list called every
    plain-effect card vanilla, over-reporting "playable" by ~700 cards).  Whether a
    given card is text-bearing or already implemented is the campaign's business,
    not this rule's.
    """
    reg, esc = P.audit._load_registry()
    trigger_words = ("when ", "on attack", "action:", "action [", "constant:",
                     "while ", "if you", "each time", "attack with")
    found = []
    for set_code in _campaign_set_order():
        _slug, groups, _meta = P.plan(None, set_code, DB)
        for det in (c for g in groups for c in g.cards):
            text = (det.text or "").lower()
            if not text.strip() or any(w in text for w in trigger_words):
                continue
            found.append(det)
        if found:
            break

    assert found, "no trigger-word-free text-bearing card found to exercise the rule"
    for det in found:
        assert P.classify_card(det, reg, esc) != "vanilla", det.cid


def test_classification_keyword_deferred():
    reg, esc = P.audit._load_registry()
    details = P.load_details(DB, [("SHD", "161"), ("SHD", "165")])
    # SHD_161's control-change primitive landed in the dedicated framework
    # session for group shd-han-solo:02 (When Played hands the unit to an
    # opponent via actions.change_control; its Bounty replays it from the owner's
    # discard), so it is now implemented.
    assert P.classify_card(details[("SHD", "161")], reg, esc) == "implemented"
    # SHD_165's Bounty was implemented in group shd-han-solo:02 (WhenDefeated +
    # SOURCE_EXHAUSTED → heal the opponent's base).
    assert P.classify_card(details[("SHD", "165")], reg, esc) == "implemented"


# NOTE: tests below that emit into a fresh tmp_path ENCODING_DIR plan a whole
# *set*, not the shd-han-solo demo deck.  The demo deck is 100% implemented, so a
# from-scratch plan of it finds zero gaps and yields zero groups — which would make
# these reconcile/emit tests vacuous (and IndexError on groups[0]).  They need a
# gap-bearing input, so the set is CHOSEN AT RUN TIME rather than hard-coded: SHD
# was the hard-coded choice until shd-set:22 completed it and took these tests down
# with it.
#
# ⚠️ The replacement was a hand-written candidate TUPLE, which rotted the same way
# the moment the campaign completed its last entry (IBH, ibh-set:04 — these three
# tests silently went to SKIP).  The candidate list is now READ FROM THE CAMPAIGN
# ITSELF (``scripts/next_group.SET_ORDER``), so every set the walker will ever visit
# is a candidate and this can only go quiet when the whole campaign is finished —
# at which point skipping really is the right answer.


def _set_with_gaps():
    """The first campaign set that still yields gap groups (skip if none do)."""
    for set_code in _campaign_set_order():
        _slug, groups, _meta = P.plan(None, set_code, DB)
        if groups:
            return set_code
    pytest.skip("no set left with gap groups — the campaign has encoded them all")


def test_emit_valid_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "ENCODING_DIR", tmp_path)
    set_with_gaps = _set_with_gaps()
    slug, groups, meta = P.plan(None, set_with_gaps, DB)
    assert groups, f"expected the {set_with_gaps} set to yield gap groups"
    out_dir = P.emit(slug, groups, meta)
    assert (out_dir / "MANIFEST.md").exists()
    mj = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert mj["deck_slug"] == slug
    assert len(mj["groups"]) == len(groups)
    for g in groups:
        assert (out_dir / f"{g.file_slug}.md").exists()
        # Each manifest group references an existing spec file and a paste id.
    man = (out_dir / "MANIFEST.md").read_text(encoding="utf-8")
    for g in groups:
        assert g.gid in man


def test_rerun_stable_ids_no_clobber(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "ENCODING_DIR", tmp_path)
    # Whole-set source (see the _set_with_gaps note above): the demo deck is fully
    # implemented now and yields no groups from scratch.
    set_with_gaps = _set_with_gaps()
    slug, groups, meta = P.plan(None, set_with_gaps, DB)
    P.emit(slug, groups, meta)
    gids_first = [g.gid for g in groups]
    assert gids_first, f"expected the {set_with_gaps} set to yield gap groups"

    # Sentinel: hand-edit a not-yet-complete spec; a re-run must rewrite it
    # (group still incomplete) — but ids stay stable via reconcile.
    slug2, groups2, meta2 = P.plan(None, set_with_gaps, DB)
    assert [g.gid for g in groups2] == gids_first

    # No-clobber: a spec whose group is fully done is preserved verbatim.
    done_group = groups2[0]
    spec = tmp_path / slug2 / f"{done_group.file_slug}.md"
    spec.write_text("SENTINEL — already encoded", encoding="utf-8")
    meta2["progress"][done_group.gid] = {
        "done": len(done_group.cards), "total": len(done_group.cards)}
    P.emit(slug2, groups2, meta2)
    assert spec.read_text(encoding="utf-8") == "SENTINEL — already encoded"


def test_set_code_input(tmp_path, monkeypatch):
    """The whole-set input path resolves and produces groups.

    Isolated from the live campaign artifacts (``encoding/<slug>-set``) by pointing
    ``ENCODING_DIR`` at a tmp dir, so the planner reconciles against no prior
    manifest and clusters from scratch.
    """
    monkeypatch.setattr(P, "ENCODING_DIR", tmp_path)
    # A completed set still resolves and reports its size; it just yields no groups.
    slug, groups, meta = P.plan(None, "SHD", DB)
    assert slug == "shd-set"
    assert meta["total_deck"] > 200

    # A set with gaps yields groups, and only the two campaign kinds.
    set_with_gaps = _set_with_gaps()
    gslug, ggroups, _gmeta = P.plan(None, set_with_gaps, DB)
    assert gslug == f"{set_with_gaps.lower()}-set"
    assert ggroups, f"expected the {set_with_gaps} set to yield gap groups"
    # Every printed keyword is now modelled engine-side (Support, the last one, landed
    # with ash-set:01), so PHASE3_KEYWORDS is empty and NO set plans a keyword group
    # any more — every remaining gap group is an ability group.
    assert all(g.kind == "ability" for g in ggroups)
    assert not A.PHASE3_KEYWORDS

    # ASH used to be the one set that planned a keyword group; it is now COMPLETE
    # (264/264, finished in ash-set:29), so it resolves and reports its size while
    # yielding no groups at all — the same shape as SHD above.
    aslug, agroups, ameta = P.plan(None, "ASH", DB)
    assert aslug == "ash-set"
    assert ameta["total_deck"] > 200
    assert agroups == []
