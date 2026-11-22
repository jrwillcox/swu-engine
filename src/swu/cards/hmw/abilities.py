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
    TriggerAbility, ActivatedAbility, ConstantAbility, GrantedAbility, EventAbility,
    WhenPlayed, WhenUnitDefeated, WhenYouPlayCard, WhenYouPlayOrCreateUnit,
    PhaseStartTrigger, OnAttack, WhenDefeated, WhenDamageDealt, WhenYouDraw,
    DealDamage, Heal, DrawCards, ExhaustCard, ModifyStats, CustomEffect, DefeatUnit,
    DiscardFromHand,
    KeywordGrant, StatBonus,
    IgnoreAspectPenaltyForPlays, BaseDamageShieldUpgrade, BasesCannotHeal,
    NextPlayDiscount, CostRoute, AbilityDamageBonus, BaseUpgradeDefeatReplacement,
    DefeatSelf, DiscardCardCost, ExhaustSelf, PayResources,
    ConditionCheck, Condition, Duration,
    TargetSpec, SELF, EACH_ENEMY,
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


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _jar_jar_clause():
    """"Deal 1 damage to a unit and heal 1 damage from a base" — two targeted
    effects in one ability (the ASH_624 DefeatUnit-then-base shape)."""
    return [DealDamage(1, TargetSpec(controller="any", kind="unit")),
            Heal(1, TargetSpec(controller="any", kind="base"))]


@card_ability("HMW", "5")
def _jar_jar_binks_hmw():
    """HMW_5 — Jar Jar Binks (Leader, Gungan, 4/5).

    Undeployed: "Action [1 resource, Exhaust]: If you gave a token upgrade to a unit
    this phase, deal 1 damage to a unit and heal 1 damage from a base."
    Deployed: "Shielded.  On Attack: If you gave a token upgrade to a unit this
    phase, you may deal 1 damage to a unit and heal 1 damage from a base."

    "If you gave a token upgrade" is the new ``token_upgrades_given_this_phase``
    ledger (``CONTROLLER_GAVE_TOKEN_UPGRADE_THIS_PHASE``), so the Action is never
    offered as a no-op.  ⚠ HMW_5 is also the Beast token UNIT's number: only the
    side-gated kinds are used (see the module docstring)."""
    gave = ConditionCheck(Condition.CONTROLLER_GAVE_TOKEN_UPGRADE_THIS_PHASE)
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=_jar_jar_clause(),
            condition=gave,
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=_jar_jar_clause(),
            optional=True,
            condition=gave,
            deployed_only=True,
        ),
    ]


def _kelnacca_strike(state, source_ci, target_id, event_ctx):
    """Pay 3 resources, then deal this unit's power to the chosen enemy unit — one
    effect, so an unpaid cost cannot grant the payoff."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import compute_power
    from swu.engine.actions.costs import _exhaust_resources
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if sum(1 for r in ps.resources if not r.exhausted) < 3:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    _exhaust_resources(ps, 3)
    _apply_deal_damage(state, target_id, compute_power(state, res[1]),
                       source_ci.card_def.display_name, dealer_id=ps.player_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("HMW", "36")
def _kelnacca():
    """HMW_36 — Kelnacca (Unit, Force/Jedi/Wookiee, 4/5; Restore 2): "When Played:
    You may pay any number of resources.  For every 3 resources paid this way, deal
    damage equal to this unit's power to an enemy unit."

    One optional "pay 3: strike" trigger per possible payment, the k-th gated on
    ≥3k READY resources.  Conditions are read when the triggers are collected and
    each accepted strike pays exactly 3, so the k-th is offered exactly when k
    payments are affordable, and declining one never strands the next.  Capped at
    3 strikes (13+ resources)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_kelnacca_strike,
                                  target=TargetSpec(controller="enemy", kind="unit"))],
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                     param=3 * k),
        )
        for k in (1, 2, 3)
    ]


