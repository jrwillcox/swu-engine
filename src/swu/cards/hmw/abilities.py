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

from swu.engine.actor import actor_of

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ActivatedAbility, ConstantAbility, GrantedAbility, EventAbility,
    WhenPlayed, WhenUnitDefeated, WhenYouPlayCard, WhenYouPlayOrCreateUnit,
    PhaseStartTrigger, OnAttack, WhenDefeated, WhenDamageDealt, WhenYouDraw,
    WhenUnitAttacks, WhenDeployed, WhenYouTakeInitiative,
    WhenOpponentPlaysCard, WhenAttackEnds, WhenYouDeployLeader, WhenUnitEntersPlay,
    RevokeKeyword, DamagePrevention, AmbushCanAttackBases, CopyLeaderTraits,
    DealDamage, Heal, DrawCards, ExhaustCard, ReadyCard, ModifyStats, CustomEffect,
    DefeatUnit, ReturnToHand,
    DiscardFromHand, GiveToken, GrantKeyword, CreateTokenUnit,
    KeywordGrant, StatBonus,
    IgnoreAspectPenaltyForPlays, BaseDamageShieldUpgrade, BasesCannotHeal,
    NextPlayDiscount, CostRoute, AbilityDamageBonus, BaseUpgradeDefeatReplacement,
    CostReduction, EntersPlayReady, UnitsEnterPlayReady, NthUnitPlayDiscount,
    DefeatSelf, DiscardCardCost, ExhaustSelf, PayResources,
    ConditionCheck, Condition, Duration,
    TargetSpec, SELF, EACH_ENEMY, EACH_FRIENDLY,
)
from swu.engine.discard_payoffs import discard_payoff


def _discard_choice(state, source_ci, player_id, count=1, **kw):
    """``push_discard_of_choice`` for an ability of ``source_ci`` (hand-back to the
    other player once it resolves)."""
    from swu.engine.actions import push_discard_of_choice
    push_discard_of_choice(state, player_id, count, source_id=source_ci.instance_id,
                           after_idx=1 - state.player_index(actor_of(state, source_ci)), **kw)


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:01 — Fortify cards' residual text
# ══════════════════════════════════════════════════════════════════════════════


def _tarkin_victim_base(state, source_ci):
    """The enemy base with 10 or less remaining HP, or None.  "A base" could name
    either base, but defeating your own base loses the game, so only an
    opponent's base is ever a sane pick (two-player)."""
    for ps in state.players:
        if ps.player_id == actor_of(state, source_ci):
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
    """Discard a card of the player's choice; the ``create_token_if_discarded``
    payoff makes the Beast token (Bix Caleen LAW_236's shape)."""
    _discard_choice(state, source_ci, actor_of(state, source_ci),
                    payoff="create_token_if_discarded",
                    payoff_args={"player_id": actor_of(state, source_ci), "token": "Beast"})
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
    ps = state.player_by_id(actor_of(state, source_ci))
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
    ps = state.player_by_id(actor_of(state, source_ci))
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
    ps = state.player_by_id(actor_of(state, source_ci))
    return len(ps.resources) - 3


def _krrsantan_has_amount(state, source_ci, event_ctx) -> bool:
    return _krrsantan_amount(state, source_ci) > 0


def _krrsantan_hit(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    amount = _krrsantan_amount(state, source_ci)
    if target_id is None or amount <= 0:
        return state
    _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
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
            "player_id": actor_of(state, source_ci), "arena": arena, "amount": 3,
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
    _apply_deal_damage(state, target_id, amount, name, dealer_id=actor_of(state, source_ci),
                       source_id=event_ctx.get("breach_dealer"))
    if excess and event_ctx.get("breach_overwhelm") and victim_ps.base_instance is not None:
        _apply_deal_damage(state, victim_ps.base_instance.instance_id, excess, name,
                           dealer_id=actor_of(state, source_ci),
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
    friendly = res[0].player_id == actor_of(state, source_ci)
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
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
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
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
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
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
    foes = [u for ps in state.players if ps.player_id != actor_of(state, source_ci)
            for u in ps.ground_arena + ps.space_arena]
    if not foes:
        return state
    rng = state.make_rng()
    victim = rng.choice(foes)
    state.rng_state = rng.getstate()
    _apply_deal_damage(state, victim.instance_id, 3, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
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
# ``OPPONENT_HAS_PLANET_BASE``.  Torrent HMW_100 (Naboo) is with the Weakness cards
# (hmw-set:26).
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
                       if p.player_id != actor_of(state, source_ci))
    push_choose_modal(state, source_ci, option_indices=[2, 3], pick=1,
                      decider_id=opponent_id)
    return state


def _gorax_defeat_their_resource(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _fire_defeat_own_resource
    for ps in state.players:
        if ps.player_id != actor_of(state, source_ci):
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
    discard is ``DiscardFromHand(chooser="opponent")`` (they pick the card);
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
    """Discard a card of the player's choice; the ``ready_source_if_discarded``
    payoff readies this unit (the Razor Crest ASH_172 "if you do" binding)."""
    _discard_choice(state, source_ci, actor_of(state, source_ci),
                    payoff="ready_source_if_discarded")
    return state


@discard_payoff("ready_source_if_discarded")
def _ready_source_if_discarded(state, source_id, discarded, args):
    """"…If you do, ready this unit."""
    from swu.engine.actions import _ready_forbidden, note_unit_readied
    from swu.engine.state import Zone
    res = state.find_instance(source_id or "")
    if not discarded or res is None or res[1].zone not in (
            Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return
    me = res[1]
    if me.cannot_ready_this_round or _ready_forbidden(state, me):
        return
    note_unit_readied(state, me)
    me.exhausted = False


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


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:07 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "249")
def _frenzied_tri_fighters():
    """HMW_249 — Frenzied Tri-Fighters (Unit, Droid/Fighter, 5/3): "When Played: You
    may defeat an upgrade that costs 3 or less." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade", cost_max=3))],
        optional=True,
    )


@card_ability("HMW", "252")
def _villainous_ambition():
    """HMW_252 — Villainous Ambition (Upgrade, Innate): "When Played: If attached
    unit is a Villainy unit, you may deal 2 damage to a unit."

    ``ATTACHED_HOST_HAS_ASPECT`` — the aspect sibling of the SEC_227 trait gate —
    so on a non-Villainy host the trigger is never collected."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.ATTACHED_HOST_HAS_ASPECT, param="Villainy"),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
    )


def _forced_pacification_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_cull_for_damage
    push_cull_for_damage(state, source_ci, pool="units", exhaust_enemy_per=2)
    return state


@card_ability("HMW", "253")
def _forced_pacification():
    """HMW_253 — Forced Pacification (Event, Plan): "Defeat any number of friendly
    units.  For each friendly unit defeated this way, exhaust 2 enemy units."

    ``cull_for_damage(pool="units", exhaust_enemy_per=2)`` — the LAW_17 token cull
    widened to every friendly unit, with an exhaust payoff in place of the damage
    (only units that really left play count)."""
    return EventAbility(effects=[CustomEffect(fn=_forced_pacification_fn)])


def _wrecker_hmw_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_each_player_defeats
    push_each_player_defeats(state, source_ci, disposition="damage_chosen",
                             damage_amount=3)
    return state


@card_ability("HMW", "263")
def _wrecker_hmw():
    """HMW_263 — Wrecker (Unit, Clone, 6/6): "When Played: Each player chooses a
    unit they control.  Deal 3 damage to each chosen unit."

    The TWI_238 ``each_player_defeats`` walk under its ``damage_chosen``
    disposition (Time of Crisis LOF_177's opposite); Wrecker himself is a legal
    pick for his own controller."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_wrecker_hmw_fn)])


@card_ability("HMW", "270")
def _wild_space_wanderer():
    """HMW_270 — Wild Space Wanderer (Unit, Fighter/Vehicle, 3/2): "When Played: You
    may defeat an upgrade on a base." — the ``on_base`` predicate (a Fortify
    upgrade), the inverse of ``on_unit``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade",
                                       predicates=("on_base",)))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:08 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "14")
def _wicket_hmw():
    """HMW_14 — Wicket (Leader, Ewok).

    Undeployed: "When a friendly unit attacks a unit that costs more than it: You
    may exhaust this leader.  If you do, draw a card." — a ``WhenUnitAttacks``
    observer whose attacker filter carries the ``defender_costs_more`` predicate,
    gated by ``SOURCE_READY`` (the Mandalorian SHD_18 self-exhaust shape).
    Deployed: "On Attack: If you control a unit that costs 3 or less, draw a card."
    Epic Action: deploy at 4+ resources (standard machinery)."""
    return [
        TriggerAbility(
            trigger=WhenUnitAttacks(filter=TargetSpec(
                controller="friendly", kind="unit",
                predicates=("defender_costs_more",))),
            effects=[ExhaustCard(TargetSpec(kind="unit", fixed=SELF)), DrawCards(1)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DrawCards(1)],
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_COST_MAX, param=3),
        ),
    ]


def _maul_play_then_defeat(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=1, then_defeat_played=True)
    return state


def _maul_replay_defeated(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_play_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    defeated = state.game_memory.units_defeated_this_round
    eligible = frozenset(ci.instance_id for ci in ps.discard
                         if isinstance(ci.card_def, Unit) and ci.instance_id in defeated)
    if eligible:
        push_play_from_hand(state, source_ci, from_discard=True, eligible_ids=eligible,
                            cost_reduction=5, up_to=True)
    return state


@card_ability("HMW", "16")
def _maul_hmw():
    """HMW_16 — Maul (Leader, Force/Fringe; Shielded on the deployed side).

    Undeployed: "Action [Exhaust]: Play a unit from your hand.  It costs 1 resource
    less.  Then, defeat it.  (When Played abilities resolve after the unit is
    defeated.)" — ``play_from_hand`` with the ``then_defeat_played`` rider, gated at
    the discounted price (the Admiral Piett JTL_5 shape).
    Deployed: "When Deployed: You may play a unit that was defeated this phase from
    your discard pile.  It costs 5 resources less." — a discard-only
    ``eligible_ids`` play (Salvage JTL_121) over ``units_defeated_this_round``
    ("this round" == "this phase" for defeats), declinable via ``up_to``."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_maul_play_then_defeat)],
            title="Play a unit for 1 less, then defeat it",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                                     param=(None, 1)),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_maul_replay_defeated)],
            deployed_only=True,
        ),
    ]


_KEEPER = "Keeper of Skara Nal"


def _keeper_discard_two(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import note_hand_or_deck_discard, record_hand_discard
    from swu.engine.state import Zone
    ps = state.player_by_id(actor_of(state, source_ci))
    for card in [c for c in ps.hand if getattr(c.card_def, "name", None) == _KEEPER][:2]:
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(state, card)
        record_hand_discard(state, ps.player_id)
    return state


@card_ability("HMW", "41")
def _keeper_of_skara_nal():
    """HMW_41 — Keeper of Skara Nal (Unit, Droid/Vehicle/Walker, 5/8; Restore 2):
    "On Attack: You may discard 2 cards named Keeper of Skara Nal from your hand.
    If you do, this unit gets +15/+0 and gains Overwhelm for this attack."

    The copies are identical, so the discard needs no choice; the trigger is gated
    by ``CONTROLLER_HAND_NAMED_COUNT_MIN`` so it is never offered unpayable."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAND_NAMED_COUNT_MIN,
                                 param=(_KEEPER, 2)),
        effects=[
            CustomEffect(fn=_keeper_discard_two),
            ModifyStats(15, 0, TargetSpec(fixed=SELF), Duration.THIS_ATTACK),
            GrantKeyword("Overwhelm", 0, TargetSpec(fixed=SELF), Duration.THIS_ATTACK),
        ],
    )


def _vernestra_bottom_and_borrow(state, source_ci, target_id, event_ctx):
    if event_ctx.get("fives_borrow"):
        return state
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=2, own_only=True,
        eligible=lambda cd: isinstance(cd, Unit) and (getattr(cd, "cost", 0) or 0) <= 5,
        then_borrow_when_played=True)
    return state


@card_ability("HMW", "48")
def _vernestra_rwoh():
    """HMW_48 — Vernestra Rwoh (Unit, Force/Jedi, 5/5; Sentinel): "As an additional
    cost to play this unit, put up to 2 units that each cost 5 or less from your
    discard pile on the bottom of your deck.  This unit gains those units' 'When
    Played' abilities for this phase."

    Modelled as her own When Played: the ``bottom_from_discard`` pick (up to 2,
    own discard, unit cost ≤5) with the ``then_borrow_when_played`` payoff, which
    re-pushes each bottomed unit's When Played clauses with Vernestra as their
    source (the Fives TS26_34 borrow).  Paying the "additional cost" as she enters
    rather than before is indistinguishable: nothing reads the discard in between,
    and the borrowed abilities matter only for this play."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_vernestra_bottom_and_borrow)])


@card_ability("HMW", "61")
def _director_krennic_hmw():
    """HMW_61 — Director Krennic (Unit, Imperial/Official, 3/4): "On Attack: If your
    base is upgraded, draw a card." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.CONTROLLER_BASE_UPGRADED),
    )


def _remote_scout_search(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Upgrade
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, window=8, up_to=False,
                     eligible=lambda cd: isinstance(cd, Upgrade))
    return state


@card_ability("HMW", "85")
def _remote_scout():
    """HMW_85 — Remote Scout (Unit, Imperial/Trooper, 1/3): "When Played: Search the
    top 8 cards of your deck for an upgrade, reveal it, and draw it." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_remote_scout_search)])


def _trust_yourself_search(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, window=3, up_to=False,
                     eligible=lambda cd: True)
    return state


@card_ability("HMW", "101")
def _trust_yourself():
    """HMW_101 — Trust Yourself (Event, Innate): "Give a Shield token to a unit.
    Search the top 3 cards of your deck for a card and draw it." """
    return EventAbility(effects=[
        GiveToken("Shield", TargetSpec(controller="any", kind="unit")),
        CustomEffect(fn=_trust_yourself_search),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:09 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "103")
def _disposable_b1():
    """HMW_103 — Disposable B1 (Unit, Droid/Separatist/Trooper, 1/2): "When Played:
    If another friendly unit entered play this phase (including leader and token
    units), draw a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.CONTROLLER_OTHER_UNIT_ENTERED_THIS_PHASE),
    )


def _boga_choose(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard

    def _ok(cd):  # printed traits: a card in the discard carries no grants
        return (isinstance(cd, Unit) and getattr(cd, "name", None) != "Boga"
                and "Vehicle" not in (getattr(cd, "traits", None) or ()))
    push_bottom_from_discard(state, source_ci, count=1, own_only=True, eligible=_ok,
                             disposition="choose_only", then_discard_play_discount=1)
    return state


@card_ability("HMW", "122")
def _boga():
    """HMW_122 — Boga (Unit, Creature, 6/6): "When Played/When Defeated: Choose a
    non-vehicle unit in your discard pile not named Boga.  For this phase, you may
    play that unit from your discard pile.  It costs 1 resource less."

    ``bottom_from_discard(disposition="choose_only")`` (Psychometry LOF_219's pure
    selector) with the ``then_discard_play_discount`` payoff, which records the
    pick in ``discard_play_discount_this_phase`` — Aid from the Innocent TWI_201's
    one-shot discounted replay permission, which already covers units."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_boga_choose)]),
        TriggerAbility(trigger=WhenDefeated(), effects=[CustomEffect(fn=_boga_choose)]),
    ]


