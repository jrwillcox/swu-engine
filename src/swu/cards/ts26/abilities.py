"""TS26 (2026 two-player starter) card ability registrations.

The first ``src/swu/cards/ts26/`` module.  Imported for its side effects (the
``@card_ability`` decorators populate the registry).

⚠️⚠️ **TOKEN COLLISIONS**: TS26 prints four tokens at LOW numbers — ``TS26_1`` is
the Battle Droid token UNIT, ``TS26_2`` the Clone Trooper token UNIT, ``TS26_3`` the
**Experience token UPGRADE** and ``TS26_4`` the **Shield token UPGRADE** — and each
shares its ``(set, number)`` registry key with a LEADER of the same number.  So Maul
TS26_3 is registered ONLY from spec kinds a token can never reach:
``ActivatedAbility(undeployed_only=True)`` (the arena scan demands a Leader card_def),
``TriggerAbility(WhenDeployed())`` (matched by instance id against a LeaderDeployed
event) and ``TriggerAbility(deployed_only=True)`` (collected only from cards in play,
never from a host's ``attached_upgrades``).  A ``ConstantAbility``, a
``GrantedAbility`` or a passive marker would NOT be safe there.  TS26_8 (Ahsoka Tano)
is above the token block and carries no hazard.
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, EventAbility, ActivatedAbility, ConstantAbility,
    GrantedAbility,
    WhenPlayed, WhenDefeated, WhenDeployed, OnAttack, WhenAttacked,
    WhenAttackEnds, WhenYouPlayCard, WhenDealsCombatDamageToBase,
    WhenUnitDefeated, PhaseStartTrigger, WhenUnitReadies, WhenUnitAttacks,
    DealDamage, DealDamageEqualTo, Heal, ReadyCard, ReturnToHand,
    GiveToken, DrawCards, CreateTokenUnit, CustomEffect,
    GrantKeyword, KeywordGrant, StatBonus, ModifyStats,
    CostReduction, NextPlayDiscount,
    ExhaustSelf, ConditionCheck, Condition, Duration,
    TargetSpec, SELF, ATTACKER, EACH_ENEMY, EACH_FRIENDLY, EACH_IN_PLAY,
)


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:01 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _maul_experience_probe(state, source_ci, target_id, event_ctx):
    """Maul TS26_3: "Choose a unit.  If it has more different keywords than it has
    Experience tokens on it, give an Experience token to it and deal 1 damage to it."

    ONE targeted ``CustomEffect`` doing the whole clause (the Kylo SHD_141 rule) —
    the choice happens unconditionally ("Choose a unit"), and only the payoff is
    gated, so a unit that fails the test is still a legal pick.  The keyword side is
    ``keywords.distinct_keyword_count`` (Gallius Rax ASH_100), which is deliberately
    LIGHTWEIGHT; the token side counts attached Experience upgrades, and because the
    token is handed out BEFORE the damage, a repeat use of the ability on the same
    unit walks the count up one step at a time exactly as printed."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, unit = res
    from swu.engine.keywords import distinct_keyword_count
    from swu.engine.tokens import attach_token
    from swu.abilities.resolver import _apply_deal_damage
    experience = sum(1 for up in (unit.attached_upgrades or ())
                     if up.card_def.display_name == "Experience")
    if distinct_keyword_count(state, unit) <= experience:
        return state
    attach_token(state, state.player_by_id(unit.owner_id), unit, "Experience")
    _apply_deal_damage(state, target_id, 1,
                       source_ci.card_def.display_name)
    return state


def _maul_clause():
    return CustomEffect(fn=_maul_experience_probe,
                        target=TargetSpec(controller="any", kind="unit"))


@card_ability("TS26", "3")
def _maul_ts26():
    """TS26_3 — Maul, "Collective Ambition" (Leader, Force Underworld, 5/9, unique).

    Undeployed: "Action [Exhaust]: <the clause>."
    Deployed:   "When Deployed/On Attack: <the clause>."

    Three registrations over ONE shared effect — the recurring leader shape.  ⚠️ See
    the module docstring: TS26_3 is also the Experience token upgrade's key, so only
    these three side-gated spec kinds are safe here."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[_maul_clause()],
            title="Choose a unit — Experience and 1 damage if it out-keywords it",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[_maul_clause()],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[_maul_clause()],
            deployed_only=True,
        ),
    ]


def _executioners_arena_damage(state, source_ci, target_id, event_ctx):
    """Executioner's Arena TS26_11: "For each friendly leader unit, you may deal 2
    damage to a unit."

    ``push_select_damage(amount_each=2, max_targets=<leader units>)`` — the
    select-up-to-N loop, whose always-offered finish carries every "you may" at once.
    DOCUMENTED NARROWING: that decision takes DISTINCT units, so two leader units
    cannot stack both hits on one target; with the usual single leader unit the two
    readings coincide."""
    from swu.engine.actions import push_select_damage
    from swu.abilities.resolver import _is_leader_unit
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena
            if _is_leader_unit(u))
    if n <= 0:
        return state
    push_select_damage(state, source_ci, amount_each=2, max_targets=n)
    return state


@card_ability("TS26", "11")
def _executioners_arena():
    """TS26_11 — Executioner's Arena (Base): "Epic Action: For each friendly leader
    unit, you may deal 2 damage to a unit."

    A once-per-GAME ``ActivatedAbility(epic=True)`` on a BASE (the Alliance Outpost
    LAW_19 shape), gated on ``CONTROLLER_HAS_LEADER_UNIT`` so the one-shot is never
    burnt while it would do nothing."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_executioners_arena_damage)],
        title="Deal 2 damage to a unit per friendly leader unit",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
    )


def _sundari_palace_ramp(state, source_ci, target_id, event_ctx):
    """Sundari Palace TS26_12: "For each friendly leader unit, you may resource a card
    from your hand and ready it.  If you do, defeat that many friendly resources at
    the start of the regroup phase."

    The new ``resource_from_hand`` decision: an "up to N" loop over the hand whose
    picks enter the resource row READY (and, unlike Smuggle, are NOT replaced from
    the deck, so the row really grows).  Its ``then_defeat_resources_at_regroup``
    rider schedules ONE resource defeat per card actually resourced — so declining
    the whole thing schedules nothing, which is the printed "If you do"."""
    from swu.engine.actions import push_resource_from_hand
    from swu.abilities.resolver import _is_leader_unit
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena
            if _is_leader_unit(u))
    if n <= 0:
        return state
    push_resource_from_hand(state, source_ci, count=n,
                            then_defeat_resources_at_regroup=True)
    return state


@card_ability("TS26", "12")
def _sundari_palace():
    """TS26_12 — Sundari Palace (Base): "Epic Action: For each friendly leader unit,
    you may resource a card from your hand and ready it.  If you do, defeat that many
    friendly resources at the start of the regroup phase." """
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_sundari_palace_ramp)],
        title="Resource cards from hand (ready) per friendly leader unit",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
    )


def _c3po_hand_over(state, source_ci, target_id, event_ctx):
    """C-3P0 TS26_15's "When Played: An opponent takes control of this unit" — the
    ``change_control`` seam (control is implicit: whichever player's arena holds the
    card), with ``owner_id`` untouched so he returns to his real owner's discard."""
    from swu.engine.actions import change_control
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    holder, ci = res
    opp = next((p for p in state.players if p.player_id != holder.player_id), None)
    if opp is None:
        return state
    change_control(state, ci, opp.player_id)
    return state


@card_ability("TS26", "15")
def _c_3p0_ts26():
    """TS26_15 — C-3P0, "Die, Jedi Dogs!" (Unit, Droid, 2/5, unique):
    "When Played: An opponent takes control of this unit.
     Action [Exhaust]: Deal damage equal to this unit's power to another ground unit.
     Only opponents may use this ability."

    "Only opponents may use this ability" needs NO new gate: the ability enumeration
    already offers a unit's Actions to whoever CONTROLS it, and the When Played hands
    him straight to the opponent — so the printed restriction is exactly what the
    ordinary controller scoping gives, for as long as he stays where he was sent.
    ``DealDamageEqualTo(count="source_power")`` is the effective power (Crosshair
    SHD_87), and ``not_self`` is the printed "another"."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_c3po_hand_over)],
        ),
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit", arena="ground",
                                  predicates=("not_self",)),
                count="source_power")],
            title="Deal damage equal to this unit's power to another ground unit",
        ),
    ]


@card_ability("TS26", "19")
def _coleman_trebor():
    """TS26_19 — Coleman Trebor, "Jedi Rescuer" (Unit, Force Jedi Republic, 2/2,
    unique; Hidden — keyword layer): "When Played: Deal 1 damage to each enemy base.
    Heal 1 damage from your base for each damage dealt this way."

    Two fixed effects, the General Veers IBH_68 shape.  In two-player "each enemy
    base" is one base and "for each damage dealt this way" is therefore 1 — the heal
    is a fixed 1 rather than a measured count (DOCUMENTED SIMPLIFICATION: a prevented
    or capped base hit would still heal)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            DealDamage(1, TargetSpec(controller="enemy", kind="base",
                                     fixed=EACH_ENEMY)),
            Heal(1, TargetSpec(controller="friendly", kind="base",
                               fixed=EACH_FRIENDLY)),
        ],
    )


@card_ability("TS26", "23")
def _assault_lander_laat():
    """TS26_23 — Assault Lander LAAT (Unit, Republic Transport Vehicle, 3/5):
    "When Played: Create 2 Clone Trooper tokens.
     When the regroup phase starts: Deal 4 damage to this unit."

    ``PhaseStartTrigger("regroup")`` is the Foresight TWI_68 timing — it fires at the
    START of regroup, i.e. before that phase's ready step.  The 4 damage is dealt to
    itself, and a 3/5 that has taken anything at all dies to it, which is the card's
    whole tradeoff."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CreateTokenUnit("Clone Trooper", count=2)],
        ),
        TriggerAbility(
            trigger=PhaseStartTrigger("regroup"),
            effects=[DealDamage(4, TargetSpec(fixed=SELF))],
        ),
    ]


@card_ability("TS26", "24")
def _sundari_gauntlet():
    """TS26_24 — Sundari Gauntlet (Unit, Mandalorian Transport Vehicle, 6/5;
    Sentinel — keyword layer): "On Defense: Deal 1 damage to your base."

    **"On Defense" IS ``WhenAttacked``** — the card's own rules note says those
    abilities trigger at the same time as "On Attack" ones (Canto Bight Security
    LAW_121)."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[DealDamage(1, TargetSpec(controller="friendly", kind="base",
                                          fixed=EACH_FRIENDLY))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:02 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _fiery_alliance_strike(state, source_ci, target_id, event_ctx):
    """Fiery Alliance TS26_25: "When Played: You may deal 1 damage to another friendly
    unit and attack with it."

    ONE targeted ``CustomEffect`` binding the damage to the attack (the Kylo SHD_141
    rule) with ``push_granted_attack(attacker_id=…)`` PINNED to the unit just chosen —
    a second free choice would let the damage and the attack name different units
    (the T-6 Shuttle ASH_109 lesson).  The attack is pushed even if the damage killed
    the unit; ``push_granted_attack`` simply finds no such attacker and fizzles."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import push_granted_attack
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
    if state.find_instance(target_id) is not None:
        push_granted_attack(state, source_ci, attacker_id=target_id)
    return state


@card_ability("TS26", "25")
def _fiery_alliance():
    """TS26_25 — Fiery Alliance (Upgrade, Innate, cost 2, +2/+2): "When Played: You
    may deal 1 damage to another friendly unit and attack with it."

    ⚠️ "ANOTHER friendly unit" on an UPGRADE's When Played is the new
    ``not_attached_host`` predicate, NOT ``not_self`` — the source here is the
    upgrade, so ``not_self`` would exclude the upgrade (which is no candidate anyway)
    and happily offer the unit it is riding."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_fiery_alliance_strike,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_attached_host",)))],
        optional=True,
    )


