"""Known-deviation fix (2026-11-24): "you" in card code is the CONTROLLER.

About 700 card-module and engine-helper reads of ``source_ci.owner_id`` now go
through ``swu.engine.state.actor_of``: a stolen unit's abilities resolve for the
thief, its When Defeated for its last controller, an upgrade for whoever played it
(it keeps control on an enemy unit, per the Comprehensive Rules), and an event for
the player who played it.
"""
from __future__ import annotations

import uuid

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _push_deck_top, _fire_on_attack,
)
from tests.test_shd_cards import _put_in_hand
from tests.test_discard_choice_cards import _drive


def _steal(state, ci, thief_id):
    """Move ``ci`` into ``thief_id``'s arena (ownership unchanged)."""
    from swu.engine.actions import change_control
    change_control(state, ci, thief_id)
    return state.find_instance(ci.instance_id)[1]


def test_stolen_unit_on_attack_resolves_for_the_thief(repo):
    """Bail Organa SEC_198 stolen by P1: P1 discards from P1's hand, P1 gets the Spy."""
    state = _make_state()
    bail = _place(state, "P0", _get_card(repo, "SEC", "198"))
    bail = _steal(state, bail, "P1")
    p0_card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    p1_card = _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
    p1_units = len(state.player_by_id("P1").ground_arena)
    state.active_player_index = 1
    state = _fire_on_attack(state, bail)
    state = _drive(state, [p1_card.instance_id])
    assert [c.instance_id for c in state.player_by_id("P0").hand] == [p0_card.instance_id]
    assert not state.player_by_id("P1").hand
    assert len(state.player_by_id("P1").ground_arena) == p1_units + 1     # the Spy


def test_stolen_unit_when_defeated_resolves_for_its_last_controller(repo):
    """Profundity JTL_154 stolen by P1 and defeated: "choose a player; they discard"
    goes to P1's opponent — the OWNER, P0."""
    from swu.engine.actions import _defeat_unit
    state = _make_state()
    prof = _place(state, "P0", _get_card(repo, "JTL", "154"), "space")
    prof = _steal(state, prof, "P1")
    for _ in range(2):
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
    _defeat_unit(state, state.player_by_id("P1"), prof)
    state = _drive(state)
    top = state.pending_decisions[-1] if state.pending_decisions else None
    assert top is not None and top.deciding_player_id == "P0", "P0 discards"
    assert len(state.player_by_id("P1").hand) == 1


def test_an_upgrade_on_an_enemy_unit_stays_under_its_players_control(repo):
    from swu.engine.actions import _attach_upgrade
    from swu.engine.state import CardInstance, Zone, actor_of, controller_id
    state = _make_state()
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    upg = CardInstance(f"P0_up_{uuid.uuid4().hex[:6]}", _get_card(repo, "SOR", "120"),
                       "P0", Zone.HAND)
    _attach_upgrade(state, state.player_by_id("P0"), upg, enemy.instance_id)
    upg = next(u for u in state.find_instance(enemy.instance_id)[1].attached_upgrades
               if u.instance_id == upg.instance_id)
    assert controller_id(state, upg) == "P0"
    assert actor_of(state, upg) == "P0"
    # A Pilot the OPPONENT plays onto their own Vehicle is theirs, even if the card
    # came from P0 (it is owned by P0).
    veh = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
    pilot = CardInstance(f"P0_pl_{uuid.uuid4().hex[:6]}", _get_card(repo, "JTL", "139"),
                         "P0", Zone.HAND)
    from swu.engine.actions import _attach_pilot
    _attach_pilot(state, state.player_by_id("P1"), pilot, veh.instance_id)
    assert controller_id(state, pilot) == "P1"


def test_an_event_resolves_for_the_player_who_played_it(repo):
    """Mission Briefing SOR_171 ("draw 2 cards") owned by P0 but played by P1."""
    from swu.engine.actions import _resolve_event_ability
    from swu.engine.state import CardInstance, Zone
    state = _make_state()
    for pid in ("P0", "P1"):
        for _ in range(3):
            _push_deck_top(state, pid, _get_card(repo, "SOR", "128"))
    evt = CardInstance(f"P0_evt_{uuid.uuid4().hex[:6]}", _get_card(repo, "SOR", "171"),
                       "P0", Zone.DISCARD)
    state.player_by_id("P0").discard.append(evt)
    state.active_player_index = 1
    _resolve_event_ability(state, state.player_by_id("P1"), evt, 0)
    state = _drive(state)
    assert len(state.player_by_id("P1").hand) == 2
    assert len(state.player_by_id("P0").hand) == 0


def test_an_unstolen_unit_is_unaffected(repo):
    """The ordinary case: owner == controller, so nothing changes."""
    state = _make_state()
    bail = _place(state, "P0", _get_card(repo, "SEC", "198"))
    card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
    state = _fire_on_attack(state, bail)
    state = _drive(state, [card.instance_id])
    assert not state.player_by_id("P0").hand
