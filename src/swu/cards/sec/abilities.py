"""SEC (Secrets of Power) card ability registrations.

Cards with no text or only keywords are handled by the keyword engine and are
not registered here.  This module is imported for its side effects (the
``@card_ability`` decorators populate the registry).

Group ``leia-organa:03`` — Combat tricks, buffs & tempo:
  * SEC_93 C-3PO — "Action [Exhaust, return this unit to hand]: Give a unit +2/+2
    for this phase" (the return-to-hand half of the cost is modelled as a trailing
    ReturnToHand(SELF) effect, since there is no return-self cost spec).
  * SEC_103 Mon Mothma — "When Played: You may attack with any number of other
    units (one at a time), even if exhausted; they can't attack bases" (the new
    repeat/allow_exhausted/no_base/exclude_source fields on the granted_attack
    seam).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ActivatedAbility, EventAbility, ConstantAbility,
    WhenPlayed, WhenDeployed, WhenDefeated, WhenUnitDefeated, OnAttack,
    OnAttackDefeatsUnit, WhenUnitAttacks,
    WhenAttacked, WhenAttackEnds, WhenYouRevealOrDiscard,
    WhenDealsCombatDamageToBase,
    ModifyStats, StatBonus, KeywordGrant, GrantKeyword, ReturnToHand, CustomEffect, GiveToken,
    DealDamage, DrawCards, DefeatUnit, NextPlayDiscount,
    DealDamageEqualTo, EntersPlayReady, CaptureUnit, CreateTokenUnit,
    InteractiveDamagePrevention,
    Heal, ExhaustSelf, ExhaustCard, ReadyCard, DiscardFromHand, PayResources,
    ConditionalEffect, GrantedAbility, AuraGrantedAbility,
    WhenFriendlyUnitDealtCombatDamage,
    WhenDealtCombatDamage, DamagePrevention, DamageAmplification,
    WhenYouTakeInitiative,
    CannotPlayFromHand, IgnoreAspectPenaltyForPlays, DiscardCardCost, WhenYouPlayCard,
    SuppressHostAbilities, StandingPlayDiscount, CostReduction, UnitsPayCosts,
    CannotBeAttackedWhileExhausted, CannotBeAttackedAfterDamagingBase,
    PlayOnlyAsFirstAction, WhenYouDraw,
    DefeatAllUnits, TraitGrant, Protection, PreventDamage,
    TargetSpec, Duration, SELF, EACH_FRIENDLY, EACH_ENEMY, EACH_IN_PLAY,
    ConditionCheck, Condition,
)


@card_ability("SEC", "93")
def _c_3po():
    """SEC_93 — C-3PO (Unit, Droid/Republic): "Action [Exhaust, return this unit
    to its owner's hand]: Give a unit +2/+2 for this phase."

    An ActivatedAbility whose Exhaust cost is a real ``ExhaustSelf`` and whose
    "return this unit to its owner's hand" cost is modelled as a trailing
    ``ReturnToHand(fixed=SELF)`` effect (there is no return-self cost spec).  The
    +2/+2 ModifyStats is ordered FIRST (a targeted effect ahead of the fixed-SELF
    return, so the player is prompted exactly once); its target excludes C-3PO
    itself (``not_self``) because the printed cost returns C-3PO to hand before the
    buff would land, so it can never be the buffed unit."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[
            ModifyStats(power=2, hp=2,
                        target=TargetSpec(controller="any", kind="unit",
                                          predicates=("not_self",)),
                        duration=Duration.THIS_PHASE),
            ReturnToHand(TargetSpec(kind="unit", fixed=SELF)),
        ],
        title="Give a unit +2/+2 this phase (return C-3PO to hand)",
    )


def _mon_mothma_attacks(state, source_ci, target_id, event_ctx):
    """Adapter: let the controller attack with any number of other units, one at a
    time, even if exhausted, never against bases (the granted_attack repeat seam)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(
        state, source_ci,
        optional=True, repeat=True, allow_exhausted=True,
        no_base=True, exclude_source=True,
    )
    return state


@card_ability("SEC", "103")
def _mon_mothma():
    """SEC_103 — Mon Mothma (Unit, Official/Rebel, Restore 3 — keyword layer).

    "When Played: You may attack with any number of other units (one at a time),
    even if those units are exhausted.  They can't attack bases for these attacks."
    A mandatory WhenPlayed whose one CustomEffect is a thin adapter onto
    ``push_granted_attack`` with the repeat loop (``repeat``), exhausted attackers
    allowed (``allow_exhausted``), bases off-limits (``no_base``), and the source
    excluded (``exclude_source``).  The "you may" / "any number" is the granted
    attack's own optional decline, which also ends the loop."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_mon_mothma_attacks)],
    )


def _eye_of_aldhani_schedule(state, source_ci, target_id, event_ctx):
    """Adapter: schedule the per-enemy pay-or-exhaust effect for the start of the
    next action phase.  The event is in discard by the time this resolves, so the
    caster's id (not the instance) is recorded on the scheduled entry."""
    from swu.engine.actions import push_eye_of_aldhani_schedule
    push_eye_of_aldhani_schedule(state, source_ci)
    return state


@card_ability("SEC", "73")
def _the_eye_of_aldhani():
    """SEC_73 — The Eye of Aldhani (Event, Vigilance): "At the start of the next
    action phase, for each enemy unit, its controller must pay 1 resource or exhaust
    that unit."

    A plain ``EventAbility`` whose one no-target ``CustomEffect`` is a thin adapter
    onto the delayed action-phase-start scheduler (``push_eye_of_aldhani_schedule``);
    the effect fires later, at the next action-phase start, as a per-enemy
    ``pay_or_exhaust`` decision addressed to the enemy (each unit's controller)."""
    return EventAbility(effects=[CustomEffect(fn=_eye_of_aldhani_schedule)])


# ── Group leia-organa:04 — Combat tricks, buffs & tempo ───────────────────────

@card_ability("SEC", "252")
def _maarva_andor():
    """SEC_252 — Maarva Andor (Unit, Rebel): "When Defeated: Give an Experience
    token to each friendly Rebel unit."

    A ``WhenDefeated`` ``GiveToken("Experience", …)`` whose target auto-selects
    every friendly Rebel unit (``fixed=EACH_FRIENDLY`` with a Rebel trait filter),
    resolving inline with no prompt.  Maarva has left play by the time her
    WhenDefeated resolves, so she is never a recipient of her own tokens."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="friendly", kind="unit",
                                      traits=("Rebel",), fixed=EACH_FRIENDLY))],
    )


# ── Group jabba-the-hutt:01 — Plot keyword residuals ──────────────────────────
# The Plot keyword itself is implemented engine-side (play a Plot card from your
# resources when you deploy a leader — the "plot" decision pushed by DeployLeader,
# PlotPlay/FinishPlot).  These two cards carry residual "When Played" text beyond
# the keyword.

@card_ability("SEC", "186")
def _garindan():
    """SEC_186 — Garindan (Unit, Underworld): "When Played: Name a card. Look at
    an opponent's hand and discard a card with that name from it."

    DEVIATION (documented): modelled as a mandatory ``WhenPlayed`` discarding one
    card from the opponent's hand via the established
    ``DiscardFromHand(chooser="opponent")`` first-card simplification (the same
    simplification K-2SO SOR_145 and Poe's repeated-modal opponent_discards use).
    The faithful "name a card, look at the hand, and discard a card with that
    name" is a controller-chosen hand-strip, which would need a new
    look-at-opponent-hand-and-pick decision kind; that is out of scope for this
    keyword group, so the engine instead discards the opponent's first card.  An
    empty opponent hand is a clean no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DiscardFromHand(count=1, chooser="opponent")],
    )


@card_ability("SEC", "239")
def _viper_probe_droid_sec():
    """SEC_239 — Viper Probe Droid (SEC reprint): "When Played: Look at an
    opponent's hand."  Identical to SOR_228 — pushes the private 'look_hand'
    decision so the player actually sees the hand (instead of an invisible
    no-op log entry)."""
    def _inspect(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_look_opponent_hand
        push_look_opponent_hand(state, source_ci)
        return state
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_inspect)])


@card_ability("SEC", "189")
def _lurking_snub_fighter():
    """SEC_189 — Lurking Snub Fighter (Unit, Fighter/Underworld/Vehicle):
    "When Played: You may exhaust a unit."

    An optional ``WhenPlayed`` ``ExhaustCard`` targeting any unit (``controller=
    "any"``); with no unit on the board the optional trigger auto-declines.  In
    practice the just-played Lurking Snub Fighter is itself a legal (friendly)
    target, so the trigger is always offered — you point it at an enemy unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


# ── Reprint-duplicate encode (Stage 4 of docs/reprint_duplicates_plan.md) ─────

@card_ability("SEC", "142")
def _fulminatrix():
    """SEC_142 — Fulminatrix (Unit, 9/7): "When Played/On Attack: You may deal 4
    damage to a ground unit."

    Two otherwise-identical optional triggers (a ``WhenPlayed`` and an
    ``OnAttack``), each a ``DealDamage(4, …)`` targeting any ground unit; the
    "you may" is the optional trigger, which auto-declines with no ground unit on
    the board."""
    dmg = [DealDamage(4, TargetSpec(controller="any", kind="unit", arena="ground"))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(dmg), optional=True),
        TriggerAbility(trigger=OnAttack(), effects=list(dmg), optional=True),
    ]


# ── Reprint sweep Stage 4 Batch 2 (canonical encode) ─────────────────────────

@card_ability("SEC", "88")
def _first_light():
    """SEC_88 — First Light (Unit, Underworld/Vehicle/Transport, Ambush + Plot —
    keyword layers): "When this unit attacks and defeats a unit: You may draw a
    card."

    Ambush and Plot are both handled by the keyword engine.  The functional text is
    a single optional ``OnAttackDefeatsUnit`` trigger drawing one card (the Fett's
    Firespray LAW_252 "defeats a unit" pattern, but drawing instead of a credit) —
    ``OnAttackDefeatsUnit`` fires only when the attacker survives and defeated its
    target, so "attacks and defeats a unit" is intrinsic; the "you may" is
    ``optional=True``."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[DrawCards(count=1)],
        optional=True,
    )


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonical, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

def _bail_organa_on_attack(state, source_ci, target_id, event_ctx):
    """Discard the first card from the controller's hand (the established
    first-card discard simplification, K-2SO SOR_145 / Merrin LOF_160); if a card
    was discarded, create a Spy token.  Cost and payoff are bound so "If you do"
    holds."""
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state  # cannot discard → "if you do" not satisfied → no token
    from swu.engine.state import Zone
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    # Record the "discard 1+ cards from your hand" observer instruction (Padmé
    # Amidala SEC_16) — this bespoke discard doesn't route through the
    # DiscardFromHand effect arm, so record it explicitly.
    from swu.engine.actions import _create_token_units, record_hand_discard
    record_hand_discard(state, ps.player_id)
    _create_token_units(state, ps, "Spy", 1)
    return state


@card_ability("SEC", "198")
def _bail_organa():
    """SEC_198 — Bail Organa (Unit, 2/4): "On Attack: You may discard a card from
    your hand.  If you do, create a Spy token."

    An optional ``OnAttack`` trigger (the "you may") gated by
    ``CONTROLLER_HAS_CARD_IN_HAND`` so it is not offered with an empty hand (the
    discard cost cannot be paid).  One no-target ``CustomEffect`` discards a card
    then creates a Spy token (the create-token-unit primitive), bound so "If you
    do" holds.  DEVIATION (documented): the discard uses the established first-card
    simplification — the controller doesn't pick *which* card."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_CARD_IN_HAND),
        effects=[CustomEffect(fn=_bail_organa_on_attack)],
    )


# ── Group padme-amidala:05 — new primitive: reveal-or-discard-trigger ──────────

@card_ability("SEC", "16")
def _padme_amidala():
    """SEC_16 — Padmé Amidala (Leader, Naboo/Official/Republic, 3/8).

    Both sides share the SAME new observer trigger — ``WhenYouRevealOrDiscard``,
    fired at the settle-point when this leader's controller reveals (a successful
    Disclose) or discards 1+ cards from their hand (the DiscardFromHand effect /
    bespoke first-card discards).  See the trigger's docstring for the ledger →
    settle-drain plumbing (mirrors WhenYouUseForce / WhenYouDraw).

    Undeployed side (``text``): "When you reveal or discard 1 or more cards from your
    hand: You may exhaust this leader. If you do, deal 1 damage to a unit."  Modelled
    as an optional (the "you may") ``undeployed_only`` trigger — accepting deals the
    damage AND pays the exhaust-self cost, declining does neither ("If you do").  The
    targeted ``DealDamage(1)`` is ordered FIRST and the fixed-SELF ``ExhaustCard``
    LAST (the C-3PO SEC_93 "fixed-before-targeted single prompt" pattern — the fixed
    effect after the targeted one so the resolver prompts exactly once); accepting
    always exhausts, so the "cost then payoff" order is unobservable.  Gated
    ``SOURCE_READY`` so it is not offered once the leader is already exhausted (the
    exhaust cost can only be paid once per round — The Mandalorian SHD_18 pattern);
    subsequent reveal/discard events that round find her exhausted and are skipped.

    Deployed side (``deploy_box``): "When you reveal or discard 1 or more cards from
    your hand: You may deal 1 damage to a unit."  The same trigger, ``deployed_only``,
    optional, with just ``DealDamage(1)`` — no exhaust cost, so it may fire on every
    reveal/discard while she is a deployed unit.

    The Epic Action deploy ("If you control 6 or more resources, deploy this leader")
    is the standard deploy_threshold machinery — no registration.  No self-chain gate
    beyond SOURCE_READY: the payoff (damage / exhaust) neither reveals nor discards,
    so it cannot re-fire the observer."""
    return [
        TriggerAbility(
            trigger=WhenYouRevealOrDiscard(),
            effects=[
                DealDamage(1, TargetSpec(controller="any", kind="unit")),
                ExhaustCard(TargetSpec(kind="unit", fixed=SELF)),
            ],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenYouRevealOrDiscard(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            optional=True,
            deployed_only=True,
        ),
    ]


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonical, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

@card_ability("SEC", "147")
def _chopper():
    """SEC_147 — Chopper (Unit, Rebel/Droid/Spectre): "When this unit deals combat
    damage to a base: Each player discards a card from their hand."

    Reuses the ``WhenDealsCombatDamageToBase`` trigger (Ketsu Onyo SHD_147, fired
    at the base-combat-damage step).  "Each player discards" is two mandatory
    ``DiscardFromHand`` effects — one for the controller, one for the opponent
    (both the established first-card simplification; a player with an empty hand
    discards nothing)."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[
            DiscardFromHand(count=1, chooser="controller"),
            DiscardFromHand(count=1, chooser="opponent"),
        ],
    )


@card_ability("SEC", "258")
def _grassroots_resistance():
    """SEC_258 — Grassroots Resistance (Event, Tactic): "Deal 3 damage to a unit.
    Heal 3 damage from your base."

    Two plain mandatory effects: a ``DealDamage(3, any unit)`` (mandatory-if-able,
    fizzles cleanly with no unit) and a ``Heal(3, friendly base)`` — the
    ``fixed=EACH_FRIENDLY`` base heal auto-targets the controller's own base (the
    501st Liberator TWI_109 heal-own-base convention)."""
    return EventAbility(effects=[
        DealDamage(3, TargetSpec(controller="any", kind="unit")),
        Heal(3, TargetSpec(controller="friendly", kind="base",
                           fixed=EACH_FRIENDLY)),
    ])


@card_ability("SEC", "51")
def _bo_katan_kryze():
    """SEC_51 — Bo-Katan Kryze (8/8): "When Played: Give each enemy unit –3/–3 for
    this phase.  When an enemy unit is defeated: Give an Experience token to a
    friendly unit."

    Two plain triggers, both pure reuse.  The ``WhenPlayed`` is a mandatory
    ``ModifyStats(-3/-3, EACH_ENEMY unit, THIS_PHASE)`` (auto-targets every enemy
    unit inline — the Encouraging Leadership TWI_126 mass-buff pattern, negatived).
    The ``WhenUnitDefeated`` observer, filtered to an *enemy* unit (the HK-47
    LOF_130 pattern), gives an Experience token to a friendly unit (mandatory-if-
    able)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ModifyStats(power=-3, hp=-3,
                                 target=TargetSpec(controller="enemy", kind="unit",
                                                   fixed=EACH_ENEMY),
                                 duration=Duration.THIS_PHASE)],
        ),
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="enemy", kind="unit")),
            effects=[GiveToken("Experience",
                               TargetSpec(controller="friendly", kind="unit"))],
        ),
    ]


# ---------------------------------------------------------------------------
# Reprint-duplicate batch 6 (2026-07-08)
# ---------------------------------------------------------------------------


@card_ability("SEC", "114")
def _kino_loy_sec114():
    """SEC_114 — Kino Loy (Unit): "This unit gets +1/+0 for each other exhausted
    friendly unit."

    A self-targeted scaling ``ConstantAbility`` (the Nien Nunb JTL_93 pattern) —
    the new ``StatBonus.count="other_exhausted_friendly_units"`` scales the +1/+0
    by the controller's exhausted arena units excluding Kino himself, read
    passively by ``compute_power`` (winks on/off with the board; no trigger or
    decision machinery)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=0, count="other_exhausted_friendly_units")],
    )


@card_ability("SEC", "170")
def _corellian_hounds_sec170():
    """SEC_170 — Corellian Hounds (Unit, 5/5): "If an opponent controls no ground
    units, this unit enters play ready."

    The Salacious Crumb LAW_210 ``EntersPlayReady`` passive-marker pattern, gated by
    the new ``ENEMY_CONTROLS_NO_GROUND_UNITS`` condition (evaluated against the
    entering unit's controller at the enter-play placement)."""
    return EntersPlayReady(
        condition=ConditionCheck(Condition.ENEMY_CONTROLS_NO_GROUND_UNITS),
    )


@card_ability("SEC", "130")
def _ferrix_uprising_sec130():
    """SEC_130 — Ferrix Uprising (Event, cost 4): "Deal damage to a unit equal to
    twice the number of units you control in its arena."

    A plain ``EventAbility`` with one ``DealDamageEqualTo`` whose magnitude is the
    new doubled ``source_controller_units_in_target_arena_x2`` count (the
    Synchronized Strike TWI_99 count, ×2).  The target is non-fixed (the controller
    picks the unit; mandatory-if-able); a magnitude of 0 (no units in that arena) is
    a no-op."""
    return EventAbility(effects=[
        DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit"),
            count="source_controller_units_in_target_arena_x2"),
    ])


@card_ability("SEC", "209")
def _the_mandalorian_sec209():
    """SEC_209 — The Mandalorian (Unit 6/8, Ambush): "When this unit attacks and
    defeats a unit: You may choose an enemy non-leader unit.  This unit captures it."

    Ambush is the keyword layer.  A single optional ``OnAttackDefeatsUnit``
    ``CaptureUnit`` (the Discerning Veteran SHD_120 pattern) — this unit captures via
    its OWN ability, so there is no ``event_ctx["attached_to_id"]`` and the
    resolver's CaptureUnit arm falls back to the source unit as the captor.  The
    "you may" is the optional trigger; auto-declines with no eligible enemy
    non-leader unit."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[CaptureUnit(target=TargetSpec(
            controller="enemy", kind="unit", predicates=("non_leader",)))],
        optional=True,
    )


def _lando_choose_enemy(state, source_ci, target_id, event_ctx):
    """Lando SEC_68 first clause: record the chosen enemy unit (the future captor)
    so the second clause can heal + capture with it (the Haymaker LAW_168 two-
    dependent-CustomEffect.target pattern, sharing the resolve_effects event_ctx)."""
    event_ctx["lando_enemy_id"] = target_id
    return state


def _lando_capture(state, source_ci, target_id, event_ctx):
    """Lando SEC_68 second clause: ``target_id`` is the chosen friendly non-leader
    unit.  "If you do" — only when BOTH an enemy unit (recorded) and this friendly
    unit were chosen: heal 6 from the controller's own base and the enemy unit
    captures the friendly unit (``_apply_capture`` with captor = the enemy unit)."""
    enemy_id = event_ctx.get("lando_enemy_id")
    if not (enemy_id and target_id):
        return state
    from swu.engine.actions import _apply_capture
    ctrl = state.player_by_id(source_ci.owner_id)
    if ctrl.base_instance is not None:
        ctrl.base_instance.damage = max(0, ctrl.base_instance.damage - 6)
    _apply_capture(state, enemy_id, target_id)
    return state


@card_ability("SEC", "68")
def _lando_calrissian_sec68():
    """SEC_68 — Lando Calrissian (Unit 6/8, Grit): "When Played: You may choose an
    enemy unit and another friendly non-leader unit.  If you do, heal 6 damage from
    your base and the enemy unit captures the friendly unit."

    Grit is the keyword layer.  An optional ``WhenPlayed`` with two dependent
    ``CustomEffect.target`` effects sharing the resolve_effects ``event_ctx`` (the
    Haymaker LAW_168 pattern): the first picks the enemy unit (the captor) and
    records it; the second picks the friendly non-leader unit (``not_self`` —
    "another"), heals the controller's base by 6, and captures it under the enemy
    unit via the existing ``_apply_capture`` primitive (the-mandalorian:07).  Both
    effects are needed for "If you do", so the heal+capture only lands when both
    targets are chosen."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            CustomEffect(fn=_lando_choose_enemy,
                         target=TargetSpec(controller="enemy", kind="unit")),
            CustomEffect(fn=_lando_capture,
                         target=TargetSpec(controller="friendly", kind="unit",
                                           predicates=("non_leader", "not_self"))),
        ],
        optional=True,
    )


def _palpatine_spies(state, source_ci, target_id, event_ctx):
    """Chancellor Palpatine SEC_82 WhenPlayed: if the controller controls a leader
    unit (a deployed leader in an arena), create 2 Spy token units and grant each a
    Sentinel keyword for this phase.  Fully inline — the leader-unit check is a
    scan of the controller's arenas (no new condition atom needed), the tokens are
    the create-token-unit primitive (ahsoka-tano:05), and the Sentinel grant is a
    ``this_phase`` ``keyword_grant`` Modifier on each created token."""
    from swu.cards.models import Leader
    ctrl = state.player_by_id(source_ci.owner_id)
    has_leader_unit = any(
        isinstance(u.card_def, Leader)
        for u in ctrl.ground_arena + ctrl.space_arena
    )
    if not has_leader_unit:
        return state
    from swu.engine.actions import _create_token_units
    from swu.engine.state import Modifier
    tokens = _create_token_units(state, ctrl, "Spy", 2)
    for tok in tokens:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=tok.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
    return state


@card_ability("SEC", "82")
def _chancellor_palpatine_sec82():
    """SEC_82 — Chancellor Palpatine (Unit 2/2, Plot): "When Played: If you control a
    leader unit, create 2 Spy tokens and give those tokens Sentinel for this phase."

    Plot is the keyword layer.  One ``WhenPlayed`` ``CustomEffect`` resolving inline
    (no player choice): the "control a leader unit" gate + the token creation + the
    per-token Sentinel grant (see ``_palpatine_spies``)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_palpatine_spies)],
    )


# ── Reprint-duplicate batch 12 (Stage 4) ──────────────────────────────────────

def _darth_traya_ready_leader(state, source_ci, target_id, event_ctx):
    """Darth Traya SEC_188 "On Attack: You may ready a non-unit leader."  Readies
    the controller's own undeployed leader (a "non-unit leader" = a Leader in
    base_zone, i.e. ``not deployed``) so its Action ability can be reused.  The
    trigger's condition already guarantees such a leader exists and is exhausted;
    readying enemy leaders is never worth it, so only the controller's is readied
    (the meaningful case in 2-player)."""
    ps = state.player_by_id(source_ci.owner_id)
    ldr = ps.leader_instance
    if ldr is not None and not getattr(ldr, "deployed", False):
        ldr.exhausted = False
    return state


@card_ability("SEC", "188")
def _darth_traya_sec_188():
    """SEC_188 — Darth Traya (Unit, Sith/Force, 2/5): "On Attack: You may ready a
    non-unit leader."

    An **optional** ``OnAttack`` (the "you may") gated by the new
    ``CONTROLLER_HAS_EXHAUSTED_UNDEPLOYED_LEADER`` condition — so it is offered only
    when the controller's leader is undeployed (a "non-unit leader") AND exhausted,
    i.e. there is actually one to ready (the "don't offer a no-op" pattern).  Its
    one no-target ``CustomEffect`` readies that leader inline."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_darth_traya_ready_leader)],
        optional=True,
        condition=ConditionCheck(
            Condition.CONTROLLER_HAS_EXHAUSTED_UNDEPLOYED_LEADER),
    )


@card_ability("SEC", "158")
def _oppression_breeds_rebellion_sec_158():
    """SEC_158 — Oppression Breeds Rebellion (Event): "If a friendly unit was
    defeated while attacking this phase, draw 3 cards."

    A plain ``EventAbility`` whose one no-target ``CustomEffect`` checks the new
    ``CONTROLLER_FRIENDLY_ATTACKER_DEFEATED_THIS_PHASE`` condition
    (``game_memory.attackers_defeated_this_round`` records the controllers of units
    defeated *while attacking* — recorded by the unit-combat step; "this round" ==
    "this phase", the units_defeated_this_round precedent) and draws 3 if it holds."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import _draw_cards
        if ConditionCheck(
                Condition.CONTROLLER_FRIENDLY_ATTACKER_DEFEATED_THIS_PHASE
        ).evaluate(state, source_ci):
            _draw_cards(state, state.player_by_id(source_ci.owner_id), 3)
        return state
    return EventAbility(effects=[CustomEffect(fn=_fn)])


# ── Reprint-duplicate batch 13 (Stage 4) ──────────────────────────────────────

def _darth_sion_when_played(state, source_ci, target_id, event_ctx):
    """Darth Sion SEC_35 "When Played: Give an Experience token to this unit for
    each enemy unit that was defeated this phase."  The count is state-derived
    (``game_memory.defeated_controllers_this_round`` records the controller-at-death
    of every unit defeated this round == this phase), so a scaling CustomEffect
    rather than a fixed-count GiveToken (the Leia LAW_10 deploy-tokens pattern)."""
    from swu.engine.tokens import attach_token
    controller = state.player_by_id(source_ci.owner_id)
    enemy_id = state.players[1 - state.player_index(source_ci.owner_id)].player_id
    n = state.game_memory.defeated_controllers_this_round.count(enemy_id)
    for _ in range(n):
        attach_token(state, controller, source_ci, "Experience")
    return state


def _darth_sion_when_defeated(state, source_ci, target_id, event_ctx):
    """Darth Sion SEC_35 "When Defeated: If this unit had 7 or more power, return
    him to his owner's hand."  ``event_ctx["defeated_power"]`` is his *effective*
    power snapshotted at the moment of defeat (before _defeat_unit stripped his
    upgrades/tokens).  This mandatory no-target trigger resolves INLINE during
    _defeat_unit — before the card is homed to discard — so the card is in limbo
    (find_instance returns None); operate on ``source_ci`` (the defeated instance)
    directly, move it to hand as a clean card, and set ``relocated_by_trigger`` so
    _defeat_unit skips the discard placement (the Stolen Landspeeder SHD_161 relocate
    convention).  If instead it has already reached discard (a deferred resolution),
    pull it back out."""
    if int(event_ctx.get("defeated_power", 0)) < 7:
        return state
    from swu.engine.state import Zone
    result = state.find_instance(source_ci.instance_id)
    if result is not None:
        ps, ci = result
        for lst in (ps.discard, ps.ground_arena, ps.space_arena):
            if ci in lst:
                lst.remove(ci)
                break
    else:
        ci = source_ci  # in limbo mid-defeat (inline resolution)
    ci.damage = 0
    ci.exhausted = False
    ci.cannot_ready_this_round = False
    ci.zone = Zone.HAND
    state.player_by_id(ci.owner_id).hand.append(ci)
    event_ctx["relocated_by_trigger"] = True
    return state


@card_ability("SEC", "35")
def _darth_sion_sec_35():
    """SEC_35 — Darth Sion (Unit, Sith/Force, 5/5): "When Played: Give an Experience
    token to this unit for each enemy unit that was defeated this phase.  When
    Defeated: If this unit had 7 or more power, return him to his owner's hand."

    Two mandatory triggers, each one no-target ``CustomEffect``.  The WhenPlayed
    scales the Experience count off the new ``defeated_controllers_this_round``
    tracker (enemy-controlled defeats this phase).  The WhenDefeated reads the new
    ``event_ctx["defeated_power"]`` (effective power at the instant of defeat, before
    the upgrade strip) and, when it was ≥ 7, moves the just-defeated card discard →
    hand (the Superlaser Technician SHD_85 relocate-the-defeated-card pattern)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_darth_sion_when_played)],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_darth_sion_when_defeated)],
        ),
    ]


# ── Stage 4 batch 21 (2026-07-12) — FRAMEWORK ESCALATION: the disclose primitive ──
#    "You may disclose <aspects> (reveal cards from your hand with these aspect
#    icons among them). If you do, <payoff>."  See actions.push_disclose.

def _karis_nemik_disclose(state, source_ci, target_id, event_ctx):
    """Karis Nemik SEC_148 payoff: disclose Aggression+Heroism → create a Spy
    token and ready it (the create-token-unit primitive, readied)."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression", "Heroism"],
        payoff="create_ready_token",
        payoff_args={"token_name": "Spy", "count": 1},
    )
    return state


@card_ability("SEC", "148")   # printed face WITH reminder text
@card_ability("J25", "17")    # anthology face WITHOUT reminder text (P26 twins alias here)
def _karis_nemik():
    """SEC_148 — Karis Nemik (Unit, Rebel; Hidden): "When Defeated: You may
    disclose [Aggression][Heroism] (reveal cards from your hand with these aspect
    icons among them). If you do, create a Spy token and ready it."

    Hidden is the keyword layer.  A MANDATORY WhenDefeated trigger whose one
    ``CustomEffect`` pushes the ``disclose`` decision — the "you may" lives in the
    disclose Decline, so no double-``optional``.  push_disclose no-ops (no prompt)
    when the controller can't cover the aspect requirement."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_karis_nemik_disclose)],
    )


