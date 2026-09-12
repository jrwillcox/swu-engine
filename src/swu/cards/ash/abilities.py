"""ASH card ability registrations.

The first ASH set module.  Its opening batch is ``ash-set:01``'s KEYWORD-RESIDUAL
half: the 22 Support cards that also carry ability text (the keyword itself landed
engine-side in the previous batch — see ``engine/keyword_triggers.py``).

Everything here composes from existing primitives except four small additive engine
seams introduced with it (all documented in CLAUDE.md's seams catalog):
  * ``WhenAttackEnds(require_defender_defeated=True)`` — "If the defending unit was
    defeated" (Thrawn ASH_33, Halo ASH_223), plus the ``attack_ended_combat_damaged``
    list on the same fire (The Great Mothers ASH_101).
  * the **Advantage token** (ASH_2), the ASH set mechanic: an ordinary +1/+0 token
    upgrade whose only bespoke rule — it is defeated when its host's attack or
    defense ends — lives in the combat pipelines (Rukh ASH_36).
  * ``KeywordRevoke``, the standing aura form of ``RevokeKeyword`` (Domesticated
    Loth-Cat ASH_68).
  * ``ConstantAbility.while_attacking_damaged_unit`` (Marrok's Fiend Fighter ASH_241),
    ``Condition.SOURCE_REMAINING_HP_MIN`` (Doctor Pershing ASH_72),
    ``Condition.CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD`` (Moff Gideon ASH_8) and
    the ``power_lt_source`` / ``power_lt_a_friendly_unit`` predicates (Ahsoka ASH_9).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ActivatedAbility, ConstantAbility, EventAbility,
    WhenPlayed, WhenDefeated, OnAttack, WhenAttackEnds, WhenYouTakeInitiative,
    WhenFriendlyUnitDealtCombatDamage, WhenYouPlayCard,
    WhenFriendlyUpgradeDefeated, WhenYouWouldCreateTokens,
    DealDamage, DealDamageEqualTo, DefeatUnit, DefeatAllUnits, DamagePrevention,
    DrawCards, ReadyCard, ModifyStats, GrantKeyword,
    GiveToken, NextPlayDiscount, CreateTokenUnit, GrantedAbility,
    StatBonus, KeywordGrant, KeywordRevoke,
    CustomEffect, ExhaustSelf,
    AuraGrantedAbility, UnpreventableDamage, WhenAttacked,
    WhenDefeatedAsUpgrade, CostReduction, WhenUnitDefeated, WhenYouDraw,
    ConditionalEffect, ReturnToHand,
    WhenFriendlyUnitAttackEnds, DeployCondition, WhenYouPlayOrCreateUnit,
    WhenEnemyAttacksYourBase, PhaseStartTrigger, WhenDamageDealtToYourBase,
    WhenUpgradeAttached, AmbushAttackerBonus, DiscardCardCost, EntersPlayReady,
    PayResources, ExhaustCard, Heal,
    ConditionCheck, Condition,
    CannotBeAttacked, ConditionalFirstStrike, CrossArenaAttack, CannotAttackBases,
    BaseDamageCap, SearchWindowDoubler, ForbidNamedCardPlay,
    LeaderUnitGrant, ProvidesAspectIcons, TraitGrant,
    AdvantageTokensLoseAbilities, AttackerLosesOverwhelm, DamageAmplification,
    IgnoreAspectPenaltyForPlays,
    StandingPlayDiscount, WhenUnitReadies,
    TargetSpec, SELF, DEFENDER, EACH_ENEMY, EACH_FRIENDLY, EACH_IN_PLAY, Duration,
)


# ── ash-set:01 — Support residuals: the LEADERS ──────────────────────────────
#
# A leader's ``text`` is its UNDEPLOYED side and ``deploy_box`` its DEPLOYED side, so
# every leader below is one ``undeployed_only`` spec plus one ``deployed_only`` one.
# A ConstantAbility on a leader needs no side gate at all — only the arena scans read
# it, so it is inert while the leader sits in the base zone.


def _moff_gideon_play_discounted(state, source_ci, target_id, event_ctx):
    """Play a unit from hand for 1 less (Moff Gideon ASH_8, undeployed)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=1)
    return state


@card_ability("ASH", "8")
def _moff_gideon():
    """Action [Exhaust]: If a friendly Imperial unit was defeated this phase, play a
    unit from your hand.  It costs 1 resource less.

    Deployed: "This unit gains each of the following keywords if it is on an Imperial
    unit in your discard pile: Ambush, Grit, Hidden, Overwhelm, Saboteur, Sentinel,
    Shielded, Support" — eight parallel conditional SELF ``KeywordGrant`` constants,
    one per keyword, each gated on the new
    ``CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD`` atom.  Registering them is also what
    strips his (entirely mistagged) printed eight-keyword bar: sanitiser rule 2 keys
    on exactly this conditional-self-grant shape.

    The Action is gated on BOTH clauses — the Imperial defeat AND an affordable unit
    in hand at the discounted price — so the exhaust is never spent on a no-op."""
    keywords = ("Ambush", "Grit", "Hidden", "Overwhelm",
                "Saboteur", "Sentinel", "Shielded", "Support")
    specs = [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_moff_gideon_play_discounted)],
            title="Play a unit from your hand for 1 less",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ALL_OF, param=(
                ConditionCheck(Condition.CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE,
                               param="Imperial"),
                ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                               param=(None, 1)),
            )),
        ),
    ]
    specs += [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant(kw)],
            condition=ConditionCheck(
                Condition.CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD,
                param=("Imperial", kw)),
        )
        for kw in keywords
    ]
    return specs


@card_ability("ASH", "9")
def _ahsoka_tano():
    """Action [Exhaust]: Choose a unit with less power than a friendly unit.  It gets
    +2/+0 for this phase.  |  Deployed On Attack: You may give a unit with less power
    than this unit +2/+0 for this phase.

    Two readings of "less power", so two predicates: the undeployed side compares each
    candidate against the strongest friendly unit (``power_lt_a_friendly_unit``), the
    deployed side against Ahsoka herself (``power_lt_source``).  The On Attack is
    ``optional``, so with no weaker unit on the board it auto-declines rather than
    prompting (the engine's "don't offer a no-op" rule)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[ModifyStats(2, 0, TargetSpec(
                controller="any", kind="unit",
                predicates=("power_lt_a_friendly_unit",)), Duration.THIS_PHASE)],
            title="Give a weaker unit +2/+0 for this phase",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(2, 0, TargetSpec(
                controller="any", kind="unit",
                predicates=("power_lt_source",)), Duration.THIS_PHASE)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _mando_pay_one_draw(state, source_ci, target_id, event_ctx):
    """Pay 1 resource; if you do, draw a card (The Mandalorian ASH_14, undeployed).

    Cost and payoff in ONE effect so an unpaid cost cannot draw (the "If you do"
    binding, Bright Hope SOR_99)."""
    from swu.engine.actions import _exhaust_resources, _draw_cards
    ps = state.player_by_id(source_ci.owner_id)
    if sum(1 for r in ps.resources if not r.exhausted) < 1:
        return state
    _exhaust_resources(ps, 1)
    _draw_cards(state, ps, 1)
    return state


@card_ability("ASH", "14")
def _the_mandalorian():
    """When you take the initiative: You may pay 1 resource.  If you do, draw a card.
    |  Deployed On Attack: If you have the initiative, you may draw a card."""
    return [
        TriggerAbility(
            trigger=WhenYouTakeInitiative(),
            effects=[CustomEffect(fn=_mando_pay_one_draw)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                     param=1),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DrawCards(count=1)],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
        ),
    ]


# ── ash-set:01 — Support residuals: the UNITS ────────────────────────────────


@card_ability("ASH", "33")
def _grand_admiral_thrawn():
    """When Attack Ends: If the defending unit was defeated, ready this unit.

    The first user of ``WhenAttackEnds(require_defender_defeated=True)``; the trigger
    only fires for an attacker still in play, so "ready this unit" is always live."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_defender_defeated=True),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
    )


@card_ability("ASH", "36")
def _rukh():
    """When Attack Ends: If the defending unit was defeated, you may give 3 Advantage
    tokens to a unit.

    The first card to create the ASH set's **Advantage** token — an ordinary
    ``GiveToken`` (the effect is token-name agnostic), since the token is a real +1/+0
    ``TokenUpgrade`` in the DB whose only special rule (it is defeated when its host's
    attack or defense ends) is enforced in the combat pipelines."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_defender_defeated=True),
        effects=[GiveToken("Advantage",
                           TargetSpec(controller="any", kind="unit"), count=3)],
        optional=True,
    )


@card_ability("ASH", "37")
def _red_leader():
    """This unit may attack units in either arena — the ``CrossArenaAttack`` marker
    (Strafing Gunship SOR_212), here on a SPACE unit reaching ground defenders."""
    return CrossArenaAttack()


@card_ability("ASH", "46")
def _scion_shuttle():
    """While this unit is attacking, the defending unit gets –1/–1.

    Modelled as an On Attack ``this_attack`` debuff on the chosen defender rather than
    a ``while_attacking`` ConstantAbility, because that flag is read only by
    ``compute_power`` — ``compute_hp`` carries no combat context, so the –1 HP half
    would silently vanish.  The two readings are indistinguishable: the unit is only
    ever "attacking" during the attack the modifier covers."""
    return TriggerAbility(
        trigger=OnAttack(vs_unit=True),
        effects=[ModifyStats(-1, -1, TargetSpec(fixed=DEFENDER),
                             Duration.THIS_ATTACK)],
    )


@card_ability("ASH", "50")
def _morgan_elsbeth():
    """When Defeated: You may give a unit –2/–2 for this phase."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ModifyStats(-2, -2, TargetSpec(controller="any", kind="unit"),
                             Duration.THIS_PHASE)],
        optional=True,
    )


def _leia_self_damage_heal_base(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to this unit; if you do, heal 2 from your base (Leia ASH_59).

    One effect, so the cost cannot land without the payoff.  The heal routes through
    the shared ``_apply_heal`` so the Wolffe SOR_160 "bases can't be healed" lock
    still applies."""
    from swu.abilities.resolver import _apply_heal
    from swu.engine.actions import _deal_damage_with_shield
    ps = state.player_by_id(source_ci.owner_id)
    _deal_damage_with_shield(state, ps, source_ci, 1)
    base = ps.base_instance
    if base is not None:
        _apply_heal(state, source_ci, base.instance_id, 2)
    return state


@card_ability("ASH", "59")
def _leia_organa():
    """On Attack: You may deal 1 damage to this unit.  If you do, heal 2 damage from
    your base."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_leia_self_damage_heal_base)],
        optional=True,
    )


@card_ability("ASH", "68")
def _domesticated_loth_cat():
    """Enemy units lose Ambush and Support.

    A standing ``KeywordRevoke`` aura — the keyword layer reads it ahead of every
    grant source, so "and can't gain them" and "units played later are covered too"
    both fall out for free, and it lifts the moment the Loth-Cat leaves play.  (Its
    own mistagged printed Ambush + Support were already stripped by keyword-sanitiser
    rule 10, which landed with the Support keyword.)"""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),
        effects=[KeywordRevoke("Ambush"), KeywordRevoke("Support")],
    )


@card_ability("ASH", "72")
def _doctor_pershing():
    """On Attack: If this unit has 3 or more remaining HP, draw a card."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(count=1)],
        condition=ConditionCheck(Condition.SOURCE_REMAINING_HP_MIN, param=3),
    )


@card_ability("ASH", "99")
def _gozanti_assault_carrier():
    """On Attack: This unit gains Sentinel for this phase.

    The printed Sentinel bar is a mistag — the carrier only gains it on attack — and
    registering this self-targeted ``GrantKeyword`` is what makes keyword-sanitiser
    rule 3 strip it."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword("Sentinel", 0, TargetSpec(fixed=SELF),
                              Duration.THIS_PHASE)],
    )


def _great_mothers_defeat_damaged(state, source_ci, target_id, event_ctx):
    """Defeat every non-leader unit this attacker dealt combat damage to (ASH_101).

    Reads ``event_ctx["attack_ended_combat_damaged"]``, the list both unit-combat
    pipelines now carry on the attack-ends fire.  A unit the damage already killed
    is skipped by the arena-zone guard below."""
    from swu.abilities.resolver import _apply_defeat_unit, _is_leader_unit
    from swu.engine.state import Zone
    for iid in list(event_ctx.get("attack_ended_combat_damaged") or ()):
        res = state.find_instance(iid)
        if res is None:
            continue
        ci = res[1]
        if ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            continue
        # ``find_instance`` REACHES THE DISCARD, so a unit the combat damage
        # already killed still resolves here — defeating it a second time would
        # append it to the discard twice (duplicate-instance_id invariant).
        if _is_leader_unit(ci):
            continue
        _apply_defeat_unit(state, iid)
    return state


@card_ability("ASH", "101")
def _the_great_mothers():
    """When Attack Ends: If this unit dealt combat damage to 1 or more non-leader
    units, defeat those units."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_great_mothers_defeat_damaged)],
    )


def _r5d4_strip_upgrades(state, source_ci, target_id, event_ctx):
    """Defeat all upgrades on the defending unit (R5-D4 ASH_156)."""
    from swu.engine.actions import _defeat_attached_upgrade
    did = event_ctx.get("defender_id")
    if not did:
        return state
    res = state.find_instance(did)
    if res is None:
        return state
    for upg in list(res[1].attached_upgrades):
        _defeat_attached_upgrade(state, upg)
    return state


@card_ability("ASH", "156")
def _r5_d4():
    """On Attack: Defeat all upgrades on the defending unit.

    "All upgrades" is literal here — unlike the ``kind="upgrade"`` targeting
    convention, this sweep also takes the defender's Shield and Experience tokens,
    which are upgrades by the rules."""
    return TriggerAbility(
        trigger=OnAttack(vs_unit=True),
        effects=[CustomEffect(fn=_r5d4_strip_upgrades)],
    )


def _migs_mayfeld_damage(state, source_ci, target_id, event_ctx):
    """Deal 1 to the defender, or 2 if this unit is upgraded (Migs Mayfeld ASH_168).

    The conditional-MAGNITUDE shape (Zeb Orrelios LAW_45): the amount is decided
    inside one effect, so no second ability and no extra prompt."""
    from swu.engine.actions import _deal_damage_with_shield
    did = event_ctx.get("defender_id")
    if not did:
        return state
    res = state.find_instance(did)
    if res is None:
        return state
    ps, ci = res
    amount = 2 if getattr(source_ci, "attached_upgrades", None) else 1
    _deal_damage_with_shield(state, ps, ci, amount)
    return state


@card_ability("ASH", "168")
def _migs_mayfeld():
    """On Attack: Deal 1 damage to the defending unit.  If this unit is upgraded, deal
    2 damage to the defending unit instead."""
    return TriggerAbility(
        trigger=OnAttack(vs_unit=True),
        effects=[CustomEffect(fn=_migs_mayfeld_damage)],
    )


def _ready_one_resource(state, source_ci, target_id, event_ctx):
    """Ready a resource (Emperor's Messenger ASH_189).

    Resources are fungible and are not targetable cards, so the pick is automatic —
    the K-2SO SOR_145 convention."""
    ps = state.player_by_id(source_ci.owner_id)
    for r in ps.resources:
        if r.exhausted:
            r.exhausted = False
            break
    return state


@card_ability("ASH", "189")
def _emperors_messenger():
    """On Attack: Ready a resource."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_ready_one_resource)],
    )


@card_ability("ASH", "202")
def _carson_teva():
    """While attacking, this unit deals combat damage before the defender.

    ``ConditionalFirstStrike`` over "any enemy unit" — i.e. unconditional while
    ATTACKING.  A plain ``KeywordGrant("First Strike")`` would be wrong: the keyword
    layer carries no combat context, so it would also apply while Carson defends."""
    return ConditionalFirstStrike(
        defender_spec=TargetSpec(controller="enemy", kind="unit"))


def _friendly_ready_leader(state, source_ci):
    """The source controller's READY leader that is not riding as a Pilot upgrade."""
    from swu.cards.models import Leader
    ps = state.player_by_id(source_ci.owner_id)
    for ci in list(ps.base_zone) + list(ps.ground_arena) + list(ps.space_arena):
        if isinstance(ci.card_def, Leader) and not ci.exhausted:
            return ci
    return None


def _n1_available(state, source_ci, event_ctx):
    return _friendly_ready_leader(state, source_ci) is not None


def _n1_exhaust_leader_for_power(state, source_ci, target_id, event_ctx):
    """Exhaust a friendly (non-upgrade) leader; if you do, +2/+0 for this attack."""
    from swu.engine.state import Modifier
    leader = _friendly_ready_leader(state, source_ci)
    if leader is None:
        return state
    leader.exhausted = True
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=source_ci.instance_id,
        kind="stats", value={"power": 2, "hp": 0}, duration="this_attack"))
    return state


@card_ability("ASH", "203")
def _mandos_n1_starfighter():
    """On Attack: You may exhaust a friendly (non-upgrade) leader.  If you do, this
    unit gets +2/+0 for this attack.

    The leader is auto-picked (a player controls at most one), and ``available_fn``
    keeps the optional trigger from prompting when there is no ready leader to
    exhaust — the "don't offer a no-op" rule for a non-targeted CustomEffect."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_n1_exhaust_leader_for_power,
                              available_fn=_n1_available)],
        optional=True,
    )


@card_ability("ASH", "209")
def _ezra_bridger():
    """On Attack: If this unit is upgraded, you may give a unit –3/–0 for this phase."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(-3, 0, TargetSpec(controller="any", kind="unit"),
                             Duration.THIS_PHASE)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


@card_ability("ASH", "223")
def _halo():
    """When Attack Ends: If the defending unit was defeated, give a Shield token to
    this unit."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_defender_defeated=True),
        effects=[GiveToken("Shield", TargetSpec(fixed=SELF))],
    )


@card_ability("ASH", "241")
def _marroks_fiend_fighter():
    """This unit gets +2/+0 while attacking a damaged unit.

    ``while_attacking_damaged_unit`` — the exact sibling of Jango Fett SHD_138's
    bounty flag, read at the same ``compute_power`` site against the threaded
    ``defender_id``."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        while_attacking_damaged_unit=True,
    )


@card_ability("ASH", "253")
def _yellow_aces_bomber():
    """On Attack: If this unit is upgraded, deal 2 damage to a base."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


# ── ash-set:02 — Direct damage & removal ─────────────────────────────────────


def _thrawn_leader_attack(state, source_ci, target_id, event_ctx):
    """Attack with a unit; it gains Restore 2 for this attack if you control the same
    number of units as the defending player (Grand Admiral Thrawn ASH_4).

    Two players, so "the defending player" is the one opponent and the comparison is
    knowable before the attacker is chosen — the Adelphi SHD_101 convention of
    deciding a granted attack's rider at resolution."""
    from swu.engine.actions import push_granted_attack
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    mine = len(ps.ground_arena) + len(ps.space_arena)
    theirs = len(opp.ground_arena) + len(opp.space_arena)
    push_granted_attack(state, source_ci,
                        grant_keywords=[("Restore", 2)] if mine == theirs else None)
    return state


@card_ability("ASH", "4")
def _grand_admiral_thrawn_leader():
    """Action [Exhaust]: Attack with a unit.  It gains Restore 2 for this attack if
    you control the same number of units as the defending player.  |  Deployed On
    Attack: If you control more units than the defending player, you may defeat a
    non-leader unit they control."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_thrawn_leader_attack)],
            title="Attack with a unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DefeatUnit(TargetSpec(controller="enemy", kind="unit",
                                           predicates=("non_leader",)))],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_MORE_UNITS_THAN_OPPONENT),
        ),
    ]


@card_ability("ASH", "11")
def _cad_bane_leader():
    """Action [Exhaust]: Deal 1 damage to a unit with 2 or more remaining HP.  |
    Deployed On Attack: You may deal 1 damage to a unit with 2 or more remaining HP.

    The ``remaining_hp_ge_<N>`` predicate — the ceiling mirror of the long-standing
    ``remaining_hp_le_<N>``.  The clause is a real restriction: it stops Cad Bane
    finishing off a unit already at 1 HP."""
    tough = TargetSpec(controller="any", kind="unit",
                       predicates=("remaining_hp_ge_2",))
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, tough)],
            title="Deal 1 damage to a unit with 2+ remaining HP",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(1, tough)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _vane_defeat_upgrade(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly upgrade and record it, so the follow-up damage is
    gated on the cost actually having been paid (the "If you do" chain)."""
    from swu.engine.actions import _defeat_attached_upgrade
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _defeat_attached_upgrade(state, res[1])
    event_ctx["prior_target_id"] = target_id
    return state


@card_ability("ASH", "12")
def _vane_leader():
    """Action [Exhaust, defeat a friendly upgrade]: Deal 2 damage to a base.  |
    Deployed On Attack: You may defeat a friendly upgrade.  If you do, deal 2 damage
    to the defending unit or a base.

    "Defeat a friendly upgrade" has no cost spec, so the undeployed side models it as
    a LEADING targeted ``DefeatUnit`` plus a payability gate (the Director Krennic
    LAW_8 / Tomb of Eilram LOF_28 shape) — with no friendly upgrade the Action is not
    offered, so the exhaust is never wasted.  The deployed side is the same cost as
    the first half of a shared-``event_ctx`` chain, the payoff gated by
    ``requires_prior_target`` and narrowed by the existing ``defender_or_base``
    predicate (Sabine Wren SOR_142)."""
    friendly_upgrade = TargetSpec(controller="friendly", kind="upgrade")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DefeatUnit(friendly_upgrade),
                     DealDamage(2, TargetSpec(controller="any", kind="base"))],
            title="Defeat a friendly upgrade: deal 2 damage to a base",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_UPGRADE),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                CustomEffect(fn=_vane_defeat_upgrade, target=friendly_upgrade),
                DealDamage(2, TargetSpec(
                    controller="any", kind="unit_or_base",
                    predicates=("defender_or_base", "requires_prior_target"))),
            ],
            optional=True,
            deployed_only=True,
        ),
    ]


def _enoch_base_damage(amount: int):
    """Build the "deal ``amount`` to your own base" half of one Enoch option."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import base_damage_after_prevention, _check_game_over
        from swu.engine.events import DamageDealt
        ps = state.player_by_id(source_ci.owner_id)
        base = ps.base_instance
        if base is None:
            return state
        dealt = base_damage_after_prevention(state, base, amount)
        if dealt <= 0:
            return state
        base.damage += dealt
        state.event_log.append(DamageDealt(
            target_instance_id=base.instance_id,
            target_name=base.card_def.display_name,
            owner_id=ps.player_id, amount=dealt, is_base=True))
        _check_game_over(state)
        return state
    return _fn


def _enoch_choose_amount(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2, 3], pick=1)
    return state


@card_ability("ASH", "27")
def _enoch():
    """When Defeated: You may deal up to 6 damage to your base.  The next unit you
    play this phase costs 1 resource less for every 2 damage dealt this way.

    "Up to 6" collapses to a ``choose_two_modal`` (``pick=1``) over 2 / 4 / 6: the
    discount steps every SECOND point, so an odd amount is strictly dominated by the
    even one below it (same discount, one more damage on your own base) — a genuine
    optimal-play collapse, and the trigger's own "you may" already covers 0.  The
    option specs are ``EventAbility`` because Enoch is a UNIT card, so they must never
    be trigger-collected (the Lightmaker SEC_207 rule)."""
    return [
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_enoch_choose_amount)],
            optional=True,
        ),
        EventAbility(effects=[CustomEffect(fn=_enoch_base_damage(2)),
                              NextPlayDiscount(trait=None, amount=1)]),
        EventAbility(effects=[CustomEffect(fn=_enoch_base_damage(4)),
                              NextPlayDiscount(trait=None, amount=2)]),
        EventAbility(effects=[CustomEffect(fn=_enoch_base_damage(6)),
                              NextPlayDiscount(trait=None, amount=3)]),
    ]


def _rancor_keeper_hit(mark: bool):
    """One "deal 1 damage to a base" step of Rancor Keeper's "any number of bases"."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.abilities.resolver import _apply_deal_damage
        if not target_id:
            return state
        _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
        seen = event_ctx.setdefault("excluded_target_ids", set())
        seen.add(target_id)
        if mark:
            state.game_memory.activated_abilities_used_this_round.add(
                f"{source_ci.instance_id}:trig")
        return state
    return _fn


