"""
SWUDB JSON decklist format loader.

The format used by swudb.com looks like:
{
  "leader": {"id": "SOR_005", "count": 1},
  "base":   {"id": "SOR_018", "count": 1},
  "deck": [
    {"id": "SOR_012", "count": 3},
    ...
  ]
}

"id" is "{SET_CODE}_{card_number}" (zero-padded to 3 digits is common but
not universal; we normalise to match the DB's card_number field).

We also support a flat list format where every entry has an "id" and "count",
with leader/base inferred by card type.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from swu.cards.models import AnyCard, Base, Leader
from swu.cards.repository import CardRepository

logger = logging.getLogger(__name__)


class DecklistError(Exception):
    pass


def _parse_card_id(card_id: str) -> tuple[str, str]:
    """
    Parse 'SOR_005' → ('SOR', '005').

    Strips leading zeros from the numeric part to match DB storage,
    but preserves any suffix (e.g. 'SOR_005a' → ('SOR', '005a')).
    """
    parts = card_id.split("_", 1)
    if len(parts) != 2:
        raise DecklistError(f"Invalid card id format: {card_id!r}")
    set_code, num = parts
    # normalise: remove leading zeros for pure-numeric parts
    if num.isdigit():
        num = str(int(num))
    return set_code, num


def _lookup(repo: CardRepository, card_id: str) -> Optional[AnyCard]:
    set_code, card_number = _parse_card_id(card_id)
    with repo._con() as con:  # type: ignore[attr-defined]
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?",
            (set_code, card_number),
        ).fetchone()
        if row is None:
            # Try zero-padded variants (e.g. stored as "005")
            for pad in (f"{int(card_number):03d}", f"{int(card_number):04d}") if card_number.isdigit() else []:
                row = con.execute(
                    "SELECT * FROM cards WHERE set_code=? AND card_number=?",
                    (set_code, pad),
                ).fetchone()
                if row:
                    break
        if row is None:
            return None
        return repo._hydrate(con, row)


def load_decklist(path: str | Path, repo: CardRepository) -> list[AnyCard]:
    """
    Load a SWUDB-format JSON decklist from disk, returning a flat list of cards.

    The list always contains exactly one Leader, one Base, and 50 other cards.
    Raises DecklistError on structural problems; logs warnings on missing cards.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_decklist(data, repo)


def parse_decklist(data: dict, repo: CardRepository) -> list[AnyCard]:
    """Parse a SWUDB decklist dict into a flat card list."""
    cards: list[AnyCard] = []

    def add_entry(entry: dict) -> None:
        card_id = entry.get("id") or entry.get("card_id")
        count = int(entry.get("count", 1))
        if not card_id:
            raise DecklistError(f"Entry missing 'id': {entry}")
        card = _lookup(repo, card_id)
        if card is None:
            logger.warning("Card not found in DB: %s", card_id)
            return
        for _ in range(count):
            cards.append(card)

    if "leader" in data:
        add_entry(data["leader"] if isinstance(data["leader"], dict) else {"id": data["leader"], "count": 1})
    if "base" in data:
        add_entry(data["base"] if isinstance(data["base"], dict) else {"id": data["base"], "count": 1})

    for entry in data.get("deck", []):
        add_entry(entry)

    # Fallback: flat list format
    if not cards and isinstance(data, list):
        for entry in data:
            add_entry(entry)

    return cards


