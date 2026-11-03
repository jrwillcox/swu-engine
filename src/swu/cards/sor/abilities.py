"""
SOR (Spark of Rebellion) card ability registrations.

Cards with no text or only keywords already handled by the keyword engine
(Sentinel, Overwhelm, Ambush, Restore, Saboteur, Raid, Shielded, Grit)
are not registered here — the keyword layer handles them automatically.

escape_hatch=True cards contain logic that is partially or fully custom
and may not be fully playable in all edge cases.
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ConstantAbility, ActivatedAbility, EventAbility, CostReduction,
    WhenPlayed, WhenDefeated, OnAttack, WhenAttacked, WhenUnitDefeated,
    WhenAttackEnds, OnAttackDefeatsUnit, WhenYouPlayCard, PhaseStartTrigger,
    WhenDeployed, WhenDealsCombatDamageToBase, WhenDealsCombatDamageToUnit,
    WhenOpponentPlaysCard, EntersPlayReady,
    DealDamage, DealDamageEqualTo, Heal, DefeatUnit, DefeatAllUnits, GiveToken, DrawCards, ExhaustCard,
    ReadyCard, ModifyStats, GrantKeyword, RevokeKeyword, ReturnToHand, CustomEffect,
    StatBonus, KeywordGrant, GrantedAbility, SuppressFirstEnemyEvent, Protection,
    ExhaustSelf, PayResources, DefeatSelf, DiscardFromHand, StandingPlayDiscount,
    NextPlayDiscount, CannotAttackBases, OpponentPlayTax, ForbidNamedCardPlay,
    CrossArenaAttack,
    TargetSpec, ConditionCheck, Condition, Duration,
    SELF, DEFENDER, EACH_FRIENDLY, EACH_ENEMY, EACH_IN_PLAY,
)


# ── LEADERS ──────────────────────────────────────────────────────────────────

@card_ability("SOR", "5")
def _luke_skywalker():
    """Luke Skywalker leader.

    Undeployed: Action [1 resource, exhaust]: Give a Shield token to a
    [Heroism] unit you played this phase.
    Deployed On Attack: You may give another unit a Shield token.
    """
    return [
        # Undeployed side: activated ability.  The target choice is fully
        # declarative — a friendly Heroism unit that the controller played this
        # phase (the "played_this_phase" predicate is backed by
        # game_memory.units_played_this_phase; combined with controller="friendly"
        # it restricts to units this player played).  With no eligible unit the
        # action is still usable but fizzles silently (no legal target).
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[GiveToken("Shield", TargetSpec(
                controller="friendly", kind="unit",
                aspects=("Heroism",), predicates=("played_this_phase",),
            ))],
            title="Give Shield (Heroism unit played this phase)",
            undeployed_only=True,
        ),
        # Deployed side: On Attack trigger (only fires when Luke is deployed)
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Shield", TargetSpec(
                controller="any", kind="unit", predicates=("not_self",)
            ))],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("SOR", "10")
def _darth_vader():
    """Darth Vader leader.

    Undeployed: Action [1 resource, exhaust]: If you played a [Villainy] card
    this phase, deal 1 damage to a unit and 1 damage to a base.
    Deployed On Attack: You may deal 2 damage to a unit.
    """
    return [
        # Undeployed side: activated ability gated on the Villainy condition.
        # The ability is only offered (and its cost only payable) when a Villainy
        # card was played this phase; the player then makes two separate target
        # choices — a unit for 1 damage and a base for 1 damage — resolved
        # sequentially by the resolve_effects machinery.
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[
                DealDamage(1, TargetSpec(controller="any", kind="unit")),
                DealDamage(1, TargetSpec(controller="any", kind="base")),
            ],
            title="Deal 1 to a unit and 1 to a base (Villainy played this phase)",
            undeployed_only=True,
            condition=ConditionCheck(Condition.VILLAINY_PLAYED_THIS_PHASE),
        ),
        # Deployed side: On Attack trigger (only fires when Vader is deployed)
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("SOR", "14")
def _sabine_wren_leader():
    """Sabine Wren leader (SOR_14).

    Undeployed: Action [exhaust]: Deal 1 damage to each base (both players' —
    EACH_IN_PLAY base auto-targets both, resolves inline).
    Deployed On Attack: Deal 1 damage to each enemy base (EACH_ENEMY → only the
    opponent's base; mandatory).
    The Epic Action deploy ("if you control 4 or more resources") is the standard
    leader-deploy machinery (deploy_threshold) and needs no ability here.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(kind="base", fixed=EACH_IN_PLAY))],
            title="Deal 1 damage to each base",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(1, TargetSpec(kind="base", fixed=EACH_ENEMY))],
            deployed_only=True,
        ),
    ]


# ── LEADERS (gap campaign sor-set:09) ────────────────────────────────────────


@card_ability("SOR", "1")
def _director_krennic():
    """Director Krennic leader (SOR_1).

    "Each friendly damaged unit gets +1/+0" is printed on BOTH the leader and unit
    sides → a single ungated ConstantAbility (Restore 2 on the deployed side is the
    keyword layer).  NOTE: the ConstantAbility scan (``compute_power``) only iterates
    arena units, so the buff applies while Krennic is DEPLOYED; the engine does not
    scan an undeployed (base_zone) leader for constants — a documented simplification
    for the leader side, shared by any leader with an undeployed constant."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("damaged",)),
        effects=[StatBonus(power=1, hp=0)],
    )


@card_ability("SOR", "2")
def _iden_versio():
    """Iden Versio leader (SOR_2).

    Undeployed: Action [Exhaust]: If an enemy unit was defeated this phase, heal 1
    damage from your base — gated by ENEMY_UNIT_DEFEATED_THIS_PHASE so the action is
    not offered when it would do nothing ("don't offer a no-op").
    Deployed: When an enemy unit is defeated: Heal 1 damage from your base.
    Shielded (deploy) is the keyword layer."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
            title="Heal 1 from your base (enemy unit defeated this phase)",
            undeployed_only=True,
            condition=ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE),
        ),
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="enemy", kind="unit")),
            effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
            deployed_only=True,
        ),
    ]


def _chewbacca_play_unit(state, source_ci, target_id, event_ctx):
    """Adapter: play a hand unit costing ≤3, paying its cost; it gains Sentinel for
    this phase (the play_from_hand cost_max + grant_keyword seam)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_max=3, grant_keyword="Sentinel")
    return state


@card_ability("SOR", "3")
def _chewbacca_leader():
    """Chewbacca leader (SOR_3).

    Undeployed: Action [exhaust]: Play a unit that costs 3 or less from your hand
    (paying its cost); it gains Sentinel for this phase → a CustomEffect adapter onto
    ``push_play_from_hand(cost_max=3, grant_keyword="Sentinel")``.  Grit + Sentinel
    (deployed) are the keyword layer."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_chewbacca_play_unit)],
        title="Play a unit costing 3 or less (it gains Sentinel)",
        undeployed_only=True,
    )


@card_ability("SOR", "4")
def _chirrut_imwe():
    """Chirrut Îmwe leader (SOR_4).

    Undeployed: Action [Exhaust]: Give a unit +0/+2 for this phase.
    Deployed: "During the action phase, this unit isn't defeated by having no
    remaining HP" → a self ConstantAbility carrying the new ``Protection(
    from_hp_defeat=True)`` marker, read (phase-gated to ACTION) by
    ``actions._hp_defeat_prevented`` — the declarative mirror of LOF_43's
    this-phase ``prevent_hp_defeat`` modifier.  During REGROUP the gate drops and
    the settle-time sweep defeats him if still at no remaining HP."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[ModifyStats(power=0, hp=2,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
            title="Give a unit +0/+2 this phase",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[Protection(from_hp_defeat=True)],
        ),
    ]


@card_ability("SOR", "7")
def _grand_moff_tarkin_leader():
    """Grand Moff Tarkin leader (SOR_7).

    Undeployed: Action [1 resource, exhaust]: Give an Experience token to a friendly
    Imperial unit.
    Deployed: On Attack: You may give an Experience token to another friendly
    Imperial unit."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[GiveToken("Experience", TargetSpec(
                controller="friendly", kind="unit", traits=("Imperial",)))],
            title="Give an Experience token to an Imperial unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(
                controller="friendly", kind="unit", traits=("Imperial",),
                predicates=("not_self",)))],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("SOR", "8")
def _hera_syndulla_leader():
    """Hera Syndulla leader (SOR_8).

    Deployed: On Attack: You may give an Experience token to another unique unit.
    RESIDUAL (deferred): "Ignore the aspect penalty on SPECTRE cards you play" is a
    passive play-cost modification — the same aspect-penalty-waiver seam deliberately
    left unimplemented on SHD_126 (a new cost seam, not part of any ability).  The
    card is otherwise fully playable."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit",
            predicates=("unique", "not_self")))],
        optional=True,
        deployed_only=True,
    )


def _leia_organa_ldr_attack(state, source_ci, target_id, event_ctx):
    """Adapter: attack with a Rebel unit, then may attack with another (repeat loop,
    each Rebel unit once).  ``optional`` so the follow-ups can be declined; see the
    registration docstring for the documented deviations."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_trait="Rebel",
                        optional=True, repeat=True)
    return state


def _leia_organa_ldr_followup(state, source_ci, target_id, event_ctx):
    """Adapter: after Leia completes an attack, may attack with another Rebel unit
    (a single optional Rebel attack, source excluded)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_trait="Rebel",
                        optional=True, exclude_source=True)
    return state


@card_ability("SOR", "9")
def _leia_organa_leader():
    """Leia Organa leader (SOR_9).

    Undeployed: Action [exhaust]: Attack with a Rebel unit. Then, you may attack with
    another Rebel unit → ``push_granted_attack(attacker_trait="Rebel", optional=True,
    repeat=True)``.  DEVIATIONS (both minor, player-favourable): the first attack is
    modelled as optional rather than mandatory, and the repeat loop allows attacking
    with every Rebel unit (once each) rather than exactly one follow-up.
    Deployed: When this unit completes an attack: You may attack with another Rebel
    unit → a ``WhenAttackEnds`` granted attack (optional, ``exclude_source``).
    Raid 1 (deployed) is the keyword layer."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_leia_organa_ldr_attack)],
            title="Attack with a Rebel unit (then may attack with another)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_leia_organa_ldr_followup)],
            deployed_only=True,
        ),
    ]


# ── REBEL UNITS ──────────────────────────────────────────────────────────────


@card_ability("SOR", "142")
def _sabine_wren_unit():
    """Sabine Wren unit (SOR_142).

    On Attack: You may deal 1 damage to the defender or to a base.  The target is
    "the defender or a base" — modelled with kind="unit_or_base" + the
    ``defender_or_base`` predicate, so a base always qualifies while a unit
    qualifies only if it is the current defender (when attacking a base there is
    no defender, so only bases are offered).  The "you may" is the optional
    trigger.

    NOTE — RESIDUAL (deferred): the printed static "While there are at least 3
    aspects among other friendly units, this unit can't be attacked (unless she
    gains Sentinel)" is NOT implemented here.  "Can't be attacked" is a defensive
    restriction that would touch attack-target enumeration (core legal_actions)
    plus a new aspect-counting condition — flagged for a dedicated framework
    session rather than jammed into this ability batch.  The card still plays
    (its On Attack ability is live); it just lacks the defensive shield.
    """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(
            kind="unit_or_base", predicates=("defender_or_base",)))],
        optional=True,
    )


@card_ability("SOR", "143")
def _fighters_for_freedom():
    """Fighters for Freedom (SOR_143).

    Saboteur is handled by the keyword engine.  Residual: "When you play another
    [Aggression] card: You may deal 1 damage to a base."  Modelled with the new
    WhenYouPlayCard(aspect="Aggression") trigger, which fires off the CardPlayed
    event for any Aggression card (unit / event / upgrade) the controller plays
    other than this one (exclude_self).  Optional, targets any base."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(aspect="Aggression"),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
        optional=True,
    )


def _k2so_when_defeated(state, source_ci, target_id, event_ctx):
    """Adapter: push the K-2SO "for each opponent, choose one" modal (deal 3 to
    that player's base, or that player discards a card)."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["kaytoo_damage_base", "kaytoo_discard"])
    return state


@card_ability("SOR", "145")
def _k2so():
    """K-2SO (SOR_145).

    Overwhelm is handled by the keyword engine.  Residual: "When Defeated: For
    each opponent, choose one: either deal 3 damage to that player's base, or that
    player discards a card from their hand."  In a 2-player game there is one
    opponent; the choice is a mandatory modal (push_modal with the two K-2SO
    modes — both fungible, so the chosen mode resolves immediately).  The trigger
    is a thin CustomEffect adapter onto the push helper (the Palpatine SOR_135
    pattern)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_k2so_when_defeated)],
    )

@card_ability("SOR", "59")
def _2_1b_surgical_droid():
    """On Attack: You may heal 2 damage from another unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[Heal(2, TargetSpec(
            controller="any", kind="unit", predicates=("not_self", "damaged")
        ))],
        optional=True,
    )


@card_ability("SOR", "236")
def _r2d2():
    """When Played/On Attack: Look at the top card of your deck. You may put it on
    the bottom of your deck. (Otherwise, leave it on top of your deck.)

    The look is mandatory but what to do with the card is the controller's
    decision, so it is modelled as a real "peek_top" (may_bottom) choice point
    (KeepTopCard vs BottomTopCard) rather than auto-resolved.  Empty deck is a
    clean no-op (push_peek_top pushes nothing)."""
    def _peek(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_peek_top
        push_peek_top(state, source_ci, mode="may_bottom")
        return state

    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_peek)]),
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_peek)]),
    ]


@card_ability("SOR", "238")
def _c3po():
    """When Played/On Attack: Choose a number, then look at the top card of your
    deck. If its cost is the chosen number, you may reveal and draw it.
    (Otherwise, leave it on top of your deck.)

    The number is genuinely chosen by the controller (a "choose_number"
    decision); only on a cost match does a "peek_top" (may_draw) decision offer
    the optional reveal-and-draw.  Empty deck is a clean no-op."""
    def _peek(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_choose_number
        push_choose_number(state, source_ci, lo=0, hi=10)
        return state

    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_peek)]),
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_peek)]),
    ]


@card_ability("SOR", "189")
def _leia_organa():
    """When Played: Either ready a resource or exhaust a unit.

    A genuine modal "choose one" for the controller (actions.push_modal): mode
    "ready_resource" readies one of the controller's exhausted resources, mode
    "exhaust_unit" exhausts any ready unit in play (the text says "a unit", not
    "an enemy unit", so friendly units are valid targets too).  Only modes with a
    legal target are offered; if neither has one the ability fizzles cleanly.
    """
    def _leia_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_modal
        push_modal(state, source_ci, ["ready_resource", "exhaust_unit"])
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_leia_effect)],
    )


@card_ability("SOR", "240")
def _fleet_lieutenant():
    """When Played: You may attack with a unit. If it's a Rebel unit, it gets
    +2/+0 for this attack."""
    def _grant(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                            optional=True, bonus_trait="Rebel")
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_grant)])


@card_ability("SOR", "45")
def _yoda():
    """Restore 2 (keyword). When Defeated: Choose any number of players; they draw a card.
    Simplified: each player draws 1 card.
    """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(1, player="each")],
    )


@card_ability("SOR", "242")
def _general_dodonna():
    """Other friendly Rebel units get +1/+1."""
    return ConstantAbility(
        target=TargetSpec(
            controller="friendly", kind="unit",
            traits=("Rebel",), predicates=("not_self",)
        ),
        effects=[StatBonus(power=1, hp=1)],
    )


@card_ability("SOR", "244")
def _snowspeeder():
    """Ambush (keyword). On Attack: Exhaust an enemy Vehicle ground unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(
            controller="enemy", kind="unit", arena="ground", traits=("Vehicle",)
        ))],
        optional=False,
    )


@card_ability("SOR", "196")
def _chewbacca():
    """Sentinel (keyword). When this unit is attacked: Ready him."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[ReadyCard(TargetSpec(fixed=SELF, kind="unit"))],
    )


@card_ability("SOR", "48")
def _vigilant_honor_guards():
    """While this unit is undamaged, it gains Sentinel."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF, kind="unit"),
        effects=[KeywordGrant("Sentinel", 0)],
        condition=ConditionCheck(Condition.SOURCE_UNDAMAGED),
    )


@card_ability("SOR", "49")
def _obi_wan_kenobi():
    """Sentinel (printed keyword, handled by the keyword engine).

    When Defeated: Give 2 Experience tokens to another friendly unit. If it's a
    Force unit, draw a card.

    The "if it's a Force unit" branch keys off the trait of the CHOSEN target —
    which ConditionCheck (source-only) cannot express — so the give-and-draw is
    a single CustomEffect.  It carries a TargetSpec so the resolver enumerates
    the legal "another friendly unit" targets and threads the chosen one in.
    """
    def _obi_effect(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        result = state.find_instance(target_id)
        if result is None:
            return state
        target_ps, target_ci = result
        from swu.engine.tokens import attach_token
        attach_token(state, target_ps, target_ci, "Experience")
        attach_token(state, target_ps, target_ci, "Experience")
        # Draw only if the unit that actually received the Experience is a Force unit.
        target_traits = getattr(target_ci.card_def, "traits", None) or ()
        if "Force" in target_traits:
            ps = state.player_by_id(source_ci.owner_id)
            from swu.engine.actions import _draw_cards
            _draw_cards(state, ps, 1)
        return state

    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(
            fn=_obi_effect,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
        )],
        optional=False,
    )


@card_ability("SOR", "198")
def _han_solo():
    """Ambush (printed keyword, handled by the keyword engine) + innate First
    Strike: while attacking, deals combat damage before the defender.

    Modelled as a constant self-grant of the First Strike keyword; the combat
    pipeline consults it only when Han is the attacker.
    """
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("First Strike", value=0)],
    )


@card_ability("SOR", "241")
def _wing_leader():
    """When Played: Give 2 Experience tokens to another friendly Rebel unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit",
            traits=("Rebel",), predicates=("not_self",)
        ), count=2)],
    )


@card_ability("SOR", "53")
def _lukes_lightsaber():
    """When Played: If attached unit is Luke Skywalker, heal all damage from him
    and give a Shield token to him.

    The "is Luke Skywalker" gate is the TriggerAbility ``condition``
    (ATTACHED_HOST_NAMED), so on any other host the trigger is never collected
    and the player is not prompted at all.  Acts on its own host (no
    player-chosen target), so the CustomEffect needs no TargetSpec — it reads
    the host from event_ctx["attached_to_id"], which the UpgradePlayed path
    supplies (actions.py `_attach_upgrade`).
    """
    def _lightsaber_effect(state, source_ci, target_id, event_ctx):
        attached_to_id = event_ctx.get("attached_to_id")
        if attached_to_id is None:
            return state
        result = state.find_instance(attached_to_id)
        if result is None:
            return state
        target_ps, target_ci = result
        target_ci.damage = 0  # heal all damage
        from swu.engine.tokens import attach_token
        attach_token(state, target_ps, target_ci, "Shield")
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_lightsaber_effect)],
        optional=True,
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Luke Skywalker"),
    )


@card_ability("SOR", "99")
def _bright_hope():
    """When Played: You may return a friendly non-leader ground unit to its
    owner's hand. If you do, draw a card.

    The "you may" is the optional WhenPlayed trigger (accept/decline).  The
    return targets a friendly non-leader *ground* unit chosen by the controller
    (Bright Hope is itself a space unit, so it can never bounce itself, and when
    the controller has no ground unit the optional trigger auto-declines without
    a prompt).  The "If you do, draw a card" is conditional on an actual return,
    so the return + draw are bound together inside one CustomEffect: a None
    target (declined) does nothing, otherwise the unit is returned and the
    controller draws exactly one card.
    """
    def _bright_hope_effect(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        from swu.abilities.resolver import _apply_return_to_hand
        from swu.engine.actions import _draw_cards
        state = _apply_return_to_hand(state, target_id)
        owner_ps = state.player_by_id(source_ci.owner_id)
        _draw_cards(state, owner_ps, 1)
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_bright_hope_effect,
            target=TargetSpec(controller="friendly", kind="unit",
                              arena="ground", predicates=("non_leader",)),
        )],
        optional=True,
    )


# ── REBEL EVENTS ─────────────────────────────────────────────────────────────

def _for_a_cause_effect(state, source_ci, target_id, event_ctx):
    """Adapter: reveal the top 4, deal 1 to the enemy base per Heroism card, then
    push the discard/reorder decision."""
    from swu.engine.actions import push_reveal_top_discard_reorder
    push_reveal_top_discard_reorder(state, source_ci, count=4, aspect="Heroism")
    return state


@card_ability("SOR", "152")
def _for_a_cause_i_believe_in():
    """For a Cause I Believe In (SOR_152).

    Reveal the top 4 cards of your deck.  For each [Heroism] card revealed, deal 1
    damage to an enemy base.  You may discard any of the revealed cards and put
    the rest back on top in any order.  Modelled with the new 'reveal_top'
    decision kind (actions.push_reveal_top_discard_reorder): the Heroism damage is
    dealt up front (deterministic), then the controller resolves each revealed
    card — DiscardRevealed sends it to discard, KeepRevealed places it back on top
    (the order of the keep choices is the new top order)."""
    return EventAbility(effects=[CustomEffect(fn=_for_a_cause_effect)])


# ── Combat tricks, buffs & tempo (sabine-mean-green:03) ───────────────────────

