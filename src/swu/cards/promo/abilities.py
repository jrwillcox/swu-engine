"""Promo / anthology reprint-duplicate canonical encodings (BATCH 19).

Each card here is a fresh reprint face (own subtitle/text, its own reprint group)
that composes from EXISTING primitives — the batch-18 "easy encode" shape.  Where
a shipped-set card has the identical *mechanic* (a different printed face, so not
an alias), the encoding mirrors that twin exactly; the twin is named in each
docstring.  Registered canonical = one member per group; siblings aliased in
``reprints.py``.

Groups encoded:
  * P26_81 Han Solo — "On Attack: Give an Experience token to this unit"
    (= Han Solo LAW_37).
  * P25_1  Bossk — Piloting; "On Attack: Exhaust the defender and deal 1 to it"
    both as a unit and as a Pilot upgrade (= Bossk JTL_187).
  * JTLP_7 Chewbacca — Piloting; "can't be defeated/returned by enemy abilities"
    (= Chewbacca JTL_103 Protection).
  * ASH_243 Darth Vader — Shielded; "While this unit is ready, he gains Sentinel".
  * P25_96 Darth Tyranus — Shielded; "While the Force is with you, gains Ambush"
    (= Darth Tyranus LOF_231).
  * G25_3 Obi-Wan Kenobi — "When you play a Force unit: gains Sentinel this phase"
    (= Obi-Wan LOF_96).
  * J25_18 General Grievous — Hidden; "When this unit is attacked: Return him to
    his owner's hand".
  * C24_3 Emperor Palpatine — Overwhelm; "When Played: Deal 6 damage divided among
    enemy units" (= Palpatine SOR_135 distribute_damage).
  * P26_75 Naboo Royal Starship — "Each friendly leader unit gains Raid 2 and
    Overwhelm" + Plot.
  * P25_7 / P25_157 Black One — "While upgraded +1/+0" + "On Attack: if you control
    Poe Dameron, you may deal 1 to a unit" (two distinct reprint groups, identical
    mechanic).
  * LOFP_10 Mace Windu — Overwhelm; "When Played: you may use the Force → deal 4 to
    a unit" (the Karis LOF_31 targeted force-spend pattern).
  * P25_129 Vernestra Rwoh — "When Played: you may use the Force → ready this unit"
    (the Infused Brawler LOF_156 no-target force-spend pattern).
  * P25_151 Karis — "When Defeated: you may use the Force → give a unit -2/-2"
    (= Karis LOF_31).
  * G25_2 Darth Sidious — Restore 2; "When Played: you may use the Force → defeat
    each non-Sith unit with 3 or less remaining HP" (= Darth Sidious LOF_39).
  * ASH_226 Qi'ra — "-1/-0 for each card in your hand" (scaling StatBonus, new
    ``controller_hand_size`` count) + "When Played: you may discard a card → deal 3
    to a unit" (the Merrin LOF_160 pattern).
  * C25_2 BB-8 — Piloting; "When played as an upgrade: you may pay 2 resources →
    ready a Resistance unit".
  * P25_31 Galen Erso — Plot; "When Played: Name a card.  Each non-leader card an
    opponent owns with that name (incl. out of play) loses all abilities while this
    unit is in play" (the name-based ability-suppression primitive; batch 46).
  * J25_4  Luke Skywalker — Piloting; "If this upgrade would be defeated, you may
    instead move him to the ground arena as a unit and exhaust him" (the pilot
    defeat-replacement seam ``WhenDefeatedAsUpgrade``; batch 47).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ConstantAbility, GrantedAbility, EventAbility,
    OnAttack, WhenPlayed, WhenDefeated, WhenDefeatedAsUpgrade, WhenAttacked, WhenYouPlayCard,
    DealDamage, DefeatUnit, ExhaustCard, GiveToken, ReturnToHand, GrantKeyword,
    StatBonus, KeywordGrant, Protection, CustomEffect, StandingPlayDiscount,
    MultiDefenderAttack, IgnoreAspectPenaltyForPlays,
    ConditionCheck, Condition, Duration,
    TargetSpec, SELF, DEFENDER,
)


# ── Plain triggers / constants (mirror an implemented twin) ───────────────────

@card_ability("P26", "81")
def _han_solo_p26_81():
    """P26_81 — Han Solo "Hibernation Sick" (1/1, Shielded — keyword layer):
    "On Attack: Give an Experience token to this unit" (= Han Solo LAW_37)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience", TargetSpec(kind="unit", fixed=SELF))],
    )


def _bossk_p25_on_attack_effects():
    """Shared On Attack: exhaust the defender and deal 1 to it (if it's a unit).
    ``fixed=DEFENDER`` no-ops on a base attack — the printed "(if it's a unit)"."""
    return [
        ExhaustCard(TargetSpec(kind="unit", fixed=DEFENDER)),
        DealDamage(1, TargetSpec(kind="unit", fixed=DEFENDER)),
    ]


