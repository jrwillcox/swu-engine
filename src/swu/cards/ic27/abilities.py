"""IC27 (Icons 2027 Edition) card ability registrations.

Imported for its side effects (the ``@card_ability`` decorators populate the
registry).  Encoded group by group via ``/encode-next``; the plan lives in
``encoding/ic27-set/``.  Run the reprint sweep (``scripts/find_reprints.py``)
before encoding here: a card whose printed face matches an implemented card is
aliased in ``swu/cards/reprints.py``, not re-encoded.

⚠️ **TOKEN COLLISIONS**: ``IC27_1`` Darth Vader (Leader) shares its registry key
with the Experience token UPGRADE, and ``IC27_2`` Rey (Leader) with the Shield
token UPGRADE.  Register those leaders ONLY from spec kinds a token can never
reach (see the same warning in ``swu/cards/ts26/abilities.py``):
``ActivatedAbility(undeployed_only=True)``, ``TriggerAbility(WhenDeployed())`` and
``TriggerAbility(deployed_only=True)``.
"""
from __future__ import annotations

from swu.engine.actor import actor_of

from swu.abilities.registry import (
    card_ability,
    TriggerAbility, ActivatedAbility, EventAbility,
    WhenPlayed, OnAttack, WhenDefeated, WhenYouPlayCard, WhenYouHealYourBase,
    DealDamage, DealDamageEqualTo, DrawCards, CustomEffect, DefeatUnit,
    ExhaustSelf, PayResources,
    Duration, TargetSpec, EACH_ENEMY, EACH_FRIENDLY, Heal,
    WhenDeployed, GiveToken, ModifyStats, DiscardCardCost, ConditionCheck, Condition,
    PlayFromDiscardAction, StartingHandModifier, ExtraRegroupDraw, NextPlayDiscount,
)
from swu.engine.discard_payoffs import discard_payoff

_IN_ARENA = ("GROUND_ARENA", "SPACE_ARENA")
_ANY_UNIT = TargetSpec(controller="any", kind="unit")
_ENEMY_UNIT = TargetSpec(controller="enemy", kind="unit")


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:01 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("IC27", "26")
def _darth_sidious_ic27():
    """IC27_26 — Darth Sidious (Unit, Force/Sith, 5/8): "Restore 3.  When you heal
    damage from your base: Deal that much damage to an enemy unit."

    The ``WhenYouHealYourBase`` observer over ``game_memory.base_heal_events`` (fed
    by ``note_base_healed`` at every base-heal site); "that much" is the stock
    ``event_healed_amount`` count.  His own Restore 3 resolves the trigger inside
    the attack, before combat damage (``combat._pause_for_base_heal_triggers``).
    Mandatory: with no enemy unit it simply does nothing.  Restore is the keyword
    layer."""
    return TriggerAbility(
        trigger=WhenYouHealYourBase(),
        effects=[DealDamageEqualTo(target=_ENEMY_UNIT, count="event_healed_amount")])


@card_ability("IC27", "5")
def _darth_maul_ic27():
    """IC27_5 — Darth Maul (Leader, Force/Sith, 4/5).

    Undeployed: "Action [1 resource, Exhaust]: Deal 1 damage to a unit."
    Deployed: "On Attack: You may deal 1 damage to a unit."  The Epic Action deploy
    is generic."""
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()],
                         effects=[DealDamage(1, _ANY_UNIT)],
                         title="Deal 1 damage to a unit", undeployed_only=True),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[DealDamage(1, _ANY_UNIT)]),
    ]


def _dryden_test_and_reward(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.tokens import attach_token
    if not target_id:
        return state
    _apply_deal_damage(state, target_id, 1, source_ci.card_def.display_name,
                       dealer_id=actor_of(state, source_ci),
                       source_id=source_ci.instance_id)
    live = state.find_instance(target_id)
    if live is not None and live[1].zone.name in _IN_ARENA:   # "If it survives"
        attach_token(state, live[0], live[1], "Experience")
    return state


@card_ability("IC27", "14")
def _dryden_vos_ic27():
    """IC27_14 — Dryden Vos (Unit, Underworld, 1/4): "On Attack: You may deal 1
    damage to a friendly unit.  If it survives, give an Experience token to it." """
    return TriggerAbility(
        trigger=OnAttack(), optional=True,
        effects=[CustomEffect(fn=_dryden_test_and_reward,
                              target=TargetSpec(controller="friendly", kind="unit"))])


def _bb8_heal_then(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_heal
    from swu.cards.hmw.abilities import _then_resolve_option
    live = state.find_instance(target_id) if target_id else None
    if live is None or live[1].damage <= 0:
        return state
    before = live[1].damage
    _apply_heal(state, source_ci, target_id, 1)
    after = state.find_instance(target_id)
    if after is not None and after[1].damage < before:        # "If you do"
        _then_resolve_option(state, source_ci, 1)
    return state


@card_ability("IC27", "31")
def _bb8_ic27():
    """IC27_31 — BB-8 (Unit, Droid/Resistance, 0/4): "On Attack: Heal 1 damage from
    a friendly unit.  If you do, deal 1 damage to an enemy unit."

    The heal targets a damaged friendly unit; once it heals, option 1 (an
    ``EventAbility``, so it is never trigger-collected) resolves the damage with
    its target chosen then."""
    return [
        TriggerAbility(
            trigger=OnAttack(),
            effects=[CustomEffect(fn=_bb8_heal_then,
                                  target=TargetSpec(controller="friendly", kind="unit",
                                                    predicates=("damaged",)))]),
        EventAbility(effects=[DealDamage(1, _ENEMY_UNIT)]),
    ]


@card_ability("IC27", "39")
def _ahsoka_tano_ic27():
    """IC27_39 — Ahsoka Tano (Unit, Force/Jedi/Republic, 4/5): "When Played: You
    may defeat a unit that costs 3 or less." """
    return TriggerAbility(
        trigger=WhenPlayed(), optional=True,
        effects=[DefeatUnit(TargetSpec(controller="any", kind="unit", cost_max=3))])


def _talzin_raise(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_play_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    eligible = frozenset(
        c.instance_id for c in ps.discard
        if isinstance(c.card_def, Unit) and (c.card_def.cost or 0) <= 4
        and "Villainy" in {a.name for a in (c.card_def.aspects or ())})
    if eligible:
        push_play_from_hand(state, source_ci, from_discard=True, eligible_ids=eligible,
                            free=True, aspect="Villainy", cost_max=4, up_to=True,
                            then_source_damage_cost_unless=("Night", "Undead"))
    return state


@card_ability("IC27", "66")
def _mother_talzin_ic27():
    """IC27_66 — Mother Talzin (Unit, Force/Night, 5/5): "When Played: You may play
    a Villainy unit that costs 4 or less from your discard pile for free.  If it's
    not a Night or Undead unit, deal damage equal to its cost to this unit."

    A discard-only free ``play_from_hand`` (Nightbrother HMW_204's shape) with the
    ``then_source_damage_cost_unless`` rider; ``up_to`` is the "may"."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_talzin_raise)])


@card_ability("IC27", "102")
def _third_sister_ic27():
    """IC27_102 — Third Sister (Unit, Force/Imperial/Inquisitor, 3/5): "On Attack:
    Deal 1 damage to a friendly ground unit and 1 damage to an enemy ground
    unit." """
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(controller="friendly", kind="unit",
                                          arena="ground")),
                 DealDamage(1, TargetSpec(controller="enemy", kind="unit",
                                          arena="ground"))])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _push_option(state, source_ci, ability_idx, event_ctx):
    """Resolve ability ``ability_idx`` of this card now, as a fresh
    ``resolve_effects`` carrying ``event_ctx`` (``_then_resolve_option`` in the HMW
    module, plus a context), so its target is chosen after what came before."""
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    me = actor_of(state, source_ci)
    after = 1 - state.player_index(me)
    state.pending_decisions.append(PendingDecision(
        deciding_player_id=me, kind="resolve_effects",
        context={"set_code": source_ci.card_def.set_code,
                 "card_number": source_ci.card_def.card_number,
                 "ability_idx": int(ability_idx), "source_id": source_ci.instance_id,
                 "effect_idx": 0, "resolved_targets": {}, "event_ctx": dict(event_ctx),
                 "after_all_player_idx": after},
        after_resolve_player_index=after))
    state.event_log.append(DecisionPushed(deciding_player_id=me, kind="resolve_effects"))
    state.active_player_index = state.player_index(me)
    return state


@card_ability("IC27", "107")
def _aurra_sing_ic27():
    """IC27_107 — Aurra Sing (Unit, Bounty Hunter/Underworld, 1/7): "Hidden.
    Action [Exhaust]: Deal 4 damage to a unit."  Hidden is the keyword layer."""
    return ActivatedAbility(costs=[ExhaustSelf()], effects=[DealDamage(4, _ANY_UNIT)],
                            title="Deal 4 damage to a unit")


def _snoke_purge(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage, _target_protected
    from swu.engine.actions import _draw_cards
    me = actor_of(state, source_ci)
    victims = [(ps.player_id, u.instance_id) for ps in state.players
               for u in ps.ground_arena + ps.space_arena
               if u.instance_id != source_ci.instance_id]
    for _, uid in victims:
        if not _target_protected(state, uid, source_ci, "damage"):
            _apply_deal_damage(state, uid, 4, source_ci.card_def.display_name,
                               dealer_id=me, source_id=source_ci.instance_id)
    lost = 0
    for pid, uid in victims:
        live = state.find_instance(uid)
        if pid == me and (live is None or live[1].zone.name not in _IN_ARENA):
            lost += 1
    if lost:
        _draw_cards(state, state.player_by_id(me), lost)
    return state


@card_ability("IC27", "109")
def _supreme_leader_snoke_ic27():
    """IC27_109 — Supreme Leader Snoke (Unit, First Order/Force/Official, 8/6):
    "Overwhelm.  When Played: Deal 4 damage to each other unit.  Draw a card for
    each friendly unit defeated this way."  Damage and draw in one effect, so
    "defeated this way" is exactly the units this sweep hit."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_snoke_purge)])


def _supremacy_halve(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions import compute_hp
    live = state.find_instance(target_id) if target_id else None
    if live is None:
        return state
    amount = max(0, compute_hp(state, live[1]) - live[1].damage) // 2
    if amount:
        _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name,
                           dealer_id=actor_of(state, source_ci),
                           source_id=source_ci.instance_id)
    return state


@card_ability("IC27", "110")
def _supremacy_ic27():
    """IC27_110 — Supremacy (Unit, Capital Ship/First Order/Vehicle, 10/10): "When
    Played: Deal damage to a base equal to half its remaining HP, rounded down." """
    return TriggerAbility(
        trigger=WhenPlayed(),
        effects=[CustomEffect(fn=_supremacy_halve,
                              target=TargetSpec(controller="any", kind="base"))])


@card_ability("IC27", "117")
def _hera_syndulla_ic27():
    """IC27_117 — Hera Syndulla (Unit, Rebel/Spectre/Twi'lek, 4/3): "When you play
    another Rebel card: Deal 1 damage to a base." """
    return TriggerAbility(
        trigger=WhenYouPlayCard(trait="Rebel"),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="base"))])


