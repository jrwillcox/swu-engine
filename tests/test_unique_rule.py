"""
The Unique Rule + deck copy-limits (audit remediation, 2026-07-09).

Covers the three fixes made after auditing the code against the official SWU
uniqueness rules:

1. Deck copy-limit is 3 per card *regardless of uniqueness* (the deckbuilding
   "unique" rule does NOT reduce the copy cap; only in-play does), keyed on the
   full name (title + subtitle) so different-subtitle same-title cards count
   separately and reprints (same name across sets) count together.
   - ``swu.cards.decklist.validate_decklist`` / ``build_vanilla_deck``
   - ``swu.cards.deckrules.deck_errors``

2. The in-play Unique Rule: a player may not control two units/upgrades with the
   same full name that are unique; when they do, the player keeps one and defeats
   the rest.  Enforced as a state-based settle sweep in ``apply`` via
   ``_resolve_unique_duplicates`` + the ``resolve_unique`` decision
   (``KeepUniqueCopy``), so it catches every path that can create a duplicate.
"""
from __future__ import annotations


from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _make_state, _place,
)


# ── card-def builders ─────────────────────────────────────────────────────────

def _unit(name="Han Solo", subtitle="Reluctant Hero", unique=True,
          set_code="SOR", number="1", power=3, hp=5):
    from swu.cards.models import Unit
    return Unit(
        id=abs(hash((name, subtitle, set_code, number))) % 999999, card_uid=None,
        set_code=set_code, set_name="T", card_number=number, name=name,
        subtitle=subtitle, type="Unit", rarity="Common", is_unique=unique,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=("Ground",),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, cost=3, power=power, hp=hp,
    )


def _upgrade(name="Shield Generator", subtitle="Mk I", unique=True,
             set_code="SOR", number="200"):
    from swu.cards.models import Upgrade
    return Upgrade(
        id=abs(hash((name, subtitle, set_code, number))) % 999999, card_uid=None,
        set_code=set_code, set_name="T", card_number=number, name=name,
        subtitle=subtitle, type="Upgrade", rarity="Common", is_unique=unique,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, cost=1, upgrade_power=0, upgrade_hp=0,
    )


def _leader_def(name="Boss Nass", subtitle="Ruler"):
    from swu.cards.models import Leader
    return Leader(
        id=1, card_uid=None, set_code="TST", set_name="T", card_number="1",
        name=name, subtitle=subtitle, type="Leader", rarity="Common",
        is_unique=True, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, power=5, hp=8, deploy_box=None, epic_action=None,
    )


def _base_def(name="Home One"):
    from swu.cards.models import Base
    return Base(
        id=2, card_uid=None, set_code="TST", set_name="T", card_number="2",
        name=name, subtitle=None, type="Base", rarity="Common", is_unique=False,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, hp=30, epic_action=None,
    )


# ── (1) deck copy-limit validators ────────────────────────────────────────────

class TestDeckValidatorCopyLimits:
    def _decklist(self, others):
        # validate_decklist needs exactly 1 leader, 1 base, 50 others.
        leader = _leader_def()
        base = _base_def()
        # pad the "others" out to 50 with distinct filler units
        pad = 50 - len(others)
        filler = [_unit(name=f"Filler {i}", subtitle=None, unique=False,
                        number=f"F{i}") for i in range(pad)]
        # wrap defs as the leader/base card instances validate_decklist expects
        # (it isinstance-checks Leader/Base and counts the rest by display_name)
        return [leader, base] + others + filler

    def test_three_copies_of_unique_is_legal(self):
        from swu.cards.decklist import validate_decklist
        u = _unit(name="Luke Skywalker", subtitle="Jedi Knight", unique=True)
        errs = validate_decklist(self._decklist([u, u, u]))
        assert errs == [], errs  # 3 copies of a unique card is legal

    def test_four_copies_is_too_many(self):
        from swu.cards.decklist import validate_decklist
        u = _unit(name="Luke Skywalker", subtitle="Jedi Knight", unique=True)
        errs = validate_decklist(self._decklist([u, u, u, u]))
        assert any("Too many copies" in e for e in errs), errs

    def test_same_title_different_subtitle_counted_separately(self):
        """Two unique cards sharing a title but with different subtitles are
        different cards — 3 of each is legal (keyed on title + subtitle)."""
        from swu.cards.decklist import validate_decklist
        a = _unit(name="Leia Organa", subtitle="Defiant Princess", number="10")
        b = _unit(name="Leia Organa", subtitle="Alliance General", number="11")
        errs = validate_decklist(self._decklist([a, a, a, b, b, b]))
        assert errs == [], errs

    def test_deckrules_aggregates_reprints_by_full_name(self):
        """deckrules keys the 3-cap on title+subtitle across DB ids, so two
        different printings (a reprint) of the same card count together."""
        from swu.cards.deckrules import deck_errors

        # two printings of the SAME card (same name+subtitle, different set/id)
        orig = _unit(name="Darth Vader", subtitle="Dark Lord", set_code="SOR",
                     number="10")
        reprint = _unit(name="Darth Vader", subtitle="Dark Lord", set_code="LOF",
                        number="99")

        class _Repo:
            def by_id(self, cid):
                return {orig.id: orig, reprint.id: reprint}.get(cid)

        # 3 of each printing = 6 of one card → over the cap of 3
        cards = {orig.id: 3, reprint.id: 3}
        errs = deck_errors(_leader_def(), _base_def(), cards, _Repo())
        assert any("Too many copies" in e and "Darth Vader" in e for e in errs), errs

    def test_deckrules_three_total_across_reprints_is_legal(self):
        from swu.cards.deckrules import deck_errors
        orig = _unit(name="Chewbacca", subtitle="Walking Carpet", set_code="SOR",
                     number="20")
        reprint = _unit(name="Chewbacca", subtitle="Walking Carpet",
                        set_code="LOF", number="88")

        class _Repo:
            def by_id(self, cid):
                return {orig.id: orig, reprint.id: reprint}.get(cid)

        # 2 + 1 = 3 total → legal; but the pool must total 50, so no size error only
        # if we ignore the size check.  Check specifically no copy-cap error.
        cards = {orig.id: 2, reprint.id: 1}
        errs = deck_errors(_leader_def(), _base_def(), cards, _Repo())
        assert not any("Too many copies" in e for e in errs), errs