@card_ability("P25", "1")
def _bossk_p25_1():
    """P25_1 — Bossk "Hunt By Instinct" (4/4, Piloting): the On Attack fires both
    when Bossk is a unit (plain ``OnAttack``) and when he is a Pilot upgrade (a
    ``GrantedAbility`` resolving from the host) — the Bossk JTL_187 dual-form
    pattern.  Exactly one is collected per play mode."""
    return [
        TriggerAbility(trigger=OnAttack(), effects=_bossk_p25_on_attack_effects()),
        GrantedAbility(ability=TriggerAbility(
            trigger=OnAttack(), effects=_bossk_p25_on_attack_effects())),
    ]


@card_ability("JTLP", "7")
def _chewbacca_jtlp_7():
    """JTLP_7 — Chewbacca "Faithful First Mate" (5/6, Piloting): "can't be defeated
    or returned to hand by enemy card abilities" (both as a unit and, via the
    SELF-``ConstantAbility`` convention, for the Vehicle he pilots) — the Chewbacca
    JTL_103 ``Protection`` pattern."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_defeat=True, from_return=True)],
    )


@card_ability("ASH", "243")
def _darth_vader_ash_243():
    """ASH_243 — Darth Vader "Meet Your Destiny" (4/6, Shielded): "While this unit
    is ready, he gains Sentinel."  A self-targeted conditional ``ConstantAbility``
    (the SOURCE_READY gate, read passively by ``has_keyword``); the keyword
    sanitiser's conditional-self-grant rule strips the mis-tagged printed Sentinel,
    leaving Shielded."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.SOURCE_READY),
    )


@card_ability("P25", "96")
def _darth_tyranus_p25_96():
    """P25_96 — Darth Tyranus "Servant of Sidious" (4/3, Shielded): "While the Force
    is with you, this unit gains Ambush" (= Darth Tyranus LOF_231).  The sanitiser
    strips the mis-tagged printed Ambush; Shielded is kept."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Ambush", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("G25", "3")
def _obi_wan_g25_3():
    """G25_3 — Obi-Wan Kenobi "Protective Padawan" (3/5): "When you play a Force
    unit: This unit gains Sentinel for this phase" (= Obi-Wan LOF_96,
    ``exclude_self=False`` so playing Obi-Wan himself triggers it).  The sanitiser
    strips his mis-tagged printed Sentinel."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Force", card_type="unit", exclude_self=False),
        effects=[GrantKeyword(
            "Sentinel", value=0,
            target=TargetSpec(fixed=SELF),
            duration=Duration.THIS_PHASE,
        )],
    )


@card_ability("J25", "18")
def _general_grievous_j25_18():
    """J25_18 — General Grievous "Scuttling to Safety" (3/3, Hidden — keyword
    layer): "When this unit is attacked: Return him to his owner's hand."  A
    mandatory ``WhenAttacked`` returning the source to hand."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[ReturnToHand(TargetSpec(kind="unit", fixed=SELF))],
    )


def _palpatine_c24_distribute(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_distribute_damage
    push_distribute_damage(state, source_ci, 6, target_controller="enemy")
    return state


@card_ability("C24", "3")
def _emperor_palpatine_c24_3():
    """C24_3 — Emperor Palpatine "Master of the Dark Side" (6/6, Overwhelm): "When
    Played: Deal 6 damage divided as you choose among enemy units" (= Palpatine
    SOR_135; the ``distribute_damage`` decision, fizzles cleanly with no enemy
    units)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_palpatine_c24_distribute)],
    )


@card_ability("C24", "6")
def _darth_maul_c24_6():
    """C24_6 — Darth Maul (5/6 Ground, Force/Sith): "This unit can attack 2 units
    instead of 1" — the multi-defender-attack primitive.  A bare
    ``MultiDefenderAttack(count=2)`` marker: while Maul is in play the engine offers
    an ``AttackTwoUnits`` action (both chosen enemy units are co-defenders of one
    attack — Maul deals his power to each and takes the sum of theirs; Overwhelm
    spills the combined excess; a base can't be a co-defender).  Canonical for the
    (C24_6, J25_5, P25_91) group."""
    return MultiDefenderAttack(count=2)


