"""
Deterministic deck-coverage gate — catches "card does nothing" bugs at CI time.

WHY THIS EXISTS
---------------
Surprise Strike (SOR_220) shipped in the Luke starter deck as an
``escape_hatch=True`` stub that returned ``[]`` — playing it did *nothing*.
Two things let it slip through:

1. The random-bot soak can't catch a no-op: a card that produces no effect
   leaves a perfectly valid game state, so no structural/semantic invariant
   fires.  The coverage tracker listed it as "zero-fire active", but that bucket
   is excused as "probably an escape-hatch stub" — nothing connected "OK to
   defer" to "this card is in a deck people play".
2. Even the coverage *audit* mislabels it: ``audit_coverage._has_ability_text``
   only matches trigger words ("When", "On Attack", "Action:"…).  Surprise
   Strike's text — "Attack with a unit. It gets +3/+0 for this attack." — matches
   none, so the audit would call an unimplemented Surprise Strike *vanilla*.

This test closes both gaps with a self-contained, heuristic-free rule:

    A card in a shipped deck that has FUNCTIONAL TEXT (anything beyond its own
    keywords + reminder text) MUST have a non-empty ability registration,
    unless it is on the explicit KNOWN_NOOP_DEFERRED allow-list below.

Functional-text detection uses the card's *own declared keywords* (not a guessed
pattern list), so "Restore 1 (When this unit attacks…)" is correctly seen as
keyword-only and engine-handled, while "Attack with a unit…" is seen as needing
an implementation.

Discipline (mirrors the per-card xfail list):
  * A shipped card with functional text and an empty registration that is NOT on
    the list (e.g. Surprise Strike regressing to a stub) -> this test FAILS.
  * When you implement a deferred card, REMOVE its entry; the stale-entry check
    FAILS if you forget, so the list cannot rot.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# Decks that ship and are meant to be fully playable end-to-end.
SHIPPED_DECKS = ["starter_luke", "starter_vader"]

# Shipped-deck cards with functional text whose ability is knowingly NOT
# implemented yet (registration returns []).  This is the single reviewed
# registry of deferred no-op cards.  key -> reason.  Keep it honest.
KNOWN_NOOP_DEFERRED: dict[tuple[str, str], str] = {
    # Empty — every shipped-deck card with functional text is implemented.
    # (Admiral Ozzel, SOR_129, was the last entry; it now uses the
    # play-from-hand subsystem — see actions.push_play_from_hand.)
}

_REMINDER_RE = re.compile(r"\([^)]*\)")  # strip reminder text in parentheses
_WORD_RE = re.compile(r"[A-Za-z']+")


def _has_functional_text(card) -> bool:
    """True if the card's text carries an ability beyond its own keywords.

    Strips reminder parentheticals and the card's *own* declared keyword names;
    if any prose word remains, the card needs an implementation.
    """
    text = (getattr(card, "text", None) or "") + "\n" + (getattr(card, "deploy_box", None) or "")
    text = _REMINDER_RE.sub("", text)
    own_kw = {k.lower() for k in (getattr(card, "keywords", ()) or ())}
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return any(w not in own_kw for w in words)


def _deck_cards(name: str, repo):
    """Distinct card defs in a deck fixture (leader + base + deck), de-duplicated by key."""
    from swu.cards.decklist import load_decklist
    path = _ROOT / "tests" / "fixtures" / f"{name}.json"
    out, seen = [], set()
    for c in load_decklist(path, repo):
        key = (c.set_code, c.card_number)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


@pytest.fixture(scope="module")
def _registry():
    import swu.cards.sor  # noqa: F401 — side effect: register SOR cards
    from swu.abilities.registry import get_abilities
    return get_abilities


def _noop_cards(repo, get_abilities) -> dict[tuple[str, str], str]:
    """{key: name} for shipped-deck cards with functional text but empty registration."""
    bad: dict[tuple[str, str], str] = {}
    seen: set[tuple[str, str]] = set()
    for deck in SHIPPED_DECKS:
        for c in _deck_cards(deck, repo):
            key = (c.set_code, c.card_number)
            if key in seen:
                continue
            seen.add(key)
            if _has_functional_text(c) and len(get_abilities(*key)) == 0:
                bad[key] = c.name
    return bad


class TestShippedDeckCoverage:
    def test_no_unexpected_noop_cards(self, repo, _registry):
        """No shipped-deck card may silently do nothing unless explicitly deferred."""
        noop = _noop_cards(repo, _registry)
        unexpected = {k: v for k, v in noop.items() if k not in KNOWN_NOOP_DEFERRED}
        assert not unexpected, (
            "Shipped-deck cards have functional text but an EMPTY ability "
            "registration (they do nothing when played) and are not on "
            "KNOWN_NOOP_DEFERRED — a stub regression or a new unimplemented card:\n  "
            + "\n  ".join(f"{k[0]}_{k[1]}: {v}" for k, v in sorted(unexpected.items()))
        )

    def test_allowlist_has_no_stale_entries(self, repo, _registry):
        """A deferred card that is now implemented must be removed from the list."""
        noop = _noop_cards(repo, _registry)
        stale = [k for k in KNOWN_NOOP_DEFERRED if k not in noop]
        assert not stale, (
            "These cards are now implemented (or no longer in a shipped deck) — "
            "remove them from KNOWN_NOOP_DEFERRED:\n  "
            + "\n  ".join(f"{k[0]}_{k[1]}" for k in sorted(stale))
        )

    def test_surprise_strike_is_implemented(self, repo, _registry):
        """Pin the just-fixed card: it must never regress to a no-op stub."""
        key = ("SOR", "220")
        assert len(_registry(*key)) > 0, (
            "Surprise Strike (SOR_220) has an empty registration again — it must "
            "stay implemented (grants +3/+0 to an attacking unit)."
        )
        assert key not in KNOWN_NOOP_DEFERRED, "SOR_220 is implemented; don't defer it."

    def test_admiral_ozzel_is_implemented(self, repo, _registry):
        """Pin the last shipped-deck stub: Admiral Ozzel must stay implemented.

        SOR_129 was the final KNOWN_NOOP_DEFERRED entry; it now uses the
        play-from-hand subsystem (an ActivatedAbility, not an escape-hatch stub).
        """
        from swu.abilities.registry import is_escape_hatch, ActivatedAbility
        key = ("SOR", "129")
        specs = _registry(*key)
        assert len(specs) > 0, "Admiral Ozzel (SOR_129) has an empty registration again."
        assert any(isinstance(s, ActivatedAbility) for s in specs), (
            "Admiral Ozzel must expose its 'play an Imperial unit from hand' "
            "ActivatedAbility."
        )
        assert not is_escape_hatch(*key), "SOR_129 is implemented; drop the escape_hatch flag."
        assert key not in KNOWN_NOOP_DEFERRED, "SOR_129 is implemented; don't defer it."
