"""Dealing damage: shields, prevention, amplification, and what counts as lethal.

Every point of damage in the game — combat, ability, indirect, overwhelm spillover,
deck-out — passes through ``_deal_damage_with_shield``.  That single funnel is why
Shield behaves consistently: a Shield token intercepts one whole instance of damage
and is then defeated, regardless of the amount or the source.  The rule is
engine-native rather than encoded per card, which is also why the Shield token card
carries no registry entry.

This module sits below ``zones`` and ``combat``, which surprises people (including
the plan for this refactor).  It has to: ``_put_unit_in_play`` deals damage when a
unit enters play into a damaging aura, and ``_draw_cards`` deals damage when a deck
runs out.  Damage application is a primitive those depend on, not a phase of the
attack pipeline.

The prevention chain runs in a fixed order, and the order is the behaviour:

1. ``_damage_is_unpreventable`` — indirect damage from certain sources ignores
   everything below, so it is checked first.
2. ``_damage_prevention_on`` / ``_consume_shield_aura_prevention`` — "prevent the
   next damage" effects, consumed one use at a time.
3. Shield tokens, via ``_deal_damage_with_shield``.
4. ``_damage_amplification_on`` — increases applied to what survives.
5. ``_base_damage_cap`` and ``_bases_cannot_heal`` — base-specific limits.

``_hp_lethal`` decides defeat by comparing damage to *effective* HP from ``stats``,
never printed HP, so a unit kept alive by an upgrade stays alive.  ``base_damage_
after_prevention`` is the same question asked for bases, and both are deliberately
separate from the act of removing anything from play: deciding lethality and
executing a defeat are different concerns, and the defeat lives in ``zones``.
"""
from __future__ import annotations

from typing import Optional

from swu.engine.events import (
    CombatDamagePrevented, DamageDealt, DamagePrevented,
)
from swu.engine.keywords import shields_on
from swu.engine.state import (
    CardInstance, GameState, Phase, PlayerState, ability_suppressed,
)
from swu.engine.tokens import defeat_shield

from swu.engine.actions.stats import (
    compute_hp,
)


# ── apply convenience wrapper ─────────────────────────────────────────────────

def note_base_healed(s: GameState, base_ci: "CardInstance", healed: int) -> None:
    """Record that ``healed`` damage was actually removed from the BASE ``base_ci``
    this phase, feeding ``game_memory.bases_healed_this_phase``.

    The base flavour of ``note_unit_healed`` — and its own function because a base
    has no single heal chokepoint: like ``_bases_cannot_heal`` (the read this mirrors)
    it is called at every site that can take damage off a base — the generic
    ``resolver._apply_heal``, Restore (``_apply_restore``), the heal flavour of the
    damage-distribution finish, Reinforcement Walker SOR_119's discard-heal, and a
    bounty's ``heal_base`` payoff.  ``healed <= 0`` records nothing: an undamaged base
    "healed" for 3 had no damage removed, so it was not healed.

    It also queues ``[owner_id, healed]`` on ``game_memory.base_heal_events`` for the
    WhenYouHealYourBase observer (Darth Sidious IC27_26: "When you heal damage from
    your base: Deal that much damage to an enemy unit")."""
    if healed <= 0 or base_ci is None:
        return
    s.game_memory.bases_healed_this_phase.add(base_ci.instance_id)
    s.game_memory.base_heal_events.append([base_ci.owner_id, int(healed)])


