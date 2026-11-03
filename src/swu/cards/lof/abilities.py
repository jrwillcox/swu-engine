"""LOF (Legends of the Force) card ability registrations.

The first LOF deck (qui-gon-jinn).  Cards with no text or only keywords are
handled by the keyword engine and are not registered here.  This module is
imported for its side effects.

Group ``qui-gon-jinn:01`` — Direct damage & removal:
  * LOF_198 Stinger Mantis — When Played: optional 2 damage to an exhausted unit.

Group ``qui-gon-jinn:02`` — Card advantage & disruption:
  * LOF_104 Luminous Beings — recur up to 3 Force units from discard, buff that
    many units +4/+4 this phase (the new ``recur_and_buff`` decision kind).
  * LOF_194 J-Type Nubian Starship — When Played: Draw a card; When Defeated:
    Discard a card from your hand.
(TWI_193 R2-D2 is in this deck but belongs to the TWI set — it is registered in
``src/swu/cards/twi/abilities.py``.)

Group ``qui-gon-jinn:03`` — Combat tricks, buffs & tempo:
  * LOF_96 Obi-Wan Kenobi — When you play a Force unit (incl. this one): gains
    Sentinel for this phase (a WhenYouPlayCard self-grant; the printed Sentinel is
    stripped by the keyword sanitiser's triggered-self-grant rule).
  * LOF_99 Paladin Training Corvette — When Played: give Experience to up to 3
    Force units (push_select_token).
  * LOF_111 Maz Kanata — When Played: may attack with a Force unit, +2/+0
    (push_granted_attack).
  * LOF_201 Qui-Gon Jinn's Lightsaber — When Played: if attached unit is Qui-Gon
    Jinn, exhaust any number of units with combined cost ≤ 6 (new
    ``exhaust_combined_cost`` decision kind).
  * LOF_242 Refugee of The Path — When Played: may give a Shield to a unit with
    Sentinel (the new ``has_sentinel`` predicate).
(SHD_96 Maz Kanata and JTL_201 Ahsoka Tano are in this deck but belong to the SHD
and JTL sets — registered in their own set modules.)

Group ``qui-gon-jinn:04`` — Combat tricks, buffs & tempo:
  * LOF_255 Curious Flock — When Played: pay up to 6 resources, give that many
    Experience tokens to this unit (the new ``pay_resources_for_tokens`` decision
    kind).

Group ``qui-gon-jinn:05`` — Miscellaneous abilities:
  * LOF_100 Kelleran Beq — When Played: search the top 7 of your deck for a unit
    and play it for 3 less (the new ``disposition="play"`` extension of the
    deck_search seam, via ``push_search_and_play``).
  * LOF_197 Qui-Gon Jinn's Aethersprite — On Attack: "the next time you use a When
    Played ability this phase, you may use that ability again" — the
    duplicate-the-next-WhenPlayed meta-mechanic (a dedicated framework session).
    Arms a phase-scoped per-player charge (actions.arm_when_played_redo); the
    resolver's _schedule_when_played_redo chokepoint consumes it on the next *used*
    WhenPlayed ability and offers an optional re-use of that same ability as a
    normal trigger_option (no new decision kind).

Group ``qui-gon-jinn:06`` — New primitive: force-token (the keystone).  The Force
token is a single per-player boolean (``PlayerState.has_force_token``): "create
your Force token" sets it (CreateForceToken effect), "use the Force (lose your
Force token)" clears it (the UseForce cost / the ``use_force`` decision), and
"While the Force is with you" reads it (CONTROLLER_HAS_FORCE_TOKEN condition).
  * LOF_193 Youngling Padawan — When Played: create your Force token.
  * LOF_23 Jedi Temple (Base) — When a friendly Force unit attacks: create your
    Force token (the new WhenUnitAttacks observer trigger; Bases are now scanned
    for triggers).
  * LOF_196 Jedi Sentinel — While the Force is with you, gains Sentinel (a
    conditional self-grant ConstantAbility; the keyword sanitiser strips any
    printed Sentinel).
  * LOF_249 Luke Skywalker — When you play another unique unit: you may use the
    Force; if you do, give it an Experience + Shield token (an optional
    WhenYouPlayCard(unique=True) trigger gated by CONTROLLER_HAS_FORCE_TOKEN; the
    "use the Force" choice = the optional Accept/Decline).
  * LOF_227 The Will of the Force (Event) — Return a non-leader unit; you may use
    the Force, if you do that player discards a random card (the new ``use_force``
    decision, payoff "discard_random").
  * LOF_218 Impossible Escape (Event) — You may exhaust a friendly unit OR use the
    Force; if you do either, exhaust an enemy unit and draw a card (the ``use_force``
    decision, payoff "exhaust_enemy_draw", with the exhaust-friendly alt cost).
  * LOF_16 Qui-Gon Jinn (Leader) — undeployed Action [Exhaust, use the Force]:
    return a friendly non-leader unit, play a cheaper non-Villainy unit free;
    deployed When Attack Ends: the same, optional, no Force cost.  The bounce-then-
    play-cheaper effect reuses push_play_from_hand (cost_max = returned cost − 1,
    free, exclude_aspect="Villainy").
"""
from __future__ import annotations

from swu.abilities.registry import (
    card_ability,
    TriggerAbility,
    ConstantAbility,
    ActivatedAbility,
    EventAbility,
    WhenPlayed,
    WhenDefeated,
    WhenUnitDefeated,
    WhenYouPlayCard,
    WhenOpponentPlaysCard,
    WhenDeployed,
    WhenUnitAttacks,
    WhenAttackEnds,
    WhenAttacked,
    WhenYouDraw,
    WhenYouUseForce,
    OnAttack,
    OnAttackDefeatsUnit,
    WhenDealsCombatDamageToBase,
    WhenDamageDealtToYourBase,
    WhenFriendlyUnitAttacksAndDefeatsUnit,
    RevokeTrait,
    PhaseStartTrigger,
    PrintedStatsOverride,
    TraitGrant,
    CostReduction,
    DealDamage,
    DealDamageEqualTo,
    DefeatUnit,
    ExhaustCard,
    Heal,
    DrawCards,
    DiscardFromHand,
    GiveToken,
    GrantKeyword,
    KeywordGrant,
    ModifyStats,
    ReadyCard,
    Protection,
    StatBonus,
    AttackRestriction,
    DoubleKeywordValue,
    RevokeKeyword,
    ReadyRestriction,
    StandingPlayDiscount,
    PreventDamage,
    GrantedAbility,
    CreateForceToken,
    NextPlayDiscount,
    ConditionalEffect,
    CustomEffect,
    ExhaustSelf,
    PayResources,
    UseForce,
    TargetSpec,
    SELF,
    DEFENDER,
    EACH_FRIENDLY,
    EACH_ENEMY,
    EACH_IN_PLAY,
    Duration,
    ConditionCheck,
    Condition,
)


@card_ability("LOF", "198")
def _stinger_mantis():
    """When Played: You may deal 2 damage to an exhausted unit.

    An optional WhenPlayed trigger (the "you may"); the 2 damage targets any
    exhausted unit, friendly or enemy (``controller="any"`` — the controller
    points it at an enemy).  With no exhausted unit on the board the optional
    trigger auto-declines (no prompt).
    """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", predicates=("exhausted",),
        ))],
        optional=True,
    )


# ── qui-gon-jinn:02 — Card advantage & disruption ─────────────────────────────

@card_ability("LOF", "104")
def _luminous_beings():
    """Put up to 3 Force units from your discard pile on the bottom of your deck in
    a random order.  Give that many units +4/+4 for this phase.

    A thin EventAbility adapter onto the new ``recur_and_buff`` decision kind
    (``actions.push_recur_and_buff``, the Palpatine SOR_135 push-helper pattern):
    the controller recurs up to 3 of their discarded Force units (each bottomed in
    a seeded-random order), then buffs that many in-play units +4/+4 this phase.
    With no Force unit in the discard pile the whole effect is a clean no-op (put
    0, buff 0).  The buff target list mirrors the literal "units" (``controller=
    "any"``) — the controller simply buffs their own.
    """
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_recur_and_buff
        push_recur_and_buff(
            state, source_ci,
            max_select=3, trait="Force", power=4, hp=4,
        )
        return state

    return EventAbility(effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "194")
def _j_type_nubian_starship():
    """When Played: Draw a card.  When Defeated: Discard a card from your hand.

    Two plain triggers.  DEVIATION (documented): the When Defeated discard uses
    ``DiscardFromHand(chooser="controller")``, which discards the FIRST card in
    hand rather than letting the controller choose which to ditch (the established
    first-card discard simplification — K-2SO SOR_145 / Garindan SEC_186) — the
    only loss is *which* card; the downside itself is faithfully forced.
    """
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[DiscardFromHand(count=1, chooser="controller")],
        ),
    ]


# ── qui-gon-jinn:03 — Combat tricks, buffs & tempo ────────────────────────────

@card_ability("LOF", "96")
def _obi_wan_kenobi():
    """LOF_96 — Obi-Wan Kenobi: "When you play a Force unit (including this one):
    This unit gains Sentinel for this phase."

    A ``WhenYouPlayCard(trait="Force", card_type="unit", exclude_self=False)``
    trigger granting Sentinel to itself for the phase.  ``exclude_self=False``
    covers "(including this one)": when Obi-Wan himself is played, ``PlayCard``
    fires the ``CardPlayed`` event *after* he is already in the arena (the Fighters
    for Freedom SOR_143 firing site), so ``_collect_triggers`` sees him as a source
    and the grant lands.  The grant is a self-targeted ``GrantKeyword`` Modifier
    (read by ``has_keyword``).  Obi-Wan's printed Sentinel keyword is a data
    mis-tag — the card only *gains* Sentinel per-phase — so the keyword sanitiser's
    triggered-self-grant rule strips the printed copy and this ability owns it."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Force", card_type="unit", exclude_self=False),
        effects=[GrantKeyword(
            "Sentinel", value=0,
            target=TargetSpec(fixed=SELF),
            duration=Duration.THIS_PHASE,
        )],
    )


@card_ability("LOF", "99")
def _paladin_training_corvette():
    """LOF_99 — Paladin Training Corvette: "When Played: You may give an Experience
    token to each of up to 3 Force units."

    A thin ``WhenPlayed`` CustomEffect adapter onto ``push_select_token`` (the
    Medal Ceremony SOR_245 / General Tagge SHD_81 select-up-to-N pattern):
    ``token_type="Experience", max_targets=3, traits=["Force"]``.  ``controller=
    "any"`` mirrors the printed text omitting "friendly", but Experience benefits
    the recipient so the controller never picks an enemy.  With no Force unit in
    play the decision is not pushed (a clean no-op — the "you may")."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_select_token
        push_select_token(
            state, source_ci,
            token_type="Experience", max_targets=3, traits=["Force"],
        )
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "111")
def _maz_kanata_lof_111():
    """LOF_111 — Maz Kanata (3/4): "When Played: You may attack with a Force unit.
    It gets +2/+0 for this attack."

    A thin ``WhenPlayed`` CustomEffect adapter onto ``push_granted_attack`` (the
    Snowtrooper Lieutenant SHD_236 / Republic Tactical Officer TWI_91 pattern):
    ``power_bonus=2, optional=True, attacker_trait="Force"``.  The controller may
    attack with any ready Force unit, which gets +2/+0 for that attack; with no
    eligible Force attacker the optional grant is declined (DeclineGrantedAttack).
    Maz herself is Underworld, not Force, so she is never the attacker."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_granted_attack
        push_granted_attack(
            state, source_ci,
            power_bonus=2, optional=True, attacker_trait="Force",
        )
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "201")
def _qui_gon_jinns_lightsaber():
    """LOF_201 — Qui-Gon Jinn's Lightsaber (Upgrade, attach to a friendly
    non-Vehicle unit): "When Played: If attached unit is Qui-Gon Jinn, you may
    exhaust any number of units with combined cost 6 or less."

    The "If attached unit is Qui-Gon Jinn" gate is the ATTACHED_HOST_NAMED
    condition (the whole WhenPlayed trigger is collected only when the host is
    named Qui-Gon Jinn).  The exhaust itself is a thin CustomEffect adapter onto
    the new ``exhaust_combined_cost`` decision kind (``push_exhaust_combined_cost``,
    budget=6): the controller exhausts any number of ready units whose combined
    PRINTED cost is ≤ 6 (no friendly/enemy restriction — points it at enemy
    units), or takes 0 (the "you may", via FinishExhaustCombined).  The non-Vehicle
    attach restriction is the engine's upgrade-target parser."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_exhaust_combined_cost
        push_exhaust_combined_cost(state, source_ci, budget=6)
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_fn)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Qui-Gon Jinn"),
    )


@card_ability("LOF", "202")
def _mind_trick():
    """LOF_202 — Mind Trick (Event): "Exhaust any number of units with a combined
    power of 4 or less.  If you control a Force unit, those units lose all abilities
    and can't gain abilities for this phase."

    A thin ``EventAbility`` CustomEffect adapter onto the existing
    ``exhaust_combined_cost`` decision kind (Qui-Gon Jinn's Lightsaber LOF_201), with
    two additive fields: ``budget_source="power"`` makes the combined budget count
    effective ``compute_power`` (not printed cost — "combined power of 4 or less"),
    and ``then_suppress_if_trait="Force"`` invokes the new ability-suppression
    read-layer — on resolve, iff the controller controls a Force unit, each
    still-in-play chosen unit's ``abilities_suppressed`` flag is set (lifted at the
    round rollover).  Because the suppression is read as a skip/early-return at every
    ability-read site, "can't gain abilities" falls out for free.  ``controller="any"``
    (the default): the controller points the exhausts at enemy units; "any number"
    includes 0 (FinishExhaustCombined always offered)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_exhaust_combined_cost
        push_exhaust_combined_cost(
            state, source_ci, budget=4, budget_source="power",
            then_suppress_if_trait="Force")
        return state

    return EventAbility(effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "255")
def _curious_flock():
    """LOF_255 — Curious Flock (1/1 Creature): "When Played: Pay up to 6 resources.
    For each resource paid this way, give an Experience token to this unit."

    A thin ``WhenPlayed`` CustomEffect adapter onto the new
    ``pay_resources_for_tokens`` decision kind (``push_pay_resources_for_tokens``,
    ``max_resources=6``, the Palpatine SOR_135 push-helper pattern): the controller
    pays any number of ready resources up to 6 (resources are fungible — no target
    choice), each payment granting one Experience token to Curious Flock inline.  The
    "up to" means paying 0 is legal (a clean no-op); with no ready resource the
    decision is not pushed."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_pay_resources_for_tokens
        push_pay_resources_for_tokens(state, source_ci, max_resources=6)
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


# ── qui-gon-jinn:05 — Miscellaneous abilities ─────────────────────────────────

@card_ability("LOF", "100")
def _kelleran_beq():
    """LOF_100 — Kelleran Beq (7/7): "When Played: Search the top 7 cards of your
    deck for a unit, reveal it, and play it.  It costs 3 resources less.  (Put the
    other cards on the bottom of your deck in a random order.)"

    A thin ``WhenPlayed`` CustomEffect adapter onto ``push_search_and_play`` (the
    ``disposition="play"`` extension of the deck_search seam): the controller
    searches the top 7, and plays one affordable unit (effective cost − 3, credits
    cover any shortfall) — firing that unit's own keyword / When Played abilities —
    while the un-taken searched cards are bottomed in a seeded-random order.  The
    play is mandatory if able (no "may"); with no affordable unit in the window
    the search resolves with nothing played.
    """
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_search_and_play
        push_search_and_play(state, source_ci, window=7, cost_reduction=3)
        return state

    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "197")
def _qui_gon_jinns_aethersprite():
    """LOF_197 — Qui-Gon Jinn's Aethersprite (3/6 Vehicle): "On Attack: The next
    time you use a 'When Played' ability this phase, you may use that ability
    again."

    The duplicate-the-next-WhenPlayed meta-mechanic (the dedicated-framework-session
    card).  A plain ``OnAttack`` whose one ``CustomEffect`` arms a phase-scoped
    "redo" charge for the controller (``actions.arm_when_played_redo`` → a counter
    on ``game_memory.when_played_redo_charges``).  The next qualifying WhenPlayed
    ability that controller *uses* this phase consumes one charge and the engine
    offers an optional re-use of that same ability with fresh target choices (the
    resolver's ``_schedule_when_played_redo`` chokepoint, surfaced as a normal
    ``trigger_option`` Accept/Decline — no new decision kind).  "Use" means the
    ability actually resolves: a mandatory WhenPlayed or an *accepted* optional one
    arms the redo; a *declined* optional WhenPlayed does not (no use, charge kept).
    The re-use itself never arms a further redo (one-shot per charge)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import arm_when_played_redo
        arm_when_played_redo(state, source_ci)
        return state

    return TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_fn)])


@card_ability("LOF", "242")
def _refugee_of_the_path():
    """LOF_242 — Refugee of The Path (Sentinel): "When Played: You may give a
    Shield token to a unit with Sentinel."

    An optional ``WhenPlayed`` ``GiveToken("Shield", …)`` targeting a unit with the
    Sentinel keyword (the new ``has_sentinel`` predicate, read via the keyword
    query layer so a granted Sentinel counts).  ``controller="any"`` mirrors the
    printed text omitting "friendly", but a Shield benefits the recipient so the
    controller never picks an enemy.  Refugee itself is a Sentinel unit, so it is a
    legal recipient; with no Sentinel unit in play the optional trigger
    auto-declines (no prompt)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="any", kind="unit", predicates=("has_sentinel",)))],
        optional=True,
    )


# ── qui-gon-jinn:06 — New primitive: force-token (the keystone) ────────────────

@card_ability("LOF", "193")
def _youngling_padawan():
    """LOF_193 — Youngling Padawan: "When Played: The Force is with you (create
    your Force token)."  A plain WhenPlayed CreateForceToken (non-targeted)."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[CreateForceToken()])


@card_ability("LOF", "23")
def _jedi_temple():
    """LOF_23 — Jedi Temple (Base): "When a friendly Force unit attacks: The Force
    is with you (create your Force token)."

    A WhenUnitAttacks observer (the new trigger): the Base watches for a friendly
    (its own) Force-trait unit being declared as an attacker and creates its
    controller's Force token (non-targeted, resolves inline).  Bases are collected
    for triggers via the new base_zone scan in resolver._collect_triggers."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(filter=TargetSpec(
            controller="friendly", kind="unit", traits=("Force",))),
        effects=[CreateForceToken()],
    )


@card_ability("LOF", "196")
def _jedi_sentinel():
    """LOF_196 — Jedi Sentinel: "While the Force is with you, this unit gains
    Sentinel."  A conditional self-grant ConstantAbility read passively by the
    keyword query layer (the Hunting Nexu SHD_168 pattern); the keyword sanitiser's
    conditional-self-grant rule strips any printed Sentinel so this ability owns
    it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Sentinel", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "249")
def _luke_skywalker():
    """LOF_249 — Luke Skywalker: "When you play another unique unit: You may use the
    Force (lose your Force token). If you do, give an Experience token and a Shield
    token to this unit."

    An optional WhenYouPlayCard(card_type="unit", unique=True) trigger gated by
    CONTROLLER_HAS_FORCE_TOKEN — so it is offered only when there is a Force token
    to spend, and the "you may use the Force" choice is the optional Accept/Decline.
    On accept the one CustomEffect spends the token and gives Luke an Experience and
    a Shield token (bound together so "if you do" holds)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import spend_force_token
        ps = state.player_by_id(source_ci.owner_id)
        if not spend_force_token(state, ps):
            return state
        result = state.find_instance(source_ci.instance_id)
        if result is not None:
            owner_ps, ci = result
            from swu.engine.tokens import attach_token
            attach_token(state, owner_ps, ci, "Experience")
            attach_token(state, owner_ps, ci, "Shield")
        return state

    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit", unique=True),
        effects=[CustomEffect(fn=_fn)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "227")
def _the_will_of_the_force():
    """LOF_227 — The Will of the Force (Event): "Return a non-leader unit to its
    owner's hand. You may use the Force (lose your Force token). If you do, that
    player discards a random card from their hand."

    One CustomEffect with a target (any non-leader unit): the resolver prompts for
    the unit, and the fn returns it (recording its owner) then — if the controller
    has a Force token — pushes the new ``use_force`` decision with payoff
    "discard_random" against that owner (the player who got the unit back).  The
    return is mandatory-if-able (fizzles with no non-leader unit); the discard is
    the optional "you may use the Force" rider."""
    def _fn(state, source_ci, target_id, event_ctx):
        if target_id is None:
            return state
        res = state.find_instance(target_id)
        owner_id = res[1].owner_id if res is not None else None
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(state, target_id)
        if owner_id is not None:
            from swu.engine.actions import push_use_force
            push_use_force(state, source_ci,
                           payoff="discard_random", payoff_player_id=owner_id)
        return state

    return EventAbility(effects=[CustomEffect(
        fn=_fn,
        target=TargetSpec(controller="any", kind="unit", predicates=("non_leader",)),
    )])


@card_ability("LOF", "218")
def _impossible_escape():
    """LOF_218 — Impossible Escape (Event): "You may either exhaust a friendly unit
    or use the Force (lose your Force token). If you do either, exhaust an enemy
    unit and draw a card."

    A thin EventAbility CustomEffect adapter onto the new ``use_force`` decision
    (payoff "exhaust_enemy_draw", with the "exhaust a friendly unit" alternative
    cost): the controller may pay one of the two costs to exhaust an enemy unit and
    draw a card, or decline (the "you may").  With neither cost payable (no Force
    token and no ready friendly unit) nothing happens."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_use_force
        push_use_force(state, source_ci,
                       payoff="exhaust_enemy_draw", allow_exhaust_friendly=True)
        return state

    return EventAbility(effects=[CustomEffect(fn=_fn)])


def _qui_gon_bounce_and_play(state, source_ci, target_id, event_ctx):
    """Shared effect of Qui-Gon Jinn LOF_16 (both sides): return the chosen friendly
    non-leader unit to its owner's hand, then play a non-Villainy unit costing less
    than the returned unit from hand for free (push_play_from_hand)."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    returned_cost = (getattr(res[1].card_def, "cost", 0) or 0) if res is not None else 0
    from swu.abilities.resolver import _apply_return_to_hand
    _apply_return_to_hand(state, target_id)
    from swu.engine.actions import push_play_from_hand
    # "costs less than the returned unit" → printed cost ≤ returned − 1.
    push_play_from_hand(
        state, source_ci,
        cost_max=returned_cost - 1, free=True, exclude_aspect="Villainy",
    )
    return state


@card_ability("LOF", "16")
def _qui_gon_jinn():
    """LOF_16 — Qui-Gon Jinn (Leader).

    Undeployed front (text): "Action [Exhaust, use the Force (lose your Force
    token)]: Return a friendly non-leader unit to its owner's hand. Play a
    non-Villainy unit that costs less than the returned unit from your hand for
    free."  An undeployed_only ActivatedAbility whose costs are ExhaustSelf +
    UseForce (so it is offered only with a Force token to spend), gated by
    CONTROLLER_HAS_NON_LEADER_UNIT so its Force token is not wasted with nothing to
    return; the mandatory effect is the shared bounce-then-play-cheaper CustomEffect
    (target = a friendly non-leader unit).

    Deployed back (deploy_box): "When this unit completes an attack (and survives):
    You may return a friendly non-leader unit … Play a non-Villainy unit …" — an
    optional deployed_only WhenAttackEnds trigger with the same CustomEffect (no
    Force cost).  Qui-Gon is a Leader, so ``non_leader`` excludes himself.

    Epic Action (deploy at 6+ resources) is the standard deploy_threshold machinery
    — no registration."""
    bounce_target = TargetSpec(controller="friendly", kind="unit",
                               predicates=("non_leader",))
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[CustomEffect(fn=_qui_gon_bounce_and_play, target=bounce_target)],
            title="Return a unit, play a cheaper non-Villainy unit free",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_NON_LEADER_UNIT),
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_qui_gon_bounce_and_play, target=bounce_target)],
            optional=True,
            deployed_only=True,
        ),
    ]


# ── darth-maul:01 — Direct damage & removal ───────────────────────────────────
# (These LOF cards belong to the second LOF deck, ``darth-maul``; they live in
# this set module because they are LOF cards.)

@card_ability("LOF", "38")
def _pong_krell():
    """LOF_38 — Pong Krell (2/9, Grit): "When this unit completes an attack (and
    survives): You may defeat a unit with less remaining HP than this unit's
    power."

    Grit is the keyword layer.  An optional ``WhenAttackEnds`` trigger (the
    Vermillion LAW_215 / Qui-Gon Jinn LOF_16 seam — fires only for an attacker
    that survived its attack) whose one ``DefeatUnit`` targets any unit whose
    *remaining* HP is strictly less than Krell's *effective* power (the new
    ``hp_remaining_lt_source_power`` predicate, so Grit's damage-driven power boost
    is counted at trigger time).  ``controller="any"`` matches the printed "a unit";
    the optional trigger auto-declines when no unit qualifies."""
    return TriggerAbility(
        trigger=WhenAttackEnds(),
        effects=[DefeatUnit(TargetSpec(
            controller="any", kind="unit",
            predicates=("hp_remaining_lt_source_power",)))],
        optional=True,
    )


def _sith_holocron_on_attack(state, source_ci, target_id, event_ctx):
    """If a friendly unit was chosen, deal 2 damage to it and give the HOST (the
    attacker, ``source_ci`` since the granted ability resolves from the host)
    +2/+0 for this attack.  Cost (the 2 self-inflicted damage) and buff are bound
    so "If you do" holds — declining the optional trigger does neither."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage, _make_modifier
    _apply_deal_damage(state, target_id, 2)
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, source_ci.instance_id,
        power=2, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("LOF", "138")
def _sith_holocron():
    """LOF_138 — Sith Holocron (Upgrade, attach to a Force unit): "Attached unit
    gains: 'On Attack: You may deal 2 damage to a friendly unit. If you do, this
    unit gets +2/+0 for this attack.'"

    A ``GrantedAbility`` wrapping an optional ``OnAttack`` trigger that resolves
    from the HOST (the Armed to the Teeth SHD_175 pattern), so "this unit" = the
    attacking host.  One ``CustomEffect`` carries a friendly-unit ``target`` (the
    host itself is a legal friendly target — "a friendly unit" includes it); the
    fn deals 2 damage to the chosen unit and applies the +2/+0 this-attack modifier
    to the host, bound together for "If you do".  The "Attach to a Force unit"
    restriction is the engine's upgrade-target parser, so the granted ability needs
    no condition."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[CustomEffect(
            fn=_sith_holocron_on_attack,
            target=TargetSpec(controller="friendly", kind="unit"))],
    ))