@card_ability("ASH", "32")
def _rancor_keeper():
    """When a friendly unit is dealt damage and survives: Deal 1 damage to any number
    of bases.  Use this ability only once each round.

    "Any number of bases" is at most two, so it is two optional targeted steps over
    the accumulating ``excludes_event_targets`` set (Attack Pattern Delta SOR_106) —
    no select-N decision needed.  The once-per-round limiter is the shared
    ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` gate charged inside the first step, so
    declining does not spend the use (Toro Calican SHD_239).

    DOCUMENTED NARROWING: the observer family sees COMBAT damage only, so ability
    damage to a friendly unit does not fire it (the standing limit — Jabba SEC_2, The
    Elite Squad SEC_143)."""
    base_spec = TargetSpec(controller="any", kind="base", optional=True,
                           predicates=("excludes_event_targets",))
    return TriggerAbility(
        trigger=WhenFriendlyUnitDealtCombatDamage(),
        effects=[CustomEffect(fn=_rancor_keeper_hit(True), target=base_spec),
                 CustomEffect(fn=_rancor_keeper_hit(False), target=base_spec)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


def _repulsor_train_damage(state, source_ci, target_id, event_ctx):
    """Deal 2 damage to the chosen ground unit for each friendly exhausted unit."""
    from swu.abilities.resolver import _apply_deal_damage
    if not target_id:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for arena in (ps.ground_arena, ps.space_arena)
            for ci in arena if ci.exhausted)
    if n <= 0:
        return state
    _apply_deal_damage(state, target_id, 2 * n, source_ci.card_def.display_name)
    return state


@card_ability("ASH", "35")
def _tatooine_repulsor_train():
    """This unit can't be attacked while you control 2 or more exhausted units
    (unless it gains Sentinel).  |  On Attack: Deal 2 damage to a ground unit for each
    friendly exhausted unit.

    The first half is the new board-gated ``CannotBeAttacked`` marker; the second is
    the Zeb Orrelios LAW_45 conditional-MAGNITUDE shape (the amount is computed inside
    one targeted CustomEffect).  Attacking exhausts the train itself, so it is already
    counting one of its own by the time the On Attack resolves — which is exactly the
    printed reading."""
    return [
        CannotBeAttacked(condition=ConditionCheck(
            Condition.CONTROLLER_N_PLUS_EXHAUSTED_UNITS, param=2)),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_repulsor_train_damage, target=TargetSpec(
                controller="any", kind="unit", arena="ground"))],
        ),
    ]


def _purrgil_return(state, source_ci, target_id, event_ctx):
    """Return the chosen friendly non-leader unit to its owner's hand, recording its
    printed cost so the follow-up damage can read it."""
    from swu.abilities.resolver import _apply_return_to_hand
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    cost = int(getattr(res[1].card_def, "cost", None) or 0)
    _apply_return_to_hand(state, target_id)
    event_ctx["prior_target_id"] = target_id
    event_ctx["purrgil_amount"] = cost
    return state


def _purrgil_damage(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    amount = int(event_ctx.get("purrgil_amount") or 0)
    if not target_id or amount <= 0:
        return state
    _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name)
    return state


@card_ability("ASH", "38")
def _purrgil_ultra():
    """When Played/When Defeated: You may return another friendly non-leader unit to
    its owner's hand.  If you do, deal damage to a unit equal to the returned unit's
    cost.

    The shared-``event_ctx`` chain (Nothing Left to Fear LAW_41): the first targeted
    effect bounces and stamps both ``prior_target_id`` and the cost, the second is
    gated by ``requires_prior_target`` so nothing is prompted when the bounce did not
    happen.  ONE effect list registered under BOTH triggers (the Captain Rex SEC_48
    shape)."""
    effects = [
        CustomEffect(fn=_purrgil_return, target=TargetSpec(
            controller="friendly", kind="unit",
            predicates=("non_leader", "not_self"))),
        CustomEffect(fn=_purrgil_damage, target=TargetSpec(
            controller="any", kind="unit",
            predicates=("requires_prior_target",))),
    ]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects), optional=True),
        TriggerAbility(trigger=WhenDefeated(), effects=list(effects), optional=True),
    ]


# ── ash-set:03 — direct damage & removal ─────────────────────────────────────


@card_ability("ASH", "43")
def _corona_four():
    """On Attack: You may give a unit −2/−0 for this phase.
    When Defeated: You may defeat a non-leader unit with 0 power.

    ``power_max`` reads EFFECTIVE power, so a 2/2 knocked to 0 by the On Attack above
    is a legal victim for the When Defeated below — the card's two halves talk to
    each other for free.  Both are ``optional``, so neither prompts with nothing to
    hit (the "don't offer a no-op" rule)."""
    return [
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(-2, 0, TargetSpec(controller="any", kind="unit"),
                                 Duration.THIS_PHASE)],
            optional=True,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                           predicates=("non_leader",),
                                           power_max=0))],
            optional=True,
        ),
    ]


def _pre_vizsla_mass_defeat(state, source_ci, target_id, event_ctx):
    """Defeat any number of non-leader units under a combined remaining-HP budget,
    minting a Mandalorian token per kill (Pre Vizsla ASH_53)."""
    from swu.engine.actions import push_capture_combined_hp
    push_capture_combined_hp(
        state, source_ci, budget=6, disposition="defeat",
        target_controller="any", then_create_token_per_unit="Mandalorian")
    return state


@card_ability("ASH", "53")
def _pre_vizsla():
    """When Played: Defeat any number of non-leader units with a total of 6 or less
    remaining HP.  Create a Mandalorian token for each unit defeated this way.

    The Dismantle the Conspiracy SEC_106 select-under-a-remaining-HP-budget walk with
    its new ``disposition="defeat"`` arm: no captor, both players' units in the pool
    ("any number of non-leader units", Pre Vizsla himself included), and the picks
    killed after the pop so each defeat's own triggers land on a clean stack."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_pre_vizsla_mass_defeat)])


def _cobb_vanth_hurt_and_shield(state, source_ci, target_id, event_ctx):
    """Deal 2 to Cobb Vanth, then Shield the unit that was just played (ASH_60)."""
    from swu.engine.state import Zone
    from swu.engine.actions import _deal_damage_with_shield
    from swu.engine.tokens import attach_token
    played_id = event_ctx.get("played_card_id")
    if not played_id:
        return state
    res = state.find_instance(played_id)
    if res is None:
        return state
    owner_ps, played = res
    if played.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    ps = state.player_by_id(source_ci.owner_id)
    _deal_damage_with_shield(state, ps, source_ci, 2,
                             source_ci.card_def.display_name)
    attach_token(state, owner_ps, played, "Shield")
    return state


@card_ability("ASH", "60")
def _cobb_vanth():
    """When you play another unit: You may deal 2 damage to this unit.  If you do,
    give a Shield token to that unit.

    The "If you do" binding (Bright Hope SOR_99): cost and payoff in ONE
    ``CustomEffect``, so the self-damage can never be paid without the Shield landing.
    "That unit" is located through ``event_ctx["played_card_id"]``, which the
    CardPlayed observer fire threads (Dengar SHD_133)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", exclude_self=True),
        effects=[CustomEffect(fn=_cobb_vanth_hurt_and_shield)],
        optional=True,
    )


@card_ability("ASH", "62")
def _the_mandalorian_ash():
    """Shielded.  If damage would be dealt to another friendly unit, you may defeat a
    Shield token on this unit.  If you do, prevent that damage.

    A ``DamagePrevention`` aura (Vigil SEC_50's shape) with the new
    ``consume_shield_on_source``: a WHOLE-instance prevention priced in a Shield token
    on the Mandalorian, consumed at the single unit-damage chokepoint and offered only
    while he really holds one.  DOCUMENTED DEVIATION — the printed "you may" is taken
    automatically, exactly as the engine's own Shield token prevents without asking;
    a decision pushed from inside the damage step would be replacement-effect
    machinery (the escalation line)."""
    return DamagePrevention(
        amount=0,
        aura_target=TargetSpec(controller="friendly", kind="unit",
                               predicates=("not_self",)),
        consume_shield_on_source=True,
    )


@card_ability("ASH", "67")
def _get_lost():
    """Defeat an upgraded non-leader unit.

    ``upgraded`` is the engine-wide "has ≥1 attached upgrade" predicate, and in SWU a
    Shield / Experience / **Advantage** token counts — so an ASH board hands this
    event far more targets than the printed word suggests, as intended."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader", "upgraded"))),
    ])


@card_ability("ASH", "71")
def _battered_haulcraft():
    """When Played: Deal 1 damage to this unit and 1 damage to an enemy space unit.

    The TARGETED half is listed first so the player is prompted exactly once (the
    Mandalorian SHD_18 rule).  DOCUMENTED DEVIATION: with no enemy space unit on the
    board the whole ability fizzles, so the self-damage is skipped too."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        DealDamage(1, TargetSpec(controller="enemy", kind="unit", arena="space")),
        DealDamage(1, TargetSpec(fixed=SELF)),
    ])


@card_ability("ASH", "83")
def _summa_verminoth():
    """Sentinel.  On Attack: Defeat all other space units.

    "All other" is both players' — ``DefeatAllUnits`` over an arena-narrowed filter
    with ``not_self``.  It resolves in the On Attack window, i.e. before combat
    damage, so the declared defender is usually gone before it can strike back."""
    return TriggerAbility(trigger=OnAttack(), effects=[
        DefeatAllUnits(TargetSpec(controller="any", kind="unit", arena="space",
                                  predicates=("not_self",))),
    ])


# ── ash-set:04 — direct damage & removal ─────────────────────────────────────


def _jerjerrod_can_double(state, source_ci, event_ctx) -> bool:
    """Only offer the doubling when the extra tokens could really be created — i.e.
    a token-UPGRADE creation whose host has since left play is not worth a prompt
    (the engine-wide "don't offer a no-op" rule, via ``CustomEffect.available_fn``)."""
    if int(event_ctx.get("token_creation_count") or 0) <= 0:
        return False
    if event_ctx.get("token_creation_kind") != "upgrade":
        return True
    from swu.engine.state import Zone
    host_id = event_ctx.get("token_creation_host")
    res = state.find_instance(host_id) if host_id else None
    return res is not None and res[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)


def _jerjerrod_double(state, source_ci, target_id, event_ctx):
    """Defeat Moff Jerjerrod, then create as many tokens again (ASH_94).

    The drained record says exactly what was created and for whom, so the top-up is
    one ``apply_token_creation`` call; it passes ``note_token_creation=False``, so the
    new tokens do not re-arm the doubler (he is dead by then in any case).  See the
    ``WhenYouWouldCreateTokens`` docstring for the documented deviation — the original
    N tokens are created normally and this adds another N, rather than the printed
    "create 2N instead"."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import apply_token_creation
    count = int(event_ctx.get("token_creation_count") or 0)
    if count <= 0:
        return state
    state = _apply_defeat_unit(state, source_ci.instance_id)
    apply_token_creation(
        state,
        str(event_ctx.get("token_creation_kind") or ""),
        str(event_ctx.get("token_creation_name") or ""),
        count,
        host_id=event_ctx.get("token_creation_host"),
        ready=bool(event_ctx.get("token_creation_ready")),
        creator_id=event_ctx.get("token_creation_creator"),
    )
    return state


@card_ability("ASH", "94")
def _moff_jerjerrod():
    """Moff Jerjerrod — "If you would create a number of tokens, you may defeat this
    unit.  If you do, create twice that number of tokens instead."

    The one replacement effect in ASH, modelled as the ``WhenYouWouldCreateTokens``
    settle-drain observer: the creation happens, then the controller is offered the
    matching top-up at the price of Jerjerrod's life.  ``optional`` carries the printed
    "you may", so declining costs nothing."""
    return TriggerAbility(
        trigger=WhenYouWouldCreateTokens(),
        effects=[CustomEffect(fn=_jerjerrod_double,
                              available_fn=_jerjerrod_can_double)],
        optional=True,
    )


def _grav_charge_blast(state, source_ci, target_id, event_ctx):
    """Deal 4 damage to the attached unit, then defeat this Grav Charge (ASH_85).

    ``source_ci`` is the HOST (a granted ability resolves from it), so the upgrade is
    re-found on the host by registry key.  Two copies fire twice and each defeats "a"
    Grav Charge — identical cards, so an arbitrary pick is exact."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import _defeat_attached_upgrade
    _apply_deal_damage(state, source_ci.instance_id, 4, "Grav Charge")
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state          # the host died of the 4 — its upgrades went with it
    _, host = res
    for upg in list(host.attached_upgrades):
        cd = upg.card_def
        if (getattr(cd, "set_code", None) == "ASH"
                and str(getattr(cd, "card_number", "")) == "85"):
            _defeat_attached_upgrade(state, upg)
            break
    return state


@card_ability("ASH", "85")
def _grav_charge():
    """When attached unit's attack ends: Deal 4 damage to it and defeat this upgrade.

    A ``GrantedAbility`` so the trigger resolves FROM the host (which is what "it"
    means).  ``WhenAttackEnds`` keys on the attacker having survived, so a Grav Charge
    whose host died in the attack simply goes to the discard with it."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_grav_charge_blast)],
    ))


def _reforge(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly upgrade, then search 8 for a replacement that can
    ride the same host, played at 4 off (Reforge ASH_90)."""
    from swu.engine.actions import (_defeat_attached_upgrade, _find_upgrade_host,
                                    push_search_and_play_upgrade)
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, upgrade = res
    host = _find_upgrade_host(state, target_id)
    if host is None:
        return state
    host_id = host.instance_id
    _defeat_attached_upgrade(state, upgrade)
    push_search_and_play_upgrade(state, source_ci, window=8, host_id=host_id,
                                 cost_reduction=4)
    return state


@card_ability("ASH", "90")
def _reforge_event():
    """Defeat an upgrade on a friendly unit.  If you do, search the top 8 cards of
    your deck for an upgrade that can attach to that unit, reveal it, and play it on
    that unit.  It costs 4 resources less.

    The "If you do" binding (Bright Hope SOR_99) — cost and payoff in ONE effect, so
    the host is captured BEFORE the defeat detaches the upgrade (the JTL_175 ordering
    rule).  ``on_friendly_host`` is the new predicate for "on a friendly unit": the
    plain ``controller="friendly"`` filter reads the UPGRADE's owner, a different
    question."""
    return EventAbility(effects=[
        CustomEffect(fn=_reforge, target=TargetSpec(
            controller="any", kind="upgrade", predicates=("on_friendly_host",))),
    ])


@card_ability("ASH", "92")
def _foundling_rescue():
    """You may defeat a unit with 2 or less remaining HP.  Create a Mandalorian token.

    The token is unconditional, so the OPTIONAL targeted defeat is listed first (one
    prompt — the Mandalorian SHD_18 rule) and the creation trails it."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              hp_remaining_max=2, optional=True)),
        CreateTokenUnit("Mandalorian"),
    ])


def _ravager_shot(state, source_ci, target_id, event_ctx):
    """Have the just-played unit deal its power to a unit in its arena (ASH_102)."""
    from swu.engine.actions import compute_power, _deal_damage_with_shield
    played_id = event_ctx.get("played_card_id")
    if not target_id or not played_id:
        return state
    pres = state.find_instance(played_id)
    tres = state.find_instance(target_id)
    if pres is None or tres is None:
        return state
    _, played = pres
    tps, victim = tres
    amount = compute_power(state, played)
    if amount <= 0:
        return state
    _deal_damage_with_shield(state, tps, victim, amount,
                             played.card_def.display_name)
    return state


@card_ability("ASH", "102")
def _ravager():
    """Restore 2.  When you play a unit: You may have it deal damage equal to its
    power to a unit in the same arena.

    "The same arena" is the arena of the card whose play fired the observer, which the
    CardPlayed fire already pins — hence the new ``same_arena_as_played_card``
    predicate rather than a leading effect stamping ``same_arena`` (that would prompt
    twice; the SHD_18 wart)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit"),
        effects=[CustomEffect(fn=_ravager_shot, target=TargetSpec(
            controller="any", kind="unit",
            predicates=("same_arena_as_played_card",)))],
        optional=True,
    )


def _long_live_the_empire(state, source_ci, target_id, event_ctx):
    """Defeat a friendly Imperial unit, then resource the deck's top card (ASH_103)."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import _resource_top_of_deck
    if not target_id:
        return state
    state = _apply_defeat_unit(state, target_id)
    _resource_top_of_deck(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("ASH", "103")
def _long_live_the_empire_event():
    """Defeat a friendly Imperial unit.  If you do, resource the top card of your
    deck.  Cost and payoff in ONE effect (the "If you do" binding)."""
    return EventAbility(effects=[
        CustomEffect(fn=_long_live_the_empire, target=TargetSpec(
            controller="friendly", kind="unit", traits=("Imperial",))),
    ])


def _ackbar_sacrifice(state, source_ci, target_id, event_ctx):
    """Defeat Ackbar, then free-play any number of cheap space units off the top 10."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import push_search_and_play_multiple
    from swu.cards.models import Unit
    state = _apply_defeat_unit(state, source_ci.instance_id)
    push_search_and_play_multiple(
        state, source_ci, window=10, budget=5,
        eligible=lambda cd: (isinstance(cd, Unit)
                             and "Space" in (getattr(cd, "arenas", ()) or ())))
    return state


@card_ability("ASH", "110")
def _admiral_ackbar():
    """When Played: You may defeat this unit.  If you do, search the top 10 cards of
    your deck for any number of space units with combined cost 5 or less and play each
    of them for free.

    Darth Vader SOR_87's ``push_search_and_play_multiple`` at window 10 / budget 5 with
    a space-arena filter; the sacrifice and the search live in ONE effect so the "If
    you do" cannot be split."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_ackbar_sacrifice)],
        optional=True,
    )


# ── ash-set:05 — direct damage & removal ─────────────────────────────────────


@card_ability("ASH", "112")
def _luke_skywalker_ash():
    """Restore 1.  When Played: If you control at least 4 units, deal 3 damage to
    each enemy unit.

    Luke is already in play when his own When Played resolves, so he counts himself —
    the printed reading.  The condition gates COLLECTION, so under four units nothing
    is offered and nothing fires."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(3, TargetSpec(controller="enemy", kind="unit",
                                          fixed=EACH_ENEMY))],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=4),
    )


def _8d8_hurt_and_dig(state, source_ci, target_id, event_ctx):
    """Deal 1 to another friendly unit, then search 5 for a unit to draw (ASH_118)."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit
    if not target_id:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
    push_deck_search(state, source_ci, count=1, up_to=False, window=5,
                     eligible=lambda cd: isinstance(cd, Unit))
    return state


@card_ability("ASH", "118")
def _8d8():
    """Hidden.  Action [Exhaust]: Deal 1 damage to another friendly unit.  If you do,
    search the top 5 cards of your deck for a unit, reveal it, and draw it.

    Cost and payoff in ONE effect (the "If you do" binding).  The ability is gated on
    controlling a SECOND unit — with 8D8 alone in play the exhaust would buy nothing
    (the "don't offer a no-op" rule)."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_8d8_hurt_and_dig, target=TargetSpec(
            controller="friendly", kind="unit", predicates=("not_self",)))],
        title="Damage a friendly unit to dig for a unit",
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=2),
    )


def _soruna_reveal_and_burn(state, source_ci, target_id, event_ctx):
    """Reveal a same-cost unit from hand, then deal 3 to the chosen unit (ASH_132)."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import record_hand_discard
    from swu.cards.models import Unit
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, victim = res
    cost = getattr(victim.card_def, "cost", None)
    ps = state.player_by_id(source_ci.owner_id)
    revealed = next((c for c in ps.hand if isinstance(c.card_def, Unit)
                     and getattr(c.card_def, "cost", None) == cost), None)
    if revealed is None:
        return state
    record_hand_discard(state, ps.player_id, kind="reveal")
    _apply_deal_damage(state, target_id, 3, source_ci.card_def.display_name)
    return state


@card_ability("ASH", "132")
def _queen_soruna():
    """When Played/On Attack: You may reveal a unit from your hand.  If you do, deal 3
    damage to a unit with the same cost as the revealed unit.

    ONE prompt: the new ``cost_eq_a_hand_unit`` predicate offers exactly the units
    whose cost some hand unit could name, and the reveal follows from the pick.
    DOCUMENTED SIMPLIFICATION — with several equal-cost hand units the first is
    revealed (the K-2SO SOR_145 fungible-choice convention); they are interchangeable
    for this card's purpose."""
    effects = [CustomEffect(fn=_soruna_reveal_and_burn, target=TargetSpec(
        controller="any", kind="unit", predicates=("cost_eq_a_hand_unit",)))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects), optional=True),
        TriggerAbility(trigger=OnAttack(), effects=list(effects), optional=True),
    ]


def _wipe_them_out(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, excess_damage_to_unit=True)
    return state


@card_ability("ASH", "137")
def _wipe_them_out_event():
    """Attack with a unit.  For this attack, you may deal its excess damage to
    another unit in the same arena.

    The new ``excess_damage_to_unit`` granted-attack rider: Overwhelm's own excess
    computation, delivered by ``push_select_damage`` at one target (the whole amount
    on one unit, which IS "another unit") with the finish carrying the "you may"."""
    return EventAbility(effects=[CustomEffect(fn=_wipe_them_out)])


@card_ability("ASH", "138")
def _turning_the_tide():
    """Choose a unit.  Deal 1 damage to it for each friendly unit.

    ``DealDamageEqualTo`` at the new arena-blind ``source_controller_units`` count —
    "friendly" is measured from the EVENT's controller."""
    return EventAbility(effects=[
        DealDamageEqualTo(TargetSpec(controller="any", kind="unit"),
                          count="source_controller_units"),
    ])


def _mortar_trooper_barrage(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=3,
                       arena="ground")
    return state


@card_ability("ASH", "142")
def _mortar_trooper():
    """Action [Exhaust]: Deal 1 damage to each of up to 3 ground units.

    IG-2000 JTL_140's ``select_damage`` with the Twin Laser Turret JTL_172 arena
    narrowing — distinct picks are what "each of up to 3" means."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_mortar_trooper_barrage)],
        title="Deal 1 damage to each of up to 3 ground units",
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=1),
    )


def _justifier_snipe(state, source_ci, target_id, event_ctx):
    """Deal 1; if that killed it, hand out an Advantage token (ASH_146)."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import push_select_token
    from swu.engine.state import Zone
    if not target_id:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
    # ``find_instance`` reaches the DISCARD, so "defeated" is an ARENA test.
    res = state.find_instance(target_id)
    gone = res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)
    if gone:
        push_select_token(state, source_ci, token_type="Advantage", max_targets=1)
    return state


@card_ability("ASH", "146")
def _justifier():
    """When Played/On Attack: You may deal 1 damage to a unit.  If that unit is
    defeated this way, give an Advantage token to a unit.

    Damage and payoff in ONE effect so "defeated this way" is exactly the instance
    this card dealt; the token rides ``select_token``, pushed after the kill so it
    resolves on a clean stack."""
    effects = [CustomEffect(fn=_justifier_snipe, target=TargetSpec(
        controller="any", kind="unit"))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects), optional=True),
        TriggerAbility(trigger=OnAttack(), effects=list(effects), optional=True),
    ]


# ── ash-set:06 — direct damage & removal ─────────────────────────────────────


def _cyborg_mech_choose(state, source_ci, target_id, event_ctx):
    """Offer only the modes that have a legal ground target (ASH_147)."""
    from swu.engine.actions import push_choose_modal
    from swu.engine.state import Zone
    undamaged, damaged = False, False
    for ps in state.players:
        for ci in ps.ground_arena:
            if ci.damage > 0:
                damaged = True
            else:
                undamaged = True
    options = ([1] if undamaged else []) + ([2] if damaged else [])
    if not options:
        return state
    push_choose_modal(state, source_ci, option_indices=options, pick=1)
    return state


@card_ability("ASH", "147")
def _the_cyborg_mech():
    """Grit.  When Played: Either deal 2 damage to an undamaged ground unit or 5
    damage to a damaged ground unit.

    ``push_choose_modal(pick=1)`` over two option specs (Enoch ASH_27's shape); they
    are ``EventAbility`` because this is a UNIT card, so they are never
    trigger-collected (the Lightmaker SEC_207 rule).  A mode with no legal target is
    not offered, so the choice is never a dead prompt."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_cyborg_mech_choose)]),
        EventAbility(effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", arena="ground",
            predicates=("undamaged",)))]),
        EventAbility(effects=[DealDamage(5, TargetSpec(
            controller="any", kind="unit", arena="ground",
            predicates=("damaged",)))]),
    ]


def _ninth_sister_discard(state, source_ci, target_id, event_ctx):
    """An opponent discards a card; spread its cost as damage (ASH_148)."""
    from swu.engine.state import Zone
    from swu.engine.actions import (push_distribute_damage, record_hand_discard,
                                    note_hand_or_deck_discard)
    opp = next((p for p in state.players if p.player_id != source_ci.owner_id), None)
    if opp is None or not opp.hand:
        return state
    ci = opp.hand.pop(0)          # first-card discard simplification (K-2SO SOR_145)
    ci.zone = Zone.DISCARD
    opp.discard.append(ci)
    record_hand_discard(state, opp.player_id)
    note_hand_or_deck_discard(state, ci)
    amount = int(getattr(ci.card_def, "cost", 0) or 0)
    push_distribute_damage(state, source_ci, amount,
                           target_controller="any", up_to=True)
    return state


@card_ability("ASH", "148")
def _ninth_sister():
    """Overwhelm.  When Played: An opponent discards a card from their hand.  You may
    deal damage equal to its cost divided as you choose among any number of units.

    ``up_to=True`` is the printed "you may" (assigning nothing is legal).  DOCUMENTED
    SIMPLIFICATION: the opponent's FIRST hand card is discarded (the standing
    first-card-discard convention)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_ninth_sister_discard)])


