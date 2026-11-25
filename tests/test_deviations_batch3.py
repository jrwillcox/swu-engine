"""Known-deviation fixes (2026-11-25), open items 1–7:

1. Smuggle and Piloting costs take play discounts, taxes and halving; a Smuggle
   rider ("deal 4 damage to a friendly unit") is charged.
2. "You may play it" plays can be declined.
3. Mandatory "give a token / exhaust" effects can't be stopped early.
4. "When Attack Ends" abilities that need no survival resolve for a defeated
   attacker.
5. Leia Organa SOR_9: a mandatory attack, then ONE optional Rebel follow-up.
6. Cantwell Arrestor Cruiser SEC_37: the ready lock lasts while it is in play.
7. A Saboteur granted for one attack ignores Sentinel when choosing a defender.
"""
from __future__ import annotations

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _push_deck_top, _place_leader,
    _play_event_from_hand,
)
from tests.test_shd_cards import _put_in_hand
from tests.test_smuggle import (
    _add_resource, _fill_resources, _add_deck_card, _synthetic_unit,
)


def _legal(state):
    from swu.engine.actions import legal_actions
    return legal_actions(state)


def _apply(state, act):
    from swu.engine.actions import apply
    return apply(state, act)


# ── 1. Smuggle / Piloting costs ───────────────────────────────────────────────