@card_ability("TS26", "29")
def _ziton_moj_ts26():
    """TS26_29 — Ziton Moj, "Sowing Chaos" (Unit, Underworld, 4/4, unique; Ambush —
    keyword layer): "On Attack: For each player, deal 1 damage to a unit that player
    controls."

    "For each player" in two-player is exactly one friendly and one enemy unit, so it
    is two ordinary targeted effects — each chosen by the source's controller, which
    is what "deal … to a unit that player controls" means.  Either half fizzles
    silently when that player controls no unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[
            DealDamage(1, TargetSpec(controller="friendly", kind="unit")),
            DealDamage(1, TargetSpec(controller="enemy", kind="unit")),
        ],
    )


def _reckless_landing_play(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=4, then_damage=4)
    return state


@card_ability("TS26", "32")
def _reckless_landing():
    """TS26_32 — Reckless Landing (Event, Gambit, cost 2): "Play a unit from your
    hand.  It costs 4 resources less.  Deal 4 damage to it."

    ``push_play_from_hand(cost_reduction=4, then_damage=4)`` verbatim — both riders
    already exist on that decision, and ``then_damage`` lands on the unit that was
    actually played."""
    return EventAbility(effects=[CustomEffect(fn=_reckless_landing_play)])


@card_ability("TS26", "58")
def _backed_by_the_pykes():
    """TS26_58 — Backed by the Pykes (Event, Supply, cost 3):
    "Give an Experience token to a friendly unit.
     You may deal damage to a unit equal to the number of Experience tokens on
     friendly units."

    Two targeted effects (two prompts, both real choices).  The new
    ``source_controller_experience_tokens`` count is read at RESOLUTION, i.e. after
    the leading ``GiveToken`` has landed — which is what makes the token this very
    card just handed out part of the magnitude, as printed.  The "you may" is the
    second target's ``optional`` (a ChooseTarget(None) decline)."""
    return EventAbility(effects=[
        GiveToken("Experience", TargetSpec(controller="friendly", kind="unit")),
        DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit", optional=True),
            count="source_controller_experience_tokens"),
    ])


def _r2d2_base_hit(state, source_ci, target_id, event_ctx):
    """R2-D2 TS26_62: "You may deal 2 damage to a base.  If you do, that base's
    controller draws a card."  ONE targeted ``CustomEffect``, so the damage and the
    draw can never name different bases (the Kylo SHD_141 rule); the beneficiary is
    read back off the chosen base through ``find_instance``, which returns the
    holding player."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, _base = res
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import _draw_cards
    _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)
    _draw_cards(state, holder, 1)
    return state


@card_ability("TS26", "62")
def _r2_d2_ts26():
    """TS26_62 — R2-D2, "Getting His Chance" (Unit, Droid Republic, 1/3, unique;
    Raid 2 — keyword layer): "When Played: You may deal 2 damage to a base.  If you
    do, that base's controller draws a card." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_r2d2_base_hit,
            target=TargetSpec(controller="any", kind="base"))],
        optional=True,
    )


@card_ability("TS26", "64")
def _urgent_mission():
    """TS26_64 — Urgent Mission (Event, Plan, cost 2): "Deal 2 damage to your base.
    Draw 2 cards."

    Both effects are prompt-free (a ``fixed=EACH_FRIENDLY`` base hit and a plain
    draw), so the SHD_18 leading-effect wart cannot bite."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="friendly", kind="base",
                                 fixed=EACH_FRIENDLY)),
        DrawCards(count=2),
    ])


@card_ability("TS26", "67")
def _ruping_rider():
    """TS26_67 — Ruping Rider (Unit, Creature Trooper, 3/4; Grit — keyword layer):
    "When Played: If your base has 15 or more damage on it, deal 2 damage to a base."

    ``CONTROLLER_BASE_DAMAGE_MIN`` at 15 as the ability's ``condition``, so a
    below-threshold board never even collects the trigger (no prompt, no no-op)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
        condition=ConditionCheck(Condition.CONTROLLER_BASE_DAMAGE_MIN, param=15),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:03 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _remove_the_chip_hit(state, source_ci, target_id, event_ctx):
    """Remove the Chip TS26_69: "Deal 2 damage to a unit.  If it's a Clone, ready
    it."  ONE targeted ``CustomEffect`` so both halves name the same unit (the Kylo
    SHD_141 rule); the trait test uses EFFECTIVE traits (``has_trait``), so a granted
    Clone trait counts, and the ready is skipped when the damage defeated it."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.traits import has_trait
    _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, unit = res
    from swu.engine.state import Zone
    if unit.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state  # defeated by the damage — find_instance reaches the DISCARD
    if has_trait(state, unit, "Clone"):
        unit.exhausted = False
    return state


@card_ability("TS26", "69")
def _remove_the_chip():
    """TS26_69 — Remove the Chip (Event, Modification, cost 2): "Deal 2 damage to a
    unit.  If it's a Clone, ready it." """
    return EventAbility(effects=[CustomEffect(
        fn=_remove_the_chip_hit,
        target=TargetSpec(controller="any", kind="unit"))])


@card_ability("TS26", "70")
def _backed_by_black_sun():
    """TS26_70 — Backed by Black Sun (Event, Supply, cost 3):
    "Deal 1 damage to an enemy unit.
     You may deal damage to a unit equal to the number of damaged enemy units."

    The new ``enemy_damaged_units`` count, read at resolution — so the unit the
    leading 1 damage just damaged is already part of the magnitude, as printed.  The
    "you may" is the second target's ``optional``."""
    return EventAbility(effects=[
        DealDamage(1, TargetSpec(controller="enemy", kind="unit")),
        DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit", optional=True),
            count="enemy_damaged_units"),
    ])


@card_ability("TS26", "71")
def _take_action():
    """TS26_71 — Take Action (Event, Tactic, cost 3): "This event costs 1 resource
    less to play for each friendly leader unit.  Deal 3 damage to a unit."

    ``CostReduction(per_friendly_leader_unit=True)`` is the new scaling arm; it shares
    ``resolver._is_leader_unit`` with the ``leader_unit`` predicate, so an UNDEPLOYED
    leader (which sits in the base zone and is no unit) correctly discounts nothing.
    Read at the single play-cost site, so it moves both affordability and the
    resources actually exhausted."""
    return [
        CostReduction(amount=1, per_friendly_leader_unit=True),
        EventAbility(effects=[
            DealDamage(3, TargetSpec(controller="any", kind="unit")),
        ]),
    ]


@card_ability("TS26", "72")
def _fervor():
    """TS26_72 — Fervor (Event, Innate, cost 5): "Ready a unit.  Deal 3 damage to a
    unit."

    Two independent targeted effects — two prompts, and deliberately not bound
    together: the card names "a unit" twice, so readying one and burning another is
    legal.  The ready is filtered to ``exhausted`` units so it is never offered as a
    no-op (the Ozzel SOR_129 rule)."""
    return EventAbility(effects=[
        ReadyCard(TargetSpec(controller="any", kind="unit",
                             predicates=("exhausted",))),
        DealDamage(3, TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("TS26", "73")
def _moralo_eval():
    """TS26_73 — Moralo Eval, "Infamous Murderer" (Unit, Underworld, 3/2, unique;
    Shielded — keyword layer): "When your base is dealt combat damage: You may deal 1
    damage to a unit."

    ``WhenDealsCombatDamageToBase(filter=…)`` is the OBSERVER form of that trigger
    (Temple of Destruction LOF_25) — a different card fires for whoever dealt the
    damage.  An ENEMY unit attacking a base always hits the observer's OWN base in
    two-player, so ``controller="enemy"`` is the whole filter, and combat-only is
    intrinsic to the trigger (unlike ``WhenDamageDealtToYourBase``, which any damage
    source feeds)."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(
            filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:04 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _ahsoka_ts26_exhaust_peek(state, source_ci, target_id, event_ctx):
    """Ahsoka TS26_8 undeployed: "You may exhaust this leader.  If you do, look at the
    top card of your deck.  You may play it (paying its cost), discard it, or leave it
    on top."

    The cost and its payoff live in ONE ``CustomEffect`` so an unpaid exhaust can
    never deliver the look (the "If you do" binding).  There is no way to express
    "exhaust this leader" as an ``ExhaustCard(fixed=SELF)`` effect — an undeployed
    leader in the base zone is no arena unit — hence the Boba Fett JTL_9 convention of
    bundling it here."""
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    _ps, leader = res
    if leader.exhausted:
        return state
    leader.exhausted = True
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_play_discard")
    return state


def _ahsoka_ts26_attack_end_peek(state, source_ci, target_id, event_ctx):
    """Ahsoka TS26_8 deployed: "When Attack Ends: Look at the top card of your deck.
    You may play it, discard it, or leave it on top.  If you play it, it costs 1
    resource less" — Improvise LAW_242's ``may_play_discard`` + ``cost_reduction``."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_play_discard", cost_reduction=1)
    return state


@card_ability("TS26", "8")
def _ahsoka_tano_ts26():
    """TS26_8 — Ahsoka Tano, "I Have an Idea" (Leader, Force, 3/6, unique).

    Undeployed: "When you play an event: You may exhaust this leader.  If you do, look
                 at the top card of your deck.  You may play it (paying its cost),
                 discard it, or leave it on top of your deck."
    Deployed:   "Raid 1  |  When Attack Ends: Look at the top card of your deck.  You
                 may play it, discard it, or leave it on top.  If you play it, it
                 costs 1 resource less."

    The undeployed clause is a ``WhenYouPlayCard(card_type="event")`` controller
    observer gated ``SOURCE_READY`` — so a spent leader is never offered a use she
    cannot pay for.  Raid 1 is the keyword layer's."""
    return [
        TriggerAbility(
            trigger=WhenYouPlayCard(card_type="event"),
            effects=[CustomEffect(fn=_ahsoka_ts26_exhaust_peek)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_ahsoka_ts26_attack_end_peek)],
            deployed_only=True,
        ),
    ]


def _mother_talzin_strip(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, discarder_draws=True,
                          then_foreign_discard_play=True)
    return state


@card_ability("TS26", "26")
def _mother_talzin():
    """TS26_26 — Mother Talzin, "Stealing the Spirit" (Unit, Force Night, 5/4, unique;
    Sentinel — keyword layer): "When Defeated: Look at an opponent's hand and discard
    a card from it.  If you do, they draw a card.  If the discarded card is a unit,
    for this phase you may play it from their discard pile, ignoring its aspect
    penalties."

    Bazine Netal SHD_184's ``push_name_and_discard(discarder_draws=True)`` — the
    optimal-play collapse of look-then-discard, since the controller already sees the
    whole hand — plus the new ``then_foreign_discard_play`` rider, which records the
    discarded instance in ``game_memory.foreign_discard_play_this_phase`` (the PAID
    cross-pile permission built for Obi-Wan Kenobi SEC_205, whose branch of the
    discard-play enumeration already expresses the aspect waiver as a discount).
    Mandatory here, so no ``optional``; an empty hand fizzles with no prompt."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_mother_talzin_strip)],
    )


def _kouhun_debuff(state, source_ci, target_id, event_ctx):
    """The payoff of Kouhun Assassination TS26_33, applied to the unit the
    CONTROLLER chose: -8/-8 for this phase."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": -8, "hp": -8},
        duration="this_phase",
    ))
    return state