def _local_support_reveal(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _draw_cards
    from swu.engine.traits import get_traits, has_trait
    ps = state.player_by_id(actor_of(state, source_ci))
    if not ps.deck:
        return state
    traits = set(get_traits(state, ps.deck[0]))  # Malakili LAW_212 counts in the deck
    if any(has_trait(state, u, t) for u in ps.ground_arena + ps.space_arena
           for t in traits):
        _draw_cards(state, ps, 1)
    return state


@card_ability("HMW", "148")
def _local_support():
    """HMW_148 — Local Support (Upgrade, Supply): "When Played: Reveal the top card
    of your deck.  If it shares a trait with a friendly unit, draw it."  Otherwise
    the revealed card stays on top."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_local_support_reveal)])


@card_ability("HMW", "173")
def _rebel_operation():
    """HMW_173 — Rebel Operation (Event, Plan/Rebel): "This card costs 1 resource
    less to play for each friendly Rebel unit and leader.  Draw 2 cards."

    ``CostReduction.per_friendly_trait`` with the new ``per_trait_includes_leader``
    leg (an undeployed Rebel leader counts; a deployed one already is a unit)."""
    return [
        CostReduction(amount=1, per_friendly_trait="Rebel",
                      per_trait_includes_leader=True),
        EventAbility(effects=[DrawCards(2)]),
    ]


@card_ability("HMW", "180")
def _stormchaser():
    """HMW_180 — Stormchaser (Unit, Tusken, 3/2): "When Played: You may reveal a
    Disaster card from your hand.  If you do or if there's a Disaster card in your
    discard pile, draw a card."

    OPTIMAL-PLAY COLLAPSE: the reveal costs nothing, so the draw happens exactly
    when a Disaster card is in hand or discard (``CONTROLLER_HAND_OR_DISCARD_HAS_
    TRAIT``).  The only thing given up is not showing the opponent the card."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAND_OR_DISCARD_HAS_TRAIT,
                                 param="Disaster"),
    )


@card_ability("HMW", "189")
def _neebray_manta():
    """HMW_189 — Neebray Manta (Unit, Creature, 7/6): "When Played: Draw 3 cards." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(3)])


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:10 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _nightbrother_replay(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_play_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    eligible = frozenset(ci.instance_id for ci in ps.discard
                         if isinstance(ci.card_def, Unit))
    if eligible:
        push_play_from_hand(state, source_ci, from_discard=True, eligible_ids=eligible,
                            cost_reduction=3, enters_ready=True,
                            defeat_at_regroup=True, up_to=True)
    return state


@card_ability("HMW", "204")
def _nightbrother():
    """HMW_204 — Nightbrother (Unit, Transport/Vehicle, 6/7): "When Played: You may
    play a unit from your discard pile.  It costs 3 resources less and enters play
    ready.  At the start of the next regroup phase, defeat it."

    A discard-only ``play_from_hand`` (Salvage JTL_121's ``eligible_ids``) with the
    existing ``enters_ready`` and ``defeat_at_regroup`` riders; ``up_to`` is the
    "may"."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_nightbrother_replay)])


def _l3_37_grant_replay(state, source_ci, target_id, event_ctx):
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    played_id = event_ctx.get("played_card_id")
    ps = state.player_by_id(actor_of(state, source_ci))
    if played_id and any(c.instance_id == played_id for c in ps.discard):
        state.game_memory.free_discard_play_this_phase.add(played_id)
    return state


@card_ability("HMW", "215")
def _l3_37_hmw():
    """HMW_215 — L3-37 (Unit, Droid/Underworld, 5/7): "When you play an event that
    costs 3 or less: You may play it again from your discard pile for free.  Use
    this ability only once each phase."

    ``WhenYouPlayCard(card_type="event", cost_max=3)``; accepting grants the
    Second Chance SHD_53 free-replay permission (``free_discard_play_this_phase``,
    now open to events) on that event.  DOCUMENTED TIMING DEVIATION: the replay is
    a ``PlayFromDiscard`` the player takes as their next action(s) this phase rather
    than inside the trigger — the event's own effects may still be resolving when
    the trigger fires.  Once per phase = ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``
    (events are played in the action phase, so round == phase)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="event", cost_max=3),
        effects=[CustomEffect(fn=_l3_37_grant_replay)],
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


_TATOOINE_BASE = ConditionCheck(Condition.CONTROLLER_HAS_PLANET_BASE, "Tatooine")


@card_ability("HMW", "222")
def _sandcrawler_sales_team():
    """HMW_222 — Sandcrawler Sales Team (Unit, Jawa, 3/2; Saboteur): "When Played:
    If you control a Tatooine base, you may return an upgrade that costs 3 or less
    to its owner's hand." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(controller="any", kind="upgrade", cost_max=3))],
        optional=True,
        condition=_TATOOINE_BASE,
    )


def _mon_cal_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["attack_plus_2", "peek_hand_discard_draw"])
    return state


@card_ability("HMW", "232")
def _mon_cal_cruiser():
    """HMW_232 — Mon Cal Cruiser (Unit, Capital Ship/Rebel/Vehicle, 4/7): "When
    Played: Choose one: Attack with a unit.  It gets +2/+0 for this attack. / Look
    at an opponent's hand.  You may discard a card from it.  If you do, they draw a
    card."

    Two new HANDOFF modes on the ``modal`` kind: ``attack_plus_2`` pushes
    ``granted_attack(power_bonus=2)``; ``peek_hand_discard_draw`` pushes Bazine Netal
    SHD_184's ``name_and_discard(optional, discarder_draws)``."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_mon_cal_choose)])


@card_ability("HMW", "236")
def _booma_ball():
    """HMW_236 — Booma Ball (Upgrade, Item/Weapon): "When Played: You may return an
    upgrade that costs 3 or less to its owner's hand." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(controller="any", kind="upgrade", cost_max=3))],
        optional=True,
    )


@card_ability("HMW", "238")
def _exploit_confidence():
    """HMW_238 — Exploit Confidence (Event, Tactic): "Return a non-leader unit with 6
    or more power to its owner's hand." """
    return EventAbility(effects=[ReturnToHand(TargetSpec(
        controller="any", kind="unit", power_min=6, predicates=("non_leader",)))])


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:11 — Combat tricks, buffs & tempo (the HMW leader block + Hunter)
# ══════════════════════════════════════════════════════════════════════════════


def _asajj_swap_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, swap_raid_restore=True)
    return state


@card_ability("HMW", "1")
def _asajj_ventress_hmw():
    """HMW_1 — Asajj Ventress (Leader, Force/Night, 3/6).

    Undeployed: "Action [Exhaust]: Attack with a unit.  For this attack, replace any
    Raid it has or gains with Restore, or vice versa."
    Deployed:   "Restore 2  |  Action: <the same clause>."

    The swap is ``push_granted_attack(swap_raid_restore=)`` — a this_attack modifier
    read at the top of ``has_keyword``/``keyword_value``.  Restore 2 is the keyword
    layer's (the sanitiser's rule-5 deploy-bar guard keeps it).  Per the card's rules
    note the deployed Action is not offered when no unit can attack
    (``CONTROLLER_HAS_READY_UNIT_COST_MAX`` with an unbounded cap).

    ⚠ HMW_1 is also the Shield token UPGRADE's number, so only the side-gated
    ``ActivatedAbility(undeployed_only/deployed_only)`` kinds are used."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_asajj_swap_attack)],
            title="Attack with a unit — swap its Raid and Restore",
            undeployed_only=True,
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_asajj_swap_attack)],
            title="Attack with a unit — swap its Raid and Restore",
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX,
                                     param=99),
        ),
    ]


def _omega_grit_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_aspect="Heroism",
                        grant_keywords=["Grit"])
    return state


@card_ability("HMW", "6")
def _omega_hmw():
    """HMW_6 — Omega (Leader, Clone, 2/7).

    Undeployed: "Action [1 resource, Exhaust]: Attack with a Heroism unit.  It gains
    Grit for this attack."
    Deployed:   "Other friendly Heroism units gain Grit."  (Omega herself has no
    keyword bar — the upstream Grit tag is the sanitiser's to strip.)"""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_omega_grit_attack)],
            title="Attack with a Heroism unit — it gains Grit",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              aspects=("Heroism",), predicates=("not_self",)),
            effects=[KeywordGrant("Grit")],
        ),
    ]


@card_ability("HMW", "7")
def _darth_vader_leader_hmw():
    """HMW_7 — Darth Vader (Leader, Force/Imperial/Sith, 5/5).

    Undeployed: "Friendly units that cost 3 or more gain Raid 1."
    Deployed:   "Raid 1  |  Other friendly units that cost 3 or more gain Raid 1."

    Two auras: the ``undeployed_only`` one (Savage Opress TS26_5 shape) and the
    ordinary deployed one; the printed cost is what ``cost_min`` reads, as the
    card's rules note says.  Raid 1 on Vader himself is the keyword layer's."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", cost_min=3),
            effects=[KeywordGrant("Raid", 1)],
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", cost_min=3,
                              predicates=("not_self",)),
            effects=[KeywordGrant("Raid", 1)],
        ),
    ]


def _grievous_play_two(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, repeat_max=1)
    return state


@card_ability("HMW", "8")
def _general_grievous_leader_hmw():
    """HMW_8 — General Grievous (Leader, Official/Separatist, 3/6).

    Undeployed: "Action [Exhaust]: Play 2 units from your hand (one at a time,
    paying their costs)."  — ``push_play_from_hand(repeat_max=1)``: a second pick is
    re-pushed under the first unit's own When Played triggers (the ASH_104 loop),
    mandatory if able.
    Deployed:   "While you control more units than an opponent, this unit gets
    +3/+0."  A deployed leader's SELF constant is read only in the arena."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_grievous_play_two)],
            title="Play 2 units from your hand, one at a time",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=3, hp=0)],
            condition=ConditionCheck(Condition.CONTROLLER_MORE_UNITS_THAN_OPPONENT),
        ),
    ]


def _exhausted_ok_unit_attack(state, source_ci, target_id, event_ctx):
    """"Attack with a unit, even if it's exhausted.  It can't attack bases for this
    attack." (Chewbacca HMW_9, Hunter HMW_35)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, allow_exhausted=True, no_base=True)
    return state


@card_ability("HMW", "9")
def _chewbacca_hmw():
    """HMW_9 — Chewbacca (Leader, Rebel/Wookiee, 3/6).

    Undeployed: "Action [2 resources, Exhaust]: Attack with a unit, even if it's
    exhausted.  It can't attack bases for this attack."
    Deployed:   "Action: <the same clause>.  Use this ability only once each round."
    """
    return [
        ActivatedAbility(
            costs=[PayResources(2), ExhaustSelf()],
            effects=[CustomEffect(fn=_exhausted_ok_unit_attack)],
            title="Attack with a unit, even if exhausted (not a base)",
            undeployed_only=True,
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_exhausted_ok_unit_attack)],
            title="Attack with a unit, even if exhausted (not a base)",
            deployed_only=True,
            once_per_round=True,
        ),
    ]


_OSHA_CAN_PLAY = ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_RESOURCES,
                                param="Villainy")


def _osha_play_from_resources(state, source_ci, target_id, event_ctx):
    """"Play a Villainy unit from your resources, ignoring its Villainy aspect
    penalties.  If you do, you may resource a card from your hand."

    ``push_play_from_hand(resources_of=<own id>, aspect="Villainy",
    waive_aspect="Villainy")`` — paying its cost.  The play is mandatory if able, so
    "if you do" is known at push time: the resource step is pushed FIRST (beneath
    the play) only when a candidate exists.  The resource enters exhausted (no "and
    ready it", unlike TS26_12).  The Action's own gate guarantees a candidate; the
    re-check covers a board that changed while costs were paid."""
    from swu.engine.actions import push_play_from_hand, push_resource_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    if not _OSHA_CAN_PLAY.evaluate(state, source_ci):
        return state
    push_resource_from_hand(state, source_ci, count=1, enters_exhausted=True)
    push_play_from_hand(state, source_ci, aspect="Villainy",
                        resources_of=ps.player_id, waive_aspect="Villainy")
    return state


@card_ability("HMW", "17")
def _osha_hmw():
    """HMW_17 — Osha (Leader, Force, 5/6).

    Undeployed: "Action [Exhaust]: If a friendly Heroism unit was defeated this
    phase, <play a Villainy unit from your resources …>."
    Deployed:   "Saboteur  |  Action: <the same clause, ungated>."

    Both Actions are offered only when a Villainy unit in her resources is actually
    playable (``CONTROLLER_CAN_PLAY_UNIT_FROM_RESOURCES("Villainy")``) — a use that
    could only do nothing would waste the action (and mislead the bot).  The
    undeployed side also needs ``CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE
    ("Heroism")``.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_osha_play_from_resources)],
            title="Play a Villainy unit from your resources",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ALL_OF, param=(
                ConditionCheck(Condition.CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE,
                               param="Heroism"),
                _OSHA_CAN_PLAY,
            )),
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_osha_play_from_resources)],
            title="Play a Villainy unit from your resources",
            deployed_only=True,
            condition=_OSHA_CAN_PLAY,
        ),
    ]


def _hunter_choose_two(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=2,
                      allow_repeat=True)
    return state