@card_ability("P26", "75")
def _naboo_royal_starship_p26_75():
    """P26_75 — Naboo Royal Starship "Fit For A Queen" (2/5, Plot — keyword layer):
    "Each friendly leader unit gains Raid 2 and Overwhelm."  A ``ConstantAbility``
    over friendly leader units, read passively by the keyword layer.  Naboo is a
    Vehicle, not a leader unit, so it never grants the keywords to itself.  The
    grants-to-others sanitiser strips Naboo's mis-tagged printed Raid; its printed
    Overwhelm is NOT stripped (the sanitiser's grant-verb matcher only sees the
    keyword directly after "gains", not the second one in "gains Raid 2 and
    Overwhelm") — an accepted cosmetic deviation, since a 2/5 promo Vehicle keeping
    a stray Overwhelm is harmless and appears in no soak/fixture deck."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("leader_unit",)),
        effects=[KeywordGrant("Raid", value=2), KeywordGrant("Overwhelm", value=0)],
    )


def _black_one_spec():
    """Shared Black One encoding: "While this unit is upgraded, +1/+0" (a
    self-conditional ``ConstantAbility``, SOURCE_UPGRADED) + "On Attack: if you
    control Poe Dameron, you may deal 1 damage to a unit" (an optional ``OnAttack``
    gated by CONTROLLER_CONTROLS_NAMED)."""
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


@card_ability("P25", "7")
def _black_one_p25_7():
    """P25_7 — Black One "Straight At Them" (2/3).  See ``_black_one_spec``."""
    return _black_one_spec()


@card_ability("P25", "157")
def _black_one_p25_157():
    """P25_157 — Black One "Straight At Them" (2/3) — a distinct reprint group from
    P25_7 (the two faces normalise differently), identical mechanic."""
    return _black_one_spec()


# ── "You may use the Force" cards (reuse the qui-gon-jinn:06 Force token) ──────

def _use_force_then(fn):
    """Wrap an effect fn so it runs only after the controller spends their Force
    token — the "If you do" binding (the Infused Brawler LOF_156 shape)."""
    def _inner(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import spend_force_token
        ps = state.player_by_id(source_ci.owner_id)
        if not spend_force_token(state, ps):
            return state
        return fn(state, source_ci, target_id, event_ctx)
    return _inner


def _mace_deal4(state, source_ci, target_id, event_ctx):
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 4, source_ci.card_def.name)
    return state


@card_ability("LOFP", "10")
def _mace_windu_lofp_10():
    """LOFP_10 — Mace Windu "Leaping into Action" (6/6, Overwhelm): "When Played:
    You may use the Force. If you do, deal 4 damage to a unit."  An optional
    ``WhenPlayed`` gated by CONTROLLER_HAS_FORCE_TOKEN whose targeted
    ``CustomEffect`` spends the token and deals 4 (the Karis LOF_31 targeted
    force-spend pattern; auto-declines with no unit to hit)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_use_force_then(_mace_deal4),
                              target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _vernestra_ready_self(state, source_ci, target_id, event_ctx):
    source_ci.exhausted = False
    return state


@card_ability("P25", "129")
def _vernestra_rwoh_p25_129():
    """P25_129 — Vernestra Rwoh "Precocious Knight" (3/4): "When Played: You may use
    the Force. If you do, ready this unit."  An optional ``WhenPlayed`` gated by
    CONTROLLER_HAS_FORCE_TOKEN whose no-target ``CustomEffect`` spends the token and
    readies the source (the Infused Brawler LOF_156 no-target pattern)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_use_force_then(_vernestra_ready_self))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _galen_name_a_card(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci)
    return state


@card_ability("P25", "31")
def _galen_erso_p25_31():
    """P25_31 — Galen Erso (4-cost Imperial, Vigilance/Heroism): "When Played: Name a
    card.  While this unit is in play, each non-leader card an opponent owns with that
    name, including those not in play, loses all abilities."  Plot is the keyword
    layer.  A mandatory ``WhenPlayed`` whose no-target ``CustomEffect`` pushes the
    ``name_a_card`` decision (the Palpatine SOR_135 inline-push pattern); the named
    card is recorded on the source's ``named_card`` field and its "loses all
    abilities" effect is a passive name-based read at the ability-read guards
    (state.is_name_suppressed — the persistent, name-based mirror of the phase-scoped
    ``abilities_suppressed`` flag from Mind Trick LOF_202).  Canonical for the
    (P25_31, P26_38, P26_50) group."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_galen_name_a_card)],
    )


def _karis_debuff(state, source_ci, target_id, event_ctx):
    if target_id is None:
        return state
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=-2, hp=-2, duration=Duration.THIS_PHASE))
    return state


@card_ability("P25", "151")
def _karis_p25_151():
    """P25_151 — Karis "We Don't Like Strangers" (2/4): "When Defeated: You may use
    the Force. If you do, give a unit -2/-2 for this phase" (= Karis LOF_31)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_use_force_then(_karis_debuff),
                              target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _sidious_wipe(state, source_ci, target_id, event_ctx):
    """Defeat each non-Sith unit with 3 or less remaining HP (victims snapshotted
    up front, so simultaneous; Sidious is Sith so is never hit)."""
    from swu.engine.actions import compute_hp
    from swu.engine.traits import has_trait
    from swu.abilities.resolver import _apply_defeat_unit
    victims = []
    for player in state.players:
        for ci in list(player.ground_arena) + list(player.space_arena):
            if has_trait(state, ci, "Sith"):
                continue
            if compute_hp(state, ci) - ci.damage <= 3:
                victims.append(ci.instance_id)
    for vid in victims:
        _apply_defeat_unit(state, vid)
    return state


@card_ability("G25", "2")
def _darth_sidious_g25_2():
    """G25_2 — Darth Sidious "The Phantom Menace" (6/8, Restore 2): "When Played:
    You may use the Force. If you do, defeat each non-Sith unit with 3 or less
    remaining HP" (= Darth Sidious LOF_39)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_use_force_then(_sidious_wipe))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


