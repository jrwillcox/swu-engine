"""
Custom deck builder — store + deckbuilding-rules unit tests (Stage 2).

Exercise ``swu.web.deckstore.DeckStore`` and ``swu.cards.deckrules`` in isolation:
create/rename/delete, add/remove cards, copy caps (3 default, 15 override, over-cap
error), leader/base slot type enforcement, complete/incomplete derivation,
multi-user isolation, and the ``SWU_CUSTOM_DECKS`` override.

Card ids are real rows in ``data/swu.db``:
  * Leader   5     Luke Skywalker
  * Base     55    Administrator's Tower
  * Unit     15    Cell Block Guard   (and the 20-list below)
  * Event    40    Galactic Ambition
  * Upgrade  100   Luke's Lightsaber
  * Token    195   Shield (Token Upgrade)
  * Override 20751 Swarming Vulture Droid (JTL_256 — 15-copy cap)
"""
from __future__ import annotations

import pytest

from swu.cards.deckrules import deck_errors, deckbuild_max_copies
from swu.cards.repository import CardRepository
from swu.web.deckstore import (
    BadDeckId,
    DeckNotFound,
    DeckStore,
    InvalidCard,
    _custom_decks_root,
)
from tests.dbpath import require_db

LEADER = 5
BASE = 55
EVENT = 40
UPGRADE = 100
TOKEN = 195
VULTURE = 20751  # "A deck can have up to 15 copies of this card."
DATA_VAULT = 19591        # JTL_24 base — "minimum deck size is increased by 10" → 60
THERMAL_OSCILLATOR = 19596  # JTL_25 base — "decreased by 5 cards" → 45
UNITS = [15, 20, 25, 30, 35, 45, 70, 75, 105, 115,
         120, 130, 145, 150, 155, 160, 165, 180, 185, 190]


@pytest.fixture(scope="module")
def repo() -> CardRepository:
    return CardRepository(str(require_db()))


@pytest.fixture()
def store(tmp_path, repo) -> DeckStore:
    return DeckStore(tmp_path / "custom_decks", repo=repo)


def _full_pool() -> dict[str, int]:
    """A legal 50-card pool: 16 units ×3 + 1 unit ×2 = 50, all within the 3-cap."""
    pool = {str(u): 3 for u in UNITS[:16]}
    pool[str(UNITS[16])] = 2
    assert sum(pool.values()) == 50
    return pool


# ── deckrules ─────────────────────────────────────────────────────────────────

class TestDeckRules:
    def test_default_copy_cap_is_3(self, repo):
        assert deckbuild_max_copies(repo.by_id(UNITS[0])) == 3

    def test_swarming_vulture_droid_override_is_15(self, repo):
        assert deckbuild_max_copies(repo.by_id(VULTURE)) == 15

    def test_complete_deck_has_no_errors(self, repo):
        errors = deck_errors(
            repo.by_id(LEADER), repo.by_id(BASE), _full_pool(), repo
        )
        assert errors == []

    def test_missing_leader_and_base_reported(self, repo):
        errors = deck_errors(None, None, _full_pool(), repo)
        assert any("leader" in e.lower() for e in errors)
        assert any("base" in e.lower() for e in errors)

    def test_wrong_count_reported(self, repo):
        errors = deck_errors(
            repo.by_id(LEADER), repo.by_id(BASE), {str(UNITS[0]): 3}, repo
        )
        assert any("needs exactly 50" in e for e in errors)

    def test_over_cap_reported(self, repo):
        pool = _full_pool()
        pool[str(UNITS[0])] = 4  # over the 3-cap
        errors = deck_errors(repo.by_id(LEADER), repo.by_id(BASE), pool, repo)
        assert any("Too many copies" in e for e in errors)

    def test_vulture_15_copies_is_within_cap(self, repo):
        # 15 vultures + 35 across other units = 50, no over-cap error.
        pool = {str(VULTURE): 15}
        rest = 35
        for u in UNITS[:12]:
            take = min(3, rest)
            if take <= 0:
                break
            pool[str(u)] = take
            rest -= take
        assert sum(pool.values()) == 50
        errors = deck_errors(repo.by_id(LEADER), repo.by_id(BASE), pool, repo)
        assert errors == []

    def test_leader_in_pool_reported(self, repo):
        errors = deck_errors(
            repo.by_id(LEADER), repo.by_id(BASE), {str(LEADER): 1}, repo
        )
        assert any("cannot go in the deck" in e for e in errors)

    def test_jtl_24_data_vault_wants_60_not_50(self, repo):
        # A 50-card pool is a *draft* under Data Vault — it needs 60.
        errors = deck_errors(
            repo.by_id(LEADER), repo.by_id(DATA_VAULT), _full_pool(), repo
        )
        assert any("needs exactly 60" in e for e in errors)

    def test_jtl_25_thermal_oscillator_wants_45(self, repo):
        errors = deck_errors(
            repo.by_id(LEADER), repo.by_id(THERMAL_OSCILLATOR), _full_pool(), repo
        )
        assert any("needs exactly 45" in e for e in errors)


