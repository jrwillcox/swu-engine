"""JTL (Jump to Lightspeed) card ability registrations.

Cards with no text or only keywords are handled by the keyword engine and are
not registered here.  This module is imported for its side effects.

Group ``leia-organa:01`` — Direct damage & removal:
  * JTL_250 Sabine's Masterpiece — On Attack, up to four independent
    aspect-gated effects resolve in order.

Group ``jabba-the-hutt:03`` — Direct damage & removal:
  * JTL_216 Contracted Hunter — Ambush (keyword layer) + "When the regroup phase
    starts: Defeat this unit" (the PhaseStartTrigger("regroup") seam).

Group ``qui-gon-jinn:03`` — Combat tricks, buffs & tempo:
  * JTL_201 Ahsoka Tano — When Played: opponent discards a card; if it was a unit,
    you may exhaust a unit (the In Pursuit TWI_221 ``requires_prior_target`` gate).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, EventAbility, GrantedAbility, ConstantAbility, ActivatedAbility,
    OnAttack, PhaseStartTrigger, WhenPlayed, WhenDefeated, WhenDeployed,
    WhenIndirectDamageDealtToUnit, WhenDealNonCombatDamage, WhenYouDraw,
    WhenUnitHealed, WhenUnitReadies, WhenDealsCombatDamageToUnit,
    WhenDealsCombatDamageToBase, WhenAttackEnds,
    WhenAttacked, CrossArenaAttack,
    WhenYouDeployLeader, WhenYouPlayCard, ReadyRestriction, WhenUnitDefeated,
    ConditionalFirstStrike, IndirectDamageBonus, AdditionalPilotSlots, WhenDefeatedRedo,
    IndirectDamageSelfAssign, StartingHandModifier, DeckSizeModifier,
    DealDamage, DealDamageEqualTo, Heal, GiveToken, DefeatUnit, DefeatAllUnits,
    ExhaustCard, ReadyCard, DrawCards, ReturnToHand, NextPlayDiscount,
    StatBonus, KeywordGrant, GrantKeyword, CopyKeywords, PayResources, ExhaustSelf,
    ModifyStats, Duration,
    CustomEffect,
    Protection, CreateTokenUnit, CostReduction, StandingPlayDiscount,
    AttackRestriction, HalvePaidCosts,
    TargetSpec, ConditionCheck, Condition, SELF, DEFENDER, EACH_FRIENDLY,
)


def _sabine_cunning(state, source_ci, target_id, event_ctx):
    """Cunning clause: if the controller controls a Cunning unit, exhaust or ready
    a resource (a fungible 'modal' choice).  No-op otherwise."""
    ps = state.player_by_id(source_ci.owner_id)
    has_cunning = any(
        "Cunning" in {a.name for a in (getattr(u.card_def, "aspects", None) or ())}
        for arena in (ps.ground_arena, ps.space_arena) for u in arena
    )
    if has_cunning:
        from swu.engine.actions import push_modal
        push_modal(state, source_ci, ["exhaust_resource", "ready_resource"])
    return state


@card_ability("JTL", "250")
def _sabines_masterpiece():
    """On Attack: If you control a:
        Vigilance unit, heal 2 damage from a base.
        Command unit, give an Experience token to a unit.
        Aggression unit, deal 1 damage to a unit or a base.
        Cunning unit, exhaust or ready a resource.

    The four clauses are independent.  Each is registered as its OWN single-effect
    OnAttack ability so the resolve_effects machinery handles every clause's one
    target choice at effect index 0 — listing them as four effects of one ability
    would mis-consume a choice against an earlier *gated-off* effect (the
    resolve_effects "skip earlier no-target effect" wart, cf. The Mandalorian
    SHD_18).  The first three are plain targeted effects gated by
    ``require_controller_aspect`` — with no unit of that aspect the effect has no
    legal target and that ability resolves inline as a no-op (no prompt); with one
    it prompts for the target.  The fourth (a resource exhaust/ready modal) is a
    CustomEffect that gates on Cunning itself and pushes a 'modal' decision
    (reusing the Leia SOR_189 push_modal seam with the new exhaust_resource mode).
    All four are mandatory (non-optional).  Clause independence makes the
    resolution order among them immaterial.
    """
    return [
        TriggerAbility(trigger=OnAttack(), effects=[
            Heal(2, TargetSpec(kind="base", require_controller_aspect="Vigilance"))]),
        TriggerAbility(trigger=OnAttack(), effects=[
            GiveToken("Experience", TargetSpec(
                kind="unit", require_controller_aspect="Command"))]),
        TriggerAbility(trigger=OnAttack(), effects=[
            DealDamage(1, TargetSpec(
                kind="unit_or_base", require_controller_aspect="Aggression"))]),
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_sabine_cunning)]),
    ]


@card_ability("JTL", "216")
def _contracted_hunter():
    """JTL_216 — Contracted Hunter (Unit, Underworld/Bounty Hunter, 4/4, Ambush —
    keyword layer): "When the regroup phase starts: Defeat this unit."

    A self-defeating temporary attacker.  Ambush is handled by the keyword engine;
    the residual is a ``PhaseStartTrigger(phase="regroup")`` (matches the
    PhaseChanged → REGROUP event fired at the ACTION→REGROUP transition) whose one
    mandatory ``DefeatUnit(fixed=SELF)`` resolves inline (no player choice).  The
    unit attacks the round it is played (Ambush) and is then defeated when the next
    regroup phase begins."""
    return TriggerAbility(
        trigger=PhaseStartTrigger(phase="regroup"),
        effects=[DefeatUnit(TargetSpec(kind="unit", fixed=SELF))],
    )


# ── qui-gon-jinn:03 — Combat tricks, buffs & tempo ────────────────────────────

def _jtl_ahsoka_when_played(state, source_ci, target_id, event_ctx):
    """Opponent discards the first card from their hand (the established first-card
    discard simplification — K-2SO SOR_145 / Garindan SEC_186).  If it was a Unit,
    push a 'you may exhaust a unit' decision (the generalised
    ``push_exhaust_combined_cost`` with ``max_units=1`` and no cost cap — the
    controller may exhaust any one unit, pointing it at an enemy, or take 0)."""
    from swu.cards.models import Unit
    from swu.engine.state import Zone
    from swu.engine.actions import push_exhaust_combined_cost
    opp_idx = 1 - state.player_index(source_ci.owner_id)
    opp = state.players[opp_idx]
    if opp.hand:
        ci = opp.hand.pop(0)
        ci.zone = Zone.DISCARD
        opp.discard.append(ci)
        if isinstance(ci.card_def, Unit):
            push_exhaust_combined_cost(state, source_ci, budget=None, max_units=1)
    return state


@card_ability("JTL", "201")
def _ahsoka_tano_jtl_201():
    """JTL_201 — Ahsoka Tano (Unit, Force/Fringe): "When Played: An opponent
    discards a card from their hand. If it's a unit, you may exhaust a unit."

    A mandatory ``WhenPlayed`` whose single no-target ``CustomEffect`` (the
    Palpatine SOR_135 inline-resolve-then-push pattern) makes the opponent discard
    their first hand card and — only if that card was a Unit — pushes a "you may
    exhaust a unit" decision (``push_exhaust_combined_cost(max_units=1)``).  Folding
    both into one effect is necessary: a two-effect [discard, exhaust] ability would
    be judged inline-resolvable (the exhaust has no targets *before* the discard
    runs), so the per-effect target re-evaluation that the resolve_effects decision
    path provides — and thus the exhaust prompt — would never happen.  Pushing the
    decision from inside the discard fn sidesteps that: the decision is created only
    when a unit was discarded, and a FinishExhaustCombined ("take 0") honours the
    "you may"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jtl_ahsoka_when_played)],
    )


# ── boba-fett:01 — Direct damage & removal (indirect-damage primitive) ────────
#
# "Indirect damage" is unpreventable damage a player assigns among their own base
# and units — modelled by the ``assign_indirect_damage`` decision kind
# (``actions.push_assign_indirect_damage``): the RECEIVING player (the opponent of
# the source's controller) chooses one target that absorbs all the points, and
# ``_apply_indirect_damage`` applies it directly (bypassing shields).  The choice
# always has a legal action because a base is always present, so there is no
# confirm step.  See docs/dev/history/seams_log.md for the primitive note.


def _boba_fett_noncombat_indirect(state, source_ci, target_id, event_ctx):
    """Boba Fett JTL_9 leader ability: exhaust this leader, then deal 1 indirect
    damage to a player.  Bundled in one CustomEffect so "If you do [exhaust]"
    holds — the optional trigger's Accept IS the "you may exhaust".  The 1 indirect
    damage is itself non-combat damage, but by the time it resolves Boba is
    exhausted, so the SOURCE_READY gate stops the observer re-firing (the chain
    terminates)."""
    source_ci.exhausted = True
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=1)
    return state


def _boba_fett_deploy_upgrade_damage(state, source_ci, target_id, event_ctx):
    """Boba Fett JTL_9 "When deployed as an upgrade": deal up to 4 damage divided
    as you choose among any number of units (any controller, either arena;
    overkill allowed — the up_to distribute_damage seam)."""
    from swu.engine.actions import push_distribute_damage
    push_distribute_damage(state, source_ci, 4, target_controller="any",
                           target_arena=None, up_to=True)
    return state


@card_ability("JTL", "9")
def _boba_fett_jtl_9():
    """JTL_9 — Boba Fett (Leader, Underworld/Bounty Hunter/Pilot, 4/7; deploys as a
    4/7 unit or, via its Epic Action, as a +4/+4 Pilot upgrade making the host a
    leader unit).  Two abilities (the deploy option itself is the
    ``DeployLeaderAsUpgrade`` action, not a registration):

    1. **"When you deal non-combat damage: You may exhaust this leader.  If you do,
       deal 1 indirect damage to a player."**  A ``WhenDealNonCombatDamage``
       observer (the new non-combat-damage-attribution primitive) — it fires when
       Boba's controller deals non-combat damage, in ANY of Boba's forms (undeployed
       leader, deployed unit, or deployed-as-upgrade), since it is neither
       deployed_only nor undeployed_only.  Optional (the "you may"), gated by
       ``SOURCE_READY`` so it is not offered while Boba is exhausted (bounding the
       self-chain — the resulting indirect damage is itself non-combat damage).  Its
       one ``CustomEffect`` exhausts Boba and pushes the indirect damage, bound so
       "If you do" holds.

    2. **"When deployed as an upgrade: Deal up to 4 damage divided as you choose
       among any number of units."**  A ``WhenDeployed(via_pilot_leader=True)``
       trigger fired only on the ``DeployLeaderAsUpgrade`` path (its event context
       carries ``via_pilot_leader``); a normal unit deploy does not set the flag, so
       it does not fire.  A thin ``CustomEffect`` adapter onto the ``up_to``
       ``push_distribute_damage`` seam (overkill among any units, either controller)."""
    return [
        TriggerAbility(
            trigger=WhenDealNonCombatDamage(),
            effects=[CustomEffect(fn=_boba_fett_noncombat_indirect)],
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenDeployed(via_pilot_leader=True),
            effects=[CustomEffect(fn=_boba_fett_deploy_upgrade_damage)],
        ),
    ]


@card_ability("JTL", "132")
def _first_order_stormtrooper():
    """JTL_132 — First Order Stormtrooper (Unit, First Order/Trooper, 2/1): "On
    Attack/When Defeated: Deal 1 indirect damage to a player."

    Two mandatory triggers (an ``OnAttack`` and a ``WhenDefeated``), each a
    no-target ``CustomEffect`` adapter onto ``push_assign_indirect_damage(1)`` —
    the opponent assigns 1 unpreventable damage among their base and units."""
    def _deal_1_indirect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source_ci, amount=1)
        return state

    return [
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_deal_1_indirect)]),
        TriggerAbility(trigger=WhenDefeated(), effects=[CustomEffect(fn=_deal_1_indirect)]),
    ]


def _pryde_defeat_upgrade(state, source_ci, target_id, event_ctx):
    """Pryde JTL_133 WhenIndirectDamageDealtToUnit: defeat a non-unique upgrade on
    the unit that took indirect damage (id in ``event_ctx``).  If the unit has
    several non-unique upgrades the first is defeated (a documented simplification;
    the player still chooses *whether* via the optional trigger).  A no-op if the
    unit is gone (defeated by the damage) or carries no non-unique upgrade."""
    unit_id = event_ctx.get("indirect_damage_unit_id")
    if not unit_id:
        return state
    result = state.find_instance(unit_id)
    if result is None:
        return state
    _, unit_ci = result
    from swu.cards.models import TokenUpgrade
    for up in list(unit_ci.attached_upgrades):
        if isinstance(up.card_def, TokenUpgrade):
            continue  # tokens are not "upgrades" for defeat purposes
        if getattr(up.card_def, "is_unique", False):
            continue
        from swu.abilities.resolver import _apply_defeat_unit
        _apply_defeat_unit(state, up.instance_id)
        break
    return state


def _pryde_on_attack(state, source_ci, target_id, event_ctx):
    """Pryde JTL_133 On Attack: deal 2 indirect damage to the opponent.  The
    "if you have the initiative" restriction is the trigger's ConditionCheck gate."""
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=2)
    return state


@card_ability("JTL", "133")
def _allegiant_general_pryde():
    """JTL_133 — Allegiant General Pryde (Unit, First Order/Official, 2/3): "When
    indirect damage is dealt to a unit: You may defeat a non-unique upgrade on it.
    On Attack: If you have the initiative, deal 2 indirect damage to a player."

    The first is a new **observer** trigger ``WhenIndirectDamageDealtToUnit`` (fires
    for any Pryde in play when indirect damage lands on a unit, via
    ``event_ctx["indirect_damage_unit_id"]``); optional, its ``CustomEffect``
    defeats a non-unique upgrade on that unit.  The On Attack is a no-target
    ``CustomEffect`` gated by ``CONTROLLER_HAS_INITIATIVE`` (the condition gates
    trigger collection, so no indirect damage is dealt without the initiative)
    that pushes ``assign_indirect_damage`` for 2."""
    return [
        TriggerAbility(
            trigger=WhenIndirectDamageDealtToUnit(),
            effects=[CustomEffect(fn=_pryde_defeat_upgrade)],
            optional=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_pryde_on_attack)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
        ),
    ]


def _dengar_on_attack(state, source_ci, target_id, event_ctx):
    """Dengar JTL_139 granted On Attack: deal 2 indirect damage to a player, or 3
    if the host (``source_ci`` — a granted ability resolves from the host) is an
    Underworld unit."""
    from swu.engine.traits import has_trait
    from swu.engine.actions import push_assign_indirect_damage
    amount = 3 if has_trait(state, source_ci, "Underworld") else 2
    push_assign_indirect_damage(state, source_ci, amount=amount)
    return state


@card_ability("JTL", "139")
def _dengar():
    """JTL_139 — Dengar (Unit, Bounty Hunter/Pilot/Underworld, 5/4; Piloting):
    "Attached unit gains: 'On Attack: Deal 2 indirect damage to a player. If this
    unit is an Underworld unit, deal 3 indirect damage instead.'"

    Dengar's only ability text is a **Pilot** grant: when he is played as a pilot
    upgrade (the Piloting keyword, already implemented) onto a Vehicle, the host
    gains the On Attack.  Modelled as a ``GrantedAbility`` wrapping an ``OnAttack``
    trigger that resolves from the HOST (the Armed to the Teeth SHD_175 pattern);
    "this unit is an Underworld unit" reads the host's effective traits.  Played as
    a normal unit he is a vanilla 5/4 (the granted ability confers nothing to
    itself)."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_dengar_on_attack)],
    ))


@card_ability("JTL", "140")
def _ig_2000():
    """JTL_140 — IG-2000 (Unit, Transport/Underworld/Vehicle, 3/4; Overwhelm —
    keyword layer): "When Played: Deal 1 damage to each of up to 3 units."

    A ``WhenPlayed`` whose one no-target ``CustomEffect`` is a thin adapter onto
    the new ``select_damage`` decision kind (``push_select_damage(amount_each=1,
    max_targets=3)``): the controller picks up to 3 distinct units one at a time
    (any controller — ``controller="any"`` mirrors the text), each dealt 1 damage
    once the selection finishes ("pop, then deal")."""
    def _ig2000_when_played(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_select_damage
        push_select_damage(state, source_ci, amount_each=1, max_targets=3)
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_ig2000_when_played)],
    )


@card_ability("JTL", "144")
def _no_disintegrations():
    """JTL_144 — No Disintegrations (Event, Plan): "Deal damage to a non-leader
    unit equal to 1 less than its remaining HP."

    A plain ``EventAbility`` with one ``DealDamageEqualTo`` whose per-target count
    is the new ``target_remaining_hp_minus_1`` scaling source (``max(0,
    compute_hp − damage − 1)``).  The controller picks a non-leader unit
    (mandatory-if-able); a unit at 1 remaining HP takes 0 (a no-op)."""
    return EventAbility(effects=[DealDamageEqualTo(
        target=TargetSpec(controller="any", kind="unit", predicates=("non_leader",)),
        count="target_remaining_hp_minus_1",
    )])


# ── boba-fett:02 — Direct damage & removal ────────────────────────────────────


@card_ability("JTL", "183")
def _zygerrian_starhopper():
    """JTL_183 — Zygerrian Starhopper (Unit, Underworld/Vehicle/Fighter, 2/3):
    "When Defeated: Deal 2 indirect damage to a player."

    A mandatory ``WhenDefeated`` whose no-target ``CustomEffect`` is a thin adapter
    onto ``push_assign_indirect_damage(2)`` (the First Order Stormtrooper JTL_132
    pattern) — the opponent (the only other player) assigns 2 unpreventable damage
    among their base and units."""
    def _deal_2_indirect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source_ci, amount=2)
        return state

    return TriggerAbility(trigger=WhenDefeated(),
                          effects=[CustomEffect(fn=_deal_2_indirect)])


def _bossk_on_attack_effects():
    """The shared On Attack: exhaust the defender and deal 1 damage to it (if it's
    a unit).  ``fixed=DEFENDER`` resolves to the current defender from event_ctx
    and to *nothing* when attacking a base — so both effects no-op on a base
    attack, giving the printed "(if it's a unit)" for free."""
    return [
        ExhaustCard(TargetSpec(kind="unit", fixed=DEFENDER)),
        DealDamage(1, TargetSpec(kind="unit", fixed=DEFENDER)),
    ]


@card_ability("JTL", "187")
def _bossk():
    """JTL_187 — Bossk (Unit, Underworld/Bounty Hunter/Pilot, 4/4; Piloting):
    "On Attack: Exhaust the defender and deal 1 damage to it (if it's a unit).
    Piloting [2 resources Cunning Villainy]. Attached unit gains: '<same On
    Attack>'."

    Played as a normal unit, Bossk's own ``OnAttack`` (a plain ``TriggerAbility``)
    fires.  Played as a Pilot upgrade (the Piloting keyword layer), the host gains
    the same On Attack — a ``GrantedAbility`` wrapping an identical ``OnAttack``
    that resolves from the HOST (the Vambrace Grappleshot SHD_74 / Armed to the
    Teeth SHD_175 pattern; ``fixed=DEFENDER`` reads the host's current defender).
    The plain trigger is never collected off an upgrade (only ``GrantedAbility``
    specs are scanned from ``attached_upgrades``) and the granted ability is never
    collected off a unit, so exactly one of the two is live per play mode."""
    return [
        TriggerAbility(trigger=OnAttack(), effects=_bossk_on_attack_effects()),
        GrantedAbility(ability=TriggerAbility(
            trigger=OnAttack(), effects=_bossk_on_attack_effects())),
    ]


def _boba_fett_189_pilot_damage(state, source_ci, target_id, event_ctx):
    """Boba Fett JTL_189 "When played as an upgrade": deal 1 damage to the chosen
    unit, or 2 if the attached host is a Transport.  The host id is threaded in
    ``event_ctx["attached_to_id"]`` by the pilot-play path (``_attach_pilot``);
    the magnitude (1 vs 2) is decided here (the Zeb Orellios LAW_45 conditional-
    magnitude-via-CustomEffect.target pattern).  A ``None`` target (declined) or a
    vanished host is a clean no-op."""
    if target_id is None:
        return state
    from swu.engine.traits import has_trait
    from swu.abilities.resolver import _apply_deal_damage
    amount = 1
    host_id = (event_ctx or {}).get("attached_to_id")
    if host_id:
        res = state.find_instance(host_id)
        if res is not None and has_trait(state, res[1], "Transport"):
            amount = 2
    return _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name)


@card_ability("JTL", "189")
def _boba_fett_jtl_189():
    """JTL_189 — Boba Fett (Unit, Underworld/Bounty Hunter/Pilot, 5/4; Shielded,
    Piloting): "When played as an upgrade: You may deal 1 damage to a unit. If
    attached unit is a Transport, you may deal 2 damage instead."

    Shielded and Piloting are the keyword layer.  The residual is an OPTIONAL
    ``WhenPlayed(as_upgrade=True)`` — the new ``as_upgrade`` flag fires the trigger
    ONLY on the Pilot-upgrade play path (``UpgradePlayed``/``via_pilot``), never
    when Boba is played as a vanilla 5/4 unit.  Its single ``CustomEffect.target``
    prompts for any unit and deals 1 (or 2 if the Transport host) — the Zeb
    Orellios LAW_45 pattern.  ``optional=True`` is the "you may" (auto-declines
    with no unit target)."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(
            fn=_boba_fett_189_pilot_damage,
            target=TargetSpec(controller="any", kind="unit"),
        )],
        optional=True,
    )


def _emp_damage_and_exhaust(state, source_ci, target_id, event_ctx):
    """Electromagnetic Pulse JTL_230: deal 2 damage to the chosen Droid/Vehicle
    unit AND exhaust it — the SAME unit, so a single CustomEffect.target (two
    separate targeted effects would prompt twice and could pick different units).
    Deal first, then exhaust only if it survived (a lethal 2 leaves nothing to
    exhaust)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)
    res = state.find_instance(target_id)
    if res is not None:
        res[1].exhausted = True
    return state


@card_ability("JTL", "230")
def _electromagnetic_pulse():
    """JTL_230 — Electromagnetic Pulse (Event, Tactic): "Deal 2 damage to a Droid
    or Vehicle unit and exhaust it."

    A plain ``EventAbility`` whose one ``CustomEffect`` carries
    ``target=TargetSpec(predicates=("droid_or_vehicle",))`` — the new "Droid OR
    Vehicle" predicate (an OR a single ``traits`` tuple, which requires ALL,
    cannot express).  The fn deals 2 to the chosen unit and exhausts the same one.
    Mandatory-if-able (fizzles with no Droid/Vehicle unit on the board)."""
    return EventAbility(effects=[CustomEffect(
        fn=_emp_damage_and_exhaust,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("droid_or_vehicle",)),
    )])


@card_ability("JTL", "237")
def _tie_bomber():
    """JTL_237 — TIE Bomber (Unit, Imperial/Vehicle/Fighter, 0/4): "On Attack:
    Deal 3 indirect damage to the defending player."

    A mandatory ``OnAttack`` whose no-target ``CustomEffect`` is a thin adapter
    onto ``push_assign_indirect_damage(3)``.  In a 2-player game the "defending
    player" is the opponent of the source's controller — exactly whom the indirect
    primitive addresses — so no defender-specific plumbing is needed."""
    def _deal_3_indirect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source_ci, amount=3)
        return state

    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_deal_3_indirect)])


def _fetts_firespray_indirect(state, source_ci, target_id, event_ctx):
    """Fett's Firespray JTL_240: deal 1 indirect damage to the opponent, or 2 if
    the controller controls Boba Fett (as a unit, upgrade, or leader).  The Boba
    Fett check reuses ``CONTROLLER_CONTROLS_NAMED`` (now also scanning attached
    upgrades, so a pilot / leader-as-upgrade Boba counts).  "Fett's Firespray"
    does not contain "Boba Fett", so there is no self-trigger."""
    from swu.engine.actions import push_assign_indirect_damage
    controls_boba = ConditionCheck(
        Condition.CONTROLLER_CONTROLS_NAMED, param="Boba Fett").evaluate(state, source_ci)
    push_assign_indirect_damage(state, source_ci, amount=2 if controls_boba else 1)
    return state


@card_ability("JTL", "240")
def _fetts_firespray_jtl_240():
    """JTL_240 — Fett's Firespray (Unit, Underworld/Vehicle/Transport, 4/4): "When
    Played/On Attack: Deal 1 indirect damage to a player. If you control Boba Fett
    (as a unit, upgrade, or leader), deal 2 indirect damage instead."

    Two mandatory triggers (a ``WhenPlayed`` and an ``OnAttack``), each a no-target
    ``CustomEffect`` that computes the magnitude (1 vs 2) from
    ``CONTROLLER_CONTROLS_NAMED("Boba Fett")`` and pushes ``assign_indirect_damage``
    accordingly."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_fetts_firespray_indirect)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_fetts_firespray_indirect)]),
    ]


# ── boba-fett:03 — Combat tricks, buffs & tempo ───────────────────────────────


@card_ability("JTL", "141")
def _ig_88():
    """JTL_141 — IG-88 (Unit, Bounty Hunter/Droid/Pilot/Underworld, 4/5; Piloting
    [2 resources Aggression Villainy]): "While an enemy unit is damaged, this unit
    gets +3/+0." + (Pilot residual) "Attached unit gains: '<the same>'."

    A single self-targeted conditional ``ConstantAbility`` (``StatBonus(3,0)`` gated
    by the new ``ENEMY_HAS_DAMAGED_UNIT`` atom) models BOTH forms of the card:
      * played as a **unit**, the arena constant-ability scan in ``compute_power``
        reads it directly and buffs IG-88 itself;
      * played as a **Pilot upgrade** (the Piloting keyword layer), the same spec is
        picked up by the new attached-upgrade SELF-``StatBonus`` scan
        (``_upgrade_self_stat_bonus``) and buffs the host — exactly the "Attached
        unit gains: '<this unit gets +3/+0>'" residual (the Grievous's Wheel Bike
        TWI_236 keyword-grant-from-upgrade pattern, mirrored for a stat buff).
    The condition winks the +3/+0 on/off with the board (read passively; no trigger
    or decision machinery)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=3, hp=0)],
        condition=ConditionCheck(Condition.ENEMY_HAS_DAMAGED_UNIT),
    )


# ── boba-fett:04 — Miscellaneous abilities ────────────────────────────────────


@card_ability("JTL", "165")
def _hunting_aggressor():
    """JTL_165 — Hunting Aggressor (Unit, Transport/Underworld/Vehicle, 3/6):
    "Indirect damage you deal to opponents is increased by 1."

    A passive ``IndirectDamageBonus(1)`` marker read at the indirect-damage
    chokepoint (``actions.push_assign_indirect_damage``): while Hunting Aggressor
    is in play, every indirect deal by its controller is raised by 1 (multiple
    copies stack).  No trigger, no decision — a static amount modifier, so it
    applies to every source of indirect damage the controller has (First Order
    Stormtrooper JTL_132, TIE Bomber JTL_237, Dengar's pilot grant, …)."""
    return IndirectDamageBonus(amount=1)


@card_ability("JTL", "185")
def _hounds_tooth():
    """JTL_185 — Hound's Tooth (Unit, Transport/Underworld/Vehicle, 4/3): "While
    attacking an exhausted unit that didn't enter play this phase, this unit deals
    combat damage before the defender."

    Conditional First Strike: a ``ConditionalFirstStrike`` marker whose
    ``defender_spec`` matches an exhausted enemy unit not played this phase.  Read
    at the unit-combat step (``actions._attacker_has_first_strike``), so the
    attacker deals its damage first (and takes none back if the defender dies)
    only against a qualifying defender — unconditional First Strike stays the
    keyword layer (Incinerator Trooper SHD_234).  ``not_played_this_phase`` is the
    new inverse of the ``played_this_phase`` predicate."""
    return ConditionalFirstStrike(
        defender_spec=TargetSpec(
            controller="enemy", kind="unit",
            predicates=("exhausted", "not_played_this_phase"),
        ),
    )


# ── han-solo:03 — Card advantage & disruption ─────────────────────────────────

def _shuttle_tydirium_on_attack(state, source_ci, target_id, event_ctx):
    """Discard the top card of the controller's deck ("Discard a card from your
    deck" mills the top card — the deck is ordered, no player choice).  If that
    card has an odd cost, push an optional "give an Experience token to another
    unit" select_token (up to 1; ``not_self`` excludes Shuttle Tydirium).  An empty
    deck is a clean no-op."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_select_token
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    card = ps.deck.pop(0)
    card.face_down = False
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    cost = getattr(card.card_def, "cost", None)
    if cost is not None and cost % 2 == 1:
        push_select_token(
            state, source_ci,
            token_type="Experience", max_targets=1,
            controller="any", kind="unit", predicates=["not_self"],
        )
    return state


@card_ability("JTL", "200")
def _shuttle_tydirium():
    """JTL_200 — Shuttle Tydirium (Unit, Rebel/Transport/Vehicle, 2/4): "On Attack:
    Discard a card from your deck. If it has an odd cost, you may give an Experience
    token to another unit."

    A plain ``OnAttack`` whose one inline ``CustomEffect`` mills the top card (Kuiil
    SHD_41 pattern) and, only if its cost is odd, offers the "up to 1" Experience
    token via ``push_select_token`` (``not_self`` = "another unit"; ``controller=
    "any"`` mirrors the printed text, but the recipient benefits so the controller
    never picks an enemy)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_shuttle_tydirium_on_attack)],
    )


def _boshek_when_played_as_upgrade(state, source_ci, target_id, event_ctx):
    """Discard the top 2 cards of the controller's deck, then return each of those
    two with an odd cost to hand (mandatory — no player choice).  Resolves inline;
    an empty deck yields fewer/zero milled cards."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    milled = []
    for _ in range(2):
        if not ps.deck:
            break
        card = ps.deck.pop(0)
        card.face_down = False
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        milled.append(card)
    for card in milled:
        cost = getattr(card.card_def, "cost", None)
        if cost is not None and cost % 2 == 1:
            ps.discard.remove(card)
            card.zone = Zone.HAND
            ps.hand.append(card)
    return state


@card_ability("JTL", "215")
def _boshek():
    """JTL_215 — BoShek (Unit, Fringe/Pilot, 3/4; Piloting [2 resources Cunning]):
    "When played as an upgrade: Discard 2 cards from your deck. Return each of those
    cards with an odd cost to your hand."

    Piloting is the keyword layer.  The ability fires only on the Pilot-upgrade play
    path (``WhenPlayed(as_upgrade=True)`` — the Boba Fett JTL_189 flag), so a
    normally-played BoShek is a vanilla 3/4.  Its one inline ``CustomEffect`` mills
    the top 2 cards and returns each odd-cost one to hand (mandatory, no choice)."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(fn=_boshek_when_played_as_upgrade)],
    )


# ── han-solo:04 — Combat tricks, buffs & tempo ────────────────────────────────

def _han_reveal_and_attack(state, source_ci, target_id, event_ctx):
    """Han Solo JTL_17 undeployed Action: reveal the top card of the controller's
    deck (read its cost for the odd-cost comparison — the card stays on top), then
    push a granted attack whose +1/+0 applies only when the revealed card and the
    chosen attacker have *different odd* costs (``bonus_if_odd_cost_diff_from``).
    An empty deck reveals nothing (cost ``None`` -> the bonus never applies)."""
    from swu.engine.actions import push_granted_attack
    ps = state.player_by_id(source_ci.owner_id)
    revealed_cost = getattr(ps.deck[0].card_def, "cost", None) if ps.deck else None
    push_granted_attack(state, source_ci, power_bonus=1,
                        bonus_if_odd_cost_diff_from=revealed_cost)
    return state


def _han_ready_resources_for_odd(state, source_ci, target_id, event_ctx):
    """Han Solo JTL_17 "When deployed as an upgrade": for each friendly unit or
    upgrade with an odd cost, ready a resource.  ``source_ci`` is the leader-upgrade
    (resolves from itself); its owner is the controller."""
    ps = state.player_by_id(source_ci.owner_id)
    count = 0
    for u in ps.ground_arena + ps.space_arena:
        c = getattr(u.card_def, "cost", None)
        if c is not None and c % 2 == 1:
            count += 1
        for up in u.attached_upgrades:
            c = getattr(up.card_def, "cost", None)
            if c is not None and c % 2 == 1:
                count += 1
    readied = 0
    for r in ps.resources:
        if readied >= count:
            break
        if r.exhausted:
            r.exhausted = False
            readied += 1
    return state


@card_ability("JTL", "17")
def _han_solo_jtl_17():
    """JTL_17 — Han Solo (Leader, Pilot/Rebel, 3/7; deploys as a 3/7 unit or, via
    its Epic Action, as a +3/+4 Pilot upgrade making the host a leader unit).

    * **Undeployed** Action [Exhaust]: "Reveal the top card of your deck, then
      attack with a unit.  If the revealed card and that unit have different odd
      costs, +1/+0 for this attack."  A thin ``CustomEffect`` adapter (the Moff
      Gideon SHD_7 undeployed-Action pattern) that reads the top card's cost and
      pushes a granted attack with the new ``bonus_if_odd_cost_diff_from`` gate.
      Gated by ``CONTROLLER_HAS_READY_UNIT_COST_MAX`` (param ``None`` = "any ready
      unit") so the Exhaust is not paid when no unit could attack (the don't-offer-
      a-no-op pattern).  DEVIATION: "reveal" is modelled by reading the top card's
      cost (it stays face-down on top) rather than a public reveal — cosmetic; the
      mechanical odd-cost comparison is faithful.
    * **When deployed as an upgrade**: "For each friendly unit or upgrade that has
      an odd cost, ready a resource."  A ``WhenDeployed(via_pilot_leader=True)``
      trigger (fired only on the ``DeployLeaderAsUpgrade`` path) whose one inline
      ``CustomEffect`` counts odd-cost friendly units + upgrades and readies that
      many resources.
    * The Epic Action deploy (5+ resources: deploy normally, or as an upgrade on a
      Vehicle without a Pilot) is the standard ``deploy_threshold`` /
      ``DeployLeaderAsUpgrade`` machinery (the Boba Fett JTL_9 primitive) — no
      registration."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_han_reveal_and_attack)],
            title="Reveal top card, then attack with a unit",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX),
        ),
        TriggerAbility(
            trigger=WhenDeployed(via_pilot_leader=True),
            effects=[CustomEffect(fn=_han_ready_resources_for_odd)],
        ),
    ]


@card_ability("JTL", "93")
def _nien_nunb():
    """JTL_93 — Nien Nunb (Unit, Pilot/Rebel, 1/2; Piloting [1 resource Command
    Heroism]): "This unit gets +1/+0 for each other friendly Pilot unit and
    upgrade." + (Pilot residual) "Attached unit gets +1/+0 for each other friendly
    Pilot unit and upgrade."

    A single self-targeted scaling ``ConstantAbility`` models BOTH forms:
      * played as a **unit**, the arena constant-ability scan buffs Nien Nunb;
      * played as a **Pilot upgrade** (the Piloting keyword layer), the same spec
        is read by the attached-upgrade SELF-``StatBonus`` scan and buffs the host
        (the IG-88 JTL_141 pattern).
    The new ``StatBonus.count="other_friendly_pilots"`` scales the +1/+0 by the
    number of friendly Pilot units and upgrades minus one for Nien Nunb itself
    (always exactly one friendly Pilot card), read passively by
    ``compute_power`` — no trigger or decision machinery."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=0, count="other_friendly_pilots")],
    )


