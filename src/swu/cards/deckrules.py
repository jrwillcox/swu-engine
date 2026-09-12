"""
Deckbuilding rules for the custom deck builder.

This is the custom deck *builder*'s rule checker (its sibling
``swu.cards.decklist.validate_decklist`` validates loaded SWUDB decklists /
fixtures).  Both follow real SWU deckbuilding rules: a unique card may sit in a
deck up to its normal copy cap (3, or a per-card override) — the "unique" rule
only forbids two copies *in play* — and the copy cap is keyed on the card's full
name (title + subtitle), NOT its DB id, so two printings of the same card (a
reprint or promo, same title+subtitle but different id) are counted **together**
toward one cap: you cannot exceed 3 by mixing printings.

Two public functions:

* ``deckbuild_max_copies(card)`` — the per-card copy cap.  Default 3; some cards
  print an override ("A deck can have up to 15 copies of this card." — Swarming
  Vulture Droid JTL_256 / JTLP_20), parsed from the card text.
* ``deck_errors(leader, base, cards, repo)`` — the builder's rule checker.  Returns
  a list of human-readable rule violations (empty ⇒ a complete, legal deck): the
  exactly-1-leader / exactly-1-base rule, the ==50 other cards rule, and the
  per-card copy cap.  A *draft* (half-built deck) naturally has entries here (e.g.
  "needs a leader") — the caller derives ``complete`` as "no errors".
"""
from __future__ import annotations

import re
from typing import Mapping, Optional

from swu.cards.models import AnyCard, Base, Leader
from swu.cards.repository import CardRepository

# Card types created during play, never legal in a deck list.
TOKEN_TYPES = frozenset(
    {"Token Unit", "Token Upgrade", "Credit Token", "Force Token"}
)

# Types allowed in the 50-card pool (everything that isn't a leader, base or token).
POOL_TYPES = frozenset({"Unit", "Event", "Upgrade"})

DECK_SIZE = 50
DEFAULT_MAX_COPIES = 3

_MAX_COPIES_RE = re.compile(
    r"a deck can have up to (\d+) copies of this card", re.IGNORECASE
)


def deck_size_for(base: Optional[AnyCard]) -> int:
    """The number of pool cards a deck built on ``base`` needs.

    ``DECK_SIZE`` (50) unless the base carries a registered ``DeckSizeModifier``
    marker — "Your minimum deck size is increased by 10 cards" (Data Vault JTL_24)
    → 60, "…decreased by 5 cards" (Thermal Oscillator JTL_25) → 45.  The single
    place that knows the number, so the validator, the builder's completeness flag
    and the precon check all shift together.

    Note the engine's convention that 50 is EXACT rather than the CR's *minimum*;
    the marker shifts that exact number rather than opening a range."""
    if base is None or not isinstance(base, Base):
        return DECK_SIZE
    set_code = getattr(base, "set_code", None)
    number = getattr(base, "card_number", None)
    if not set_code or number is None:
        return DECK_SIZE
    from swu.abilities.registry import get_abilities, DeckSizeModifier
    amount = sum(spec.amount for spec in get_abilities(set_code, str(number))
                 if isinstance(spec, DeckSizeModifier))
    return DECK_SIZE + amount


def deckbuild_max_copies(card: AnyCard) -> int:
    """The maximum number of copies of ``card`` a deck may contain.

    Default 3; a card printing "A deck can have up to N copies of this card."
    raises the cap to N.  ``\\xa0`` (non-breaking space, present in some DB rows)
    is normalised before matching.
    """
    text = (getattr(card, "text", None) or "").replace("\xa0", " ")
    m = _MAX_COPIES_RE.search(text)
    return int(m.group(1)) if m else DEFAULT_MAX_COPIES


def deck_errors(
    leader: Optional[AnyCard],
    base: Optional[AnyCard],
    cards: Mapping[int | str, int],
    repo: CardRepository,
) -> list[str]:
    """Return the deck's rule violations (empty ⇒ complete & legal).

    ``leader``/``base`` are the resolved slot cards (or ``None`` for an empty
    slot); ``cards`` maps a DB card id (int or str) → copy count for the 50-card
    pool; ``repo`` resolves those ids for the copy-cap and type checks.
    """
    errors: list[str] = []

    # -- leader slot --
    if leader is None:
        errors.append("Deck needs a leader.")
    elif not isinstance(leader, Leader):
        errors.append(f"{leader.name!r} is not a Leader card.")

    # -- base slot --
    if base is None:
        errors.append("Deck needs a base.")
    elif not isinstance(base, Base):
        errors.append(f"{base.name!r} is not a Base card.")

    # -- the 50-card pool --
    # Copy caps are keyed on the card's full name (title + subtitle), NOT on the
    # DB id: two different printings of the same card (a reprint/promo) share one
    # cap, so 3× the SHD printing + 3× the promo printing is 6 copies of one card
    # — over the limit — not two independent 3s.
    total = 0
    grouped: dict[str, list] = {}  # display_name -> [(card, count), ...]
    for raw_id, count in cards.items():
        count = int(count)
        if count <= 0:
            continue
        total += count
        card = repo.by_id(int(raw_id))
        if card is None:
            errors.append(f"Unknown card id {raw_id}.")
            continue
        if card.type in TOKEN_TYPES or isinstance(card, (Leader, Base)):
            errors.append(f"{card.name!r} cannot go in the deck.")
            continue
        grouped.setdefault(card.display_name, []).append((card, count))

    for display_name, entries in grouped.items():
        group_count = sum(c for _, c in entries)
        # A reprint override raises the cap for the whole name group.
        cap = max(deckbuild_max_copies(card) for card, _ in entries)
        if group_count > cap:
            errors.append(
                f"Too many copies of {display_name!r}: {group_count} (max {cap})."
            )

    required = deck_size_for(base)
    if total != required:
        errors.append(f"Deck has {total} cards; needs exactly {required}.")

    return errors
