"""IBH card ability registrations.

The IBH set is a fresh batch of reprint-duplicate faces (each shares a *name*
with an earlier-set card but carries its own subtitle/text, so they are their own
reprint groups).  Every card here composes from EXISTING engine primitives — no
new decision kind, no trigger/decision-machinery change — the batch-7-through-13
"easy encode" shape.  Registered canonical (lowest-number) member of each group;
siblings are aliased in ``src/swu/cards/reprints.py``.  Imported for its side
effects (the ``@card_ability`` decorators populate the registry).

Groups encoded (all shipped-set reprint canonicals):
  * IBH_61 We're In Trouble — "Deal 3 damage to a unit" (plain ``DealDamage``).
  * IBH_59 Target the Main Generator — "Deal 2 damage to a base".
  * IBH_66 Too Strong for Blasters — "Heal 2 damage from a unit".
  * IBH_18 Go for the Legs — "Exhaust an enemy ground unit".
  * IBH_5  I'll Cover For You — "Deal 1 to an enemy unit and 1 to another enemy
    unit" (the Grenade Strike TWI_171 record-then-exclude two-effect pattern).
  * IBH_21 Improvised Detonation — "Attack with a unit. +2/+0" (``granted_attack``).
  * IBH_74 I Want Proof, Not Leads — "Draw 2 cards, then discard a card".
  * IBH_9  I've Found Them — "Reveal top 3, draw a unit, discard the rest" (the
    ``deck_search`` seam with the new ``rest_disposition="discard"``).
  * IBH_82 Admiral Ozzel — "When Defeated: Each opponent discards a card".
  * IBH_60 Admiral Piett — "On Attack: if you control an Aggression unit, draw".
  * IBH_19 C-3PO — "When Played: if you control a Cunning unit, draw".
  * IBH_68 General Veers — "When Played: if you control a Vigilance unit, deal 2 to
    an enemy base and heal 2 from your base".
  * IBH_11 R2-D2 — "On Attack: if you control a Command unit, exhaust an enemy
    ground unit that costs 4 or less".
  * IBH_6  Rebellion Y-Wing — "On Attack: Deal 1 damage to a base".
  * IBH_15 Tauntaun Mount — "When Defeated: Heal 2 damage from your base".
  * IBH_64 Hoth Lieutenant — "When Played: you may attack with another unit. +2/+0".
  * IBH_16 Ion Cannon — "Action [Exhaust]: Deal 3 damage to a space unit".
  * IBH_62 Imperial Deck Officer — "Action [Exhaust]: Heal 2 from a Villainy unit".
  * IBH_23 General Rieekan — "Action [Exhaust]: Attack with another Heroism unit.
    +2/+0".
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, EventAbility, ActivatedAbility,
    WhenPlayed, WhenDefeated, OnAttack,
    DealDamage, Heal, ExhaustCard, ReadyCard, DefeatUnit,
    DrawCards, DiscardFromHand, CustomEffect,
    ExhaustSelf, PayResources,
    ConditionCheck, Condition,
    ModifyStats, Duration,
    TargetSpec, SELF, DEFENDER, EACH_ENEMY, EACH_FRIENDLY, EACH_IN_PLAY,
)


# ── Events ──────────────────────────────────────────────────────────────────

@card_ability("IBH", "61")
def _were_in_trouble():
    """Deal 3 damage to a unit."""
    return EventAbility(effects=[
        DealDamage(3, TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("IBH", "59")
def _target_the_main_generator():
    """Deal 2 damage to a base."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="any", kind="base")),
    ])