def _blue_leader_when_played(state, source_ci, target_id, event_ctx):
    """Blue Leader JTL_96 When Played: pay 2 resources, move to the ground arena,
    and give it 2 Experience tokens (the optional trigger's Accept IS the "you may
    pay 2 resources"; the ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` gate guarantees
    the payment can be made)."""
    from swu.engine.state import Zone
    from swu.engine.tokens import attach_token
    from swu.engine.actions import _exhaust_resources
    ps = state.player_by_id(source_ci.owner_id)
    _exhaust_resources(ps, 2)
    for arena in (ps.ground_arena, ps.space_arena):
        if source_ci in arena:
            arena.remove(source_ci)
            break
    source_ci.zone = Zone.GROUND_ARENA
    ps.ground_arena.append(source_ci)
    for up in source_ci.attached_upgrades:
        up.zone = Zone.GROUND_ARENA
    attach_token(state, ps, source_ci, "Experience")
    attach_token(state, ps, source_ci, "Experience")
    return state


@card_ability("JTL", "96")
def _blue_leader():
    """JTL_96 — Blue Leader (Unit, Fighter/Rebel/Vehicle, 3/3; Ambush — keyword
    layer): "When Played: You may pay 2 resources. If you do, move this unit to the
    ground arena and give 2 Experience tokens to it."

    An **optional** ``WhenPlayed`` (the "you may") whose one inline ``CustomEffect``
    pays 2 resources, relocates the unit from the space arena to the ground arena,
    and gives it 2 Experience tokens.  Gated by ``CONTROLLER_N_PLUS_READY_RESOURCES(2)``
    so it is offered only when the 2 resources can actually be paid (the "you may
    pay" is meaningful only then)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_blue_leader_when_played)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=2),
    )


def _leia_jtl_when_played(state, source_ci, target_id, event_ctx):
    """Leia Organa JTL_97 When Played: you may attack with a Pilot unit or a unit
    with a Pilot on it; it gets +1/+0 and gains Restore 1 for this attack.  A thin
    adapter onto ``push_granted_attack`` restricting the attacker to pilot-related
    units (``attacker_pilot_related``), granting +1/+0 and Restore 1 (the new
    ``(name, value)`` grant_keywords form) for the attack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1, optional=True,
                        attacker_pilot_related=True,
                        grant_keywords=[("Restore", 1)])
    return state


@card_ability("JTL", "97")
def _leia_organa_jtl_97():
    """JTL_97 — Leia Organa (Unit, Official/Rebel, 3/4; Restore 1 — keyword layer):
    "When Played: You may attack with a Pilot unit or a unit with a Pilot on it. It
    gets +1/+0 and gains Restore 1 for this attack."

    A ``WhenPlayed`` whose one ``CustomEffect`` is a thin adapter onto the
    granted-attack seam (the Snowtrooper Lieutenant SHD_236 pattern): the attacker
    is restricted to a Pilot unit or a unit carrying a Pilot upgrade
    (``attacker_pilot_related``), the "may" is ``optional=True``, and the chosen
    attacker gets +1/+0 (``power_bonus``) and Restore 1 (``grant_keywords`` with a
    numeric value) for that attack."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_leia_jtl_when_played)],
    )


def _tandem_assault(state, source_ci, target_id, event_ctx):
    """Tandem Assault JTL_124: attack with a space unit; if you do, attack with a
    ground unit (+2/+0).  Only when the controller has a ready space unit able to
    attack do we push BOTH granted attacks — ground first (resolves 2nd), space
    last (resolves 1st via LIFO) — so the mandatory space attack precedes the
    ground attack and "if you do" holds (with no space unit nothing is pushed)."""
    from swu.engine.actions import push_granted_attack, _enumerate_attacks
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(ps.player_id)]
    space_ids = {u.instance_id for u in ps.space_arena}
    if not any(a.attacker_id in space_ids
               for a in _enumerate_attacks(state, ps, opp)):
        return state
    push_granted_attack(state, source_ci, power_bonus=2, attacker_arena="ground")
    push_granted_attack(state, source_ci, attacker_arena="space")
    return state


@card_ability("JTL", "124")
def _tandem_assault_jtl_124():
    """JTL_124 — Tandem Assault (Event, Tactic): "Attack with a space unit. If you
    do, attack with a ground unit, and that ground unit gets +2/+0 for this
    attack."

    An ``EventAbility`` whose one ``CustomEffect`` pushes two granted attacks (the
    Outflank TWI_123 double-grant pattern), each arena-restricted via the new
    ``attacker_arena`` filter: a space-unit attack that resolves first, then a
    ground-unit attack (+2/+0) that resolves second.  Both are pushed only when a
    ready space unit exists, so the ground attack is contingent on the space
    attack ("If you do")."""
    return EventAbility(effects=[CustomEffect(fn=_tandem_assault)])


def _its_a_trap(state, source_ci, target_id, event_ctx):
    """It's a Trap JTL_209: if the opponent controls more space units than you,
    ready each of your space units (set ``exhausted=False``)."""
    ps = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(ps.player_id)]
    if len(opp.space_arena) > len(ps.space_arena):
        for u in ps.space_arena:
            u.exhausted = False
    return state


@card_ability("JTL", "209")
def _its_a_trap_jtl_209():
    """JTL_209 — It's a Trap (Event, Gambit): "If an opponent controls more space
    units than you, ready each space unit you control."

    A plain ``EventAbility`` whose one non-targeted inline ``CustomEffect`` compares
    space-unit counts and readies each friendly space unit when the opponent has
    more (a clean no-op otherwise)."""
    return EventAbility(effects=[CustomEffect(fn=_its_a_trap)])


# ── han-solo:05 — Combat tricks, buffs & tempo ────────────────────────────────

def _mando_jtl_210_exhaust_ground(state, source_ci, target_id, event_ctx):
    """The Mandalorian JTL_210 "When played as a unit": exhaust up to 2 ground
    units (a thin adapter onto the ``exhaust_combined_cost`` decision restricted to
    the ground arena, no cost budget, ``max_units=2``).  "Up to" includes 0."""
    from swu.engine.actions import push_exhaust_combined_cost
    push_exhaust_combined_cost(state, source_ci, budget=None, max_units=2,
                               arena="ground")
    return state


@card_ability("JTL", "210")
def _the_mandalorian_jtl_210():
    """JTL_210 — The Mandalorian (Unit, Bounty Hunter/Mandalorian/Pilot, 5/6;
    Piloting [2 resources Cunning]):
        "When played as a unit: Exhaust up to 2 ground units.
         Piloting [2 resources Cunning]
         When played as an upgrade: Exhaust an enemy unit in this arena."

    Piloting is the keyword layer.  Two mutually-exclusive triggers keyed to the
    play mode:
      * ``WhenPlayed(as_unit=True)`` — fires only on the normal unit play path
        (never when played as a Pilot upgrade).  A thin ``CustomEffect`` adapter
        onto ``push_exhaust_combined_cost`` restricted to the ground arena with
        ``max_units=2`` (the Qui-Gon's Lightsaber LOF_201 "exhaust any number"
        seam, capped and arena-filtered) — "Exhaust up to 2 ground units".
      * ``WhenPlayed(as_upgrade=True)`` — fires only on the Pilot-upgrade play path
        (the Boba Fett JTL_189 flag).  A mandatory ``ExhaustCard`` on an enemy unit
        in the host's arena, via the new ``same_arena_as_host`` predicate (reads the
        host from ``event_ctx["attached_to_id"]``) — "Exhaust an enemy unit in this
        arena".  Fizzles cleanly with no eligible enemy unit."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(as_unit=True),
            effects=[CustomEffect(fn=_mando_jtl_210_exhaust_ground)],
        ),
        TriggerAbility(
            trigger=WhenPlayed(as_upgrade=True),
            effects=[ExhaustCard(TargetSpec(
                controller="enemy", kind="unit",
                predicates=("same_arena_as_host",)))],
        ),
    ]


@card_ability("JTL", "217")
def _death_space_skirmisher_jtl_217():
    """JTL_217 — Death Space Skirmisher (Unit, Fighter/Underworld/Vehicle, 3/3):
    "When Played: If you control another space unit, you may exhaust a unit."

    An **optional** ``WhenPlayed`` (the "you may") gated by the new
    ``CONTROLLER_HAS_OTHER_SPACE_UNIT`` condition (the condition gates trigger
    collection, so the "you may exhaust" is offered only when another unit is in the
    controller's space arena — Death Space Skirmisher, itself a space unit, is the
    excluded source).  Its ``ExhaustCard`` targets any unit (``controller="any"`` —
    the controller points it at an enemy)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_SPACE_UNIT),
    )


@card_ability("JTL", "249")
def _millennium_falcon_jtl_249():
    """JTL_249 — Millennium Falcon (Unit, Rebel/Transport/Vehicle, 3/4):
        "You may play or deploy 1 additional Pilot on this unit.
         This unit gets +1/+0 for each Pilot on it."

    Two clauses, both passive:
      * The stat buff is a self-targeted scaling ``ConstantAbility`` with the new
        ``StatBonus.count="pilots_on_self"`` (the number of Pilot upgrades — or a
        leader deployed as an upgrade — attached to the Falcon), read passively by
        ``compute_power`` (the Nien Nunb JTL_93 scaling-StatBonus pattern).
      * The extra Pilot slot is an ``AdditionalPilotSlots(1)`` passive marker read
        at the pilot-attach seam (``_pilot_limit``), letting the Falcon host a
        second Pilot.  DEVIATION (documented on the marker): the engine does not
        enforce the standard one-Pilot-per-Vehicle limit on the normal ``PilotPlay``
        path (any Vehicle may already receive multiple Pilots), so this marker's
        functional effect is to relax the *leader-deploy-as-upgrade* Pilot cap (the
        one place a cap is checked); the "play an additional Pilot" case is free."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0, count="pilots_on_self")],
        ),
        AdditionalPilotSlots(count=1),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:06 — Miscellaneous abilities (JTL_103, JTL_245)
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("JTL", "103")
def _chewbacca_jtl_103():
    """JTL_103 — Chewbacca (Unit, Pilot/Rebel/Wookiee, 5/6, Piloting):
        "This unit can't be defeated or returned to hand by enemy card abilities.
         Attached unit gains: 'This unit can't be defeated or returned to hand by
         enemy card abilities.'"

    Both clauses are the SAME passive protection expressed once: a self-targeted
    ``ConstantAbility`` carrying a ``Protection(from_defeat, from_return)`` effect.
    By the "attached unit gains X" convention the keyword layer already uses (an
    upgrade's ``ConstantAbility(target=SELF, …)`` confers X on its host), this one
    ability protects Chewbacca while he is a unit AND, when he is played as a Pilot
    upgrade, protects the Vehicle he is attached to.

    Read (never routed) at the defeat/return effect seams
    (``resolver`` DefeatUnit / DefeatAllUnits / ReturnToHand arms via
    ``_target_protected``): an enemy ability's defeat/return simply skips a
    protected target.  Only *enemy* abilities are blocked; combat/damage defeat is
    untouched (it does not route through the DefeatUnit effect)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_defeat=True, from_return=True)],
    )


@card_ability("JTL", "245")
def _r2d2_jtl_245():
    """JTL_245 — R2-D2 (Unit, Droid/Pilot/Rebel, 1/4, Piloting [0]):
        "This upgrade can be played on a friendly Vehicle unit with a Pilot on it.
         Attached unit gains: 'You may play or deploy 1 additional Pilot on this
         unit.'"

    Only the second clause needs an ability; the first is already free — the engine
    does not enforce the "without a Pilot" restriction on the normal Piloting/
    PilotPlay path (``_eligible_pilot_targets`` returns every friendly Vehicle), so
    R2-D2 can already attach to a Vehicle that has a Pilot.

    The granted extra slot is the ``AdditionalPilotSlots(1)`` passive marker (from
    han-solo:05, Millennium Falcon): ``_pilot_limit`` now also scans a host's
    attached upgrades for the marker, so a Vehicle carrying R2-D2 may host one Pilot
    beyond R2-D2 itself (the leader-deploy-as-upgrade cap is the one place a Pilot
    limit is checked — the "play an additional Pilot" case is already free)."""
    return AdditionalPilotSlots(count=1)


# ── han-solo:07 — New primitive: scaling-magnitude (SOR_97, JTL_208) ───────────
# Both cards deal a magnitude that a fixed DealDamage cannot express.  Neither
# needs a *new* engine primitive:
#   * Admiral Ackbar (SOR_97) reuses the EXISTING DealDamageEqualTo scaling count
#     ``source_controller_units_in_target_arena`` (ahsoka-tano:06 / Synchronized
#     Strike TWI_99) verbatim — an optional WhenPlayed instead of an Event.
#   * Never Tell Me the Odds (JTL_208) has a *transient* magnitude (odd-cost cards
#     milled "this way").  It is an inline-resolve-then-push (Palpatine SOR_135 /
#     Ahsoka JTL_201): a no-target CustomEffect mills both decks, counts odd-cost
#     cards, then pushes the EXISTING ``select_damage`` decision (IG-2000 JTL_140)
#     with ``amount_each=<count>, max_targets=1`` — one clean "deal N to a unit"
#     prompt.  No new decision kind, no trigger/decision-machinery change.


@card_ability("SOR", "97")
def _admiral_ackbar_sor_97():
    """SOR_97 — Admiral Ackbar (Unit, Official/Rebel, 1/4, Restore 1): "When Played:
    You may deal damage to a unit equal to the number of units you control in its
    arena."

    Restore 1 is the keyword layer.  An **optional** ``WhenPlayed`` (the "you may")
    with one ``DealDamageEqualTo`` targeting any unit (``controller="any"`` — the
    printed text lets you pick friendly or enemy); the per-target magnitude is the
    existing ``source_controller_units_in_target_arena`` count (Synchronized Strike
    TWI_99) — the number of Ackbar-controller units sharing the chosen unit's arena.
    Being optional, it is auto-declined when no unit is on the board, and a
    magnitude of 0 (no friendly units in that arena) is a clean no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit"),
            count="source_controller_units_in_target_arena",
        )],
    )


def _never_tell_me_the_odds_fn(state, source_ci, target_id, event_ctx):
    """Mill 3 cards from the opponent's deck and 3 from the controller's deck,
    counting how many carry an odd printed cost, then push a ``select_damage``
    decision to deal that many damage to one chosen unit (the inline-resolve-then-
    push pattern — Palpatine SOR_135 / Ahsoka JTL_201).

    Each deck is milled from the top (no player choice — mills are always inline
    CustomEffects, there being no declarative deck-discard primitive); an empty
    deck simply mills fewer / zero cards.  The mill always happens (it needs no
    target); the damage is offered only when the count is positive and a unit is in
    play (``push_select_damage`` no-ops otherwise)."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_select_damage
    ctrl = state.player_by_id(source_ci.owner_id)
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    odd = 0
    for ps in (opp, ctrl):
        for _ in range(3):
            if not ps.deck:
                break
            card = ps.deck.pop(0)
            card.face_down = False
            card.zone = Zone.DISCARD
            ps.discard.append(card)
            cost = getattr(card.card_def, "cost", None)
            if cost is not None and cost % 2 == 1:
                odd += 1
    if odd > 0:
        push_select_damage(state, source_ci, amount_each=odd, max_targets=1)
    return state


@card_ability("JTL", "208")
def _never_tell_me_the_odds_jtl_208():
    """JTL_208 — Never Tell Me the Odds (Event, Gambit, cost 3): "Discard 3 cards
    from an opponent's deck and 3 cards from your deck. Deal damage to a unit equal
    to the number of cards with an odd cost discarded this way."

    A plain ``EventAbility`` with one no-target ``CustomEffect`` (an escape-hatch —
    the mill is inherently custom, and the damage magnitude is a *transient* value,
    the odd-cost cards milled "this way", that no declarative count spec can
    express).  The fn mills 3 from each deck, counts odd-cost cards, then reuses the
    existing ``select_damage`` decision (IG-2000 JTL_140) with ``amount_each=count,
    max_targets=1`` — one clean "deal N to a chosen unit" prompt, resolved through
    the standard damage path (defeat triggers, shields).  The mandatory mill always
    happens even with no unit on the board; a count of 0 pushes no damage decision.

    Minor deviation: ``select_damage`` is an "up to 1" choice, so the controller
    may decline to deal the (mandatory) damage or, with only friendly units on the
    board, is not forced to hit their own — player-friendly and rarely material."""
    return EventAbility(effects=[
        CustomEffect(fn=_never_tell_me_the_odds_fn),
    ])


# ── han-solo:08 — New primitive: control-change (JTL_235) ─────────────────────
# Composition of two existing seams — NO new decision kind, NO core-resolution
# change: actions.change_control (control is implicit = arena occupancy; Stolen
# Landspeeder SHD_161) plus a defeat_at_regroup-style one-shot flag
# (return_to_owner_hand_at_regroup) swept in _enter_regroup, whose return routes
# through the existing _apply_return_to_hand.

def _commandeer_fn(state, source_ci, target_id, event_ctx):
    """Take control of the chosen enemy Vehicle unit, ready it, and flag it to
    return to its owner's hand at the start of the next regroup phase.

    ``target_id`` is a non-leader Vehicle unit costing ≤6 with no Pilot on it (the
    TargetSpec below enumerates only those).  ``change_control`` relocates the
    instance into the caster's matching arena (owner_id unchanged); readying is a
    plain ``exhausted = False``; the delayed bounce is the
    ``return_to_owner_hand_at_regroup`` flag (mirrors Sneak Attack SOR_219's
    ``defeat_at_regroup``), swept in ``actions._enter_regroup`` through
    ``_apply_return_to_hand`` — which already sends a card to its OWNER's hand
    regardless of who controls it, so the unit goes home even while commandeered."""
    from swu.engine.actions import change_control
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, target_ci = res
    change_control(state, target_ci, source_ci.owner_id)  # "Take control"
    target_ci.exhausted = False                            # "If you do, ready it"
    target_ci.return_to_owner_hand_at_regroup = True       # delayed bounce
    return state


@card_ability("JTL", "235")
def _commandeer_jtl_235():
    """JTL_235 — Commandeer (Event, Trick, cost 5): "Take control of a non-leader
    Vehicle unit that costs 6 or less without a Pilot on it. If you do, ready it.
    At the start of the next regroup phase, return that unit to its owner's hand."

    A single targeted ``CustomEffect`` composing the existing control-change seam
    (actions.change_control — control is implicit arena occupancy, per Stolen
    Landspeeder SHD_161) with a ``defeat_at_regroup``-style delayed flag
    (``return_to_owner_hand_at_regroup``, swept in _enter_regroup via the existing
    _apply_return_to_hand).  The TargetSpec restricts the choice to Vehicle,
    non-leader, cost ≤6, and the new ``no_pilot`` predicate ("without a Pilot on
    it" — no attached Pilot upgrade / leader-as-upgrade).

    Faithful-intent simplification: ``controller="enemy"``.  The printed text is
    "a unit", which technically includes a unit you already control — but taking a
    unit you control changes nothing (change_control no-ops) and its "If you do"
    clause then does nothing either, so a friendly target is never a meaningful
    play.  Restricting to enemy units offers only the meaningful targets and makes
    control always change, so ready + delayed-return always apply.  A CustomEffect
    (not a bare declarative chain) is used because the atomic take-control → ready
    → schedule-return sequence spans three seams with no single declarative
    primitive; each step is an existing seam, so this is not an escape hatch for
    novel behaviour."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_commandeer_fn,
            target=TargetSpec(
                controller="enemy",
                kind="unit",
                traits=("Vehicle",),
                cost_max=6,
                predicates=("non_leader", "no_pilot"),
            ),
        ),
    ])


# ── Reprint-duplicate encodes (Stage 4 of docs/dev/plans/reprint_duplicates_plan.md) ────

@card_ability("JTL", "85")
def _victor_leader():
    """JTL_85 — Victor Leader (Unit, 2/4): "Each other friendly space unit gets
    +1/+1."

    A self-standing ``ConstantAbility`` buffing every *other* friendly space unit
    (the Red Three SOR_144 pattern with an arena filter), read passively by
    ``compute_power``/``compute_hp``.  ``not_self`` excludes Victor Leader; the
    ``space`` arena filter restricts to space units."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", arena="space",
                          predicates=("not_self",)),
        effects=[StatBonus(power=1, hp=1)],
    )


@card_ability("JTL", "33")
def _onyx_squadron_brute():
    """JTL_33 — Onyx Squadron Brute (Unit, 2/3): "When Defeated: Heal 2 damage
    from a base."

    A mandatory ``WhenDefeated`` healing the controller's own base
    (``fixed=EACH_FRIENDLY`` auto-targets the single friendly base, resolving
    inline — the 501st Liberator TWI_109 heal-own-base pattern)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
    )


@card_ability("JTL", "151")
def _red_five():
    """JTL_151 — Red Five (Unit, 3/4): "On Attack: You may deal 2 damage to a
    damaged unit."

    An optional ``OnAttack`` ``DealDamage(2, …)`` targeting any damaged unit (the
    ``damaged`` predicate).  Auto-declines when no damaged unit is on the board."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          predicates=("damaged",)))],
        optional=True,
    )


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonicals, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

@card_ability("JTL", "90")
def _executor():
    """JTL_90 — Executor (Unit, Imperial/Capital Ship, 12/12; Overwhelm = keyword
    layer): "When Played/On Attack/When Defeated: Create 3 TIE Fighter tokens."

    Three mandatory triggers (a ``WhenPlayed``, an ``OnAttack`` and a
    ``WhenDefeated``), each a non-targeted ``CreateTokenUnit("TIE Fighter", 3)``
    (the create-token-unit primitive, ahsoka-tano:05 / general-grievous:05) — the
    tokens enter the controller's space arena and resolve inline."""
    make = CreateTokenUnit("TIE Fighter", count=3)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[make]),
        TriggerAbility(trigger=OnAttack(), effects=[make]),
        TriggerAbility(trigger=WhenDefeated(), effects=[make]),
    ]


def _planetary_bombardment(state, source_ci, target_id, event_ctx):
    """Deal 8 indirect damage to the opponent, or 12 if the controller controls a
    Capital Ship unit (a conditional magnitude — the Zeb Orellios LAW_45 pattern),
    via the indirect-damage primitive (boba-fett:01)."""
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    has_capital = any(
        has_trait(state, u, "Capital Ship")
        for arena in (ps.ground_arena, ps.space_arena) for u in arena
    )
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=12 if has_capital else 8)
    return state


@card_ability("JTL", "181")
def _planetary_bombardment_event():
    """JTL_181 — Planetary Bombardment (Event): "Deal 8 indirect damage to a player.
    If you control a Capital Ship unit, deal 12 indirect damage instead."

    A plain ``EventAbility`` whose one non-targeted ``CustomEffect`` decides the
    magnitude (8 vs 12) from the board and pushes ``assign_indirect_damage`` (the
    opponent assigns the unpreventable damage among their base/units)."""
    return EventAbility(effects=[CustomEffect(fn=_planetary_bombardment)])


# ---------------------------------------------------------------------------
# Reprint-duplicate batch 6 (2026-07-08)
# ---------------------------------------------------------------------------


@card_ability("JTL", "256")
def _swarming_vulture_droid_jtl256():
    """JTL_256 — Swarming Vulture Droid (Unit): "A deck can have up to 15 copies of
    this card.  This unit gets +1/+0 for each other friendly Swarming Vulture
    Droid."

    The deck-copy limit is a deckbuild rule (handled in ``swu/cards/deckrules.py``),
    not an in-play ability.  The stat clause is a self-targeted scaling
    ``ConstantAbility`` (the Nien Nunb JTL_93 pattern) — the new
    ``StatBonus.count="other_friendly_same_name"`` scales the +1/+0 by the
    controller's arena units sharing this card's printed name, excluding itself,
    read passively by ``compute_power``."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=0, count="other_friendly_same_name")],
    )


# ---------------------------------------------------------------------------
# Stage-4 reprint sweep (Batch 8, 2026-07-08) — shipped-set canonical encodes.
# Siblings aliased in src/swu/cards/reprints.py.
# ---------------------------------------------------------------------------


def _shoot_down_fn(state, source_ci, target_id, event_ctx):
    """Deal 3 to the chosen space unit, then record whether it was defeated so the
    follow-up "you may deal 2 to a base" can gate on it (``requires_prior_defeat``)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 3,
                       source_name=getattr(source_ci.card_def, "name", None))
    # A defeated unit has left play (no longer found in any zone/arena in-play).
    res = state.find_instance(target_id)
    defeated = res is None or res[1].zone.name not in ("GROUND_ARENA", "SPACE_ARENA")
    event_ctx["prior_target_defeated"] = bool(defeated)
    return state


@card_ability("JTL", "176")
def _shoot_down_jtl176():
    """JTL_176 Shoot Down (Event cost 2): "Deal 3 damage to a space unit. If that
    unit is defeated this way, you may deal 2 damage to a base."

    Two effects sharing the resolve_effects ``event_ctx``: a mandatory
    ``CustomEffect.target`` (a space unit, any controller) deals 3 and records the
    defeat under ``event_ctx["prior_target_defeated"]``; an optional
    ``DealDamage(2, a base)`` whose target carries the new ``requires_prior_defeat``
    predicate (reads that flag), so the base-damage is offered only when the space
    unit actually died (else no candidate → no prompt, honouring "If … defeated")."""
    return EventAbility(effects=[
        CustomEffect(fn=_shoot_down_fn,
                     target=TargetSpec(controller="any", kind="unit", arena="space")),
        DealDamage(2, TargetSpec(controller="any", kind="base",
                                 predicates=("requires_prior_defeat",),
                                 optional=True)),
    ])


@card_ability("JTL", "204")
def _home_one_jtl204():
    """JTL_204 Home One (Unit 7/8, Ambush): "If an opponent controls 3 or more space
    units, this unit costs 3 resources less to play."

    Ambush is the keyword layer.  The cost reduction is a declarative
    ``CostReduction(amount=3)`` gated by the new ``ENEMY_N_PLUS_SPACE_UNITS(3)``
    condition, read by the play-cost path (Force Choke SOR_139 pattern) so it
    affects both affordability and the resources actually paid, floored at 0."""
    return CostReduction(
        amount=3,
        condition=ConditionCheck(Condition.ENEMY_N_PLUS_SPACE_UNITS, 3),
    )


@card_ability("JTL", "143")
def _devastator_jtl143():
    """JTL_143 — Devastator (Unit 9/6): "You assign all indirect damage you deal to
    opponents.  When Played: Deal 4 indirect damage to each opponent."

    Two specs.  The static "You assign all indirect damage" is a passive
    ``IndirectDamageSelfAssign`` marker read at the indirect-damage chokepoint
    (``push_assign_indirect_damage``): while Devastator is in play, ITS controller
    (not the receiving player) picks which of the opponent's base/units absorbs the
    indirect damage — the additive decider flip added for this card.  The WhenPlayed
    is a thin no-target ``CustomEffect`` adapter onto ``push_assign_indirect_damage``
    (the First Order Stormtrooper JTL_132 pattern); "each opponent" is the single
    opponent in a 2-player game, so one push of 4."""
    def _deal_4_indirect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source_ci, amount=4)
        return state

    return [
        IndirectDamageSelfAssign(),
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_deal_4_indirect)]),
    ]


@card_ability("JTL", "154")
def _profundity_jtl154():
    """JTL_154 — Profundity (Unit 8/9, Overwhelm): "When Played/When Defeated:
    Choose a player.  They discard a card from their hand.  Then, if they have more
    cards in their hand than you, they discard a card from their hand."

    Overwhelm is the keyword layer.  Two triggers (a ``WhenPlayed`` and a
    ``WhenDefeated``), each a no-target ``CustomEffect``: "choose a player" resolves
    to the opponent (choosing yourself is self-harm, never the play), who discards
    the first card of their hand (the established K-2SO SOR_145 / J-Type Nubian
    Starship LOF_194 first-card simplification), and then — only if they now hold
    more cards than the controller — discards a second.  Bound inline so the
    conditional second discard reads the post-first-discard hand sizes."""
    def _profundity_discard(state, source_ci, target_id, event_ctx):
        from swu.engine.state import Zone
        ctrl = state.player_by_id(source_ci.owner_id)
        opp = state.players[1 - state.player_index(source_ci.owner_id)]

        def _discard_first():
            if opp.hand:
                ci = opp.hand.pop(0)
                ci.zone = Zone.DISCARD
                opp.discard.append(ci)

        _discard_first()
        # "Then, if they have more cards in their hand than you" (the controller).
        if len(opp.hand) > len(ctrl.hand):
            _discard_first()
        return state

    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_profundity_discard)]),
        TriggerAbility(trigger=WhenDefeated(), effects=[CustomEffect(fn=_profundity_discard)]),
    ]


# ── Reprint-duplicate batch 12 (Stage 4) ──────────────────────────────────────

def _han_solo_203_pilot_attack(state, source_ci, target_id, event_ctx):
    """Han Solo JTL_203 "When played as an upgrade": the attached host attacks;
    if the host is the Millennium Falcon it deals its combat damage before the
    defender (First Strike) for that attack.  The host id is threaded in
    ``event_ctx["attached_to_id"]`` by the pilot-play path.  ``attacker_id`` pins
    the offered attack to the host (the Hotshot DL-44 SHD_174 pin); ``optional`` is
    the "you may".  A vanished host is a clean no-op."""
    from swu.engine.actions import push_granted_attack
    host_id = (event_ctx or {}).get("attached_to_id")
    if not host_id:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    host = res[1]
    grant = (["First Strike"]
             if getattr(host.card_def, "name", None) == "Millennium Falcon" else None)
    push_granted_attack(state, source_ci, attacker_id=host_id, optional=True,
                        grant_keywords=grant)
    return state


@card_ability("JTL", "203")
def _han_solo_jtl_203():
    """JTL_203 — Han Solo (Unit, Rebel/Pilot, 4/5; Ambush, Piloting [2 resources
    Cunning Heroism]): "When played as an upgrade: You may attack with attached
    unit. If it's the Millennium Falcon, it deals its combat damage before the
    defender."

    Ambush and Piloting are the keyword layer.  Played as a normal unit Han is a
    vanilla 4/5; the only ability fires on the Pilot-upgrade play path
    (``WhenPlayed(as_upgrade=True)`` — the Boba Fett JTL_189 flag).  Its one
    ``CustomEffect`` is a thin adapter onto ``push_granted_attack`` pinned to the
    host (``attacker_id``) with ``optional=True`` (the "you may"); when the host is
    the Millennium Falcon it also grants First Strike for that attack
    (``grant_keywords=["First Strike"]`` — the same keyword the combat pipeline
    already reads, Incinerator Trooper SHD_234)."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(fn=_han_solo_203_pilot_attack)],
    )


def _darth_vader_142_on_attack_first(state, source_ci, target_id, event_ctx):
    """Darth Vader JTL_142 granted On Attack, effect 1: "You may deal 1 damage to a
    unit."  Deals 1 to the chosen unit and records into the shared resolve_effects
    ``event_ctx`` whether that damage defeated it (target no longer in an arena),
    so the follow-up effect can gate on "If a unit is defeated this way" (the
    Grenade Strike TWI_171 two-effect shared-event_ctx pattern).  A ``None`` target
    (declined) leaves the flag unset."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    state = _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
    # "If a unit is defeated this way": the target left its arena (moved to discard
    # or vanished).  find_instance still locates a defeated unit in discard, so
    # check that it is no longer in an arena.
    res = state.find_instance(target_id)
    if res is None or res[1].zone.name not in ("GROUND_ARENA", "SPACE_ARENA"):
        event_ctx["prior_target_defeated"] = True
    return state


def _darth_vader_142_on_attack_second(state, source_ci, target_id, event_ctx):
    """Darth Vader JTL_142 granted On Attack, effect 2: "If a unit is defeated this
    way, you may deal 1 damage to a unit or base."  Gated by the existing
    ``requires_prior_defeat`` predicate (so it is offered only when effect 1
    recorded a defeat); deals 1 to the chosen unit or base."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)


@card_ability("JTL", "142")
def _darth_vader_jtl_142():
    """JTL_142 — Darth Vader (Unit, Imperial/Sith/Force/Pilot, 7/7; Piloting [3
    resources Aggression Villainy]): "Attached unit gains: 'On Attack: You may deal
    1 damage to a unit. If a unit is defeated this way, you may deal 1 damage to a
    unit or base.'"

    Piloting is the keyword layer.  The card's only ability is a Pilot grant, so it
    is a ``GrantedAbility`` wrapping an ``OnAttack`` that resolves from the HOST
    (the Dengar JTL_139 / Armed to the Teeth SHD_175 pattern) — played as a normal
    unit Vader is a vanilla 7/7.  Two dependent optional ``CustomEffect.target``
    effects share the resolve_effects ``event_ctx`` (the Grenade Strike TWI_171
    pattern): effect 1 deals 1 to a chosen unit and records whether it was defeated;
    effect 2 (existing ``requires_prior_defeat`` predicate, ``kind="unit_or_base"``)
    is offered only when that defeat happened and deals 1 more.  Both target specs are
    ``optional`` (the two "you may"s)."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[
            CustomEffect(
                fn=_darth_vader_142_on_attack_first,
                target=TargetSpec(controller="any", kind="unit", optional=True),
            ),
            CustomEffect(
                fn=_darth_vader_142_on_attack_second,
                target=TargetSpec(controller="any", kind="unit_or_base",
                                  predicates=("requires_prior_defeat",),
                                  optional=True),
            ),
        ],
    ))


# ── Stage 4 batch 28 (2026-07-13) — FRAMEWORK ESCALATION: the keyword-copy aura
#    ("each other friendly <trait> unit gains this unit's keywords").  Lives
#    entirely in the keyword-query layer (keywords.has_keyword/keyword_value) — the
#    same functions batch 27's permanent keyword-grant touched — via the new
#    CopyKeywords ConstantAbility effect.  NO new decision kind, NO combat pipeline.
# ─────────────────────────────────────────────────────────────────────────────
@card_ability("JTL", "53")
def _the_ghost_jtl53():
    """JTL_53 — The Ghost "Heart of the Family" (5/6): "Each other friendly Spectre
    unit gains this unit's keywords.  While this unit is upgraded, it gains
    Sentinel."

    Two ``ConstantAbility`` specs (both passive — read by the keyword layer, never
    routed through the resolver):

    * A ``CopyKeywords`` aura over every OTHER friendly Spectre unit — the keyword
      layer scans for this and reports each such unit as having whatever keywords
      The Ghost currently has (the batch-28 primitive).
    * A conditional self-grant of Sentinel while upgraded (the Cinta Kaz LAW_105 /
      Protector of the Throne SHD_247 pattern) — so the copy confers Sentinel to
      the other Spectres only while The Ghost is upgraded.  The keyword sanitiser's
      conditional-self-grant rule strips The Ghost's DB-mistagged *printed* Sentinel
      because this ability owns it (verified: the printed Sentinel is not always-on).
    """
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Spectre",), predicates=("not_self",)),
            effects=[CopyKeywords()],
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
            condition=ConditionCheck(Condition.SOURCE_UPGRADED),
        ),
    ]


# ── Group padme-amidala:02 — Combat tricks, buffs & tempo ─────────────────────