@card_ability("ASH", "151")
def _operation_cinder():
    """Deal 5 damage to your base.  Then, deal 5 damage to each unit.

    Both halves are fixed-target, so the event resolves with no prompt at all — and
    in the printed order, base first."""
    return EventAbility(effects=[
        DealDamage(5, TargetSpec(controller="friendly", kind="base",
                                 fixed=EACH_FRIENDLY)),
        DealDamage(5, TargetSpec(controller="any", kind="unit", fixed=EACH_IN_PLAY)),
    ])


@card_ability("ASH", "153")
def _green_leader():
    """When Defeated: You may deal 2 damage to a unit."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


@card_ability("ASH", "158")
def _han_solo_ash():
    """Saboteur.  When Played: Deal 3 damage to this unit.  Give 3 Advantage tokens
    to a unit.

    The TARGETED half is listed FIRST so the player is prompted exactly once (the
    Mandalorian SHD_18 rule); Han is a 3/7, so taking his own 3 damage after the
    tokens changes nothing."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        GiveToken("Advantage", TargetSpec(controller="any", kind="unit"), count=3),
        DealDamage(3, TargetSpec(fixed=SELF)),
    ])


@card_ability("ASH", "161")
def _zeb_orrelios_ash():
    """When Played: Give 3 Advantage tokens to another unit.
    When a friendly upgrade is defeated: Deal 1 damage to a base.

    The second clause is the new ``WhenFriendlyUpgradeDefeated`` settle-drain
    observer.  A token upgrade IS an upgrade, so an expiring Advantage token — the
    ASH set mechanic, and what Zeb's own first clause hands out — fires it."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[
            GiveToken("Advantage", TargetSpec(controller="any", kind="unit",
                                              predicates=("not_self",)), count=3),
        ]),
        TriggerAbility(
            trigger=WhenFriendlyUpgradeDefeated(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
        ),
    ]


def _reckless_sacrifice_discard(state, source_ci, target_id, event_ctx):
    """Discard a unit from hand and record its cost as the damage threshold."""
    from swu.engine.state import Zone
    from swu.cards.models import Unit
    from swu.engine.actions import record_hand_discard, note_hand_or_deck_discard
    ps = state.player_by_id(source_ci.owner_id)
    units = [c for c in ps.hand if isinstance(c.card_def, Unit)]
    if not units:
        return state
    # The CHEAPEST unit — it maximises the legal targets, and is the natural pitch
    # (the K-2SO SOR_145 fungible-choice convention).
    ci = min(units, key=lambda c: getattr(c.card_def, "cost", 0) or 0)
    ps.hand.remove(ci)
    ci.zone = Zone.DISCARD
    ps.discard.append(ci)
    record_hand_discard(state, ps.player_id)
    note_hand_or_deck_discard(state, ci)
    event_ctx["cost_gt_threshold"] = int(getattr(ci.card_def, "cost", 0) or 0)
    return state


@card_ability("ASH", "163")
def _reckless_sacrifice():
    """Discard a unit from your hand.  Deal 5 damage to a unit that costs more than
    the discarded card.

    The Force Throw SOR_167 "record then gate" shape: a leading no-target
    ``CustomEffect`` does the discard and stamps the threshold, then the targeted hit
    is narrowed by the new ``cost_gt_event_threshold`` predicate — so with no unit in
    hand nothing is offered."""
    return EventAbility(effects=[
        CustomEffect(fn=_reckless_sacrifice_discard),
        DealDamage(5, TargetSpec(controller="any", kind="unit",
                                 predicates=("cost_gt_event_threshold",))),
    ])


# ── ash-set:07 — direct damage & removal ─────────────────────────────────────


@card_ability("ASH", "165")
def _clan_vizsla_soldier():
    """When Defeated: You may defeat an upgrade.

    Any upgrade, either side of the board — the engine-wide ``kind="upgrade"``
    convention already excludes Shield / Experience / Advantage tokens."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade"))],
        optional=True,
    )


@card_ability("ASH", "170")
def _desert_sharpshooter():
    """When Played: You may deal 2 damage to an upgraded ground unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground",
                                          predicates=("upgraded",)))],
        optional=True,
    )


def _pegasus_ready(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly upgrade, then ready this unit (ASH_171)."""
    from swu.engine.actions import _defeat_attached_upgrade
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, upgrade = res
    _defeat_attached_upgrade(state, upgrade)
    source_ci.exhausted = False
    return state


@card_ability("ASH", "171")
def _pegasus_tri_wing():
    """When Played: You may defeat a friendly upgrade.  If you do, ready this unit.

    Cost and payoff in ONE effect (the "If you do" binding), and the optional trigger
    is never offered with no friendly upgrade to spend."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_pegasus_ready, target=TargetSpec(
            controller="any", kind="upgrade", predicates=("on_friendly_host",)))],
        optional=True,
    )


@card_ability("ASH", "174")
def _starfortress_heavy_bomber():
    """When Played: You may deal 6 damage to a non-<uq> ground unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(6, TargetSpec(controller="any", kind="unit",
                                          arena="ground",
                                          predicates=("non_unique",)))],
        optional=True,
    )


def _scout_walker_snipe(state, source_ci, target_id, event_ctx):
    """Deal 3 to a ground unit; a kill pays 3 Advantage tokens to this unit."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.state import Zone
    from swu.engine.tokens import attach_token
    if not target_id:
        return state
    _apply_deal_damage(state, target_id, 3, source_ci.card_def.display_name)
    res = state.find_instance(target_id)
    gone = res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)
    if not gone:
        return state
    live = state.find_instance(source_ci.instance_id)
    if live is None:
        return state
    ps, walker = live
    for _ in range(3):
        attach_token(state, ps, walker, "Advantage")
    return state


@card_ability("ASH", "176")
def _imposing_scout_walker():
    """When Played: You may deal 3 damage to a ground unit.  If it's defeated this
    way, give 3 Advantage tokens to this unit.

    Damage and payoff in ONE effect so "defeated this way" is exactly this instance;
    ``find_instance`` reaches the DISCARD, so the kill test is an ARENA test."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_scout_walker_snipe, target=TargetSpec(
            controller="any", kind="unit", arena="ground"))],
        optional=True,
    )


def _rancor_arrival(state, source_ci, target_id, event_ctx):
    """5 to your own base, then TWO separate 5s onto one enemy ground unit."""
    from swu.abilities.resolver import _apply_deal_damage
    ps = state.player_by_id(source_ci.owner_id)
    base = ps.base_instance
    if base is not None:
        _apply_deal_damage(state, base.instance_id, 5,
                           source_ci.card_def.display_name)
    if not target_id:
        return state
    # Two separate instances, as printed — a Shield eats only the first (the Heavy
    # Blaster Cannon LOF_171 lesson).
    for _ in range(2):
        _apply_deal_damage(state, target_id, 5, source_ci.card_def.display_name)
    return state


def _rancor_base_burn(state, source_ci, target_id, event_ctx):
    """Deal 1 to a base for every 5 damage on your own base (ASH_179 On Attack)."""
    from swu.abilities.resolver import _apply_deal_damage
    if not target_id:
        return state
    own_base = state.player_by_id(source_ci.owner_id).base_instance
    amount = (own_base.damage // 5) if own_base is not None else 0
    if amount <= 0:
        return state
    _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name)
    return state


@card_ability("ASH", "179")
def _boba_fetts_rancor():
    """When Played: Deal 5 damage to your base.  Then, deal 5 damage to an enemy
    ground unit.  Then, deal 5 damage to the same unit.
    On Attack: You may deal 1 damage to a base for every 5 damage on your base.

    All three When Played clauses live in ONE targeted effect — one prompt, and "the
    same unit" is free.  The On Attack is the Zeb LAW_45 conditional-magnitude read."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_rancor_arrival, target=TargetSpec(
                controller="enemy", kind="unit", arena="ground")),
        ]),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_rancor_base_burn, target=TargetSpec(
                controller="any", kind="base"))],
            optional=True,
        ),
    ]


def _whistling_birds_blast(state, source_ci, target_id, event_ctx):
    """Deal 2 to each unit the damaged opponent controls in the host's arena."""
    from swu.abilities.resolver import _apply_deal_damage
    host_res = state.find_instance(source_ci.instance_id)
    if host_res is None:
        return state
    host_ps, host = host_res
    opp = next((p for p in state.players if p.player_id != host_ps.player_id), None)
    if opp is None:
        return state
    from swu.engine.state import Zone
    arena = (opp.ground_arena if host.zone == Zone.GROUND_ARENA
             else opp.space_arena)
    for ci in list(arena):
        _apply_deal_damage(state, ci.instance_id, 2, "Whistling Birds")
    return state


@card_ability("ASH", "183")
def _whistling_birds():
    """Attach to a non-Vehicle unit.  Attached unit gains: "When Attack Ends: If this
    unit dealt combat damage to an opponent's base, deal 2 damage to each unit that
    opponent controls in this unit's arena."

    ``GrantedAbility`` so the trigger resolves FROM the host ("this unit"), over
    ``WhenAttackEnds(require_base_damage=True)`` — Maul LAW_54's narrowing verbatim.
    In a two-player game "that opponent" is the one opponent."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenAttackEnds(require_base_damage=True),
        effects=[CustomEffect(fn=_whistling_birds_blast)],
    ))


# ── ash-set:08 — Direct damage & removal ─────────────────────────────────────


def _minefield_choose_arena(state, source_ci, target_id, event_ctx):
    """"Choose an arena" — the one-of-two ``choose_two_modal`` SELECTOR over the
    arena options at ability indices 1 (ground) and 2 (space) (the Confidence in
    Victory SEC_145 / Lightmaker SEC_207 shape)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _minefield_arm(state, source_ci, arena):
    """Record the chosen arena against this event's instance and keep the spent
    event addressable as an aura source for the rest of the phase.

    Two ledgers, both already in place: ``chosen_arenas`` is what the
    ``in_source_chosen_arena`` predicate reads (so ONE aura spec covers whichever
    arena was picked), and ``phase_aura_sources`` is what lets a card sitting in
    the discard keep granting until the phase rolls over — which IS the printed
    "for this phase" (Pyrrhic Assault TWI_103)."""
    gm = state.game_memory
    gm.chosen_arenas[source_ci.instance_id] = arena
    if source_ci.instance_id not in gm.phase_aura_sources:
        gm.phase_aura_sources.append(source_ci.instance_id)
    return state


def _minefield_ground(state, source_ci, target_id, event_ctx):
    return _minefield_arm(state, source_ci, "ground")


def _minefield_space(state, source_ci, target_id, event_ctx):
    return _minefield_arm(state, source_ci, "space")


@card_ability("ASH", "186")
def _treacherous_minefield():
    """ASH_186 — Treacherous Minefield (Event, Plan, cost 2): "Choose an arena.  For
    this phase, each unit in that arena gains: 'On Attack: Deal 2 damage to this
    unit.'"

    Index 0 is the EventAbility controller pushing the arena SELECTOR; indices 1/2
    are the two arena options, registered as ``TriggerAbility`` because this is an
    EVENT card — ``_resolve_event_ability`` walks every EventAbility spec, so an
    option must not be one (the SEC_145 convention).  Each records the pick and arms
    the phase aura.

    Index 3 is the aura itself: ONE ``AuraGrantedAbility`` for both arenas, pinned to
    the chosen one by the ``in_source_chosen_arena`` predicate (the Implicate SEC_231
    trick of reading the choice back off a ledger rather than registering a spec per
    branch).  ``controller="any"`` is the printed "each unit", and the grant covers
    units that enter that arena later this phase, exactly as an aura should.  The
    granted damage targets ``SELF`` — the ability resolves FROM the attacking unit,
    so "this unit" is that attacker."""
    return [
        EventAbility(effects=[CustomEffect(fn=_minefield_choose_arena)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_minefield_ground)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_minefield_space)]),
        AuraGrantedAbility(
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("in_source_chosen_arena",)),
            ability=TriggerAbility(
                trigger=OnAttack(),
                effects=[DealDamage(2, TargetSpec(kind="unit", fixed=SELF))],
            ),
        ),
    ]


@card_ability("ASH", "187")
def _reckoning():
    """ASH_187 — Reckoning (Event, Plan, cost 3): "Deal damage to a unit equal to the
    total amount of damage on all units you control."

    The new ``source_controller_units_damage`` scaling count — the damage-summing
    sibling of ``source_controller_units`` (Turning the Tide ASH_138) — over both of
    the controller's arenas.  A friendly target correctly contributes its own damage
    to the total (the count is read as a snapshot before any is dealt)."""
    return EventAbility(effects=[DealDamageEqualTo(
        TargetSpec(controller="any", kind="unit"),
        count="source_controller_units_damage",
    )])


@card_ability("ASH", "194")
def _snub_fighter_squadron():
    """ASH_194 — Snub Fighter Squadron (Unit, Fighter Underworld Vehicle, 4/3;
    Ambush): "When Played: Deal 1 damage to a space unit."

    Ambush is the keyword layer.  A mandatory ``WhenPlayed`` ``DealDamage`` over any
    controller's space unit — the squadron itself is a legal target, as printed, and
    with no space unit at all it fizzles unprompted."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                          arena="space"))],
    )


@card_ability("ASH", "196")
def _gorian_shards_corsair():
    """ASH_196 — Gorian Shard's Corsair (Unit, Capital Ship Underworld Vehicle, 6/5):
    "Damage dealt by friendly Underworld cards is unpreventable.
    When Played/On Attack: You may deal 2 damage to a unit."

    The static line is the new ``UnpreventableDamage`` marker, read at the single
    unit-damage chokepoint against the card DEALING the instance (recovered from the
    ``dealer_source_id`` the chokepoint now carries) — so a matching dealer skips
    every prevention AND the Shield token.  "Cards" covers the Corsair's own combat
    damage, an Underworld ability's damage, and a spent Underworld EVENT (find_instance
    reaches the discard).

    "When Played/On Attack" is the two-trigger shape (Captain Rex SEC_48): one
    optional ``DealDamage`` registered under each."""
    return [
        UnpreventableDamage(traits=("Underworld",), controller="friendly"),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            optional=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            optional=True,
        ),
    ]


def _ddc_defender_shot(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the chosen unit AND exhaust it, in one effect so the two
    halves can never land on different units (the Kylo Ren SHD_141 rule).  The
    exhaust honours Protection ("can't be exhausted by enemy card abilities") and is
    skipped for a unit the damage just defeated — an ARENA test, since
    ``find_instance`` reaches the discard."""
    from swu.abilities.resolver import _apply_deal_damage, _target_protected
    from swu.engine.state import Zone
    if not target_id:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    res = state.find_instance(target_id)
    if res is None or res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    if _target_protected(state, target_id, source_ci, "exhaust"):
        return state
    res[1].exhausted = True
    return state


@card_ability("ASH", "210")
def _ddc_defender():
    """ASH_210 — DDC Defender (Upgrade, Item Weapon, cost 1, +1/+0): "Attach to a
    non-Vehicle unit.  Attached unit gains: 'On Defense: You may deal 1 damage to a
    unit in this unit's arena and exhaust it.'"

    "Attach to a non-Vehicle unit" is parsed by ``_upgrade_target_spec`` onto the
    ``non_vehicle`` predicate, so the restriction holds at every attachment site with
    no registration.  "On Defense" IS ``WhenAttacked`` (Canto Bight Security LAW_121),
    wrapped in a ``GrantedAbility`` so it resolves FROM the host — which is also why
    "this unit's arena" is ``same_arena_as_source`` and not ``same_arena_as_host``
    (Tam Ryvora JTL_35)."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CustomEffect(fn=_ddc_defender_shot, target=TargetSpec(
            controller="any", kind="unit",
            predicates=("same_arena_as_source",)))],
        optional=True,
    ))


# ── ash-set:11 — Card advantage & disruption ─────────────────────────────────


@card_ability("ASH", "232")
def _full_of_surprises():
    """ASH_232 — Full of Surprises (Event, cost 2): "Return an upgrade that costs 2 or
    less to its owner's hand.  Give a Shield token to a unit."

    TWO separate single-effect ``EventAbility`` specs rather than one two-effect
    ability (the Sabine's Masterpiece JTL_250 pattern): ``_resolve_event_ability``
    walks them in order, so the Shield still lands when no cheap upgrade exists —
    the resolve_effects walker would otherwise skip the earlier clause."""
    return [
        EventAbility(effects=[ReturnToHand(TargetSpec(
            controller="any", kind="upgrade", cost_max=2))]),
        EventAbility(effects=[GiveToken("Shield", TargetSpec(
            controller="any", kind="unit"))]),
    ]


def _sense_through_the_force(state, source_ci, target_id, event_ctx):
    """"Choose a number, then search the top 5 … and draw it.  If its cost is the
    chosen number, you may give 3 Advantage tokens to a Force unit."

    ``push_choose_number``'s new ``then`` continuation carries the number into a
    ``deck_search``, whose DRAW finish is the only place the drawn card's cost is
    known; the payoff is an ordinary one-target ``select_token``, whose always-legal
    finish IS the printed "you may"."""
    from swu.engine.actions import push_choose_number
    push_choose_number(state, source_ci, lo=0, hi=10, then={
        "kind": "deck_search_tokens_if_cost", "window": 5,
        "token": "Advantage", "count": 3, "trait": "Force",
    })
    return state


@card_ability("ASH", "235")
def _sense_through_the_force_event():
    """ASH_235 — Sense Through the Force (Event, Force, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_sense_through_the_force)])


def _far_far_away_friendly(state, source_ci, target_id, event_ctx):
    """Return the chosen FRIENDLY unit and record that it happened — the "If you do"
    gate for the second half (the Nothing Left to Fear LAW_41 shared-event_ctx
    chain)."""
    from swu.abilities.resolver import _apply_return_to_hand
    if not target_id:
        return state
    _apply_return_to_hand(state, target_id)
    event_ctx["prior_target_id"] = target_id
    return state


def _far_far_away_enemy(state, source_ci, target_id, event_ctx):
    """Return the chosen ENEMY unit (only reached when the friendly half happened —
    the target spec carries ``requires_prior_target``)."""
    from swu.abilities.resolver import _apply_return_to_hand
    if target_id:
        _apply_return_to_hand(state, target_id)
    return state


@card_ability("ASH", "236")
def _far_far_away():
    """ASH_236 — Far Far Away (Event, cost 3): "Return a friendly non-leader unit to
    its owner's hand.  If you do, return an enemy non-leader unit to its owner's
    hand." """
    return EventAbility(effects=[
        CustomEffect(fn=_far_far_away_friendly, target=TargetSpec(
            controller="friendly", kind="unit", predicates=("non_leader",))),
        CustomEffect(fn=_far_far_away_enemy, target=TargetSpec(
            controller="enemy", kind="unit",
            predicates=("non_leader", "requires_prior_target"))),
    ])


def _exploit_advantage(state, source_ci, target_id, event_ctx):
    """"Defeat a friendly upgrade.  If you do, draw 2 cards" — cost and payoff in ONE
    effect, so an unpaid cost can never draw (the Bright Hope SOR_99 binding).  With
    no friendly upgrade the effect has no candidate and fizzles unprompted."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import _draw_cards
    if not target_id:
        return state
    _apply_defeat_unit(state, target_id)
    _draw_cards(state, state.player_by_id(source_ci.owner_id), 2)
    return state


@card_ability("ASH", "246")
def _exploit_advantage_event():
    """ASH_246 — Exploit Advantage (Event, cost 2): "Defeat a friendly upgrade.  If
    you do, draw 2 cards."

    ``on_friendly_host`` is the right filter for "a friendly upgrade" (Reforge
    ASH_90): the plain ``controller="friendly"`` test reads the UPGRADE's owner,
    which is a different question once an upgrade sits on an enemy unit."""
    return EventAbility(effects=[CustomEffect(
        fn=_exploit_advantage, target=TargetSpec(
            controller="any", kind="upgrade",
            predicates=("on_friendly_host",)))])


def _one_must_destroy(state, source_ci, target_id, event_ctx):
    """"Defeat a friendly non-leader unit.  Then, you may play that unit from your
    discard pile for free" — one effect: the defeat, then a ``play_from_hand`` loop
    whitelisted to exactly that corpse, with ``up_to`` carrying the "you may"."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import push_play_from_hand
    if not target_id:
        return state
    _apply_defeat_unit(state, target_id)
    ps = state.player_by_id(source_ci.owner_id)
    if any(c.instance_id == target_id for c in ps.discard):
        push_play_from_hand(state, source_ci, free=True, from_discard=True,
                            eligible_ids=frozenset({target_id}), up_to=True)
    return state


@card_ability("ASH", "247")
def _one_must_destroy_to_create():
    """ASH_247 — One Must Destroy to Create (Event, cost 3).

    The replay is offered only when the defeated unit really landed in the
    controller's discard — a token ceases to exist, and a defeat replacement may
    send it elsewhere."""
    return EventAbility(effects=[CustomEffect(
        fn=_one_must_destroy, target=TargetSpec(
            controller="friendly", kind="unit", predicates=("non_leader",)))])


def _watermonger_draw_discard(state, source_ci, target_id, event_ctx):
    """"You may draw a card.  If you do, discard a card" — both halves in ONE effect
    so the discard can never happen without the draw; first-card discard (the K-2SO
    SOR_145 convention)."""
    from swu.engine.actions import _draw_cards, note_hand_or_deck_discard
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if _draw_cards(state, ps, 1) <= 0 or not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    return state


