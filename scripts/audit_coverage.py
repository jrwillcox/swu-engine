"""
Registry-aware coverage audit.

Classifies every card in the DB as one of:
  vanilla          — no keywords, no ability text  (Phase 1 handles fully)
  keyword-complete — only Phase 2 keywords          (Phase 2 handles fully)
  implemented      — registered in the ability registry with real logic
  escape-hatch     — registered with escape_hatch=True (simplified/stub)
  keyword-deferred — has an unimplemented Phase 3 keyword (Support)
  text-bearing     — has ability text but NOT registered  (gap)

Usage:
    python scripts/audit_coverage.py [--db path/to/swu.db] [--output path]
    python scripts/audit_coverage.py --deck tests/fixtures/starter_luke.json
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ── Keyword sets ─────────────────────────────────────────────────────────────

PHASE2_KEYWORDS = frozenset({
    "Sentinel", "Overwhelm", "Raid", "Ambush",
    "Restore", "Saboteur", "Shielded", "Grit", "Exploit",
    "Smuggle",     # Phase 7: implemented engine-side (shd-han-solo:01)
    "Plot",        # Phase 7: implemented engine-side (jabba-the-hutt:01)
    "Hidden",      # Phase 7: implemented engine-side (jabba-the-hutt:02)
    "Piloting",    # Phase 7: implemented engine-side (boba-fett:01)
    "Coordinate",  # Phase 7: implemented engine-side as an ability template (ahsoka-tano:01, CONTROLLER_N_PLUS_UNITS)
    "Bounty",      # Phase 7: implemented engine-side as an ability template (shd-han-solo:02, GrantedAbility WhenDefeated)
    "Support",     # Phase 7: implemented engine-side (ash-set:01, granted_attack + borrowed abilities)
})

# Genuinely-unimplemented keywords: a card whose ONLY functional content is one of
# these is a real gap.  EMPTY since ash-set:01 landed Support — every printed SWU
# keyword is now modelled engine-side.
PHASE3_KEYWORDS: frozenset[str] = frozenset()

ALL_KNOWN_KEYWORDS = PHASE2_KEYWORDS | PHASE3_KEYWORDS

# Token card types. The DB's true unique key is the ``id`` column; the SWUDB
# ``{set}_{number}`` reference is NOT unique — every Leader (numbered 1, 2, 3, …)
# collides with a Token (Token Unit / Token Upgrade / Credit/Force Token) that
# reuses the same low number. Decklists only ever reference real cards, never
# tokens, so when we must resolve a (set, number) reference we prefer the
# non-token row (see ``index_by_set_number``).
TOKEN_TYPES = frozenset({
    "Token Unit", "Token Upgrade", "Credit Token", "Force Token",
})

# Tokens whose printed text IS a rule the engine implements natively, rather than
# through the ability registry. They are fully playable and must NOT be given a
# registry entry — registering one would add a second, conflicting implementation
# on top of the engine's.
#
# Shield: "If damage would be dealt to attached unit, prevent that damage. If you
# do, defeat a Shield token on it." — implemented at
# swu.engine.actions._deal_damage_with_shield, which every combat and
# ability-damage path routes through, and covered by tests/test_keywords.py
# (absorbs one full damage instance, consumed exactly once, correct alongside
# Saboteur / Overwhelm / Ambush).
#
# Matched on NAME + token type rather than (set, number) so a future set's
# reprint of the same token is recognised automatically. Without this, exactly one
# of the eight Shield rows in the DB audits as a gap: the other seven share a
# (set, number) key with a registered Leader and so inherit an "implemented"
# verdict from ``index_by_set_number``, while GG_6 has no such twin and survives
# to be classified on its own.
ENGINE_NATIVE_TOKEN_NAMES = frozenset({"Shield"})

# ── Text-bearing detection ────────────────────────────────────────────────────
#
# Heuristic-free, registry-independent functional-text rule (the authoritative
# detector, mirrored in tests/test_deck_coverage.py and reused by
# scripts/plan_encoding.py): strip reminder parentheticals and keyword cost
# brackets, then subtract the card's OWN declared keyword names; if any prose
# word survives, the card carries an ability beyond its keyword bar and needs an
# implementation.
#
# This replaces the old trigger-word pattern list (``_has_ability_text``), which
# only matched "When"/"On Attack"/"Action:"… and so mislabelled every
# plain-effect or conditional-static card ("Deal 2 damage…", "While X, this unit
# gains…") as *vanilla* — the documented flaw in tests/test_deck_coverage.py that
# made the headline "playable" count over-report by hundreds of cards.

_REMINDER_RE = re.compile(r"\([^)]*\)")        # reminder text in parentheses
_BRACKET_RE = re.compile(r"\[[^\]]*\]")        # smuggle/bounty cost notation
_WORD_RE = re.compile(r"[A-Za-z']+")
# An upgrade's "Attach to …" clause is a declarative attachment RESTRICTION, not
# an ability — the engine parses it automatically (actions._upgrade_target_spec)
# and applies the upgrade's printed stats, so an upgrade whose ONLY text is such a
# clause is fully playable as a vanilla stat upgrade. Strip it before the prose
# check so it is not mistaken for functional text (the "register-as-vanilla"
# exemption; the terminating period means a clause followed by real ability text
# — "Attach to a non-Vehicle unit. Attached unit gains …" — keeps that ability).
_ATTACH_CLAUSE_RE = re.compile(r"attach to an? [^.\n]+\.", re.IGNORECASE)


def has_functional_text(full_text: str | None, keywords: "Iterable[str]" = ()) -> bool:
    """True if ``full_text`` carries an ability beyond the card's own keywords.

    ``full_text`` should be the card's combined rules text (text + deploy_box +
    epic_action). ``keywords`` is the card's own declared keyword names, which
    are subtracted so a pure-keyword card ("Raid 2 (This unit gets +2/+0…)") is
    not flagged.
    """
    if not full_text:
        return False
    text = _REMINDER_RE.sub("", full_text)
    text = _BRACKET_RE.sub("", text)
    text = _ATTACH_CLAUSE_RE.sub("", text)
    own_kw = {k.lower() for k in keywords}
    return any(w.lower() not in own_kw for w in _WORD_RE.findall(text))


def _has_ability_text(text: str | None) -> bool:
    """Deprecated thin shim — kept for backwards compatibility.

    Prefer :func:`has_functional_text`, which subtracts the card's own keywords.
    This shim has no keyword context, so it reports any prose word as functional.
    """
    return has_functional_text(text, ())


# ── Card loading ──────────────────────────────────────────────────────────────

@dataclass
class CardRow:
    id: int
    name: str
    card_type: str
    set_code: str
    card_number: str
    cost: int | None
    text: str | None
    deploy_box: str | None
    epic_action: str | None = None
    keywords: set[str] = field(default_factory=set)

    @property
    def full_text(self) -> str:
        """Combined rules text (text + deploy_box + epic_action), \xa0 normalised."""
        parts = [self.text, self.deploy_box, self.epic_action]
        return "\n".join(p for p in parts if p).replace("\xa0", " ").replace("’", "'")


def load_cards(db_path: str) -> list[CardRow]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, name, type, set_code, card_number, cost, text, deploy_box, "
        "epic_action FROM cards"
    ).fetchall()
    cards_by_id: dict[int, CardRow] = {}
    for r in rows:
        cards_by_id[r["id"]] = CardRow(
            id=r["id"], name=r["name"], card_type=r["type"],
            set_code=r["set_code"], card_number=r["card_number"],
            cost=r["cost"], text=r["text"], deploy_box=r["deploy_box"],
            epic_action=r["epic_action"],
        )
    kw_rows = con.execute("SELECT card_id, name FROM card_keywords").fetchall()
    for kwr in kw_rows:
        if kwr["card_id"] in cards_by_id:
            cards_by_id[kwr["card_id"]].keywords.add(kwr["name"])
    con.close()
    return list(cards_by_id.values())


def index_by_set_number(cards: "Iterable[CardRow]") -> dict[tuple[str, str], CardRow]:
    """Index cards by their (set_code, card_number) reference, resolving the
    Leader-vs-Token collision in favour of the real (non-token) card.

    ``{set}_{number}`` is how decklists reference cards, but it is not unique (a
    Leader and a Token share the same low number). Decklists never reference
    tokens, so on a collision we keep the non-token row; a token is kept only
    when no real card shares its key.
    """
    idx: dict[tuple[str, str], CardRow] = {}
    for c in cards:
        key = (c.set_code, c.card_number)
        existing = idx.get(key)
        if existing is None or (
            existing.card_type in TOKEN_TYPES and c.card_type not in TOKEN_TYPES
        ):
            idx[key] = c
    return idx


# ── Registry lookup ───────────────────────────────────────────────────────────

def _load_registry() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Return (registered_keys, escape_hatch_keys) after importing all card modules."""
    try:
        import swu.cards.sor  # noqa: F401 — side-effect: registers SOR cards
        from swu.abilities.registry import get_all_registered, is_escape_hatch
        registered: set[tuple[str, str]] = set()
        escape_hatch: set[tuple[str, str]] = set()
        for key in get_all_registered():
            registered.add(key)
            if is_escape_hatch(key[0], key[1]):
                escape_hatch.add(key)
        return registered, escape_hatch
    except ImportError:
        return set(), set()


