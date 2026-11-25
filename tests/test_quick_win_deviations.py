"""Known-deviation quick wins (2026-11-24).

* "Use this ability only once each round" is enforced on Cad Bane SHD_14,
  Cassian Andor SOR_13 and Agent Kallus SOR_115.
* A leader constant printed on BOTH sides applies while the leader is undeployed
  (Director Krennic SOR_1, Gar Saxon SHD_1).
* A Vehicle takes one Pilot (plus any extra slots) on every Pilot play, not only
  when a leader deploys as a Pilot; R2-D2 JTL_245 may still join a piloted Vehicle.
"""
from __future__ import annotations

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _get_leader, _place_leader,
    _push_deck_top, _fire_other_unit_defeated, _accept_optional_and_run,
)
from tests.test_piloting import _give_resources, _place_vehicle, _put_in_hand


def _offered_accept(state, source_ci):
    from swu.engine.actions import legal_actions, AcceptTrigger
    return any(isinstance(a, AcceptTrigger) and a.source_id == source_ci.instance_id
               for a in legal_actions(state))


# ── Once each round ──────────────────────────────────────────────────────────

def test_SOR_115_kallus_draws_only_once_each_round(repo):
    state = _make_state()
    kallus = _place(state, "P0", _get_card(repo, "SOR", "115"), "ground")
    first = _place(state, "P1", _get_card(repo, "SOR", "135"), "ground")    # unique
    second = _place(state, "P1", _get_card(repo, "SOR", "135"), "ground")
    for _ in range(2):
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    hand = len(state.player_by_id("P0").hand)
    state = _fire_other_unit_defeated(state, first, "P1")
    state = _accept_optional_and_run(state)
    assert len(state.player_by_id("P0").hand) == hand + 1
    state = _fire_other_unit_defeated(state, second, "P1")
    assert not _offered_accept(state, kallus), "the round's use is spent"


def test_SOR_115_declining_does_not_spend_the_round(repo):
    from swu.engine.actions import legal_actions, apply, DeclineTrigger
    state = _make_state()
    kallus = _place(state, "P0", _get_card(repo, "SOR", "115"), "ground")
    first = _place(state, "P1", _get_card(repo, "SOR", "135"), "ground")
    second = _place(state, "P1", _get_card(repo, "SOR", "135"), "ground")
    _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    state = _fire_other_unit_defeated(state, first, "P1")
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, DeclineTrigger)))
    state = _fire_other_unit_defeated(state, second, "P1")
    assert _offered_accept(state, kallus)


def _attack_base(state, attacker):
    from swu.engine.actions import apply, AttackWithUnit
    state.active_player_index = 0
    attacker = state.find_instance(attacker.instance_id)[1]
    attacker.exhausted = False
    return apply(state, AttackWithUnit(attacker.instance_id, None))


def test_SOR_13_cassian_deployed_draw_is_once_each_round(repo):
    state = _make_state()
    cassian = _place(state, "P0", _get_leader(repo, "SOR", "13"), "ground")
    cassian.deployed = True
    for _ in range(2):
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    hand = len(state.player_by_id("P0").hand)
    state = _attack_base(state, cassian)
    state = _accept_optional_and_run(state)
    assert len(state.player_by_id("P0").hand) == hand + 1
    state = _attack_base(state, cassian)                 # re-readied, attacks again
    assert not _offered_accept(state, cassian), "the round's use is spent"


def test_SHD_14_cad_bane_deployed_is_once_each_round(repo):
    from swu.engine.actions import (
        legal_actions, apply, AcceptTrigger, AutoResolveEffects, ChooseOwnTarget,
        ConfirmOpponentDamage)
    from tests.test_shd_cards import _fire_card_played
    state = _make_state()
    cad = _place(state, "P0", _get_card(repo, "SHD", "14"), "ground")
    cad.deployed = True
    played = _place(state, "P0", _get_card(repo, "SHD", "33"), "ground")
    enemy = _place(state, "P1", _get_card(repo, "SOR", "116"), "ground")
    state = _fire_card_played(state, "P0", played)
    for kind in (AcceptTrigger, AutoResolveEffects, ChooseOwnTarget,
                 ConfirmOpponentDamage):
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, kind)
                                  and getattr(a, "target_id", enemy.instance_id)
                                  == enemy.instance_id))
    assert state.find_instance(enemy.instance_id)[1].damage == 2
    state = _fire_card_played(state, "P0", played)
    assert not _offered_accept(state, cad), "the round's use is spent"


