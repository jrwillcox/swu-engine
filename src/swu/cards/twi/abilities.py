"""
TWI (Twilight of the Republic) card ability registrations.

The deck's keystone is the **Coordinate** keyword: "Gain this ability/keyword
while you control 3 or more units."  Coordinate is not a single self-contained
keyword effect — it is a conditional *prefix* on a heterogeneous set of abilities
(a stat buff, an enter-play keyword, an on-attack draw, a granted keyword, …),
each gated by the same board condition.  So Coordinate is modelled as the new
``Condition.CONTROLLER_N_PLUS_UNITS`` atom (param=3, the source counts itself),
and every "Coordinate — X" clause is registered as the appropriate ability spec
gated by that condition:

  * a conditional stat buff  → ``ConstantAbility(target=SELF, StatBonus(...),
    condition=COORDINATE)``
  * a conditional keyword     → ``ConstantAbility(target=SELF, KeywordGrant(...),
    condition=COORDINATE)`` (the keyword sanitiser strips the printed always-on
    copy because we model it as a conditional self-grant — the Hunting Nexu
    SHD_168 / Protector of the Throne SHD_247 pattern)
  * a conditional triggered ability → ``TriggerAbility(..., condition=COORDINATE)``
    (the condition gates trigger collection)
  * a conditional activated ability → ``ActivatedAbility(..., condition=COORDINATE)``
    (the condition gates availability in legal_actions)

``CONTROLLER_N_PLUS_UNITS`` counts both arenas (deployed leaders are units and
count; an undeployed leader in base_zone does not).  Because every Coordinate
clause is evaluated while the source unit is already in its arena, "including
this one" falls out for free.
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ConstantAbility, ActivatedAbility, EventAbility, GrantedAbility,
    AuraGrantedAbility,
    WhenDefeated, WhenPlayed, OnAttack, WhenAttacked, WhenYouPlayCard, WhenUnitDefeated,
    WhenOpponentPlaysNthCard, WhenDeployed, WhenYouDeployLeader, PhaseStartTrigger,
    WhenEnemyAttacksYourBase, WhenOpponentPlaysCard, TokensEnterPlayReady,
    WhenAttackEnds, WhenDefeatedAsUpgrade,
    WhenFriendlyUnitDealsCombatDamageToEnemyUnit, IgnoreAspectPenaltyForPlays,
    DealDamage, DealDamageEqualTo, DrawCards, CustomEffect, NextPlayDiscount, CreateTokenUnit,
    DefeatUnit, DefeatAllUnits, IgnoreAspectPenaltyForUpgrades,
    DiscardFromHand, Protection, CaptureUnit,
    ConditionalEffect,
    CannotBeAttackedWhileExhausted, BasesCannotHeal, MultiDefenderAttack,
    SuppressLeaderAbilities, FlipLeaderAspects,
    Heal, ModifyStats, Duration, ReturnToHand, ExhaustCard, GrantKeyword, ReadyCard,
    StatBonus, KeywordGrant, CostReduction,
    ExhaustSelf, PayResources,
    TargetSpec, ConditionCheck, Condition,
    SELF, DEFENDER, EACH_ENEMY, EACH_FRIENDLY, EACH_IN_PLAY,
)

# The Coordinate gate: "while you control 3 or more units".
_COORDINATE = ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3)


# ── LEADERS ──────────────────────────────────────────────────────────────────

@card_ability("TWI", "11")
def _ahsoka_tano():
    """TWI_11 — Ahsoka Tano (Leader, Force/Jedi/Republic, 3/6, Coordinate).

    Undeployed side: "Coordinate — Action [Exhaust]: Attack with a unit.  It gets
    +1/+0 for this attack."  An ``undeployed_only`` ActivatedAbility gated by the
    Coordinate condition, whose one CustomEffect is a thin adapter onto the
    granted-attack seam (the Surprise Strike SOR_220 / Moff Gideon SHD_7 pattern).

    Deployed side: "Coordinate — This unit gets +2/+0."  A self-targeted
    ConstantAbility gated by Coordinate — naturally active only while Ahsoka is in
    an arena (deployed), since the constant scan only sees arena sources.

    The Epic Action deploy ("If you control 5 or more resources, deploy this
    leader") is the standard leader-deploy machinery (deploy_threshold) — no
    ability registration.
    """
    def _coordinate_attack(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=1, hp_bonus=0)
        return state

    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_coordinate_attack)],
            title="Coordinate — Attack with a unit (+1/+0)",
            undeployed_only=True,
            condition=_COORDINATE,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=2, hp=0)],
            condition=_COORDINATE,
        ),
    ]


# ── UNITS ────────────────────────────────────────────────────────────────────

@card_ability("TWI", "90")
def _echo():
    """TWI_90 — Echo: "Coordinate — This unit gets +2/+2." """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=2)],
        condition=_COORDINATE,
    )


@card_ability("TWI", "106")
def _coruscant_guard():
    """TWI_106 — Coruscant Guard: "Coordinate — Ambush."

    A conditional self-grant of the Ambush keyword.  Ambush is an enter-play
    keyword read by ``has_keyword`` at the enter-play bus; the unit is already in
    its arena at that moment, so a controller with 3+ units (including this one)
    triggers Ambush exactly as printed.  The keyword sanitiser strips the printed
    Ambush because this conditional self-grant is registered.
    """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Ambush", value=0)],
        condition=_COORDINATE,
    )


@card_ability("TWI", "114")
def _clone_commander_cody():
    """TWI_114 — Clone Commander Cody (Overwhelm + Coordinate).

    "Coordinate — Each other friendly unit gets +1/+1 and gains Overwhelm."  A
    ConstantAbility over every OTHER friendly unit (``not_self``) granting both a
    StatBonus and Overwhelm, gated by Coordinate.  Cody's own printed Overwhelm is
    the keyword layer (the residual flagged in the spec) — the sanitiser keeps it
    (a bare keyword-bar mention), so it is untouched here.
    """
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
        effects=[StatBonus(power=1, hp=1), KeywordGrant("Overwhelm", value=0)],
        condition=_COORDINATE,
    )


@card_ability("TWI", "147")
def _anakin_skywalker():
    """TWI_147 — Anakin Skywalker: "Coordinate — On Attack: Draw a card."

    A ``TriggerAbility(OnAttack)`` whose ``condition`` gates trigger collection, so
    the draw is offered only while the controller has 3+ units.
    """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(count=1)],
        condition=_COORDINATE,
    )


@card_ability("TWI", "64")
def _ki_adi_mundi():
    """TWI_64 — Ki-Adi-Mundi (canonical; J25_2 is a byte-identical reprint face):
    "Coordinate — When an opponent plays their second card each phase: You may
    draw 2 cards."

    The FRAMEWORK ESCALATION of this batch — a new observer trigger
    ``WhenOpponentPlaysNthCard(count=2)`` firing on an opponent's Nth card each
    phase (a per-phase per-player card-play counter maintained at the CardPlayed
    firing chokepoint; see the trigger docstring).  The Coordinate prefix is the
    ``_COORDINATE`` condition gating trigger collection (offered only while the
    controller has 3+ units, the Anakin TWI_147 pattern); ``optional`` carries the
    "You may".
    """
    return TriggerAbility(
        trigger=WhenOpponentPlaysNthCard(count=2),
        effects=[DrawCards(count=2)],
        optional=True,
        condition=_COORDINATE,
    )


@card_ability("TWI", "158")
def _clone_heavy_gunner():
    """TWI_158 — Clone Heavy Gunner: "Coordinate — This unit gets +2/+0." """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=_COORDINATE,
    )


@card_ability("TWI", "164")
def _hevy():
    """TWI_164 — Hevy (Coordinate + Raid).

    "Coordinate — Raid 2" is a conditional self-grant of Raid 2 (sanitiser strips
    the printed always-on Raid).  Raid's numeric value is read by ``keyword_value``,
    which sums ConstantAbility ``KeywordGrant`` values — so the +2 attacking bonus
    applies only while the controller has 3+ units.

    "When Defeated: Deal 1 damage to each enemy ground unit" — the residual flagged
    in the spec, but trivial and clearly in scope: a ``WhenDefeated`` with a single
    ``DealDamage(1, …)`` auto-targeting every enemy ground unit (``EACH_ENEMY``).
    """
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Raid", value=2)],
            condition=_COORDINATE,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                              arena="ground", fixed=EACH_ENEMY))],
        ),
    ]


@card_ability("TWI", "240")
def _332nd_stalwart():
    """TWI_240 — 332nd Stalwart: "Coordinate — This unit gets +1/+1." """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=1)],
        condition=_COORDINATE,
    )


# ── EVENTS — direct damage (group ahsoka-tano:02) ─────────────────────────────

def _grenade_first(state, source_ci, target_id, event_ctx):
    """Deal 2 damage to the chosen unit, then record it (id + arena) so the
    follow-up "you may deal 1 to another unit in the same arena" effect can
    restrict to that arena and exclude this unit."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    from swu.engine.state import Zone
    event_ctx["excluded_target_id"] = target_id
    event_ctx["same_arena"] = "ground" if unit.zone == Zone.GROUND_ARENA else "space"
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)


def _grenade_second(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the chosen "other" unit in the same arena (the "you may"
    half — ``target_id`` is None if the controller declined)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)


@card_ability("TWI", "171")
def _grenade_strike():
    """TWI_171 — Grenade Strike (Event, Tactic, cost 2): "Deal 2 damage to a unit.
    You may deal 1 damage to another unit in the same arena."

    Two sequential effects sharing the resolve_effects ``event_ctx`` (the Haymaker
    LAW_168 / Nothing Left to Fear LAW_41 pattern): a mandatory CustomEffect.target
    deals 2 to the chosen unit and records its id + arena; an optional
    CustomEffect.target deals 1 to "another unit in the same arena", restricted by
    the existing ``same_arena_as_event`` predicate plus the new
    ``excludes_event_target`` predicate ("another" — not the first unit).  The
    first is mandatory-if-able (fizzles with no unit on the board); the second is a
    "you may" (declinable, and offered only when an eligible other same-arena unit
    exists)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_grenade_first,
            target=TargetSpec(controller="any", kind="unit"),
        ),
        CustomEffect(
            fn=_grenade_second,
            target=TargetSpec(controller="any", kind="unit", optional=True,
                              predicates=("same_arena_as_event",
                                          "excludes_event_target")),
        ),
    ])


@card_ability("TWI", "174")
def _open_fire():
    """TWI_174 — Open Fire (Event, Tactic, cost 3): "Deal 4 damage to a unit." """
    return EventAbility(effects=[
        DealDamage(4, TargetSpec(controller="any", kind="unit")),
    ])


# ── UNITS — card advantage & disruption (group ahsoka-tano:03) ────────────────


@card_ability("TWI", "107")
def _patrolling_v_wing():
    """TWI_107 — Patrolling V-Wing (Unit, Fighter/Vehicle, 1/1): "When Played:
    Draw a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(count=1)],
    )


def _is_republic_unit(card_def) -> bool:
    """A "Republic unit": a Unit card carrying the Republic trait."""
    from swu.cards.models import Unit
    return (isinstance(card_def, Unit)
            and "Republic" in (getattr(card_def, "traits", None) or ()))


def _tranquility_return(state, source_ci, target_id, event_ctx):
    """Adapter: the controller may return one Republic unit from their discard pile
    to hand (push_return_from_discard, "up to 1" — the Razor Crest SHD_44 pattern)."""
    from swu.engine.actions import push_return_from_discard
    push_return_from_discard(state, source_ci, count=1, eligible=_is_republic_unit)
    return state


@card_ability("TWI", "246")
def _tranquility():
    """TWI_246 — Tranquility (Unit, Capital Ship/Republic/Vehicle, 7/6).

    "When Played: You may return a Republic unit from your discard pile to your
    hand."  A thin CustomEffect adapter onto the return_from_discard decision kind
    (push_return_from_discard, the Razor Crest SHD_44 pattern) — the controller may
    take up to one Republic unit from their discard pile back to hand, or finish
    without taking one (the "you may"); pushed only when one is present.

    "On Attack: Each of the next 3 Republic cards you play this phase costs 1
    resource less."  A deferred ``NextPlayDiscount("Republic", amount=1, count=3,
    units_only=False)`` (the Khetanna LAW_158 pending-discount seam, extended): it
    records 3 pending entries for the controller, each consumed by one subsequent
    Republic *card* play (``units_only=False`` so events/upgrades qualify too, not
    just units).  The discounts lift at the phase rollover.

    LIMITATION (inherited from Khetanna): the discount applies only on the normal
    hand-play path (``PlayCard``) and its affordability gates, not on the
    ability-driven play-from-hand subsystem (which pays the raw effective cost) — the
    common, faithful case.
    """
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_tranquility_return)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[NextPlayDiscount("Republic", amount=1, count=3,
                                      units_only=False)],
        ),
    ]


# ── TWI_243 Republic Commando (Coordinate — Saboteur) ─────────────────────────


# ── Group ahsoka-tano:04 — combat tricks, buffs & tempo ───────────────────────


def _rep_tactical_officer_attack(state, source_ci, target_id, event_ctx):
    """Adapter: may attack with a Republic unit; +2/+0 to it for this attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                        optional=True, attacker_trait="Republic")
    return state


@card_ability("TWI", "91")
def _republic_tactical_officer():
    """TWI_91 — Republic Tactical Officer (Unit, Clone/Republic, 1/4): "When
    Played: You may attack with a Republic unit. It gets +2/+0 for this attack."

    A ``WhenPlayed`` whose one CustomEffect is a thin adapter onto the granted-attack
    seam (``attacker_trait="Republic"`` restricts the attacker to a Republic unit,
    ``optional=True`` for the "you may", ``power_bonus=2`` for the +2/+0).  The
    officer itself is a Republic unit but enters play exhausted, so it is not offered
    as the attacker the turn it is played; other ready Republic units are.  With no
    eligible ready Republic unit a ``DeclineGrantedAttack`` is the only option."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_rep_tactical_officer_attack)],
    )


@card_ability("TWI", "92")
def _admiral_yularen():
    """TWI_92 — Admiral Yularen (Unit, Official/Republic, 2/5, Restore 1): "Restore
    1.  Each other friendly Heroism unit gets +0/+1."

    Restore 1 is the keyword layer.  The buff is a ``ConstantAbility`` over every
    OTHER friendly Heroism unit (``aspects=("Heroism",)``, ``not_self``) granting
    ``StatBonus(0, 1)`` — read passively by ``compute_hp`` (the Red Three SOR_144
    pattern), so it winks on/off as Heroism units enter/leave."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          aspects=("Heroism",), predicates=("not_self",)),
        effects=[StatBonus(power=0, hp=1)],
    )


@card_ability("TWI", "109")
def _501st_liberator():
    """TWI_109 — 501st Liberator (Unit, Clone/Republic/Trooper, 3/3): "When Played:
    If you control another Republic unit, you may heal 3 damage from a base."

    An optional ``WhenPlayed`` ``Heal(3, …)`` on the controller's base
    (``kind="base"``, ``fixed=EACH_FRIENDLY`` → resolves inline on your own base),
    gated by ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Republic")`` so the whole trigger is
    collected only when you control another Republic unit (excludes the Liberator
    itself, which is Republic).  The "you may" is ``optional=True`` (the Cargo
    Juggernaut SHD_66 heal-own-base pattern, but optional)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[Heal(3, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Republic"),
    )


def _outflank_twi(state, source_ci, target_id, event_ctx):
    """Adapter: grant two attacks (one at a time)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci)
    push_granted_attack(state, source_ci)
    return state


@card_ability("TWI", "123")
def _outflank():
    """TWI_123 — Outflank (Event, Tactic, cost 1): "Attack with 2 units (one at a
    time)."  Identical to Outflank SHD_128 — a thin CustomEffect calling
    ``push_granted_attack`` twice (the Rebel Assault SOR_103 pattern): the two
    granted attacks sit on the LIFO decision stack and resolve one at a time, and
    "2 different units" falls out of exhaustion (the first attacker is exhausted by
    its attack).  Each is mandatory-if-able; spare grants fizzle via
    ``DeclineGrantedAttack``."""
    return EventAbility(effects=[CustomEffect(fn=_outflank_twi)])


@card_ability("TWI", "126")
def _encouraging_leadership():
    """TWI_126 — Encouraging Leadership (Event, Learned, cost 3): "Give each
    friendly unit +1/+1 for this phase."

    A plain ``EventAbility`` with one ``ModifyStats(+1/+1, this phase)`` auto-
    targeting every friendly unit (``fixed=EACH_FRIENDLY``)."""
    return EventAbility(effects=[
        ModifyStats(power=1, hp=1,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      fixed=EACH_FRIENDLY),
                    duration=Duration.THIS_PHASE),
    ])


@card_ability("TWI", "142")
def _anakins_interceptor():
    """TWI_142 — Anakin's Interceptor (Unit, Fighter/Jedi/Republic/Vehicle, 2/3):
    "While your base has 15 or more damage on it, this unit gets +2/+0."

    A self-targeted ``ConstantAbility(StatBonus(2, 0))`` gated by the new
    ``CONTROLLER_BASE_DAMAGE_MIN`` condition (param=15), read passively by
    ``compute_power`` so the buff winks on/off with the base's damage total."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_BASE_DAMAGE_MIN, 15),
    )


def _padawan_lightsaber_attack(state, source_ci, target_id, event_ctx):
    """Adapter: may attack with a unit (any of the controller's ready units)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True)
    return state


@card_ability("TWI", "248")
def _ahsokas_padawan_lightsaber():
    """TWI_248 — Ahsoka's Padawan Lightsaber (Upgrade, Item/Lightsaber/Weapon, cost
    1): "Attach to a non-Vehicle unit.  When Played: If attached unit is Ahsoka
    Tano, you may attack with a unit."

    A ``WhenPlayed`` gated by ``ATTACHED_HOST_NAMED("Ahsoka Tano")`` (so the whole
    trigger is collected only when the host is Ahsoka, evaluated against the upgrade
    at collection time — the Mandalorian's Rifle SHD_251 / Leia's Disguise LAW_111
    pattern), whose one CustomEffect is a thin adapter onto the granted-attack seam
    (``optional=True`` for the "you may"; any of the controller's ready units may
    attack — not pinned to the host).  The non-Vehicle attach restriction is the
    engine's upgrade-target parser."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_padawan_lightsaber_attack)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Ahsoka Tano"),
    )


# ── Group ahsoka-tano:05 — create-token-unit primitive ────────────────────────
# All four cards create "Clone Trooper" token units (TWI_2, a 0-cost 2/2 ground
# Token Unit) via the new ``CreateTokenUnit`` effect — a non-targeted effect (like
# DrawCards) routed through ``actions._create_token_units`` → ``_put_unit_in_play``,
# so each token enters the controller's ground arena exhausted and is buffable like
# any unit.  Token units are excluded from card conservation and cease to exist
# when they leave play (see the engine-primitive note in CLAUDE.md).

@card_ability("TWI", "94")
def _shaak_ti():
    """TWI_94 — Shaak Ti (Unit, Force/Jedi/Republic, 3/4): "Each friendly token unit
    gets +1/+0.  On Attack: Create a Clone Trooper token."

    Two abilities: a ``ConstantAbility`` over every friendly **token unit** (the new
    ``token_unit`` predicate) granting ``StatBonus(1, 0)`` — read passively by
    ``compute_power`` (the Red Three SOR_144 pattern), so a created Clone Trooper is
    a 3/2 while Shaak Ti is in play; and an ``OnAttack`` ``CreateTokenUnit`` that
    creates one Clone Trooper token (non-targeted, resolves inline)."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("token_unit",)),
            effects=[StatBonus(power=1, hp=0)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CreateTokenUnit("Clone Trooper", count=1)],
        ),
    ]


@card_ability("TWI", "97")
def _captain_rex():
    """TWI_97 — Captain Rex (Unit, Clone/Republic/Trooper, 4/4): "When Played:
    Create 2 Clone Trooper tokens."  A plain ``WhenPlayed`` ``CreateTokenUnit``
    (count=2), non-targeted → resolves inline."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Clone Trooper", count=2)],
    )


@card_ability("TWI", "144")
def _batch_brothers():
    """TWI_144 — Batch Brothers (Unit, Clone/Republic/Trooper, 2/1): "When Played:
    Create a Clone Trooper token."  A plain ``WhenPlayed`` ``CreateTokenUnit``
    (count=1)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Clone Trooper", count=1)],
    )


@card_ability("TWI", "251")
def _drop_in():
    """TWI_251 — Drop In (Event, Supply, cost 4): "Create 2 Clone Trooper tokens."
    A plain ``EventAbility`` with one ``CreateTokenUnit`` (count=2)."""
    return EventAbility(effects=[CreateTokenUnit("Clone Trooper", count=2)])


@card_ability("TWI", "243")
def _republic_commando():
    """TWI_243 — Republic Commando: "Coordinate — Saboteur."

    A conditional self-grant of the Saboteur keyword (sanitiser strips the printed
    always-on copy).  Saboteur is read by ``has_keyword`` at the on-attack step
    (CR step 2: ignore Sentinel, defeat the defender's Shields) — active only while
    the controller has 3+ units.
    """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Saboteur", value=0)],
        condition=_COORDINATE,
    )


# ── New primitive: scaling-magnitude (ahsoka-tano:06) ─────────────────────────
# Synchronized Strike deals an enemy unit a magnitude that depends on the BOARD —
# the number of units the controller has in that unit's arena — which a fixed
# DealDamage cannot express.  It reuses the existing DealDamageEqualTo effect
# (from shd-han-solo:08 / the-mandalorian:02) with one new ``count`` scaling
# source ("source_controller_units_in_target_arena"); a new magnitude arm in
# resolver._scaling_magnitude reads the source controller's matching arena list.
# No new decision kind, no trigger/decision-machinery change (the allowed
# small-primitive path).

# ── Group general-grievous:01 — direct damage & removal ───────────────────────
# Merciless Contest (TWI_238) is a new self-contained decision kind: "each player
# chooses one of their own non-leader units, then defeat them all".  The opponent
# must choose *their own* unit, which the resolve_effects flow cannot express
# (a ChooseTarget is always decided by the source's controller), so it needs a
# per-stage deciding-player shift — the established say_no SOR_233 /
# opponent_chooses_target SHD_246 precedent (push_each_player_defeats).

def _merciless_contest_fn(state, source_ci, target_id, event_ctx):
    """Adapter: push the each-player-defeats decision (the source's controller
    chooses first, then the opponent)."""
    from swu.engine.actions import push_each_player_defeats
    push_each_player_defeats(state, source_ci)
    return state


@card_ability("TWI", "238")
def _merciless_contest():
    """TWI_238 — Merciless Contest (Event, Tactic, cost 3): "Each player chooses a
    non-leader unit they control. Defeat those units."

    A plain ``EventAbility`` whose one non-targeted ``CustomEffect`` is a thin
    adapter onto the new ``each_player_defeats`` decision kind: each player picks
    one of their own non-leader units (the controller first, then the opponent —
    a per-stage deciding-player shift, since the opponent must choose *their own*
    unit, which a normal controller-decided ChooseTarget cannot express), then the
    chosen units are defeated together.  A player with no eligible unit is skipped;
    with neither having one the event fizzles."""
    return EventAbility(effects=[CustomEffect(fn=_merciless_contest_fn)])


@card_ability("TWI", "99")
def _synchronized_strike():
    """TWI_99 — Synchronized Strike (Event, Tactic, cost 2): "Deal damage to an
    enemy unit equal to the number of units you control in its arena."

    A plain ``EventAbility`` with one ``DealDamageEqualTo`` whose (non-fixed)
    target is an enemy unit — the controller picks which one, and the per-target
    scaling magnitude is the new ``source_controller_units_in_target_arena`` count
    (the number of the controller's own units sharing the chosen unit's arena).
    Mandatory-if-able: fizzles cleanly with no enemy unit; a magnitude of 0 (you
    control no units in that arena) is a no-op."""
    return EventAbility(effects=[
        DealDamageEqualTo(
            target=TargetSpec(controller="enemy", kind="unit"),
            count="source_controller_units_in_target_arena",
        ),
    ])


# ── Group general-grievous:02 — card advantage & disruption ───────────────────


def _admiral_trench_return(state, source_ci, target_id, event_ctx):
    """Adapter: return up to 3 units **defeated this phase** from the controller's
    discard pile to their hand.

    ``eligible`` (a card_def predicate) keeps only Unit cards; ``eligible_instance``
    keeps only the instances whose ids are in ``game_memory.units_defeated_this_round``
    — the phase's defeated-unit set.  (Defeats happen in ACTION and the set clears
    at the round rollover, so "this round" and "this phase" coincide — the Medal
    Ceremony SOR_245 ``attacked_this_phase`` precedent.)  ``push_return_from_discard``
    pushes the "up to 3" decision only when ≥1 such unit is present, else fizzles."""
    from swu.engine.actions import push_return_from_discard
    from swu.cards.models import Unit

    defeated = set(state.game_memory.units_defeated_this_round)

    def _is_unit(card_def) -> bool:
        return isinstance(card_def, Unit)

    def _was_defeated_this_phase(ci) -> bool:
        return ci.instance_id in defeated

    push_return_from_discard(
        state, source_ci, count=3, up_to=True,
        eligible=_is_unit, eligible_instance=_was_defeated_this_phase,
    )
    return state


@card_ability("TWI", "86")
def _admiral_trench():
    """TWI_86 — Admiral Trench (Unit, Official/Separatist, 5/5, Exploit 1).

    Exploit 1 is the keyword layer.  "When Played: Return up to 3 units that were
    defeated this phase from your discard pile to your hand."  A ``WhenPlayed``
    whose one CustomEffect is a thin adapter onto the ``return_from_discard``
    decision kind (the Razor Crest SHD_44 / Tranquility TWI_246 pattern), extended
    with an instance-level ``eligible_instance`` filter that restricts the
    candidates to units in ``units_defeated_this_round`` ("defeated this phase").
    The controller may take up to 3 (or fewer — the "up to"); pushed only when at
    least one such unit is in the discard pile."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_admiral_trench_return)],
    )


@card_ability("TWI", "226")
def _waylay():
    """TWI_226 — Waylay (Event, Trick, cost 3): "Return a non-leader unit to its
    owner's hand."  A plain ``EventAbility`` with one mandatory ``ReturnToHand``
    targeting any non-leader unit (``controller="any"`` — friendly or enemy);
    fizzles cleanly with no eligible unit."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="any", kind="unit",
                                predicates=("non_leader",))),
    ])


def _private_manufacturing_bottom(state, source_ci, target_id, event_ctx):
    """Adapter (runs after the DrawCards(2)): "If you control no token units, put 2
    cards from your hand on the bottom of your deck in any order."

    Checks the controller's arenas for any ``TokenUnit`` instance; if there are
    none, pushes the ``bottom_from_hand`` decision (mandatory, ``min(2, hand)`` cards,
    chosen one at a time so "in any order" falls out).  With a token unit in play the
    downside is skipped entirely."""
    from swu.cards.models import TokenUnit
    from swu.engine.actions import push_bottom_from_hand
    ps = state.player_by_id(source_ci.owner_id)
    controls_token_unit = any(
        isinstance(u.card_def, TokenUnit)
        for u in ps.ground_arena + ps.space_arena
    )
    if not controls_token_unit:
        push_bottom_from_hand(state, source_ci, count=2)
    return state


@card_ability("TWI", "257")
def _private_manufacturing():
    """TWI_257 — Private Manufacturing (Event, Supply, cost 2): "Draw 2 cards. If
    you control no token units, put 2 cards from your hand on the bottom of your
    deck in any order."

    A ``DrawCards(2)`` followed by a CustomEffect that resolves the conditional
    downside inline: if the controller controls no token units, it pushes the new
    self-contained ``bottom_from_hand`` decision kind (put 2 chosen hand cards on the
    bottom of the deck, one at a time — the pick order is the bottom order).  The
    bottoming lands as a nested decision beneath the event's buried resolve_effects
    decision (the Calculated Lethality SHD_39 nested-decision pattern), which
    ``apply_resolve_effects`` already resumes.  The token-unit synergy (skip the
    downside when you have a Clone Trooper etc. in play) is the deck's reward for
    the create-token-unit cards (group :05)."""
    return EventAbility(effects=[
        DrawCards(count=2),
        CustomEffect(fn=_private_manufacturing_bottom),
    ])


# ── Group general-grievous:03 — combat tricks, buffs & tempo ──────────────────


def _grievous_on_attack(state, source_ci, target_id, event_ctx):
    """Deployed General Grievous On Attack: give the chosen friendly Droid unit
    +1/+0 AND Sentinel, both for this phase, bound to the SAME unit (the text grants
    both to one Droid unit, so a single CustomEffect.target rather than two separate
    effects that could split the choice)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _make_modifier, _make_kw_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=1, hp=0, duration=Duration.THIS_PHASE))
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id,
        keyword="Sentinel", value=0, duration=Duration.THIS_PHASE,
        kind="keyword_grant"))
    return state