def _rebel_assault_effect(state, source_ci, target_id, event_ctx):
    """Adapter: grant TWO sequential Rebel attacks, each +1/+0 for the attack.

    Pushed onto the LIFO decision stack, so the second push resolves first — but
    both grants are identical (a Rebel attacker, +1/+0), so order is irrelevant.
    "Another" Rebel unit for the second attack falls out of exhaustion: the first
    attacker is exhausted after attacking and so is never re-offered.  Each grant
    is restricted to a Rebel attacker via attacker_trait and fizzles cleanly
    (DeclineGrantedAttack) when the controller has no eligible Rebel unit able to
    attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1, attacker_trait="Rebel")
    push_granted_attack(state, source_ci, power_bonus=1, attacker_trait="Rebel")
    return state


@card_ability("SOR", "103")
def _rebel_assault():
    """Rebel Assault (SOR_103) — Event.

    "Attack with a REBEL unit. It gets +1/+0 for this attack.  Then, attack with
    another REBEL unit. It gets +1/+0 for this attack."  Two granted attacks
    (push_granted_attack) restricted to a Rebel attacker (attacker_trait="Rebel"),
    each with a +1/+0 this-attack bonus.  The one CustomEffect is a thin adapter
    onto the push helper (the Desperate Attack SHD_179 / Surprise Strike SOR_220
    pattern)."""
    return EventAbility(effects=[CustomEffect(fn=_rebel_assault_effect)])


@card_ability("SOR", "144")
def _red_three():
    """Red Three (SOR_144) — Unit.

    "Raid 1 (printed keyword, handled by the keyword engine).  Each other friendly
    [Heroism] unit gains Raid 1."  The grant is a ConstantAbility whose target is
    every OTHER friendly Heroism unit (not_self excludes Red Three itself);
    KeywordGrant("Raid", 1) is read passively by keyword_value, so each such unit's
    attacking power is +1 while Red Three is in play.  Red Three keeps its own
    printed Raid 1 (the sanitiser's bare-mention rule protects it)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          aspects=("Heroism",), predicates=("not_self",)),
        effects=[KeywordGrant("Raid", value=1)],
    )


def _medal_ceremony_effect(state, source_ci, target_id, event_ctx):
    """Adapter: give an Experience token to up to 3 Rebel units that attacked this
    phase (the controller picks distinct units, or fewer — "up to")."""
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Experience", max_targets=3,
        controller="any", kind="unit", traits=["Rebel"],
        predicates=["attacked_this_phase"],
    )
    return state


@card_ability("SOR", "245")
def _medal_ceremony():
    """Medal Ceremony (SOR_245) — Event.

    "Give an Experience token to each of up to 3 REBEL units that attacked this
    phase."  Modelled with the new 'select_token' decision kind
    (actions.push_select_token): the controller picks distinct Rebel units (filtered
    by the attacked_this_phase predicate, backed by game_memory.units_attacked_this_round)
    one at a time up to 3, each receiving an Experience token, or stops early (the
    "up to").  The card does not say "friendly", so any Rebel unit that attacked is
    eligible; because giving Experience helps the recipient, the controller chooses
    and so simply never picks an enemy unit.  The one CustomEffect is a thin adapter
    onto the push helper (the Palpatine SOR_135 pattern)."""
    return EventAbility(effects=[CustomEffect(fn=_medal_ceremony_effect)])


@card_ability("SOR", "74")
def _repair():
    """Heal 3 damage from a unit or base."""
    return EventAbility(effects=[
        Heal(3, TargetSpec(kind="unit_or_base", predicates=("damaged",))),
    ])


@card_ability("SOR", "217")
def _shoot_first():
    """Attack with a unit. It gets +1/+0 for this attack and deals its combat
    damage before the defender (First Strike)."""
    def _grant(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=1, hp_bonus=0,
                            grant_keywords=["First Strike"])
        return state

    return EventAbility(effects=[CustomEffect(fn=_grant)])


@card_ability("SOR", "218")
def _asteroid_sanctuary():
    """Exhaust an enemy unit. Give a Shield token to a friendly unit that costs 3 or less."""
    return EventAbility(effects=[
        ExhaustCard(TargetSpec(controller="enemy", kind="unit")),
        GiveToken("Shield", TargetSpec(controller="friendly", kind="unit", cost_max=3)),
    ])


@card_ability("SOR", "220")
def _surprise_strike():
    """Attack with a unit. It gets +3/+0 for this attack.

    Pushes a 'granted_attack' decision (see actions.push_granted_attack): the
    controller picks a unit to attack with, and that unit gets +3/+0 for the
    attack via a this-attack stats modifier applied in AttackWithUnit.
    """
    def _grant(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=3, hp_bonus=0)
        return state

    return EventAbility(effects=[CustomEffect(fn=_grant)])


@card_ability("SOR", "222")
def _waylay():
    """Return a non-leader unit to its owner's hand."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(predicates=("non_leader",))),
    ])


@card_ability("SOR", "78")
def _vanquish():
    """Defeat a non-leader unit."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(predicates=("non_leader",))),
    ])


# ── IMPERIAL UNITS ────────────────────────────────────────────────────────────

@card_ability("SOR", "79")
def _admiral_piett():
    """Each friendly non-leader unit that costs 6 or more gains Ambush."""
    return ConstantAbility(
        target=TargetSpec(
            controller="friendly", kind="unit",
            predicates=("non_leader",), cost_min=6
        ),
        effects=[KeywordGrant("Ambush", 0)],
    )


@card_ability("SOR", "129")
def _admiral_ozzel():
    """Action [exhaust]: Play an Imperial unit from your hand (paying its cost).
    It enters play ready. Each opponent may ready a unit.

    Uses the play-from-hand subsystem (actions.push_play_from_hand): the
    CustomEffect pushes a 'play_from_hand' decision (the controller picks an
    affordable Imperial unit from hand; it enters ready), followed by an
    'opponent_ready' decision per opponent ("may ready a unit").

    The "Each opponent may ready a unit" clause is unconditional per the card,
    so activating the ability with *no* affordable Imperial unit in hand only
    readies the opponent's units — pure self-harm.  The ability is therefore
    gated by CONTROLLER_CAN_PLAY_UNIT_FROM_HAND("Imperial") so it is offered
    only when there is actually an Imperial unit to play (the Han Solo SHD_13
    pattern: don't offer an action that could only hurt you).
    """
    def _ozzel(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_from_hand
        push_play_from_hand(
            state, source_ci,
            trait="Imperial", enters_ready=True, then_opponents_ready=True,
        )
        return state

    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_ozzel)],
        title="Play an Imperial unit from hand (it enters ready)",
        condition=ConditionCheck(
            Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND, "Imperial"),
    )


@card_ability("SOR", "22")
def _energy_conversion_lab():
    """Epic Action: Play a unit that costs 6 resources or less from your hand.
    Give it Ambush for this phase.

    A once-per-game Epic Action on a base (``epic=True``, no resource cost).
    The CustomEffect is a thin adapter onto the play-from-hand subsystem (the
    Admiral Ozzel SOR_129 pattern): ``push_play_from_hand`` with ``cost_max=6``
    (only hand units whose printed cost is ≤6 are offered) and
    ``grant_keyword="Ambush"`` (the played unit gains Ambush *for this phase*,
    applied as a keyword_grant modifier before its enter-play bus fires, so it
    may immediately attack an enemy unit).  Gated by
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX(6) so the once-per-game epic is
    never wasted when no unit of cost ≤6 is playable.

    Base activated abilities were not previously enumerated (``legal_actions``
    only scanned the arenas); this card needed the small additive base_zone scan.
    """
    def _ecl(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_from_hand
        push_play_from_hand(state, source_ci, cost_max=6, grant_keyword="Ambush")
        return state

    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_ecl)],
        title="Epic Action: play a unit (cost 6 or less) from hand with Ambush",
        epic=True,
        condition=ConditionCheck(
            Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX, 6),
    )


@card_ability("SOR", "130")
def _first_legion_snowtrooper():
    """On Attack: if the defender is damaged, this unit gets +2/+0 and Overwhelm this attack."""
    def _buff_vs_damaged(state, source_ci, target_id, event_ctx):
        defender_id = event_ctx.get("defender_id")
        if not defender_id:
            return state
        result = state.find_instance(defender_id)
        if result is None:
            return state
        _, defender_ci = result
        if defender_ci.damage == 0:
            return state
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id("fls_stats"),
            source_instance_id=source_ci.instance_id,
            target_instance_id=source_ci.instance_id,
            kind="stats",
            value={"power": 2, "hp": 0},
            duration="this_attack",
        ))
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id("fls_kw"),
            source_instance_id=source_ci.instance_id,
            target_instance_id=source_ci.instance_id,
            kind="keyword_grant",
            value={"keyword": "Overwhelm", "value": 0},
            duration="this_attack",
        ))
        return state

    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_buff_vs_damaged)],
        optional=False,
    )


@card_ability("SOR", "226")
def _admiral_motti():
    """When Defeated: You may ready a Villainy unit."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ReadyCard(TargetSpec(
            controller="friendly", kind="unit", aspects=("Villainy",)
        ))],
        optional=True,
    )


@card_ability("SOR", "227")
def _snowtrooper_lieutenant():
    """When Played: You may attack with a unit. If it's an Imperial unit, it gets
    +2/+0 for this attack."""
    def _grant(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                            optional=True, bonus_trait="Imperial")
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_grant)])


def _viper_probe_inspect(state, source_ci, target_id, event_ctx):
    """When Played: Look at an opponent's hand.

    Pushes a private 'look_hand' decision carrying the opponent's hand card
    identities (card_id + name only) in the inspecting player's context, so the
    UI actually shows the hand and holds the screen until the player is done —
    instead of the old no-op log entry the player could never see (Viper Probe
    Droid SOR_228 / SEC_239).  An empty opponent hand still pushes the decision
    (the player learns the hand is empty) — a clean acknowledge."""
    from swu.engine.actions import push_look_opponent_hand
    push_look_opponent_hand(state, source_ci)
    return state


@card_ability("SOR", "228")
def _viper_probe_droid():
    """When Played: Look at an opponent's hand."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_viper_probe_inspect)])


@card_ability("SOR", "83")
def _superlaser_technician():
    """When Defeated: You may put this unit into play as a resource and ready it.

    "Put into play as a resource" places the card facedown and exhausted in the
    resource zone (CR §"PUT INTO PLAY AS A RESOURCE": "placed facedown and
    exhausted ... unless otherwise specified"). Here the card text *does*
    specify otherwise — "and ready it" — so the resource enters READY
    (``exhausted=False``). It still enters facedown (a blank resource); we also
    clear any combat damage the unit carried since a resource has no printed
    attributes. The ``optional=True`` flag makes the "you may" a decline-able
    AcceptTrigger/DeclineTrigger decision; declining leaves the card in discard.
    """
    def _resource_self(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        ps = state.player_by_id(source_ci.owner_id)
        # The defeated unit was placed in discard by _defeat_unit before the
        # optional trigger resolves; move it from discard into the resource zone.
        for i, ci in enumerate(ps.discard):
            if ci.instance_id == source_ci.instance_id:
                ps.discard.pop(i)
                ci.zone = Zone.RESOURCES
                ci.face_down = True
                ci.exhausted = False  # "and ready it"
                ci.damage = 0
                ps.resources.append(ci)
                return state
        return state

    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_resource_self)],
        optional=True,
    )


@card_ability("SOR", "230")
def _general_veers():
    """Other friendly Imperial units get +1/+1."""
    return ConstantAbility(
        target=TargetSpec(
            controller="friendly", kind="unit",
            traits=("Imperial",), predicates=("not_self",)
        ),
        effects=[StatBonus(power=1, hp=1)],
    )


def _is_imperial_card(card_def) -> bool:
    """An "Imperial card" is one with the Imperial trait.

    In the SWU comprehensive rules "Imperial" is a card *trait*, not an aspect, so
    a card's eligibility is decided solely by its trait list — a Villainy/Command
    card without the Imperial trait is not an Imperial card.  (The earlier stub
    also matched the Command/Villainy aspects; that was an over-broad approximation
    and is corrected here.)
    """
    return "Imperial" in (getattr(card_def, "traits", None) or ())


@card_ability("SOR", "84")
def _grand_moff_tarkin():
    """When Played: Search the top 5 cards of your deck for up to 2 Imperial cards,
    reveal them, and draw them. (Put the other cards on the bottom of your deck in
    a random order.)

    Pushes a player-directed 'deck_search' decision (actions.push_deck_search): the
    controller reveals the Imperial cards among the top 5 and takes up to 2 of them
    ("up to" → 0, 1, or 2 are all legal); the un-taken top-5 cards are bottomed in a
    seeded-random order.
    """
    def _tarkin_search(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_deck_search
        push_deck_search(state, source_ci, count=2,
                         eligible=_is_imperial_card, up_to=True)
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_tarkin_search)],
    )


@card_ability("SOR", "88")
def _blizzard_assault_at_at():
    """When this unit attacks and defeats a unit: may deal 3 damage to an enemy ground unit."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[DealDamage(3, TargetSpec(controller="enemy", kind="unit", arena="ground"))],
        optional=True,
    )


@card_ability("SOR", "135")
def _emperor_palpatine():
    """Overwhelm (keyword). When Played: Deal 6 damage divided as you choose
    among enemy units.

    The mandatory When Played CustomEffect pushes a player-directed
    'distribute_damage' decision (actions.push_distribute_damage): the controller
    allocates the 6-point pool across any number of enemy units.  With no enemy
    units the effect fizzles cleanly (no decision pushed).
    """
    def _palpatine_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_distribute_damage
        push_distribute_damage(state, source_ci, 6, target_controller="enemy")
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_palpatine_effect)],
    )


@card_ability("SOR", "132")
def _imperial_interceptor():
    """When Played: You may deal 3 damage to a space unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit", arena="space"))],
        optional=True,
    )


@card_ability("SOR", "231")
def _tie_advanced():
    """When Played: Give 2 Experience tokens to another friendly Imperial unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit",
            traits=("Imperial",), predicates=("not_self",)
        ), count=2)],
    )


@card_ability("SOR", "86")
def _gladiator_star_destroyer():
    """When Played: Give a unit Sentinel for this phase."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GrantKeyword("Sentinel", 0, TargetSpec(controller="any", kind="unit"),
                              Duration.THIS_PHASE)],
    )


@card_ability("SOR", "89")
def _relentless():
    """The first event played by each opponent each round loses all abilities.

    A passive replacement effect, active while Relentless is in play.  The
    ConstantAbility's ``target`` is unused (this is not a stat/keyword buff on
    units) — the engine detects the marker at the event-resolution seam
    (``_resolve_event_ability``) and blanks the affected event's abilities.
    """
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),  # nominal; unused by detection
        effects=[SuppressFirstEnemyEvent()],
    )


# ── IMPERIAL EVENTS ───────────────────────────────────────────────────────────

@card_ability("SOR", "123")
def _recruit():
    """Search the top 5 cards of your deck for a unit, reveal it, and draw it.
    (Put the other cards on the bottom of your deck in a random order.)

    Pushes a player-directed 'deck_search' decision (actions.push_deck_search): the
    controller reveals the units among the top 5 and takes exactly one (mandatory if
    a unit is present — there is no "up to" here, so a unit must be taken while one
    remains; with no unit present nothing is taken).  The un-taken top-5 cards are
    bottomed in a seeded-random order.
    """
    def _recruit_search(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_deck_search
        from swu.cards.models import Unit
        push_deck_search(state, source_ci, count=1,
                         eligible=lambda cd: isinstance(cd, Unit), up_to=False)
        return state

    return EventAbility(effects=[CustomEffect(fn=_recruit_search)])


@card_ability("SOR", "139")
def _force_choke():
    """If you control a Force unit, this event costs 1 resource less to play.
    Deal 5 damage to a non-Vehicle unit. That unit's controller draws a card.

    The cost reduction is a declarative ``CostReduction`` read by the play-cost
    path (so it affects both affordability and the resources actually paid,
    floored at 0).  The damage targets a player-CHOSEN non-Vehicle unit via the
    CustomEffect.target seam; the non-Vehicle restriction is enforced by the
    ``non_vehicle`` predicate, and the draw goes to the controller of the
    TARGETED unit (not the caster).
    """
    def _choke_effect(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        result = state.find_instance(target_id)
        if result is None:
            return state
        target_ps, target_ci = result
        from swu.abilities.resolver import _apply_deal_damage
        state = _apply_deal_damage(state, target_id, 5)
        # Controller of the targeted unit draws a card
        ps = state.player_by_id(target_ci.owner_id)
        from swu.engine.actions import _draw_cards
        _draw_cards(state, ps, 1)
        return state

    return [
        CostReduction(
            amount=1,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, "Force"),
        ),
        EventAbility(effects=[CustomEffect(
            fn=_choke_effect,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("non_vehicle",)),
        )]),
    ]


@card_ability("SOR", "126")
def _resupply():
    """Put this event into play as a resource.

    No "ready it" / "unless otherwise specified" override, so the default
    applies (CR §"PUT INTO PLAY AS A RESOURCE": the card is "placed facedown and
    exhausted in that player's resource zone"). The card therefore enters
    EXHAUSTED — it counts toward ``total_resources`` (e.g. deploy thresholds)
    but is not available to pay costs until it readies in the next regroup.
    """
    def _resupply_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        ps = state.player_by_id(source_ci.owner_id)
        # source_ci is already in discard (event was played); move to resources
        for i, ci in enumerate(ps.discard):
            if ci.instance_id == source_ci.instance_id:
                ps.discard.pop(i)
                ci.zone = Zone.RESOURCES
                ci.face_down = True
                ci.exhausted = True  # facedown and exhausted (CR default)
                ps.resources.append(ci)
                return state
        return state

    return EventAbility(effects=[CustomEffect(fn=_resupply_effect)])