@card_ability("IBH", "66")
def _too_strong_for_blasters():
    """Heal 2 damage from a unit."""
    return EventAbility(effects=[
        Heal(2, TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("IBH", "18")
def _go_for_the_legs():
    """Exhaust an enemy ground unit."""
    return EventAbility(effects=[
        ExhaustCard(TargetSpec(controller="enemy", kind="unit", arena="ground")),
    ])


def _ill_cover_deal_and_record(state, source_ci, target_id, event_ctx):
    """Deal 1 to the chosen enemy unit and record it as excluded, so the
    follow-up effect's ``excludes_event_target`` predicate offers "another"."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name)
    event_ctx["excluded_target_id"] = target_id
    return state


@card_ability("IBH", "5")
def _ill_cover_for_you():
    """Deal 1 damage to an enemy unit and 1 damage to another enemy unit."""
    return EventAbility(effects=[
        CustomEffect(fn=_ill_cover_deal_and_record,
                     target=TargetSpec(controller="enemy", kind="unit")),
        DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                 predicates=("excludes_event_target",))),
    ])


def _improvised_detonation_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2)
    return state


@card_ability("IBH", "21")
def _improvised_detonation():
    """Attack with a unit. It gets +2/+0 for this attack."""
    return EventAbility(effects=[CustomEffect(fn=_improvised_detonation_attack)])


@card_ability("IBH", "74")
def _i_want_proof_not_leads():
    """Draw 2 cards, then discard a card from your hand.

    DEVIATION (documented): the controller discard uses the established
    first-card simplification (K-2SO SOR_145 / J-Type Nubian Starship LOF_194) —
    the forced downside itself is faithful, only *which* card is not chosen."""
    return EventAbility(effects=[
        DrawCards(count=2),
        DiscardFromHand(count=1, chooser="controller"),
    ])


def _ive_found_them_search(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit
    push_deck_search(
        state, source_ci,
        count=1, window=3, up_to=False,
        eligible=lambda cd: isinstance(cd, Unit),
        rest_disposition="discard",
    )
    return state


@card_ability("IBH", "9")
def _ive_found_them():
    """Reveal the top 3 cards of your deck. Draw a unit revealed this way, then
    discard the other revealed cards."""
    return EventAbility(effects=[CustomEffect(fn=_ive_found_them_search)])


# ── Unit triggers ───────────────────────────────────────────────────────────

@card_ability("IBH", "82")
def _admiral_ozzel():
    """When Defeated: Each opponent discards a card from their hand."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DiscardFromHand(count=1, chooser="opponent")],
    )


@card_ability("IBH", "60")
def _admiral_piett():
    """On Attack: If you control an Aggression unit, draw a card."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(count=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Aggression"),
    )


@card_ability("IBH", "19")
def _c_3po():
    """When Played: If you control a Cunning unit, draw a card."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(count=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Cunning"),
    )


@card_ability("IBH", "68")
def _general_veers():
    """When Played: If you control a Vigilance unit, deal 2 damage to an enemy
    base and heal 2 damage from your base."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            DealDamage(2, TargetSpec(controller="enemy", kind="base",
                                     fixed=EACH_ENEMY)),
            Heal(2, TargetSpec(controller="friendly", kind="base",
                               fixed=EACH_FRIENDLY)),
        ],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Vigilance"),
    )


@card_ability("IBH", "11")
def _r2_d2():
    """On Attack: If you control a Command unit, exhaust an enemy ground unit that
    costs 4 or less."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit",
                                        arena="ground", cost_max=4))],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Command"),
    )


@card_ability("IBH", "6")
def _rebellion_y_wing():
    """On Attack: Deal 1 damage to a base."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
    )


@card_ability("IBH", "15")
def _tauntaun_mount():
    """When Defeated: Heal 2 damage from your base."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
    )


def _hoth_lieutenant_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        optional=True, exclude_source=True)
    return state


@card_ability("IBH", "64")
def _hoth_lieutenant():
    """When Played: You may attack with another unit. It gets +2/+0 for this
    attack."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_hoth_lieutenant_attack)],
    )


# ── Activated abilities ─────────────────────────────────────────────────────

@card_ability("IBH", "16")
def _ion_cannon():
    """Action [Exhaust]: Deal 3 damage to a space unit."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="space"))],
        title="Deal 3 damage to a space unit",
    )


@card_ability("IBH", "62")
def _imperial_deck_officer():
    """Action [Exhaust]: Heal 2 damage from a Villainy unit."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                    aspects=("Villainy",)))],
        title="Heal 2 damage from a Villainy unit",
    )


def _general_rieekan_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    # "another Heroism unit" — Heroism is an aspect, not a trait.
    push_granted_attack(state, source_ci, power_bonus=2,
                        attacker_aspect="Heroism", exclude_source=True)
    return state


@card_ability("IBH", "23")
def _general_rieekan():
    """Action [Exhaust]: Attack with another Heroism unit. It gets +2/+0 for this
    attack."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_general_rieekan_attack)],
        title="Attack with another Heroism unit",
    )


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:01 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════
#
# Pure composition of existing primitives — no new engine seam in either IBH group.


@card_ability("IBH", "20")
def _luke_skywalker_ibh():
    """IBH_20 — Luke Skywalker (Unit, Force Rebel, 6/6, unique): "Restore 2  |  When
    Played: You may deal 3 damage to a ground unit."

    Restore is the keyword layer; ``optional`` carries the "you may", so an empty
    ground arena auto-declines rather than prompting."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
        optional=True,
    )


@card_ability("IBH", "53")
def _darth_vader_ibh():
    """IBH_53 — Darth Vader (Leader, Force Imperial Sith, 3/8, unique).

    Undeployed: "Action [1 resource, Exhaust]: Deal 1 damage to a base."
    Deployed:   "On Attack: Deal 2 damage to a base."

    The standard leader split — a ``undeployed_only`` ActivatedAbility and a
    ``deployed_only`` TriggerAbility, since a leader's ``text`` is its undeployed side
    and its ``deploy_box`` the deployed one.  His Epic Action is an ordinary
    resource-threshold deploy, which the ``_deploy_threshold`` regex reads straight
    off the text — no ``DeployCondition`` marker needed.  IBH prints no tokens at all,
    so the number carries no collision hazard."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))],
            title="Deal 1 damage to a base",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
            deployed_only=True,
        ),
    ]


