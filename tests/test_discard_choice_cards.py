"""Known-deviation fix (2026-11-24): every "discard a card" is the discarding
player's CHOICE — the card-module discards and the activated-ability
``DiscardCardCost`` used to take the first card in hand.

The mechanism is ``push_discard_of_choice(eligible=, payoff=)``: a choice, then a
named ``swu.engine.discard_payoffs`` payoff for the "If you do, …" half.
"""
from __future__ import annotations

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _get_leader, _place_leader,
    _push_deck_top, _fire_when_played, _fire_on_attack, _play_event_from_hand,
)
from tests.test_shd_cards import _put_in_hand

# SOR_128 costs 1, SOR_46 costs 4, SOR_134 costs 6 (units); SOR_120 is an upgrade
# and SOR_74 an event.


def _drive(state, picks=(), accept=True, limit=40):
    """Resolve decisions: take each id in ``picks`` (a discard, a target, …) the
    first time it is offered, accept optional triggers, auto-resolve effects; stop
    at the first decision none of those answers."""
    from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                    AutoResolveEffects)
    picks = list(picks)
    for _ in range(limit):
        if not state.pending_decisions:
            return state
        acts = legal_actions(state)
        act = next((a for a in acts for f in ("instance_id", "target_id")
                    if getattr(a, f, None) in picks), None)
        if act is not None:
            picks.remove(getattr(act, "instance_id", None) or act.target_id)
        elif accept:
            act = next((a for a in acts if isinstance(a, AcceptTrigger)), None)
        if act is None:
            act = next((a for a in acts if isinstance(a, AutoResolveEffects)), None)
        if act is None:
            return state
        state = apply(state, act)
    return state


def _hand_ids(state, pid):
    return [c.instance_id for c in state.player_by_id(pid).hand]


def _discard_offers(state):
    from swu.engine.actions import legal_actions
    top = state.pending_decisions[-1]
    assert top.kind == "discard_excess_from_hand"
    return {a.instance_id for a in legal_actions(state)}


def _use(state, source):
    from swu.engine.actions import legal_actions, apply, UseAbility
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, UseAbility)
                             and a.source_id == source.instance_id))


# ── The activated-ability cost ───────────────────────────────────────────────

def test_SHD_11_discard_cost_is_the_players_choice(repo):
    from swu.engine.actions import compute_power
    state = _make_state()
    kylo = _place_leader(state, "P0", _get_leader(repo, "SHD", "11"))
    unit = _place(state, "P0", _get_card(repo, "SOR", "46"))
    keep = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    pitch = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    power = compute_power(state, unit)
    state = _use(state, kylo)
    assert _discard_offers(state) == {keep.instance_id, pitch.instance_id}
    state = _drive(state, [pitch.instance_id, unit.instance_id])
    assert _hand_ids(state, "P0") == [keep.instance_id]
    assert compute_power(state, state.find_instance(unit.instance_id)[1]) == power + 2


def test_SHD_11_single_card_cost_needs_no_prompt(repo):
    state = _make_state()
    kylo = _place_leader(state, "P0", _get_leader(repo, "SHD", "11"))
    _place(state, "P0", _get_card(repo, "SOR", "46"))
    _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    state = _use(state, kylo)
    assert not state.player_by_id("P0").hand
    assert state.pending_decisions[-1].kind != "discard_excess_from_hand"


def test_SEC_7_cost_min_limits_which_cards_may_pay(repo):
    state = _make_state()
    dryden = _place_leader(state, "P0", _get_leader(repo, "SEC", "7"))
    big1 = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    big2 = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    state = _use(state, dryden)
    assert _discard_offers(state) == {big1.instance_id, big2.instance_id}


def test_LAW_84_discard_two_of_three(repo):
    state = _make_state()
    krr = _place(state, "P0", _get_card(repo, "LAW", "84"))
    a = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    b = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
    c = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    state = _use(state, krr)
    state = _drive(state, [a.instance_id, c.instance_id])
    assert set(_hand_ids(state, "P0")) == {b.instance_id, krr.instance_id}


def test_JTL_14_trench_pitches_a_chosen_3_plus_card_then_draws(repo):
    state = _make_state()
    trench = _place_leader(state, "P0", _get_leader(repo, "JTL", "14"))
    big1 = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    big2 = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    small = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
    state = _use(state, trench)
    assert _discard_offers(state) == {big1.instance_id, big2.instance_id}
    state = _drive(state, [big2.instance_id])
    assert set(_hand_ids(state, "P0")) == {big1.instance_id, small.instance_id,
                                          top.instance_id}


