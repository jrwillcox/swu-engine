"""Effective stats: what a unit's power and HP actually are right now.

A card's printed power and HP are only the starting point.  By the time a unit
fights, its numbers may have been changed by upgrades, Experience tokens, active
constant abilities on either side, temporary modifiers with a duration, aura
effects from other units, and outright printed-stat overrides.  ``compute_power``
and ``compute_hp`` are the single answer to "what is this unit, now", and every
combat, targeting and legality decision in the engine is written against them
rather than against the card definition.

This module is the bottom of the kernel alongside ``base``: it imports nothing
else from the ``actions`` package, and ``damage``, ``zones`` and ``combat`` all
build on it.  That direction matters — it is why the attack pipeline can ask for a
number without knowing how the number was assembled.

Two behaviours here are load-bearing and easy to break:

* **``compute_power`` floors at zero.** Nothing in the game has negative power, so
  a -3 modifier on a 2-power unit yields 0, not -1.  Damage calculations depend on
  that floor rather than re-clamping at each call site.
* **``_ZERO_POWER_COUNT_EVALUATING`` guards re-entrancy.** An ability whose bonus
  is "+1 power for each friendly unit with 0 power" has to evaluate power *while*
  computing power.  The guard stops that recursing forever, and is the reason
  those abilities read the printed-plus-modifier value of the unit being counted
  rather than its fully-resolved value.
"""
from __future__ import annotations

from typing import Optional

from swu.engine.keywords import Keyword, has_keyword, keyword_value
from swu.engine.state import (
    CardInstance, GameState, ability_suppressed,
)



# ── Effective-stats layer ─────────────────────────────────────────────────────

_PRINTED_STATS_OVERRIDE_KEYS: "Optional[set]" = None
_PRINTED_STATS_AURA_KEYS: "Optional[set]" = None


def _printed_stats_override_keys() -> set:
    """(set_code, card_number) keys of every card carrying a ``PrintedStatsOverride``
    marker.  Tiny (one card today); ``compute_power``/``compute_hp`` sit on the
    hottest path in the engine, so the per-upgrade spec walk must only run for a
    host actually carrying such an upgrade."""
    global _PRINTED_STATS_OVERRIDE_KEYS
    if _PRINTED_STATS_OVERRIDE_KEYS is None:
        from swu.abilities.registry import get_all_registered, PrintedStatsOverride
        keys = set()
        for key, specs in get_all_registered().items():
            if any(isinstance(sp, PrintedStatsOverride) for sp in specs):
                keys.add(key)
        _PRINTED_STATS_OVERRIDE_KEYS = keys
    return _PRINTED_STATS_OVERRIDE_KEYS


def _printed_stats_aura_keys() -> set:
    """(set_code, card_number) keys of every card carrying an AURA
    ``PrintedStatsOverride`` (``aura_controller`` set — Obi-Wan Kenobi LAW_36).
    Kept separate from the upgrade-borne keys so the arena scan is skipped
    entirely while no such card is registered."""
    global _PRINTED_STATS_AURA_KEYS
    if _PRINTED_STATS_AURA_KEYS is None:
        from swu.abilities.registry import get_all_registered, PrintedStatsOverride
        keys = set()
        for key, specs in get_all_registered().items():
            if any(isinstance(sp, PrintedStatsOverride)
                   and getattr(sp, "aura_controller", None) for sp in specs):
                keys.add(key)
        _PRINTED_STATS_AURA_KEYS = keys
    return _PRINTED_STATS_AURA_KEYS