@card_ability("HMW", "35")
def _hunter_hmw():
    """HMW_35 — Hunter (Unit, Clone, 4/7): "When Played: Choose two.  You may choose
    the same option more than once: Give a Shield token to a unit. / Attack with a
    unit, even if it's exhausted.  It can't attack bases for this attack."

    The ``choose_two_modal`` selector with ``allow_repeat``; the option specs are
    ``EventAbility`` (Enoch ASH shape) so a UNIT card's options are never
    trigger-collected."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_hunter_choose_two)]),
        EventAbility(effects=[GiveToken("Shield",
                                        TargetSpec(controller="any", kind="unit"))]),
        EventAbility(effects=[CustomEffect(fn=_exhausted_ok_unit_attack)]),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:12 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "39")
def _mother_talzin_hmw():
    """HMW_39 — Mother Talzin (Unit, Force/Night, 3/4): "Raid 1.  Each other friendly
    unit gains Restore 1."  Raid 1 is printed (the upstream Restore tag is rule 1's
    grant-to-others to strip)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", predicates=("not_self",)),
        effects=[KeywordGrant("Restore", 1)],
    )


def _dooku_ready_and_heal(state, source_ci, target_id, event_ctx):
    """"Ready another unit.  If you do, heal damage from a base equal to that unit's
    cost."  Only an EXHAUSTED unit can be readied (so "if you do" holds whenever the
    pick resolves), unless an effect forbids it.  "A base" collapses to the
    controller's own — healing an opponent's base is never the better pick."""
    from swu.engine.actions import _ready_forbidden, note_unit_readied
    from swu.abilities.resolver import _apply_heal
    res = state.find_instance(target_id) if target_id else None
    if res is None:
        return state
    ci = res[1]
    if (not ci.exhausted or getattr(ci, "cannot_ready_this_round", False)
            or _ready_forbidden(state, ci)):
        return state
    note_unit_readied(state, ci)
    ci.exhausted = False
    cost = int(getattr(ci.card_def, "cost", 0) or 0)
    base = state.player_by_id(actor_of(state, source_ci)).base_instance
    if cost and base is not None:
        _apply_heal(state, source_ci, base.instance_id, cost)
    return state


@card_ability("HMW", "42")
def _dooku_hmw():
    """HMW_42 — Dooku (Unit, Force/Jedi/Republic, 8/7; Overwhelm): "When Played: You
    may ready another unit.  If you do, heal damage from a base equal to that unit's
    cost."  A targeted ``CustomEffect`` over exhausted other units (either side);
    the printed cost is what heals (a leader unit's cost is its printed cost)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_dooku_ready_and_heal,
                              target=TargetSpec(controller="any", kind="unit",
                                                predicates=("not_self", "exhausted")))],
        optional=True,
    )


def _ima_gun_di_ramp(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_resource_from_hand
    push_resource_from_hand(state, source_ci, count=1, enters_exhausted=True,
                            then_resource_deck_top=True)
    return state


@card_ability("HMW", "44")
def _ima_gun_di_hmw():
    """HMW_44 — Ima-Gun Di (Unit, Force/Jedi/Republic, 5/3): "When Defeated: If you
    control fewer resources than an opponent, you may resource a card from your
    hand.  If you do, resource the top card of your deck."

    ``push_resource_from_hand(then_resource_deck_top=)`` — the "if you do" rider
    settles only when a card was resourced; both enter exhausted (Resupply
    SOR_126's ruling).  The decision's own Finish is the "may"."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_ima_gun_di_ramp)],
        condition=ConditionCheck(Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER),
    )


def _low_altitude_move_and_attack(state, source_ci, target_id, event_ctx):
    """Move the chosen space unit to its controller's ground arena (the Blue Leader
    JTL_96 relocation, upgrades riding along), then offer the optional +2/+0 ground
    attack."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_granted_attack
    res = state.find_instance(target_id) if target_id else None
    if res is None:
        return state
    ps, ci = res
    if ci not in ps.space_arena:
        return state
    ps.space_arena.remove(ci)
    ci.zone = Zone.GROUND_ARENA
    ps.ground_arena.append(ci)
    for up in ci.attached_upgrades:
        up.zone = Zone.GROUND_ARENA
    push_granted_attack(state, source_ci, 2, optional=True, attacker_arena="ground")
    return state


@card_ability("HMW", "50")
def _low_altitude_combat():
    """HMW_50 — Low Altitude Combat (Event, Tactic, 2): "Move a space unit to the
    ground arena (it's now a ground unit).  If you do, you may attack with a ground
    unit.  It gets +2/+0 for this attack."  No space unit → nothing happens (the
    target fizzles, so the attack is never offered)."""
    return EventAbility(effects=[CustomEffect(
        fn=_low_altitude_move_and_attack,
        target=TargetSpec(controller="any", kind="unit", arena="space"))])


@card_ability("HMW", "52")
def _a_koba():
    """HMW_52 — A'Koba (Unit, Tusken, 1/4; Raid 1): "When Played: Give a unit +2/+0
    for this phase." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        ModifyStats(2, 0, TargetSpec(controller="any", kind="unit"),
                    Duration.THIS_PHASE)])


def _yoda_in_discard(state, source_ci, event_ctx):
    res = state.find_instance(source_ci.instance_id)
    return res is not None and res[1] in res[0].discard


def _yoda_top_and_heal(state, source_ci, target_id, event_ctx):
    """"Put this card from your discard pile on top of your deck.  If you do, heal 2
    damage from a base." — the chosen base."""
    from swu.engine.state import Zone
    from swu.abilities.resolver import _apply_heal
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1] not in res[0].discard:
        return state
    owner_ps, ci = res
    owner_ps.discard.remove(ci)
    ci.zone = Zone.DECK
    owner_ps.deck.insert(0, ci)
    if target_id:
        _apply_heal(state, source_ci, target_id, 2)
    return state


@card_ability("HMW", "56")
def _yoda_hmw():
    """HMW_56 — Yoda (Unit, Force/Fringe/Jedi, 4/4; Hidden): "When Defeated: You may
    put this card from your discard pile on top of your deck.  If you do, heal 2
    damage from a base."  One targeted ``CustomEffect`` over bases; gated on the card
    really being in its owner's discard (a token or a captured-then-gone card never
    is)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_yoda_top_and_heal, available_fn=_yoda_in_discard,
                              target=TargetSpec(controller="any", kind="base"))],
        optional=True,
    )


@card_ability("HMW", "63")
def _rho_medical_shuttle():
    """HMW_63 — Rho Medical Shuttle (Unit, Imperial/Transport/Vehicle, 3/3): "When
    Played/On Attack: You may heal 1 damage from another unit or base." """
    def _heal():
        return Heal(1, TargetSpec(controller="any", kind="unit_or_base",
                                  predicates=("not_self",)))
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[_heal()], optional=True),
        TriggerAbility(trigger=OnAttack(), effects=[_heal()], optional=True),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:13 — Combat tricks, buffs & tempo  (HMW_84 lives in the planet block)
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("HMW", "66")
def _carrion_spike():
    """HMW_66 — Carrion Spike (Unit, Capital Ship/Imperial/Vehicle, 3/5; Shielded):
    "For each upgrade on your base, this unit gets +1/+0 and gains Restore 1."

    One self ``ConstantAbility`` scaled by the new ``upgrades_on_controller_base``
    count on both layers (``StatBonus.count`` and ``KeywordGrant.value_count``, the
    Punishing One SEC_171 dynamic-value shape that sanitiser rule 8 recognises)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=0, count="upgrades_on_controller_base"),
                 KeywordGrant("Restore", 0, value_count="upgrades_on_controller_base")],
    )


@card_ability("HMW", "72")
def _grand_army_marine():
    """HMW_72 — Grand Army Marine (Unit, Gungan/Trooper, 2/2): "When Played: Give a
    Shield token to a friendly Gungan unit."  (It is a Gungan itself.)"""
    return TriggerAbility(trigger=WhenPlayed(), effects=[GiveToken(
        "Shield", TargetSpec(controller="friendly", kind="unit", traits=("Gungan",)))])


@card_ability("HMW", "73")
def _peppi_bow():
    """HMW_73 — Peppi Bow (Unit, Gungan, 2/3; Restore 1): "While this unit is
    upgraded, she gets +1/+1." """
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=1)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


@card_ability("HMW", "74")
def _yord_fandar():
    """HMW_74 — Yord Fandar (Unit, Force/Jedi, 2/4): "While a base has 15 or more
    damage on it, this unit gains Sentinel."  ``ANY_BASE_DAMAGE_MIN(15)`` — either
    base; the upstream Sentinel tag is rule 2's to strip (conditional self-grant)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.ANY_BASE_DAMAGE_MIN, 15),
    )


def _fambaa_shield_wall(state, source_ci, target_id, event_ctx):
    """Every friendly GROUND unit without a Shield token gets one — no choice, so
    one inline pass (the ``has_shield_token`` predicate's own test, inverted)."""
    from swu.cards.models import TokenUpgrade
    from swu.engine.tokens import attach_token
    res = state.find_instance(source_ci.instance_id)
    ps = res[0] if res is not None else state.player_by_id(actor_of(state, source_ci))
    for unit in list(ps.ground_arena):
        if not any(isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Shield"
                   for u in unit.attached_upgrades):
            attach_token(state, ps, unit, "Shield")
    return state


@card_ability("HMW", "80")
def _fambaa_shield_team():
    """HMW_80 — Fambaa Shield Team (Unit, Creature/Gungan, 4/7): "When Played: Give a
    Shield token to each friendly ground unit without a Shield token on it." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_fambaa_shield_wall)])


@card_ability("HMW", "83")
def _batcher():
    """HMW_83 — Batcher (Unit, Creature, 2/3; Restore 1): "This unit gets +1/+0 while
    defending."  ``while_target_defending`` pointed at SELF (SHD precedent)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=0)],
        while_target_defending=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:14–20 — Combat tricks, buffs & tempo
#
# Mostly composition.  The small new pieces (all self-contained reads, no
# decision kind): Conditions ENEMY_HAS_UNIQUE_UNIT, CONTROLLER_HAS_OTHER_UNIT_COST,
# CONTROLLER_ALL_RESOURCES_EXHAUSTED, CONTROLLER_ASPECT_ICONS_MIN, FIRST_ROUND;
# predicates ``no_abilities`` and the board gates
# ``controller_has_planet_base:<P>`` / ``controller_nonleader_shares_leader_trait``;
# ``KeywordGrant.value_count`` now falls back to every ``StatBonus.count`` source;
# ``WhenYouDeployLeader(opponent=)``; ``push_granted_attack(then_attack_again=)``;
# markers ``UnitsEnterPlayReady`` and ``NthUnitPlayDiscount``.
# ══════════════════════════════════════════════════════════════════════════════

_KASHYYYK_BASE = ConditionCheck(Condition.CONTROLLER_HAS_PLANET_BASE, "Kashyyyk")
_TATOOINE_BASE = ConditionCheck(Condition.CONTROLLER_HAS_PLANET_BASE, "Tatooine")


def _self_grant(*keywords, condition=None):
    """"While <condition>, this unit gains <keywords>" — the conditional self-grant
    (Hunting Nexu SHD_168); the sanitiser strips the mistagged printed keyword."""
    return ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                           effects=[KeywordGrant(k) for k in keywords],
                           condition=condition)


def _self_buff(power, condition):
    return ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                           effects=[StatBonus(power=power, hp=0)],
                           condition=condition)


def _resource_deck_top(state, ps, ready=False):
    """Resource the top card of ``ps``'s deck.  An ability-made resource enters
    EXHAUSTED (Resupply SOR_126's ruling; Chewbacca's Bowcaster HMW_127 prints it)
    unless the card says to ready it.  Returns True if a card moved."""
    from swu.engine.actions.shared import _resource_top_of_deck
    before = len(ps.resources)
    _resource_top_of_deck(state, ps)
    if len(ps.resources) == before:
        return False
    ps.resources[-1].exhausted = not ready
    return True


def _ramp_one(state, source_ci, target_id, event_ctx):
    _resource_deck_top(state, state.player_by_id(actor_of(state, source_ci)))
    return state


def _deck_not_empty(state, source_ci, event_ctx):
    return bool(state.player_by_id(actor_of(state, source_ci)).deck)


def _ready_a_resource(state, source_ci, target_id, event_ctx):
    """"Ready a (friendly) resource" — fungible, never adverse, so inline (the
    Coruscant Dissident SHD_199 helper)."""
    from swu.cards.shd.abilities import _coruscant_dissident_attack
    return _coruscant_dissident_attack(state, source_ci, target_id, event_ctx)


# ── hmw-set:14 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "91")
def _pelta_relief_frigate():
    """HMW_91 — Pelta Relief Frigate (Unit, 5/4): "When Played: Heal 2 damage from a
    friendly base and 2 damage from a friendly unit."  One ability per clause (the
    JTL_250 rule); the unit heal picks a damaged unit, so an all-healthy board
    fizzles without a prompt."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[Heal(2, TargetSpec(controller="friendly", kind="base"))]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[Heal(2, TargetSpec(controller="friendly", kind="unit",
                                                   predicates=("damaged",)))]),
    ]


@card_ability("HMW", "92")
def _starlit_purrgil():
    """HMW_92 — Starlit Purrgil (Unit, Creature, 4/5; Restore 2): "When Played: You
    may exhaust a unit."  ``ready`` is the don't-offer-a-no-op filter."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("ready",)))],
        optional=True,
    )


@card_ability("HMW", "98")
def _resonate():
    """HMW_98 — Resonate (Event, Innate, 1): "If a friendly non-leader unit shares a
    Trait with a friendly leader, heal 4 damage from a unit or base."  The new
    ``controller_nonleader_shares_leader_trait`` BOARD gate (an EventAbility has no
    condition; the event fizzles unprompted when it fails)."""
    return EventAbility(effects=[Heal(4, TargetSpec(
        controller="any", kind="unit_or_base",
        predicates=("controller_nonleader_shares_leader_trait",)))])


def _garnac_attack_again(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True, exclude_source=True)
    return state


@card_ability("HMW", "104")
def _garnac():
    """HMW_104 — Garnac (Unit, Underworld, 3/1): "While an opponent controls a <uq>
    unit, this unit gains Hidden.  When Attack Ends: You may attack with another
    unit."  The trigger stays mandatory; the granted attack's decline IS the "may"."""
    return [
        _self_grant("Hidden",
                    condition=ConditionCheck(Condition.ENEMY_HAS_UNIQUE_UNIT)),
        TriggerAbility(trigger=WhenAttackEnds(),
                       effects=[CustomEffect(fn=_garnac_attack_again)]),
    ]