def _merrin_on_attack(state, source_ci, target_id, event_ctx):
    """Discard the first card from the controller's hand (the established
    first-card discard simplification); if a card was discarded, deal 2 damage to
    the chosen unit.  Cost and payoff are bound so "If you do" holds."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state  # cannot discard → "if you do" not satisfied → no damage
    from swu.engine.state import Zone
    card = ps.hand.pop(0)
    card.zone = Zone.DISCARD
    ps.discard.append(card)
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 2)
    return state


@card_ability("LOF", "160")
def _merrin():
    """LOF_160 — Merrin (2/5): "On Attack: You may discard a card from your hand.
    If you do, deal 2 damage to a unit."

    An optional ``OnAttack`` trigger (the "you may") gated by the new
    ``CONTROLLER_HAS_CARD_IN_HAND`` condition so it is not offered with an empty
    hand (the discard cost cannot be paid).  One ``CustomEffect`` carries a unit
    ``target`` (``controller="any"`` — "a unit", which includes Merrin herself);
    the fn discards a card then deals 2, bound so "If you do" holds.  DEVIATION
    (documented): the discard uses the established first-card simplification
    (K-2SO SOR_145 / J-Type Nubian Starship LOF_194) — the controller doesn't pick
    *which* card; only the forced discard itself is faithful."""
    return TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_CARD_IN_HAND),
        effects=[CustomEffect(
            fn=_merrin_on_attack,
            target=TargetSpec(controller="any", kind="unit"))],
    )


# ── darth-maul:02 — Card advantage & disruption ───────────────────────────────

@card_ability("LOF", "59")
def _nightsister_warrior():
    """LOF_59 — Nightsister Warrior (2/2): "When Defeated: Draw a card."

    A plain mandatory ``WhenDefeated`` trigger drawing one card for the
    controller (the self-WhenDefeated machinery already fires for the dying
    unit — ``_defeat_unit`` threads ``defeated_ci`` so ``_collect_triggers`` sees
    it as a source).  ``DrawCards`` defaults to ``player="controller"`` and is
    non-targeted, so it resolves inline."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DrawCards(1)],
    )


# ── darth-maul:03 — Combat tricks, buffs & tempo ──────────────────────────────

@card_ability("LOF", "63")
def _oggdo_bogdo():
    """LOF_63 — Oggdo Bogdo (5/5 Creature): "This unit can't attack unless it's
    damaged.  When this unit attacks and defeats a unit: Heal 2 damage from this
    unit."

    Two specs:
      * The attack restriction is the new passive ``AttackRestriction`` marker
        (read only at ``actions._enumerate_attacks``): Oggdo may declare an attack
        only while it is damaged — ``condition=SOURCE_DAMAGED``.  An undamaged
        Oggdo is dropped from the legal attackers (both normal and granted
        attacks); once it has taken any damage it can attack normally.
      * "When this unit attacks and defeats a unit" is an ``OnAttackDefeatsUnit``
        trigger (fires only when Oggdo, as attacker, defeats the defender and
        survives) whose mandatory ``Heal(2, SELF)`` heals 2 damage from itself —
        re-arming the attack restriction's downside is the synergy (healing to 0
        means it can't attack again until re-damaged)."""
    return [
        AttackRestriction(ConditionCheck(Condition.SOURCE_DAMAGED)),
        TriggerAbility(
            trigger=OnAttackDefeatsUnit(),
            effects=[Heal(2, TargetSpec(fixed=SELF))],
        ),
    ]


def _darth_mauls_lightsaber_when_played(state, source_ci, target_id, event_ctx):
    """Grant the attached host (Darth Maul) an optional attack for this trigger,
    pinned to him, gaining Overwhelm and unable to attack bases for that attack.
    The host id is threaded by ``_attach_upgrade`` as ``event_ctx['attached_to_id']``
    (the Hotshot DL-44 SHD_174 / Ahsoka's Padawan Lightsaber TWI_248 pattern)."""
    from swu.engine.actions import push_granted_attack
    host_id = event_ctx.get("attached_to_id")
    if host_id:
        push_granted_attack(
            state, source_ci,
            attacker_id=host_id, optional=True,
            grant_keywords=["Overwhelm"], no_base=True,
        )
    return state


@card_ability("LOF", "140")
def _darth_mauls_lightsaber():
    """LOF_140 — Darth Maul's Lightsaber (Upgrade, Overwhelm; attach to a friendly
    non-Vehicle unit): "When Played: If attached unit is Darth Maul, you may attack
    with him.  For this attack, he gains Overwhelm and can't attack bases."

    A ``WhenPlayed`` trigger gated by ``ATTACHED_HOST_NAMED("Darth Maul")`` (the
    whole trigger is collected only when the host is Darth Maul — the LOF_201
    Qui-Gon Jinn's Lightsaber pattern), whose one ``CustomEffect`` is a thin
    adapter onto ``push_granted_attack`` pinned to the host (``attacker_id``),
    ``optional=True`` ("you may attack"), ``grant_keywords=["Overwhelm"]`` and
    ``no_base=True`` ("for this attack, he gains Overwhelm and can't attack
    bases").  If Maul is exhausted / cannot attack, the optional grant declines
    cleanly (DeclineGrantedAttack).  The non-Vehicle attach restriction is the
    engine's upgrade-target parser; the upgrade's printed Overwhelm bar is the
    accepted inert-printed-keyword simplification (the grant in the text is the
    modelled, "for this attack" copy)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_darth_mauls_lightsaber_when_played)],
        condition=ConditionCheck(Condition.ATTACHED_HOST_NAMED, "Darth Maul"),
    )


@card_ability("LOF", "233")
def _scimitar():
    """LOF_233 — Scimitar (3/4 Sith Transport Vehicle): "While this unit is damaged,
    it gets +3/+0."

    A self-targeted conditional ``ConstantAbility`` (``StatBonus(3, 0)`` gated by
    ``SOURCE_DAMAGED``), read passively by ``compute_power`` — the bonus winks on
    the moment Scimitar takes damage and off if it is healed (the Seasoned
    Shoretrooper SHD_83 / Anakin's Interceptor TWI_142 self-conditional-stat
    pattern)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=3, hp=0)],
        condition=ConditionCheck(Condition.SOURCE_DAMAGED),
    )


# ── darth-maul:04 — New primitive: force-token (reuses qui-gon-jinn:06) ────────
# The Force token primitive (CreateForceToken / UseForce / CONTROLLER_HAS_FORCE_TOKEN
# / push_use_force) was built for qui-gon-jinn:06 — this group is a pure reuse, not
# a real escalation.

def _deal_1_and_record(state, source_ci, target_id, event_ctx):
    """Deal 1 damage to the chosen unit and record its id so the second damage of
    the pair hits a *different* unit (the Grenade Strike TWI_171
    ``excludes_event_target`` pattern)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = getattr(source_ci.card_def, "display_name", None)
    _apply_deal_damage(state, target_id, 1, source_name=name)
    event_ctx["excluded_target_id"] = target_id
    return state


def _maul_damage_pair():
    """The shared "Deal 1 damage to a unit and 1 damage to a different unit" effect
    pair: a CustomEffect (any unit) deals 1 and records its target, then a plain
    DealDamage(1) targets any unit excluding the first (``excludes_event_target``).
    Both are mandatory-if-able — the second fizzles when there is no second unit."""
    return [
        CustomEffect(fn=_deal_1_and_record,
                     target=TargetSpec(controller="any", kind="unit")),
        DealDamage(1, TargetSpec(controller="any", kind="unit",
                                 predicates=("excludes_event_target",))),
    ]


@card_ability("LOF", "9")
def _darth_maul():
    """LOF_9 — Darth Maul (Leader, 5/6 Force/Sith).

    Undeployed front (text): "Action [Exhaust, use the Force (lose your Force
    token)]: Deal 1 damage to a unit and 1 damage to a different unit."  An
    ``undeployed_only`` ActivatedAbility whose costs are ExhaustSelf + UseForce
    (so it is offered only with a Force token to spend) and whose effects are the
    shared damage pair.  Not gated on target existence — faithful to the card
    (you may always activate it), and "a unit" is almost always present.

    Deployed back (deploy_box): "On Attack: Deal 1 damage to a unit and 1 damage to
    a different unit."  A ``deployed_only`` mandatory ``OnAttack`` with the same
    pair.

    The damage pair is two sequential targeted effects (the Death Trooper SHD_30
    two-DealDamage pattern): the first CustomEffect deals 1 and records its target;
    the second ``DealDamage(1)`` excludes it via the ``excludes_event_target``
    predicate, so it lands on a *different* unit (fizzling when none exists).  The
    Epic Action deploy (6+ resources) is the standard ``deploy_threshold`` machinery
    — no registration."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=_maul_damage_pair(),
            title="Deal 1 to a unit and 1 to a different unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=_maul_damage_pair(),
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "21")
def _shadowed_undercity():
    """LOF_21 — Shadowed Undercity (Base): "When a friendly Force unit attacks: The
    Force is with you (create your Force token)."

    Identical to Jedi Temple LOF_23 — a ``WhenUnitAttacks`` observer watching for a
    friendly Force-trait attacker and creating the controller's Force token (Bases
    are collected for triggers via resolver's base_zone scan)."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(filter=TargetSpec(
            controller="friendly", kind="unit", traits=("Force",))),
        effects=[CreateForceToken()],
    )


def _use_force_debuff(power, hp):
    """Build a CustomEffect fn: spend the controller's Force token, then give the
    chosen unit ``power``/``hp`` for this phase — bound together so "If you do"
    holds (the spend and the debuff are one indivisible effect; declining the
    optional trigger does neither).  The optional trigger is only ever offered with
    a Force token (the condition gate) and a legal unit target, so ``target_id`` is
    not None in practice."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import spend_force_token
        ps = state.player_by_id(source_ci.owner_id)
        if not spend_force_token(state, ps):
            return state
        if target_id is None:
            return state
        from swu.abilities.resolver import _make_modifier
        state.modifiers.append(_make_modifier(
            state, source_ci.instance_id, target_id,
            power=power, hp=hp, duration=Duration.THIS_PHASE))
        return state
    return _fn


@card_ability("LOF", "31")
def _karis():
    """LOF_31 — Karis (2/4 Force/Night): "When Defeated: You may use the Force (lose
    your Force token). If you do, give a unit –2/–2 for this phase."

    An optional ``WhenDefeated`` trigger gated by ``CONTROLLER_HAS_FORCE_TOKEN`` (so
    it is offered only with a token to spend — the "you may use the Force" choice IS
    the Accept/Decline, the Luke Skywalker LOF_249 pattern).  One ``CustomEffect``
    (target = any unit) spends the token and applies a –2/–2 this-phase modifier,
    bound together for "If you do"."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(
            fn=_use_force_debuff(-2, -2),
            target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "35")
def _talzins_assassin():
    """LOF_35 — Talzin's Assassin (4/4 Force/Night): "When Played: You may use the
    Force (lose your Force token). If you do, give a unit –3/–3 for this phase."

    Identical shape to Karis LOF_31 but a ``WhenPlayed`` trigger and a –3/–3
    modifier."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_use_force_debuff(-3, -3),
            target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _darth_sidious_fn(state, source_ci, target_id, event_ctx):
    """Spend the controller's Force token, then defeat each non-Sith unit with 3 or
    less remaining HP.  Victims are snapshotted up front so a cascading HP change
    from one defeat cannot retroactively spare/condemn another (the text defeats
    them simultaneously).  Darth Sidious is Sith, so the wipe never hits him."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
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


@card_ability("LOF", "39")
def _darth_sidious():
    """LOF_39 — Darth Sidious (6/8 Force/Separatist/Sith, Restore 2): "When Played:
    You may use the Force (lose your Force token). If you do, defeat each non-Sith
    unit with 3 or less remaining HP."

    Restore 2 is the keyword layer.  An optional ``WhenPlayed`` trigger gated by
    ``CONTROLLER_HAS_FORCE_TOKEN`` whose one no-target ``CustomEffect`` spends the
    token and runs the non-Sith ≤3-HP wipe (the "non-Sith" exclusion and the
    remaining-HP threshold are computed in the fn — a "defeat each" mass effect
    with a negated-trait filter the TargetSpec layer can't express directly).
    Being a no-target effect, the trigger is offered whenever a Force token is held
    (even with nothing to defeat) — a faithful "you may" the player simply declines
    when it would whiff."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_darth_sidious_fn)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "41")
def _drain_essence():
    """LOF_41 — Drain Essence (Event, cost 2): "Deal 2 damage to a unit. The Force
    is with you (create your Force token)."

    A plain ``EventAbility`` with two mandatory effects: a targeted ``DealDamage(2)``
    (the controller picks any unit) followed by a non-targeted ``CreateForceToken``
    (resolves inline — the Doctor Pershing SHD_28 targeted-then-untargeted pattern).
    The token is created even if the damage fizzles with no unit on the board."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(controller="any", kind="unit")),
        CreateForceToken(),
    ])


def _chirrut_imwe_fn(state, source_ci, target_id, event_ctx):
    """Spend the controller's Force token, then give the attacker (from
    ``event_ctx["attacker_id"]``) –2/–0 for this attack — reducing the damage it
    deals to Chirrut, since the trigger fires before combat damage."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    attacker_id = event_ctx.get("attacker_id")
    if attacker_id:
        from swu.abilities.resolver import _make_modifier
        state.modifiers.append(_make_modifier(
            state, source_ci.instance_id, attacker_id,
            power=-2, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("LOF", "67")
def _chirrut_imwe():
    """LOF_67 — Chirrut Îmwe (3/5 Force/Fringe, Sentinel): "When this unit is
    attacked (before damage is dealt): You may use the Force (lose your Force
    token). If you do, the attacker gets –2/–0 for this attack."

    Sentinel is the keyword layer.  An optional ``WhenAttacked`` trigger (fires when
    Chirrut is the declared defender, before combat damage) gated by
    ``CONTROLLER_HAS_FORCE_TOKEN`` — the "you may use the Force" choice is the
    Accept/Decline.  One no-target ``CustomEffect`` spends the token and applies a
    –2/–0 this-attack modifier to the attacker (read from ``event_ctx["attacker_id"]``,
    the fixed-DEFENDER/ATTACKER event-context pattern)."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[CustomEffect(fn=_chirrut_imwe_fn)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


# ── darth-maul:05 — New primitive: force-token (reuses qui-gon-jinn:06) ────────
# Five more Force-token cards.  Like darth-maul:04 these are a pure REUSE of the
# Force-token primitive built for qui-gon-jinn:06 (CreateForceToken / UseForce /
# CONTROLLER_HAS_FORCE_TOKEN / push_use_force).  Three small additive seams were
# needed for individual cards (none touching core resolution): a ``decline_penalty``
# on push_use_force (Savage Opress), a ``defeat_experience`` token helper (Infused
# Brawler), and a ``WhenYouPlayCard.on_self`` filter (Kylo Ren).


@card_ability("LOF", "129")
def _acolyte_of_the_beyond():
    """LOF_129 — Acolyte of the Beyond (2/3 Sith): "On Attack/When Defeated: The
    Force is with you (create your Force token)."

    Two mandatory triggers, each a non-targeted ``CreateForceToken`` (resolves
    inline).  The token is a single per-player boolean, so a second creation while
    one is already held is a harmless no-op."""
    return [
        TriggerAbility(trigger=OnAttack(), effects=[CreateForceToken()]),
        TriggerAbility(trigger=WhenDefeated(), effects=[CreateForceToken()]),
    ]


def _savage_opress_fn(state, source_ci, target_id, event_ctx):
    """Push the "you may use the Force; if you don't, deal 9 to your base" choice
    (the inverse force-spend).  ``push_use_force`` with ``decline_penalty`` pushes a
    use_force decision when a Force token is held (use it = avoid the penalty;
    decline = take 9 to your own base) and, when no token is held, applies the 9
    damage inline (you cannot use the Force, so "you don't")."""
    from swu.engine.actions import push_use_force
    push_use_force(state, source_ci, payoff="none",
                   decline_penalty="self_base_damage:9")
    return state


@card_ability("LOF", "137")
def _savage_opress():
    """LOF_137 — Savage Opress (9/6 Force/Night, Overwhelm): "When Played/When
    Defeated: You may use the Force (lose your Force token). If you don't, deal 9
    damage to your base."

    Overwhelm is the keyword layer.  Two mandatory triggers (the whole clause
    always happens — the "may" is internal to the use_force choice), each a
    no-target ``CustomEffect`` adapter onto ``push_use_force`` with the new
    ``decline_penalty`` (the Palpatine SOR_135 inline-push pattern).  Modelling
    this as a normal optional trigger gated by CONTROLLER_HAS_FORCE_TOKEN would be
    wrong — the penalty must land on decline AND when no token is held."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_savage_opress_fn)]),
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[CustomEffect(fn=_savage_opress_fn)]),
    ]


def _infused_brawler_use_force(state, source_ci, target_id, event_ctx):
    """Spend the controller's Force token and give this unit 2 Experience tokens —
    bound together so "If you do" holds (the Luke Skywalker LOF_249 pattern)."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    from swu.engine.tokens import attach_token
    for _ in range(2):
        attach_token(state, ps, source_ci, "Experience")
    return state


def _infused_brawler_defeat_exp(state, source_ci, target_id, event_ctx):
    """Defeat one Experience token on this unit (no-op if it has none)."""
    from swu.engine.tokens import defeat_experience
    defeat_experience(state, source_ci)
    return state


@card_ability("LOF", "156")
def _infused_brawler():
    """LOF_156 — Infused Brawler (2/2 Force/Night): "When Played: You may use the
    Force (lose your Force token). If you do, give 2 Experience tokens to this unit.
    When this unit completes an attack: Defeat an Experience token on it."

    First ability: an optional ``WhenPlayed`` gated by CONTROLLER_HAS_FORCE_TOKEN
    (the "you may use the Force" choice = Accept/Decline, the Karis LOF_31 pattern);
    its one no-target ``CustomEffect`` spends the token and gives this unit 2
    Experience.  Second ability: a mandatory ``WhenAttackEnds`` ("completes an
    attack"; a defeated attacker has no token to defeat, so the survivor-only firing
    is faithful) whose no-target ``CustomEffect`` defeats one Experience token on
    this unit (the new ``defeat_experience`` token helper)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_infused_brawler_use_force)],
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
        ),
        TriggerAbility(
            trigger=WhenAttackEnds(),
            effects=[CustomEffect(fn=_infused_brawler_defeat_exp)],
        ),
    ]


def _kylo_ren_use_force(state, source_ci, target_id, event_ctx):
    """Spend the controller's Force token and draw a card — bound for "If you do"."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    from swu.engine.actions import _draw_cards
    _draw_cards(state, ps, 1)
    return state


@card_ability("LOF", "229")
def _kylo_ren():
    """LOF_229 — Kylo Ren (2/3 First Order/Force, Overwhelm): "When you play an
    upgrade on this unit: You may use the Force (lose your Force token). If you do,
    draw a card."

    Overwhelm is the keyword layer.  A ``WhenYouPlayCard(card_type="upgrade",
    on_self=True)`` observer — the new ``on_self`` filter narrows to an upgrade
    played onto Kylo himself (the matcher locates the played upgrade's host).
    Optional and gated by CONTROLLER_HAS_FORCE_TOKEN (the "you may use the Force"
    choice = Accept/Decline); its no-target ``CustomEffect`` spends the token and
    draws a card."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="upgrade", on_self=True),
        effects=[CustomEffect(fn=_kylo_ren_use_force)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "231")
def _darth_tyranus():
    """LOF_231 — Darth Tyranus (4/3 Force/Separatist/Sith, Shielded): "While the
    Force is with you, this unit gains Ambush."

    Shielded is the keyword layer (genuinely possessed — kept).  The conditional
    Ambush is a self-targeted ``ConstantAbility`` gated by CONTROLLER_HAS_FORCE_TOKEN
    (the Jedi Sentinel LOF_196 / Hunting Nexu SHD_168 pattern), read passively by
    ``has_keyword`` so it winks on/off with the Force token — and consulted at the
    enter-play keyword bus, so playing Tyranus while the Force is with you grants
    the Ambush attack.  The official data mis-tags him with a printed Ambush; the
    keyword sanitiser's conditional-self-grant rule strips it (this ability owns
    it), leaving Shielded intact."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Ambush", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


# ── Reprint-duplicate encode (Stage 4 of docs/dev/plans/reprint_duplicates_plan.md) ─────

@card_ability("LOF", "165")
def _asajj_ventress():
    """LOF_165 — Asajj Ventress (Unit, 5/6): "When Played/On Attack: Give another
    friendly Force unit +2/+0 for this phase."

    Two otherwise-identical mandatory triggers (a ``WhenPlayed`` and an
    ``OnAttack``), each a ``ModifyStats(+2/+0, this phase)`` targeting another
    friendly Force unit (``not_self`` — "another"; the ``Force`` trait filter).
    Mandatory-if-able: with no other friendly Force unit the effect fizzles (no
    legal target), so nothing is buffed."""
    buff = [ModifyStats(power=2, hp=0,
                        target=TargetSpec(controller="friendly", kind="unit",
                                          traits=("Force",),
                                          predicates=("not_self",)),
                        duration=Duration.THIS_PHASE)]
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(buff)),
        TriggerAbility(trigger=OnAttack(), effects=list(buff)),
    ]


# ── Reprint sweep Stage 4 Batch 2 (canonical encodes) ────────────────────────

@card_ability("LOF", "45")
def _yaddle():
    """LOF_45 — Yaddle (Unit, Force/Jedi/Republic, Restore 1 — keyword layer): "On
    Attack: Each other friendly Jedi unit gains Restore 1 for this phase."

    A plain ``OnAttack`` ``GrantKeyword("Restore", 1, …, THIS_PHASE)`` whose fixed
    ``EACH_FRIENDLY`` target (with a Jedi trait filter and ``not_self``)
    auto-grants Restore 1 to every other friendly Jedi unit (the Encouraging
    Leadership TWI_126 / Maarva Andor SEC_252 each-friendly pattern), read passively
    by ``keyword_value``.  Yaddle keeps her own printed Restore 1 — this grant is to
    *other* units, not a self-grant, so neither sanitiser self-grant rule strips
    it."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GrantKeyword(
            "Restore", 1,
            TargetSpec(controller="friendly", kind="unit", traits=("Jedi",),
                       predicates=("not_self",), fixed=EACH_FRIENDLY),
            Duration.THIS_PHASE)],
    )


@card_ability("LOF", "77")
def _crushing_blow():
    """LOF_77 — Crushing Blow (Event, Tactic): "Defeat a non-leader unit that costs
    2 or less."

    A plain ``EventAbility`` with one mandatory ``DefeatUnit`` targeting any
    non-leader unit with printed cost ≤ 2 (the Confiscate SHD_262 / Fell the Dragon
    SHD_78 cost-restricted removal pattern); mandatory-if-able — the controller
    chooses one to defeat, or it fizzles cleanly with no eligible unit."""
    return EventAbility(effects=[
        DefeatUnit(TargetSpec(controller="any", kind="unit",
                              predicates=("non_leader",), cost_max=2)),
    ])


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonicals, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

@card_ability("LOF", "130")
def _hk_47():
    """LOF_130 — HK-47 (2/4): "When an enemy unit is defeated: Deal 1 damage to its
    controller's base."

    A ``WhenUnitDefeated`` observer whose ``filter`` is an enemy unit (matched from
    HK-47's controller's perspective — the Rogue One LAW_119 pattern, mirrored for
    the enemy side, so a *friendly* defeat never fires it).  "Its controller's
    base" is the enemy base: ``DealDamage(1, kind="base", controller="enemy",
    fixed=EACH_ENEMY)`` auto-targets the opponent's base and resolves inline (no
    player choice)."""
    return TriggerAbility(
        trigger=WhenUnitDefeated(
            filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="base",
                                          fixed=EACH_ENEMY))],
    )


@card_ability("LOF", "207")
def _loth_cat():
    """LOF_207 — Loth-Cat (2/1): "When Played/When Defeated: You may exhaust a
    ground unit."

    Two optional triggers (a ``WhenPlayed`` and a ``WhenDefeated``), each a plain
    ``ExhaustCard`` on any ground unit (``controller="any"`` — the controller
    points it at an enemy).  With no ground unit on the board the optional trigger
    auto-declines (no prompt)."""
    target = TargetSpec(controller="any", kind="unit", arena="ground")
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[ExhaustCard(target)]),
        TriggerAbility(trigger=WhenDefeated(), optional=True,
                       effects=[ExhaustCard(target)]),
    ]


@card_ability("LOF", "235")
def _hk_87_assassin_droid():
    """LOF_235 — HK-87 Assassin Droid (4/4): "When Defeated: Deal 2 damage to each
    ground unit."

    A plain ``WhenDefeated`` dealing 2 to every ground unit of either controller
    (``fixed=EACH_IN_PLAY`` auto-targets, snapshotting the targets so the damage is
    simultaneous — matching the card's rules box).  HK-87 has already left its
    arena by the time this resolves, so it never damages itself."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(controller="any", kind="unit",
                                          arena="ground", fixed=EACH_IN_PLAY))],
    )


# ── Reprint-duplicate sweep (Stage 4) — shipped-set canonical, pure primitive
#    reuse; siblings aliased in swu.cards.reprints.REPRINT_ALIASES. ─────────────

@card_ability("LOF", "51")
def _jedi_holocron():
    """LOF_51 — Jedi Holocron (Upgrade, attach to a Force unit): "Attached unit
    gains: 'On Attack: You may heal 3 damage from another unit.'"

    A ``GrantedAbility`` wrapping an optional ``OnAttack`` that resolves from the
    HOST (the Armed to the Teeth SHD_175 / Jedi Holocron pattern), so
    ``not_self`` excludes the attacking host and "another unit" falls out.  The
    "attach to a Force unit" restriction is the upgrade-target parser."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        optional=True,
        effects=[Heal(3, TargetSpec(controller="any", kind="unit",
                                    predicates=("not_self",)))],
    ))


@card_ability("LOF", "187")
def _corrupted_saber():
    """LOF_187 — Corrupted Saber (Upgrade, attach to a non-Vehicle unit): "If
    attached unit is a Force unit, it gains: 'On Attack: The defender gets −2/−0
    for this attack.'"

    A ``GrantedAbility`` wrapping an ``OnAttack`` (resolves from the host) gated by
    ``SOURCE_HAS_TRAIT("Force")`` (the granted ability is collected only while the
    host is a Force unit — the Fallen Lightsaber SOR_137 pattern).  ``fixed=DEFENDER``
    applies the this-attack −2/−0 to the current defender and resolves to nothing on
    a base attack, so it fizzles harmlessly there."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Force"),
        effects=[ModifyStats(power=-2, hp=0, target=TargetSpec(fixed=DEFENDER),
                             duration=Duration.THIS_ATTACK)],
    ))


@card_ability("LOF", "238")
def _darth_revans_lightsabers():
    """LOF_238 — Darth Revan's Lightsabers (Upgrade, attach to a non-Vehicle unit):
    "If attached unit is a Sith, it gains Grit."

    A self-targeted conditional ``ConstantAbility(KeywordGrant("Grit"))`` read by
    the keyword layer's attached-upgrade conferral scan (Grievous's Wheel Bike
    TWI_236 / Darth Revan's Lightsabers pattern), which confers the keyword to the
    HOST and evaluates the ``SOURCE_HAS_TRAIT("Sith")`` condition against the host.
    Grit is the existing keyword (Grit's compute_power path).  The upgrade's printed
    Grit bar (a mistag on a non-attacking upgrade) is stripped by the keyword
    sanitiser's conditional-self-grant rule now that this ability models it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Grit", value=0)],
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Sith"),
    )