def _printed_stats_override(state: Optional[GameState], unit_ci: CardInstance):
    """``{"power": N, "hp": M}`` (either key optional) if anything overrides this
    unit's PRINTED stats, else None.  Read at the seed of ``compute_power`` /
    ``compute_hp``, so every ordinary bonus still layers on top.

    Three sources, applied in the order they can become active — the card's own
    "the most recent … determines the printed values" rule:

      1. an AURA ``PrintedStatsOverride`` on a friendly unit in an arena (Obi-Wan
         Kenobi LAW_36, "While you control 7 or more units, their printed power is
         considered to be 7 and printed HP is considered to be 7");
      2. an attached-upgrade ``PrintedStatsOverride`` (Size Matters Not LOF_56);
      3. a ``printed_stats`` MODIFIER on the instance — the duration-carrying
         flavour (Adventurer Sniper Rifle LAW_126, "Its printed HP is considered to
         be 1 for this phase").
    """
    out: Optional[dict] = None
    from swu.abilities.registry import get_abilities, PrintedStatsOverride

    aura_keys = _printed_stats_aura_keys()
    if aura_keys and state is not None:
        try:
            owner_ps = state.player_by_id(unit_ci.owner_id)
        except Exception:
            owner_ps = None
        if owner_ps is not None:
            for src in owner_ps.ground_arena + owner_ps.space_arena:
                cd = src.card_def
                key = (getattr(cd, "set_code", None) or "",
                       str(getattr(cd, "card_number", "") or ""))
                if key not in aura_keys:
                    continue
                if ability_suppressed(state, src):
                    continue
                for spec in get_abilities(key[0], key[1]):
                    if not isinstance(spec, PrintedStatsOverride):
                        continue
                    if not getattr(spec, "aura_controller", None):
                        continue
                    if (spec.condition is not None
                            and not spec.condition.evaluate(state, src)):
                        continue
                    out = dict(out or {})
                    if spec.power is not None:
                        out["power"] = spec.power
                    if spec.hp is not None:
                        out["hp"] = spec.hp

    ups = getattr(unit_ci, "attached_upgrades", None)
    keys = _printed_stats_override_keys()
    if ups and keys:
        for up in ups:
            cd = up.card_def
            key = (getattr(cd, "set_code", None) or "",
                   str(getattr(cd, "card_number", "") or ""))
            if key not in keys:
                continue
            for spec in get_abilities(key[0], key[1]):
                if not isinstance(spec, PrintedStatsOverride):
                    continue
                if getattr(spec, "aura_controller", None):
                    continue  # an aura rides the arena scan above, not a host
                out = dict(out or {})
                if spec.power is not None:
                    out["power"] = spec.power
                if spec.hp is not None:
                    out["hp"] = spec.hp

    if state is not None:
        for mod in state.modifiers:
            if (mod.kind == "printed_stats"
                    and mod.target_instance_id == unit_ci.instance_id):
                out = dict(out or {})
                if mod.value.get("power") is not None:
                    out["power"] = int(mod.value["power"])
                if mod.value.get("hp") is not None:
                    out["hp"] = int(mod.value["hp"])
    return out


def compute_power(state: GameState, unit_ci: CardInstance, is_attacking: bool = False,
                  attacking_unit: bool = False, defender_id: Optional[str] = None,
                  attacking_base: bool = False, is_defending: bool = False,
                  attacker_id: Optional[str] = None) -> int:
    """Effective power for combat, context-aware.

    Aggregates: base power + upgrade bonuses (incl. Experience tokens)
              + Grit (+1 per damage on this unit)
              + Raid (+N only while this unit is attacking)
              + Phase 3 Modifier records (stats / keyword_grant)
              + ConstantAbility buffs from cards in play

    Use this in the attack pipeline instead of unit_ci.effective_power().
    """
    base = getattr(unit_ci.card_def, "power", 0) or 0
    # "Attached unit's printed power/HP is considered to be N" (Size Matters Not
    # LOF_56) — an upgrade-borne override of the PRINTED seed; everything below
    # still layers on top.
    _override = _printed_stats_override(state, unit_ci)
    if _override is not None and _override.get("power") is not None:
        base = _override["power"]
    # Upgrade and token stat bonuses
    for u in unit_ci.attached_upgrades:
        base += getattr(u.card_def, "upgrade_power", 0) or 0
    # Grit: +1 per damage on this unit
    if has_keyword(state, unit_ci, Keyword.GRIT):
        base += unit_ci.damage
    # Raid: +N only while attacking
    if is_attacking and has_keyword(state, unit_ci, Keyword.RAID):
        base += keyword_value(state, unit_ci, Keyword.RAID)
    # Phase 3: Modifier records
    for mod in state.modifiers:
        if mod.target_instance_id == unit_ci.instance_id and mod.kind == "stats":
            if (mod.duration == "permanent"
                    and not _modifier_source_in_play(state, mod.source_instance_id)):
                continue  # "while this unit is in play" — source has left play
            if mod.value.get("while_attacking_base") and not attacking_base:
                continue  # "-2/-0 while it's attacking a base" (Sly Moore SEC_33) —
                          # the debuff contributes only at the base-attack site
            if (mod.value.get("while_attacking_unit_id")
                    and mod.value["while_attacking_unit_id"] != defender_id):
                continue  # "-4/-0 while attacking THAT unit" (I Have the High Ground
                          # TWI_72) — the applied-modifier sibling of the "while
                          # defending" constant (Lando LAW_108), which reads the same
                          # ``defender_id`` combat context; outside an attack on that
                          # unit (defender_id None) the debuff contributes nothing
            base += mod.value.get("power", 0)
    # Phase 3: ConstantAbility buffs from cards currently in play.  ``attacking_unit``
    # gates "while attacking an enemy unit" constants (Moff Gideon SHD_7);
    # ``defender_id`` identifies the current combat defender so a "while defending"
    # source debuffs only the unit attacking it (Lando Calrissian LAW_108).
    base += _constant_ability_power_bonus(state, unit_ci, attacking_unit, defender_id,
                                          is_defending, attacker_id)
    return max(0, base)