def _vader_hmw_search(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_search_and_play_multiple
    push_search_and_play_multiple(
        state, source_ci, window=8, budget=999, max_units=2, then_damage=2,
        eligible=lambda cd: isinstance(cd, Unit) and (getattr(cd, "cost", 99) or 0) <= 4)
    return state


@card_ability("HMW", "43")
def _darth_vader_hmw():
    """HMW_43 — Darth Vader (Unit, Force/Imperial/Sith, 9/8; Saboteur): "When Played:
    Search the top 8 cards of your deck for up to 2 units that each cost 4 or less,
    play them for free, and deal 2 damage to each of them."

    ``push_search_and_play_multiple`` (Darth Vader SOR_87) with ``max_units=2``, an
    unbounded budget and the new ``then_damage`` (the Han Solo enter-play damage
    seam: after the keyword bus, before When Played)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_vader_hmw_search)])


def _krrsantan_amount(state, source_ci) -> int:
    ps = state.player_by_id(source_ci.owner_id)
    return len(ps.resources) - 3


def _krrsantan_has_amount(state, source_ci, event_ctx) -> bool:
    return _krrsantan_amount(state, source_ci) > 0


def _krrsantan_hit(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    amount = _krrsantan_amount(state, source_ci)
    if target_id is None or amount <= 0:
        return state
    _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id, source_id=source_ci.instance_id)
    return state


@card_ability("HMW", "46")
def _krrsantan_hmw():
    """HMW_46 — Krrsantan (Unit, Underworld/Wookiee, 4/4): "When Played: You may
    deal damage equal to the number of resources you control minus 3 to a ground
    unit."  Conditional magnitude in the effect fn; not offered at ≤3 resources."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_krrsantan_hit, available_fn=_krrsantan_has_amount,
                              target=TargetSpec(controller="any", kind="unit",
                                                arena="ground"))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:03 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _third_sister_chain(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=2, max_targets=1,
                       then_escalate=(3, 4))
    return state


@card_ability("HMW", "51")
def _third_sister():
    """HMW_51 — Third Sister (Unit, Force/Imperial/Inquisitor, 6/3; Overwhelm): "When
    Played: You may deal 2 damage to a unit.  If you do, that unit's controller may
    deal 3 damage to a unit.  If they do, that unit's controller may deal 4 damage
    to a unit."

    ``select_damage`` ("up to 1" carries every "may") with the new
    ``then_escalate`` hand-off: each pick pushes the next amount for the picked
    unit's controller."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_third_sister_chain)])


def _seismic_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _seismic_schedule(arena):
    def _fn(state, source_ci, target_id, event_ctx):
        state.game_memory.damage_at_regroup.append({
            "player_id": source_ci.owner_id, "arena": arena, "amount": 3,
            "source_name": source_ci.card_def.display_name})
        return state
    return _fn


@card_ability("HMW", "54")
def _seismic_detonation():
    """HMW_54 — Seismic Detonation (Event, Tactic, 6): "Choose an arena.  At the
    start of the next regroup phase, deal 3 damage to each enemy unit in that
    arena."

    The Confidence in Victory SEC_145 shape: index 0 pushes the arena selector over
    the two ``TriggerAbility`` options (1 = ground, 2 = space), each scheduling a
    one-shot ``game_memory.damage_at_regroup`` entry swept in ``_enter_regroup``."""
    return [
        EventAbility(effects=[CustomEffect(fn=_seismic_choose)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_seismic_schedule("ground"))]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_seismic_schedule("space"))]),
    ]


@card_ability("HMW", "64")
def _scorch():
    """HMW_64 — Scorch (Unit, Clone/Imperial/Trooper, 3/5): "On Attack: You may deal
    1 damage to an upgraded unit." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                          predicates=("upgraded",)))],
        optional=True,
    )


@card_ability("HMW", "68")
def _imperial_commandos():
    """HMW_68 — Imperial Commandos (Unit, Clone/Imperial/Trooper, 4/4): "When Played:
    You may defeat a non-leader unit with 4 or less power." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit", power_max=4,
                                       predicates=("non_leader",)))],
        optional=True,
    )


def _qui_gon_hmw_defeat(state, source_ci, target_id, event_ctx):
    """Defeat the base attacker; if it was a leader unit, defeat Qui-Gon too.  The
    leader test is read before the defeat (a defeated leader leaves the arena)."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.cards.models import Leader
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    was_leader = isinstance(res[1].card_def, Leader)
    _apply_defeat_unit(state, target_id)
    if was_leader and state.find_instance(source_ci.instance_id) is not None:
        from swu.engine.state import Zone
        me = state.find_instance(source_ci.instance_id)[1]
        if me.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            _apply_defeat_unit(state, source_ci.instance_id)
    return state


