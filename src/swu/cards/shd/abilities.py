"""SHD (Shadows of the Galaxy) card ability registrations.

Cards with no text or only Phase-2 keywords are handled by the keyword engine
and are not registered here.  Cards blocked by a deferred keyword (Smuggle,
Bounty) are left for the keyword-group sessions.

Encoded so far (Phase 7 dry run — group ``shd-han-solo:03`` "Direct damage &
removal"): the four cards whose abilities compose cleanly from existing
primitives.  Han Solo (SHD_13, group ``shd-han-solo:05``) extends the
play-from-hand subsystem with a discount + follow-up self-damage seam (see the
registration below and ``actions.push_play_from_hand``).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, EventAbility, ConstantAbility, ActivatedAbility, GrantedAbility,
    PlayFromDiscardAction,
    AuraGrantedAbility,
    WhenPlayed, WhenPlayedViaSmuggle, WhenDefeated, WhenDeployed, OnAttack, WhenYouPlayCard,
    PhaseStartTrigger,
    WhenOpponentPlaysCard, OnAttackDefeatsUnit, WhenBountyCollected, WhenAttacked,
    WhenEnemyAttacksYourBase,
    WhenPlayerDiscardsFromHand, WhenUnitDefeated,
    WhenDealsCombatDamageToBase, WhenDealtCombatDamage,
    WhenFriendlyUnitDealtCombatDamage, AmbushDefenderDebuff, DamagePrevention,
    DealDamage, DealDamageEqualTo, DefeatUnit, Heal, DrawCards, DiscardFromHand,
    ReturnToHand, CustomEffect, ExhaustCard, CaptureUnit,
    GiveToken, GrantSmuggleToResources, KeywordGrant, StatBonus, ExhaustSelf, PayResources, DefeatSelf, ModifyStats,
    TraitGrant, CostReduction, ReadyRestriction, ReadyCard, KeywordIfPlayedFromHand,
    SuppressHostAbilities, Protection, NamedCardPlayTax,
    TargetSpec, ConditionCheck, Condition, Duration,
    EACH_IN_PLAY, EACH_FRIENDLY, EACH_ENEMY, SELF, DEFENDER,
)


@card_ability("SHD", "164")
def _rhokai_gunship():
    """When Defeated: Deal 1 damage to a unit or base."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit_or_base"))],
    )


@card_ability("SHD", "166")
def _disabling_fang_fighter():
    """When Played: You may defeat an upgrade."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade"))],
        optional=True,
    )


@card_ability("SHD", "147")
def _ketsu_onyo():
    """Ketsu Onyo (SHD_147).

    Saboteur is handled by the keyword engine.  Residual: "When this unit deals
    combat damage to a base: You may defeat an upgrade that costs 2 or less."
    Modelled with the new WhenDealsCombatDamageToBase trigger (fired at the
    base-combat damage step, flagged in event_ctx like OnAttackDefeatsUnit); the
    optional effect defeats any real (non-token) upgrade costing ≤ 2 attached to
    a unit of either player (kind="upgrade", cost_max=2)."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade", cost_max=2))],
        optional=True,
    )


@card_ability("SHD", "178")
def _daring_raid():
    """Daring Raid — Deal 2 damage to a unit or base."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="any", kind="unit_or_base")),
    ])


# ── Smuggle group (shd-han-solo:01) residual abilities ────────────────────────
# The Smuggle keyword itself is implemented engine-side (play a card from the
# resource zone, replace from deck).  These registrations cover the residual
# rules text that the keyword does not.

@card_ability("SHD", "148")
def _cassian_andor():
    """SHD_148 — When played using Smuggle: Ready this unit.

    Smuggle's only residual: the unit readies itself, but only when it was
    played from the resource zone (WhenPlayedViaSmuggle), so a normal hand play
    leaves it exhausted as usual."""
    return TriggerAbility(
        trigger=WhenPlayedViaSmuggle(),
        effects=[ReadyCard(TargetSpec(kind="unit", fixed=SELF))],
    )


@card_ability("SHD", "160")
def _reckless_gunslinger():
    """SHD_160 — When Played: Deal 1 damage to each base.

    Fires on every play (hand or Smuggle).  EACH_IN_PLAY auto-targets both
    bases, so the effect resolves inline with no player choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(kind="base", fixed=EACH_IN_PLAY))],
    )


@card_ability("SHD", "252")
def _smugglers_aid():
    """SHD_252 — Smuggler's Aid (Event): Heal 3 damage from your base."""
    return EventAbility(effects=[
        Heal(3, TargetSpec(controller="friendly", kind="base", fixed=EACH_FRIENDLY)),
    ])


@card_ability("SHD", "248")
def _tech():
    """SHD_248 — Each friendly resource gains Smuggle. The gained Smuggle cost is
    that card's cost plus 2 resources and its aspect icons.

    A passive constant marker (GrantSmuggleToResources) read only by the
    smuggle-enumeration seam in legal_actions — it makes every one of the
    controller's resources smuggleable at (printed cost + 2) with its own
    aspects, while Tech is in play.  Tech's own printed Smuggle keyword is
    handled by the engine keyword layer."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly"),
        effects=[GrantSmuggleToResources()],
    )


# SHD_174 Hotshot DL-44 Blaster — Smuggle-group residual unblocked by the
# granted-attack-restricted-attacker primitive (group shd-han-solo:09).  The
# upgrade's "When played using Smuggle: Attack with attached unit" is a granted
# attack pinned to the upgrade's host: the WhenPlayedViaSmuggle trigger's
# CustomEffect reads the host id from event_ctx["attached_to_id"] (threaded by
# _attach_upgrade) and calls push_granted_attack(attacker_id=host).  No stat
# bonus.  (resolver._collect_triggers was widened to collect an upgrade's
# WhenPlayedViaSmuggle trigger, not just WhenPlayed.)

def _hotshot_attack_with_host(state, source_ci, target_id, event_ctx):
    """Adapter: grant an attack pinned to this upgrade's attached host unit."""
    from swu.engine.actions import push_granted_attack
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        push_granted_attack(state, source_ci, attacker_id=host_id)
    return state


@card_ability("SHD", "174")
def _hotshot_dl44_blaster():
    """SHD_174 — Hotshot DL-44 Blaster (Upgrade): attach to a non-Vehicle unit;
    Smuggle [3, Cunning].  When played using Smuggle: Attack with attached unit.

    The attach restriction and the Smuggle cost are handled by the engine
    (upgrade target spec + keyword layer).  The only residual is the granted
    attack, pinned to the host unit via push_granted_attack(attacker_id=...).
    Fires only on a Smuggle play (WhenPlayedViaSmuggle), not a normal hand play."""
    return TriggerAbility(
        trigger=WhenPlayedViaSmuggle(),
        effects=[CustomEffect(fn=_hotshot_attack_with_host)],
    )


# SHD_175 Armed to the Teeth — the last Smuggle-group residual, unblocked by the
# upgrade-grants-host-a-triggered-ability primitive (GrantedAbility).  The upgrade
# confers an On Attack trigger on its host unit: the granted ability is collected
# by resolver._collect_triggers (which scans each in-play unit's attached
# upgrades), fires when the HOST attacks, and resolves from the host's
# perspective — so "another friendly unit" (controller="friendly", not_self)
# means a friendly unit other than the attacker.  The +2/+0 lasts the phase.

@card_ability("SHD", "175")
def _armed_to_the_teeth():
    """SHD_175 — Armed to the Teeth (Upgrade): attach to a unit; Smuggle
    [4, Aggression].  Attached unit gains: "On Attack: Give another friendly unit
    +2/+0 for this phase."

    The attach and the Smuggle cost are handled by the engine; the residual is
    the granted triggered ability, expressed via GrantedAbility wrapping a normal
    OnAttack TriggerAbility that resolves from the host unit."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(
                power=2, hp=0,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("not_self",)),
                duration=Duration.THIS_PHASE,
            )],
        ),
    )


# ── Bounty group (shd-han-solo:02) ────────────────────────────────────────────
# Bounty modelling convention: a "Bounty — <effect>" ability is the reminder-
# text "When this unit is defeated or captured, your opponent collects its
# bounty" — i.e. a WhenDefeated trigger whose effect resolves for the OPPONENT
# of the unit's controller.  We express "your opponent collects" by writing the
# effect from the ENEMY perspective (relative to the dying unit's owner), so no
# change to the trigger/decision machinery is needed.  (Capture is not modelled
# in the engine, so WhenDefeated is the only realisable bounty path today.)

@card_ability("SHD", "165")
def _unlicensed_headhunter():
    """SHD_165 — Saboteur (keyword engine).  While this unit is exhausted, it
    gains: "Bounty — Heal 5 damage from your base."

    The Bounty fires when the unit is defeated; "your base" belongs to the
    opponent who collects the bounty, i.e. the ENEMY base from the dying unit's
    owner perspective (EACH_ENEMY → resolves inline, no prompt).  The
    "while exhausted" clause gates the trigger via SOURCE_EXHAUSTED, evaluated
    against the unit's state at the moment of defeat — so a unit defeated while
    ready collects no bounty."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        condition=ConditionCheck(Condition.SOURCE_EXHAUSTED),
        effects=[Heal(5, TargetSpec(controller="enemy", kind="base",
                                    fixed=EACH_ENEMY))],
        is_bounty=True,
    )


# ── Bounty keyword group (han-solo:01) ────────────────────────────────────────
# Two plain-unit "Bounty — Draw a card" cards.  Same convention as above: the
# Bounty is a WhenDefeated trigger resolving for the COLLECTOR (the opponent of
# the dying unit's controller).  "Draw a card" from the collector's perspective
# is DrawCards(player="opponent") — the resolver draws for the opponent of the
# source (dying) unit's owner, which equals the collector for a unit whose
# control never changed (both cards).  Clone Deserter's Restore 1 is the keyword
# layer and needs no registration.

@card_ability("SHD", "95")
def _clone_deserter():
    """SHD_95 — Clone Deserter (Restore 1 keyword + Bounty).
    Bounty — Draw a card (the opponent who collects the bounty draws)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(count=1, player="opponent")],
        is_bounty=True,
    )


@card_ability("SHD", "195")
def _cartel_turncoat():
    """SHD_195 — Cartel Turncoat.
    Bounty — Draw a card (the opponent who collects the bounty draws)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(count=1, player="opponent")],
        is_bounty=True,
    )


# ── New primitive: control-change (shd-han-solo:02, Stolen Landspeeder SHD_161) ─
# The escalation card of the Bounty group.  Two pieces:
#
#   When Played: If you played this unit from your hand, an opponent takes
#   control of it.
#       → the control-change primitive.  Control in this engine is implicit (a
#         unit is controlled by whichever player's arena list holds it; owner is
#         ci.owner_id), so "an opponent takes control" is relocating the unit to
#         the opponent's arena with owner_id unchanged — actions.change_control.
#         Gated on play_source == "hand" (threaded through _put_unit_in_play), so
#         neither a Smuggle play nor the Bounty replay-from-discard re-triggers it.
#
#   Bounty — If you own this unit, play it from your discard pile for free and
#   give an Experience token to it.
#       → the standard Bounty WhenDefeated trigger (resolves for the collector =
#         opponent of the controller at death).  The collector "owns this unit"
#         exactly when the unit died under enemy control — i.e. the Stolen
#         Landspeeder loop: you play it, the opponent takes control, it dies, and
#         you (owner = collector) replay it under YOUR control with +1/+1.  When
#         it instead dies under its owner's control (e.g. after a previous
#         bounty replay), the collector does not own it and the effect no-ops.
#
# Both are non-optional CustomEffects with no player-chosen target, so they
# resolve INLINE during _put_unit_in_play / _defeat_unit — no new decision kind,
# no change to the trigger/decision machinery.

def _stolen_landspeeder_steal(state, source_ci, target_id, event_ctx):
    """When Played (hand only): the opponent of the controller takes control."""
    from swu.engine.actions import change_control
    if event_ctx.get("play_source", "hand") != "hand":
        return state  # a Smuggle play / discard replay does not hand it over
    opponent_id = state.players[
        1 - state.player_index(source_ci.owner_id)
    ].player_id
    change_control(state, source_ci, opponent_id)
    return state


def _stolen_landspeeder_bounty(state, source_ci, target_id, event_ctx):
    """Bounty: if the collector owns this unit, replay it from the owner's
    discard for free, under the owner's control, with an Experience token.

    Fires inline during _defeat_unit while the unit is in limbo (already out of
    its arena, not yet in discard); ``source_ci`` IS the defeated instance.  The
    collector is the opponent of the controller at the moment of defeat; the
    effect only does anything when that collector also OWNS the unit."""
    from swu.engine.actions import _put_unit_in_play
    from swu.engine import tokens

    controller_at_death = event_ctx.get("defeated_controller_id")
    if controller_at_death is None:
        return state
    collector_id = state.players[
        1 - state.player_index(controller_at_death)
    ].player_id
    if collector_id != source_ci.owner_id:
        return state  # "If you own this unit" — the collector must be the owner

    ci = source_ci
    collector_ps = state.player_by_id(collector_id)
    # A replay is a fresh in-play object: clear stale damage/exhaust and any
    # modifiers that targeted the old instance (it reuses the same instance_id).
    ci.damage = 0
    ci.exhausted = False
    state.modifiers = [
        m for m in state.modifiers if m.target_instance_id != ci.instance_id
    ]
    # Play from discard "for free", under the OWNER's control.  play_source
    # "discard" keeps the When Played control-change from firing again.
    _put_unit_in_play(state, collector_ps, ci, play_source="discard")
    tokens.attach_token(state, collector_ps, ci, "Experience")
    # Tell _defeat_unit the card is back in play — skip discard placement.
    event_ctx["relocated_by_trigger"] = True
    return state


@card_ability("SHD", "161")
def _stolen_landspeeder():
    """SHD_161 — When Played (from hand): an opponent takes control of it.
    Bounty — If you own this unit, play it from your discard pile for free and
    give it an Experience token."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_stolen_landspeeder_steal)],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_stolen_landspeeder_bounty)],
            is_bounty=True,
        ),
    ]


@card_ability("SHD", "254")
def _bounty_guild_initiate():
    """When Played: If you control another Bounty Hunter unit, you may deal 2
    damage to a ground unit.

    The "another Bounty Hunter" check excludes this unit itself
    (CONTROLLER_HAS_OTHER_TRAIT_UNIT); the whole trigger is gated by it, so it is
    not even offered when the condition fails.  The "you may" is the optional
    target decline."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit", arena="ground"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Bounty Hunter"),
    )


# ── New primitive: play-from-hand-act-on-result (shd-han-solo:05) ─────────────
# Han Solo's action plays a unit from hand at a discount and then deals damage to
# *that specific unit*.  The "act on the played unit" handle is the new bit: the
# play-from-hand subsystem (push_play_from_hand) now carries an optional
# cost_reduction (applied to affordability + payment) and then_damage (dealt to
# the played unit after enter-play keywords but before its When Played abilities,
# per Han's errata).  Both leader sides reuse the one CustomEffect seam — the
# only escape-hatch here, mirroring Admiral Ozzel SOR_129's push_play_from_hand
# call (a thin adapter, not irreducible card logic).  The Epic Action deploy is
# the standard leader-deploy machinery (deploy_threshold) and needs no ability.

def _han_play_discounted_unit(state, source_ci, target_id, event_ctx):
    """Adapter: push a play_from_hand decision that discounts the unit by 1 and
    deals 2 damage to it once it enters play."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=1, then_damage=2)
    return state


@card_ability("SHD", "13")
def _han_solo():
    """Han Solo (SHD_13) — Underworld leader, 5 cost, 3/6.

    Action [Exhaust] (undeployed) / Action (deployed leader unit):
        Play a unit from your hand. It costs 1 resource less. Deal 2 damage to it.

    Both sides resolve through the same play-from-hand adapter.  The ability is
    gated by CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT(1) so it is only offered when at
    least one hand unit is affordable at the −1 discount — matching the errata
    that the action cannot be used if it would not change the game state (and
    keeping the costless deployed side from being a legal no-op).  The 2 damage
    is dealt to the played unit before its own When Played abilities resolve.
    """
    gate = ConditionCheck(Condition.CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT, 1)
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_han_play_discounted_unit)],
            title="Play a unit from hand (−1 cost, deal 2 to it)",
            undeployed_only=True,
            condition=gate,
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_han_play_discounted_unit)],
            title="Play a unit from hand (−1 cost, deal 2 to it)",
            deployed_only=True,
            condition=gate,
        ),
    ]


# ── Card advantage & disruption (shd-han-solo:03) ─────────────────────────────

# ── Combat tricks, buffs & tempo (shd-han-solo:04) ────────────────────────────
# Two conditional self keyword-grants.  A ConstantAbility(target=SELF,
# effects=[KeywordGrant(...)], condition=...) is read passively by the keyword
# layer (has_keyword / keyword_value), which already honours spec.condition — so
# the keyword winks on/off as the board condition changes, with no action and no
# new trigger/decision machinery.

@card_ability("SHD", "168")
def _hunting_nexu():
    """SHD_168 — While you control another Aggression unit, this unit gains
    Raid 2.

    A self-targeted constant KeywordGrant gated by
    CONTROLLER_HAS_OTHER_ASPECT_UNIT("Aggression") (excludes the Nexu itself).
    keyword_value sums the granted Raid 2, so compute_power adds +2 while
    attacking exactly while the condition holds."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Raid", value=2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 "Aggression"),
    )


@card_ability("SHD", "247")
def _protector_of_the_throne():
    """SHD_247 — While this unit is upgraded, it gains Sentinel.

    A self-targeted constant KeywordGrant gated by SOURCE_UPGRADED (the unit has
    ≥1 attached upgrade).  Per the CR, Shield/Experience tokens are upgrades and
    likewise count, so any attached_upgrade switches Sentinel on; has_keyword
    reports it for the duration."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


# ── New primitive: repeated-modal-per-X (shd-han-solo:06) ─────────────────────
# Poe Dameron's On Attack discards up to 3 cards and grants one *distinct* option
# per discard, each chosen by the controller.  The new self-contained
# 'repeated_modal' decision kind (actions.push_repeated_modal) drives the
# discard → per-card option → per-option target flow; choices are recorded and
# applied together after the decision pops (so a defeat trigger lands cleanly,
# the push_distribute_damage gotcha).  The trigger is a plain OnAttack whose one
# CustomEffect is a thin adapter onto the push helper (the Palpatine SOR_135
# pattern), not irreducible card logic.

def _poe_dameron_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push the repeated-modal discard/option decision."""
    from swu.engine.actions import push_repeated_modal
    push_repeated_modal(state, source_ci)
    return state


@card_ability("SHD", "153")
def _poe_dameron():
    """SHD_153 — On Attack: Discard up to 3 cards from your hand. For each card
    discarded this way, choose a different option: Deal 2 damage to a unit or
    base / Defeat an upgrade / An opponent discards a card from their hand.

    Modelled with the new 'repeated_modal' decision kind: the controller discards
    0..3 cards, then picks one distinct option per discard (targeted options
    prompt for a target).  All chosen options are applied after the decision
    resolves."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_poe_dameron_attack)],
    )


# ── New primitive: sacrifice-resource-cost (shd-han-solo:07) ──────────────────
# Wrecker's When Played pays an *optional* cost (defeat a friendly resource) to
# unlock a follow-up effect (deal 5 damage to a ground unit).  The new
# self-contained 'sacrifice_resource' decision kind
# (actions.push_sacrifice_resource_for_damage) drives the two-stage "decide to
# sacrifice → choose the damage target" flow; the damage is dealt after the
# decision pops (the push_distribute_damage "pop, then deal" gotcha).  The trigger
# is a plain WhenPlayed whose one CustomEffect is a thin adapter onto the push
# helper (the Palpatine SOR_135 / Poe SHD_153 pattern), not irreducible card
# logic.  The decision is only pushed when the controller actually has a resource
# to spend AND a ground unit to hit, so "you may" with no upside is never offered.

def _wrecker_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: push the optional-sacrifice → deal-5 decision."""
    from swu.engine.actions import push_sacrifice_resource_for_damage
    push_sacrifice_resource_for_damage(
        state, source_ci, amount=5, target_controller="any", target_arena="ground")
    return state


@card_ability("SHD", "154")
def _wrecker():
    """SHD_154 — Overwhelm (keyword engine).  When Played: You may defeat a
    friendly resource. If you do, deal 5 damage to a ground unit.

    Modelled with the new 'sacrifice_resource' decision kind: the controller may
    defeat one of their resources and, if they do, deal 5 damage to a ground unit
    of either player."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_wrecker_when_played)],
    )


# ── New primitive: scaling-magnitude (shd-han-solo:08) ────────────────────────
# The Chaos of War deals each base a *different* amount of damage — equal to that
# base's own controller's hand size.  A fixed-amount DealDamage cannot express a
# per-target magnitude, so this is the new self-contained DealDamageEqualTo
# effect (a new effect dataclass + one resolver arm + a magnitude helper); it
# reuses the existing fixed-target (EACH_IN_PLAY base) resolution and
# _apply_deal_damage, and touches none of the trigger/decision machinery.

@card_ability("SHD", "159")
def _the_chaos_of_war():
    """SHD_159 — The Chaos of War (Event): Deal damage to each player's base
    equal to the number of cards in that player's hand.

    EACH_IN_PLAY auto-targets both bases (no player choice → resolves inline);
    DealDamageEqualTo("target_controller_hand") gives each base its own owner's
    hand size as the magnitude.  Note this event is in hand and not yet in
    discard while the magnitudes are read, so it does not count toward the
    controller's own hand size."""
    return EventAbility(effects=[
        DealDamageEqualTo(
            target=TargetSpec(kind="base", fixed=EACH_IN_PLAY),
            count="target_controller_hand",
        ),
    ])


# ── New primitive: granted-attack-restricted-attacker (shd-han-solo:09) ───────
# Desperate Attack grants an attack like Surprise Strike, but the attacker is
# restricted to a *damaged* unit.  The existing push_granted_attack seam gained
# an optional attacker_predicates filter (a serialisable list of TargetSpec
# predicate names) that narrows the offered AttackWithUnit options; if no unit
# qualifies the mandatory attack fizzles via DeclineGrantedAttack.  No change to
# the trigger/decision machinery — the event's one CustomEffect is a thin adapter
# onto the push helper (the Surprise Strike SOR_220 pattern).

def _desperate_attack(state, source_ci, target_id, event_ctx):
    """Adapter: grant an attack restricted to a damaged unit, +2/+0 this attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                        attacker_predicates=["damaged"])
    return state


@card_ability("SHD", "179")
def _desperate_attack_event():
    """SHD_179 — Desperate Attack (Event): Attack with a damaged unit. It gets
    +2/+0 for this attack.

    A granted attack (push_granted_attack) restricted to a damaged attacker via
    attacker_predicates=["damaged"]; the chosen unit gets a +2/+0 this-attack
    modifier.  Mandatory: if the controller has no damaged unit able to attack,
    the event fizzles."""
    return EventAbility(effects=[CustomEffect(fn=_desperate_attack)])


# ── New primitive: opponent-chooses-target (shd-han-solo:10) ──────────────────
# Grey Squadron Y-Wing's On Attack hands the *target choice* to an opponent (they
# pick which of their own cards is exposed), then the controller MAY deal 2 to it.
# The new self-contained 'opponent_chooses_target' decision kind
# (actions.push_opponent_chooses_target) drives the two stages, shifting the
# deciding player between them exactly as say_no (SOR_233) does — the controller
# never picks the target.  The damage is dealt after the decision pops (the
# push_distribute_damage "pop, then deal" gotcha).  The trigger is a plain
# OnAttack whose one CustomEffect is a thin adapter onto the push helper (the
# Palpatine SOR_135 pattern), not irreducible card logic.

def _grey_squadron_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push the opponent-chooses-target → may-deal-2 decision."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(state, source_ci, amount=2)
    return state


@card_ability("SHD", "246")
def _grey_squadron_y_wing():
    """SHD_246 — On Attack: An opponent chooses a unit or base they control.
    You may deal 2 damage to it.

    Modelled with the new 'opponent_chooses_target' decision kind: the opponent
    first picks one of their own units or base (mandatory — a base is always
    available), then the controller may deal 2 damage to that card or decline."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_grey_squadron_attack)],
    )


# ── Combat tricks, buffs & tempo (sabine-mean-green:03) ───────────────────────

@card_ability("SHD", "126")
def _the_darksaber():
    """The Darksaber (SHD_126) — Upgrade (attach to a non-Vehicle unit).

    "Attached unit gains, 'On Attack: Give an Experience token to each other
    friendly Mandalorian unit.'"  Modelled with GrantedAbility wrapping a normal
    OnAttack TriggerAbility that resolves from the HOST unit (the Armed to the
    Teeth SHD_175 pattern): when the host attacks, every other friendly
    Mandalorian unit (controller="friendly", Mandalorian trait, not_self — so the
    host itself is excluded) gets an Experience token (fixed=EACH_FRIENDLY
    auto-targets them all, resolves inline).

    The "attach to a non-Vehicle unit" restriction is handled by the engine's
    upgrade target parser (the non_vehicle predicate).  RESIDUAL (deferred): the
    cost clause "While playing this upgrade on a Mandalorian unit, ignore its
    aspect penalty" is NOT implemented — it is a play-cost modification (a new
    aspect-penalty-waiver seam at the upgrade play site), not part of the granted
    ability; the same kind of cost residual left unimplemented on the Smuggle-cost
    upgrades.  The card is fully playable (it attaches and its granted On Attack
    ability fires); only the conditional cost discount is missing."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(
                controller="friendly", kind="unit",
                traits=("Mandalorian",), predicates=("not_self",),
                fixed=EACH_FRIENDLY,
            ))],
        ),
    )


@card_ability("SHD", "249")
def _wookiee_warrior():
    """SHD_249 — When Played: If you control another Wookiee unit, draw a card.

    Grit is handled by the keyword engine.  The "another Wookiee" check excludes
    this unit itself (CONTROLLER_HAS_OTHER_TRAIT_UNIT); the whole trigger is
    gated by it, so the mandatory draw only happens when the condition holds and
    is never offered otherwise."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(count=1, player="controller")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, "Wookiee"),
    )


# ── Miscellaneous abilities (sabine-mean-green:04) ────────────────────────────

def _timely_intervention(state, source_ci, target_id, event_ctx):
    """Adapter: play a unit from hand, granting it Ambush for this phase."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, grant_keyword="Ambush")
    return state


# ── Bounty keyword group (the-mandalorian:01) ─────────────────────────────────
# Three bounty-granting UPGRADES and one combat-trick unit.  Bounty is the
# convention from shd-han-solo:02 (a WhenDefeated trigger resolving for the
# collector = the OPPONENT of the dying unit's controller).  For an upgrade that
# "Attached unit gains: 'Bounty — …'", the bounty is wrapped in a GrantedAbility
# so it resolves from the HOST (the Armed to the Teeth SHD_175 pattern).  These
# three bounties' effects benefit the *collector*, who therefore makes any
# target choice — unlike the deterministic Unlicensed Headhunter SHD_165 bounty,
# the collector is NOT the source's controller, so a plain targeted effect would
# prompt the wrong player.  Each is a CustomEffect that computes the collector and
# resolves from their perspective (a Shield/Experience select_token addressed to
# the collector, or an inline resource-ready).
#
# Engine support added for this group (both small, additive, synthetic-tested):
#   * resolver._collect_triggers now collects a GrantedAbility(WhenDefeated) from
#     a *defeated* unit's upgrades (stashed by _defeat_unit in
#     event_ctx["defeated_upgrades"] before detaching) — without this the granted
#     bounty could never fire, since the host leaves play and its upgrades detach
#     before UnitDefeated.  This completes the GrantedAbility primitive for the
#     defeated-host case.
#   * push_select_token gained decider_id / after_resolve_idx overrides so the
#     COLLECTOR (not the dying unit's controller) makes the token choice and the
#     attacker's turn resumes after a mid-combat bounty.

def _bounty_collector_id(state, event_ctx):
    """The player who collects the bounty: the OPPONENT of whoever controlled the
    dying unit at the moment of defeat (recorded in event_ctx by _defeat_unit)."""
    controller_at_death = event_ctx.get("defeated_controller_id")
    if controller_at_death is None:
        return None
    return state.players[1 - state.player_index(controller_at_death)].player_id


def _public_enemy_bounty(state, source_ci, target_id, event_ctx):
    """Collector gives a Shield token to a unit of their choice."""
    from swu.engine.actions import push_select_token
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    push_select_token(
        state, source_ci, token_type="Shield", max_targets=1,
        controller="any", kind="unit",
        decider_id=collector, after_resolve_idx=state.active_player_index)
    return state


@card_ability("SHD", "68")
def _public_enemy():
    """SHD_68 — Public Enemy (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Give a Shield token to a unit.'"

    GrantedAbility(WhenDefeated) resolving from the host; the collector (the
    opponent of the host's controller) picks the unit to shield via a
    collector-addressed select_token (max 1).  NOTE: "Give a Shield token to a
    unit" is mandatory-if-able, but select_token's "up to" lets the collector
    finish without giving — a negligible deviation, since declining a free shield
    is never advantageous."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_public_enemy_bounty)],
            is_bounty=True,
        ),
    )


def _wanted_bounty(state, source_ci, target_id, event_ctx):
    """Collector readies up to 2 of their own exhausted resources (deterministic;
    resources are interchangeable, so no choice — resolves inline)."""
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    ps = state.player_by_id(collector)
    readied = 0
    for r in ps.resources:
        if readied >= 2:
            break
        if r.exhausted:
            r.exhausted = False
            readied += 1
    return state


@card_ability("SHD", "221")
def _wanted():
    """SHD_221 — Wanted (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Ready 2 friendly resources.'"

    GrantedAbility(WhenDefeated) resolving from the host; "friendly resources" is
    from the collector's perspective, so the collector readies up to 2 of their
    own exhausted resources.  Deterministic (resources are fungible) → resolves
    inline with no decision."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_wanted_bounty)],
            is_bounty=True,
        ),
    )


def _rich_reward_bounty(state, source_ci, target_id, event_ctx):
    """Collector gives an Experience token to each of up to 2 units of their
    choice (the collector picks via a collector-addressed select_token)."""
    from swu.engine.actions import push_select_token
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    push_select_token(
        state, source_ci, token_type="Experience", max_targets=2,
        controller="any", kind="unit",
        decider_id=collector, after_resolve_idx=state.active_player_index)
    return state


@card_ability("SHD", "261")
def _rich_reward():
    """SHD_261 — Rich Reward (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Give an Experience token to each of up to 2 units.'"

    GrantedAbility(WhenDefeated) resolving from the host; the collector picks up
    to 2 units (any) to receive an Experience token via a collector-addressed
    select_token (the Medal Ceremony SOR_245 select-up-to-N pattern)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_rich_reward_bounty)],
            is_bounty=True,
        ),
    )