def _kouhun_assassination_ask(state, source_ci, target_id, event_ctx):
    """"An opponent (of your choice) may discard a card from their hand.  If they do,
    give a non-Vehicle unit -8/-8 for this phase" (TS26_33).

    The ``may_discard`` decision handed to the OPPONENT (the say_no SOR_233
    deciding-player shift), with the payoff on the ACCEPT arm.  The unit is chosen
    FIRST by the ordinary targeted-effect machinery and pinned into the decision, so
    the controller is prompted once and the debuff cannot drift to another unit.

    ⚠️ DOCUMENTED ODDITY — implemented exactly as printed: because the payoff harms
    the deciding player, a rational opponent always declines and the card does
    nothing.  Every sibling template in the engine (Look the Other Way SHD_227,
    Political Pressure TWI_222, Syril Karn SEC_133) puts the penalty on the DECLINE
    arm, so this text reads like an upstream "If they do"/"If they don't" slip; the
    printed wording is nevertheless what the DB carries and what is implemented, and
    flipping it is a rules judgement, not an encoding one."""
    if target_id is None:
        return state
    from swu.engine.actions import push_may_discard_for_debuff
    push_may_discard_for_debuff(state, source_ci, target_id)
    return state


@card_ability("TS26", "33")
def _kouhun_assassination():
    """TS26_33 — Kouhun Assassination (Event, Gambit, cost 3): "An opponent (of your
    choice) may discard a card from their hand.  If they do, give a non-Vehicle unit
    -8/-8 for this phase." """
    return EventAbility(effects=[CustomEffect(
        fn=_kouhun_assassination_ask,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("non_vehicle",)))])


def _abandoned_the_order_revoke(state, source_ci, target_id, event_ctx):
    """Abandoned the Order TS26_37: "Attached unit LOSES the Jedi trait".

    A PERMANENT ``trait_revoke`` modifier sourced on the upgrade — the Exiled from
    the Force SEC_54 recipe over the Lando JTL_3 lifetime rule
    (``_modifier_source_in_play`` counts an attached upgrade as in play, so the
    revocation lifts exactly when the upgrade detaches).  The trait layer consults
    revocations FIRST, so the host cannot regain Jedi while it holds."""
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
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
        value={"trait": "Jedi"},
        duration="permanent",
    ))
    return state


@card_ability("TS26", "37")
def _abandoned_the_order():
    """TS26_37 — Abandoned the Order (Upgrade, Learned, cost 4, +1/+1):
    "Attached unit loses the Jedi trait and gains Restore 1.
     When Played: You may return a non-leader unit to its owner's hand."

    THREE specs.  The Restore is an upgrade-SELF ``ConstantAbility(KeywordGrant)`` —
    the keyword layer's attached-upgrade scan is the one path an upgrade's keyword
    reaches its host (Constructed Lightsaber LOF_261).  The trait loss cannot ride
    there (it is no keyword), so it is a permanent ``trait_revoke`` armed on play.
    The bounce is its OWN When Played ability because only separate abilities can
    carry different ``optional`` flags (the Bossk LAW_31 rule) — the trait strip is
    mandatory, the return is a "may"."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Restore", value=1)],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_abandoned_the_order_revoke)],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                             predicates=("non_leader",)))],
            optional=True,
        ),
    ]


def _captain_vaughn_search(state, source_ci, target_id, event_ctx):
    """Captain Vaughn TS26_39: "Search the top 3 cards of your deck for a card and
    draw it.  Then, put a card from your hand on top of your deck."

    The "Then, …" half rides ``push_deck_search(then_top_from_hand=True)``, settled at
    the search's own resolve point.  ⚠️ It could NOT simply be pushed first and let
    LIFO order it: ``push_bottom_from_hand`` reads the hand at PUSH time and fizzles
    on an empty one, and the whole point is that the card the search just drew is
    among the cards that may go back."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, window=3, up_to=False,
                     eligible=lambda cd: True, then_top_from_hand=True)
    return state


@card_ability("TS26", "39")
def _captain_vaughn():
    """TS26_39 — Captain Vaughn, "Search the Tunnels" (Unit, Clone Republic Trooper,
    2/5, unique; Grit — keyword layer): "When Defeated: Search the top 3 cards of your
    deck for a card and draw it.  Then, put a card from your hand on top of your deck.
    (Put the other cards on the bottom of your deck in a random order.)" """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_captain_vaughn_search)],
    )


def _secret_marriage_shields(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_select_token
    push_select_token(
        state, source_ci, token_type="Shield", max_targets=2,
        controller="any", kind="unit", predicates=["non_vehicle"],
        then_draw_if_enemy_chosen=True,
    )
    return state


@card_ability("TS26", "46")
def _secret_marriage():
    """TS26_46 — Secret Marriage (Event, Plan, cost 2; Plot — keyword layer): "Give a
    Shield token to each of up to 2 non-Vehicle units.  If you give a Shield to an
    enemy unit this way, draw a card."

    The select-up-to-N loop (its always-offered finish IS the "up to"), with the new
    ``then_draw_if_enemy_chosen`` rider settled after the pop — so the draw is paid
    exactly when a pick really landed on an enemy unit, which is the whole tension of
    the card."""
    return EventAbility(effects=[CustomEffect(fn=_secret_marriage_shields)])


def _mechanize_replay(state, source_ci, target_id, event_ctx):
    """Mechanize TS26_57: "Play a non-Vehicle unit from your discard pile (paying its
    cost) and give an Experience token to it."

    ``from_discard`` alone would ALSO offer the hand, so the discard-only restriction
    is spelled with a computed ``eligible_ids`` whitelist (the Salvage JTL_121
    convention).  The token rides the ``then_select_token`` SETTLE payoff at
    ``restrict_played`` — the only ordering that runs after the play (LOF_125)."""
    from swu.engine.actions import push_play_from_hand
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    eligible = frozenset(
        ci.instance_id for ci in ps.discard
        if isinstance(ci.card_def, Unit)
        and "Vehicle" not in (getattr(ci.card_def, "traits", None) or ())
    )
    if not eligible:
        return state
    push_play_from_hand(
        state, source_ci, from_discard=True, eligible_ids=eligible,
        then_select_token={"token_type": "Experience", "max_targets": 1,
                           "restrict_played": True},
    )
    return state


@card_ability("TS26", "57")
def _mechanize():
    """TS26_57 — Mechanize (Event, Supply, cost 2): "Play a non-Vehicle unit from your
    discard pile (paying its cost) and give an Experience token to it." """
    return EventAbility(effects=[CustomEffect(fn=_mechanize_replay)])


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:05 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("TS26", "68")
def _arms_deal():
    """TS26_68 — Arms Deal (Event, Supply, cost 2): "You and an opponent each draw 2
    cards."

    ``DrawCards(player="each")`` — in two-player "you and an opponent" IS every
    player (the Chio Fain LAW_48 reading)."""
    return EventAbility(effects=[DrawCards(count=2, player="each")])


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:06 — the TS26 LEADER block (+ First Battle Memorial)
#
# ⚠️⚠️ THREE of these seven numbers are TOKEN COLLISIONS — TS26_1 (Battle Droid
# token UNIT), TS26_2 (Clone Trooper token UNIT) and TS26_4 (Shield token
# UPGRADE).  Every ability registered on those keys is therefore side-gated to a
# spec kind a token can never reach: ``ActivatedAbility(undeployed_only=True)``
# (the arena enumeration demands a Leader card_def), ``TriggerAbility(WhenDeployed
# ())`` (matched by instance id against a LeaderDeployed event) and
# ``TriggerAbility(deployed_only=True)`` (collected only from cards in play, never
# from a host's ``attached_upgrades``).  A ``ConstantAbility``, a
# ``GrantedAbility`` or a passive marker would leak onto the token — see the
# module docstring.  TS26_5/6/7/9 are collision-free.
# ══════════════════════════════════════════════════════════════════════════════


def _dooku_aid_both_players(state, source_ci, target_id, event_ctx):
    """Count Dooku TS26_1 undeployed: "Choose 2 players.  They each heal 1 damage
    from their base and create a Battle Droid token."

    In a two-player game "choose 2 players" IS every player, so the choice collapses
    (the Chio Fain LAW_48 reading, which this module's Arms Deal TS26_68 already
    uses).  The heal goes through ``resolver._apply_heal`` rather than poking
    ``base.damage``, so the Wolffe SOR_160 "bases can't be healed" lock and the
    ``bases_healed_this_phase`` ledger both see it."""
    from swu.abilities.resolver import _apply_heal
    from swu.engine.actions import _create_token_units
    for ps in list(state.players):
        if ps.base_instance is not None:
            _apply_heal(state, source_ci, ps.base_instance.instance_id, 1)
        _create_token_units(state, ps, "Battle Droid", 1)
    return state


@card_ability("TS26", "1")
def _count_dooku_ts26():
    """TS26_1 — Count Dooku, "Offering Aid" (Leader, cost 7, 6/7, Restore 2).

    Undeployed: "Action [Exhaust]: Choose 2 players.  They each heal 1 damage from
    their base and create a Battle Droid token."
    Deployed:   "On Attack: Create 2 Battle Droid tokens."  (Restore 2 is printed and
    handled by the keyword layer.)

    ⚠️ TS26_1 is ALSO the Battle Droid token unit's registry key — only the two
    side-gated spec kinds below are safe here."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_dooku_aid_both_players)],
            title="Each player heals 1 from their base and creates a Battle Droid",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CreateTokenUnit(token_name="Battle Droid", count=2)],
            deployed_only=True,
        ),
    ]


def _entered_play_this_phase_ids(state, player_id) -> list:
    """The instance_ids of ``player_id``'s units that entered play this phase.

    "friendly units [that] entered play this phase (including tokens and leaders)"
    (Anakin Skywalker TS26_2, Padmé Amidala TS26_4) — exactly
    ``game_memory.units_played_this_phase`` intersected with that player's arenas.
    A created token is in the set because ``_create_token_units`` routes through
    ``_put_unit_in_play``; a DEPLOYED LEADER is in it because
    ``_deploy_leader_into_arena`` records it there too (the same read Hidden's own
    leader reminder uses)."""
    played = getattr(getattr(state, "game_memory", None),
                     "units_played_this_phase", set()) or set()
    ps = state.player_by_id(player_id)
    return [u.instance_id for u in ps.ground_arena + ps.space_arena
            if u.instance_id in played]


def _anakin_shield_an_entrant(state, source_ci, target_id, event_ctx):
    """Anakin Skywalker TS26_2 undeployed: "If 2 or more friendly units entered play
    this phase (including tokens and leaders), give a Shield token to 1 of them."

    A no-target ``CustomEffect`` pushing ``select_token`` rather than a targeted
    ``GiveToken``, because the ≥2 clause is a BOARD gate on the payoff and not on the
    Action: the card's own rules note says the ability "still can be used as an
    action even if fewer than 2 friendly units entered play this phase (but no Shield
    token is created)".  So the gate lives here — failing it pushes nothing and
    prompts for nothing, while the Action itself stays available."""
    from swu.engine.actions import push_select_token
    ids = _entered_play_this_phase_ids(state, source_ci.owner_id)
    if len(ids) < 2:
        return state
    push_select_token(state, source_ci, token_type="Shield", max_targets=1,
                      controller="friendly", restrict_ids=ids, mandatory=True)
    return state


@card_ability("TS26", "2")
def _anakin_skywalker_ts26():
    """TS26_2 — Anakin Skywalker, "Protect Her At All Costs" (Leader, cost 5, 4/5,
    Sentinel).

    Undeployed: "Action [Exhaust]: If 2 or more friendly units entered play this phase
    (including tokens and leaders), give a Shield token to 1 of them."
    Deployed:   "On Attack: Give a Shield token to another friendly unit that entered
    play this phase."

    ⚠️ TS26_2 is ALSO the Clone Trooper token unit's registry key — side-gated kinds
    only."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_anakin_shield_an_entrant)],
            title="Shield a unit that entered play this phase",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Shield", TargetSpec(
                controller="friendly", kind="unit",
                predicates=("not_self", "played_this_phase")))],
            deployed_only=True,
        ),
    ]