def _sabine_choose_deck(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    me = actor_of(state, source_ci)
    options = [(1, "Your deck", me)]
    options += [(2, "Your opponent's deck", p.player_id)
                for p in state.players if p.player_id != me]
    live = [o for o in options if state.player_by_id(o[2]).deck]
    if len(live) == 1:
        return _sabine_mill(live[0][0] == 1)(state, source_ci, target_id, event_ctx)
    if live:
        push_choose_modal(state, source_ci, option_indices=[o[0] for o in live],
                          pick=1, option_labels=[o[1] for o in live])
    return state


def _sabine_mill(own_deck):
    def _fn(state, source_ci, target_id, event_ctx):
        from swu.engine.actions import discard_from_deck
        me = actor_of(state, source_ci)
        pid = me if own_deck else next(p.player_id for p in state.players
                                       if p.player_id != me)
        milled = discard_from_deck(state, state.player_by_id(pid), 2)
        if len(milled) == 2:
            a, b = ((getattr(c.card_def, "cost", 0) or 0) for c in milled)
            if abs(a - b) > 0:
                _push_option(state, source_ci, 3, {"sabine_diff": abs(a - b)})
        return state
    return _fn


def _sabine_strike(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _apply_deal_damage
    amount = int(event_ctx.get("sabine_diff", 0))
    if target_id and amount > 0:
        _apply_deal_damage(state, target_id, amount, source_ci.card_def.display_name,
                           dealer_id=actor_of(state, source_ci),
                           source_id=source_ci.instance_id)
    return state


@card_ability("IC27", "119")
def _sabine_wren_ic27():
    """IC27_119 — Sabine Wren (Unit, Mandalorian/Rebel/Spectre, 5/4): "Saboteur.
    When Played: Discard 2 cards from a deck.  You may deal damage to a unit equal
    to the difference in those cards' costs."

    Index 0 chooses the deck (options 1 = yours, 2 = the opponent's, as
    ``EventAbility`` specs so they are never trigger-collected); the mill then
    resolves option 3, the optional damage, with the difference in its context.
    A deck with fewer than 2 cards discards what it has, and deals nothing."""
    return [
        TriggerAbility(trigger=WhenPlayed(),
                       effects=[CustomEffect(fn=_sabine_choose_deck)]),
        EventAbility(effects=[CustomEffect(fn=_sabine_mill(True))]),
        EventAbility(effects=[CustomEffect(fn=_sabine_mill(False))]),
        EventAbility(effects=[CustomEffect(
            fn=_sabine_strike,
            target=TargetSpec(controller="any", kind="unit", optional=True))]),
    ]


@card_ability("IC27", "124")
def _k2so_ic27():
    """IC27_124 — K-2SO (Unit, Droid/Rebel, 10/5): "When Defeated: Deal 5 damage to
    each enemy unit and each enemy base." """
    return TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(5, TargetSpec(controller="enemy", kind="unit",
                                          fixed=EACH_ENEMY)),
                 DealDamage(5, TargetSpec(kind="base", fixed=EACH_ENEMY))])


def _aggression_buff(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _make_modifier, _make_kw_modifier
    if not target_id:
        return state
    state.modifiers.append(_make_modifier(
        state, source_ci.instance_id, target_id, power=3, hp=0,
        duration=Duration.THIS_PHASE))
    state.modifiers.append(_make_kw_modifier(
        state, source_ci.instance_id, target_id, keyword="Overwhelm", value=0,
        duration=Duration.THIS_PHASE, kind="keyword_grant"))
    return state


@card_ability("IC27", "127")
def _act_of_aggression_ic27():
    """IC27_127 — Act of Aggression (Event, Innate, 4): "Draw a card.  You may deal 3
    damage to a unit.  Give a friendly unit +3/+0 and Overwhelm for this phase."
    The buff is one ``CustomEffect`` so one unit gets both (General Grievous
    TWI_15's shape)."""
    return EventAbility(effects=[
        DrawCards(1),
        DealDamage(3, TargetSpec(controller="any", kind="unit", optional=True)),
        CustomEffect(fn=_aggression_buff,
                     target=TargetSpec(controller="friendly", kind="unit")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:03 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _asajj_swap_in(state, source_ci, target_id, event_ctx):
    """Pay, bounce the attacker to its owner's hand, put Asajj into play (exhausted,
    as an attacking unit is) and make her the attacker of the parked ``pre_attack``
    that ``combat._pause_for_attacker_swap`` left beneath this decision."""
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.abilities.registry import FromHandAttackerSwap, get_abilities
    from swu.engine.actions import _exhaust_resources
    from swu.engine.actions.combat import attacker_swap_cost
    from swu.engine.state import Zone
    old_id = (event_ctx or {}).get("swap_attacker_id")
    me = actor_of(state, source_ci)
    ps = state.player_by_id(me)
    card = next((c for c in ps.hand if c.instance_id == source_ci.instance_id), None)
    attacker = next((u for u in ps.ground_arena if u.instance_id == old_id), None)
    if card is None or attacker is None:
        return state
    base_cost = next(spec.trigger.cost for spec in get_abilities("IC27", "147")
                     if isinstance(getattr(spec, "trigger", None), FromHandAttackerSwap))
    cost = attacker_swap_cost(state, ps, card, base_cost)
    if sum(1 for r in ps.resources if not r.exhausted) < cost:
        return state
    _exhaust_resources(ps, cost)
    _apply_return_to_hand(state, old_id)
    ps.hand.remove(card)
    card.zone = Zone.GROUND_ARENA
    card.exhausted = True
    card.damage = 0
    ps.ground_arena.append(card)
    for dec in reversed(state.pending_decisions):
        if dec.kind == "pre_attack" and dec.context.get("attacker_id") == old_id:
            dec.context["attacker_id"] = card.instance_id
            break
    return state


@card_ability("IC27", "147")
def _asajj_ventress_ic27_147():
    """IC27_147 — Asajj Ventress (Unit, Force/Separatist/Sith, 6, 5/7): "If a
    friendly non-leader ground unit would deal combat damage while attacking a base,
    you may reveal this unit from your hand and pay 5 resources [Cunning][Villainy].
    If you do, return the attacker to its owner's hand and put this unit into play as
    the attacker.  She deals combat damage to that base instead."

    The ``FromHandAttackerSwap`` replacement window (``combat._pause_for_attacker_swap``):
    offered right before base combat damage, only while affordable (5 + her aspect
    penalty); Accept = reveal and pay.  She enters exhausted as the attacker, and the
    attack resumes with HER power — no On Attack (the attack was already declared)
    and no When Played (put into play, not played)."""
    from swu.abilities.registry import FromHandAttackerSwap
    return TriggerAbility(trigger=FromHandAttackerSwap(cost=5), optional=True,
                          effects=[CustomEffect(fn=_asajj_swap_in)])


def _r2d2_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2, 3], pick=1,
                      option_labels=["Ready a resource",
                                     "Deal 1 damage to a ground unit",
                                     "Look at the top card of your deck"])
    return state


@card_ability("IC27", "151")
def _r2d2_ic27():
    """IC27_151 — R2-D2 (Unit, Droid/Rebel, 1/3): "On Attack: Choose one: Ready a
    resource.  Deal 1 damage to a ground unit.  Look at the top card of your deck.
    You may discard it."

    ``push_choose_modal(pick=1)`` over three ``EventAbility`` options (a UNIT card,
    so they must never be trigger-collected — the Jod Na Nawood ASH_219 shape).
    Reuses Emperor's Messenger ASH_189's resource ready and Reanimated Night Trooper
    ASH_45's ``may_discard`` peek."""
    from swu.cards.ash.abilities import _night_trooper_peek, _ready_one_resource
    return [
        TriggerAbility(trigger=OnAttack(), effects=[CustomEffect(fn=_r2d2_choose)]),
        EventAbility(effects=[CustomEffect(fn=_ready_one_resource)]),
        EventAbility(effects=[DealDamage(1, TargetSpec(controller="any", kind="unit",
                                                       arena="ground"))]),
        EventAbility(effects=[CustomEffect(fn=_night_trooper_peek)]),
    ]


@card_ability("IC27", "185")
def _i_am_your_father_ic27():
    """IC27_185 — I Am Your Father: SOR_233 reworded (curly quotes), so not an
    alias.  Registered from the canonical's own spec builder so the two cannot
    drift."""
    from swu.cards.sor.abilities import _i_am_your_father
    return _i_am_your_father()


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:04 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _return_unit_from_discard(state, source_ci, target_id, event_ctx):
    """"You may return a unit from your discard pile to your hand" — the
    ``return_from_discard`` decision is already "up to" (the SEC_105 shape)."""
    from swu.cards.models import Unit
    from swu.engine.actions import push_return_from_discard
    ps = state.player_by_id(actor_of(state, source_ci))
    if any(isinstance(ci.card_def, Unit) for ci in ps.discard):
        push_return_from_discard(state, source_ci, count=1,
                                 eligible=lambda cd: isinstance(cd, Unit))
    return state


@card_ability("IC27", "3")
def _kylo_ren_ic27():
    """IC27_3 — Kylo Ren (Leader, First Order/Force/Official, 5/3).

    Undeployed: "Action [Exhaust, discard a card from your hand]: Give an Experience
    token to a unit." — Kylo Ren SHD_11's ``DiscardCardCost`` action.
    Deployed: "When Deployed: You may return a unit from your discard pile to your
    hand."  The Epic Action deploy is generic."""
    return [
        ActivatedAbility(costs=[ExhaustSelf(), DiscardCardCost()],
                         effects=[GiveToken("Experience", _ANY_UNIT)],
                         title="Give an Experience token to a unit",
                         undeployed_only=True),
        TriggerAbility(trigger=WhenDeployed(), deployed_only=True,
                       effects=[CustomEffect(fn=_return_unit_from_discard)]),
    ]


@card_ability("IC27", "6")
def _luke_skywalker_ic27():
    """IC27_6 — Luke Skywalker (Leader, Force/Jedi/Rebel, 4/6).

    "Draw 2 more cards in your starting hand" — a ``StartingHandModifier`` read
    from the base zone at setup (where the undeployed leader sits; summed with a
    base's own marker).  Deployed: Overwhelm (the keyword layer) and "On Attack: You
    may discard a card from your hand.  If you do, this unit gets +2/+0 for this
    attack" — Razor Crest ASH_172's discard-for-power, gated on a non-empty hand."""
    from swu.cards.ash.abilities import _razor_crest_discard_for_power
    return [
        StartingHandModifier(amount=2),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=[CustomEffect(fn=_razor_crest_discard_for_power)],
                       condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN,
                                                param=1)),
    ]


@card_ability("IC27", "8")
def _princess_leia_ic27():
    """IC27_8 — Princess Leia (Leader, Official/Rebel, 4/7).

    Undeployed: "Action [1 resource, Exhaust]: Draw a card, then put a card from
    your hand on the top or bottom of your deck."  Deployed: "On Attack: <the same>".
    Both are Yoda TWI_4's draw + ``bottom_from_hand(allow_top=True)``."""
    from swu.cards.twi.abilities import _yoda_twi_4_top_or_bottom
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()],
                         effects=[DrawCards(1),
                                  CustomEffect(fn=_yoda_twi_4_top_or_bottom)],
                         title="Draw a card, then top/bottom a card from your hand",
                         undeployed_only=True),
        TriggerAbility(trigger=OnAttack(), deployed_only=True,
                       effects=[DrawCards(1),
                                CustomEffect(fn=_yoda_twi_4_top_or_bottom)]),
    ]