def _hp_defeat_prevented(s: GameState, ci: CardInstance) -> bool:
    """True if a passive marker protects ``ci`` from being defeated *for having no
    remaining HP* (The Tragedy of Plagueis LOF_43: "For this phase, it can't be
    defeated by having no remaining HP").

    Modelled as a ``prevent_hp_defeat`` Modifier on the unit (duration
    ``this_phase``, so it expires at the ACTION→REGROUP rollover via the existing
    ``_expire_modifiers(s, "this_phase")`` step).  It is a pure read — the exact
    mirror of the ``Protection`` marker (Chewbacca JTL_103), which guards only
    *ability* defeat/return and deliberately leaves combat/HP defeat alone; this
    guards *HP* defeat and leaves ability defeat ("Defeat that unit") alone.  A
    "Defeat that unit" ability never routes through an HP check, so it still works
    against a protected unit.

    Also honours a passive self ``ConstantAbility`` carrying ``Protection(
    from_hp_defeat=True)`` (Chirrut Îmwe SOR_4), but only during the ACTION phase —
    the card protects "during the action phase" and is deliberately defeated during
    REGROUP if still at no remaining HP, which the ACTION-only gate delivers (the
    marker drops when phase becomes REGROUP and the settle-time sweep defeats him)."""
    if any(
        m.target_instance_id == ci.instance_id and m.kind == "prevent_hp_defeat"
        for m in s.modifiers
    ):
        return True
    from swu.abilities.resolver import _card_grants_self_protection
    if s.phase == Phase.ACTION:
        if _card_grants_self_protection(ci.card_def, "hp_defeat", s, ci):
            return True
    # A clause carrying NO phase limit ("While you have the initiative, this unit
    # isn't defeated by having no remaining HP" — Cassian Andor SEC_12) holds through
    # REGROUP too; ``Protection.hp_defeat_any_phase`` opts into that reading and
    # leaves Chirrut's printed action-phase gate as the default.
    elif _card_grants_self_protection(ci.card_def, "hp_defeat_any_phase", s, ci):
        return True
    return False


def _hp_lethal(s: GameState, ci: CardInstance) -> bool:
    """A unit is HP-lethal when its damage meets/exceeds effective HP AND it is not
    protected from no-remaining-HP defeat (LOF_43).  Every state-based / combat /
    direct-damage defeat gate funnels its "damage >= HP" test through here, so the
    LOF_43 prevention is honoured uniformly and defaults inert (no marker present ⇒
    identical to the bare comparison)."""
    return ci.damage >= compute_hp(s, ci) and not _hp_defeat_prevented(s, ci)


# ── Attack pipeline helpers ───────────────────────────────────────────────────

