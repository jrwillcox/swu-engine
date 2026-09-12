"""
Regression: a unit's own "When Defeated" ability never fired in real play.

``_defeat_unit()`` removes the unit from its arena BEFORE firing the
UnitDefeated event, and ``_collect_triggers()`` only scanned cards currently in
play — so the defeated unit was never a candidate source for its own
WhenDefeated trigger.  Unit tests passed only because they fired the event
manually while the unit was still placed in the arena.

Surfaced by the Phase 4 ability-coverage tracker: Admiral Motti (SOR 226,
"When Defeated: you may ready a Villainy unit"), Yoda, Obi-Wan, and Superlaser
Technician — all self-WhenDefeated cards — showed ZERO firings across thousands
of games despite being defeated constantly.

Fix: ``_defeat_unit()`` now passes the defeated CardInstance via
``event_ctx["defeated_ci"]`` and ``_collect_triggers()`` includes it as a
WhenDefeated source.
"""
from __future__ import annotations

import uuid

import pytest

from tests.dbpath import require_db


@pytest.fixture(scope="module")
def repo():
    from swu.cards.repository import CardRepository
    from pathlib import Path
    db = Path(__file__).resolve().parents[2] / "data" / "swu.db"
    if not db.exists():
        pytest.skip("swu.db not found")
    return CardRepository(db)


def _get_card(repo, set_code, num):
    with repo._con() as con:
        n = str(int(num))
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?", (set_code, n)
        ).fetchone()
        assert row is not None, f"card {set_code}_{num} not found"
        return repo._hydrate(con, row)


def _make_state():
    from swu.engine.state import GameState, PlayerState, CardInstance, Zone, Phase
    from swu.cards.models import Base

    def _base(pid):
        bdef = Base(
            id=abs(hash(pid)) % 99999, card_uid=None, set_code="TST", set_name="T",
            card_number="99", name=f"Base {pid}", subtitle=None, type="Base",
            rarity="Common", is_unique=False, artist=None, text=None, text_styled=None,
            rules=None, rules_styled=None, aspects=(), keywords=(), traits=(), arenas=(),
            image_front_url=None, image_back_url=None, image_front_path=None,
            image_back_path=None, hp=30, epic_action=None,
        )
        return CardInstance(instance_id=f"{pid}_base", card_def=bdef,
                            owner_id=pid, zone=Zone.BASE_ZONE)

    ps0 = PlayerState(player_id="P0")
    ps1 = PlayerState(player_id="P1")
    ps0.base_zone.append(_base("P0"))
    ps1.base_zone.append(_base("P1"))
    return GameState(players=[ps0, ps1], phase=Phase.ACTION,
                     active_player_index=0, round_number=2, initiative_holder=0)