def test_smuggle_cost_takes_a_pending_discount_and_spends_it(repo):
    from swu.engine.actions import SmugglePlay
    from swu.engine.actions.costs import _smuggle_cost
    state = _make_state()
    unit = _synthetic_unit(cost=3, smuggle_text="Smuggle [3 resources]")
    smug = _add_resource(state, "P0", unit)
    _fill_resources(state, "P0", 2, repo)
    _add_deck_card(state, "P0", repo)
    ps = state.player_by_id("P0")
    assert _smuggle_cost(state, smug, ps) == 3
    state.game_memory.pending_play_discounts.append(
        {"player_id": "P0", "trait": None, "amount": 2})
    assert _smuggle_cost(state, smug, ps) == 1
    act = next(a for a in _legal(state)
               if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
    state = _apply(state, act)
    assert state.game_memory.pending_play_discounts == []
    assert sum(1 for r in state.player_by_id("P0").resources if r.exhausted) == 1


def test_smuggle_cost_is_halved_by_the_starhawk(repo):
    from swu.engine.actions.costs import _smuggle_cost
    state = _make_state()
    _place(state, "P0", _get_card(repo, "JTL", "105"), "space")
    smug = _add_resource(state, "P0",
                         _synthetic_unit(cost=4, smuggle_text="Smuggle [5 resources]"))
    assert _smuggle_cost(state, smug, state.player_by_id("P0")) == 3   # 5 → 3 (round up)


def test_SHD_36_first_light_smuggle_deals_its_rider_damage(repo):
    from swu.engine.actions import SmugglePlay
    state = _make_state()
    fl = _add_resource(state, "P0", _get_card(repo, "SHD", "36"))
    _fill_resources(state, "P0", 11, repo)        # 7 + 4 aspect penalty, from OTHERS
    _add_deck_card(state, "P0", repo)
    assert not [a for a in _legal(state) if isinstance(a, SmugglePlay)
                and a.instance_id == fl.instance_id], "no friendly unit to pay the rider"

    a = _place(state, "P0", _get_card(repo, "SOR", "46"))
    b = _place(state, "P0", _get_card(repo, "SOR", "46"))
    offers = [x for x in _legal(state) if isinstance(x, SmugglePlay)
              and x.instance_id == fl.instance_id]
    assert {x.upgrade_target_id for x in offers} == {a.instance_id, b.instance_id}
    state = _apply(state, next(x for x in offers if x.upgrade_target_id == b.instance_id))
    ps = state.player_by_id("P0")
    assert any(u.instance_id == fl.instance_id for u in ps.space_arena)
    dmg = {u.instance_id: u.damage for u in ps.ground_arena}
    assert dmg == {a.instance_id: 0, b.instance_id: 4}


def test_SHD_36_bot_puts_the_rider_damage_on_a_unit_that_survives(repo):
    from swu.engine.actions import SmugglePlay
    from swu.players.heuristic_bot import HeuristicBot
    state = _make_state()
    _add_resource(state, "P0", _get_card(repo, "SHD", "36"))
    _fill_resources(state, "P0", 11, repo)
    _add_deck_card(state, "P0", repo)
    frail = _place(state, "P0", _get_card(repo, "SOR", "95"))      # 3/3: would die
    sturdy = _place(state, "P0", _get_card(repo, "SOR", "46"))     # 3/7
    from swu.players.heuristic_bot import _card_index, _enemy_base_remaining
    view = state.view_for("P0")
    idx = _card_index(view)
    bot = HeuristicBot("P0", seed=1)
    score = {a.upgrade_target_id: bot._score_main_action(
                 a, view, idx, _enemy_base_remaining(view))
             for a in _legal(state) if isinstance(a, SmugglePlay)}
    assert score[sturdy.instance_id] > score[frail.instance_id]


def test_piloting_cost_takes_a_standing_upgrade_discount_once(repo):
    from tests.test_bot_pilot_plays import _pilot_board
    from swu.engine.actions import PilotPlay
    from swu.engine.actions.costs import _piloting_cost
    state, pilot, vehicle = _pilot_board()
    congress = _place(state, "P0", _get_card(repo, "SEC", "64"))   # first upgrade −1
    ps = state.player_by_id("P0")
    assert _piloting_cost(state, pilot, ps, vehicle.instance_id) == 1
    state = _apply(state, PilotPlay(pilot.instance_id, vehicle.instance_id))
    assert congress.instance_id in state.game_memory.standing_play_discounts_used_this_round


def test_piloting_cost_is_halved_by_the_starhawk(repo):
    from tests.test_bot_pilot_plays import _pilot_board
    from swu.engine.actions.costs import _piloting_cost
    state, pilot, vehicle = _pilot_board()
    _place(state, "P0", _get_card(repo, "JTL", "105"), "space")
    ps = state.player_by_id("P0")
    assert _piloting_cost(state, pilot, ps, vehicle.instance_id) == 1   # 2 → 1


# ── 2. "you may play it" ──────────────────────────────────────────────────────

def test_LOF_123_directed_by_the_force_play_can_be_declined(repo):
    from swu.engine.actions import DeclinePlayFromHand, PlayFromHand
    state = _make_state()
    unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
    # 3 for the event (aspect penalty included), 8 for the unit.
    state, _evt = _play_event_from_hand(state, repo, "LOF", "123", resources=12)
    acts = _legal(state)
    assert any(isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id
               for a in acts)
    state = _apply(state, next(a for a in acts if isinstance(a, DeclinePlayFromHand)))
    assert any(c.instance_id == unit.instance_id
               for c in state.player_by_id("P0").hand)


def test_LAW_66_declining_spares_the_opponent_the_resource(repo):
    from swu.engine.actions import DeclinePlayFromHand
    state = _make_state()
    _fill_resources(state, "P1", 2, repo)
    _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
    before = len(state.player_by_id("P1").resources)
    state, _evt = _play_event_from_hand(state, repo, "LAW", "66", resources=14)
    state = _apply(state, next(a for a in _legal(state)
                               if isinstance(a, DeclinePlayFromHand)))
    assert len(state.player_by_id("P1").resources) == before


def test_LAW_66_plays_an_event_from_the_opponents_resources(repo):
    from swu.engine.actions import PlayFromHand
    state = _make_state()
    evt = _add_resource(state, "P1", _get_card(repo, "SHD", "244"))   # No Bargain
    _fill_resources(state, "P1", 1, repo)
    _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
    _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
    before = len(state.player_by_id("P1").resources)
    state, _e = _play_event_from_hand(state, repo, "LAW", "66", resources=14)
    assert any(isinstance(a, PlayFromHand) and a.instance_id == evt.instance_id
               for a in _legal(state))
    state = _apply(state, PlayFromHand(evt.instance_id))
    p1 = state.player_by_id("P1")
    assert evt.instance_id in {c.instance_id for c in p1.discard}, "owner's discard"
    assert len(p1.resources) == before                  # replaced from the deck top
    assert p1.resources[-1].exhausted


# ── 3. mandatory gives / exhausts ─────────────────────────────────────────────

def test_SEC_196_exhausts_cannot_be_stopped_early(repo):
    from swu.engine.actions import FinishSelectToken, SelectTokenTarget
    state = _make_state()
    _place(state, "P0", _get_card(repo, "SEC", "64"))       # Official
    _place(state, "P0", _get_card(repo, "SEC", "64"))       # Official
    e1 = _place(state, "P1", _get_card(repo, "SOR", "46"))
    e2 = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state, _evt = _play_event_from_hand(state, repo, "SEC", "196")
    acts = _legal(state)
    assert not any(isinstance(a, FinishSelectToken) for a in acts)
    state = _apply(state, SelectTokenTarget(e1.instance_id))
    assert not any(isinstance(a, FinishSelectToken) for a in _legal(state))
    state = _apply(state, SelectTokenTarget(e2.instance_id))
    p1 = state.player_by_id("P1")
    assert all(u.exhausted for u in p1.ground_arena)


def test_SEC_59_disclose_payoff_gift_is_mandatory(repo):
    from swu.engine.actions import FinishSelectToken
    from swu.engine.actions.reveal import _apply_disclose_payoff
    state = _make_state()
    warden = _place(state, "P0", _get_card(repo, "SEC", "59"))
    _place(state, "P1", _get_card(repo, "SOR", "46"))
    _apply_disclose_payoff(state, {
        "payoff": "select_token", "discloser_id": "P0",
        "source_id": warden.instance_id,
        "payoff_args": {"token_type": "Experience", "max_targets": 1,
                        "controller": "any", "kind": "unit", "mandatory": True}})
    assert state.pending_decisions[-1].kind == "select_token"
    assert not any(isinstance(a, FinishSelectToken) for a in _legal(state))


# ── 4. attack-end abilities that need no survival ─────────────────────────────

def _fire_end(state, ctx):
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(state, None, after_all_player_idx=1, event_ctx=ctx)


def _to_discard(state, owner, card_def, iid):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=iid, card_def=card_def, owner_id=owner,
                      zone=Zone.DISCARD)
    state.player_by_id(owner).discard.append(ci)
    return ci