# ── (2) in-play Unique Rule ───────────────────────────────────────────────────

def _settle(state):
    """Run the state-based sweeps ``apply`` runs after an action settles."""
    from swu.engine.actions import _sweep_defeated_units, _resolve_unique_duplicates
    _sweep_defeated_units(state)
    _resolve_unique_duplicates(state)


def _pending_kind(state):
    return state.pending_decisions[-1].kind if state.pending_decisions else None


class TestInPlayUniqueRule:
    def test_two_copies_of_unique_unit_push_resolve_unique(self, repo):
        state = _make_state()
        card = _unit(name="Han Solo", subtitle="Reluctant Hero")
        a = _place(state, "P0", card, "ground")
        b = _place(state, "P0", card, "ground")
        _settle(state)
        assert _pending_kind(state) == "resolve_unique"
        from swu.engine.actions import legal_actions, KeepUniqueCopy
        legal = legal_actions(state)
        ids = {la.instance_id for la in legal if isinstance(la, KeepUniqueCopy)}
        assert ids == {a.instance_id, b.instance_id}

    def test_keeping_one_defeats_the_other(self, repo):
        state = _make_state()
        card = _unit(name="Han Solo", subtitle="Reluctant Hero")
        a = _place(state, "P0", card, "ground")
        b = _place(state, "P0", card, "ground")
        _settle(state)
        from swu.engine.actions import apply, KeepUniqueCopy
        state = apply(state, KeepUniqueCopy(a.instance_id))
        ps0 = state.player_by_id("P0")
        arena_ids = {u.instance_id for u in ps0.ground_arena}
        assert a.instance_id in arena_ids       # kept
        assert b.instance_id not in arena_ids   # defeated
        assert any(c.instance_id == b.instance_id for c in ps0.discard)
        assert _pending_kind(state) is None     # resolved

    def test_non_unique_duplicates_are_allowed(self, repo):
        state = _make_state()
        card = _unit(name="Battle Droid", subtitle=None, unique=False)
        _place(state, "P0", card, "ground")
        _place(state, "P0", card, "ground")
        _settle(state)
        assert _pending_kind(state) is None
        assert len(state.player_by_id("P0").ground_arena) == 2

    def test_same_title_different_subtitle_coexist(self, repo):
        state = _make_state()
        a = _place(state, "P0", _unit("Leia Organa", "Defiant Princess", number="10"),
                   "ground")
        b = _place(state, "P0", _unit("Leia Organa", "Alliance General", number="11"),
                   "ground")
        _settle(state)
        assert _pending_kind(state) is None
        assert len(state.player_by_id("P0").ground_arena) == 2

    def test_each_player_may_control_their_own_copy(self, repo):
        state = _make_state()
        card = _unit(name="Han Solo", subtitle="Reluctant Hero")
        _place(state, "P0", card, "ground")
        _place(state, "P1", card, "ground")
        _settle(state)
        assert _pending_kind(state) is None  # per-player: both keep their copy

    def test_duplicate_unique_upgrades_resolve(self, repo):
        state = _make_state()
        host_a = _place(state, "P0", _unit("Host A", None, unique=False, number="H1"),
                        "ground")
        host_b = _place(state, "P0", _unit("Host B", None, unique=False, number="H2"),
                        "ground")
        up = _upgrade(name="Dark Saber", subtitle="Ancient")
        from swu.engine.state import CardInstance, Zone
        u1 = CardInstance("P0_up1", up, "P0", Zone.GROUND_ARENA)
        u2 = CardInstance("P0_up2", up, "P0", Zone.GROUND_ARENA)
        host_a.attached_upgrades.append(u1)
        host_b.attached_upgrades.append(u2)
        _settle(state)
        assert _pending_kind(state) == "resolve_unique"
        from swu.engine.actions import apply, KeepUniqueCopy
        state = apply(state, KeepUniqueCopy(u1.instance_id))
        # u2 detached + discarded; u1 still attached to its host
        ps0 = state.player_by_id("P0")
        attached = {u.instance_id for h in ps0.ground_arena for u in h.attached_upgrades}
        assert u1.instance_id in attached
        assert u2.instance_id not in attached
        assert _pending_kind(state) is None
