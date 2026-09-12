"""
Trait query layer.

Central API for the *effective* traits of a unit — its printed traits plus any
traits granted to it while in play.  Mirrors the keyword query layer
(``swu.engine.keywords.has_keyword``): never read ``card_def.traits`` directly at
a point where a granted trait should count — call ``get_traits`` / ``has_trait``.

Sources of a granted trait today:
  * An attached **upgrade** carrying a ``ConstantAbility`` whose effects include a
    ``TraitGrant`` (Foundling, SHD_69: "Attached unit gains the Mandalorian
    trait").  The grant resolves from the upgrade onto its host unit.
  * An **in-play unit** carrying a ``ConstantAbility`` whose (non-SELF) target
    matches *other* units and whose effects include a ``TraitGrant`` (Malakili,
    LAW_212: "Each friendly Creature unit … gains the Underworld trait").  The
    grant resolves from the source unit onto every unit its target matches.

The printed traits always count; granted traits are additive and de-duplicated.
A future "trait_grant" Modifier kind could be folded in here without changing any
consumer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import CardInstance, GameState

# Re-entrancy guard for ``_granted_traits``.  An arena-wide grant's target filter
# (e.g. Malakili's ``traits=("Creature",)``) reads the candidate's effective traits
# via ``get_traits`` → ``_granted_traits`` again; the guard breaks that cycle by
# exposing only the printed traits to the nested matcher.  Keyed by (id(state),
# instance_id) so concurrent queries on different units don't interfere.
_resolving_grants: set = set()

# Cache: does a card type carry an arena-wide (non-SELF) ConstantAbility TraitGrant?
# The vast majority of cards do not, so the hot trait-query path skips the full
# spec scan for them with a single dict lookup.  Card defs are immutable so this is
# safe across states/games.
_arena_granter_cache: dict = {}

# Cache: the set of trait names that ANY registered TraitGrant (upgrade or arena)
# can confer.  Tiny (e.g. {"Underworld", "Mandalorian"}).  ``has_trait`` consults it
# to skip the (potentially board-wide) granted-trait scan entirely for the common
# case — a query for a trait no card grants (e.g. "Trooper") is then a single set
# membership test.  Populated lazily from the registry after all ``@card_ability``
# decorators have run (import time, before any game).
_grantable_traits_cache: "set | None" = None


def _grantable_traits() -> set:
    global _grantable_traits_cache
    if _grantable_traits_cache is None:
        try:
            from swu.abilities.registry import (
                get_all_registered, ConstantAbility, TraitGrant)
        except ImportError:
            return set()  # abilities not yet loaded (early boot) — don't cache
        traits: set = set()
        for specs in get_all_registered().values():
            for spec in specs:
                if isinstance(spec, ConstantAbility):
                    for eff in spec.effects:
                        if isinstance(eff, TraitGrant):
                            traits.add(eff.trait)
        _grantable_traits_cache = traits
    return _grantable_traits_cache


def _revoked_traits(state: "GameState", ci: "CardInstance") -> set:
    """Traits currently REVOKED from ``ci`` by a ``trait_revoke`` Modifier ("Each
    enemy unit loses the Force trait for this phase", Nameless Terror LOF_33).

    Read ahead of both the printed traits and every grant source — the
    ``keyword_revoke`` convention — so a revoked trait also cannot be re-granted
    while the modifier lasts."""
    out: set = set()
    for mod in getattr(state, "modifiers", []) or ():
        if (mod.target_instance_id == ci.instance_id
                and mod.kind == "trait_revoke"):
            t = mod.value.get("trait")
            if t:
                out.add(t)
    return out


def get_traits(state: "GameState", ci: "CardInstance") -> tuple[str, ...]:
    """Return the effective traits of ``ci`` — printed plus granted, minus any
    revoked — preserving printed order and appending any granted trait not already
    present."""
    printed = tuple(getattr(ci.card_def, "traits", None) or ())
    granted = _granted_traits(state, ci)
    revoked = _revoked_traits(state, ci)
    out = [t for t in printed if t not in revoked]
    for t in granted:
        if t not in out and t not in revoked:
            out.append(t)
    return tuple(out)


def has_trait(state: "GameState", ci: "CardInstance", trait: str) -> bool:
    """True if ``ci`` has ``trait`` from any source (printed or granted) and it is
    not currently revoked."""
    if trait in _revoked_traits(state, ci):
        return False
    if trait in (getattr(ci.card_def, "traits", None) or ()):
        return True
    # Fast path: if no registered card can ever grant this trait, skip the
    # (potentially board-wide) granted-trait scan — the overwhelming majority of
    # trait queries are for never-granted traits (Trooper, Rebel, Force, …).
    if trait not in _grantable_traits():
        return False
    return trait in _granted_traits(state, ci)


def _granted_traits(state: "GameState", ci: "CardInstance") -> tuple[str, ...]:
    """Traits granted to ``ci`` by (1) its attached upgrades' TraitGrant constants
    and (2) in-play units whose arena-wide TraitGrant constant targets ``ci``."""
    key = (id(state), ci.instance_id)
    if key in _resolving_grants:
        # Re-entrant query (a grant's target trait filter is reading this unit's
        # traits): break the cycle by exposing printed traits only.
        return ()
    try:
        from swu.abilities.registry import get_abilities, ConstantAbility, TraitGrant
    except ImportError:
        return ()  # abilities not yet loaded (early boot)

    _resolving_grants.add(key)
    try:
        out: list[str] = []
        # (1) Attached-upgrade TraitGrant constants (Foundling SHD_69, Leia's
        #     Disguise LAW_111).  The grant applies to the host unit (``ci``).
        for upg in getattr(ci, "attached_upgrades", None) or ():
            cd = upg.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility):
                    continue
                if spec.condition is not None and not spec.condition.evaluate(state, ci):
                    continue
                for eff in spec.effects:
                    if isinstance(eff, TraitGrant) and eff.trait not in out:
                        out.append(eff.trait)

        # (2) Arena-wide TraitGrant constants on other in-play units (Malakili
        #     LAW_212).  The grant resolves from the source unit; its non-SELF
        #     target is matched against ``ci`` from the source's perspective.
        _scan_arena_grants(state, ci, out, get_abilities, ConstantAbility, TraitGrant)
        return tuple(out)
    finally:
        _resolving_grants.discard(key)


def _is_arena_trait_granter(get_abilities, ConstantAbility, TraitGrant,
                            sc: str, cn: str) -> bool:
    """True if this card type carries an arena-wide (non-SELF) ConstantAbility whose
    effects include a TraitGrant — cached, since card defs are immutable."""
    key = (sc, cn)
    cached = _arena_granter_cache.get(key)
    if cached is not None:
        return cached
    from swu.abilities.registry import SELF
    result = False
    for spec in get_abilities(sc, cn):
        if (isinstance(spec, ConstantAbility)
                and spec.target.fixed != SELF
                and any(isinstance(e, TraitGrant) for e in spec.effects)):
            result = True
            break
    _arena_granter_cache[key] = result
    return result


def _scan_arena_grants(state, ci, out, get_abilities, ConstantAbility, TraitGrant):
    """Append traits granted to ``ci`` by any in-play unit's arena-wide TraitGrant
    ConstantAbility whose target matches ``ci``."""
    from swu.abilities.resolver import _spec_matches_ci
    from swu.engine.state import ability_suppressed
    for ps in state.players:
        for source in (*ps.ground_arena, *ps.space_arena):
            if ability_suppressed(state, source):
                continue  # a suppressed (Mind Trick LOF_202) or Galen-named (P25_31)
                          # unit grants no traits
            cd = source.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            if not _is_arena_trait_granter(get_abilities, ConstantAbility,
                                           TraitGrant, sc, cn):
                continue
            from swu.abilities.registry import SELF
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility) or spec.target.fixed == SELF:
                    continue
                grants = [e.trait for e in spec.effects if isinstance(e, TraitGrant)]
                if not grants:
                    continue
                if spec.condition is not None and not spec.condition.evaluate(state, source):
                    continue
                if not _spec_matches_ci(spec.target, ci, source, state, {}):
                    continue
                for t in grants:
                    if t not in out:
                        out.append(t)