@card_ability("TWI", "15")
def _general_grievous():
    """TWI_15 — General Grievous (Leader, Official/Separatist, 4/8, Sentinel).

    Undeployed front: "Action [Exhaust]: Give a Droid unit Sentinel for this
    phase."  An ``undeployed_only`` ActivatedAbility (exhaust the undeployed leader)
    whose one ``GrantKeyword("Sentinel", THIS_PHASE)`` targets a friendly Droid unit
    (you grant Sentinel to your own droid — forcing enemies onto it; never an
    enemy's).

    Deployed back (Sentinel keyword, the keyword layer): "On Attack: You may give a
    Droid unit +1/+0 and Sentinel for this phase."  A ``deployed_only`` optional
    OnAttack trigger whose one CustomEffect applies both the +1/+0 and Sentinel to
    one chosen friendly Droid unit (bound together — the same unit gets both).

    The Epic Action deploy ("If you control 6 or more resources, deploy this
    leader") is the standard ``deploy_threshold`` machinery — no registration."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[GrantKeyword(
                "Sentinel", value=0,
                target=TargetSpec(controller="friendly", kind="unit",
                                  traits=("Droid",)),
                duration=Duration.THIS_PHASE)],
            title="Give a Droid unit Sentinel",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            deployed_only=True,
            effects=[CustomEffect(
                fn=_grievous_on_attack,
                target=TargetSpec(controller="friendly", kind="unit",
                                  traits=("Droid",)),
            )],
        ),
    ]


def _magnaguard_two_attacks(state, source_ci, target_id, event_ctx):
    """Adapter: grant two attacks, each restricted to a Droid unit (one at a time);
    "another" Droid unit falls out of the first attacker's exhaustion."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_trait="Droid")
    push_granted_attack(state, source_ci, attacker_trait="Droid")
    return state


@card_ability("TWI", "82")
def _magnaguard_wing_leader():
    """TWI_82 — MagnaGuard Wing Leader (Unit, Fighter/Separatist/Vehicle, 3/4):
    "Action: Attack with a Droid unit. Then, attack with another Droid unit. Use
    this ability only once each round."

    A no-cost ``ActivatedAbility`` (``once_per_round=True``, the new engine seam)
    whose one CustomEffect calls ``push_granted_attack(attacker_trait="Droid")``
    twice (the Outflank TWI_123 / Rebel Assault SOR_103 double-grant pattern): the
    two granted attacks sit on the LIFO decision stack and resolve one at a time,
    restricted to Droid attackers, and "another Droid unit" falls out of the first
    attacker's exhaustion.  Each is mandatory-if-able; a spare grant with no
    eligible Droid attacker fizzles via ``DeclineGrantedAttack``."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_magnaguard_two_attacks)],
        title="Attack with two Droid units",
        once_per_round=True,
    )


@card_ability("TWI", "104")
def _obedient_vanguard():
    """TWI_104 — Obedient Vanguard (Unit, Droid/Separatist/Trooper, 1/1, Raid 1):
    "When Defeated: You may give a Trooper unit +2/+2 for this phase."

    Raid 1 is the keyword layer.  An optional ``WhenDefeated`` ``ModifyStats(+2/+2,
    this phase)`` on a friendly Trooper unit (the Vanguard itself has left play, so
    it is never its own recipient); with no friendly Trooper unit the optional
    trigger auto-declines."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[ModifyStats(
            power=2, hp=2,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Trooper",)),
            duration=Duration.THIS_PHASE)],
    )


@card_ability("TWI", "124")
def _tactical_advantage():
    """TWI_124 — Tactical Advantage (Event, Tactic, cost 1): "Give a unit +2/+2 for
    this phase."  A plain ``EventAbility`` with one ``ModifyStats(+2/+2, this phase)``
    on any unit (``controller="any"`` mirrors "a unit"; the Moment of Glory SHD_130
    pattern)."""
    return EventAbility(effects=[
        ModifyStats(power=2, hp=2,
                    target=TargetSpec(controller="any", kind="unit"),
                    duration=Duration.THIS_PHASE),
    ])


def _soulless_one_on_attack(state, source_ci, target_id, event_ctx):
    """If a friendly Droid unit (or General Grievous) was chosen, exhaust it and
    give Soulless One +2/+0 for this attack.  Cost (exhaust) and buff are bound so
    "If you do" holds (the Kihraxz SHD_118 pattern)."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    if unit.exhausted:
        return state  # cannot pay the exhaust → no buff
    unit.exhausted = True
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, source_ci.instance_id,
        power=2, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("TWI", "179")
def _soulless_one():
    """TWI_179 — Soulless One (Unit, Fighter/Separatist/Vehicle, 1/2): "On Attack:
    You may exhaust a friendly Droid unit or General Grievous (leader or unit). If
    you do, this unit gets +2/+0 for this attack."

    An optional ``OnAttack`` trigger (the "you may") whose one CustomEffect carries a
    target of a friendly unit restricted by the new ``droid_or_general_grievous``
    predicate (a Droid trait OR named General Grievous — his deployed form, who is
    not a Droid).  Choosing one exhausts it and applies a +2/+0 this-attack modifier
    to Soulless One; cost and buff are bound in one CustomEffect so "If you do"
    holds (the Kihraxz SHD_118 pattern).  With no eligible unit the optional trigger
    auto-declines.  LIMITATION: the undeployed leader form is in base_zone and is
    not an arena unit, so it is not offered as the exhaust target (the unexercised
    "(leader or unit)" edge)."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_soulless_one_on_attack,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("droid_or_general_grievous", "ready")),
        )],
    )


@card_ability("TWI", "180")
def _separatist_commando():
    """TWI_180 — Separatist Commando (Unit, Droid/Separatist/Trooper, 2/3): "While
    you control another Separatist unit, this unit gains Raid 2."

    A self-targeted ``ConstantAbility`` granting Raid 2, gated by
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Separatist")`` ("another Separatist unit"
    excludes the source), read passively by ``keyword_value`` so the +2 attacking
    bonus winks on/off with the board (the Hunting Nexu SHD_168 conditional
    self-grant pattern).  The card's printed Raid keyword (the upstream data tags
    it) is stripped by the keyword sanitiser because this conditional self-grant is
    registered, so the ability — not an always-on bar — owns Raid."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", value=2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Separatist"),
    )


@card_ability("TWI", "184")
def _tactical_droid_commander():
    """TWI_184 — Tactical Droid Commander (Unit, Droid/Separatist, 4/4, Exploit 2):
    "When you play another Separatist unit: You may exhaust a unit that costs the
    same as or less than the played unit."

    Exploit 2 is the keyword layer.  An optional ``WhenYouPlayCard`` trigger
    (``trait="Separatist"``, ``card_type="unit"``, ``exclude_self`` for "another"):
    the matcher fires off the ``CardPlayed`` event for a Separatist unit play and
    records the played unit's printed cost in ``event_ctx["cost_le_threshold"]``;
    the one ``ExhaustCard`` effect then targets any unit (``controller="any"`` —
    you exhaust an enemy) filtered by the new ``cost_le_event_threshold`` predicate
    (cost ≤ the played unit).  The "you may" is ``optional=True``; with no eligible
    unit the trigger auto-declines."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Separatist", card_type="unit"),
        optional=True,
        effects=[ExhaustCard(
            TargetSpec(controller="any", kind="unit",
                       predicates=("cost_le_event_threshold",)))],
    )


# ── Group general-grievous:04 — combat tricks, buffs & tempo ──────────────────


@card_ability("TWI", "206")
def _independent_senator():
    """TWI_206 — Independent Senator (Unit, Official/Separatist, 0/4): "Action [2
    resources, Exhaust]: Exhaust a unit with 4 or less power."

    An ``ActivatedAbility`` whose cost is the printed [2 resources, Exhaust]
    (``PayResources(2)`` + ``ExhaustSelf()``) and whose one ``ExhaustCard`` targets
    any unit with effective power ≤ 4 (the new ``power_max`` TargetSpec filter — the
    inverse of ``power_min``).  ``controller="any"`` mirrors "a unit"; you point it
    at an enemy.  With no eligible unit the mandatory targeted effect fizzles
    silently (the resolver skips an effect with no legal target)."""
    return ActivatedAbility(
        costs=[PayResources(2), ExhaustSelf()],
        effects=[ExhaustCard(
            TargetSpec(controller="any", kind="unit", power_max=4))],
        title="Exhaust a unit with 4 or less power",
    )


@card_ability("TWI", "217")
def _tri_droid_suppressor():
    """TWI_217 — Tri-Droid Suppressor (Unit, Droid/Separatist/Vehicle/Walker, 4/7,
    Exploit 2): "When Played: Exhaust an enemy ground unit."

    Exploit 2 is the keyword layer.  A plain ``WhenPlayed`` with one ``ExhaustCard``
    targeting an enemy ground unit (mandatory-if-able; fizzles with no enemy ground
    unit on the board)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(
            TargetSpec(controller="enemy", kind="unit", arena="ground"))],
    )


def _in_pursuit_first(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen friendly unit and record that a target was chosen, so the
    follow-up enemy-exhaust effect ("If you do") fires only when a friendly was
    actually exhausted (the ``requires_prior_target`` predicate gate)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    unit.exhausted = True
    event_ctx["prior_target_id"] = target_id
    return state


@card_ability("TWI", "221")
def _in_pursuit():
    """TWI_221 — In Pursuit (Event, Tactic, cost 0): "Exhaust a friendly unit. If
    you do, exhaust an enemy unit."

    Two sequential effects sharing the resolve_effects ``event_ctx`` (the Grenade
    Strike TWI_171 / Haymaker LAW_168 pattern): a mandatory ``CustomEffect.target``
    exhausts the chosen friendly unit and records that a target was chosen; a
    mandatory ``ExhaustCard`` on an enemy unit gated by the new
    ``requires_prior_target`` predicate ("If you do" — it has no candidates, so no
    prompt, unless the first effect actually exhausted a friendly).  With no
    friendly unit the first effect fizzles, the flag is never set, and the enemy
    exhaust is skipped; with a friendly but no enemy unit the enemy exhaust fizzles
    cleanly."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_in_pursuit_first,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        ExhaustCard(
            TargetSpec(controller="enemy", kind="unit",
                       predicates=("requires_prior_target",))),
    ])


@card_ability("TWI", "236")
def _grievouss_wheel_bike():
    """TWI_236 — Grievous's Wheel Bike (Upgrade, Vehicle, cost 4): "While playing
    this upgrade on General Grievous, it costs 2 resources less to play.  Attach to
    a non-Vehicle unit.  Attached unit gains Overwhelm."

    Two specs: a ``ConstantAbility(target=SELF, KeywordGrant("Overwhelm"))`` (read
    passively by ``has_keyword``, so the host gains Overwhelm while equipped); and a
    host-conditional ``CostReduction(amount=2, host_named="General Grievous")`` — the
    new ``host_named`` field on ``CostReduction``, read by the play-cost path (which
    now knows the chosen host), so the upgrade is 2 cheaper precisely when attached
    to General Grievous (his deployed leader-unit form, named "General Grievous").
    The non-Vehicle attach restriction is the engine's upgrade-target parser."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Overwhelm", value=0)],
        ),
        CostReduction(amount=2, host_named="General Grievous"),
    ]


# ── Group general-grievous:05 — create-token-unit (Battle Droid) ───────────────
# Seven Separatist cards "Create N Battle Droid tokens" — a Battle Droid is the
# Token Unit def TWI_1 (a 1/1 ground unit, traits Separatist/Droid/Trooper,
# Villainy).  They reuse the existing ``CreateTokenUnit`` effect (ahsoka-tano:05);
# the only engine addition this group needed is the ``enters_ready`` field on
# CreateTokenUnit ("Create 3 … and ready them", On the Doorstep TWI_190).  A token
# unit goes to the source's controller, enters the ground arena, is buffable like
# any unit, is excluded from card conservation, and ceases to exist when defeated.

@card_ability("TWI", "79")
def _confederate_courier():
    """TWI_79 — Confederate Courier (Unit, Fighter/Separatist/Vehicle, 2/1):
    "When Defeated: Create a Battle Droid token."  A plain ``WhenDefeated``
    ``CreateTokenUnit`` (non-targeted, resolves inline).  The token goes to the
    dying unit's controller (the source resolves from its owner on defeat)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
    )


@card_ability("TWI", "80")
def _poggle_the_lesser():
    """TWI_80 — Poggle the Lesser (Unit, Official/Separatist, 1/4): "When you play
    another unit: You may exhaust this unit.  If you do, create a Battle Droid
    token."

    An optional ``WhenYouPlayCard(card_type="unit")`` trigger (``exclude_self``
    drops Poggle's own play → "another unit"), gated by ``SOURCE_READY`` so it is
    offered only while Poggle is ready (the "exhaust this unit" cost is payable).
    On Accept it resolves two non-targeted effects in order: ``ExhaustCard(SELF)``
    (the "exhaust this unit" cost) then ``CreateTokenUnit`` (the effect).  Because
    the SOURCE_READY gate guarantees the exhaust always succeeds when offered, the
    "If you do" binding holds — declining (the optional "may") makes neither
    happen.  No CustomEffect needed: both effects have fixed/no targets, so they
    auto-resolve inline."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit"),
        effects=[
            ExhaustCard(TargetSpec(fixed=SELF)),
            CreateTokenUnit("Battle Droid", count=1),
        ],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_READY),
    )


@card_ability("TWI", "83")
def _generals_guardian():
    """TWI_83 — General's Guardian (Unit, Droid/Separatist, 4/4): "When this unit
    is attacked: Create a Battle Droid token."  A plain ``WhenAttacked``
    ``CreateTokenUnit`` (non-targeted, resolves inline)."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
    )


@card_ability("TWI", "84")
def _kraken():
    """TWI_84 — Kraken (Unit, Droid/Separatist, 2/5): "When Played: Create 2 Battle
    Droid tokens.  On Attack: Give each friendly token unit +1/+1 for this phase."

    Two abilities: a ``WhenPlayed`` ``CreateTokenUnit(count=2)``; and an
    ``OnAttack`` ``ModifyStats(+1/+1, this phase)`` auto-targeting every friendly
    **token unit** (the ``token_unit`` predicate from ahsoka-tano:05,
    ``fixed=EACH_FRIENDLY`` → resolves inline).  Kraken is a real unit, not a
    token, so it never buffs itself."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Battle Droid", count=2)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(
                power=1, hp=1,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("token_unit",), fixed=EACH_FRIENDLY),
                duration=Duration.THIS_PHASE,
            )],
        ),
    ]


@card_ability("TWI", "112")
def _subjugating_starfighter():
    """TWI_112 — Subjugating Starfighter (Unit, Fighter/Separatist/Vehicle, 3/3,
    Ambush): "When Played: If you have the initiative, create a Battle Droid
    token."  Ambush is the keyword layer.  A ``WhenPlayed`` ``CreateTokenUnit``
    gated by ``CONTROLLER_HAS_INITIATIVE`` (the condition gates trigger collection,
    so nothing is created without initiative)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


@card_ability("TWI", "190")
def _on_the_doorstep():
    """TWI_190 — On the Doorstep (Event, Supply, cost 4): "Create 3 Battle Droid
    tokens and ready them."  A plain ``EventAbility`` with one
    ``CreateTokenUnit(count=3, enters_ready=True)`` — the new ``enters_ready`` field
    puts the created tokens into play ready instead of the default exhausted."""
    return EventAbility(effects=[
        CreateTokenUnit("Battle Droid", count=3, enters_ready=True)])


@card_ability("TWI", "218")
def _droid_cohort():
    """TWI_218 — Droid Cohort (Upgrade, Supply, cost 1): "Attached unit gains, 'When
    Defeated: Create a Battle Droid token.'"  A ``GrantedAbility`` wrapping a
    ``WhenDefeated`` ``CreateTokenUnit`` (the Armed to the Teeth SHD_175 /
    the-mandalorian:01 granted-WhenDefeated-from-a-defeated-host pattern): the
    ability resolves from the HOST, so the token goes to the host's controller when
    the host is defeated.  Unlike a Bounty, this is an ordinary (own-perspective)
    granted ability, not collected by an opponent."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
    ))


# ── Group general-grievous:06 — create-token-unit (Battle Droid), part 2 ───────
# Four more Separatist "Create N Battle Droid tokens" cards.  Two are trivial
# reuses of the existing ``CreateTokenUnit`` effect (TWI_229, TWI_237); two need a
# small self-contained decision kind each (the allowed small-primitive path):
#   * Political Pressure TWI_222 → ``may_discard`` (opponent may discard a random
#     card to prevent the controller's token creation — the say_no SOR_233
#     deciding-player-shift precedent).
#   * The Invisible Hand TWI_234 On Attack → ``exhaust_for_base_damage`` (exhaust
#     any number of friendly Separatist units, deal 1 to the defending base per —
#     the Medal Ceremony SOR_245 "select any number" multi-select shape).

def _political_pressure_fn(state, source_ci, target_id, event_ctx):
    """Adapter: the (single) opponent may discard a random card from their hand; if
    they don't, the controller creates 2 Battle Droid tokens."""
    from swu.engine.actions import push_may_discard_else_tokens
    push_may_discard_else_tokens(state, source_ci,
                                 token_name="Battle Droid", token_count=2)
    return state


@card_ability("TWI", "222")
def _political_pressure():
    """TWI_222 — Political Pressure (Event, Plan, cost 1): "Choose an opponent.
    They may discard a random card from their hand. If they don't, create 2 Battle
    Droid tokens."

    A plain ``EventAbility`` whose one non-targeted ``CustomEffect`` is a thin
    adapter onto the new ``may_discard`` decision kind: the opponent (the only
    opponent in 2-player) decides whether to discard a *random* card (RNG-chosen)
    to prevent the tokens, or to decline — in which case the controller creates 2
    Battle Droid tokens (the create-token-unit primitive, ahsoka-tano:05 /
    general-grievous:05).  When the opponent's hand is empty they cannot discard,
    so the tokens are created inline (no decision)."""
    return EventAbility(effects=[CustomEffect(fn=_political_pressure_fn)])


@card_ability("TWI", "229")
def _battle_droid_escort():
    """TWI_229 — Battle Droid Escort (Unit, Droid/Separatist/Trooper, 1/1): "When
    Played/When Defeated: Create a Battle Droid token."

    The combined "When Played/When Defeated" trigger is registered as two separate
    ``TriggerAbility``s — a ``WhenPlayed`` and a ``WhenDefeated`` — each creating
    one Battle Droid token (non-targeted, resolves inline)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Battle Droid", count=1)],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CreateTokenUnit("Battle Droid", count=1)],
        ),
    ]


def _invisible_hand_on_attack(state, source_ci, target_id, event_ctx):
    """Adapter: exhaust any number of friendly Separatist units, then deal 1 damage
    to the defending player's base for each unit exhausted this way."""
    from swu.engine.actions import push_exhaust_for_base_damage
    push_exhaust_for_base_damage(state, source_ci,
                                 traits=["Separatist"], damage_per=1)
    return state


@card_ability("TWI", "234")
def _the_invisible_hand():
    """TWI_234 — The Invisible Hand (Unit, Capital Ship/Separatist/Vehicle, 4/7):
    "When Played: Create 4 Battle Droid tokens.  On Attack: Exhaust any number of
    friendly Separatist units. Deal 1 damage to the defending player's base for
    each unit exhausted this way."

    Two abilities: a ``WhenPlayed`` ``CreateTokenUnit(count=4)`` (non-targeted,
    inline); and an ``OnAttack`` whose one ``CustomEffect`` is a thin adapter onto
    the new ``exhaust_for_base_damage`` decision kind — the controller exhausts any
    number (including zero) of their ready Separatist units one at a time, and on
    finishing deals 1 damage to the defending (enemy) base per unit exhausted.  The
    Invisible Hand is itself a Separatist unit but is exhausted from attacking, so
    the ``ready`` filter never offers it; pushed only when ≥1 eligible ready unit
    exists."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Battle Droid", count=4)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_invisible_hand_on_attack)],
        ),
    ]


@card_ability("TWI", "237")
def _droid_deployment():
    """TWI_237 — Droid Deployment (Event, Supply, cost 2): "Create 2 Battle Droid
    tokens."  A plain ``EventAbility`` with one ``CreateTokenUnit(count=2)``."""
    return EventAbility(effects=[CreateTokenUnit("Battle Droid", count=2)])


# ── qui-gon-jinn:02 — Card advantage & disruption (TWI card in an LOF deck) ────

@card_ability("TWI", "193")
def _r2d2_twi():
    """TWI_193 — R2-D2 (Unit, 2/4): "When Played: You may discard a card from your
    hand.  If you do, search the top 3 cards of your deck for a card and draw it.
    (Put the other cards on the bottom of your deck in a random order.)"

    A mandatory ``WhenPlayed`` whose one ``CustomEffect`` is a thin adapter onto
    the generalised ``discard_for_search`` seam (``actions.push_discard_for_search``,
    the Great Pit of Carkoon LAW_23 pattern extended to any-card discard + any-card
    search + an optional "you may" decline): ``optional=True`` carries the "you may
    discard" (a FinishDiscardForSearch decline), ``discard_units_only=False`` (any
    card), ``search_name=None`` (any card), ``search_window=3``, ``search_count=1``,
    ``search_up_to=False`` (search FOR a card — the take is mandatory once a card is
    revealed).  With an empty hand the push no-ops, so the mandatory trigger fizzles
    cleanly (no hand-size condition needed).  The decline lives in the decision, so
    the trigger itself is not optional (no double-decline prompt).
    """
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_discard_for_search
        push_discard_for_search(
            state, source_ci,
            search_window=3, search_count=1, search_up_to=False,
            search_name=None, discard_units_only=False, optional=True,
        )
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


# ── darth-maul:01 — Direct damage & removal (TWI card in an LOF deck) ──────────

@card_ability("TWI", "138")
def _count_dooku():
    """TWI_138 — Count Dooku (6/6, Exploit 2, Overwhelm): "When Played: For each
    unit you exploited while playing this card, you may deal damage to an enemy
    unit equal to the power of the exploited unit."

    Exploit 2 and Overwhelm are the keyword layer.  Each exploited (sacrificed)
    unit's effective power is snapshotted at sacrifice time and threaded through
    the play event_ctx as ``exploited_powers``; the mandatory ``WhenPlayed``
    CustomEffect is a thin adapter onto the new ``per_exploit_damage`` decision
    kind (``push_per_exploit_damage``, the Palpatine SOR_135 push-helper pattern):
    for each exploited power the controller may deal that much to one enemy unit,
    or skip it (the "you may").  With nothing exploited (or no enemy unit) the
    push is a clean no-op."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_per_exploit_damage
        powers = (event_ctx or {}).get("exploited_powers", []) or []
        push_per_exploit_damage(state, source_ci, powers)
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


# ── boba-fett:02 — Direct damage & removal ────────────────────────────────────

@card_ability("TWI", "181")
def _elite_p38_starfighter():
    """TWI_181 — Elite P-38 Starfighter (Unit, Separatist/Vehicle/Fighter, 3/2):
    "When Played/When Defeated: You may deal 1 damage to a unit."

    Two optional triggers (a ``WhenPlayed`` and a ``WhenDefeated``), each a plain
    ``DealDamage(1, any unit)``; ``controller="any"`` mirrors the printed text and
    the controller points it at an enemy.  Each auto-declines with no unit on the
    board."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            optional=True,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            optional=True,
        ),
    ]


# ── han-solo:03 — Card advantage & disruption ─────────────────────────────────

@card_ability("TWI", "191")
def _wolf_pack_escort():
    """TWI_191 — Wolf Pack Escort (Unit, Fighter/Republic/Vehicle, 2/1): "When
    Played: You may return a friendly non-leader, non-Vehicle unit to its owner's
    hand."

    An optional ``WhenPlayed`` ``ReturnToHand`` targeting a friendly non-leader,
    non-Vehicle unit (the ``non_leader``/``non_vehicle`` predicates).  Wolf Pack
    Escort is itself a Vehicle, so it can never bounce itself; with no eligible
    unit the optional trigger auto-declines."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(
            controller="friendly", kind="unit",
            predicates=("non_leader", "non_vehicle"),
        ))],
        optional=True,
    )


# ── han-solo:04 — Combat tricks, buffs & tempo ────────────────────────────────

def _huyang_when_played(state, source_ci, target_id, event_ctx):
    """Buff the chosen unit +2/+2 for as long as Huyang is in play.  Modelled as a
    ``permanent`` stat modifier sourced by Huyang — the documented ``permanent``
    semantic ("lasts until source leaves play") is enforced by the compute-time
    source-in-play guard (``compute_power``/``compute_hp``) plus the leave-play
    cleanup in ``_defeat_unit`` / ``_apply_return_to_hand``, so the +2/+2 winks off
    the moment Huyang leaves play.  A ``None`` target (Huyang is the only friendly
    unit) is a clean no-op."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": 2, "hp": 2},
        duration="permanent",
    ))
    return state


@card_ability("TWI", "110")
def _huyang():
    """TWI_110 — Huyang (Unit, Droid/Jedi, 2/4): "When Played: Choose another
    friendly unit. While this unit is in play, the chosen unit gets +2/+2."

    A mandatory ``WhenPlayed`` whose one ``CustomEffect.target`` (another friendly
    unit) applies a ``permanent`` +2/+2 modifier sourced by Huyang.  Unlike a
    ``ConstantAbility`` (whose target is a static filter), the buff attaches to one
    runtime-chosen instance and lasts exactly while Huyang remains in play — the
    ``permanent``-modifier-ends-when-source-leaves-play semantic."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_huyang_when_played,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
        )],
    )


@card_ability("TWI", "198")
def _enfys_nest():
    """TWI_198 — Enfys Nest (5/7, Saboteur): "When Played/On Attack: You may return
    an enemy non-leader unit with less power than this unit to its owner's hand."

    Saboteur is the keyword layer.  Two optional triggers (a ``WhenPlayed`` and an
    ``OnAttack``), each a ``ReturnToHand`` targeting an enemy non-leader unit whose
    *effective* power is strictly less than Enfys Nest's own (the
    ``power_less_than_captor`` predicate, whose captor falls back to the source unit
    — Hound's Tooth LAW_33 / Legal Authority SHD_124).  Auto-declines with no
    weaker enemy unit."""
    target = TargetSpec(controller="enemy", kind="unit",
                        predicates=("non_leader",), power_less_than_captor=True)
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[ReturnToHand(target)]),
        TriggerAbility(trigger=OnAttack(), optional=True,
                       effects=[ReturnToHand(target)]),
    ]


# ---------------------------------------------------------------------------
# Stage-4 reprint sweep (Batch 8, 2026-07-08) — shipped-set canonical encode.
# Siblings aliased in src/swu/cards/reprints.py.
# ---------------------------------------------------------------------------


@card_ability("TWI", "121")
def _generals_blade_twi121():
    """TWI_121 General's Blade (Upgrade cost 3, attach to a non-Vehicle unit): "If
    attached unit is a Jedi, it gains: 'On Attack: The next unit you play this
    phase costs 2 resources less.'"

    A ``GrantedAbility`` wrapping an ``OnAttack`` that resolves from the HOST (the
    Fallen Lightsaber SOR_137 pattern), gated by ``SOURCE_HAS_TRAIT("Jedi")`` so it
    is collected only while the host is a Jedi.  The effect is a deferred
    ``NextPlayDiscount`` with an empty trait ("the next *unit*", any trait —
    ``units_only`` defaults True; the empty-trait "any" match is the small
    ``_play_discount_entry_matches`` tweak) reducing the next unit play by 2 (the
    Khetanna LAW_158 seam).  The non-Vehicle attach is the upgrade-target parser."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[NextPlayDiscount(trait="", amount=2)],
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, "Jedi"),
    ))


# ── Stage-4 reprint sweep (batch 11) — TWI cards ─────────────────────────────