def _bases_cannot_heal(s: GameState) -> bool:
    """True while "Bases can't be healed" is in force — from either source, read at
    every base-heal chokepoint as a global lock on BOTH players' bases:

      * the phase-scoped ``game_memory`` flag set by an effect (Wolffe SOR_160,
        "for this phase"; cleared at the phase rollover), or
      * a standing ``BasesCannotHeal`` marker on any in-play unit (Confederate
        Tri-Fighter TWI_132), which lifts when that unit leaves play.

    The marker scan honours ability suppression like every other in-play marker
    scan; a no-op for boards carrying no such unit."""
    if bool(getattr(s.game_memory, "bases_cannot_heal_this_phase", False)):
        return True
    from swu.abilities.registry import get_abilities, BasesCannotHeal
    for ps in s.players:
        for ci in ps.ground_arena + ps.space_arena:
            if ability_suppressed(s, ci):
                continue
            sc = getattr(ci.card_def, "set_code", None) or ""
            cn = getattr(ci.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            if any(isinstance(spec, BasesCannotHeal)
                   for spec in get_abilities(sc, cn)):
                return True
    return False


def _base_damage_cap(s: GameState, base_owner_id: Optional[str]) -> Optional[int]:
    """The tightest ``BaseDamageCap`` that player has in play, or None.

    "If your base would be dealt more than 4 damage, prevent all but 4 of that
    damage" (At Attin Safety Droid ASH_70) — a passive marker on a UNIT its
    controller has in play, the ``CannotAttackBases`` marker pattern.  Two copies
    do not stack into a smaller number by addition; the CR's independent-application
    reading leaves the strictest cap in force, which is the ``min``."""
    if base_owner_id is None:
        return None
    from swu.abilities.registry import get_abilities, BaseDamageCap
    ps = s.player_by_id(base_owner_id)
    best: Optional[int] = None
    for ci in ps.ground_arena + ps.space_arena:
        if not hasattr(ci.card_def, "set_code"):
            continue
        if ability_suppressed(s, ci):
            continue
        for spec in get_abilities(ci.card_def.set_code or "",
                                  ci.card_def.card_number or ""):
            if isinstance(spec, BaseDamageCap):
                best = spec.amount if best is None else min(best, spec.amount)
    return best


def _base_shield_upgrade_absorbs(s: GameState, base_ci: CardInstance,
                                 amount: int) -> bool:
    """Spend the first ``BaseDamageShieldUpgrade`` on ``base_ci`` that this
    instance of ``amount`` damage qualifies for: log the prevention, defeat the
    upgrade, and draw for its controller.  True if one absorbed the damage."""
    from swu.abilities.registry import get_abilities, BaseDamageShieldUpgrade
    for upg in list(base_ci.attached_upgrades):
        sc = getattr(upg.card_def, "set_code", None) or ""
        cn = getattr(upg.card_def, "card_number", None) or ""
        if not sc or not cn or ability_suppressed(s, upg):
            continue
        spec = next((sp for sp in get_abilities(sc, cn)
                     if isinstance(sp, BaseDamageShieldUpgrade)), None)
        if spec is None or amount < spec.min_amount:
            continue
        s.event_log.append(DamagePrevented(
            unit_instance_id=base_ci.instance_id,
            unit_name=base_ci.card_def.display_name,
            owner_id=base_ci.owner_id,
            amount=amount,
        ))
        from swu.engine.actions.api import _defeat_attached_upgrade
        from swu.engine.actions.zones import _draw_cards
        _defeat_attached_upgrade(s, upg)
        _draw_cards(s, s.player_by_id(base_ci.owner_id), spec.draw)
        return True
    return False


def base_damage_after_prevention(s: GameState, base_ci: CardInstance,
                                 amount: int) -> int:
    """Amount of damage that actually lands on ``base_ci``, consuming a pending
    one-shot base-damage prevention (Close the Shield Gate JTL_74: "Choose a base.
    The next time damage would be dealt to it this phase, prevent that damage").

    ``game_memory.prevent_next_base_damage`` holds the OWNER ids of bases with a
    prevention armed (each player has exactly one base); the entry is spent by the
    first instance of damage that would reach that base and the whole instance is
    prevented, whatever its size or source.  Cleared at the phase rollover, so
    "this phase" needs no expiry bookkeeping.

    Read at every base-damage site — ability damage, indirect damage, a base
    attack, Overwhelm spillover, a leader's base hit and the empty-deck penalty —
    the same shape as ``_bases_cannot_heal``'s read at every base-heal site.  A
    no-op (returns ``amount``) whenever nothing is armed."""
    if amount <= 0:
        return amount
    owner_id = getattr(base_ci, "owner_id", None)
    # "If your base would be dealt more than N damage, prevent all but N of that
    # damage" (At Attin Safety Droid ASH_70) — a per-instance CAP its controller
    # has in play, read at this same single helper so it covers every base-damage
    # site at once.  Applied BEFORE the one-shot prevention: a capped instance is
    # still an instance, so a pending Close the Shield Gate JTL_74 charge should
    # eat the (capped) hit rather than the cap silently spending it.
    cap = _base_damage_cap(s, owner_id)
    if cap is not None and amount > cap:
        s.event_log.append(DamagePrevented(
            unit_instance_id=base_ci.instance_id,
            unit_name=base_ci.card_def.display_name,
            owner_id=owner_id,
            amount=amount - cap,
        ))
        amount = cap
        if amount <= 0:
            return 0
    # "If attached base would be dealt 5 or more damage, prevent that damage.  If
    # you do, defeat this upgrade and draw a card" (Alliance Shield Generator HMW_81)
    # — a marker on a Fortify upgrade ON this base.
    if base_ci.attached_upgrades and _base_shield_upgrade_absorbs(s, base_ci, amount):
        return 0
    armed = getattr(s.game_memory, "prevent_next_base_damage", None)
    if not armed:
        return amount
    if owner_id not in armed:
        return amount
    armed.discard(owner_id)
    s.event_log.append(DamagePrevented(
        unit_instance_id=base_ci.instance_id,
        unit_name=base_ci.card_def.display_name,
        owner_id=owner_id,
        amount=amount,
    ))
    return 0


def _dealer_player(s: GameState, target_player_id: str, combat: bool,
                   dealer: str | None) -> str | None:
    """The PLAYER dealing a damage instance (see ``note_damage_dealt``)."""
    if combat:
        return next((p.player_id for p in s.players
                     if p.player_id != target_player_id), None)
    if dealer:
        if any(p.player_id == dealer for p in s.players):
            return dealer
        res = s.find_instance(dealer)
        if res is not None:
            return res[0].player_id
    from swu.abilities.resolver import _noncombat_dealer_stack
    return _noncombat_dealer_stack[-1] if _noncombat_dealer_stack else None


_ABILITY_DAMAGE_BONUS_KEYS: list = []


def _ability_damage_bonus(s: GameState, target_player_id: str,
                          dealer: str | None) -> int:
    """Extra damage for one NON-COMBAT instance from ``AbilityDamageBonus``
    markers (Ty Yorrick HMW_185) on units the dealing player controls — counted
    only when the target belongs to an opponent of that player (the "may" taken
    when it helps).  A cached registry index keeps every other board at one empty
    check."""
    if not _ABILITY_DAMAGE_BONUS_KEYS:
        from swu.abilities.registry import _REGISTRY, AbilityDamageBonus
        _ABILITY_DAMAGE_BONUS_KEYS.append(frozenset(
            key for key, specs in _REGISTRY.items()
            if any(isinstance(sp, AbilityDamageBonus) for sp in specs)))
    keys = _ABILITY_DAMAGE_BONUS_KEYS[0]
    if not keys:
        return 0
    dealer_player = _dealer_player(s, target_player_id, False, dealer)
    if dealer_player is None or dealer_player == target_player_id:
        return 0
    from swu.abilities.registry import get_abilities, AbilityDamageBonus
    total = 0
    ps = s.player_by_id(dealer_player)
    for ci in ps.ground_arena + ps.space_arena:
        cd = ci.card_def
        key = (getattr(cd, "set_code", None) or "", getattr(cd, "card_number", None))
        if key not in keys or getattr(ci, "abilities_suppressed", False):
            continue
        total += sum(sp.amount for sp in get_abilities(*key)
                     if isinstance(sp, AbilityDamageBonus))
    return total


def note_damage_dealt(
    s: GameState,
    target_ci: CardInstance,
    target_player_id: str,
    amount: int,
    *,
    combat: bool = False,
    dealer: str | None = None,
    dealer_card: str | None = None,
) -> None:
    """Queue one damage instance that actually LANDED on a unit or base, for the
    settle-point ``WhenDamageDealt`` observer drain (``_fire_damage_observers``).

    ``dealer_card`` is the instance id of the CARD that dealt it when known (the
    attacker for combat, the ability's source for ability damage to a base), so
    ``WhenDamageDealt(dealer="friendly_unit")`` can tell a unit from an event (The
    Ghost IC27_122).

    ``amount`` is what landed after every prevention, so a Shield or a fully
    prevented hit records nothing.  The DEALING PLAYER is resolved here:

    * combat damage is always dealt by the target controller's opponent (the
      attacker hits the defender, the defender hits back; a Maul SHD_90 redirect
      still takes the defender's damage);
    * otherwise ``dealer`` names a player, or a card whose controller dealt it
      (callers pass either today);
    * failing both, the resolver's current effect controller
      (``_noncombat_dealer_stack``), the WhenDealNonCombatDamage fallback.

    Unknown → ``None`` (an observer reading "when YOU deal" then never matches).
    A bare list append, so a board with no such observer pays almost nothing; the
    drain clears the queue without firing when no observer card is on the board."""
    if amount <= 0:
        return
    dealer_player = _dealer_player(s, target_player_id, combat, dealer)
    from swu.cards.models import Base
    s.game_memory.damage_events.append({
        "target_id": target_ci.instance_id,
        "target_player": target_player_id,
        "is_base": isinstance(target_ci.card_def, Base),
        "amount": int(amount),
        "dealer_player": dealer_player,
        "dealer_card": dealer_card,
        "combat": bool(combat),
    })


def _deal_damage_with_shield(
    s: GameState,
    owner_ps: PlayerState,
    unit_ci: CardInstance,
    amount: int,
    source_name: str | None = None,
    is_combat: bool = False,
    dealer_id: str | None = None,
    dealer_source_id: str | None = None,
) -> int:
    """Apply ``amount`` damage to unit_ci, intercepted by one Shield if present.

    If a Shield token is on unit_ci, defeat the Shield and prevent ALL damage
    from this instance.  Returns the actual damage dealt (0 if shielded).

    ``source_name`` attributes ability damage to its source card in the log;
    combat callers leave it None (the attacker is clear from AttackDeclared).
    ``is_combat`` is set by the combat pipelines only, so a prevention that reads
    "prevent all COMBAT damage" (Aayla Secura TWI_96) can tell the two apart.

    ``dealer_source_id`` names the CARD dealing this instance (the ability's
    source, or the combat attacker/defender).  It is what makes "Damage dealt by
    friendly Underworld cards is unpreventable" (Gorian Shard's Corsair ASH_196)
    expressible: a matching dealer skips every prevention below AND the Shield.
    """
    if amount <= 0:
        return 0
    # UNPREVENTABLE damage (ASH_196) — checked first, so nothing below is even
    # consumed: not the one-shot combat replacement, not a once-per-phase
    # prevention, not a Shield.  Amplification still applies (it increases the
    # instance rather than preventing it).
    if _damage_is_unpreventable(s, dealer_source_id):
        amount += _damage_amplification_on(s, unit_ci, dealer_id, amount)
        if not is_combat:
            amount += _ability_damage_bonus(s, owner_ps.player_id,
                                            dealer_id or dealer_source_id)
        unit_ci.damage += amount
        note_damage_dealt(s, unit_ci, owner_ps.player_id, amount, combat=is_combat,
                          dealer=dealer_id or dealer_source_id)
        s.event_log.append(DamageDealt(
            target_instance_id=unit_ci.instance_id,
            target_name=unit_ci.card_def.display_name,
            owner_id=owner_ps.player_id,
            amount=amount,
            is_base=False,
            source_name=source_name,
        ))
        return amount
    # Queen Amidala SEC_101 combat-damage replacement: the combat_damage_prevention
    # decision already defeated a friendly trait-sharing unit and armed this one-shot
    # flag.  Drop this one combat-damage instance and disarm (before the shield check
    # — the decision was only offered when no shield was present, and the sacrifice
    # was already paid, so this replaces the whole instance).
    if unit_ci.prevent_next_combat_damage:
        unit_ci.prevent_next_combat_damage = False
        s.event_log.append(CombatDamagePrevented(
            unit_instance_id=unit_ci.instance_id,
            unit_name=unit_ci.card_def.display_name,
            owner_id=owner_ps.player_id,
            amount=amount,
        ))
        return 0
    # Boba Fett's Armor SHD_224: an attached DamagePrevention upgrade prevents N of
    # EVERY instance of damage dealt to its host.  A reduction, not a replacement —
    # applied before the Shield check, so an instance reduced to nothing leaves no
    # damage for the Shield to prevent and the Shield survives.
    # Vigil SEC_50's dual: an instance dealt to a unit carrying DamageAmplification
    # is increased BEFORE prevention/shields, so "that much damage plus 1" is what
    # the rest of the pipeline sees.
    amount += _damage_amplification_on(s, unit_ci, dealer_id, amount)
    # Ty Yorrick HMW_185's dealer-side "+1" on friendly ABILITY damage.
    if not is_combat:
        amount += _ability_damage_bonus(s, owner_ps.player_id,
                                        dealer_id or dealer_source_id)
    # "The first time this unit would take damage each phase, prevent that damage"
    # (Umbaran Mobile Cannon SEC_67) — a whole-instance, once-per-phase prevention,
    # so it is consumed here rather than summed into the per-instance reduction.
    # Ahead of the Shield check for the same reason as the markers below: an
    # instance fully prevented leaves nothing for the Shield to eat.
    if _consume_first_damage_prevention(s, unit_ci):
        return 0
    # "If damage would be dealt to another friendly unit, you may defeat a Shield
    # token on this unit.  If you do, prevent that damage" (The Mandalorian ASH_62)
    # — another whole-instance prevention, priced in a Shield on the aura's source.
    if _consume_shield_aura_prevention(s, unit_ci, is_combat, dealer_id):
        return 0
    prevented = _damage_prevention_on(s, unit_ci, is_combat, dealer_id)
    # An APPLIED prevention (a ``damage_prevention`` Modifier on the unit) reduces
    # every instance the same way the attached-upgrade marker does, but is landed by
    # an effect for a duration: "prevent 1 of that damage" for this phase (Finn
    # TWI_53) or "prevent ALL combat damage" for this attack (Aayla Secura TWI_96,
    # ``all`` + ``combat_only``).  Multiple preventions stack, an ``all`` wins.
    spent_once: list = []
    for mod in s.modifiers:
        if mod.kind != "damage_prevention" or mod.target_instance_id != unit_ci.instance_id:
            continue
        if mod.value.get("combat_only") and not is_combat:
            continue
        if mod.value.get("all"):
            prevented = amount
            break
        prevented += int(mod.value.get("amount", 0) or 0)
        # "The NEXT time it would be dealt damage this phase, prevent 2 of that
        # damage" (Shien Flurry LOF_220) — a one-shot prevention, dropped here as
        # soon as it applies to an instance, rather than reducing every instance for
        # the duration (Finn TWI_53's standing shape).
        if mod.value.get("once"):
            spent_once.append(mod.modifier_id)
    for _mid in spent_once:
        s.modifiers = [m for m in s.modifiers if m.modifier_id != _mid]
    if prevented:
        amount = max(0, amount - prevented)
        if amount <= 0:
            return 0
    if shields_on(unit_ci) > 0:
        defeat_shield(s, unit_ci)
        return 0  # all damage prevented
    unit_ci.damage += amount
    if amount > 0:
        # "Ready a unit that was damaged this phase" (Galvanized Leap ASH_188) —
        # the exact mirror of ``note_unit_healed``'s ledger, recorded only for
        # damage really dealt (everything above this line prevented it).
        s.game_memory.units_damaged_this_phase.add(unit_ci.instance_id)
        note_damage_dealt(s, unit_ci, owner_ps.player_id, amount, combat=is_combat,
                          dealer=dealer_id or dealer_source_id)
    s.event_log.append(DamageDealt(
        target_instance_id=unit_ci.instance_id,
        target_name=unit_ci.card_def.display_name,
        owner_id=owner_ps.player_id,
        amount=amount,
        is_base=False,
        source_name=source_name,
    ))
    return amount


# ── Internal helpers ──────────────────────────────────────────────────────────

def _dp_applies(state: GameState, spec, protected_ci: CardInstance,
                marker_owner_id: str, is_combat: bool, dealer_id) -> bool:
    """Whether one ``DamagePrevention`` marker covers THIS instance of damage.

    ``ability_only`` drops combat damage (Cassian SEC_42's rules insert: "Combat
    damage is not a card ability"); ``enemy_only`` requires the dealing card to be
    controlled by an opponent of the marker's controller.  An ``enemy_only`` marker
    with no identifiable dealer does not apply — the conservative reading, and the
    combat path (where ``dealer_id`` is never threaded) is already excluded by
    ``ability_only`` on every card that uses it today."""
    if spec.ability_only and is_combat:
        return False
    if spec.enemy_only:
        if not dealer_id:
            return False
        res = state.find_instance(dealer_id)
        if res is None or res[0].player_id == marker_owner_id:
            return False
    return True


def _consume_first_damage_prevention(s: GameState, unit_ci: CardInstance) -> bool:
    """True (and records the spend) if this is the FIRST damage instance ``unit_ci``
    would take this phase and its card carries ``DamagePrevention(first_each_phase)``
    (Umbaran Mobile Cannon SEC_67).

    The ledger `game_memory.first_damage_prevented_this_phase` is phase-cleared, so
    the prevention refreshes every phase.  The cheap set membership is tested first,
    then the spec scan — so a board with no such card pays a single set lookup per
    damage instance."""
    from swu.abilities.registry import get_abilities, DamagePrevention
    if unit_ci.instance_id in s.game_memory.first_damage_prevented_this_phase:
        return False
    if unit_ci.abilities_suppressed:
        return False
    sc = getattr(unit_ci.card_def, "set_code", None) or ""
    cn = getattr(unit_ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    if not any(isinstance(sp, DamagePrevention) and sp.first_each_phase
               for sp in get_abilities(sc, cn)):
        return False
    s.game_memory.first_damage_prevented_this_phase.add(unit_ci.instance_id)
    return True


def _consume_shield_aura_prevention(s: GameState, unit_ci: CardInstance,
                                    is_combat: bool = False, dealer_id=None) -> bool:
    """True (and spends the Shield) if some in-play unit carries a
    ``DamagePrevention(aura_target=…, consume_shield_on_source=True)`` matching
    ``unit_ci``, and that SOURCE holds a Shield token to pay with — "If damage would
    be dealt to another friendly unit, you may defeat a Shield token on this unit.
    If you do, prevent that damage" (The Mandalorian ASH_62).

    A whole-instance prevention (the ``first_each_phase`` shape, not an ``amount``
    reduction), consumed at the single unit-damage chokepoint.  The board walk runs
    only after the cheap registry-index test, so an ordinary board pays one set
    lookup per damage instance.  DOCUMENTED DEVIATION: the printed "you may" is
    taken automatically whenever a Shield is available — the engine's own Shield
    token likewise prevents without asking, and pushing a decision from inside the
    damage step would be replacement-effect machinery."""
    from swu.abilities.registry import get_abilities, DamagePrevention
    from swu.abilities.resolver import _spec_matches_ci
    from swu.engine.tokens import defeat_shield
    if not _shield_aura_prevention_keys():
        return False
    for ps in s.players:
        for src in ps.ground_arena + ps.space_arena:
            key = (getattr(src.card_def, "set_code", None) or "",
                   getattr(src.card_def, "card_number", None) or "")
            if key not in _shield_aura_prevention_keys():
                continue
            if src.abilities_suppressed:
                continue
            for spec in get_abilities(*key):
                if (not isinstance(spec, DamagePrevention)
                        or spec.aura_target is None
                        or not spec.consume_shield_on_source):
                    continue
                if not _dp_applies(s, spec, unit_ci, ps.player_id,
                                   is_combat, dealer_id):
                    continue
                if not _spec_matches_ci(spec.aura_target, unit_ci, src, s, {}):
                    continue
                if defeat_shield(s, src):
                    return True
    return False


_SHIELD_AURA_PREVENTION_KEYS: list = []


def _shield_aura_prevention_keys() -> frozenset:
    """Cached (set_code, card_number) index of the cards carrying a shield-priced
    prevention aura — the ``keywords._keyword_revoke_aura_keys`` /
    ``_suppress_leader_keys`` trick, mandatory on the damage chokepoint."""
    if not _SHIELD_AURA_PREVENTION_KEYS:
        from swu.abilities.registry import _REGISTRY, DamagePrevention
        keys = {key for key, specs in _REGISTRY.items()
                if any(isinstance(sp, DamagePrevention)
                       and sp.consume_shield_on_source for sp in specs)}
        _SHIELD_AURA_PREVENTION_KEYS.append(frozenset(keys))
    return _SHIELD_AURA_PREVENTION_KEYS[0]


_UNPREVENTABLE_DAMAGE_KEYS: list = []


def _unpreventable_damage_keys() -> frozenset:
    """Cached (set_code, card_number) index of the cards carrying an
    ``UnpreventableDamage`` marker — the ``_shield_aura_prevention_keys`` trick,
    mandatory on the damage chokepoint."""
    if not _UNPREVENTABLE_DAMAGE_KEYS:
        from swu.abilities.registry import _REGISTRY, UnpreventableDamage
        keys = {key for key, specs in _REGISTRY.items()
                if any(isinstance(sp, UnpreventableDamage) for sp in specs)}
        _UNPREVENTABLE_DAMAGE_KEYS.append(frozenset(keys))
    return _UNPREVENTABLE_DAMAGE_KEYS[0]


def _damage_is_unpreventable(s: GameState, dealer_source_id: str | None) -> bool:
    """True if the card dealing this instance is named by some in-play
    ``UnpreventableDamage`` marker — "Damage dealt by friendly Underworld cards
    is unpreventable" (Gorian Shard's Corsair ASH_196).

    The dealer is recovered with ``find_instance`` (which reaches the discard, so
    a spent Underworld EVENT counts as a "card"), and matched on its EFFECTIVE
    traits.  ``controller`` is measured against the marker's own controller.  No
    dealer id ⇒ False, which is the conservative reading (the damage keeps every
    prevention it would otherwise have had)."""
    if not dealer_source_id or not _unpreventable_damage_keys():
        return False
    from swu.abilities.registry import get_abilities, UnpreventableDamage
    from swu.engine.traits import has_trait
    res = s.find_instance(dealer_source_id)
    if res is None:
        return False
    dealer_ps, dealer_ci = res
    for ps in s.players:
        for src in ps.ground_arena + ps.space_arena:
            key = (getattr(src.card_def, "set_code", None) or "",
                   getattr(src.card_def, "card_number", None) or "")
            if key not in _unpreventable_damage_keys():
                continue
            if src.abilities_suppressed:
                continue
            for spec in get_abilities(*key):
                if not isinstance(spec, UnpreventableDamage):
                    continue
                same_side = dealer_ps.player_id == ps.player_id
                if spec.controller == "friendly" and not same_side:
                    continue
                if spec.controller == "enemy" and same_side:
                    continue
                if all(has_trait(s, dealer_ci, t) for t in spec.traits):
                    return True
    return False


def _damage_prevention_on(state: GameState, unit_ci: CardInstance,
                          is_combat: bool = False, dealer_id=None) -> int:
    """Total damage prevented per instance for ``unit_ci`` by the three
    ``DamagePrevention`` shapes: an attached UPGRADE (Boba Fett's Armor SHD_224), the
    unit's OWN ``on_self`` marker (Cassian Andor SEC_42), and an ``aura_target``
    marker on some other in-play unit (Vigil SEC_50).

    A marker carrying ``host_named`` applies only while the host's card name matches
    (the armor does nothing on a host who isn't Boba Fett).  Multiple markers stack.
    Read only at ``_deal_damage_with_shield``; 0 for the overwhelming majority of
    units.  Mirrors the ``_cannot_attack_bases`` marker scan."""
    from swu.abilities.registry import get_abilities, DamagePrevention
    total = 0
    host_name = getattr(unit_ci.card_def, "name", None)
    protected_ps = state.find_instance(unit_ci.instance_id)
    protected_owner = (protected_ps[0].player_id if protected_ps is not None
                       else unit_ci.owner_id)

    for upg in unit_ci.attached_upgrades:
        sc = getattr(upg.card_def, "set_code", None) or ""
        cn = getattr(upg.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, DamagePrevention) and not spec.on_self \
                    and spec.aura_target is None:
                if spec.host_named is not None and host_name != spec.host_named:
                    continue
                if _dp_applies(state, spec, unit_ci, protected_owner,
                               is_combat, dealer_id):
                    total += spec.amount

    # The unit's OWN marker ("… would deal damage to THIS unit").
    sc = getattr(unit_ci.card_def, "set_code", None) or ""
    cn = getattr(unit_ci.card_def, "card_number", None) or ""
    if sc and cn and not unit_ci.abilities_suppressed:
        for spec in get_abilities(sc, cn):
            # ``first_each_phase`` is a whole-instance one-shot consumed by
            # ``_consume_first_damage_prevention``, never a per-instance reduction.
            if (isinstance(spec, DamagePrevention) and spec.on_self
                    and not spec.first_each_phase):
                if _dp_applies(state, spec, unit_ci, protected_owner,
                               is_combat, dealer_id):
                    total += spec.amount

    # An AURA marker on another in-play unit ("… would deal damage to another
    # friendly unit").  Skipped entirely unless some in-play unit carries one, so
    # the ordinary board pays only the arena walk.
    from swu.abilities.resolver import _spec_matches_ci
    for ps in state.players:
        for src in ps.ground_arena + ps.space_arena:
            if src.abilities_suppressed:
                continue
            ssc = getattr(src.card_def, "set_code", None) or ""
            scn = getattr(src.card_def, "card_number", None) or ""
            if not ssc or not scn:
                continue
            for spec in get_abilities(ssc, scn):
                if not isinstance(spec, DamagePrevention) or spec.aura_target is None:
                    continue
                if spec.consume_shield_on_source:
                    continue    # a whole-instance prevention consumed elsewhere
                if not _dp_applies(state, spec, unit_ci, ps.player_id,
                                   is_combat, dealer_id):
                    continue
                if _spec_matches_ci(spec.aura_target, unit_ci, src, state, {}):
                    total += spec.amount
    return total


def _damage_amplification_on(state: GameState, unit_ci: CardInstance,
                             dealer_id=None, amount: int = 0) -> int:
    """Extra damage added to each instance dealt to ``unit_ci`` by a
    ``DamageAmplification`` marker on its own card (Vigil SEC_50: "If damage would be
    dealt to this unit by another card, deal that much damage plus 1 instead") or on
    an ATTACHED UPGRADE ("If attached unit would take damage, it takes twice as much
    damage instead" — Deadly Vulnerability ASH_150).

    ``by_another_card`` excludes self-inflicted damage (a dealer that IS this unit).
    ``multiplier`` scales the incoming ``amount`` — expressed as the EXTRA on top, so
    an additive marker and a multiplying one compose in one return value.  Read only
    at ``_deal_damage_with_shield``, right after prevention."""
    from swu.abilities.registry import get_abilities, DamageAmplification
    if unit_ci.abilities_suppressed:
        return 0
    total = 0
    for holder in (unit_ci, *unit_ci.attached_upgrades):
        sc = getattr(holder.card_def, "set_code", None) or ""
        cn = getattr(holder.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if not isinstance(spec, DamageAmplification):
                continue
            if spec.by_another_card and dealer_id == unit_ci.instance_id:
                continue
            mult = int(getattr(spec, "multiplier", 1) or 1)
            if mult > 1:
                total += max(0, int(amount)) * (mult - 1)
            total += spec.amount
    return total