@card_ability("HMW", "107")
def _stormtrooper_patrol():
    """HMW_107 — Stormtrooper Patrol (Unit, 2/4; Sentinel): "While you control another
    unit that costs 3 or more, this unit gets +2/+0." """
    return _self_buff(2, ConditionCheck(Condition.CONTROLLER_HAS_OTHER_UNIT_COST,
                                        ("min", 3)))


@card_ability("HMW", "111")
def _invasion_lander():
    """HMW_111 — Invasion Lander (Unit, 3/7): "When Played: Give each other friendly
    unit +2/+2 for this phase." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[ModifyStats(
        2, 2, TargetSpec(controller="friendly", kind="unit", predicates=("not_self",),
                         fixed=EACH_FRIENDLY),
        Duration.THIS_PHASE)])


# ── hmw-set:15 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "115")
def _leia_organa_hmw():
    """HMW_115 — Leia Organa (Unit, Official/Rebel, 2/3): "When you play another unit
    that costs 3 or less: Heal 1 damage from your base." """
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", cost_max=3),
        effects=[Heal(1, TargetSpec(controller="friendly", kind="base"))],
    )


@card_ability("HMW", "117")
def _chewbacca_hmw_117():
    """HMW_117 — Chewbacca (Unit, Wookiee, 0/5): "This unit gains Raid 1 for each
    exhausted resource you control.  While each resource you control is exhausted,
    this unit gains Overwhelm."  Raid via ``KeywordGrant.value_count`` (now any
    ``StatBonus.count`` source)."""
    return [
        ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                        effects=[KeywordGrant("Raid", 1,
                                              value_count="controller_exhausted_resources")]),
        _self_grant("Overwhelm",
                    condition=ConditionCheck(Condition.CONTROLLER_ALL_RESOURCES_EXHAUSTED)),
    ]


@card_ability("HMW", "118")
def _ryyk_blademaster():
    """HMW_118 — Ryyk Blademaster (Unit, Wookiee, 5/4): "While you control 6 or more
    resources, this unit gains Ambush and Overwhelm." """
    return _self_grant("Ambush", "Overwhelm",
                       condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_RESOURCES, 6))


@card_ability("HMW", "119")
def _saw_gerrera_hmw():
    """HMW_119 — Saw Gerrera (Unit, Rebel, 3/6): "When an opponent plays an event:
    Resource the top card of your deck."  Enters exhausted."""
    return TriggerAbility(trigger=WhenOpponentPlaysCard(card_type="event"),
                          effects=[CustomEffect(fn=_ramp_one)])


def _no_ready_next_regroup(state, source_ci, target_id, event_ctx):
    """"This unit doesn't ready during the next regroup phase" — the Carbonite
    Chamber HMW_95 flag (``cannot_ready_this_round``)."""
    res = state.find_instance(source_ci.instance_id)
    if res is not None:
        res[1].cannot_ready_this_round = True
    return state


@card_ability("HMW", "121")
def _hijacked_at_st():
    """HMW_121 — Hijacked AT-ST (Unit, 7/7; Overwhelm): "When Played: This unit
    doesn't ready during the next regroup phase." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_no_ready_next_regroup)])


def _grakchawwaa_ramp(state, source_ci, target_id, event_ctx):
    """One READY resource per other friendly Wookiee unit, counted now."""
    from swu.engine.traits import has_trait
    ps = state.player_by_id(actor_of(state, source_ci))
    n = sum(1 for u in ps.ground_arena + ps.space_arena
            if u.instance_id != source_ci.instance_id and has_trait(state, u, "Wookiee"))
    for _ in range(n):
        if not _resource_deck_top(state, ps, ready=True):
            break
    return state


@card_ability("HMW", "123")
def _king_grakchawwaa():
    """HMW_123 — King Grakchawwaa (Unit, Official/Wookiee, 6/6): "When Played: For
    each other friendly Wookiee unit, resource the top card of your deck.  Ready each
    card resourced this way." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_grakchawwaa_ramp)])


def _luminara_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, optional=True)
    return state


@card_ability("HMW", "124")
def _luminara_unduli_hmw():
    """HMW_124 — Luminara Unduli (Unit, Force/Jedi/Republic, 7/7): "When you play a
    unit (including this one): You may attack with a unit.  It gets +2/+0 for this
    attack."  ``exclude_self=False`` is the "(including this one)"."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", exclude_self=False),
        effects=[CustomEffect(fn=_luminara_attack)],
    )


# ── hmw-set:16 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "127")
def _chewbaccas_bowcaster():
    """HMW_127 — Chewbacca's Bowcaster (Upgrade, Item/Weapon, 3): "Attach to a
    non-Vehicle unit.  When Played: If attached unit is Chewbacca, resource the top
    card of your deck.  (It enters play exhausted.)"  The attach restriction is
    parsed from the text (``_upgrade_target_spec``)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_ramp_one)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Chewbacca"),
    )


@card_ability("HMW", "129")
def _child_of_dathomir():
    """HMW_129 — Child of Dathomir (Unit, Night, 1/2): "While you control 3 or more
    units (including this one), this unit gets +2/+0." """
    return _self_buff(2, ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3))


@card_ability("HMW", "131")
def _soaring_can_cell():
    """HMW_131 — Soaring Can-Cell (Unit, Creature, 1/4; Raid 1): "While you control a
    Kashyyyk base, this unit gains Ambush." """
    return _self_grant("Ambush", condition=_KASHYYYK_BASE)


@card_ability("HMW", "133")
def _wroshyr_rebel():
    """HMW_133 — Wroshyr Rebel (Unit, Rebel/Wookiee, 0/4): "This unit gets +1/+0 for
    every 2 resources you control." """
    return ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                           effects=[StatBonus(power=1, hp=0,
                                              count="controller_resources_per_2")])


@card_ability("HMW", "136")
def _lifetree_caravan():
    """HMW_136 — Lifetree Caravan (Unit, Ewok, 2/1): "When Played: If you control 3 or
    more units (including this one), you may resource the top card of your deck." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_ramp_one, available_fn=_deck_not_empty)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3),
    )


@card_ability("HMW", "137")
def _v19_skirmisher():
    """HMW_137 — V-19 Skirmisher (Unit, 3/3): "While you control 3 or more units, this
    unit gains Sentinel." """
    return _self_grant("Sentinel",
                       condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3))


@card_ability("HMW", "138")
def _commander_gree():
    """HMW_138 — Commander Gree (Unit, Clone/Republic/Trooper, 3/6): "While there are
    3 or more Command aspect icons among friendly units (including this one) and
    upgrades, this unit gains Raid 4." """
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Raid", 4)],
        condition=ConditionCheck(Condition.CONTROLLER_ASPECT_ICONS_MIN, ("Command", 3)),
    )


# ── hmw-set:17 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "141")
def _rex_hmw():
    """HMW_141 — Rex (Unit, Clone/Fringe, 5/6): "Friendly units with no abilities get
    +1/+1."  The new ``no_abilities`` predicate: a unit that lost all abilities, or
    one printing no text and having no keyword (``has_any_keyword``, which counts
    aura-granted keywords too since 2026-11-23)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", predicates=("no_abilities",)),
        effects=[StatBonus(power=1, hp=1)],
    )


@card_ability("HMW", "142")
def _wookiee_rangers():
    """HMW_142 — Wookiee Rangers (Unit, Wookiee, 5/6): "While you control another
    Wookiee unit or a Kashyyyk base, this unit gains Sentinel." """
    return _self_grant("Sentinel", condition=ConditionCheck(Condition.ANY_OF, (
        ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Wookiee"),
        _KASHYYYK_BASE,
    )))


@card_ability("HMW", "145")
def _origin_tree_shyyyo():
    """HMW_145 — Origin Tree Shyyyo (Unit, Creature, 4/8; Restore 1): "While you
    control a Kashyyyk base, the first, second, and third units you play each round
    cost 1 resource less, 2 resources less, and 3 resources less, respectively."
    The new ``NthUnitPlayDiscount`` marker."""
    return NthUnitPlayDiscount(amounts=(1, 2, 3), condition=_KASHYYYK_BASE)


def _log_trap_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, then_attack_again=True)
    return state


@card_ability("HMW", "149")
def _log_trap():
    """HMW_149 — Log Trap (Event, Trick, 2): "Attack with a friendly unit.  Then
    attack with it again, even if it's exhausted.  It can't attack bases for the
    second attack."  The new ``then_attack_again`` rider."""
    return EventAbility(effects=[CustomEffect(fn=_log_trap_attack)])


def _overgrowth_resource_self(state, source_ci, target_id, event_ctx):
    """"Resource this card" — the played event, now in its owner's discard, goes
    face down and exhausted into the resource row (Resupply SOR_126)."""
    from swu.engine.state import Zone
    ps = state.player_by_id(actor_of(state, source_ci))
    for i, ci in enumerate(ps.discard):
        if ci.instance_id == source_ci.instance_id:
            ps.discard.pop(i)
            ci.zone = Zone.RESOURCES
            ci.face_down = True
            ci.exhausted = True
            ps.resources.append(ci)
            break
    return state


@card_ability("HMW", "151")
def _overgrowth():
    """HMW_151 — Overgrowth (Event, Disaster, 5): "If you control a Kashyyyk base, a
    friendly unit deals damage equal to its power to an enemy unit.  Resource this
    card."  The Director Krennic LAW_8 shooter/victim chain behind the
    ``controller_has_planet_base:Kashyyyk`` board gate; the resource clause is
    unconditional and untargeted, so it comes last."""
    from swu.cards.law.abilities import _krennic_pick_shooter, _krennic_fire
    return EventAbility(effects=[
        CustomEffect(fn=_krennic_pick_shooter,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("controller_has_planet_base:Kashyyyk",))),
        CustomEffect(fn=_krennic_fire,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("requires_prior_target",))),
        CustomEffect(fn=_overgrowth_resource_self),
    ])


@card_ability("HMW", "164")
def _chief_chirpa():
    """HMW_164 — Chief Chirpa (Unit, Ewok, 1/5): "This unit gets +1/+0 for each other
    friendly Ewok unit." """
    return ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                           effects=[StatBonus(power=1, hp=0,
                                              count="other_controller_trait_units_Ewok")])


@card_ability("HMW", "165")
def _commandeered_tour_shuttle():
    """HMW_165 — Commandeered Tour Shuttle (Unit, 2/2): "When Played: You may ready
    another unit with 3 or less power."  ``exhausted`` keeps it from offering a
    no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(controller="any", kind="unit", power_max=3,
                                      predicates=("not_self", "exhausted")))],
        optional=True,
    )


# ── hmw-set:18 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "170")
def _han_solo_hmw():
    """HMW_170 — Han Solo (Unit, Official/Rebel, 4/7): "Action [Exhaust]: Ready
    another unit."  Offered only while some unit is exhausted (Han himself is ready
    to pay the cost, so every exhausted unit is "another")."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[ReadyCard(TargetSpec(controller="any", kind="unit",
                                      predicates=("not_self", "exhausted")))],
        title="Ready another unit",
        condition=ConditionCheck(Condition.N_PLUS_EXHAUSTED_UNITS_IN_PLAY, 1),
    )


@card_ability("HMW", "176")
def _village_troublemaker():
    """HMW_176 — Village Troublemaker (Unit, Ewok, 2/2): "While you control an Endor
    base, this unit gains Hidden and Saboteur." """
    return _self_grant("Hidden", "Saboteur", condition=_ENDOR_BASE)


@card_ability("HMW", "184")
def _aggrocrab():
    """HMW_184 — Aggrocrab (Unit, Creature, 6/4): "While you have the initiative, this
    unit costs 1 resource less to play." """
    return CostReduction(1, condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE))


@card_ability("HMW", "190")
def _enraged():
    """HMW_190 — Enraged (Upgrade, Innate, 2): "Attached unit gains Raid 2."  The
    upgrade-SELF grant the attached-upgrade keyword scan confers on the host."""
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[KeywordGrant("Raid", 2)])


@card_ability("HMW", "191")
def _hunters_instinct():
    """HMW_191 — Hunter's Instinct (Upgrade, Innate, 3): "If attached unit is a
    Creature, it gains Grit."  The attached-upgrade scan evaluates the condition
    against the HOST, so ``SOURCE_HAS_TRAIT`` reads the attached unit."""
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[KeywordGrant("Grit")],
                           condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, "Creature"))


@card_ability("HMW", "203")
def _victor_squadron():
    """HMW_203 — Victor Squadron (Unit, 5/5): "This unit enters play ready." """
    return EntersPlayReady()


@card_ability("HMW", "208")
def _luke_skywalker_hmw():
    """HMW_208 — Luke Skywalker (Unit, Force/Fringe, 1/3; Raid 1): "While it's the
    first round of the game, this unit enters play ready." """
    return EntersPlayReady(condition=ConditionCheck(Condition.FIRST_ROUND))


# ── hmw-set:19 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "209")
def _corona_squadron_x_wing():
    """HMW_209 — Corona Squadron X-Wing (Unit, 2/2): "On Attack: You may ready a
    resource."  Coruscant Dissident SHD_199's text exactly (a different name, so not
    a reprint alias)."""
    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_ready_a_resource)])


@card_ability("HMW", "210")
def _sol():
    """HMW_210 — Sol (Unit, Force/Jedi, 2/2; Shielded): "On Attack: This unit gains
    Sentinel for this phase." """
    return TriggerAbility(trigger=OnAttack(), effects=[GrantKeyword(
        "Sentinel", 0, TargetSpec(kind="unit", fixed=SELF), Duration.THIS_PHASE)])


@card_ability("HMW", "212")
def _the_chieftain():
    """HMW_212 — The Chieftain (Unit, Tusken, 2/5): "This unit gains Raid 1 for each
    other friendly Tusken unit.  While a friendly Tusken unit is defending, it gets
    +1/+0 for each Raid it has."  The second clause is ``while_target_defending``
    over friendly Tuskens with the new ``target_raid`` count."""
    return [
        ConstantAbility(target=TargetSpec(kind="unit", fixed=SELF),
                        effects=[KeywordGrant(
                            "Raid", 1, value_count="other_controller_trait_units_Tusken")]),
        ConstantAbility(target=TargetSpec(controller="friendly", kind="unit",
                                          traits=("Tusken",)),
                        effects=[StatBonus(power=1, hp=0, count="target_raid")],
                        while_target_defending=True),
    ]