@card_ability("HMW", "78")
def _qui_gon_jinn_hmw():
    """HMW_78 — Qui-Gon Jinn (Unit, Force/Jedi/Republic, 2/5; Grit): "When Played: You
    may defeat a unit that attacked your base this phase.  If it's a leader unit,
    defeat this unit."  The ``attacked_your_base_this_phase`` predicate (Ephant Mon
    SHD_88)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_qui_gon_hmw_defeat,
                              target=TargetSpec(controller="any", kind="unit",
                                                predicates=("attacked_your_base_this_phase",)))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:04 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _radiant_vii_brace(state, source_ci, target_id, event_ctx):
    """Deal 3 to this unit; only if that damage was really dealt (not prevented)
    and it survived, give it a Shield — one effect, so the "If you do" binds."""
    from swu.engine.actions import _deal_damage_with_shield, _hp_lethal, _defeat_unit
    from swu.engine.state import Zone
    from swu.engine.tokens import attach_token
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    ps, me = res
    dealt = _deal_damage_with_shield(state, ps, me, 3,
                                     source_name=me.card_def.display_name,
                                     dealer_id=ps.player_id,
                                     dealer_source_id=me.instance_id)
    if _hp_lethal(state, me):
        _defeat_unit(state, ps, me)
        return state
    if dealt > 0:
        attach_token(state, ps, me, "Shield")
    return state


@card_ability("HMW", "79")
def _radiant_vii():
    """HMW_79 — Radiant VII (Unit, Republic/Transport/Vehicle, 5/7): "When Played: You
    may deal 3 damage to this unit.  If you do, give a Shield token to it." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_radiant_vii_brace)],
                          optional=True)


@card_ability("HMW", "86")
def _n1_patroller():
    """HMW_86 — N-1 Patroller (Unit, Fighter/Naboo/Vehicle, 2/2): "When Played: You
    may defeat a non-leader unit with 1 or less remaining HP." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader", "remaining_hp_le_1")))],
        optional=True,
    )


def _bigger_fish(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly Creature, then offer a free Creature from hand
    costing up to 3 more — one effect, so nothing is played unless the defeat
    happened ("If you do")."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import push_play_from_hand
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    cost = int(getattr(res[1].card_def, "cost", 0) or 0)
    _apply_defeat_unit(state, target_id)
    push_play_from_hand(state, source_ci, trait="Creature", free=True,
                        cost_max=cost + 3)
    return state


@card_ability("HMW", "99")
def _always_a_bigger_fish():
    """HMW_99 — Always a Bigger Fish (Event, Innate, 2): "Defeat a friendly Creature
    unit.  If you do, play a Creature unit that costs up to 3 more than the defeated
    unit from your hand for free."  ``push_play_from_hand(trait=, free=, cost_max=)``
    keyed off the defeated unit's printed cost."""
    return EventAbility(effects=[CustomEffect(
        fn=_bigger_fish,
        target=TargetSpec(controller="friendly", kind="unit", traits=("Creature",)))])


@card_ability("HMW", "102")
def _dragons_might():
    """HMW_102 — Dragon's Might (Event, Innate, 4): "Defeat a non-leader unit with 4
    or less power." """
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit", power_max=4,
                              predicates=("non_leader",)))])