@card_ability("SOR", "172")
def _open_fire():
    """Deal 4 damage to a unit."""
    return EventAbility(effects=[
        DealDamage(4, TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("SOR", "233")
def _i_am_your_father():
    """Deal 7 damage to an enemy unit unless its controller says "no." If they
    do, draw 3 cards.

    The controller picks the enemy unit through the CustomEffect.target seam;
    the chosen unit's controller (the opponent) then resolves a 'say_no'
    decision (actions.push_say_no): allow the 7 damage, or say "no" — in which
    case no damage is dealt and this card's controller draws 3 cards.  Fizzles
    cleanly when there is no enemy unit to target.
    """
    def _iayf_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_say_no
        push_say_no(state, source_ci, target_id, damage=7, draw_on_refuse=3)
        return state

    return EventAbility(effects=[CustomEffect(
        fn=_iayf_effect,
        target=TargetSpec(controller="enemy", kind="unit"),
    )])


@card_ability("SOR", "234")
def _maximum_firepower():
    """A friendly Imperial unit deals damage equal to its power to a unit.
    Then, another friendly Imperial unit deals damage equal to its power to the
    same unit.

    Pushes a sequenced 'distribute_damage' decision
    (actions.push_sequence_damage): the controller first chooses the target unit,
    then a friendly Imperial source that deals its power to it, then — if the
    target survives — a second distinct friendly Imperial source.  Fizzles
    cleanly with no friendly Imperial units or no legal target.
    """
    def _max_firepower_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_sequence_damage
        push_sequence_damage(
            state, source_ci, num_sources=2,
            source_controller="friendly", source_traits=["Imperial"],
            target_controller="any",
        )
        return state

    return EventAbility(effects=[CustomEffect(fn=_max_firepower_effect)])


@card_ability("SOR", "92")
def _overwhelming_barrage():
    """Give a friendly unit +2/+2 for this phase. Then, it deals damage equal to
    its power divided as you choose among any number of other units.

    Pushes a 'distribute_damage' decision (actions.push_distribute_source_power):
    the controller picks a friendly source unit, the +2/+2 this-phase buff is
    applied (via alloc_modifier_id, so determinism holds), and the unit's buffed
    power becomes a pool distributed among any number of OTHER units (the source
    itself is excluded).  Fizzles cleanly with no friendly unit.
    """
    def _barrage_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_distribute_source_power
        push_distribute_source_power(
            state, source_ci,
            source_controller="friendly", buff_power=2, buff_hp=2,
            target_controller="any", exclude_source_from_targets=True,
        )
        return state

    return EventAbility(effects=[CustomEffect(fn=_barrage_effect)])


# ── IMPERIAL UPGRADES ────────────────────────────────────────────────────────

@card_ability("SOR", "136")
def _vaders_lightsaber():
    """When Played: If attached unit is Darth Vader, you may deal 4 damage to a
    ground unit.

    The "you may" is the optional WhenPlayed trigger (accept/decline).  The 4
    damage targets a ground unit chosen by the controller, so the CustomEffect
    carries a TargetSpec restricted to the ground arena and the resolver threads
    the chosen target into fn.  The host==Vader gate is the TriggerAbility
    ``condition`` (ATTACHED_HOST_NAMED), so off Vader the trigger is never
    collected and the player is not prompted at all.
    """
    def _vsaber_effect(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        from swu.abilities.resolver import _apply_deal_damage
        return _apply_deal_damage(state, target_id, 4)

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_vsaber_effect,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
        )],
        optional=True,
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Darth Vader"),
    )


# ── qui-gon-jinn:01 — Direct damage & removal ─────────────────────────────────

@card_ability("SOR", "219")
def _sneak_attack():
    """Sneak Attack (Event): Play a unit from your hand.  It costs 3 resources
    less and enters play ready.  At the start of the regroup phase, defeat it.

    A thin adapter onto the play-from-hand subsystem (the Admiral Ozzel SOR_129 /
    Timely Intervention SHD_129 pattern): ``cost_reduction=3`` (floored at 0),
    ``enters_ready=True``, and the new ``defeat_at_regroup=True`` flag — the unit
    is swept and defeated when the next regroup phase begins (actions._enter_regroup).
    Mandatory if able (no decline); fizzles if no hand unit is affordable at the
    discount.
    """
    def _sneak_attack_effect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_from_hand
        push_play_from_hand(
            state, source_ci,
            cost_reduction=3, enters_ready=True, defeat_at_regroup=True,
        )
        return state

    return EventAbility(effects=[CustomEffect(fn=_sneak_attack_effect)])


# ── darth-maul:01 — Direct damage & removal (SOR card in an LOF deck) ──────────

@card_ability("SOR", "137")
def _fallen_lightsaber():
    """SOR_137 — Fallen Lightsaber (Upgrade, attach to a non-Vehicle unit): "If
    attached unit is a Force unit, it gains: 'On Attack: Deal 1 damage to each
    ground unit the defending player controls.'"

    A ``GrantedAbility`` wrapping an ``OnAttack`` trigger that resolves from the
    HOST (the Armed to the Teeth SHD_175 pattern), gated by the new
    ``SOURCE_HAS_TRAIT("Force")`` condition so the granted ability is collected
    only while the host is a Force unit (the host = source for a granted ability,
    so the condition reads the host's effective traits).  ``DealDamage(1, …)`` with
    ``controller="enemy", arena="ground", fixed=EACH_ENEMY`` auto-targets every
    ground unit the defending player controls (the enemy of the attacking host).
    The "Attach to a non-Vehicle unit" restriction is the upgrade-target parser."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(
            controller="enemy", kind="unit", arena="ground", fixed=EACH_ENEMY))],
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, "Force"),
    ))


@card_ability("SOR", "131")
def _fifth_brother():
    """SOR_131 — Fifth Brother (Ground Unit, Force/Imperial/Inquisitor): "This
    unit gains Raid 1 for each damage on him. (He gets +1/+0 while attacking for
    each damage on him.)  On Attack: You may deal 1 damage to this unit and 1
    damage to another ground unit."

    "Raid 1 for each damage" is exactly the Grit keyword — Grit adds the unit's
    damage total to its effective power (same scaling, different name; the
    reminder text spells it out as "+1/+0 while attacking for each damage").
    Modelled as an *unconditional* ``ConstantAbility(SELF, KeywordGrant("Grit"))``
    so the keyword-query/compute_power Grit path adds ``ci.damage`` to his power.
    The 4th sanitiser rule strips his DB-tagged printed "Raid" because this
    unconditional Grit self-grant fully models the scaling (the raw printed "Raid"
    bar would otherwise stack a fixed Raid 1 on top of the Grit scaling).

    The On Attack is a single **optional** ``CustomEffect`` bundling both damages
    ("deal 1 to this unit AND 1 to another ground unit"): its ``target`` is another
    ground unit (any controller, ``not_self``), so the optional trigger
    auto-declines when there is no other ground unit; on accept it deals 1 to the
    chosen unit and 1 to himself (self-damage that feeds his own Grit)."""
    def _fifth_brother_on_attack(state, source_ci, target_id, event_ctx):
        from swu.abilities.resolver import _apply_deal_damage
        name = source_ci.card_def.display_name
        if target_id:
            _apply_deal_damage(state, target_id, 1, source_name=name)
        _apply_deal_damage(state, source_ci.instance_id, 1, source_name=name)
        return state

    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Grit")],
            condition=None,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_fifth_brother_on_attack,
                target=TargetSpec(controller="any", kind="unit", arena="ground",
                                  predicates=("not_self",)),
            )],
            optional=True,
        ),
    ]


# ── boba-fett:03 — Combat tricks, buffs & tempo ───────────────────────────────


def _fetts_firespray_ready(state, source_ci, target_id, event_ctx):
    """When Played: ready this unit if the controller controls Boba Fett or Jango
    Fett (as a leader or unit).  Reuses ``CONTROLLER_CONTROLS_NAMED`` for each name
    (an OR a single condition atom cannot express); readying = clearing the
    default enters-exhausted flag."""
    for name in ("Boba Fett", "Jango Fett"):
        if ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                          param=name).evaluate(state, source_ci):
            source_ci.exhausted = False
            break
    return state


@card_ability("SOR", "184")
def _fetts_firespray_sor_184():
    """SOR_184 — Fett's Firespray (Unit, Transport/Underworld/Vehicle, 5/6): "When
    Played: If you control Boba Fett or Jango Fett (as a leader or unit), ready this
    unit.  Action [2 resources]: Exhaust a non-unique unit."

    The When Played is a no-target ``CustomEffect`` that readies the unit when the
    controller controls a Boba/Jango Fett (the OR is checked via two
    ``CONTROLLER_CONTROLS_NAMED`` evaluations — a single condition atom cannot
    express the OR).  The Action is a plain ``ActivatedAbility`` (cost = 2
    resources, no exhaust-self) exhausting any non-unique unit (the new
    ``non_unique`` predicate; ``controller="any"`` — you point it at an enemy).  The
    engine does not gate an activated ability on target existence, so with no
    non-unique unit on the board it fizzles silently (the Grogu SHD_196 / Independent
    Senator TWI_206 simplification)."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_fetts_firespray_ready)]),
        ActivatedAbility(
            costs=[PayResources(2)],
            effects=[ExhaustCard(TargetSpec(
                controller="any", kind="unit", predicates=("non_unique",)))],
            title="Exhaust a non-unique unit",
        ),
    ]


def _no_good_to_me_dead_fn(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen unit and forbid it readying for the rest of the round
    (the ``cannot_ready_this_round`` flag, honoured by ``_end_regroup`` and the
    ``ReadyCard`` resolver arm).  A ``None`` target is a clean no-op (fizzle)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is not None:
        _, ci = res
        ci.exhausted = True
        ci.cannot_ready_this_round = True
    return state


@card_ability("SOR", "186")
def _no_good_to_me_dead_sor_186():
    """SOR_186 — No Good to Me Dead (Event, Plan): "Exhaust a unit. That unit can't
    ready this round (including during the regroup phase)."

    A plain ``EventAbility`` whose one ``CustomEffect.target`` (any unit) both
    exhausts the chosen unit and sets the new serialisable
    ``CardInstance.cannot_ready_this_round`` flag — read at the two ready sites:
    ``_end_regroup`` skips the flagged unit's ready step for the current regroup
    (then clears the flag, so it readies normally next round), and the ``ReadyCard``
    effect is a no-op on it.  Exhaust + mark are bundled in one CustomEffect so a
    single target is chosen (a plain ``ExhaustCard`` cannot also set the flag).
    Mandatory-if-able (fizzles with no unit on the board)."""
    return EventAbility(effects=[CustomEffect(
        fn=_no_good_to_me_dead_fn,
        target=TargetSpec(controller="any", kind="unit"),
    )])


def _greedo_mill(state, source_ci, target_id, event_ctx):
    """Mill the top card of the controller's deck to their discard pile.  If the
    milled card is not a Unit, arm the follow-up damage by recording a truthy
    ``event_ctx["prior_target_id"]`` — the established "If you do / if the
    condition held" gate (the ``requires_prior_target`` predicate, In Pursuit
    TWI_221) read by the next effect's ``DealDamage`` target.

    "Discard a card from your deck" mills the top card (no player choice — the
    deck is ordered).  An empty deck is a clean no-op (nothing milled ⇒ the flag
    stays unset ⇒ no damage).  Resolves inline (deterministic, no decision)."""
    from swu.engine.state import Zone
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    card = ps.deck.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    if not isinstance(card.card_def, Unit):
        # "If it's not a unit, deal 2 damage to a ground unit" — arm the gate.
        event_ctx["prior_target_id"] = card.instance_id
    return state


@card_ability("SOR", "204")
def _greedo_sor_204():
    """SOR_204 — Greedo (Unit, Bounty Hunter/Underworld): "When Defeated: You may
    discard a card from your deck.  If it's not a unit, deal 2 damage to a ground
    unit."

    An **optional** ``WhenDefeated`` trigger (the "you may" — Accept mills +
    conditionally deals; Decline mills nothing) with two effects sharing the
    ``resolve_effects`` ``event_ctx`` (the In Pursuit TWI_221 / Grenade Strike
    TWI_171 "record then gate" pattern):

    1. a non-targeted ``CustomEffect`` that mills the top card of the deck and, if
       it is not a Unit, records a truthy ``event_ctx["prior_target_id"]``;
    2. a ``DealDamage(2, ground unit)`` gated by the ``requires_prior_target``
       predicate — so it prompts for a ground unit only when a non-unit was
       milled, and fizzles silently (no prompt) when a unit was milled or the deck
       was empty.

    Folding the conditional into a shared ``event_ctx`` flag means the damage
    target is only offered when it should be; the mill still always happens on
    Accept (even with no ground unit on the board)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[
            CustomEffect(fn=_greedo_mill),
            DealDamage(2, TargetSpec(
                controller="any", kind="unit", arena="ground",
                predicates=("requires_prior_target",),
            )),
        ],
    )


# ── han-solo:03 — Card advantage & disruption ─────────────────────────────────

def _ezra_bridger_attack_ends(state, source_ci, target_id, event_ctx):
    """Push a 'peek_top' (may_play_discard) decision: the controller looks at the
    top card of their deck and may play it, discard it, or leave it on top.  An
    empty deck is a clean no-op (push_peek_top pushes nothing)."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_play_discard")
    return state


@card_ability("SOR", "192")
def _ezra_bridger():
    """SOR_192 — Ezra Bridger (Unit, Force/Rebel/Spectre, 3/4): "When this unit
    completes an attack: Look at the top card of your deck. You may play it,
    discard it, or leave it on top of your deck."

    A mandatory ``WhenAttackEnds`` (fires for the surviving attacker — the
    "completes an attack" seam, Pong Krell LOF_38 / Infused Brawler LOF_156) whose
    one ``CustomEffect`` pushes the ``peek_top`` decision in the new
    ``may_play_discard`` mode: PlayTopCard (pay its cost, one per legal host for an
    upgrade) / DiscardTopCard / KeepTopCard (leave on top)."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_ezra_bridger_attack_ends)],
    )


# ── Reprint-duplicate encodes (Stage 4 of docs/dev/plans/reprint_duplicates_plan.md) ────
# Canonicals whose only reason for being unregistered was that no encoded deck
# pulled them in; each is a plain reuse of an existing primitive.  Siblings are
# aliased in src/swu/cards/reprints.py.

@card_ability("SOR", "43")
def _superlaser_blast():
    """SOR_43 — Superlaser Blast (Event, 8): "Defeat all units."

    A plain ``EventAbility`` with a single ``DefeatAllUnits`` whose filter is
    every unit in play (both players, both arenas, deployed leaders included).
    The resolver defeats each matching unit in turn (``kind="unit"`` excludes
    bases; protected units are skipped per ``_target_protected``)."""
    return EventAbility(effects=[
        DefeatAllUnits(filter=TargetSpec(controller="any", kind="unit")),
    ])


# ── Reprint sweep Stage 4 Batch 2 (canonical encodes) ────────────────────────

@card_ability("SOR", "112")
def _consortium_starviper():
    """SOR_112 — Consortium StarViper (Unit, Vehicle/Fighter, Space): "While you
    have the initiative, this unit gains Restore 2."

    A self-targeted conditional ``ConstantAbility`` granting Restore 2, gated by
    ``CONTROLLER_HAS_INITIATIVE`` and read passively by ``keyword_value`` so the
    heal-on-attack winks on/off as initiative changes hands (the Separatist
    Commando TWI_180 / Cinta Kaz LAW_105 conditional self-grant pattern).  The
    keyword sanitiser strips the printed Restore because this conditional
    self-grant is registered, so the ability — not an always-on bar — owns it."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Restore", value=2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


@card_ability("SOR", "113")
def _homestead_militia():
    """SOR_113 — Homestead Militia (Unit, Trooper, Ground): "While you control 6
    or more resources, this unit gains Sentinel."

    A self-targeted conditional ``ConstantAbility`` granting Sentinel, gated by
    ``CONTROLLER_N_PLUS_RESOURCES(6)`` and read passively by ``has_keyword`` — the
    Sentinel sibling of Seasoned Shoretrooper SHD_83's conditional +2/+0.  The
    keyword sanitiser strips the printed Sentinel because this conditional
    self-grant is registered."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_RESOURCES, 6),
    )


def _prepare_for_takeoff_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 8 for up to 2 Vehicle units and draw them."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit

    def eligible(cd):
        return isinstance(cd, Unit) and "Vehicle" in (getattr(cd, "traits", None) or ())

    push_deck_search(state, source_ci, count=2, window=8, eligible=eligible,
                     up_to=True)
    return state


@card_ability("SOR", "125")
def _prepare_for_takeoff():
    """SOR_125 — Prepare for Takeoff (Event, Plan): "Search the top 8 cards of your
    deck for up to 2 Vehicle units, reveal them, and draw them. (Put the other
    cards on the bottom of your deck in a random order.)"

    A thin ``CustomEffect`` adapter onto the deck_search seam (``push_deck_search``,
    the This Is The Way SHD_253 / Remnant Reserves SHD_93 pattern): ``count=2,
    window=8, up_to=True``, eligibility = a Unit carrying the Vehicle trait; the
    rest of the window is bottomed in a seeded-random order."""
    return EventAbility(effects=[CustomEffect(fn=_prepare_for_takeoff_search)])


def _luke_skywalker_sor51(state, source_ci, target_id, event_ctx):
    """Give the chosen enemy unit –3/–3 for this phase, or –6/–6 instead if a
    friendly unit was defeated this phase.  "A friendly unit was defeated this
    phase" is read as: an id in ``game_memory.units_defeated_this_round`` (defeats
    happen only in ACTION and the set clears at the round rollover, so
    "this round" == "this phase") belonging to a card now in the controller's
    discard pile (the common home of a defeated unit — the Admiral Trench TWI_86
    defeated-this-phase pattern).  DEVIATION: a friendly unit defeated then removed
    from discard would not be counted."""
    if target_id is None:
        return state
    defeated = set(state.game_memory.units_defeated_this_round)
    ps = state.player_by_id(source_ci.owner_id)
    friendly_defeated = any(c.instance_id in defeated for c in ps.discard)
    n = 6 if friendly_defeated else 3
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(
        _make_modifier(state, source_ci.instance_id, target_id, -n, -n,
                       Duration.THIS_PHASE)
    )
    return state


@card_ability("SOR", "51")
def _luke_skywalker_sor51_card():
    """SOR_51 — Luke Skywalker (6/7, Restore 3): "When Played: Give an enemy unit
    –3/–3 for this phase.  If a friendly unit was defeated this phase, give that
    enemy unit –6/–6 for this phase instead."

    Restore 3 is the keyword layer.  A mandatory ``WhenPlayed`` whose one
    ``CustomEffect.target`` (an enemy unit) applies a this-phase stat debuff whose
    magnitude (–3/–3 vs –6/–6) is decided from board state — the Zeb Orellios
    LAW_45 conditional-magnitude pattern (an OR/count a single ModifyStats cannot
    express).  Fizzles with no enemy unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_luke_skywalker_sor51,
            target=TargetSpec(controller="enemy", kind="unit"))],
    )


@card_ability("SOR", "176")
def _isb_agent_sor176():
    """SOR_176 — ISB Agent (Unit, 1/3): "When Played: You may reveal an event from
    your hand. If you do, deal 1 damage to a unit."

    The reveal is public-info cosmetic and the "if you do" simply gates the damage
    on actually holding an Event — so this is an optional ``WhenPlayed
    DealDamage(1, a unit)`` gated by the new ``CONTROLLER_HAS_EVENT_IN_HAND``
    condition (the trigger is not offered without an Event in hand).
    ``controller="any"`` mirrors the printed "a unit" (the controller points the 1
    damage at an enemy); auto-declines when no unit is on the board."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_EVENT_IN_HAND),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
    )


@card_ability("SOR", "40")
def _avenger_sor40():
    """SOR_40 — Avenger (8/8 Imperial Vehicle Capital Ship): "When Played/On
    Attack: An opponent chooses a non-leader unit they control.  Defeat that unit."

    Two triggers (``WhenPlayed`` + ``OnAttack``), each a thin no-target
    ``CustomEffect`` adapter onto ``push_each_player_defeats(only_opponent=True)``
    (the Merciless Contest TWI_238 seam, restricted to the opponent): the OPPONENT
    of Avenger's controller chooses one of their own non-leader units, which is
    then defeated.  Fizzles cleanly when the opponent has no non-leader unit."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_each_player_defeats
        push_each_player_defeats(state, source_ci, only_opponent=True)
        return state
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)]),
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_fn)]),
    ]


# ── "Choose two, in any order" aspect events ─────────────────────────────────
# Aggression SOR_155 / Command SOR_107 / Cunning SOR_203 / Vigilance SOR_58.
# Each registers idx 0 = the EventAbility controller (a thin CustomEffect calling
# push_choose_modal over the option ability-indices) and idx 1..4 = the four
# options, each a TriggerAbility whose ``.effects`` is that option's effect list.
# The option specs are never fired as real triggers (an event card is never in
# play) nor resolved by _resolve_event_ability (they are not EventAbility) — they
# are reached ONLY from the choose_two_modal decision, which delegates each chosen
# option to the standard resolve_effects machinery (all targeting is the
# resolver's).  See actions.push_choose_modal.

def _choose_two_modal_controller(state, source_ci, target_id, event_ctx):
    """Thin controller: push the choose_two_modal decision over options idx 1..4."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2, 3, 4], pick=2)
    return state


@card_ability("SOR", "155")
def _aggression_sor155():
    """SOR_155 — Aggression (Event): "Choose two, in any order: Draw a card /
    Defeat up to 2 upgrades / Ready a unit with 3 or less power / Deal 4 damage to
    a unit." (the choose_two_modal primitive)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_choose_two_modal_controller)]),
        # opt 1 — Draw a card.
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        # opt 2 — Defeat up to 2 upgrades (two optional targeted defeats;
        # kind="upgrade" enumerates real, non-token upgrades).
        TriggerAbility(trigger=WhenPlayed(), effects=[
            DefeatUnit(TargetSpec(controller="any", kind="upgrade", optional=True)),
            DefeatUnit(TargetSpec(controller="any", kind="upgrade", optional=True)),
        ]),
        # opt 3 — Ready a unit with 3 or less power.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            ReadyCard(TargetSpec(controller="any", kind="unit", power_max=3)),
        ]),
        # opt 4 — Deal 4 damage to a unit.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            DealDamage(4, TargetSpec(controller="any", kind="unit")),
        ]),
    ]


def _command_deal_power_pick(state, source_ci, target_id, event_ctx):
    """opt 2, effect 1: record the chosen FRIENDLY unit's effective power (the
    Haymaker LAW_168 two-target shape)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    event_ctx["cmd_deal_power"] = int(compute_power(state, res[1]))
    return state


def _command_deal_power_hit(state, source_ci, target_id, event_ctx):
    """opt 2, effect 2: deal the recorded power to the chosen enemy non-unique
    unit."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("cmd_deal_power", 0))
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, amount,
                       source_name=source_ci.card_def.display_name)
    return state


def _command_put_self_as_resource(state, source_ci, target_id, event_ctx):
    """opt 3: put this event into play as a (ready) resource for its controller."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    ps = state.player_by_id(source_ci.owner_id)
    ci = next((c for c in ps.discard
               if c.instance_id == source_ci.instance_id), None)
    if ci is None:
        return state  # already relocated (shouldn't happen) → no-op
    ps.discard.remove(ci)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    state.event_log.append(CardResourced(
        player_id=ps.player_id, instance_id=ci.instance_id,
        card_name=ci.card_def.display_name))
    return state


def _command_return_unit_from_discard(state, source_ci, target_id, event_ctx):
    """opt 4: return a unit from your discard pile to your hand (reuses the
    return_from_discard decision — lands nested beneath the option's buried
    resolve_effects, resumed automatically)."""
    from swu.engine.actions import push_return_from_discard
    from swu.cards.models import Unit
    push_return_from_discard(
        state, source_ci, count=1,
        eligible=lambda cd: isinstance(cd, Unit))
    return state


@card_ability("SOR", "107")
def _command_sor107():
    """SOR_107 — Command (Event): "Choose two, in any order: Give 2 Experience
    tokens to a unit / A friendly unit deals damage equal to its power to a
    non-unique enemy unit / Put this event into play as a resource / Return a unit
    from your discard pile to your hand." (the choose_two_modal primitive)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_choose_two_modal_controller)]),
        # opt 1 — Give 2 Experience tokens to a unit.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            GiveToken("Experience", TargetSpec(controller="any", kind="unit"),
                      count=2),
        ]),
        # opt 2 — A friendly unit deals its power to a non-unique enemy unit
        # (two dependent CustomEffect.target effects sharing event_ctx).
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_command_deal_power_pick,
                         target=TargetSpec(controller="friendly", kind="unit")),
            CustomEffect(fn=_command_deal_power_hit,
                         target=TargetSpec(controller="enemy", kind="unit",
                                           predicates=("non_unique",))),
        ]),
        # opt 3 — Put this event into play as a resource.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_command_put_self_as_resource),
        ]),
        # opt 4 — Return a unit from your discard pile to your hand.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_command_return_unit_from_discard),
        ]),
    ]


