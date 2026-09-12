"""Tests for the reprint-duplicate detection + alias mechanism.

Stage 1 built the tooling (the printed-face identity helper, the alias guard,
the --check contract). Stage 2 populated REPRINT_ALIASES from the worklist's
`mirror` bucket, so these tests now also assert — for EVERY alias — that the
reprint resolves to its canonical's exact spec list, the two DB faces are
byte-identical, and the audit classifier now labels the reprint playable
(implemented / escape-hatch). `find_reprints.py --check` must exit 0.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))   # for find_reprints / audit_coverage
sys.path.insert(0, str(ROOT / "src"))       # for swu.*

import audit_coverage as audit  # noqa: E402
import find_reprints  # noqa: E402
from swu.abilities.registry import _ESCAPE_HATCH, _REGISTRY, get_abilities  # noqa: E402
from swu.cards import reprints  # noqa: E402  (import applies the aliases as a side effect)

DB = str(ROOT / "data" / "swu.db")


def _unregistered_keywordless_text_card():
    """A card that is NOT registered, carries functional text, and prints NO keyword.

    Exactly the shape ``verify_playable``'s functional-text guard must flag when such
    a card is (wrongly) filed under ``keyword_deferred``: with no keywords the keyword
    gate passes, so only the text guard can catch it.  Found at run time rather than
    named, so the campaign encoding one more card cannot rot this test; sorted for a
    deterministic pick, and skipped outright if the campaign ever runs out."""
    registered, escape_hatch = audit._load_registry()
    known = registered | escape_hatch
    for card in sorted(audit.load_cards(DB),
                       key=lambda c: (c.set_code, int(c.card_number or 0))):
        if card.card_type in audit.TOKEN_TYPES:
            continue
        if (card.set_code, card.card_number) in known:
            continue
        if card.keywords:
            continue
        if audit.has_functional_text(card.full_text, card.keywords):
            return card
    pytest.skip("no unregistered keyword-free text-bearing card left in the DB")

# Sorted list so the parametrized ids are stable across runs.
ALIASES = sorted(reprints.REPRINT_ALIASES.items())


@pytest.fixture
def out_path():
    """A throwaway --output file path. Uses an OS temp dir (not pytest's
    tmp_path) whose teardown tolerates the Windows WinError-5 cleanup quirk."""
    d = tempfile.mkdtemp(prefix="reprints_")
    try:
        yield Path(d) / "wl.json"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def registry_snapshot():
    """Restore the global registry after a test mutates it (apply_reprint_aliases
    writes into the shared _REGISTRY / _ESCAPE_HATCH)."""
    reg = dict(_REGISTRY)
    esc = set(_ESCAPE_HATCH)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(reg)
    _ESCAPE_HATCH.clear()
    _ESCAPE_HATCH.update(esc)


# ── The printed-face identity helper ─────────────────────────────────────────

class TestIdentityHelper:
    def test_law_93_groups_with_p26_2(self):
        faces = reprints.load_faces(DB)
        assert reprints.face_key(faces[("LAW", "93")]) == \
            reprints.face_key(faces[("P26", "2")])
        assert faces[("LAW", "93")]["name"] == "Rio Durant"

    def test_maul_shadow_collective_group_has_multiple_members(self):
        faces = reprints.load_faces(DB)
        groups: dict[tuple, list] = {}
        for (s, n), f in faces.items():
            if f["type"] in reprints.TOKEN_TYPES:
                continue
            groups.setdefault(reprints.face_key(f), []).append((s, n))
        target = None
        for f in faces.values():
            if f["name"] == "Maul" and (f["subtitle"] or "").startswith("Shadow Collective"):
                target = reprints.face_key(f)
                break
        assert target is not None, "Maul 'Shadow Collective Visionary' not in DB"
        assert len(groups[target]) >= 2

    def test_distinct_same_name_faces_do_not_collide(self):
        # A shared NAME is not enough — the several distinct "Maul" cards must
        # each get their own identity key (whole printed face, not just name).
        faces = reprints.load_faces(DB)
        maul_keys = {
            reprints.face_key(f)
            for f in faces.values()
            if f["name"] == "Maul" and f["type"] not in reprints.TOKEN_TYPES
        }
        maul_faces = [
            f for f in faces.values()
            if f["name"] == "Maul" and f["type"] not in reprints.TOKEN_TYPES
        ]
        # There is more than one distinct Maul face in the DB.
        assert len(maul_keys) >= 2
        assert len(maul_keys) < len(maul_faces)  # ...but some are reprints of each other


# ── The populated alias table (Stage 2) ──────────────────────────────────────

class TestPopulatedTable:
    def test_table_matches_the_worklist_mirror_bucket(self):
        """Every mirror gap in a freshly-built worklist (with the aliases NOT
        applied) must be present in REPRINT_ALIASES, and nothing else may be — i.e.
        the table's KEYS are exactly the mirror bucket, no more and no less. Guards
        against the table drifting from the detector.

        The table's *values* are checked for validity, not for equality with the
        detector's pick.  A face group may contain several registered twins, and
        which one ``_all_mirror_gaps`` nominates as canonical is an artefact of its
        iteration order — it shifted for 22 long-standing entries when
        ``_norm_rules`` (reminder-text stripping) merged previously-separate groups.
        Any registered member of the same printed face is an equally correct
        canonical: ``apply_reprint_aliases`` proves face identity at import, and
        ``test_alias_resolves_to_canonical_spec`` proves the target is registered.
        Re-pointing those 22 to chase the detector's new preference would churn the
        table (and falsify their batch comments) for no behavioural gain."""
        # Build the worklist against the ORIGINAL registry (aliases removed), so
        # the mirror bucket is the pre-Stage-2 set of gaps.
        reg = dict(_REGISTRY)
        esc = set(_ESCAPE_HATCH)
        for rep in reprints.REPRINT_ALIASES:
            _REGISTRY.pop(rep, None)
            _ESCAPE_HATCH.discard(rep)
        try:
            gaps = dict(find_reprints._all_mirror_gaps(find_reprints.build_worklist(DB)))
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(reg)
            _ESCAPE_HATCH.clear()
            _ESCAPE_HATCH.update(esc)
        table = dict(reprints.REPRINT_ALIASES)
        assert set(gaps) == set(table)
        # Each aliased canonical must be a registered twin sharing the reprint's
        # printed face (the detector's own identity function).
        faces = reprints.load_faces(DB)
        for reprint, canonical in table.items():
            assert canonical in reg, (reprint, canonical)
            assert reprints.face_key(faces[reprint]) == reprints.face_key(faces[canonical]), \
                (reprint, canonical)

    def test_apply_is_idempotent_and_counts_all(self):
        assert reprints.apply_reprint_aliases(DB) == len(reprints.REPRINT_ALIASES)

    @pytest.mark.parametrize("reprint, canonical", ALIASES,
                             ids=[f"{r[0]}_{r[1]}" for r, _ in ALIASES])
    def test_alias_resolves_to_canonical_spec(self, reprint, canonical):
        # The aliases were applied at import; the reprint now shares the
        # canonical's exact spec list object.
        assert get_abilities(*reprint) is get_abilities(*canonical)
        assert get_abilities(*canonical) != []

    @pytest.mark.parametrize("reprint, canonical", ALIASES,
                             ids=[f"{r[0]}_{r[1]}" for r, _ in ALIASES])
    def test_alias_faces_are_identical(self, reprint, canonical):
        faces = reprints.load_faces(DB)
        assert reprints.face_key(faces[reprint]) == reprints.face_key(faces[canonical])

    @pytest.mark.parametrize("reprint, canonical", ALIASES,
                             ids=[f"{r[0]}_{r[1]}" for r, _ in ALIASES])
    def test_alias_now_classifies_playable(self, reprint, canonical):
        registered, escape_hatch = audit._load_registry()
        card_index = audit.index_by_set_number(audit.load_cards(DB))
        row = card_index[reprint]
        label = audit.classify(row, registered, escape_hatch)
        assert label in ("implemented", "escape-hatch")
        assert audit.is_playable(label)
        # The reprint's registered-ness must MATCH its canonical's (escape-hatch
        # membership is copied too), so they classify identically.
        crow = card_index[canonical]
        assert label == audit.classify(crow, registered, escape_hatch)


# ── The alias-application guard (still enforced with the table populated) ─────

class TestApplyGuard:
    def test_face_mismatch_raises(self, registry_snapshot, monkeypatch):
        # Alias a reprint onto a DIFFERENT registered card (different face) — the
        # guard must refuse rather than silently alias the wrong card.
        reprint = ("SOR", "251")          # Confiscate
        wrong = ("LAW", "45")             # Zeb Orellios — registered, different face
        assert wrong in _REGISTRY
        monkeypatch.setattr(reprints, "REPRINT_ALIASES", {reprint: wrong})
        with pytest.raises(ValueError, match="face mismatch"):
            reprints.apply_reprint_aliases(DB)

    def test_unregistered_canonical_raises(self, registry_snapshot, monkeypatch):
        # Alliance X-Wing LAW_253 / SOR_237 are the same (vanilla) face but NEITHER
        # is registered (an already_playable group — vanilla cards need no per-card
        # encode) — aliasing onto an unregistered canonical must fail loud.  (Was
        # The Eye of Aldhani SEC_73/SECP_5 until it was encoded in batch 50, which
        # cleared the LAST needs_encoding reprint group, so no text-bearing pair
        # with an unregistered canonical remains — a vanilla pair is the stable
        # stand-in.)
        assert ("SOR", "237") not in _REGISTRY
        monkeypatch.setattr(reprints, "REPRINT_ALIASES", {("LAW", "253"): ("SOR", "237")})
        with pytest.raises(ValueError, match="not registered"):
            reprints.apply_reprint_aliases(DB)


# ── The --check exit-code contract ───────────────────────────────────────────

class TestCheckFlag:
    def test_check_passes_now_that_every_gap_is_aliased(self, monkeypatch, out_path):
        # Stage 2: the alias table covers every mirror gap, so --check exits 0.
        monkeypatch.setattr(sys, "argv", [
            "find_reprints", "--check", "--db", DB,
            "--output", str(out_path),
        ])
        assert find_reprints.main() == 0

    def test_check_fails_if_an_alias_is_removed(self, monkeypatch, out_path):
        # Sanity: remove one alias and --check must catch the now-un-aliased gap.
        # (Build the mirror bucket against the pre-alias registry so a gap exists.)
        reg = dict(_REGISTRY)
        esc = set(_ESCAPE_HATCH)
        for rep in reprints.REPRINT_ALIASES:
            _REGISTRY.pop(rep, None)
            _ESCAPE_HATCH.discard(rep)
        one_short = dict(reprints.REPRINT_ALIASES)
        one_short.pop(next(iter(one_short)))
        try:
            monkeypatch.setattr(reprints, "REPRINT_ALIASES", one_short)
            monkeypatch.setattr(sys, "argv", [
                "find_reprints", "--check", "--db", DB, "--output", str(out_path),
            ])
            assert find_reprints.main() == 1
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(reg)
            _ESCAPE_HATCH.clear()
            _ESCAPE_HATCH.update(esc)

    def test_worklist_written_and_buckets_reconcile(self, monkeypatch, out_path):
        import json
        out = out_path
        monkeypatch.setattr(sys, "argv", [
            "find_reprints", "--db", DB, "--output", str(out),
        ])
        assert find_reprints.main() == 0
        wl = json.loads(out.read_text(encoding="utf-8"))
        # Every group is bucketed exactly once (member/group totals reconcile).
        gc, mc = wl["group_counts"], wl["member_counts"]
        assert sum(mc.values()) == sum(len(e["members"])
                                       for lst in wl["buckets"].values() for e in lst)
        assert sum(gc.values()) == sum(len(lst) for lst in wl["buckets"].values())


# ── The already_playable / keyword_deferred verification (Stage 3) ────────────

class TestVerifyPlayable:
    """Stage 3: prove the two 'no work needed' buckets really need no work, and
    that a keyword-deferred card whose ability is unregistered is NOT hidden in
    keyword_deferred but routed to needs_encoding (a real per-card encode)."""

    def test_verify_playable_finds_no_exceptions(self):
        # Fresh worklist (aliases applied at import), re-verified from scratch.
        wl = find_reprints.build_worklist(DB)
        problems = find_reprints.verify_playable(wl, DB)
        assert problems == [], (
            "already_playable / keyword_deferred members that are not actually "
            f"playable: {problems}"
        )

    def test_verify_playable_flag_exits_zero(self, monkeypatch, out_path):
        monkeypatch.setattr(sys, "argv", [
            "find_reprints", "--verify-playable", "--db", DB,
            "--output", str(out_path),
        ])
        assert find_reprints.main() == 0

    def test_already_playable_members_all_classify_playable(self):
        wl = find_reprints.build_worklist(DB)
        registered, escape_hatch = audit._load_registry()
        idx = audit.index_by_set_number(audit.load_cards(DB))
        checked = 0
        for entry in wl["buckets"]["already_playable"]:
            for m in entry["members"]:
                card = idx[(m["set"], m["number"])]
                label = audit.classify(card, registered, escape_hatch)
                assert audit.is_playable(label), f"{m} → {label}"
                checked += 1
        assert checked == wl["member_counts"]["already_playable"]

    def test_keyword_deferred_members_are_pure_playable_keywords(self):
        # Every keyword_deferred member: all keywords implemented engine-side and
        # no unregistered functional text beyond them.
        wl = find_reprints.build_worklist(DB)
        registered, _ = audit._load_registry()
        idx = audit.index_by_set_number(audit.load_cards(DB))
        for entry in wl["buckets"]["keyword_deferred"]:
            for m in entry["members"]:
                card = idx[(m["set"], m["number"])]
                assert not (card.keywords - find_reprints.IMPL_ENGINE_KEYWORDS), m
                if (m["set"], m["number"]) not in registered:
                    assert not audit.has_functional_text(
                        card.full_text, card.keywords), m

    def test_no_needs_encoding_group_hides_a_free_alias(self):
        # The reprint SWEEP is complete in the sense that matters: no reprint gap
        # sits next to an implemented twin (the mirror bucket is empty, which
        # ``--check`` enforces).
        #
        # This slot used to assert ``needs_encoding == []`` outright — true under the
        # OLD ``face_key``, which compared rules text verbatim.  Stripping reminder
        # text (``_norm_rules``, 2026-08-06) merged faces that differ only in whether
        # the parenthesised reminder was printed, and that surfaced 13 genuine reprint
        # GROUPS whose members had each been an invisible SINGLETON: Captain Tarkin
        # (JTL_161/JTLP_13), Chopper (LAW_55/LAWP_4), Do or Do Not (LOF_175/LOFP_12),
        # Heirloom Lightsaber (LOF_53/P25_105), Jango Fett (LAW_87/LAWP_9), Jedi
        # Consular (LOF_94/LOFP_5), Kazuda Xiono (SEC_151/SECP_13), L3-37
        # (C25_1/JTL_49), Luthen Rael (LOF_68/LOFP_1), Maz Kanata (LAW_74/LAWP_6),
        # Razor Crest (ASH_172/MV26_2), The Elite Squad (SEC_143/SECP_11) and Yoda's
        # Lightsaber (LOF_102/P25_107).  NEITHER member of any of them is implemented,
        # so none is a missed free alias — they are ordinary campaign gaps that the
        # per-set encoding groups will reach, after which the twin gets aliased and
        # the group graduates to ``already_covered``.
        #
        # So the durable invariant is not "the bucket is empty" but "the bucket never
        # contains a group we could have aliased for free" — which stays true both as
        # the campaign shrinks the bucket and if a future DB import grows it.
        wl = find_reprints.build_worklist(DB)
        registered, _ = audit._load_registry()
        for entry in wl["buckets"]["needs_encoding"]:
            hits = [(m["set"], m["number"]) for m in entry["members"]
                    if (m["set"], m["number"]) in registered]
            assert not hits, (entry["name"], hits)   # would be a mirror, not a gap
        assert wl["buckets"]["mirror"] == []
        covered = {(m["set"], m["number"])
                   for e in wl["buckets"]["already_covered"] for m in e["members"]}
        assert ("SEC", "73") in covered
        assert ("SECP", "5") in covered

    def test_verify_playable_flags_an_injected_bad_keyword_deferred(self):
        # Sanity: if a keyword_deferred group carried an UNREGISTERED card that still
        # has functional text beyond its keywords, verify_playable must report it.
        #
        # This stand-in used to NAME the card and so rotted every single batch — The
        # Eye of Aldhani SEC_73, then Long Live the Empire ASH_103, Chimaera ASH_52,
        # Trask Walker ASH_133, Children of the Watch ASH_111 — each dying the moment
        # the campaign encoded it, and finally with nothing left to name once ASH
        # completed in ash-set:29.  It now FINDS a qualifying card at run time (the
        # test_plan_encoding.test_classification_strong_functional_text fix), so it
        # tracks the campaign instead of chasing it.
        card = _unregistered_keywordless_text_card()
        fake = {
            "buckets": {
                "already_playable": [],
                "keyword_deferred": [{
                    "name": card.name,
                    "members": [{"set": card.set_code, "number": card.card_number,
                                 "label": "keyword-deferred"}],
                }],
            },
            "member_counts": {"already_playable": 0, "keyword_deferred": 1},
        }
        problems = find_reprints.verify_playable(fake, DB)
        assert problems and problems[0]["set"] == card.set_code
        assert problems[0]["number"] == card.card_number


class TestAttachRestrictionExemption:
    """A vanilla upgrade whose ONLY text is an "Attach to …" restriction is
    fully playable (the engine parses the restriction and applies printed stats),
    so the canonical functional-text rule must not mistake that declarative clause
    for an ability. This clears Knight's Saber LOF_151/P25_109 from needs_encoding
    into already_playable with no registration (the "register-as-vanilla" fix)."""

    def test_pure_attach_clause_is_not_functional_text(self):
        assert not audit.has_functional_text("Attach to a Jedi non-Vehicle unit.", ())
        assert not audit.has_functional_text("Attach to a Force unit.", ())
        assert not audit.has_functional_text("Attach to a unit that costs 4 or less.", ())

    def test_attach_clause_before_ability_text_stays_functional(self):
        # The terminating period scopes the strip to the restriction sentence, so
        # a real ability after it is still detected.
        assert audit.has_functional_text(
            "Attach to a non-Vehicle unit. Attached unit gains Sentinel.", ())

    def test_knights_saber_classifies_vanilla_and_playable(self):
        registered, escape_hatch = audit._load_registry()
        idx = audit.index_by_set_number(audit.load_cards(DB))
        for key in (("LOF", "151"), ("P25", "109")):
            label = audit.classify(idx[key], registered, escape_hatch)
            assert label == "vanilla", f"{key} → {label}"
            assert audit.is_playable(label)

    def test_knights_saber_group_in_already_playable(self):
        wl = find_reprints.build_worklist(DB)
        ne = {e["name"] for e in wl["buckets"]["needs_encoding"]}
        ap = {e["name"] for e in wl["buckets"]["already_playable"]}
        assert "Knight's Saber" not in ne
        assert "Knight's Saber" in ap
