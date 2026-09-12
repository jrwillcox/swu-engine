"""
Keyword query layer.

Central API for checking keyword presence and extracting numeric values.
Never string-match at point of use — call has_keyword() / keyword_value()
instead.

Keyword sources (Phase 2: printed keywords only):
  * Printed on the card (card_def.keywords tuple)
  * For leaders: the deployed-unit side has its own keyword lines stored
    in deploy_box; the card_keywords table already reflects both sides,
    so card_def.keywords is authoritative for presence checks.
  * Numeric value: extracted from card_def.text (units/upgrades) or
    card_def.deploy_box (leaders) via regex.

Phase 3 will add:
  * Upgrade-granted keywords (e.g. an upgrade that grants Sentinel)
  * Effect-granted keywords (temporary, from on-attack triggers, etc.)
  At that point, pass the additional sources into has_keyword() / keyword_value().

Numeric keywords stack additively across all sources (two sources of
Raid 2 → Raid 4).  Boolean keywords are present/absent.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional, TYPE_CHECKING

from swu.engine.state import ability_suppressed, borrowed_ability_sources

if TYPE_CHECKING:
    from swu.engine.state import CardInstance, GameState


class Keyword(str, Enum):
    """All known SWU keywords.  Value is the canonical DB name."""
    SENTINEL = "Sentinel"
    OVERWHELM = "Overwhelm"
    RAID = "Raid"
    AMBUSH = "Ambush"
    RESTORE = "Restore"
    SABOTEUR = "Saboteur"
    SHIELDED = "Shielded"
    GRIT = "Grit"
    EXPLOIT = "Exploit"
    # First Strike is not a printed DB keyword — it is granted (innately via a
    # ConstantAbility, e.g. Han Solo, or for one attack via a this-attack
    # keyword_grant, e.g. Shoot First).  An attacker with First Strike deals its
    # combat damage before the defender; if the defender is defeated, it deals
    # none back.
    FIRST_STRIKE = "First Strike"
    # Phase 3 — deferred
    HIDDEN = "Hidden"
    PILOTING = "Piloting"
    BOUNTY = "Bounty"
    COORDINATE = "Coordinate"
    PLOT = "Plot"
    SUPPORT = "Support"


# Regex for extracting the numeric parameter from card text.
# Matches "Keyword N" (word-bounded) and captures the integer.
_NUMERIC_PATTERNS: dict[str, re.Pattern] = {
    kw: re.compile(rf"\b{re.escape(kw)}\s+(\d+)", re.IGNORECASE)
    for kw in ("Raid", "Restore", "Exploit")
}

_NUMERIC_KEYWORDS = frozenset(_NUMERIC_PATTERNS.keys())


def _extract_value_from_text(text: str | None, keyword: str) -> int | None:
    if not text:
        return None
    pattern = _NUMERIC_PATTERNS.get(keyword)
    if pattern is None:
        return None
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def _printed_keyword_value(card_def: object, keyword: str) -> int | None:
    """Return the printed numeric value for ``keyword`` on ``card_def``, or None."""
    from swu.cards.models import Leader
    text: str | None = getattr(card_def, "text", None)
    val = _extract_value_from_text(text, keyword)
    if val is not None:
        return val
    # For leaders, the deployed-unit side stores keyword lines in deploy_box.
    if isinstance(card_def, Leader):
        deploy_box: str | None = getattr(card_def, "deploy_box", None)
        val = _extract_value_from_text(deploy_box, keyword)
    return val


# ── Public API ────────────────────────────────────────────────────────────────

def _permanent_kw_source_in_play(state: "GameState", source_id: str) -> bool:
    """Whether a ``permanent`` keyword_grant's source is still in play — the
    keyword-layer mirror of ``actions._modifier_source_in_play`` (which gates a
    permanent *stats* modifier in ``compute_power``).  Lazily imported to avoid the
    keywords↔actions module cycle (``actions`` imports this module)."""
    from swu.engine.actions import _modifier_source_in_play
    return _modifier_source_in_play(state, source_id)


# Re-entrancy guard for the keyword-copy aura (The Ghost JTL_53).  Keyed by
# ``(id(state), instance_id)`` and added/removed around the recursive copy scan,
# so two units that copy each other's keywords (a hypothetical two-Ghost board)
# terminate instead of recursing forever.
_KEYWORD_COPY_RESOLVING: set = set()


def _copy_keyword_sources(state: "GameState", unit_ci: "CardInstance"):
    """Yield each in-play unit whose ConstantAbility copies its keywords onto
    ``unit_ci`` — "Each other friendly Spectre unit gains this unit's keywords"
    (The Ghost JTL_53).  The aura's ``not_self`` means a source never copies onto
    itself; matching reuses the universal target matcher so "friendly Spectre"
    resolves exactly as it does for any other effect."""
    try:
        from swu.abilities.registry import get_abilities, ConstantAbility, CopyKeywords
        from swu.abilities.resolver import _spec_matches_ci
    except ImportError:
        return
    for ps in state.players:
        for source_ci in ps.ground_arena + ps.space_arena:
            if source_ci.instance_id == unit_ci.instance_id:
                continue
            cd = source_ci.card_def
            if not hasattr(cd, "set_code"):
                continue
            sc = cd.set_code or ""
            cn = cd.card_number or ""
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility):
                    continue
                if not any(isinstance(e, CopyKeywords) for e in spec.effects):
                    continue
                if spec.condition and not spec.condition.evaluate(state, source_ci):
                    continue
                if not _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    continue
                yield source_ci
                break


_KEYWORD_REVOKE_KEYS: list = []   # one-element cache: frozenset[(set_code, number)]


def _keyword_revoke_aura_keys() -> frozenset:
    """The registry keys of every card carrying a ``ConstantAbility`` with a
    ``KeywordRevoke`` effect, built once and cached.

    ``has_keyword``/``keyword_value`` are the engine's hottest read path, so the
    revoke-aura board scan below must not run at all for the ~2600 cards that revoke
    nothing (the ``_suppress_leader_keys`` / ``_printed_stats_override_keys`` trick)."""
    if not _KEYWORD_REVOKE_KEYS:
        keys: set = set()
        try:
            from swu.abilities.registry import (
                _REGISTRY, ConstantAbility, KeywordRevoke)
            for key, specs in _REGISTRY.items():
                for spec in specs:
                    if isinstance(spec, ConstantAbility) and any(
                            isinstance(eff, KeywordRevoke) for eff in spec.effects):
                        keys.add(key)
                        break
        except ImportError:
            return frozenset()
        _KEYWORD_REVOKE_KEYS.append(frozenset(keys))
    return _KEYWORD_REVOKE_KEYS[0]


_UNDEPLOYED_AURA_KEYS: list = []   # one-element cache: frozenset[(set_code, number)]


def _undeployed_keyword_aura_keys() -> frozenset:
    """The registry keys of every card carrying a ``ConstantAbility(undeployed_only=
    True)`` with a ``KeywordGrant``, built once and cached.

    ``has_keyword``/``keyword_value`` are the engine's hottest read path, so the
    base-zone pass below must not run at all for the ~2600 cards that have no
    undeployed-side aura (the ``_keyword_revoke_aura_keys`` trick).  Exactly one card
    is in this set today (Savage Opress TS26_5), so the pass is a set miss per
    base-zone card."""
    if not _UNDEPLOYED_AURA_KEYS:
        keys: set = set()
        try:
            from swu.abilities.registry import (
                _REGISTRY, ConstantAbility, KeywordGrant)
            for key, specs in _REGISTRY.items():
                for spec in specs:
                    if (isinstance(spec, ConstantAbility)
                            and getattr(spec, "undeployed_only", False)
                            and any(isinstance(eff, KeywordGrant)
                                    for eff in spec.effects)):
                        keys.add(key)
                        break
        except ImportError:
            return frozenset()
        _UNDEPLOYED_AURA_KEYS.append(frozenset(keys))
    return _UNDEPLOYED_AURA_KEYS[0]


def _undeployed_aura_grants(state: "GameState", unit_ci: "CardInstance",
                            kw_name: str) -> list:
    """Every ``KeywordGrant`` of ``kw_name`` an UNDEPLOYED leader's aura currently
    confers on ``unit_ci``, paired with the leader that grants it.

    The base-zone counterpart of the arena ConstantAbility scan in ``has_keyword``.
    An undeployed leader sits in ``base_zone``, which the arena scans never walk —
    that is precisely what makes every ordinary leader ConstantAbility deployed-only
    for free — so a clause printed on a leader's UNDEPLOYED side ("Each friendly unit
    with the most power among friendly units gains Overwhelm", Savage Opress TS26_5)
    needs its own pass, opted into by ``ConstantAbility.undeployed_only``.  Returns
    ``[(effect, source_ci), …]`` so the numeric reader can price each grant."""
    keys = _undeployed_keyword_aura_keys()
    if not keys:
        return []
    try:
        from swu.abilities.registry import get_abilities, ConstantAbility, KeywordGrant
        from swu.abilities.resolver import _spec_matches_ci
    except ImportError:
        return []
    out: list = []
    for ps in state.players:
        for source_ci in ps.base_zone:
            cd = source_ci.card_def
            key = (getattr(cd, "set_code", None) or "",
                   getattr(cd, "card_number", None) or "")
            if key not in keys:
                continue
            if getattr(source_ci, "deployed", False):
                continue   # belt and braces: a deployed leader has left base_zone
            if ability_suppressed(state, source_ci):
                continue
            for spec in get_abilities(*key):
                if not isinstance(spec, ConstantAbility):
                    continue
                if not getattr(spec, "undeployed_only", False):
                    continue
                grants = [eff for eff in spec.effects
                          if isinstance(eff, KeywordGrant) and eff.keyword == kw_name]
                if not grants:
                    continue  # keyword filter before the condition — see has_keyword
                if spec.condition and not spec.condition.evaluate(state, source_ci):
                    continue
                if not _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    continue
                out.extend((eff, source_ci) for eff in grants)
    return out


def _aura_revoked(state: "GameState", unit_ci: "CardInstance", kw_name: str) -> bool:
    """True if an in-play card's ``KeywordRevoke`` aura currently strips ``kw_name``
    from ``unit_ci`` — "Enemy units lose Ambush and Support" (Domesticated Loth-Cat
    ASH_68).  Read before every grant source, so "can't gain it" is intrinsic."""
    keys = _keyword_revoke_aura_keys()
    if not keys:
        return False
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordRevoke)
        from swu.abilities.resolver import _spec_matches_ci
    except ImportError:
        return False
    for ps in state.players:
        for source_ci in ps.ground_arena + ps.space_arena:
            cd = source_ci.card_def
            key = (getattr(cd, "set_code", None) or "", getattr(cd, "card_number", None) or "")
            if key not in keys:
                continue
            if ability_suppressed(state, source_ci):
                continue
            for spec in get_abilities(*key):
                if not isinstance(spec, ConstantAbility):
                    continue
                if not any(isinstance(eff, KeywordRevoke) and eff.keyword == kw_name
                           for eff in spec.effects):
                    continue
                if spec.condition and not spec.condition.evaluate(state, source_ci):
                    continue
                if _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    return True
    return False


def _keywords_suppressed(state: "GameState", unit_ci: "CardInstance") -> bool:
    """True if a ``keywords_suppressed`` Modifier currently covers ``unit_ci``.

    The applied, keyword-only mirror of the ``abilities_suppressed`` read-layer
    (Mind Trick LOF_202): "it loses its keywords (and can't gain keywords) for this
    phase" (Screeching TIE Fighter SEC_185).  Carried as a Modifier so it expires
    with the ordinary duration sweep, and read at both keyword-layer entry points so
    the "can't gain" half needs no separate guard."""
    for mod in getattr(state, "modifiers", []):
        if (mod.kind == "keywords_suppressed"
                and mod.target_instance_id == unit_ci.instance_id):
            return True
    return False


def has_keyword(state: "GameState", unit_ci: "CardInstance", keyword: Keyword) -> bool:
    """Return True if unit_ci has keyword from any active source.

    Sources (Phase 3):
      1. Printed on the card (card_def.keywords)
      2. Granted by a Modifier record (keyword_grant kind)
      3. Granted by an active ConstantAbility (KeywordGrant static effect)
    A keyword_revoke modifier on this unit suppresses sources 1 and 2.
    """
    kw_name = keyword.value

    # A unit whose abilities are suppressed this phase (Mind Trick LOF_202) has NO
    # keywords, from any source — the early return also makes "can't gain abilities"
    # fall out (even a keyword granted to it below is never reached).  A card an
    # enemy Galen Erso P25_31 has named is suppressed the same way (persistent /
    # name-based).
    if ability_suppressed(state, unit_ci):
        # ONE carve-out: a keyword_grant modifier flagged despite_suppression
        # survives the blackout — "Attached unit loses … all abilities EXCEPT FOR
        # GRIT.  Attached unit gains Grit" (Exiled from the Force SEC_54), where the
        # same card both suppresses and grants.  Default-off, so every existing
        # grant still goes dark exactly as before.
        for mod in getattr(state, "modifiers", []):
            if (mod.target_instance_id == unit_ci.instance_id
                    and mod.kind == "keyword_grant"
                    and mod.value.get("keyword") == kw_name
                    and mod.value.get("despite_suppression")):
                if mod.duration == "permanent" and not _permanent_kw_source_in_play(
                        state, mod.source_instance_id):
                    continue
                return True
        return False

    # "It loses its keywords (and can't gain keywords) for this phase" (Screeching
    # TIE Fighter SEC_185) — the KEYWORD-only sibling of ``abilities_suppressed``:
    # every source is dark, but the unit keeps its triggers/constants.  Read here
    # and in ``keyword_value``, so "can't gain" falls out the same way.
    if _keywords_suppressed(state, unit_ci):
        return False

    # Check for revoke first
    for mod in getattr(state, "modifiers", []):
        if (mod.target_instance_id == unit_ci.instance_id
                and mod.kind == "keyword_revoke"
                and mod.value.get("keyword") == kw_name):
            return False

    # …and the standing aura form of the same revoke ("Enemy units lose Ambush and
    # Support" — Domesticated Loth-Cat ASH_68).  Read here, ahead of every grant
    # source, so a unit under the aura also cannot GAIN the keyword.
    if _aura_revoked(state, unit_ci, kw_name):
        return False

    # Printed keyword on the card itself
    card_keywords = getattr(unit_ci.card_def, "keywords", ())
    if kw_name in card_keywords:
        return True

    # Modifier records — keyword_grant.  A ``permanent`` grant models "while
    # <source> is in play, this unit gains <keyword>" (BD-1 C25_4) — the keyword-
    # layer mirror of the ``permanent`` stat modifier (Huyang TWI_110), so it is
    # inert once its source has left play (the same source-in-play guard that
    # ``compute_power`` applies to a permanent stats modifier).
    for mod in getattr(state, "modifiers", []):
        if (mod.target_instance_id == unit_ci.instance_id
                and mod.kind == "keyword_grant"
                and mod.value.get("keyword") == kw_name):
            if mod.duration == "permanent" and not _permanent_kw_source_in_play(
                    state, mod.source_instance_id):
                continue
            return True

    # ConstantAbility KeywordGrant from other cards in play
    try:
        from swu.abilities.registry import get_abilities, ConstantAbility, KeywordGrant
        from swu.abilities.resolver import _spec_matches_ci
        for ps in state.players:
            for source_ci in ps.ground_arena + ps.space_arena:
                if not hasattr(source_ci.card_def, "set_code"):
                    continue
                # An upgrade may carry an aura over OTHER cards, resolved as if its
                # HOST were the source (``via_host`` — Figure of Unity SEC_104).  The
                # host stays ``source_ci`` in both cases, so "this unit"/"friendly"/
                # "not_self" always read off the unit in the arena.
                for spec_ci in (source_ci,
                                *(getattr(source_ci, "attached_upgrades", None) or ())):
                    from_upgrade = spec_ci is not source_ci
                    sc = getattr(spec_ci.card_def, "set_code", None) or ""
                    cn = getattr(spec_ci.card_def, "card_number", None) or ""
                    if not sc or not cn:
                        continue
                    for spec in get_abilities(sc, cn):
                        if not isinstance(spec, ConstantAbility):
                            continue
                        if from_upgrade != bool(getattr(spec, "via_host", False)):
                            continue  # via_host specs come ONLY from the upgrade slot
                        if getattr(spec, "upgrade_only", False):
                            continue  # "Attached unit gains …" — conferred only by the
                                      # attached-upgrade scan below, never by the card's
                                      # own unit side (Jarek Yeager JTL_109)
                        if getattr(spec, "undeployed_only", False):
                            continue  # a leader's UNDEPLOYED-side aura, read by the
                                      # base-zone pass below (Savage Opress TS26_5)
                        # Filter on the keyword FIRST: a condition may itself read this
                        # layer (Oppo Rancisis LOF_105 asks whether another friendly unit
                        # has keyword K), and evaluating the conditions of grants for
                        # *other* keywords would fan that recursion out across every
                        # keyword on the board.  Conditions are pure predicates, so the
                        # reordering is free.
                        if not any(isinstance(eff, KeywordGrant) and eff.keyword == kw_name
                                   for eff in spec.effects):
                            continue
                        if spec.condition and not spec.condition.evaluate(state, source_ci):
                            continue
                        if not _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                            continue
                        return True
    except ImportError:
        pass  # abilities not yet loaded (early boot)

    # …and the same aura printed on a leader's UNDEPLOYED side, whose source sits in
    # base_zone and so is invisible to the arena scan above (Savage Opress TS26_5).
    if _undeployed_aura_grants(state, unit_ci, kw_name):
        return True

    # Granted by an attached upgrade's ConstantAbility KeywordGrant(target=SELF):
    # "Attached unit gains <keyword>" (Grievous's Wheel Bike TWI_236 → Overwhelm).
    # Mirrors the trait query layer (``traits._granted_traits``), which scans the
    # host's attached upgrades for a SELF-targeted TraitGrant; the arena scan above
    # never sees an upgrade (it lives in its host's ``attached_upgrades``, not an
    # arena), so this is the only path that confers an upgrade's keyword.
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant, SELF)
        for upg in getattr(unit_ci, "attached_upgrades", None) or ():
            cd = upg.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility) or spec.target.fixed != SELF:
                    continue
                if not any(isinstance(eff, KeywordGrant) and eff.keyword == kw_name
                           for eff in spec.effects):
                    continue  # keyword filter before the condition — see above
                if spec.condition is not None and not spec.condition.evaluate(state, unit_ci):
                    continue
                return True
    except ImportError:
        pass

    # Keyword-copy aura: "Each other friendly Spectre unit gains this unit's
    # keywords" (The Ghost JTL_53).  The unit has the keyword if any copy source
    # has it.  Guarded against mutual-copy recursion.
    #
    # The BORROW (Support: "It gains this unit's other abilities for this attack")
    # rides the same guarded block — a borrowed keyword reads exactly like a copied
    # one, and Support itself is excluded because the card says "other abilities".
    guard = (id(state), unit_ci.instance_id)
    if guard not in _KEYWORD_COPY_RESOLVING:
        _KEYWORD_COPY_RESOLVING.add(guard)
        try:
            sources = list(_copy_keyword_sources(state, unit_ci))
            if keyword is not Keyword.SUPPORT:
                sources += borrowed_ability_sources(state, unit_ci)
            for source_ci in sources:
                if has_keyword(state, source_ci, keyword):
                    return True
        finally:
            _KEYWORD_COPY_RESOLVING.discard(guard)

    return False


def has_any_keyword(state: "GameState", unit_ci: "CardInstance") -> bool:
    """True if ``unit_ci`` has at least one keyword — "a unit that has 1 or more
    keywords" (Boba Fett SHD_8).

    Deliberately a LIGHTWEIGHT check (printed keywords minus revokes, plus modifier
    ``keyword_grant`` grants) rather than iterating ``has_keyword`` over the
    ``Keyword`` enum: this predicate is consulted from inside a ConstantAbility aura
    target (Boba's deployed aura), and ``has_keyword``'s own constant-ability scan
    would call back into ``_spec_matches_ci`` on that same aura target — an infinite
    recursion.  So a keyword granted ONLY by another card's aura is not counted here
    (a documented simplification; every SHD_8-relevant unit carries a printed
    keyword).  Ability / name suppression zero it out, matching ``has_keyword``."""
    if ability_suppressed(state, unit_ci):
        return False
    revoked = {
        mod.value.get("keyword")
        for mod in getattr(state, "modifiers", [])
        if mod.target_instance_id == unit_ci.instance_id and mod.kind == "keyword_revoke"
    }
    for kw in getattr(unit_ci.card_def, "keywords", ()) or ():
        if kw not in revoked:
            return True
    for mod in getattr(state, "modifiers", []):
        if (mod.target_instance_id == unit_ci.instance_id
                and mod.kind == "keyword_grant"):
            if mod.duration == "permanent" and not _permanent_kw_source_in_play(
                    state, mod.source_instance_id):
                continue
            return True
    return False


def distinct_keyword_count(state: "GameState", unit_ci: "CardInstance") -> int:
    """How many DIFFERENT keywords ``unit_ci`` has — "units with 2 or more different
    keywords get +2/+2" (Gallius Rax ASH_100).  ``len(distinct_keyword_names(...))``."""
    return len(distinct_keyword_names(state, unit_ci))


def distinct_keyword_names(state: "GameState", unit_ci: "CardInstance") -> set:
    """The NAMES of the different keywords ``unit_ci`` has.

    The set behind ``distinct_keyword_count``, exposed so a card can UNION across
    several units — "If there are 4 or more different keywords among friendly units"
    (The Darksaber TS26_22), which a per-unit count cannot answer.

    The counting sibling of ``has_any_keyword``, and lightweight for the same
    reason: it is consulted from inside a ConstantAbility aura target, so iterating
    ``has_keyword`` over the ``Keyword`` enum would recurse through the very scans
    that evaluate that aura.  Printed keywords minus revokes, plus ``keyword_grant``
    modifier grants; a keyword granted ONLY by another card's aura is not counted
    (the documented ``has_any_keyword`` simplification).  Ability / name suppression
    zeroes it out, matching ``has_keyword``."""
    if ability_suppressed(state, unit_ci):
        return set()
    revoked = {
        mod.value.get("keyword")
        for mod in getattr(state, "modifiers", [])
        if mod.target_instance_id == unit_ci.instance_id and mod.kind == "keyword_revoke"
    }
    names: set = set()
    for kw in getattr(unit_ci.card_def, "keywords", ()) or ():
        # A printed keyword may carry its value ("Raid 2"); the NAME is what makes
        # two keywords different, so normalise to the leading word(s).
        base = str(kw).split(" ")[0]
        if kw not in revoked and base not in revoked:
            names.add(base)
    for mod in getattr(state, "modifiers", []):
        if (mod.target_instance_id == unit_ci.instance_id
                and mod.kind == "keyword_grant"):
            if mod.duration == "permanent" and not _permanent_kw_source_in_play(
                    state, mod.source_instance_id):
                continue
            granted = str(mod.value.get("keyword") or "").split(" ")[0]
            if granted and granted not in revoked:
                names.add(granted)
    return names


def _keyword_grant_value(state: "GameState", eff, source_ci) -> int:
    """The numeric value one ``KeywordGrant`` contributes.

    Normally the flat ``value``; a grant carrying ``value_count`` instead names a
    board count evaluated now, relative to ``source_ci`` (the card whose
    ConstantAbility this is) — "Raid 1 for each damaged enemy unit" (Punishing One
    SEC_171).  The keyword-layer sibling of ``StatBonus.count``; an unknown count name
    contributes nothing."""
    count = getattr(eff, "value_count", None)
    if not count:
        return eff.value
    if count == "damaged_enemy_units":
        own = state.player_index(source_ci.owner_id)
        return sum(1 for i, ps in enumerate(state.players) if i != own
                   for u in ps.ground_arena + ps.space_arena if u.damage > 0)
    return 0


def keyword_value(state: "GameState", unit_ci: "CardInstance", keyword: Keyword) -> int:
    """Return the effective numeric value for a stacking keyword (Raid, Restore, Exploit).

    Returns 0 if the keyword is absent or has no numeric parameter.
    Multiple sources add together.
    """
    kw_name = keyword.value
    total = 0

    # Abilities suppressed this phase (Mind Trick LOF_202) or named by an enemy
    # Galen Erso P25_31 → no numeric keyword.
    if ability_suppressed(state, unit_ci):
        return 0
    # Keyword-only blackout (Screeching TIE Fighter SEC_185) — see has_keyword.
    if _keywords_suppressed(state, unit_ci):
        return 0
    # A standing KeywordRevoke aura zeroes the value too (ASH_68) — the numeric
    # mirror of the same read in ``has_keyword``, and likewise ahead of every source.
    if _aura_revoked(state, unit_ci, kw_name):
        return 0

    # Printed value on the card itself
    if kw_name in unit_ci.card_def.keywords:
        v = _printed_keyword_value(unit_ci.card_def, kw_name)
        if v is not None:
            total += v

    # Modifier records — keyword_grant with numeric value.  A ``permanent`` grant
    # (BD-1 C25_4) is inert once its source has left play — see ``has_keyword``.
    for mod in getattr(state, "modifiers", []):
        if (mod.target_instance_id == unit_ci.instance_id
                and mod.kind == "keyword_grant"
                and mod.value.get("keyword") == kw_name):
            if mod.duration == "permanent" and not _permanent_kw_source_in_play(
                    state, mod.source_instance_id):
                continue
            total += mod.value.get("value", 0)

    # ConstantAbility KeywordGrant numeric values
    try:
        from swu.abilities.registry import get_abilities, ConstantAbility, KeywordGrant
        from swu.abilities.resolver import _spec_matches_ci
        for ps in state.players:
            for source_ci in ps.ground_arena + ps.space_arena:
                if not hasattr(source_ci.card_def, "set_code"):
                    continue
                # ``via_host`` upgrade-borne auras — see the note in ``has_keyword``.
                for spec_ci in (source_ci,
                                *(getattr(source_ci, "attached_upgrades", None) or ())):
                    from_upgrade = spec_ci is not source_ci
                    sc = getattr(spec_ci.card_def, "set_code", None) or ""
                    cn = getattr(spec_ci.card_def, "card_number", None) or ""
                    if not sc or not cn:
                        continue
                    for spec in get_abilities(sc, cn):
                        if not isinstance(spec, ConstantAbility):
                            continue
                        if from_upgrade != bool(getattr(spec, "via_host", False)):
                            continue
                        if getattr(spec, "upgrade_only", False):
                            continue  # see the matching note in ``has_keyword``
                        if getattr(spec, "undeployed_only", False):
                            continue  # see the matching note in ``has_keyword``
                        grants = [eff for eff in spec.effects
                                  if isinstance(eff, KeywordGrant) and eff.keyword == kw_name]
                        if not grants:
                            continue  # keyword filter before the condition — see the
                                      # recursion note in ``has_keyword``
                        if spec.condition and not spec.condition.evaluate(state, source_ci):
                            continue
                        if not _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                            continue
                        for eff in grants:
                            total += _keyword_grant_value(state, eff, source_ci)
    except ImportError:
        pass

    # The undeployed-leader aura's numeric contribution (see ``has_keyword``).
    for eff, src in _undeployed_aura_grants(state, unit_ci, kw_name):
        total += _keyword_grant_value(state, eff, src)

    # Attached-upgrade ConstantAbility KeywordGrant(target=SELF) numeric values
    # ("Attached unit gains <Keyword N>"; the SELF-target conferral the arena scan
    # above cannot see — see the matching note in ``has_keyword``).
    try:
        from swu.abilities.registry import (
            get_abilities, ConstantAbility, KeywordGrant, SELF)
        for upg in getattr(unit_ci, "attached_upgrades", None) or ():
            cd = upg.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility) or spec.target.fixed != SELF:
                    continue
                grants = [eff for eff in spec.effects
                          if isinstance(eff, KeywordGrant) and eff.keyword == kw_name]
                if not grants:
                    continue  # keyword filter before the condition — see above
                if spec.condition is not None and not spec.condition.evaluate(state, unit_ci):
                    continue
                for eff in grants:
                    total += _keyword_grant_value(state, eff, unit_ci)
    except ImportError:
        pass

    # Keyword-copy aura (The Ghost JTL_53): add each copy source's value for this
    # keyword ("gains this unit's keywords" — a numeric keyword is copied at its
    # value).  Guarded against mutual-copy recursion.
    # A BORROWED keyword (Support) is added the same way — see ``has_keyword``.
    guard = (id(state), unit_ci.instance_id)
    if guard not in _KEYWORD_COPY_RESOLVING:
        _KEYWORD_COPY_RESOLVING.add(guard)
        try:
            sources = list(_copy_keyword_sources(state, unit_ci))
            if keyword is not Keyword.SUPPORT:
                sources += borrowed_ability_sources(state, unit_ci)
            for source_ci in sources:
                total += keyword_value(state, source_ci, keyword)
        finally:
            _KEYWORD_COPY_RESOLVING.discard(guard)

    # LAST: multiplicative doublers ("Each friendly unit's Raid is doubled",
    # Marchion Ro LOF_186).  Applied after every additive source so it doubles the
    # EFFECTIVE value, which is what the card says.
    if total:
        total *= _keyword_doubling_factor(state, unit_ci, kw_name)

    return total