def _breach_record(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly unit (its power, arena and Overwhelm) for the
    damage step — the Haymaker LAW_168 shared-``event_ctx`` shape."""
    from swu.engine.actions import compute_power
    from swu.engine.keywords import has_keyword, Keyword
    from swu.engine.state import Zone
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    unit = res[1]
    event_ctx["breach_power"] = compute_power(state, unit)
    event_ctx["breach_overwhelm"] = has_keyword(state, unit, Keyword.OVERWHELM)
    event_ctx["breach_dealer"] = unit.instance_id
    event_ctx["breach_name"] = unit.card_def.display_name
    event_ctx["same_arena"] = "ground" if unit.zone == Zone.GROUND_ARENA else "space"
    return state


def _breach_strike(state, source_ci, target_id, event_ctx):
    """Deal the recorded power to the enemy unit; with Overwhelm, the excess over
    its remaining HP (read before the hit) goes to that unit's controller's base."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import compute_hp
    if target_id is None:
        return state
    amount = int(event_ctx.get("breach_power", 0) or 0)
    res = state.find_instance(target_id)
    if amount <= 0 or res is None:
        return state
    victim_ps, victim = res
    excess = max(0, amount - (compute_hp(state, victim) - victim.damage))
    name = event_ctx.get("breach_name") or source_ci.card_def.display_name
    _apply_deal_damage(state, target_id, amount, name, dealer_id=source_ci.owner_id,
                       source_id=event_ctx.get("breach_dealer"))
    if excess and event_ctx.get("breach_overwhelm") and victim_ps.base_instance is not None:
        _apply_deal_damage(state, victim_ps.base_instance.instance_id, excess, name,
                           dealer_id=source_ci.owner_id,
                           source_id=event_ctx.get("breach_dealer"))
    return state


@card_ability("HMW", "114")
def _breach():
    """HMW_114 — Breach (Event, Tactic, 2): "A friendly unit deals damage equal to
    its power to an enemy unit in its arena.  If the friendly unit has Overwhelm,
    deal the excess damage to an enemy base."

    Haymaker LAW_168's two-step shape (``same_arena_as_event``).  The excess is the
    power beyond the victim's remaining HP, read before the hit; it lands on the
    victim's controller's base (the one enemy base in two-player).  The printed
    Overwhelm tag is upstream noise (the sanitiser's concern, not this card's)."""
    return EventAbility(effects=[
        CustomEffect(fn=_breach_record,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_breach_strike,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("same_arena_as_event",))),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:05 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _emerie_ping(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen ground unit; if the source's controller controls it,
    record the Khetanna LAW_158 next-unit discount through the resolver's own
    ``NextPlayDiscount`` arm (read the controller before the damage can kill it)."""
    from swu.abilities.resolver import _apply_deal_damage, execute_effect
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    friendly = res[0].player_id == source_ci.owner_id
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id, source_id=source_ci.instance_id)
    if friendly:
        state = execute_effect(state, NextPlayDiscount(None, 1), source_ci, None,
                               event_ctx)
    return state


@card_ability("HMW", "130")
def _emerie_karr():
    """HMW_130 — Emerie Karr (Unit, Clone/Imperial, 2/1): "When Played: You may deal
    1 damage to another ground unit.  If you control that unit, the next unit you
    play this phase costs 1 resource less." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_emerie_ping,
                              target=TargetSpec(controller="any", kind="unit",
                                                arena="ground",
                                                predicates=("not_self",)))],
        optional=True,
    )


@card_ability("HMW", "158")
def _battle_scarred_destroyer():
    """HMW_158 — Battle-Scarred Destroyer (Unit, Capital Ship/Imperial/Vehicle, 7/8):
    "When Played: Deal 4 damage to a friendly unit."  Mandatory (it may hit
    itself)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(4, TargetSpec(controller="friendly", kind="unit"))],
    )


@card_ability("HMW", "159")
def _general_grievous_hmw():
    """HMW_159 — General Grievous (Unit, Official/Separatist, 8/5): "Bases can't be
    healed.  When Played: Deal 4 damage to a base."  The ``BasesCannotHeal`` marker
    (Confederate Tri-Fighter TWI_132)."""
    return [
        BasesCannotHeal(),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[DealDamage(4, TargetSpec(controller="any", kind="base"))]),
    ]


def _arena_nexu_feed(state, source_ci, target_id, event_ctx):
    """Burn the round's single use, deal 3 to the chosen friendly Creature, then
    ready this unit — one effect, so the ready needs the damage clause."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import _ready_forbidden, note_unit_readied
    from swu.engine.state import Zone
    if target_id is None:
        return state
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    _apply_deal_damage(state, target_id, 3, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id, source_id=source_ci.instance_id)
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    me = res[1]
    if me.cannot_ready_this_round or _ready_forbidden(state, me):
        return state
    note_unit_readied(state, me)
    me.exhausted = False
    return state