def _phee_tax(state, source_ci, target_id, event_ctx):
    """"Its controller may pay 2 resources.  If they don't, exhaust that leader" —
    ``push_pay_or_exhaust`` (Look the Other Way SHD_227), decided by the deploying
    player.  A leader deployed as a Pilot upgrade is not a unit to exhaust."""
    from swu.engine.actions.scheduling import push_pay_or_exhaust
    for p in state.players:
        if p.player_id == actor_of(state, source_ci):
            continue
        ldr = p.leader_instance
        if ldr is not None and any(u.instance_id == ldr.instance_id
                                   for u in p.ground_arena + p.space_arena):
            push_pay_or_exhaust(state, ldr.instance_id, pay_amount=2)
    return state


@card_ability("HMW", "214")
def _phee_genoa():
    """HMW_214 — Phee Genoa (Unit, Underworld, 5/4; Hidden): "When an enemy leader
    deploys: Its controller may pay 2 resources.  If they don't, exhaust that
    leader."  ``WhenYouDeployLeader(opponent=True)``."""
    return TriggerAbility(trigger=WhenYouDeployLeader(opponent=True),
                          effects=[CustomEffect(fn=_phee_tax)])


@card_ability("HMW", "228")
def _lakeside_shaaks():
    """HMW_228 — Lakeside Shaaks (Unit, Creature, 4/4): "When Played: Ready a friendly
    resource." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_ready_a_resource)])


@card_ability("HMW", "230")
def _raiding_party():
    """HMW_230 — Raiding Party (Unit, Tusken, 0/6; Raid 6): "When Played: If you
    control another Tusken unit or a Tatooine base, you may exhaust a ground unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit", arena="ground",
                                        predicates=("ready",)))],
        optional=True,
        condition=ConditionCheck(Condition.ANY_OF, (
            ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Tusken"),
            _TATOOINE_BASE,
        )),
    )


# ── hmw-set:20 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "234")
def _ritual_dragon():
    """HMW_234 — Ritual Dragon (Unit, Creature, 6/9; Saboteur): "While you control a
    Tatooine base, friendly units enter play ready (including this one)."  The new
    ``UnitsEnterPlayReady`` marker."""
    return UnitsEnterPlayReady(condition=_TATOOINE_BASE)


@card_ability("HMW", "255")
def _c3po_hmw():
    """HMW_255 — C-3PO (Unit, Droid/Rebel, 2/3): "When Played: You may give an Ewok
    unit +2/+2 for this phase.  You may give a Rebel unit +2/+2 for this phase."
    Two independent optional clauses = two abilities (the Bossk LAW_31 rule)."""
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[ModifyStats(
            2, 2, TargetSpec(controller="any", kind="unit", traits=(trait,)),
            Duration.THIS_PHASE)])
        for trait in ("Ewok", "Rebel")
    ]


@card_ability("HMW", "256")
def _jedi_interceptor():
    """HMW_256 — Jedi Interceptor (Unit, 2/2): "While you control 6 or more
    resources, this unit gets +2/+0." """
    return _self_buff(2, ConditionCheck(Condition.CONTROLLER_N_PLUS_RESOURCES, 6))


@card_ability("HMW", "257")
def _ewok_archers():
    """HMW_257 — Ewok Archers (Unit, Ewok, 2/5): "While you control another unit that
    costs 3 or less, this unit gains Ambush." """
    return _self_grant("Ambush", condition=ConditionCheck(
        Condition.CONTROLLER_HAS_OTHER_UNIT_COST, ("max", 3)))


@card_ability("HMW", "259")
def _pack_guardian():
    """HMW_259 — Pack Guardian (Unit, Creature, 5/4): "While this unit is ready, it
    gains Sentinel." """
    return _self_grant("Sentinel", condition=ConditionCheck(Condition.SOURCE_READY))


@card_ability("HMW", "261")
def _ben_kenobi_hmw():
    """HMW_261 — Ben Kenobi (Unit, Force/Fringe/Jedi, 5/5): "When Played: You may
    exhaust a unit with 3 or less power.  On Attack: You may heal 3 damage from
    another unit." """
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[ExhaustCard(
            TargetSpec(controller="any", kind="unit", power_max=3, predicates=("ready",)))]),
        TriggerAbility(trigger=OnAttack(), optional=True, effects=[Heal(
            3, TargetSpec(controller="any", kind="unit",
                          predicates=("not_self", "damaged")))]),
    ]


def _shield_attached_host(state, source_ci, target_id, event_ctx):
    from swu.engine.actions.zones import _find_upgrade_host
    from swu.engine.tokens import attach_token
    host = _find_upgrade_host(state, source_ci.instance_id)
    if host is not None:
        attach_token(state, state.player_by_id(host.owner_id), host, "Shield")
    return state


@card_ability("HMW", "264")
def _heroic_bravery():
    """HMW_264 — Heroic Bravery (Upgrade, Innate, 2): "When Played: If attached unit
    is a Heroism unit, give a Shield token to it."  The Villainous Ambition HMW_252
    gate; the Shield goes on the host found from the upgrade."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_shield_attached_host)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_HAS_ASPECT, "Heroism"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:21–24 — the last combat tricks + miscellaneous abilities
#
# New small pieces: ``push_granted_attack(bonus_if_shares_trait_with_friendly=)``;
# ``AmbushCanAttackBases`` (the ``ambush`` decision gains an enemy-base option);
# ``CopyLeaderTraits`` (trait layer); ``ConstantAbility.while_target_attacking``;
# Condition ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_POWER_MAX``; predicate
# ``has_token_upgrade``; ``name_a_card`` payoff ``revoke_trait_enemy_phase``.
# ══════════════════════════════════════════════════════════════════════════════


def _familiar_strategem_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        bonus_if_shares_trait_with_friendly=True)
    return state


@card_ability("HMW", "266")
def _familiar_strategem():
    """HMW_266 — Familiar Strategem (Event, Tactic, 1): "Attack with a unit.  If it
    shares a Trait with another friendly unit, it gets +2/+0 for this attack." """
    return EventAbility(effects=[CustomEffect(fn=_familiar_strategem_attack)])


def _heal_own_base_3(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_heal
    base = state.player_by_id(actor_of(state, source_ci)).base_instance
    if base is not None:
        state = _apply_heal(state, source_ci, base.instance_id, 3)
    return state


@card_ability("HMW", "267")
def _renew():
    """HMW_267 — Renew (Event, Innate, 2): "You may defeat a Condition upgrade.  Heal 3
    damage from your base."  Targeted (optional) first, the fixed heal second — the
    one-prompt rule; the heal goes through ``_apply_heal`` so heal bookkeeping holds."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="upgrade", traits=("Condition",),
                              optional=True)),
        CustomEffect(fn=_heal_own_base_3),
    ])


# ── hmw-set:22 ────────────────────────────────────────────────────────────────


_WARRIOR_CAN_PLAY = ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_POWER_MAX,
                                   (3, 1))


def _warrior_play(state, source_ci, target_id, event_ctx):
    """Play a unit with 3 or less PRINTED power (it is in hand, nothing has buffed
    it) from hand, paying its cost, with Ambush for this phase."""
    from swu.engine.actions import push_play_from_hand, _playable_units_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    ids = frozenset(ci.instance_id for ci in _playable_units_from_hand(state, ps, None)
                    if int(getattr(ci.card_def, "power", 0) or 0) <= 3)
    if ids:
        push_play_from_hand(state, source_ci, eligible_ids=ids, grant_keyword="Ambush")
    return state


@card_ability("HMW", "18")
def _the_warrior():
    """HMW_18 — The Warrior (Leader, Tusken, 3/6).

    Undeployed: "Action [1 resource, Exhaust]: Play a unit with 3 or less power from
    your hand (paying its cost) and give it Ambush for this phase."  Deployed: Ambush,
    Raid 1 (the deploy box — keyword layer).  Gated by the new
    ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_POWER_MAX((3, 1))``, which prices in the
    Action's own 1-resource cost, so it is never offered when nothing is playable."""
    return ActivatedAbility(
        costs=[PayResources(1), ExhaustSelf()],
        effects=[CustomEffect(fn=_warrior_play)],
        title="Play a unit with 3 or less power (gains Ambush)",
        undeployed_only=True,
        condition=_WARRIOR_CAN_PLAY,
    )


@card_ability("HMW", "53")
def _fetts_firespray_hmw():
    """HMW_53 — Fett's Firespray (Unit, 6/6; Ambush): "Friendly units can attack bases
    while using Ambush."  The new ``AmbushCanAttackBases`` marker."""
    return AmbushCanAttackBases()


def _lyonie_copy_token(state, source_ci, target_id, event_ctx):
    """Give the chosen unit another copy of one of its token upgrades.  Which token
    is a choice when it carries several kinds; the controller's obvious pick is made
    for them (a documented simplification): on a friendly unit the most useful
    (Experience, then Shield, then Advantage), on an enemy unit a Weakness."""
    from swu.cards.models import TokenUpgrade
    from swu.engine.tokens import attach_token
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, unit = res
    kinds = [u.card_def.name for u in unit.attached_upgrades
             if isinstance(u.card_def, TokenUpgrade)]
    if not kinds:
        return state
    prefs: tuple[str, ...] = (("Experience", "Shield", "Advantage")
                              if holder.player_id == actor_of(state, source_ci)
                              else ("Weakness",))
    pick = next((k for k in prefs if k in kinds), kinds[0])
    attach_token(state, holder, unit, pick)
    return state


@card_ability("HMW", "57")
def _boss_lyonie():
    """HMW_57 — Boss Lyonie (Unit, Gungan/Official, 5/5): "When Played/On Attack: You
    may choose a token upgrade attached to another unit.  Give another one of those
    tokens to that unit."  The new ``has_token_upgrade`` predicate picks the unit."""
    eff = CustomEffect(fn=_lyonie_copy_token, target=TargetSpec(
        controller="any", kind="unit", predicates=("not_self", "has_token_upgrade")))
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[eff]),
        TriggerAbility(trigger=OnAttack(), optional=True, effects=[eff]),
    ]


@card_ability("HMW", "88")
def _numa():
    """HMW_88 — Numa (Unit, Rebel/Twi'lek, 4/4; Restore 1): "If this unit would be
    dealt damage, prevent 1 of that damage."  ``DamagePrevention(on_self=True)``."""
    return DamagePrevention(amount=1, on_self=True)


def _nute_volley(state, source_ci, target_id, event_ctx):
    """"Each friendly unit (including this one) deals 1 damage to a different enemy
    unit" — ``select_damage`` over enemy units, capped at the friendly unit count.
    Documented simplifications: the picks are "up to" (taking fewer is never better
    here), and the damage is dealt by Nute's ability rather than per friendly unit."""
    from swu.engine.actions import push_select_damage
    ps = state.player_by_id(actor_of(state, source_ci))
    n = len(ps.ground_arena) + len(ps.space_arena)
    if n:
        push_select_damage(state, source_ci, max_targets=n, enemy_only=True)
    return state


@card_ability("HMW", "105")
def _nute_gunray_hmw():
    """HMW_105 — Nute Gunray (Unit, Official/Separatist, 2/2): "When Played: Each
    friendly unit (including this one) deals 1 damage to a different enemy unit." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_nute_volley)])


def _first_legion_trait_names(state, controller_id):
    """Traits on the opponent's PUBLIC cards (units, their upgrades, leader, base,
    discard) — naming a trait no visible card carries is never the better pick, and
    offering the hidden zones' traits would leak them."""
    opp = next(p for p in state.players if p.player_id != controller_id)
    names: set = set()
    for zone in (opp.ground_arena, opp.space_arena, opp.base_zone, opp.discard):
        for ci in zone:
            names.update(getattr(ci.card_def, "traits", None) or ())
            for u in getattr(ci, "attached_upgrades", ()) or ():
                names.update(getattr(u.card_def, "traits", None) or ())
    return sorted(names)


def _first_legion_name(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_name_a_card
    names = _first_legion_trait_names(state, actor_of(state, source_ci))
    if names:
        push_name_a_card(state, source_ci, names=names,
                         then_payoff="revoke_trait_enemy_phase")
    return state


@card_ability("HMW", "108")
def _the_first_legion():
    """HMW_108 — The First Legion (Unit, Imperial/Trooper, 5/5): "On Attack: Name a
    trait.  Enemy cards, including those not in play, lose that trait for this
    phase."  The ``name_a_card`` decision over trait names (the opponent's public
    cards' traits), with the new ``revoke_trait_enemy_phase`` payoff: a this_phase
    ``trait_revoke`` on every enemy card in every zone."""
    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_first_legion_name)])


@card_ability("HMW", "134")
def _zam_wesell_hmw():
    """HMW_134 — Zam Wesell (Unit, Bounty Hunter/Underworld, 2/4; Hidden): "This unit
    gains each friendly leader's traits except Force, even while she's not in play."
    The new ``CopyLeaderTraits`` marker, read by the trait layer in every zone."""
    return CopyLeaderTraits(exclude=("Force",))


# ── hmw-set:23 ────────────────────────────────────────────────────────────────


@card_ability("HMW", "154")
def _dookus_solar_sailer():
    """HMW_154 — Dooku's Solar Sailer (Unit, 3/3): "When Played: If you control a unit
    that costs 1 or less, each opponent discards a card from their hand."  The
    opponent picks the card (``DiscardFromHand``)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DiscardFromHand(1, chooser="opponent")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_COST_MAX, 1),
    )


def _raze_to_ruin_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_discard_excess_from_hand
    push_discard_excess_from_hand(state, source_ci, keep=3)
    return state


@card_ability("HMW", "161")
def _raze_to_ruin():
    """HMW_161 — Raze to Ruin (Event, Disaster/Plan, 2): "Each player discards all but
    3 cards from their hand."  Smoke and Cinders SOR_174's decision at keep=3."""
    return EventAbility(effects=[CustomEffect(fn=_raze_to_ruin_fn)])


@card_ability("HMW", "162")
def _teebo():
    """HMW_162 — Teebo (Unit, Ewok, 3/1; Hidden): "Other friendly Ewok units gain
    Hidden." """
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Ewok",),
                          predicates=("not_self",)),
        effects=[KeywordGrant("Hidden")],
    )