# ── Both-sided leader constants ──────────────────────────────────────────────

def test_SOR_1_krennic_buffs_while_undeployed(repo):
    from swu.engine.actions import compute_power
    state = _make_state()
    unit = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
    unit.damage = 1
    printed = compute_power(state, unit)
    _place_leader(state, "P0", _get_leader(repo, "SOR", "1"))
    assert compute_power(state, unit) == printed + 1


def test_SHD_1_gar_saxon_buffs_while_undeployed(repo):
    from swu.engine.actions import compute_power
    from tests.test_shd_cards import TestGarSaxon
    state = _make_state()
    unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
    TestGarSaxon()._attach_real_upgrade(state, repo, unit)
    before = compute_power(state, unit)
    _place_leader(state, "P0", _get_leader(repo, "SHD", "1"))
    assert compute_power(state, unit) == before + 1


def test_undeployed_leader_with_a_deployed_only_constant_buffs_nothing(repo):
    """Nala Se TWI_1's aura is deployed-side only."""
    from swu.engine.actions import compute_power, compute_hp
    from tests.test_twi_cards import _get_leader as _twi_leader
    state = _make_state()
    unit = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
    power, hp = compute_power(state, unit), compute_hp(state, unit)
    _place_leader(state, "P0", _twi_leader(repo, "TWI", "1"))
    assert (compute_power(state, unit), compute_hp(state, unit)) == (power, hp)


# ── One Pilot per Vehicle ────────────────────────────────────────────────────

def _pilot_plays(state):
    from swu.engine.actions import legal_actions, PilotPlay
    return [a for a in legal_actions(state) if isinstance(a, PilotPlay)]


def test_JTL_piloted_vehicle_takes_no_second_pilot(repo):
    from swu.engine.actions import apply, PilotPlay
    from swu.engine.actions.base import IllegalActionError
    import pytest
    state = _make_state()
    vehicle = _place_vehicle(state, "P0")
    first = _put_in_hand(state, "P0", _get_card(repo, "JTL", "139"))     # Dengar
    second = _put_in_hand(state, "P0", _get_card(repo, "JTL", "187"))    # Bossk
    _give_resources(state, "P0", 20)
    state = apply(state, PilotPlay(first.instance_id, vehicle.instance_id))
    state.active_player_index = 0
    assert not any(a.instance_id == second.instance_id for a in _pilot_plays(state))
    with pytest.raises(IllegalActionError):
        apply(state, PilotPlay(second.instance_id, vehicle.instance_id))


def _offered_ids(state):
    return {a.instance_id for a in _pilot_plays(state)}


def _r2_board(repo, *order):
    """A Vehicle and three Pilots in hand; play ``order`` onto it in turn.
    Names: "dengar", "r2", "bossk", "ig88"."""
    from swu.engine.actions import apply, PilotPlay
    state = _make_state()
    vehicle = _place_vehicle(state, "P0")
    cards = {name: _put_in_hand(state, "P0", _get_card(repo, "JTL", num))
             for name, num in (("dengar", "139"), ("r2", "245"),
                               ("bossk", "187"), ("ig88", "141"))}
    _give_resources(state, "P0", 40)
    for name in order:
        state = apply(state, PilotPlay(cards[name].instance_id, vehicle.instance_id))
        state.active_player_index = 0
    return state, {k: v.instance_id for k, v in cards.items()}


def test_JTL_245_r2d2_joins_a_piloted_vehicle_and_another_pilot_follows(repo):
    """Official JTL ruling: "If R2-D2 is attached to a unit, another Pilot still
    can be played or deployed on that unit." — R2-D2 isn't counted."""
    state, ids = _r2_board(repo, "dengar")
    offered = _offered_ids(state)
    assert ids["r2"] in offered and ids["bossk"] not in offered
    state, ids = _r2_board(repo, "dengar", "r2")
    assert ids["bossk"] in _offered_ids(state)
    state, ids = _r2_board(repo, "dengar", "r2", "bossk")      # 3 Pilots aboard
    assert ids["ig88"] not in _offered_ids(state), "R2-D2's one extra slot is used"


def test_JTL_245_r2d2_first_then_two_more_pilots(repo):
    state, ids = _r2_board(repo, "r2", "dengar")
    assert ids["bossk"] in _offered_ids(state)
    state, ids = _r2_board(repo, "r2", "dengar", "bossk")
    assert ids["ig88"] not in _offered_ids(state)