def _syril_karn_disclose(state, source_ci, target_id, event_ctx):
    """Syril Karn SEC_133 payoff: disclose Aggression×2 + Villainy → deal 2 to the
    chosen unit unless its controller discards a card (the may_discard else-damage
    seam).  The target (an enemy unit) is chosen up front via CustomEffect.target,
    a cosmetic reorder of the printed "disclose, then choose a unit"."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(
        state, source_ci, ["Aggression", "Aggression", "Villainy"],
        payoff="damage_unless_discard",
        payoff_args={"target_id": target_id, "amount": 2},
    )
    return state


@card_ability("SEC", "133")   # printed face WITH reminder text
@card_ability("P26", "42")    # anthology face WITHOUT reminder text (P26_54 aliases here)
def _syril_karn():
    """SEC_133 — Syril Karn (Unit, Official/Imperial): "On Attack: You may disclose
    [Aggression][Aggression][Villainy] (reveal cards from your hand with these
    aspect icons among them). If you do, choose a unit. Deal 2 damage to that unit
    unless its controller discards a card from their hand."

    A MANDATORY ``OnAttack`` whose one ``CustomEffect`` first picks the target
    (``TargetSpec`` enemy unit — you never damage your own; a documented
    simplification of "a unit"), then pushes the ``disclose`` decision.  On a
    successful disclose the payoff hands a ``may_discard`` (else-damage) decision to
    that unit's controller — discard a card (first-card simplification) to prevent
    the 2 damage, or take it.  With no enemy unit the mandatory targeted effect
    fizzles (no prompt), so nothing is disclosed."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(
            fn=_syril_karn_disclose,
            target=TargetSpec(controller="enemy", kind="unit"),
        )],
    )


def _thrawn_capture_or_ready(state, source_ci, target_id, event_ctx):
    """SEC_193 When Played — inline-push the 'capture_or_ready' decision (the
    Palpatine SOR_135 non-targeted inline-push pattern)."""
    from swu.engine.actions import push_opponent_capture_or_ready
    push_opponent_capture_or_ready(state, source_ci)
    return state


def _thrawn_record_captor(state, source_ci, target_id, event_ctx):
    """SEC_193 When Defeated — record the chosen friendly captor + its arena so the
    follow-up effect captures an enemy non-leader unit "in the same arena"."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, captor = res
    from swu.engine.state import Zone
    event_ctx["thrawn_captor_id"] = target_id
    event_ctx["same_arena"] = "ground" if captor.zone == Zone.GROUND_ARENA else "space"
    return state


def _thrawn_capture_enemy(state, source_ci, target_id, event_ctx):
    """SEC_193 When Defeated — the recorded friendly captor captures the chosen
    enemy non-leader unit in its arena."""
    if target_id is None:
        return state
    captor_id = event_ctx.get("thrawn_captor_id")
    if not captor_id:
        return state
    from swu.engine.actions import _apply_capture
    return _apply_capture(state, captor_id, target_id)


@card_ability("SEC", "193")
def _grand_admiral_thrawn():
    """SEC_193 — Grand Admiral Thrawn (Unit, Imperial/Official, Cunning/Villainy,
    7-cost 8/7 unique):
      * When Played: "An opponent may choose a non-leader unit they control.  If
        they do, this unit captures that unit.  If they don't, ready this unit."
      * When Defeated: "A friendly unit captures an enemy non-leader unit in the
        same arena."

    THE NEW PRIMITIVE — the ``capture_or_ready`` decision kind
    (``push_opponent_capture_or_ready``): the OPPONENT decides (the deciding-player
    shift of each_player_defeats TWI_238 / opponent_chooses_target SHD_246), giving
    up a non-leader unit to be captured (``ChooseCaptureVictim`` → ``_apply_capture``
    with Thrawn as captor) or declining (``DeclineCaptureVictim`` → Thrawn readies).
    With no opponent non-leader unit the source readies inline (no decision).  The
    When Played is MANDATORY from the controller's side (the optionality is the
    opponent's, inside the decision), so a plain ``WhenPlayed`` with one no-target
    ``CustomEffect`` inline-push (the Palpatine SOR_135 pattern).

    The When Defeated is a COMPOSITION — no new decision kind: two dependent
    ``CustomEffect``s sharing the ``resolve_effects`` ``event_ctx`` (the Haymaker
    LAW_168 / Double-Cross LAW_170 pattern) reusing the ``same_arena_as_event``
    predicate + the existing capture primitive.  The first picks the friendly captor
    and records its arena; the second picks the enemy non-leader unit restricted to
    that arena and captures it.  Each is mandatory-if-able (no friendly unit ⇒
    nothing; a captor in an arena with no enemy non-leader ⇒ the capture step
    fizzles — the documented minor sequencing deviation of the two-CustomEffect
    pattern).  Thrawn himself has left the arena when this resolves, so he is never
    the captor."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_thrawn_capture_or_ready)],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[
                CustomEffect(
                    fn=_thrawn_record_captor,
                    target=TargetSpec(controller="friendly", kind="unit"),
                ),
                CustomEffect(
                    fn=_thrawn_capture_enemy,
                    target=TargetSpec(controller="enemy", kind="unit",
                                      predicates=("non_leader", "same_arena_as_event")),
                ),
            ],
        ),
    ]


# ── Group padme-amidala:01 — Card advantage & disruption ──────────────────────

def _mina_bonteri_disclose(state, source_ci, target_id, event_ctx):
    """Mina Bonteri SEC_94 payoff: disclose Command+Command+Heroism → draw a card
    (the new ``draw`` disclose-payoff arm in ``_apply_disclose_payoff``)."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Command", "Command", "Heroism"],
        payoff="draw",
        payoff_args={"count": 1},
    )
    return state


@card_ability("SEC", "94")
def _mina_bonteri():
    """SEC_94 — Mina Bonteri (Unit, Official/Separatist, Restore 1 — keyword layer):
    "When Defeated: You may disclose [Command][Command][Heroism] (reveal cards from
    your hand with these aspect icons among them). If you do, draw a card."

    Restore 1 is the keyword layer.  A MANDATORY ``WhenDefeated`` whose one
    ``CustomEffect`` pushes the ``disclose`` decision (the Karis Nemik SEC_148
    pattern) — the "you may" lives in the disclose Decline, so no double-optional.
    The "if you do, draw a card" payoff is the new ``draw`` arm of
    ``_apply_disclose_payoff`` (a thin ``_draw_cards`` reuse).  push_disclose
    no-ops with no prompt when the controller's hand can't cover Command×2+Heroism."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_mina_bonteri_disclose)],
    )


@card_ability("SEC", "197")
def _furtive_handmaiden():
    """SEC_197 — Furtive Handmaiden (Unit, Naboo): "On Attack: You may discard a
    card from your hand. If you do, draw a card."

    An optional ``OnAttack`` trigger (the "you may") gated by
    ``CONTROLLER_HAS_CARD_IN_HAND`` so it is not offered with an empty hand (the
    discard cost cannot be paid — the Bail Organa SEC_198 gate).  Two plain
    mandatory-once-accepted effects bind the cost to the payoff: a
    ``DiscardFromHand`` (the established first-card simplification — the controller
    doesn't pick *which* card) then ``DrawCards(1)``.  Since the condition
    guarantees ≥1 card, the discard always lands, so "if you do" holds."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_CARD_IN_HAND),
        effects=[
            DiscardFromHand(count=1, chooser="controller"),
            DrawCards(count=1),
        ],
    )


# ── Group padme-amidala:02 — Combat tricks, buffs & tempo ─────────────────────

def _ahsoka_tano_disclose(state, source_ci, target_id, event_ctx):
    """Ahsoka Tano SEC_96 payoff: disclose Command+Heroism → attack with another
    unit (the new ``granted_attack`` disclose-payoff arm, reusing
    ``push_granted_attack`` with ``exclude_source``)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Command", "Heroism"],
                  payoff="granted_attack", payoff_args={})
    return state


@card_ability("SEC", "96")
def _ahsoka_tano_sec():
    """SEC_96 — Ahsoka Tano (Unit, Force/Jedi/Republic): "When this unit completes
    an attack (and survives): You may disclose [Command][Heroism] (reveal cards
    from your hand with these aspect icons among them). If you do, attack with
    another unit."

    A MANDATORY ``WhenAttackEnds`` trigger (the "and survives" clause is intrinsic
    to the trigger — it only fires for an attacker still in play) whose one
    ``CustomEffect`` pushes the ``disclose`` decision (the Mina Bonteri SEC_94
    pattern) — the "you may" lives in the disclose Decline.  The "if you do, attack
    with another unit" payoff is the new ``granted_attack`` arm of
    ``_apply_disclose_payoff``, which reuses ``push_granted_attack`` (``exclude_source``
    → "another unit"); with no other eligible attacker it simply pushes nothing."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_ahsoka_tano_disclose)],
    )


def _captain_typho_disclose(state, source_ci, target_id, event_ctx):
    """Captain Typho SEC_98 payoff: disclose Command+Heroism → heal 1 from your
    base (the new ``heal_base`` disclose-payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Command", "Heroism"],
                  payoff="heal_base", payoff_args={"amount": 1})
    return state


@card_ability("SEC", "98")
def _captain_typho():
    """SEC_98 — Captain Typho (Unit, Naboo/Republic/Trooper, Sentinel — keyword
    layer): "When this unit is attacked: You may disclose [Command][Heroism]
    (reveal cards from your hand with these aspect icons among them). If you do,
    heal 1 damage from your base."

    Sentinel is the keyword layer.  A MANDATORY ``WhenAttacked`` trigger whose one
    ``CustomEffect`` pushes the ``disclose`` decision — the "you may" lives in the
    disclose Decline.  The "if you do, heal 1 from your base" payoff is the new
    ``heal_base`` arm of ``_apply_disclose_payoff`` (a direct base-damage reduction,
    the Lando SEC_68 heal-own-base convention).  push_disclose no-ops with no prompt
    when the controller's hand can't cover Command+Heroism."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CustomEffect(fn=_captain_typho_disclose)],
    )


@card_ability("SEC", "99")
def _naboo_royal_starship():
    """SEC_99 — Naboo Royal Starship (Unit, Naboo/Transport/Vehicle; Overwhelm,
    Plot, Raid — keyword layers): "Each friendly leader unit gains Raid 2 and
    Overwhelm."

    Overwhelm/Plot/Raid on the Starship itself are the keyword layers.  The
    functional text is a plain ``ConstantAbility`` targeting every friendly *leader
    unit* (a deployed leader in an arena — the ``leader_unit`` predicate) with two
    ``KeywordGrant`` effects (Raid 2 + Overwhelm), read passively by
    ``keyword_value``/``has_keyword`` (the Red Three grant-to-others pattern)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("leader_unit",)),
        effects=[KeywordGrant("Raid", 2), KeywordGrant("Overwhelm", 0)],
    )


@card_ability("SEC", "111")
def _jar_jar_binks():
    """SEC_111 — Jar Jar Binks (Unit, Gungan/Naboo/Official/Republic, Plot —
    keyword layer): "When Played: You may give another friendly unit +2/+2 for this
    phase."

    Plot is the keyword layer.  An optional ``WhenPlayed`` (the "you may")
    ``ModifyStats(+2/+2, THIS_PHASE)`` on another friendly unit (``not_self`` →
    "another"); auto-declines when Jar Jar is the only friendly unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ModifyStats(power=2, hp=2,
                             target=TargetSpec(controller="friendly", kind="unit",
                                               predicates=("not_self",)),
                             duration=Duration.THIS_PHASE)],
    )


@card_ability("SEC", "116")
def _nubian_star_skiff():
    """SEC_116 — Nubian Star Skiff (Unit, Naboo/Transport/Vehicle): "While you
    control an Official unit, this unit gains Restore 2."

    The Salacious Crumb / Hunting Nexu SHD_168 conditional-self-grant pattern: a
    ``ConstantAbility(target=SELF, KeywordGrant("Restore", 2))`` gated by
    ``CONTROLLER_HAS_TRAIT_UNIT("Official")``, read passively by
    ``keyword_value``/``has_keyword``.  The Skiff itself is not Official, so it never
    satisfies the condition on its own.  The keyword sanitiser strips the printed
    "Restore" tag (mis-tagged from the reminder text) because this conditional
    self-grant ConstantAbility is registered, so the ability — not an always-on bar
    — owns the keyword."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", 2)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT,
                                 param="Official"),
    )


# ── Group padme-amidala:03 — Combat tricks, buffs & tempo ─────────────────────

def _thunderous_applause_first(state, source_ci, target_id, event_ctx):
    """With Thunderous Applause SEC_129 first effect: give the chosen unit +2/+2
    for this phase and record its id so the disclose payoff buffs 'another' unit
    (the Grenade Strike TWI_171 excludes_event_target pattern)."""
    if target_id is None:
        return state
    event_ctx["excluded_target_id"] = target_id
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=2, hp=2, duration=Duration.THIS_PHASE))
    return state


def _thunderous_applause_disclose(state, source_ci, target_id, event_ctx):
    """SEC_129 payoff: disclose Command → give the pre-chosen 'another' unit +2/+2
    this phase (the new ``buff_unit`` disclose-payoff arm).  ``target_id`` is the
    second (different) unit; None if there is no other unit to buff → no disclose."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Command"],
                  payoff="buff_unit",
                  payoff_args={"target_id": target_id, "power": 2, "hp": 2})
    return state


@card_ability("SEC", "129")
def _with_thunderous_applause():
    """SEC_129 — With Thunderous Applause (Event, Plan): "Give a unit +2/+2 for
    this phase. You may disclose [Command] (reveal a card from your hand with this
    aspect icon). If you do, give another unit +2/+2 for this phase."

    Two sequential effects sharing the ``resolve_effects`` ``event_ctx`` (the
    Grenade Strike TWI_171 / Syril Karn SEC_133 pattern).  The first is a
    mandatory CustomEffect.target that buffs the chosen unit and records its id
    under ``event_ctx["excluded_target_id"]``.  The second CustomEffect.target
    picks "another unit" (the ``excludes_event_target`` predicate → not the first)
    and pushes the ``disclose`` decision — the "you may" lives in the disclose
    Decline (a cosmetic reorder: both units are chosen before disclosing).  The
    "if you do, buff another unit" payoff is the new ``buff_unit`` arm of
    ``_apply_disclose_payoff`` (a thin stat-modifier reuse).  With only one unit on
    the board the second target fizzles, so nothing is disclosed."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_thunderous_applause_first,
            target=TargetSpec(controller="any", kind="unit"),
        ),
        CustomEffect(
            fn=_thunderous_applause_disclose,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("excludes_event_target",)),
        ),
    ])


@card_ability("SEC", "201")
def _anakin_skywalker_sec():
    """SEC_201 — Anakin Skywalker (Unit, Force/Jedi/Republic; Hidden): "Hidden
    (This unit can't be attacked if he was played this phase.)  While you control
    Padmé Amidala (as a leader or unit), this unit gains Raid 2."

    Hidden is the keyword layer.  The functional text is the conditional-self-grant
    pattern (Nubian Star Skiff SEC_116 / Hunting Nexu SHD_168): a
    ``ConstantAbility(target=SELF, KeywordGrant("Raid", 2))`` gated by
    ``CONTROLLER_CONTROLS_NAMED("Padmé Amidala")`` (substring match — the leader
    deployed or undeployed, or a Padmé unit; it does NOT match Queen Amidala),
    read passively by ``keyword_value``.  Registering this conditional self-grant
    makes the keyword sanitiser strip the mis-tagged printed "Raid" (rule 2), so
    the ability — not an always-on printed bar — owns the Raid."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 2)],
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                 param="Padmé Amidala"),
    )


def _bog_down_first(state, source_ci, target_id, event_ctx):
    """Bog Down in Procedure SEC_234 first effect: exhaust the chosen unit and
    record its id so the disclose payoff exhausts 'another' unit."""
    if target_id is None:
        return state
    event_ctx["excluded_target_id"] = target_id
    res = state.find_instance(target_id)
    if res is not None:
        from swu.abilities.resolver import _target_protected
        if not _target_protected(state, target_id, source_ci, "exhaust"):
            res[1].exhausted = True
    return state


def _bog_down_disclose(state, source_ci, target_id, event_ctx):
    """SEC_234 payoff: disclose Cunning → exhaust the pre-chosen 'another' unit
    (the new ``exhaust_unit`` disclose-payoff arm).  ``target_id`` is None when no
    other unit exists → no disclose."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Cunning"],
                  payoff="exhaust_unit",
                  payoff_args={"target_id": target_id})
    return state


@card_ability("SEC", "234")
def _bog_down_in_procedure():
    """SEC_234 — Bog Down in Procedure (Event, Law): "Exhaust a unit. You may
    disclose [Cunning] (reveal a card from your hand with this aspect icon). If you
    do, exhaust another unit."

    The With Thunderous Applause SEC_129 structure with exhaust in place of the
    buff: a mandatory CustomEffect.target exhausts the chosen unit (honours
    Protection) and records ``event_ctx["excluded_target_id"]``; a second
    CustomEffect.target picks "another unit" (``excludes_event_target``) and pushes
    the ``disclose`` decision.  The "if you do" payoff is the new ``exhaust_unit``
    arm of ``_apply_disclose_payoff``.  With only one unit on the board the second
    target fizzles, so nothing is disclosed."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_bog_down_first,
            target=TargetSpec(controller="any", kind="unit"),
        ),
        CustomEffect(
            fn=_bog_down_disclose,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("excludes_event_target",)),
        ),
    ])


# ── Group padme-amidala:04 — Miscellaneous abilities ──────────────────────────

@card_ability("SEC", "115")
def _taylander_shuttle():
    """SEC_115 — Taylander Shuttle (Unit, Vehicle/Transport): "On Attack: If you
    have the initiative, create a Spy token."

    A plain ``OnAttack`` gated by ``CONTROLLER_HAS_INITIATIVE`` (the trigger-collect
    condition, so nothing is offered without the initiative — Pryde JTL_?/SOR
    pattern), with a non-targeted ``CreateTokenUnit`` (the ahsoka-tano:05 primitive)
    that resolves inline."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CreateTokenUnit("Spy", count=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


def _hunter_on_attack(state, source_ci, target_id, event_ctx):
    """Hunter SEC_208 On Attack: if the current defender is exhausted, give it
    −4/−0 for this attack (the Chain Code Collector SHD_216 combat-trick pattern —
    a CustomEffect reading ``event_ctx["defender_id"]`` before power computation)."""
    from swu.abilities.resolver import _make_modifier
    defender_id = event_ctx.get("defender_id")
    if not defender_id:
        return state  # attacking a base — no defender unit
    result = state.find_instance(defender_id)
    if result is None:
        return state
    _, defender = result
    if not defender.exhausted:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, defender_id,
        power=-4, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("SEC", "208")
def _hunter():
    """SEC_208 — Hunter (Unit, Saboteur): "On Attack: If the defender is exhausted,
    it gets −4/−0 for this attack."

    Saboteur is the keyword engine.  The On Attack is the Chain Code Collector
    SHD_216 combat trick: a CustomEffect that (before combat-damage computation)
    checks the current defender's exhausted flag and, if set, applies a this-attack
    −4/−0 ModifyStats to it.  Resolves inline (the defender is fixed by the
    attack), so no decision is pushed."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_hunter_on_attack)],
    )


@card_ability("SEC", "256")
def _moral_authority():
    """SEC_256 — Moral Authority (Upgrade, Innate; attach to a friendly unique
    unit): "When Played: Attached unit captures an enemy non-leader unit with less
    remaining HP than it."

    An upgrade ``WhenPlayed`` ``CaptureUnit`` (the-mandalorian:07 capture primitive).
    The captor is the attached host — the resolver's CaptureUnit arm reads
    ``event_ctx["attached_to_id"]`` (threaded by the upgrade play path).  The victim
    is chosen through the normal resolve_effects/ChooseTarget machinery, narrowed to
    enemy non-leader units whose remaining HP is strictly less than the host's (the
    new ``less_remaining_hp_than_host`` predicate).  Mandatory-if-able: with no
    eligible enemy unit it fizzles with no prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(target=TargetSpec(
            controller="enemy", kind="unit",
            predicates=("non_leader", "less_remaining_hp_than_host")))],
    )


def _naboo_sec_force_disclose(state, source_ci, target_id, event_ctx):
    """Naboo Security Force SEC_120 payoff: the chosen friendly unit is pre-picked;
    push disclose Command → give it Sentinel this phase (the new ``grant_keyword``
    disclose-payoff arm).  ``target_id`` is None when there is no friendly unit
    (e.g. the source is the only friendly unit and is being defeated) → no
    disclose."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Command"],
                  payoff="grant_keyword",
                  payoff_args={"target_id": target_id,
                               "keyword": "Sentinel", "value": 0})
    return state


@card_ability("SEC", "120")
def _naboo_security_force():
    """SEC_120 — Naboo Security Force (Unit, Sentinel): "When Played/When Defeated:
    You may disclose [Command].  If you do, give a friendly unit Sentinel for this
    phase."

    Sentinel is the printed keyword.  The functional text fires on TWO windows, so
    two ``TriggerAbility``s (``WhenPlayed`` + ``WhenDefeated``) each carrying one
    CustomEffect.target that pre-picks the friendly unit and pushes the ``disclose``
    decision (the SEC_129 pre-chosen convention: the target is chosen before
    disclosing, a cosmetic reorder).  "If you do, give it Sentinel this phase" is
    the new ``grant_keyword`` disclose-payoff arm (a keyword-grant modifier reuse)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(
                fn=_naboo_sec_force_disclose,
                target=TargetSpec(controller="friendly", kind="unit"))],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(
                fn=_naboo_sec_force_disclose,
                target=TargetSpec(controller="friendly", kind="unit"))],
        ),
    ]


def _b2emo_disclose(state, source_ci, target_id, event_ctx):
    """B2EMO SEC_248 payoff: the chosen unit is pre-picked; push disclose
    Heroism+Heroism → give it Sentinel this phase (the ``grant_keyword`` arm).
    ``target_id`` None (no unit in play) → no disclose."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Heroism", "Heroism"],
                  payoff="grant_keyword",
                  payoff_args={"target_id": target_id,
                               "keyword": "Sentinel", "value": 0})
    return state


@card_ability("SEC", "248")
def _b2emo():
    """SEC_248 — B2EMO (Unit, Restore 1): "On Attack: You may disclose
    [Heroism][Heroism].  If you do, give a unit Sentinel for this phase."

    Restore is the keyword engine.  The On Attack pre-picks any unit (``controller
    ="any"`` — "a unit") and pushes the ``disclose`` decision requiring two Heroism
    icons; the payoff is the ``grant_keyword`` arm (give it Sentinel this phase).
    The SEC_120 pattern with a two-icon Heroism requirement and any-controller
    target."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(
            fn=_b2emo_disclose,
            target=TargetSpec(controller="any", kind="unit"))],
    )


def _charged_choose_captor(state, source_ci, target_id, event_ctx):
    """Charged with Corruption SEC_127 first effect: record the chosen friendly
    captor so the disclose payoff captures under it (the Lando SEC_68 / Thrawn
    SEC_193 two-dependent-CustomEffect pattern sharing the resolve_effects
    event_ctx)."""
    event_ctx["cwc_captor_id"] = target_id
    return state


def _charged_disclose(state, source_ci, target_id, event_ctx):
    """SEC_127 second effect: ``target_id`` is the chosen enemy non-leader victim.
    Push disclose Command+Command → the pre-chosen friendly captor captures it (the
    new ``capture`` disclose-payoff arm).  Only pushes when both a captor and a
    victim were chosen (else there is nothing to capture)."""
    from swu.engine.actions import push_disclose
    captor_id = event_ctx.get("cwc_captor_id")
    if not (captor_id and target_id):
        return state
    push_disclose(state, source_ci, ["Command", "Command"],
                  payoff="capture",
                  payoff_args={"captor_id": captor_id, "victim_id": target_id})
    return state


@card_ability("SEC", "127")
def _charged_with_corruption():
    """SEC_127 — Charged with Corruption (Event, Law): "You may disclose
    [Command][Command].  If you do, a friendly unit captures an enemy non-leader
    unit."

    Two dependent ``CustomEffect.target`` effects sharing the ``resolve_effects``
    event_ctx (the Lando SEC_68 / Thrawn SEC_193 capture pattern), plus the SEC_129
    pre-chosen-disclose convention: the first picks the friendly captor and records
    it; the second picks the enemy non-leader victim and pushes the ``disclose``
    decision (two Command icons).  "If you do, capture" is the new ``capture``
    disclose-payoff arm (reuses ``_apply_capture`` with the pre-chosen captor +
    victim).  Declining, or an uncoverable disclose, captures nothing."""
    return EventAbility(effects=[
        CustomEffect(fn=_charged_choose_captor,
                     target=TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_charged_disclose,
                     target=TargetSpec(controller="enemy", kind="unit",
                                       predicates=("non_leader",))),
    ])


def _dismantle_choose_captor(state, source_ci, target_id, event_ctx):
    """Dismantle the Conspiracy SEC_106: ``target_id`` is the chosen friendly
    captor.  Push the ``capture_combined_hp`` decision (budget 7) so it captures any
    number of enemy non-leader units with combined remaining HP ≤ 7 under it."""
    from swu.engine.actions import push_capture_combined_hp
    if target_id is None:
        return state
    push_capture_combined_hp(state, source_ci, captor_id=target_id, budget=7)
    return state


@card_ability("SEC", "106")
def _dismantle_the_conspiracy():
    """SEC_106 — Dismantle the Conspiracy (Event, Tactic): "A friendly unit captures
    any number of enemy non-leader units with a total of 7 or less remaining HP."

    A CustomEffect.target picks the friendly captor (mandatory-if-able), then pushes
    the new ``capture_combined_hp`` decision kind — the exhaust_combined_cost
    LOF_201 budget-select shape, but weighted by each candidate's *remaining* HP and
    capturing (under the pre-chosen captor) instead of exhausting.  "Any number"
    includes 0, so a FinishCaptureCombined is always offered; each pick captures an
    enemy non-leader unit whose remaining HP still fits the shrinking 7-HP budget."""
    return EventAbility(effects=[
        CustomEffect(fn=_dismantle_choose_captor,
                     target=TargetSpec(controller="friendly", kind="unit")),
    ])


@card_ability("SEC", "101")
def _queen_amidala():
    """SEC_101 — Queen Amidala (Unit, Naboo/Official): "When Played: Create 2 Spy
    tokens.  If damage would be dealt to this unit, you may defeat another friendly
    unit that shares a trait with this unit.  If you do, prevent that damage."

    Two specs: a plain ``WhenPlayed`` creating 2 Spy token units (the TokenUnit def
    SEC_1, 0/2 Official — so her own tokens share her Official trait and are eligible
    sacrifices), and the ``InteractiveDamagePrevention`` marker (the replacement).  The
    marker is read at BOTH damage sinks: the combat half (``_deal_damage_with_shield``'s
    one-shot flag + the pre-step2 ``_armed_combat_preventions`` checkpoint) and the
    ability half (``resolver._apply_deal_damage``'s deferred ``ability_damage_prevention``
    decision).  Indirect damage needs no coverage — its receiving player assigns the
    sink and so never places it on a unit they would rather protect."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Spy", count=2)],
        ),
        InteractiveDamagePrevention(),
    ]


# ── Group chancellor-palpatine:01 — Direct damage & removal ───────────────────

@card_ability("SEC", "34")
def _cad_bane():
    """SEC_34 — Cad Bane (Unit, Bounty Hunter/Underworld, 4/5; Plot — keyword
    layer): "When Played: You may defeat a unit with 2 or less remaining HP."

    Plot is the keyword engine.  An optional ``WhenPlayed`` (the "you may")
    ``DefeatUnit`` targeting any unit (friendly or enemy) with 2 or less remaining
    HP (the new ``remaining_hp_le_2`` predicate: effective HP − damage ≤ 2).
    Auto-declines when no unit is low enough."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       predicates=("remaining_hp_le_2",)))],
        optional=True,
    )


def _charged_with_murder_disclose(state, source_ci, target_id, event_ctx):
    """Charged with Murder SEC_76: ``target_id`` is the pre-chosen damaged
    non-leader unit.  Push disclose Vigilance+Vigilance → defeat it (the new
    ``defeat`` disclose-payoff arm).  ``target_id`` is None when there is no damaged
    non-leader unit → the mandatory targeted effect fizzled, so nothing is
    disclosed."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Vigilance", "Vigilance"],
                  payoff="defeat",
                  payoff_args={"target_id": target_id})
    return state


@card_ability("SEC", "76")
def _charged_with_murder():
    """SEC_76 — Charged with Murder (Event, Law): "You may disclose
    [Vigilance][Vigilance] (reveal cards from your hand with these aspect icons
    among them).  If you do, defeat a damaged non-leader unit."

    The Syril Karn SEC_133 pre-chosen-disclose convention: one CustomEffect.target
    first picks the victim (a damaged non-leader unit, ``controller="any"`` — a
    documented simplification of "a … unit"), then pushes the ``disclose`` decision
    (two Vigilance icons).  "If you do, defeat it" is the new ``defeat`` arm of
    ``_apply_disclose_payoff`` (reuses ``_apply_defeat_unit``).  With no damaged
    non-leader unit the mandatory targeted effect fizzles (no prompt), so nothing is
    disclosed; the "you may" otherwise lives in the disclose Decline."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_charged_with_murder_disclose,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("damaged", "non_leader")),
        ),
    ])