def _volley_pick_shooter(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly unit and its Raid (read now)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.keywords import keyword_value, Keyword
    event_ctx["prior_target_id"] = target_id
    event_ctx["krennic_damage"] = keyword_value(state, res[1], Keyword.RAID)
    return state


@card_ability("HMW", "192")
def _volley_fire():
    """HMW_192 — Volley Fire (Event, Tactic, 1): "A friendly unit deals damage equal
    to its Raid to an enemy unit."  The Krennic LAW_8 shooter/victim chain with the
    shooter's Raid as the amount; only units with Raid are offered as shooters."""
    from swu.cards.law.abilities import _krennic_fire
    return EventAbility(effects=[
        CustomEffect(fn=_volley_pick_shooter,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("has_keyword_raid",))),
        CustomEffect(fn=_krennic_fire,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("requires_prior_target",))),
    ])


def _new_tactics_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_put_on_deck
    if target_id is not None:
        push_put_on_deck(state, source_ci, target_id)
    return state


@card_ability("HMW", "218")
def _new_tactics():
    """HMW_218 — New Tactics (Event, Learned/Tactic, 5): "Choose a non-leader unit.
    Its owner puts it on the top or bottom of their deck."  Qui-Gon Jinn LOF_200's
    ``push_put_on_deck`` (the owner decides top vs bottom)."""
    return EventAbility(effects=[CustomEffect(
        fn=_new_tactics_fn,
        target=TargetSpec(controller="any", kind="unit", predicates=("non_leader",)))])


def _teeka_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


@card_ability("HMW", "221")
def _teeka():
    """HMW_221 — Teeka (Unit, Jawa, 2/2; Sentinel): "When Played: Choose one: Give a
    unit Sentinel for this phase. / A unit loses Sentinel for this phase."  The
    ``choose_two_modal`` selector at pick=1, options as ``EventAbility`` (the Hunter
    HMW_35 shape) so a unit's options are never trigger-collected."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_teeka_choose)]),
        EventAbility(effects=[GrantKeyword("Sentinel", 0,
                                           TargetSpec(controller="any", kind="unit"),
                                           Duration.THIS_PHASE)]),
        EventAbility(effects=[RevokeKeyword("Sentinel",
                                            TargetSpec(controller="any", kind="unit",
                                                       predicates=("has_sentinel",)),
                                            Duration.THIS_PHASE)]),
    ]


def _therm_reveal(state, source_ci, target_id, event_ctx):
    """Look at (reveal) the top card of each deck — the controller's and the
    opponent's — and take −2/−2 for this phase per card costing 3 or more."""
    from swu.engine.state import Modifier
    hits = 0
    for p in state.players:
        if p.deck and int(getattr(p.deck[0].card_def, "cost", 0) or 0) >= 3:
            hits += 1
    if hits:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=source_ci.instance_id,
            kind="stats",
            value={"power": -2 * hits, "hp": -2 * hits},
            duration="this_phase",
        ))
    return state


@card_ability("HMW", "223")
def _therm_scissorpunch():
    """HMW_223 — Therm Scissorpunch (Unit, Underworld, 5/5): "When the action phase
    starts: Reveal the top card of your deck and an opponent's deck.  For each card
    that costs 3 or more revealed this way, this unit gets –2/–2 for this phase." """
    return TriggerAbility(trigger=PhaseStartTrigger("action"),
                          effects=[CustomEffect(fn=_therm_reveal)])


# ── hmw-set:24 ────────────────────────────────────────────────────────────────


def _boba_arm_ambusher(state, source_ci, target_id, event_ctx):
    """"Give it Raid 1 and Saboteur for this phase" — the unit that just entered
    (``event_ctx["source_id"]``), before its Ambush decision (Phase-3 triggers resolve
    above the keyword bus)."""
    from swu.engine.state import Modifier
    uid = event_ctx.get("source_id")
    if not uid or state.find_instance(uid) is None:
        return state
    for kw, val in (("Raid", 1), ("Saboteur", 0)):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=uid,
            kind="keyword_grant",
            value={"keyword": kw, "value": val},
            duration="this_phase",
        ))
    return state


@card_ability("HMW", "225")
def _boba_fett_hmw():
    """HMW_225 — Boba Fett (Unit, Tusken, 1/5; Ambush): "When a friendly unit with
    Ambush enters play: Give it Raid 1 and Saboteur for this phase."  Boba himself
    counts.  A deployed leader enters by deploying, not entering play from a card, so
    it is not covered (documented)."""
    return TriggerAbility(
        trigger=WhenUnitEntersPlay(filter=TargetSpec(
            controller="friendly", kind="unit", predicates=("has_keyword_ambush",))),
        effects=[CustomEffect(fn=_boba_arm_ambusher, grants_keywords=("Raid", "Saboteur"))],
    )


@card_ability("HMW", "233")
def _awakened_exogorth():
    """HMW_233 — Awakened Exogorth (Unit, Creature, 7/7; Hidden): "While this unit is
    attacking, the defending unit gets –3/–0."  Strafing Gunship SOR_212's
    ``while_attacking``."""
    return ConstantAbility(target=TargetSpec(controller="enemy", kind="unit"),
                           effects=[StatBonus(power=-3, hp=0)],
                           while_attacking=True)


@card_ability("HMW", "243")
def _sun_fac():
    """HMW_243 — Sun Fac (Unit, Separatist, 2/3): "When Played: Give a unit Grit for
    this phase." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[GrantKeyword(
        "Grit", 0, TargetSpec(controller="any", kind="unit"), Duration.THIS_PHASE)])


@card_ability("HMW", "246")
def _pyke_sarisa():
    """HMW_246 — Pyke Sarisa (Unit, 4/3; Sentinel): "When Played: Give a unit Sentinel
    for this phase." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[GrantKeyword(
        "Sentinel", 0, TargetSpec(controller="any", kind="unit"), Duration.THIS_PHASE)])


@card_ability("HMW", "251")
def _blockade_ship():
    """HMW_251 — Blockade Ship (Unit, 5/8; Sentinel): "Enemy ground units get –1/–0
    while attacking."  The new ``while_target_attacking`` flag."""
    return ConstantAbility(target=TargetSpec(controller="enemy", kind="unit",
                                             arena="ground"),
                           effects=[StatBonus(power=-1, hp=0)],
                           while_target_attacking=True)


@card_ability("HMW", "260")
def _queen_amidala_hmw():
    """HMW_260 — Queen Amidala (Unit, Naboo/Official, 4/4; Restore 2): "If you control
    an upgraded base, this unit costs 2 resources less to play." """
    return CostReduction(2, condition=ConditionCheck(Condition.CONTROLLER_BASE_UPGRADED))


def _kalikori_search(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_search_and_play_multiple
    push_search_and_play_multiple(
        state, source_ci, window=8, budget=5,
        eligible=lambda cd: isinstance(cd, Unit)
        and "Twi'lek" in (getattr(cd, "traits", ()) or ()))
    return state


@card_ability("HMW", "265")
def _twilek_kalikori():
    """HMW_265 — Twi'lek Kalikori (Upgrade, Item, 4): "When Played: If attached unit
    is a Twi'lek, search the top 8 cards of your deck for any number of Twi'lek units
    with combined cost 5 or less and play each of them for free."  L3-37 LAW_63's
    ``push_search_and_play_multiple``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_kalikori_search)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_HAS_TRAIT, "Twi'lek"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:25 — the first Weakness-token cards
#
# The Weakness token is a TokenUpgrade DB row (−1/−1, no text), so
# ``GiveToken("Weakness", …)`` / ``attach_token`` need no machinery.  The framework
# session behind it fixed ``compute_hp``'s floor (1 → 0, so 0 HP is lethal) and the
# bot's GiveToken / select_token polarity — see tests/test_weakness_token.py.
# HMW_2 (Maz) shares its number with the Weakness token and HMW_3 (Hemlock) with
# the Beast token: both register only token-safe spec kinds (module docstring).
# ══════════════════════════════════════════════════════════════════════════════


def _weakness_to(target):
    return GiveToken("Weakness", target)


_ANY_UNIT = TargetSpec(controller="any", kind="unit")

_MAZ_CAN_PLAY = ConditionCheck(Condition.ANY_OF, (
    ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND, ("Fringe", 1)),
    ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND, ("Underworld", 1)),
))


def _maz_play(state, source_ci, target_id, event_ctx):
    """"Play a Fringe or Underworld unit from your hand.  It costs 1 resource less.
    Give a Weakness token to it." — ``push_play_from_hand`` with the either-trait
    pool as ``eligible_ids`` and the token as ``then_tokens`` (Three Lessons
    LOF_225's rider: it lands on the played unit)."""
    from swu.engine.actions import push_play_from_hand, _playable_units_from_hand
    from swu.engine.traits import has_trait
    ps = state.player_by_id(actor_of(state, source_ci))
    ids = frozenset(ci.instance_id for ci in _playable_units_from_hand(state, ps, None, 1)
                    if has_trait(state, ci, "Fringe") or has_trait(state, ci, "Underworld"))
    if ids:
        push_play_from_hand(state, source_ci, eligible_ids=ids, cost_reduction=1,
                            then_tokens=["Weakness"])
    return state


@card_ability("HMW", "2")
def _maz_kanata_hmw():
    """HMW_2 — Maz Kanata (Leader, Underworld, 4/4).

    Undeployed: "Action [Exhaust]: Play a Fringe or Underworld unit from your hand.
    It costs 1 resource less.  Give a Weakness token to it."  Deployed: "Hidden.
    Action: <the same>."  Both gated so they are never offered with nothing to
    play.  ⚠ HMW_2 is also the Weakness token's number: only ActivatedAbility specs
    (an attached token offers no plain Action), each side-gated."""
    return [
        ActivatedAbility(costs=[ExhaustSelf()], effects=[CustomEffect(fn=_maz_play)],
                         title="Play a Fringe or Underworld unit (1 less, Weakness)",
                         undeployed_only=True, condition=_MAZ_CAN_PLAY),
        ActivatedAbility(costs=[], effects=[CustomEffect(fn=_maz_play)],
                         title="Play a Fringe or Underworld unit (1 less, Weakness)",
                         deployed_only=True, condition=_MAZ_CAN_PLAY),
    ]


@card_ability("HMW", "3")
def _doctor_hemlock():
    """HMW_3 — Doctor Hemlock (Leader, Imperial/Official, 3/6).

    Undeployed: "Action [1 resource, Exhaust]: Give a Weakness token to a unit
    without a Weakness token on it."  Deployed: "On Attack: You may give a Weakness
    token to a unit."  ⚠ HMW_3 is also the Beast token's number: an
    ``undeployed_only`` Action and a ``deployed_only`` trigger only."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[_weakness_to(TargetSpec(controller="any", kind="unit",
                                             predicates=("lacks_token:Weakness",)))],
            title="Give a Weakness token to a unit without one",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ANY_UNIT_LACKS_TOKEN, "Weakness"),
        ),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[_weakness_to(_ANY_UNIT)]),
    ]


def _bossk_heal_and_weaken(state, source_ci, target_id, event_ctx):
    """"Heal 1 damage from a damaged enemy unit and give a Weakness token to it" —
    one target, both halves (so they can never split across two units)."""
    from swu.abilities.resolver import _apply_heal
    from swu.engine.tokens import attach_token
    if target_id is None:
        return state
    state = _apply_heal(state, source_ci, target_id, 1)
    res = state.find_instance(target_id)
    if res is not None:
        attach_token(state, res[0], res[1], "Weakness")
    return state


@card_ability("HMW", "15")
def _bossk_hmw():
    """HMW_15 — Bossk (Leader, Bounty Hunter/Underworld, 4/5).

    Undeployed: "Action [Exhaust]: Heal 1 damage from a damaged enemy unit and give a
    Weakness token to it."  Deployed: "On Attack: You may deal 2 damage to a unit
    with a token upgrade on it."  (``has_token_upgrade``, Boss Lyonie HMW_57.)"""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_bossk_heal_and_weaken,
                                  target=TargetSpec(controller="enemy", kind="unit",
                                                    predicates=("damaged",)))],
            title="Heal 1 from a damaged enemy unit; give it a Weakness token",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ENEMY_HAS_DAMAGED_UNIT),
        ),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                                         predicates=("has_token_upgrade",)))]),
    ]


@card_ability("HMW", "40")
def _talzins_shuttle():
    """HMW_40 — Talzin's Shuttle (Unit, Night/Transport/Vehicle, 2/4; Raid 1): "When
    Played: If an opponent played 2 or more cards this phase, you may give 2 Weakness
    tokens to a unit." """
    return TriggerAbility(
        trigger=WhenPlayed(), optional=True,
        effects=[GiveToken("Weakness", _ANY_UNIT, count=2)],
        condition=ConditionCheck(Condition.OPPONENT_CARDS_PLAYED_THIS_PHASE_MIN, 2),
    )


@card_ability("HMW", "59")
def _clone_x_assassin():
    """HMW_59 — Clone X Assassin (Unit, Clone/Imperial/Trooper, 1/3): "When Defeated:
    You may give a Weakness token to a unit." """
    return TriggerAbility(trigger=WhenDefeated(), optional=True,
                          effects=[_weakness_to(_ANY_UNIT)])


def _nuvo_weaken_once(state, source_ci, target_id, event_ctx):
    """Give the Weakness and spend the once-per-round charge on USE (the Dengar
    LAW_53 / Toro Calican SHD_239 ``{iid}:trig`` marker), so a decline costs nothing."""
    from swu.engine.tokens import attach_token
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is not None:
        attach_token(state, res[0], res[1], "Weakness")
    return state


@card_ability("HMW", "62")
def _nuvo_vindi():
    """HMW_62 — Nuvo Vindi (Unit, Separatist, 1/4): "When Played: You may give a
    Weakness token to a unit.  When an enemy unit with a Weakness token on it is
    defeated: You may give a Weakness token to a unit.  Use this ability only once
    each round."  The defeated unit's tokens are read off
    ``event_ctx["defeated_upgrades"]`` by the new ``had_token:<Name>`` predicate."""
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[_weakness_to(_ANY_UNIT)]),
        TriggerAbility(
            trigger=WhenUnitDefeated(filter=TargetSpec(
                controller="enemy", kind="unit", predicates=("had_token:Weakness",))),
            optional=True,
            effects=[CustomEffect(fn=_nuvo_weaken_once, target=_ANY_UNIT)],
            condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        ),
    ]


