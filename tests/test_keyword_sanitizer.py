"""
Tests for swu.cards.keyword_sanitizer — corrects the upstream data quirk where
a card is tagged with a keyword it only *grants to other units*.

The reported bug: Admiral Piett (SOR 079) entered play with Ambush and attacked
immediately, even though his keyword bar is empty and his text only grants
Ambush to *other* friendly non-leader units costing 6+.

These are pure-function tests (no DB needed); DB-backed and behavioural
coverage lives in tests/test_sor_cards.py::TestAdmiralPiett.
"""
from __future__ import annotations

import pytest

from swu.cards.keyword_sanitizer import sanitize_keywords


# ── The bug: keyword granted to OTHER units must be stripped ──────────────────

@pytest.mark.parametrize("name, text, printed, kept", [
    (
        "Admiral Piett",
        "Each friendly non-leader unit that costs 6 or more gains Ambush. "
        "(After you play that unit, it may ready and attack an enemy unit.)",
        ("Ambush",), (),
    ),
    (
        "Wedge Antilles",
        "Each friendly VEHICLE unit gets +1/+1 and gains Ambush. "
        "(After you play that unit, it may ready and attack an enemy unit.)",
        ("Ambush",), (),
    ),
    (
        "Benthic Two Tubes",
        "On Attack: Another friendly Aggression unit gains Raid 2 for this phase. "
        "(It gets +2/+0 while attacking.)",
        ("Raid",), (),
    ),
    (
        "General Hux",
        "Each other friendly First Order unit gains Raid 1. "
        "(They get +1/+0 while attacking.)",
        ("Raid",), (),
    ),
    (
        "Obi-Wan Kenobi",
        "Other friendly Republic units gain Restore 1.",
        ("Restore",), (),
    ),
    (
        "King Katuunko",
        "When Played: All units (including enemy units) gain Restore 1 for this phase.",
        ("Restore",), (),
    ),
    (
        "Sabine Wren (next-unit grant)",
        "Action [Exhaust]: ... the next unit you play this phase gains Shielded "
        "for this phase. (When you play that unit, give a Shield token to it.)",
        ("Shielded",), (),
    ),
])
def test_strips_keyword_granted_to_others(name, text, printed, kept):
    assert sanitize_keywords("Unit", text, printed) == kept


def test_strips_one_of_two_granted_keywords_keeps_real_one():
    """BD-1: bar shows Hidden (real); Saboteur is only granted to a chosen unit."""
    text = (
        "Hidden\n"
        "When Played: Choose another friendly unit. While this unit is in play, "
        "the chosen unit gets +1/+0 and gains Saboteur."
    )
    assert sanitize_keywords("Unit", text, ("Hidden", "Saboteur")) == ("Hidden",)


# ── Must NOT strip: card genuinely possesses the keyword ──────────────────────

@pytest.mark.parametrize("name, text, printed", [
    (
        "Home One",  # leading 'Restore 2' bar token; also grants Restore 1 to others
        "Restore 2\nEach other friendly unit gains Restore 1.\n"
        "When Played: Play a Heroism unit from your discard pile.",
        ("Restore",),
    ),
    (
        "Red Three",
        "Raid 1 (This unit gets +1/+0 while attacking.)  "
        "Each other friendly Heroism unit gains Raid 1.",
        ("Raid",),
    ),
    (
        "4-LOM",
        "Ambush (When you play this unit, it may ready and attack an enemy unit.) "
        "Each friendly unit named Zuckuss gets +1/+1.",
        ("Ambush",),
    ),
    (
        "Onyx Cinder",
        "Hidden\nOther friendly units gain Hidden.",
        ("Hidden",),
    ),
])
def test_keeps_keyword_present_in_bar(name, text, printed):
    assert sanitize_keywords("Unit", text, printed) == printed


@pytest.mark.parametrize("name, text, kw", [
    ("First Legion Snowtrooper",
     "While attacking a damaged unit, this unit gets +2/+0 and gains Overwhelm. "
     "(Deal excess damage to the opponent's base.)", "Overwhelm"),
    ("Jango Fett",
     "While attacking a unit with a Bounty, this unit gets +3/+0 and gains Overwhelm.",
     "Overwhelm"),
    ("Jyn Erso",
     "While an enemy unit has been defeated this phase, this unit gets +1/+0 and "
     "gains Saboteur.", "Saboteur"),
])
def test_keeps_conditional_self_grant(name, text, kw):
    """'this unit gains K' is a self-buff, not a grant to others — keep it."""
    assert sanitize_keywords("Unit", text, (kw,)) == (kw,)


# ── Reference-only keyword: '…with K' names a property of OTHER cards ──────────
# Regression: Refugee of The Path LOF_242 was tagged Sentinel (the API scraped the
# word out of its ability text) and so forced enemy attacks onto itself, blocking
# an attack on the base. The card's printed bar is empty.

@pytest.mark.parametrize("name, text, kw", [
    ("Refugee of The Path",
     "When Played: You may give a Shield token to a unit with Sentinel.", "Sentinel"),
    ("Kylo Ren's Command Shuttle",
     "Each friendly ground unit with Sentinel gets +0/+2.", "Sentinel"),
    ("Chancellor Palpatine",
     "Action [1 resource, Exhaust]: Search the top 5 cards of your deck for a card "
     "with Plot, reveal it, and draw it.", "Plot"),
])
def test_strips_reference_only_keyword(name, text, kw):
    """A keyword that only ever appears as '…with K' is not possessed — strip it."""
    assert sanitize_keywords("Unit", text, (kw,)) == ()


def test_keeps_possessed_keyword_even_when_also_referenced():
    """A reminder/bar mention alongside a '…with K' reference means it's real."""
    text = ("Sentinel (Units must attack this unit if able.) "
            "When Played: Give a Shield token to another unit with Sentinel.")
    assert sanitize_keywords("Unit", text, ("Sentinel",)) == ("Sentinel",)


# ── Scope: only Unit/Leader cards are sanitised ───────────────────────────────

def test_upgrades_and_events_are_not_sanitised():
    # An upgrade that grants Sentinel keeps it (its keyword is the grant seam).
    text = "Attached unit gains Sentinel."
    assert sanitize_keywords("Upgrade", text, ("Sentinel",)) == ("Sentinel",)
    assert sanitize_keywords("Event", "Each friendly unit gains Raid 2 this phase.",
                             ("Raid",)) == ("Raid",)


def test_leader_is_sanitised():
    text = "Action [Exhaust]: A friendly unit gains Raid 1 for this phase."
    assert sanitize_keywords("Leader", text, ("Raid",)) == ()


# ── Robustness ────────────────────────────────────────────────────────────────

def test_no_text_passes_through():
    assert sanitize_keywords("Unit", None, ("Ambush",)) == ("Ambush",)


def test_unrelated_keyword_untouched():
    """A keyword neither granted nor mentioned passes through unchanged."""
    text = "Each friendly non-leader unit that costs 6 or more gains Ambush."
    assert sanitize_keywords("Unit", text, ("Sentinel",)) == ("Sentinel",)


def test_unknown_keyword_passes_through():
    # Defensive: a non-keyword tag we don't recognise is never stripped.
    assert sanitize_keywords("Unit", "blah gains Foo", ("Foo",)) == ("Foo",)