# ── moff-gideon:01 — Bounty cards ─────────────────────────────────────────────
# Bounty heals resolve for the COLLECTOR (the opponent of the dying unit's
# controller).  Per the established bounty-heal convention (a bounty's "Heal N
# from a base" auto-heals the collector's base via enemy-perspective targeting),
# Top Target's "Heal … from a unit or base" heals the collector's base and the
# "or a unit" option is dropped — a documented simplification (the collector
# benefits from healing their base, the safe default, and avoids a new
# collector-decided heal-target decision kind).

def _top_target_bounty(state, source_ci, target_id, event_ctx):
    """Collector heals 4 (6 if the dying unit is unique) damage from their base."""
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    amount = 6 if getattr(source_ci.card_def, "is_unique", False) else 4
    base = state.player_by_id(collector).base_instance
    if base is not None:
        base.damage = max(0, base.damage - amount)
    return state


@card_ability("SHD", "71")
def _top_target():
    """SHD_71 — Top Target (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Heal 4 damage from a unit or base. If this unit is unique, heal 6
    damage instead.'"

    GrantedAbility(WhenDefeated) resolving from the host (the dying unit), so the
    "If this unit is unique" check reads the host's is_unique.  The collector heals
    their base (see the convention note above)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_top_target_bounty)],
            is_bounty=True,
        ),
    )


def _price_on_your_head_bounty(state, source_ci, target_id, event_ctx):
    """Collector puts the top card of THEIR deck into play as a resource."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    ps = state.player_by_id(collector)
    if not ps.deck:
        return state
    ci = ps.deck.pop(0)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    state.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))
    return state


@card_ability("SHD", "125")
def _price_on_your_head():
    """SHD_125 — Price on Your Head (Upgrade, Bounty/Condition): "Attached unit
    gains: 'Bounty — Put the top card of your deck into play as a resource.'"

    GrantedAbility(WhenDefeated) resolving from the host; "your deck" is from the
    collector's perspective, so the collector puts the top card of their own deck
    into play as a ready resource.  Deterministic (deck order is fixed) → resolves
    inline with no decision."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_price_on_your_head_bounty)],
            is_bounty=True,
        ),
    )


def _the_client_grant_bounty(state, source_ci, target_id, event_ctx):
    """Grant the chosen unit a phase-scoped "Bounty — Heal 5 damage from a base"
    by appending the encoded key to its ``granted_bounties`` (resolved inline for
    the collector when that unit is defeated; see actions._resolve_granted_bounty).
    """
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    unit.granted_bounties.append("heal_base:5")
    return state


@card_ability("SHD", "31")
def _the_client():
    """SHD_31 — The Client (Unit, Shielded + Bounty): "Shielded.  Action [Exhaust]:
    Choose a unit.  For this phase, it gains: 'Bounty — Heal 5 damage from a base.'"

    Shielded is the keyword engine.  The activated ability is a CustomEffect with a
    ``target`` TargetSpec so the standard resolve_effects machinery prompts the
    controller to choose any unit (the CustomEffect.target seam); the fn grants that
    unit a phase-scoped bounty via the new ``CardInstance.granted_bounties`` field.
    The bounty heals the collector's base by 5 when the chosen unit is defeated this
    phase (you point it at an enemy unit so you collect)."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(
            fn=_the_client_grant_bounty,
            target=TargetSpec(controller="any", kind="unit"),
        )],
        title="Grant a unit a Bounty (heal 5 from a base) this phase",
    )


def _unit_has_bounty(state, ci) -> bool:
    """True if ``ci`` "has a Bounty": the Bounty keyword printed on (or granted
    to) the unit itself, OR a non-token attached upgrade that carries the Bounty
    keyword (Public Enemy / Wanted / Rich Reward etc.).  Bounties are modelled as
    abilities/granted upgrades, not a queryable keyword state, so this is the
    structural definition used by Chain Code Collector's combat trick."""
    from swu.engine.keywords import has_keyword, Keyword
    from swu.cards.models import TokenUpgrade
    if has_keyword(state, ci, Keyword.BOUNTY):
        return True
    for u in ci.attached_upgrades:
        if isinstance(u.card_def, TokenUpgrade):
            continue
        if "Bounty" in (getattr(u.card_def, "keywords", ()) or ()):
            return True
    return False


def _chain_code_on_attack(state, source_ci, target_id, event_ctx):
    """If the defender has a Bounty, give it −4/−0 for this attack."""
    from swu.abilities.resolver import _make_modifier
    defender_id = event_ctx.get("defender_id")
    if not defender_id:
        return state  # attacking a base — no defender unit
    result = state.find_instance(defender_id)
    if result is None:
        return state
    _, defender = result
    if not _unit_has_bounty(state, defender):
        return state
    mod = _make_modifier(
        state, source_ci.instance_id, defender_id,
        power=-4, hp=0, duration=Duration.THIS_ATTACK)
    state.modifiers.append(mod)
    return state


@card_ability("SHD", "216")
def _chain_code_collector():
    """SHD_216 — Chain Code Collector (Unit, Ambush + Bounty keyword): "On Attack:
    If the defender has a Bounty, it gets −4/−0 for this attack."

    Ambush is the keyword engine.  The On Attack is a combat trick: a CustomEffect
    that, before combat damage (OnAttack fires at CR step 2, ahead of power
    computation), checks the current defender for a Bounty (printed keyword or a
    bounty-granting upgrade) and, if present, applies a this-attack −4/−0
    ModifyStats to it.  Resolves inline (no target choice — the defender is fixed
    by the attack), so no decision is pushed."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_chain_code_on_attack)],
    )


# ── Direct damage & removal (the-mandalorian:02) ──────────────────────────────

@card_ability("SHD", "78")
def _fell_the_dragon():
    """SHD_78 — Fell the Dragon (Event, Tactic): Defeat a non-leader unit with
    5 or more power.

    A plain EventAbility with a single DefeatUnit whose TargetSpec narrows the
    candidates to non-leader units (the ``non_leader`` predicate) of effective
    power >= 5 (the new ``power_min`` filter, read via compute_power so buffs /
    upgrades / Experience tokens count).  Mandatory-if-able: with no eligible
    unit the event fizzles; otherwise the controller chooses one to defeat."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader",), power_min=5)),
    ])


@card_ability("SHD", "220")
def _fennec_shand():
    """SHD_220 — Fennec Shand (Unit, Ambush): "On Attack: Deal 1 damage to the
    defender (if it's a unit) for each different cost among cards in your discard
    pile."

    Ambush is handled by the keyword engine.  The On Attack is a scaling-magnitude
    DealDamageEqualTo targeting the current defender (``fixed=DEFENDER`` — resolves
    to the defending unit from event_ctx, and to nothing when attacking a base, so
    "if it's a unit" falls out for free).  The per-hit magnitude is the new
    ``source_controller_discard_distinct_costs`` count — the number of distinct
    printed costs among cards in the controller's discard pile (1 damage each).
    A magnitude of 0 (empty discard) is a no-op."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamageEqualTo(
            target=TargetSpec(kind="unit", fixed=DEFENDER),
            count="source_controller_discard_distinct_costs",
        )],
    )


# ── Card advantage & disruption (the-mandalorian:03) ──────────────────────────
# Five cards.  Two are deck searches that reuse the existing deck_search seam
# (Grand Moff Tarkin SOR_84 / Recruit SOR_123 pattern), one mills+conditionally-
# returns the top card of the deck (an inline CustomEffect, no player choice), one
# bounces an enemy unit (the existing ReturnToHand effect), and one returns an
# upgrade from the discard pile (the new self-contained return_from_discard
# decision kind — see actions.push_return_from_discard).

def _is_upgrade_card(card_def) -> bool:
    """An "upgrade" is a non-token Upgrade card (Token upgrades — Shield /
    Experience — are a separate class and never sit in a deck or discard pile)."""
    from swu.cards.models import Upgrade
    return isinstance(card_def, Upgrade)


def _is_mando_or_upgrade(card_def) -> bool:
    """A "Mandalorian and/or upgrade card": the Mandalorian trait OR an upgrade."""
    if "Mandalorian" in (getattr(card_def, "traits", None) or ()):
        return True
    return _is_upgrade_card(card_def)


def _greef_karga_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 5 for an upgrade and draw it (mandatory if able)."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, window=5,
                     eligible=_is_upgrade_card, up_to=False)
    return state


@card_ability("SHD", "245")
def _greef_karga():
    """SHD_245 — Greef Karga (Unit): When Played: Search the top 5 cards of your
    deck for an upgrade, reveal it, and draw it. (Put the other cards on the
    bottom of your deck in a random order.)

    A thin CustomEffect adapter onto the deck_search seam (the Recruit SOR_123
    pattern): ``count=1, window=5, up_to=False`` — exactly one upgrade is taken
    while one is present (mandatory if able), else nothing; the un-taken top-5
    cards are bottomed in a seeded-random order."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_greef_karga_search)],
    )


def _this_is_the_way_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 8 for up to 2 Mandalorian and/or upgrade cards."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=2, window=8,
                     eligible=_is_mando_or_upgrade, up_to=True)
    return state


@card_ability("SHD", "253")
def _this_is_the_way():
    """SHD_253 — This Is The Way (Event): Search the top 8 cards of your deck for
    up to 2 Mandalorian and/or upgrade cards, reveal them, and draw them. (Put the
    other cards on the bottom of your deck in a random order.)

    A thin CustomEffect adapter onto the deck_search seam (the Grand Moff Tarkin
    SOR_84 pattern): ``count=2, window=8, up_to=True`` — 0, 1, or 2 of the
    eligible cards (Mandalorian trait or any upgrade) may be taken; the rest of
    the top 8 are bottomed in a seeded-random order."""
    return EventAbility(effects=[CustomEffect(fn=_this_is_the_way_search)])


def _kuiil_on_attack(state, source_ci, target_id, event_ctx):
    """Discard the top card of the controller's deck; if it shares an aspect with
    the controller's base, return it from the discard pile to hand.

    "Discard a card from your deck" mills the top card (no player choice — the
    deck is ordered).  The aspect comparison is against the controller's base
    card; on a match the milled card moves discard → hand.  An empty deck is a
    clean no-op.  Resolves inline (deterministic, no decision)."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    card = ps.deck.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    base = ps.base_instance
    base_aspects = {a.name for a in (getattr(base.card_def, "aspects", None) or ())} if base else set()
    card_aspects = {a.name for a in (getattr(card.card_def, "aspects", None) or ())}
    if base_aspects & card_aspects:
        ps.discard.remove(card)
        card.zone = Zone.HAND
        ps.hand.append(card)
    return state


@card_ability("SHD", "41")
def _kuiil():
    """SHD_41 — Kuiil (Unit, Restore 1): On Attack: Discard a card from your deck.
    If it shares an aspect with your base, return it to your hand.

    Restore 1 is the keyword engine.  The On Attack is an inline CustomEffect (no
    player choice): mill the top card of the deck, and if it shares an aspect with
    the controller's base, move it from the discard pile back to hand."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_kuiil_on_attack)],
    )


def _razor_crest_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: let the controller return one upgrade from their discard pile to
    hand (push_return_from_discard, "up to 1")."""
    from swu.engine.actions import push_return_from_discard
    push_return_from_discard(state, source_ci, count=1, eligible=_is_upgrade_card)
    return state


@card_ability("SHD", "44")
def _razor_crest():
    """SHD_44 — Razor Crest (Unit, Restore 2): When Played: You may return an
    upgrade from your discard pile to your hand.

    Restore 2 is the keyword engine.  The When Played is a thin CustomEffect
    adapter onto the new return_from_discard decision kind
    (push_return_from_discard): the controller may take up to one upgrade from
    their discard pile back to hand, or finish without taking one (the "you may").
    The decision is only pushed when an upgrade is actually present in the discard
    pile."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_razor_crest_when_played)],
    )


@card_ability("SHD", "206")
def _spare_the_target():
    """SHD_206 — Spare the Target (Event, Tactic): Return an enemy non-leader unit
    to its owner's hand. Collect that unit's Bounties.

    The bounce is a plain ReturnToHand targeting an enemy non-leader arena unit
    (mandatory-if-able: the controller chooses one to return, or the event fizzles
    with no eligible target).

    RESIDUAL (deferred): "Collect that unit's Bounties" is NOT implemented.
    Bounties are modelled as ``WhenDefeated`` triggers (printed, or a
    GrantedAbility on a bounty-granting upgrade) that fire only on *defeat* and
    resolve for the collector; "collect on return-to-hand" would require both a
    way to fire those triggers off the bounce path AND a marker to distinguish a
    *bounty* WhenDefeated from an ordinary one (e.g. Rhokai Gunship's
    "When Defeated: deal 1") — that touches the trigger-firing machinery and needs
    a bounty tag, so it is flagged for a dedicated framework session.  The card is
    fully playable (the bounce works); only the bounty-collection rider is missing,
    and it matters only when the bounced unit actually carries a bounty."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="enemy", kind="unit",
                                predicates=("non_leader",))),
    ])


@card_ability("SHD", "129")
def _timely_intervention_event():
    """SHD_129 — Timely Intervention (Event, cost 1): Play a unit from your
    hand. Give it Ambush for this phase.

    A thin CustomEffect adapter onto the play-from-hand subsystem
    (push_play_from_hand with grant_keyword="Ambush"): the chosen affordable
    hand unit is played and gains Ambush as it enters play (a keyword_grant
    modifier applied before the enter-play bus, so Ambush triggers immediately —
    the unit may ready and attack an enemy unit).  No cost cap (any affordable
    unit is eligible).  Smuggle [2, command] is handled by the keyword engine;
    the printed Ambush keyword on the event itself is inert (an event never
    enters an arena, so the Ambush enter-play listener never fires for it)."""
    return EventAbility(effects=[CustomEffect(fn=_timely_intervention)])


# ── Combat tricks, buffs & tempo (the-mandalorian:04) ─────────────────────────
# Seven cards.  Six compose from existing primitives; only The Mandalorian SHD_18
# needs engine support (two small additive seams, neither touching decision/
# resolution machinery):
#   * WhenYouPlayCard gained a ``card_type`` filter ("When you play an upgrade").
#   * resolver._collect_triggers now also scans each player's base_zone for an
#     UNDEPLOYED leader's triggers — _cards_in_play only yields arenas, so an
#     undeployed leader's "When you play an upgrade" trigger could never fire
#     before.  Purely additive (mirrors the existing defeated-unit / upgrade-play
#     collection scans).
#   * Condition.SOURCE_READY gates the undeployed self-exhaust so it is offered
#     only while the leader is ready (the "you may exhaust this leader" cost can
#     be paid once per round).

@card_ability("SHD", "18")
def _the_mandalorian():
    """SHD_18 — The Mandalorian (Leader, Bounty Hunter/Mandalorian).

    Undeployed: "When you play an upgrade: You may exhaust this leader. If you do,
        exhaust an enemy unit with 4 or less remaining HP."
    Deployed:   "When you play an upgrade: You may exhaust an enemy unit with 6 or
        less remaining HP."
    Epic Action: deploy when you control 6+ resources (the standard leader-deploy
        machinery via deploy_threshold — no ability registration needed).

    Both sides are optional ``WhenYouPlayCard(card_type="upgrade")`` triggers (the
    "you may").  The deployed side is a single ExhaustCard on an enemy unit with
    ≤6 remaining HP (``hp_remaining_max=6``); with no eligible enemy the optional
    trigger auto-declines.  The undeployed side first exhausts the chosen enemy
    (≤4 remaining HP) then exhausts the leader itself (the cost) — the targeted
    effect is ordered FIRST so the player is prompted exactly once (a fixed SELF
    effect ahead of a targeted effect would otherwise double-prompt); the outcome
    is identical to the printed order since exhausting the leader does not change
    the legal enemy targets.  The undeployed trigger is gated by SOURCE_READY so
    it is only offered while the leader is ready — modelling that "you may exhaust
    this leader" can be paid only once before it readies again at regroup."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="upgrade"),
            effects=[
                ExhaustCard(TargetSpec(controller="enemy", kind="unit",
                                       hp_remaining_max=4)),
                ExhaustCard(TargetSpec(kind="unit", fixed=SELF)),
            ],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="upgrade"),
            effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit",
                                            hp_remaining_max=6))],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("SHD", "40")
def _clan_wren_rescuer():
    """SHD_40 — Clan Wren Rescuer (Unit): When Played: Give an Experience token
    to a unit.

    A plain WhenPlayed GiveToken; the controller chooses any unit (mandatory-if-
    able — a unit is in play, the Rescuer itself being a valid target)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(controller="any", kind="unit"))],
    )


def _the_armorer_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: give a Shield token to each of up to 3 Mandalorian units."""
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Shield", max_targets=3,
        controller="any", kind="unit", traits=["Mandalorian"])
    return state


@card_ability("SHD", "47")
def _the_armorer():
    """SHD_47 — The Armorer (Unit): When Played: Give a Shield token to each of up
    to 3 Mandalorian units.

    The "up to 3" multi-pick is the select_token seam (Medal Ceremony SOR_245
    pattern): the controller picks up to 3 distinct Mandalorian units, each
    receiving a Shield, or stops early.  ``controller="any"`` mirrors the printed
    text (it omits "friendly"); since a Shield benefits the recipient the
    controller never picks an enemy.  A thin CustomEffect adapter onto the push
    helper."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_the_armorer_when_played)],
    )


@card_ability("SHD", "56")
def _follower_of_the_way():
    """SHD_56 — Follower of The Way (Unit): While this unit is upgraded, it gets
    +1/+1.

    A self-targeted ConstantAbility gated by SOURCE_UPGRADED (the unit has ≥1
    attached upgrade; per CR, Shield/Experience tokens count as upgrades), read
    passively by compute_power/compute_hp — the buff winks on/off with the
    presence of any upgrade.  (The Protector of the Throne SHD_247 pattern, with a
    StatBonus instead of a KeywordGrant.)"""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=1, hp=1)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


@card_ability("SHD", "66")
def _cargo_juggernaut():
    """SHD_66 — Cargo Juggernaut (Unit, Shielded): When Played: If you control
    another Vigilance unit, heal 4 damage from your base.

    Shielded is the keyword engine.  The When Played is a Heal of 4 on the
    controller's base (kind="base", fixed=EACH_FRIENDLY → resolves inline), gated
    by CONTROLLER_HAS_OTHER_ASPECT_UNIT("Vigilance") — "another Vigilance unit"
    excludes the Juggernaut itself, so the whole trigger is collected only when
    the condition holds.  (Cargo Juggernaut is itself a Vehicle, not Vigilance-
    tagged for the *other*-unit check, but the condition excludes the source
    regardless.)"""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[Heal(4, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 "Vigilance"),
    )


def _mando_armor_when_played(state, source_ci, target_id, event_ctx):
    """If the attached host unit is a Mandalorian, give it a Shield token.

    Resolves inline: the host is read from event_ctx["attached_to_id"] (threaded
    by _attach_upgrade); no player choice."""
    from swu.engine.tokens import attach_token
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    result = state.find_instance(host_id)
    if result is None:
        return state
    ps, host = result
    if "Mandalorian" in (getattr(host.card_def, "traits", None) or ()):
        attach_token(state, ps, host, "Shield")
    return state


@card_ability("SHD", "73")
def _mandalorian_armor():
    """SHD_73 — Mandalorian Armor (Upgrade, attach to a non-Vehicle unit):
    When Played: If attached unit is a Mandalorian, give a Shield token to it.

    The attach restriction is the engine's upgrade-target parser (non_vehicle).
    The When Played is an inline CustomEffect (no player choice — the host is
    fixed by the attachment): if the host has the Mandalorian trait, attach a
    Shield to it.  An upgrade's own WhenPlayed is collected by the
    UpgradePlayed special-case in resolver._collect_triggers."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_mando_armor_when_played)],
    )


@card_ability("SHD", "74")
def _vambrace_grappleshot():
    """SHD_74 — Vambrace Grappleshot (Upgrade, attach to a non-Vehicle unit):
    Attached unit gains: "On Attack: Exhaust the defender."

    The attach restriction is the engine's upgrade-target parser (non_vehicle).
    The granted ability is a GrantedAbility wrapping an OnAttack TriggerAbility
    that resolves from the HOST (the Armed to the Teeth SHD_175 pattern): when the
    host attacks a unit, the defender (fixed=DEFENDER from event_ctx — resolves to
    nothing when attacking a base, so "exhaust the defender" fizzles harmlessly on
    a base attack) is exhausted.  Resolves inline (fixed target)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttack(),
            effects=[ExhaustCard(TargetSpec(kind="unit", fixed=DEFENDER))],
        ),
    )


# ── Miscellaneous abilities (the-mandalorian:06) ──────────────────────────────
# Two cards, each needing a small additive engine seam (neither touches core
# resolution or the trigger/decision machinery destructively):
#   * Foundling SHD_69 grants its host the Mandalorian trait — modelled with the
#     new TraitGrant constant effect read by the trait query layer
#     (swu.engine.traits.get_traits/has_trait), which the target matcher, the
#     trait-gated Conditions, and the decision trait filters now consult so a
#     granted trait counts everywhere a printed one does.
#   * Survivors' Gauntlet SHD_64 relocates an in-play upgrade — modelled with the
#     new self-contained 'move_upgrade' decision kind (actions.push_move_upgrade).

@card_ability("SHD", "69")
def _foundling():
    """SHD_69 — Foundling (Upgrade): Attached unit gains the Mandalorian trait.

    A ConstantAbility carrying a TraitGrant; on an upgrade the grant resolves onto
    its attached host (the trait query layer scans a unit's attached upgrades for
    a TraitGrant constant).  The host then counts as Mandalorian everywhere
    effective traits are read — "each friendly Mandalorian unit" effects (The
    Darksaber SHD_126), Mandalorian-only token grants (The Armorer SHD_47), and
    the CONTROLLER_HAS_(OTHER_)TRAIT_UNIT conditions — for as long as Foundling is
    attached."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[TraitGrant("Mandalorian")],
    )


def _survivors_gauntlet_move(state, source_ci, target_id, event_ctx):
    """Adapter: push the move-an-upgrade decision (Survivors' Gauntlet SHD_64)."""
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci)
    return state


@card_ability("SHD", "64")
def _survivors_gauntlet():
    """SHD_64 — Survivors' Gauntlet (Unit, Transport/Vehicle): When Played/On
    Attack: You may attach an upgrade on a unit to another eligible unit
    controlled by the same player.

    Both triggers are thin CustomEffect adapters onto the new 'move_upgrade'
    decision kind (push_move_upgrade): the controller may relocate any in-play
    (non-token) upgrade from its current host to another unit controlled by the
    same player, provided the destination satisfies the upgrade's attach
    restriction.  The "you may" is the DeclineMoveUpgrade option; when no upgrade
    can be moved the decision is not even pushed (a clean no-op)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_survivors_gauntlet_move)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_survivors_gauntlet_move)],
        ),
    ]


# ── New primitive: capture (the-mandalorian:07) ───────────────────────────────
# Capture removes an enemy unit from play and places it facedown "under" the
# capturing unit until that unit leaves play, when it returns to its owner's
# arena.  Implemented as the new registry.CaptureUnit effect + the
# actions._apply_capture / _release_captured_cards helpers, reusing the existing
# CAPTURE_PILE zone (already wired into conservation / serialisation / lookup) and
# the normal resolve_effects / ChooseTarget target machinery — so no new decision
# kind and no change to the trigger/decision machinery.

@card_ability("SHD", "251")
def _the_mandalorians_rifle():
    """SHD_251 — The Mandalorian's Rifle (Upgrade, attach to a friendly
    non-Vehicle unit): When Played: If attached unit is The Mandalorian, he
    captures an exhausted enemy non-leader unit.

    The non-Vehicle attach restriction is the engine's upgrade-target parser.
    The "If attached unit is The Mandalorian" gate is the ATTACHED_HOST_NAMED
    condition (the upgrade's host name must contain "The Mandalorian"), so the
    whole WhenPlayed trigger is collected only when the host is the Mandalorian.
    The capture itself is the new CaptureUnit effect targeting an exhausted enemy
    non-leader unit (mandatory-if-able — the controller picks among them and the
    ability fizzles with no eligible target); the captor is the host, read by the
    resolver from event_ctx["attached_to_id"].  An upgrade's own WhenPlayed is
    collected by the UpgradePlayed special-case in resolver._collect_triggers."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(target=TargetSpec(
            controller="enemy", kind="unit",
            predicates=("non_leader", "exhausted")))],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "The Mandalorian"),
    )


# ── New primitive: capture (moff-gideon:07) ───────────────────────────────────
# Two more capturers reusing the the-mandalorian:07 CaptureUnit effect (no engine
# change beyond one additive TargetSpec.power_less_than_captor filter for SHD_124).

@card_ability("SHD", "120")
def _discerning_veteran():
    """SHD_120 — Discerning Veteran (Unit, Bounty Hunter): "When Played: This unit
    captures an enemy non-leader ground unit."

    A plain WhenPlayed CaptureUnit targeting an enemy non-leader ground unit.
    This unit captures via its OWN ability (not an upgrade), so there is no
    event_ctx["attached_to_id"]: the resolver's CaptureUnit arm falls back to the
    source unit as the captor (the card sits facedown under Discerning Veteran).
    Mandatory-if-able — the controller picks among eligible enemy ground units and
    the ability fizzles cleanly with no eligible target."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(target=TargetSpec(
            controller="enemy", kind="unit", arena="ground",
            predicates=("non_leader",)))],
    )


@card_ability("SHD", "124")
def _legal_authority():
    """SHD_124 — Legal Authority (Upgrade, Law; attach to a friendly unit):
    "When Played: Attached unit captures an enemy non-leader unit with less power
    than it."

    A WhenPlayed CaptureUnit (the Mandalorian's Rifle SHD_251 pattern) where the
    captor is the attached host (read by the resolver from
    event_ctx["attached_to_id"], threaded by _attach_upgrade), so the captured
    card sits facedown under the host until it leaves play.  "with less power than
    it" is the new additive TargetSpec.power_less_than_captor filter: the
    candidate's effective power must be strictly less than the host's effective
    power (the same captor resolution as the effect, evaluated during target
    enumeration off the persisted event_ctx).  No name gate — the upgrade always
    captures on play; mandatory-if-able (fizzles with no weaker enemy)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(target=TargetSpec(
            controller="enemy", kind="unit",
            predicates=("non_leader",), power_less_than_captor=True))],
    )


# ── Combat tricks, buffs & tempo (the-mandalorian:05) ─────────────────────────
# Three cards, all composing from existing primitives — no engine change.

@card_ability("SHD", "196")
def _grogu():
    """SHD_196 — Grogu (Unit, Force): "Action [Exhaust]: Exhaust an enemy unit."

    A plain ActivatedAbility whose cost is exhausting Grogu itself (ExhaustSelf)
    and whose effect exhausts a chosen enemy unit (ExhaustCard, controller=
    "enemy").  Mandatory-once-chosen: with no enemy unit the targeted effect
    fizzles silently (the resolver skips an effect with no legal target), so the
    only cost is Grogu's own exhaustion — the player simply never uses it then."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit"))],
        title="Exhaust an enemy unit",
    )


def _snapshot_reflexes_attack(state, source_ci, target_id, event_ctx):
    """Adapter: optionally grant an attack pinned to this upgrade's host unit.

    The "you may" is expressed by push_granted_attack(optional=True) — a single
    decision offering the host's attack(s) plus DeclineGrantedAttack.  When the
    host is exhausted it has no attack to offer (it can only attack if ready), so
    the decision presents only the decline."""
    from swu.engine.actions import push_granted_attack
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        push_granted_attack(state, source_ci, attacker_id=host_id, optional=True)
    return state


@card_ability("SHD", "223")
def _snapshot_reflexes():
    """SHD_223 — Snapshot Reflexes (Upgrade): "When Played: You may attack with
    attached unit. (It can only attack if it's ready.)"

    The granted attack is pinned to the upgrade's host via
    push_granted_attack(attacker_id=host, optional=True) — the Hotshot DL-44
    Blaster SHD_174 pattern, but optional (a "may") and firing on a normal play
    (WhenPlayed; an upgrade's own WhenPlayed is collected by the UpgradePlayed
    special-case in resolver._collect_triggers).  No stat bonus.  The "ready"
    restriction falls out of the attack enumeration (an exhausted host offers no
    attack)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_snapshot_reflexes_attack)],
    )


@card_ability("SHD", "258")
def _mandalorian_warrior():
    """SHD_258 — Mandalorian Warrior (Unit, Mandalorian): "When Played: You may
    give an Experience token to another Mandalorian unit."

    An optional WhenPlayed GiveToken whose target is another Mandalorian unit
    (traits=("Mandalorian",), not_self — the Warrior excludes itself).
    ``controller="any"`` mirrors the printed text (it omits "friendly"); since an
    Experience token benefits the recipient the controller never picks an enemy.
    The "you may" is the optional decline; with no other Mandalorian unit in play
    the optional trigger auto-declines (no prompt)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="any", kind="unit",
            traits=("Mandalorian",), predicates=("not_self",)))],
        optional=True,
    )


@card_ability("SHD", "231")
def _surprise_strike():
    """SHD_231 — Surprise Strike (Event, Tactic): "Attack with a unit. It gets
    +3/+0 for this attack."

    Identical to Surprise Strike SOR_220 — a plain ``EventAbility`` whose one
    ``CustomEffect`` is a thin adapter calling ``push_granted_attack(power_bonus=3,
    hp_bonus=0)`` (the Surprise Strike SOR_220 / Desperate Attack SHD_179 pattern):
    the controller picks a unit to attack with, and that unit gets +3/+0 for the
    attack via a this-attack stats modifier applied in AttackWithUnit.  No new
    primitive — reuses the existing granted_attack seam.
    """
    def _grant(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(state, source_ci, power_bonus=3, hp_bonus=0)
        return state

    return EventAbility(effects=[CustomEffect(fn=_grant)])


# ── moff-gideon:02 — Direct damage & removal ──────────────────────────────────

@card_ability("SHD", "30")
def _death_trooper():
    """SHD_30 — Death Trooper (Unit): "When Played: Deal 2 damage to a friendly
    ground unit and 2 damage to an enemy ground unit."

    Two mandatory ``DealDamage`` effects, each with its own targeted ``TargetSpec``
    (friendly / enemy ground unit).  The resolver prompts for each target in turn;
    an effect with no legal target fizzles (e.g. no enemy ground unit on the board).
    Death Trooper itself enters the ground arena before its WhenPlayed resolves, so
    it is always a legal "friendly ground unit" target — faithful to the mandatory
    text (the controller may have to point the first 2 at their own unit)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            DealDamage(2, TargetSpec(controller="friendly", kind="unit", arena="ground")),
            DealDamage(2, TargetSpec(controller="enemy", kind="unit", arena="ground")),
        ],
    )