@card_ability("IC27", "38")
def _admiral_holdo_ic27():
    """IC27_38 — Admiral Holdo (Unit, Official/Resistance, 3/7): "Draw 1 more card
    during the regroup phase." — the new ``ExtraRegroupDraw`` marker, read at the
    regroup draw (``turn._regroup_draw_count``)."""
    return ExtraRegroupDraw(1)


def _obi_wan_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    push_choose_modal(state, source_ci, option_indices=[1, 2], pick=1,
                      option_labels=["Play a unit defeated this phase for 5 less",
                                     "Give a unit that entered play -5/-5"])
    return state


@card_ability("IC27", "42")
def _obi_wan_kenobi_ic27():
    """IC27_42 — Obi-Wan Kenobi (Unit, Force/Jedi/Republic, 5/9): "When Played: You
    may choose one: Play a unit that was defeated this phase from your discard pile.
    It costs 5 resources less.  Choose a unit that entered play this phase.  It gets
    –5/–5 for this phase."

    An optional trigger onto ``push_choose_modal(pick=1)`` over two ``EventAbility``
    options (a UNIT card — never trigger-collected).  Option 1 is Maul HMW_16's
    deployed replay (same 5-less); option 2 is Hello There TWI_52 at –5/–5."""
    from swu.cards.hmw.abilities import _maul_replay_defeated
    return [
        TriggerAbility(trigger=WhenPlayed(), optional=True,
                       effects=[CustomEffect(fn=_obi_wan_choose)]),
        EventAbility(effects=[CustomEffect(fn=_maul_replay_defeated)]),
        EventAbility(effects=[ModifyStats(
            power=-5, hp=-5,
            target=TargetSpec(controller="any", kind="unit",
                              predicates=("played_this_phase",)),
            duration=Duration.THIS_PHASE)]),
    ]


@card_ability("IC27", "63")
def _kylos_tie_silencer_ic27():
    """IC27_63 — Kylo's TIE Silencer (Unit, 4/4, Restore 1): "When this unit is
    discarded from your hand: For this phase, you may play it from your discard pile
    (paying its cost)."

    The trigger-then-permission collapses to Kylo's TIE Silencer SHD_135's
    ``PlayFromDiscardAction`` gated on ``SELF_DISCARDED_THIS_PHASE``.  DOCUMENTED
    DEVIATION (docs/known_deviations.md): that ledger is fed by hand AND deck
    discards (several mill sites cannot tell them apart), so a self-mill also opens
    the replay — favourable to the controller, and still paid in full.  Restore is
    the keyword layer."""
    return PlayFromDiscardAction(
        condition=ConditionCheck(Condition.SELF_DISCARDED_THIS_PHASE))


def _c3po_experience_then_draw(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import compute_power, _draw_cards
    from swu.engine.tokens import attach_token
    live = state.find_instance(target_id) if target_id else None
    if live is None or live[1].zone.name not in _IN_ARENA:
        return state
    attach_token(state, live[0], live[1], "Experience")
    live = state.find_instance(target_id)
    if live is not None and compute_power(state, live[1]) >= 6:   # "Then, if …"
        _draw_cards(state, state.player_by_id(actor_of(state, source_ci)), 1)
    return state


@card_ability("IC27", "70")
def _c3po_ic27():
    """IC27_70 — C-3PO (Unit, Droid/Rebel, 1/3): "Action [Exhaust]: Give an
    Experience token to another unit.  Then, if it has 6 or more power, draw a
    card."  One CustomEffect so the power check reads the unit AFTER its token."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_c3po_experience_then_draw,
                              target=TargetSpec(controller="any", kind="unit",
                                                predicates=("not_self",)))],
        title="Give an Experience token to another unit")


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:05 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _search_deck_for_vader(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    ps = state.player_by_id(actor_of(state, source_ci))
    if ps.deck:
        push_deck_search(state, source_ci, count=1, up_to=False, window=len(ps.deck),
                         eligible=lambda cd: getattr(cd, "name", None) == "Darth Vader")
    return state


@card_ability("IC27", "78")
def _anakin_skywalker_ic27():
    """IC27_78 — Anakin Skywalker (Unit, Force/Jedi/Republic, 7/4): "When Defeated:
    Search your deck for a card named Darth Vader, reveal it, and draw it.  While
    this unit is in your discard pile, ignore the aspect penalties on cards you play
    named Darth Vader."

    The search is a whole-deck ``deck_search`` (the rest bottomed in a seeded-random
    order, which doubles as the shuffle).  The waiver is ``IgnoreAspectPenaltyForPlays``
    with the new ``names`` + ``in_discard`` readings, so it works ONLY from the
    discard pile (``costs._controller_waives_aspect_penalty`` scans it last)."""
    from swu.abilities.registry import IgnoreAspectPenaltyForPlays
    return [
        TriggerAbility(trigger=WhenDefeated(),
                       effects=[CustomEffect(fn=_search_deck_for_vader)]),
        IgnoreAspectPenaltyForPlays(names=("Darth Vader",), in_discard=True),
    ]


def _negotiator_resource_top(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import _resource_top_of_deck
    _resource_top_of_deck(state, state.player_by_id(actor_of(state, source_ci)))
    return state


def _negotiator_return_resource(state, source_ci, target_id, event_ctx):
    """"You may return a friendly resource to its owner's hand" — the resource is
    AUTO-PICKED (the K-2SO SOR_145 fungible convention; Citadel Research Center
    LAW_29 takes the highest-cost one, the card most worth recovering)."""
    from swu.engine.state import Zone
    ps = state.player_by_id(actor_of(state, source_ci))
    if not ps.resources:
        return state
    res = max(ps.resources, key=lambda c: getattr(c.card_def, "cost", 0) or 0)
    ps.resources.remove(res)
    res.zone = Zone.HAND
    res.face_down = False
    res.exhausted = False
    state.player_by_id(res.owner_id).hand.append(res)
    return state


def _negotiator_triggers(trigger):
    return [
        TriggerAbility(trigger=trigger,
                       effects=[CustomEffect(fn=_negotiator_resource_top)]),
        TriggerAbility(trigger=trigger, optional=True,
                       effects=[CustomEffect(fn=_negotiator_return_resource)]),
    ]


@card_ability("IC27", "84")
def _negotiator_ic27():
    """IC27_84 — Negotiator (Unit, Capital Ship/Republic/Vehicle, 9/7, Sentinel):
    "On Attack/When Defeated: Resource the top card of your deck.  Then, you may
    return a friendly resource to its owner's hand."

    Per event, two triggers: the mandatory ramp (``_resource_top_of_deck``, Broken
    Horn LAW_83) and the optional return (there is no optional sub-effect inside one
    ability, so the "you may" is its own ``AcceptTrigger``).  Sentinel is the keyword
    layer."""
    return _negotiator_triggers(OnAttack()) + _negotiator_triggers(WhenDefeated())


def _issue_a_command_reveal(state, source_ci, target_id, event_ctx):
    """"Reveal the top card of your deck.  If it's a unit, draw it." — a non-unit
    stays on top (revealing it changes nothing a player could act on)."""
    from swu.cards.models import Unit
    from swu.engine.actions import _draw_cards
    ps = state.player_by_id(actor_of(state, source_ci))
    if ps.deck and isinstance(ps.deck[0].card_def, Unit):
        _draw_cards(state, ps, 1)
    return state


def _resource_this_event(state, source_ci, target_id, event_ctx):
    """"Resource this event." — the Stockpile LAW_171 move: a played event is in
    its owner's discard before its ability resolves, so it is resourced straight out
    of that pile, face down and EXHAUSTED (a mid-phase resource)."""
    from swu.engine.state import Zone
    from swu.engine.events import CardResourced
    ps = state.player_by_id(source_ci.owner_id)
    me = next((c for c in ps.discard if c.instance_id == source_ci.instance_id), None)
    if me is None:
        return state
    ps.discard.remove(me)
    me.zone = Zone.RESOURCES
    me.face_down = True
    me.exhausted = True
    ps.resources.append(me)
    state.event_log.append(CardResourced(player_id=ps.player_id,
                                         instance_id=me.instance_id,
                                         card_name=me.card_def.display_name))
    return state


@card_ability("IC27", "87")
def _issue_a_command_ic27():
    """IC27_87 — Issue a Command (Event, Plan, 4): "Reveal the top card of your
    deck.  If it's a unit, draw it.  Give an Experience token to a friendly unit.
    Resource this event." """
    return EventAbility(effects=[
        CustomEffect(fn=_issue_a_command_reveal),
        GiveToken("Experience", TargetSpec(controller="friendly", kind="unit")),
        CustomEffect(fn=_resource_this_event),
    ])


@card_ability("IC27", "116")
def _black_one_ic27():
    """IC27_116 — Black One (Unit, Fighter/Resistance/Vehicle, 2/2): "When
    Played/When Defeated: Draw a card." """
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        TriggerAbility(trigger=WhenDefeated(), effects=[DrawCards(1)]),
    ]


@card_ability("IC27", "122")
def _the_ghost_ic27():
    """IC27_122 — The Ghost (Unit, Rebel/Spectre/Transport/Vehicle, 7/7,
    Overwhelm): "When a friendly unit deals damage to an enemy base: If you have 7
    or fewer cards in your hand, draw a card."

    The ``WhenDamageDealt`` observer with the new ``dealer="friendly_unit"`` filter
    (the dealing card is recorded on every base-damage entry), resolved at the
    settle point; the hand-size gate is read then.  Overwhelm spill counts (it is
    the attacker's combat damage)."""
    from swu.abilities.registry import WhenDamageDealt
    return TriggerAbility(
        trigger=WhenDamageDealt(dealer="friendly_unit", target="enemy", kind="base"),
        effects=[DrawCards(1)],
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MAX, param=7))


def _jango_discard_for_event(state, source_ci, target_id, event_ctx):
    from swu.cards.ash.abilities import _discard_choice
    _discard_choice(state, source_ci, actor_of(state, source_ci),
                    payoff="ic27_jango_event_back")
    return state


@discard_payoff("ic27_jango_event_back")
def _jango_event_back(state, source_id, discarded, args):
    """"If you do, return an event from your discard pile to your hand" — the
    just-discarded card is eligible if it is an event."""
    from swu.cards.models import Event
    from swu.engine.actions import push_return_from_discard
    if not discarded:
        return
    res = state.find_instance(source_id or "")
    if res is None:
        return
    if any(isinstance(c.card_def, Event) for c in res[0].discard):
        push_return_from_discard(state, res[1], count=1,
                                 eligible=lambda cd: isinstance(cd, Event))


@card_ability("IC27", "144")
def _jango_fett_ic27():
    """IC27_144 — Jango Fett (Unit, Bounty Hunter/Separatist, 4/4, Ambush): "When
    Defeated: You may discard a card from your hand.  If you do, return an event
    from your discard pile to your hand."

    The Razor Crest ASH_172 "if you do" binding: the discard is the player's choice
    and the return is its payoff.  Gated on a non-empty hand so it is never a dead
    prompt.  Ambush is the keyword layer."""
    return TriggerAbility(
        trigger=WhenDefeated(), optional=True,
        effects=[CustomEffect(fn=_jango_discard_for_event)],
        condition=ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1))


