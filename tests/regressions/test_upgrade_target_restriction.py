"""Regression: upgrade plays ignored the card's "Attach to …" restriction.

`legal_actions` enumerated an upgrade play against *every* unit in play
(`_all_units_in_play`, both players' arenas) with no regard for the upgrade's
printed attachment restriction. So "Attach to a friendly unit" / "Attach to a
Vehicle unit" upgrades were offered against illegal targets, and the apply path
attached them without validation.

Fix: `_upgrade_target_spec` parses the "Attach to …" clause into a `TargetSpec`;
`legal_actions` only offers matching targets and `_attach_upgrade` rejects a
non-matching target. Parsing is conservative — an upgrade with no parseable
restriction (e.g. Resilient) is still attachable to ANY unit, friendly or
enemy, per CR ("A player may play an upgrade onto an enemy unit.").
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
        instance_id=f"{owner_id}_u_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.GROUND_ARENA,
    )
    state.player_by_id(owner_id).ground_arena.append(ci)
    return ci


def _put_in_hand(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_h_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _give_resources(state, owner_id, n):
    """Give the player N ready resource cards (any card def works as a stand-in)."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    # Use whatever base def the repo already loaded as an inert filler card_def;
    # resources are never inspected beyond their exhausted flag.
    filler = ps.ground_arena[0].card_def if ps.ground_arena else None
    for _ in range(n):
        ps.resources.append(CardInstance(
            instance_id=f"{owner_id}_r_{uuid.uuid4().hex[:6]}",
            card_def=filler, owner_id=owner_id, zone=Zone.RESOURCES,
        ))


# ── Card-number constants ─────────────────────────────────────────────────────
RESILIENT = ("SOR", "69")              # no restriction (+0/+3)
LEGAL_AUTHORITY = ("SHD", "124")       # "Attach to a friendly unit"
HARDPOINT = ("SOR", "121")             # "Attach to a VEHICLE unit"
SHUTTLE = ("SOR", "110")               # Frontline Shuttle — a Vehicle unit
LEIA = ("SOR", "189")                  # Leia Organa — a non-Vehicle unit


# ── Parser unit tests ─────────────────────────────────────────────────────────
def test_spec_none_for_unrestricted_upgrade(repo):
    from swu.engine.actions import _upgrade_target_spec
    assert _upgrade_target_spec(_get_card(repo, *RESILIENT)) is None


def test_spec_friendly_only(repo):
    from swu.engine.actions import _upgrade_target_spec
    spec = _upgrade_target_spec(_get_card(repo, *LEGAL_AUTHORITY))
    assert spec is not None and spec.controller == "friendly"


def test_spec_vehicle_trait(repo):
    from swu.engine.actions import _upgrade_target_spec
    spec = _upgrade_target_spec(_get_card(repo, *HARDPOINT))
    assert spec is not None and "Vehicle" in spec.traits


# ── legal_actions filtering ───────────────────────────────────────────────────
def test_friendly_only_upgrade_skips_enemy_unit(repo):
    """Legal Authority (friendly-only) must only be offered on the friendly unit."""
    from swu.engine.actions import legal_actions, PlayCard
    state = _make_state()
    mine = _place_unit(state, "P0", _get_card(repo, *LEIA))
    theirs = _place_unit(state, "P1", _get_card(repo, *LEIA))
    _give_resources(state, "P0", 12)
    upg = _put_in_hand(state, "P0", _get_card(repo, *LEGAL_AUTHORITY))

    targets = {
        a.upgrade_target_id
        for a in legal_actions(state)
        if isinstance(a, PlayCard) and a.instance_id == upg.instance_id
    }
    assert targets == {mine.instance_id}, \
        "friendly-only upgrade must not be offered against an enemy unit"
    assert theirs.instance_id not in targets


def test_vehicle_upgrade_skips_non_vehicle(repo):
    """Hardpoint Heavy Blaster (Vehicle only) only attaches to the Vehicle unit."""
    from swu.engine.actions import legal_actions, PlayCard
    state = _make_state()
    shuttle = _place_unit(state, "P0", _get_card(repo, *SHUTTLE))    # Vehicle
    leia = _place_unit(state, "P0", _get_card(repo, *LEIA))          # non-Vehicle
    _give_resources(state, "P0", 12)
    upg = _put_in_hand(state, "P0", _get_card(repo, *HARDPOINT))

    targets = {
        a.upgrade_target_id
        for a in legal_actions(state)
        if isinstance(a, PlayCard) and a.instance_id == upg.instance_id
    }
    assert targets == {shuttle.instance_id}
    assert leia.instance_id not in targets


def test_unrestricted_upgrade_still_offered_on_enemy(repo):
    """Resilient has no restriction → enemy units remain legal targets (CR)."""
    from swu.engine.actions import legal_actions, PlayCard
    state = _make_state()
    mine = _place_unit(state, "P0", _get_card(repo, *LEIA))
    theirs = _place_unit(state, "P1", _get_card(repo, *LEIA))
    _give_resources(state, "P0", 12)
    upg = _put_in_hand(state, "P0", _get_card(repo, *RESILIENT))

    targets = {
        a.upgrade_target_id
        for a in legal_actions(state)
        if isinstance(a, PlayCard) and a.instance_id == upg.instance_id
    }
    assert targets == {mine.instance_id, theirs.instance_id}


# ── apply-time guard ──────────────────────────────────────────────────────────
def test_apply_rejects_illegal_enemy_target(repo):
    """Forcing a friendly-only upgrade onto an enemy unit must raise."""
    from swu.engine.actions import apply, PlayCard, IllegalActionError
    state = _make_state()
    _place_unit(state, "P0", _get_card(repo, *LEIA))
    theirs = _place_unit(state, "P1", _get_card(repo, *LEIA))
    _give_resources(state, "P0", 12)
    upg = _put_in_hand(state, "P0", _get_card(repo, *LEGAL_AUTHORITY))

    with pytest.raises(IllegalActionError):
        apply(state, PlayCard(upg.instance_id, theirs.instance_id))