# ── Classification ────────────────────────────────────────────────────────────

def classify(
    card: CardRow,
    registered: set[tuple[str, str]],
    escape_hatch: set[tuple[str, str]],
) -> str:
    key = (card.set_code, card.card_number)

    has_p3 = bool(card.keywords & PHASE3_KEYWORDS)
    has_p2 = bool(card.keywords & PHASE2_KEYWORDS)
    unknown_kws = card.keywords - ALL_KNOWN_KEYWORDS
    has_unknown_kw = bool(unknown_kws)

    has_text = has_functional_text(card.full_text, card.keywords)

    # Registry check takes priority over text classification
    if key in registered:
        if key in escape_hatch:
            return "escape-hatch"
        return "implemented"

    # Engine-native tokens: playable without a registry entry (see
    # ENGINE_NATIVE_TOKEN_NAMES). Checked after the registry so a genuine
    # registration still wins, and before the text check so the token's printed
    # rule is not mistaken for an unimplemented ability.
    #
    # getattr, not attribute access: callers may pass a reduced row carrying only
    # the four fields this function is documented to need — swu.web.explorer does
    # exactly that, and it filters tokens out before classifying anyway, so the
    # missing fields simply mean "not an engine-native token".
    if (getattr(card, "card_type", None) in TOKEN_TYPES
            and getattr(card, "name", None) in ENGINE_NATIVE_TOKEN_NAMES):
        return "implemented"

    if has_p3 or has_unknown_kw:
        return "keyword-deferred"
    if has_text:
        return "text-bearing"
    if has_p2:
        return "keyword-complete"
    return "vanilla"