@card_ability("SEC", "77")
def _retaliation():
    """SEC_77 — Retaliation (Event, Tactic): "Defeat a unit that dealt damage to a
    base this phase."

    A plain mandatory ``EventAbility`` with one ``DefeatUnit`` narrowed by the new
    ``dealt_damage_to_base_this_phase`` predicate (backed by
    ``game_memory.units_dealt_base_damage_this_round`` — units that dealt combat
    damage by attacking a base this round; "this round" == "this phase").  The
    target is non-fixed (the controller picks among the eligible units);
    mandatory-if-able, so with no such unit it fizzles cleanly with no prompt."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              predicates=("dealt_damage_to_base_this_phase",))),
    ])


@card_ability("SEC", "241")
def _political_bully():
    """SEC_241 — Political Bully (Unit, Official/Republic, 2/3): "When Played: If you
    control another Official unit, you may deal 2 damage to a ground unit."

    An optional ``WhenPlayed`` (the "you may") gated by the
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` condition with param "Official" (the "If you
    control **another** Official unit" clause — excludes Political Bully itself, which
    is Official; so it is offered only when a second Official unit is in play).  The
    payoff is a plain ``DealDamage(2, …)`` targeting any ground unit
    (``controller="any"``)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 param="Official"),
    )


# ── chancellor-palpatine:02 — Card advantage & disruption ────────────────────

def _has_plot(card_def) -> bool:
    """A card_def carrying the Plot keyword (printed on the card)."""
    return "Plot" in (getattr(card_def, "keywords", ()) or ())


@card_ability("SEC", "1")
def _chancellor_palpatine():
    """SEC_1 — Chancellor Palpatine (Leader, Official/Republic, 6/8, Plot).

    Deployed side:
      * Action [1 resource, Exhaust]: Search the top 5 cards of your deck for a card
        with Plot, reveal it, and draw it. (Put the other cards on the bottom of your
        deck in a random order.)  → an ``ActivatedAbility`` (``deployed_only``) whose
        ``CustomEffect`` calls the ``deck_search`` seam (``push_deck_search``) with a
        "has Plot keyword" ``eligible`` predicate; ``count=1, up_to=False`` (mandatory
        if a Plot card is present — the Recruit SOR_123 convention), window 5, rest
        bottomed in a seeded-random order.
      * When Deployed: The next card you play using Plot this phase costs 3 less. →
        a ``WhenDeployed`` trigger recording a pending ``NextPlayDiscount`` with the
        new ``plot_only=True`` flag (``units_only=False`` = any card type, empty trait
        = any card).  The play-cost path only applies it on the Plot play path
        (``PlotPlay`` passes ``via_plot=True``), and it lifts at the phase rollover.

    The undeployed "Epic Action: deploy at 7+ resources" is the standard leader-deploy
    path (``DeployLeader`` reads the epic_action threshold) — no registration needed.
    """
    def _search_plot(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_deck_search
        push_deck_search(state, source_ci, count=1, window=5,
                         eligible=_has_plot, up_to=False)
        return state

    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_search_plot)],
            title="Search top 5 for a Plot card",
            deployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[NextPlayDiscount(trait="", amount=3, units_only=False,
                                      plot_only=True)],
            deployed_only=True,
        ),
    ]


# ── Group chancellor-palpatine:03 — Combat tricks, buffs & tempo ───────────────

@card_ability("SEC", "27")
def _the_chancellors_shuttle():
    """SEC_27 — The Chancellor's Shuttle (Unit, Republic/Transport/Vehicle, 1/3;
    Restore 1 — keyword layer): "When Defeated: If you control Chancellor Palpatine
    (as a leader or unit), you may give an Experience token to a unit."

    Restore 1 is the keyword layer.  An optional (the "you may") ``WhenDefeated``
    ``GiveToken("Experience", …)`` on any unit, gated by
    ``CONTROLLER_CONTROLS_NAMED("Chancellor Palpatine")`` — the "if you control
    Chancellor Palpatine" clause, matching either the leader SEC_1 (deployed or
    undeployed) or the unit SEC_82 by name substring (the Anakin SEC_201 named-control
    gate).  The condition gates trigger COLLECTION, so with no Palpatine the trigger
    is never offered.  The Shuttle has left play by When Defeated, so it is never a
    recipient of its own token."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Experience", TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                 param="Chancellor Palpatine"),
    )


def _cantwell_disclose(state, source_ci, target_id, event_ctx):
    """Cantwell Arrestor Cruiser SEC_37 payoff: pick an enemy unit up front, then
    disclose Vigilance×2 + Villainy → exhaust that unit and keep it tapped (the
    ``exhaust_unit`` disclose payoff with ``lock_round``).  ``target_id`` is None
    when there is no enemy unit → no disclose (nothing to exhaust)."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(
        state, source_ci, ["Vigilance", "Vigilance", "Villainy"],
        payoff="exhaust_unit",
        payoff_args={"target_id": target_id, "lock_round": True},
    )
    return state


@card_ability("SEC", "37")
def _cantwell_arrestor_cruiser():
    """SEC_37 — Cantwell Arrestor Cruiser (Unit, Capital Ship/Imperial/Vehicle, 6/7):
    "When Played: You may disclose [Vigilance][Vigilance][Villainy] (reveal cards from
    your hand with these aspect icons among them). If you do, exhaust an enemy unit.
    That unit can't ready while this unit is in play."

    A MANDATORY ``WhenPlayed`` whose one ``CustomEffect`` first picks the enemy unit
    (``TargetSpec`` enemy unit — a cosmetic reorder of "disclose, then exhaust an
    enemy unit", the Syril Karn SEC_133 convention), then pushes the ``disclose``
    decision — the "you may" lives in the disclose Decline, so no double-``optional``.
    On a successful disclose the ``exhaust_unit`` payoff exhausts the chosen unit and
    flags it ``cannot_ready_this_round``.  DEVIATION (documented): "can't ready while
    this unit is in play" is approximated as "can't ready this round" via the existing
    ``cannot_ready_this_round`` flag (the faithful persistent while-in-play lock would
    need a new ready-lock modifier kind, out of scope for this no-new-primitive group).
    With no enemy unit the mandatory targeted effect fizzles (no prompt), so nothing
    is disclosed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_cantwell_disclose,
            target=TargetSpec(controller="enemy", kind="unit"),
        )],
    )


@card_ability("SEC", "55")
def _dhani_pilgrim():
    """SEC_55 — Dhani Pilgrim (Unit, Fringe, 1/3): "When Played/When Defeated: Heal 1
    damage from your base."

    Two mandatory triggers (a ``WhenPlayed`` and a ``WhenDefeated``), each a single
    ``Heal(1, friendly base)`` auto-targeting the controller's own base
    (``fixed=EACH_FRIENDLY`` — the Grassroots Resistance SEC_258 heal-own-base
    convention).  A no-op when the base is already undamaged."""
    heal = Heal(1, TargetSpec(controller="friendly", kind="base",
                              fixed=EACH_FRIENDLY))
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[heal]),
        TriggerAbility(trigger=WhenDefeated(), effects=[heal]),
    ]


@card_ability("SEC", "79")
def _corrupt_politician():
    """SEC_79 — Corrupt Politician (Unit, Official/Republic, 2/2): "While you control
    more units than an opponent, this unit gains Sentinel."

    The conditional-self-grant pattern (Nubian Star Skiff SEC_116 / Hunting Nexu
    SHD_168): a ``ConstantAbility(target=SELF, KeywordGrant("Sentinel"))`` gated by
    the new ``CONTROLLER_MORE_UNITS_THAN_OPPONENT`` condition (strictly more units in
    play than the opponent), read passively by ``has_keyword``.  Registering this
    conditional self-grant makes the keyword sanitiser strip the mis-tagged printed
    "Sentinel" (reminder-text tag), so the ability — not an always-on printed bar —
    owns the keyword."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel", 0)],
        condition=ConditionCheck(Condition.CONTROLLER_MORE_UNITS_THAN_OPPONENT),
    )


@card_ability("SEC", "81")
def _major_partagaz():
    """SEC_81 — Major Partagaz (Unit, Imperial/Official, 0/6; Overwhelm — keyword
    layer): "When another friendly Official unit attacks: This unit gets +2/+2 for
    this phase."

    Overwhelm is the keyword layer.  A ``WhenUnitAttacks`` observer (Jedi Temple
    LOF_23 pattern) filtered to a friendly Official unit — the resolver never fires
    it for the source itself, so "another" is intrinsic (no ``not_self`` needed).  Its
    one mandatory ``ModifyStats(+2/+2, fixed=SELF, THIS_PHASE)`` buffs Partagaz for
    the phase."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(
            filter=TargetSpec(controller="friendly", kind="unit",
                              traits=("Official",))),
        effects=[ModifyStats(power=2, hp=2,
                             target=TargetSpec(kind="unit", fixed=SELF),
                             duration=Duration.THIS_PHASE)],
    )


def _mas_amedda_tokens(state, source_ci, target_id, event_ctx):
    """Mas Amedda SEC_84 WhenPlayed: give an Experience token to each of up to 2 other
    Official units (the Medal Ceremony SOR_245 select_token decision; ``not_self`` →
    "other")."""
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Experience", max_targets=2,
        controller="any", kind="unit", traits=["Official"],
        predicates=["not_self"],
    )
    return state


@card_ability("SEC", "84")
def _mas_amedda():
    """SEC_84 — Mas Amedda (Unit, Official/Republic, 3/4; Plot — keyword layer): "When
    Played: Give an Experience token to each of up to 2 other Official units."

    Plot is the keyword layer.  A mandatory ``WhenPlayed`` whose one ``CustomEffect``
    pushes the ``select_token`` decision ("give a token to up to N units" — Medal
    Ceremony SOR_245), filtered to Official units excluding Mas Amedda himself
    (``not_self`` → "other").  Pushed only when ≥1 eligible unit exists, so it
    fizzles cleanly otherwise (the "up to")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_mas_amedda_tokens)],
    )


def _rampart_disclose(state, source_ci, target_id, event_ctx):
    """Vice Admiral Rampart SEC_85 payoff: disclose Command×2 + Villainy → give an
    Experience token to each of up to 2 other units (the new ``select_token`` disclose
    payoff arm, reusing push_select_token; ``not_self`` → "other")."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Command", "Command", "Villainy"],
        payoff="select_token",
        payoff_args={"token_type": "Experience", "max_targets": 2,
                     "predicates": ["not_self"]},
    )
    return state


@card_ability("SEC", "85")
def _vice_admiral_rampart():
    """SEC_85 — Vice Admiral Rampart (Unit, Imperial/Official, 3/6): "On Attack: You
    may disclose [Command][Command][Villainy] (reveal cards from your hand with these
    aspect icons among them). If you do, give an Experience token to each of up to 2
    other units."

    A MANDATORY ``OnAttack`` whose one ``CustomEffect`` pushes the ``disclose``
    decision (the Ahsoka Tano SEC_96 pattern) — the "you may" lives in the disclose
    Decline.  The "if you do" payoff is the new ``select_token`` arm of
    ``_apply_disclose_payoff``, which reuses push_select_token to give an Experience
    token to up to 2 other units (``not_self`` → "other").  push_disclose no-ops with
    no prompt when the controller's hand can't cover Command×2+Villainy."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_rampart_disclose)],
    )


# ══ Group chancellor-palpatine:04 — Combat tricks, buffs & tempo ═════════════════

def _budget_scheming_tokens(state, source_ci, target_id, event_ctx):
    """Budget Scheming SEC_124: give an Experience token to each of up to 3 Official
    units (the Medal Ceremony SOR_245 select_token decision).  No ``not_self`` — it
    is an event with no source unit on the board."""
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Experience", max_targets=3,
        controller="any", kind="unit", traits=["Official"],
    )
    return state


@card_ability("SEC", "124")
def _budget_scheming():
    """SEC_124 — Budget Scheming (Event, Law): "Give an Experience token to each of
    up to 3 Official units."

    Exactly the Medal Ceremony SOR_245 pattern: an ``EventAbility`` whose one
    ``CustomEffect`` pushes the ``select_token`` decision ("give a token to up to N
    units"), filtered to Official units.  The card does not say "friendly", so any
    Official unit is eligible; because Experience helps the recipient the
    controller chooses and so simply never picks an enemy.  Pushed only when ≥1
    Official unit exists, so it fizzles cleanly otherwise (the "up to")."""
    return EventAbility(effects=[CustomEffect(fn=_budget_scheming_tokens)])


def _when_has_become_now_effect(state, source_ci, target_id, event_ctx):
    """When Has Become Now SEC_245: play a Plot card from resources (paying its
    cost); if you do, put the top card of your deck into play as a resource."""
    from swu.engine.actions import push_plot_ability
    push_plot_ability(state, source_ci, ramp=True)
    return state


@card_ability("SEC", "245")
def _when_has_become_now():
    """SEC_245 — When Has Become Now (Event, Trick; Plot — keyword layer): "Play a
    card with Plot from your resources (paying its cost). If you do, put the top
    card of your deck into play as a resource." (ERRATA phrasing — the ramp is
    conditional on actually playing a Plot card.)

    An ``EventAbility`` whose one ``CustomEffect`` pushes a single-shot ``plot``
    decision via ``push_plot_ability`` (the existing Plot decision / PlotPlay path,
    marked ``plot_ability`` so PlotPlay resolves it after ONE play and then runs
    the "if you do" ramp — ``_resource_top_of_deck``, a net +1 resource on top of
    Plot's own replace-with-deck-top).  push_plot_ability no-ops with no prompt
    when the controller has no affordable Plot card in resources, so the ramp
    correctly does not happen (you did not play a card).  The event itself carries
    Plot (the keyword layer), letting it be played from resources too."""
    return EventAbility(effects=[CustomEffect(fn=_when_has_become_now_effect)])


# ── Group chancellor-palpatine:05 — Miscellaneous abilities ───────────────────

@card_ability("SEC", "31")
def _nute_gunray():
    """SEC_31 — Nute Gunray (Unit, Official/Separatist, Grit + Sentinel — keyword
    layers): "When Played/On Attack: You may give another friendly Official unit
    Sentinel for this phase."

    Grit and Sentinel on Nute himself are the keyword layers.  The functional text
    is two otherwise-identical optional triggers (a ``WhenPlayed`` and an
    ``OnAttack``, the "you may"), each a ``GrantKeyword("Sentinel", THIS_PHASE)``
    targeting another friendly Official unit (the Bodhi Rook LAW_104 / General
    Grievous TWI_15 grant-Sentinel-for-the-phase pattern, restricted by
    ``traits=("Official",)`` and ``not_self`` → "another").  Auto-declines when no
    OTHER friendly Official unit is in play (Nute himself is excluded)."""
    grant = [GrantKeyword(
        "Sentinel", 0,
        TargetSpec(controller="friendly", kind="unit",
                   traits=("Official",), predicates=("not_self",)),
        Duration.THIS_PHASE)]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(grant), optional=True),
        TriggerAbility(trigger=OnAttack(), effects=list(grant), optional=True),
    ]


def _sly_moore_debuff(state, source_ci, target_id, event_ctx):
    """Sly Moore SEC_33 WhenPlayed: for this phase, each enemy unit gets -2/-0 while
    it's attacking a base.  Applies, to each current enemy unit, a ``this_phase``
    stats modifier carrying the ``while_attacking_base`` flag — read only at the
    base-attack ``compute_power`` site (``attacking_base=True``), so the -2 lands
    exactly when that unit attacks a base and nowhere else.  The Bo-Katan SEC_51
    per-unit-snapshot pattern (each enemy unit in play gets its own modifier),
    gated to base attacks."""
    from swu.engine.state import Modifier
    enemy = state.players[1 - state.player_index(source_ci.owner_id)]
    for u in enemy.ground_arena + enemy.space_arena:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=u.instance_id,
            kind="stats",
            value={"power": -2, "hp": 0, "while_attacking_base": True},
            duration="this_phase",
        ))
    return state


@card_ability("SEC", "33")
def _sly_moore():
    """SEC_33 — Sly Moore (Unit, Official/Republic, Plot — keyword layer): "When
    Played: For this phase, each enemy unit gets -2/-0 while it's attacking a base."

    Plot is the keyword layer.  A mandatory ``WhenPlayed`` whose one no-target
    ``CustomEffect`` snapshots the enemy units in play and gives each a ``this_phase``
    ``while_attacking_base`` stats modifier (see ``_sly_moore_debuff``).

    ENGINE ADDITION (small, contained — flagged for review): a new
    ``attacking_base`` combat-context gate on ``compute_power`` (mirroring the
    existing ``while_attacking_unit`` / ``while_defending`` gates), passed
    ``True`` only from the base-attack power site, plus the ``while_attacking_base``
    modifier flag it reads.  No trigger/decision machinery is touched; the debuff is
    a plain stats Modifier."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_sly_moore_debuff)],
    )


def _isb_shuttle_token(state, source_ci, target_id, event_ctx):
    """ISB Shuttle SEC_83 WhenPlayed: if a friendly unit was defeated this phase,
    create a Spy token.  "A friendly unit was defeated this phase" reads the
    ``defeated_controllers_this_round`` tracker (the controller-at-death of every
    unit defeated this round == this phase — the Darth Sion SEC_35 / Oppression
    Breeds Rebellion SEC_158 precedent): the controller's own id present means a
    friendly unit died.  The Spy token is the create-token-unit primitive."""
    ctrl = state.player_by_id(source_ci.owner_id)
    if ctrl.player_id in state.game_memory.defeated_controllers_this_round:
        from swu.engine.actions import _create_token_units
        _create_token_units(state, ctrl, "Spy", 1)
    return state


@card_ability("SEC", "83")
def _isb_shuttle():
    """SEC_83 — ISB Shuttle (Unit, Imperial/Transport/Vehicle): "When Played: If a
    friendly unit was defeated this phase, create a Spy token."

    A mandatory ``WhenPlayed`` whose one no-target ``CustomEffect`` checks the
    "a friendly unit was defeated this phase" condition inline against
    ``game_memory.defeated_controllers_this_round`` and, when it holds, creates one
    Spy token (the create-token-unit primitive).  Inline like Oppression Breeds
    Rebellion SEC_158 — no new condition atom needed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_isb_shuttle_token)],
    )


@card_ability("SEC", "87")
def _dedra_meero():
    """SEC_87 — Dedra Meero (Unit, Imperial/Official, Ambush — keyword layer): "On
    Attack: Create a Spy token."

    Ambush is the keyword layer.  A mandatory ``OnAttack`` trigger with one
    non-targeted ``CreateTokenUnit("Spy", 1)`` (the create-token-unit primitive,
    ahsoka-tano:05)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CreateTokenUnit("Spy", count=1)],
    )


@card_ability("SEC", "92")
def _i_am_the_senate():
    """SEC_92 — I Am the Senate (Event, Law): "Create 5 Spy tokens."

    A plain ``EventAbility`` with one non-targeted ``CreateTokenUnit("Spy", 5)``
    (the create-token-unit primitive)."""
    return EventAbility(effects=[CreateTokenUnit("Spy", count=5)])


# ── Group sec-set:01 — Direct damage & removal ────────────────────────────────
# Six Leaders (front-side ``text`` = the UNDEPLOYED ability, ``deploy_box`` = the
# DEPLOYED-unit ability — gated with ``undeployed_only`` / ``deployed_only``) plus
# one upgrade.  Every Epic Action is the plain "deploy this leader" the engine
# already implements, so none is registered.


def _jabba_sec2_pick_dealer(state, source_ci, target_id, event_ctx):
    """Jabba SEC_2 undeployed, step 1: record the chosen friendly DAMAGED unit and
    how hard it hits (2 if it carries 3+ damage, else 1) — the shared-``event_ctx``
    chain (Asajj JTL_1 / Haymaker LAW_168), which is also the "if you do" binding:
    with no damaged friendly, the enemy half is gated off by ``requires_prior_target``
    and fizzles without a prompt."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, dealer = res
    event_ctx["prior_target_id"] = target_id
    event_ctx["jabba_sec2_amount"] = 2 if dealer.damage >= 3 else 1
    return state


def _jabba_sec2_deal(state, source_ci, target_id, event_ctx):
    """Jabba SEC_2 undeployed, step 2: the recorded friendly unit deals the recorded
    amount to the chosen enemy unit (the damage is attributed to the DEALER, which is
    what "that unit deals" means for a damage-source observer)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    dealer_id = event_ctx.get("prior_target_id")
    res = state.find_instance(dealer_id) if dealer_id else None
    name = (res[1].card_def.display_name if res is not None
            else source_ci.card_def.display_name)
    return _apply_deal_damage(
        state, target_id, int(event_ctx.get("jabba_sec2_amount", 1) or 1), name,
        dealer_id=dealer_id)


def _jabba_sec2_retaliate(state, source_ci, target_id, event_ctx):
    """Jabba SEC_2 deployed: the friendly unit that was just dealt combat damage and
    survived deals THAT MUCH to the chosen enemy unit, and the round's single use is
    spent (the Toro Calican SHD_239 ``:trig`` marker — set only here, on resolution,
    so declining the "you may" does not burn the round's use).

    "Another friendly unit" — a self-hit is dropped here rather than in the trigger
    filter, because ``WhenFriendlyUnitDealtCombatDamage`` filters only on traits."""
    dmg_id = event_ctx.get("dealt_combat_damage_to")
    amount = int(event_ctx.get("combat_damage_amount", 0) or 0)
    if target_id is None or not dmg_id or dmg_id == source_ci.instance_id or amount <= 0:
        return state
    res = state.find_instance(dmg_id)
    name = (res[1].card_def.display_name if res is not None
            else source_ci.card_def.display_name)
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, amount, name, dealer_id=dmg_id)


@card_ability("SEC", "2")
def _jabba_the_hutt_sec():
    """SEC_2 — Jabba the Hutt (Leader, Hutt/Underworld).

    Undeployed: "Action [1 resource, Exhaust]: A friendly damaged unit deals 1 damage
    to an enemy unit.  If the friendly unit has 3 or more damage on it, it deals 2
    damage instead."  An ``ActivatedAbility`` (``PayResources(1)`` + ``ExhaustSelf``)
    whose two ``CustomEffect.target`` steps are the shared-``event_ctx`` chain: the
    first picks the damaged friendly and computes the magnitude, the second picks the
    enemy unit (gated by ``requires_prior_target``) and deals it.

    Deployed: "When another friendly unit is dealt damage and survives: You may have
    that unit deal that much damage to an enemy unit.  Use this ability only once each
    round."  An optional ``WhenFriendlyUnitDealtCombatDamage`` observer (whose firing
    site only fires for a unit still in play, so "and survives" is intrinsic), limited
    by ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``.
    DEVIATION (documented): the card's rules insert says Jabba triggers on combat AND
    non-combat damage; the observer trigger available today covers COMBAT damage only,
    so ability/indirect damage to a friendly unit does not offer the retaliation."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            undeployed_only=True,
            effects=[
                CustomEffect(fn=_jabba_sec2_pick_dealer,
                             target=TargetSpec(controller="friendly", kind="unit",
                                               predicates=("damaged",))),
                CustomEffect(fn=_jabba_sec2_deal,
                             target=TargetSpec(controller="enemy", kind="unit",
                                               predicates=("requires_prior_target",))),
            ],
            title="A friendly damaged unit deals damage to an enemy unit",
        ),
        TriggerAbility(
            trigger=WhenFriendlyUnitDealtCombatDamage(),
            deployed_only=True,
            optional=True,
            condition=ConditionCheck(
                Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
            effects=[CustomEffect(fn=_jabba_sec2_retaliate,
                                  target=TargetSpec(controller="enemy", kind="unit"))],
        ),
    ]


def _lama_su_hand_upgrade(state, source_ci, target_id, event_ctx):
    """Lama Su SEC_3 undeployed: the host is chosen first (a friendly non-Vehicle
    unit), then the ``play_upgrade_from_hand`` decision is pushed pinned to that host
    at 1 resource off, with the new ``then_damage_host`` "if you do" hook carrying the
    1 damage — so declining the play deals nothing."""
    if target_id is None:
        return state
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(state, source_ci, free=False, cost_reduction=1,
                                host_id=target_id, then_damage_host=1)
    return state


def _lama_su_discard_upgrade(state, source_ci, target_id, event_ctx):
    """Lama Su SEC_3 deployed: the same shape from the DISCARD pile
    (``from_discard_only``), with no damage clause."""
    if target_id is None:
        return state
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(state, source_ci, free=False, cost_reduction=1,
                                host_id=target_id, from_discard_only=True)
    return state


@card_ability("SEC", "3")
def _lama_su():
    """SEC_3 — Lama Su (Leader, Kaminoan/Official).

    Undeployed: "Action [Exhaust]: Play an upgrade from your hand on a friendly
    non-Vehicle unit.  It costs 1 resource less.  If you do, deal 1 damage to that
    unit."  Deployed: "When this unit completes an attack (and survives): You may play
    an upgrade from your discard pile on a friendly non-Vehicle unit.  It costs 1
    resource less."

    Both are the existing ``push_play_upgrade_from_hand`` seam with the host pinned by
    a leading ``CustomEffect.target`` (the only way to express "on a friendly
    non-Vehicle unit" — the host enumeration has no trait filter).  ``WhenAttackEnds``
    already means "completed an attack and survived".  The push no-ops (no prompt)
    when no affordable upgrade exists, so the Action stays legal but does nothing —
    matching how the printed Action reads."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            undeployed_only=True,
            effects=[CustomEffect(
                fn=_lama_su_hand_upgrade,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("non_vehicle",)))],
            title="Play an upgrade from hand on a friendly non-Vehicle unit",
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            deployed_only=True,
            optional=True,
            effects=[CustomEffect(
                fn=_lama_su_discard_upgrade,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("non_vehicle",)))],
        ),
    ]


def _satine_heal_then_base(state, source_ci, target_id, event_ctx):
    """Satine SEC_5 undeployed: heal up to 2 from the chosen unit, then deal exactly
    that much to your OWN base.

    DEVIATION (documented): "up to 2" is resolved as "as much as possible, capped at
    2" — the player picks WHICH unit but not HOW MUCH.  The engine has no
    choose-a-magnitude decision, and the ``damaged`` predicate already keeps the
    ability from being offered a target it could not heal, so the only lost line is
    deliberately healing 1 off a 2-damage unit to take 1 less base damage."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    healed = min(2, unit.damage)
    if healed <= 0:
        return state
    from swu.abilities.resolver import _apply_heal, _apply_deal_damage
    state = _apply_heal(state, source_ci, target_id, healed)
    own = state.player_by_id(source_ci.owner_id)
    if own.base_instance is not None:
        state = _apply_deal_damage(state, own.base_instance.instance_id, healed,
                                   source_ci.card_def.display_name)
    return state


@card_ability("SEC", "5")
def _satine_kryze():
    """SEC_5 — Satine Kryze (Leader, Mandalorian/Official).

    Undeployed: "Action [Exhaust]: Heal up to 2 damage from a unit.  If you do, deal
    that much damage to your base."  One ``CustomEffect.target`` over any DAMAGED unit
    (the predicate makes the ability fizzle cleanly with nothing to heal) that heals
    and then self-damages by the same amount, so the "if you do" is bound by
    construction.  Deployed: Restore 4 — pure keyword layer, nothing to register."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        undeployed_only=True,
        effects=[CustomEffect(
            fn=_satine_heal_then_base,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("damaged",)))],
        title="Heal up to 2 from a unit, then deal that much to your base",
    )


def _dedra_meero_offer(state, source_ci, target_id, event_ctx):
    """Dedra Meero SEC_10 undeployed: hand the chosen enemy unit's controller the
    ``say_no`` decision — AllowEffect deals 2 damage to their own unit, SayNo lets
    Dedra's controller draw 1.  Exactly the I Am Your Father SOR_233 seam with the
    roles as printed ("Its controller MAY deal 2 damage to it.  If they don't, draw a
    card")."""
    if target_id is None:
        return state
    from swu.engine.actions import push_say_no
    push_say_no(state, source_ci, target_id, damage=2, draw_on_refuse=1)
    return state


@card_ability("SEC", "10")
def _dedra_meero():
    """SEC_10 — Dedra Meero (Leader, Imperial/Official).

    Undeployed: "Action [1 resource, Exhaust]: Choose an enemy unit.  Its controller
    may deal 2 damage to it.  If they don't, draw a card."  The ``say_no`` seam.
    Deployed: "While you have more cards in hand than an opponent, this unit gains
    Raid 2" — a self-targeted ``ConstantAbility(KeywordGrant)`` gated by the new
    ``CONTROLLER_MORE_CARDS_IN_HAND_THAN_OPPONENT`` atom (the hand-size sibling of
    ``CONTROLLER_MORE_UNITS_THAN_OPPONENT``)."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            undeployed_only=True,
            effects=[CustomEffect(
                fn=_dedra_meero_offer,
                target=TargetSpec(controller="enemy", kind="unit"))],
            title="An enemy unit's controller may damage it, or you draw",
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Raid", 2)],
            condition=ConditionCheck(
                Condition.CONTROLLER_MORE_CARDS_IN_HAND_THAN_OPPONENT),
        ),
    ]


_LUTHEN_TRIGGER = dict(
    filter=TargetSpec(controller="friendly", kind="unit",
                      predicates=("defeated_while_attacking",)),
)


def _luthen_exhaust_then_damage(state, source_ci, target_id, event_ctx):
    """Luthen SEC_13 undeployed: exhaust the leader, then deal 1 to the chosen unit
    or base.  Bundled in ONE CustomEffect so "If you do [exhaust]" holds — the
    optional trigger's Accept IS the "you may exhaust" (the Boba Fett JTL_9
    leader-exhaust convention; a separate ``ExhaustCard(fixed=SELF)`` effect cannot
    express it, an undeployed leader in the base zone being no arena unit)."""
    if target_id is None:
        return state
    source_ci.exhausted = True
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1,
                              source_ci.card_def.display_name)


@card_ability("SEC", "13")
def _luthen_rael():
    """SEC_13 — Luthen Rael (Leader, Rebel).  BOTH sides carry the same trigger:

    Undeployed: "When a friendly unit is defeated while attacking: You may exhaust
    this leader.  If you do, deal 1 damage to a unit or base."  Deployed: the same
    trigger for a flat 2 damage, no exhaust.

    "While attacking" is the new ``defeated_while_attacking`` predicate on the
    ``WhenUnitDefeated`` filter, backed by the ``while_attacking=True`` flag the two
    attacker-death sites in the combat pipeline now pass to ``_defeat_unit`` (it
    stamps the defeat's own event_ctx — no new state, and every other defeat site is
    untouched).  The undeployed half bundles its exhaust into the damage
    ``CustomEffect`` so "If you do" holds, and is gated by ``SOURCE_READY`` so it is
    not offered once Luthen is already exhausted (the Boba Fett JTL_9 convention)."""
    return [
        TriggerAbility(
            trigger=WhenUnitDefeated(**_LUTHEN_TRIGGER),
            undeployed_only=True,
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
            effects=[CustomEffect(
                fn=_luthen_exhaust_then_damage,
                target=TargetSpec(controller="any", kind="unit_or_base"))],
        ),
        TriggerAbility(
            trigger=WhenUnitDefeated(**_LUTHEN_TRIGGER),
            deployed_only=True,
            optional=True,
            effects=[
                DealDamage(2, TargetSpec(controller="any", kind="unit_or_base")),
            ],
        ),
    ]


@card_ability("SEC", "14")
def _sly_moore():
    """SEC_14 — Sly Moore (Leader, Force/Imperial/Official).

    Undeployed: "Action [1 resource, Exhaust]: If there are 4 or more exhausted units
    in play, create a Spy token."  A ``ConditionalEffect`` on the new
    ``N_PLUS_EXHAUSTED_UNITS_IN_PLAY`` atom (both players' arenas — the card says "in
    play"), which is exactly the printed shape: the rules insert confirms the Action
    may still be taken below the threshold, creating nothing.
    Deployed: "On Attack: You may deal 2 damage to an exhausted unit."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            undeployed_only=True,
            effects=[ConditionalEffect(
                condition=ConditionCheck(
                    Condition.N_PLUS_EXHAUSTED_UNITS_IN_PLAY, param=4),
                if_true=(CreateTokenUnit("Spy", count=1),),
                if_false=(),
            )],
            title="If 4+ exhausted units are in play, create a Spy token",
        ),
        TriggerAbility(
            trigger=OnAttack(),
            deployed_only=True,
            optional=True,
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                              predicates=("exhausted",)))],
        ),
    ]


@card_ability("SEC", "39")
def _creditors_claim():
    """SEC_39 — Creditor's Claim (Upgrade, Supply, +2/+2): "Attached unit gains: 'When
    Defeated: You may defeat a unit with 3 or less remaining HP.'"

    The plain ``GrantedAbility`` shape (Armed to the Teeth SHD_175): the wrapped
    optional ``WhenDefeated`` resolves FROM THE HOST, so the "You" is the host's
    controller, as the card's rules insert requires.  "3 or less remaining HP" is the
    existing ``TargetSpec.hp_remaining_max`` filter — no new predicate."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       hp_remaining_max=3))],
    ))


# ── Group sec-set:02 — Direct damage & removal ────────────────────────────────


@card_ability("SEC", "42")
def _cassian_andor_sec():
    """SEC_42 — Cassian Andor (Unit, Fringe, 2/2): "While this unit is defending, the
    attacker gets -2/-0.  If an enemy card ability would deal damage to this unit,
    prevent 2 of that damage."

    The first clause is Lando Calrissian LAW_108 verbatim — a ``while_defending``
    ``ConstantAbility`` whose target is the enemy attacker, so ``compute_power``
    applies it only to the unit actually attacking Cassian.  The second is the
    ``DamagePrevention`` marker in its new ``on_self`` shape with both narrowing
    flags: ``ability_only`` (his rules insert is explicit that combat damage is not a
    card ability) and ``enemy_only`` (a friendly ability's damage is not prevented).
    Both are pure reads at existing chokepoints."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="enemy", kind="unit"),
            effects=[StatBonus(power=-2, hp=0)],
            while_defending=True,
        ),
        DamagePrevention(amount=2, on_self=True, ability_only=True, enemy_only=True),
    ]


@card_ability("SEC", "50")
def _vigil():
    """SEC_50 — Vigil (Unit, Capital Ship/Resistance/Vehicle, 5/9; Plot): "If damage
    would be dealt to another friendly unit, prevent 1 of that damage.  If damage
    would be dealt to this unit by another card, deal that much damage plus 1
    instead."

    An ``aura_target`` ``DamagePrevention`` (every OTHER friendly unit, ``not_self``)
    plus its exact dual, the new ``DamageAmplification`` marker — both pure reads at
    the single ``_deal_damage_with_shield`` chokepoint, so they cover combat and
    ability damage alike, as printed.  Plot is the keyword layer."""
    return [
        DamagePrevention(
            amount=1,
            aura_target=TargetSpec(controller="friendly", kind="unit",
                                   predicates=("not_self",)),
        ),
        DamageAmplification(amount=1, by_another_card=True),
    ]


@card_ability("SEC", "53")
def _one_in_a_million():
    """SEC_53 — One in a Million (Event, Gambit; Plot): "This card can't be played
    from your hand.  Defeat a unit with power and remaining HP both equal to the
    number of ready resources you control."

    The new ``CannotPlayFromHand`` marker (read only at the hand-play enumeration, so
    the Plot route out of the resource zone is untouched — which is the card's whole
    design) plus a mandatory ``DefeatUnit`` narrowed by the new
    ``power_and_hp_equal_source_ready_resources`` predicate.  Mandatory-if-able: with
    no matching unit it fizzles cleanly, no prompt."""
    return [
        CannotPlayFromHand(),
        EventAbility(effects=[
            DefeatUnit(TargetSpec(
                controller="any", kind="unit",
                predicates=("power_and_hp_equal_source_ready_resources",))),
        ]),
    ]


@card_ability("SEC", "78")
def _hyperspace_disaster():
    """SEC_78 — Hyperspace Disaster (Event, Disaster): "Defeat all space units."

    A plain ``EventAbility`` with one ``DefeatAllUnits`` filtered to the space arena
    (both controllers)."""
    return EventAbility(effects=[
        DefeatAllUnits(filter=TargetSpec(controller="any", kind="unit",
                                         arena="space")),
    ])


def _arihnda_pryce_sacrifice(state, source_ci, target_id, event_ctx):
    """Arihnda Pryce SEC_136: defeat the chosen friendly unit, and only then deal 4 to
    each enemy base — the "if you do" bound by construction (one CustomEffect, so a
    declined/absent target deals nothing)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit, _apply_deal_damage
    state = _apply_defeat_unit(state, target_id)
    name = source_ci.card_def.display_name
    for ps in state.players:
        if ps.player_id == source_ci.owner_id or ps.base_instance is None:
            continue
        state = _apply_deal_damage(state, ps.base_instance.instance_id, 4, name)
    return state


@card_ability("SEC", "136")
def _arihnda_pryce():
    """SEC_136 — Arihnda Pryce (Unit, Imperial, 4/4): "When Defeated: You may defeat
    another friendly unit.  If you do, deal 4 damage to each enemy base."

    An optional ``WhenDefeated`` with one ``CustomEffect.target`` over another
    friendly unit; the sacrifice and the payoff live in the same fn so "if you do"
    holds.  ``not_self`` is belt-and-braces — Pryce has already left play when her own
    When Defeated resolves."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[CustomEffect(
            fn=_arihnda_pryce_sacrifice,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)))],
    )


@card_ability("SEC", "139")
def _miraj_scintel():
    """SEC_139 — Miraj Scintel (Unit, Official/Separatist, 3/7; Overwhelm): "While a
    friendly unit is attacking a damaged unit, the attacker gains Overwhelm.  When
    Played: You may deal 3 damage to an undamaged unit."

    The grant is a ``while_attacking_unit`` ``ConstantAbility`` over friendly units
    carrying a ``KeywordGrant("Overwhelm")``.  DEVIATION (documented, and the standing
    convention for this shape — Moff Gideon SHD_7 / Jango Fett SHD_138): the keyword
    query layer sees no combat context, so the granted Overwhelm is reported for a
    friendly unit at all times rather than only while it attacks a DAMAGED unit.
    Overwhelm only does anything during an attack that defeats a defender, so the
    visible effect is limited to attacks on an *undamaged* defender."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit"),
            effects=[KeywordGrant("Overwhelm", 0)],
            while_attacking_unit=True,
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            optional=True,
            effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                              predicates=("undamaged",)))],
        ),
    ]


@card_ability("SEC", "143")
def _the_elite_squad():
    """SEC_143 — The Elite Squad (Unit, Imperial/Trooper, 6/8; Grit): "When
    Played/When damage is dealt to this unit: You may deal 2 damage to another unique
    unit."

    Two optional triggers sharing one effect.  DEVIATION (documented): the second is a
    ``WhenDealtCombatDamage`` observer, so it fires on COMBAT damage to this unit but
    not on ability or indirect damage — the same limit the observer family has carried
    since Phase-III Dark Trooper SHD_84 (its firing site is the combat pipeline).  The
    survivor clause is intrinsic there, which is right: a defeated Elite Squad has no
    ability to use."""
    hit = DealDamage(2, TargetSpec(controller="any", kind="unit",
                                   predicates=("unique", "not_self")))
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[hit]),
        TriggerAbility(trigger=WhenDealtCombatDamage(), optional=True, effects=[hit]),
    ]


# ── Group sec-set:03 — Direct damage & removal ────────────────────────────────


@card_ability("SEC", "144")
def _tempest_assault():
    """SEC_144 — Tempest Assault (Event, Tactic): "If you've dealt damage to an enemy
    base this phase, deal 2 damage to each enemy space unit."

    A ``ConditionalEffect`` on the existing
    ``CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE`` atom (param 1 = "dealt damage")
    wrapping a fixed ``EACH_ENEMY`` ``DealDamage`` narrowed to the space arena."""
    return EventAbility(effects=[ConditionalEffect(
        condition=ConditionCheck(
            Condition.CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE, param=1),
        if_true=(DealDamage(2, TargetSpec(controller="enemy", kind="unit",
                                          arena="space", fixed=EACH_ENEMY)),),
        if_false=(),
    )])


def _kaydel_connix_strip(state, source_ci, target_id, event_ctx):
    """Kaydel Connix SEC_149: defeat every NON-UNIQUE upgrade on the chosen unit.
    Token upgrades (Shield/Experience) are non-unique cards and are stripped too,
    which is what "all non-unique upgrades" says."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, host = res
    from swu.engine.actions import _defeat_attached_upgrade
    for upg in list(host.attached_upgrades):
        if not getattr(upg.card_def, "is_unique", False):
            _defeat_attached_upgrade(state, upg)
    return state


def _kaydel_has_a_target(state, source_ci, event_ctx):
    """Don't offer the "you may" when no unit in play carries a non-unique upgrade."""
    for ps in state.players:
        for u in ps.ground_arena + ps.space_arena:
            if any(not getattr(x.card_def, "is_unique", False)
                   for x in u.attached_upgrades):
                return True
    return False


@card_ability("SEC", "149")
def _kaydel_connix():
    """SEC_149 — Kaydel Connix (Unit, Resistance, 3/2; Plot): "When Played: You may
    defeat all non-unique upgrades on a unit."

    An optional ``WhenPlayed`` whose one ``CustomEffect.target`` (any unit) strips the
    host's non-unique upgrades through the existing ``_defeat_attached_upgrade``
    chokepoint (so each upgrade's own When Defeated resolves normally).  Its
    ``available_fn`` keeps the "you may" from being offered when no unit anywhere
    carries a strippable upgrade.  Plot is the keyword layer."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(
            fn=_kaydel_connix_strip,
            target=TargetSpec(controller="any", kind="unit"),
            available_fn=_kaydel_has_a_target)],
    )


def _valiant_commando_dive(state, source_ci, target_id, event_ctx):
    """Valiant Commando SEC_150: defeat this unit, then deal 3 to the base it just
    hit.  Bound in ONE CustomEffect so "If you do" holds.  "That base" is the base of
    the OPPONENT it was attacking — in two-player the one enemy base, read from the
    board rather than the event (the base-damage fire carries the dealer, not the
    base)."""
    from swu.abilities.resolver import _apply_defeat_unit, _apply_deal_damage
    victim = None
    for ps in state.players:
        if ps.player_id != source_ci.owner_id and ps.base_instance is not None:
            victim = ps.base_instance.instance_id
    state = _apply_defeat_unit(state, source_ci.instance_id)
    if victim is not None:
        state = _apply_deal_damage(state, victim, 3,
                                   source_ci.card_def.display_name)
    return state


@card_ability("SEC", "150")
def _valiant_commando():
    """SEC_150 — Valiant Commando (Unit, Rebel/Trooper, 3/3): "When this unit deals
    combat damage to a base: You may defeat this unit.  If you do, deal 3 damage to
    that base."

    An optional ``WhenDealsCombatDamageToBase`` (its self form — no ``filter``, so it
    matches only this unit) whose single non-targeted ``CustomEffect`` defeats the
    commando and then burns the enemy base for 3."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        optional=True,
        effects=[CustomEffect(fn=_valiant_commando_dive)],
    )


@card_ability("SEC", "152")
def _strike_force_x_wing():
    """SEC_152 — Strike Force X-Wing (Unit, Fighter/Rebel/Vehicle, 3/2; Plot): "When
    Played: You may deal 2 damage to a ready unit."

    An optional ``WhenPlayed`` ``DealDamage`` with the existing ``ready`` predicate
    (the mirror of Stinger Mantis LOF_198's ``exhausted``); with no ready unit on the
    board the "you may" is never offered.  Plot is the keyword layer."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          predicates=("ready",)))],
    )


def _kallus_spread(state, source_ci, target_id, event_ctx):
    """Alexsandr Kallus SEC_155 When Played: "Deal 2 damage to each of up to 3 ground
    units" — the ``select_damage`` seam (IG-2000 JTL_140) with ``amount_each=2``."""
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=2, max_targets=3,
                       arena="ground")
    return state


@card_ability("SEC", "155")
def _alexsandr_kallus():
    """SEC_155 — Alexsandr Kallus (Unit, Rebel/Spectre, 6/6; Raid): "While you have
    the initiative, each other friendly unique unit gains Raid 2.  When Played: Deal 2
    damage to each of up to 3 ground units."

    A ``ConstantAbility`` anthem over other friendly UNIQUE units (``unique`` +
    ``not_self``) gated by ``CONTROLLER_HAS_INITIATIVE``, plus a mandatory
    ``WhenPlayed`` adapter onto ``push_select_damage``.  Kallus's own printed Raid is
    the keyword layer (the anthem says "each OTHER")."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("unique", "not_self")),
            effects=[KeywordGrant("Raid", 2)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
        ),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_kallus_spread)]),
    ]


def _nemik_manifesto_burn(state, source_ci, target_id, event_ctx):
    """Nemik's Manifesto SEC_156's granted When Defeated: "Deal 1 damage to each enemy
    base for each other friendly Rebel unit."  ``source_ci`` is the HOST (the ability
    is granted to it), which has already left play when this resolves — so every
    surviving friendly Rebel unit is "another"."""
    from swu.engine.traits import get_traits
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena
            if u.instance_id != source_ci.instance_id
            and "Rebel" in get_traits(state, u))
    if n <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    for other in state.players:
        if other.player_id == ps.player_id or other.base_instance is None:
            continue
        state = _apply_deal_damage(state, other.base_instance.instance_id, n,
                                   source_ci.card_def.display_name)
    return state


@card_ability("SEC", "156")
def _nemiks_manifesto():
    """SEC_156 — Nemik's Manifesto (Upgrade, Item/Rebel): "Attach to a non-Vehicle
    unit.  Attached unit gains the Rebel trait and: 'When Defeated: Deal 1 damage to
    each enemy base for each other friendly Rebel unit.'"

    The attach restriction is parsed off the printed text by ``_upgrade_target_spec``.
    The trait is a ``ConstantAbility(target=SELF, TraitGrant)`` marked
    ``upgrade_only`` — read by the attached-upgrade scan, which confers it on the HOST
    (the standing "attached unit gains" shape; ``upgrade_only`` keeps the arena scan
    from leaking it onto the card itself).  The ability is a ``GrantedAbility`` whose
    mandatory When Defeated scales with a live count of other friendly Rebel units —
    the granted trait counts, since the count reads effective traits."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[TraitGrant("Rebel")],
            upgrade_only=True,
        ),
        GrantedAbility(ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_nemik_manifesto_burn)],
        )),
    ]


def _crosshair_friendly_fire(state, source_ci, target_id, event_ctx):
    """Crosshair SEC_162 On Attack: deal 1 to the chosen friendly unit, then 2 to the
    defending player's base.  Bound in ONE CustomEffect so "If you do" holds; with no
    other friendly unit the targeted effect fizzles and nothing happens."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    state = _apply_deal_damage(state, target_id, 1, name,
                               dealer_id=source_ci.instance_id)
    for ps in state.players:
        if ps.player_id != source_ci.owner_id and ps.base_instance is not None:
            state = _apply_deal_damage(state, ps.base_instance.instance_id, 2,
                                       name, dealer_id=source_ci.instance_id)
    return state


@card_ability("SEC", "162")
def _crosshair():
    """SEC_162 — Crosshair (Unit, Clone/Imperial/Trooper, 2/3): "On Attack: You may
    deal 1 damage to another friendly unit.  If you do, deal 2 damage to the defending
    player's base."

    An optional ``OnAttack`` whose one ``CustomEffect.target`` picks another friendly
    unit (``not_self``) and bundles both halves.  "The defending player" is the
    source's opponent — Crosshair is the attacker, so in two-player that is the base
    being attacked toward."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_crosshair_friendly_fire,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)))],
    )


# ── Group sec-set:04 — Direct damage & removal ────────────────────────────────


@card_ability("SEC", "163")
def _outer_rim_constable():
    """SEC_163 — Outer Rim Constable (Unit, Fringe/Official, 3/1): "When Played: You
    may defeat an upgrade."

    An optional ``WhenPlayed`` ``DefeatUpgrade`` over any attached upgrade
    (``kind="upgrade"``); with no upgrade in play the "you may" is never offered."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade"))],
    )


def _warrior_clan_ordo_disclose(state, source_ci, target_id, event_ctx):
    """Warrior of Clan Ordo SEC_164: push the disclose with the new DECLINE arm —
    "If you don't, deal 2 damage to your base".  ``always_offer`` keeps the decision
    on the stack even when the hand cannot cover Aggression, so the penalty still
    lands (the discloser is simply left with only the Decline)."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression"],
        payoff="none",
        decline_payoff="self_base_damage",
        decline_payoff_args={"amount": 2},
        always_offer=True,
    )
    return state


@card_ability("SEC", "164")
def _warrior_of_clan_ordo():
    """SEC_164 — Warrior of Clan Ordo (Unit, Mandalorian, 3/3): "On Attack: You may
    disclose [Aggression] (reveal a card from your hand with this aspect icon).  If
    you don't, deal 2 damage to your base."

    The inverse of every disclose card so far: the payoff is on the DECLINE.  A
    mandatory ``OnAttack`` whose one ``CustomEffect`` pushes the disclose with
    ``decline_payoff="self_base_damage"``; disclosing successfully does nothing at
    all (``payoff="none"``, an unknown key the dispatcher ignores), which is exactly
    what the card says."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_warrior_clan_ordo_disclose)],
    )


def _academy_disciplinarian_prod(state, source_ci, target_id, event_ctx):
    """Academy Disciplinarian SEC_165: deal 1 to the chosen low-power friendly unit
    and ready it.  One CustomEffect so the player is prompted once and both halves
    land on the same unit ("… and ready IT")."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    state = _apply_deal_damage(state, target_id, 1,
                               source_ci.card_def.display_name,
                               dealer_id=source_ci.instance_id)
    res = state.find_instance(target_id)
    if res is not None and res[1].exhausted:
        from swu.engine.events import UnitReadied
        res[1].exhausted = False
        state.event_log.append(UnitReadied(
            player_id=res[0].player_id,
            instance_id=res[1].instance_id,
            card_name=res[1].card_def.display_name,
        ))
    return state


@card_ability("SEC", "165")
def _academy_disciplinarian():
    """SEC_165 — Academy Disciplinarian (Unit, Imperial/Official, 3/4): "When Played:
    You may deal 1 damage to a friendly unit with 2 or less power and ready it."

    An optional ``WhenPlayed`` whose ``CustomEffect.target`` uses the existing
    ``power_max`` filter (effective power, so a temporary buff counts — the card's
    rules insert)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(
            fn=_academy_disciplinarian_prod,
            target=TargetSpec(controller="friendly", kind="unit", power_max=2))],
    )


@card_ability("SEC", "168")
def _ziton_moj():
    """SEC_168 — Ziton Moj (Unit, Underworld, 4/5): "When you take the initiative:
    Deal 2 damage to a base."

    The new ``WhenYouTakeInitiative`` trigger, matched against the ``InitiativeTaken``
    event that ``ClaimInitiative`` already fires and now runs the trigger pipeline
    for.  Mandatory, targeting any base (the controller may burn their own — "a base",
    as printed)."""
    return TriggerAbility(
        trigger=WhenYouTakeInitiative(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


def _aat_incinerator_spray(state, source_ci, target_id, event_ctx):
    """AAT Incinerator SEC_169: "Deal 1 damage to each of up to 4 OTHER ground units.
    If no friendly units were damaged by this ability, deal 2 damage to your base."
    Both riders are new ``push_select_damage`` knobs (``exclude_source`` and
    ``then_self_base_damage_if_no_friendly_hit``), evaluated at the decision's resolve
    so the self-burn is bound to what was actually chosen."""
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=4,
                       arena="ground", exclude_source=True,
                       then_self_base_damage_if_no_friendly_hit=2)
    return state


@card_ability("SEC", "169")
def _aat_incinerator():
    """SEC_169 — AAT Incinerator (Unit, Imperial/Tank/Vehicle, 3/6): a mandatory
    ``WhenPlayed`` adapter onto the ``select_damage`` seam (see the fn)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_aat_incinerator_spray)],
    )


@card_ability("SEC", "171")
def _punishing_one():
    """SEC_171 — Punishing One (Unit, Transport/Underworld/Vehicle, 3/5; Raid): "This
    unit gains Raid 1 for each damaged enemy unit.  When Played/On Attack: You may
    deal 1 damage to a unit."

    The scaling Raid is the new ``KeywordGrant.value_count`` shape
    (``"damaged_enemy_units"``), read live in ``keywords.keyword_value`` — so damaging
    a fresh unit with the On Attack ability raises the Raid for that same attack,
    which is exactly the card's rules insert.  Two optional triggers share one
    ``DealDamage``."""
    hit = DealDamage(1, TargetSpec(controller="any", kind="unit"))
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[KeywordGrant("Raid", 0, value_count="damaged_enemy_units")],
        ),
        TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[hit]),
        TriggerAbility(trigger=OnAttack(), optional=True, effects=[hit]),
    ]


def _lets_call_it_war_first(state, source_ci, target_id, event_ctx):
    """Let's Call It War SEC_180 step 1: deal 3 to the chosen unit and record it plus
    its arena, so the follow-up "another unit in the same arena" is gated by
    ``same_arena_as_event`` + ``requires_prior_target`` (the Asajj JTL_1 chain)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _, unit = res
    # The "if you have the initiative" gate lives HERE rather than in a
    # ConditionalEffect, because a ConditionalEffect cannot hold a TARGETED
    # sub-effect: without the initiative we simply do not stamp prior_target_id, so
    # the follow-up requires_prior_target finds no candidates and fizzles silently.
    if state.initiative_holder == state.player_index(source_ci.owner_id):
        event_ctx["same_arena"] = ("space" if unit.zone == Zone.SPACE_ARENA
                                  else "ground")
        event_ctx["prior_target_id"] = target_id
        event_ctx["excluded_target_id"] = target_id
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 3,
                              source_ci.card_def.display_name)


@card_ability("SEC", "180")
def _lets_call_it_war():
    """SEC_180 — Let's Call It War (Event, Tactic): "Deal 3 damage to a unit.  Then, if
    you have the initiative, you may deal 2 damage to another unit in the same arena."

    The shared-``event_ctx`` chain: a mandatory ``CustomEffect.target`` deals the 3 and
    stamps the arena + the chosen id ONLY when the controller holds the initiative.
    The second ``DealDamage`` is narrowed by ``same_arena_as_event`` (the same arena),
    ``excludes_event_target`` ("another unit") and ``requires_prior_target`` — so with
    no initiative, or no first target, it fizzles silently and never prompts.  The
    gate lives in the fn because a ``ConditionalEffect`` cannot hold a targeted
    sub-effect."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_lets_call_it_war_first,
            target=TargetSpec(controller="any", kind="unit"),
        ),
        DealDamage(2, TargetSpec(
            controller="any", kind="unit",
            predicates=("same_arena_as_event", "excludes_event_target",
                        "requires_prior_target"))),
    ])


# ── Group sec-set:05 — Direct damage & removal ────────────────────────────────

def _charged_with_treason_disclose(state, source_ci, target_id, event_ctx):
    """Charged with Treason SEC_182: pick the unit up front (the Syril Karn SEC_133
    convention — a cosmetic reorder of the printed "disclose, then deal"), then push
    the disclose whose ``damage_unit`` payoff deals the 5."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(
        state, source_ci, ["Aggression", "Aggression"],
        payoff="damage_unit",
        payoff_args={"target_id": target_id, "amount": 5},
    )
    return state


@card_ability("SEC", "182")
def _charged_with_treason():
    """SEC_182 — Charged with Treason (Event, Law): "You may disclose
    [Aggression][Aggression] (reveal cards from your hand with these aspect icons
    among them).  If you do, deal 5 damage to a unit."

    One targeted ``CustomEffect`` that chooses the victim first and then pushes the
    ``disclose`` decision (the Syril Karn SEC_133 shape) — the "you may" is the
    disclose's own Decline, and push_disclose simply does not prompt when the hand
    cannot cover Aggression×2.  The payoff is the existing ``damage_unit`` arm of
    ``_apply_disclose_payoff``."""
    return EventAbility(effects=[CustomEffect(
        fn=_charged_with_treason_disclose,
        target=TargetSpec(controller="any", kind="unit"),
    )])


@card_ability("SEC", "183")
def _topple_the_summit():
    """SEC_183 — Topple the Summit (Event, Plan; Plot — keyword layer): "Deal 3
    damage to each damaged unit."

    A plain ``EACH_IN_PLAY`` ``DealDamage`` narrowed by the ``damaged`` predicate
    (the TWI_3/TWI_13 shape) — every damaged unit, friendly or enemy, in either
    arena.  Plot is the keyword engine's play-from-resources path."""
    return EventAbility(effects=[
        DealDamage(3, TargetSpec(controller="any", kind="unit",
                                 predicates=("damaged",), fixed=EACH_IN_PLAY)),
    ])


@card_ability("SEC", "240")
def _hutt_cartel_starfighter():
    """SEC_240 — Hutt Cartel Starfighter (Unit, Fighter/Underworld/Vehicle, 3/5):
    "When Played: Deal 2 damage to this unit."

    A mandatory ``WhenPlayed`` dealing a fixed 2 to ``SELF`` — no prompt, no
    choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(kind="unit", fixed=SELF))],
    )


def _elia_kane_has_enemy_resource(state, source_ci, event_ctx):
    """Availability gate for Elia Kane's optional When Played: only offer the "you
    may defeat 1 of them" when the opponent actually controls a resource (the
    Shadow Caster JTL_169 ``available_fn`` seam — a non-targeted CustomEffect is
    otherwise assumed to always do something)."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    return bool(opp.resources)


def _elia_kane_defeat_resource(state, source_ci, target_id, event_ctx):
    """Defeat one enemy resource, then that player replaces it from the top of
    their deck (ready).  Resources are fungible face-down cards, so the one defeated
    is auto-selected (the K-2SO SOR_145 convention) rather than prompted — "look at
    3 enemy resources" is pure information over interchangeable cards.  Cost and
    payoff live in one fn so "If you do" holds (nothing is ramped when there was no
    resource to defeat)."""
    from swu.engine.actions import _fire_defeat_own_resource, _resource_top_of_deck
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.resources:
        return state
    _fire_defeat_own_resource(state, opp.player_id)
    _resource_top_of_deck(state, opp)
    return state


@card_ability("SEC", "242")
def _elia_kane():
    """SEC_242 — Elia Kane (Unit, Imperial/New Republic, 3/6; Raid 1 — keyword
    layer): "When Played: Look at 3 enemy resources.  You may defeat 1 of them.  If
    you do, its controller puts the top card of their deck into play as a resource
    and readies it."

    An optional ``WhenPlayed`` whose one ``CustomEffect`` defeats an auto-picked
    enemy resource and ramps its controller a fresh ready one (``_resource_top_of_deck``
    already enters ready).  The ``available_fn`` keeps the "you may" off the table
    when the opponent controls no resource.  DOCUMENTED SIMPLIFICATION: resources
    are interchangeable face-down cards, so neither the "look at 3" nor the choice
    of which to defeat is prompted."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(fn=_elia_kane_defeat_resource,
                              available_fn=_elia_kane_has_enemy_resource)],
    )


@card_ability("SEC", "246")
def _contempt_for_culture():
    """SEC_246 — Contempt for Culture (Event, Innate): "Deal 2 damage to a
    non-Vehicle unit.  Create a Spy token."

    The targeted ``DealDamage`` is ordered FIRST and the fixed ``CreateTokenUnit``
    second, so the resolver prompts exactly once (the Mandalorian SHD_18 wart)."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="any", kind="unit",
                                 predicates=("non_vehicle",))),
        CreateTokenUnit("Spy", count=1),
    ])


@card_ability("SEC", "247")
def _evil_is_everywhere():
    """SEC_247 — Evil is Everywhere (Event, Disaster): "Defeat a unit with cost
    equal to or less than the number of Villainy aspect icons among friendly units."

    A plain ``DefeatUnit`` whose cap is the new DYNAMIC ``cost_max_count``
    (the ``power_max_count`` sibling): ``"controller_villainy_aspect_icons"`` counts
    every Villainy pip on the controller's arena units, duplicates included, so a
    double-Villainy unit contributes 2.  With no Villainy on board the cap is 0 and
    only free units are legal — usually none, and the event fizzles with no
    prompt."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              cost_max_count="controller_villainy_aspect_icons")),
    ])


# ── Group sec-set:06 — Direct damage & removal ────────────────────────────────

@card_ability("SEC", "254")
def _heroic_arc_170():
    """SEC_254 — Heroic ARC-170 (Unit, Fighter/Republic/Vehicle, 4/3): "When Played:
    If you control a damaged unit, you may deal 2 damage to an enemy unit."

    An optional ``WhenPlayed`` gated by ``CONTROLLER_HAS_DAMAGED_UNIT`` — a failing
    condition stops the trigger being COLLECTED, so there is no prompt and no
    no-op."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_DAMAGED_UNIT),
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="unit"))],
    )


@card_ability("SEC", "263")
def _assassin_probe():
    """SEC_263 — Assassin Probe (Unit, Droid/Separatist, 4/4): "When Defeated: Deal
    1 damage to each exhausted enemy ground unit."

    A mandatory ``WhenDefeated`` whose ``EACH_ENEMY`` target is narrowed to the
    ground arena and the ``exhausted`` predicate — expanded inline, so all the
    damage lands with no prompt."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                          arena="ground",
                                          predicates=("exhausted",),
                                          fixed=EACH_ENEMY))],
    )


def _clandestine_connections_pay(state, source_ci, target_id, event_ctx):
    """Pay 2 resources, and only if the payment succeeds deal 2 to the chosen base
    ("If you do" — cost and payoff bound in one fn).  ``source_ci`` is the HOST (a
    GrantedAbility resolves from the attached unit), so the resources come from the
    host's controller."""
    from swu.engine.actions import _exhaust_resources
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if sum(1 for r in ps.resources if not r.exhausted) < 2:
        return state
    _exhaust_resources(ps, 2)
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 2,
                              source_ci.card_def.display_name)


@card_ability("SEC", "264")
def _clandestine_connections():
    """SEC_264 — Clandestine Connections (Upgrade, Supply): "Attached unit gains:
    'On Attack: You may pay 2 resources.  If you do, deal 2 damage to a base.'"

    A ``GrantedAbility`` wrapping the On Attack trigger, so it matches and resolves
    with the HOST as source.  The trigger is gated by
    ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` so it is never offered when the price
    cannot be paid, and its one ``CustomEffect`` binds the payment to the damage."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=2),
        effects=[CustomEffect(
            fn=_clandestine_connections_pay,
            target=TargetSpec(controller="any", kind="base"),
        )],
    ))