def _padme_attack_with_an_entrant(state, source_ci, target_id, event_ctx):
    """Padmé Amidala TS26_4 undeployed: "If 2 or more friendly units entered play this
    phase …, attack with 1 of them, even if it's exhausted.  It can't attack bases for
    this attack."

    The ≥2 gate is on the payoff, not the Action (her rules note, like Anakin's), so
    it lives in the effect fn.  ``allow_exhausted`` is "even if it's exhausted" and
    ``no_base`` is the last sentence; the attack is MANDATORY ("you must attack with a
    unit, if able")."""
    from swu.engine.actions import push_granted_attack
    ids = _entered_play_this_phase_ids(state, source_ci.owner_id)
    if len(ids) < 2:
        return state
    push_granted_attack(state, source_ci,
                        attacker_predicates=["played_this_phase"],
                        allow_exhausted=True, no_base=True)
    return state


def _padme_followup_attack(state, source_ci, target_id, event_ctx):
    """Padmé TS26_4 deployed: "When Attack Ends: You may attack with ANOTHER friendly
    unit that entered play this phase, even if it's exhausted.  It can't attack bases
    for this attack."

    ``exclude_source`` is the "another" (the attack that just ended was hers).
    DOCUMENTED DEVIATION: ``WhenAttackEnds`` fires off ``attack_ended_survivor``, so a
    Padmé who died in the attack she made does not get the follow-up, while her rules
    note says she "does not need to survive the attack in order to attack with another
    unit"."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci,
                        attacker_predicates=["played_this_phase"],
                        allow_exhausted=True, no_base=True,
                        exclude_source=True, optional=True)
    return state


@card_ability("TS26", "4")
def _padme_amidala_ts26():
    """TS26_4 — Padmé Amidala, "Follow My Lead" (Leader, cost 6, 5/6).

    ⚠️ TS26_4 is ALSO the SHIELD TOKEN UPGRADE's registry key, the worse half of the
    collision: a token UPGRADE lives in a host's ``attached_upgrades``, which is
    exactly where a ``GrantedAbility`` is looked for.  Only the side-gated
    Activated/Trigger kinds below are safe."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_padme_attack_with_an_entrant)],
            title="Attack with a unit that entered play this phase",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_padme_followup_attack)],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("TS26", "5")
def _savage_opress_ts26():
    """TS26_5 — Savage Opress, "You Must Have Your Revenge" (Leader, cost 6, 3/7,
    Raid 3 + Overwhelm on the deployed side).

    Undeployed: "Each friendly unit with the most power among friendly units gains
    Overwhelm."
    Deployed:   "Each other friendly unit gains Overwhelm."

    Two auras, and the undeployed one is the interesting half: every other leader
    ConstantAbility is deployed-only FOR FREE because the keyword scans walk the
    arenas and an undeployed leader sits in ``base_zone``.  ``undeployed_only=True``
    inverts that — the spec is skipped by the arena scans and read by
    ``keywords._undeployed_aura_grants`` instead, so the aura is live exactly while he
    is NOT deployed.  The deployed aura needs no flag for the mirror reason.

    "with the most power" is the new ``most_power_among_friendly`` predicate — an
    EACH, so a tie grants Overwhelm to every tied unit, which is the card's own rules
    note.  TS26_5 is not a token number, so ConstantAbility is safe here."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("most_power_among_friendly",)),
            effects=[KeywordGrant("Overwhelm")],
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
            effects=[KeywordGrant("Overwhelm")],
        ),
    ]


def _rex_ready_and_discount(state, source_ci, target_id, event_ctx):
    """Rex TS26_6 deployed: "On Attack: You may ready an exhausted enemy unit.  If you
    do, the next event you play this phase costs 2 resources less."

    ONE targeted ``CustomEffect`` so the ready and its payoff cannot be split (the
    Kylo SHD_141 / "If you do" rule) — the discount is recorded only when a unit was
    really readied."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    unit = res[1]
    if not getattr(unit, "exhausted", False):
        return state
    from swu.engine.actions import note_unit_readied
    note_unit_readied(state, unit)
    unit.exhausted = False
    state.game_memory.pending_play_discounts.append({
        "player_id": source_ci.owner_id,
        "trait": "",
        "amount": 2,
        "units_only": False,
        "card_type": "event",
    })
    return state


@card_ability("TS26", "6")
def _rex_ts26():
    """TS26_6 — Rex, "No Other Option" (Leader, cost 6, 5/6).

    Undeployed: "Action [Exhaust, ready an exhausted enemy unit]: The next event you
    play this phase costs 1 resource less."
    Deployed:   "On Attack: You may ready an exhausted enemy unit.  If you do, the next
    event you play this phase costs 2 resources less."

    "ready an exhausted enemy unit" is a printed COST with no cost spec, so it is a
    LEADING TARGETED ``ReadyCard`` with the payoff behind it and a payability gate
    (the Tomb of Eilram LOF_28 / Director Krennic LAW_8 shape); targeted effect first,
    so the player is prompted exactly once (the Mandalorian SHD_18 rule).  The gate is
    ``ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS(1)``, so the Exhaust is never spent when
    the cost cannot be paid.  The deployed side is the same clause as a "you may",
    which means ONE CustomEffect binding (see ``_rex_ready_and_discount``)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[
                ReadyCard(TargetSpec(controller="enemy", kind="unit",
                                     predicates=("exhausted",))),
                NextPlayDiscount(trait="", amount=1, units_only=False,
                                 card_type="event"),
            ],
            title="Ready an exhausted enemy unit; next event costs 1 less",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS, param=1),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_rex_ready_and_discount,
                target=TargetSpec(controller="enemy", kind="unit",
                                  predicates=("exhausted",)))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _asajj_token_attack(state, source_ci, target_id, event_ctx):
    """Asajj Ventress TS26_7 undeployed: "Action [Exhaust]: Attack with a token unit.
    It gets +1/+0 for this attack." """
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1,
                        attacker_predicates=["token_unit"])
    return state


@card_ability("TS26", "7")
def _asajj_ventress_ts26():
    """TS26_7 — Asajj Ventress, "Ambitious Apprentice" (Leader, cost 5, 3/5, Hidden).

    Undeployed: "Action [Exhaust]: Attack with a token unit.  It gets +1/+0 for this
    attack."
    Deployed:   "While you've attacked with a token unit this phase, this unit gets
    +2/+0."

    The deployed clause is a SELF ``ConstantAbility`` (arena-scanned, so deployed-only
    for free) gated by the new ``CONTROLLER_ATTACKED_TOKEN_UNIT_THIS_PHASE`` — which
    needs its own ledger because a token that attacked and died is unreachable by
    ``find_instance``, unlike every other "attacked this phase" atom's subject.  Her
    printed Hidden ("can't be attacked if she was deployed this phase") now works too:
    a deployed leader is recorded in ``units_played_this_phase``, which is what
    ``_hidden_protected`` reads."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_asajj_token_attack)],
            title="Attack with a token unit (+1/+0)",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=2, hp=0)],
            condition=ConditionCheck(
                Condition.CONTROLLER_ATTACKED_TOKEN_UNIT_THIS_PHASE),
        ),
    ]


def _first_battle_memorial_tokens(state, source_ci, target_id, event_ctx):
    """First Battle Memorial TS26_9: "Epic Action: For each friendly leader unit, give
    an Experience token to a unit."

    ``push_select_token(allow_repeats=True)`` (Elzar Mann ASH_224) — "a unit" is
    re-chosen for each leader unit, so the same unit may take several, which the
    default distinct-picks loop could not say.  ``mandatory`` because the card is not
    a "you may"; ``controller="any"`` because it says "a unit", not "a friendly
    unit"."""
    from swu.engine.actions import push_select_token
    from swu.abilities.resolver import _is_leader_unit
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena if _is_leader_unit(u))
    if n <= 0:
        return state
    push_select_token(state, source_ci, token_type="Experience", max_targets=n,
                      controller="any", mandatory=True, allow_repeats=True)
    return state


@card_ability("TS26", "9")
def _first_battle_memorial():
    """TS26_9 — First Battle Memorial (Base, 27 HP): "Epic Action: For each friendly
    leader unit, give an Experience token to a unit."

    Gated on ``CONTROLLER_HAS_LEADER_UNIT`` so the once-per-GAME Epic Action is never
    burnt for zero tokens (the TS26_11/12 base convention)."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_first_battle_memorial_tokens)],
        title="Give an Experience token per friendly leader unit",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_LEADER_UNIT),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:07 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _dookus_palace_play(state, source_ci, target_id, event_ctx):
    """Dooku's Palace TS26_10: "Epic Action: Play a unit from your hand.  It costs 1
    resource less for each friendly leader unit."

    ``push_play_from_hand(cost_reduction=<leader units>)`` — the reduction is read at
    resolution, and the SAME count the ability's availability gate uses (``_is_leader_
    unit``, shared with ``CostReduction.per_friendly_leader_unit``), so the offer and
    the price cannot disagree."""
    from swu.engine.actions import push_play_from_hand
    from swu.abilities.resolver import _is_leader_unit
    ps = state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena if _is_leader_unit(u))
    push_play_from_hand(state, source_ci, cost_reduction=n)
    return state


@card_ability("TS26", "10")
def _dookus_palace():
    """TS26_10 — Dooku's Palace (Base, 27 HP): "Epic Action: Play a unit from your
    hand.  It costs 1 resource less for each friendly leader unit."

    The gate is ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND`` at the card's own DYNAMIC
    reduction (``"per_friendly_leader_unit"``), so the once-per-GAME Epic Action is
    offered exactly when a play is really affordable — a fixed 0 would hide it in
    precisely the case where the discount is what makes the play possible."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_dookus_palace_play)],
        title="Play a unit from hand (1 less per friendly leader unit)",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                                 param=(None, "per_friendly_leader_unit")),
    )


