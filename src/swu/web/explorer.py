"""
Card catalog for the Card Explorer screen.

The explorer browses the *whole* card database (not a game), so this module reads
``data/swu.db`` directly and decorates each card with:

  * its printed metadata (set, number, type, cost/power/hp, aspects, keywords,
    traits, arenas, uniqueness);
  * whether it is **playable** in the engine yet ("Available to play"), reusing
    the single canonical classifier in ``scripts/audit_coverage.py`` so the
    explorer, the deck-coverage tests, the planner and the verifier all agree;
  * which built-in / graduated catalog decks it appears in (for the "deck"
    filter and the eventual deck-builder).

Tokens (Token Unit / Token Upgrade / Credit / Force) are excluded — they are
created during play, never browsed or added to a deck.

The catalog is static for a given DB, so the assembled payload is cached.
"""
from __future__ import annotations

import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

from swu.cards.deckrules import deckbuild_max_copies
from swu.web.cards import has_back, image_file_for_card, variants_for_card
from swu.web.decks import catalog, resolve_deck
from swu.web.paths import connect_ro

# ``scripts/`` is not an installed package; add the repo root so the canonical
# classifier can be imported wherever the server's cwd happens to be.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.audit_coverage import (  # noqa: E402  (after sys.path tweak)
    TOKEN_TYPES,
    classify,
    is_playable,
)


def _load_registry() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(registered_keys, escape_hatch_keys) across *all* card sets.

    ``scripts.audit_coverage._load_registry`` only imports the SOR module; the
    explorer needs every set, so ``swu.cards`` (which imports each set module on
    import) is used instead.
    """
    import swu.cards  # noqa: F401 — side-effect: registers every set's cards
    from swu.abilities.registry import get_all_registered, is_escape_hatch

    registered: set[tuple[str, str]] = set()
    escape_hatch: set[tuple[str, str]] = set()
    for key in get_all_registered():
        registered.add(key)
        if is_escape_hatch(key[0], key[1]):
            escape_hatch.add(key)
    return registered, escape_hatch


# audit_coverage.CardRow only carries the fields the classifier needs; the
# explorer needs presentational fields too, so it reads the DB itself and builds
# a lightweight row object the classifier accepts (it only touches
# ``set_code``/``card_number``/``keywords``/``full_text``).
class _ClassRow:
    __slots__ = ("set_code", "card_number", "text", "deploy_box",
                 "epic_action", "keywords")

    def __init__(self, set_code, card_number, text, deploy_box, epic_action,
                 keywords):
        self.set_code = set_code
        self.card_number = card_number
        self.text = text
        self.deploy_box = deploy_box
        self.epic_action = epic_action
        self.keywords = keywords

    @property
    def full_text(self) -> str:
        parts = [self.text, self.deploy_box, self.epic_action]
        return "\n".join(p for p in parts if p).replace("\xa0", " ").replace("’", "'")


def _deck_membership() -> dict[int, list[str]]:
    """Map DB card id -> the catalog deck keys whose decklist includes it."""
    out: dict[int, list[str]] = {}
    for info in catalog():
        try:
            cards = resolve_deck(info.key)
        except Exception:  # a missing/broken fixture must not break the explorer
            continue
        for c in cards:
            cid = getattr(c, "id", None)
            if cid is not None:
                out.setdefault(cid, [])
                if info.key not in out[cid]:
                    out[cid].append(info.key)
    return out


@lru_cache(maxsize=1)
def build_catalog() -> dict:
    """Assemble the full explorer payload (cards + filter facets). Cached."""
    registered, escape_hatch = _load_registry()
    deck_members = _deck_membership()

    con = connect_ro()
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, set_code, set_name, card_number, name, subtitle, type, "
            "rarity, cost, power, hp, upgrade_power, upgrade_hp, is_unique, "
            "text, deploy_box, epic_action FROM cards"
        ).fetchall()
        aspects = _group(con, "SELECT card_id, name FROM card_aspects ORDER BY position")
        keywords = _group(con, "SELECT card_id, name FROM card_keywords")
        traits = _group(con, "SELECT card_id, name FROM card_traits")
        arenas = _group(con, "SELECT card_id, name FROM card_arenas")
        set_names = {r["set_code"]: r["set_name"] for r in rows}
    finally:
        con.close()

    cards: list[dict] = []
    for r in rows:
        if r["type"] in TOKEN_TYPES:
            continue
        cid = r["id"]
        kws = keywords.get(cid, [])
        crow = _ClassRow(r["set_code"], r["card_number"], r["text"],
                         r["deploy_box"], r["epic_action"], set(kws))
        status = classify(crow, registered, escape_hatch)
        has_front = image_file_for_card(cid, "front") is not None
        cards.append({
            "id": cid,
            "set_code": r["set_code"],
            "card_number": r["card_number"],
            "name": r["name"],
            "subtitle": r["subtitle"],
            "type": r["type"],
            "rarity": r["rarity"],
            "cost": r["cost"],
            "power": r["power"],
            "hp": r["hp"],
            "unique": bool(r["is_unique"]),
            "aspects": aspects.get(cid, []),
            "keywords": kws,
            "traits": traits.get(cid, []),
            "arenas": arenas.get(cid, []),
            "status": status,
            "playable": is_playable(status),
            # The deck-builder copy cap (default 3; some cards print an override,
            # e.g. Swarming Vulture Droid = 15). ``_ClassRow`` carries ``.text``,
            # which is all ``deckbuild_max_copies`` reads.
            "deckbuild_max_copies": deckbuild_max_copies(crow),
            "decks": deck_members.get(cid, []),
            "image_url": f"/api/cards/{cid}/image" if has_front else None,
            "back_image_url": (
                f"/api/cards/{cid}/image?face=back" if has_back(cid) else None
            ),
            "variants": _card_variants(cid),
        })

    cards.sort(key=lambda c: (c["set_code"], _num(c["card_number"]), c["name"]))

    # Filter facets, sorted for stable UI ordering.
    sets = sorted({c["set_code"] for c in cards})
    return {
        "cards": cards,
        "sets": [{"code": s, "name": set_names.get(s, s)} for s in sets],
        "types": sorted({c["type"] for c in cards}),
        "aspects": sorted({a for c in cards for a in c["aspects"]}),
        "keywords": sorted({k for c in cards for k in c["keywords"]}),
        "traits": sorted({t for c in cards for t in c["traits"]}),
        "decks": [{"key": d.key, "label": d.label} for d in catalog()],
    }


def _card_variants(card_id: int) -> dict[str, dict[str, str | None]]:
    """Available alternate-art printings for a card (cosmetic; may be empty).

    Mirrors ``serializers._card_variants`` but emits plain dicts for the cached
    explorer payload: ``{variant_type: {image_url, back_image_url}}``.
    """
    out: dict[str, dict[str, str | None]] = {}
    for vtype, faces in variants_for_card(card_id).items():
        out[vtype] = {
            "image_url": f"/api/cards/{card_id}/image?face=front&variant={vtype}",
            "back_image_url": (
                f"/api/cards/{card_id}/image?face=back&variant={vtype}"
                if faces.get("back")
                else None
            ),
        }
    return out


def _group(con: sqlite3.Connection, sql: str) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for row in con.execute(sql).fetchall():
        out.setdefault(row["card_id"], []).append(row["name"])
    return out


def _num(card_number: str) -> tuple[int, str]:
    """Sort key for a card number that may be non-numeric (e.g. 'T01')."""
    try:
        return (int(card_number), "")
    except (TypeError, ValueError):
        return (10**9, str(card_number))