# ── Group sec-set:07 — Card advantage & disruption ────────────────────────────

def _sabe_mill_defender_deck(state, source_ci, target_id, event_ctx):
    """Sabé SEC_17 (undeployed): exhaust the leader, then look at the top 2 cards of
    the DEFENDING player's deck and discard 1 (the other goes back on top).

    The exhaust is bundled into the payoff fn because an undeployed leader sits in
    the base zone and is no arena unit, so ``ExhaustCard(fixed=SELF)`` cannot reach
    it (the Boba Fett JTL_9 convention).  A friendly unit attacking a base always
    hits the ENEMY base, so the defending player is simply the controller's
    opponent.  The look is the new FOREIGN ``deck_search``: ``deck_owner_id`` picks
    whose deck is searched while ``decider_id`` keeps the choice with Sabé's
    controller; ``disposition="discard"`` sends the pick to its owner's discard and
    ``rest_disposition="top"`` puts the other back on top, in order."""
    from swu.engine.actions import push_deck_search
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    leader = res[1]
    if leader.exhausted:
        return state
    leader.exhausted = True
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    push_deck_search(
        state, source_ci,
        count=1, window=2, up_to=False,
        eligible=lambda card_def: True,
        disposition="discard", rest_disposition="top",
        decider_id=source_ci.owner_id, deck_owner_id=opp.player_id,
    )
    return state