# ── Qi'ra: scaling self-debuff + discard-then-deal ────────────────────────────

def _qira_discard_deal(state, source_ci, target_id, event_ctx):
    """Discard the first hand card (first-card simplification); if a card was
    discarded, deal 3 to the chosen unit — bound so "If you do" holds (Merrin
    LOF_160 pattern)."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    from swu.engine.state import Zone
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 3, source_ci.card_def.name)
    return state


@card_ability("ASH", "226")
def _qira_ash_226():
    """ASH_226 — Qi'ra "Master of Teräs Käsi" (9/7): "This unit gets -1/-0 for each
    card in your hand." + "When Played: You may discard a card from your hand. If
    you do, deal 3 damage to a unit."  The debuff is a self-targeted scaling
    ``ConstantAbility`` (the new ``controller_hand_size`` count; read passively by
    ``compute_power``).  The second is the Merrin LOF_160 discard-then-deal
    pattern, gated by CONTROLLER_HAS_CARD_IN_HAND."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=-1, hp=0, count="controller_hand_size")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_qira_discard_deal,
                                  target=TargetSpec(controller="any", kind="unit"))],
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_CARD_IN_HAND),
        ),
    ]


# ── BB-8: play-as-upgrade pay-then-ready ──────────────────────────────────────

def _bb8_pay_ready(state, source_ci, target_id, event_ctx):
    """Pay 2 resources and ready the chosen friendly Resistance unit — bound so
    "If you do" holds.  The gate guarantees ≥2 ready resources when offered."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 2)
    result = state.find_instance(target_id)
    if result is not None:
        result[1].exhausted = False
    return state


@card_ability("C25", "2")
def _bb8_c25_2():
    """C25_2 — BB-8 "Happy Beeps" (1/4, Piloting): "When played as an upgrade: You
    may pay 2 resources. If you do, ready a Resistance unit."  A
    ``WhenPlayed(as_upgrade=True)`` (fires only on the Pilot-upgrade play path)
    optional trigger gated by CONTROLLER_N_PLUS_READY_RESOURCES(2); its targeted
    ``CustomEffect`` pays 2 and readies a chosen friendly Resistance unit."""
    return TriggerAbility(
        trigger=WhenPlayed(as_upgrade=True),
        effects=[CustomEffect(
            fn=_bb8_pay_ready,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Resistance",)))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=2),
    )


# ── Stage 4 batch 26 (2026-07-13) — FRAMEWORK ESCALATION: the
#    ``TargetSpec.select_extreme`` set-relative "extreme" target selector ───────
def _darth_nihilus_p26_79(state, source_ci, target_id, event_ctx):
    """Deal 3 to the chosen (least-remaining-HP) unit; if that unit is a
    non-Vehicle unit, give an Experience token to Darth Nihilus.  The two clauses
    are bound in one CustomEffect because the conditional Experience depends on
    *which* unit was hit (the Bright Hope SOR_99 / Zeb Orellios LAW_45 pattern);
    the "non-Vehicle" test is read BEFORE the damage so it still applies when the
    3 damage defeats the target ("it" = the unit that was damaged)."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _ps, target_ci = result
    # "If it's a non-Vehicle unit" — printed traits, matching the ``non_vehicle``
    # predicate; captured before the damage so a defeated target still qualifies.
    is_non_vehicle = "Vehicle" not in (getattr(target_ci.card_def, "traits", None) or ())
    from swu.abilities.resolver import _apply_deal_damage
    state = _apply_deal_damage(state, target_id, 3, source_ci.card_def.display_name,
                               dealer_id=source_ci.owner_id)
    if is_non_vehicle:
        src = state.find_instance(source_ci.instance_id)
        if src is not None:
            ps, ci = src
            from swu.engine.tokens import attach_token
            attach_token(state, ps, ci, "Experience")
    return state