@card_ability("TS26", "13")
def _darth_sidious_ts26():
    """TS26_13 — Darth Sidious, "Under a Cloak of Darkness" (Unit, cost 6, 4/6,
    Hidden): "Each other friendly Separatist unit gets +1/+0.  When a non-token unit
    is defeated: Create a Battle Droid token."

    The observer is unqualified — EITHER player's non-token unit dying feeds him —
    and ``non_token`` is what stops the Battle Droids he makes from replicating
    themselves (the Bo-Katan's Gauntlet ASH_63 reason for that predicate)."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Separatist",), predicates=("not_self",)),
            effects=[StatBonus(power=1, hp=0)],
        ),
        TriggerAbility(
            trigger=WhenUnitDefeated(filter=TargetSpec(
                controller="any", kind="unit", predicates=("non_token",))),
            effects=[CreateTokenUnit(token_name="Battle Droid", count=1)],
        ),
    ]


@card_ability("TS26", "16")
def _king_katuunko():
    """TS26_16 — King Katuunko, "Great King of Toydaria" (Unit, cost 2, 2/4): "When
    Played: All units (including enemy units) gain Restore 1 for this phase."

    ``fixed=EACH_IN_PLAY`` is exactly "all units", the parenthetical included."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GrantKeyword("Restore", value=1,
                              target=TargetSpec(kind="unit", fixed=EACH_IN_PLAY),
                              duration=Duration.THIS_PHASE)],
    )


def _jendirian_valley_search(state, source_ci, target_id, event_ctx):
    """Jendirian Valley TS26_18: "When Played: Search the top 8 cards of your deck for
    a card and resource it."

    The new ``deck_search`` disposition ``"resource"`` — the selected card goes
    straight into the resource row face down and EXHAUSTED, which is both the CR
    default for a resource put into play by an effect and the card's own rules note
    ("Resources enter play exhausted").  Any card qualifies ("for a card"), and the
    search is mandatory-if-able (``up_to=False``)."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=lambda cd: True,
                     up_to=False, window=8, disposition="resource")
    return state


@card_ability("TS26", "18")
def _jendirian_valley():
    """TS26_18 — Jendirian Valley, "Refugee Freighter" (Unit, cost 4, 1/5, Restore 1):
    "When Played: Search the top 8 cards of your deck for a card and resource it.  (Put
    the other cards on the bottom of your deck in a random order.)" """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jendirian_valley_search)],
    )


@card_ability("TS26", "20")
def _501st_veteran():
    """TS26_20 — 501st Veteran (Unit, cost 2, 0/4, Grit + Raid 1): "While this unit is
    undamaged it gains Sentinel."

    The conditional SELF grant (Hunting Nexu SHD_168 / Protector SHD_247), which is
    also what makes sanitiser rule 2 strip the printed Sentinel — so a damaged 501st
    Veteran really loses it, while Grit and Raid (its own leading bar lines) stay."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel")],
        condition=ConditionCheck(Condition.SOURCE_UNDAMAGED),
    )


def _darksaber_ready_host(state, source_ci, target_id, event_ctx):
    """The Darksaber TS26_22: "When Played: If there are 4 or more different keywords
    among friendly units, ready attached unit."

    The UNION of every friendly unit's keyword names — a per-unit
    ``distinct_keyword_count`` cannot answer "among friendly units", hence
    ``keywords.distinct_keyword_names``.  The card's own rules note ("Multiple
    instances of the same keyword aren't considered different keywords, including for
    stacking keywords like Raid X") is the name-normalisation that helper already
    does.  The host comes from the standard ``event_ctx["attached_to_id"]`` an upgrade
    play threads, and the count is taken AFTER attachment, so the Sentinel this
    upgrade itself confers is part of it."""
    from swu.engine.keywords import distinct_keyword_names
    from swu.engine.actions import note_unit_readied
    host_id = event_ctx.get("attached_to_id")
    if not host_id:
        return state
    res = state.find_instance(host_id)
    if res is None:
        return state
    ps = state.player_by_id(res[0].player_id)
    names: set = set()
    for u in ps.ground_arena + ps.space_arena:
        names |= distinct_keyword_names(state, u)
    if len(names) < 4:
        return state
    host = res[1]
    if getattr(host, "exhausted", False):
        note_unit_readied(state, host)
        host.exhausted = False
    return state


@card_ability("TS26", "22")
def _the_darksaber_ts26():
    """TS26_22 — The Darksaber, "Only the Strongest Shall Rule" (Upgrade, cost 4,
    +2/+2): "Attach to a non-Vehicle unit.  Attached unit gains Sentinel.  When Played:
    If there are 4 or more different keywords among friendly units, ready attached
    unit."

    "Attach to a non-Vehicle unit" is parsed straight off the printed text by
    ``_upgrade_target_spec``; the grant is the ordinary upgrade-SELF ConstantAbility
    conferral (Grievous's Wheel Bike TWI_236)."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_darksaber_ready_host)],
        ),
    ]


def _almec_buff_and_exhaust(state, source_ci, target_id, event_ctx):
    """Prime Minister Almec TS26_28: "When Played: Give a friendly unit +2/+2 for this
    phase.  Exhaust each enemy unit in its arena with less power than it."

    ONE targeted ``CustomEffect`` (the Kylo SHD_141 rule): the buff and the sweep must
    name the same unit, and the sweep is measured AFTER the buff lands — the card's
    own rules note says "Abilities that refer to a card's power include temporary
    modifiers", which is exactly what makes the +2 part of the comparison."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, unit = res
    from swu.engine.state import Modifier
    from swu.engine.actions import compute_power
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id("almec"),
        target_instance_id=unit.instance_id,
        source_instance_id=source_ci.instance_id,
        kind="stats",
        value={"power": 2, "hp": 2},
        duration="this_phase",
    ))
    arena = unit.arena()
    mine = compute_power(state, unit)
    for ps in state.players:
        if ps.player_id == holder.player_id:
            continue
        for enemy in list(ps.ground_arena) + list(ps.space_arena):
            if enemy.arena() != arena or getattr(enemy, "exhausted", False):
                continue
            if compute_power(state, enemy) < mine:
                enemy.exhausted = True
    return state


@card_ability("TS26", "28")
def _prime_minister_almec():
    """TS26_28 — Prime Minister Almec, "Scheming Populist" (Unit, cost 4, 2/4,
    Saboteur): "When Played: Give a friendly unit +2/+2 for this phase.  Exhaust each
    enemy unit in its arena with less power than it." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_almec_buff_and_exhaust,
            target=TargetSpec(controller="friendly", kind="unit"))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:08 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _maul_unit_granted_attack(state, source_ci, target_id, event_ctx):
    """Maul TS26_30: "When Played: You may attack with another unit." """
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True, exclude_source=True)
    return state


@card_ability("TS26", "30")
def _maul_one_last_lesson():
    """TS26_30 — Maul, "One Last Lesson" (Unit, cost 4, 5/4, Sentinel): "When Played:
    You may attack with another unit."

    The trigger itself is MANDATORY: the "you may" is the granted attack's own
    always-offered ``DeclineGrantedAttack``, so the player is prompted exactly once
    (an optional trigger on top of it would ask twice for one choice — the Kalani
    TWI_85 note)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_maul_unit_granted_attack)],
    )


def _chaotic_diversion_ready(state, source_ci, target_id, event_ctx):
    """Chaotic Diversion TS26_31, first clause: "Ready an enemy unit.  If you do, it
    can't attack your base or units you control for this phase."

    ONE ``CustomEffect`` so the ready and its rider cannot be split.  In a two-player
    game "your base or units you control" is EVERYTHING the readied unit could legally
    attack, so the restriction collapses to the blanket ``cannot_attack`` modifier
    (Malevolence TWI_39) — a documented two-player collapse, and the reason the card
    is a trick rather than a gift."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    unit = res[1]
    from swu.engine.state import Modifier
    from swu.engine.actions import note_unit_readied
    if getattr(unit, "exhausted", False):
        note_unit_readied(state, unit)
        unit.exhausted = False
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id("chaotic"),
        target_instance_id=unit.instance_id,
        source_instance_id=source_ci.instance_id,
        kind="cannot_attack",
        value={},
        duration="this_phase",
    ))
    return state


@card_ability("TS26", "31")
def _chaotic_diversion():
    """TS26_31 — Chaotic Diversion (Event, Tactic Trick, cost 1): "Ready an enemy unit.
    If you do, it can't attack your base or units you control for this phase.  Give a
    Shield token to a friendly unit."

    TWO single-effect ``EventAbility``s rather than two effects (the Barrel Roll
    JTL_228 / Beguile SEC_233 rule) — ``_resolve_event_ability`` walks them in order,
    so each clause gets its own clean prompt and one fizzling does not eat the
    other's."""
    return [
        EventAbility(effects=[CustomEffect(
            fn=_chaotic_diversion_ready,
            target=TargetSpec(controller="enemy", kind="unit"))]),
        EventAbility(effects=[GiveToken(
            "Shield", TargetSpec(controller="friendly", kind="unit"))]),
    ]


def _ahsoka_sabers_shield_and_discount(state, source_ci, target_id, event_ctx):
    """Ahsoka's Lightsabers TS26_35: "You may give a Shield token to an enemy unit.  If
    you do, the next event you play this phase costs 2 resources less."

    ONE targeted ``CustomEffect`` binding the gift to its payoff.  ``source_ci`` is the
    HOST (a ``GrantedAbility`` resolves from the host), so the discount goes to
    whoever controls the unit — and it survives both the upgrade and the host leaving
    play, exactly as the card's rules note says, because it is a pending
    ``game_memory`` entry rather than anything read off the source."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, unit = res
    from swu.engine.tokens import attach_token
    attach_token(state, holder, unit, "Shield")
    state.game_memory.pending_play_discounts.append({
        "player_id": source_ci.owner_id,
        "trait": "",
        "amount": 2,
        "units_only": False,
        "card_type": "event",
    })
    return state


def _ahsoka_sabers_clause():
    return CustomEffect(fn=_ahsoka_sabers_shield_and_discount,
                        target=TargetSpec(controller="enemy", kind="unit"))


@card_ability("TS26", "35")
def _ahsokas_lightsabers():
    """TS26_35 — Ahsoka's Lightsabers, "Don't Hurt Them" (Upgrade, cost 4, +2/+3):
    "Attach to a non-Vehicle unit.  Attached unit gains: 'On Attack/When Defeated: You
    may give a Shield token to an enemy unit.  If you do, the next event you play this
    phase costs 2 resources less.'"

    Two ``GrantedAbility`` wrappers over one shared clause — the wrapper is what makes
    it the HOST's ability (and what keeps the When Defeated collectable off the
    detached upgrade when the host dies)."""
    return [
        GrantedAbility(ability=TriggerAbility(
            trigger=OnAttack(), effects=[_ahsoka_sabers_clause()], optional=True)),
        GrantedAbility(ability=TriggerAbility(
            trigger=WhenDefeated(), effects=[_ahsoka_sabers_clause()], optional=True)),
    ]


def _solar_sailer_clause():
    return GiveToken("Experience", TargetSpec(
        controller="friendly", kind="unit", traits=("Separatist",),
        predicates=("not_self",)))


@card_ability("TS26", "38")
def _dookus_solar_sailer():
    """TS26_38 — Dooku's Solar Sailer, "Beautiful and Expensive" (Unit, cost 3, 2/4):
    "When Played/On Attack: If a base was healed this phase, give an Experience token
    to another Separatist unit."

    ONE clause under BOTH triggers (the Captain Rex SEC_48 shape).  The gate is the new
    ``ANY_BASE_HEALED_THIS_PHASE`` over ``game_memory.bases_healed_this_phase``, fed by
    ``actions.note_base_healed`` at every base-heal site — Restore included, which is
    how this card is meant to be turned on."""
    gate = ConditionCheck(Condition.ANY_BASE_HEALED_THIS_PHASE)
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[_solar_sailer_clause()], condition=gate),
        TriggerAbility(trigger=OnAttack(),
                       effects=[_solar_sailer_clause()], condition=gate),
    ]


@card_ability("TS26", "40")
def _obi_wan_kenobi_ts26():
    """TS26_40 — Obi-Wan Kenobi, "Steadfast Knight" (Unit, cost 3, 4/4): "Other
    friendly Republic units gain Restore 1."

    He does NOT have Restore himself — sanitiser rule 1 already strips the printed bar
    the upstream data gives him, because his only textual mention is the grant."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          traits=("Republic",), predicates=("not_self",)),
        effects=[KeywordGrant("Restore", value=1)],
    )