def compute_hp(state: GameState, unit_ci: CardInstance) -> int:
    """Effective max HP for a unit, context-aware.

    Aggregates: base HP + upgrade bonuses + Phase 3 Modifier records +
    ConstantAbility HP buffs.

    Use this instead of unit_ci.effective_hp() wherever modifiers may apply.
    """
    base = getattr(unit_ci.card_def, "hp", 0) or 0
    _override = _printed_stats_override(state, unit_ci)
    if _override is not None and _override.get("hp") is not None:
        base = _override["hp"]  # Size Matters Not LOF_56 / Obi-Wan LAW_36
    for u in unit_ci.attached_upgrades:
        base += getattr(u.card_def, "upgrade_hp", 0) or 0
    # Phase 3: Modifier records
    for mod in state.modifiers:
        if mod.target_instance_id == unit_ci.instance_id and mod.kind == "stats":
            if (mod.duration == "permanent"
                    and not _modifier_source_in_play(state, mod.source_instance_id)):
                continue  # "while this unit is in play" — source has left play
            if mod.value.get("while_attacking_base"):
                continue  # combat-only debuff (Sly Moore SEC_33); compute_hp carries
                          # no combat context, so it never contributes HP
            base += mod.value.get("hp", 0)
    # Phase 3: ConstantAbility HP buffs
    base += _constant_ability_hp_bonus(state, unit_ci)
    return max(1, base)


def _modifier_source_in_play(state: GameState, source_id: str) -> bool:
    """Whether ``source_id`` is still in play (an arena unit or an attached
    upgrade / pilot).  Used to gate a ``permanent`` modifier that models "while
    this unit is in play, …" (Huyang TWI_110) — the documented ``permanent``
    semantic ("lasts until source leaves play")."""
    for ps in state.players:
        for ci in ps.ground_arena + ps.space_arena:
            if ci.instance_id == source_id:
                return True
            for up in ci.attached_upgrades:
                if up.instance_id == source_id:
                    return True
    return False


def _constant_stat_sources(ps) -> list:
    """Cards of ``ps`` whose ConstantAbility stat buffs are live.

    Every arena unit, plus the player's **BASE** — a base is a permanent in play
    and can carry a constant ("Each leader unit you control gets +0/+1", Pau City
    TWI_19 / Petranaki Arena TWI_28).  The undeployed LEADER also sits in
    ``base_zone`` but is deliberately excluded: a leader's ConstantAbility is
    deployed-only, which is exactly what the arenas-only scan has always given it
    for free (Anakin Skywalker TWI_12's self-buff, Nala Se TWI_1's aura).
    """
    out = list(ps.ground_arena) + list(ps.space_arena)
    base = ps.base_instance
    if base is not None:
        out.append(base)
    return out