@card_ability("P26", "79")
def _darth_nihilus_p26_79_register():
    """P26_79 — Darth Nihilus "Lord of Hunger" (6/6, Villainy Force/Sith): "When
    Played/On Attack: Deal 3 damage to the unit with the least remaining HP among
    other units.  If it's a non-Vehicle unit, give an Experience token to this
    unit."  The keystone is the new ``TargetSpec.select_extreme="least_remaining_hp"``
    set-relative selector (a post-filter in ``_gather_legal_targets`` keeping only
    the minimum-remaining-HP candidates, so a tie prompts the controller and a
    single candidate auto-resolves).  "Among other units" = ``controller="any"``
    + ``not_self`` (both sides, excluding Nihilus).  Two mandatory triggers
    (``WhenPlayed`` + ``OnAttack``) share one ``CustomEffect`` (``_darth_nihilus_
    p26_79``); with no other units the effect fizzles (no legal target)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(
                fn=_darth_nihilus_p26_79,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("not_self",),
                                  select_extreme="least_remaining_hp"))],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_darth_nihilus_p26_79,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("not_self",),
                                  select_extreme="least_remaining_hp"))],
        ),
    ]


# ── Stage 4 batch 27 (2026-07-13) — FRAMEWORK ESCALATION: the ``permanent``
#    keyword-grant that ends when its source leaves play (the keyword-layer mirror
#    of Huyang TWI_110's permanent stat modifier) ────────────────────────────────
def _bd1_c25_4(state, source_ci, target_id, event_ctx):
    """Give the chosen unit +1/+0 and Saboteur for as long as BD-1 is in play.
    Two ``permanent`` modifiers sourced by BD-1 — a ``stats`` +1/+0 (the Huyang
    TWI_110 pattern) and a ``keyword_grant`` Saboteur.  Both are inert once BD-1
    leaves play (the compute-time / keyword-layer source-in-play guards) and are
    dropped by the leave-play cleanup in ``_defeat_unit`` / ``_apply_return_to_hand``
    (which drop every permanent modifier by source, regardless of kind).  A ``None``
    target (BD-1 is the only friendly unit) is a clean no-op."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": 1, "hp": 0},
        duration="permanent",
    ))
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="keyword_grant",
        value={"keyword": "Saboteur", "value": 0},
        duration="permanent",
    ))
    return state


