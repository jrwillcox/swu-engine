"""
Printed-keyword sanitisation — corrects an upstream source-data quirk.

The official Strapi card data populates a card's ``keywords`` relation not only
with the keywords the card actually *possesses* (its keyword bar) but, for many
cards, also with keywords the card merely *grants to other units* in its rules
text.  Example — Admiral Piett (SOR 079):

    "Each friendly non-leader unit that costs 6 or more gains Ambush."

The API tags Piett himself with the ``Ambush`` keyword even though Piett's
keyword bar is empty.  Because the engine reads ``card_def.keywords`` to drive
keyword behaviour (e.g. the Ambush enter-play listener lets a unit ready and
attack immediately), an un-sanitised Piett would attack the turn he is played —
the exact bug this module fixes.

The fix removes a printed keyword **K** from a Unit/Leader iff the card's text
*grants K to other units* and **K is not actually possessed by the card itself**.
We deliberately scope this to ``Unit``/``Leader`` cards: those are the cards
whose printed keyword bar drives arena behaviour through ``has_keyword``.
Upgrades and Events carry keywords with different (or inert) semantics, so we
leave them untouched.

Two signals keep this conservative — i.e. it never strips a keyword the card
really has:

1. **Bare-token override.**  If K appears anywhere as a standalone token (a
   keyword-bar entry or reminder mention) — i.e. *not* immediately preceded by
   "gain/gains" — the card genuinely has K and we keep it.  This protects
   multi-keyword cards like Home One ("Restore 2  Each other friendly unit gains
   Restore 1") and Red Three ("Raid 1 ... Each other friendly unit gains Raid").

2. **Grant subject.**  For each "gains K" occurrence we look at the subject of
   the granting clause.  If the nearest subject is *this unit* (a conditional
   self-grant such as First Legion Snowtrooper's "While attacking a damaged
   unit, this unit ... gains Overwhelm") we keep K.  We only strip when the
   nearest subject refers to *other* units ("Each friendly ... unit", "the next
   unit you play", "the attacker", etc.).
"""
from __future__ import annotations

import re
from typing import Iterable

# Canonical printed keywords (DB names).  Mirrors swu.engine.keywords.Keyword
# plus the Phase-3+ keywords that exist in the data but aren't engine-modelled
# yet — sanitisation should still correct their printed-vs-granted confusion.
_KNOWN_KEYWORDS = frozenset({
    "Sentinel", "Overwhelm", "Raid", "Ambush", "Restore", "Saboteur",
    "Shielded", "Grit", "Exploit", "Bounty", "Coordinate", "Hidden",
    "Piloting", "Plot", "Smuggle", "Support",
})

_SANITISED_TYPES = frozenset({"Unit", "Leader"})

# "this unit" / he / she / it — the source card referring to itself.
_SELF_SUBJECT = re.compile(r"\b(this unit|he|she|it)\b", re.IGNORECASE)

# Any phrase referring to a unit that is *not* the source card itself.
_OTHER_SUBJECT = re.compile(
    r"(\bother\b|\banother\b|\beach\b|\bevery\b|\ball\b|\bfriendly\b|\benemy\b"
    r"|the attacker|the defender|the chosen|that unit|the next unit|next unit"
    r"|\ba unit\b|an? [\w-]+ unit|\bunits\b)",
    re.IGNORECASE,
)

_GAINS = re.compile(r"\bgains?\b", re.IGNORECASE)

# "Enemy units LOSE Ambush and Support" — the revoke verb (rule 10).
_LOSES = re.compile(r"\bloses?\b", re.IGNORECASE)


def _normalise(text: str | None) -> str:
    # Non-breaking spaces appear in some DB rows (see CLAUDE.md).
    return (text or "").replace("\xa0", " ")


def _grant_verb_positions(text: str, kw: str) -> list[int]:
    """Start indices of each 'gain(s)' that grants ``kw`` (kw follows shortly)."""
    positions: list[int] = []
    for m in _GAINS.finditer(text):
        tail = text[m.end():m.end() + 45]
        if re.match(r"[^.]*?\b" + re.escape(kw) + r"\b", tail, re.IGNORECASE):
            positions.append(m.start())
    return positions


