"""
Encoding planner (Phase 7, Part A).

Given an unshipped deck (a SWUDB-JSON fixture or a set code), this finds every
card that is not yet playable, classifies and clusters the gaps into small,
coherent *encoding groups*, orders them by dependency, and emits a per-deck
dashboard (`MANIFEST.md` + `manifest.json`) and a self-contained spec file per
group under `encoding/<deck_slug>/`.

It is **deterministic and offline by design** — it calls no LLM and no network.
Same input ⇒ same groups, every run.  Re-running after some groups are encoded
updates progress and never clobbers a group spec whose cards are all playable.

Three group *kinds* are produced distinctly:

  * keyword   — cards blocked *only* by a deferred keyword (Smuggle, Bounty, …).
                One group per deferred keyword; the task is to implement the
                keyword engine-side once, unlocking every listed card.
  * ability   — text-bearing cards clustered by trigger archetype + effect
                family, capped at ~7 cards per group.
  * primitive — surfaced as a flag *on* a group when a cluster needs a framework
                primitive that does not yet exist (see _NEW_CAPABILITIES).

Usage::

    python scripts/plan_encoding.py --deck tests/fixtures/shd_han_solo.json
    python scripts/plan_encoding.py --set SHD
    python scripts/plan_encoding.py --deck <path> --slug shd-han-solo
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Reuse the registry-aware classification from the audit script (same dir).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_coverage as audit  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "swu.db"
ENCODING_DIR = ROOT / "encoding"

# Group size cap for ability groups — keeps an encoding session focused and in
# context (spec: ~6–8 cards).
ABILITY_GROUP_CAP = 7


# ── Card detail ────────────────────────────────────────────────────────────────

@dataclass
class CardDetail:
    set_code: str
    card_number: str
    name: str
    card_type: str
    cost: int | None
    power: int | None
    hp: int | None
    text: str
    deploy_box: str
    epic_action: str
    keywords: list[str]
    traits: list[str]
    aspects: list[str]
    label: str = ""               # classification label
    raw_json: str = ""

    @property
    def cid(self) -> str:
        return f"{self.set_code}_{self.card_number}"

    @property
    def num_sort(self) -> tuple:
        n = self.card_number
        return (int(n) if n.isdigit() else 1_000_000, n)

    @property
    def full_text(self) -> str:
        """All rules text, newlines preserved, non-breaking spaces normalised."""
        parts = [self.text, self.deploy_box, self.epic_action]
        joined = "\n".join(p for p in parts if p)
        return joined.replace("\xa0", " ").replace("’", "'")


def _norm(t: str | None) -> str:
    return (t or "").replace("\xa0", " ").replace("’", "'")


# ── Classification ─────────────────────────────────────────────────────────────
#
# The planner uses a STRONGER gap detector than audit_coverage._has_ability_text
# (which only matches trigger words and so mislabels plain-effect events like
# "Deal 2 damage to a unit or base" as vanilla — the exact flaw documented in
# tests/test_deck_coverage.py).  We reuse that test's authoritative rule:
# strip reminder parentheticals + the card's OWN keyword names; if any prose word
# remains, the card has functional text and needs an ability registration.

_REMINDER_RE = re.compile(r"\([^)]*\)")
_WORD_RE = re.compile(r"[A-Za-z']+")


def has_functional_text(card: "CardDetail") -> bool:
    # Delegate to the canonical detector in audit_coverage (single source of
    # truth): strip reminder parentheticals + keyword cost brackets, subtract the
    # card's own keyword names, and flag any remaining prose word.
    return audit.has_functional_text(card.full_text, card.keywords)


def classify_card(card: "CardDetail", registered: set, escape_hatch: set) -> str:
    """Registry-aware classification with strong functional-text detection."""
    key = (card.set_code, card.card_number)
    if key in registered:
        return "escape-hatch" if key in escape_hatch else "implemented"
    kws = set(card.keywords)
    if (kws & audit.PHASE3_KEYWORDS) or (kws - audit.ALL_KNOWN_KEYWORDS):
        return "keyword-deferred"
    if has_functional_text(card):
        return "text-bearing"
    if kws & audit.PHASE2_KEYWORDS:
        return "keyword-complete"
    return "vanilla"


def load_details(db_path: str, ids: list[tuple[str, str]]) -> dict[tuple[str, str], CardDetail]:
    """Load full DB detail for the given (set_code, card_number) keys."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    out: dict[tuple[str, str], CardDetail] = {}
    for sc, cn in ids:
        # (set, number) is not unique — a Leader and a Token share low numbers.
        # Decklists reference the real card, so prefer the non-token row.
        rows = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?", (sc, cn)
        ).fetchall()
        if not rows:
            continue
        row = next((r for r in rows if r["type"] not in audit.TOKEN_TYPES), rows[0])
        cid = row["id"]
        kws = [r["name"] for r in con.execute(
            "SELECT name FROM card_keywords WHERE card_id=?", (cid,))]
        traits = [r["name"] for r in con.execute(
            "SELECT name FROM card_traits WHERE card_id=?", (cid,))]
        aspects = [r["name"] for r in con.execute(
            "SELECT name FROM card_aspects WHERE card_id=?", (cid,))]
        out[(sc, cn)] = CardDetail(
            set_code=row["set_code"], card_number=row["card_number"],
            name=row["name"], card_type=row["type"], cost=row["cost"],
            power=row["power"], hp=row["hp"],
            text=_norm(row["text"]), deploy_box=_norm(row["deploy_box"]),
            epic_action=_norm(row["epic_action"]),
            keywords=sorted(kws), traits=sorted(traits), aspects=sorted(aspects),
            raw_json=row["raw_json"] or "",
        )
    con.close()
    return out