def _place(state, owner_id, card_def, arena="ground", exhausted=False):
    from swu.engine.state import CardInstance, Zone
    zone = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
    ci = CardInstance(instance_id=f"{owner_id}_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=zone)
    ci.exhausted = exhausted
    state.player_by_id(owner_id).ground_arena.append(ci)
    return ci


def test_motti_when_defeated_fires_and_readies_villainy(repo):
    from swu.engine.actions import _defeat_unit, legal_actions, apply
    from swu.engine.actions import AcceptTrigger, ChooseTarget

    motti = _get_card(repo, "SOR", "226")   # When Defeated: ready a Villainy unit
    snow = _get_card(repo, "SOR", "130")    # First Legion Snowtrooper (Villainy)

    state = _make_state()
    motti_ci = _place(state, "P0", motti)
    ally = _place(state, "P0", snow, exhausted=True)
    assert ally.exhausted

    # Defeat Motti through the engine path.
    _defeat_unit(state, state.player_by_id("P0"), motti_ci)

    # The optional WhenDefeated trigger must now be on the stack.
    assert state.pending_decisions, "Motti's When Defeated trigger should fire"
    top = state.pending_decisions[-1]
    assert top.kind == "trigger_option"
    assert top.context.get("card_number") in ("226", "0226")

    # Accept, then ready the exhausted Villainy ally.
    accept = next((a for a in legal_actions(state) if isinstance(a, AcceptTrigger)), None)
    assert accept is not None
    state = apply(state, accept)
    choose = next((a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id), None)
    assert choose is not None, "Should be able to target the Villainy ally"
    state = apply(state, choose)

    result = state.find_instance(ally.instance_id)
    assert result is not None
    _, ci = result
    assert not ci.exhausted, "Motti's When Defeated should have readied the ally"


def test_pending_when_defeated_decision_is_serialisable(repo):
    """The defeated CardInstance must not leak into the persisted decision
    context — it isn't JSON-serialisable and the soak campaign serialises the
    state/view after every action (hidden-info + roundtrip invariants)."""
    require_db()  # engine token lookup / from_json needs the card database
    import json
    from swu.engine.actions import _defeat_unit
    from swu.engine.state import GameState

    motti = _get_card(repo, "SOR", "226")
    snow = _get_card(repo, "SOR", "130")
    state = _make_state()
    motti_ci = _place(state, "P0", motti)
    _place(state, "P0", snow, exhausted=True)  # a legal ready target

    _defeat_unit(state, state.player_by_id("P0"), motti_ci)
    assert state.pending_decisions, "Motti's optional When Defeated should be pending"

    # Both the full state and each player's view must serialise cleanly.
    raw = state.to_json()
    GameState.from_json(raw)  # round-trips
    for pid in ("P0", "P1"):
        view = state.view_for(pid)
        json.loads(view.to_json())  # must not raise TypeError


def test_pending_decision_serialisable_with_attached_upgrade(repo):
    """A defeated unit that carried an upgrade stashes ``defeated_upgrades`` (raw
    CardInstances) in event_ctx for the granted-bounty-from-a-defeated-upgrade
    scan (the-mandalorian:01).  Those must NOT leak into the persisted decision
    context — like ``defeated_ci`` they are not JSON-serialisable, and the soak
    campaign serialises the state after every action.  Regression: the strip in
    _build_ability_decision dropped only ``defeated_ci``, so a WhenDefeated
    trigger pushed by an upgraded unit broke the round-trip."""
    require_db()  # engine token lookup / from_json needs the card database
    import json
    from swu.engine.actions import _defeat_unit
    from swu.engine.state import GameState, CardInstance, Zone

    motti = _get_card(repo, "SOR", "226")   # optional WhenDefeated → persisted decision
    snow = _get_card(repo, "SOR", "130")
    upgrade = _get_card(repo, "SOR", "53")  # Luke's Lightsaber (a real upgrade)
    state = _make_state()
    motti_ci = _place(state, "P0", motti)
    _place(state, "P0", snow, exhausted=True)  # a legal ready target
    up = CardInstance(instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
                      owner_id="P0", zone=Zone.GROUND_ARENA)
    motti_ci.attached_upgrades.append(up)

    _defeat_unit(state, state.player_by_id("P0"), motti_ci)
    assert state.pending_decisions

    raw = state.to_json()
    GameState.from_json(raw)
    for pid in ("P0", "P1"):
        json.loads(state.view_for(pid).to_json())  # must not raise TypeError


def test_when_defeated_collected_for_removed_unit(repo):
    """Lower-level guard: a defeated unit no longer in any arena is still a
    WhenDefeated trigger source via event_ctx['defeated_ci']."""
    from swu.abilities.resolver import _collect_triggers
    from swu.engine.events import UnitDefeated

    motti = _get_card(repo, "SOR", "226")
    state = _make_state()
    motti_ci = _place(state, "P0", motti)
    # Simulate _defeat_unit having already removed it from the arena.
    state.player_by_id("P0").ground_arena.remove(motti_ci)

    evt = UnitDefeated(player_id="P0", instance_id=motti_ci.instance_id,
                       card_name=motti_ci.card_def.display_name)
    triggers = _collect_triggers(state, evt, {"defeated_id": motti_ci.instance_id,
                                              "defeated_ci": motti_ci})
    assert any(src.instance_id == motti_ci.instance_id for src, _, _, _ in triggers), \
        "Removed unit's own WhenDefeated trigger must still be collected"