@card_ability("TS26", "41")
def _twilight_ts26():
    """TS26_41 — Twilight, "Escaping Malevolence" (Unit, cost 3, 3/4): "When Played: If
    there are 5 or more cards in your discard pile, heal 3 damage from your base."

    The gate is the new ``CONTROLLER_DISCARD_SIZE_MIN(5)``, read on collection so the
    trigger simply is not collected below the threshold."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[Heal(3, TargetSpec(controller="friendly", kind="base"))],
        condition=ConditionCheck(Condition.CONTROLLER_DISCARD_SIZE_MIN, param=5),
    )


def _relief_frigate_heal_others(state, source_ci, target_id, event_ctx):
    """Relief Frigate TS26_42: "When Played: Choose a base.  Heal 3 damage from each
    OTHER base."

    The chosen base is the one EXCLUDED, so in two-player this is "choose which base
    stays damaged".  Routed through ``resolver._apply_heal`` so the Wolffe SOR_160 lock
    and the ``bases_healed_this_phase`` ledger both apply."""
    from swu.abilities.resolver import _apply_heal
    for ps in list(state.players):
        base = ps.base_instance
        if base is None or base.instance_id == target_id:
            continue
        _apply_heal(state, source_ci, base.instance_id, 3)
    return state


@card_ability("TS26", "42")
def _relief_frigate():
    """TS26_42 — Relief Frigate (Unit, cost 5, 3/7): "When Played: Choose a base.  Heal
    3 damage from each other base." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_relief_frigate_heal_others,
            target=TargetSpec(controller="any", kind="base"))],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:09 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _take_cover_heal_and_shield(state, source_ci, target_id, event_ctx):
    """Take Cover TS26_47: "Heal up to 3 damage from a unit and give a Shield token
    to it."

    ONE targeted ``CustomEffect`` (the Kylo SHD_141 rule) so the heal and the Shield
    cannot name different units — a ``Heal`` + ``GiveToken`` pair would prompt twice.
    "Heal up to 3" heals as much as possible, the standing convention (Satine SEC_5):
    no choose-a-magnitude decision exists, and healing less is never better.  The
    Shield lands even on an undamaged unit, which is why the target is unfiltered."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, unit = res
    from swu.abilities.resolver import _apply_heal
    from swu.engine.tokens import attach_token
    state = _apply_heal(state, source_ci, target_id, 3)
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, unit = res
    attach_token(state, ps, unit, "Shield")
    return state


@card_ability("TS26", "47")
def _take_cover():
    """TS26_47 — Take Cover (Event, Tactic, cost 3): "This event costs 1 resource less
    to play for each friendly leader unit.  Heal up to 3 damage from a unit and give a
    Shield token to it."

    ``CostReduction(per_friendly_leader_unit=True)`` is Take Action TS26_71's arm
    verbatim, so the two cards' readings of "leader unit" cannot drift."""
    return [
        CostReduction(amount=1, per_friendly_leader_unit=True),
        EventAbility(effects=[CustomEffect(
            fn=_take_cover_heal_and_shield,
            target=TargetSpec(controller="any", kind="unit"))]),
    ]


def _separatist_council_choose(state, source_ci, target_id, event_ctx):
    """Offer only the modes that can do something (Separatist Council TS26_49).

    Mode 2 ("Give 2 Experience tokens to a Battle Droid token") is dead with no
    Battle Droid token on the board, so it is filtered out at push time — the Cyborg
    Mech ASH_147 rule.  Mode 1 always creates a token, so it is never dead."""
    from swu.engine.actions import push_choose_modal
    from swu.cards.models import TokenUnit
    droid = any(
        isinstance(ci.card_def, TokenUnit)
        and ci.card_def.display_name == "Battle Droid"
        for ps in state.players
        for ci in ps.ground_arena + ps.space_arena
    )
    push_choose_modal(state, source_ci,
                      option_indices=[2, 3] if droid else [2], pick=1)
    return state


@card_ability("TS26", "49")
def _separatist_council():
    """TS26_49 — Separatist Council, "Quarrelsome Holdouts" (Unit, cost 4, 2/6):
    "When Played/On Attack: Choose one: Create a Battle Droid token. / Give 2
    Experience tokens to a Battle Droid token."

    ``push_choose_modal(pick=1)`` over two option specs, which are ``EventAbility``
    because this is a UNIT card and a ``TriggerAbility`` option would be collected for
    real (the Lightmaker SEC_207 rule).  "A Battle Droid token" is unqualified, so
    either player's token is a legal recipient (``controller="any"``)."""
    push = [CustomEffect(fn=_separatist_council_choose)]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(push)),
        TriggerAbility(trigger=OnAttack(), effects=list(push)),
        EventAbility(effects=[CreateTokenUnit(token_name="Battle Droid", count=1)]),
        EventAbility(effects=[GiveToken(
            "Experience",
            TargetSpec(controller="any", kind="unit",
                       names=("Battle Droid",), predicates=("token_unit",)),
            count=2)]),
    ]


@card_ability("TS26", "50")
def _general_grievous_ts26():
    """TS26_50 — General Grievous, "Crush Them!" (Unit, cost 5, printed 0/0): "This
    unit gets +1/+1 for each resource you control.  While this unit is undamaged, he
    gains Sentinel."

    ``StatBonus(count="controller_resources")`` is 97th Legion SOR_118's arm (which
    scales BOTH halves), and the Sentinel is the conditional SELF grant (501st Veteran
    TS26_20) — which is also what makes sanitiser rule 2 strip his printed Sentinel,
    so a damaged Grievous really loses it."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=1, count="controller_resources")],
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel")],
            condition=ConditionCheck(Condition.SOURCE_UNDAMAGED),
        ),
    ]


def _lom_pyke_offer(state, source_ci, target_id, event_ctx):
    """Lom Pyke TS26_51: "In player order, each opponent may heal 5 damage from their
    base.  For each player that does, give 2 Experience tokens to a unit."

    In two player there is exactly one opponent, so "in player order" collapses to a
    single offer.  It is a real binary choice for them — a damaged base is worth more
    than the two Experience it concedes, an undamaged one is not — so it rides the
    ``say_no`` decider shift rather than collapsing to an optimal default.  The
    payoff is pushed by the ACCEPT arm after the pop (the pop-then-act rule)."""
    from swu.engine.actions import push_say_no
    push_say_no(state, source_ci, None, effect="opponent_heal_base",
                heal_amount=5, then_experience=2)
    return state


@card_ability("TS26", "51")
def _lom_pyke():
    """TS26_51 — Lom Pyke, "Making a Withdrawal" (Unit, Underworld, cost 5, 5/5)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_lom_pyke_offer)],
    )


@card_ability("TS26", "52")
def _sith_traditions():
    """TS26_52 — Sith Traditions (Upgrade, Learned Sith, cost 2): "Attach to a
    non-Vehicle unit.  Attached unit gains: 'On Attack: Give an Experience token to
    this unit.' and 'When Defeated: Give an Experience token to a friendly unit.'"

    Two ``GrantedAbility`` wrappers (Ahsoka's Lightsabers TS26_35's shape) — the
    wrapper is what makes each the HOST's ability, and what keeps the When Defeated
    collectable off the DETACHED upgrade once the host dies.  "This unit" is therefore
    ``fixed=SELF``, which resolves to the host."""
    return [
        GrantedAbility(ability=TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(fixed=SELF))])),
        GrantedAbility(ability=TriggerAbility(
            trigger=WhenDefeated(),
            effects=[GiveToken("Experience", TargetSpec(
                controller="friendly", kind="unit"))])),
    ]


def _coruscanti_spy_heal(state, source_ci, target_id, event_ctx):
    """One "heal 2 from a base" step of Coruscanti Spy's "any number of bases"."""
    if not target_id:
        return state
    from swu.abilities.resolver import _apply_heal
    state = _apply_heal(state, source_ci, target_id, 2)
    seen = event_ctx.setdefault("excluded_target_ids", set())
    seen.add(target_id)
    return state


@card_ability("TS26", "53")
def _coruscanti_spy():
    """TS26_53 — Coruscanti Spy (Unit, Official, cost 1, 0/2, Raid 2): "When Played:
    Heal 2 damage from each of any number of bases."

    "Any number of bases" is at most two, so it is two optional targeted steps over
    the accumulating ``excludes_event_targets`` set (Rancor Keeper ASH_32 / Attack
    Pattern Delta SOR_106) — no select-N decision needed.  ``damaged`` on both keeps a
    fully-healed base out of the offer, so neither step is ever a dead prompt."""
    base_spec = TargetSpec(controller="any", kind="base", optional=True,
                           predicates=("damaged", "excludes_event_targets"))
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_coruscanti_spy_heal, target=base_spec),
                 CustomEffect(fn=_coruscanti_spy_heal, target=base_spec)],
    )


def _wartime_mercenaries_gift(state, source_ci, target_id, event_ctx):
    """Wartime Mercenaries TS26_54: "When Defeated: An opponent may give an Experience
    token to a unit."

    ``push_select_token(decider_id=<opponent>)`` — the collector-decider override
    (Sabine Wren ASH_6), left NON-mandatory so the always-legal ``FinishSelectToken``
    carries the printed "may".  ``controller="any"`` is read from the SOURCE's
    perspective, and the clause says plain "a unit", so the opponent may hand the
    token to either side."""
    from swu.engine.actions import push_select_token
    opp_id = next(p.player_id for p in state.players
                  if p.player_id != source_ci.owner_id)
    push_select_token(state, source_ci, token_type="Experience", max_targets=1,
                      controller="any", decider_id=opp_id)
    return state


@card_ability("TS26", "54")
def _wartime_mercenaries():
    """TS26_54 — Wartime Mercenaries (Unit, Trooper, cost 4, 5/5)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_wartime_mercenaries_gift)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:10 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _jedi_general_clones(state, source_ci, target_id, event_ctx):
    """Jedi General TS26_55: "For each Republic leader you control (as a leader or
    unit), create a Clone Trooper token and give an Experience token to it."

    "As a leader or unit" is the whole board a leader card can occupy — the base
    zone while undeployed, an arena once deployed — so the scan covers both, and the
    Republic test goes through ``traits.has_trait`` so a granted trait counts.  Each
    token is tokened individually because ``_create_token_units`` RETURNS the
    instances it made (the Buy Time ASH_91 seam), so "give an Experience token to
    IT" needs no target choice."""
    from swu.cards.models import Leader
    from swu.engine.traits import has_trait
    from swu.engine.actions import _create_token_units
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    leaders = [ci for ci in (ps.base_zone + ps.ground_arena + ps.space_arena)
               if isinstance(ci.card_def, Leader) and has_trait(state, ci, "Republic")]
    for _ldr in leaders:
        made = _create_token_units(state, ps, "Clone Trooper", 1)
        for token in made:
            attach_token(state, ps, token, "Experience")
    return state