@card_ability("IBH", "72")
def _avenger():
    """IBH_72 — Avenger (Unit, Capital Ship Imperial Vehicle, 8/6, unique): "When
    Played: Deal 1 damage to each other unit (including friendly units)."

    ``fixed=EACH_IN_PLAY`` + ``not_self`` — the inline expansion IS the printed
    "each", dealt simultaneously with no prompt (Bendu LOF_170's shape)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                          fixed=EACH_IN_PLAY,
                                          predicates=("not_self",)))],
    )


def _you_have_failed_me_defeat(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly unit and record that a target was really chosen, so
    the "If you do" ready fires only when one was (IBH_95)."""
    from swu.abilities.resolver import _apply_defeat_unit
    if target_id is None:
        return state
    if state.find_instance(target_id) is None:
        return state
    _apply_defeat_unit(state, target_id)
    event_ctx["prior_target_id"] = target_id
    return state


@card_ability("IBH", "95")
def _you_have_failed_me():
    """IBH_95 — You Have Failed Me (Event, Tactic, cost 4): "Defeat a friendly unit.
    If you do, ready a friendly unit with 5 or less power."

    The In Pursuit TWI_221 shared-``event_ctx`` chain with a DEFEAT as the cost
    (TWI_140's flavour): a targeted ``CustomEffect`` defeats and stamps
    ``prior_target_id``, then a ``ReadyCard`` gated by ``requires_prior_target`` — so
    with no friendly unit the first effect fizzles, the flag is never set, and the
    ready is skipped with no prompt at all."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_you_have_failed_me_defeat,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        ReadyCard(TargetSpec(controller="friendly", kind="unit", power_max=5,
                             predicates=("requires_prior_target",))),
    ])


@card_ability("IBH", "99")
def _blizzard_one():
    """IBH_99 — Blizzard One (Unit, Imperial Vehicle Walker, 5/7, unique): "When
    Played: You may defeat a non-leader ground unit with 3 or less remaining HP."

    ``hp_remaining_max`` is the standing "remaining HP" filter (effective HP less
    damage); ``optional`` means a board with no such unit auto-declines."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit", arena="ground",
                                       predicates=("non_leader",),
                                       hp_remaining_max=3))],
        optional=True,
    )


@card_ability("IBH", "104")
def _the_desolation_of_hoth():
    """IBH_104 — The Desolation of Hoth (Event, Disaster, cost 6): "Defeat up to 2
    enemy units that each cost 3 or less."

    Two sequential ``DefeatUnit`` effects, each ``optional`` (the "up to").  They need
    no ``excludes_event_targets`` bookkeeping — the first defeat has already removed
    its target from the arena, so the second cannot name it again (General Grievous
    TWI_34's "defeat 4 enemy units" is the same four-effect shape)."""
    spec = TargetSpec(controller="enemy", kind="unit", cost_max=3, optional=True)
    return EventAbility(effects=[DefeatUnit(spec), DefeatUnit(spec)])


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:02 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _watch_this(state, source_ci, target_id, event_ctx):
    """"Return a non-leader unit that costs 6 or less to its owner's hand.  Exhaust
    each other enemy unit in the same arena" (IBH_52).

    ONE targeted ``CustomEffect`` doing both clauses (the Kylo SHD_141 rule): the
    arena is read off the bounced unit BEFORE it leaves play, and "each OTHER enemy
    unit" is measured from the EVENT's controller, so bouncing a friendly unit still
    exhausts the opponent's units in that arena — which is what the card says."""
    from swu.abilities.resolver import _apply_return_to_hand
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _ps, victim = res
    arena = victim.zone
    _apply_return_to_hand(state, target_id)
    enemy = state.players[1 - state.player_index(source_ci.owner_id)]
    for u in enemy.ground_arena + enemy.space_arena:
        if u.zone == arena and u.instance_id != target_id:
            u.exhausted = True
    return state


@card_ability("IBH", "52")
def _watch_this_card():
    """IBH_52 — Watch This (Event, Gambit, cost 6): "Return a non-leader unit that
    costs 6 or less to its owner's hand.  Exhaust each other enemy unit in the same
    arena."  """
    return EventAbility(effects=[CustomEffect(
        fn=_watch_this,
        target=TargetSpec(controller="any", kind="unit", cost_max=6,
                          predicates=("non_leader",)))])


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:03 — combat tricks, buffs & tempo   /   ibh-set:04 — misc abilities
# ══════════════════════════════════════════════════════════════════════════════
#
# Pure composition apart from ONE new condition atom
# (``CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY``, IBH_31).