@card_ability("C25", "4")
def _bd1_c25_4_register():
    """C25_4 — BD-1 "Beep Boo Boo Bweep" (1/3, Hidden — keyword layer): "When
    Played: Choose another friendly unit.  While this unit is in play, the chosen
    unit gets +1/+0 and gains Saboteur."  A mandatory ``WhenPlayed`` whose one
    ``CustomEffect.target`` (another friendly unit) attaches two ``permanent``
    modifiers sourced by BD-1.  The +1/+0 reuses the Huyang TWI_110 permanent-stat
    mechanism; the granted Saboteur is the new keyword-layer mirror
    (``has_keyword``/``keyword_value`` now skip a ``permanent`` keyword_grant whose
    source has left play).  With no other friendly unit the mandatory effect
    fizzles (no legal target)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_bd1_c25_4,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)))],
    )


# ── Stage 4 batch 29 (2026-07-13) — FRAMEWORK ESCALATION: deploy-leader-as-effect ──
def _grogu_deploy(state, source_ci, target_id, event_ctx):
    """Deploy Grogu (the source undeployed leader) for free."""
    from swu.engine.actions import deploy_leader_as_effect
    return deploy_leader_as_effect(state, source_ci.instance_id)


@card_ability("ASH", "18")
def _grogu_ash_18():
    """ASH_18 — Grogu "Charming Companion" (Leader 0/3): "When you play a unique
    unit that costs 4 or more: If this leader is ready, you may deploy him."

    An optional undeployed-leader ``WhenYouPlayCard`` trigger (collected by the
    base_zone trigger scan, the-mandalorian:04) gated ``SOURCE_READY`` ("If this
    leader is ready"), whose one no-target ``CustomEffect`` deploys the source
    leader **for free** via ``actions.deploy_leader_as_effect`` (the shared
    ``DeployLeader`` body factored into ``_deploy_leader_into_arena``).  The new
    ``WhenYouPlayCard`` fields ``unique=True`` + ``cost_min=4`` narrow the observed
    play to "a unique unit that costs 4 or more"; the deploy is off-threshold
    (Grogu has no deploy threshold, so this trigger is his only deploy path), and
    ``undeployed_only`` stops it re-firing once he is a unit.
    """
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", unique=True, cost_min=4),
        effects=[CustomEffect(fn=_grogu_deploy)],
        optional=True,
        undeployed_only=True,
        condition=ConditionCheck(Condition.SOURCE_READY),
    )


# ── Stage 4 batch 30 (2026-07-13) — trivial straggler cleanup (NO new primitive):
#    Shatterpoint P25_153, a "Choose one:" event that composes entirely from the
#    choose_two_modal pick=1 selector (batch 15/23) + DefeatUnit(hp_remaining_max)
#    + the spend_force_token / requires_prior_target "if you do" gate (In Pursuit
#    TWI_221).  batches 15/17/23 made modal+force trivial, so this needs zero
#    engine code.
def _shatterpoint_controller(state, source_ci, target_id, event_ctx):
    """Thin controller: push the choose_two_modal decision over the two option
    specs (idx 1, 2) with ``pick=1`` (Choose one)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _shatterpoint_use_force(state, source_ci, target_id, event_ctx):
    """Opt 2, effect 1 (no target): "Use the Force."  Spend the controller's Force
    token if held and, if a token was actually spent, set the ``prior_target_id``
    flag so the follow-up ``DefeatUnit(requires_prior_target)`` fires (the In
    Pursuit TWI_221 "If you do" gate).  With no token the flag stays unset, so the
    defeat has no candidates and is skipped."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if spend_force_token(state, ps):
        event_ctx["prior_target_id"] = source_ci.instance_id
    return state


@card_ability("P25", "153")
def _shatterpoint_p25_153():
    """P25_153 — Shatterpoint (Event, cost 4): "Choose one: Defeat a non-leader
    unit with 3 or less remaining HP. / Use the Force. If you do, defeat a
    non-leader unit."

    Zero new engine code — a pure composition (the Shatterpoint straggler my batch
    27–29 notes flagged, now cleared):
      * idx 0 = the ``EventAbility`` controller (a thin ``CustomEffect`` calling
        ``push_choose_modal(pick=1)`` over options idx 1, 2 — the SOR aspect-event
        selector shape, pick=1).
      * idx 1 (opt 1) = ``DefeatUnit`` on a non-leader unit with ≤3 remaining HP
        (``hp_remaining_max=3``); fizzles cleanly with no eligible unit.
      * idx 2 (opt 2) = "Use the Force. If you do, defeat a non-leader unit": a
        no-target ``CustomEffect`` spends the Force token (setting the
        ``prior_target_id`` flag iff spent) followed by a mandatory
        ``DefeatUnit(requires_prior_target)`` on ANY non-leader unit — the flag
        gates the defeat, so with no Force token the defeat has no candidates and
        the option does nothing (the In Pursuit TWI_221 "If you do" gate).

    The option specs are ``TriggerAbility(WhenPlayed())`` (the SOR aspect-event
    convention): safe because an event is never in ``_cards_in_play``, so
    ``_collect_triggers`` can never reach them — they resolve ONLY from the modal.
    """
    return [
        EventAbility(effects=[CustomEffect(fn=_shatterpoint_controller)]),
        # opt 1 — Defeat a non-leader unit with 3 or less remaining HP.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            DefeatUnit(TargetSpec(controller="any", kind="unit",
                                  predicates=("non_leader",), hp_remaining_max=3)),
        ]),
        # opt 2 — Use the Force. If you do, defeat a non-leader unit.
        TriggerAbility(trigger=WhenPlayed(), effects=[
            CustomEffect(fn=_shatterpoint_use_force),
            DefeatUnit(TargetSpec(controller="any", kind="unit",
                                  predicates=("non_leader", "requires_prior_target"))),
        ]),
    ]


# ── Batch 31: standing per-round conditional play-cost discount ───────────────

@card_ability("JTLP", "1")
def _director_krennic():
    """Director Krennic (JTLP_1) — "Shielded.  The first unit you play each round
    that has a 'When Defeated' ability costs 1 resource less."

    Shielded is the keyword layer.  The discount is a passive ``StandingPlayDiscount``
    marker read at the play-cost seam (``actions._play_cost`` via
    ``_standing_play_discount``): while Krennic is in play, the FIRST unit its
    controller plays each round whose printed text carries a "When Defeated" ability
    costs 1 less (``once_per_round`` default, tracked per source in
    ``game_memory.standing_play_discounts_used_this_round`` and spent at the play
    site).  No trigger, no decision.  Reprint sibling P25_65 aliased in reprints.py.
    """
    return StandingPlayDiscount(amount=1)


# ── Batch 34: attach an in-play unit as a Pilot upgrade ───────────────────────

def _poe_jtlp6(state, source_ci, target_id, event_ctx):
    """Poe Dameron JTLP_6 "When played as a unit": create an X-Wing token, then
    offer to attach Poe himself onto a friendly Vehicle without a Pilot as a
    Pilot upgrade (the pilot_self_attach primitive)."""
    from swu.engine.actions import _create_token_units, push_attach_unit_as_pilot
    ps = state.player_by_id(source_ci.owner_id)
    _create_token_units(state, ps, "X-Wing", 1)
    push_attach_unit_as_pilot(state, source_ci)
    return state


@card_ability("JTLP", "6")
def _poe_dameron_jtlp_6():
    """Poe Dameron (JTLP_6) — Piloting [2] (keyword layer).  "When played as a
    unit: Create an X-Wing token.  You may attach this unit as an upgrade to a
    friendly Vehicle unit without a Pilot on it."

    A mandatory ``WhenPlayed(as_unit=True)`` (fires only when Poe is played as a
    unit, never via his own Piloting) whose one no-target ``CustomEffect`` creates
    the X-Wing (CreateTokenUnit, ahsoka-tano:05) and pushes the new
    ``pilot_self_attach`` decision — the unit-becomes-Pilot-upgrade relocation
    primitive.  The X-Wing (a Vehicle) is itself a legal host, so Poe can hop onto
    the token he just made.  Reprint sibling P25_90 aliased in reprints.py.
    """
    return TriggerAbility(
        trigger=WhenPlayed(as_unit=True),
        effects=[CustomEffect(fn=_poe_jtlp6)],
    )


def _jabba_ash42_return_and_replay(state, source_ci, target_id, event_ctx):
    """Jabba the Hutt ASH_42 "When Played": return the chosen upgrade to its
    owner's hand; if it was returned to YOUR hand (you own it), offer to play it
    from your hand for free onto a legal host (the new play_upgrade_from_hand
    decision kind).

    ``target_id`` is a chosen non-token upgrade in play (kind="upgrade").  The
    return uses the extended ``_apply_return_to_hand`` (which now detaches an
    upgrade to its owner's hand).  The free-play is only offered when the upgrade's
    owner is the controller — "If it's returned to *your* hand" — otherwise it went
    to the opponent's hand and Jabba's controller cannot play it.
    """
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, upgrade_ci = result
    owner_id = upgrade_ci.owner_id
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.engine.actions import push_play_upgrade_from_hand
    state = _apply_return_to_hand(state, target_id)
    # Only the controller may replay it, and only if it landed in their hand.
    if owner_id == source_ci.owner_id:
        push_play_upgrade_from_hand(state, source_ci,
                                    upgrade_id=target_id, free=True)
    return state


@card_ability("ASH", "42")
def _jabba_the_hutt_ash_42():
    """Jabba the Hutt (ASH_42) — Restore 2 (keyword layer).  "When Played: You may
    return an upgrade to its owner's hand.  If it's returned to your hand, you may
    play it for free."

    An **optional** ``WhenPlayed`` whose one ``CustomEffect`` carries a
    ``kind="upgrade"`` target (any non-token upgrade in play — the optional trigger
    auto-declines when none exists).  The fn returns the chosen upgrade to its
    owner's hand (the completed ``_apply_return_to_hand`` upgrade branch) and, iff
    the controller owns it, pushes the new ``play_upgrade_from_hand`` decision to
    replay it for free onto a legal host (which re-fires the upgrade's own
    WhenPlayed).  Reprint sibling C26_6 aliased in reprints.py (batch 43).
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_jabba_ash42_return_and_replay,
            target=TargetSpec(controller="any", kind="upgrade"),
        )],
        optional=True,
    )