def _poggle_pay_and_discard(state, source_ci, target_id, event_ctx):
    from swu.cards.ash.abilities import _discard_choice
    from swu.engine.actions import _exhaust_resources
    ps = state.player_by_id(actor_of(state, source_ci))
    if not ps.hand or not any(not r.exhausted for r in ps.resources):
        return state
    _exhaust_resources(ps, 1)
    _discard_choice(state, source_ci, ps.player_id, payoff="ic27_poggle_discount")
    return state


@discard_payoff("ic27_poggle_discount")
def _poggle_discount(state, source_id, discarded, args):
    """"…the next card you play this phase costs 3 resources less" — a
    ``pending_play_discounts`` entry, any card type."""
    from swu.abilities.resolver import execute_effect
    if not discarded:
        return
    res = state.find_instance(source_id or "")
    if res is None:
        return
    execute_effect(state, NextPlayDiscount(trait=None, amount=3, units_only=False),
                   res[1], None, {})


@card_ability("IC27", "145")
def _poggle_the_lesser_ic27():
    """IC27_145 — Poggle the Lesser (Unit, Official/Separatist, 3/5): "On Attack: You
    may pay 1 resource and discard a card from your hand.  If you do, the next card
    you play this phase costs 3 resources less."

    One effect pays the resource and pushes the discard; the discount is the
    discard's payoff (``NextPlayDiscount(units_only=False)``).  Gated on BOTH a
    ready resource and a hand card (``ALL_OF``) so it is never a dead prompt."""
    return TriggerAbility(
        trigger=OnAttack(), optional=True,
        effects=[CustomEffect(fn=_poggle_pay_and_discard)],
        condition=ConditionCheck(Condition.ALL_OF, param=(
            ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=1),
            ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=1),
        )))


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:06 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _han_search_then_random_discard(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, up_to=False, window=10,
                     eligible=lambda cd: True, then_discard_random=True)
    return state


@card_ability("IC27", "155")
def _han_solo_ic27():
    """IC27_155 — Han Solo (Unit, Rebel, 5/3, Saboteur): "When Played: Search the
    top 10 cards of your deck for a card and draw it, then discard a random card
    from your hand."

    A mandatory ``deck_search`` with the ``then_discard_random`` finish (seeded RNG,
    from the hand that now holds the drawn card — so the drawn card itself can be
    the one lost).  Saboteur is the keyword layer."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_han_search_then_random_discard)])


def _falcon_pay_return_replay(state, source_ci, target_id, event_ctx):
    """Pay 1, bounce the chosen friendly unit; if it landed in OUR hand, offer it
    for free (``push_play_from_hand`` whitelisted to that one card, declinable)."""
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.engine.actions import _exhaust_resources, push_play_from_hand
    me = actor_of(state, source_ci)
    ps = state.player_by_id(me)
    res = state.find_instance(target_id or "")
    if res is None or not any(not r.exhausted for r in ps.resources):
        return state
    owner = res[1].owner_id
    _exhaust_resources(ps, 1)
    _apply_return_to_hand(state, res[1].instance_id)
    if owner == me and any(c.instance_id == target_id for c in ps.hand):
        push_play_from_hand(state, source_ci, free=True,
                            eligible_ids=frozenset({target_id}))
    return state


@card_ability("IC27", "158")
def _millennium_falcon_ic27():
    """IC27_158 — Millennium Falcon (Unit, Rebel/Transport/Vehicle, 4/4): "When
    Attack Ends: You may pay 1 resource.  If you do, return a friendly unit that
    costs 3 or less to its owner's hand.  If it's returned to your hand, you may play
    it for free."

    The optional trigger's Accept IS the "you may pay" (Blue Leader JTL_96), gated on
    a ready resource AND a qualifying unit so it is never a dead prompt.  The bounce
    target is chosen; a stolen unit goes to its owner and is not replayed."""
    from swu.abilities.registry import WhenAttackEnds
    return TriggerAbility(
        trigger=WhenAttackEnds(), optional=True,
        effects=[CustomEffect(fn=_falcon_pay_return_replay,
                              target=TargetSpec(controller="friendly", kind="unit",
                                                predicates=("non_leader",),
                                                cost_max=3))],
        condition=ConditionCheck(Condition.ALL_OF, param=(
            ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=1),
            ConditionCheck(Condition.CONTROLLER_HAS_UNIT_COST_MAX, param=3),
        )))


@card_ability("IC27", "166")
def _ive_got_a_bad_feeling_ic27():
    """IC27_166 — I've Got A Bad Feeling (Event, Innate, 4): "Return a non-leader
    unit to its owner's hand.  Give a Shield token to a friendly unit." """
    from swu.abilities.registry import ReturnToHand
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="any", kind="unit",
                                predicates=("non_leader",))),
        GiveToken("Shield", TargetSpec(controller="friendly", kind="unit")),
    ])


def _lando_ic27_return_then_resource(state, source_ci, target_id, event_ctx):
    """Return 3 friendly resources (auto-picked: exhausted ones first, the ones the
    controller can no longer use this phase — the K-2SO SOR_145 fungible
    convention), then the "you may resource up to 3" decision."""
    from swu.engine.state import Zone
    from swu.engine.actions import push_resource_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    for _ in range(min(3, len(ps.resources))):
        res = next((r for r in ps.resources if r.exhausted), ps.resources[0])
        ps.resources.remove(res)
        res.zone = Zone.HAND
        res.face_down = False
        res.exhausted = False
        state.player_by_id(res.owner_id).hand.append(res)
    push_resource_from_hand(state, source_ci, count=3, enters_exhausted=True)
    return state


@card_ability("IC27", "167")
def _lando_calrissian_ic27():
    """IC27_167 — Lando Calrissian (Unit, Official, 4/4): "When Played: Return 3
    friendly resources to their owners' hands.  Then, you may resource up to 3 cards
    from your hand."

    The return is mandatory and auto-picked (exhausted first); the re-resource is the
    ``resource_from_hand`` decision (always finishable), each card entering exhausted
    (the Osha HMW_17 plain "resource a card" reading)."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_lando_ic27_return_then_resource)])


def _cunning_ploy_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=3, optional=True)
    return state


@card_ability("IC27", "168")
def _cunning_ploy_ic27():
    """IC27_168 — Cunning Ploy (Event, Trick, 4): "Look at an opponent's hand.  You
    may discard a card from it.  If you do, that player draws a card.  Exhaust an
    enemy unit.  You may attack with a unit.  It gets +3/+0 for this attack."

    The first clause is Remnant Lookouts ASH_220's adapter (``name_and_discard``
    with ``discarder_draws``); then a plain ``ExhaustCard`` and an optional granted
    attack at +3/+0."""
    from swu.abilities.registry import ExhaustCard
    from swu.cards.ash.abilities import _remnant_lookouts_peek_hand
    return EventAbility(effects=[
        CustomEffect(fn=_remnant_lookouts_peek_hand),
        ExhaustCard(_ENEMY_UNIT),
        CustomEffect(fn=_cunning_ploy_attack),
    ])


def _morgan_elsbeth_reveal(state, source_ci, target_id, event_ctx):
    """Reveal the top card: cost 6+ is drawn, anything else is milled (through
    ``discard_from_deck``, so the deck-discard observers see it)."""
    from swu.engine.actions import _draw_cards
    from swu.engine.actions.combat import discard_from_deck
    ps = state.player_by_id(actor_of(state, source_ci))
    if not ps.deck:
        return state
    if (getattr(ps.deck[0].card_def, "cost", None) or 0) >= 6:
        _draw_cards(state, ps, 1)
    else:
        discard_from_deck(state, ps, 1)
    return state


@card_ability("IC27", "179")
def _morgan_elsbeth_ic27():
    """IC27_179 — Morgan Elsbeth (Unit, Force/Imperial/Night, 1/5): "On Attack:
    Reveal the top card of your deck.  If it costs 6 or more, draw it.  Otherwise,
    discard it." """
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_morgan_elsbeth_reveal)])


def _jar_jar_mill_for_power(state, source_ci, target_id, event_ctx):
    """Mill 1; a 6+-cost card gives this unit +4/+0 for this attack (the Dryden Vos
    SEC_137 THIS_ATTACK modifier)."""
    from swu.abilities.resolver import _make_modifier
    from swu.engine.actions.combat import discard_from_deck
    ps = state.player_by_id(actor_of(state, source_ci))
    milled = discard_from_deck(state, ps, 1)
    if milled and (getattr(milled[0].card_def, "cost", None) or 0) >= 6:
        state.modifiers.append(_make_modifier(
            state, source_ci.instance_id, source_ci.instance_id,
            power=4, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("IC27", "187")
def _jar_jar_binks_ic27():
    """IC27_187 — Jar Jar Binks (Unit, Gungan/Official/Republic, 1/5): "On Attack:
    Discard a card from your deck.  If it costs 6 or more, this unit gets +4/+0 for
    this attack." """
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_jar_jar_mill_for_power)])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:07 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


@card_ability("IC27", "194")
def _youre_my_only_hope_ic27():
    """IC27_194 — You're My Only Hope (Event, Gambit, 3): SOR_246's ability, reworded
    ("5 resources" for the cost icon), so registered from its builder rather than
    aliased (the alias table needs identical faces)."""
    from swu.cards.sor.abilities import _youre_my_only_hope_sor_246
    return _youre_my_only_hope_sor_246()



# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:08 — Combat tricks, buffs & tempo
# (IC27_1 / IC27_2 collide with the Experience / Shield token keys: registered ONLY
# from undeployed Actions, WhenDeployed and deployed_only triggers — see the module
# docstring.)
# ══════════════════════════════════════════════════════════════════════════════

_FRIENDLY_BASE = TargetSpec(controller="friendly", kind="base", fixed=EACH_FRIENDLY)
_DAMAGED_UNIT = TargetSpec(controller="any", kind="unit", predicates=("damaged",))
_ANY_DAMAGED_UNIT = ConditionCheck(Condition.ANY_OF, param=(
    ConditionCheck(Condition.CONTROLLER_HAS_DAMAGED_UNIT),
    ConditionCheck(Condition.ENEMY_HAS_DAMAGED_UNIT),
))


@card_ability("IC27", "1")
def _darth_vader_ic27():
    """IC27_1 — Darth Vader (Leader, Force/Imperial/Sith, 5/7).

    Undeployed: "Action [1 resource, Exhaust, defeat a friendly unit]: Draw a card
    and heal 2 damage from your base."  Deployed: "On Attack: You may defeat another
    friendly unit.  If you do, draw a card and heal 2 damage from your base."

    Emperor Palpatine SOR_6's exact shape: the defeat cost is the first mandatory
    targeted effect, both gated on CONTROLLER_HAS_NON_LEADER_UNIT so a paid cost is
    never wasted and an accepted On Attack always has a unit to defeat."""
    payoff = [DrawCards(1), Heal(2, _FRIENDLY_BASE)]
    has_fodder = ConditionCheck(Condition.CONTROLLER_HAS_NON_LEADER_UNIT)
    return [
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[DefeatUnit(TargetSpec(controller="friendly", kind="unit"))] + payoff,
            title="Defeat a friendly unit: draw and heal 2",
            undeployed_only=True, condition=has_fodder),
        TriggerAbility(
            trigger=OnAttack(), optional=True, deployed_only=True,
            effects=[DefeatUnit(TargetSpec(controller="friendly", kind="unit",
                                           predicates=("not_self",)))] + payoff,
            condition=has_fodder),
    ]


