"""
Regression: two bugs surfaced by the ``ahsoka-tano`` graduation soak (mirror
match, 2026-06-27).

1. **Combat double-defeat → duplicate instance_id.**  In the unit-combat pipeline
   (``_resolve_unit_combat_step2``), ``attacker_dead`` / ``defender_dead`` are
   computed up front, then the attacker is defeated first.  When the attacker has
   (or a board observer has) a ``WhenDefeated`` trigger that deals area damage —
   e.g. Hevy TWI_164 "When Defeated: Deal 1 damage to each enemy ground unit" —
   that damage can ALREADY defeat the still-in-arena defender *inline*
   (``_apply_deal_damage`` → ``_defeat_unit``), homing it to base_zone (leader) or
   discard.  The combat step then defeated the already-removed defender a *second*
   time, appending the same instance to base_zone/discard twice → the
   "Duplicate instance_id" invariant.  Fix: re-check each combatant is still in its
   arena (``_find_in_arenas``) before the combat-defeat call.

2. **return_from_discard → exhausted card in HAND.**  A unit defeated while
   exhausted lands in discard still exhausted (discard carries no exhaust meaning).
   The ``return_from_discard`` seam (Tranquility TWI_246 / Razor Crest SHD_44)
   moved such a card from discard to hand without clearing the flag, tripping the
   zone/exhaust-sanity invariant ("no exhausted cards in HAND").  Fix:
   ``_finish_return_from_discard`` now clears ``exhausted`` and ``damage`` — a card
   returned to hand must be a clean card (the Sarlacc LAW_163 discard→deck fix,
   mirrored for the discard→hand path).
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


def test_combat_defeat_with_attacker_aoe_does_not_double_home_defender(repo):
    """Hevy (WhenDefeated: deal 1 to each enemy ground unit) attacks a defender it
    trades with; Hevy's own defeat AoE must not re-home the just-defeated defender.

    Hevy TWI_164 is a 2/2.  We give it Raid via the board so it deals lethal to a
    3-HP defender, and the defender trades back to kill Hevy (2 dmg ≥ Hevy's 2 HP).
    When Hevy is defeated first, its "deal 1 to each enemy ground unit" hits the
    defender, which is already at lethal combat damage → defeated inline.  The
    combat step must then NOT defeat the (already-removed) defender again."""
    from swu.engine.actions import legal_actions, apply, AttackWithUnit, compute_hp
    from swu.engine.invariants import CheckContext, check

    hevy = _get_card(repo, "TWI", "164")          # 2/2, Coordinate Raid 2 + WhenDefeated AoE
    defender_card = _get_card(repo, "SOR", "46")  # 3/7 — survives one hit, hits back

    state = _make_state()
    # Active player is P1; make Hevy the P1 attacker so it is defeated by the trade.
    hevy_ci = _place(state, "P1", hevy)
    defender_ci = _place(state, "P0", defender_card)
    # Pre-damage the defender so Hevy's 2 power + the 1 AoE on defeat is lethal,
    # and pre-damage Hevy so the defender's 3 power kills it back this combat.
    defender_ci.damage = compute_hp(state, defender_ci) - 2  # 2 from lethal
    # Attack: defender deals 3 → Hevy (2 HP) dies; Hevy deals 2 → defender at -1 from
    # lethal; Hevy's WhenDefeated AoE deals the final 1 → defender defeated inline.
    attack = next(a for a in legal_actions(state)
                  if isinstance(a, AttackWithUnit)
                  and a.attacker_id == hevy_ci.instance_id
                  and a.defender_id == defender_ci.instance_id)
    state = apply(state, attack)

    # Resolve any pending decisions with safe defaults (the bot's path).
    from swu.players.heuristic_bot import HeuristicBot
    bot0 = HeuristicBot("P0", seed=1)
    bot1 = HeuristicBot("P1", seed=2)
    guard = 0
    while state.pending_decisions and guard < 50:
        top = state.pending_decisions[-1]
        bot = bot0 if top.deciding_player_id == "P0" else bot1
        state = apply(state, bot.choose_action(state.view_for(top.deciding_player_id),
                                               legal_actions(state)))
        guard += 1

    # No instance appears twice anywhere — the invariant checker enforces it.
    ctx = CheckContext.from_state(state)
    check(state, ctx)

    # Specifically: the defender's instance is in exactly one zone, once.
    all_ids = [ci.instance_id
               for ps in state.players
               for zone in (ps.ground_arena, ps.space_arena, ps.base_zone,
                            ps.hand, ps.discard)
               for ci in zone]
    assert all_ids.count(defender_ci.instance_id) <= 1


def test_return_from_discard_clears_exhausted(repo):
    """An exhausted unit in the discard pile, returned to hand via Tranquility's
    return_from_discard seam, must arrive in hand un-exhausted (clean card)."""
    from swu.engine.actions import (
        push_return_from_discard, legal_actions, apply,
        SelectDiscardCard, FinishReturnFromDiscard,
    )
    from swu.engine.state import CardInstance, Zone
    from swu.engine.invariants import CheckContext, check
    from swu.cards.models import Unit

    commando = _get_card(repo, "TWI", "243")  # Republic Commando (a Republic unit)
    src = _get_card(repo, "TWI", "246")       # Tranquility (the returner) as a stand-in source

    state = _make_state()
    # A source unit in P0's arena so push_return_from_discard has a source_ci.
    src_ci = _place(state, "P0", _get_card(repo, "SOR", "128"))
    # The exhausted Republic Commando sitting in P0's discard pile.
    disc_ci = CardInstance(instance_id="P0_disc_cmd", card_def=commando,
                           owner_id="P0", zone=Zone.DISCARD)
    disc_ci.exhausted = True
    disc_ci.damage = 1
    state.player_by_id("P0").discard.append(disc_ci)

    def _is_republic_unit(cd):
        return isinstance(cd, Unit) and "Republic" in (getattr(cd, "traits", None) or ())

    push_return_from_discard(state, src_ci, count=1, eligible=_is_republic_unit)
    # Select it, then finish.
    sel = next(a for a in legal_actions(state)
               if isinstance(a, SelectDiscardCard) and a.instance_id == disc_ci.instance_id)
    state = apply(state, sel)
    if state.pending_decisions:
        fin = next((a for a in legal_actions(state)
                    if isinstance(a, FinishReturnFromDiscard)), None)
        if fin is not None:
            state = apply(state, fin)

    hand = state.player_by_id("P0").hand
    returned = next(ci for ci in hand if ci.instance_id == disc_ci.instance_id)
    assert returned.exhausted is False
    assert returned.damage == 0

    ctx = CheckContext.from_state(state)
    check(state, ctx)