def _flight_of_the_inquisitor(state, source_ci, target_id, event_ctx):
    """Adapter: offer two independent "up to 1" ``return_from_discard`` decisions —
    one for a Force unit, one for a Lightsaber upgrade — from the controller's
    discard pile (the Tranquility TWI_246 / Razor Crest SHD_44 pattern).

    Both are pushed (each only when an eligible card is present); they resolve LIFO
    with no dependency between them, so the "and" of the printed text is honoured
    (return up to one of each)."""
    from swu.cards.models import Unit, Upgrade
    from swu.engine.actions import push_return_from_discard

    def _is_force_unit(card_def) -> bool:
        return isinstance(card_def, Unit) and "Force" in (getattr(card_def, "traits", None) or ())

    def _is_lightsaber_upgrade(card_def) -> bool:
        return isinstance(card_def, Upgrade) and "Lightsaber" in (getattr(card_def, "traits", None) or ())

    push_return_from_discard(state, source_ci, count=1, up_to=True,
                             eligible=_is_force_unit)
    push_return_from_discard(state, source_ci, count=1, up_to=True,
                             eligible=_is_lightsaber_upgrade)
    return state


@card_ability("LOF", "240")
def _flight_of_the_inquisitor_card():
    """LOF_240 — Flight of the Inquisitor (Event, Tactic): "You may return a Force
    unit and a Lightsaber upgrade from your discard pile to your hand."

    A plain ``EventAbility`` whose one no-target ``CustomEffect`` pushes two
    independent "up to 1" ``return_from_discard`` decisions (see
    ``_flight_of_the_inquisitor``)."""
    return EventAbility(effects=[CustomEffect(fn=_flight_of_the_inquisitor)])


# ---------------------------------------------------------------------------
# Reprint-duplicate batch 6 (2026-07-08)
# ---------------------------------------------------------------------------


@card_ability("LOF", "46")
def _ezra_bridger_lof46():
    """LOF_46 — Ezra Bridger (Unit): "On Attack: You may give an Experience token
    to another Creature or Spectre unit."

    An optional ``OnAttack`` ``GiveToken`` whose target is another unit carrying
    the Creature OR Spectre trait — the new ``creature_or_spectre`` predicate (a
    trait-OR a single ``traits`` tuple cannot express; the ``droid_or_vehicle``
    JTL_230 pattern).  ``controller="any"`` mirrors the printed "a unit"; an
    Experience token benefits the recipient, so the controller never points it at
    an enemy.  With no other Creature/Spectre unit the optional trigger
    auto-declines."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="any", kind="unit",
            predicates=("not_self", "creature_or_spectre")))],
        optional=True,
    )


@card_ability("LOF", "163")
def _quinlan_vos_lof163():
    """LOF_163 — Quinlan Vos (Unit): "On Attack: If this unit has 6 or more power,
    you may deal 2 damage to an enemy base."

    An optional ``OnAttack`` whose one mandatory ``DealDamage(2, enemy base)`` is
    gated by the new ``SOURCE_POWER_MIN(6)`` condition — the condition gates
    trigger COLLECTION, so the "you may" is never offered below 6 effective power
    (an enemy base always exists, so an ungated optional trigger would always be
    offered).  Quinlan is 4/5, reaching 6 via upgrades / Experience tokens."""
    return TriggerAbility(
        trigger=OnAttack(),
        condition=ConditionCheck(Condition.SOURCE_POWER_MIN, param=6),
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="base"))],
        optional=True,
    )


@card_ability("LOF", "62")
def _axe_woves_lof62():
    """LOF_62 — Axe Woves (Unit, 2/2): "Shielded. This unit gets +1/+1 for each
    upgrade on him."

    Shielded is the keyword layer.  The scaling buff is a self-targeted
    ``ConstantAbility`` with the new ``upgrades_on_self`` StatBonus count (the Nien
    Nunb JTL_93 scaling-StatBonus pattern), read passively by
    ``compute_power``/``compute_hp`` and winking with the board.  Tokens count as
    upgrades per CR, so an Experience token nets +2/+2 (its own +1/+1 plus this)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=1, count="upgrades_on_self")],
    )


@card_ability("LOF", "132")
def _grand_inquisitor_lof132():
    """LOF_132 — Grand Inquisitor (Unit, 3/4): "Hidden. Raid 1. Other friendly
    Inquisitor units gain Hidden."

    His own Hidden + Raid 1 are the keyword layer (kept by the sanitiser's
    bare-mention rule).  The grant is a ``ConstantAbility`` over every OTHER friendly
    Inquisitor unit conferring Hidden (the Red Three SOR_144 grant-to-others
    pattern), read passively by ``has_keyword`` — so an Inquisitor played the same
    phase while Grand Inquisitor is in play can't be attacked that phase."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          traits=("Inquisitor",), predicates=("not_self",)),
        effects=[KeywordGrant("Hidden")],
    )


# ---------------------------------------------------------------------------
# Stage-4 reprint sweep (Batch 8, 2026-07-08) — shipped-set canonical encodes.
# Siblings aliased in src/swu/cards/reprints.py.
# ---------------------------------------------------------------------------


@card_ability("LOF", "70")
def _anakin_skywalker_lof70():
    """LOF_70 Anakin Skywalker (Unit 5/7): two When Played triggers —
    "If there is a Heroism card in your discard pile, you may give a unit -3/-3
    for this phase" and the same gated on a Villainy card in the discard pile.

    Two optional ``WhenPlayed`` triggers, each gated by the new
    ``CONTROLLER_HAS_ASPECT_CARD_IN_DISCARD`` condition (so the trigger is not
    offered without a matching discard card) with a ``ModifyStats(-3,-3, any
    unit, THIS_PHASE)``.  When both aspects are present both fire (each a separate
    -3/-3)."""
    def _debuff(aspect):
        return TriggerAbility(
            trigger=WhenPlayed(),
            optional=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_ASPECT_CARD_IN_DISCARD, aspect),
            effects=[ModifyStats(power=-3, hp=-3,
                                 target=TargetSpec(controller="any", kind="unit"),
                                 duration=Duration.THIS_PHASE)],
        )
    return [_debuff("Heroism"), _debuff("Villainy")]


@card_ability("LOF", "234")
def _darth_malak_lof234():
    """LOF_234 Darth Malak (Unit 4/7, Overwhelm): "When Played: If you control a
    Sith leader unit, you may ready this unit."

    Overwhelm is the keyword layer.  An optional ``WhenPlayed`` gated by the new
    ``CONTROLLER_HAS_TRAIT_LEADER_UNIT("Sith")`` condition (so it is offered only
    when a Sith leader unit is in play) with a ``ReadyCard(fixed=SELF)`` — Malak
    enters exhausted like any non-leader unit, so readying lets him attack the
    round he is played."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_LEADER_UNIT, "Sith"),
        effects=[ReadyCard(TargetSpec(fixed=SELF))],
    )


@card_ability("LOF", "40")
def _kylo_rens_lightsaber_lof40():
    """LOF_40 Kylo Ren's Lightsaber (Upgrade, attach to a non-Vehicle unit): "If
    attached unit is a Force unit, it gains: 'This unit can't be exhausted by
    enemy card abilities.'"

    A self-targeted ``ConstantAbility`` conferring ``Protection(from_exhaust=True)``
    on the host (the Chewbacca JTL_103 "attached unit gains X" convention), gated
    by ``SOURCE_HAS_TRAIT("Force")`` so it applies only while the host is a Force
    unit (the condition reads the host, since the protection is looked up per
    host).  The exhaust protection is honoured at the ``ExhaustCard`` resolver arm
    for *enemy* abilities only; the non-Vehicle attach is the upgrade-target parser."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[Protection(from_exhaust=True)],
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, "Force"),
    )


# ── Reprint-sweep batch (2026-07-09) ─────────────────────────────────────────

@card_ability("LOF", "37")
def _darth_vader_lof37():
    """LOF_37 — Darth Vader (5/6 Force/Imperial/Sith): "When Played: Give a Shield
    token to a friendly unit and to an enemy unit.  On Attack: Defeat an enemy unit
    with a Shield token on it."

    The ``WhenPlayed`` is two mandatory ``GiveToken("Shield", …)`` — one friendly
    (Vader himself is a legal friendly target), one enemy.  The ``OnAttack`` is a
    mandatory ``DefeatUnit`` on an enemy unit carrying a Shield token (the new
    ``has_shield_token`` predicate); it fizzles cleanly when no enemy unit has a
    Shield.  Since the When Played hands the enemy a Shield, the On Attack has a
    ready-made target on the next attack."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[
                GiveToken("Shield", TargetSpec(controller="friendly", kind="unit")),
                GiveToken("Shield", TargetSpec(controller="enemy", kind="unit")),
            ],
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DefeatUnit(TargetSpec(
                controller="enemy", kind="unit",
                predicates=("has_shield_token",)))],
        ),
    ]


# ── Stage-4 reprint sweep (batch 11) — LOF cards ─────────────────────────────

def _inquisitors_lightsaber_on_attack(state, source_ci, target_id, event_ctx):
    """While the host is attacking a Force unit, it gets +2/+0 for this attack."""
    from swu.engine.traits import has_trait
    from swu.abilities.resolver import _make_modifier
    defender_id = event_ctx.get("defender_id")
    if not defender_id:
        return state  # attacking a base — no defender unit
    res = state.find_instance(defender_id)
    if res is None:
        return state
    _, defender = res
    if not has_trait(state, defender, "Force"):
        return state
    mod = _make_modifier(state, source_ci.instance_id, source_ci.instance_id,
                         power=2, hp=0, duration=Duration.THIS_ATTACK)
    state.modifiers.append(mod)
    return state


@card_ability("LOF", "90")
def _inquisitors_lightsaber():
    """LOF_90 — Inquisitor's Lightsaber (Upgrade): "Attach to a non-Vehicle unit.
    Attached unit gains: 'While attacking a Force unit, this unit gets +2/+0.'"

    A GrantedAbility wrapping an OnAttack CustomEffect that resolves from the HOST
    (the Chain Code Collector SHD_216 / Vambrace Grappleshot SHD_74 pattern): at
    combat step 2 it reads the current defender and, if it is a Force unit, applies
    a this-attack +2/+0 modifier to the host.  Modelling the static "while
    attacking a Force unit" clause as an OnAttack this-attack buff is
    behaviour-identical (the bonus only matters during that attack, and a base
    attack has no defender so it fizzles).  The non-Vehicle attach restriction is
    the upgrade-target parser."""
    return GrantedAbility(ability=TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_inquisitors_lightsaber_on_attack)],
    ))


def _grogu_heal_record(state, source_ci, target_id, event_ctx):
    """Heal up to 2 damage from the chosen unit; record how much was actually
    healed so the follow-up damage matches ("deal that much")."""
    event_ctx["grogu_amount"] = 0
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, unit = res
    healed = min(2, int(getattr(unit, "damage", 0) or 0))
    if healed > 0:
        unit.damage -= healed
    event_ctx["grogu_amount"] = healed
    return state


def _grogu_deal(state, source_ci, target_id, event_ctx):
    """Deal the recorded healed amount to the chosen unit."""
    if target_id is None:
        return state
    amount = int(event_ctx.get("grogu_amount", 0) or 0)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(
        state, target_id, amount, source_ci.card_def.display_name)


@card_ability("LOF", "246")
def _grogu():
    """LOF_246 — Grogu (Unit, Hidden — keyword layer): "Action [Exhaust]: Heal up
    to 2 damage from a unit.  If you do, deal that much damage to a unit."

    Two dependent CustomEffect.target effects sharing the resolve_effects
    ``event_ctx`` (the Haymaker LAW_168 / Grenade Strike TWI_171 pattern): the
    first heals as much as possible (min(2, damage)) from the chosen unit and
    records the amount; the second deals that much to a chosen unit.  DEVIATION
    (documented): "up to 2" is modelled as healing the maximum available rather
    than offering a 0/1/2 amount choice — a new choose-amount decision kind is not
    worth the agency (healing more is strictly better for the controller, who then
    aims the equal damage at an enemy).  Healing an undamaged unit heals 0, so the
    follow-up deals 0 — a clean no-op."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[
            CustomEffect(fn=_grogu_heal_record,
                         target=TargetSpec(controller="any", kind="unit")),
            CustomEffect(fn=_grogu_deal,
                         target=TargetSpec(controller="any", kind="unit")),
        ],
        title="Heal up to 2 damage, then deal that much",
    )


@card_ability("LOF", "261")
def _constructed_lightsaber():
    """LOF_261 — Constructed Lightsaber (Upgrade): "Attach to a Force unit.
    If attached unit is a Heroism unit, it gains Restore 2.
    If attached unit is a Villainy unit, it gains Raid 2.
    If attached unit is a non-Heroism, non-Villainy unit, it gains Sentinel."

    Three mutually-exclusive self-targeted ConstantAbility KeywordGrants gated by
    the host's printed aspect (the new SOURCE_HAS_ASPECT / SOURCE_LACKS_ASPECTS
    conditions).  The keyword query layer's attached-upgrade scan
    (``has_keyword`` / ``keyword_value``) reads a SELF-targeted upgrade
    ConstantAbility KeywordGrant and evaluates its condition against the HOST, so
    the granted keyword winks on with the host's aspect (the Grievous's Wheel Bike
    TWI_236 upgrade-keyword-scan pattern).  The "Force unit" attach restriction is
    the upgrade-target parser."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Restore", 2)],
            condition=ConditionCheck(Condition.SOURCE_HAS_ASPECT, "Heroism"),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Raid", 2)],
            condition=ConditionCheck(Condition.SOURCE_HAS_ASPECT, "Villainy"),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant("Sentinel", 0)],
            condition=ConditionCheck(Condition.SOURCE_LACKS_ASPECTS, "Heroism,Villainy"),
        ),
    ]


@card_ability("LOF", "148")
def _rey_with_palpatines_power():
    """LOF_148 — Rey, "With Palpatine's Power" (Unit 5/5):
    "When you draw this card during the action phase: If you control an Aggression
     leader or base, you may reveal this card from your hand. If you do, deal 2
     damage to a unit and 2 damage to a base."

    The batch-16 ``WhenYouDraw`` observer (drawn-card flavour, ``on_self=True``):
    the trigger fires for Rey while she sits in the drawer's hand (a dedicated hand
    scan in ``resolver._collect_triggers`` collects it — ``find_instance`` locates
    her in hand, and the effects target the board, so resolving from a hand source
    needs no new machinery).  Collection is gated by the new
    ``CONTROLLER_HAS_ASPECT_LEADER_OR_BASE`` condition ("If you control an Aggression
    leader or base"); the "you may reveal this card from your hand" is the optional
    trigger's Accept/Decline (the reveal itself is a documented no-op — Rey stays in
    hand).  On accept both mandatory damage effects resolve."""
    return TriggerAbility(
        trigger=WhenYouDraw(on_self=True),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_ASPECT_LEADER_OR_BASE,
                                 param="Aggression"),
        effects=[
            DealDamage(2, TargetSpec(controller="any", kind="unit")),
            DealDamage(2, TargetSpec(controller="any", kind="base")),
        ],
    )


# ── Reprint sweep Stage 4 Batch 17 (FRAMEWORK — new WhenYouUseForce observer) ──

def _yoda_use_force_heal(state, source_ci, target_id, event_ctx):
    """Yoda's "When Played: You may use the Force. If you do, heal 5 damage from a
    base."  Spend the controller's Force token (via the ``spend_force_token``
    chokepoint — which records the use so Yoda's second ability observer fires),
    then heal 5 from the controller's OWN base (the "a base" convention — you never
    heal the enemy's).  Bound in one ``CustomEffect`` so "If you do" holds — with no
    token the spend fails and no healing happens (the Infused Brawler LOF_156
    pattern)."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    base_ci = ps.base_instance
    if base_ci is not None:
        base_ci.damage = max(0, base_ci.damage - 5)
    return state


@card_ability("LOF", "101")
def _yoda_my_ally_is_the_force():
    """LOF_101 — Yoda, "My Ally is the Force" (Unit 5/9, cost 8):
    "When Played: You may use the Force. If you do, heal 5 damage from a base.
     When you use the Force: You may deal damage to a unit equal to twice the
     number of units you control."

    The batch-17 ``WhenYouUseForce`` observer — an exact mirror of the batch-16
    ``WhenYouDraw`` ledger+settle observer, reusing the qui-gon-jinn:06 Force-token
    primitive.  First ability: an optional ``WhenPlayed`` gated by
    ``CONTROLLER_HAS_FORCE_TOKEN`` (so the Accept/Decline IS the "you may use the
    Force" choice) whose one ``CustomEffect`` spends the token and heals 5 from the
    controller's base — the spend routes through ``spend_force_token``, recording the
    use into the ``force_uses`` ledger.  Second ability: an optional
    ``WhenYouUseForce`` observer (in-play, collected by the ordinary arena scan)
    whose ``DealDamageEqualTo(count="source_controller_units_x2")`` deals 2× the
    controller's unit count to a chosen unit.  Per the card's rules box, using the
    Force for the first ability triggers the second — the ledger is drained at the
    settle-point after the WhenPlayed resolves, firing the observer while Yoda is in
    play.  No self-chain (dealing damage does not use the Force), so no
    ``SOURCE_READY`` gate is needed."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
            effects=[CustomEffect(fn=_yoda_use_force_heal)],
        ),
        TriggerAbility(
            trigger=WhenYouUseForce(),
            optional=True,
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit"),
                count="source_controller_units_x2")],
        ),
    ]


@card_ability("LOF", "185")
def _baylan_skoll():
    """LOF_185 — Baylan Skoll (Unit 5/5, Hidden = keyword layer): "When Played:
    You may use the Force. If you do, return a non-leader unit that costs 4 or
    less to its owner's hand. Then, its owner may play it for free."

    The multi-decider return-then-owner-replays-free primitive (shared with Rio
    Durant LAW_93).  An optional ``WhenPlayed`` gated by
    ``CONTROLLER_HAS_FORCE_TOKEN`` — the Accept/Decline IS the "you may use the
    Force" choice.  On accept, a target is chosen (a non-leader unit costing ≤ 4,
    any controller) and the one ``CustomEffect`` spends the Force token, returns
    that unit to its owner's hand (``_apply_return_to_hand``), then hands that
    owner an ``owner_may_replay`` decision to play it for FREE — the owner may be
    the source's opponent (the say_no SOR_233 deciding-player shift).  Baylan
    grants no keyword on the replay (unlike Rio's Shielded).  With a Force token
    but no eligible unit to return the optional trigger auto-declines (the token
    is not wasted)."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import spend_force_token, push_owner_may_replay
        from swu.abilities.resolver import _apply_return_to_hand
        ps = state.player_by_id(source_ci.owner_id)
        if not spend_force_token(state, ps):
            return state
        if target_id is None:
            return state
        _apply_return_to_hand(state, target_id)
        push_owner_may_replay(state, source_ci, target_id)
        return state

    return TriggerAbility(
        trigger=WhenPlayed(),
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
        effects=[CustomEffect(fn=_fn, target=TargetSpec(
            controller="any", kind="unit",
            predicates=("non_leader",), cost_max=4))],
    )


@card_ability("LOF", "200")
def _qui_gon_jinn_lof200():
    """Qui-Gon Jinn LOF_200 — "Ambush.  When Defeated: You may choose a non-leader
    ground unit.  Its owner puts it on the top or bottom of their deck."

    Ambush is the keyword layer.  An OPTIONAL ``WhenDefeated`` (the "you may") whose
    one ``CustomEffect`` targets a non-leader ground unit (any controller — the
    controller points it at an enemy) and is a thin adapter onto the new
    ``push_put_on_deck`` multi-decider decision (the Palpatine SOR_135 inline-push
    pattern): the chosen unit's OWNER then decides top vs bottom.  With no eligible
    ground unit the optional trigger auto-declines."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_put_on_deck
        if target_id is None:
            return state
        push_put_on_deck(state, source_ci, target_id)
        return state

    return TriggerAbility(
        trigger=WhenDefeated(),
        optional=True,
        effects=[CustomEffect(fn=_fn, target=TargetSpec(
            controller="any", kind="unit", arena="ground",
            predicates=("non_leader",)))],
    )


@card_ability("LOF", "42")
def _always_two():
    """Always Two (Event) — "Choose 2 friendly unique Sith units. If you do, give
    2 Shield tokens and 2 Experience tokens to each chosen unit. Defeat all other
    friendly units."

    A thin ``EventAbility`` adapter (the Palpatine SOR_135 inline-push pattern) onto
    the new ``choose_units_sacrifice_rest`` decision kind: the controller chooses
    exactly 2 friendly unique Sith units to spare, each is buffed, and every other
    friendly unit is defeated.  With fewer than 2 eligible units the push is a clean
    no-op ("If you do" fails — nothing is defeated).  The event sits in discard
    during resolution, but the push scans the controller's arenas directly, so the
    source's location is a non-issue."""
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import push_choose_units_sacrifice_rest
        push_choose_units_sacrifice_rest(
            state, source_ci,
            required_count=2,
            traits=["Sith"], predicates=["unique"],
            tokens=[["Shield", 2], ["Experience", 2]],
        )
        return state

    return EventAbility(effects=[CustomEffect(fn=_fn)])


def _leia_lof98_move_to_ground(state, source_ci, target_id, event_ctx):
    """Leia Organa LOF_98's Action, relocation half: move her from the space arena
    to the ground arena (mirrors Blue Leader JTL_96's inline space→ground move)."""
    from swu.engine.state import Zone
    ps = state.player_by_id(source_ci.owner_id)
    for arena in (ps.ground_arena, ps.space_arena):
        if source_ci in arena:
            arena.remove(source_ci)
            break
    source_ci.zone = Zone.GROUND_ARENA
    ps.ground_arena.append(source_ci)
    for up in source_ci.attached_upgrades:
        up.zone = Zone.GROUND_ARENA
    return state


@card_ability("LOF", "98")
def _leia_organa_lof98():
    """LOF_98 — Leia Organa (5/5 unique Space unit, Command/Heroism): "While this
    unit is in the space arena, she can't ready and gains: 'Action [use the Force]:
    Move this unit to the ground arena and give each friendly Heroism unit +2/+2 for
    this phase.'"

    Two specs sharing ONE ``SOURCE_IN_SPACE_ARENA`` atom (batch-37 primitive):
    - a ``ReadyRestriction`` (the ready-site mirror of ``AttackRestriction``) so she
      can't ready while she sits in the space arena — read at ``_end_regroup`` + the
      ``ReadyCard`` effect arm, and lifted automatically once she moves to ground;
    - an ``ActivatedAbility`` gated by ``condition=SOURCE_IN_SPACE_ARENA`` (so the
      Action is offered only while she's in space — the "gains [Action]" clause),
      costing the Force token (``UseForce()``).  Its effects: a no-target
      ``CustomEffect`` moving her to the ground arena (the Blue Leader JTL_96
      relocation), then a ``ModifyStats`` +2/+2 THIS_PHASE to every friendly Heroism
      unit (``EACH_FRIENDLY`` honours the aspect filter; she is herself a friendly
      Heroism unit, so she's buffed too — faithful to "each friendly Heroism unit").
    Once she reaches the ground arena, ``SOURCE_IN_SPACE_ARENA`` goes False, so both
    the restriction and the Action disappear."""
    return [
        ReadyRestriction(ConditionCheck(Condition.SOURCE_IN_SPACE_ARENA)),
        ActivatedAbility(
            costs=[UseForce()],
            effects=[
                CustomEffect(fn=_leia_lof98_move_to_ground),
                ModifyStats(
                    power=2, hp=2,
                    target=TargetSpec(controller="friendly", kind="unit",
                                      aspects=("Heroism",), fixed=EACH_FRIENDLY),
                    duration=Duration.THIS_PHASE),
            ],
            title="Move to the ground arena; friendly Heroism units +2/+2",
            condition=ConditionCheck(Condition.SOURCE_IN_SPACE_ARENA),
        ),
    ]


# ── Stage 4 batch 41 (2026-07-15) — FRAMEWORK ESCALATION: ability-damage prevention
@card_ability("LOF", "108")
def _malakili_lof108():
    """LOF_108 Malakili — a 2-cost 1/4 Underworld unit with two passive clauses:

      1. "The first Creature unit you play each phase costs 1 resource less."
         = a ``StandingPlayDiscount`` (B31, Director Krennic JTLP_1) with the new
         ``applies_to="creature_unit"`` predicate.  "Each phase" is modelled with
         ``once_per_round`` — there is one ACTION phase per round, so the first
         Creature "each phase" and "each round" coincide for plays (documented in
         ``_card_matches_standing_discount``).

      2. "If a friendly Creature unit would deal damage to a friendly unit, prevent
         that damage." = the new ability-damage-prevention primitive
         ``PreventDamage(source_traits=("Creature",))`` — read at the single
         ``_apply_deal_damage`` chokepoint (combat is always attacker-vs-enemy, so
         friendly-fire can only be ability damage).

    Reprint sibling LOFP_7 aliased in reprints.py.
    """
    return [
        StandingPlayDiscount(amount=1, applies_to="creature_unit", once_per_round=True),
        PreventDamage(source_traits=("Creature",)),
    ]


# ── Group chancellor-palpatine:01 — Direct damage & removal (LOF reprint) ─────