# ── Replacement effect: pilot-defeat → move to the ground arena (batch 47) ────

def _luke_j25_4_move_to_ground(state, source_ci, target_id, event_ctx):
    """Move the just-defeated pilot (Luke, in his owner's discard by now) back into
    the ground arena as an exhausted unit — the "you may instead" branch of his
    defeat-replacement.

    By the time this optional ``WhenDefeatedAsUpgrade`` trigger resolves, the host
    vehicle's ``_defeat_unit`` has already detached the pilot and placed it in its
    owner's discard (the Superlaser Technician SHD_85 timing).  So locate it there,
    move it into the owner's ground arena as a fresh unit — damage cleared,
    face-up, and **exhausted** ("exhaust him") — and emit ``UnitEntersPlay`` for the
    UI.  It is a relocation, not a play, so the enter-play bus / When Played
    triggers are NOT fired (Luke has none anyway)."""
    from swu.engine.state import Zone
    from swu.engine.events import UnitEntersPlay
    result = state.find_instance(source_ci.instance_id)
    if result is None:
        return state
    ps, ci = result
    if ci in ps.discard:
        ps.discard.remove(ci)
    ci.zone = Zone.GROUND_ARENA
    ci.face_down = False
    ci.exhausted = True
    ci.damage = 0
    ci.attached_upgrades = []
    ps.ground_arena.append(ci)
    state.event_log.append(UnitEntersPlay(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        arena="Ground",
    ))
    return state


@card_ability("J25", "4")
def _luke_skywalker_j25_4():
    """Luke Skywalker "You Still With Me?" (J25_4) — Piloting (keyword layer).  His
    only functional text lives in ``epic_action``: "If this upgrade would be
    defeated, you may instead move him to the ground arena as a unit and exhaust
    him."  A defeat-**replacement** on the Pilot upgrade form.

    Modelled as an optional ``WhenDefeatedAsUpgrade`` trigger (collected only when he
    dies as a detached pilot — see resolver._collect_triggers) whose one no-target
    ``CustomEffect`` relocates him discard → ground arena as an exhausted unit.  This
    is the faithful, low-risk replacement stand-in (the Superlaser Technician SHD_85
    discard-then-relocate pattern): the only difference from a true pre-defeat
    interception is a momentary discard touch, which no shipped card can observe
    (nothing triggers on an upgrade's defeat).  Played as a normal 3/2 unit he is
    vanilla — the trigger fires only from the ``defeated_upgrades`` scan, never for a
    unit-form defeat.  Canonical for the (J25_4, P25_89) group."""
    return TriggerAbility(
        trigger=WhenDefeatedAsUpgrade(),
        effects=[CustomEffect(fn=_luke_j25_4_move_to_ground)],
        optional=True,
    )


