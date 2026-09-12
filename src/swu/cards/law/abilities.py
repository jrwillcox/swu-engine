"""LAW (Legends of the Force) card ability registrations.

Cards with no text or only keywords are handled by the keyword engine and are
not registered here.  This module is imported for its side effects (the
``@card_ability`` decorators populate the registry).

Group ``leia-organa:01`` — Direct damage & removal:
  * LAW_41 Nothing Left to Fear — buff a friendly unit, then defeat a unit with
    power ≤ the chosen unit (the ``power_le_event_threshold`` predicate seam).
  * LAW_45 Zeb Orellios — "you may deal 3 (or 5 if you control a Command/Cunning
    unit) to a ground unit" (a conditional-magnitude CustomEffect.target).

Group ``leia-organa:02`` — Card advantage & disruption:
  * LAW_119 Rogue One — "When a friendly unit is defeated: look at the top 2,
    bottom any number, rest on top in any order" (the ``reveal_top`` seam with
    ``disposition="bottom"`` + a filtered ``WhenUnitDefeated`` trigger).
  * LAW_145 R2-D2 — "When Played: search the top 5 for a unit sharing an aspect
    with a friendly unit and draw it" (the ``deck_search`` seam).
  * LAW_166 Putting a Team Together — "search the top 8 for a Vigilance,
    Aggression, or Cunning unit and draw it" (the ``deck_search`` seam).

Group ``leia-organa:05`` — Miscellaneous abilities:
  * LAW_20 Daimyo's Palace — Epic Action "play a card ignoring 1 V/C/A/Cunning
    aspect penalty" (play-from-hand ``ignore_aspect_penalty`` field; units only).
  * LAW_104 Bodhi Rook — "On Attack: you may give a friendly Rebel unit Sentinel
    this phase" (an optional OnAttack GrantKeyword).
  * LAW_108 Lando Calrissian — "While defending, the attacker gets −1/−0" (a
    ``while_defending`` ConstantAbility debuffing the attacker via compute_power).

Group ``jabba-the-hutt:03`` — Direct damage & removal:
  * LAW_163 The Sarlacc of Carkoon — "On Attack: Put a unit from your discard pile
    on the bottom of your deck.  Deal damage equal to that unit's power to an enemy
    ground unit" (the new ``discard_unit_damage`` two-stage decision kind).
  * LAW_214 Boba Fett — "When Played/On Attack: You may pay 1 resource.  If you do,
    deal 3 damage to a ground unit" (two optional triggers gated by
    ``CONTROLLER_N_PLUS_READY_RESOURCES``, a pay-and-damage CustomEffect).

Group ``jabba-the-hutt:05`` — Combat tricks, buffs & tempo:
  * LAW_65 4-LOM — "When Played: you may attack with a friendly Bounty Hunter
    unit, even if exhausted; no bases" (the granted-attack seam).
  * LAW_158 Khetanna — "the next Underworld unit you play this phase costs 1 less"
    (the new deferred ``NextPlayDiscount`` effect + pending-discount play-cost seam).
  * LAW_168 Haymaker — "token a friendly unit, then it deals its power to an enemy
    unit in the same arena" (two dependent effects + the ``same_arena_as_event``
    predicate).
  * LAW_210 Salacious Crumb — "if you control Jabba the Hutt, enters play ready"
    (the new ``EntersPlayReady`` spec read at ``_put_unit_in_play``).
  * LAW_231 Weequay Pirate — "if no resources were paid, give it Experience" (reads
    the play's ``cost_paid`` threaded into the enter-play ``event_ctx``).
  * LAW_249 Black Sun Cabalist — "give Experience to another friendly Underworld
    unit" (a plain WhenPlayed GiveToken).

Group ``jabba-the-hutt:04`` — Card advantage & disruption:
  * LAW_23 Great Pit of Carkoon — Epic Action [discard a unit from hand]: tutor
    The Sarlacc of Carkoon (the new ``discard_for_search`` decision kind feeding
    the ``deck_search`` seam; gated by ``CONTROLLER_HAS_UNIT_IN_HAND``).
  * LAW_136 Syndicate Spice Runner — "When Played: search the top 3 for an
    Underworld unit and draw it" (the ``deck_search`` seam).
  * LAW_246 The Axe Forgets — "Return a non-leader unit that costs 3 or less to its
    owner's hand" (a plain ``ReturnToHand`` with ``cost_max=3``).
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, EventAbility, ActivatedAbility, ConstantAbility,
    WhenPlayed, WhenUnitDefeated, WhenDefeated, WhenDeployed, OnAttack,
    OnAttackDefeatsUnit, WhenAttackEnds, WhenYouDraw,
    DefeatUnit, DefeatAllUnits, DiscardCardCost, DealDamageEqualTo,
    WhenUnitHealed, WhenFriendlyUnitAttacksAndDefeatsUnit,
    DealDamage, DrawCards, Heal, CustomEffect, GiveToken, GrantKeyword, KeywordGrant,
    TraitGrant, ReturnToHand, CreateCreditToken, NextPlayDiscount, EntersPlayReady,
    ExtraRegroupPhase, GrantedAbility, ReadyRestriction, PhaseStartTrigger,
    WhenThisIsDiscarded, WhenYouDiscardFromDeck, PlayFromDiscardAction,
    StandingPlayDiscount, WhenYouPlayCard, WhenFriendlyUnitAttackEnds,
    OnAttackRedo, ExhaustCard, ReadyCard, WhenUnitAttacks,
    CostReduction, IgnoreAspectPenaltyForPlays, WhenAttacked, Protection,
    ConditionalFirstStrike,
    PrintedStatsOverride, AuraGrantedAbility, DefeatCreditCost,
    EnemyCreditsLoseAbilities, DiscardFromHand,
    ModifyStats, StatBonus, PayResources, ExhaustSelf,
    ConditionalEffect,
    ConditionCheck, Condition,
    TargetSpec, Duration, SELF, EACH_FRIENDLY, EACH_ENEMY,
)


def _nlf_buff_and_record(state, source_ci, target_id, event_ctx):
    """Give the chosen friendly unit +2/+2 for this phase and record its buffed
    effective power as the defeat threshold for the follow-up effect."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    from swu.abilities.resolver import _make_modifier
    from swu.engine.actions import compute_power
    state.modifiers.append(
        _make_modifier(state, source_ci.instance_id, target_id, 2, 2, Duration.THIS_PHASE)
    )
    event_ctx["power_le_threshold"] = compute_power(state, unit)
    return state


def _zeb_damage(state, source_ci, target_id, event_ctx):
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    boosted = any(
        ({"Command", "Cunning"} & {a.name for a in (getattr(u.card_def, "aspects", None) or ())})
        for arena in (ps.ground_arena, ps.space_arena) for u in arena
    )
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 5 if boosted else 3,
                              source_ci.card_def.display_name)


@card_ability("LAW", "41")
def _nothing_left_to_fear():
    """Choose a friendly unit and give it +2/+2 for this phase.  Then, you may
    defeat a non-leader unit with power equal to or less than the chosen unit.

    Two sequential, dependent target choices: the first (mandatory) picks the
    friendly unit, buffs it, and records its *buffed* effective power as the
    defeat threshold in ``event_ctx["power_le_threshold"]``; the second (optional
    — "you may") defeats a non-leader unit whose effective power is ≤ that
    threshold (the ``power_le_event_threshold`` predicate reads the recorded
    value).  The shared ``event_ctx`` dict of the resolve_effects decision
    threads the threshold between the two effects.
    """
    return EventAbility(effects=[
        CustomEffect(
            fn=_nlf_buff_and_record,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        DefeatUnit(target=TargetSpec(
            controller="any", kind="unit",
            predicates=("non_leader", "power_le_event_threshold"),
            optional=True,
        )),
    ])


@card_ability("LAW", "45")
def _zeb_orellios():
    """Sentinel (keyword layer).
    When Played: You may deal 3 damage to a ground unit.  If you control a
    Command or Cunning unit, you may deal 5 damage to a ground unit instead.

    A single optional ("you may") WhenPlayed whose CustomEffect.target prompts
    for a ground unit; the magnitude (3 vs 5) is decided inside the fn from the
    board (controlling a Command or Cunning unit — two aspects OR'd, which a
    single Condition atom cannot express).  Auto-declines with no ground unit.
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_zeb_damage,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
        )],
        optional=True,
    )


# ── Group leia-organa:02 — Card advantage & disruption ────────────────────────

def _rogue_one_look(state, source_ci, target_id, event_ctx):
    """Adapter: look at the top 2 cards, then push the reveal_top decision in
    *bottom* disposition (un-kept cards go to the bottom of the deck, kept cards
    stay on top in the chosen order).  No aspect damage — this is a plain look."""
    from swu.engine.actions import push_reveal_top_discard_reorder
    push_reveal_top_discard_reorder(
        state, source_ci, count=2,
        deal_aspect_damage=False, disposition="bottom",
    )
    return state


@card_ability("LAW", "119")
def _rogue_one():
    """When a friendly unit is defeated: Look at the top 2 cards of your deck.
    Put any number of them on the bottom of your deck and the rest on top in any
    order.

    A ``WhenUnitDefeated`` trigger filtered to friendly units (the source is in
    play, so the filter is read from its perspective; the trigger fires for every
    *other* friendly unit's defeat — Rogue One's own defeat removes it from play
    before the event fires, so it does not self-trigger).  The look-and-reorder is
    the ``reveal_top`` seam in ``disposition="bottom"`` (un-kept cards bottom the
    deck instead of going to the discard pile, and no aspect damage is dealt).
    """
    return TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(controller="friendly", kind="unit")),
        effects=[CustomEffect(fn=_rogue_one_look)],
    )


def _aspect_names(card_def):
    return {a.name for a in (getattr(card_def, "aspects", None) or ())}


def _r2d2_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 5 for a unit that shares an aspect with a friendly
    unit, draw it, bottom the rest in seeded-random order.

    The eligibility ("shares an aspect with a friendly unit") depends on the board
    at resolution, so the friendly aspects are gathered here into a closure passed
    to ``push_deck_search`` (R2-D2 itself is in play when its When Played resolves,
    so its own aspects count — any unit sharing them qualifies)."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    friendly_aspects: set[str] = set()
    for arena in (ps.ground_arena, ps.space_arena):
        for u in arena:
            friendly_aspects |= _aspect_names(u.card_def)

    def eligible(cd):
        return isinstance(cd, Unit) and bool(_aspect_names(cd) & friendly_aspects)

    push_deck_search(state, source_ci, count=1, eligible=eligible,
                     up_to=False, window=5)
    return state


@card_ability("LAW", "145")
def _r2_d2():
    """When Played: Search the top 5 cards of your deck for a unit that shares an
    aspect with a friendly unit, reveal it, and draw it.  (Put the other cards on
    the bottom of your deck in a random order.)

    A ``deck_search`` (window=5, count=1, mandatory-if-able) whose eligibility
    closure captures the aspects of the controller's units (the ``deck_search``
    seam: reveal the eligible cards among the window, take the chosen one to hand,
    bottom the rest in a seeded-random order)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_r2d2_search)],
    )


_TEAM_ASPECTS = {"Vigilance", "Aggression", "Cunning"}


def _putting_a_team_search(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit

    def eligible(cd):
        return isinstance(cd, Unit) and bool(_aspect_names(cd) & _TEAM_ASPECTS)

    push_deck_search(state, source_ci, count=1, eligible=eligible,
                     up_to=False, window=8)
    return state


@card_ability("LAW", "166")
def _putting_a_team_together():
    """Search the top 8 cards of your deck for a Vigilance, Aggression, or Cunning
    unit, reveal it, and draw it.  (Put the rest of the cards on the bottom of your
    deck in a random order.)

    A ``deck_search`` (window=8, count=1, mandatory-if-able) whose eligibility is a
    unit carrying any of the three aspects."""
    return EventAbility(effects=[CustomEffect(fn=_putting_a_team_search)])


# ── Group leia-organa:03 — Combat tricks, buffs & tempo ───────────────────────

def _leia_buff(state, source_ci, target_id, event_ctx):
    """Give the chosen unit +1/+1 for each different aspect it has, this phase.

    The magnitude scales with the *chosen* unit's distinct aspect count (a single
    ModifyStats with fixed numbers cannot express it), so the modifier is built
    here from the resolved target's aspects."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    n = len(_aspect_names(unit.card_def))
    if n:
        from swu.abilities.resolver import _make_modifier
        state.modifiers.append(
            _make_modifier(state, source_ci.instance_id, target_id, n, n,
                           Duration.THIS_PHASE))
    return state


def _leia_deploy_tokens(state, source_ci, target_id, event_ctx):
    """Give the chosen unit an Experience token for each different aspect among
    units the controller controls (the count is state-derived, so a scaling
    CustomEffect rather than a fixed-count GiveToken)."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    host_ps, unit = result
    controller = state.player_by_id(source_ci.owner_id)
    aspects: set[str] = set()
    for arena in (controller.ground_arena, controller.space_arena):
        for u in arena:
            aspects |= _aspect_names(u.card_def)
    from swu.engine.tokens import attach_token
    for _ in range(len(aspects)):
        attach_token(state, host_ps, unit, "Experience")
    return state


@card_ability("LAW", "10")
def _leia_organa():
    """LAW_10 — Leia Organa (Leader, Rebel, 2/2, Overwhelm).

    Undeployed Action [2 resources, Exhaust]: "For this phase, give a unit +1/+1
    for each different aspect it has."  An ``undeployed_only`` ActivatedAbility
    whose one CustomEffect.target prompts for any unit and applies a scaling
    this-phase +N/+N (N = the chosen unit's distinct aspect count).

    Deployed side: Overwhelm (the keyword layer — Leia's printed bar) plus "When
    Deployed: Choose a unit. Give an Experience token to that unit for each
    different aspect among units you control."  Modelled as a ``WhenDeployed``
    trigger (fires on the LeaderDeployed event for this leader) whose one
    CustomEffect.target prompts for the unit and gives it a state-derived number of
    Experience tokens.  ``deployed_only`` since it is the deployed side.

    The Epic Action deploy ("If you control 5 or more resources, deploy this
    leader") is the standard deploy_threshold machinery — no registration."""
    return [
        ActivatedAbility(
            costs=[PayResources(2), ExhaustSelf()],
            effects=[CustomEffect(
                fn=_leia_buff,
                target=TargetSpec(controller="any", kind="unit"),
            )],
            title="Give a unit +1/+1 per different aspect (this phase)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(
                fn=_leia_deploy_tokens,
                target=TargetSpec(controller="any", kind="unit"),
            )],
            deployed_only=True,
        ),
    ]


def _ezra_heal(state, source_ci, target_id, event_ctx):
    """Heal 2 from the chosen unit, or 4 if the controller controls an Aggression
    or Cunning unit (an OR of two aspects a single Condition atom cannot express —
    the magnitude is decided here from the board, the Zeb Orellios LAW_45
    conditional-magnitude pattern)."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    boosted = any(
        ({"Aggression", "Cunning"} & _aspect_names(u.card_def))
        for arena in (ps.ground_arena, ps.space_arena) for u in arena)
    from swu.abilities.resolver import _apply_heal
    return _apply_heal(state, source_ci, target_id, 4 if boosted else 2)


@card_ability("LAW", "35")
def _ezra_bridger():
    """LAW_35 — Ezra Bridger (Unit, Force/Rebel/Spectre, Raid 1 — keyword layer).

    "When Played: You may heal 2 damage from a unit.  If you control an Aggression
    or Cunning unit, you may heal 4 damage from a unit instead."  A single optional
    ("you may") WhenPlayed whose CustomEffect.target prompts for a unit; the heal
    magnitude (2 vs 4) is decided inside the fn from the board.  Auto-declines with
    no damaged unit to heal (the optional-trigger legal-effect gate)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_ezra_heal,
            target=TargetSpec(controller="any", kind="unit", predicates=("damaged",)),
        )],
        optional=True,
    )


@card_ability("LAW", "37")
def _han_solo():
    """LAW_37 — Han Solo (Unit, Rebel, Shielded — keyword layer).

    "On Attack: Give an Experience token to this unit."  A plain OnAttack
    GiveToken with a fixed SELF target (no player choice → resolves inline)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience", TargetSpec(kind="unit", fixed=SELF))],
    )


def _jyn_erso_modal(state, source_ci, target_id, event_ctx):
    """Adapter: push the "give an Experience token to a unit OR exhaust a unit"
    modal (the Leia SOR_189 push_modal seam)."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["give_experience_unit", "exhaust_unit"])
    return state


@card_ability("LAW", "67")
def _jyn_erso():
    """LAW_67 — Jyn Erso (Unit, Rebel): "When Played: Either give an Experience
    token to a unit or exhaust a unit."

    A mandatory ("Either … or") WhenPlayed whose one CustomEffect is a thin adapter
    onto push_modal with two modes — ``give_experience_unit`` (any unit; the new
    modal mode) and the existing ``exhaust_unit``.  Jyn herself is in play when her
    When Played resolves, so the give-token mode always has a legal target (the
    modal never fully fizzles)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jyn_erso_modal)],
    )


@card_ability("LAW", "105")
def _cinta_kaz():
    """LAW_105 — Cinta Kaz (Unit, Rebel): "While this unit is upgraded, she gains
    Sentinel."

    A self-targeted constant KeywordGrant gated by SOURCE_UPGRADED (the Protector
    of the Throne SHD_247 pattern).  Per the CR, Shield/Experience tokens count as
    upgrades, so any attached upgrade switches Sentinel on.  The keyword sanitiser
    strips Cinta's printed Sentinel because this conditional self-grant is
    registered, so the ability — not an always-on printed bar — owns it."""
    return ConstantAbility(
        target=TargetSpec(kind="unit", fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED),
    )


# ── Group leia-organa:04 — Combat tricks, buffs & tempo ───────────────────────

@card_ability("LAW", "111")
def _leias_disguise():
    """LAW_111 — Leia's Disguise (Upgrade, Armor/Item; "Attach to a non-Vehicle
    unit"):
      * Attached unit gains the Underworld trait.
      * When Played: If attached unit is Leia Organa, give a Shield token to a
        friendly unit.

    Two specs.  The trait grant is a ``ConstantAbility(target=SELF,
    effects=[TraitGrant("Underworld")])`` (the Foundling SHD_69 pattern — the trait
    query layer scans a unit's attached upgrades for a TraitGrant constant, so the
    host gains Underworld for as long as the upgrade is attached).  The When Played
    is a ``WhenPlayed`` ``GiveToken("Shield", friendly unit)`` gated by
    ``ATTACHED_HOST_NAMED("Leia Organa")`` (the Mandalorian's Rifle SHD_251 pattern
    — the whole trigger is collected only when the host's name is Leia Organa; the
    host is itself a friendly unit so the mandatory Shield always has a target).
    The non-Vehicle attach restriction is the engine's upgrade-target parser."""
    return [
        ConstantAbility(
            target=TargetSpec(kind="unit", fixed=SELF),
            effects=[TraitGrant("Underworld")],
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[GiveToken("Shield",
                               TargetSpec(controller="friendly", kind="unit"))],
            condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Leia Organa"),
        ),
    ]


@card_ability("LAW", "142")
def _scarif_lieutenant():
    """LAW_142 — Scarif Lieutenant (Unit, Rebel/Trooper): "When Defeated: Give an
    Experience token to a friendly Rebel unit."

    A ``WhenDefeated`` ``GiveToken("Experience", friendly Rebel unit)``,
    mandatory-if-able (the controller picks among their Rebel units; fizzles
    silently with none).  Scarif Lieutenant has left play by the time its
    WhenDefeated resolves, so it is never its own recipient."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="friendly", kind="unit",
                                      traits=("Rebel",)))],
    )


def _jaunty_tokens(state, source_ci, target_id, event_ctx):
    """Give this unit an Experience token for each different aspect among units the
    controller controls (a state-derived count, so a scaling CustomEffect rather
    than a fixed-count GiveToken — the Leia LAW_10 ``_leia_deploy_tokens`` pattern,
    but fixed on SELF).  Jaunty itself is in play when its When Played resolves, so
    its own aspects count."""
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    host_ps, unit = res
    controller = state.player_by_id(source_ci.owner_id)
    aspects: set[str] = set()
    for arena in (controller.ground_arena, controller.space_arena):
        for u in arena:
            aspects |= _aspect_names(u.card_def)
    from swu.engine.tokens import attach_token
    for _ in range(len(aspects)):
        attach_token(state, host_ps, unit, "Experience")
    return state


@card_ability("LAW", "147")
def _jaunty_light_freighter():
    """LAW_147 — Jaunty Light Freighter (Unit, Vehicle/Transport): "When Played:
    Give an Experience token to this unit for each different aspect among units you
    control."

    A ``WhenPlayed`` whose one CustomEffect gives SELF a state-derived number of
    Experience tokens (no player choice → resolves inline)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jaunty_tokens)],
    )


@card_ability("LAW", "152")
def _c_3po_law():
    """LAW_152 — C-3PO (Unit, Droid/Rebel/Underworld): "On Attack: You may give an
    Experience token to another non-leader unit that shares a Trait with a friendly
    leader."

    An optional ("you may") ``OnAttack`` ``GiveToken("Experience", …)`` whose target
    is another (``not_self``) non-leader unit sharing a trait with the controller's
    leader — the new ``shares_trait_with_friendly_leader`` predicate.
    ``controller="any"`` mirrors the printed text (it omits "friendly"), but an
    Experience token benefits the recipient so the controller never picks an enemy;
    with no eligible unit the optional trigger auto-declines."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="any", kind="unit",
                                      predicates=("not_self", "non_leader",
                                                  "shares_trait_with_friendly_leader")))],
        optional=True,
    )


def _common_cause_buff(state, source_ci, target_id, event_ctx):
    """Give the chosen unit +1/+1 for this phase for each different aspect among
    units the controller controls (a state-derived magnitude, so a scaling
    CustomEffect rather than a fixed ModifyStats — the Common Cause is an Event, so
    it never counts itself)."""
    if target_id is None:
        return state
    controller = state.player_by_id(source_ci.owner_id)
    aspects: set[str] = set()
    for arena in (controller.ground_arena, controller.space_arena):
        for u in arena:
            aspects |= _aspect_names(u.card_def)
    n = len(aspects)
    if n:
        from swu.abilities.resolver import _make_modifier
        state.modifiers.append(
            _make_modifier(state, source_ci.instance_id, target_id, n, n,
                           Duration.THIS_PHASE))
    return state


@card_ability("LAW", "167")
def _common_cause():
    """LAW_167 — Common Cause (Event): "Give a unit +1/+1 for this phase for each
    different aspect among units you control."

    An ``EventAbility`` whose one CustomEffect.target prompts for any unit and
    applies a scaling this-phase +N/+N (N = the distinct aspect count among the
    controller's units)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_common_cause_buff,
            target=TargetSpec(controller="any", kind="unit"),
        ),
    ])


# ── Group leia-organa:05 — Miscellaneous abilities ────────────────────────────

def _daimyo_play(state, source_ci, target_id, event_ctx):
    """Adapter: push the play-from-hand decision with one V/C/A/Cunning aspect
    penalty waived (the Energy Conversion Lab SOR_22 / Admiral Ozzel SOR_129
    adapter pattern)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, ignore_aspect_penalty=True)
    return state


@card_ability("LAW", "20")
def _daimyos_palace():
    """LAW_20 — Daimyo's Palace (Base): "Epic Action: Play a card from your hand,
    ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties."

    A once-per-game Epic Action on a base (``epic=True``, no resource cost).  The
    one CustomEffect is a thin adapter onto the play-from-hand subsystem
    (``push_play_from_hand`` with the new ``ignore_aspect_penalty=True`` field),
    which waives one V/C/A/Cunning aspect-penalty pip — 2 resources, but only when
    the card actually carries such a penalty (a fully-matched card and
    Heroism/Villainy penalties are never discounted).  Gated by
    ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY`` so the
    once-per-game epic is not wasted when nothing is playable (the Energy
    Conversion Lab SOR_22 "don't offer a no-op epic" pattern).

    DEVIATION (documented): "Play a **card**" is restricted to **units** — the
    play-from-hand subsystem plays only units (events/upgrades would require the
    PlayCard resolution path threaded through it, a larger change to core play
    resolution, out of scope for a card batch).  The aspect-penalty waiver itself
    is faithful.  Base activated/Epic abilities are enumerated via the existing
    base_zone scan (Energy Conversion Lab SOR_22)."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_daimyo_play)],
        title="Epic Action: play a unit from hand, ignoring 1 aspect penalty",
        epic=True,
        condition=ConditionCheck(
            Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY),
    )


@card_ability("LAW", "104")
def _bodhi_rook():
    """LAW_104 — Bodhi Rook (Unit, Rebel, Sentinel — keyword layer): "On Attack:
    You may give a friendly Rebel unit Sentinel for this phase."

    An optional ("you may") ``OnAttack`` ``GrantKeyword("Sentinel", …)`` targeting
    a friendly Rebel unit for this phase (a ``keyword_grant`` modifier honoured by
    the ``has_keyword`` query layer).  Bodhi himself is a friendly Rebel unit in
    play when this resolves, so the optional trigger always has a legal target (the
    controller may simply choose to grant Sentinel to any of their Rebel units —
    typically a blocker, not the attacking Bodhi)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword(
            "Sentinel", 0,
            TargetSpec(controller="friendly", kind="unit", traits=("Rebel",)),
            Duration.THIS_PHASE)],
        optional=True,
    )


@card_ability("LAW", "108")
def _lando_calrissian():
    """LAW_108 — Lando Calrissian (Unit, Rebel/Underworld, Sentinel — keyword
    layer): "While this unit is defending, the attacker gets −1/−0."

    A ``while_defending`` ``ConstantAbility`` whose target is the enemy attacker
    (``controller="enemy"``); the ``StatBonus(power=-1)`` is contributed to that
    attacker's effective power only while Lando is the **current combat defender**
    — ``compute_power`` threads the defender's instance id through to the constant
    scan, so the debuff lands solely on the unit attacking Lando (not on enemy
    units generally, and not when Lando attacks).  The −0 hp side is skipped by
    ``compute_hp`` (no combat context).  Sentinel is Lando's unconditional printed
    keyword (the keyword layer; no registration / no sanitiser interaction)."""
    return ConstantAbility(
        target=TargetSpec(controller="enemy", kind="unit"),
        effects=[StatBonus(power=-1, hp=0)],
        while_defending=True,
    )


# ── Group leia-organa:02-jabba (jabba-the-hutt:02) — Hidden keyword residual ───

def _jabbas_rancor_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push the opponent-chooses-target → may-deal-7 decision, restricted
    to the opponent's *ground* units (the Grey Squadron Y-Wing SHD_246 seam with
    the new ``ground_only`` flag)."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(state, source_ci, amount=7, ground_only=True)
    return state


@card_ability("LAW", "216")
def _jabbas_rancor():
    """LAW_216 — Jabba's Rancor (Unit, Creature/Underworld, 7/7, Hidden — the
    keyword layer):

    "On Attack: An opponent chooses a ground unit they control.  You may deal 7
    damage to that unit."

    The residual On Attack text for the Hidden-keyword card.  A plain ``OnAttack``
    whose one CustomEffect is a thin adapter onto the existing
    ``opponent_chooses_target`` decision kind (push_opponent_chooses_target,
    SHD_246), extended with ``ground_only=True`` so the opponent picks one of
    their ground units (not a base / space unit); the controller may then deal 7
    damage to it or decline.  With no opponent ground unit the decision is not
    pushed (the trigger fizzles)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_jabbas_rancor_attack)],
    )


# ── Group jabba-the-hutt:07 — New primitive: create-token-unit (Credit) ────────
# The Credit token is an unlimited-supply resource token created by these cards
# and *defeated* while paying a resource cost to pay 1 less (see the
# CreateCreditToken effect + actions._pay_play_cost / the PlayerState.credits
# pile).  Three cards merely create credits; Jabba the Hutt LAW_15 is the only
# consumer of the "defeated a Credit while paying its cost" rider.


@card_ability("LAW", "244")
def _unmarked_credits():
    """LAW_244 — Unmarked Credits (Event, Supply): "Create a Credit token."

    The minimal create-token-unit primitive: a plain ``EventAbility`` with one
    non-targeted ``CreateCreditToken`` effect (resolves inline for the controller,
    like DrawCards)."""
    return EventAbility(effects=[CreateCreditToken()])


@card_ability("LAW", "134")
def _bib_fortuna():
    """LAW_134 — Bib Fortuna (Unit, Twi'lek/Underworld): "When Played: If you
    control another Underworld unit, create a Credit token."

    A ``WhenPlayed`` ``CreateCreditToken`` gated by
    ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Underworld")`` (the condition gates trigger
    *collection*, so the credit is created only when the controller already
    controls another Underworld unit — Bib himself is excluded by "other")."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CreateCreditToken()],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 "Underworld"),
    )


@card_ability("LAW", "252")
def _fetts_firespray():
    """LAW_252 — Fett's Firespray (Unit, Transport/Underworld/Vehicle, Ambush —
    keyword layer): "When Attack Ends: If the defending unit was defeated, create
    a Credit token."

    Modelled with the existing ``OnAttackDefeatsUnit`` trigger ("when this unit
    defeats a unit in combat"), whose one mandatory effect creates a Credit token.
    DEVIATION (documented): ``OnAttackDefeatsUnit`` fires only when the attacker
    *survives* the combat (the engine's `not attacker_dead` guard), so if Fett's
    Firespray trades and dies while defeating the defender, no credit is created —
    the same simplification the existing "defeats a unit" trigger makes.  A base
    attack defeats no unit, so it never creates a credit either way."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[CreateCreditToken()],
    )


# ── Group jabba-the-hutt:03 — Direct damage & removal ─────────────────────────

def _sarlacc_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push the discard_unit_damage decision (recycle a discarded unit to
    the bottom of the deck, then deal its power to an enemy ground unit)."""
    from swu.engine.actions import push_discard_unit_then_damage
    push_discard_unit_then_damage(state, source_ci,
                                  target_controller="enemy", target_arena="ground")
    return state


@card_ability("LAW", "163")
def _sarlacc_of_carkoon():
    """LAW_163 — The Sarlacc of Carkoon (Unit, Creature, 8/9): "On Attack: Put a
    unit from your discard pile on the bottom of your deck.  Deal damage equal to
    that unit's power to an enemy ground unit."

    A plain ``OnAttack`` whose one CustomEffect is a thin adapter onto the new
    ``discard_unit_damage`` two-stage decision kind (``push_discard_unit_then_damage``,
    the push_sacrifice_resource_for_damage "choose, then deal" shape): the
    controller picks a unit from their discard pile (recycled to the bottom of the
    deck), and that unit's printed power becomes the damage dealt to a chosen enemy
    ground unit.  Mandatory-if-able — fizzles cleanly with no unit in the discard
    pile; the damage step is skipped if no enemy ground unit exists when the recycle
    resolves."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_sarlacc_attack)],
    )


def _boba_pay_and_damage(state, source_ci, target_id, event_ctx):
    """Pay 1 resource, then deal 3 damage to the chosen ground unit.

    The "you may pay 1 resource.  If you do, deal 3 …" is bound into one
    CustomEffect so the damage is dealt only when the payment is made (the Bright
    Hope SOR_99 / Kihraxz SHD_118 "if you do" pattern): the trigger's optional
    accept is the "may pay", and accepting commits to the payment + damage.
    Affordability is guaranteed by the trigger's ``CONTROLLER_N_PLUS_READY_RESOURCES``
    gate, but the fn re-checks defensively before paying."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state  # cannot pay → no damage ("if you do")
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 3, source_ci.card_def.display_name)


def _boba_trigger(trigger):
    """Build one of Boba Fett's two identical optional pay-then-damage triggers."""
    return TriggerAbility(
        trigger=trigger,
        effects=[CustomEffect(
            fn=_boba_pay_and_damage,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
        )],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, 1),
    )


@card_ability("LAW", "214")
def _boba_fett():
    """LAW_214 — Boba Fett (Unit, Underworld/Bounty Hunter, 6/5): "When Played/On
    Attack: You may pay 1 resource.  If you do, deal 3 damage to a ground unit."

    Two triggers — a ``WhenPlayed`` and an ``OnAttack`` — that are otherwise
    identical: each is optional ("you may"), gated by
    ``CONTROLLER_N_PLUS_READY_RESOURCES(1)`` so it is offered only when the 1
    resource can actually be paid (the "don't offer a no-op" pattern), and its one
    CustomEffect (target = any ground unit) pays the resource and deals 3 — bound
    together so the damage lands only if the payment is made.  ``controller="any"``
    mirrors the printed "a ground unit"; the controller naturally aims at an enemy.
    The optional trigger auto-declines when no ground unit is on the board."""
    return [_boba_trigger(WhenPlayed()), _boba_trigger(OnAttack())]


# ── Group jabba-the-hutt:04 — Card advantage & disruption ─────────────────────

def _great_pit_search(state, source_ci, target_id, event_ctx):
    """Adapter: push the discard_for_search decision (discard a chosen unit from
    hand, then tutor 'The Sarlacc of Carkoon')."""
    from swu.engine.actions import push_discard_unit_for_search
    push_discard_unit_for_search(state, source_ci,
                                 search_name="The Sarlacc of Carkoon")
    return state


