"""
SWUDB decklist import (Phase 7, Part D).

Takes a SWUDB-format decklist (a pasted JSON object, or a deck id/url fetched
over HTTP) and:
  * normalises it to our fixture format (already very close),
  * validates every card resolves against ``data/swu.db`` and the deck is legal,
  * reports which cards are not yet playable (the engine governs play, so an
    imported deck with gaps is importable but those cards will do nothing),
  * optionally writes the normalised fixture to disk so the encoding planner can
    immediately produce its groups (``python scripts/plan_encoding.py --deck …``).

The card-playability classification mirrors the planner's strong rule (registry
membership + functional-text detection); see scripts/plan_encoding.py and
tests/test_deck_coverage.py for the canonical statement of that rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import swu.cards  # noqa: F401 — side-effect: registers all sets so classification is accurate
from swu.abilities.registry import get_abilities
from swu.cards.decklist import parse_decklist, validate_decklist
from swu.cards.repository import CardRepository

# Mirror scripts/audit_coverage.py: Smuggle (shd-han-solo:01), Plot
# (jabba-the-hutt:01), Hidden (jabba-the-hutt:02), and Piloting (boba-fett:01)
# are implemented engine-side, so they are Phase-2 (playable) keywords.
PHASE2_KEYWORDS = {
    "Sentinel", "Overwhelm", "Raid", "Ambush", "Restore", "Saboteur",
    "Shielded", "Grit", "Exploit", "Smuggle", "Plot", "Hidden", "Piloting",
    "Support",   # implemented engine-side (ash-set:01)
}
DEFERRED_KEYWORDS = {
    "Bounty", "Coordinate",
}

_REMINDER_RE = re.compile(r"\([^)]*\)")        # reminder text in parentheses
_BRACKET_RE = re.compile(r"\[[^\]]*\]")        # smuggle/bounty cost notation
_WORD_RE = re.compile(r"[A-Za-z']+")


def _has_functional_text(card) -> bool:
    # Mirror the canonical functional-text rule (audit_coverage.has_functional_text /
    # plan_encoding): strip reminder parentheticals AND keyword cost brackets
    # (e.g. "Smuggle [5 resources Aggression Heroism]"), then subtract the card's
    # own keyword names — so a pure-keyword card (e.g. a plain-Smuggle unit like
    # Nite Owl Skirmisher SHD_149) is not mis-flagged as text-bearing.
    text = (getattr(card, "text", None) or "") + "\n" + (getattr(card, "deploy_box", None) or "")
    text = _REMINDER_RE.sub("", text)
    text = _BRACKET_RE.sub("", text)
    own_kw = {k.lower() for k in (getattr(card, "keywords", ()) or ())}
    return any(w.lower() not in own_kw for w in _WORD_RE.findall(text))


def classify(card) -> str:
    key = (card.set_code, str(card.card_number))
    if get_abilities(*key):
        return "implemented"
    kws = set(getattr(card, "keywords", ()) or ())
    if kws & DEFERRED_KEYWORDS:
        return "keyword-deferred"
    if _has_functional_text(card):
        return "text-bearing"
    if kws & PHASE2_KEYWORDS:
        return "keyword-complete"
    return "vanilla"


_PLAYABLE = {"implemented", "keyword-complete", "vanilla"}


@dataclass
class ImportReport:
    ok: bool                       # deck is legal AND fully playable
    legal: bool                    # deck-construction valid
    errors: list[str] = field(default_factory=list)
    total_cards: int = 0
    playable_cards: int = 0
    unimplemented: list[dict] = field(default_factory=list)  # {id,name,label,count}
    fixture_path: Optional[str] = None
    planner_hint: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "legal": self.legal, "errors": self.errors,
            "total_cards": self.total_cards, "playable_cards": self.playable_cards,
            "unimplemented": self.unimplemented,
            "fixture_path": self.fixture_path, "planner_hint": self.planner_hint,
        }


def import_deck(data: dict, repo: CardRepository,
                write_to: Optional[Path] = None, slug: str = "imported") -> ImportReport:
    """Validate + classify a SWUDB-format decklist dict."""
    cards = parse_decklist(data, repo)          # flat list, counts expanded
    errors = validate_decklist(cards)

    # Per distinct card: classify and tally copies.
    by_key: dict[tuple, list] = {}
    for c in cards:
        by_key.setdefault((c.set_code, str(c.card_number)), []).append(c)

    total = len(cards)
    playable = 0
    unimplemented: list[dict] = []
    for (sc, cn), copies in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        card = copies[0]
        label = classify(card)
        if label in _PLAYABLE:
            playable += len(copies)
        else:
            unimplemented.append({
                "id": f"{sc}_{cn}", "name": card.name,
                "label": label, "count": len(copies),
            })

    fixture_path = None
    planner_hint = None
    if write_to is not None:
        write_to.parent.mkdir(parents=True, exist_ok=True)
        import json
        write_to.write_text(json.dumps(_normalise(data), indent=2), encoding="utf-8")
        fixture_path = str(write_to)
        planner_hint = f"python scripts/plan_encoding.py --deck {fixture_path}"

    return ImportReport(
        ok=(not errors and not unimplemented),
        legal=not errors,
        errors=errors,
        total_cards=total,
        playable_cards=playable,
        unimplemented=unimplemented,
        fixture_path=fixture_path,
        planner_hint=planner_hint,
    )


def _normalise(data: dict) -> dict:
    """SWUDB JSON is already our fixture shape; pass through leader/base/deck."""
    out: dict = {}
    if "leader" in data:
        out["leader"] = data["leader"] if isinstance(data["leader"], dict) else {"id": data["leader"]}
    if "base" in data:
        out["base"] = data["base"] if isinstance(data["base"], dict) else {"id": data["base"]}
    out["deck"] = [
        e if isinstance(e, dict) else {"id": e}
        for e in data.get("deck", [])
    ]
    return out


def fetch_swudb_deck(ref: str, fetch_fn: Optional[Callable[[str], dict]] = None) -> dict:
    """Fetch a deck JSON by SWUDB url or deck id.

    ``fetch_fn`` is injectable for tests/offline use.  The default uses httpx
    against the SWUDB deck JSON endpoint.
    """
    if fetch_fn is not None:
        return fetch_fn(ref)
    deck_id = ref.rstrip("/").split("/")[-1] if "/" in ref else ref
    import httpx
    url = f"https://swudb.com/api/deck/{deck_id}/json"
    resp = httpx.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()