def _cunning_opponent_random_discard(state, source_ci, target_id, event_ctx):
    """opt 4: an opponent discards a random card from their hand (seeded RNG)."""
    from swu.engine.state import Zone
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.hand:
        return state
    rng = state.make_rng()
    idx = rng.randrange(len(opp.hand))
    state.rng_state = rng.getstate()
    ci = opp.hand.pop(idx)
    ci.zone = Zone.DISCARD
    opp.discard.append(ci)
    return state


@card_ability("SOR", "203")
def _cunning_sor203():
    """SOR_203 — Cunning (Event): "Choose two, in any order: Return a non-leader
    unit with 4 or less power to its owner's hand / Give a unit +4/+0 for this
    phase / Exhaust up to 2 units / An opponent discards a random card from their
    hand." (the choose_two_modal primitive)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_choose_two_modal_controller)]),
        # opt 1 — Return a non-leader unit with 4 or less power to owner's hand.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            ReturnToHand(TargetSpec(controller="any", kind="unit",
                                    predicates=("non_leader",), power_max=4)),
        ]),
        # opt 2 — Give a unit +4/+0 for this phase.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            ModifyStats(power=4, hp=0,
                        target=TargetSpec(controller="any", kind="unit"),
                        duration=Duration.THIS_PHASE),
        ]),
        # opt 3 — Exhaust up to 2 units (two optional exhausts; the "ready"
        # predicate excludes already-exhausted units, so picks stay distinct).
        TriggerAbility(trigger=WhenPlayed(), effects=[
            ExhaustCard(TargetSpec(controller="any", kind="unit",
                                   predicates=("ready",), optional=True)),
            ExhaustCard(TargetSpec(controller="any", kind="unit",
                                   predicates=("ready",), optional=True)),
        ]),
        # opt 4 — An opponent discards a random card from their hand.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_cunning_opponent_random_discard),
        ]),
    ]


def _vigilance_mill_opponent_6(state, source_ci, target_id, event_ctx):
    """opt 1: discard 6 cards from an opponent's deck (top-down)."""
    from swu.engine.state import Zone
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    for _ in range(6):
        if not opp.deck:
            break
        ci = opp.deck.pop(0)
        ci.zone = Zone.DISCARD
        opp.discard.append(ci)
    return state


@card_ability("SOR", "58")
def _vigilance_sor58():
    """SOR_58 — Vigilance (Event): "Choose two, in any order: Discard 6 cards from
    an opponent's deck / Heal 5 damage from a base / Defeat a unit with 3 or less
    remaining HP / Give a Shield token to a unit." (the choose_two_modal
    primitive)."""
    return [
        EventAbility(effects=[CustomEffect(fn=_choose_two_modal_controller)]),
        # opt 1 — Discard 6 cards from an opponent's deck.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_vigilance_mill_opponent_6),
        ]),
        # opt 2 — Heal 5 damage from a base (your own; EACH_FRIENDLY base heals
        # inline with no trivial 1-target prompt).
        TriggerAbility(trigger=WhenPlayed(), effects=[
            Heal(5, TargetSpec(controller="friendly", kind="base",
                               fixed=EACH_FRIENDLY)),
        ]),
        # opt 3 — Defeat a unit with 3 or less remaining HP.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            DefeatUnit(TargetSpec(controller="any", kind="unit",
                                  hp_remaining_max=3)),
        ]),
        # opt 4 — Give a Shield token to a unit.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            GiveToken("Shield", TargetSpec(controller="any", kind="unit")),
        ]),
    ]


def _falcon_regroup_upkeep(state, source_ci, target_id, event_ctx):
    """Millennium Falcon SOR_193 regroup upkeep — push the "pay 1 or return"
    decision for the Falcon's controller (a thin adapter, no player choice here)."""
    from swu.engine.actions import push_regroup_upkeep
    push_regroup_upkeep(state, source_ci)
    return state


@card_ability("SOR", "193")
def _millennium_falcon():
    """Millennium Falcon SOR_193 (Piece of Junk, 3/4 Unit) — "This unit enters
    play ready. When you ready cards during the regroup phase: Either pay [1
    resource] or return this unit to her owner's hand."

    Two specs: an unconditional ``EntersPlayReady()`` (read at the enter-play
    placement seam) and a ``PhaseStartTrigger(phase="regroup")`` whose mandatory,
    non-targeted ``CustomEffect`` resolves inline at ``_enter_regroup`` (the
    Contracted Hunter JTL_216 site) and pushes the ``regroup_upkeep`` decision —
    the new self-contained primitive for a recurring per-round "pay or return"
    upkeep. Reprint sibling P25_92 aliased in reprints.py."""
    return [
        EntersPlayReady(),
        TriggerAbility(
            trigger=PhaseStartTrigger(phase="regroup"),
            effects=[CustomEffect(fn=_falcon_regroup_upkeep)],
        ),
    ]


@card_ability("SOR", "87")
def _darth_vader_first_legion():
    """Darth Vader — Commanding the First Legion SOR_87 (7-cost 5/7, Ambush).
    "When Played: Search the top 10 cards of your deck for any number of
    [Villainy] units with combined cost 3 or less and play each of them for free."

    Ambush is the keyword layer.  The When Played is a MANDATORY trigger (the
    search is not "you may"; "any number" lets the controller take 0 via
    FinishSearch) whose one non-targeted ``CustomEffect`` is a thin adapter (the
    Palpatine SOR_135 inline-push pattern) onto the new
    ``push_search_and_play_multiple`` primitive — a combined-cost budget
    multi-select over the ``deck_search`` play disposition.  Reprint siblings
    C24_2 / P25_103 aliased in reprints.py."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_search_and_play_multiple
        from swu.cards.models import Unit

        def _villainy_unit(cd) -> bool:
            return (isinstance(cd, Unit)
                    and any(a.name == "Villainy"
                            for a in (getattr(cd, "aspects", None) or ())))

        push_search_and_play_multiple(
            state, source_ci, window=10, budget=3, eligible=_villainy_unit)
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


# ── group_01 — Direct damage & removal ───────────────────────────────────────

def _palpatine_take_control(state, source_ci, target_id, event_ctx):
    """Emperor Palpatine SOR_6 When Deployed: "Take control of a damaged non-leader
    unit."  A thin adapter onto the control-change seam (actions.change_control —
    control is implicit arena occupancy, per Stolen Landspeeder SHD_161); the
    TargetSpec restricts the choice to a damaged non-leader unit."""
    from swu.engine.actions import change_control
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, target_ci = res
    change_control(state, target_ci, source_ci.owner_id)
    return state


@card_ability("SOR", "6")
def _emperor_palpatine():
    """SOR_6 — Emperor Palpatine (Leader).

    Undeployed: Action [1 resource, exhaust, defeat a friendly unit]: Deal 1 damage
      to a unit and draw a card.  The "defeat a friendly unit" cost is modelled as
      the first mandatory targeted effect (a friendly unit — could be another
      deployed unit); the ability is gated on CONTROLLER_HAS_NON_LEADER_UNIT so the
      resource+exhaust cost is never wasted when there is nothing to defeat
      (undeployed, Palpatine is not a unit, so the sacrifice is always another unit).
    Deployed When Deployed: Take control of a damaged non-leader unit (control-change
      CustomEffect).
    Deployed On Attack: You may defeat another friendly unit; if you do, deal 1 damage
      to a unit and draw a card.  The "if you do" binding is the ability-level
      optional + CONTROLLER_HAS_NON_LEADER_UNIT gate (so accepting always has a
      not_self friendly to defeat), then the mandatory defeat/damage/draw sequence.
    """
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[
                DefeatUnit(TargetSpec(controller="friendly", kind="unit")),
                DealDamage(1, TargetSpec(controller="any", kind="unit")),
                DrawCards(1),
            ],
            title="Defeat a friendly unit: deal 1 to a unit and draw",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_NON_LEADER_UNIT),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(
                fn=_palpatine_take_control,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("damaged", "non_leader")),
            )],
            deployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                DefeatUnit(TargetSpec(controller="friendly", kind="unit",
                                      predicates=("not_self",))),
                DealDamage(1, TargetSpec(controller="any", kind="unit")),
                DrawCards(1),
            ],
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_NON_LEADER_UNIT),
        ),
    ]


def _damage_and_ready(amount):
    """Factory: a CustomEffect fn that deals ``amount`` damage to the chosen target
    and then readies it — Grand Inquisitor SOR_11's "Deal N damage to a friendly
    unit with 3 or less power and ready it" (both clauses hit the SAME single
    player-chosen target, so one CustomEffect rather than two independently-targeted
    effects)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.abilities.resolver import _apply_deal_damage
        if target_id is None:
            return state
        state = _apply_deal_damage(state, target_id, amount)
        res = state.find_instance(target_id)
        if res is not None:
            res[1].exhausted = False   # "and ready it"
        return state
    return _fn


@card_ability("SOR", "11")
def _grand_inquisitor():
    """SOR_11 — Grand Inquisitor (Leader).

    Undeployed: Action [exhaust]: Deal 2 damage to a friendly unit with 3 or less
      power and ready it.
    Deployed On Attack: You may deal 1 damage to another friendly unit with 3 or
      less power and ready it.
    Both are one CustomEffect (damage-then-ready the same target); the ``power_max``
    TargetSpec filter restricts the host to a friendly unit with effective power ≤3.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_damage_and_ready(2),
                target=TargetSpec(controller="friendly", kind="unit", power_max=3),
            )],
            title="Deal 2 to a friendly power-3-or-less unit and ready it",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_damage_and_ready(1),
                target=TargetSpec(controller="friendly", kind="unit",
                                  power_max=3, predicates=("not_self",)),
            )],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("SOR", "13")
def _cassian_andor():
    """SOR_13 — Cassian Andor (Leader).

    Undeployed: Action [1 resource, Exhaust]: If you've dealt 3 or more damage to an
      enemy base this phase, draw a card.  Gated by the new
      CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE(3) condition (backed by
      game_memory.base_damage_dealt_this_phase, accumulated at the direct base-combat
      damage step — the "don't offer a no-op" pattern, so the cost isn't wasted).
    Deployed "When you deal damage to an enemy base: You may draw a card. Use this
      ability only once each round."  Faithful simplification: the broad "when you
      deal damage" is modelled with WhenDealsCombatDamageToBase (this unit's combat
      damage — Cassian is a Saboteur base-attacker, the common case), optional.
      DEVIATION: the printed "Use this ability only once each round" is dropped —
      TriggerAbility has no once-per-round limiter, and Cassian (a single unit)
      attacks at most once per round unless readied, so it is naturally satisfied
      in the common case; the sole edge is a re-readied Cassian attacking a base
      twice in one round (a small over-draw).
    (Saboteur is a printed keyword handled by the keyword engine.)
    """
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[DrawCards(1)],
            title="Draw a card (dealt 3+ to an enemy base this phase)",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE, param=3),
        ),
        TriggerAbility(
            trigger=WhenDealsCombatDamageToBase(),
            effects=[DrawCards(1)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _han_solo_resource_from_hand(state, source_ci, target_id, event_ctx):
    """Han Solo SOR_17 undeployed Action: put a card from hand into play as a ready
    resource, then schedule "defeat a resource you control" for the next action
    phase start."""
    from swu.engine.actions import (
        _resource_card_from_hand, push_defeat_own_resource_schedule)
    ps = state.player_by_id(source_ci.owner_id)
    _resource_card_from_hand(state, ps)
    push_defeat_own_resource_schedule(state, source_ci)
    return state


def _han_solo_resource_from_deck(state, source_ci, target_id, event_ctx):
    """Han Solo SOR_17 deployed On Attack: put the top card of deck into play as a
    ready resource, then schedule the next-action-phase resource defeat."""
    from swu.engine.actions import (
        _resource_top_of_deck, push_defeat_own_resource_schedule)
    ps = state.player_by_id(source_ci.owner_id)
    _resource_top_of_deck(state, ps)
    push_defeat_own_resource_schedule(state, source_ci)
    return state


@card_ability("SOR", "17")
def _han_solo():
    """SOR_17 — Han Solo (Leader).

    Undeployed: Action [exhaust]: Put a card from your hand into play as a resource
      and ready it. At the start of the next action phase, defeat a resource you
      control.
    Deployed On Attack: Put the top card of your deck into play as a resource and
      ready it. At the start of the next action phase, defeat a resource you control.
    Both compose the ramp primitives (_resource_card_from_hand / _resource_top_of_deck)
    with the delayed defeat_own_resource scheduler (scheduled_action_phase_effects,
    the Eye of Aldhani SEC_73 seam).  Resource selection (which hand card to resource,
    which resource to later defeat) is auto-resolved — resources are fungible face-down
    cards (the K-2SO SOR_145 auto-select precedent).
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_han_solo_resource_from_hand)],
            title="Resource a card from hand (defeat a resource next phase)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_han_solo_resource_from_deck)],
            deployed_only=True,
        ),
    ]


@card_ability("SOR", "25")
def _tarkintown():
    """SOR_25 — Tarkintown (Base): "Epic Action: Deal 3 damage to a damaged
    non-leader unit."  A once-per-game Epic Action on a base (epic=True, no cost),
    enumerated via the existing base_zone scan (Energy Conversion Lab SOR_22)."""
    return ActivatedAbility(
        costs=[],
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          predicates=("damaged", "non_leader")))],
        title="Epic Action: deal 3 to a damaged non-leader unit",
        epic=True,
    )


@card_ability("SOR", "38")
def _count_dooku():
    """SOR_38 — Count Dooku (Unit): "When Played: You may defeat a unit with 4 or
    less remaining HP."  (Shielded is a printed keyword handled by the keyword
    engine.)"""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       hp_remaining_max=4))],
        optional=True,
    )


def _power_of_the_dark_side(state, source_ci, target_id, event_ctx):
    """Power of the Dark Side SOR_41: "An opponent chooses a unit they control.
    Defeat that unit."  The opponent_chooses_target decision with
    disposition="defeat" + units_only (the LOF_43 Tragedy of Plagueis / SHD_246
    reuse) — a single mandatory stage, skipped when the opponent has no unit."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(
        state, source_ci, disposition="defeat", units_only=True)
    return state


@card_ability("SOR", "41")
def _power_of_the_dark_side_event():
    """SOR_41 — Power of the Dark Side (Event)."""
    return EventAbility(effects=[CustomEffect(fn=_power_of_the_dark_side)])


# ── sor-set:02 — Direct damage & removal ─────────────────────────────────────

def _redemption_heal(state, source_ci, target_id, event_ctx):
    """Redemption SOR_52 When Played: heal up to 8 across own units/bases, then deal
    the healed total back to Redemption (push_distribute_heal wraps it all)."""
    from swu.engine.actions import push_distribute_heal
    push_distribute_heal(state, source_ci, 8)
    return state


@card_ability("SOR", "52")
def _redemption():
    """SOR_52 — Redemption (Unit): Sentinel (keyword). "When Played: Heal up to 8
    total damage from any number of units and/or bases. Deal that much damage to this
    unit."

    A thin CustomEffect adapter over the heal flavour of the distribute_damage
    decision (push_distribute_heal): the controller distributes up to 8 healing across
    its own damaged units and base, and the amount actually healed is dealt back to
    Redemption ("this unit")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_redemption_heal)],
    )


def _binds_heal(state, source_ci, target_id, event_ctx):
    """Heal up to 3 from the chosen unit; record the amount healed, the healed unit's
    id (so the follow-up hits ANOTHER unit), and — only when the payoff is live (some
    damage healed AND a friendly Force unit is controlled) — set ``prior_target_id`` so
    the optional follow-up is offered."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    healed = min(3, int(ci.damage))
    ci.damage -= healed
    event_ctx["binds_amount"] = healed
    event_ctx["excluded_target_id"] = target_id
    from swu.engine.traits import get_traits
    ps = state.player_by_id(source_ci.owner_id)
    has_force = any("Force" in get_traits(state, u)
                    for u in (ps.ground_arena + ps.space_arena))
    if healed > 0 and has_force:
        event_ctx["prior_target_id"] = target_id
    return state


def _binds_damage(state, source_ci, target_id, event_ctx):
    """Deal the recorded healed amount to the chosen 'another' unit."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("binds_amount", 0) or 0)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, amount, dealer_id=source_ci.owner_id)


@card_ability("SOR", "75")
def _it_binds_all_things():
    """SOR_75 — It Binds All Things (Event, Force): "Heal up to 3 damage from a unit.
    If you control a FORCE unit, you may deal that much damage to another unit."

    Two dependent effects sharing the resolve_effects event_ctx (the Haymaker LAW_168
    pattern): a mandatory heal of a chosen damaged unit records the amount healed + its
    id; the optional follow-up deals that amount to ANOTHER unit (``excludes_event_target``)
    and is offered only when the payoff is live — some damage was healed AND a friendly
    Force unit is controlled — via the ``requires_prior_target`` gate (``prior_target_id``
    is set by the heal fn only in that case), so a base with no Force unit / no damaged
    unit shows no follow-up prompt."""
    return EventAbility(effects=[
        CustomEffect(fn=_binds_heal,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("damaged",))),
        CustomEffect(fn=_binds_damage,
                     target=TargetSpec(controller="any", kind="unit", optional=True,
                                       predicates=("excludes_event_target",
                                                   "requires_prior_target"))),
    ])


@card_ability("SOR", "77")
def _takedown():
    """SOR_77 — Takedown (Event, Tactic): "Defeat a unit with 5 or less remaining
    HP."  A plain targeted DefeatUnit with ``hp_remaining_max=5``."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit", hp_remaining_max=5)),
    ])


@card_ability("SOR", "85")
def _rukh():
    """SOR_85 — Rukh (Unit): Shielded (keyword). "When this unit deals combat damage
    to a non-leader unit while attacking: Defeat that unit."

    The new ``WhenDealsCombatDamageToUnit`` trigger (the attacker-side mirror of
    WhenDealtCombatDamage), with ``non_leader_only`` so it is suppressed against a
    leader unit; "that unit" is the surviving defender (fixed ``DEFENDER`` target)."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToUnit(non_leader_only=True),
        effects=[DefeatUnit(TargetSpec(fixed=DEFENDER, kind="unit"))],
    )


@card_ability("SOR", "90")
def _devastator():
    """SOR_90 — Devastator (Unit): Sentinel + Overwhelm (keywords). "When Played: You
    may deal damage to a unit equal to the number of resources you control."

    Scaling magnitude via DealDamageEqualTo with the new ``source_controller_resources``
    count; optional (the "you may")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit"),
            count="source_controller_resources",
        )],
        optional=True,
    )


@card_ability("SOR", "121")
def _hardpoint_heavy_blaster():
    """SOR_121 — Hardpoint Heavy Blaster (Upgrade, Modification/Weapon): "Attach to a
    VEHICLE unit.  Attached unit gains: 'On Attack: If this unit isn't attacking a
    base, you may deal 2 damage to a unit in the defender's arena.'"

    The attach-to-VEHICLE restriction is parsed from the card text by the engine; the
    residual is the granted On Attack ability (GrantedAbility wrapping a normal OnAttack
    that resolves from the host — the Armed to the Teeth SHD_175 pattern).  The damage
    is a plain optional targeted DealDamage restricted by the new
    ``same_arena_as_defender_unit`` predicate, which encodes both "a unit in the
    defender's arena" and "if this unit isn't attacking a base" (a base defender yields
    no candidates, so the ability fizzles on a base attack with no prompt)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(2, TargetSpec(
                controller="any", kind="unit", optional=True,
                predicates=("same_arena_as_defender_unit",)))],
        ),
    )


@card_ability("SOR", "133")
def _seventh_sister():
    """SOR_133 — Seventh Sister (Unit): Saboteur (keyword). "When this unit deals
    combat damage to an opponent's base: You may deal 3 damage to a ground unit that
    opponent controls."

    Reuses the WhenDealsCombatDamageToBase trigger (Ketsu Onyo SHD_147); optional; the
    target is an enemy ground unit."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[DealDamage(3, TargetSpec(controller="enemy", kind="unit",
                                          arena="ground"))],
        optional=True,
    )


# ── sor-set:03 — Direct damage & removal ─────────────────────────────────────


@card_ability("SOR", "134")
def _ruthless_raider():
    """SOR_134 — Ruthless Raider (Unit, Capital Ship/Imperial/Vehicle, 4/6): "When
    Played/When Defeated: Deal 2 damage to an enemy base and 2 damage to an enemy
    unit."

    Two identical triggers (WhenPlayed + WhenDefeated), each two DealDamage effects:
    the enemy base (controller="enemy", kind="base" — auto-resolves to the single
    opponent base) and an enemy unit (a target choice).  With no enemy unit the second
    effect fizzles while the base damage still lands (per-effect targeting)."""
    def _effects():
        return [
            DealDamage(2, TargetSpec(controller="enemy", kind="base")),
            DealDamage(2, TargetSpec(controller="enemy", kind="unit")),
        ]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=_effects()),
        TriggerAbility(trigger=WhenDefeated(), effects=_effects()),
    ]


def _force_lightning(state, source_ci, target_id, event_ctx):
    """SOR_138 — the chosen unit loses all abilities for this phase (the
    ``abilities_suppressed`` read-layer, Mind Trick LOF_202), then — iff the
    controller controls a Force unit — the pay-any-number-of-resources scaling damage
    is offered (the ``pay_resources_for_tokens`` damage payoff).  A ``None`` target is
    a clean no-op."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    unit.abilities_suppressed = True
    from swu.engine.traits import has_trait
    ctrl = state.player_by_id(source_ci.owner_id)
    if any(has_trait(state, u, "Force")
           for u in ctrl.ground_arena + ctrl.space_arena):
        from swu.engine.actions import push_pay_resources_for_tokens
        push_pay_resources_for_tokens(
            state, source_ci, max_resources=None,
            payoff="damage", damage_per=2, damage_target_id=target_id)
    return state