def _leia_heal_and_record(state, source_ci, target_id, event_ctx):
    """Heal 1 from the chosen friendly unit and record it as excluded, so the
    follow-up effect's ``excludes_event_target`` predicate really offers "ANOTHER"
    friendly unit (IBH_1's On Attack).

    It must be the effect FN that stamps the exclusion — a pair of plain declarative
    ``Heal`` effects over ``excludes_event_target`` would offer, and heal, the SAME
    unit twice (the Keep Them Talking ASH_233 lesson)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_heal
    _apply_heal(state, source_ci, target_id, 1)
    event_ctx["excluded_target_id"] = target_id
    return state


@card_ability("IBH", "1")
def _leia_organa_ibh():
    """IBH_1 — Leia Organa, "Get to Your Transports!" (Leader, Official Rebel, 3/7).

    Undeployed: "Action [1 resource, Exhaust]: Heal 1 damage from a friendly unit."
    Deployed:   "On Attack: Heal 1 damage from a friendly unit and 1 damage from
                 another friendly unit."

    The standard leader split (``undeployed_only`` Action + ``deployed_only``
    trigger).  Both clauses filter on ``damaged`` so the ability is never OFFERED as
    a no-op ("don't offer a no-op", Ozzel SOR_129) — which for the Action also means
    the resource and the exhaust are never spent on nothing, hence the matching
    ``CONTROLLER_HAS_DAMAGED_UNIT`` payability gate.  IBH prints no tokens, so the
    number carries no collision hazard.  Her Epic Action is an ordinary
    resource-threshold deploy the ``_deploy_threshold`` regex reads straight off the
    text."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[Heal(1, TargetSpec(controller="friendly", kind="unit",
                                        predicates=("damaged",)))],
            title="Heal 1 damage from a friendly unit",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_DAMAGED_UNIT),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[
                CustomEffect(
                    fn=_leia_heal_and_record,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      predicates=("damaged",))),
                Heal(1, TargetSpec(controller="friendly", kind="unit",
                                   predicates=("damaged", "excludes_event_target"))),
            ],
            deployed_only=True,
        ),
    ]


@card_ability("IBH", "13")
def _recovery():
    """IBH_13 — Recovery (Event, Plan, cost 3): "Heal 5 damage from a unit."

    The plain targeted heal, the IBH_66 Too Strong for Blasters shape at 5."""
    return EventAbility(effects=[
        Heal(5, TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("IBH", "31")
def _millennium_falcon_ibh():
    """IBH_31 — Millennium Falcon, "Bucket of Bolts" (Unit, Rebel Transport Vehicle,
    5/6, unique): "When Played: If your base has more damage on it than an enemy
    base, ready this unit."

    The new ``CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY`` atom — a COMPARISON rather
    than the existing ``CONTROLLER_BASE_DAMAGE_MIN`` threshold, and STRICT, so an
    equal count grants nothing (the mirror-not-negation convention).  Used as the
    ability's ``condition`` so the trigger is not even collected when the clause
    fails, and a unit that enters play exhausted simply stays exhausted."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
        condition=ConditionCheck(
            Condition.CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY),
    )


def _han_solo_nerf_herder():
    """IBH_10 / IBH_42 — Han Solo, "Scruffy-Looking Nerf Herder" (Unit, Rebel, 4/6):
    "Raid 2  |  On Attack: The defender gets -2/-0 for this attack."

    Raid is the keyword layer's; the residual clause is an OnAttack ``ModifyStats``
    on ``fixed=DEFENDER`` for ``THIS_ATTACK`` — NOT a ``while_attacking``
    ConstantAbility, which ``compute_power`` alone reads (so the HP half of any such
    debuff is silently dropped; Scion Shuttle ASH_46's lesson, harmless at -2/-0 but
    the wrong shape to copy).  Attacking a BASE leaves ``DEFENDER`` unresolved and
    the effect is a clean no-op, which is exactly right.

    The two numbers are the same printed card: the DB rows differ only in the DASH
    character of "-2/-0" (hyphen-minus vs en-dash), so ``find_reprints``' rules-text
    identity keys them into separate singleton groups and each must be registered
    (the ``_norm_rules`` blind-spot, recorded in the reprint-duplicates memory)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=-2, hp=0, target=TargetSpec(fixed=DEFENDER),
                             duration=Duration.THIS_ATTACK)],
    )


card_ability("IBH", "42")(_han_solo_nerf_herder)
card_ability("IBH", "10")(_han_solo_nerf_herder)