@card_ability("TS26", "55")
def _jedi_general():
    """TS26_55 — Jedi General (Unit, Force Jedi Republic, cost 5, 2/3, Ambush)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jedi_general_clones)],
    )


def _brothers_attacks(state, source_ci, target_id, event_ctx):
    """Brothers TS26_59: "Attack with up to 2 <uq> units (one at a time).  Prevent
    all combat damage that would be dealt to each of them for these attacks."

    ``repeat`` + ``repeat_max=2`` is the Headhunting SHD_145 loop; ``optional`` is
    the "up to" (the decision's own decline), and the ctx carries forward, so each
    chosen attacker gets the prevention.  ``attacker_predicates=["unique"]`` needed
    the ``unique`` arm added to ``actions._attacker_matches_predicates`` as well as
    the resolver's — an unknown predicate there is IGNORED, not failed."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True, repeat=True, repeat_max=2,
                        attacker_predicates=["unique"],
                        attacker_damage_prevention=True,
                        attacker_prevention_combat_only=True)
    return state


@card_ability("TS26", "59")
def _brothers():
    """TS26_59 — Brothers (Event, Innate, cost 3)."""
    return EventAbility(effects=[CustomEffect(fn=_brothers_attacks)])


def _take_charge_tokens(state, source_ci, target_id, event_ctx):
    """Take Charge TS26_60: "Give an Experience token to each of up to 3 units."."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Experience", max_targets=3,
                      controller="any")
    return state


@card_ability("TS26", "60")
def _take_charge():
    """TS26_60 — Take Charge (Event, Tactic, cost 3): "This event costs 1 resource
    less to play for each friendly leader unit.  Give an Experience token to each of
    up to 3 units."

    The discount is Take Action TS26_71's arm; the gift is the plain select-up-to-N
    loop, whose always-legal ``FinishSelectToken`` IS the "up to"."""
    return [
        CostReduction(amount=1, per_friendly_leader_unit=True),
        EventAbility(effects=[CustomEffect(fn=_take_charge_tokens)]),
    ]


def _encircle_choose_captor(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly captor + its arena (Take Captive SHD_131)."""
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


def _encircle_capture(state, source_ci, target_id, event_ctx):
    """Capture the chosen enemy unit under the recorded captor."""
    captor = event_ctx.get("captor_id")
    if captor is None or target_id is None:
        return state
    from swu.engine.actions import _apply_capture
    _apply_capture(state, captor, target_id)
    return state


@card_ability("TS26", "61")
def _encircle():
    """TS26_61 — Encircle (Event, Tactic, cost 5): "This event costs 1 resource less
    to play for each friendly unit.  A friendly unit captures an enemy non-leader
    unit in the same arena."

    The capture half is Take Captive SHD_131 verbatim (two dependent
    ``CustomEffect.target``s sharing the resolve_effects ``event_ctx``).  The
    discount is the new trait-blind ``CostReduction(per_friendly_units=True)`` —
    which is also what makes the card's own tension work: the board that pays for it
    is the board that supplies the captor."""
    return [
        CostReduction(amount=1, per_friendly_units=True),
        EventAbility(effects=[
            CustomEffect(fn=_encircle_choose_captor,
                         target=TargetSpec(controller="friendly", kind="unit")),
            CustomEffect(fn=_encircle_capture,
                         target=TargetSpec(
                             controller="enemy", kind="unit",
                             predicates=("non_leader", "same_arena_as_event"))),
        ]),
    ]


def _dc17s_ready_host(state, source_ci, target_id, event_ctx):
    """Rex's DC-17s TS26_63: ready the host and charge the once-per-round use.

    The charge is spent HERE rather than on collection so it is only paid when the
    ability really runs (the Toro Calican SHD_239 ``{iid}:trig`` limiter)."""
    from swu.engine.actions import note_unit_readied
    if source_ci.exhausted:
        note_unit_readied(state, source_ci)
        source_ci.exhausted = False
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("TS26", "63")
def _rexs_dc17s():
    """TS26_63 — Rex's DC-17s (Upgrade, Item Weapon, cost 3): "Attach to a
    non-Vehicle unit.  Attached unit gains: 'When an enemy unit readies during the
    action phase: Ready this unit.  Use this ability only once each round.'"

    ``GrantedAbility`` so the trigger resolves FROM the host ("this unit"), over the
    ``WhenUnitReadies`` observer widened two ways: ``controller="enemy"`` (it was
    strictly self-referential for In Debt to Crimson Dawn JTL_192) and
    ``action_phase=True``, which reads the phase recorded WITH the ledger entry — the
    regroup mass-ready is drained after the rollover into ACTION, so a drain-time
    phase read would let every regroup ready through and burn the round's use."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenUnitReadies(controller="enemy", action_phase=True),
        effects=[CustomEffect(fn=_dc17s_ready_host)],
        condition=ConditionCheck(
            Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    ))


@card_ability("TS26", "75")
def _jango_fett_ts26():
    """TS26_75 — Jango Fett, "Concealing the Conspiracy" (Unit, Bounty Hunter
    Separatist, cost 5, 5/5): "While an enemy unit has attacked your base this phase,
    this unit gains Ambush.  On Attack: Give an enemy unit −3/−0 for this phase."

    The conditional SELF grant over ``CONTROLLER_BASE_ATTACKED_THIS_PHASE`` (Greef
    Karga ASH_119's atom, keyed by base OWNER and written at the DECLARE step) — and
    it is that registration which makes sanitiser rule 2 strip his printed Ambush, so
    an untouched base really leaves him without it."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Ambush")],
            condition=ConditionCheck(Condition.CONTROLLER_BASE_ATTACKED_THIS_PHASE),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=-3, hp=0,
                                 target=TargetSpec(controller="enemy", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
        ),
    ]


def _wartime_profiteer_ready(state, source_ci, target_id, event_ctx):
    """Wartime Profiteer TS26_76: "When Defeated: Each opponent may ready a
    resource."

    Resources are fungible and not targetable cards, so the pick is automatic (the
    K-2SO SOR_145 convention), and readying one is pure upside for the decider — so
    the printed "may" collapses to taking it (the Foresight TWI_68 reading).  An
    exhausted resource is chosen, since readying a ready one is a no-op."""
    for ps in state.players:
        if ps.player_id == source_ci.owner_id:
            continue
        for r in ps.resources:
            if r.exhausted:
                r.exhausted = False
                break
    return state