# ── DeckStore CRUD ──────────────────────────────────────────────────────────────

class TestDeckStoreCrud:
    def test_create_returns_empty_draft(self, store):
        d = store.create("Bob", "My Aggro Deck")
        assert d.owner == "bob"
        assert d.name == "My Aggro Deck"
        assert d.leader_id is None and d.base_id is None
        assert d.cards == {} and d.count == 0
        assert d.complete is False
        assert d.errors  # a draft has outstanding rule violations

    def test_get_roundtrips(self, store):
        d = store.create("Bob", "Deck")
        again = store.get("Bob", d.id)
        assert again.id == d.id and again.name == "Deck"

    def test_get_missing_raises(self, store):
        with pytest.raises(DeckNotFound):
            store.get("Bob", "nope-does-not-exist")

    def test_bad_id_raises(self, store):
        with pytest.raises(BadDeckId):
            store.get("Bob", "../escape")

    def test_rename(self, store):
        d = store.create("Bob", "Old")
        renamed = store.rename("Bob", d.id, "New Name")
        assert renamed.name == "New Name"
        assert store.get("Bob", d.id).name == "New Name"

    def test_delete_removes_file(self, store):
        d = store.create("Bob", "Doomed")
        store.delete("Bob", d.id)
        with pytest.raises(DeckNotFound):
            store.get("Bob", d.id)

    def test_delete_missing_raises(self, store):
        with pytest.raises(DeckNotFound):
            store.delete("Bob", "nope")

    def test_list_newest_first(self, store):
        a = store.create("Bob", "A")
        b = store.create("Bob", "B")
        ids = [s.id for s in store.list_decks("Bob")]
        assert set(ids) == {a.id, b.id}


# ── DeckStore editing + validation ──────────────────────────────────────────────