@card_ability("JTL", "111")
def _seasoned_fleet_admiral():
    """JTL_111 — Seasoned Fleet Admiral (Unit, Official/Rebel/Twi'lek, Raid 1 —
    keyword layer): "When an opponent draws 1 or more cards during the action
    phase: You may give an Experience token to a unit."

    Raid 1 is the keyword layer.  An optional ``WhenYouDraw(opponent=True)``
    observer (the new ``opponent`` flag inverts the in-play draw match to fire when
    an opponent drew — mirroring The Mandalorian LAW_52's self-draw observer,
    fired at the action-phase-draw settle-point).  Its one ``GiveToken("Experience")``
    targets any unit; the "you may" is ``optional=True`` (always at least the Admiral
    himself as a friendly recipient, so it is offered)."""
    return TriggerAbility(
        trigger=WhenYouDraw(opponent=True),
        optional=True,
        effects=[GiveToken("Experience",
                           TargetSpec(controller="any", kind="unit"))],
    )


def _dogfight_attack(state, source_ci, target_id, event_ctx):
    """Dogfight JTL_123: attack with a friendly unit even if exhausted; that unit
    can't attack a base for this attack (the granted_attack allow_exhausted+no_base
    seam, the Dogfight/Shoot First family)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, allow_exhausted=True, no_base=True)
    return state


@card_ability("JTL", "123")
def _dogfight():
    """JTL_123 — Dogfight (Event, Tactic): "Attack with a unit, even if it's
    exhausted. That unit can't attack bases for this attack."

    A plain ``EventAbility`` whose one no-target ``CustomEffect`` is a thin adapter
    onto ``push_granted_attack`` with ``allow_exhausted`` (exhausted attacker
    allowed) and ``no_base`` (bases off-limits for this attack).  Mandatory-if-able:
    with no friendly unit to attack, the granted-attack decision simply isn't
    pushed."""
    return EventAbility(effects=[CustomEffect(fn=_dogfight_attack)])


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:01 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════
#
# ⚠️ JTL_1 SHARES ITS (set, number) WITH THE **TIE FIGHTER TOKEN** — ``get_abilities``
# is keyed on the strings alone, so every spec registered on "JTL"/"1" is also read
# for each TIE Fighter token sitting in an arena.  Asajj's registration is therefore
# built only from specs a token can never reach:
#   * ``ActivatedAbility(undeployed_only=True)`` — the arena scan in ``legal_actions``
#     and ``resolver._collect_triggers`` requires a **Leader** card_def for an
#     undeployed-side spec (the twi-set:19 guard), and a token is no Leader.
#   * ``GrantedAbility`` — collected ONLY from a host's ``attached_upgrades``; the
#     arena trigger scan skips it outright (``isinstance(spec, TriggerAbility)``).
#   * ``TriggerAbility(WhenDeployed(via_pilot_leader=True))`` — matched by instance
#     id against a ``LeaderDeployed`` event, which a token can never be the subject of.
# A ``ConstantAbility`` or a passive marker would NOT be safe here: the constant-stat
# and keyword scans walk arena units by (set, number) with no leader gate, so Asajj's
# "It gains Grit" is granted as a permanent modifier from her deploy-as-an-upgrade
# trigger rather than as a self-targeted ``KeywordGrant`` constant.


def _asajj_chain_first(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the chosen FRIENDLY unit, then record its arena and the fact
    that a target was chosen at all, so the follow-up "deal 1 damage to an enemy unit
    in the same arena" is gated by ``same_arena_as_event`` + ``requires_prior_target``
    (the Haymaker LAW_168 shared-``event_ctx`` chain, which is also the "If you do"
    binding — no friendly unit chosen ⇒ the enemy half has no candidates and fizzles
    without a prompt)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _, unit = res
    event_ctx["same_arena"] = "space" if unit.zone == Zone.SPACE_ARENA else "ground"
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)


_ASAJJ_CHAIN = [
    CustomEffect(fn=_asajj_chain_first,
                 target=TargetSpec(controller="friendly", kind="unit")),
    DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                             predicates=("same_arena_as_event",
                                         "requires_prior_target"))),
]


def _asajj_grant_grit_to_host(state, source_ci, target_id, event_ctx):
    """"It gains Grit": grant the host a PERMANENT ``keyword_grant`` modifier when
    Asajj deploys as a Pilot upgrade onto it (host id from
    ``event_ctx["attached_to_id"]``, threaded by ``DeployLeaderAsUpgrade``).

    A permanent keyword grant is gated by ``keywords._permanent_kw_source_in_play``,
    which counts an attached upgrade as in play — so the grant lives exactly as long
    as Asajj is attached and lapses the moment she leaves, which is what an "attached
    unit gains" clause means.  The usual ``ConstantAbility(SELF, KeywordGrant)`` shape
    is deliberately avoided here (see the TIE Fighter token note above)."""
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import execute_effect
    return execute_effect(
        state, GrantKeyword("Grit", 0, target=TargetSpec(),
                            duration=Duration.PERMANENT),
        source_ci, host_id, event_ctx)


@card_ability("JTL", "1")
def _asajj_ventress_jtl_1():
    """JTL_1 — Asajj Ventress, I Work Alone (Leader, Force/Night/Bounty Hunter/Pilot,
    4/6 with Grit; +3/+4 as a Pilot upgrade).

    * **Undeployed** "Action [Exhaust]: Deal 1 damage to a friendly unit.  If you do,
      deal 1 damage to an enemy unit in the same arena." — an ``ActivatedAbility``
      with the two-step ``_ASAJJ_CHAIN`` (two targeted effects ⇒ two sequential
      ChooseTarget steps).
    * **Deployed as a unit**: Grit only, handled by the keyword layer (no spec).
    * **Deployed as an upgrade** "Attached unit is a leader unit.  It gains Grit
      and: 'On Attack: You may deal 1 damage to a friendly unit.  If you do, deal 1
      damage to an enemy unit in the same arena.'" — the Grit half is the permanent
      grant above, the ability half is the same chain wrapped in a ``GrantedAbility``
      (so it resolves from the HOST as source), and "is a leader unit" needs no spec:
      ``resolver._is_leader_unit`` counts any unit carrying a Leader pilot.
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=list(_ASAJJ_CHAIN),
            title="Deal 1 to a friendly unit, then 1 to an enemy in that arena",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(via_pilot_leader=True),
            effects=[CustomEffect(fn=_asajj_grant_grit_to_host)],
        ),
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=list(_ASAJJ_CHAIN),
            optional=True,
        )),
    ]


def _phasma_hit_unit(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen unit and stamp ``prior_target_id``, so the follow-up base
    damage happens only "if you do" (``requires_prior_target``)."""
    if target_id is None:
        return state
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)


@card_ability("JTL", "10")
def _captain_phasma_jtl_10():
    """JTL_10 — Captain Phasma, Chrome Dome (Leader, First Order/Trooper, 4/6).

    * **Undeployed** "Action [Exhaust]: If you played a First Order card this phase,
      deal 1 damage to a base." — gated by the new
      ``CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE`` atom so the exhaust is never spent
      on a no-op (the "don't offer a no-op" rule).
    * **Deployed** "On Attack: If you played another First Order card this phase, you
      may deal 1 damage to a unit.  If you do, deal 1 damage to a base." — the same
      gate on trigger collection, then the "If you do" chain (a targeted unit damage
      that stamps ``prior_target_id``, then a base damage gated by
      ``requires_prior_target``).

    DEVIATION: "another" reads identically to "a" here.  A leader is never *played*,
    so Phasma can contribute nothing to the ledger herself and there is no other card
    the word could be excluding — both sides ask for ≥1 First Order card played this
    phase.
    """
    played_fo = ConditionCheck(Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE,
                               param="First Order")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
            title="Deal 1 damage to a base",
            condition=played_fo,
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                CustomEffect(fn=_phasma_hit_unit,
                             target=TargetSpec(controller="any", kind="unit")),
                DealDamage(1, TargetSpec(controller="any", kind="base",
                                         predicates=("requires_prior_target",))),
            ],
            optional=True,
            condition=played_fo,
            deployed_only=True,
        ),
    ]


@card_ability("JTL", "12")
def _luke_skywalker_jtl_12():
    """JTL_12 — Luke Skywalker, Hero of Yavin (Leader, Force/Rebel/Pilot, 5/6; +4/+5
    as a Pilot upgrade).

    * **Undeployed** "Action [Exhaust]: If you attacked with a Fighter unit this
      phase, deal 1 damage to a unit." — pure reuse of
      ``CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE``.  That atom excludes the
      SOURCE, which costs nothing here: an undeployed leader never attacks (the
      Bo-Katan SHD_12 reading).
    * **As an upgrade** "This upgrade can't be defeated by enemy card abilities." —
      a self-targeted ``Protection(from_defeat=True, upgrade_only=True)``.  The new
      ``upgrade_only`` flag is what keeps this honest: unlike Chewbacca JTL_103's
      "this unit … / attached unit gains …", Luke's clause protects ONLY the upgrade,
      so it must not cover Luke deployed as a unit nor the Vehicle he is riding.
    * **As an upgrade** "Attached unit is a leader unit.  If it's a Fighter, it gains:
      'On Attack: You may deal 3 damage to a unit.'" — a ``GrantedAbility`` gated on
      ``SOURCE_HAS_TRAIT("Fighter")``, which for a granted ability is evaluated
      against the HOST.  "Is a leader unit" needs no spec (``_is_leader_unit``).
    """
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            title="Deal 1 damage to a unit",
            condition=ConditionCheck(
                Condition.CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE,
                param="Fighter"),
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[Protection(from_defeat=True, upgrade_only=True)],
        ),
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(3, TargetSpec(controller="any", kind="unit"))],
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Fighter"),
        )),
    ]


@card_ability("JTL", "37")
def _banshee_jtl_37():
    """JTL_37 — Banshee, Crippling Command (Unit, Separatist/Vehicle/Fighter, 4/5):
    "On Attack: You may deal damage to a unit equal to the amount of damage on this
    unit."

    Pure reuse — ``DealDamageEqualTo`` with the ``source_damage`` count (Krrsantan
    SHD_139).  Undamaged Banshee deals 0, which the optional trigger lets the
    controller simply decline."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamageEqualTo(TargetSpec(controller="any", kind="unit"),
                                   count="source_damage")],
        optional=True,
    )


@card_ability("JTL", "40")
def _fleet_interdictor_jtl_40():
    """JTL_40 — Fleet Interdictor (Unit, Imperial/Vehicle/Capital Ship, 6/6,
    Sentinel): "When Defeated: You may defeat a space unit that costs 3 or less."

    Pure reuse — an optional ``WhenDefeated`` whose ``DefeatUnit`` is narrowed by
    ``arena="space"`` + ``cost_max=3``.  ``controller="any"`` as printed: the
    Interdictor may take down a friendly cheap ship if that is what the controller
    wants (the optional trigger means it never has to)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       arena="space", cost_max=3))],
        optional=True,
    )


def _no_glory_only_results(state, source_ci, target_id, event_ctx):
    """Take control of the chosen non-leader unit, then defeat it.

    Control is implicit (whichever arena list holds the unit), so
    ``actions.change_control`` relocates it into the controller's matching arena
    before ``_apply_defeat_unit`` kills it.  ``owner_id`` never changes, so the card
    still goes to its OWNER's discard — the point of the detour is that it dies while
    YOU control it, so friendly "when a unit you control is defeated" triggers see it
    and the opponent's do not."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import change_control
    from swu.abilities.resolver import _apply_defeat_unit
    change_control(state, res[1], source_ci.owner_id)
    return _apply_defeat_unit(state, target_id)


@card_ability("JTL", "43")
def _no_glory_only_results_jtl_43():
    """JTL_43 — No Glory, Only Results (Event, Tactic, 5): "Take control of a
    non-leader unit, then defeat it."

    Pure composition of the two existing seams (``change_control`` +
    ``_apply_defeat_unit``) in ONE ``CustomEffect.target`` — they must be atomic, so
    the unit cannot be left under the wrong control if the defeat fizzles."""
    return EventAbility(effects=[
        CustomEffect(fn=_no_glory_only_results,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader",))),
    ])


@card_ability("JTL", "46")
def _paige_tico_jtl_46():
    """JTL_46 — Paige Tico, Dropping the Hammer (Unit, Resistance/Pilot, 3/2,
    Piloting 2): "Attached unit gains: 'On Attack: Give an Experience token to this
    unit, then deal 1 damage to it.'"

    Piloting itself is the keyword engine's (the ``PilotPlay`` path).  The residual
    is one ``GrantedAbility``: both effects are ``fixed=SELF`` and a granted ability
    resolves from the HOST, so "this unit" is the Vehicle Paige is riding — it grows
    +1/+1 from the Experience token and takes 1 damage, a net +1/+0 per attack with a
    slow bleed.  Both are no-target, so the whole trigger resolves inline."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[
            GiveToken("Experience", TargetSpec(fixed=SELF)),
            DealDamage(1, TargetSpec(fixed=SELF)),
        ],
    ))


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _red_squadron_self_damage_draw(state, source_ci, target_id, event_ctx):
    """"You may deal 2 damage to this unit.  If you do, draw a card."  Cost and
    payoff in ONE CustomEffect (the Bright Hope SOR_99 "If you do" binding) so the
    draw can never happen without the self-damage — the optional trigger's Accept IS
    the "you may".  The X-Wing is 3/4, so 2 damage never kills it outright, but the
    damage is dealt first and the draw follows unconditionally, as printed."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import _draw_cards
    state = _apply_deal_damage(state, source_ci.instance_id, 2,
                               source_ci.card_def.display_name)
    _draw_cards(state, state.player_by_id(source_ci.owner_id), 1)
    return state


@card_ability("JTL", "51")
def _red_squadron_x_wing_jtl_51():
    """JTL_51 — Red Squadron X-Wing (Unit, Rebel/Vehicle/Fighter, 3/4): "When Played:
    You may deal 2 damage to this unit.  If you do, draw a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_red_squadron_self_damage_draw)],
        optional=True,
    )


def _all_clear_kid_defeat(state, source_ci, target_id, event_ctx):
    """Defeat the chosen enemy space unit and stamp ``prior_target_id`` so the
    follow-up token half's "if you do" gate holds."""
    if target_id is None:
        return state
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_defeat_unit
    return _apply_defeat_unit(state, target_id)


@card_ability("JTL", "55")
def _youre_all_clear_kid_jtl_55():
    """JTL_55 — You're All Clear, Kid (Event, Gambit, 2): "Defeat an enemy space unit
    with 3 or less remaining HP.  If you do and an opponent controls no space units,
    you may give an Experience token to a unit."

    Two sequential effects sharing the ``resolve_effects`` ``event_ctx``.  The defeat
    is a plain targeted ``DefeatUnit`` narrowed by ``arena="space"`` +
    ``hp_remaining_max=3``.  The token half is gated by TWO predicates that between
    them spell the whole conditional: ``requires_prior_target`` ("if you do") and the
    new ``opponent_no_space_units`` board gate.  The gate is read AFTER the defeat
    resolves, which is exactly right — clearing their last space unit with this very
    card satisfies it.  Failing either yields no candidates, so the token half fizzles
    silently; ``optional=True`` on the spec honours the "you may" when it doesn't."""
    return EventAbility(effects=[
        CustomEffect(fn=_all_clear_kid_defeat,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       arena="space", hp_remaining_max=3)),
        GiveToken("Experience", TargetSpec(
            controller="any", kind="unit", optional=True,
            predicates=("requires_prior_target", "opponent_no_space_units"))),
    ])


@card_ability("JTL", "62")
def _silver_angel_jtl_62():
    """JTL_62 — Silver Angel, Trace's Hope (Unit, Fringe/Vehicle/Transport, 2/3):
    "When 1 or more damage is healed from this unit: You may deal 1 damage to a space
    unit."

    The new ``WhenUnitHealed`` observer — a settle-drain trigger over the heal ledger
    ``game_memory.heal_events``, fed at the single heal chokepoint
    ``actions.note_unit_healed`` (which already ignores no-op heals, so an entry IS
    "1 or more damage healed").  Self-referential: the ledger entry must be the Silver
    Angel's own instance id."""
    return TriggerAbility(
        trigger=WhenUnitHealed(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                          arena="space"))],
        optional=True,
    )


@card_ability("JTL", "78")
def _direct_hit_jtl_78():
    """JTL_78 — Direct Hit (Event, Tactic, 4): "Defeat a non-leader Vehicle unit."

    Pure reuse.  Note that ``non_leader`` now also excludes a Vehicle piloted by a
    deployed leader ("Attached unit is a leader unit"), so a Luke- or Asajj-crewed
    fighter is out of reach — which is the printed interaction."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit", traits=("Vehicle",),
                              predicates=("non_leader",))),
    ])


@card_ability("JTL", "80")
def _nebula_ignition_jtl_80():
    """JTL_80 — Nebula Ignition (Event, Disaster, 9): "Defeat each unit that isn't
    upgraded."

    A symmetric board wipe: ``DefeatAllUnits`` over every unit in play narrowed by the
    new ``not_upgraded`` predicate.  A Shield or Experience TOKEN is an upgrade, so a
    shielded unit survives — the card's whole tension."""
    return EventAbility(effects=[
        DefeatAllUnits(TargetSpec(controller="any", kind="unit",
                                  predicates=("not_upgraded",))),
    ])


@card_ability("JTL", "91")
def _apology_accepted_jtl_91():
    """JTL_91 — Apology Accepted (Event, Tactic, 1): "Defeat a friendly unit.  You may
    give 2 Experience tokens to a unit."

    Two independent targeted effects — the second sentence is NOT conditional on the
    first (no "if you do"), so the token half has no ``requires_prior_target`` gate and
    still resolves when the controller has no unit to sacrifice.  ``count=2`` gives
    both tokens to the one chosen unit."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="friendly", kind="unit")),
        GiveToken("Experience", TargetSpec(controller="any", kind="unit",
                                           optional=True), count=2),
    ])


@card_ability("JTL", "102")
def _resistance_blue_squadron_jtl_102():
    """JTL_102 — Resistance Blue Squadron (Unit, Resistance/Vehicle/Fighter, 3/4):
    "When Played: You may deal damage to a unit equal to the number of friendly space
    units."

    ``DealDamageEqualTo`` with the new ``source_controller_space_units`` count.  The
    Squadron is itself a space unit and has already entered play when its When Played
    resolves, so it counts itself — "units you control", not "other units"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamageEqualTo(TargetSpec(controller="any", kind="unit"),
                                   count="source_controller_space_units")],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:03 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("JTL", "104")
def _raddus_jtl_104():
    """JTL_104 — Raddus, Holdo's Final Command (Unit, Resistance/Vehicle/Capital Ship,
    8/6): "While you control another Resistance card (unit, upgrade, or leader), this
    unit gains Sentinel." + "When Defeated: Deal damage equal to this unit's power to
    an enemy unit."

    The conditional self-grant is the standard shape (Protector SHD_247): a
    ``ConstantAbility(SELF, KeywordGrant)`` read passively by ``has_keyword``, whose
    presence makes the keyword sanitiser strip the DB's mis-tagged printed Sentinel —
    so a lone Raddus really does lack it.  The gate is the new
    ``CONTROLLER_HAS_OTHER_TRAIT_CARD_IN_PLAY`` atom: self-excluding (Raddus is himself
    Resistance) and widened to base_zone so an undeployed Resistance leader satisfies
    "or leader".

    The death rattle is ``DealDamageEqualTo(count="source_power")`` — his *effective*
    power, read at the moment the trigger resolves.  ``_defeat_unit`` moves him to the
    discard before firing, but ``compute_power`` needs no arena, so an 8-power Raddus
    still swings for 8 on the way out."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_OTHER_TRAIT_CARD_IN_PLAY,
                param="Resistance"),
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DealDamageEqualTo(TargetSpec(controller="enemy", kind="unit"),
                                       count="source_power")],
        ),
    ]


def _dornean_gunship_indirect(state, source_ci, target_id, event_ctx):
    """Deal indirect damage to the opponent equal to the number of Vehicle units the
    source's controller has in play (both arenas; the Gunship is itself a Vehicle and
    has already entered play, so it counts itself).  0 Vehicles is impossible here,
    but the guard keeps the decision from being pushed for nothing."""
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in (ps.ground_arena + ps.space_arena)
            if has_trait(state, u, "Vehicle"))
    if n > 0:
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source_ci, amount=n)
    return state


@card_ability("JTL", "116")
def _dornean_gunship_jtl_116():
    """JTL_116 — Dornean Gunship (Unit, Rebel/Vehicle/Capital Ship, 4/6): "When
    Played: Deal indirect damage to a player equal to the number of Vehicle units you
    control."

    A thin ``CustomEffect`` adapter onto the ``assign_indirect_damage`` decision — the
    receiving player assigns the whole amount among their base and units, bypassing
    shields."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_dornean_gunship_indirect)],
    )


@card_ability("JTL", "120")
def _dorsal_turret_jtl_120():
    """JTL_120 — Dorsal Turret (Upgrade, Modification/Weapon, 1): "Attach to a Vehicle
    unit.  Attached unit gains: 'When this unit deals combat damage to a unit while
    attacking: Defeat that unit.'"

    Pure reuse of the Rukh SOR_85 pair — ``WhenDealsCombatDamageToUnit`` is precisely
    "deals combat damage to a unit WHILE ATTACKING" (it fires only on the attacker
    side, and only when the defender survived the exchange), and ``DEFENDER`` is
    "that unit".  The attach restriction is parsed straight off the card text by
    ``_upgrade_target_spec``, so no TargetSpec is written here."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenDealsCombatDamageToUnit(),
        effects=[DefeatUnit(TargetSpec(kind="unit", fixed=DEFENDER))],
    ))


def _salvage_play_vehicle_from_discard(state, source_ci, target_id, event_ctx):
    """Play a Vehicle unit from the controller's DISCARD (paying its cost), then deal
    1 damage to it.

    ``push_play_from_hand(from_discard=True)`` offers hand *and* discard, but Salvage
    is discard-only — so the eligible set is computed here and handed over as
    ``eligible_ids`` (the Now There Are Two of Them TWI_225 computed-whitelist
    pattern; ``eligible_ids`` is a general zone filter, not a discard-only one).
    ``then_damage=1`` is the existing "then deal N to the played unit" field."""
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    eligible = frozenset(
        ci.instance_id for ci in ps.discard
        if isinstance(ci.card_def, Unit)
        and "Vehicle" in (getattr(ci.card_def, "traits", None) or ()))
    if not eligible:
        return state
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, from_discard=True,
                        eligible_ids=eligible, then_damage=1)
    return state


@card_ability("JTL", "121")
def _salvage_jtl_121():
    """JTL_121 — Salvage (Event, Supply, 0): "Play a Vehicle unit from your discard
    pile (paying its cost).  Then, deal 1 damage to it." """
    return EventAbility(effects=[CustomEffect(fn=_salvage_play_vehicle_from_discard)])


@card_ability("JTL", "125")
def _air_superiority_jtl_125():
    """JTL_125 — Air Superiority (Event, Tactic, 2): "If you control more space units
    than an opponent, deal 4 damage to a ground unit that opponent controls."

    The whole conditional lives in the new
    ``controller_more_space_units_than_target_controller`` board predicate rather than
    a ``ConditionalEffect`` — an ``EventAbility`` has no ``condition`` field, and a
    ConditionalEffect cannot carry a targeted sub-effect.  Reading the comparison
    per-candidate is also what ties "that opponent" to the same player in both halves
    of the sentence.  Losing the space race leaves no candidates, so the event fizzles
    with no prompt."""
    return EventAbility(effects=[
        DealDamage(4, TargetSpec(
            controller="enemy", kind="unit", arena="ground",
            predicates=("controller_more_space_units_than_target_controller",))),
    ])


def _lightspeed_assault_sacrifice(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly space unit's power, then defeat it — the damage it
    "deals" is its power at the moment it dies, so the snapshot must precede the
    defeat.  Stamps ``prior_target_id`` for the follow-up's "if you do" gate."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    event_ctx["lightspeed_power"] = max(0, compute_power(state, res[1]))
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_defeat_unit
    return _apply_defeat_unit(state, target_id)


def _lightspeed_assault_strike(state, source_ci, target_id, event_ctx):
    """Deal the recorded power to the chosen enemy space unit, then deal indirect
    damage equal to THAT unit's power to its controller.

    The enemy unit's power is snapshotted before the damage lands, so a ship that dies
    to the hit still bills its controller for its full power (and the indirect damage
    is pushed after the strike resolves — pop-then-deal, so any defeat trigger settles
    on a clean stack)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power, push_assign_indirect_damage
    enemy_power = max(0, compute_power(state, res[1]))
    amount = int(event_ctx.get("lightspeed_power", 0) or 0)
    if amount > 0:
        from swu.abilities.resolver import _apply_deal_damage
        state = _apply_deal_damage(state, target_id, amount,
                                   source_ci.card_def.display_name)
    if enemy_power > 0:
        push_assign_indirect_damage(state, source_ci, amount=enemy_power)
    return state


@card_ability("JTL", "127")
def _lightspeed_assault_jtl_127():
    """JTL_127 — Lightspeed Assault (Event, Gambit, 2): "Defeat a friendly space unit
    and deal damage equal to its power to an enemy space unit.  If you do, deal
    indirect damage equal to the enemy unit's power to its controller."

    Two dependent targeted effects sharing the ``resolve_effects`` ``event_ctx`` (the
    Nothing Left to Fear LAW_41 chain): the first snapshots the sacrifice's power and
    kills it, the second — gated by ``requires_prior_target`` so it cannot happen
    without the sacrifice — spends that power on an enemy ship and bills its
    controller the ship's own power as indirect damage."""
    return EventAbility(effects=[
        CustomEffect(fn=_lightspeed_assault_sacrifice,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       arena="space")),
        CustomEffect(fn=_lightspeed_assault_strike,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       arena="space",
                                       predicates=("requires_prior_target",))),
    ])


@card_ability("JTL", "147")
def _black_one_jtl_147():
    """JTL_147 — Black One, Straight At Them (Unit, Resistance/Vehicle/Fighter, 2/3):
    "While this unit is upgraded, it gets +1/+0." + "On Attack: If you control Poe
    Dameron (as a unit, upgrade, or leader), you may deal 1 damage to a unit."

    Both halves are pure reuse: a conditional SELF ``StatBonus`` gated by
    ``SOURCE_UPGRADED``, and an optional On Attack gated by
    ``CONTROLLER_CONTROLS_NAMED`` — which already scans base_zone, the arenas and every
    attached upgrade, so it covers all three of "as a unit, upgrade, or leader"
    (including an undeployed Poe) with no widening."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0)],
            condition=ConditionCheck(Condition.SOURCE_UPGRADED),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                     param="Poe Dameron"),
        ),
    ]


# ── jtl-set:04 — Direct damage & removal ──────────────────────────────────────

@card_ability("JTL", "148")
def _frisk_jtl_148():
    """JTL_148 — Frisk (Unit, New Republic/Pilot, 3/2, Piloting 2): "When played as
    an upgrade: You may defeat an upgrade that costs 2 or less."

    Piloting itself belongs to the keyword engine; the residual is the Boba Fett
    JTL_189 ``WhenPlayed(as_upgrade=True)`` flag (fires only on the Pilot-upgrade
    play path, never when Frisk is played as an ordinary unit) over the same
    optional ``DefeatUnit(kind="upgrade", cost_max=2)`` as Waylay's little sibling
    SHD_45 — the kind enumerates real (non-token) upgrades attached to a unit of
    either player."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade", cost_max=2))],
        optional=True,
    )


def _red_squadron_y_wing_indirect(state, source_ci, target_id, event_ctx):
    """Deal 3 indirect damage to the defending player.  In two-player the defending
    player IS the source controller's opponent, which is exactly who
    ``push_assign_indirect_damage`` addresses — so no attack context is needed."""
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=3)
    return state


@card_ability("JTL", "149")
def _red_squadron_y_wing_jtl_149():
    """JTL_149 — Red Squadron Y-Wing (Unit, Fighter/Rebel/Vehicle, 1/3): "On Attack:
    Deal 3 indirect damage to the defending player."

    A thin ``CustomEffect`` adapter onto the ``assign_indirect_damage`` decision
    (Dornean Gunship JTL_116)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_red_squadron_y_wing_indirect)],
    )


def _tactical_heavy_bomber_indirect(state, source_ci, target_id, event_ctx):
    """Indirect damage equal to the bomber's own effective power, with the "If a
    base is damaged this way, draw a card" rider settled at the decision's resolve
    point — the only place it is known whether the receiving player put the damage
    on their base or on one of their units."""
    from swu.engine.actions import compute_power, push_assign_indirect_damage
    amount = max(0, compute_power(state, source_ci, is_attacking=True))
    if amount > 0:
        push_assign_indirect_damage(state, source_ci, amount=amount,
                                    then_draw_if_base=True)
    return state


@card_ability("JTL", "152")
def _tactical_heavy_bomber_jtl_152():
    """JTL_152 — Tactical Heavy Bomber (Unit, Resistance/Transport/Vehicle, 3/5):
    "On Attack: Deal indirect damage equal to this unit's power to the defending
    player.  If a base is damaged this way, draw a card."

    The magnitude is the bomber's *effective* attacking power (``compute_power``, so
    an upgrade or a buff counts); the conditional draw is the new
    ``then_draw_if_base`` rider on ``push_assign_indirect_damage``."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_tactical_heavy_bomber_indirect)],
    )


@card_ability("JTL", "153")
def _rebellious_hammerhead_jtl_153():
    """JTL_153 — Rebellious Hammerhead (Unit, Capital Ship/Rebel/Vehicle, 5/7):
    "When Played: You may deal damage to a unit equal to the number of cards in your
    hand."

    Pure reuse: an optional ``WhenPlayed`` whose one effect is a
    ``DealDamageEqualTo`` on the new ``source_controller_hand`` count — the
    source-side mirror of the long-standing ``target_controller_hand``.  The
    Hammerhead has left the hand by the time the trigger resolves, so it never
    counts itself."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamageEqualTo(TargetSpec(controller="any", kind="unit"),
                                   count="source_controller_hand")],
        optional=True,
    )


def _trench_run_fn(state, source_ci, target_id, event_ctx):
    """Mill 2 from the opponent's deck, deal the cost DIFFERENCE to the chosen
    Fighter as unpreventable damage, then attack with it at +4/+0.

    DEVIATION (ordering): the card grants the attacker a temporary "On Attack"
    ability, which would resolve just after the attack is declared.  There is
    exactly one attack and nothing between the two steps can change the milled
    cards, so resolving the mill and the recoil BEFORE pushing the attack is
    outcome-equivalent — except that a Fighter killed by its own recoil never
    declares the attack (rather than declaring it and fizzling mid-combat), which
    reaches the same board state.  "The defending player" is the one opponent.

    The recoil goes through ``_apply_indirect_damage`` because the card prints it as
    *unpreventable* — that is the damage path which bypasses shields."""
    if target_id is None:
        return state
    if state.find_instance(target_id) is None:
        return state
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard, push_granted_attack
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    costs: list[int] = []
    for _ in range(2):
        if not opp.deck:
            break
        card = opp.deck.pop(0)
        card.zone = Zone.DISCARD
        card.face_down = False
        opp.discard.append(card)
        note_hand_or_deck_discard(state, card)
        costs.append(int(getattr(card.card_def, "cost", 0) or 0))
    if len(costs) == 2 and abs(costs[0] - costs[1]) > 0:
        from swu.abilities.resolver import _apply_indirect_damage
        state = _apply_indirect_damage(
            state, target_id, abs(costs[0] - costs[1]),
            source_name=source_ci.card_def.display_name,
            dealer_id=source_ci.owner_id)
    still = state.find_instance(target_id)
    if still is not None and still[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        push_granted_attack(state, source_ci, power_bonus=4, attacker_id=target_id)
    return state


@card_ability("JTL", "156")
def _trench_run_jtl_156():
    """JTL_156 — Trench Run (Event, Gambit, 1): "Attack with a Fighter unit.  For
    this attack, it gets +4/+0 and gains: 'On Attack: Discard 2 cards from the
    defending player's deck.  Deal unpreventable damage equal to the difference in
    the discarded cards' costs to this unit.'"

    One targeted ``CustomEffect`` picks the Fighter; the mill, the recoil and the
    ``push_granted_attack(attacker_id=…, power_bonus=4)`` all hang off that single
    choice (see ``_trench_run_fn`` for the one documented ordering deviation)."""
    return EventAbility(effects=[
        CustomEffect(fn=_trench_run_fn,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       traits=("Fighter",))),
    ])


@card_ability("JTL", "158")
def _crackshot_v_wing_jtl_158():
    """JTL_158 — Crackshot V-Wing (Unit, Fighter/Republic/Vehicle, 2/2): "When
    Played: If you control no other Fighter units, deal 1 damage to this unit."

    The whole condition is the new ``CONTROLLER_NO_OTHER_TRAIT_UNIT`` atom — the
    exact negation of ``CONTROLLER_HAS_OTHER_TRAIT_UNIT``, sharing its
    source-excluding scan (the V-Wing has already entered play when the trigger is
    collected, so "no OTHER Fighter" is what must be asked).  Failing the gate means
    the trigger is never collected, so there is no prompt and no no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(kind="unit", fixed=SELF))],
        condition=ConditionCheck(Condition.CONTROLLER_NO_OTHER_TRAIT_UNIT,
                                 param="Fighter"),
    )


def _droid_missile_platform_indirect(state, source_ci, target_id, event_ctx):
    """Deal 3 indirect damage to "a player" — the established reading (Dornean
    Gunship JTL_116) is the source controller's opponent, which is who
    ``push_assign_indirect_damage`` addresses."""
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=3)
    return state


@card_ability("JTL", "162")
def _droid_missile_platform_jtl_162():
    """JTL_162 — Droid Missile Platform (Unit, Droid/Separatist/Transport/Vehicle,
    4/2): "When Defeated: Deal 3 indirect damage to a player."

    Pure reuse — the WhenDefeated source resolves from the discard pile, and the
    indirect-damage decision only ever needs the source's controller."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_droid_missile_platform_indirect)],
    )


# ── jtl-set:05 — Direct damage & removal ──────────────────────────────────────

@card_ability("JTL", "168")
def _insurgent_saboteurs_jtl_168():
    """JTL_168 — Insurgent Saboteurs (Unit, Rebel/Trooper, 6/5, Saboteur): "On
    Attack: You may defeat an upgrade."

    Saboteur is the keyword engine's; the residual is one optional ``DefeatUnit``
    over ``kind="upgrade"`` (Waylay's sibling SHD_45 — the kind enumerates real,
    non-token upgrades attached to a unit of either player)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade"))],
        optional=True,
    )


def _war_juggernaut_bombard(state, source_ci, target_id, event_ctx):
    """"Deal 1 damage to each of any number of units" — the ``select_damage``
    decision with no real cap: "any number" is every unit currently in play, and
    ``FinishSelectDamage`` (always offered) is the "any number, including zero"."""
    total = sum(len(ps.ground_arena) + len(ps.space_arena) for ps in state.players)
    if total > 0:
        from swu.engine.actions import push_select_damage
        push_select_damage(state, source_ci, amount_each=1, max_targets=total)
    return state