@card_ability("TS26", "76")
def _wartime_profiteer():
    """TS26_76 — Wartime Profiteer (Unit, Underworld, cost 2, 3/3)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_wartime_profiteer_ready)],
    )


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:11 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _droideka_pay_for_tokens(state, source_ci, target_id, event_ctx):
    """Deployed Droideka TS26_77: "You may pay 2 resources.  If you do, give an
    Experience token and a Shield token to this unit."

    The cost and its payoff in ONE effect so an unpaid cost can never apply the
    payoff (the Boba Fett LAW_214 idiom); the trigger's ``optional`` carries the
    "may" and the ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` gate means it is never
    offered unaffordable."""
    from swu.engine.actions import _exhaust_resources
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 2:
        return state
    _exhaust_resources(ps, 2)
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    holder, unit = res
    attach_token(state, holder, unit, "Experience")
    attach_token(state, holder, unit, "Shield")
    return state


@card_ability("TS26", "77")
def _deployed_droideka():
    """TS26_77 — Deployed Droideka (Unit, Droid Separatist, cost 4, 4/3, Ambush)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_droideka_pay_for_tokens)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=2),
    )


@card_ability("TS26", "78")
def _barriss_offee_ts26():
    """TS26_78 — Barriss Offee, "Repaying the Debt" (Unit, Force Jedi Republic,
    cost 5, 5/6, Hidden): "When an enemy unit attacks: You may give an Experience
    token to that unit."

    ``WhenUnitAttacks`` is the OBSERVER form (Jedi Temple LOF_23) — ``OnAttack``
    fires only for the attacking unit itself, and this card watches someone else's
    attack.  "That unit" is ``fixed=ATTACKER``, which resolves off the
    ``attacker_id`` all three attack-declare fire sites thread.

    ⚠ The token goes to the ENEMY attacker, which reads like a drawback; it is
    implemented as printed, and the trigger's ``optional`` means it is never
    forced."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(
            filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[GiveToken("Experience", TargetSpec(fixed=ATTACKER))],
        optional=True,
    )


@card_ability("TS26", "81")
def _mislead():
    """TS26_81 — Mislead (Event, Trick, cost 2): "Give a Shield token to a unit.
    Give a unit −3/−0 for this phase."

    Two INDEPENDENT targeted effects — two prompts, deliberately unbound: the card
    names "a unit" twice, so shielding one and debuffing another is legal (Fervor
    TS26_72's reading)."""
    return EventAbility(effects=[
        GiveToken("Shield", TargetSpec(controller="any", kind="unit")),
        ModifyStats(power=-3, hp=0,
                    target=TargetSpec(controller="any", kind="unit"),
                    duration=Duration.THIS_PHASE),
    ])


def _evade_arrest_exhaust(state, source_ci, target_id, event_ctx):
    """Evade Arrest TS26_82: "Exhaust any number of non-<uq> units."

    "Any number" is the Kazuda Xiono JTL_18 idiom — ``max_targets`` = the size of
    the eligible pool, with the always-legal ``FinishSelectToken`` ending it early
    (including at zero).  ``ready_only`` is not a filter this decision has, but the
    ``exhaust`` payoff honours Protection and an already-exhausted unit is simply a
    wasted pick, so the pool is the printed one."""
    from swu.engine.actions import push_select_token
    pool = sum(1 for ps in state.players
               for ci in ps.ground_arena + ps.space_arena
               if not getattr(ci.card_def, "is_unique", False))
    if pool <= 0:
        return state
    push_select_token(state, source_ci, token_type=None, max_targets=pool,
                      controller="any", predicates=["non_unique"], exhaust=True)
    return state


@card_ability("TS26", "82")
def _evade_arrest():
    """TS26_82 — Evade Arrest (Event, Trick, cost 3)."""
    return EventAbility(effects=[CustomEffect(fn=_evade_arrest_exhaust)])


def _take_aim_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        grant_keywords=["Saboteur"])
    return state


@card_ability("TS26", "83")
def _take_aim():
    """TS26_83 — Take Aim (Event, Tactic, cost 3): "This event costs 1 resource less
    to play for each friendly leader unit.  Attack with a unit.  It gets +2/+0 and
    gains Saboteur for this attack."

    Take Action TS26_71's discount over the plain granted attack; Saboteur is the
    keyword engine, granted for the attack by the decision's own
    ``grant_keywords``."""
    return [
        CostReduction(amount=1, per_friendly_leader_unit=True),
        EventAbility(effects=[CustomEffect(fn=_take_aim_attack)]),
    ]


def _fearless_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, bonus_per_defending_player_unit=1)
    return state


@card_ability("TS26", "84")
def _fearless_attack_card():
    """TS26_84 — Fearless Attack (Event, Tactic, cost 4): "Attack with a unit.  It
    gets +1/+0 for this attack for each unit controlled by the defending player."

    The new ``bonus_per_defending_player_unit`` — the arena-blind sibling of
    Masterstroke ASH_234's ``bonus_per_defending_arena_unit``, measured at the attack
    site (so it counts the board as it stands when the attack is declared) and
    scaling on a BASE attack too, since that still has a defending player."""
    return EventAbility(effects=[CustomEffect(fn=_fearless_attack)])


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:12 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


def _yoda_ts26_clone(state, source_ci, target_id, event_ctx):
    """Yoda TS26_14: "Create a Clone Trooper token and give it Sentinel for this
    phase."

    ``_create_token_units`` RETURNS the instances it made (the Buy Time ASH_91
    seam), so "give IT Sentinel" is a ``keyword_grant`` modifier on that exact token
    with no target choice — and being ``this_phase`` it lapses with the ordinary
    duration sweep."""
    from swu.engine.actions import _create_token_units
    from swu.engine.state import Modifier
    ps = state.player_by_id(source_ci.owner_id)
    for token in _create_token_units(state, ps, "Clone Trooper", 1):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=token.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
    return state


@card_ability("TS26", "14")
def _yoda_ts26():
    """TS26_14 — Yoda, "Old and Grumpy" (Unit, Force Jedi Republic, cost 5, 4/4,
    Sentinel): "If you control 7 or more resources, this unit costs 2 resources less
    to play.  When Played/When Defeated: Create a Clone Trooper token and give it
    Sentinel for this phase."

    ONE clause under BOTH triggers (the Captain Rex SEC_48 shape)."""
    clause = [CustomEffect(fn=_yoda_ts26_clone)]
    return [
        CostReduction(amount=2, condition=ConditionCheck(
            Condition.CONTROLLER_N_PLUS_RESOURCES, param=7)),
        TriggerAbility(trigger=WhenPlayed(), effects=list(clause)),
        TriggerAbility(trigger=WhenDefeated(), effects=list(clause)),
    ]


def _fortune_and_glory_capture(state, source_ci, target_id, event_ctx):
    """Fortune and Glory TS26_27 When Played: "This unit captures a non-leader
    unit."  No arena clause, so any non-leader unit on the board is a legal prey."""
    if target_id is None:
        return state
    from swu.engine.actions import _apply_capture
    _apply_capture(state, source_ci.instance_id, target_id)
    return state


def _fortune_and_glory_bounty(state, source_ci, target_id, event_ctx):
    """Fortune and Glory TS26_27's Bounty: "A friendly unit captures a non-leader
    unit" — friendly to the COLLECTOR, i.e. the opponent of the dying unit's
    controller.

    DOCUMENTED AUTO-PICK (the Fugitive Wookiee SHD_211 / Xanadu Blood SHD_191
    convention): a bounty's targeted effect would otherwise be chosen by the DYING
    unit's controller, who has every reason to choose badly.  So the captor is the
    collector's highest-power unit and the prey is the highest-cost non-leader unit
    the collector does NOT control, falling back to any non-leader unit."""
    from swu.cards.models import Leader
    from swu.engine.actions import _apply_capture, compute_power
    collector_id = event_ctx.get("defeated_controller_id")
    if collector_id is None:
        collector_id = source_ci.owner_id
    idx = state.player_index(collector_id)
    collector = state.players[1 - idx]
    captors = [ci for ci in collector.ground_arena + collector.space_arena]
    if not captors:
        return state
    captor = max(captors, key=lambda c: compute_power(state, c))
    prey = [ci for ps in state.players
            for ci in ps.ground_arena + ps.space_arena
            if not isinstance(ci.card_def, Leader)
            and ci.instance_id != captor.instance_id]
    if not prey:
        return state
    foreign = [c for c in prey if c not in captors]
    pool = foreign or prey
    victim = max(pool, key=lambda c: int(getattr(c.card_def, "cost", 0) or 0))
    _apply_capture(state, captor.instance_id, victim.instance_id)
    return state


@card_ability("TS26", "27")
def _fortune_and_glory():
    """TS26_27 — Fortune and Glory (Unit, Transport Underworld Vehicle, cost 4,
    3/5, Bounty)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(
                fn=_fortune_and_glory_capture,
                target=TargetSpec(controller="any", kind="unit",
                                  predicates=("non_leader", "not_self")))],
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_fortune_and_glory_bounty)],
            is_bounty=True,
        ),
    ]


def _fives_borrow_when_played(state, source_ci, target_id, event_ctx):
    """Fives TS26_34: "You may have this unit enter play with the 'When Played'
    abilities of another unit in play."

    The Chimaera JTL_39 seam pointed the other way: instead of using ANOTHER unit's
    ability from that unit, the chosen unit's When Played specs are re-pushed as
    fresh ``resolve_effects`` decisions with ``source_id`` = FIVES — the
    GrantedAbility source/spec split, one card further away — because the printed
    reading is that the abilities become HIS ("this unit enters play with them"), so
    every "this unit" inside them means Fives.

    The ``fives_borrow`` flag is a TERMINATION guard: without it, one copy of Fives
    could borrow a second copy's clause, which would choose the first copy again,
    forever."""
    if target_id is None or event_ctx.get("fives_borrow"):
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, lender = res
    from swu.abilities.resolver import _when_played_ability_indices
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    controller_id = source_ci.owner_id
    owner_idx = state.player_index(controller_id)
    pushed = False
    for ability_idx in reversed(_when_played_ability_indices(state, lender)):
        state.pending_decisions.append(PendingDecision(
            deciding_player_id=controller_id,
            kind="resolve_effects",
            context={
                "set_code": lender.card_def.set_code,
                "card_number": lender.card_def.card_number,
                "ability_idx": ability_idx,
                "source_id": source_ci.instance_id,
                "effect_idx": 0,
                "resolved_targets": {},
                "event_ctx": {"ability_redo": True, "fives_borrow": True},
                "after_all_player_idx": owner_idx,
            },
            after_resolve_player_index=owner_idx,
        ))
        state.event_log.append(DecisionPushed(
            deciding_player_id=controller_id, kind="resolve_effects"))
        pushed = True
    if pushed:
        state.active_player_index = owner_idx
    return state


@card_ability("TS26", "34")
def _fives_ts26():
    """TS26_34 — Fives (Unit, Clone Republic Trooper, cost 6, 6/6, Sentinel)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_fives_borrow_when_played,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("not_self", "has_when_played_ability")))],
        optional=True,
    )


@card_ability("TS26", "36")
def _tribunal():
    """TS26_36 — Tribunal (Unit, Capital Ship Republic Vehicle, cost 10, 6/8): "This
    unit costs 2 resources less to play for each other card you played this phase.
    When Played: Give each other unit −2/−2 for this phase."

    The new ``CostReduction(per_controller_card_played_this_phase=True)``; "each
    other unit" is ``fixed=EACH_IN_PLAY`` + ``not_self``, whose inline expansion is
    the simultaneous application the card means."""
    return [
        CostReduction(amount=2, per_controller_card_played_this_phase=True),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ModifyStats(
                power=-2, hp=-2,
                target=TargetSpec(controller="any", kind="unit",
                                  fixed=EACH_IN_PLAY, predicates=("not_self",)),
                duration=Duration.THIS_PHASE)],
        ),
    ]


def _wartime_refugee_heal(state, source_ci, target_id, event_ctx):
    """Wartime Refugee TS26_43: "On Attack: An opponent heals 1 damage from their
    base."  A printed drawback, so it is mandatory and needs no choice — in two
    player there is exactly one opponent.  Routed through ``_apply_heal`` so the
    Wolffe SOR_160 lock and the base-heal ledger both apply."""
    from swu.abilities.resolver import _apply_heal
    for ps in state.players:
        if ps.player_id == source_ci.owner_id:
            continue
        base = ps.base_instance
        if base is not None:
            state = _apply_heal(state, source_ci, base.instance_id, 1)
    return state


@card_ability("TS26", "43")
def _wartime_refugee():
    """TS26_43 — Wartime Refugee (Unit, Twi'lek, cost 1, 2/3)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_wartime_refugee_heal)],
    )


@card_ability("TS26", "48")
def _vanquish_the_legion():
    """TS26_48 — Vanquish the Legion (Event, Tactic, cost 4): "Give each enemy
    ground unit −2/−2 for this phase."  ``fixed=EACH_ENEMY`` + ``arena`` (the
    Kalani TWI_67 shape)."""
    return EventAbility(effects=[ModifyStats(
        power=-2, hp=-2,
        target=TargetSpec(controller="enemy", kind="unit", arena="ground",
                          fixed=EACH_ENEMY),
        duration=Duration.THIS_PHASE)])


def _galactic_escalation(state, source_ci, target_id, event_ctx):
    """Galactic Escalation TS26_56: "Each player resources the top card of their
    deck" — the shared ``_resource_top_of_deck`` ramp primitive, once per player, in
    player order.  An empty deck simply ramps nothing."""
    from swu.engine.actions import _resource_top_of_deck
    for ps in list(state.players):
        _resource_top_of_deck(state, ps)
    return state


@card_ability("TS26", "56")
def _galactic_escalation_card():
    """TS26_56 — Galactic Escalation (Event, Supply, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_galactic_escalation)])


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:13 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


def _wartime_pirate_opponent_snipe(state, source_ci, target_id, event_ctx):
    """Wartime Pirate TS26_66: "On Attack: An opponent deals 1 damage to a unit."

    ``push_select_damage(decider_id=…)`` — the collector-decider override built for
    Val SHD_58 — with ``max_targets=1``, so the "a unit" is chosen by the OPPONENT.
    A printed drawback, so it is mandatory: the decision's own finish is the only
    out, and with no unit on the board nothing is pushed."""
    from swu.engine.actions import push_select_damage
    opp_id = next(p.player_id for p in state.players
                  if p.player_id != source_ci.owner_id)
    push_select_damage(state, source_ci, max_targets=1, decider_id=opp_id)
    return state


@card_ability("TS26", "66")
def _wartime_pirate():
    """TS26_66 — Wartime Pirate (Unit, Capital Ship Underworld Vehicle, cost 3,
    4/4)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_wartime_pirate_opponent_snipe)],
    )


def _reveal_intentions(state, source_ci, target_id, event_ctx):
    """Reveal Intentions TS26_80: "Each player reveals their hand.  In player order,
    each player discards a card from the hand of the player to their right.  Then,
    each player draws a card."

    In two player "the player to their right" is the one opponent, so this is TWO
    ``name_and_discard`` pushes — one per seat, via the new ``namer_id`` — and that
    decision already reveals the whole hand to the namer and offers only names really
    present, which IS "each player reveals their hand" plus a free pick (the Tip the
    Scale TWI_223 reading).  ``discarder_draws`` is the trailing "then, each player
    draws a card": the discarding player is the one who lost the card, so each seat
    ends one card down and one card up.

    Pushed in REVERSE seat order so the CONTROLLER's pick resolves first on the LIFO
    stack, which is the printed "in player order"."""
    from swu.engine.actions import push_name_and_discard
    controller_id = source_ci.owner_id
    order = [controller_id] + [p.player_id for p in state.players
                               if p.player_id != controller_id]
    for pid in reversed(order):
        push_name_and_discard(state, source_ci, namer_id=pid,
                              discarder_draws=True)
    return state


@card_ability("TS26", "80")
def _reveal_intentions():
    """TS26_80 — Reveal Intentions (Event, Gambit, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_reveal_intentions)])