@card_ability("SHD", "262")
def _confiscate():
    """SHD_262 — Confiscate (Event, Law): "Defeat an upgrade."

    A plain ``EventAbility`` with one mandatory ``DefeatUnit(kind="upgrade")`` (the
    Disabling Fang Fighter SHD_166 / Confiscate pattern, but mandatory rather than
    "you may").  ``kind="upgrade"`` enumerates real (non-token) upgrades attached to
    any unit; the controller picks one to defeat.  Fizzles cleanly when no real
    upgrade is in play."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="upgrade")),
    ])


def _calculated_lethality_fn(state, source_ci, target_id, event_ctx):
    """Calculated Lethality (SHD_39) resolution.

    The controller chose ``target_id`` (a non-leader unit costing ≤ 3) via the
    CustomEffect's TargetSpec.  Count the upgrades currently on it, defeat it, then
    — "for each upgrade that was on that unit" — push a ``select_token`` decision
    letting the controller give that many Experience tokens to friendly units.

    We count *all* attached upgrades, including Shield/Experience tokens, since
    those are upgrade cards per the CR ("each upgrade that was on that unit").  The
    token distribution reuses ``push_select_token`` ("give a token to each of up to
    N units"), which lands as a nested decision beneath this event's buried
    ``resolve_effects`` decision (the SOR_233 nested-decision pattern) and resumes
    cleanly via AutoResolveEffects when it finishes."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import push_select_token
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, target_ci = result
    n_upgrades = len(target_ci.attached_upgrades)
    state = _apply_defeat_unit(state, target_id)
    if n_upgrades > 0:
        push_select_token(
            state, source_ci,
            token_type="Experience", max_targets=n_upgrades,
            controller="friendly", kind="unit",
        )
    return state


@card_ability("SHD", "39")
def _calculated_lethality():
    """SHD_39 — Calculated Lethality (Event, Tactic): "Defeat a non-leader unit
    that costs 3 or less. For each upgrade that was on that unit, give an
    Experience token to a friendly unit."

    A single ``CustomEffect`` carrying a TargetSpec (non-leader unit, cost ≤ 3):
    the resolver prompts for the unit, then ``_calculated_lethality_fn`` counts its
    upgrades, defeats it, and (for each upgrade) gives an Experience token to a
    friendly unit via ``push_select_token``.  The dynamic per-upgrade token count is
    why this is one CustomEffect rather than ``[DefeatUnit, GiveToken]`` — the count
    is only known after the unit is chosen and is gone once it is defeated, and
    ``GiveToken`` cannot place a state-derived number of distinct-target tokens.

    DEVIATION (minor): ``push_select_token`` gives each token to a *distinct*
    friendly unit, whereas the literal text would let two tokens land on the same
    unit.  With a unit costing ≤ 3 the upgrade count is small and Experience tokens
    are rarely worth doubling up, so the loss is negligible."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_calculated_lethality_fn,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader",), cost_max=3),
        ),
    ])


# ── moff-gideon:03 — Card advantage & disruption ──────────────────────────────

@card_ability("SHD", "28")
def _doctor_pershing():
    """SHD_28 — Doctor Pershing (Unit, Imperial): "Action [Exhaust, deal 1 damage
    to a friendly unit]: Draw a card."

    The activated ability exhausts the source (``ExhaustSelf``) and resolves two
    effects: deal 1 damage to a friendly unit, then draw a card.  The "deal 1
    damage to a friendly unit" half of the printed *cost* is modelled as a
    mandatory targeted effect rather than a dedicated cost spec — there is no
    cost-shaped "deal damage" primitive, and the behaviour is identical: a
    friendly unit always exists (Doctor Pershing itself, a 0/5, is a legal
    target), so the damage is always payable, and it resolves before the draw
    exactly as a cost would.  The controller chooses which friendly unit takes
    the damage (``controller="friendly"``; ``not_self`` is deliberately omitted so
    self-damage is allowed)."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[
            DealDamage(1, TargetSpec(controller="friendly", kind="unit")),
            DrawCards(count=1, player="controller"),
        ],
        title="Deal 1 to a friendly unit, draw a card",
    )


def _remnant_reserves_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 5 for up to 3 units and draw them."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit
    push_deck_search(state, source_ci, count=3, window=5,
                     eligible=lambda cd: isinstance(cd, Unit), up_to=True)
    return state


@card_ability("SHD", "93")
def _remnant_reserves():
    """SHD_93 — Remnant Reserves (Event, Supply): "Search the top 5 cards of your
    deck for up to 3 units, reveal them, and draw them. (Put the other cards on
    the bottom of your deck in a random order.)"

    A thin ``CustomEffect`` adapter onto the existing deck_search seam (the Grand
    Moff Tarkin SOR_84 / This Is The Way SHD_253 pattern): ``count=3, window=5,
    up_to=True`` — 0..3 of the top-5 cards that are units may be taken (drawn),
    and the rest of the window is bottomed in a seeded-random order."""
    return EventAbility(effects=[CustomEffect(fn=_remnant_reserves_search)])


def _gideons_light_cruiser_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: play a Villainy unit costing ≤3 from hand OR discard, for free."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, aspect="Villainy", cost_max=3,
                        free=True, from_discard=True)
    return state


@card_ability("SHD", "242")
def _gideons_light_cruiser():
    """SHD_242 — Gideon's Light Cruiser (Unit, Capital Ship/Imperial/Vehicle):
    Overwhelm.  "When Played: If you control Moff Gideon (as a leader or unit),
    play a [villainy] unit that costs 3 or less from your hand or discard pile
    for free."

    Overwhelm is the keyword engine.  The When Played is a thin ``CustomEffect``
    adapter onto the play-from-hand subsystem, which gained three small additive
    fields for this card: ``aspect="Villainy"`` (only Villainy units offered),
    ``cost_max=3`` (printed cost ≤ 3), ``free=True`` (cost 0) and
    ``from_discard=True`` (candidates drawn from hand *and* discard).  The whole
    trigger is gated by ``CONTROLLER_CONTROLS_NAMED("Moff Gideon")`` — true when
    the controller has Moff Gideon in play as a leader (deployed or undeployed in
    base_zone) or a unit — so the play is offered only when the condition holds.
    Mandatory if able (no decline); fizzles cleanly when no eligible Villainy unit
    is in hand/discard."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_gideons_light_cruiser_when_played)],
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED, "Moff Gideon"),
    )


# ── Combat tricks, buffs & tempo (moff-gideon:04) ─────────────────────────────
# Seven cards.  Three small additive engine seams (all on existing layers, none
# touching the decision/trigger machinery destructively): two new
# push_granted_attack fields (attacker_cost_max / bonus_if_defender_unit), a new
# WhenDealtCombatDamage trigger, and a while_attacking_unit flag on
# ConstantAbility threaded through compute_power.  No escape-hatch on any card.

def _moff_gideon_attack(state, source_ci, target_id, event_ctx):
    """Adapter: attack with a cost-≤3 unit; +1/+0 if it attacks a unit."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1, hp_bonus=0,
                        attacker_cost_max=3, bonus_if_defender_unit=True)
    return state


@card_ability("SHD", "7")
def _moff_gideon():
    """SHD_7 — Moff Gideon (Leader, Imperial/Official, 3/6, Overwhelm).

    Undeployed Action [Exhaust]: "Attack with a unit that costs 3 or less.  If
    it's attacking a unit, it gets +1/+0 for this attack."  A thin CustomEffect
    adapter onto the granted_attack seam, restricting the attacker to printed
    cost ≤ 3 (``attacker_cost_max=3``) and gating the +1/+0 on a unit defender
    (``bonus_if_defender_unit=True``); both new, additive filter fields.

    Deployed side: Overwhelm (the keyword layer — Gideon's printed bar) plus the
    constant "Each friendly unit that costs 3 or less gets +1/+0 and gains
    Overwhelm while attacking an enemy unit."  Modelled as a ConstantAbility over
    friendly cost-≤3 units with ``while_attacking_unit=True``: compute_power gates
    the StatBonus precisely to a unit attack, while the KeywordGrant("Overwhelm")
    it also carries is reported always by the keyword layer — harmless, since
    Overwhelm only matters when attacking a unit.  The constant is active only
    while Gideon is in the arena (deployed), as the constant scan only sees arena
    sources, so it needs no explicit deployed-only flag.

    The Epic Action deploy ("If you control 5 or more resources, deploy this
    leader") is the standard leader-deploy machinery (deploy_threshold) — no
    registration.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_moff_gideon_attack)],
            title="Attack with a unit that costs 3 or less (+1/+0 vs a unit)",
            undeployed_only=True,
            # "Don't offer a no-op": the Exhaust cost is paid up front, so the
            # ability must not be available when there is no ready cost-≤3 unit to
            # attack with (otherwise activating it just exhausts Gideon for
            # nothing — the round-1 self-exhaust bug).  Mirrors the granted
            # attack's own attacker_cost_max=3 filter (the Ozzel SOR_129 /
            # Han SHD_13 don't-offer-a-no-op pattern).
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX, 3),
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", cost_max=3),
            effects=[StatBonus(power=1, hp=0), KeywordGrant("Overwhelm", value=0)],
            while_attacking_unit=True,
        ),
    ]


def _general_tagge_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: give an Experience token to each of up to 3 Trooper units."""
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Experience", max_targets=3,
        controller="any", kind="unit", traits=["Trooper"])
    return state


@card_ability("SHD", "81")
def _general_tagge():
    """SHD_81 — General Tagge (Unit): "When Played: Give an Experience token to
    each of up to 3 Trooper units."

    The "up to 3" multi-pick is the select_token seam (The Armorer SHD_47 / Medal
    Ceremony SOR_245 pattern): the controller picks up to 3 distinct Trooper units,
    each receiving an Experience token, or stops early.  ``controller="any"``
    mirrors the printed text (it omits "friendly"); an Experience token benefits
    the recipient so the controller never picks an enemy.  A thin CustomEffect
    adapter onto the push helper."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_general_tagge_when_played)],
    )


@card_ability("SHD", "82")
def _outland_tie_vanguard():
    """SHD_82 — Outland TIE Vanguard (Unit): "When Played: You may give an
    Experience token to another unit that costs 3 or less."

    An optional WhenPlayed GiveToken targeting another (``not_self``) unit of
    printed cost ≤ 3; ``controller="any"`` mirrors the printed text (it omits
    "friendly"), and an Experience token benefits the recipient so the controller
    never picks an enemy.  With no eligible target the optional trigger
    auto-declines (no prompt)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="any", kind="unit", predicates=("not_self",), cost_max=3))],
        optional=True,
    )


@card_ability("SHD", "83")
def _seasoned_shoretrooper():
    """SHD_83 — Seasoned Shoretrooper (Unit): "While you control 6 or more
    resources, this unit gets +2/+0."

    A self-targeted ConstantAbility gated by CONTROLLER_N_PLUS_RESOURCES(6), read
    passively by compute_power — the +2/+0 winks on/off as the controller's
    resource count crosses 6."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_RESOURCES, 6),
    )


@card_ability("SHD", "84")
def _phase_iii_dark_trooper():
    """SHD_84 — Phase-III Dark Trooper (Unit, Sentinel): "When combat damage is
    dealt to this unit: Give an Experience token to this unit (if it survives the
    damage)."

    Sentinel is the keyword layer.  The combat-damage trigger uses the new
    WhenDealtCombatDamage trigger — fired (from _resolve_unit_combat after defeat
    processing) only for a unit still in play that took combat damage, so the "if
    it survives the damage" clause is intrinsic.  A mandatory self-targeted
    GiveToken (fixed SELF) resolves inline with no decision."""
    return TriggerAbility(
        trigger=WhenDealtCombatDamage(),
        effects=[GiveToken("Experience", TargetSpec(kind="unit", fixed=SELF))],
    )


def _superlaser_technician_when_defeated(state, source_ci, target_id, event_ctx):
    """Put this (now-defeated) unit into play as a ready resource for its owner.

    By the time this optional trigger resolves, _defeat_unit has already placed the
    card in its owner's discard (the relocate-on-defeat fast path applies only to
    inline relocations).  So locate the card, move it from discard into the owner's
    resource zone face-down and ready, and emit CardResourced."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    result = state.find_instance(source_ci.instance_id)
    if result is None:
        return state
    ps, ci = result
    if ci in ps.discard:
        ps.discard.remove(ci)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ci.damage = 0
    ps.resources.append(ci)
    state.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))
    return state


@card_ability("SHD", "85")
def _superlaser_technician():
    """SHD_85 — Superlaser Technician (Unit): "When Defeated: You may put this
    unit into play as a resource and ready it."

    An optional WhenDefeated whose one CustomEffect (no target) moves the just-
    defeated unit from its owner's discard into the resource zone as a ready
    resource.  Because the trigger is optional it defers (AcceptTrigger/
    DeclineTrigger) — by the time it resolves the card sits in discard, so the fn
    simply relocates it (no relocated_by_trigger fast path needed).  The optional
    'you may' is always offered (a non-targeted effect can always do something)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_superlaser_technician_when_defeated)],
        optional=True,
    )


@card_ability("SHD", "113")
def _privateer_crew():
    """SHD_113 — Privateer Crew (Unit, Smuggle [6, Command]): "When played using
    Smuggle: Give 3 Experience tokens to this unit."

    Smuggle is the keyword layer.  The residual is a WhenPlayedViaSmuggle (fires
    only on a Smuggle play) that gives 3 Experience tokens to itself — a mandatory
    self-targeted GiveToken (fixed SELF, count=3) resolving inline."""
    return TriggerAbility(
        trigger=WhenPlayedViaSmuggle(),
        effects=[GiveToken("Experience", TargetSpec(kind="unit", fixed=SELF), count=3)],
    )


# ── Combat tricks, buffs & tempo (moff-gideon:05) ─────────────────────────────
# Four cards, all composing from existing primitives — no new decision kind, no
# trigger/decision-machinery change.  One tiny additive seam: a "ready" predicate
# (the inverse of the existing "exhausted") in resolver._spec_matches_ci, so a
# target can be restricted to a ready (non-exhausted) unit (Kihraxz's "exhaust
# another friendly unit").  No escape-hatch on any card.

def _kihraxz_on_attack(state, source_ci, target_id, event_ctx):
    """If a (ready, friendly, non-self) unit was chosen, exhaust it and give this
    unit +3/+0 for this attack.  Binds the cost (exhaust) and the buff together so
    "If you do" is honoured — declining the optional trigger leaves both undone."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    if unit.exhausted:
        return state  # cannot pay (target should be ready) → no buff
    unit.exhausted = True
    from swu.abilities.resolver import _make_modifier
    mod = _make_modifier(
        state, source_ci.instance_id, source_ci.instance_id,
        power=3, hp=0, duration=Duration.THIS_ATTACK)
    state.modifiers.append(mod)
    return state


@card_ability("SHD", "118")
def _kihraxz_heavy_fighter():
    """SHD_118 — Kihraxz Heavy Fighter (Unit, Overwhelm): "On Attack: You may
    exhaust another friendly unit. If you do, this unit gets +3/+0 for this
    attack."

    Overwhelm is the keyword layer.  The On Attack is an optional trigger (the
    "you may") whose one CustomEffect carries a ``target`` of another (``not_self``)
    ready (the new ``ready`` predicate) friendly unit: choosing one exhausts it and
    applies a +3/+0 this-attack modifier to Kihraxz.  Cost and buff are bound in
    one CustomEffect so "If you do" holds; the optional trigger auto-declines when
    there is no eligible friendly unit to exhaust (``_optional_trigger_has_legal_effect``
    consults the CustomEffect's target).  The +3/+0 lands as a this_attack modifier
    read by compute_power at the damage step."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_kihraxz_on_attack,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self", "ready")),
        )],
    )


def _outflank(state, source_ci, target_id, event_ctx):
    """Adapter: grant two attacks (one at a time)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci)
    push_granted_attack(state, source_ci)
    return state


@card_ability("SHD", "128")
def _outflank_event():
    """SHD_128 — Outflank (Event, Tactic): "Attack with 2 units (one at a time)."

    A thin CustomEffect calling push_granted_attack twice (the Rebel Assault
    SOR_103 pattern): the two granted attacks sit on the LIFO decision stack and
    resolve one at a time.  "2 different units" falls out of exhaustion — the
    first attacker is exhausted by its attack and so is not re-offered for the
    second grant.  Each attack is mandatory-if-able; with fewer than two ready
    units the spare grant(s) fizzle via DeclineGrantedAttack."""
    return EventAbility(effects=[CustomEffect(fn=_outflank)])


@card_ability("SHD", "130")
def _moment_of_glory():
    """SHD_130 — Moment of Glory (Event, Tactic): "Give a unit +4/+4 for this
    phase."

    A plain EventAbility with a single ModifyStats(+4/+4, this phase) targeting any
    unit (the controller chooses; ``controller="any"`` mirrors the printed text,
    and the buff benefits the recipient so it is pointed at a friendly unit).
    Fizzles harmlessly if no unit is in play."""
    return EventAbility(effects=[
        ModifyStats(power=4, hp=4,
                    target=TargetSpec(controller="any", kind="unit"),
                    duration=Duration.THIS_PHASE),
    ])


def _snowtrooper_lieutenant_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: may attack with a unit; +2/+0 to it only if it is Imperial."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                        optional=True, bonus_trait="Imperial")
    return state


@card_ability("SHD", "236")
def _snowtrooper_lieutenant():
    """SHD_236 — Snowtrooper Lieutenant (Unit, Imperial/Trooper): "When Played:
    You may attack with a unit. If it's an Imperial unit, it gets +2/+0 for this
    attack."

    A thin CustomEffect adapter onto the granted_attack seam: ``optional=True`` for
    the "you may" (a DeclineGrantedAttack is always offered), and ``bonus_trait=
    "Imperial"`` so the +2/+0 applies only when the chosen attacker is an Imperial
    unit (the Fleet Lieutenant conditional-bonus pattern).  The "ready friendly
    unit" restriction in the reminder text is intrinsic to push_granted_attack's
    attack enumeration."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_snowtrooper_lieutenant_when_played)],
    )


@card_ability("SHD", "234")
def _incinerator_trooper():
    """SHD_234 — Incinerator Trooper (Unit, Imperial/Trooper): "While attacking,
    this unit deals combat damage before the defender. (If the defender is
    defeated, it deals no combat damage.)"

    This is exactly First Strike (cf. Han Solo SOR_198's innate First Strike).
    Modelled as a constant self-grant of the First Strike keyword; the combat
    pipeline (``_resolve_unit_combat_step2``) consults ``has_keyword(attacker,
    FIRST_STRIKE)`` only when this unit is the attacker, dealing its damage first
    and skipping the defender's return damage if the defender is defeated."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("First Strike", value=0)],
    )


# ── qui-gon-jinn:03 — Combat tricks, buffs & tempo (SHD card in an LOF deck) ───

@card_ability("SHD", "96")
def _maz_kanata_shd_96():
    """SHD_96 — Maz Kanata (Unit, Underworld, 1/1): "When you play another unit:
    Give an Experience token to this unit."

    A ``WhenYouPlayCard(card_type="unit")`` trigger (``exclude_self=True`` by
    default → "another unit") giving Maz herself an Experience token each time the
    controller plays another unit.  The grant is a self-targeted ``GiveToken``
    (mandatory, fixed=SELF → resolves inline)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit"),
        effects=[GiveToken("Experience", TargetSpec(fixed=SELF))],
    )


# ── Reprint-duplicate encode (Stage 4 of docs/reprint_duplicates_plan.md) ─────

@card_ability("SHD", "37")
def _supreme_leader_snoke():
    """SHD_37 — Supreme Leader Snoke (Unit, 6/6): "Each enemy non-leader unit
    gets -2/-2."

    A self-standing ``ConstantAbility`` debuffing every enemy non-leader unit
    (the Red Three SOR_144 / Lando Calrissian LAW_108 negative-StatBonus
    pattern), read passively by ``compute_power``/``compute_hp``.  ``controller=
    "enemy"`` resolves relative to Snoke's controller; ``non_leader`` excludes a
    deployed enemy leader-unit."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader",)),
        effects=[StatBonus(power=-2, hp=-2)],
    )


# ── Reprint sweep Stage 4 Batch 2 (canonical encode) ─────────────────────────

def _street_gang_recruiter_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: return one Underworld card from discard to hand (up to 1)."""
    from swu.engine.actions import push_return_from_discard

    def eligible(cd):
        return "Underworld" in (getattr(cd, "traits", None) or ())

    push_return_from_discard(state, source_ci, count=1, eligible=eligible)
    return state


@card_ability("SHD", "260")
def _street_gang_recruiter():
    """SHD_260 — Street Gang Recruiter (Unit, Underworld): "When Played: You may
    return an Underworld card from your discard pile to your hand."

    A thin ``WhenPlayed`` CustomEffect adapter onto the return_from_discard seam
    (``push_return_from_discard``, the Razor Crest SHD_44 / Tranquility TWI_246
    pattern): the controller may take up to one Underworld card (any type) from
    their discard pile back to hand, or finish without taking one (the "you may").
    The decision is only pushed when an Underworld card is present in the discard
    pile."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_street_gang_recruiter_when_played)],
    )


def _mandalorian_shd49(state, source_ci, target_id, event_ctx):
    """Heal ALL damage from the chosen unit and give it 2 Shield tokens (bound in
    one effect, both landing on the same cost≤2 unit)."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    unit.damage = 0
    from swu.engine.tokens import attach_token
    owner_ps = state.player_by_id(source_ci.owner_id)
    attach_token(state, owner_ps, unit, "Shield")
    attach_token(state, owner_ps, unit, "Shield")
    return state


@card_ability("SHD", "49")
def _the_mandalorian_shd49():
    """SHD_49 — The Mandalorian (5/6, Sentinel): "When Played: You may heal all
    damage from a unit that costs 2 or less and give 2 Shield tokens to it."

    Sentinel is the keyword layer.  An optional ``WhenPlayed`` whose one
    ``CustomEffect.target`` (a unit that costs 2 or less, ``controller="any"``
    mirroring the printed "a unit" — the recipient benefits, so the controller
    picks a friendly one) zeroes the chosen unit's damage and attaches two Shield
    tokens, bound together so both land on the same unit.  Auto-declines with no
    cost≤2 unit on the board."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_mandalorian_shd49,
            target=TargetSpec(controller="any", kind="unit", cost_max=2))],
        optional=True,
    )


# ── Reprint-sweep batch (2026-07-09) ─────────────────────────────────────────

def _take_captive_choose_captor(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly captor + its arena into the shared event_ctx
    (the Haymaker LAW_168 two-dependent-effects pattern)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _, ci = res
    event_ctx["captor_id"] = target_id
    event_ctx["same_arena"] = "space" if ci.zone == Zone.SPACE_ARENA else "ground"
    return state


def _take_captive_capture(state, source_ci, target_id, event_ctx):
    """Capture the chosen enemy unit under the recorded captor."""
    captor = event_ctx.get("captor_id")
    if captor is None or target_id is None:
        return state
    from swu.engine.actions import _apply_capture
    _apply_capture(state, captor, target_id)
    return state


@card_ability("SHD", "131")
def _take_captive_shd131():
    """SHD_131 — Take Captive (Event, Command/Tactic): "A friendly unit captures an
    enemy non-leader unit in the same arena."

    Two dependent ``CustomEffect.target``s sharing the resolve_effects ``event_ctx``
    (the Haymaker LAW_168 / Nothing Left to Fear LAW_41 pattern): the first picks a
    friendly captor and records its arena; the second picks an enemy non-leader unit
    in that same arena (the existing ``same_arena_as_event`` predicate) and captures
    it via the existing capture primitive (``actions._apply_capture``,
    the-mandalorian:07).  Mandatory-if-able; no friendly captor ⇒ nothing, no
    same-arena enemy ⇒ the capture fizzles."""
    return EventAbility(effects=[
        CustomEffect(fn=_take_captive_choose_captor,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_take_captive_capture,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader", "same_arena_as_event"))),
    ])


def _kylo_ren_shd141_on_attack(state, source_ci, target_id, event_ctx):
    """Give the chosen unit +2/+0 this phase; if it is a non-Villainy unit, also
    give it an Experience token."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.abilities.resolver import _make_modifier
    _, ci = res
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=2, hp=0, duration=Duration.THIS_PHASE))
    if "Villainy" not in ci.card_def.aspect_names:
        from swu.engine.tokens import attach_token
        attach_token(state, state.player_by_id(ci.owner_id), ci, "Experience")
    return state


@card_ability("SHD", "141")
def _kylo_ren_shd141():
    """SHD_141 — Kylo Ren (6/6 Villainy): "On Attack: Give a unit +2/+0 for this
    phase.  If it's a non-Villainy unit, also give an Experience token to it."

    A mandatory ``OnAttack`` whose one ``CustomEffect.target`` (any unit) applies a
    +2/+0 this-phase modifier and, when the target carries no Villainy aspect, an
    Experience token — bound in one effect so the conditional token keys off the
    same chosen unit (the Zeb Orellios LAW_45 conditional-payoff pattern).
    RESIDUAL (deferred): "While playing this unit, ignore his Villainy aspect
    penalty if you control Rey" — a play-cost waiver on the normal PlayCard path
    (the same deferred cost-residual class as The Darksaber SHD_126); the card is
    fully playable without it."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(
            fn=_kylo_ren_shd141_on_attack,
            target=TargetSpec(controller="any", kind="unit"))],
    )


def _rey_shd46_on_attack(state, source_ci, target_id, event_ctx):
    """Heal 2 from the chosen unit; if it is a non-Heroism unit, give it a Shield."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    ci.damage = max(0, ci.damage - 2)
    if "Heroism" not in ci.card_def.aspect_names:
        from swu.engine.tokens import attach_token
        attach_token(state, state.player_by_id(ci.owner_id), ci, "Shield")
    return state


@card_ability("SHD", "46")
def _rey_shd46():
    """SHD_46 — Rey (5-cost Heroism): "On Attack: You may heal 2 damage from a unit.
    If it's a non-Heroism unit, give a Shield token to it."

    An optional ``OnAttack`` whose one ``CustomEffect.target`` (any unit) heals 2
    and, when the target carries no Heroism aspect, gives it a Shield — bound in one
    effect (the Kylo Ren SHD_141 mirror).  RESIDUAL (deferred): "ignore her Heroism
    aspect penalty if you control Kylo Ren" — the same deferred play-cost-waiver
    class as Kylo Ren SHD_141."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_rey_shd46_on_attack,
            target=TargetSpec(controller="any", kind="unit"))],
    )


def _maul_shd90_redirect(state, source_ci, target_id, event_ctx):
    """Maul SHD_90 On Attack redirect: mark the chosen friendly Underworld unit as
    the sink for all combat damage that would be dealt to Maul during this attack.
    Read at the combat-damage step (actions._apply_attacker_combat_damage) and
    cleared at the end of the attack — a this_attack scope."""
    if target_id:
        source_ci.combat_damage_redirect_to = target_id
    return state


@card_ability("SHD", "90")
def _maul_shd90():
    """SHD_90 — Maul (7-cost 7/6 Ground, Force/Underworld; Ambush, Overwhelm =
    keyword layer): "On Attack: You may choose another friendly Underworld unit. If
    you do, all combat damage that would be dealt to this unit during this attack is
    dealt to the chosen unit instead."

    A stock optional ``OnAttack`` ``CustomEffect.target`` (the "you may choose"):
    the fn records the chosen unit's id on Maul's ``combat_damage_redirect_to`` flag,
    which the combat step reads to redirect Maul's incoming combat damage onto the
    chosen unit (its own Shield may intercept it); Maul still deals his own damage +
    Overwhelm to the defender.  ``not_self`` excludes Maul ("another"); the optional
    trigger auto-declines when no other friendly Underworld unit is in play."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_maul_shd90_redirect,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Underworld",), predicates=("not_self",)))],
    )


# ── shd-set:01 — Direct damage & removal (leaders + Synara San) ───────────────
# Each leader's Epic Action deploy uses the standard deploy_threshold machinery
# (no registration needed).  This group registers the card-specific ability sides
# (text = undeployed, deploy_box = deployed).  Bossk (SHD_10) and Lando (SHD_17)
# were the two framework-session cards of this group; both are now landed with new
# engine seams:
#   * Bossk's deployed "When you collect a bounty: collect that bounty again" uses
#     the new WhenBountyCollected observer (registry) fired from the
#     bounties-collected ledger drained at the settle-point (actions
#     _fire_bounty_observers) — recorded whenever an is_bounty WhenDefeated ability is
#     collected (resolver.fire_triggered_abilities).  The re-collection re-runs that
#     exact bounty via a fresh resolve_effects decision (actions.push_bounty_recollect),
#     so it needs no new decision kind; the once-per-round is the
#     SOURCE_BOUNTY_RECOLLECT_AVAILABLE gate.
#   * Lando's "Play a card using Smuggle. It costs 2 less. Defeat a resource you own"
#     uses the new play_via_smuggle decision (the Smuggle sibling of Bib Fortuna
#     SOR_177's play_event_from_hand): actions.push_play_via_smuggle / PlayViaSmuggle
#     reuse the SmugglePlay mechanics at a discount without handing the turn over,
#     then auto-defeat one owned resource (fungible).


def _qira_dmg_shield(state, source_ci, target_id, event_ctx):
    """Qi'ra undeployed action: deal 2 to the chosen friendly unit, THEN give it a
    Shield token.  Same target ("it") — threaded in via the CustomEffect.target
    seam.  The shield only lands if the unit survives the 2 damage."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.tokens import attach_token
    if target_id is None:
        return state
    state = _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)
    result = state.find_instance(target_id)
    if result is not None:
        host_ps, host_ci = result
        if host_ci in host_ps.ground_arena or host_ci in host_ps.space_arena:
            attach_token(state, host_ps, host_ci, "Shield")
    return state


def _qira_when_deployed(state, source_ci, target_id, event_ctx):
    """Qi'ra When Deployed: heal all damage from EACH unit (both players), then
    deal each unit damage equal to half its remaining HP rounded down.  Remaining
    HP is read AFTER the heal (= full HP), so the amounts are snapshotted from the
    healed board before any damage is dealt (the deals are simultaneous per the
    printed 'each unit')."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import compute_hp
    units = []
    for ps in state.players:
        units.extend(ps.ground_arena)
        units.extend(ps.space_arena)
    for ci in units:
        ci.damage = 0                       # heal all damage from each unit
    plan = [(ci.instance_id, compute_hp(state, ci) // 2) for ci in units]
    for iid, amount in plan:
        if amount > 0:
            state = _apply_deal_damage(state, iid, amount,
                                       source_ci.card_def.display_name)
    return state


@card_ability("SHD", "2")
def _qira():
    """SHD_2 — Qi'ra (Leader, Underworld; Grit on the deployed side handled by the
    keyword engine).

    Undeployed: "Action [1 resource, Exhaust]: Deal 2 damage to a friendly unit.
        Then, give a Shield token to it."  A CustomEffect.target (a friendly unit)
        deals 2 then shields the same unit (Thin CustomEffect adapter, same-target).
    Deployed: "When Deployed: Heal all damage from each unit. Then, deal damage to
        each unit equal to half its remaining HP, rounded down."  A no-target
        CustomEffect on the WhenDeployed trigger (heal-all → snapshot half-HP →
        deal), pop-then-deal-safe since it pushes no decision.
    Epic Action deploy at 5+ resources = standard deploy_threshold machinery."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(
                fn=_qira_dmg_shield,
                target=TargetSpec(controller="friendly", kind="unit"))],
            title="Deal 2 to a friendly unit, then Shield it",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_qira_when_deployed)],
            deployed_only=True,
        ),
    ]


