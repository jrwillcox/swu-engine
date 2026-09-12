"""Regression: an upgrade's own ``WhenPlayed`` trigger never fired.

Soak finding (10k campaign): Luke's Lightsaber (SOR_53) and Vader's Lightsaber
(SOR_136) — the only two registered upgrade ``WhenPlayed`` abilities, both
present in the starter decks — showed ZERO firings across 10,000 games.

Root cause: ``_collect_triggers`` gathered trigger sources only from
``_cards_in_play`` (the ground/space arenas). A freshly-played upgrade lives in
its host unit's ``attached_upgrades`` list, never directly in an arena, so the
upgrade was never considered as a trigger source and its ``WhenPlayed`` ability
could not fire. Fix: special-case the ``UpgradePlayed`` event in
``_collect_triggers`` (mirrors the ``UnitDefeated`` / ``defeated_ci`` special
case), locating the upgrade by ``event.instance_id`` and collecting its
``WhenPlayed`` triggers.
"""
from __future__ import annotations

import sqlite3
import uuid

import pytest

from tests.dbpath import require_db


@pytest.fixture(scope="module")
def repo():
    from swu.cards.repository import CardRepository
    return CardRepository(require_db())


def _get_card(repo, set_code, num):
    con = sqlite3.connect(require_db())
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?",
            (set_code, num),
        ).fetchone()
        if row is None:
            raise KeyError(f"Card not found: {set_code}_{num}")
        return repo._hydrate(con, row)
    finally:
        con.close()


def _make_state():
    from swu.engine.state import GameState, PlayerState, Phase
    return GameState(
        players=[PlayerState(player_id="P0"), PlayerState(player_id="P1")],
        phase=Phase.ACTION,
        active_player_index=0,
        round_number=1,
        initiative_holder=0,
    )


def _place_unit(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.GROUND_ARENA,
    )
    state.player_by_id(owner_id).ground_arena.append(ci)
    return ci


def _attach_and_fire_upgrade(state, host_ci, upgrade_def):
    """Attach an upgrade to host and fire the UpgradePlayed event, as apply() does."""
    from swu.engine.state import CardInstance
    from swu.engine.events import UpgradePlayed
    from swu.abilities.resolver import fire_triggered_abilities
    upg_ci = CardInstance(
        instance_id=f"{host_ci.owner_id}_upg_{uuid.uuid4().hex[:4]}",
        card_def=upgrade_def, owner_id=host_ci.owner_id, zone=host_ci.zone,
    )
    host_ci.attached_upgrades.append(upg_ci)
    evt = UpgradePlayed(
        player_id=host_ci.owner_id,
        instance_id=upg_ci.instance_id,
        card_name=upgrade_def.display_name,
        attached_to_instance_id=host_ci.instance_id,
    )
    state.event_log.append(evt)
    after_idx = 1 - state.player_index(host_ci.owner_id)
    state = fire_triggered_abilities(
        state, evt, after_all_player_idx=after_idx,
        event_ctx={"attached_to_id": host_ci.instance_id},
    )
    return state, upg_ci


def test_upgrade_when_played_trigger_is_collected(repo):
    """Playing an upgrade with a WhenPlayed trigger must offer the trigger."""
    luke = _get_card(repo, "SOR", "5")       # Luke Skywalker (leader as unit)
    saber = _get_card(repo, "SOR", "53")     # Luke's Lightsaber
    state = _make_state()
    host = _place_unit(state, "P0", luke)
    host.deployed = True
    host.damage = 2

    state, _ = _attach_and_fire_upgrade(state, host, saber)

    # Optional WhenPlayed → an AcceptTrigger/DeclineTrigger decision is pushed.
    from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
    acts = legal_actions(state)
    assert any(isinstance(a, AcceptTrigger) for a in acts), \
        "Upgrade WhenPlayed trigger was not collected (regression)"
    assert any(isinstance(a, DeclineTrigger) for a in acts)


def test_conditional_upgrade_trigger_not_offered_on_wrong_host(repo):
    """A host-gated WhenPlayed (Luke's Lightsaber's "If attached unit is Luke
    Skywalker") must NOT prompt the player when attached to any other unit — the
    trigger does nothing there, so the player should never see a decision.
    """
    from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
    arc = _get_card(repo, "SOR", "44")       # Restored ARC-170 (not Luke)
    saber = _get_card(repo, "SOR", "53")     # Luke's Lightsaber
    state = _make_state()
    host = _place_unit(state, "P0", arc)
    host.deployed = True
    host.damage = 2

    state, _ = _attach_and_fire_upgrade(state, host, saber)

    assert not state.pending_decisions, \
        "Host-gated trigger should not push a decision on the wrong host"
    acts = legal_actions(state)
    assert not any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts), \
        "Player must not be prompted for a trigger that cannot apply"
    # Host took no benefit (damage unchanged, no Shield).
    _, h = state.find_instance(host.instance_id)
    assert h.damage == 2


def test_lukes_lightsaber_heals_and_shields_luke(repo):
    """Accepting Luke's Lightsaber on Luke heals all damage and grants a Shield."""
    luke = _get_card(repo, "SOR", "5")
    saber = _get_card(repo, "SOR", "53")
    state = _make_state()
    host = _place_unit(state, "P0", luke)
    host.deployed = True
    host.damage = 4

    state, _ = _attach_and_fire_upgrade(state, host, saber)

    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    from swu.engine.keywords import shields_on
    accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
    state = apply(state, accept)
    # Drain any follow-up resolution decisions (AutoResolveEffects for the
    # targetless CustomEffect) until control returns to normal play.
    while state.pending_decisions:
        state = apply(state, legal_actions(state)[0])

    result = state.find_instance(host.instance_id)
    assert result is not None
    _, healed = result
    assert healed.damage == 0, "Luke's Lightsaber should heal all damage"
    assert shields_on(healed) >= 1, "Luke's Lightsaber should grant a Shield"