def _vanee_move_experience(state, source_ci, target_id, event_ctx):
    """Vaneé LOF_82 first effect: ``target_id`` is the chosen friendly unit carrying
    an Experience token.  Defeat one Experience token on it (the defeat_experience
    helper, Infused Brawler LOF_156) and record ``event_ctx["prior_target_id"]`` so
    the follow-up GiveToken only fires "if you do" (the In Pursuit TWI_221
    requires_prior_target gate).  ``target_id`` None (the gate guaranteed a unit,
    but belt-and-braces) → nothing recorded → no give."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.engine.tokens import defeat_experience
    if defeat_experience(state, res[1]):
        event_ctx["prior_target_id"] = target_id
    return state


@card_ability("LOF", "82")
def _vanee():
    """LOF_82 — Vaneé (Unit, Imperial/Official/Sith, 2/4): "When Played/On Attack:
    You may defeat an Experience token on a friendly unit.  If you do, give an
    Experience token to a friendly unit."

    Two windows, so two optional triggers (``WhenPlayed`` + ``OnAttack``; the "you
    may"), each gated by the new ``CONTROLLER_HAS_UNIT_WITH_EXPERIENCE_TOKEN``
    condition so nothing is offered when there is no Experience token to defeat (the
    "don't offer a no-op" pattern).  Two dependent effects share the resolve_effects
    event_ctx: a CustomEffect.target picks a friendly unit with an Experience token
    (the new ``has_experience_token`` predicate), defeats one, and records the prior
    target; a ``GiveToken("Experience", …)`` then gives one to a friendly unit,
    gated by ``requires_prior_target`` so it fires only when a token was actually
    defeated ("If you do")."""
    effects = [
        CustomEffect(
            fn=_vanee_move_experience,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("has_experience_token",)),
        ),
        GiveToken("Experience",
                  TargetSpec(controller="friendly", kind="unit",
                             predicates=("requires_prior_target",))),
    ]
    gate = ConditionCheck(Condition.CONTROLLER_HAS_UNIT_WITH_EXPERIENCE_TOKEN)
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=list(effects),
                       optional=True, condition=gate),
        TriggerAbility(trigger=OnAttack(), effects=list(effects),
                       optional=True, condition=gate),
    ]


# ── Group chancellor-palpatine:06 — New primitive: opponent-chooses-target ─────

def _plagueis_protect(state, source_ci, target_id, event_ctx):
    """Tragedy of Plagueis LOF_43 first clause: ``target_id`` is the chosen friendly
    unit.  Mark it so it "can't be defeated by having no remaining HP" for this
    phase — a ``prevent_hp_defeat`` Modifier (duration ``this_phase``) read by
    ``actions._hp_lethal`` at every HP-defeat gate.  ``target_id`` None (no friendly
    unit) → no-op."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="prevent_hp_defeat",
        value={},
        duration="this_phase",
    ))
    return state


def _plagueis_opponent_defeat(state, source_ci, target_id, event_ctx):
    """Tragedy of Plagueis LOF_43 second clause: "An opponent chooses a unit they
    control. Defeat that unit."  A thin adapter onto the ``opponent_chooses_target``
    decision kind (SHD_246) with ``disposition="defeat"`` + ``units_only=True`` — a
    single mandatory stage: the opponent picks one of their units and it is defeated
    at once (no controller confirm).  Skipped when the opponent controls no unit."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(
        state, source_ci, disposition="defeat", units_only=True)
    return state


@card_ability("LOF", "43")
def _the_tragedy_of_plagueis():
    """LOF_43 — The Tragedy of Plagueis (Event, Learned, cost 5):

    "Choose a friendly unit. For this phase, it can't be defeated by having no
    remaining HP.  An opponent chooses a unit they control. Defeat that unit."

    Two effects sharing the standard resolve_effects sequence (the Vaneé LOF_82
    shape):
      1. A targeted CustomEffect (mandatory "Choose a friendly unit") applies the
         new ``prevent_hp_defeat`` this-phase marker — the mirror of the Protection
         marker (Chewbacca JTL_103) but for *HP* defeat instead of *ability* defeat.
      2. A CustomEffect adapter pushes the ``opponent_chooses_target`` decision with
         the new ``disposition="defeat"`` / ``units_only`` extension (a contained
         reuse of the existing SHD_246 decision kind — the opponent must give up one
         of their units).  When effect 2 pushes its decision our resolve_effects
         decision is buried and re-surfaces to auto-pop cleanly (the SOR_233 nested
         push guard)."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_plagueis_protect,
            target=TargetSpec(controller="friendly", kind="unit"),
        ),
        CustomEffect(fn=_plagueis_opponent_defeat),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:01`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("LOF", "11")
def _kit_fisto_lof_11():
    """LOF_11 — Kit Fisto (Leader, Force/Jedi/Republic, 1/6).

    * **Undeployed** "Action [1 resource, Exhaust]: If you attacked with a Jedi
      unit this phase, deal 2 damage to a unit."  A plain ``undeployed_only``
      ActivatedAbility gated by ``CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_
      PHASE("Jedi")`` — the source-INCLUSIVE attacked-with-trait atom (Darth Vader
      JTL_6), which resolves each attacker through ``find_instance`` so a Jedi that
      has since died still counts.  Its non-token narrowing is a no-op here: no
      token unit carries the Jedi trait, and the alternative "other"-flavoured atom
      would wrongly discount Kit Fisto's own attack.
    * **Deployed** "Saboteur" (keyword engine) + "This unit gets +1/+0 for each
      OTHER friendly Jedi unit" — a self-targeted ConstantAbility over the new
      ``other_controller_trait_units_Jedi`` scaling count.  A ConstantAbility on a
      Leader is only ever read by the ARENA scans, so it contributes nothing while
      he sits undeployed in the base zone; no ``deployed_only`` gate is needed.

    Epic Action (deploy at 5+ resources) is the standard deploy_threshold
    machinery — no registration."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            title="Deal 2 damage to a unit",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE,
                param="Jedi"),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0,
                               count="other_controller_trait_units_Jedi")],
        ),
    ]


def _rey_lof_12_discard_hand_draw(state, source_ci, target_id, event_ctx):
    """"You may discard your hand.  If you do, draw 2 cards" (Rey LOF_12, When
    Deployed) — the Black One SOR_147 shape: the whole hand goes to the discard and
    the draw follows in one indivisible step, so accepting can never leave the
    controller having paid without being paid.  An empty hand is still "discarding
    your hand", so the draw stands (the "if you do" is about accepting, not about
    holding cards)."""
    from swu.engine.state import Zone
    from swu.engine.actions import _draw_cards
    ps = state.player_by_id(source_ci.owner_id)
    while ps.hand:
        ci = ps.hand.pop(0)
        ci.zone = Zone.DISCARD
        ps.discard.append(ci)
    _draw_cards(state, ps, 2)
    return state


@card_ability("LOF", "12")
def _rey_lof_12():
    """LOF_12 — Rey (Leader, Force/Resistance, 6/8).

    * **Undeployed** "Action [Exhaust]: If you played a NON-UNIT Force card this
      phase, deal 1 damage to a unit."  Gated by the new
      ``CONTROLLER_PLAYED_NON_UNIT_TRAIT_CARD_THIS_PHASE("Force")`` atom — the
      card-type-narrowed sibling of Captain Phasma JTL_10's trait atom, over the
      non-unit slice recorded at the same CardPlayed chokepoint.
    * **Deployed** "When Deployed: You may discard your hand.  If you do, draw 2
      cards" — an optional WhenDeployed trigger over one atomic CustomEffect.

    Epic Action (deploy at 7+ resources) is the standard deploy_threshold
    machinery — no registration."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
            title="Deal 1 damage to a unit",
            undeployed_only=True,
            condition=ConditionCheck(
                Condition.CONTROLLER_PLAYED_NON_UNIT_TRAIT_CARD_THIS_PHASE,
                param="Force"),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_rey_lof_12_discard_hand_draw)],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "71")
def _grappling_guardian_lof_71():
    """LOF_71 — Grappling Guardian (Unit 3/9, Creature): "When Played: You may
    defeat a space unit with 6 or less remaining HP."

    An optional WhenPlayed DefeatUnit over the existing ``hp_remaining_max`` cap and
    ``arena="space"``; ``controller="any"`` because the printed text does not
    restrict the side (the controller aims it at an enemy).  With no eligible space
    unit the optional trigger auto-declines with no prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(
            controller="any", kind="unit", arena="space", hp_remaining_max=6))],
        optional=True,
    )


@card_ability("LOF", "91")
def _craving_power_lof_91():
    """LOF_91 — Craving Power (Upgrade, Innate, cost 5): "Attach to a friendly unit.
    When Played: Deal damage to an enemy unit equal to attached unit's power."

    "Attach to a friendly unit" is parsed by ``_upgrade_target_spec``, so only the
    When Played needs registering: a ``DealDamageEqualTo`` over the new
    ``attached_host_power`` count, which reads the host through the standard
    ``event_ctx["attached_to_id"]`` the upgrade-play site threads.  Effective power,
    so the upgrade's own stats and any other buff on the host are already counted by
    the time this resolves.  Mandatory (no "may"), and it fizzles harmlessly when
    the opponent controls no unit."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamageEqualTo(
            target=TargetSpec(controller="enemy", kind="unit"),
            count="attached_host_power")],
    )


@card_ability("LOF", "133")
def _purge_trooper_lof_133():
    """LOF_133 — Purge Trooper (Unit 4/2, Imperial/Trooper): "When Played: You may
    deal 2 damage to a Force unit."

    An optional WhenPlayed DealDamage narrowed by ``traits=("Force",)``;
    ``controller="any"`` as printed (a friendly Force unit is a legal, if unwise,
    target).  Effective traits, so a TraitGrant counts."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", traits=("Force",)))],
        optional=True,
    )


@card_ability("LOF", "134")
def _heavy_missile_gunship_lof_134():
    """LOF_134 — Heavy Missile Gunship (Unit 4/3, Droid/Separatist/Transport/
    Vehicle): "Action [Exhaust]: Deal 2 damage to a ground unit."

    A plain exhaust-cost ActivatedAbility; ``arena="ground"`` is the only narrowing
    (the gunship itself is a ground unit and is a legal — self-harming — target, as
    printed, which the bot's self-harm guard already refuses)."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", arena="ground"))],
        title="Deal 2 damage to a ground unit",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:02`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("LOF", "141")
def _death_field_lof_141():
    """LOF_141 — Death Field (Event, Force, cost 4): "Deal 2 damage to each
    non-Vehicle enemy unit.  If you control a Force unit, draw a card."

    Two effects in one EventAbility: an ``EACH_ENEMY`` mass DealDamage carrying the
    existing ``non_vehicle`` predicate (the EACH_* expansion preserves per-candidate
    filters), then a ConditionalEffect on ``CONTROLLER_HAS_TRAIT_UNIT("Force")`` for
    the draw.  Ordering matters and is as printed: the sweep can defeat the
    controller's own last Force unit only if it is an *enemy* unit, which it cannot
    be, so the condition reads the same board either way."""
    return EventAbility(effects=[
        DealDamage(2, TargetSpec(
            controller="enemy", kind="unit",
            predicates=("non_vehicle",), fixed=EACH_ENEMY)),
        ConditionalEffect(
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT,
                                     param="Force"),
            if_true=(DrawCards(1),),
            if_false=(),
        ),
    ])


@card_ability("LOF", "142")
def _adi_gallia_lof_142():
    """LOF_142 — Adi Gallia (Unit 2/4, Force/Jedi/Republic): "When an opponent plays
    an event: Deal 1 damage to that player's base."

    The Saw Gerrera SOR_153 shape exactly — a ``WhenOpponentPlaysCard(card_type=
    "event")`` observer plus DealDamage to the enemy base.  "That player's base" is
    the single opponent's in two-player, which is what ``controller="enemy"``
    resolves to."""
    return TriggerAbility(
        trigger=WhenOpponentPlaysCard(card_type="event"),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="base"))],
    )


@card_ability("LOF", "144")
def _jedi_starfighter_lof_144():
    """LOF_144 — Jedi Starfighter (Unit 1/4, Fighter/Jedi/Republic/Vehicle): "On
    Attack: You may deal 1 damage to a space unit."

    An optional OnAttack DealDamage narrowed to ``arena="space"``; the starfighter
    itself is in space and is a legal (self-harming) target, as printed."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(
            controller="any", kind="unit", arena="space"))],
        optional=True,
    )


@card_ability("LOF", "145")
def _jedi_knight_lof_145():
    """LOF_145 — Jedi Knight (Unit 3/3, Force/Jedi): "When Played: If you have the
    initiative, deal 2 damage to an enemy ground unit."

    A MANDATORY WhenPlayed whose collection is gated by ``TriggerAbility.condition``
    = ``CONTROLLER_HAS_INITIATIVE`` — an "If …" clause with no "may", so without the
    initiative the trigger is never collected and never prompts (the LOF_163
    precedent), rather than being offered and fizzling."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(
            controller="enemy", kind="unit", arena="ground"))],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


def _kit_fistos_aethersprite_lof_147_defeat(state, source_ci, target_id, event_ctx):
    """"Defeat any number of upgrades on a unit" (LOF_147) — the host unit is the
    chosen target; its non-token upgrades become the whitelist for a
    ``select_token`` decision in the new DEFEAT mode, with "any number" expressed
    the Kazuda Xiono JTL_18 way (``max_targets`` = the size of the pool, and Finish
    ends it early — including at zero).

    Per the engine-wide ``kind="upgrade"`` convention a Shield or Experience token
    is NOT an "upgrade" a defeat effect can name, so tokens are excluded from both
    the whitelist and the ``has_non_token_upgrade`` gate on the unit choice."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    from swu.cards.models import Upgrade, TokenUpgrade
    ids = [u.instance_id for u in res[1].attached_upgrades
           if isinstance(u.card_def, Upgrade)
           and not isinstance(u.card_def, TokenUpgrade)]
    if not ids:
        return state
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type=None, max_targets=len(ids),
                      kind="upgrade", restrict_ids=ids, defeat=True)
    return state


@card_ability("LOF", "147")
def _kit_fistos_aethersprite_lof_147():
    """LOF_147 — Kit Fisto's Aethersprite (Unit 4/5, Fighter/Jedi/Republic/Vehicle,
    Saboteur): "When Played: You may defeat any number of upgrades on a unit."

    Saboteur is the keyword engine.  The "you may" is the optional trigger; the unit
    choice is a targeted CustomEffect filtered by the new ``has_non_token_upgrade``
    predicate (so a bare unit — or one carrying only a Shield — is never offered and
    the trigger auto-declines when nobody is upgraded), and the "any number" is the
    ``select_token`` loop in DEFEAT mode over just that unit's upgrades."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_kit_fistos_aethersprite_lof_147_defeat,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("has_non_token_upgrade",)))],
        optional=True,
    )


@card_ability("LOF", "155")
def _drk_1_probe_droid_lof_155():
    """LOF_155 — DRK-1 Probe Droid (Unit 2/3, Droid): "When Played: You may defeat a
    non-unique upgrade."

    An optional WhenPlayed DefeatUnit over ``kind="upgrade"`` (which already means a
    real, non-token upgrade attached to a unit) plus the existing ``non_unique``
    predicate; either side's, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DefeatUnit(TargetSpec(
            controller="any", kind="upgrade", predicates=("non_unique",)))],
        optional=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:03`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("LOF", "158")
def _hyena_bomber_lof_158():
    """LOF_158 — Hyena Bomber (Unit 2/2, Droid/Fighter/Separatist/Vehicle): "When
    Played: If you control another Aggression unit, you may deal 2 damage to a
    ground unit."

    The "If you control another …" clause gates trigger COLLECTION via the existing
    ``CONTROLLER_HAS_OTHER_ASPECT_UNIT`` atom (self-excluding, so the bomber cannot
    satisfy its own condition), and the "you may" is the optional trigger."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(2, TargetSpec(
            controller="any", kind="unit", arena="ground"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Aggression"),
    )


def _saesee_tiin_lof_167_damage(state, source_ci, target_id, event_ctx):
    """"Deal 1 damage to each of up to 3 units" — the ``select_damage`` decision
    (IG-2000 JTL_140) verbatim.  Its resolve deals every point after the pop, which
    is exactly the card's printed "all damage … is dealt simultaneously"."""
    from swu.engine.actions import push_select_damage
    push_select_damage(state, source_ci, amount_each=1, max_targets=3)
    return state


@card_ability("LOF", "167")
def _saesee_tiin_lof_167():
    """LOF_167 — Saesee Tiin (Unit 4/6, Force/Jedi/Republic): "When Played: If you
    have the initiative, deal 1 damage to each of up to 3 units."

    A MANDATORY WhenPlayed gated on ``CONTROLLER_HAS_INITIATIVE`` at COLLECTION (an
    "If …" with no "may" — the Jedi Knight LOF_145 precedent, so without the
    initiative it never prompts), whose one effect is the select-up-to-3 damage
    loop."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_saesee_tiin_lof_167_damage)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE),
    )


@card_ability("LOF", "170")
def _bendu_lof_170():
    """LOF_170 — Bendu (Unit 10/10, Creature/Force): "On Attack: Deal 3 damage to
    each other unit."

    A fixed ``EACH_IN_PLAY`` DealDamage narrowed by ``not_self`` — "each OTHER unit"
    means both players' arenas, Bendu excepted.  The EACH_* expansion resolves every
    match inline with no prompt, so the whole sweep lands as one instruction (the
    printed "all damage … is dealt simultaneously")."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(3, TargetSpec(
            controller="any", kind="unit",
            predicates=("not_self",), fixed=EACH_IN_PLAY))],
    )


def _heavy_blaster_cannon_lof_171_damage(state, source_ci, target_id, event_ctx):
    """Three SEPARATE 1-damage instances onto the one chosen unit (LOF_171).

    The card's printed rules note is the whole point: a Shield eats only the FIRST
    instance, so the damage must NOT be collapsed into a single 3.  Each call goes
    through ``_apply_deal_damage`` → ``_deal_damage_with_shield`` independently; once
    the unit is defeated ``find_instance`` returns None and the rest are no-ops."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    name = source_ci.card_def.display_name
    for _ in range(3):
        _apply_deal_damage(state, target_id, 1, source_name=name,
                           dealer_id=source_ci.owner_id)
    return state


@card_ability("LOF", "171")
def _heavy_blaster_cannon_lof_171():
    """LOF_171 — Heavy Blaster Cannon (Upgrade, Item/Weapon, cost 4): "Attach to a
    non-Vehicle unit.  When Played: You may deal 1 damage to a ground unit.  Then,
    deal 1 damage to the same unit.  Then, deal 1 damage to the same unit."

    The attach restriction is parsed by ``_upgrade_target_spec``.  "The same unit"
    three times over is ONE targeted CustomEffect dealing three separate instances —
    the card's rules note turns on their separateness (a Shield stops only the
    first)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_heavy_blaster_cannon_lof_171_damage,
            target=TargetSpec(controller="any", kind="unit", arena="ground"))],
        optional=True,
    )


def _sorcerous_blast_lof_172_fn(state, source_ci, target_id, event_ctx):
    """Spend the Force token, then deal 3 to the chosen unit (LOF_172).

    Cost and payoff live in ONE CustomEffect (the "If you do" binding), and
    ``spend_force_token`` is the single chokepoint every "use the Force" routes
    through, so The Father LOF_260 / Yoda LOF_101's observers see the spend."""
    if target_id is None:
        return state
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 3,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id)
    return state


@card_ability("LOF", "172")
def _sorcerous_blast_lof_172():
    """LOF_172 — Sorcerous Blast (Event, Force, cost 1): "Use the Force (lose your
    Force token).  If you do, deal 3 damage to a unit."

    An EventAbility has no ``condition`` field and a ConditionalEffect cannot carry a
    targeted sub-effect, so the "If you do" is the new BOARD-gate predicate
    ``controller_has_force_token`` (the Face Off JTL_178 shape): with no Force token
    there are no candidates and the event fizzles unprompted."""
    return EventAbility(effects=[CustomEffect(
        fn=_sorcerous_blast_lof_172_fn,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("controller_has_force_token",)))])


def _lightsaber_throw_lof_176_fn(state, source_ci, target_id, event_ctx):
    """Discard a Lightsaber card, then deal 4 and draw (LOF_176) — one CustomEffect
    so the cost and its payoff stay atomic.

    The card to pitch is auto-picked (the first Lightsaber in hand — the K-2SO
    SOR_145 first-card-discard convention); the target gate guarantees one exists."""
    if target_id is None:
        return state
    from swu.engine.state import Zone
    from swu.engine.actions import (note_hand_or_deck_discard, record_hand_discard,
                                    _draw_cards)
    ps = state.player_by_id(source_ci.owner_id)
    pitch = next((h for h in ps.hand
                  if "Lightsaber" in (getattr(h.card_def, "traits", None) or ())),
                 None)
    if pitch is None:
        return state
    ps.hand.remove(pitch)
    pitch.zone = Zone.DISCARD
    ps.discard.append(pitch)
    note_hand_or_deck_discard(state, pitch)
    record_hand_discard(state, ps.player_id)
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 4,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id)
    _draw_cards(state, ps, 1)
    return state


@card_ability("LOF", "176")
def _lightsaber_throw_lof_176():
    """LOF_176 — Lightsaber Throw (Event, Tactic, cost 2): "Discard a Lightsaber card
    from your hand.  If you do, deal 4 damage to a ground unit and draw a card."

    The "If you do" is the new BOARD-gate predicate
    ``controller_has_trait_card_in_hand:Lightsaber`` (the LOF_172 shape, with the
    trait riding in the predicate string), so with no Lightsaber in hand the event
    fizzles unprompted rather than offering a target it cannot pay for."""
    return EventAbility(effects=[CustomEffect(
        fn=_lightsaber_throw_lof_176_fn,
        target=TargetSpec(
            controller="any", kind="unit", arena="ground",
            predicates=("controller_has_trait_card_in_hand:Lightsaber",)))])


def _time_of_crisis_lof_177_fn(state, source_ci, target_id, event_ctx):
    """"Each player chooses a unit they control.  Deal 3 damage to each unit not
    chosen this way" (LOF_177) — the ``each_player_defeats`` TWI_238 walk in its new
    INVERSE ``spare_then_damage`` disposition."""
    from swu.engine.actions import push_each_player_defeats
    push_each_player_defeats(state, source_ci,
                             disposition="spare_then_damage", damage_amount=3)
    return state


@card_ability("LOF", "177")
def _time_of_crisis_lof_177():
    """LOF_177 — Time of Crisis (Event, Disaster, cost 4): "Each player chooses a
    unit they control.  Deal 3 damage to each unit not chosen this way."

    A symmetric per-stage decider-shift (the controller picks first, then the
    opponent), then one settle that damages every unspared unit — which is the
    printed "all damage … is dealt simultaneously".  A player with no unit is
    skipped and simply spares nothing."""
    return EventAbility(effects=[CustomEffect(fn=_time_of_crisis_lof_177_fn)])


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:04`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _the_legacy_run_lof_213_fn(state, source_ci, target_id, event_ctx):
    """"Deal 6 damage divided as you choose among enemy units" (LOF_213) — the
    ``distribute_damage`` pool (Palpatine SOR_135) narrowed to the enemy side.  Its
    settle deals every point at once, which is the printed "all damage … is dealt
    simultaneously"; the pool is a fixed 6 (no ``up_to``), and the card's rules note
    that overkill assignment is legal is the pool's own behaviour."""
    from swu.engine.actions import push_distribute_damage
    push_distribute_damage(state, source_ci, 6, target_controller="enemy")
    return state


@card_ability("LOF", "213")
def _the_legacy_run_lof_213():
    """LOF_213 — The Legacy Run (Unit 3/3, Republic/Transport/Vehicle): "When
    Defeated: Deal 6 damage divided as you choose among enemy units."

    "Enemy" is measured from the dying unit's controller, which is what
    ``target_controller="enemy"`` resolves to for a WhenDefeated resolving from the
    defeated instance."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_the_legacy_run_lof_213_fn)],
    )


def _consumed_by_the_dark_side_lof_239_fn(state, source_ci, target_id, event_ctx):
    """Two Experience tokens onto the chosen unit, THEN 2 damage to it (LOF_239).

    Both clauses act on "a unit" / "it", so they are ONE targeted CustomEffect (two
    targeted effects would prompt twice and could split across units — the Kylo
    SHD_141 rule).  Order is as printed: the Experience lands first, so its +1/+1
    each is already counted when the damage is checked for lethality."""
    if target_id is None:
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    ps, ci = res
    from swu.engine.tokens import attach_token
    attach_token(state, ps, ci, "Experience")
    attach_token(state, ps, ci, "Experience")
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, target_id, 2,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id)
    return state


@card_ability("LOF", "239")
def _consumed_by_the_dark_side_lof_239():
    """LOF_239 — Consumed by the Dark Side (Event, Force, cost 2): "Give 2
    Experience tokens to a unit, then deal 2 damage to it."

    Either side's unit, as printed — a boon with a sting for a friendly unit, a
    (usually) net-negative gift for an enemy one."""
    return EventAbility(effects=[CustomEffect(
        fn=_consumed_by_the_dark_side_lof_239_fn,
        target=TargetSpec(controller="any", kind="unit"))])


@card_ability("LOF", "259")
def _ravening_gundark_lof_259():
    """LOF_259 — Ravening Gundark (Unit 5/4, Creature): "When Played: Deal 1 damage
    to a ground unit."

    A MANDATORY WhenPlayed DealDamage narrowed to the ground arena; the Gundark
    itself is a legal (self-harming) target, as printed."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(
            controller="any", kind="unit", arena="ground"))],
    )


def _the_father_lof_260_fn(state, source_ci, target_id, event_ctx):
    """Deal 1 to this unit, then create the controller's Force token (LOF_260).

    ONE CustomEffect so the self-damage and its payoff stay atomic ("If you do").
    The damage can defeat him; the token is still created, since the printed
    sequence pays first and the "if you do" refers to the damage having been dealt."""
    from swu.abilities.resolver import _apply_deal_damage
    _apply_deal_damage(state, source_ci.instance_id, 1,
                       source_name=source_ci.card_def.display_name,
                       dealer_id=source_ci.owner_id)
    state.player_by_id(source_ci.owner_id).has_force_token = True
    return state


@card_ability("LOF", "260")
def _the_father_lof_260():
    """LOF_260 — The Father (Unit 5/10, Creature/Force): "When you use the Force:
    You may deal 1 damage to this unit.  If you do, the Force is with you."

    The existing ``WhenYouUseForce`` observer (Yoda LOF_101), which fires from the
    settle-point drain of ``game_memory.force_uses`` — the card's own rules note
    ("triggers when you use the Force but only resolves after any current ability is
    finished resolving") is exactly that drain point.  Creating a token is not
    *using* one, so the observer cannot re-arm itself."""
    return TriggerAbility(
        trigger=WhenYouUseForce(),
        effects=[CustomEffect(fn=_the_father_lof_260_fn)],
        optional=True,
    )


@card_ability("LOF", "264")
def _its_worse_lof_264():
    """LOF_264 — It's Worse (Event, Trick, cost 7): "Defeat a non-leader unit."

    A plain targeted ``DefeatUnit`` over the existing ``non_leader`` predicate;
    ``controller="any"`` as printed."""
    return EventAbility(effects=[DefeatUnit(TargetSpec(
        controller="any", kind="unit", predicates=("non_leader",)))])


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:05`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

def _kylo_ren_lof_1_discard(state, source_ci, target_id, event_ctx):
    """"Discard a card from your hand.  If you discarded an upgrade this way, draw a
    card" (LOF_1 undeployed).

    Cost and payoff in ONE CustomEffect.  The card pitched is auto-picked (the first
    in hand — the K-2SO SOR_145 first-card-discard convention); the collection gate
    (``CONTROLLER_HAND_SIZE_MIN`` 1) guarantees one exists."""
    from swu.cards.models import Upgrade
    from swu.engine.state import Zone
    from swu.engine.actions import (note_hand_or_deck_discard, record_hand_discard,
                                    _draw_cards)
    ps = state.player_by_id(source_ci.owner_id)
    if not ps.hand:
        return state
    pitched = ps.hand.pop(0)
    pitched.zone = Zone.DISCARD
    ps.discard.append(pitched)
    note_hand_or_deck_discard(state, pitched)
    record_hand_discard(state, ps.player_id)
    if isinstance(pitched.card_def, Upgrade):
        _draw_cards(state, ps, 1)
    return state