@card_ability("IC27", "2")
def _rey_ic27():
    """IC27_2 — Rey (Leader, Force/Resistance, 3/6).

    Undeployed: "Action [1 resource, Exhaust]: Give an Experience token to a damaged
    unit."  Deployed: "On Attack: You may give an Experience token to a damaged
    unit."  Both gated on a damaged unit existing (either side) — never a dead
    prompt."""
    token = [GiveToken("Experience", _DAMAGED_UNIT)]
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()], effects=token,
                         title="Give an Experience token to a damaged unit",
                         undeployed_only=True, condition=_ANY_DAMAGED_UNIT),
        TriggerAbility(trigger=OnAttack(), optional=True, deployed_only=True,
                       effects=token, condition=_ANY_DAMAGED_UNIT),
    ]


def _mace_attack_with_restore(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, grant_keywords=[("Restore", 2)])
    return state


@card_ability("IC27", "4")
def _mace_windu_ic27():
    """IC27_4 — Mace Windu (Leader, Force/Jedi/Republic, 4/7).

    Undeployed: "Action [1 resource, Exhaust]: Attack with a unit.  It gains Restore
    2 for this attack."  Deployed: "Restore 2.  When Deployed: Resource the top card
    of your deck."  Restore is the keyword layer (rule 11 reads the deploy box); the
    grant is a ``(name, value)`` granted-attack keyword (Leia JTL_97); the ramp is
    Negotiator IC27_84's ``_resource_top_of_deck``."""
    return [
        ActivatedAbility(costs=[PayResources(1), ExhaustSelf()],
                         effects=[CustomEffect(fn=_mace_attack_with_restore)],
                         title="Attack with a unit (it gains Restore 2)",
                         undeployed_only=True),
        TriggerAbility(trigger=WhenDeployed(),
                       effects=[CustomEffect(fn=_negotiator_resource_top)]),
    ]


def _asajj_attack_then_ready(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, then_ready_resource_if_survived=True)
    return state


@card_ability("IC27", "7")
def _asajj_ventress_ic27_leader():
    """IC27_7 — Asajj Ventress (Leader, Force/Separatist/Sith, 5/6).

    Undeployed: "Action [Exhaust]: Attack with a unit.  After completing this attack,
    if the attacker survived, you may ready a resource."  Deployed: "Saboteur.  On
    Attack: You may ready a resource."

    The new ``then_ready_resource_if_survived`` granted-attack rider (settled with
    the other riders).  Readying a resource is never a drawback, so both "may"s are
    taken automatically (Emperor's Messenger ASH_189's fungible ready).  Saboteur is
    the keyword layer."""
    from swu.cards.ash.abilities import _ready_one_resource
    return [
        ActivatedAbility(costs=[ExhaustSelf()],
                         effects=[CustomEffect(fn=_asajj_attack_then_ready)],
                         title="Attack with a unit (then ready a resource)",
                         undeployed_only=True),
        TriggerAbility(trigger=OnAttack(), deployed_only=True,
                       effects=[CustomEffect(fn=_ready_one_resource)]),
    ]


@card_ability("IC27", "13")
def _nute_gunray_ic27():
    """IC27_13 — Nute Gunray (Unit, Official/Separatist, 1/4): "Each other friendly
    Separatist unit gains Restore 1."  (The upstream Restore tag is the grant — the
    keyword sanitiser strips it, so Nute himself has no Restore.)"""
    from swu.abilities.registry import ConstantAbility, KeywordGrant
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Separatist",),
                          predicates=("not_self",)),
        effects=[KeywordGrant("Restore", 1)])


_GRIEVOUS_OPTIONS = ((1, "Give an Experience token to him"),
                     (2, "Heal 3 damage from your base"),
                     (3, "Draw a card"))


def _grievous_choose(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_choose_modal
    taken = state.game_memory.modal_options_chosen_this_phase
    left = [o for o in _GRIEVOUS_OPTIONS
            if f"{source_ci.instance_id}:{o[0]}" not in taken]
    if left:
        push_choose_modal(state, source_ci, option_indices=[o[0] for o in left],
                          pick=1, option_labels=[o[1] for o in left])
    return state


def _grievous_mark(idx):
    def _fn(state, source_ci, target_id, event_ctx):
        state.game_memory.modal_options_chosen_this_phase.add(
            f"{source_ci.instance_id}:{idx}")
        return state
    return _fn


@card_ability("IC27", "21")
def _general_grievous_ic27():
    """IC27_21 — General Grievous (Unit, Official/Separatist, 4/5): "When you play an
    upgrade on this unit: Choose one that hasn't been chosen this phase: Give an
    Experience token to him.  Heal 3 damage from your base.  Draw a card."

    ``WhenYouPlayCard(card_type="upgrade", on_self=True)`` onto ``push_choose_modal``
    over the options not yet in the new phase-scoped
    ``game_memory.modal_options_chosen_this_phase`` (each option marks itself as it
    resolves).  Options are ``EventAbility`` specs (a unit card — never
    trigger-collected).  With all three used, the trigger does nothing."""
    from swu.abilities.registry import SELF
    return [
        TriggerAbility(trigger=WhenYouPlayCard(card_type="upgrade", on_self=True),
                       effects=[CustomEffect(fn=_grievous_choose)]),
        EventAbility(effects=[CustomEffect(fn=_grievous_mark(1)),
                              GiveToken("Experience", TargetSpec(fixed=SELF))]),
        EventAbility(effects=[CustomEffect(fn=_grievous_mark(2)),
                              Heal(3, _FRIENDLY_BASE)]),
        EventAbility(effects=[CustomEffect(fn=_grievous_mark(3)), DrawCards(1)]),
    ]


@card_ability("IC27", "23")
def _grand_moff_tarkin_ic27():
    """IC27_23 — Grand Moff Tarkin (Unit, Imperial/Official, 3/6): "Each friendly
    unit with Sentinel gets +1/+1."  The upstream Sentinel tag is a reference, not
    his own keyword (sanitised), so he buffs himself only if granted Sentinel."""
    from swu.abilities.registry import ConstantAbility, StatBonus
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit",
                          predicates=("has_sentinel",)),
        effects=[StatBonus(power=1, hp=1)])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:09 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

def _apply_all(state, source_ci, target_id, event_ctx, effects):
    """Run several effects on ONE chosen target ("give it X; it gains Y")."""
    from swu.abilities.resolver import execute_effect
    for eff in effects:
        if target_id is None or state.find_instance(target_id) is None:
            break
        state = execute_effect(state, eff, source_ci, target_id, event_ctx)
    return state


def _thrawn_xp_sentinel(state, source_ci, target_id, event_ctx):
    from swu.abilities.registry import GrantKeyword
    return _apply_all(state, source_ci, target_id, event_ctx, [
        GiveToken("Experience", TargetSpec()),
        GrantKeyword("Sentinel", 0, TargetSpec(), Duration.THIS_PHASE)])


@card_ability("IC27", "24")
def _grand_admiral_thrawn_ic27():
    """IC27_24 — Grand Admiral Thrawn (Unit, Imperial/Official, 6, 4/4): "When
    Played/On Attack/When Defeated: You may give an Experience token to another
    friendly unit.  It gains Sentinel for this phase."  One optional trigger per
    timing, each picking the unit once and applying both halves to it."""
    target = TargetSpec(controller="friendly", kind="unit", predicates=("not_self",))
    return [TriggerAbility(trigger=t, optional=True,
                           effects=[CustomEffect(fn=_thrawn_xp_sentinel, target=target)])
            for t in (WhenPlayed(), OnAttack(), WhenDefeated())]


def _chimaera_xp_and_heal(state, source_ci, target_id, event_ctx):
    """Snapshot each friendly unit's upgrade count, give that many Experience,
    then heal 1 from the base per friendly upgrade (counted after the tokens)."""
    from swu.abilities.resolver import execute_effect
    ps = state.player_by_id(actor_of(state, source_ci))
    counts = [(u.instance_id, len(u.attached_upgrades))
              for u in ps.ground_arena + ps.space_arena]
    for iid, n in counts:
        if n and state.find_instance(iid) is not None:
            state = execute_effect(state, GiveToken("Experience", TargetSpec(), count=n),
                                   source_ci, iid, event_ctx)
    ps = state.player_by_id(actor_of(state, source_ci))
    total = sum(len(u.attached_upgrades) for u in ps.ground_arena + ps.space_arena)
    if total:
        state = execute_effect(state, Heal(total, _FRIENDLY_BASE), source_ci, None,
                               event_ctx)
    return state


@card_ability("IC27", "29")
def _chimaera_ic27():
    """IC27_29 — Chimaera (Unit, Capital Ship/Imperial/Vehicle, 10, 8/8; Shielded):
    "When Played: Give an Experience token to each friendly unit for each upgrade on
    it.  Then, heal 1 damage from your base for each friendly upgrade."  Shielded
    resolves first, so the Chimaera's own Shield counts for it."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_chimaera_xp_and_heal)])


@card_ability("IC27", "34")
def _obi_wans_interceptor_ic27():
    """IC27_34 — Obi-Wan's Interceptor (Unit, 2/3): "Other friendly Republic units
    get +0/+1."""
    from swu.abilities.registry import ConstantAbility, StatBonus
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Republic",),
                          predicates=("not_self",)),
        effects=[StatBonus(power=0, hp=1)])


@card_ability("IC27", "37")
def _finn_ic27():
    """IC27_37 — Finn (Unit, Resistance, 4/5; Sentinel): "While this unit is
    upgraded, he gains Restore 2."""
    from swu.abilities.registry import ConstantAbility, KeywordGrant, SELF
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Restore", 2)],
        condition=ConditionCheck(Condition.SOURCE_UPGRADED))


@card_ability("IC27", "40")
def _rose_tico_ic27():
    """IC27_40 — Rose Tico (Unit, Resistance, 6/6; Shielded): "On Attack: You may
    give a Shield token to another Resistance unit" — any controller's."""
    return TriggerAbility(trigger=OnAttack(), optional=True, effects=[
        GiveToken("Shield", TargetSpec(controller="any", kind="unit",
                                       traits=("Resistance",),
                                       predicates=("not_self",)))])


def _qira_xp_count(event_ctx) -> int:
    return list((event_ctx or {}).get("defeated_upgrade_names") or ()).count(
        "Experience")


def _qira_pass_on(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import execute_effect
    n = _qira_xp_count(event_ctx)
    if n and target_id:
        state = execute_effect(state, GiveToken("Experience", TargetSpec(), count=n),
                               source_ci, target_id, event_ctx)
    return state


@card_ability("IC27", "45")
def _qira_ic27():
    """IC27_45 — Qi'ra (Unit, Underworld, 3, 1/1): "When Played: Give 2 Experience
    tokens to this unit.  When Defeated: Choose a unit.  You may give an Experience
    token to it for each Experience token that was on this unit."  The count reads
    the defeat snapshot's plain names (``event_ctx["defeated_upgrade_names"]``, which
    survives the optional's round-trip); not offered at 0."""
    from swu.abilities.registry import SELF
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[
            GiveToken("Experience", TargetSpec(fixed=SELF), count=2)]),
        TriggerAbility(trigger=WhenDefeated(), optional=True, effects=[
            CustomEffect(fn=_qira_pass_on, target=_ANY_UNIT,
                         available_fn=lambda s, src, ctx: _qira_xp_count(ctx) > 0)]),
    ]