# Cache: does a card type carry a ``DoubleKeywordValue`` marker?  Almost none do,
# so the hot keyword_value path skips the spec scan for the rest with one dict
# lookup (the traits._arena_granter_cache pattern).  Card defs are immutable.
_doubler_cache: dict = {}


def _is_keyword_doubler(get_abilities, DoubleKeywordValue, sc: str, cn: str) -> bool:
    key = (sc, cn)
    cached = _doubler_cache.get(key)
    if cached is None:
        cached = any(isinstance(spec, DoubleKeywordValue)
                     for spec in get_abilities(sc, cn))
        _doubler_cache[key] = cached
    return cached


def _keyword_doubling_factor(state: "GameState", unit_ci: "CardInstance",
                             kw_name: str) -> int:
    """2**n, where n is the number of in-play ``DoubleKeywordValue`` markers for
    ``kw_name`` whose target matches ``unit_ci`` (Marchion Ro LOF_186).  1 — the
    identity — for the overwhelming majority of units, at the cost of one cached
    lookup per unit in play."""
    try:
        from swu.abilities.registry import get_abilities, DoubleKeywordValue
        from swu.abilities.resolver import _spec_matches_ci
    except ImportError:
        return 1
    factor = 1
    for ps in state.players:
        for source_ci in ps.ground_arena + ps.space_arena:
            cd = source_ci.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            if not _is_keyword_doubler(get_abilities, DoubleKeywordValue, sc, cn):
                continue
            if ability_suppressed(state, source_ci):
                continue
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, DoubleKeywordValue) or spec.keyword != kw_name:
                    continue
                if _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    factor *= 2
    return factor