@card_ability("JTL", "170")
def _war_juggernaut_jtl_170():
    """JTL_170 — War Juggernaut (Unit, Republic/Tank/Vehicle, 3/7): "This unit gets
    +1/+0 for each damaged unit." + "When Played: Deal 1 damage to each of any number
    of units."

    The buff is a SELF ``ConstantAbility`` on the new ``damaged_units_in_play``
    count — "each damaged unit" is unqualified, so it counts BOTH players' damaged
    units (including the Juggernaut itself once it has taken damage), which is also
    what makes its own bombardment feed it.  The bombardment is a thin
    ``CustomEffect`` adapter onto ``push_select_damage`` (IG-2000 JTL_140)."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0, count="damaged_units_in_play")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_war_juggernaut_bombard)],
        ),
    ]


def _twin_laser_turret_fire(state, source_ci, target_id, event_ctx):
    """"Deal 1 damage to each of up to 2 units in this arena."  Resolving from a
    ``GrantedAbility`` makes ``source_ci`` the HOST, so "this arena" is simply the
    host's own arena — handed to the decision as the new ``arena`` narrowing."""
    from swu.engine.state import Zone
    arena = "space" if source_ci.zone == Zone.SPACE_ARENA else "ground"
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=2, arena=arena)
    return state


@card_ability("JTL", "172")
def _twin_laser_turret_jtl_172():
    """JTL_172 — Twin Laser Turret (Upgrade, Modification/Weapon, 2): "Attach to a
    Vehicle unit.  Attached unit gains: 'On Attack: Deal 1 damage to each of up to 2
    units in this arena.'"

    A ``GrantedAbility`` wrapping the On Attack (it matches and resolves with the
    HOST as source); the attach restriction is parsed straight off the card text by
    ``_upgrade_target_spec``, so no TargetSpec is written here."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_twin_laser_turret_fire)],
    ))


def _fight_fire_pick_friendly(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly unit and its arena, arming the enemy half's
    ``same_arena_as_event`` + ``requires_prior_target`` gates (the Haymaker LAW_168
    shape).  Nothing is damaged yet — "If you do" means BOTH units must be chosen
    before any damage is dealt."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    event_ctx["prior_target_id"] = target_id
    event_ctx["same_arena"] = ("space" if res[1].zone == Zone.SPACE_ARENA
                               else "ground")
    return state


def _fight_fire_strike_both(state, source_ci, target_id, event_ctx):
    """Deal 3 to the chosen enemy unit AND to the friendly unit recorded by the
    first half.  Both hits are applied here so neither lands while the other choice
    is still open (the Unlimited Power TWI_156 record-then-apply shape)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    for tid in (event_ctx.get("prior_target_id"), target_id):
        if tid:
            state = _apply_deal_damage(state, tid, 3, source_name=name,
                                       dealer_id=source_ci.owner_id)
    return state


@card_ability("JTL", "173")
def _fight_fire_with_fire_jtl_173():
    """JTL_173 — Fight Fire With Fire (Event, Gambit, 1): "Choose a friendly unit and
    an enemy unit in the same arena.  If you do, deal 3 damage to each of them."

    Two dependent targeted ``CustomEffect``s sharing the ``resolve_effects``
    ``event_ctx``: the first records the friendly pick plus its arena, the second is
    gated by ``requires_prior_target`` + ``same_arena_as_event`` so it can only pick
    an enemy beside it — and with no such enemy the event fizzles with no damage at
    all, which is exactly what "If you do" buys."""
    return EventAbility(effects=[
        CustomEffect(fn=_fight_fire_pick_friendly,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_fight_fire_strike_both,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("requires_prior_target",
                                                   "same_arena_as_event"))),
    ])


def _count_on_attack_abilities(state, ci) -> int:
    """How many "On Attack" abilities ``ci`` has — its own registered ones plus any
    an attached upgrade grants it (Dorsal Turret JTL_120 grants a combat trigger,
    Twin Laser Turret JTL_172 an On Attack).  Side-gated leader specs for the wrong
    side don't count."""
    from swu.abilities.registry import (
        get_abilities, TriggerAbility, GrantedAbility, OnAttack)
    from swu.engine.state import ability_suppressed

    def _own(card_def, deployed) -> int:
        sc = getattr(card_def, "set_code", None) or ""
        cn = getattr(card_def, "card_number", None) or ""
        if not sc or not cn:
            return 0
        n = 0
        for spec in get_abilities(sc, cn):
            inner = spec.ability if isinstance(spec, GrantedAbility) else spec
            if not isinstance(inner, TriggerAbility):
                continue
            if not isinstance(inner.trigger, OnAttack):
                continue
            if getattr(spec, "deployed_only", False) and not deployed:
                continue
            if getattr(spec, "undeployed_only", False) and deployed:
                continue
            n += 1
        return n

    if ability_suppressed(state, ci):
        return 0
    total = _own(ci.card_def, getattr(ci, "deployed", False))
    for up in getattr(ci, "attached_upgrades", None) or ():
        total += _own(up.card_def, True)
    return total


def _hotshot_maneuver_fn(state, source_ci, target_id, event_ctx):
    """Count the chosen unit's "On Attack" abilities, deal 2 to that many DIFFERENT
    enemy units, then attack with it.

    The damage runs through ``push_select_damage(enemy_only=True)`` — "a different
    enemy unit" per ability is precisely its distinct-target loop — carrying the new
    ``then_attack_with`` rider so the "Then, attack" happens AFTER the damage
    settles (pushing both up front would resolve them LIFO, i.e. backwards).  A unit
    with no On Attack ability (or a board with no enemy units) skips straight to the
    attack.  ``FinishSelectDamage`` stays on offer, so the damage is "up to" rather
    than strictly mandatory (the established ``select_damage`` reading)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import push_select_damage, push_granted_attack
    n = _count_on_attack_abilities(state, res[1])
    before = len(state.pending_decisions)
    if n > 0:
        push_select_damage(state, source_ci, amount_each=2, max_targets=n,
                           enemy_only=True, then_attack_with=target_id)
    if len(state.pending_decisions) == before:
        push_granted_attack(state, source_ci, attacker_id=target_id)
    return state


@card_ability("JTL", "174")
def _hotshot_maneuver_jtl_174():
    """JTL_174 — Hotshot Maneuver (Event, Tactic, 1): "Choose a friendly unit.  For
    each of its 'On Attack' abilities, deal 2 damage to a different enemy unit.
    Then, attack with the chosen unit." """
    return EventAbility(effects=[
        CustomEffect(fn=_hotshot_maneuver_fn,
                     target=TargetSpec(controller="friendly", kind="unit")),
    ])


def _system_shock_fn(state, source_ci, target_id, event_ctx):
    """Defeat the chosen upgrade, then deal 1 to the unit it was attached to.  The
    host is resolved BEFORE the upgrade is detached (afterwards there is no link)."""
    if target_id is None:
        return state
    from swu.engine.actions import _find_upgrade_host, _defeat_attached_upgrade
    host = _find_upgrade_host(state, target_id)
    res = state.find_instance(target_id)
    if host is None or res is None:
        return state
    host_id = host.instance_id
    _defeat_attached_upgrade(state, res[1])
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, host_id, 1,
                              source_name=source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id)


@card_ability("JTL", "175")
def _system_shock_jtl_175():
    """JTL_175 — System Shock (Event, Tactic, 1): "Defeat a non-leader upgrade
    attached to a unit.  If you do, deal 1 damage to that unit."

    ``kind="upgrade"`` already enumerates only real (non-token) upgrades attached to
    a unit, so "attached to a unit" needs no predicate; ``non_leader`` excludes a
    leader deployed as a Pilot upgrade (``_is_leader_unit`` matches a Leader
    card_def).  "If you do" is intrinsic — with no legal upgrade the event fizzles
    and no damage is dealt."""
    return EventAbility(effects=[
        CustomEffect(fn=_system_shock_fn,
                     target=TargetSpec(controller="any", kind="upgrade",
                                       predicates=("non_leader",))),
    ])


def _piercing_shot_fn(state, source_ci, target_id, event_ctx):
    """Strip every Shield token from the chosen unit, then deal it 3.  The shields
    go first, so ordinary (shield-eatable) damage lands in full — which is the whole
    point of the card and why the 3 is a plain ``_apply_deal_damage``."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.tokens import defeat_shield
    while defeat_shield(state, res[1]):
        pass
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 3,
                              source_name=source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id)


@card_ability("JTL", "180")
def _piercing_shot_jtl_180():
    """JTL_180 — Piercing Shot (Event, Tactic, 3): "Defeat all Shield tokens on a
    unit.  Deal 3 damage to that unit."

    One targeted ``CustomEffect`` — both clauses hang off the same choice, and the
    order (shields first) is what the card is for."""
    return EventAbility(effects=[
        CustomEffect(fn=_piercing_shot_fn,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


# ── jtl-set:06 — Direct damage & removal ──────────────────────────────────────

@card_ability("JTL", "198")
def _fireball_jtl_198():
    """JTL_198 — Fireball (Unit, Fighter/Resistance/Vehicle, 3/3, Ambush): "When the
    regroup phase starts: Deal 1 damage to this unit."

    Ambush is the keyword engine's; the residual is the Contracted Hunter JTL_216
    ``PhaseStartTrigger("regroup")`` seam, here burning itself down one point a round
    rather than defeating itself outright."""
    return TriggerAbility(
        trigger=PhaseStartTrigger(phase="regroup"),
        effects=[DealDamage(1, TargetSpec(kind="unit", fixed=SELF))],
    )


def _guerilla_soldier_indirect(state, source_ci, target_id, event_ctx):
    """3 indirect damage carrying the "If a base is damaged this way, ready this
    unit" rider — settled at the decision's resolve point, where it is known whether
    the receiving player took it on their base or on a unit."""
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=3,
                                then_ready_source_if_base=True)
    return state


@card_ability("JTL", "218")
def _guerilla_soldier_jtl_218():
    """JTL_218 — Guerilla Soldier (Unit, Fringe/Trooper/Twi'lek, 2/3): "When Played:
    Deal 3 indirect damage to a player.  If a base is damaged this way, ready this
    unit."

    A unit enters play exhausted, so the rider is a real tempo swing: an opponent who
    protects their units by eating the 3 on their base hands the Soldier an immediate
    attack."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_guerilla_soldier_indirect)],
    )


def _rafa_martez_fn(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen friendly unit AND ready a resource.

    Both clauses live in ONE targeted ``CustomEffect`` so the pair resolves off a
    single prompt (the Kylo Ren SHD_141 shape).  Readying a resource is auto-picked
    — resources are fungible and are not targetable cards (the K-2SO SOR_145
    convention); with none exhausted that half is simply a no-op."""
    if target_id is not None:
        from swu.abilities.resolver import _apply_deal_damage
        state = _apply_deal_damage(state, target_id, 1,
                                   source_name=source_ci.card_def.display_name,
                                   dealer_id=source_ci.owner_id)
    ps = state.player_by_id(source_ci.owner_id)
    for r in ps.resources:
        if r.exhausted:
            r.exhausted = False
            break
    return state


@card_ability("JTL", "219")
def _rafa_martez_jtl_219():
    """JTL_219 — Rafa Martez (Unit, Underworld, 3/3): "When Played/On Attack: Deal 1
    damage to a friendly unit and ready a resource."

    The two trigger sides are two registrations over the same effect (the R2-D2
    SOR_236 "When Played/On Attack" shape).  Rafa herself is always a legal friendly
    target, so the effect never fizzles for want of one."""
    effects = [CustomEffect(fn=_rafa_martez_fn,
                            target=TargetSpec(controller="friendly", kind="unit"))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects)),
        TriggerAbility(trigger=OnAttack(), effects=list(effects)),
    ]


def _kimogila_indirect(state, source_ci, target_id, event_ctx):
    """3 indirect damage carrying the "Exhaust each unit damaged this way" rider.
    The decision assigns the whole amount to ONE target, so "each" is at most one
    unit — and a unit the damage defeated is no longer there to exhaust."""
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=3,
                                then_exhaust_damaged=True)
    return state


@card_ability("JTL", "222")
def _kimogila_heavy_fighter_jtl_222():
    """JTL_222 — Kimogila Heavy Fighter (Unit, Fighter/Underworld/Vehicle, 3/4):
    "When Played: Deal 3 indirect damage to a player.  Exhaust each unit damaged this
    way."

    The mirror of Guerilla Soldier JTL_218: there the opponent is punished for
    guarding their units, here for guarding their base."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_kimogila_indirect)],
    )


def _radiant_vii_indirect(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=5)
    return state


@card_ability("JTL", "226")
def _radiant_vii_jtl_226():
    """JTL_226 — Radiant VII (Unit, Capital Ship/Republic/Vehicle, 5/6): "Each enemy
    non-leader unit gets −1/−0 for each damage on it." + "When Played: Deal 5
    indirect damage to a player."

    The aura is the first StatBonus whose magnitude scales off the BUFFED unit rather
    than the source — the new ``target_damage`` count, threaded through
    ``_stat_bonus_amount``'s optional ``target_ci``.  It pairs with its own When
    Played: 5 indirect damage taken on units immediately blunts them."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("non_leader",)),
            effects=[StatBonus(power=-1, hp=0, count="target_damage")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_radiant_vii_indirect)],
        ),
    ]


def _superheavy_ion_cannon_fn(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen ready enemy unit, then bill its controller indirect damage
    equal to that unit's power.  The power is read BEFORE the exhaust (exhausting
    does not change it, but the ordering keeps the read honest against any future
    exhaust-sensitive buff), and the "If you do" is intrinsic: with no ready enemy
    non-leader unit there is no candidate, so nothing happens at all."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power, push_assign_indirect_damage
    amount = max(0, compute_power(state, res[1]))
    res[1].exhausted = True
    if amount > 0:
        push_assign_indirect_damage(state, source_ci, amount=amount)
    return state


@card_ability("JTL", "227")
def _superheavy_ion_cannon_jtl_227():
    """JTL_227 — Superheavy Ion Cannon (Upgrade, Modification/Weapon, 2): "Attach to
    a Capital Ship or Transport unit.  Attached unit gains: 'On Attack: You may
    exhaust a non-leader unit the defending player controls.  If you do, deal
    indirect damage equal to its power to that player.'"

    A ``GrantedAbility`` wrapping the optional On Attack (it resolves with the HOST
    as source, so the indirect damage is billed to the host controller's opponent —
    who in two-player IS the defending player).  The target is narrowed to READY
    units so the "you may" is never offered as a no-op."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_superheavy_ion_cannon_fn,
                              target=TargetSpec(controller="enemy", kind="unit",
                                                predicates=("non_leader", "ready")))],
        optional=True,
    ))


def _torpedo_barrage_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_assign_indirect_damage
    push_assign_indirect_damage(state, source_ci, amount=5)
    return state


@card_ability("JTL", "234")
def _torpedo_barrage_jtl_234():
    """JTL_234 — Torpedo Barrage (Event, Tactic, 3): "Deal 5 indirect damage to a
    player."

    The plainest possible use of the ``assign_indirect_damage`` decision — the
    receiving player (the one opponent) assigns all 5 among their base and units,
    bypassing shields."""
    return EventAbility(effects=[CustomEffect(fn=_torpedo_barrage_fn)])


# ── jtl-set:07 — Direct damage & removal ──────────────────────────────────────

@card_ability("JTL", "239")
def _tie_dagger_vanguard_jtl_239():
    """JTL_239 — TIE Dagger Vanguard (Unit, Fighter/First Order/Sith/Vehicle, 2/2):
    "When Played: You may deal 2 damage to a damaged unit."

    Pure reuse: an optional targeted ``DealDamage`` narrowed by the ``damaged``
    predicate.  With no damaged unit anywhere there is no legal target, so the
    optional trigger resolves as a no-op without prompting."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          predicates=("damaged",)))],
        optional=True,
    )


@card_ability("JTL", "248")
def _dilapidated_ski_speeder_jtl_248():
    """JTL_248 — Dilapidated Ski Speeder (Unit, Resistance/Speeder/Vehicle, 3/7):
    "When Played: Deal 3 damage to this unit."

    A mandatory self-hit — the drawback that pays for a 3-cost 3/7.  ``fixed=SELF``
    needs no prompt, and the damage runs through the ordinary chokepoint, so a
    Shield on the Speeder would eat it."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(3, TargetSpec(kind="unit", fixed=SELF))],
    )


# ── jtl-set:08 — Card advantage & disruption ──────────────────────────────────

def _discard_hand_card(state, ps, ci):
    """Send one held card to its owner's discard pile, feeding both discard
    ledgers (the ``DiscardFromHand`` resolver arm verbatim, for one chosen card)."""
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard, record_hand_discard
    ps.hand.remove(ci)
    ci.zone = Zone.DISCARD
    ps.discard.append(ci)
    note_hand_or_deck_discard(state, ci)
    record_hand_discard(state, ps.player_id)


def _admiral_trench_discard_draw(state, source_ci, target_id, event_ctx):
    """Discard a hand card costing 3 or more, then draw.

    The card to pitch is auto-picked (the first qualifying one — the K-2SO SOR_145
    first-card-discard convention); the collection gate guarantees one exists, so
    the "If you do" always fires and the Exhaust is never wasted."""
    from swu.engine.actions import _draw_cards
    ps = state.player_by_id(source_ci.owner_id)
    victim = next((c for c in ps.hand
                   if int(getattr(c.card_def, "cost", None) or 0) >= 3), None)
    if victim is None:
        return state
    _discard_hand_card(state, ps, victim)
    _draw_cards(state, ps, 1)
    return state


def _admiral_trench_reveal(state, source_ci, target_id, event_ctx):
    """Reveal the top 4; an opponent discards 2; draw 1 of the rest, discard the
    other — the ``reveal_cull_draw`` cross-decider decision."""
    from swu.engine.actions import push_reveal_cull_draw
    push_reveal_cull_draw(state, source_ci, count=4, cull=2)
    return state


@card_ability("JTL", "14")
def _admiral_trench_jtl_14():
    """JTL_14 — Admiral Trench (Leader, Official/Separatist, 4/5):
      undeployed "Action [Exhaust]: Discard a card that costs 3 or more from your
      hand.  If you do, draw a card."
      deployed  "When Deployed: Reveal the top 4 cards of your deck.  An opponent
      discards 2 of them.  Draw 1 of the remaining cards and discard the other."

    The Action binds cost to payoff inside ONE ``CustomEffect`` (the Bright Hope
    SOR_99 "If you do" shape) and is gated by the new
    ``CONTROLLER_HAS_HAND_CARD_COST_MIN`` so it is never offered as a no-op.  The
    When Deployed is the new ``reveal_cull_draw`` decision kind — a two-stage
    decider shift where the OPPONENT culls first and the controller then keeps one
    survivor.  (Trench's third line is his Epic Action deploy, a discounted
    conditional deploy; deploying never routes through the ability registry, so the
    leader deploys at its printed cost as every other leader does.)"""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_admiral_trench_discard_draw)],
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_HAND_CARD_COST_MIN, param=3),
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_admiral_trench_reveal)],
            deployed_only=True,
        ),
    ]


@card_ability("JTL", "21")
def _colossus_jtl_21():
    """JTL_21 — Colossus (Base, 35 HP): "Draw 1 less card in your starting hand."

    The biggest base in the set pays for its HP with a card.  A passive
    ``StartingHandModifier`` marker, read at the three setup seams that already
    knew the number 6 (the opening draw, a mulligan redraw, and — via
    ``no_mulligan``, which Colossus does not set — the mulligan's legality)."""
    return StartingHandModifier(amount=-1)


def _nabat_village_bottom(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_bottom_from_hand
    push_bottom_from_hand(state, source_ci, count=3)
    return state


@card_ability("JTL", "28")
def _nabat_village_jtl_28():
    """JTL_28 — Nabat Village (Base, 27 HP): "Draw 3 more cards in your starting
    hand.  You can't take a mulligan." + "When the first action phase starts: Put 3
    cards from your hand on the bottom of your deck in any order."

    The mirror of Colossus: a small base that buys a deep opening look, paid for by
    losing the mulligan AND handing 3 cards back once the game starts.  The static
    half is the same ``StartingHandModifier`` marker (``no_mulligan`` drops
    ``TakeMultiligan`` from that player's setup actions); the delayed half is
    ``PhaseStartTrigger("action", first_only=True)`` — the action-phase sibling of
    the long-standing regroup fire site — onto the existing ``bottom_from_hand``
    decision (Private Manufacturing TWI_257)."""
    return [
        StartingHandModifier(amount=3, no_mulligan=True),
        TriggerAbility(
            trigger=PhaseStartTrigger(phase="action", first_only=True),
            effects=[CustomEffect(fn=_nabat_village_bottom)],
        ),
    ]


def _annihilator_name_purge(state, source_ci, target_id, event_ctx):
    """Defeat the chosen enemy unit, then strip every card sharing its NAME from
    that unit's controller's deck and hand.

    Cost and payoff live in one ``CustomEffect`` ("If you do" — Bright Hope SOR_99):
    with no enemy unit there is no target and nothing happens at all.  The name is
    read BEFORE the defeat (the JTL_175 ordering rule — the instance is gone from
    the arena afterwards), and the deck is reshuffled with the game's seeded RNG so
    the purge leaks no ordering information."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.actions import note_hand_or_deck_discard
    from swu.engine.state import Zone
    res = state.find_instance(target_id)
    if res is None:
        return state
    victim_ps, victim = res
    name = getattr(victim.card_def, "name", None)
    state = _apply_defeat_unit(state, target_id)
    if not name:
        return state
    ps = state.player_by_id(victim_ps.player_id)
    hits = [c for c in ps.hand if getattr(c.card_def, "name", None) == name]
    for ci in hits:
        _discard_hand_card(state, ps, ci)
    deck_hits = [c for c in ps.deck if getattr(c.card_def, "name", None) == name]
    for ci in deck_hits:
        ps.deck.remove(ci)
        ci.zone = Zone.DISCARD
        ps.discard.append(ci)
        note_hand_or_deck_discard(state, ci)
    if deck_hits:
        rng = state.make_rng()
        rng.shuffle(ps.deck)
        state.rng_state = rng.getstate()
    return state


@card_ability("JTL", "41")
def _annihilator_jtl_41():
    """JTL_41 — Annihilator (Unit, Capital Ship/Imperial/Vehicle, 12/12): "When
    Played/When Defeated: You may defeat an enemy unit.  If you do, search its
    controller's deck and hand for each card with that unit's name and discard
    them.  (They shuffle their deck.)"

    The set's 11-cost finisher, and the only card that removes a NAME rather than a
    card.  Two registrations over one targeted ``CustomEffect`` (the R2-D2 SOR_236
    "When Played/When Defeated" shape), so it fires on the way in and again on the
    way out."""
    effects = [CustomEffect(fn=_annihilator_name_purge,
                            target=TargetSpec(controller="enemy", kind="unit"))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects), optional=True),
        TriggerAbility(trigger=WhenDefeated(), effects=list(effects), optional=True),
    ]


def _cassian_andor_mill(state, source_ci, target_id, event_ctx):
    """Discard the top card of the DEFENDING player's deck; if it costs 3 or less,
    the attacker's controller draws.

    Resolving from a ``GrantedAbility`` makes ``source_ci`` the HOST, so the
    defending player is simply the host controller's opponent (two-player)."""
    from swu.engine.actions import note_hand_or_deck_discard, _draw_cards
    from swu.engine.state import Zone
    idx = state.player_index(source_ci.owner_id)
    mine = state.players[idx]
    theirs = state.players[1 - idx]
    if not theirs.deck:
        return state
    ci = theirs.deck.pop(0)
    ci.zone = Zone.DISCARD
    theirs.discard.append(ci)
    note_hand_or_deck_discard(state, ci)
    if int(getattr(ci.card_def, "cost", None) or 0) <= 3:
        _draw_cards(state, mine, 1)
    return state


@card_ability("JTL", "48")
def _cassian_andor_jtl_48():
    """JTL_48 — Cassian Andor (Unit, Pilot/Rebel, 3/4, Piloting 2): "Attached unit
    gains: 'On Attack: Discard a card from the defending player's deck.  If that
    card costs 3 or less, draw a card.'"

    Piloting is the keyword engine's; the residual is the ``GrantedAbility``
    wrapping an On Attack (Armed to the Teeth SHD_175).  As a UNIT in an arena the
    grant is never collected (the arena trigger scan skips ``GrantedAbility``), so
    Cassian only mills while he is riding a Vehicle — exactly as printed."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_cassian_andor_mill)],
    ))


@card_ability("JTL", "63")
def _landing_shuttle_jtl_63():
    """JTL_63 — Landing Shuttle (Unit, Imperial/Transport/Vehicle, 2/4): "When
    Defeated: You may draw a card."

    A bare optional ``DrawCards(1)``."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(1)],
        optional=True,
    )


def _invisible_hand_search(state, source_ci, target_id, event_ctx):
    """Search the top 8 for a Droid unit, draw it, and — if it costs 2 or less —
    play it for free (the new ``then_play_free_cost_max`` deck_search rider, which
    whitelists the just-drawn card into a free ``play_from_hand``)."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search

    def eligible(card_def) -> bool:
        return (isinstance(card_def, Unit)
                and "Droid" in (getattr(card_def, "traits", None) or ()))

    push_deck_search(state, source_ci, count=1, eligible=eligible, up_to=True,
                     window=8, then_play_free_cost_max=2)
    return state


@card_ability("JTL", "89")
def _the_invisible_hand_jtl_89():
    """JTL_89 — The Invisible Hand (Unit, Capital Ship/Separatist/Vehicle, 6/6):
    "When Played/When this unit completes an attack (and survives): You may search
    the top 8 cards of your deck for a Droid unit, reveal it, and draw it.  If it
    costs 2 or less, you may play it for free.  (Put the other cards on the bottom
    of your deck in a random order.)"

    Two registrations over one ``CustomEffect`` — ``WhenPlayed`` and the existing
    ``WhenAttackEnds`` trigger, whose "and survives" is intrinsic (it only fires for
    a source still in play).  The search is ``up_to=True``, which is the outer "you
    may"; the inner one collapses to mandatory (a free ≤2-cost Droid is never a
    downside)."""
    effects = [CustomEffect(fn=_invisible_hand_search)]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects)),
        TriggerAbility(trigger=WhenAttackEnds(), effects=list(effects)),
    ]


# ── jtl-set:09 — Card advantage & disruption ──────────────────────────────────

def _snap_wexley_search(state, source_ci, target_id, event_ctx):
    """Search the top 5 for a Resistance CARD (any type), reveal it, and draw it."""
    from swu.engine.actions import push_deck_search

    def eligible(card_def) -> bool:
        return "Resistance" in (getattr(card_def, "traits", None) or ())

    push_deck_search(state, source_ci, count=1, eligible=eligible, up_to=False,
                     window=5)
    return state


@card_ability("JTL", "98")
def _snap_wexley_jtl_98():
    """JTL_98 — Snap Wexley (Unit, Pilot/Resistance, 2/5, Piloting 2):
      "When played as a unit/On Attack: The next Resistance card you play this
       phase costs 1 resource less."
      "When played as an upgrade: Search the top 5 cards of your deck for a
       Resistance card, reveal it, and draw it."

    The two halves key off the two play paths: ``WhenPlayed(as_unit=True)`` +
    ``OnAttack`` for the discount (a ``NextPlayDiscount`` with ``units_only=False``,
    since the card says "card"), ``WhenPlayed(as_upgrade=True)`` for the dig.  The
    search is ``up_to=False`` — "search for a Resistance card" is mandatory if the
    window holds one."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(as_unit=True),
            effects=[NextPlayDiscount(trait="Resistance", amount=1,
                                      units_only=False)],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[NextPlayDiscount(trait="Resistance", amount=1,
                                      units_only=False)],
        ),
        TriggerAbility(
            trigger=WhenPlayed(as_upgrade=True),
            effects=[CustomEffect(fn=_snap_wexley_search)],
        ),
    ]


def _eject_detach_to_ground(state, source_ci, target_id, event_ctx):
    """Detach the chosen Pilot upgrade and stand it up in the ground arena as an
    exhausted unit under its host's controller.

    Deliberately NOT a "play": the card moves the upgrade, so no cost is paid, no
    ``CardPlayed`` fires and the unit's own When Played does not trigger.  Control
    follows the arena it lands in — the host's controller, which is also who was
    getting the Pilot's benefit."""
    if target_id is None:
        return state
    from swu.engine.actions import _find_upgrade_host
    from swu.engine.state import Zone
    host = _find_upgrade_host(state, target_id)
    if host is None:
        return state
    upgrade = next((u for u in host.attached_upgrades
                    if u.instance_id == target_id), None)
    if upgrade is None:
        return state
    located = state.find_instance(host.instance_id)
    if located is None:
        return state
    holder, _ = located
    host.attached_upgrades = [u for u in host.attached_upgrades
                              if u.instance_id != target_id]
    upgrade.zone = Zone.GROUND_ARENA
    upgrade.exhausted = True
    upgrade.damage = 0
    state.player_by_id(holder.player_id).ground_arena.append(upgrade)
    return state


@card_ability("JTL", "126")
def _eject_jtl_126():
    """JTL_126 — Eject (Event, Gambit, 2): "Detach a Pilot upgrade, move it to the
    ground arena as a unit, and exhaust it.  Draw a card."

    The inverse of a Piloting play.  The targeted move comes FIRST so the resolver
    prompts exactly once (the Mandalorian SHD_18 ordering rule) and the draw lands
    afterwards; the new ``kind="unit_upgrade"`` keeps the offer to Pilot upgrades
    that actually have unit stats to stand up with — a leader riding as a Pilot, or
    a printed (non-unit) Pilot upgrade, is not offered."""
    return EventAbility(effects=[
        CustomEffect(fn=_eject_detach_to_ground,
                     target=TargetSpec(controller="any", kind="unit_upgrade",
                                       traits=("Pilot",))),
        DrawCards(1),
    ])


@card_ability("JTL", "134")
def _general_hux_jtl_134():
    """JTL_134 — General Hux (Unit, First Order/Official, 1/4): "Each other friendly
    First Order unit gains Raid 1." + "Action [Exhaust]: If you played a First Order
    card this phase, draw a card."

    A plain keyword-anthem ``ConstantAbility`` (read passively by the keyword layer)
    plus an ``ActivatedAbility`` gated by ``CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE``
    — "if you played a First Order CARD" is any card type, which is exactly what
    that ledger records (Captain Phasma JTL_10)."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("First Order",), predicates=("not_self",)),
            effects=[KeywordGrant("Raid", 1)],
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DrawCards(1)],
            condition=ConditionCheck(
                Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE,
                param="First Order"),
        ),
    ]


def _stay_on_target_fn(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        attacker_trait="Vehicle", draw_if_base_damaged=True)
    return state


@card_ability("JTL", "177")
def _stay_on_target_jtl_177():
    """JTL_177 — Stay on Target (Event, Tactic, 2): "Attack with a Vehicle unit.
    For this attack, it gets +2/+0 and gains: 'When this unit deals damage to a
    base: Draw a card.'"

    ``push_granted_attack`` with the trait filter and the +2/+0, plus the new
    ``draw_if_base_damaged`` rider: instead of granting a temporary trigger, the
    attack site compares each base's damage against a pre-combat snapshot and draws
    if the attack put anything on one — so an Overwhelm spill counts as printed,
    not only a direct base attack."""
    return EventAbility(effects=[CustomEffect(fn=_stay_on_target_fn)])


@card_ability("JTL", "186")
def _mist_hunter_jtl_186():
    """JTL_186 — Mist Hunter (Unit, Transport/Underworld/Vehicle, 3/4): "On Attack:
    If you played a Bounty Hunter or Pilot card this phase, you may draw a card."

    The card's clause is a DISJUNCTION, which is what the new ``Condition.ANY_OF``
    composite is for — registering one ability per trait would draw twice in a turn
    that played both."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(1)],
        optional=True,
        condition=ConditionCheck(Condition.ANY_OF, param=(
            ConditionCheck(Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE,
                           param="Bounty Hunter"),
            ConditionCheck(Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE,
                           param="Pilot"),
        )),
    )


@card_ability("JTL", "191")
def _invincible_jtl_191():
    """JTL_191 — Invincible (Unit, Capital Ship/Separatist/Vehicle, 6/6): "If you
    control a unique Separatist card, this unit costs 1 resource less to play." +
    "When you deploy a leader: You may return a non-leader unit that costs 3 or
    less to its owner's hand."

    A ``CostReduction`` gated by the new ``CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY``
    (the uniqueness-narrowed sibling of ``CONTROLLER_HAS_TRAIT_CARD_IN_PLAY`` — and,
    like it, satisfied by an undeployed unique Separatist leader in the base zone),
    plus the existing ``WhenYouDeployLeader`` observer (Shadow Collective Camp
    TWI_25) onto an optional ``ReturnToHand``."""
    return [
        CostReduction(1, condition=ConditionCheck(
            Condition.CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY,
            param="Separatist")),
        TriggerAbility(
            trigger=WhenYouDeployLeader(),
            effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                             predicates=("non_leader",),
                                             cost_max=3))],
            optional=True,
        ),
    ]