def _kylo_ren_lof_1_recur_upgrades(state, source_ci, target_id, event_ctx):
    """"Play any number of upgrades from your discard pile on this unit (one at a
    time, paying their costs)" (LOF_1 When Deployed) — the play_upgrade_from_hand
    decision in its new discard-only / host-pinned / repeating mode."""
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(
        state, source_ci, free=False, from_discard_only=True,
        host_id=source_ci.instance_id, repeat=True)
    return state


@card_ability("LOF", "1")
def _kylo_ren_lof_1():
    """LOF_1 — Kylo Ren (Leader, First Order/Force, 5/5, Sentinel).

    * **Undeployed** "Action [Exhaust]: Discard a card from your hand.  If you
      discarded an upgrade this way, draw a card."
    * **Deployed** "When Deployed: Play any number of upgrades from your discard pile
      on this unit (one at a time, paying their costs)."  Sentinel is the keyword
      engine.

    ⚠️ LOF_1 is ALSO the Experience token upgrade's (set, number), so only spec kinds
    a token can never reach are registered: ``ActivatedAbility(undeployed_only=True)``
    (the arena scans require a Leader card_def) and ``TriggerAbility(WhenDeployed())``
    (matched by instance id against a LeaderDeployed event).  A ConstantAbility, a
    passive marker or a GrantedAbility would leak onto every Experience token."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_kylo_ren_lof_1_discard)],
            title="Discard a card; draw if it was an upgrade",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1),
        ),
        TriggerAbility(
            trigger=WhenDeployed(),
            effects=[CustomEffect(fn=_kylo_ren_lof_1_recur_upgrades)],
            deployed_only=True,
        ),
    ]


def _old_daka_lof_36_fn(state, source_ci, target_id, event_ctx):
    """Defeat the chosen friendly Night unit, then offer to play it back out of the
    discard for free (LOF_36).

    ONE targeted CustomEffect so "that unit" is unambiguous: the defeat and the
    free replay are bound together, and the instance id survives the trip to the
    discard, so it is exactly the whitelist ``push_play_from_hand`` needs.
    DOCUMENTED SIMPLIFICATION: ``play_from_hand`` has no decline, so the SECOND
    "you may" collapses to mandatory; the first is the optional trigger."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _apply_defeat_unit
    _apply_defeat_unit(state, target_id)
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, from_discard=True, free=True,
                        eligible_ids=frozenset({target_id}))
    return state


@card_ability("LOF", "36")
def _old_daka_lof_36():
    """LOF_36 — Old Daka (Unit 6/6, Force/Night): "When Played: You may defeat a
    friendly Night unit not named Old Daka.  Then, you may play that unit from your
    discard pile for free."

    "Not named Old Daka" is the ``not_self`` predicate: Old Daka is unique, so the
    only friendly Old Daka that could be in play is this one."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(
            fn=_old_daka_lof_36_fn,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Night",), predicates=("not_self",)))],
        optional=True,
    )


def _force_unit_search(state, source_ci, target_id, event_ctx):
    """"Search the top 5 cards of your deck for a Force unit, reveal it, and draw
    it" — the shared body of Owen Lars LOF_57 and Dagoyan Master LOF_115's payoff."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search

    def _eligible(cd) -> bool:
        return (isinstance(cd, Unit)
                and "Force" in (getattr(cd, "traits", None) or ()))

    push_deck_search(state, source_ci, count=1, eligible=_eligible,
                     up_to=False, window=5)
    return state


@card_ability("LOF", "57")
def _owen_lars_lof_57():
    """LOF_57 — Owen Lars (Unit 0/3, Fringe, Restore 2): "When Defeated: Search the
    top 5 cards of your deck for a Force unit, reveal it, and draw it."

    Restore is the keyword engine.  The search is the long-standing ``deck_search``
    decision (Grand Moff Tarkin SOR_84), whose default ``rest_disposition="bottom"``
    IS the printed parenthetical."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_force_unit_search)],
    )


def _watto_lof_65_fn(state, source_ci, target_id, event_ctx):
    """"An opponent chooses one: [You give an Experience token to a friendly unit] /
    [You draw a card]" (LOF_65) — the ``modal`` decision with its new ``decider_id``
    shift, so the MODE is picked by the opponent while both modes still resolve for
    (and target for) the controller."""
    from swu.engine.actions import push_modal
    opponent_id = next(p.player_id for p in state.players
                       if p.player_id != source_ci.owner_id)
    push_modal(state, source_ci, ["give_experience_friendly_unit", "draw_card"],
               decider_id=opponent_id)
    return state


@card_ability("LOF", "65")
def _watto_lof_65():
    """LOF_65 — Watto (Unit 1/6, Fringe): "On Attack: An opponent chooses one: You
    give an Experience token to a friendly unit.  You draw a card."

    Both modes benefit the controller, so the opponent is picking the lesser evil —
    a real choice, not one that collapses to an optimal default.  ``draw_card``
    targets nothing and is therefore fungible (the controller's base is its
    throwaway proxy); ``give_experience_friendly_unit`` is not, so the controller
    still picks which of their units takes the token."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_watto_lof_65_fn)],
    )


def _luthen_rael_lof_68_fn(state, source_ci, target_id, event_ctx):
    """"Search the top 5 cards of your deck for an Item upgrade, reveal it, and draw
    it" (LOF_68) — ``deck_search`` narrowed to an Upgrade card carrying Item."""
    from swu.cards.models import Upgrade
    from swu.engine.actions import push_deck_search

    def _eligible(cd) -> bool:
        return (isinstance(cd, Upgrade)
                and "Item" in (getattr(cd, "traits", None) or ()))

    push_deck_search(state, source_ci, count=1, eligible=_eligible,
                     up_to=False, window=5)
    return state


@card_ability("LOF", "68")
def _luthen_rael_lof_68():
    """LOF_68 — Luthen Rael (Unit 4/5, Rebel): "On Attack: Search the top 5 cards of
    your deck for an Item upgrade, reveal it, and draw it." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_luthen_rael_lof_68_fn)],
    )


@card_ability("LOF", "83")
def _captain_enoch_lof_83():
    """LOF_83 — Captain Enoch (Unit 1/5, Imperial/Trooper): "This unit gets +1/+0 for
    each Trooper unit in your discard pile."

    A SELF ConstantAbility over the new ``controller_discard_trait_units_<Trait>``
    StatBonus count — the discard-pile sibling of Squad Support TWI_122's in-play
    count, read passively by ``compute_power`` (so it tracks the pile with no
    trigger)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=0,
                           count="controller_discard_trait_units_Trooper")],
    )


def _dagoyan_master_lof_115_fn(state, source_ci, target_id, event_ctx):
    """Spend the Force token, then run the top-5 Force-unit search (LOF_115) — cost
    and payoff in ONE CustomEffect ("If you do")."""
    from swu.engine.actions import spend_force_token
    if not spend_force_token(state, state.player_by_id(source_ci.owner_id)):
        return state
    return _force_unit_search(state, source_ci, target_id, event_ctx)


@card_ability("LOF", "115")
def _dagoyan_master_lof_115():
    """LOF_115 — Dagoyan Master (Unit 5/5, Force): "When Played/When Defeated: You may
    use the Force (lose your Force token).  If you do, search the top 5 cards of your
    deck for a Force unit, reveal it, and draw it."

    Two independent triggers over one effect (the printed slash is two windows, not a
    choice).  Each is optional — the "you may" — and gated on
    ``CONTROLLER_HAS_FORCE_TOKEN`` at collection, so a tokenless controller is never
    offered a use it cannot pay for (the Luke Skywalker LOF_249 shape)."""
    gate = ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN)
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[CustomEffect(fn=_dagoyan_master_lof_115_fn)],
            optional=True, condition=gate,
        ),
        TriggerAbility(
            trigger=WhenDefeated(),
            effects=[CustomEffect(fn=_dagoyan_master_lof_115_fn)],
            optional=True, condition=gate,
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:06`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

def _sifo_dyas_lof_117_fn(state, source_ci, target_id, event_ctx):
    """"Search the top 8 of your deck for any number of Clone units with combined
    cost 4 or less and discard them.  For this phase, you may play those cards from
    your discard pile for free" (LOF_117).

    Three existing deck_search knobs, newly combined: ``up_to=True`` + a
    ``max_select`` equal to the whole window is "any number" (the Kazuda JTL_18
    idiom), ``budget=4`` is the combined-COST cap (the Darth Vader SOR_87 ctx key,
    now reachable from a plain search), and ``disposition="discard_free_replay"`` is
    the Cobb Vanth SHD_115 discard-and-flag-for-a-free-replay payoff."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search

    def _eligible(cd) -> bool:
        return (isinstance(cd, Unit)
                and "Clone" in (getattr(cd, "traits", None) or ()))

    push_deck_search(state, source_ci, count=8, eligible=_eligible, up_to=True,
                     window=8, budget=4, disposition="discard_free_replay")
    return state


@card_ability("LOF", "117")
def _sifo_dyas_lof_117():
    """LOF_117 — Sifo-Dyas (Unit 4/4, Force/Jedi/Republic): "When Defeated: Search
    the top 8 cards of your deck for any number of Clone units with combined cost 4
    or less and discard them. … For this phase, you may play those cards from your
    discard pile for free." """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_sifo_dyas_lof_117_fn)],
    )


def _the_purrgil_king_lof_121_fn(state, source_ci, target_id, event_ctx):
    """"Draw a card for each friendly unit with 7 or more remaining HP" (LOF_121) —
    a conditional-magnitude CustomEffect (the Zeb LAW_45 shape).  Remaining HP is
    effective HP less damage, so a buff or an Experience token counts; the King
    himself (12 HP) is a friendly unit and counts as printed."""
    from swu.engine.actions import compute_hp, _draw_cards
    res = state.find_instance(source_ci.instance_id)
    ps = res[0] if res is not None else state.player_by_id(source_ci.owner_id)
    n = sum(1 for u in ps.ground_arena + ps.space_arena
            if compute_hp(state, u) - u.damage >= 7)
    if n:
        _draw_cards(state, state.player_by_id(source_ci.owner_id), n)
    return state


@card_ability("LOF", "121")
def _the_purrgil_king_lof_121():
    """LOF_121 — The Purrgil King (Unit 4/12, Creature, Restore 4): "When Played:
    Draw a card for each friendly unit with 7 or more remaining HP."  Restore is the
    keyword engine."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_the_purrgil_king_lof_121_fn)],
    )


def _pillio_star_compass_lof_122_fn(state, source_ci, target_id, event_ctx):
    """"Search the top 3 cards of your deck for a unit, reveal it, and draw it"
    (LOF_122) — ``deck_search`` at window 3 over any Unit card."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1,
                     eligible=lambda cd: isinstance(cd, Unit),
                     up_to=False, window=3)
    return state


@card_ability("LOF", "122")
def _pillio_star_compass_lof_122():
    """LOF_122 — Pillio Star Compass (Upgrade, Item, cost 2): "Attach to a
    non-Vehicle unit.  When Played: Search the top 3 cards of your deck for a unit,
    reveal it, and draw it."

    The attach restriction is parsed by ``_upgrade_target_spec``; only the search
    needs registering."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_pillio_star_compass_lof_122_fn)],
    )


def _the_burden_of_masters_lof_125_fn(state, source_ci, target_id, event_ctx):
    """"Put a Force unit from your discard pile on the bottom of your deck.  If you
    do, play a unit from your hand and give 2 Experience tokens to it" (LOF_125).

    ``bottom_from_discard`` narrowed to the controller's own Force units, with the
    play as its new ``then_play_from_hand`` settle rider — so choosing nothing plays
    nothing ("If you do").  The 2 Experience ride on the play's own
    ``then_select_token``, which fires only once the unit has really entered play
    (the Lando JTL_3 ordering rule: it cannot be a second effect)."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_bottom_from_discard

    def _eligible(cd) -> bool:
        return (isinstance(cd, Unit)
                and "Force" in (getattr(cd, "traits", None) or ()))

    push_bottom_from_discard(
        state, source_ci, count=1, own_only=True, eligible=_eligible,
        then_play_from_hand={
            "then_select_token": {"token_type": "Experience", "token_count": 2,
                                  "max_targets": 1, "restrict_played": True},
        })
    return state


@card_ability("LOF", "125")
def _the_burden_of_masters_lof_125():
    """LOF_125 — The Burden of Masters (Event, Learned, cost 1): "Put a Force unit
    from your discard pile on the bottom of your deck.  If you do, play a unit from
    your hand and give 2 Experience tokens to it."

    The unit is played at its full cost ("Abilities that let you play a card require
    you to pay that card's cost unless specified otherwise")."""
    return EventAbility(effects=[
        CustomEffect(fn=_the_burden_of_masters_lof_125_fn)])


@card_ability("LOF", "139")
def _battle_fury_lof_139():
    """LOF_139 — Battle Fury (Upgrade, Innate, cost 2): "Attached unit gains: 'On
    Attack: Discard a card from your hand.'"

    A ``GrantedAbility`` wrapping the trigger, so it matches and resolves with the
    HOST as source (Armed to the Teeth SHD_175).  Mandatory, and a first-card
    discard (the K-2SO SOR_145 convention) — an empty hand simply discards
    nothing."""
    return GrantedAbility(TriggerAbility(
        trigger=OnAttack(),
        effects=[DiscardFromHand(1)],
    ))


def _ki_adi_mundi_lof_146_fn(state, source_ci, target_id, event_ctx):
    """Spend the Force token, then draw 2 (LOF_146) — one CustomEffect binding the
    cost to its payoff."""
    from swu.engine.actions import spend_force_token, _draw_cards
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    _draw_cards(state, ps, 2)
    return state


@card_ability("LOF", "146")
def _ki_adi_mundi_lof_146():
    """LOF_146 — Ki-Adi-Mundi (Unit 4/4, Force/Jedi/Republic): "When Played: You may
    use the Force (lose your Force token).  If you do, draw 2 cards."

    An optional WhenPlayed gated on ``CONTROLLER_HAS_FORCE_TOKEN`` at collection, so
    a tokenless controller is never prompted (the Dagoyan Master LOF_115 shape)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_ki_adi_mundi_lof_146_fn)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _do_or_do_not_lof_175_fn(state, source_ci, target_id, event_ctx):
    """"You may use the Force.  If you do, draw 2 cards.  If you do not, draw a
    card" (LOF_175) — the ``use_force`` decision with the new ``"draw:N"`` payoff
    and the same string-encoded form as its "if you don't" clause.

    ``decline_penalty`` is really just the if-you-don't clause, benefit or not: with
    no Force token no decision is pushed and it lands inline, which is exactly the
    printed reading."""
    from swu.engine.actions import push_use_force
    push_use_force(state, source_ci, payoff="draw:2", decline_penalty="draw:1")
    return state


@card_ability("LOF", "175")
def _do_or_do_not_lof_175():
    """LOF_175 — Do or Do Not (Event, Force, cost 2): "You may use the Force (lose
    your Force token).  If you do, draw 2 cards.  If you do not, draw a card." """
    return EventAbility(effects=[CustomEffect(fn=_do_or_do_not_lof_175_fn)])


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:07`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

def _second_sister_lof_184_fn(state, source_ci, target_id, event_ctx):
    """"Discard 2 cards from your deck.  For each Force card discarded this way,
    ready a resource" (LOF_184) — cost and payoff in ONE CustomEffect.

    A resource is fungible (the K-2SO SOR_145 convention), so the ones readied are
    auto-picked.  A short deck simply mills fewer cards, and only cards actually
    discarded this way are counted."""
    from swu.engine.state import Zone
    from swu.engine.actions import note_hand_or_deck_discard
    ps = state.player_by_id(source_ci.owner_id)
    force_count = 0
    for _ in range(2):
        if not ps.deck:
            break
        milled = ps.deck.pop(0)
        milled.zone = Zone.DISCARD
        milled.face_down = False
        ps.discard.append(milled)
        note_hand_or_deck_discard(state, milled)
        if "Force" in (getattr(milled.card_def, "traits", None) or ()):
            force_count += 1
    for r in ps.resources:
        if force_count <= 0:
            break
        if r.exhausted:
            r.exhausted = False
            force_count -= 1
    return state


@card_ability("LOF", "184")
def _second_sister_lof_184():
    """LOF_184 — Second Sister (Unit 3/6, Force/Imperial/Inquisitor): "On Attack: You
    may discard 2 cards from your deck.  For each Force card discarded this way,
    ready a resource." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_second_sister_lof_184_fn)],
        optional=True,
    )


def _as_i_have_foreseen_lof_188_fn(state, source_ci, target_id, event_ctx):
    """"Look at the top card of your deck.  You may use the Force (lose your Force
    token).  If you do, play that card.  It costs 4 resources less" (LOF_188).

    ``peek_top`` in its ``may_play`` mode (You're My Only Hope SOR_246) with the new
    ``force_cost`` rider: the Force token is the price of the PLAY option only, so
    KeepTopCard still costs nothing.  With no Force token the play could never be
    paid for, so the card collapses to its "look" clause — no decision, no state
    change (a documented simplification: a look nobody can act on is unobservable)."""
    from swu.engine.actions import push_peek_top
    if not getattr(state.player_by_id(source_ci.owner_id), "has_force_token", False):
        return state
    push_peek_top(state, source_ci, mode="may_play", cost_reduction=4,
                  force_cost=True)
    return state


@card_ability("LOF", "188")
def _as_i_have_foreseen_lof_188():
    """LOF_188 — As I Have Foreseen (Event, Force, cost 1)."""
    return EventAbility(effects=[
        CustomEffect(fn=_as_i_have_foreseen_lof_188_fn)])


def _zuckuss_lof_204_fn(state, source_ci, target_id, event_ctx):
    """"Name a card, then discard the top card of the defending player's deck.  If a
    card with that name is discarded, this unit gets +4/+0 for this attack"
    (LOF_204) — ``name_a_card`` with the new ``mill_defender_match_buff`` rider.

    The nameable set is the opponent's PUBLIC card names (the Galen Erso P25_31
    option list): naming is blind in paper, and offering the opponent's hidden deck
    would leak information, so this is the information-honest reading."""
    from swu.engine.actions import push_name_a_card
    push_name_a_card(state, source_ci,
                     then_payoff="mill_defender_match_buff:4")
    return state


@card_ability("LOF", "204")
def _zuckuss_lof_204():
    """LOF_204 — Zuckuss (Unit 4/7, Bounty Hunter/Force)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[CustomEffect(fn=_zuckuss_lof_204_fn)],
    )


def _psychometry_lof_219_fn(state, source_ci, target_id, event_ctx):
    """"Choose another card in your discard pile.  Search the top 5 cards of your
    deck for a card that shares a trait with the chosen card, reveal it, and draw
    it" (LOF_219).

    The discard choice is ``bottom_from_discard`` in its new pure-SELECTOR
    ``choose_only`` disposition (nothing moves), whose settle runs an ordinary
    ``deck_search`` over the chosen card's traits.  "Another" excludes the event
    itself, which is already in the controller's own discard by the time its
    ability resolves (the Commence Patrol JTL_205 rule)."""
    from swu.engine.actions import push_bottom_from_discard
    push_bottom_from_discard(
        state, source_ci, count=1, own_only=True,
        exclude_ids=frozenset({source_ci.instance_id}),
        disposition="choose_only", then_deck_search_shared_trait=5)
    return state


@card_ability("LOF", "219")
def _psychometry_lof_219():
    """LOF_219 — Psychometry (Event, Force, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_psychometry_lof_219_fn)])


def _a_precarious_predicament_lof_222_fn(state, source_ci, target_id, event_ctx):
    """"Return an enemy non-leader unit to its owner's hand unless its controller
    says, 'It could be worse.'  If they do, you may play a card named It's Worse
    from your hand or resources for free" (LOF_222).

    The ``say_no`` SOR_233 decider-shift with two new riders:
    ``effect="return_to_hand"`` for the allowed branch and ``refuse_play_named``
    for the refusal payoff, which reuses the one free-play seam
    (``push_play_from_hand`` whitelisted by instance id), pulling a copy out of the
    resource row first if that is where it sits."""
    from swu.engine.actions import push_say_no
    push_say_no(state, source_ci, target_id, effect="return_to_hand",
                refuse_play_named="It's Worse")
    return state


@card_ability("LOF", "222")
def _a_precarious_predicament_lof_222():
    """LOF_222 — A Precarious Predicament (Event, Trick, cost 2)."""
    return EventAbility(effects=[CustomEffect(
        fn=_a_precarious_predicament_lof_222_fn,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader",)))])


def _tip_the_scale_lof_226_fn(state, source_ci, target_id, event_ctx):
    """"Look at an opponent's hand and discard a non-unit card from it" (LOF_226) —
    ``name_and_discard`` (which already carries the whole hand to the controller and
    offers only names actually present) narrowed by the new ``"non_unit"`` type
    filter."""
    from swu.engine.actions import push_name_and_discard
    push_name_and_discard(state, source_ci, card_type="non_unit")
    return state


@card_ability("LOF", "226")
def _tip_the_scale_lof_226():
    """LOF_226 — Tip the Scale (Event, Force/Trick, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_tip_the_scale_lof_226_fn)])


@card_ability("LOF", "243")
def _caretaker_matron_lof_243():
    """LOF_243 — Caretaker Matron (Unit 0/4, Fringe): "Action [Exhaust]: If you
    played a Force card this phase, draw a card."

    The "If …" gates availability via ``ActivatedAbility.condition`` over the
    existing ``CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE`` ledger (Captain Phasma
    JTL_10), so the exhaust is never spent on a guaranteed no-op."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DrawCards(1)],
        title="Draw a card",
        condition=ConditionCheck(Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE,
                                 param="Force"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:08`` — Combat tricks, buffs & tempo (the LOF leaders)
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("LOF", "4")
def _kanan_jarrus_lof_4():
    """LOF_4 — Kanan Jarrus (Leader, Force/Jedi/Rebel/Spectre, 3/6, Shielded).

    * **Undeployed** "Action [1 resource, Exhaust]: Give a Shield token to a Creature
      or Spectre unit."  The disjunctive trait filter is the existing
      ``creature_or_spectre`` predicate.
    * **Deployed** "While you control another Creature or Spectre unit, this unit
      gets +2/+2" — a SELF ConstantAbility gated by ``ANY_OF`` over the two
      self-excluding ``CONTROLLER_HAS_OTHER_TRAIT_UNIT`` atoms (one atom per trait,
      OR'd; a single atom takes only one trait).  A ConstantAbility on a leader is
      deployed-only for free — only the arena scans read it.

    Shielded is the keyword engine."""
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[GiveToken("Shield", TargetSpec(
                controller="any", kind="unit",
                predicates=("creature_or_spectre",)))],
            title="Give a Shield token to a Creature or Spectre unit",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=2, hp=2)],
            condition=ConditionCheck(Condition.ANY_OF, param=(
                ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                               param="Creature"),
                ConditionCheck(Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                               param="Spectre"),
            )),
        ),
    ]


def _morgan_elsbeth_lof_5_play(state, source_ci, target_id, event_ctx):
    """"Choose a friendly unit that attacked this phase.  Play a unit from your hand
    that shares a keyword with the chosen unit.  It costs 1 resource less" (LOF_5
    undeployed) — one targeted CustomEffect, so "the chosen unit" is unambiguous."""
    if target_id is None:
        return state
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=1,
                        shares_keyword_with_id=target_id)
    return state


@card_ability("LOF", "5")
def _morgan_elsbeth_lof_5():
    """LOF_5 — Morgan Elsbeth (Leader, Force/Imperial/Night, 3/6).

    * **Undeployed** Action [Exhaust]: the targeted play above, over the existing
      ``attacked_this_phase`` predicate and the new
      ``push_play_from_hand(shares_keyword_with_id=)`` filter.
    * **Deployed** "On Attack: The next unit you play this phase costs 1 resource
      less if it shares a keyword with a friendly unit" — a ``NextPlayDiscount``
      carrying the new ``shares_keyword_with_friendly`` gate, which is evaluated
      while the cost is being paid (the card's own printed rules note)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(
                fn=_morgan_elsbeth_lof_5_play,
                target=TargetSpec(controller="friendly", kind="unit",
                                  predicates=("attacked_this_phase",)))],
            title="Play a unit sharing a keyword with one that attacked",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[NextPlayDiscount(trait="", amount=1,
                                      shares_keyword_with_friendly=True)],
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "6")
def _supreme_leader_snoke_lof_6():
    """LOF_6 — Supreme Leader Snoke (Leader, First Order/Force/Official, 4/7).

    Both sides give an Experience token to "the unit with the most power among
    friendly Villainy units.  (If multiple units are tied, choose one.)" — the new
    ``most_power_among_friendly_villainy`` predicate, a per-candidate board read that
    admits only the units at the maximum, so a clear winner auto-resolves and a tie
    is a real choice, exactly as the parenthetical says.  Effective power, per the
    card's printed rules note."""
    spec = TargetSpec(controller="friendly", kind="unit",
                      predicates=("most_power_among_friendly_villainy",))
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[GiveToken("Experience", spec)],
            title="Give an Experience token to your strongest Villainy unit",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", spec)],
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "7")
def _avar_kriss_lof_7():
    """LOF_7 — Avar Kriss (Leader, Force/Jedi/Republic, 4/10, Overwhelm).

    * **Undeployed** "Action [Exhaust]: The Force is with you (create your Force
      token)" — the ``CreateForceToken`` effect.
    * **Deployed** "While the Force is with you, this unit gets +4/+0 and gains
      Overwhelm" — one SELF ConstantAbility carrying BOTH a StatBonus and a
      KeywordGrant (the Tarkin JTL_161 shape), gated on
      ``CONTROLLER_HAS_FORCE_TOKEN``.  The printed Overwhelm is stripped by keyword
      sanitiser rule 2 (a conditional SELF grant), so a tokenless Avar really lacks
      it.

    His Epic Action's deploy condition ("resources plus the number of times you used
    the Force this phase") is not one the deploy-threshold parser reads, so he
    deploys by the standard machinery — no registration."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CreateForceToken()],
            title="The Force is with you",
            undeployed_only=True,
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=4, hp=0), KeywordGrant("Overwhelm")],
            condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
        ),
    ]


@card_ability("LOF", "8")
def _obi_wan_kenobi_lof_8():
    """LOF_8 — Obi-Wan Kenobi (Leader, Force/Jedi/Republic, 3/6).

    * **Undeployed** "Action [Exhaust, use the Force (lose your Force token)]: Give
      an Experience token to a unit without an Experience token on it" — the
      ``UseForce`` ability cost (already gated at every affordability site) plus the
      new ``no_experience_token`` predicate.
    * **Deployed** "On Attack: You may give an Experience token to ANOTHER unit
      without an Experience token on it" — the same predicate with ``not_self``, and
      no Force cost."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[GiveToken("Experience", TargetSpec(
                controller="any", kind="unit",
                predicates=("no_experience_token",)))],
            title="Give an Experience token to a unit without one",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(
                controller="any", kind="unit",
                predicates=("no_experience_token", "not_self")))],
            optional=True,
            deployed_only=True,
        ),
    ]