@card_ability("ASH", "260")
def _mos_espa_watermonger():
    """ASH_260 — Mos Espa Watermonger (Unit, Fringe, 1/3): "When Played: You may draw
    a card.  If you do, discard a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_watermonger_draw_discard)],
        optional=True,
    )


# ── ash-set:10 — Card advantage & disruption ─────────────────────────────────


def _bothan5_capture_corpse(state, source_ci, target_id, event_ctx):
    """Have Bothan-5 capture the just-defeated unit OUT OF THE DISCARD PILE.

    ``_apply_capture`` only relocates an ARENA unit, so the discard-pile leg is
    spelled out here: the corpse leaves its owner's discard for the captor's capture
    pile, facedown and tagged ``captured_by``, exactly as that helper leaves an arena
    captive.  The trigger is optional, so it resolves on a LATER apply — by which
    time ``_defeat_unit`` has really homed the corpse in the discard (the Expendable
    Mercenary LAW_159 timing rule)."""
    from swu.engine.state import Zone
    from swu.engine.events import UnitCaptured
    # ``defeated_id`` (a plain string) rather than ``defeated_ci`` — the instance in
    # the event_ctx is a pre-defeat snapshot that does not survive the optional
    # trigger's decision round-trip.
    dead_id = event_ctx.get("defeated_id")
    if not dead_id:
        return state
    cap_res = state.find_instance(source_ci.instance_id)
    if cap_res is None or cap_res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state
    captor_ps, captor_ci = cap_res
    owner_ps = corpse = None
    for ps in state.players:
        found = next((c for c in ps.discard if c.instance_id == dead_id), None)
        if found is not None:
            owner_ps, corpse = ps, found
            break
    if corpse is None:
        return state
    owner_ps.discard.remove(corpse)
    corpse.damage = 0
    corpse.exhausted = False
    corpse.face_down = True
    corpse.deployed = False
    corpse.captured_by = captor_ci.instance_id
    corpse.zone = Zone.CAPTURE_PILE
    captor_ps.capture_pile.append(corpse)
    state.event_log.append(UnitCaptured(
        captor_instance_id=captor_ci.instance_id,
        captor_name=captor_ci.card_def.display_name,
        captured_instance_id=corpse.instance_id,
        captured_name=corpse.card_def.display_name,
        captor_player_id=captor_ps.player_id,
        owner_id=corpse.owner_id,
    ))
    return state


@card_ability("ASH", "128")
def _bothan_5():
    """ASH_128 — Bothan-5 (Unit, Droid Underworld, 4/5, unique): "When another
    friendly non-Vehicle unit is defeated: You may have this unit capture that unit
    from your discard pile.  Use this ability only once each round."

    A ``WhenUnitDefeated`` observer narrowed to friendly non-Vehicle units and
    excluding Bothan-5 itself, with the shared once-per-round limiter
    (``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` + the ``{iid}:trig`` marker charged
    on ACCEPT — Toro Calican SHD_239), so declining is not a use."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(
            filter=TargetSpec(controller="friendly", kind="unit",
                              predicates=("non_vehicle", "not_self"))),
        effects=[CustomEffect(fn=_bothan5_capture_corpse)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


@card_ability("ASH", "169")
def _axe_woves():
    """ASH_169 — Axe Woves (Unit, Mandalorian, 2/4, unique): "When you draw 1 or more
    cards (including during the regroup phase): Give an Advantage token to this
    unit."

    The ``WhenYouDraw`` settle-drain observer with the new ``any_phase`` opt-in —
    the draw ledger now records REGROUP draws too, but only a trigger printing that
    parenthetical reads them, so every other WhenYouDraw card keeps its
    action-phase-only wording."""
    return TriggerAbility(
        trigger=WhenYouDraw(any_phase=True),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    )


def _razor_crest_discard_for_power(state, source_ci, target_id, event_ctx):
    """"You may discard a card from your hand.  If you do, this unit gets +2/+0 for
    this attack" — cost and payoff in ONE effect so an unpaid cost can never apply
    the buff (the Bright Hope SOR_99 "if you do" binding).  First-card discard, the
    K-2SO SOR_145 convention."""
    from swu.engine.actions import note_hand_or_deck_discard
    from swu.engine.state import Zone, Modifier
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=source_ci.instance_id,
        kind="stats",
        value={"power": 2, "hp": 0},
        duration="this_attack",
    ))
    return state


@card_ability("ASH", "172")
def _razor_crest_ash():
    """ASH_172 — Razor Crest (Unit, Transport Vehicle, 3/5, unique; Saboteur): "On
    Attack: You may discard a card from your hand.  If you do, this unit gets +2/+0
    for this attack."

    Saboteur is the keyword layer.  ``CONTROLLER_HAND_SIZE_MIN`` gates collection so
    an empty hand is never a dead prompt."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_razor_crest_discard_for_power)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1),
    )


@card_ability("ASH", "185")
def _intimidation():
    """ASH_185 — Intimidation (Event, cost 2): "If you control a unit with 4 or more
    power, draw 2 cards."

    An ``EventAbility`` has no ``condition`` field, so the gate is a plain
    ``ConditionalEffect`` around the draw (Petition the Senate TWI_100) over the
    existing ``CONTROLLER_HAS_UNIT_POWER_MIN`` atom, which reads EFFECTIVE power."""
    return EventAbility(effects=[ConditionalEffect(
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_POWER_MIN, param=4),
        if_true=[DrawCards(2)],
        if_false=[],
    )])


def _remnant_lookouts_peek_hand(state, source_ci, target_id, event_ctx):
    """"Look at an opponent's hand.  You may discard a card from it.  If you do, they
    draw a card" — Bazine Netal SHD_184 verbatim: ``push_name_and_discard`` carries
    the opponent's hand to the controller, offers only names actually present, and
    ``discarder_draws`` is the "if you do" rider."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, optional=True, discarder_draws=True)
    return state


@card_ability("ASH", "220")
def _remnant_lookouts():
    """ASH_220 — Remnant Lookouts (Unit, Imperial Trooper, 3/3): "When Played: Look at
    an opponent's hand.  You may discard a card from it.  If you do, they draw a
    card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_remnant_lookouts_peek_hand)],
    )


def _camtono_peek(state, source_ci, target_id, event_ctx):
    """"Look at the top card of your deck.  If it costs 2 or less, you may play it
    for free."  A cheap top card gets the ``may_play`` peek at ``free=True``; an
    expensive one still gets the ``reveal_only`` look, so the reveal is never
    invisible (the C-3PO SOR_238 convention)."""
    from swu.engine.actions import push_peek_top
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    cost = getattr(ps.deck[0].card_def, "cost", None) or 0
    if cost <= 2:
        push_peek_top(state, source_ci, mode="may_play", free=True)
    else:
        push_peek_top(state, source_ci, mode="reveal_only")
    return state


@card_ability("ASH", "229")
def _camtono():
    """ASH_229 — Camtono (Upgrade, Item, cost 2, +0/+0): "Attached unit gains: 'When
    Attack Ends: Look at the top card of your deck.  If it costs 2 or less, you may
    play it for free.'"

    ``GrantedAbility`` so it resolves FROM the host — "your deck" is then the HOST's
    controller's deck, which is what makes the upgrade worth putting on a unit that
    may change hands."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_camtono_peek)],
    ))


def _improvised_identity_search(state, source_ci, target_id, event_ctx):
    """Search the top 3 for a ground unit, discard it, then attack with this unit
    borrowing the discarded unit's abilities.

    The attack rides ``push_deck_search``'s new ``then_borrowed_attack_by`` rider,
    settled at the ``discard`` disposition's finish (after the pop), so the granted
    attack lands on a clean stack with the discarded card as the borrow LENDER —
    ``state.borrowed_ability_sources`` resolves it with ``find_instance``, which
    reaches the discard."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit

    def _eligible(cd) -> bool:
        return isinstance(cd, Unit) and "Ground" in (getattr(cd, "arenas", ()) or ())

    push_deck_search(state, source_ci, count=1, eligible=_eligible, up_to=False,
                     window=3, disposition="discard",
                     then_borrowed_attack_by=source_ci.instance_id)
    return state


@card_ability("ASH", "230")
def _improvised_identity():
    """ASH_230 — Improvised Identity (Upgrade, cost 2, +0/+3): "Attach to a ground
    unit.  Attached unit gains: 'Action: Search the top 3 cards of your deck for a
    ground unit and discard it.  Then, you may attack with this unit.  For this
    attack, this unit gains the discarded unit's abilities.  Use this ability only
    once each round.'"

    ``GrantedAbility(ActivatedAbility)`` (Heroic Resolve SHD_155): the Action is
    enumerated from the host's attached upgrades, addressed by the UPGRADE's id, and
    resolves FROM the host — so "this unit" is the host throughout.  The ability's
    two halves are the deck search and its ``then_borrowed_attack_by`` rider; the
    BORROW is the Support keyword's own read layer with an explicit lender
    (``borrow_lender_id``), so no ability-copying machinery is involved.
    DOCUMENTED NARROWING (Support's): keywords and triggered abilities travel, but
    constants and Actions do not — they are read by scans keyed on a card in an
    arena."""
    return GrantedAbility(ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_improvised_identity_search)],
        title="Search the top 3 for a ground unit, discard it, then attack",
        once_per_round=True,
    ))


# ── ash-set:09 — Card advantage & disruption ─────────────────────────────────


def _night_trooper_peek(state, source_ci, target_id, event_ctx):
    """"Look at the top card of a deck.  You may discard it" — the controller's OWN
    deck (the Lando LAW_18 / Watchful LAW_125 reading of "a deck": the only one whose
    composition they know), over the new ``may_discard`` peek mode."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_discard")
    return state


@card_ability("ASH", "45")
def _reanimated_night_trooper():
    """ASH_45 — Reanimated Night Trooper (Unit, Imperial Night Trooper Undead, 2/2):
    "When Defeated: Look at the top card of a deck.  You may discard it."

    The printed "you may" IS the peek decision's own KeepTopCard, so the trigger is
    mandatory; with an empty deck ``push_peek_top`` is a clean no-op."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_night_trooper_peek)],
    )


def _blade_of_talzin_recur(state, source_ci, target_id, event_ctx):
    """Return this upgrade from its owner's discard pile to their hand, but only if
    it was attached to a friendly Night unit.

    The host is the unit whose defeat brought the upgrade down — the standard
    ``defeated_ci`` the defeat path threads.  "Friendly" is measured against the
    UPGRADE's owner, which is who gets the card back."""
    from swu.engine.state import Zone
    from swu.engine.traits import has_trait
    host = event_ctx.get("defeated_ci")
    if host is None:
        return state
    host_res = state.find_instance(host.instance_id)
    host_owner = host_res[0].player_id if host_res is not None else host.owner_id
    if host_owner != source_ci.owner_id or not has_trait(state, host, "Night"):
        return state
    ps = state.player_by_id(source_ci.owner_id)
    me = next((c for c in ps.discard if c.instance_id == source_ci.instance_id), None)
    if me is None:
        return state
    ps.discard.remove(me)
    me.zone = Zone.HAND
    me.damage = 0
    me.exhausted = False
    ps.hand.append(me)
    return state


@card_ability("ASH", "55")
def _blade_of_talzin():
    """ASH_55 — Blade of Talzin (Upgrade, Item Night Weapon, cost 2, +2/+1): "Attach
    to a non-Vehicle unit.  When Defeated: If this upgrade was on a friendly Night
    unit, return this upgrade from your discard pile to your hand."

    ``WhenDefeatedAsUpgrade`` — the ONE seam that collects an upgrade's own trigger
    when its host dies, resolving FROM the upgrade now sitting in the discard (Roger
    Roger TWI_69 / Luke J25_4).  The "Attach to a non-Vehicle unit" restriction is
    parsed by ``_upgrade_target_spec``, so it needs no registration.  DOCUMENTED
    NARROWING: that scan is the host-death path, so an upgrade picked off on its own
    by a "defeat an upgrade" effect does not recur itself."""
    return TriggerAbility(
        trigger=WhenDefeatedAsUpgrade(),
        effects=[CustomEffect(fn=_blade_of_talzin_recur)],
    )


@card_ability("ASH", "87")
def _cybernetic_enhancements():
    """ASH_87 — Cybernetic Enhancements (Upgrade, Modification, cost 3, +2/+2): "When
    Played: Draw a card."

    A freshly-played upgrade lives in its host's ``attached_upgrades``, which the
    in-play scan never yields — the resolver's ``UpgradePlayed`` special case is what
    collects its own WhenPlayed."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)])


def _moff_gideon_97_recur(state, source_ci, target_id, event_ctx):
    """"Return a non-unique Imperial unit from your discard pile to your hand" —
    ``push_return_from_discard`` with the eligibility in the closure."""
    from swu.engine.actions import push_return_from_discard
    from swu.cards.models import Unit

    def _eligible(cd) -> bool:
        return (isinstance(cd, Unit) and not getattr(cd, "is_unique", False)
                and "Imperial" in (getattr(cd, "traits", ()) or ()))

    push_return_from_discard(state, source_ci, count=1, eligible=_eligible)
    return state


@card_ability("ASH", "97")
def _moff_gideon_unit():
    """ASH_97 — Moff Gideon (Unit, Imperial Official, 2/5; Sentinel): "When Defeated:
    You may return a non-unique Imperial unit from your discard pile to your hand."

    Sentinel is the keyword layer.  The printed "you may" IS ``return_from_discard``'s
    own ``up_to`` decline, and the decision is pushed only when a qualifying card is
    already in the pile — Gideon himself is still mid-defeat and so is never one of
    the candidates."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_moff_gideon_97_recur)],
    )


def _dathomiri_magicks_play(state, source_ci, target_id, event_ctx):
    """"Play up to 3 non-Vehicle units that each cost 2 or less from your discard
    pile for free" — one ``play_from_hand`` loop over a whitelist of the controller's
    own discard (``from_discard`` alone would also offer the HAND, the JTL_121
    convention), ``repeat_max=2`` for the two further plays and ``up_to`` for the
    decline that makes it "up to"."""
    from swu.engine.actions import push_play_from_hand
    from swu.cards.models import Unit
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    eligible = frozenset(
        c.instance_id for c in ps.discard
        if isinstance(c.card_def, Unit)
        and (getattr(c.card_def, "cost", 0) or 0) <= 2
        and not has_trait(state, c, "Vehicle"))
    if not eligible:
        return state
    push_play_from_hand(state, source_ci, free=True, from_discard=True,
                        cost_max=2, eligible_ids=eligible,
                        repeat_max=2, up_to=True)
    return state


@card_ability("ASH", "104")
def _dathomiri_magicks():
    """ASH_104 — Dathomiri Magicks (Event, Force, cost 6): "If you control a Force
    unit, this event costs 1 resource less to play.  Play up to 3 non-Vehicle units
    that each cost 2 or less from your discard pile for free."

    The discount is an ordinary conditional ``CostReduction`` read at the single
    play-cost seam.  The payoff is the ``play_from_hand`` decision's new "up to N"
    loop: each play re-pushes the decision with one fewer remaining BEFORE the unit
    enters play, so a played unit's own When Played resolves before the next pick."""
    return [
        CostReduction(1, condition=ConditionCheck(
            Condition.CONTROLLER_HAS_TRAIT_UNIT, param="Force")),
        EventAbility(effects=[CustomEffect(fn=_dathomiri_magicks_play)]),
    ]


def _clan_wren_search(state, source_ci, target_id, event_ctx):
    """"Search the top 5 of your deck for a card that shares a Trait with a unit you
    control, reveal it, and draw it."  The controlled units' EFFECTIVE traits are
    snapshotted into the closure; the "(put the others on the bottom in a random
    order)" reminder is ``push_deck_search``'s default ``rest_disposition``."""
    from swu.engine.actions import push_deck_search
    from swu.engine.traits import get_traits
    ps = state.player_by_id(source_ci.owner_id)
    owned: set[str] = set()
    for ci in ps.ground_arena + ps.space_arena:
        owned.update(get_traits(state, ci) or ())

    def _eligible(cd) -> bool:
        return bool(owned & set(getattr(cd, "traits", ()) or ()))

    push_deck_search(state, source_ci, count=1, eligible=_eligible,
                     up_to=False, window=5)
    return state


@card_ability("ASH", "107")
def _clan_wren_loyalist():
    """ASH_107 — Clan Wren Loyalist (Unit, Mandalorian Trooper, 3/2): "When Played:
    Search the top 5 cards of your deck for a card that shares a Trait with a unit
    you control, reveal it, and draw it."

    ``up_to=False`` is the printed mandatory take; the Loyalist itself is already in
    play when its When Played resolves, so its own Mandalorian/Trooper traits count."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_clan_wren_search)],
    )


@card_ability("ASH", "116")
def _ant_droid():
    """ASH_116 — Ant Droid (Unit, Droid, 1/2): "When Defeated: Draw a card." """
    return TriggerAbility(trigger=WhenDefeated(), effects=[DrawCards(1)])


@card_ability("ASH", "259")
def _lep_ratcatcher():
    """ASH_259 — LEP Ratcatcher (Unit, Droid, 1/1): "When Played: You may deal 1
    damage to a ground unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
        optional=True,
    )


# ── ash-set:12 — the ASH LEADER block ────────────────────────────────────────
#
# A leader's ``text`` is its UNDEPLOYED side and ``deploy_box`` its DEPLOYED side.
#
# ⚠️⚠️ TOKEN COLLISION on THREE of these seven numbers: ASH_1 is also the
# Mandalorian token UNIT, ASH_2 the Advantage token UPGRADE and ASH_3 the Shield
# token UPGRADE.  Only specs a token can never reach are registered there —
# ``ActivatedAbility(undeployed_only=True)`` (the arena scan demands a Leader
# card_def), ``ActivatedAbility(deployed_only=True)`` and
# ``TriggerAbility(deployed_only=True)`` (a token is never a deployed leader).  A
# ConstantAbility, a GrantedAbility or a passive marker would NOT be safe.


def _armorer_upgrade_from_resources(state, source_ci, host_controller,
                                    host_predicates):
    """Shared body: "Play an upgrade from your resources on <filtered host>
    (paying its cost).  If you do, resource the top card of your deck."

    A thin adapter onto ``push_play_upgrade_from_hand``'s ``from_resources`` mode:
    the chosen upgrade LEAVES the resource row (it is not replaced, unlike Smuggle)
    and cannot pay for itself, which is exactly why the card hands the row back a
    card — the ``then_resource_top_of_deck`` rider, run only on a real play."""
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(
        state, source_ci, free=False, from_resources=True,
        host_controller=host_controller, host_predicates=host_predicates,
        then_resource_top_of_deck=True)
    return state


def _armorer_entered_this_phase(state, source_ci, target_id, event_ctx):
    """Undeployed: the host must have entered play this phase."""
    return _armorer_upgrade_from_resources(state, source_ci, None,
                                           ("played_this_phase",))


def _armorer_friendly_host(state, source_ci, target_id, event_ctx):
    """Deployed: any friendly unit may host."""
    return _armorer_upgrade_from_resources(state, source_ci, "friendly", ())


@card_ability("ASH", "1")
def _the_armorer():
    """ASH_1 — The Armorer (Leader, Mandalorian, 4/6).

    Undeployed: "Action [Exhaust]: Play an upgrade from your resources on a unit
    that entered play this phase (paying its cost).  If you do, resource the top
    card of your deck."
    Deployed: "When Attack Ends: You may play an upgrade from your resources on a
    friendly unit.  If you do, resource the top card of your deck."

    Both sides are the same adapter, differing only by the host filter and by
    Action-vs-trigger — the recurring leader shape.  Each is gated on
    ``CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES``, which reuses the decision's own
    candidate filter, so the Exhaust is never spent (and the optional trigger never
    prompts) when no such play exists."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_armorer_entered_this_phase)],
            title="Play an upgrade from your resources",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES,
                param=(None, ("played_this_phase",))),
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_armorer_friendly_host)],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES,
                param=("friendly", ())),
        ),
    ]


def _fennec_play_unit_ready(state, source_ci, target_id, event_ctx):
    """"Play a unit from your hand (paying its cost).  It enters play ready."
    (Fennec Shand ASH_2, both sides.)"""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, enters_ready=True)
    return state


_FENNEC_PLAYABLE = ConditionCheck(
    Condition.ALL_OF,
    param=(ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND),
           ConditionCheck(Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX)),
)


@card_ability("ASH", "2")
def _fennec_shand():
    """ASH_2 — Fennec Shand (Leader, Underworld, 3/4).

    Undeployed: "Action [1 resource, Exhaust, exhaust a friendly unit]: Play a unit
    from your hand (paying its cost).  It enters play ready."
    Deployed: "Saboteur  |  Action [1 resource, exhaust a friendly unit]: Play a
    unit from your hand.  It enters play ready."  (Her deployed Action drops the
    self-exhaust, so she can use it and still attack.)

    "Exhaust a friendly unit" has no cost spec — it is a LEADING TARGETED
    ``ExhaustCard`` effect with the play behind it (the Tomb of Eilram LOF_28 /
    Director Krennic LAW_8 shape), targeted effect first so the player is prompted
    exactly once (the Mandalorian SHD_18 rule).  Both sides are gated on having
    BOTH a ready unit to exhaust and an affordable unit in hand, so neither cost is
    ever spent on a no-op."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[
                ExhaustCard(TargetSpec(controller="friendly", kind="unit",
                                       predicates=("ready",))),
                CustomEffect(fn=_fennec_play_unit_ready),
            ],
            title="Play a unit from your hand ready",
            undeployed_only=True,
            condition=_FENNEC_PLAYABLE,
        ),
        ActivatedAbility(
            costs=[PayResources(1)],
            effects=[
                ExhaustCard(TargetSpec(controller="friendly", kind="unit",
                                       predicates=("ready",))),
                CustomEffect(fn=_fennec_play_unit_ready),
            ],
            title="Play a unit from your hand ready",
            deployed_only=True,
            condition=_FENNEC_PLAYABLE,
        ),
    ]


def _baylan_buff_and_sentinel(state, source_ci, target_id, event_ctx):
    """"Give a friendly unit +2/+2 AND Sentinel for this phase" (Baylan Skoll
    ASH_3, deployed).

    ONE targeted effect doing both halves — a ``ModifyStats`` + ``GrantKeyword``
    pair would prompt twice and could split the buff and the keyword across two
    units (the Kylo Ren SHD_141 / Heroes on Both Sides TWI_249 rule)."""
    from swu.abilities.resolver import _make_modifier, _make_kw_modifier
    if target_id is None:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id, 2, 2, Duration.THIS_PHASE))
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id,
        keyword="Sentinel", value=0, duration=Duration.THIS_PHASE,
        kind="keyword_grant"))
    return state


@card_ability("ASH", "3")
def _baylan_skoll():
    """ASH_3 — Baylan Skoll (Leader, Force, 4/6).

    Undeployed: "Action [1 resource, Exhaust]: Give a friendly unit +2/+2 for this
    phase if it's the only unit you control in its arena."
    Deployed: "On Attack: You may give a friendly unit +2/+2 and Sentinel for this
    phase if it's the only non-leader unit you control in its arena."

    The "if it's the only …" clause is a CANDIDATE filter, not a condition — the
    predicates ``sole_friendly_unit_in_arena`` / ``sole_friendly_non_leader_unit_in
    _arena``, so a board with no lone unit simply offers nothing.  The deployed
    reading excludes leaders because Baylan himself is standing in the ground arena
    when his On Attack resolves."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[ModifyStats(2, 2, TargetSpec(
                controller="friendly", kind="unit",
                predicates=("sole_friendly_unit_in_arena",)),
                Duration.THIS_PHASE)],
            title="Give a lone friendly unit +2/+2",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_baylan_buff_and_sentinel,
                target=TargetSpec(
                    controller="friendly", kind="unit",
                    predicates=("non_leader",
                                "sole_friendly_non_leader_unit_in_arena")),
                # Declares the buried Sentinel grant to keyword-sanitiser rule 9,
                # which strips the Sentinel the upstream data mistags onto Baylan.
                grants_keywords=("Sentinel",))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _luke_exhaust_to_heal(state, source_ci, target_id, event_ctx):
    """"You may exhaust this leader.  If you do, heal 1 damage from that unit."
    (Luke Skywalker ASH_5, undeployed.)

    Cost and payoff in ONE effect so an unpaid exhaust cannot heal (the "If you do"
    binding); "that unit" is the attacker the ``WhenFriendlyUnitAttackEnds`` fire
    carries in ``attack_ended_attacker`` (set whether or not the attacker
    survived, so a dead attacker simply has nothing to heal)."""
    from swu.engine.actions import note_unit_healed
    if source_ci.exhausted:
        return state
    attacker_id = event_ctx.get("attack_ended_attacker")
    res = state.find_instance(attacker_id) if attacker_id else None
    if res is None or res[1].damage <= 0:
        return state
    source_ci.exhausted = True
    healed = min(1, res[1].damage)
    res[1].damage -= healed
    note_unit_healed(state, res[1], healed)
    return state


def _luke_heal_available(state, source_ci, event_ctx):
    """Offer the undeployed trigger only when it could really do something: the
    leader is ready AND the attacker still has damage on it."""
    if source_ci.exhausted:
        return False
    attacker_id = event_ctx.get("attack_ended_attacker")
    res = state.find_instance(attacker_id) if attacker_id else None
    return res is not None and res[1].damage > 0


@card_ability("ASH", "5")
def _luke_skywalker_ash():
    """ASH_5 — Luke Skywalker (Leader, Force Jedi Rebel, 6/7).

    Undeployed: "When a friendly unit's attack ends: You may exhaust this leader.
    If you do, heal 1 damage from that unit."
    Deployed: "When a friendly unit's attack ends: Heal 2 damage from that unit or
    from your base."

    Both sides ride ``WhenFriendlyUnitAttackEnds``, which fires EXACTLY ONCE per
    attack and carries the attacker alive or dead.  The deployed heal's "that unit
    or your base" is the ``attack_ended_attacker_or_own_base`` predicate over a
    ``unit_or_base`` target; ``damaged`` keeps it from being a dead prompt (with
    neither damaged the mandatory effect fizzles unprompted)."""
    return [
        TriggerAbility(
            trigger=WhenFriendlyUnitAttackEnds(),
            effects=[CustomEffect(fn=_luke_exhaust_to_heal,
                                  available_fn=_luke_heal_available)],
            optional=True,
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenFriendlyUnitAttackEnds(),
            effects=[Heal(2, TargetSpec(
                controller="friendly", kind="unit_or_base",
                predicates=("damaged", "attack_ended_attacker_or_own_base")))],
            deployed_only=True,
        ),
    ]


def _sabine_opponent_advantage(state, source_ci, target_id, event_ctx):
    """"An opponent gives 2 Advantage tokens to a unit they control.  If they do,
    the next unit you play this phase gains Shielded for this phase."  (Sabine Wren
    ASH_6, undeployed.)

    The OPPONENT decides (``decider_id``) and must if able (``mandatory``), and the
    "If they do" payoff is armed for SABINE's controller only when a unit was
    really chosen — with no enemy unit in play nothing is pushed and nothing is
    armed, which is the printed reading."""
    from swu.engine.actions import push_select_token
    opp_idx = 1 - state.player_index(source_ci.owner_id)
    opponent_id = state.players[opp_idx].player_id
    push_select_token(
        # ``controller`` is read from the SOURCE's perspective, so "a unit THEY
        # control" is "enemy" even though the opponent is the one choosing.
        state, source_ci, token_type="Advantage", token_count=2, max_targets=1,
        controller="enemy", decider_id=opponent_id, mandatory=True,
        then_pending_keyword={"keyword": "Shielded"})
    return state


def _sabine_arm_shielded(state, source_ci, target_id, event_ctx):
    """"The next unit you play this phase gains Shielded for this phase."
    (ASH_6 deployed — the ``pending_keyword_grants`` ledger, Deceptive Shade
    LOF_180, consumed by the controller's next unit play.)"""
    state.game_memory.pending_keyword_grants.append({
        "player_id": source_ci.owner_id,
        "trait": "",
        "keyword": "Shielded",
    })
    return state


@card_ability("ASH", "6")
def _sabine_wren_ash():
    """ASH_6 — Sabine Wren (Leader, Jedi Mandalorian Spectre, 3/5).

    Undeployed: "Action [Exhaust]: An opponent gives 2 Advantage tokens to a unit
    they control.  If they do, the next unit you play this phase gains Shielded for
    this phase."
    Deployed: "On Attack: The next unit you play this phase gains Shielded for this
    phase." """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_sabine_opponent_advantage)],
            title="An opponent gives 2 Advantage tokens",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_sabine_arm_shielded)],
            deployed_only=True,
        ),
    ]


def _sloane_choose_arena(state, source_ci, target_id, event_ctx):
    """"Choose one: give each GROUND unit / each SPACE unit Sentinel and Overwhelm
    for this phase."  (Grand Admiral Sloane ASH_7, undeployed.)

    ``push_choose_modal(pick=1)`` over the two option specs — which are
    ``EventAbility`` because this is a LEADER card: a ``TriggerAbility`` option
    would be collected as a real trigger from the base zone (the Lightmaker SEC_207
    rule, and the exact mirror of an EVENT card's need for TriggerAbility
    options)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _sloane_arena_grants(arena: str):
    """Sentinel + Overwhelm for this phase to EVERY unit in one arena (both
    players' — "each ground unit" draws no friendly/enemy distinction)."""
    return [
        GrantKeyword("Sentinel", 0, TargetSpec(
            controller="any", kind="unit", arena=arena, fixed=EACH_IN_PLAY),
            Duration.THIS_PHASE),
        GrantKeyword("Overwhelm", 0, TargetSpec(
            controller="any", kind="unit", arena=arena, fixed=EACH_IN_PLAY),
            Duration.THIS_PHASE),
    ]


@card_ability("ASH", "7")
def _grand_admiral_sloane():
    """ASH_7 — Grand Admiral Sloane (Leader, Imperial Official, 4/5).

    Undeployed: "Action [Exhaust]: Choose one: Give each ground unit Sentinel and
    Overwhelm for this phase.  /  Give each space unit Sentinel and Overwhelm for
    this phase."
    Deployed: "Overwhelm  |  Each other friendly unit gains Overwhelm and
    Sentinel."

    Her printed bar is Overwhelm ALONE; the upstream data also tags her with the
    Sentinel she only grants to others, which keyword-sanitiser rule 9 now strips
    for Leaders too (the line test reads text + deploy_box, and "Overwhelm" is the
    leading line of her deploy box while "Sentinel" never starts one)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_sloane_choose_arena)],
            title="Give an arena Sentinel and Overwhelm",
            undeployed_only=True,
        ),
        EventAbility(effects=_sloane_arena_grants("ground")),
        EventAbility(effects=_sloane_arena_grants("space")),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            effects=[KeywordGrant("Overwhelm"), KeywordGrant("Sentinel")],
        ),
    ]


@card_ability("ASH", "10")
def _bo_katan_kryze_ash():
    """ASH_10 — Bo-Katan Kryze (Leader, Mandalorian, 4/7).

    Undeployed: "Action [2 resources, Exhaust]: If you control a unit in each
    arena, create a Mandalorian token."
    Deployed: "Other friendly Mandalorian units get +1/+0.  |  On Attack: If you
    control a unit in each arena, create a Mandalorian token."
    Epic Action: "If the number of resources you control plus the number of
    friendly Mandalorian units is 10 or more, deploy this leader."

    That deploy clause is the one the ``_deploy_threshold`` regex cannot read — she
    was previously undeployable — so it is registered as a ``DeployCondition``
    marker, read at the single ``_leader_deploy_allowed`` gate.  Both halves of the
    token clause are gated on ``CONTROLLER_HAS_GROUND_AND_SPACE_UNIT``, so neither
    the 2 resources nor the prompt is spent when the clause cannot be met."""
    both_arenas = ConditionCheck(Condition.CONTROLLER_HAS_GROUND_AND_SPACE_UNIT)
    return [
        ActivatedAbility(
            costs=[PayResources(2), ExhaustSelf()],
            effects=[CreateTokenUnit("Mandalorian", 1)],
            title="Create a Mandalorian token",
            undeployed_only=True,
            condition=both_arenas,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Mandalorian",), predicates=("not_self",)),
            effects=[StatBonus(power=1, hp=0)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CreateTokenUnit("Mandalorian", 1)],
            deployed_only=True,
            condition=both_arenas,
        ),
        DeployCondition(condition=ConditionCheck(
            Condition.CONTROLLER_RESOURCES_PLUS_TRAIT_UNITS_MIN,
            param=("Mandalorian", 10))),
    ]


# ── ash-set:13 — combat tricks, buffs & tempo ────────────────────────────────
#
# Four LEADERS whose clauses all key off the END of an attack, plus three units.
# The batch's one shared engine seam is the attack-end fires now carrying
# ``attack_ended_base_damage_amount`` — HOW MUCH combat damage the attack put on a
# base — which they read as a threshold (ASH_13), a ceiling (ASH_16) and a
# magnitude (ASH_31).  Overwhelm excess counts, because it IS combat damage dealt
# to a base; the amount rides on the same fires the direct base attack uses.


def _advantage_to_other_unit(state, source_ci, event_ctx, *, exhaust_source: bool):
    """Ezra Bridger ASH_13's payoff: (optionally exhaust the leader, then) give an
    Advantage token to a unit OTHER than the one that just attacked.

    Cost and payoff live in ONE effect so an unpaid exhaust can never hand out the
    token (the Bright Hope SOR_99 "if you do" binding).  ``mandatory=True`` on the
    select — the clause has no "up to", so once the leader is exhausted the token
    must be given if anything is eligible."""
    from swu.engine.actions import push_select_token
    attacker_id = event_ctx.get("attack_ended_attacker")
    if exhaust_source:
        res = state.find_instance(source_ci.instance_id)
        if res is None or res[1].exhausted:
            return state
        res[1].exhausted = True
    push_select_token(
        state, source_ci, token_type="Advantage", max_targets=1,
        controller="any", kind="unit", mandatory=True,
        exclude_ids=[attacker_id] if attacker_id else None,
    )
    return state


def _ezra_exhaust_for_advantage(state, source_ci, target_id, event_ctx):
    """Undeployed Ezra: "you may exhaust this leader.  If you do, give an Advantage
    token to a different unit"."""
    return _advantage_to_other_unit(state, source_ci, event_ctx, exhaust_source=True)


def _ezra_advantage(state, source_ci, target_id, event_ctx):
    """Deployed Ezra: the same payoff, with no exhaust to pay."""
    return _advantage_to_other_unit(state, source_ci, event_ctx, exhaust_source=False)


def _another_unit_available(state, source_ci, event_ctx) -> bool:
    """True while some unit OTHER than the attacker whose attack just ended is in
    play — the "don't offer a no-op" gate for Ezra's optional trigger."""
    attacker_id = event_ctx.get("attack_ended_attacker")
    for ps in state.players:
        for u in ps.ground_arena + ps.space_arena:
            if u.instance_id != attacker_id:
                return True
    return False


@card_ability("ASH", "13")
def _ezra_bridger_ash():
    """ASH_13 — Ezra Bridger (Leader, Force Jedi Rebel Spectre, 3/6, unique).

    Undeployed: "When a friendly unit's attack ends: If it dealt 3 or more combat
    damage to a base, you may exhaust this leader.  If you do, give an Advantage
    token to a different unit."
    Deployed: Saboteur, and the same trigger without the exhaust.

    "If it dealt 3 or more combat damage to a base" is the new
    ``WhenFriendlyUnitAttackEnds(require_base_damage_min=3)`` — the trigger is not
    even collected below the threshold, so there is no prompt.  The undeployed side
    is additionally gated on ``SOURCE_READY`` (an exhausted leader cannot pay) and
    both sides carry an ``available_fn`` so a board with only the attacker on it
    never asks (Shadow Caster JTL_169)."""
    trigger = WhenFriendlyUnitAttackEnds(require_base_damage_min=3)
    return [
        TriggerAbility(
            trigger=trigger,
            effects=[CustomEffect(fn=_ezra_exhaust_for_advantage,
                                  available_fn=_another_unit_available)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=trigger,
            effects=[CustomEffect(fn=_ezra_advantage,
                                  available_fn=_another_unit_available)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _palpatine_advantage_per_other_unit(state, source_ci, target_id, event_ctx):
    """Emperor Palpatine ASH_15: "Give an Advantage token to it for each OTHER
    friendly unit."  The chosen unit is already picked, so the count is every unit
    its controller has in play except itself — a straight ``attach_token`` loop
    (the token count is board-derived, not a decision)."""
    from swu.engine.tokens import attach_token
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, chosen = res
    count = sum(1 for arena in (holder.ground_arena, holder.space_arena)
                for u in arena if u.instance_id != chosen.instance_id)
    for _ in range(count):
        attach_token(state, holder, chosen, "Advantage")
    return state


@card_ability("ASH", "15")
def _emperor_palpatine_ash():
    """ASH_15 — Emperor Palpatine (Leader, Force Imperial Official Sith, 4/8, unique).

    Undeployed: "Action [Exhaust]: Choose an exhausted friendly unit.  Give an
    Advantage token to it for each other friendly unit."
    Deployed: "On Attack: You may choose ANOTHER exhausted friendly unit.  If you
    do, give an Advantage token to it for each other friendly unit."

    One targeted ``CustomEffect`` per side, differing only in the ``not_self``
    predicate ("another" — attacking exhausts Palpatine himself, so without it he
    would be his own best target) and in the exhaust cost.  The Action is gated on
    ``CONTROLLER_HAS_EXHAUSTED_UNIT`` so it is never offered with nothing to
    choose; the deployed trigger is ``optional`` and its target list is likewise
    empty when there is no other exhausted unit, so it auto-declines."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_palpatine_advantage_per_other_unit,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("exhausted",)))],
            title="Give an exhausted friendly unit Advantage tokens",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_EXHAUSTED_UNIT),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_palpatine_advantage_per_other_unit,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("exhausted", "not_self")))],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT),
        ),
    ]


def _shin_cheaper_than_base_damage(state, event_ctx) -> list:
    """The ids Shin Hati ASH_16 may exhaust: READY units costing strictly less than
    the combat damage this attack dealt to a base.  Computed by the card (rather
    than expressed as a predicate) because the ceiling is an event value, and it is
    then handed to the select decision as a ``restrict_ids`` whitelist."""
    amount = int(event_ctx.get("attack_ended_base_damage_amount", 0) or 0)
    if amount <= 0:
        return []
    out = []
    for ps in state.players:
        for u in ps.ground_arena + ps.space_arena:
            if u.exhausted:
                continue
            cost = getattr(u.card_def, "cost", None)
            if cost is not None and cost < amount:
                out.append(u.instance_id)
    return out


def _shin_exhaust_available(state, source_ci, event_ctx) -> bool:
    """"Don't offer a no-op": only ask when something is actually exhaustable."""
    return bool(_shin_cheaper_than_base_damage(state, event_ctx))


def _shin_exhaust_a_cheaper_unit(state, source_ci, target_id, event_ctx):
    """Undeployed Shin Hati: "You may exhaust this leader.  If you do, exhaust a
    unit that costs less than the amount of combat damage dealt to a base this
    attack" — cost and payoff in ONE effect (the "if you do" binding)."""
    from swu.engine.actions import push_select_token
    ids = _shin_cheaper_than_base_damage(state, event_ctx)
    if not ids:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1].exhausted:
        return state
    res[1].exhausted = True
    push_select_token(state, source_ci, token_type=None, max_targets=1,
                      controller="any", kind="unit", exhaust=True,
                      mandatory=True, restrict_ids=ids)
    return state


def _shin_exhaust_a_cheaper_unit_once(state, source_ci, target_id, event_ctx):
    """Deployed Shin Hati: the same exhaust with no cost, but "only once each
    round" — the shared ``{iid}:trig`` marker, charged HERE (i.e. on accept), so
    declining the optional trigger does not spend the use (Toro Calican SHD_239)."""
    from swu.engine.actions import push_select_token
    ids = _shin_cheaper_than_base_damage(state, event_ctx)
    if not ids:
        return state
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    push_select_token(state, source_ci, token_type=None, max_targets=1,
                      controller="any", kind="unit", exhaust=True,
                      mandatory=True, restrict_ids=ids)
    return state


@card_ability("ASH", "16")
def _shin_hati_leader():
    """ASH_16 — Shin Hati (Leader, Force, 4/6, unique).

    Undeployed: "When a friendly unit's attack ends: You may exhaust this leader.
    If you do, exhaust a unit that costs less than the amount of combat damage
    dealt to a base this attack."
    Deployed: the same without the leader exhaust, "only once each round".

    Both read the new ``attack_ended_base_damage_amount`` key.  A ceiling read off
    an event value cannot be a TargetSpec filter, so the card computes the eligible
    (ready, cheap enough) units itself and hands them to the exhaust-mode
    ``select_token`` decision as a ``restrict_ids`` whitelist — and the same helper
    backs the ``available_fn``, so the offer and the pool can never disagree."""
    trigger = WhenFriendlyUnitAttackEnds()
    return [
        TriggerAbility(
            trigger=trigger,
            effects=[CustomEffect(fn=_shin_exhaust_a_cheaper_unit,
                                  available_fn=_shin_exhaust_available)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=trigger,
            effects=[CustomEffect(fn=_shin_exhaust_a_cheaper_unit_once,
                                  available_fn=_shin_exhaust_available)],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(
                Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        ),
    ]


def _greef_token_on_entered_unit(state, source_ci, event_ctx, *, exhaust_source: bool):
    """Greef Karga ASH_17's payoff: give an Advantage token to the unit that just
    entered play, located by ``event_ctx["entered_unit_id"]`` (the key the new
    WhenYouPlayOrCreateUnit drain carries).  The undeployed side pays with the
    leader's exhaust, bound into this same effect."""
    from swu.engine.tokens import attach_token
    res = state.find_instance(event_ctx.get("entered_unit_id") or "")
    if res is None:
        return state
    holder, entered = res
    if exhaust_source:
        own = state.find_instance(source_ci.instance_id)
        if own is None or own[1].exhausted:
            return state
        own[1].exhausted = True
    attach_token(state, holder, entered, "Advantage")
    return state


def _greef_exhaust_for_token(state, source_ci, target_id, event_ctx):
    return _greef_token_on_entered_unit(state, source_ci, event_ctx,
                                        exhaust_source=True)


def _greef_token(state, source_ci, target_id, event_ctx):
    return _greef_token_on_entered_unit(state, source_ci, event_ctx,
                                        exhaust_source=False)


def _entered_unit_still_in_play(state, source_ci, event_ctx) -> bool:
    """The entered unit may already have left play again by the time the drain
    runs (a When Played that defeats it); don't offer the exhaust for nothing."""
    from swu.engine.state import Zone
    res = state.find_instance(event_ctx.get("entered_unit_id") or "")
    return res is not None and res[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)


@card_ability("ASH", "17")
def _greef_karga_ash():
    """ASH_17 — Greef Karga (Leader, Official, 4/7, unique).

    Undeployed: "When you play or create a unit: You may exhaust this leader.  If
    you do, give an Advantage token to that unit."
    Deployed: the same, mandatory and free.

    "Play OR create" is the whole reason for the new ``WhenYouPlayOrCreateUnit``
    observer: it drains ``game_memory.unit_entries``, fed at ``_put_unit_in_play``
    — the one chokepoint a played unit, an ability-played unit and a created token
    unit all pass through."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayOrCreateUnit(),
            effects=[CustomEffect(fn=_greef_exhaust_for_token,
                                  available_fn=_entered_unit_still_in_play)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenYouPlayOrCreateUnit(),
            effects=[CustomEffect(fn=_greef_token)],
            deployed_only=True,
        ),
    ]


@card_ability("ASH", "30")
def _marrok():
    """ASH_30 — Marrok (Unit, Force Inquisitor, 2/6, unique): "Sentinel.  While this
    unit is upgraded, he loses Sentinel and gains Saboteur."

    Two SELF constants over one condition: a ``KeywordRevoke`` (the aura form, read
    ahead of every grant source so the printed Sentinel really goes away) and a
    ``KeywordGrant``.  A Shield / Experience / Advantage token IS an upgrade, so any
    of them flips him — the printed reading.  The mistagged printed Saboteur is
    stripped by keyword-sanitiser rule 2 (which keys on exactly this conditional
    SELF grant); the printed Sentinel is KEPT, because it leads its own line and so
    survives rule 10's "lose-only" test — Marrok really has it while bare."""
    upgraded = ConditionCheck(Condition.SOURCE_ATTACHED_UPGRADES_MIN, param=1)
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordRevoke("Sentinel")],
            condition=upgraded,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Saboteur")],
            condition=upgraded,
        ),
    ]


def _hera_heal_base_for_base_damage(state, source_ci, target_id, event_ctx):
    """Hera Syndulla ASH_31: heal the controller's base for exactly the combat
    damage this attack dealt to a base.  Routed through the shared heal helper so
    the Wolffe SOR_160 "bases can't heal" lock and the heal observers both apply."""
    from swu.abilities.resolver import _apply_heal
    amount = int(event_ctx.get("attack_ended_base_damage_amount", 0) or 0)
    if amount <= 0:
        return state
    res = state.find_instance(source_ci.instance_id)
    ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
    if ps.base_instance is not None:
        _apply_heal(state, source_ci, ps.base_instance.instance_id, amount)
    return state


@card_ability("ASH", "31")
def _hera_syndulla_ash():
    """ASH_31 — Hera Syndulla (Unit, New Republic Spectre Twi'lek, 3/4, unique):
    "When Attack Ends: If this unit dealt combat damage to a base, heal that much
    damage from your base."

    ``WhenAttackEnds(require_base_damage=True)`` already means "this attack put
    combat damage on a base" (Maul LAW_54); the new part is the AMOUNT riding on
    the same fire.  An Overwhelm spill now sets both keys too, so a unit attack that
    spills onto the base heals as printed."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_base_damage=True),
        effects=[CustomEffect(fn=_hera_heal_base_for_base_damage)],
    )


@card_ability("ASH", "39")
def _baylan_skoll_unit():
    """ASH_39 — Baylan Skoll (Unit, Force, 6/6, unique): "Overwhelm.  When
    Played/When Attack Ends: If an enemy base was damaged this phase, give an
    Advantage token to a unit.  If a friendly upgrade was defeated this phase, you
    may exhaust a unit."

    Two clauses with different optionality under two triggers, so FOUR single-effect
    abilities (the Bossk LAW_31 rule — only separate abilities can carry different
    ``optional`` flags, and only a per-clause ``condition`` can stop a failed clause
    prompting at all).  Both gates are new phase-scoped ledgers read at the
    chokepoints that already fed their drained-queue observers:
    ``ENEMY_BASE_DAMAGED_THIS_PHASE`` (``record_base_damage``, which an Overwhelm
    spill now also reaches — and Baylan HAS Overwhelm) and
    ``CONTROLLER_UPGRADE_DEFEATED_THIS_PHASE`` (``note_upgrade_defeated``; a
    defeated Advantage token counts, which on an ASH board is the common case)."""
    base_damaged = ConditionCheck(Condition.ENEMY_BASE_DAMAGED_THIS_PHASE)
    upgrade_lost = ConditionCheck(Condition.CONTROLLER_UPGRADE_DEFEATED_THIS_PHASE)
    token = [GiveToken("Advantage", TargetSpec(controller="any", kind="unit"))]
    exhaust = [ExhaustCard(TargetSpec(controller="any", kind="unit",
                                      predicates=("ready",)))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=token, condition=base_damaged),
        TriggerAbility(trigger=WhenAttackEnds(), effects=token,
                       condition=base_damaged),
        TriggerAbility(trigger=WhenPlayed(), effects=exhaust, optional=True,
                       condition=upgrade_lost),
        TriggerAbility(trigger=WhenAttackEnds(), effects=exhaust, optional=True,
                       condition=upgrade_lost),
    ]


# ── ash-set:14 — combat tricks, buffs & tempo ────────────────────────────────


def _outcast_buff_entered_unit(state, source_ci, target_id, event_ctx):
    """Outcast ASH_41: "When a friendly unit enters play (including this one): It
    gets +1/+0 for this phase."  "It" is the unit that entered, read off the
    ``entered_unit_id`` key the WhenYouPlayOrCreateUnit drain carries — which is
    why this is a CustomEffect and not a targeted ``ModifyStats``: there is no
    choice to make."""
    from swu.abilities.resolver import _make_modifier
    entered_id = event_ctx.get("entered_unit_id")
    if not entered_id or state.find_instance(entered_id) is None:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, entered_id, 1, 0, Duration.THIS_PHASE))
    return state


@card_ability("ASH", "41")
def _outcast():
    """ASH_41 — Outcast (Unit, 1/4, unique): "When a friendly unit enters play
    (including this one): It gets +1/+0 for this phase."

    The second user of ``WhenYouPlayOrCreateUnit``, and the reason its
    ``include_self`` default is True: the drain runs at the action settle-point,
    with Outcast already standing in its arena, so the ordinary in-play trigger
    scan collects it for its own entry exactly as the parenthetical says."""
    return TriggerAbility(
        trigger=WhenYouPlayOrCreateUnit(),
        effects=[CustomEffect(fn=_outcast_buff_entered_unit)],
    )


def _barriss_heal_then_advantage(state, source_ci, target_id, event_ctx):
    """Barriss Offee ASH_44: "Heal up to 2 damage from a unit.  Give an Advantage
    token to it for each damage healed this way."

    ONE targeted effect, because both halves must land on the SAME chosen unit (the
    Kylo Ren SHD_141 rule).  "Up to 2" heals as much as it can, the Satine SEC_5
    convention — and since the token count is the damage actually removed, healing
    less could only ever be worse."""
    from swu.abilities.resolver import _apply_heal
    from swu.engine.tokens import attach_token
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, chosen = res
    before = chosen.damage
    _apply_heal(state, source_ci, target_id, 2)
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, chosen = res
    healed = max(0, before - chosen.damage)
    for _ in range(healed):
        attach_token(state, holder, chosen, "Advantage")
    return state


@card_ability("ASH", "44")
def _barriss_offee_ash():
    """ASH_44 — Barriss Offee (Unit, 3/4, unique): "When Played: Heal up to 2 damage
    from a unit.  Give an Advantage token to it for each damage healed this way."

    The ``damaged`` predicate keeps the prompt honest: an undamaged unit heals
    nothing and so earns no token, which would make it a strictly dead choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_barriss_heal_then_advantage,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("damaged",)))],
    )


@card_ability("ASH", "49")
def _shin_hati_unit():
    """ASH_49 — Shin Hati (Unit, Force, 6/6, unique): "While this is the only
    friendly non-leader ground unit, she gains Sentinel."

    A conditional SELF ``KeywordGrant`` over the new
    ``SOURCE_SOLE_FRIENDLY_NON_LEADER_UNIT_IN_ARENA`` atom — the condition sibling
    of the ``sole_friendly_non_leader_unit_in_arena`` predicate (Baylan Skoll
    ASH_3), so a deployed leader standing beside her does not break the clause.
    Registering it is also what strips her mistagged printed Sentinel (sanitiser
    rule 2), so a Shin Hati with company really lacks it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(
            Condition.SOURCE_SOLE_FRIENDLY_NON_LEADER_UNIT_IN_ARENA),
    )


@card_ability("ASH", "51")
def _reinforcing_light_cruiser():
    """ASH_51 — Reinforcing Light Cruiser (Unit, 5/5): "Restore 1.  When Played: You
    may exhaust a unit."

    The ``ready`` predicate is the "don't offer a no-op" gate — exhausting an
    already-exhausted unit changes nothing, so with no ready unit on the board the
    optional trigger auto-declines."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("ready",)))],
        optional=True,
    )


def _chimaera_pick_friendly(state, source_ci, target_id, event_ctx):
    """Chimaera ASH_52, step 1: record the chosen FRIENDLY unit so step 2 can be
    gated on it (the Nothing Left to Fear LAW_41 shared-``event_ctx`` chain)."""
    if target_id:
        event_ctx["prior_target_id"] = target_id
    return state


def _chimaera_defeat_both(state, source_ci, target_id, event_ctx):
    """Chimaera ASH_52, step 2: "If you do, defeat those units" — the enemy pick and
    the friendly one recorded by step 1, defeated together."""
    from swu.abilities.resolver import _apply_defeat_unit
    if not target_id:
        return state
    friendly_id = event_ctx.get("prior_target_id")
    for iid in (target_id, friendly_id):
        if iid and state.find_instance(iid) is not None:
            _apply_defeat_unit(state, iid)
    return state


@card_ability("ASH", "52")
def _chimaera_ash():
    """ASH_52 — Chimaera (Unit, 6/6, unique): "When Played: You may choose a friendly
    unit and an enemy non-leader unit.  If you do, defeat those units.  |  When an
    enemy unit is defeated: Heal 2 damage from your base."

    The pair is the LAW_41 chain: a targeted CustomEffect stamps
    ``prior_target_id``, and the second targeted effect is gated by
    ``requires_prior_target``, so declining the first (or having no enemy
    non-leader to pick) leaves nothing defeated — which is exactly "If you do"."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[
                CustomEffect(fn=_chimaera_pick_friendly,
                             target=TargetSpec(controller="friendly", kind="unit",
                                               optional=True)),
                CustomEffect(fn=_chimaera_defeat_both,
                             target=TargetSpec(controller="enemy", kind="unit",
                                               predicates=("non_leader",
                                                           "requires_prior_target"))),
            ],
            optional=True,
        ),
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="enemy", kind="unit")),
            effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
        ),
    ]


@card_ability("ASH", "57")
def _lothal_e_wing():
    """ASH_57 — Lothal E-Wing (Unit, 2/3): "While an enemy unit is upgraded, this
    unit gains Restore 2."

    A conditional SELF ``KeywordGrant`` with a value, over the existing
    ``ENEMY_UNIT_UPGRADED`` atom (Sugi SHD_52) — a Shield / Experience / Advantage
    token counts as an upgrade there, as it does everywhere."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", value=2)],
        condition=ConditionCheck(Condition.ENEMY_UNIT_UPGRADED),
    )


@card_ability("ASH", "64")
def _the_armorer_unit():
    """ASH_64 — The Armorer (Unit, 5/5, unique): "Shielded.  When Played: Give a
    Shield token to each friendly unit with Shielded (including this one)."

    ``fixed=EACH_FRIENDLY`` narrowed by the ``has_keyword_shielded`` predicate,
    which reads through the keyword layer — so a unit GRANTED Shielded qualifies
    too.  "(Including this one)" needs no special casing: her own Shielded has
    already resolved on the enter-play bus by the time her When Played fires, and
    she matches her own filter."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="friendly", kind="unit", fixed=EACH_FRIENDLY,
            predicates=("has_keyword_shielded",)))],
    )


# ── ash-set:15 — combat tricks, buffs & tempo ────────────────────────────────


def _home_one_heal_all_friendly(state, source_ci, target_id, event_ctx):
    """Home One ASH_65: "Heal ALL damage from each friendly unit."  No magnitude
    exists that says "all", so the effect reads each unit's own damage and heals
    exactly that, through the shared ``_apply_heal`` seam (so the heal observers and
    the ``units_healed_this_phase`` ledger see every one of them)."""
    from swu.abilities.resolver import _apply_heal
    res = state.find_instance(source_ci.instance_id)
    ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
    for ci in list(ps.ground_arena) + list(ps.space_arena):
        if ci.damage > 0:
            _apply_heal(state, source_ci, ci.instance_id, ci.damage)
    return state


@card_ability("ASH", "65")
def _home_one():
    """ASH_65 — Home One (Unit, 7/10, unique): "Sentinel.  When Played: Heal all
    damage from each friendly unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_home_one_heal_all_friendly)],
    )


@card_ability("ASH", "66")
def _lukes_jedi_lightsaber():
    """ASH_66 — Luke's Jedi Lightsaber (Upgrade, +3/+3, unique): "Attach to a
    non-Vehicle unit.  If attached unit is Luke Skywalker, he gains Sentinel."

    The upgrade-SELF ``KeywordGrant`` (Constructed Lightsaber LOF_261): the keyword
    layer's attached-upgrade scan confers it on the HOST and evaluates the condition
    against that host — which is why the atom is the new ``SOURCE_NAMED`` and NOT
    ``ATTACHED_HOST_NAMED``: that one expects the UPGRADE as its source and looks the
    host up from it, so handed the host it reads False.  "Attach to a non-Vehicle
    unit" needs no registration — ``_upgrade_target_spec`` parses it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.SOURCE_NAMED, param="Luke Skywalker"),
    )


@card_ability("ASH", "73")
def _palace_chef_droid():
    """ASH_73 — Palace Chef Droid (Unit, 0/3): "Sentinel.  This unit gets +2/+0
    while defending."

    ``while_target_defending`` with ``fixed=SELF`` (Concord Dawn SHD_42, Cal Kestis
    LOF_49) — the bonus applies only while this unit is itself the current combat
    defender, which is a combat context the keyword layer could not express."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        while_target_defending=True,
    )


@card_ability("ASH", "75")
def _pit_droid_team():
    """ASH_75 — Pit Droid Team (Unit, 3/3): "The first upgrade you play on ANOTHER
    friendly unit each phase costs 1 resource less."

    ``StandingPlayDiscount`` with the new ``applies_to="upgrade_not_on_source"`` —
    the complement of Guardian of the Whills SOR_61's ``upgrade_on_source``: the
    chosen host must be a unit its controller controls and must NOT be Pit Droid
    Team itself.  "Each phase" is modelled by ``once_per_round`` (the Malakili
    LOF_108 equivalence — one action phase per round, and upgrades are only played
    in it)."""
    return StandingPlayDiscount(amount=1, applies_to="upgrade_not_on_source",
                                once_per_round=True)


@card_ability("ASH", "78")
def _b_wing_rearguard():
    """ASH_78 — B-Wing Rearguard (Unit, 3/5): "While you control a ground unit, this
    unit gains Sentinel."

    A conditional SELF ``KeywordGrant`` over ``CONTROLLER_HAS_UNIT_IN_ARENA``
    (Getaway Freighter LAW_155).  This is a SPACE unit, so its own presence can
    never satisfy a "ground unit" clause and no self-exclusion is needed."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_IN_ARENA,
                                 param="ground"),
    )


@card_ability("ASH", "79")
def _koska_reeves():
    """ASH_79 — Koska Reeves (Unit, Mandalorian, 4/4, unique): "While you control a
    token unit, this unit gains Sentinel.  |  When Played: If a friendly unit was
    defeated this phase, create a Mandalorian token."

    Both halves are existing atoms — ``CONTROLLER_HAS_TOKEN_UNIT`` (First Order TIE
    Fighter JTL_81) and ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` (Wat Tambor TWI_6),
    the latter gating COLLECTION so an unmet clause never prompts."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TOKEN_UNIT),
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Mandalorian", 1)],
            condition=ConditionCheck(
                Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE),
        ),
    ]


