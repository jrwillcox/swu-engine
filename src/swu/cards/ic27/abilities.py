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
    WhenPlayed, OnAttack, WhenDefeated, WhenYouPlayCard,
    DealDamage, DrawCards, CustomEffect, DefeatUnit,
    ExhaustSelf, PayResources,
    Duration, TargetSpec, EACH_ENEMY,
)

_IN_ARENA = ("GROUND_ARENA", "SPACE_ARENA")
_ANY_UNIT = TargetSpec(controller="any", kind="unit")
_ENEMY_UNIT = TargetSpec(controller="enemy", kind="unit")


# ══════════════════════════════════════════════════════════════════════════════
# ic27-set:01 — Direct damage & removal
#
# Darth Sidious IC27_26 ("When you heal damage from your base: Deal that much
# damage to an enemy unit") is NOT encoded: it needs a new base-heal trigger
# (``note_base_healed`` feeds no observer today) — flagged for a framework session.
# ══════════════════════════════════════════════════════════════════════════════


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