def _has_bare_mention(text: str, kw: str) -> bool:
    """True if ``kw`` appears as a standalone token (not a 'gains K' grant)."""
    for m in re.finditer(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
        preceding = text[max(0, m.start() - 12):m.start()]
        if not re.search(r"\bgains?\b\s*\W*$", preceding, re.IGNORECASE):
            return True
    return False


def _grants_to_other_unit(text: str, kw: str) -> bool:
    """True if some 'gains K' clause's nearest subject is another unit."""
    for g in _grant_verb_positions(text, kw):
        clause_start = max([text.rfind(c, 0, g) for c in ".:"] + [-1]) + 1
        clause = text[clause_start:g]
        self_pos = max((m.end() for m in _SELF_SUBJECT.finditer(clause)), default=-1)
        other_pos = max((m.end() for m in _OTHER_SUBJECT.finditer(clause)), default=-1)
        if other_pos > self_pos:
            return True
    return False


def _is_spurious(text: str, kw: str) -> bool:
    text = _normalise(text)
    if _has_bare_mention(text, kw):
        return False  # the card genuinely possesses the keyword
    return _grants_to_other_unit(text, kw)


# "with Sentinel", "unit with Sentinel", "a card with Plot" — the keyword names a
# *property of other cards* the ability cares about, not a keyword this card has.
def _reference_mention(text: str, kw: str) -> "re.Match | None":
    return re.search(r"\bwith\s+" + re.escape(kw) + r"\b", text, re.IGNORECASE)


def _is_reference_only(text: str, kw: str) -> bool:
    """True if every textual occurrence of ``kw`` is a "with K" *reference* to
    other cards, so the card does not possess K itself.

    The upstream data tags a card with a keyword it merely *refers to* in its
    rules text — e.g. Refugee of The Path LOF_242 ("give a Shield token to a unit
    with Sentinel") and Kylo Ren's Command Shuttle SEC_32 ("Each friendly ground
    unit with Sentinel gets +0/+2").  Neither has the keyword on its printed bar;
    the API scraped "Sentinel" out of the ability text.  A genuinely-possessed
    keyword shows up as a bare/reminder mention (e.g. Dooku's "Hidden (This unit
    can't be attacked…)"), which is *not* a "with K" reference, so this stays
    conservative — it strips only when the keyword appears **exclusively** as
    "…with K".
    """
    text = _normalise(text)
    occurrences = list(re.finditer(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE))
    if not occurrences:
        return False
    ref_spans = {(m.end() - len(kw), m.end())
                 for m in re.finditer(r"\bwith\s+" + re.escape(kw) + r"\b",
                                      text, re.IGNORECASE)}
    for m in occurrences:
        if (m.start(), m.end()) not in ref_spans:
            return False  # a non-reference occurrence ⇒ the card may possess K
    return True


def _conditional_self_grant_keywords(set_code: str | None,
                                     card_number: str | None) -> frozenset[str]:
    """Keywords this card grants to *itself conditionally* via a registered
    ConstantAbility (e.g. Hunting Nexu SHD_168 "While you control another
    Aggression unit, this unit gains Raid 2"; Protector of the Throne SHD_247
    "While this unit is upgraded, it gains Sentinel").

    The official data tags such cards with the keyword on their printed bar, but
    the keyword is *not* actually possessed — it is conditional, and the ability
    grants it only while the condition holds.  When we have implemented that
    conditional grant as a ConstantAbility (target self, KeywordGrant, with a
    condition), the printed keyword must be stripped so the ability — not an
    always-on printed bar — owns the keyword.  A conditional self-grant with no
    such registered ability (e.g. First Legion Snowtrooper's Overwhelm, still a
    printed-keyword simplification) is left untouched.
    """
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant,
        )
        from swu.abilities.registry import SELF
    except ImportError:
        return frozenset()
    out: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        if not isinstance(spec, ConstantAbility):
            continue
        if spec.condition is None:
            continue
        if getattr(spec.target, "fixed", None) != SELF:
            continue
        for eff in spec.effects:
            if isinstance(eff, KeywordGrant):
                out.add(eff.keyword)
    return frozenset(out)


def _triggered_self_grant_keywords(set_code: str | None,
                                   card_number: str | None) -> frozenset[str]:
    """Keywords this card grants to *itself* via a registered TriggerAbility whose
    effects include a self-targeted ``GrantKeyword`` (e.g. Obi-Wan Kenobi LOF_96
    "When you play a Force unit (including this one): This unit gains Sentinel for
    this phase").

    Like the conditional-self-grant case, the official data tags such a card with
    the keyword on its printed bar even though it is not *possessed* — the card
    only gains it for a phase when the trigger fires.  When we have implemented the
    grant as a TriggerAbility (target self, ``GrantKeyword``), the printed keyword
    must be stripped so the ability — not an always-on printed bar — owns it.
    """
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import (
            get_abilities, TriggerAbility, GrantKeyword, SELF,
        )
    except ImportError:
        return frozenset()
    out: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        if not isinstance(spec, TriggerAbility):
            continue
        for eff in spec.effects:
            if isinstance(eff, GrantKeyword) and getattr(eff.target, "fixed", None) == SELF:
                out.add(eff.keyword)
    return frozenset(out)