def _barriss_offee_lof_13_play_event(state, source_ci, target_id, event_ctx):
    """"Play an event from your hand.  It costs 1 resource less" (LOF_13) — the
    ``play_event_from_hand`` decision (Bib Fortuna SOR_177)."""
    from swu.engine.actions import push_play_event_from_hand
    push_play_event_from_hand(state, source_ci, cost_reduction=1)
    return state


@card_ability("LOF", "13")
def _barriss_offee_lof_13():
    """LOF_13 — Barriss Offee (Leader, Force/Jedi/Republic, 4/7).

    Both sides play a discounted event; the difference is only the cost — undeployed
    "[Exhaust, use the Force]", deployed "[use the Force]" (no exhaust, so she may do
    it as often as she has Force tokens).  Both are gated by
    ``CONTROLLER_CAN_PLAY_EVENT_FROM_HAND(1)`` so the price is never paid for a
    guaranteed no-op; the ``UseForce`` cost is itself gated at the affordability
    sites."""
    gate = ConditionCheck(Condition.CONTROLLER_CAN_PLAY_EVENT_FROM_HAND, param=1)
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[CustomEffect(fn=_barriss_offee_lof_13_play_event)],
            title="Play an event from your hand for 1 less",
            undeployed_only=True,
            condition=gate,
        ),
        ActivatedAbility(
            costs=[UseForce()],
            effects=[CustomEffect(fn=_barriss_offee_lof_13_play_event)],
            title="Play an event from your hand for 1 less",
            deployed_only=True,
            condition=gate,
        ),
    ]


def _grand_inquisitor_lof_14_attack(state, source_ci, target_id, event_ctx):
    """"Attack with a friendly unit.  The defender gets −2/−0 for this attack"
    (LOF_14 undeployed) — ``push_granted_attack`` with the long-standing
    ``defender_power_bonus`` debuff (Jyn Erso SOR_18)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, defender_power_bonus=-2)
    return state


@card_ability("LOF", "14")
def _grand_inquisitor_lof_14():
    """LOF_14 — Grand Inquisitor (Leader, Force/Imperial/Inquisitor, 3/5, Shielded).

    * **Undeployed** "Action [Exhaust, use the Force (lose your Force token)]: Attack
      with a friendly unit.  The defender gets −2/−0 for this attack."
    * **Deployed** "On Attack: The defender gets −2/−0 for this attack" — a fixed
      ``DEFENDER`` this-attack ``ModifyStats``.

    Shielded is the keyword engine."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[CustomEffect(fn=_grand_inquisitor_lof_14_attack)],
            title="Attack with a friendly unit (defender −2/−0)",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=-2, hp=0,
                                 target=TargetSpec(fixed=DEFENDER),
                                 duration=Duration.THIS_ATTACK)],
            deployed_only=True,
        ),
    ]


# ── lof-set:09 — Combat tricks, buffs & tempo ─────────────────────────────────

def _cal_kestis_lof_15_exhaust(state, source_ci, target_id, event_ctx):
    """"An opponent chooses a ready unit they control.  Exhaust that unit."

    The ``opponent_chooses_target`` decision (Grey Squadron Y-Wing SHD_246) in its
    new ``disposition="exhaust"`` flavour: a SINGLE mandatory stage decided by the
    opponent (the LOF_43 "defeat" shape), narrowed by ``ready_only`` so an
    already-exhausted unit — which would make the whole clause a no-op — is never
    a legal choice.  With no ready enemy unit nothing is pushed and the clause
    fizzles."""
    from swu.engine.actions import push_opponent_chooses_target
    push_opponent_chooses_target(state, source_ci, units_only=True,
                                 ready_only=True, disposition="exhaust")
    return state


@card_ability("LOF", "15")
def _cal_kestis_lof_15():
    """LOF_15 — Cal Kestis (Leader, Force/Fringe, 3/4).

    * **Undeployed** "Action [Exhaust, use the Force (lose your Force token)]: An
      opponent chooses a ready unit they control.  Exhaust that unit."
    * **Deployed** "On Attack: <the same>."

    Both sides are the one thin ``CustomEffect`` adapter onto
    ``push_opponent_chooses_target(disposition="exhaust")``.  The Epic Action is
    the ordinary leader deploy (never routed through the registry)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[CustomEffect(fn=_cal_kestis_lof_15_exhaust)],
            title="An opponent exhausts one of their ready units",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_cal_kestis_lof_15_exhaust)],
            deployed_only=True,
        ),
    ]


def _darth_revan_lof_17_attacker(state, event_ctx):
    """The friendly unit that just attacked and defeated a unit, or None."""
    aid = (event_ctx or {}).get("attack_defeated_unit")
    if not aid:
        return None
    result = state.find_instance(aid)
    return None if result is None else result[1]


def _darth_revan_lof_17_exhaust_then_token(state, source_ci, target_id, event_ctx):
    """Undeployed: "You may exhaust this leader.  If you do, give an Experience
    token to that friendly unit."  Cost and payoff in ONE ``CustomEffect`` so an
    unpayable cost can never apply the payoff (the Bright Hope SOR_99 binding)."""
    if source_ci.exhausted:
        return state
    attacker = _darth_revan_lof_17_attacker(state, event_ctx)
    if attacker is None:
        return state
    source_ci.exhausted = True
    from swu.engine.tokens import attach_token
    attach_token(state, state.player_by_id(source_ci.owner_id), attacker, "Experience")
    return state


def _darth_revan_lof_17_token(state, source_ci, target_id, event_ctx):
    """Deployed: "You may give an Experience token to that friendly unit."" """
    attacker = _darth_revan_lof_17_attacker(state, event_ctx)
    if attacker is None:
        return state
    from swu.engine.tokens import attach_token
    attach_token(state, state.player_by_id(source_ci.owner_id), attacker, "Experience")
    return state


@card_ability("LOF", "17")
def _darth_revan_lof_17():
    """LOF_17 — Darth Revan (Leader, Force/Sith, 3/6, Restore 1 deployed).

    * **Undeployed** "When a friendly unit attacks and defeats a unit: You may
      exhaust this leader.  If you do, give an Experience token to that friendly
      unit."
    * **Deployed** "<the same trigger>: You may give an Experience token to that
      friendly unit" (no cost).

    Both use the new ``WhenFriendlyUnitAttacksAndDefeatsUnit`` observer — the group
    analogue of ``OnAttackDefeatsUnit``, matched at the same firing site off the
    same ``attack_defeated_unit`` key, which is also how "that friendly unit" is
    located.  The undeployed side is gated ``SOURCE_READY`` so the "you may" is
    never offered when the cost cannot be paid.  Restore 1 is the keyword engine."""
    return [
        TriggerAbility(
            trigger=WhenFriendlyUnitAttacksAndDefeatsUnit(),
            effects=[CustomEffect(fn=_darth_revan_lof_17_exhaust_then_token)],
            optional=True,
            undeployed_only=True,
            condition=ConditionCheck(Condition.SOURCE_READY),
        ),
        TriggerAbility(
            trigger=WhenFriendlyUnitAttacksAndDefeatsUnit(),
            effects=[CustomEffect(fn=_darth_revan_lof_17_token)],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "33")
def _nameless_terror_lof_33():
    """LOF_33 — Nameless Terror (Unit, Creature, 3/3).

    * "When Played: You may exhaust a Force unit." — a plain optional
      ``ExhaustCard`` over any ready Force unit (the ``ready`` predicate keeps the
      prompt off a no-op choice).
    * "On Attack: Each enemy unit loses the Force trait for this phase." — the new
      ``RevokeTrait`` effect on ``EACH_ENEMY``: a ``trait_revoke`` Modifier the
      trait query layer reads ahead of printed traits AND every ``TraitGrant``, so
      "can't regain it this phase" falls out for free (the ``keyword_revoke``
      precedent)."""
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            effects=[ExhaustCard(TargetSpec(
                controller="any", kind="unit", traits=("Force",),
                predicates=("ready",),
            ))],
            optional=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[RevokeTrait("Force",
                                 TargetSpec(fixed=EACH_ENEMY, kind="unit"),
                                 duration=Duration.THIS_PHASE)],
        ),
    ]


@card_ability("LOF", "47")
def _t6_shuttle_lof_47():
    """LOF_47 — T-6 Shuttle 1974 (Unit, Fringe/Transport/Vehicle, 3/4): "When this
    unit is attacked (before damage is dealt): You may give an Experience token to
    this unit."

    A plain optional ``WhenAttacked`` trigger — that trigger already fires in the
    pre-damage window, so the printed parenthetical is intrinsic and the +1/+1 is
    live for the combat damage step."""
    return TriggerAbility(
        trigger=WhenAttacked(),
        effects=[GiveToken("Experience", TargetSpec(fixed=SELF))],
        optional=True,
    )


def _itinerant_warrior_lof_48_heal(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, heal 3 damage from a
    base" — cost and payoff bound in ONE ``CustomEffect`` (Bright Hope SOR_99), so
    an unpaid cost can never heal.  The heal routes through ``_apply_heal`` so the
    Wolffe SOR_160 "bases can't be healed" lock still applies."""
    from swu.engine.actions import spend_force_token
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _apply_heal
    return _apply_heal(state, source_ci, target_id, 3)


@card_ability("LOF", "48")
def _itinerant_warrior_lof_48():
    """LOF_48 — Itinerant Warrior (Unit, Force/Jedi, 4/4, Shielded): "When Played:
    You may use the Force (lose your Force token).  If you do, heal 3 damage from a
    base."

    The optional trigger IS the "you may", gated on ``CONTROLLER_HAS_FORCE_TOKEN``
    so it is never offered without a token to spend (Luke Skywalker LOF_249's
    recipe).  Shielded is the keyword engine."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_itinerant_warrior_lof_48_heal,
                              target=TargetSpec(controller="any", kind="base"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "49")
def _jedi_guardian_lof_49():
    """LOF_49 — Jedi Guardian (Unit, Force/Jedi, 4/8): "While this unit is
    defending, it gets +2/+0."

    ``ConstantAbility(target=SELF, while_target_defending=True)`` — the buff lands
    on its own target only while that target is the current combat defender
    (Concord Dawn Protector SHD_42's reading of the same sentence)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        while_target_defending=True,
    )


@card_ability("LOF", "50")
def _plo_koon_lof_50():
    """LOF_50 — Plo Koon (Unit, Force/Jedi/Republic, 6/8): "While the Force is with
    you, this unit gains Grit."

    The conditional SELF keyword grant on ``CONTROLLER_HAS_FORCE_TOKEN`` (Jedi
    Sentinel LOF_196's shape); the keyword sanitiser's rule 2 strips the printed
    Grit so the ability — not an always-on bar — owns it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Grit", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


# ── lof-set:10 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "52")
def _jedi_trials_lof_52():
    """LOF_52 — Jedi Trials (Upgrade, Jedi/Learned, cost 1).

    * "Attached unit gains: 'On Attack: Give an Experience token to this unit.'" —
      a ``GrantedAbility``, which resolves with the HOST as source, so the SELF
      token lands on the host (Armed to the Teeth SHD_175).
    * "While attached unit has 4 or more upgrades on it, it gains the Jedi trait."
      — a SELF ``ConstantAbility`` carrying a ``TraitGrant``; the trait layer's
      attached-upgrade scan confers it on the host and evaluates the condition
      against that host, so the new trait-blind ``SOURCE_ATTACHED_UPGRADES_MIN``
      atom counts the HOST's upgrades (Shield/Experience tokens included, as
      "upgrades on it" always does).  This upgrade itself is one of them.

    "Attach to a Force unit" is the ``_upgrade_target_spec`` text parser."""
    return [
        GrantedAbility(TriggerAbility(
            trigger=OnAttack(),
            effects=[GiveToken("Experience", TargetSpec(fixed=SELF))],
        )),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[TraitGrant(trait="Jedi")],
            condition=ConditionCheck(Condition.SOURCE_ATTACHED_UPGRADES_MIN, param=4),
        ),
    ]


@card_ability("LOF", "53")
def _heirloom_lightsaber_lof_53():
    """LOF_53 — Heirloom Lightsaber (Upgrade, Item/Lightsaber/Weapon, cost 2):
    "Attach to a non-Vehicle unit.  If attached unit is a Force unit, it gains
    Restore 1."

    The upgrade-SELF ``KeywordGrant`` — the only path an upgrade's keyword reaches
    its host (Grievous's Wheel Bike TWI_236) — gated by ``SOURCE_HAS_TRAIT``, which
    the keyword layer's attached-upgrade scan evaluates against the HOST
    (Constructed Lightsaber LOF_261)."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Restore", value=1)],
        condition=ConditionCheck(Condition.SOURCE_HAS_TRAIT, param="Force"),
    )


def _calm_in_the_storm_lof_54(state, source_ci, target_id, event_ctx):
    """"Exhaust a friendly unit.  If you do, give a Shield token and 2 Experience
    tokens to it."  ONE ``CustomEffect.target`` so the cost and its payoff cannot
    split across two prompts (the Kylo Ren SHD_141 rule); only READY friendly units
    are offered, so "if you do" can never fail."""
    if target_id is None:
        return state
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, ci = result
    if ci.exhausted:
        return state
    ci.exhausted = True
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    attach_token(state, ps, ci, "Shield")
    for _ in range(2):
        attach_token(state, ps, ci, "Experience")
    return state


@card_ability("LOF", "54")
def _calm_in_the_storm():
    """LOF_54 — Calm in the Storm (Event, Force, cost 2)."""
    return EventAbility(effects=[CustomEffect(
        fn=_calm_in_the_storm_lof_54,
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("ready",)),
    )])


@card_ability("LOF", "55")
def _dume_lof_55():
    """LOF_55 — Dume (Unit, Creature/Force, 2/7): "When the regroup phase starts:
    Give an Experience token to each other friendly non-Vehicle unit."

    A ``PhaseStartTrigger("regroup")`` whose ``EACH_FRIENDLY`` target expands
    inline (no prompt); ``not_self`` is the printed "each OTHER"."""
    return TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[GiveToken("Experience", TargetSpec(
            fixed=EACH_FRIENDLY, kind="unit",
            predicates=("not_self", "non_vehicle"),
        ))],
    )


@card_ability("LOF", "56")
def _size_matters_not_lof_56():
    """LOF_56 — Size Matters Not (Upgrade, Force, cost 3).

    * "If you control a Force unit, this upgrade costs 1 resource less to play." —
      the declarative ``CostReduction`` read at the play-cost seam (Force Choke
      SOR_139).
    * "Attached unit's printed power is considered to be 5 and its printed HP is
      considered to be 5." — the new ``PrintedStatsOverride`` marker, read where
      ``compute_power``/``compute_hp`` seed the total from the printed value, so
      every bonus (upgrades, tokens, Grit, modifiers, constants) still layers on
      top of the 5/5 — the printed reading."""
    return [
        CostReduction(
            amount=1,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, param="Force"),
        ),
        PrintedStatsOverride(power=5, hp=5),
    ]


@card_ability("LOF", "58")
def _guardian_of_the_whills_lof_58():
    """LOF_58 — Guardian of the Whills (Unit, Force/Fringe, 2/2): "The first
    upgrade you play on this unit each round costs 1 resource less."

    Pure reuse of the host-scoped ``StandingPlayDiscount`` built for its SOR_61
    namesake: the play-cost seam matches only an Upgrade being played onto this
    very unit and spends the discount after the first such play each round."""
    return StandingPlayDiscount(amount=1, applies_to="upgrade_on_source",
                                once_per_round=True)


@card_ability("LOF", "60")
def _padawan_starfighter_lof_60():
    """LOF_60 — Padawan Starfighter (Unit, Fighter/Jedi/Republic/Vehicle, 1/3):
    "While you control a Force unit or upgrade, this unit gets +1/+1."

    Pure reuse of its TWI_58 namesake: a conditional SELF ``StatBonus`` on
    ``CONTROLLER_HAS_TRAIT_CARD_IN_PLAY``, which widens the trait scan to each
    arena unit's attached upgrades — exactly the card's "or upgrade"."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=1, hp=1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_CARD_IN_PLAY, param="Force"),
    )


# ── lof-set:11 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "64")
def _tauntaun_lof_64():
    """LOF_64 — Tauntaun (Unit, Creature, 3/3): "When Defeated: You may give a
    Shield token to a damaged non-Vehicle unit."

    A plain optional ``WhenDefeated`` ``GiveToken``; with no damaged non-Vehicle
    unit on the board the optional trigger auto-declines (no prompt)."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Shield", TargetSpec(
            controller="any", kind="unit",
            predicates=("damaged", "non_vehicle"),
        ))],
        optional=True,
    )


def _priestesses_of_the_force_lof_72(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, give a Shield token to
    each of up to 5 units."  The cost and its payoff are bound in ONE
    ``CustomEffect`` (Bright Hope SOR_99), and the payoff is the long-standing
    ``select_token`` up-to-N loop (Medal Ceremony SOR_245)."""
    from swu.engine.actions import spend_force_token, push_select_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    push_select_token(state, source_ci, token_type="Shield", max_targets=5,
                      controller="any", kind="unit")
    return state


@card_ability("LOF", "72")
def _priestesses_of_the_force():
    """LOF_72 — Priestesses of the Force (Unit, Force, 6/8): "When Played: You may
    use the Force (lose your Force token).  If you do, give a Shield token to each
    of up to 5 units."

    The optional trigger IS the "you may", gated on ``CONTROLLER_HAS_FORCE_TOKEN``
    so it is never offered without a token to spend (Itinerant Warrior LOF_48)."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_priestesses_of_the_force_lof_72)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _cure_wounds_lof_75(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, heal 6 damage from a
    unit."  The Force token is a BOARD GATE on the candidates (the
    ``controller_has_force_token`` predicate, Sorcerous Blast LOF_172), so with no
    token the event has no legal target and fizzles unprompted; the cost and the
    heal then live in this one effect."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    from swu.engine.actions import spend_force_token
    if not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _apply_heal
    return _apply_heal(state, source_ci, target_id, 6)


@card_ability("LOF", "75")
def _cure_wounds():
    """LOF_75 — Cure Wounds (Event, Force, cost 1)."""
    return EventAbility(effects=[CustomEffect(
        fn=_cure_wounds_lof_75,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("controller_has_force_token",)),
    )])


def _soresu_stance_lof_76(state, source_ci, target_id, event_ctx):
    """"Play a Force unit from your hand (paying its cost) and give a Shield token
    to it."  ``push_play_from_hand(trait="Force")`` with the ``then_select_token``
    settle rider narrowed by ``restrict_played`` — the token must land on the unit
    just played (The Burden of Masters LOF_125), and a settle payoff is the only
    ordering that runs AFTER the play."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(
        state, source_ci, trait="Force",
        then_select_token={"token_type": "Shield", "max_targets": 1,
                           "controller": "friendly", "kind": "unit",
                           "restrict_played": True},
    )
    return state


@card_ability("LOF", "76")
def _soresu_stance():
    """LOF_76 — Soresu Stance (Event, Learned, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_soresu_stance_lof_76)])


@card_ability("LOF", "81")
def _sith_legionnaire_lof_81():
    """LOF_81 — Sith Legionnaire (Unit, Sith/Trooper, 2/2): "While you control
    another Villainy unit, this unit gets +2/+0."

    A conditional SELF ``StatBonus`` on ``CONTROLLER_HAS_OTHER_ASPECT_UNIT``
    (Privateer Scyk SHD_212's atom), whose scan already excludes the source — the
    printed "another"."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT,
                                 param="Villainy"),
    )


@card_ability("LOF", "85")
def _praetorian_guard_lof_85():
    """LOF_85 — Praetorian Guard (Unit, First Order, 2/5): "While you control a
    unit with 4 or more power, this unit gains Sentinel."

    The conditional SELF keyword grant (Protector of the Throne SHD_247's shape) on
    the new ``CONTROLLER_HAS_UNIT_POWER_MIN`` atom, which shares SOURCE_POWER_MIN's
    reentrancy guard — the scan measures *effective* power, and compute_power
    re-enters the very keyword layer that asks the question.  "A unit" is
    unqualified, so the Guard itself counts when something has pushed it to 4; the
    sanitiser strips the printed Sentinel so the ability owns it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Sentinel", value=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_UNIT_POWER_MIN, param=4),
    )


def _drengir_spawn_lof_86(state, source_ci, target_id, event_ctx):
    """"Give a number of Experience tokens to this unit equal to the defeated
    unit's cost."  The victim is ``event_ctx["attack_defeated_defender"]`` (the key
    the combat site threads beside ``attack_defeated_unit``); ``find_instance``
    still reaches it in its owner's discard, where the defeat just put it."""
    did = (event_ctx or {}).get("attack_defeated_defender")
    if not did:
        return state
    result = state.find_instance(did)
    if result is None:
        return state
    cost = int(getattr(result[1].card_def, "cost", 0) or 0)
    if cost <= 0:
        return state
    from swu.engine.tokens import attach_token
    ps = state.player_by_id(source_ci.owner_id)
    for _ in range(cost):
        attach_token(state, ps, source_ci, "Experience")
    return state


@card_ability("LOF", "86")
def _drengir_spawn():
    """LOF_86 — Drengir Spawn (Unit, Creature, 3/3, Overwhelm): "When this unit
    attacks and defeats a unit: Give a number of Experience tokens to this unit
    equal to the defeated unit's cost."

    ``OnAttackDefeatsUnit`` (which already means "attacked, survived, and killed
    it") plus a ``CustomEffect`` for the dynamic count — ``GiveToken.count`` is a
    fixed number.  Overwhelm is the keyword engine."""
    return TriggerAbility(
        trigger=OnAttackDefeatsUnit(),
        effects=[CustomEffect(fn=_drengir_spawn_lof_86)],
    )


# ── lof-set:12 — Combat tricks, buffs & tempo ─────────────────────────────────

def _eighth_brother_lof_87_buff(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, give a unit +2/+2 for
    this phase" — cost and payoff in ONE ``CustomEffect`` (Bright Hope SOR_99), so
    a declined/unpayable cost can never buff."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    from swu.engine.actions import spend_force_token
    if not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=2, hp=2, duration=Duration.THIS_PHASE))
    return state


@card_ability("LOF", "87")
def _eighth_brother_lof_87():
    """LOF_87 — Eighth Brother (Unit, Force/Imperial/Inquisitor, 5/7, Ambush):
    "When you play another unit: You may use the Force (lose your Force token).  If
    you do, give a unit +2/+2 for this phase."

    ``WhenYouPlayCard(card_type="unit")`` (``exclude_self`` defaults True = "another")
    gated on ``CONTROLLER_HAS_FORCE_TOKEN`` so it is never offered without a token to
    spend — Luke Skywalker LOF_249's recipe.  "A unit" is unrestricted, so
    ``controller="any"``.  Ambush is the keyword engine (it is a bare printed
    mention, so the sanitiser keeps it)."""
    return TriggerAbility(
        trigger=WhenYouPlayCard(card_type="unit"),
        effects=[CustomEffect(fn=_eighth_brother_lof_87_buff,
                              target=TargetSpec(controller="any", kind="unit"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "89")
def _supremacy_lof_89():
    """LOF_89 — Supremacy (Unit, Capital Ship/First Order/Vehicle, 12/12, Ambush):
    "Other friendly Vehicle units get +6/+6."

    The plain trait anthem — General Veers SOR_230's shape with ``not_self`` for
    "other" and the Vehicle trait filter.  ``get`` (not "gains"), so it is a
    ``StatBonus`` aura, live only while Supremacy is in play."""
    return ConstantAbility(
        target=TargetSpec(
            controller="friendly", kind="unit",
            traits=("Vehicle",), predicates=("not_self",),
        ),
        effects=[StatBonus(power=6, hp=6)],
    )


@card_ability("LOF", "92")
def _point_rain_reclaimer_lof_92():
    """LOF_92 — Point Rain Reclaimer (Unit, Clone/Republic/Trooper, 1/2): "When
    Played: If you control a Jedi unit, you may give an Experience token to this
    unit."

    The "if you control" clause is the trigger ``condition`` (false ⇒ the trigger is
    never collected, so no prompt); the "you may" is ``optional``.  This unit is a
    Clone, never a Jedi, so ``CONTROLLER_HAS_TRAIT_UNIT`` needs no self-exclusion."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Experience", TargetSpec(fixed=SELF))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_TRAIT_UNIT, param="Jedi"),
    )


@card_ability("LOF", "95")
def _lor_san_tekka_lof_95():
    """LOF_95 — Lor San Tekka (Unit, Resistance, 3/2): "When Defeated: You may give
    an Experience token to a unique unit."

    An optional ``WhenDefeated`` + the ``unique`` predicate (Always Two LOF_42).
    "A unique unit" names no controller, so ``controller="any"``; with no unique
    unit on the board the optional trigger auto-declines."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="any", kind="unit", predicates=("unique",),
        ))],
        optional=True,
    )


def _eeth_koth_lof_97_resource(state, source_ci, target_id, event_ctx):
    """"Use the Force.  If you do, put this card into play as a resource."  The
    defeat already put the card in its owner's discard; move it from there into the
    resource zone facedown and EXHAUSTED — the CR default, since (unlike Superlaser
    Technician SOR_83) this card does not say "and ready it"."""
    ps = state.player_by_id(source_ci.owner_id)
    from swu.engine.actions import spend_force_token
    if not spend_force_token(state, ps):
        return state
    from swu.engine.state import Zone
    for i, ci in enumerate(ps.discard):
        if ci.instance_id == source_ci.instance_id:
            ps.discard.pop(i)
            ci.zone = Zone.RESOURCES
            ci.face_down = True
            ci.exhausted = True
            ci.damage = 0
            ps.resources.append(ci)
            return state
    return state


@card_ability("LOF", "97")
def _eeth_koth_lof_97():
    """LOF_97 — Eeth Koth (Unit, Force/Jedi/Republic, 5/4): "When Defeated: You may
    use the Force.  If you do, put this card into play as a resource."

    Superlaser Technician SOR_83's self-recursion, with the Force spend bound into
    the same ``CustomEffect`` as the payoff and the trigger gated on
    ``CONTROLLER_HAS_FORCE_TOKEN`` so it is never offered with nothing to spend."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_eeth_koth_lof_97_resource)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "102")
def _yodas_lightsaber_lof_102():
    """LOF_102 — Yoda's Lightsaber (Upgrade, Item/Lightsaber/Weapon, cost 2):
    "Attach to a non-Vehicle unit.  When Played: You may use the Force (lose your
    Force token).  If you do, heal 3 damage from a base."

    Word-for-word Itinerant Warrior LOF_48's second sentence, so it reuses that
    card's payoff function verbatim (spend, then ``_apply_heal`` so Wolffe SOR_160's
    "bases can't be healed" lock still applies).  An Upgrade fires ``WhenPlayed``
    exactly as a unit does (Qui-Gon Jinn's Lightsaber LOF_201); "Attach to a
    non-Vehicle unit" is the ``_upgrade_target_spec`` text parser."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_itinerant_warrior_lof_48_heal,
                              target=TargetSpec(controller="any", kind="base"))],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