@card_ability("HMW", "182")
def _arena_nexu():
    """HMW_182 — Arena Nexu (Unit, Creature, 2/6; Grit): "On Attack: You may deal 3
    damage to a friendly Creature unit (including this one) and ready this unit.
    Use this ability only once each round."

    The Toro Calican SHD_239 once-per-round trigger limiter
    (``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``), the marker set on resolve."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_arena_nexu_feed,
                              target=TargetSpec(controller="friendly", kind="unit",
                                                traits=("Creature",)))],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:06 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "186")
def _mining_guild_trespasser():
    """HMW_186 — Mining Guild Trespasser (Unit, Transport/Vehicle, 5/5): "When
    Played: You may deal 2 damage to a base and 2 damage to an enemy unit."  Two
    targeted effects in one optional ability (the HMW_5 / ASH_624 shape)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base")),
                 DealDamage(2, TargetSpec(controller="enemy", kind="unit"))],
        optional=True,
    )


def _maim(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen unit and exhaust "it" — one effect, one target."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.state import Zone
    if target_id is None:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id, source_id=source_ci.instance_id)
    res = state.find_instance(target_id)
    if res is not None and res[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        res[1].exhausted = True
    return state


@card_ability("HMW", "207")
def _maim_hmw():
    """HMW_207 — Maim (Event, Tactic, 1): "Deal 1 damage to a unit and exhaust it." """
    return EventAbility(effects=[
        CustomEffect(fn=_maim, target=TargetSpec(controller="any", kind="unit"))])


def _dont_touch_anything(state, source_ci, target_id, event_ctx):
    """3 damage to a RANDOM enemy unit — the seeded game rng (``state.make_rng``)."""
    from swu.abilities.resolver import _apply_deal_damage
    foes = [u for ps in state.players if ps.player_id != source_ci.owner_id
            for u in ps.ground_arena + ps.space_arena]
    if not foes:
        return state
    rng = state.make_rng()
    victim = rng.choice(foes)
    state.rng_state = rng.getstate()
    _apply_deal_damage(state, victim.instance_id, 3, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id, source_id=source_ci.instance_id)
    return state


@card_ability("HMW", "217")
def _dont_touch_anything_hmw():
    """HMW_217 — Don't Touch Anything (Event, Trick, 2): "Deal 3 damage to a random
    enemy unit." """
    return EventAbility(effects=[CustomEffect(fn=_dont_touch_anything)])


def _harbinger_strike(state, source_ci, target_id, event_ctx):
    from swu.cards.shd.abilities import _grey_squadron_attack
    return _grey_squadron_attack(state, source_ci, target_id, event_ctx)


@card_ability("HMW", "244")
def _separatist_harbinger():
    """HMW_244 — Separatist Harbinger (Unit, Separatist/Transport/Vehicle, 1/4):
    "When Played/On Attack: An opponent chooses a unit or base they control.  You may
    deal 2 damage to it."  Grey Squadron Y-Wing SHD_246's adapter, on both
    triggers."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_harbinger_strike)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_harbinger_strike)]),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Base-planet cards ("If you control a Naboo/Endor base") — from hmw-set:04, 05,
# 06, 10, 13 and 14.  The planet comes from the hand-maintained
# ``swu.cards.base_planets`` table via ``CONTROLLER_HAS_PLANET_BASE`` /
# ``OPPONENT_HAS_PLANET_BASE``.  Torrent HMW_100 (Naboo, hmw-set:26) waits for the
# Weakness token.
# ══════════════════════════════════════════════════════════════════════════════

_NABOO_BASE = ConditionCheck(Condition.CONTROLLER_HAS_PLANET_BASE, "Naboo")
_ENDOR_BASE = ConditionCheck(Condition.CONTROLLER_HAS_PLANET_BASE, "Endor")


def _sando_defeat(state, source_ci, target_id, event_ctx):
    """Open the combined-power picker over every other ground unit, capped at this
    unit's current power; the picker defeats them and damages this unit."""
    from swu.engine.actions import compute_power, push_combined_power_play
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    push_combined_power_play(state, res[1], pool="ground_any",
                             power_cap=max(0, compute_power(state, res[1])),
                             payoff="defeat_self_damage")
    return state


@card_ability("HMW", "94")
def _sando_aqua_monster():
    """HMW_94 — Sando Aqua Monster (Unit, Creature, 5/9; Grit): "When Played: If you
    control a Naboo base, you may defeat any number of ground units with combined
    power equal to or less than this unit's power.  Deal damage to this unit equal
    to the combined power of the defeated units."

    The Consolidation of Power TWI_89 ``combined_power_play`` picker with its
    ``defeat_self_damage`` payoff.  "Any number" includes none, so the trigger is
    mandatory and ``FinishCombinedPowerPlay`` is the "may"."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_sando_defeat)],
                          condition=_NABOO_BASE)


@card_ability("HMW", "177")
def _adamant_ewoks():
    """HMW_177 — Adamant Ewoks (Unit, Ewok, 3/2): "When Played: If you control
    another Ewok unit or an Endor base, you may deal 1 damage to a base and 1 damage
    to an enemy unit."  Mining Guild Trespasser HMW_186's shape, gated."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="base")),
                 DealDamage(1, TargetSpec(controller="enemy", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.ANY_OF, (
            ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Ewok"),
            _ENDOR_BASE)),
    )