def _heartless_tactics_fn(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen unit and give it −2/−0 for this phase; if that leaves a
    non-leader at 0 power, return it to its owner's hand.

    All three clauses live in ONE targeted ``CustomEffect`` so they land on the SAME
    unit off a single prompt (the Kylo Ren SHD_141 shape).  The closing "you may"
    collapses to mandatory — the caster chose the target, and a 0-power unit is
    exactly the one they wanted gone."""
    if target_id is None:
        return state
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import (
        _apply_return_to_hand, _is_leader_unit, _make_modifier)
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    ci.exhausted = True
    from swu.abilities.registry import Duration
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=-2, hp=0, duration=Duration.THIS_PHASE))
    if compute_power(state, ci) <= 0 and not _is_leader_unit(ci):
        state = _apply_return_to_hand(state, target_id)
    return state


@card_ability("JTL", "194")
def _heartless_tactics_jtl_194():
    """JTL_194 — Heartless Tactics (Event, Tactic, 2): "Exhaust a unit and give it
    –2/–0 for this phase.  Then, if it has 0 power and isn't a leader, you may
    return it to its owner's hand."

    A cheap answer to the set's swarm of 1- and 2-power Pilots: the debuff and the
    bounce are one ``CustomEffect`` on one chosen unit, and the power is re-read
    through ``compute_power`` AFTER the modifier lands (so an Experience token or a
    Raid bonus keeps a unit on the board)."""
    return EventAbility(effects=[
        CustomEffect(fn=_heartless_tactics_fn,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


# ── Group jtl-set:10 — Card advantage & disruption ───────────────────────────
#
# Six cards, all built from existing primitives plus three small additive
# widenings (see each docstring): ``push_bottom_from_discard(exclude_ids=)``,
# ``push_name_and_discard(card_type=)`` and ``TargetSpec.cost_max_if_exhausted``,
# alongside one new phase-scoped permission ledger
# (``game_memory.foreign_free_discard_play_this_phase``) for JTL_221.


# Every printing of Anakin Skywalker "I'll Try Spinning".  JTLP_16 is the
# prerelease face, which the reprint sweep cannot alias onto JTL_197 (its DB
# ``epic_action`` is TRUNCATED — the whole "When attached unit completes an
# attack (and survives):" clause is missing), so it is registered separately in
# the promo module and shares this finder rather than a copy of it.
ANAKIN_PILOT_KEYS = (("JTL", "197"), ("JTLP", "16"))


def _anakin_jtl_197_return_pilot(state, source_ci, target_id, event_ctx):
    """Return the Anakin Skywalker Pilot upgrade riding ``source_ci`` to its
    owner's hand.

    A ``GrantedAbility`` resolves from the HOST (``source_ci`` is the Vehicle that
    just attacked), so "this upgrade" has to be located among the host's
    ``attached_upgrades`` by registry coordinates — the only card that can have
    granted this trigger to this host is Anakin himself, in one of his printings
    (:data:`ANAKIN_PILOT_KEYS`; he is unique, so at most one can be riding).
    ``_apply_return_to_hand`` already knows how to detach an attached upgrade and
    route it to its owner's hand as a clean card."""
    from swu.abilities.resolver import _apply_return_to_hand
    for upg in list(source_ci.attached_upgrades):
        cd = getattr(upg, "card_def", None)
        if (getattr(cd, "set_code", None),
                getattr(cd, "card_number", None)) in ANAKIN_PILOT_KEYS:
            return _apply_return_to_hand(state, upg.instance_id)
    return state


@card_ability("JTL", "197")
def _anakin_skywalker_jtl_197():
    """JTL_197 — Anakin Skywalker, "I'll Try Spinning" (Unit, Force/Fringe/Pilot,
    2/3; Piloting [2 resources Cunning Heroism]):

        Piloting [2 resources Cunning Heroism]
        When attached unit completes an attack (and survives): You may return this
        upgrade to its owner's hand.

    Piloting itself is the keyword layer (``PilotPlay``).  The residual is one
    ``GrantedAbility`` wrapping ``WhenAttackEnds`` — the trigger whose firing site
    only marks an attacker that is still in play once defeats have processed, so
    the printed "(and survives)" is intrinsic (Vermillion LAW_215).  Registered as
    a granted ability because a non-leader unit riding as a Pilot upgrade never has
    its OWN triggers collected: the arena scan walks units, and the upgrade scan
    only collects ``GrantedAbility`` (Dengar JTL_139, Bossk JTL_187).  The "you
    may" is the ordinary ``optional`` prompt — recycling Anakin for a fresh
    Piloting play is a real choice against leaving the +2/+3 on the Vehicle."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_anakin_jtl_197_return_pilot)],
        optional=True,
    ))


def _commence_patrol_fn(state, source_ci, target_id, event_ctx):
    """Bottom one card from a discard pile; each card actually bottomed makes an
    X-Wing token.

    Pure reuse of ``push_bottom_from_discard``, whose ``then_create_token`` payoff
    is settled at the finish — so "If you do" is honoured for free (bottoming
    nothing creates nothing).  ``exclude_ids`` carries the printed "ANOTHER card":
    an event is already sitting in its owner's discard by the time its own ability
    resolves, so Commence Patrol would otherwise be its own best target.  A SECOND
    copy of Commence Patrol in a discard pile stays a legal choice."""
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=1, then_create_token="X-Wing",
        exclude_ids=frozenset({source_ci.instance_id}),
    )
    return state


@card_ability("JTL", "205")
def _commence_patrol_jtl_205():
    """JTL_205 — Commence Patrol (Event, Tactic, 1): "Put another card in a discard
    pile on the bottom of its owner's deck.  If you do, create an X-Wing token."

    "A discard pile" is either player's (the Restock SOR_252 default), so this is
    both graveyard hate against an opponent's recursion and self-recursion of your
    own best card — the controller picks.  The token is the JTL X-Wing Token Unit
    (JTL_2), created through the shared ``_create_token_units`` path."""
    return EventAbility(effects=[CustomEffect(fn=_commence_patrol_fn)])


def _jam_communications_fn(state, source_ci, target_id, event_ctx):
    """Reveal an opponent's hand and discard an event from it."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, card_type="event")
    return state


@card_ability("JTL", "207")
def _jam_communications_jtl_207():
    """JTL_207 — Jam Communications (Event, Trick, 1): "Look at an opponent's hand
    and discard an event from it."

    The ``name_and_discard`` decision already models "the controller sees the
    opponent's hand, then one card leaves it" (Bazine Netal SHD_184 is the same
    look-then-strip shape).  The new ``card_type`` filter keeps the WHOLE hand
    revealed — that is the printed "look at" half — while narrowing what may be
    named to the events in it; with no event in hand the decision fizzles with no
    prompt, exactly as an empty hand already did."""
    return EventAbility(effects=[CustomEffect(fn=_jam_communications_fn)])


@card_ability("JTL", "220")
def _skyway_cloud_car_jtl_220():
    """JTL_220 — Skyway Cloud Car (Unit, Fighter/Fringe/Vehicle, 3/3): "When
    Defeated: You may return a non-leader unit with 2 or less power to its owner's
    hand."

    Pure reuse: an optional ``WhenDefeated`` ``ReturnToHand`` over the existing
    ``power_max`` filter (Independent Senator TWI_206), which reads EFFECTIVE power
    — a 1-power Pilot pumped past 2 by an Experience token is out of reach, and a
    debuffed 4-power unit is in it.  "A non-leader unit" is either player's, so
    this can also rescue a friendly unit that is about to die."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                         predicates=("non_leader",),
                                         power_max=2))],
        optional=True,
    )


def _stolen_at_hauler_fn(state, source_ci, target_id, event_ctx):
    """Grant the (single) opponent a free replay of this unit out of its owner's
    discard pile for the rest of the phase.

    The sibling of Second Chance SHD_53's per-instance permission, except the
    beneficiary is the OTHER player, so it is recorded in the cross-pile ledger
    ``game_memory.foreign_free_discard_play_this_phase`` (permitted player →
    instance ids) that ``_enumerate_discard_play_actions`` reads.  "Choose an
    opponent" is forced in a two-player game, so no prompt.  The unit is not yet in
    the discard when a WhenDefeated trigger resolves, but its instance_id is
    stable, so flagging it here is enough; it enters under the player who replays
    it, while ``owner_id`` — and therefore the pile it returns to — is unchanged."""
    opp_id = next(p.player_id for p in state.players
                  if p.player_id != source_ci.owner_id)
    ledger = state.game_memory.foreign_free_discard_play_this_phase
    ids = ledger.setdefault(opp_id, [])
    if source_ci.instance_id not in ids:
        ids.append(source_ci.instance_id)
    return state


@card_ability("JTL", "221")
def _stolen_at_hauler_jtl_221():
    """JTL_221 — Stolen AT-Hauler (Unit, Transport/Underworld/Vehicle, 4/5): "When
    Defeated: Choose an opponent.  For this phase, they may play this unit from its
    owner's discard pile for free."

    A 3-cost 4/5 whose drawback is that killing it hands it to the killer — the
    stolen hauler gets stolen again.  Mandatory (no "you may"), so it resolves
    inline with no prompt."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_stolen_at_hauler_fn)],
    )


@card_ability("JTL", "223")
def _razor_crest_jtl_223():
    """JTL_223 — Razor Crest, "Ride For Hire" (Unit, Mandalorian/Transport/Vehicle,
    3/5): "When a Pilot attaches to this unit: You may return a non-leader unit
    that costs 2 or less or an exhausted non-leader unit that costs 4 or less to
    its owner's hand."

    The trigger is the existing ``WhenYouPlayCard`` controller-observer narrowed by
    ``on_self`` (the played card must be attached to THIS unit — Kylo Ren LOF_229)
    and ``trait="Pilot"``; by the time ``CardPlayed`` fires, both the ordinary
    upgrade play and the ``PilotPlay`` path have already attached the card, so a
    Piloting unit riding as a Pilot counts exactly like a printed Pilot upgrade.
    (A LEADER deploying as a Pilot fires ``LeaderDeployed`` rather than
    ``CardPlayed`` and is a documented non-trigger.)

    The disjunctive target — "costs 2 or less" OR "exhausted and costs 4 or less" —
    is one spec via the new ``cost_max_if_exhausted``: an exhausted candidate is
    measured against the higher cap.  It is the per-candidate sibling of
    ``cost_max_boost`` (Kanan Jarrus LAW_89), which reads the source controller's
    board instead."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(on_self=True, trait="Pilot"),
        effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                         predicates=("non_leader",),
                                         cost_max=2, cost_max_if_exhausted=4))],
        optional=True,
    )


# ── Group jtl-set:11 — Leaders (combat tricks, buffs & tempo) ────────────────
#
# Seven leaders.  SIX are encoded here; JTL_2 Grand Admiral Thrawn lives at the end
# of this module with the rest of the ability-redo framework — see the note below.
#
# ⚠️ TOKEN-COLLISION HAZARD (the JTL_1 Asajj Ventress rule, now hit twice more):
# JTL_3 is BOTH Lando Calrissian (Leader) and the **Experience Token Upgrade**, and
# JTL_4 is BOTH Rose Tico and the **Shield Token Upgrade** — ``get_abilities`` is
# keyed on (set, number) strings alone, so every spec registered for these two
# numbers is also read for every Experience/Shield token on the board.  Safe spec
# kinds here are only those the collision cannot reach:
#   * ``ActivatedAbility(undeployed_only=True)`` — the enumeration and the trigger
#     collector both require a **Leader** card_def.
#   * ``TriggerAbility(deployed_only=True)`` — likewise requires a *deployed leader*,
#     and a token UPGRADE is never an arena unit, so it is never even a candidate.
#   * ``TriggerAbility(WhenDeployed(via_pilot_leader=True))`` — matched by INSTANCE
#     ID against a LeaderDeployed event.
# ❌ NOT SAFE for these two numbers: a ``ConstantAbility``/passive marker (the
# constant-stat and keyword scans walk by (set, number) with no leader gate) AND —
# unlike JTL_1, whose twin is a token UNIT — a ``GrantedAbility``, because the
# granted-trigger scan reads a host's ``attached_upgrades``, which is exactly where
# an Experience/Shield token lives.  So Lando's "Attached unit gains Sentinel" is a
# PERMANENT ``keyword_grant`` modifier applied from his deploy-as-an-upgrade
# trigger (the Asajj JTL_1 recipe), which also gets the right lifetime for free.


def _lando_jtl_3_play_unit(state, source_ci, target_id, event_ctx):
    """"Play a unit from your hand (paying its cost).  If you do and you control a
    ground unit and a space unit, give a Shield token to a unit."

    Both halves are ONE effect: the Shield rides along as the play_from_hand
    decision's SETTLE payoff, so the freshly-played unit counts toward the
    two-arena gate — which is the whole point of the clause, and impossible if the
    Shield were a second effect of the ability (the resolve_effects walker would
    run it before the play).  play_from_hand is mandatory-if-able and pushed only
    when able, so "if you do" is guaranteed by the gate on the ability."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, then_select_token={
        "token_type": "Shield", "max_targets": 1, "require_both_arenas": True,
    })
    return state


def _lando_jtl_3_deploy_as_upgrade(state, source_ci, target_id, event_ctx):
    """Grant the host Sentinel permanently, then offer a Shield to a unit in the
    OTHER arena.

    The Sentinel half is a permanent ``keyword_grant`` modifier rather than the
    usual ``ConstantAbility(SELF, KeywordGrant)`` — see the token-collision note
    above — and ``keywords._permanent_kw_source_in_play`` counts an attached
    upgrade as in play, so the grant lapses the instant Lando detaches, which is
    exactly what "attached unit gains" means."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_select_token
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import execute_effect
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    state = execute_effect(
        state, GrantKeyword("Sentinel", 0, target=TargetSpec(),
                            duration=Duration.PERMANENT),
        source_ci, host_id, event_ctx)
    host_res = state.find_instance(host_id)
    if host_res is None:
        return state
    other = "space" if host_res[1].zone == Zone.GROUND_ARENA else "ground"
    push_select_token(state, source_ci, token_type="Shield", max_targets=1,
                      arena=other)
    return state


@card_ability("JTL", "3")
def _lando_calrissian_jtl_3():
    """JTL_3 — Lando Calrissian, Buying Time (Leader, Rebel/Official/Pilot, 5/7
    with Sentinel; +5/+5 as a Pilot upgrade).

    * **Undeployed** "Action [1 resource, Exhaust]: Play a unit from your hand
      (paying its cost).  If you do and you control a ground unit and a space unit,
      give a Shield token to a unit." — two effects of one ``ActivatedAbility``:
      the play (Ozzel SOR_129's ``play_from_hand``) then the conditional Shield
      (``select_token``), gated so the exhaust is never spent on nothing.
    * **Deployed as a unit**: Sentinel only — a PRINTED keyword, read off the
      Leader's own card_def, so the Experience token (whose card_def has no
      keywords) is untouched.
    * **Deployed as an upgrade** "Attached unit is a leader unit.  Attached unit
      gains Sentinel.  When deployed as an upgrade: You may give a Shield token to a
      unit in a different arena." — "is a leader unit" needs no spec
      (``resolver._is_leader_unit`` counts any unit carrying a Leader pilot); the
      rest is the single ``WhenDeployed(via_pilot_leader=True)`` above.
    """
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_lando_jtl_3_play_unit)],
            title="Play a unit; if you hold both arenas, Shield a unit",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND),
        ),
        TriggerAbility(
            trigger=WhenDeployed(via_pilot_leader=True),
            effects=[CustomEffect(fn=_lando_jtl_3_deploy_as_upgrade)],
        ),
    ]


@card_ability("JTL", "4")
def _rose_tico_jtl_4():
    """JTL_4 — Rose Tico, Saving What We Love (Leader, Resistance, 4/6).

    * **Undeployed** "Action [Exhaust]: Heal 2 damage from a Vehicle unit that
      attacked this phase." — the existing ``attacked_this_phase`` predicate.
    * **Deployed** "On Attack: You may heal 2 damage from a Vehicle unit." — the
      same heal without the attacked gate, and optional.

    Both spec kinds are leader-gated, so the Shield token that shares this number
    (see the collision note above) reaches neither: ``undeployed_only`` requires a
    Leader card_def and ``deployed_only`` a *deployed* leader, while a token upgrade
    is never an arena unit and so never a trigger candidate at all."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                        traits=("Vehicle",),
                                        predicates=("attacked_this_phase",)))],
            title="Heal 2 from a Vehicle that attacked this phase",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                        traits=("Vehicle",)))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _piett_jtl_5_play_capital_ship(state, source_ci, target_id, event_ctx):
    """"Play a Capital Ship unit from your hand.  It costs 1 resource less"."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, trait="Capital Ship", cost_reduction=1)
    return state


@card_ability("JTL", "5")
def _admiral_piett_jtl_5():
    """JTL_5 — Admiral Piett, Commanding the Armada (Leader, Imperial/Official, 2/7).

    * **Undeployed** "Action [Exhaust]: Play a Capital Ship unit from your hand.  It
      costs 1 resource less." — ``play_from_hand`` with a trait + discount, gated by
      ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND`` measured at the SAME discounted price
      the decision will offer (the new ``(trait, reduction)`` param form), so the
      exhaust is never spent on an empty prompt.
    * **Deployed** "Each Capital Ship unit you play costs 2 resources less." — a
      ``StandingPlayDiscount`` with the new ``"trait:<Trait>"`` predicate and
      ``once_per_round=False`` ("each", not "the first").  The discount scan walks
      ARENA units only, so an undeployed Piett sitting in the base zone grants
      nothing — the deployed-only reading falls out for free with no gate."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_piett_jtl_5_play_capital_ship)],
            title="Play a Capital Ship for 1 less",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                                     param=("Capital Ship", 1)),
        ),
        StandingPlayDiscount(amount=2, applies_to="trait:Capital Ship",
                             once_per_round=False),
    ]


@card_ability("JTL", "7")
def _admiral_holdo_jtl_7():
    """JTL_7 — Admiral Holdo, We're Not Alone (Leader, Resistance/Official, 3/8).

    * **Undeployed** "Action [1 resource, Exhaust]: Give a Resistance unit or a unit
      with a Resistance upgrade on it +2/+2 for this phase."
    * **Deployed** "On Attack: You may give ANOTHER Resistance unit or a unit with a
      Resistance upgrade on it +2/+2 for this phase."

    Both halves are one ``ModifyStats`` over the new ``trait_or_upgrade_trait``
    TargetSpec field, which is precisely the printed disjunction: the unit's own
    effective traits OR the printed traits of anything attached to it.  In JTL that
    second arm is mostly a Resistance *Pilot* riding a Vehicle — the card is written
    to reward exactly the pilot deck it ships in.  The deployed clause adds
    ``not_self`` for the printed "another"."""
    from swu.abilities.registry import Duration, ModifyStats
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[ModifyStats(2, 2, TargetSpec(
                controller="any", kind="unit",
                trait_or_upgrade_trait="Resistance"), Duration.THIS_PHASE)],
            title="Give a Resistance unit +2/+2",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(2, 2, TargetSpec(
                controller="any", kind="unit",
                trait_or_upgrade_trait="Resistance",
                predicates=("not_self",)), Duration.THIS_PHASE)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _wedge_jtl_8_pilot_play(state, source_ci, target_id, event_ctx):
    """"Play a card from your hand using Piloting.  It costs 1 resource less"."""
    from swu.engine.actions import push_play_via_piloting
    push_play_via_piloting(state, source_ci, cost_reduction=1)
    return state


@card_ability("JTL", "8")
def _wedge_antilles_jtl_8():
    """JTL_8 — Wedge Antilles, Leader of Red Squadron (Leader, Rebel/Pilot, 3/6;
    Piloting, +3/+4 as a Pilot upgrade).

    * **Undeployed** "Action [Exhaust]: Play a card from your hand using Piloting.
      It costs 1 resource less." — the NEW ``play_via_piloting`` decision kind, the
      Piloting sibling of Lando SHD_17's ``play_via_smuggle``: it reuses the
      ``PilotPlay`` mechanics (``_piloting_cost`` → ``_attach_pilot``) but resolves
      inside the ability without handing the turn over, and enumerates (pilot, host)
      PAIRS so a Piloting card with no Vehicle to ride is never offered.  Gated by
      ``CONTROLLER_CAN_PILOT`` at the same discount.
    * **Deployed as an upgrade** "Attached unit is a leader unit.  It gains: 'On
      Attack: The next Pilot card you play this phase costs 1 resource less. (This
      includes Piloting costs.)'" — a ``GrantedAbility`` (safe here: JTL_8 is not a
      token number) wrapping the existing ``NextPlayDiscount``, with the new
      ``applies_to_piloting`` flag so the entry is also read and consumed by
      ``_piloting_cost`` / ``PilotPlay`` — the parenthetical is the whole point of
      the card, and without the flag a Piloting play would sail past the discount.
      ``units_only=False`` because it is a "Pilot *card*"."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_wedge_jtl_8_pilot_play)],
            title="Play a Pilot from hand for 1 less",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PILOT, param=1),
        ),
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=[NextPlayDiscount(trait="Pilot", amount=1, units_only=False,
                                      applies_to_piloting=True)],
        )),
    ]


def _vonreg_jtl_11_play_vehicle(state, source_ci, target_id, event_ctx):
    """"Play a Vehicle unit from your hand (paying its cost).  If you do, give
    another unit +1/+0 for this phase."

    The buff is the play_from_hand decision's SETTLE payoff — a buff-only
    ``select_token`` (``token_type=None``) whose ``exclude_played`` bars the
    freshly-played Vehicle, which is exactly the printed "another"."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, trait="Vehicle", then_select_token={
        "token_type": None, "max_targets": 1,
        "power_bonus": 1, "hp_bonus": 0, "duration": "this_phase",
        "exclude_played": True,
    })
    return state


@card_ability("JTL", "11")
def _major_vonreg_jtl_11():
    """JTL_11 — Major Vonreg, Red Baron (Leader, First Order/Pilot, 2/5; +3/+3 as a
    Pilot upgrade).

    * **Undeployed** "Action [Exhaust]: Play a Vehicle unit from your hand (paying
      its cost).  If you do, give another unit +1/+0 for this phase." — one effect:
      the play carries its own settle payoff (``then_select_token``), a buff-only
      ``select_token`` whose ``exclude_played`` bars the freshly-played Vehicle, so
      the printed "another" lands exactly.
    * **Deployed as an upgrade** "Attached unit is a leader unit.  It gains: 'On
      Attack: You may give another unit in this arena +1/+0 for this phase.'" — a
      ``GrantedAbility`` resolving from the HOST, whose target uses the new
      ``same_arena_as_source`` predicate ("in this arena", source-anchored) plus
      ``not_self`` ("another")."""
    from swu.abilities.registry import Duration, ModifyStats
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_vonreg_jtl_11_play_vehicle)],
            title="Play a Vehicle, then give another unit +1/+0",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                                     param="Vehicle"),
        ),
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(1, 0, TargetSpec(
                controller="any", kind="unit",
                predicates=("not_self", "same_arena_as_source")),
                Duration.THIS_PHASE)],
            optional=True,
        )),
    ]


# ── ESCALATION RESOLVED (jtl-set:11, framework session 2026-08-06) ────────────
#
# JTL_2 Grand Admiral Thrawn is now registered at the END of this module (with the
# other framework work), not here, because both leader sides are passive
# ``WhenDefeatedRedo`` markers rather than group-11 leader abilities.  What made it
# an escalation — an OBSERVER on the *use* of an entire trigger class, plus
# RE-RESOLUTION of an arbitrary already-resolved ability — turned out to be exactly
# what Qui-Gon Jinn's Aethersprite LOF_197 had already built for the When Played
# half.  Generalising that chokepoint (``resolver._schedule_when_played_redo`` →
# ``_schedule_ability_redo``) covered both cards with no new decision kind.  (The
# X-Wing token still shares this number — see the collision note at the top of this
# group; Thrawn adds only markers, which the token never reads.)


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:12 — Combat tricks, buffs & tempo (two leaders + five cards)
# ══════════════════════════════════════════════════════════════════════════════
#
# No token collisions in this group: JTL_15/16/32/34/36/42/44 are each a single DB
# row.  Four of the seven are PURE REUSE of shapes the catalog already names; the
# only "new" machinery is one existing condition atom (SOURCE_HAS_TRAIT) read at a
# seam that already existed (``_upgrade_self_stat_bonus``).


def _rio_jtl_15_space_attack(state, source_ci, target_id, event_ctx):
    """"Attack with a space unit.  It gets +1/+0 and gains Saboteur for this attack."

    A plain ``push_granted_attack`` narrowed to the space arena.  MANDATORY — the
    printed rules insert says "you must attack with a unit, if able" — and left
    UNGATED: with no ready space unit the decision offers only
    ``DeclineGrantedAttack``, so it fizzles cleanly rather than needing a
    board-reading condition atom.
    """
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1,
                        attacker_arena="space", grant_keywords=["Saboteur"])
    return state


@card_ability("JTL", "15")
def _rio_durant_jtl_15():
    """JTL_15 — Rio Durant, "Grinning Gunner" (Leader, Underworld/Pilot, 3/5;
    Saboteur):

    * **Undeployed** "Action [1 resource, Exhaust]: Attack with a space unit.  It
      gets +1/+0 and gains Saboteur for this attack."
    * **Deployed as an upgrade** "Attached unit is a leader unit.  It gains
      Saboteur.  If it's a Transport, it also gets +1/+0."

    "Attached unit is a leader unit" is free — ``resolver._is_leader_unit`` already
    counts a unit carrying a LEADER as a Pilot upgrade (the Boba Fett JTL_9 rule).

    The other two clauses are the ordinary "attached unit gains …" convention: an
    unconditional ``ConstantAbility(SELF, KeywordGrant)`` and a conditional
    ``ConstantAbility(SELF, StatBonus)``, both read off the host by the two
    attached-upgrade scans (``keywords.has_keyword`` / ``_upgrade_self_stat_bonus``),
    which evaluate a present condition against the HOST — so
    ``SOURCE_HAS_TRAIT("Transport")`` is exactly "if it's a Transport".  Safe here
    only because JTL_15 has no token twin; on a colliding number a ConstantAbility
    would be forbidden (see the jtl-set:11 header).  As a deployed leader UNIT both
    specs still read correctly: Rio grants himself the Saboteur he already prints,
    and he is not a Transport, so the +1/+0 never applies to him."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_rio_jtl_15_space_attack)],
            title="Attack with a space unit (+1/+0 and Saboteur)",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Saboteur")],
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(1, 0)],
            condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Transport"),
        ),
    ]


def _ackbar_jtl_16_exhaust(state, source_ci, target_id, event_ctx):
    """"Exhaust a unit.  If you do, ITS CONTROLLER creates an X-Wing token."

    One targeted ``CustomEffect`` carrying both clauses (the Kylo Ren SHD_141
    shape), because the token's recipient is decided by the chosen target — the
    ``CreateTokenUnit(player=)`` axis only knows "controller"/"opponent"/"each".
    ``find_instance`` returns the player whose zone HOLDS the unit, i.e. its
    controller, so a unit stolen with a control-change effect makes the token for
    whoever currently controls it.

    The "if you do" is protected on both sides: candidates are narrowed to ``ready``
    units so the prompt never offers a guaranteed no-op, and an already-exhausted
    unit slipping through still makes no token.
    """
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder_ps, ci = res
    if ci.exhausted:
        return state
    ci.exhausted = True
    from swu.engine.actions import _create_token_units
    _create_token_units(state, holder_ps, "X-Wing", 1)
    return state


@card_ability("JTL", "16")
def _admiral_ackbar_jtl_16():
    """JTL_16 — Admiral Ackbar, "Brilliant Strategist" (Leader, Rebel/Official, 3/8):

    * **Undeployed** "Action [1 resource, Exhaust]: Exhaust a **non-leader** unit.
      If you do, its controller creates an X-Wing token."
    * **Deployed** "On Attack: You may exhaust **a unit**.  If you do, its
      controller creates an X-Wing token."

    Both halves share ``_ackbar_jtl_16_exhaust``; only the candidate filter differs
    (the deployed side drops the ``non_leader`` restriction, exactly as printed).
    The deployed trigger is ``optional=True`` for its "you may" and carries
    ``deployed_only=True`` so it reads as the deploy-box ability it is."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(
                fn=_ackbar_jtl_16_exhaust,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("non_leader", "ready")),
            )],
            title="Exhaust a non-leader unit (its controller creates an X-Wing)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_ackbar_jtl_16_exhaust,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("ready",)),
            )],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("JTL", "32")
def _director_krennic_jtl_32():
    """JTL_32 — Director Krennic (Unit, Imperial/Official, 2/2; Shielded): "The
    first unit you play each round that has a 'When Defeated' ability costs 1
    resource less."

    Shielded is the keyword layer.  The discount is the passive
    ``StandingPlayDiscount`` marker — whose default
    ``applies_to="has_when_defeated_ability"`` was built for this very card's
    prerelease twin JTLP_1 (B31), read at the play-cost seam (``actions._play_cost``
    via ``_standing_play_discount``) and consumed once per round per source.  Pure
    reuse: one line, no trigger, no decision."""
    return StandingPlayDiscount(amount=1)


@card_ability("JTL", "34")
def _interceptor_ace_jtl_34():
    """JTL_34 — Interceptor Ace (Unit, Imperial/Pilot, 2/3; Grit, Piloting
    [3 resources Vigilance Villainy]): "Attached unit gains Grit."

    Grit and Piloting are the keyword layer.  The residual is the plain
    "attached unit gains <keyword>" convention — an unconditional
    ``ConstantAbility(SELF, KeywordGrant)`` that ``keywords.has_keyword``'s
    attached-upgrade scan confers on the host (Grievous's Wheel Bike TWI_236).
    Played as a vanilla 2/3 unit the same spec grants Interceptor Ace the Grit he
    already prints, which is a no-op.

    Note the sanitiser leaves his printed Grit alone: rule 2 needs a *conditional*
    self-grant and rule 4 only strips a printed **Raid**."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Grit")],
    )


def _iden_versio_jtl_36_shield(state, source_ci, target_id, event_ctx):
    """Give a Shield token to the unit this upgrade just attached to.

    The host comes from ``event_ctx["attached_to_id"]`` (the LOF_140 seam) rather
    than a prompt — "that unit" is the attach target, never a choice."""
    host_id = (event_ctx or {}).get("attached_to_id")
    if not host_id:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    _, host = res
    from swu.engine.tokens import attach_token
    attach_token(state, state.player_by_id(host.owner_id), host, "Shield")
    return state


@card_ability("JTL", "36")
def _iden_versio_jtl_36():
    """JTL_36 — Iden Versio (Unit, Imperial/Pilot, 4/3; Shielded, Piloting
    [3 resources Vigilance Villainy]): "When this upgrade attaches to a unit: Give
    a Shield token to that unit."

    Shielded and Piloting are the keyword layer — played as a 4/3 unit she shields
    herself and this ability never fires.  The residual is
    ``WhenPlayed(as_upgrade=True)`` (the Boba Fett JTL_189 flag), which fires only
    on the Pilot-upgrade play path, plus a no-target ``CustomEffect`` reading
    ``event_ctx["attached_to_id"]``.

    DEVIATION: "attaches" is strictly broader than "is played as an upgrade" — an
    effect that MOVED her onto a new host would also read as an attach.  No shipped
    card moves a Pilot upgrade between hosts, so the play path is the whole of it."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(fn=_iden_versio_jtl_36_shield)],
    )


def _power_from_pain_jtl_42_fn(state, source_ci, target_id, event_ctx):
    """+1/+0 for this phase for each damage on the chosen unit.

    The magnitude is SNAPSHOTTED at resolution — "the unit gets +1/+0 only for the
    damage on it when this event is played" (the printed rules insert) — so this is
    a flat ``_make_modifier`` sized once, not the re-reading
    ``StatBonus(count="target_damage")`` aura (Radiant VII JTL_226).  An undamaged
    unit gets no modifier at all."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    amount = getattr(ci, "damage", 0) or 0
    if amount <= 0:
        return state
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=amount, hp=0, duration=Duration.THIS_PHASE))
    return state


@card_ability("JTL", "42")
def _power_from_pain_jtl_42():
    """JTL_42 — Power from Pain (Event, Tactic, 3): "Give a unit +1/+0 for this
    phase for each damage on it."

    One targeted ``CustomEffect`` that reads the victim's damage and applies a
    single sized ``THIS_PHASE`` stat modifier (the Heartless Tactics JTL_194 shape,
    with the sign flipped and the amount computed)."""
    return EventAbility(effects=[CustomEffect(
        fn=_power_from_pain_jtl_42_fn,
        target=TargetSpec(controller="any", kind="unit"),
    )])


@card_ability("JTL", "44")
def _echo_base_engineer_jtl_44():
    """JTL_44 — Echo Base Engineer (Unit, Rebel, 2/3): "When Played: You may give a
    Shield token to a damaged Vehicle unit."

    Declarative ``GiveToken`` over a ``damaged`` + Vehicle-trait target, either side
    of the board as printed; ``optional=True`` is the "you may" and auto-declines
    when no damaged Vehicle is in play."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="any", kind="unit",
            traits=("Vehicle",), predicates=("damaged",)))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:13 — Combat tricks, buffs & tempo (the Pilot-upgrade residual batch)
# ══════════════════════════════════════════════════════════════════════════════
#
# Five of the seven are Piloting units whose only residual is an "attached unit
# gains …" clause.  The convention is an unconditional
# ``ConstantAbility(target=SELF, …)``, which BOTH attached-upgrade scans read off
# the host (``keywords.has_keyword`` for a KeywordGrant,
# ``actions._upgrade_self_stat_bonus`` for a StatBonus) — see Grievous's Wheel Bike
# TWI_236 / IG-88 JTL_141.  ⚠️ That shape only works when the unit-side reading of
# the same spec is harmless, i.e. when the card PRINTS the thing it grants.  Phantom
# II JTL_50 does not (+3/+3 only as an upgrade), so its buff is a pair of PERMANENT
# modifiers applied at attach time (the Lando JTL_3 recipe) whose lifetime
# ``_modifier_source_in_play`` already ties to the upgrade staying in play.


@card_ability("JTL", "45")
def _hera_syndulla_jtl_45():
    """JTL_45 — Hera Syndulla (Unit, Rebel/Spectre/Twi'lek/Pilot, 2/3; Restore 1,
    Piloting [2 resources Vigilance Heroism]): "Attached unit gains Restore 1."

    Restore 1 and Piloting are the keyword layer.  The residual is the
    "attached unit gains <keyword N>" convention with a VALUE — the keyword query
    layer's attached-upgrade scan has a numeric-value sibling
    (``keywords.keyword_value``), so ``KeywordGrant("Restore", 1)`` confers
    Restore *1* on the host rather than an untyped Restore.  Played as a 2/3 unit
    the same spec grants Hera the Restore 1 she already prints (a no-op)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", 1)],
    )


def _phantom_ii_jtl_50_attach(state, source_ci, target_id, event_ctx):
    """Attach Phantom II to The Ghost, then apply its "+3/+3 and Grit" as PERMANENT
    modifiers on the host.

    ``_attach_unit_as_pilot`` (the Poe JTLP_6 relocation) already does everything
    the printed rules insert asks for: it removes Phantom II from its arena, sends
    its own real upgrades to the discard, clears its damage and drops the modifiers
    that targeted it as a unit.

    The buff CANNOT be the usual ``ConstantAbility(SELF, StatBonus)``: unlike
    IG-88 JTL_141, whose bonus is the same either way, Phantom II is a plain 3/3
    while it is a unit — and the ARENA constant-stat scan walks units by
    (set, number) with no upgrade gate, so a SELF StatBonus would silently make the
    unit-side 6/6.  Two permanent modifiers instead, whose lifetime
    ``_modifier_source_in_play`` / ``keywords._permanent_kw_source_in_play`` tie to
    Phantom II remaining attached — exactly "attached unit gets".  (Its printed
    Grit means the KeywordGrant would have been safe on its own; keeping both
    clauses on the same path keeps them impossible to desynchronise.)
    """
    from swu.engine.actions import _attach_unit_as_pilot
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import execute_effect, _make_modifier
    ps = state.player_by_id(source_ci.owner_id)
    ghost = next((ci for ci in ps.ground_arena + ps.space_arena
                  if ci.instance_id != source_ci.instance_id
                  and (ci.card_def.name or "") == "The Ghost"), None)
    if ghost is None:
        return state
    host_id = ghost.instance_id
    _attach_unit_as_pilot(state, source_ci.instance_id, host_id)
    if state.find_instance(source_ci.instance_id) is None:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, host_id,
        power=3, hp=3, duration=Duration.PERMANENT))
    return execute_effect(
        state, GrantKeyword("Grit", 0, target=TargetSpec(),
                            duration=Duration.PERMANENT),
        source_ci, host_id, event_ctx)


@card_ability("JTL", "50")
def _phantom_ii_jtl_50():
    """JTL_50 — Phantom II (Unit, Rebel/Spectre/Transport/Vehicle, 3/3; Grit):
    "Action [1 resource]: If this card is a unit, attach it as an upgrade to The
    Ghost.  (It's no longer a unit.  Defeat all upgrades on it and remove all
    damage from it.)" + "Attached unit gets +3/+3 and gains Grit."

    "If this card is a unit" is free: ``legal_actions`` enumerates a bare
    ``ActivatedAbility`` only from arena units and leaders, and an attached upgrade
    needs a ``GrantedAbility`` wrapper to be offered (Heroic Resolve SHD_155) — so
    once Phantom II is riding The Ghost the Action disappears by construction.

    The Ghost is unique, so there is exactly one legal host and no prompt is
    needed; ``CONTROLLER_CONTROLS_NAMED`` keeps the resource from being spent when
    it is not on the board."""
    return ActivatedAbility(
        costs=[PayResources(1)],
        effects=[CustomEffect(fn=_phantom_ii_jtl_50_attach)],
        title="Attach to The Ghost as an upgrade",
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                 param="The Ghost"),
    )


@card_ability("JTL", "57")
def _astromech_pilot_jtl_57():
    """JTL_57 — Astromech Pilot (Unit, Droid/Pilot, 1/3; Piloting [2 resources
    Vigilance]): "When played as an upgrade: You may heal 2 damage from a unit."

    ``WhenPlayed(as_upgrade=True)`` (the Boba Fett JTL_189 flag) so a vanilla 1/3
    play does nothing, plus a declarative ``Heal`` over any unit — the "you may" is
    ``optional=True``, which auto-declines when nothing is damaged."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                    predicates=("damaged",)))],
        optional=True,
    )