# Oppo Rancisis LOF_105 mirrors nine keywords off "another friendly unit"; the two
# numeric ones are granted at the printed value ("gains Raid 2 … the same is true
# for Restore").
_OPPO_RANCISIS_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("Ambush", 0), ("Grit", 0), ("Hidden", 0), ("Overwhelm", 0),
    ("Saboteur", 0), ("Sentinel", 0), ("Shielded", 0),
    ("Raid", 2), ("Restore", 2),
)


@card_ability("LOF", "105")
def _oppo_rancisis_lof_105():
    """LOF_105 — Oppo Rancisis (Unit, Force/Jedi/Republic, 3/5): "This unit gains
    Ambush while another friendly unit has Ambush.  The same is true for Grit,
    Hidden, Overwhelm, Saboteur, Sentinel, and Shielded.  This unit gains Raid 2
    while another friendly unit has Raid.  The same is true for Restore."

    Nine independent conditional SELF ``KeywordGrant`` specs (Jedi Sentinel
    LOF_196's shape), each gated on the new
    ``CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD`` atom — which reads the *effective*
    keyword layer, so a keyword another unit was merely granted mirrors too.  Every
    one of the nine is a conditional self-grant, so the sanitiser's rule 2 strips
    the whole printed bar and these abilities own it."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[KeywordGrant(keyword=kw, value=val)],
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD, param=kw),
        )
        for kw, val in _OPPO_RANCISIS_KEYWORDS
    ]


# ── lof-set:13 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "106")
def _acclamator_assault_ship_lof_106():
    """LOF_106 — Acclamator Assault Ship (Unit, Capital Ship/Republic/Vehicle,
    5/8): "On Attack: You may give another unit +5/+5 for this phase."

    The plain optional ``OnAttack`` ``ModifyStats``; "another unit" names no
    controller, so ``controller="any"`` with ``not_self``."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(
            power=5, hp=5,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("not_self",)),
            duration=Duration.THIS_PHASE,
        )],
        optional=True,
    )


@card_ability("LOF", "118")
def _terentatek_lof_118():
    """LOF_118 — Terentatek (Unit, Creature, 5/5): "While an opponent controls a
    Force unit, this unit gains Ambush."

    The conditional SELF keyword grant (Jedi Sentinel LOF_196's shape) on the new
    ``ENEMY_HAS_TRAIT_UNIT`` atom — CONTROLLER_HAS_TRAIT_UNIT read across the
    table.  The sanitiser's rule 2 strips the printed Ambush so this ability owns
    it."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Ambush", value=0)],
        condition=ConditionCheck(Condition.ENEMY_HAS_TRAIT_UNIT, param="Force"),
    )


def _niman_strike_lof_124(state, source_ci, target_id, event_ctx):
    """"Attack with a Force unit, even if it's exhausted.  It gets +1/+0 and can't
    attack bases for this attack." — the granted-attack seam with three of its
    existing knobs (Mon Mothma LAW_16's ``no_base``, Impossible Escape LOF_218's
    ``allow_exhausted``)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=1,
                        attacker_trait="Force", allow_exhausted=True,
                        no_base=True)
    return state


@card_ability("LOF", "124")
def _niman_strike_lof_124_card():
    """LOF_124 — Niman Strike (Event, Learned, cost 1): "Attack with a Force unit,
    even if it's exhausted.  It gets +1/+0 and can't attack bases for this
    attack." """
    return EventAbility(effects=[CustomEffect(fn=_niman_strike_lof_124)])


def _overpower_lof_126(state, source_ci, target_id, event_ctx):
    """"Give a unit +3/+3 and Overwhelm for this phase" — both landed on the SAME
    chosen unit from one ``CustomEffect.target``, rather than two effects that could
    split the choice (General Grievous TWI_15's rule)."""
    if target_id is None:
        return state
    from swu.abilities.resolver import _make_modifier, _make_kw_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=3, hp=3, duration=Duration.THIS_PHASE))
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id,
        keyword="Overwhelm", value=0, duration=Duration.THIS_PHASE,
        kind="keyword_grant"))
    return state


@card_ability("LOF", "126")
def _overpower_lof_126_card():
    """LOF_126 — Overpower (Event, Innate, cost 3): "Give a unit +3/+3 and Overwhelm
    for this phase."  (The printed "Overwhelm" is the reminder text of the keyword
    this event grants, not a keyword the event has — Events are outside the
    sanitiser's scope and an Event's keyword bar is inert.)"""
    return EventAbility(effects=[CustomEffect(
        fn=_overpower_lof_126,
        target=TargetSpec(controller="any", kind="unit"),
    )])


@card_ability("LOF", "127")
def _rampage_lof_127():
    """LOF_127 — Rampage (Event, Innate, cost 3): "Each friendly Creature unit gets
    +2/+2 for this phase."

    An untargeted sweep — ``EACH_FRIENDLY`` narrowed by the Creature trait, the
    Rally the Troops-style board buff."""
    return EventAbility(effects=[ModifyStats(
        power=2, hp=2,
        target=TargetSpec(fixed=EACH_FRIENDLY, kind="unit", traits=("Creature",)),
        duration=Duration.THIS_PHASE,
    )])


@card_ability("LOF", "135")
def _scythe_lof_135():
    """LOF_135 — Scythe (Unit, Imperial/Inquisitor/Transport/Vehicle, 3/5): "On
    Attack: You may give another friendly Inquisitor unit +2/+0 for this phase."

    Acclamator LOF_106 next door, narrowed to friendly Inquisitors.  Scythe is
    itself an Inquisitor, hence ``not_self`` for "another"; with no other Inquisitor
    the optional trigger auto-declines."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(
            power=2, hp=0,
            target=TargetSpec(controller="friendly", kind="unit",
                              traits=("Inquisitor",), predicates=("not_self",)),
            duration=Duration.THIS_PHASE,
        )],
        optional=True,
    )


def _cin_drallig_lof_150(state, source_ci, target_id, event_ctx):
    """"You may play a Lightsaber upgrade from your hand for free on this unit.  If
    you do, ready him."  The ``play_upgrade_from_hand`` decision (Fenn Rau SHD_67's
    choose-an-upgrade mode) with three of its knobs: the new ``trait`` narrowing to
    Lightsabers, ``host_id`` pinning the host to Cin Drallig himself ("on this
    unit", Kylo Ren LOF_1's knob), and the new ``then_ready_source`` for the "if you
    do" ready — which therefore never fires on a decline."""
    from swu.engine.actions import push_play_upgrade_from_hand
    push_play_upgrade_from_hand(
        state, source_ci, free=True, trait="Lightsaber",
        host_id=source_ci.instance_id, then_ready_source=True,
    )
    return state


@card_ability("LOF", "150")
def _cin_drallig_lof_150_card():
    """LOF_150 — Cin Drallig (Unit, Force/Jedi/Republic, 5/6): "When Played: You may
    play a Lightsaber upgrade from your hand for free on this unit.  If you do,
    ready him."

    The decision is itself the "you may" (it carries a decline and is only pushed
    when some Lightsaber in hand can legally attach), so the trigger is not
    ``optional`` — that would prompt twice."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_cin_drallig_lof_150)],
    )


# ── lof-set:14 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "152")
def _focus_determines_reality_lof_152():
    """LOF_152 — Focus Determines Reality (Event, Force, cost 2): "Each friendly
    Force unit gains Raid 1 and Saboteur for this phase."

    Two ``GrantKeyword`` effects over the same untargeted ``EACH_FRIENDLY`` sweep —
    with no choice to split, separate effects are exactly the printed reading (the
    General Grievous TWI_15 "bind them" rule only applies to a *chosen* target)."""
    _force_units = TargetSpec(fixed=EACH_FRIENDLY, kind="unit", traits=("Force",))
    return EventAbility(effects=[
        GrantKeyword("Raid", 1, _force_units, Duration.THIS_PHASE),
        GrantKeyword("Saboteur", 0, _force_units, Duration.THIS_PHASE),
    ])


@card_ability("LOF", "153")
def _paz_vizsla_lof_153():
    """LOF_153 — Paz Vizsla (Unit, Mandalorian, 3/6): "This unit gets +2/+0 for each
    damage on him."

    The scaling ``StatBonus(count="target_damage")`` (Radiant VII JTL_226), here on
    a SELF target so the count is read off Paz himself — Grit's arithmetic at
    double rate, which is why it is an ability and not the keyword."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0, count="target_damage")],
    )


@card_ability("LOF", "166")
def _blockade_runner_lof_166():
    """LOF_166 — Blockade Runner (Unit, Capital Ship/Rebel/Vehicle, 4/4, Saboteur):
    "When this unit deals combat damage to a base: You may give an Experience token
    to this unit."

    Pure reuse of ``WhenDealsCombatDamageToBase`` (Ketsu Onyo SHD_147); Saboteur is
    the keyword engine."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(),
        effects=[GiveToken("Experience", TargetSpec(fixed=SELF))],
        optional=True,
    )


@card_ability("LOF", "169")
def _invasion_control_ship_lof_169():
    """LOF_169 — Invasion Control Ship (Unit, Capital Ship/Separatist/Vehicle, 5/9,
    Raid): "Friendly Droid units gain Raid 2."

    A trait anthem in the keyword layer.  Not "other", so the ship would buff itself
    if it were a Droid — it is not (Capital Ship/Separatist/Vehicle), so no
    ``not_self`` is needed and none is printed."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Droid",)),
        effects=[KeywordGrant(keyword="Raid", value=2)],
    )


def _unleash_rage_lof_173(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, give a friendly unit
    +3/+0 for this phase" — spend and payoff in ONE ``CustomEffect`` (Bright Hope
    SOR_99), so an unpayable cost can never buff."""
    if target_id is None:
        return state
    ps = state.player_by_id(source_ci.owner_id)
    from swu.engine.actions import spend_force_token
    if not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=3, hp=0, duration=Duration.THIS_PHASE))
    return state


@card_ability("LOF", "173")
def _unleash_rage_lof_173_card():
    """LOF_173 — Unleash Rage (Event, Force, cost 1): "Use the Force (lose your
    Force token).  If you do, give a friendly unit +3/+0 for this phase." """
    return EventAbility(effects=[CustomEffect(
        fn=_unleash_rage_lof_173,
        target=TargetSpec(controller="friendly", kind="unit"),
    )])


@card_ability("LOF", "174")
def _ataru_onslaught_lof_174():
    """LOF_174 — Ataru Onslaught (Event, Learned, cost 2): "Ready a Force unit with
    4 or less power."

    ``ReadyCard`` over the Force trait plus ``power_max=4``, which the target matcher
    reads as EFFECTIVE power (a unit buffed past 4 is off limits, and a debuffed one
    is fair game)."""
    return EventAbility(effects=[ReadyCard(TargetSpec(
        controller="any", kind="unit", traits=("Force",), power_max=4,
    ))])


@card_ability("LOF", "178")
def _adept_of_anger_lof_178():
    """LOF_178 — Adept of Anger (Unit, Force/Fringe, 1/3): "Action [Exhaust, use the
    Force (lose your Force token)]: Exhaust a unit."

    The two-cost ``ActivatedAbility`` (Cal Kestis LOF_15's undeployed shape): both
    ``ExhaustSelf`` and ``UseForce`` must be payable for the action to be offered, so
    the ability disappears with no Force token."""
    return ActivatedAbility(
        costs=[ExhaustSelf(), UseForce()],
        effects=[ExhaustCard(TargetSpec(controller="any", kind="unit"))],
        title="Exhaust a unit",
    )


# ── lof-set:15 — Combat tricks, buffs & tempo ─────────────────────────────────

def _deceptive_shade_lof_180(state, source_ci, target_id, event_ctx):
    """Arm "the next unit you play this phase gains Ambush for this phase" — one
    entry on the new ``pending_keyword_grants`` list (the Count Dooku TWI_5
    pending-grant shape), consumed by that player's next unit play in
    ``_put_unit_in_play``, before the enter-play keyword bus, so the granted Ambush
    fires on entry exactly as a printed one would."""
    state.game_memory.pending_keyword_grants.append(
        {"player_id": source_ci.owner_id, "trait": "", "keyword": "Ambush"})
    return state


@card_ability("LOF", "180")
def _deceptive_shade_lof_180_card():
    """LOF_180 — Deceptive Shade (Unit, Sith/Undead, 2/3, Ambush): "When Defeated:
    The next unit you play this phase gains Ambush for this phase."

    The grant is to *another* card, so the Shade's own Ambush (its keyword bar) is
    untouched."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_deceptive_shade_lof_180)],
    )


def _premonition_of_doom_lof_203(state, source_ci, target_id, event_ctx):
    """Arm "the next time you take the initiative this phase, exhaust all units" —
    one entry on the new ``pending_initiative_effects`` list, consumed by this
    player's ``ClaimInitiative`` (the only place initiative is taken)."""
    state.game_memory.pending_initiative_effects.append(
        {"player_id": source_ci.owner_id, "effect": "exhaust_all_units"})
    return state


@card_ability("LOF", "203")
def _premonition_of_doom_lof_203_card():
    """LOF_203 — Premonition of Doom (Event, Force, cost 3): "The next time you take
    the initiative this phase, exhaust all units."

    "All units" is every unit in play on both sides — the claimer's own board is
    exhausted too, which is the card's whole tension."""
    return EventAbility(effects=[CustomEffect(fn=_premonition_of_doom_lof_203)])


def _force_speed_lof_205(state, source_ci, target_id, event_ctx):
    """"Attack with a unit.  For this attack, it gains: 'On Attack: Return any number
    of non-<uq> upgrades attached to the defender to their owners' hands.'"  The
    granted-attack seam plus the new ``return_defender_upgrades`` rider, which marks
    the attacker and lands the choice inside the OnAttack window (before combat
    damage)."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, return_defender_upgrades=True)
    return state


@card_ability("LOF", "205")
def _force_speed_lof_205_card():
    """LOF_205 — Force Speed (Event, Force, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_force_speed_lof_205)])


def _babu_frik_lof_206(state, source_ci, target_id, event_ctx):
    """"You may attack with a friendly Droid unit.  For this attack, it deals damage
    equal to its remaining HP instead of its power."  The granted-attack seam with
    the new ``power_equals_remaining_hp`` rider — expressed as a this_attack stats
    shift, so every damage site (combat, Overwhelm spill) reads one number."""
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True,
                        attacker_trait="Droid",
                        power_equals_remaining_hp=True)
    return state


@card_ability("LOF", "206")
def _babu_frik_lof_206_card():
    """LOF_206 — Babu Frik (Unit, Underworld, 1/4): "Action [Exhaust]: You may attack
    with a friendly Droid unit.  For this attack, it deals damage equal to its
    remaining HP instead of its power."

    The decision carries its own decline (``optional``), so the "you may" is the
    granted attack itself."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_babu_frik_lof_206)],
        title="Attack with a Droid unit (damage = its remaining HP)",
    )


@card_ability("LOF", "212")
def _life_wind_sage_lof_212():
    """LOF_212 — Life Wind Sage (Unit, Force, 3/5, Raid): "While an enemy unit is
    exhausted, this unit gains Raid 2."

    The conditional SELF ``KeywordGrant`` on ``ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS``
    (Blade Squadron B-Wing JTL_199), whose "another player" reading is exactly "an
    ENEMY unit" — a wall of exhausted friendlies never satisfies it.  (The upstream
    data leaves this card's keyword bar empty, so nothing needs stripping; the
    printed "Raid" in the card text is this ability's own reminder.)"""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Raid", value=2)],
        condition=ConditionCheck(
            Condition.ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS, param=1),
    )


# ── lof-set:16 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "215")
def _ascension_cable_lof_215():
    """LOF_215 — Ascension Cable (Upgrade, Item, cost 2): "Attach to a non-Vehicle
    unit.  Attached unit gains Saboteur."

    The unconditional upgrade-SELF ``KeywordGrant`` — the only path an upgrade's
    keyword reaches its host (Grievous's Wheel Bike TWI_236).  "Attach to a
    non-Vehicle unit" is the ``_upgrade_target_spec`` text parser."""
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant(keyword="Saboteur", value=0)],
    )


def _disturbance_in_the_force_lof_216(state, source_ci, target_id, event_ctx):
    """"If a friendly unit left play this phase, the Force is with you (create your
    Force token) and you may give a Shield token to a unit."

    An ``EventAbility`` carries no ``condition``, and ``ConditionalEffect`` cannot
    hold a *targeted* sub-effect — so the gate, the token and the optional Shield all
    live in one ``CustomEffect``: nothing is offered when the gate fails (no stray
    prompt), and the Shield is the ``select_token`` decision whose always-available
    finish IS the "you may"."""
    from swu.abilities.registry import Condition, ConditionCheck
    from swu.engine.actions import push_select_token
    gate = ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE)
    if not gate.evaluate(state, source_ci):
        return state
    state.player_by_id(source_ci.owner_id).has_force_token = True
    push_select_token(state, source_ci, token_type="Shield", max_targets=1,
                      controller="any", kind="unit")
    return state


@card_ability("LOF", "216")
def _disturbance_in_the_force_lof_216_card():
    """LOF_216 — Disturbance in the Force (Event, Force, cost 1).

    DEVIATION: "left play" is read as ``CONTROLLER_UNIT_DEFEATED_THIS_PHASE`` — the
    engine keeps no "left play" ledger, and defeat is how a unit leaves play in every
    case bar a bounce to hand."""
    return EventAbility(effects=[
        CustomEffect(fn=_disturbance_in_the_force_lof_216)])


def _shien_flurry_lof_220(state, source_ci, target_id, event_ctx):
    """"Play a Force unit from your hand (paying its cost).  It gains Ambush for this
    phase.  The next time it would be dealt damage this phase, prevent 2 of that
    damage."  The play-from-hand seam with ``grant_keyword`` (which lands before the
    enter-play keyword bus, so the granted Ambush triggers on entry) plus the new
    one-shot ``then_prevent_next_damage`` rider."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, trait="Force",
                        grant_keyword="Ambush", then_prevent_next_damage=2)
    return state


@card_ability("LOF", "220")
def _shien_flurry_lof_220_card():
    """LOF_220 — Shien Flurry (Event, Learned, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_shien_flurry_lof_220)])


def _trust_your_instincts_lof_221(state, source_ci, target_id, event_ctx):
    """"Use the Force.  If you do, attack with a unit.  It gets +2/+0 for this attack
    and deals its combat damage before the defender."  The spend gates the attack in
    ONE effect (Bright Hope SOR_99); "deals its combat damage before the defender" is
    First Strike, granted for the attack (Shoot First SOR_216's ``grant_keywords``)."""
    from swu.engine.actions import push_granted_attack, spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    push_granted_attack(state, source_ci, power_bonus=2,
                        grant_keywords=["First Strike"])
    return state


@card_ability("LOF", "221")
def _trust_your_instincts_lof_221_card():
    """LOF_221 — Trust Your Instincts (Event, Force, cost 1)."""
    return EventAbility(effects=[CustomEffect(fn=_trust_your_instincts_lof_221)])


@card_ability("LOF", "223")
def _force_illusion_lof_223():
    """LOF_223 — Force Illusion (Event, Force/Trick, cost 2): "Exhaust an enemy unit.
    A friendly unit gains Sentinel for this phase."

    Two sentences, two different units — so two effects with their own TargetSpecs
    (the General Grievous TWI_15 "bind them into one CustomEffect" rule applies only
    when the SAME chosen unit takes both)."""
    return EventAbility(effects=[
        ExhaustCard(TargetSpec(controller="enemy", kind="unit")),
        GrantKeyword("Sentinel", 0,
                     TargetSpec(controller="friendly", kind="unit"),
                     Duration.THIS_PHASE),
    ])


def _pounce_lof_224(state, source_ci, target_id, event_ctx):
    """"Attack with a Creature unit.  It gets +4/+0 for this attack." """
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=4,
                        attacker_trait="Creature")
    return state


@card_ability("LOF", "224")
def _pounce_lof_224_card():
    """LOF_224 — Pounce (Event, Trick, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_pounce_lof_224)])


def _three_lessons_lof_225(state, source_ci, target_id, event_ctx):
    """"Play a unit from your hand (paying its cost).  It gains Hidden for this
    phase.  Give an Experience token and a Shield token to it."  ``grant_keyword``
    for the Hidden plus the new ``then_tokens`` rider — the tokens land on the played
    unit with no choice to make, so this is not the ``then_select_token`` rider."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, grant_keyword="Hidden",
                        then_tokens=["Experience", "Shield"])
    return state


@card_ability("LOF", "225")
def _three_lessons_lof_225_card():
    """LOF_225 — Three Lessons (Event, Learned, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_three_lessons_lof_225)])


# ── lof-set:17 — Combat tricks, buffs & tempo ─────────────────────────────────

@card_ability("LOF", "237")
def _the_son_lof_237():
    """LOF_237 — The Son (Unit, Force, 6/8): "While the Force is with you, each
    friendly unit gets +2/+0."

    A conditional anthem — the ``CONTROLLER_HAS_FORCE_TOKEN`` gate on a friendly-unit
    ``StatBonus`` aura.  "Each friendly unit" is not "other", so The Son buffs himself
    too."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit"),
        effects=[StatBonus(power=2, hp=0)],
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


def _in_the_shadows_lof_241(state, source_ci, target_id, event_ctx):
    """"Give an Experience token to each of up to 3 friendly units with Hidden."  The
    ``select_token`` decision (Medal Ceremony's shape) narrowed by the new
    ``has_hidden`` predicate — "up to 3" is ``max_targets`` plus the always-available
    finish."""
    from swu.engine.actions import push_select_token
    push_select_token(state, source_ci, token_type="Experience", max_targets=3,
                      controller="friendly", kind="unit",
                      predicates=["has_hidden"])
    return state


@card_ability("LOF", "241")
def _in_the_shadows_lof_241_card():
    """LOF_241 — In the Shadows (Event, Plan, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_in_the_shadows_lof_241)])


@card_ability("LOF", "244")
def _jedi_vector_lof_244():
    """LOF_244 — Jedi Vector (Unit, Fighter/Jedi/Vehicle, 1/3): "This unit gets +1/+0
    if you control another Jedi unit and +1/+0 if you control a Lightsaber upgrade."

    Two independent conditional SELF buffs, so both can apply at once (the printed
    "and").  The Vector is itself a Jedi, hence ``CONTROLLER_HAS_OTHER_TRAIT_UNIT``
    for "another"; the Lightsaber clause is ``CONTROLLER_HAS_TRAIT_CARD_IN_PLAY``,
    whose basis includes every attached upgrade — which is where a Lightsaber
    lives."""
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0)],
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT, param="Jedi"),
        ),
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            effects=[StatBonus(power=1, hp=0)],
            condition=ConditionCheck(
                Condition.CONTROLLER_HAS_TRAIT_CARD_IN_PLAY, param="Lightsaber"),
        ),
    ]


@card_ability("LOF", "250")
def _medical_frigate_lof_250():
    """LOF_250 — Medical Frigate (Unit, Capital Ship/Republic/Vehicle, 3/6): "On
    Attack: You may heal 2 damage from another unit."

    The optional ``OnAttack`` ``Heal`` — "another unit" names no controller, so
    ``controller="any"`` with ``not_self`` (2-1B Surgical Droid SOR_59's wording)."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                    predicates=("not_self",)))],
        optional=True,
    )


def _the_daughter_lof_252(state, source_ci, target_id, event_ctx):
    """"Use the Force (lose your Force token).  If you do, heal 2 damage from your
    base."  Spend and payoff in ONE ``CustomEffect`` (Bright Hope SOR_99); the heal
    routes through ``_apply_heal`` so Wolffe SOR_160's "bases can't be healed" lock
    still applies.  "Your base" is fixed, so there is nothing to target."""
    from swu.engine.actions import spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    base = ps.base_instance
    if base is None or not spend_force_token(state, ps):
        return state
    from swu.abilities.resolver import _apply_heal
    return _apply_heal(state, source_ci, base.instance_id, 2)


@card_ability("LOF", "252")
def _the_daughter_lof_252_card():
    """LOF_252 — The Daughter (Unit, Force, 4/6): "When damage is dealt to your base:
    You may use the Force (lose your Force token).  If you do, heal 2 damage from
    your base."

    The new ``WhenDamageDealtToYourBase`` observer (fired at the settle point from
    the base-damage ledger, so it covers a base attack, an ability, and indirect
    damage alike), gated on ``CONTROLLER_HAS_FORCE_TOKEN`` so it is never offered
    with nothing to spend."""
    return TriggerAbility(
        trigger=WhenDamageDealtToYourBase(),
        effects=[CustomEffect(fn=_the_daughter_lof_252)],
        optional=True,
        condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
    )