@card_ability("ASH", "81")
def _nebulon_c_frigate():
    """ASH_81 — Nebulon-C Frigate (Unit, 3/6): "When Played: You may heal 3 damage
    from a unit or base."

    The ``damaged`` predicate is the "don't offer a no-op" gate, and it reaches
    bases too (a base with damage on it matches)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[Heal(3, TargetSpec(controller="any", kind="unit_or_base",
                                    predicates=("damaged",)))],
        optional=True,
    )


# ── ash-set:16 — combat tricks, buffs & tempo ────────────────────────────────


@card_ability("ASH", "82")
def _trexler_armored_marauder():
    """ASH_82 — Trexler Armored Marauder (Unit, 5/6): "Grit.  When Played: You may
    give a Shield token to a unit that costs 3 or less." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(controller="any", kind="unit",
                                                cost_max=3))],
        optional=True,
    )


def _durasteel_shield_host(state, source_ci, target_id, event_ctx):
    """Durasteel Plating ASH_86: "Give a Shield token to attached unit."  The host
    is ``event_ctx["attached_to_id"]``, the key the upgrade-play path threads
    (Craving Power LOF_91)."""
    from swu.engine.tokens import attach_token
    res = state.find_instance(event_ctx.get("attached_to_id") or "")
    if res is None:
        return state
    holder, host = res
    attach_token(state, holder, host, "Shield")
    return state