@card_ability("JTL", "58")
def _academy_graduate_jtl_58():
    """JTL_58 — Academy Graduate (Unit, Imperial/Pilot, 1/2; Sentinel, Piloting
    [2 resources Vigilance]): "Attached unit gains Sentinel."

    The plain "attached unit gains <keyword>" convention, exactly like Interceptor
    Ace JTL_34; played as a unit it re-grants the Sentinel it already prints."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
    )


def _trace_martez_jtl_66_heal(state, source_ci, target_id, event_ctx):
    """Heal 2 total damage spread across any number of friendly units."""
    from swu.engine.actions import push_distribute_heal
    push_distribute_heal(state, source_ci, 2,
                         include_bases=False, then_damage_self=False)
    return state


@card_ability("JTL", "66")
def _trace_martez_jtl_66():
    """JTL_66 — Trace Martez (Unit, Fringe/Pilot, 2/5; Piloting [1 resource
    Vigilance]): "Attached unit gains: 'On Attack: You may heal 2 total damage
    from any number of units.'"

    A ``GrantedAbility(TriggerAbility(OnAttack))`` — never collected while Trace is
    an ordinary unit (the granted-trigger scan reads a host's ``attached_upgrades``),
    which IS the "attached unit gains" reading (Cassian JTL_48).

    "2 total damage from any number of units" is the heal flavour of the
    ``distribute_damage`` pool, ``push_distribute_heal`` (Redemption SOR_52), with
    bases and the heal-it-back rider both off.  It inherits SOR_52's documented
    narrowing to the controller's OWN damaged units, and is "up to" by
    construction, so the ability fizzles with no prompt when nothing is damaged —
    which also covers the printed "you may"."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_trace_martez_jtl_66_heal)],
        optional=True,
    ))


@card_ability("JTL", "67")
def _cloaked_starviper_jtl_67():
    """JTL_67 — Cloaked StarViper (Unit, Underworld/Vehicle/Fighter, 3/2): "When
    Played: Give 2 Shield tokens to this unit."

    A self-targeted ``GiveToken(count=2)`` — mandatory, no prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(fixed=SELF), count=2)],
    )


def _u_wing_lander_jtl_70_ferry(state, source_ci, target_id, event_ctx):
    """Offer to move one upgrade off the U-Wing onto another friendly Vehicle."""
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci,
                      from_host_id=source_ci.instance_id,
                      dest_traits=["Vehicle"],
                      include_tokens=True)
    return state


@card_ability("JTL", "70")
def _u_wing_lander_jtl_70():
    """JTL_70 — U-Wing Lander (Unit, Rebel/Transport/Vehicle, 2/2): "When Played:
    Give 3 Experience tokens to this unit." + "When this unit completes an attack
    (and survives): You may attach an upgrade on this unit to another eligible
    friendly Vehicle unit."

    The load-up is a self-targeted ``GiveToken(count=3)``.  The ferry is
    ``WhenAttackEnds`` (which already means "and survives" — the LOF_38 seam) onto
    the ``move_upgrade`` decision (Survivors' Gauntlet SHD_64), narrowed by its
    three new context filters: ``from_host_id`` pins the source host to "this
    unit", ``dest_traits`` to "Vehicle", and ``include_tokens`` admits the very
    Experience tokens the first ability just created — which the board-wide default
    excludes under the engine's ``kind="upgrade"`` convention, and without which
    the card's own two halves would not talk to each other.

    ``push_move_upgrade`` is pushed only when something can really move, so the
    "you may" needs no separate decline path."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[GiveToken("Experience", TargetSpec(fixed=SELF), count=3)],
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_u_wing_lander_jtl_70_ferry)],
            optional=True,
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:14 — Combat tricks, buffs & tempo (shields, keyword swings, tokens)
# ══════════════════════════════════════════════════════════════════════════════
#
# Six of the seven are pure reuse.  The one new piece of engine surface is a
# condition atom, ``CONTROLLER_HAS_TOKEN_UNIT`` (JTL_81) — the condition sibling of
# the long-standing ``token_unit`` target predicate.


@card_ability("JTL", "71")
def _cr90_relief_runner_jtl_71():
    """JTL_71 — CR90 Relief Runner (Unit, Rebel/Vehicle/Capital Ship, 4/6;
    Restore 2): "When Defeated: Heal up to 3 damage from a unit or base."

    Restore 2 is the keyword layer.  The death rattle is a declarative ``Heal``
    over ``kind="unit_or_base"`` (either player's, as printed).  "Up to 3" needs no
    extra machinery — ``Heal`` already caps at the damage actually present — and
    the ``damaged`` predicate keeps a fully-healthy board from raising a prompt
    that could do nothing."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[Heal(3, TargetSpec(controller="any", kind="unit_or_base",
                                    predicates=("damaged",)))],
    )


def _wing_guard_jtl_72_shields(state, source_ci, target_id, event_ctx):
    """Give a Shield to each of up to 2 Fringe units (either player's)."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Shield", max_targets=2,
                      controller="any", traits=["Fringe"])
    return state


@card_ability("JTL", "72")
def _wing_guard_security_team_jtl_72():
    """JTL_72 — Wing Guard Security Team (Unit, Fringe/Trooper, 4/4; Sentinel):
    "When Played: Give a Shield token to each of up to 2 Fringe units."

    Sentinel is the keyword layer.  The residual is the ``select_token`` decision
    (Medal Ceremony SOR_245) with a trait filter; "up to" is that decision's
    stop-early, and Wing Guard — itself Fringe — is an eligible recipient."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_wing_guard_jtl_72_shields)],
    )


@card_ability("JTL", "73")
def _grim_valor_jtl_73():
    """JTL_73 — Grim Valor (Upgrade, Innate, +1/+1): "Attached unit gains: 'When
    Defeated: You may exhaust a unit.'"

    A ``GrantedAbility(TriggerAbility(WhenDefeated))`` — the shape the bounty
    upgrades already use (Public Enemy SHD_68).  By the time ``UnitDefeated`` fires
    the host's upgrades are already detached, which is why ``_defeat_unit`` stashes
    them in ``event_ctx["defeated_upgrades"]``; the collector reads them from there
    and resolves the ability from the HOST.  ``optional=True`` is the "you may",
    and the ``ready`` predicate keeps the prompt off the board when every unit is
    already exhausted."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("ready",)))],
        optional=True,
    ))


def _covering_the_wing_jtl_76(state, source_ci, target_id, event_ctx):
    """Create an X-Wing token, then offer a Shield to any OTHER unit.

    One no-target ``CustomEffect`` rather than two effects: the Shield's candidate
    list has to be computed AFTER the token exists so the new X-Wing can be
    excluded from "another unit" — and the resolve_effects walker resolves an
    earlier no-target effect only when a LATER targeted one is chosen, i.e. in the
    wrong order (the Lando JTL_3 lesson).  ``select_token``'s stop-early is the
    printed "you may"."""
    from swu.engine.actions import _create_token_units, push_select_token
    ps = state.player_by_id(source_ci.owner_id)
    created = _create_token_units(state, ps, "X-Wing", 1)
    push_select_token(state, source_ci, token_type="Shield", max_targets=1,
                      controller="any",
                      exclude_ids=[ci.instance_id for ci in created])
    return state


@card_ability("JTL", "76")
def _covering_the_wing_jtl_76_event():
    """JTL_76 — Covering the Wing (Event, Tactic, 2): "Create an X-Wing token.  You
    may give a Shield token to another unit."."""
    return EventAbility(effects=[CustomEffect(fn=_covering_the_wing_jtl_76)])


@card_ability("JTL", "77")
def _in_the_heat_of_battle_jtl_77():
    """JTL_77 — In the Heat of Battle (Event, Disaster, 2): "Each unit gains
    Sentinel and loses Saboteur for this phase."

    Two ``fixed=EACH_IN_PLAY`` effects, so both auto-target every unit on the board
    with no prompt (and the resolve-order wart cannot bite — neither effect asks
    for a target).  The removal is the existing ``RevokeKeyword`` (Sneak Attack
    SOR_237's Sentinel strip), whose ``keyword_revoke`` modifier is checked FIRST
    by ``has_keyword`` — ahead of the printed bar, every ConstantAbility grant and
    every attached-upgrade grant — so the printed rules insert's "Affected units
    can't gain Saboteur for this phase" falls out for free."""
    from swu.abilities.registry import Duration, RevokeKeyword, EACH_IN_PLAY
    return EventAbility(effects=[
        GrantKeyword("Sentinel", 0,
                     TargetSpec(controller="any", kind="unit", fixed=EACH_IN_PLAY),
                     Duration.THIS_PHASE),
        RevokeKeyword("Saboteur",
                      TargetSpec(controller="any", kind="unit", fixed=EACH_IN_PLAY),
                      Duration.THIS_PHASE),
    ])


@card_ability("JTL", "81")
def _first_order_tie_fighter_jtl_81():
    """JTL_81 — First Order TIE Fighter (Unit, First Order/Vehicle/Fighter, 2/1):
    "While you control a token unit, this unit gains Raid 1."

    A conditional self-grant — ``ConstantAbility(SELF, KeywordGrant("Raid", 1))``
    gated by the new ``CONTROLLER_HAS_TOKEN_UNIT`` atom, the condition sibling of
    the ``token_unit`` target predicate (Shaak Ti TWI_94).  Because the grant is
    conditional AND registered, the keyword sanitiser strips the DB's printed
    "Raid" (rule 2), so a lone TIE Fighter really does lack it and the ability —
    not an always-on bar — owns the keyword."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TOKEN_UNIT),
    )


def _wingman_victor_three_jtl_86(state, source_ci, target_id, event_ctx):
    """Give an Experience token to a unit other than the one being ridden."""
    from swu.engine.actions import push_select_token
    host_id = (event_ctx or {}).get("attached_to_id")
    push_select_token(state, source_ci, token_type="Experience", max_targets=1,
                      controller="any",
                      exclude_ids=[host_id] if host_id else None)
    return state


@card_ability("JTL", "86")
def _wingman_victor_three_jtl_86_unit():
    """JTL_86 — Wingman Victor Three (Unit, Imperial/Pilot, 4/3; Piloting
    [1 resource Command Villainy]): "When played as an upgrade: You may give an
    Experience token to another unit."  (ERRATA: "…to a unit other than the
    attached unit.")

    ``WhenPlayed(as_upgrade=True)`` so a vanilla 4/3 play does nothing, then a
    ``select_token`` whose ``exclude_ids`` carries the errata exactly — the host
    read off ``event_ctx["attached_to_id"]``.  The decision's stop-early is the
    "you may", and it is not pushed at all when the board holds no other unit."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(fn=_wingman_victor_three_jtl_86)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:15 — Combat tricks, buffs & tempo
# (JTL_88, JTL_92, JTL_101, JTL_106, JTL_107, JTL_109)
#
# JTL_94 Luke Skywalker "You Still With Me?" is NOT registered — see the
# escalation note at the bottom of this block.
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("JTL", "88")
def _captain_phasma_on_my_command():
    """When Played/On Attack: You may give another First Order unit +2/+2 for this
    phase.

    Two separate optional triggers over the same one-effect buff — the plain
    "When Played/On Attack" shape (the slash on a printed card is two independent
    trigger conditions, not a choice).  "another First Order unit" is unqualified,
    so an ENEMY First Order unit is a legal target too (``controller="any"``); the
    ``not_self`` predicate supplies the "another".
    """
    from swu.abilities.registry import Duration, ModifyStats
    buff = ModifyStats(2, 2, TargetSpec(
        controller="any", kind="unit", traits=("First Order",),
        predicates=("not_self",)), Duration.THIS_PHASE)
    return [
        TriggerAbility(WhenPlayed(), [buff], optional=True),
        TriggerAbility(OnAttack(), [buff], optional=True),
    ]


def _scramble_fighters_jtl_92(state, source_ci, target_id, event_ctx):
    """Create 8 ready TIE Fighter tokens that can't attack bases this phase.

    ``_create_token_units(enters_ready=True)`` is the existing "create N and ready
    them" primitive (On the Doorstep TWI_190); the base bar is the phase-scoped
    per-instance ledger ``game_memory.cannot_attack_bases_this_phase``, read at the
    same single seam (``_cannot_attack_bases``) as the printed CannotAttackBases
    marker — so the base-attack option simply never appears for these tokens while
    their unit attacks stay intact."""
    from swu.engine.actions import _create_token_units
    ps = state.player_by_id(source_ci.owner_id)
    created = _create_token_units(state, ps, "TIE Fighter", 8, enters_ready=True)
    for ci in created:
        state.game_memory.cannot_attack_bases_this_phase.add(ci.instance_id)
    return state


@card_ability("JTL", "92")
def _scramble_fighters():
    """Create 8 TIE Fighter tokens and ready them.  They can't attack bases for
    this phase."""
    return EventAbility(effects=[CustomEffect(fn=_scramble_fighters_jtl_92)])


@card_ability("JTL", "101")
def _red_leader_form_up():
    """This unit costs 1 resource less to play for each friendly Pilot unit and
    upgrade.  When a Pilot upgrade attaches to this unit: Create an X-Wing token.

    The discount is the new ``CostReduction.per_friendly_pilots`` scaling arm (the
    ``other_friendly_pilots`` StatBonus count basis without its self-exclusion —
    Red Leader is in hand when the play-cost path reads it).  The trigger is a
    plain ``WhenYouPlayCard`` observer narrowed by the existing ``trait`` /
    ``on_self`` filters — ``on_self`` is precisely "the played card is attached to
    the source unit" (Kylo Ren LOF_229), which already implies "as an upgrade".
    No ``card_type="upgrade"`` filter: a *Pilot* upgrade is usually a Piloting
    UNIT card riding a Vehicle (BB-8 JTL_145, Wingman Victor Three JTL_86), whose
    printed type is "Unit" — filtering on the type would miss the common case."""
    return [
        CostReduction(amount=1, per_friendly_pilots=True),
        TriggerAbility(
            WhenYouPlayCard(trait="Pilot", on_self=True),
            [CreateTokenUnit("X-Wing", 1)],
        ),
    ]


def _unity_of_purpose_jtl_106(state, source_ci, target_id, event_ctx):
    """For each friendly unit with a different name, give each unit you control
    +1/+1 for this phase.

    The magnitude is the number of DISTINCT names among the controller's units
    (three units named A, A, B ⇒ +2/+2), so this is a conditional-magnitude
    CustomEffect (Zeb Orellios LAW_45) rather than a fixed ModifyStats — and the
    buff is applied to every friendly unit inline, the EACH_FRIENDLY basis.  A
    board with no units yields 0 and nothing is applied."""
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import _make_modifier
    ps = state.player_by_id(source_ci.owner_id)
    units = list(ps.ground_arena) + list(ps.space_arena)
    amount = len({getattr(u.card_def, "name", None) for u in units})
    if not amount:
        return state
    for u in units:
        state.modifiers.append(_make_modifier(
            state, source_ci.instance_id, u.instance_id, amount, amount,
            Duration.THIS_PHASE))
    return state


@card_ability("JTL", "106")
def _unity_of_purpose():
    """For each friendly unit with a different name, give each unit you control
    +1/+1 for this phase."""
    return EventAbility(effects=[CustomEffect(fn=_unity_of_purpose_jtl_106)])


@card_ability("JTL", "107")
def _bunker_defender():
    """While you control a Vehicle unit, this unit gains Sentinel.

    The conditional-self-grant pattern (Hunting Nexu SHD_168): the keyword
    sanitiser strips the mis-tagged printed "Sentinel" from the card bar so this
    ability — not an always-on printed keyword — owns it.  Bunker Defender is a
    Trooper, so it can never satisfy its own Vehicle condition."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT,
                                 param="Vehicle"),
    )


@card_ability("JTL", "109")
def _jarek_yeager():
    """Piloting [2 Command] — While you control a ground unit and a space unit,
    attached unit gains Sentinel.

    ``upgrade_only=True`` is what makes this correct.  A plain
    ``ConstantAbility(target=SELF)`` is read by BOTH the attached-upgrade scan
    (which confers it on the HOST — what the card means) and the arena scan (which
    walks in-play units by (set, number) with no upgrade gate).  Jarek can also be
    played as an ordinary 2/3 ground unit, and without the flag he would hand
    HIMSELF Sentinel whenever his controller also had a space unit — a keyword the
    unit side never has.  The flag makes the arena scans skip the spec; the
    attached scans are untouched.  (The printed "Sentinel" on the card bar is the
    usual upstream mis-tag and is stripped by keyword-sanitiser rule 2, which keys
    on the conditional SELF grant regardless of this flag.)"""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_GROUND_AND_SPACE_UNIT),
        upgrade_only=True,
    )


# ── ESCALATION RESOLVED (jtl-set:15, framework session 2026-08-06) ────────────
# JTL_94 Luke Skywalker "You Still With Me?" — "If this upgrade would be defeated,
# you may instead move him to the ground arena as a unit and exhaust him."
#
# It needed no framework at all: the card is the ORIGINAL printing of J25_4, whose
# defeat-replacement (the ``WhenDefeatedAsUpgrade`` seam) landed in reprint-sweep
# batch 47.  It read as an unsolved escalation only because the sweep could not SEE
# the twin: ``reprints.face_key`` compared rules text verbatim, and JTL_94 prints
# the Piloting reminder text its two promo faces omit, so it keyed to a SINGLETON
# group — and ``find_reprints`` skips singletons, which is why ``--check`` stayed
# green with the original unplayable.  ``reprints._norm_rules`` now strips reminder
# text from the printed-face identity; JTL_94 is aliased onto J25_4 in
# ``REPRINT_ALIASES`` (with 35 further faces the same blind spot had hidden).


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:16 — Combat tricks, buffs & tempo
# (JTL_115, JTL_119, JTL_122, JTL_135, JTL_137, JTL_138, JTL_145)
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("JTL", "115")
def _clone_combat_squadron():
    """This unit gets +1/+1 for each other friendly space unit.

    A scaling SELF ``StatBonus`` over the new ``other_friendly_space_units`` count
    (the ``other_friendly_same_name`` JTL_256 shape, keyed on the arena instead of
    the name).  The squadron is itself a space unit, so the count excludes it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(1, 1, count="other_friendly_space_units")],
    )


def _resupply_carrier_jtl_119(state, source_ci, target_id, event_ctx):
    """Put the top card of your deck into play as a resource — the shared ramp
    primitive (``_resource_top_of_deck``, When Has Become Now SEC_245).  A no-op
    on an empty deck."""
    from swu.engine.actions import _resource_top_of_deck
    _resource_top_of_deck(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("JTL", "119")
def _resupply_carrier():
    """When Played: You may put the top card of your deck into play as a resource."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_resupply_carrier_jtl_119)],
        optional=True,
    )


def _all_wings_report_in_jtl_122(state, source_ci, target_id, event_ctx):
    """Exhaust up to 2 friendly space units; one X-Wing token per unit exhausted.

    A thin adapter over the existing ``exhaust_combined_cost`` decision (The
    Mandalorian JTL_210's "Exhaust up to 2 ground units" shape) with no cost
    ceiling — ``budget=None``, ``max_units=2``, ``arena="space"``,
    ``controller="friendly"`` — plus the new ``then_create_token_per_unit`` rider,
    which settles the payoff at resolve where the final count is known.  "Up to 2"
    includes 0, so the decision's own Finish action is the decline."""
    from swu.engine.actions import push_exhaust_combined_cost
    push_exhaust_combined_cost(
        state, source_ci, budget=None, max_units=2, arena="space",
        controller="friendly", then_create_token_per_unit="X-Wing")
    return state


@card_ability("JTL", "122")
def _all_wings_report_in():
    """Exhaust up to 2 friendly space units.  For each unit exhausted this way,
    create an X-Wing token."""
    return EventAbility(effects=[CustomEffect(fn=_all_wings_report_in_jtl_122)])


@card_ability("JTL", "135")
def _special_forces_tie_fighter():
    """When Played: If an opponent controls more space units than you, ready this
    unit.

    The condition gates trigger COLLECTION, so nothing is offered (and no prompt
    appears) when the opponent is not ahead in the space arena.  The count is taken
    AFTER this unit has entered play — it is in its controller's space arena by the
    time a When Played trigger fires — which is the CR reading."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(
            Condition.OPPONENT_MORE_SPACE_UNITS_THAN_CONTROLLER),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
    )


@card_ability("JTL", "137")
def _vonregs_tie_interceptor():
    """While this unit has 4 or more power, it gains Overwhelm.
    While this unit has 6 or more power, it gains Raid 1.

    Two conditional self-grants (Hunting Nexu SHD_168), so keyword-sanitiser rule 2
    strips BOTH mis-tagged printed keywords — a 3/4 with no buffs has neither.  The
    thresholds read *effective* power via ``SOURCE_POWER_MIN``, whose reentrancy
    guard is what makes a ConstantAbility gated on power safe (see the note there):
    the Raid gate measures non-attacking power, so a 5-power Interceptor cannot
    bootstrap itself to 6 off its own Raid."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Overwhelm")],
            condition=ConditionCheck(Condition.SOURCE_POWER_MIN, param=4),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Raid", 1)],
            condition=ConditionCheck(Condition.SOURCE_POWER_MIN, param=6),
        ),
    ]


@card_ability("JTL", "138")
def _decimator_of_dissidents():
    """If you dealt indirect damage this phase, this unit costs 1 resource less to
    play.  (Overwhelm is genuinely printed and stays on the card bar.)

    A plain conditional ``CostReduction`` over the new
    ``CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE`` atom, which reads the
    phase-scoped ledger fed at the single indirect-damage settle point."""
    return CostReduction(
        amount=1,
        condition=ConditionCheck(
            Condition.CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE),
    )


def _bb8_jtl_145_pay_and_ready(state, source_ci, target_id, event_ctx):
    """Pay 2 resources; if you do, ready the chosen Resistance unit.

    The "If you do" binding (Bright Hope SOR_99): cost and payoff live in ONE
    CustomEffect over the chosen target, so an unaffordable pay can never ready
    anything — and, per the Kylo Ren SHD_141 gotcha, a pay-then-buff-a-TARGET
    trigger must be a single ``CustomEffect.target`` rather than two effects."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    ps = state.player_by_id(source_ci.owner_id)
    if sum(1 for r in ps.resources if not r.exhausted) < 2:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 2)
    unit.exhausted = False
    return state


@card_ability("JTL", "145")
def _bb8_happy_beeps():
    """Piloting [1 Aggression Heroism] — When played as an upgrade: You may pay 2
    resources.  If you do, ready a Resistance unit.

    Only exhausted Resistance units are offered (readying a ready unit changes
    nothing — the "don't offer a no-op" pattern), and the trigger is collected only
    when the controller can actually pay AND has such a unit, so the "you may" is
    never a dead prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        condition=ConditionCheck(Condition.ALL_OF, param=(
            ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=2),
            ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, param="Resistance"),
        )),
        effects=[CustomEffect(
            fn=_bb8_jtl_145_pay_and_ready,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Resistance",), predicates=("exhausted",)),
        )],
        optional=True,
    )


# ── jtl-set:11 keystone — the "use that ability again" leader (framework) ─────