@card_ability("SOR", "138")
def _force_lightning_sor_138():
    """SOR_138 — Force Lightning (Event, Force): "Choose a unit.  It loses all
    abilities for this phase.  Then, if you control a FORCE unit, pay any number of
    resources and deal 2 damage to the chosen unit for each resource paid this way."

    A single ``CustomEffect.target`` (any unit) that suppresses the target's abilities
    (always) and then, gated on controlling a Force unit, pushes the
    ``pay_resources_for_tokens`` decision in its ``payoff="damage"`` flavour
    (unbounded "any number", 2 damage per resource, dealt to the chosen unit at
    resolve).  Suppression lifts at the round rollover (the Mind Trick LOF_202
    read-layer)."""
    return EventAbility(effects=[CustomEffect(
        fn=_force_lightning,
        target=TargetSpec(controller="any", kind="unit"),
    )])


@card_ability("SOR", "146")
def _zeb_orrelios():
    """SOR_146 — Zeb Orrelios (Unit, Rebel/Spectre, 5/5): "When this unit completes an
    attack: If the defender was defeated, you may deal 4 damage to a ground unit."

    Reuses ``OnAttackDefeatsUnit`` (fires only when this unit defeats a unit via combat
    damage — so "completes an attack" + "defender was defeated" are both intrinsic);
    optional "you may"; the target is any ground unit."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[DealDamage(4, TargetSpec(
            controller="any", kind="unit", arena="ground"))],
        optional=True,
    )


@card_ability("SOR", "153")
def _saw_gerrera():
    """SOR_153 — Saw Gerrera (Unit, Rebel, 5/4): "As an additional cost for each
    opponent to play an event, they must deal 2 damage to their base."

    **Documented simplification.**  The additional cost is modelled as an observer
    trigger (``WhenOpponentPlaysCard(card_type="event")``) that deals 2 damage to the
    event player's base after they play an event.  Base damage is always payable, so
    the after-the-fact observer yields the same board state as a true additional cost
    in every realistic case (the only divergences — an unpayable cost, or Saw being
    removed by the very event — never change the outcome here).  DealDamage
    controller="enemy", kind="base" auto-resolves to the opponent's (event player's)
    base in 2-player."""
    return TriggerAbility(
        trigger=WhenOpponentPlaysCard(card_type="event"),
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base"))],
    )


@card_ability("SOR", "158")
def _jedha_agitator():
    """SOR_158 — Jedha Agitator (Unit, Rebel, 2/1): Saboteur (keyword).  "On Attack:
    If you control a leader unit, deal 2 damage to a ground unit or a base."

    The On Attack trigger is gated by the new ``CONTROLLER_HAS_LEADER_UNIT`` condition
    (a deployed leader in an arena) so it is only collected — no prompt — when a leader
    unit is controlled.  The target "a ground unit or a base" uses kind="unit_or_base"
    + the new ``ground_or_base`` predicate (a base always qualifies; a unit only in the
    ground arena).  Saboteur is the keyword engine's."""
    return TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit_or_base",
            predicates=("ground_or_base",)))],
    )


def _force_throw_discard(state, source_ci, target_id, event_ctx):
    """SOR_167 effect 1 — the opponent discards the first card from their hand
    (the documented "choose a player" -> opponent simplification, K-2SO SOR_145).  If
    the controller controls a Force unit and the discarded card has a positive cost,
    record that cost and arm the follow-up damage (``event_ctx["prior_target_id"]`` —
    the ``requires_prior_target`` gate, In Pursuit TWI_221)."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.hand:
        return state
    from swu.engine.state import Zone
    card = opp.hand.pop(0)
    card.zone = Zone.DISCARD
    opp.discard.append(card)
    from swu.engine.actions import record_hand_discard
    record_hand_discard(state, opp.player_id)
    from swu.engine.traits import has_trait
    ctrl = state.player_by_id(source_ci.owner_id)
    cost = getattr(card.card_def, "cost", 0) or 0
    if cost > 0 and any(has_trait(state, u, "Force")
                        for u in ctrl.ground_arena + ctrl.space_arena):
        event_ctx["force_throw_amount"] = cost
        event_ctx["prior_target_id"] = card.instance_id
    return state


def _force_throw_damage(state, source_ci, target_id, event_ctx):
    """SOR_167 effect 2 — deal the recorded discarded-card cost to the chosen unit."""
    if target_id is None:
        return state
    amt = int(event_ctx.get("force_throw_amount", 0))
    if amt > 0:
        from swu.abilities.resolver import _apply_deal_damage
        _apply_deal_damage(state, target_id, amt,
                           source_name=source_ci.card_def.display_name)
    return state


@card_ability("SOR", "167")
def _force_throw_sor_167():
    """SOR_167 — Force Throw (Event, Force): "Choose a player.  That player discards a
    card from their hand.  Then, if you control a FORCE unit, you may deal damage to a
    unit equal to the cost of the discarded card."

    Two effects sharing the ``resolve_effects`` ``event_ctx`` (the It Binds All Things
    SOR_75 / In Pursuit TWI_221 "record then gate" pattern): (1) a non-targeted
    ``CustomEffect`` — the opponent discards their first card (documented "choose a
    player"->opponent simplification) and, iff a Force unit is controlled and the
    card's cost is positive, records the cost and arms the payoff; (2) an **optional**
    ``CustomEffect`` (target any unit, ``requires_prior_target`` so it prompts only
    when armed, ``optional=True`` for the "you may") that deals the recorded cost."""
    return EventAbility(effects=[
        CustomEffect(fn=_force_throw_discard),
        CustomEffect(
            fn=_force_throw_damage,
            target=TargetSpec(controller="any", kind="unit", optional=True,
                              predicates=("requires_prior_target",)),
        ),
    ])


def _power_failure(state, source_ci, target_id, event_ctx):
    """SOR_170 — defeat every real (non-token) upgrade on the chosen unit.  The
    documented simplification of "any number" -> all (Pryde JTL_133 defeats the first
    upgrade; here Power Failure is a removal event whose realistic use always strips
    every upgrade off the chosen enemy unit).  Ids are snapshotted before defeating so
    a WhenDefeatedAsUpgrade (bounty) firing mid-loop can't disturb the iteration."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    from swu.cards.models import TokenUpgrade
    from swu.abilities.resolver import _apply_defeat_unit
    up_ids = [u.instance_id for u in list(unit.attached_upgrades)
              if not isinstance(u.card_def, TokenUpgrade)]
    for uid in up_ids:
        _apply_defeat_unit(state, uid)
    return state


@card_ability("SOR", "170")
def _power_failure_sor_170():
    """SOR_170 — Power Failure (Event, Tactic): "Defeat any number of upgrades on a
    unit."

    A single ``CustomEffect.target`` (any unit) that defeats all real upgrades on the
    chosen unit — the documented "any number -> all" simplification (choosing the unit
    is the real decision; leaving some of a chosen unit's upgrades alive is never
    advantageous for a removal event)."""
    return EventAbility(effects=[CustomEffect(
        fn=_power_failure,
        target=TargetSpec(controller="any", kind="unit"),
    )])


# ── sor-set:04 — Direct damage & removal ──────────────────────────────────────

def _bombing_run(state, source_ci, target_id, event_ctx):
    """SOR_173 — push the arena-choice modal (bomb_ground / bomb_space); the chosen
    mode deals 3 to every unit in that arena."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["bomb_ground", "bomb_space"])
    return state


@card_ability("SOR", "173")
def _bombing_run_sor_173():
    """SOR_173 — Bombing Run (Event, Tactic): "Choose an arena (ground or space).
    Deal 3 damage to each unit in that arena."

    A ``modal`` decision with two fungible arena modes (``bomb_ground`` /
    ``bomb_space``); the chosen mode deals 3 to each unit in that arena (both
    players' units).  Only a non-empty arena is offered (don't offer a no-op)."""
    return EventAbility(effects=[CustomEffect(fn=_bombing_run)])


def _boba_fett_179_hit(state, source_ci, target_id, event_ctx):
    """SOR_179 — On Attack: if the defender is an exhausted unit that didn't enter
    play this round, deal 3 to it.  "Didn't enter play this round" is approximated by
    the action-phase ``units_played_this_phase`` ledger (one action phase per round,
    where all combat happens)."""
    did = event_ctx.get("defender_id") if event_ctx else None
    if did is None:
        return state
    res = state.find_instance(did)
    if res is None:
        return state
    _, defender = res
    from swu.cards.models import Unit
    if not isinstance(defender.card_def, Unit):
        return state
    if not defender.exhausted:
        return state
    if did in state.game_memory.units_played_this_phase:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, did, 3, source_name=source_ci.card_def.display_name)
    return state


@card_ability("SOR", "179")
def _boba_fett_sor_179():
    """SOR_179 — Boba Fett (Unit, Bounty Hunter/Underworld, 3/5): "On Attack: If this
    unit is attacking an exhausted unit that didn't enter play this round, deal 3
    damage to the defender."

    A single OnAttack ``CustomEffect`` gating on the defender's exhausted state and
    "didn't enter play this round" (the units_played_this_phase proxy); when the gate
    holds it deals 3 to the fixed defender (no prompt)."""
    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_boba_fett_179_hit)])


@card_ability("SOR", "182")
def _bossk_sor_182():
    """SOR_182 — Bossk (Unit, Bounty Hunter/Underworld, 4/5, Ambush): "When you play
    an event: You may deal 2 damage to a unit."

    Ambush is handled by the keyword engine; the residual is a
    ``WhenYouPlayCard(card_type="event")`` optional trigger dealing 2 to any unit."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="event"),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


def _dont_get_cocky(state, source_ci, target_id, event_ctx):
    """SOR_223 — push the reveal-until-stop loop against the chosen unit."""
    from swu.engine.actions import push_reveal_cost_damage
    push_reveal_cost_damage(state, source_ci, target_id, max_reveals=7, threshold=7)
    return state


@card_ability("SOR", "223")
def _dont_get_cocky_sor_223():
    """SOR_223 — Don't Get Cocky (Event, Gambit): "Choose a unit.  One at a time,
    reveal cards from your deck until you choose to stop or have revealed 7 cards.
    If the combined cost of the revealed cards is 7 or less, deal that much damage to
    the chosen unit.  Put the revealed cards on the bottom of your deck in a random
    order."

    A single ``CustomEffect.target`` (any unit) that pushes the ``reveal_cost_damage``
    push-your-luck decision (reveal one at a time, tally the cost, deal it if within
    7; bottom the revealed cards in a seeded-random order)."""
    return EventAbility(effects=[CustomEffect(
        fn=_dont_get_cocky,
        target=TargetSpec(controller="any", kind="unit"),
    )])


@card_ability("SOR", "235")
def _galactic_ambition_sor_235():
    """SOR_235 — Galactic Ambition (Event, Innate): "Play a non-[Heroism] unit from
    your hand for free.  Deal damage to your base equal to its cost."

    Reuses ``play_from_hand`` with ``free`` + ``exclude_aspect="Heroism"`` and the new
    ``then_self_base_damage_cost`` rider (deal the played unit's printed cost to the
    controller's own base)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_from_hand
        push_play_from_hand(
            state, source_ci, free=True, exclude_aspect="Heroism",
            then_self_base_damage_cost=True)
        return state
    return EventAbility(effects=[CustomEffect(fn=_fn)])


# ── sor-set:05 — Card advantage & disruption ──────────────────────────────────

def _inferno_four_scry(state, source_ci, target_id, event_ctx):
    """SOR_31 — look at the top 2, bottom any number, keep the rest on top in any
    order (the reveal_top "bottom" disposition, no aspect damage)."""
    from swu.engine.actions import push_reveal_top_discard_reorder
    push_reveal_top_discard_reorder(
        state, source_ci, count=2, deal_aspect_damage=False, disposition="bottom")
    return state


@card_ability("SOR", "31")
def _inferno_four_sor_31():
    """SOR_31 — Inferno Four (Unit, Fighter/Imperial/Vehicle, 2/3): "When Played/When
    Defeated: Look at the top 2 cards of your deck.  Put any number of them on the
    bottom of your deck and the rest on top in any order."

    Two triggers (WhenPlayed + WhenDefeated), each a ``reveal_top`` decision with the
    ``bottom`` disposition and no aspect damage — a plain look-2-and-reorder scry."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_inferno_four_scry)]),
        TriggerAbility(trigger=WhenDefeated(), effects=[CustomEffect(fn=_inferno_four_scry)]),
    ]


def _search_your_feelings(state, source_ci, target_id, event_ctx):
    """SOR_42 — search the whole deck for a card, draw it, then (effectively) shuffle:
    bottom the un-taken searched cards in a seeded-random order — with window = the
    full deck, that randomises the whole remaining deck."""
    from swu.engine.actions import push_deck_search
    ps = state.player_by_id(source_ci.owner_id)
    push_deck_search(
        state, source_ci, count=1, eligible=lambda cd: True, up_to=True,
        window=len(ps.deck), rest_disposition="bottom")
    return state


@card_ability("SOR", "42")
def _search_your_feelings_sor_42():
    """SOR_42 — Search Your Feelings (Event, Innate): "Search your deck for a card and
    draw it.  (Then, shuffle your deck.)"

    A ``deck_search`` over the entire deck (window = full deck), take up to 1; the
    un-taken cards are bottomed in a seeded-random order — with a full-deck window
    that is the shuffle."""
    return EventAbility(effects=[CustomEffect(fn=_search_your_feelings)])


@card_ability("SOR", "67")
def _rugged_survivors_sor_67():
    """SOR_67 — Rugged Survivors (Unit, Fringe, 3/5, Grit): "On Attack: If you control
    a leader unit, you may draw a card."

    Grit is handled by the keyword engine; the residual is an OnAttack optional
    DrawCards gated by ``CONTROLLER_HAS_LEADER_UNIT``."""
    return TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
        effects=[DrawCards(1)],
        optional=True,
    )


def _emperors_legion(state, source_ci, target_id, event_ctx):
    """SOR_91 — return each unit in the controller's discard that was defeated this
    phase to their hand.  "Defeated this phase" is approximated by
    ``units_defeated_this_round`` (one action phase per round)."""
    from swu.engine.state import Zone
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    defeated = state.game_memory.units_defeated_this_round
    for c in list(ps.discard):
        if isinstance(c.card_def, Unit) and c.instance_id in defeated:
            ps.discard.remove(c)
            c.zone = Zone.HAND
            c.exhausted = False
            c.damage = 0
            ps.hand.append(c)
    return state


@card_ability("SOR", "91")
def _emperors_legion_sor_91():
    """SOR_91 — The Emperor's Legion (Event, Imperial/Supply): "Return each unit in
    your discard pile that was defeated this phase to your hand."

    An automatic (no-choice) sweep — a single ``CustomEffect`` moving each qualifying
    unit from discard to hand (cleared of damage/exhaust per the discard→hand zone
    sanity convention).  "Defeated this phase" uses the units_defeated_this_round
    ledger (one action phase per round)."""
    return EventAbility(effects=[CustomEffect(fn=_emperors_legion)])


def _mon_mothma_search(state, source_ci, target_id, event_ctx):
    """SOR_96 — search the top 5 for a REBEL card and draw it (mandatory if one is
    found); bottom the rest in a seeded-random order."""
    from swu.engine.actions import push_deck_search
    def _rebel(cd):
        return "Rebel" in (getattr(cd, "traits", ()) or ())
    push_deck_search(state, source_ci, count=1, eligible=_rebel, up_to=False, window=5)
    return state


@card_ability("SOR", "96")
def _mon_mothma_sor_96():
    """SOR_96 — Mon Mothma (Unit, Official/Rebel, 1/3): "When Played: Search the top 5
    cards of your deck for a REBEL card, reveal it, and draw it.  (Put the other cards
    on the bottom of your deck in a random order.)"

    A ``deck_search`` (window 5, take 1, mandatory-if-able) restricted to Rebel-trait
    cards; the rest bottom in a seeded-random order."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_mon_mothma_search)])


def _rogue_squadron_return(state, source_ci, target_id, event_ctx):
    """SOR_101 — return a unit that costs 2 or less from discard to hand."""
    from swu.engine.actions import push_return_from_discard
    from swu.cards.models import Unit
    push_return_from_discard(
        state, source_ci, count=1, up_to=True,
        eligible=lambda cd: isinstance(cd, Unit) and (getattr(cd, "cost", 0) or 0) <= 2)
    return state


@card_ability("SOR", "101")
def _rogue_squadron_skirmisher_sor_101():
    """SOR_101 — Rogue Squadron Skirmisher (Unit, Rebel/Speeder/Vehicle, 4/6, Ambush):
    "When Played: Return a unit that costs 2 or less from your discard pile to your
    hand."

    Ambush via the keyword engine; the residual is a ``return_from_discard`` (take up
    to 1 unit costing ≤2)."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_rogue_squadron_return)])


def _home_one_play(state, source_ci, target_id, event_ctx):
    """SOR_102 — play a [Heroism] unit from the discard pile, costing 3 less."""
    from swu.engine.actions import push_play_from_hand
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    eligible = frozenset(
        c.instance_id for c in ps.discard
        if isinstance(c.card_def, Unit)
        and "Heroism" in {a.name for a in (getattr(c.card_def, "aspects", None) or ())})
    push_play_from_hand(
        state, source_ci, from_discard=True, cost_reduction=3, eligible_ids=eligible)
    return state


@card_ability("SOR", "102")
def _home_one_sor_102():
    """SOR_102 — Home One (Unit, Capital Ship/Rebel/Vehicle, 7/7, Restore 2): "Each
    other friendly unit gains Restore 1.  When Played: Play a [Heroism] unit from your
    discard pile.  It costs 3 resources less."

    Restore 2 via the keyword engine.  A ``ConstantAbility`` grants Restore 1 to each
    OTHER friendly unit (read passively by has_keyword's arena-wide granter scan).
    WhenPlayed reuses ``play_from_hand`` (from_discard restricted to Heroism units in
    the discard pile via eligible_ids, cost_reduction 3)."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", predicates=("not_self",)),
            effects=[KeywordGrant("Restore", 1)],
        ),
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_home_one_play)]),
    ]


# ── Gap-fill: card advantage & disruption (sor-set:06) ────────────────────────

@card_ability("SOR", "105")
def _general_krell_sor_105():
    """SOR_105 — General Krell (Unit 5/4, Force/Jedi/Republic): "Each other friendly
    unit gains: 'When Defeated: You may draw a card.'"

    Modelled as an observer on Krell itself (the Saw Gerrera SOR_153 reframe): a
    WhenUnitDefeated filtered to another friendly unit -> you may draw.  Identical
    observable behaviour — a friendly unit dying while Krell is in play lets you
    draw; Krell's own death ("each OTHER friendly unit") does not, via not_self."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(
            controller="friendly", kind="unit", predicates=("not_self",))),
        effects=[DrawCards(1)],
        optional=True,
    )


@card_ability("SOR", "115")
def _agent_kallus_sor_115():
    """SOR_115 — Agent Kallus (Unit 4/4, Imperial/Trooper; Ambush): "When another
    unique unit is defeated: You may draw a card.  Use this ability only once each
    round."

    Ambush is the keyword engine.  A WhenUnitDefeated observer filtered to another
    (not_self) unique unit — any player's — draws.  DEVIATION: the "only once each
    round" limiter is dropped (TriggerAbility has no once-per-round gate — the
    Cassian Andor SOR_13 precedent); the only cost is over-drawing when several
    unique units die in one round."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(
            kind="unit", predicates=("unique", "not_self"))),
        effects=[DrawCards(1)],
        optional=True,
    )


@card_ability("SOR", "147")
def _black_one_sor_147():
    """SOR_147 — Black One (Unit 4/4, Fighter/Resistance/Vehicle): "When Played/When
    Defeated: You may discard your hand.  If you do, draw 3 cards."

    Two optional triggers sharing one "If you do" CustomEffect: accepting discards
    the whole hand (the atomic cost) then draws 3 — bound inline so cost and payoff
    are one indivisible step (Bright Hope SOR_99 pattern)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        from swu.engine.actions import _draw_cards
        ps = state.player_by_id(source_ci.owner_id)
        while ps.hand:
            ci = ps.hand.pop(0)
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
        _draw_cards(state, ps, 3)
        return state
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)], optional=True),
        TriggerAbility(trigger=WhenDefeated(), effects=[CustomEffect(fn=_fn)], optional=True),
    ]