def is_playable(label: str) -> bool:
    """True if the card can be played correctly in the engine."""
    return label in ("vanilla", "keyword-complete", "implemented")


# ── Per-deck readiness ────────────────────────────────────────────────────────

def audit_deck(deck_path: Path, db_path: str) -> None:
    """Print per-deck readiness: N/M cards playable and list the gaps."""
    registered, escape_hatch = _load_registry()
    cards = index_by_set_number(load_cards(db_path))

    import json
    data = json.loads(deck_path.read_text(encoding="utf-8"))

    # Flatten decklist entries
    entries: list[tuple[str, str, int]] = []  # (set_code, card_number, count)
    def _parse(entry: dict) -> None:
        cid = entry.get("id") or entry.get("card_id", "")
        count = int(entry.get("count", 1))
        if "_" in cid:
            sc, cn = cid.split("_", 1)
            cn = str(int(cn)) if cn.isdigit() else cn
            entries.append((sc, cn, count))

    if "leader" in data:
        _parse(data["leader"] if isinstance(data["leader"], dict) else {"id": data["leader"]})
    if "base" in data:
        _parse(data["base"] if isinstance(data["base"], dict) else {"id": data["base"]})
    for e in data.get("deck", []):
        _parse(e)

    total_cards = sum(c for _, _, c in entries)
    playable = 0
    gaps: list[str] = []

    print(f"\nDeck readiness audit: {deck_path.name}\n")
    print(f"  {'Card':<40} {'x':>2}  {'Status'}")
    print(f"  {'-'*40}  --  ------")

    for sc, cn, count in entries:
        card = cards.get((sc, cn))
        if card is None:
            label = "not-in-db"
        else:
            label = classify(card, registered, escape_hatch)
        is_ok = is_playable(label)
        playable += count if is_ok else 0
        name = card.name if card else f"{sc}_{cn}"
        flag = "" if is_ok else "  << gap"
        print(f"  {name:<40} x{count}  {label}{flag}")
        if not is_ok:
            gaps.append(f"{name} ({sc}_{cn}) [{label}]")

    print(f"\n  {playable}/{total_cards} cards playable")
    if gaps:
        print(f"\n  Gaps ({len(gaps)}):")
        for g in gaps:
            print(f"    - {g}")
    else:
        print("\n  All cards playable — deck is ready!")