def _sabe_strip_hand(state, source_ci, target_id, event_ctx):
    """Sabé SEC_17 (deployed): "Look at the defending player's hand.  You may
    discard a card from it.  If you do, that player draws a card" — exactly the
    Bazine Netal SHD_184 shape of ``name_and_discard`` (the decision already carries
    the whole hand to the controller and offers only names present, which IS the
    look; ``optional`` is the "you may" and ``discarder_draws`` the rider)."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, optional=True, discarder_draws=True)
    return state


@card_ability("SEC", "17")
def _sabe():
    """SEC_17 — Sabé (Leader, Naboo; Raid 1 deployed — keyword layer).

    Undeployed: "When a friendly unit deals combat damage to a base: You may exhaust
    this leader.  If you do, look at the top 2 cards of the defending player's deck.
    Discard 1 of those cards.  (Put the other back on top.)"  The observer form of
    ``WhenDealsCombatDamageToBase`` (a ``filter`` for "a friendly unit" — the Temple
    of Destruction LOF_25 shape), gated ``SOURCE_READY`` so the "you may exhaust" is
    never offered when the price cannot be paid.

    Deployed: "When this unit deals combat damage to a base: Look at the defending
    player's hand.  You may discard a card from it.  If you do, that player draws a
    card" — the self-matching form of the same trigger onto ``name_and_discard``."""
    return [
        TriggerAbility(
            trigger=WhenDealsCombatDamageToBase(
                filter=TargetSpec(controller="friendly", kind="unit")),
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
            effects=[CustomEffect(fn=_sabe_mill_defender_deck)],
        ),
        TriggerAbility(
            trigger=WhenDealsCombatDamageToBase(),
            deployed_only=True,
            effects=[CustomEffect(fn=_sabe_strip_hand)],
        ),
    ]


def _bardottan_ornithopter_disclose(state, source_ci, target_id, event_ctx):
    """Bardottan Ornithopter SEC_62: disclose Vigilance → draw a card (the existing
    ``draw`` arm of ``_apply_disclose_payoff``)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Vigilance"],
                  payoff="draw", payoff_args={"count": 1})
    return state


@card_ability("SEC", "62")
def _bardottan_ornithopter():
    """SEC_62 — Bardottan Ornithopter (Unit, Fringe/Transport/Vehicle, 3/4): "When
    Played: You may disclose [Vigilance] (reveal a card from your hand with this
    aspect icon).  If you do, draw a card."

    A MANDATORY ``WhenPlayed`` whose one ``CustomEffect`` pushes the disclose (the
    Mina Bonteri SEC_94 pattern) — the "you may" is the disclose's own Decline, and
    push_disclose does not prompt at all when the hand holds no Vigilance card."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_bardottan_ornithopter_disclose)],
    )


def _scour_the_archives(state, source_ci, target_id, event_ctx):
    """Search the top 8 for an upgrade and draw it; the rest are bottomed in a
    seeded-random order (the deck_search default)."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Upgrade, TokenUpgrade
    push_deck_search(
        state, source_ci, count=1, window=8, up_to=False,
        eligible=lambda cd: isinstance(cd, Upgrade) and not isinstance(cd, TokenUpgrade),
    )
    return state


@card_ability("SEC", "72")
def _scour_the_archives_event():
    """SEC_72 — Scour the Archives (Event, Learned): "Search the top 8 cards of your
    deck for an upgrade, reveal it, and draw it.  (Put the other cards on the bottom
    of your deck in a random order.)"

    A thin ``push_deck_search`` adapter — ``up_to=False`` makes the take mandatory
    while an eligible upgrade remains (the Recruit SOR_123 reading of "search for
    a <thing>")."""
    return EventAbility(effects=[CustomEffect(fn=_scour_the_archives)])


@card_ability("SEC", "75")
def _knowledge_and_defense():
    """SEC_75 — Knowledge and Defense (Event, Learned): "Give a unit −2/−2 for this
    phase.  Draw a card."

    The targeted ``ModifyStats`` is ordered FIRST and the fixed ``DrawCards``
    second, so the resolver prompts exactly once (the Mandalorian SHD_18 wart)."""
    return EventAbility(effects=[
        ModifyStats(power=-2, hp=-2,
                    target=TargetSpec(controller="any", kind="unit"),
                    duration=Duration.THIS_PHASE),
        DrawCards(count=1),
    ])


def _krennic_mill_and_maybe_recur(state, source_ci, target_id, event_ctx):
    """Director Krennic SEC_90: discard the top card of the controller's own deck;
    if it is a unit, offer to return THAT card to hand.  The offer is the
    ``return_from_discard`` decision pinned by ``eligible_instance`` to the
    just-milled card, so its always-available Finish is the printed "you may"."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_return_from_discard, note_hand_or_deck_discard
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    milled = ps.deck.pop(0)
    milled.zone = Zone.DISCARD
    ps.discard.append(milled)
    note_hand_or_deck_discard(state, milled)
    if not isinstance(milled.card_def, Unit):
        return state
    push_return_from_discard(
        state, source_ci, count=1,
        eligible=lambda cd: isinstance(cd, Unit),
        eligible_instance=lambda ci: ci.instance_id == milled.instance_id,
    )
    return state


@card_ability("SEC", "90")
def _director_krennic():
    """SEC_90 — Director Krennic (Unit, Imperial/Official, 8/10; Sentinel — keyword
    layer): "When this unit is attacked: Discard a card from your deck.  If it's a
    unit, you may return it to your hand."

    A mandatory ``WhenAttacked`` whose one ``CustomEffect`` mills and (only for a
    unit) pushes the pinned ``return_from_discard`` — cost and payoff bound in one
    fn so "if it's a unit" cannot be gamed."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CustomEffect(fn=_krennic_mill_and_maybe_recur)],
    )


def _renewed_friendship(state, source_ci, target_id, event_ctx):
    """Return a unit from the controller's discard to hand, then create 2 Spy
    tokens.  DOCUMENTED SIMPLIFICATION: ``return_from_discard`` only has the "up to"
    mode, so the printed mandatory return collapses to "you may" — returning a unit
    is never a downside, so no reachable state differs."""
    from swu.engine.actions import push_return_from_discard, _create_token_units
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    _create_token_units(state, ps, "Spy", 2)
    push_return_from_discard(
        state, source_ci, count=1,
        eligible=lambda cd: isinstance(cd, Unit),
    )
    return state


@card_ability("SEC", "105")
def _renewed_friendship_event():
    """SEC_105 — Renewed Friendship (Event, Innate): "Return a unit from your discard
    pile to your hand.  Create 2 Spy tokens."

    One ``CustomEffect`` doing both clauses, so the tokens land whether or not the
    discard pile holds a unit (the return simply fizzles with no prompt when it
    does not)."""
    return EventAbility(effects=[CustomEffect(fn=_renewed_friendship)])


def _orn_free_taa_search(state, source_ci, target_id, event_ctx):
    """Search the top 10 of the controller's deck for a Law card and draw it."""
    from swu.engine.actions import push_deck_search
    push_deck_search(
        state, source_ci, count=1, window=10, up_to=False,
        eligible=lambda cd: "Law" in (getattr(cd, "traits", None) or ()),
    )
    return state


@card_ability("SEC", "112")
def _orn_free_taa():
    """SEC_112 — Orn Free Taa (Unit, Official/Republic/Twi'lek, 0/4): "This unit gets
    +1/+0 for each Law card in your discard pile.  When Played: Search the top 10
    cards of your deck for a Law card, reveal it, and draw it."

    Two specs: a SELF ``ConstantAbility`` scaled by the new
    ``controller_discard_trait_cards_Law`` count (the card-type-blind sibling of
    Captain Enoch LOF_83's units-only count — an event or upgrade with the Law trait
    counts too), and a mandatory ``WhenPlayed`` ``push_deck_search``."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=1, hp=0,
                               count="controller_discard_trait_cards_Law")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_orn_free_taa_search)],
        ),
    ]


# ── Group sec-set:08 — Card advantage & disruption ────────────────────────────

@card_ability("SEC", "125")
def _reconnaissance():
    """SEC_125 — Reconnaissance (Event, Plan): "If you control a ground unit and a
    space unit, draw 2 cards."

    A plain ``ConditionalEffect`` over ``CONTROLLER_HAS_GROUND_AND_SPACE_UNIT``
    (an ``EventAbility`` has no ``condition`` field, so the gate lives in the
    effect)."""
    return EventAbility(effects=[
        ConditionalEffect(
            condition=ConditionCheck(Condition.CONTROLLER_HAS_GROUND_AND_SPACE_UNIT),
            if_true=(DrawCards(count=2),),
            if_false=(),
        ),
    ])


def _convene_the_senate(state, source_ci, target_id, event_ctx):
    """Create a Spy token, then search the top 8 for up to 2 Official units.  Both
    clauses in one fn: the search pushes a decision, so it resolves after this fn
    returns — the token is made either way."""
    from swu.engine.actions import push_deck_search, _create_token_units
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    _create_token_units(state, ps, "Spy", 1)
    push_deck_search(
        state, source_ci, count=2, window=8, up_to=True,
        eligible=lambda cd: (isinstance(cd, Unit)
                             and "Official" in (getattr(cd, "traits", None) or ())),
    )
    return state


@card_ability("SEC", "128")
def _convene_the_senate_event():
    """SEC_128 — Convene the Senate (Event, Law): "Search the top 8 cards of your
    deck for up to 2 Official units, reveal them, and draw them.  Create a Spy
    token."

    One ``CustomEffect`` doing both clauses — ``up_to=True`` is the printed "up to
    2", and the token lands whatever the search finds."""
    return EventAbility(effects=[CustomEffect(fn=_convene_the_senate)])


@card_ability("SEC", "200")
def _junior_senator():
    """SEC_200 — Junior Senator (Unit, Official/Republic, 3/2): "When Played: You may
    return an upgrade that costs 3 or less to its owner's hand."

    An optional ``WhenPlayed`` ``ReturnToHand`` over any attached upgrade capped at
    cost 3.  A Shield/Experience TOKEN has no printed cost, so the cap excludes it
    (a token cannot go to a hand anyway)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ReturnToHand(TargetSpec(controller="any", kind="upgrade",
                                         cost_max=3))],
    )


def _obi_wan_mill_and_permit(state, source_ci, target_id, event_ctx):
    """Obi-Wan Kenobi SEC_205: discard the top card of the DEFENDING player's deck,
    then permit the source's controller to play that card from their pile for the
    rest of the phase, ignoring its aspect penalties (the new cross-pile PAID
    permission ``game_memory.foreign_discard_play_this_phase``; the waiver is
    applied as a discount equal to the payer's aspect penalty at the enumeration
    site).  A friendly unit attacking a base always hits the ENEMY base, so the
    defending player is the controller's opponent."""
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    if not opp.deck:
        return state
    milled = opp.deck.pop(0)
    milled.zone = Zone.DISCARD
    opp.discard.append(milled)
    note_hand_or_deck_discard(state, milled)
    permitted = state.game_memory.foreign_discard_play_this_phase
    permitted.setdefault(source_ci.owner_id, []).append(milled.instance_id)
    return state


@card_ability("SEC", "205")
def _obi_wan_kenobi():
    """SEC_205 — Obi-Wan Kenobi (Unit, Force/Jedi/Republic, 4/5): "When this unit
    deals combat damage to a base: Discard a card from the defending player's deck.
    For this phase, you may play that card from their discard pile, ignoring its
    aspect penalties."

    A mandatory self-matching ``WhenDealsCombatDamageToBase`` whose one
    ``CustomEffect`` mills and records the permission."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[CustomEffect(fn=_obi_wan_mill_and_permit)],
    )


def _faith_in_your_friends(state, source_ci, target_id, event_ctx):
    """Push the disclose FIRST and the search SECOND so the search — sitting on top
    of the stack — resolves first, matching the printed order ("Search … Then, you
    may disclose …")."""
    from swu.engine.actions import push_disclose, push_deck_search
    push_disclose(
        state, source_ci,
        ["Cunning", "Cunning", "Cunning", "Heroism", "Heroism"],
        payoff="create_token",
        payoff_args={"token_name": "Spy", "count": 2},
    )
    push_deck_search(
        state, source_ci, count=1, window=3, up_to=False,
        eligible=lambda cd: True,
    )
    return state


@card_ability("SEC", "211")
def _faith_in_your_friends_event():
    """SEC_211 — Faith in Your Friends (Event, Gambit): "Search the top 3 cards of
    your deck for a card and draw it.  Then, you may disclose
    [Cunning][Cunning][Cunning][Heroism][Heroism] (reveal cards from your hand with
    these aspect icons among them).  If you do, create 2 Spy tokens."

    One ``CustomEffect`` pushing both decisions in reverse order (LIFO) so the
    search resolves before the disclose.  The tokens are the new plain
    ``create_token`` disclose payoff (they enter exhausted, the CR default)."""
    return EventAbility(effects=[CustomEffect(fn=_faith_in_your_friends)])


def _cikatro_vizago_reveal(state, source_ci, target_id, event_ctx):
    """Cikatro Vizago SEC_218: reveal the top card of the controller's deck and hand
    the opponent a PRICED say-no — pay 1 resource to deny the draw, or let the
    controller draw it.  ``revealed_card`` carries the card's identity (card_id +
    name only, never its instance_id) so the decider sees what they are paying to
    stop.  With an empty deck there is nothing to draw and nothing is pushed."""
    from swu.engine.actions import push_say_no
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    top = ps.deck[0]
    push_say_no(
        state, source_ci, None,
        effect="draw_top_card", pay_to_refuse=1, draw_on_refuse=0,
        revealed_card={"card_id": top.card_def.id,
                       "card_name": top.card_def.display_name},
    )
    return state


@card_ability("SEC", "218")
def _cikatro_vizago():
    """SEC_218 — Cikatro Vizago (Unit, Underworld, 3/4): "On Attack: Reveal the top
    card of your deck.  An opponent may pay 1 resource.  If they don't, draw that
    card."

    A mandatory ``OnAttack`` onto the ``say_no`` decision's new PRICED refusal:
    ``pay_to_refuse`` makes SayNo cost the decider a resource (and it is only
    offered while they can pay), and the ``draw_top_card`` effect arm is what
    "allowing" it means."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_cikatro_vizago_reveal)],
    )


# ── Group sec-set:09 — Card advantage & disruption ────────────────────────────

def _charged_with_espionage(state, source_ci, target_id, event_ctx):
    """Charged with Espionage SEC_230: disclose Cunning×2 → look at an opponent's
    hand and discard a unit from it (the new ``name_and_discard`` disclose payoff)."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Cunning", "Cunning"],
        payoff="name_and_discard",
        payoff_args={"card_type": "unit"},
    )
    return state


@card_ability("SEC", "230")
def _charged_with_espionage_event():
    """SEC_230 — Charged with Espionage (Event, Law): "You may disclose
    [Cunning][Cunning] (reveal cards from your hand with these aspect icons among
    them).  If you do, look at an opponent's hand and discard a unit from it."

    A thin ``push_disclose`` adapter — the "you may" is the disclose's own Decline
    and the payoff is the ``name_and_discard`` decision narrowed to units (which
    fizzles with no prompt when the opponent holds no unit)."""
    return EventAbility(effects=[CustomEffect(fn=_charged_with_espionage)])


def _kreias_whispers(state, source_ci, target_id, event_ctx):
    """Draw 3, then put one hand card on the BOTTOM and another on the TOP.  The two
    pushes are in reverse order (LIFO) so the TOP placement is decided first, as
    printed; each is the existing ``bottom_from_hand`` decision, the second in its
    new exclusive ``top_only`` mode."""
    from swu.engine.actions import _draw_cards, push_bottom_from_hand
    ps = state.player_by_id(source_ci.owner_id)
    _draw_cards(state, ps, 3)
    push_bottom_from_hand(state, source_ci, count=1)
    push_bottom_from_hand(state, source_ci, count=1, top_only=True)
    return state


@card_ability("SEC", "232")
def _kreias_whispers_event():
    """SEC_232 — Kreia's Whispers (Event, Force/Learned): "Draw 3 cards, then put a
    card from your hand on the top of your deck and another card from your hand on
    the bottom of your deck."

    One ``CustomEffect``: the draw, then two ``bottom_from_hand`` decisions — one
    ``top_only``, one plain — so the placements cannot be collapsed onto the same
    side.  Each is mandatory-if-able and fizzles cleanly on an empty hand."""
    return EventAbility(effects=[CustomEffect(fn=_kreias_whispers)])


def _beguile_look(state, source_ci, target_id, event_ctx):
    """Beguile SEC_233: look at an opponent's hand (pure information — the bounce
    that follows targets the board, not the hand)."""
    from swu.engine.actions import push_look_opponent_hand
    push_look_opponent_hand(state, source_ci)
    return state


@card_ability("SEC", "233")
def _beguile():
    """SEC_233 — Beguile (Event, Trick): "Look at an opponent's hand.  Then, choose a
    non-leader unit that opponent controls that costs 6 or less and return it to its
    owner's hand."

    TWO abilities, not two effects (the Barrel Roll JTL_228 lesson): a single
    ability would prompt for the bounce target BEFORE the leading CustomEffect ran.
    ``_resolve_event_ability`` walks the abilities in order, so the TARGETED bounce
    (ability 0) pushes its ChooseTarget first and the lone no-target look (ability 1)
    then inlines and pushes ``look_hand`` ON TOP — look first, choose after, one
    prompt each."""
    return [
        EventAbility(effects=[
            ReturnToHand(TargetSpec(controller="enemy", kind="unit",
                                    predicates=("non_leader",), cost_max=6)),
        ]),
        EventAbility(effects=[CustomEffect(fn=_beguile_look)]),
    ]


# ── Group sec-set:10 — Combat tricks, buffs & tempo (the SEC leaders) ─────────

_LEIA_ASPECTS = ["Vigilance", "Command", "Aggression", "Cunning", "Heroism"]


def _leia_organa_disclose(state, source_ci, target_id, event_ctx):
    """Leia Organa SEC_4: disclose ONE card bearing any of the five basic aspect
    icons (the new ``any_of`` disjunctive disclose), then give an Experience token
    to a unit that shares no aspect with it (the ``experience_off_aspect_unit``
    payoff)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, list(_LEIA_ASPECTS),
                  payoff="experience_off_aspect_unit", any_of=True)
    return state


@card_ability("SEC", "4")
def _leia_organa_sec():
    """SEC_4 — Leia Organa (Leader, New Republic/Official).

    Undeployed: "Action [1 resource, Exhaust]: Disclose Vigilance, Command,
    Aggression, Cunning, or Heroism (reveal a card from your hand with this aspect
    icon).  If you do, give an Experience token to a unit that doesn't share an
    aspect with the disclosed card."  Deployed: the same as an optional On Attack.

    Both sides are the one ``CustomEffect`` onto the disclose, whose ``any_of``
    mode is the printed "or" (one card carrying ANY of the five satisfies it).  The
    payoff whitelists every in-play unit sharing no aspect with the revealed card
    into a ``select_token`` (DOCUMENTED DEVIATION: select_token is an "up to", so
    the gift may be declined)."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_leia_organa_disclose)],
            title="Disclose an aspect for an Experience token",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            deployed_only=True,
            effects=[CustomEffect(fn=_leia_organa_disclose)],
        ),
    ]


def _yularen_attack_then_cheaper(state, source_ci, target_id, event_ctx):
    """Colonel Yularen SEC_6 (undeployed Action): attack with a unit, then optionally
    attack with another unit that costs less than it (the new ``then_attack_cheaper``
    rider, whose cap is read off the unit that actually attacked)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, then_attack_cheaper=True)
    return state


def _yularen_followup_attack(state, source_ci, target_id, event_ctx):
    """Colonel Yularen SEC_6 (deployed): after he completes an attack and survives,
    he may attack with another unit costing 4 or less."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True,
                        attacker_cost_max=4, exclude_source=True)
    return state


@card_ability("SEC", "6")
def _colonel_yularen():
    """SEC_6 — Colonel Yularen (Leader, Imperial/Official).

    Undeployed: "Action [Exhaust]: Attack with a unit.  Then, you may attack with
    another unit that costs less than it."  Deployed: "When this unit completes an
    attack (and survives): You may attack with another unit that costs 4 or less."

    Both are ``push_granted_attack`` adapters; the undeployed one uses the new
    ``then_attack_cheaper`` follow-up (a one-shot re-push capped at the first
    attacker's cost − 1, excluding that attacker), the deployed one the
    long-standing ``attacker_cost_max`` / ``exclude_source`` fields on
    ``WhenAttackEnds`` (which only fires for a surviving attacker)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_yularen_attack_then_cheaper)],
            title="Attack with a unit, then a cheaper one",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            deployed_only=True,
            effects=[CustomEffect(fn=_yularen_followup_attack)],
        ),
    ]


def _dryden_vos_play_unit(state, source_ci, target_id, event_ctx):
    """Dryden Vos SEC_7 (deployed): play a unit from hand (paying its cost); it gains
    Ambush for this phase.  No cost cap on this side."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, grant_keyword="Ambush")
    return state


def _dryden_vos_play_unit_cheap(state, source_ci, target_id, event_ctx):
    """The undeployed side's capped play ("a unit that costs 5 or less")."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_max=5, grant_keyword="Ambush")
    return state


@card_ability("SEC", "7")
def _dryden_vos():
    """SEC_7 — Dryden Vos (Leader, Underworld; Overwhelm deployed — keyword layer).

    Undeployed: "Action [Exhaust, discard a card that costs 6 or more from your
    hand]: Play a unit that costs 5 or less from your hand (paying its cost).  It
    gains Ambush for this phase."  Deployed: the same Action with no cost cap and a
    plain "discard a card" (no Exhaust).

    The discard costs are ``DiscardCardCost``, whose new ``cost_min`` both gates the
    offer (the ability is not enumerated when the hand holds no card costing 6+) and
    picks which card is discarded.  The plays are ``push_play_from_hand`` with
    ``grant_keyword="Ambush"`` (a granted Ambush still fires on entry)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), DiscardCardCost(cost_min=6)],
            effects=[CustomEffect(fn=_dryden_vos_play_unit_cheap)],
            title="Play a unit costing 5 or less with Ambush",
            undeployed_only=True,
        ),
        ActivatedAbility(
            costs=[DiscardCardCost()],
            effects=[CustomEffect(fn=_dryden_vos_play_unit)],
            title="Play a unit from hand with Ambush",
            deployed_only=True,
        ),
    ]


def _bail_organa_recycle_resource(state, source_ci, target_id, event_ctx):
    """Bail Organa SEC_8 (undeployed): return a friendly resource to hand and, if you
    do, ramp the top card of your deck into play as a resource.  Resources are
    fungible face-down cards, so the returned one is auto-picked (the K-2SO SOR_145
    convention); cost and payoff are bound in one fn so "If you do" holds."""
    from swu.engine.state import Zone
    from swu.engine.actions import _resource_top_of_deck
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.resources:
        return state
    res = next((r for r in ps.resources if r.face_down), ps.resources[0])
    ps.resources.remove(res)
    res.zone = Zone.HAND
    res.face_down = False
    res.exhausted = False
    ps.hand.append(res)
    _resource_top_of_deck(state, ps)
    return state


@card_ability("SEC", "8")
def _bail_organa():
    """SEC_8 — Bail Organa (Leader, Official/Republic).

    Undeployed: "Action [1 resource, Exhaust]: If a friendly unit was defeated this
    phase, return a friendly resource to its owner's hand.  If you do, put the top
    card of your deck into play as a resource" — gated by
    ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` so the cost is never spent on a no-op.
    Deployed: "When you play a card from your resources: Heal 1 damage from your
    base" — the ``WhenYouPlayCard(via_smuggle=True)`` observer.  DOCUMENTED
    NARROWING: Smuggle is the resource-play path the observer sees; a Plot play from
    resources does not fire it.

    (His third printed line is an alternate DEPLOY action; deploying never routes
    through the ability registry, so it needs no registration.)"""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            condition=ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE),
            effects=[CustomEffect(fn=_bail_organa_recycle_resource)],
            title="Recycle a resource",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenYouPlayCard(via_smuggle=True),
            deployed_only=True,
            effects=[Heal(1, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
        ),
    ]


@card_ability("SEC", "9")
def _mon_mothma_sec_9():
    """SEC_9 — Mon Mothma (Leader, Official/Republic): "Ignore the aspect penalties
    on non-Villainy Official units you play." (both sides) plus, deployed, "Each
    other friendly Official unit gets +0/+1."

    The waiver is the ``IgnoreAspectPenaltyForPlays`` marker (controller-scoped, and
    its scan already covers the base zone so the UNDEPLOYED leader's copy counts)
    with the new ``exclude_aspects`` narrowing for "non-Villainy".  The anthem is an
    ordinary aura ``ConstantAbility``, which only the ARENA scans read — so it is
    deployed-only for free."""
    return [
        IgnoreAspectPenaltyForPlays(card_type="unit", traits=("Official",),
                                    exclude_aspects=("Villainy",)),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Official",), predicates=("not_self",)),
            effects=[StatBonus(power=0, hp=1)],
        ),
    ]


@card_ability("SEC", "11")
def _governor_pryce():
    """SEC_11 — Governor Pryce (Leader, Imperial/Official).

    Undeployed: "Action [1 resource, Exhaust]: Ready a token unit."  Deployed: "This
    unit gets +1/+0 for each ready friendly token unit" and "On Attack: Create a Spy
    token."

    The ready is a plain targeted ``ReadyCard`` narrowed to an EXHAUSTED friendly
    token unit (so the cost is never spent on a no-op — the "don't offer a no-op"
    rule), the buff a SELF ``ConstantAbility`` on the new
    ``controller_ready_token_units`` count, and the token the ``CreateTokenUnit``
    primitive."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[ReadyCard(TargetSpec(controller="friendly", kind="unit",
                                          predicates=("token_unit", "exhausted")))],
            title="Ready a token unit",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[StatBonus(power=1, hp=0, count="controller_ready_token_units")],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            deployed_only=True,
            effects=[CreateTokenUnit("Spy", count=1)],
        ),
    ]


@card_ability("SEC", "15")
def _c_3po_sec_15():
    """SEC_15 — C-3PO (Leader, Droid/Rebel).

    Undeployed: "Action [1 resource, Exhaust]: If you control an exhausted unit,
    exhaust a unit."  Deployed: "On Attack: If you control another exhausted unit,
    you may exhaust a unit."

    Two new condition atoms carry the gates: ``CONTROLLER_HAS_EXHAUSTED_UNIT`` and
    its self-excluding sibling ``CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT`` — the latter
    matters because attacking exhausts C-3PO himself, so without the exclusion the
    deployed clause would always hold.  The payoff is a targeted ``ExhaustCard``
    over any READY unit (an already-exhausted one would be a no-op)."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_EXHAUSTED_UNIT),
            effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                            predicates=("ready",)))],
            title="Exhaust a unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT),
            effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                            predicates=("ready",)))],
        ),
    ]


# ── Group sec-set:11 — Combat tricks, buffs & tempo ───────────────────────────

def _dj_capture_play(state, source_ci, target_id, event_ctx):
    """DJ SEC_18 (undeployed): the chosen friendly unit captures a unit played from
    hand at 1 resource less.  The capture is the new ``then_capture_by`` SETTLE
    payoff on ``play_from_hand`` — it must run after the play has really happened,
    which no second effect could express."""
    from swu.engine.actions import push_play_from_hand
    if target_id is None:
        return state
    push_play_from_hand(state, source_ci, cost_reduction=1,
                        then_capture_by=target_id)
    return state


@card_ability("SEC", "18")
def _dj():
    """SEC_18 — DJ (Leader, Underworld; Saboteur deployed — keyword layer).

    Undeployed: "Action [Exhaust]: Choose a friendly unit.  If you do, play a unit
    from your hand.  It costs 1 resource less.  The chosen unit captures it."  ONE
    targeted ``CustomEffect`` picks the captor and pushes the discounted play with
    the ``then_capture_by`` rider, so cost and payoff cannot come apart.

    Deployed: "Friendly units that are rescued enter play ready" — already the
    engine's behaviour: ``actions._release_captured_cards`` (the rescue-into-play
    path, run when a captor leaves play) returns every captive READY.  So the clause
    needs no registration; it is documented here rather than duplicated as an inert
    marker."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(
            fn=_dj_capture_play,
            target=TargetSpec(controller="friendly", kind="unit"),
        )],
        title="Play a unit 1 cheaper and capture it",
        undeployed_only=True,
    )


@card_ability("SEC", "29")
def _zam_wesell():
    """SEC_29 — Zam Wesell (Unit, Bounty Hunter/Underworld, 1/5): "While this unit is
    upgraded, she gains Grit."

    The conditional self-grant (Jedi Trials LOF_52's ``SOURCE_ATTACHED_UPGRADES_MIN``
    at 1 — a Shield or Experience token counts as an upgrade, as in SWU it is one).
    Sanitiser rule 2 strips the mis-tagged printed Grit, so a bare Zam really lacks
    it."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Grit", value=0)],
        condition=ConditionCheck(Condition.SOURCE_ATTACHED_UPGRADES_MIN, param=1),
    )


@card_ability("SEC", "32")
def _kylo_rens_command_shuttle():
    """SEC_32 — Kylo Ren's Command Shuttle (Unit, First Order/Transport/Vehicle,
    3/5): "Each friendly ground unit with Sentinel gets +0/+2."

    An aura ``ConstantAbility`` narrowed by the new per-candidate keyword predicate
    ``has_keyword_sentinel``, which reads through the keyword layer so a GRANTED
    Sentinel counts too.  (The card's own printed "Sentinel" tag is already stripped
    by the sanitiser's "with K" reference rule — it names a property of other
    cards.)"""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", arena="ground",
                          predicates=("has_keyword_sentinel",)),
        effects=[StatBonus(power=0, hp=2)],
    )


def _emergency_powers(state, source_ci, target_id, event_ctx):
    """Emergency Powers SEC_40: pay any number of resources, each buying one
    Experience token for the CHOSEN unit (the new ``token_target_id`` on the
    pay-any-number decision)."""
    from swu.engine.actions import push_pay_resources_for_tokens
    if target_id is None:
        return state
    push_pay_resources_for_tokens(
        state, source_ci, max_resources=None,
        token_type="Experience", token_target_id=target_id)
    return state


@card_ability("SEC", "40")
def _emergency_powers_event():
    """SEC_40 — Emergency Powers (Event, Law): "Choose a non-leader unit and pay any
    number of resources.  For each resource paid this way, give an Experience token
    to the chosen unit."

    One targeted ``CustomEffect`` picks the unit and hands the payment loop the new
    ``token_target_id``; ``max_resources=None`` is the printed "any number"."""
    return EventAbility(effects=[CustomEffect(
        fn=_emergency_powers,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("non_leader",)),
    )])