@card_ability("LAW", "23")
def _great_pit_of_carkoon():
    """LAW_23 — Great Pit of Carkoon (Base): "Epic Action [discard a unit from your
    hand]: Search your deck for a card named The Sarlacc of Carkoon, reveal it, and
    draw it."

    A once-per-game Epic Action on a base (``epic=True``, no resource cost),
    enumerated via the existing base_zone scan (Daimyo's Palace LAW_20 pattern).
    The "discard a unit from your hand" cost lets the controller *choose* which
    unit to discard, so it is modelled by the one CustomEffect pushing the new
    self-contained ``discard_for_search`` decision kind
    (``push_discard_unit_for_search``): pick a hand unit → it is discarded (the
    mandatory cost) → the deck is searched for the named card, which is drawn (the
    ``deck_search`` seam over the whole deck; the un-taken cards are bottomed in a
    seeded-random order, doubling as the post-search shuffle).  Gated by
    ``CONTROLLER_HAS_UNIT_IN_HAND`` so the epic is not wasted when there is no unit
    to discard (the "don't offer a no-op epic" pattern)."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_great_pit_search)],
        title="Epic Action: discard a unit to tutor The Sarlacc of Carkoon",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_IN_HAND),
    )


def _spice_runner_search(state, source_ci, target_id, event_ctx):
    """Adapter: search the top 3 cards for an Underworld unit and draw it (the
    deck_search seam, mandatory-if-able)."""
    from swu.engine.actions import push_deck_search
    from swu.cards.models import Unit

    def eligible(cd):
        return isinstance(cd, Unit) and "Underworld" in (getattr(cd, "traits", None) or ())

    push_deck_search(state, source_ci, count=1, eligible=eligible,
                     up_to=False, window=3)
    return state


@card_ability("LAW", "136")
def _syndicate_spice_runner():
    """LAW_136 — Syndicate Spice Runner (Unit, Underworld, 2/2): "When Played:
    Search the top 3 cards of your deck for an Underworld unit, reveal it, and draw
    it.  (Put the other cards on the bottom of your deck in a random order.)"

    A ``WhenPlayed`` whose one CustomEffect is a thin adapter onto the ``deck_search``
    seam (``push_deck_search``, the R2-D2 LAW_145 pattern): window=3, count=1,
    mandatory-if-able (no "up to" — an Underworld unit is taken if one is found),
    eligibility = a Unit carrying the Underworld trait; the rest are bottomed in a
    seeded-random order."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_spice_runner_search)],
    )


@card_ability("LAW", "246")
def _the_axe_forgets():
    """LAW_246 — The Axe Forgets (Event, Gambit): "Return a non-leader unit that
    costs 3 or less to its owner's hand."

    A plain ``EventAbility`` with one mandatory ``ReturnToHand`` targeting any
    non-leader unit whose printed cost is ≤ 3 (``controller="any"`` — the text omits
    "friendly"/"enemy", so either side's units are legal; the controller picks).
    Mandatory-if-able: fizzles cleanly with no eligible unit on the board."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="any", kind="unit",
                                predicates=("non_leader",), cost_max=3)),
    ])


def _jabba_play_underworld(state, source_ci, target_id, event_ctx):
    """Adapter (Jabba the Hutt deployed Action): push the play-from-hand decision
    restricted to Underworld units, granting Ambush this phase if a Credit was
    defeated while paying the played unit's cost (the Admiral Ozzel SOR_129 adapter
    pattern + the new ``grant_keyword_if_credit_spent`` field)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, trait="Underworld",
                        grant_keyword_if_credit_spent="Ambush")
    return state


@card_ability("LAW", "15")
def _jabba_the_hutt():
    """LAW_15 — Jabba the Hutt (Leader, Hutt/Underworld, 3/9, Ambush — keyword
    layer when deployed).

    Undeployed Action [1 resource, Exhaust, return a friendly Underworld unit to
    its owner's hand]: "Create a Credit token."  An ``undeployed_only``
    ActivatedAbility.  The "return a friendly Underworld unit" half of the cost is
    modelled as a leading ``ReturnToHand`` effect (there is no return-a-chosen-unit
    *cost* spec — the C-3PO SEC_93 return-as-effect pattern); the ability is gated
    by ``CONTROLLER_HAS_TRAIT_UNIT("Underworld")`` so it is offered only when such a
    unit exists to return, keeping the return a genuine cost (you cannot create a
    credit without paying it).  The targeted ``ReturnToHand`` is ordered before the
    non-targeted ``CreateCreditToken`` so the controller is prompted exactly once.

    Deployed Action: "Play an Underworld unit from your hand.  If you defeated a
    Credit while paying its cost, that unit gains Ambush for this phase."  A
    ``deployed_only`` costless ActivatedAbility whose one CustomEffect is a thin
    adapter onto the play-from-hand subsystem (``push_play_from_hand`` with
    ``grant_keyword_if_credit_spent="Ambush"``).  Gated by
    ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND("Underworld")`` so the costless action is
    never offered as a no-op (the Admiral Ozzel SOR_129 "don't offer a no-op"
    pattern); that gate counts credits toward affordability, so an Underworld unit
    affordable only by defeating a credit is offered (and then gains Ambush).

    The Epic Action deploy ("If you control 6 or more resources, deploy this
    leader") is the standard deploy_threshold machinery — no registration.

    LIMITATION (documented): credit-spend is need-based, so the deployed action
    grants Ambush only when the played unit's cost exceeds the controller's ready
    resources (a credit covers the shortfall); a player cannot deliberately spend
    a credit on an otherwise-affordable unit just to gain Ambush.  The undeployed
    action's "1 resource" cost is paid from ready resources only (credits are not
    spent on activated-ability resource costs)."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[
                ReturnToHand(TargetSpec(controller="friendly", kind="unit",
                                        traits=("Underworld",))),
                CreateCreditToken(),
            ],
            title="Return an Underworld unit to create a Credit token",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT,
                                     "Underworld"),
        ),
        ActivatedAbility(
            costs=[],
            effects=[CustomEffect(fn=_jabba_play_underworld)],
            title="Play an Underworld unit (Ambush if a Credit was spent)",
            deployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND,
                                     "Underworld"),
        ),
    ]


# ── Group jabba-the-hutt:05 — Combat tricks, buffs & tempo ────────────────────

def _4lom_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push a granted attack restricted to a friendly Bounty Hunter unit,
    even if exhausted, that can't attack bases (the Mon Mothma SEC_103 /
    Surprise Strike SOR_220 granted-attack seam)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True,
                        attacker_trait="Bounty Hunter",
                        allow_exhausted=True, no_base=True)
    return state


@card_ability("LAW", "65")
def _4_lom():
    """LAW_65 — 4-LOM (Unit, Bounty Hunter/Droid/Underworld, 4/5): "When Played:
    You may attack with a friendly Bounty Hunter unit, even if it's exhausted.  It
    can't attack bases for this attack."

    A mandatory ``WhenPlayed`` whose one CustomEffect is a thin adapter onto
    ``push_granted_attack`` (the granted-attack seam): ``optional=True`` for the
    "you may" (a single decision offering the eligible attacks + DeclineGrantedAttack),
    ``attacker_trait="Bounty Hunter"`` restricts the attacker, ``allow_exhausted=True``
    offers exhausted Bounty Hunters too, and ``no_base=True`` drops the attack-a-base
    option.  4-LOM is itself a Bounty Hunter, so it is a valid attacker (the text
    says "a friendly Bounty Hunter unit", not "another").  With no eligible attacker
    the controller simply declines."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_4lom_attack)],
    )


@card_ability("LAW", "158")
def _khetanna():
    """LAW_158 — Khetanna (Unit, Speeder/Underworld/Vehicle, 2/4): "When Played/On
    Attack: The next Underworld unit you play this phase costs 1 resource less."

    Two triggers (a ``WhenPlayed`` and an ``OnAttack``), each adding a deferred
    ``NextPlayDiscount("Underworld", 1)`` for the controller — a *pending* discount
    recorded in ``game_memory.pending_play_discounts`` (the play-cost path
    ``_play_cost`` reads it and the real play site ``PlayCard`` consumes one matching
    entry), unlike a static ``CostReduction`` on the card's own cost.  Two Khetanna
    triggers stack as two separate "next unit" discounts (each applies to a
    different subsequent Underworld unit).  The discount lifts at the phase rollover.

    LIMITATION (documented): the discount is applied/consumed only on the normal
    hand-play path (``PlayCard``) and its affordability gates, not on the
    ability-driven play-from-hand subsystem (which pays the raw effective cost, like
    Exploit), so a Khetanna discount does not stack onto an Underworld unit played by
    Jabba the Hutt's deployed action.  This is the common, faithful case."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[NextPlayDiscount("Underworld", 1)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[NextPlayDiscount("Underworld", 1)]),
    ]


def _haymaker_token_record(state, source_ci, target_id, event_ctx):
    """Give the chosen friendly unit an Experience token, then record its
    *post-token* power, arena, and name so the follow-up damage effect can deal "its
    power" to an enemy unit "in the same arena"."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, unit = res
    from swu.engine.tokens import attach_token
    attach_token(state, ps, unit, "Experience")
    from swu.engine.actions import compute_power
    from swu.engine.state import Zone
    event_ctx["haymaker_power"] = compute_power(state, unit)
    event_ctx["same_arena"] = "ground" if unit.zone == Zone.GROUND_ARENA else "space"
    event_ctx["haymaker_source_name"] = unit.card_def.display_name
    return state


def _haymaker_damage(state, source_ci, target_id, event_ctx):
    """Deal the recorded power (the buffed friendly unit's power) to the chosen
    enemy unit in the same arena."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("haymaker_power", 0) or 0)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = event_ctx.get("haymaker_source_name") or source_ci.card_def.display_name
    return _apply_deal_damage(state, target_id, amount, name)


@card_ability("LAW", "168")
def _haymaker():
    """LAW_168 — Haymaker (Event, Tactic): "Give an Experience token to a friendly
    unit.  That unit deals damage equal to its power to an enemy unit in the same
    arena."

    Two sequential, dependent effects sharing the resolve_effects decision's
    ``event_ctx`` (the Nothing Left to Fear LAW_41 pattern): a mandatory
    CustomEffect.target picks the friendly unit, gives it an Experience token, and
    records its *post-token* power + arena; the second CustomEffect.target deals that
    recorded power to a chosen enemy unit restricted to the recorded arena (the new
    ``same_arena_as_event`` predicate).  Each is mandatory-if-able — no friendly unit
    ⇒ nothing happens; no enemy unit in that arena ⇒ the damage step fizzles."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_haymaker_token_record,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        CustomEffect(
            fn=_haymaker_damage,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("same_arena_as_event",)),
        ),
    ])


@card_ability("LAW", "210")
def _salacious_crumb():
    """LAW_210 — Salacious Crumb (Unit, Creature/Underworld, 0/2, Raid 2 — keyword
    layer): "If you control Jabba the Hutt (as a leader or unit), this unit enters
    play ready."

    An ``EntersPlayReady`` spec gated by ``CONTROLLER_CONTROLS_NAMED("Jabba the
    Hutt")`` — read by ``_put_unit_in_play`` when Salacious Crumb itself enters play:
    if the controller has a Jabba the Hutt in play (the leader deployed in an arena
    or undeployed in the base zone, or a Jabba unit), it enters ready instead of the
    default exhausted.  Raid 2 is the keyword layer."""
    return EntersPlayReady(
        condition=ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED,
                                 "Jabba the Hutt"),
    )


def _weequay_token(state, source_ci, target_id, event_ctx):
    """If no resources were paid to play this unit (the play's recorded
    ``cost_paid`` is exactly 0), give it an Experience token.  An unknown cost
    (``None`` — a play path that does not record one) is treated as "resources were
    paid" (no token)."""
    if event_ctx.get("cost_paid") != 0:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    ps, unit = res
    from swu.engine.tokens import attach_token
    attach_token(state, ps, unit, "Experience")
    return state


@card_ability("LAW", "231")
def _weequay_pirate():
    """LAW_231 — Weequay Pirate (Unit, Underworld, 2/3, Saboteur — keyword layer):
    "When Played: If no resources were paid to play this unit, give an Experience
    token to it."

    A ``WhenPlayed`` whose one CustomEffect reads the play's recorded ``cost_paid``
    from the enter-play ``event_ctx`` (threaded by ``_put_unit_in_play``): when it is
    exactly 0 (the unit was played for free / its cost was reduced to 0), it gives
    itself an Experience token (no player choice → resolves inline).  Saboteur is the
    keyword layer."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_weequay_token)],
    )


# ── Group jabba-the-hutt:06 — Miscellaneous abilities ─────────────────────────

@card_ability("LAW", "212")
def _malakili():
    """LAW_212 — Malakili (Unit, Underworld, 2/4): "Each friendly Creature unit and
    each Creature unit you own that isn't in play gains the Underworld trait."

    A ``ConstantAbility`` whose (non-SELF) target is every friendly Creature unit,
    granting the Underworld trait.  This is the first *arena-wide* TraitGrant: the
    trait query layer (``swu.engine.traits``) now scans in-play units for a
    ConstantAbility TraitGrant whose target matches the queried unit (in addition to
    the existing attached-upgrade scan), so a friendly Creature in play counts as
    Underworld everywhere the trait layer is consulted (target matching, the
    trait-gated Conditions, the select_token/distribute trait filters) — e.g. Black
    Sun Cabalist LAW_249's "another friendly Underworld unit" or Jabba the Hutt's
    "an Underworld unit".

    DEVIATION (documented): the "and each Creature unit you own that isn't in play
    gains the Underworld trait" clause is NOT implemented.  The trait query layer is
    a read over *in-play* ``CardInstance``s, whereas out-of-play trait gates read a
    card's printed ``card_def.traits`` directly (the play-from-hand ``trait`` filter,
    the deck_search eligibility closures, etc.).  Routing every out-of-play trait
    read through a state-aware ``has_trait`` is a broad change to those card-specific
    paths, out of scope for a card batch; flagged for a future session if a card ever
    needs a granted-while-out-of-play trait.  The in-play clause (the common, board-
    relevant case) is faithful."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Creature",)),
        effects=[TraitGrant("Underworld")],
    )


def _vermillion_attack_ends(state, source_ci, target_id, event_ctx):
    """Adapter: push the reveal-a-deck-top → a chosen player plays it free → a
    different player makes Credits = its cost decision (the new
    ``reveal_play_credit`` multi-decider seam)."""
    from swu.engine.actions import push_reveal_play_credit
    push_reveal_play_credit(state, source_ci)
    return state


@card_ability("LAW", "215")
def _vermillion():
    """LAW_215 — Vermillion (Unit, Capital Ship/Underworld/Vehicle, 5/7): "When
    Attack Ends: If this unit survived, reveal the top card of a deck, then choose
    a player.  They may play the revealed card for free.  If they do, a different
    player creates Credit tokens equal to that card's cost."

    A mandatory ``WhenAttackEnds`` trigger (the new "attack ends / this unit
    survived" combat trigger — fired for the attacker at the end of both combat
    pipelines only if it is still in play) whose one CustomEffect is a thin adapter
    onto the new ``reveal_play_credit`` multi-decider decision kind
    (``push_reveal_play_credit``, the Palpatine SOR_135 adapter pattern): the
    controller chooses which deck's top card to reveal and which player may play it
    for free; if that player plays it, the OTHER player makes Credit tokens equal to
    its printed cost.  The played card is removed from the revealed deck and played
    (unit / event / upgrade) for free under the chosen player's control via the
    normal play paths, so its own keyword / When Played abilities fire.

    LIMITATION (documented): the played card's ``owner_id`` is left unchanged
    (control is implicit in this engine — the Stolen Landspeeder SHD_161
    convention), so when the controller hands the play to a player who does NOT own
    the revealed card (a cross-deck play), that card's own abilities resolve from
    its OWNER's perspective, not the playing player's.  The common cases (a player
    plays their own deck's card) are exact.  An attack aborted before combat damage
    by a pre-combat removal of the defender does not count as the attack "ending"
    for this trigger (the firing site is the combat-damage completion path)."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_vermillion_attack_ends)],
    )


@card_ability("LAW", "249")
def _black_sun_cabalist():
    """LAW_249 — Black Sun Cabalist (Unit, Underworld, 1/3): "When Played: Give an
    Experience token to another friendly Underworld unit."

    A ``WhenPlayed`` ``GiveToken("Experience", …)`` targeting another (``not_self``)
    friendly Underworld unit, mandatory-if-able — the controller picks among their
    other Underworld units; fizzles silently if there is none."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience",
                           TargetSpec(controller="friendly", kind="unit",
                                      traits=("Underworld",),
                                      predicates=("not_self",)))],
    )


def _double_cross_record_friendly(state, source_ci, target_id, event_ctx):
    """Record the chosen friendly non-leader unit; the exchange happens in the
    second (enemy-target) effect once both units are known."""
    if target_id is not None:
        event_ctx["double_cross_friendly_id"] = target_id
    return state


def _double_cross_exchange(state, source_ci, target_id, event_ctx):
    """Exchange control of the recorded friendly unit and the chosen enemy unit,
    then give the player who now controls the lower-cost unit Credit tokens equal
    to the cost difference.  No-op unless BOTH units were chosen (the exchange is
    all-or-nothing)."""
    from swu.engine.actions import change_control
    from swu.engine.tokens import create_credit_token

    fci_id = event_ctx.get("double_cross_friendly_id")
    eci_id = target_id
    if fci_id is None or eci_id is None:
        return state
    fres = state.find_instance(fci_id)
    eres = state.find_instance(eci_id)
    if fres is None or eres is None:
        return state
    _, fci = fres
    _, eci = eres

    my_id = source_ci.owner_id
    opponent_id = state.players[1 - state.player_index(my_id)].player_id
    f_cost = int(getattr(fci.card_def, "cost", 0) or 0)
    e_cost = int(getattr(eci.card_def, "cost", 0) or 0)

    # Exchange control: my friendly unit goes to the opponent, the enemy unit
    # comes to me (the two units sit in different arenas, so order is immaterial).
    change_control(state, fci, opponent_id)
    change_control(state, eci, my_id)

    # The player who takes control of the lower-cost unit creates Credit tokens
    # equal to the difference.  Opponent now controls the (formerly friendly)
    # unit; I now control the (formerly enemy) unit.
    diff = abs(f_cost - e_cost)
    if diff > 0:
        beneficiary_id = opponent_id if f_cost < e_cost else my_id
        beneficiary_ps = state.player_by_id(beneficiary_id)
        for _ in range(diff):
            create_credit_token(state, beneficiary_ps)
    return state


@card_ability("LAW", "170")
def _double_cross():
    """LAW_170 — Double-Cross (Event, Trick): "Choose a friendly non-leader unit
    and an enemy non-leader unit.  Exchange control of those units.  The player who
    takes control of the lower-cost unit creates Credit tokens equal to the
    difference between those units' costs."

    Two sequential, dependent effects sharing the resolve_effects decision's
    ``event_ctx`` (the Nothing Left to Fear LAW_41 / Haymaker LAW_168 pattern): a
    mandatory ``CustomEffect.target`` picks the friendly non-leader unit and records
    its id; the second ``CustomEffect.target`` picks the enemy non-leader unit, then
    performs the whole exchange — relocating each unit to the other player's arena
    via the ``change_control`` primitive (shd-han-solo:02; control is implicit =
    arena membership, owner unchanged) and creating Credit tokens (jabba-the-hutt:07)
    for whichever player now controls the lower-cost unit.  Both targets are
    required (the exchange is all-or-nothing): with no friendly OR no enemy
    non-leader unit the second effect no-ops.

    SCOPE/LIMITATION (the documented control-change convention): "friendly"/"enemy"
    resolve by ``owner_id`` in the target matcher, which equals the controller in
    every normal case — only a unit whose control was ALREADY changed by an earlier
    effect would diverge (the same limitation noted on ``actions.change_control``).
    Costs use the units' printed ``card_def.cost`` (the Credit-token convention)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_double_cross_record_friendly,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("non_leader",)),
        ),
        CustomEffect(
            fn=_double_cross_exchange,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("non_leader",)),
        ),
    ])


# ── Reprint-duplicate encode (Stage 4 of docs/reprint_duplicates_plan.md) ─────

@card_ability("LAW", "131")
def _incapacitate():
    """LAW_131 — Incapacitate (Event, 2): "Give a unit -2/-2 for this phase."

    A plain ``EventAbility`` with a single negative ``ModifyStats`` (the Moment of
    Glory SHD_130 pattern, debuff instead of buff) targeting any unit; the
    controller points it at an enemy.  Fizzles harmlessly with no unit in play."""
    return EventAbility(effects=[
        ModifyStats(power=-2, hp=-2,
                    target=TargetSpec(controller="any", kind="unit"),
                    duration=Duration.THIS_PHASE),
    ])


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonical, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

@card_ability("LAW", "57")
def _benthic_two_tubes():
    """LAW_57 — Benthic "Two Tubes" (Unit, 3/2): "On Attack: Deal 1 damage to an
    enemy ground unit.  When Defeated: Deal 1 damage to a base."

    Two plain mandatory triggers: an ``OnAttack`` dealing 1 to a chosen enemy
    ground unit (fizzles cleanly with none), and a ``WhenDefeated`` dealing 1 to a
    chosen base (``controller="any"`` — "a base"; the controller points it at the
    enemy base)."""
    return [
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                              arena="ground"))]),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))]),
    ]


@card_ability("LAW", "79")
def _k_2so():
    """LAW_79 — K-2SO (Unit, Rebel/Droid, Ambush): "On Attack: You may deal 3
    damage to a damaged ground unit."

    Ambush is the keyword layer.  An optional ``OnAttack`` dealing 3 to a chosen
    damaged ground unit (``controller="any"`` — "a unit"; the controller points it
    at an enemy).  Auto-declines when no damaged ground unit is on the board."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[DealDamage(3, TargetSpec(controller="any", kind="unit",
                                          arena="ground",
                                          predicates=("damaged",)))],
    )


def _daring_delve(state, source_ci, target_id, event_ctx):
    """Adapter: discard the top 2 cards of the controller's deck, then let the
    controller return one of *those* cards to hand if it is an Aggression card.

    "Discard 2 cards from your deck" mills the top two (no choice — the deck is
    ordered).  The optional return reuses the ``return_from_discard`` decision kind
    (Admiral Trench TWI_86 pattern): ``eligible`` keeps Aggression-aspect cards and
    ``eligible_instance`` keeps only the two just-milled ids ("discarded this way"),
    so an Aggression card already in the discard pile is not offered.  Pushed only
    when a milled card qualifies, else fizzles cleanly."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_return_from_discard

    ps = state.player_by_id(source_ci.owner_id)
    milled_ids = []
    for _ in range(2):
        if not ps.deck:
            break
        card = ps.deck.pop(0)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        milled_ids.append(card.instance_id)

    milled = set(milled_ids)

    def _is_aggression(card_def) -> bool:
        return "Aggression" in {a.name for a in (getattr(card_def, "aspects", None) or ())}

    def _was_milled(ci) -> bool:
        return ci.instance_id in milled

    push_return_from_discard(
        state, source_ci, count=1, up_to=True,
        eligible=_is_aggression, eligible_instance=_was_milled,
    )
    return state


@card_ability("LAW", "203")
def _daring_delve_card():
    """LAW_203 — Daring Delve (Event, Gambit): "Discard 2 cards from your deck. You
    may return an Aggression card discarded this way to your hand."

    A plain ``EventAbility`` whose one no-target ``CustomEffect`` mills the top two
    cards, then offers an "up to 1" ``return_from_discard`` over those Aggression
    cards (see ``_daring_delve``)."""
    return EventAbility(effects=[CustomEffect(fn=_daring_delve)])


def _interrogation_droid(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen enemy unit; then, if it costs 3 or less, its controller
    (the opponent) discards a card from their hand.  Bound in one CustomEffect so
    the conditional discard keys off the same chosen unit (the "If you do and that
    unit costs 3 or less" rider).  DEVIATION: the opponent discard uses the
    established first-card simplification (K-2SO SOR_145 / Garindan SEC_186) — the
    forced downside is faithful, the *which* card is not chosen."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    unit.exhausted = True
    if (getattr(unit.card_def, "cost", 0) or 0) <= 3:
        from swu.engine.state import Zone
        opp = state.players[1 - state.player_index(source_ci.owner_id)]
        if opp.hand:
            ci = opp.hand.pop(0)
            ci.zone = Zone.DISCARD
            opp.discard.append(ci)
    return state


@card_ability("LAW", "75")
def _interrogation_droid_card():
    """LAW_75 — Interrogation Droid (3/1): "When Played: Exhaust an enemy unit. If
    you do and that unit costs 3 or less, its controller discards a card from their
    hand."

    A mandatory ``WhenPlayed`` whose one ``CustomEffect.target`` (an enemy unit)
    exhausts the chosen unit and, when its cost is ≤ 3, makes the opponent discard
    (the conditional discard bound into the same effect so it keys off the chosen
    unit).  Fizzles cleanly with no enemy unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_interrogation_droid,
            target=TargetSpec(controller="enemy", kind="unit"))],
    )


@card_ability("LAW", "33")
def _hounds_tooth():
    """LAW_33 — Hound's Tooth (4/8): "When Attack Ends: If this unit survived, you
    may defeat a unit with less power than this unit."

    An optional ``WhenAttackEnds`` trigger (fires only for an attacker that survived
    its attack — the Pong Krell LOF_38 / Vermillion LAW_215 seam) whose one
    ``DefeatUnit`` targets any unit whose *effective* power is strictly less than
    Hound's Tooth's own effective power (the ``power_less_than_captor`` predicate,
    whose captor falls back to the ability's source unit — Legal Authority SHD_124).
    ``controller="any"`` matches the printed "a unit"; the optional trigger
    auto-declines when no weaker unit qualifies."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[DefeatUnit(TargetSpec(
            controller="any", kind="unit",
            power_less_than_captor=True))],
        optional=True,
    )


# ---------------------------------------------------------------------------
# Reprint-duplicate batch 6 (2026-07-08)
# ---------------------------------------------------------------------------


@card_ability("LAW", "34")
def _chewbacca_law34():
    """LAW_34 — Chewbacca (Unit, Overwhelm): "When Attack Ends: If the defending
    unit was defeated, give an Experience token to this unit and heal 3 damage
    from him."

    "When Attack Ends: if the defending unit was defeated" (with the attacker
    surviving — a defeated Chewbacca gets nothing) is exactly the existing
    ``OnAttackDefeatsUnit`` trigger (fires when the source, as attacker, defeats
    the defender and survives; a base attack defeats no *unit* so it does not
    fire).  Both effects are fixed on SELF and resolve inline — no player choice
    (the Oggdo Bogdo LOF_63 self-heal pattern).  Overwhelm is the keyword layer."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[
            GiveToken("Experience", TargetSpec(fixed=SELF)),
            Heal(3, TargetSpec(fixed=SELF)),
        ],
    )


@card_ability("LAW", "68")
def _millennium_falcon_law68():
    """LAW_68 — Millennium Falcon (Unit): "On Attack: You may give a space unit
    −2/−0 for this phase.  You may give a ground unit +2/+0 for this phase."

    Two INDEPENDENT optional On Attack effects → registered as two separate
    single-effect ``OnAttack`` abilities (the Sabine's Masterpiece JTL_250 / Leia
    LAW_10 "separate single-effect abilities" pattern), each a ``ModifyStats``
    with a ``THIS_PHASE`` duration and an arena filter.  ``controller="any"``
    mirrors the printed "a space/ground unit" (the −2/−0 you point at an enemy
    space unit; the +2/+0 at a friendly ground unit).  Each optional trigger
    auto-declines when its arena is empty."""
    return [
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=-2, hp=0, target=TargetSpec(
                controller="any", kind="unit", arena="space"),
                duration=Duration.THIS_PHASE)],
            optional=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=2, hp=0, target=TargetSpec(
                controller="any", kind="unit", arena="ground"),
                duration=Duration.THIS_PHASE)],
            optional=True,
        ),
    ]


def _backed_by_the_hutts_fn(state, source_ci, target_id, event_ctx):
    """Create a Credit token, then (optionally) deal damage to one unit equal to the
    controller's total Credit tokens — the just-created one included.

    The order matters ("Create … then deal equal to the number of friendly Credit
    tokens"), and a plain ``[CreateCreditToken, DealDamageEqualTo]`` two-effect list
    would double-prompt (the resolve_effects generator skips the no-target create
    and offers the damage target before the create runs).  So both are folded into
    one CustomEffect (the Never Tell Me the Odds JTL_208 inline-then-push pattern):
    create the credit inline, then reuse the ``select_damage`` decision
    (``max_targets=1`` = "you may deal to a unit"; "up to 1" honours the "may")."""
    from swu.engine.tokens import create_credit_token
    from swu.engine.actions import push_select_damage
    ps = state.player_by_id(source_ci.owner_id)
    create_credit_token(state, ps)
    amount = len(ps.credits)
    if amount > 0:
        push_select_damage(state, source_ci, amount_each=amount, max_targets=1)
    return state


@card_ability("LAW", "247")
def _backed_by_the_hutts_law247():
    """LAW_247 — Backed by the Hutts (Event, cost 3): "Create a Credit token. You
    may deal damage to a unit equal to the number of friendly Credit tokens."

    An ``EventAbility`` with one no-target ``CustomEffect`` (see the fn)."""
    return EventAbility(effects=[CustomEffect(fn=_backed_by_the_hutts_fn)])


# ── Reprint-sweep batch (2026-07-09) ─────────────────────────────────────────

def _rickety_quadjumper_law115(state, source_ci, target_id, event_ctx):
    """Reveal the top card of the controller's deck (read it in place — "leave it
    on top"); if it is NOT a unit, give an Experience token to another unit."""
    from swu.cards.models import Unit
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    top = ps.deck[0]
    if not isinstance(top.card_def, Unit):
        from swu.engine.actions import push_select_token
        push_select_token(state, source_ci, token_type="Experience",
                          max_targets=1, predicates=["not_self"])
    return state


@card_ability("LAW", "115")
def _rickety_quadjumper():
    """LAW_115 — Rickety Quadjumper (1/3 Fringe Vehicle Transport): "On Attack: You
    may reveal the top card of your deck.  If it's not a unit, give an Experience
    token to another unit.  (Leave the revealed card on top of your deck.)"

    An optional ``OnAttack`` whose one inline ``CustomEffect`` reads the deck top in
    place (the reveal is cosmetic — the card stays on top, the Han Solo JTL_17
    read-top pattern) and, when it is not a Unit, pushes the "up to 1" Experience
    ``push_select_token`` for another unit (``not_self``; ``controller="any"``
    mirrors the printed "another unit", the recipient benefits so never an enemy).
    An empty deck / a unit on top is a clean no-op."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(fn=_rickety_quadjumper_law115)],
    )


# ── Stage-4 reprint sweep (batch 11) — LAW cards ─────────────────────────────

def _secret_battle_fn(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen friendly unit, then let the controller exhaust up to
    (its distinct aspect count) enemy units in the same arena."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    from swu.engine.state import Zone
    from swu.engine.actions import push_exhaust_combined_cost
    unit.exhausted = True
    aspects = {a.name for a in (getattr(unit.card_def, "aspects", None) or ())}
    n = len(aspects)
    if n <= 0:
        return state
    arena = "ground" if unit.zone == Zone.GROUND_ARENA else "space"
    push_exhaust_combined_cost(
        state, source_ci, budget=None, max_units=n, arena=arena,
        controller="enemy")
    return state


@card_ability("LAW", "226")
def _secret_battle_of_pretend():
    """LAW_226 — Secret Battle of Pretend (Event, Trick): "Exhaust a friendly unit.
    If you do, for each different aspect it has, exhaust an enemy unit in the same
    arena."

    A single CustomEffect.target picks the friendly unit, exhausts it, and — for
    its distinct aspect count N — pushes an ``exhaust_combined_cost`` decision
    restricted to enemy units in that unit's arena, capped at N (the new
    ``controller`` filter on the Qui-Gon's Lightsaber LOF_201 seam; ``budget=None``
    = no cost cap).  The decision is pushed from inside the effect (the Ahsoka Tano
    JTL_201 inline-then-push pattern), landing nested beneath the buried
    resolve_effects decision.  DEVIATION (minor): "exhaust an enemy unit … for each
    aspect" is offered as "exhaust up to N" (the decision always allows finishing
    early) — exhausting enemy units only benefits the controller, so they max out.
    Fizzles cleanly when the chosen friendly unit has no aspects or no enemy unit
    shares its arena."""
    return EventAbility(effects=[CustomEffect(
        fn=_secret_battle_fn,
        target=TargetSpec(controller="friendly", kind="unit"))])


@card_ability("LAW", "52")
def _the_mandalorian_lets_see_the_puck():
    """LAW_52 — The Mandalorian, "Let's See the Puck" (Unit 6/5):
    "When Played: Draw a card.
     When you draw 1 or more cards during the action phase: Give a Shield token to
     this unit."

    The batch-16 ``WhenYouDraw`` observer (in-play flavour, ``on_self=False``): it
    fires once per ACTION-phase draw *event* for its controller (the ledger records
    one entry per ``_draw_cards`` batch), giving itself a Shield inline.  Its own
    "When Played: Draw a card" enters it into the ledger, so — since it is already in
    play by the settle-point drain — that first draw also feeds it a Shield (a
    separate ability, faithfully triggered)."""
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(count=1)]),
        TriggerAbility(
            trigger=WhenYouDraw(),
            effects=[GiveToken("Shield", TargetSpec(fixed=SELF))],
        ),
    ]


@card_ability("LAW", "93")
def _rio_durant():
    """LAW_93 — Rio Durant, "Beckett's Right Hands" (Unit 2/5): "When Played: You
    may return a non-leader unit that costs 3 or less to its owner's hand. Then,
    its owner may play it for free. It gains Shielded for this phase."

    The multi-decider return-then-owner-replays-free primitive (shared with Baylan
    Skoll LOF_185, but ungated — no Force token, and grants Shielded on the
    replay).  An optional ``WhenPlayed`` whose one ``CustomEffect`` (target = a
    non-leader unit costing ≤ 3, any controller) returns the chosen unit to its
    owner's hand (``_apply_return_to_hand``), then hands that owner an
    ``owner_may_replay`` decision to play it for FREE with "Shielded" granted for
    this phase (applied before the enter-play keyword bus, so the replayed unit
    gets a Shield token on entry).  The owner may be the source's opponent (the
    say_no SOR_233 deciding-player shift).  With no eligible unit the optional
    trigger auto-declines."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_owner_may_replay
        from swu.abilities.resolver import _apply_return_to_hand
        if target_id is None:
            return state
        _apply_return_to_hand(state, target_id)
        push_owner_may_replay(state, source_ci, target_id,
                              grant_keyword="Shielded")
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[CustomEffect(fn=_fn, target=TargetSpec(
            controller="any", kind="unit",
            predicates=("non_leader",), cost_max=3))],
    )


