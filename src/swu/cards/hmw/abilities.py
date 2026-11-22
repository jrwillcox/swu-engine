"""HMW (Homeworlds) card ability registrations.

Imported for its side effects (the ``@card_ability`` decorators populate the
registry).  Encoded group by group via ``/encode-next``; the plan lives in
``encoding/hmw-set/``.

⚠️ **TOKEN COLLISIONS**: HMW prints its tokens at LOW numbers, and each shares its
``(set, number)`` registry key with a LEADER of the same number:

* ``HMW_1`` Asajj Ventress (Leader) / Shield token UPGRADE
* ``HMW_2`` Maz Kanata (Leader) / **Weakness** token UPGRADE (new token type)
* ``HMW_3`` Doctor Hemlock (Leader) / **Beast** token UNIT (new token type)
* ``HMW_4`` Grand Moff Tarkin (Leader) / Beast token UNIT
* ``HMW_5`` Jar Jar Binks (Leader) / Beast token UNIT

Register those leaders ONLY from spec kinds a token can never reach (see the
same warning in ``swu/cards/ts26/abilities.py``):
``ActivatedAbility(undeployed_only=True)``, ``TriggerAbility(WhenDeployed())`` and
``TriggerAbility(deployed_only=True)``.  A ``ConstantAbility``, a
``GrantedAbility`` or a passive marker would NOT be safe there — unless the marker
carries its own leader guard (``IgnoreAspectPenaltyForPlays(leader_only=True)``,
Grand Moff Tarkin HMW_4).

**Fortify** (most of ``hmw-set:01``): the keyword itself is engine-side (see
``docs/dev/engine_seams.md`` § Fortify).  A Fortify upgrade's abilities come in
three shapes here:

* "Attached base gains: 'When …'" = ``GrantedAbility(TriggerAbility)``, resolving
  from the BASE (``resolver._fortify_upgrade_triggers``), so ``fixed=SELF`` is the
  base and "friendly" reads its owner.
* "Attached base gains: 'Action …'" = ``GrantedAbility(ActivatedAbility)``.
* "Attached base gains: 'Friendly units gain …/get …'" = a
  ``ConstantAbility(via_host=True)`` — the Figure of Unity SEC_104 upgrade-borne
  aura, whose scans now also walk the base's attached upgrades.
* A trigger printed on the upgrade itself ("You may defeat this upgrade …") is a
  plain ``TriggerAbility``, resolving from the UPGRADE.
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ActivatedAbility, ConstantAbility, GrantedAbility,
    WhenPlayed, WhenUnitDefeated, WhenYouPlayCard, WhenYouPlayOrCreateUnit,
    PhaseStartTrigger,
    DealDamage, Heal, DrawCards, ExhaustCard, ModifyStats, CustomEffect,
    KeywordGrant, StatBonus,
    IgnoreAspectPenaltyForPlays, BaseDamageShieldUpgrade,
    DefeatSelf, DiscardCardCost,
    ConditionCheck, Condition, Duration,
    TargetSpec, SELF,
)


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:01 — Fortify cards' residual text
# ══════════════════════════════════════════════════════════════════════════════


def _tarkin_victim_base(state, source_ci):
    """The enemy base with 10 or less remaining HP, or None.  "A base" could name
    either base, but defeating your own base loses the game, so only an
    opponent's base is ever a sane pick (two-player)."""
    for ps in state.players:
        if ps.player_id == source_ci.owner_id:
            continue
        base = ps.base_instance
        if base is None:
            continue
        hp = getattr(base.card_def, "hp", None) or 0
        if hp - (base.damage or 0) <= 10:
            return base
    return None


def _tarkin_has_victim(state, source_ci, event_ctx):
    return _tarkin_victim_base(state, source_ci) is not None


def _tarkin_defeat_base(state, source_ci, target_id, event_ctx):
    """Defeat the base: mark it lethally damaged — the Final Showdown SHD_208
    shape — which ``is_eliminated`` / ``_check_game_over`` pick up.  Not damage,
    so no prevention or damage observer applies."""
    from swu.engine.actions.flow import _check_game_over
    base = _tarkin_victim_base(state, source_ci)
    if base is None:
        return state
    base.damage = getattr(base.card_def, "hp", None) or base.damage
    _check_game_over(state)
    return state