def validate_decklist(cards: list[AnyCard]) -> list[str]:
    """
    Return a list of validation error strings (empty = valid).

    Rules:
    * Exactly 1 Leader
    * Exactly 1 Base
    * Exactly 50 non-leader/non-base cards
    * No more than 3 copies of any card, keyed on full name (title + subtitle).
      Uniqueness does NOT reduce the deck copy cap — a unique card may sit in a
      deck up to 3 copies; the unique rule only limits copies *in play*.  The cap
      is keyed on ``display_name`` (title + subtitle), NOT the DB id, so two
      *different* printings of the same card (a reprint/promo, same title+subtitle
      but different id) count TOGETHER toward one cap of 3 — you cannot dodge the
      limit by mixing printings.  Two different cards sharing a title but with
      different subtitles are still counted separately.
    """
    errors = []
    leaders = [c for c in cards if isinstance(c, Leader)]
    bases = [c for c in cards if isinstance(c, Base)]
    others = [c for c in cards if not isinstance(c, (Leader, Base))]

    if len(leaders) != 1:
        errors.append(f"Deck must have exactly 1 Leader, got {len(leaders)}")
    if len(bases) != 1:
        errors.append(f"Deck must have exactly 1 Base, got {len(bases)}")
    # 50, shifted by a base's DeckSizeModifier marker (Data Vault JTL_24 +10,
    # Thermal Oscillator JTL_25 −5) — the deckrules sibling owns the number.
    from swu.cards.deckrules import deck_size_for
    required = deck_size_for(bases[0] if len(bases) == 1 else None)
    if len(others) != required:
        errors.append(
            f"Deck must have exactly {required} non-leader/base cards, "
            f"got {len(others)}")

    # Copy limits — keyed on full name (title + subtitle), cap 3 for every card.
    # Reprints (same title+subtitle, different id) count TOGETHER toward one cap.
    from collections import Counter
    name_counts: Counter[str] = Counter()
    for c in others:
        name_counts[c.display_name] += 1
    for name, cnt in name_counts.items():
        if cnt > 3:
            errors.append(f"Too many copies of {name!r}: {cnt} (limit 3)")

    return errors


def build_vanilla_deck(
    repo: CardRepository,
    leader_name: str,
    base_name: str,
    set_code: Optional[str] = None,
) -> list[AnyCard]:
    """
    Build a 50-card vanilla deck (no text effects needed): one leader, one base,
    and 50 units/upgrades that share at least one aspect with the leader/base.

    Used for test fixtures when a full real decklist isn't available.
    """
    leaders = repo.by_name(leader_name)
    if not leaders:
        raise DecklistError(f"Leader not found: {leader_name!r}")
    leader = next((c for c in leaders if isinstance(c, Leader)), None)
    if leader is None:
        raise DecklistError(f"No Leader card named {leader_name!r}")

    bases = repo.by_name(base_name)
    if not bases:
        raise DecklistError(f"Base not found: {base_name!r}")
    base = next((c for c in bases if isinstance(c, Base)), None)
    if base is None:
        raise DecklistError(f"No Base card named {base_name!r}")

    # Collect aspects available from leader + base
    available_aspects = {a.name for a in leader.aspects} | {a.name for a in base.aspects}

    # Get all units (and non-token upgrades) that share at least one aspect
    candidates: list[AnyCard] = []
    from swu.cards.models import Upgrade, Unit
    for card_type in ("Unit", "Upgrade"):
        for card in repo.all_of_type(card_type):
            if set_code and card.set_code != set_code:
                continue
            if not isinstance(card, (Unit, Upgrade)):
                continue
            card_aspect_names = {a.name for a in card.aspects}
            # Accept aspect-neutral cards or cards sharing at least one aspect
            if not card_aspect_names or card_aspect_names & available_aspects:
                candidates.append(card)

    if not candidates:
        # Fallback: any unit
        candidates = [c for c in repo.all_of_type("Unit") if isinstance(c, Unit)]

    # Deduplicate by full name (title + subtitle); respect copy limits
    name_pool: dict[str, AnyCard] = {}
    for c in candidates:
        if c.display_name not in name_pool:
            name_pool[c.display_name] = c

    # Build deck: fill with up to 3 copies per card.  Uniqueness does not lower
    # the deck copy cap (the unique rule only limits copies in play).
    deck_cards: list[AnyCard] = []
    for c in sorted(name_pool.values(), key=lambda x: x.display_name):
        for _ in range(3):
            if len(deck_cards) < 50:
                deck_cards.append(c)
            else:
                break
        if len(deck_cards) >= 50:
            break

    if len(deck_cards) < 50:
        raise DecklistError(
            f"Not enough valid cards for a vanilla deck with {leader_name}: "
            f"got {len(deck_cards)}"
        )

    return [leader, base] + deck_cards[:50]