# ── Stage 4 batch 22 (2026-07-13) — FRAMEWORK ESCALATION: defeat-Credits-for-a-
#    scaling-payoff (the pay_resources_for_tokens decision kind generalised with a
#    cost_source="credit" cost item).  Canonical for the Cad Bane reprint group
#    (C26_5 / P26_80 / P26_96 aliased in reprints.py); all four faces are byte-
#    identical, so a single registration + same-face aliases.


@card_ability("LAW", "32")
def _cad_bane():
    """Cad Bane — Now It's My Turn: "Shielded. Overwhelm. On Attack: Defeat any
    number of friendly Credit tokens. Give an Experience token to this unit for each
    Credit defeated this way."

    Shielded/Overwhelm are the keyword layer.  The ability is a mandatory ``OnAttack``
    whose one no-target ``CustomEffect`` is a thin adapter (the Palpatine SOR_135
    inline-push pattern) onto the ``pay_resources_for_tokens`` decision, generalised
    with ``cost_source="credit"`` (defeat a Credit token per token) and an unbounded
    cap (``max_resources=None`` — "any number", bounded only by the credits held).
    "Any number" includes 0 via the always-offered FinishPayResources, so the
    mandatory trigger needs no ``optional`` flag; the push no-ops when no Credit token
    is held (a clean fizzle)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_pay_resources_for_tokens
        push_pay_resources_for_tokens(
            state, source_ci,
            max_resources=None, token_type="Experience", cost_source="credit")
        return state

    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_fn)])


# ── Luke Skywalker LAW_80 — opponent-decided modal (choose_two_modal, pick=1) ──
# "When Played: An opponent chooses one:
#    They create a Credit token. Ready this unit.
#    You may deal 5 damage to a unit."
# Reuses the choose_two_modal decision kind with the new ``decider_id`` opponent
# shift + pick=1.  idx 0 = the real WhenPlayed trigger (pushes the modal); idx 1/2
# = the two option specs — registered as EventAbility (NOT TriggerAbility) so that,
# because Luke is a UNIT in play, _collect_triggers (which collects only
# TriggerAbility) never fires them on his entry.  resolve_effects reads any spec's
# ``.effects``, and an EventAbility on a Unit is never run by _resolve_event_ability
# (that fires only for Event cards) — so the options are reached ONLY from the
# modal resolution.  See actions.push_choose_modal.

def _luke_law80_push_modal(state, source_ci, target_id, event_ctx):
    """idx 0: hand the opponent the "choose one" over options idx 1 (credit+ready)
    and idx 2 (deal 5)."""
    from swu.engine.actions import push_choose_modal
    opponent_id = next(p.player_id for p in state.players
                       if p.player_id != source_ci.owner_id)
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1,
                      decider_id=opponent_id)
    return state


def _luke_law80_opt_credit_ready(state, source_ci, target_id, event_ctx):
    """Option 1 (opponent's choice): the opponent creates a Credit token (for
    themselves — "They create …"), and Luke is readied."""
    from swu.engine.tokens import create_credit_token
    opponent_ps = next(p for p in state.players
                       if p.player_id != source_ci.owner_id)
    create_credit_token(state, opponent_ps)
    res = state.find_instance(source_ci.instance_id)
    if res is not None:
        res[1].exhausted = False
    return state


@card_ability("LAW", "80")
def _luke_skywalker_law80():
    """Luke Skywalker LAW_80 — the opponent-decided modal (the choose_two_modal
    ``decider_id`` extension, pick=1)."""
    return [
        # idx 0 — the real WhenPlayed trigger: hand the opponent the choice.
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_luke_law80_push_modal)]),
        # idx 1 — option A: opponent creates a Credit token, ready this unit.
        EventAbility(effects=[CustomEffect(fn=_luke_law80_opt_credit_ready)]),
        # idx 2 — option B: "You may deal 5 damage to a unit" (the controller's
        # choice; optional → a DeclineTarget is offered; no unit ⇒ fizzles).
        EventAbility(effects=[
            DealDamage(5, TargetSpec(controller="any", kind="unit", optional=True)),
        ]),
    ]

@card_ability("LAW", "89")
def _kanan_jarrus_law89():
    """Kanan Jarrus LAW_89 — Restore 1 (keyword layer).  When Played: You may
    return a non-leader unit that costs 2 or less to its owner's hand.  If you
    control a Command or Aggression unit, you may return a non-leader unit that
    costs 4 or less instead.

    The closest mirror to the Baylan/Rio return-to-hand primitive minus the
    replay — a plain optional ``WhenPlayed`` ``ReturnToHand`` (``controller="any"``:
    "a non-leader unit", not friendly/enemy).  The only new engine surface is the
    conditional cost cap on the target: ``cost_max=2`` normally, raised to 4 by
    ``cost_max_boost`` when the controller controls a Command or Aggression unit
    (Kanan himself is Cunning/Vigilance/Heroism, so he never self-satisfies the
    boost).  Being optional + targeted, the trigger auto-declines when no eligible
    unit is in play (the CustomEffect.target-style gate over ``ReturnToHand``)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ReturnToHand(TargetSpec(
            controller="any", kind="unit", predicates=("non_leader",),
            cost_max=2, cost_max_boost=(("Command", "Aggression"), 4),
        ))],
    )


# ── Stage 4 batch 30 (2026-07-13) — trivial straggler cleanup (NO new primitive):
#    Lawbringer LAW_101, "Choose an aspect. Give each enemy unit with that aspect
#    –2/–2 for this phase."  Composes entirely from the choose_two_modal pick=1
#    selector (batch 15/23 — "choose ONE of the listed options") + a mass negative
#    ``ModifyStats`` to ``EACH_ENEMY`` of the chosen aspect (the Encouraging
#    Leadership TWI_126 EACH_* pattern, but enemy + aspect-filtered).  The same
#    pick=1 insight that made Shatterpoint trivial covers "choose an aspect" (six
#    options, pick 1), so this needs zero engine code.
#
#    Lawbringer is a UNIT in play, so the six option specs are ``EventAbility``
#    (NOT ``TriggerAbility``) — the Luke LAW_80 lesson: _collect_triggers collects
#    only TriggerAbility, so registering the options as EventAbility keeps them from
#    firing on his entry, and an EventAbility on a Unit is never run by
#    _resolve_event_ability, so they resolve ONLY from the modal.  idx 0/1 = the two
#    real triggers ("When Played/On Attack"), each pushing the pick=1 modal over the
#    six aspect options idx 2..7.

_LAWBRINGER_ASPECTS = ("Vigilance", "Command", "Aggression",
                       "Cunning", "Heroism", "Villainy")


def _lawbringer_push_modal(state, source_ci, target_id, event_ctx):
    """idx 0/1: push the "choose an aspect" modal (pick=1) over the six aspect
    option specs (idx 2..7)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci,
                      option_indices=[2, 3, 4, 5, 6, 7], pick=1)
    return state


def _lawbringer_aspect_option(aspect: str) -> EventAbility:
    """One aspect option: give each enemy unit with ``aspect`` –2/–2 this phase
    (EACH_ENEMY auto-targets every matching enemy unit; a magnitude that drops a
    unit's remaining HP to 0 is caught by the state-based defeat sweep)."""
    return EventAbility(effects=[ModifyStats(
        power=-2, hp=-2,
        target=TargetSpec(controller="enemy", kind="unit",
                          aspects=(aspect,), fixed=EACH_ENEMY),
        duration=Duration.THIS_PHASE,
    )])


@card_ability("LAW", "101")
def _lawbringer_law101():
    """Lawbringer LAW_101 — "When Played/On Attack: Choose an aspect. Give each
    enemy unit with that aspect –2/–2 for this phase."  Zero new engine code (the
    choose_two_modal pick=1 selector + mass ModifyStats; see the section comment)."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_lawbringer_push_modal)]),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_lawbringer_push_modal)]),
        *[_lawbringer_aspect_option(a) for a in _LAWBRINGER_ASPECTS],
    ]


# ---------------------------------------------------------------------------
# Stage 4 batch 33 (2026-07-14) — source-linked control-revert primitive.
# ---------------------------------------------------------------------------

def _maul_law54_take_control(state, source_ci, target_id, event_ctx):
    """Maul LAW_54: take control of the chosen enemy non-leader unit, then LINK it
    so control reverts to its owner when Maul leaves play.  ``change_control``
    relocates the unit into Maul's controller's arena (owner_id unchanged, the
    implicit-control convention); ``control_linked_to`` marks the revert, resolved
    by actions._revert_linked_control on Maul's defeat."""
    from swu.engine.actions import change_control
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, ci = result
    change_control(state, ci, source_ci.owner_id)
    ci.control_linked_to = source_ci.instance_id
    return state


@card_ability("LAW", "54")
def _maul_master_of_the_shadow_collective():
    """Maul LAW_54 — Unit (7-cost 6/8, Overwhelm=keyword layer): "When Attack Ends:
    If this unit dealt combat damage to a player's base, you may take control of a
    non-leader unit that player controls.  When this unit leaves play, that unit's
    owner takes control of that unit."

    An optional ``WhenAttackEnds(require_base_damage=True)`` (the Vermillion LAW_215
    surviving-attacker seam, gated to a base attack via the new require_base_damage
    filter) whose one CustomEffect.target prompts for an enemy non-leader unit (the
    base-damaged player is the opponent in 2-player) and takes control of it via
    ``actions.change_control``, then links it with the new
    ``CardInstance.control_linked_to`` so control REVERTS to its owner when Maul
    leaves play (actions._revert_linked_control, fired from _defeat_unit — the
    capture leave-play precedent).  Reprint sibling P26_4 aliased in reprints.py."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_base_damage=True),
        effects=[CustomEffect(
            fn=_maul_law54_take_control,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("non_leader",)),
        )],
        optional=True,
    )


def _the_stranger_law86_defender_first(state, source_ci, target_id, event_ctx):
    """The Stranger LAW_86 On Attack: mark the attacker so the defending unit deals
    combat damage before it does this attack (actions._defender_deals_first, read at
    the unit-combat step; a this_attack flag cleared at the end of the attack)."""
    source_ci.defender_deals_first = True
    return state


@card_ability("LAW", "86")
def _the_stranger_law86():
    """LAW_86 — The Stranger (5-cost 5/? Ground, Cunning/Vigilance/Villainy;
    Ambush, Grit = keyword layer): "While attacking, you may have the defending unit
    deal combat damage before this unit."

    Defender-first-strike — the mirror of the attacker First Strike keyword, but
    chosen per-attack by the attacker.  Modelled as an optional ("you may")
    ``OnAttack`` trigger whose no-target CustomEffect sets the attacker's
    ``defender_deals_first`` this_attack flag; the combat step
    (actions._defender_deals_first, a new elif branch in _resolve_unit_combat_step2)
    then has the defender deal its combat damage first, and if that defeats the
    Stranger it deals none back.  The optional trigger IS the "you may" (Accept/
    Decline); a no-target effect is always offerable, so the choice is presented on
    every attack.  Reprint sibling P26_110 aliased in reprints.py."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(fn=_the_stranger_law86_defender_first)],
    )


@card_ability("LAW", "72")
def _max_rebo_law72():
    """LAW_72 — Max Rebo (4-cost Unit): "There is an additional regroup phase after
    the first regroup phase each round."

    The extra-regroup-phase turn-structure primitive.  A bare ``ExtraRegroupPhase``
    passive marker (the AttackRestriction / EntersPlayReady family), read only at the
    regroup-rollover site (actions._end_regroup via _extra_regroup_active): while any
    Max Rebo is in play, after the first regroup's ready step the engine re-enters a
    second regroup (a fresh draw-2 + resource + ready — the "Encore!" extra cards and
    resources) before rolling over to the next round.  A static condition, not
    additive: any number of copies still yields exactly one extra regroup (the
    ``regroup_count_this_round < 2`` cap).  No trigger, no decision — with no Max Rebo
    in play the turn structure is byte-identical.  Reprint siblings P26_82, P26_98
    aliased in reprints.py."""
    return ExtraRegroupPhase()


# ── Group law-set:01 — Direct damage & removal ────────────────────────────────
#
# Five leaders and two spells.  Every leader here reads the same way: an
# "Action [Exhaust, …]" on the UNDEPLOYED side (``undeployed_only=True``) and a
# combat trigger on the DEPLOYED side (``deployed_only=True``), with the printed
# "Epic Action: … deploy this leader" handled by the engine's generic
# DeployLeader path (no registration).


def _saw_suicide_attack(state, source_ci, target_id, event_ctx):
    """Adapter: "Attack with a unit.  It gets +2/+0 and gains Overwhelm for this
    attack.  After completing this attack, defeat it." (Saw Gerrera LAW_1,
    undeployed Action) — the granted-attack seam with ``then_defeat_attacker``."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        grant_keywords=["Overwhelm"], then_defeat_attacker=True)
    return state


def _saw_suicide_attack_again(state, source_ci, target_id, event_ctx):
    """The deployed twin: "you MAY attack with ANOTHER unit" — the same grant with
    ``optional`` (the decline) and ``exclude_source`` (Saw himself just attacked)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2,
                        grant_keywords=["Overwhelm"], then_defeat_attacker=True,
                        optional=True, exclude_source=True)
    return state


@card_ability("LAW", "1")
def _saw_gerrera():
    """LAW_1 — Saw Gerrera (Leader, Rebel): "Action [Exhaust]: Attack with a unit.
    It gets +2/+0 and gains Overwhelm for this attack.  After completing this
    attack, defeat it." / "When Attack Ends: If this unit survived, you may attack
    with another unit.  It gets +2/+0 and gains Overwhelm for this attack.  After
    completing this attack, defeat it."

    Both halves are the existing ``granted_attack`` seam, which already carries
    every piece: ``power_bonus``/``grant_keywords`` for the buff and
    ``then_defeat_attacker`` for the "after completing this attack, defeat it"
    rider.  The deployed half rides ``WhenAttackEnds``, whose "if this unit
    survived" clause is intrinsic to the trigger (it only fires for an attacker
    still in play after defeat processing), and adds ``optional`` + the
    ``exclude_source`` filter for "ANOTHER unit"."""
    return [
        ActivatedAbility(costs=[ExhaustSelf()],
                         effects=[CustomEffect(fn=_saw_suicide_attack)],
                         undeployed_only=True),
        TriggerAbility(trigger=WhenAttackEnds(),
                       effects=[CustomEffect(fn=_saw_suicide_attack_again)],
                       deployed_only=True),
    ]


@card_ability("LAW", "4")
def _aurra_sing():
    """LAW_4 — Aurra Sing (Leader, Bounty Hunter/Underworld): "Action [Exhaust]:
    Defeat a non-leader unit with 1 or less remaining HP." / "When Deployed: You
    may defeat a non-leader unit with 5 or less remaining HP."

    Two plain ``DefeatUnit`` effects whose whole content is the target filter: the
    ``non_leader`` predicate plus ``remaining_hp_le_N`` — the Cad Bane SEC_34
    predicate, generalised this batch so the threshold is read from the suffix
    instead of being hard-coded at 2.  Either player's unit qualifies
    (``controller="any"``, as printed); with no eligible unit the Action's effect
    simply fizzles and the optional trigger auto-declines."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DefeatUnit(TargetSpec(
                controller="any", kind="unit",
                predicates=("non_leader", "remaining_hp_le_1")))],
            undeployed_only=True),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[DefeatUnit(TargetSpec(
                controller="any", kind="unit",
                predicates=("non_leader", "remaining_hp_le_5")))],
            optional=True),
    ]


def _vader_discard_any_number(state, source_ci, target_id, event_ctx):
    """Adapter: "Discard any number of cards from your hand.  Deal damage to a unit
    or base equal to the number of cards discarded this way." (Darth Vader LAW_11,
    On Attack) — the new ``cull_for_damage`` decision kind over the hand pool."""
    from swu.engine.actions import push_cull_for_damage
    push_cull_for_damage(state, source_ci, pool="hand", allow_base=True)
    return state


@card_ability("LAW", "11")
def _darth_vader_law():
    """LAW_11 — Darth Vader (Leader, Force/Imperial/Sith): "Action [Exhaust,
    discard a card from your hand]: Deal 1 damage to a unit or base." / "On Attack:
    Discard any number of cards from your hand.  Deal damage to a unit or base
    equal to the number of cards discarded this way."

    The Action is the existing ``DiscardCardCost`` (Kylo Ren SHD_11) plus a flat
    ``DealDamage(1)`` — the cost gate means it is never offered on an empty hand.
    The On Attack half is the scaling twin and drives the new ``cull_for_damage``
    kind: pick any number of hand cards, then one damage per card, "a unit or base"
    being ``allow_base``.  Culling nothing is legal and simply deals no damage (the
    decision resolves without ever asking for a target)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), DiscardCardCost()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit_or_base"))],
            undeployed_only=True),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_vader_discard_any_number)],
                       deployed_only=True),
    ]


def _chewie_sacrifice_cost(state, source_ci, target_id, event_ctx):
    """Adapter for Chewbacca LAW_13's undeployed Action: the resource sacrifice is
    a COST (``mandatory``), and the payoff is 2 damage plus a Credit token."""
    from swu.engine.actions import push_sacrifice_resource_for_damage
    push_sacrifice_resource_for_damage(state, source_ci, amount=2,
                                       mandatory=True, create_credit=True)
    return state


def _chewie_sacrifice_may(state, source_ci, target_id, event_ctx):
    """The deployed twin — "You MAY defeat a friendly resource.  If you do, …"."""
    from swu.engine.actions import push_sacrifice_resource_for_damage
    push_sacrifice_resource_for_damage(state, source_ci, amount=2,
                                       create_credit=True)
    return state


@card_ability("LAW", "13")
def _chewbacca_law():
    """LAW_13 — Chewbacca (Leader, Underworld/Wookiee): "Action [1 resource,
    Exhaust, defeat a friendly resource]: Deal 2 damage to a unit and create a
    Credit token." / "On Attack: You may defeat a friendly resource.  If you do,
    deal 2 damage to a unit and create a Credit token."

    Both halves are the ``sacrifice_resource`` seam (Wrecker SHD_154), extended
    this batch with ``create_credit`` (the "and create a Credit token" half of the
    same "if you do" payoff) and ``mandatory`` — the undeployed version's sacrifice
    is a printed COST, so there is no decline, though the controller still chooses
    WHICH resource to give up.  The 1 resource and the exhaust are ordinary
    ``PayResources``/``ExhaustSelf`` costs on top."""
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()],
                         effects=[CustomEffect(fn=_chewie_sacrifice_cost)],
                         undeployed_only=True),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_chewie_sacrifice_may)],
                       deployed_only=True),
    ]


def _han_defeat_one_token(state, source_ci, target_id, event_ctx):
    """Adapter for Han Solo LAW_17's undeployed "Action [Exhaust, defeat a friendly
    token]: Deal 1 damage to a unit" — the ``cull_for_damage`` kind pinned to
    exactly one token (a cost: no decline, and 1 token = 1 damage)."""
    from swu.engine.actions import push_cull_for_damage
    push_cull_for_damage(state, source_ci, pool="tokens",
                         min_count=1, max_count=1)
    return state


def _han_defeat_any_tokens(state, source_ci, target_id, event_ctx):
    """The deployed twin — "Defeat any number of friendly tokens.  Deal damage to a
    unit equal to the number of tokens defeated this way."."""
    from swu.engine.actions import push_cull_for_damage
    push_cull_for_damage(state, source_ci, pool="tokens")
    return state


@card_ability("LAW", "17")
def _han_solo_law():
    """LAW_17 — Han Solo (Leader, Underworld, Saboteur): "Action [Exhaust, defeat a
    friendly token]: Deal 1 damage to a unit." / "On Attack: Defeat any number of
    friendly tokens.  Deal damage to a unit equal to the number of tokens defeated
    this way."

    The token twin of Vader LAW_11 above, on the same new ``cull_for_damage`` kind:
    the pool is the controller's tokens — token UNITS in the arenas and token
    UPGRADES (Experience / Shield) attached to their units alike, which is what
    "friendly token" means.  The Action pins the count to exactly 1 (a cost, hence
    no decline); the On Attack half is the open "any number".  Saboteur is the
    keyword layer — no registration."""
    return [
        ActivatedAbility(costs=[ExhaustSelf()],
                         effects=[CustomEffect(fn=_han_defeat_one_token)],
                         undeployed_only=True),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_han_defeat_any_tokens)],
                       deployed_only=True),
    ]


def _taramyn_credit_for_experience(state, source_ci, target_id, event_ctx):
    """"You may defeat a Credit token (belonging to any player).  If you do, give an
    Experience token to this unit and another friendly unit." (Taramyn Barcona
    LAW_40).

    OPTIMAL-PLAY COLLAPSE (the ``name_and_discard`` precedent): "belonging to any
    player" is a free choice, but a Credit is a fungible resource, so removing an
    OPPONENT's is never worse for the controller than removing their own — the
    opponent's is defeated when one exists, otherwise the controller's.  Both
    Experience tokens are given here, bound to the defeat, so the "if you do" is
    exact; ``target_id`` is the "another friendly unit" the controller chose."""
    from swu.engine.tokens import attach_token
    from swu.engine.state import Zone
    controller = state.player_by_id(source_ci.owner_id)
    opponent = next((p for p in state.players
                     if p.player_id != source_ci.owner_id), None)
    donor = (opponent if opponent is not None and opponent.credits
             else (controller if controller.credits else None))
    if donor is None:
        return state
    credit = donor.credits.pop()
    credit.zone = Zone.DISCARD
    donor.discard.append(credit)
    attach_token(state, controller, source_ci, "Experience")
    result = state.find_instance(target_id) if target_id else None
    if result is not None:
        attach_token(state, result[0], result[1], "Experience")
    return state


@card_ability("LAW", "40")
def _taramyn_barcona():
    """LAW_40 — Taramyn Barcona (Unit, Rebel/Trooper): "When Played: You may defeat
    a Credit token (belonging to any player).  If you do, give an Experience token
    to this unit and another friendly unit."

    One optional ``WhenPlayed`` whose single targeted CustomEffect does the whole
    "if you do" atomically — one prompt, and the tokens can never land without the
    defeat.  Gated by the new ``ANY_PLAYER_HAS_CREDIT`` atom: Credits live in
    ``PlayerState.credits``, not an arena, so no target predicate can see them and
    without the gate the trigger would offer a choice that can do nothing."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.ANY_PLAYER_HAS_CREDIT),
        effects=[CustomEffect(
            fn=_taramyn_credit_for_experience,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)))],
        optional=True,
    )


def _single_reactor_ignition(state, source_ci, target_id, event_ctx):
    """"Defeat all units.  For each enemy unit defeated this way, deal 1 damage to
    its controller's base." (LAW_44).

    The enemy count is snapshotted BEFORE the sweep (afterwards there is nothing
    left to count), the sweep reuses the ``DefeatAllUnits`` effect body, and the
    base damage is dealt last — so a base-damage observer sees a board that has
    already been cleared, which is the printed order."""
    from swu.abilities.resolver import execute_effect, _apply_deal_damage
    from swu.cards.models import Base
    opponent = next((p for p in state.players
                     if p.player_id != source_ci.owner_id), None)
    n = len(opponent.ground_arena) + len(opponent.space_arena) if opponent else 0
    state = execute_effect(state, DefeatAllUnits(), source_ci, None, event_ctx)
    if n and opponent is not None and opponent.base_zone:
        base = next((b for b in opponent.base_zone
                     if isinstance(b.card_def, Base)), None)
        if base is not None:
            state = _apply_deal_damage(state, base.instance_id, n,
                                       source_ci.card_def.display_name)
    return state


@card_ability("LAW", "44")
def _single_reactor_ignition_event():
    """LAW_44 — Single Reactor Ignition (Event, Disaster/Tactic, cost 8): "Defeat
    all units.  For each enemy unit defeated this way, deal 1 damage to its
    controller's base."

    A single CustomEffect rather than ``DefeatAllUnits`` + a scaling damage effect,
    because the count must be taken BEFORE the board wipe — after it there is
    nothing left to scale off.  A deployed leader is a unit and is swept with the
    rest; the wipe itself is the shared ``DefeatAllUnits`` body, so Protection
    ("can't be defeated by enemy card abilities") is honoured exactly as elsewhere,
    and a protected enemy unit correctly still counts toward the damage only if it
    was actually defeated — it is counted before, so this is the one deliberate
    simplification: the count is "enemy units in play", the printed "defeated this
    way" differing only when an enemy unit is undefeatable."""
    return EventAbility(effects=[CustomEffect(fn=_single_reactor_ignition)])


# ── Group law-set:02 — Direct damage & removal ────────────────────────────────


@card_ability("LAW", "47")
def _baze_malbus():
    """LAW_47 — Baze Malbus (Unit, Rebel, Sentinel): "When 1 or more damage is
    healed from this unit: You may deal that much damage to a unit."

    The existing ``WhenUnitHealed`` observer (Silver Angel JTL_62) — a settle-drain
    over ``game_memory.heal_events``, whose entries now carry the AMOUNT beside the
    healed unit's id so "that much" is exact; the new ``event_healed_amount``
    scaling count reads it off the observer's event_ctx.  Sentinel is the keyword
    layer."""
    return TriggerAbility(
        trigger=WhenUnitHealed(),
        effects=[DealDamageEqualTo(target=TargetSpec(controller="any", kind="unit"),
                                   count="event_healed_amount")],
        optional=True,
    )


@card_ability("LAW", "51")
def _beilert_valance():
    """LAW_51 — Beilert Valance (Unit, Bounty Hunter/Underworld): "On Attack: Draw
    a card.  You may deal damage to a ground unit equal to the number of cards
    you've drawn this phase."

    The SEPARATE SINGLE-EFFECT ABILITIES pattern: a mandatory draw and an optional
    scaling damage are two ``OnAttack`` triggers, resolved in spec order — so the
    draw is already counted when the damage reads
    ``controller_cards_drawn_this_phase`` (Pre Vizsla TWI_10's count).  One ability
    with both effects would tie the optional "may" to the draw as well."""
    return [
        TriggerAbility(trigger=OnAttack(), effects=[DrawCards(1)]),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit", arena="ground"),
                count="controller_cards_drawn_this_phase")],
            optional=True,
        ),
    ]


@card_ability("LAW", "56")
def _cassian_andor():
    """LAW_56 — Cassian Andor (Unit, Rebel): "When a friendly unit's attack ends: If
    the defending unit was defeated, deal 2 damage to a base."

    Exactly the existing ``WhenFriendlyUnitAttacksAndDefeatsUnit`` observer (Darth
    Revan LOF_17): it fires off the ``attack_defeated_unit`` event_ctx key, so both
    printed clauses — a FRIENDLY unit attacked, and the defender died — are
    intrinsic to the match, leaving only the damage.  Cassian himself is a friendly
    unit and is not excluded."""
    return TriggerAbility(
        trigger=WhenFriendlyUnitAttacksAndDefeatsUnit(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


@card_ability("LAW", "58")
def _honor_bound_partisan():
    """LAW_58 — Honor-Bound Partisan (Unit, Rebel/Twi'lek): "When Played: Deal 1
    damage to a base." / "When Defeated: The next unit you play this phase costs 1
    resource less."

    Two plain triggers over existing primitives — a targeted ``DealDamage`` at a
    base of either player (as printed) and the deferred ``NextPlayDiscount``
    (Khetanna LAW_158), whose default ``units_only`` and phase scope are already the
    printed reading."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[DealDamage(1, TargetSpec(controller="any",
                                                         kind="base"))]),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[NextPlayDiscount(trait='', amount=1)]),
    ]


def _hammerhead_ram(state, source_ci, target_id, event_ctx):
    """"you may give this unit +4/+0 for this attack.  If you do, defeat this unit
    after completing this attack." (Defiant Hammerhead LAW_62).

    Both halves in ONE untargeted effect so the "if you do" cannot come apart: the
    this-attack stat modifier and the new one-shot ``defeat_after_attack`` flag, read
    at the end of every combat pipeline by ``actions._settle_defeat_after_attack``."""
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, source_ci.instance_id, 4, 0,
        Duration.THIS_ATTACK))
    source_ci.defeat_after_attack = True
    return state


@card_ability("LAW", "62")
def _defiant_hammerhead():
    """LAW_62 — Defiant Hammerhead (Unit, Capital Ship/Rebel/Vehicle): "On Attack:
    If this unit is attacking a unit, you may give this unit +4/+0 for this attack.
    If you do, defeat this unit after completing this attack."

    "If this unit is attacking a unit" is the new ``OnAttack(vs_unit=True)`` filter —
    a base attack carries a ``None`` defender on the AttackDeclared event, so the
    clause is a plain read at the existing firing point and the trigger is never
    even offered on a base attack.  The rest is one optional untargeted effect (see
    ``_hammerhead_ram``); declining leaves the Hammerhead a plain 6/6 attacker."""
    return TriggerAbility(
        trigger=OnAttack(vs_unit=True),
        effects=[CustomEffect(fn=_hammerhead_ram)],
        optional=True,
    )


@card_ability("LAW", "64")
def _zuckuss():
    """LAW_64 — Zuckuss (Unit, Bounty Hunter/Underworld, Saboteur): "On Attack: If
    you control another Bounty Hunter unit, you may deal damage equal to this unit's
    power to a ground unit."

    An optional ``OnAttack`` gated by ``CONTROLLER_HAS_OTHER_TRAIT_UNIT("Bounty
    Hunter")`` — the atom already excludes the source, which is the printed
    "another" — dealing the ``source_power`` scaling count (Crosshair SHD_87), read
    as EFFECTIVE power so an upgrade or a this-attack buff counts.  Saboteur is the
    keyword layer."""
    return TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                                 param="Bounty Hunter"),
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
            count="source_power")],
        optional=True,
    )


def _skerris_defender_strafe(state, source_ci, target_id, event_ctx):
    """"You may deal 1 damage to a space unit AND exhaust it" (LAW_76) — one target,
    both halves, so the controller is prompted exactly once and the exhaust can
    never land without the damage."""
    from swu.abilities.resolver import _apply_deal_damage
    result = state.find_instance(target_id) if target_id else None
    if result is None:
        return state
    state = _apply_deal_damage(state, target_id, 1,
                               source_ci.card_def.display_name,
                               dealer_id=source_ci.owner_id,
                               source_id=source_ci.instance_id)
    still = state.find_instance(target_id)
    if still is not None:
        still[1].exhausted = True      # a unit defeated by the damage is not exhausted
    return state


@card_ability("LAW", "76")
def _vult_skerriss_defender():
    """LAW_76 — Vult Skerris's Defender (Unit, Fighter/Imperial/Vehicle): "When
    Played: If you discarded a card from your hand or deck this phase, give a Shield
    token to this unit." / "On Attack: You may deal 1 damage to a space unit and
    exhaust it."

    The When Played gate is the new ``CONTROLLER_DISCARDED_THIS_PHASE`` atom — the
    per-player reading of the ledger ``SELF_DISCARDED_THIS_PHASE`` already uses,
    resolving ownership off the discarded instance rather than storing it twice.
    The On Attack half is one optional targeted CustomEffect doing damage AND
    exhaust together."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            condition=ConditionCheck(Condition.CONTROLLER_DISCARDED_THIS_PHASE),
            effects=[GiveToken("Shield", TargetSpec(fixed=SELF))]),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(
                fn=_skerris_defender_strafe,
                target=TargetSpec(controller="any", kind="unit", arena="space"))],
            optional=True),
    ]


# ── Group law-set:03 — Direct damage & removal ────────────────────────────────


def _stygeon_regroup_base_damage(state, source_ci, target_id, event_ctx):
    """"When the regroup phase starts: Deal 2 damage to your base" (Shadow of
    Stygeon Prime LAW_77).

    A ``GrantedAbility`` resolves FROM THE HOST, so ``source_ci`` is the attached
    unit and "your base" is the base of whoever currently CONTROLS it — read off
    the board through ``find_instance`` rather than ``owner_id``, which never moves
    under a control change.  A fixed base needs no prompt."""
    from swu.abilities.resolver import _apply_deal_damage
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    host_ps, _host = res
    base = host_ps.base_instance
    if base is None:
        return state
    return _apply_deal_damage(state, base.instance_id, 2,
                              "Shadow of Stygeon Prime",
                              dealer_id=host_ps.player_id)