def _finn_defeat_upgrade_shield(state, source_ci, target_id, event_ctx):
    """Finn: defeat the chosen friendly upgrade, then ('if you do') give a Shield
    token to the unit it was on.  The host is captured BEFORE the defeat detaches
    the upgrade."""
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.tokens import attach_token
    if target_id is None:
        return state
    host_ps = host_ci = None
    for ps in state.players:
        for unit in ps.ground_arena + ps.space_arena:
            if any(u.instance_id == target_id for u in unit.attached_upgrades):
                host_ps, host_ci = ps, unit
                break
        if host_ci is not None:
            break
    state = _apply_defeat_unit(state, target_id)
    if host_ci is not None and (host_ci in host_ps.ground_arena
                                or host_ci in host_ps.space_arena):
        attach_token(state, host_ps, host_ci, "Shield")
    return state


@card_ability("SHD", "3")
def _finn():
    """SHD_3 — Finn (Leader, Fringe/Trooper).

    Undeployed: "Action [Exhaust]: Defeat a friendly upgrade on a unit. If you do,
        give a Shield token to that unit."
    Deployed:   "On Attack: You may defeat a friendly upgrade on a unit. If you do,
        give a Shield token to that unit."
    Both sides are the same CustomEffect.target over a friendly upgrade (the "if you
    do" cost+payoff kept atomic in one fn): capture the host, defeat the upgrade,
    shield the host.  The undeployed side is an ExhaustSelf activated ability; the
    deployed side is an optional On Attack trigger (auto-declines with no friendly
    upgrade to defeat).  Epic Action deploy at 5+ resources = standard machinery."""
    upgrade_spec = TargetSpec(controller="friendly", kind="upgrade")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_finn_defeat_upgrade_shield, target=upgrade_spec)],
            title="Defeat a friendly upgrade, then Shield its unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[CustomEffect(fn=_finn_defeat_upgrade_shield, target=upgrade_spec)],
            deployed_only=True,
        ),
    ]


@card_ability("SHD", "12")
def _bo_katan_kryze():
    """SHD_12 — Bo-Katan Kryze (Leader, Mandalorian).

    Undeployed: "Action [Exhaust]: If you attacked with a Mandalorian unit this
        phase, deal 1 damage to a unit."  ExhaustSelf activated ability gated by the
        new CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE("Mandalorian") condition
        (don't-offer-a-no-op — the cost isn't wasted when no Mandalorian attacked).
    Deployed: "On Attack: You may deal 1 damage to a unit. If you attacked with
        another Mandalorian unit this phase, you may deal 1 damage to a unit."  Two
        separate optional On Attack abilities — the first unconditional, the second
        gated by the SAME condition (which excludes the source, so 'another
        Mandalorian' falls out for free even though Bo-Katan is herself Mandalorian
        and the current attacker).  Registering each clause as its own single-effect
        ability sidesteps the resolve_effects skip-earlier wart.
    Epic Action deploy at 6+ resources = standard deploy_threshold machinery."""
    mando_attacked = ConditionCheck(
        Condition.CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE, "Mandalorian")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            title="Deal 1 damage to a unit",
            undeployed_only=True,
            condition=mando_attacked,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            deployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            deployed_only=True,
            condition=mando_attacked,
        ),
    ]


def _cad_bane_undeployed(state, source_ci, target_id, event_ctx):
    """Cad Bane undeployed: exhaust this leader (the 'if you do' cost), then an
    opponent chooses a unit they control and it is dealt 1 damage."""
    from swu.engine.actions import push_opponent_chooses_target
    source_ci.exhausted = True
    push_opponent_chooses_target(state, source_ci, amount=1, units_only=True)
    return state


def _cad_bane_deployed(state, source_ci, target_id, event_ctx):
    """Cad Bane deployed: an opponent chooses a unit they control; deal 2 to it."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(state, source_ci, amount=2, units_only=True)
    return state


@card_ability("SHD", "14")
def _cad_bane():
    """SHD_14 — Cad Bane (Leader, Bounty Hunter/Underworld; Raid 2 keyword engine).

    Undeployed: "When you play an Underworld card: You may exhaust this leader. If
        you do, an opponent chooses a unit they control. Deal 1 damage to it."  An
        optional WhenYouPlayCard(trait='Underworld') gated by SOURCE_READY (the
        exhaust cost is only payable while ready); on accept the fn exhausts the
        leader and pushes the opponent_chooses_target damage decision (Grey Squadron
        Y-Wing SHD_246 seam), amount 1, units_only.
    Deployed: "When you play an Underworld card: You may choose an opponent. They
        choose a unit they control. Deal 2 damage to it. Use this ability only once
        each round."  Same optional trigger, amount 2, no self-exhaust.
        DEVIATION: the once-each-round limiter is dropped (TriggerAbility has no
        once-per-round field and adding one touches the trigger machinery — the
        Cassian SHD_148 precedent); only relevant if Cad Bane plays 2+ Underworld
        cards while deployed in one round.
    Epic Action deploy at 6+ resources = standard deploy_threshold machinery.

    (The opponent_chooses_target 'damage' disposition offers the controller a
    confirm/decline stage; Cad Bane's deal is mandatory once the opponent chooses,
    but optimal play always confirms, so the superset is behaviourally faithful.)"""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(trait="Underworld"),
            optional=True,
            effects=[CustomEffect(fn=_cad_bane_undeployed)],
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(trait="Underworld"),
            optional=True,
            effects=[CustomEffect(fn=_cad_bane_deployed)],
            deployed_only=True,
        ),
    ]


def _bossk_recollect(state, source_ci, target_id, event_ctx):
    """Bossk deployed payoff: "collect that bounty again" — re-run the just-collected
    bounty for its collector (this leader's controller).  Delegates to
    ``actions.push_bounty_recollect``, which pushes a fresh resolve_effects for the
    recorded bounty and marks the once-per-round spent."""
    from swu.engine.actions import push_bounty_recollect
    push_bounty_recollect(state, source_ci, event_ctx)
    return state


@card_ability("SHD", "10")
def _bossk():
    """SHD_10 — Bossk (Leader, Bounty Hunter/Underworld).

    Undeployed: "Action [Exhaust]: Deal 1 damage to a unit with a Bounty. You may give
        it +1/+0 for this phase."  An ExhaustSelf activated ability that deals 1 to a
        unit currently carrying a Bounty (the new ``has_bounty`` target predicate).
        DEVIATION: the optional "+1/+0 for this phase" rider is dropped — a situational
        "may" buff (buffing a bounty unit, usually an enemy, is rarely wanted), the
        Cad Bane SHD_14 once-per-round precedent for dropping a minor optional rider.
    Deployed: "When you collect a bounty: You may collect that bounty again. Use this
        ability only once each round."  An optional WhenBountyCollected observer (the
        new bounty-collection seam), gated by SOURCE_BOUNTY_RECOLLECT_AVAILABLE so the
        "you may" is offered at most once per round; on accept it re-runs the bounty.
    Epic Action deploy at 5+ resources = standard deploy_threshold machinery."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                              predicates=("has_bounty",)))],
            title="Deal 1 damage to a unit with a Bounty",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenBountyCollected(),
            optional=True,
            effects=[CustomEffect(fn=_bossk_recollect)],
            deployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_BOUNTY_RECOLLECT_AVAILABLE),
        ),
    ]


def _lando_smuggle(state, source_ci, target_id, event_ctx):
    """Lando: play a card using Smuggle for 2 resources less, then defeat a resource
    you own (the play_via_smuggle seam; the defeat is auto-selected, resources being
    fungible face-down cards)."""
    from swu.engine.actions import push_play_via_smuggle
    push_play_via_smuggle(state, source_ci, cost_reduction=2,
                          then_defeat_own_resource=True)
    return state


@card_ability("SHD", "17")
def _lando_calrissian():
    """SHD_17 — Lando Calrissian (Leader, Underworld).

    Undeployed: "Action [Exhaust]: Play a card using Smuggle. It costs 2 resources
        less. Defeat a resource you own and control."  An ExhaustSelf activated ability
        pushing the new play_via_smuggle decision (cost_reduction 2, then defeat a
        resource).
    Deployed: same effect as a no-cost once-per-round Action (no Exhaust).
    Both sides are gated by CONTROLLER_CAN_SMUGGLE (param 2) so the ability is not
    offered — and its Exhaust / once-per-round not wasted — when nothing is
    smuggle-playable.  Epic Action deploy at 4+ resources = standard machinery."""
    can_smuggle = ConditionCheck(Condition.CONTROLLER_CAN_SMUGGLE, 2)
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_lando_smuggle)],
            title="Play a card using Smuggle (2 less), then defeat a resource",
            undeployed_only=True,
            condition=can_smuggle,
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_lando_smuggle)],
            title="Play a card using Smuggle (2 less), then defeat a resource",
            deployed_only=True,
            once_per_round=True,
            condition=can_smuggle,
        ),
    ]


@card_ability("SHD", "33")
def _synara_san():
    """SHD_33 — Synara San (Unit, Underworld; Grit handled by the keyword engine).

    "While this unit is exhausted, she gains, 'Bounty — Deal 5 damage to a base.'"
    The exact mirror of Unlicensed Headhunter SHD_165 (conditional bounty): a
    WhenDefeated trigger gated by SOURCE_EXHAUSTED (the bounty exists only while
    exhausted, evaluated at the moment of defeat), written from the dying unit's
    OWNER perspective so 'your opponent collects it' resolves for the collector —
    the collector deals 5 to their opponent's (= the owner's, 'friendly') base.
    EACH_FRIENDLY resolves the owner's single base inline, no prompt."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        condition=ConditionCheck(Condition.SOURCE_EXHAUSTED),
        effects=[DealDamage(5, TargetSpec(controller="friendly", kind="base",
                                          fixed=EACH_FRIENDLY))],
        is_bounty=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _rose_tico_shield_to_xp(state, source_ci, target_id, event_ctx):
    """Defeat one Shield token on the chosen friendly unit; if one was removed,
    give 2 Experience tokens to that same unit ("if you do" binding)."""
    from swu.engine import tokens
    if not target_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    if tokens.defeat_shield(state, ci):
        owner_ps = state.player_by_id(ci.owner_id)
        tokens.attach_token(state, owner_ps, ci, "Experience")
        tokens.attach_token(state, owner_ps, ci, "Experience")
    return state


@card_ability("SHD", "45")
def _rose_tico():
    """SHD_45 — Rose Tico (Shielded handled by the keyword engine).
    "On Attack: You may defeat a Shield token on a friendly unit.  If you do,
    give 2 Experience tokens to that unit."

    One optional CustomEffect targeting a friendly unit that carries a Shield
    token (``has_shield_token`` predicate).  The fn removes one Shield and, if it
    did, gives 2 Experience tokens to the same unit — the cost/payoff kept atomic
    in a single effect ("if you do" binding)."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_rose_tico_shield_to_xp,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("has_shield_token",)),
        )],
    )


@card_ability("SHD", "50")
def _chewbacca_shd50():
    """SHD_50 — Chewbacca (Grit + Smuggle handled by the keyword engine).
    "When Played: You may defeat a unit with 5 or less remaining HP." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       hp_remaining_max=5))],
    )


def _val_bounty(state, source_ci, target_id, event_ctx):
    """Bounty — the collector deals 3 damage to a unit of their choice."""
    from swu.engine.actions import push_select_damage
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    push_select_damage(state, source_ci, amount_each=3, max_targets=1,
                       decider_id=collector,
                       after_resolve_idx=state.active_player_index)
    return state


@card_ability("SHD", "58")
def _val():
    """SHD_58 — Val (Underworld).
    "Bounty — Deal 3 damage to a unit.
     When Defeated: Give 2 Experience tokens to a friendly unit."

    Two WhenDefeated abilities (the active player orders them).  The Bounty is an
    ``is_bounty`` trigger resolving for the COLLECTOR, who picks the unit to take
    3 damage (collector-addressed ``select_damage``).  The separate When Defeated
    resolves for Val's OWNER, giving 2 Experience tokens to one of their units."""
    return [
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_val_bounty)],
            is_bounty=True,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[GiveToken("Experience",
                               TargetSpec(controller="friendly", kind="unit"),
                               count=2)],
        ),
    ]


@card_ability("SHD", "79")
def _rivals_fall():
    """SHD_79 — Rival's Fall (Event, Tactic): "Defeat a unit." """
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("SHD", "80")
def _salacious_crumb_shd80():
    """SHD_80 — Salacious Crumb (Creature, Underworld).
    "When Played: Heal 1 damage from your base.
     Action [Exhaust, return this unit to his owner's hand]: Deal 1 damage to a
     ground unit."

    The Action's "return this unit to hand" is folded into the effect list (bounce
    self, then deal 1 to a ground unit) with ExhaustSelf as the paid cost; the
    damage still resolves after the source leaves play (its chosen target is
    independent)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[
                DealDamage(1, TargetSpec(controller="any", kind="unit",
                                         arena="ground")),
                ReturnToHand(TargetSpec(kind="unit", fixed=SELF)),
            ],
            title="Return to hand: deal 1 to a ground unit",
        ),
    ]


@card_ability("SHD", "91")
def _jabbas_rancor():
    """SHD_91 — Jabba's Rancor (Creature, Underworld, 9/9).
    "If you control Jabba the Hutt (as a leader or unit), this unit costs 1
     resource less to play.
     When Played/On Attack: Deal 3 damage to another friendly ground unit and 3
     damage to an enemy ground unit."

    A ``CostReduction`` gated by ``CONTROLLER_CONTROLS_NAMED("Jabba the Hutt")``
    (which counts the leader deployed or undeployed, or a unit).  The
    When Played and On Attack effects are identical: 3 to another friendly ground
    unit (``not_self``) and 3 to an enemy ground unit — both mandatory."""
    reduction = CostReduction(
        amount=1,
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                 param="Jabba the Hutt"),
    )
    dmg = [
        DealDamage(3, TargetSpec(controller="friendly", kind="unit",
                                 arena="ground", predicates=("not_self",))),
        DealDamage(3, TargetSpec(controller="enemy", kind="unit", arena="ground")),
    ]
    return [
        reduction,
        TriggerAbility(trigger=WhenPlayed(), effects=list(dmg)),
        TriggerAbility(trigger=OnAttack(), effects=list(dmg)),
    ]


def _enterprising_lackeys_reprocess(state, source_ci, target_id, event_ctx):
    """Defeat one friendly resource, then put this unit into play as a face-down
    ready resource.

    This is an *optional* WhenDefeated, so it resolves as a decision — by which
    time ``_defeat_unit`` has already homed the unit in its owner's discard (the
    inline limbo-relocation of Stolen Landspeeder SHD_161 does not apply).  The fn
    therefore pulls the unit out of wherever it currently sits (its discard) and
    moves it into the resource row."""
    from swu.engine.state import Zone
    from swu.engine.events import UnitDefeated, CardResourced
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.resources:
        return state  # "may defeat a friendly resource" — nothing to pay
    # Resources are fungible: defeat the first one (deterministic, no prompt).
    res = ps.resources.pop(0)
    res.zone = Zone.DISCARD
    res.face_down = False
    res.exhausted = False
    ps.discard.append(res)
    state.event_log.append(UnitDefeated(
        player_id=ps.player_id, instance_id=res.instance_id,
        card_name=res.card_def.display_name,
    ))
    # Locate the defeated unit (in its owner's discard by now) and move it into
    # play as a ready resource.
    ci = source_ci
    owner = state.player_by_id(ci.owner_id)
    for pile in (owner.discard, owner.ground_arena, owner.space_arena):
        if ci in pile:
            pile.remove(ci)
            break
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ci.damage = 0
    for u in list(ci.attached_upgrades):
        ci.attached_upgrades.remove(u)
    owner.resources.append(ci)
    state.modifiers = [m for m in state.modifiers
                       if m.target_instance_id != ci.instance_id]
    state.event_log.append(CardResourced(
        player_id=owner.player_id, instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))
    return state


@card_ability("SHD", "107")
def _enterprising_lackeys():
    """SHD_107 — Enterprising Lackeys (Underworld; Smuggle handled by the engine).
    "When Defeated: You may defeat a friendly resource.  If you do, put this unit
     into play as a resource."

    Optional WhenDefeated: if accepted (and the controller has a resource to pay),
    a friendly resource is defeated and the dying unit is moved from its discard
    into play as a ready resource.  Resources are fungible, so no which-resource
    prompt."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[CustomEffect(fn=_enterprising_lackeys_reprocess)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:03 — Direct damage & removal
#
# The two escalation cards were landed in a dedicated FRAMEWORK session — each got
# a new self-contained engine seam (registered in all the usual places):
#   * SHD_142 Pre Vizsla → the 'pay_and_steal_upgrade' decision kind
#     (actions.push_pay_and_steal_upgrade): pay an upgrade's printed cost, take
#     control of it onto this unit (relocation, not a play), else defeat it.
#   * SHD_144 Give In to Your Anger → the forced-attack COMPULSION
#     (game_memory.forced_attack + actions._forced_attack_actions): the damaged
#     unit's controller's next action this phase is constrained to that unit's
#     attack (a unit target if able).
# ══════════════════════════════════════════════════════════════════════════════

def _pre_vizsla_steal(state, source_ci, target_id, event_ctx):
    """Push the pay-and-steal-an-upgrade decision for Pre Vizsla (SHD_142)."""
    from swu.engine.actions import push_pay_and_steal_upgrade
    push_pay_and_steal_upgrade(state, source_ci)
    return state


@card_ability("SHD", "142")
def _pre_vizsla():
    """SHD_142 — Pre Vizsla (Unit; Mandalorian, Trooper, 8/7).
    "When Played/On Attack: You may pay the cost of an upgrade attached to another
    non-Vehicle unit. If you do, take control of that upgrade and attach it to this
    unit, if able. If it can't attach to this unit, defeat it instead."

    Both triggers are thin CustomEffect adapters onto the new self-contained
    'pay_and_steal_upgrade' decision kind (actions.push_pay_and_steal_upgrade): the
    controller may pay a steal-eligible upgrade's printed cost, then RELOCATE it
    onto Pre Vizsla ("take control" is implicit — control follows the host) or, when
    its "Attach to …" restriction bars Pre Vizsla, DEFEAT it.  The "you may" is the
    DeclineStealUpgrade option; the decision is only pushed when at least one
    affordable candidate exists (so it is never offered when it could do nothing)."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_pre_vizsla_steal)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_pre_vizsla_steal)]),
    ]


def _give_in_to_your_anger(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen enemy unit, then COMPEL its controller's next action
    this phase to be an attack with that unit (a unit target if able)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       source_id=source_ci.instance_id)
    # Only a surviving unit can be compelled (1 damage may have defeated it).
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, ci = result
    from swu.engine.state import Zone
    if ci.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        state.game_memory.forced_attack = {
            "player_id": ps.player_id, "unit_id": ci.instance_id}
    return state


@card_ability("SHD", "144")
def _give_in_to_your_anger_card():
    """SHD_144 — Give In to Your Anger (Event; Innate).
    "Deal 1 damage to an enemy unit. Its controller's next action this phase must be
    an attack action with that unit, if able. It must attack a unit, if able."

    A CustomEffect.target picks the enemy unit, deals 1, then arms the forced-attack
    COMPULSION (game_memory.forced_attack).  The compulsion is enforced at the
    ACTION-phase legal-action seam (actions._forced_attack_actions): while the
    flagged player is active and their unit is able, their legal actions are
    restricted to that unit's attacks (a unit target if any, else base); if the unit
    can't attack the compulsion is vacuous.  It is consumed by the flagged player's
    next action (actions.apply) and cleared at the phase rollover."""
    return EventAbility(effects=[
        CustomEffect(fn=_give_in_to_your_anger,
                     target=TargetSpec(controller="enemy", kind="unit")),
    ])


def _scanning_officer(state, source_ci, target_id, event_ctx):
    """Reveal 3 enemy resources; defeat each that has the Smuggle keyword, and for
    each defeated, its controller puts the top of their deck into play as a
    resource.  Resources are face-down but their card_def keywords are known;
    "reveal 3" is modelled as the first up-to-3 enemy resources (deterministic —
    the controller cannot see face-down Smuggle status, so which 3 is arbitrary)."""
    from swu.engine.state import Zone
    from swu.engine.events import UnitDefeated
    from swu.engine.actions import _resource_top_of_deck
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    for res in list(opp.resources[:3]):
        if "Smuggle" not in (getattr(res.card_def, "keywords", ()) or ()):
            continue
        opp.resources.remove(res)
        res.zone = Zone.DISCARD
        res.face_down = False
        res.exhausted = False
        opp.discard.append(res)
        state.event_log.append(UnitDefeated(
            player_id=opp.player_id, instance_id=res.instance_id,
            card_name=res.card_def.display_name,
        ))
        _resource_top_of_deck(state, opp)  # its controller ramps
    return state


@card_ability("SHD", "114")
def _scanning_officer_card():
    """SHD_114 — Scanning Officer (Imperial, Official; Smuggle handled engine-side).
    "When Played: Reveal 3 enemy resources.  Defeat each resource with the Smuggle
    keyword revealed this way.  For each resource defeated this way, its controller
    puts the top card of their deck into play as a resource." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_scanning_officer)],
    )


def _dengar_upgrade_damage(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the unit the just-played upgrade was attached to."""
    from swu.abilities.resolver import _cards_in_play, _apply_deal_damage
    played_id = event_ctx.get("played_card_id")
    if not played_id:
        return state
    host = next((u for u in _cards_in_play(state)
                 if any(up.instance_id == played_id for up in u.attached_upgrades)),
                None)
    if host is None:
        return state
    _apply_deal_damage(state, host.instance_id, 1,
                       source_name=source_ci.card_def.display_name)
    return state


@card_ability("SHD", "133")
def _dengar():
    """SHD_133 — Dengar (Bounty Hunter, Underworld).
    "When you play an upgrade on a unit: You may deal 1 damage to that unit."

    An optional ``WhenYouPlayCard(card_type="upgrade")`` observer; its no-target
    CustomEffect locates the played upgrade's host (via the ``played_card_id``
    threaded into the CardPlayed observer fire) and deals 1 damage to it."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="upgrade"),
        optional=True,
        effects=[CustomEffect(fn=_dengar_upgrade_damage)],
    )


@card_ability("SHD", "139")
def _krrsantan():
    """SHD_139 — Krrsantan (Bounty Hunter, Underworld, Wookiee).
    "When Played: If an enemy unit has a Bounty, you may ready this unit.
     On Attack: Choose a ground unit.  You may deal 1 damage to it for each damage
     on this unit."

    The When Played readies the source (optional "may"), gated by the new
    ``ENEMY_CONTROLS_BOUNTY_UNIT`` condition so it is offered only when it can do
    something.  The On Attack is an optional ``DealDamageEqualTo`` on a chosen
    ground unit, scaled by the new ``source_damage`` count (damage on Krrsantan)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            optional=True,
            condition=ConditionCheck(Condition.ENEMY_CONTROLS_BOUNTY_UNIT),
            effects=[ReadyCard(TargetSpec(kind="unit", fixed=SELF))],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit", arena="ground"),
                count="source_damage")],
        ),
    ]


@card_ability("SHD", "143")
def _ruthlessness():
    """SHD_143 — Ruthlessness (Upgrade, Innate): "Attached unit gains: 'When this
    unit attacks and defeats a unit: Deal 2 damage to the defending player's
    base.'"

    A GrantedAbility(OnAttackDefeatsUnit) resolving from the host; the "defending
    player's base" is the enemy base from the host controller's perspective
    (EACH_ENEMY base, resolved inline)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttackDefeatsUnit(),
            effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base",
                                              fixed=EACH_ENEMY))],
        ),
    )


@card_ability("SHD", "150")
def _koska_reeves():
    """SHD_150 — Koska Reeves (Mandalorian, Trooper).
    "On Attack: If this unit is upgraded, you may deal 2 damage to a ground unit."

    Optional OnAttack gated by ``SOURCE_UPGRADED`` (only offered while Koska carries
    an upgrade); deals 2 to any ground unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:04 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _migs_mayfeld_mark(state, source_ci, target_id, event_ctx):
    """Mark Migs's once-per-round trigger used, after the "you may" was accepted and
    the 2 damage resolved (the Toro Calican SHD_239 marker pattern)."""
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("SHD", "163")
def _migs_mayfeld():
    """SHD_163 — Migs Mayfeld (Underworld).
    "When a player discards a card from their hand: You may deal 2 damage to a unit or
    base.  Use this ability only once each round."

    A ``WhenPlayerDiscardsFromHand`` observer (the new any-player discard-only seam) —
    fires on EITHER player's hand-discard, never on a Disclose reveal.  ``optional``
    handles the "you may"; the shared ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``
    condition offers it at most once per round.  Accepting resolves the well-trodden
    ``DealDamage(2, unit_or_base)`` (a base always exists, so the targeted effect never
    fizzles) and then marks the round's use — declining spends nothing."""
    return TriggerAbility(
        trigger=WhenPlayerDiscardsFromHand(),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit_or_base")),
                 CustomEffect(fn=_migs_mayfeld_mark)],
    )

@card_ability("SHD", "158")
def _wild_rancor():
    """SHD_158 — Wild Rancor (Creature; Overwhelm handled by the keyword engine).
    "When Played: Deal 2 damage to each other ground unit." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", arena="ground",
            predicates=("not_self",), fixed=EACH_IN_PLAY))],
    )


def _wanted_insurgents_bounty(state, source_ci, target_id, event_ctx):
    """Bounty — the collector deals 2 damage to a unit of their choice."""
    from swu.engine.actions import push_select_damage
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    push_select_damage(state, source_ci, amount_each=2, max_targets=1,
                       decider_id=collector,
                       after_resolve_idx=state.active_player_index)
    return state


@card_ability("SHD", "167")
def _wanted_insurgents():
    """SHD_167 — Wanted Insurgents (Rebel): "Bounty — Deal 2 damage to a unit."

    An ``is_bounty`` WhenDefeated resolving for the COLLECTOR, who picks the unit to
    take 2 damage (collector-addressed ``select_damage``, as Val SHD_58)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_wanted_insurgents_bounty)],
        is_bounty=True,
    )


@card_ability("SHD", "171")
def _covetous_rivals():
    """SHD_171 — Covetous Rivals (Bounty Hunter; Grit handled by the keyword engine).
    "When Played/On Attack: You may deal 2 damage to a unit with a Bounty."

    Two optional triggers (When Played and On Attack), each dealing 2 to a unit
    carrying a Bounty (the ``has_bounty`` target predicate); with no Bounty unit on
    the board the optional trigger auto-declines."""
    dmg = [DealDamage(2, TargetSpec(controller="any", kind="unit",
                                    predicates=("has_bounty",)))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(dmg), optional=True),
        TriggerAbility(trigger=OnAttack(), effects=list(dmg), optional=True),
    ]


def _guild_target_bounty(state, source_ci, target_id, event_ctx):
    """Bounty — the collector deals 2 (3 if the host unit is unique) damage to the
    dying unit's owner's base (the collector's enemy base)."""
    from swu.abilities.resolver import _apply_deal_damage
    amount = 3 if getattr(source_ci.card_def, "is_unique", False) else 2
    base = state.player_by_id(source_ci.owner_id).base_instance
    if base is not None:
        _apply_deal_damage(state, base.instance_id, amount,
                           source_name=source_ci.card_def.display_name)
    return state


@card_ability("SHD", "173")
def _guild_target():
    """SHD_173 — Guild Target (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Deal 2 damage to a base.  If this unit is unique, deal 3 damage
    instead.'"

    GrantedAbility(WhenDefeated) resolving from the host, so the "if this unit is
    unique" check reads the host's is_unique.  The collector damages the owner's
    base (the collector's enemy base) — the damage mirror of Top Target SHD_71's
    heal-your-base convention."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_guild_target_bounty)],
            is_bounty=True,
        ),
    )


@card_ability("SHD", "170")
def _ig_11():
    """SHD_170 — IG-11 (Bounty Hunter, Droid).

    Encoded: "On Attack: You may deal 3 damage to a damaged ground unit."

    DEFERRED (documented, flagged): "If this unit would be captured, defeat him and
    deal 3 damage to each enemy ground unit instead" is a REPLACEMENT effect on
    capture — the engine has no replacement-effect system (an escalation the rule
    reserves for a framework session).  No card in the shipped/encoded pool captures
    IG-11, so the reachable behaviour is the On Attack ability alone."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="ground", predicates=("damaged",)))],
    )


@card_ability("SHD", "172")
def _krayt_dragon():
    """SHD_172 — Krayt Dragon (Creature; Overwhelm handled by the keyword engine).
    "When an opponent plays a card: You may deal damage equal to that card's cost to
    their base or a ground unit they control."

    A ``WhenOpponentPlaysCard`` observer (any opponent play); the optional payoff is a
    ``DealDamageEqualTo`` scaled by the new ``event_played_card_cost`` count (the
    just-played card's printed cost, recorded into event_ctx by the matcher), aimed at
    the opponent's base OR a ground unit they control (``ground_or_base`` predicate).
    With a 0-cost card the magnitude is 0 (DealDamageEqualTo deals nothing)."""
    return TriggerAbility(
        trigger=WhenOpponentPlaysCard(),
        optional=True,
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="enemy", kind="unit_or_base",
                              predicates=("ground_or_base",)),
            count="event_played_card_cost")],
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:05 — Direct damage & removal
#
# SHD_142 Pre Vizsla and SHD_144 Give In to Your Anger landed in a dedicated
# framework session (see the shd-set:03 block above for their new seams).  SHD_226
# Unrefusable Offer was flagged as an escalation but turned out to need NO new
# engine machinery — it composes two existing seams (see its docstring below).
# ══════════════════════════════════════════════════════════════════════════════