def _gorax_push_choice(state, source_ci, target_id, event_ctx):
    """Hand the opponent the "chooses one" over option specs idx 2 and idx 3."""
    from swu.engine.actions import push_choose_modal
    opponent_id = next(p.player_id for p in state.players
                       if p.player_id != source_ci.owner_id)
    push_choose_modal(state, source_ci, option_indices=[2, 3], pick=1,
                      decider_id=opponent_id)
    return state


def _gorax_defeat_their_resource(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _fire_defeat_own_resource
    for ps in state.players:
        if ps.player_id != source_ci.owner_id:
            _fire_defeat_own_resource(state, ps.player_id)
    return state


@card_ability("HMW", "188")
def _giant_gorax():
    """HMW_188 — Giant Gorax (Unit, Creature, 7/7; Overwhelm): "On Attack/When
    Defeated: If you control an Endor base, each opponent chooses one: You deal 3
    damage to a unit or base they control.  / They discard a card from their hand
    and defeat a resource they control."

    Luke Skywalker LAW_80's opponent-decided ``choose_two_modal`` (``pick=1``).  The
    option specs are ``EventAbility`` so a unit never trigger-collects them.  The
    discard is the documented first-card ``DiscardFromHand(chooser="opponent")``;
    the resource is auto-picked (resources are fungible face-down cards)."""
    return [
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_gorax_push_choice)],
                       condition=_ENDOR_BASE),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[CustomEffect(fn=_gorax_push_choice)],
                       condition=_ENDOR_BASE),
        # idx 2 — "You deal 3 damage to a unit or base they control."
        EventAbility(effects=[
            DealDamage(3, TargetSpec(controller="enemy", kind="unit_or_base"))]),
        # idx 3 — "They discard a card from their hand and defeat a resource."
        EventAbility(effects=[
            DiscardFromHand(1, chooser="opponent"),
            CustomEffect(fn=_gorax_defeat_their_resource)]),
    ]


def _nightfall_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    if _ENDOR_BASE.evaluate(state, source_ci):
        push_granted_attack(state, source_ci, 2, optional=True)
    return state


@card_ability("HMW", "193")
def _nightfall():
    """HMW_193 — Nightfall (Event, Disaster, 2): "Deal 1 damage to an enemy unit.  If
    you control an Endor base, you may attack with a unit.  It gets +2/+0 for this
    attack."  The base check is made when the attack clause resolves."""
    return EventAbility(effects=[
        DealDamage(1, TargetSpec(controller="enemy", kind="unit")),
        CustomEffect(fn=_nightfall_attack),
    ])


@card_ability("HMW", "247")
def _surveillance_cruiser():
    """HMW_247 — Surveillance Cruiser (Unit, Capital Ship/Imperial/Vehicle, 4/4):
    "When Played: If an opponent controls an Endor, Kashyyyk, Naboo, or Tatooine
    base, draw a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.OPPONENT_HAS_PLANET_BASE,
                                 ("Endor", "Kashyyyk", "Naboo", "Tatooine")),
    )


@card_ability("HMW", "84")
def _gunga_city_guard():
    """HMW_84 — Gunga City Guard (Unit, Gungan, 2/1; Restore 1): "While you control
    another Gungan unit or a Naboo base, this unit gains Shielded."  Shielded is read
    through ``has_keyword`` when the unit enters play, so the grant only matters
    then — exactly as printed."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Shielded")],
        condition=ConditionCheck(Condition.ANY_OF, (
            ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Gungan"),
            _NABOO_BASE)),
    )