def _raid_replaced_by_grit(set_code: str | None,
                           card_number: str | None) -> bool:
    """True if the card has an *unconditional* ``ConstantAbility(SELF,
    KeywordGrant("Grit"))`` registered — meaning its printed "Raid" is actually
    "Raid for each damage" (= Grit), and the ability owns the Grit semantics so
    the raw "Raid" printed bar must be stripped (Fifth Brother SOR_131).

    This is distinct from rule 2 (conditional self-grant), where the condition
    gates the keyword; here the ability is unconditional and the keyword NAME
    differs ("Raid" vs "Grit"), making the standard grant-to-self stripping
    inapplicable without this explicit equivalence rule.
    """
    if not set_code or card_number is None:
        return False
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant, SELF,
        )
    except ImportError:
        return False
    for spec in get_abilities(set_code, str(card_number)):
        if not isinstance(spec, ConstantAbility):
            continue
        if spec.condition is not None:
            continue  # conditional — handled by rule 2
        if getattr(spec.target, "fixed", None) != SELF:
            continue
        for eff in spec.effects:
            if isinstance(eff, KeywordGrant) and eff.keyword == "Grit":
                return True
    return False


def _dynamic_self_grant_keywords(set_code: str | None,
                                 card_number: str | None) -> frozenset[str]:
    """Keywords whose VALUE this card computes for itself via a registered
    unconditional ``ConstantAbility(SELF, KeywordGrant(..., value_count=...))`` —
    "This unit gains Raid 1 for each damaged enemy unit" (Punishing One SEC_171).

    The official data tags such a card with a bare printed "Raid", which the value
    layer reads as Raid 1; leaving it would add a permanent +1 on top of the computed
    value.  The dynamic grant owns the whole value, so the printed bar is stripped.
    Keys on ``value_count`` being set, which no card that genuinely possesses a
    printed numeric keyword ever registers — so this is exact, like rule 4."""
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant, SELF,
        )
    except ImportError:
        return frozenset()
    out: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        if not isinstance(spec, ConstantAbility) or spec.condition is not None:
            continue
        if getattr(spec.target, "fixed", None) != SELF:
            continue
        for eff in spec.effects:
            if isinstance(eff, KeywordGrant) and getattr(eff, "value_count", None):
                out.add(eff.keyword)
    return frozenset(out)


def _played_from_hand_grant_keywords(set_code: str | None,
                                     card_number: str | None) -> frozenset[str]:
    """Keywords this card gains only when played from hand, via a registered
    ``KeywordIfPlayedFromHand`` marker (Millennium Falcon SHD_204 → Ambush).

    The official data tags such a card with the keyword on its printed bar even
    though the card possesses it only on a hand play (not via Smuggle etc.).  When
    the conditional grant is registered as a ``KeywordIfPlayedFromHand`` marker
    (which ``actions._put_unit_in_play`` applies on a hand play), the printed
    keyword must be stripped so the marker — not an always-on printed bar — owns it.
    """
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import get_abilities, KeywordIfPlayedFromHand
    except ImportError:
        return frozenset()
    out: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        if isinstance(spec, KeywordIfPlayedFromHand):
            out.add(spec.keyword)
    return frozenset(out)


def _chosen_keyword_aura_keywords(set_code: str | None,
                                  card_number: str | None) -> frozenset[str]:
    """Keywords this card grants to OTHER units only when its controller *chose*
    that keyword — the parallel ``ConstantAbility`` specs gated by
    ``Condition.SOURCE_CHOSEN_KEYWORD`` (Admiral Yularen JTL_47: "When Played:
    Choose Grit, Restore 1, Sentinel, or Shielded.  While this unit is in play,
    each friendly Vehicle unit gains the chosen keyword").

    The official data tags such a card with all four *choosable* keywords even
    though its own printed bar is empty, and rule 1's text heuristic keeps them
    (each name appears bare, in the "Choose …" list, rather than after "gains").
    Keying on the registered condition atom instead makes this exact and
    regression-free: no card that genuinely possesses a keyword registers a
    SOURCE_CHOSEN_KEYWORD-gated grant of it."""
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant, Condition,
        )
    except ImportError:
        return frozenset()
    out: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        if not isinstance(spec, ConstantAbility) or spec.condition is None:
            continue
        if getattr(spec.condition, "condition", None) != Condition.SOURCE_CHOSEN_KEYWORD:
            continue
        for eff in spec.effects:
            if isinstance(eff, KeywordGrant):
                out.add(eff.keyword)
    return frozenset(out)