def test_LAW_252_firespray_trades_and_still_creates_a_credit(repo):
    from swu.engine.actions import AttackWithUnit
    state = _make_state()
    fett = _place(state, "P0", _get_card(repo, "LAW", "252"), "space")   # 4/6
    fett.exhausted = False
    fett.damage = 3
    patrol = _place(state, "P1", _get_card(repo, "SOR", "66"), "space")  # 3/4 Sentinel
    state = _apply(state, AttackWithUnit(fett.instance_id, patrol.instance_id))
    ps = state.player_by_id("P0")
    assert not ps.space_arena, "both died"
    assert len(ps.credits) == 1


def test_LAW_46_chirrut_heals_even_when_defeated_in_the_attack(repo):
    from swu.engine.actions import AcceptTrigger
    state = _make_state()
    chirrut = _to_discard(state, "P0", _get_card(repo, "LAW", "46"), "P0_chirrut")
    hurt = _place(state, "P0", _get_card(repo, "SOR", "46"))
    hurt.damage = 3
    state = _fire_end(state, {"attack_ended_departed": chirrut.instance_id,
                              "attack_ended_base_damage": chirrut.instance_id})
    assert any(isinstance(a, AcceptTrigger) and a.source_id == chirrut.instance_id
               for a in _legal(state))