@card_ability("ASH", "86")
def _durasteel_plating():
    """ASH_86 — Durasteel Plating (Upgrade, +1/+1): "When Played: Give a Shield token
    to attached unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_durasteel_shield_host)],
    )


def _conflict_within_pay_or_exhaust(state, source_ci, target_id, event_ctx):
    """The Conflict Within ASH_88: "You may pay 3 resources.  If you don't, exhaust
    this unit" — the single-unit ``pay_or_exhaust`` decision addressed to the host's
    controller (In Debt to Crimson Dawn JTL_192 with ``pay_amount=3``).
    ``source_ci`` is the HOST: the spec rides in a ``GrantedAbility``."""
    from swu.engine.actions import push_pay_or_exhaust
    push_pay_or_exhaust(state, source_ci.instance_id, 3)
    return state


@card_ability("ASH", "88")
def _the_conflict_within():
    """ASH_88 — The Conflict Within (Upgrade, Condition, 3): "Attached unit gains:
    'When this unit readies: You may pay 3 resources.  If you don't, exhaust this
    unit.'"

    JTL_192 verbatim at a higher price: ``GrantedAbility`` + the ``WhenUnitReadies``
    settle-drain observer, so the decision can be pushed from inside the REGROUP
    phase's mass-ready."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenUnitReadies(),
        effects=[CustomEffect(fn=_conflict_within_pay_or_exhaust)],
    ))


def _perseverance_heal_and_shield(state, source_ci, target_id, event_ctx):
    """Perseverance ASH_89: "Heal 3 damage from a unit AND give a Shield token to
    it."  ONE targeted effect, because both halves must land on the same chosen unit
    (the Kylo Ren SHD_141 rule) — a Heal + GiveToken pair would prompt twice and
    could split them."""
    from swu.abilities.resolver import _apply_heal
    from swu.engine.tokens import attach_token
    if not target_id:
        return state
    _apply_heal(state, source_ci, target_id, 3)
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, chosen = res
    attach_token(state, holder, chosen, "Shield")
    return state


@card_ability("ASH", "89")
def _perseverance():
    """ASH_89 — Perseverance (Event, 2): "Heal 3 damage from a unit and give a Shield
    token to it." """
    return EventAbility(effects=[CustomEffect(
        fn=_perseverance_heal_and_shield,
        target=TargetSpec(controller="any", kind="unit"))])


@card_ability("ASH", "93")
def _captain_pellaeon():
    """ASH_93 — Captain Pellaeon (Unit, 2/4, unique): "While a leader unit has been
    defeated this phase, this unit gains Raid 3."

    A conditional SELF ``KeywordGrant`` with a value over the new
    ``ANY_LEADER_UNIT_DEFEATED_THIS_PHASE`` atom — EITHER player's leader, so the
    ledger it reads is not keyed by controller.  Registering it strips his mistagged
    printed Raid (sanitiser rule 2), so a Pellaeon with no leader in the graveyard
    really lacks it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", value=3)],
        condition=ConditionCheck(Condition.ANY_LEADER_UNIT_DEFEATED_THIS_PHASE),
    )


@card_ability("ASH", "98")
def _at_st_raider():
    """ASH_98 — AT-ST Raider (Unit, 4/5): "While you control ANOTHER non-<uq> unit,
    this unit gains Ambush."

    The new ``CONTROLLER_HAS_OTHER_NON_UNIQUE_UNIT`` atom — the self-excluding
    sibling of Rose Tico LAW_223's: the Raider is itself non-unique and would
    otherwise always satisfy its own clause.  A granted Ambush still fires on entry
    (the enter-play listener reads ``has_keyword`` once the unit is in its arena)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Ambush")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_NON_UNIQUE_UNIT),
    )


@card_ability("ASH", "100")
def _gallius_rax():
    """ASH_100 — Gallius Rax (Unit, 4/7, unique): "Other friendly units with 2 or
    more DIFFERENT keywords get +2/+2."

    A plain aura ``StatBonus`` whose filter is the new ``n_plus_keywords_2``
    predicate.  That predicate counts through ``keywords.distinct_keyword_count``,
    the LIGHTWEIGHT count — a full ``has_keyword`` sweep would recurse back into the
    constant scans that are evaluating this very aura (the Boba Fett SHD_8
    ``has_any_keyword`` lesson)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self", "n_plus_keywords_2")),
        effects=[StatBonus(power=2, hp=2)],
    )


# ── ash-set:17 — combat tricks, buffs & tempo ────────────────────────────────


@card_ability("ASH", "105")
def _bo_katan_kryze_unit():
    """ASH_105 — Bo-Katan Kryze (Unit, Mandalorian, 2/4, unique): "While you control
    another Mandalorian unit, this unit gains Raid 2." """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", value=2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 param="Mandalorian"),
    )


def _t6_buff_then_attack(state, source_ci, target_id, event_ctx):
    """T-6 Shuttle ASH_109: "Give another unit +2/+2 for this phase.  You may attack
    with that unit."

    ONE targeted effect: the buff and the attack must name the SAME unit, so the
    attack is pushed with ``attacker_id`` pinned to the chosen target rather than
    offered as a second free choice.  ``optional=True`` carries the "you may"; the
    push is skipped for a unit that could not attack anyway, so a dead prompt never
    appears (``push_granted_attack`` probes the same filter ``legal_actions`` uses)."""
    from swu.abilities.resolver import _make_modifier
    from swu.engine.actions import push_granted_attack
    if not target_id:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id, 2, 2, Duration.THIS_PHASE))
    push_granted_attack(state, source_ci, attacker_id=target_id, optional=True)
    return state


@card_ability("ASH", "109")
def _t6_shuttle_1974():
    """ASH_109 — T-6 Shuttle 1974 (Unit, 2/6, unique): "Sentinel.  Action [Exhaust]:
    Give another unit +2/+2 for this phase.  You may attack with that unit." """
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(
            fn=_t6_buff_then_attack,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("not_self",)))],
        title="Buff another unit and attack with it",
    )


@card_ability("ASH", "113")
def _mandalorian_flagship():
    """ASH_113 — Mandalorian Flagship (Unit, 4/8, unique): "While you control a
    leader unit, this unit gains Ambush.  |  This unit gets +1/+0 for each other
    friendly Mandalorian unit."

    ``CONTROLLER_HAS_LEADER_UNIT`` (Jedha Agitator SOR_158) plus the self-excluding
    scaling count ``other_controller_trait_units_Mandalorian`` (Kit Fisto LOF_11) —
    the Flagship is itself Mandalorian, so the exclusion is the printed "other"."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Ambush")],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(
                power=1, hp=0,
                count="other_controller_trait_units_Mandalorian")],
        ),
    ]


@card_ability("ASH", "114")
def _sabines_lightsaber():
    """ASH_114 — Sabine's Lightsaber (Upgrade, +2/+2, unique): "Attach to a
    non-Vehicle unit.  If attached unit is Sabine Wren OR a Force unit, it gains
    Restore 2."

    The upgrade-SELF ``KeywordGrant`` again, so the condition is evaluated against
    the HOST — ``SOURCE_NAMED`` / ``SOURCE_HAS_TRAIT``, never their
    ``ATTACHED_HOST_*`` cousins — and the "or" is one ``ANY_OF`` composite rather
    than two specs, so a Force Sabine still only gets Restore 2 once."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", value=2)],
        condition=ConditionCheck(Condition.ANY_OF, param=(
            ConditionCheck(Condition.SOURCE_NAMED, param="Sabine Wren"),
            ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Force"),
        )),
    )


def _student_guides_master(state, source_ci, target_id, event_ctx):
    """The Student Guides the Master ASH_115: "Give a friendly unit +1/+0 for this
    phase for each OTHER friendly unit with less power than it."

    A conditional MAGNITUDE read at resolution (the Zeb Orellios LAW_45 shape): the
    chosen unit is known, so the count is a straight board read — and it uses
    EFFECTIVE power on both sides, so an already-buffed unit counts correctly."""
    from swu.abilities.resolver import _make_modifier
    from swu.engine.actions import compute_power
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, chosen = res
    mine = compute_power(state, chosen)
    count = sum(1 for arena in (holder.ground_arena, holder.space_arena)
                for u in arena
                if u.instance_id != chosen.instance_id
                and compute_power(state, u) < mine)
    if count <= 0:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id, count, 0, Duration.THIS_PHASE))
    return state


@card_ability("ASH", "115")
def _the_student_guides_the_master():
    """ASH_115 — The Student Guides the Master (Event, 1): "Give a friendly unit
    +1/+0 for this phase for each other friendly unit with less power than it." """
    return EventAbility(effects=[CustomEffect(
        fn=_student_guides_master,
        target=TargetSpec(controller="friendly", kind="unit"))])


@card_ability("ASH", "120")
def _warrior_of_clan_kryze():
    """ASH_120 — Warrior of Clan Kryze (Unit, 2/3): "While you control another
    exhausted unit, this unit gains Sentinel."

    ``CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT`` (C-3PO SEC_15) — the self-exclusion
    matters, since this unit is exhausted for most of the round it is played."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT),
    )


@card_ability("ASH", "125")
def _stolen_eta_shuttle():
    """ASH_125 — Stolen Eta Shuttle (Unit, 3/5): "Hidden.  While you have the
    initiative, this unit gets +2/+0." """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


# ── ash-set:18 — combat tricks, buffs & tempo ────────────────────────────────
#
# Mostly Advantage-token payouts.  Two of them arrive AT the end of an attack
# (ASH_144 here, Bokken Saber ASH_180 in the next group), which is why the
# pipelines now snapshot the Advantage tokens an attack rode with BEFORE firing
# its attack-end triggers (``actions._snapshot_advantage_tokens``) — otherwise the
# token would be swept away by the very attack that granted it.


@card_ability("ASH", "127")
def _the_twins():
    """When Played/On Attack: You may give another friendly unit Sentinel for this
    phase.  When another friendly unit is defeated: Heal 1 damage from your base.

    One targeted this-phase ``GrantKeyword`` under both printed triggers (the
    Captain Rex SEC_48 shape), plus a ``WhenUnitDefeated`` observer narrowed to
    friendly units and excluding the Twins themselves ("another")."""
    def _grant():
        return GrantKeyword(
            "Sentinel", 0,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            duration=Duration.THIS_PHASE)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[_grant()], optional=True),
        TriggerAbility(trigger=OnAttack(), effects=[_grant()], optional=True),
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("not_self",))),
            effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
        ),
    ]


def _trask_eligible(card_def) -> bool:
    """A unit costing 7 or less — Trask Walker ASH_133's discard-pile filter."""
    from swu.cards.models import Unit
    return isinstance(card_def, Unit) and int(getattr(card_def, "cost", 0) or 0) <= 7


def _trask_choose(state, source_ci, target_id, event_ctx):
    """Offer the two dispositions, but only with something to choose (ASH_133)."""
    from swu.engine.actions import push_choose_modal
    ps = state.player_by_id(source_ci.owner_id)
    if not any(_trask_eligible(ci.card_def) for ci in ps.discard):
        return state
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _trask_bottom_heal(state, source_ci, target_id, event_ctx):
    """"…put that card on the bottom of your deck and heal 3 from your base"."""
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(state, source_ci, count=1, own_only=True,
                             eligible=_trask_eligible, then_heal_base=3)
    return state


def _trask_return(state, source_ci, target_id, event_ctx):
    """"…or return it to your hand"."""
    from swu.engine.actions import push_return_from_discard
    push_return_from_discard(state, source_ci, count=1,
                             eligible=_trask_eligible, up_to=False)
    return state


@card_ability("ASH", "133")
def _trask_walker():
    """When Played/On Attack: Choose a unit in your discard pile that costs 7 or
    less.  Either put that card on the bottom of your deck and heal 3 damage from
    your base or return it to your hand.

    The "either/or" is a ``choose_two_modal`` at ``pick=1`` whose two options are
    ``EventAbility`` specs (Trask is a UNIT card, so they must never be
    trigger-collected — the Lightmaker SEC_207 rule), each pushing the decision that
    already models its disposition: ``bottom_from_discard`` with the new
    ``then_heal_base`` payoff, or ``return_from_discard``.  Both narrow the pile to
    the same "unit costing 7 or less" predicate, and the modal is not pushed at all
    when no such card is in the discard."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_trask_choose)]),
        EventAbility(effects=[CustomEffect(fn=_trask_bottom_heal)]),
        EventAbility(effects=[CustomEffect(fn=_trask_return)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_trask_choose)]),
    ]


@card_ability("ASH", "136")
def _display_of_strength():
    """Give a unit +3/+3 for this phase."""
    return EventAbility(effects=[ModifyStats(
        power=3, hp=3,
        target=TargetSpec(controller="any", kind="unit"),
        duration=Duration.THIS_PHASE)])


@card_ability("ASH", "144")
def _vanes_snub_fighter():
    """When a friendly unit's attack ends: If it dealt combat damage to a base, give
    an Advantage token to this unit.

    ``WhenFriendlyUnitAttackEnds(require_base_damage_min=1)`` — the threshold form
    built for Ezra Bridger ASH_13, here at its minimum, so the trigger is not even
    collected when the attack put nothing on a base."""
    return TriggerAbility(
        trigger=WhenFriendlyUnitAttackEnds(require_base_damage_min=1),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    )


def _grogu_attack(state, source_ci, target_id, event_ctx):
    """"You may attack with a unit" (Grogu ASH_155)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True)
    return state


@card_ability("ASH", "155")
def _grogu_ash():
    """When you take the initiative: You may attack with a unit.

    The "you may" rides on the decision's own decline (``optional=True``) rather
    than on the trigger, so the player is prompted once."""
    return TriggerAbility(
        trigger=WhenYouTakeInitiative(),
        effects=[CustomEffect(fn=_grogu_attack)],
    )