def _unnatural_life_play(state, source_ci, target_id, event_ctx):
    """Play a unit defeated this phase from the controller's discard pile: it
    costs 2 less, enters play ready, and is defeated at the start of regroup."""
    from swu.engine.actions import push_play_from_hand
    from swu.cards.models import Unit
    ctrl = state.player_by_id(source_ci.owner_id)
    defeated = set(state.game_memory.units_defeated_this_round)
    eligible = frozenset(
        c.instance_id for c in ctrl.discard
        if isinstance(c.card_def, Unit) and c.instance_id in defeated)
    if not eligible:
        return state
    push_play_from_hand(
        state, source_ci,
        cost_reduction=2, enters_ready=True, from_discard=True,
        defeat_at_regroup=True, eligible_ids=eligible)
    return state


@card_ability("TWI", "189")
def _unnatural_life():
    """TWI_189 — Unnatural Life (Event): "Play a unit that was defeated this phase
    from your discard pile.  It costs 2 resources less and enters play ready.  At
    the start of the regroup phase, defeat it."

    A thin EventAbility CustomEffect adapter onto the play-from-hand subsystem (the
    Sneak Attack SOR_219 defeat-at-regroup pattern, but sourced from the discard):
    ``push_play_from_hand(from_discard=True, cost_reduction=2, enters_ready=True,
    defeat_at_regroup=True)`` restricted by the new ``eligible_ids`` whitelist to
    units in the controller's discard whose ids are in
    ``game_memory.units_defeated_this_round`` ("defeated this phase" — defeats
    happen in ACTION and the set clears at the round rollover, so "this phase" ==
    "this round", the Admiral Trench TWI_86 precedent).  Mandatory if able (no "you
    may"); fizzles cleanly when no such unit is in the discard."""
    return EventAbility(effects=[CustomEffect(fn=_unnatural_life_play)])


# ── twi-set:01 — Direct damage & removal ──────────────────────────────────────

def _obi_wan_heal_then_burn(state, source_ci, target_id, event_ctx):
    """Heal 1 from the chosen unit and record it, so the follow-up damage clause is
    gated on the heal having happened ("If you do") and can't pick the same unit
    ("a different unit")."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_heal
    _apply_heal(state, source_ci, target_id, 1)
    event_ctx["prior_target_id"] = target_id
    event_ctx["excluded_target_id"] = target_id
    return state


@card_ability("TWI", "3")
def _obi_wan_kenobi():
    """TWI_3 — Obi-Wan Kenobi (Leader, Force/Jedi/Republic, 4/7, Sentinel).

    Undeployed: "Action [Exhaust]: Heal 1 damage from a unit."  The target is
    narrowed to a ``damaged`` unit so the Exhaust is never spent on a no-op (the
    Ozzel SOR_129 "don't offer a no-op" pattern, expressed through the target
    rather than a condition — no candidates ⇒ the effect fizzles unprompted).

    Deployed: "On Attack: Heal 1 damage from a unit.  If you do, deal 1 damage to a
    different unit."  The In Pursuit TWI_221 "If you do" shape: a CustomEffect.target
    heals and records ``prior_target_id`` (the gate) plus ``excluded_target_id``
    ("a different unit"), and the follow-up ``DealDamage`` reads both predicates —
    so with nothing damaged to heal, the burn never prompts."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[Heal(1, TargetSpec(controller="any", kind="unit",
                                        predicates=("damaged",)))],
            title="Heal 1 damage from a unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                CustomEffect(fn=_obi_wan_heal_then_burn,
                             target=TargetSpec(controller="any", kind="unit",
                                               predicates=("damaged",))),
                DealDamage(1, TargetSpec(
                    controller="any", kind="unit",
                    predicates=("requires_prior_target", "excludes_event_target"))),
            ],
            deployed_only=True,
        ),
    ]


@card_ability("TWI", "10")
def _pre_vizsla():
    """TWI_10 — Pre Vizsla (Leader, Mandalorian/Trooper, 4/6).

    Undeployed: "Action [1 resource, Exhaust]: Deal damage to a unit equal to the
    number of cards you've drawn this phase."  ``DealDamageEqualTo`` with the new
    ``controller_cards_drawn_this_phase`` count, fed by the single draw chokepoint
    (``actions._draw_cards``, ACTION-phase draws only — precisely the card's "this
    doesn't include cards drawn in the regroup phase").

    Deployed: two hand-size clauses, both the standard conditional self-grant
    (Hunting Nexu SHD_168 / Protector SHD_247) over the new
    ``CONTROLLER_HAND_SIZE_MIN`` atom — Saboteur at 3+, +2/+0 at 6+.  They are
    independent, so at 6+ cards both are live."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit"),
                count="controller_cards_drawn_this_phase")],
            title="Deal damage equal to cards drawn this phase",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Saboteur")],
            condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, 3),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=2, hp=0)],
            condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, 6),
        ),
    ]


def _mace_windu_burn(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen damaged enemy unit, then — if it now sits on 5 or more
    damage — deal 1 more to that same unit.  One CustomEffect because the second
    clause's target is not chosen but *inherited*, and its condition is read only
    after the first point of damage has landed."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    _apply_deal_damage(state, target_id, 1, source_name=name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    res = state.find_instance(target_id)
    if res is None:          # already defeated by the first point
        return state
    _, hit = res
    if hit.damage >= 5:
        _apply_deal_damage(state, target_id, 1, source_name=name,
                           dealer_id=source_ci.owner_id,
                           source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "13")
def _mace_windu():
    """TWI_13 — Mace Windu (Leader, Force/Jedi/Republic, 5/8).

    Undeployed: "Action [1 resource, Exhaust]: Deal 1 damage to a damaged enemy
    unit.  Then, if it has 5 or more damage on it, deal 1 damage to it."

    Deployed: "When Deployed: Deal 2 damage to each damaged enemy unit." — the
    ``EACH_ENEMY`` auto-target carrying the ``damaged`` predicate (mass effects keep
    their per-candidate filters through the expansion)."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(
                fn=_mace_windu_burn,
                target=TargetSpec(controller="enemy", kind="unit",
                                  predicates=("damaged",)))],
            title="Deal 1 damage to a damaged enemy unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[DealDamage(2, TargetSpec(fixed=EACH_ENEMY, kind="unit",
                                              predicates=("damaged",)))],
            deployed_only=True,
        ),
    ]


def _flip_chancellor_palpatine(state, source_ci, target_id, event_ctx):
    """"..., then flip this leader." — toggle the source leader's side marker."""
    flipped = state.game_memory.flipped_leaders
    if source_ci.instance_id in flipped:
        flipped.discard(source_ci.instance_id)
    else:
        flipped.add(source_ci.instance_id)
    return state


@card_ability("TWI", "17")
def _chancellor_palpatine():
    """TWI_17 — Chancellor Palpatine (Leader, Official/Republic).

    A double-sided leader that **flips** rather than deploys: it has no Epic Action
    and no unit stats, so both sides are ``undeployed_only`` Actions and the side in
    play is tracked by ``game_memory.flipped_leaders`` (the new
    SOURCE_LEADER_NOT_FLIPPED / SOURCE_LEADER_FLIPPED pair), not by ``deployed``.

    Front: "Action [Exhaust]: If a friendly Heroism unit was defeated this phase,
    draw a card, heal 2 damage from your base, then flip this leader."
    Back: "Action [Exhaust]: If you played a Villainy card this phase, create a
    Clone Trooper token, deal 2 damage to each enemy base, then flip this leader."

    Each side's gate is a conjunction (the right side showing AND the card's own
    "If …"), which the engine's single ``condition`` field expresses via the new
    ``ALL_OF`` composite.  Both actions cost the same Exhaust, so using one side
    leaves the leader exhausted and the other side unavailable until it readies —
    exactly the printed tempo.

    Each side lists its TARGETED effect (the base heal / the base damage) FIRST and
    its fixed ones after, so the resolver prompts exactly once — the Mandalorian
    SHD_18 "fixed-before-targeted" ordering wart.  The clauses are independent, so
    this order is outcome-identical to the printed one.

    ⚠ The two sides also print DIFFERENT ASPECTS — Chancellor Palpatine is
    [Cunning]/[Heroism], Darth Sidious [Cunning]/[Villainy] — but the DB carries one
    aspect list per row, so the card arrives with the UNION of all three.  The
    ``FlipLeaderAspects`` marker names each side's real icons for
    ``actions._available_aspects``, keyed on the same ``flipped_leaders`` ledger the
    Actions above are gated on; without it an unflipped Palpatine pays no aspect
    penalty on the Villainy half of his own deck."""
    return [
        FlipLeaderAspects(front=("Cunning", "Heroism"),
                          back=("Cunning", "Villainy")),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[
                Heal(2, TargetSpec(controller="friendly", kind="base")),
                DrawCards(1),
                CustomEffect(fn=_flip_chancellor_palpatine),
            ],
            title="Draw, heal your base, flip",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ALL_OF, (
                ConditionCheck(Condition.SOURCE_LEADER_NOT_FLIPPED),
                ConditionCheck(Condition.CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE,
                               "Heroism"),
            )),
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[
                DealDamage(2, TargetSpec(controller="enemy", kind="base")),
                CreateTokenUnit("Clone Trooper"),
                CustomEffect(fn=_flip_chancellor_palpatine),
            ],
            title="Create a Clone Trooper, damage enemy bases, flip",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ALL_OF, (
                ConditionCheck(Condition.SOURCE_LEADER_FLIPPED),
                ConditionCheck(Condition.VILLAINY_PLAYED_THIS_PHASE),
            )),
        ),
    ]


def _quinlan_vos_exhaust_and_burn(state, source_ci, target_id, event_ctx):
    """"You may exhaust this leader.  If you do, deal 1 damage to an enemy unit that
    costs the same as the played unit."  Cost and payoff in ONE effect so a leader
    that can't be exhausted never deals the damage (the Kylo SHD_141 pattern)."""
    if target_id is None or getattr(source_ci, "exhausted", False):
        return state
    source_ci.exhausted = True
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 1,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "18")
def _quinlan_vos():
    """TWI_18 — Quinlan Vos (Leader, Force/Jedi/Republic, 3/7).

    Undeployed: "When you play a unit: You may exhaust this leader.  If you do, deal
    1 damage to an enemy unit that costs the same as the played unit."  Gated on the
    leader being ready so the "you may" isn't offered when it can't be paid; the
    target uses the new ``cost_eq_event_threshold`` predicate over the played card's
    cost that the WhenYouPlayCard matcher already records.

    Deployed: the same observer, no exhaust, and "the same as **or less than**" —
    the existing ``cost_le_event_threshold`` predicate."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="unit"),
            effects=[CustomEffect(
                fn=_quinlan_vos_exhaust_and_burn,
                target=TargetSpec(controller="enemy", kind="unit",
                                  predicates=("cost_eq_event_threshold",)))],
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="unit"),
            effects=[DealDamage(1, TargetSpec(
                controller="enemy", kind="unit",
                predicates=("cost_le_event_threshold",)))],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("TWI", "34")
def _general_grievous():
    """TWI_34 — General Grievous (Unit, Official/Separatist, 4/4).

    "Ignore the aspect penalty on each Lightsaber upgrade you play on this unit." —
    the new ``IgnoreAspectPenaltyForUpgrades`` passive marker, read at the play-cost
    seam with the upgrade's chosen host (``actions._host_waives_aspect_penalty``).

    "On Attack: If this unit has 4 or more Lightsaber upgrades attached to him,
    defeat 4 enemy units." — collection is gated by the new
    ``SOURCE_ATTACHED_TRAIT_UPGRADES_MIN`` atom, and "defeat 4" is four sequential
    ``DefeatUnit`` effects: each prompts for one enemy unit, and a defeated unit has
    already left the arena, so the later picks can't repeat it (and fizzle
    unprompted once the board is empty)."""
    return [
        IgnoreAspectPenaltyForUpgrades(traits=("Lightsaber",)),
        TriggerAbility(
            trigger=OnAttack(),
            condition=ConditionCheck(Condition.SOURCE_ATTACHED_TRAIT_UPGRADES_MIN,
                                     ("Lightsaber", 4)),
            effects=[DefeatUnit(TargetSpec(controller="enemy", kind="unit"))
                     for _ in range(4)],
        ),
    ]


@card_ability("TWI", "36")
def _devastating_gunship():
    """TWI_36 — Devastating Gunship (Unit, Droid/Separatist/Transport/Vehicle, 3/5,
    Grit): "When Played: Defeat an enemy unit with 2 or less remaining HP."

    Pure reuse — ``hp_remaining_max`` already expresses "with N or less remaining
    HP", so the whole card is one declarative ``DefeatUnit``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="enemy", kind="unit",
                                       hp_remaining_max=2))],
    )


# ── twi-set:02 — Direct damage & removal ──────────────────────────────────────

def _lethal_crackdown(state, source_ci, target_id, event_ctx):
    """Defeat the chosen non-leader unit, then deal its power to your own base.

    One CustomEffect because the payoff magnitude must be read from the target
    *before* it leaves play (the Zeb LAW_45 conditional-magnitude shape, here a
    magnitude captured rather than computed)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import _apply_defeat_unit, _apply_deal_damage
    power = max(0, compute_power(state, res[1]))
    _apply_defeat_unit(state, target_id)
    own_base = state.player_by_id(source_ci.owner_id).base_instance
    if power and own_base is not None:
        _apply_deal_damage(state, own_base.instance_id, power,
                           source_name=source_ci.card_def.display_name,
                           dealer_id=source_ci.owner_id,
                           source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "41")
def _lethal_crackdown_event():
    """TWI_41 — Lethal Crackdown (Event, Tactic): "Defeat a non-leader unit.  Deal
    damage to your base equal to that unit's power"."""
    return EventAbility(effects=[CustomEffect(
        fn=_lethal_crackdown,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("non_leader",)))])


def _kashyyyk_defender(state, source_ci, target_id, event_ctx):
    """Heal up to 2 from the chosen other unit and deal exactly that much back to
    this unit — the amount is "that much", so cost and payoff are one effect (the
    Bright Hope SOR_99 "If you do" binding)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    healed = min(2, res[1].damage)
    if healed <= 0:
        return state
    from swu.abilities.resolver import _apply_heal, _apply_deal_damage
    _apply_heal(state, source_ci, target_id, healed)
    _apply_deal_damage(state, source_ci.instance_id, healed,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "44")
def _kashyyyk_defender_unit():
    """TWI_44 — Kashyyyk Defender (Unit, Wookiee, 0/5, Grit): "When Played: Heal up
    to 2 damage from another unit and deal that much damage to this unit."

    "Up to" includes 0, so the trigger is ``optional``; when taken, it heals as
    much as it can (min(2, damage on the target)) — the documented magnitude
    collapse, since a player choosing to heal wants the full amount.  Candidates
    are other DAMAGED units, so the option is never a pure self-harm no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_kashyyyk_defender,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("not_self", "damaged")))],
        optional=True,
    )


def _aethersprite_strafe(state, source_ci, target_id, event_ctx):
    """Deal 1 to this unit and 2 to the chosen other space unit — one effect so the
    self-damage can never land without the payoff."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    _apply_deal_damage(state, source_ci.instance_id, 1, source_name=name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    _apply_deal_damage(state, target_id, 2, source_name=name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "48")
def _obi_wans_aethersprite():
    """TWI_48 — Obi-Wan's Aethersprite (Unit, Jedi/Republic/Vehicle/Fighter, 4/6):
    "When Played/On Attack: You may deal 1 damage to this unit and 2 damage to
    another space unit."

    Two triggers over one shared optional effect — the standard "When Played/On
    Attack" pair (registered separately because the engine has no combined
    trigger)."""
    strafe = CustomEffect(
        fn=_aethersprite_strafe,
        target=TargetSpec(controller="any", kind="unit", arena="space",
                          predicates=("not_self",)))
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[strafe], optional=True),
        TriggerAbility(trigger=OnAttack(), effects=[strafe], optional=True),
    ]


@card_ability("TWI", "59")
def _royal_guard_attache():
    """TWI_59 — Royal Guard Attaché (Unit, Naboo/Trooper, 2/5): "When Played: Deal
    2 damage to this unit."  Pure reuse — a fixed-SELF ``DealDamage``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(fixed=SELF))],
    )


@card_ability("TWI", "76")
def _death_by_droids():
    """TWI_76 — Death by Droids (Event, Tactic): "Defeat a unit that costs 3 or
    less.  Create 2 Battle Droid tokens."

    Pure reuse — ``cost_max`` on the defeat target and the Battle Droid token
    primitive.  The targeted clause is listed first so the resolver prompts once."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit", cost_max=3)),
        CreateTokenUnit("Battle Droid", 2),
    ])


@card_ability("TWI", "78")
def _the_invasion_of_christophsis():
    """TWI_78 — The Invasion of Christophsis (Event, Separatist/Plan, cost 15,
    Exploit 4): "Choose an opponent.  Defeat each unit that player controls."

    Two players, so "choose an opponent" resolves to the one opponent and the body
    is a single ``DefeatAllUnits`` filtered to enemy units (Exploit itself is
    keyword-engine work already in place)."""
    return EventAbility(effects=[
        DefeatAllUnits(filter=TargetSpec(controller="enemy", kind="unit")),
    ])


def _consolidation_of_power(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_combined_power_play
    push_combined_power_play(state, source_ci)
    return state


@card_ability("TWI", "89")
def _consolidation_of_power_event():
    """TWI_89 — Consolidation of Power (Event, Plan): "Choose any number of friendly
    units.  You may play a unit from your hand if its cost is less than or equal to
    the combined power of the chosen units for free.  Then, defeat the chosen
    units."

    A thin CustomEffect adapter onto the new ``combined_power_play`` decision kind:
    a select-any-number loop over friendly units whose combined *effective* power
    becomes the ``cost_max`` of a free ``play_from_hand``, which carries the new
    ``then_defeat_ids`` so the chosen units die only after that play resolves — the
    printed order, and the reason a unit's power still counts while it is spent."""
    return EventAbility(effects=[CustomEffect(fn=_consolidation_of_power)])


# ── twi-set:03 — Direct damage & removal ─────────────────────────────────────
# The group's one new seam is the PHASE-SCOPED AURA (Pyrrhic Assault TWI_103):
# an ``AuraGrantedAbility`` whose source is a spent EVENT sitting in the discard
# rather than a card in play.  ``game_memory.phase_aura_sources`` lists the ids of
# such sources for the current phase, and the existing aura-collection site in
# ``resolver._collect_triggers`` scans them alongside the in-play sources.


def _pyrrhic_assault(state, source_ci, target_id, event_ctx):
    """Arm the phase-scoped aura: record this event as an aura source for the rest
    of the phase.

    The grant itself is the ``AuraGrantedAbility`` spec registered below at index 1;
    all this effect does is make the collection site *look* at this card, which by
    resolution time is on its way to the discard.  ``game_memory.phase_aura_sources``
    is cleared at the phase rollover, which is the whole of "for this phase"."""
    gm = state.game_memory
    if source_ci.instance_id not in gm.phase_aura_sources:
        gm.phase_aura_sources.append(source_ci.instance_id)
    return state


@card_ability("TWI", "103")
def _pyrrhic_assault_card():
    """TWI_103 — Pyrrhic Assault (Event, cost 3, Disaster).

    "For this phase, each friendly unit gains: 'When Defeated: Deal 2 damage to an
    enemy unit.'"

    The Gar Saxon SHD_1 ``AuraGrantedAbility`` seam, but granted by a card that is
    NOT in play: an event resolves and goes to the discard, so the aura would die
    with it.  ``phase_aura_sources`` keeps the discarded event addressable as an
    aura source until the phase ends — the collection site recovers it through
    ``find_instance`` (which reaches the discard) and so still knows its controller,
    which is what "friendly" means here.

    Two specs: idx 0 is the event body (arm the aura), idx 1 is the grant.  The
    granted trigger's source is the DYING unit, so "an enemy unit" is relative to
    that unit's controller — the same as the event's controller, by construction."""
    return [
        EventAbility(effects=[CustomEffect(fn=_pyrrhic_assault)]),
        AuraGrantedAbility(
            target=TargetSpec(controller="friendly", kind="unit"),
            ability=TriggerAbility(
                trigger=WhenDefeated(),
                effects=[DealDamage(2, TargetSpec(controller="enemy", kind="unit"))],
            ),
        ),
    ]


@card_ability("TWI", "131")
def _oom_series_officer():
    """TWI_131 — OOM-Series Officer (Unit, 2 cost, 2/1, Droid/Separatist).

    "When Defeated: Deal 2 damage to a base." — either base is a legal target
    (``controller="any"``), so this can also finish off your own base if you choose;
    the printed text does not restrict it."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


def _self_destruct(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly unit and record it as the prior target, so the
    follow-up damage's ``requires_prior_target`` gate ("If you do") opens."""
    if target_id is None:
        return state
    from swu.engine.actions import _apply_defeat_unit_by_id
    if state.find_instance(target_id) is not None:
        _apply_defeat_unit_by_id(state, target_id)
        event_ctx["prior_target_id"] = target_id
    return state


@card_ability("TWI", "140")
def _self_destruct_card():
    """TWI_140 — Self-Destruct (Event, cost 2, Tactic).

    "Defeat a friendly unit.  If you do, deal 4 damage to a unit."

    Both effects are targeted, so they become two sequential ChooseTarget steps.
    The cost is paid first (a CustomEffect that defeats and stamps
    ``prior_target_id``); the payoff is a plain ``DealDamage`` whose target spec
    carries ``requires_prior_target`` — with no friendly unit to defeat there are no
    candidates for the second step either, so the whole thing fizzles rather than
    handing out free damage."""
    return EventAbility(effects=[
        CustomEffect(fn=_self_destruct,
                     target=TargetSpec(controller="friendly", kind="unit")),
        DealDamage(4, TargetSpec(controller="any", kind="unit",
                                 predicates=("requires_prior_target",))),
    ])


def _steela_gerrera_search(state, source_ci, target_id, event_ctx):
    """Deal 2 to your own base, then search the top 8 for a Tactic card and draw it.

    "If you do" is unconditional here — the self-damage always happens once the
    optional trigger is accepted — so the two clauses are one effect.  The search is
    the ``deck_search`` seam (window=8, count=1, mandatory-if-able, rest bottomed in
    a seeded-random order)."""
    from swu.engine.actions import push_deck_search
    from swu.abilities.resolver import _apply_deal_damage
    ps = state.player_by_id(source_ci.owner_id)
    if ps.base_instance is not None:
        _apply_deal_damage(state, ps.base_instance.instance_id, 2,
                           source_name=source_ci.card_def.display_name,
                           dealer_id=source_ci.owner_id,
                           source_id=source_ci.instance_id)

    def eligible(cd):
        return "Tactic" in (getattr(cd, "traits", None) or ())

    push_deck_search(state, source_ci, count=1, eligible=eligible,
                     up_to=False, window=8)
    return state


@card_ability("TWI", "146")
def _steela_gerrera():
    """TWI_146 — Steela Gerrera (Unit, 4 cost, 4/3, Fringe).

    "When Played/When Defeated: You may deal 2 damage to your base.  If you do,
    search the top 8 cards of your deck for a Tactic card, reveal it, and draw it."

    Two optional triggers over the same effect — the "you may" is the accept/decline
    on the trigger itself, so accepting commits to both halves."""
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[CustomEffect(fn=_steela_gerrera_search)]),
        TriggerAbility(trigger=WhenDefeated(), optional=True,
                       effects=[CustomEffect(fn=_steela_gerrera_search)]),
    ]


@card_ability("TWI", "149")
def _low_altitude_gunship():
    """TWI_149 — Low Altitude Gunship (Unit, 6 cost, 6/5, Republic/Transport/Vehicle,
    Overwhelm).

    "When Played: Choose an enemy unit.  Deal 1 damage to it for each friendly
    Republic unit." — ``DealDamageEqualTo`` with the parametric count
    ``source_controller_units_with_trait:<Trait>``.  The gunship is itself a Republic
    unit and is already in its arena when its When Played resolves, so it counts
    itself (matching the printed "each friendly Republic unit")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="enemy", kind="unit"),
            count="source_controller_units_with_trait:Republic",
        )],
    )


@card_ability("TWI", "150")
def _saw_gerrera():
    """TWI_150 — Saw Gerrera (Unit, 6 cost, 4/8, Fringe/Trooper, Raid 2).

    "On Attack: If your base has 15 or more damage on it, deal 1 damage to each
    enemy ground unit." — the ``CONTROLLER_BASE_DAMAGE_MIN`` gate on trigger
    collection (below the threshold the trigger is never offered, so no prompt) plus
    the ``EACH_ENEMY`` auto-target narrowed to the ground arena."""
    return TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.CONTROLLER_BASE_DAMAGE_MIN, 15),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                          arena="ground", fixed=EACH_ENEMY))],
    )


def _resolute_strike(state, source_ci, target_id, event_ctx):
    """Deal 2 to the chosen enemy unit, then 2 to each OTHER enemy unit sharing its
    printed name.

    One CustomEffect because the second clause's targets are not chosen but derived
    from the first clause's target ("each other enemy unit with the same name as
    that unit"), and the name must be read before the first hit possibly defeats
    it."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, chosen = res
    name = getattr(chosen.card_def, "name", None)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    same_name = [u.instance_id for u in (opp.ground_arena + opp.space_arena)
                 if u.instance_id != target_id
                 and getattr(u.card_def, "name", None) == name]

    from swu.abilities.resolver import _apply_deal_damage
    src_name = source_ci.card_def.display_name
    for hit_id in [target_id] + same_name:
        if state.find_instance(hit_id) is not None:
            _apply_deal_damage(state, hit_id, 2, source_name=src_name,
                               dealer_id=source_ci.owner_id,
                               source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "151")
def _resolute():
    """TWI_151 — Resolute (Unit, 10 cost, 8/8, Capital Ship/Republic/Vehicle).

    "This unit costs 1 resource less to play for every 5 damage on your base." — a
    ``CostReduction`` carrying the new ``per_controller_base_damage`` scaling field
    (amount=1 per 5 damage, integer division), read at the same single play-cost
    site as every other CostReduction, so it moves both affordability in
    ``legal_actions`` and the resources actually exhausted.

    "When Played/On Attack: Deal 2 damage to an enemy unit and each other enemy unit
    with the same name as that unit." — one targeted CustomEffect (the extra targets
    are derived from the chosen one, not chosen)."""
    strike = [CustomEffect(fn=_resolute_strike,
                           target=TargetSpec(controller="enemy", kind="unit"))]
    return [
        CostReduction(amount=1, per_controller_base_damage=5),
        TriggerAbility(trigger=WhenPlayed(), effects=list(strike)),
        TriggerAbility(trigger=OnAttack(), effects=list(strike)),
    ]


# ── twi-set:04 — Direct damage & removal ─────────────────────────────────────


@card_ability("TWI", "154")
def _mister_bones():
    """TWI_154 — Mister Bones (Unit, 1 cost, 3/1, Droid/Fringe).

    "On Attack: If you have no cards in your hand, you may deal 3 damage to a ground
    unit." — the empty-hand gate is ``CONTROLLER_HAND_SIZE_MAX(0)`` (the mirror of
    the MIN atom) on trigger COLLECTION, so a non-empty hand never even offers the
    prompt; ``optional=True`` carries the "you may"."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MAX, 0),
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
    )


def _twice_the_pride(state, source_ci, target_id, event_ctx):
    """Deal 2 damage to the unit this upgrade was just attached to.

    The host id is threaded by ``_attach_upgrade`` as ``event_ctx["attached_to_id"]``
    (the Darth Maul's Lightsaber LOF_140 pattern); the target is not chosen, so this
    is a non-targeted CustomEffect rather than a DealDamage with a TargetSpec."""
    host_id = (event_ctx or {}).get("attached_to_id")
    if not host_id:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, host_id, 2,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "155")
def _twice_the_pride_card():
    """TWI_155 — Twice the Pride (Upgrade, 2 cost, Innate).

    "When Played: Deal 2 damage to attached unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_twice_the_pride)],
    )