# ── Main audit ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Registry-aware SWU coverage audit")
    parser.add_argument("--db", default="data/swu.db")
    parser.add_argument("--output", default="docs/coverage_report.md")
    parser.add_argument("--deck", default=None,
                        help="Path to a JSON decklist — prints per-deck readiness")
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        sys.exit(f"DB not found: {db}")

    if args.deck:
        audit_deck(Path(args.deck), str(db))
        return

    registered, escape_hatch = _load_registry()
    cards = load_cards(str(db))

    by_type: dict[str, list[CardRow]] = defaultdict(list)
    for c in cards:
        by_type[c.card_type].append(c)

    totals: Counter[str] = Counter()
    type_counts: dict[str, Counter] = {}

    for ct in sorted(by_type.keys()):
        counts: Counter[str] = Counter()
        for c in by_type[ct]:
            label = classify(c, registered, escape_hatch)
            counts[label] += 1
            totals[label] += 1
        type_counts[ct] = counts

    grand_total = sum(totals.values())

    print(f"\nCoverage Audit  ({len(cards)} cards total, "
          f"{len(registered)} registered in ability registry)\n")
    w = 14
    header = (f"{'Type':<{w}} {'vanilla':>9} {'kw-cmpl':>9} {'impl':>9}"
              f" {'esc-hatch':>10} {'kw-def':>8} {'text-bear':>10} {'total':>7}")
    print(header)
    print("-" * len(header))
    for ct in sorted(type_counts.keys()):
        c = type_counts[ct]
        t = sum(c.values())
        print(f"{ct:<{w}} {c['vanilla']:>9} {c['keyword-complete']:>9}"
              f" {c['implemented']:>9} {c['escape-hatch']:>10}"
              f" {c['keyword-deferred']:>8} {c['text-bearing']:>10} {t:>7}")
    print("-" * len(header))
    print(f"{'TOTAL':<{w}} {totals['vanilla']:>9} {totals['keyword-complete']:>9}"
          f" {totals['implemented']:>9} {totals['escape-hatch']:>10}"
          f" {totals['keyword-deferred']:>8} {totals['text-bearing']:>10} {grand_total:>7}")

    pct = lambda n: f"{100 * n / grand_total:.1f}%"
    playable = totals["vanilla"] + totals["keyword-complete"] + totals["implemented"]
    print(f"\nPlayable (vanilla + kw-complete + implemented): {playable} ({pct(playable)})")
    print(f"Escape-hatch (simplified):                      {totals['escape-hatch']} ({pct(totals['escape-hatch'])})")
    print(f"Gaps (text-bearing, unimplemented):             {totals['text-bearing']} ({pct(totals['text-bearing'])})")
    print(f"Keyword-deferred:                               {totals['keyword-deferred']} ({pct(totals['keyword-deferred'])})")

    # ── Markdown report ───────────────────────────────────────────────────────
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Coverage Report\n",
        f"Total cards in DB: **{len(cards)}** | Registered in ability registry: **{len(registered)}**\n",
        "## Summary by card type\n",
        "| Type | Vanilla | Kw-Complete | Implemented | Escape-Hatch | Kw-Deferred | Text-Bearing | Total |",
        "|------|--------:|------------:|------------:|-------------:|------------:|-------------:|------:|",
    ]
    for ct in sorted(type_counts.keys()):
        c = type_counts[ct]
        t = sum(c.values())
        lines.append(
            f"| {ct} | {c['vanilla']} | {c['keyword-complete']}"
            f" | {c['implemented']} | {c['escape-hatch']}"
            f" | {c['keyword-deferred']} | {c['text-bearing']} | {t} |"
        )
    total_playable = totals["vanilla"] + totals["keyword-complete"] + totals["implemented"]
    lines += [
        f"| **TOTAL** | **{totals['vanilla']}** | **{totals['keyword-complete']}**"
        f" | **{totals['implemented']}** | **{totals['escape-hatch']}**"
        f" | **{totals['keyword-deferred']}** | **{totals['text-bearing']}** | **{grand_total}** |",
        "",
        "## Classification definitions",
        "- **vanilla**: no keywords, no ability text — Phase 1 handles fully",
        "- **keyword-complete**: only Phase 2 keywords (Grit, Raid, Sentinel, etc.) — Phase 2 handles fully",
        "- **implemented**: registered in the ability registry with declarative or custom logic",
        "- **escape-hatch**: registered with `escape_hatch=True` — simplified or stub implementation",
        "- **keyword-deferred**: has an unimplemented Phase 3 keyword (Support)",
        "- **text-bearing**: has ability text but NOT yet registered — implementation gap",
        "",
        f"**Playable** (vanilla + kw-complete + implemented): {total_playable} ({pct(total_playable)})",
        "",
        "## Phase 2 keyword counts",
        "| Keyword | Cards |",
        "|---------|------:|",
    ]
    kw_counts: Counter[str] = Counter()
    for c in cards:
        for kw in c.keywords & PHASE2_KEYWORDS:
            kw_counts[kw] += 1
    for kw, cnt in sorted(kw_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {kw} | {cnt} |")

    lines += [
        "",
        "## Deferred keyword counts",
        "| Keyword | Cards |",
        "|---------|------:|",
    ]
    kw3_counts: Counter[str] = Counter()
    for c in cards:
        for kw in c.keywords & PHASE3_KEYWORDS:
            kw3_counts[kw] += 1
    for kw, cnt in sorted(kw3_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {kw} | {cnt} |")

    lines += [
        "",
        "## Escape-hatch cards (simplified implementations)",
        "| Set | Number | Name |",
        "|-----|-------:|------|",
    ]
    for c in sorted(cards, key=lambda c: (c.set_code, c.card_number)):
        key = (c.set_code, c.card_number)
        if key in escape_hatch:
            lines.append(f"| {c.set_code} | {c.card_number} | {c.name} |")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
