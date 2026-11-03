"""
Custom deck builder — the per-user, file-backed store + payload models.

Each whitelisted user curates 0+ custom decks (a "Spotify playlist" of cards);
complete ones surface in the start-screen deck dropdown.  This module owns the
on-disk contract, the store, and the derived-rules glue; ``app.py`` wires the HTTP
routes and ``decks.resolve_deck`` builds a playable card list from a stored deck.

Identity is the DB card **id** (not ``(set, number)``, which collides between a
Leader and its same-numbered Token — see ``docs/encoding_guide.md``).

On-disk layout — one JSON file per deck under the owner's folder, resolved via
``data_dir()`` so it lands in the right instance and survives ``deploy.ps1`` (which
mirrors code only, never ``data/``); overridable via ``SWU_CUSTOM_DECKS`` for
tests::

    data/custom_decks/
      <username-lowercased>/
        <id>.json          # id = "<YYYYMMDD-hhmm>-<name-slug>"

Only the base fields are persisted; ``count``/``complete``/``errors`` are derived
on read from ``swu.cards.deckrules`` + the card repository.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from swu.cards.deckrules import DECK_SIZE, TOKEN_TYPES, deck_errors, deck_size_for
from swu.cards.models import AnyCard, Base, Leader
from swu.cards.repository import CardRepository
from swu.web.paths import data_dir, db_path

# Sentinel distinguishing "field omitted" from an explicit ``None`` (= clear slot)
# in the partial ``set_cards`` update.
_UNSET: Any = object()

# The start-screen / game-creation key for a custom deck: ``custom:<user>:<id>``.
# ``resolve_deck`` (decks.py) routes a key with this prefix through this module.
CUSTOM_PREFIX = "custom"


# ── payload models ──────────────────────────────────────────────────────────────

class CustomDeck(BaseModel):
    id: str
    name: str
    owner: str                       # lowercased username
    leader_id: Optional[int] = None
    base_id: Optional[int] = None
    cards: dict[str, int] = {}       # str(DB card id) -> count (the pool)
    created: str
    updated: str
    # Derived on read (never persisted):
    count: int = 0                   # sum(cards.values())
    # How many pool cards a COMPLETE deck needs — ``DECK_SIZE`` (50) unless the
    # chosen base shifts it (Data Vault JTL_24 → 60, Thermal Oscillator JTL_25 →
    # 45).  Sent to the client because the builder's "N/M · X to go" readout and
    # its deck-full guard must move with the base, not with a hardcoded 50.
    required: int = DECK_SIZE
    complete: bool = False
    errors: list[str] = []


class DeckSummary(BaseModel):
    id: str
    name: str
    count: int
    required: int = DECK_SIZE
    complete: bool


# ── errors ──────────────────────────────────────────────────────────────────────

class DeckStoreError(Exception):
    """Base for deck-store failures."""


class DeckNotFound(DeckStoreError):
    """No deck with that id for the user."""


class BadDeckId(DeckStoreError):
    """An id that fails the containment guard (path traversal attempt)."""


class InvalidCard(DeckStoreError):
    """A card id that isn't a real non-token card, or doesn't fit its slot."""


# ── helpers ─────────────────────────────────────────────────────────────────────

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_STORED_KEYS = ("id", "name", "owner", "leader_id", "base_id", "cards",
                "created", "updated")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:40] or "deck"


@lru_cache(maxsize=1)
def _default_repo() -> CardRepository:
    return CardRepository(str(db_path()))


# ── the store ─────────────────────────────────────────────────────────────────

class DeckStore:
    """File-backed custom decks.  All public methods are thread-safe.

    ``root`` is overridable for tests (else ``data_dir()/custom_decks``);
    ``repo`` is injectable (else the shared DB repository).
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        repo: CardRepository | None = None,
    ) -> None:
        self._root = Path(root) if root is not None else _custom_decks_root()
        self._repo = repo
        self._lock = threading.RLock()

    @property
    def repo(self) -> CardRepository:
        return self._repo if self._repo is not None else _default_repo()

    # -- path resolution / containment guard -----------------------------------

    def _user_dir(self, user: str) -> Path:
        return self._root / user.lower()

    def _check_id(self, deck_id: str) -> None:
        if not deck_id or not _ID_RE.match(deck_id):
            raise BadDeckId(deck_id)

    def _path_for(self, user: str, deck_id: str) -> Path:
        self._check_id(deck_id)
        return self._user_dir(user) / f"{deck_id}.json"

    # -- (de)serialisation -----------------------------------------------------

    @staticmethod
    def _read(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write(path: Path, deck: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        stored = {k: deck[k] for k in _STORED_KEYS if k in deck}
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(stored, f, indent=2)
        tmp.replace(path)  # atomic-ish swap

    def _model(self, deck: dict) -> CustomDeck:
        """Build the returned model, computing the derived fields via deckrules."""
        cards = {str(k): int(v) for k, v in (deck.get("cards") or {}).items() if int(v) > 0}
        leader = self.repo.by_id(deck["leader_id"]) if deck.get("leader_id") else None
        base = self.repo.by_id(deck["base_id"]) if deck.get("base_id") else None
        errors = deck_errors(leader, base, cards, self.repo)
        return CustomDeck(
            id=deck["id"],
            name=deck.get("name", ""),
            owner=deck.get("owner", ""),
            leader_id=deck.get("leader_id"),
            base_id=deck.get("base_id"),
            cards=cards,
            created=deck.get("created", ""),
            updated=deck.get("updated", ""),
            count=sum(cards.values()),
            required=deck_size_for(base),
            complete=not errors,
            errors=errors,
        )

    # -- card-id validation ----------------------------------------------------

    def _require_card(self, card_id: int):
        card = self.repo.by_id(card_id)
        if card is None:
            raise InvalidCard(f"Unknown card id {card_id}.")
        if card.type in TOKEN_TYPES:
            raise InvalidCard(f"{card.name!r} is a token, not a deckbuildable card.")
        return card

    def _validate_leader(self, card_id: Optional[int]) -> None:
        if card_id is None:
            return
        card = self._require_card(card_id)
        if not isinstance(card, Leader):
            raise InvalidCard(f"{card.name!r} is not a Leader card.")

    def _validate_base(self, card_id: Optional[int]) -> None:
        if card_id is None:
            return
        card = self._require_card(card_id)
        if not isinstance(card, Base):
            raise InvalidCard(f"{card.name!r} is not a Base card.")

    def _validate_pool(self, cards: dict) -> dict[str, int]:
        out: dict[str, int] = {}
        for raw_id, count in cards.items():
            count = int(count)
            if count <= 0:
                continue
            card = self._require_card(int(raw_id))
            if isinstance(card, (Leader, Base)):
                raise InvalidCard(f"{card.name!r} cannot go in the deck pool.")
            out[str(int(raw_id))] = count
        return out

    # -- create ----------------------------------------------------------------

    def create(self, user: str, name: str) -> CustomDeck:
        now = _now()
        ts = _ts(now)
        base_id = f"{now:%Y%m%d-%H%M}-{_slugify(name)}"
        with self._lock:
            user_dir = self._user_dir(user)
            deck_id = base_id
            n = 2
            while (user_dir / f"{deck_id}.json").exists():
                deck_id = f"{base_id}-{n}"
                n += 1
            deck = {
                "id": deck_id,
                "name": name or "Untitled deck",
                "owner": user.lower(),
                "leader_id": None,
                "base_id": None,
                "cards": {},
                "created": ts,
                "updated": ts,
            }
            self._write(user_dir / f"{deck_id}.json", deck)
            return self._model(deck)

    # -- read ------------------------------------------------------------------

    def get(self, user: str, deck_id: str) -> CustomDeck:
        with self._lock:
            path = self._path_for(user, deck_id)
            if not path.exists():
                raise DeckNotFound(deck_id)
            return self._model(self._read(path))

    def list_decks(self, user: str) -> list[DeckSummary]:
        """The user's decks, newest first."""
        with self._lock:
            user_dir = self._user_dir(user)
            decks: list[CustomDeck] = []
            if user_dir.exists():
                for child in user_dir.iterdir():
                    if child.suffix != ".json" or not child.is_file():
                        continue
                    try:
                        decks.append(self._model(self._read(child)))
                    except (json.JSONDecodeError, OSError, KeyError):
                        continue
        decks.sort(key=lambda d: d.created, reverse=True)
        return [
            DeckSummary(id=d.id, name=d.name, count=d.count,
                        required=d.required, complete=d.complete)
            for d in decks
        ]

    # -- mutate ----------------------------------------------------------------

    def _load_raw(self, user: str, deck_id: str) -> tuple[Path, dict]:
        path = self._path_for(user, deck_id)
        if not path.exists():
            raise DeckNotFound(deck_id)
        return path, self._read(path)

    def rename(self, user: str, deck_id: str, name: str) -> CustomDeck:
        with self._lock:
            path, deck = self._load_raw(user, deck_id)
            deck["name"] = name or deck.get("name", "Untitled deck")
            deck["updated"] = _ts(_now())
            self._write(path, deck)
            return self._model(deck)

    def set_cards(
        self,
        user: str,
        deck_id: str,
        *,
        leader_id: Any = _UNSET,
        base_id: Any = _UNSET,
        cards: Any = _UNSET,
    ) -> CustomDeck:
        """Partial edit: rename via ``rename``; here set any of the three slots.

        A field left ``_UNSET`` is unchanged; an explicit ``None`` clears the
        leader/base slot.  Validates card ids and slot types before persisting.
        """
        with self._lock:
            path, deck = self._load_raw(user, deck_id)
            if leader_id is not _UNSET:
                self._validate_leader(leader_id)
                deck["leader_id"] = leader_id
            if base_id is not _UNSET:
                self._validate_base(base_id)
                deck["base_id"] = base_id
            if cards is not _UNSET:
                deck["cards"] = self._validate_pool(dict(cards or {}))
            deck["updated"] = _ts(_now())
            self._write(path, deck)
            return self._model(deck)

    def add_card(self, user: str, deck_id: str, card_id: int, delta: int) -> CustomDeck:
        """Increment (delta>0) or decrement (delta<0) a pool card's count.

        A count reaching ≤0 removes the entry.  Over-cap is permitted (drafts are
        allowed) and surfaced via the derived ``errors``.
        """
        with self._lock:
            path, deck = self._load_raw(user, deck_id)
            card = self._require_card(int(card_id))
            if isinstance(card, (Leader, Base)):
                raise InvalidCard(f"{card.name!r} cannot go in the deck pool.")
            key = str(int(card_id))
            pool = {str(k): int(v) for k, v in (deck.get("cards") or {}).items()}
            new_count = pool.get(key, 0) + int(delta)
            if new_count > 0:
                pool[key] = new_count
            else:
                pool.pop(key, None)
            deck["cards"] = pool
            deck["updated"] = _ts(_now())
            self._write(path, deck)
            return self._model(deck)

    def delete(self, user: str, deck_id: str) -> None:
        with self._lock:
            path = self._path_for(user, deck_id)
            if not path.exists():
                raise DeckNotFound(deck_id)
            path.unlink()


def _custom_decks_root() -> Path:
    """The custom-decks root; overridable via ``SWU_CUSTOM_DECKS`` for tests."""
    env = os.environ.get("SWU_CUSTOM_DECKS")
    return Path(env) if env else data_dir() / "custom_decks"


# ── shared singleton (Stage 3) ──────────────────────────────────────────────────
#
# One store instance backs BOTH the HTTP routes (app.py) and ``resolve_deck``
# (decks.py), so a game created from a ``custom:…`` key sees exactly the deck the
# routes wrote.  Lazily built (honouring ``SWU_CUSTOM_DECKS`` at first use); tests
# reset it via ``monkeypatch.setattr(deckstore, "_SINGLETON", DeckStore(root))``.

_SINGLETON: Optional[DeckStore] = None


def get_deck_store() -> DeckStore:
    """The process-wide custom-deck store (created on first use)."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = DeckStore()
    return _SINGLETON


# ── custom-deck key parsing + resolution (Stage 3) ──────────────────────────────

def parse_custom_key(key: str) -> Optional[tuple[str, str]]:
    """Parse ``custom:<user>:<id>`` → ``(user, deck_id)``; ``None`` if not one.

    Split with maxsplit=2 so a deck id containing ``-`` (the slug carries them)
    survives intact; usernames never contain ``:``.
    """
    if not key.startswith(CUSTOM_PREFIX + ":"):
        return None
    parts = key.split(":", 2)
    if len(parts) != 3 or not parts[1] or not parts[2]:
        return None
    return parts[1], parts[2]


def resolve_custom_deck(key: str, store: Optional[DeckStore] = None) -> list[AnyCard]:
    """Expand a ``custom:<user>:<id>`` key into a flat, playable card list.

    Mirrors ``decklist.load_decklist``'s output (leader + base + the pool expanded
    by count).  Raises ``FileNotFoundError`` — the ``resolve_deck`` contract that
    the game-creation route maps to HTTP 400 — when the deck is missing, malformed,
    or **incomplete** (an incomplete deck can't seat a game).
    """
    parsed = parse_custom_key(key)
    if parsed is None:
        raise FileNotFoundError(f"Not a custom deck key: {key!r}")
    user, deck_id = parsed
    store = store or get_deck_store()
    try:
        deck = store.get(user, deck_id)
    except (DeckNotFound, BadDeckId):
        raise FileNotFoundError(f"Custom deck not found: {key!r}")
    if not deck.complete:
        raise FileNotFoundError(f"Custom deck {deck.name!r} is incomplete.")
    repo = store.repo
    cards: list[AnyCard] = []
    leader = repo.by_id(deck.leader_id) if deck.leader_id is not None else None
    base = repo.by_id(deck.base_id) if deck.base_id is not None else None
    if leader is None or base is None:
        raise FileNotFoundError(f"Custom deck {deck.name!r} is missing its leader/base.")
    cards.append(leader)
    cards.append(base)
    for raw_id, count in deck.cards.items():
        card = repo.by_id(int(raw_id))
        if card is None:  # defensive: a stored id that vanished from the DB
            raise FileNotFoundError(f"Custom deck {deck.name!r} references unknown card {raw_id}.")
        cards.extend([card] * int(count))
    return cards


# Expose the completeness threshold for callers (Stage 3 catalog merge).
__all__ = [
    "CustomDeck", "DeckSummary", "DeckStore",
    "DeckStoreError", "DeckNotFound", "BadDeckId", "InvalidCard",
    "DECK_SIZE", "CUSTOM_PREFIX",
    "get_deck_store", "parse_custom_key", "resolve_custom_deck",
]