@card_ability("JTL", "2")
def _grand_admiral_thrawn():
    """JTL_2 — Grand Admiral Thrawn "...How Unfortunate" (Leader 4/7).

    Undeployed: "When you use a 'When Defeated' ability: You may exhaust this
    leader.  If you do, use that ability again."
    Deployed:   "When you use a 'When Defeated' ability: You may use that ability
    again.  Use this ability only once each round."

    Both sides are the SAME meta-mechanic with different prices, so both are the
    same passive ``WhenDefeatedRedo`` marker — read at the shared ability-redo
    chokepoint ``resolver._schedule_ability_redo``, which Qui-Gon Jinn's
    Aethersprite LOF_197 already used for the When Played half.  Every time this
    leader's controller *uses* a qualifying When Defeated ability, the engine
    offers an optional re-use of that same ability with fresh target choices, as an
    ordinary ``trigger_option`` (no new decision kind).  "Use" means it actually
    resolves: a mandatory When Defeated, or an *accepted* optional one — declining
    an optional one is not a use.

    The price is charged only on accept (``actions.AcceptTrigger``): the undeployed
    side exhausts him, the deployed side spends the round's single use
    (``game_memory.when_defeated_redo_used_this_round``).  The redo is only offered
    while its price is payable, so an exhausted undeployed Thrawn — or a deployed
    one who already re-used something this round — prompts for nothing.

    Excluded from "a 'When Defeated' ability", per the card's own printed rules
    note ("Any ability whose trigger starts with 'When Defeated'…"): **Bounty**,
    which is its own keyword ability and is collected by the defeated unit's
    opponent rather than by Thrawn's controller; and the ``WhenDefeatedAsUpgrade``
    defeat-*replacement* (Luke Skywalker JTL_94), whose trigger reads "If this
    upgrade would be defeated".  A leader is only ever on one side at a time, so
    the two markers never both apply."""
    return [
        WhenDefeatedRedo(cost_exhaust_source=True, undeployed_only=True),
        WhenDefeatedRedo(once_per_round=True, deployed_only=True),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:17 — Combat tricks, buffs & tempo
# (JTL_146, JTL_150, JTL_157, JTL_160, JTL_161, JTL_163, JTL_164)
# ══════════════════════════════════════════════════════════════════════════════


def _massassi_tactical_officer_jtl_146(state, source_ci, target_id, event_ctx):
    """"Attack with a Fighter unit.  It gets +2/+0 for this attack."

    A plain ``push_granted_attack`` narrowed by ``attacker_trait``, left UNGATED
    like Rio Durant JTL_15: with no ready Fighter the decision offers only
    ``DeclineGrantedAttack``, so it fizzles cleanly rather than needing a
    board-reading condition atom."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, attacker_trait="Fighter")
    return state


@card_ability("JTL", "146")
def _massassi_tactical_officer():
    """JTL_146 — Massassi Tactical Officer (Unit, Rebel, 0/4).
    "Action [Exhaust]: Attack with a Fighter unit.  It gets +2/+0 for this attack."
    """
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_massassi_tactical_officer_jtl_146)],
        title="Attack with a Fighter unit (+2/+0)",
    )


@card_ability("JTL", "150")
def _biggs_darklighter():
    """JTL_150 — Biggs Darklighter (Unit, Rebel/Pilot, 3/4; Piloting
    [1 resource Aggression Heroism]):
      "If attached unit is a Fighter, it gains Overwhelm.
       If attached unit is a Transport, it gets +0/+1.
       If attached unit is a Speeder, it gains Grit."

    Three "attached unit gains …" clauses, i.e. three
    ``ConstantAbility(target=SELF, …, condition=SOURCE_HAS_TRAIT(<Trait>))`` specs
    read off the HOST by the two attached-upgrade scans (``keywords.has_keyword``
    and ``_upgrade_self_stat_bonus``), both of which evaluate a present condition
    against that host — the Rio Durant JTL_15 "if it's a Transport" shape.

    ``upgrade_only=True`` on all three (Jarek Yeager JTL_109): unlike Rio, whose
    grants are harmless on his own unit side, these clauses are strictly about the
    *attached* unit, and the ARENA constant scans walk units by (set, number) with
    no upgrade gate — so without the flag a Biggs who ever picked up one of those
    traits (a TraitGrant) would hand HIMSELF the keyword as a unit.  The flag makes
    the arena scans skip the specs; the attached scans are untouched.

    The printed "Overwhelm" and "Grit" on the card bar are the usual upstream
    mis-tag (both are granted to the *host*, never possessed).  Biggs' ``text`` is
    empty — his whole rules box lives in ``epic_action`` — so the sanitiser's
    text-driven grant-to-others rule cannot see them; rule 2 strips both anyway,
    keying on these conditional SELF KeywordGrants regardless of ``upgrade_only``.
    """
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Overwhelm")],
            condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Fighter"),
            upgrade_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(0, 1)],
            condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Transport"),
            upgrade_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Grit")],
            condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Speeder"),
            upgrade_only=True,
        ),
    ]


def _relentless_firespray_jtl_157(state, source_ci, target_id, event_ctx):
    """Ready this unit and mark the once-each-round trigger used.

    The Toro Calican SHD_239 limiter: the marker is written by the ability's own
    CustomEffect (not at collection), so the round's single use is spent when the
    ability actually resolves."""
    source_ci.exhausted = False
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("JTL", "157")
def _relentless_firespray():
    """JTL_157 — Relentless Firespray (Unit, Transport/Underworld/Vehicle, 4/6).
    "On Attack: Ready this unit.  Use this ability only once each round."

    On Attack fires after the attacker has been exhausted to declare, so readying
    it here is exactly the printed effect: it may attack again this phase.  The
    once-each-round limiter is the shared
    ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` gate on collection plus the
    ``{instance_id}:trig`` marker written by the effect (Toro Calican SHD_239).
    Mandatory, so no decline can waste the round's use."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_relentless_firespray_jtl_157)],
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


@card_ability("JTL", "160")
def _supporting_eta_2():
    """JTL_160 — Supporting Eta-2 (Unit, Fighter/Republic/Vehicle, 2/2).
    "On Attack: You may give a ground unit +2/+0 for this phase."

    A plain optional On Attack with one targeted ``ModifyStats``.  "A ground unit"
    names no controller, so either player's ground units are eligible (the
    heuristic bot only ever buffs its own)."""
    from swu.abilities.registry import Duration, ModifyStats
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[ModifyStats(
            power=2, hp=0,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
            duration=Duration.THIS_PHASE,
        )],
    )


@card_ability("JTL", "161")
def _captain_tarkin():
    """JTL_161 — Captain Tarkin (Unit, Official/Republic, 2/5).
    "Each friendly Vehicle unit gets +1/+0 and gains Overwhelm."

    One ``ConstantAbility`` over friendly Vehicle units carrying both a
    ``StatBonus`` and a ``KeywordGrant`` — the anthem convention.  Tarkin is an
    Official, never a Vehicle, so he sits outside his own aura; his printed
    "Overwhelm" is the upstream grant-to-others mis-tag and is stripped by
    keyword-sanitiser rule 1 (the Admiral Piett SOR_079 case)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Vehicle",)),
        effects=[StatBonus(1, 0), KeywordGrant("Overwhelm")],
    )


@card_ability("JTL", "163")
def _at_dp_occupier():
    """JTL_163 — AT-DP Occupier (Unit, Imperial/Vehicle/Walker, 3/4; Overwhelm).
    "This unit costs 1 resource less to play for each damaged ground unit."

    A ``CostReduction`` on the new ``per_damaged_ground_unit`` scaling basis — the
    ground-arena narrowing of the ``damaged_units_in_play`` count (War Juggernaut
    JTL_170).  "Each damaged ground unit" names no controller, so both players'
    ground arenas count; the play path floors the final cost at 0 and the same
    single site drives both affordability and the resources actually exhausted."""
    return CostReduction(amount=1, per_damaged_ground_unit=True)


def _cham_syndulla_jtl_164(state, source_ci, target_id, event_ctx):
    """Put the top card of your deck into play as a resource — the shared ramp
    primitive ``_resource_top_of_deck`` (Resupply Carrier JTL_119).  A no-op on an
    empty deck."""
    from swu.engine.actions import _resource_top_of_deck
    _resource_top_of_deck(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("JTL", "164")
def _cham_syndulla():
    """JTL_164 — Cham Syndulla (Unit, Rebel/Twi'lek, 5/4).
    "When Played: If an opponent controls more resources than you, you may put the
    top card of your deck into play as a resource."

    Resupply Carrier JTL_119's optional ramp trigger plus the new
    ``OPPONENT_MORE_RESOURCES_THAN_CONTROLLER`` gate on collection, so a Cham
    played while level or ahead on resources prompts for nothing at all."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(
            Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER),
        effects=[CustomEffect(fn=_cham_syndulla_jtl_164)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:18 — Combat tricks, buffs & tempo
# (JTL_178, JTL_179, JTL_182, JTL_188, JTL_192, JTL_193, JTL_195)
# ══════════════════════════════════════════════════════════════════════════════


def _ready_ci_jtl(state, ci) -> bool:
    """Ready ``ci`` honouring the two standing blocks the ``ReadyCard`` effect arm
    honours (``cannot_ready_this_round``, ``_ready_forbidden``) and feeding the
    ready ledger.  Returns whether it actually readied."""
    from swu.engine.actions import _ready_forbidden, note_unit_readied
    if getattr(ci, "cannot_ready_this_round", False) or _ready_forbidden(state, ci):
        return False
    note_unit_readied(state, ci)
    ci.exhausted = False
    return True


def _face_off_ready_enemy(state, source_ci, target_id, event_ctx):
    """Ready the chosen enemy unit and record it (plus its arena), arming the
    friendly half's ``requires_prior_target`` + ``same_arena_as_event`` gates — the
    Fight Fire With Fire JTL_173 shape.  Declining ("you may") records nothing, so
    the second half fizzles with no prompt, which is exactly "If you do"."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _ready_ci_jtl(state, res[1])
    event_ctx["prior_target_id"] = target_id
    event_ctx["same_arena"] = ("space" if res[1].zone == Zone.SPACE_ARENA
                               else "ground")
    return state


@card_ability("JTL", "178")
def _face_off():
    """JTL_178 — Face Off (Event, Tactic, 3): "If no player has taken the initiative
    this phase, you may ready an enemy unit.  If you do, ready a friendly unit in
    the same arena."

    The opening clause is a BOARD gate expressed as a candidate predicate rather
    than a ``ConditionalEffect`` (an ``EventAbility`` has no ``condition`` field,
    and a ConditionalEffect cannot carry a targeted sub-effect): with the
    initiative already claimed the new ``no_initiative_claimed`` predicate admits
    nothing, so the event fizzles with no prompt at all — the
    ``fewer_units_than_prior_target_controller`` TWI_55 shape.

    Candidates on both halves are narrowed to EXHAUSTED units so neither prompt is
    a guaranteed no-op, which also makes "If you do" exact."""
    return EventAbility(effects=[
        CustomEffect(fn=_face_off_ready_enemy,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       optional=True,
                                       predicates=("exhausted",
                                                   "no_initiative_claimed"))),
        ReadyCard(TargetSpec(controller="friendly", kind="unit",
                             predicates=("exhausted", "requires_prior_target",
                                         "same_arena_as_event"))),
    ])


@card_ability("JTL", "179")
def _koiogran_turn():
    """JTL_179 — Koiogran Turn (Event, Tactic, 3): "Ready a Fighter or Transport
    unit with 6 or less power."

    A plain targeted ``ReadyCard``.  The trait DISJUNCTION is the new
    ``fighter_or_transport`` predicate (a single ``TargetSpec.traits`` tuple
    requires ALL of them), the cap is ``power_max`` (effective power), and
    ``exhausted`` keeps the prompt off already-ready units.  No controller is
    named, so either player's units qualify as printed."""
    return EventAbility(effects=[
        ReadyCard(TargetSpec(controller="any", kind="unit", power_max=6,
                             predicates=("fighter_or_transport", "exhausted"))),
    ])


@card_ability("JTL", "182")
def _rampart():
    """JTL_182 — Rampart (Unit, Transport/Underworld/Vehicle, 3/3): "This unit
    doesn't ready during the regroup phase unless its power is 4 or more."

    The ``ReadyRestriction`` marker (Leia Organa LOF_98) — which forbids WHILE its
    condition holds, so "unless power ≥ 4" is the new ``SOURCE_POWER_MAX`` ceiling
    at 3 — narrowed by the new ``regroup_only`` flag, because the card bars only
    the regroup ready step and says nothing about a card readying it mid-action.
    Re-evaluated at every regroup, so an upgrade that pushes Rampart to 4 power
    lifts the block on its own."""
    return ReadyRestriction(
        condition=ConditionCheck(Condition.SOURCE_POWER_MAX, param=3),
        regroup_only=True,
    )


def _moff_gideon_jtl_188_tax(state, source_ci, target_id, event_ctx):
    """"Each unit that opponent plays this phase costs 1 resource more" — record the
    surcharge against the damaged player in the phase-scoped
    ``unit_play_tax_this_phase`` ledger, read at the single play-cost surcharge site
    ``_opponent_play_tax``.

    A ledger rather than a marker on Gideon, because the tax is bought by an event
    that has already happened: it must survive Gideon leaving play, and two hits in
    one phase must stack."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    tax = state.game_memory.unit_play_tax_this_phase
    tax[opp.player_id] = int(tax.get(opp.player_id, 0) or 0) + 1
    return state


@card_ability("JTL", "188")
def _moff_gideon_jtl_188():
    """JTL_188 — Moff Gideon (Unit, Imperial/Official, 5/4): "When this unit deals
    combat damage to an opponent's base: Each unit that opponent plays this phase
    costs 1 resource more."

    ``WhenDealsCombatDamageToBase`` (Ketsu Onyo SHD_147) fires only on a direct base
    attack, and in two-player the base attacked is that single opponent's."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[CustomEffect(fn=_moff_gideon_jtl_188_tax)],
    )


def _in_debt_to_crimson_dawn_jtl_192(state, source_ci, target_id, event_ctx):
    """"Exhaust it unless its controller pays 2 resources" — the single-unit
    ``pay_or_exhaust`` decision addressed to the host's controller (Look the Other
    Way SHD_227 with ``pay_amount=2``).  ``source_ci`` is the HOST: the spec rides
    in a ``GrantedAbility``, which matches and resolves from the attached unit."""
    from swu.engine.actions import push_pay_or_exhaust
    push_pay_or_exhaust(state, source_ci.instance_id, 2)
    return state


@card_ability("JTL", "192")
def _in_debt_to_crimson_dawn():
    """JTL_192 — In Debt to Crimson Dawn (Upgrade, Condition, 2): "When attached
    unit readies: Exhaust it unless its controller pays 2 resources."

    A ``GrantedAbility`` (so the HOST is the source) wrapping the new
    ``WhenUnitReadies`` observer — the ``WhenUnitHealed`` settle-drain shape, fed by
    ``actions.note_unit_readied`` at the regroup mass-ready and the ``ReadyCard``
    effect arm and drained on a clean stack, which is what lets the payoff push a
    decision from inside the regroup phase."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenUnitReadies(),
        effects=[CustomEffect(fn=_in_debt_to_crimson_dawn_jtl_192)],
    ))


def _i_have_you_now_jtl_193(state, source_ci, target_id, event_ctx):
    """"Attack with a Vehicle unit.  Prevent all damage that would be dealt to it
    during this attack."  The prevention is a decision-scoped rider: the attacker is
    only known once chosen, so ``attacker_damage_prevention`` lands a ``this_attack``
    ``damage_prevention`` modifier (``all``, NOT ``combat_only`` — "all damage",
    including an ability's) on it at the attack site."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_trait="Vehicle",
                        attacker_damage_prevention=True)
    return state


@card_ability("JTL", "193")
def _i_have_you_now():
    """JTL_193 — I Have You Now (Event, Tactic, 1)."""
    return EventAbility(effects=[CustomEffect(fn=_i_have_you_now_jtl_193)])


def _cat_and_mouse_exhaust(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen enemy unit and record it, its arena and its power, arming
    the friendly half's ``requires_prior_target`` / ``same_arena_as_event`` /
    ``power_le_event_threshold`` gates (the Nothing Left to Fear LAW_41 threshold on
    the Fight Fire With Fire JTL_173 chain).  Power is read BEFORE the exhaust so a
    while-ready buff cannot move the ceiling under us."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    from swu.engine.state import Zone
    _, ci = res
    event_ctx["power_le_threshold"] = compute_power(state, ci)
    ci.exhausted = True
    event_ctx["prior_target_id"] = target_id
    event_ctx["same_arena"] = ("space" if ci.zone == Zone.SPACE_ARENA else "ground")
    return state


@card_ability("JTL", "195")
def _cat_and_mouse():
    """JTL_195 — Cat and Mouse (Event, Tactic, 3): "Exhaust an enemy unit.  If you
    do, ready a friendly unit in the same arena with power equal to or less than
    that enemy unit."

    The enemy half is narrowed to READY units (exhausting an exhausted unit is the
    no-op that would still arm "if you do"), the friendly half to EXHAUSTED ones."""
    return EventAbility(effects=[
        CustomEffect(fn=_cat_and_mouse_exhaust,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("ready",))),
        ReadyCard(TargetSpec(controller="friendly", kind="unit",
                             predicates=("exhausted", "requires_prior_target",
                                         "same_arena_as_event",
                                         "power_le_event_threshold"))),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:19 — Combat tricks, buffs & tempo
# (JTL_199, JTL_202, JTL_206, JTL_211, JTL_228, JTL_231, JTL_238)
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("JTL", "199")
def _blade_squadron_b_wing():
    """JTL_199 — Blade Squadron B-Wing (Unit, Fighter/Rebel/Vehicle, 3/3): "When
    Played: If another player controls 3 or more exhausted units, give a Shield
    token to a unit."

    A plain targeted ``GiveToken`` gated on collection by the new
    ``ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS`` atom, so below the threshold the
    trigger is never collected and there is no prompt.  "A unit" names no
    controller, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(
            Condition.ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS, param=3),
        effects=[GiveToken("Shield", TargetSpec(controller="any", kind="unit"))],
    )


def _black_squadron_scout_wing_jtl_202(state, source_ci, target_id, event_ctx):
    """"You may attack with this unit.  It gets +1/+0 for this attack." —
    ``push_granted_attack`` pinned to the source (``attacker_id``), the Hotshot
    DL-44 Blaster shape."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1,
                        attacker_id=source_ci.instance_id)
    return state


@card_ability("JTL", "202")
def _black_squadron_scout_wing():
    """JTL_202 — Black Squadron Scout Wing (Unit, Fighter/Resistance/Vehicle, 4/6):
    "When you play an upgrade on this unit: You may attack with this unit.  It gets
    +1/+0 for this attack."

    ``WhenYouPlayCard(on_self=True)`` (the Kylo Ren LOF_229 observer) — deliberately
    WITHOUT ``card_type="upgrade"``: a Piloting card played as an upgrade has the
    printed type "Unit" (the Red Leader JTL_101 gotcha), and ``on_self`` already
    means "attached to the source", which no non-upgrade play can be.  The outer
    "you may" is the optional trigger; the attack itself is then mandatory, so the
    decision offers only real attacks (an exhausted Scout Wing simply has none and
    the granted attack fizzles via DeclineGrantedAttack)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(on_self=True),
        optional=True,
        effects=[CustomEffect(fn=_black_squadron_scout_wing_jtl_202)],
    )


def _fly_casual_jtl_206(state, source_ci, target_id, event_ctx):
    """"Ready a Vehicle unit.  It can't attack bases for this phase."

    ONE targeted CustomEffect carrying both clauses (the Kylo Ren SHD_141 shape) —
    splitting them would prompt twice and could apply the bar to a different unit.
    The base bar is the phase-scoped per-instance ledger
    ``game_memory.cannot_attack_bases_this_phase`` (Scramble Fighters JTL_92), read
    at the same ``_cannot_attack_bases`` seam as the printed marker; it applies even
    when a standing restriction stopped the ready, as printed."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ready_ci_jtl(state, res[1])
    state.game_memory.cannot_attack_bases_this_phase.add(target_id)
    return state


@card_ability("JTL", "206")
def _fly_casual():
    """JTL_206 — Fly Casual (Event, Trick, 1)."""
    return EventAbility(effects=[
        CustomEffect(fn=_fly_casual_jtl_206,
                     target=TargetSpec(controller="any", kind="unit",
                                       traits=("Vehicle",),
                                       predicates=("exhausted",))),
    ])


@card_ability("JTL", "211")
def _independent_smuggler():
    """JTL_211 — Independent Smuggler (Unit, Pilot/Underworld, 1/1; Raid 1, Piloting
    [1 resource Cunning]): "Attached unit gains Raid 1."

    The "attached unit gains <keyword N>" convention with a VALUE (Hera Syndulla
    JTL_45): the keyword layer's attached-upgrade scan has a numeric sibling
    (``keywords.keyword_value``), so this confers Raid *1*.  Unconditional, so the
    sanitiser leaves the printed Raid 1 on the unit side alone — which is right, the
    unit really has it — and re-granting it there is a no-op."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 1)],
    )


def _barrel_roll_jtl_228(state, source_ci, target_id, event_ctx):
    """"Attack with a space unit."  Mandatory and ungated (Rio Durant JTL_15): with
    no ready space unit the decision offers only DeclineGrantedAttack."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_arena="space")
    return state


@card_ability("JTL", "228")
def _barrel_roll():
    """JTL_228 — Barrel Roll (Event, Tactic, 1): "Attack with a space unit.  After
    completing this attack, you may exhaust a space unit."

    "After completing this attack" is the SEPARATE SINGLE-EFFECT ABILITIES pattern
    (Sabine's Masterpiece JTL_250) plus LIFO, not a rider on
    ``push_granted_attack``.  The two clauses CANNOT be two effects of one ability:
    the ``resolve_effects`` walker consumes the later targeted effect's choice at
    the current ``effect_idx`` (the Mandalorian SHD_18 wart), so the exhaust would
    be picked before the attack was even declared.

    Registered as two abilities, ``_resolve_event_ability`` walks them in order:
    the EXHAUST (ability 0, targeted) pushes its ``resolve_effects`` decision, then
    the ATTACK (ability 1, a lone no-target CustomEffect) resolves inline and pushes
    the ``granted_attack`` ON TOP — so the attack fully resolves first and the
    exhaust choice is offered afterwards, exactly as printed.

    The exhaust is narrowed to READY space units, so the "you may" (the optional
    TargetSpec's decline) is never a prompt for a no-op."""
    return [
        EventAbility(effects=[
            ExhaustCard(TargetSpec(controller="any", kind="unit", arena="space",
                                   optional=True, predicates=("ready",))),
        ]),
        EventAbility(effects=[CustomEffect(fn=_barrel_roll_jtl_228)]),
    ]


def _punch_it_jtl_231(state, source_ci, target_id, event_ctx):
    """"Attack with a Vehicle unit.  It gets +2/+0 for this attack." — plain
    ``push_granted_attack`` narrowed by ``attacker_trait``."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2, attacker_trait="Vehicle")
    return state


@card_ability("JTL", "231")
def _punch_it():
    """JTL_231 — Punch It (Event, Tactic, 1)."""
    return EventAbility(effects=[CustomEffect(fn=_punch_it_jtl_231)])


def _sith_trooper_jtl_238(state, source_ci, target_id, event_ctx):
    """"+1/+0 for this attack for each damaged unit the defending player controls."

    A conditional-MAGNITUDE buff (Zeb Orellios LAW_45): the count is read at
    resolution, so a single ``ModifyStats`` cannot express it.  In two-player the
    defending player IS the source's opponent, whichever unit (or base) is being
    attacked.  A count of 0 applies nothing."""
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import _make_modifier
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    amount = sum(1 for u in opp.ground_arena + opp.space_arena if u.damage > 0)
    if not amount:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, source_ci.instance_id, amount, 0,
        Duration.THIS_ATTACK))
    return state


@card_ability("JTL", "238")
def _sith_trooper():
    """JTL_238 — Sith Trooper (Unit, First Order/Sith/Trooper, 3/3): "On Attack:
    This unit gets +1/+0 for this attack for each damaged unit the defending player
    controls." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_sith_trooper_jtl_238)],
    )


# ── Group jtl-set:20 — Combat tricks, buffs & tempo ───────────────────────────


@card_ability("JTL", "247")
def _resistance_x_wing():
    """JTL_247 — Resistance X-Wing (Unit, Fighter/Resistance/Vehicle, 2/2):
    "While this unit has a Pilot on it, it gets +1/+1."

    Pure reuse of ``Condition.SOURCE_ATTACHED_TRAIT_UPGRADES_MIN`` (General
    Grievous TWI_34's "4 or more Lightsaber upgrades") at ``("Pilot", 1)``, which
    is exactly "has a Pilot on it": it counts attached upgrades carrying the Pilot
    trait, so a Piloting *unit* riding as a Pilot and a LEADER deployed as an
    upgrade both count (both carry Pilot on their card_def), while a
    Shield/Experience token does not.  No ``upgrade_only`` — this card is the
    Vehicle, never the pilot, so the arena scans are the only readers."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(1, 1)],
        condition=ConditionCheck(Condition.SOURCE_ATTACHED_TRAIT_UPGRADES_MIN,
                                 param=("Pilot", 1)),
    )


@card_ability("JTL", "253")
def _coordinated_front():
    """JTL_253 — Coordinated Front (Event, Plan, 2): "You may give a ground unit
    +2/+2 for this phase.  You may give a space unit +2/+2 for this phase."

    Two independent "you may" clauses, each with its own target choice = the
    SEPARATE SINGLE-EFFECT ABILITIES pattern (Sabine's Masterpiece JTL_250): as
    two effects of ONE ability the ``resolve_effects`` walker would consume the
    later clause's choice at the earlier ``effect_idx`` (the Mandalorian SHD_18
    wart).  ``optional`` on each TargetSpec is the printed "may", and
    ``_resolve_event_ability`` walks the abilities in order so the SPACE prompt
    (ability 1, pushed last) resolves first — the clauses are independent, so the
    order the player is asked in is immaterial."""
    from swu.abilities.registry import Duration, ModifyStats
    return [
        EventAbility(effects=[
            ModifyStats(2, 2, TargetSpec(controller="any", kind="unit",
                                         arena="ground", optional=True),
                        Duration.THIS_PHASE),
        ]),
        EventAbility(effects=[
            ModifyStats(2, 2, TargetSpec(controller="any", kind="unit",
                                         arena="space", optional=True),
                        Duration.THIS_PHASE),
        ]),
    ]


@card_ability("JTL", "257")
def _flanking_fang_fighter():
    """JTL_257 — Flanking Fang Fighter (Unit, Fighter/Mandalorian/Vehicle, 2/3):
    "While you control another Fighter unit, this unit gains Raid 2."

    The conditional self-grant (Hunting Nexu SHD_168): a SELF ``KeywordGrant``
    read passively by ``has_keyword``/``keyword_value``, gated by the existing
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` atom (which already excludes the source).
    Its printed keyword bar is empty in the data (nothing for sanitiser rule 2 to
    strip), so the grant is the card's only source of Raid — a lone Fang Fighter
    really lacks it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 param="Fighter"),
    )


def _attack_run_jtl_261(state, source_ci, target_id, event_ctx):
    """"Attack with 2 space units (one at a time)."

    ``repeat`` + ``repeat_max=2`` (Headhunting SHD_145): each resolved attack
    re-pushes the decision with the attacker added to ``already_attacked``, and the
    re-push stops after the second.  Mandatory (no ``optional``), so a decline is
    offered only when nothing can attack — one lone space unit therefore attacks
    once and the second half fizzles, as printed."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, attacker_arena="space",
                        repeat=True, repeat_max=2)
    return state


@card_ability("JTL", "261")
def _attack_run():
    """JTL_261 — Attack Run (Event, Tactic, 1)."""
    return EventAbility(effects=[CustomEffect(fn=_attack_run_jtl_261)])


@card_ability("JTL", "262")
def _evasive_maneuvers():
    """JTL_262 — Evasive Maneuvers (Event, Trick, 2): "Exhaust a unit."

    Mandatory targeted ``ExhaustCard`` over either player's units, narrowed to
    READY ones so the choice is never a no-op (Grim Valor JTL_73's shape without
    the "you may")."""
    return EventAbility(effects=[
        ExhaustCard(TargetSpec(controller="any", kind="unit",
                               predicates=("ready",))),
    ])


# ── Group jtl-set:21 — Miscellaneous abilities ────────────────────────────────


@card_ability("JTL", "6")
def _darth_vader_jtl_6():
    """JTL_6 — Darth Vader, Victor Squadron Leader (Leader, Force/Imperial/Sith/
    Pilot, 5/6; +5/+5 as a Pilot upgrade).

    * **Action [Exhaust]** "If you attacked with a non-token Vehicle unit this
      phase, create a TIE Fighter token."  A ``CreateTokenUnit`` behind the new
      ``CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE`` gate — the non-token
      filter is the whole point of the clause, since Vader's own TIE tokens are
      Vehicles and would otherwise re-arm the ability every round.  Not scoped to
      either side (the JTL_9 Boba Fett convention), so it is available undeployed
      and as a deployed unit; a bare ``ActivatedAbility`` is never enumerated from
      an attached upgrade, so his Pilot form correctly loses it for free.
    * **"When deployed as an upgrade: Create 2 TIE Fighter tokens."** — the
      ``WhenDeployed(via_pilot_leader=True)`` trigger, fired only on the
      leader-as-upgrade path (Boba Fett JTL_9).
    * "Attached unit is a leader unit" needs no spec (``resolver._is_leader_unit``
      counts any unit carrying a Leader pilot), and the Epic Action's "choose one:
      deploy / deploy as an upgrade" is read straight off the ``epic_action`` text
      by ``actions._leader_can_deploy_as_upgrade``."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CreateTokenUnit("TIE Fighter", count=1)],
            title="Create a TIE Fighter token",
            condition=ConditionCheck(
                Condition.CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE,
                param="Vehicle"),
        ),
        TriggerAbility(
            trigger=WhenDeployed(via_pilot_leader=True),
            effects=[CreateTokenUnit("TIE Fighter", count=2)],
        ),
    ]


def _poe_jtl_13_flip_onto_vehicle(state, source_ci, target_id, event_ctx):
    """"Flip this leader and attach him as an upgrade to a friendly Vehicle unit
    without a Pilot on it."

    The Epic Action's relocation at a printed price — so it reuses the very body
    ``DeployLeaderAsUpgrade`` uses (``actions.attach_leader_as_pilot_upgrade``):
    out of the base zone, onto the host, ``LeaderDeployed`` with
    ``via_pilot_leader``.  ``epic_action_spent`` is set there, which is what stops
    his own "Epic Action: deploy this leader (as a unit)" being offered afterwards
    — he is already flipped."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, host = res
    ps = state.player_by_id(source_ci.owner_id)
    if not any(c is source_ci for c in ps.base_zone):
        return state
    from swu.engine.actions import attach_leader_as_pilot_upgrade
    return attach_leader_as_pilot_upgrade(state, ps, source_ci, host)


def _poe_jtl_13_move_upgrade(state, source_ci, target_id, event_ctx):
    """Upgrade side: "Action [1 resource]: Attach this upgrade to a friendly
    Vehicle unit without a Pilot on it."

    A granted ``ActivatedAbility`` resolves FROM THE HOST (Heroic Resolve
    SHD_155), so ``source_ci`` is the Vehicle Poe is currently riding and Poe
    himself is the Leader sitting in its ``attached_upgrades``.  Relocating him is
    then the ordinary ``_relocate_upgrade``."""
    if target_id is None or target_id == source_ci.instance_id:
        return state
    from swu.cards.models import Leader
    poe = next((u for u in source_ci.attached_upgrades
                if isinstance(u.card_def, Leader)
                and (u.card_def.set_code, u.card_def.card_number) == ("JTL", "13")),
               None)
    if poe is None:
        return state
    from swu.engine.actions import _relocate_upgrade
    _relocate_upgrade(state, poe.instance_id, source_ci.instance_id, target_id)
    return state


_JTL_13_VEHICLE_HOST = TargetSpec(controller="friendly", kind="unit",
                                  traits=("Vehicle",), predicates=("no_pilot",))


@card_ability("JTL", "13")
def _poe_dameron_jtl_13():
    """JTL_13 — Poe Dameron, I Can Fly Anything (Leader, Resistance/Pilot, 4/6;
    +2/+1 as a Pilot upgrade).

    * **Undeployed** "Action [1 resource, Exhaust]: Flip this leader and attach him
      as an upgrade to a friendly Vehicle unit without a Pilot on it."  A cheap
      alternative to his Epic Action, so the effect is the shared leader-as-Pilot
      relocation rather than a new path.  ``undeployed_only`` (he can only flip
      once) and one targeted ``CustomEffect`` over the ``no_pilot`` predicate
      (Commandeer JTL_235), which is exactly what the engine's own
      ``_eligible_leader_upgrade_targets`` admits.
    * **As an upgrade** "Action [1 resource]: Attach this upgrade to a friendly
      Vehicle unit without a Pilot on it.  Use this ability only once each round."
      A ``GrantedAbility(ActivatedAbility(once_per_round=True))`` — the wrapper is
      what makes ``legal_actions`` enumerate it from the host's attached upgrades
      at all (a bare ActivatedAbility is only scanned on arena units).
    * The Epic Action ("deploy this leader (as a unit)") is the engine's own
      ``DeployLeader``; his ``epic_action`` text says nothing about an upgrade, so
      ``_leader_can_deploy_as_upgrade`` correctly does NOT offer that mode."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_poe_jtl_13_flip_onto_vehicle,
                                  target=_JTL_13_VEHICLE_HOST)],
            title="Flip Poe onto a Vehicle",
            undeployed_only=True,
        ),
        GrantedAbility(ActivatedAbility(
            costs=[PayResources(1)],
            effects=[CustomEffect(fn=_poe_jtl_13_move_upgrade,
                                  target=_JTL_13_VEHICLE_HOST)],
            title="Move Poe to another Vehicle",
            once_per_round=True,
        )),
    ]


def _kazuda_jtl_18_suppress_one(state, source_ci, target_id, event_ctx):
    """"A friendly unit loses all abilities for this round." — the unified
    ability-suppression read-layer flag (Mind Trick LOF_202), which is lifted at
    the round rollover, so "for this round" needs no new ledger."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    res[1].abilities_suppressed = True
    return state


def _kazuda_jtl_18_suppress_any(state, source_ci, target_id, event_ctx):
    """"Choose any number of friendly units.  They lose all abilities for this
    round."

    The select-up-to-N loop (``select_token``) in its new ``suppress_abilities``
    mode; "any number" is the cap set to however many friendly units are in play,
    so the decision can take all of them or, via Finish, none.  ``source_ci`` is
    the ability's resolving card — Kazuda himself when deployed, the HOST when the
    ability is the one he grants as an upgrade — and either way the controller is
    the same player, which is who "friendly" means."""
    from swu.engine.actions import push_select_token
    ps = state.player_by_id(source_ci.owner_id)
    count = len(ps.ground_arena) + len(ps.space_arena)
    if count <= 0:
        return state
    push_select_token(state, source_ci, token_type=None, max_targets=count,
                      controller="friendly", suppress_abilities=True)
    return state


@card_ability("JTL", "18")
def _kazuda_xiono_jtl_18():
    """JTL_18 — Kazuda Xiono, Best Pilot in the Galaxy (Leader, Resistance/Pilot,
    2/5; +3/+3 as a Pilot upgrade).

    * **Undeployed** "Action [Exhaust]: A friendly unit loses all abilities for this
      round.  Take an extra action after this one."  A targeted ``CustomEffect``
      onto the suppression flag, plus the new ``ActivatedAbility.extra_action`` —
      the seat is kept instead of handed over, so the ability really is free
      tempo-wise.  With no friendly unit in play the effect fizzles and the extra
      action still stands.
    * **Deployed** "On Attack: Choose any number of friendly units.  They lose all
      abilities for this round." — ``push_select_token(suppress_abilities=True)``.
    * **As an upgrade** the same On Attack, wrapped in a ``GrantedAbility`` so it
      matches and resolves with the HOST as source ("Attached unit … gains: …");
      "attached unit is a leader unit" needs no spec.

    Losing abilities is not always a drawback (a friendly unit's own When Defeated
    or a costly constant can be worth switching off), which is why both halves are
    real player choices rather than an optimal-play collapse."""
    on_attack_effects = [CustomEffect(fn=_kazuda_jtl_18_suppress_any)]
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_kazuda_jtl_18_suppress_one,
                target=TargetSpec(controller="friendly", kind="unit"))],
            title="A friendly unit loses all abilities",
            undeployed_only=True,
            extra_action=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=on_attack_effects,
            deployed_only=True,
        ),
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=on_attack_effects,
        )),
    ]


@card_ability("JTL", "24")
def _data_vault_jtl_24():
    """JTL_24 — Data Vault (Base, 33 HP): "Your minimum deck size is increased by
    10 cards."

    The biggest base in the set pays for its HP in consistency.  A deckBUILDING
    rule, so it is a passive ``DeckSizeModifier`` marker read by
    ``deckrules.deck_size_for`` — the Colossus JTL_21 ``StartingHandModifier``
    pattern one seam over.  No trigger, no decision, nothing at all during a
    game."""
    return DeckSizeModifier(amount=10)


@card_ability("JTL", "25")
def _thermal_oscillator_jtl_25():
    """JTL_25 — Thermal Oscillator (Base, 27 HP): "Your minimum deck size is
    decreased by 5 cards."

    The mirror of Data Vault: a small base that buys consistency.  Same
    ``DeckSizeModifier`` marker with a negative amount."""
    return DeckSizeModifier(amount=-5)


@card_ability("JTL", "35")
def _tam_ryvora_jtl_35():
    """JTL_35 — Tam Ryvora, Searching For Purpose (Unit, First Order/Pilot, 2/5;
    Piloting [2 Vigilance Villainy], +2/+2): "Attached unit gains: 'On Attack: Give
    an enemy unit in this arena −1/−1 for this phase.'"

    The plain "attached unit gains: '<trigger>'" convention — a ``GrantedAbility``
    so the trigger matches and resolves with the HOST as source (Armed to the Teeth
    SHD_175), which also means "in this arena" is the HOST's arena.  The predicate
    is therefore ``same_arena_as_source`` (Major Vonreg JTL_11's granted On Attack),
    NOT ``same_arena_as_host`` — the latter reads ``event_ctx["attached_to_id"]``,
    which only the upgrade-PLAY path threads, and the source here already IS the
    host.  A negative ``ModifyStats`` is the debuff; her own unit side prints no
    ability, so nothing leaks there."""
    from swu.abilities.registry import Duration, ModifyStats
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(-1, -1, TargetSpec(
            controller="enemy", kind="unit",
            predicates=("same_arena_as_source",)), Duration.THIS_PHASE)],
    ))


def _corvus_jtl_38_attach_pilot(state, source_ci, target_id, event_ctx):
    """"You may attach a friendly Pilot unit or upgrade to this unit.  (Defeat all
    upgrades on that Pilot and remove all damage from it.)"

    One choice over two pools (the new ``unit_or_unit_upgrade`` kind), so the fn
    dispatches on where the chosen Pilot actually sits:

    * standing in an arena → ``_attach_unit_as_pilot``, which already performs the
      printed reminder verbatim (sheds its upgrades, clears its damage and the
      modifiers that targeted it as a unit) — the Poe JTLP_6 relocation;
    * already riding another Vehicle → the ordinary ``_relocate_upgrade`` (an
      upgrade has no upgrades or damage of its own, so the reminder is moot).
    """
    if target_id is None or target_id == source_ci.instance_id:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, pilot = res
    from swu.engine.actions import _attach_unit_as_pilot, _relocate_upgrade
    if any(u is pilot for u in ps.ground_arena + ps.space_arena):
        _attach_unit_as_pilot(state, target_id, source_ci.instance_id)
        return state
    host = next((u for u in ps.ground_arena + ps.space_arena
                 if any(a is pilot for a in u.attached_upgrades)), None)
    if host is None or host.instance_id == source_ci.instance_id:
        return state
    _relocate_upgrade(state, target_id, host.instance_id, source_ci.instance_id)
    return state


@card_ability("JTL", "38")
def _corvus_jtl_38():
    """JTL_38 — Corvus, Inferno Squadron Raider (Unit, Imperial/Vehicle/Capital
    Ship, 4/5; Restore 2): "When Played: You may attach a friendly Pilot unit or
    upgrade to this unit."

    An **optional** ``WhenPlayed`` with one targeted ``CustomEffect``.  The target
    is the printed disjunction — a friendly Pilot standing in an arena OR one
    already riding another Vehicle — which no existing ``kind`` covered, hence the
    small ``unit_or_unit_upgrade`` union.  The optional trigger auto-declines when
    the controller has no Pilot anywhere, and Restore 2 is the keyword layer."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_corvus_jtl_38_attach_pilot,
            target=TargetSpec(controller="friendly", kind="unit_or_unit_upgrade",
                              traits=("Pilot",)))],
        optional=True,
    )


# ── Group jtl-set:22 — Miscellaneous abilities ────────────────────────────────

def _chimaera_jtl_39_use_when_defeated(state, source_ci, target_id, event_ctx):
    """Resolve the chosen friendly unit's "When Defeated" ability *without*
    defeating it (Chimaera JTL_39).

    The chosen unit is the SOURCE of that ability, so this pushes an ordinary
    ``resolve_effects`` decision for it — exactly what ``AcceptTrigger`` pushes
    when an optional trigger is accepted — and the normal machinery then walks the
    ability's effects and prompts for its targets.  ``ability_redo`` is stamped on
    the event context so a re-use cannot itself arm another (the
    ``_schedule_ability_redo`` convention).  Cards with more than one "When
    Defeated" ability are vanishingly rare; the first registered one is used.
    """
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, ci = res
    from swu.abilities.resolver import _when_defeated_ability_indices
    idxs = _when_defeated_ability_indices(state, ci)
    if not idxs:
        return state
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    controller_id = source_ci.owner_id
    owner_idx = state.player_index(controller_id)
    state.pending_decisions.append(PendingDecision(
        deciding_player_id=controller_id,
        kind="resolve_effects",
        context={
            "set_code": ci.card_def.set_code,
            "card_number": ci.card_def.card_number,
            "ability_idx": idxs[0],
            "source_id": ci.instance_id,
            "effect_idx": 0,
            "resolved_targets": {},
            "event_ctx": {"ability_redo": True},
            "after_all_player_idx": 1 - owner_idx,
        },
        after_resolve_player_index=1 - owner_idx,
    ))
    state.active_player_index = owner_idx
    state.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="resolve_effects"))
    return state


@card_ability("JTL", "39")
def _chimaera_jtl_39():
    """JTL_39 — Chimaera (Unit, Capital Ship/Imperial/Vehicle, 5/6): "When Played:
    You may use a 'When Defeated' ability on another friendly unit.  When Defeated:
    Create 2 TIE Fighter tokens."

    Two abilities.  The When Played is an **optional** trigger whose single
    targeted ``CustomEffect`` picks another friendly unit that actually has a "When
    Defeated" ability — the new ``has_when_defeated_ability`` predicate, which
    applies the same two carve-outs as the ability-redo chokepoint (a Bounty is the
    OPPONENT's ability, and ``WhenDefeatedAsUpgrade`` is a defeat replacement), per
    the card's own printed rules note.  With no such unit on the board the optional
    trigger has no legal target and is never offered.  The When Defeated is a plain
    ``CreateTokenUnit`` — and is itself a legal target for another Chimaera."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(
                fn=_chimaera_jtl_39_use_when_defeated,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("not_self",
                                              "has_when_defeated_ability")))],
            optional=True,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CreateTokenUnit("TIE Fighter", count=2)],
        ),
    ]


def _yularen_jtl_47_choose(state, source_ci, target_id, event_ctx):
    """Push the four-way "choose a keyword" modal (Admiral Yularen JTL_47).

    All four modes are fungible (nothing is targeted) and always available, so the
    controller simply names one; ``_resolve_modal_mode`` records it in
    ``game_memory.chosen_keywords`` against Yularen's instance id."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["choose_keyword_grit", "choose_keyword_restore_1",
                                  "choose_keyword_sentinel", "choose_keyword_shielded"])
    return state


@card_ability("JTL", "47")
def _admiral_yularen_jtl_47():
    """JTL_47 — Admiral Yularen (Unit, Official/Republic, 1/5): "When Played: Choose
    Grit, Restore 1, Sentinel, or Shielded.  While this unit is in play, each
    friendly Vehicle unit gains the chosen keyword."

    A mandatory ``WhenPlayed`` ``CustomEffect`` pushes a four-mode ``push_modal``
    whose only job is to RECORD the pick, plus FOUR parallel ``ConstantAbility``
    auras — one per choosable keyword — each gated on
    ``Condition.SOURCE_CHOSEN_KEYWORD``, so exactly the chosen one is live.  Making
    them constants (rather than modifiers applied once) gets the printed duration
    for free in both directions: the grant covers Vehicles played *later* and lapses
    the moment Yularen leaves play, because the constant scans only cards in play.
    Yularen's own printed bar is empty — the API tags him with all four choosable
    keywords, stripped by the new sanitiser rule 7 (which keys on this very
    condition atom)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_yularen_jtl_47_choose)],
        ),
        *[ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit", traits=("Vehicle",)),
            effects=[KeywordGrant(kw, value)],
            condition=ConditionCheck(Condition.SOURCE_CHOSEN_KEYWORD, param=kw),
        ) for kw, value in (("Grit", 0), ("Restore", 1),
                            ("Sentinel", 0), ("Shielded", 0))],
    ]


def _l3_37_jtl_49_attach(state, source_ci, target_id, event_ctx):
    """Pull L3-37 out of her owner's discard and attach her, as a Pilot upgrade, to
    the chosen friendly Vehicle (JTL_49).

    The replacement is modelled the documented Luke J25_4 / Superlaser Technician
    SHD_85 way — an optional When Defeated trigger that finds the card already in
    the discard and relocates it — rather than a true pre-defeat interception.
    ``_defeat_unit`` has already discarded her upgrades and cleared her
    attachments, which is exactly the printed reminder; her damage is reset here."""
    if target_id is None:
        return state
    host_res = state.find_instance(target_id)
    if host_res is None:
        return state
    _, host_ci = host_res
    owner = state.player_by_id(source_ci.owner_id)
    me = next((c for c in owner.discard
               if c.instance_id == source_ci.instance_id), None)
    if me is None:
        return state  # something else already moved her
    owner.discard.remove(me)
    me.damage = 0
    me.exhausted = False
    me.face_down = False
    me.deployed = False
    me.attached_upgrades.clear()
    me.zone = host_ci.zone
    host_ci.attached_upgrades.append(me)
    from swu.engine.events import UpgradePlayed
    state.event_log.append(UpgradePlayed(
        player_id=me.owner_id,
        instance_id=me.instance_id,
        card_name=me.card_def.display_name,
        attached_to_instance_id=host_ci.instance_id,
    ))
    return state


@card_ability("JTL", "49")
def _l3_37_jtl_49():
    """JTL_49 — L3-37 (Unit, Droid/Pilot/Underworld, 3/3; Piloting): "If this unit
    would be defeated, you may instead attach her as an upgrade to a friendly
    Vehicle unit without a Pilot on it."

    An **optional** ``WhenDefeated`` whose one targeted ``CustomEffect`` recovers her
    from the discard onto the chosen Vehicle — the established stand-in for a defeat
    replacement (Luke J25_4's ``WhenDefeatedAsUpgrade``, itself the Superlaser
    Technician SHD_85 shape); the momentary discard touch is unobservable, no
    shipped card watching a unit's defeat can tell.  With no eligible host
    (``no_pilot`` on a friendly Vehicle) the trigger has no legal target and is
    never offered, so she simply dies.  Piloting is the keyword layer."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(
            fn=_l3_37_jtl_49_attach,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Vehicle",), predicates=("no_pilot",)))],
        optional=True,
    )