def _constant_ability_power_bonus(state: GameState, unit_ci: CardInstance,
                                  attacking_unit: bool = False,
                                  defender_id: Optional[str] = None,
                                  is_defending: bool = False,
                                  attacker_id: Optional[str] = None) -> int:
    """Sum all active ConstantAbility power bonuses that apply to unit_ci.

    A ``while_attacking_unit`` constant (Moff Gideon SHD_7) contributes its
    StatBonus only when ``unit_ci`` is currently attacking an enemy unit.  A
    ``while_defending`` constant (Lando Calrissian LAW_108) contributes only
    while its *source* is the current combat defender (``defender_id``), so its
    debuff lands solely on the unit attacking that source.  A ``while_attacking``
    constant (Strafing Gunship SOR_212) contributes only while its *source* is the
    current combat attacker (``attacker_id``), so its debuff lands solely on the
    unit that source is attacking.
    """
    from swu.abilities.registry import get_abilities, ConstantAbility, StatBonus
    total = 0
    for ps in state.players:
        for source_ci in _constant_stat_sources(ps):
            if not hasattr(source_ci.card_def, "set_code"):
                continue
            if ability_suppressed(state, source_ci):
                continue  # a suppressed (Mind Trick LOF_202) / Galen-named (P25_31)
                          # / Imprisoned (SHD_72) unit buffs nothing
            sc = source_ci.card_def.set_code or ""
            cn = source_ci.card_def.card_number or ""
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility):
                    continue
                if getattr(spec, "via_host", False):
                    continue  # an upgrade-borne aura — handled by the dedicated
                              # _via_host_stat_bonus pass, never from a unit's own
                              # specs (Figure of Unity SEC_104, Fulcrum LAW_150)
                if getattr(spec, "upgrade_only", False):
                    continue  # "Attached unit gains …" — conferred only by
                              # _upgrade_self_stat_bonus, never by the card's own
                              # unit side (Jarek Yeager JTL_109)
                if getattr(spec, "while_attacking_unit", False) and not attacking_unit:
                    continue
                want_arena = getattr(spec, "while_attacking_unit_arena", None)
                if want_arena is not None:
                    # "While attacking a SPACE unit …" (Retrofitted Airspeeder
                    # JTL_259) — the defender must exist and sit in that arena.
                    if not attacking_unit or defender_id is None:
                        continue
                    dres = state.find_instance(defender_id)
                    if dres is None:
                        continue
                    zname = dres[1].zone.name
                    if zname != ("SPACE_ARENA" if want_arena == "space"
                                 else "GROUND_ARENA"):
                        continue
                if getattr(spec, "while_attacking_damaged_unit", False):
                    # "While attacking a DAMAGED unit" (Marrok's Fiend Fighter
                    # ASH_241) — the exact sibling of the bounty arm below.
                    if not attacking_unit or defender_id is None:
                        continue
                    dres = state.find_instance(defender_id)
                    if dres is None or dres[1].damage <= 0:
                        continue
                if getattr(spec, "while_attacking_bounty_unit", False):
                    # "While attacking a unit with a Bounty" (Jango Fett SHD_138): the
                    # target must be attacking a unit (defender_id threaded) that
                    # currently has a Bounty.
                    if not attacking_unit or defender_id is None:
                        continue
                    dres = state.find_instance(defender_id)
                    from swu.abilities.resolver import _unit_has_bounty
                    if dres is None or not _unit_has_bounty(state, dres[1]):
                        continue
                if getattr(spec, "while_defending", False) and (
                        defender_id is None
                        or source_ci.instance_id != defender_id):
                    continue
                if getattr(spec, "while_target_defending", False) and not is_defending:
                    continue
                if getattr(spec, "while_attacking", False) and (
                        attacker_id is None
                        or source_ci.instance_id != attacker_id):
                    continue
                if spec.condition and not spec.condition.evaluate(state, source_ci):
                    continue
                from swu.abilities.resolver import _spec_matches_ci
                if _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    for eff in spec.effects:
                        if isinstance(eff, StatBonus):
                            total += _stat_bonus_amount(state, source_ci, eff,
                                                        "power", unit_ci)
    # Attached upgrades conferring a ``while_defending`` debuff on the attacker
    # (Electrostaff SOR_71: "While attached unit is defending, the attacker gets
    # −1/−0").  The main loop scans arena units' own specs, not their upgrades, so
    # handle upgrade-borne while_defending constants here: the HOST is the
    # defender identity and the debuff lands on the enemy attacker (unit_ci).
    if defender_id is not None:
        from swu.abilities.registry import get_abilities as _get_ab, ConstantAbility as _CA, StatBonus as _SB
        for ps in state.players:
            for host in ps.ground_arena + ps.space_arena:
                if host.instance_id != defender_id:
                    continue
                for up in host.attached_upgrades:
                    sc = getattr(up.card_def, "set_code", None) or ""
                    cn = getattr(up.card_def, "card_number", None) or ""
                    if not sc or not cn:
                        continue
                    for spec in _get_ab(sc, cn):
                        if not isinstance(spec, _CA) or not getattr(spec, "while_defending", False):
                            continue
                        if spec.condition and not spec.condition.evaluate(state, host):
                            continue
                        from swu.abilities.resolver import _spec_matches_ci
                        if _spec_matches_ci(spec.target, unit_ci, host, state, {}):
                            for eff in spec.effects:
                                if isinstance(eff, _SB):
                                    total += _stat_bonus_amount(state, host, eff,
                                                                "power", unit_ci)
    total += _upgrade_self_stat_bonus(state, unit_ci, "power")
    total += _via_host_stat_bonus(state, unit_ci, "power")
    return total