@card_ability("LAW", "77")
def _shadow_of_stygeon_prime():
    """LAW_77 — Shadow of Stygeon Prime (Upgrade, Condition; attach to a non-leader
    unit): "Attached unit can't ready.  It gains: 'When the regroup phase starts:
    Deal 2 damage to your base.'"

    The attach restriction is the engine's upgrade-target parser.  The residual is
    the Frozen in Carbonite SHD_193 pair, with the "gains" half instead of an
    exhaust: an unconditional ``ReadyRestriction`` carried by the upgrade (read by
    ``_ready_forbidden`` against the host, so the lock holds through every regroup)
    plus a ``GrantedAbility`` wrapping a ``PhaseStartTrigger("regroup")`` — the
    Foresight TWI_68 timing, and the wrapper is what makes "your base" follow the
    host rather than the player who played the Condition onto it."""
    return [
        ReadyRestriction(condition=None),
        GrantedAbility(TriggerAbility(
            trigger=PhaseStartTrigger(phase="regroup"),
            effects=[CustomEffect(fn=_stygeon_regroup_base_damage)],
        )),
    ]


_SABINE_VIGILANCE_OR_COMMAND = ConditionCheck(Condition.ANY_OF, param=(
    ConditionCheck(Condition.CONTROLLER_HAS_ASPECT_UNIT, param="Vigilance"),
    ConditionCheck(Condition.CONTROLLER_HAS_ASPECT_UNIT, param="Command"),
))


@card_ability("LAW", "78")
def _sabine_wren_law():
    """LAW_78 — Sabine Wren (Unit, Mandalorian/Rebel/Spectre, Ambush): "When Played:
    You may defeat a non-<uq> upgrade.  If you control a Vigilance or Command unit,
    you may defeat an upgrade instead."

    The clause changes the CANDIDATE SET, not a magnitude, so it cannot ride inside
    one CustomEffect (the Zeb LAW_45 shape): it is two optional ``WhenPlayed``
    triggers over COMPLEMENTARY conditions — the widened one gated on the new
    ``CONTROLLER_HAS_ASPECT_UNIT`` disjunction (source-inclusive: Sabine counts
    herself), the ``non_unique`` one on its ``NOT_OF`` negation, so exactly one is
    ever collected and the printed "instead" is exact.  Ambush is the keyword layer."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            condition=_SABINE_VIGILANCE_OR_COMMAND,
            effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade"))],
            optional=True,
        ),
        TriggerAbility(
            trigger=WhenPlayed(),
            condition=ConditionCheck(Condition.NOT_OF,
                                     param=_SABINE_VIGILANCE_OR_COMMAND),
            effects=[DefeatUnit(TargetSpec(controller="any", kind="upgrade",
                                           predicates=("non_unique",)))],
            optional=True,
        ),
    ]


def _you_hold_this_hand_over(state, source_ci, target_id, event_ctx):
    """Hand the chosen friendly non-leader unit to the opponent and record it, so
    the follow-up damage can find "another unit in the same arena" (You Hold This
    LAW_85).

    Control is implicit — ``change_control`` relocates the instance into the other
    player's arena and leaves ``owner_id`` alone (Stolen Landspeeder SHD_161)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, unit = res
    opponent = next((p for p in state.players if p.player_id != ps.player_id), None)
    if opponent is None:
        return state
    from swu.engine.actions import change_control
    from swu.engine.state import Zone
    arena = "ground" if unit.zone == Zone.GROUND_ARENA else "space"
    change_control(state, unit, opponent.player_id)
    event_ctx["prior_target_id"] = target_id
    event_ctx["excluded_target_id"] = target_id
    event_ctx["same_arena"] = arena
    return state


@card_ability("LAW", "85")
def _you_hold_this():
    """LAW_85 — You Hold This (Event, Trick): "Choose a friendly non-leader unit.
    An opponent takes control of it.  If they do, deal 4 damage to another unit in
    the same arena."

    The Haymaker LAW_168 shared-``event_ctx`` chain: a targeted CustomEffect gives
    the unit away and stamps ``prior_target_id`` / ``excluded_target_id`` /
    ``same_arena``, then a targeted ``DealDamage`` narrowed by
    ``requires_prior_target`` ("if they do"), ``same_arena_as_event`` and
    ``excludes_event_target`` ("another") — with nothing to give away, the damage
    step has no candidates and fizzles unprompted.  The gift itself is the whole
    cost, so the damage may hit either player's unit, as printed."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_you_hold_this_hand_over,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("non_leader",)),
        ),
        DealDamage(4, TargetSpec(controller="any", kind="unit",
                                 predicates=("requires_prior_target",
                                             "same_arena_as_event",
                                             "excludes_event_target"))),
    ])


def _governors_shuttle_mutual_defeat(state, source_ci, target_id, event_ctx):
    """Thin adapter onto the ``each_player_defeats`` decision (LAW_99)."""
    from swu.engine.actions import push_each_player_defeats
    push_each_player_defeats(state, source_ci, include_leaders=True)
    return state


@card_ability("LAW", "99")
def _governors_shuttle():
    """LAW_99 — Governor's Shuttle (Unit, Imperial/Transport/Vehicle, 2/4): "When
    Played: Each player chooses a unit they control.  Defeat those units."

    The Merciless Contest TWI_238 decision verbatim (controller chooses first, a
    player with no unit is skipped, both defeats settle after the pop), with the new
    ``include_leaders`` widening: this card prints plain "a unit they control" with
    no non-leader clause, so a deployed leader is a legal — and often the only —
    pick.  The Shuttle has just entered play and is itself a legal choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_governors_shuttle_mutual_defeat)],
    )


def _choke_on_aspirations_damage(state, source_ci, target_id, event_ctx):
    """Hand the chosen friendly non-Vehicle unit to a one-target damage pool of 5,
    with the base heal riding on the finish (LAW_102)."""
    if target_id is None:
        return state
    from swu.engine.actions import push_distribute_damage
    push_distribute_damage(state, source_ci, 5, target_controller="friendly",
                           restrict_ids=[target_id], up_to=True,
                           then_heal_base_if_survives=True)
    return state


@card_ability("LAW", "102")
def _choke_on_aspirations():
    """LAW_102 — Choke on Aspirations (Event, Force, cost 1): "Deal up to 5 damage
    to a friendly non-Vehicle unit.  If it survives, heal damage from your base
    equal to the damage dealt this way."

    "Up to 5" is a magnitude the CONTROLLER picks, and no choose-a-number decision
    exists — so the unit is chosen by an ordinary targeted CustomEffect and the
    magnitude by the ``distribute_damage`` pool pinned to that one unit (the new
    ``restrict_ids`` whitelist + the long-standing ``up_to``), which is exactly a
    0-to-5 dial.  The payoff rides on the new ``then_heal_base_if_survives``,
    settled after the pop: a unit the damage defeated has left its arena and
    forfeits the heal, and assigning 0 heals nothing."""
    return EventAbility(effects=[CustomEffect(
        fn=_choke_on_aspirations_damage,
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("non_vehicle",)))])


def _defiant_scrapper_defeat_credit(state, source_ci, target_id, event_ctx):
    """Defeat one Credit token belonging to an opponent (LAW_106).

    Credits are fungible and live in ``PlayerState.credits``, so there is nothing to
    choose between two of them — the Taramyn LAW_40 body without its "any player"
    fallback, since this card may only take an ENEMY credit."""
    from swu.engine.state import Zone
    donor = next((p for p in state.players
                  if p.player_id != source_ci.owner_id and p.credits), None)
    if donor is None:
        return state
    credit = donor.credits.pop()
    credit.zone = Zone.DISCARD
    donor.discard.append(credit)
    return state


@card_ability("LAW", "106")
def _defiant_scrapper():
    """LAW_106 — Defiant Scrapper (Unit, Fringe, 3/4): "When Played: You may defeat
    an enemy Credit token."

    An optional ``WhenPlayed`` gated by the new ``OPPONENT_HAS_CREDIT`` atom — the
    enemy-narrowed sibling of ``ANY_PLAYER_HAS_CREDIT`` (Taramyn LAW_40).  A Credit
    is no arena card, so no target predicate can see one: without the gate the
    trigger would offer a choice that can do nothing."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.OPPONENT_HAS_CREDIT),
        effects=[CustomEffect(fn=_defiant_scrapper_defeat_credit)],
        optional=True,
    )


@card_ability("LAW", "124")
def _industrious_team():
    """LAW_124 — Industrious Team (Unit, Bounty Hunter/Underworld, 4/7): "When
    Played: You may defeat a non-leader unit with 4 or less remaining HP."

    Pure reuse: an optional ``WhenPlayed`` ``DefeatUnit`` over the generalised
    ``remaining_hp_le_<N>`` predicate (law-set:01's widening of Cad Bane SEC_34's
    ``remaining_hp_le_2``), which reads EFFECTIVE HP less damage, so an upgraded or
    buffed unit is out of reach exactly as printed.  Either player's unit is a legal
    target, and with none in range the trigger is not offered."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit",
                                       predicates=("non_leader",
                                                   "remaining_hp_le_4")))],
        optional=True,
    )


# ── Group law-set:04 — Direct damage & removal ────────────────────────────────


def _betrayed_trust_block(state, source_ci, target_id, event_ctx):
    """"For this phase, that unit can't deal combat damage." (LAW_130)

    A ``cannot_deal_combat_damage`` Modifier — the DEALER-side mirror of the
    ``damage_prevention`` modifier (Finn TWI_53), read by
    ``actions._combat_power_after_block`` at every point a combat pipeline turns a
    unit's power into an amount to deal.  The unit's power itself is untouched, so
    an "equal to its power" ability still reads the real number, and the modifier
    lapses with the ordinary this-phase sweep."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="cannot_deal_combat_damage",
        value={},
        duration=Duration.THIS_PHASE.value,
    ))
    return state


@card_ability("LAW", "130")
def _betrayed_trust():
    """LAW_130 — Betrayed Trust (Event, Trick, cost 2): "Choose an enemy unit.  For
    this phase, that unit can't deal combat damage."

    One targeted CustomEffect landing the new ``cannot_deal_combat_damage``
    modifier.  It covers attacking a unit, attacking a base, striking back as a
    defender and the multi-defender split alike, because all five go through the one
    blocking helper — and, unlike zeroing the unit's power, it leaves everything
    that merely READS power (Overwhelm's excess, "damage equal to its power")
    honest."""
    return EventAbility(effects=[CustomEffect(
        fn=_betrayed_trust_block,
        target=TargetSpec(controller="enemy", kind="unit"))])


def _the_tree_remembers(state, source_ci, target_id, event_ctx):
    """"An enemy unit loses all abilities for this phase.  If it costs 3 or less,
    defeat it." (LAW_132)

    ONE effect, so the two clauses can never come apart and the controller is
    prompted once: the phase-scoped ``abilities_suppressed`` modifier (the One Way
    Out SEC_157 arm of the unified ``state.ability_suppressed`` read-layer, which
    also gives "can't gain abilities" for free) and then the conditional defeat,
    read off the PRINTED cost."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="abilities_suppressed",
        value={},
        duration=Duration.THIS_PHASE.value,
    ))
    if int(getattr(res[1].card_def, "cost", 0) or 0) <= 3:
        from swu.abilities.resolver import _apply_defeat_unit
        state = _apply_defeat_unit(state, target_id)
    return state


@card_ability("LAW", "132")
def _the_tree_remembers_card():
    """LAW_132 — The Tree Remembers (Event, Tactic, cost 4): "An enemy unit loses all
    abilities for this phase.  If it costs 3 or less, defeat it."

    Pure reuse in one targeted CustomEffect — the suppression is a modifier (a
    DURATION the per-instance Mind Trick LOF_202 flag cannot carry), and the defeat
    is not a separate targeted effect, so a unit too expensive to kill still loses
    its abilities from the same single prompt."""
    return EventAbility(effects=[CustomEffect(
        fn=_the_tree_remembers,
        target=TargetSpec(controller="enemy", kind="unit"))])


@card_ability("LAW", "137")
def _ruthless_duo():
    """LAW_137 — Ruthless Duo (Unit, Bounty Hunter/Underworld, 3/5): "When Played: If
    you control another Villainy unit, you may deal 2 damage to a ground unit."

    Pure reuse: an optional ``WhenPlayed`` gated by ``CONTROLLER_HAS_OTHER_ASPECT_UNIT``
    ("another" is the atom's own source exclusion — the Duo is herself Villainy) with
    a plain targeted ``DealDamage``.  Failing the gate means the trigger is never
    collected, so there is no prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Villainy"),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground"))],
        optional=True,
    )


def _bt1_mill_and_arm(state, source_ci, target_id, event_ctx):
    """"Discard a card from your deck.  If it's Aggression, you may deal 1 damage to
    a ground unit." (BT-1 LAW_173)

    The Yoda TWI_4 "record then gate" shape: mill the top card, and arm the
    follow-up damage with ``prior_target_id`` ONLY when the discarded card carries
    the Aggression aspect — so a non-Aggression discard (or an empty deck) leaves
    the ``requires_prior_target`` target with no candidates and the damage step
    fizzles with no prompt."""
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
    aspects = {a.name for a in (getattr(card.card_def, "aspects", None) or ())}
    if "Aggression" in aspects:
        event_ctx["prior_target_id"] = card.instance_id
    return state


@card_ability("LAW", "173")
def _bt1():
    """LAW_173 — BT-1 (Unit, Droid/Underworld, 2/4): "On Attack: Discard a card from
    your deck.  If it's Aggression, you may deal 1 damage to a ground unit."

    A MANDATORY ``OnAttack`` (the mill always happens) whose leading non-targeted
    CustomEffect mills and arms, followed by a targeted ``DealDamage`` gated by
    ``requires_prior_target``.  The printed "you may" rides on the target being
    optional — the gate makes the damage unavailable rather than declinable when
    the discard misses, which is the same board state."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[
            CustomEffect(fn=_bt1_mill_and_arm),
            DealDamage(1, TargetSpec(controller="any", kind="unit", arena="ground",
                                     optional=True,
                                     predicates=("requires_prior_target",))),
        ],
    )


def _triple_zero_recycle(state, source_ci, target_id, event_ctx):
    """Thin adapter onto ``bottom_from_discard`` with the base-damage payoff
    (0-0-0 LAW_174)."""
    from swu.engine.actions import push_bottom_from_discard

    def _aggression(card_def):
        return "Aggression" in {a.name for a in (getattr(card_def, "aspects", None)
                                                 or ())}

    push_bottom_from_discard(state, source_ci, count=1, own_only=True,
                             eligible=_aggression, then_damage_enemy_base=1)
    return state


@card_ability("LAW", "174")
def _triple_zero():
    """LAW_174 — 0-0-0 (Unit, Droid/Underworld, 4/4): "On Attack: You may put an
    Aggression card from your discard pile on the bottom of your deck.  If you do,
    deal 1 damage to each enemy base."

    The Fives TWI_216 shape with a new payoff: ``push_bottom_from_discard`` narrowed
    to the controller's own pile and to Aggression cards, ``count=1``, with the new
    ``then_damage_enemy_base`` settled at the finish — so the "you may" is the
    decision's own decline (bottoming nothing deals nothing) and no Aggression card
    in the discard means no prompt at all."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_triple_zero_recycle)],
    )


def _persecutor_bomb(state, source_ci, target_id, event_ctx):
    """"Choose an arena.  You may deal 3 damage to each unit in that arena."
    (Persecutor LAW_178) — the Bombing Run SOR_173 arena modal verbatim."""
    from swu.engine.actions import push_modal
    push_modal(state, source_ci, ["bomb_ground", "bomb_space"])
    return state


@card_ability("LAW", "178")
def _persecutor():
    """LAW_178 — Persecutor (Unit, Capital Ship/Imperial/Vehicle, 9/7): "When Played:
    Choose an arena.  You may deal 3 damage to each unit in that arena." / the same
    On Attack.

    Two optional triggers over ONE adapter (the recurring LAW leader shape, here for
    a unit): the "you may" is the trigger's own decline, and the arena choice is
    ``push_modal``'s two fungible ``bomb_ground``/``bomb_space`` modes, which already
    deal exactly 3 to every unit in the chosen arena — including the Persecutor
    itself when it is the space arena, as printed.  An empty arena is not offered."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_persecutor_bomb)], optional=True),
        TriggerAbility(trigger=OnAttack(),
                       effects=[CustomEffect(fn=_persecutor_bomb)], optional=True),
    ]


@card_ability("LAW", "179")
def _fear_and_dead_men():
    """LAW_179 — Fear and Dead Men (Event, Tactic, cost 7): "This card costs 1
    resource less to play for each card discarded from your hand this phase.  Deal 4
    damage to each enemy ground unit."

    A ``CostReduction`` on the new ``per_controller_discard_this_phase`` basis — read
    at the single play-cost site, so it moves affordability AND the resources
    actually exhausted — plus a fixed ``EACH_ENEMY`` ``DealDamage`` narrowed to the
    ground arena (no prompt, and "all damage is dealt simultaneously" falls out of
    the inline expansion).  DOCUMENTED WIDENING: the ledger behind the count is fed
    by hand and deck discards alike, so a self-mill also discounts this card."""
    return [
        CostReduction(amount=1, per_controller_discard_this_phase=True),
        EventAbility(effects=[
            DealDamage(4, TargetSpec(fixed=EACH_ENEMY, kind="unit",
                                     arena="ground"))]),
    ]


# ── Group law-set:05 — Direct damage & removal ────────────────────────────────


@card_ability("LAW", "181")
def _cloud_rider_veteran():
    """LAW_181 — Cloud-Rider Veteran (Unit, Underworld, 1/4): "On Attack: Deal 2
    damage to a base."

    A plain mandatory ``OnAttack`` targeted ``DealDamage``.  "A base" names no
    controller, so either base is a legal choice, as printed."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


def _bwing_skirmisher_strafe(state, source_ci, target_id, event_ctx):
    """Thin adapter onto ``select_damage`` — "1 damage to each of up to 2 space
    units" (LAW_183)."""
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=2,
                       arena="space")
    return state


@card_ability("LAW", "183")
def _bwing_skirmisher():
    """LAW_183 — B-Wing Skirmisher (Unit, Fighter/Rebel/Vehicle, 4/4): "When Played:
    Deal 1 damage to each of up to 2 space units."

    The IG-2000 JTL_140 ``select_damage`` decision with the Twin Laser Turret
    JTL_172 ``arena`` narrowing: distinct picks, "up to" as the decision's own
    finish, and pop-then-deal so a defeat lands on a clean stack.  Either player's
    space units are eligible — the Skirmisher itself included, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_bwing_skirmisher_strafe)],
    )


@card_ability("LAW", "184")
def _aerie():
    """LAW_184 — Aerie (Unit, Transport/Underworld/Vehicle, 3/7): "On Attack: Deal 2
    damage to an enemy ground unit and 2 damage to a base."

    Two mandatory targeted effects — two genuinely separate choices, so two prompts
    is the printed reading (not the single-prompt C-3PO SEC_93 case).  Each is
    mandatory-if-able: with no enemy ground unit the first fizzles and the base
    damage still happens."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[
            DealDamage(2, TargetSpec(controller="enemy", kind="unit",
                                     arena="ground")),
            DealDamage(2, TargetSpec(controller="any", kind="base")),
        ],
    )


def _staccato_lightning_burst(state, source_ci, target_id, event_ctx):
    """Thin adapter onto ``select_damage`` — "1 damage to each of up to 3 different
    ground units" (LAW_187).  ``source_ci`` is the upgrade; the decision is addressed
    to its controller."""
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=3,
                       arena="ground")
    return state


@card_ability("LAW", "187")
def _staccato_lightning_repeater():
    """LAW_187 — "Staccato Lightning" Repeater (Upgrade, Item/Weapon; attach to a
    non-Vehicle unit): "When Played: Deal 1 damage to each of up to 3 different
    ground units."

    The attach restriction is the engine's upgrade-target parser.  "Different" is
    intrinsic to the ``select_damage`` decision, which only ever offers units not
    already chosen — so the card's residual is the same adapter as LAW_183, three
    picks wide and in the ground arena."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_staccato_lightning_burst)],
    )


@card_ability("LAW", "189")
def _cavern_angels_xwing():
    """LAW_189 — Cavern Angels X-Wing (Unit, Fighter/Rebel/Vehicle, 2/1): "When
    Defeated: Deal 2 damage to a base."

    A plain mandatory ``WhenDefeated`` targeted ``DealDamage`` — collected from the
    dying instance by the UnitDefeated path, so the 1-HP body trading itself for 2
    base damage works from any defeat."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="base"))],
    )


def _arvel_skeen_credit_burn(state, source_ci, target_id, event_ctx):
    """"You may defeat a Credit token (belonging to any player).  If you do, deal 1
    damage to a unit or base." (Arvel Skeen LAW_191)

    The Taramyn LAW_40 body: the OPTIMAL-PLAY COLLAPSE of "any player" (a Credit is
    fungible, so taking an opponent's is never worse) with the payoff bound into the
    same effect, so the "if you do" is exact and the controller is prompted once."""
    from swu.engine.state import Zone
    controller = state.player_by_id(source_ci.owner_id)
    opponent = next((p for p in state.players
                     if p.player_id != source_ci.owner_id), None)
    donor = (opponent if opponent is not None and opponent.credits
             else (controller if controller.credits else None))
    if donor is None:
        return state
    credit = donor.credits.pop()
    credit.zone = Zone.DISCARD
    donor.discard.append(credit)
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 1,
                              source_ci.card_def.display_name,
                              dealer_id=source_ci.owner_id,
                              source_id=source_ci.instance_id)


@card_ability("LAW", "191")
def _arvel_skeen():
    """LAW_191 — Arvel Skeen (Unit, Rebel, 4/3): "When Played/On Attack: You may
    defeat a Credit token (belonging to any player).  If you do, deal 1 damage to a
    unit or base."

    Two optional triggers over ONE targeted CustomEffect, gated by
    ``ANY_PLAYER_HAS_CREDIT`` (Taramyn LAW_40) — Credits live in
    ``PlayerState.credits``, which no target predicate can see, so without the gate
    the trigger would offer a choice that can do nothing."""
    fx = [CustomEffect(fn=_arvel_skeen_credit_burn,
                       target=TargetSpec(controller="any", kind="unit_or_base"))]
    gate = ConditionCheck(Condition.ANY_PLAYER_HAS_CREDIT)
    return [
        TriggerAbility(trigger=WhenPlayed(), condition=gate, effects=fx,
                       optional=True),
        TriggerAbility(trigger=OnAttack(), condition=gate, effects=fx,
                       optional=True),
    ]


@card_ability("LAW", "195")
def _overcharged_transport():
    """LAW_195 — Overcharged Transport (Unit, Transport/Vehicle, 4/3): "When
    Played/When Defeated: You may defeat an upgrade attached to a space unit."

    Two optional triggers over one ``DefeatUnit`` with ``kind="upgrade"``.  An
    attached upgrade carries its HOST's zone tag (the engine-wide invariant), so
    ``arena="space"`` is exactly "attached to a space unit"; either player's upgrade
    is eligible, and with none the trigger is not offered."""
    fx = [DefeatUnit(TargetSpec(controller="any", kind="upgrade", arena="space"))]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=fx, optional=True),
        TriggerAbility(trigger=WhenDefeated(), effects=fx, optional=True),
    ]


# -- Group law-set:06 -- Direct damage & removal -------------------------------

def _dogged_pursuers_pay_and_damage(state, source_ci, target_id, event_ctx):
    """Pay 1 resource, then deal 2 damage to the chosen ground unit.

    The Boba Fett LAW_214 binding verbatim (itself the Bright Hope SOR_99 "if you
    do" pattern): payment and damage live in ONE CustomEffect, so accepting the
    optional trigger commits to both and the damage cannot happen without the
    payment.  Affordability is guaranteed by the trigger's
    ``CONTROLLER_N_PLUS_READY_RESOURCES`` gate; the fn re-checks defensively."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state  # cannot pay -> no damage ("if you do")
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)


@card_ability("LAW", "198")
def _dogged_pursuers():
    """LAW_198 -- Dogged Pursuers (Unit, Bounty Hunter/Underworld, 5/5): "When
    Played: You may pay 1 resource.  If you do, deal 2 damage to a ground unit."

    Boba Fett LAW_214's shape with one trigger instead of two and 2 damage instead
    of 3: an optional WhenPlayed gated by ``CONTROLLER_N_PLUS_READY_RESOURCES(1)``
    so it is never offered when the resource cannot be paid, over a single
    ground-unit-targeted CustomEffect that pays and damages together.
    ``controller="any"`` mirrors the printed "a ground unit"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_dogged_pursuers_pay_and_damage,
            target=TargetSpec(controller="any", kind="unit", arena="ground"),
        )],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, 1),
    )


@card_ability("LAW", "201")
def _thermal_detonator():
    """LAW_201 -- Thermal Detonator (Upgrade, Item/Weapon, cost 3): "Attach to a
    non-Vehicle unit.  Attached unit gains: 'When Defeated: If this unit was ready,
    deal 2 damage to each enemy ground unit.'"

    The Armed to the Teeth SHD_175 ``GrantedAbility`` shape: the upgrade confers a
    triggered ability on its HOST, so the damage radiates from the host and "enemy"
    reads from the host's controller.  The attach restriction is parsed off the
    printed "Attach to a non-Vehicle unit" by ``_upgrade_target_spec`` -- no field
    needed here.

    "If this unit was ready" is the plain ``SOURCE_READY`` condition, which works
    unchanged at defeat time: ``_defeat_unit`` fires the WhenDefeated triggers BEFORE
    it resets the card's ``exhausted`` flag on its way to the discard pile, so the
    condition still reads the state the unit died in.  A detached upgrade is
    collected from ``event_ctx["defeated_upgrades"]``, which evaluates that condition
    against the host -- exactly the reading we want."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(fixed=EACH_ENEMY, kind="unit",
                                          arena="ground"))],
        condition=ConditionCheck(Condition.SOURCE_READY),
    ))


def _flash_the_vents_attack(state, source_ci, target_id, event_ctx):
    """Adapter: push the granted attack with +2/+0, Overwhelm, and the
    "defeat it if it damaged a base" rider."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, 2, 0,
                        grant_keywords=["Overwhelm"],
                        defeat_attacker_if_base_damaged=True)
    return state


@card_ability("LAW", "205")
def _flash_the_vents():
    """LAW_205 -- Flash the Vents (Event, Gambit, cost 1): "Attack with a unit.  It
    gets +2/+0 and gains Overwhelm for this attack.  After completing this attack, if
    that unit damaged a base, defeat that unit."

    ``push_granted_attack`` carries the first two clauses as-is (``power_bonus=2``
    plus the Shoot First SOR_218 ``grant_keywords`` seam).  The third is the new
    ``defeat_attacker_if_base_damaged`` rider -- the CONDITIONAL twin of Heroic
    Sacrifice SOR_150's ``then_defeat_attacker``, reading Stay on Target JTL_177's
    before/after base-damage snapshot so an Overwhelm spill onto the base counts
    exactly like a direct base attack (which is the whole point here: the +2/+0 and
    the granted Overwhelm are what push damage through onto a base)."""
    return EventAbility(effects=[CustomEffect(fn=_flash_the_vents_attack)])


@card_ability("LAW", "206")
def _thats_a_rock():
    """LAW_206 -- That's a Rock (Event, Gambit, cost 1): "Deal 1 damage to a unit.
    When this event is discarded from your hand or deck: You may deal 1 damage to a
    unit."

    Two independent abilities.  The played half is an ordinary ``EventAbility``.  The
    second is the new ``WhenThisIsDiscarded`` observer: a settle-drained trigger whose
    SOURCE is this very card sitting in its owner's DISCARD pile, fed by the existing
    ``note_hand_or_deck_discard`` chokepoint (so a hand discard, a self-mill and a
    deck-search discard all fire it) and collected by the dedicated discard-pile scan
    in ``_collect_triggers``.  Optional ("You may"), so declining costs nothing; with
    no unit on the board it fizzles without a prompt."""
    fx = [DealDamage(1, TargetSpec(controller="any", kind="unit"))]
    return [
        EventAbility(effects=list(fx)),
        TriggerAbility(trigger=WhenThisIsDiscarded(), effects=list(fx),
                       optional=True),
    ]


def _attack_from_all_sides_damage(state, source_ci, target_id, event_ctx):
    """Deal 3 damage to the chosen unit -- 5 instead when 4+ different aspects are
    represented among the controller's units.

    The Zeb Orellios LAW_45 conditional-MAGNITUDE trick: one clause changes only how
    much damage the already-chosen target takes, so it rides inside the single
    targeted CustomEffect rather than needing a second ability.  The aspect count is
    computed here rather than as a Condition atom because nothing else asks for it.
    The printed "you may ... instead" is auto-taken: the controller has already picked
    the target, and 5 is never worse than 3 on a unit they chose to damage (a
    documented simplification of a formality)."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    aspects = set()
    for arena in (ps.ground_arena, ps.space_arena):
        for ci in arena:
            for a in (getattr(ci.card_def, "aspects", None) or ()):
                aspects.add(a.name)
    amount = 5 if len(aspects) >= 4 else 3
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, amount,
                              source_ci.card_def.display_name)


@card_ability("LAW", "207")
def _attack_from_all_sides():
    """LAW_207 -- Attack From All Sides (Event, Tactic, cost 3): "Deal 3 damage to a
    unit.  If there are 4 or more different aspects among friendly units, you may deal
    5 damage to that unit instead." """
    return EventAbility(effects=[CustomEffect(
        fn=_attack_from_all_sides_damage,
        target=TargetSpec(controller="any", kind="unit"),
    )])


def _collateral_damage_first(state, source_ci, target_id, event_ctx):
    """Deal 2 damage to the chosen unit, then record its arena and its id so the
    follow-up "a base or ANOTHER unit in the SAME arena" is exactly gated.

    The Haymaker LAW_168 / Asajj JTL shared-``event_ctx`` chain: ``same_arena`` +
    ``excluded_target_id`` + ``prior_target_id`` are the three stamps the second
    effect's predicates read."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    _, unit = res
    event_ctx["same_arena"] = "space" if unit.zone == Zone.SPACE_ARENA else "ground"
    event_ctx["excluded_target_id"] = target_id
    event_ctx["prior_target_id"] = target_id
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, 2, source_ci.card_def.display_name)


@card_ability("LAW", "208")
def _collateral_damage():
    """LAW_208 -- Collateral Damage (Event, Disaster, cost 3): "Deal 2 damage to a
    unit.  Then, deal 2 damage to a base or another unit in the same arena."

    A two-link shared-``event_ctx`` chain.  The second link needs "a base OR another
    unit in the same arena", which the plain ``same_arena_as_event`` predicate cannot
    express -- a base lives in ``base_zone`` and so fails every arena test.  Hence the
    new ``same_arena_as_event_or_base`` predicate: the ``ground_or_base`` SOR_158
    widening (a base always qualifies) applied to ``same_arena_as_event``.
    ``excludes_event_target`` is the printed "another"; ``requires_prior_target``
    makes the whole second link fizzle unprompted when no first unit was chosen."""
    return EventAbility(effects=[
        CustomEffect(fn=_collateral_damage_first,
                     target=TargetSpec(controller="any", kind="unit")),
        DealDamage(2, TargetSpec(controller="any", kind="unit_or_base",
                                 predicates=("same_arena_as_event_or_base",
                                             "excludes_event_target",
                                             "requires_prior_target"))),
    ])


@card_ability("LAW", "213")
def _cutthroat_podracer():
    """LAW_213 -- Cutthroat Podracer (Unit, Speeder/Vehicle, 4/4): "When Played: You
    may deal 2 damage to an exhausted ground unit."

    Pure reuse: an optional WhenPlayed over a ``DealDamage`` whose TargetSpec carries
    the existing ``exhausted`` predicate beside ``arena="ground"``.  With no exhausted
    ground unit on the board the optional trigger has no candidates and fizzles
    without a prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground",
                                          predicates=("exhausted",)))],
        optional=True,
    )


# -- Group law-set:07 -- Card advantage & disruption ---------------------------
#
# Four LEADERS, two BASES and one unit.  Every leader reads the standing LAW
# shape: an "Action [...]" on the UNDEPLOYED side (``undeployed_only=True``) and a
# trigger on the DEPLOYED side (``deployed_only=True`` / ``WhenDeployed``), with
# the printed "Epic Action: ... deploy this leader" handled by the engine's
# generic DeployLeader path (no registration).  Both bases are once-per-game
# ``epic=True`` ActivatedAbilities, enumerated by the existing base_zone scan
# (Energy Conversion Lab SOR_22).