def _unlimited_power_mark(amount: int):
    """Record one of Unlimited Power's four hits (target + amount) instead of
    dealing it, and exclude that unit from the remaining choices ("a SECOND unit",
    "a THIRD unit", …).  The damage is applied later, all at once."""
    def _fn(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        event_ctx.setdefault("unlimited_power_hits", []).append((target_id, amount))
        event_ctx.setdefault("excluded_target_ids", set()).add(target_id)
        return state
    return _fn


def _unlimited_power_apply(state, source_ci, target_id, event_ctx):
    """Apply every recorded hit — the printed "(All damage is dealt
    simultaneously.)".  Nothing lands until all four targets have been chosen, so an
    early defeat cannot pre-empt a later choice."""
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    for hit_id, amount in (event_ctx or {}).get("unlimited_power_hits", []):
        if state.find_instance(hit_id) is not None:
            _apply_deal_damage(state, hit_id, amount, source_name=name,
                               dealer_id=source_ci.owner_id,
                               source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "156")
def _unlimited_power():
    """TWI_156 — Unlimited Power (Event, 6 cost, Force).

    "Deal 4 damage to a unit, 3 damage to a second unit, 2 damage to a third unit,
    and 1 damage to a fourth unit.  (All damage is dealt simultaneously.)"

    Four sequential ChooseTarget steps over distinct units (the Attack Pattern Delta
    SOR_106 ``excludes_event_targets`` accumulating-set pattern), but each step only
    RECORDS its hit; a final non-targeted effect then applies them all.  That is what
    makes the damage simultaneous: no unit is defeated — and so no target becomes
    illegal, and no When Defeated fires — while choices are still being made.  With
    fewer than four units on the board the later steps simply have no candidates and
    fizzle; the applier still runs, because it takes no target."""
    return EventAbility(effects=[
        CustomEffect(fn=_unlimited_power_mark(4),
                     target=TargetSpec(controller="any", kind="unit")),
        CustomEffect(fn=_unlimited_power_mark(3),
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("excludes_event_targets",))),
        CustomEffect(fn=_unlimited_power_mark(2),
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("excludes_event_targets",))),
        CustomEffect(fn=_unlimited_power_mark(1),
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("excludes_event_targets",))),
        CustomEffect(fn=_unlimited_power_apply),
    ])


@card_ability("TWI", "157")
def _disaffected_senator():
    """TWI_157 — Disaffected Senator (Unit, 1 cost, 0/4, Official/Separatist).

    "Action [2 resources, Exhaust]: Deal 2 damage to a base." — either base is a
    legal target, as printed."""
    return ActivatedAbility(
        costs=[PayResources(2), ExhaustSelf()],
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


@card_ability("TWI", "160")
def _vanguard_droid_bomber():
    """TWI_160 — Vanguard Droid Bomber (Unit, 2 cost, 2/2,
    Droid/Fighter/Separatist/Vehicle).

    "When Played: If you control another Separatist unit, deal 2 damage to an enemy
    base." — ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Separatist")`` gates trigger
    collection ("another" = excluding the bomber itself, which is Separatist)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Separatist"),
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base"))],
    )


def _reckless_torrent_friendly_hit(state, source_ci, target_id, event_ctx):
    """Deal 2 to the chosen friendly unit and record its arena, so the follow-up
    enemy hit is restricted to "an enemy unit in the same arena"."""
    if target_id is None:
        return state
    from swu.engine.state import Zone
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, hit = res
    event_ctx["same_arena"] = (
        "ground" if hit.zone == Zone.GROUND_ARENA else
        "space" if hit.zone == Zone.SPACE_ARENA else None)
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 2,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=source_ci.instance_id)
    return state


@card_ability("TWI", "162")
def _reckless_torrent():
    """TWI_162 — Reckless Torrent (Unit, 3 cost, 3/1, Fighter/Republic/Vehicle,
    Coordinate).

    "Coordinate — When Played: You may deal 2 damage to a friendly unit and 2 damage
    to an enemy unit in the same arena."

    The Coordinate condition gates trigger collection; ``optional=True`` is the "you
    may".  The friendly hit stamps ``event_ctx["same_arena"]`` so the enemy hit's
    ``same_arena_as_event`` predicate (Haymaker LAW_168) narrows the second choice —
    with no enemy unit in that arena the second step simply fizzles."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=_COORDINATE,
        effects=[
            CustomEffect(fn=_reckless_torrent_friendly_hit,
                         target=TargetSpec(controller="friendly", kind="unit")),
            DealDamage(2, TargetSpec(controller="enemy", kind="unit",
                                     predicates=("same_arena_as_event",))),
        ],
    )


@card_ability("TWI", "165")
def _kit_fisto():
    """TWI_165 — Kit Fisto (Unit, 6 cost, 7/6, Force/Jedi/Republic, Saboteur +
    Coordinate).

    "Coordinate — On Attack: You may deal 3 damage to a ground unit." — Saboteur is
    the printed keyword (handled by the keyword engine); the Coordinate clause is an
    optional On Attack gated by the shared condition."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=_COORDINATE,
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
    )


# ── twi-set:05 — Direct damage & removal ─────────────────────────────────────


@card_ability("TWI", "167")
def _heavy_persuader_tank():
    """TWI_167 — Heavy Persuader Tank (Unit, 7 cost, 6/5,
    Droid/Separatist/Tank/Vehicle, Exploit 2).

    Exploit is the keyword engine (the sacrifice-then-discount play path); the
    residual text is a plain optional "When Played: You may deal 2 damage to a
    ground unit"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
    )


@card_ability("TWI", "173")
def _blood_sport():
    """TWI_173 — Blood Sport (Event, 3 cost, Fringe): "Deal 2 damage to each ground
    unit."

    ``fixed=EACH_IN_PLAY`` auto-targets every ground unit of either controller and
    resolves inline, with no prompt (the HK-87 Assassin Droid LOF_235 pattern)."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="any", kind="unit", arena="ground",
                                 fixed=EACH_IN_PLAY)),
    ])


def _guerilla_insurgency(state, source_ci, target_id, event_ctx):
    """Each player defeats a resource and discards 2 cards; deal 4 to each ground
    unit.

    The resource is auto-selected (resources are fungible face-down cards — the
    K-2SO SOR_145 convention) via the shared ``_fire_defeat_own_resource``, starting
    with the controller.  The two hand discards ARE a real choice, so they go
    through the symmetric ``discard_excess_from_hand`` decision in its new
    per-player ``count`` mode (each player discards 2, controller first).

    ORDER: the decision is pushed last, so the mass damage settles first and the
    discards finish after it.  The printed order is the reverse, but nothing about
    a hand discard can change how much damage a ground unit takes, so the two are
    interchangeable here."""
    from swu.engine.actions import (_fire_defeat_own_resource,
                                    push_discard_excess_from_hand)
    from swu.abilities.resolver import _apply_deal_damage
    controller_id = source_ci.owner_id
    order = ([controller_id]
             + [p.player_id for p in state.players if p.player_id != controller_id])
    for pid in order:
        _fire_defeat_own_resource(state, pid)
    name = source_ci.card_def.display_name
    ground = [u.instance_id for p in state.players for u in p.ground_arena]
    for iid in ground:
        if state.find_instance(iid) is not None:
            _apply_deal_damage(state, iid, 4, source_name=name,
                               dealer_id=controller_id,
                               source_id=source_ci.instance_id)
    push_discard_excess_from_hand(state, source_ci, count=2)
    return state


@card_ability("TWI", "177")
def _guerilla_insurgency_card():
    """TWI_177 — Guerilla Insurgency (Event, 8 cost, Tactic): "Each player defeats a
    resource they control and discards 2 cards from their hand.  Deal 4 damage to
    each ground unit." """
    return EventAbility(effects=[CustomEffect(fn=_guerilla_insurgency)])


def _sabine_wren_mill(state, source_ci, target_id, event_ctx):
    """Discard the top card of your deck; if it shares no aspect with your base,
    deal 2 damage to the chosen ground unit.

    "Discard a card from your deck" mills the top card (the deck is ordered — no
    choice); the aspect comparison is against the controller's base, the Kuiil
    SHD_41 shape.  The target is chosen BEFORE the mill is revealed — the
    optimal-play collapse this codebase uses throughout, since the identity of the
    milled card cannot change which unit you would rather hit.  An empty deck mills
    nothing and so shares no aspect: the damage still lands, as printed."""
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard
    from swu.abilities.resolver import _apply_deal_damage
    ps = state.player_by_id(source_ci.owner_id)
    card_aspects = set()
    if ps.deck:
        card = ps.deck.pop(0)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(state, card)
        card_aspects = {a.name for a in (getattr(card.card_def, "aspects", None) or ())}
    base = ps.base_instance
    base_aspects = ({a.name for a in (getattr(base.card_def, "aspects", None) or ())}
                    if base is not None else set())
    if card_aspects & base_aspects:
        return state
    if target_id is None:
        return state
    return _apply_deal_damage(state, target_id, 2,
                              source_name=source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id,
                              source_id=source_ci.instance_id)


@card_ability("TWI", "195")
def _sabine_wren_twi():
    """TWI_195 — Sabine Wren (Unit, 4 cost, 4/4, Fringe/Mandalorian/Spectre).

    "While this unit is exhausted, she can't be attacked (unless she gains
    Sentinel)." — the new ``CannotBeAttackedWhileExhausted`` marker, read at the
    attack-enumeration seam next to the Hidden filter: while exhausted she drops out
    of the eligible defenders entirely.  Sentinel is the printed escape hatch (and a
    necessary one — an unattackable Sentinel would lock her whole arena).

    "On Attack: You may discard a card from your deck.  If it doesn't share an
    aspect with your base, deal 2 damage to a ground unit." — an optional trigger
    whose one CustomEffect binds the mill and its conditional payoff."""
    return [
        CannotBeAttackedWhileExhausted(),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[CustomEffect(
                fn=_sabine_wren_mill,
                target=TargetSpec(controller="any", kind="unit", arena="ground"),
            )],
        ),
    ]


def _jar_jar_random_hit(state, source_ci, target_id, event_ctx):
    """Deal 2 damage to a random unit or base — a uniform draw over every unit in
    either arena plus both bases (Jar Jar himself included; he is a unit in play
    when this resolves, and the card says "a random unit or base" without
    qualification).

    The draw comes from the embedded seeded RNG (``make_rng`` + writing back
    ``rng_state``), the same discipline as every other random effect, so a replayed
    game reproduces the same victim."""
    from swu.abilities.resolver import _apply_deal_damage
    candidates = []
    for p in state.players:
        candidates.extend(p.ground_arena + p.space_arena)
        if p.base_instance is not None:
            candidates.append(p.base_instance)
    if not candidates:
        return state
    rng = state.make_rng()
    pick = candidates[rng.randrange(len(candidates))]
    state.rng_state = rng.getstate()
    return _apply_deal_damage(state, pick.instance_id, 2,
                              source_name=source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id,
                              source_id=source_ci.instance_id)


@card_ability("TWI", "202")
def _jar_jar_binks():
    """TWI_202 — Jar Jar Binks (Unit, 2 cost, 2/3, Gungan): "On Attack: Deal 2
    damage to a random unit or base." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_jar_jar_random_hit)],
    )


def _freelance_assassin_pay(state, source_ci, target_id, event_ctx):
    """Pay 2 resources, then deal 2 damage to the chosen unit — the payment and the
    payoff bound into one CustomEffect so "If you do" holds (the Boba Fett LAW_214 /
    Bright Hope SOR_99 pattern).  Affordability is guaranteed by the trigger's
    ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` gate, re-checked defensively."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 2:
        return state  # cannot pay → no damage
    from swu.engine.actions import _exhaust_resources
    from swu.abilities.resolver import _apply_deal_damage
    _exhaust_resources(ps, 2)
    return _apply_deal_damage(state, target_id, 2,
                              source_name=source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id,
                              source_id=source_ci.instance_id)


@card_ability("TWI", "212")
def _freelance_assassin():
    """TWI_212 — Freelance Assassin (Unit, 3 cost, 4/2, Underworld): "When Played:
    You may pay 2 resources.  If you do, deal 2 damage to a unit."

    Optional ("you may") and gated by ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` so it
    is never offered when the 2 resources can't be paid (the "don't offer a no-op"
    pattern).  Any unit in either arena is a legal target, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, 2),
        effects=[CustomEffect(
            fn=_freelance_assassin_pay,
            target=TargetSpec(controller="any", kind="unit"),
        )],
    )


def _execute_order_66(state, source_ci, target_id, event_ctx):
    """Deal 6 damage to each Jedi unit; each unit defeated this way makes its
    CONTROLLER create a Clone Trooper token.

    The Jedi units are snapshotted with their controllers first, so the damage is
    simultaneous (nothing that dies mid-sweep is skipped and no newly-arrived unit
    is hit).  "Defeated this way" is then read off the board: a snapshotted unit no
    longer in one of its controller's arenas was killed by this sweep — the only
    thing that could have removed it — and that controller creates one token via the
    shared ``_create_token_units`` path (so each token enters exhausted and fires the
    normal enter-play bus)."""
    from swu.engine.traits import has_trait
    from swu.engine.actions import _create_token_units
    from swu.abilities.resolver import _apply_deal_damage
    victims = [(p.player_id, u.instance_id)
               for p in state.players
               for u in (p.ground_arena + p.space_arena)
               if has_trait(state, u, "Jedi")]
    name = source_ci.card_def.display_name
    for _pid, iid in victims:
        if state.find_instance(iid) is not None:
            _apply_deal_damage(state, iid, 6, source_name=name,
                               dealer_id=source_ci.owner_id,
                               source_id=source_ci.instance_id)
    for pid, iid in victims:
        ps = state.player_by_id(pid)
        if not any(u.instance_id == iid
                   for u in (ps.ground_arena + ps.space_arena)):
            _create_token_units(state, ps, "Clone Trooper", 1)
    return state


@card_ability("TWI", "239")
def _execute_order_66_card():
    """TWI_239 — Execute Order 66 (Event, 4 cost, Plan): "Deal 6 damage to each Jedi
    unit.  For each unit defeated this way, its controller creates a Clone Trooper
    token." """
    return EventAbility(effects=[CustomEffect(fn=_execute_order_66)])


# ── twi-set:06 — Direct damage & removal ─────────────────────────────────────

def _hold_out_blaster_shot(state, source_ci, target_id, event_ctx):
    """Have the ATTACHED UNIT deal 1 damage to the chosen ground unit.

    The only thing this adds over a plain ``DealDamage(1, ...)`` is the source: the
    printed text is "have attached unit deal 1 damage", so the shot is attributed to
    the HOST — the log reads "takes 1 from <host>" and any source-keyed guard
    (Malakili LOF_108's friendly-fire prevention, which asks what card dealt it)
    sees the unit that fired rather than the gun.  The host id is threaded by
    ``_attach_upgrade`` as ``event_ctx["attached_to_id"]`` (the Mandalorian Armor
    SHD_73 read); if the host has somehow left play the upgrade falls back to
    dealing the damage itself, so the effect never silently vanishes.

    ``dealer_id`` stays the upgrade's owner (the codebase-wide convention: the
    player whose ability this is, which is what the non-combat-damage observers are
    keyed on), and ``_target_protected`` is checked against the upgrade for the same
    reason — "can't be damaged by enemy card abilities" (SHD_187) is a question
    about whose ability fired, not about which body fired it."""
    from swu.abilities.resolver import _apply_deal_damage, _target_protected
    if _target_protected(state, target_id, source_ci, "damage"):
        return state
    shooter = source_ci
    host_id = (event_ctx or {}).get("attached_to_id")
    if host_id:
        result = state.find_instance(host_id)
        if result is not None:
            shooter = result[1]
    _apply_deal_damage(state, target_id, 1,
                       source_name=shooter.card_def.display_name,
                       dealer_id=source_ci.owner_id,
                       source_id=shooter.instance_id)
    return state


@card_ability("TWI", "256")
def _hold_out_blaster():
    """TWI_256 — Hold-Out Blaster (Upgrade, Item/Weapon, cost 1): "Attach to a
    non-Vehicle unit.  When Played: You may have attached unit deal 1 damage to a
    ground unit."

    An optional ``WhenPlayed`` with one targeted CustomEffect.  The attach
    restriction is the engine's upgrade-target parser (``non_vehicle``), and an
    upgrade's own WhenPlayed is collected by the UpgradePlayed special-case in
    ``resolver._collect_triggers``.  The target is "a ground unit" — either
    controller's, including the host itself — so the ``optional=True`` "you may"
    is what keeps a lone friendly board from being forced to shoot itself."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(
            fn=_hold_out_blaster_shot,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
        )],
    )


# ── twi-set:07 — Card advantage & disruption ─────────────────────────────────

def _yoda_twi_4_top_or_bottom(state, source_ci, target_id, event_ctx):
    """Yoda TWI_4, undeployed Action, second half: "…then put a card from your hand
    on the top or bottom of your deck".

    The bottom_from_hand decision (Private Manufacturing TWI_257) with the new
    ``allow_top`` option, so every hand card is offered in BOTH placements.  It runs
    after the draw (effect 1), so the just-drawn card is among the choices — which is
    the whole point of the ability (draw, then bury or re-set the top)."""
    from swu.engine.actions import push_bottom_from_hand
    push_bottom_from_hand(state, source_ci, count=1, allow_top=True)
    return state


def _yoda_twi_4_mill(state, source_ci, target_id, event_ctx):
    """Yoda TWI_4, deployed When Deployed, first half: "You may discard a card from
    your deck.  If you do, …".

    Mills the top card of the controller's own deck and ARMS the follow-up defeat by
    recording the discarded card's printed cost as the ``cost_le_event_threshold``
    ceiling plus ``prior_target_id`` (the ``requires_prior_target`` gate) — the Force
    Throw SOR_167 "record then gate" shape, so effect 2 prompts only when a card was
    actually discarded.  An empty deck records nothing and the defeat never fires."""
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    card = ps.deck.pop(0)
    card.zone = Zone.DISCARD
    card.face_down = False
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    cost = getattr(card.card_def, "cost", None)
    if cost is None:
        return state
    event_ctx["cost_le_threshold"] = cost
    event_ctx["prior_target_id"] = card.instance_id
    return state


@card_ability("TWI", "4")
def _yoda_sensing_darkness():
    """TWI_4 — Yoda, Sensing Darkness (Leader, Force/Jedi/Republic, 4/9, Restore 2).

    Undeployed: "Action [Exhaust]: If a unit left play this phase, draw a card, then
    put a card from your hand on the top or bottom of your deck."  An
    ``undeployed_only`` ActivatedAbility gated by the new
    ``ANY_UNIT_DEFEATED_THIS_PHASE`` atom (the controller-blind sibling of
    ENEMY_UNIT_DEFEATED_THIS_PHASE — "a unit", either side's), so the exhaust is never
    spent on a no-op; its two effects are a plain draw and the top-or-bottom decision.

    Deployed: "When Deployed: You may discard a card from your deck.  If you do,
    defeat an enemy non-leader unit that costs the same as or less than the discarded
    card."  An optional WhenDeployed (the "you may" is on the discard) whose leading
    non-targeted CustomEffect mills and arms, followed by a ``DefeatUnit`` whose
    target carries ``requires_prior_target`` + ``cost_le_event_threshold`` — so with
    nothing milled, or nothing cheap enough on the board, it fizzles with no prompt.
    Restore 2 and the Epic Action deploy are handled by the keyword/leader layers."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DrawCards(count=1),
                     CustomEffect(fn=_yoda_twi_4_top_or_bottom)],
            title="Draw a card, then top/bottom a card from your hand",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ANY_UNIT_DEFEATED_THIS_PHASE),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            optional=True,
            deployed_only=True,
            effects=[
                CustomEffect(fn=_yoda_twi_4_mill),
                DefeatUnit(TargetSpec(
                    controller="enemy", kind="unit",
                    predicates=("non_leader", "requires_prior_target",
                                "cost_le_event_threshold"))),
            ],
        ),
    ]


def _padme_twi_8_search(state, source_ci, target_id, event_ctx):
    """Padmé TWI_8 (both sides): "Search the top 3 cards of your deck for a Republic
    card, reveal it, and draw it.  (Put the other cards on the bottom of your deck in
    a random order.)" — a thin adapter onto ``push_deck_search``: window 3, exactly
    one card, ``up_to=False`` (mandatory if able — "search FOR a Republic card"), the
    default bottom-in-random-order rest disposition."""
    from swu.engine.actions import push_deck_search
    push_deck_search(
        state, source_ci, count=1, window=3, up_to=False,
        eligible=lambda cd: "Republic" in (getattr(cd, "traits", ()) or ()))
    return state


@card_ability("TWI", "8")
def _padme_amidala_serving_the_republic():
    """TWI_8 — Padmé Amidala, Serving the Republic (Leader, Naboo/Official/Republic,
    2/7, Coordinate + Restore 1).

    Both sides are the same search, gated by the same Coordinate condition ("while you
    control 3 or more units", ``CONTROLLER_N_PLUS_UNITS`` param 3):

      * undeployed — "Coordinate — Action [1 resource, Exhaust]: Search the top 3 …";
        the condition gates availability in ``legal_actions``.
      * deployed — "Coordinate — On Attack: Search the top 3 …"; the condition gates
        trigger collection, so it is not even offered below 3 units.

    Restore 1 and the Epic Action deploy are handled by the keyword/leader layers."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_padme_twi_8_search)],
            title="Search the top 3 for a Republic card",
            undeployed_only=True,
            condition=_COORDINATE,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_padme_twi_8_search)],
            deployed_only=True,
            condition=_COORDINATE,
        ),
    ]


@card_ability("TWI", "25")
def _shadow_collective_camp():
    """TWI_25 — Shadow Collective Camp (Base, 25 HP): "When you deploy a leader: Draw
    a card."

    The new ``WhenYouDeployLeader`` observer — the sibling of ``WhenDeployed`` that
    fires for a DIFFERENT permanent watching its own controller's deploy.  A Base is
    reached by the base_zone branch of ``resolver._collect_triggers``, and the trigger
    is collected at the existing LeaderDeployed firing sites, so this needs no new
    firing point.  Not optional — "draw a card" is unconditional."""
    return TriggerAbility(
        trigger=WhenYouDeployLeader(),
        effects=[DrawCards(count=1)],
    )


def _morgan_elsbeth_twi_35(state, source_ci, target_id, event_ctx):
    """Morgan Elsbeth TWI_35 On Attack: "You may defeat another friendly unit.  If
    you do, draw a card."

    The cost and its payoff live in ONE CustomEffect (the "If you do" binding, Bright
    Hope SOR_99) so the draw can never happen without the sacrifice; the "you may" is
    the trigger's ``optional``, and with no other friendly unit the target set is
    empty so the trigger self-declines."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import _draw_cards
    _apply_defeat_unit(state, target_id)
    _draw_cards(state, state.player_by_id(source_ci.owner_id), 1)
    return state


@card_ability("TWI", "35")
def _morgan_elsbeth():
    """TWI_35 — Morgan Elsbeth, Keeper of Many Secrets (Unit, Force/Imperial/Official,
    3/6): "Restore 1.  On Attack: You may defeat another friendly unit.  If you do,
    draw a card."  Restore 1 is the keyword layer; the On Attack is one targeted
    CustomEffect over friendly non-self units."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_morgan_elsbeth_twi_35,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
        )],
    )


def _a_fine_addition_twi_40(state, source_ci, target_id, event_ctx):
    """A Fine Addition TWI_40: "If an enemy unit was defeated this phase, play an
    upgrade from your hand or from any player's discard pile, ignoring its aspect
    penalty."

    The leading "If …" is checked here rather than as a spec-level gate (an
    EventAbility has no ``condition`` field) — an event that fizzles still costs its
    play.  The play itself is ``push_play_upgrade_from_hand`` widened with
    ``include_discards`` (every player's discard joins the controller's hand as a
    source zone) and ``ignore_aspect_penalty`` (the whole penalty, unqualified —
    the General Grievous TWI_34 reading); the cost is otherwise paid in full."""
    from swu.engine.actions import push_play_upgrade_from_hand
    if not ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE).evaluate(
            state, source_ci):
        return state
    push_play_upgrade_from_hand(
        state, source_ci, upgrade_id=None, free=False,
        include_discards=True, ignore_aspect_penalty=True)
    return state


@card_ability("TWI", "40")
def _a_fine_addition():
    """TWI_40 — A Fine Addition (Event, Supply, cost 0) — see the effect docstring."""
    return EventAbility(effects=[CustomEffect(fn=_a_fine_addition_twi_40)])


def _foresight_twi_68(state, source_ci, target_id, event_ctx):
    """Foresight TWI_68's granted regroup trigger: "Name a card, then look at the top
    card of your deck.  If it's the named card, you may reveal and draw it."

    ``source_ci`` is the HOST unit (a GrantedAbility resolves from the host), so "your
    deck" is the host controller's deck.

    Two documented collapses, both from the fact that the naming is information-free:
    the player cannot see the top card, so the ONLY thing their choice moves is the
    hit probability — which is maximised by naming the most numerous name still in the
    deck (ties broken alphabetically for determinism).  And "you may … draw it" is
    never declined in practice, so a hit draws.  Hence no prompt at all.

    Timing deviation: the engine's regroup PhaseStartTrigger site runs AFTER the
    regroup draws, not "before drawing cards" as printed — so the peeked card is the
    one below this regroup's draws.  With a name-blind guess the two orderings are
    equivalent in expectation, so the deviation is unobservable in play."""
    from collections import Counter
    from swu.engine.actions import _draw_cards
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    counts = Counter(ci.card_def.display_name for ci in ps.deck)
    named = min(counts, key=lambda n: (-counts[n], n))
    if ps.deck[0].card_def.display_name == named:
        _draw_cards(state, ps, 1)
    return state


@card_ability("TWI", "68")
def _foresight():
    """TWI_68 — Foresight (Upgrade, Learned, cost 1): "Attached unit gains: 'When the
    regroup phase starts (before drawing cards): Name a card, then look at the top
    card of your deck.  If it's the named card, you may reveal and draw it.'"

    A ``GrantedAbility`` (so it resolves from the HOST — "your deck" follows the host's
    controller, including when the upgrade sits on an enemy unit) wrapping a
    ``PhaseStartTrigger(phase="regroup")``, the Contracted Hunter JTL_216 timing."""
    return GrantedAbility(TriggerAbility(
        trigger=PhaseStartTrigger(phase="regroup"),
        effects=[CustomEffect(fn=_foresight_twi_68)],
    ))

def _satine_kryze_twi_47(state, source_ci, target_id, event_ctx):
    """Satine Kryze TWI_47's granted Action: "Discard cards from an opponent's deck
    equal to half this unit's remaining HP, rounded up."

    ``source_ci`` is the ACTING unit (the aura resolves from whoever used it), not
    Satine — so "this unit's remaining HP" and "an opponent" both follow the actor.
    The actor is re-located through ``find_instance`` so its CONTROLLER (the arena
    holding it, which is what "an opponent" is relative to) is read from the board
    rather than from ``owner_id``, which never changes under a control swap.

    Two-player, so "an opponent's deck" is unambiguous and needs no prompt.  Half is
    rounded UP, and a deck that runs out simply mills fewer cards (running out of
    deck is not a loss condition here — it is checked at the regroup draw)."""
    from swu.engine.state import Zone
    from swu.engine.actions import compute_hp, note_hand_or_deck_discard
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    actor_ps, actor = res
    hp_left = max(0, compute_hp(state, actor) - actor.damage)
    count = -(-hp_left // 2)          # rounded up
    opp = next((p for p in state.players if p.player_id != actor_ps.player_id), None)
    if opp is None:
        return state
    for _ in range(count):
        if not opp.deck:
            break
        card = opp.deck.pop(0)
        card.zone = Zone.DISCARD
        card.face_down = False
        opp.discard.append(card)
        note_hand_or_deck_discard(state, card)
    return state


@card_ability("TWI", "47")
def _satine_kryze():
    """TWI_47 — Satine Kryze, Advocate for Peace (Unit, Mandalorian/Official, 0/6):
    "Each unit (including enemy units) gains: 'Action [Exhaust]: Discard cards from
    an opponent's deck equal to half this unit's remaining HP, rounded up.'"

    The AURA-granted **ActivatedAbility** seam — an ``AuraGrantedAbility`` wrapping
    an ActivatedAbility instead of the WhenDefeated trigger it carried until now
    (Gar Saxon SHD_1).  One source grants to MANY units, so the acting unit cannot
    be derived from the source the way an upgrade's single host can (Heroic Resolve
    SHD_155); ``legal_actions`` therefore offers the Action once per matching unit
    and the ``UseAbility`` names both — ``source_id`` for the spec, ``actor_id`` for
    the unit.  ``target=TargetSpec()`` is the default "any unit, either arena, either
    controller", which is literally "each unit (including enemy units)" — including
    Satine herself, who is a unit and gains it too.

    Enemy units are armed for THEIR controller, not for Satine's: a unit's abilities
    are used by whoever controls it, so the enumeration walks the active player's own
    arenas and the exhaust cost falls on the acting unit.  She is a 0-power 6-HP
    body, so her own copy mills 3 — and every mill shrinks as the unit takes damage."""
    return AuraGrantedAbility(
        ability=ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_satine_kryze_twi_47)],
            title="Discard half this unit's remaining HP (rounded up) from an "
                  "opponent's deck",
        ),
        target=TargetSpec(),
    )

# ── twi-set:08 — card advantage & disruption ──────────────────────────────────

def _reprocess(state, source_ci, target_id, event_ctx):
    """Adapter: bottom up to 4 UNITS from your own discard, then a Battle Droid each."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=4,
        own_only=True,                                  # "in YOUR discard pile"
        eligible=lambda cd: isinstance(cd, Unit),       # "choose up to 4 UNITS"
        then_create_token="Battle Droid",
    )
    return state