def _vigilant_buff(state, source_ci, target_id, event_ctx):
    from swu.abilities.registry import GrantKeyword
    return _apply_all(state, source_ci, target_id, event_ctx, [
        ModifyStats(0, 3, TargetSpec(), Duration.THIS_PHASE),
        GrantKeyword("Sentinel", 0, TargetSpec(), Duration.THIS_PHASE)])


@card_ability("IC27", "46")
def _vigilant_defense_ic27():
    """IC27_46 — Vigilant Defense (Event, Tactic, 4): "Give a friendly unit +0/+3
    and Sentinel for this phase.  Heal 3 damage from a friendly unit or base.  Defeat
    an enemy unit with 3 or less remaining HP."""
    return EventAbility(effects=[
        CustomEffect(fn=_vigilant_buff,
                     target=TargetSpec(controller="friendly", kind="unit")),
        Heal(3, TargetSpec(controller="friendly", kind="unit_or_base")),
        DefeatUnit(TargetSpec(controller="enemy", kind="unit", hp_remaining_max=3)),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:10 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

def _dexter_pay_and_look(state, source_ci, target_id, event_ctx):
    """Pay 1, then the ``reveal_top`` seam in ``disposition="bottom"`` (Rogue One
    LAW_119): un-kept cards go to the bottom, kept ones stay on top in order."""
    from swu.engine.actions import _exhaust_resources, push_reveal_top_discard_reorder
    ps = state.player_by_id(actor_of(state, source_ci))
    if not any(not r.exhausted for r in ps.resources) or not ps.deck:
        return state
    _exhaust_resources(ps, 1)
    push_reveal_top_discard_reorder(state, source_ci, count=3,
                                    deal_aspect_damage=False, disposition="bottom")
    return state


@card_ability("IC27", "49")
def _dexter_jettster_ic27():
    """IC27_49 — Dexter Jettster (Unit, Fringe, 3, 2/6): "On Attack: You may pay 1
    resource.  If you do, look at the top 3 cards of your deck.  Put any number of
    them on the bottom of your deck and the rest on top in any order."  Accept = pay;
    offered only with a ready resource."""
    return TriggerAbility(
        trigger=OnAttack(), optional=True,
        effects=[CustomEffect(fn=_dexter_pay_and_look)],
        condition=ConditionCheck(Condition.CONTROLLER_N_PLUS_READY_RESOURCES, param=1))


@card_ability("IC27", "56")
def _allegiant_general_pryde_ic27():
    """IC27_56 — Allegiant General Pryde (Unit, 1, 2/2): "When Defeated: Give an
    Experience token to the friendly unit with the most power.  (If multiple units
    are tied, choose one.)"  The ``most_power_among_friendly`` predicate offers
    every tied unit as a target."""
    return TriggerAbility(trigger=WhenDefeated(), effects=[
        GiveToken("Experience", TargetSpec(controller="friendly", kind="unit",
                                           predicates=("most_power_among_friendly",)))])


def _jabba_mark_defender(state, source_ci, target_id, event_ctx):
    """"For this phase, while that unit is defending, the attacker gets +4/+0" —
    the I Have the High Ground TWI_72 shape mirrored: a ``while_attacking_unit_id``
    stats modifier on each unit that could attack it (Jabba's controller's units),
    read at resolution, so a unit arriving later this phase is not covered."""
    if target_id is None:
        return state
    from swu.engine.state import Modifier
    ps = state.player_by_id(actor_of(state, source_ci))
    for ci in ps.ground_arena + ps.space_arena:
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id,
            target_instance_id=ci.instance_id,
            kind="stats",
            value={"power": 4, "hp": 0, "while_attacking_unit_id": target_id},
            duration="this_phase",
        ))
    return state


@card_ability("IC27", "60")
def _jabba_the_hutt_ic27():
    """IC27_60 — Jabba the Hutt (Unit, Hutt/Underworld, 3, 0/8): "Action [Exhaust]:
    Choose an enemy unit.  For this phase, while that unit is defending, the attacker
    gets +4/+0."""
    return ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[CustomEffect(fn=_jabba_mark_defender, target=_ENEMY_UNIT)],
        condition=ConditionCheck(Condition.OPPONENT_N_PLUS_UNITS, param=1))


@card_ability("IC27", "62")
def _admiral_motti_ic27():
    """IC27_62 — Admiral Motti (Unit, Imperial/Official, 4, 2/6; Hidden): "On
    Attack: Give an Experience token to each other friendly Imperial unit."""
    return TriggerAbility(trigger=OnAttack(), effects=[
        GiveToken("Experience", TargetSpec(controller="friendly", kind="unit",
                                           traits=("Imperial",),
                                           predicates=("not_self",),
                                           fixed=EACH_FRIENDLY))])


@card_ability("IC27", "67")
def _darth_vader_ic27_67():
    """IC27_67 — Darth Vader (Unit, Force/Imperial/Sith, 8, 8/8; Ambush): "Each other
    friendly unit gains Ambush."""
    from swu.abilities.registry import ConstantAbility, KeywordGrant
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", predicates=("not_self",)),
        effects=[KeywordGrant("Ambush")])


@card_ability("IC27", "71")
def _avar_kriss_ic27():
    """IC27_71 — Avar Kriss (Unit, Force/Jedi/Republic, 2, 0/5; Raid 1): "This unit
    gains Raid 1 for each other friendly unit."  Stacks on her printed Raid 1."""
    from swu.abilities.registry import ConstantAbility, KeywordGrant, SELF
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", value=1, value_count="other_friendly_units")])


def _cody_give_xp(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import execute_effect
    uid = (event_ctx or {}).get("source_id")
    if not uid or state.find_instance(uid) is None:
        return state
    return execute_effect(state, GiveToken("Experience", TargetSpec()), source_ci, uid,
                          event_ctx)


@card_ability("IC27", "76")
def _clone_commander_cody_ic27():
    """IC27_76 — Clone Commander Cody (Unit, Clone/Republic/Trooper, 4, 4/4): "When
    another friendly Republic unit enters play: Give an Experience token to it."
    The entering unit is ``event_ctx["source_id"]`` (Boba Fett HMW's shape)."""
    from swu.abilities.registry import WhenUnitEntersPlay
    return TriggerAbility(
        trigger=WhenUnitEntersPlay(filter=TargetSpec(
            controller="friendly", kind="unit", traits=("Republic",),
            predicates=("not_self",))),
        effects=[CustomEffect(fn=_cody_give_xp)])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:11 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("IC27", "89")
def _maz_kanata_ic27():
    """IC27_89 — Maz Kanata (Unit, Underworld, 2, 2/1): "Hidden.  When you resource
    a card (including during the regroup phase): Give an Experience token to this
    unit."  The ``WhenYouResourceCard`` observer — every resource site, the regroup
    resource step included, via the ``CardResourced`` log feed.  Hidden is the
    keyword layer."""
    from swu.abilities.registry import SELF, WhenYouResourceCard
    return TriggerAbility(
        trigger=WhenYouResourceCard(),
        effects=[GiveToken("Experience", TargetSpec(fixed=SELF))])


def _mon_mothma_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True, allow_exhausted=True,
                        no_base=True, exclude_source=True,
                        grant_keywords=["Overwhelm"])
    return state


@card_ability("IC27", "77")
def _mon_mothma_ic27():
    """IC27_77 — Mon Mothma (Unit, Official/Rebel, 4, 3/6): "When Played: You may
    attack with another unit, even if it's exhausted.  For this attack, it gains
    Overwhelm and can't attack bases."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_mon_mothma_attack)])


@card_ability("IC27", "79")
def _qui_gon_jinn_ic27():
    """IC27_79 — Qui-Gon Jinn (Unit, Force/Jedi/Republic, 5, 5/5; Sentinel): "When
    Played: Give another friendly unit +2/+2 for this phase."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        ModifyStats(2, 2, TargetSpec(controller="friendly", kind="unit",
                                     predicates=("not_self",)), Duration.THIS_PHASE)])


@card_ability("IC27", "81")
def _mace_windu_ic27_81():
    """IC27_81 — Mace Windu (Unit, Force/Jedi/Republic, 6, 5/5; Ambush): "On Attack:
    Give an Experience token to this unit."""
    from swu.abilities.registry import SELF
    return TriggerAbility(trigger=OnAttack(), effects=[
        GiveToken("Experience", TargetSpec(fixed=SELF))])


@card_ability("IC27", "83")
def _padme_amidala_ic27_83():
    """IC27_83 — Padmé Amidala (Unit, Naboo/Official/Republic, 8, 5/7; Sentinel):
    "Other friendly Heroism units get +3/+3."""
    from swu.abilities.registry import ConstantAbility, StatBonus
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", aspects=("Heroism",),
                          predicates=("not_self",)),
        effects=[StatBonus(power=3, hp=3)])


@card_ability("IC27", "85")
def _inspiring_mentor_ic27():
    """IC27_85 — Inspiring Mentor (Upgrade, Innate, 2): "Attach to a non-Vehicle
    unit.  Attached unit gains: 'On Attack/When Defeated: Give an Experience token to
    another friendly unit.'"  Two ``GrantedAbility`` triggers resolving FROM the host
    (a granted When Defeated is collected off the defeat snapshot); the attach
    restriction is parsed by ``_upgrade_target_spec``."""
    from swu.abilities.registry import GrantedAbility
    give = GiveToken("Experience", TargetSpec(controller="friendly", kind="unit",
                                              predicates=("not_self",)))
    return [GrantedAbility(TriggerAbility(trigger=t, effects=[give]))
            for t in (OnAttack(), WhenDefeated())]


@card_ability("IC27", "86")
def _enfys_nest_ic27():
    """IC27_86 — Enfys Nest (Unit, Underworld, 5, 4/6; Ambush): "While attacking a
    unit that costs 3 or less, this unit gets +2/+0 and gains Overwhelm."  The new
    ``while_attacking_unit_cost_max`` gate (defender's printed cost), read by both
    the stat and the keyword layer."""
    from swu.abilities.registry import ConstantAbility, KeywordGrant, StatBonus, SELF
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[StatBonus(power=2, hp=0), KeywordGrant("Overwhelm")],
        while_attacking_unit_cost_max=3)


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:12 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("IC27", "92")
def _resupply_carrier_ic27():
    """IC27_92 — Resupply Carrier (Unit, Capital Ship/Imperial/Vehicle, 6, 4/5): "When
    Played: You may resource the top card of your deck."  Negotiator IC27_84's ramp,
    offered only while the deck has a card."""
    return TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[
        CustomEffect(fn=_negotiator_resource_top,
                     available_fn=lambda s, src, ctx: bool(
                         s.player_by_id(actor_of(s, src)).deck))])


@card_ability("IC27", "99")
def _eighth_brother_ic27():
    """IC27_99 — Eighth Brother (Unit, Force/Imperial/Inquisitor, 2, 3/1): "When
    Defeated: You may ready an Imperial unit."  Only exhausted Imperial units are
    offered (readying a ready unit does nothing)."""
    from swu.abilities.registry import ReadyCard
    return TriggerAbility(trigger=WhenDefeated(), optional=True, effects=[
        ReadyCard(TargetSpec(kind="unit", traits=("Imperial",),
                             predicates=("exhausted",)))])