@card_ability("SEC", "41")
def _populist_advisor():
    """SEC_41 — Populist Advisor (Unit, New Republic/Official, 1/4): "When an enemy
    unit deals combat damage to your base: This unit gains Sentinel for this phase."

    The OBSERVER form of ``WhenDealsCombatDamageToBase`` (a ``filter`` for an enemy
    unit — an enemy unit attacking a base always hits the source controller's base,
    so ``controller="enemy"`` is the whole filter), granting Sentinel to SELF for the
    phase."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(
            filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[GrantKeyword("Sentinel", value=0,
                              target=TargetSpec(kind="unit", fixed=SELF),
                              duration=Duration.THIS_PHASE)],
    )


@card_ability("SEC", "47")
def _coronet():
    """SEC_47 — Coronet (Unit, Mandalorian/Transport/Vehicle, 4/6; Restore 1 —
    keyword layer): "Each other friendly unit gains Restore 1."

    A plain aura ``ConstantAbility`` carrying a ``KeywordGrant``.  Coronet keeps her
    OWN printed Restore 1: the sanitiser's bare-mention override sees the keyword-bar
    entry (with its reminder text) and never strips it."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
        effects=[KeywordGrant("Restore", value=1)],
    )


def _exiled_from_the_force_revoke(state, source_ci, target_id, event_ctx):
    """Exiled from the Force SEC_54: strip the Force trait from the attached unit
    with a PERMANENT ``trait_revoke`` modifier sourced on the upgrade (the Lando
    JTL_3 permanent-modifier recipe — ``_modifier_source_in_play`` ties its lifetime
    to the upgrade staying attached, which IS "while attached").  The trait layer
    consults revocations FIRST, so the unit cannot regain Force while it holds."""
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        # The upgrade-play site threads attached_to_id, but a scan of the boards is
        # the robust fallback (and the only route when the upgrade is already
        # attached).
        for ps in state.players:
            for arena in (ps.ground_arena, ps.space_arena):
                for u in arena:
                    if any(up.instance_id == source_ci.instance_id
                           for up in u.attached_upgrades):
                        host_id = u.instance_id
    if not host_id:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=host_id,
        kind="trait_revoke",
        value={"trait": "Force"},
        duration="permanent",
    ))
    # "…and all abilities EXCEPT FOR GRIT.  Attached unit gains Grit" — the Grit
    # cannot ride on a ConstantAbility here, because this same upgrade suppresses the
    # host's ability reads (has_keyword returns False outright for a suppressed
    # unit).  It is instead a permanent keyword_grant modifier flagged
    # ``despite_suppression``, the one carve-out the keyword layer honours; its
    # lifetime is likewise tied to this upgrade staying in play.
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=host_id,
        kind="keyword_grant",
        value={"keyword": "Grit", "value": 0, "despite_suppression": True},
        duration="permanent",
    ))
    return state


@card_ability("SEC", "54")
def _exiled_from_the_force():
    """SEC_54 — Exiled from the Force (Upgrade, Condition): "Attached unit loses the
    Force trait and all abilities except for Grit.  Attached unit gains Grit."

    Three specs.  ``SuppressHostAbilities`` is the unified ability-suppression
    read-layer's upgrade-borne source (Imprisoned SHD_72), so "loses all abilities …
    and can't gain abilities" falls out of the upgrade's mere presence.  The Force trait is
    stripped by a permanent ``trait_revoke`` modifier armed on play, and the Grit by a
    permanent ``keyword_grant`` modifier flagged ``despite_suppression`` — the one
    carve-out ``has_keyword`` honours for a suppressed unit (a ConstantAbility could
    not work here: this very upgrade blacks out the host's ability reads)."""
    return [
        SuppressHostAbilities(),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_exiled_from_the_force_revoke)],
        ),
    ]


# ── Group sec-set:12 — Combat tricks, buffs & tempo ───────────────────────────

def _senate_warden_disclose(state, source_ci, target_id, event_ctx):
    """Senate Warden SEC_59 When Defeated: disclose [Vigilance] → give an
    Experience token to a unit (the ``select_token`` disclose-payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Vigilance"],
                  payoff="select_token",
                  payoff_args={"token_type": "Experience", "max_targets": 1,
                               "controller": "any", "kind": "unit"})
    return state


@card_ability("SEC", "59")
def _senate_warden():
    """SEC_59 — Senate Warden (Unit, Republic/Trooper): "When Defeated: You may
    disclose [Vigilance] (reveal a card from your hand with this aspect icon).  If
    you do, give an Experience token to a unit."

    A ``WhenDefeated`` trigger carrying one untargeted ``CustomEffect`` that pushes
    the ``disclose`` decision — the "you may" is the disclose Decline, and nothing
    is prompted at all when the hand cannot cover the icon (``push_disclose``
    self-gates).  "Give an Experience token to a unit" reuses the existing
    ``select_token`` payoff arm (Vice Admiral Rampart SEC_85) with ``max_targets=1``
    over every unit in play.  DOCUMENTED DEVIATION: ``select_token`` is an "up to",
    so the printed mandatory gift can be declined after disclosing."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_senate_warden_disclose)],
    )


@card_ability("SEC", "63")
def _rotunda_senate_guards():
    """SEC_63 — Rotunda Senate Guards (Unit, Republic/Trooper): "While this unit is
    undamaged, it gains Sentinel."

    The conditional-self-grant pattern (Anakin Skywalker SEC_201 / Nubian Star Skiff
    SEC_116): a ``ConstantAbility(target=SELF, KeywordGrant("Sentinel"))`` gated by
    ``SOURCE_UNDAMAGED`` and read passively by ``keywords.has_keyword`` — so the
    Sentinel comes and goes with the unit's damage, including mid-combat.
    Registering it makes the keyword sanitiser strip the printed "Sentinel" bar
    (rule 2), leaving this ability the sole owner of the keyword."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.SOURCE_UNDAMAGED),
    )


@card_ability("SEC", "64")
def _congress_of_malastare():
    """SEC_64 — Congress of Malastare (Unit, Official/Republic): "The first upgrade
    you play each phase costs 1 resource less."

    A ``StandingPlayDiscount`` passive marker (Director Krennic JTLP_1), read at the
    single play-cost seam so affordability and payment agree and spent at the real
    play site.  The new ``applies_to="upgrade"`` predicate is the host-free sibling
    of Guardian of the Whills SOR_61's ``upgrade_on_source``: card type only, any
    host.  "Each phase" is modelled as ``once_per_round`` (the Malakili LOF_108
    equivalence — there is one action phase per round, and no card is played in a
    regroup phase)."""
    return StandingPlayDiscount(amount=1, applies_to="upgrade", once_per_round=True)


def _nala_se_disclose(state, source_ci, target_id, event_ctx):
    """Nala Se SEC_65 On Attack: disclose [Vigilance][Vigilance] → heal up to 4
    damage from among OTHER units (the new ``distribute_heal`` payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Vigilance", "Vigilance"],
                  payoff="distribute_heal", payoff_args={"amount": 4})
    return state


@card_ability("SEC", "65")
def _nala_se():
    """SEC_65 — Nala Se (Unit, Kaminoan): "On Attack: You may disclose
    [Vigilance][Vigilance] (reveal cards from your hand with these aspect icons
    among them).  If you do, heal up to 4 damage from among other units."

    An ``OnAttack`` trigger whose untargeted ``CustomEffect`` pushes a two-icon
    ``disclose``; the payoff is the new ``distribute_heal`` arm, which reuses the
    Redemption SOR_52 heal-pool decision (allocate the pool one point at a time,
    stop early — it is an "up to") with three widenings: units only
    (``include_bases=False``), either player's units (``target_controller="any"`` —
    the printed "among other units" is unqualified), and Nala Se herself excluded
    ("other").  ``then_damage_self=False``: only Redemption pays its heal back."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_nala_se_disclose)],
    )


@card_ability("SEC", "69")
def _nimble_prowess():
    """SEC_69 — Nimble Prowess (Upgrade, Innate): "Attach to a friendly unit.  When
    Played: You may exhaust a unit in attached unit's arena."

    The Mandalorian JTL_210 shape ("When played as an upgrade: Exhaust an enemy unit
    in this arena"): an optional ``WhenPlayed`` trigger with a declarative
    ``ExhaustCard`` whose target carries the ``same_arena_as_host`` predicate — the
    upgrade play path threads ``event_ctx["attached_to_id"]``, so "attached unit's
    arena" needs no new machinery.  ``controller="any"`` because the printed text
    says "a unit", not "an enemy unit"; the host itself is a legal choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit",
                                        predicates=("same_arena_as_host",)))],
    )


@card_ability("SEC", "71")
def _disciples_devotion():
    """SEC_71 — Disciples' Devotion (Upgrade, Innate): "While attached unit is
    exhausted, it gains Sentinel."

    The "attached unit gains …" shape (Biggs Darklighter JTL_150): a
    ``ConstantAbility(target=SELF, KeywordGrant("Sentinel"))`` read off the HOST by
    the attached-upgrade scan in ``keywords.has_keyword``, which evaluates the
    condition against that host — so ``SOURCE_EXHAUSTED`` here means "while the
    attached unit is exhausted".  ``upgrade_only=True`` keeps the arena constant
    scan from ever conferring it on the upgrade card itself."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.SOURCE_EXHAUSTED),
        upgrade_only=True,
    )


def _relief_request_first(state, source_ci, target_id, event_ctx):
    """Relief Request SEC_74 first effect: heal 3 from the chosen unit and record
    its id so the disclose payoff heals 'another' one."""
    if target_id is None:
        return state
    event_ctx["excluded_target_id"] = target_id
    res = state.find_instance(target_id)
    if res is not None:
        from swu.engine.actions import note_unit_healed
        healed = min(3, int(res[1].damage))
        if healed > 0:
            res[1].damage -= healed
            note_unit_healed(state, res[1], healed)
    return state


def _relief_request_disclose(state, source_ci, target_id, event_ctx):
    """SEC_74 payoff: disclose [Vigilance] → heal 3 from the pre-chosen 'another'
    unit (the new ``heal_unit`` disclose-payoff arm)."""
    from swu.engine.actions import push_disclose
    if target_id is None:
        return state
    push_disclose(state, source_ci, ["Vigilance"],
                  payoff="heal_unit",
                  payoff_args={"target_id": target_id, "amount": 3})
    return state


@card_ability("SEC", "74")
def _relief_request():
    """SEC_74 — Relief Request (Event, Law): "Heal 3 damage from a unit.  You may
    disclose [Vigilance] (reveal a card from your hand with this aspect icon).  If
    you do, heal 3 damage from another unit."

    The With Thunderous Applause SEC_129 structure with a heal in place of the buff:
    a mandatory ``CustomEffect.target`` heals the chosen unit and records
    ``event_ctx["excluded_target_id"]``; a second ``CustomEffect.target`` picks
    "another unit" (``excludes_event_target``) and pushes the ``disclose`` decision,
    whose new ``heal_unit`` arm does the second heal.  Both units are chosen before
    disclosing (the SEC_129 pre-chosen convention, a cosmetic reorder); with only
    one unit on the board the second target fizzles and nothing is disclosed."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_relief_request_first,
            target=TargetSpec(controller="any", kind="unit"),
        ),
        CustomEffect(
            fn=_relief_request_disclose,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("excludes_event_target",)),
        ),
    ])


# ── Group sec-set:13 — Combat tricks, buffs & tempo ───────────────────────────

def _premor_carrier_experience(state, source_ci, target_id, event_ctx):
    """PreMor Personnel Carrier SEC_89: one Experience token per friendly GROUND
    unit (the Carrier itself counts when it landed in a ground arena)."""
    from swu.engine.state import Zone
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    n = len(ps.ground_arena)
    host = state.find_instance(source_ci.instance_id)
    if host is None or n <= 0:
        return state
    for _ in range(n):
        attach_token(state, ps, host[1], "Experience")
    return state


@card_ability("SEC", "89")
def _premor_personnel_carrier():
    """SEC_89 — PreMor Personnel Carrier (Unit, Transport/Vehicle; Overwhelm):
    "When Played: Give this unit an Experience token for each ground unit you
    control."

    Overwhelm is the keyword layer.  ``GiveToken`` carries a FIXED ``count``, so the
    "for each" magnitude is a thin ``CustomEffect`` over the same ``attach_token``
    seam — the scaling-magnitude shape (Ahsoka Tano SEC/TWI's DealDamageEqualTo)
    without minting a token-flavoured count source for one card.  The Carrier is a
    ground unit itself and is already in its arena when the trigger resolves, so it
    counts (the printed "each ground unit you control" is unqualified)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_premor_carrier_experience)],
    )


def _corporate_warmongering_first(state, source_ci, target_id, event_ctx):
    """Corporate Warmongering SEC_91 first effect: +3/+3 to the chosen friendly
    unit, recording it so the mass +1/+1 skips it ("each OTHER friendly unit")."""
    if target_id is None:
        return state
    event_ctx["excluded_target_id"] = target_id
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=3, hp=3, duration=Duration.THIS_PHASE))
    return state


@card_ability("SEC", "91")
def _corporate_warmongering():
    """SEC_91 — Corporate Warmongering (Event, Plan): "Give a friendly unit +3/+3
    for this phase.  Give each other friendly unit +1/+1 for this phase."

    A targeted ``CustomEffect`` buffs the chosen unit and records
    ``event_ctx["excluded_target_id"]`` (the Grenade Strike TWI_171 pattern); the
    fixed ``EACH_FRIENDLY`` ``ModifyStats`` that follows carries the
    ``excludes_event_target`` predicate, which the EACH_* expansion propagates into
    its sub-spec — so the first unit is not double-buffed.  Targeted effect first,
    fixed second: exactly one prompt."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_corporate_warmongering_first,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        ModifyStats(
            power=1, hp=1,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("excludes_event_target",),
                              fixed=EACH_FRIENDLY),
            duration=Duration.THIS_PHASE,
        ),
    ])


@card_ability("SEC", "95")
def _theed_security():
    """SEC_95 — Theed Security (Unit, Naboo/Trooper): "When Played: If an opponent
    controls an upgrade, give an Experience token to a unit."

    A ``WhenPlayed`` trigger gated by the existing ``ENEMY_UNIT_UPGRADED`` condition
    (the TriggerAbility.condition gate: false ⇒ the trigger is never collected, so
    there is no prompt at all), giving one Experience token to any unit in play.
    DOCUMENTED DEVIATION: ``ENEMY_UNIT_UPGRADED`` asks whether an upgrade sits on an
    enemy UNIT, which is the overwhelmingly common reading of "an opponent controls
    an upgrade"; an opponent-controlled upgrade parked on one of YOUR units (a
    Bounty) is not seen."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.ENEMY_UNIT_UPGRADED),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="any", kind="unit"))],
    )


def _renowned_dignitaries_heal(state, source_ci, target_id, event_ctx):
    """Renowned Dignitaries SEC_102: heal 2 from the controller's base per friendly
    Official unit (the source itself is an Official and counts)."""
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for ci in list(ps.ground_arena) + list(ps.space_arena)
            if has_trait(state, ci, "Official"))
    if ps.base_instance is not None and n > 0:
        ps.base_instance.damage = max(0, int(ps.base_instance.damage) - 2 * n)
    return state


@card_ability("SEC", "102")
def _renowned_dignitaries():
    """SEC_102 — Renowned Dignitaries (Unit, New Republic/Official; Overwhelm):
    "When Played: Heal 2 damage from your base for each friendly Official unit."

    Overwhelm is the keyword layer.  ``Heal`` carries a FIXED ``amount``, so the
    "for each" magnitude is a thin ``CustomEffect`` (the SEC_89 shape) that counts
    friendly Official units — trait grants included, via ``traits.has_trait`` — and
    heals 2× that from the controller's own base.  The Dignitaries are themselves an
    Official unit and are in play when the trigger resolves, so they count."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_renowned_dignitaries_heal)],
    )


@card_ability("SEC", "104")
def _figure_of_unity():
    """SEC_104 — Figure of Unity (Upgrade, Innate): "Attach to a unique unit.
    Attached unit gains: 'While this unit is ready, each other friendly unit gains
    Overwhelm, Raid 1, and Restore 1.'"

    An upgrade-borne AURA over third cards — neither existing scan could express it
    (the arena scans only see units; the attached-upgrade scans only handle
    ``target=SELF``, i.e. the host itself).  The new ``via_host`` flag makes the two
    keyword scans also walk each arena unit's attached upgrades, evaluating the
    spec's condition and target with the HOST as ``source_ci``: so ``SOURCE_READY``
    is "while THIS UNIT is ready" and ``controller="friendly"`` + ``not_self`` is
    "each other friendly unit".  The upgrade's own printed Overwhelm/Raid/Restore
    bar is the usual upstream mis-tag for a grants-to-others card (an attached
    upgrade's printed keywords are never conferred on its host anyway).

    Note this aura is keyword-only: the ``via_host`` widening covers
    ``has_keyword``/``keyword_value``, the two layers this card needs."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
        effects=[KeywordGrant("Overwhelm"),
                 KeywordGrant("Raid", 1),
                 KeywordGrant("Restore", 1)],
        condition=ConditionCheck(Condition.SOURCE_READY),
        via_host=True,
    )


def _chancellor_valorum_disclose(state, source_ci, target_id, event_ctx):
    """Chancellor Valorum SEC_107 When Attack Ends: disclose [Command]×3 → put the
    top card of your deck into play as a resource (the new ``resource_top_of_deck``
    disclose-payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Command", "Command", "Command"],
                  payoff="resource_top_of_deck")
    return state


@card_ability("SEC", "107")
def _chancellor_valorum():
    """SEC_107 — Chancellor Valorum (Unit, Official/Republic): "When this unit
    completes an attack: You may disclose [Command][Command][Command] (reveal cards
    from your hand with these aspect icons among them).  If you do, put the top card
    of your deck into play as a resource."

    ``WhenAttackEnds`` is exactly "completes an attack" (it fires only for an
    attacker still in play after defeat processing).  Its one untargeted
    ``CustomEffect`` pushes a three-icon ``disclose`` — the "you may" is the disclose
    Decline, and a hand that cannot cover three Command icons is never prompted.
    The payoff is the new ``resource_top_of_deck`` arm over the existing
    ``_resource_top_of_deck`` ramp seam (Bail Organa SEC_8)."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_chancellor_valorum_disclose)],
    )


@card_ability("SEC", "108")
def _senators_aide():
    """SEC_108 — Senator's Aide (Unit, Official/Republic, 0/3): "While you have the
    initiative, this unit gets +2/+0."

    The conditional self-buff shape: a ``ConstantAbility(target=SELF,
    StatBonus(2, 0))`` gated by the existing ``CONTROLLER_HAS_INITIATIVE`` atom and
    read passively by ``compute_power``, so the buff appears and disappears with the
    initiative token — no trigger, no modifier bookkeeping."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(2, 0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


# ── Group sec-set:14 — Combat tricks, buffs & tempo ───────────────────────────

def _diplomatic_envoy_disclose(state, source_ci, target_id, event_ctx):
    """Diplomatic Envoy SEC_109 When Played: disclose [Command] → the next unit you
    play this phase gains Ambush (the new ``pending_keyword_grant`` payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Command"],
                  payoff="pending_keyword_grant",
                  payoff_args={"keyword": "Ambush"})
    return state


@card_ability("SEC", "109")
def _diplomatic_envoy():
    """SEC_109 — Diplomatic Envoy (Unit, Republic/Transport/Vehicle; Ambush): "When
    Played: You may disclose [Command] (reveal a card from your hand with this
    aspect icon).  If you do, the next unit you play this phase gains Ambush for
    this phase."

    Ambush on the Envoy itself is the keyword layer.  The functional text is a
    ``WhenPlayed`` ``CustomEffect`` that pushes a one-icon ``disclose`` (the "you
    may" is the Decline; an uncoverable hand is never prompted), whose new
    ``pending_keyword_grant`` payoff arm arms one entry on the
    ``pending_keyword_grants`` ledger (Deceptive Shade LOF_180).  That ledger is
    consumed in ``_put_unit_in_play`` BEFORE the enter-play keyword bus, so the
    granted Ambush fires on entry exactly as a printed one would."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_diplomatic_envoy_disclose)],
    )


@card_ability("SEC", "110")
def _gnk_power_droid():
    """SEC_110 — GNK Power Droid (Unit, Droid): "On Attack: The next unit you play
    this phase costs 1 resource less."

    Exactly the ``NextPlayDiscount`` seam (Khetanna LAW_158) with no trait filter:
    one pending entry on ``game_memory.pending_play_discounts`` for the Droid's
    controller, read by ``_play_cost`` and consumed by the next matching unit play,
    lifting at the phase rollover.  ``units_only`` is the default — the printed
    "next UNIT you play"."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[NextPlayDiscount(trait="", amount=1)],
    )


@card_ability("SEC", "119")
def _crucible():
    """SEC_119 — Crucible (Unit, Jedi/Transport/Vehicle): "When Played/When
    Defeated: Give an Experience token to each other friendly unit."

    One functional line firing on TWO windows, so two ``TriggerAbility``s (the Naboo
    Security Force SEC_120 shape) carrying the same fixed ``GiveToken`` over
    ``EACH_FRIENDLY`` with ``not_self`` — "each OTHER friendly unit".  No target
    prompt: the EACH_* expansion resolves the whole set.  On the When Defeated fire
    the Crucible has already left the arena, so ``not_self`` is belt-and-braces."""
    give = GiveToken("Experience",
                     TargetSpec(controller="friendly", kind="unit",
                                predicates=("not_self",), fixed=EACH_FRIENDLY))
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[give]),
        TriggerAbility(trigger=WhenDefeated(), effects=[give]),
    ]


@card_ability("SEC", "122")
def _vuutun_palaa():
    """SEC_122 — Vuutun Palaa (Unit, Capital Ship/Separatist/Vehicle): "This unit
    costs 1 resource less to play for each friendly Droid unit.  Each friendly Droid
    unit may be exhausted to pay costs as if it were a resource."

    Two specs, both read at the play-cost/payment seam and neither a trigger:

      * ``CostReduction(1, per_friendly_trait="Droid")`` — the new trait-parameterised
        scaling arm (the ``per_friendly_pilots`` basis without its upgrade leg).  The
        Palaa is in hand while this is read, so it never counts itself.
      * ``UnitsPayCosts(traits=("Droid",))`` — the new passive marker: while the
        Palaa is in play its controller may exhaust friendly Droid units to pay, "as
        if it were a resource".  Spending is need-based and automatic (the Credit
        economy's shape): resources, then credits, then units — so a Droid is never
        tapped for a play the resource row could already afford."""
    return [
        CostReduction(amount=1, per_friendly_trait="Droid"),
        UnitsPayCosts(traits=("Droid",)),
    ]


@card_ability("SEC", "134")
def _hunting_assassin_droid():
    """SEC_134 — Hunting Assassin Droid (Unit, Bounty Hunter/Droid/Underworld):
    "While an enemy unit is damaged, this unit gains Raid 2."

    The conditional-self-grant pattern (Anakin Skywalker SEC_201): a
    ``ConstantAbility(target=SELF, KeywordGrant("Raid", 2))`` gated by the existing
    ``ENEMY_HAS_DAMAGED_UNIT`` atom and read passively by ``keyword_value``, so the
    Raid appears and vanishes with the enemy board.  Registering it makes the keyword
    sanitiser strip the printed "Raid" bar (rule 2)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 2)],
        condition=ConditionCheck(Condition.ENEMY_HAS_DAMAGED_UNIT),
    )


@card_ability("SEC", "135")
def _muckraker_crab_droid():
    """SEC_135 — Muckraker Crab Droid (Unit, Droid/Separatist): "While this unit is
    ready, it can't be attacked."

    The Sabine Wren TWI_195 marker with its readiness test inverted — the new
    ``while_ready`` flag on ``CannotBeAttackedWhileExhausted``, read at the same
    single attack-enumeration seam (``_cannot_be_attacked``), so a ready Crab Droid
    simply drops out of the eligible-defender set and therefore neither blocks nor
    forces anything.  It becomes attackable the moment it exhausts (i.e. after it
    attacks).  The marker's standing Sentinel escape is inherited; the Crab Droid
    prints no Sentinel, so it only ever matters if one is granted."""
    return CannotBeAttackedWhileExhausted(while_ready=True)


def _dryden_vos_sec_137(state, source_ci, target_id, event_ctx):
    """Dryden Vos SEC_137 On Attack: double his power for this attack (a +power
    modifier equal to his CURRENT effective power, so the doubling reflects any
    other buff already applied) and lock him down for the next regroup."""
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import _make_modifier
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    ci = res[1]
    bonus = compute_power(state, ci)
    if bonus > 0:
        state.modifiers.append(_make_modifier(
            state, ci.instance_id, ci.instance_id,
            power=bonus, hp=0, duration=Duration.THIS_ATTACK))
    ci.cannot_ready_this_round = True
    return state


@card_ability("SEC", "137")
def _dryden_vos_sec():
    """SEC_137 — Dryden Vos (Unit, Underworld, 2/5): "On Attack: You may double this
    unit's power for this attack.  If you do, this unit doesn't ready during the
    next regroup phase."

    An OPTIONAL ``OnAttack`` trigger — the "you may" — whose single ``CustomEffect``
    binds cost and payoff together ("if you do"): it adds a ``THIS_ATTACK`` stat
    modifier equal to Dryden's current effective power (doubling whatever he is
    worth right now, buffs included) and sets ``cannot_ready_this_round``, the
    existing keep-tapped flag ``_end_regroup`` honours (No Good to Me Dead SOR_186).
    DOCUMENTED SIMPLIFICATION: that flag is round-scoped rather than
    "next-regroup"-scoped, which coincides except under Max Rebo LAW_72's extra
    regroup phase."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(fn=_dryden_vos_sec_137)],
    )


# ── Group sec-set:15 — Combat tricks, buffs & tempo ───────────────────────────

@card_ability("SEC", "140")
def _hondo_ohnaka_sec():
    """SEC_140 — Hondo Ohnaka (Unit, Underworld; Plot, Raid): "Each other friendly
    unit gains Raid 1."

    Plot and Hondo's own Raid are the keyword layers.  The functional line is the
    plain keyword-anthem aura (Coronet SEC_47): a ``ConstantAbility`` over
    ``EACH_FRIENDLY`` with ``not_self``, granting ``Raid 1``, read passively by
    ``keyword_value``.  Hondo's printed Raid stays his own — the aura excludes
    him, so the sanitiser's grants-to-others rule must not strip it; it keys on
    SELF-targeted grants, and this one is not."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",), fixed=EACH_FRIENDLY),
        effects=[KeywordGrant("Raid", 1)],
    )


@card_ability("SEC", "151")
def _kazuda_xiono():
    """SEC_151 — Kazuda Xiono (Unit, Resistance, 2/6; Raid 2): "While you control
    fewer resources than an opponent, this unit gets +2/+0."

    Raid 2 is the keyword layer.  The functional line is the conditional self-buff
    shape (Senator's Aide SEC_108) over the existing
    ``OPPONENT_MORE_RESOURCES_THAN_CONTROLLER`` atom — literally "you control fewer
    resources than an opponent" — read passively by ``compute_power``."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(2, 0)],
        condition=ConditionCheck(
            Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER),
    )


@card_ability("SEC", "154")
def _inner_rim_coalition():
    """SEC_154 — Inner Rim Coalition (Unit, Official/Republic): "When Defeated: You
    may ready a unit that costs 5 or less."

    An optional ``WhenDefeated`` carrying the declarative ``ReadyCard`` with a
    ``cost_max=5`` target — no new machinery.  ``controller="any"``: the printed "a
    unit" is unqualified (the bot's don't-help-the-enemy heuristic keeps it sane in
    practice)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[ReadyCard(TargetSpec(controller="any", kind="unit", cost_max=5))],
    )


def _one_way_out_sec_157(state, source_ci, target_id, event_ctx):
    """One Way Out SEC_157: a granted attack whose attacker gets +1/+0 and Overwhelm
    for the attack, and whose unit defender loses all abilities for it."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(
        state, source_ci, power_bonus=1,
        grant_keywords=["Overwhelm"],
        defender_suppress_abilities=True,
    )
    return state


@card_ability("SEC", "157")
def _one_way_out():
    """SEC_157 — One Way Out (Event, Gambit): "Attack with a unit.  It gets +1/+0
    and gains Overwhelm for this attack.  If it attacks a unit, the defender loses
    all abilities for this attack."

    The ``granted_attack`` seam carries the first two clauses directly
    (``power_bonus`` + ``grant_keywords``).  The third is the new
    ``defender_suppress_abilities`` flag: at the AttackWithUnit site — the one place
    that knows the chosen defender — it applies a ``this_attack``
    ``abilities_suppressed`` modifier, the new modifier-backed arm of the unified
    ``state.ability_suppressed`` read.  Only a UNIT defender is affected ("if it
    attacks a unit"); a base attack simply skips it, and the modifier is swept with
    every other this-attack modifier."""
    return EventAbility(effects=[CustomEffect(fn=_one_way_out_sec_157)])


def _cinta_kaz_sec_172(state, source_ci, target_id, event_ctx):
    """Cinta Kaz SEC_172 When Played: "You may attack with a unit."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True)
    return state


@card_ability("SEC", "172")
def _cinta_kaz():
    """SEC_172 — Cinta Kaz (Unit, Rebel; Plot): "When Played: You may attack with a
    unit."

    Plot is the keyword layer.  The functional line is the bare ``granted_attack``
    seam with ``optional=True`` (the "you may" lives in the decision's Decline, so
    the trigger itself stays mandatory and never double-prompts).  No attacker
    filter: the printed "a unit" includes Cinta herself, though she entered play
    exhausted and so cannot usually take it."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_cinta_kaz_sec_172)],
    )


def _saw_gerreras_uwing_sec_174(state, source_ci, target_id, event_ctx):
    """Saw Gerrera's U-Wing SEC_174 When Attack Ends: "You may attack with another
    Aggression unit" (the ``attacker_aspect`` + ``exclude_source`` filters)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True,
                        attacker_aspect="Aggression", exclude_source=True)
    return state