@card_ability("TWI", "88")
def _reprocess_card():
    """TWI_88 — Reprocess (Event, Supply, cost 3): "Choose up to 4 units in your
    discard pile.  Put them on the bottom of your deck in a random order and create
    that many Battle Droid tokens."

    A thin CustomEffect adapter onto the ``bottom_from_discard`` decision (Restock
    SOR_252), which already bottoms the picks in a seeded-random order.  Three
    additive knobs express this card's narrower version: ``own_only`` (Restock says
    "a discard pile", this one "your discard pile"), ``eligible`` (units only), and
    ``then_create_token`` — the token payoff scales with how many cards were
    actually bottomed, so it settles at the finish rather than up front, and
    choosing none creates none."""
    return EventAbility(effects=[CustomEffect(fn=_reprocess)])


@card_ability("TWI", "100")
def _petition_the_senate():
    """TWI_100 — Petition the Senate (Event, Tactic, cost 3): "If you control 3 or
    more Official units, draw 3 cards."

    A ``ConditionalEffect`` over the new ``CONTROLLER_N_PLUS_TRAIT_UNITS`` atom (the
    trait-narrowed sibling of the Coordinate condition, param=(trait, N)).  The
    event is playable either way — the condition is checked on resolution, not on
    play — and simply draws nothing when it fails."""
    return EventAbility(effects=[ConditionalEffect(
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_TRAIT_UNITS,
                                 ("Official", 3)),
        if_true=(DrawCards(3),),
        if_false=(),
    )])


def _mas_amedda(state, source_ci, target_id, event_ctx):
    """Exhaust Mas Amedda; if he was ready, search the top 4 of his controller's
    deck for a unit and draw it.

    ONE effect, so the cost and its payoff are atomic (the "If you do" binding):
    the ability is already gated ``SOURCE_READY`` at collection, and re-checking the
    live instance here keeps the search from happening without the exhaust if the
    board moved between collection and resolution."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search
    result = state.find_instance(source_ci.instance_id)
    if result is None:
        return state
    _, me = result
    if me.exhausted:
        return state
    me.exhausted = True
    push_deck_search(
        state, source_ci, count=1, window=4, up_to=False,
        eligible=lambda cd: isinstance(cd, Unit),
    )
    return state


@card_ability("TWI", "101")
def _mas_amedda_card():
    """TWI_101 — Mas Amedda, Vice Chair (Unit, Official/Republic, 0/4): "When you
    play another unit: You may exhaust this unit.  If you do, search the top 4 cards
    of your deck for a unit, reveal it, and draw it.  (Put the other cards on the
    bottom of your deck in a random order.)"

    A ``WhenYouPlayCard(card_type="unit")`` observer (``exclude_self`` defaults True
    → "another unit"), ``optional`` for the "you may" and gated ``SOURCE_READY`` so
    it is never offered when the exhaust cost cannot be paid — the Grogu ASH_18
    shape.  The search is ``push_deck_search(window=4, count=1, up_to=False)``: "search
    for a unit" is mandatory-if-able, and the bottom-the-rest-in-random-order clause
    is that helper's default disposition."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit"),
        effects=[CustomEffect(fn=_mas_amedda)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_READY),
    )


@card_ability("TWI", "152")
def _mace_windus_lightsaber():
    """TWI_152 — Mace Windu's Lightsaber (Upgrade, Item/Lightsaber/Weapon, +2/+2,
    cost 2): "Attach to a non-Vehicle unit.  When Played: If attached unit is Mace
    Windu, draw 2 cards."

    The Ahsoka's Padawan Lightsaber TWI_248 / Luke's Lightsaber SOR_53 pattern: a
    ``WhenPlayed`` gated by ``ATTACHED_HOST_NAMED`` so the trigger is not even
    collected on a different host.  The attach restriction is the engine's
    upgrade-target parser."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(2)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Mace Windu"),
    )


@card_ability("TWI", "168")
def _old_access_codes():
    """TWI_168 — Old Access Codes (Upgrade, Item, +1/+0, cost 1): "When Played: If
    an opponent controls more units than you, draw a card."

    A ``WhenPlayed`` gated by the new ``OPPONENT_MORE_UNITS_THAN_CONTROLLER`` atom —
    the mirror of ``CONTROLLER_MORE_UNITS_THAN_OPPONENT`` (Corrupt Politician
    SEC_79), not its negation: with equal counts neither holds.  Playing the upgrade
    does not change either side's unit count, so the comparison reads the same
    before and after the attach."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.OPPONENT_MORE_UNITS_THAN_CONTROLLER),
    )


@card_ability("TWI", "175")
def _strategic_analysis():
    """TWI_175 — Strategic Analysis (Event, Plan, cost 5): "Draw 3 cards."  """
    return EventAbility(effects=[DrawCards(3)])


def _cad_bane_capture(state, source_ci, target_id, event_ctx):
    """Adapter: Cad Bane captures up to 3 enemy non-leaders, total remaining HP ≤ 8."""
    from swu.engine.actions import push_capture_combined_hp
    push_capture_combined_hp(state, source_ci, captor_id=source_ci.instance_id,
                             budget=8, max_captures=3)
    return state


def _cad_bane_on_attack(state, source_ci, target_id, event_ctx):
    """Adapter: the defending player may rescue a card of theirs Cad Bane guards."""
    from swu.engine.actions import push_rescue_guarded
    push_rescue_guarded(state, source_ci, draw_on_rescue=2)
    return state


@card_ability("TWI", "187")
def _cad_bane():
    """TWI_187 — Cad Bane, Hostage Taker (Unit, Bounty Hunter/Underworld, 7/7):
      * "When Played: This unit captures up to 3 enemy non-leader units with a total
        of 8 or less remaining HP."
      * "On Attack: The defending player may rescue a card they own guarded by this
        unit.  If they do, draw 2 cards."

    The capture is ``push_capture_combined_hp`` (Dismantle the Conspiracy SEC_106)
    with Cad Bane himself as the pre-chosen captor, budget 8, plus the new
    ``max_captures`` cap for "up to 3" — each pick spends that unit's remaining HP
    against the budget, and the cap auto-finishes the decision.

    The On Attack is the new ``rescue_guarded`` decision, handed to the DEFENDING
    player (the say_no SOR_233 deciding-player shift).  It cannot collapse to an
    optimal-play default: taking the card back costs its owner two cards of tempo
    for Cad Bane's controller, who is the one who draws (the unattributed-subject
    convention — "draw 2 cards" means "you", the card's controller)."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_cad_bane_capture)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_cad_bane_on_attack)]),
    ]


# ── twi-set:09/10 — card advantage & disruption ──────────────────────────────

def _wartime_profiteering_effect(state, source_ci, target_id, event_ctx):
    """Look at N from the top (N = units defeated this phase), draw 1, bottom the
    rest in a random order — a ``deck_search`` whose WINDOW is the scaling part."""
    from swu.engine.actions import push_deck_search
    n = len(state.game_memory.defeated_controllers_this_round)
    if n <= 0:
        return state          # nothing defeated yet — look at nothing, draw nothing
    push_deck_search(state, source_ci, count=1, window=n, up_to=False,
                     eligible=lambda cd: True)
    return state


@card_ability("TWI", "188")
def _wartime_profiteering():
    """TWI_188 — Wartime Profiteering (Event): "Look at cards from the top of your
    deck equal to the number of units that were defeated this phase.  Draw 1 and put
    the others on the bottom of your deck in a random order."

    Exactly the ``deck_search`` shape (search a window, take a mandatory 1, bottom
    the rest in a seeded-random order) with every card eligible and the window read
    from ``defeated_controllers_this_round`` — a list carrying one entry per defeat,
    so its LENGTH is the count (it is round-scoped, and defeats outside the action
    phase are vanishingly rare — the ``units_attacked_this_round`` simplification).
    A phase with no defeats looks at nothing rather than pushing an empty search."""
    return EventAbility(effects=[CustomEffect(fn=_wartime_profiteering_effect)])


def _heroism_non_unit(cd) -> bool:
    """A Heroism card that is not a Unit (Aid from the Innocent TWI_201)."""
    from swu.cards.models import Unit
    if isinstance(cd, Unit):
        return False
    return "Heroism" in {a.name for a in (getattr(cd, "aspects", None) or ())}


def _aid_from_the_innocent_effect(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=2, window=10, up_to=False,
                     eligible=_heroism_non_unit,
                     disposition="discard_play_discount", play_discount=2)
    return state


@card_ability("TWI", "201")
def _aid_from_the_innocent():
    """TWI_201 — Aid from the Innocent (Event): "Search the top 10 cards of your deck
    for 2 Heroism non-unit cards and discard them.  (Put the other cards on the bottom
    of your deck in a random order.)  For this phase, you may play the discarded
    cards, and they each cost 2 resources less."

    The search is the ordinary ``deck_search`` (mandatory take, rest bottomed at
    random) under the new ``"discard_play_discount"`` disposition — the discounted
    sibling of Cobb Vanth SHD_115's free-replay flag: each chosen card is discarded
    and recorded in ``game_memory.discard_play_discount_this_phase`` at 2 off, which
    the discard-play enumeration turns into a real ``PlayFromDiscard`` for the rest of
    the phase.  Unlike the free permission (a Second Chance replay, hence Unit-only)
    this one covers every card type, because the cards it grants are non-units."""
    return EventAbility(effects=[CustomEffect(fn=_aid_from_the_innocent_effect)])


@card_ability("TWI", "208")
def _favorable_delegate():
    """TWI_208 — Favorable Delegate (Unit, Official/Republic, 1/5):
      * "When Played: Draw a card."
      * "When Defeated: Discard a card from your hand."

    Two plain triggers over the declarative primitives; the discard is the
    first-card convention (``DiscardFromHand(chooser="controller")``)."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[DiscardFromHand(count=1, chooser="controller")]),
    ]


@card_ability("TWI", "215")
def _geonosis_patrol_fighter():
    """TWI_215 — Geonosis Patrol Fighter (Unit, Fighter/Separatist/Vehicle, 3/2,
    Exploit 2): "When Played: You may return a non-leader unit that costs 3 or less
    to its owner's hand."

    Exploit is the keyword engine's; the residual is a plain optional
    ``ReturnToHand`` narrowed by ``cost_max`` — either player's unit is a legal
    target ("a non-leader unit", not "an enemy unit")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                         predicates=("non_leader",), cost_max=3))],
        optional=True,
    )


def _fives_effect(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=1,
        own_only=True,                                  # "YOUR discard pile"
        eligible=lambda cd: (isinstance(cd, Unit)
                             and "Clone" in (getattr(cd, "traits", ()) or ())),
        then_draw=1,                                    # "If you do, draw a card"
    )
    return state


@card_ability("TWI", "216")
def _fives():
    """TWI_216 — Fives, In Search of Truth (Unit, Clone/Republic/Trooper, 5/5,
    Saboteur): "When you play an event: You may put a Clone unit from your discard
    pile on the bottom of your deck.  If you do, draw a card."

    A ``WhenYouPlayCard(card_type="event")`` observer onto the ``bottom_from_discard``
    decision, narrowed to the controller's own Clone units, with the draw bound to an
    actual bottoming by the new ``then_draw`` knob — so declining inside the decision
    draws nothing, the "If you do" binding."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="event"),
        effects=[CustomEffect(fn=_fives_effect)],
        optional=True,
    )


@card_ability("TWI", "220")
def _shadowed_intentions():
    """TWI_220 — Shadowed Intentions (Upgrade, Innate): "Attached unit gains: 'This
    unit can't be captured, defeated, or returned to its owner's hand by enemy card
    abilities.'"

    The Chewbacca JTL_103 convention: one self-targeted ``ConstantAbility`` carrying
    a ``Protection`` marker, read (never routed) at the capture seam and the resolver
    DefeatUnit / ReturnToHand arms — ``_target_protected`` scans a target's attached
    upgrades, so an upgrade's self-protection is exactly "attached unit gains".  Only
    ENEMY abilities are blocked; combat damage/defeat never routes through those
    effects and so is unaffected (as printed)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_capture=True, from_defeat=True, from_return=True)],
    )


def _unmasking_the_conspiracy_effect(state, source_ci, target_id, event_ctx):
    from swu.engine.state import Zone
    from swu.engine.actions import (push_name_and_discard, note_hand_or_deck_discard,
                                    record_hand_discard)
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state          # can't pay the cost → no payoff ("If you do")
    ci = ps.hand.pop(0)
    ci.zone = Zone.DISCARD
    ps.discard.append(ci)
    note_hand_or_deck_discard(state, ci)
    record_hand_discard(state, ps.player_id)
    push_name_and_discard(state, source_ci)
    return state


@card_ability("TWI", "223")
def _unmasking_the_conspiracy():
    """TWI_223 — Unmasking the Conspiracy (Event, Gambit): "Discard a card from your
    hand.  If you do, look at an opponent's hand and discard a card from it."

    ONE CustomEffect so the cost and its payoff stay atomic — with an empty hand
    nothing is discarded and the opponent's hand is never seen.  The payoff is the
    existing ``name_and_discard`` decision, which already carries the opponent's hand
    identities to the controller and offers only names actually present: that IS
    "look at their hand and discard a card from it" (Chimaera SOR_185)."""
    return EventAbility(effects=[CustomEffect(fn=_unmasking_the_conspiracy_effect)])


def _aggrieved_parliamentarian_effect(state, source_ci, target_id, event_ctx):
    from swu.engine.state import Zone
    idx = state.player_index(source_ci.owner_id)
    opp = state.players[1 - idx]          # two-player: "an opponent" is THE opponent
    if not opp.discard:
        return state
    pile = list(opp.discard)
    rng = state.make_rng()
    rng.shuffle(pile)
    state.rng_state = rng.getstate()
    opp.discard.clear()
    for ci in pile:
        ci.zone = Zone.DECK
        ci.face_down = True
        ci.exhausted = False
        ci.damage = 0
        opp.deck.append(ci)               # bottom, in the shuffled order
    return state


@card_ability("TWI", "252")
def _aggrieved_parliamentarian():
    """TWI_252 — Aggrieved Parliamentarian (Unit, Official/Separatist, 2/2): "When
    Played: Choose an opponent.  They shuffle their discard pile and put it on the
    bottom of their deck."

    Two-player, so "choose an opponent" collapses to the opponent (no prompt).  The
    shuffle uses the seeded ``make_rng``/write-back convention — the global ``random``
    would fork the determinism oracle."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_aggrieved_parliamentarian_effect)])


# ── twi-set:11 — leaders: combat tricks, buffs & tempo ───────────────────────
#
# Seven leaders.  ``text`` is the UNDEPLOYED side and ``deploy_box`` the DEPLOYED
# one, so each registration is a list of specs flagged ``undeployed_only`` /
# ``deployed_only`` — except a clause the card prints on BOTH sides (Nala Se's
# aspect waiver), which carries neither flag.  A ConstantAbility / AuraGrantedAbility
# on a leader is deployed-only for free: both are collected by scans over cards in
# play, and an undeployed leader sits in base_zone.

_FRIENDLY_UNIT_DIED = ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE)
_PLAYED_EVENT = ConditionCheck(Condition.CONTROLLER_PLAYED_EVENT_THIS_PHASE)


@card_ability("TWI", "1")
def _nala_se():
    """TWI_1 — Nala Se, Clone Engineer (Leader, Kaminoan, 1/7):
      * both sides: "Ignore the aspect penalty on Clone units you play."
      * deployed: "Each friendly Clone unit gains: 'When Defeated: Heal 2 damage
        from your base.'"

    The waiver is the new controller-scoped ``IgnoreAspectPenaltyForPlays`` marker
    (the sibling of General Grievous TWI_34's host-scoped one), read at the play-cost
    seam; it carries no side flag because the card prints it on both, and the scan
    covers base_zone so the undeployed side counts.  The grant is the Gar Saxon SHD_1
    ``AuraGrantedAbility`` — a WhenDefeated inner ability resolving from the dying
    unit, so "your base" is that unit's controller's base."""
    return [
        IgnoreAspectPenaltyForPlays(card_type="unit", traits=("Clone",)),
        AuraGrantedAbility(
            target=TargetSpec(controller="friendly", kind="unit", traits=("Clone",)),
            ability=TriggerAbility(
                trigger=WhenDefeated(),
                effects=[Heal(2, TargetSpec(controller="friendly", kind="base"))],
            ),
        ),
    ]


@card_ability("TWI", "6")
def _wat_tambor():
    """TWI_6 — Wat Tambor, Techno Union Foreman (Leader, Official/Separatist, 3/6):
      * undeployed: "Action [Exhaust]: If a friendly unit was defeated this phase,
        give a unit +2/+2 for this phase."
      * deployed: "On Attack: If a friendly unit was defeated this phase, you may give
        another unit +2/+2 for this phase."

    Both sides are the same clause behind the new
    ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` gate (the friendly mirror of the ENEMY_
    atom): the condition gates availability on the undeployed side and trigger
    COLLECTION on the deployed one, so an unusable ability is never offered.  The
    deployed clause says "another", hence ``not_self``."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[ModifyStats(power=2, hp=2,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
            title="Give a unit +2/+2 for this phase",
            condition=_FRIENDLY_UNIT_DIED,
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=2, hp=2,
                                 target=TargetSpec(controller="any", kind="unit",
                                                   predicates=("not_self",)),
                                 duration=Duration.THIS_PHASE)],
            optional=True,
            condition=_FRIENDLY_UNIT_DIED,
            deployed_only=True,
        ),
    ]


@card_ability("TWI", "7")
def _captain_rex():
    """TWI_7 — Captain Rex, Fighting For His Brothers (Leader, Clone/Republic/Trooper,
    2/6):
      * undeployed: "Action [2 resources, Exhaust]: If a friendly unit attacked this
        phase, create a Clone Trooper token."
      * deployed: "When Deployed: Create a Clone Trooper token." + "Each other friendly
        Trooper unit gets +0/+1."

    The gate is the new ``CONTROLLER_ATTACKED_THIS_PHASE`` atom, which resolves each
    recorded attacker id through ``find_instance`` — so an attacker that has since died
    still satisfies "a friendly unit attacked this phase"."""
    return [
        ActivatedAbility(
            costs=[PayResources(2), ExhaustSelf()],
            effects=[CreateTokenUnit("Clone Trooper", count=1)],
            title="Create a Clone Trooper token",
            condition=ConditionCheck(Condition.CONTROLLER_ATTACKED_THIS_PHASE),
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CreateTokenUnit("Clone Trooper", count=1)],
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", traits=("Trooper",),
                              predicates=("not_self",)),
            effects=[StatBonus(power=0, hp=1)],
        ),
    ]


def _maul_granted_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, grant_keywords=["Overwhelm"])
    return state


@card_ability("TWI", "9")
def _maul_twi_9():
    """TWI_9 — Maul, A Rival in Darkness (Leader, Force/Underworld, 6/6, Overwhelm):
      * undeployed: "Action [Exhaust]: Attack with a unit.  It gains Overwhelm for
        this attack."
      * deployed: printed Overwhelm (the keyword engine's) + "Each other friendly unit
        gains Overwhelm."

    The action is the ``granted_attack`` seam with ``grant_keywords``; the anthem is a
    plain ``KeywordGrant`` ConstantAbility over the controller's other units."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_maul_granted_attack)],
            title="Attack with a unit — it gains Overwhelm",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            effects=[KeywordGrant("Overwhelm")],
        ),
    ]


def _anakin_twi_12_attack(state, source_ci, target_id, event_ctx):
    """Pay the printed "deal 2 damage to your base" cost, then grant the attack."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import push_granted_attack
    ps = state.player_by_id(source_ci.owner_id)
    if ps.base_instance is not None:
        _apply_deal_damage(state, ps.base_instance.instance_id, 2,
                           source_name=source_ci.card_def.display_name,
                           dealer_id=source_ci.owner_id,
                           source_id=source_ci.instance_id)
    push_granted_attack(state, source_ci, power_bonus=2, bonus_if_defender_unit=True)
    return state


@card_ability("TWI", "12")
def _anakin_skywalker_twi_12():
    """TWI_12 — Anakin Skywalker, What it Takes to Win (Leader, Force/Jedi/Republic,
    4/7):
      * undeployed: "Action [Exhaust, deal 2 damage to your base]: Attack with a unit.
        If it's attacking a unit, it gets +2/+0 for this attack."
      * deployed: printed Overwhelm + "This unit gets +1/+0 for every 5 damage on your
        base."

    The base-damage half of the cost lives inside the one CustomEffect (base damage is
    always payable, so binding it to the payoff there is exact — the Galactic Ambition
    SOR_235 convention); ``bonus_if_defender_unit`` is the "if it's attacking a unit"
    clause.  The self-buff is the new scaling ``StatBonus.count`` —
    ``controller_base_damage_per_5``, the stat sibling of Resolute TWI_151's scaling
    cost reduction."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_anakin_twi_12_attack)],
            title="Deal 2 to your base: attack with a unit (+2/+0 vs a unit)",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0, count="controller_base_damage_per_5")],
        ),
    ]


def _asajj_granted_attack(state, source_ci, target_id, event_ctx):
    """+1/+0 only if the controller played an event this phase — a conditional
    magnitude settled at resolution (the Zeb Orellios LAW_45 shape)."""
    from swu.engine.actions import push_granted_attack
    bonus = 1 if _PLAYED_EVENT.evaluate(state, source_ci) else 0
    push_granted_attack(state, source_ci, power_bonus=bonus)
    return state


@card_ability("TWI", "14")
def _asajj_ventress_twi_14():
    """TWI_14 — Asajj Ventress, Unparalleled Adversary (Leader, Force/Separatist/Sith,
    3/4):
      * undeployed: "Action [Exhaust]: Attack with a unit.  If you played an event this
        phase, it gets +1/+0 for this attack."
      * deployed: "On Attack: If you played an event this phase, this unit gets +1/+0
        for this attack and deals combat damage before the defender."

    The new ``CONTROLLER_PLAYED_EVENT_THIS_PHASE`` atom gates the deployed trigger's
    collection and decides the undeployed magnitude at resolution (the attack is
    granted either way — only the bonus is conditional).  "Deals combat damage before
    the defender" IS First Strike, granted to herself for this attack: the combat step
    reads it through ``has_keyword``, and On Attack triggers resolve before the damage
    step."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_asajj_granted_attack)],
            title="Attack with a unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                ModifyStats(power=1, hp=0, target=TargetSpec(fixed=SELF),
                            duration=Duration.THIS_ATTACK),
                GrantKeyword("First Strike", value=0, target=TargetSpec(fixed=SELF),
                             duration=Duration.THIS_ATTACK),
            ],
            condition=_PLAYED_EVENT,
            deployed_only=True,
        ),
    ]


def _jango_fett_twi_16_exhaust(state, source_ci, target_id, event_ctx):
    """Exhaust this (undeployed) leader; if you do, exhaust the damaged enemy unit."""
    res = state.find_instance(source_ci.instance_id)
    victim_id = event_ctx.get("defender_id")
    vres = state.find_instance(victim_id) if victim_id else None
    if res is None or vres is None or res[1].exhausted:
        return state          # can't pay the cost → no payoff ("If you do")
    res[1].exhausted = True
    vres[1].exhausted = True
    return state


@card_ability("TWI", "16")
def _jango_fett_twi_16():
    """TWI_16 — Jango Fett, Concealing the Conspiracy (Leader, Bounty Hunter/Underworld,
    3/7):
      * undeployed: "When a friendly unit deals damage to an enemy unit: You may exhaust
        this leader.  If you do, exhaust that enemy unit."
      * deployed: "When a friendly unit deals damage to an enemy unit: You may exhaust
        that unit."

    Both sides use the new ``WhenFriendlyUnitDealsCombatDamageToEnemyUnit`` observer —
    the group analogue of Rukh SOR_85's ``WhenDealsCombatDamageToUnit``, sharing its
    firing site and its ``defender_id`` key, so "that unit" is the ``DEFENDER``
    sentinel.  The undeployed side binds its self-exhaust cost to the payoff in ONE
    CustomEffect and is gated ``SOURCE_READY`` so an already-exhausted Jango is never
    offered a no-op."""
    return [
        TriggerAbility(
            trigger=WhenFriendlyUnitDealsCombatDamageToEnemyUnit(),
            effects=[CustomEffect(fn=_jango_fett_twi_16_exhaust)],
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenFriendlyUnitDealsCombatDamageToEnemyUnit(),
            effects=[ExhaustCard(TargetSpec(fixed=DEFENDER))],
            optional=True,
            deployed_only=True,
        ),
    ]

# ── twi-set:12 — combat tricks, buffs & tempo ────────────────────────────────

@card_ability("TWI", "19")
def _pau_city():
    """TWI_19 — Pau City (Base, 26 HP): "Each leader unit you control gets +0/+1."

    A BASE carrying a ConstantAbility.  The two constant-stat scans
    (``actions._constant_ability_power_bonus`` / ``_hp_bonus``) previously walked
    only the arenas; they now walk ``actions._constant_stat_sources``, which appends
    the player's base (and deliberately NOT the undeployed leader beside it, whose
    constants stay deployed-only).  "Leader unit" is the existing ``leader_unit``
    predicate — a Leader card in an arena, i.e. a deployed leader."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("leader_unit",)),
        effects=[StatBonus(power=0, hp=1)],
    )


@card_ability("TWI", "28")
def _petranaki_arena():
    """TWI_28 — Petranaki Arena (Base, 26 HP): "Each leader unit you control gets
    +1/+0."  The power twin of Pau City TWI_19."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("leader_unit",)),
        effects=[StatBonus(power=1, hp=0)],
    )


@card_ability("TWI", "33")
def _calculating_magnaguard():
    """TWI_33 — Calculating MagnaGuard (Unit, Droid/Separatist, 3/4): "When
    Played/When a friendly unit is defeated: This unit gains Sentinel for this
    phase."

    One clause with two firing conditions ⇒ two TriggerAbilities sharing the same
    self-targeted this-phase ``GrantKeyword``.  The keyword sanitiser's rule 3
    (implemented triggered self-grant) strips the printed Sentinel the API tags on
    the card, so the ability — not an always-on bar — owns it.  Mandatory: "gains
    Sentinel" is not a "you may"."""
    def _sentinel():
        return GrantKeyword("Sentinel", value=0, target=TargetSpec(fixed=SELF),
                            duration=Duration.THIS_PHASE)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[_sentinel()]),
        TriggerAbility(
            trigger=WhenUnitDefeated(filter=TargetSpec(controller="friendly")),
            effects=[_sentinel()]),
    ]