@card_ability("HMW", "4")
def _grand_moff_tarkin_hmw():
    """HMW_4 — Grand Moff Tarkin (Leader, Imperial Official, 2/12).

    Both sides: "Ignore the aspect penalties on upgrades with Fortify you play."
    Deployed: "When the regroup phase starts: You may defeat a base with 10 or less
    remaining HP."  Epic Action deploy is the generic leader machinery.

    ⚠ HMW_4 is also the Beast token UNIT's number, so the waiver marker carries
    ``leader_only`` (a Beast never waives anything) and the regroup trigger is
    ``deployed_only`` (collected only for a deployed LEADER).  The upstream
    "Fortify" tag on Tarkin is harmless: ``_is_fortify`` reads Upgrades only."""
    return [
        IgnoreAspectPenaltyForPlays(card_type="upgrade", keyword="Fortify",
                                    leader_only=True),
        TriggerAbility(
            trigger=PhaseStartTrigger("regroup"),
            effects=[CustomEffect(fn=_tarkin_defeat_base,
                                  available_fn=_tarkin_has_victim)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _bacta_tank_recur(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=1, own_only=True, disposition="top",
        eligible=lambda cd: isinstance(cd, Unit)
        and "Vehicle" not in (getattr(cd, "traits", None) or ()))
    return state


@card_ability("HMW", "37")
def _bacta_tank():
    """HMW_37 — Bacta Tank (Upgrade, Fortification, 1; Fortify): "When Played: Heal
    up to 3 damage from a non-Vehicle unit.  Action [defeat this upgrade]: Put a
    non-Vehicle unit from your discard pile on top of your deck."

    The Action is printed on the upgrade; modelled as a ``GrantedAbility`` so the
    base-host enumeration offers it (its effect reads only the controller).  The
    pick reuses ``bottom_from_discard`` with the new ``disposition="top"``; like
    every user of that kind it is "up to", a documented simplification.  Gated on a
    non-empty discard (no unit-only atom exists)."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[
            Heal(3, TargetSpec(controller="any", kind="unit",
                               predicates=("non_vehicle",)))]),
        GrantedAbility(ActivatedAbility(
            costs=[DefeatSelf()],
            effects=[CustomEffect(fn=_bacta_tank_recur)],
            condition=ConditionCheck(Condition.CONTROLLER_DISCARD_SIZE_MIN, param=1),
        )),
    ]


@card_ability("HMW", "70")
def _dark_sanctum():
    """HMW_70 — Dark Sanctum (Upgrade, Fortification, 3; Fortify): "Attached base
    gains: 'When the regroup phase starts: Draw a card and deal 2 damage to this
    base.'" """
    return GrantedAbility(TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[DrawCards(1),
                 DealDamage(2, TargetSpec(controller="friendly", kind="base",
                                          fixed=SELF))],
    ))


@card_ability("HMW", "81")
def _alliance_shield_generator():
    """HMW_81 — Alliance Shield Generator (Upgrade, Fortification, 2; Fortify): "If
    attached base would be dealt 5 or more damage, prevent that damage.  If you do,
    defeat this upgrade and draw a card."

    The new ``BaseDamageShieldUpgrade`` marker, read at the single base-damage
    chokepoint ``base_damage_after_prevention`` beside the At Attin Safety Droid
    ASH_70 cap — the existing prevention seam, not a replacement-effect system."""
    return BaseDamageShieldUpgrade(min_amount=5, draw=1)


def _carbonite_freeze(state, source_ci, target_id, event_ctx):
    """"It doesn't ready during the next regroup phase."  Actions happen in the
    action phase, so the next regroup is this round's: ``cannot_ready_this_round``
    (No Good to Me Dead SOR_186), cleared at the round rollover.  That flag also
    blocks an effect ready for the rest of the round — a slight over-reach of the
    printed text, documented."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    res[1].cannot_ready_this_round = True
    return state


@card_ability("HMW", "95")
def _carbonite_chamber():
    """HMW_95 — Carbonite Chamber (Upgrade, Fortification, 1; Fortify): "Action
    [defeat this upgrade]: Choose a non-Vehicle unit.  It doesn't ready during the
    next regroup phase." """
    return GrantedAbility(ActivatedAbility(
        costs=[DefeatSelf()],
        effects=[CustomEffect(fn=_carbonite_freeze,
                              target=TargetSpec(controller="any", kind="unit",
                                                predicates=("non_vehicle",)))],
    ))


@card_ability("HMW", "112")
def _military_academy():
    """HMW_112 — Military Academy (Upgrade, Fortification, 1; Fortify): "Attached
    base gains: 'Friendly units gain Overwhelm.'"  A base-hosted ``via_host``
    aura (the printed Overwhelm tag is upstream noise: it would confer on the base,
    which never attacks)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit"),
        effects=[KeywordGrant("Overwhelm")],
        via_host=True,
    )


@card_ability("HMW", "113")
def _sinister_war_memorial():
    """HMW_113 — Sinister War Memorial (Upgrade, Fortification, 2; Fortify):
    "Attached base gains: 'When a friendly unit is defeated: Heal 1 damage from
    this base.'" """
    return GrantedAbility(TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(controller="friendly", kind="unit")),
        effects=[Heal(1, TargetSpec(controller="friendly", kind="base", fixed=SELF))],
    ))