@card_ability("SEC", "174")
def _saw_gerreras_uwing():
    """SEC_174 — Saw Gerrera's U-Wing (Unit, Fighter/Rebel/Vehicle; Saboteur): "When
    this unit completes an attack: You may attack with another Aggression unit."

    Saboteur is the keyword layer.  ``WhenAttackEnds`` is exactly "completes an
    attack" (it fires only for an attacker still in play after defeat processing),
    and the granted attack reuses the existing ``attacker_aspect`` filter plus
    ``exclude_source`` for "ANOTHER".  With no other Aggression unit ready the
    decision fizzles through its own Decline."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_saw_gerreras_uwing_sec_174)],
    )


@card_ability("SEC", "177")
def _its_not_over_yet():
    """SEC_177 — It's Not Over Yet (Event, Innate): "You may ready a unit that
    didn't attack or enter play this phase.  Create a Spy token."

    A targeted ``ReadyCard`` first (its ``optional`` target is the "you may"), then
    the fixed ``CreateTokenUnit`` — targeted-before-fixed, so there is exactly one
    prompt (the Contempt for Culture SEC_246 ordering).  The target filter is two
    predicates: the existing ``not_played_this_phase`` ("didn't enter play this
    phase", over ``units_played_this_phase``) and the new
    ``not_attacked_this_phase``, its mirror over ``units_attacked_this_round``."""
    return EventAbility(effects=[
        ReadyCard(TargetSpec(controller="any", kind="unit", optional=True,
                             predicates=("not_played_this_phase",
                                         "not_attacked_this_phase"))),
        CreateTokenUnit("Spy"),
    ])


# ── Group sec-set:16 — Combat tricks, buffs & tempo ───────────────────────────

def _aggressive_negotiations_sec_179(state, source_ci, target_id, event_ctx):
    """Aggressive Negotiations SEC_179: a granted attack whose attacker gets +1/+0
    per card in the controller's hand, measured NOW (the event has already left the
    hand, so it never counts itself)."""
    from swu.engine.actions import push_granted_attack
    hand = len(state.player_by_id(source_ci.owner_id).hand)
    push_granted_attack(state, source_ci, power_bonus=hand)
    return state


@card_ability("SEC", "179")
def _aggressive_negotiations():
    """SEC_179 — Aggressive Negotiations (Event, Tactic): "Attack with a unit.  For
    this attack, it gets +1/+0 for each card in your hand."

    The plain ``granted_attack`` seam: the "for each card in your hand" magnitude is
    a fixed ``power_bonus`` computed at push time, which is when the effect resolves
    — the event is already out of hand by then, so it never counts itself.  Drawing
    a card mid-attack does not retroactively grow the bonus (a documented reading of
    "for this attack", and the same convention the other granted-attack bonuses
    use)."""
    return EventAbility(effects=[CustomEffect(fn=_aggressive_negotiations_sec_179)])


def _soulless_one_disclose(state, source_ci, target_id, event_ctx):
    """Soulless One SEC_190 On Attack: disclose [Cunning][Cunning][Villainy] → ready
    2 resources (the new ``ready_resources`` payoff arm)."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Cunning", "Cunning", "Villainy"],
                  payoff="ready_resources", payoff_args={"count": 2})
    return state


@card_ability("SEC", "190")
def _soulless_one():
    """SEC_190 — Soulless One (Unit, Fighter/Separatist/Vehicle): "On Attack: You
    may disclose [Cunning][Cunning][Villainy] (reveal cards from your hand with
    these aspect icons among them).  If you do, ready 2 resources."

    An ``OnAttack`` trigger whose untargeted ``CustomEffect`` pushes a three-icon
    ``disclose`` (the icons are a multiset, so one Cunning/Villainy card covers two
    of the three at once).  The payoff is the new ``ready_resources`` arm — the
    ramp mirror of ``heal_base``, readying up to N exhausted resources."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_soulless_one_disclose)],
    )


def _no_one_ever_knew_sec_196(state, source_ci, target_id, event_ctx):
    """No One Ever Knew SEC_196: exhaust one enemy unit per friendly Official."""
    from swu.engine.actions import push_select_token
    from swu.engine.traits import has_trait
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for ci in list(ps.ground_arena) + list(ps.space_arena)
            if has_trait(state, ci, "Official"))
    if n > 0:
        push_select_token(state, source_ci, token_type=None, max_targets=n,
                          controller="enemy", kind="unit", exhaust=True)
    return state


@card_ability("SEC", "196")
def _no_one_ever_knew():
    """SEC_196 — No One Ever Knew (Event, Trick): "For each friendly Official unit,
    exhaust an enemy unit."

    The ``select_token`` decision (pick distinct units one at a time up to a cap)
    with the new ``exhaust`` payoff — the mirror of its existing ``ready`` mode, and
    it honours Protection exactly as the declarative ``ExhaustCard`` arm does.  The
    cap is the count of friendly Official units, read through ``has_trait`` so trait
    grants count; with none the event fizzles with no prompt.  DOCUMENTED DEVIATION:
    ``select_token`` is an "up to", so the printed mandatory exhausts can be stopped
    early."""
    return EventAbility(effects=[CustomEffect(fn=_no_one_ever_knew_sec_196)])


def _rebel_propagandist_sec_202(state, source_ci, target_id, event_ctx):
    """Rebel Propagandist SEC_202: the chosen other friendly unit gets +1/+0 and
    Saboteur for this phase (both payoffs on ONE chosen target, so one prompt)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _make_modifier, _make_kw_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=1, hp=0, duration=Duration.THIS_PHASE))
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id,
        keyword="Saboteur", value=0,
        duration=Duration.THIS_PHASE, kind="keyword_grant"))
    return state


@card_ability("SEC", "202")
def _rebel_propagandist():
    """SEC_202 — Rebel Propagandist (Unit, Official/Rebel; Saboteur): "When
    Played/When Defeated: Give another friendly unit +1/+0 and Saboteur for this
    phase."

    Saboteur on the Propagandist is the keyword layer.  One functional line on TWO
    windows, so two ``TriggerAbility``s (the Naboo Security Force SEC_120 shape).
    Both payoffs ride ONE ``CustomEffect.target`` rather than a ModifyStats plus a
    GrantKeyword — two targeted effects would prompt twice for what the card calls a
    single unit.  ``not_self`` is the printed "ANOTHER"; with no other friendly unit
    the effect fizzles with no prompt."""
    eff = CustomEffect(
        fn=_rebel_propagandist_sec_202,
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
    )
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[eff]),
        TriggerAbility(trigger=WhenDefeated(), effects=[eff]),
    ]


@card_ability("SEC", "204")
def _blue_ace():
    """SEC_204 — Blue Ace (Unit, Fighter/Resistance/Vehicle; Ambush): "On Attack:
    Ready an exhausted enemy unit."

    Ambush is the keyword layer.  The functional line is the declarative
    ``ReadyCard`` over an enemy target with the ``exhausted`` predicate — a printed
    DOWNSIDE (readying an enemy), so it is mandatory, and it fizzles cleanly with no
    prompt when every enemy unit is already ready."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ReadyCard(TargetSpec(controller="enemy", kind="unit",
                                      predicates=("exhausted",)))],
    )


def _lightmaker_sec_207(state, source_ci, target_id, event_ctx):
    """Lightmaker SEC_207 When Defeated: "Choose an arena" — a one-of-two
    ``choose_two_modal`` selector over the two arena options registered at ability
    indices 1 (ground) and 2 (space)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


@card_ability("SEC", "207")
def _lightmaker():
    """SEC_207 — Lightmaker (Unit, Capital Ship/Rebel/Vehicle; Raid 4): "When
    Defeated: Choose an arena.  Exhaust each enemy unit in that arena."

    Raid 4 is the keyword layer.  "Choose an arena" is the ``choose_two_modal``
    SELECTOR with ``pick=1`` (the SOR aspect-event machinery): index 0 is the
    ``WhenDefeated`` controller, and indices 1/2 are the two arena options, each an
    ``EventAbility`` (never trigger-collected — this is a unit card) carrying one
    fixed ``ExhaustCard`` over ``EACH_ENEMY`` narrowed by ``arena``.  All targeting
    stays in the ordinary resolve_effects machinery, so the option resolves with no
    further prompt."""
    return [
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_lightmaker_sec_207)],
        ),
        EventAbility(effects=[ExhaustCard(
            TargetSpec(controller="enemy", kind="unit", arena="ground",
                       fixed=EACH_ENEMY))]),
        EventAbility(effects=[ExhaustCard(
            TargetSpec(controller="enemy", kind="unit", arena="space",
                       fixed=EACH_ENEMY))]),
    ]


def _libertine_pick_captor(state, source_ci, target_id, event_ctx):
    """Libertine SEC_212 first effect: record the chosen ENEMY captor."""
    if target_id is not None:
        event_ctx["captor_id"] = target_id
    return state


def _libertine_capture(state, source_ci, target_id, event_ctx):
    """SEC_212 second effect: the recorded enemy unit captures the chosen friendly
    non-leader unit."""
    from swu.engine.actions import _apply_capture
    captor_id = event_ctx.get("captor_id")
    if (captor_id and target_id
            and state.find_instance(captor_id) is not None
            and state.find_instance(target_id) is not None):
        state = _apply_capture(state, captor_id, target_id)
    return state


@card_ability("SEC", "212")
def _libertine():
    """SEC_212 — Libertine (Unit, Transport/Underworld/Vehicle, 3/7): "This unit
    gets +1/+0 for each captured card it's guarding.  When Played: Choose an enemy
    unit and a non-leader friendly unit.  The enemy unit captures the friendly
    unit."

    Two specs.  The scaling self-buff is a ``ConstantAbility(SELF, StatBonus(count=
    "captives_guarded"))`` — a new count source that scans the capture piles for
    captives whose ``captured_by`` is this unit, read passively by ``compute_power``.
    The When Played is the two-dependent-targets capture shape (Charged with
    Corruption SEC_127 / Thrawn SEC_193): the first ``CustomEffect.target`` records
    the enemy captor in the shared ``event_ctx``, the second picks the friendly
    non-leader prey and runs ``_apply_capture``.  Either target missing ⇒ nothing
    happens (the Libertine itself is a legal prey — the printed text says only
    "a non-leader friendly unit")."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(1, 0, count="captives_guarded")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[
                CustomEffect(
                    fn=_libertine_pick_captor,
                    target=TargetSpec(controller="enemy", kind="unit"),
                ),
                CustomEffect(
                    fn=_libertine_capture,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      predicates=("non_leader",)),
                ),
            ],
        ),
    ]


# ── Group sec-set:17 — Combat tricks, buffs & tempo ───────────────────────────

def _ready_exhausted_resources(state, ps, count):
    """Ready up to ``count`` of ``ps``'s exhausted resources.  Resources are
    interchangeable face-down cards, so which ones is never a choice."""
    for r in ps.resources:
        if count <= 0:
            break
        if r.exhausted:
            r.exhausted = False
            count -= 1
    return state


def _emissarys_sheathipede_sec_215(state, source_ci, target_id, event_ctx):
    """Emissary's Sheathipede SEC_215 When Defeated: each opponent readies one
    resource."""
    own = source_ci.owner_id
    for ps in state.players:
        if ps.player_id != own:
            _ready_exhausted_resources(state, ps, 1)
    return state


@card_ability("SEC", "215")
def _emissarys_sheathipede():
    """SEC_215 — Emissary's Sheathipede (Unit, Separatist/Transport/Vehicle): "When
    Defeated: Each opponent may ready a resource."

    A ``WhenDefeated`` ``CustomEffect`` readying one exhausted resource for every
    opponent.  DOCUMENTED SIMPLIFICATION (the Elia Kane SEC_242 convention):
    resources are interchangeable face-down cards, so WHICH one is never a choice —
    and the "may" belongs to the opponent, who is being handed a free resource and
    would never decline, so it is not prompted either.  With no exhausted resource
    the effect is a no-op."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_emissarys_sheathipede_sec_215)],
    )


def _regulations_bureaucrat_sec_216(state, source_ci, target_id, event_ctx):
    """Regulations Bureaucrat SEC_216: exhaust one ready ENEMY resource."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    for r in opp.resources:
        if not r.exhausted:
            r.exhausted = True
            break
    return state


@card_ability("SEC", "216")
def _regulations_bureaucrat():
    """SEC_216 — Regulations Bureaucrat (Unit, Imperial/Official, 0/5): "Action
    [Exhaust]: Exhaust a resource."

    An ``ActivatedAbility`` whose cost is a real ``ExhaustSelf`` and whose effect is
    a thin ``CustomEffect``.  DOCUMENTED SIMPLIFICATION (the Elia Kane SEC_242
    convention): the printed "a resource" is unqualified, but exhausting one's OWN
    resource is never useful, and resources are interchangeable face-down cards — so
    the effect always takes one ready ENEMY resource and never prompts.  With every
    enemy resource already exhausted it is a no-op."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_regulations_bureaucrat_sec_216)],
        title="Exhaust an enemy resource",
    )


def _ebon_hawk_sec_219(state, source_ci, target_id, event_ctx):
    """Ebon Hawk SEC_219 On Attack: two INDEPENDENT one-icon discloses ("and/or").
    Pushed Villainy-first so the LIFO stack offers Heroism first, matching the
    printed order; each self-gates on the hand and each has its own payoff."""
    from swu.engine.actions import push_disclose
    defender_id = event_ctx.get("defender_id")
    if defender_id and state.find_instance(defender_id) is not None:
        push_disclose(state, source_ci, ["Villainy"],
                      payoff="buff_unit",
                      payoff_args={"target_id": defender_id, "power": -4, "hp": 0,
                                   "duration": "this_attack"})
    push_disclose(state, source_ci, ["Heroism"],
                  payoff="buff_unit",
                  payoff_args={"target_id": source_ci.instance_id,
                               "power": 2, "hp": 0, "duration": "this_attack"})
    return state


@card_ability("SEC", "219")
def _ebon_hawk():
    """SEC_219 — Ebon Hawk (Unit, Fringe/Transport/Vehicle): "On Attack: You may
    disclose [Heroism] and/or [Villainy].  If you disclosed [Heroism], this unit
    gets +2/+0 for this attack.  If you disclosed [Villainy], give the defender
    −4/−0 for this attack."

    "And/or" is TWO independent one-icon ``disclose`` decisions, each with its own
    payoff — not one two-icon disclose, because either may be taken alone.  They are
    pushed Villainy-first so the LIFO stack offers Heroism first (the printed
    order), and each self-gates: a hand with no Villainy card is simply never asked.
    Both payoffs are the existing ``buff_unit`` arm with its new
    ``duration="this_attack"``: the Heroism one targets the Hawk itself, the
    Villainy one the defender read off ``event_ctx["defender_id"]`` (a base attack
    has no defender unit, so that half is skipped)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_ebon_hawk_sec_219)],
    )


def _hired_slicer_sec_220(state, source_ci, target_id, event_ctx):
    """Hired Slicer SEC_220 On Attack: reveal the opponent's top 2, offer an exhaust
    of any unit sharing a trait with them, then bottom the two in random order."""
    from swu.engine.actions import push_select_token
    from swu.engine.traits import has_trait
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    revealed = opp.deck[:2]
    if not revealed:
        return state
    traits = {t for ci in revealed
              for t in (getattr(ci.card_def, "traits", ()) or ())}
    # Bottom the revealed cards NOW, in a seeded-random order — the reveal is
    # instantaneous, so nothing about the opponent's deck stays visible while the
    # exhaust decision is open (and the hidden-info invariant has nothing to see).
    del opp.deck[:len(revealed)]
    rng = state.make_rng()
    rest = list(revealed)
    rng.shuffle(rest)
    opp.deck.extend(rest)
    if not traits:
        return state
    eligible = [u.instance_id
                for p in state.players
                for arena in (p.ground_arena, p.space_arena)
                for u in arena
                if any(has_trait(state, u, t) for t in traits)]
    if eligible:
        push_select_token(state, source_ci, token_type=None, max_targets=1,
                          controller="any", kind="unit", exhaust=True,
                          restrict_ids=eligible)
    return state


@card_ability("SEC", "220")
def _hired_slicer():
    """SEC_220 — Hired Slicer (Unit, Fringe): "On Attack: Reveal the top 2 cards of
    a deck.  If you do, you may exhaust a unit that shares a Trait with one of those
    cards.  Put those cards on the bottom of that deck in a random order."

    One ``CustomEffect``: it reads the opponent's top two cards, bottoms them
    immediately in a ``state.make_rng()`` order (deterministic and replayable), and
    offers the exhaust as a ``select_token`` with ``max_targets=1``, the new
    ``exhaust`` payoff, and a ``restrict_ids`` whitelist of every unit sharing a
    trait with the revealed pair — so the "you may" is the decision's own stop-early
    arm.  DOCUMENTED SIMPLIFICATIONS: "a deck" is always the OPPONENT's (looking at
    your own is strictly worse), and the two cards are bottomed before the choice
    rather than after, which is invisible mechanically and keeps the opponent's deck
    order off the wire."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_hired_slicer_sec_220)],
    )


@card_ability("SEC", "221")
def _unruly_astromech():
    """SEC_221 — Unruly Astromech (Unit, Droid; Hidden): "When Defeated: Exhaust an
    enemy unit."

    Hidden is the keyword layer.  The functional line is the declarative
    ``ExhaustCard`` over an enemy unit — mandatory, and it fizzles with no prompt
    when the opponent controls no unit."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit"))],
    )


def _synara_san_sec_225(state, source_ci, target_id, event_ctx):
    """Synara San SEC_225 On Attack: ready one friendly resource per friendly
    unit."""
    ps = state.player_by_id(source_ci.owner_id)
    n = len(ps.ground_arena) + len(ps.space_arena)
    return _ready_exhausted_resources(state, ps, n)


@card_ability("SEC", "225")
def _synara_san():
    """SEC_225 — Synara San (Unit, Underworld, 7/7; Hidden): "On Attack: For each
    friendly unit, ready a friendly resource."

    Hidden is the keyword layer.  The functional line is a thin ``CustomEffect``
    over the shared resource-ready helper: the count is the controller's units in
    both arenas (Synara herself is attacking, so she counts), and readying stops
    when no exhausted resource is left.  Which resources ready is never a choice
    (the fungible-resource convention)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_synara_san_sec_225)],
    )


def _accelerate_our_plans_sec_228(state, source_ci, target_id, event_ctx):
    """Accelerate Our Plans SEC_228: exhaust the chosen friendly unit; if it really
    exhausted, grant an attack (+3/+0) — the exhausted unit cannot take it itself,
    which IS the printed "another unit"."""
    from swu.engine.actions import push_granted_attack
    from swu.abilities.resolver import _target_protected
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    if _target_protected(state, target_id, source_ci, "exhaust"):
        return state          # the cost was not paid ⇒ no "if you do" attack
    res[1].exhausted = True
    push_granted_attack(state, source_ci, power_bonus=3)
    return state


@card_ability("SEC", "228")
def _accelerate_our_plans():
    """SEC_228 — Accelerate Our Plans (Event, Plan): "Exhaust a friendly unit.  If
    you do, attack with another unit.  It gets +3/+0 for this attack."

    One ``CustomEffect.target`` binds cost and payoff together (the "If you do"
    convention): it exhausts the chosen friendly unit — honouring Protection, and
    granting no attack when Protection blocks it — then pushes the ordinary
    ``granted_attack`` with ``power_bonus=3``.  "ANOTHER unit" needs no exclusion
    parameter: the unit just exhausted is no longer a legal attacker, so it falls
    out of the offered set on its own."""
    return EventAbility(effects=[CustomEffect(
        fn=_accelerate_our_plans_sec_228,
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("ready",)),
    )])


# ── Group sec-set:18 — Combat tricks, buffs & tempo ───────────────────────────
#
# SEC_231 Implicate is NOT registered here — see the ESCALATION note at the end of
# this group.

def _catch_unawares_sec_229(state, source_ci, target_id, event_ctx):
    """Catch Unawares SEC_229: a granted attack whose unit defender gets -4/-0."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, defender_power_bonus=-4)
    return state


@card_ability("SEC", "229")
def _catch_unawares():
    """SEC_229 — Catch Unawares (Event, Tactic): "Attack with a unit.  The defender
    gets −4/−0 for this attack."

    The plain ``granted_attack`` seam with its existing ``defender_power_bonus``
    (Jyn Erso SOR_18): the debuff is applied as a ``this_attack`` stats modifier on
    the chosen defender before the combat pipeline reads its power, and only for a
    UNIT defender (a base attack simply skips it)."""
    return EventAbility(effects=[CustomEffect(fn=_catch_unawares_sec_229)])


def _the_wrong_ride_sec_235(state, source_ci, target_id, event_ctx):
    """The Wrong Ride SEC_235: exhaust 2 ready enemy resources."""
    opp = state.players[1 - state.player_index(source_ci.owner_id)]
    remaining = 2
    for r in opp.resources:
        if remaining <= 0:
            break
        if not r.exhausted:
            r.exhausted = True
            remaining -= 1
    return state


@card_ability("SEC", "235")
def _the_wrong_ride():
    """SEC_235 — The Wrong Ride (Event, Disaster; Plot): "Exhaust 2 enemy
    resources."

    Plot is the keyword layer (the event can also be played from resources).  The
    functional line is a thin ``CustomEffect``: resources are interchangeable
    face-down cards, so WHICH two is never a choice (the Elia Kane SEC_242
    convention), and with fewer than two ready it exhausts what it can."""
    return EventAbility(effects=[CustomEffect(fn=_the_wrong_ride_sec_235)])


def _undercover_operation_sec_236(state, source_ci, target_id, event_ctx):
    """Undercover Operation SEC_236: ready the chosen just-played unit and, if it
    costs 3 or less, create a Spy token."""
    from swu.engine.actions import _create_token_units
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    res[1].exhausted = False
    if int(getattr(res[1].card_def, "cost", None) or 0) <= 3:
        _create_token_units(state, state.player_by_id(source_ci.owner_id), "Spy", 1)
    return state


@card_ability("SEC", "236")
def _undercover_operation():
    """SEC_236 — Undercover Operation (Event, Tactic): "Ready a unit that was played
    this phase.  If it costs 3 or less, create a Spy token."

    One ``CustomEffect.target`` carries both clauses, because the second is a rider
    on the FIRST's chosen unit ("if IT costs 3 or less") — splitting it into a
    ReadyCard plus a CreateTokenUnit would lose that link.  The target filter is the
    existing ``played_this_phase`` predicate (over ``units_played_this_phase``, which
    every play path feeds); ``controller="any"``, the printed "a unit" being
    unqualified.  Printed cost decides the token, matching every other cost gate."""
    return EventAbility(effects=[CustomEffect(
        fn=_undercover_operation_sec_236,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("played_this_phase",)),
    )])


@card_ability("SEC", "243")
def _fn_trooper_corps():
    """SEC_243 — FN Trooper Corps (Unit, First Order/Trooper; Plot): "When Played:
    Give an Experience token to another friendly unit."

    Plot is the keyword layer.  The functional line is the declarative ``GiveToken``
    with ``not_self`` for the printed "ANOTHER" — mandatory, and it fizzles with no
    prompt when the Corps is the controller's only unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="friendly", kind="unit",
                                      predicates=("not_self",)))],
    )


@card_ability("SEC", "249")
def _high_command_councilor():
    """SEC_249 — High Command Councilor (Unit, Official/Rebel, 1/4; Raid): "While
    you control another Official unit, this unit gains Raid 2."

    The conditional-self-grant pattern (Anakin Skywalker SEC_201): a
    ``ConstantAbility(target=SELF, KeywordGrant("Raid", 2))`` gated by the existing
    ``CONTROLLER_N_PLUS_TRAIT_UNITS`` atom with ``("Official", 2)`` — the Councilor
    is itself an Official unit in play, so "another Official unit" is exactly "two
    or more Official units", and the atom reads EFFECTIVE traits so a TraitGrant
    counts.  Registering it makes the sanitiser strip the printed "Raid" bar."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 2)],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_TRAIT_UNITS,
                                 param=("Official", 2)),
    )


def _restore_freedom_sec_257(state, source_ci, target_id, event_ctx):
    """Restore Freedom SEC_257: play a unit from hand, 1 cheaper per Heroism aspect
    ICON among friendly units (duplicates count, the SEC_247 icon basis)."""
    from swu.engine.actions import push_play_from_hand
    ctrl = state.player_by_id(source_ci.owner_id)
    icons = sum(
        1
        for arena in (ctrl.ground_arena, ctrl.space_arena)
        for u in arena
        for a in (getattr(u.card_def, "aspects", None) or ())
        if a.name == "Heroism"
    )
    push_play_from_hand(state, source_ci, cost_reduction=icons)
    return state


@card_ability("SEC", "257")
def _restore_freedom():
    """SEC_257 — Restore Freedom (Event, Gambit): "Play a unit from your hand.  It
    costs 1 resource less for each Heroism aspect icon among friendly units."

    The ``play_from_hand`` seam with a computed ``cost_reduction`` — the discount is
    applied to both the affordability check and the payment, and floors at 0.  The
    magnitude counts Heroism PIPS on the controller's arena units (duplicates
    included, so a double-Heroism unit contributes 2) — the same icon basis as Evil
    is Everywhere SEC_247's ``cost_max_count``.  It is measured when the effect
    resolves, i.e. before the new unit arrives, so the played unit never discounts
    itself."""
    return EventAbility(effects=[CustomEffect(fn=_restore_freedom_sec_257)])


# -- Group sec-set:19 -- Combat tricks, buffs & tempo -------------------------

def _inspectors_shuttle_name(state, source_ci, target_id, event_ctx):
    """Adapter: name a card, then count the copies in the opponent's hand and give
    that many Experience tokens to this unit (the name_a_card ``then_payoff``)."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci, from_hand=True,
                     then_payoff="experience_per_hand_copy")
    return state


@card_ability("SEC", "260")
def _inspectors_shuttle():
    """SEC_260 - Inspector's Shuttle (Unit, Republic/Transport/Vehicle): "When
    Played: Name a card, then an opponent reveals their hand.  For each copy of the
    named card in their hand, give an Experience token to this unit."

    The ``name_a_card`` decision with the new ``experience_per_hand_copy`` payoff,
    which counts the named card in the opponent's hand AFTER the naming (the printed
    order) and attaches that many Experience tokens to the source.  DOCUMENTED
    DEVIATION: the nameable set is the opponent's HAND (``from_hand=True``) rather
    than a blind naming - the Chimaera SOR_185 optimal-play collapse, since a name
    absent from the hand can only score zero."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_inspectors_shuttle_name)],
    )


@card_ability("SEC", "261")
def _inspiring_senator():
    """SEC_261 - Inspiring Senator (Unit, Official/Republic): "When Defeated: The
    next Official unit you play this phase costs 1 resource less."

    A plain ``WhenDefeated`` recording one pending ``NextPlayDiscount`` entry for the
    controller (Khetanna LAW_158): the play-cost path consults it and the play site
    consumes it, so exactly one subsequent Official UNIT play is discounted and the
    entry lifts at the phase rollover."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[NextPlayDiscount(trait="Official", amount=1)],
    )


# -- Group sec-set:20 -- Miscellaneous abilities ------------------------------

@card_ability("SEC", "12")
def _cassian_andor_sec():
    """SEC_12 - Cassian Andor (Leader, Rebel).

    Undeployed: "Friendly units that have damaged an opponent's base this phase
    can't be attacked (unless they have Sentinel)" - the new
    ``CannotBeAttackedAfterDamagingBase`` marker, read at the single
    attack-enumeration seam ``actions._cannot_be_attacked`` over the long-standing
    ``game_memory.units_dealt_base_damage_this_round`` ledger (Retaliation SEC_77).
    The scan walks only the controller's base_zone, so the aura is undeployed-only
    for free - once he deploys, his printed deployed side no longer carries it.

    Deployed: "While you have the initiative, this unit isn't defeated by having no
    remaining HP and can't be defeated by enemy card abilities" (+ printed
    Overwhelm, keyword layer) - one self-targeted ``Protection`` ConstantAbility
    gated on ``CONTROLLER_HAS_INITIATIVE``, carrying both ``from_defeat`` (the
    enemy-ability guard, Chewbacca JTL_103) and ``from_hp_defeat`` (the state-based
    guard, Chirrut Imwe SOR_4).  ``hp_defeat_any_phase`` opts out of Chirrut's
    printed action-phase limit, which Cassian's clause does not have.  Being a
    ConstantAbility it is read only by scans over cards in play, so it is inert
    while he sits undeployed in the base zone.

    DOCUMENTED DEVIATION: the ledger records combat damage dealt by ATTACKING a
    base (its single feed site); ability damage to a base has no dealer id at the
    sink, so a unit that pinged a base with an ability is not covered."""
    return [
        CannotBeAttackedAfterDamagingBase(),
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[Protection(from_defeat=True, from_hp_defeat=True,
                                hp_defeat_any_phase=True)],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
        ),
    ]


def _condemn_on_attack(state, source_ci, target_id, event_ctx):
    """Condemn SEC_38: while the attached unit attacks it loses all other abilities
    (a this_attack ``abilities_suppressed`` modifier - the modifier-backed arm of the
    unified suppression read, One Way Out SEC_157) and the DEFENDING player may
    disclose Vigilance+Villainy to give it -6/-0 for this attack."""
    from swu.engine.actions import push_disclose
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=source_ci.instance_id,
        kind="abilities_suppressed",
        value={},
        duration="this_attack",
    ))
    defending_id = next((p.player_id for p in state.players
                         if p.player_id != source_ci.owner_id), None)
    if defending_id is not None:
        push_disclose(
            state, source_ci, ["Vigilance", "Villainy"],
            payoff="buff_unit",
            payoff_args={"target_id": source_ci.instance_id,
                         "power": -6, "hp": 0, "duration": "this_attack"},
            discloser_id=defending_id,
        )
    return state


@card_ability("SEC", "38")
def _condemn():
    """SEC_38 - Condemn (Upgrade, Condition): "While attached unit is attacking, it
    gains: 'On Attack: The defending player may disclose [Vigilance][Villainy].  If
    they do, this unit gets -6/-0 for this attack' and loses all other abilities."

    A ``GrantedAbility`` wrapping an On Attack trigger, so it matches and resolves
    with the HOST as source.  Its one CustomEffect does both halves: the suppression
    is a ``this_attack`` ``abilities_suppressed`` modifier on the host (so it lifts
    with the ordinary duration sweep and cannot leak into the next attack), and the
    disclose is pushed with ``discloser_id`` = the defending player - the decider
    shift ``push_disclose`` already supports.  The -6/-0 rides the existing
    ``buff_unit`` payoff at ``duration="this_attack"`` (Ebon Hawk SEC_219).

    DOCUMENTED DEVIATION: the host's OWN On Attack abilities were collected in the
    same window and so still resolve for this attack; everything read AFTER this
    effect (keywords, constants, later triggers) is suppressed as printed."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_condemn_on_attack)],
    ))


@card_ability("SEC", "45")
def _senator_chuchi():
    """SEC_45 - Senator Chuchi (Unit, Official/Republic, Restore 1 - keyword layer):
    "On Attack: Give another friendly Official unit Restore 2 for this phase."

    A plain On Attack ``GrantKeyword`` with the numeric value, narrowed to a friendly
    Official unit other than herself.  Mandatory-if-able, so with no other Official
    unit it fizzles with no prompt.  Her printed Restore 1 survives the sanitiser:
    it is a leading keyword-bar line, which is exactly what rule 9 tests for."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword(
            "Restore", value=2,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Official",), predicates=("not_self",)),
            duration=Duration.THIS_PHASE)],
    )


@card_ability("SEC", "48")
def _captain_rex_sec():
    """SEC_48 - Captain Rex (Unit, Clone/Republic/Trooper): "When Played/When this
    unit completes an attack: Give this unit and an enemy unit Sentinel for this
    phase."

    The same two effects registered under BOTH triggers (``WhenPlayed`` and
    ``WhenAttackEnds``, which only fires for a unit that survived its attack - the
    printed "completes an attack" reading).  The TARGETED enemy grant is ordered
    FIRST and the fixed-SELF grant second, so the resolver prompts exactly once (the
    Mandalorian SHD_18 convention).  The self-targeted ``GrantKeyword`` is also what
    strips his mistagged printed Sentinel (sanitiser rule 3) - his bar is empty, the
    keyword name appears only inside this ability."""
    effects = [
        GrantKeyword("Sentinel", 0,
                     target=TargetSpec(controller="enemy", kind="unit"),
                     duration=Duration.THIS_PHASE),
        GrantKeyword("Sentinel", 0, target=TargetSpec(kind="unit", fixed=SELF),
                     duration=Duration.THIS_PHASE),
    ]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects)),
        TriggerAbility(trigger=WhenAttackEnds(), effects=list(effects)),
    ]