# ── Smuggle cost parsing ──────────────────────────────────────────────────────
#
# Smuggle is a deck-replacement keyword: a card in your resource zone may be
# played for its printed "Smuggle cost" (a resource number + aspect icons),
# then replaced with the top card of your deck.  The smuggle cost is printed
# inside a bracket, e.g.:
#     "Smuggle [5 resources Aggression Heroism]"
#     "Smuggle [3 resources, cunning]"
# The bracketed aspect icons drive the same +2-per-unmatched-pip penalty as a
# card's printed cost (computed against the controller's base/leader aspects).

_ASPECT_NAMES: tuple[str, ...] = (
    "Vigilance", "Command", "Aggression", "Cunning", "Heroism", "Villainy",
)
_SMUGGLE_BRACKET_RE = re.compile(r"Smuggle\s*\[([^\]]*)\]", re.IGNORECASE)


def parse_smuggle_cost(text: str | None) -> Optional[tuple[int, tuple[str, ...]]]:
    """Parse a printed ``Smuggle [N resources <aspects>]`` clause.

    Returns ``(resource_count, aspect_names)`` or ``None`` if no smuggle cost is
    printed.  Aspect names are normalised to their canonical capitalised form.
    """
    if not text:
        return None
    m = _SMUGGLE_BRACKET_RE.search(text)
    if not m:
        return None
    inner = m.group(1)
    nm = re.search(r"(\d+)", inner)
    n = int(nm.group(1)) if nm else 0
    aspects = tuple(
        a for a in _ASPECT_NAMES
        if re.search(rf"\b{re.escape(a)}\b", inner, re.IGNORECASE)
    )
    return n, aspects