def _beckett_hand_over_unit(state, source_ci, target_id, event_ctx):
    """"Choose a friendly unit.  An opponent takes control of it.  If they do,
    create a Credit token." (Tobias Beckett LAW_2, undeployed Action).

    ``actions.change_control`` (control is implicit -- whichever arena holds the
    unit -- while ``owner_id`` is untouched) plus the payoff in ONE CustomEffect,
    so the "if they do" can never be split.  With two players "an opponent" is
    unambiguous and the transfer always happens, so the Credit is always paid."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, unit = result
    opponent = next((p for p in state.players
                     if p.player_id != source_ci.owner_id), None)
    if opponent is None:
        return state
    from swu.engine.actions import change_control
    from swu.engine.tokens import create_credit_token
    change_control(state, unit, opponent.player_id)
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


def _beckett_reclaim_owned_units(state, source_ci, target_id, event_ctx):
    """"Defeat any number of units you own but don't control.  For each unit
    defeated this way, create a Credit token and draw a card." (LAW_2, deployed
    side -- the payoff for the giveaway his undeployed Action performs).

    "Own but don't control" is exactly the split ``change_control`` opens up: the
    unit's ``owner_id`` is the controller's while the unit sits in the OTHER
    player's arena.  No TargetSpec expresses that (``controller`` is the holder),
    so the pool is computed here and handed to the ``select_token`` loop as a
    ``restrict_ids`` whitelist with ``defeat=True`` -- the Kit Fisto's Aethersprite
    LOF_147 shape.  "Any number" is ``max_targets`` = the size of the pool (the
    Kazuda Xiono JTL_18 idiom, where ``FinishSelectToken`` ends it early, including
    at zero), and the new ``then_credit_and_draw`` rider pays the per-defeat payoff
    at the resolve point -- after the pop, like every other DEFEAT-mode payoff.
    On an ordinary board the pool is empty, nothing is pushed, and the trigger is
    silent."""
    from swu.engine.actions import push_select_token
    me = source_ci.owner_id
    pool = [u.instance_id
            for ps in state.players if ps.player_id != me
            for u in ps.ground_arena + ps.space_arena
            if u.owner_id == me]
    if not pool:
        return state
    push_select_token(state, source_ci, token_type=None, max_targets=len(pool),
                      controller="any", kind="unit", restrict_ids=pool,
                      defeat=True, then_credit_and_draw=True)
    return state


@card_ability("LAW", "2")
def _tobias_beckett_law():
    """LAW_2 -- Tobias Beckett (Leader, Underworld): "Action [Exhaust]: Choose a
    friendly unit.  An opponent takes control of it.  If they do, create a Credit
    token." / "When Deployed: Defeat any number of units you own but don't
    control.  For each unit defeated this way, create a Credit token and draw a
    card."

    The two sides are one loop: he rents units out for Credits, then repossesses
    them.  ``CONTROLLER_N_PLUS_UNITS`` gates the Action so the exhaust is never
    spent with nothing to hand over.

    WARNING -- LAW_2 IS ALSO THE EXPERIENCE TOKEN's (set, number).  Both specs
    here are of the two kinds a token upgrade can never reach:
    ``ActivatedAbility(undeployed_only=True)`` (the arena scans require a Leader
    card_def) and ``TriggerAbility(WhenDeployed())`` (matched by instance id
    against a ``LeaderDeployed`` event, which a token never generates).  A
    ``ConstantAbility``, a passive marker or a ``GrantedAbility`` would NOT be
    safe -- the last of those reads a host's ``attached_upgrades``, which is
    exactly where an Experience token lives (the JTL_3/JTL_4 lesson)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_beckett_hand_over_unit,
                target=TargetSpec(controller="friendly", kind="unit"))],
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 1),
            title="Action: give a friendly unit away for a Credit",
            undeployed_only=True),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_beckett_reclaim_owned_units)]),
    ]


def _jyn_search_top_three(state, source_ci, target_id, event_ctx):
    """"Search the top 3 cards of your deck for a card and draw it.  (Put the
    other cards on the bottom of your deck in a random order.)" (Jyn Erso LAW_5,
    both sides).

    The plain ``deck_search`` seam at its default disposition (draw) and default
    ``rest_disposition="bottom"`` -- whose parenthesised reminder IS the printed
    one.  ``up_to=False`` because the card says "for a card and draw it", not "you
    may" (the Ahsoka TWI_8 / Bad Batch TWI_146 reading); every card qualifies, so
    the search only fizzles on an empty deck."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=lambda cd: True,
                     up_to=False, window=3)
    return state


@card_ability("LAW", "5")
def _jyn_erso_law():
    """LAW_5 -- Jyn Erso (Leader, Rebel): "Action [1 resource, Exhaust]: If a
    friendly Rebel unit was defeated this phase, search the top 3 cards of your
    deck for a card and draw it." / "On Attack: If a friendly Rebel unit was
    defeated this phase, search the top 3 ... and draw it."

    Both sides are the same adapter behind the same gate, differing only in what
    pays for it.  The gate is the new ``CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE``
    atom -- the TRAIT sibling of Chancellor Palpatine TWI_17's aspect one, over the
    matching ``game_memory.defeated_traits_this_round`` ledger recorded at the
    defeat site.  It has to be its own ledger rather than a re-find of the corpse
    for the reason the aspect one does: a token unit ceases to exist and sits in no
    discard pile.  Gating COLLECTION means the On Attack never prompts and the
    Action is never offered when no Rebel has died, so neither the exhaust nor the
    resource can be spent on a no-op."""
    gate = ConditionCheck(Condition.CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE,
                          "Rebel")
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_jyn_search_top_three)],
            condition=gate,
            title="Action: search the top 3 and draw a card",
            undeployed_only=True),
        TriggerAbility(
            trigger=OnAttack(),
            condition=gate,
            effects=[CustomEffect(fn=_jyn_search_top_three)],
            deployed_only=True),
    ]


def _sebulba_mill_and_raid(state, source_ci, target_id, event_ctx):
    """"Action [Exhaust, discard a card from your deck]: A friendly unit gains
    Raid 1 for this phase." (Sebulba LAW_12, undeployed).

    The deck discard is a printed COST with no choice attached, and a mill is
    always payable -- so it rides INSIDE this one CustomEffect rather than needing
    a cost spec (the Anakin Skywalker TWI_12 "deal 2 damage to your base"
    half-cost convention).  One effect also keeps cost and payoff atomic and costs
    exactly one prompt (the Kylo Ren SHD_141 shape)."""
    from swu.engine.actions import discard_from_deck
    discard_from_deck(state, state.player_by_id(source_ci.owner_id), 1)
    if target_id is None:
        return state
    from swu.abilities.resolver import _make_kw_modifier
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id,
        keyword="Raid", value=1, duration=Duration.THIS_PHASE,
        kind="keyword_grant"))
    return state


def _sebulba_mill(state, source_ci, target_id, event_ctx):
    """"On Attack: Discard a card from your deck." (LAW_12, deployed) -- the same
    self-mill with no payoff attached."""
    from swu.engine.actions import discard_from_deck
    discard_from_deck(state, state.player_by_id(source_ci.owner_id), 1)
    return state


@card_ability("LAW", "12")
def _sebulba_law():
    """LAW_12 -- Sebulba (Leader, Fringe): "Action [Exhaust, discard a card from
    your deck]: A friendly unit gains Raid 1 for this phase." / "Raid 1" + "On
    Attack: Discard a card from your deck."

    Both halves are the new ``actions.discard_from_deck`` primitive; the deployed
    side's printed Raid 1 is the keyword layer (read from ``deploy_box``) and needs
    no registration.  ``CONTROLLER_N_PLUS_UNITS`` gates the Action so the mill is
    never paid with no unit to buff."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_sebulba_mill_and_raid,
                target=TargetSpec(controller="friendly", kind="unit"))],
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 1),
            title="Action: mill 1, a friendly unit gains Raid 1",
            undeployed_only=True),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_sebulba_mill)],
            deployed_only=True),
    ]


def _lando_choose_aspect_and_mill(state, source_ci, target_id, event_ctx):
    """"Choose an aspect, then discard a card from a deck.  If it has the chosen
    aspect, create a Credit token." (Lando Calrissian LAW_18, undeployed Action).

    OPTIMAL-PLAY COLLAPSE (the Foresight TWI_68 precedent, where a name-a-card is
    likewise resolved before anything is revealed): the aspect is chosen with the
    card still face down, so the only thing the choice can move is the hit
    probability -- and the MODAL aspect among the cards still in the deck maximises
    it exactly.  A prompt here would be a decision with a computable right answer
    and no bluff value.  Ties break on the aspect NAME, never on dict order, so the
    choice is deterministic.

    DOCUMENTED SIMPLIFICATION: "a deck" is read as the CONTROLLER's own deck -- the
    only deck whose remaining composition the controller knows, and therefore the
    only one over which "choose an aspect" is a real choice at all."""
    from swu.engine.actions import discard_from_deck
    from swu.engine.tokens import create_credit_token
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return state
    counts: dict = {}
    for ci in ps.deck:
        for a in (getattr(ci.card_def, "aspects", None) or ()):
            counts[a.name] = counts.get(a.name, 0) + 1
    chosen_aspect = max(sorted(counts), key=lambda n: counts[n]) if counts else None
    milled = discard_from_deck(state, ps, 1)
    if not milled or chosen_aspect is None:
        return state
    got = {a.name for a in (getattr(milled[0].card_def, "aspects", None) or ())}
    if chosen_aspect in got:
        create_credit_token(state, ps)
    return state


def _lando_credits_from_credit(state, source_ci, target_id, event_ctx):
    """"You may defeat a friendly Credit token.  If you do, create 3 Credit
    tokens." (LAW_18, When Deployed) -- a net +2 Credits.

    The defeat and the payoff are bound in one effect so the "if you do" is exact.
    A Credit is defeated by moving it out of ``PlayerState.credits`` into its
    owner's discard, the Taramyn Barcona LAW_40 removal verbatim; Credits are
    interchangeable, so WHICH one is not a choice."""
    from swu.engine.state import Zone
    from swu.engine.tokens import create_credit_token
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.credits:
        return state
    credit = ps.credits.pop()
    credit.zone = Zone.DISCARD
    ps.discard.append(credit)
    for _ in range(3):
        create_credit_token(state, ps)
    return state


@card_ability("LAW", "18")
def _lando_calrissian_law():
    """LAW_18 -- Lando Calrissian (Leader, Underworld): "Action [1 resource,
    Exhaust]: Choose an aspect, then discard a card from a deck.  If it has the
    chosen aspect, create a Credit token." / "When Deployed: You may defeat a
    friendly Credit token.  If you do, create 3 Credit tokens."

    Both sides are Credit economy.  The deploy half is gated by the new
    ``CONTROLLER_HAS_CREDIT`` atom -- the controller-narrowed sibling of
    ``ANY_PLAYER_HAS_CREDIT`` / ``OPPONENT_HAS_CREDIT`` -- because Credits live in
    ``PlayerState.credits``, not an arena, so no target predicate can see them and
    without the gate the optional trigger would offer a choice that can do
    nothing."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_lando_choose_aspect_and_mill)],
            title="Action: name an aspect, mill 1, Credit on a match",
            undeployed_only=True),
        TriggerAbility(
            trigger=WhenDeployed(),
            condition=ConditionCheck(Condition.CONTROLLER_HAS_CREDIT),
            effects=[CustomEffect(fn=_lando_credits_from_credit)],
            optional=True),
    ]


def _shipbreaking_yard_mill(state, source_ci, target_id, event_ctx):
    """"Discard 3 cards from your deck.  You may return a card discarded this way
    to the top of your deck." (Shipbreaking Yard LAW_26, Epic Action).

    PURE REUSE of the ``deck_search`` seam at a combination no card had used
    before: ``window=3`` with ``disposition="top"`` (Following the Path LOF_103 --
    the picks go back on TOP rather than to hand) and ``rest_disposition="discard"``
    (I've Found Them IBH_9 -- the un-taken ones are discarded), so the two halves
    of the printed sentence fall out of one decision.  ``count=1, up_to=True`` is
    the "you may return A card".

    The engine touches nothing while a deck_search is open, so the discard happens
    at the finish and the rescued card is never discarded at all -- which is why a
    "When this is discarded from your hand or deck" card (That's a Rock LAW_206)
    correctly does NOT fire for the one you keep."""
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=lambda cd: True,
                     up_to=True, window=3, disposition="top",
                     rest_disposition="discard")
    return state


@card_ability("LAW", "26")
def _shipbreaking_yard():
    """LAW_26 -- Shipbreaking Yard (Base): "Epic Action: Discard 3 cards from your
    deck.  You may return a card discarded this way to the top of your deck."

    A once-per-game Epic Action on a base (``epic=True``, no cost), enumerated by
    the existing base_zone scan (Energy Conversion Lab SOR_22)."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_shipbreaking_yard_mill)],
        title="Epic Action: mill 3, keep one on top",
        epic=True,
    )


def _citadel_research_ramp(state, source_ci, target_id, event_ctx):
    """"Return a friendly resource to its owner's hand.  If you do, resource the
    top card of your deck." (Citadel Research Center LAW_29, Epic Action).

    Frontier Trader SHD_214 verbatim: the resource is AUTO-PICKED (the K-2SO
    SOR_145 fungible convention -- face-down resources are indistinguishable and
    are not targetable cards), taking the highest-cost one, which is the card most
    worth recovering.  It goes to its OWNER's hand, which is not always the
    controller's (a resource can change hands -- DJ SHD_213), while the ramp is the
    shared ``_resource_top_of_deck`` primitive and refills the controller's own
    row.  Both live in one effect so the "if you do" holds: no resource to return
    means no ramp."""
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
    _resource_top_of_deck(state, ps)
    return state


@card_ability("LAW", "29")
def _citadel_research_center():
    """LAW_29 -- Citadel Research Center (Base): "Epic Action [1 resource]: Return
    a friendly resource to its owner's hand.  If you do, resource the top card of
    your deck."

    A once-per-game Epic Action on a base with an ordinary ``PayResources(1)``
    cost.  Net: a spent resource becomes a hand card and the deck top becomes a
    fresh one (deck -1, hand +1, resource count unchanged)."""
    return ActivatedAbility(
        costs=[PayResources(1)],
        effects=[CustomEffect(fn=_citadel_research_ramp)],
        title="Epic Action: recycle a resource, ramp the deck top",
        epic=True,
    )


@card_ability("LAW", "48")
def _chio_fain():
    """LAW_48 -- Chio Fain (Unit, Bounty Hunter/Underworld, 2/4): "On Attack: You
    may choose 2 players.  If you do, they each draw a card."

    In a two-player game "2 players" IS both players, so the only real decision the
    card offers is the printed "you may" -- an optional OnAttack whose whole
    content is a symmetric draw (``player="each"``, the DrawCards convention).
    Declining is a live choice: the draw helps the opponent as much as the
    controller."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DrawCards(count=1, player="each")],
        optional=True,
    )


# -- Group law-set:08 -- Card advantage & disruption ---------------------------
#
# Almost entirely pure reuse: one new condition atom (the hand-size mirror), one
# new disposition on an existing decision, and five cards built from machinery
# that already existed.


def _broken_horn_ramp(state, source_ci, target_id, event_ctx):
    """The second clause of Broken Horn LAW_83 — "resource the top card of your
    deck", the shared ``_resource_top_of_deck`` primitive."""
    from swu.engine.actions import _resource_top_of_deck
    _resource_top_of_deck(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "83")
def _broken_horn():
    """LAW_83 -- Broken Horn (Unit, Transport/Underworld/Vehicle, 5/4): "When
    Played: If you have fewer cards in hand than an opponent, draw a card.  If you
    control fewer resources than an opponent, resource the top card of your deck."

    A catch-up card: two INDEPENDENT clauses, each a plain ``ConditionalEffect``
    (neither is targeted, so both inline in order and the card prompts for
    nothing).  The resource half is `OPPONENT_MORE_RESOURCES_THAN_CONTROLLER`,
    which already existed for Cham Syndulla JTL_164; the hand half needed its
    exact mirror, the new `OPPONENT_MORE_CARDS_IN_HAND_THAN_CONTROLLER`.  Both are
    MIRRORS rather than negations, so a level count satisfies neither -- which is
    right, since level is not "fewer".  Broken Horn itself has already left hand
    and is already in play when its When Played resolves, so both counts are read
    at the moment the card asks about."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[
            ConditionalEffect(
                condition=ConditionCheck(
                    Condition.OPPONENT_MORE_CARDS_IN_HAND_THAN_CONTROLLER),
                if_true=[DrawCards(count=1)],
                if_false=[]),
            ConditionalEffect(
                condition=ConditionCheck(
                    Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER),
                if_true=[CustomEffect(fn=_broken_horn_ramp)],
                if_false=[]),
        ])


@card_ability("LAW", "84")
def _krrsantan_law():
    """LAW_84 -- Krrsantan (Unit, Bounty Hunter/Underworld/Wookiee, 7/7; Ambush and
    Overwhelm are the keyword engine): "Action [discard 2 cards from your hand]:
    Return this unit to your hand (from play)."

    A plain `ActivatedAbility` over the existing `DiscardCardCost(count=2)` (Dryden
    Vos SEC_7) and a `fixed=SELF` `ReturnToHand`.  The cost is checked at all three
    `legal_actions` affordability sites, so the Action is simply not offered on a
    hand of fewer than 2 -- and note there is NO exhaust in the printed cost, so an
    exhausted Krrsantan can still bounce himself out of a bad attack."""
    return ActivatedAbility(
        costs=[DiscardCardCost(count=2)],
        effects=[ReturnToHand(TargetSpec(fixed=SELF))],
        title="Action [discard 2]: return this unit to your hand",
    )


def _hondo_play_top_card(state, source_ci, target_id, event_ctx):
    """"Action: Play the top card of your deck (paying its cost)." (Hondo Ohnaka
    LAW_94), on the existing `peek_top` `may_play` mode (You're My Only Hope
    SOR_246): the top card is revealed to the controller, who plays it or leaves
    it on top.

    DOCUMENTED SIMPLIFICATION: the printed play is not a "may", but the mode's
    KeepTopCard is a superset that costs nothing in practice -- Hondo's OTHER line
    lets his controller see the top card at any time, so activating the Action is
    itself the decision, and `PlayTopCard` is only offered when the card is
    actually affordable.  An empty deck pushes no decision at all."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_play")
    return state


@card_ability("LAW", "94")
def _hondo_ohnaka_law():
    """LAW_94 -- Hondo Ohnaka (Unit, Underworld, 3/7): "You may look at the top card
    of your deck at any time." / "Action: Play the top card of your deck (paying its
    cost).  Use this ability only once each round."

    The first line is pure INFORMATION and needs no registration -- it changes no
    game state, and the `peek_top` decision the Action pushes reveals that card to
    its controller anyway (the decision context is private to the deciding player,
    so nothing leaks).  The Action is a costless `once_per_round` ActivatedAbility;
    the round limit is the long-standing `once_per_round` flag over
    `game_memory.activated_abilities_used_this_round`."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_hondo_play_top_card)],
        once_per_round=True,
        title="Action: play the top card of your deck",
    )


def _rhydonium_detonation(state, source_ci, target_id, event_ctx):
    """"Each player may return a non-leader unit to its owner's hand.  Then, defeat
    all non-leader units." (Rhydonium Detonation LAW_96) -- the `each_player_defeats`
    walk (Merciless Contest TWI_238) at its new `return_then_defeat_all`
    disposition, which rescues each player's pick to hand and then wipes every
    non-leader unit left standing."""
    from swu.engine.actions import push_each_player_defeats
    push_each_player_defeats(state, source_ci,
                             disposition="return_then_defeat_all")
    return state


@card_ability("LAW", "96")
def _rhydonium_detonation_card():
    """LAW_96 -- Rhydonium Detonation (Event, Tactic, cost 7): a symmetric board
    wipe that lets each player buy one unit back first.

    The controller chooses first and the opponent second (the TWI_238 order), and
    the printed "may" is an OPTIMAL-PLAY COLLAPSE -- with the wipe landing
    immediately afterwards, returning a doomed unit to hand is never worse than
    leaving it to die (the same card leaves play either way; hand beats discard)."""
    return EventAbility(effects=[CustomEffect(fn=_rhydonium_detonation)])


def _display_piece_defeat_and_resource(state, source_ci, target_id, event_ctx):
    """"Defeat an enemy non-leader unit.  Its controller resources it from its
    owner's discard pile." (Display Piece LAW_103).

    The Arquitens SHD_122 relocation, run on a unit this card defeats rather than
    one an attack killed: note the CONTROLLER-at-death is captured BEFORE the
    defeat (afterwards the card is in a discard pile and out of every arena -- the
    JTL_175 ordering rule), and the card is then moved facedown into THAT player's
    resource row.  So the removal hands the victim's owner a resource, which is
    the whole trade the card offers."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    victim_controller_ps, victim = result
    controller_id = victim_controller_ps.player_id
    from swu.abilities.resolver import _apply_defeat_unit
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    _apply_defeat_unit(state, target_id)
    # The defeated card is now in its OWNER's discard pile (a token would have
    # ceased to exist instead, in which case there is nothing to resource).
    for ps in state.players:
        for card in list(ps.discard):
            if card.instance_id != target_id:
                continue
            ps.discard.remove(card)
            dest = state.player_by_id(controller_id)
            card.zone = Zone.RESOURCES
            card.face_down = True
            card.exhausted = False
            card.damage = 0
            dest.resources.append(card)
            state.event_log.append(CardResourced(
                player_id=dest.player_id,
                instance_id=card.instance_id,
                card_name=card.card_def.display_name,
            ))
            return state
    return state


@card_ability("LAW", "103")
def _display_piece():
    """LAW_103 -- Display Piece (Event, Supply, cost 4): "Defeat an enemy non-leader
    unit.  Its controller resources it from its owner's discard pile."

    ONE targeted `CustomEffect` doing both halves (the Kylo Ren SHD_141 shape), so
    the compensation can never be split from the removal it pays for."""
    return EventAbility(effects=[CustomEffect(
        fn=_display_piece_defeat_and_resource,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader",)))])


@card_ability("LAW", "107")
def _swoop_bike_marauder():
    """LAW_107 -- Swoop Bike Marauder (Unit, Underworld, 4/4): "On Attack: Draw a
    card."  A bare `DrawCards` on an `OnAttack` trigger."""
    return TriggerAbility(trigger=OnAttack(), effects=[DrawCards(count=1)])


def _watchful_peek(state, source_ci, target_id, event_ctx):
    """"Look at the top card of a deck.  You may put it on the bottom of that deck.
    (Otherwise, leave it on top.)" (Watchful LAW_125) -- the `peek_top` decision's
    `may_bottom` mode (R2-D2 SOR_181) verbatim: KeepTopCard vs BottomTopCard, with
    the card revealed to the decider only.

    DOCUMENTED NARROWING: "a deck" is read as the CONTROLLER's own deck -- the same
    reading Lando Calrissian LAW_18 takes in this set, and the one where the look
    is a real filter rather than a bare peek at hidden information.  `push_peek_top`
    keys the deck off `source_ci.owner_id`, and because this is a `GrantedAbility`
    the source IS the host unit, so the deck followed is the host's."""
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_bottom")
    return state


@card_ability("LAW", "125")
def _watchful():
    """LAW_125 -- Watchful (Upgrade, Learned, cost 1): "Attached unit gains: 'On
    Attack: Look at the top card of a deck.  You may put it on the bottom of that
    deck.'"

    The standard `GrantedAbility` wrapper (Armed to the Teeth SHD_175): the inner
    `OnAttack` is collected from the host and resolves with the HOST as source, so
    an upgrade with no unit-side reading of its own needs nothing else."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_watchful_peek)]))


# ══════════════════════════════════════════════════════════════════════════════
# Group ``law-set:09`` — Card advantage & disruption
#
# The set's self-mill group.  Six of the seven are pure reuse of seams that
# landed in law-set:07 (`actions.discard_from_deck`) or long before; the one new
# piece of machinery is the `WhenYouDiscardFromDeck` observer (LAW_176), which is
# the `WhenThisIsDiscarded` settle-drain family with an easier source — the
# observer is an ordinary unit IN PLAY, so no discard-pile scan is needed.
# ══════════════════════════════════════════════════════════════════════════════

def _is_bounty_hunter_unit(card_def) -> bool:
    """A Bounty Hunter UNIT card (the deck_search eligibility filter for LAW_138).
    Printed traits: a card in the deck is out of the trait-grant layer's reach."""
    from swu.cards.models import Unit
    return (isinstance(card_def, Unit)
            and "Bounty Hunter" in (getattr(card_def, "traits", None) or ()))


def _undercity_search(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=_is_bounty_hunter_unit,
                     up_to=False, window=5)
    return state


@card_ability("LAW", "138")
def _undercity_hunting_team():
    """LAW_138 -- Undercity Hunting Team (Unit 5/5, Bounty Hunter, Underworld):
    "When Played: Search the top 5 cards of your deck for a Bounty Hunter unit,
    reveal it, and draw it.  (Put the other cards on the bottom of your deck in a
    random order.)"

    `push_deck_search` verbatim at the Syndicate Spice Runner LAW_136 settings, one
    window wider: `count=1`, `up_to=False` (the printed search is mandatory among
    the qualifiers), `window=5`, and the default `rest_disposition="bottom"`, which
    IS the parenthesised reminder.  The "reveal it" needs no registration — the
    decision already shows the searched cards to the searcher, and drawing it makes
    it public soon enough."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_undercity_search)],
    )


def _expendable_mercenary_resource(state, source_ci, target_id, event_ctx):
    """Offer THIS card — now sitting in its owner's discard pile — as a resource.

    `push_resource_from_discard` scans exactly that pile and pre-filters to the
    qualifying cards, so narrowing `eligible` to the source's own instance id makes
    the whole decision "resource this unit": exactly one candidate.  The printed
    "you may" is the TRIGGER's `optional`, not the decision's `up_to` — which is
    also what makes the timing work, since an optional trigger resolves from its own
    decision, i.e. AFTER `_defeat_unit` has finished homing the corpse in the
    discard.  A mandatory inline effect would run while the unit is in no zone at
    all and find nothing to offer."""
    from swu.engine.actions import push_resource_from_discard
    push_resource_from_discard(
        state, source_ci, up_to=False,
        eligible=lambda ci: ci.instance_id == source_ci.instance_id)
    return state


@card_ability("LAW", "159")
def _expendable_mercenary():
    """LAW_159 -- Expendable Mercenary (Unit 3/3, Bounty Hunter, Underworld):
    "When Defeated: You may resource this unit from its owner's discard pile."

    The L3-37 JTL_49 shape: a When Defeated whose payoff finds the card ALREADY in
    the discard and moves it on from there.  ⚠️ That "already" is why the trigger has
    to be `optional`: `_defeat_unit` fires its triggers with the unit pulled from its
    arena and NOT YET placed in the discard, so a mandatory effect would inline into
    that gap and see the card nowhere.  An optional trigger resolves from a
    `trigger_option` decision, i.e. on a later `apply`, by which time the corpse is in
    the pile.  (JTL_49 gets the same delay from its effect being TARGETED.)"""
    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[CustomEffect(fn=_expendable_mercenary_resource)],
    )


def _sebulbas_podracer_ready(state, source_ci, target_id, event_ctx):
    """Ready the Podracer and spend the round's use (the Toro Calican SHD_239 marker),
    charged on ACCEPT only — declining the "you may" is not a use."""
    from swu.engine.actions import note_unit_readied
    res = state.find_instance(source_ci.instance_id)
    unit = res[1] if res is not None else source_ci
    if unit.exhausted:
        note_unit_readied(state, unit)
        unit.exhausted = False
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    return state


@card_ability("LAW", "176")
def _sebulbas_podracer():
    """LAW_176 -- Sebulba's Podracer (Unit 3/3, Speeder, Vehicle): "When you discard
    a card from your deck: You may ready this unit.  Use this ability only once each
    round."

    The one new seam in this group: `WhenYouDiscardFromDeck`, an observer over the
    new `game_memory.deck_discards` ledger (fed by
    `note_hand_or_deck_discard(..., from_deck=True)` at the mill sites and drained at
    the action settle-point).  "When YOU discard" is enforced in the matcher — the
    ledger records WHICH player milled — so an opponent's self-mill leaves it alone.
    `optional` is the "you may"; the shared `SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`
    limiter is the "only once each round", charged on accept."""
    return TriggerAbility(
        trigger=WhenYouDiscardFromDeck(),
        optional=True,
        condition=ConditionCheck(Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
        effects=[CustomEffect(fn=_sebulbas_podracer_ready)],
    )


def _bracca_mill(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import discard_from_deck
    discard_from_deck(state, state.player_by_id(source_ci.owner_id), 1)
    return state


@card_ability("LAW", "192")
def _bracca_shipbreaker():
    """LAW_192 -- Bracca Shipbreaker (Unit 4/3, Fringe): "On Attack: Discard a card
    from your deck."

    The shared `actions.discard_from_deck` primitive (law-set:07), which routes the
    milled card through `note_hand_or_deck_discard` — so this attack also feeds That's
    a Rock LAW_206's self-discard observer and Sebulba's Podracer LAW_176's deck
    observer for free.  Mandatory and unconditional: an empty deck mills nothing (a
    mill is not the empty-deck DRAW penalty)."""
    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_bracca_mill)])


def _doctor_aphra_mill(state, source_ci, target_id, event_ctx):
    """Mill 3, then offer back an Underworld card FROM THAT MILL.

    "discarded this way" is the whole filter, so the returned card is pinned by
    INSTANCE id (`eligible_instance`) rather than by card def — a matching Underworld
    card already sitting in the discard from an earlier turn is not offered."""
    from swu.engine.actions import discard_from_deck, push_return_from_discard
    milled = discard_from_deck(state, state.player_by_id(source_ci.owner_id), 3)
    ids = {ci.instance_id for ci in milled}
    if not ids:
        return state
    push_return_from_discard(
        state, source_ci, count=1, up_to=True,
        eligible=lambda cd: "Underworld" in (getattr(cd, "traits", None) or ()),
        eligible_instance=lambda ci: ci.instance_id in ids,
    )
    return state


@card_ability("LAW", "194")
def _doctor_aphra():
    """LAW_194 -- Doctor Aphra (Unit 4/5, Underworld): "On Attack: Discard 3 cards
    from your deck.  You may return an Underworld card discarded this way to your
    hand."

    `discard_from_deck(3)` bound to `push_return_from_discard` inside ONE
    `CustomEffect`, because the second clause reads what the first actually milled —
    two effects could not share that list.  `up_to=True` is the "you may"; with no
    Underworld card among the three the decision is never pushed (its candidates are
    pre-filtered), so there is no empty prompt."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_doctor_aphra_mill)])


@card_ability("LAW", "200")
def _salvaged_blaster():
    """LAW_200 -- Salvaged Blaster (Upgrade, Item/Weapon, cost 2): "Attach to a
    non-Vehicle unit.  Action: If this upgrade was discarded from your hand or deck
    this phase, play it from your discard pile (paying its cost)."

    Kylo Ren's TIE Silencer SHD_135 verbatim — a `PlayFromDiscardAction` gated by
    `SELF_DISCARDED_THIS_PHASE`, which reads the phase-scoped
    `cards_discarded_this_phase` ledger against this very instance.  That SHD card is
    a Unit and this one an Upgrade, but the enumerator already splits on that: for an
    Upgrade it offers the play once per legal "Attach to …" host, and the printed
    restriction is parsed onto a TargetSpec by `_upgrade_target_spec`, so neither
    clause needs registering here."""
    return PlayFromDiscardAction(
        condition=ConditionCheck(Condition.SELF_DISCARDED_THIS_PHASE))


def _hold_for_questioning(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen enemy unit; if it was really exhausted, strip a hand card
    sharing one of its aspects.

    ONE `CustomEffect` because the second clause is an "If you do" bound to the first
    AND reads the chosen unit's aspects (the Kihraxz SHD_118 binding).  An already
    exhausted unit is not a legal target, so "if you do" is only ever false when
    there was no target at all."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    unit.exhausted = True
    aspects = tuple(getattr(a, "name", str(a))
                    for a in (getattr(unit.card_def, "aspects", None) or ()))
    if not aspects:
        return state
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, aspects_any=aspects)
    return state


@card_ability("LAW", "217")
def _hold_for_questioning_event():
    """LAW_217 -- Hold For Questioning (Event, Law, cost 3): "Exhaust an enemy unit.
    If you do, look at its controller's hand and discard a card from it that shares
    an aspect with that unit."

    The `name_and_discard` decision already IS "look at an opponent's hand and discard
    a card from it" (it carries the whole hand to the controller and offers only names
    actually present — the Chimaera SOR_185 shape), so the only new part is the
    aspect filter, which rides in as `aspects_any`.  With nothing in their hand
    sharing an aspect the decision fizzles unprompted, which is the right reading of
    a clause that can find no legal card.  The target is narrowed to a READY enemy
    unit so the exhaust — and with it the whole card — is never spent on a no-op."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_hold_for_questioning,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("ready",)),
        ),
    ])


# ==============================================================================
# Group ``law-set:10`` -- Card advantage & disruption (the Credit-economy group)
#
# All reuse bar one settle payoff: `push_bottom_from_discard(then_create_credit=)`,
# the Credit sibling of its `then_draw` / `then_create_token` riders.
# ==============================================================================

def _liberty_strip(state, source_ci, target_id, event_ctx):
    """Exhaust the chosen enemy unit and bounce every cheap upgrade off it.

    ONE `CustomEffect` because the second clause reads the unit the first one
    exhausted.  The upgrades are returned to their OWNERS' hands (an upgrade keeps
    its owner even on an enemy host), which `_apply_return_to_hand` already does;
    a Shield/Experience TOKEN has no cost and no hand to return to, so the
    `cost <= 4` filter excludes it naturally -- but it is skipped explicitly, since
    a token's ``cost`` reads as 0 and 0 is "4 or less"."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    unit.exhausted = True
    from swu.cards.models import TokenUpgrade
    from swu.abilities.resolver import _apply_return_to_hand
    doomed = [u.instance_id for u in list(unit.attached_upgrades)
              if not isinstance(u.card_def, TokenUpgrade)
              and int(getattr(u.card_def, "cost", 0) or 0) <= 4]
    for uid in doomed:
        if state.find_instance(uid) is not None:
            _apply_return_to_hand(state, uid)
    return state


@card_ability("LAW", "224")
def _liberty():
    """LAW_224 -- Liberty (Unit 9/7, Capital Ship/Rebel/Vehicle, Sentinel): "When
    Played/On Attack: Exhaust an enemy unit and return all upgrades on it that cost
    4 or less to their owner's hands."

    One targeted `CustomEffect` registered under BOTH triggers (the Captain Rex
    SEC_48 shape).  Both clauses are mandatory and act on the same chosen unit, so
    they must share one effect -- two effects would prompt twice and could split
    across two units.  The target is any enemy unit: the exhaust alone is worth it,
    so an unupgraded unit is still a legal (and often correct) pick."""
    fx = [CustomEffect(fn=_liberty_strip,
                       target=TargetSpec(controller="enemy", kind="unit"))]
    return [TriggerAbility(trigger=WhenPlayed(), effects=list(fx)),
            TriggerAbility(trigger=OnAttack(), effects=list(fx))]


def _golden_dice_roll(state, source_ci, target_id, event_ctx):
    """Mill one; an ODD printed cost pays a Credit.  `source_ci` is the HOST (this
    is a GrantedAbility), so "your deck" is the host's controller's deck."""
    from swu.engine.actions import discard_from_deck
    ps = state.player_by_id(source_ci.owner_id)
    milled = discard_from_deck(state, ps, 1)
    if not milled:
        return state
    cost = getattr(milled[0].card_def, "cost", None)
    if cost is not None and int(cost) % 2 == 1:
        from swu.engine.tokens import create_credit_token
        create_credit_token(state, ps)
    return state


@card_ability("LAW", "225")
def _hans_golden_dice():
    """LAW_225 -- Han's Golden Dice (Upgrade, Item, cost 1): "Attached unit gains:
    'On Attack: Discard a card from your deck.  If its cost is odd, create a Credit
    token.'"

    The standard `GrantedAbility` wrapper (Armed to the Teeth SHD_175) over the
    law-set:07 `discard_from_deck` primitive.  The mill and the conditional payoff
    live in ONE `CustomEffect` because the payoff reads what was milled -- the
    Doctor Aphra LAW_194 binding.  A card with no printed cost (there are none in a
    deck, but a leader would be one) pays nothing rather than counting as even."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_golden_dice_roll)]))


def _is_gambit_card(card_def) -> bool:
    return "Gambit" in (getattr(card_def, "traits", None) or ())


def _codebreaker_search(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=_is_gambit_card,
                     up_to=False, window=8)
    return state


@card_ability("LAW", "229")
def _the_master_codebreaker():
    """LAW_229 -- The Master Codebreaker (Unit 1/4, Underworld): "The first Gambit
    card you play each round costs 1 resource less.  When Played: Search the top 8
    cards of your deck for a Gambit card, reveal it, and draw it."

    Two specs: `StandingPlayDiscount` at its DEFAULT `once_per_round=True`, which IS
    "the first … each round" (Admiral Piett JTL_5 uses the same family with the flag
    off for "each"), over the NEW card-type-blind `applies_to="card_trait:<Trait>"`
    arm -- Gambit is printed on Events and Upgrades, never Units, so the existing
    `trait:` arm's Unit gate would have made the clause dead text; and the
    Undercity Hunting Team LAW_138 `push_deck_search` at `window=8`.  ⚠️ The discount
    scan walks ARENA units, so it is inert while the card is in hand -- which is the
    printed reading, since the card must be in play to grant it.  The search is
    card-type-blind ("a Gambit CARD"), unlike LAW_138's unit filter."""
    return [
        StandingPlayDiscount(amount=1, applies_to="card_trait:Gambit",
                             once_per_round=True),
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_codebreaker_search)]),
    ]