@card_ability("TWI", "42")
def _barriss_offee():
    """TWI_42 — Barriss Offee (Unit, Force/Jedi/Republic, 1/1): "Each friendly unit
    that was healed this phase gets +1/+0."

    A group aura keyed on the new ``healed_this_phase`` predicate, backed by
    ``game_memory.units_healed_this_phase`` (fed at the heal chokepoints by
    ``actions.note_unit_healed``, and only when damage was actually removed).
    Barriss buffs herself too if she was healed — "each friendly unit"."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("healed_this_phase",)),
        effects=[StatBonus(power=1, hp=0)],
    )


@card_ability("TWI", "43")
def _outspoken_representative():
    """TWI_43 — Outspoken Representative (Unit, Official/Republic, 0/3): "While you
    control another Republic unit, this unit gains Sentinel.  When Defeated: Create
    a Clone Trooper token."

    The conditional self-grant is the Protector of the Throne SHD_247 pattern
    (``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` — "another"), whose printed Sentinel the
    sanitiser's rule 2 strips; the When Defeated is a plain ``CreateTokenUnit``."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel", 0)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                     "Republic"),
        ),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[CreateTokenUnit("Clone Trooper", count=1)]),
    ]


@card_ability("TWI", "45")
def _41st_elite_corps():
    """TWI_45 — 41st Elite Corps (Unit, Clone/Republic/Trooper, 3/3): "Coordinate —
    This unit gets +0/+3."  The plain Coordinate stat buff (Echo TWI_90's shape)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=0, hp=3)],
        condition=_COORDINATE,
    )


def _luminara_heal_base(state, source_ci, target_id, event_ctx):
    """Luminara Unduli TWI_50 When Played: "Choose a base.  Heal 1 damage from it
    for each unit you control."

    The magnitude is decided from board state at resolution (the Zeb Orellios
    LAW_45 conditional-magnitude shape), so a chosen-target CustomEffect rather
    than a flat ``Heal``.  Routed through ``resolver._apply_heal`` so the
    bases-can't-be-healed lock (Wolffe SOR_160) still applies.  Luminara is already
    in her arena when this resolves, so she counts herself."""
    from swu.abilities.resolver import _apply_heal
    if not target_id:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    units = len(ps.ground_arena) + len(ps.space_arena)
    if units <= 0:
        return state
    return _apply_heal(state, source_ci, target_id, units)


@card_ability("TWI", "50")
def _luminara_unduli():
    """TWI_50 — Luminara Unduli (Unit, Force/Jedi/Republic, 4/9): "Coordinate — Grit.
    When Played: Choose a base.  Heal 1 damage from it for each unit you control."

    Grit is the conditional keyword self-grant (sanitiser rule 2 strips the printed
    copy, so it only applies while you control 3+ units); the heal is a targeted
    CustomEffect whose magnitude is the unit count at resolution."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Grit", 0)],
            condition=_COORDINATE,
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_luminara_heal_base,
                                  target=TargetSpec(kind="base"))],
        ),
    ]

# ── twi-set:13 — combat tricks, buffs & tempo ────────────────────────────────

@card_ability("TWI", "51")
def _for_the_republic():
    """TWI_51 — For The Republic (Upgrade, Republic, cost 3): "If you control 3 or
    more Republic units, this upgrade costs 2 resources less to play.  Attached unit
    gains: 'Coordinate — Restore 2.'"

    The discount is a plain ``CostReduction`` gated by ``CONTROLLER_N_PLUS_TRAIT_UNITS``
    (Petition the Senate TWI_100's atom), read at the play-cost seam so it moves both
    affordability and the resources exhausted.  The grant is the Constructed
    Lightsaber LOF_261 shape — a SELF-targeted ConstantAbility ``KeywordGrant`` on the
    UPGRADE, which the keyword layer's attached-upgrade scan confers on the host,
    evaluating the condition (here Coordinate) against that host.  So the host has
    Restore 2 exactly while its controller has 3+ units."""
    return [
        CostReduction(
            amount=2,
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_TRAIT_UNITS,
                                     ("Republic", 3)),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Restore", 2)],
            condition=_COORDINATE,
        ),
    ]


@card_ability("TWI", "54")
def _duchesss_champion():
    """TWI_54 — Duchess's Champion (Unit, Mandalorian, 1/8): "While an opponent
    controls 3 or more units, this unit gains Sentinel."

    The conditional self-grant (sanitiser rule 2 strips the printed Sentinel) on the
    new ``OPPONENT_N_PLUS_UNITS`` atom — the enemy-side mirror of the Coordinate
    condition, same both-arenas count basis."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel", 0)],
        condition=ConditionCheck(Condition.OPPONENT_N_PLUS_UNITS, 3),
    )


@card_ability("TWI", "56")
def _compassionate_senator():
    """TWI_56 — Compassionate Senator (Unit, Official/Republic, 0/4): "Action [2
    resources, Exhaust]: Heal 2 damage from a unit or base."

    A plain two-cost activated ability.  The target is narrowed to a ``damaged``
    unit-or-base so the resources and the exhaust are never spent on a no-op (the
    Obi-Wan TWI_3 / Ozzel SOR_129 "don't offer a no-op" reading, expressed through
    the target)."""
    return ActivatedAbility(
        costs=[PayResources(2), ExhaustSelf()],
        effects=[Heal(2, TargetSpec(controller="any", kind="unit_or_base",
                                    predicates=("damaged",)))],
        title="Heal 2 damage from a unit or base",
    )


@card_ability("TWI", "58")
def _padawan_starfighter():
    """TWI_58 — Padawan Starfighter (Unit, Jedi/Republic/Vehicle/Fighter, 1/3):
    "While you control a Force unit or a Force upgrade, this unit gets +1/+1."

    A conditional SELF stat buff on the new ``CONTROLLER_HAS_TRAIT_CARD_IN_PLAY``
    atom — ``CONTROLLER_HAS_TRAIT_UNIT`` widened to each arena unit's attached
    upgrades, which is exactly the card's "or a Force upgrade"."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_CARD_IN_PLAY, "Force"),
    )


@card_ability("TWI", "62")
def _daughter_of_dathomir():
    """TWI_62 — Daughter of Dathomir (Unit, Force/Night, 3/5): "While this unit is
    undamaged, it gains Restore 2."

    The conditional keyword self-grant on the existing ``SOURCE_UNDAMAGED`` atom;
    the sanitiser strips the printed Restore so the ability owns it, and the Restore
    keyword engine does the rest (heal your base on attack)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", 2)],
        condition=ConditionCheck(Condition.SOURCE_UNDAMAGED),
    )


@card_ability("TWI", "67")
def _the_zillo_beast():
    """TWI_67 — The Zillo Beast (Unit, Creature, 10/10): "When Played: Give each
    enemy ground unit −5/−0 for this phase.  When the regroup phase starts: Heal 5
    damage from this unit."

    Both clauses are pure reuse: the debuff is an ``EACH_ENEMY`` this-phase
    ``ModifyStats`` narrowed by ``arena="ground"`` (HK-87 LOF_235's mass shape), and
    the regroup heal is a ``PhaseStartTrigger("regroup")`` with a SELF ``Heal``
    (Contracted Hunter JTL_216's hook)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ModifyStats(power=-5, hp=0,
                                 target=TargetSpec(fixed=EACH_ENEMY, kind="unit",
                                                   arena="ground"),
                                 duration=Duration.THIS_PHASE)],
        ),
        TriggerAbility(
            trigger=PhaseStartTrigger(phase="regroup"),
            effects=[Heal(5, TargetSpec(fixed=SELF))],
        ),
    ]


def _perilous_position_exhaust(state, source_ci, target_id, event_ctx):
    """Perilous Position TWI_70 When Played: exhaust the attached host (its id is
    threaded through the upgrade play context) — the Frozen in Carbonite SHD_193
    ``event_ctx["attached_to_id"]`` shape."""
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        result = state.find_instance(host_id)
        if result is not None:
            _, host = result
            host.exhausted = True
    return state


@card_ability("TWI", "70")
def _perilous_position():
    """TWI_70 — Perilous Position (Upgrade, Condition, cost 3): "When Played: Exhaust
    attached unit."  A statless Condition upgrade whose only text is the one-shot
    exhaust; mandatory, so no ``optional``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_perilous_position_exhaust)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# twi-set:14 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("TWI", "71")
def _unshakeable_will():
    """TWI_71 — Unshakeable Will (Upgrade, Innate, cost 4): "Attached unit gains
    Sentinel."

    The upgrade-SELF ``KeywordGrant`` shape (Grievous's Wheel Bike TWI_236 →
    Overwhelm): the keyword layer's attached-upgrade scan reads a
    ``ConstantAbility(target=SELF, KeywordGrant)`` on each of a host's upgrades and
    confers the keyword on the HOST, which is the only path an upgrade's keyword
    reaches its unit (an upgrade lives in ``attached_upgrades``, never an arena, so
    the in-play ConstantAbility scan never sees it).  The printed Sentinel on the
    upgrade's own bar never transfers — ``has_keyword`` reads only the host's
    printed keywords — so this registration is what makes the card work."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
    )


@card_ability("TWI", "73")
def _grievous_reassembly():
    """TWI_73 — Grievous Reassembly (Event, Supply, cost 2): "Heal 3 damage from a
    unit.  Create a Battle Droid token."

    Two plain effects, the TARGETED one first (the Mandalorian SHD_18 ordering wart
    — a leading fixed effect would make the resolver skip the prompt).  The heal is
    unit-only, so the Wolffe SOR_160 bases-can't-heal lock is not in play; the token
    reuses the Separatist ``CreateTokenUnit("Battle Droid")`` supply
    (general-grievous:05)."""
    return EventAbility(effects=[
        Heal(3, TargetSpec(controller="any", kind="unit")),
        CreateTokenUnit("Battle Droid", count=1),
    ])


def _guarding_the_way(state, source_ci, target_id, event_ctx):
    """Guarding the Way TWI_74: the chosen unit gains Sentinel for this phase and,
    if the controller has the initiative, ALSO +2/+2 for this phase.

    One ``CustomEffect.target`` rather than two effects, because both clauses act on
    the SAME chosen unit — the conditional-rider shape (Zeb Orellios LAW_45 /
    General Rieekan SHD_103).  Two separate targeted effects would prompt twice and
    could land on different units.  Initiative is fixed for the round, so reading it
    at resolution is the same as reading it when the buff applies.

    Both sub-effects carry a bare ``TargetSpec()`` (NOT ``fixed=SELF``, which would
    make ``execute_effect`` resolve them onto the event card itself and ignore the
    chosen unit)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import execute_effect
    state = execute_effect(
        state,
        GrantKeyword("Sentinel", value=0, target=TargetSpec(),
                     duration=Duration.THIS_PHASE),
        source_ci, target_id, event_ctx)
    if state.initiative_holder == state.player_index(source_ci.owner_id):
        state = execute_effect(
            state,
            ModifyStats(power=2, hp=2, target=TargetSpec(),
                        duration=Duration.THIS_PHASE),
            source_ci, target_id, event_ctx)
    return state


@card_ability("TWI", "74")
def _guarding_the_way_card():
    """TWI_74 — Guarding the Way (Event, Tactic, cost 2): "Give a unit Sentinel for
    this phase.  If you have the initiative, also give that unit +2/+2 for this
    phase." """
    return EventAbility(effects=[
        CustomEffect(fn=_guarding_the_way,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("TWI", "81")
def _droid_commando():
    """TWI_81 — Droid Commando (Unit, Droid/Separatist/Trooper, 4/3): "While you
    control another Separatist unit, this unit gains Ambush."

    The conditional self-grant (Gamorrean Retainer SHD_112 / Protector SHD_247), on
    the existing ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` atom; the keyword sanitiser
    strips the mis-tagged printed Ambush so the condition owns it.  The Ambush
    listener reads ``has_keyword`` when the unit is already in its arena, and the
    condition excludes the source itself, so a Commando entering play beside another
    Separatist gets its Ambush attack for free."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Ambush", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Separatist"),
    )


def _kalani_on_attack(state, source_ci, target_id, event_ctx):
    """Kalani TWI_85 On Attack: choose 1 other unit — or up to 2 if the controller
    has the initiative — and give each +2/+2 for this phase.

    A thin adapter onto ``push_select_token`` in its BUFF mode (``token_type=None``
    plus ``power_bonus``/``hp_bonus``): the same select-up-to-N flow as Medal
    Ceremony SOR_245, with a stat modifier as the payoff instead of a token.  The
    "you may" is the decision's always-legal ``FinishSelectToken``, so the trigger
    itself is mandatory (an optional trigger would prompt twice).  ``not_self`` =
    "another unit"; ``controller="any"`` because the card does not say friendly."""
    from swu.engine.actions import push_select_token
    has_init = state.initiative_holder == state.player_index(source_ci.owner_id)
    push_select_token(
        state, source_ci,
        token_type=None, power_bonus=2, hp_bonus=2, duration="this_phase",
        max_targets=2 if has_init else 1,
        controller="any", kind="unit", predicates=["not_self"],
    )
    return state


@card_ability("TWI", "85")
def _kalani():
    """TWI_85 — Kalani (Unit, Droid/Separatist, 5/7): "On Attack: You may choose
    another unit.  If you have the initiative, you may choose up to 2 other units
    instead.  Give each chosen unit +2/+2 for this phase." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_kalani_on_attack)],
    )


@card_ability("TWI", "98")
def _republic_defense_carrier():
    """TWI_98 — Republic Defense Carrier (Unit, Capital Ship/Republic/Vehicle, 6/7,
    Sentinel, cost 11): "This unit costs 1 resource less to play for each unit
    controlled by the opponent who controls the most units."

    A ``CostReduction`` carrying the new ``per_max_opponent_units`` scaling flag —
    the opponent-side sibling of Resolute TWI_151's ``per_controller_base_damage``.
    With two players "the opponent who controls the most units" is simply the one
    opponent, counted across both arenas (deployed leaders included, the
    ``CONTROLLER_N_PLUS_UNITS`` basis).  The play path floors the cost at 0.  The
    printed Sentinel is engine-implemented and needs no registration."""
    return CostReduction(amount=1, per_max_opponent_units=True)


def _steadfast_senator_attack(state, source_ci, target_id, event_ctx):
    """Steadfast Senator TWI_105's Action: attack with a unit, +2/+0 for that
    attack — the thin ``push_granted_attack`` adapter (Surprise Strike SOR_220).
    Mandatory-if-able: the cost is already paid, so a spare grant fizzles via
    ``DeclineGrantedAttack`` only when no unit can attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0)
    return state


@card_ability("TWI", "105")
def _steadfast_senator():
    """TWI_105 — Steadfast Senator (Unit, Official/Republic, 0/4): "Action [2
    resources, Exhaust]: Attack with a unit.  It gets +2/+0 for this attack."

    An ``ActivatedAbility`` with the two-cost list (``PayResources(2)`` +
    ``ExhaustSelf()``) whose effect is the granted-attack adapter.  A 0-power body
    that turns resources into attacks — the attacker may be any friendly unit,
    including the Senator herself (she is not excluded by the card)."""
    return ActivatedAbility(
        costs=[PayResources(2), ExhaustSelf()],
        effects=[CustomEffect(fn=_steadfast_senator_attack)],
        title="Action [2 resources, Exhaust]: Attack with a unit (+2/+0)",
    )


# ── twi-set:15 — Combat tricks, buffs & tempo ────────────────────────────────
# Two small additive seams, both widenings of existing machinery: the "Attach to
# a token unit" clause now parses into the already-known ``token_unit`` predicate
# (``actions._upgrade_target_spec``), and ``StatBonus.count`` gained a
# ``controller_trait_units_<Trait>`` source.  The rest is reuse.


@card_ability("TWI", "119")
def _nameless_valor():
    """TWI_119 — Nameless Valor (Upgrade, Learned, cost 1): "Attach to a token
    unit.  Attached unit gains Overwhelm."

    The upgrade-SELF ``ConstantAbility(KeywordGrant)`` (Grievous's Wheel Bike
    TWI_236 / Unshakeable Will TWI_71) — the ONLY path by which an upgrade confers
    a keyword on its host, since an upgrade lives in ``attached_upgrades`` rather
    than an arena (so the in-play constant scan never sees it) and its own printed
    keyword bar never transfers.  The "Attach to a token unit" restriction is
    enforced by the generic ``_upgrade_target_spec`` parser, which now maps that
    clause onto the existing ``token_unit`` predicate — so it holds at every
    attachment site (legal_actions, the apply guard, upgrade relocation)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Overwhelm", value=0)],
    )


def _strategic_acumen_play(state, source_ci, target_id, event_ctx):
    """Strategic Acumen's granted Action: play a unit from hand at 1 resource off
    — the thin ``push_play_from_hand`` adapter (Admiral Ozzel SOR_129).  A granted
    activated ability resolves FROM THE HOST, so ``source_ci`` is the attached
    unit and the played unit lands under its controller."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=1)
    return state


@card_ability("TWI", "120")
def _strategic_acumen():
    """TWI_120 — Strategic Acumen (Upgrade, Learned, cost 1): "Attached unit
    gains: 'Action [Exhaust]: Play a unit from your hand.  It costs 1 resource
    less.'"

    A ``GrantedAbility`` wrapping an ``ActivatedAbility`` (Heroic Resolve
    SHD_155): the trigger collector skips it, and the attached-upgrade scan in
    ``legal_actions`` surfaces the Action addressed by the UPGRADE's instance_id
    with ``ExhaustSelf`` exhausting the HOST.  Gated by
    ``CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT`` (param=1, Han Solo SHD_13) so the
    host's exhaust is never spent when nothing in hand could be played."""
    return GrantedAbility(ability=ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_strategic_acumen_play)],
        condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT, 1),
        title="Action [Exhaust]: Play a unit from your hand (1 resource less)",
    ))


@card_ability("TWI", "122")
def _squad_support():
    """TWI_122 — Squad Support (Upgrade, Learned, cost 3): "Attach to a non-leader
    unit.  Attached unit gains: 'This unit gets +1/+1 for each Trooper unit you
    control.'"

    An upgrade-SELF scaling ``StatBonus``, conferred by the
    ``_upgrade_self_stat_bonus`` scan (IG-88 JTL_141) — the stat-layer twin of the
    keyword scan above.  The new ``count="controller_trait_units_Trooper"`` source
    counts the controller's Trooper units across both arenas over EFFECTIVE traits
    (a granted trait counts); "each Trooper unit you control" is not "each other",
    so a Trooper host counts itself.  The non-leader attachment restriction is
    parsed for free by ``_upgrade_target_spec``."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=1, count="controller_trait_units_Trooper")],
    )


def _in_defense_of_kamino(state, source_ci, target_id, event_ctx):
    """Register the spent event as a PHASE-SCOPED aura source so its
    ``AuraGrantedAbility`` (spec index 1) keeps granting the When Defeated clause
    from the discard for the rest of the phase — the Pyrrhic Assault TWI_103 seam.
    ``game_memory.phase_aura_sources`` is cleared at the phase rollover, which is
    the whole of "for this phase"."""
    gm = state.game_memory
    if source_ci.instance_id not in gm.phase_aura_sources:
        gm.phase_aura_sources.append(source_ci.instance_id)
    return state


@card_ability("TWI", "129")
def _in_defense_of_kamino_card():
    """TWI_129 — In Defense of Kamino (Event, Republic, cost 4): "For this phase,
    each friendly Republic unit gains Restore 2 and: 'When Defeated: Create a
    Clone Trooper token.'"

    Two clauses, two mechanisms.  The KEYWORD half is a plain
    ``GrantKeyword("Restore", 2, …, THIS_PHASE)`` over a fixed ``EACH_FRIENDLY``
    target narrowed by ``traits=("Republic",)`` — no prompt, auto-applied to every
    match and read passively by ``has_keyword`` (Encouraging Leadership TWI_126).
    The ABILITY half is the Pyrrhic Assault TWI_103 phase-scoped
    ``AuraGrantedAbility``: the event is already in the discard by the time a unit
    dies, so ``phase_aura_sources`` keeps it addressable as an aura source, and
    the granted trigger resolves from the DYING unit — which is what puts the
    Clone Trooper under the right player's control.

    A unit that becomes friendly-Republic later in the phase gains the When
    Defeated clause (the aura is re-evaluated at each defeat) but not the Restore,
    which was applied as a modifier when the event resolved.  That asymmetry is
    inherent to the two mechanisms and matches the TWI_103 precedent.

    Both event effects are untargeted, so their order is free."""
    return [
        EventAbility(effects=[
            GrantKeyword(
                "Restore", 2,
                TargetSpec(controller="friendly", kind="unit",
                           traits=("Republic",), fixed=EACH_FRIENDLY),
                Duration.THIS_PHASE),
            CustomEffect(fn=_in_defense_of_kamino),
        ]),
        AuraGrantedAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Republic",)),
            ability=TriggerAbility(
                trigger=WhenDefeated(),
                effects=[CreateTokenUnit("Clone Trooper", count=1)],
            ),
        ),
    ]


@card_ability("TWI", "130")
def _bo_katan_kryze_twi():
    """TWI_130 — Bo-Katan Kryze (Unit, Mandalorian/Trooper, 2/3, cost 2):
    "While you control another Mandalorian unit, this unit gains Overwhelm and
    Saboteur.  While you control another Trooper unit, this unit gets +1/+0."

    Two conditional SELF ``ConstantAbility`` specs on the same
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` atom with different params (the Scimitar
    LOF_233 / Clan Challengers SHD_169 shape).  Bo-Katan is herself both a
    Mandalorian and a Trooper, and the atom excludes the source, so "another" is
    exact.  The keyword sanitiser strips her printed Overwhelm/Saboteur because
    they are registered here as conditional self-grants — without that she would
    have them unconditionally."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Overwhelm", value=0),
                     KeywordGrant("Saboteur", value=0)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                     "Mandalorian"),
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=1, hp=0)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                     "Trooper"),
        ),
    ]


@card_ability("TWI", "134")
def _asajj_ventress_twi134():
    """TWI_134 — Asajj Ventress (Unit, Force/Separatist/Sith, 2/4, cost 4,
    Exploit 2): "On Attack: If you've attacked with another Separatist unit this
    phase, this unit gets +3/+0 for this phase."

    Exploit is the keyword engine.  The residual is a plain ``OnAttack``
    ``ModifyStats`` on SELF gated by ``CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE``
    (param="Separatist") — the atom written for Bo-Katan Kryze SHD_12, which
    excludes the source, so Asajj's own attack (already ledgered by the time this
    fires) never satisfies "another".  A MANDATORY trigger: the text has no "you
    may", and the condition gates collection so nothing is offered when it would
    do nothing."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=3, hp=0, target=TargetSpec(fixed=SELF),
                             duration=Duration.THIS_PHASE)],
        condition=ConditionCheck(
            Condition.CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE, "Separatist"),
    )


@card_ability("TWI", "137")
def _savage_opress_twi137():
    """TWI_137 — Savage Opress (Unit, Force/Night/Underworld, 7/7, cost 7): "When
    Played: If you control fewer units (including this one) than an opponent, ready
    this unit."

    A ``WhenPlayed`` ``ReadyCard(SELF)`` gated by
    ``OPPONENT_MORE_UNITS_THAN_CONTROLLER`` (Old Access Codes TWI_168) — the
    MIRROR of its sibling, not its negation, so equal counts do NOT ready him,
    which is exactly "fewer".  A When Played trigger fires with the unit already in
    its arena, so "including this one" falls out for free.  Units enter play
    exhausted, so this is a real tempo swing: a 7/7 that can attack immediately
    when you are behind on board."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
        condition=ConditionCheck(Condition.OPPONENT_MORE_UNITS_THAN_CONTROLLER),
    )



# ── twi-set:16 — Combat tricks, buffs & tempo ────────────────────────────────
#
# Seven cards, five of them pure reuse.  Two additive widenings of machinery that
# already existed, both keyed on something the decision already knows:
#
#   * ``push_granted_attack(bonus_per_defender_damage=1)`` — the attacker's bonus
#     scales on the DEFENDER's damage (TWI_139), read before combat deals anything.
#   * ``WhenEnemyAttacksYourBase(arena="ground")`` — the SHD_241 observer narrowed
#     to the attacker's arena (TWI_166).
#   * ``push_select_token(shared_trait=True)`` — the select-up-to-N decision keeps
#     a running trait intersection across picks (TWI_153).


def _corner_the_prey(state, source_ci, target_id, event_ctx):
    """Attack with a unit; it gets +1/+0 for each damage on the defender."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, bonus_per_defender_damage=1)
    return state


@card_ability("TWI", "139")
def _corner_the_prey_card():
    """TWI_139 — Corner the Prey (Event, Villainy/Aggression, cost 1): "Attack with
    a unit.  It gets +1/+0 for this attack for each damage on the defender at the
    start of this attack."

    The thin-CustomEffect-adapter shape (Palpatine SOR_135) over the existing
    ``granted_attack`` decision.  What is new is the bonus BASIS: every prior field
    scales on the attacker (``bonus_trait``) or gates on the defender's kind/arena
    (``bonus_if_defender_unit`` / ``bonus_if_defender_ground``); this one reads the
    chosen defender's damage.  It is computed in AttackWithUnit *before* the combat
    pipeline runs, which is exactly "at the start of this attack" — a defender that
    takes damage during the attack does not raise the bonus mid-combat.  A base
    defender counts its own damage: "the defender" is whatever the attack is aimed
    at, and a 1-cost trick pointed at a chipped base is a real (if fringe) line."""
    return EventAbility(effects=[CustomEffect(fn=_corner_the_prey)])


@card_ability("TWI", "143")
def _jyn_erso_twi143():
    """TWI_143 — Jyn Erso (Unit, Aggression/Heroism, Rebel, 3/2, cost 2): "While an
    enemy unit has been defeated this phase, this unit gets +1/+0 and gains
    Saboteur."

    One ``ConstantAbility`` carrying BOTH payoffs under one condition — the stat
    scan reads the ``StatBonus``, ``has_keyword`` reads the ``KeywordGrant``, so a
    single spec serves both (unlike Bo-Katan TWI_130, whose two clauses have
    DIFFERENT conditions and therefore need two specs).  ``Saboteur`` is printed on
    the card and mistagged as always-on; registering it as a conditional self-grant
    makes the keyword sanitiser strip the printed copy (Hunting Nexu SHD_168 /
    Protector SHD_247), so a 2-drop does not get free evasion on turn one."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=0), KeywordGrant("Saboteur", value=0)],
        condition=ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE),
    )


def _bold_resistance(state, source_ci, target_id, event_ctx):
    """Choose up to 3 units sharing a trait; each gets +2/+0 for this phase."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type=None, max_targets=3,
                      controller="any", kind="unit",
                      power_bonus=2, hp_bonus=0, duration="this_phase",
                      shared_trait=True)
    return state


@card_ability("TWI", "153")
def _bold_resistance_card():
    """TWI_153 — Bold Resistance (Event, Aggression/Heroism, cost 3): "Choose up to
    3 units that share the same Trait.  Each of those units gets +2/+0 for this
    phase."

    The ``select_token`` BUFF mode (Kalani TWI_85 — ``token_type=None``, the payoff
    a stat modifier) plus the new ``shared_trait`` narrowing: after each pick the
    candidate list keeps only units still sharing a trait with EVERY unit chosen so
    far (a running intersection of effective traits, so a TraitGrant counts).  The
    first pick is unconstrained, which is right — "up to 3" permits a selection of
    one, and the intersection only has something to say from the second pick on.

    ``controller="any"`` is the printed text: it says "units", not "friendly units".
    Buffing an enemy is legal and pointless, which is how the card reads."""
    return EventAbility(effects=[CustomEffect(fn=_bold_resistance)])


@card_ability("TWI", "163")
def _relentless_rocket_droid():
    """TWI_163 — Relentless Rocket Droid (Unit, Aggression, Droid/Separatist/
    Trooper, 3/5, cost 4): "While you control another Trooper unit, this unit gets
    +2/+0."

    Pure reuse: the ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` clause of Bo-Katan TWI_130.
    The droid is itself a Trooper, and "another" excludes the source, so it needs a
    partner — a 3/5 body that turns into a 5/5 the moment the swarm shows up."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Trooper"),
    )


@card_ability("TWI", "166")
def _aurra_sing_twi166():
    """TWI_166 — Aurra Sing (Unit, Aggression, Bounty Hunter/Underworld, 7/6, cost
    7, Overwhelm): "When an enemy ground unit attacks your base: Ready this unit."

    The ``WhenEnemyAttacksYourBase`` observer (Kragan Gorr SHD_241) narrowed by the
    new ``arena`` filter — a space attacker running the base past her does not ready
    her.  Overwhelm is a printed engine keyword and needs no registration.

    Mandatory and self-targeted, so it needs no prompt; the ready lands at attack
    DECLARATION, before damage, which is the point — she punishes a base race by
    threatening a 7-power counter-swing on the same turn."""
    return TriggerAbility(
        trigger=WhenEnemyAttacksYourBase(arena="ground"),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
    )


@card_ability("TWI", "169")
def _clone_cohort():
    """TWI_169 — Clone Cohort (Upgrade, Aggression, Supply, cost 2): "Attached unit
    gains Raid 2 and: 'When Defeated: Create a Clone Trooper token.'"

    Both halves of an upgrade's conferral, one spec each — the two (and only two)
    paths by which an upgrade gives its host anything:

      * ``ConstantAbility(target=SELF, KeywordGrant("Raid", 2))`` — read by
        ``has_keyword``/``keyword_value``'s attached-upgrade walk (Grievous's Wheel
        Bike TWI_236).  The upgrade's own printed ``Raid`` bar never transfers, so
        this registration is what makes the card work.
      * ``GrantedAbility(TriggerAbility(WhenDefeated, CreateTokenUnit))`` — the
        Armed to the Teeth SHD_175 pattern, matched and resolved with the HOST as
        source, and still collected from a defeated host's just-detached upgrades,
        which is the only reason the replacement token ever appears."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Raid", value=2)],
        ),
        GrantedAbility(ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CreateTokenUnit("Clone Trooper", count=1)],
        )),
    ]


def _grim_resolve(state, source_ci, target_id, event_ctx):
    """Attack with a non-leader unit; it gains Grit for that attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci,
                        attacker_predicates=["non_leader"],
                        grant_keywords=["Grit"])
    return state