@card_ability("HMW", "126")
def _verdant_fortress():
    """HMW_126 — Verdant Fortress (Upgrade, Fortification, 2; Fortify): "Attached
    base gains: 'Friendly units gain Raid 1.'"  A base-hosted ``via_host`` aura;
    Raid is read by ``compute_power(is_attacking=True)`` via ``keyword_value``."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit"),
        effects=[KeywordGrant("Raid", 1)],
        via_host=True,
    )


def _beast_lair_pitch(state, source_ci, target_id, event_ctx):
    """Discard the first hand card and create a Beast token — one effect, so the
    "If you do" cannot split (Bix Caleen LAW_236's shape, first-card convention)."""
    from swu.engine.actions import (
        _create_token_units, note_hand_or_deck_discard, record_hand_discard)
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    card.face_down = False
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    record_hand_discard(state, ps.player_id)
    _create_token_units(state, ps, "Beast", 1)
    return state


@card_ability("HMW", "147")
def _beast_lair():
    """HMW_147 — Beast Lair (Upgrade, Fortification, 2; Fortify): "Attached base
    gains: 'When the action phase starts: You may discard a card from your hand.
    If you do, create a Beast token.'"

    The Beast token is a vanilla 3/3 ground ``TokenUnit`` row in the DB, so
    ``_create_token_units("Beast")`` needs no new machinery (the Clone Trooper
    path).  Gated on a non-empty hand."""
    return GrantedAbility(TriggerAbility(
        trigger=PhaseStartTrigger("action"),
        effects=[CustomEffect(fn=_beast_lair_pitch)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1),
    ))


def _noxious_reveal(state, source_ci, target_id, event_ctx):
    """Reveal the top card (it stays on top); arm the damage only if it is
    Aggression — BT-1 LAW_173's "record then gate" shape, minus the mill."""
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    top = ps.deck[0]
    aspects = {a.name for a in (getattr(top.card_def, "aspects", None) or ())}
    if "Aggression" in aspects:
        event_ctx["prior_target_id"] = top.instance_id
    return state


@card_ability("HMW", "160")
def _noxious_refinery():
    """HMW_160 — Noxious Refinery (Upgrade, Fortification, 4; Fortify): "Attached
    base gains: 'When the regroup phase starts: Reveal the top card of your deck.
    If it's Aggression, deal 1 damage to an enemy unit.'" """
    return GrantedAbility(TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[
            CustomEffect(fn=_noxious_reveal),
            DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                     predicates=("requires_prior_target",))),
        ],
    ))


def _entered_ground_unit_in_play(state, source_ci, event_ctx) -> bool:
    from swu.engine.state import Zone
    res = state.find_instance(event_ctx.get("entered_unit_id") or "")
    return res is not None and res[1].zone == Zone.GROUND_ARENA


def _trap_field_spring(state, source_ci, target_id, event_ctx):
    """Defeat this upgrade, then deal 3 to the unit that entered — one effect
    (the Bright Hope SOR_99 "if you do" binding)."""
    from swu.abilities.resolver import _apply_deal_damage, _apply_defeat_unit
    entered = event_ctx.get("entered_unit_id")
    if not _entered_ground_unit_in_play(state, source_ci, event_ctx):
        return state
    if state.find_instance(source_ci.instance_id) is None:
        return state  # already gone: the cost can't be paid
    _apply_defeat_unit(state, source_ci.instance_id)
    _apply_deal_damage(state, entered, 3, source_ci.card_def.display_name)
    return state