# ── p25-set:03 / jtlp-set:01 residuals ────────────────────────────────────────


def _kylo_p25_46_on_attack(state, source_ci, target_id, event_ctx):
    """Kylo Ren P25_46: "On Attack: Give a unit +2/+0 for this phase.  If it's a
    non-Villainy unit, also give an Experience token to it."

    ONE targeted ``CustomEffect`` doing both halves — the Kylo Ren SHD_141 rule,
    aptly — so the buff and the token cannot name different units.  The Villainy
    test reads the chosen unit's PRINTED aspects, which is what an aspect clause
    means (nothing grants an aspect)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, unit = res
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=unit.instance_id,
        kind="stats",
        value={"power": 2, "hp": 0},
        duration="this_phase",
    ))
    aspects = {getattr(a, "name", str(a))
               for a in (getattr(unit.card_def, "aspects", None) or ())}
    if "Villainy" not in aspects:
        from swu.engine.tokens import attach_token
        attach_token(state, holder, unit, "Experience")
    return state


@card_ability("P25", "46")
def _kylo_ren_p25_46():
    """P25_46 — Kylo Ren "Rule By Fear" (Unit, First Order/Force, 6/7): "While
    playing this unit, ignore his Villainy aspect penalty if you control Rey.  On
    Attack: Give a unit +2/+0 for this phase.  If it's a non-Villainy unit, also
    give an Experience token to it."

    The waiver is ``IgnoreAspectPenaltyForPlays`` in its two NEW readings —
    ``self_only`` (the marker sits on the card being PLAYED, which no in-play scan
    could reach) and ``only_aspects`` (only the Villainy pips are waived, computed
    as their marginal cost, so an Aggression pip the base cannot match is still
    paid).  "You control Rey" is ``CONTROLLER_CONTROLS_NAMED``, which already scans
    base_zone, both arenas and every attached upgrade."""
    return [
        IgnoreAspectPenaltyForPlays(
            self_only=True, only_aspects=("Villainy",),
            condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                     param="Rey")),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_kylo_p25_46_on_attack,
                target=TargetSpec(controller="any", kind="unit"))],
        ),
    ]


@card_ability("JTLP", "18")
def _fetts_firespray_jtlp_18():
    """JTLP_18 — Fett's Firespray (Unit, Underworld/Vehicle/Transport, 4/4), the
    prerelease printing of Fett's Firespray JTL_240: "When Played/On Attack: Deal 1
    indirect damage to a player.  If you control Boba Fett (as a unit, upgrade, or
    leader), deal 2 indirect damage instead."

    ⚠ Its DB ``text`` is TRUNCATED mid-sentence ("… If you control Boba Fett"),
    which is why the reprint sweep could not alias it onto JTL_240 —
    ``apply_reprint_aliases`` asserts the two printed faces are byte-identical, and
    these differ by the missing clause (the ``_norm_rules`` blind spot, from the
    other side).  It is the same card, so it reuses JTL_240's own magnitude
    function by import rather than a copy: the two cannot drift."""
    from swu.cards.jtl.abilities import _fetts_firespray_indirect
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_fetts_firespray_indirect)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_fetts_firespray_indirect)]),
    ]


@card_ability("JTLP", "16")
def _anakin_skywalker_jtlp_16():
    """JTLP_16 — Anakin Skywalker, "I'll Try Spinning" (Unit, Force/Fringe/Pilot,
    2/3; Piloting [2 resources Cunning Heroism]), the prerelease printing of
    Anakin Skywalker JTL_197:

        Piloting [2 resources Cunning Heroism]
        When attached unit completes an attack (and survives): You may return this
        upgrade to its owner's hand.

    ⚠ Its DB ``epic_action`` is TRUNCATED — the trigger clause is missing outright,
    leaving "Piloting [2 resources Cunning Heroism]: You may return this upgrade to
    its owner's hand." — so the reprint sweep cannot alias it onto JTL_197 (the
    ``apply_reprint_aliases`` face guard would, correctly, refuse).  That the clause
    is a DB defect rather than a different card is confirmed by the row's own rules
    note, which glosses a trigger the printed text no longer contains: "A unit must
    survive an attack to trigger its 'when this unit completes an attack'
    abilities."  The same defect shape as JTLP_18 Fett's Firespray.

    So it is registered here and IMPORTS JTL_197's own finder — which now matches
    either printing's registry coordinates (``ANAKIN_PILOT_KEYS``) — rather than
    copying it: the twins cannot drift.  See JTL_197 for why this must be a
    ``GrantedAbility`` (a non-leader unit riding as a Pilot upgrade never has its
    OWN triggers collected) and why "(and survives)" is intrinsic to
    ``WhenAttackEnds``."""
    from swu.abilities.registry import WhenAttackEnds
    from swu.cards.jtl.abilities import _anakin_jtl_197_return_pilot
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_anakin_jtl_197_return_pilot)],
        optional=True,
    ))