def _unrefusable_offer_bounty(state, source_ci, target_id, event_ctx):
    """Bounty: the collector plays the defeated host unit under THEIR control,
    ready, flagged to be defeated at the next regroup phase.

    A GrantedAbility bounty resolves from the HOST (``source_ci`` IS the dying host
    unit — the Public Enemy SHD_68 pattern), inline during ``_defeat_unit`` while
    the host is in limbo (already out of its arena, not yet in discard).  The
    collector is the OPPONENT of the host's controller at death.  This is the
    Stolen Landspeeder SHD_161 replay MINUS its "if you own this unit" gate, plus
    ``enters_ready`` and ``defeat_at_regroup`` (both already threaded by
    ``_put_unit_in_play``), so no new engine machinery is needed."""
    from swu.engine.actions import _put_unit_in_play

    controller_at_death = event_ctx.get("defeated_controller_id")
    if controller_at_death is None:
        return state
    collector_ps = state.players[1 - state.player_index(controller_at_death)]

    ci = source_ci
    # A replay is a fresh in-play object: clear stale damage and any modifiers that
    # targeted the old instance (it reuses the same instance_id).  exhaust and
    # defeat_at_regroup are (re)set by _put_unit_in_play from the params below.
    ci.damage = 0
    state.modifiers = [
        m for m in state.modifiers if m.target_instance_id != ci.instance_id
    ]
    # Play "for free" under the COLLECTOR's control (control is implicit arena
    # occupancy; owner_id is unchanged, so a later regroup defeat still sends it to
    # the OWNER's discard).  play_source "discard" keeps any hand-gated When Played
    # (Stolen Landspeeder's control-steal) from firing on this replay; a normal
    # When Played still fires, as playing a unit should.
    _put_unit_in_play(state, collector_ps, ci, enters_ready=True,
                      play_source="discard", defeat_at_regroup=True)
    # Tell _defeat_unit the card is back in play — skip discard placement.
    event_ctx["relocated_by_trigger"] = True
    return state


@card_ability("SHD", "226")
def _unrefusable_offer():
    """SHD_226 — Unrefusable Offer (Upgrade; Bounty/Condition; "Attach to a
    non-leader unit").
    "Attached unit gains: 'Bounty — Play this unit for free (under your control).
    It enters play ready. At the start of the regroup phase, defeat it.'"

    A GrantedAbility(WhenDefeated, is_bounty=True) resolving from the host (the
    Public Enemy SHD_68 wrapper): when the host is defeated the collector replays
    it under their OWN control (the Stolen Landspeeder SHD_161 replay, minus the
    ownership gate), ready and flagged ``defeat_at_regroup``.  The regroup sweep in
    ``_enter_regroup`` defeats it — to the owner's discard — next regroup phase."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_unrefusable_offer_bounty)],
            is_bounty=True,
        ),
    )

@card_ability("SHD", "235")
def _ruthless_assassin():
    """SHD_235 — Ruthless Assassin (Bounty Hunter, Underworld; Overwhelm keyword).
    "When Played: Deal 2 damage to a friendly unit."

    A mandatory drawback: the source itself is always a legal friendly target, so the
    2 damage cannot fizzle."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="friendly", kind="unit"))],
    )


def _ma_klounkee_return(state, source_ci, target_id, event_ctx):
    """Return the chosen friendly non-leader Underworld unit to its owner's hand and
    record that a target was chosen (the ``requires_prior_target`` "If you do" gate)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_return_to_hand
    _apply_return_to_hand(state, target_id)
    event_ctx["prior_target_id"] = target_id
    return state


@card_ability("SHD", "229")
def _ma_klounkee():
    """SHD_229 — Ma Klounkee (Event; Trick, Underworld).
    "Return a friendly non-leader Underworld unit to its owner's hand. If you do, deal
    3 damage to a unit."

    The In Pursuit TWI_221 "If you do" pattern: a mandatory ``CustomEffect.target``
    returns the chosen Underworld unit and records ``prior_target_id``; the follow-up
    ``DealDamage(3)`` on any unit is gated by ``requires_prior_target`` so it fires
    (and prompts) only when a unit was actually returned — with no friendly non-leader
    Underworld unit the whole event fizzles cleanly."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_ma_klounkee_return,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Underworld",), predicates=("non_leader",)),
        ),
        DealDamage(3, TargetSpec(controller="any", kind="unit",
                                 predicates=("requires_prior_target",))),
    ])


def _vambrace_flamethrower(state, source_ci, target_id, event_ctx):
    """Push a 3-point distribute_damage pool over enemy ground units (the host's
    perspective — source_ci is the host of this GrantedAbility)."""
    from swu.engine.actions import push_distribute_damage
    push_distribute_damage(state, source_ci, 3, target_controller="enemy",
                           target_arena="ground")
    return state


@card_ability("SHD", "177")
def _vambrace_flamethrower_card():
    """SHD_177 — Vambrace Flamethrower (Upgrade; "Attach to a non-Vehicle unit").
    "Attached unit gains: 'On Attack: You may deal 3 damage divided as you choose
    among enemy ground units.'"

    A GrantedAbility(OnAttack) resolving from the host; the optional payoff pushes the
    standard ``distribute_damage`` pool (3) over enemy ground units.  The
    non-Vehicle attach restriction is parsed from the card text automatically."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[CustomEffect(fn=_vambrace_flamethrower)],
        ),
    )


def _detention_block_rescue(state, source_ci, target_id, event_ctx):
    """Deal 6 to the chosen unit if it is guarding any captured cards, else 3."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    guarding = any(
        c.captured_by == target_id
        for ps in state.players
        for c in ps.capture_pile
    )
    return _apply_deal_damage(state, target_id, 6 if guarding else 3,
                              source_ci.card_def.display_name)