@card_ability("TWI", "172")
def _grim_resolve_card():
    """TWI_172 — Grim Resolve (Event, Aggression, Tactic, cost 2): "Attack with a
    non-leader unit.  It gains Grit for this attack."

    Pure reuse on both axes: ``attacker_predicates=["non_leader"]`` (Desperate
    Attack SHD_179's predicate filter) and ``grant_keywords`` (Shoot First's
    this-attack keyword modifier).  Grit is a live engine keyword — ``compute_power``
    adds +1 per damage on the unit while it has it — so granting it for the attack
    is the whole card: it turns a nearly-dead unit into a real threat."""
    return EventAbility(effects=[CustomEffect(fn=_grim_resolve)])



# ── twi-set:17 — Combat tricks, buffs & tempo ────────────────────────────────
#
# Resources are FUNGIBLE — one exhausted resource is worth exactly as much as any
# other — so "exhaust/ready a resource" is auto-picked rather than prompted (the
# K-2SO SOR_145 convention).  Three cards here lean on that.


def _planetary_invasion(state, source_ci, target_id, event_ctx):
    """Ready up to 3 units; each gets +1/+0 and Overwhelm for this phase."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type=None, max_targets=3,
                      controller="any", kind="unit",
                      power_bonus=1, hp_bonus=0, duration="this_phase",
                      ready=True, grant_keywords=["Overwhelm"])
    return state


@card_ability("TWI", "178")
def _planetary_invasion_card():
    """TWI_178 — Planetary Invasion (Event, Aggression, Plan/Separatist, cost 12,
    Exploit 3): "Ready up to 3 units.  Each of those units gets +1/+0 and gains
    Overwhelm for this phase."

    The ``select_token`` decision again (Bold Resistance TWI_153 next door), now
    with the ``ready`` + ``grant_keywords`` payoffs stacked on the buff — one
    select-up-to-N flow, three things applied per pick.  Exploit 3 is a printed
    engine keyword and handles its own cost reduction; a 12-cost event that is
    really a 6-cost alpha strike is the whole design, and this half is the payoff:
    three units attack a second time, bigger, with excess damage going upstairs."""
    return EventAbility(effects=[CustomEffect(fn=_planetary_invasion)])


@card_ability("TWI", "183")
def _rush_clovis():
    """TWI_183 — Rush Clovis (Unit, Cunning/Villainy, Official/Separatist, 3/5, cost 4,
    Raid 2): "On Attack: If the defending player controls no ready resources,
    create a Battle Droid token."

    A mandatory ``OnAttack`` gated by the new ``OPPONENT_NO_READY_RESOURCES`` atom
    — in two-player the defending player IS the source controller's opponent, so
    the condition needs no attack context and gates trigger COLLECTION (nothing is
    offered when it would do nothing).  Raid 2 is printed and engine-handled.

    Reading the board rather than the attack means it also answers the natural
    question "what if he attacks the base?" the same way the card does: the
    defending player is still the opponent, so a tapped-out opponent still pays."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
        condition=ConditionCheck(Condition.OPPONENT_NO_READY_RESOURCES),
    )


def _ziro_exhaust_resource(state, source_ci, target_id, event_ctx):
    """Exhaust one ready resource controlled by the source's opponent."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    for r in opp.resources:
        if not r.exhausted:
            r.exhausted = True
            break
    return state


@card_ability("TWI", "185")
def _ziro_the_hutt():
    """TWI_185 — Ziro the Hutt (Unit, Cunning/Villainy, Hutt/Underworld, 2/8, cost 5): "When
    Played: For each opponent, you may exhaust a unit that player controls." and
    "On Attack: For each opponent, you may exhaust a resource that player controls."

    "For each opponent" is one opponent in two-player, so each clause is a single
    optional effect.  The unit half is a plain targeted ``ExhaustCard`` over enemy
    units; the resource half is a ``CustomEffect`` because resources are not
    targetable cards (and need not be — any ready resource is as good as any
    other, the SOR_145 auto-pick convention).  Both are ``optional``: the text says
    "you may", and declining is real when exhausting would trip an opponent's
    "while you control no ready resources" clause in your favour."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit"))],
            optional=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_ziro_exhaust_resource)],
            optional=True,
        ),
    ]


def _san_hill_ready_resources(state, source_ci, target_id, event_ctx):
    """Ready one friendly resource per friendly unit defeated this phase."""
    gm = state.game_memory
    n = sum(1 for pid in (getattr(gm, "defeated_controllers_this_round", None) or [])
            if pid == source_ci.owner_id)
    ps = state.player_by_id(source_ci.owner_id)
    readied = 0
    for r in ps.resources:
        if readied >= n:
            break
        if r.exhausted:
            r.exhausted = False
            readied += 1
    return state


@card_ability("TWI", "186")
def _san_hill():
    """TWI_186 — San Hill (Unit, Villainy/Cunning, Official/Separatist, 3/7, cost 6, Exploit
    3): "On Attack: For each friendly unit that was defeated this phase, ready a
    friendly resource."

    The count comes from ``game_memory.defeated_controllers_this_round`` — one
    entry per defeat, stamped with the controller AT DEATH, so it counts units the
    source's controller lost however they died (including the ones his own Exploit
    3 just ate, which is the intended combo).  Defeats only happen in ACTION and
    the ledger clears at the round rollover, so this-round == this-phase here.

    Readying is auto-picked and capped by how many resources are actually
    exhausted — fungible, so there is nothing to decide."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_san_hill_ready_resources)],
    )


def _ahsoka_twi194_bounce(state, source_ci, target_id, event_ctx):
    """Return this unit AND each upgrade on her to their owners' hands."""
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.cards.models import TokenUpgrade
    # The upgrades go FIRST: returning the host detaches them, and the default
    # rule sends a detached upgrade to its owner's DISCARD.  Routing each one
    # through _apply_return_to_hand while it is still attached takes the
    # upgrade branch of that helper, which homes it in its owner's HAND.
    for upg in list(getattr(source_ci, "attached_upgrades", None) or ()):
        if not isinstance(upg.card_def, TokenUpgrade):
            _apply_return_to_hand(state, upg.instance_id)
    _apply_return_to_hand(state, source_ci.instance_id)
    return state


@card_ability("TWI", "194")
def _ahsoka_tano_twi194():
    """TWI_194 — Ahsoka Tano (Unit, Cunning/Heroism, Force/Jedi/Republic, 3/4, cost 3):
    "While you control fewer units than an opponent (including this unit), this
    unit gains Ambush." and "Action [2 resources]: Return this unit and each
    upgrade on her to their owners' hands."

    The Ambush clause is the Savage Opress TWI_137 gate —
    ``OPPONENT_MORE_UNITS_THAN_CONTROLLER``, the MIRROR of its sibling, so equal
    counts grant nothing, which is exactly "fewer".  Registering it as a
    conditional self-grant makes the sanitiser strip the printed always-on copy.

    The Action is a ``CustomEffect`` rather than a bare ``ReturnToHand`` because of
    the upgrade clause: the default rule DISCARDS a detached upgrade, while this
    card returns each one to its owner's hand — the reason to pay 2 for a bounce is
    to re-buy the upgrades, so the deviation is the point of the card.  Together
    the two halves are one loop: bounce her when behind, replay her with Ambush."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Ambush", value=0)],
            condition=ConditionCheck(Condition.OPPONENT_MORE_UNITS_THAN_CONTROLLER),
        ),
        ActivatedAbility(
            costs=[PayResources(2)],
            effects=[CustomEffect(fn=_ahsoka_twi194_bounce)],
            title="Action [2 resources]: Return this unit and its upgrades to hand",
        ),
    ]


@card_ability("TWI", "197")
def _republic_attack_pod():
    """TWI_197 — Republic Attack Pod (Unit, Cunning/Heroism, Republic/Vehicle/Walker, 6/7,
    cost 6): "If you control 3 or more units, this unit costs 1 resource less to
    play."

    Pure reuse: a ``CostReduction`` gated by the Coordinate atom
    ``CONTROLLER_N_PLUS_UNITS`` (param 3).  Read at the play-cost path, so it moves
    both affordability in ``legal_actions`` and the resources actually spent.  The
    pod is still in hand when the condition is evaluated, so it does not count
    itself — three OTHER units are needed, which is the card's whole tension."""
    return CostReduction(
        amount=1,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3),
    )


@card_ability("TWI", "200")
def _creative_thinking():
    """TWI_200 — Creative Thinking (Event, Cunning/Heroism, Trick, cost 2): "Exhaust a
    non-unique unit.  Create a Clone Trooper token."

    Two effects, targeted one FIRST (the resolver consumes the chosen target at the
    current effect index, so a fixed/untargeted effect listed ahead of a targeted
    one costs the prompt).  ``non_unique`` is an existing predicate; "a unit" is
    unrestricted by controller, and exhausting a friendly non-unique is legal if
    pointless — the printed text, not a house rule."""
    return EventAbility(effects=[
        ExhaustCard(TargetSpec(kind="unit", predicates=("non_unique",))),
        CreateTokenUnit("Clone Trooper", count=1),
    ])



# ── twi-set:18 — Combat tricks, buffs & tempo ────────────────────────────────
#
# Two of these (TWI_204, TWI_211) are pure composition of the Change of Heart
# SOR_224 pair: ``actions.change_control`` (control is implicit arena occupancy)
# plus the one-shot ``return_control_to_owner_at_regroup`` flag swept in
# ``_enter_regroup``.  Nothing new was needed for the loan-and-return shape.


@card_ability("TWI", "203")
def _chancellor_palpatine_twi203():
    """TWI_203 — Chancellor Palpatine (Unit, Cunning, Official/Republic,
    2/6, cost 4): "Each token unit you create enters play ready." and "On Attack:
    If a unit left play this phase, create a Clone Trooper token."

    Two specs.  The first is the new ``TokensEnterPlayReady`` marker, read at the
    single token-creation seam — a board-wide upgrade to EVERY token this player
    makes, not just the ones this card makes, which is what "each token unit you
    create" says.  It is the standing version of the per-effect
    ``CreateTokenUnit(enters_ready=True)`` (On the Doorstep TWI_190).

    The second is a mandatory ``OnAttack`` gated by ``ANY_UNIT_DEFEATED_THIS_PHASE``
    (Yoda TWI_4) — "a unit left play", whoever owned it, so trading in combat before
    he swings arms it.  Together they read as one card: he manufactures a body that
    can act immediately, so the token is tempo rather than a wall."""
    return [
        TokensEnterPlayReady(),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CreateTokenUnit("Clone Trooper", count=1)],
            condition=ConditionCheck(Condition.ANY_UNIT_DEFEATED_THIS_PHASE),
        ),
    ]


def _impropriety_pick_theirs(state, source_ci, target_id, event_ctx):
    """Remember the enemy unit chosen for the swap (stage 1 of 2)."""
    event_ctx["impropriety_theirs"] = target_id
    return state


def _impropriety_swap(state, source_ci, target_id, event_ctx):
    """Swap control of the two chosen units, each reverting at regroup."""
    from swu.engine.actions import change_control
    theirs_id = event_ctx.get("impropriety_theirs")
    if theirs_id is None or target_id is None:
        return state          # "If you do" — one side had no legal pick
    me = source_ci.owner_id
    opp = state.players[1 - state.player_index(me)].player_id
    theirs = state.find_instance(theirs_id)
    mine = state.find_instance(target_id)
    if theirs is None or mine is None:
        return state
    # Move both before flagging: change_control is a no-op if the unit is already
    # in the destination arena, and each flag is consumed once at regroup.
    change_control(state, theirs[1], me)
    change_control(state, mine[1], opp)
    theirs[1].return_control_to_owner_at_regroup = True
    mine[1].return_control_to_owner_at_regroup = True
    return state


@card_ability("TWI", "204")
def _impropriety_among_thieves():
    """TWI_204 — Impropriety Among Thieves (Event, Cunning, Trick, cost 4): "Choose
    a ready non-leader unit controlled by each player.  If you do, each player takes
    control of the chosen unit controlled by the player to their right.  At the
    start of the regroup phase, each player takes control of each unit they own that
    was chosen for this ability."

    In two-player "the player to their right" is just the other player, so the whole
    thing is a straight two-unit SWAP that undoes itself at regroup.  Two targeted
    ``CustomEffect``s sharing the resolve_effects ``event_ctx`` (the Nothing Left to
    Fear LAW_41 pattern): the first records the enemy pick, the second takes the
    friendly pick and performs both relocations.  "If you do" is the guard in the
    second fn — with either side unpickable, nothing moves.

    Both units carry ``return_control_to_owner_at_regroup``, the Change of Heart
    SOR_224 flag, so the loan expires on its own; the units keep their damage and
    upgrades across the swap because control is only arena occupancy."""
    return EventAbility(effects=[
        CustomEffect(fn=_impropriety_pick_theirs,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader", "ready"))),
        CustomEffect(fn=_impropriety_swap,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("non_leader", "ready"))),
    ])


def _lux_bonteri_ready_or_exhaust(state, source_ci, target_id, event_ctx):
    """Offer "ready or exhaust a unit" as a two-mode modal."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["ready_unit", "exhaust_unit"])
    return state


@card_ability("TWI", "210")
def _lux_bonteri():
    """TWI_210 — Lux Bonteri (Unit, Cunning, Separatist, 3/2, cost 2):
    "When an opponent plays a card: If that opponent paid less than the card's cost
    to play it, ready or exhaust a unit."

    ``WhenOpponentPlaysCard(paid_less_than_cost=True)`` — every play path stamps
    what was actually paid onto the ``CardPlayed`` event, so "paid less than the
    card's cost" is just ``cost_paid < printed cost``, whatever produced the
    discount (a CostReduction, Exploit, a smuggle/plot price, a granted discount).
    The filter gates COLLECTION, so a full-price play never prompts.

    "Ready or exhaust a unit" is ``push_modal`` over the existing ``exhaust_unit``
    mode and its new ``ready_unit`` sibling — both non-fungible (which unit matters,
    and either may be friendly or enemy), and each offered only when it would do
    something, so the modal fizzles on an empty board rather than asking."""
    return TriggerAbility(
        trigger=WhenOpponentPlaysCard(paid_less_than_cost=True),
        effects=[CustomEffect(fn=_lux_bonteri_ready_or_exhaust)],
    )


def _sly_moore_steal_token(state, source_ci, target_id, event_ctx):
    """Take control of the chosen enemy token unit, ready it, revert at regroup."""
    from swu.engine.actions import change_control
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, token_ci = res
    change_control(state, token_ci, source_ci.owner_id)
    token_ci.exhausted = False                                # "and ready it"
    token_ci.return_control_to_owner_at_regroup = True        # delayed revert
    return state


@card_ability("TWI", "211")
def _sly_moore():
    """TWI_211 — Sly Moore (Unit, Cunning, Official/Republic, 3/3, cost 3):
    "When Played: Take control of an enemy token unit and ready it.  At the start of
    the regroup phase, that token unit's owner takes control of it."

    Change of Heart SOR_224 narrowed to a token host: one targeted ``CustomEffect``
    composing ``change_control`` with the ``return_control_to_owner_at_regroup``
    flag, plus the ready.  The ``token_unit`` predicate (Shaak Ti TWI_94) is what
    makes it a token-swarm answer rather than a generic steal.

    A borrowed token that dies under her control simply ceases to exist — token
    units are never discarded — which is exactly what the printed card does."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_sly_moore_steal_token,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("token_unit",)),
        )],
    )


def _breaking_in_attack(state, source_ci, target_id, event_ctx):
    """Attack with a unit; it gets +2/+0 and Saboteur for this attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        grant_keywords=["Saboteur"])
    return state


@card_ability("TWI", "224")
def _breaking_in_card():
    """TWI_224 — Breaking In (Event, Cunning, Tactic, cost 2): "Attack with a unit.
    It gets +2/+0 and gains Saboteur for this attack."

    Pure reuse — ``push_granted_attack`` with a ``power_bonus`` and a this-attack
    ``grant_keywords`` (Shoot First's First Strike, Grim Resolve TWI_172's Grit).
    Saboteur is a live engine keyword, so ignoring Sentinel and popping the
    defender's Shields both fall out of the grant with nothing card-specific."""
    return EventAbility(effects=[CustomEffect(fn=_breaking_in_attack)])


def _heroes_on_both_sides(state, source_ci, target_id, event_ctx):
    """Give the chosen unit +2/+2 and Saboteur for this phase."""
    from swu.engine.state import Modifier
    if target_id is None:
        return state
    for kind, value in (("stats", {"power": 2, "hp": 2}),
                        ("keyword_grant", {"keyword": "Saboteur", "value": 0})):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=target_id,
            kind=kind,
            value=value,
            duration="this_phase",
        ))
    return state


@card_ability("TWI", "249")
def _heroes_on_both_sides_card():
    """TWI_249 — Heroes on Both Sides (Event, Heroism, Republic/Separatist, cost 2):
    "Choose up to 1 Republic unit and up to 1 Separatist unit.  Give each chosen
    unit +2/+2 and Saboteur for this phase."

    Two targeted ``CustomEffect``s, one per trait, each applying BOTH payoffs to the
    unit it chose.  One effect rather than a ``ModifyStats`` + ``GrantKeyword``
    pair, because the pair would prompt twice and could land the buff and the
    keyword on DIFFERENT units — the two halves must follow one choice (the Kylo
    SHD_141 one-CustomEffect rule).

    "Up to 1" collapses to a mandatory pick when a legal target exists (the Val
    SHD_58 optimal-play convention) and fizzles cleanly when none does — the effect
    is a pure buff, so declining it is never the better line."""
    return EventAbility(effects=[
        CustomEffect(fn=_heroes_on_both_sides,
                     target=TargetSpec(kind="unit", traits=("Republic",))),
        CustomEffect(fn=_heroes_on_both_sides,
                     target=TargetSpec(kind="unit", traits=("Separatist",))),
    ])


@card_ability("TWI", "254")
def _volunteer_soldier():
    """TWI_254 — Volunteer Soldier (Unit, aspectless, Trooper, 2/3, cost 3,
    Raid 1): "If you control a Trooper unit, this unit costs 1 resource less to
    play."

    Pure reuse: ``CostReduction`` gated by ``CONTROLLER_HAS_TRAIT_UNIT`` — the
    plain atom, NOT the "other" variant, because the soldier is still in hand when
    the play cost is computed and so never counts itself either way.  Read at the
    play-cost path, so it moves affordability and the resources actually spent."""
    return CostReduction(
        amount=1,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, "Trooper"),
    )


# ── twi-set:19 — Miscellaneous abilities (Separatist leaders, base & bodies) ──


@card_ability("TWI", "2")
def _nute_gunray():
    """TWI_2 — Nute Gunray (Leader, Official/Separatist, 2/8):
      * undeployed: "Action [Exhaust]: If 2 or more friendly units were defeated
        this phase, create a Battle Droid token."
      * deployed: "On Attack: Create a Battle Droid token."

    The counting gate is the new ``CONTROLLER_N_UNITS_DEFEATED_THIS_PHASE`` atom
    (param=2) — the ledger behind ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` holds one
    entry per defeat, so "2 or more friendly units" is just a count of the
    controller's entries.  The Epic Action deploy is the standard leader-deploy
    machinery (deploy_threshold), not an ability.

    NOTE: (TWI, "2") is also the registry key of the **Clone Trooper token unit** —
    token units share their set/number with a real card.  Both sides are side-gated
    (``undeployed_only`` / ``deployed_only``), and the collection seams now require
    a Leader card_def before honouring ``undeployed_only``, so a Clone Trooper token
    in an arena inherits neither clause.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CreateTokenUnit("Battle Droid", count=1)],
            title="Create a Battle Droid token",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_N_UNITS_DEFEATED_THIS_PHASE, 2),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CreateTokenUnit("Battle Droid", count=1)],
            deployed_only=True,
        ),
    ]


def _dooku_exploit_play(state, source_ci, target_id, event_ctx):
    """TWI_5 undeployed: play a Separatist card from hand, with Exploit 1.

    Exploit 1 is "you may defeat 1 unit you control; if you do, that card costs 2
    resources less", so the play is the combined_power_play seam under its EXPLOIT
    pricing knobs: choose up to 1 friendly unit, then play a Separatist card at 2
    less per unit given up, the chosen unit dying only if the play happens.  With
    no friendly unit to give up there is nothing to choose, so the play is pushed
    directly at full price.

    DEVIATION: ``push_play_from_hand`` plays UNITS, so a Separatist event/upgrade is
    not offered here (the card says "a Separatist card").
    """
    from swu.engine.actions import push_combined_power_play, push_play_from_hand
    before = len(state.pending_decisions)
    push_combined_power_play(state, source_ci, trait="Separatist",
                             max_units=1, cost_reduction_per_unit=2)
    if len(state.pending_decisions) == before:
        push_play_from_hand(state, source_ci, trait="Separatist")
    return state


def _dooku_grant_exploit_3(state, source_ci, target_id, event_ctx):
    """TWI_5 deployed On Attack: arm "the next Separatist card you play this phase
    gains Exploit 3" — one pending grant, consumed by the Exploit seam in
    ``PlayCard`` at the next matching play (the pending_play_discounts shape)."""
    state.game_memory.pending_exploit_grants.append(
        {"player_id": source_ci.owner_id, "trait": "Separatist", "amount": 3})
    return state


@card_ability("TWI", "5")
def _count_dooku_twi5():
    """TWI_5 — Count Dooku, Face of the Confederacy (Leader, Force/Separatist/Sith):
      * undeployed: "Action [Exhaust]: Play a Separatist card from your hand.  It
        gains Exploit 1."
      * deployed: Overwhelm (the keyword layer) + "On Attack: The next Separatist
        card you play this phase gains Exploit 3."

    Both clauses hang off the same idea — a play that gains Exploit — from opposite
    ends: the Action *is* the play (the combined_power_play exploit-pricing seam),
    while the On Attack arms a pending grant that the ordinary play path picks up.
    The granted value ADDS to the printed one, so a Providence Destroyer (Exploit 2)
    played under the grant exploits up to 5 units.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_dooku_exploit_play)],
            title="Play a Separatist card (Exploit 1)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_dooku_grant_exploit_3)],
            deployed_only=True,
        ),
    ]


@card_ability("TWI", "22")
def _droid_manufactory():
    """TWI_22 — Droid Manufactory (Base): "When you deploy a leader: Create 2 Battle
    Droid tokens."

    Pure reuse: the ``WhenYouDeployLeader`` observer (Shadow Collective Camp TWI_25)
    — a Base is reached by the base_zone branch of the trigger collector — plus the
    create-token-unit primitive.
    """
    return TriggerAbility(
        trigger=WhenYouDeployLeader(),
        effects=[CreateTokenUnit("Battle Droid", count=2)],
    )


@card_ability("TWI", "31")
def _rune_haako():
    """TWI_31 — Rune Haako: "When Played: If a friendly unit was defeated this
    phase, you may give a unit –1/–1 for this phase."

    The condition gates trigger COLLECTION, so with no friendly loss this phase the
    trigger is never offered; ``optional`` covers the "you may".  "A unit" is any
    unit — the card does not restrict it to an enemy.
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ModifyStats(power=-1, hp=-1,
                             target=TargetSpec(controller="any", kind="unit"),
                             duration=Duration.THIS_PHASE)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE),
    )


@card_ability("TWI", "32")
def _wartime_trade_official():
    """TWI_32 — Wartime Trade Official: "When Defeated: Create a Battle Droid
    token." """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
    )


@card_ability("TWI", "38")
def _providence_destroyer():
    """TWI_38 — Providence Destroyer (Exploit 2): "On Attack: Give an enemy space
    unit –2/–2 for this phase."

    Exploit is the keyword layer.  The debuff is a targeted this-phase
    ``ModifyStats`` narrowed to the space arena — Providence is itself a space unit,
    but the restriction is printed, so it is spelled out rather than inferred.
    """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=-2, hp=-2,
                             target=TargetSpec(controller="enemy", kind="unit",
                                               arena="space"),
                             duration=Duration.THIS_PHASE)],
    )


def _malevolence_debuff(state, source_ci, target_id, event_ctx):
    """TWI_39: the chosen enemy unit gets –4/–0 AND can't attack, both for this
    phase.  ONE CustomEffect per pick (the Heroes on Both Sides TWI_249 rule): a
    ModifyStats + a second effect would prompt twice and could split the halves
    across two different units."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    for kind, value in (("stats", {"power": -4, "hp": 0}),
                        ("cannot_attack", {})):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=target_id,
            kind=kind,
            value=value,
            duration="this_phase",
        ))
    return state


@card_ability("TWI", "39")
def _malevolence():
    """TWI_39 — Malevolence (Exploit 4, Restore 2): "When Played: Give an enemy unit
    –4/–0 for this phase.  It can't attack for this phase."

    Exploit and Restore are the keyword layer.  "It can't attack" is the new applied
    ``cannot_attack`` Modifier, read at the attack-enumeration seam beside the
    printed ``AttackRestriction`` marker — a duration-scoped effect landed on a unit
    rather than a property of a card, so it expires with the ordinary sweep.
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_malevolence_debuff,
                              target=TargetSpec(controller="enemy", kind="unit"))],
    )


# ── twi-set:20 — Miscellaneous abilities (debuffs, tokens & a shield) ────────


@card_ability("TWI", "46")
def _captain_typho():
    """TWI_46 — Captain Typho (Sentinel): "When Played/On Attack: Give a unit
    Sentinel for this phase."

    A "When Played/On Attack" card is two TriggerAbilities over the same effect —
    the engine has no combined trigger, and each fires at its own site.  "A unit" is
    any unit; giving an enemy unit Sentinel is legal and pointless, which is how the
    card reads.
    """
    grant = GrantKeyword("Sentinel", value=0,
                         target=TargetSpec(controller="any", kind="unit"),
                         duration=Duration.THIS_PHASE)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[grant]),
        TriggerAbility(trigger=OnAttack(), effects=[grant]),
    ]


@card_ability("TWI", "49")
def _knight_of_the_republic():
    """TWI_49 — Knight of the Republic: "When this unit is attacked: Create a Clone
    Trooper token." """
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CreateTokenUnit("Clone Trooper", count=1)],
    )


@card_ability("TWI", "52")
def _hello_there():
    """TWI_52 — Hello There: "Choose a unit that entered play this phase.  It gets
    –4/–4 for this phase."

    Pure reuse: the ``played_this_phase`` predicate is backed by
    ``game_memory.units_played_this_phase``, which every enter-play path feeds —
    including ``_create_token_units`` — so "entered play" covers created tokens as
    well as played units, exactly as printed.
    """
    return EventAbility(effects=[
        ModifyStats(power=-4, hp=-4,
                    target=TargetSpec(controller="any", kind="unit",
                                      predicates=("played_this_phase",)),
                    duration=Duration.THIS_PHASE),
    ])


def _finn_prevent_1(state, source_ci, target_id, event_ctx):
    """TWI_53: the chosen unique unit prevents 1 of EVERY instance of damage dealt
    to it this phase — the applied sibling of the Boba Fett's Armor SHD_224
    ``DamagePrevention`` upgrade marker, read at the same single damage
    chokepoint."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="damage_prevention",
        value={"amount": 1},
        duration="this_phase",
    ))
    return state


@card_ability("TWI", "53")
def _finn():
    """TWI_53 — Finn: "When this unit completes an attack: Choose a unique unit.
    For this phase, if damage would be dealt to that unit, prevent 1 of that
    damage."

    ``WhenAttackEnds`` is "completes an attack" (it fires only for an attacker still
    in play, so "completes" is intrinsic).  The prevention is the new
    ``damage_prevention`` Modifier: a reduction applied before the Shield check, so
    an instance reduced to nothing leaves no damage for a Shield to eat.  "A unique
    unit" is the ``unique`` predicate — either player's, as printed.
    """
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_finn_prevent_1,
                              target=TargetSpec(controller="any", kind="unit",
                                                predicates=("unique",)))],
    )


def _equalize_first(state, source_ci, target_id, event_ctx):
    """Equalize's first half: –2/–2 for this phase, recording the chosen unit and
    its CONTROLLER so the second half can gate on "that unit's controller"."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": -2, "hp": -2},
        duration="this_phase",
    ))
    event_ctx["excluded_target_id"] = target_id
    for ps in state.players:
        if any(ci.instance_id == target_id
               for ci in ps.ground_arena + ps.space_arena):
            event_ctx["prior_target_controller"] = ps.player_id
            break
    return state