# ── Input resolution ───────────────────────────────────────────────────────────

def resolve_input(deck: str | None, set_code: str | None, db_path: str
                  ) -> tuple[str, list[tuple[str, str, int]]]:
    """Return (deck_slug, entries) where entries = [(set_code, card_number, count)].

    Accepts a SWUDB-JSON fixture path (``deck``) or a whole set code (``set_code``).
    """
    if deck:
        path = Path(deck)
        if not path.exists():
            sys.exit(f"Deck file not found: {deck}")
        data = json.loads(path.read_text(encoding="utf-8"))
        entries: list[tuple[str, str, int]] = []

        def _add(entry: dict) -> None:
            cid = entry.get("id") or entry.get("card_id", "")
            count = int(entry.get("count", 1))
            if "_" in cid:
                sc, cn = cid.split("_", 1)
                cn = str(int(cn)) if cn.isdigit() else cn
                entries.append((sc, cn, count))

        if "leader" in data:
            _add(data["leader"] if isinstance(data["leader"], dict) else {"id": data["leader"]})
        if "base" in data:
            _add(data["base"] if isinstance(data["base"], dict) else {"id": data["base"]})
        for e in data.get("deck", []):
            _add(e)
        slug = path.stem.replace("_", "-").lower()
        return slug, entries

    if set_code:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT card_number FROM cards WHERE set_code=? AND type IN "
            "('Leader','Base','Unit','Event','Upgrade')", (set_code,)
        ).fetchall()
        con.close()
        entries = [(set_code, r["card_number"], 1) for r in rows]
        return f"{set_code.lower()}-set", entries

    sys.exit("Provide --deck <path> or --set <CODE>")


# ── Feature detection (deterministic, rule-based) ──────────────────────────────

# Trigger archetypes, checked in priority order; first match wins.
_ARCHETYPES: list[tuple[str, re.Pattern]] = [
    ("when_played",   re.compile(r"\bWhen Played\b|\bWhen this unit enters play\b", re.I)),
    ("when_defeated", re.compile(r"\bWhen Defeated\b", re.I)),
    ("on_attack",     re.compile(r"\bOn Attack\b", re.I)),
    ("when_attacked", re.compile(r"\bWhen Attacked\b", re.I)),
    ("on_defeats",    re.compile(r"\bdefeats? a unit\b", re.I)),
    ("epic_action",   re.compile(r"\bEpic Action\b", re.I)),
    ("activated",     re.compile(r"\bAction\s*[:\[]", re.I)),
    ("constant",      re.compile(r"\bConstant\b|\bWhile\b|\bgains?\b", re.I)),
    ("phase_boundary", re.compile(r"\bat the start of\b|\bat the end of\b|\beach (action|regroup) phase\b", re.I)),
]

# Effect families, all that match are recorded; the first is the "primary".
_EFFECT_FAMILIES: list[tuple[str, re.Pattern]] = [
    ("damage",      re.compile(r"\bdeal\b.*\bdamage\b", re.I)),
    ("heal",        re.compile(r"\bheal\b", re.I)),
    ("draw",        re.compile(r"\bdraw\b", re.I)),
    ("discard",     re.compile(r"\bdiscard\b", re.I)),
    ("return_hand", re.compile(r"\breturn\b.*\bhand\b|to (its|their) owner'?s hand", re.I)),
    ("defeat",      re.compile(r"\bdefeat\b", re.I)),
    ("token",       re.compile(r"\b(Shield|Experience)\b.*token|token to", re.I)),
    ("ready_exhaust", re.compile(r"\bready\b|\bexhaust\b", re.I)),
    ("stat_buff",   re.compile(r"[+\-]\d+/[+\-]?\d+|gets \+", re.I)),
    ("keyword_grant", re.compile(r"\bgains?\b.*\b(Sentinel|Raid|Overwhelm|Grit|Ambush|Restore|Saboteur|Shielded|Sentinel)\b", re.I)),
    ("ramp",        re.compile(r"\bresource\b", re.I)),
    ("search",      re.compile(r"search your deck|look at the top", re.I)),
    ("attack_grant", re.compile(r"\battack with\b", re.I)),
]