# ── Piloting cost parsing ─────────────────────────────────────────────────────
#
# Piloting is a dual-mode keyword: a Unit card with Piloting may be played
# either as a normal unit OR as a Pilot upgrade on a friendly Vehicle unit,
# paying the bracketed Piloting cost instead of the unit cost.  The cost is
# printed in the card's epic_action field, e.g.:
#     "Piloting [2 resources Aggression Villainy]"

_PILOTING_BRACKET_RE = re.compile(r"Piloting\s*\[([^\]]*)\]", re.IGNORECASE)


def parse_piloting_cost(text: str | None) -> Optional[tuple[int, tuple[str, ...]]]:
    """Parse a printed ``Piloting [N resources <aspects>]`` clause.

    Returns ``(resource_count, aspect_names)`` or ``None`` if not present.
    The Piloting clause lives in the card's ``epic_action`` field, not ``text``.
    """
    if not text:
        return None
    m = _PILOTING_BRACKET_RE.search(text)
    if not m:
        return None
    inner = m.group(1)
    nm = re.search(r"(\d+)", inner)
    n = int(nm.group(1)) if nm else 0
    aspects = tuple(
        a for a in _ASPECT_NAMES
        if re.search(rf"\b{re.escape(a)}\b", inner, re.IGNORECASE)
    )
    return n, aspects


def shields_on(unit_ci: "CardInstance") -> int:
    """Count Shield tokens attached to unit_ci."""
    from swu.cards.models import TokenUpgrade
    return sum(
        1 for u in unit_ci.attached_upgrades
        if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Shield"
    )


def experience_on(unit_ci: "CardInstance") -> int:
    """Count Experience tokens attached to unit_ci."""
    from swu.cards.models import TokenUpgrade
    return sum(
        1 for u in unit_ci.attached_upgrades
        if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Experience"
    )