@card_ability("SOR", "150")
def _heroic_sacrifice_sor_150():
    """SOR_150 — Heroic Sacrifice (Event, Tactic): "Draw a card, then attack with a
    unit.  For this attack, it gets +2/+0 and gains: 'When this unit deals combat
    damage: Defeat it.'"

    DrawCards(1) then a granted_attack (+2/+0, then_defeat_attacker — the self-defeat
    rider on the granted_attack decision kind).  The attack is mandatory ("then
    attack with a unit"); with no unit able to attack it fizzles via
    DeclineGrantedAttack."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                            then_defeat_attacker=True)
        return state
    return EventAbility(effects=[DrawCards(1), CustomEffect(fn=_fn)])


@card_ability("SOR", "163")
def _star_wing_scout_sor_163():
    """SOR_163 — Star Wing Scout (Unit 4/1, Fighter/Vehicle): "When Defeated: If you
    have the initiative, draw 2 cards."

    A WhenDefeated trigger gated by CONTROLLER_HAS_INITIATIVE (don't-offer-a-no-op)
    -> draw 2."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


@card_ability("SOR", "171")
def _mission_briefing_sor_171():
    """SOR_171 — Mission Briefing (Event, Plan): "Choose a player.  They draw 2
    cards."

    Reduced to "you draw 2 cards": choosing yourself is the only advantageous play
    (giving an opponent cards is never beneficial — the Profundity JTL_154
    choose-a-player simplification, in the beneficial direction)."""
    return EventAbility(effects=[DrawCards(2)])


@card_ability("SOR", "175")
def _forced_surrender_sor_175():
    """SOR_175 — Forced Surrender (Event, Plan): "Draw 2 cards.  Each opponent whose
    base you've damaged this phase discards 2 cards from their hand."

    DrawCards(2) then a CustomEffect: game_memory.base_damage_dealt_this_phase records
    the combat base damage the controller has dealt this phase (Cassian SOR_13's
    ledger); if > 0 the (single) opponent discards their first 2 cards (the K-2SO
    SOR_145 first-card discard simplification).  DEVIATION: only combat base damage
    is tracked (ability base damage is not), matching the Cassian ledger's scope."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        dealt = state.game_memory.base_damage_dealt_this_phase.get(source_ci.owner_id, 0)
        if dealt > 0:
            opp = state.players[1 - state.player_index(source_ci.owner_id)]
            for _ in range(2):
                if opp.hand:
                    ci = opp.hand.pop(0)
                    ci.zone = Zone.DISCARD
                    opp.discard.append(ci)
        return state
    return EventAbility(effects=[DrawCards(2), CustomEffect(fn=_fn)])


# ── Gap-fill: card advantage & disruption (sor-set:07) ────────────────────────

@card_ability("SOR", "181")
def _jabba_the_hutt_sor_181():
    """SOR_181 — Jabba the Hutt (Unit, Hutt/Underworld): "Each TRICK event you play
    costs 1 resource less.  When Played: Search the top 8 cards of your deck for a
    TRICK event, reveal it, and draw it."

    The cost reducer is a ``StandingPlayDiscount`` (Director Krennic JTLP_1) with the
    new ``applies_to="trick_event"`` predicate and ``once_per_round=False`` (every
    Trick event, not just the first) — read at the play-cost seam so both
    affordability and payment see it.  The When Played search reuses the
    ``deck_search`` seam (``push_deck_search``, Recruit SOR_123 mandatory-take flavour:
    ``up_to=False`` forces the draw while an eligible Trick event remains) with a
    window of 8 and an event-with-Trick-trait ``eligible`` predicate; the un-taken
    searched cards are bottomed in a random order."""
    def _search(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_deck_search
        from swu.cards.models import Event
        def _elig(cd):
            return isinstance(cd, Event) and "Trick" in (getattr(cd, "traits", ()) or ())
        push_deck_search(state, source_ci, count=1, eligible=_elig,
                         up_to=False, window=8)
        return state
    return [
        StandingPlayDiscount(amount=1, applies_to="trick_event", once_per_round=False),
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_search)]),
    ]


@card_ability("SOR", "183")
def _bounty_hunter_crew_sor_183():
    """SOR_183 — Bounty Hunter Crew (Unit, Bounty Hunter/Underworld, Ambush): "When
    Played: You may return an event from a discard pile to its owner's hand."

    Ambush is the keyword layer.  The residual When Played reuses the
    ``return_from_discard`` seam (Razor Crest SHD_44) with an event ``eligible``
    predicate; ``up_to=True`` supplies the "you may" (returning 0 is legal).
    DEVIATION (documented): the seam scans only the controller's own discard pile
    (returning to the controller's hand), not "a discard pile" (either).  Returning
    an *enemy* event to the enemy's hand is only ever a downside, so no rational
    controller does it — restricting to the own discard loses no meaningful play,
    and the seam fizzles cleanly with no prompt when the controller's discard holds
    no event."""
    def _return_event(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_return_from_discard
        from swu.cards.models import Event
        push_return_from_discard(state, source_ci, count=1, up_to=True,
                                 eligible=lambda cd: isinstance(cd, Event))
        return state
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_return_event)])


@card_ability("SOR", "188")
def _chopper_sor_188():
    """SOR_188 — Chopper (Unit, Droid/Rebel/Spectre, 1/3): "While you control another
    SPECTRE unit, this unit gains Raid 1.  On Attack: Discard a card from the
    defending player's deck.  If it's an event, exhaust a resource that player
    controls."

    Clause 1 is the conditional self-grant + sanitiser pattern (Hunting Nexu SHD_168):
    a self-targeted ``ConstantAbility`` ``KeywordGrant("Raid", 1)`` gated by
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Spectre")`` (excludes Chopper itself); the
    keyword sanitiser strips the mis-tagged printed Raid so it applies only while the
    condition holds.  Clause 2 is a plain ``OnAttack`` whose inline ``CustomEffect``
    mills the top card of the defending player's deck (the Shuttle Tydirium JTL_200
    mill idiom) and, if that card is an Event, exhausts one of that player's ready
    resources (``_exhaust_resources``, guarded so an empty/tapped resource row is a
    clean no-op).  The defending player is the opponent (On Attack always targets an
    enemy)."""
    def _on_attack(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        from swu.cards.models import Event
        from swu.engine.actions import _exhaust_resources
        opp = state.players[1 - state.player_index(source_ci.owner_id)]
        if not opp.deck:
            return state
        card = opp.deck.pop(0)
        card.face_down = False
        card.zone = Zone.DISCARD
        opp.discard.append(card)
        if isinstance(card.card_def, Event):
            if any(not r.exhausted for r in opp.resources):
                _exhaust_resources(opp, 1)
        return state
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Raid", value=1)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                     "Spectre"),
        ),
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_on_attack)]),
    ]


@card_ability("SOR", "199")
def _bamboozle_sor_199():
    """SOR_199 — Bamboozle (Event, Trick): "You may discard a Cunning card from your
    hand instead of paying this event's cost.  Exhaust a unit and return each upgrade
    on it to its owner's hand."

    A single ``CustomEffect`` with its own target (the CustomEffect.target seam):
    the controller picks any unit, it is exhausted, and each non-token upgrade on it
    is returned to its owner's hand (``_apply_return_to_hand``'s upgrade branch,
    Jabba ASH_42).  DEVIATION (documented): the alternative cost ("discard a Cunning
    card instead of paying") is a payment *option*, not part of the effect — the card
    remains fully playable at its printed cost, so omitting the discount path leaves
    it functionally complete (no generic discard-instead-of-pay cost seam exists)."""
    def _bamboozle(state, source_ci, target_id, event_ctx):
        from swu.cards.models import TokenUpgrade
        from swu.abilities.resolver import _apply_return_to_hand
        result = state.find_instance(target_id)
        if result is None:
            return state
        _, unit_ci = result
        unit_ci.exhausted = True
        for up in list(unit_ci.attached_upgrades):
            if isinstance(up.card_def, TokenUpgrade):
                continue
            _apply_return_to_hand(state, up.instance_id)
        return state
    return EventAbility(effects=[CustomEffect(
        fn=_bamboozle, target=TargetSpec(kind="unit", controller="any"))])


@card_ability("SOR", "200")
def _spark_of_rebellion_sor_200():
    """SOR_200 — Spark of Rebellion (Event, Spectre): "Look at an opponent's hand and
    discard a card from it."

    A single ``CustomEffect`` pushes the private ``look_hand`` decision (Viper Probe
    Droid SOR_228 — so the player actually sees the hand) and discards the opponent's
    first hand card (the K-2SO SOR_145 / Garindan SEC_186 first-card simplification).
    The look snapshots the full hand before the discard, matching "look, then
    discard"; an empty opponent hand is a clean acknowledge with nothing discarded."""
    def _spark(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_look_opponent_hand, record_hand_discard
        from swu.engine.state import Zone
        push_look_opponent_hand(state, source_ci)
        opp = state.players[1 - state.player_index(source_ci.owner_id)]
        if opp.hand:
            card = opp.hand.pop(0)
            card.zone = Zone.DISCARD
            opp.discard.append(card)
            record_hand_discard(state, opp.player_id)
        return state
    return EventAbility(effects=[CustomEffect(fn=_spark)])


@card_ability("SOR", "201")
def _bodhi_rook_sor_201():
    """SOR_201 — Bodhi Rook (Unit, Imperial/Rebel, 3/3): "When Played: Look at an
    opponent's hand and discard a non-unit card from it."

    Like Spark of Rebellion SOR_200 but the discard is *filtered to non-units*: the
    ``CustomEffect`` pushes the ``look_hand`` decision then discards the opponent's
    first NON-UNIT card (the first-card simplification, filtered per the card text —
    plain ``DiscardFromHand`` can't express the filter).  No non-unit in the
    opponent's hand ⇒ nothing discarded (a clean look)."""
    def _bodhi(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_look_opponent_hand, record_hand_discard
        from swu.engine.state import Zone
        from swu.cards.models import Unit
        push_look_opponent_hand(state, source_ci)
        opp = state.players[1 - state.player_index(source_ci.owner_id)]
        for i, ci in enumerate(opp.hand):
            if not isinstance(ci.card_def, Unit):
                card = opp.hand.pop(i)
                card.zone = Zone.DISCARD
                opp.discard.append(card)
                record_hand_discard(state, opp.player_id)
                break
        return state
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_bodhi)])


@card_ability("SOR", "187")
def _i_had_no_choice_sor_187():
    """SOR_187 — I Had No Choice (Event, Trick): "Choose up to 2 non-leader units.
    An opponent chooses 1 of those units.  Return that unit to its owner's hand and
    put the other on the bottom of its owner's deck."

    A thin ``CustomEffect`` adapter (Palpatine SOR_135 pattern) onto the new
    ``opponent_split_bounce`` decision kind (the opponent_chooses_target SHD_246 /
    say_no SOR_233 decider-shift): the controller selects up to 2 non-leader units,
    then the opponent picks which returns to its owner's hand — the other is put on
    the bottom of its owner's deck (reusing ``_apply_return_to_hand`` /
    ``_apply_put_on_deck``).  Choosing 1 returns just that one; choosing 0 or an
    empty board is a clean fizzle."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_opponent_split_bounce
        push_opponent_split_bounce(state, source_ci)
        return state
    return EventAbility(effects=[CustomEffect(fn=_fn)])


# ── Gap-fill: card advantage & disruption (sor-set:08) ────────────────────────

@card_ability("SOR", "202")
def _cantina_bouncer_sor_202():
    """SOR_202 — Cantina Bouncer (Unit, Fringe, 3/5): "When Played: You may return
    a non-leader unit to its owner's hand."

    Optional WhenPlayed with a single ``ReturnToHand`` targeting any non-leader unit
    (either player's — controller's choice); the "you may" auto-declines with no
    prompt when no non-leader unit is in play."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(
            controller="any", kind="unit", predicates=("non_leader",)))],
        optional=True,
    )


def _mining_guild_pay_draw(state, source_ci, target_id, event_ctx):
    """Pay 2 resources, then draw a card ("if you do" binding — Bright Hope SOR_99).
    Affordability is guaranteed by the trigger's ``CONTROLLER_N_PLUS_READY_RESOURCES(2)``
    gate; re-checked defensively before paying."""
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 2:
        return state
    from swu.engine.actions import _exhaust_resources, _draw_cards
    _exhaust_resources(ps, 2)
    _draw_cards(state, ps, 1)
    return state


@card_ability("SOR", "206")
def _mining_guild_tie_fighter_sor_206():
    """SOR_206 — Mining Guild TIE Fighter (Unit, Fighter/Fringe/Vehicle, 1/2): "On
    Attack: You may pay [2 resources]. If you do, draw a card."

    Optional OnAttack gated by ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` (the
    "don't offer a no-op" pattern), whose one CustomEffect binds the payment and the
    draw (LAW_214 Boba Fett pay-then-effect)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_mining_guild_pay_draw)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, 2),
    )


@card_ability("SOR", "209")
def _pirated_starfighter_sor_209():
    """SOR_209 — Pirated Starfighter (Unit, Fighter/Underworld/Vehicle, 2/4): "Raid 1.
    When Played: Return a friendly non-leader unit to its owner's hand."

    Raid is the keyword engine.  A mandatory WhenPlayed ``ReturnToHand`` of a friendly
    non-leader unit — Pirated Starfighter is itself an eligible target (it just entered
    play), so the effect always has at least one choice and never fizzles."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReturnToHand(TargetSpec(
            controller="friendly", kind="unit", predicates=("non_leader",)))],
    )


def _youre_my_only_hope(state, source_ci, target_id, event_ctx):
    """Look at the top card; you may play it costing 5 less, or free if your base has
    5 or less remaining HP.  Modelled with the ``peek_top`` ``may_play`` mode (the
    play carries a cost_reduction / free) — reveal + KeepTopCard/PlayTopCard."""
    from swu.engine.actions import push_peek_top
    ps = state.player_by_id(source_ci.owner_id)
    base = ps.base_instance
    free = base is not None and (base.card_def.hp - base.damage) <= 5
    push_peek_top(state, source_ci, mode="may_play", cost_reduction=5, free=free)
    return state


@card_ability("SOR", "246")
def _youre_my_only_hope_sor_246():
    """SOR_246 — You're My Only Hope (Event, Gambit, 3): "Look at the top card of
    your deck. You may play it. It costs [5 resources] less. If your base has 5 or
    less remaining HP, you may play it for free instead." """
    return EventAbility(effects=[CustomEffect(fn=_youre_my_only_hope)])


def _restock(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(state, source_ci, count=4)
    return state


@card_ability("SOR", "252")
def _restock_sor_252():
    """SOR_252 — Restock (Event, Supply, 1): "Choose up to 4 cards in a discard pile.
    Put them on the bottom of their owner's deck in a random order."

    A thin adapter onto the new ``bottom_from_discard`` decision kind: the controller
    selects up to 4 cards across either discard pile; each returns to the bottom of
    its owner's deck, the collected picks shuffled first for the random order."""
    return EventAbility(effects=[CustomEffect(fn=_restock)])


# ── Gap-filling campaign: sor-set groups 10–12 (combat tricks, buffs & tempo) ──

def _ready_n_resources(ps, n: int) -> int:
    """Ready up to ``n`` of ``ps``'s exhausted resources (resources are fungible,
    so which ones is immaterial — no decision needed).  Returns the count readied."""
    readied = 0
    for r in ps.resources:
        if readied >= n:
            break
        if r.exhausted:
            r.exhausted = False
            readied += 1
    return readied


def _has_aspect(cd, aspect: str) -> bool:
    return aspect in {a.name for a in (getattr(cd, "aspects", None) or ())}


# ── SOR_12 IG-88 (Leader) ─────────────────────────────────────────────────────

def _ig88_activate(state, source_ci, target_id, event_ctx):
    """Undeployed: "Attack with a unit.  If you control more units than the
    defending player, the attacker gets +1/+0 for this attack."  The defending
    player is the (single) opponent, so the +1/+0 is decided here from the current
    board (stable between activation and the immediately-resolved attack).  A thin
    adapter onto push_granted_attack (mandatory attack)."""
    from swu.engine.actions import push_granted_attack
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    my = len(ps.ground_arena) + len(ps.space_arena)
    their = len(opp.ground_arena) + len(opp.space_arena)
    bonus = 1 if my > their else 0
    push_granted_attack(state, source_ci, power_bonus=bonus, hp_bonus=0)
    return state


@card_ability("SOR", "12")
def _ig88():
    """IG-88 (SOR_12) — Leader.

    Undeployed Action [Exhaust]: attack with a unit; the attacker gets +1/+0 if
    you control more units than the defending player (a granted_attack adapter).
    Deployed: "Each other friendly unit gains Raid 1" — a ConstantAbility whose
    Raid grant is read passively by keyword_value; it is active only while IG-88 is
    in an arena (the deployment gate, since the constant scan never sees an
    undeployed leader in base_zone).  IG-88's own printed Raid is the keyword layer."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_ig88_activate)],
            title="Attack with a unit (+1/+0 if you have more units)",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            effects=[KeywordGrant("Raid", value=1)],
        ),
    ]


# ── SOR_15 Boba Fett (Leader) ─────────────────────────────────────────────────

def _boba_ready_one(state, source_ci, target_id, event_ctx):
    """Undeployed: "You may exhaust this leader.  If you do, ready a resource."
    The payoff (ready a resource) requires exhausting the leader, so we only spend
    the leader when there is an exhausted resource to ready ("If you do" binding)."""
    if source_ci.exhausted:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if _ready_n_resources(ps, 1):
        source_ci.exhausted = True
    return state


def _boba_ready_two(state, source_ci, target_id, event_ctx):
    """Deployed: "ready up to 2 resources" (mandatory, fungible -> no decision)."""
    ps = state.player_by_id(source_ci.owner_id)
    _ready_n_resources(ps, 2)
    return state


@card_ability("SOR", "15")
def _boba_fett():
    """Boba Fett (SOR_15) — Leader.

    Undeployed: "When an enemy unit leaves play: You may exhaust this leader.  If
    you do, ready a resource" — a WhenUnitDefeated(enemy) optional trigger (defeat
    is the common "leaves play"; documented simplification).
    Deployed: "When this unit completes an attack: If an enemy unit left play this
    phase, ready up to 2 resources" — a WhenAttackEnds trigger gated by
    ENEMY_UNIT_DEFEATED_THIS_PHASE."""
    return [
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="enemy", kind="unit")),
            effects=[CustomEffect(fn=_boba_ready_one)],
            optional=True,
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_boba_ready_two)],
            condition=ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE),
            deployed_only=True,
        ),
    ]


# ── SOR_16 Grand Admiral Thrawn (Leader) ──────────────────────────────────────

def _thrawn_reveal_exhaust(state, source_ci, target_id, event_ctx):
    """Reveal the top card of a player's deck; exhaust a unit that costs <= the
    revealed card.  Simplification (fully functional, documented): the deck peeked
    is the opponent's and the exhaust auto-targets the highest-cost READY enemy
    unit whose printed cost <= the revealed cost — the controller would never
    exhaust their own unit, and a single peek/exhaust needs no player prompt to be
    correct.  The revealed card stays on top of the deck (only revealed)."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.deck:
        return state
    revealed_cost = getattr(opp.deck[0].card_def, "cost", 0) or 0
    candidates = [
        u for u in opp.ground_arena + opp.space_arena
        if not u.exhausted and (getattr(u.card_def, "cost", 0) or 0) <= revealed_cost
    ]
    if candidates:
        best = max(candidates, key=lambda u: getattr(u.card_def, "cost", 0) or 0)
        best.exhausted = True
    return state


@card_ability("SOR", "16")
def _grand_admiral_thrawn():
    """Grand Admiral Thrawn (SOR_16) — Leader.

    "Reveal the top card of any player's deck.  Exhaust a unit that costs the same
    as or less than the revealed card" — undeployed as an Action [1 resource,
    exhaust], deployed as an optional On Attack.  The "When the action phase
    starts: Look at the top card of each player's deck" clauses are pure
    information (no state change) and are a mechanical no-op in the headless
    engine, so they are intentionally not registered."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_thrawn_reveal_exhaust)],
            title="Reveal top card; exhaust a unit costing <= it",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_thrawn_reveal_exhaust)],
            optional=True,
            deployed_only=True,
        ),
    ]


# ── SOR_18 Jyn Erso (Leader) ──────────────────────────────────────────────────

def _jyn_activate(state, source_ci, target_id, event_ctx):
    """Undeployed: "Attack with a unit.  The defender gets -1/-0 for this attack"
    — a granted_attack carrying the new defender_power_bonus (applied as a
    this_attack modifier on the chosen defender)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, defender_power_bonus=-1, defender_hp_bonus=0)
    return state


@card_ability("SOR", "18")
def _jyn_erso():
    """Jyn Erso (SOR_18) — Leader.

    Undeployed Action [Exhaust]: attack with a unit; the defender gets -1/-0 for
    this attack (granted_attack defender_power_bonus seam).
    Deployed: "While a friendly unit is attacking, the defender gets -1/-0" — a
    ConstantAbility(target=enemy unit) with the new ``while_target_defending`` flag,
    so its -1 power lands only on the enemy unit currently being attacked (in a
    2-player game the attacker is necessarily friendly to Jyn)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_jyn_activate)],
            title="Attack with a unit (defender gets -1/-0)",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="enemy", kind="unit"),
            effects=[StatBonus(power=-1, hp=0)],
            while_target_defending=True,
        ),
    ]


# ── SOR_19 Security Complex (Base) ────────────────────────────────────────────

@card_ability("SOR", "19")
def _security_complex():
    """Security Complex (SOR_19) — Base.
    "Epic Action: Give a Shield token to a non-leader unit." """
    return ActivatedAbility(
        costs=[],
        effects=[GiveToken("Shield", TargetSpec(
            controller="any", kind="unit", predicates=("non_leader",)))],
        title="Give a Shield token to a non-leader unit",
        epic=True,
    )


# ── SOR_28 Jedha City (Base) ──────────────────────────────────────────────────

@card_ability("SOR", "28")
def _jedha_city():
    """Jedha City (SOR_28) — Base.
    "Epic Action: Give a non-leader unit -4/-0 for this phase." """
    return ActivatedAbility(
        costs=[],
        effects=[ModifyStats(power=-4, hp=0, target=TargetSpec(
            controller="any", kind="unit", predicates=("non_leader",)),
            duration=Duration.THIS_PHASE)],
        title="Give a non-leader unit -4/-0 for this phase",
        epic=True,
    )


# ── SOR_35 Lieutenant Childsen (Unit) ─────────────────────────────────────────

def _childsen_when_played(state, source_ci, target_id, event_ctx):
    """"Reveal up to 4 [Vigilance] cards from your hand.  For each card revealed
    this way, give an Experience token to this unit."  Revealing Vigilance cards
    only benefits Childsen (Experience on itself), so we reveal the maximum
    (min(4, Vigilance cards in hand)) and give that many Experience to self."""
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    n = min(4, sum(1 for c in ps.hand if _has_aspect(c.card_def, "Vigilance")))
    for _ in range(n):
        attach_token(state, ps, source_ci, "Experience")
    return state


@card_ability("SOR", "35")
def _lieutenant_childsen():
    """Lieutenant Childsen (SOR_35) — Unit.  Sentinel is the keyword layer.
    "When Played: Reveal up to 4 [Vigilance] cards from your hand.  For each card
    revealed this way, give an Experience token to this unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_childsen_when_played)],
    )