def _bix_caleen_pitch(state, source_ci, target_id, event_ctx):
    """Discard the first hand card and take a Credit -- both in ONE effect, so the
    "If you do" cannot be split (the Bright Hope SOR_99 binding).  First-card
    discard is the standing convention (K-2SO SOR_145)."""
    from swu.engine.actions import note_hand_or_deck_discard, record_hand_discard
    from swu.engine.state import Zone
    from swu.engine.tokens import create_credit_token
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    card.face_down = False
    ps.discard.append(card)
    note_hand_or_deck_discard(state, card)
    record_hand_discard(state, ps.player_id)
    create_credit_token(state, ps)
    return state


@card_ability("LAW", "236")
def _bix_caleen():
    """LAW_236 -- Bix Caleen (Unit 4/5, Fringe): "When Played/On Attack: You may
    discard a card from your hand.  If you do, create a Credit token."

    One `CustomEffect` under both triggers, `optional` for the "you may" and gated
    by `CONTROLLER_HAND_SIZE_MIN` at 1 so an empty hand is never offered a trigger
    that could do nothing (the "don't offer a no-op" rule).  A hand discard, not a
    mill -- so it feeds the hand ledgers (Migs Mayfeld SHD_163) and NOT the new deck
    ledger."""
    fx = [CustomEffect(fn=_bix_caleen_pitch)]
    gate = ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, 1)
    return [TriggerAbility(trigger=WhenPlayed(), effects=list(fx),
                           optional=True, condition=gate),
            TriggerAbility(trigger=OnAttack(), effects=list(fx),
                           optional=True, condition=gate)]


def _qui_gon_look(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, eligible=lambda cd: True,
                     up_to=True, window=3,
                     disposition="discard", rest_disposition="top")
    return state


@card_ability("LAW", "237")
def _qui_gon_jinn_law():
    """LAW_237 -- Qui-Gon Jinn (Unit 3/5, Force/Jedi/Republic, Sentinel): "When
    Played/On Attack: Look at the top 3 cards of your deck.  You may discard 1 of
    them.  Put the rest back on top in any order."

    The EXACT INVERSE of Shipbreaking Yard LAW_26's `push_deck_search` combination:
    there `disposition="top"` + `rest_disposition="discard"` ("discard 3, rescue
    one"), here `disposition="discard"` + `rest_disposition="top"` ("look at 3,
    discard one").  `up_to=True` is the "you may".  DOCUMENTED DEVIATION: the
    un-taken cards keep their existing order rather than being re-ordered by the
    controller -- "in any order" is a freedom the decision does not model, and the
    order of cards the controller has just seen is public to nobody else."""
    fx = [CustomEffect(fn=_qui_gon_look)]
    return [TriggerAbility(trigger=WhenPlayed(), effects=list(fx)),
            TriggerAbility(trigger=OnAttack(), effects=list(fx))]


def _sandcrawler_recycle(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(state, source_ci, count=1, own_only=True,
                             then_create_credit=1)
    return state


@card_ability("LAW", "238")
def _scavenging_sandcrawler():
    """LAW_238 -- Scavenging Sandcrawler (Unit 1/7, Transport/Vehicle): "On Attack:
    You may put a card from your discard pile on the bottom of your deck.  If you
    do, create a Credit token."

    `push_bottom_from_discard(own_only=True, count=1)` -- whose always-offered
    finish IS the "you may" -- with the new `then_create_credit` rider, settled at
    the finish so bottoming nothing creates nothing (that is exactly the "If you
    do").  An empty discard pile fizzles with no prompt."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_sandcrawler_recycle)])


@card_ability("LAW", "240")
def _milodon_rider():
    """LAW_240 -- Milodon Rider (Unit 5/6, Creature/Fringe, Ambush): "When Played:
    You may return another friendly non-leader unit to its owner's hand."

    A plain optional `ReturnToHand`; `not_self` is the printed "another" and
    `non_leader` the printed restriction.  Ambush needs no registration (the keyword
    engine owns it), and the two are independent -- the Ambush attack window opens
    from the enter-play bus, this trigger from the same entry."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ReturnToHand(TargetSpec(controller="friendly", kind="unit",
                                         predicates=("not_self", "non_leader")))],
    )


# ==============================================================================
# Group ``law-set:11`` -- Card advantage & disruption (3 cards)
# ==============================================================================

@card_ability("LAW", "241")
def _the_blade_wing():
    """LAW_241 -- The Blade Wing (Unit 3/3, Fighter/Rebel/Vehicle): "When Played:
    You may return a non-leader unit to its owner's hand."

    A plain optional `ReturnToHand`.  Unlike Milodon Rider LAW_240 the target is
    `controller="any"` -- the card says "a non-leader unit", not "a friendly one" --
    and it is NOT self-excluded, since the Blade Wing is itself a legal (if odd)
    target the moment it enters."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        effects=[ReturnToHand(TargetSpec(controller="any", kind="unit",
                                         predicates=("non_leader",)))],
    )


def _improvise_peek(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_peek_top
    push_peek_top(state, source_ci, mode="may_play_discard", cost_reduction=1)
    return state


@card_ability("LAW", "242")
def _improvise():
    """LAW_242 -- Improvise (Event, Gambit, cost 1): "Look at the top card of your
    deck.  You may play it.  It costs 1 resource less.  If you don't, you may
    discard it."

    Ezra Bridger SOR_192's `push_peek_top(mode="may_play_discard")` verbatim -- that
    mode already offers exactly the three branches this card spells out (play it /
    discard it / leave it on top), and its long-standing `cost_reduction` field is
    the "1 resource less" (read at `PlayTopCard`, so it moves both affordability and
    the resources actually exhausted).  An unaffordable top card simply is not
    offered the play branch."""
    return EventAbility(effects=[CustomEffect(fn=_improvise_peek)])


def _salvaged_materials(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(
        state, source_ci, free=False, cost_reduction=3,
        from_discard_only=True, trait="Item", then_defeat_at_regroup=True)
    return state


@card_ability("LAW", "245")
def _salvaged_materials_event():
    """LAW_245 -- Salvaged Materials (Event, Supply, cost 1): "Play an Item upgrade
    from your discard pile.  It costs 3 resources less.  At the start of the next
    regroup phase, defeat it."

    `push_play_upgrade_from_hand` at the Kylo Ren LOF_1 source setting
    (`from_discard_only=True` -- the controller's OWN discard pile, no hand) plus the
    Cin Drallig LOF_150 `trait` filter, paid (`free=False`) at `cost_reduction=3`,
    with the new `then_defeat_at_regroup` rider stamping the played upgrade with the
    Sneak Attack SOR_219 delayed-defeat flag.  ⚠️ That sweep had only ever seen
    TOKEN upgrades (Jetpack SHD_225), which cease to exist -- it now sends a real
    card to its owner's discard instead, or the rental would leave the game.
    With no affordable Item upgrade in the pile the decision is never pushed."""
    return EventAbility(effects=[CustomEffect(fn=_salvaged_materials)])


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:12`` — Combat tricks, buffs & tempo (the set's LEADER block)
#
#   * LAW_3   Agent Kallus       — play a card ignoring its aspect penalties, both
#                                  sides, + a Heroism-play base heal when deployed.
#   * LAW_6   Vel Sartha         — Experience for a unit, a Credit for an opponent.
#   * LAW_7   Boba Fett          — a Credit when a friendly Bounty Hunter's attack
#                                  ends having killed the defender.
#   * LAW_14  Enfys Nest         — "use that On Attack ability again".
#   * LAW_16  The Client         — exhaust an enemy unit if you made a token.
#   * LAW_19  Alliance Outpost   — Epic Action [defeat a friendly token]: a token
#                                  or a Credit.
#   * LAW_31  Bossk              — +1/+1 to a unit, and you may -1/-1 another.
# ─────────────────────────────────────────────────────────────────────────────


def _kallus_play_ignoring_aspects(state, source_ci, target_id, event_ctx):
    """"Play a card from your hand, ignoring its aspect penalties." (Agent Kallus
    LAW_3, both sides — the deployed one simply costs no exhaust.)

    DOCUMENTED NARROWING: ``push_play_from_hand`` plays UNITS, so a card of another
    type is not offered — the standing limit of that decision (Count Dooku TWI_5's
    "a Separatist event/upgrade is not offered", Daimyo's Palace LAW_20's identical
    aspect-waiver Epic Action).  The card's own printed rules note — "Abilities that
    let you play a card require you to pay that card's cost unless specified
    otherwise" — is the decision's default (``free=False``)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, ignore_aspect_penalty=True)
    return state


@card_ability("LAW", "3")
def _agent_kallus_law():
    """LAW_3 — Agent Kallus, "Reconsider Your Allegiance" (Leader, Imperial Trooper).

    Undeployed: "Action [1 resource, Exhaust]: Play a card from your hand, ignoring
    its aspect penalties."  Deployed: the same Action for 1 resource and no exhaust,
    plus "When you play a Heroism card: Heal 2 damage from your base."

    ⚠️⚠️ **LAW_3 IS ALSO THE SHIELD TOKEN's (set, number)** — the token-collision
    hazard, in its token-UPGRADE flavour (LAW_2 is the Experience token; see Tobias
    Beckett).  Every spec here is one a token upgrade can never reach: an
    ``ActivatedAbility`` is enumerated only from ARENA UNITS (an attached upgrade
    needs a ``GrantedAbility`` wrapper), and a plain ``TriggerAbility`` is likewise
    only collected from cards in play, never from a host's ``attached_upgrades``.
    A ``GrantedAbility`` would NOT be safe here, and neither would a
    ``ConstantAbility`` or a passive marker.  A regression test pins it.

    The base heal takes ``fixed=EACH_FRIENDLY`` so it auto-resolves — a plain
    friendly-base TargetSpec prompts for a choice (Yularen SOR_109)."""
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()],
                         effects=[CustomEffect(fn=_kallus_play_ignoring_aspects)],
                         title="Play a card ignoring its aspect penalties",
                         undeployed_only=True),
        ActivatedAbility(costs=[PayResources(1)],
                         effects=[CustomEffect(fn=_kallus_play_ignoring_aspects)],
                         title="Play a card ignoring its aspect penalties",
                         deployed_only=True),
        TriggerAbility(
            trigger=WhenYouPlayCard(aspect="Heroism"),
            effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                        fixed=EACH_FRIENDLY))],
            deployed_only=True),
    ]


def _vel_experience_then_opponent_credit(state, source_ci, target_id, event_ctx):
    """"You may give an Experience token to a unit.  If you do, an opponent creates
    a Credit token." (Vel Sartha LAW_6 deployed.)

    The "If you do" binding (Bright Hope SOR_99): the gift and the drawback are ONE
    effect, so the opponent can never be paid for a gift that did not happen."""
    from swu.engine.tokens import attach_token, create_credit_token
    if target_id is None:
        return state
    found = state.find_instance(target_id)
    if found is None:
        return state
    host_ps, host_ci = found
    attach_token(state, host_ps, host_ci, "Experience")
    opponent = next((p for p in state.players
                     if p.player_id != source_ci.owner_id), None)
    if opponent is not None:
        create_credit_token(state, opponent)
    return state


@card_ability("LAW", "6")
def _vel_sartha_law():
    """LAW_6 — Vel Sartha, "Aldhani Insurgent" (Leader, Rebel).

    Undeployed: "Action [Exhaust]: Give an Experience token to a unit.  An opponent
    creates a Credit token."  Deployed: "On Attack: You may give an Experience token
    to a unit.  If you do, an opponent creates a Credit token."

    The undeployed side is two independent effects — the Credit is unconditional —
    with the TARGETED one first so the resolver prompts exactly once (the
    Mandalorian SHD_18 rule).  The deployed side's "If you do" makes the pair
    atomic, so it is ONE ``CustomEffect.target`` instead (the Kihraxz SHD_118
    shape).  "An opponent creates a Credit token" is the new
    ``CreateCreditToken(player="opponent")``; with two players "an opponent" needs
    no choice, as the card's own rules note allows for."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[GiveToken("Experience",
                               TargetSpec(controller="any", kind="unit")),
                     CreateCreditToken(count=1, player="opponent")],
            title="Give an Experience token; an opponent creates a Credit",
            undeployed_only=True),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_vel_experience_then_opponent_credit,
                                  target=TargetSpec(controller="any", kind="unit"))],
            optional=True,
            deployed_only=True),
    ]


def _boba_law_exhaust_for_credit(state, source_ci, target_id, event_ctx):
    """"You may exhaust this leader.  If you do, create a Credit token." (Boba Fett
    LAW_7 undeployed.)

    The exhaust is bundled into the payoff rather than expressed as an
    ``ExhaustCard(fixed=SELF)`` effect: an UNDEPLOYED leader sits in the base zone
    and is no arena unit, so that spec silently falls back to a full target prompt
    (the Boba Fett JTL_9 convention)."""
    from swu.engine.tokens import create_credit_token
    found = state.find_instance(source_ci.instance_id)
    if found is None:
        return state
    found[1].exhausted = True
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "7")
def _boba_fett_law():
    """LAW_7 — Boba Fett, "Krayt's Claw Commander" (Leader, Bounty Hunter Underworld).

    Undeployed: "When a friendly Bounty Hunter unit's attack ends: If the defending
    unit was defeated, you may exhaust this leader.  If you do, create a Credit
    token."  Deployed: Raid 1 (keyword layer) + the same observer, free and
    mandatory.

    Both sides ride the new ``WhenFriendlyUnitAttackEnds`` observer — the group
    analogue of the self-referential ``WhenAttackEnds``, which exists because the
    card's printed rules note is explicit that "The attacking Bounty Hunter unit
    doesn't need to survive the attack in order to create a Credit token": neither
    ``WhenAttackEnds`` (keyed on a survivor) nor ``OnAttackDefeatsUnit`` (fired only
    when the attacker lives) can say that.  The undeployed side is gated
    ``SOURCE_READY`` so the "you may exhaust" is never a dead prompt."""
    return [
        TriggerAbility(
            trigger=WhenFriendlyUnitAttackEnds(traits=("Bounty Hunter",),
                                               require_defender_defeated=True),
            effects=[CustomEffect(fn=_boba_law_exhaust_for_credit)],
            optional=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
            undeployed_only=True),
        TriggerAbility(
            trigger=WhenFriendlyUnitAttackEnds(traits=("Bounty Hunter",),
                                               require_defender_defeated=True),
            effects=[CreateCreditToken(count=1)],
            deployed_only=True),
    ]


@card_ability("LAW", "14")
def _enfys_nest_law():
    """LAW_14 — Enfys Nest, "Until We Can Go No Higher" (Leader, Underworld).

    Undeployed: "When you use an 'On Attack' ability: You may pay 2 resources and
    exhaust this leader.  If you do, use that ability again."  Deployed: the same,
    free, but "Use this ability only once each round."

    Two ``OnAttackRedo`` markers, one per side — the exact sibling of Grand Admiral
    Thrawn JTL_2's pair of ``WhenDefeatedRedo`` markers, read at the shared
    ability-redo chokepoint ``resolver._schedule_ability_redo``.  So the whole card
    is two passive markers and no trigger of its own: the chokepoint offers the
    re-use as an ordinary ``trigger_option`` inserted just below the original
    ability's resolution, which is why "use that ability again" needs no new
    decision kind.  Price is charged on ACCEPT only (declining a "you may" is not a
    use) and the redo is offered only while payable, and
    ``event_ctx["ability_redo"]`` stops a re-use arming another."""
    return [
        OnAttackRedo(cost_resources=2, cost_exhaust_source=True,
                     undeployed_only=True),
        OnAttackRedo(once_per_round=True, deployed_only=True),
    ]


@card_ability("LAW", "16")
def _the_client_law():
    """LAW_16 — The Client, "Please Lower Your Blaster" (Leader, Imperial Official).

    Undeployed: "Action [Exhaust]: If you created a token this phase, exhaust an
    enemy unit."  Deployed: Shielded (keyword layer) + "On Attack: If you created a
    token this phase, exhaust an enemy unit."

    The clause is a candidate BOARD GATE (the new
    ``controller_created_token_this_phase`` predicate over
    ``game_memory.tokens_created_this_phase``), NOT the ability's ``condition`` —
    the card's own rules note says "The Client's leader ability still can be used as
    an action even if you didn't create a token this phase (but you don't exhaust a
    unit)", which is exactly what an empty candidate set gives: the Action stays
    legal and simply fizzles.  A ``ConditionalEffect`` could not express it either
    way, since it cannot carry a targeted sub-effect."""
    gate = TargetSpec(controller="enemy", kind="unit",
                      predicates=("ready", "controller_created_token_this_phase"))
    return [
        ActivatedAbility(costs=[ExhaustSelf()],
                         effects=[ExhaustCard(gate)],
                         title="Exhaust an enemy unit (if you created a token)",
                         undeployed_only=True),
        TriggerAbility(trigger=OnAttack(),
                       effects=[ExhaustCard(gate)],
                       deployed_only=True),
    ]


def _alliance_outpost_epic(state, source_ci, target_id, event_ctx):
    """"Epic Action [defeat a friendly token]: Give an Experience or Shield token to
    a unit, or create a Credit token." (Alliance Outpost LAW_19.)

    The cost is Han Solo LAW_17's ``cull_for_damage(pool="tokens")`` pinned to
    exactly one pick (``min_count=max_count=1``, so there is no decline — it is a
    cost), and the new ``then_modal`` rider replaces that decision's damage with the
    card's three-way choice, pushed after the pop so the modal resolves on a clean
    stack."""
    from swu.engine.actions import push_cull_for_damage
    push_cull_for_damage(
        state, source_ci, pool="tokens", min_count=1, max_count=1,
        then_modal=["give_experience_unit", "give_shield_unit",
                    "create_credit_token"])
    return state


@card_ability("LAW", "19")
def _alliance_outpost_law():
    """LAW_19 — Alliance Outpost (Base, 26 HP).

    Gated on ``CONTROLLER_HAS_TOKEN`` — the new card-type-blind widening of
    ``CONTROLLER_HAS_TOKEN_UNIT``, matching exactly the pool the cull offers — so a
    once-per-GAME Epic Action can never be burnt on a cost that cannot be paid.
    (The card's own printed rules note is about Ambush and belongs to another card;
    the DB carries it verbatim.)"""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_alliance_outpost_epic)],
        title="Defeat a friendly token: give a token or create a Credit",
        epic=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TOKEN),
    )


@card_ability("LAW", "31")
def _bossk_law():
    """LAW_31 — Bossk, "Join Our Merry Band" (Unit, Bounty Hunter Underworld, 3/5).

    "On Attack: Give a unit +1/+1 for this phase.  You may give a unit -1/-1 for
    this phase."

    TWO single-effect ``OnAttack`` abilities rather than one two-effect ability (the
    Sabine's Masterpiece JTL_250 shape): the buff is mandatory and the debuff is a
    "you may", and only separate abilities can carry different ``optional`` flags —
    a two-effect ability would also hit the resolve_effects skip-earlier-no-target
    wart.  Neither clause says "another", so both may name the same unit, and either
    may name a friendly or enemy one."""
    return [
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=1, hp=1,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)]),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=-1, hp=-1,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
            optional=True),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:13`` — Combat tricks, buffs & tempo (the token-payoff block)
#
#   * LAW_39  Latts Razzi        — a Shield OR an Experience, then her power as
#                                  damage (the token changes the number).
#   * LAW_43  Shadow Cloaking    — ready a unit AND shield it.
#   * LAW_46  Chirrut Imwe       — heal 4 after damaging a base.
#   * LAW_55  Chopper            — 1 Experience, or 2 with a Cunning/Vigilance unit.
#   * LAW_59  Highsinger         — an Experience on entry and on death.
#   * LAW_61  Asajj Ventress     — ready another Bounty Hunter.
#   * LAW_69  The Ghost          — Experience + Shield on 1 unit, or on 2.
# ─────────────────────────────────────────────────────────────────────────────


def _latts_choose_token(state, source_ci, target_id, event_ctx):
    """Latts Razzi LAW_39 When Played: "Give a Shield token or an Experience token
    to this unit" — the one-of-two ``choose_two_modal`` SELECTOR over the two token
    options registered at ability indices 1 and 2 (the Lightmaker SEC_207 shape;
    this is a UNIT card, so the option specs must be ``EventAbility``, which is
    never trigger-collected)."""
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1)
    return state


def _latts_token_then_damage(state, source_ci, target_id, event_ctx, token):
    """"Give a <token> to this unit.  Then, she deals damage equal to her power to
    an enemy ground unit." (Latts Razzi LAW_39, one branch.)

    ONE effect, so the branch prompts exactly once: a leading no-target (or
    ``fixed=SELF``) effect would still consume a ChooseTarget of its own at the
    current ``effect_idx`` (the Mandalorian SHD_18 wart), letting the two halves
    name different units.  The token is attached BEFORE the power is read, which is
    the whole point of the printed order — an Experience token is +1/+1, and the
    card's own rules note says "Abilities that refer to a card's power include
    temporary modifiers"."""
    from swu.engine.tokens import attach_token
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import _apply_deal_damage
    found = state.find_instance(source_ci.instance_id)
    if found is None:
        return state
    attach_token(state, found[0], found[1], token)
    if target_id is None:
        return state
    amount = compute_power(state, found[1])
    if amount > 0:
        _apply_deal_damage(state, target_id, amount,
                           source_name=source_ci.card_def.display_name)
    return state


def _latts_shield_then_damage(state, source_ci, target_id, event_ctx):
    return _latts_token_then_damage(state, source_ci, target_id, event_ctx, "Shield")


def _latts_experience_then_damage(state, source_ci, target_id, event_ctx):
    return _latts_token_then_damage(state, source_ci, target_id, event_ctx,
                                    "Experience")


@card_ability("LAW", "39")
def _latts_razzi_law():
    """LAW_39 — Latts Razzi (Unit, Bounty Hunter Underworld, 2/1): "When Played:
    Give a Shield token or an Experience token to this unit.  Then, she deals damage
    equal to her power to an enemy ground unit."

    Each branch is ONE targeted ``CustomEffect`` doing both halves in the printed
    order (see the helper).  DOCUMENTED DEVIATION: an effect with no legal target
    fizzles, so with no enemy ground unit in play the token is not given either —
    the price of keeping the two halves in one prompt, and the alternative (a
    leading fixed effect) would let the player name two different units."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_latts_choose_token)]),
        EventAbility(effects=[
            CustomEffect(fn=_latts_shield_then_damage,
                         target=TargetSpec(controller="enemy", kind="unit",
                                           arena="ground")),
        ]),
        EventAbility(effects=[
            CustomEffect(fn=_latts_experience_then_damage,
                         target=TargetSpec(controller="enemy", kind="unit",
                                           arena="ground")),
        ]),
    ]


def _shadow_cloaking(state, source_ci, target_id, event_ctx):
    """"Ready a unit and give a Shield token to it." (Shadow Cloaking LAW_43.)

    ONE ``CustomEffect.target``, not a ``ReadyCard`` + ``GiveToken`` pair — two
    targeted effects would prompt twice and could land on different units (the Kylo
    Ren SHD_141 rule)."""
    from swu.engine.tokens import attach_token
    from swu.engine.actions import note_unit_readied
    if target_id is None:
        return state
    found = state.find_instance(target_id)
    if found is None:
        return state
    ps, ci = found
    note_unit_readied(state, ci)        # feeds the WhenUnitReadies observer
    ci.exhausted = False
    attach_token(state, ps, ci, "Shield")
    return state


@card_ability("LAW", "43")
def _shadow_cloaking_law():
    """LAW_43 — Shadow Cloaking (Event): "Ready a unit and give a Shield token to
    it."  Either player's unit, as printed; readying an enemy is a downside the
    controller simply never takes."""
    return EventAbility(effects=[
        CustomEffect(fn=_shadow_cloaking,
                     target=TargetSpec(controller="any", kind="unit")),
    ])


@card_ability("LAW", "46")
def _chirrut_imwe_law():
    """LAW_46 — Chirrut Imwe (Unit, Force Guardian, 8/6; Saboteur): "When Attack
    Ends: If this unit dealt combat damage to a base, you may heal 4 damage from
    another unit."

    Saboteur is the keyword layer.  The trigger is Maul LAW_54's
    ``WhenAttackEnds(require_base_damage=True)`` verbatim.  DOCUMENTED DEVIATION:
    that trigger's firing site only runs for an attacker still in play, whereas the
    card's rules note says "Chirrut does not need to survive the attack" — but a
    base attack never damages the attacker, so the two readings differ only if
    something else killed him during his own attack.  ``damaged`` keeps the "you
    may" off the table when no other unit has any damage to heal (the
    "don't offer a no-op" rule)."""
    return TriggerAbility(
        trigger=WhenAttackEnds(require_base_damage=True),
        effects=[Heal(4, TargetSpec(controller="any", kind="unit",
                                    predicates=("not_self", "damaged")))],
        optional=True,
    )


def _chopper_experience(state, source_ci, target_id, event_ctx):
    """"Give an Experience token to this unit.  If you control a Cunning or
    Vigilance unit, give 2 Experience tokens to him instead." (Chopper LAW_55.)

    The conditional-MAGNITUDE CustomEffect (Zeb Orellios LAW_45): the OR-of-aspects
    is computed inline, which no single ``Condition`` expresses.  Chopper himself is
    a Cunning card, so he satisfies his own clause the moment he is in play — which
    is the printed reading ("a Cunning or Vigilance unit", not "another")."""
    from swu.engine.tokens import attach_token
    found = state.find_instance(source_ci.instance_id)
    if found is None:
        return state
    ps, ci = found
    controller = state.player_by_id(source_ci.owner_id)
    boosted = any(
        {"Cunning", "Vigilance"} & {a.name for a in (u.card_def.aspects or ())}
        for arena in (controller.ground_arena, controller.space_arena)
        for u in arena)
    for _ in range(2 if boosted else 1):
        attach_token(state, ps, ci, "Experience")
    return state


@card_ability("LAW", "55")
def _chopper_law():
    """LAW_55 — Chopper (Unit, Droid Spectre, 1/2; Raid 1).  Raid is the keyword
    layer; the When Played is the conditional-magnitude effect above."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_chopper_experience)])


@card_ability("LAW", "59")
def _highsinger_law():
    """LAW_59 — Highsinger (Unit, Bounty Hunter Droid, 4/2): "When Played: Give an
    Experience token to another friendly Command unit." / "When Defeated: Give an
    Experience token to a friendly Aggression unit."

    Two independent triggers.  The When Defeated one needs no special handling
    despite the LAW_159 corpse-timing trap: its effect is TARGETED, so it resolves
    from its own decision on a later ``apply`` — by which time the dying unit has
    been homed (and it is excluded anyway, being neither a legal Aggression target
    nor in an arena)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[GiveToken("Experience",
                               TargetSpec(controller="friendly", kind="unit",
                                          aspects=("Command",),
                                          predicates=("not_self",)))]),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[GiveToken("Experience",
                               TargetSpec(controller="friendly", kind="unit",
                                          aspects=("Aggression",)))]),
    ]


@card_ability("LAW", "61")
def _asajj_ventress_law():
    """LAW_61 — Asajj Ventress (Unit, Bounty Hunter Sith, 3/3): "When Played: You
    may ready another Bounty Hunter unit."

    ``exhausted`` keeps the "you may" off the table when there is nothing to ready
    (the "don't offer a no-op" rule), and ``not_self`` is "another"."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ReadyCard(TargetSpec(controller="any", kind="unit",
                                      traits=("Bounty Hunter",),
                                      predicates=("not_self", "exhausted")))],
        optional=True,
    )


def _the_ghost_tokens(state, source_ci, target_id, event_ctx):
    """"You may give an Experience token and a Shield token to a unit.  If you
    control a Vigilance or Aggression unit, you may give an Experience token and a
    Shield token to each of up to 2 units instead." (The Ghost LAW_69.)

    The conditional-magnitude read (Zeb LAW_45) decides only ``max_targets``; the
    payoff is the ordinary select-up-to-N loop with the new
    ``extra_token_type`` rider, which is the only way to put TWO DIFFERENT tokens on
    each chosen unit (``token_count`` repeats one kind).  The printed "you may" is
    ``select_token``'s always-legal finish, so no optional trigger is needed — one
    would prompt twice."""
    from swu.engine.actions import push_select_token
    controller = state.player_by_id(source_ci.owner_id)
    boosted = any(
        {"Vigilance", "Aggression"} & {a.name for a in (u.card_def.aspects or ())}
        for arena in (controller.ground_arena, controller.space_arena)
        for u in arena)
    push_select_token(state, source_ci, token_type="Experience",
                      extra_token_type="Shield",
                      max_targets=2 if boosted else 1)
    return state