@card_ability("SHD", "180")
def _detention_block_rescue_card():
    """SHD_180 — Detention Block Rescue (Event; Gambit).
    "Deal 3 damage to a unit. If that unit is guarding any captured cards, deal 6
    damage instead."

    A single mandatory ``CustomEffect.target`` (the Zeb Orellios LAW_45
    conditional-magnitude pattern); the fn picks 6 vs 3 by checking whether any
    captured card is guarded by the chosen unit (``captured_by == target``)."""
    return EventAbility(effects=[
        CustomEffect(fn=_detention_block_rescue,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


def _jetpack_shield(state, source_ci, target_id, event_ctx):
    """Give the host a Shield token flagged to be defeated at the next regroup phase
    (the regroup token-sweep in ``_enter_regroup``)."""
    from swu.engine.tokens import attach_token
    host_id = event_ctx.get("attached_to_id")
    host = None
    if host_id is not None:
        res = state.find_instance(host_id)
        host = res[1] if res else None
    if host is None:
        # Fallback: locate the host by the upgrade's attachment (Dengar pattern).
        from swu.abilities.resolver import _cards_in_play
        host = next((u for u in _cards_in_play(state)
                     if any(up.instance_id == source_ci.instance_id
                            for up in u.attached_upgrades)), None)
    if host is None:
        return state
    owner_ps = state.player_by_id(host.owner_id)
    token = attach_token(state, owner_ps, host, "Shield")
    token.defeat_at_regroup = True
    return state


@card_ability("SHD", "225")
def _jetpack():
    """SHD_225 — Jetpack (Upgrade; "Attach to a non-Vehicle unit"; Smuggle handled by
    the keyword engine).
    "When Played: Give a Shield token to attached unit. At the start of the regroup
    phase, defeat that token."

    A WhenPlayed CustomEffect gives the host a Shield token flagged
    ``defeat_at_regroup``; the regroup token-sweep in ``_enter_regroup`` detaches it
    at the start of the next regroup phase (tokens cease to exist when removed)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jetpack_shield)],
    )


def _toro_calican(state, source_ci, target_id, event_ctx):
    """Deal 1 to the just-played Bounty Hunter unit, ready Toro, and mark the
    once-per-round trigger used ("If you do, ready this unit")."""
    from swu.abilities.resolver import _apply_deal_damage, _cards_in_play
    played_id = event_ctx.get("played_card_id")
    if not played_id or state.find_instance(played_id) is None:
        return state
    _apply_deal_damage(state, played_id, 1, source_ci.card_def.display_name)
    source_ci.exhausted = False
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("SHD", "239")
def _toro_calican_card():
    """SHD_239 — Toro Calican (Bounty Hunter).
    "When you play another Bounty Hunter unit: You may deal 1 damage to it. If you do,
    ready this unit. Use this ability only once each round."

    A ``WhenYouPlayCard(trait="Bounty Hunter", card_type="unit")`` observer gated by
    the new ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` condition (offered at most once
    per round).  The optional payoff is one ``CustomEffect`` ("if you do" bound): it
    deals 1 to the played unit (located via ``played_card_id``, the Dengar SHD_133
    pattern), readies Toro, and marks the once-per-round used — so declining does not
    spend the round's use."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Bounty Hunter", card_type="unit"),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        effects=[CustomEffect(fn=_toro_calican)],
    )


@card_ability("SHD", "255")
def _lady_proxima():
    """SHD_255 — Lady Proxima (Unit, Underworld).
    "When you play another Underworld card: You may deal 1 damage to a base."

    A plain optional ``WhenYouPlayCard(trait="Underworld")`` observer (any card
    type; ``exclude_self`` default means playing Lady Proxima herself never
    triggers).  The payoff is a single targeted ``DealDamage(1, base)`` — the
    controller picks a base (optimal play is the enemy base), the Cad Bane SHD_14
    Underworld-observer precedent minus the leader machinery."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Underworld"),
        optional=True,
        effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
    )


@card_ability("SHD", "27")
def _hylobon_enforcer():
    """SHD_27 — Hylobon Enforcer (Unit, Underworld; Grit keyword engine).
    "Bounty — Draw a card."

    The standard bounty-draw template (Clone Deserter SHD_95, Cartel Turncoat
    SHD_195): a ``WhenDefeated`` ability tagged ``is_bounty=True`` so the OPPONENT
    who collects the bounty draws.  Grit is the keyword engine's job."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(count=1, player="opponent")],
        is_bounty=True,
    )


def _palpatines_return(state, source_ci, target_id, event_ctx):
    """Play a unit from the controller's discard, -6 (or -8 if Force)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, from_discard=True,
                        cost_reduction=6, cost_reduction_if_trait=("Force", 8))
    return state


@card_ability("SHD", "94")
def _palpatines_return_card():
    """SHD_94 — Palpatine's Return (Event, Force/Plan). "Play a unit from your
    discard pile. It costs 6 resources less. If it's a Force unit, it costs 8
    resources less instead."

    A thin ``EventAbility`` adapter over ``push_play_from_hand`` (from_discard):
    the ``cost_reduction_if_trait=("Force", 8)`` field REPLACES the base −6 with
    −8 for a Force unit (per-card conditional reduction; the Han Solo SHD_13
    play-from-hand discount seam extended with a trait-conditional value).  The
    event card itself is an Event, so it is never a candidate."""
    return EventAbility(effects=[CustomEffect(fn=_palpatines_return)])


@card_ability("SHD", "134")
def _guavian_antagonizer():
    """SHD_134 — Guavian Antagonizer (Unit, Underworld; Saboteur keyword engine).
    "Bounty — Draw a card."

    The bounty-draw template (Hylobon Enforcer SHD_27): the collecting OPPONENT
    draws.  Saboteur is the keyword engine's job."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(count=1, player="opponent")],
        is_bounty=True,
    )


def _enforced_loyalty(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly unit; if one was defeated, draw 2 (the atomic
    "If you do" binding — both halves in one CustomEffect so no defeat ⇒ no draw)."""
    from swu.engine.actions import _defeat_unit, _draw_cards
    if target_id is None:
        return state
    ctrl_ps, ci = state.find_instance(target_id)
    if ci is None:
        return state
    _defeat_unit(state, ctrl_ps, ci)
    _draw_cards(state, state.player_by_id(source_ci.owner_id), 2)
    return state


@card_ability("SHD", "108")
def _enforced_loyalty_card():
    """SHD_108 — Enforced Loyalty (Event, Law). "Defeat a friendly unit. If you
    do, draw 2 cards."

    A mandatory-if-able ``CustomEffect.target`` picks a friendly unit; the fn
    defeats it and draws 2 atomically, so playing the event with no friendly unit
    fizzles cleanly (no free draw).  The single-CustomEffect "If you do" binding
    (DrawCards is untargeted, so the Ma Klounkee SHD_229 ``requires_prior_target``
    gate doesn't apply — both halves live in one fn instead)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_enforced_loyalty,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
    ])


# ── shd-set:07 framework session — AuraGrantedAbility seam ───────────────────
# A SOURCE granting a triggered ability as an AURA to every unit matching a target
# ("Each friendly … unit gains: '<triggered ability>'"), the group analogue of the
# upgrade-borne GrantedAbility.  Landed for Gar Saxon SHD_1; collected at the
# UnitDefeated defeat path (resolver._collect_triggers), unwrapped by unwrap_granted.
def _gar_saxon_return_upgrade(state, source_ci, target_id, event_ctx):
    """Return one upgrade that was attached to the defeated unit (``source_ci`` = the
    dying unit) to its owner's hand.

    ``_defeat_unit`` detached the unit's real (non-token) upgrades to their owner's
    discard and stashed the snapshot in ``event_ctx["defeated_upgrades"]``; offer just
    those via ``push_return_from_discard`` with ``up_to`` (so returning none is the
    "you may").  Tokens vanish on defeat and cannot return to a hand, so they are
    excluded.  Scans the dying unit's controller's discard — the common case where a
    friendly unit carried its controller's own upgrades (an enemy-owned bounty upgrade
    would sit in the opponent's discard and is simply not offered)."""
    from swu.cards.models import Upgrade, TokenUpgrade
    from swu.engine.actions import push_return_from_discard
    ids = {u.instance_id for u in (event_ctx.get("defeated_upgrades") or [])
           if isinstance(u.card_def, Upgrade) and not isinstance(u.card_def, TokenUpgrade)}
    if not ids:
        return state
    push_return_from_discard(
        state, source_ci, count=1,
        eligible=lambda cd: True,
        eligible_instance=lambda ci: ci.instance_id in ids,
    )
    return state


@card_ability("SHD", "1")
def _gar_saxon():
    """Gar Saxon leader (SHD_1).

    "Each friendly upgraded unit gets +1/+0" (printed on BOTH sides) → an ungated
    ConstantAbility (applies while DEPLOYED; the undeployed base_zone constant is the
    documented leader-side simplification shared by Director Krennic SOR_1).

    The deployed unit side additionally grants each friendly upgraded unit "When
    Defeated: You may return an upgrade that was attached to this unit to its owner's
    hand." → the AuraGrantedAbility seam.  The grant targets friendly units WITHOUT an
    "upgraded" predicate on purpose: a non-upgraded unit's granted When-Defeated has no
    upgrade to return, so it self-limits (behaviourally identical to gating on
    "upgraded"), which also sidesteps matching a dying unit whose upgrades are already
    detached.  The mandatory trigger's CustomEffect pushes an "up to 1" return
    decision, so the "you may" is the option to return none.  (Gar Saxon's own defeat
    is a last-known-information corner — the aura source has already left play by the
    time UnitDefeated fires — so the grant applies to OTHER friendly upgraded units;
    Epic Action deploy is the engine-generic leader mechanic.)"""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("upgraded",)),
            effects=[StatBonus(power=1, hp=0)],
        ),
        AuraGrantedAbility(
            target=TargetSpec(controller="friendly", kind="unit"),
            ability=TriggerAbility(
                trigger=WhenDefeated(),
                effects=[CustomEffect(fn=_gar_saxon_return_upgrade)],
            ),
        ),
    ]


# ── shd-set:07 framework session — reveal_resource_ramp seam ──────────────────

def _hunter_reveal_ramp(state, source_ci, target_id, event_ctx):
    """Hunter SHD_9 undeployed Action: mandatory reveal (gated so it only fires with
    a match) → push the reveal_resource_ramp decision with no decline option."""
    from swu.engine.actions import push_reveal_resource_ramp
    push_reveal_resource_ramp(state, source_ci, optional=False)
    return state


def _hunter_reveal_ramp_optional(state, source_ci, target_id, event_ctx):
    """Hunter SHD_9 deployed On Attack: same effect, but the reveal is a 'may' (the
    push is a no-op when nothing matches, so the trigger just does nothing)."""
    from swu.engine.actions import push_reveal_resource_ramp
    push_reveal_resource_ramp(state, source_ci, optional=True)
    return state


@card_ability("SHD", "9")
def _hunter():
    """SHD_9 — Hunter (Leader, Clone/Fringe; Overwhelm handled engine-side).

    Undeployed: "Action [1 resource, Exhaust]: Reveal a resource you control. If it
        shares a name with a friendly unique unit, return the resource to its
        owner's hand and put the top card of your deck into play as a resource."
    Deployed:   "On Attack: You may reveal a resource you control. If it shares a
        name with a friendly unique unit, return the resource … put the top card of
        your deck into play as a resource." (+ Overwhelm keyword)
    Both read the same text; both push the new self-contained ``reveal_resource_ramp``
    decision (actions.push_reveal_resource_ramp): the controller reveals one of their
    name-matching resources → it returns to its owner's hand and they ramp the deck
    top.  Both sides are gated by CONTROLLER_HAS_REVEAL_RAMP_RESOURCE so nothing is
    offered when no reveal could match: the undeployed Action's 1-resource+Exhaust
    cost is never spent for nothing, and the deployed On Attack trigger isn't even
    collected.  The "may" of the On Attack is the pushed decision's
    DeclineRevealResource option (optional=True); the undeployed Action, already
    paid, pushes with optional=False.  Epic Action deploy at 7+ resources = standard
    deploy_threshold machinery."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_hunter_reveal_ramp)],
            title="Reveal a resource — return it and ramp",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_REVEAL_RAMP_RESOURCE),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_hunter_reveal_ramp_optional)],
            deployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_REVEAL_RAMP_RESOURCE),
        ),
    ]


# ── shd-set:07 framework session — Doctor Aphra SHD_15 ────────────────────────

def _aphra_mill(state, source_ci, target_id, event_ctx):
    """Discard the top card of the controller's deck (a mandatory self-mill; the
    deck is ordered, so no player choice — the BoShek JTL_215 mill pattern)."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if ps.deck:
        card = ps.deck.pop(0)
        card.face_down = False
        card.zone = Zone.DISCARD
        ps.discard.append(card)
    return state


def _aphra_deploy(state, source_ci, target_id, event_ctx):
    """When Deployed: choose 3 differently-named discard cards; return 1 at random.
    Pushed only when ≥3 distinct names exist (else "if you do" is unmet)."""
    from swu.engine.actions import push_select_distinct_return_random
    push_select_distinct_return_random(state, source_ci, count=3)
    return state


@card_ability("SHD", "15")
def _doctor_aphra():
    """SHD_15 — Doctor Aphra (Leader, Fringe, 2/5).

    Deployed side (all three below function only while Aphra is a unit in play):
      - "When the regroup phase starts: Discard a card from your deck." — a
        ``PhaseStartTrigger(phase="regroup")`` (the Contracted Hunter JTL_216 hook)
        whose inline mandatory ``_aphra_mill`` mills the deck top.
      - "While there are 5 or more different costs among cards in your discard pile,
        this unit gets +3/+0." — a self-``ConstantAbility`` gated by the new
        ``CONTROLLER_DISCARD_DISTINCT_COSTS_MIN`` condition (param 5), reusing the
        same distinct-cost count as Fennec Shand SHD_220.
      - "When Deployed: Choose 3 cards in your discard pile with different names.
        If you do, return 1 of them at random to your hand." — a ``WhenDeployed``
        trigger pushing the new self-contained ``select_distinct_return_random``
        decision (actions.push_select_distinct_return_random), which is pushed only
        when ≥3 distinct names are present.
    Epic Action deploy at 5+ resources = standard deploy_threshold machinery."""
    return [
        TriggerAbility(
            trigger=PhaseStartTrigger(phase="regroup"),
            effects=[CustomEffect(fn=_aphra_mill)],
            deployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=3, hp=0)],
            condition=ConditionCheck(
                Condition.CONTROLLER_DISCARD_DISTINCT_COSTS_MIN, 5),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_aphra_deploy)],
            deployed_only=True,
        ),
    ]


@card_ability("SHD", "38")
def _brutal_traditions():
    """Brutal Traditions (SHD_38) — Upgrade, cost 2.

    "Action: If an enemy unit was defeated this phase, play this upgrade from
    your discard pile (paying its cost)."

    A recursion upgrade: while it sits in your discard pile, it offers an Action
    to replay it (paying its normal cost) — gated on an enemy unit having been
    defeated this phase.  Modeled with the ``PlayFromDiscardAction`` seam, which
    makes the discard pile a legal-action source; the gate reuses the existing
    ``ENEMY_UNIT_DEFEATED_THIS_PHASE`` condition (Darth Sion SEC_35).  The
    "Attach to …" host restriction, cost payment and WhenPlayed firing all flow
    through the shared play machinery."""
    return PlayFromDiscardAction(
        condition=ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE),
    )


def _second_chance_grant(state, source_ci, target_id, event_ctx):
    """When the host (``source_ci`` = the defeated unit) is defeated, flag it so
    its owner may replay it from discard for FREE for the rest of this phase.

    The flag is a per-instance, phase-scoped permission
    (``game_memory.free_discard_play_this_phase``) read by
    ``actions._enumerate_discard_play_actions`` (a free ``PlayFromDiscard`` for
    the flagged unit once it is sitting in the owner's discard) and consumed on
    replay.  The unit is not yet in discard when this fires (WhenDefeated resolves
    before the placement), but its instance_id is stable, so flagging it here is
    enough."""
    state.game_memory.free_discard_play_this_phase.add(source_ci.instance_id)
    return state


@card_ability("SHD", "53")
def _second_chance():
    """Second Chance (SHD_53) — Upgrade, cost 4, attach to a non-leader unit.

    "Attached unit gains: 'When Defeated: For this phase, this unit's owner may
    play it from their discard pile for free.'"

    A ``GrantedAbility`` conferring a WhenDefeated trigger on the host (the same
    granted-When-Defeated collection path as Gar Saxon SHD_1's aura / the bounty
    upgrades): on the host's defeat it records a phase-scoped free-replay
    permission for that unit.  The "Attach to a non-leader unit" restriction is
    parsed from the card text by the shared upgrade-target machinery, and the
    free replay surfaces via the ``PlayFromDiscard`` seam (``free=True``)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_second_chance_grant)],
        ),
    )


# ── Group 08: card advantage & disruption ────────────────────────────────────

def _echo_discard_for_experience(state, source_ci, target_id, event_ctx):
    """Adapter: push Echo's optional "discard a card, give 2 Experience to a
    same-named unit" decision (the discard_for_experience seam)."""
    from swu.engine.actions import push_discard_for_experience
    push_discard_for_experience(state, source_ci)
    return state


@card_ability("SHD", "99")
def _echo():
    """Echo (SHD_99) — Unit, cost 4, 4/4, Restore 2.

    Restore is handled by the keyword engine.  Residual: "When Played: You may
    discard a card from your hand.  Give 2 Experience tokens to a unit in play
    with the same name as the discarded card."  A ``discard_for_experience``
    decision (the candidates are hand cards whose name matches a friendly unit in
    play — the Clone name-match — and the chosen card is discarded to give 2
    Experience to that unit)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_echo_discard_for_experience)],
    )


def _marauder_resource_from_discard(state, source_ci, target_id, event_ctx):
    """Adapter: The Marauder resources a discard card that shares a name with a
    friendly unit in play (the resource_from_discard seam)."""
    from swu.engine.actions import push_resource_from_discard
    ps = state.player_by_id(source_ci.owner_id)
    unit_names = {u.card_def.display_name
                  for arena in (ps.ground_arena, ps.space_arena) for u in arena}
    push_resource_from_discard(
        state, source_ci,
        eligible=lambda ci: ci.card_def.display_name in unit_names,
    )
    return state


@card_ability("SHD", "102")
def _the_marauder():
    """The Marauder (SHD_102) — Unit, cost 5, 4/5, Ambush.

    Ambush is handled by the keyword engine.  Residual: "When Played: Choose a
    card in your discard pile.  Put it into play as a resource if it shares a name
    with a unit you control."  A ``resource_from_discard`` decision pre-filtered to
    the name-sharing discard cards (choosing a non-sharing card would do nothing);
    the chosen card enters the resource zone facedown + exhausted."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_marauder_resource_from_discard)],
    )


def _spark_of_hope_resource(state, source_ci, target_id, event_ctx):
    """Adapter: Spark of Hope resources a unit in the discard pile that was
    defeated this phase (the resource_from_discard seam)."""
    from swu.engine.actions import push_resource_from_discard
    from swu.cards.models import Unit
    defeated = state.game_memory.units_defeated_this_round
    push_resource_from_discard(
        state, source_ci,
        eligible=lambda ci: (isinstance(ci.card_def, Unit)
                             and ci.instance_id in defeated),
    )
    return state


@card_ability("SHD", "105")
def _spark_of_hope():
    """Spark of Hope (SHD_105) — Event, cost 2.

    "Choose a unit in your discard pile.  If it was defeated this phase, put it
    into play as a resource."  A ``resource_from_discard`` decision pre-filtered to
    units that were defeated this phase (``units_defeated_this_round`` — the
    Admiral Trench TWI_86 defeated-this-phase precedent); the chosen card enters
    the resource zone facedown + exhausted."""
    return EventAbility(effects=[CustomEffect(fn=_spark_of_hope_resource)])


def _cobb_vanth_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 10 for a unit costing 2 or less, discard it, and
    flag it for a free replay from the discard pile this phase (the deck_search
    ``discard_free_replay`` disposition — the Second Chance SHD_53 seam)."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit
    push_deck_search(
        state, source_ci,
        count=1, window=10, up_to=False,
        eligible=lambda cd: isinstance(cd, Unit) and (cd.cost or 0) <= 2,
        disposition="discard_free_replay",
    )
    return state


@card_ability("SHD", "115")
def _cobb_vanth():
    """Cobb Vanth (SHD_115) — Unit, cost 3, 3/2.

    "When Defeated: Search the top 10 cards of your deck for a unit that costs 2 or
    less and discard it.  For this phase, you may play that card from your discard
    pile for free."  A ``deck_search`` (window=10, count=1, mandatory-if-able) whose
    selected unit is discarded and flagged in ``free_discard_play_this_phase``, so
    the free replay surfaces via the ``PlayFromDiscard`` seam (``free=True``)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_cobb_vanth_search)],
    )


_COMMISSION_TRAITS = {"Bounty Hunter", "Item", "Transport"}


def _commission_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 10 for a Bounty Hunter / Item / Transport card and
    draw it, bottoming the rest in a seeded-random order (the deck_search seam)."""
    from swu.engine.actions import push_deck_search
    push_deck_search(
        state, source_ci,
        count=1, window=10, up_to=False,
        eligible=lambda cd: bool(set(getattr(cd, "traits", None) or ())
                                 & _COMMISSION_TRAITS),
    )
    return state


@card_ability("SHD", "127")
def _commission():
    """Commission (SHD_127) — Event, cost 1, Smuggle [3 Command].

    Smuggle is handled by the keyword engine.  Residual: "Search the top 10 cards
    of your deck for a Bounty Hunter, Item, or Transport card, reveal it, and draw
    it.  (Put the other cards on the bottom of your deck in a random order.)"  A
    ``deck_search`` (window=10, count=1, mandatory-if-able) filtered by trait."""
    return EventAbility(effects=[CustomEffect(fn=_commission_search)])


# ── shd-set:09 — Card advantage & disruption ──────────────────────────────────

@card_ability("SHD", "135")
def _kylos_tie_silencer():
    """Kylo's TIE Silencer (SHD_135) — Unit, cost 2, 3/2, Fighter/First Order/Vehicle.

    "Action: If this unit was discarded from your hand or deck this phase, play it
    from your discard pile (paying its cost)."  A ``PlayFromDiscardAction`` (the
    Brutal Traditions SHD_38 discard-as-legal-action-source seam) gated by the new
    ``SELF_DISCARDED_THIS_PHASE`` condition, which reads the phase-scoped
    ``game_memory.cards_discarded_this_phase`` ledger fed by
    ``actions.note_hand_or_deck_discard`` at the self-discard / mill sites."""
    return PlayFromDiscardAction(
        condition=ConditionCheck(Condition.SELF_DISCARDED_THIS_PHASE),
    )


@card_ability("SHD", "138")
def _jango_fett():
    """Jango Fett (SHD_138) — Unit, cost 4, 3/6, Bounty/Overwhelm.

    Two clauses:
      * "While attacking a unit with a Bounty, this unit gets +3/+0 and gains
        Overwhelm."  A self-targeted ``ConstantAbility`` with the new
        ``while_attacking_bounty_unit`` flag — compute_power adds +3/+0 only while
        Jango is attacking a unit that has a Bounty (checked via the threaded
        ``defender_id``).  The Overwhelm KeywordGrant it also carries is reported
        always by the keyword layer (the Moff Gideon SHD_7 simplification — Overwhelm
        matters chiefly when attacking a unit anyway).  Jango's *printed* Overwhelm
        bar is a keyword-engine keyword; this constant's grant is redundant with it
        while attacking, and harmless otherwise.
      * "When this unit attacks and defeats a unit: Draw a card."  A mandatory
        ``OnAttackDefeatsUnit`` trigger (First Light SEC_88 pattern)."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=3, hp=0), KeywordGrant("Overwhelm", value=0)],
            while_attacking_bounty_unit=True,
        ),
        TriggerAbility(
            trigger=OnAttackDefeatsUnit(),
            effects=[DrawCards(count=1)],
        ),
    ]


def _cripple_authority_discard(state, source_ci, target_id, event_ctx):
    """"Each opponent who controls more resources than you discards a card from
    their hand."  2-player: the one opponent discards their first card (the
    established first-card discard simplification) only when they control strictly
    more resources than the controller."""
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if len(opp.resources) > len(ps.resources) and opp.hand:
        from swu.engine.state import Zone
        from swu.engine.actions import note_hand_or_deck_discard, record_hand_discard
        ci = opp.hand.pop(0)
        ci.zone = Zone.DISCARD
        opp.discard.append(ci)
        note_hand_or_deck_discard(state, ci)
        record_hand_discard(state, opp.player_id)
    return state


@card_ability("SHD", "156")
def _cripple_authority():
    """Cripple Authority (SHD_156) — Event, cost 2, Trick.

    "Draw a card.  Each opponent who controls more resources than you discards a
    card from their hand."  ``DrawCards(1)`` then a CustomEffect for the
    resource-comparison-gated opponent discard (drawing doesn't change resource
    counts, so the two are order-independent)."""
    return EventAbility(effects=[
        DrawCards(count=1),
        CustomEffect(fn=_cripple_authority_discard),
    ])


def _bo_katan_kryze_draw(state, source_ci, target_id, event_ctx):
    """"For each player with 15 or more damage on their base, draw a card." — draw
    that many for the controller (0, 1, or 2 in a 2-player game)."""
    from swu.engine.actions import _draw_cards
    n = sum(1 for p in state.players
            if p.base_instance is not None and p.base_instance.damage >= 15)
    if n:
        _draw_cards(state, state.player_by_id(source_ci.owner_id), n)
    return state


@card_ability("SHD", "157")
def _bo_katan_kryze():
    """Bo-Katan Kryze (SHD_157) — Unit, cost 2, 3/3, Mandalorian/Trooper.

    "When Defeated: For each player with 15 or more damage on their base, draw a
    card."  A ``WhenDefeated`` trigger whose CustomEffect counts bases at ≥15 damage
    and draws that many (scaling magnitude read from board state)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_bo_katan_kryze_draw)],
    )


def _death_mark_bounty(state, source_ci, target_id, event_ctx):
    """Collector draws 2 cards (Death Mark's bounty)."""
    from swu.engine.actions import _draw_cards
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    _draw_cards(state, state.player_by_id(collector), 2)
    return state


@card_ability("SHD", "176")
def _death_mark():
    """Death Mark (SHD_176) — Upgrade, cost 2, Bounty/Condition.

    "Attached unit gains: 'Bounty — Draw 2 cards.'"  A ``GrantedAbility`` bounty
    (WhenDefeated) resolving from the host; the collector (the opponent of the dying
    unit's controller) draws 2.  Deterministic → resolves inline (the Price on Your
    Head SHD_125 bounty pattern, drawing instead of ramping)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_death_mark_bounty)],
            is_bounty=True,
        ),
    )


@card_ability("SHD", "181")
def _pillage():
    """Pillage (SHD_181) — Event, cost 4, Tactic.

    "Choose a player.  They discard 2 cards from their hand."  A controller would
    always choose the opponent, so this collapses to the opponent discarding 2 (the
    ``DiscardFromHand(chooser="opponent")`` first-card simplification, ×2 — a
    documented deviation from a look-and-pick decision)."""
    return EventAbility(effects=[DiscardFromHand(count=2, chooser="opponent")])


def _bazine_netal_when_played(state, source_ci, target_id, event_ctx):
    """Adapter: look at the opponent's hand; you MAY discard 1 of those cards, and
    if you do, that player draws a card (the name_and_discard seam, optional + the
    discarder-draws rider)."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, optional=True, discarder_draws=True)
    return state


@card_ability("SHD", "184")
def _bazine_netal():
    """Bazine Netal (SHD_184) — Unit, cost 2, 1/3, Underworld, Smuggle.

    Smuggle is the keyword engine.  "When Played: Look at an opponent's hand.  You
    may discard 1 of those cards.  If you do, that player draws a card."  Modelled on
    the ``name_and_discard`` seam (Chimaera SOR_185): the controller sees the hand
    (identities only, never hidden instance_ids) and may strip one card — ``optional``
    for the "you may", ``discarder_draws`` for the "that player draws a card"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_bazine_netal_when_played)],
    )


# ── shd-set:10 "Card advantage & disruption" (ordinary ability batch) ──────────

def _is_clone_card(card_def) -> bool:
    """A card with the Clone trait (Omega SHD_198's deck-search filter)."""
    return "Clone" in (getattr(card_def, "traits", None) or ())


def _omega_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 5 for a Clone card and draw it (mandatory if able)."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, window=5,
                     eligible=_is_clone_card, up_to=False)
    return state


@card_ability("SHD", "198")
def _omega():
    """SHD_198 — Omega (Unit, Clone/Fringe, 2/2).

    "When Played: Search the top 5 cards of your deck for a Clone card, reveal it,
    and draw it.  (Put the other cards on the bottom of your deck in a random
    order.)"  A thin CustomEffect adapter onto the deck_search seam (the Greef Karga
    SHD_245 pattern): ``count=1, window=5, up_to=False`` — one Clone taken while one
    is present, else nothing; the un-taken top-5 are bottomed in a seeded-random
    order.

    RESIDUAL (deferred): "Ignore the aspect penalty on the first Clone unit you play
    each round" is a passive per-round play-cost waiver, not part of the When Played
    ability — the same aspect-penalty-waiver cost seam left unimplemented on The
    Darksaber SHD_126.  Omega is fully playable (her search fires); only the
    conditional cost discount is missing."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_omega_search)],
    )


def _zorii_schedule_discard(state, source_ci, target_id, event_ctx):
    """Schedule the delayed "at the start of the regroup phase, discard a card from
    your hand" obligation on Zorii herself (the per-instance
    ``discard_from_hand_at_regroup`` counter, swept in actions._enter_regroup)."""
    res = state.find_instance(source_ci.instance_id)
    if res is not None:
        res[1].discard_from_hand_at_regroup += 1
    return state


@card_ability("SHD", "203")
def _zorii_bliss():
    """SHD_203 — Zorii Bliss (Unit, Underworld, 4/7; Smuggle = keyword engine).

    "On Attack: Draw a card.  At the start of the regroup phase, discard a card from
    your hand."  A single ``OnAttack`` trigger that draws now (declarative
    ``DrawCards``) and schedules the delayed discard on Zorii via the new
    ``discard_from_hand_at_regroup`` per-instance counter (mirroring
    ``defeat_at_regroup`` / ``return_to_owner_hand_at_regroup``): at the start of the
    next regroup phase her controller discards one card (first-card simplification,
    the DiscardFromHand convention).  Two attacks in a round schedule two discards.
    A per-instance flag, so a Zorii who has left play by regroup skips the discard —
    a minor, documented deviation from the delayed-ability-persists rule."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(count=1), CustomEffect(fn=_zorii_schedule_discard)],
    )


def _frontier_trader(state, source_ci, target_id, event_ctx):
    """Return one controlled resource to its owner's hand, then ramp the deck top.

    Auto-select simplification (the K-2SO SOR_145 / _resource_card_from_hand
    precedent): face-down resources are indistinguishable to the UI, so the
    highest-cost resource is recovered — the card most worth getting back — instead
    of prompting.  The "if you do" ramp always follows (strictly beneficial)."""
    from swu.engine.actions import _resource_top_of_deck
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.resources:
        return state
    res = max(ps.resources, key=lambda c: getattr(c.card_def, "cost", 0) or 0)
    ps.resources.remove(res)
    res.zone = Zone.HAND
    res.face_down = False
    res.exhausted = False
    state.player_by_id(res.owner_id).hand.append(res)
    _resource_top_of_deck(state, ps)  # "you may put the top card into play as a resource"
    return state


@card_ability("SHD", "214")
def _frontier_trader_card():
    """SHD_214 — Frontier Trader (Unit, Fringe/Jawa, 2/2).

    "When Played: You may return a resource you control to its owner's hand.  If you
    do, you may put the top card of your deck into play as a resource."  An optional
    ``WhenPlayed`` (the "you may") whose one ``CustomEffect`` recovers a resource to
    hand and ramps the deck top (both "may"s collapse onto the single accept — the
    ramp is strictly good, so it always follows the recovery).  Net: a spent resource
    becomes a hand card and the deck top becomes a fresh resource (deck −1, hand +1,
    resource count unchanged).  With no resources the accept is a no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(fn=_frontier_trader)],
    )


@card_ability("SHD", "209")
def _criminal_muscle():
    """SHD_209 — Criminal Muscle (Unit, Underworld, 2/1).

    "When Played: You may return a non-unique upgrade to its owner's hand."  An
    optional ``WhenPlayed`` (the "you may") whose ``ReturnToHand`` targets any
    non-unique real upgrade in play (either player's — the controller points it at an
    enemy's buff), reusing the ``non_unique`` predicate.  Auto-declines when no
    non-unique upgrade is in play."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ReturnToHand(TargetSpec(
            controller="any", kind="upgrade", predicates=("non_unique",)))],
    )


def _xanadu_blood_effect(state, source_ci, target_id, event_ctx):
    """Return the chosen friendly Underworld unit; if a return happened, exhaust an
    enemy unit.  Auto-select the enemy's best READY unit (highest printed power),
    falling back to any enemy unit.  DEVIATIONS (documented on the card): "or
    resource" is narrowed to an enemy unit (there is no resource target kind, and the
    spec's suggested primitive is ExhaustCard), and the exhaust target is auto-picked
    rather than prompted (the return is the player-willed, value-bearing choice)."""
    from swu.abilities.resolver import _apply_return_to_hand
    if target_id is None:
        return state  # declined, or no friendly Underworld unit — no return, no exhaust
    _apply_return_to_hand(state, target_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    enemies = list(opp.ground_arena) + list(opp.space_arena)
    pool = [u for u in enemies if not u.exhausted] or enemies
    if pool:
        victim = max(pool, key=lambda u: getattr(u.card_def, "power", 0) or 0)
        victim.exhausted = True
    return state


@card_ability("SHD", "191")
def _xanadu_blood():
    """SHD_191 — Xanadu Blood (Unit, Fighter/Underworld/Vehicle, 4/6; Raid = keyword).

    "When Played/On Attack: You may return another friendly non-leader Underworld unit
    to its owner's hand.  If you do, exhaust an enemy unit or resource."  Two OPTIONAL
    triggers (a ``WhenPlayed`` and an ``OnAttack``) sharing one ``CustomEffect`` whose
    target is the friendly non-leader Underworld unit to return (``not_self`` excludes
    Xanadu itself) — the accept/target IS the "you may", and the fn only exhausts when
    a return actually happened (the "If you do" coupling).  The exhaust is simplified:
    an enemy unit (no resource target kind) auto-picked as the best ready enemy unit
    (see ``_xanadu_blood_effect``)."""
    spec = TargetSpec(controller="friendly", kind="unit",
                      traits=("Underworld",), predicates=("non_leader", "not_self"))
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[CustomEffect(fn=_xanadu_blood_effect, target=spec)]),
        TriggerAbility(trigger=OnAttack(), optional=True,
                       effects=[CustomEffect(fn=_xanadu_blood_effect, target=spec)]),
    ]


def _a_new_adventure(state, source_ci, target_id, event_ctx):
    """Return the chosen non-leader unit (cost ≤ 6) to its owner's hand, then hand
    that owner an ``owner_may_replay`` decision to play it for FREE (the Rio Durant
    LAW_93 / Baylan Skoll LOF_185 multi-decider primitive, ungated and with no granted
    keyword)."""
    from swu.engine.actions import push_owner_may_replay
    from swu.abilities.resolver import _apply_return_to_hand
    if target_id is None:
        return state
    _apply_return_to_hand(state, target_id)
    push_owner_may_replay(state, source_ci, target_id)
    return state


@card_ability("SHD", "207")
def _a_new_adventure_card():
    """SHD_207 — A New Adventure (Event, Gambit, cost 2).

    "Return a non-leader unit that costs 6 or less to its owner's hand.  Then, its
    owner may play it for free."  A pure reuse of the return-then-owner-replays-free
    primitive (Rio Durant LAW_93): a single ``CustomEffect`` targets a non-leader unit
    costing ≤ 6 (any controller — the owner, who may be the opponent, gets the free
    replay), returns it, and pushes the ``owner_may_replay`` decision.  With no
    eligible unit the event fizzles cleanly."""
    return EventAbility(effects=[CustomEffect(
        fn=_a_new_adventure,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("non_leader",), cost_max=6))])


def _is_vehicle_unit(card_def) -> bool:
    """A Vehicle unit (Triple Dark Raid SHD_194's search-and-play filter)."""
    from swu.cards.models import Unit
    return (isinstance(card_def, Unit)
            and "Vehicle" in (getattr(card_def, "traits", None) or ()))


def _triple_dark_raid(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 7 for a Vehicle, play it for 5 less, ready, and flag it
    to return to hand at the phase boundary (the extended search-and-play seam)."""
    from swu.engine.actions import push_search_and_play
    push_search_and_play(state, source_ci, window=7, cost_reduction=5,
                         eligible=_is_vehicle_unit, enters_ready=True,
                         return_at_regroup=True)
    return state


@card_ability("SHD", "194")
def _triple_dark_raid_card():
    """SHD_194 — Triple Dark Raid (Event, Tactic, cost 3).

    "Search the top 7 cards of your deck for a Vehicle and play it.  (Put the other
    cards on the bottom of your deck in a random order.)  It costs 5 resources less
    and enters play ready.  Return it to its owner's hand at the end of the phase."
    A ``CustomEffect`` onto the search-and-play seam (Kelleran Beq LOF_100), extended
    with an ``eligible`` filter (Vehicle units only), ``enters_ready`` (the temporary
    Vehicle arrives ready to attack), and ``return_at_regroup`` (the "end of the
    phase" bounce, modelled on the action→regroup boundary via the Commandeer JTL_235
    delayed-return flag).  Affordability is checked at the reduced cost; with no
    affordable Vehicle in the window the search resolves with nothing played."""
    return EventAbility(effects=[CustomEffect(fn=_triple_dark_raid)])


# ── shd-set:11 — Card advantage & disruption ──────────────────────────────────

def _enticing_reward_bounty(state, source_ci, target_id, event_ctx):
    """Enticing Reward SHD_222 bounty (collector = opponent of the dying host):
    "Search the top 10 cards of your deck for 2 non-unit cards, reveal them, and
    draw them.  (Put the other cards on the bottom of your deck in a random order.)
    Then, if this unit isn't unique, discard a card from your hand."

    The collector-decided deck search runs over the COLLECTOR's deck (the
    push_deck_search ``decider_id`` override — "your deck" belongs to whoever
    collects the bounty).  The conditional discard is applied FIRST, from the
    collector's pre-draw hand via the first-card-discard simplification (it is a
    drawback the collector would minimise either way, so choosing after drawing is
    a negligible deviation); "this unit" is the dying host, so its is_unique gates
    the discard."""
    from swu.cards.models import Unit
    from swu.engine.state import Zone
    from swu.engine.actions import (
        push_deck_search, note_hand_or_deck_discard, record_hand_discard)
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    if not getattr(source_ci.card_def, "is_unique", False):
        cps = state.player_by_id(collector)
        if cps.hand:
            ci = cps.hand.pop(0)
            ci.zone = Zone.DISCARD
            cps.discard.append(ci)
            note_hand_or_deck_discard(state, ci)
            record_hand_discard(state, collector)
    push_deck_search(
        state, source_ci, count=2, window=10, up_to=False,
        eligible=lambda cd: not isinstance(cd, Unit),
        decider_id=collector)
    return state


@card_ability("SHD", "222")
def _enticing_reward():
    """SHD_222 — Enticing Reward (Upgrade, Bounty/Condition): "Attached unit gains:
    'Bounty — Search the top 10 cards of your deck for 2 non-unit cards, reveal
    them, and draw them. … Then, if this unit isn't unique, discard a card from
    your hand.'"

    GrantedAbility(WhenDefeated) resolving from the host; the collector (the
    opponent of the host's controller) searches THEIR OWN deck (the push_deck_search
    ``decider_id`` override, the select_token collector-decider convention)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_enticing_reward_bounty)],
            is_bounty=True,
        ),
    )


def _bounty_posting(state, source_ci, target_id, event_ctx):
    """Search the controller's whole deck for a Bounty upgrade, reveal + draw it,
    then bottom the rest in a random order (≈ the printed "Shuffle your deck").

    Modelled as a full-window ``push_deck_search`` (window = deck size) with an
    eligible filter of "Upgrade carrying the Bounty keyword/trait", ``count=1``,
    mandatory-if-able.  RESIDUAL (documented simplification): the optional "You may
    play that upgrade (paying its cost)" follow-up is dropped — the drawn upgrade is
    in hand to be played on the normal PlayCard path; modelling an in-ability
    upgrade play (with host targeting + cost) would need a new play path and the
    tempo gain is minor."""
    from swu.cards.models import Upgrade
    from swu.engine.actions import push_deck_search
    ps = state.player_by_id(source_ci.owner_id)

    def _is_bounty_upgrade(cd):
        return isinstance(cd, Upgrade) and (
            "Bounty" in getattr(cd, "keywords", ()) or "Bounty" in getattr(cd, "traits", ()))

    push_deck_search(
        state, source_ci, count=1, window=max(1, len(ps.deck)), up_to=False,
        eligible=_is_bounty_upgrade)
    return state


@card_ability("SHD", "228")
def _bounty_posting_card():
    """SHD_228 — Bounty Posting (Event, Plan, cost 1): "Search your deck for a
    Bounty upgrade, reveal it, and draw it. (Shuffle your deck.) You may play that
    upgrade (paying its cost)."  A thin CustomEffect onto the deck_search seam over
    the full deck (see the note on the dropped optional-play residual)."""
    return EventAbility(effects=[CustomEffect(fn=_bounty_posting)])


@card_ability("SHD", "233")
def _evacuate():
    """SHD_233 — Evacuate (Event, Tactic, cost 6): "Return each non-leader unit to
    its owner's hand."  ``EACH_IN_PLAY`` auto-targets every non-leader unit in both
    arenas (either controller) — no player choice — and ReturnToHand bounces each to
    its owner's hand."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="any", kind="unit",
                                predicates=("non_leader",), fixed=EACH_IN_PLAY)),
    ])


def _altering_the_deal(state, source_ci, target_id, event_ctx):
    """Discard a captured card guarded by a friendly unit.

    Captured cards guarded by the controller's units live in the controller's
    ``capture_pile`` (tagged ``captured_by`` = the guarding unit's instance_id).
    Discarding a captured card sends it to its OWNER's (the enemy's) discard pile
    permanently.  The first such captured card is discarded (the first-card
    simplification — a bespoke among-captured-cards choice would need a new decision
    kind for a niche disruption event); fizzles cleanly if none is guarded."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    guard_ids = {
        ci.instance_id
        for arena in (ps.ground_arena, ps.space_arena) for ci in arena
    }
    for captured in list(ps.capture_pile):
        if captured.captured_by in guard_ids:
            ps.capture_pile.remove(captured)
            captured.captured_by = None
            captured.face_down = False
            captured.zone = Zone.DISCARD
            state.player_by_id(captured.owner_id).discard.append(captured)
            break
    return state


@card_ability("SHD", "243")
def _altering_the_deal_card():
    """SHD_243 — Altering the Deal (Event, Trick, cost 1): "Discard a captured card
    guarded by a friendly unit."  A CustomEffect over the controller's capture pile
    (see the first-card note)."""
    return EventAbility(effects=[CustomEffect(fn=_altering_the_deal)])


@card_ability("SHD", "244")
def _no_bargain():
    """SHD_244 — No Bargain (Event, Trick, cost 3): "Each opponent discards a card
    from their hand. Draw a card."  DiscardFromHand(chooser="opponent") drops the
    opponent's first card (the K-2SO SOR_145 first-card simplification), then the
    controller draws 1."""
    return EventAbility(effects=[
        DiscardFromHand(count=1, chooser="opponent"),
        DrawCards(count=1, player="controller"),
    ])


# ── shd-set:12 — Leaders & combat tricks ──────────────────────────────────────

@card_ability("SHD", "4")
def _rey_shd4():
    """SHD_4 — Rey (Leader, Force/Fringe, 2/6, Restore 3).

    Undeployed Action [1 resource, Exhaust]: "Give an Experience token to a unit
    with 2 or less power."  Deployed side: Restore 3 (keyword layer) + On Attack:
    "You may give an Experience token to a unit with 2 or less power."  Epic deploy
    is the standard leader-deploy machinery (no registration).  ``power_max=2``
    filters the token target to a unit with 2 or less (effective) power."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[GiveToken("Experience", TargetSpec(
                controller="any", kind="unit", power_max=2))],
            title="Give an Experience token to a unit with 2 or less power",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(
                controller="any", kind="unit", power_max=2))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _hondo_undeployed_smuggle(state, source_ci, target_id, event_ctx):
    """Hondo SHD_5 undeployed: "You may exhaust this leader.  If you do, give an
    Experience token to a unit."  Bundled in one CustomEffect so "If you do
    [exhaust]" binds (the Boba Fett JTL_9 pattern); the collector-choice token goes
    via push_select_token (max 1)."""
    source_ci.exhausted = True
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Experience", max_targets=1,
                      controller="any", kind="unit")
    return state


@card_ability("SHD", "5")
def _hondo_ohnaka():
    """SHD_5 — Hondo Ohnaka (Leader, Underworld, 3/7).

    Undeployed: "When you play a card using Smuggle: You may exhaust this leader.
    If you do, give an Experience token to a unit."  Deployed: Raid 1 (keyword
    layer) + "When you play a card using Smuggle: You may give an Experience token
    to a unit."  Both are ``WhenYouPlayCard(via_smuggle=True)`` controller-observers
    (the new via_smuggle filter — the printed WhenPlayedViaSmuggle only self-fires).
    The undeployed one pays an exhaust (gated ``SOURCE_READY`` so it is not offered
    while Hondo is exhausted); the deployed one is a plain optional GiveToken."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(via_smuggle=True),
            effects=[CustomEffect(fn=_hondo_undeployed_smuggle)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(via_smuggle=True),
            effects=[GiveToken("Experience", TargetSpec(controller="any", kind="unit"))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _make_jabba_grant(amount):
    """Grant the chosen unit a phase-scoped "Bounty — The next unit you play this
    phase costs ``amount`` less" via ``granted_bounties`` (resolved for the collector
    when that unit is defeated; see actions._resolve_granted_bounty)."""
    def _fn(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        res = state.find_instance(target_id)
        if res is None:
            return state
        _, unit = res
        unit.granted_bounties.append(f"next_unit_discount:{amount}")
        return state
    return _fn


def _jabba_record_captor(state, source_ci, target_id, event_ctx):
    """Jabba SHD_6 When Deployed — record the chosen "another friendly unit" as the
    captor (the Grand Admiral Thrawn SEC_193 two-CustomEffect capture composition,
    without the same-arena restriction)."""
    if target_id is None:
        return state
    event_ctx["jabba_captor_id"] = target_id
    return state


def _jabba_capture_enemy(state, source_ci, target_id, event_ctx):
    """Jabba SHD_6 When Deployed — the recorded friendly captor captures the chosen
    enemy non-leader unit."""
    if target_id is None:
        return state
    captor_id = event_ctx.get("jabba_captor_id")
    if not captor_id:
        return state
    from swu.engine.actions import _apply_capture
    return _apply_capture(state, captor_id, target_id)


@card_ability("SHD", "6")
def _jabba_the_hutt_shd6():
    """SHD_6 — Jabba the Hutt (Leader, Hutt/Underworld, 2/12).

    Undeployed Action [Exhaust]: "Choose a unit. For this phase, it gains: 'Bounty —
    The next unit you play this phase costs 1 resource less.'"  Deployed side: When
    Deployed: "Another friendly unit captures an enemy non-leader unit." + Action
    [Exhaust]: the same grant with a 2-resource discount.  The granted bounty reuses
    the phase-scoped ``granted_bounties`` seam (The Client SHD_31), with a new
    ``next_unit_discount:N`` key that records a pending NextPlayDiscount for the
    collector.  The capture is the Thrawn SEC_193 two-CustomEffect composition
    (choose captor, then capture an enemy non-leader; ``not_self`` = "another")."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_make_jabba_grant(1),
                target=TargetSpec(controller="any", kind="unit"))],
            title="Grant a unit a Bounty (next unit costs 1 less) this phase",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[
                CustomEffect(
                    fn=_jabba_record_captor,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      predicates=("not_self",))),
                CustomEffect(
                    fn=_jabba_capture_enemy,
                    target=TargetSpec(controller="enemy", kind="unit",
                                      predicates=("non_leader",))),
            ],
            deployed_only=True,
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_make_jabba_grant(2),
                target=TargetSpec(controller="any", kind="unit"))],
            title="Grant a unit a Bounty (next unit costs 2 less) this phase",
            deployed_only=True,
        ),
    ]


def _boba_fett_shd8_exhaust_buff(state, source_ci, target_id, event_ctx):
    """Boba Fett SHD_8 undeployed — exhaust this leader and give the chosen friendly
    unit +1/+0 for this phase, bound in one CustomEffect so "If you do [exhaust]"
    holds (the Kylo Ren SHD_141 CustomEffect.target + _make_modifier pattern)."""
    if target_id is None:
        return state
    if state.find_instance(target_id) is None:
        return state
    source_ci.exhausted = True
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=1, hp=0, duration=Duration.THIS_PHASE))
    return state


@card_ability("SHD", "8")
def _boba_fett_shd8():
    """SHD_8 — Boba Fett (Leader, Underworld, 4/7).

    Undeployed: "When you play a unit that has 1 or more keywords: You may exhaust
    this leader. If you do, give a friendly unit +1/+0 for this phase."  Deployed:
    "Each other friendly unit that has 1 or more keywords gets +1/+0."  The trigger
    is a ``WhenYouPlayCard(card_type="unit", has_any_keyword=True)`` observer (the
    new keyword-count filter), optional + gated ``SOURCE_READY``; the leading
    no-target CustomEffect exhausts Boba, then the targeted ModifyStats prompts for
    the friendly unit (the leading-side-effect-then-target order).  The deployed
    aura is a ConstantAbility over other friendly units with >=1 keyword (the new
    ``has_any_keyword`` predicate)."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="unit", has_any_keyword=True),
            effects=[CustomEffect(
                fn=_boba_fett_shd8_exhaust_buff,
                target=TargetSpec(controller="friendly", kind="unit"))],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self", "has_any_keyword")),
            effects=[StatBonus(power=1, hp=0)],
        ),
    ]


@card_ability("SHD", "11")
def _kylo_ren_shd11():
    """SHD_11 — Kylo Ren (Leader, First Order/Force, 5/4).

    Undeployed Action [Exhaust, discard a card from your hand]: "Give a unit +2/+0
    for this phase."  Deployed side: "This unit gets -1/-0 for each card in your
    hand."  The discard-a-card cost is ``DiscardCardCost``; the deployed self-debuff
    is a self-targeted ConstantAbility with a scaling ``StatBonus(power=-1,
    count="controller_hand_size")``."""
    from swu.abilities.registry import DiscardCardCost
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), DiscardCardCost()],
            effects=[ModifyStats(power=2, hp=0,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
            title="Give a unit +2/+0 for this phase",
            undeployed_only=True,
        ),
        # The self-debuff is active only while Kylo is deployed: the ConstantAbility
        # scan only sees arena sources, so an undeployed leader (in base_zone)
        # contributes nothing — no explicit deployed_only flag needed (the Moff
        # Gideon SHD_7 convention).
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=-1, hp=0, count="controller_hand_size")],
        ),
    ]


def _lom_pyke_attack(state, source_ci, target_id, event_ctx):
    """Lom Pyke SHD_32 On Attack: give a Shield to the chosen enemy unit; "if you
    do", give a Shield to a friendly unit (bound in one CustomEffect so declining
    the enemy shield skips the friendly one)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.tokens import attach_token
    from swu.engine.actions import push_select_token
    _, enemy = res
    attach_token(state, state.player_by_id(enemy.owner_id), enemy, "Shield")
    push_select_token(state, source_ci, token_type="Shield", max_targets=1,
                      controller="friendly", kind="unit")
    return state


@card_ability("SHD", "32")
def _lom_pyke():
    """SHD_32 — Lom Pyke (Unit, Underworld, 4/6, Smuggle): "On Attack: You may give
    a Shield token to an enemy unit. If you do, give a Shield token to a friendly
    unit."  Smuggle is the keyword layer.  An optional OnAttack whose CustomEffect
    targets an enemy unit; giving that shield then pushes a friendly-shield
    select_token — the "if you do" binding (declining the trigger gives neither)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(
            fn=_lom_pyke_attack,
            target=TargetSpec(controller="enemy", kind="unit"))],
        optional=True,
    )


@card_ability("SHD", "34")
def _supercommando_squad():
    """SHD_34 — Supercommando Squad (Unit, Mandalorian/Trooper, 4/4, Shielded):
    "While this unit is upgraded, it gains Sentinel."  Shielded is the keyword
    layer.  A self-targeted constant KeywordGrant gated by SOURCE_UPGRADED (the
    Protector of the Throne SHD_247 pattern — Shield/Experience tokens are upgrades
    and also switch it on)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


# ── shd-set:13 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("SHD", "35")
def _clan_saxon_gauntlet():
    """SHD_35 — Clan Saxon Gauntlet (Unit, Mandalorian/Transport/Vehicle, 4/5,
    Sentinel): "When this unit is attacked: You may give an Experience token to a
    unit (before damage is dealt)."  Sentinel is the keyword layer.  A ``WhenAttacked``
    trigger (fires before combat damage) whose optional GiveToken targets any unit."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[GiveToken("Experience", TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


@card_ability("SHD", "36")
def _first_light():
    """SHD_36 — First Light (Unit, Transport/Underworld/Vehicle, 4/7, Grit,
    Smuggle): "Grit.  Each other friendly non-leader unit gains Grit."  Grit on
    First Light itself is the keyword layer; the aura is a ConstantAbility granting
    Grit to every OTHER friendly non-leader unit (has_keyword reports it for the
    duration).  RESIDUAL (documented): the Smuggle cost rider "deal 4 damage to a
    friendly unit" is not enforced — the card is playable via Smuggle at its
    resource cost (the deferred smuggle-rider class)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self", "non_leader")),
        effects=[KeywordGrant("Grit", value=0)],
    )


@card_ability("SHD", "42")
def _concord_dawn_interceptors():
    """SHD_42 — Concord Dawn Interceptors (Unit, Fighter/Mandalorian/Vehicle, 1/4,
    Sentinel): "This unit gets +2/+0 while defending."  Sentinel is the keyword
    layer.  A self-targeted ConstantAbility with ``while_target_defending`` — the
    StatBonus applies to its target (SELF) only while that target is the current
    combat defender (the Jyn Erso SOR_18 field, here pointed at SELF for a
    self-buff-while-defending)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        while_target_defending=True,
    )


def _gentle_giant_heal(state, source_ci, target_id, event_ctx):
    """Gentle Giant SHD_48 On Attack: heal the chosen other unit by the damage
    currently on this unit ("up to" — capped at the target's own damage)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, target = res
    heal = min(source_ci.damage, target.damage)
    if heal > 0:
        target.damage -= heal
    return state


@card_ability("SHD", "48")
def _gentle_giant():
    """SHD_48 — Gentle Giant (Unit, Wookiee, 2/8, Grit): "On Attack: You may heal
    damage from another unit equal to the damage on this unit."  Grit is the
    keyword layer.  An optional OnAttack whose CustomEffect targets another unit and
    heals it by ``source.damage`` (capped at the target's damage — "heal up to")."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(
            fn=_gentle_giant_heal,
            target=TargetSpec(controller="any", kind="unit", predicates=("not_self",)))],
        optional=True,
    )


@card_ability("SHD", "52")
def _sugi():
    """SHD_52 — Sugi (Unit, Bounty Hunter/Underworld, 4/6, Smuggle): "While an enemy
    unit is upgraded, this unit gains Sentinel."  Smuggle is the keyword layer.  A
    self-targeted constant KeywordGrant gated by the new ENEMY_UNIT_UPGRADED
    condition (any enemy arena unit carries ≥1 upgrade)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.ENEMY_UNIT_UPGRADED),
    )


def _midnight_repairs(state, source_ci, target_id, event_ctx):
    """Midnight Repairs SHD_54: heal up to 8 total damage from any number of units
    (the Redemption SOR_52 distribute-heal seam, units only, no self-damage)."""
    from swu.engine.actions import push_distribute_heal
    push_distribute_heal(state, source_ci, 8, include_bases=False,
                         then_damage_self=False)
    return state


@card_ability("SHD", "54")
def _midnight_repairs_card():
    """SHD_54 — Midnight Repairs (Event, Tactic, cost 2): "Heal up to 8 total damage
    from any number of units."  A CustomEffect onto ``push_distribute_heal`` with
    ``include_bases=False`` / ``then_damage_self=False`` — the controller allocates
    up to 8 healing across its own damaged units (healing enemies is never
    beneficial, the standard distribute-heal scope)."""
    return EventAbility(effects=[CustomEffect(fn=_midnight_repairs)])


@card_ability("SHD", "59")
def _embo():
    """SHD_59 — Embo (Unit, Bounty Hunter/Underworld, 3/4): "When this unit completes
    an attack: If the defender was defeated, heal up to 2 damage from a unit."  An
    ``OnAttackDefeatsUnit`` trigger (fires only when the attack defeated the
    defender) whose optional Heal(2) heals up to 2 from any chosen unit."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[Heal(2, TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:14 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

def _covert_strength(state, source_ci, target_id, event_ctx):
    """Heal 2 from the chosen unit and give it an Experience token (one target)."""
    if target_id is None:
        return state
    from swu.engine import tokens
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, unit = result
    unit.damage = max(0, unit.damage - 2)
    tokens.attach_token(state, ps, unit, "Experience")
    return state


@card_ability("SHD", "75")
def _covert_strength_card():
    """SHD_75 — Covert Strength (Event, Tactic; Smuggle handled by the keyword
    engine): "Heal 2 damage from a unit and give an Experience token to it."  One
    CustomEffect.target so both the heal and the token land on the same chosen unit
    (resolve_effects prompts exactly once)."""
    return EventAbility(effects=[CustomEffect(
        fn=_covert_strength,
        target=TargetSpec(controller="any", kind="unit"))])


def _unexpected_escape(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen unit; then rescue (to its owner's hand) the first
    controller-owned captured card guarded by it."""
    from swu.engine.actions import _rescue_captured_card
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, guard = result
    guard.exhausted = True
    controller_id = source_ci.owner_id
    # "You may rescue a captured card guarded by that unit" — rescue the first
    # captive OWNED BY THE CONTROLLER (rescuing an enemy's captive is never
    # beneficial, so the optional collapses to the beneficial subset).  Rescue
    # returns the card to its owner's HAND (the CR rescue destination), unlike the
    # leave-play RELEASE (_release_captured_cards) which returns captives to arena.
    for ps in state.players:
        for captured in list(ps.capture_pile):
            if captured.captured_by != guard.instance_id:
                continue
            if captured.owner_id != controller_id:
                continue
            _rescue_captured_card(state, captured)
            return state  # "a captured card" — rescue exactly one
    return state


@card_ability("SHD", "76")
def _unexpected_escape_card():
    """SHD_76 — Unexpected Escape (Event, Trick): "Exhaust a unit. You may rescue a
    captured card guarded by that unit."  One CustomEffect.target: exhaust the chosen
    unit, then rescue one controller-owned captive it guards to that card's owner's
    hand."""
    return EventAbility(effects=[CustomEffect(
        fn=_unexpected_escape,
        target=TargetSpec(controller="any", kind="unit"))])


@card_ability("SHD", "86")
def _warbird_stowaway():
    """SHD_86 — Warbird Stowaway (Underworld; Smuggle handled by the keyword engine):
    "While you have the initiative, this unit gets +2/+0."  A self-targeted
    conditional ConstantAbility (StatBonus gated by CONTROLLER_HAS_INITIATIVE), read
    passively by compute_power (the Scimitar LOF_233 pattern)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


@card_ability("SHD", "87")
def _crosshair():
    """SHD_87 — Crosshair (Clone/Imperial/Trooper, 2/6): two Actions.
    [2 resources]: this unit gets +1/+0 for this phase.
    [Exhaust]: this unit deals damage equal to his power to an enemy ground unit
    (DealDamageEqualTo count="source_power")."""
    return [
        ActivatedAbility(
            costs=[PayResources(2)],
            effects=[ModifyStats(power=1, hp=0, target=TargetSpec(fixed=SELF),
                                 duration=Duration.THIS_PHASE)],
            title="+1/+0 for this phase",
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="enemy", kind="unit", arena="ground"),
                count="source_power")],
            title="Deal damage equal to power to an enemy ground unit",
        ),
    ]


@card_ability("SHD", "97")
def _freetown_backup():
    """SHD_97 — Freetown Backup (Fringe; Smuggle handled by the keyword engine):
    "On Attack: Give another friendly unit +2/+2 for this phase."  The Armed to the
    Teeth SHD_175 pattern (controller="friendly", not_self), +2/+2 THIS_PHASE."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(
            power=2, hp=2,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            duration=Duration.THIS_PHASE)],
    )


def _adelphi_when_played(state, source_ci, target_id, event_ctx):
    """Push an optional granted attack; +2/+0 only if the controller has the
    initiative at resolution (initiative is fixed for the round, so reading it now
    is equivalent to reading it during the attack)."""
    from swu.engine.actions import push_granted_attack
    has_init = state.initiative_holder == state.player_index(source_ci.owner_id)
    push_granted_attack(state, source_ci, power_bonus=2 if has_init else 0,
                        hp_bonus=0, optional=True)
    return state


@card_ability("SHD", "101")
def _adelphi_patrol_wing():
    """SHD_101 — Adelphi Patrol Wing (Fighter/New Republic/Vehicle, 4/6): "When
    Played: You may attack with a unit. If you have the initiative, it gets +2/+0
    for this attack."  A thin CustomEffect adapter onto push_granted_attack; the
    conditional bonus is decided from the fixed round initiative at resolution."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_adelphi_when_played)],
    )


def _general_rieekan(state, source_ci, target_id, event_ctx):
    """Choose a friendly unit: if it has Sentinel, give it an Experience token;
    otherwise it gains Sentinel for this phase (a phase-scoped keyword modifier)."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, unit = result
    from swu.engine.keywords import has_keyword, Keyword
    if has_keyword(state, unit, Keyword.SENTINEL):
        from swu.engine import tokens
        tokens.attach_token(state, ps, unit, "Experience")
    else:
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=unit.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
    return state


@card_ability("SHD", "103")
def _general_rieekan_card():
    """SHD_103 — General Rieekan (Official/Rebel, Sentinel, 5/7): "When Played/On
    Attack: Choose a friendly unit. If it has Sentinel, give an Experience token to
    it. Otherwise, it gains Sentinel for this phase."  A conditional-magnitude
    CustomEffect.target (the Zeb LAW_45 pattern) resolving both clauses from the one
    chosen unit; registered on both the When Played and On Attack triggers."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_general_rieekan,
                                target=TargetSpec(controller="friendly", kind="unit"))]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_general_rieekan,
                                target=TargetSpec(controller="friendly", kind="unit"))]),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:15 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("SHD", "104")
def _inspiring_mentor():
    """SHD_104 — Inspiring Mentor (Upgrade, Innate; attach to a non-Vehicle unit):
    "Attached unit gains: 'On Attack/When Defeated: Give an Experience token to
    another friendly unit.'"  Two GrantedAbility (the Armed to the Teeth SHD_175
    pattern) resolving from the host — one on the host's attack, one on its defeat
    (collected from the defeated host's snapshotted upgrades).  "another friendly
    unit" = controller="friendly", not_self (relative to the host)."""
    def _grant():
        return GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit", predicates=("not_self",)))
    return [
        GrantedAbility(ability=TriggerAbility(trigger=OnAttack(), effects=[_grant()])),
        GrantedAbility(ability=TriggerAbility(trigger=WhenDefeated(), effects=[_grant()])),
    ]


@card_ability("SHD", "112")
def _gamorrean_retainer():
    """SHD_112 — Gamorrean Retainer (Underworld, 3/2): "While you control another
    Command unit, this unit gains Sentinel."  A self-targeted conditional
    ConstantAbility (KeywordGrant Sentinel) gated by CONTROLLER_HAS_OTHER_ASPECT_UNIT
    ("Command") — Command is an aspect; the keyword sanitiser strips the mis-tagged
    printed Sentinel (the Protector SHD_247 pattern)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT, "Command"),
    )


@card_ability("SHD", "116")
def _outlaw_corona():
    """SHD_116 — Outlaw Corona (Capital Ship/Underworld/Vehicle, 3/5): printed
    "Bounty — Put the top card of your deck into play as a resource."  A WhenDefeated
    is_bounty trigger resolving for the collector; reuses the Price on Your Head
    SHD_125 bounty (the collector ramps the top of their own deck)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_price_on_your_head_bounty)],
        is_bounty=True,
    )


@card_ability("SHD", "117")
def _reputable_hunter():
    """SHD_117 — Reputable Hunter (Bounty Hunter, 3/4): "If an enemy unit has a
    Bounty, this unit costs 1 resource less to play."  A declarative CostReduction
    gated by ENEMY_CONTROLS_BOUNTY_UNIT (read by the play-cost path)."""
    return CostReduction(
        amount=1,
        condition=ConditionCheck(Condition.ENEMY_CONTROLS_BOUNTY_UNIT),
    )


def _arquitens_resource(state, source_ci, target_id, event_ctx):
    """Put the just-defeated (non-leader) defender into play as a resource under the
    attacker's controller.  The defender is now in its owner's discard (threaded via
    event_ctx["attack_defeated_defender"]); relocate it facedown into the source
    controller's resource row (owner_id unchanged, control follows the holder — the
    control-change convention)."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    from swu.cards.models import Leader
    did = (event_ctx or {}).get("attack_defeated_defender")
    if not did:
        return state
    for ps in state.players:
        for card in list(ps.discard):
            if card.instance_id != did:
                continue
            if isinstance(card.card_def, Leader):
                return state   # "non-leader unit" only
            ps.discard.remove(card)
            controller_ps = state.player_by_id(source_ci.owner_id)
            card.zone = Zone.RESOURCES
            card.face_down = True
            card.exhausted = False
            card.damage = 0
            controller_ps.resources.append(card)
            state.event_log.append(CardResourced(
                player_id=controller_ps.player_id,
                instance_id=card.instance_id,
                card_name=card.card_def.display_name,
            ))
            return state
    return state


@card_ability("SHD", "122")
def _arquitens_assault_cruiser():
    """SHD_122 — Arquitens Assault Cruiser (Capital Ship/Vehicle, 7/8; Ambush is the
    keyword engine): "When this unit attacks and defeats a non-leader unit: Put the
    defeated unit into play as a resource under your control."  An OnAttackDefeatsUnit
    trigger whose CustomEffect relocates the defeated defender (found via the new
    event_ctx["attack_defeated_defender"] key) into the controller's resource row."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[CustomEffect(fn=_arquitens_resource)],
    )


def _punishing_one_ready(state, source_ci, target_id, event_ctx):
    """Ready the source and mark its once-per-round trigger used (the Toro Calican
    SHD_239 / Migs Mayfeld SHD_163 marker pattern)."""
    result = state.find_instance(source_ci.instance_id)
    if result is not None:
        _, unit = result
        unit.exhausted = False
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("SHD", "137")
def _punishing_one():
    """SHD_137 — Punishing One (Transport/Underworld/Vehicle, 3/4): "When an upgraded
    enemy unit is defeated: You may ready this unit. Use this ability only once each
    round."  A WhenUnitDefeated observer filtered to enemy units that were upgraded
    at the moment of defeat (the new ``defeated_upgraded`` predicate reads the
    snapshot in event_ctx["defeated_upgrades"]).  ``optional`` is the "you may"; the
    shared SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE gate + marker enforce once/round
    (declining spends nothing)."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(
            controller="enemy", kind="unit", predicates=("defeated_upgraded",))),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        effects=[CustomEffect(fn=_punishing_one_ready)],
    )


@card_ability("SHD", "140")
def _trandoshan_hunters():
    """SHD_140 — Trandoshan Hunters (Bounty Hunter/Underworld, 6/4; Overwhelm is the
    keyword engine): "When Played: If an enemy unit has a Bounty, give an Experience
    token to this unit."  A WhenPlayed trigger gated by ENEMY_CONTROLS_BOUNTY_UNIT
    giving an Experience token to itself."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.ENEMY_CONTROLS_BOUNTY_UNIT),
        effects=[GiveToken("Experience", TargetSpec(kind="unit", fixed=SELF))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:16 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

def _headhunting(state, source_ci, target_id, event_ctx):
    """Adapter: push a capped-repeat granted attack (up to 3 units, no bases; each
    Bounty Hunter attacker gets +2/+0)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, hp_bonus=0,
                        optional=True, repeat=True, repeat_max=3,
                        no_base=True, bonus_trait="Bounty Hunter")
    return state


@card_ability("SHD", "145")
def _headhunting_card():
    """SHD_145 — Headhunting (Event, Tactic): "Attack with up to 3 units (one at a
    time). They can't attack bases for these attacks. Each Bounty Hunter that attacks
    this way gets +2/+0 for its attack."  A thin adapter onto push_granted_attack
    with the new ``repeat_max=3`` cap, ``no_base``, and ``bonus_trait="Bounty
    Hunter"`` (the bonus applies only to Bounty Hunter attackers)."""
    return EventAbility(effects=[CustomEffect(fn=_headhunting)])


def _valiant_on_attack(state, source_ci, target_id, event_ctx):
    """If the defending player (the opponent) controls more resources than the
    source's controller, apply +2/+0 to the source for this attack."""
    my_ps = state.player_by_id(source_ci.owner_id)
    opp_ps = state.players[1 - state.player_index(source_ci.owner_id)]
    if len(opp_ps.resources) > len(my_ps.resources):
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=source_ci.instance_id,
            kind="stats", value={"power": 2, "hp": 0}, duration="this_attack"))
    return state


@card_ability("SHD", "151")
def _valiant_assault_ship():
    """SHD_151 — Valiant Assault Ship (Fringe/Transport/Vehicle, 3/4; Saboteur is the
    keyword engine): "On Attack: If the defending player controls more resources than
    you, this unit gets +2/+0 for this attack."  A CustomEffect reading the resource
    comparison and applying a this_attack self stat modifier."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_valiant_on_attack)])


def _heroic_resolve_attack(state, source_ci, target_id, event_ctx):
    """Host attacks with +4/+0 and Overwhelm for this attack (SHD_155's granted
    Action).  ``source_ci`` is the HOST — the granted ability resolves from it — so
    the attack is pinned to the host via ``attacker_id``."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(
        state, source_ci, power_bonus=4, hp_bonus=0,
        grant_keywords=["Overwhelm"], attacker_id=source_ci.instance_id)
    return state


@card_ability("SHD", "155")
def _heroic_resolve():
    """SHD_155 — Heroic Resolve (Upgrade): "Attached unit gains: 'Action [2
    resources, defeat a Heroic Resolve on this unit]: Attack with this unit. It gets
    +4/+0 and gains Overwhelm for this attack.'"

    The first upgrade-granted ACTIVATED ability in the campaign (the shd-set:16
    framework session): a GrantedAbility wrapping an ActivatedAbility.  The trigger
    collector skips it; instead the attached-upgrade activated-ability scan in
    ``legal_actions`` surfaces the Action, addressed by the UPGRADE's instance_id.
    Its ``DefeatSelf`` cost defeats THIS upgrade (``_defeat_attached_upgrade``, not
    the host), and the effect resolves from the host — a lone CustomEffect onto
    push_granted_attack pinning the attacker to the host with +4/+0 and a
    for-this-attack Overwhelm grant."""
    return GrantedAbility(ability=ActivatedAbility(
        costs=[PayResources(2), DefeatSelf()],
        effects=[CustomEffect(fn=_heroic_resolve_attack)],
    ))


@card_ability("SHD", "169")
def _clan_challengers():
    """SHD_169 — Clan Challengers (Mandalorian/Trooper, 3/6; Raid 3 is the keyword
    engine): "While this unit is upgraded, it gains Overwhelm."  A self-targeted
    conditional ConstantAbility (KeywordGrant Overwhelm) gated by SOURCE_UPGRADED —
    the Protector SHD_247 pattern."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Overwhelm", value=0)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


@card_ability("SHD", "182")
def _bravado():
    """SHD_182 — Bravado (Event, Innate): "If you've defeated an enemy unit this
    phase, this event costs 2 resources less to play. Ready a unit."  A declarative
    CostReduction gated by ENEMY_UNIT_DEFEATED_THIS_PHASE plus a targeted ReadyCard."""
    return [
        CostReduction(
            amount=2,
            condition=ConditionCheck(Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE),
        ),
        EventAbility(effects=[ReadyCard(TargetSpec(controller="any", kind="unit"))]),
    ]


@card_ability("SHD", "183")
def _kintan_intimidator():
    """SHD_183 — Kintan Intimidator (Underworld, 1/4): "On Attack: Exhaust the
    defender."  An OnAttack trigger with ExhaustCard(fixed=DEFENDER) — resolves to
    the current defender from event_ctx, a no-op on a base attack."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(kind="unit", fixed=DEFENDER))],
    )


def _doctor_evazan_bounty(state, source_ci, target_id, event_ctx):
    """Collector readies up to 12 of their own exhausted resources (deterministic —
    resources are fungible, so no choice; the Wanted SHD_221 bounty, cap 12)."""
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    ps = state.player_by_id(collector)
    readied = 0
    for r in ps.resources:
        if readied >= 12:
            break
        if r.exhausted:
            r.exhausted = False
            readied += 1
    return state


@card_ability("SHD", "185")
def _doctor_evazan():
    """SHD_185 — Doctor Evazan (Underworld, 3/3; Shielded is the keyword engine):
    printed "Bounty — Ready up to 12 resources."  A WhenDefeated is_bounty trigger
    resolving for the collector, who readies up to 12 of their own resources (the
    Wanted SHD_221 collector-ready-resources pattern)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_doctor_evazan_bounty)],
        is_bounty=True,
    )


# ── Combat tricks, buffs & tempo (shd-set:17) ─────────────────────────────────
# Seven "no flag" ability cards.  Two conditional self keyword-grants (the
# Hunting Nexu SHD_168 / Protector of the Throne SHD_247 pattern — the printed
# keyword is stripped by the sanitiser's conditional-self-grant rule so the
# ability owns it); two name-anthem auras (the new TargetSpec.names filter); a
# When-Played ready with a DYNAMIC power cap (the new power_max_count target
# filter); an upgrade that forbids its host from readying (the new
# ReadyRestriction-on-upgrade seam) and exhausts it; a rescue-or-shield When
# Played; and an On-Attack ready-a-resource.

@card_ability("SHD", "186")
def _hunter_of_the_haxion_brood():
    """SHD_186 — While an enemy unit has a Bounty, this unit gains Shielded.

    A self-targeted constant KeywordGrant gated by ENEMY_CONTROLS_BOUNTY_UNIT.
    The printed "Shielded" is stripped by the keyword sanitiser (implemented
    conditional self-grant), so has_keyword reports Shielded — and the Shielded
    enter-play shield token is given — only while an enemy Bounty unit is in
    play."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Shielded", value=0)],
        condition=ConditionCheck(Condition.ENEMY_CONTROLS_BOUNTY_UNIT),
    )


@card_ability("SHD", "188")
def _four_lom():
    """SHD_188 — Each friendly unit named Zuckuss gets +1/+1 and gains Ambush.

    A name-anthem: a ConstantAbility over every friendly unit named "Zuckuss"
    (the new TargetSpec.names filter) granting a StatBonus and Ambush, read
    passively by compute_power/has_keyword.  4-LOM's own printed Ambush is the
    keyword engine (its keyword bar)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", names=("Zuckuss",)),
        effects=[StatBonus(power=1, hp=1), KeywordGrant("Ambush", value=0)],
    )


@card_ability("SHD", "189")
def _slavers_freighter():
    """SHD_189 — When Played: You may ready another unit with power equal to or
    less than the number of upgrades on enemy units.

    A ReadyCard whose target carries the dynamic power_max_count filter
    ("enemy_units_upgrade_count") — every attached upgrade (token upgrades
    included) on an enemy unit raises the cap.  "Another unit" = any unit other
    than this one (not_self); optional ("you may"), so it fizzles with no eligible
    unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(controller="any", kind="unit",
                                      predicates=("not_self",),
                                      power_max_count="enemy_units_upgrade_count"))],
        optional=True,
    )


@card_ability("SHD", "190")
def _zuckuss():
    """SHD_190 — Each friendly unit named 4-LOM gets +1/+1 and gains Saboteur.

    The name-anthem mirror of 4-LOM (SHD_188): a ConstantAbility over every
    friendly unit named "4-LOM" granting a StatBonus and Saboteur.  Zuckuss's own
    printed Saboteur is the keyword engine."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", names=("4-LOM",)),
        effects=[StatBonus(power=1, hp=1), KeywordGrant("Saboteur", value=0)],
    )


def _frozen_in_carbonite_exhaust(state, source_ci, target_id, event_ctx):
    """When Played: exhaust the attached host unit (its id is threaded through the
    upgrade play context)."""
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        result = state.find_instance(host_id)
        if result is not None:
            _, host = result
            host.exhausted = True
    return state


@card_ability("SHD", "193")
def _frozen_in_carbonite():
    """SHD_193 — Frozen in Carbonite (Upgrade, Condition; attach to a non-leader
    unit): "Attached unit can't ready.  When Played: Exhaust attached unit."

    The "attach to a non-leader unit" restriction is the engine upgrade-target
    parser.  The residual is two specs: an unconditional ReadyRestriction (carried
    by the upgrade, read by _ready_forbidden against the host — so the host stays
    tapped through every regroup while frozen) and a WhenPlayed trigger that
    exhausts the host immediately so the lock bites the turn it lands."""
    return [
        ReadyRestriction(condition=None),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_frozen_in_carbonite_exhaust)],
        ),
    ]


def _l337_when_played(state, source_ci, target_id, event_ctx):
    """Rescue the first friendly captured card (return it to its owner's hand); if
    there is none to rescue, give a Shield token to L3-37 instead.

    "You may rescue a captured card. If you don't, give a Shield token to this
    unit."  Rescuing a controller-owned captive (a whole card back to hand) is
    strictly better than a shield, so the "you may" collapses to auto-rescue when
    a friendly captive exists; the shield is the "if you don't" fallback when
    there is nothing to rescue (the only realisable case in practice)."""
    from swu.engine.state import Zone
    from swu.engine.events import UnitReturnedFromCapture
    from swu.engine import tokens
    controller_id = source_ci.owner_id
    for ps in state.players:
        for captured in list(ps.capture_pile):
            if captured.owner_id != controller_id:
                continue  # rescuing an enemy's captive is never beneficial
            ps.capture_pile.remove(captured)
            owner_ps = state.player_by_id(captured.owner_id)
            captor_id = captured.captured_by
            captured.captured_by = None
            captured.face_down = False
            captured.damage = 0
            captured.exhausted = False
            captured.zone = Zone.HAND
            owner_ps.hand.append(captured)
            state.event_log.append(UnitReturnedFromCapture(
                instance_id=captured.instance_id,
                card_name=captured.card_def.display_name,
                owner_id=captured.owner_id,
                captor_instance_id=captor_id,
            ))
            return state  # rescued one captured card — no shield
    tokens.attach_token(state, state.player_by_id(controller_id), source_ci, "Shield")
    return state


@card_ability("SHD", "197")
def _l3_37():
    """SHD_197 — When Played: You may rescue a captured card.  If you don't, give a
    Shield token to this unit.  (Smuggle handled by the keyword engine.)

    One inline CustomEffect (no player-chosen target): rescue the first friendly
    captive if any, else shield this unit — see the helper for the "you may"
    simplification."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_l337_when_played)],
    )


def _coruscant_dissident_attack(state, source_ci, target_id, event_ctx):
    """On Attack: ready one of the controller's exhausted resources.  Resources are
    fungible and readying one is never adverse, so the "you may" resolves inline
    (the Wanted SHD_221 ready-resource pattern)."""
    ps = state.player_by_id(source_ci.owner_id)
    for r in ps.resources:
        if r.exhausted:
            r.exhausted = False
            break
    return state


@card_ability("SHD", "199")
def _coruscant_dissident():
    """SHD_199 — On Attack: You may ready a resource."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_coruscant_dissident_attack)],
    )


# ── Combat tricks, buffs & tempo (shd-set:18) ─────────────────────────────────
# Five of the seven cards compose from existing primitives (plus two small
# additive engine seams — neither touching decision/resolution machinery):
#   * SHD_204 Millennium Falcon — the new ``KeywordIfPlayedFromHand`` marker
#     (grant a keyword only on a hand play; the printed Ambush the API mistags is
#     stripped by keyword-sanitiser rule 6).
#   * SHD_208 Final Showdown — the new ``game_memory.lose_at_regroup`` schedule
#     (a player forced to lose at the next regroup start).
# The remaining two cards are FLAGGED escalations for a dedicated framework
# session (see the bottom of this block): SHD_205 (opponent-DECIDED modal whose
# second mode has the controller perform a granted attack — decision machinery)
# and SHD_213 (take control of an enemy RESOURCE with a leave-play reversion — a
# resource-control subsystem the engine has never modelled).


@card_ability("SHD", "201")
def _principled_outlaw():
    """SHD_201 — On Attack: You may exhaust a ground unit.  (Smuggle is the keyword
    engine.)

    A plain optional OnAttack ExhaustCard targeting any ground-arena unit (either
    player's).  "You may" = ``optional`` (declinable, and auto-declined by the
    resolver when no ground unit exists)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        arena="ground"))],
        optional=True,
    )


@card_ability("SHD", "204")
def _millennium_falcon():
    """SHD_204 — If you play this unit from your hand, it gains Ambush.  (Smuggle is
    the keyword engine.)

    The new ``KeywordIfPlayedFromHand`` marker: ``actions._put_unit_in_play`` grants
    Ambush (before the enter-play keyword bus, so it triggers on entry) only on a
    hand play — a Smuggle play (from the resource zone) does not.  The printed
    Ambush the API mistags on this card is stripped by keyword-sanitiser rule 6, so
    the marker — not an always-on printed bar — owns it."""
    return KeywordIfPlayedFromHand("Ambush")


def _final_showdown(state, source_ci, target_id, event_ctx):
    """Ready each unit the controller controls, then schedule the controller to lose
    the game at the start of the next regroup phase (``game_memory.lose_at_regroup``,
    consumed in ``actions._enter_regroup``).  Readying is done directly (the
    ready-resources convention); a deployed leader in an arena is a unit and is
    readied too."""
    ps = state.player_by_id(source_ci.owner_id)
    for ci in list(ps.ground_arena) + list(ps.space_arena):
        ci.exhausted = False
    state.game_memory.lose_at_regroup.add(source_ci.owner_id)
    return state


@card_ability("SHD", "208")
def _final_showdown_event():
    """SHD_208 — Final Showdown (Event, Gambit): Ready each unit you control.  At the
    start of the regroup phase, you lose the game.

    One inline CustomEffect (no player-chosen target): ready every friendly unit and
    add the controller to ``game_memory.lose_at_regroup``, which ``_enter_regroup``
    consumes at the next regroup start by forcing that player's base defeated."""
    return EventAbility(effects=[CustomEffect(fn=_final_showdown)])


def _fugitive_wookiee_bounty(state, source_ci, target_id, event_ctx):
    """Bounty — Exhaust a unit (resolves for the collector = the OPPONENT of whoever
    controlled this unit at death).  The collector exhausts a unit; the target is
    auto-picked as the collector's best READY opposing unit (the documented
    auto-exhaust simplification — Xanadu Blood SHD_191), which is exactly the unit a
    rational collector would exhaust."""
    controller_id = event_ctx.get("defeated_controller_id", source_ci.owner_id)
    controller_idx = state.player_index(controller_id)
    # Collector = opponent of the controller; the collector's enemies = the
    # controller's own side (index controller_idx).
    victim_side = state.players[controller_idx]
    enemies = list(victim_side.ground_arena) + list(victim_side.space_arena)
    pool = [u for u in enemies if not u.exhausted] or enemies
    if pool:
        victim = max(pool, key=lambda u: getattr(u.card_def, "power", 0) or 0)
        victim.exhausted = True
    return state


@card_ability("SHD", "211")
def _fugitive_wookiee():
    """SHD_211 — Fugitive Wookiee (Wookiee, 3/3): "Bounty — Exhaust a unit."

    A standard ``is_bounty`` WhenDefeated trigger resolving for the collector, whose
    exhaust target is auto-picked (see ``_fugitive_wookiee_bounty`` — the Doctor
    Evazan SHD_185 collector-resolves + Xanadu Blood SHD_191 auto-exhaust patterns)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_fugitive_wookiee_bounty)],
        is_bounty=True,
    )


@card_ability("SHD", "212")
def _privateer_scyk():
    """SHD_212 — While you control another Cunning unit, this unit gains Shielded.
    (Shielded's shield token is given when the condition holds as it enters play.)

    A self-targeted constant KeywordGrant gated by CONTROLLER_HAS_OTHER_ASPECT_UNIT
    (param="Cunning"; source-excludes this unit, so "another").  The printed
    Shielded is stripped by the keyword sanitiser's conditional-self-grant rule, so
    has_keyword reports Shielded — and the enter-play shield is given — only while
    the controller holds another Cunning unit (the Hunter of the Haxion Brood
    SHD_186 pattern)."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Shielded", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Cunning"),
    )


# ── shd-set:18 framework cards (the two escalations, now built) ───────────────────
#   * SHD_205 Let the Wookiee Win — an OPPONENT-decided modal whose second mode
#     hands a granted attack back to the CONTROLLER (new "let_wookiee_win" decision
#     kind: a cross-decider two-stage decision chaining into push_granted_attack).
#   * SHD_213 DJ — take control of an enemy RESOURCE with a leave-play reversion
#     (new actions.change_resource_control + the _revert_orphaned_resource_control
#     settle-time backstop; resource control is implicit, like unit control).


def _dj_steal_resource(state, source_ci, target_id, event_ctx):
    """When played using Smuggle: take control of an enemy resource, linked to DJ so
    it reverts when DJ leaves play.

    Auto-picks a READY enemy resource (falling back to any) — the documented
    auto-pick simplification (Xanadu Blood SHD_191): a rational controller steals a
    resource they can spend now, which also denies the opponent an *available* one.
    ``source_ci.owner_id`` is the controller (a Smuggle play is from your own
    resource zone)."""
    from swu.engine.actions import change_resource_control
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.resources:
        return state
    pool = [r for r in opp.resources if not r.exhausted] or list(opp.resources)
    change_resource_control(state, pool[0], source_ci.owner_id,
                            link_to=source_ci.instance_id)
    return state


@card_ability("SHD", "213")
def _dj():
    """SHD_213 — DJ (Underworld, 3/5, Smuggle [7 Cunning Cunning]): "When played
    using Smuggle: Take control of an enemy resource.  When this unit leaves play,
    that resource's owner takes control of it."

    A WhenPlayedViaSmuggle trigger (fires only on a Smuggle play, not a hand play —
    the Han Solo SHD_13 / shd-han-solo:01 Smuggle precedent) whose inline
    CustomEffect relocates an enemy resource via the new resource-control seam and
    links it to DJ; the ``_revert_orphaned_resource_control`` settle sweep returns
    it to its owner once DJ is no longer in play."""
    return TriggerAbility(
        trigger=WhenPlayedViaSmuggle(),
        effects=[CustomEffect(fn=_dj_steal_resource)],
    )


def _let_wookiee_win_push(state, source_ci, target_id, event_ctx):
    """Push the opponent-decided modal (see actions.push_let_wookiee_win)."""
    from swu.engine.actions import push_let_wookiee_win
    push_let_wookiee_win(state, source_ci)
    return state


@card_ability("SHD", "205")
def _let_wookiee_win():
    """SHD_205 — Let the Wookiee Win (Trick event, cost 2): "An opponent chooses
    one: [You ready up to 6 resources] / [You ready a friendly unit.  If it's a
    Wookiee unit, attack with it.  It gets +2/+0 for this attack]."

    The OPPONENT picks the mode (a cross-decider modal — push_modal is
    controller-only), then the CONTROLLER executes it.  Mode "ready_resources" readies
    up to 6 of the controller's exhausted resources (fungible, resolved directly);
    mode "ready_attack" advances to a controller stage that readies a chosen friendly
    unit and, when it is a Wookiee, chains into push_granted_attack (+2/+0).  See the
    new "let_wookiee_win" decision kind in actions.py."""
    return EventAbility(effects=[CustomEffect(fn=_let_wookiee_win_push)])


# ── Combat tricks, buffs & tempo (shd-set:19) ─────────────────────────────────
# Five cards composed from existing primitives plus a handful of small, additive
# engine seams (all registered where the existing machinery lives): the
# WhenYouPlayCard ``non_unit`` filter, the ``pay_or_exhaust`` ``pay_amount``
# generalisation, the ``granted_attack`` ``cross_arena`` / ``bonus_if_defender_ground``
# fields, and the ``WhenEnemyAttacksYourBase`` observer trigger.


def _tobias_beckett_exhaust(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen unit and mark the once-per-round trigger used ("Use this
    ability only once each round" — declining does not spend the use)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is not None:
        res[1].exhausted = True
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("SHD", "217")
def _tobias_beckett():
    """SHD_217 — Tobias Beckett (Unit, Underworld, 4/5, Smuggle): "When you play a
    non-unit card: You may exhaust a unit that costs the same as or less than the
    card you played. Use this ability only once each round."

    The Tactical Droid Commander TWI_184 pattern (WhenYouPlayCard + the
    ``cost_le_event_threshold`` predicate off ``event_ctx["cost_le_threshold"]``)
    with two additions: the new ``non_unit`` filter (fires only for a played
    event/upgrade, and records the played card's cost like the other filters), and
    the Toro Calican SHD_239 once-per-round gate — the payoff is one
    ``CustomEffect.target`` that exhausts the chosen unit (any controller) and marks
    ``{iid}:trig`` used, so declining the optional trigger does not spend the
    round's use.  Smuggle is the keyword engine."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(non_unit=True),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        effects=[CustomEffect(
            fn=_tobias_beckett_exhaust,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("cost_le_event_threshold",)))],
    )


def _look_the_other_way(state, source_ci, target_id, event_ctx):
    """Push the pay-2-or-exhaust decision to the chosen unit's controller."""
    if target_id is None:
        return state
    from swu.engine.actions import push_pay_or_exhaust
    push_pay_or_exhaust(state, target_id, pay_amount=2)
    return state


@card_ability("SHD", "227")
def _look_the_other_way_card():
    """SHD_227 — Look the Other Way (Event, Trick, cost 0): "Exhaust a unit unless
    its controller pays 2 resources."

    The controller chooses any unit; the decision is then addressed to that unit's
    controller (Eye of Aldhani SEC_73 ``pay_or_exhaust`` machinery, generalised with
    the new ``pay_amount`` context field): pay 2 to keep it ready, or let it be
    exhausted."""
    return EventAbility(effects=[
        CustomEffect(fn=_look_the_other_way,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


def _swoop_down(state, source_ci, target_id, event_ctx):
    """Push a space-unit granted attack that may reach the ground arena and gets a
    conditional bonus vs a ground unit (see push_granted_attack cross_arena /
    bonus_if_defender_ground)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(
        state, source_ci,
        power_bonus=2, hp_bonus=0,
        attacker_arena="space",
        grant_keywords=["Saboteur"],
        cross_arena=True,
        bonus_if_defender_ground=True,
        defender_power_bonus=-2,
        defender_hp_bonus=0,
    )
    return state


@card_ability("SHD", "230")
def _swoop_down_card():
    """SHD_230 — Swoop Down (Event, Tactic, cost 1): "Attack with a space unit. It
    gains Saboteur and can attack ground units for this attack. If it attacks a
    ground unit, it gets +2/+0 and the defender gets −2/−0 for this attack."

    A ``granted_attack`` restricted to a space attacker (``attacker_arena="space"``)
    that grants Saboteur for the attack and carries the two new granted-attack
    fields: ``cross_arena`` (the space attacker may target ground units this attack)
    and ``bonus_if_defender_ground`` (the +2/+0 attacker bonus AND the −2/−0 defender
    debuff apply only when the chosen defender is a ground unit).  LIMITATION: the
    granted Saboteur is a this-attack modifier applied at resolution, so it does not
    bypass Sentinel during defender *enumeration* (a documented granted-keyword
    edge, like Shoot First's First Strike)."""
    return EventAbility(effects=[CustomEffect(fn=_swoop_down)])


def _relentless_choose_captor(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly captor + its cost (the cost ceiling for the
    captured unit), and give it a Shield now if it is a Bounty Hunter (that clause
    is independent of whether an enemy is actually captured)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    captor_ps, captor = res
    event_ctx["captor_id"] = target_id
    event_ctx["cost_le_threshold"] = getattr(captor.card_def, "cost", None)
    from swu.engine.traits import has_trait
    if has_trait(state, captor, "Bounty Hunter"):
        from swu.engine.tokens import attach_token
        attach_token(state, captor_ps, captor, "Shield")
    return state


def _relentless_capture(state, source_ci, target_id, event_ctx):
    """The recorded captor captures the chosen enemy non-leader unit."""
    captor_id = event_ctx.get("captor_id")
    if captor_id is None or target_id is None:
        return state
    from swu.engine.actions import _apply_capture
    _apply_capture(state, captor_id, target_id)
    return state


@card_ability("SHD", "232")
def _relentless_pursuit():
    """SHD_232 — Relentless Pursuit (Event, Tactic, cost 3): "Choose a friendly
    unit. It captures an enemy non-leader unit that costs the same as or less than
    it. If the friendly unit is a Bounty Hunter, give a Shield token to it."

    Two dependent ``CustomEffect.target``s sharing the resolve_effects ``event_ctx``
    (the Take Captive SHD_131 pattern): the first picks the friendly captor, records
    its cost into ``event_ctx["cost_le_threshold"]`` (the ceiling for the captured
    unit) and, if the captor is a Bounty Hunter, gives it a Shield immediately (that
    clause is unconditional on capturing); the second picks an enemy non-leader unit
    whose cost is ≤ the captor's (``cost_le_event_threshold``) and captures it via
    ``_apply_capture`` (the-mandalorian:07).  No friendly captor ⇒ nothing; no
    eligible enemy ⇒ the Shield still lands but no capture."""
    return EventAbility(effects=[
        CustomEffect(fn=_relentless_choose_captor,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_relentless_capture,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader", "cost_le_event_threshold"))),
    ])


@card_ability("SHD", "241")
def _kragan_gorr():
    """SHD_241 — Kragan Gorr (Unit, Underworld, 6/6): "When an enemy unit attacks
    your base: Give a Shield token to a friendly unit in the same arena as the
    attacker."

    A ``WhenEnemyAttacksYourBase`` observer (the new base-attack observer trigger,
    collected at the existing base-attack ``fire_triggered_abilities`` site): the
    matcher records the attacker's arena in ``event_ctx["same_arena"]``, and the one
    ``GiveToken`` targets a friendly unit in that arena (the ``same_arena_as_event``
    predicate, Haymaker LAW_168).  Mandatory-if-able; no friendly unit in the
    attacker's arena ⇒ it fizzles."""
    return TriggerAbility(
        trigger=WhenEnemyAttacksYourBase(),
        effects=[GiveToken(
            token_type="Shield",
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("same_arena_as_event",)))],
    )


# ── shd-set:20 — Miscellaneous abilities ─────────────────────────────────────

def _fennec_play_ambush(state, source_ci, target_id, event_ctx):
    """Adapter: play a unit costing 4 or less from hand (paying its cost) and give
    it Ambush for this phase (the Energy Conversion Lab SOR_22 pattern)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_max=4, grant_keyword="Ambush")
    return state


@card_ability("SHD", "16")
def _fennec_shand():
    """SHD_16 — Fennec Shand (Leader, Underworld, 4/4).

    Undeployed Action [1 resource, Exhaust]: Play a unit that costs 4 or less from
    your hand (paying its cost).  Give it Ambush for this phase.
    Deployed Saboteur (keyword layer) + Action: Play a unit that costs 4 or less
    from your hand.  Give it Ambush for this phase.
    Epic Action: If you control 5 or more resources, deploy this leader (standard
    leader-deploy machinery — no ability).

    Both Action sides are one thin ``push_play_from_hand`` adapter (Admiral Ozzel
    SOR_129 / Energy Conversion Lab SOR_22): ``cost_max=4`` offers only hand units
    costing ≤4 and ``grant_keyword="Ambush"`` grants Ambush before the played
    unit's enter-play bus so it may immediately attack.  Each side is gated by
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX(4) so the action is never offered
    (and its cost never paid) when no unit of cost ≤4 is playable."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_fennec_play_ambush)],
            title="Play a unit (cost 4 or less) from hand with Ambush",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX, 4),
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_fennec_play_ambush)],
            title="Play a unit (cost 4 or less) from hand with Ambush",
            deployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX, 4),
        ),
    ]


def _mystic_reflection(state, source_ci, target_id, event_ctx):
    """Give the chosen enemy unit −2/−0 this phase, or −2/−2 instead if the
    controller controls a Force unit (a conditional-magnitude CustomEffect.target,
    the Zeb Orellios LAW_45 pattern — the hp part is board-decided)."""
    from swu.abilities.resolver import _make_modifier
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    has_force = any(has_trait(state, u, "Force")
                    for arena in (ps.ground_arena, ps.space_arena) for u in arena)
    mod = _make_modifier(state, source_ci.instance_id, target_id,
                         power=-2, hp=(-2 if has_force else 0),
                         duration=Duration.THIS_PHASE)
    state.modifiers.append(mod)
    return state


@card_ability("SHD", "51")
def _mystic_reflection_card():
    """SHD_51 — Mystic Reflection (Event, Force, cost 1): "Give an enemy unit −2/−0
    for this phase.  If you control a Force unit, give the enemy unit −2/−2 for this
    phase instead."

    One targeted ``CustomEffect`` (the −2 power is unconditional; the hp part is 0
    or −2 decided from the board inside the fn — a single Condition atom can't
    express "control a Force unit" as a magnitude choice)."""
    return EventAbility(effects=[CustomEffect(
        fn=_mystic_reflection,
        target=TargetSpec(controller="enemy", kind="unit"))])


def _fenn_rau_play_upgrade(state, source_ci, target_id, event_ctx):
    """Adapter: push a play_upgrade_from_hand decision letting the controller
    choose an upgrade from hand to play at 2 resources less (the ASH_42 subsystem,
    now with a choose-the-upgrade mode + cost_reduction)."""
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(state, source_ci, upgrade_id=None,
                                free=False, cost_reduction=2)
    return state


@card_ability("SHD", "67")
def _fenn_rau():
    """SHD_67 — Fenn Rau (Unit, Mandalorian, 5/6).

    When Played: You may play an upgrade from your hand.  It costs 2 resources
    less.  → a ``push_play_upgrade_from_hand`` adapter in choose-upgrade mode
    (``cost_reduction=2``); the decision itself carries the "you may" (Decline) and
    is only pushed when an affordable hand upgrade with a legal host exists.

    When you play an upgrade on this unit: Give an enemy unit −2/−2 for this phase.
    → a ``WhenYouPlayCard(card_type="upgrade", on_self=True)`` observer (the Kylo
    Ren LOF_229 filter) with a mandatory targeted ``ModifyStats`` (fizzles with no
    enemy unit)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_fenn_rau_play_upgrade)],
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="upgrade", on_self=True),
            effects=[ModifyStats(-2, -2,
                                 TargetSpec(controller="enemy", kind="unit"),
                                 Duration.THIS_PHASE)],
        ),
    ]


def _evidence_choose_upgrade(state, source_ci, target_id, event_ctx):
    """Record the chosen upgrade so the follow-up effect can relocate it."""
    event_ctx["evidence_upgrade_id"] = target_id
    return state


def _evidence_attach(state, source_ci, target_id, event_ctx):
    """Relocate the recorded upgrade from its current host onto the chosen host
    (``target_id``).  "Take control" is implicit — control follows the host (the
    pay-and-steal SHD_142 convention)."""
    from swu.engine.actions import _find_upgrade_host, _relocate_upgrade
    uid = event_ctx.get("evidence_upgrade_id")
    if not uid:
        return state
    host = _find_upgrade_host(state, uid)
    if host is None:
        return state
    _relocate_upgrade(state, uid, host.instance_id, target_id)
    return state


@card_ability("SHD", "77")
def _evidence_of_the_crime():
    """SHD_77 — Evidence of the Crime (Event, Trick, cost 3): "Take control of an
    upgrade that costs 3 or less and attach it to an eligible unit of your choice."

    Two dependent ``CustomEffect.target``s sharing the resolve_effects ``event_ctx``
    (the Haymaker LAW_168 pattern): the first picks any in-play upgrade costing ≤3
    and records it; the second picks a legal "Attach to …" host for THAT upgrade
    (the ``eligible_host_for_event_upgrade`` predicate) and relocates it there via
    ``_relocate_upgrade`` — control follows the new host, so "take control" needs no
    explicit step (Pre Vizsla SHD_142)."""
    return EventAbility(effects=[
        CustomEffect(fn=_evidence_choose_upgrade,
                     target=TargetSpec(controller="any", kind="upgrade", cost_max=3)),
        CustomEffect(fn=_evidence_attach,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("eligible_host_for_event_upgrade",))),
    ])


def _ephant_choose_prey(state, source_ci, target_id, event_ctx):
    """Record the chosen enemy base-attacker + its arena, so a friendly unit in the
    same arena can capture it."""
    from swu.engine.state import Zone
    event_ctx["ephant_prey"] = target_id
    res = state.find_instance(target_id)
    if res is not None:
        event_ctx["same_arena"] = (
            "space" if res[1].zone == Zone.SPACE_ARENA else "ground")
    return state


def _ephant_capture(state, source_ci, target_id, event_ctx):
    """The chosen friendly unit (``target_id``) captures the recorded prey."""
    from swu.engine.actions import _apply_capture
    prey = event_ctx.get("ephant_prey")
    if prey is None:
        return state
    return _apply_capture(state, target_id, prey)


@card_ability("SHD", "88")
def _ephant_mon():
    """SHD_88 — Ephant Mon (Unit, Underworld, 4/6): "On Attack: Choose an enemy
    non-leader unit that attacked your base this phase.  A friendly unit in the same
    arena captures that unit."

    Two dependent ``CustomEffect.target``s sharing ``event_ctx`` (the Haymaker
    LAW_168 pattern): the first picks an enemy non-leader unit recorded in
    ``game_memory.base_attackers_this_round`` for the controller's base (the new
    ``attacked_your_base_this_phase`` predicate) and stashes its arena; the second
    picks a friendly unit in that arena (``same_arena_as_event``) which captures the
    prey via ``_apply_capture`` (the-mandalorian:07).  Fizzles with no eligible
    base-attacker, or no friendly unit in its arena."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[
            CustomEffect(fn=_ephant_choose_prey,
                         target=TargetSpec(controller="enemy", kind="unit",
                                           predicates=("non_leader",
                                                       "attacked_your_base_this_phase"))),
            CustomEffect(fn=_ephant_capture,
                         target=TargetSpec(controller="friendly", kind="unit",
                                           predicates=("same_arena_as_event",))),
        ],
    )


@card_ability("SHD", "72")
def _imprisoned():
    """SHD_72 — Imprisoned (Upgrade, Condition): "Attach to a non-leader unit.
    Attached unit loses its current abilities and can't gain abilities."

    A pure ``SuppressHostAbilities`` marker — the third, upgrade-borne source of the
    ability-suppression read-layer (``state.ability_suppressed``), a
    persistent-while-attached mirror of Mind Trick LOF_202's phase-scoped
    ``abilities_suppressed`` flag and Galen Erso P25_31's name-scoped
    ``is_name_suppressed`` scan.  The read guards short-circuit on the host, so both
    "loses its current abilities" and "can't gain abilities" fall out for free, and
    the suppression lifts the moment Imprisoned leaves play.  The "Attach to a
    non-leader unit" restriction is enforced by the generic ``_upgrade_target_spec``
    parser (→ a ``non_leader`` predicate)."""
    return SuppressHostAbilities()


def _finalizer_capture(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_multi_capture
    push_multi_capture(state, source_ci)
    return state


@card_ability("SHD", "92")
def _finalizer():
    """SHD_92 — Finalizer (Capital Ship, 11/11, Overwhelm): "When Played: Choose any
    number of friendly units.  Each of those units captures an enemy non-leader unit
    in the same arena."

    Overwhelm is handled by the keyword engine.  The When-Played effect is a thin
    ``CustomEffect`` adapter onto the new ``multi_capture_pairing`` decision kind
    (``push_multi_capture``): the controller repeatedly picks a (friendly captor,
    same-arena enemy non-leader prey) PAIR, capturing each prey under its captor
    inline.  Each friendly unit captures at most one enemy; "any number" includes 0,
    so finishing immediately is legal and the decision fizzles with no legal pair."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_finalizer_capture)],
    )


# ── shd-set:21 — Miscellaneous abilities ─────────────────────────────────────

def _rule_with_respect_capture(state, source_ci, target_id, event_ctx):
    """The chosen friendly unit (``target_id``) captures EACH enemy non-leader unit
    that attacked the controller's base this phase (``base_attackers_this_round``)."""
    from swu.engine.actions import _apply_capture
    from swu.engine.state import Zone
    from swu.cards.models import Leader
    if target_id is None:
        return state
    attackers = list(
        state.game_memory.base_attackers_this_round.get(source_ci.owner_id, []))
    for prey_id in attackers:
        res = state.find_instance(prey_id)
        if res is None:
            continue
        _holder, prey = res
        if isinstance(prey.card_def, Leader):
            continue
        if prey.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            continue  # no longer an in-play arena unit
        _apply_capture(state, target_id, prey_id)
    return state


@card_ability("SHD", "106")
def _rule_with_respect():
    """SHD_106 — Rule with Respect (Event, Plan): "A friendly unit captures each
    enemy non-leader unit that attacked your base this phase."

    The controller picks ONE friendly captor (``TargetSpec`` friendly unit); a
    ``CustomEffect`` then captures every enemy non-leader recorded in
    ``game_memory.base_attackers_this_round`` for the controller's base (the Ephant
    Mon SHD_88 ``base_attackers`` ledger + ``_apply_capture``), all under that one
    captor.  Fizzles cleanly with no friendly unit or no qualifying base-attacker
    (capture is arena-agnostic here — unlike Finalizer/Ephant, the text imposes no
    same-arena constraint)."""
    return EventAbility(effects=[
        CustomEffect(fn=_rule_with_respect_capture,
                     target=TargetSpec(controller="friendly", kind="unit")),
    ])


def _choose_sides_pick_friendly(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly non-leader unit so the second target (an enemy
    non-leader unit) can be exchanged with it."""
    event_ctx["choose_sides_friendly"] = target_id
    return state


def _choose_sides_exchange(state, source_ci, target_id, event_ctx):
    """Exchange control of the recorded friendly unit and the chosen enemy unit: the
    friendly goes to the opponent's control, the enemy to the controller's."""
    from swu.engine.actions import change_control
    friendly_id = event_ctx.get("choose_sides_friendly")
    enemy_id = target_id
    if friendly_id is None or enemy_id is None:
        return state
    controller_id = source_ci.owner_id
    opp_id = state.players[1 - state.player_index(controller_id)].player_id
    fres = state.find_instance(friendly_id)
    eres = state.find_instance(enemy_id)
    if fres is None or eres is None:
        return state
    change_control(state, fres[1], opp_id)
    change_control(state, eres[1], controller_id)
    return state


@card_ability("SHD", "132")
def _choose_sides():
    """SHD_132 — Choose Sides (Event, Plan): "Choose a friendly non-leader unit and
    an enemy non-leader unit.  Exchange control of those units."

    Two dependent ``CustomEffect.target``s sharing ``event_ctx`` (the Choose Sides
    pair; the Nothing Left to Fear LAW_41 shared-context pattern): the first records
    the friendly unit, the second picks the enemy unit and swaps control of both via
    ``change_control`` (control is implicit — whoever's arena holds the unit; owner is
    unchanged).  Fizzles if either side has no eligible non-leader unit."""
    return EventAbility(effects=[
        CustomEffect(fn=_choose_sides_pick_friendly,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       predicates=("non_leader",))),
        CustomEffect(fn=_choose_sides_exchange,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader",))),
    ])


@card_ability("SHD", "187")
def _lurking_tie_phantom():
    """SHD_187 — Lurking TIE Phantom (Unit, Raid 2): "This unit can't be captured,
    damaged, or defeated by enemy card abilities."

    Raid 2 is handled by the keyword engine.  The immunity is a single self-targeted
    ``ConstantAbility`` carrying a ``Protection`` marker covering all three enemy-
    ability effects (capture / damage / defeat), read at the capture seam
    (``_apply_capture``), the resolver DealDamage arms, and the DefeatUnit arm
    respectively.  Combat damage/defeat never routes through those effects, so it is
    unaffected (the Chewbacca JTL_103 Protection convention)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_capture=True, from_damage=True, from_defeat=True)],
    )


def _qira_look_and_name(state, source_ci, target_id, event_ctx):
    """Look at an opponent's hand, then name a card from it (recorded on the source's
    ``named_card``; the NamedCardPlayTax marker then surcharges that named card)."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci, from_hand=True)
    return state


@card_ability("SHD", "202")
def _qira():
    """SHD_202 — Qi'ra (Unit, Underworld, 3/5): "When Played: Look at an opponent's
    hand, then name a card.  While this unit is in play, each card with that name
    costs 3 resources more for your opponents to play."

    Two specs: a WhenPlayed ``CustomEffect`` that looks at the opponent's hand and
    names one of its cards (``push_name_a_card(from_hand=True)`` records the choice on
    ``named_card``), and a persistent ``NamedCardPlayTax(3)`` marker read at the
    play-cost seam (``_opponent_play_tax``) — the per-name analogue of Del Meeko
    SOR_34's ``OpponentPlayTax`` and the tax-mirror of Regional Governor SOR_62's
    ``ForbidNamedCardPlay``.  The tax lifts automatically when Qi'ra leaves play (the
    marker is read only while she is in an arena)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_qira_look_and_name)],
        ),
        NamedCardPlayTax(amount=3),
    ]


def _bounty_hunters_quarry_bounty(state, source_ci, target_id, event_ctx):
    """Collector searches the top 5 (or 10 if the guarded host is unique) cards of
    THEIR deck for a unit costing 3 or less and plays it for free."""
    from swu.engine.actions import push_search_and_play
    from swu.cards.models import Unit
    collector = _bounty_collector_id(state, event_ctx)
    if collector is None:
        return state
    window = 10 if getattr(source_ci.card_def, "is_unique", False) else 5

    def _eligible(cd):
        return isinstance(cd, Unit) and (getattr(cd, "cost", 99) or 0) <= 3

    push_search_and_play(state, source_ci, window=window, eligible=_eligible,
                         free=True, decider_id=collector)
    return state


@card_ability("SHD", "123")
def _bounty_hunters_quarry():
    """SHD_123 — Bounty Hunter's Quarry (Upgrade, Bounty/Condition): "Attached unit
    gains: 'Bounty — Search the top 5 cards of your deck, or 10 cards instead if this
    unit is unique, for a unit that costs 3 or less and play it for free.'"

    A ``GrantedAbility(WhenDefeated, is_bounty)`` resolving from the host (the Price on
    Your Head SHD_125 bounty-upgrade template): the collector (opponent of the dying
    host) searches THEIR own deck via ``push_search_and_play(decider_id=collector,
    free=True)`` — window 10 when the guarded host is unique, else 5 — narrowed to
    units costing ≤3, and plays the found one for free under their control (the
    ``decider_id``/``free`` search-and-play extension)."""
    return GrantedAbility(
        ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_bounty_hunters_quarry_bounty)],
            is_bounty=True,
        ),
    )


def _dryden_vos_play_captured(state, source_ci, target_id, event_ctx):
    """Adapter: push the play_captured_card decision (choose a captive guarded by a
    friendly unit and play it free under the controller)."""
    from swu.engine.actions import push_play_captured_card
    push_play_captured_card(state, source_ci, up_to=True)
    return state


@card_ability("SHD", "192")
def _dryden_vos():
    """SHD_192 — Dryden Vos (Unit, Underworld, 5/7, Shielded): "When Played: Choose a
    captured card guarded by a unit you control.  You may play it for free under your
    control."

    Shielded is handled by the keyword engine.  The When-Played effect is a thin
    ``CustomEffect`` adapter onto the new ``play_captured_card`` decision kind
    (``push_play_captured_card``): the controller may pick one Unit captive from their
    own capture pile (every captive there is guarded by one of their units) and play
    it for free under their control — the captive leaves the pile, enters play under
    the controller (owner unchanged), and fires its own When Played / keyword triggers
    (pop-then-act).  Fizzles cleanly with no captive."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_dryden_vos_play_captured)],
    )


def _endless_legions_play(state, source_ci, target_id, event_ctx):
    """Adapter: push the play_resource_units loop (reveal any number of your Unit
    resources and play each for free, one at a time)."""
    from swu.engine.actions import push_play_resource_units
    push_play_resource_units(state, source_ci, up_to=True)
    return state


@card_ability("SHD", "109")
def _endless_legions():
    """SHD_109 — Endless Legions (Event, Supply, cost 14): "Reveal any number of
    resources you control.  Play each unit revealed this way for free (one at a time)."

    A thin ``CustomEffect`` adapter onto the new ``play_resource_units`` decision kind
    (``push_play_resource_units``): the controller may reveal any number of their Unit
    resources and play each for free, one at a time — each play removes the resource
    from the resource row (the count genuinely drops; unlike Smuggle it is NOT replaced
    from the deck) and the just-played unit's triggers resolve before the next pick.
    Revealing a non-unit resource is strictly pointless (no play, identity leaked), so
    only Unit resources are offered (the optimal-play collapse).  Fizzles cleanly with
    no unit resources."""
    return EventAbility(effects=[CustomEffect(fn=_endless_legions_play)])


@card_ability("SHD", "215")
def _smugglers_starfighter():
    """SHD_215 — Smuggler's Starfighter (Unit, Underworld/Vehicle/Transport, 2/2):
    "When Played: If you control another Underworld unit, give an enemy unit -3/-0
    for this phase."  (Smuggle is handled by the keyword engine.)

    Pure reuse: ``Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT`` gates trigger
    COLLECTION on the "another Underworld unit" clause (so the prompt never appears
    when the condition is unmet), and the debuff is an ordinary targeted
    ``ModifyStats`` for this phase."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 param="Underworld"),
        effects=[ModifyStats(power=-3, hp=0,
                             target=TargetSpec(controller="enemy", kind="unit"),
                             duration=Duration.THIS_PHASE)],
    )


@card_ability("SHD", "219")
def _enfys_nest():
    """SHD_219 — Enfys Nest (Unit, Underworld, 5/4, Ambush): "While a friendly unit
    (including this one) is attacking using Ambush, the defender gets -3/-0."

    Ambush itself is the keyword engine's.  The residual is an
    ``AmbushDefenderDebuff`` marker, read at ``UseAmbush.apply`` — the sole seam an
    Ambush attack is declared — which applies it as a ``this_attack`` stats modifier
    on the chosen defender.  A normal (non-Ambush) attack by the same unit is
    unaffected, which is exactly the distinction the card draws, and "including this
    one" needs no special case (Enfys is in play when she Ambush-attacks)."""
    return AmbushDefenderDebuff(power=-3, hp=0)


@card_ability("SHD", "224")
def _boba_fetts_armor():
    """SHD_224 — Boba Fett's Armor (Upgrade, Armor/Item, cost 2): "Attach to a
    non-Vehicle unit.  If attached unit is Boba Fett and damage would be dealt to
    him, prevent 2 of that damage."

    The "Attach to a non-Vehicle unit" restriction is parsed from the printed text by
    ``_upgrade_target_spec``.  The residual is a ``DamagePrevention`` marker gated on
    the host's name, read at the single unit-damage chokepoint
    (``_deal_damage_with_shield``), so it reduces every instance of damage — combat
    and ability alike — by 2 while the host is Boba Fett, and does nothing on any
    other host."""
    return DamagePrevention(amount=2, host_named="Boba Fett")


@card_ability("SHD", "250")
def _tarfful():
    """SHD_250 — Tarfful (Unit, Wookiee, 3/9, Restore 2): "When a friendly Wookiee
    unit is dealt combat damage and isn't defeated: That unit deals that much damage
    to an enemy ground unit."

    Restore is the keyword engine's.  The residual uses the new
    ``WhenFriendlyUnitDealtCombatDamage`` observer (the group analogue of
    ``WhenDealtCombatDamage``), whose firing site only fires for a unit still in play
    after defeat processing — so "isn't defeated" is intrinsic.  "That much damage"
    reads the amount the same site records in ``event_ctx``
    (``DealDamageEqualTo(count="event_combat_damage")``).  Tarfful is himself a
    Wookiee, so the trigger also covers damage dealt to him."""
    return TriggerAbility(
        trigger=WhenFriendlyUnitDealtCombatDamage(traits=("Wookiee",)),
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="enemy", kind="unit", arena="ground"),
            count="event_combat_damage")],
    )


def _mercenary_gunship_take_control(state, source_ci, target_id, event_ctx):
    """Take control of the gunship for whichever player used the ability."""
    from swu.engine.actions import change_control
    user_id = (event_ctx or {}).get("ability_user_id") or state.active_player.player_id
    change_control(state, source_ci, user_id)
    return state


@card_ability("SHD", "256")
def _mercenary_gunship():
    """SHD_256 — Mercenary Gunship (Unit, Underworld/Vehicle/Fighter, 3/2): "Action
    [4 resources]: Take control of this unit.  Any player may use this ability."

    ``ActivatedAbility.any_player`` lifts the two controller restrictions: the
    opponent's arena is scanned for the ability in ``legal_actions`` and
    ``UseAbility``'s ownership guard is bypassed.  Costs are paid by the player USING
    it (the active player), so either side can pay 4 to take the gunship — including
    taking it back afterwards, since the ability travels with the unit.  The effect
    reuses the existing ``change_control`` seam (control is implicit — whoever's
    arena holds the unit; ``owner_id`` never changes)."""
    return ActivatedAbility(
        costs=[PayResources(4)],
        effects=[CustomEffect(fn=_mercenary_gunship_take_control)],
        title="Take control of this unit",
        any_player=True,
    )