# Capability hints: (label, regex, status).  status "existing" = a primitive or
# Phase-3 seam already covers it; "new" = no primitive yet → surfaces as a
# new-primitive flag for a dedicated framework session.
_CAPABILITIES: list[tuple[str, re.Pattern, str]] = [
    ("DealDamage",        re.compile(r"\bdeal\b.*\bdamage\b", re.I), "existing"),
    ("Heal",              re.compile(r"\bheal\b", re.I), "existing"),
    ("DrawCards",         re.compile(r"\bdraw\b", re.I), "existing"),
    ("DiscardFromHand",   re.compile(r"\bdiscard\b", re.I), "existing"),
    ("ReturnToHand",      re.compile(r"\breturn\b.*\bhand\b|owner'?s hand", re.I), "existing"),
    ("DefeatUnit/Upgrade", re.compile(r"\bdefeat (a|an|the|target|up to)\b", re.I), "existing"),
    ("GiveToken",         re.compile(r"\b(Shield|Experience)\b", re.I), "existing"),
    ("ModifyStats/StatBonus", re.compile(r"[+\-]\d+/[+\-]?\d+", re.I), "existing"),
    ("GrantKeyword",      re.compile(r"\bgains? (Sentinel|Raid|Overwhelm|Grit|Ambush|Restore|Saboteur|Shielded)\b", re.I), "existing"),
    ("ExhaustCard/ReadyCard", re.compile(r"\b(exhaust|ready) (a|an|the|another|target)\b", re.I), "existing"),
    ("push_play_from_hand", re.compile(r"play (a|an|the) .*\bfrom your hand\b", re.I), "existing"),
    ("CostReduction",     re.compile(r"costs? \d+ resource", re.I), "existing"),
    ("push_modal",        re.compile(r"\bchoose one\b", re.I), "existing"),
    ("push_say_no",       re.compile(r"\bunless\b", re.I), "existing"),
    ("deck_search",       re.compile(r"search your deck|look at the top \d+", re.I), "existing"),
    ("push_granted_attack", re.compile(r"\battack with\b", re.I), "existing"),
    # Disclose (SEC): "You may disclose <aspects> …" — the disclose gate is
    # implemented (actions.push_disclose, keystone Karis Nemik SEC_148); a new
    # disclose card just adds a small payoff arm to _apply_disclose_payoff.
    ("disclose",          re.compile(r"\bdisclose\b", re.I), "existing"),
    # Capture is IMPLEMENTED (CaptureUnit / actions._apply_capture; the
    # Mandalorian's Rifle SHD_251 + SEC precedent) — reuse, not an escalation.
    ("capture",           re.compile(r"\bcaptures?\b", re.I), "existing"),
    # Create-token-unit is IMPLEMENTED (actions._create_token_units; Battle Droid
    # TWI_1 / Clone Trooper TWI_2, and the Spy token SEC_1) — reuse.
    ("create-token-unit", re.compile(r"create (a|an|\d).*token", re.I), "existing"),
    # ── Previously-new primitives, now all landed (Phase-7 deck sweep). Kept as
    #    detectors so specs still name the relevant seam, but classified "existing"
    #    so they cluster into ordinary ability groups, NOT escalation groups. ──
    # control-change: actions.change_control (shd-han-solo:02, Stolen Landspeeder SHD_161).
    ("control-change",    re.compile(r"takes? control of", re.I), "existing"),
    # opponent_chooses_target two-stage decision (shd-han-solo:10, Grey Squadron Y-Wing SHD_246).
    ("opponent-chooses-target", re.compile(r"an opponent chooses", re.I), "existing"),
    # GrantSmuggleToResources / grant-keyword-to-resources marker (smuggle keyword, Tech).
    ("grant-keyword-to-resources", re.compile(r"resources?\b.*\bgains?\b|gains? Smuggle", re.I), "existing"),
    # sacrifice_resource two-stage decision (shd-han-solo:07, Wrecker SHD_154).
    ("sacrifice-resource-cost", re.compile(r"defeat (a|one) (friendly )?resource", re.I), "existing"),
    # Repeated modal / distribute decision (modal decision seam SOR_189; distribute_damage seam).
    ("repeated-modal-per-X", re.compile(r"for each .* (discarded|defeated).*choose", re.I | re.S), "existing"),
    # scaling-magnitude via DealDamageEqualTo count sources (ahsoka-tano:06).
    ("scaling-magnitude", re.compile(r"equal to the number of", re.I), "existing"),
    # Leader trigger "When you reveal or discard 1 or more cards from your hand":
    # WhenYouRevealOrDiscard observer trigger landed (padme-amidala:05).
    ("reveal-or-discard-trigger",
     re.compile(r"reveal or discard \d+ or more cards", re.I), "existing"),
    # Force token (LOF): per-player marker — has_force_token / CreateForceToken /
    # UseForce / CONTROLLER_HAS_FORCE_TOKEN + use_force decision (qui-gon-jinn:06).
    ("force-token",       re.compile(r"use the Force|the Force is with you", re.I), "existing"),
    # Compound play-from-hand that ALSO acts on the played card (Han Solo SHD_13):
    # play_from_hand act-on-result extension landed in the han-solo sweep.
    ("play-from-hand-act-on-result",
     re.compile(r"from your hand.{0,90}(deal \d+ damage to it|damage to it|it gets)", re.I | re.S), "existing"),
    # Granted attack with a RESTRICTED attacker: push_granted_attack attacker_predicates
    # (Desperate Attack SHD_179).
    ("granted-attack-restricted-attacker",
     re.compile(r"attack with a (damaged|exhausted|ready) ", re.I), "existing"),
]