def _granted_only_keywords(text: str | None, set_code: str | None,
                           card_number: str | None) -> frozenset[str]:
    """Keywords this card only *grants* — it registers a ``GrantKeyword`` /
    ``KeywordGrant`` for K, and K never appears at the START OF A LINE in the
    printed text (Gladiator Star Destroyer SOR_86, Captain Typho TWI_46, Bodhi Rook
    LAW_104, Remote Escort Tank SEC_255 → Sentinel; Kaadu LOF_114, Naboo Royal
    Starship SEC_99 → Overwhelm).

    Rule 1's text heuristic keeps these, because it only recognises the verb
    "gain(s)" and every one of them says "*give* a unit K" instead — and "give a
    unit Sentinel" reads as a bare mention.  Line position is the exact signal the
    source data provides: a keyword a card genuinely POSSESSES is always rendered as
    its own leading paragraph, with reminder text ("Hidden (This unit can't be
    attacked …)"), while a granted one only ever occurs mid-sentence.  Combining
    that with a REGISTERED grant (the rule 2/3/4/6/7 discipline) keeps it exact:
    nothing is stripped from a card whose ability we have not modelled.

    For a LEADER the caller passes ``text`` + ``deploy_box`` joined, because a
    leader's printed keyword bar is the leading line of its DEPLOYED side —
    Grand Admiral Sloane ASH_7's deploy box is "Overwhelm\\nEach other friendly unit
    gains Overwhelm and Sentinel", so Overwhelm (a leading line) is kept and the
    granted-only Sentinel is stripped."""
    if not set_code or card_number is None:
        return frozenset()
    try:
        from swu.abilities.registry import (
            get_abilities, GrantKeyword, KeywordGrant,
        )
    except ImportError:
        return frozenset()
    granted: set[str] = set()
    for spec in get_abilities(set_code, str(card_number)):
        sources = [spec, getattr(spec, "ability", None)]
        for src in sources:
            for eff in (getattr(src, "effects", None) or ()):
                if isinstance(eff, (GrantKeyword, KeywordGrant)):
                    granted.add(eff.keyword)
                # A grant buried inside a CustomEffect declares itself here (the
                # inert ``grants_keywords`` field) — Baylan Skoll ASH_3 hands ONE
                # chosen unit +2/+2 AND Sentinel from a single effect, which is the
                # only way to keep the two halves on one unit and one prompt.
                granted.update(getattr(eff, "grants_keywords", ()) or ())
    if not granted:
        return frozenset()
    lines = [ln.strip().lower() for ln in _normalise(text).split("\n")]
    return frozenset(
        kw for kw in granted
        if not any(ln.startswith(kw.lower()) for ln in lines))


def _is_lose_only(text: str | None, kw: str) -> bool:
    """True if EVERY textual occurrence of ``kw`` is governed by a "lose(s) K"
    clause whose subject is some OTHER unit — so the card revokes K rather than
    possessing it (Domesticated Loth-Cat ASH_68 "Enemy units lose Ambush and
    Support"; Poe Dameron ASH_40 "All units lose Sentinel"; Tusken Tracker LOF_209
    "Each enemy unit loses Hidden for this phase").

    The revoke-side mirror of rule 1, which only knows the verb "gain(s)" and so
    reads a revoked keyword as a bare mention — i.e. as possessed.  Two guards keep
    it as conservative as rule 1:

      * a keyword a card really has is printed as its OWN leading bar line, which
        has no governing verb at all, so one such occurrence keeps K (Marrok ASH_30
        prints "Sentinel" *and* says "he loses Sentinel and gains Saboteur");
      * within a clause the NEAREST preceding verb wins, so "loses Sentinel and
        **gains** Saboteur" leaves Saboteur to rules 1–9 (Marrok again).

    Scoped to Units by its caller: a LEADER's printed bar lives in ``deploy_box``,
    which this module never sees, so the leading-line guard cannot protect it.
    """
    text = _normalise(text)
    occurrences = list(re.finditer(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE))
    if not occurrences:
        return False
    for m in occurrences:
        clause_start = max(
            [text.rfind(c, 0, m.start()) for c in ".:\n"] + [-1]) + 1
        clause = text[clause_start:m.start()]
        lose_pos = max((x.end() for x in _LOSES.finditer(clause)), default=-1)
        gain_pos = max((x.end() for x in _GAINS.finditer(clause)), default=-1)
        if lose_pos < 0 or gain_pos > lose_pos:
            return False  # a bare mention, or a GRANT governs this occurrence
        head = clause[:lose_pos]
        self_pos = max((x.end() for x in _SELF_SUBJECT.finditer(head)), default=-1)
        other_pos = max((x.end() for x in _OTHER_SUBJECT.finditer(head)), default=-1)
        if other_pos <= self_pos:
            return False  # "this unit loses K" — the card had K to lose
    return True