@card_ability("HMW", "65")
def _clone_of_the_zillo_beast():
    """HMW_65 — Clone of the Zillo Beast (Unit, Clone/Creature, 6/6): "Other friendly
    units get –2/–2.  On Attack: You may give a Weakness token to a unit."  With the
    0-HP floor, the aura really defeats a friendly 2-HP unit, as printed."""
    return [
        ConstantAbility(target=TargetSpec(controller="friendly", kind="unit",
                                          predicates=("not_self",)),
                        effects=[StatBonus(power=-2, hp=-2)]),
        TriggerAbility(trigger=OnAttack(), optional=True,
                       effects=[_weakness_to(_ANY_UNIT)]),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:26 — Weakness-token cards
# ══════════════════════════════════════════════════════════════════════════════

_IN_ARENA = ("GROUND_ARENA", "SPACE_ARENA")


def _attach_weakness(state, target_id, count):
    """Give ``count`` Weakness tokens to ``target_id``, stopping if it leaves play
    (a unit at 0 HP is defeated as the tokens land)."""
    from swu.engine.tokens import attach_token
    given = 0
    for _ in range(count):
        res = state.find_instance(target_id) if target_id else None
        if res is None or res[1].zone.name not in _IN_ARENA:
            break
        attach_token(state, res[0], res[1], "Weakness")
        given += 1
    return given


def _progenitor_breed(state, source_ci, target_id, event_ctx):
    """Give this unit a Weakness, then create a Beast per Weakness token on it."""
    from swu.engine.actions import _create_token_units
    if not _attach_weakness(state, source_ci.instance_id, 1):
        return state
    res = state.find_instance(source_ci.instance_id)
    me = res[1] if res is not None else source_ci
    n = sum(1 for u in me.attached_upgrades or ()
            if getattr(u.card_def, "name", None) == "Weakness")
    if n:
        _create_token_units(state, state.player_by_id(actor_of(state, source_ci)),
                            "Beast", n)
    return state


@card_ability("HMW", "67")
def _the_great_progenitor():
    """HMW_67 — The Great Progenitor (Unit, Creature, 4/7): "When Attack Ends: You
    may give a Weakness token to this unit.  If you do, create a Beast token for
    each Weakness token on this unit."  ``WhenAttackEnds`` fires only for a
    survivor, and the count includes the token just given."""
    return TriggerAbility(trigger=WhenAttackEnds(), optional=True,
                          effects=[CustomEffect(fn=_progenitor_breed)])


def _ravage_distribute(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Weakness", max_targets=3,
                      controller="any", allow_repeats=True)
    return state


@card_ability("HMW", "71")
def _ravage():
    """HMW_71 — Ravage (Event, Disaster/Tactic, 4): "Distribute up to 3 Weakness
    tokens among any number of units."  ``push_select_token(allow_repeats=True)``,
    the Elzar Mann ASH_224 pool."""
    return EventAbility(effects=[CustomEffect(fn=_ravage_distribute)])


@card_ability("HMW", "87")
def _venomous_wyyyshokk():
    """HMW_87 — Venomous Wyyyshokk (Unit, Creature, 3/4): "When Defeated: You may
    give a Weakness token to a damaged unit." """
    return TriggerAbility(trigger=WhenDefeated(), optional=True,
                          effects=[_weakness_to(TargetSpec(controller="any", kind="unit",
                                                           predicates=("damaged",)))])


@card_ability("HMW", "97")
def _dire_prowess():
    """HMW_97 — Dire Prowess (Upgrade, Learned, 2): "When Played: You may give a
    Weakness token to a unit." """
    return TriggerAbility(trigger=WhenPlayed(), optional=True,
                          effects=[_weakness_to(_ANY_UNIT)])


def _torrent(state, source_ci, target_id, event_ctx):
    _attach_weakness(state, target_id, 2 if _NABOO_BASE.evaluate(state, source_ci) else 1)
    return state


@card_ability("HMW", "100")
def _torrent_hmw():
    """HMW_100 — Torrent (Event, Disaster, 2): "Give a Weakness token to a unit.  If
    you control a Naboo base, give 2 Weakness tokens to that unit instead." """
    return EventAbility(effects=[CustomEffect(fn=_torrent, target=_ANY_UNIT)])


def _magnaguard_grant_replay(state, source_ci, target_id, event_ctx):
    """The Second Chance SHD_53 free-replay permission, plus the 2 Weakness tokens
    the replay attaches (``discard_replay_tokens_this_phase``) — only if it had 5
    or more power when defeated."""
    if int((event_ctx or {}).get("defeated_power", 0) or 0) < 5:
        return state
    iid = source_ci.instance_id
    state.game_memory.free_discard_play_this_phase.add(iid)
    state.game_memory.discard_replay_tokens_this_phase[iid] = ["Weakness", "Weakness"]
    return state


@card_ability("HMW", "109")
def _tireless_magnaguard():
    """HMW_109 — Tireless Magnaguard (Unit, Droid/Separatist, 5/3): "When Defeated: If
    this unit had 5 or more power, for this phase you may play this unit from your
    discard pile for free and give 2 Weakness tokens to it."  The power is the
    last-known ``defeated_power``; the "may" is the free ``PlayFromDiscard`` itself."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_magnaguard_grant_replay)],
    )


def _palpatine_steal(state, source_ci, target_id, event_ctx):
    """Take control of the unit; if you do, give it 2 Weakness tokens."""
    from swu.engine.actions import change_control
    res = state.find_instance(target_id) if target_id else None
    if res is None:
        return state
    me = actor_of(state, source_ci)
    change_control(state, res[1], me)
    after = state.find_instance(target_id)
    if after is not None and after[0].player_id == me:
        _attach_weakness(state, target_id, 2)
    return state


@card_ability("HMW", "110")
def _emperor_palpatine_hmw():
    """HMW_110 — Emperor Palpatine (Unit, Force/Imperial/Official/Sith, 3/2): "When
    Played: You may take control of an enemy non-leader unit that costs 3 or less.
    If you do, give 2 Weakness tokens to it."  The Commandeer JTL_235 shape."""
    return TriggerAbility(
        trigger=WhenPlayed(), optional=True,
        effects=[CustomEffect(fn=_palpatine_steal, target=TargetSpec(
            controller="enemy", kind="unit", cost_max=3, predicates=("non_leader",)))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:27 — Weakness-token cards
# ══════════════════════════════════════════════════════════════════════════════


def _qimir_mill(state, source_ci, target_id, event_ctx):
    """Discard the top card of your deck; if it's not Villainy, give a Weakness
    token to an enemy unit (the Rickety Quadjumper LAW_115 shape, chosen after the
    card is seen)."""
    from swu.engine.actions import discard_from_deck, push_select_token
    milled = discard_from_deck(state, state.player_by_id(actor_of(state, source_ci)), 1)
    if not milled:
        return state
    aspects = {a.name for a in (getattr(milled[0].card_def, "aspects", None) or ())}
    if "Villainy" not in aspects:
        push_select_token(state, source_ci, token_type="Weakness", max_targets=1,
                          controller="enemy", mandatory=True)
    return state


@card_ability("HMW", "196")
def _qimir():
    """HMW_196 — Qimir (Unit, Force, 3/1): "When Defeated: You may discard the top
    card of your deck.  If it's not Villainy, give a Weakness token to an enemy
    unit." """
    return TriggerAbility(trigger=WhenDefeated(), optional=True,
                          effects=[CustomEffect(fn=_qimir_mill)])


def _cid_opponent_weakens(state, source_ci, target_id, event_ctx):
    """"An opponent chooses a unit they control" — the Sabine Wren ASH_6 shape:
    ``controller`` reads from the source's side, so "theirs" is "enemy"."""
    from swu.engine.actions import push_select_token
    me_idx = state.player_index(actor_of(state, source_ci))
    push_select_token(state, source_ci, token_type="Weakness", max_targets=1,
                      controller="enemy", decider_id=state.players[1 - me_idx].player_id,
                      after_resolve_idx=1 - me_idx, mandatory=True)
    return state


@card_ability("HMW", "197")
def _cid_scaleback():
    """HMW_197 — Cid Scaleback (Unit, Underworld, 2/2): "When Played: An opponent
    chooses a unit they control.  Give a Weakness token to it." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_cid_opponent_weakens)])


def _picador_breed(state, source_ci, target_id, event_ctx):
    """Create the Beast first, so it is one of the friendly units the Weakness can
    go to."""
    from swu.engine.actions import _create_token_units, push_select_token
    _create_token_units(state, state.player_by_id(actor_of(state, source_ci)), "Beast", 1)
    push_select_token(state, source_ci, token_type="Weakness", max_targets=1,
                      controller="friendly", mandatory=True)
    return state


@card_ability("HMW", "199")
def _geonosian_picador():
    """HMW_199 — Geonosian Picador (Unit, Separatist, 2/2): "When Played: Create a
    Beast token.  Then, give a Weakness token to a friendly unit." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_picador_breed)])


def _rish_loo_steal(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import change_control
    res = state.find_instance(target_id) if target_id else None
    if res is None:
        return state
    change_control(state, res[1], actor_of(state, source_ci))
    res[1].return_control_to_owner_at_regroup = True
    return state


@card_ability("HMW", "200")
def _rish_loo():
    """HMW_200 — Rish Loo (Unit, Gungan/Official/Separatist, 3/2; Hidden): "When
    Played: Take control of an enemy non-leader unit with a Weakness token on it.
    At the start of the next regroup phase, its owner takes control of it."  Change
    of Heart SOR_224's take-and-revert; ``had_token:`` reads a live unit's tokens."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(
        fn=_rish_loo_steal,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader", "had_token:Weakness")))])


def _inferno_strike(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the unit and give it a Weakness token (one target)."""
    from swu.abilities.resolver import _apply_deal_damage
    if target_id is None:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
    _attach_weakness(state, target_id, 1)
    return state


@card_ability("HMW", "202")
def _inferno_squad_hmw():
    """HMW_202 — Inferno Squad (Unit, Imperial/Trooper, 3/6): "When Played/When
    Defeated: You may deal 1 damage to a unit and give a Weakness token to it." """
    strike = CustomEffect(fn=_inferno_strike, target=_ANY_UNIT)
    return [TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[strike]),
            TriggerAbility(trigger=WhenDefeated(), optional=True, effects=[strike])]


def _dragonboat_weaken(state, source_ci, target_id, event_ctx):
    """Give a Weakness token; if the unit is unique, exhaust it."""
    if not _attach_weakness(state, target_id, 1):
        return state
    res = state.find_instance(target_id)
    if res is not None and res[1].zone.name in _IN_ARENA and getattr(
            res[1].card_def, "is_unique", False):
        res[1].exhausted = True
    return state


@card_ability("HMW", "231")
def _dragonboat_freighter():
    """HMW_231 — Dragonboat Freighter (Unit, Transport/Underworld/Vehicle, 5/5):
    "When Played: You may give a Weakness token to a unit.  If it's a unique unit,
    exhaust it." """
    return TriggerAbility(trigger=WhenPlayed(), optional=True,
                          effects=[CustomEffect(fn=_dragonboat_weaken, target=_ANY_UNIT)])


def _easy_prey(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _create_token_units
    me = state.player_by_id(actor_of(state, source_ci))
    opp = state.players[1 - state.player_index(me.player_id)]
    _create_token_units(state, me, "Beast", 1)
    theirs = _create_token_units(state, opp, "Beast", 1)
    if theirs:
        _attach_weakness(state, theirs[0].instance_id, 1)
    return state


@card_ability("HMW", "237")
def _easy_prey_hmw():
    """HMW_237 — Easy Prey (Event, Innate, 1): "Create a Beast token.  An opponent
    creates a Beast token.  Give a Weakness token to it." """
    return EventAbility(effects=[CustomEffect(fn=_easy_prey)])


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:28 — Weakness-token cards
# ══════════════════════════════════════════════════════════════════════════════


def _sandstorm_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[2, 3], pick=1)
    return state


def _sandstorm_arena(arena):
    def _fn(state, source_ci, target_id, event_ctx):
        me = actor_of(state, source_ci)
        for ps in state.players:
            if ps.player_id == me:
                continue
            units = ps.ground_arena if arena == "ground" else ps.space_arena
            for iid in [u.instance_id for u in units if u.exhausted]:
                _attach_weakness(state, iid, 1)
        return state
    return _fn


@card_ability("HMW", "240")
def _sandstorm():
    """HMW_240 — Sandstorm (Event, Disaster, 3): "While you control a Tatooine base,
    this event costs 1 resource less to play.  Choose an arena.  Give a Weakness
    token to each exhausted enemy unit in that arena."  The Seismic Detonation
    HMW_54 arena selector (indices 2 = ground, 3 = space; 0 is the discount)."""
    return [
        CostReduction(1, condition=_TATOOINE_BASE),
        EventAbility(effects=[CustomEffect(fn=_sandstorm_choose)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_sandstorm_arena("ground"))]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_sandstorm_arena("space"))]),
    ]


@card_ability("HMW", "242")
def _occupation_officer():
    """HMW_242 — Occupation Officer (Unit, Imperial, 3/2): "When Played: If you
    control 6 or more resources, you may give a Weakness token to a unit." """
    return TriggerAbility(
        trigger=WhenPlayed(), optional=True,
        effects=[_weakness_to(_ANY_UNIT)],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_RESOURCES, 6),
    )


def _defoliator_victim(state, source_ci, event_ctx):
    """The defending unit, if it isn't a Droid or Vehicle and you can pay 2."""
    from swu.engine.traits import has_trait
    did = (event_ctx or {}).get("defender_id")
    res = state.find_instance(did) if did else None
    if res is None or res[1].zone.name not in _IN_ARENA:
        return None
    if has_trait(state, res[1], "Droid") or has_trait(state, res[1], "Vehicle"):
        return None
    ps = state.player_by_id(actor_of(state, source_ci))
    if sum(1 for r in ps.resources if not r.exhausted) < 2:
        return None
    return res[1]


def _defoliator_can(state, source_ci, event_ctx):
    return _defoliator_victim(state, source_ci, event_ctx) is not None


