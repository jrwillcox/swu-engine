"""
Regression: a "for this phase" stat buff never wore off.

Reported by a player (bug 2026-07-02-2053): Tactical Advantage TWI_124 ("Give a
unit +2/+2 for this phase") kept its bonus permanently — the buffed unit stayed
+2/+2 for the rest of the game.

Root cause: the engine only ever expired ``this_attack`` and ``this_round``
modifiers (``_expire_modifiers`` was called with those two durations only).
There was NO ``_expire_modifiers("this_phase")`` step, so every "for this phase"
``ModifyStats`` modifier (Tactical Advantage, Moment of Glory SHD_130,
Encouraging Leadership TWI_126, granted keywords, …) persisted indefinitely.

Fix: ``_enter_regroup`` now calls ``_expire_modifiers(s, "this_phase")`` at the
ACTION->REGROUP transition — the moment the action phase in which the buff was
played ends — so the bonus wears off exactly as printed.  An invariant now
asserts no ``this_phase`` modifier survives a round rollover.
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
        assert row is not None, f"card {set_code}_{num} not found"
        return repo._hydrate(con, row)


def _base(pid):
    from swu.engine.state import CardInstance, Zone
    from swu.cards.models import Base
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


def _make_state():
    from swu.engine.state import GameState, PlayerState, Phase
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


def test_this_phase_stat_modifier_expires_entering_regroup(repo):
    """A +2/+2 this_phase modifier is gone once the action phase ends."""
    from swu.engine.actions import compute_power, compute_hp, _enter_regroup
    from swu.abilities.resolver import _make_modifier
    from swu.abilities.registry import Duration

    fleet_lt = _get_card(repo, "SOR", "240")  # Fleet Lieutenant, 3/3
    state = _make_state()
    lt_ci = _place(state, "P1", fleet_lt)

    base_power = compute_power(state, lt_ci)
    base_hp = compute_hp(state, lt_ci)

    # Apply a "+2/+2 for this phase" modifier, exactly as Tactical Advantage does.
    mod = _make_modifier(state, lt_ci.instance_id, lt_ci.instance_id,
                         power=2, hp=2, duration=Duration.THIS_PHASE)
    state.modifiers.append(mod)

    assert compute_power(state, lt_ci) == base_power + 2
    assert compute_hp(state, lt_ci) == base_hp + 2

    # The action phase ends → enter regroup.  The buff must wear off.
    _enter_regroup(state)

    assert not any(m.duration == "this_phase" for m in state.modifiers), \
        "this_phase modifier must be expired when the action phase ends"
    assert compute_power(state, lt_ci) == base_power
    assert compute_hp(state, lt_ci) == base_hp


def test_tactical_advantage_buff_gone_next_round(repo):
    """Full path: play Tactical Advantage TWI_124, then roll to the next round."""
    from swu.engine.actions import (
        legal_actions, apply, compute_power, PlayCard, ChooseTarget, Pass,
    )
    from swu.engine.state import CardInstance, Zone, Phase
    from swu.cards.models import Base
    from swu.engine.invariants import CheckContext, check

    tac_adv = _get_card(repo, "TWI", "124")   # Give a unit +2/+2 for this phase
    fleet_lt = _get_card(repo, "SOR", "240")  # 3/3 target

    state = _make_state()
    lt_ci = _place(state, "P1", fleet_lt)
    base_power = compute_power(state, lt_ci)

    tac_ci = CardInstance(instance_id="P1_tac", card_def=tac_adv,
                          owner_id="P1", zone=Zone.HAND)
    state.player_by_id("P1").hand.append(tac_ci)

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

    # Play Tactical Advantage and target Fleet Lieutenant.
    play = next((a for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == tac_ci.instance_id), None)
    assert play is not None, "Tactical Advantage should be playable"
    state = apply(state, play)
    choose = next((a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == lt_ci.instance_id), None)
    assert choose is not None, "Should be able to target Fleet Lieutenant"
    state = apply(state, choose)

    lt_now = next(c for c in state.player_by_id("P1").ground_arena
                  if c.instance_id == lt_ci.instance_id)
    assert compute_power(state, lt_now) == base_power + 2, "buff should be active this phase"

    # Both players pass → ACTION ends, REGROUP, then a new ACTION round begins.
    def _pass_until_new_round(st):
        start_round = st.round_number
        for _ in range(50):
            if st.round_number > start_round and st.phase == Phase.ACTION:
                return st
            legal = legal_actions(st)
            act = next((a for a in legal if isinstance(a, Pass)), None)
            if act is None:
                act = legal[0]
            st = apply(st, act)
        raise AssertionError("did not reach the next action round")

    state = _pass_until_new_round(state)

    assert not any(m.duration == "this_phase" for m in state.modifiers), \
        "no this_phase modifier may survive into the next round"
    lt_next = next(c for c in state.player_by_id("P1").ground_arena
                   if c.instance_id == lt_ci.instance_id)
    assert compute_power(state, lt_next) == base_power, \
        "Tactical Advantage's +2/+2 must have worn off after its phase"

    ctx = CheckContext.from_state(state)
    check(state, ctx)
