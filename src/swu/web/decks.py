"""
Deck catalog — maps friendly names the UI shows in the new-game screen to the
decklist fixtures on disk.  A seat's ``deck`` field may be either a catalog key
(``"luke"``) or an explicit path to a SWUDB-format JSON decklist.

The catalog has two layers: a hand-written set of built-in starter decks
(``_CATALOG``) and a generated registry of decks that have *graduated* (passed
``scripts/verify_encoding.py <slug> --graduate``).  The graduation gate calls
``register_ui_deck`` so a newly shippable deck shows up on the start screen
without a code edit; ``catalog()`` merges both layers (built-ins win on a key /
fixture-path clash).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from swu.cards.decklist import load_decklist
from swu.cards.models import AnyCard, Base, Leader
from swu.cards.repository import CardRepository
from swu.web.paths import data_dir, db_path


@dataclass(frozen=True)
class DeckInfo:
    key: str
    label: str
    leader_name: str
    base_name: str
    path: str


def _fixtures_dir() -> Path:
    # .../swu-game/src/swu/web/decks.py -> parents[3] == .../swu-game
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures"


_CATALOG: dict[str, DeckInfo] = {}


def _register(key: str, label: str, leader: str, base: str, filename: str) -> None:
    _CATALOG[key] = DeckInfo(
        key=key, label=label, leader_name=leader, base_name=base,
        path=str(_fixtures_dir() / filename),
    )


_register("luke", "Luke Skywalker — Heroism (Spark of Rebellion starter)",
          "Luke Skywalker", "Administrator's Tower", "starter_luke.json")
_register("vader", "Darth Vader — Villainy (Spark of Rebellion starter)",
          "Darth Vader", "Command Center", "starter_vader.json")
_register("shd-han-solo", "Han Solo — Heroism/Aggression (Shadows of the Galaxy)",
          "Han Solo", "Spice Mines", "shd_han_solo.json")
_register("sabine", "Sabine Wren — Aggression/Heroism (Mean Green)",
          "Sabine Wren", "Energy Conversion Lab", "sabine_mean_green.json")
_register("mandalorian", "The Mandalorian — Cunning/Heroism (Shadows of the Galaxy)",
          "The Mandalorian", "Remote Village", "the_mandalorian.json")


def _registry_path() -> Path:
    """File the graduated-deck registry is read from / written to.

    Overridable via ``SWU_UI_DECKS`` (used by tests so they never touch the real
    ``data/ui_decks.json``).
    """
    env = os.environ.get("SWU_UI_DECKS")
    return Path(env) if env else data_dir() / "ui_decks.json"


def _registry_entries() -> list[DeckInfo]:
    """DeckInfos for graduated decks recorded by ``register_ui_deck`` (best-effort)."""
    path = _registry_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    out: list[DeckInfo] = []
    for e in raw if isinstance(raw, list) else []:
        try:
            out.append(DeckInfo(
                key=e["key"], label=e["label"],
                leader_name=e["leader_name"], base_name=e["base_name"],
                path=str(_fixtures_dir() / e["filename"]),
            ))
        except (KeyError, TypeError):
            continue
    return out


def register_ui_deck(*, key: str, label: str, leader_name: str,
                     base_name: str, filename: str) -> None:
    """Upsert a graduated deck into the start-screen registry (idempotent).

    Keyed by ``key``; re-registering the same key overwrites its row.  A deck
    that is already a built-in (matched by fixture path in ``catalog()``) is
    harmless to register — it is de-duplicated on read.
    """
    path = _registry_path()
    entries: list[dict] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                entries = [e for e in loaded if isinstance(e, dict)]
        except json.JSONDecodeError:
            entries = []
    entries = [e for e in entries if e.get("key") != key]
    entries.append({
        "key": key, "label": label, "leader_name": leader_name,
        "base_name": base_name, "filename": filename,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def catalog() -> list[DeckInfo]:
    """Built-in starter decks plus graduated decks; existing files only.

    Built-ins take precedence over a registry entry that collides on key or
    fixture path, so re-graduating a starter never duplicates it in the UI.
    """
    out: list[DeckInfo] = []
    seen_keys: set[str] = set()
    seen_paths: set[str] = set()
    for d in [*_CATALOG.values(), *_registry_entries()]:
        if not Path(d.path).exists():
            continue
        rp = str(Path(d.path).resolve())
        if d.key in seen_keys or rp in seen_paths:
            continue
        seen_keys.add(d.key)
        seen_paths.add(rp)
        out.append(d)
    return out


@lru_cache(maxsize=1)
def _repo() -> CardRepository:
    return CardRepository(str(db_path()))


def resolve_deck(deck: str) -> list[AnyCard]:
    """Resolve a deck reference to a flat card list.

    Three accepted forms: a catalog key (built-in or graduated), a filesystem path
    to a SWUDB decklist, or a ``custom:<user>:<id>`` key backed by the per-user
    ``DeckStore``.  Raises ``FileNotFoundError`` (→ HTTP 400) if it can't resolve.
    """
    if deck.startswith("custom:"):
        from swu.web.deckstore import resolve_custom_deck
        return resolve_custom_deck(deck)
    info = next((d for d in catalog() if d.key == deck), None)
    path = info.path if info else deck
    if not Path(path).exists():
        raise FileNotFoundError(f"Deck not found: {deck!r}")
    return load_decklist(path, _repo())