_CAPABILITIES_BY_LABEL = {label: pat for label, pat, _ in _CAPABILITIES}


@dataclass
class Features:
    archetype: str
    effect_families: list[str]
    capabilities: list[str]      # existing primitive/seam names needed
    new_primitives: list[str]    # missing primitives (flagged)


_BRACKET_RE = re.compile(r"\[[^\]]*\]")  # smuggle/bounty cost notation


def _feature_text(card: CardDetail) -> str:
    """Card text cleaned for feature detection: reminder parentheticals and
    cost brackets removed so e.g. 'Smuggle [3 resources]' / its reminder don't
    spuriously match the 'resource'/'ramp' patterns."""
    txt = _REMINDER_RE.sub("", card.full_text)
    txt = _BRACKET_RE.sub("", txt)
    return txt


def detect_features(card: CardDetail) -> Features:
    text = _feature_text(card)
    archetype = "static"
    if card.card_type == "Event":
        archetype = "event"
    for name, pat in _ARCHETYPES:
        if pat.search(text):
            archetype = name
            break
    else:
        if card.card_type == "Event":
            archetype = "event"

    families = [name for name, pat in _EFFECT_FAMILIES if pat.search(text)]
    existing: list[str] = []
    new: list[str] = []
    for label, pat, status in _CAPABILITIES:
        if pat.search(text):
            (new if status == "new" else existing).append(label)
    # The Force token can appear as an ability COST inside [...] brackets (e.g.
    # Qui-Gon Jinn's "Action [Exhaust, use the Force]: …"), which _feature_text
    # strips before detection.  Re-check the force-token phrases against the RAW
    # full text so a bracketed Force spend is still recognised.  The Force engine
    # is implemented (qui-gon-jinn:06), so it's an EXISTING capability — reuse it,
    # not an escalation.  (A specific card that needs more than the existing Force
    # primitive gets flagged at encode time, not here.)
    _FORCE_RE = _CAPABILITIES_BY_LABEL["force-token"]
    if "force-token" not in existing and _FORCE_RE.search(card.full_text):
        existing.insert(0, "force-token")
    return Features(archetype=archetype, effect_families=families,
                    capabilities=existing, new_primitives=new)


# ── Grouping ───────────────────────────────────────────────────────────────────

@dataclass
class Group:
    gid: str                       # e.g. "shd-han-solo:01"
    seq: int                       # numeric order (1-based)
    kind: str                      # "keyword" | "ability"
    theme: str                     # human label, also the file slug
    keyword: str = ""              # for keyword groups
    cards: list[CardDetail] = field(default_factory=list)
    new_primitives: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # group ids

    @property
    def file_slug(self) -> str:
        safe = re.sub(r"[^a-z0-9]+", "_", self.theme.lower()).strip("_")
        return f"group_{self.seq:02d}_{safe}"


# Mechanical buckets: related effect families grouped so encoding sessions stay
# coherent (cards needing the same primitives land together) without fragmenting
# into singletons.  Order here is also the simple→bespoke encoding order.
_BUCKETS: list[tuple[str, str, tuple[str, ...]]] = [
    # (bucket key, human theme, member effect families) — order is also the
    # simple→bespoke encoding order.
    ("damage_removal", "Direct damage & removal", ("damage", "defeat")),
    ("card_advantage", "Card advantage & disruption",
     ("draw", "discard", "return_hand", "search")),
    ("combat_tricks", "Combat tricks, buffs & tempo",
     ("attack_grant", "stat_buff", "keyword_grant", "token", "ready_exhaust",
      "ramp", "heal")),
]
_BUCKET_ORDER = {b[0]: i for i, b in enumerate(_BUCKETS)}
_BUCKET_THEME = {b[0]: b[1] for b in _BUCKETS}
_FAMILY_TO_BUCKET = {fam: b[0] for b in _BUCKETS for fam in b[2]}