@card_ability("HMW", "171")
def _trap_field():
    """HMW_171 — Trap Field (Upgrade, Fortification, 2; Fortify): "When a non-leader
    ground unit enters play (including token units): You may defeat this upgrade.
    If you do, deal 3 damage to that unit."

    The unit-entry observer (``_put_unit_in_play`` is the one chokepoint every
    play route AND token creation passes through), widened with ``any_player`` and
    a ``filter``.  Printed on the upgrade, so it resolves from the UPGRADE."""
    return TriggerAbility(
        trigger=WhenYouPlayOrCreateUnit(
            any_player=True,
            filter=TargetSpec(controller="any", kind="unit", arena="ground",
                              predicates=("non_leader",))),
        effects=[CustomEffect(fn=_trap_field_spring,
                              available_fn=_entered_ground_unit_in_play)],
        optional=True,
    )


@card_ability("HMW", "172")
def _heavy_ion_cannon():
    """HMW_172 — Heavy Ion Cannon (Upgrade, Fortification, 3; Fortify): "When
    Played: Draw a card.  Attached base gains: 'Action [discard a card from your
    hand]: Deal 2 damage to a unit.  Use this ability only once each phase.'"

    Actions are taken only in the action phase, so "once each phase" is
    ``once_per_round``."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        GrantedAbility(ActivatedAbility(
            costs=[DiscardCardCost()],
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            once_per_round=True,
        )),
    ]


def _intelligence_agency_peek_hand(state, source_ci, target_id, event_ctx):
    from swu.cards.ash.abilities import _remnant_lookouts_peek_hand
    return _remnant_lookouts_peek_hand(state, source_ci, target_id, event_ctx)


@card_ability("HMW", "205")
def _intelligence_agency():
    """HMW_205 — Intelligence Agency (Upgrade, Fortification, 1; Fortify):
    "Attached base gains: 'You may look at the top card of your deck at any time.'
    When Played: Look at an opponent's hand.  You may discard a card from it.  If
    you do, they draw a card."

    The When Played is Remnant Lookouts ASH_220's text verbatim, so it reuses that
    card's adapter.  The "look at your top card at any time" clause is pure hidden
    information with no rules effect; it is not modelled (no UI surface yet)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_intelligence_agency_peek_hand)])


@card_ability("HMW", "206")
def _the_tarkin_doctrine():
    """HMW_206 — The Tarkin Doctrine (Upgrade, Law, 1; Fortify): "Attached base
    gains: 'When you play a Fortification upgrade: Exhaust an enemy unit.'  When
    Played: If you control Grand Moff Tarkin, give an enemy unit –3/–0 for this
    phase." """
    return [
        GrantedAbility(TriggerAbility(
            trigger=WhenYouPlayCard(card_type="upgrade", trait="Fortification"),
            effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit"))],
        )),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ModifyStats(-3, 0, TargetSpec(controller="enemy", kind="unit"),
                                 Duration.THIS_PHASE)],
            condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                     param="Grand Moff Tarkin"),
        ),
    ]


def _played_unit_still_in_play(state, source_ci, event_ctx) -> bool:
    from swu.engine.state import Zone
    res = state.find_instance(event_ctx.get("played_card_id") or "")
    return res is not None and res[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)


def _insurgent_camp_ready(state, source_ci, target_id, event_ctx):
    """Defeat this upgrade, then ready the played unit — one effect."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import _ready_forbidden, note_unit_readied
    if not _played_unit_still_in_play(state, source_ci, event_ctx):
        return state
    if state.find_instance(source_ci.instance_id) is None:
        return state
    _apply_defeat_unit(state, source_ci.instance_id)
    _, unit = state.find_instance(event_ctx["played_card_id"])
    if unit.cannot_ready_this_round or _ready_forbidden(state, unit):
        return state
    note_unit_readied(state, unit)
    unit.exhausted = False
    return state


@card_ability("HMW", "216")
def _insurgent_camp():
    """HMW_216 — Insurgent Camp (Upgrade, Fortification, 1; Fortify): "When you
    play a unit with 3 or less power: You may defeat this upgrade.  If you do,
    ready that unit."  ``WhenYouPlayCard(power_max=3)`` (effective power); "that
    unit" is ``event_ctx["played_card_id"]`` (Cobb Vanth ASH_60)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", power_max=3),
        effects=[CustomEffect(fn=_insurgent_camp_ready,
                              available_fn=_played_unit_still_in_play)],
        optional=True,
    )


@card_ability("HMW", "271")
def _landing_pad():
    """HMW_271 — Landing Pad (Upgrade, Fortification, 3; Fortify): "Attached base
    gains: 'Friendly space units get +1/+0.'"  A base-hosted ``via_host`` aura,
    read by ``actions._via_host_stat_bonus``."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", arena="space"),
        effects=[StatBonus(power=1)],
        via_host=True,
    )