# ── SOR_36 Gideon Hask (Unit) ─────────────────────────────────────────────────

@card_ability("SOR", "36")
def _gideon_hask():
    """Gideon Hask (SOR_36) — Unit.
    "When an enemy unit is defeated: Give an Experience token to a friendly unit." """
    return TriggerAbility(
        trigger=WhenUnitDefeated(
            filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit"))],
    )


# ── SOR_37 Academy Defense Walker (Unit) ──────────────────────────────────────

@card_ability("SOR", "37")
def _academy_defense_walker():
    """Academy Defense Walker (SOR_37) — Unit.  Sentinel is the keyword layer.
    "When Played: Give an Experience token to each friendly damaged unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit", predicates=("damaged",),
            fixed=EACH_FRIENDLY))],
    )


# ── SOR_39 AT-AT Suppressor (Unit) ────────────────────────────────────────────

@card_ability("SOR", "39")
def _at_at_suppressor():
    """AT-AT Suppressor (SOR_39) — Unit.
    "When Played: Exhaust all ground units." (both players' ground units)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(
            controller="any", kind="unit", arena="ground", fixed=EACH_IN_PLAY))],
    )


# ── SOR_47 Kanan Jarrus (Unit) ────────────────────────────────────────────────

def _kanan_on_attack(state, source_ci, target_id, event_ctx):
    """"You may discard 1 card from the defending player's deck for each friendly
    SPECTRE unit.  Heal 1 damage from your base for each different aspect among the
    discarded cards."  Defending player = the opponent (Kanan is attacking); mill
    that many from the top of their deck, then heal our base by the number of
    distinct aspects milled."""
    from swu.engine.traits import has_trait
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    spectre = sum(1 for u in ps.ground_arena + ps.space_arena
                  if has_trait(state, u, "Spectre"))
    aspects = set()
    for _ in range(spectre):
        if not opp.deck:
            break
        ci = opp.deck.pop(0)
        ci.zone = Zone.DISCARD
        opp.discard.append(ci)
        for a in (getattr(ci.card_def, "aspects", None) or ()):
            aspects.add(a.name)
    base = ps.base_instance
    if base is not None and aspects:
        base.damage = max(0, base.damage - len(aspects))
    return state


@card_ability("SOR", "47")
def _kanan_jarrus():
    """Kanan Jarrus (SOR_47) — Unit.
    "On Attack: You may discard 1 card from the defending player's deck for each
    friendly SPECTRE unit.  Heal 1 damage from your base for each different aspect
    among the discarded cards." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_kanan_on_attack)],
        optional=True,
    )


# ── SOR_50 The Ghost (Unit) ───────────────────────────────────────────────────

@card_ability("SOR", "50")
def _the_ghost():
    """The Ghost (SOR_50) — Unit.  Shielded is the keyword layer.
    "When Played/On Attack: You may give a Shield token to another SPECTRE unit." """
    def _shield_spectre():
        return [GiveToken("Shield", TargetSpec(
            controller="friendly", kind="unit", traits=("Spectre",),
            predicates=("not_self",)))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=_shield_spectre(),
                       optional=True),
        TriggerAbility(trigger=OnAttack(), effects=_shield_spectre(),
                       optional=True),
    ]


# ── SOR_55 The Force Is With Me (Event) ───────────────────────────────────────

def _force_is_with_me(state, source_ci, target_id, event_ctx):
    """Choose a friendly unit; give it 2 Experience tokens; if you control a FORCE
    unit, also give it a Shield token; you may attack with the chosen unit (the
    shared-target pattern: everything acts on the chosen ``target_id``)."""
    from swu.engine.tokens import attach_token
    from swu.engine.traits import has_trait
    from swu.engine.actions import push_granted_attack, _find_in_arenas
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    target = _find_in_arenas(ps, target_id)
    if target is None:
        return state
    attach_token(state, ps, target, "Experience")
    attach_token(state, ps, target, "Experience")
    if any(has_trait(state, u, "Force") for u in ps.ground_arena + ps.space_arena):
        attach_token(state, ps, target, "Shield")
    push_granted_attack(state, source_ci, attacker_id=target_id, optional=True)
    return state


@card_ability("SOR", "55")
def _the_force_is_with_me():
    """The Force Is With Me (SOR_55) — Event.
    "Choose a friendly unit and give 2 Experience tokens to it.  If you control a
    FORCE unit, also give a Shield token to the chosen unit.  You may attack with
    the chosen unit." """
    return EventAbility(effects=[CustomEffect(
        fn=_force_is_with_me,
        target=TargetSpec(controller="friendly", kind="unit"))])


# ── SOR_57 Protector (Upgrade) ────────────────────────────────────────────────

@card_ability("SOR", "57")
def _protector():
    """Protector (SOR_57) — Upgrade.  "Attached unit gains Sentinel."
    A ConstantAbility(target=SELF, KeywordGrant("Sentinel")); the keyword is
    conferred on the host by the has_keyword upgrade scan."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
    )


# ── SOR_60 Distant Patroller (Unit) ───────────────────────────────────────────

@card_ability("SOR", "60")
def _distant_patroller():
    """Distant Patroller (SOR_60) — Unit.
    "When Defeated: You may give a Shield token to a [Vigilance] unit." """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="friendly", kind="unit", aspects=("Vigilance",)))],
        optional=True,
    )


# ── SOR_65 Baze Malbus (Unit) ─────────────────────────────────────────────────

@card_ability("SOR", "65")
def _baze_malbus():
    """Baze Malbus (SOR_65) — Unit.  Grit is the keyword layer.
    "While you have the initiative, this unit gains Sentinel" — a conditional
    self-grant ConstantAbility; the keyword sanitiser strips Baze's printed
    Sentinel so this ability (not an always-on bar) owns it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


# ── SOR_68 Cargo Juggernaut (Unit) ────────────────────────────────────────────

def _cargo_juggernaut(state, source_ci, target_id, event_ctx):
    """"If you control another [Vigilance] unit, heal 4 damage from your base." """
    ps = state.player_by_id(source_ci.owner_id)
    others = [u for u in ps.ground_arena + ps.space_arena
              if u.instance_id != source_ci.instance_id
              and _has_aspect(u.card_def, "Vigilance")]
    if others:
        base = ps.base_instance
        if base is not None:
            base.damage = max(0, base.damage - 4)
    return state


@card_ability("SOR", "68")
def _cargo_juggernaut_card():
    """Cargo Juggernaut (SOR_68) — Unit.  Shielded is the keyword layer.
    "When Played: If you control another [Vigilance] unit, heal 4 damage from your
    base." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_cargo_juggernaut)],
    )


# ── SOR_70 Devotion (Upgrade) ─────────────────────────────────────────────────

@card_ability("SOR", "70")
def _devotion():
    """Devotion (SOR_70) — Upgrade.  "Attached unit gains Restore 2."
    A ConstantAbility(target=SELF, KeywordGrant("Restore", 2)); keyword_value reads
    the numeric grant off the host's attached upgrades."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", value=2)],
    )


# ── SOR_73 Moment of Peace (Event) ────────────────────────────────────────────

@card_ability("SOR", "73")
def _moment_of_peace():
    """Moment of Peace (SOR_73) — Event.  "Give a Shield token to a unit." """
    return EventAbility(effects=[GiveToken("Shield", TargetSpec(
        controller="any", kind="unit"))])


# ── SOR_76 Make an Opening (Event) ────────────────────────────────────────────

@card_ability("SOR", "76")
def _make_an_opening():
    """Make an Opening (SOR_76) — Event.
    "Give a unit -2/-2 for this phase.  Heal 2 damage from your base."
    The targeted debuff is ordered before the fixed self-base heal so the resolver
    prompts exactly once (fixed-before-targeted pattern)."""
    return EventAbility(effects=[
        ModifyStats(power=-2, hp=-2, target=TargetSpec(
            controller="any", kind="unit"), duration=Duration.THIS_PHASE),
        Heal(2, TargetSpec(controller="friendly", kind="base", fixed=EACH_FRIENDLY)),
    ])


# ── SOR_80 General Tagge (Unit) ───────────────────────────────────────────────

def _general_tagge_effect(state, source_ci, target_id, event_ctx):
    """"Give an Experience token to each of up to 3 TROOPER units" — the
    select_token decision kind (Medal Ceremony SOR_245 pattern)."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Experience", max_targets=3,
                      controller="any", kind="unit", traits=["Trooper"])
    return state


@card_ability("SOR", "80")
def _general_tagge():
    """General Tagge (SOR_80) — Unit.
    "When Played: Give an Experience token to each of up to 3 TROOPER units." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_general_tagge_effect)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set groups 13, 14, 15 (combat tricks, buffs & tempo)
# ══════════════════════════════════════════════════════════════════════════════

# ── SOR_82 Emperor's Royal Guard (Unit) ───────────────────────────────────────
@card_ability("SOR", "82")
def _emperors_royal_guard():
    """While you control an OFFICIAL unit, this unit gains Sentinel.
    While you control Emperor Palpatine (leader or unit), this unit gets +0/+1.

    Two conditional self-grants.  The Sentinel grant is a ConstantAbility(SELF,
    KeywordGrant) whose registration makes the keyword sanitiser strip the
    mistagged printed Sentinel (Hunting Nexu SHD_168 pattern)."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, "Official"),
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=0, hp=1)],
            condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                     "Emperor Palpatine"),
        ),
    ]


# ── SOR_94 Bail Organa (Unit) ─────────────────────────────────────────────────
@card_ability("SOR", "94")
def _bail_organa():
    """Action [Exhaust]: Give an Experience token to another friendly unit."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit", predicates=("not_self",)))],
        title="Give an Experience token to another friendly unit",
    )


# ── SOR_100 Wedge Antilles (Unit) ─────────────────────────────────────────────
@card_ability("SOR", "100")
def _wedge_antilles():
    """Each friendly VEHICLE unit gets +1/+1 and gains Ambush."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Vehicle",)),
        effects=[StatBonus(power=1, hp=1), KeywordGrant("Ambush")],
    )


# ── SOR_106 Attack Pattern Delta (Event) ──────────────────────────────────────
def _apd_buff(power: int, hp: int):
    """Give the chosen friendly unit +power/+hp for this phase and record it so a
    later clause of Attack Pattern Delta offers only 'another'/'a third' unit
    (the ``excludes_event_targets`` accumulating-set predicate)."""
    def _fn(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        from swu.abilities.resolver import _make_modifier
        state.modifiers.append(_make_modifier(
            state, source_ci.instance_id, target_id,
            power=power, hp=hp, duration=Duration.THIS_PHASE))
        event_ctx.setdefault("excluded_target_ids", set()).add(target_id)
        return state
    return _fn


@card_ability("SOR", "106")
def _attack_pattern_delta():
    """Give a friendly unit +3/+3, another +2/+2, and a third +1/+1 for this
    phase — three sequential buffs to distinct friendly units."""
    return EventAbility(effects=[
        CustomEffect(fn=_apd_buff(3, 3),
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_apd_buff(2, 2),
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("excludes_event_targets",))),
        CustomEffect(fn=_apd_buff(1, 1),
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("excludes_event_targets",))),
    ])


# ── SOR_108 Vanguard Infantry (Unit) ──────────────────────────────────────────
@card_ability("SOR", "108")
def _vanguard_infantry():
    """When Defeated: You may give an Experience token to a unit."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Experience", TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


# ── SOR_109 Colonel Yularen (Unit) ────────────────────────────────────────────
@card_ability("SOR", "109")
def _colonel_yularen():
    """When you play a [Command] unit (including this one): Heal 1 damage from
    your base."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(aspect="Command", card_type="unit",
                                exclude_self=False),
        effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
    )


# ── SOR_110 Frontline Shuttle (Unit) ──────────────────────────────────────────
def _frontline_shuttle_attack(state, source_ci, target_id, event_ctx):
    """Attack with any unit, even if exhausted; it can't attack bases this attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, allow_exhausted=True, no_base=True)
    return state


@card_ability("SOR", "110")
def _frontline_shuttle():
    """Action [defeat this unit]: Attack with a unit, even if it's exhausted. It
    can't attack bases for this attack."""
    return ActivatedAbility(
        costs=[DefeatSelf()],
        effects=[CustomEffect(fn=_frontline_shuttle_attack)],
        title="Attack with a unit (even if exhausted; not bases)",
    )


# ── SOR_114 Escort Skiff (Unit) ───────────────────────────────────────────────
@card_ability("SOR", "114")
def _escort_skiff():
    """While you control another [Command] unit, this unit gains Ambush."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Ambush")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT, "Command"),
    )


# ── SOR_116 Steadfast Battalion (Unit) ────────────────────────────────────────
@card_ability("SOR", "116")
def _steadfast_battalion():
    """On Attack: If you control a leader unit, give a friendly unit +2/+2 for
    this phase.  (Overwhelm is the keyword layer.)"""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=2, hp=2, target=TargetSpec(
            controller="friendly", kind="unit"), duration=Duration.THIS_PHASE)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
    )


# ── SOR_118 97th Legion (Unit) ────────────────────────────────────────────────
@card_ability("SOR", "118")
def _97th_legion():
    """This unit gets +1/+1 for each resource you control."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=1, count="controller_resources")],
    )


# ── SOR_119 Reinforcement Walker (Unit) ───────────────────────────────────────
def _reinforcement_walker_peek(state, source_ci, target_id, event_ctx):
    """Look at the top card; draw it, or discard it and heal 3 from your base."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_draw_or_discard_heal", discard_heal=3)
    return state


@card_ability("SOR", "119")
def _reinforcement_walker():
    """When Played/On Attack: Look at the top card of your deck. Either draw that
    card or discard it and heal 3 damage from your base."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_reinforcement_walker_peek)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_reinforcement_walker_peek)]),
    ]


# ── SOR_148 Guerilla Attack Pod (Unit) ────────────────────────────────────────
@card_ability("SOR", "148")
def _guerilla_attack_pod():
    """When Played: If a base has 15 or more damage on it, ready this unit.
    (Grit is the keyword layer.)"""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(kind="unit", fixed=SELF))],
        condition=ConditionCheck(Condition.ANY_BASE_DAMAGE_MIN, 15),
    )


# ── SOR_149 Mace Windu (Unit) ─────────────────────────────────────────────────
@card_ability("SOR", "149")
def _mace_windu():
    """When this unit attacks and defeats a unit: Ready him.  (Ambush is the
    keyword layer.)"""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[ReadyCard(TargetSpec(kind="unit", fixed=SELF))],
    )


# ── SOR_154 Rallying Cry (Event) ──────────────────────────────────────────────
@card_ability("SOR", "154")
def _rallying_cry():
    """Each friendly unit gains Raid 2 this phase."""
    return EventAbility(effects=[
        GrantKeyword("Raid", value=2, target=TargetSpec(
            controller="friendly", kind="unit", fixed=EACH_FRIENDLY),
            duration=Duration.THIS_PHASE),
    ])


# ── SOR_156 Benthic Two Tubes (Unit) ──────────────────────────────────────────
@card_ability("SOR", "156")
def _benthic_two_tubes():
    """On Attack: Another friendly [Aggression] unit gains Raid 2 for this
    phase."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword("Raid", value=2, target=TargetSpec(
            controller="friendly", kind="unit", aspects=("Aggression",),
            predicates=("not_self",)), duration=Duration.THIS_PHASE)],
        optional=True,
    )


# ── SOR_159 Partisan Insurgent (Unit) ─────────────────────────────────────────
@card_ability("SOR", "159")
def _partisan_insurgent():
    """While you control another [Aggression] unit, this unit gains Raid 2."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Raid", value=2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 "Aggression"),
    )


# ── SOR_161 Ardent Sympathizer (Unit) ─────────────────────────────────────────
@card_ability("SOR", "161")
def _ardent_sympathizer():
    """While you have the initiative, this unit gets +2/+0."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


# ── SOR_166 Infiltrator's Skill (Upgrade) ─────────────────────────────────────
@card_ability("SOR", "166")
def _infiltrators_skill():
    """Attached unit gains Saboteur.  An upgrade's ConstantAbility(SELF,
    KeywordGrant) is read by the keyword layer's attached-upgrade scan and
    confers the keyword to the host unit."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Saboteur")],
    )


# ── SOR_168 Precision Fire (Event) ────────────────────────────────────────────
def _precision_fire_attack(state, source_ci, target_id, event_ctx):
    """Attack with a unit; it gains Saboteur for this attack, and +2/+0 more if
    it's a TROOPER."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                        bonus_trait="Trooper", grant_keywords=["Saboteur"])
    return state


@card_ability("SOR", "168")
def _precision_fire():
    """Attack with a unit. It gains Saboteur for this attack. If it's a TROOPER,
    it also gets +2/+0 for this attack."""
    return EventAbility(effects=[CustomEffect(fn=_precision_fire_attack)])


# ── SOR_169 Keep Fighting (Event) ─────────────────────────────────────────────
@card_ability("SOR", "169")
def _keep_fighting():
    """Ready a unit with 3 or less power."""
    return EventAbility(effects=[
        ReadyCard(TargetSpec(controller="any", kind="unit", power_max=3)),
    ])


# ── SOR_178 Cartel Spacer (Unit) ──────────────────────────────────────────────
@card_ability("SOR", "178")
def _cartel_spacer():
    """When Played: If you control another [Cunning] unit, exhaust an enemy unit
    that costs 4 or less."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit",
                                        cost_max=4))],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 "Cunning"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set group 16 (combat tricks, buffs & tempo)
# ══════════════════════════════════════════════════════════════════════════════

# ── SOR_191 Vanguard Ace (Unit) ───────────────────────────────────────────────
def _vanguard_ace_tokens(state, source_ci, target_id, event_ctx):
    """Give this unit one Experience token per OTHER card its controller played
    this phase.  The per-phase play counter already includes this unit's own play
    (it increments at the CardPlayed chokepoint before WhenPlayed collection), so
    'other cards' = count − 1."""
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    others = state.game_memory.cards_played_this_phase.get(source_ci.owner_id, 0) - 1
    for _ in range(max(0, others)):
        attach_token(state, ps, source_ci, "Experience")
    return state


@card_ability("SOR", "191")
def _vanguard_ace():
    """When Played: For each other card you played this phase, give an Experience
    token to this unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_vanguard_ace_tokens)],
    )


# ── SOR_208 Outer Rim Headhunter (Unit) ───────────────────────────────────────
@card_ability("SOR", "208")
def _outer_rim_headhunter():
    """On Attack: If you control a leader unit, you may exhaust a non-leader unit.
    (Raid 1 is the keyword layer.)"""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("non_leader",)))],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
        optional=True,
    )


# ── SOR_211 Gamorrean Guards (Unit) ───────────────────────────────────────────
@card_ability("SOR", "211")
def _gamorrean_guards():
    """While you control another [Cunning] unit, this unit gains Sentinel.
    (Conditional self-grant read by has_keyword; the sanitiser strips the mistagged
    printed Sentinel — SOR_114 pattern.)"""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 "Cunning"),
    )


# ── SOR_214 Smuggling Compartment (Upgrade) ───────────────────────────────────
def _ready_one_resource(state, source_ci, target_id, event_ctx):
    """Ready one of the host controller's exhausted resources (readying a ready
    resource is a no-op, so pick an exhausted one)."""
    ps = state.player_by_id(source_ci.owner_id)
    for r in ps.resources:
        if r.exhausted:
            r.exhausted = False
            break
    return state


@card_ability("SOR", "214")
def _smuggling_compartment():
    """Attach to a VEHICLE unit.  Attached unit gains: "On Attack: Ready a
    resource."  A GrantedAbility wrapping an OnAttack that resolves from the host
    (the upgrade confers the trigger to its host — JTL VEHICLE-modification
    pattern)."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_ready_one_resource)],
    ))


# ── SOR_215 Snapshot Reflexes (Upgrade) ───────────────────────────────────────
def _snapshot_reflexes_attack(state, source_ci, target_id, event_ctx):
    """Optionally grant an attack pinned to this upgrade's host unit (reprint of
    SHD_223; the Hotshot DL-44 attacker_id=host pattern, optional)."""
    from swu.engine.actions import push_granted_attack
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        push_granted_attack(state, source_ci, attacker_id=host_id, optional=True)
    return state


@card_ability("SOR", "215")
def _snapshot_reflexes():
    """When Played: You may attack with attached unit.  (Reprint of SHD_223 — an
    upgrade's own WhenPlayed collected via UpgradePlayed; the host can only attack
    if ready, which falls out of the attack enumeration.)"""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_snapshot_reflexes_attack)],
    )