# ── "Discard a card.  If you do, …" ──────────────────────────────────────────

def test_LOF_160_merrin_discards_the_chosen_card_then_deals_2(repo):
    state = _make_state()
    merrin = _place(state, "P0", _get_card(repo, "LOF", "160"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    keep = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    pitch = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    state = _fire_on_attack(state, merrin)
    state = _drive(state, [enemy.instance_id, pitch.instance_id])
    assert _hand_ids(state, "P0") == [keep.instance_id]
    assert state.find_instance(enemy.instance_id)[1].damage == 2


def test_SEC_198_bail_organa_spy_follows_the_chosen_discard(repo):
    state = _make_state()
    bail = _place(state, "P0", _get_card(repo, "SEC", "198"))
    keep = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    pitch = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    units_before = len(state.player_by_id("P0").ground_arena)
    state = _fire_on_attack(state, bail)
    state = _drive(state, [pitch.instance_id])
    assert _hand_ids(state, "P0") == [keep.instance_id]
    assert len(state.player_by_id("P0").ground_arena) == units_before + 1   # Spy


def test_ASH_148_ninth_sister_spreads_the_chosen_cards_cost(repo):
    state = _make_state()
    sister = _place(state, "P0", _get_card(repo, "ASH", "148"))
    _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
    big = _put_in_hand(state, "P1", _get_card(repo, "SOR", "134"))
    state = _fire_when_played(state, sister)
    state = _drive(state)
    assert state.pending_decisions[-1].deciding_player_id == "P1", "the opponent picks"
    state = _drive(state, [big.instance_id])
    top = state.pending_decisions[-1]
    assert top.kind == "distribute_damage" and top.context["pool"] == 6


def test_JTL_201_ahsoka_exhaust_only_if_the_chosen_card_is_a_unit(repo):
    for pick_unit in (False, True):
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "JTL", "201"))
        _place(state, "P1", _get_card(repo, "SOR", "46"))
        unit = _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        event = _put_in_hand(state, "P1", _get_card(repo, "SOR", "74"))
        state = _fire_when_played(state, ahsoka)
        state = _drive(state, [(unit if pick_unit else event).instance_id])
        kinds = [d.kind for d in state.pending_decisions]
        assert ("exhaust_combined_cost" in kinds) is pick_unit


def test_LOF_1_kylo_draws_only_for_a_discarded_upgrade(repo):
    for pick_upgrade in (False, True):
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_leader(repo, "LOF", "1"))
        upg = _put_in_hand(state, "P0", _get_card(repo, "SOR", "120"))
        other = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _use(state, kylo)
        state = _drive(state, [(upg if pick_upgrade else other).instance_id])
        assert len(state.player_by_id("P0").hand) == (2 if pick_upgrade else 1)


def test_ASH_260_watermonger_may_discard_the_card_it_drew(repo):
    state = _make_state()
    monger = _place(state, "P0", _get_card(repo, "ASH", "260"))
    old = _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    drawn = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    state = _fire_when_played(state, monger)
    state = _drive(state)
    assert _discard_offers(state) == {old.instance_id, drawn.instance_id}
    state = _drive(state, [drawn.instance_id])
    assert _hand_ids(state, "P0") == [old.instance_id]


def test_TWI_223_unmasking_looks_only_after_the_chosen_discard(repo):
    state = _make_state()
    _put_in_hand(state, "P0", _get_card(repo, "SOR", "134"))
    pitch = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
    state, _evt = _play_event_from_hand(state, repo, "TWI", "223")
    assert state.pending_decisions[-1].kind == "discard_excess_from_hand"
    state = _drive(state, [pitch.instance_id])
    assert state.pending_decisions[-1].kind == "name_and_discard"


def test_syril_karn_style_may_discard_offers_each_card(repo):
    """``may_discard`` with ``chosen`` (Syril Karn SEC_133, TS26_33): one action per
    hand card; Political Pressure TWI_222's printed RANDOM discard is unchanged."""
    from swu.engine.actions import (legal_actions, push_may_discard_else_damage,
                                    DiscardChosenCard, DiscardRandomCard)
    state = _make_state()
    src = _place(state, "P0", _get_card(repo, "SOR", "46"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    cards = [_put_in_hand(state, "P1", _get_card(repo, "SOR", n)) for n in ("128", "74")]
    push_may_discard_else_damage(state, src, enemy.instance_id, 2)
    acts = legal_actions(state)
    assert {a.instance_id for a in acts if isinstance(a, DiscardChosenCard)} == {
        c.instance_id for c in cards}
    assert not any(isinstance(a, DiscardRandomCard) for a in acts)