@card_ability("IC27", "101")
def _general_hux_ic27():
    """IC27_101 — General Hux (Unit, First Order/Official, 3, 3/4; Overwhelm): "Each
    other friendly First Order unit gets +1/+0 and gains Overwhelm."  His own
    Overwhelm is the keyword layer."""
    from swu.abilities.registry import ConstantAbility, KeywordGrant, StatBonus
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("First Order",),
                          predicates=("not_self",)),
        effects=[StatBonus(power=1, hp=0), KeywordGrant("Overwhelm")])


@card_ability("IC27", "103")
def _grand_inquisitor_ic27():
    """IC27_103 — Grand Inquisitor (Unit, Force/Imperial/Inquisitor, 4, 3/6): "While
    this unit is damaged, he gains Raid 3 and Saboteur."  (The upstream Raid/Saboteur
    tags are the conditional grant, stripped by the keyword sanitiser.)"""
    from swu.abilities.registry import ConstantAbility, KeywordGrant, SELF
    return ConstantAbility(
        target=TargetSpec(fixed=SELF),
        effects=[KeywordGrant("Raid", 3), KeywordGrant("Saboteur")],
        condition=ConditionCheck(Condition.SOURCE_DAMAGED))


def _kylo_ready_if_first_attack(state, source_ci, target_id, event_ctx):
    from swu.abilities.registry import ReadyCard
    from swu.abilities.resolver import execute_effect
    if state.game_memory.unit_attack_counts.get(source_ci.instance_id, 0) != 1:
        return state
    if state.find_instance(source_ci.instance_id) is None:
        return state
    return execute_effect(state, ReadyCard(TargetSpec()), source_ci,
                          source_ci.instance_id, event_ctx)


@card_ability("IC27", "106")
def _kylo_ren_ic27():
    """IC27_106 — Kylo Ren (Unit, First Order/Force, 5, 5/5; Hidden): "On Attack: If
    this is the first time this unit has attacked this phase, ready him."  Reads the
    per-unit ``game_memory.unit_attack_counts`` (== 1: this attack is his first).
    Hidden is the keyword layer."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_kylo_ready_if_first_attack)])


@card_ability("IC27", "115")
def _poe_dameron_ic27_115():
    """IC27_115 — Poe Dameron (Unit, Resistance, 2, 2/4): "When you play another
    Resistance card: This unit gets +1/+0 for this phase."""
    from swu.abilities.registry import SELF
    return TriggerAbility(trigger=WhenYouPlayCard(trait="Resistance"), effects=[
        ModifyStats(1, 0, TargetSpec(fixed=SELF), Duration.THIS_PHASE)])


def _rey_attack_plus_2(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, power_bonus=2)
    return state


@card_ability("IC27", "120")
def _rey_ic27_120():
    """IC27_120 — Rey (Unit, Force, 5, 6/6): "Action [1 resource, discard a card from
    your hand]: Attack with a unit.  It gets +2/+0 for this attack."""
    return ActivatedAbility(costs=[PayResources(1), DiscardCardCost()],
                            effects=[CustomEffect(fn=_rey_attack_plus_2)],
                            title="Attack with a unit (+2/+0)")


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:13 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

def _jyn_ready_up_to_3(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_exhaust_combined_cost
    push_exhaust_combined_cost(state, source_ci, budget=7, max_units=3, ready=True,
                               then_grant_keyword="Saboteur")
    return state


@card_ability("IC27", "123")
def _jyn_erso_ic27():
    """IC27_123 — Jyn Erso (Unit, Rebel, 8, 8/7; Saboteur): "When Played: Ready up to
    3 units with combined cost 7 or less.  They each gain Saboteur for this phase."
    The ``exhaust_combined_cost`` decision in its new READY disposition
    (``ready=True``, ``then_grant_keyword``); "up to" = Finish at any point."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_jyn_ready_up_to_3)])


@card_ability("IC27", "131")
def _cham_syndulla_ic27():
    """IC27_131 — Cham Syndulla: JTL_164 reworded ("If you control fewer resources
    than an opponent, you may resource the top card of your deck"), registered from
    the canonical's own builder."""
    from swu.cards.jtl.abilities import _cham_syndulla
    return _cham_syndulla()


@card_ability("IC27", "137")
def _kintan_intimidator_ic27():
    """IC27_137 — Kintan Intimidator (Unit, Underworld, 1, 1/4): "On Attack: Exhaust
    the defending unit."  A base defender is not a unit, so nothing happens."""
    from swu.abilities.registry import DEFENDER, ExhaustCard
    return TriggerAbility(trigger=OnAttack(),
                          effects=[ExhaustCard(TargetSpec(fixed=DEFENDER, kind="unit"))])


@card_ability("IC27", "139")
def _bib_fortuna_ic27():
    """IC27_139 — Bib Fortuna: SOR_177's text, registered from its own builder."""
    from swu.cards.sor.abilities import _bib_fortuna
    return _bib_fortuna()


def _wat_tambor_attack(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_granted_attack
    push_granted_attack(state, source_ci, optional=True)
    return state


@card_ability("IC27", "143")
def _wat_tambor_ic27():
    """IC27_143 — Wat Tambor (Unit, Official/Separatist, 3, 4/2; Sentinel): "When
    Played: You may attack with a unit."  Sentinel is the keyword layer."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_wat_tambor_attack)])


def _boba_ready_2_resources(state, source_ci, target_id, event_ctx):
    from swu.cards.sor.abilities import _ready_n_resources
    _ready_n_resources(state.player_by_id(actor_of(state, source_ci)), 2)
    return state


@card_ability("IC27", "146")
def _boba_fett_ic27_146():
    """IC27_146 — Boba Fett (Unit, Bounty Hunter/Underworld, 5, 4/7): "When Attack
    Ends: If the defending unit was defeated, you may ready 2 resources."  Readying
    resources is never a drawback, so the "may" is taken automatically (the
    Emperor's Messenger ASH_189 fungible-ready convention)."""
    from swu.abilities.registry import WhenAttackEnds
    return TriggerAbility(trigger=WhenAttackEnds(require_defender_defeated=True),
                          effects=[CustomEffect(fn=_boba_ready_2_resources)])


def _dooku_may_exhaust(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_exhaust_combined_cost
    push_exhaust_combined_cost(state, source_ci, budget=None, max_units=1)
    return state


@card_ability("IC27", "148")
def _count_dooku_ic27_148():
    """IC27_148 — Count Dooku (Unit, Force/Official/Separatist/Sith, 7, 8/7): "Each
    opponent can't ready more than 1 ground unit and 1 space unit during the regroup
    phase.  When Played: You may exhaust a unit."  The new
    ``OpponentRegroupReadyCap`` marker (auto-picks the unit that readies, a noted
    deviation) plus the ``exhaust_combined_cost(max_units=1)`` "you may exhaust a
    unit" (Ahsoka Tano JTL_201)."""
    from swu.abilities.registry import OpponentRegroupReadyCap
    return [OpponentRegroupReadyCap(per_arena=1),
            TriggerAbility(trigger=WhenPlayed(),
                           effects=[CustomEffect(fn=_dooku_may_exhaust)])]


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:14 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("IC27", "150")
def _frozen_in_carbonite_ic27():
    """IC27_150 — Frozen in Carbonite: SHD_193 reworded (en dash in "non–leader"),
    registered from the canonical's own builder."""
    from swu.cards.shd.abilities import _frozen_in_carbonite
    return _frozen_in_carbonite()


def _leia_exhaust_up_to_2(state, source_ci, target_id, event_ctx):
    from swu.engine.actions import push_exhaust_combined_cost
    push_exhaust_combined_cost(state, source_ci, budget=4, max_units=2,
                               same_arena=True)
    return state


@card_ability("IC27", "159")
def _princess_leia_ic27_159():
    """IC27_159 — Princess Leia (Unit, Official/Rebel, 5, 5/5): "When Played/On
    Attack: Exhaust up to 2 units in the same arena with combined cost 4 or less."
    The ``exhaust_combined_cost`` decision with its new ``same_arena`` lock."""
    return [TriggerAbility(trigger=t, effects=[CustomEffect(fn=_leia_exhaust_up_to_2)])
            for t in (WhenPlayed(), OnAttack())]


@card_ability("IC27", "160")
def _tantive_iv_ic27():
    """IC27_160 — Tantive IV (Unit, Capital Ship/Rebel/Vehicle, 5, 3/5): "Each other
    friendly Rebel unit gains Raid 2 and Saboteur."  (The upstream Raid/Saboteur
    tags are the grant, stripped by the keyword sanitiser.)"""
    from swu.abilities.registry import ConstantAbility, KeywordGrant
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Rebel",),
                          predicates=("not_self",)),
        effects=[KeywordGrant("Raid", 2), KeywordGrant("Saboteur")])


@card_ability("IC27", "162")
def _chewbacca_ic27_162():
    """IC27_162 — Chewbacca (Unit, Rebel/Wookiee, 6, 4/6; Sentinel): "While this unit
    is damaged, he gets +4/+0."  Sentinel is the keyword layer."""
    from swu.abilities.registry import ConstantAbility, StatBonus, SELF
    return ConstantAbility(target=TargetSpec(fixed=SELF),
                           effects=[StatBonus(power=4, hp=0)],
                           condition=ConditionCheck(Condition.SOURCE_DAMAGED))


@card_ability("IC27", "175")
def _shoot_first_ic27():
    """IC27_175 — Shoot First: SOR_217 reworded ("before the defending unit"),
    registered from the canonical's own builder."""
    from swu.cards.sor.abilities import _shoot_first
    return _shoot_first()


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:15 — Miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

def _soulless_one_debuff(state, source_ci, target_id, event_ctx):
    """A ``permanent`` −3/−0 sourced by Soulless One (Huyang TWI_110's shape), so it
    lasts exactly while this unit is in play."""
    if target_id is None or state.find_instance(target_id) is None:
        return state
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_ci.instance_id,
        target_instance_id=target_id,
        kind="stats", value={"power": -3, "hp": 0}, duration="permanent"))
    return state


@card_ability("IC27", "19")
def _soulless_one_ic27():
    """IC27_19 — Soulless One (Unit, Fighter/Separatist/Vehicle, 4, 3/5): "When
    Played: Choose an enemy ground unit.  While this unit is in play, the chosen unit
    gets –3/–0."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[CustomEffect(
        fn=_soulless_one_debuff,
        target=TargetSpec(controller="enemy", kind="unit", arena="ground"))])


@card_ability("IC27", "22")
def _moff_gideon_ic27_22():
    """IC27_22 — Moff Gideon (Unit, Imperial/Official, 5, 3/6): "If a friendly unit
    was defeated this phase, this unit costs 2 resources less to play."  A
    conditional ``CostReduction`` (Decimator of Dissidents JTL_138's shape)."""
    from swu.abilities.registry import CostReduction
    return CostReduction(amount=2, condition=ConditionCheck(
        Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE))


def _yoda_neutralise(state, source_ci, target_id, event_ctx):
    """Both halves for this phase: a ``damage_prevention`` (all, combat only) on the
    unit, and LAW_130's dealer-side ``cannot_deal_combat_damage``."""
    if target_id is None or state.find_instance(target_id) is None:
        return state
    from swu.engine.state import Modifier
    for kind, value in (("damage_prevention", {"all": True, "combat_only": True}),
                        ("cannot_deal_combat_damage", {})):
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=source_ci.instance_id, target_instance_id=target_id,
            kind=kind, value=value, duration="this_phase"))
    return state