# ── SOR_221 Outmaneuver (Event) ───────────────────────────────────────────────
def _outmaneuver_choose_arena(state, source_ci, target_id, event_ctx):
    """Choose an arena (ground or space), then exhaust each unit in it — a two-mode
    modal (exhaust_ground/exhaust_space), each a fungible no-target mode that
    exhausts every unit in the arena (Bombing Run SOR_173's arena-choice pattern)."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, modes=["exhaust_ground", "exhaust_space"])
    return state


@card_ability("SOR", "221")
def _outmaneuver():
    """Choose an arena (ground or space). Exhaust each unit in that arena."""
    return EventAbility(effects=[CustomEffect(fn=_outmaneuver_choose_arena)])


# ── SOR_249 Frontier AT-RT (Unit) ─────────────────────────────────────────────
@card_ability("SOR", "249")
def _frontier_at_rt():
    """While you control another VEHICLE unit, this unit gains Ambush.
    (Conditional self-grant; CONTROLLER_HAS_OTHER_TRAIT_UNIT excludes self.)"""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Ambush")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Vehicle"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set group 17 (miscellaneous abilities)
# ══════════════════════════════════════════════════════════════════════════════

# ── SOR_34 Del Meeko (Unit) ───────────────────────────────────────────────────
@card_ability("SOR", "34")
def _del_meeko():
    """Each event an opponent plays costs 1 resource more.  (Restore 1 is the
    keyword layer.)  An OpponentPlayTax marker read at the play-cost seam."""
    return OpponentPlayTax(amount=1, card_type="event")


# ── SOR_54 Jedi Lightsaber (Upgrade) ──────────────────────────────────────────
@card_ability("SOR", "54")
def _jedi_lightsaber():
    """Attach to a non-VEHICLE unit.  If attached unit is a FORCE unit, it gains:
    "On Attack: Give the defender -2/-2 for this phase."  A GrantedAbility wrapping
    an OnAttack (resolves from the host) gated by SOURCE_HAS_TRAIT("Force") — the
    Corrupted Saber LOF_187 pattern.  ``fixed=DEFENDER`` applies to the current
    defender and fizzles on a base attack.  The printed +3/+3 is the upgrade's own
    stat line (applied by the compute layer)."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, "Force"),
        effects=[ModifyStats(power=-2, hp=-2, target=TargetSpec(fixed=DEFENDER),
                             duration=Duration.THIS_PHASE)],
    ))


# ── SOR_56 Bendu (Unit) ───────────────────────────────────────────────────────
@card_ability("SOR", "56")
def _bendu():
    """On Attack: The next non-[Heroism], non-[Villainy] card you play this phase
    costs 2 resources less.  (Sentinel is the keyword layer.)  A NextPlayDiscount
    with ``exclude_aspects`` and ``units_only=False`` (any card type)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[NextPlayDiscount(trait="", amount=2, units_only=False,
                                  exclude_aspects=("Heroism", "Villainy"))],
    )


# ── SOR_61 Guardian of the Whills (Unit) ──────────────────────────────────────
@card_ability("SOR", "61")
def _guardian_of_the_whills():
    """The first upgrade you play on this unit each round costs 1 resource less.
    A host-scoped StandingPlayDiscount (``applies_to="upgrade_on_source"``,
    once_per_round): the play-cost seam matches only an Upgrade being played onto
    this very unit and spends the discount after the first such play each round."""
    return StandingPlayDiscount(amount=1, applies_to="upgrade_on_source",
                                once_per_round=True)


# ── SOR_62 Regional Governor (Unit) ───────────────────────────────────────────
def _regional_governor_name(state, source_ci, target_id, event_ctx):
    """Name a card (recorded on this unit's ``named_card`` field)."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci)
    return state


@card_ability("SOR", "62")
def _regional_governor():
    """When Played: Name a card.  While this unit is in play, opponents can't play
    the named card.  The WhenPlayed pushes the name_a_card decision; the
    ForbidNamedCardPlay marker makes the play-legality seam bar the named card while
    this unit is in play (distinct from Galen Erso's ability-suppression naming)."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_regional_governor_name)]),
        ForbidNamedCardPlay(),
    ]


# ── SOR_71 Electrostaff (Upgrade) ─────────────────────────────────────────────
@card_ability("SOR", "71")
def _electrostaff():
    """Attach to a non-VEHICLE unit.  While attached unit is defending, the
    attacker gets -1/-0.  A while_defending ConstantAbility on the upgrade whose
    target is the enemy attacker (Lando Calrissian LAW_108's ability, conferred by
    an upgrade); compute_power scans the defender's attached upgrades for it."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),
        effects=[StatBonus(power=-1, hp=0)],
        while_defending=True,
    )


# ── SOR_72 Entrenched (Upgrade) ───────────────────────────────────────────────
@card_ability("SOR", "72")
def _entrenched():
    """Attached unit can't attack bases.  A CannotAttackBases marker on the upgrade,
    read at attack enumeration (the base-attack option is dropped for the host)."""
    return CannotAttackBases()


# ── sor-set:18 — Miscellaneous abilities ──────────────────────────────────────

@card_ability("SOR", "93")
def _alliance_dispatcher():
    """SOR_93 — Alliance Dispatcher (Unit, Rebel, 1/2): "Action [exhaust]: Play a
    unit from your hand.  It costs 1 resource less."

    The Admiral Ozzel SOR_129 activated-play pattern: an ``ExhaustSelf`` action whose
    CustomEffect is a thin adapter onto the play-from-hand subsystem with
    ``cost_reduction=1`` (any unit — no trait filter).  Gated by
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND (any trait) so the exhaust is never wasted when
    no unit is affordable (conservative: the gate checks the full cost, so a unit
    affordable only via the 1-discount is a rare, safe under-offer)."""
    def _dispatch(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_from_hand
        push_play_from_hand(state, source_ci, cost_reduction=1)
        return state

    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_dispatch)],
        title="Play a unit from hand (it costs 1 less)",
        condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND, None),
    )


@card_ability("SOR", "104")
def _u_wing_reinforcement():
    """SOR_104 — U-Wing Reinforcement (Event, Supply, 7): "Search the top 10 cards of
    your deck for up to 3 units with combined cost 7 or less and play each of them
    for free.  (Put the other cards on the bottom of your deck in a random order.)"

    The Darth Vader SOR_87 multi-select budgeted free-play primitive
    (``push_search_and_play_multiple``) with the new ``max_units=3`` cap (the per-pick
    auto-finish enforces it) and no trait/aspect filter — any Unit in the window with
    combined printed cost ≤ 7 is eligible."""
    def _reinforce(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_search_and_play_multiple
        from swu.cards.models import Unit
        push_search_and_play_multiple(
            state, source_ci, window=10, budget=7, max_units=3,
            eligible=lambda cd: isinstance(cd, Unit))
        return state

    return EventAbility(effects=[CustomEffect(fn=_reinforce)])


def _strike_true_record(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly unit's effective power so the follow-up step can
    deal "its power" to an enemy unit (the Haymaker LAW_168 two-step pattern, minus
    the Experience token and the same-arena restriction)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    from swu.engine.actions import compute_power
    event_ctx["strike_amount"] = compute_power(state, unit)
    event_ctx["strike_source_name"] = unit.card_def.display_name
    return state


def _strike_true_damage(state, source_ci, target_id, event_ctx):
    """Deal the recorded amount to the chosen enemy unit."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("strike_amount", 0) or 0)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = event_ctx.get("strike_source_name") or source_ci.card_def.display_name
    return _apply_deal_damage(state, target_id, amount, name)


@card_ability("SOR", "127")
def _strike_true():
    """SOR_127 — Strike True (Event, Tactic, 3): "A friendly unit deals damage equal
    to its power to an enemy unit."

    Two sequential, dependent CustomEffect.target steps sharing the resolve_effects
    ``event_ctx`` (the Haymaker LAW_168 pattern): the first picks the friendly unit
    and records its effective power; the second deals that recorded power to a chosen
    enemy unit (no arena restriction).  Each is mandatory-if-able."""
    return EventAbility(effects=[
        CustomEffect(fn=_strike_true_record,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_strike_true_damage,
                     target=TargetSpec(controller="enemy", kind="unit")),
    ])


@card_ability("SOR", "140")
def _specforce_soldier():
    """SOR_140 — SpecForce Soldier (Unit, Rebel/Trooper, 2/2): "When Played: A unit
    loses Sentinel for this phase."

    A WhenPlayed ``RevokeKeyword("Sentinel", THIS_PHASE)`` on a chosen unit (any
    unit — typically an enemy Sentinel, to open an attack lane).  ``keyword_revoke``
    already exists and is honoured by ``has_keyword``; mandatory-if-able (there is
    always at least this unit itself to target)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[RevokeKeyword(keyword="Sentinel",
                               target=TargetSpec(controller="any", kind="unit"),
                               duration=Duration.THIS_PHASE)],
    )


def _karabast_record(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly unit's current damage + 1 (the Haymaker two-step,
    with a damage-driven magnitude instead of power)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    event_ctx["strike_amount"] = int(unit.damage) + 1
    event_ctx["strike_source_name"] = unit.card_def.display_name
    return state


@card_ability("SOR", "151")
def _karabast():
    """SOR_151 — Karabast (Event, Spectre, 2): "A friendly unit deals damage to an
    enemy unit equal to the amount of damage on the friendly unit plus 1."

    The Strike True SOR_127 two-step, but the recorded magnitude is the friendly
    unit's current damage + 1 (reusing ``_strike_true_damage`` for the delivery)."""
    return EventAbility(effects=[
        CustomEffect(fn=_karabast_record,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_strike_true_damage,
                     target=TargetSpec(controller="enemy", kind="unit")),
    ])


def _wolffe_no_heal(state, source_ci, target_id, event_ctx):
    """Set the global "bases can't be healed for this phase" lock (Wolffe SOR_160)."""
    state.game_memory.bases_cannot_heal_this_phase = True
    return state


@card_ability("SOR", "160")
def _wolffe():
    """SOR_160 — Wolffe (Unit, Clone/Fringe, 3/2, Saboteur): "When Played / On Attack:
    Bases can't be healed for this phase."

    Saboteur is the keyword layer.  The "When Played / On Attack" clause fires on
    EITHER event — modelled as two triggers, each setting the phase-scoped
    ``bases_cannot_heal_this_phase`` lock (idempotent; a global boolean read at every
    base-heal chokepoint).  No target."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_wolffe_no_heal)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_wolffe_no_heal)]),
    ]


# ── sor-set:19 — Miscellaneous abilities ──────────────────────────────────────

@card_ability("SOR", "216")
def _disarm():
    """SOR_216 — Disarm (Event, Tactic, cost 1): "Give an enemy unit -4/-0 for this
    phase."

    Pure reuse: an ``EventAbility`` whose single ``ModifyStats`` targets an enemy
    unit (drives a ChooseTarget) and applies a THIS_PHASE debuff — the event twin of
    Jedha City SOR_28's Epic Action, retargeted from any non-leader to an enemy."""
    return EventAbility(effects=[ModifyStats(
        power=-4, hp=0,
        target=TargetSpec(controller="enemy", kind="unit"),
        duration=Duration.THIS_PHASE)])


@card_ability("SOR", "190")
def _lothal_insurgent():
    """SOR_190 — Lothal Insurgent (Unit, Rebel, 3/2): "When Played: If you played
    another card this phase, each opponent draws a card then discards a random card
    from their hand."

    Pure reuse: a ``WhenPlayed`` trigger gated by the new
    ``CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE`` condition (controller's per-phase play
    counter ≥2 — the source's own play is already counted before trigger collection).
    Effects run in order: ``DrawCards(1, player="opponent")`` then
    ``DiscardFromHand(1, chooser="opponent")`` — the latter uses the established
    first-card = "random discard" simplification.  2-player: "each opponent" is the
    one opponent."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(1, player="opponent"),
                 DiscardFromHand(1, chooser="opponent")],
        condition=ConditionCheck(
            Condition.CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE, None),
    )


def _lando_return_resources(state, source_ci, target_id, event_ctx):
    """Return up to 2 of the controller's resources to their hand (Lando SOR_197).

    Resources are fungible face-down cards, so — following the K-2SO SOR_145
    auto-select precedent — we return the maximum (min(2, available)) rather than
    prompting a choice; a plain face-down resource is preferred.  Each returned card
    goes face-up to the owner's hand and is no longer a resource."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    for _ in range(min(2, len(ps.resources))):
        res = next((r for r in ps.resources if r.face_down), ps.resources[0])
        ps.resources.remove(res)
        res.zone = Zone.HAND
        res.face_down = False
        res.exhausted = False
        ps.hand.append(res)
    return state


@card_ability("SOR", "197")
def _lando_calrissian():
    """SOR_197 — Lando Calrissian (Unit, Fringe/Official, 6/5, Saboteur): "When
    Played: Return up to 2 friendly resources to their owners' hands."

    Saboteur is the keyword layer.  The When Played clause is a self-contained
    CustomEffect that auto-returns up to 2 of the controller's own resources to hand
    (the fungible-resource auto-select simplification — resources are always the
    controller's own, so "their owners' hands" = the controller's hand)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_lando_return_resources)],
    )


def _smoke_and_cinders(state, source_ci, target_id, event_ctx):
    """Each player discards down to 2 cards of their choice (Smoke and Cinders
    SOR_174).  Delegates to the symmetric ``discard_excess_from_hand`` decision."""
    from swu.engine.actions import push_discard_excess_from_hand
    push_discard_excess_from_hand(state, source_ci, keep=2)
    return state


@card_ability("SOR", "174")
def _smoke_and_cinders_event():
    """SOR_174 — Smoke and Cinders (Event, Disaster, cost 5): "Each player discards
    all but 2 cards (of their choice) from their hand."

    A CustomEffect that pushes the self-contained symmetric ``discard_excess_from_hand``
    decision (the each_player_defeats order/idx walk): the controller discards down to
    2 first, then the opponent.  Fizzles cleanly if neither player holds >2 cards."""
    return EventAbility(effects=[CustomEffect(fn=_smoke_and_cinders)])


def _chimaera_name_discard(state, source_ci, target_id, event_ctx):
    """Name a card; an opponent reveals their hand and discards a copy (Chimaera
    SOR_185 On Attack).  Delegates to the ``name_and_discard`` decision."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci)
    return state


@card_ability("SOR", "185")
def _chimaera():
    """SOR_185 — Chimaera (Unit, Capital Ship/Imperial/Vehicle, 8/7, Shielded): "On
    Attack: Name a card.  An opponent reveals their hand and discards a card with that
    name from it."

    Shielded is the keyword layer.  The On Attack clause is a CustomEffect that pushes
    the self-contained ``name_and_discard`` decision — the controller names a card in
    the opponent's revealed hand and one copy is discarded (the optimal-play collapse
    of "name blind then reveal", since the reveal is part of the effect)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_chimaera_name_discard)],
    )


@card_ability("SOR", "177")
def _bib_fortuna():
    """SOR_177 — Bib Fortuna — Jabba's Majordomo (Unit, Underworld/Twi'lek, 1/3,
    Shielded): "Action [Exhaust]: Play an event from your hand.  It costs 1 resource
    less."

    Shielded is the keyword layer.  The action uses the new play-EVENT-from-hand
    subsystem (actions.push_play_event_from_hand — the event sibling of Admiral
    Ozzel SOR_129's units-only push_play_from_hand, since events resolve via a wholly
    different path).  Gated by CONTROLLER_CAN_PLAY_EVENT_FROM_HAND(param=1) so the
    exhaust is never wasted when no event is affordable at the −1 discount (the
    Ozzel pattern — don't offer an action that could do nothing)."""
    def _bib(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_play_event_from_hand
        push_play_event_from_hand(state, source_ci, cost_reduction=1)
        return state

    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_bib)],
        title="Play an event from hand (costs 1 less)",
        condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_EVENT_FROM_HAND, 1),
    )


@card_ability("SOR", "212")
def _strafing_gunship():
    """SOR_212 — Strafing Gunship (Unit, Underworld/Vehicle/Fighter, Space, 3/4):
    "This unit can attack units in the ground arena.  While this unit is attacking a
    ground unit, the defender gets −2/−0."

    Two constant markers — no trigger, no decision:
      * ``CrossArenaAttack`` widens the attack-enumeration eligible-defender set to
        the opposite (ground) enemy arena and relaxes the AttackWithUnit cross-arena
        guard.
      * A ``while_attacking`` ConstantAbility (the attacker-scoped mirror of Jyn
        Erso SOR_18's ``while_target_defending``): while THIS unit is the current
        attacker, an enemy ground unit it is attacking gets −2/−0.  compute_power
        threads the attacker id so the debuff lands only on the unit this gunship is
        actually attacking, and only mid-combat."""
    return [
        CrossArenaAttack(),
        ConstantAbility(
            target=TargetSpec(controller="enemy", kind="unit", arena="ground"),
            effects=[StatBonus(power=-2, hp=0)],
            while_attacking=True,
        ),
    ]


# ── sor-set:20 — control-change at regroup + conditional cost reduction ────────

def _change_of_heart_fn(state, source_ci, target_id, event_ctx):
    """Take control of the chosen enemy non-leader unit and flag it to revert to its
    owner's control at the start of the next regroup phase (Change of Heart SOR_224).

    Pure composition of two existing seams — no new decision kind, no core-resolution
    change: ``actions.change_control`` relocates the instance into the caster's
    matching arena (control is implicit arena occupancy, per Stolen Landspeeder
    SHD_161), and the new one-shot ``return_control_to_owner_at_regroup`` flag (swept
    in ``actions._enter_regroup``, mirroring Commandeer JTL_235's
    ``return_to_owner_hand_at_regroup``) reverts control at regroup — here via
    ``change_control`` back to the owner rather than to hand."""
    from swu.engine.actions import change_control
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, target_ci = res
    change_control(state, target_ci, source_ci.owner_id)      # "Take control"
    target_ci.return_control_to_owner_at_regroup = True        # delayed revert
    return state


@card_ability("SOR", "224")
def _change_of_heart():
    """SOR_224 — Change of Heart (Event, Gambit, cost 6): "Take control of a
    non-leader unit.  At the start of the regroup phase, its owner takes control of
    it."

    A single targeted ``CustomEffect`` composing the control-change seam
    (actions.change_control) with the new ``return_control_to_owner_at_regroup``
    delayed-revert flag (mirrors Commandeer JTL_235, but reverts CONTROL rather than
    bouncing to hand).  Faithful-intent simplification ``controller="enemy"``: the
    printed "a non-leader unit" technically includes a unit you already control, but
    taking a unit you control changes nothing (change_control no-ops) and the delayed
    revert is likewise inert, so a friendly target is never a meaningful play —
    restricting to enemy offers only the meaningful targets, matching Commandeer."""
    return EventAbility(effects=[CustomEffect(
        fn=_change_of_heart_fn,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader",)),
    )])


@card_ability("SOR", "248")
def _volunteer_soldier():
    """SOR_248 — Volunteer Soldier (Unit, Trooper, 2/3, Raid 1): "If you control a
    TROOPER unit, this unit costs 1 resource less to play."

    Raid 1 is handled by the keyword layer.  The cost text is the exact Force Choke
    SOR_139 template — a ``CostReduction`` gated by ``CONTROLLER_HAS_TRAIT_UNIT``,
    read by the play-cost path before the card is played (it never counts itself, as
    it is still in hand at play time)."""
    return CostReduction(
        amount=1,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, "Trooper"),
    )


# ── sor-set:18 — control-linking upgrade (Traitorous SOR_122) ──────────────────
# The former escalation of the "miscellaneous abilities" group. Two clauses:
#   1. "When this upgrade becomes attached to a non-leader unit that costs 3 or
#      less: Take control of that unit."  → an ordinary WhenPlayed on the upgrade
#      (UpgradePlayed carries the host in event_ctx["attached_to_id"]); the effect
#      relocates the host into the player's arena (actions.change_control — control
#      is implicit arena occupancy, per Stolen Landspeeder SHD_161) and LINKS the
#      host to this upgrade (control_linked_to).
#   2. "When this upgrade becomes unattached from a unit: That unit's owner takes
#      control of it."  → no ability needed: it reuses the Maul LAW_54 seam
#      (_revert_linked_control), which now also fires from the two upgrade-removal
#      chokepoints in the resolver (_apply_defeat_unit / _apply_return_to_hand). So
#      when Traitorous is defeated or bounced (or its host leaves play, which routes
#      the host to its owner anyway), the host reverts to its owner's control.

def _traitorous_take_control(state, source_ci, target_id, event_ctx):
    """When Traitorous attaches to a non-leader unit costing 3 or less, its
    controller takes control of the host, linked to this upgrade so the owner
    reclaims it when the upgrade leaves play."""
    from swu.engine.actions import change_control
    from swu.cards.models import Leader
    host_id = event_ctx.get("attached_to_id") or target_id
    if host_id is None:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    _, host_ci = res
    if isinstance(host_ci.card_def, Leader):
        return state
    if (getattr(host_ci.card_def, "cost", None) or 0) > 3:
        return state
    change_control(state, host_ci, source_ci.owner_id)  # "Take control of that unit"
    host_ci.control_linked_to = source_ci.instance_id   # revert on unattach
    return state


@card_ability("SOR", "122")
def _traitorous():
    """SOR_122 — Traitorous (Upgrade, Innate, cost 5): take control of the ≤3-cost
    non-leader unit it attaches to; the owner reclaims it when it unattaches."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_traitorous_take_control)],
    )