def test_a_survival_only_attack_end_ability_stays_silent(repo):
    state = _make_state()
    verm = _to_discard(state, "P0", _get_card(repo, "LAW", "215"), "P0_verm")
    state = _fire_end(state, {"attack_ended_departed": verm.instance_id})
    assert not state.pending_decisions


def test_TS26_4_padme_follow_up_after_she_is_defeated(repo):
    from swu.engine.actions import AcceptTrigger
    state = _make_state()
    padme = _place_leader(state, "P0", _get_card(repo, "TS26", "4"))
    state = _fire_end(state, {"attack_ended_departed": padme.instance_id})
    assert any(isinstance(a, AcceptTrigger) and a.source_id == padme.instance_id
               for a in _legal(state))


# ── 5. Leia Organa SOR_9 ──────────────────────────────────────────────────────

def test_SOR_9_one_mandatory_attack_then_one_optional_follow_up(repo):
    from swu.engine.actions import AttackWithUnit, DeclineGrantedAttack, UseAbility
    state = _make_state()
    leia = _place_leader(state, "P0", _get_card(repo, "SOR", "9"))
    rebels = [_place(state, "P0", _get_card(repo, "SOR", "46")) for _ in range(3)]
    for r in rebels:
        r.exhausted = False
    state = _apply(state, next(a for a in _legal(state) if isinstance(a, UseAbility)
                               and a.source_id == leia.instance_id))
    acts = _legal(state)
    assert not any(isinstance(a, DeclineGrantedAttack) for a in acts), "mandatory"
    state = _apply(state, next(a for a in acts if isinstance(a, AttackWithUnit)
                               and a.attacker_id == rebels[0].instance_id))
    acts = _legal(state)
    assert any(isinstance(a, DeclineGrantedAttack) for a in acts), "the follow-up is a may"
    assert not any(isinstance(a, AttackWithUnit) and a.attacker_id == rebels[0].instance_id
                   for a in acts)
    state = _apply(state, next(a for a in acts if isinstance(a, AttackWithUnit)
                               and a.attacker_id == rebels[1].instance_id))
    assert not any(d.kind == "granted_attack" for d in state.pending_decisions), \
        "only ONE follow-up"


# ── 6. Cantwell Arrestor Cruiser SEC_37 ───────────────────────────────────────

def test_SEC_37_lock_survives_the_round_and_ends_when_the_cruiser_leaves(repo):
    from swu.abilities.resolver import _apply_return_to_hand
    from swu.engine.actions.reveal import _apply_disclose_payoff
    from swu.engine.actions.turn import _ready_all_cards, _ready_forbidden
    state = _make_state()
    cantwell = _place(state, "P0", _get_card(repo, "SEC", "37"), "space")
    victim = _place(state, "P1", _get_card(repo, "SOR", "46"))
    _apply_disclose_payoff(state, {
        "payoff": "exhaust_unit", "discloser_id": "P0",
        "source_id": cantwell.instance_id,
        "payoff_args": {"target_id": victim.instance_id,
                        "lock_while_source_in_play": True}})
    _ready_all_cards(state)
    _ready_all_cards(state)                     # a second regroup: still locked
    assert victim.exhausted and _ready_forbidden(state, victim)
    state = _apply_return_to_hand(state, cantwell.instance_id)
    victim = state.find_instance(victim.instance_id)[1]
    assert not _ready_forbidden(state, victim)
    _ready_all_cards(state)
    assert not victim.exhausted


# ── 8. two-unit attacks (Darth Maul) ──────────────────────────────────────────

def _maul_vs(repo, d1, d2):
    state = _make_state()
    maul = _place(state, "P0", _get_card(repo, "TWI", "135"))        # 5/6
    maul.exhausted = False
    a = _place(state, "P1", _get_card(repo, *d1))
    b = _place(state, "P1", _get_card(repo, *d2))
    return state, maul, a, b