@card_ability("LAW", "69")
def _the_ghost_law():
    """LAW_69 — The Ghost (Unit, Transport Vehicle, 4/4)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_the_ghost_tokens)])


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:14`` — Combat tricks, buffs & tempo
#
#   * LAW_73 Patient Hunter — "When the regroup phase starts: You may give an
#     Experience token to a non-leader unit.  If you do, that unit can't ready
#     during this regroup phase."
#   * LAW_74 Maz Kanata — "When Attack Ends: … search the top 5 for an Underworld
#     unit and play it.  It costs 4 less and enters play ready.  At the start of
#     the regroup phase, put that unit on the bottom of your deck."
#   * LAW_87 Jango Fett — "On Attack: If this unit is upgraded, exhaust an enemy
#     unit."
#   * LAW_88 Anakin Skywalker — "When a friendly unit's attack ends: If no other
#     units have attacked this phase, you may return it to its owner's hand.  If
#     you do, heal 2 damage from your base."
#   * LAW_91 Val — Shield a friendly unit on entry, an enemy one on defeat.
#   * LAW_95 Finn — "On Attack: You may give a Shield token to a non-unique unit."
#   * LAW_97 Imperial Door Technician — "When Defeated: Heal 2 from your base."
# ─────────────────────────────────────────────────────────────────────────────


def _patient_hunter_token_then_lock(state, source_ci, target_id, event_ctx):
    """"You may give an Experience token to a non-leader unit.  If you do, that
    unit can't ready during this regroup phase." (Patient Hunter LAW_73.)

    ONE targeted effect, the "If you do" binding (Bright Hope SOR_99): the token
    and the ready-lock must be atomic, and a leading fixed effect would consume a
    second ChooseTarget of its own (the Mandalorian SHD_18 wart).

    The lock is the standing per-instance ``cannot_ready_this_round`` flag (No Good
    to Me Dead SOR_186), which ``_ready_all_cards`` skips and the round rollover
    clears.  This trigger fires at the START of the regroup phase — i.e. before
    that phase's ready step and after the round's only other one — so "during this
    regroup phase" and "this round" name exactly the same skipped ready.
    DOCUMENTED DEVIATION: with Max Rebo LAW_72's *additional* regroup phase in play
    the flag also holds through the second one.
    """
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    holder, unit = res
    from swu.engine.tokens import attach_token
    attach_token(state, holder, unit, "Experience")
    unit.cannot_ready_this_round = True
    return state


@card_ability("LAW", "73")
def _patient_hunter():
    """LAW_73 — Patient Hunter (Unit, Bounty Hunter, 3/3).

    A ``PhaseStartTrigger("regroup")`` (Contracted Hunter JTL_216), ``optional``
    for the printed "You may"; the target is any non-leader unit, either player's,
    so the lock can also be aimed at an enemy."""
    return TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[CustomEffect(
            fn=_patient_hunter_token_then_lock,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader",)),
        )],
        optional=True,
    )


def _maz_kanata_search_and_play(state, source_ci, target_id, event_ctx):
    """"Search the top 5 cards of your deck for an Underworld unit and play it.
    It costs 4 resources less and enters play ready.  At the start of the regroup
    phase, put that unit on the bottom of your deck (if it is still in play)."
    (Maz Kanata LAW_74.)

    The Kelleran Beq LOF_100 search-and-play with the new ``bottom_at_regroup``
    rider — the deck-bound sibling of Triple Dark Raid SHD_194's
    ``return_at_regroup``.  The sweep relocates rather than defeats, which is what
    the card's own rules note demands ("Putting a unit on the bottom of your deck
    from play does not trigger any 'When Defeated' abilities on that unit")."""
    from swu.engine.actions import push_search_and_play
    push_search_and_play(
        state, source_ci, window=5, cost_reduction=4,
        eligible=lambda cd: "Underworld" in (getattr(cd, "traits", None) or ()),
        enters_ready=True, bottom_at_regroup=True,
    )
    return state


@card_ability("LAW", "74")
def _maz_kanata_wheres_my_boyfriend():
    """LAW_74 — Maz Kanata (Unit, Underworld, 4/4).

    "If this unit survived" is intrinsic to ``WhenAttackEnds`` (Vermillion
    LAW_215): the firing site only sets ``attack_ended_survivor`` for an attacker
    still in play."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[CustomEffect(fn=_maz_kanata_search_and_play)],
    )


@card_ability("LAW", "87")
def _jango_fett_wily_mercenary():
    """LAW_87 — Jango Fett (Unit, Bounty Hunter/Underworld, 6/5, Shielded):
    "On Attack: If this unit is upgraded, exhaust an enemy unit."

    ``SOURCE_ATTACHED_UPGRADES_MIN`` at 1 (Zam Wesell SEC_29) gates COLLECTION, so
    a bare Jango is never offered the trigger — and his printed Shielded means he
    normally carries a Shield token, which counts as an upgrade exactly as
    "upgraded" always does."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ExhaustCard(TargetSpec(controller="enemy", kind="unit"))],
        condition=ConditionCheck(Condition.SOURCE_ATTACHED_UPGRADES_MIN, param=1),
    )


def _anakin_return_available(state, source_ci, event_ctx):
    """Availability gate for LAW_88's second clause, so the optional trigger is
    never a dead prompt: the card's own rules note says "If the attacking unit is
    defeated, it cannot be returned to hand by Anakin's ability", so the unit whose
    attack just ended must still be standing in an arena.  (The first clause —
    "no other units have attacked this phase" — is the shared
    ``NO_OTHER_UNIT_ATTACKED_THIS_PHASE`` atom on the ability's ``condition``.)"""
    att_id = event_ctx.get("attack_ended_attacker")
    if att_id is None:
        return False
    res = state.find_instance(att_id)
    if res is None:
        return False
    from swu.engine.state import Zone
    return res[1].zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)


def _anakin_return_and_heal(state, source_ci, target_id, event_ctx):
    """"… you may return it to its owner's hand.  If you do, heal 2 damage from
    your base." (Anakin Skywalker LAW_88.)

    ONE effect, the "If you do" binding: the heal is paid for by the bounce, so a
    bounce that cannot happen must not heal.  "It" is the unit whose attack just
    ended, read off ``event_ctx["attack_ended_attacker"]`` (there is no target
    choice to make — the trigger names the unit)."""
    att_id = event_ctx.get("attack_ended_attacker")
    if att_id is None:
        return state
    res = state.find_instance(att_id)
    if res is None:
        return state
    from swu.engine.state import Zone
    if res[1].zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return state          # defeated by the attack — nothing to return, no heal
    from swu.abilities.resolver import _apply_return_to_hand, _apply_heal
    _apply_return_to_hand(state, att_id)
    controller = state.player_by_id(source_ci.owner_id)
    if controller is not None and controller.base_instance is not None:
        _apply_heal(state, source_ci, controller.base_instance.instance_id, 2)
    return state


@card_ability("LAW", "88")
def _anakin_skywalker_prescient_podracer():
    """LAW_88 — Anakin Skywalker (Unit, Force, 2/4).

    The plain reading of ``WhenFriendlyUnitAttackEnds`` (Boba Fett LAW_7 built the
    trigger; this is the same observer without its "If the defending unit was
    defeated" narrowing), so it also fires when a friendly unit attacks a BASE.
    The board clause is the shared ``NO_OTHER_UNIT_ATTACKED_THIS_PHASE`` atom
    gating COLLECTION; the survival clause reads the EVENT (which unit attacked),
    which a ``condition`` cannot see, so it lives in ``available_fn`` (Shadow
    Caster JTL_169) — either way the trigger is simply not offered."""
    return TriggerAbility(
        trigger=WhenFriendlyUnitAttackEnds(),
        effects=[CustomEffect(fn=_anakin_return_and_heal,
                              available_fn=_anakin_return_available)],
        optional=True,
        condition=ConditionCheck(Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE),
    )


@card_ability("LAW", "91")
def _val_its_been_a_ride_babe():
    """LAW_91 — Val (Unit, Underworld, 2/4): "When Played: Give a Shield token to
    another friendly unit.  When Defeated: Give a Shield token to an enemy unit."

    Two plain ``GiveToken`` triggers.  The When Defeated one needs no Expendable
    Mercenary LAW_159 corpse-timing care — its effect is TARGETED, so it already
    resolves on a later ``apply``, by which time Val has landed in the discard."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[GiveToken("Shield", TargetSpec(controller="friendly",
                                                    kind="unit",
                                                    predicates=("not_self",)))]),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[GiveToken("Shield", TargetSpec(controller="enemy",
                                                    kind="unit"))]),
    ]


@card_ability("LAW", "95")
def _finn_looking_closer():
    """LAW_95 — Finn (Unit, Resistance, 6/5, Ambush): "On Attack: You may give a
    Shield token to a non-unique unit."

    The ``non_unique`` predicate (Fett's Firespray SOR_184) — note Finn himself is
    unique, so he can never shield himself.  Ambush is the keyword engine's."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Shield", TargetSpec(controller="any", kind="unit",
                                                predicates=("non_unique",)))],
        optional=True,
    )


@card_ability("LAW", "97")
def _imperial_door_technician():
    """LAW_97 — Imperial Door Technician (Unit, Imperial/Trooper, 2/2): "When
    Defeated: Heal 2 damage from your base."

    "Your base" is the ``fixed=EACH_FRIENDLY`` base idiom (Agent Kallus LAW_3), so
    the mandatory effect resolves inline with no prompt — and needs no corpse in
    the discard, so the LAW_159 timing wart does not apply."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:15`` — Combat tricks, buffs & tempo
#
#   * LAW_109 Tantive IV — "When Played: If a friendly unit was defeated this
#     phase, heal 4 damage from your base."
#   * LAW_110 Phoenix Squadron Fighters — "costs 1 less for each friendly damaged
#     unit."
#   * LAW_112 Boonta Eve Flagbearer — "When a friendly unit attacks: If no other
#     units have attacked this phase, heal 2 damage from your base."
#   * LAW_113 Shield Drive Outfitter — "When Played: You may pay 1 resource.  If
#     you do, give a Shield token to a unit."
#   * LAW_127 Kill Switch — "When Played: Exhaust attached unit."
#   * LAW_128 Veiled Strength — "Attached unit gains Grit."
#   * LAW_129 Mastery — "costs 1 less to play on a unique unit."
# ─────────────────────────────────────────────────────────────────────────────


@card_ability("LAW", "109")
def _tantive_iv_carrying_hope():
    """LAW_109 — Tantive IV (Unit, Capital Ship/Rebel/Vehicle, 5/8, Restore 2):
    "When Played: If a friendly unit was defeated this phase, heal 4 damage from
    your base."

    ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` (Wat Tambor TWI_6) gates COLLECTION, so
    a no-op never even fires; the heal is the ``fixed=EACH_FRIENDLY`` base idiom.
    Restore 2 is the keyword engine's."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[Heal(4, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
        condition=ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE),
    )


@card_ability("LAW", "110")
def _phoenix_squadron_fighters():
    """LAW_110 — Phoenix Squadron Fighters (Unit, Fighter/Rebel/Vehicle, 6/6):
    "This unit costs 1 resource less to play for each friendly damaged unit."

    The new ``per_friendly_damaged_unit`` scaling reduction — the AT-DP Occupier
    JTL_163 basis with the arena filter swapped for a controller one.  It is read
    at the single play-cost site, so it moves affordability and the resources
    actually exhausted alike, and the play path floors the cost at 0."""
    return CostReduction(amount=1, per_friendly_damaged_unit=True)


@card_ability("LAW", "112")
def _boonta_eve_flagbearer():
    """LAW_112 — Boonta Eve Flagbearer (Unit, Fringe, 1/3): "When a friendly unit
    attacks: If no other units have attacked this phase (including enemy units),
    heal 2 damage from your base."

    ``WhenUnitAttacks`` (Jedi Temple LOF_23) is the observer form of ``OnAttack``,
    so the Flagbearer watches every friendly attack including his own — and
    including one on a base.  The clause is the shared
    ``NO_OTHER_UNIT_ATTACKED_THIS_PHASE`` atom: both combat pipelines stamp the
    attacker into ``units_attacked_this_round`` at the DECLARE step, just before
    this fire, so "no OTHER units" is "the ledger holds only this one"."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(filter=TargetSpec(controller="friendly",
                                                  kind="unit")),
        effects=[Heal(2, TargetSpec(controller="friendly", kind="base",
                                    fixed=EACH_FRIENDLY))],
        condition=ConditionCheck(Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE),
    )


def _shield_drive_pay_and_shield(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, give a Shield token to a unit."
    (Shield Drive Outfitter LAW_113.)

    The Boba Fett LAW_214 binding: payment and payoff live in ONE CustomEffect, so
    accepting the optional trigger commits to both and the Shield can never land
    unpaid.  Affordability is guaranteed by the trigger's
    ``CONTROLLER_N_PLUS_READY_RESOURCES`` gate; the fn re-checks defensively."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state                       # cannot pay → no Shield ("if you do")
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.engine.tokens import attach_token
    attach_token(state, res[0], res[1], "Shield")
    return state


@card_ability("LAW", "113")
def _shield_drive_outfitter():
    """LAW_113 — Shield Drive Outfitter (Unit, Underworld, 1/3).  "A unit" names no
    controller, so an enemy unit is a legal (if odd) choice, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_shield_drive_pay_and_shield,
            target=TargetSpec(controller="any", kind="unit"),
        )],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=1),
    )


def _kill_switch_exhaust_host(state, source_ci, target_id, event_ctx):
    """"When Played: Exhaust attached unit." (Kill Switch LAW_127.)

    The host is located through ``event_ctx["attached_to_id"]``, which the
    upgrade-play path threads (Frozen in Carbonite SHD_193)."""
    host_id = event_ctx.get("attached_to_id")
    if host_id is None:
        return state
    res = state.find_instance(host_id)
    if res is not None:
        res[1].exhausted = True
    return state


@card_ability("LAW", "127")
def _kill_switch():
    """LAW_127 — Kill Switch (Upgrade, Condition, cost 2)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_kill_switch_exhaust_host)],
    )


@card_ability("LAW", "128")
def _veiled_strength():
    """LAW_128 — Veiled Strength (Upgrade, Innate, cost 3): "Attach to a non-leader
    unit.  Attached unit gains Grit."

    The upgrade-SELF ``KeywordGrant`` (Grievous's Wheel Bike TWI_236) — the only
    path by which an upgrade's keyword reaches its host, since the printed bar on
    an upgrade never transfers.  "Attach to a non-leader unit" is
    ``_upgrade_target_spec``'s text parser."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Grit", value=0)],
    )


@card_ability("LAW", "129")
def _mastery():
    """LAW_129 — Mastery (Upgrade, Learned, cost 4): "This upgrade costs 1 resource
    less to play on a unique unit."

    The new ``host_unique`` flag — ``host_named``'s sibling, keyed on a property of
    the chosen host rather than its name.  The play-cost path already knows the
    host an upgrade is being attached to."""
    return CostReduction(amount=1, host_unique=True)


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:16`` — Combat tricks, buffs & tempo
#
#   * LAW_133 Lost and Forgotten — "Defeat a non-leader unit.  If you do, heal 3
#     damage from your base."
#   * LAW_139 Admiral Motti — "Friendly leader units get +2/+2."
#   * LAW_140 Intimidator — "Return any number of friendly resources to their
#     owners' hands.  For each resource returned this way, create a Credit token."
#   * LAW_144 Phantom — "You may play a Heroism unit from your hand (paying its
#     cost) and give an Experience token to it."
#   * LAW_148 Smuggler's YT-2400 — "You may pay 1 resource.  If you do, this unit
#     gets +1/+1 for this phase."
#   * LAW_150 Fulcrum — "Attached unit gains the Rebel trait and 'Each other
#     friendly Rebel unit gets +2/+2.'"
#   * LAW_151 Profiteering Hunter — "Another friendly unit gets +1/+1 this phase."
# ─────────────────────────────────────────────────────────────────────────────


def _lost_and_forgotten(state, source_ci, target_id, event_ctx):
    """"Defeat a non-leader unit.  If you do, heal 3 damage from your base."
    (Lost and Forgotten LAW_133.)

    ONE targeted effect, the "If you do" binding: with no legal unit to defeat the
    event fizzles and no heal happens.  The heal is read AFTER the defeat, which
    matters not for a base but keeps the printed order."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit, _apply_heal
    _apply_defeat_unit(state, target_id)
    ps = state.player_by_id(source_ci.owner_id)
    if ps is not None and ps.base_instance is not None:
        _apply_heal(state, source_ci, ps.base_instance.instance_id, 3)
    return state


@card_ability("LAW", "133")
def _lost_and_forgotten_event():
    """LAW_133 — Lost and Forgotten (Event, cost 6)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_lost_and_forgotten,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader",)),
        )
    ])


@card_ability("LAW", "139")
def _admiral_motti_chain_of_command():
    """LAW_139 — Admiral Motti (Unit, Imperial/Official, 4/5): "Friendly leader
    units get +2/+2."

    A plain aura over the ``leader_unit`` predicate — a LEADER card standing in an
    arena, i.e. a deployed one (Pau City TWI_19)."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("leader_unit",)),
        effects=[StatBonus(power=2, hp=2)],
    )


def _intimidator_return_resources(state, source_ci, target_id, event_ctx):
    """"Return any number of friendly resources to their owners' hands.  For each
    resource returned this way, create a Credit token." (Intimidator LAW_140.)

    The pay-any-number loop (Curious Flock LOF_255) at its new
    ``cost_source="return_resource"`` / ``payoff="credit"`` combination: each step
    hands one resource back and mints one Credit.  It is a REAL choice — a returned
    resource is a card in hand plus a one-shot Credit, against a permanent resource
    — so it cannot collapse to an optimal default, and "any number" is the
    always-offered finish (including zero)."""
    from swu.engine.actions import push_pay_resources_for_tokens
    push_pay_resources_for_tokens(
        state, source_ci, max_resources=None,
        cost_source="return_resource", payoff="credit",
    )
    return state


@card_ability("LAW", "140")
def _intimidator_citadel_overwatch():
    """LAW_140 — Intimidator (Unit, Capital Ship/Imperial/Vehicle, 11/11)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_intimidator_return_resources)],
    )


def _phantom_heroism_units_in_hand(state, source_ci, event_ctx):
    """Availability gate for LAW_144: at least one affordable Heroism UNIT in the
    controller's hand, so the optional trigger is never a dead prompt."""
    from swu.cards.models import Unit
    from swu.engine.actions import _effective_cost
    ps = state.player_by_id(source_ci.owner_id)
    budget = ps.available_resources + len(ps.credits)
    for c in ps.hand:
        cd = c.card_def
        if not isinstance(cd, Unit):
            continue
        if "Heroism" not in {a.name for a in (getattr(cd, "aspects", None) or ())}:
            continue
        if _effective_cost(cd, ps, state) <= budget:
            return True
    return False


def _phantom_play_heroism_unit(state, source_ci, target_id, event_ctx):
    """"You may play a Heroism unit from your hand (paying its cost) and give an
    Experience token to it." (Phantom LAW_144.)

    ``push_play_from_hand(aspect="Heroism")`` with the ``then_select_token`` SETTLE
    payoff narrowed by ``restrict_played`` to the unit that was just played — the
    only ordering that runs AFTER the play (Lando JTL_3 / The Burden of Masters
    LOF_125)."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(
        state, source_ci, aspect="Heroism",
        then_select_token={"token_type": "Experience", "max_targets": 1,
                           "restrict_played": True},
    )
    return state


@card_ability("LAW", "144")
def _phantom_spectre_shuttle():
    """LAW_144 — Phantom (Unit, Rebel/Transport/Vehicle, 2/2).  ``push_play_from_hand``
    has no decline, so the printed "you may" is the optional trigger itself."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_phantom_play_heroism_unit,
                              available_fn=_phantom_heroism_units_in_hand)],
        optional=True,
    )


def _yt2400_pay_and_buff(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, this unit gets +1/+1 for this phase."
    (Smuggler's YT-2400 LAW_148.)  The Boba Fett LAW_214 binding, with no target to
    choose — the buff always lands on the source."""
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, source_ci.instance_id, 1, 1,
        Duration.THIS_PHASE))
    return state


@card_ability("LAW", "148")
def _smugglers_yt_2400():
    """LAW_148 — Smuggler's YT-2400 (Unit, Transport/Vehicle, 4/5, Ambush)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_yt2400_pay_and_buff)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=1),
    )


@card_ability("LAW", "150")
def _fulcrum():
    """LAW_150 — Fulcrum (Upgrade, Innate, cost 5): "Attach to a non-Vehicle unit.
    Attached unit gains the Rebel trait and 'Each other friendly Rebel unit gets
    +2/+2.'"

    Two specs, one per clause:

    * the trait is an upgrade-SELF ``TraitGrant`` — the trait layer's
      attached-upgrade scan confers it on the HOST (Foundling SHD_69);
    * the granted aura is a ``ConstantAbility(via_host=True)`` (Figure of Unity
      SEC_104), which resolves with the HOST as its source, so "each OTHER friendly
      Rebel unit" excludes the host and reads its controller.  LAW_150 is the first
      such aura carrying a StatBonus rather than keywords, which is what the
      ``_via_host_stat_bonus`` pass adds.

    The host itself is a Rebel by the clause above, and is excluded by ``not_self``
    exactly as printed."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[TraitGrant(trait="Rebel")],
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Rebel",), predicates=("not_self",)),
            effects=[StatBonus(power=2, hp=2)],
            via_host=True,
        ),
    ]


@card_ability("LAW", "151")
def _profiteering_hunter():
    """LAW_151 — Profiteering Hunter (Unit, Bounty Hunter/Underworld, 1/3): "When
    Played: Another friendly unit gets +1/+1 for this phase." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[ModifyStats(power=1, hp=1,
                             target=TargetSpec(controller="friendly", kind="unit",
                                               predicates=("not_self",)),
                             duration=Duration.THIS_PHASE)],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:17`` — Combat tricks, buffs & tempo
#
#   * LAW_157 Target Tagger — "You may attack with a unit.  If it's a Bounty
#     Hunter, it gets +2/+0 for this attack."
#   * LAW_165 Combat Exercise — "Exhaust a friendly unit.  If you do, give 2
#     Experience tokens to it."
#   * LAW_171 Stockpile — "Resource this event and the top card of your deck."
#   * LAW_182 Weazel — "On Attack: Another friendly unit gains Raid 2 this phase."
#   * LAW_185 Ben Solo — "When Played/When Defeated: Ready another friendly unit.
#     It can't be attacked this phase."
#   * LAW_186 Enfys Nest's Helmet — "Attached unit gains: 'On Attack: You may give
#     another unit +3/+0 for this phase.'"
#   * LAW_193 Mid Rim Sharpshooter — "You may pay 1 resource.  If you do, an
#     opponent discards a card from their hand."
# ─────────────────────────────────────────────────────────────────────────────


def _target_tagger_attack(state, source_ci, target_id, event_ctx):
    """"You may attack with a unit.  If it's a Bounty Hunter, it gets +2/+0 for
    this attack." (Target Tagger LAW_157.)  ``bonus_trait`` is exactly that gate:
    the bonus applies only when the CHOSEN attacker carries the trait (Fleet
    Lieutenant SOR_137's field)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, 2, 0, optional=True,
                        bonus_trait="Bounty Hunter")
    return state


@card_ability("LAW", "157")
def _target_tagger():
    """LAW_157 — Target Tagger (Unit, Bounty Hunter/Underworld, 3/3)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_target_tagger_attack)],
    )


def _combat_exercise(state, source_ci, target_id, event_ctx):
    """"Exhaust a friendly unit.  If you do, give 2 Experience tokens to it."
    (Combat Exercise LAW_165.)

    ONE targeted effect, the "If you do" binding (Kylo SHD_141): the exhaust is the
    cost and the tokens the payoff, and the ``ready`` predicate on the candidate
    set means an already-exhausted unit — which could not pay — is never offered."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None or res[1].exhausted:
        return state
    holder, unit = res
    unit.exhausted = True
    from swu.engine.tokens import attach_token
    attach_token(state, holder, unit, "Experience")
    attach_token(state, holder, unit, "Experience")
    return state


@card_ability("LAW", "165")
def _combat_exercise_event():
    """LAW_165 — Combat Exercise (Event, cost 1)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_combat_exercise,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("ready",)),
        )
    ])


def _stockpile(state, source_ci, target_id, event_ctx):
    """"Resource this event and the top card of your deck." (Stockpile LAW_171.)

    An EVENT is placed in its owner's discard BEFORE its ability resolves, so the
    card resources itself straight out of that pile — no new zone plumbing, and
    card conservation holds because nothing else touches it afterwards.  Both cards
    enter EXHAUSTED, which the card's own rules note spells out ("Resources enter
    play exhausted") and is the CR default for a mid-phase resource; that is why
    this does not reuse ``_resource_top_of_deck``, which enters a READY one for the
    cards that print it (When Has Become Now SEC_245)."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    ps = state.player_by_id(source_ci.owner_id)

    def _resource(ci):
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ci.exhausted = True
        ps.resources.append(ci)
        state.event_log.append(CardResourced(
            player_id=ps.player_id, instance_id=ci.instance_id,
            card_name=ci.card_def.display_name))

    me = next((c for c in ps.discard if c.instance_id == source_ci.instance_id),
              None)
    if me is not None:
        ps.discard.remove(me)
        _resource(me)
    if ps.deck:
        _resource(ps.deck.pop(0))
    return state


@card_ability("LAW", "171")
def _stockpile_event():
    """LAW_171 — Stockpile (Event, cost 6)."""
    return EventAbility(effects=[CustomEffect(fn=_stockpile)])


@card_ability("LAW", "182")
def _weazel_fighting_back():
    """LAW_182 — Weazel (Unit, Underworld, 2/3): "On Attack: Another friendly unit
    gains Raid 2 for this phase." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword("Raid", value=2,
                              target=TargetSpec(controller="friendly", kind="unit",
                                                predicates=("not_self",)),
                              duration=Duration.THIS_PHASE)],
    )


def _ben_solo_ready_and_shelter(state, source_ci, target_id, event_ctx):
    """"Ready another friendly unit.  It can't be attacked this phase." (Ben Solo
    LAW_185.)

    ONE targeted effect so both halves land on the SAME unit from one prompt (the
    Kylo SHD_141 rule).  The bar is the existing ``cannot_be_attacked`` modifier
    (On Top of Things TWI_219), read at the single attack-enumeration seam — which
    carries the Sentinel escape the card's own rules note describes ("If the unit
    chosen by Ben Solo has or gains Sentinel, it can be attacked")."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import note_unit_readied
    note_unit_readied(state, res[1])
    res[1].exhausted = False
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="cannot_be_attacked",
        value={},
        duration="this_phase",
    ))
    return state


def _ben_solo_ability(trigger):
    return TriggerAbility(
        trigger=trigger,
        effects=[CustomEffect(
            fn=_ben_solo_ready_and_shelter,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("not_self",)),
        )],
    )


@card_ability("LAW", "185")
def _ben_solo_facing_the_light():
    """LAW_185 — Ben Solo (Unit, Force/Sith, 8/8, Hidden).  The same effect under
    both printed triggers (Captain Rex SEC_48's shape); the When Defeated one needs
    no LAW_159 corpse-timing care because its effect is TARGETED, so it resolves on
    a later ``apply``."""
    return [_ben_solo_ability(WhenPlayed()), _ben_solo_ability(WhenDefeated())]


@card_ability("LAW", "186")
def _enfys_nests_helmet():
    """LAW_186 — Enfys Nest's Helmet (Upgrade, Item, cost 2): "Attach to a
    non-Vehicle unit.  Attached unit gains: 'On Attack: You may give another unit
    +3/+0 for this phase.'"

    A ``GrantedAbility``, which resolves with the HOST as source — so ``not_self``
    is "another unit" relative to the attacker, and the grant is never collected
    while this card sits anywhere but on a host (Armed to the Teeth SHD_175).
    "Another unit" names no controller, so an enemy is a legal (if odd) choice."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=3, hp=0,
                             target=TargetSpec(controller="any", kind="unit",
                                               predicates=("not_self",)),
                             duration=Duration.THIS_PHASE)],
        optional=True,
    ))


def _sharpshooter_pay_and_discard(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, an opponent discards a card from their
    hand." (Mid Rim Sharpshooter LAW_193.)  The Boba Fett LAW_214 binding; the
    discard is the standard first-card simplification (K-2SO SOR_145)."""
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.abilities.registry import DiscardFromHand
    from swu.abilities.resolver import execute_effect
    return execute_effect(state, DiscardFromHand(count=1, chooser="opponent"),
                          source_ci, None, event_ctx)


@card_ability("LAW", "193")
def _mid_rim_sharpshooter():
    """LAW_193 — Mid Rim Sharpshooter (Unit, Bounty Hunter/Underworld, 3/3,
    Saboteur)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_sharpshooter_pay_and_discard)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=1),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:18`` — Combat tricks, buffs & tempo
#
#   * LAW_202 Commence the Festivities — "Attack with a unit.  It gains Saboteur
#     for this attack.  If you control fewer resources than an opponent, it gets
#     +2/+0 for this attack."
#   * LAW_223 Rose Tico — "If you control a non-unique unit, this unit enters play
#     ready."
#   * LAW_227 Rookie Rocket-jumper — "You may pay 1 resource.  If you do, give a
#     Shield token to this unit."
#   * LAW_233 Galen Erso — "You may have an opponent take control of this unit.
#     Enemy units gain Raid 1 and Saboteur."
#   * LAW_257 Hidden Hand Supplier — "You may pay 1 resource.  If you do, give an
#     Experience token to another unit."
# ─────────────────────────────────────────────────────────────────────────────


def _commence_the_festivities(state, source_ci, target_id, event_ctx):
    """"Attack with a unit.  It gains Saboteur for this attack.  If you control
    fewer resources than an opponent, it gets +2/+0 for this attack."
    (Commence the Festivities LAW_202.)

    The bonus is decided AT RESOLUTION rather than by a spec ``condition`` — an
    ``EventAbility`` has none, and the resource comparison cannot change between
    here and the attack (the decision is the very next thing that happens).  The
    Adelphi SHD_101 convention; the atom is the JTL_164 MIRROR
    ``OPPONENT_MORE_RESOURCES_THAN_CONTROLLER``, so a level count grants nothing,
    which is exactly "fewer".  Mandatory — the printed rules note says "You must
    attack with a unit, if able"."""
    from swu.engine.actions import push_granted_attack
    behind = ConditionCheck(
        Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER).evaluate(state, source_ci)
    push_granted_attack(state, source_ci, 2 if behind else 0, 0,
                        grant_keywords=["Saboteur"])
    return state


@card_ability("LAW", "202")
def _commence_the_festivities_event():
    """LAW_202 — Commence the Festivities (Event, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_commence_the_festivities)])


@card_ability("LAW", "223")
def _rose_tico_now_its_worth_it():
    """LAW_223 — Rose Tico (Unit, Resistance, 5/5): "If you control a non-unique
    unit, this unit enters play ready."

    The Salacious Crumb LAW_210 ``EntersPlayReady`` marker over the new
    ``CONTROLLER_HAS_NON_UNIQUE_UNIT`` atom.  Rose is herself unique, so she never
    satisfies her own gate."""
    return EntersPlayReady(
        condition=ConditionCheck(Condition.CONTROLLER_HAS_NON_UNIQUE_UNIT))


def _rocket_jumper_pay_and_shield(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, give a Shield token to this unit."
    (Rookie Rocket-jumper LAW_227.)  The Boba Fett LAW_214 binding with no target
    to choose."""
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.engine.tokens import attach_token
    attach_token(state, res[0], res[1], "Shield")
    return state


@card_ability("LAW", "227")
def _rookie_rocket_jumper():
    """LAW_227 — Rookie Rocket-jumper (Unit, Fringe, 2/1)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_rocket_jumper_pay_and_shield)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=1),
    )


def _galen_erso_hand_over(state, source_ci, target_id, event_ctx):
    """"You may have an opponent take control of this unit." (Galen Erso LAW_233.)

    ``change_control`` relocates him into the opponent's arena; control is implicit
    arena occupancy and ``owner_id`` is untouched, so he goes home to his real
    owner's discard when he dies.  Handing him over is the whole point of the card:
    his aura is measured against whoever CONTROLS him, so the Raid 1 / Saboteur
    gift follows to the other side of the table."""
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    holder, ci = res
    opponent = next((p for p in state.players
                     if p.player_id != holder.player_id), None)
    if opponent is None:
        return state
    from swu.engine.actions import change_control
    change_control(state, ci, opponent.player_id)
    return state


@card_ability("LAW", "233")
def _galen_erso_destroying_his_creation():
    """LAW_233 — Galen Erso (Unit, Imperial/Official, 0/5).

    The aura uses the new ``enemy_of_source_controller`` predicate rather than
    ``controller="enemy"``: the ordinary filter compares ``owner_id``, which does
    not move when this card's own trigger hands him to an opponent — and that
    hand-over is precisely when "enemy units" must flip sides."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_galen_erso_hand_over)],
            optional=True,
        ),
        ConstantAbility(
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("enemy_of_source_controller",)),
            effects=[KeywordGrant("Raid", value=1),
                     KeywordGrant("Saboteur", value=0)],
        ),
    ]


def _hidden_hand_supplier(state, source_ci, target_id, event_ctx):
    """"You may pay 1 resource.  If you do, give an Experience token to another
    unit." (Hidden Hand Supplier LAW_257.)  The Boba Fett LAW_214 binding."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 1:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import _exhaust_resources
    _exhaust_resources(ps, 1)
    from swu.engine.tokens import attach_token
    attach_token(state, res[0], res[1], "Experience")
    return state


@card_ability("LAW", "257")
def _hidden_hand_supplier_card():
    """LAW_257 — Hidden Hand Supplier (Unit, Underworld, 1/2).  "Another unit"
    names no controller, so an enemy is a legal (if odd) choice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_hidden_hand_supplier,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("not_self",)),
        )],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=1),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:19`` — Miscellaneous abilities
#
#   * LAW_8  Director Krennic (Leader) — undeployed Action [Exhaust, defeat a
#     friendly unit]: create a Credit; When Deployed: another friendly unit deals
#     damage equal to its power to an enemy unit.
#   * LAW_9  Hera Syndulla (Leader) — "While you control 2 or more units, ignore
#     the aspect penalties on Heroism units you play" (both sides).
#   * LAW_21/22/24/25/27 — five bases printing Daimyo's Palace LAW_20's Epic
#     Action verbatim.
# ─────────────────────────────────────────────────────────────────────────────


def _krennic_pick_shooter(state, source_ci, target_id, event_ctx):
    """"Another friendly unit deals damage equal to its power to an enemy unit."
    (Director Krennic LAW_8, When Deployed — first half.)

    The Haymaker LAW_168 shared-``event_ctx`` chain: this targeted effect only
    RECORDS the chosen shooter (and its power, read now so a later board change
    cannot alter it); the second effect picks the victim.  With no other friendly
    unit nothing is stamped, so the follow-up has no candidates and fizzles
    unprompted."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.actions import compute_power
    event_ctx["prior_target_id"] = target_id
    event_ctx["krennic_damage"] = compute_power(state, res[1])
    return state


def _krennic_fire(state, source_ci, target_id, event_ctx):
    """Second half: the recorded shooter's power lands on the chosen enemy unit."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("krennic_damage") or 0)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, amount,
                              source_ci.card_def.display_name)


@card_ability("LAW", "8")
def _director_krennic_law():
    """LAW_8 — Director Krennic, "Aspirations of Power" (Leader, Imperial Official).

    Undeployed: "Action [Exhaust, defeat a friendly unit]: Create a Credit token."
    Deployed (When Deployed): "Another friendly unit deals damage equal to its
    power to an enemy unit."

    The "defeat a friendly unit" half of the cost has no cost spec — it is a
    player CHOICE, so it is modelled as a leading TARGETED ``DefeatUnit`` effect
    with the payoff behind it (Tomb of Eilram LOF_28's "Action [exhaust a friendly
    unit]"), gated by ``CONTROLLER_N_PLUS_UNITS(1)`` so the exhaust is never spent
    on an unpayable cost.  Targeted effect FIRST, the fixed ``CreateCreditToken``
    second — the Mandalorian SHD_18 single-prompt rule.

    The When Deployed clause is the Haymaker LAW_168 shared-``event_ctx`` chain:
    choose the shooter (``prior_target_id`` + its power), then the victim, narrowed
    by ``requires_prior_target`` so an empty board fizzles with no prompt.
    ``not_self`` is the printed "another" (Krennic has just arrived in the ground
    arena)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[
                DefeatUnit(TargetSpec(controller="friendly", kind="unit")),
                CreateCreditToken(),
            ],
            title="Defeat a friendly unit: create a Credit token",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=1),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[
                CustomEffect(
                    fn=_krennic_pick_shooter,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      predicates=("not_self",)),
                ),
                CustomEffect(
                    fn=_krennic_fire,
                    target=TargetSpec(controller="enemy", kind="unit",
                                      predicates=("requires_prior_target",)),
                ),
            ],
        ),
    ]


@card_ability("LAW", "9")
def _hera_syndulla_law():
    """LAW_9 — Hera Syndulla, "Never Tell Me The Odds" (Leader, Rebel Spectre).

    Both sides print the same clause: "While you control 2 or more units, ignore
    the aspect penalties on Heroism units you play."  (The deployed side also
    prints Restore 1, which the keyword layer handles on its own.)

    One ``IgnoreAspectPenaltyForPlays`` marker covers both sides for free — the
    controller-scoped waiver scan walks ``base_zone`` (the undeployed leader) AND
    both arenas (the deployed one), so a marker with no side gate is read from
    wherever she happens to be.  The new ``aspects`` field is the include-filter
    ("Heroism units") and the new ``condition`` carries the "While you control 2 or
    more units" gate, evaluated against Hera herself."""
    return IgnoreAspectPenaltyForPlays(
        card_type="unit",
        aspects=("Heroism",),
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=2),
    )


def _law_aspect_waiver_base(name: str):
    """Daimyo's Palace LAW_20's Epic Action, printed verbatim on six more LAW bases
    (LAW_21/22/24/25/27/28/30): "Epic Action: Play a card from your hand, ignoring
    1 of its Vigilance, Command, Aggression, or Cunning aspect penalties."

    Same adapter, same gate, same documented units-only narrowing."""
    return ActivatedAbility(
        costs=[],
        effects=[CustomEffect(fn=_daimyo_play)],
        title="Epic Action: play a unit from hand, ignoring 1 aspect penalty",
        epic=True,
        condition=ConditionCheck(
            Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY),
    )


@card_ability("LAW", "21")
def _coaxium_mine():
    """LAW_21 — Coaxium Mine (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Coaxium Mine")


@card_ability("LAW", "22")
def _aldhani_garrison():
    """LAW_22 — Aldhani Garrison (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Aldhani Garrison")


@card_ability("LAW", "24")
def _imperial_command_complex():
    """LAW_24 — Imperial Command Complex (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Imperial Command Complex")


@card_ability("LAW", "25")
def _contested_caverns():
    """LAW_25 — Contested Caverns (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Contested Caverns")


@card_ability("LAW", "27")
def _stygeon_spire():
    """LAW_27 — Stygeon Spire (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Stygeon Spire")


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:20`` — Miscellaneous abilities
#
#   * LAW_28/30 — the last two bases printing Daimyo's Palace LAW_20's Epic Action.
#   * LAW_36 Obi-Wan Kenobi — "While you control 7 or more units, their printed
#     power is considered to be 7 and printed HP is considered to be 7."
#   * LAW_53 Dengar — "When a unit with the highest cost among enemy units is
#     defeated: Create a Credit token.  Use this ability only once each round."
#   * LAW_63 L3-37 — "search the top 10 for any number of Droid units with
#     combined cost 5 or less and play each of them for free."
#   * LAW_66 Tear This Ship Apart — play one of an opponent's resources for free.
#   * LAW_71 The Max Rebo Band — "When the regroup phase starts: Create a Credit."
# ─────────────────────────────────────────────────────────────────────────────


@card_ability("LAW", "28")
def _canto_bight_base():
    """LAW_28 — Canto Bight (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Canto Bight")


@card_ability("LAW", "30")
def _partisan_hideout():
    """LAW_30 — Partisan Hideout (Base): Daimyo's Palace LAW_20 verbatim."""
    return _law_aspect_waiver_base("Partisan Hideout")


@card_ability("LAW", "36")
def _obi_wan_kenobi_law():
    """LAW_36 — Obi-Wan Kenobi (Unit, Force Jedi Republic, 7/7, Sentinel — keyword
    layer): "While you control 7 or more units, their printed power is considered
    to be 7 and printed HP is considered to be 7."

    The first AURA ``PrintedStatsOverride``: the marker LOF_56 built for an
    attached upgrade, now carried by a UNIT and read for every unit its controller
    owns (``aura_controller="friendly"`` — "their", which includes Obi-Wan, who is
    already 7/7).  Read at the SEED of ``compute_power``/``compute_hp``, so every
    bonus — upgrades, tokens, Experience, Grit, Raid, modifiers, constants — still
    layers on top of the 7, which is the printed reading its rules note spells out.

    The gate is a ``condition``, not a TargetSpec predicate, because this is read
    from inside the effective-stats layer and the target matcher re-enters it;
    ``CONTROLLER_N_PLUS_UNITS(7)`` is a plain arena count and cannot recurse."""
    return PrintedStatsOverride(
        power=7, hp=7, aura_controller="friendly",
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, param=7),
    )


def _dengar_credit_once(state, source_ci, target_id, event_ctx):
    """Create a Credit token and spend Dengar's once-per-round charge."""
    from swu.engine.tokens import create_credit_token
    state.game_memory.activated_abilities_used_this_round.add(
        f"{source_ci.instance_id}:trig")
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "53")
def _dengar_law():
    """LAW_53 — Dengar (Unit, Bounty Hunter Underworld, 4/3): "When a unit with the
    highest cost among enemy units is defeated: Create a Credit token.  Use this
    ability only once each round."

    A ``WhenUnitDefeated`` observer narrowed by the new
    ``highest_cost_among_enemy_units`` predicate — printed cost, ties all qualify
    (both are the card's own rules notes).  Because the trigger is collected AFTER
    the dying unit has left its arena, "≥ the highest cost still standing" is the
    exact test.

    "Only once each round" is the shared ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``
    limiter (Toro Calican SHD_239): the effect marks ``{instance_id}:trig`` and the
    condition gates collection, so the charge is spent on USE, not on offer."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(
            filter=TargetSpec(controller="enemy", kind="unit",
                              predicates=("highest_cost_among_enemy_units",)),
        ),
        effects=[CustomEffect(fn=_dengar_credit_once)],
        condition=ConditionCheck(
            Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE),
    )


def _l3_37_search(state, source_ci, target_id, event_ctx):
    """"Search the top 10 cards of your deck for any number of Droid units with
    combined cost 5 or less and play each of them for free." (L3-37 LAW_63.)

    Darth Vader SOR_87's ``push_search_and_play_multiple`` verbatim, at a wider
    window and a Droid filter — the budget is the printed combined-cost cap, the
    un-taken cards are bottomed in a seeded-random order (the card's own note), and
    each unit is played on its own so its triggers resolve before the next pick."""
    from swu.engine.actions import push_search_and_play_multiple
    push_search_and_play_multiple(
        state, source_ci, window=10, budget=5,
        eligible=lambda cd: "Droid" in (getattr(cd, "traits", ()) or ()),
    )
    return state


@card_ability("LAW", "63")
def _l3_37_law():
    """LAW_63 — L3-37 (Unit, Droid Underworld, 3/2, Hidden — keyword layer)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_l3_37_search)])


def _tear_this_ship_apart(state, source_ci, target_id, event_ctx):
    """"Look at all of an opponent's resources.  You may play 1 of those cards for
    free.  If you do, that opponent resources the top card of their deck."
    (Tear This Ship Apart LAW_66.)

    The ``play_from_hand`` decision's new ``resources_of`` source zone: the
    candidates are the opponent's resource cards, the play is free, and
    ``then_owner_resources_deck_top`` is the printed "If you do" — settled inside
    the play, so a fizzle (no eligible resource) pays them nothing.

    DOCUMENTED NARROWINGS, both standing limits of that decision: only UNIT
    resources are offered (Daimyo's Palace LAW_20 / Count Dooku TWI_5), and the
    "you may" collapses to mandatory-if-able — taking a free unit off an opponent
    is never worse than declining (The Invisible Hand JTL_89)."""
    from swu.engine.actions import push_play_from_hand
    opp = next((p for p in state.players if p.player_id != source_ci.owner_id), None)
    if opp is None:
        return state
    push_play_from_hand(state, source_ci, free=True,
                        resources_of=opp.player_id,
                        then_owner_resources_deck_top=True)
    return state


@card_ability("LAW", "66")
def _tear_this_ship_apart_law():
    """LAW_66 — Tear This Ship Apart (Event, Tactic, cost 7)."""
    return EventAbility(effects=[CustomEffect(fn=_tear_this_ship_apart)])


def _max_rebo_band_credit(state, source_ci, target_id, event_ctx):
    from swu.engine.tokens import create_credit_token
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "71")
def _the_max_rebo_band():
    """LAW_71 — The Max Rebo Band (Unit, Musician Underworld, 1/5): "When the
    regroup phase starts: Create a Credit token."  A plain
    ``PhaseStartTrigger("regroup")`` (Patient Hunter LAW_73's timing)."""
    return TriggerAbility(trigger=PhaseStartTrigger("regroup"),
                          effects=[CustomEffect(fn=_max_rebo_band_credit)])


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:21`` — Miscellaneous abilities
#
#   * LAW_92  Two-Faced Troig — "You may have an opponent take control of this
#     unit.  If you do, create 2 Credit tokens."
#   * LAW_116 Rodian Bondsman — "When Defeated: Each player creates a Credit."
#   * LAW_117 Conveyex Security Captain — "Enemy Credit tokens lose all abilities."
#   * LAW_121 Canto Bight Security — "On Defense: Create a Credit token."
#   * LAW_126 Adventurer Sniper Rifle — the host gains an Action setting a chosen
#     unit's PRINTED HP to 1 for this phase.
#   * LAW_141 Targeted For Removal — the host gains "When Defeated: An opponent
#     creates Credit tokens equal to this unit's cost."
#   * LAW_149 Rey — can't be taken control of, can't be defeated by enemy
#     card abilities.
# ─────────────────────────────────────────────────────────────────────────────


def _troig_hand_over_for_credits(state, source_ci, target_id, event_ctx):
    """"You may have an opponent take control of this unit.  If you do, create 2
    Credit tokens." (Two-Faced Troig LAW_92.)

    ONE no-target effect: the gift and its payment must be atomic (the "If you do"
    binding, Bright Hope SOR_99), and the credits go to the controller who gave the
    unit away — the ``owner_id`` never moves, so ``source_ci.owner_id`` is still the
    right seat after the hand-over."""
    from swu.engine.actions import change_control
    from swu.engine.tokens import create_credit_token
    owner_id = source_ci.owner_id
    opp = next((p for p in state.players if p.player_id != owner_id), None)
    if opp is None:
        return state
    res = state.find_instance(source_ci.instance_id)
    if res is None or res[0].player_id != owner_id:
        return state
    change_control(state, res[1], opp.player_id)
    after = state.find_instance(source_ci.instance_id)
    if after is None or after[0].player_id != opp.player_id:
        return state   # refused (a Protection) — no gift, so no payment
    for _ in range(2):
        create_credit_token(state, state.player_by_id(owner_id))
    return state


@card_ability("LAW", "92")
def _two_faced_troig():
    """LAW_92 — Two-Faced Troig (Unit, Underworld, 2/4, Sentinel — keyword layer)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_troig_hand_over_for_credits)],
                          optional=True)


@card_ability("LAW", "116")
def _rodian_bondsman():
    """LAW_116 — Rodian Bondsman (Unit, Bounty Hunter, 2/3): "When Defeated: Each
    player creates a Credit token."  ``CreateCreditToken(player="each")`` — the
    DrawCards / CreateTokenUnit ``player`` convention, whose "each" arm the Credit
    effect gains here."""
    return TriggerAbility(trigger=WhenDefeated(),
                          effects=[CreateCreditToken(player="each")])


@card_ability("LAW", "117")
def _conveyex_security_captain():
    """LAW_117 — Conveyex Security Captain (Unit, Imperial Trooper, 2/4): "Enemy
    Credit tokens lose all abilities."

    A Credit token's ONLY printed ability is its spend clause ("While paying
    resources, you may defeat this token.  If you do, pay 1 resource less"), so
    the whole card is the new ``EnemyCreditsLoseAbilities`` passive marker read
    through ``actions._usable_credits`` — consulted by both the affordability gate
    and the payment site, so an opponent's credit pile simply stops paying while
    the Captain is in play (and starts again when he leaves)."""
    return EnemyCreditsLoseAbilities()


def _canto_bight_security_credit(state, source_ci, target_id, event_ctx):
    from swu.engine.tokens import create_credit_token
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "121")
def _canto_bight_security():
    """LAW_121 — Canto Bight Security (Unit, Fringe, 3/5, Sentinel — keyword
    layer): "On Defense: Create a Credit token."

    "'On Defense' abilities trigger at the same time as 'On Attack' abilities"
    (the card's own rules note), which is exactly ``WhenAttacked`` — the trigger
    that fires when this unit is declared as a defender."""
    return TriggerAbility(trigger=WhenAttacked(),
                          effects=[CustomEffect(fn=_canto_bight_security_credit)])


def _sniper_rifle_hp_to_one(state, source_ci, target_id, event_ctx):
    """"Choose an undamaged non-leader ground unit.  Its printed HP is considered
    to be 1 for this phase." (Adventurer Sniper Rifle LAW_126.)

    A ``printed_stats`` MODIFIER — the duration-carrying flavour of
    ``PrintedStatsOverride``, read at the same ``compute_hp`` SEED, so upgrades,
    tokens and buffs still layer on top of the 1 (the printed reading its rules
    note spells out) and the whole thing lapses at the phase rollover."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="printed_stats",
        value={"hp": 1},
        duration=Duration.THIS_PHASE.value,
    ))
    return state


@card_ability("LAW", "126")
def _adventurer_sniper_rifle():
    """LAW_126 — Adventurer Sniper Rifle (Upgrade, Item Weapon, cost 2): "Attach to
    a non-Vehicle unit.  Attached unit gains: 'Action [Exhaust]: Choose an
    undamaged non-leader ground unit.  Its printed HP is considered to be 1 for
    this phase.'"

    A ``GrantedAbility`` wrapping an ``ActivatedAbility`` (Heroic Resolve SHD_155):
    the arena scan in ``legal_actions`` walks each unit's attached upgrades and
    offers the Action from the HOST, whose exhaust pays for it.  The attach
    restriction is parsed off the printed "Attach to …" line by
    ``_upgrade_target_spec``, so it needs no registration."""
    return GrantedAbility(ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(
            fn=_sniper_rifle_hp_to_one,
            target=TargetSpec(controller="any", kind="unit", arena="ground",
                              predicates=("undamaged", "non_leader")),
        )],
        title="Set a unit's printed HP to 1 for this phase",
    ))


def _targeted_for_removal_bounty(state, source_ci, target_id, event_ctx):
    """"When Defeated: An opponent creates Credit tokens equal to this unit's
    cost." (Targeted For Removal LAW_141, granted to its host.)

    Resolves FROM the host (the GrantedAbility convention), so ``source_ci`` is the
    dying unit: its PRINTED cost is the count (the card's own rules note) and "an
    opponent" is the one opponent of its controller."""
    from swu.engine.tokens import create_credit_token
    count = int(getattr(source_ci.card_def, "cost", None) or 0)
    if count <= 0:
        return state
    opp = next((p for p in state.players
                if p.player_id != source_ci.owner_id), None)
    if opp is None:
        return state
    for _ in range(count):
        create_credit_token(state, opp)
    return state


@card_ability("LAW", "141")
def _targeted_for_removal():
    """LAW_141 — Targeted For Removal (Upgrade, Condition, cost 3)."""
    return GrantedAbility(TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_targeted_for_removal_bounty)],
    ))


@card_ability("LAW", "149")
def _rey_law():
    """LAW_149 — Rey (Unit, Force Jedi Resistance, 9/9): "Opponents can't take
    control of this unit.  This unit can't be defeated by enemy card abilities."

    One self-targeted ``ConstantAbility`` carrying a ``Protection`` with two arms:
    the long-standing ``from_defeat`` (an enemy ability's ``DefeatUnit`` skips her)
    and the new ``from_control_change`` (``actions.change_control`` refuses to hand
    her to anyone but her owner).  Her printed rules note — "can't be defeated
    directly by card abilities that 'defeat a unit', but can still be defeated as a
    result of card abilities or game effects, such as abilities that give a unit
    -X/-X" — is exactly what ``from_defeat`` already means: the HP-defeat gate is a
    separate arm (``from_hp_defeat``) she does not carry."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_defeat=True, from_control_change=True)],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:22`` — Miscellaneous abilities
#
#   * LAW_155 Getaway Freighter — "On Attack: If you control a ground unit, create
#     a Credit token."
#   * LAW_156 Hunter For Hire — "Action [defeat a friendly Credit token]: Take
#     control of this unit.  Any player may use this ability."
#   * LAW_161 Partisan U-Wing — "When Played: If a friendly unit was defeated this
#     phase, create a Credit token."
#   * LAW_169 Payroll Heist — "For this phase, each friendly unit gains: 'On
#     Attack: Create a Credit token.'"
#   * LAW_197 Shifty Suspects — "On Attack: Bases can't be healed for this phase."
#   * LAW_204 Every Day, More Lies — "Each player discards a card from their hand."
#   * LAW_219 Anakin's Podracer — conditional First Strike while attacking.
# ─────────────────────────────────────────────────────────────────────────────


def _law22_credit(state, source_ci, target_id, event_ctx):
    """Create one Credit token for the source's controller."""
    from swu.engine.tokens import create_credit_token
    create_credit_token(state, state.player_by_id(source_ci.owner_id))
    return state


@card_ability("LAW", "155")
def _getaway_freighter():
    """LAW_155 — Getaway Freighter (Unit, Transport Vehicle, 1/4): "On Attack: If
    you control a ground unit, create a Credit token."

    The clause gates trigger COLLECTION (the new ``CONTROLLER_HAS_UNIT_IN_ARENA``
    atom at "ground"), so an all-space board never offers a no-op — the Freighter
    is itself a space unit, so it cannot satisfy its own clause."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_law22_credit)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_IN_ARENA,
                                 param="ground"),
    )


def _hunter_for_hire_take_control(state, source_ci, target_id, event_ctx):
    """"Take control of this unit." (Hunter For Hire LAW_156.)

    The ability is ``any_player``, so the beneficiary is whoever USED it — read off
    ``event_ctx["ability_user_id"]``, which ``UseAbility`` threads for exactly this
    (Mercenary Gunship SHD_256)."""
    from swu.engine.actions import change_control
    user_id = event_ctx.get("ability_user_id") or source_ci.owner_id
    res = state.find_instance(source_ci.instance_id)
    if res is None:
        return state
    change_control(state, res[1], user_id)
    return state


@card_ability("LAW", "156")
def _hunter_for_hire():
    """LAW_156 — Hunter For Hire (Unit, Bounty Hunter Underworld, 4/4): "Action
    [defeat a friendly Credit token]: Take control of this unit.  Any player may
    use this ability."

    ``any_player=True`` (Mercenary Gunship SHD_256) plus the new
    ``DefeatCreditCost`` cost spec: "a friendly Credit token" is one from the
    USER's own pile, and credits are fungible so no choice is made.  The ability is
    offered only while that user actually holds a credit, at every one of the six
    activated-ability affordability sites."""
    return ActivatedAbility(
        costs=[DefeatCreditCost()],
        effects=[CustomEffect(fn=_hunter_for_hire_take_control)],
        title="Defeat a Credit token: take control of this unit",
        any_player=True,
    )


@card_ability("LAW", "161")
def _partisan_u_wing():
    """LAW_161 — Partisan U-Wing (Unit, Rebel Transport Vehicle, 3/5): "When
    Played: If a friendly unit was defeated this phase, create a Credit token."
    ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` gates collection (Wat Tambor TWI_6)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_law22_credit)],
        condition=ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE),
    )