@card_ability("JTL", "52")
def _dqar_cargo_frigate_jtl_52():
    """JTL_52 — D'Qar Cargo Frigate (Unit, Capital Ship/Resistance/Vehicle, 6/7):
    "This unit gets –1/–0 for each damage on it."

    A SELF ``ConstantAbility`` reusing the ``target_damage`` scaling count built for
    Radiant VII JTL_226's aura — here the buffed unit and the source are the same
    card, so the count re-reads its own damage on every ``compute_power``."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=-1, hp=0, count="target_damage")],
    )


@card_ability("JTL", "54")
def _gold_leader_jtl_54():
    """JTL_54 — Gold Leader (Unit, Rebel/Transport/Vehicle, 5/5; Shielded): "While
    this unit is defending, the attacker gets –1/–0."

    Lando Calrissian LAW_108 verbatim: a ``while_defending`` ``ConstantAbility``
    whose target is the enemy attacker, contributed only while Gold Leader is the
    current combat defender.  Shielded is the keyword layer."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),
        effects=[StatBonus(power=-1, hp=0)],
        while_defending=True,
    )


def _hondo_ohnaka_jtl_56_steal(state, source_ci, target_id, event_ctx):
    """Push the take-control-and-move decision (Hondo Ohnaka JTL_56).

    Control follows the host, so "take control of a non-Pilot upgrade on a unit and
    attach it to a different eligible unit" is the board-wide ``move_upgrade``
    decision with two narrowings: destinations must be HONDO'S CONTROLLER's units
    (``dest_controller_id`` — that is the taking of control, and it lets the source
    upgrade sit on an enemy unit), and Pilot upgrades are excluded.  Hondo himself
    is an eligible destination, as his printed rules note allows."""
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci,
                      dest_controller_id=source_ci.owner_id,
                      exclude_upgrade_traits=["Pilot"])
    return state


@card_ability("JTL", "56")
def _hondo_ohnaka_jtl_56():
    """JTL_56 — Hondo Ohnaka (Unit, Underworld, 3/5; Shielded): "On Attack: You may
    take control of a non-Pilot upgrade on a unit and attach it to a different
    eligible unit."

    A thin ``CustomEffect`` adapter onto the ``move_upgrade`` decision, which
    already carries its own decline (the "you may") and is pushed only when some
    upgrade can actually be relocated.  Shielded is the keyword layer."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_hondo_ohnaka_jtl_56_steal)],
    )


@card_ability("JTL", "59")
def _corporate_defense_shuttle_jtl_59():
    """JTL_59 — Corporate Defense Shuttle (Unit, Separatist/Transport/Vehicle, 3/5):
    "This unit can't attack."

    The ``AttackRestriction`` passive marker with no condition — the unconditional
    bar (the ``ReadyRestriction`` convention), read at the single attack-enumeration
    seam, so the shuttle is dropped from the legal attackers for both ordinary and
    effect-granted attacks."""
    return AttackRestriction()


# ── Group jtl-set:23 — Miscellaneous abilities ────────────────────────────────

@card_ability("JTL", "60")
def _desperate_commando_jtl_60():
    """JTL_60 — Desperate Commando (Unit, Resistance/Trooper, 2/2): "When Defeated:
    You may give a unit –1/–1 for this phase."

    An optional ``WhenDefeated`` with one targeted ``ModifyStats`` — "a unit", so
    either player's, in either arena."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ModifyStats(power=-1, hp=-1,
                             target=TargetSpec(controller="any", kind="unit"),
                             duration=Duration.THIS_PHASE)],
        optional=True,
    )


def _close_the_shield_gate_jtl_74(state, source_ci, target_id, event_ctx):
    """Arm the one-shot base-damage prevention on the chosen base (JTL_74).

    ``game_memory.prevent_next_base_damage`` is keyed by the base's OWNER (each
    player has exactly one base) and consumed by the first damage instance that
    would reach it, at whichever site deals it — ability damage, indirect damage, a
    base attack, Overwhelm spillover, a leader's hit or the empty-deck penalty (see
    ``actions.base_damage_after_prevention``).  Cleared at the phase rollover."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, base_ci = res
    state.game_memory.prevent_next_base_damage.add(base_ci.owner_id)
    return state


@card_ability("JTL", "74")
def _close_the_shield_gate():
    """JTL_74 — Close the Shield Gate (Event, Tactic, cost 1): "Choose a base.  The
    next time damage would be dealt to it this phase, prevent that damage."

    One targeted ``CustomEffect`` arming the new one-shot prevention.  Either base
    is a legal choice (the card says "a base") — normally your own, but shielding an
    enemy base is legal and occasionally relevant."""
    return EventAbility(effects=[CustomEffect(
        fn=_close_the_shield_gate_jtl_74,
        target=TargetSpec(controller="any", kind="base"))])


@card_ability("JTL", "79")
def _out_the_airlock_jtl_79():
    """JTL_79 — Out the Airlock (Event, Tactic, cost 5): "Give a unit –5/–5 for this
    phase."

    A plain targeted ``ModifyStats``; the state-based defeat sweep finishes off any
    unit whose effective HP drops to nothing."""
    return EventAbility(effects=[ModifyStats(
        power=-5, hp=-5, target=TargetSpec(controller="any", kind="unit"),
        duration=Duration.THIS_PHASE)])


@card_ability("JTL", "82")
def _kijimi_patrollers_jtl_82():
    """JTL_82 — Kijimi Patrollers (Unit, Fighter/First Order/Vehicle, 1/1): "When
    Played: Create a TIE Fighter token"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("TIE Fighter")],
    )


def _pantoran_starship_thief_jtl_83(state, source_ci, target_id, event_ctx):
    """Pay 3 resources, ride the chosen Fighter/Transport as a Pilot, and take
    control of it (JTL_83).

    Cost and payoff live in ONE ``CustomEffect`` so an unpayable cost can never
    apply the payoff (the "If you do" binding).  Control is taken with the
    Traitorous SOR_122 control-LINKING pattern — ``change_control`` plus
    ``control_linked_to`` on the host, pointing at the thief — which is exactly the
    printed second clause: when this upgrade detaches, ``_revert_linked_control``
    hands the unit back to its owner."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, host_ci = res
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 3:
        return state
    from swu.engine.actions import (
        _exhaust_resources, _attach_unit_as_pilot, change_control)
    _exhaust_resources(ps, 3)
    _attach_unit_as_pilot(state, source_ci.instance_id, host_ci.instance_id)
    if all(u is not source_ci for u in host_ci.attached_upgrades):
        return state  # the attach could not happen (already left play)
    change_control(state, host_ci, source_ci.owner_id)
    host_ci.control_linked_to = source_ci.instance_id
    return state


@card_ability("JTL", "83")
def _pantoran_starship_thief():
    """JTL_83 — Pantoran Starship Thief (Unit, Pilot/Underworld, 2/2): "When Played:
    You may pay 3 resources.  If you do, attach this unit as an upgrade to a Fighter
    or Transport unit without a Pilot on it.  Take control of that unit."

    An optional ``WhenPlayed`` gated on the controller actually having 3 ready
    resources, so the "you may pay" is never offered when it could not be paid.  The
    target is the printed disjunction (the ``fighter_or_transport`` predicate built
    for Koiogran Turn JTL_179) plus ``no_pilot``, and either player's unit qualifies
    — stealing an enemy ship is the point of the card.  He has no Piloting keyword;
    this ability is his only way onto a Vehicle (his printed rules note)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_pantoran_starship_thief_jtl_83,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("fighter_or_transport", "no_pilot")))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=3),
    )


@card_ability("JTL", "84")
def _wingman_victor_two_jtl_84():
    """JTL_84 — Wingman Victor Two (Unit, Imperial/Pilot, 3/2; Piloting): "When
    played as an upgrade: Create a TIE Fighter token."

    The ``WhenPlayed(as_upgrade=True)`` split (Boba Fett JTL_189) — the token comes
    only when he is played via Piloting, never when he is played as a unit.  His
    rules box lives in the DB's ``epic_action`` column, beside the Piloting cost."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CreateTokenUnit("TIE Fighter")],
    )


@card_ability("JTL", "87")
def _tie_ambush_squadron_jtl_87():
    """JTL_87 — TIE Ambush Squadron (Unit, Fighter/Imperial/Vehicle, 2/3; Ambush):
    "When Played/When Defeated: Create a TIE Fighter token."

    Two triggers on one effect — the combined-trigger line is two registrations, so
    each fires exactly once at its own moment.  Ambush is the keyword layer."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CreateTokenUnit("TIE Fighter")]),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[CreateTokenUnit("TIE Fighter")]),
    ]


# ── Group jtl-set:24 — Miscellaneous abilities ────────────────────────────────

@card_ability("JTL", "99")
def _veteran_fleet_officer_jtl_99():
    """JTL_99 — Veteran Fleet Officer (Unit, Resistance, 2/1): "When Played: Create
    an X-Wing token"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("X-Wing")],
    )


@card_ability("JTL", "105")
def _the_starhawk_jtl_105():
    """JTL_105 — The Starhawk (Unit, Capital Ship/New Republic/Vehicle, 6/9;
    Ambush): "While paying costs, you pay half as many resources, rounded up."

    The new ``HalvePaidCosts`` passive marker, read through the single helper
    ``actions.resource_cost_for`` at the play-cost seam AND at every activated
    ability's ``PayResources`` check/payment — so it covers card costs and ability
    costs alike, as its printed rules note requires, and leaves non-resource costs
    (exhaust / defeat / discard) untouched.  It applies to the *determined* cost,
    i.e. after every reduction, discount and tax."""
    return HalvePaidCosts()


@card_ability("JTL", "117")
def _general_draven_jtl_117():
    """JTL_117 — General Draven (Unit, Official/Rebel, 2/5): "When Played/On Attack:
    Create an X-Wing token."

    A combined-trigger line is two registrations, so the token comes once on entry
    and once per attack."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[CreateTokenUnit("X-Wing")]),
        TriggerAbility(trigger=OnAttack(), effects=[CreateTokenUnit("X-Wing")]),
    ]


def _focus_fire_jtl_129(state, source_ci, target_id, event_ctx):
    """Each friendly Vehicle in the chosen unit's arena deals its power to it
    (JTL_129).

    Record-then-apply (Unlimited Power TWI_156): every shooter's ``compute_power``
    is snapshotted BEFORE any damage lands, so a Vehicle killed by the target's own
    death-rattle — or a buff that lapses mid-volley — cannot change how much the
    later shooters contribute."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, victim = res
    from swu.engine.actions import compute_power
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    arena = (ps.ground_arena if victim.zone.name == "GROUND_ARENA" else ps.space_arena)
    shots = [(u.card_def.display_name, compute_power(state, u))
             for u in arena if has_trait(state, u, "Vehicle")]
    from swu.abilities.resolver import _apply_deal_damage
    for name, power in shots:
        if power <= 0 or state.find_instance(target_id) is None:
            continue
        _apply_deal_damage(state, target_id, power, source_name=name)
    return state


@card_ability("JTL", "129")
def _focus_fire():
    """JTL_129 — Focus Fire (Event, Tactic, cost 4): "Choose a unit.  Each friendly
    Vehicle unit in the same arena deals damage equal to its power to that unit."

    One targeted ``CustomEffect``; "friendly" is the event's controller and "the
    same arena" is read off the chosen unit, so an enemy ground unit is shot by your
    ground Vehicles and a space unit by your space Vehicles."""
    return EventAbility(effects=[CustomEffect(
        fn=_focus_fire_jtl_129,
        target=TargetSpec(controller="any", kind="unit"))])


def _timely_reinforcements_jtl_130(state, source_ci, target_id, event_ctx):
    """Create one Sentinel X-Wing per 2 resources the opponent controls (JTL_130).

    Two players, so "choose an opponent" has exactly one answer and needs no
    prompt.  Sentinel is a this-phase ``keyword_grant`` modifier on each created
    token."""
    from swu.engine.actions import _create_token_units
    from swu.engine.state import Modifier
    idx = state.player_index(source_ci.owner_id)
    opp = state.players[1 - idx]
    ps = state.player_by_id(source_ci.owner_id)
    count = len(opp.resources) // 2
    if count <= 0:
        return state
    for tok in _create_token_units(state, ps, "X-Wing", count):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=tok.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
    return state


@card_ability("JTL", "130")
def _timely_reinforcements():
    """JTL_130 — Timely Reinforcements (Event, Tactic, cost 5): "Choose an opponent.
    For every 2 resources they control, create an X-Wing token and give it Sentinel
    for this phase."

    A single no-target ``CustomEffect``: in two-player the opponent choice has one
    answer, so there is nothing to prompt for.  Each token is created through the
    ordinary ``_create_token_units`` path (so its enter-play bus runs) and then
    picks up a this-phase Sentinel grant."""
    return EventAbility(effects=[CustomEffect(fn=_timely_reinforcements_jtl_130)])


def _turbolaser_salvo_pick_shooter(state, source_ci, target_id, event_ctx):
    """Record the friendly space unit that will fire (JTL_131), with its power
    snapshotted now so the volley is simultaneous."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    _, shooter = res
    event_ctx["salvo_power"] = compute_power(state, shooter)
    event_ctx["salvo_name"] = shooter.card_def.display_name
    event_ctx["prior_target_id"] = target_id
    return state


def _turbolaser_salvo_fire(state, source_ci, target_id, event_ctx):
    """Deal the recorded power to EVERY enemy unit in the chosen unit's arena
    (JTL_131) — the chosen enemy names the arena."""
    power = int(event_ctx.get("salvo_power") or 0)
    if target_id is None or power <= 0:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    idx = state.player_index(source_ci.owner_id)
    opp = state.players[1 - idx]
    _, marker = res
    arena = (opp.ground_arena if marker.zone.name == "GROUND_ARENA"
             else opp.space_arena)
    victim_ids = [u.instance_id for u in arena]
    from swu.abilities.resolver import _apply_deal_damage
    name = event_ctx.get("salvo_name")
    for vid in victim_ids:
        if state.find_instance(vid) is not None:
            _apply_deal_damage(state, vid, power, source_name=name)
    return state


@card_ability("JTL", "131")
def _turbolaser_salvo():
    """JTL_131 — Turbolaser Salvo (Event, Tactic, cost 7): "Choose an arena.  A
    friendly space unit deals damage equal to its power to each enemy unit in that
    arena."

    Two shared-``event_ctx`` targeted ``CustomEffect``s (the Nothing Left to Fear
    LAW_41 chain): the first picks the shooter and snapshots its power (so all the
    damage is dealt simultaneously, per the printed rules note); the second picks
    ANY enemy unit, whose arena IS the chosen arena, and hits every enemy unit
    there.  Collapsing "choose an arena" to "choose an enemy unit in it" loses
    nothing — an arena with no enemy units is a choice that does nothing — and it
    keeps both halves on the ordinary target machinery.  The event fizzles with no
    friendly space unit, or with no enemy unit anywhere."""
    return EventAbility(effects=[
        CustomEffect(fn=_turbolaser_salvo_pick_shooter,
                     target=TargetSpec(controller="friendly", kind="unit",
                                       arena="space")),
        CustomEffect(fn=_turbolaser_salvo_fire,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("requires_prior_target",))),
    ])


# ── Group jtl-set:25 — Miscellaneous abilities ────────────────────────────────

def _they_hate_that_ship_jtl_155(state, source_ci, target_id, event_ctx):
    """The opponent gets 2 ready TIE Fighters; then play a discounted Vehicle
    (JTL_155).  Both clauses in one ``CustomEffect`` so the drawback is paid even
    when nothing is playable, and so the play decision lands on top."""
    from swu.engine.actions import _create_token_units, push_play_from_hand
    idx = state.player_index(source_ci.owner_id)
    _create_token_units(state, state.players[1 - idx], "TIE Fighter", 2,
                        enters_ready=True)
    push_play_from_hand(state, source_ci, trait="Vehicle", cost_reduction=3)
    return state


@card_ability("JTL", "155")
def _they_hate_that_ship():
    """JTL_155 — They Hate That Ship (Event, Innate, cost 1): "An opponent creates 2
    TIE Fighter tokens and readies them.  Then, play a Vehicle unit from your hand.
    It costs 3 resources less."

    A single no-target ``CustomEffect``: the tokens go to the opponent (the
    ``CreateTokenUnit(player="opponent")`` reading, done inline because the payoff
    must follow in the same effect), then the existing ``play_from_hand`` decision
    offers every affordable Vehicle at 3 off.  With no affordable Vehicle the
    decision is simply not pushed — the tokens are still created, as printed."""
    return EventAbility(effects=[CustomEffect(fn=_they_hate_that_ship_jtl_155)])


def _shadow_caster_jtl_169_available(state, source_ci, event_ctx):
    """Only offer the re-use when the dead unit actually has a "When Defeated"
    ability — most units do not, and prompting for a no-op every time anything
    friendly dies would be unbearable (the "don't offer a no-op" rule)."""
    dead = event_ctx.get("defeated_ci")
    if dead is None:
        dead_id = event_ctx.get("defeated_id")
        res = state.find_instance(dead_id) if dead_id else None
        dead = res[1] if res else None
    if dead is None:
        return False
    from swu.abilities.resolver import _when_defeated_ability_indices
    return bool(_when_defeated_ability_indices(state, dead))


def _shadow_caster_jtl_169(state, source_ci, target_id, event_ctx):
    """Re-use every "When Defeated" ability of the friendly unit that just died
    (JTL_169).

    The same push-a-``resolve_effects`` shape Chimaera JTL_39 uses, once per
    registered "When Defeated" ability, pushed in REVERSE so the first-registered
    one resolves first (the stack is LIFO).  The dying unit is the source, and by
    now it sits in its owner's discard, which ``find_instance`` reaches."""
    dead_id = event_ctx.get("defeated_id")
    dead = event_ctx.get("defeated_ci")
    if dead is None and dead_id:
        res = state.find_instance(dead_id)
        dead = res[1] if res else None
    if dead is None:
        return state
    from swu.abilities.resolver import _when_defeated_ability_indices
    idxs = _when_defeated_ability_indices(state, dead)
    if not idxs:
        return state
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    controller_id = source_ci.owner_id
    owner_idx = state.player_index(controller_id)
    for ability_idx in reversed(idxs):
        state.pending_decisions.append(PendingDecision(
            deciding_player_id=controller_id,
            kind="resolve_effects",
            context={
                "set_code": dead.card_def.set_code,
                "card_number": dead.card_def.card_number,
                "ability_idx": ability_idx,
                "source_id": dead.instance_id,
                "effect_idx": 0,
                "resolved_targets": {},
                "event_ctx": {"ability_redo": True,
                              "defeated_id": dead.instance_id,
                              "defeated_ci": dead},
                "after_all_player_idx": 1 - owner_idx,
            },
            after_resolve_player_index=1 - owner_idx,
        ))
        state.event_log.append(DecisionPushed(
            deciding_player_id=controller_id, kind="resolve_effects"))
    state.active_player_index = owner_idx
    return state


@card_ability("JTL", "169")
def _shadow_caster_jtl_169_card():
    """JTL_169 — Shadow Caster (Unit, Transport/Underworld/Vehicle, 4/7): "When a
    friendly unit is defeated: You may use all of its 'When Defeated' abilities
    again."

    An optional ``WhenUnitDefeated`` observer over friendly units, whose
    ``CustomEffect`` re-resolves each of the dead unit's "When Defeated" abilities
    from the dead unit itself.  "When Defeated" means the same thing here as at the
    ability-redo chokepoint (a Bounty is the OPPONENT's ability; a
    ``WhenDefeatedAsUpgrade`` is a defeat replacement — neither counts).  Shadow
    Caster is collected only while it is in play, so it never re-uses its own."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(controller="friendly", kind="unit")),
        effects=[CustomEffect(fn=_shadow_caster_jtl_169,
                              available_fn=_shadow_caster_jtl_169_available)],
        optional=True,
    )


@card_ability("JTL", "171")
def _targeting_computer_jtl_171():
    """JTL_171 — Targeting Computer (Upgrade, Item/Modification, cost 1): "Attached
    unit gains: 'You assign all indirect damage dealt by this unit.'"

    The ``IndirectDamageSelfAssign`` marker built for Devastator JTL_143, now also
    read off a unit's attached upgrades at the same single indirect-damage decider
    seam.  DOCUMENTED SIMPLIFICATION: that read is controller-scoped (as
    Devastator's own "all indirect damage YOU deal" already made it), so while the
    Computer is on the board its controller assigns their indirect damage
    generally, not only the host's."""
    return IndirectDamageSelfAssign()


def _sidon_ithano_jtl_213(state, source_ci, target_id, event_ctx):
    """Offer to ride an ENEMY pilotless Vehicle (JTL_213) — the Poe JTLP_6
    self-attach decision pointed at the opponent's arenas."""
    from swu.engine.actions import push_attach_unit_as_pilot
    push_attach_unit_as_pilot(state, source_ci, hosts="enemy")
    return state


@card_ability("JTL", "213")
def _sidon_ithano():
    """JTL_213 — Sidon Ithano (Unit, Pilot/Underworld, 2/2): "When played as a unit:
    You may attach this unit as an upgrade to an enemy Vehicle unit without a Pilot
    on it."

    A thin adapter onto the ``pilot_self_attach`` decision, which carries its own
    decline (the "you may") and is pushed only when an eligible enemy Vehicle
    exists.  ``WhenPlayed(as_unit=True)`` keeps it off any upgrade play."""
    return TriggerAbility(
        trigger=WhenPlayed(as_unit=True),
        effects=[CustomEffect(fn=_sidon_ithano_jtl_213)],
    )


@card_ability("JTL", "229")
def _diversion_jtl_229():
    """JTL_229 — Diversion (Event, Gambit, cost 1): "Give a unit Sentinel for this
    phase."

    A plain targeted ``GrantKeyword`` — "a unit", so either player's (giving an
    enemy unit Sentinel to pull attacks is a real, if unusual, line)."""
    return EventAbility(effects=[GrantKeyword(
        "Sentinel", value=0,
        target=TargetSpec(controller="any", kind="unit"),
        duration=Duration.THIS_PHASE)])


def _jump_to_lightspeed_jtl_232(state, source_ci, target_id, event_ctx):
    """Bounce the chosen friendly space unit with its non-leader upgrades, then arm
    a free replay of a copy of it this phase (JTL_232).

    "Any number of non-leader upgrades on it" collapses to ALL of them: an upgrade
    left behind is defeated when its host leaves play, so returning every one is
    strictly better and the choice is information-free.  The free replay is a
    pending play-discount entry narrowed by CARD NAME and flagged ``free``, so it
    waives the whole aspect-adjusted cost of the next matching play and is consumed
    by it; the phase rollover clears it."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    name = getattr(unit.card_def, "name", None)
    from swu.cards.models import Leader, TokenUpgrade
    from swu.abilities.resolver import _apply_return_to_hand
    for upg in list(unit.attached_upgrades):
        if isinstance(upg.card_def, TokenUpgrade) or isinstance(upg.card_def, Leader):
            continue
        _apply_return_to_hand(state, upg.instance_id)
    _apply_return_to_hand(state, target_id)
    if name:
        state.game_memory.pending_play_discounts.append({
            "player_id": source_ci.owner_id,
            "trait": None,
            "units_only": True,
            "card_name": name,
            "free": True,
            "amount": 0,
        })
    return state


@card_ability("JTL", "232")
def _jump_to_lightspeed():
    """JTL_232 — Jump to Lightspeed (Event, Gambit, cost 2): "Return a friendly space
    unit and any number of non-leader upgrades on it to their owners' hands.  The
    next time you play a copy of that unit this phase, you may play it for free."

    One targeted ``CustomEffect`` over the two new pending-discount entry keys
    (``card_name`` + ``free``); a leader riding as a Pilot is left behind, as
    printed ("non-leader upgrades")."""
    return EventAbility(effects=[CustomEffect(
        fn=_jump_to_lightspeed_jtl_232,
        target=TargetSpec(controller="friendly", kind="unit", arena="space"))])


def _sweep_the_area_first(state, source_ci, target_id, event_ctx):
    """Return the first chosen unit and record the arena + remaining budget
    (JTL_233)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    event_ctx["same_arena"] = ("ground" if unit.zone.name == "GROUND_ARENA"
                               else "space")
    event_ctx["cost_le_threshold"] = 3 - int(getattr(unit.card_def, "cost", 0) or 0)
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_return_to_hand
    _apply_return_to_hand(state, target_id)
    return state


def _sweep_the_area_second(state, source_ci, target_id, event_ctx):
    """Return the second chosen unit (JTL_233)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_return_to_hand
    _apply_return_to_hand(state, target_id)
    return state


@card_ability("JTL", "233")
def _sweep_the_area():
    """JTL_233 — Sweep the Area (Event, Tactic, cost 3): "Return up to 2 non-leader
    units in the same arena with a combined cost 3 or less to their owners' hands."

    The Nothing Left to Fear LAW_41 shared-``event_ctx`` chain rather than a new
    select-N decision: the first (optional) target is any non-leader unit costing
    ≤3; resolving it stamps the arena and the LEFTOVER budget, so the second
    (optional) target is filtered by the existing ``same_arena_as_event`` and
    ``cost_le_event_threshold`` predicates plus ``requires_prior_target``.  "Up to
    2" is the two optional targets; declining the first fizzles the second with no
    prompt."""
    return EventAbility(effects=[
        CustomEffect(fn=_sweep_the_area_first,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader",),
                                       cost_max=3, optional=True)),
        CustomEffect(fn=_sweep_the_area_second,
                     target=TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader",
                                                   "requires_prior_target",
                                                   "same_arena_as_event",
                                                   "cost_le_event_threshold"),
                                       optional=True)),
    ])


# ═════════════════════════════════════════════════════════════════════════════
# Group ``jtl-set:26`` — Miscellaneous abilities (the last JTL group)
# ═════════════════════════════════════════════════════════════════════════════


def _shuttle_st_149_jtl_242_move_token(state, source_ci, target_id, event_ctx):
    """Push the take-control-and-move decision, narrowed to TOKEN upgrades
    (Shuttle ST-149 JTL_242).

    The Hondo Ohnaka JTL_56 shape with the complementary upgrade filter:
    ``tokens_only`` admits exactly the Shield / Experience token upgrades the
    board-wide ``kind="upgrade"`` convention normally hides, and
    ``dest_controller_id`` (the Shuttle's controller) is the taking of control, so
    the source token may sit on an ENEMY unit.  The Shuttle itself is an eligible
    destination and its own Shield an eligible source — both spelled out in the
    card's printed rules note."""
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci,
                      tokens_only=True,
                      dest_controller_id=source_ci.owner_id)
    return state


@card_ability("JTL", "242")
def _shuttle_st_149_jtl_242():
    """JTL_242 — Shuttle ST-149 (Unit, Imperial/Transport/Vehicle, 3/4; Shielded):
    "When Played/When Defeated: You may take control of a token upgrade on a unit
    and attach it to a different eligible unit."

    Two abilities over one shared ``CustomEffect`` adapter onto the ``move_upgrade``
    decision, which already carries its own decline (the "you may") and is pushed
    only when some token can actually be relocated.  Shielded is the keyword layer —
    and the Shield it hands itself on entry is immediately a legal source, which is
    the point of the card.  On the When Defeated side the Shuttle is already out of
    its arena, so it is no longer a destination, but ``source_ci.owner_id`` still
    names the right controller."""
    move = CustomEffect(fn=_shuttle_st_149_jtl_242_move_token)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[move]),
        TriggerAbility(trigger=WhenDefeated(), effects=[move]),
    ]


@card_ability("JTL", "243")
def _quasar_tie_carrier_jtl_243():
    """JTL_243 — Quasar TIE Carrier (Unit, Capital Ship/Imperial/Vehicle, 5/7):
    "On Attack: Create a TIE Fighter token."

    A plain non-targeted ``CreateTokenUnit`` on the OnAttack trigger — the Chimaera
    JTL_39 token effect at count 1."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CreateTokenUnit("TIE Fighter", count=1)],
    )


def _there_is_no_escape_suppress(state, source_ci, target_id, event_ctx):
    """Suppress one chosen unit's abilities for the round and exclude it from the
    remaining choices ("a second / a third unit" — JTL_244)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    unit.abilities_suppressed = True
    event_ctx.setdefault("excluded_target_ids", set()).add(target_id)
    return state


def _there_is_no_escape_step(first: bool):
    """One of There Is No Escape's three optional target steps."""
    preds = () if first else ("excludes_event_targets",)
    return CustomEffect(
        fn=_there_is_no_escape_suppress,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=preds, optional=True),
    )


@card_ability("JTL", "244")
def _there_is_no_escape_jtl_244():
    """JTL_244 — There Is No Escape (Event, Tactic, cost 2): "Choose up to 3 units.
    Those units lose all abilities and can't gain abilities for this round."

    Three sequential ChooseTarget steps over DISTINCT units — the Attack Pattern
    Delta SOR_106 / Unlimited Power TWI_156 ``excludes_event_targets``
    accumulating-set pattern — rather than a new select-N decision; each step is
    ``optional``, which is the printed "up to 3" (and with fewer than three units on
    the board the later steps simply have no candidates and fizzle).

    "Lose all abilities and can't gain abilities" is the Mind Trick LOF_202
    read-layer flag ``CardInstance.abilities_suppressed``: every ability-read site
    short-circuits on it, so "can't gain" falls out for free (a read stops before
    any grant is consulted).  Its scope is already exactly right for this card — the
    flag is cleared at the round rollover, i.e. "for this round"."""
    return EventAbility(effects=[
        _there_is_no_escape_step(True),
        _there_is_no_escape_step(False),
        _there_is_no_escape_step(False),
    ])


@card_ability("JTL", "252")
def _tantive_iv_jtl_252():
    """JTL_252 — Tantive IV (Unit, Capital Ship/Rebel/Vehicle, 5/7; Sentinel):
    "When Played: Create an X-Wing token."

    A plain non-targeted ``CreateTokenUnit``; Sentinel is the keyword layer."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("X-Wing", count=1)],
    )


@card_ability("JTL", "254")
def _dedicated_wingmen_jtl_254():
    """JTL_254 — Dedicated Wingmen (Event, Supply, cost 4): "Create 2 X-Wing
    tokens."

    A single non-targeted ``CreateTokenUnit`` at count 2."""
    return EventAbility(effects=[CreateTokenUnit("X-Wing", count=2)])


@card_ability("JTL", "259")
def _retrofitted_airspeeder_jtl_259():
    """JTL_259 — Retrofitted Airspeeder (Unit, Speeder/Vehicle, 3/6; Ambush): "This
    unit can attack space units." + "While attacking a space unit, this unit gets
    −1/−0."

    The ``CrossArenaAttack`` passive marker (Strafing Gunship SOR_212, mirrored:
    a GROUND unit reaching space defenders) widens the eligible-defender set at the
    attack-enumeration seam.  The debuff is a self-targeted ``ConstantAbility``
    gated by ``while_attacking_unit`` narrowed with ``while_attacking_unit_arena``,
    so it contributes only while this unit is actually attacking a unit that sits in
    the space arena — i.e. only on the attacks the first line unlocked.  Ambush is
    the keyword layer."""
    return [
        CrossArenaAttack(),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=-1, hp=0)],
            while_attacking_unit=True,
            while_attacking_unit_arena="space",
        ),
    ]


def _death_star_plans_jtl_260_steal(state, source_ci, target_id, event_ctx):
    """The attacking player takes control of Death Star Plans and attaches it to a
    unit they control (JTL_260).

    The spec rides in a ``GrantedAbility``, so ``source_ci`` is the ATTACHED UNIT
    (the defender of the attack that fired it) and the upgrade must be found among
    its attachments.  Two players, so "the attacking player" is simply the
    defender's controller's opponent.  Three narrowings on the existing
    ``move_upgrade`` decision say the rest: ``only_upgrade_id`` pins the relocation
    to THIS upgrade (the host may carry others), ``dest_controller_id`` +
    ``decider_id`` hand both the control and the choice to the attacker, and
    ``mandatory`` drops the decline — the card says "takes", not "may take".  With
    no legal destination for the attacker the decision is never pushed and the
    upgrade simply stays put."""
    upg = next((u for u in source_ci.attached_upgrades
                if getattr(u.card_def, "set_code", None) == "JTL"
                and str(getattr(u.card_def, "card_number", "")) == "260"), None)
    if upg is None:
        return state
    located = state.find_instance(source_ci.instance_id)
    host_controller = located[0].player_id if located else source_ci.owner_id
    attacker_id = next((p.player_id for p in state.players
                        if p.player_id != host_controller), None)
    if attacker_id is None:
        return state
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci,
                      only_upgrade_id=upg.instance_id,
                      dest_controller_id=attacker_id,
                      decider_id=attacker_id,
                      mandatory=True)
    return state


@card_ability("JTL", "260")
def _death_star_plans_jtl_260():
    """JTL_260 — Death Star Plans (Upgrade, Item, cost 2, 0/0): "When attached unit
    is attacked: The attacking player takes control of this upgrade and attaches it
    to a unit they control." + "Attached unit gains: 'The first unit you play each
    round costs 2 resources less.'"

    Line 1 is a ``GrantedAbility(TriggerAbility(WhenAttacked))`` — the granted
    trigger fires from the HOST, which is exactly "when attached unit is attacked",
    and lands at the same time as On Attack abilities, as printed.

    Line 2 is a ``StandingPlayDiscount`` riding on the UPGRADE: the play-cost seam
    now reads the marker off attached upgrades as well as arena units, and the
    beneficiary is the host's controller — the "attached unit gains" reading, which
    is what makes the plans worth stealing.  ``once_per_round`` is spent per
    (upgrade, beneficiary) rather than per upgrade, so the card's printed note
    "Multiple players can benefit from the discount ability in the same round"
    holds after it changes hands."""
    return [
        GrantedAbility(TriggerAbility(
            trigger=WhenAttacked(),
            effects=[CustomEffect(fn=_death_star_plans_jtl_260_steal)],
        )),
        StandingPlayDiscount(amount=2, applies_to="unit", once_per_round=True),
    ]