@card_ability("ASH", "157")
def _danger_squadron_wingmen():
    """On Attack: You may give an Advantage token to another unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Advantage", TargetSpec(
            controller="any", kind="unit", predicates=("not_self",)))],
        optional=True,
    )


@card_ability("ASH", "159")
def _alphabet_squadron_u_wing():
    """Overwhelm.  When the regroup phase starts: Give an Advantage token to a unit.

    Overwhelm is printed and handled by the keyword layer; the trigger is the
    long-standing regroup ``PhaseStartTrigger``."""
    return TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[GiveToken("Advantage",
                           TargetSpec(controller="any", kind="unit"))],
    )


# ── ash-set:19 — combat tricks, buffs & tempo ────────────────────────────────


def _kachirho_ready(state, source_ci, target_id, event_ctx):
    """Ready Kachirho Militia and charge its once-each-round use (ASH_160)."""
    from swu.engine.actions import note_unit_readied
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    res = state.find_instance(source_ci.instance_id)
    if res is not None and res[1].exhausted:
        note_unit_readied(state, res[1])
        res[1].exhausted = False
    return state


@card_ability("ASH", "160")
def _kachirho_militia():
    """Hidden.  When an enemy ground unit attacks your base: Ready this unit.  Use
    this ability only once each round.

    ``WhenEnemyAttacksYourBase(arena="ground")`` (Aurra Sing TWI_166) with the shared
    ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` limiter charged inside the effect
    (Toro Calican SHD_239).  The ready goes through ``note_unit_readied`` so a
    WhenUnitReadies observer still sees it."""
    return TriggerAbility(
        trigger=WhenEnemyAttacksYourBase(arena="ground"),
        effects=[CustomEffect(fn=_kachirho_ready)],
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


def _rash_action_attack(state, source_ci, target_id, event_ctx):
    """Attack with a unit at +1/+0, taxing a damaged opponent base (ASH_162)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1,
                        opponent_discard_if_base_damaged=True)
    return state


@card_ability("ASH", "162")
def _rash_action():
    """Attack with a unit.  For this attack, it gets +1/+0 and gains: "When Attack
    Ends: If this unit dealt combat damage to an opponent's base, that opponent
    discards a card."

    The granted trigger is the new ``opponent_discard_if_base_damaged`` rider —
    the opponent-facing sibling of Stay on Target JTL_177's ``draw_if_base_damaged``,
    sharing its before/after base snapshot (so an Overwhelm spill counts exactly like
    a direct base attack) and its settle point."""
    return EventAbility(effects=[CustomEffect(fn=_rash_action_attack)])


@card_ability("ASH", "167")
def _flarestar_attack_shuttle():
    """When Played/When Defeated: You may give an Advantage token to a unit."""
    def _tok():
        return GiveToken("Advantage",
                         TargetSpec(controller="any", kind="unit"))
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[_tok()], optional=True),
        TriggerAbility(trigger=WhenDefeated(), effects=[_tok()], optional=True),
    ]


def _ice_spider_tokens(state, source_ci, target_id, event_ctx):
    """One Advantage token per ENEMY unit, onto the Spider itself (ASH_178)."""
    from swu.engine.tokens import attach_token
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    holder, me = res
    enemies = sum(len(ps.ground_arena) + len(ps.space_arena)
                  for ps in state.players if ps.player_id != holder.player_id)
    for _ in range(enemies):
        attach_token(state, holder, me, "Advantage")
    return state


@card_ability("ASH", "178")
def _knobby_white_ice_spider():
    """Hidden.  When Played: For each enemy unit, give an Advantage token to this
    unit.

    A count with no fixed magnitude, so it is a ``CustomEffect`` looping
    ``attach_token`` (Imposing Scout Walker ASH_176's shape) rather than a
    ``GiveToken``, whose ``count`` is static."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_ice_spider_tokens)])


@card_ability("ASH", "180")
def _bokken_saber():
    """Attach to a non-Vehicle unit.  Attached unit gains: "When Attack Ends: Give an
    Advantage token to this unit."

    A ``GrantedAbility``, so the trigger matches and resolves from the HOST — "this
    unit" is the host, not the saber.  The token survives the attack that granted it
    because the pipelines snapshot the Advantage tokens BEFORE firing their
    attack-end triggers (see ``_snapshot_advantage_tokens``)."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    ))


@card_ability("ASH", "181")
def _mark_my_words():
    """Attach to a damaged unit.  Attached unit gains Overwhelm.

    The upgrade-SELF ``KeywordGrant``: the keyword layer's attached-upgrade scan
    reads a ``ConstantAbility(target=SELF)`` on an upgrade and confers it on the HOST
    (Grievous's Wheel Bike TWI_236, Constructed Lightsaber LOF_261).  The "Attach to
    a damaged unit" restriction is parsed straight off the text by
    ``_upgrade_target_spec``."""
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[KeywordGrant("Overwhelm")])


def _unfettered_ambition_tokens(state, source_ci, target_id, event_ctx):
    """One Advantage token per non-Advantage upgrade on the host (ASH_182).

    The upgrade is already attached when its own When Played fires, so "(including
    this one)" needs no special case."""
    from swu.engine.tokens import attach_token
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    holder, host = res
    n = sum(1 for u in host.attached_upgrades
            if getattr(u.card_def, "name", "") != "Advantage")
    owner = state.player_by_id(source_ci.owner_id)
    for _ in range(n):
        attach_token(state, owner, host, "Advantage")
    return state


@card_ability("ASH", "182")
def _unfettered_ambition():
    """When Played: For each upgrade on attached unit not named Advantage (including
    this one), give an Advantage token to attached unit."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_unfettered_ambition_tokens)])


# ── ash-set:20 — combat tricks, buffs & tempo ────────────────────────────────


def _follow_me_attack(state, source_ci, target_id, event_ctx):
    """"Attack with a unit" (Follow Me ASH_184)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci)
    return state


@card_ability("ASH", "184")
def _follow_me():
    """Attack with a unit.  After completing the attack, give 3 Advantage tokens to
    a unit.

    TWO ``EventAbility`` specs, not two effects (the Barrel Roll JTL_228 rule):
    ``_resolve_event_ability`` walks them in order, so the TARGETED token effect
    pushes its ChooseTarget first and the lone no-target attack pushes the
    ``granted_attack`` ON TOP — attack first, tokens after."""
    return [
        EventAbility(effects=[GiveToken(
            "Advantage", TargetSpec(controller="any", kind="unit"), count=3)]),
        EventAbility(effects=[CustomEffect(fn=_follow_me_attack)]),
    ]


@card_ability("ASH", "188")
def _galvanized_leap():
    """Ready a unit that was damaged this phase.

    The new ``damaged_this_phase`` predicate over
    ``game_memory.units_damaged_this_phase`` — the mirror of Barriss Offee TWI_42's
    heal ledger.  NOT the ``damaged`` predicate: a unit healed since the hit still
    qualifies, and one that walked in already damaged does not."""
    return EventAbility(effects=[ReadyCard(TargetSpec(
        controller="any", kind="unit", predicates=("damaged_this_phase",)))])


@card_ability("ASH", "197")
def _executor():
    """This unit gets +1/+0 for each upgrade on other friendly units.
    When Played: Give an Advantage token to each other friendly unit.

    The new ``upgrades_on_other_friendly_units`` StatBonus count.  A Shield /
    Experience / Advantage token IS an upgrade, so the Executor grows with its own
    When Played gift."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0,
                               count="upgrades_on_other_friendly_units")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[GiveToken("Advantage", TargetSpec(
                controller="friendly", kind="unit",
                predicates=("not_self",), fixed=EACH_FRIENDLY))],
        ),
    ]


@card_ability("ASH", "198")
def _nowhere_to_hide():
    """Attached unit gains Sentinel.

    The upgrade-SELF ``KeywordGrant`` (Grievous's Wheel Bike TWI_236) — the keyword
    layer's attached-upgrade scan confers it on the HOST.  Its −2/+0 upgrade box is
    printed stats and needs no registration; the printed Sentinel bar is a mistag the
    sanitiser strips (rule 1, "Attached unit gains Sentinel")."""
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[KeywordGrant("Sentinel")])


@card_ability("ASH", "204")
def _blade_three():
    """When your base is dealt damage: Give an Advantage token to this unit.

    The ``WhenDamageDealtToYourBase`` settle-drain observer (The Daughter LOF_252),
    so damage from ANY source counts — an attack, an ability, an Overwhelm spill."""
    return TriggerAbility(
        trigger=WhenDamageDealtToYourBase(),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    )


def _inspiring_veteran_tokens(state, source_ci, target_id, event_ctx):
    """"Give an Advantage token to each of up to 3 exhausted units" (ASH_205)."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Advantage", max_targets=3,
                      predicates=["exhausted"])
    return state


@card_ability("ASH", "205")
def _inspiring_veteran():
    """When Played: Give an Advantage token to each of up to 3 exhausted units."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_inspiring_veteran_tokens)])


@card_ability("ASH", "206")
def _kelleran_beq():
    """Ambush.  This unit gets +1/+0 for each other unit (friendly and enemy) with 0
    power.

    The new ``other_zero_power_units`` StatBonus count, which reads EFFECTIVE power
    and therefore carries a reentrancy guard (the ``SOURCE_POWER_MIN`` lesson): the
    bonus lands on Kelleran alone, so it can never change another unit's power and a
    re-entrant 0 is also the right answer."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=0, count="other_zero_power_units")],
    )


# ── ash-set:21 — combat tricks, buffs & tempo ────────────────────────────────


@card_ability("ASH", "207")
def _heroic_purrgil():
    """Ambush.  While attacking using Ambush, this unit gets +2/+0.

    The new ``AmbushAttackerBonus`` marker, read at ``UseAmbush.apply`` — the sole
    seam an Ambush attack is declared — as a ``this_attack`` stats modifier.  A
    ``ConstantAbility(while_attacking=…)`` could not say it: that flag knows only
    THAT the source is attacking, never whether Ambush declared the attack."""
    return AmbushAttackerBonus(power=2, hp=0)


@card_ability("ASH", "208")
def _sabine_wren_ash():
    """Shielded.  When 1 or more upgrades attach to this unit (including from
    Shielded): You may exhaust a ground unit.

    The new ``WhenUpgradeAttached`` settle-drain observer.  Its ledger is fed by
    ``tokens.attach_token`` too, which is exactly what makes the parenthetical work —
    a Shield token IS an upgrade — and the drain coalesces per host, so "1 or more"
    fires once however many arrive together."""
    return TriggerAbility(
        trigger=WhenUpgradeAttached(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        arena="ground"))],
        optional=True,
    )


@card_ability("ASH", "214")
def _amnesty_officer():
    """When Played: You may exhaust a unit with one or more keywords.

    The ``has_any_keyword`` predicate (Boba Fett SHD_8) — deliberately the
    LIGHTWEIGHT keyword check, for the same reason it was built."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("has_any_keyword",)))],
        optional=True,
    )


def _mandalorian_scout_exhaust_resource(state, source_ci, target_id, event_ctx):
    """Exhaust one ready friendly resource (ASH_216).

    Resources are fungible and not targetable cards, so the pick is automatic (the
    K-2SO SOR_145 convention)."""
    ps = state.player_by_id(source_ci.owner_id)
    for r in ps.resources:
        if not r.exhausted:
            r.exhausted = True
            break
    return state


@card_ability("ASH", "216")
def _mandalorian_scout():
    """When Defeated: Exhaust a ready friendly resource."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_mandalorian_scout_exhaust_resource)],
    )


@card_ability("ASH", "217")
def _mayors_majordomo():
    """Action [Exhaust, discard a card from your hand]: Exhaust a unit.

    ``DiscardCardCost`` (Kylo Ren SHD_11) beside the exhaust; the discard is the
    standing first-card simplification."""
    return ActivatedAbility(
        costs=[ExhaustSelf(), DiscardCardCost()],
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit"))],
        title="Exhaust a unit",
    )


def _jod_pay_and_choose_arena(state, source_ci, target_id, event_ctx):
    """Pay 4 resources; if you do, choose an arena to exhaust (ASH_219).

    Cost and payoff in ONE effect (the "If you do" binding), so an unpaid cost can
    never reach the arena choice."""
    from swu.engine.actions import _exhaust_resources, push_choose_modal
    ps = state.player_by_id(source_ci.owner_id)
    if sum(1 for r in ps.resources if not r.exhausted) < 4:
        return state
    _exhaust_resources(ps, 4)
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


@card_ability("ASH", "219")
def _jod_na_nawood():
    """Sentinel.  When Played: You may pay 4 resources.  If you do, choose an arena.
    Exhaust each unit in that arena.

    Gated on ``CONTROLLER_N_PLUS_READY_RESOURCES(4)`` so the "you may" is never
    offered unaffordable (Boba Fett LAW_214); the arena choice is
    ``push_choose_modal(pick=1)`` over two ``EventAbility`` options — Jod is a UNIT
    card, so they must never be trigger-collected (the Lightmaker SEC_207 rule)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_jod_pay_and_choose_arena)],
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                     param=4),
        ),
        EventAbility(effects=[ExhaustCard(TargetSpec(
            controller="any", kind="unit", arena="ground",
            fixed=EACH_IN_PLAY))]),
        EventAbility(effects=[ExhaustCard(TargetSpec(
            controller="any", kind="unit", arena="space",
            fixed=EACH_IN_PLAY))]),
    ]


def _helix_starfighter_tokens(state, source_ci, target_id, event_ctx):
    """Shield if an opponent controls a space unit, otherwise 2 Advantage (ASH_221).

    The Zeb Orrelios LAW_45 conditional read, decided at resolution — one effect, so
    the branch cannot split across two prompts."""
    from swu.engine.tokens import attach_token
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    holder, me = res
    enemy_space = any(ps.space_arena for ps in state.players
                      if ps.player_id != holder.player_id)
    if enemy_space:
        attach_token(state, holder, me, "Shield")
    else:
        attach_token(state, holder, me, "Advantage")
        attach_token(state, holder, me, "Advantage")
    return state


@card_ability("ASH", "221")
def _helix_starfighter():
    """When Played: If an opponent controls a space unit, give a Shield token to this
    unit.  Otherwise, give 2 Advantage tokens to this unit."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_helix_starfighter_tokens)])


# ── ash-set:22 — combat tricks, buffs & tempo ────────────────────────────────


def _elzar_distribute(state, source_ci, target_id, event_ctx):
    """Distribute up to 5 Advantage tokens among OTHER friendly units (ASH_224)."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Advantage", max_targets=5,
                      controller="friendly", predicates=["not_self"],
                      allow_repeats=True, then_opponent_event_search=True)
    return state


@card_ability("ASH", "224")
def _elzar_mann():
    """While you control a Force leader, this unit enters play ready.
    When Played: Distribute up to 5 Advantage tokens among other friendly units.
    Then, an opponent searches twice that many cards from the top of their deck for
    an event, reveals it, and draws it.

    "Distribute … among" is ``push_select_token`` in the new ``allow_repeats`` mode,
    which turns the select-up-to-N loop into a POOL: a unit already given a token
    stays pickable, so all 5 may land on one unit.  The drawback is its
    ``then_opponent_event_search`` rider, settled at the resolve so it scales with
    what was really given (and searches nothing when nothing was)."""
    return [
        EntersPlayReady(condition=ConditionCheck(
            Condition.CONTROLLER_HAS_TRAIT_LEADER, param="Force")),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_elzar_distribute)]),
    ]


@card_ability("ASH", "227")
def _heightened_awareness():
    """Attached unit gains: "When the regroup phase starts: Give an Advantage token
    to this unit." """
    return GrantedAbility(ability=TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    ))


def _preparation_exhaust_host(state, source_ci, target_id, event_ctx):
    """Exhaust the unit this upgrade just attached to (ASH_228)."""
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    res = state.find_instance(host_id)
    if res is not None:
        res[1].exhausted = True
    return state


@card_ability("ASH", "228")
def _preparation():
    """When Played: Exhaust attached unit.

    The host is ``event_ctx["attached_to_id"]``, which the upgrade-play site threads
    (Frozen in Carbonite SHD_193)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_preparation_exhaust_host)])


def _diplomatic_pageantry_friendly(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen FRIENDLY unit and remember it (ASH_231)."""
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    res[1].exhausted = True
    event_ctx["prior_target_id"] = target_id
    return state


def _diplomatic_pageantry_enemy(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen ENEMY unit; if you do, pay the friendly unit 2 tokens."""
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    res[1].exhausted = True
    ally = state.find_instance(event_ctx.get("prior_target_id") or "")
    if ally is not None:
        from swu.engine.tokens import attach_token
        attach_token(state, ally[0], ally[1], "Advantage")
        attach_token(state, ally[0], ally[1], "Advantage")
    return state


@card_ability("ASH", "231")
def _diplomatic_pageantry():
    """Exhaust a friendly unit and an enemy unit.  If you do, give 2 Advantage tokens
    to that friendly unit.

    The LAW_41 shared-``event_ctx`` chain: the friendly pick stamps
    ``prior_target_id``, the enemy pick is gated by ``requires_prior_target`` and
    carries the payoff, so an unpaid half can never hand out the tokens."""
    return EventAbility(effects=[
        CustomEffect(fn=_diplomatic_pageantry_friendly,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_diplomatic_pageantry_enemy,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("requires_prior_target",))),
    ])


def _keep_them_talking_exhaust(state, source_ci, target_id, event_ctx):
    """Exhaust one chosen unit and bar it from the second pick (ASH_233)."""
    from swu.abilities.resolver import _target_protected
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is not None and not _target_protected(state, target_id, source_ci,
                                                 "exhaust"):
        res[1].exhausted = True
    event_ctx.setdefault("excluded_target_ids", set()).add(target_id)
    return state


@card_ability("ASH", "233")
def _keep_them_talking():
    """Exhaust up to 2 units that each cost 3 or less.

    Two optional targeted steps over the accumulating ``excludes_event_targets`` set
    (Attack Pattern Delta SOR_106) — that IS "up to 2 DIFFERENT units", and each
    carries the cost cap in its own spec.  ⚠️ The steps must be ``CustomEffect``s: it
    is the effect fn that STAMPS ``excluded_target_ids``, so a plain declarative
    ``ExhaustCard`` pair would offer (and take) the same unit twice."""
    def _step():
        return CustomEffect(fn=_keep_them_talking_exhaust, target=TargetSpec(
            controller="any", kind="unit", cost_max=3, optional=True,
            predicates=("excludes_event_targets",)))
    return EventAbility(effects=[_step(), _step()])


def _masterstroke_attack(state, source_ci, target_id, event_ctx):
    """Attack, scaled by the defending player's units in the attacker's arena."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, bonus_per_defending_arena_unit=1)
    return state


@card_ability("ASH", "234")
def _masterstroke():
    """Attack with a unit.  It gets +1/+0 for this attack for each unit the defending
    player controls in its arena.

    The new ``bonus_per_defending_arena_unit`` rider — the population sibling of
    Corner the Prey TWI_139's ``bonus_per_defender_damage``, measured (like it) just
    before combat."""
    return EventAbility(effects=[CustomEffect(fn=_masterstroke_attack)])


@card_ability("ASH", "237")
def _mouse_droid():
    """Raid 1.  When Played: The next Imperial unit you play this phase costs 1
    resource less."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[NextPlayDiscount(trait="Imperial", amount=1)])


# ── ash-set:23 — combat tricks, buffs & tempo ────────────────────────────────


@card_ability("ASH", "240")
def _mandalorian_super_commandos():
    """While you control a leader unit, this unit gets +2/+0."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
    )


def _eye_of_sion_search(state, source_ci, target_id, event_ctx):
    """Search 8 for a unit costing at most this unit's power; play it free, ready."""
    from swu.engine.actions import compute_power, push_search_and_play
    from swu.cards.models import Unit
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    cap = compute_power(state, res[1])
    push_search_and_play(
        state, res[1], window=8, free=True, enters_ready=True,
        eligible=lambda cd: (isinstance(cd, Unit)
                             and int(getattr(cd, "cost", 0) or 0) <= cap))
    return state


@card_ability("ASH", "245")
def _eye_of_sion():
    """Action [Exhaust]: Search the top 8 cards of your deck for a unit that costs the
    same as or less than this unit's power.  Play it for free.  It enters play ready.

    ``push_search_and_play`` at its ``free`` + ``enters_ready`` settings (Triple Dark
    Raid SHD_194 / Bounty Hunter's Quarry SHD_123); the cap is EFFECTIVE power, read
    at resolution, so an upgrade or an Advantage token widens the search."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_eye_of_sion_search)],
        title="Search for a unit and play it free",
    )


def _neel_arm_enters_ready(state, source_ci, target_id, event_ctx):
    """Arm "the next unit you play this phase with 1 or less power enters ready"."""
    state.game_memory.pending_enters_ready.append(
        {"player_id": source_ci.owner_id, "power_max": 1})
    return state


@card_ability("ASH", "248")
def _neel():
    """When Played/On Attack: The next unit you play this phase with 1 or less power
    enters play ready.

    The new ``game_memory.pending_enters_ready`` charge list — the
    ``pending_keyword_grants`` (Deceptive Shade LOF_180) shape, consumed in
    ``_put_unit_in_play`` and cleared at the phase rollover."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_neel_arm_enters_ready)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_neel_arm_enters_ready)]),
    ]


@card_ability("ASH", "251")
def _zealous_soldier():
    """When Played: Give an Advantage token to this unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Advantage", TargetSpec(kind="unit", fixed=SELF))],
    )


@card_ability("ASH", "255")
def _anakin_skywalker_ash():
    """Hidden.  Saboteur.  When Played: Give a Shield token to another friendly
    unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="friendly", kind="unit", predicates=("not_self",)))],
    )


def _choose_your_path_choose(state, source_ci, target_id, event_ctx):
    """Offer only the modes whose "if you control …" clause actually holds."""
    from swu.engine.actions import push_choose_modal
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    mine = ps.ground_arena + ps.space_arena
    options = []
    if any(has_trait(state, u, "Force") for u in mine):
        options.append(1)
    if any(has_trait(state, u, "Mandalorian") for u in mine):
        options.append(2)
    if not options:
        return state
    push_choose_modal(state, source_ci, option_indices=options, pick=1)
    return state


def _choose_your_path_mandalorian(state, source_ci, target_id, event_ctx):
    """Create a Mandalorian token and give an Advantage token to IT."""
    from swu.engine.actions import _create_token_units
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    before = {u.instance_id for u in ps.ground_arena + ps.space_arena}
    _create_token_units(state, ps, "Mandalorian", 1)
    ps = state.player_by_id(source_ci.owner_id)
    for u in ps.ground_arena + ps.space_arena:
        if u.instance_id not in before:
            attach_token(state, ps, u, "Advantage")
            break
    return state


@card_ability("ASH", "257")
def _choose_your_path():
    """Choose one:
    If you control a Force unit, heal 5 damage from your base.
    If you control a Mandalorian unit, create a Mandalorian token and give an
    Advantage token to it.

    ``push_choose_modal(pick=1)`` with the dead modes filtered out at push time (The
    Cyborg Mech ASH_147).  ⚠️ This is an EVENT card, so the option specs must be
    ``TriggerAbility`` — ``_resolve_event_ability`` walks every ``EventAbility`` spec
    and would run both options (the Confidence in Victory SEC_145 rule, the exact
    mirror of the Lightmaker SEC_207 one for unit cards)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_choose_your_path_choose)]),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[Heal(5, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_choose_your_path_mandalorian)],
        ),
    ]


@card_ability("ASH", "262")
def _faith_in_the_empire():
    """This upgrade costs 1 resource less to play on an Imperial unit.

    The new ``CostReduction.host_trait`` — the ``host_named`` (Grievous's Wheel Bike
    TWI_236) / ``host_unique`` (Mastery LAW_129) sibling keyed on the chosen host's
    effective traits."""
    return CostReduction(amount=1, host_trait="Imperial")


# ── ash-set:24 — combat tricks, buffs & tempo ────────────────────────────────


@card_ability("ASH", "263")
def _the_way_of_the_mandalor():
    """This upgrade costs 1 resource less to play on a Mandalorian unit."""
    return CostReduction(amount=1, host_trait="Mandalorian")


def _a_new_order_tokens(state, source_ci, target_id, event_ctx):
    """"Give an Advantage token to each of up to 2 units" (ASH_264)."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Advantage", max_targets=2)
    return state


@card_ability("ASH", "264")
def _a_new_order():
    """Give an Advantage token to each of up to 2 units."""
    return EventAbility(effects=[CustomEffect(fn=_a_new_order_tokens)])


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:25 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


def _paz_vizsla_tokens(state, source_ci, target_id, event_ctx):
    """"If this unit wasn't defeated by combat damage, create 2 Mandalorian tokens"
    (Paz Vizsla ASH_28).

    ``event_ctx["defeated_by_combat_damage"]`` is the new ``_defeat_unit`` stamp —
    the exact sibling of ``defeated_while_attacking`` (Luthen Rael SEC_13), set only
    by the four combatant-death sites of the two unit-combat pipelines.  Every other
    defeat route (an ability, the state-based HP sweep, an exploit sacrifice) leaves
    it False, which is exactly what the card means by "wasn't defeated by combat
    damage"."""
    from swu.engine.actions import _create_token_units
    if event_ctx.get("defeated_by_combat_damage"):
        return state
    ps = state.player_by_id(
        event_ctx.get("defeated_controller_id") or source_ci.owner_id)
    _create_token_units(state, ps, "Mandalorian", 2)
    return state


@card_ability("ASH", "28")
def _paz_vizsla():
    """ASH_28 — Paz Vizsla (Unit, Mandalorian, 4/7): "Sentinel  |  When Defeated: If
    this unit wasn't defeated by combat damage, create 2 Mandalorian tokens."

    Sentinel is the keyword layer.  The clause is one no-target ``CustomEffect``
    reading the new ``defeated_by_combat_damage`` event_ctx stamp; the tokens go to
    whoever controlled Paz at the moment of defeat (``defeated_controller_id``, the
    bounty convention), so a control-changed Paz still pays his real controller."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_paz_vizsla_tokens)],
    )


@card_ability("ASH", "34")
def _wicket():
    """ASH_34 — Wicket (Unit, Ewok, 3/3, unique): "Saboteur  |  This unit can't
    attack bases."

    Saboteur is the keyword layer; the bar is the standing ``CannotAttackBases``
    marker (Entrenched SOR_72), read at the attack-enumeration seam
    ``actions._cannot_attack_bases`` so the base-attack option is simply never
    offered."""
    return CannotAttackBases()


@card_ability("ASH", "40")
def _poe_dameron_ash():
    """ASH_40 — Poe Dameron (Unit, Resistance, 3/3, unique): "All units lose
    Sentinel."

    A standing ``KeywordRevoke`` aura over EVERY unit — his own included, which is
    what "all units" says — the Domesticated Loth-Cat ASH_68 shape.  The keyword
    layer reads a revoke ahead of every grant source, so "and can't gain it" and
    "covers units played later" both fall out free, and it lifts when Poe leaves
    play.  His own mistagged printed Sentinel was already stripped by
    keyword-sanitiser rule 10 (the lose-only rule that landed with Support)."""
    return ConstantAbility(
        target=TargetSpec(controller="any", kind="unit"),
        effects=[KeywordRevoke("Sentinel")],
    )


def _gar_saxon_ash_token(state, source_ci, target_id, event_ctx):
    """Create a Mandalorian token and spend Gar Saxon's once-per-round use (ASH_47).

    The Toro Calican SHD_239 ``{instance_id}:trig`` marker, charged only here — i.e.
    on ACCEPT — so declining the "you may" does not spend the round's use."""
    from swu.engine.actions import _create_token_units
    _create_token_units(state, state.player_by_id(source_ci.owner_id),
                        "Mandalorian", 1)
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("ASH", "47")
def _gar_saxon_ash():
    """ASH_47 — Gar Saxon (Unit, Mandalorian Trooper, 3/4, unique): "When you play an
    upgrade on this unit: You may create a Mandalorian token.  Use this ability only
    once each round."

    ``WhenYouPlayCard(card_type="upgrade", on_self=True)`` is the Kylo Ren LOF_229
    observer — ``on_self`` already means "attached to the source", so no extra host
    check is needed.  A Shield / Experience / Advantage token is *created*, never
    *played*, so it correctly does not arm this.  ``optional`` carries the "you may";
    the shared ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` gate offers it at most once
    a round."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="upgrade", on_self=True),
        effects=[CustomEffect(fn=_gar_saxon_ash_token)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


def _pointless_to_resist_debuff(state, source_ci, target_id, event_ctx):
    """Attached unit gets -3/-0 while attacking a base (Pointless to Resist ASH_54).

    A PERMANENT stats modifier carrying the existing ``while_attacking_base`` flag
    (Sly Moore SEC_33) — read only at the base-attack ``compute_power`` site, and
    skipped outright by ``compute_hp``, so the debuff lands exactly when the host
    attacks a base and nowhere else.  ``permanent`` is the Lando JTL_3 lifetime
    recipe: ``_modifier_source_in_play`` counts an attached upgrade as in play, so
    the debuff lapses the moment this Condition leaves the host."""
    from swu.engine.state import Modifier
    host_id = event_ctx.get("attached_to_id")
    if host_id is None:
        return state
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=host_id,
        kind="stats",
        value={"power": -3, "hp": 0, "while_attacking_base": True},
        duration="permanent",
    ))
    return state


@card_ability("ASH", "54")
def _pointless_to_resist():
    """ASH_54 — Pointless to Resist (Upgrade, Condition, cost 1): "Attached unit gets
    -3/-0 while attacking a base."

    Not a ``ConstantAbility``: the attached-upgrade stat scan carries no combat
    context, so it cannot tell a base attack from any other.  Instead the upgrade's
    own When Played lands a permanent ``while_attacking_base`` modifier on its host
    (see ``_pointless_to_resist_debuff``), reusing the flag SEC_33 built."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_pointless_to_resist_debuff)],
    )


@card_ability("ASH", "56")
def _huyang_ash():
    """ASH_56 — Huyang (Unit, Droid Jedi, 2/4, unique): "On Attack: You may give an
    upgraded unit -4/-0 for this phase."

    A plain targeted ``ModifyStats`` over the long-standing ``upgraded`` predicate
    (a Shield / Experience / Advantage token counts as an upgrade, so it reaches
    more than just carded upgrades — the engine-wide reading).  ``optional`` means a
    board with no upgraded unit auto-declines rather than prompting."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=-4, hp=0,
                             target=TargetSpec(controller="any", kind="unit",
                                               predicates=("upgraded",)),
                             duration=Duration.THIS_PHASE)],
        optional=True,
    )