def sanitize_keywords(
    card_type: str | None,
    text: str | None,
    keywords: Iterable[str],
    set_code: str | None = None,
    card_number: str | None = None,
    deploy_box: str | None = None,
) -> tuple[str, ...]:
    """Return ``keywords`` with mistagged keywords removed.

    Four corrections, all scoped to Unit/Leader cards (other types pass through):
      1. **Grant-to-others.**  A keyword the card only grants to *other* units
         (Admiral Piett SOR_079 → Ambush) is removed (text-driven heuristic).  For a
         LEADER the scan reads ``text`` + ``deploy_box``, since a leader's own bar is
         the leading line of its deployed side (Savage Opress TS26_5 keeps the printed
         Overwhelm his undeployed box also grants; Jabba the Hutt LAW_15 loses the
         Ambush his deploy box only grants).
      2. **Implemented conditional self-grant.**  A keyword the card grants to
         *itself conditionally*, where we have registered a ConstantAbility to
         model that grant, is removed so the ability owns it (Hunting Nexu
         SHD_168 → Raid; Protector of the Throne SHD_247 → Sentinel).
      3. **Implemented triggered self-grant.**  A keyword the card grants to
         *itself* via a registered TriggerAbility (self-targeted GrantKeyword) is
         removed so the per-phase grant — not an always-on printed bar — owns it
         (Obi-Wan Kenobi LOF_96 → Sentinel).
      4. **Grit/Raid equivalence.**  A printed "Raid" is stripped when the card
         has an unconditional ``ConstantAbility(SELF, KeywordGrant("Grit"))``
         registered — the ability models "Raid for each damage on this unit" as
         Grit, so the raw "Raid" bar is inaccurate (Fifth Brother SOR_131).
      5. **Reference-only keyword.**  A keyword whose every textual occurrence is
         a "…with K" *reference* to other cards — not possessed by this card — is
         removed (Refugee of The Path LOF_242 "give a Shield token to a unit with
         Sentinel"; Kylo Ren's Command Shuttle SEC_32 "Each friendly ground unit
         with Sentinel gets +0/+2").  The API scraped the keyword name out of the
         ability text; the card's printed bar is empty.
      6. **Played-from-hand grant.**  A keyword the card gains only on a hand play,
         modelled by a registered ``KeywordIfPlayedFromHand`` marker, is removed so
         the marker owns it (Millennium Falcon SHD_204 → Ambush).
      8. **Dynamic self-grant value.**  A numeric keyword whose value this card
         computes for itself via an unconditional ConstantAbility(SELF,
         KeywordGrant(value_count=...)) is removed, so the computed value is not
         stacked on top of the bare printed bar (Punishing One SEC_171 → Raid).
      7. **Chosen-keyword aura.**  A keyword the card grants to other units only
         when its controller picked it, modelled by a ``ConstantAbility`` gated on
         ``Condition.SOURCE_CHOSEN_KEYWORD``, is removed — the card itself never
         possesses any of the choosable keywords (Admiral Yularen JTL_47 → Grit,
         Restore, Sentinel, Shielded).
      9. **Granted-only keyword (Units and Leaders).**  A keyword the card registers a grant of
         and which never appears at the start of a line in its text is removed —
         "Give a unit Sentinel for this phase" evades rule 1 (which only knows the
         verb "gain(s)") and reads as a bare mention (Gladiator Star Destroyer
         SOR_86, Captain Typho TWI_46, Bodhi Rook LAW_104, Remote Escort Tank
         SEC_255 → Sentinel; Kaadu LOF_114, Naboo Royal Starship SEC_99 →
         Overwhelm).  For a Leader the line test reads ``text`` + ``deploy_box``,
         since a leader's own bar is the leading line of its deployed side (Grand
         Admiral Sloane ASH_7 keeps Overwhelm, loses the granted-only Sentinel).
     10. **Revoked-only keyword (Units).**  A keyword every occurrence of which is
         governed by a "lose(s) K" clause aimed at OTHER units is removed — the
         revoke-side mirror of rule 1, which knows only the verb "gain(s)" and so
         reads a revoked keyword as a bare mention (Domesticated Loth-Cat ASH_68
         "Enemy units lose Ambush and Support"; Poe Dameron ASH_40 "All units lose
         Sentinel"; Tusken Tracker LOF_209 "Each enemy unit loses Hidden").
    """
    kws = tuple(keywords)
    if card_type not in _SANITISED_TYPES:
        return kws
    conditional = _conditional_self_grant_keywords(set_code, card_number)
    triggered = _triggered_self_grant_keywords(set_code, card_number)
    from_hand = _played_from_hand_grant_keywords(set_code, card_number)
    chosen_aura = _chosen_keyword_aura_keywords(set_code, card_number)
    dynamic = _dynamic_self_grant_keywords(set_code, card_number)
    raid_via_grit = _raid_replaced_by_grit(set_code, card_number)
    if card_type == "Unit":
        granted_only = _granted_only_keywords(text, set_code, card_number)
    elif card_type == "Leader":
        # A leader's own keyword bar is the leading line of its DEPLOYED side, so the
        # line test needs the deploy box beside the (undeployed) text — Grand Admiral
        # Sloane ASH_7 keeps her printed Overwhelm and loses the Sentinel she only
        # grants to other units.
        granted_only = _granted_only_keywords(
            "\n".join(x for x in (text, deploy_box) if x), set_code, card_number)
    else:
        granted_only = frozenset()
    # RULE 1 has the SAME leader gap rule 9 closes: a leader's own keyword bar is the
    # leading line of its DEPLOYED side, and ``text`` is only the UNDEPLOYED side.
    # Savage Opress TS26_5's undeployed box says "Each friendly unit … gains
    # Overwhelm" while his deployed box prints a bare "Overwhelm" line — read on
    # ``text`` alone rule 1 saw only the grant and stripped a keyword he really has.
    # Reading both boxes lets ``_has_bare_mention`` find that printed line, which is
    # exactly the signal rule 1 keys on.  ⚠️ Rule 5 (``_is_reference_only``) is
    # deliberately NOT widened: its signal is "EVERY occurrence is a '…with K'
    # reference", so a larger corpus can only weaken it — with the deploy box included
    # Chancellor Palpatine SEC_1 would keep a Plot keyword he does not have.
    #
    # MEASURED DB-wide: exactly 8 leaders change, all genuine.  Seven get back a
    # keyword printed as their own leading deploy-box line (Moff Gideon SHD_7, Maul
    # TWI_9, Sloane ASH_7, Savage Opress TS26_5 → Overwhelm; Rio Durant JTL_15 →
    # Saboteur; Sebulba LAW_12 → Raid), and Jabba the Hutt LAW_15 correctly LOSES the
    # Ambush he only grants ("that unit gains Ambush for this phase").
    rule1_text = text
    if card_type == "Leader" and deploy_box:
        rule1_text = "\n".join(x for x in (text, deploy_box) if x)
    out = []
    for kw in kws:
        if kw in conditional or kw in triggered or kw in from_hand or kw in dynamic:
            continue  # implemented self-grant — the ability owns it
        if kw in granted_only:
            continue  # only ever granted to a target — never on this card's bar
        if kw in chosen_aura:
            continue  # choosable-keyword aura — never possessed by this card
        if kw == "Raid" and raid_via_grit:
            continue  # Grit unconditional self-grant models this card's Raid
        if kw in _KNOWN_KEYWORDS and rule1_text and _is_spurious(rule1_text, kw):
            continue  # grant-to-others-only
        if kw in _KNOWN_KEYWORDS and text and _is_reference_only(text, kw):
            continue  # keyword only referenced ("…with K"), not possessed
        if (card_type == "Unit" and kw in _KNOWN_KEYWORDS and text
                and _is_lose_only(text, kw)):
            continue  # the card REVOKES K from others — it does not possess it
        out.append(kw)
    return tuple(out)