def _via_host_stat_bonus(state: GameState, unit_ci: CardInstance, which: str) -> int:
    """StatBonus contributed to ``unit_ci`` by an upgrade-borne AURA — a
    ``ConstantAbility(via_host=True)`` on some arena unit's attached upgrade,
    resolved as if the HOST were its source ("Attached unit gains … 'Each other
    friendly Rebel unit gets +2/+2'" — Fulcrum LAW_150).

    The stat-layer twin of the ``via_host`` walk in ``keywords.has_keyword``
    (Figure of Unity SEC_104), and a separate pass for the same reason the
    ``while_defending`` upgrade pass above is one: the main loop scans a unit's OWN
    specs.  The host is the source throughout, so "friendly" / "not_self" and the
    condition all read off the unit standing in the arena, and a suppressed host
    confers nothing.  Combat-scoped ``while_*`` variants are skipped — no aura of
    this shape carries one, and neither stat path threads combat context here."""
    from swu.abilities.registry import get_abilities, ConstantAbility, StatBonus
    from swu.abilities.resolver import _spec_matches_ci
    total = 0
    for ps in state.players:
        for host in ps.ground_arena + ps.space_arena:
            if not host.attached_upgrades or ability_suppressed(state, host):
                continue
            for up in host.attached_upgrades:
                sc = getattr(up.card_def, "set_code", None) or ""
                cn = getattr(up.card_def, "card_number", None) or ""
                if not sc or not cn:
                    continue
                for spec in get_abilities(sc, cn):
                    if not isinstance(spec, ConstantAbility):
                        continue
                    if not getattr(spec, "via_host", False):
                        continue
                    if spec.condition and not spec.condition.evaluate(state, host):
                        continue
                    if not _spec_matches_ci(spec.target, unit_ci, host, state, {}):
                        continue
                    for eff in spec.effects:
                        if isinstance(eff, StatBonus):
                            total += _stat_bonus_amount(state, host, eff,
                                                        which, unit_ci)
    return total


# Reentrancy guard for the ``other_zero_power_units`` StatBonus count (Kelleran Beq
# ASH_206), the ``_POWER_MIN_EVALUATING`` trick one layer over: that count reads
# every other unit's EFFECTIVE power, and ``compute_power`` re-enters the constant
# scan that is evaluating it.
_ZERO_POWER_COUNT_EVALUATING = False


def _stat_bonus_amount(state: GameState, source_ci: CardInstance,
                       eff, which: str,
                       target_ci: Optional[CardInstance] = None) -> int:
    """The power/hp a StatBonus contributes, honouring a ``count`` scaling source.

    A flat StatBonus (``count is None``) contributes its raw ``power``/``hp``; a
    scaling StatBonus contributes that per-unit amount times a count computed from
    game state relative to the buff's ``source_ci`` (Nien Nunb JTL_93).

    ``target_ci`` is the BUFFED unit — needed only by a count that scales per
    recipient rather than per source ("Each enemy non-leader unit gets −1/−0 **for
    each damage on it**", Radiant VII JTL_226).  Every other count ignores it."""
    base = eff.power if which == "power" else eff.hp
    count_src = getattr(eff, "count", None)
    if not count_src or base == 0:
        return base
    return base * _stat_bonus_count(state, source_ci, count_src, target_ci)