@card_ability("IC27", "35")
def _yoda_ic27_35():
    """IC27_35 — Yoda (Unit, Force/Jedi/Republic, 3, 3/4): "On Attack: You may choose
    an enemy unit.  Prevent all combat damage that would be dealt to and dealt by
    that unit for this phase."  Choosing the defender protects Yoda this attack."""
    return TriggerAbility(trigger=OnAttack(), optional=True, effects=[CustomEffect(
        fn=_yoda_neutralise, target=TargetSpec(controller="enemy", kind="unit"))])


@card_ability("IC27", "43")
def _raddus_ic27():
    """IC27_43 — Raddus (Unit, Capital Ship/Resistance/Vehicle, 9, 8/9; Restore 3):
    "While this unit is exhausted, cards your opponents play cost 3 resources more."
    ``OpponentPlayTax`` widened to every card type and gated on exhaustion.  Restore
    is the keyword layer."""
    from swu.abilities.registry import OpponentPlayTax
    return OpponentPlayTax(amount=3, card_type="any", while_exhausted=True)


def _krennic_play_big_unit(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_play_from_hand
    ps = state.player_by_id(actor_of(state, source_ci))
    ids = frozenset(c.instance_id for c in ps.hand
                    if isinstance(c.card_def, Unit) and (c.card_def.cost or 0) >= 7)
    if ids:
        push_play_from_hand(state, source_ci, cost_reduction=2, eligible_ids=ids)
    return state


@card_ability("IC27", "57")
def _director_krennic_ic27_57():
    """IC27_57 — Director Krennic (Unit, Imperial/Official, 2, 0/4): "Action
    [Exhaust]: Play a unit that costs 7 or more from your hand.  It costs 2 resources
    less."  ``push_play_from_hand(eligible_ids=)`` over the hand's 7+ units, gated by
    ``CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT`` at ``(2, 7)`` so the exhaust is never
    wasted."""
    return ActivatedAbility(
        costs=[ExhaustSelf()], effects=[CustomEffect(fn=_krennic_play_big_unit)],
        title="Play a unit that costs 7+ from hand (2 less)",
        condition=ConditionCheck(Condition.CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT,
                                 param=(2, 7)))


def _devastator_search(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_search_and_play
    push_search_and_play(
        state, source_ci, window=5, free=True,
        eligible=lambda cd: (isinstance(cd, Unit) and (cd.cost or 0) <= 12
                             and "Villainy" in {a.name for a in (cd.aspects or ())}))
    return state


@card_ability("IC27", "68")
def _devastator_ic27():
    """IC27_68 — Devastator (Unit, Capital Ship/Imperial/Vehicle, 10, 9/9;
    Overwhelm): "When Played: Search the top 5 cards of your deck for a Villainy unit
    that costs 12 or less and play it for free."  ``push_search_and_play(free=True)``
    (Maz Kanata LAW_74's search-and-play).  Overwhelm is the keyword layer."""
    return TriggerAbility(trigger=WhenPlayed(),
                          effects=[CustomEffect(fn=_devastator_search)])


@card_ability("IC27", "104")
def _inquisitors_tie_ic27():
    """IC27_104 — The Inquisitor's TIE (Unit, Fighter/Imperial/Inquisitor/Vehicle, 4,
    4/5): "On Attack: Each player with 4 or more cards in their hand discards a card
    from their hand."  Two gated ``DiscardFromHand`` effects (Every Day, More Lies'
    per-player shape), each player choosing their own card."""
    from swu.abilities.registry import ConditionalEffect, DiscardFromHand
    return TriggerAbility(trigger=OnAttack(), effects=[
        ConditionalEffect(ConditionCheck(Condition.CONTROLLER_HAND_SIZE_MIN, param=4),
                          (DiscardFromHand(count=1, chooser="controller"),), ()),
        ConditionalEffect(ConditionCheck(Condition.OPPONENT_HAND_SIZE_MIN, param=4),
                          (DiscardFromHand(count=1, chooser="opponent"),), ()),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:16 — Miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("IC27", "113")
def _ezra_bridger_ic27_113():
    """IC27_113 — Ezra Bridger (Unit, Force/Jedi/Rebel/Spectre, 2, 1/3; Raid 2): "On
    Attack: Give another friendly Heroism unit Raid 2 for this phase."  His own Raid
    is the keyword layer."""
    from swu.abilities.registry import GrantKeyword
    return TriggerAbility(trigger=OnAttack(), effects=[GrantKeyword(
        "Raid", 2, TargetSpec(controller="friendly", kind="unit", aspects=("Heroism",),
                              predicates=("not_self",)), Duration.THIS_PHASE)])


def _saw_double_power(state, source_ci, target_id, event_ctx):
    """+power equal to the unit's CURRENT effective power, for this phase (Dryden
    Vos SEC_137's doubling)."""
    from swu.engine.actions import compute_power
    from swu.abilities.resolver import _make_modifier
    res = state.find_instance(target_id or "")
    if res is None:
        return state
    bonus = compute_power(state, res[1])
    if bonus > 0:
        state.modifiers.append(_make_modifier(state, source_ci.instance_id, target_id,
                                              power=bonus, hp=0,
                                              duration=Duration.THIS_PHASE))
    return state


@card_ability("IC27", "126")
def _saw_gerrera_ic27_126():
    """IC27_126 — Saw Gerrera (Unit, Rebel, 5, 6/5): "On Attack: You may double
    another friendly unit's power for this phase."  The bonus is the unit's power
    when Saw attacks, so later buffs aren't doubled."""
    return TriggerAbility(trigger=OnAttack(), optional=True, effects=[CustomEffect(
        fn=_saw_double_power,
        target=TargetSpec(controller="friendly", kind="unit", predicates=("not_self",)))])


def _banshee_search(state, source_ci, target_id, event_ctx):
    from swu.cards.models import Unit
    from swu.engine.actions import push_deck_search
    push_deck_search(state, source_ci, count=1, up_to=True, window=5,
                     disposition="top", eligible=lambda cd: not isinstance(cd, Unit))
    return state


@card_ability("IC27", "138")
def _banshee_ic27():
    """IC27_138 — Banshee (Unit, Separatist/Transport/Vehicle, 2, 2/3): "On Attack:
    You may search the top 5 cards of your deck for a non-unit card, reveal it, and
    put it on top of your deck."  ``push_deck_search(disposition="top")``; "you may"
    is the search's ``up_to``."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_banshee_search)])


@card_ability("IC27", "142")
def _greedo_ic27():
    """IC27_142 — Greedo (Unit, Bounty Hunter/Underworld, 3, 5/3; Ambush): "While
    attacking or defending, this unit deals combat damage after the other attacking
    or defending unit."  The new ``DealsCombatDamageLast`` marker, read by
    ``combat._combat_order``.  Ambush is the keyword layer."""
    from swu.abilities.registry import DealsCombatDamageLast
    return DealsCombatDamageLast()


@card_ability("IC27", "149")
def _invisible_hand_ic27():
    """IC27_149 — The Invisible Hand (Unit, Capital Ship/Separatist/Vehicle, 10,
    9/9): "When Played/When Defeated: The next card you play this phase costs 9
    resources less."  ``NextPlayDiscount`` (Count Dooku IC27_14's shape)."""
    disc = NextPlayDiscount(trait=None, amount=9, units_only=False)
    return [TriggerAbility(trigger=t, effects=[disc]) for t in (WhenPlayed(), WhenDefeated())]


def _mando_debuff_exhausted_defender(state, source_ci, target_id, event_ctx):
    from swu.abilities.resolver import _make_modifier
    did = (event_ctx or {}).get("defender_id")
    res = state.find_instance(did or "")
    if res is None or not res[1].exhausted:
        return state
    state.modifiers.append(_make_modifier(state, source_ci.instance_id, did,
                                          power=-4, hp=0, duration=Duration.THIS_ATTACK))
    return state


@card_ability("IC27", "157")
def _the_mandalorian_ic27_157():
    """IC27_157 — The Mandalorian (Unit, Bounty Hunter/Mandalorian, 4, 5/3;
    Shielded): "On Attack: If the defending unit is exhausted, it gets –4/–0 for this
    attack."  Shielded is the keyword layer."""
    return TriggerAbility(trigger=OnAttack(),
                          effects=[CustomEffect(fn=_mando_debuff_exhausted_defender)])


@card_ability("IC27", "161")
def _han_solo_ic27_161():
    """IC27_161 — Han Solo (Unit, Rebel, 6, 4/6; Raid 2): "On Attack: The defending
    unit gets –2/–0 for this attack."  Raid is the keyword layer."""
    from swu.abilities.registry import DEFENDER
    return TriggerAbility(trigger=OnAttack(), effects=[
        ModifyStats(-2, 0, TargetSpec(fixed=DEFENDER), Duration.THIS_ATTACK)])


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:17 — Miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

@card_ability("IC27", "163")
def _bo_katan_kryze_ic27_163():
    """IC27_163 — Bo-Katan Kryze (Unit, Mandalorian, 7, 7/6; Shielded): "When Played:
    Give each enemy unit –7/–0 for this phase."  Shielded is the keyword layer."""
    return TriggerAbility(trigger=WhenPlayed(), effects=[
        ModifyStats(-7, 0, TargetSpec(fixed=EACH_ENEMY, kind="unit"), Duration.THIS_PHASE)])


def _luke_tuck_and_draw(state, source_ci, target_id, event_ctx):
    """Bottom the chosen unit (``_apply_put_on_deck``), then ITS OWNER draws 2."""
    res = state.find_instance(target_id or "")
    if res is None:
        return state
    from swu.engine.actions.zones import _apply_put_on_deck, _draw_cards
    owner_id = res[1].owner_id
    state = _apply_put_on_deck(state, target_id, to_top=False)
    _draw_cards(state, state.player_by_id(owner_id), 2)
    return state


@card_ability("IC27", "165")
def _luke_skywalker_ic27_165():
    """IC27_165 — Luke Skywalker (Unit, Force/Rebel, 8, 9/9): "When Played: You may
    put an enemy non-leader unit on the bottom of its owner's deck.  Its owner draws
    2 cards."  The draw is part of the same "you may": no unit moved, no draw."""
    return TriggerAbility(trigger=WhenPlayed(), optional=True, effects=[CustomEffect(
        fn=_luke_tuck_and_draw,
        target=TargetSpec(controller="enemy", kind="unit", predicates=("non_leader",)))])


@card_ability("IC27", "172")
def _razor_crest_ic27():
    """IC27_172 — Razor Crest (Unit, Mandalorian/Transport/Vehicle, 3, 2/5): "Each
    unit (including friendly units) loses all 'When Defeated' abilities."  The new
    ``UnitsLoseWhenDefeated`` marker, read where triggers are collected."""
    from swu.abilities.registry import UnitsLoseWhenDefeated
    return UnitsLoseWhenDefeated()