def _bucket_for(families: list[str]) -> tuple[str, str]:
    """Pick the mechanical bucket for a card from its effect families."""
    for fam in families:
        if fam in _FAMILY_TO_BUCKET:
            key = _FAMILY_TO_BUCKET[fam]
            return key, _BUCKET_THEME[key]
    return "misc", "Miscellaneous abilities"


def build_groups(cards: list[CardDetail], slug: str) -> list[Group]:
    """Cluster gap cards into ordered keyword + ability + escalation groups.

    Order: keyword groups first (unblock the most), then simple ability groups
    (bucketed by mechanical family, simplest first), then a clearly-flagged
    escalation group for cards that need a framework primitive that does not yet
    exist (these must NOT be jammed into a card batch — see the standing prompt).
    Deterministic: same input ⇒ same groups, same ids.
    """
    keyword_deferred = [c for c in cards if c.label == "keyword-deferred"]
    text_bearing = [c for c in cards if c.label == "text-bearing"]
    feats = {c.cid: detect_features(c) for c in cards}

    # ── Keyword groups: one per deferred keyword present ──
    kw_to_cards: dict[str, list[CardDetail]] = {}
    for c in keyword_deferred:
        for kw in c.keywords:
            if kw in audit.PHASE3_KEYWORDS:
                kw_to_cards.setdefault(kw, []).append(c)
    kw_order = sorted(kw_to_cards.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    # ── Ability cards: split simple vs needs-new-primitive ──
    simple = [c for c in text_bearing if not feats[c.cid].new_primitives]
    escalations = [c for c in text_bearing if feats[c.cid].new_primitives]

    # Simple cards → mechanical buckets, capped & split deterministically.
    bucketed: dict[str, list[CardDetail]] = {}
    for c in sorted(simple, key=lambda x: x.num_sort):
        key, _ = _bucket_for(feats[c.cid].effect_families)
        bucketed.setdefault(key, []).append(c)

    ability_chunks: list[tuple[str, list[CardDetail]]] = []
    for key in sorted(bucketed, key=lambda k: (_BUCKET_ORDER.get(k, 99), k)):
        members = sorted(bucketed[key], key=lambda x: x.num_sort)
        for i in range(0, len(members), ABILITY_GROUP_CAP):
            ability_chunks.append((key, members[i:i + ABILITY_GROUP_CAP]))

    # ── Assemble Group objects with stable sequential ids ──
    groups: list[Group] = []
    seq = 0
    kw_gid_by_keyword: dict[str, str] = {}

    def _keyword_residual_new_primitives(members: list[CardDetail], kw: str) -> list[str]:
        nps: list[str] = []
        for c in members:
            for np in feats[c.cid].new_primitives:
                if np not in nps:
                    nps.append(np)
        return nps

    for kw, members in kw_order:
        seq += 1
        members.sort(key=lambda x: x.num_sort)
        gid = f"{slug}:{seq:02d}"
        kw_gid_by_keyword[kw] = gid
        groups.append(Group(
            gid=gid, seq=seq, kind="keyword", theme=f"{kw} keyword",
            keyword=kw, cards=members,
            new_primitives=_keyword_residual_new_primitives(members, kw),
        ))

    def _deps(members: list[CardDetail]) -> list[str]:
        deps: list[str] = []
        for c in members:
            for kw in c.keywords:
                g = kw_gid_by_keyword.get(kw)
                if g and g not in deps:
                    deps.append(g)
        return deps

    for key, members in ability_chunks:
        seq += 1
        groups.append(Group(
            gid=f"{slug}:{seq:02d}", seq=seq, kind="ability",
            theme=_BUCKET_THEME.get(key, "Miscellaneous abilities"),
            cards=members, new_primitives=[], depends_on=_deps(members),
        ))

    # Escalation groups: cards needing a not-yet-existing primitive.  ONE GROUP
    # PER NEW PRIMITIVE (so each group id maps to exactly one framework session
    # with a single clear deliverable), ordered last and split at the cap.
    esc_by_prim: dict[str, list[CardDetail]] = {}
    for c in sorted(escalations, key=lambda x: x.num_sort):
        prim = feats[c.cid].new_primitives[0]   # primary new primitive
        esc_by_prim.setdefault(prim, []).append(c)
    for prim in sorted(esc_by_prim, key=lambda p: (esc_by_prim[p][0].num_sort, p)):
        members_all = esc_by_prim[prim]
        for i in range(0, len(members_all), ABILITY_GROUP_CAP):
            members = members_all[i:i + ABILITY_GROUP_CAP]
            seq += 1
            nps: list[str] = []
            for c in members:
                for np in feats[c.cid].new_primitives:
                    if np not in nps:
                        nps.append(np)
            groups.append(Group(
                gid=f"{slug}:{seq:02d}", seq=seq, kind="ability",
                theme=f"New primitive: {prim}",
                cards=members, new_primitives=nps, depends_on=_deps(members),
            ))
    return groups


# ── Mechanical analysis text (per card, for the group spec) ────────────────────

def analyse_card(card: CardDetail) -> dict:
    f = detect_features(card)
    return {
        "archetype": f.archetype,
        "effect_families": f.effect_families,
        "existing_primitives": f.capabilities,
        "new_primitives": f.new_primitives,
    }


# ── Artifact emission ──────────────────────────────────────────────────────────

def _card_table_row(c: CardDetail) -> str:
    stats = ""
    if c.power is not None or c.hp is not None:
        stats = f"{c.power}/{c.hp}"
    cost = "" if c.cost is None else str(c.cost)
    return f"| {c.cid} | {c.name} | {c.card_type} | {cost} | {stats} | {', '.join(c.keywords)} |"


def write_group_spec(group: Group, out_dir: Path) -> Path:
    path = out_dir / f"{group.file_slug}.md"
    L: list[str] = []
    L.append(f"# {group.gid} — {group.theme}")
    L.append("")
    L.append(f"- **Group id (paste this):** `{group.gid}`")
    L.append(f"- **Kind:** {group.kind}")
    L.append(f"- **Cards:** {len(group.cards)}")
    if group.depends_on:
        L.append(f"- **Depends on:** {', '.join(group.depends_on)} (encode those first)")
    if group.new_primitives:
        L.append(f"- **⚠ New primitives suspected:** {', '.join(group.new_primitives)} "
                 f"— see escalation rule; do NOT jam a core-resolution change into a card batch.")
    L.append("")

    if group.kind == "keyword":
        L.append(f"## Keyword group: **{group.keyword}**")
        L.append("")
        L.append(f"Implement the **{group.keyword}** keyword engine-side once "
                 f"(Phase 2 pattern: keyword query layer / effective-stats / "
                 f"decision-stack as needed), with synthetic-card framework tests "
                 f"first. Then confirm every card below becomes playable and add "
                 f"`{group.keyword}` to the keyword list in `docs/engine_seams.md`.")
        L.append("")
        L.append("Note: a card may have rules text *beyond* the keyword. Where "
                 "flagged 'residual text' below, the keyword unblocks the card but "
                 "its ability text still needs a separate ability registration "
                 "(re-run the planner after the keyword lands — it will recluster "
                 "the residual text into an ability group).")
        L.append("")

    L.append("## Cards")
    L.append("")
    L.append("| id | name | type | cost | P/HP | keywords |")
    L.append("|----|------|------|-----:|------|----------|")
    for c in group.cards:
        L.append(_card_table_row(c))
    L.append("")

    L.append("## Per-card analysis & acceptance criteria")
    L.append("")
    for c in group.cards:
        a = analyse_card(c)
        L.append(f"### {c.cid} — {c.name}")
        L.append("")
        L.append(f"**Type/Stats:** {c.card_type}"
                 + (f", cost {c.cost}" if c.cost is not None else "")
                 + (f", {c.power}/{c.hp}" if c.power is not None else "")
                 + (f"  |  Traits: {', '.join(c.traits)}" if c.traits else ""))
        L.append("")
        L.append("**Rules text:**")
        L.append("")
        for line in (c.full_text or "(no text)").splitlines():
            L.append(f"> {line}")
        L.append("")
        if group.kind == "keyword":
            residual = _residual_text(c, group.keyword)
            if residual:
                L.append(f"**Residual text (needs separate ability after keyword):** {residual}")
                L.append("")
        L.append(f"**Mechanical analysis:** trigger archetype `{a['archetype']}`; "
                 f"effect families {a['effect_families'] or ['—']}.")
        L.append("")
        if a["existing_primitives"]:
            L.append(f"**Existing primitives that should suffice:** "
                     f"{', '.join(a['existing_primitives'])}.")
            L.append("")
        if a["new_primitives"]:
            L.append(f"**⚠ Suspected NEW primitive:** {', '.join(a['new_primitives'])}. "
                     f"If implementing it touches core resolution / the trigger / "
                     f"decision machinery, STOP and flag for a dedicated framework "
                     f"session.")
            L.append("")
        L.append("**Acceptance criteria:** one focused test named for the card "
                 "asserting the behaviour through public engine interfaces "
                 "(`legal_actions`/`apply`), and the card classifies as "
                 "`implemented` (or better) in the deck audit.")
        L.append("")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


_KEYWORD_REMINDER_RE = re.compile(r"\(If this card is a resource.*?\)", re.I | re.S)


def _residual_text(card: CardDetail, keyword: str) -> str:
    """Best-effort: the card's text with the keyword's own line/reminder stripped."""
    txt = card.full_text
    lines = []
    for ln in txt.splitlines():
        stripped = ln.strip()
        if not stripped:
            continue
        # Drop the keyword declaration line and its reminder.
        if stripped.lower().startswith(keyword.lower()):
            continue
        if _KEYWORD_REMINDER_RE.search(stripped):
            stripped = _KEYWORD_REMINDER_RE.sub("", stripped).strip()
            if not stripped:
                continue
        if keyword.lower() in stripped.lower() and "when played using" not in stripped.lower() \
                and "gains" not in stripped.lower():
            # a bare "Smuggle [..]" cost line
            continue
        lines.append(stripped)
    return " ".join(lines).strip()


def write_manifest(slug: str, groups: list[Group], progress: dict, out_dir: Path,
                   total_deck: int, playable_deck: int, source: dict | None = None) -> None:
    # manifest.json (machine-readable)
    mj = {
        "deck_slug": slug,
        "source": source or {},
        "total_deck_cards": total_deck,
        "playable_deck_cards": playable_deck,
        "groups": [
            {
                "gid": g.gid, "seq": g.seq, "kind": g.kind, "theme": g.theme,
                "keyword": g.keyword, "file": f"{g.file_slug}.md",
                "depends_on": g.depends_on, "new_primitives": g.new_primitives,
                "cards": [c.cid for c in g.cards],
                "done": progress[g.gid]["done"], "total": progress[g.gid]["total"],
            }
            for g in groups
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(mj, indent=2) + "\n", encoding="utf-8")

    # MANIFEST.md (dashboard)
    done_groups = sum(1 for g in groups if progress[g.gid]["done"] == progress[g.gid]["total"]
                      and progress[g.gid]["total"] > 0)
    L: list[str] = []
    L.append(f"# Encoding manifest — `{slug}`")
    L.append("")
    L.append(f"Deck readiness: **{playable_deck}/{total_deck}** cards playable. "
             f"Encoding groups: **{done_groups}/{len(groups)}** complete.")
    L.append("")
    L.append("Encode one group per session: paste its **group id** into "
             "`docs/encode_group_prompt.md`, review, then run "
             "`python scripts/verify_encoding.py " + slug + " --group NN`.")
    L.append("")
    L.append("## Groups (in dependency order)")
    L.append("")
    L.append("| # | group id | kind | theme | cards | progress | new primitives | depends on |")
    L.append("|--:|----------|------|-------|------:|----------|----------------|------------|")
    for g in groups:
        p = progress[g.gid]
        bar = f"{p['done']}/{p['total']}"
        if p["total"] and p["done"] == p["total"]:
            bar += " ✅"
        np = ", ".join(g.new_primitives) if g.new_primitives else "—"
        deps = ", ".join(g.depends_on) if g.depends_on else "—"
        L.append(f"| {g.seq} | `{g.gid}` | {g.kind} | {g.theme} | "
                 f"{len(g.cards)} | {bar} | {np} | {deps} |")
    L.append("")
    L.append("## Copy-paste entries")
    L.append("")
    L.append("Paste the **id** line into the standing prompt. The card names are "
             "shown only so you know what you're submitting.")
    L.append("")
    for g in groups:
        p = progress[g.gid]
        status = "✅ done" if (p["total"] and p["done"] == p["total"]) else f"{p['done']}/{p['total']}"
        L.append(f"### `{g.gid}` — {g.theme} ({status})")
        L.append("```")
        L.append(g.gid)
        names = ", ".join(f"{c.name} ({c.cid})" for c in g.cards)
        L.append(f"# {names}")
        L.append("```")
        L.append("")
    (out_dir / "MANIFEST.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ── Orchestration ──────────────────────────────────────────────────────────────

def plan(deck: str | None, set_code: str | None, db_path: str,
         slug_override: str | None = None) -> tuple[str, list[Group], dict]:
    slug, entries = resolve_input(deck, set_code, db_path)
    if slug_override:
        slug = slug_override

    registered, escape_hatch = audit._load_registry()

    # Unique keys, classified.
    keys = sorted(set((sc, cn) for sc, cn, _ in entries),
                  key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else 1_000_000, k[1]))
    details = load_details(db_path, keys)

    gaps: list[CardDetail] = []
    total = sum(cnt for _, _, cnt in entries)
    playable = 0
    counted: dict[tuple[str, str], int] = {}
    for sc, cn, cnt in entries:
        counted[(sc, cn)] = counted.get((sc, cn), 0) + cnt
    for key in keys:
        d = details.get(key)
        label = classify_card(d, registered, escape_hatch) if d else "not-in-db"
        cnt = counted[key]
        if audit.is_playable(label):
            playable += cnt
            continue
        if d is None:
            continue
        d.label = label
        if label in ("text-bearing", "keyword-deferred"):
            gaps.append(d)

    groups = build_groups(gaps, slug)

    # Progress: a group card is "done" if it's currently playable (it would have
    # dropped out of `gaps`).  Recompute against persisted membership if a prior
    # manifest exists so completed group specs are preserved across re-runs.
    out_dir = ENCODING_DIR / slug
    prior = _load_prior_manifest(out_dir)
    if prior:
        groups = _reconcile_with_prior(groups, prior, slug, db_path, registered, escape_hatch, details)

    progress = {}
    for g in groups:
        done = 0
        for c in g.cards:
            lbl = classify_card(c, registered, escape_hatch)
            if audit.is_playable(lbl):
                done += 1
        progress[g.gid] = {"done": done, "total": len(g.cards)}
    source = {"deck": deck, "set_code": set_code}
    return slug, groups, {"progress": progress, "total_deck": total,
                          "playable_deck": playable, "source": source}


def _load_prior_manifest(out_dir: Path) -> dict | None:
    p = out_dir / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _reconcile_with_prior(groups, prior, slug, db_path, registered, escape_hatch, details):
    """Keep stable ids/themes from a prior manifest; append genuinely-new groups.

    Persisted groups keep their id and membership (so completed specs and paste
    ids stay valid); any gap card not in a persisted group forms a new appended
    group using the freshly-computed clusters.
    """
    prior_groups = prior.get("groups", [])
    prior_cids = {cid for pg in prior_groups for cid in pg.get("cards", [])}
    out: list[Group] = []
    # Re-materialise prior groups (membership frozen from the manifest).
    for pg in prior_groups:
        cards = [details[(cid.split("_", 1)[0], cid.split("_", 1)[1])]
                 for cid in pg.get("cards", [])
                 if (cid.split("_", 1)[0], cid.split("_", 1)[1]) in details]
        out.append(Group(
            gid=pg["gid"], seq=pg["seq"], kind=pg["kind"], theme=pg["theme"],
            keyword=pg.get("keyword", ""), cards=cards,
            new_primitives=pg.get("new_primitives", []),
            depends_on=pg.get("depends_on", []),
        ))
    # Append new groups for gap cards not previously tracked.
    max_seq = max((pg["seq"] for pg in prior_groups), default=0)
    for g in groups:
        new_cards = [c for c in g.cards if c.cid not in prior_cids]
        if not new_cards:
            continue  # already fully covered by a prior group
        if len(new_cards) != len(g.cards):
            # Some of this fresh cluster is already tracked by a (frozen) prior
            # group; spin up a new group for just the genuinely-new stragglers
            # rather than dropping them (prior membership stays frozen).
            g.cards = new_cards
        max_seq += 1
        g.seq = max_seq
        g.gid = f"{slug}:{max_seq:02d}"
        out.append(g)
    return out


def emit(slug: str, groups: list[Group], meta: dict) -> Path:
    out_dir = ENCODING_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = meta["progress"]
    for g in groups:
        spec = out_dir / f"{g.file_slug}.md"
        # Re-runnable: never clobber a spec whose cards are all playable.
        if spec.exists() and progress[g.gid]["total"] and \
                progress[g.gid]["done"] == progress[g.gid]["total"]:
            continue
        write_group_spec(g, out_dir)
    write_manifest(slug, groups, progress, out_dir,
                   meta["total_deck"], meta["playable_deck"], meta.get("source"))
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 7 encoding planner")
    ap.add_argument("--deck", default=None, help="SWUDB-JSON decklist fixture path")
    ap.add_argument("--set", dest="set_code", default=None, help="whole set code, e.g. SHD")
    ap.add_argument("--slug", default=None, help="override the deck slug")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    slug, groups, meta = plan(args.deck, args.set_code, args.db, args.slug)
    out_dir = emit(slug, groups, meta)
    p = meta["progress"]
    done_groups = sum(1 for g in groups if p[g.gid]["total"] and p[g.gid]["done"] == p[g.gid]["total"])
    print(f"Planned '{slug}': {meta['playable_deck']}/{meta['total_deck']} cards playable, "
          f"{len(groups)} groups ({done_groups} complete).")
    for g in groups:
        pr = p[g.gid]
        flag = "  [NEW PRIMS]" if g.new_primitives else ""
        line = (f"  {g.gid}  [{g.kind:7}] {g.theme:34} {len(g.cards)} cards  "
                f"({pr['done']}/{pr['total']}){flag}")
        print(line.encode("ascii", "replace").decode("ascii"))
    print(f"\nArtifacts written to {out_dir}")


if __name__ == "__main__":
    main()