def _payroll_heist_arm_aura(state, source_ci, target_id, event_ctx):
    """Arm the phase-scoped aura (Implicate SEC_231 / Pyrrhic Assault TWI_103): the
    spent event keeps granting from its owner's discard until the phase rolls
    over, which is the whole of "for this phase"."""
    gm = state.game_memory
    if source_ci.instance_id not in gm.phase_aura_sources:
        gm.phase_aura_sources.append(source_ci.instance_id)
    return state


@card_ability("LAW", "169")
def _payroll_heist():
    """LAW_169 — Payroll Heist (Event, Plan, cost 4): "For this phase, each
    friendly unit gains: 'On Attack: Create a Credit token.'"

    Spec 0 arms the phase aura; spec 1 is the ``AuraGrantedAbility`` itself, whose
    inner ``OnAttack`` is collected by the main ``_collect_triggers`` aura scan
    (the seam the SEC_231 framework session opened for non-``WhenDefeated`` inner
    triggers).  Each grant resolves FROM the attacking unit, so the Credit goes to
    that unit's controller — "friendly" is measured against the event's own
    ``owner_id``, which ``find_instance`` still reports from the discard.

    Board-wide by design: the grant covers every friendly unit, including ones
    played later this phase, exactly as printed."""
    return [
        EventAbility(effects=[CustomEffect(fn=_payroll_heist_arm_aura)]),
        AuraGrantedAbility(
            target=TargetSpec(controller="friendly", kind="unit"),
            ability=TriggerAbility(
                trigger=OnAttack(),
                effects=[CustomEffect(fn=_law22_credit)],
            ),
        ),
    ]


def _shifty_suspects_lock(state, source_ci, target_id, event_ctx):
    """"Bases can't be healed for this phase." — Wolffe SOR_160's phase-scoped
    global lock, read at every base-heal chokepoint and cleared at the rollover."""
    state.game_memory.bases_cannot_heal_this_phase = True
    return state


@card_ability("LAW", "197")
def _shifty_suspects():
    """LAW_197 — Shifty Suspects (Unit, Bounty Hunter Underworld, 4/5)."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_shifty_suspects_lock)])


@card_ability("LAW", "204")
def _every_day_more_lies():
    """LAW_204 — Every Day, More Lies (Event, Innate, cost 1): "Each player
    discards a card from their hand."

    Two ``DiscardFromHand`` effects, one per chooser — the first-card
    simplification each already uses (K-2SO SOR_145).  A player with an empty hand
    simply discards nothing."""
    return EventAbility(effects=[
        DiscardFromHand(count=1, chooser="controller"),
        DiscardFromHand(count=1, chooser="opponent"),
    ])


@card_ability("LAW", "219")
def _anakins_podracer():
    """LAW_219 — Anakin's Podracer (Unit, Speeder Vehicle, 3/2, Ambush — keyword
    layer): "While attacking, if no other units have attacked this phase, this
    unit deals combat damage before the defending unit."

    "Deals combat damage before the defending unit" IS First Strike, and "while
    attacking" is what makes this a ``ConditionalFirstStrike`` marker (read only at
    the attacker's combat step) rather than a conditional ``KeywordGrant`` — the
    keyword layer has no combat context, so a grant would also fire while this unit
    is DEFENDING.  The defender filter is "any unit"; the new ``condition`` carries
    the printed clause over ``NO_OTHER_UNIT_ATTACKED_THIS_PHASE``, which both
    combat pipelines stamp at the DECLARE step — so by the damage step the ledger
    holds exactly this attack, and "≤1" is "no OTHER unit attacked"."""
    return ConditionalFirstStrike(
        defender_spec=TargetSpec(controller="any", kind="unit"),
        condition=ConditionCheck(Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:23`` — Miscellaneous abilities
#
#   * LAW_221 Lieutenant Gorn — "On Attack: Take control of an enemy Credit token."
#   * LAW_228 Canyon Frontrunner — "On Attack: If no other units have attacked this
#     phase, you may give a unit −2/−0 for this phase."
#   * LAW_232 Champion's KT9 Podracer / LAW_248 Windfall — plain Credit creation.
#   * LAW_235 Lady Proxima — "Action [Exhaust]: Create a Credit token."
#   * LAW_243 Transmission Jamming — "Name a card.  Cards with that name can't be
#     played this phase."
#   * LAW_256 Fire Across the Galaxy — "Use any number of 'When Played' abilities
#     on friendly Spectre units."
# ─────────────────────────────────────────────────────────────────────────────


def _gorn_steal_credit(state, source_ci, target_id, event_ctx):
    """"Take control of an enemy Credit token." (Lieutenant Gorn LAW_221.)

    Credits live in their own per-player pile and are fungible, so which one moves
    is not a choice (the K-2SO SOR_145 auto-select convention): one token is
    relocated from the opponent's pile to the controller's, ``owner_id`` untouched
    exactly as at every other control seam.  With an empty enemy pile nothing
    happens."""
    owner_id = source_ci.owner_id
    opp = next((p for p in state.players if p.player_id != owner_id), None)
    if opp is None or not opp.credits:
        return state
    ps = state.player_by_id(owner_id)
    credit = opp.credits.pop()
    ps.credits.append(credit)
    from swu.engine.events import ControlChanged
    state.event_log.append(ControlChanged(
        instance_id=credit.instance_id,
        card_name="Credit",
        owner_id=credit.owner_id,
        from_player_id=opp.player_id,
        to_player_id=owner_id,
    ))
    return state


@card_ability("LAW", "221")
def _lieutenant_gorn():
    """LAW_221 — Lieutenant Gorn (Unit, Imperial Rebel, 4/4)."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_gorn_steal_credit)])


@card_ability("LAW", "228")
def _canyon_frontrunner():
    """LAW_228 — Canyon Frontrunner (Unit, Speeder Vehicle, 3/2): "On Attack: If no
    other units have attacked this phase (including enemy units), you may give a
    unit −2/−0 for this phase."

    ``NO_OTHER_UNIT_ATTACKED_THIS_PHASE`` (Anakin Skywalker LAW_88) gates
    collection — both combat pipelines stamp the attacker at the DECLARE step, so
    by the On Attack window the ledger holds exactly this attack.  "A unit" names
    no controller, as printed; the controller naturally aims at the defender."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(-2, 0,
                             target=TargetSpec(controller="any", kind="unit"),
                             duration=Duration.THIS_PHASE)],
        optional=True,
        condition=ConditionCheck(Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE),
    )


@card_ability("LAW", "232")
def _champions_kt9_podracer():
    """LAW_232 — Champion's KT9 Podracer (Unit, Speeder Vehicle, 2/3): "When
    Played: Create a Credit token." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[CreateCreditToken()])


@card_ability("LAW", "235")
def _lady_proxima():
    """LAW_235 — Lady Proxima (Unit, Underworld, 1/5): "Action [Exhaust]: Create a
    Credit token." """
    return ActivatedAbility(costs=[ExhaustSelf()],
                            effects=[CreateCreditToken()],
                            title="Create a Credit token")


def _transmission_jamming(state, source_ci, target_id, event_ctx):
    """"Name a card.  Cards with that name can't be played this phase."
    (Transmission Jamming LAW_243.)

    ``push_name_a_card`` with the new ``forbid_play_this_phase`` payoff arm, which
    records the name in ``game_memory.forbidden_card_names_this_phase`` — read at
    the same play-legality seam as Regional Governor SOR_62's standing marker, but
    binding EVERY player (as printed) and lifting at the phase rollover.

    The nameable set stays the opponent's PUBLIC card names (the standing
    ``name_a_card`` convention — offering their hidden deck would leak
    information); with no name to pick the event fizzles."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci, then_payoff="forbid_play_this_phase")
    return state


@card_ability("LAW", "243")
def _transmission_jamming_law():
    """LAW_243 — Transmission Jamming (Event, Tactic, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_transmission_jamming)])


@card_ability("LAW", "248")
def _windfall():
    """LAW_248 — Windfall (Event, Supply, cost 5): "Create 3 Credit tokens." """
    return EventAbility(effects=[CreateCreditToken(count=3)])


def _fire_across_the_galaxy(state, source_ci, target_id, event_ctx):
    """"Use any number of 'When Played' abilities on friendly Spectre units."
    (Fire Across the Galaxy LAW_256.)

    The ``select_token`` select-up-to-N loop in its "any number" form (``max_targets``
    = the eligible count, ``FinishSelectToken`` always legal — the Kazuda Xiono
    JTL_18 idiom) over friendly Spectre units narrowed by the new
    ``has_when_played_ability`` predicate, with the new ``then_use_when_played``
    payoff: after the pop, each chosen unit's registered When Played abilities are
    pushed as fresh ``resolve_effects`` decisions (the Chimaera JTL_39 /
    Shadow Caster JTL_169 shape), so no trigger or decision machinery moves.

    DOCUMENTED SIMPLIFICATION: the "any number" is counted in UNITS, not in
    individual abilities — a chosen unit contributes all of its When Played
    abilities.  Only Shadow Caster's precedent ("use ALL of its 'When Defeated'
    abilities") exists for the multi-ability case, and no Spectre unit prints more
    than one."""
    from swu.engine.actions import push_select_token, _select_token_targets
    ctx = {"source_id": source_ci.instance_id,
           "controller_id": source_ci.owner_id,
           "controller": "friendly", "kind": "unit",
           "traits": ["Spectre"], "predicates": ["has_when_played_ability"],
           "chosen": []}
    eligible = _select_token_targets(state, ctx)
    if not eligible:
        return state
    push_select_token(
        state, source_ci, token_type=None, max_targets=len(eligible),
        controller="friendly", kind="unit", traits=["Spectre"],
        predicates=["has_when_played_ability"],
        then_use_when_played=True,
    )
    return state


@card_ability("LAW", "256")
def _fire_across_the_galaxy_law():
    """LAW_256 — Fire Across the Galaxy (Event, Spectre, cost 6)."""
    return EventAbility(effects=[CustomEffect(fn=_fire_across_the_galaxy)])


# ─────────────────────────────────────────────────────────────────────────────
# Group ``law-set:24`` — Miscellaneous abilities (the last LAW group)
#
#   * LAW_258 Criminal Contact — "On Attack: You may pay 2 resources.  If you do,
#     create a Credit token."
#   * LAW_262 Bank Job Fugitives — "When Played: Create a Credit token."
#   * LAW_264 From a Certain Point of View — "Play a card from your hand, ignoring
#     its aspect penalties."
# ─────────────────────────────────────────────────────────────────────────────


def _criminal_contact_pay_for_credit(state, source_ci, target_id, event_ctx):
    """"You may pay 2 resources.  If you do, create a Credit token." (Criminal
    Contact LAW_258.)

    The Boba Fett LAW_214 pay-then-payoff binding: payment and payoff live in ONE
    effect so "if you do" can never be split, and the optional trigger is gated by
    ``CONTROLLER_N_PLUS_READY_RESOURCES(2)`` so it is never offered unaffordable."""
    from swu.engine.actions import _exhaust_resources
    from swu.engine.tokens import create_credit_token
    ps = state.player_by_id(source_ci.owner_id)
    if ps.available_resources < 2:
        return state
    _exhaust_resources(ps, 2)
    create_credit_token(state, ps)
    return state


@card_ability("LAW", "258")
def _criminal_contact():
    """LAW_258 — Criminal Contact (Unit, Underworld, 1/4)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_criminal_contact_pay_for_credit)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES,
                                 param=2),
    )


@card_ability("LAW", "262")
def _bank_job_fugitives():
    """LAW_262 — Bank Job Fugitives (Unit, Underworld, 4/6): "When Played: Create a
    Credit token." """
    return TriggerAbility(trigger=WhenPlayed(), effects=[CreateCreditToken()])


@card_ability("LAW", "264")
def _from_a_certain_point_of_view():
    """LAW_264 — From a Certain Point of View (Event, Learned, cost 1): "Play a
    card from your hand, ignoring its aspect penalties."

    Agent Kallus LAW_3's adapter verbatim — the same printed clause, the same
    ``push_play_from_hand(ignore_aspect_penalty=True)``, and the same two
    DOCUMENTED NARROWINGS: the decision plays UNITS only (Daimyo's Palace LAW_20 /
    Count Dooku TWI_5), and ``ignore_aspect_penalty`` waives one V/C/A/Cunning pip
    rather than the whole penalty.  The card's own rules note — "Abilities that let
    you play a card require you to pay that card's cost unless specified
    otherwise" — is the decision's default (``free=False``)."""
    return EventAbility(
        effects=[CustomEffect(fn=_kallus_play_ignoring_aspects)])