@card_ability("LOF", "258")
def _peli_motto_lof_258():
    """LOF_258 — Peli Motto (Unit, Fringe, 1/4): "On Attack: Give an Experience token
    to a friendly Vehicle or Droid unit."

    The new ``traits_any`` TargetSpec filter — the OR sibling of ``traits`` (which
    demands ALL).  Mandatory, and Peli is neither a Vehicle nor a Droid, so it always
    points at something else when there is anything to point at."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[GiveToken("Experience", TargetSpec(
            controller="friendly", kind="unit",
            traits_any=("Vehicle", "Droid"),
        ))],
    )


def _last_words_lof_263(state, source_ci, target_id, event_ctx):
    """"If a friendly unit was defeated this phase, give 2 Experience tokens to a
    unit."  An ``EventAbility`` carries no ``condition``, so the gate lives in the
    effect (Disturbance in the Force LOF_216's recipe): nothing is offered when no
    friendly unit died, and the tokens ride the ``select_token`` decision with
    ``token_count=2``."""
    from swu.abilities.registry import Condition, ConditionCheck
    from swu.engine.actions import push_select_token
    gate = ConditionCheck(Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE)
    if not gate.evaluate(state, source_ci):
        return state
    push_select_token(state, source_ci, token_type="Experience", max_targets=1,
                      controller="any", kind="unit", token_count=2)
    return state


@card_ability("LOF", "263")
def _last_words_lof_263_card():
    """LOF_263 — Last Words (Event, Learned, cost 2)."""
    return EventAbility(effects=[CustomEffect(fn=_last_words_lof_263)])


# ── lof-set:18 — Miscellaneous abilities ──────────────────────────────────────

@card_ability("LOF", "2")
def _mother_talzin_lof_2():
    """LOF_2 — Mother Talzin (Leader, Force/Night, 3/7).

    * undeployed: "Action [Exhaust, use the Force]: Give a unit −1/−1 for this
      phase."  Both costs must be payable, so the action disappears without a Force
      token (Adept of Anger LOF_178's shape).
    * deployed: "On Attack: You may give a unit −1/−1 for this phase."  No Force cost
      on this side — the "you may" is the optional trigger.

    The Epic Action deploy is the standard ``deploy_threshold`` machinery — no
    registration."""
    _any_unit = TargetSpec(controller="any", kind="unit")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[ModifyStats(power=-1, hp=-1, target=_any_unit,
                                 duration=Duration.THIS_PHASE)],
            title="Give a unit -1/-1",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[ModifyStats(power=-1, hp=-1, target=_any_unit,
                                 duration=Duration.THIS_PHASE)],
            optional=True,
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "3")
def _ahsoka_tano_lof_3():
    """LOF_3 — Ahsoka Tano (Leader, Force/Fringe, 5/6, Sentinel).

    Mother Talzin LOF_2's two-sided shape, with a friendly Sentinel grant as the
    payoff: undeployed "Action [Exhaust, use the Force]", deployed "On Attack: You
    may".  Her printed Sentinel is a genuine keyword-bar entry (the text grants
    Sentinel to *another* unit, never to herself), so the sanitiser keeps it."""
    _friendly = TargetSpec(controller="friendly", kind="unit")
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[GrantKeyword("Sentinel", 0, _friendly, Duration.THIS_PHASE)],
            title="Give a friendly unit Sentinel",
            undeployed_only=True,
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[GrantKeyword("Sentinel", 0, _friendly, Duration.THIS_PHASE)],
            optional=True,
            deployed_only=True,
        ),
    ]


def _third_sister_lof_10_play(state, source_ci, target_id, event_ctx):
    """Undeployed Action: "Play a unit from your hand.  It gains Hidden for this
    phase."  ``grant_keyword`` lands before the enter-play keyword bus, so the
    granted Hidden is live from the moment the unit arrives."""
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, grant_keyword="Hidden")
    return state


def _third_sister_lof_10_arm(state, source_ci, target_id, event_ctx):
    """Deployed On Attack: "The next unit you play this phase gains Hidden" — the
    ``pending_keyword_grants`` seam (Deceptive Shade LOF_180)."""
    state.game_memory.pending_keyword_grants.append(
        {"player_id": source_ci.owner_id, "trait": "", "keyword": "Hidden"})
    return state


@card_ability("LOF", "10")
def _third_sister_lof_10():
    """LOF_10 — Third Sister (Leader, Force/Imperial/Inquisitor, 5/4, Hidden).

    * undeployed: "Action [Exhaust]: Play a unit from your hand.  It gains Hidden for
      this phase."
    * deployed: Hidden (the keyword bar, with its own reminder text — genuinely hers)
      + "On Attack: The next unit you play this phase gains Hidden."

    The undeployed action is gated on ``CONTROLLER_CAN_PLAY_UNIT_FROM_HAND`` so the
    exhaust is never spent on nothing (Bib Fortuna SOR_177's rule)."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf()],
            effects=[CustomEffect(fn=_third_sister_lof_10_play)],
            title="Play a unit from hand (it gains Hidden)",
            undeployed_only=True,
            condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND),
        ),
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_third_sister_lof_10_arm)],
            deployed_only=True,
        ),
    ]


def _anakin_skywalker_lof_18(state, source_ci, target_id, event_ctx):
    """"Play a Villainy non-unit card from your hand, ignoring its aspect penalties."

    The ``play_event_from_hand`` decision whitelisted to the controller's Villainy
    EVENTS, with the new ``ignore_aspect_penalty`` rider waiving the whole penalty.
    DEVIATION: "non-unit" also covers upgrades, which live on a different decision
    kind (``play_upgrade_from_hand``) and so cannot share one choice — the event half
    is offered."""
    from swu.engine.actions import push_play_event_from_hand
    from swu.cards.models import Event
    ps = state.player_by_id(source_ci.owner_id)
    eligible = {c.instance_id for c in ps.hand
                if isinstance(c.card_def, Event)
                and "Villainy" in {a.name for a in
                                   (getattr(c.card_def, "aspects", None) or ())}}
    if not eligible:
        return state
    push_play_event_from_hand(state, source_ci, eligible_ids=eligible,
                              ignore_aspect_penalty=True)
    return state


@card_ability("LOF", "18")
def _anakin_skywalker_lof_18_card():
    """LOF_18 — Anakin Skywalker (Leader, Force/Jedi/Republic, 4/6).

    * undeployed: "Action [Exhaust, use the Force]: Play a Villainy non-unit card
      from your hand, ignoring its aspect penalties."
    * deployed: "Action [use the Force]: …" — the same play with no exhaust, so a
      deployed Anakin can still attack the round he uses it."""
    return [
        ActivatedAbility(
            costs=[ExhaustSelf(), UseForce()],
            effects=[CustomEffect(fn=_anakin_skywalker_lof_18)],
            title="Play a Villainy non-unit card (ignoring aspect penalties)",
            undeployed_only=True,
        ),
        ActivatedAbility(
            costs=[UseForce()],
            effects=[CustomEffect(fn=_anakin_skywalker_lof_18)],
            title="Play a Villainy non-unit card (ignoring aspect penalties)",
            deployed_only=True,
        ),
    ]


@card_ability("LOF", "19")
def _vergence_temple_lof_19():
    """LOF_19 — Vergence Temple (Base): "When the regroup phase starts: If you
    control a unit with 4 or more remaining HP, the Force is with you."

    ``PhaseStartTrigger("regroup")`` plus the new
    ``CONTROLLER_HAS_UNIT_REMAINING_HP_MIN`` atom (effective HP less damage, so
    Experience tokens and buffs count and damage subtracts).  Bases are scanned for
    triggers (the Jedi Temple LOF_23 base_zone scan)."""
    return TriggerAbility(
        trigger=PhaseStartTrigger("regroup"),
        effects=[CreateForceToken()],
        condition=ConditionCheck(
            Condition.CONTROLLER_HAS_UNIT_REMAINING_HP_MIN, param=4),
    )


@card_ability("LOF", "20")
def _nightsister_lair_lof_20():
    """LOF_20 — Nightsister Lair (Base): "When a friendly Force unit attacks: The
    Force is with you (create your Force token)."

    Word-for-word Jedi Temple LOF_23, so it is that card's registration verbatim —
    the ``WhenUnitAttacks`` observer with a friendly-Force filter."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(filter=TargetSpec(
            controller="friendly", kind="unit", traits=("Force",))),
        effects=[CreateForceToken()],
    )


@card_ability("LOF", "22")
def _mystic_monastery_lof_22():
    """LOF_22 — Mystic Monastery (Base): "Action: The Force is with you (create your
    Force token).  Use this ability no more than 3 times each game."

    A costless activated ability gated by the new ``SOURCE_ABILITY_USES_MAX`` atom,
    which reads the per-game tally ``UseAbility`` keeps for every activated ability —
    the game-scoped sibling of ``once_per_round`` (and of ``epic``'s once-per-game
    set), expressed as a condition so it needs no new gate at each enumeration
    site."""
    return ActivatedAbility(
        costs=[],
        effects=[CreateForceToken()],
        title="The Force is with you",
        condition=ConditionCheck(Condition.SOURCE_ABILITY_USES_MAX, param=3),
    )


# ── lof-set:19 — Force-token Bases ────────────────────────────────────────────
# Seven Bases, all payoffs for the Force-token primitive (qui-gon-jinn:06).  Five
# are Jedi Temple LOF_23 word for word; the two that differ are LOF_25 (the new
# observer form of WhenDealsCombatDamageToBase) and LOF_28 (an Action whose
# "exhaust a friendly unit" cost is modelled as a targeted ExhaustCard effect).


def _force_base_when_friendly_force_unit_attacks():
    """The shared body of the five Bases whose text is Jedi Temple LOF_23 verbatim:
    "When a friendly Force unit attacks: The Force is with you (create your Force
    token)."  A ``WhenUnitAttacks`` observer filtered to friendly Force units; Bases
    are collected for triggers by the base_zone scan in ``_collect_triggers``."""
    return TriggerAbility(
        trigger=WhenUnitAttacks(filter=TargetSpec(
            controller="friendly", kind="unit", traits=("Force",))),
        effects=[CreateForceToken()],
    )


@card_ability("LOF", "24")
def _starlight_temple_lof_24():
    """LOF_24 — Starlight Temple (Base): "When a friendly Force unit attacks: The
    Force is with you."  Jedi Temple LOF_23 verbatim."""
    return _force_base_when_friendly_force_unit_attacks()


@card_ability("LOF", "26")
def _fortress_vader_lof_26():
    """LOF_26 — Fortress Vader (Base): "When a friendly Force unit attacks: The
    Force is with you."  Jedi Temple LOF_23 verbatim."""
    return _force_base_when_friendly_force_unit_attacks()


@card_ability("LOF", "27")
def _strangled_cliffs_lof_27():
    """LOF_27 — Strangled Cliffs (Base): "When a friendly Force unit attacks: The
    Force is with you."  Jedi Temple LOF_23 verbatim."""
    return _force_base_when_friendly_force_unit_attacks()


@card_ability("LOF", "29")
def _crystal_caves_lof_29():
    """LOF_29 — Crystal Caves (Base): "When a friendly Force unit attacks: The
    Force is with you."  Jedi Temple LOF_23 verbatim."""
    return _force_base_when_friendly_force_unit_attacks()


@card_ability("LOF", "30")
def _the_holy_city_lof_30():
    """LOF_30 — The Holy City (Base): "When a friendly Force unit attacks: The
    Force is with you."  Jedi Temple LOF_23 verbatim."""
    return _force_base_when_friendly_force_unit_attacks()


@card_ability("LOF", "25")
def _temple_of_destruction_lof_25():
    """LOF_25 — Temple of Destruction (Base): "When a friendly unit deals 3 or more
    combat damage to an enemy base: The Force is with you (create your Force
    token)."

    ``WhenDealsCombatDamageToBase`` in its new OBSERVER form: ``filter`` makes a
    *different* card (here a Base) fire for the unit that dealt the damage — the
    ``WhenFriendlyUnitDealtCombatDamage`` group-analogue shape — and ``min_amount``
    reads the ``base_combat_damage_amount`` now carried in the same event_ctx.  A
    friendly unit attacking a base always hits the ENEMY base, so
    ``controller="friendly"`` is the entire filter."""
    return TriggerAbility(
        trigger=WhenDealsCombatDamageToBase(
            filter=TargetSpec(controller="friendly", kind="unit"),
            min_amount=3,
        ),
        effects=[CreateForceToken()],
    )


@card_ability("LOF", "28")
def _tomb_of_eilram_lof_28():
    """LOF_28 — Tomb of Eilram (Base): "Action [exhaust a friendly unit]: The Force
    is with you (create your Force token)."

    There is no "exhaust a friendly unit" COST spec (``ExhaustSelf`` would exhaust
    the Base), so the cost is modelled as the first EFFECT — a targeted
    ``ExhaustCard`` over friendly ready units — with the ability gated by
    ``CONTROLLER_HAS_READY_UNIT_COST_MAX`` (``param=None`` = "any ready unit") so it
    is never offered when the cost could not be paid.  Cost-as-leading-effect plus a
    payability gate is behaviourally the same here: both steps resolve together and
    the controller still chooses *which* unit to exhaust."""
    return ActivatedAbility(
        costs=[],
        effects=[
            ExhaustCard(target=TargetSpec(
                controller="friendly", kind="unit", predicates=("ready",))),
            CreateForceToken(),
        ],
        title="Exhaust a friendly unit: The Force is with you",
        condition=ConditionCheck(Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX),
    )


# ── lof-set:20 — Miscellaneous abilities ──────────────────────────────────────


@card_ability("LOF", "44")
def _loth_wolf_lof_44():
    """LOF_44 — Loth-Wolf (Creature 3/3, Sentinel): "This unit can't attack."

    Sentinel is the keyword layer.  The restriction is the unconditional
    ``AttackRestriction`` passive marker (``condition=None`` — Corporate Defense
    Shuttle JTL_59's unconditional bar), read at ``legal_actions`` so it is never
    offered as an attacker; it still defends, which is the whole point of a
    Sentinel wall."""
    return AttackRestriction()


@card_ability("LOF", "73")
def _mythosaur_lof_73():
    """LOF_73 — Mythosaur (Creature/Mandalorian 10/10, Shielded):
    "Friendly upgraded units can't be exhausted or returned to hand by enemy card
     abilities.
     Friendly leaders gain the Mandalorian trait."

    Two arena-wide ``ConstantAbility`` auras, one per clause:

    * The protection is the first AURA ``Protection`` in the game — every earlier
      one was self-targeted or rode an attached upgrade — so ``_target_protected``
      grew a third source, ``_aura_protection`` (a cached board scan for a non-SELF
      ConstantAbility Protection whose target matches).  ``upgraded`` is an existing
      predicate, and the "by enemy card abilities" clause is intrinsic to
      ``_target_protected``, which already ignores friendly sources.
    * The trait grant reuses the Malakili LAW_212 arena-wide ``TraitGrant`` scan
      with the new ``kind="leader"`` target — a leader card in play, deployed into
      an arena OR still undeployed in base_zone (a leader in hand grants nothing).

    Shielded is printed."""
    return [
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("upgraded",)),
            effects=[Protection(from_exhaust=True, from_return=True)],
        ),
        ConstantAbility(
            target=TargetSpec(controller="friendly", kind="leader"),
            effects=[TraitGrant("Mandalorian")],
        ),
    ]


def _whirlwind_of_power_lof_78(state, source_ci, target_id, event_ctx):
    """Give the chosen unit -2/-2 for this phase, or -3/-3 if the controller
    controls a Force unit."""
    from swu.engine.traits import has_trait
    ctrl = state.player_by_id(source_ci.owner_id)
    force = any(has_trait(state, u, "Force")
                for u in (*ctrl.ground_arena, *ctrl.space_arena))
    amount = 3 if force else 2
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id,
        power=-amount, hp=-amount, duration=Duration.THIS_PHASE,
    ))
    return state


@card_ability("LOF", "78")
def _whirlwind_of_power():
    """LOF_78 — Whirlwind of Power (Event, Force, cost 3): "Give a unit –2/–2 for
    this phase.  If you control a Force unit, give it –3/–3 instead."

    One ``CustomEffect`` with a ``target``: an ``EventAbility`` has no ``condition``
    field and a ``ConditionalEffect`` can't carry a *targeted* sub-effect, so the
    "instead" branch is decided inside the effect once the target is chosen — the
    LOF_216/263 shape.  The debuff is the ordinary phase-duration ``stat_bonus``
    modifier with negative values (compute_power/compute_hp floor at 0)."""
    return EventAbility(effects=[CustomEffect(
        fn=_whirlwind_of_power_lof_78,
        target=TargetSpec(controller="any", kind="unit"))])


def _jedi_consular_lof_94(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci, cost_reduction=2)
    return state


@card_ability("LOF", "94")
def _jedi_consular():
    """LOF_94 — Jedi Consular (Force/Jedi 1/4): "Action [Exhaust, use the Force
    (lose your Force token)]: Play a unit from your hand.  It costs 2 resources
    less."

    Pure composition: the ``ExhaustSelf`` + ``UseForce`` cost pair (Qui-Gon Jinn
    LOF_16) driving ``push_play_from_hand(cost_reduction=2)`` (Han Solo SHD_13).
    ``UseForce`` already gates the ability on holding a Force token."""
    return ActivatedAbility(
        costs=[ExhaustSelf(), UseForce()],
        effects=[CustomEffect(fn=_jedi_consular_lof_94)],
        title="Play a unit from your hand for 2 less",
    )


def _following_the_path_lof_103(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    from swu.engine.traits import has_trait  # noqa: F401 — see the eligible note

    def _eligible(card_def):
        from swu.cards.models import Unit
        return (isinstance(card_def, Unit)
                and "Force" in (getattr(card_def, "traits", None) or ()))

    push_deck_search(state, source_ci, count=2, eligible=_eligible, up_to=True,
                     window=8, disposition="top")
    return state


@card_ability("LOF", "103")
def _following_the_path():
    """LOF_103 — Following the Path (Event, Plan, cost 1): "Search the top 8 cards
    of your deck for up to 2 Force units, reveal them, and put them on top of your
    deck in any order.  (Put the other cards on the bottom of your deck in a random
    order.)"

    ``push_deck_search`` with the new ``disposition="top"``: instead of drawing the
    chosen cards it puts them back on TOP, in selection order (the reveal_top
    SOR_152 click-order convention for "in any order").  The un-taken cards ride the
    default ``rest_disposition="bottom"`` — bottom in a seeded-random order, exactly
    as printed.  Eligibility reads the PRINTED traits of a card_def in the deck (no
    instance exists to carry a granted trait)."""
    return EventAbility(effects=[CustomEffect(fn=_following_the_path_lof_103)])


@card_ability("LOF", "114")
def _kaadu_lof_114():
    """LOF_114 — Kaadu (Creature 4/4, Overwhelm): "When Played: You may give
    another friendly unit Overwhelm for this phase."

    An optional ``WhenPlayed`` ``GrantKeyword`` with the ``not_self`` predicate for
    "another"; with no other friendly unit on the board the optional trigger
    auto-declines rather than prompting."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GrantKeyword(
            "Overwhelm", 0,
            TargetSpec(controller="friendly", kind="unit",
                       predicates=("not_self",)),
            Duration.THIS_PHASE,
        )],
        optional=True,
    )


def _directed_by_the_force_lof_123(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_play_from_hand
    push_play_from_hand(state, source_ci)
    return state


@card_ability("LOF", "123")
def _directed_by_the_force():
    """LOF_123 — Directed by the Force (Event, Force, cost 1): "The Force is with
    you (create your Force token).  You may play a unit from your hand (paying its
    cost)."

    ``CreateForceToken`` then ``push_play_from_hand`` (full price).  DEVIATION
    (documented, the standing play_from_hand convention): the decision has no
    decline, so "you may" collapses to mandatory whenever an affordable hand unit
    exists — the decision simply isn't pushed when none does."""
    return EventAbility(effects=[
        CreateForceToken(),
        CustomEffect(fn=_directed_by_the_force_lof_123),
    ])


# ── lof-set:21 — Miscellaneous abilities ──────────────────────────────────────


def _protect_the_pod_pick_dealer(state, source_ci, target_id, event_ctx):
    """Stage 1: remember which friendly non-Vehicle unit is dealing the damage."""
    event_ctx["prior_target_id"] = target_id
    return state


def _protect_the_pod_deal(state, source_ci, target_id, event_ctx):
    """Stage 2: the remembered unit deals damage equal to its remaining HP."""
    dealer_id = event_ctx.get("prior_target_id")
    res = state.find_instance(dealer_id) if dealer_id else None
    if res is None or target_id is None:
        return state
    _, dealer = res
    from swu.engine.actions import compute_hp
    amount = max(0, compute_hp(state, dealer) - dealer.damage)
    if amount <= 0:
        return state
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(state, target_id, amount,
                              dealer.card_def.display_name)


@card_ability("LOF", "128")
def _protect_the_pod_lof_128():
    """LOF_128 — Protect the Pod (Event, Tactic, cost 4): "A friendly non-Vehicle
    unit deals damage equal to its remaining HP to an enemy unit."

    The two-stage ``prior_target_id`` chain (Asajj Ventress JTL_1): the first
    ``CustomEffect`` only records the chosen dealer, the second targets an enemy
    unit gated by the ``requires_prior_target`` predicate — so if the first choice
    never happened the second fizzles without prompting.  Remaining HP is
    ``compute_hp`` (effective, so Experience tokens and buffs count) less damage,
    the Leia LOF_206 reading."""
    return EventAbility(effects=[
        CustomEffect(
            fn=_protect_the_pod_pick_dealer,
            target=TargetSpec(controller="friendly", kind="unit",
                              predicates=("non_vehicle",))),
        CustomEffect(
            fn=_protect_the_pod_deal,
            target=TargetSpec(controller="enemy", kind="unit",
                              predicates=("requires_prior_target",))),
    ])


def _jedi_in_hiding_lof_159(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_use_force
    push_use_force(state, source_ci, payoff="opponents_discard")
    return state


@card_ability("LOF", "159")
def _jedi_in_hiding_lof_159_card():
    """LOF_159 — Jedi In Hiding (Force/Jedi 3/3, Hidden): "When Defeated: You may
    use the Force (lose your Force token).  If you do, each opponent discards a
    card from their hand."

    The ``use_force`` decision (qui-gon-jinn:06) with the new ``opponents_discard``
    payoff — a no-target rider, so the decision pops as soon as the token is spent.
    With no Force token nothing is pushed (the whole clause is "you may").  Hidden
    is the keyword layer."""
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[CustomEffect(fn=_jedi_in_hiding_lof_159)],
    )


@card_ability("LOF", "186")
def _marchion_ro_lof_186():
    """LOF_186 — Marchion Ro (Nihil/Underworld 6/7, Raid 1): "Each friendly unit's
    Raid is doubled."

    The new ``DoubleKeywordValue`` passive marker, read at the very end of
    ``keywords.keyword_value`` so it multiplies the EFFECTIVE Raid (printed value +
    every grant) rather than just the printed one.  Marchion Ro's own Raid is
    friendly to himself, so it doubles too — as printed ("each friendly unit")."""
    return DoubleKeywordValue(
        keyword="Raid",
        target=TargetSpec(controller="friendly", kind="unit"),
    )


def _liberated_by_darkness_lof_189(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import change_control, spend_force_token
    ps = state.player_by_id(source_ci.owner_id)
    if not spend_force_token(state, ps):
        return state
    res = state.find_instance(target_id)
    if res is None:
        return state
    _, target_ci = res
    change_control(state, target_ci, source_ci.owner_id)
    target_ci.return_control_to_owner_at_regroup = True
    return state


@card_ability("LOF", "189")
def _liberated_by_darkness():
    """LOF_189 — Liberated by Darkness (Event, Force, cost 5): "Use the Force (lose
    your Force token).  If you do, take control of a non-leader unit.  At the start
    of the regroup phase, its owner takes control of it."

    Change of Heart SOR_224 (``change_control`` +
    ``return_control_to_owner_at_regroup``) behind the ``controller_has_force_token``
    BOARD gate (Sorcerous Blast LOF_172): with no Force token the target spec yields
    no candidates, so the event fizzles without prompting — an ``EventAbility`` has
    no ``condition`` field.  The token is spent inside the effect, once the choice is
    made.  ``controller="enemy"`` is SOR_224's faithful-intent narrowing (taking a
    unit you already control does nothing)."""
    return EventAbility(effects=[CustomEffect(
        fn=_liberated_by_darkness_lof_189,
        target=TargetSpec(controller="enemy", kind="unit",
                          predicates=("non_leader", "controller_has_force_token")),
    )])


@card_ability("LOF", "209")
def _tusken_tracker_lof_209():
    """LOF_209 — Tusken Tracker (Tusken 2/4, Raid 2): "When Played: Each enemy unit
    loses Hidden for this phase."

    A plain ``RevokeKeyword`` over every enemy unit — the ``keyword_revoke``
    modifier the keyword query layer reads FIRST, so a revoked Hidden cannot be
    re-granted while it lasts, and ``_is_hidden_from_attack`` (which asks
    ``has_keyword``) stops protecting them."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[RevokeKeyword(
            "Hidden",
            TargetSpec(controller="enemy", kind="unit", fixed=EACH_ENEMY),
            Duration.THIS_PHASE,
        )],
    )


def _dooku_lof_211(state, source_ci, target_id, event_ctx):
    """Mark every friendly unit with Hidden as un-attackable for this phase."""
    from swu.engine.state import Modifier
    from swu.engine.keywords import has_keyword, Keyword
    ps = state.player_by_id(source_ci.owner_id)
    for unit in (*ps.ground_arena, *ps.space_arena):
        if not has_keyword(state, unit, Keyword.HIDDEN):
            continue
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=unit.instance_id,
            kind="cannot_be_attacked",
            value={},
            duration="this_phase",
        ))
    return state


@card_ability("LOF", "211")
def _dooku_lof_211_card():
    """LOF_211 — Dooku (Force/Jedi 5/4, Hidden): "When Played: Each friendly unit
    with Hidden can't be attacked for this phase."

    The ``cannot_be_attacked`` phase modifier (On Top of Things TWI_219), applied to
    each friendly unit that currently has Hidden — Dooku himself included, which is
    the point: it extends his protection past the phase he was played in, and covers
    Hidden units that were played earlier.  DEVIATION (inherited from that seam): the
    marker yields to Sentinel, which LOF_211 does not print; a friendly Hidden
    Sentinel unit stays attackable."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_dooku_lof_211)],
    )


@card_ability("LOF", "217")
def _force_slow_lof_217():
    """LOF_217 — Force Slow (Event, Force, cost 1): "Give an exhausted unit
    –8/–0 for this phase."

    A plain ``ModifyStats`` over the ``exhausted`` predicate (Stinger Mantis
    LOF_198's target shape); ``controller="any"`` since the printed text does not
    restrict it, and ``compute_power`` floors at 0."""
    return EventAbility(effects=[ModifyStats(
        power=-8, hp=0,
        target=TargetSpec(controller="any", kind="unit",
                          predicates=("exhausted",)),
        duration=Duration.THIS_PHASE,
    )])


# ── lof-set:22 — Miscellaneous abilities (completes the LOF set) ──────────────


def _jocasta_nu_lof_248(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_move_upgrade
    push_move_upgrade(state, source_ci, host_controller_id=source_ci.owner_id)
    return state


@card_ability("LOF", "248")
def _jocasta_nu_lof_248_card():
    """LOF_248 — Jocasta Nu (Force/Jedi/Republic 3/4): "When Played: You may attach
    a friendly upgrade on a friendly unit to a different eligible unit."

    A thin adapter onto the ``move_upgrade`` decision (Survivors' Gauntlet SHD_64)
    with the new ``host_controller_id`` filter, which pins the upgrade's CURRENT
    host to a unit the controller controls — the board-wide default admits enemy
    hosts.  Destinations were already restricted to the host's own controller, so
    both ends end up friendly, and ``push_move_upgrade`` only pushes when something
    can really move, so the "you may" is never a dead prompt."""
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_jocasta_nu_lof_248)],
    )


def _go_into_hiding_lof_262(state, source_ci, target_id, event_ctx):
    from swu.engine.state import Modifier
    if target_id is None:
        return state
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="cannot_be_attacked",
        value={},
        duration="this_phase",
    ))
    return state


@card_ability("LOF", "262")
def _go_into_hiding_lof_262_card():
    """LOF_262 — Go Into Hiding (Event, Tactic, cost 2): "Choose a unit.  It can't
    be attacked this phase (unless it has Sentinel)."

    The ``cannot_be_attacked`` phase modifier read at ``_cannot_be_attacked`` (On
    Top of Things TWI_219) — including that seam's printed Sentinel escape, which
    this card prints too.  ``controller="any"``: the printed text says "a unit", and
    the choice is the controller's."""
    return EventAbility(effects=[CustomEffect(
        fn=_go_into_hiding_lof_262,
        target=TargetSpec(controller="any", kind="unit"),
    )])