@card_ability("ASH", "58")
def _duchesss_protector():
    """ASH_58 — Duchess's Protector (Unit, Mandalorian, 2/3): "When Defeated: Create a
    Mandalorian token."  """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Mandalorian", 1)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:26 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("ASH", "63")
def _bo_katans_gauntlet():
    """ASH_63 — Bo-Katan's Gauntlet (Unit, Mandalorian Transport Vehicle, 4/5,
    unique): "Restore 1  |  Each other friendly non-token unit gains: 'When Defeated:
    Create a Mandalorian token.'"

    Restore is the keyword layer.  The grant is an ``AuraGrantedAbility`` over a
    ``WhenDefeated`` inner (the Gar Saxon SHD_1 shape), collected at the UnitDefeated
    path with the DYING unit as the trigger source, so each token is created by the
    unit that died.  The new ``non_token`` predicate is what stops the minted
    Mandalorian tokens from minting more of themselves; ``not_self`` is the printed
    "other" (the Gauntlet dying creates nothing)."""
    return AuraGrantedAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self", "non_token")),
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CreateTokenUnit("Mandalorian", 1)],
        ),
    )


@card_ability("ASH", "70")
def _at_attin_safety_droid():
    """ASH_70 — At Attin Safety Droid (Unit, Droid Republic, 1/4): "If your base would
    be dealt more than 4 damage, prevent all but 4 of that damage."

    The new ``BaseDamageCap`` passive marker, read through the single shared helper
    ``actions.base_damage_after_prevention`` — which every base-damage site already
    calls, so ability damage, indirect damage, a base attack, an Overwhelm spill and
    the empty-deck penalty are all capped by one read.  Per INSTANCE, so two separate
    5-damage hits land 4 each; it lifts the moment the Droid leaves play."""
    return BaseDamageCap(amount=4)


def _ryder_azadi_name(state, source_ci, target_id, event_ctx):
    """Name a card (recorded on this unit's ``named_card`` field) — Ryder Azadi
    ASH_77, the Regional Governor SOR_62 adapter verbatim."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci)
    return state


@card_ability("ASH", "77")
def _ryder_azadi():
    """ASH_77 — Ryder Azadi (Unit, New Republic Official, 2/5, unique): "Restore 1  |
    When Played: Name a card.  While this unit is in play, opponents can't play cards
    with that name."

    Regional Governor SOR_62 verbatim: the When Played pushes the ``name_a_card``
    decision and the ``ForbidNamedCardPlay`` marker makes the play-legality seam
    (``actions._named_card_play_forbidden``) bar that name for opponents while Ryder
    stands — distinct from Galen Erso P25_31's ability-suppressing naming, which uses
    the same ``named_card`` field but no marker."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_ryder_azadi_name)]),
        ForbidNamedCardPlay(),
    ]


@card_ability("ASH", "80")
def _covert_believers():
    """ASH_80 — Covert Believers (Unit, Mandalorian, 4/5): "When Defeated: Create a
    Mandalorian token."  """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Mandalorian", 1)],
    )


@card_ability("ASH", "84")
def _arcana_star_map():
    """ASH_84 — Arcana Star Map (Upgrade, Item, cost 1, unique): "Attached unit gains:
    'If you would search a number of cards from your deck, search twice that number of
    cards instead.'"

    The new ``SearchWindowDoubler`` passive marker.  Registered bare on the UPGRADE:
    ``actions._search_window_doubled`` walks the searching player's arena units AND
    each unit's attached upgrades, so "attached unit gains" needs no ConstantAbility
    wrapper — and because the scan is keyed on the HOST's controller, the doubling
    follows the unit if the Star Map ever changes hands.  Read at the single
    ``push_deck_search`` entry point, so every search route doubles at once; only the
    WINDOW doubles, never how many cards may be taken."""
    return SearchWindowDoubler()


def _buy_time_token(state, source_ci, target_id, event_ctx):
    """Create a Mandalorian token and give IT Sentinel for this phase (ASH_91).

    ``_create_token_units`` returns the instances it made, so "give it Sentinel" is a
    plain ``keyword_grant`` modifier on that exact token — no target choice, which is
    right: the card names the token it just created."""
    from swu.engine.actions import _create_token_units
    from swu.engine.state import Modifier
    ps = state.player_by_id(source_ci.owner_id)
    made = _create_token_units(state, ps, "Mandalorian", 1)
    for tok in made:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=tok.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
    return state


@card_ability("ASH", "91")
def _buy_time():
    """ASH_91 — Buy Time (Event, Tactic, cost 3): "Create a Mandalorian token and give
    it Sentinel for this phase."  """
    return EventAbility(effects=[CustomEffect(fn=_buy_time_token)])


def _crix_madine_play(state, source_ci, target_id, event_ctx):
    """"You may play a Heroism unit from your hand.  It costs 2 resources less for
    each arena in which you control the most units" (Crix Madine ASH_108).

    "The most" is STRICTLY more than the opponent — a tie is nobody's most — measured
    per arena at resolution, so the discount is 0, 2 or 4.  ``up_to=True`` carries the
    printed "you may" (that decision is otherwise mandatory-if-able)."""
    from swu.engine.actions import push_play_from_hand
    me = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    reduction = 0
    for mine, theirs in ((me.ground_arena, opp.ground_arena),
                         (me.space_arena, opp.space_arena)):
        if len(mine) > len(theirs):
            reduction += 2
    push_play_from_hand(state, source_ci, aspect="Heroism",
                        cost_reduction=reduction, up_to=True)
    return state


@card_ability("ASH", "108")
def _crix_madine():
    """ASH_108 — Crix Madine (Unit, Official Rebel, 3/2, unique): "When Played: You
    may play a Heroism unit from your hand.  It costs 2 resources less for each arena
    in which you control the most units."

    Crix is already in his arena when his When Played resolves, so he counts himself
    toward the ground majority — the printed reading."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_crix_madine_play)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:27 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("ASH", "111")
def _children_of_the_watch():
    """ASH_111 — Children of the Watch (Unit, Mandalorian, 3/3): "When Played: Create
    2 Mandalorian tokens."  """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Mandalorian", 2)],
    )


@card_ability("ASH", "119")
def _greef_karga_ash119():
    """ASH_119 — Greef Karga (Unit, Official, 2/3, unique): "Action [1 resource,
    Exhaust]: If your base was attacked this phase, create a Mandalorian token."

    The new ``CONTROLLER_BASE_ATTACKED_THIS_PHASE`` atom over the
    ``base_attackers_this_round`` ledger (Ephant Mon SHD_88's), which is keyed by base
    OWNER and written at the base-attack DECLARE step — so it really means "attacked",
    not "damaged".  Used as the ability's ``condition`` (not a ``ConditionalEffect``)
    so the resource and the exhaust are never spent on a no-op — the standing
    "don't offer a no-op" rule; ASH_119 prints no note licensing a wasted use, unlike
    The Client LAW_16."""
    return ActivatedAbility(
        costs=[PayResources(1), ExhaustSelf()],
        effects=[CreateTokenUnit("Mandalorian", 1)],
        title="Create a Mandalorian token",
        condition=ConditionCheck(Condition.CONTROLLER_BASE_ATTACKED_THIS_PHASE),
    )


@card_ability("ASH", "123")
def _lang():
    """ASH_123 — Lang (Unit, Fringe, 2/5, unique): "Action [Exhaust]: This unit deals
    damage equal to his power to a ground unit."

    ``DealDamageEqualTo(count="source_power")`` (Crosshair SHD_87) reads Lang's
    *effective* power, so every buff on him counts at the moment the ability
    resolves."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DealDamageEqualTo(
            count="source_power",
            target=TargetSpec(controller="any", kind="unit", arena="ground"))],
        title="Deal damage equal to this unit's power",
    )


@card_ability("ASH", "124")
def _protectorate_fighter():
    """ASH_124 — Protectorate Fighter (Unit, Fighter Mandalorian Vehicle, 2/1): "When
    Played: If you control a <uq> unit, create a Mandalorian token."

    The new ``CONTROLLER_HAS_UNIQUE_UNIT`` atom (the exact mirror of Rose Tico
    LAW_223's ``CONTROLLER_HAS_NON_UNIQUE_UNIT``) gating trigger COLLECTION, so with
    no unique unit the trigger is never even offered.  The Fighter itself is
    non-unique, so it cannot satisfy its own clause."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Mandalorian", 1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIQUE_UNIT),
    )


@card_ability("ASH", "134")
def _warriors_legacy():
    """ASH_134 — Warrior's Legacy (Upgrade, Learned, cost 3): "Attached unit gains:
    'When Defeated: Create a Mandalorian token.'"

    A ``GrantedAbility`` — it matches and resolves with the HOST as source, and is
    still collected from the DETACHED upgrade when the host dies (the
    ``event_ctx["defeated_upgrades"]`` snapshot), so the token is minted by the very
    defeat that removed the upgrade."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CreateTokenUnit("Mandalorian", 1)],
        ),
    )


@card_ability("ASH", "135")
def _the_darksaber():
    """ASH_135 — The Darksaber (Upgrade, Item Mandalorian Weapon, cost 4, unique):
    "Attach to a <uq> non-Vehicle unit.  |  Attached unit is a leader unit and gains
    the Mandalorian trait.  |  Attached unit gains: 'While you are paying costs, this
    unit provides its aspect icons.'"

    Three clauses, three mechanisms and no decision:
      * "is a leader unit" — the new ``LeaderUnitGrant`` marker, read at the shared
        ``resolver._is_leader_unit`` predicate that already answers this for a
        leader-piloted Vehicle (Boba Fett JTL_9).  The host therefore dodges "defeat a
        non-leader unit" removal and joins "each leader unit you control" auras.
      * "gains the Mandalorian trait" — a SELF ``ConstantAbility`` carrying a
        ``TraitGrant``; the trait layer's attached-upgrade scan confers it on the
        HOST (Jedi Trials LOF_52's shape).
      * "provides its aspect icons" — the new ``ProvidesAspectIcons`` marker, read at
        ``actions._available_aspects``, the single place that decides which icons
        offset an aspect penalty.
    The "Attach to a <uq> non-Vehicle unit" restriction is parsed by the standing
    conservative ``_upgrade_target_spec`` reader; it understands "non-Vehicle" and
    leaves the <uq> half open rather than forbidding a legal host."""
    return [
        LeaderUnitGrant(),
        ProvidesAspectIcons(),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[TraitGrant("Mandalorian")],
        ),
    ]


def _hold_them_off_distribute(state, source_ci, target_id, event_ctx):
    """"That unit deals damage equal to its power divided as you choose among any
    number of units in its arena" (Hold Them Off ASH_139).

    ``push_distribute_damage(restrict_ids=…)`` (Choke on Aspirations LAW_102's
    whitelist) pins the pool to the units standing in the CHOSEN unit's arena — the
    chosen unit included, since the card says "any number of units", not "other".
    The magnitude is the chooser's *effective* power at resolution."""
    from swu.engine.actions import push_distribute_damage, compute_power
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, dealer = res
    arena = dealer.zone
    pool = [u.instance_id for p in state.players
            for u in (p.ground_arena + p.space_arena) if u.zone == arena]
    push_distribute_damage(state, dealer, compute_power(state, dealer),
                           target_controller="any", restrict_ids=pool)
    return state


@card_ability("ASH", "139")
def _hold_them_off():
    """ASH_139 — Hold Them Off (Event, Tactic, cost 4): "Choose a friendly unit.  That
    unit deals damage equal to its power divided as you choose among any number of
    units in its arena."

    ONE targeted ``CustomEffect``: the friendly unit is the effect's target and its
    power becomes the distribution pool, so the player is prompted exactly once for
    the dealer (the Mandalorian SHD_18 single-prompt rule) and then allocates."""
    return EventAbility(effects=[CustomEffect(
        fn=_hold_them_off_distribute,
        target=TargetSpec(controller="friendly", kind="unit"))])


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:28 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("ASH", "140")
def _stronger_together():
    """ASH_140 — Stronger Together (Event, Learned, cost 4): "Create 2 Mandalorian
    tokens."  """
    return EventAbility(effects=[CreateTokenUnit("Mandalorian", 2)])


@card_ability("ASH", "149")
def _eviscerator():
    """ASH_149 — Eviscerator (Unit, Capital Ship Imperial Vehicle, 9/7, unique):
    "Advantage tokens on friendly units lose all abilities.  (They aren't defeated
    after combat.)  |  When Played/On Attack: Give 2 Advantage tokens to each other
    friendly unit."

    The first clause is the new ``AdvantageTokensLoseAbilities`` marker, read at the
    combat pipelines' ``tokens.defeat_advantage_tokens`` sweep — the token's expiry is
    its only ability and it lives there rather than in the registry, so the marker
    simply stops the sweep for that player's units and the +1/+0 stays.  The second is
    ONE ``GiveToken`` over ``EACH_FRIENDLY`` + ``not_self`` (the "other"), registered
    under both printed triggers (the Captain Rex SEC_48 shape)."""
    give = GiveToken("Advantage", count=2,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       fixed=EACH_FRIENDLY,
                                       predicates=("not_self",)))
    return [
        AdvantageTokensLoseAbilities(),
        TriggerAbility(trigger=WhenPlayed(), effects=[give]),
        TriggerAbility(trigger=OnAttack(), effects=[give]),
    ]


@card_ability("ASH", "150")
def _deadly_vulnerability():
    """ASH_150 — Deadly Vulnerability (Upgrade, Condition, cost 1, Overwhelm printed):
    "If attached unit would take damage, it takes twice as much damage instead.  |
    While attached unit is defending, the attacker loses Overwhelm."

    Two passive markers, no trigger and no decision:
      * ``DamageAmplification(amount=0, multiplier=2)`` — the doubling rides the
        existing Vigil SEC_50 read at the single unit-damage chokepoint, which now
        also walks a unit's attached upgrades and understands a multiplier.  Applied
        BEFORE prevention and the Shield, so a Shield still eats the whole (doubled)
        instance, which is the printed layering.
      * ``AttackerLosesOverwhelm`` — read at the two Overwhelm excess-spill steps
        rather than as a ``KeywordRevoke`` aura, since the keyword layer cannot tell
        "while attached unit is DEFENDING" from any other moment.
    The printed Overwhelm on the upgrade is the upgrade's own bar and never transfers
    to a host, so nothing needs stripping."""
    return [
        DamageAmplification(amount=0, by_another_card=False, multiplier=2),
        AttackerLosesOverwhelm(),
    ]


@card_ability("ASH", "177")
def _onyx_cinder():
    """ASH_177 — Onyx Cinder (Unit, Transport Vehicle, 6/6, unique): "Hidden  |  Other
    friendly units gain Hidden."

    A plain ``KeywordGrant`` aura.  Onyx Cinder's own Hidden is PRINTED as its leading
    bar line, so keyword-sanitiser rules 1 and 9 both leave it alone (their line-start
    guard) and only the aura grants the rest."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
        effects=[KeywordGrant("Hidden")],
    )


def _shin_hati_fighter_tokens(state, source_ci, target_id, event_ctx):
    """"Give 2 Advantage tokens to a unit — 3 instead if this unit wasn't defeated by
    combat damage" (Shin Hati's Fiend Fighter ASH_191).

    A Zeb LAW_45 conditional MAGNITUDE decided inside one targeted ``CustomEffect``,
    so the player is prompted once and both readings land on the SAME chosen unit.
    The gate is the new ``defeated_by_combat_damage`` stamp, a plain bool that
    survives the optional trigger's decision round-trip (unlike ``defeated_ci``)."""
    from swu.engine.tokens import attach_token
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, host = res
    count = 2 if event_ctx.get("defeated_by_combat_damage") else 3
    for _ in range(count):
        attach_token(state, ps, host, "Advantage")
    return state


@card_ability("ASH", "191")
def _shin_hatis_fiend_fighter():
    """ASH_191 — Shin Hati's Fiend Fighter (Unit, Fighter Vehicle, 3/1, unique): "When
    Defeated: You may give 2 Advantage tokens to a unit.  If this unit wasn't defeated
    by combat damage, you may give 3 Advantage tokens to that unit instead."  """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_shin_hati_fighter_tokens,
                              target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


def _helgait_distribute(state, source_ci, target_id, event_ctx):
    """"Distribute a number of Advantage tokens equal to this unit's power among
    friendly units" (Helgait ASH_195).

    ``push_select_token(allow_repeats=True)`` is the POOL-DISTRIBUTION form of the
    select-up-to-N loop (Elzar Mann ASH_224): a chosen unit stays pickable, so the
    whole pool may land on one unit.  The magnitude is ``event_ctx["defeated_power"]``
    — the effective power ``_defeat_unit`` snapshots BEFORE stripping his upgrades, so
    a buffed Helgait pays out what he was actually worth."""
    from swu.engine.actions import push_select_token, compute_power
    power = event_ctx.get("defeated_power")
    if power is None:
        power = compute_power(state, source_ci)
    if int(power) <= 0:
        return state
    push_select_token(state, source_ci, token_type="Advantage",
                      max_targets=int(power), controller="friendly",
                      allow_repeats=True)
    return state


@card_ability("ASH", "195")
def _helgait():
    """ASH_195 — Helgait (Unit, Separatist, 6/4, unique): "When Defeated: You may
    distribute a number of Advantage tokens equal to this unit's power among friendly
    units (divided as you choose)."

    The decision's always-legal ``FinishSelectToken`` already carries a "you may", but
    the trigger stays ``optional`` too so the whole clause can be declined without a
    prompt when there is nothing worth doing."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_helgait_distribute)],
        optional=True,
    )


def _there_is_no_conflict_return(state, source_ci, target_id, event_ctx):
    """"Return any number of OTHER upgrades on attached unit to their owners' hands"
    (There Is No Conflict ASH_199).

    ``push_select_token(restrict_ids=…, return_to_hand=True)`` is the Kit Fisto
    LOF_147 shape: the whitelist is exactly the host's other NON-TOKEN upgrades, and
    "any number" is the Kazuda JTL_18 idiom (``max_targets`` = the pool size, with the
    always-offered finish ending it early — including at zero).  Token upgrades
    (Shield / Experience / Advantage) are excluded: they have no owner's hand to
    return to.  The returns run after the decision pops, the standing rule for a
    payoff that can push its own triggers."""
    from swu.engine.actions import push_select_token
    from swu.cards.models import TokenUpgrade
    host_id = event_ctx.get("attached_to_id")
    if host_id is None:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    _ps, host = res
    others = [u.instance_id for u in host.attached_upgrades
              if u.instance_id != source_ci.instance_id
              and not isinstance(u.card_def, TokenUpgrade)]
    if not others:
        return state
    push_select_token(state, source_ci, token_type=None, max_targets=len(others),
                      controller="any", kind="upgrade",
                      restrict_ids=others, return_to_hand=True)
    return state


@card_ability("ASH", "199")
def _there_is_no_conflict():
    """ASH_199 — There Is No Conflict (Upgrade, Innate, cost 2): "When Played: Return
    any number of other upgrades on attached unit to their owners' hands."  """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_there_is_no_conflict_return)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:29 — miscellaneous abilities  (🏁 completes ASH)
# ══════════════════════════════════════════════════════════════════════════════


def _rehabilitation_take(state, source_ci, target_id, event_ctx):
    """"Give that unit -3/-0 for this phase, then take control of it.  At the start of
    the regroup phase, its owner takes control of it" (Rehabilitation ASH_200).

    All three clauses in ONE targeted ``CustomEffect`` (the Mandalorian SHD_18
    single-prompt rule — a separate ``ModifyStats`` would prompt again and could name
    a different unit).  The take-back is the standing Change of Heart SOR_224 pair:
    ``change_control`` plus the one-shot ``return_control_to_owner_at_regroup`` flag
    swept in ``_enter_regroup``."""
    from swu.engine.actions import change_control
    from swu.engine.state import Modifier
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, victim = res
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=victim.instance_id,
        kind="stats",
        value={"power": -3, "hp": 0},
        duration="this_phase",
    ))
    change_control(state, victim, source_ci.owner_id)
    res = state.find_instance(target_id)
    if res is not None:
        res[1].return_control_to_owner_at_regroup = True
    return state


@card_ability("ASH", "200")
def _rehabilitation():
    """ASH_200 — Rehabilitation (Event, Learned, cost 5): "Choose a non-leader unit.
    Give that unit -3/-0 for this phase, then take control of it.  At the start of the
    regroup phase, its owner takes control of it."  """
    return EventAbility(effects=[CustomEffect(
        fn=_rehabilitation_take,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("non_leader",)))])


def _fateful_goodbye_tokens(state, source_ci, target_id, event_ctx):
    """"Distribute 3 Advantage tokens among friendly units — 5 instead if a friendly
    LEADER unit left play this phase" (Fateful Goodbye ASH_211).

    A Zeb LAW_45 conditional magnitude read from two phase ledgers: the leader one is
    the new controller-keyed ``leader_unit_defeat_controllers_this_phase``, the plain
    one the long-standing ``defeated_controllers_this_round``.  With neither satisfied
    nothing is pushed and the event fizzles, which IS the printed "If"."""
    from swu.engine.actions import push_select_token
    pid = source_ci.owner_id
    gm = state.game_memory
    leader_gone = pid in (getattr(gm, "leader_unit_defeat_controllers_this_phase",
                                  None) or set())
    unit_gone = pid in (getattr(gm, "defeated_controllers_this_round", None) or set())
    if leader_gone:
        count = 5
    elif unit_gone:
        count = 3
    else:
        return state
    push_select_token(state, source_ci, token_type="Advantage", max_targets=count,
                      controller="friendly", allow_repeats=True)
    return state


@card_ability("ASH", "211")
def _fateful_goodbye():
    """ASH_211 — Fateful Goodbye (Event, Innate, cost 2): "If a friendly unit left play
    this phase, distribute 3 Advantage tokens among friendly units.  If a friendly
    leader unit left play this phase, distribute 5 Advantage tokens instead."  """
    return EventAbility(effects=[CustomEffect(fn=_fateful_goodbye_tokens)])


@card_ability("ASH", "212")
def _peli_motto():
    """ASH_212 — Peli Motto (Unit, Fringe, 1/1, unique): "Shielded  |  Ignore the
    aspect penalties of the first non-unit card you play each phase."

    Shielded is the keyword layer.  The waiver is ``IgnoreAspectPenaltyForPlays`` at
    the new ``card_type="non_unit"`` (the complement filter), gated by the new
    ``CONTROLLER_NO_NON_UNIT_PLAYED_THIS_PHASE`` atom — which is how "the FIRST … each
    phase" is expressed with no spend ledger at all: the waiver is simply live until
    that player has played a non-unit card this phase.  The phase counter is written
    at the CardPlayed chokepoint, i.e. after the cost is paid, so the first play still
    sees zero and really is waived."""
    return IgnoreAspectPenaltyForPlays(
        card_type="non_unit",
        condition=ConditionCheck(
            Condition.CONTROLLER_NO_NON_UNIT_PLAYED_THIS_PHASE),
    )


@card_ability("ASH", "218")
def _ferry_droid():
    """ASH_218 — Ferry Droid (Unit, Droid, 1/5): "When Played: Give 4 Advantage tokens
    to this unit."  """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Advantage", count=4, target=TargetSpec(fixed=SELF))],
    )


@card_ability("ASH", "238")
def _attendant_navigator():
    """ASH_238 — Attendant Navigator (Unit, First Order, 2/3): "When Played: You may
    give 2 Advantage tokens to a space unit."

    ``optional`` carries the "you may", so with no space unit on either side the
    trigger auto-declines rather than prompting."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Advantage", count=2,
                           target=TargetSpec(controller="any", kind="unit",
                                             arena="space"))],
        optional=True,
    )


def _imperial_defector_look(state, source_ci, target_id, event_ctx):
    """Look at an opponent's hand (ASH_250) — the private ``look_hand`` decision
    (Viper Probe Droid SOR_228 verbatim)."""
    from swu.engine.actions import push_look_opponent_hand
    push_look_opponent_hand(state, source_ci)
    return state


@card_ability("ASH", "250")
def _imperial_defector():
    """ASH_250 — Imperial Defector (Unit, Imperial Rebel, 3/2): "When Played: Look at
    an opponent's hand."  """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_imperial_defector_look)],
    )


@card_ability("ASH", "254")
def _gallofree_transport():
    """ASH_254 — Gallofree Transport (Unit, Rebel Transport Vehicle, 3/5): "When
    Defeated: Give 2 Advantage tokens to a friendly unit."  """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Advantage", count=2,
                           target=TargetSpec(controller="friendly", kind="unit"))],
    )