class TestDeckStoreEditing:
    def test_set_leader_and_base(self, store):
        d = store.create("Bob", "Deck")
        d = store.set_cards("Bob", d.id, leader_id=LEADER, base_id=BASE)
        assert d.leader_id == LEADER and d.base_id == BASE

    def test_set_leader_rejects_non_leader(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.set_cards("Bob", d.id, leader_id=UNITS[0])

    def test_set_base_rejects_non_base(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.set_cards("Bob", d.id, base_id=UNITS[0])

    def test_pool_rejects_leader(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.set_cards("Bob", d.id, cards={str(LEADER): 1})

    def test_pool_rejects_token(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.set_cards("Bob", d.id, cards={str(TOKEN): 1})

    def test_pool_rejects_unknown_id(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.set_cards("Bob", d.id, cards={"99999999": 1})

    def test_required_defaults_to_50(self, store):
        d = store.create("Bob", "Deck")
        d = store.set_cards("Bob", d.id, leader_id=LEADER, base_id=BASE)
        assert d.required == 50

    def test_required_follows_the_base(self, store):
        """The builder's pool target must move with the base.

        Regression for Bob's report "The Data Vault doesn't work" (2026-08-06):
        ``deck_errors`` already demanded 60, but the store never told the client,
        so the explorer used a hardcoded 50 — it capped him at 50 cards and then
        showed the deck as a Draft he could not finish.
        """
        d = store.create("Bob", "Vault Deck")
        d = store.set_cards("Bob", d.id, leader_id=LEADER, base_id=DATA_VAULT)
        assert d.required == 60
        d = store.set_cards("Bob", d.id, base_id=THERMAL_OSCILLATOR)
        assert d.required == 45

    def test_required_is_in_the_list_summary(self, store):
        d = store.create("Bob", "Vault Deck")
        store.set_cards("Bob", d.id, leader_id=LEADER, base_id=DATA_VAULT)
        assert [s.required for s in store.list_decks("Bob")] == [60]

    def test_sixty_card_data_vault_deck_is_complete(self, store, repo):
        """The whole point: 60 cards on Data Vault is a *finishable* deck."""
        pool = {str(u): 3 for u in UNITS[:20]}
        assert sum(pool.values()) == 60
        d = store.create("Bob", "Vault Deck")
        d = store.set_cards(
            "Bob", d.id, leader_id=LEADER, base_id=DATA_VAULT, cards=pool
        )
        assert d.count == 60 and d.required == 60
        assert d.complete, d.errors

    def test_pool_accepts_event_and_upgrade(self, store):
        d = store.create("Bob", "Deck")
        d = store.set_cards("Bob", d.id, cards={str(EVENT): 2, str(UPGRADE): 1})
        assert d.cards == {str(EVENT): 2, str(UPGRADE): 1}
        assert d.count == 3

    def test_clear_leader_with_explicit_none(self, store):
        d = store.create("Bob", "Deck")
        d = store.set_cards("Bob", d.id, leader_id=LEADER)
        d = store.set_cards("Bob", d.id, leader_id=None)
        assert d.leader_id is None

    def test_add_card_increments_then_removes(self, store):
        d = store.create("Bob", "Deck")
        d = store.add_card("Bob", d.id, UNITS[0], 2)
        assert d.cards == {str(UNITS[0]): 2}
        d = store.add_card("Bob", d.id, UNITS[0], 1)
        assert d.cards == {str(UNITS[0]): 3}
        d = store.add_card("Bob", d.id, UNITS[0], -3)
        assert str(UNITS[0]) not in d.cards

    def test_add_card_over_cap_allowed_but_flagged(self, store):
        d = store.create("Bob", "Deck")
        d = store.add_card("Bob", d.id, UNITS[0], 5)  # over the 3-cap
        assert d.cards[str(UNITS[0])] == 5
        assert any("Too many copies" in e for e in d.errors)

    def test_add_card_rejects_leader(self, store):
        d = store.create("Bob", "Deck")
        with pytest.raises(InvalidCard):
            store.add_card("Bob", d.id, LEADER, 1)

    def test_complete_deck_derivation(self, store):
        d = store.create("Bob", "Complete")
        d = store.set_cards(
            "Bob", d.id, leader_id=LEADER, base_id=BASE, cards=_full_pool()
        )
        assert d.count == 50
        assert d.complete is True
        assert d.errors == []


# ── isolation + storage location ────────────────────────────────────────────────

class TestIsolationAndStorage:
    def test_users_are_isolated(self, store):
        a = store.create("Bob", "Bob's deck")
        store.create("Alice", "Alice's deck")
        bob_ids = {s.id for s in store.list_decks("Bob")}
        alice_ids = {s.id for s in store.list_decks("Alice")}
        assert a.id in bob_ids
        assert a.id not in alice_ids
        # Alice cannot fetch Bob's deck by id.
        with pytest.raises(DeckNotFound):
            store.get("Alice", a.id)

    def test_username_case_insensitive_folder(self, store):
        d = store.create("Bob", "Deck")
        assert store.get("bob", d.id).id == d.id
        assert store.get("BOB", d.id).id == d.id

    def test_swu_custom_decks_env_honoured(self, tmp_path, repo, monkeypatch):
        target = tmp_path / "envroot"
        monkeypatch.setenv("SWU_CUSTOM_DECKS", str(target))
        assert _custom_decks_root() == target
        s = DeckStore(repo=repo)  # no explicit root → uses the env override
        d = s.create("Bob", "Env Deck")
        assert (target / "bob" / f"{d.id}.json").exists()