def _equalize_second(state, source_ci, target_id, event_ctx):
    """Equalize's second half — identical debuff on a different unit.  The gate
    lives in the TargetSpec (no candidates ⇒ no prompt), so by the time this runs
    the "if you control fewer units" clause is already satisfied."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": -2, "hp": -2},
        duration="this_phase",
    ))
    return state


@card_ability("TWI", "55")
def _equalize():
    """TWI_55 — Equalize: "Give a unit –2/–2 for this phase.  Then, if you control
    fewer units than that unit's controller, give another unit –2/–2 for this
    phase."

    Two sequential targeted ``CustomEffect``s sharing the resolve step's
    ``event_ctx`` (the Nothing Left to Fear LAW_41 shape).  The conditional half is
    gated inside its TargetSpec by the new
    ``fewer_units_than_prior_target_controller`` predicate plus
    ``excludes_event_target`` for "another unit" — failing the board test leaves no
    candidates, so the second half fizzles silently instead of prompting.
    """
    return EventAbility(effects=[
        CustomEffect(fn=_equalize_first,
                     target=TargetSpec(controller="any", kind="unit")),
        CustomEffect(fn=_equalize_second,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("excludes_event_target",
                                                   "fewer_units_than_prior_target_controller"))),
    ])


@card_ability("TWI", "60")
def _trade_federation_shuttle():
    """TWI_60 — Trade Federation Shuttle: "When Played: If you control a damaged
    unit, create a Battle Droid token."

    The gate is the new ``CONTROLLER_HAS_DAMAGED_UNIT`` atom (the friendly mirror of
    ``ENEMY_HAS_DAMAGED_UNIT``); it gates trigger collection, so an undamaged board
    never prompts.  The Shuttle is in its arena when the trigger is evaluated, so it
    counts itself if it somehow entered damaged.
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_DAMAGED_UNIT),
    )


@card_ability("TWI", "63")
def _vulture_interceptor_wing():
    """TWI_63 — Vulture Interceptor Wing: "On Attack: Give an enemy unit –1/–1 for
    this phase."  Any arena — the card does not restrict it to space."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=-1, hp=-1,
                             target=TargetSpec(controller="enemy", kind="unit"),
                             duration=Duration.THIS_PHASE)],
    )


# ── twi-set:21 — Miscellaneous abilities (droid swarm, debuffs & prevention) ─


@card_ability("TWI", "66")
def _multi_troop_transport():
    """TWI_66 — Multi-Troop Transport (Exploit 2): "On Attack: Create a Battle Droid
    token."  Exploit is the keyword layer."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CreateTokenUnit("Battle Droid", count=1)],
    )


def _roger_roger_reattach(state, source_ci, target_id, event_ctx):
    """TWI_69: move the just-defeated upgrade out of its owner's discard and attach
    it to the chosen friendly Battle Droid token.

    By the time this ``WhenDefeatedAsUpgrade`` trigger resolves, ``_defeat_unit`` has
    already detached the upgrade and homed it in its owner's discard (the Luke
    J25_4 / Superlaser Technician SHD_85 timing), so this is a relocation: pull it
    back out and hang it on the new host.  Deliberately NOT an ``UpgradePlayed``
    fire — the upgrade is not played again, so no When-Played trigger (its own or
    anyone's) may see it a second time.
    """
    if target_id is None:
        return state
    result = state.find_instance(source_ci.instance_id)
    host = state.find_instance(target_id)
    if result is None or host is None:
        return state
    ps, upg = result
    host_ps, host_ci = host
    if upg in ps.discard:
        ps.discard.remove(upg)
    upg.face_down = False
    upg.zone = host_ci.zone
    host_ci.attached_upgrades.append(upg)
    return state


@card_ability("TWI", "69")
def _roger_roger():
    """TWI_69 — Roger Roger (Upgrade): "When Defeated: Attach this upgrade to a
    friendly Battle Droid token."

    An upgrade is "defeated" when its host is, and the only seam that collects an
    upgrade's own trigger from that path is ``WhenDefeatedAsUpgrade`` (the
    ``event_ctx["defeated_upgrades"]`` scan) — a plain ``WhenDefeated`` on an upgrade
    is never collected there.  The new host is picked with ``TargetSpec.names`` +
    the ``token_unit`` predicate, which is exactly "a friendly Battle Droid token"
    (the printed Battle Droid unit is not a token; a Clone Trooper token is not
    named Battle Droid).  Mandatory as printed — it simply fizzles with no token in
    play.
    """
    return TriggerAbility(
        trigger=WhenDefeatedAsUpgrade(),
        effects=[CustomEffect(
            fn=_roger_roger_reattach,
            target=TargetSpec(controller="friendly", kind="unit",
                              names=("Battle Droid",),
                              predicates=("token_unit",)),
        )],
    )


def _high_ground_debuff(state, source_ci, target_id, event_ctx):
    """TWI_72: every enemy unit gets –4/–0 *while attacking the chosen unit* this
    phase — one ``stats`` modifier per enemy unit carrying the new
    ``while_attacking_unit_id`` flag, which ``compute_power`` honours only when that
    unit is the current combat defender (the Lando LAW_108 ``defender_id`` context).

    "Each enemy unit" is read at resolution, the EACH_ENEMY convention: an enemy
    unit that arrives later this phase is not covered.
    """
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    for ci in opp.ground_arena + opp.space_arena:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=ci.instance_id,
            kind="stats",
            value={"power": -4, "hp": 0, "while_attacking_unit_id": target_id},
            duration="this_phase",
        ))
    return state


@card_ability("TWI", "72")
def _i_have_the_high_ground():
    """TWI_72 — I Have the High Ground: "Choose a friendly unit.  Each enemy unit
    gets –4/–0 while attacking that unit this phase." """
    return EventAbility(effects=[
        CustomEffect(fn=_high_ground_debuff,
                     target=TargetSpec(controller="friendly", kind="unit")),
    ])


@card_ability("TWI", "75")
def _disruptive_burst():
    """TWI_75 — Disruptive Burst: "Give each enemy unit –1/–1 for this phase." """
    return EventAbility(effects=[
        ModifyStats(power=-1, hp=-1,
                    target=TargetSpec(fixed=EACH_ENEMY, kind="unit"),
                    duration=Duration.THIS_PHASE),
    ])


@card_ability("TWI", "95")
def _pelta_supply_frigate():
    """TWI_95 — Pelta Supply Frigate: "Coordinate — When Played: Create a Clone
    Trooper token."  The Coordinate condition gates trigger collection, and the
    Frigate is already in its arena when it is evaluated, so "including this one"
    falls out for free."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Clone Trooper", count=1)],
        condition=_COORDINATE,
    )


def _aayla_prevent_combat_damage(state, source_ci, target_id, event_ctx):
    """TWI_96: prevent ALL combat damage to Aayla for this attack — a
    ``damage_prevention`` Modifier with ``all`` (not a number) and ``combat_only``,
    so an ability that damages her mid-attack still lands, and ``this_attack`` so it
    expires with the ordinary sweep at the end of combat."""
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=source_ci.instance_id,
        kind="damage_prevention",
        value={"all": True, "combat_only": True},
        duration="this_attack",
    ))
    return state


@card_ability("TWI", "96")
def _aayla_secura():
    """TWI_96 — Aayla Secura: "Coordinate — On Attack: Prevent all combat damage
    that would be dealt to this unit for this attack."

    The On Attack fires before the damage step, so arming the prevention there
    covers the defender's swing back (and a First Strike / defender-first ordering
    alike — every combat instance flows through the one damage chokepoint).
    """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_aayla_prevent_combat_damage)],
        condition=_COORDINATE,
    )


def _manufactured_soldiers_choice(state, source_ci, target_id, event_ctx):
    """TWI_102: push the "choose one" over the two token-creation modes."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci,
               ["create_clone_troopers_2", "create_battle_droids_3"])
    return state


@card_ability("TWI", "102")
def _manufactured_soldiers():
    """TWI_102 — Manufactured Soldiers: "Choose one: Create 2 Clone Trooper tokens /
    Create 3 Battle Droid tokens."

    Two new ``push_modal`` modes.  Neither targets anything, so both are fungible
    and resolve on a throwaway proxy (the controller's base) — the Bombing Run
    SOR_173 arena-mode shape, with a proxy pool that can never be empty, so the
    choice is always offered.
    """
    return EventAbility(effects=[
        CustomEffect(fn=_manufactured_soldiers_choice),
    ])


# ── twi-set:22 — Miscellaneous abilities ─────────────────────────────────────


def _osi_sobeck_paid_threshold(state, source_ci, target_id, event_ctx):
    """TWI_115: record the resources actually paid to play this unit as the capture
    cost ceiling.  ``_put_unit_in_play`` already threads ``cost_paid`` into the
    When Played event context (it is the post-Exploit amount, so exploiting three
    units genuinely shrinks what Osi Sobeck can seize).  A unit that reached the
    arena some other way (a token/free entry) carries no cost — record nothing and
    the capture finds no candidates."""
    paid = event_ctx.get("cost_paid")
    if paid is None:
        return state
    event_ctx["cost_le_threshold"] = int(paid)
    return state


@card_ability("TWI", "115")
def _osi_sobeck():
    """TWI_115 — Osi Sobeck (Separatist, 3/6, Exploit 3): "When Played: This unit
    captures an enemy non-leader ground unit with cost equal to or less than the
    number of resources paid to play this unit."

    Exploit 3 is the keyword layer.  The Yoda TWI_4 "record then gate" shape: a
    leading non-targeted CustomEffect stashes ``cost_le_threshold`` from the play's
    own ``cost_paid``, then a ``CaptureUnit`` whose target carries the existing
    ``cost_le_event_threshold`` predicate — so with nothing cheap enough on the
    board it fizzles without a prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            CustomEffect(fn=_osi_sobeck_paid_threshold),
            CaptureUnit(TargetSpec(
                controller="enemy", kind="unit", arena="ground",
                predicates=("non_leader", "cost_le_event_threshold"))),
        ],
    )


def _clone_become_copy(state, source_ci, target_id, event_ctx):
    """TWI_116: replace this unit's card_def with a copy of the chosen unit's
    printed one, plus the Clone trait and not unique.

    "Only the card's printed attributes are copied", so a frozen
    ``dataclasses.replace`` of the target's own ``card_def`` IS the copy — printed
    stats, traits, aspects, keywords and (because ``get_abilities`` is keyed on
    set+number) its printed abilities all come along.  The instance_id is
    untouched, so card conservation and every zone list still hold.

    If the copied unit belongs to the other arena, the instance is relocated to
    match (it was placed as a Ground unit before the copy resolved).

    Two documented narrowings: the copy happens just after this unit enters play,
    so the copied card's own "When Played" does not fire; and a serialisation
    round-trip rebuilds the card from its ``card_id``, restoring the printed def
    (the added Clone trait and the non-unique flag are lost on reload)."""
    if target_id is None:
        return state
    tgt = state.find_instance(target_id)
    mine = state.find_instance(source_ci.instance_id)
    if tgt is None or mine is None:
        return state
    import dataclasses
    from swu.engine.state import Zone
    holder_ps, me = mine
    copied = tgt[1].card_def
    traits = tuple(getattr(copied, "traits", ()) or ())
    if "Clone" not in traits:
        traits = traits + ("Clone",)
    me.card_def = dataclasses.replace(copied, traits=traits, is_unique=False)
    want = me.zone_for_arena()
    if me.zone != want and me.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        src_list = (holder_ps.ground_arena if me.zone == Zone.GROUND_ARENA
                    else holder_ps.space_arena)
        dst_list = (holder_ps.ground_arena if want == Zone.GROUND_ARENA
                    else holder_ps.space_arena)
        if me in src_list:
            src_list.remove(me)
            me.zone = want
            dst_list.append(me)
    return state


@card_ability("TWI", "116")
def _clone():
    """TWI_116 — Clone (Clone, 0/0): "You may have this unit enter play as a copy of
    a non-leader, non-Vehicle unit in play, except it gains the Clone trait and is
    not unique.  (Only the card's printed attributes are copied.)"

    An optional When Played whose one targeted CustomEffect swaps the instance's
    ``card_def`` for a ``dataclasses.replace`` of the chosen unit's — the whole
    printed profile in one move, since every stat/keyword/ability read goes through
    ``card_def``.  Declining leaves the printed 0/0 body, which is exactly what the
    "you may" buys you (nothing)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(
            fn=_clone_become_copy,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader", "non_vehicle",
                                          "not_self")))],
    )


def _the_clone_wars_pay(state, source_ci, target_id, event_ctx):
    """TWI_125: push the pay-any-number decision with the token-unit payoff."""
    from swu.engine.actions import push_pay_resources_for_tokens
    push_pay_resources_for_tokens(
        state, source_ci, max_resources=None, payoff="token_units",
        token_unit_name="Clone Trooper", opponent_token_unit_name="Battle Droid")
    return state


@card_ability("TWI", "125")
def _the_clone_wars():
    """TWI_125 — The Clone Wars (Event, Disaster): "Pay any number of resources.
    Create that many Clone Trooper tokens.  Each opponent creates that many Battle
    Droid tokens."

    The existing ``pay_resources_for_tokens`` decision (unbounded "any number") with
    a new ``token_units`` payoff: both sides' tokens are tallied through ``paid``
    and created at resolve, after the decision pops, so each token's enter-play bus
    lands on a clean stack."""
    return EventAbility(effects=[CustomEffect(fn=_the_clone_wars_pay)])


@card_ability("TWI", "132")
def _confederate_tri_fighter():
    """TWI_132 — Confederate Tri-Fighter (Separatist/Droid/Vehicle/Fighter, 3/3):
    "Bases can't be healed."

    A bare ``BasesCannotHeal`` marker — the standing, in-play version of Wolffe
    SOR_160's phase-scoped lock, read through the same single
    ``actions._bases_cannot_heal`` predicate that every base-heal chokepoint
    already consults.  Symmetric as printed: it stops the controller's own Restore
    too."""
    return BasesCannotHeal()


@card_ability("TWI", "135")
def _darth_maul_twi_135():
    """TWI_135 — Darth Maul (Force/Sith, 5/6): "This unit can attack 2 units instead
    of 1."

    A bare ``MultiDefenderAttack(count=2)`` marker — the multi-defender-attack
    primitive built for Darth Maul C24_6 (both chosen enemy units are co-defenders
    of one attack: Maul deals his power to each and takes the sum of theirs, all
    simultaneously; a base can't be a co-defender)."""
    return MultiDefenderAttack(count=2)


@card_ability("TWI", "145")
def _jesse():
    """TWI_145 — Jesse (Republic/Clone/Trooper, 4/4, Raid 1): "When Played: An
    opponent creates 2 Battle Droid tokens."

    Raid 1 is the keyword layer.  The drawback clause is a plain
    ``CreateTokenUnit`` with the new ``player="opponent"`` selector (the DrawCards
    convention) — the tokens are created under the OPPONENT's control, in their
    ground arena."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Battle Droid", count=2, player="opponent")],
    )


@card_ability("TWI", "148")
def _senatorial_corvette():
    """TWI_148 — Senatorial Corvette (Republic/Vehicle/Capital Ship, 5/4, Saboteur):
    "When Defeated: Each opponent discards a card from their hand."

    Saboteur is the keyword layer.  A plain ``DiscardFromHand(chooser="opponent")``
    — the first-card discard simplification (K-2SO SOR_145) applied to the one
    opponent this two-player engine has."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DiscardFromHand(count=1, chooser="opponent")],
    )


# ── twi-set:23 — Miscellaneous abilities ─────────────────────────────────────


def _crossfire_first(state, source_ci, target_id, event_ctx):
    """TWI_176: record the first chosen enemy unit and its arena, so the second
    choice is narrowed to "in the same arena" and to a different unit."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _, ci = res
    event_ctx["prior_target_id"] = target_id
    event_ctx["excluded_target_id"] = target_id
    event_ctx["same_arena"] = ("space" if ci.zone == Zone.SPACE_ARENA else "ground")
    event_ctx["crossfire_first"] = target_id
    return state


def _crossfire_second(state, source_ci, target_id, event_ctx):
    """TWI_176: record the second chosen enemy unit."""
    if target_id is not None:
        event_ctx["crossfire_second"] = target_id
    return state


def _crossfire_apply(state, source_ci, target_id, event_ctx):
    """TWI_176: each chosen unit deals damage equal to its power to the other, all
    at once.  Both powers are read BEFORE either instance takes damage, so neither
    swing is blunted by the other (the "All damage is dealt simultaneously" shape of
    Unlimited Power TWI_156: record the pairs, then apply them)."""
    a_id = event_ctx.get("crossfire_first")
    b_id = event_ctx.get("crossfire_second")
    if not a_id or not b_id:
        return state          # only one enemy in an arena — nothing to cross
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import _apply_deal_damage
    pending = []
    for src_id, dst_id in ((a_id, b_id), (b_id, a_id)):
        res = state.find_instance(src_id)
        if res is None:
            continue
        _, ci = res
        pending.append((dst_id, compute_power(state, ci),
                        ci.card_def.display_name))
    for dst_id, amount, name in pending:
        if amount > 0 and state.find_instance(dst_id) is not None:
            _apply_deal_damage(state, dst_id, amount, source_name=name)
    return state


@card_ability("TWI", "176")
def _caught_in_the_crossfire():
    """TWI_176 — Caught in the Crossfire (Event, Disaster): "Choose 2 enemy units in
    the same arena.  Each of those units deals damage equal to its power to the
    other."

    The Nothing Left to Fear LAW_41 shared-``event_ctx`` chain: the first targeted
    CustomEffect records the pick and its arena, the second is narrowed by the
    existing ``same_arena_as_event`` / ``excludes_event_target`` /
    ``requires_prior_target`` predicates (so with one lone enemy the second half
    fizzles without a prompt), and a trailing NON-targeted effect reads both powers
    and then deals both hits — simultaneity, so a unit that dies still swings."""
    return EventAbility(effects=[
        CustomEffect(fn=_crossfire_first,
                     target=TargetSpec(controller="enemy", kind="unit")),
        CustomEffect(fn=_crossfire_second,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("same_arena_as_event",
                                                   "excludes_event_target",
                                                   "requires_prior_target"))),
        CustomEffect(fn=_crossfire_apply),
    ])


@card_ability("TWI", "192")
def _padme_amidala_twi_192():
    """TWI_192 — Padmé Amidala (Naboo/Republic/Official, 1/4): "Coordinate — On
    Attack: Give an enemy unit –3/–0 for this phase."

    A plain targeted this-phase ``ModifyStats`` on an OnAttack trigger, gated by the
    Coordinate condition (which gates trigger collection, so below 3 units the
    prompt never appears)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=-3, hp=0,
                             target=TargetSpec(controller="enemy", kind="unit"),
                             duration=Duration.THIS_PHASE)],
        condition=_COORDINATE,
    )


def _clear_the_field(state, source_ci, target_id, event_ctx):
    """TWI_199: bounce the chosen unit, plus every ENEMY non-leader unit sharing its
    name.  "Enemy" is relative to this event's controller, so choosing your own
    cheap unit is a way to clear the opponent's copies of it."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.cards.models import Leader
    name = res[1].card_def.display_name
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    also = [ci.instance_id for ci in opp.ground_arena + opp.space_arena
            if ci.instance_id != target_id
            and not isinstance(ci.card_def, Leader)
            and ci.card_def.display_name == name]
    _apply_return_to_hand(state, target_id)
    for iid in also:
        _apply_return_to_hand(state, iid)
    return state


@card_ability("TWI", "199")
def _clear_the_field_card():
    """TWI_199 — Clear the Field (Event, Tactic): "Choose a non-leader unit that
    costs 3 or less.  Return it and each enemy non-leader unit with the same name as
    it to their owners' hands."

    One targeted CustomEffect: the choice is the ordinary ChooseTarget machinery
    (``non_leader`` + ``cost_max=3``, either controller), and the name sweep reuses
    the shared ``_apply_return_to_hand`` — each card goes to its OWN owner's hand."""
    return EventAbility(effects=[
        CustomEffect(fn=_clear_the_field,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader",), cost_max=3)),
    ])


@card_ability("TWI", "205")
def _clone_dive_trooper():
    """TWI_205 — Clone Dive Trooper (Republic/Clone/Trooper, 2/1): "Coordinate —
    While this unit is attacking, the defender gets –2/–0."

    The Strafing Gunship SOR_212 ``while_attacking`` ConstantAbility (the
    attacker-scoped mirror of Jyn Erso SOR_18's ``while_target_defending``):
    ``compute_power`` threads the attacker's id, so the debuff lands only on the unit
    THIS trooper is attacking, and only mid-combat.  Coordinate gates the whole
    constant."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),
        effects=[StatBonus(power=-2, hp=0)],
        while_attacking=True,
        condition=_COORDINATE,
    )


@card_ability("TWI", "213")
def _sanctioners_shuttle():
    """TWI_213 — Sanctioner's Shuttle (Republic/Vehicle/Transport, 2/3): "Coordinate
    — When Played: This unit captures an enemy non-leader unit that costs 3 or less."

    A ``CaptureUnit`` on a Coordinate-gated When Played.  The shuttle is already in
    its arena when the trigger is collected, so "including this one" falls out of the
    condition for free; with nothing cheap enough the capture fizzles."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(TargetSpec(controller="enemy", kind="unit",
                                        predicates=("non_leader",), cost_max=3))],
        condition=_COORDINATE,
    )


def _on_top_of_things(state, source_ci, target_id, event_ctx):
    """TWI_219: make the attached unit unattackable for this phase."""
    host_id = event_ctx.get("attached_to_id")
    if host_id is None or state.find_instance(host_id) is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=host_id,
        kind="cannot_be_attacked",
        value={},
        duration="this_phase",
    ))
    return state


@card_ability("TWI", "219")
def _on_top_of_things_card():
    """TWI_219 — On Top of Things (Upgrade, Trick): "When Played: Attached unit can't
    be attacked this phase (unless it has Sentinel)."

    An applied ``cannot_be_attacked`` modifier on the host (located through the
    existing ``event_ctx["attached_to_id"]`` key, Frozen in Carbonite SHD_193), read
    at the single attack-enumeration seam ``_cannot_be_attacked`` beside Sabine
    Wren TWI_195's printed marker — so the unit simply drops out of the eligible
    defenders, and the printed Sentinel escape is shared with that marker."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_on_top_of_things)],
    )


def _now_there_are_two_of_them(state, source_ci, target_id, event_ctx):
    """TWI_225: with exactly one friendly unit in play, offer every non-Vehicle hand
    unit sharing a Trait with it, at 5 resources off.

    The trait test uses EFFECTIVE traits for the unit in play (a granted trait
    counts) and printed traits for the hand card (nothing grants traits in hand).
    The whitelist rides on ``push_play_from_hand``'s existing ``eligible_ids``, so no
    new machinery is needed."""
    from swu.engine.actions import push_play_from_hand
    from swu.engine.traits import get_traits
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    units = list(ps.ground_arena) + list(ps.space_arena)
    if len(units) != 1:
        return state
    mine = set(get_traits(state, units[0]))
    if not mine:
        return state
    eligible = frozenset(
        ci.instance_id for ci in ps.hand
        if isinstance(ci.card_def, Unit)
        and "Vehicle" not in (getattr(ci.card_def, "traits", ()) or ())
        and mine & set(getattr(ci.card_def, "traits", ()) or ()))
    if not eligible:
        return state
    push_play_from_hand(state, source_ci, cost_reduction=5, eligible_ids=eligible)
    return state


@card_ability("TWI", "225")
def _now_there_are_two_of_them_card():
    """TWI_225 — Now There Are Two of Them (Event, Trick): "If you control exactly
    one unit, play a non-Vehicle unit from your hand that shares a Trait with the
    unit you control.  It costs 5 resources less."

    The board gate and the trait match are both board reads, so one CustomEffect
    computes the whitelist and hands it to the existing ``play_from_hand`` decision
    via ``eligible_ids`` — the discount is its ordinary ``cost_reduction``.  With no
    qualifying card (or the wrong number of units) nothing is pushed at all."""
    return EventAbility(effects=[CustomEffect(fn=_now_there_are_two_of_them)])


# ── twi-set:24 — Miscellaneous abilities ─────────────────────────────────────


def _prisoner_of_war_captor(state, source_ci, target_id, event_ctx):
    """TWI_227: record the friendly captor (and its cost, for the token rider)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    event_ctx["captor_id"] = target_id
    event_ctx["captor_cost"] = getattr(res[1].card_def, "cost", None)
    return state


def _prisoner_of_war_capture(state, source_ci, target_id, event_ctx):
    """TWI_227: capture the chosen enemy under the recorded captor; if the prey is
    cheaper than the captor, the controller also gets 2 Battle Droid tokens."""
    captor_id = event_ctx.get("captor_id")
    if captor_id is None or target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    prey_cost = getattr(res[1].card_def, "cost", None)
    captor_cost = event_ctx.get("captor_cost")
    from swu.engine.actions import _apply_capture, _create_token_units
    _apply_capture(state, captor_id, target_id)
    if (prey_cost is not None and captor_cost is not None
            and prey_cost < captor_cost):
        _create_token_units(state, state.player_by_id(source_ci.owner_id),
                            "Battle Droid", 2)
    return state


@card_ability("TWI", "227")
def _prisoner_of_war():
    """TWI_227 — Prisoner of War (Event, Tactic): "A friendly unit captures an enemy
    non-leader, non-Vehicle unit.  If the enemy unit costs less than the friendly
    unit, create 2 Battle Droid tokens."

    The Take Captive SHD_131 pair of shared-``event_ctx`` targeted CustomEffects: the
    first records the captor and its cost, the second captures and settles the
    conditional token rider (a strict ``<``, so an equal-cost trade pays nothing).
    With no friendly unit or no eligible prey it fizzles without a prompt."""
    return EventAbility(effects=[
        CustomEffect(fn=_prisoner_of_war_captor,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_prisoner_of_war_capture,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader", "non_vehicle"))),
    ])


@card_ability("TWI", "235")
def _battle_droid_legion():
    """TWI_235 — Battle Droid Legion (Separatist/Droid/Trooper, 6/5, Exploit 2):
    "When Defeated: Create 3 Battle Droid tokens."

    Exploit 2 is the keyword layer; the clause is a plain ``CreateTokenUnit``."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Battle Droid", count=3)],
    )


@card_ability("TWI", "247")
def _at_te_vanguard():
    """TWI_247 — AT-TE Vanguard (Republic/Vehicle/Walker, 6/9, Restore 3): "When
    Defeated: Create 2 Clone Trooper tokens."

    Restore 3 is the keyword layer; the clause is a plain ``CreateTokenUnit``."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Clone Trooper", count=2)],
    )


@card_ability("TWI", "250")
def _sword_and_shield_maneuver():
    """TWI_250 — Sword and Shield Maneuver (Event, Jedi/Republic/Tactic): "Give each
    friendly Trooper unit Raid 1 for this phase.  Give each friendly Jedi unit
    Sentinel for this phase."

    Two fixed ``EACH_FRIENDLY`` ``GrantKeyword`` effects, each narrowed by its own
    trait — no prompt, and a unit that is both a Trooper and a Jedi picks up both,
    as printed.  The Raid/Sentinel the API tags on the event itself are its
    granted keywords, not its own; an Event is never asked for keywords."""
    return EventAbility(effects=[
        GrantKeyword("Raid", value=1,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       traits=("Trooper",), fixed=EACH_FRIENDLY),
                     duration=Duration.THIS_PHASE),
        GrantKeyword("Sentinel", value=0,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       traits=("Jedi",), fixed=EACH_FRIENDLY),
                     duration=Duration.THIS_PHASE),
    ])


@card_ability("TWI", "255")
def _brain_invaders():
    """TWI_255 — Brain Invaders (Fringe, 2/4): "Each leader loses all abilities
    except for epic actions and can't gain abilities."

    A bare ``SuppressLeaderAbilities`` marker — the fourth source of the unified
    ``state.ability_suppressed`` read-layer, so every ability read (keywords,
    trigger collection, the constant-stat scans, the arena action enumeration, the
    TraitGrant scan) turns off for BOTH players' leaders at once, deployed or not,
    and "can't gain abilities" falls out of those reads short-circuiting.  Epic
    actions are carved out at the one seam that offers an undeployed leader's own
    actions; deploying is itself the Epic Action and never routes through the
    ability registry, so a leader can still be deployed."""
    return SuppressLeaderAbilities()