# ══════════════════════════════════════════════════════════════════════════════
# "When damage is dealt" cards — the general WhenDamageDealt observer (fed by
# ``actions.note_damage_dealt``, drained by ``actions._fire_damage_observers``).
# From hmw-set:02, 05, 09 and 19.
# ══════════════════════════════════════════════════════════════════════════════

_A_DIFFERENT_UNIT_OR_BASE = TargetSpec(controller="any", kind="unit_or_base",
                                       predicates=("excludes_event_target",))


@card_ability("HMW", "11")
def _darth_sidious_hmw():
    """HMW_11 — Darth Sidious (Leader, Force/Sith, 4/5).

    Undeployed: "When you deal 4 or more damage to a unit or base: You may exhaust
    this leader.  If you do, deal 1 damage to a different unit or base."
    Deployed (Hidden): "When you deal 4 or more damage to a unit or base: You may
    deal 1 damage to a different unit or base."

    The SEC_16 Padmé shape: the targeted damage first, then the fixed-SELF exhaust,
    gated ``SOURCE_READY``.  "Different" = the stock ``excludes_event_target``
    predicate (the drain names the damaged card).  ⚠ HMW_11 shares its number with
    a token, so only side-gated kinds (``undeployed_only`` needs a Leader card;
    ``deployed_only`` a deployed one)."""
    trigger = WhenDamageDealt(dealer="you", min_amount=4)
    return [
        TriggerAbility(
            trigger=trigger,
            effects=[DealDamage(1, _A_DIFFERENT_UNIT_OR_BASE),
                     ExhaustCard(TargetSpec(kind="unit", fixed=SELF))],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(trigger=trigger,
                       effects=[DealDamage(1, _A_DIFFERENT_UNIT_OR_BASE)],
                       optional=True,
                       deployed_only=True),
    ]


@card_ability("HMW", "13")
def _cham_syndulla():
    """HMW_13 — Cham Syndulla (Leader, Twi'lek, 3/8).

    Undeployed: "When non-combat damage is dealt to a friendly unit or base: You may
    exhaust this leader.  If you do, deal 1 damage to an enemy unit or base."
    Deployed: the same without the exhaust.

    Padmé SEC_16's two-sided shape over ``WhenDamageDealt(target="friendly",
    combat=False)``.  Two DEPLOYED Chams facing each other could trade pings for
    ever (each ping is non-combat damage to the other's friendly card); a player
    declines, and the heuristic bot declines that mirror case explicitly."""
    trigger = WhenDamageDealt(target="friendly", combat=False)
    enemy = TargetSpec(controller="enemy", kind="unit_or_base")
    return [
        TriggerAbility(
            trigger=trigger,
            effects=[DealDamage(1, enemy),
                     ExhaustCard(TargetSpec(kind="unit", fixed=SELF))],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(trigger=trigger, effects=[DealDamage(1, enemy)],
                       optional=True, deployed_only=True),
    ]


@card_ability("HMW", "45")
def _logray():
    """HMW_45 — Logray (Unit, Ewok, 1/5): "When another friendly unit that costs 3 or
    less is dealt damage: You may deal 1 damage to an enemy unit." """
    return TriggerAbility(
        trigger=WhenDamageDealt(target="other_friendly", kind="unit",
                                target_cost_max=3),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit"))],
        optional=True,
    )


_DEALT_DAMAGE_AND_SURVIVES = WhenDamageDealt(target="self", kind="unit", survived=True)


@card_ability("HMW", "156")
def _arena_acklay():
    """HMW_156 — Arena Acklay (Unit, Creature, 5/6): "When this unit is dealt damage
    and survives: Deal 2 damage to each enemy base." """
    return TriggerAbility(
        trigger=_DEALT_DAMAGE_AND_SURVIVES,
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base",
                                          fixed=EACH_ENEMY))],
    )


@card_ability("HMW", "169")
def _crosshair_hmw():
    """HMW_169 — Crosshair (Unit, Clone, 5/6): "When this unit is dealt damage and
    survives: Each player draws a card.  / When an opponent draws 1 or more cards
    during the action phase: Deal 2 damage to their base."

    The second line is the Seasoned Fleet Admiral JTL_111 ``WhenYouDraw(opponent=
    True)`` observer; in two-player "their base" is the enemy base."""
    return [
        TriggerAbility(trigger=_DEALT_DAMAGE_AND_SURVIVES,
                       effects=[DrawCards(1, player="each")]),
        TriggerAbility(
            trigger=WhenYouDraw(opponent=True),
            effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base",
                                              fixed=EACH_ENEMY))]),
    ]


