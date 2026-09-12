"""
Regression: a unit kept alive only by a buff (e.g. General Dodonna's Constant
"Other friendly Rebel units get +1/+1") was NOT defeated when the buff source
left play, even though its damage then met or exceeded its effective HP.

Found by the Phase 4 soak campaign: 148/10000 games tripped the invariant
"Defeated unit X still in arena (damage=D, compute_hp=D)".  The shared
mechanism in every case was an effective-HP *drop* (buff source bounced by
Waylay, a duration modifier expiring, an upgrade removed) with no state-based
defeat check afterward.  Combat and direct-damage effects defeated units at the
point of dealing lethal damage, but nothing swept the board when HP fell.

Fix: ``apply()`` now runs ``_sweep_defeated_units()`` — a fixed-point
state-based defeat check (SWU CR: a unit with damage >= HP is defeated) — after
every action resolves and the board has settled.

Minimal reproduction (soak seed=4130): P1 plays General Dodonna (+1/+1 to other
Rebels), Fleet Lieutenant (3/3 Rebel) becomes 4/4 and survives 3 damage, then
P1 plays Waylay returning their own Dodonna to hand.  Fleet Lieutenant drops
back to 3 HP with 3 damage and must be defeated.
"""
from __future__ import annotations

import uuid

import pytest


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
        if row is None:
            for pad in (f"{int(n):03d}", f"{int(n):04d}"):
                row = con.execute(
                    "SELECT * FROM cards WHERE set_code=? AND card_number=?", (set_code, pad)
                ).fetchone()
                if row:
                    break
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
                     active_player_index=1, round_number=2, initiative_holder=1)


def _place(state, owner_id, card_def, arena="ground"):
    from swu.engine.state import CardInstance, Zone
    zone = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
    ci = CardInstance(instance_id=f"{owner_id}_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=zone)
    (state.player_by_id(owner_id).ground_arena if arena == "ground"
     else state.player_by_id(owner_id).space_arena).append(ci)
    return ci


def test_sweep_defeats_unit_when_buff_source_removed(repo):
    """Direct test of the state-based defeat sweep on an effective-HP drop."""
    from swu.engine.actions import compute_hp, _sweep_defeated_units
    from swu.engine.state import Zone

    dodonna = _get_card(repo, "SOR", "242")   # Constant: other friendly Rebels +1/+1
    fleet_lt = _get_card(repo, "SOR", "240")  # Fleet Lieutenant, 3/3 Rebel

    state = _make_state()
    dod_ci = _place(state, "P1", dodonna)
    lt_ci = _place(state, "P1", fleet_lt)

    # Dodonna buffs Fleet Lieutenant to 3+1 = 4 HP.
    assert compute_hp(state, lt_ci) == 4
    lt_ci.damage = 3  # survives at 3/4

    _sweep_defeated_units(state)
    assert any(c.instance_id == lt_ci.instance_id
               for c in state.player_by_id("P1").ground_arena), \
        "Fleet Lieutenant should still be alive while buffed (3 dmg < 4 HP)"

    # Remove the buff source (as Waylay would).
    state.player_by_id("P1").ground_arena.remove(dod_ci)

    # Now Fleet Lieutenant is at 3 damage with 3 effective HP → defeated.
    assert compute_hp(state, lt_ci) == 3
    _sweep_defeated_units(state)

    arena_ids = [c.instance_id for c in state.player_by_id("P1").ground_arena]
    assert lt_ci.instance_id not in arena_ids, \
        "Fleet Lieutenant must be defeated once its buff is gone"
    assert lt_ci.zone == Zone.DISCARD


def test_waylay_bounce_defeats_now_lethal_rebel(repo):
    """Full apply() path: bouncing the buff source defeats the now-lethal unit."""
    from swu.engine.actions import (
        legal_actions, apply, compute_hp, PlayCard, ChooseTarget,
    )
    from swu.engine.state import CardInstance, Zone

    dodonna = _get_card(repo, "SOR", "242")
    fleet_lt = _get_card(repo, "SOR", "240")
    waylay = _get_card(repo, "SOR", "222")  # Return a non-leader unit to hand

    state = _make_state()
    dod_ci = _place(state, "P1", dodonna)
    lt_ci = _place(state, "P1", fleet_lt)
    lt_ci.damage = 3
    assert compute_hp(state, lt_ci) == 4  # alive while buffed

    # Put Waylay in P1's hand and give resources to play it.
    way_ci = CardInstance(instance_id="P1_waylay", card_def=waylay,
                          owner_id="P1", zone=Zone.HAND)
    state.player_by_id("P1").hand.append(way_ci)
    from swu.cards.models import Base
    res_def = Base(
        id=99990, card_uid=None, set_code="TST", set_name="T", card_number="RES",
        name="Resource", subtitle=None, type="Base", rarity="Common", is_unique=False,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(), image_front_url=None,
        image_back_url=None, image_front_path=None, image_back_path=None,
        hp=0, epic_action=None,
    )
    for _ in range(5):
        r = CardInstance(instance_id=f"P1_res_{uuid.uuid4().hex[:4]}",
                         card_def=res_def, owner_id="P1", zone=Zone.RESOURCES)
        r.exhausted = False
        state.player_by_id("P1").resources.append(r)

    # Play Waylay.
    play = next((a for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == way_ci.instance_id), None)
    assert play is not None, "Waylay should be playable"
    state = apply(state, play)

    # Choose to bounce our own Dodonna.
    choose = next((a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == dod_ci.instance_id), None)
    assert choose is not None, "Should be able to target Dodonna with Waylay"
    state = apply(state, choose)

    # Dodonna is back in hand; Fleet Lieutenant lost its buff and is defeated.
    arena_ids = [c.instance_id for c in state.player_by_id("P1").ground_arena]
    assert dod_ci.instance_id not in arena_ids
    assert lt_ci.instance_id not in arena_ids, \
        "Fleet Lieutenant must be defeated by the state-based sweep after the bounce"

    # And the invariant checker is happy with the resulting state.
    from swu.engine.invariants import CheckContext, check
    ctx = CheckContext.from_state(state)
    check(state, ctx)