def test_two_unit_attack_first_strike_spares_the_attacker(repo):
    from swu.engine.actions import AttackTwoUnits
    from swu.engine.state import Modifier
    state, maul, marine, guard = _maul_vs(repo, ("SOR", "95"), ("SOR", "46"))
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(), source_instance_id=maul.instance_id,
        target_instance_id=maul.instance_id, kind="keyword_grant",
        value={"keyword": "First Strike", "value": 0}, duration="this_phase"))
    state = _apply(state, AttackTwoUnits(maul.instance_id, marine.instance_id,
                                         guard.instance_id))
    # The 3/3 Marine dies first and strikes nothing back; the 3/7 survives and hits.
    maul = state.find_instance(maul.instance_id)[1]
    assert maul.damage == 3
    assert state.find_instance(marine.instance_id)[1].zone.name == "DISCARD"


def test_two_unit_attack_fires_each_defenders_when_attacked(repo):
    from swu.engine.actions import AttackTwoUnits
    state, maul, a, b = _maul_vs(repo, ("LAW", "121"), ("LAW", "121"))  # On Defense: Credit
    state = _apply(state, AttackTwoUnits(maul.instance_id, a.instance_id, b.instance_id))
    assert len(state.player_by_id("P1").credits) == 2


# ── 10. alternative costs and optional extras ─────────────────────────────────

def test_SOR_199_bamboozle_paid_by_discarding_a_cunning_card(repo):
    from swu.engine.actions import (
        CommitCostRoute, PayCostRoute, PlayCard, ChooseTarget)
    state = _make_state()
    bamboozle = _put_in_hand(state, "P0", _get_card(repo, "SOR", "199"))
    fodder = _put_in_hand(state, "P0", _get_card(repo, "SOR", "199"))   # Cunning
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    enemy.exhausted = False
    assert any(isinstance(a, PlayCard) and a.instance_id == bamboozle.instance_id
               for a in _legal(state)), "playable with no resources at all"
    state = _apply(state, PlayCard(bamboozle.instance_id))
    assert state.pending_decisions[-1].kind == "cost_route"
    assert not any(isinstance(a, CommitCostRoute) for a in _legal(state))
    state = _apply(state, PayCostRoute(fodder.instance_id))
    state = _apply(state, CommitCostRoute())
    state = _apply(state, next(a for a in _legal(state) if isinstance(a, ChooseTarget)
                               and a.target_id == enemy.instance_id))
    assert state.find_instance(enemy.instance_id)[1].exhausted
    assert fodder.instance_id in {c.instance_id for c in state.player_by_id("P0").discard}


def test_SOR_199_no_prompt_without_a_cunning_card(repo):
    from swu.engine.actions import PlayCard
    state = _make_state()
    bamboozle = _put_in_hand(state, "P0", _get_card(repo, "SOR", "199"))
    _place(state, "P1", _get_card(repo, "SOR", "46"))
    _fill_resources(state, "P0", 6, repo)
    state = _apply(state, PlayCard(bamboozle.instance_id))
    assert all(d.kind != "cost_route" for d in state.pending_decisions)


def test_SHD_10_bossk_may_give_the_pinged_unit_plus_one(repo):
    from tests.test_shd_cards import _attach_bounty_upgrade
    from swu.engine.actions import (
        ChooseTarget, FinishSelectToken, SelectTokenTarget, UseAbility, compute_power)
    state = _make_state()
    bossk = _place_leader(state, "P0", _get_card(repo, "SHD", "10"))
    target = _place(state, "P1", _get_card(repo, "SOR", "46"))
    _attach_bounty_upgrade(state, target, _get_card(repo, "SHD", "68"), "P1")
    before = compute_power(state, target)
    state = _apply(state, next(a for a in _legal(state) if isinstance(a, UseAbility)
                               and a.source_id == bossk.instance_id))
    state = _apply(state, next(a for a in _legal(state) if isinstance(a, ChooseTarget)
                               and a.target_id == target.instance_id))
    acts = _legal(state)
    assert any(isinstance(a, FinishSelectToken) for a in acts), "a may"
    state = _apply(state, SelectTokenTarget(target.instance_id))
    target = state.find_instance(target.instance_id)[1]
    assert target.damage == 1
    assert compute_power(state, target) == before + 1