def _defoliator_pay_and_weaken(state, source_ci, target_id, event_ctx):
    """Pay 2 and give 2 Weakness tokens — one effect, so the tokens only come with
    the payment."""
    from swu.engine.actions.costs import _exhaust_resources
    victim = _defoliator_victim(state, source_ci, event_ctx)
    if victim is None:
        return state
    _exhaust_resources(state.player_by_id(actor_of(state, source_ci)), 2)
    _attach_weakness(state, victim.instance_id, 2)
    return state


@card_ability("HMW", "248")
def _defoliator_tank():
    """HMW_248 — Defoliator Tank (Unit, Separatist/Tank/Vehicle, 4/6; Overwhelm):
    "On Attack: If the defending unit isn't a Droid or Vehicle, you may pay 2
    resources.  If you do, give 2 Weakness tokens to it."  A base defender, a Droid
    or Vehicle, or fewer than 2 ready resources: no prompt."""
    return TriggerAbility(
        trigger=OnAttack(), optional=True,
        effects=[CustomEffect(fn=_defoliator_pay_and_weaken,
                              available_fn=_defoliator_can)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:29 — Beast-token cards
#
# The Beast token is a vanilla 3/3 ground Creature TokenUnit row, so
# ``CreateTokenUnit("Beast")`` / ``_create_token_units`` need no machinery.
# Mysterious Disappearance HMW_58 ("A player chooses a non-leader unit they
# control.  You may defeat that unit.  If you do, that player creates a Beast
# token.") is NOT encoded: it needs a choose-a-player → that player picks → you
# confirm flow (a new ``opponent_chooses_target`` disposition with bot and web
# handling) — flagged for a framework session.
# ══════════════════════════════════════════════════════════════════════════════


def _ready_resources(state, source_ci):
    ps = state.player_by_id(actor_of(state, source_ci))
    return sum(1 for r in ps.resources if not r.exhausted)


def _tarfful_can_pay(state, source_ci, event_ctx):
    return _ready_resources(state, source_ci) >= 1


def _tarfful_pay_for_beast(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, create a Beast token." """
    from swu.engine.actions import _create_token_units
    from swu.engine.actions.costs import _exhaust_resources
    if _ready_resources(state, source_ci) < 1:
        return state
    ps = state.player_by_id(actor_of(state, source_ci))
    _exhaust_resources(ps, 1)
    _create_token_units(state, ps, "Beast", 1)
    return state


@card_ability("HMW", "10")
def _tarfful():
    """HMW_10 — Tarfful (Leader, Rebel/Wookiee, 3/7).

    Undeployed: "Action [2 resources, Exhaust, discard a card from your hand]:
    Create a Beast token."  Deployed: "Sentinel.  On Attack: You may pay 1
    resource.  If you do, create a Beast token."  Sentinel and the Epic Action
    deploy are generic."""
    return [
        ActivatedAbility(costs=[PayResources(2), ExhaustSelf(), DiscardCardCost()],
                         effects=[CreateTokenUnit("Beast")],
                         title="Create a Beast token", undeployed_only=True),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[CustomEffect(fn=_tarfful_pay_for_beast,
                                             available_fn=_tarfful_can_pay)]),
    ]


def _poggle_rouse(state, source_ci, target_id, event_ctx):
    """Ready the friendly Creature and deal 1 damage to it."""
    from swu.abilities.resolver import _apply_deal_damage
    res = state.find_instance(target_id) if target_id else None
    if res is None or res[1].zone.name not in _IN_ARENA:
        return state
    res[1].exhausted = False
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci), source_id=source_ci.instance_id)
    return state


_FRIENDLY_CREATURE = TargetSpec(controller="friendly", kind="unit", traits=("Creature",))


@card_ability("HMW", "12")
def _poggle_the_lesser():
    """HMW_12 — Poggle the Lesser (Leader, Official/Separatist, 1/6).

    Undeployed: "Action [1 resource, Exhaust]: Ready a friendly Creature unit and
    deal 1 damage to it."  Deployed: "When Deployed: Create a Beast token.  On
    Attack: You may ready a friendly Creature unit and deal 1 damage to it."  The
    Action is gated on a friendly Creature existing (no no-op Action)."""
    rouse = CustomEffect(fn=_poggle_rouse, target=_FRIENDLY_CREATURE)
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()], effects=[rouse],
                         title="Ready a friendly Creature; deal 1 damage to it",
                         undeployed_only=True,
                         condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT,
                                                  "Creature")),
        TriggerAbility(trigger=WhenDeployed(), effects=[CreateTokenUnit("Beast")]),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[rouse]),
    ]


@card_ability("HMW", "38")
def _bestial_bond():
    """HMW_38 — Bestial Bond (Upgrade, Innate, 3): "When Played: If attached unit is
    a Creature or a Force unit, create a Beast token." """
    return TriggerAbility(
        trigger=WhenPlayed(), effects=[CreateTokenUnit("Beast")],
        condition=ConditionCheck(Condition.ANY_OF, (
            ConditionCheck(Condition.ATTACHED_HOST_HAS_TRAIT, "Creature"),
            ConditionCheck(Condition.ATTACHED_HOST_HAS_TRAIT, "Force"),
        )),
    )


@card_ability("HMW", "47")
def _eravana():
    """HMW_47 — Eravana (Unit, Transport/Underworld/Vehicle, 1/7): "On Attack: Create
    a Beast token and ready it." """
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CreateTokenUnit("Beast", enters_ready=True)])


def _boss_nass_swap(state, source_ci, target_id, event_ctx):
    """Defeat a Shield on the chosen friendly Gungan; if one came off, create a Beast
    and give it a Shield (the Rose Tico SHD_45 "if you do" binding)."""
    from swu.engine import tokens
    from swu.engine.actions import _create_token_units
    res = state.find_instance(target_id) if target_id else None
    if res is None or not tokens.defeat_shield(state, res[1]):
        return state
    ps = state.player_by_id(actor_of(state, source_ci))
    for beast in _create_token_units(state, ps, "Beast", 1):
        tokens.attach_token(state, ps, beast, "Shield")
    return state


@card_ability("HMW", "77")
def _boss_nass():
    """HMW_77 — Boss Nass (Unit, Gungan/Official, 4/6): "When Played/On Attack: You
    may defeat a Shield token on a friendly Gungan unit.  If you do, create a Beast
    token and give a Shield token to it." """
    swap = CustomEffect(fn=_boss_nass_swap, target=TargetSpec(
        controller="friendly", kind="unit", traits=("Gungan",),
        predicates=("has_shield_token",)))
    return [TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[swap]),
            TriggerAbility(trigger=OnAttack(), optional=True, effects=[swap])]


@card_ability("HMW", "144")
def _howler_pack():
    """HMW_144 — Howler Pack (Unit, Creature, 3/3): "When Played/When Defeated:
    Create a Beast token." """
    return [TriggerAbility(trigger=WhenPlayed(), effects=[CreateTokenUnit("Beast")]),
            TriggerAbility(trigger=WhenDefeated(), effects=[CreateTokenUnit("Beast")])]


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:30 — Beast-token cards
# ══════════════════════════════════════════════════════════════════════════════


def _then_resolve_option(state, source_ci, ability_idx):
    """Push ``ability_idx`` of this card as a fresh ``resolve_effects`` (the
    ``_resolve_choose_two_modal`` shape), so its targets are gathered only now —
    after a token this ability just created exists ("Create a Beast token.  Deal 1
    damage to a friendly ground unit …" may hit that Beast)."""
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    me = actor_of(state, source_ci)
    after = 1 - state.player_index(me)
    state.pending_decisions.append(PendingDecision(
        deciding_player_id=me, kind="resolve_effects",
        context={"set_code": source_ci.card_def.set_code,
                 "card_number": source_ci.card_def.card_number,
                 "ability_idx": int(ability_idx), "source_id": source_ci.instance_id,
                 "effect_idx": 0, "resolved_targets": {}, "event_ctx": {},
                 "after_all_player_idx": after},
        after_resolve_player_index=after))
    state.event_log.append(DecisionPushed(deciding_player_id=me, kind="resolve_effects"))
    state.active_player_index = state.player_index(me)
    return state


def _beast_then(ability_idx):
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import _create_token_units
        _create_token_units(state, state.player_by_id(actor_of(state, source_ci)),
                            "Beast", 1)
        return _then_resolve_option(state, source_ci, ability_idx)
    return _fn


def _migrate(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _create_token_units
    ps = state.player_by_id(actor_of(state, source_ci))
    n = len(ps.resources) // 3
    if n:
        _create_token_units(state, ps, "Beast", n)
    return state


@card_ability("HMW", "150")
def _migrate_hmw():
    """HMW_150 — Migrate (Event, Innate, 3): "For every 3 resources you control,
    create a Beast token." """
    return EventAbility(effects=[CustomEffect(fn=_migrate)])


@card_ability("HMW", "152")
def _babwa_venomor():
    """HMW_152 — Babwa Venomor (Unit, Imperial, 4/4; Overwhelm): "When Played: An
    opponent creates a Beast token." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CreateTokenUnit("Beast", player="opponent")])


def _poacher_swap(state, source_ci, target_id, event_ctx):
    """Defeat this unit; if you do, create a Beast and deal 1 damage to it."""
    from swu.abilities.resolver import _apply_defeat_unit, _apply_deal_damage
    from swu.engine.actions import _create_token_units
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[1].zone.name not in _IN_ARENA:
        return state
    ps = state.player_by_id(actor_of(state, source_ci))
    _apply_defeat_unit(state, source_ci.instance_id)
    after = state.find_instance(source_ci.instance_id)
    if after is not None and after[1].zone.name in _IN_ARENA:
        return state                      # not defeated (prevented): no "if you do"
    for beast in _create_token_units(state, ps, "Beast", 1):
        _apply_deal_damage(state, beast.instance_id, 1, source_ci.card_def.display_name,
                           dealer_id=ps.player_id, source_id=source_ci.instance_id)
    return state


@card_ability("HMW", "153")
def _poachers_starfighter():
    """HMW_153 — Poacher's Starfighter (Unit, Fighter/Underworld/Vehicle, 3/1):
    "When Played: You may defeat this unit.  If you do, create a Beast token and
    deal 1 damage to it." """
    return TriggerAbility(trigger=WhenPlayed(), optional=True,
                          effects=[CustomEffect(fn=_poacher_swap)])


def _ezra_feed_the_beast(state, source_ci, target_id, event_ctx):
    """Deal 3 damage to your base; if you do, create a Beast token."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import _create_token_units
    ps = state.player_by_id(actor_of(state, source_ci))
    base = ps.base_instance
    if base is None:
        return state
    _apply_deal_damage(state, base.instance_id, 3, source_ci.card_def.display_name,
                       dealer_id=ps.player_id, source_id=source_ci.instance_id)
    if not state.is_terminal():
        _create_token_units(state, ps, "Beast", 1)
    return state


@card_ability("HMW", "168")
def _ezra_bridger_hmw():
    """HMW_168 — Ezra Bridger (Unit, Force/Rebel/Spectre, 5/4): "When you take the
    initiative: You may deal 3 damage to your base.  If you do, create a Beast
    token." """
    return TriggerAbility(trigger=WhenYouTakeInitiative(), optional=True,
                          effects=[CustomEffect(fn=_ezra_feed_the_beast)])


_FRIENDLY_GROUND = TargetSpec(controller="friendly", kind="unit", arena="ground")
_ENEMY_GROUND = TargetSpec(controller="enemy", kind="unit", arena="ground")


@card_ability("HMW", "194")
def _run_amok():
    """HMW_194 — Run Amok (Event, Disaster, 3): "Create a Beast token.  Deal 1 damage
    to a friendly ground unit and 1 damage to an enemy ground unit."  The Beast is
    created first and the damage resolves as option 1 (``_then_resolve_option``), so
    the new Beast is a legal friendly target."""
    return [
        EventAbility(effects=[CustomEffect(fn=_beast_then(1))]),
        TriggerAbility(trigger=WhenPlayed(), effects=[
            DealDamage(1, _FRIENDLY_GROUND), DealDamage(1, _ENEMY_GROUND)]),
    ]


def _catch_the_scent(state, source_ci, target_id, event_ctx):
    """Create 2 Beasts and ready 1 (identical tokens: no choice to make)."""
    from swu.engine.actions import _create_token_units
    beasts = _create_token_units(state, state.player_by_id(actor_of(state, source_ci)),
                                 "Beast", 2)
    if beasts:
        beasts[0].exhausted = False
    return state


@card_ability("HMW", "195")
def _catch_the_scent_hmw():
    """HMW_195 — Catch the Scent (Event, Innate, 5): "Create 2 Beast tokens and
    ready 1 of them." """
    return EventAbility(effects=[CustomEffect(fn=_catch_the_scent)])


@card_ability("HMW", "241")
def _howl():
    """HMW_241 — Howl (Event, Innate, 6): "Create a Beast token.  You may return a
    non-leader unit to its owner's hand."  As Run Amok HMW_194: the Beast first, then
    the bounce as option 1, so the new Beast could be returned too (it ceases to
    exist)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_beast_then(1))]),
        TriggerAbility(trigger=WhenPlayed(), effects=[ReturnToHand(
            TargetSpec(controller="any", kind="unit", predicates=("non_leader",),
                       optional=True))]),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:31 — Beast-token cards
# ══════════════════════════════════════════════════════════════════════════════

_YOUR_BASE = TargetSpec(controller="friendly", kind="base", fixed=EACH_FRIENDLY)


@card_ability("HMW", "250")
def _imperial_cavalry():
    """HMW_250 — Imperial Cavalry (Unit, Imperial/Trooper, 4/4): "When Played: Create
    a Beast token and deal 1 damage to an enemy unit."  The Beast is friendly, so
    gathering the enemy targets before it exists loses nothing."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        CreateTokenUnit("Beast"),
        DealDamage(1, TargetSpec(controller="enemy", kind="unit"))])


@card_ability("HMW", "262")
def _mylaya_rider():
    """HMW_262 — Mylaya Rider (Unit, Creature/Wookiee, 4/4): "When Played: Create a
    Beast token and heal 2 damage from your base." """
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CreateTokenUnit("Beast"), Heal(2, _YOUR_BASE)])


@card_ability("HMW", "272")
def _growth():
    """HMW_272 — Growth (Event, Innate, 5): "Create a Beast token.  Heal 3 damage
    from your base.  Draw a card." """
    return EventAbility(effects=[CreateTokenUnit("Beast"), Heal(3, _YOUR_BASE),
                                 DrawCards(1)])