def _gungi_discard_to_ready(state, source_ci, target_id, event_ctx):
    """Discard (the first card — the K-2SO SOR_145 convention), then ready this
    unit: one effect, so the ready needs the discard (the Razor Crest ASH_172
    "if you do" binding)."""
    from swu.engine.actions import (
        _ready_forbidden, note_hand_or_deck_discard, note_unit_readied)
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    me = res[1]
    if me.cannot_ready_this_round or _ready_forbidden(state, me):
        return state
    note_unit_readied(state, me)
    me.exhausted = False
    return state


@card_ability("HMW", "166")
def _gungi():
    """HMW_166 — Gungi (Unit, Force/Jedi/Wookiee, 2/5; Grit): "When this unit is
    dealt damage and survives: You may discard a card from your hand.  If you do,
    ready this unit."  Gated on a non-empty hand so it is never a dead prompt."""
    return TriggerAbility(
        trigger=_DEALT_DAMAGE_AND_SURVIVES,
        effects=[CustomEffect(fn=_gungi_discard_to_ready)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1),
    )


@card_ability("HMW", "211")
def _tech_hmw():
    """HMW_211 — Tech (Unit, Clone, 3/5): "When this unit is dealt damage and
    survives: You may exhaust a unit." """
    return TriggerAbility(
        trigger=_DEALT_DAMAGE_AND_SURVIVES,
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# "While playing this unit" cost routes — the ``CostRoute`` marker, read at
# PlayCard (the ``cost_route`` decision; the Exploit skeleton).  hmw-set:03, 04.
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "49")
def _greater_sarlacc():
    """HMW_49 — Greater Sarlacc (Unit, Creature, 9/8; Overwhelm): "While playing
    this unit, you may defeat any number of ready resources you control.  For each
    resource defeated this way, this unit costs 3 resources less to play." """
    return CostRoute(kind="defeat_ready_resource", discount=3)


@card_ability("HMW", "125")
def _the_marauder_hmw():
    """HMW_125 — The Marauder (Unit, Transport/Vehicle, 5/7): "While playing this
    unit, you may choose any number of friendly units.  Deal 1 damage to each of
    them.  For each unit chosen this way, this unit costs 1 resource less." """
    return CostRoute(kind="damage_friendly_unit", discount=1)


# ══════════════════════════════════════════════════════════════════════════════
# Replacement effects without a replacement system — hmw-set:03, 06.
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "60")
def _vice_admiral_rampart():
    """HMW_60 — Vice Admiral Rampart (Unit, Imperial/Official, 1/5): "If an upgrade
    on your base would be defeated, you may defeat this unit instead."

    ``BaseUpgradeDefeatReplacement``: applied AUTOMATICALLY at
    ``resolver._apply_defeat_unit`` when an opponent's effect would defeat an upgrade
    on this unit's controller's base (the user's call — the ASH_62 un-prompted
    "may … instead" precedent; an interactive deferral would be the start of a
    replacement-effect system).  A Fortify upgrade's own self-defeat cost is never
    replaced."""
    return BaseUpgradeDefeatReplacement()


@card_ability("HMW", "185")
def _ty_yorrick():
    """HMW_185 — Ty Yorrick (Unit, Bounty Hunter/Force, 4/5): "If a friendly ability
    would deal damage, you may have that ability deal that much damage plus 1
    instead.  / On Attack: You may deal 1 damage to a Creature unit."

    The first line is ``AbilityDamageBonus`` — the dealer-side twin of the
    ``DamageAmplification`` seam, taken exactly when it helps (damage to an
    opponent's unit or base; never indirect)."""
    return [
        AbilityDamageBonus(amount=1),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                              traits=("Creature",)))],
            optional=True),
    ]


@card_ability("HMW", "90")
def _opee_sea_killer():
    """HMW_90 — Opee Sea Killer (Unit, Creature, 5/6): "While you control a Naboo
    base, this unit gains Grit." """
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[KeywordGrant("Grit")],
                           condition=_NABOO_BASE)