def test_SHD_228_bounty_posting_offers_to_play_the_drawn_upgrade(repo):
    from tests.test_shd_cards import _put_on_deck
    from swu.engine.actions import SelectSearchCard
    state = _make_state()
    upgrade = _get_card(repo, "SHD", "68")                        # Public Enemy
    _put_on_deck(state, "P0", [_get_card(repo, "SOR", "46"), upgrade])
    _place(state, "P1", _get_card(repo, "SOR", "46"))
    state, _evt = _play_event_from_hand(state, repo, "SHD", "228", resources=12)
    state = _apply(state, next(a for a in _legal(state)
                               if isinstance(a, SelectSearchCard)))
    assert state.pending_decisions[-1].kind == "play_upgrade_from_hand"


def test_LAW_212_malakili_creatures_out_of_play_are_underworld(repo):
    from swu.engine.traits import has_trait
    state = _make_state()
    creature = _put_in_hand(state, "P0", _get_card(repo, "LAW", "163"))
    assert "Creature" in creature.card_def.traits
    assert not has_trait(state, creature, "Underworld")
    _place(state, "P0", _get_card(repo, "LAW", "212"))
    assert has_trait(state, creature, "Underworld")
    # An opponent's Malakili does nothing for my cards.
    theirs = _put_in_hand(state, "P1", _get_card(repo, "LAW", "163"))
    assert not has_trait(state, theirs, "Underworld")


def test_LAW_212_malakili_creature_in_deck_matches_an_underworld_search(repo):
    """A deck search's filter reads the trait layer, so Malakili's grant counts
    for a Creature in the deck (was: printed traits only)."""
    from tests.test_shd_cards import _put_on_deck
    from swu.engine.actions.deck import push_deck_search

    def underworld(cd):
        return "Underworld" in (getattr(cd, "traits", None) or ())

    def candidates(state):
        src = state.player_by_id("P0").ground_arena[0]
        state.pending_decisions.clear()
        push_deck_search(state, src, count=1, eligible=underworld, up_to=True)
        return state.pending_decisions[-1].context["candidate_ids"]

    state = _make_state()
    creature_def = _get_card(repo, "LAW", "163")
    assert "Underworld" not in creature_def.traits
    _put_on_deck(state, "P0", [creature_def])
    creature = state.player_by_id("P0").deck[0]
    _place(state, "P0", _get_card(repo, "SOR", "46"))         # a search source
    assert creature.instance_id not in candidates(state)
    _place(state, "P0", _get_card(repo, "LAW", "212"))         # Malakili
    assert creature.instance_id in candidates(state)


# ── 7. granted Saboteur vs Sentinel ───────────────────────────────────────────

def test_SHD_230_swoop_down_ignores_sentinel(repo):
    from swu.engine.actions import AttackWithUnit
    state = _make_state()
    ship = _place(state, "P0", _get_card(repo, "LAW", "252"), "space")
    ship.exhausted = False
    _place(state, "P1", _get_card(repo, "SOR", "66"), "space")        # Sentinel
    other = _place(state, "P1", _get_card(repo, "SOR", "46"))           # ground
    state, _evt = _play_event_from_hand(state, repo, "SHD", "230")
    targets = {a.defender_id for a in _legal(state) if isinstance(a, AttackWithUnit)}
    assert other.instance_id in targets
    assert None in targets, "the base too"