def _stat_bonus_count(state: GameState, source_ci: CardInstance,
                      count_src: str,
                      target_ci: Optional[CardInstance] = None) -> int:
    """Magnitude for a scaling StatBonus ``count`` (mirrors the DealDamageEqualTo
    ``_scaling_magnitude`` pattern, but for a persistent stat buff).

    ``other_friendly_pilots`` — the number of friendly Pilot units plus friendly
    Pilot upgrades, minus one for the source itself (Nien Nunb is always exactly
    one friendly Pilot card — a Pilot unit when played normally, a Pilot upgrade
    when played via Piloting — so "each OTHER friendly Pilot unit and upgrade" is
    the total friendly Pilot count less itself).  "Friendly" is relative to the
    buff's controller (the owner of the buffed unit == the Pilot's controller).
    """
    if count_src == "target_damage":
        # Radiant VII JTL_226: "Each enemy non-leader unit gets −1/−0 for each
        # damage on it."  The only count read off the BUFFED unit rather than the
        # buff's source — with no target threaded it contributes nothing.
        if target_ci is None:
            return 0
        return int(getattr(target_ci, "damage", 0) or 0)
    if count_src == "captives_guarded":
        # Libertine SEC_212: "This unit gets +1/+0 for each captured card it's
        # guarding."  A captive lives in its owner's capture pile carrying
        # ``captured_by`` = its guard's instance id, so the count is that scan.
        return sum(1 for ps in state.players for c in ps.capture_pile
                   if getattr(c, "captured_by", None) == source_ci.instance_id)
    if count_src == "damaged_units_in_play":
        # War Juggernaut JTL_170: "This unit gets +1/+0 for each damaged unit."
        # Every damaged arena unit on EITHER side ("each damaged unit", not
        # "each damaged unit you control"); the source counts itself when damaged.
        return sum(1 for ps in state.players
                   for u in ps.ground_arena + ps.space_arena
                   if int(getattr(u, "damage", 0) or 0) > 0)
    if count_src == "upgrades_on_other_friendly_units":
        # Executor ASH_197: "+1/+0 for each upgrade on OTHER friendly units."
        # Every attached card counts — a Shield / Experience / Advantage token IS
        # an upgrade in SWU — but nothing on the Executor itself.  Reads no power,
        # so it cannot re-enter the stat scans.
        ps = state.player_by_id(source_ci.owner_id)
        return sum(len(u.attached_upgrades)
                   for u in ps.ground_arena + ps.space_arena
                   if u.instance_id != source_ci.instance_id)
    if count_src == "other_zero_power_units":
        # Kelleran Beq ASH_206: "+1/+0 for each OTHER unit (friendly and enemy)
        # with 0 power."  EFFECTIVE power, so it must call back into
        # ``compute_power`` — which re-enters the very constant scan that is
        # evaluating this count.  The guard reports 0 on re-entry, which is also the
        # right answer: this bonus lands on Kelleran alone (fixed=SELF), so it can
        # never change another unit's power and therefore never its own count.
        global _ZERO_POWER_COUNT_EVALUATING
        if _ZERO_POWER_COUNT_EVALUATING:
            return 0
        _ZERO_POWER_COUNT_EVALUATING = True
        try:
            return sum(1 for ps in state.players
                       for u in ps.ground_arena + ps.space_arena
                       if u.instance_id != source_ci.instance_id
                       and compute_power(state, u) == 0)
        finally:
            _ZERO_POWER_COUNT_EVALUATING = False
    if count_src == "other_friendly_space_units":
        # Clone Combat Squadron JTL_115: "+1/+1 for each OTHER friendly space unit."
        # The controller's space arena less the source itself (which is always in it).
        ps = state.player_by_id(source_ci.owner_id)
        return sum(1 for u in ps.space_arena
                   if u.instance_id != source_ci.instance_id)
    if count_src == "other_friendly_pilots":
        from swu.engine.traits import has_trait
        ps = state.player_by_id(source_ci.owner_id)
        n = 0
        for u in ps.ground_arena + ps.space_arena:
            if has_trait(state, u, "Pilot"):
                n += 1
            for up in u.attached_upgrades:
                if "Pilot" in (getattr(up.card_def, "traits", ()) or ()):
                    n += 1
        return max(0, n - 1)
    if count_src == "pilots_on_self":
        # Number of Pilot upgrades attached to the source unit itself
        # (Millennium Falcon JTL_249: "+1/+0 for each Pilot on it").  A Pilot
        # upgrade OR a leader deployed as an upgrade both carry the Pilot trait.
        return sum(
            1 for up in getattr(source_ci, "attached_upgrades", None) or ()
            if "Pilot" in (getattr(up.card_def, "traits", ()) or ()))
    if count_src == "other_exhausted_friendly_units":
        # Kino Loy SEC_114: "+1/+0 for each OTHER exhausted friendly unit."  Count
        # the controller's exhausted arena units, excluding the source itself.
        ps = state.player_by_id(source_ci.owner_id)
        return sum(
            1 for u in ps.ground_arena + ps.space_arena
            if getattr(u, "exhausted", False)
            and u.instance_id != source_ci.instance_id)
    if count_src == "other_friendly_same_name":
        # Swarming Vulture Droid JTL_256: "+1/+0 for each other friendly Swarming
        # Vulture Droid."  Count the controller's arena units sharing the source's
        # printed name, excluding the source itself.
        ps = state.player_by_id(source_ci.owner_id)
        name = getattr(source_ci.card_def, "name", None)
        return sum(
            1 for u in ps.ground_arena + ps.space_arena
            if getattr(u.card_def, "name", None) == name
            and u.instance_id != source_ci.instance_id)
    if count_src == "upgrades_on_self":
        # Axe Woves LOF_62: "This unit gets +1/+1 for each upgrade on him."  Count
        # every upgrade attached to the source — Shield/Experience tokens included,
        # since tokens ARE upgrade cards per CR (so an Experience token nets +2/+2:
        # its own inherent +1/+1 plus this +1/+1).
        return len(getattr(source_ci, "attached_upgrades", None) or ())
    if count_src == "controller_hand_size":
        # Qi'ra ASH_226: "This unit gets -1/-0 for each card in your hand."  Count
        # the buff controller's hand (the source is in play, so never in hand).
        return len(state.player_by_id(source_ci.owner_id).hand)
    if count_src == "controller_resources":
        # 97th Legion SOR_118: "+1/+1 for each resource you control."  Count every
        # resource in the buff controller's resource row (available + spent).
        return len(state.player_by_id(source_ci.owner_id).resources)
    if count_src == "controller_ready_token_units":
        # Governor Pryce SEC_11 (deployed): "This unit gets +1/+0 for each READY
        # friendly TOKEN unit."  Token units are the ones with no printed cost that
        # the token-unit registry creates; ``token_unit`` is the same test the
        # target predicate uses.
        from swu.cards.models import TokenUnit
        res = state.find_instance(source_ci.instance_id)
        ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
        return sum(1 for arena in (ps.ground_arena, ps.space_arena)
                   for u in arena
                   if isinstance(u.card_def, TokenUnit) and not u.exhausted)
    if count_src.startswith("controller_discard_trait_cards_"):
        # Orn Free Taa SEC_112: "This unit gets +1/+0 for each LAW CARD in your
        # discard pile" — the card-type-blind sibling of
        # ``controller_discard_trait_units_`` (events and upgrades count too).
        # PRINTED traits, for the same reason: a card in the discard is out of the
        # trait-grant layer's reach.
        trait = count_src[len("controller_discard_trait_cards_"):]
        res = state.find_instance(source_ci.instance_id)
        ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
        return sum(1 for c in ps.discard
                   if trait in (getattr(c.card_def, "traits", None) or ()))
    if count_src.startswith("controller_discard_trait_units_"):
        # Captain Enoch LOF_83: "This unit gets +1/+0 for each Trooper unit in your
        # discard pile."  The trait rides in the count string after the prefix, so
        # one arm serves any trait.  A card in the DISCARD is not in play, so the
        # trait-grant layer cannot reach it — PRINTED traits, and the Unit card-def
        # test is what "unit" means there.
        from swu.cards.models import Unit
        trait = count_src[len("controller_discard_trait_units_"):]
        res = state.find_instance(source_ci.instance_id)
        ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
        return sum(1 for c in ps.discard
                   if isinstance(c.card_def, Unit)
                   and trait in (getattr(c.card_def, "traits", None) or ()))
    if count_src.startswith("other_controller_trait_units_"):
        # Kit Fisto LOF_11 (deployed): "This unit gets +1/+0 for each OTHER friendly
        # Jedi unit" — the self-excluding sibling of ``controller_trait_units_``
        # below, over the same effective-trait / both-arenas basis.  The source is
        # itself a Jedi unit whenever this is evaluated (it is in an arena), so
        # "each other" is exactly the total less itself.
        from swu.engine.traits import has_trait
        trait = count_src[len("other_controller_trait_units_"):]
        res = state.find_instance(source_ci.instance_id)
        ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
        return sum(1 for arena in (ps.ground_arena, ps.space_arena)
                   for u in arena
                   if u.instance_id != source_ci.instance_id
                   and has_trait(state, u, trait))
    if count_src.startswith("controller_trait_units_"):
        # Squad Support TWI_122: "This unit gets +1/+1 for each Trooper unit you
        # control" — the trait rides in the count string after the prefix, so one
        # arm serves any trait.  Effective traits (a TraitGrant counts), both
        # arenas, the CONTROLLER_N_PLUS_TRAIT_UNITS basis; the source itself
        # counts when it carries the trait ("each", not "each other").
        #
        # "You" is the CONTROLLER.  For an upgrade-granted buff the source passed
        # here is the UPGRADE (``_upgrade_self_stat_bonus``), whose ``owner_id`` is
        # whoever played it — which is the wrong seat when the upgrade sits on an
        # enemy unit.  ``find_instance`` returns the player whose zones hold the
        # card, i.e. the HOST's controller, so prefer it and fall back to the owner.
        from swu.engine.traits import has_trait
        trait = count_src[len("controller_trait_units_"):]
        res = state.find_instance(source_ci.instance_id)
        ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
        return sum(1 for arena in (ps.ground_arena, ps.space_arena)
                   for u in arena if has_trait(state, u, trait))
    if count_src.startswith("controller_base_damage_per_"):
        # Anakin Skywalker TWI_12: "This unit gets +1/+0 for every 5 damage on your
        # base" — the StatBonus sibling of CostReduction.per_controller_base_damage
        # (Resolute TWI_151), the divisor riding in the count string after the last
        # underscore so one arm serves any step size.  Integer division: 4 damage
        # with a step of 5 is still no bonus.
        per = int(count_src.rsplit("_", 1)[1] or 1)
        base = state.player_by_id(source_ci.owner_id).base_instance
        dmg = base.damage if base is not None else 0
        return (dmg // per) if per > 0 else 0
    return 0


def _upgrade_self_stat_bonus(state: GameState, unit_ci: CardInstance,
                             which: str) -> int:
    """Sum StatBonus contributions an attached upgrade's own
    ``ConstantAbility(target=SELF, …)`` grants to its host — "Attached unit gains:
    '<this unit gets +X/+Y>'" (IG-88 JTL_141, played as a Pilot upgrade).

    Mirrors the keyword layer's attached-upgrade scan (``keywords.has_keyword``):
    the arena constant-ability scan never sees an upgrade (it lives in the host's
    ``attached_upgrades``, not an arena), so this is the only path that confers an
    upgrade's SELF-targeted stat buff to its host.  A present condition is
    evaluated against the HOST (``unit_ci``) — its owner is the upgrade's
    controller, so a "while an enemy unit is damaged" gate reads correctly.
    """
    from swu.abilities.registry import get_abilities, ConstantAbility, StatBonus, SELF
    total = 0
    for upg in getattr(unit_ci, "attached_upgrades", None) or ():
        cd = upg.card_def
        sc = getattr(cd, "set_code", None) or ""
        cn = getattr(cd, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if not isinstance(spec, ConstantAbility) or spec.target.fixed != SELF:
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, unit_ci):
                continue
            for eff in spec.effects:
                if isinstance(eff, StatBonus):
                    total += _stat_bonus_amount(state, upg, eff, which, unit_ci)
    return total


def _constant_ability_hp_bonus(state: GameState, unit_ci: CardInstance) -> int:
    """Sum all active ConstantAbility HP bonuses that apply to unit_ci.

    ``while_attacking_unit`` and ``while_defending`` constants are skipped entirely
    — compute_hp carries no combat context, so a combat-only buff/debuff never
    contributes HP (Moff Gideon grants +1/+0 and Lando debuffs −1/−0 anyway).
    """
    from swu.abilities.registry import get_abilities, ConstantAbility, StatBonus
    total = 0
    for ps in state.players:
        for source_ci in _constant_stat_sources(ps):
            if not hasattr(source_ci.card_def, "set_code"):
                continue
            if ability_suppressed(state, source_ci):
                continue  # a suppressed (Mind Trick LOF_202) / Galen-named (P25_31)
                          # / Imprisoned (SHD_72) unit buffs nothing
            sc = source_ci.card_def.set_code or ""
            cn = source_ci.card_def.card_number or ""
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility):
                    continue
                if getattr(spec, "via_host", False):
                    continue  # upgrade-borne aura — the _via_host_stat_bonus pass
                if getattr(spec, "upgrade_only", False):
                    continue  # see the matching note in _constant_ability_power_bonus
                if getattr(spec, "while_attacking_unit", False):
                    continue
                if getattr(spec, "while_attacking_bounty_unit", False):
                    continue  # combat-only (Jango SHD_138 is +3/+0 anyway)
                if getattr(spec, "while_attacking_damaged_unit", False):
                    continue  # combat-only (Marrok's Fiend Fighter ASH_241 is +2/+0)
                if getattr(spec, "while_defending", False):
                    continue
                if spec.condition and not spec.condition.evaluate(state, source_ci):
                    continue
                from swu.abilities.resolver import _spec_matches_ci
                if _spec_matches_ci(spec.target, unit_ci, source_ci, state, {}):
                    for eff in spec.effects:
                        if isinstance(eff, StatBonus):
                            total += _stat_bonus_amount(state, source_ci, eff,
                                                        "hp", unit_ci)
    total += _upgrade_self_stat_bonus(state, unit_ci, "hp")
    total += _via_host_stat_bonus(state, unit_ci, "hp")
    return total


# ── Deploy threshold extraction ───────────────────────────────────────────────

def _expire_modifiers(s: GameState, duration: str) -> None:
    """Remove all Modifier records whose duration matches the given tag."""
    from swu.engine.events import ModifierExpired
    remaining = []
    for m in s.modifiers:
        if m.duration == duration:
            s.event_log.append(ModifierExpired(
                modifier_id=m.modifier_id,
                reason=duration,
            ))
        else:
            remaining.append(m)
    s.modifiers = remaining