def _diplomatic_immunity_defend(state, source_ci, target_id, event_ctx):
    """Diplomatic Immunity SEC_52: the attacked unit's controller may disclose
    [Vigilance][Vigilance][Heroism][Heroism] to give the ATTACKER -2/-0 for this
    attack.  The attacker comes off the WhenAttacked event_ctx."""
    from swu.engine.actions import push_disclose
    attacker_id = (event_ctx or {}).get("attacker_id")
    if attacker_id is None or state.find_instance(attacker_id) is None:
        return state
    push_disclose(
        state, source_ci,
        ["Vigilance", "Vigilance", "Heroism", "Heroism"],
        payoff="buff_unit",
        payoff_args={"target_id": attacker_id, "power": -2, "hp": 0,
                     "duration": "this_attack"},
    )
    return state


@card_ability("SEC", "52")
def _diplomatic_immunity():
    """SEC_52 - Diplomatic Immunity (Upgrade, Law): "Attached unit gains: 'When this
    unit is attacked: You may disclose [Vigilance][Vigilance][Heroism][Heroism].  If
    you do, the attacker gets -2/-0 for this attack.'"

    A ``GrantedAbility`` wrapping a ``WhenAttacked`` trigger (so it resolves from the
    HOST) whose CustomEffect is a thin adapter onto ``push_disclose`` with the
    existing ``buff_unit`` payoff at ``duration="this_attack"``.  The trigger is
    mandatory: the printed "you may" IS the disclose decision's own Decline, and
    ``push_disclose`` pushes nothing when the hand cannot cover the icons, so an
    unsatisfiable board never prompts."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CustomEffect(fn=_diplomatic_immunity_defend)],
    ))


@card_ability("SEC", "56")
def _escape_pod():
    """SEC_56 - Escape Pod (Unit, Transport/Vehicle): "When Played: You may have this
    unit capture a friendly non-Vehicle, non-leader unit."

    An optional ``WhenPlayed`` with one ``CaptureUnit`` (the capture primitive, whose
    captor defaults to the ability's source unit).  Capturing a FRIENDLY unit works
    unchanged - ``_apply_capture`` removes the prey from whichever arena holds it -
    and it returns to its owner's arena when the Pod leaves play, which is the
    card's whole point.  ``non_vehicle`` also excludes the Pod itself."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CaptureUnit(TargetSpec(
            controller="friendly", kind="unit",
            predicates=("non_vehicle", "non_leader")))],
    )


# -- Group sec-set:21 -- Miscellaneous abilities ------------------------------

@card_ability("SEC", "61")
def _willrow_hood():
    """SEC_61 - Willrow Hood (Unit, Fringe): "While this unit has exactly 1 friendly
    upgrade on it, that upgrade can't be defeated or returned to hand by enemy card
    abilities."

    An AURA ``Protection`` (Mythosaur LOF_73): a NON-SELF ``ConstantAbility`` whose
    target selects the protected card, read as the third source in
    ``resolver._target_protected``.  The target is an upgrade, narrowed by the new
    ``sole_friendly_upgrade_on_source`` predicate - which is evaluated against the
    SOURCE, so "exactly 1" and "on it" are one test.  Shield/Experience tokens are
    upgrades and so break the "exactly 1" count, but are never the protected
    candidate (the engine-wide ``kind="upgrade"`` convention excludes them)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="upgrade",
                          predicates=("sole_friendly_upgrade_on_source",)),
        effects=[Protection(from_defeat=True, from_return=True)],
    )


@card_ability("SEC", "67")
def _umbaran_mobile_cannon():
    """SEC_67 - Umbaran Mobile Cannon (Unit, Fringe/Vehicle/Walker): "The first time
    this unit would take damage each phase, prevent that damage."

    The ``DamagePrevention`` marker family with the new ``first_each_phase`` flag:
    a WHOLE-instance, once-per-phase prevention consumed at the single unit-damage
    chokepoint ``actions._deal_damage_with_shield`` (through which both combat and
    ability damage flow), ahead of the Shield check - so the first instance is
    dropped entirely and the Cannon's Shield, if any, survives to eat the second."""
    return DamagePrevention(on_self=True, first_each_phase=True)


@card_ability("SEC", "97")
def _beloved_orator():
    """SEC_97 - Beloved Orator (Unit, New Republic/Official): "When Played: Create a
    Spy token."  A plain ``WhenPlayed`` with one ``CreateTokenUnit``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Spy", count=1)],
    )


def _trade_route_taxation(state, source_ci, target_id, event_ctx):
    """Trade Route Taxation SEC_126: if the controller has more units than the chosen
    opponent, lock that opponent out of playing events for this phase."""
    ctrl_id = source_ci.owner_id
    opp = next((p for p in state.players if p.player_id != ctrl_id), None)
    if opp is None:
        return state
    ctrl = state.player_by_id(ctrl_id)
    mine = len(ctrl.ground_arena) + len(ctrl.space_arena)
    theirs = len(opp.ground_arena) + len(opp.space_arena)
    if mine > theirs:
        state.game_memory.cannot_play_events_this_phase.add(opp.player_id)
    return state


@card_ability("SEC", "126")
def _trade_route_taxation_event():
    """SEC_126 - Trade Route Taxation (Event, Law; Plot): "Choose an opponent.  If you
    control more units than that opponent, they can't play events for this phase."

    One no-target ``CustomEffect``: in two-player "choose an opponent" collapses to
    the single opponent, and the lock is the new phase-cleared ledger
    ``game_memory.cannot_play_events_this_phase``, read at the two hand-play seams
    (``_events_locked``) the ``CannotPlayFromHand`` marker already uses."""
    return EventAbility(effects=[CustomEffect(fn=_trade_route_taxation)])


def _lets_talk_captures(state, source_ci, target_id, event_ctx):
    """Let's Talk SEC_131: every friendly unit captures an enemy non-leader unit in
    its arena - the Finalizer SHD_92 pairing walk with no opt-out."""
    from swu.engine.actions import push_multi_capture
    push_multi_capture(state, source_ci, mandatory=True)
    return state


@card_ability("SEC", "131")
def _lets_talk():
    """SEC_131 - Let's Talk (Event, Trick): "If a friendly unit left play this phase,
    this event costs 3 resources less to play.  Each friendly unit captures an enemy
    non-leader unit in the same arena."

    A ``CostReduction`` gated on ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` (read by the
    play-cost path, so it moves both affordability and the resources exhausted) plus
    one no-target ``CustomEffect`` onto ``push_multi_capture(mandatory=True)`` - the
    same pair-selection walk as Finalizer SHD_92, with the "any number" stop withheld
    while a legal pair remains, which is exactly "EACH friendly unit captures".

    DOCUMENTED SIMPLIFICATION: "left play" is read as the defeat ledger
    ``defeated_controllers_this_round`` (the TWI_4 convention) - a friendly unit
    bounced or captured this phase does not discount the event."""
    return [
        CostReduction(
            amount=3,
            condition=ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE)),
        EventAbility(effects=[CustomEffect(fn=_lets_talk_captures)]),
    ]


@card_ability("SEC", "132")
def _imperial_occupier():
    """SEC_132 - Imperial Occupier (Unit, Imperial/Trooper): "When Defeated: Create a
    Spy token."  A plain ``WhenDefeated`` with one ``CreateTokenUnit``."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CreateTokenUnit("Spy", count=1)],
    )


def _the_galleon_disclose(state, source_ci, target_id, event_ctx):
    """The Galleon SEC_141: disclose [Aggression][Aggression][Villainy] to create 3
    Spy tokens (the existing ``create_token`` disclose payoff)."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression", "Aggression", "Villainy"],
        payoff="create_token",
        payoff_args={"token_name": "Spy", "count": 3},
    )
    return state


@card_ability("SEC", "141")
def _the_galleon():
    """SEC_141 - The Galleon (Unit, Transport/Underworld/Vehicle): "When Played: You
    may disclose [Aggression][Aggression][Villainy].  If you do, create 3 Spy
    tokens."

    A mandatory ``WhenPlayed`` whose one CustomEffect is a thin adapter onto
    ``push_disclose`` with the ``create_token`` payoff: the printed "you may" IS the
    disclose decision's own Decline, and nothing is pushed when the hand cannot
    cover the icons."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_the_galleon_disclose)],
    )


# -- Group sec-set:22 -- Miscellaneous abilities ------------------------------

def _confidence_in_victory_choose(state, source_ci, target_id, event_ctx):
    """Confidence in Victory SEC_145: "Choose an arena" - the one-of-two
    ``choose_two_modal`` SELECTOR over the arena options at indices 1 (ground) and
    2 (space) (the Lightmaker SEC_207 shape)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _schedule_sole_arena_win(state, source_ci, arena):
    state.game_memory.win_at_regroup_sole_arena.append(
        {"player_id": source_ci.owner_id, "arena": arena})
    return state


def _confidence_ground(state, source_ci, target_id, event_ctx):
    return _schedule_sole_arena_win(state, source_ci, "ground")


def _confidence_space(state, source_ci, target_id, event_ctx):
    return _schedule_sole_arena_win(state, source_ci, "space")


@card_ability("SEC", "145")
def _confidence_in_victory():
    """SEC_145 - Confidence in Victory (Event, Gambit): "Play only as your first
    action in the action phase.  Choose an arena.  At the start of the regroup phase,
    if you are the only player who controls units in that arena, you win the game."

    Three specs plus a marker.  The ``PlayOnlyAsFirstAction`` marker is read at the
    two hand-play seams over the new per-player turn-action counter, which also
    delivers the card's printed "can't be played as the result of another action"
    note for free (an ability that plays a card never routes through ``PlayCard``).
    Index 0 is the EventAbility controller pushing the arena SELECTOR; indices 1/2
    are the two arena options, registered as ``TriggerAbility`` because this is an
    EVENT card - ``_resolve_event_ability`` walks every EventAbility spec, so an
    option must NOT be one (the SOR aspect-event convention; the Lightmaker SEC_207
    UNIT card needs the mirror image).  Each records a one-shot entry in
    ``game_memory.win_at_regroup_sole_arena`` that ``_enter_regroup`` checks - the
    mirror of Final Showdown SHD_208's ``lose_at_regroup``, delivered by marking
    every other player's base defeated."""
    return [
        EventAbility(effects=[CustomEffect(fn=_confidence_in_victory_choose)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_confidence_ground)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_confidence_space)]),
        PlayOnlyAsFirstAction(),
    ]


def _luthens_haulcraft_disclose(state, source_ci, target_id, event_ctx):
    """Luthen's Haulcraft SEC_153: disclose [Aggression][Aggression][Heroism] to make
    the chosen opponent discard 2 cards."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression", "Aggression", "Heroism"],
        payoff="opponent_discard", payoff_args={"count": 2},
    )
    return state


@card_ability("SEC", "153")
def _luthens_haulcraft():
    """SEC_153 - Luthen's Haulcraft (Unit, Rebel/Transport/Vehicle): "When Defeated:
    You may choose an opponent and disclose [Aggression][Aggression][Heroism].  If
    you do, that opponent discards 2 cards from their hand."

    A ``WhenDefeated`` CustomEffect onto ``push_disclose`` with the new
    ``opponent_discard`` payoff (the first-card discard convention, K-2SO SOR_145).
    In two-player "choose an opponent" collapses to the single opponent.  The
    printed "you may" IS the disclose's own Decline, and nothing is pushed when the
    hand cannot cover the icons."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_luthens_haulcraft_disclose)],
    )


def _chairman_papanoida_disclose(state, source_ci, target_id, event_ctx):
    """Chairman Papanoida SEC_159: disclose [Aggression][Aggression] to create a Spy
    token."""
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression", "Aggression"],
        payoff="create_token", payoff_args={"token_name": "Spy", "count": 1},
    )
    return state


@card_ability("SEC", "159")
def _chairman_papanoida():
    """SEC_159 - Chairman Papanoida (Unit, Official/Republic): "When a player draws 1
    or more cards during the action phase: You may disclose
    [Aggression][Aggression].  If you do, create a Spy token."

    The ``WhenYouDraw`` settle-drain observer with the new ``any_player`` flag (the
    any-seat sibling of its controller / opponent readings), so it fires whoever
    drew.  "During the action phase" is intrinsic: the draw ledger only records
    ACTION-phase draws.  The payoff is the ordinary ``create_token`` disclose."""
    return TriggerAbility(
        trigger=WhenYouDraw(any_player=True),
        effects=[CustomEffect(fn=_chairman_papanoida_disclose)],
    )


@card_ability("SEC", "175")
def _ambitions_reward():
    """SEC_175 - Ambition's Reward (Upgrade, Law): "When Played: Create a Spy token."
    A plain ``WhenPlayed`` with one ``CreateTokenUnit`` (an upgrade's own WhenPlayed
    is collected at the UpgradePlayed seam)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Spy", count=1)],
    )


def _pursue_the_lead_discard(state, source_ci, player_id):
    """Discard the first card of ``player_id``'s hand; if its PRINTED cost is 3 or
    less, the caster creates a Spy token."""
    from swu.engine.actions import (
        _create_token_units, note_hand_or_deck_discard, record_hand_discard,
    )
    from swu.engine.state import Zone
    ps = state.player_by_id(player_id)
    if not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    record_hand_discard(state, player_id, kind="discard")
    if (getattr(card.card_def, "cost", None) or 0) <= 3:
        _create_token_units(state, state.player_by_id(source_ci.owner_id), "Spy", 1)
    return state


def _pursue_the_lead_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _pursue_the_lead_self(state, source_ci, target_id, event_ctx):
    return _pursue_the_lead_discard(state, source_ci, source_ci.owner_id)


def _pursue_the_lead_opponent(state, source_ci, target_id, event_ctx):
    opp = next((p for p in state.players if p.player_id != source_ci.owner_id), None)
    if opp is None:
        return state
    return _pursue_the_lead_discard(state, source_ci, opp.player_id)


@card_ability("SEC", "178")
def _pursue_the_lead():
    """SEC_178 - Pursue the Lead (Event, Plan): "Choose a player.  That player
    discards a card from their hand.  If it costs 3 or less, create a Spy token."

    "Choose a player" is the ``choose_two_modal`` SELECTOR with ``pick=1`` (the
    Lightmaker SEC_207 shape): index 0 pushes it, indices 1/2 are the two players,
    registered as ``TriggerAbility`` so ``_resolve_event_ability`` does not run them
    both (the SOR aspect-event convention for an EVENT card).
    The choice is a REAL one - discarding your own cheap card guarantees the token,
    hitting the opponent costs them a card - so it does not collapse to an optimal
    default.  The discard is the first-card convention (K-2SO SOR_145) and the cost
    test reads the PRINTED cost, as the card's rules note requires."""
    return [
        EventAbility(effects=[CustomEffect(fn=_pursue_the_lead_choose)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_pursue_the_lead_self)]),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_pursue_the_lead_opponent)]),
    ]


def _unauthorized_investigation_disclose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_disclose
    push_disclose(
        state, source_ci, ["Aggression"],
        payoff="create_token", payoff_args={"token_name": "Spy", "count": 1},
    )
    return state


@card_ability("SEC", "181")
def _unauthorized_investigation():
    """SEC_181 - Unauthorized Investigation (Event, Plan): "Create a Spy token.  You
    may disclose [Aggression].  If you do, create another Spy token."

    Two non-targeted effects in printed order: the unconditional ``CreateTokenUnit``
    first, then a CustomEffect onto ``push_disclose`` with the ``create_token``
    payoff.  Neither takes a target, so the resolver never prompts twice."""
    return EventAbility(effects=[
        CreateTokenUnit("Spy", count=1),
        CustomEffect(fn=_unauthorized_investigation_disclose),
    ])


def _screeching_tie_suppress(state, source_ci, target_id, event_ctx):
    """Screeching TIE Fighter SEC_185: the chosen ground unit loses its keywords -
    and can't gain any - for this phase (the keywords_suppressed modifier)."""
    from swu.engine.state import Modifier
    if target_id is None or state.find_instance(target_id) is None:
        return state
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="keywords_suppressed",
        value={},
        duration="this_phase",
    ))
    return state


@card_ability("SEC", "185")
def _screeching_tie_fighter():
    """SEC_185 - Screeching TIE Fighter (Unit, Fighter/Imperial/Vehicle): "On Attack:
    You may choose a ground unit.  If you do, it loses its keywords (and can't gain
    keywords) for this phase."

    An optional On Attack whose one targeted CustomEffect lands the new
    ``keywords_suppressed`` Modifier - the KEYWORD-only mirror of Mind Trick
    LOF_202's ability blackout, read at both keyword-layer entry points
    (``has_keyword`` / ``keyword_value``) so "can't gain keywords" needs no separate
    guard, and expiring with the ordinary this-phase duration sweep.  The unit keeps
    its non-keyword abilities, which is exactly what the card says."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_screeching_tie_suppress,
            target=TargetSpec(controller="any", kind="unit", arena="ground"))],
    )


# -- Group sec-set:23 -- Miscellaneous abilities ------------------------------

@card_ability("SEC", "191")
def _trade_federation_delegates():
    """SEC_191 - Trade Federation Delegates (Unit, Official/Republic): "When Played:
    Create 2 Spy tokens."  A plain ``WhenPlayed`` with one ``CreateTokenUnit``."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateTokenUnit("Spy", count=2)],
    )


def _grand_moff_tarkin_steal(state, source_ci, target_id, event_ctx):
    """Grand Moff Tarkin SEC_192: take control of the chosen enemy Vehicle and LINK
    it to him, so his leaving play hands it back (the Traitorous SOR_122 pair)."""
    from swu.engine.actions import change_control
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, victim = res
    change_control(state, victim, source_ci.owner_id)
    victim.control_linked_to = source_ci.instance_id
    return state


@card_ability("SEC", "192")
def _grand_moff_tarkin_sec():
    """SEC_192 - Grand Moff Tarkin (Unit, Imperial/Official): "When Played: Take
    control of an enemy non-leader Vehicle unit.  When this unit leaves play, that
    unit's owner takes control of that unit."

    Pure composition of the Traitorous SOR_122 control-LINKING pair: ``change_control``
    relocates the victim into Tarkin's controller's arena (control is implicit arena
    occupancy) and ``control_linked_to`` records the tie, which the existing Maul
    LAW_54 leave-play seam (``_revert_linked_control``) honours - so the second
    sentence needs no ability of its own, however Tarkin leaves play."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_grand_moff_tarkin_steal,
            target=TargetSpec(controller="enemy", kind="unit",
                              traits=("Vehicle",), predicates=("non_leader",)))],
    )


def _fully_armed_and_operational(state, source_ci, target_id, event_ctx):
    """Fully Armed and Operational SEC_194: only if an opponent attacked your base
    this phase - play a unit from hand, granting it Ambush for this phase."""
    from swu.engine.actions import push_play_from_hand
    attackers = state.game_memory.base_attackers_this_round.get(
        source_ci.owner_id, [])
    if not attackers:
        return state
    push_play_from_hand(state, source_ci, grant_keyword="Ambush")
    return state


@card_ability("SEC", "194")
def _fully_armed_and_operational_event():
    """SEC_194 - Fully Armed and Operational (Event, Trick; Ambush, Plot): "If an
    opponent attacked your base during their previous action this phase, play a unit
    from your hand.  Give it Ambush for this phase."

    One no-target ``CustomEffect``: the BOARD GATE is read inside the fn (an
    EventAbility has no ``condition`` field), so a failing gate simply pushes nothing
    and the event fizzles with no prompt.  The payoff is ``push_play_from_hand`` with
    the existing ``grant_keyword`` rider, whose granted Ambush is applied before the
    enter-play keyword bus and so triggers on entry.

    DOCUMENTED SIMPLIFICATION: the gate is "attacked your base THIS PHASE" (the
    ``game_memory.base_attackers_this_round`` ledger, recorded at the base-attack
    declare step), not the narrower "during their PREVIOUS action"."""
    return EventAbility(effects=[CustomEffect(fn=_fully_armed_and_operational)])


def _arrest_capture(state, source_ci, target_id, event_ctx):
    """Arrest SEC_195: the caster's BASE captures the chosen enemy non-leader unit,
    and the captive is scheduled for its owner's rescue at the next regroup start."""
    from swu.engine.actions import _apply_capture
    if target_id is None:
        return state
    base = state.player_by_id(source_ci.owner_id).base_instance
    if base is None:
        return state
    state = _apply_capture(state, base.instance_id, target_id)
    res = state.find_instance(target_id)
    if res is not None and res[1].captured_by == base.instance_id:
        state.game_memory.rescue_at_regroup.append(target_id)
    return state


@card_ability("SEC", "195")
def _arrest():
    """SEC_195 - Arrest (Event, Law): "Your base captures an enemy non-leader unit.
    At the start of the regroup phase, its owner rescues it."

    ``_apply_capture`` already works with ANY in-play card as the captor - it looks
    the captor up with ``find_instance`` (which reaches the base zone) and files the
    captive in that player's capture pile - so "your base captures" needs no new
    machinery, and the base guards the captive exactly as the card's rules note says.
    The delayed release rides the new one-shot ``game_memory.rescue_at_regroup``
    schedule, swept in ``_enter_regroup`` through the shared CR rescue seam
    ``_rescue_captured_card`` (owner's hand)."""
    return EventAbility(effects=[CustomEffect(
        fn=_arrest_capture,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader",)))])


@card_ability("SEC", "203")
def _tala_durith():
    """SEC_203 - Tala Durith (Unit, Imperial/Rebel; Plot): "Each other friendly unit
    gains Hidden."

    A plain aura ``ConstantAbility`` with a ``KeywordGrant``, read passively by the
    keyword layer.  Her printed bar carries only Plot: the API also tags her with
    Hidden, scraped out of "gains Hidden", and sanitiser rule 1 strips it (the
    keyword never appears as a leading keyword-bar line), which is why the grant is
    "each OTHER friendly unit" and she is not Hidden herself."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("not_self",)),
        effects=[KeywordGrant("Hidden")],
    )


@card_ability("SEC", "206")
def _emissaries_from_ryloth():
    """SEC_206 - Emissaries from Ryloth (Unit, Official/Republic/Twi'lek): "When
    Played: You may give a unit -3/-0 for this phase."

    An optional ``WhenPlayed`` with one targeted ``ModifyStats`` over any unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ModifyStats(power=-3, hp=0,
                             target=TargetSpec(controller="any", kind="unit"),
                             duration=Duration.THIS_PHASE)],
    )


def _stolen_starpath_name(state, source_ci, target_id, event_ctx):
    """Stolen Starpath Unit SEC_210: name a card, then create one Spy token per copy
    of it in the defending player's hand (the name_a_card ``then_payoff``)."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci, from_hand=True,
                     then_payoff="token_per_hand_copy:Spy")
    return state


@card_ability("SEC", "210")
def _stolen_starpath_unit():
    """SEC_210 - Stolen Starpath Unit (Upgrade, Item/Modification): "Attached unit
    gains: 'On Attack: Name a card.  The defending player reveals their hand.  For
    each card in their hand with that name, create a Spy token.'"

    A ``GrantedAbility`` wrapping an On Attack trigger (so it resolves with the HOST
    as source, and the host's controller both names and gets the tokens) onto the
    ``name_a_card`` decision with the ``token_per_hand_copy`` payoff - the Spy-token
    sibling of Inspector's Shuttle SEC_260's Experience payoff.  In two-player the
    defending player IS the source's opponent.  DOCUMENTED DEVIATION: the nameable
    set is that opponent's HAND (``from_hand=True``), the Chimaera SOR_185
    optimal-play collapse of a blind naming."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_stolen_starpath_name)],
    ))


# -- Group sec-set:24 -- Miscellaneous abilities ------------------------------

def _duchesss_investigators_disclose(state, source_ci, target_id, event_ctx):
    """Duchess's Investigators SEC_223: disclose [Cunning] to make each opponent
    discard a random card."""
    from swu.engine.actions import push_disclose
    push_disclose(state, source_ci, ["Cunning"], payoff="opponents_discard_random")
    return state


@card_ability("SEC", "223")
def _duchesss_investigators():
    """SEC_223 - Duchess's Investigators (Unit, Mandalorian): "When Played: You may
    disclose [Cunning].  If you do, each opponent discards a random card from their
    hand."

    A ``WhenPlayed`` CustomEffect onto ``push_disclose`` with the new
    ``opponents_discard_random`` payoff, which draws the card from the SEEDED game
    RNG (``state.make_rng`` + write-back) so a replay reproduces it.  The printed
    "you may" IS the disclose's own Decline."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_duchesss_investigators_disclose)],
    )


@card_ability("SEC", "224")
def _vel_sartha():
    """SEC_224 - Vel Sartha (Unit, Rebel; Raid 2 - keyword layer): "Each exhausted
    enemy unit gets -2/-0 while defending."

    A ``while_target_defending`` aura ``ConstantAbility`` (Jyn Erso SOR_18): the
    StatBonus lands on its target only while that target is the current combat
    defender, and the ``exhausted`` predicate is re-read per candidate, so a unit
    that readies before it is attacked keeps its power.  Her printed Raid 2 is a
    leading keyword-bar line and so survives sanitiser rule 9."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("exhausted",)),
        effects=[StatBonus(power=-2, hp=0)],
        while_target_defending=True,
    )


@card_ability("SEC", "227")
def _special_modifications():
    """SEC_227 - Special Modifications (Upgrade, Modification): "Attach to a Vehicle
    unit.  When Played: If attached unit is a Transport, you may create a Spy
    token."

    The attachment restriction is parsed off the printed text by
    ``_upgrade_target_spec``.  The trigger is an optional ``WhenPlayed`` gated by the
    new ``ATTACHED_HOST_HAS_TRAIT`` condition atom (the trait sibling of
    ``ATTACHED_HOST_NAMED``), so on a non-Transport Vehicle the trigger is never
    collected and there is no no-op prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.ATTACHED_HOST_HAS_TRAIT,
                                 param="Transport"),
        effects=[CreateTokenUnit("Spy", count=1)],
    )


@card_ability("SEC", "253")
def _covert_operative():
    """SEC_253 - Covert Operative (Unit, Rebel): "When Played: This unit captures an
    enemy non-leader unit that costs 2 or less."

    A mandatory ``WhenPlayed`` with one ``CaptureUnit`` (the capture primitive, whose
    captor defaults to the source unit), narrowed by ``cost_max`` - the PRINTED cost,
    as the card's rules note requires.  Mandatory-if-able, so it fizzles cleanly with
    no prompt when no cheap enemy unit is on the board."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CaptureUnit(TargetSpec(
            controller="enemy", kind="unit", cost_max=2,
            predicates=("non_leader",)))],
    )


@card_ability("SEC", "255")
def _remote_escort_tank():
    """SEC_255 - Remote Escort Tank (Unit, Republic/Tank/Vehicle; Plot): "When
    Played: Give a unit Sentinel for this phase."

    A plain ``WhenPlayed`` ``GrantKeyword`` over any unit.  The API also tags the
    card with Sentinel, scraped out of this ability text - sanitiser rule 9 strips
    it, because the keyword never appears as a leading keyword-bar line and the card
    now registers a grant of it."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GrantKeyword("Sentinel", 0,
                              target=TargetSpec(controller="any", kind="unit"),
                              duration=Duration.THIS_PHASE)],
    )


# -- Group sec-set:18 -- framework session: the PINNED PHASE AURA ---------------
# Implicate SEC_231 is the first card to grant an ONGOING triggered ability (not a
# When Defeated one) to a SINGLE CHOSEN unit for a phase.  Neither existing grant
# shape fits: ``GrantedAbility`` needs an attached upgrade to carry it, and
# ``AuraGrantedAbility`` was a board-wide scan collected only at the defeat path.
# Two small, additive seams close the gap and are reused by any future
# "chosen unit gains: '<ongoing trigger>'" card:
#   1. ``resolver._collect_triggers`` now scans aura grants whose inner trigger is
#      NOT WhenDefeated over the units in play (plus ``phase_aura_sources``, so a
#      spent event keeps granting from the discard — Pyrrhic Assault TWI_103).
#   2. the ``granted_keyword_by_source`` predicate narrows such an aura to the unit
#      carrying a ``keyword_grant`` modifier from that same source.
# (2) is what turns a board-wide aura into a single-target grant, and it needs no
# new state: the Sentinel half of this very card already stamps exactly one
# modifier onto exactly the chosen unit, and both halves are ``this_phase``, so the
# keyword and the trigger appear and lapse together.


def _implicate_arm_aura(state, source_ci, target_id, event_ctx):
    """Arm the phase-scoped aura: record this event as an aura source for the phase.

    By resolution time the event is on its way to the discard, so the collection
    site can only reach it through ``game_memory.phase_aura_sources`` — cleared at
    the phase rollover, which is the whole of "for this phase".  Ordered SECOND,
    behind the targeted ``GrantKeyword``: a targeted effect ahead of an untargeted one
    prompts the player exactly once (the C-3PO SEC_93 ordering), and with no unit to
    choose the ability fizzles before this runs — correctly leaving the aura unarmed,
    since it would have nothing to pin to."""
    gm = state.game_memory
    if source_ci.instance_id not in gm.phase_aura_sources:
        gm.phase_aura_sources.append(source_ci.instance_id)
    return state


@card_ability("SEC", "231")
def _implicate():
    """SEC_231 — Implicate (Event, cost 2, Trick).

    "Choose a unit.  For this phase, it gains Sentinel and: 'When this unit is
    attacked: Create a Spy token.'"

    One choice feeds both halves.  Spec 0 is the event body: a ``GrantKeyword``
    whose ChooseTarget IS the printed "choose a unit" (any controller — giving an
    enemy unit Sentinel to drag it into a fight is a real line), then arm the phase
    aura.  Spec 1 is the ongoing half, an ``AuraGrantedAbility`` pinned by
    ``granted_keyword_by_source`` to whichever unit spec 0's modifier landed on.

    The Spy token is created from the ATTACKED unit as source, so it goes to that
    unit's controller — correct for either choice, since the granted ability is the
    unit's own."""
    return [
        EventAbility(effects=[
            GrantKeyword("Sentinel", 0,
                         target=TargetSpec(controller="any", kind="unit"),
                         duration=Duration.THIS_PHASE),
            CustomEffect(fn=_implicate_arm_aura),
        ]),
        AuraGrantedAbility(
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("granted_keyword_by_source",)),
            ability=TriggerAbility(
                trigger=WhenAttacked(),
                effects=[CreateTokenUnit("Spy", count=1)],
            ),
        ),
    ]
