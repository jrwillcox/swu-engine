"""TWI (Twilight of the Republic) card ability tests — deck ``ahsoka-tano``.

Group ``ahsoka-tano:01`` — the **Coordinate** keyword.  Coordinate ("Gain this
ability/keyword while you control 3 or more units") is modelled as the
``Condition.CONTROLLER_N_PLUS_UNITS`` atom gating each card's specific clause.
A synthetic framework test exercises the condition itself; per-card tests assert
each clause toggles on/off with the controller's unit count through the public
engine interfaces (compute_power / compute_hp / has_keyword / keyword_value /
legal_actions / trigger firing).

Reuses the DB-backed game-state helpers from the SOR card tests.  Method names
embed the card number so the encoding verifier's ``-k`` gate selects them.
"""
from __future__ import annotations

import uuid


from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _place_leader, _fire_on_attack,
    _fire_when_defeated, _fire_when_played, _fire_upgrade_played, _defeat_and_fire,
    _find_instance, _give_resources, _play_event_from_hand,
)
from tests.test_shd_cards import (
    _attach_upgrade_directly, _fire_card_played, _place_deployed_leader,
    _put_in_hand, _fire_when_deployed,
)


def _filler(state, owner_id, repo, arena="ground"):
    """Place a plain SOR unit (no Coordinate / no constant self-buff) as board
    filler so the controller's unit count can be raised without confounds."""
    return _place(state, owner_id, _get_card(repo, "SOR", "128"), arena)  # 3/1


def _add_deck_cards(state, owner_id, repo, n):
    """Put ``n`` cards on top of a player's deck so a draw resolves."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    for _ in range(n):
        ci = CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:5]}",
            card_def=_get_card(repo, "SOR", "128"), owner_id=owner_id,
            zone=Zone.DECK,
        )
        ps.deck.append(ci)


# ── Synthetic framework test: the Coordinate condition ────────────────────────

class TestCoordinateKeyword:
    """The keystone of Coordinate is ``Condition.CONTROLLER_N_PLUS_UNITS`` — "you
    control 3 or more units", the source counting itself."""

    def test_coordinate_condition_counts_units_including_self(self, repo):
        from swu.abilities.registry import ConditionCheck, Condition
        cond = ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3)
        state = _make_state()
        a = _filler(state, "P0", repo)
        assert cond.evaluate(state, a) is False              # 1 unit
        _filler(state, "P0", repo)
        assert cond.evaluate(state, a) is False              # 2 units
        _filler(state, "P0", repo, arena="space")
        assert cond.evaluate(state, a) is True               # 3 units (both arenas)

    def test_coordinate_condition_ignores_enemy_and_undeployed_leaders(self, repo):
        from swu.abilities.registry import ConditionCheck, Condition
        cond = ConditionCheck(Condition.CONTROLLER_N_PLUS_UNITS, 3)
        state = _make_state()
        src = _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        # Enemy units don't count toward P0's total.
        _filler(state, "P1", repo)
        _filler(state, "P1", repo)
        # An undeployed leader sits in base_zone and is not a unit in an arena.
        _place_leader(state, "P0", _get_card(repo, "TWI", "11"))
        assert cond.evaluate(state, src) is False            # still only 2 P0 units

    def test_coordinate_stat_buff_toggles_with_board_twi_90(self, repo):
        """Echo's "Coordinate — This unit gets +2/+2" winks on/off as the third
        unit enters/leaves (exercised through the public compute_power layer)."""
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        echo = _place(state, "P0", _get_card(repo, "TWI", "90"), "ground")
        assert compute_power(state, echo) == 2 and compute_hp(state, echo) == 2
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)            # now 3 units → Coordinate active
        assert compute_power(state, echo) == 4 and compute_hp(state, echo) == 4


# ── TWI_11 Ahsoka Tano (Leader) ───────────────────────────────────────────────

class TestAhsokaTano:
    def test_twi_11_deployed_constant_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "TWI", "11"), "ground")
        ahsoka.deployed = True
        # Ahsoka + 1 filler = 2 units → no buff (printed 3 power).
        _filler(state, "P0", repo)
        assert compute_power(state, ahsoka) == 3
        # Third unit → Coordinate active → +2/+0.
        _filler(state, "P0", repo)
        assert compute_power(state, ahsoka) == 5

    def test_twi_11_undeployed_coordinate_attack_gated(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        ahsoka = _place_leader(state, "P0", _get_card(repo, "TWI", "11"))
        # Two units: condition false → the Coordinate action is not offered.
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert not any(isinstance(a, UseAbility) and a.source_id == ahsoka.instance_id
                       for a in legal_actions(state))
        # Third unit: condition true → the action is offered.
        _filler(state, "P0", repo)
        use = next((a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == ahsoka.instance_id), None)
        assert use is not None
        # Using it exhausts Ahsoka and pushes a granted_attack decision.
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "granted_attack"


# ── TWI_106 Coruscant Guard (Coordinate — Ambush) ─────────────────────────────

class TestCoruscantGuard:
    def test_twi_106_ambush_toggles_with_unit_count(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "TWI", "106"), "ground")
        # Printed Ambush is sanitised away; with <3 units the conditional grant is off.
        assert has_keyword(state, guard, Keyword.AMBUSH) is False
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)            # 3 units incl. the guard → Ambush on
        assert has_keyword(state, guard, Keyword.AMBUSH) is True


# ── TWI_114 Clone Commander Cody ──────────────────────────────────────────────

class TestCloneCommanderCody:
    def test_twi_114_buffs_other_units_not_self(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        cody = _place(state, "P0", _get_card(repo, "TWI", "114"), "ground")
        ally = _filler(state, "P0", repo)     # 3/1
        # Only 2 units → Coordinate inactive: ally unbuffed, no granted Overwhelm.
        assert compute_power(state, ally) == 3 and compute_hp(state, ally) == 1
        assert has_keyword(state, ally, Keyword.OVERWHELM) is False
        # Third unit → Coordinate active.
        _filler(state, "P0", repo)
        assert compute_power(state, ally) == 4 and compute_hp(state, ally) == 2
        assert has_keyword(state, ally, Keyword.OVERWHELM) is True
        # Cody does not buff himself ("each OTHER friendly unit"); printed 4 power.
        assert compute_power(state, cody) == 4

    def test_twi_114_keeps_own_printed_overwhelm(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        cody = _place(state, "P0", _get_card(repo, "TWI", "114"), "ground")
        assert has_keyword(state, cody, Keyword.OVERWHELM) is True  # his own keyword bar


# ── TWI_147 Anakin Skywalker (Coordinate — On Attack: Draw a card) ────────────

class TestAnakinSkywalker:
    def test_twi_147_draws_only_while_coordinating(self, repo):
        state = _make_state()
        anakin = _place(state, "P0", _get_card(repo, "TWI", "147"), "ground")
        _add_deck_cards(state, "P0", repo, 3)
        ps = state.player_by_id("P0")

        # Two units → trigger not collected → no draw.
        _filler(state, "P0", repo)
        before = len(ps.hand)
        state = _fire_on_attack(state, _find_instance(state, anakin.instance_id))
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == before

        # Third unit → On Attack draw fires.
        _filler(state, "P0", repo)
        before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, _find_instance(state, anakin.instance_id))
        assert len(state.player_by_id("P0").hand) == before + 1


# ── TWI_158 / TWI_240 simple Coordinate stat buffs ────────────────────────────

class TestCloneHeavyGunner:
    def test_twi_158_plus_2_0_with_coordinate(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        gunner = _place(state, "P0", _get_card(repo, "TWI", "158"), "ground")  # 1/3
        assert compute_power(state, gunner) == 1
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert compute_power(state, gunner) == 3 and compute_hp(state, gunner) == 3


class Test332ndStalwart:
    def test_twi_240_plus_1_1_with_coordinate(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        stalwart = _place(state, "P0", _get_card(repo, "TWI", "240"), "ground")  # 1/2
        assert compute_power(state, stalwart) == 1 and compute_hp(state, stalwart) == 2
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert compute_power(state, stalwart) == 2 and compute_hp(state, stalwart) == 3


# ── TWI_164 Hevy (Coordinate — Raid 2 + When Defeated) ────────────────────────

class TestHevy:
    def test_twi_164_raid_2_toggles_with_coordinate(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        from swu.engine.actions import compute_power
        state = _make_state()
        hevy = _place(state, "P0", _get_card(repo, "TWI", "164"), "ground")  # 4/4
        assert keyword_value(state, hevy, Keyword.RAID) == 0
        assert compute_power(state, hevy, is_attacking=True) == 4
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)            # 3 units → Raid 2 active
        assert keyword_value(state, hevy, Keyword.RAID) == 2
        assert compute_power(state, hevy, is_attacking=True) == 6

    def test_twi_164_when_defeated_damages_each_enemy_ground_unit(self, repo):
        state = _make_state()
        hevy = _place(state, "P0", _get_card(repo, "TWI", "164"), "ground")
        e1 = _filler(state, "P1", repo)                       # enemy ground 3/1
        e2 = _place(state, "P1", _get_card(repo, "TWI", "90"), "ground")  # Echo 2/2
        space = _filler(state, "P1", repo, arena="space")     # enemy SPACE — unaffected
        state = _fire_when_defeated(state, hevy)
        # e1 (1 hp) defeated by the 1 damage; e2 takes 1 (survives, 2 hp).
        assert _find_instance(state, e1.instance_id) is None
        e2_live = _find_instance(state, e2.instance_id)
        assert e2_live is not None and e2_live.damage == 1
        assert _find_instance(state, space.instance_id).damage == 0


# ── TWI_243 Republic Commando (Coordinate — Saboteur) ─────────────────────────

class TestRepublicCommando:
    def test_twi_243_saboteur_toggles_with_unit_count(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        commando = _place(state, "P0", _get_card(repo, "TWI", "243"), "ground")
        assert has_keyword(state, commando, Keyword.SABOTEUR) is False
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert has_keyword(state, commando, Keyword.SABOTEUR) is True


# ── Group ahsoka-tano:02 — direct damage events ───────────────────────────────

class TestGrenadeStrike:
    """TWI_171 — "Deal 2 damage to a unit. You may deal 1 damage to another unit
    in the same arena." """

    def test_twi_171_two_then_one_to_another_same_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # enemy 3/7
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # ally 3/7
        space = _place(state, "P1", _get_card(repo, "SOR", "128"), "space")  # other arena
        state, _evt = _play_event_from_hand(state, repo, "TWI", "171")
        # First effect: deal 2 to a unit (choose the enemy ground unit).
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == a.instance_id))
        assert _find_instance(state, a.instance_id).damage == 2
        # Second effect: "another unit in the same arena" — b is offered, the first
        # target (a) is excluded ("another"), and the space unit is a different arena.
        offered = {x.target_id for x in legal_actions(state) if isinstance(x, ChooseTarget)}
        assert b.instance_id in offered
        assert a.instance_id not in offered
        assert space.instance_id not in offered
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == b.instance_id))
        assert _find_instance(state, b.instance_id).damage == 1
        assert not state.pending_decisions

    def test_twi_171_second_damage_is_optional(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, DeclineTarget
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "171")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == a.instance_id))
        # "You may" — a decline is offered; declining leaves the other unit undamaged.
        assert any(isinstance(x, DeclineTarget) for x in legal_actions(state))
        state = apply(state, next(x for x in legal_actions(state) if isinstance(x, DeclineTarget)))
        assert not state.pending_decisions
        assert _find_instance(state, b.instance_id).damage == 0


class TestOpenFire:
    """TWI_174 — "Deal 4 damage to a unit." """

    def test_twi_174_deals_4_to_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "TWI", "174")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4
        assert not state.pending_decisions


# ── Group ahsoka-tano:03 — card advantage & disruption ────────────────────────

def _put_in_discard(state, owner_id, card_def):
    """Put a card def into a player's discard pile.  Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_dis_{uuid.uuid4().hex[:5]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD,
    )
    state.player_by_id(owner_id).discard.append(ci)
    return ci


def _put_in_hand(state, owner_id, card_def):
    """Put a card def into a player's hand.  Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{uuid.uuid4().hex[:5]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _ready_resources(state, owner_id):
    return sum(1 for r in state.player_by_id(owner_id).resources if not r.exhausted)


class TestPatrollingVWing:
    """TWI_107 — "When Played: Draw a card." """

    def test_twi_107_when_played_draws_a_card(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 3)
        before = len(state.player_by_id("P0").hand)
        vwing = _place(state, "P0", _get_card(repo, "TWI", "107"), "space")
        state = _fire_when_played(state, vwing)
        assert len(state.player_by_id("P0").hand) == before + 1
        assert not state.pending_decisions


class TestTranquility:
    """TWI_246 — When Played: may return a Republic unit from discard to hand.
    On Attack: each of the next 3 Republic cards you play this phase costs 1 less."""

    def test_twi_246_when_played_returns_republic_unit_from_discard(self, repo):
        from swu.engine.actions import (legal_actions, apply, SelectDiscardCard,
                                        FinishReturnFromDiscard)
        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        rep = _put_in_discard(state, "P0", _get_card(repo, "TWI", "240"))   # Republic unit
        non_rep = _put_in_discard(state, "P0", _get_card(repo, "TWI", "107"))  # Vehicle/Fighter
        non_unit = _put_in_discard(state, "P0", _get_card(repo, "TWI", "171"))  # event

        state = _fire_when_played(state, tq)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        acts = legal_actions(state)
        sels = [a for a in acts if isinstance(a, SelectDiscardCard)]
        # Only the Republic *unit* is eligible (not the non-Republic unit / event).
        assert [a.instance_id for a in sels] == [rep.instance_id]
        assert any(isinstance(a, FinishReturnFromDiscard) for a in acts)
        state = apply(state, sels[0])
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == rep.instance_id for ci in ps.hand)
        assert all(ci.instance_id != rep.instance_id for ci in ps.discard)

    def test_twi_246_when_played_may_decline(self, repo):
        from swu.engine.actions import apply, FinishReturnFromDiscard
        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        rep = _put_in_discard(state, "P0", _get_card(repo, "TWI", "240"))
        state = _fire_when_played(state, tq)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        state = apply(state, FinishReturnFromDiscard())
        # Declined: the unit stays in the discard pile.
        assert any(ci.instance_id == rep.instance_id
                   for ci in state.player_by_id("P0").discard)

    def test_twi_246_when_played_no_republic_unit_no_decision(self, repo):
        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        _put_in_discard(state, "P0", _get_card(repo, "TWI", "107"))   # non-Republic unit
        state = _fire_when_played(state, tq)
        assert not state.pending_decisions

    def _play_and_count(self, state, repo, set_code, num, owner="P0"):
        """Play a card from hand via PlayCard, returning (state, resources_spent).
        Penalty-agnostic — measures the actual ready-resource delta.  Forces ``owner``
        to be the active player so consecutive plays in one test stay legal (PlayCard
        normally hands the turn over)."""
        from swu.engine.actions import apply, PlayCard
        state.active_player_index = state.player_index(owner)
        state.passed_players = [p for p in state.passed_players
                                if p != state.active_player_index]
        ci = _put_in_hand(state, owner, _get_card(repo, set_code, num))
        before = _ready_resources(state, owner)
        state = apply(state, PlayCard(ci.instance_id))
        return state, before - _ready_resources(state, owner)

    def test_twi_246_on_attack_discounts_next_three_republic_units(self, repo):
        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        _give_resources(state, "P0", 30)
        _add_deck_cards(state, "P0", repo, 8)   # Echo plays are fine; padding for safety
        # On Attack: records 3 pending "Republic card costs 1 less" discounts.
        state = _fire_on_attack(state, tq)
        assert not state.pending_decisions
        assert len(state.game_memory.pending_play_discounts) == 3

        # Echo (TWI_90) is a Republic unit; the aspect penalty is constant per card,
        # so measure the discount as the delta between discounted and full plays.
        spent = []
        for _ in range(4):
            state, n = self._play_and_count(state, repo, "TWI", "90")
            spent.append(n)
            # Echo is a unique unit; we only measure play cost here, so clear it
            # from the arena before the next play rather than resolve the Unique
            # Rule duplicate that a second copy would create.
            state.player_by_id("P0").ground_arena.clear()
        # First three each cost 1 less than the fourth (no discount left).
        assert spent[0] == spent[1] == spent[2] == spent[3] - 1
        assert not state.game_memory.pending_play_discounts

    def test_twi_246_discount_applies_to_non_unit_republic_cards(self, repo):
        """units_only=False — the discount applies to a Republic *event*, not just
        units (Tranquility says "Republic cards")."""
        # Baseline: full cost of the event with no discount active.
        base = _make_state()
        _give_resources(base, "P0", 30)
        base, full = self._play_and_count(base, repo, "TWI", "129")  # In Defense of Kamino

        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        _give_resources(state, "P0", 30)
        state = _fire_on_attack(state, tq)
        state, discounted = self._play_and_count(state, repo, "TWI", "129")
        assert discounted == full - 1
        assert len(state.game_memory.pending_play_discounts) == 2

    def test_twi_246_discount_not_applied_to_non_republic_card(self, repo):
        # Baseline: full cost of Patrolling V-Wing (Vehicle/Fighter, no Republic).
        base = _make_state()
        _give_resources(base, "P0", 30)
        _add_deck_cards(base, "P0", repo, 4)   # its When Played draws
        base, full = self._play_and_count(base, repo, "TWI", "107")

        state = _make_state()
        tq = _place(state, "P0", _get_card(repo, "TWI", "246"), "space")
        _give_resources(state, "P0", 30)
        _add_deck_cards(state, "P0", repo, 4)
        state = _fire_on_attack(state, tq)
        state, with_discounts = self._play_and_count(state, repo, "TWI", "107")
        assert with_discounts == full                      # no discount on a non-Republic card
        assert len(state.game_memory.pending_play_discounts) == 3   # entries untouched


# ── Group ahsoka-tano:04 — combat tricks, buffs & tempo ───────────────────────


class TestRepublicTacticalOfficer:
    """TWI_91 — "When Played: You may attack with a Republic unit. It gets +2/+0
    for this attack." """

    def test_twi_91_grants_attack_restricted_to_republic(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        rto = _place(state, "P0", _get_card(repo, "TWI", "91"), "ground")
        rep = _place(state, "P0", _get_card(repo, "TWI", "240"), "ground")  # Republic
        non_rep = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # not Republic
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy to attack
        state = _fire_when_played(state, rto)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        # The Republic ally may attack; the non-Republic unit may not.
        assert rep.instance_id in attackers
        assert non_rep.instance_id not in attackers

    def test_twi_91_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        state = _make_state()
        rto = _place(state, "P0", _get_card(repo, "TWI", "91"), "ground")
        state = _fire_when_played(state, rto)
        # No other ready Republic unit → only a decline is offered ("you may").
        assert any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))
        state = apply(state, DeclineGrantedAttack())
        assert not state.pending_decisions


class TestAdmiralYularen:
    """TWI_92 — Restore 1 + "Each other friendly Heroism unit gets +0/+1." """

    def test_twi_92_buffs_other_heroism_units_hp(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        yularen = _place(state, "P0", _get_card(repo, "TWI", "92"), "ground")
        heroism = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7 Heroism
        non_hero = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Villainy/Aggr
        enemy_hero = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy Heroism
        assert compute_hp(state, heroism) == 8        # 7 + 1
        assert compute_hp(state, non_hero) == 1       # not Heroism → unbuffed
        assert compute_hp(state, enemy_hero) == 7     # enemy → unbuffed
        # Yularen does not buff himself ("each OTHER friendly Heroism unit").
        assert compute_hp(state, yularen) == 5


class Test501stLiberator:
    """TWI_109 — "When Played: If you control another Republic unit, you may heal 3
    damage from a base." """

    def test_twi_109_heals_own_base_when_controls_republic(self, repo):
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 10
        lib = _place(state, "P0", _get_card(repo, "TWI", "109"), "ground")
        _place(state, "P0", _get_card(repo, "TWI", "240"), "ground")  # another Republic
        state = _fire_when_played(state, lib)
        # Optional trigger offered; accept it, then auto-resolve the fixed heal.
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        AutoResolveEffects)
        acc = next((a for a in legal_actions(state) if isinstance(a, AcceptTrigger)), None)
        assert acc is not None
        state = apply(state, acc)
        while state.pending_decisions:
            state = apply(state, AutoResolveEffects())
        assert state.player_by_id("P0").base_instance.damage == 7  # healed 3

    def test_twi_109_no_trigger_without_another_republic(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 10
        lib = _place(state, "P0", _get_card(repo, "TWI", "109"), "ground")
        # The Liberator is the only Republic unit → condition false → no trigger.
        state = _fire_when_played(state, lib)
        assert not state.pending_decisions
        assert state.player_by_id("P0").base_instance.damage == 10


class TestOutflankTWI:
    """TWI_123 — "Attack with 2 units (one at a time)." """

    def test_twi_123_grants_two_sequential_attacks(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        u1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "123")
        assert state.pending_decisions[-1].kind == "granted_attack"
        # First attack: u1 hits the enemy base (or unit). Attack with u1.
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit) and a.attacker_id == u1.instance_id)
        state = apply(state, atk)
        # Resolve any follow-up to settle, then the SECOND granted attack remains.
        # The first attacker is now exhausted; only u2 is offered.
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert u2.instance_id in attackers
        assert u1.instance_id not in attackers


class TestEncouragingLeadership:
    """TWI_126 — "Give each friendly unit +1/+1 for this phase." """

    def test_twi_126_buffs_each_friendly_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        b = _place(state, "P0", _get_card(repo, "SOR", "128"), "space")   # 3/1
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "126")
        assert not state.pending_decisions
        assert compute_power(state, _find_instance(state, a.instance_id)) == 4
        assert compute_hp(state, _find_instance(state, a.instance_id)) == 8
        assert compute_power(state, _find_instance(state, b.instance_id)) == 4
        assert compute_hp(state, _find_instance(state, b.instance_id)) == 2
        # Enemy units are not buffed.
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 3


class TestAnakinsInterceptor:
    """TWI_142 — "While your base has 15 or more damage on it, this unit gets
    +2/+0." """

    def test_twi_142_buff_toggles_with_base_damage(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        interceptor = _place(state, "P0", _get_card(repo, "TWI", "142"), "space")  # 2/3
        base = state.player_by_id("P0").base_instance
        base.damage = 14
        assert compute_power(state, interceptor) == 2     # below threshold
        base.damage = 15
        assert compute_power(state, interceptor) == 4     # +2/+0 active

    def test_twi_142_keys_off_own_base_not_enemy(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        interceptor = _place(state, "P0", _get_card(repo, "TWI", "142"), "space")
        # Enemy base damage must not activate the buff.
        state.player_by_id("P1").base_instance.damage = 20
        assert compute_power(state, interceptor) == 2


class TestAhsokasPadawanLightsaber:
    """TWI_248 — "When Played: If attached unit is Ahsoka Tano, you may attack with
    a unit." """

    def test_twi_248_grants_attack_when_host_is_ahsoka(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "TWI", "11"), "ground")  # "Ahsoka Tano"
        ahsoka.deployed = True
        ally = _place(state, "P0", _get_card(repo, "TWI", "240"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy
        up = _attach_upgrade_directly(state, ahsoka, _get_card(repo, "TWI", "248"), "P0")
        state = _fire_upgrade_played(state, up, ahsoka)
        assert state.pending_decisions[-1].kind == "granted_attack"
        # Any of the controller's ready units may attack (not pinned to the host).
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert ally.instance_id in attackers
        assert any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))

    def test_twi_248_no_trigger_when_host_not_ahsoka(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Ahsoka
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "248"), "P0")
        state = _fire_upgrade_played(state, up, host)
        assert not state.pending_decisions


# ── Group ahsoka-tano:05 — create-token-unit primitive ────────────────────────

def _clone_troopers(state, owner_id="P0"):
    """Return the owner's in-play Clone Trooper token-unit instances."""
    from swu.cards.models import TokenUnit
    ps = state.player_by_id(owner_id)
    return [ci for ci in ps.ground_arena + ps.space_arena
            if isinstance(ci.card_def, TokenUnit) and ci.card_def.name == "Clone Trooper"]


class TestCreateTokenUnitPrimitive:
    """Synthetic coverage of the create-token-unit seam itself, independent of any
    specific card."""

    def test_creates_token_unit_in_ground_arena_exhausted(self, repo):
        from swu.engine.actions import _create_token_units
        state = _make_state()
        ps = state.player_by_id("P0")
        before = len(ps.ground_arena)
        created = _create_token_units(state, ps, "Clone Trooper", 2)
        assert len(created) == 2
        toks = _clone_troopers(state)
        assert len(toks) == 2 and len(ps.ground_arena) == before + 2
        # A 0-cost 2/2 ground token, entering play exhausted like any unit.
        for t in toks:
            assert t.card_def.power == 2 and t.card_def.hp == 2
            assert t.exhausted is True
            assert t.zone.name == "GROUND_ARENA"

    def test_token_excluded_from_card_conservation(self, repo):
        """A created token is not a real deck card — it must not break conservation."""
        from swu.engine.actions import _create_token_units
        from swu.engine.invariants import CheckContext, check
        state = _make_state()
        ctx = CheckContext.from_state(state)
        ps = state.player_by_id("P0")
        _create_token_units(state, ps, "Clone Trooper", 2)
        check(state, ctx)   # raises on a conservation/zone/token violation

    def test_token_ceases_to_exist_when_defeated(self, repo):
        from swu.engine.actions import _create_token_units, _defeat_unit
        state = _make_state()
        ps = state.player_by_id("P0")
        tok = _create_token_units(state, ps, "Clone Trooper", 1)[0]
        _defeat_unit(state, ps, tok)
        # Gone from the arena AND never placed into the discard pile.
        assert not _clone_troopers(state)
        from swu.cards.models import TokenUnit
        assert not any(isinstance(c.card_def, TokenUnit) for c in ps.discard)


class TestShaakTi:
    """TWI_94 — "Each friendly token unit gets +1/+0.  On Attack: Create a Clone
    Trooper token." """

    def test_twi_94_buffs_friendly_token_units(self, repo):
        from swu.engine.actions import compute_power, compute_hp, _create_token_units
        state = _make_state()
        shaak = _place(state, "P0", _get_card(repo, "TWI", "94"), "ground")  # 3/4
        ps = state.player_by_id("P0")
        tok = _create_token_units(state, ps, "Clone Trooper", 1)[0]
        # 2/2 base +1/+0 from Shaak Ti's constant → 3/2.
        assert compute_power(state, tok) == 3 and compute_hp(state, tok) == 2
        # The buff winks off when Shaak Ti leaves play.
        ps.ground_arena.remove(shaak)
        assert compute_power(state, tok) == 2

    def test_twi_94_does_not_buff_non_token_or_enemy(self, repo):
        from swu.engine.actions import compute_power, _create_token_units
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "94"), "ground")
        ally = _filler(state, "P0", repo)                 # non-token friendly 3/1
        enemy_tok = _create_token_units(state, state.player_by_id("P1"),
                                        "Clone Trooper", 1)[0]
        assert compute_power(state, ally) == 3            # unaffected (not a token)
        assert compute_power(state, enemy_tok) == 2       # unaffected (enemy)

    def test_twi_94_on_attack_creates_token(self, repo):
        state = _make_state()
        shaak = _place(state, "P0", _get_card(repo, "TWI", "94"), "ground")
        assert not _clone_troopers(state)
        state = _fire_on_attack(state, shaak)
        assert len(_clone_troopers(state)) == 1


class TestCaptainRex:
    """TWI_97 — "When Played: Create 2 Clone Trooper tokens." """

    def test_twi_97_creates_two_tokens(self, repo):
        state = _make_state()
        rex = _place(state, "P0", _get_card(repo, "TWI", "97"), "ground")
        state = _fire_when_played(state, rex)
        assert not state.pending_decisions
        assert len(_clone_troopers(state)) == 2


class TestBatchBrothers:
    """TWI_144 — "When Played: Create a Clone Trooper token." """

    def test_twi_144_creates_one_token(self, repo):
        state = _make_state()
        bb = _place(state, "P0", _get_card(repo, "TWI", "144"), "ground")
        state = _fire_when_played(state, bb)
        assert len(_clone_troopers(state)) == 1


class TestDropIn:
    """TWI_251 — Event: "Create 2 Clone Trooper tokens." """

    def test_twi_251_event_creates_two_tokens(self, repo):
        state, _ = _play_event_from_hand(state := _make_state(), repo, "TWI", "251")
        assert len(_clone_troopers(state)) == 2


# ── Group ahsoka-tano:06 — scaling-magnitude (Synchronized Strike) ────────────

class TestSynchronizedStrike:
    """TWI_99 — Event: "Deal damage to an enemy unit equal to the number of units
    you control in its arena."

    The new ``DealDamageEqualTo`` count ``source_controller_units_in_target_arena``
    reads the controller's own arena list matching the chosen unit's arena."""

    def test_twi_99_damage_equals_controllers_units_in_targets_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        # P0 (the controller) has 3 ground units …
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        # … and 1 space unit, which must NOT count toward a ground-target's damage.
        _filler(state, "P0", repo, arena="space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "TWI", "99")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert not state.pending_decisions

    def test_twi_99_magnitude_is_per_target_arena(self, repo):
        """An enemy unit in the SPACE arena takes damage equal to the controller's
        SPACE units only (here 2), not its 3 ground units."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        for _ in range(3):
            _filler(state, "P0", repo)                 # 3 ground
        _filler(state, "P0", repo, arena="space")
        _filler(state, "P0", repo, arena="space")      # 2 space
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # 3/7 space
        state, _evt = _play_event_from_hand(state, repo, "TWI", "99")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_twi_99_zero_units_in_arena_is_a_noop(self, repo):
        """Controller has units only in the OTHER arena → magnitude 0, no damage."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _filler(state, "P0", repo, arena="space")      # P0 has only space units
        _filler(state, "P0", repo, arena="space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # ground
        state, _evt = _play_event_from_hand(state, repo, "TWI", "99")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert not state.pending_decisions

    def test_twi_99_targets_only_enemy_units(self, repo):
        """The target is an enemy unit; a friendly unit is never offered."""
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        friendly = _filler(state, "P0", repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "99")
        offered = {x.target_id for x in legal_actions(state) if isinstance(x, ChooseTarget)}
        assert enemy.instance_id in offered
        assert friendly.instance_id not in offered


# ── Group general-grievous:01 — direct damage & removal ───────────────────────

class TestMercilessContest:
    """TWI_238 — Event: "Each player chooses a non-leader unit they control.
    Defeat those units."  A new ``each_player_defeats`` decision: the controller
    chooses one of their own non-leader units first, then the opponent chooses one
    of theirs (a per-stage deciding-player shift), then both are defeated."""

    def _arena_ids(self, state, pid):
        ps = state.player_by_id(pid)
        return {u.instance_id for u in ps.ground_arena + ps.space_arena}

    def test_twi_238_each_player_defeats_own_chosen_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseUnitToDefeat
        state = _make_state()
        p0a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        p0b = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        p1a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        p1b = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "238")
        # The controller (P0) chooses first, among ONLY P0's units.
        top = state.pending_decisions[-1]
        assert top.kind == "each_player_defeats"
        assert top.deciding_player_id == "P0"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseUnitToDefeat)}
        assert offered == {p0a.instance_id, p0b.instance_id}
        state = apply(state, ChooseUnitToDefeat(p0a.instance_id))
        # Now the opponent (P1) chooses, among ONLY P1's units.
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P1"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseUnitToDefeat)}
        assert offered == {p1a.instance_id, p1b.instance_id}
        state = apply(state, ChooseUnitToDefeat(p1b.instance_id))
        # Both chosen units are defeated; the unchosen ones survive.
        assert not state.pending_decisions
        assert p0a.instance_id not in self._arena_ids(state, "P0")
        assert p0b.instance_id in self._arena_ids(state, "P0")
        assert p1b.instance_id not in self._arena_ids(state, "P1")
        assert p1a.instance_id in self._arena_ids(state, "P1")

    def test_twi_238_excludes_deployed_leaders(self, repo):
        from swu.engine.actions import legal_actions, ChooseUnitToDefeat
        state = _make_state()
        leader = _place(state, "P0", _get_card(repo, "TWI", "11"), "ground")  # Ahsoka (Leader)
        leader.deployed = True
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # opponent unit
        state, _evt = _play_event_from_hand(state, repo, "TWI", "238")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseUnitToDefeat)}
        assert offered == {unit.instance_id}  # the deployed leader is not a "non-leader unit"

    def test_twi_238_skips_player_with_no_eligible_unit(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        p0a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        # P1 controls no non-leader unit, so its stage is skipped.
        state, _evt = _play_event_from_hand(state, repo, "TWI", "238")
        state = apply(state, ChooseUnitToDefeat(p0a.instance_id))
        assert not state.pending_decisions
        assert p0a.instance_id not in self._arena_ids(state, "P0")

    def test_twi_238_opponent_only_when_controller_has_none(self, repo):
        """Controller has no eligible unit → the decision goes straight to the
        opponent, who must defeat one of their own."""
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        p1a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "238")
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P1"
        state = apply(state, ChooseUnitToDefeat(p1a.instance_id))
        assert not state.pending_decisions
        assert p1a.instance_id not in self._arena_ids(state, "P1")

    def test_twi_238_fizzles_with_no_units(self, repo):
        """Neither player controls a non-leader unit → no decision, the event just
        resolves to discard."""
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "TWI", "238")
        assert not state.pending_decisions


# ── Group general-grievous:02 — card advantage & disruption ───────────────────


class TestAdmiralTrench:
    """TWI_86 — Unit (Exploit 1): "When Played: Return up to 3 units that were
    defeated this phase from your discard pile to your hand."  A WhenPlayed adapter
    onto the return_from_discard decision restricted (instance-level) to units in
    ``units_defeated_this_round``."""

    def _mark_defeated(self, state, *cis):
        for ci in cis:
            state.game_memory.units_defeated_this_round.add(ci.instance_id)

    def test_twi_86_offers_only_units_defeated_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        trench = _place(state, "P0", _get_card(repo, "TWI", "86"), "ground")
        # In P0's discard: a unit defeated this phase (eligible), a unit NOT
        # defeated this phase (ineligible), and an event "defeated this phase"
        # (ineligible — not a unit).
        defeated_unit = _put_in_discard(state, "P0", _get_card(repo, "TWI", "240"))
        old_unit = _put_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        an_event = _put_in_discard(state, "P0", _get_card(repo, "TWI", "171"))
        self._mark_defeated(state, defeated_unit, an_event)

        state = _fire_when_played(state, trench)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        sels = [a.instance_id for a in legal_actions(state)
                if isinstance(a, SelectDiscardCard)]
        assert sels == [defeated_unit.instance_id]
        _ = old_unit  # untouched
        from swu.engine.actions import FinishReturnFromDiscard
        state = apply(state, SelectDiscardCard(defeated_unit.instance_id))
        # Only one eligible (cap is 3) — finish to close the "up to" decision.
        state = apply(state, FinishReturnFromDiscard())
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == defeated_unit.instance_id for ci in ps.hand)

    def test_twi_86_returns_up_to_three(self, repo):
        from swu.engine.actions import apply, SelectDiscardCard
        state = _make_state()
        trench = _place(state, "P0", _get_card(repo, "TWI", "86"), "ground")
        units = [_put_in_discard(state, "P0", _get_card(repo, "TWI", "240"))
                 for _ in range(4)]
        self._mark_defeated(state, *units)
        state = _fire_when_played(state, trench)
        # Take three, one at a time; the engine auto-finishes at the cap of 3.
        for u in units[:3]:
            state = apply(state, SelectDiscardCard(u.instance_id))
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        in_hand = {ci.instance_id for ci in ps.hand}
        assert {u.instance_id for u in units[:3]} <= in_hand
        assert units[3].instance_id not in in_hand   # the 4th stays in discard

    def test_twi_86_no_eligible_unit_no_decision(self, repo):
        state = _make_state()
        trench = _place(state, "P0", _get_card(repo, "TWI", "86"), "ground")
        # A unit in discard, but not defeated this phase → ineligible.
        _put_in_discard(state, "P0", _get_card(repo, "TWI", "240"))
        state = _fire_when_played(state, trench)
        assert not state.pending_decisions


class TestWaylay:
    """TWI_226 — Event: "Return a non-leader unit to its owner's hand." """

    def test_twi_226_returns_a_non_leader_unit_to_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "226")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id) is None  # left the arena
        assert any(ci.instance_id == enemy.instance_id
                   for ci in state.player_by_id("P1").hand)

    def test_twi_226_excludes_deployed_leaders(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        leader = _place(state, "P1", _get_card(repo, "TWI", "11"), "ground")
        leader.deployed = True
        unit = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "226")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {unit.instance_id}  # the deployed leader is excluded


class TestPrivateManufacturing:
    """TWI_257 — Event: "Draw 2 cards. If you control no token units, put 2 cards
    from your hand on the bottom of your deck in any order." """

    def test_twi_257_draws_two_then_bottoms_two_with_no_token_units(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectHandCardToBottom
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        keep = [_put_in_hand(state, "P0", _get_card(repo, "SOR", "128")) for _ in range(2)]
        deck_before = len(state.player_by_id("P0").deck)
        hand_before = len(state.player_by_id("P0").hand)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "257")
        # Drew 2 → deck -2, hand +2; then the bottom_from_hand decision is pushed.
        ps = state.player_by_id("P0")
        assert len(ps.hand) == hand_before + 2
        assert state.pending_decisions[-1].kind == "bottom_from_hand"
        assert state.pending_decisions[-1].context["count"] == 2
        # Bottom two chosen hand cards, one at a time (pick order = bottom order).
        acts = [a for a in legal_actions(state)
                if isinstance(a, SelectHandCardToBottom)]
        first, second = acts[0].instance_id, acts[1].instance_id
        state = apply(state, SelectHandCardToBottom(first))
        assert state.pending_decisions[-1].kind == "bottom_from_hand"
        state = apply(state, SelectHandCardToBottom(second))
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        # Net hand change: +2 drawn − 2 bottomed = 0; the two bottomed cards are
        # the deck's last two, in pick order.
        assert len(ps.hand) == hand_before
        # Deck: started deck_before, −2 drawn, +2 bottomed = deck_before.
        assert len(ps.deck) == deck_before
        assert ps.deck[-2].instance_id == first
        assert ps.deck[-1].instance_id == second
        assert all(ci.instance_id not in {first, second} for ci in ps.hand)
        _ = keep

    def test_twi_257_skips_bottoming_when_controlling_a_token_unit(self, repo):
        from swu.engine.actions import _create_token_units
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _create_token_units(state, state.player_by_id("P0"), "Clone Trooper", 1)
        hand_before = len(state.player_by_id("P0").hand)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "257")
        # Drew 2, but the downside is skipped entirely — no decision pushed.
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == hand_before + 2


# ── Group general-grievous:03 — combat tricks, buffs & tempo ──────────────────


class TestGeneralGrievous:
    """TWI_15 — Leader (Sentinel).  Undeployed Action [Exhaust]: give a Droid unit
    Sentinel for this phase.  Deployed On Attack: may give a Droid unit +1/+0 and
    Sentinel for this phase."""

    def test_twi_15_undeployed_grants_droid_sentinel(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        grievous = _place_leader(state, "P0", _get_card(repo, "TWI", "15"))
        droid = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # Droid
        non_droid = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # not Droid
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == grievous.instance_id)
        state = apply(state, use)
        # Only the friendly Droid is a legal target for the Sentinel grant.
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert droid.instance_id in targs
        assert non_droid.instance_id not in targs
        state = apply(state, ChooseTarget(droid.instance_id))
        assert has_keyword(state, _find_instance(state, droid.instance_id), Keyword.SENTINEL)
        # Exhaust cost was paid (leader is now exhausted) and the ability fully resolved.
        assert state.find_instance(grievous.instance_id)[1].exhausted
        assert not state.pending_decisions

    def test_twi_15_deployed_on_attack_buffs_and_sentinels_droid(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        ChooseTarget, compute_power)
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "15"), "ground")
        grievous.deployed = True
        droid = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # 1/1 Droid
        state = _fire_on_attack(state, grievous)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(droid.instance_id))
        d = _find_instance(state, droid.instance_id)
        assert compute_power(state, d) == 1 + 1            # +1/+0
        assert has_keyword(state, d, Keyword.SENTINEL)
        assert not state.pending_decisions

    def test_twi_15_deployed_on_attack_auto_declines_with_no_droid(self, repo):
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "15"), "ground")
        grievous.deployed = True
        # The only other friendly unit is not a Droid → optional trigger auto-declines.
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, grievous)
        assert not state.pending_decisions


class TestMagnaGuardWingLeader:
    """TWI_82 — Unit: "Action: Attack with a Droid unit. Then, attack with another
    Droid unit. Use this ability only once each round." """

    def _use(self, state, mg):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == mg.instance_id)
        return apply(state, use)

    def test_twi_82_attacks_with_two_different_droid_units(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        mg = _place(state, "P0", _get_card(repo, "TWI", "82"), "space")
        d1 = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # Droid
        d2 = _place(state, "P0", _get_card(repo, "TWI", "180"), "ground")  # Droid
        non_droid = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # not Droid
        state = self._use(state, mg)
        assert state.pending_decisions[-1].kind == "granted_attack"
        # First grant: both Droids offered as attackers; the non-Droid and MagnaGuard
        # (a Vehicle, not a Droid) are not.
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert {d1.instance_id, d2.instance_id} <= attackers
        assert non_droid.instance_id not in attackers
        assert mg.instance_id not in attackers
        # Attack the enemy base with d1; the second grant then offers only d2
        # ("another" — d1 is now exhausted).
        state = apply(state, AttackWithUnit(d1.instance_id, None))
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers2 = {a.attacker_id for a in legal_actions(state)
                      if isinstance(a, AttackWithUnit)}
        assert attackers2 == {d2.instance_id}

    def test_twi_82_only_once_per_round(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, DeclineGrantedAttack
        state = _make_state()
        mg = _place(state, "P0", _get_card(repo, "TWI", "82"), "space")
        # No Droid units → each of the two grants offers only a decline.
        state = self._use(state, mg)
        for _ in range(2):
            assert state.pending_decisions[-1].kind == "granted_attack"
            state = apply(state, DeclineGrantedAttack())
        assert not state.pending_decisions
        # The ability is spent for the round: no UseAbility offered for MagnaGuard.
        assert not any(isinstance(a, UseAbility) and a.source_id == mg.instance_id
                       for a in legal_actions(state))
        key = f"{mg.instance_id}:0"
        assert key in state.game_memory.activated_abilities_used_this_round


class TestObedientVanguard:
    """TWI_104 — Unit (Raid 1): "When Defeated: You may give a Trooper unit +2/+2
    for this phase." """

    def test_twi_104_when_defeated_buffs_a_trooper(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        ChooseTarget, compute_power, compute_hp)
        from tests.test_law_cards import _fire_unit_defeated
        state = _make_state()
        vanguard = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")
        trooper = _place(state, "P0", _get_card(repo, "TWI", "180"), "ground")  # Trooper
        non_trooper = _place(state, "P0", _get_card(repo, "TWI", "82"), "space")  # not Trooper
        # Mirror the engine: the defeated unit leaves its arena and homes to discard.
        state = _fire_unit_defeated(state, vanguard, controller_id="P0")
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert trooper.instance_id in targs
        assert non_trooper.instance_id not in targs
        state = apply(state, ChooseTarget(trooper.instance_id))
        t = _find_instance(state, trooper.instance_id)
        assert compute_power(state, t) == 2 + 2
        assert compute_hp(state, t) == 3 + 2

    def test_twi_104_auto_declines_with_no_trooper(self, repo):
        from tests.test_law_cards import _fire_unit_defeated
        state = _make_state()
        vanguard = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")
        _place(state, "P0", _get_card(repo, "TWI", "82"), "space")  # not a Trooper
        state = _fire_unit_defeated(state, vanguard, controller_id="P0")
        assert not state.pending_decisions


class TestTacticalAdvantage:
    """TWI_124 — Event: "Give a unit +2/+2 for this phase." """

    def test_twi_124_buffs_a_unit(self, repo):
        from swu.engine.actions import (legal_actions, apply, ChooseTarget,
                                        compute_power, compute_hp)
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        state, _evt = _play_event_from_hand(state, repo, "TWI", "124")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == ally.instance_id))
        a = _find_instance(state, ally.instance_id)
        assert compute_power(state, a) == 3 + 2
        assert compute_hp(state, a) == 1 + 2
        assert not state.pending_decisions


class TestSoullessOne:
    """TWI_179 — Unit: "On Attack: You may exhaust a friendly Droid unit or General
    Grievous (leader or unit). If you do, this unit gets +2/+0 for this attack." """

    def test_twi_179_exhaust_droid_buffs_self(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        ChooseTarget, compute_power)
        state = _make_state()
        soulless = _place(state, "P0", _get_card(repo, "TWI", "179"), "space")  # 1/2
        droid = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # Droid
        non_droid = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # not Droid
        state = _fire_on_attack(state, soulless)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert droid.instance_id in targs
        assert non_droid.instance_id not in targs       # not a Droid → not offered
        state = apply(state, ChooseTarget(droid.instance_id))
        assert _find_instance(state, droid.instance_id).exhausted
        s = _find_instance(state, soulless.instance_id)
        assert compute_power(state, s, is_attacking=True) == 1 + 2
        assert not state.pending_decisions

    def test_twi_179_general_grievous_is_a_valid_target(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        soulless = _place(state, "P0", _get_card(repo, "TWI", "179"), "space")
        # The deployed General Grievous leader-unit is not a Droid, but is named
        # "General Grievous" → still a valid exhaust target.
        grievous = _place(state, "P0", _get_card(repo, "TWI", "15"), "ground")
        grievous.deployed = True
        state = _fire_on_attack(state, soulless)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert grievous.instance_id in targs

    def test_twi_179_auto_declines_with_no_eligible_unit(self, repo):
        state = _make_state()
        soulless = _place(state, "P0", _get_card(repo, "TWI", "179"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # not a Droid
        state = _fire_on_attack(state, soulless)
        assert not state.pending_decisions


class TestSeparatistCommando:
    """TWI_180 — Unit: "While you control another Separatist unit, this unit gains
    Raid 2." """

    def test_twi_180_gains_raid2_only_with_another_separatist(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        commando = _place(state, "P0", _get_card(repo, "TWI", "180"), "ground")
        # Alone: printed Raid was stripped (the ability owns it), condition false → 0.
        assert keyword_value(state, commando, Keyword.RAID) == 0
        # Another Separatist unit → Raid 2 winks on.
        other = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # Separatist
        assert keyword_value(state, commando, Keyword.RAID) == 2
        # An enemy Separatist does not count ("you control another").
        state.player_by_id("P0").ground_arena.remove(other)
        _place(state, "P1", _get_card(repo, "TWI", "104"), "ground")
        assert keyword_value(state, commando, Keyword.RAID) == 0

    def test_twi_180_raid_adds_attacking_power(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        commando = _place(state, "P0", _get_card(repo, "TWI", "180"), "ground")  # 2/3
        _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # another Separatist
        assert compute_power(state, commando, is_attacking=True) == 2 + 2
        assert compute_power(state, commando, is_attacking=False) == 2


class TestTacticalDroidCommander:
    """TWI_184 — Unit (Exploit 2): "When you play another Separatist unit: You may
    exhaust a unit that costs the same as or less than the played unit." """

    def _play_separatist_unit(self, state, repo, num, owner="P0"):
        """Play a Separatist unit from hand via PlayCard (fires CardPlayed)."""
        from swu.engine.actions import apply, PlayCard
        state.active_player_index = state.player_index(owner)
        state.passed_players = [p for p in state.passed_players
                                if p != state.active_player_index]
        ci = _put_in_hand(state, owner, _get_card(repo, "TWI", num))
        _give_resources(state, owner, 10)
        return apply(state, PlayCard(ci.instance_id)), ci

    def test_twi_184_exhaust_unit_costing_le_played(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        commander = _place(state, "P0", _get_card(repo, "TWI", "184"), "ground")
        # Targets: an enemy 1-cost unit (≤ played) and an enemy 5-cost unit (> played).
        cheap = _place(state, "P1", _get_card(repo, "TWI", "104"), "ground")   # cost 1
        pricey = _place(state, "P1", _get_card(repo, "TWI", "184"), "ground")  # cost 5
        # Play another Separatist unit costing 2 (Separatist Commando TWI_180).
        state, _played = self._play_separatist_unit(state, repo, "180")
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in targs        # cost 1 ≤ 2
        assert pricey.instance_id not in targs   # cost 5 > 2
        state = apply(state, ChooseTarget(cheap.instance_id))
        assert _find_instance(state, cheap.instance_id).exhausted
        assert not state.pending_decisions

    def test_twi_184_only_fires_on_separatist_unit_play(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "184"), "ground")
        _place(state, "P1", _get_card(repo, "TWI", "104"), "ground")  # a possible target
        # Playing a non-Separatist unit (SOR_128) does NOT fire the trigger.
        ci = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(ci.instance_id))
        assert not state.pending_decisions


# ── Group general-grievous:04 — combat tricks, buffs & tempo ──────────────────


class TestIndependentSenator:
    """TWI_206 — "Action [2 resources, Exhaust]: Exhaust a unit with 4 or less
    power." """

    def test_twi_206_exhausts_only_low_power_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "206"), "ground")
        _give_resources(state, "P0", 2)
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 3/7, power 3
        strong = _place(state, "P1", _get_card(repo, "TWI", "86"), "ground")  # 5/5, power 5
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == senator.instance_id)
        state = apply(state, use)
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert weak.instance_id in targs        # power 3 ≤ 4
        assert strong.instance_id not in targs  # power 5 > 4
        state = apply(state, ChooseTarget(weak.instance_id))
        assert _find_instance(state, weak.instance_id).exhausted
        # The [2 resources, Exhaust] cost was paid.
        assert state.find_instance(senator.instance_id)[1].exhausted
        assert state.player_by_id("P0").available_resources == 0
        assert not state.pending_decisions


class TestTriDroidSuppressor:
    """TWI_217 — Exploit 2 (keyword) + "When Played: Exhaust an enemy ground
    unit." """

    def test_twi_217_when_played_exhausts_enemy_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        sup = _place(state, "P0", _get_card(repo, "TWI", "217"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "128"), "space")
        friendly = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")
        state = _fire_when_played(state, sup)
        targs = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert ground.instance_id in targs
        assert space.instance_id not in targs     # space arena excluded
        assert friendly.instance_id not in targs  # friendly excluded
        state = apply(state, ChooseTarget(ground.instance_id))
        assert _find_instance(state, ground.instance_id).exhausted
        assert not state.pending_decisions

    def test_twi_217_no_enemy_ground_unit_fizzles(self, repo):
        state = _make_state()
        sup = _place(state, "P0", _get_card(repo, "TWI", "217"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "space")  # only a space unit
        state = _fire_when_played(state, sup)
        assert not state.pending_decisions


class TestInPursuit:
    """TWI_221 — "Exhaust a friendly unit. If you do, exhaust an enemy unit." """

    def test_twi_221_exhausts_friendly_then_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "221")
        # First effect: exhaust a friendly unit (only friendly offered).
        targs1 = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert friendly.instance_id in targs1
        assert enemy.instance_id not in targs1
        state = apply(state, ChooseTarget(friendly.instance_id))
        assert _find_instance(state, friendly.instance_id).exhausted
        # Second effect ("If you do"): exhaust an enemy unit (only enemy offered).
        targs2 = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy.instance_id in targs2
        assert friendly.instance_id not in targs2
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted
        assert not state.pending_decisions

    def test_twi_221_no_friendly_unit_skips_enemy_exhaust(self, repo):
        # No friendly unit → the first effect fizzles, so "If you do" never fires
        # and the enemy unit is left ready (the requires_prior_target gate).
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "221")
        assert not state.pending_decisions
        assert not _find_instance(state, enemy.instance_id).exhausted


class TestGrievoussWheelBike:
    """TWI_236 — Upgrade: "While playing this upgrade on General Grievous, it costs
    2 resources less to play.  Attach to a non-Vehicle unit.  Attached unit gains
    Overwhelm." """

    def test_twi_236_costs_2_less_on_general_grievous(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "15"), "ground")
        grievous.deployed = True
        other = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")  # non-Vehicle
        wheel = _put_in_hand(state, "P0", _get_card(repo, "TWI", "236"))
        ps = state.player_by_id("P0")
        on_other = _play_cost(state, wheel, ps, target_host_id=other.instance_id)
        on_grievous = _play_cost(state, wheel, ps, target_host_id=grievous.instance_id)
        on_none = _play_cost(state, wheel, ps)
        assert on_grievous == on_other - 2
        assert on_none == on_other  # the reduction needs the named host

    def test_twi_236_grants_overwhelm_only_to_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "TWI", "104"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        assert not has_keyword(state, host, Keyword.OVERWHELM)
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "236"), "P0")
        assert has_keyword(state, host, Keyword.OVERWHELM)         # conferred to host
        assert not has_keyword(state, other, Keyword.OVERWHELM)    # not to other units

    def test_twi_236_played_from_hand_on_grievous_pays_reduced(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, _play_cost
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "15"), "ground")
        grievous.deployed = True
        wheel = _put_in_hand(state, "P0", _get_card(repo, "TWI", "236"))
        ps = state.player_by_id("P0")
        cost = _play_cost(state, wheel, ps, target_host_id=grievous.instance_id)
        _give_resources(state, "P0", cost)  # exactly enough at the reduced cost
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard)
                    and a.instance_id == wheel.instance_id
                    and a.upgrade_target_id == grievous.instance_id)
        state = apply(state, play)
        g = _find_instance(state, grievous.instance_id)
        assert any(u.instance_id == wheel.instance_id for u in g.attached_upgrades)
        assert has_keyword(state, g, Keyword.OVERWHELM)
        assert state.player_by_id("P0").available_resources == 0


# ── Group general-grievous:05 — create-token-unit (Battle Droid) ──────────────

def _battle_droids(state, owner_id="P0"):
    """Return the owner's in-play Battle Droid token-unit instances."""
    from swu.cards.models import TokenUnit
    ps = state.player_by_id(owner_id)
    return [ci for ci in ps.ground_arena + ps.space_arena
            if isinstance(ci.card_def, TokenUnit) and ci.card_def.name == "Battle Droid"]


class TestConfederateCourier:
    """TWI_79 — "When Defeated: Create a Battle Droid token." """

    def test_twi_79_when_defeated_creates_token(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        courier = _place(state, "P0", _get_card(repo, "TWI", "79"), "ground")
        assert not _battle_droids(state)
        _defeat_unit(state, state.player_by_id("P0"), courier)
        # The token is created for the dying unit's controller (P0).
        assert len(_battle_droids(state)) == 1
        assert not state.pending_decisions
        # It is a 1/1 Battle Droid that entered the ground arena exhausted.
        tok = _battle_droids(state)[0]
        assert tok.card_def.power == 1 and tok.card_def.hp == 1
        assert tok.zone.name == "GROUND_ARENA" and tok.exhausted is True


class TestPoggleTheLesser:
    """TWI_80 — "When you play another unit: You may exhaust this unit. If you do,
    create a Battle Droid token." """

    def test_twi_80_exhaust_creates_token_on_accept(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects)
        state = _make_state()
        poggle = _place(state, "P0", _get_card(repo, "TWI", "80"), "ground")
        # Another unit P0 plays this phase (already in a zone so its type resolves).
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_card_played(state, "P0", other)
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger)
                      and a.source_id == poggle.instance_id)
        state = apply(state, accept)
        # The two non-targeted effects (exhaust SELF, create token) auto-resolve.
        auto = next(a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects))
        state = apply(state, auto)
        assert not state.pending_decisions
        assert _find_instance(state, poggle.instance_id).exhausted is True
        assert len(_battle_droids(state)) == 1

    def test_twi_80_decline_makes_no_token(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        poggle = _place(state, "P0", _get_card(repo, "TWI", "80"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_card_played(state, "P0", other)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        assert _find_instance(state, poggle.instance_id).exhausted is False
        assert not _battle_droids(state)

    def test_twi_80_not_offered_while_exhausted(self, repo):
        """The exhaust-this-unit cost can't be paid → trigger is not offered."""
        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        state = _make_state()
        poggle = _place(state, "P0", _get_card(repo, "TWI", "80"), "ground")
        poggle.exhausted = True
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_card_played(state, "P0", other)
        assert not state.pending_decisions
        acts = legal_actions(state)
        assert not any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts)


class TestGeneralsGuardian:
    """TWI_83 — "When this unit is attacked: Create a Battle Droid token." """

    def test_twi_83_when_attacked_creates_token(self, repo):
        state = _make_state()
        guardian = _place(state, "P0", _get_card(repo, "TWI", "83"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        assert not _battle_droids(state)
        state = _fire_on_attack(state, attacker, guardian)
        assert len(_battle_droids(state)) == 1
        assert not state.pending_decisions


class TestKraken:
    """TWI_84 — "When Played: Create 2 Battle Droid tokens. On Attack: Give each
    friendly token unit +1/+1 for this phase." """

    def test_twi_84_when_played_creates_two(self, repo):
        state = _make_state()
        kraken = _place(state, "P0", _get_card(repo, "TWI", "84"), "ground")
        state = _fire_when_played(state, kraken)
        assert len(_battle_droids(state)) == 2
        assert not state.pending_decisions

    def test_twi_84_on_attack_buffs_only_friendly_tokens(self, repo):
        from swu.engine.actions import compute_power, compute_hp, _create_token_units
        state = _make_state()
        kraken = _place(state, "P0", _get_card(repo, "TWI", "84"), "ground")
        tok = _create_token_units(state, state.player_by_id("P0"),
                                  "Battle Droid", 1)[0]
        enemy_tok = _create_token_units(state, state.player_by_id("P1"),
                                        "Battle Droid", 1)[0]
        ally = _filler(state, "P0", repo)             # non-token friendly 3/1
        state = _fire_on_attack(state, kraken)
        # +1/+1 to the friendly token only (1/1 → 2/2).
        assert compute_power(state, tok) == 2 and compute_hp(state, tok) == 2
        assert compute_power(state, enemy_tok) == 1  # enemy token untouched
        assert compute_power(state, ally) == 3       # non-token friendly untouched
        # Kraken (a real unit, not a token) does not buff itself.
        assert compute_power(state, kraken) == 2


class TestSubjugatingStarfighter:
    """TWI_112 — Ambush + "When Played: If you have the initiative, create a Battle
    Droid token." """

    def test_twi_112_creates_token_with_initiative(self, repo):
        state = _make_state()
        state.initiative_holder = 0                   # P0 has initiative
        sf = _place(state, "P0", _get_card(repo, "TWI", "112"), "space")
        state = _fire_when_played(state, sf)
        assert len(_battle_droids(state)) == 1

    def test_twi_112_no_token_without_initiative(self, repo):
        state = _make_state()
        state.initiative_holder = 1                   # P1 has initiative, not P0
        sf = _place(state, "P0", _get_card(repo, "TWI", "112"), "space")
        state = _fire_when_played(state, sf)
        assert not _battle_droids(state)
        assert not state.pending_decisions


class TestOnTheDoorstep:
    """TWI_190 — Event: "Create 3 Battle Droid tokens and ready them." """

    def test_twi_190_creates_three_ready_tokens(self, repo):
        state, _ = _play_event_from_hand(state := _make_state(), repo, "TWI", "190")
        toks = _battle_droids(state)
        assert len(toks) == 3
        # "and ready them" — all three enter ready, not the default exhausted.
        assert all(not t.exhausted for t in toks)


class TestDroidCohort:
    """TWI_218 — Upgrade: "Attached unit gains, 'When Defeated: Create a Battle
    Droid token.'" """

    def test_twi_218_granted_when_defeated_creates_token(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "218"), "P0")
        assert not _battle_droids(state)
        _defeat_unit(state, state.player_by_id("P0"), host)
        # The granted ability resolves from the host → token to the host's controller.
        assert len(_battle_droids(state)) == 1
        assert not state.pending_decisions

    def test_twi_218_no_token_without_the_upgrade(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), host)
        assert not _battle_droids(state)


# ── Group general-grievous:06 — create-token-unit (Battle Droid), part 2 ───────


class TestPoliticalPressure:
    """TWI_222 — Event: "Choose an opponent. They may discard a random card from
    their hand. If they don't, create 2 Battle Droid tokens."  A new ``may_discard``
    decision handed to the opponent (the say_no SOR_233 deciding-player shift)."""

    def test_twi_222_opponent_declines_controller_creates_two_tokens(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDiscard
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))  # opponent has a card
        state, _evt = _play_event_from_hand(state, repo, "TWI", "222")
        top = state.pending_decisions[-1]
        assert top.kind == "may_discard" and top.deciding_player_id == "P1"
        assert not _battle_droids(state, "P0")
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineDiscard))
        state = apply(state, decline)
        assert not state.pending_decisions
        # The controller (P0) gets 2 Battle Droid tokens; the opponent kept its card.
        assert len(_battle_droids(state, "P0")) == 2
        assert len(state.player_by_id("P1").hand) == 1
        assert state.active_player_index == 0  # turn handed back to the controller

    def test_twi_222_opponent_discards_random_card_prevents_tokens(self, repo):
        from swu.engine.actions import legal_actions, apply, DiscardRandomCard
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        _put_in_hand(state, "P1", _get_card(repo, "TWI", "240"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "222")
        hand_before = len(state.player_by_id("P1").hand)
        discard = next(a for a in legal_actions(state) if isinstance(a, DiscardRandomCard))
        state = apply(state, discard)
        assert not state.pending_decisions
        # A (random) card left P1's hand for the discard pile; no tokens are created.
        assert len(state.player_by_id("P1").hand) == hand_before - 1
        assert len(state.player_by_id("P1").discard) == 1
        assert not _battle_droids(state, "P0")

    def test_twi_222_empty_opponent_hand_creates_tokens_inline(self, repo):
        """An opponent with no cards "doesn't" discard → tokens created, no decision."""
        state = _make_state()  # P1 starts with an empty hand
        state, _evt = _play_event_from_hand(state, repo, "TWI", "222")
        assert not state.pending_decisions
        assert len(_battle_droids(state, "P0")) == 2


class TestBattleDroidEscort:
    """TWI_229 — Unit: "When Played/When Defeated: Create a Battle Droid token." """

    def test_twi_229_when_played_creates_token(self, repo):
        state = _make_state()
        escort = _place(state, "P0", _get_card(repo, "TWI", "229"), "ground")
        state = _fire_when_played(state, escort)
        assert len(_battle_droids(state)) == 1
        assert not state.pending_decisions

    def test_twi_229_when_defeated_creates_token(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        escort = _place(state, "P0", _get_card(repo, "TWI", "229"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), escort)
        assert len(_battle_droids(state)) == 1
        assert not state.pending_decisions


class TestTheInvisibleHand:
    """TWI_234 — Unit: "When Played: Create 4 Battle Droid tokens.  On Attack:
    Exhaust any number of friendly Separatist units. Deal 1 damage to the defending
    player's base for each unit exhausted this way."  A new
    ``exhaust_for_base_damage`` multi-select decision."""

    def _enemy_base(self, state):
        return state.player_by_id("P1").base_instance

    def test_twi_234_when_played_creates_four_tokens(self, repo):
        state = _make_state()
        ih = _place(state, "P0", _get_card(repo, "TWI", "234"), "space")
        state = _fire_when_played(state, ih)
        assert len(_battle_droids(state)) == 4
        assert not state.pending_decisions

    def test_twi_234_on_attack_exhausts_chosen_deals_base_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _create_token_units,
            SelectUnitToExhaust, FinishExhaustForBaseDamage)
        state = _make_state()
        ih = _place(state, "P0", _get_card(repo, "TWI", "234"), "space")
        ih.exhausted = True  # the attacker is exhausted from attacking (CR step 1)
        # Three ready friendly Battle Droids (Separatist) + a non-Separatist filler.
        droids = _create_token_units(state, state.player_by_id("P0"),
                                     "Battle Droid", 3, enters_ready=True)
        filler = _filler(state, "P0", repo)  # SOR_128, not Separatist
        state = _fire_on_attack(state, ih)
        top = state.pending_decisions[-1]
        assert top.kind == "exhaust_for_base_damage" and top.deciding_player_id == "P0"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaust)}
        assert offered == {d.instance_id for d in droids}   # only ready Separatist units
        assert filler.instance_id not in offered
        assert ih.instance_id not in offered                # the exhausted attacker
        # Exhaust two of the three, then finish ("any number").
        state = apply(state, SelectUnitToExhaust(droids[0].instance_id))
        assert _find_instance(state, droids[0].instance_id).exhausted is True
        state = apply(state, SelectUnitToExhaust(droids[1].instance_id))
        state = apply(state, FinishExhaustForBaseDamage())
        assert not state.pending_decisions
        # 2 units exhausted → 2 damage to the defending (P1) base; droids[2] untouched.
        assert self._enemy_base(state).damage == 2
        assert _find_instance(state, droids[2].instance_id).exhausted is False

    def test_twi_234_exhausting_all_auto_resolves_and_deals_full_damage(self, repo):
        from swu.engine.actions import (
            apply, _create_token_units, SelectUnitToExhaust)
        state = _make_state()
        ih = _place(state, "P0", _get_card(repo, "TWI", "234"), "space")
        ih.exhausted = True
        droids = _create_token_units(state, state.player_by_id("P0"),
                                     "Battle Droid", 2, enters_ready=True)
        state = _fire_on_attack(state, ih)
        # Exhaust both — the decision auto-resolves once no ready unit remains.
        state = apply(state, SelectUnitToExhaust(droids[0].instance_id))
        state = apply(state, SelectUnitToExhaust(droids[1].instance_id))
        assert not state.pending_decisions
        assert self._enemy_base(state).damage == 2

    def test_twi_234_finish_with_none_chosen_deals_no_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _create_token_units, FinishExhaustForBaseDamage)
        state = _make_state()
        ih = _place(state, "P0", _get_card(repo, "TWI", "234"), "space")
        ih.exhausted = True
        _create_token_units(state, state.player_by_id("P0"),
                            "Battle Droid", 1, enters_ready=True)
        state = _fire_on_attack(state, ih)
        finish = next(a for a in legal_actions(state)
                      if isinstance(a, FinishExhaustForBaseDamage))
        state = apply(state, finish)
        assert not state.pending_decisions
        assert self._enemy_base(state).damage == 0

    def test_twi_234_no_eligible_ready_separatist_unit_no_decision(self, repo):
        """No ready friendly Separatist unit → the On Attack ability fizzles."""
        state = _make_state()
        ih = _place(state, "P0", _get_card(repo, "TWI", "234"), "space")
        ih.exhausted = True
        _filler(state, "P0", repo)  # ready, but not Separatist
        state = _fire_on_attack(state, ih)
        assert not state.pending_decisions


class TestDroidDeployment:
    """TWI_237 — Event: "Create 2 Battle Droid tokens." """

    def test_twi_237_event_creates_two_tokens(self, repo):
        state, _ = _play_event_from_hand(state := _make_state(), repo, "TWI", "237")
        assert len(_battle_droids(state)) == 2


# ── TWI_193 R2-D2 (qui-gon-jinn:02 — a TWI card in an LOF deck) ────────────────

class TestR2D2:
    """When Played: You may discard a card from your hand.  If you do, search the
    top 3 cards of your deck for a card and draw it."""

    def test_twi_193_discard_then_search_and_draw(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, DiscardForSearch, SelectSearchCard, FinishSearch,
        )
        state = _make_state()
        r2 = _place(state, "P0", _get_card(repo, "TWI", "193"), "ground")
        held = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _add_deck_cards(state, "P0", repo, 3)
        deck_top_ids = [c.instance_id for c in state.player_by_id("P0").deck[:3]]

        state = _fire_when_played(state, r2)
        top = state.pending_decisions[-1]
        assert top.kind == "discard_for_search" and top.context.get("optional") is True

        # Discard the held card → a deck_search decision is pushed.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DiscardForSearch)
                                  and a.instance_id == held.instance_id))
        assert held.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").discard}
        assert state.pending_decisions[-1].kind == "deck_search"

        # Take a revealed card → it is drawn into hand.
        pick = next(a for a in legal_actions(state) if isinstance(a, SelectSearchCard))
        state = apply(state, pick)
        # FinishSearch (if still pending) to bottom the rest.
        if state.pending_decisions and state.pending_decisions[-1].kind == "deck_search":
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, FinishSearch)))
        hand_ids = {c.instance_id for c in state.player_by_id("P0").hand}
        assert pick.instance_id in hand_ids
        assert pick.instance_id in deck_top_ids

    def test_twi_193_may_decline(self, repo):
        """The discard is optional ("You may") — declining leaves hand and deck
        untouched, no search."""
        from swu.engine.actions import legal_actions, apply, FinishDiscardForSearch
        state = _make_state()
        r2 = _place(state, "P0", _get_card(repo, "TWI", "193"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _add_deck_cards(state, "P0", repo, 3)
        before_hand = len(state.player_by_id("P0").hand)
        before_disc = len(state.player_by_id("P0").discard)
        state = _fire_when_played(state, r2)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishDiscardForSearch)))
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == before_hand
        assert len(state.player_by_id("P0").discard) == before_disc

    def test_twi_193_empty_hand_no_decision(self, repo):
        """With an empty hand there is nothing to discard — the mandatory trigger
        fizzles cleanly (no decision pushed)."""
        state = _make_state()
        r2 = _place(state, "P0", _get_card(repo, "TWI", "193"), "ground")
        _add_deck_cards(state, "P0", repo, 3)
        state = _fire_when_played(state, r2)
        assert not state.pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:03 — Card advantage & disruption (TWI_191)
# ══════════════════════════════════════════════════════════════════════════════

class TestWolfPackEscort:
    """TWI_191 — When Played: You may return a friendly non-leader, non-Vehicle
    unit to its owner's hand."""

    def test_twi_191_returns_friendly_non_vehicle_unit_to_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        escort = _place(state, "P0", _get_card(repo, "TWI", "191"), "space")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # non-Vehicle
        state = _fire_when_played(state, escort)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        ps = state.player_by_id("P0")
        assert any(c.instance_id == friendly.instance_id for c in ps.hand)
        assert _find_instance(state, friendly.instance_id) is None

    def test_twi_191_auto_declines_with_no_eligible_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        escort = _place(state, "P0", _get_card(repo, "TWI", "191"), "space")
        # Only a Vehicle would be excluded; here there is simply no other unit, and
        # the escort itself is a Vehicle → non_vehicle excludes it. No eligible
        # target, so the optional trigger auto-declines (no AcceptTrigger offered).
        state = _fire_when_played(state, escort)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:04 — Huyang (TWI_110)
# ══════════════════════════════════════════════════════════════════════════════


class TestHuyang:
    """TWI_110 Huyang — "When Played: Choose another friendly unit. While this unit
    is in play, the chosen unit gets +2/+2." (the permanent-while-source-in-play
    modifier semantic)."""

    def test_twi_110_buffs_chosen_unit_while_in_play(self, repo):
        from swu.engine.actions import legal_actions, apply, compute_power, compute_hp, ChooseTarget
        state = _make_state()
        huyang = _place(state, "P0", _get_card(repo, "TWI", "110"), "ground")  # 2/4
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        state = _fire_when_played(state, huyang)
        ct = next(a for a in legal_actions(state)
                  if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, ct)
        ally_now = _find_instance(state, ally.instance_id)
        assert compute_power(state, ally_now) == 5   # 3 + 2
        assert compute_hp(state, ally_now) == 9       # 7 + 2
        # The buff lasts only "while this unit [Huyang] is in play".
        h = _find_instance(state, huyang.instance_id)
        state.player_by_id("P0").ground_arena.remove(h)
        ally_now = _find_instance(state, ally.instance_id)
        assert compute_power(state, ally_now) == 3
        assert compute_hp(state, ally_now) == 7

    def test_twi_110_no_target_when_alone(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        huyang = _place(state, "P0", _get_card(repo, "TWI", "110"), "ground")
        state = _fire_when_played(state, huyang)
        # No other friendly unit -> the mandatory targeted effect has no target.
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ── Reprint-duplicate encode (Stage 4 batch 5) ────────────────────────────────

class TestEnfysNest:
    """TWI_198 — Saboteur.  When Played/On Attack: You may return an enemy
    non-leader unit with less power than this unit (5) to its owner's hand."""

    def test_twi_198_when_played_returns_weaker_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        enfys = _place(state, "P0", _get_card(repo, "TWI", "198"), "ground")  # power 5
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # power 3
        state = _fire_when_played(state, enfys)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(weak.instance_id))
        assert _find_instance(state, weak.instance_id) is None  # bounced
        assert len(state.player_by_id("P1").hand) == 1

    def test_twi_198_on_attack_offers_only_weaker_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        enfys = _place(state, "P0", _get_card(repo, "TWI", "198"), "ground")  # power 5
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # power 3 < 5
        tough = _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")   # power 8 >= 5
        state = _fire_on_attack(state, enfys)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert weak.instance_id in offered
        assert tough.instance_id not in offered

    def test_twi_198_auto_declines_with_no_weaker_enemy(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        enfys = _place(state, "P0", _get_card(repo, "TWI", "198"), "ground")  # power 5
        _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")           # power 8
        state = _fire_when_played(state, enfys)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


# ── Stage-4 reprint sweep (Batch 8) ───────────────────────────────────────────
# TWI_121 General's Blade.


class TestGeneralsBladeTWI121:
    """Upgrade: If attached unit is a Jedi, it gains 'On Attack: The next unit you
    play this phase costs 2 resources less.'"""

    def test_twi_121_jedi_host_grants_next_unit_discount(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "45"), "ground")  # Yoda, Jedi
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "121"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, host, defender)
        disc = state.game_memory.pending_play_discounts
        assert len(disc) == 1
        assert disc[0]["amount"] == 2 and not disc[0]["trait"]  # any unit

    def test_twi_121_non_jedi_host_no_discount(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")  # not Jedi
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "121"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, host, defender)
        assert not state.game_memory.pending_play_discounts

    def test_twi_121_discount_reduces_next_unit_cost(self, repo):
        from swu.engine.actions import _pending_play_discount
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "45"), "ground")  # Jedi
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "121"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, host, defender)
        ps = state.player_by_id("P0")
        unit = CardInstance("P0_next", _get_card(repo, "SOR", "88"), "P0", Zone.HAND)
        ps.hand.append(unit)
        assert _pending_play_discount(state, unit, ps) == 2


# ── Stage-4 reprint sweep (batch 11) ─────────────────────────────────────────

class TestUnnaturalLife:
    """TWI_189 — Event: Play a unit that was defeated this phase from your discard
    pile for 2 less, ready; defeat it at the start of the regroup phase."""

    def test_twi_189_plays_defeated_unit_ready_with_regroup_flag(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.state import Zone
        state = _make_state()
        unit = _put_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        state.game_memory.units_defeated_this_round.add(unit.instance_id)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "189", "P0", resources=30)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        _, u = state.find_instance(unit.instance_id)
        assert u.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)  # entered play
        assert not u.exhausted                                  # enters play ready
        assert u.defeat_at_regroup is True                      # defeated at regroup

    def test_twi_189_non_defeated_discard_unit_not_offered(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        from swu.engine.state import Zone
        state = _make_state()
        unit = _put_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        # NOT marked as defeated this phase → not eligible.
        state, _evt = _play_event_from_hand(state, repo, "TWI", "189", "P0", resources=30)
        assert not any(isinstance(a, PlayFromHand) for a in legal_actions(state))
        _, u = state.find_instance(unit.instance_id)
        assert u.zone == Zone.DISCARD


# ── Stage 4 batch 30 (2026-07-13) — FRAMEWORK ESCALATION: the opponent-plays-Nth-
#    card observer trigger (Ki-Adi-Mundi TWI_64).

class TestKiAdiMundiTWI64:
    """Ki-Adi-Mundi TWI_64 (canonical; J25_2 is a byte-identical reprint face):
    "Coordinate — When an opponent plays their second card each phase: You may draw
    2 cards."

    The new ``WhenOpponentPlaysNthCard(count=2)`` observer trigger + a per-phase
    per-player card-play counter (``GameMemory.cards_played_this_phase``, bumped at
    the CardPlayed firing chokepoint in ``fire_triggered_abilities``).  The
    Coordinate prefix is the ``CONTROLLER_N_PLUS_UNITS(3)`` condition gating trigger
    collection.
    """

    def _setup(self, repo, p0_units=3):
        """P0 controls Ki-Adi + fillers (>=3 for Coordinate) and has a deck to draw."""
        state = _make_state()
        kiadi = _place(state, "P0", _get_card(repo, "TWI", "64"), "ground")
        for _ in range(max(0, p0_units - 1)):
            _filler(state, "P0", repo)
        _add_deck_cards(state, "P0", repo, 4)
        return state, kiadi

    def _opp_plays(self, state, repo):
        """P1 plays one card (place a P1 unit, then fire its CardPlayed)."""
        played = _filler(state, "P1", repo)
        return _fire_card_played(state, "P1", played)

    def _drain(self, state):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        for _ in range(20):
            act = next((a for a in legal_actions(state)
                        if isinstance(a, AutoResolveEffects)), None)
            if act is None:
                break
            state = apply(state, act)
        return state

    def test_twi_64_first_opponent_play_offers_no_draw(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, _ = self._setup(repo)
        state = self._opp_plays(state, repo)         # opponent's 1st card
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_twi_64_second_opponent_play_may_draw_two(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state, _ = self._setup(repo)
        state = self._opp_plays(state, repo)         # 1st
        state = self._opp_plays(state, repo)         # 2nd → the trigger fires
        before = len(state.player_by_id("P0").hand)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        state = self._drain(state)
        assert len(state.player_by_id("P0").hand) == before + 2      # drew 2

    def test_twi_64_third_opponent_play_does_not_retrigger(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, DeclineTrigger
        state, _ = self._setup(repo)
        state = self._opp_plays(state, repo)         # 1st
        state = self._opp_plays(state, repo)         # 2nd → trigger
        dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, dec)
        state = self._opp_plays(state, repo)         # 3rd → count 3 ≠ 2, no trigger
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_twi_64_requires_coordinate_three_units(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, _ = self._setup(repo, p0_units=1)     # only Ki-Adi → Coordinate OFF
        state = self._opp_plays(state, repo)
        state = self._opp_plays(state, repo)         # 2nd card, but <3 friendly units
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_twi_64_friendly_plays_do_not_count(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, _ = self._setup(repo)
        # P0's own two plays do not advance the opponent's counter.
        a = _filler(state, "P0", repo)
        state = _fire_card_played(state, "P0", a)
        b = _filler(state, "P0", repo)
        state = _fire_card_played(state, "P0", b)
        assert not any(isinstance(a2, AcceptTrigger) for a2 in legal_actions(state))
        # The opponent's counter is independent: their 2nd play still triggers.
        state = self._opp_plays(state, repo)         # P1 1st
        state = self._opp_plays(state, repo)         # P1 2nd → trigger
        assert any(isinstance(a2, AcceptTrigger) for a2 in legal_actions(state))

    def test_twi_64_counter_resets_each_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, DeclineTrigger
        state, _ = self._setup(repo)
        state = self._opp_plays(state, repo)         # 1st
        state = self._opp_plays(state, repo)         # 2nd → trigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        state.game_memory.clear_phase()              # phase rollover clears the counter
        state = self._opp_plays(state, repo)         # new phase, opponent's 1st → no trigger
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state = self._opp_plays(state, repo)         # opponent's 2nd this phase → triggers again
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_twi_64_reprint_face_registered(self):
        from swu.abilities.registry import get_abilities
        assert get_abilities("J25", "2") is get_abilities("TWI", "64")


# ── twi-set:01 — Direct damage & removal ──────────────────────────────────────

def _choose_target(state, target_id):
    """Apply the ChooseTarget for ``target_id`` from the current decision."""
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, act)


def _target_ids(state):
    from swu.engine.actions import legal_actions, ChooseTarget
    return {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}


class TestObiWanKenobiTwi3:
    """TWI_3 — undeployed "Action [Exhaust]: Heal 1 damage from a unit"; deployed
    "On Attack: Heal 1 damage from a unit. If you do, deal 1 damage to a different
    unit"."""

    def test_TWI_3_undeployed_action_heals_a_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        obi = _place_leader(state, "P0", _get_card(repo, "TWI", "3"))
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 4
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == obi.instance_id)
        state = apply(state, use)
        state = _choose_target(state, hurt.instance_id)
        _, healed = state.find_instance(hurt.instance_id)
        assert healed.damage == 3

    def test_TWI_3_undeployed_action_only_offers_damaged_units(self, repo):
        """Nothing damaged ⇒ the heal has no candidate and never prompts."""
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        obi = _place_leader(state, "P0", _get_card(repo, "TWI", "3"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # undamaged
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == obi.instance_id)
        state = apply(state, use)
        assert not _target_ids(state)

    def test_TWI_3_deployed_on_attack_heals_then_burns_a_different_unit(self, repo):
        state = _make_state()
        obi = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "3"))
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 4
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, obi, enemy)
        state = _choose_target(state, hurt.instance_id)          # heal
        # "a different unit" — the healed unit is excluded from the burn.
        assert hurt.instance_id not in _target_ids(state)
        state = _choose_target(state, enemy.instance_id)         # burn
        _, healed = state.find_instance(hurt.instance_id)
        _, burned = state.find_instance(enemy.instance_id)
        assert healed.damage == 3 and burned.damage == 1

    def test_TWI_3_deployed_on_attack_burn_needs_the_heal_to_happen(self, repo):
        """"If you do" — with nothing damaged to heal, the damage clause fizzles."""
        state = _make_state()
        obi = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "3"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, obi, enemy)
        assert not _target_ids(state)
        _, untouched = state.find_instance(enemy.instance_id)
        assert untouched.damage == 0


class TestPreVizslaTwi10:
    """TWI_10 — undeployed Action scaling off cards drawn this phase; deployed
    hand-size self-grants."""

    def test_TWI_10_undeployed_damage_equals_cards_drawn_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        vizsla = _place_leader(state, "P0", _get_card(repo, "TWI", "10"))
        _give_resources(state, "P0", 1, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.cards_drawn_this_phase["P0"] = 3
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == vizsla.instance_id)
        state = apply(state, use)
        state = _choose_target(state, enemy.instance_id)
        _, hit = state.find_instance(enemy.instance_id)
        assert hit.damage == 3

    def test_TWI_10_draw_tally_is_fed_by_the_draw_chokepoint(self, repo):
        """The count comes from real ACTION-phase draws, not a hand-wired number."""
        from swu.engine.actions import _draw_cards
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 4)
        _draw_cards(state, state.player_by_id("P0"), 2)
        assert state.game_memory.cards_drawn_this_phase["P0"] == 2
        state.game_memory.clear_phase()
        assert state.game_memory.cards_drawn_this_phase == {}

    def test_TWI_10_deployed_hand_size_grants_saboteur_then_power(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        vizsla = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "10"))
        assert not has_keyword(state, vizsla, Keyword.SABOTEUR)
        assert compute_power(state, vizsla) == 4
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        assert has_keyword(state, vizsla, Keyword.SABOTEUR)   # 3 cards
        assert compute_power(state, vizsla) == 4              # but not yet 6
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        assert compute_power(state, vizsla) == 6              # 6 cards → +2/+0


class TestMaceWinduTwi13:
    """TWI_13 — undeployed "Deal 1 to a damaged enemy unit. Then, if it has 5 or
    more damage on it, deal 1 damage to it"; deployed "When Deployed: Deal 2 to
    each damaged enemy unit"."""

    def _use_action(self, state, mace):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == mace.instance_id)
        return apply(state, use)

    def test_TWI_13_undeployed_second_point_lands_at_5_damage(self, repo):
        state = _make_state()
        mace = _place_leader(state, "P0", _get_card(repo, "TWI", "13"))
        _give_resources(state, "P0", 1, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.damage = 4
        state = self._use_action(state, mace)
        state = _choose_target(state, enemy.instance_id)
        _, hit = state.find_instance(enemy.instance_id)
        assert hit.damage == 6      # 4 +1 → 5 → the "then" clause adds 1 more

    def test_TWI_13_undeployed_single_point_below_the_threshold(self, repo):
        state = _make_state()
        mace = _place_leader(state, "P0", _get_card(repo, "TWI", "13"))
        _give_resources(state, "P0", 1, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.damage = 1
        state = self._use_action(state, mace)
        state = _choose_target(state, enemy.instance_id)
        _, hit = state.find_instance(enemy.instance_id)
        assert hit.damage == 2

    def test_TWI_13_when_deployed_hits_each_damaged_enemy_unit(self, repo):
        from swu.engine.events import LeaderDeployed
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        mace = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "13"))
        hurt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 1
        clean = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friendly_hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly_hurt.damage = 1
        evt = LeaderDeployed(player_id="P0", instance_id=mace.instance_id,
                             leader_name=mace.card_def.display_name, arena="Ground")
        state.event_log.append(evt)
        state = fire_triggered_abilities(state, evt, after_all_player_idx=0)
        assert state.find_instance(hurt.instance_id)[1].damage == 3
        assert state.find_instance(clean.instance_id)[1].damage == 0
        assert state.find_instance(friendly_hurt.instance_id)[1].damage == 1


class TestChancellorPalpatineTwi17:
    """TWI_17 — a double-sided leader that FLIPS instead of deploying.  Each side's
    Action is gated on the side currently showing AND its own "If …" clause."""

    def _uses(self, state, leader):
        from swu.engine.actions import legal_actions, UseAbility
        return [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.source_id == leader.instance_id]

    def test_TWI_17_front_action_needs_a_friendly_heroism_defeat_then_flips(self, repo):
        from swu.engine.actions import apply, legal_actions, AttackWithUnit
        state = _make_state()
        palps = _place_leader(state, "P0", _get_card(repo, "TWI", "17"))
        _add_deck_cards(state, "P0", repo, 2)
        state.player_by_id("P0").base_instance.damage = 5
        # Neither side is live yet: nothing defeated, no Villainy card played.
        assert not self._uses(state, palps)

        # A friendly Heroism unit dies attacking — the real defeat path feeds the
        # aspect ledger the front side reads.
        trooper = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # 3/2
        wall = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")      # 3/7
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == trooper.instance_id
                   and a.defender_id == wall.instance_id)
        state = apply(state, atk)
        assert "Heroism" in state.game_memory.defeated_aspects_this_round["P0"]

        state.active_player_index = 0
        uses = self._uses(state, palps)
        assert len(uses) == 1
        state = apply(state, uses[0])
        # The effect list resolves lazily; the heal's base target is the only choice.
        state = _choose_target(state, state.player_by_id("P0").base_instance.instance_id)
        assert len(state.player_by_id("P0").hand) == 1
        assert state.player_by_id("P0").base_instance.damage == 3
        assert palps.instance_id in state.game_memory.flipped_leaders

    def test_TWI_17_back_action_needs_a_villainy_play_and_flips_back(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        palps = _place_leader(state, "P0", _get_card(repo, "TWI", "17"))
        state.game_memory.flipped_leaders.add(palps.instance_id)
        # Back side showing, but no Villainy card played this phase → not offered.
        assert not self._uses(state, palps)

        state.game_memory.villainy_players_this_phase.add("P0")
        uses = self._uses(state, palps)
        assert len(uses) == 1
        state = apply(state, uses[0])
        state = _choose_target(state, state.player_by_id("P1").base_instance.instance_id)
        ps0 = state.player_by_id("P0")
        assert any(ci.card_def.display_name.startswith("Clone Trooper")
                   for ci in ps0.ground_arena)
        assert state.player_by_id("P1").base_instance.damage == 2
        assert palps.instance_id not in state.game_memory.flipped_leaders

    # ── aspect icons per side (a reported bug: no Villainy penalty while
    # Chancellor Palpatine was face up) ────────────────────────────────────────
    def _base_zone(self, state, repo, owner="P0"):
        """Palpatine TWI_17 + an Aggression base, the reporter's own board."""
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id(owner)
        leader = CardInstance(f"{owner}_palps", _get_card(repo, "TWI", "17"),
                              owner, Zone.BASE_ZONE)
        ps.base_zone = [
            CardInstance(f"{owner}_base", _get_card(repo, "SEC", "24"),
                         owner, Zone.BASE_ZONE),   # Naval Intelligence HQ, Aggression
            leader,
        ]
        return leader

    def test_TWI_17_front_side_provides_heroism_not_villainy(self, repo):
        """The DB carries the UNION of both sides' icons (Cunning/Villainy/Heroism);
        only the face-up side may offset a penalty."""
        from swu.engine.actions import _available_aspects
        state = _make_state()
        self._base_zone(state, repo)
        available = _available_aspects(state.player_by_id("P0"), state)
        assert available["Cunning"] == 1
        assert available["Heroism"] == 1
        assert available["Villainy"] == 0      # Darth Sidious is face DOWN

    def test_TWI_17_back_side_provides_villainy_not_heroism(self, repo):
        from swu.engine.actions import _available_aspects
        state = _make_state()
        leader = self._base_zone(state, repo)
        state.game_memory.flipped_leaders.add(leader.instance_id)
        available = _available_aspects(state.player_by_id("P0"), state)
        assert available["Cunning"] == 1
        assert available["Villainy"] == 1
        assert available["Heroism"] == 0

    def test_TWI_17_villainy_card_costs_the_penalty_until_he_flips(self, repo):
        """The reported bug: Tactical Droid Commander TWI_184 (Cunning/Villainy) was
        payable at its printed 5 while Palpatine sat on his Heroism side."""
        from swu.engine.actions import _effective_cost
        state = _make_state()
        leader = self._base_zone(state, repo)
        ps = state.player_by_id("P0")
        card = _get_card(repo, "TWI", "184")
        printed = card.cost
        assert {a.name for a in card.aspects} == {"Cunning", "Villainy"}

        # Front side: the Villainy pip is unmatched → +2.
        assert _effective_cost(card, ps, state) == printed + 2
        # Flipped to Darth Sidious: fully on-aspect.
        state.game_memory.flipped_leaders.add(leader.instance_id)
        assert _effective_cost(card, ps, state) == printed

    def test_TWI_17_heroism_card_costs_the_penalty_once_flipped(self, repo):
        """The mirror: flipping to Darth Sidious gives up the Heroism icon."""
        from swu.engine.actions import _effective_cost
        state = _make_state()
        leader = self._base_zone(state, repo)
        ps = state.player_by_id("P0")
        card = _get_card(repo, "TWI", "149")        # Low Altitude Gunship
        printed = card.cost
        assert "Heroism" in {a.name for a in card.aspects}

        assert _effective_cost(card, ps, state) == printed
        state.game_memory.flipped_leaders.add(leader.instance_id)
        assert _effective_cost(card, ps, state) == printed + 2

    def test_TWI_17_penalty_pill_in_the_hand_view_follows_the_side(self, repo):
        """The surcharge the player actually sees on the card in hand."""
        import uuid as _uuid
        from swu.engine.state import CardInstance, Zone
        from swu.engine.views import build_view
        state = _make_state()
        leader = self._base_zone(state, repo)
        ps = state.player_by_id("P0")
        ci = CardInstance(f"P0_h_{_uuid.uuid4().hex[:4]}",
                          _get_card(repo, "TWI", "184"), "P0", Zone.HAND)
        ps.hand.append(ci)

        pill = {c.instance_id: c for c in build_view(state, "P0").my.hand}
        assert pill[ci.instance_id].aspect_penalty == 2
        state.game_memory.flipped_leaders.add(leader.instance_id)
        pill = {c.instance_id: c for c in build_view(state, "P0").my.hand}
        assert pill[ci.instance_id].aspect_penalty == 0

    def test_TWI_17_ordinary_leader_aspects_are_unaffected(self, repo):
        """Only a card carrying the marker reads per-side; every other leader still
        contributes its printed icons (the deployed-leader fix stays intact)."""
        from swu.engine.actions import _available_aspects
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        leia = _get_card(repo, "LAW", "10")          # Command / Heroism
        ps.base_zone = [
            CardInstance("P0_base", _get_card(repo, "SEC", "24"), "P0", Zone.BASE_ZONE),
            CardInstance("P0_leia", leia, "P0", Zone.BASE_ZONE),
        ]
        available = _available_aspects(ps, state)
        for a in leia.aspects:
            assert available[a.name] >= 1


class TestQuinlanVosTwi18:
    """TWI_18 — "When you play a unit: … deal 1 damage to an enemy unit that costs
    the same as (undeployed) / the same as or less than (deployed) the played
    unit"."""

    def test_TWI_18_undeployed_exhausts_to_burn_an_equal_cost_enemy(self, repo):
        from swu.engine.actions import apply, legal_actions, AcceptTrigger
        state = _make_state()
        quinlan = _place_leader(state, "P0", _get_card(repo, "TWI", "18"))
        same = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # cost 4
        cheaper = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        played = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # cost 4
        state = _fire_card_played(state, "P0", played)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        # "costs the same as" — the cheaper enemy is NOT a legal target.
        assert _target_ids(state) == {same.instance_id}
        state = _choose_target(state, same.instance_id)
        assert state.find_instance(same.instance_id)[1].damage == 1
        assert state.find_instance(cheaper.instance_id)[1].damage == 0
        assert state.find_instance(quinlan.instance_id)[1].exhausted is True

    def test_TWI_18_undeployed_not_offered_while_exhausted(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        quinlan = _place_leader(state, "P0", _get_card(repo, "TWI", "18"))
        quinlan.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        played = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_card_played(state, "P0", played)
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]

    def test_TWI_18_deployed_burns_an_enemy_costing_the_same_or_less(self, repo):
        from swu.engine.actions import apply, legal_actions, AcceptTrigger
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "18"))
        same = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # cost 4
        cheaper = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        played = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_card_played(state, "P0", played)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        assert _target_ids(state) == {same.instance_id, cheaper.instance_id}


class TestGeneralGrievousTwi34:
    """TWI_34 — waives the aspect penalty on Lightsaber upgrades played on him, and
    an On Attack mass defeat once 4 Lightsabers are attached."""

    def test_TWI_34_waives_the_aspect_penalty_on_a_lightsaber_upgrade(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        blade = _get_card(repo, "TWI", "121")     # cost 3, one [Command] pip
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "34"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hand_ci = _put_in_hand(state, "P0", blade)
        _give_resources(state, "P0", 3, repo)     # printed cost only
        hosts = {a.upgrade_target_id for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == hand_ci.instance_id}
        # Grievous absorbs the +2 aspect penalty; the other host would need 5.
        assert hosts == {grievous.instance_id}
        _give_resources(state, "P0", 2, repo)     # 5 total → both hosts affordable
        hosts = {a.upgrade_target_id for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == hand_ci.instance_id}
        assert hosts == {grievous.instance_id, other.instance_id}

    def test_TWI_34_on_attack_defeats_4_enemy_units_with_4_lightsabers(self, repo):
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "34"), "ground")
        blade = _get_card(repo, "TWI", "121")
        for _ in range(4):
            _attach_upgrade_directly(state, grievous, blade, "P0")
        enemies = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                   for _ in range(4)]
        state = _fire_on_attack(state, grievous, enemies[0])
        for e in enemies:
            state = _choose_target(state, e.instance_id)
        assert state.player_by_id("P1").ground_arena == []

    def test_TWI_34_on_attack_silent_with_only_3_lightsabers(self, repo):
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TWI", "34"), "ground")
        blade = _get_card(repo, "TWI", "121")
        for _ in range(3):
            _attach_upgrade_directly(state, grievous, blade, "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, grievous, enemy)
        assert not _target_ids(state)
        assert state.find_instance(enemy.instance_id) is not None


class TestDevastatingGunshipTwi36:
    """TWI_36 — "When Played: Defeat an enemy unit with 2 or less remaining HP"."""

    def test_TWI_36_when_played_defeats_a_low_remaining_hp_enemy(self, repo):
        state = _make_state()
        frail = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        gunship = _place(state, "P0", _get_card(repo, "TWI", "36"), "space")
        state = _fire_when_played(state, gunship)
        assert _target_ids(state) == {frail.instance_id}
        state = _choose_target(state, frail.instance_id)
        ps1 = state.player_by_id("P1")
        assert [ci.instance_id for ci in ps1.ground_arena] == [tough.instance_id]
        assert frail.instance_id in {ci.instance_id for ci in ps1.discard}

    def test_TWI_36_when_played_fizzles_with_no_frail_enemy(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")           # 3/7
        gunship = _place(state, "P0", _get_card(repo, "TWI", "36"), "space")
        state = _fire_when_played(state, gunship)
        assert not _target_ids(state)


# ── twi-set:02 — Direct damage & removal ──────────────────────────────────────

class TestLethalCrackdownTwi41:
    """TWI_41 — "Defeat a non-leader unit. Deal damage to your base equal to that
    unit's power"."""

    def test_TWI_41_defeats_a_unit_and_bills_your_base_its_power(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3 power
        leader = _place_deployed_leader(state, "P1", _get_card(repo, "TWI", "11"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "41")
        # A deployed leader is not a legal target ("a non-leader unit").
        assert _target_ids(state) == {victim.instance_id}
        state = _choose_target(state, victim.instance_id)
        ps1 = state.player_by_id("P1")
        assert victim.instance_id not in {c.instance_id for c in ps1.ground_arena}
        assert leader.instance_id in {c.instance_id for c in ps1.ground_arena}
        assert state.player_by_id("P0").base_instance.damage == 3

    def test_TWI_41_bill_tracks_effective_power_not_printed(self, repo):
        """The base takes the unit's power *as it stood*, buffs included."""
        from swu.engine.state import Modifier
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(), source_instance_id=None,
            target_instance_id=victim.instance_id, kind="stats",
            value={"power": 2, "hp": 0}, duration="this_phase"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "41")
        state = _choose_target(state, victim.instance_id)
        assert state.player_by_id("P0").base_instance.damage == 5


class TestKashyyykDefenderTwi44:
    """TWI_44 — "When Played: Heal up to 2 damage from another unit and deal that
    much damage to this unit"."""

    def test_TWI_44_heals_another_unit_and_takes_that_much(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 5
        defender = _place(state, "P0", _get_card(repo, "TWI", "44"), "ground")
        state = _fire_when_played(state, defender)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _choose_target(state, hurt.instance_id)
        assert state.find_instance(hurt.instance_id)[1].damage == 3
        assert state.find_instance(defender.instance_id)[1].damage == 2

    def test_TWI_44_heals_only_what_is_there(self, repo):
        """"Up to 2" — a unit sitting on 1 damage transfers exactly 1."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 1
        defender = _place(state, "P0", _get_card(repo, "TWI", "44"), "ground")
        state = _fire_when_played(state, defender)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _choose_target(state, hurt.instance_id)
        assert state.find_instance(hurt.instance_id)[1].damage == 0
        assert state.find_instance(defender.instance_id)[1].damage == 1


class TestObiWansAethersprilteTwi48:
    """TWI_48 — "When Played/On Attack: You may deal 1 damage to this unit and 2
    damage to another space unit"."""

    def test_TWI_48_when_played_trades_1_self_damage_for_2(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        ship = _place(state, "P0", _get_card(repo, "TWI", "48"), "space")
        state = _fire_when_played(state, ship)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        # "another SPACE unit" — the ground unit is not a candidate.
        assert _target_ids(state) == {enemy.instance_id}
        state = _choose_target(state, enemy.instance_id)
        assert state.find_instance(enemy.instance_id)[1].damage == 2
        assert state.find_instance(ship.instance_id)[1].damage == 1
        assert state.find_instance(ground.instance_id)[1].damage == 0

    def test_TWI_48_on_attack_is_optional_and_declinable(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        ship = _place(state, "P0", _get_card(repo, "TWI", "48"), "space")
        state = _fire_on_attack(state, ship, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.find_instance(ship.instance_id)[1].damage == 0
        assert state.find_instance(enemy.instance_id)[1].damage == 0


class TestRoyalGuardAttacheTwi59:
    """TWI_59 — "When Played: Deal 2 damage to this unit"."""

    def test_TWI_59_when_played_damages_itself(self, repo):
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "TWI", "59"), "ground")
        state = _fire_when_played(state, guard)
        assert state.find_instance(guard.instance_id)[1].damage == 2


class TestDeathByDroidsTwi76:
    """TWI_76 — "Defeat a unit that costs 3 or less. Create 2 Battle Droid tokens"."""

    def test_TWI_76_defeats_a_cheap_unit_and_makes_two_droids(self, repo):
        state = _make_state()
        cheap = _place(state, "P1", _get_card(repo, "SOR", "179"), "ground")  # cost 3
        pricey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state, _evt = _play_event_from_hand(state, repo, "TWI", "76")
        assert _target_ids(state) == {cheap.instance_id}
        state = _choose_target(state, cheap.instance_id)
        ps0, ps1 = state.player_by_id("P0"), state.player_by_id("P1")
        assert cheap.instance_id not in {c.instance_id for c in ps1.ground_arena}
        assert pricey.instance_id in {c.instance_id for c in ps1.ground_arena}
        droids = [c for c in ps0.ground_arena
                  if c.card_def.display_name.startswith("Battle Droid")]
        assert len(droids) == 2


class TestInvasionOfChristophsisTwi78:
    """TWI_78 — "Choose an opponent. Defeat each unit that player controls"."""

    def test_TWI_78_defeats_every_enemy_unit_in_both_arenas(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "78", resources=20)
        # Exploit 4 is a keyword decision that fronts the body; commit nothing.
        from swu.engine.actions import legal_actions, apply, ExploitCommit
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ExploitCommit)))
        ps1 = state.player_by_id("P1")
        assert ps1.ground_arena == [] and ps1.space_arena == []
        assert mine.instance_id in {
            c.instance_id for c in state.player_by_id("P0").ground_arena}


class TestConsolidationOfPowerTwi89:
    """TWI_89 — "Choose any number of friendly units. You may play a unit from your
    hand if its cost is ≤ the combined power of the chosen units for free. Then,
    defeat the chosen units"."""

    def _setup(self, repo, hand_card):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3 power
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3 power
        hand_ci = _put_in_hand(state, "P0", _get_card(repo, *hand_card))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "89")
        return state, a, b, hand_ci

    def test_TWI_89_combined_power_pays_for_a_free_unit_then_they_die(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectCombinedPowerUnit, FinishCombinedPowerPlay,
            PlayFromHand,
        )
        # SHD_120 costs 5 — affordable only once BOTH 3-power units are pooled.
        state, a, b, hand_ci = self._setup(repo, ("SHD", "120"))
        assert state.pending_decisions[-1].kind == "combined_power_play"
        ps_before = state.player_by_id("P0")
        resources_before = len(ps_before.resources)
        exhausted_before = sum(1 for r in ps_before.resources if r.exhausted)

        state = apply(state, next(
            act for act in legal_actions(state)
            if isinstance(act, SelectCombinedPowerUnit) and act.unit_id == a.instance_id))
        state = apply(state, next(
            act for act in legal_actions(state)
            if isinstance(act, SelectCombinedPowerUnit) and act.unit_id == b.instance_id))
        state = apply(state, next(act for act in legal_actions(state)
                                  if isinstance(act, FinishCombinedPowerPlay)))

        assert state.pending_decisions[-1].kind == "play_from_hand"
        assert state.pending_decisions[-1].context["cost_max"] == 6
        play = next(act for act in legal_actions(state)
                    if isinstance(act, PlayFromHand)
                    and act.instance_id == hand_ci.instance_id)
        state = apply(state, play)

        ps0 = state.player_by_id("P0")
        arena_ids = {c.instance_id for c in ps0.ground_arena + ps0.space_arena}
        assert hand_ci.instance_id in arena_ids       # played…
        assert a.instance_id not in arena_ids         # …and the pool was spent
        assert b.instance_id not in arena_ids
        # "for free" — the play exhausted no further resources.
        assert sum(1 for r in ps0.resources if r.exhausted) == exhausted_before
        assert len(ps0.resources) == resources_before

    def test_TWI_89_choosing_nothing_defeats_nothing(self, repo):
        """"Any number" includes zero: finishing straight away spends no unit, and
        a 0 ceiling leaves nothing playable."""
        from swu.engine.actions import legal_actions, apply, FinishCombinedPowerPlay
        state, a, b, _hand = self._setup(repo, ("SHD", "120"))
        state = apply(state, next(act for act in legal_actions(state)
                                  if isinstance(act, FinishCombinedPowerPlay)))
        ps0 = state.player_by_id("P0")
        arena_ids = {c.instance_id for c in ps0.ground_arena}
        assert {a.instance_id, b.instance_id} <= arena_ids
        assert not any(d.kind == "play_from_hand" for d in state.pending_decisions)


# ── twi-set:03 — Direct damage & removal ──────────────────────────────────────


def _accept(state):
    """Accept the topmost offered trigger, then drain any AutoResolveEffects steps
    (a non-inlinable effect list resolves one action at a time)."""
    from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                    AutoResolveEffects)
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, AcceptTrigger)))
    while True:
        auto = [a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)]
        if not auto:
            return state
        state = apply(state, auto[0])


class TestPyrrhicAssaultTwi103:
    """TWI_103 — "For this phase, each friendly unit gains: 'When Defeated: Deal 2
    damage to an enemy unit.'"  The aura's source is the spent EVENT, which lives in
    the discard by the time any unit dies — the phase_aura_sources seam."""

    def _armed(self, repo):
        state = _make_state()
        state, evt = _play_event_from_hand(state, repo, "TWI", "103")
        return state, evt

    def test_TWI_103_arms_a_phase_scoped_aura_source(self, repo):
        state, evt = self._armed(repo)
        assert evt.instance_id in state.game_memory.phase_aura_sources

    def _defeat(self, state, ci, controller_id):
        """Defeat through the real engine path (the aura matches the dying unit
        against its target, which needs the unit's genuine leaving-play state)."""
        from swu.engine.actions import _defeat_unit
        _defeat_unit(state, state.player_by_id(controller_id), ci)
        return state

    def test_TWI_103_defeated_friendly_unit_deals_2_to_an_enemy_unit(self, repo):
        state, _evt = self._armed(repo)
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._defeat(state, mine, "P0")
        # The grant is mandatory; only enemy units are candidates.
        assert _target_ids(state) == {enemy.instance_id}
        state = _choose_target(state, enemy.instance_id)
        assert state.find_instance(enemy.instance_id)[1].damage == 2

    def test_TWI_103_does_not_grant_to_enemy_units(self, repo):
        """"each FRIENDLY unit" — an opposing unit's defeat grants nothing."""
        state, _evt = self._armed(repo)
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = self._defeat(state, theirs, "P1")
        assert state.pending_decisions == []

    def test_TWI_103_grant_expires_at_the_phase_rollover(self, repo):
        state, _evt = self._armed(repo)
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.clear_phase()          # "for this phase" ends here
        state = self._defeat(state, mine, "P0")
        assert state.pending_decisions == []


class TestOomSeriesOfficerTwi131:
    """TWI_131 — "When Defeated: Deal 2 damage to a base"."""

    def test_TWI_131_when_defeated_damages_a_chosen_base(self, repo):
        state = _make_state()
        officer = _place(state, "P0", _get_card(repo, "TWI", "131"), "ground")
        state = _defeat_and_fire(state, officer, "P0")
        enemy_base = state.player_by_id("P1").base_instance
        # Either base is a legal target ("a base" is unrestricted).
        assert enemy_base.instance_id in _target_ids(state)
        state = _choose_target(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_instance.damage == 2
        assert state.player_by_id("P0").base_instance.damage == 0


class TestSelfDestructTwi140:
    """TWI_140 — "Defeat a friendly unit.  If you do, deal 4 damage to a unit"."""

    def test_TWI_140_defeats_a_friendly_unit_then_burns_a_chosen_unit(self, repo):
        state = _make_state()
        fodder = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "140")
        # Step 1 — only friendly units may be sacrificed.
        assert _target_ids(state) == {fodder.instance_id}
        state = _choose_target(state, fodder.instance_id)
        assert fodder.instance_id not in {
            c.instance_id for c in state.player_by_id("P0").ground_arena}
        # Step 2 — "a unit", either side.
        state = _choose_target(state, enemy.instance_id)
        assert state.find_instance(enemy.instance_id)[1].damage == 4

    def test_TWI_140_fizzles_with_no_friendly_unit_to_defeat(self, repo):
        """No sacrifice ⇒ no "if you do" ⇒ the enemy unit takes nothing."""
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "140")
        while state.pending_decisions:
            acts = _target_ids(state)
            assert enemy.instance_id not in acts
            from swu.engine.actions import legal_actions, apply
            state = apply(state, legal_actions(state)[0])
        assert state.find_instance(enemy.instance_id)[1].damage == 0


class TestSteelaGerreraTwi146:
    """TWI_146 — "When Played/When Defeated: You may deal 2 damage to your base.  If
    you do, search the top 8 cards of your deck for a Tactic card, reveal it, and
    draw it"."""

    def _stock_deck(self, state, repo):
        """Top 8: one Tactic (Self-Destruct TWI_140) buried under filler."""
        from tests.test_sor_cards import _push_deck_top
        for _ in range(5):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        _push_deck_top(state, "P0", _get_card(repo, "TWI", "140"))
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))

    def test_TWI_146_when_played_pays_2_base_damage_to_dig_for_a_tactic(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        self._stock_deck(state, repo)
        steela = _place(state, "P0", _get_card(repo, "TWI", "146"), "ground")
        state = _fire_when_played(state, steela)
        state = _accept(state)
        assert state.player_by_id("P0").base_instance.damage == 2
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        # Only the Tactic among the top 8 is offered.
        assert len(picks) == 1
        state = apply(state, picks[0])
        hand_names = {c.card_def.name for c in state.player_by_id("P0").hand}
        assert "Self-Destruct" in hand_names

    def test_TWI_146_when_defeated_offers_the_same_dig(self, repo):
        state = _make_state()
        self._stock_deck(state, repo)
        steela = _place(state, "P0", _get_card(repo, "TWI", "146"), "ground")
        state = _defeat_and_fire(state, steela, "P0")
        state = _accept(state)
        assert state.player_by_id("P0").base_instance.damage == 2
        assert state.pending_decisions[-1].kind == "deck_search"

    def test_TWI_146_is_declinable(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        self._stock_deck(state, repo)
        steela = _place(state, "P0", _get_card(repo, "TWI", "146"), "ground")
        state = _fire_when_played(state, steela)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").base_instance.damage == 0
        assert state.pending_decisions == []


class TestLowAltitudeGunshipTwi149:
    """TWI_149 — "When Played: Choose an enemy unit.  Deal 1 damage to it for each
    friendly Republic unit"."""

    def test_TWI_149_scales_with_friendly_republic_units(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # Republic
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # Republic
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # Imperial
        _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")   # ENEMY Republic
        gunship = _place(state, "P0", _get_card(repo, "TWI", "149"), "space")
        state = _fire_when_played(state, gunship)
        state = _choose_target(state, enemy.instance_id)
        # 2 clone troopers + the gunship itself; the Imperial and the enemy
        # Republic unit do not count.
        assert state.find_instance(enemy.instance_id)[1].damage == 3

    def test_TWI_149_counts_only_itself_on_an_empty_board(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        gunship = _place(state, "P0", _get_card(repo, "TWI", "149"), "space")
        state = _fire_when_played(state, gunship)
        state = _choose_target(state, enemy.instance_id)
        assert state.find_instance(enemy.instance_id)[1].damage == 1


class TestSawGerreraTwi150:
    """TWI_150 — "On Attack: If your base has 15 or more damage on it, deal 1 damage
    to each enemy ground unit"."""

    def test_TWI_150_sweeps_enemy_ground_units_when_your_base_is_wrecked(self, repo):
        state = _make_state()
        saw = _place(state, "P0", _get_card(repo, "TWI", "150"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").base_instance.damage = 15
        state = _fire_on_attack(state, saw, ground)
        assert state.find_instance(ground.instance_id)[1].damage == 1
        assert state.find_instance(space.instance_id)[1].damage == 0
        assert state.find_instance(mine.instance_id)[1].damage == 0

    def test_TWI_150_is_silent_below_15_base_damage(self, repo):
        state = _make_state()
        saw = _place(state, "P0", _get_card(repo, "TWI", "150"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").base_instance.damage = 14
        state = _fire_on_attack(state, saw, ground)
        assert state.find_instance(ground.instance_id)[1].damage == 0
        assert state.pending_decisions == []


class TestResoluteTwi151:
    """TWI_151 — "costs 1 resource less to play for every 5 damage on your base";
    "When Played/On Attack: Deal 2 damage to an enemy unit and each other enemy unit
    with the same name as that unit"."""

    def _cost_paid(self, repo, base_damage):
        """Play Resolute from hand with ``base_damage`` on your base; return the
        number of resources the play exhausted."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = base_damage
        ci = CardInstance("P0_resolute", _get_card(repo, "TWI", "151"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        _give_resources(state, "P0", 20)
        state = apply(state, PlayCard(ci.instance_id))
        return sum(1 for r in state.player_by_id("P0").resources if r.exhausted)

    def test_TWI_151_costs_1_less_per_5_damage_on_your_base(self, repo):
        full = self._cost_paid(repo, 0)
        assert self._cost_paid(repo, 4) == full        # 4 // 5 == 0
        assert self._cost_paid(repo, 5) == full - 1
        assert self._cost_paid(repo, 12) == full - 2   # 12 // 5 == 2
        assert self._cost_paid(repo, 25) == full - 5

    def test_TWI_151_when_played_hits_every_enemy_unit_of_that_name(self, repo):
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        other = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        friendly_twin = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        resolute = _place(state, "P0", _get_card(repo, "TWI", "151"), "space")
        state = _fire_when_played(state, resolute)
        state = _choose_target(state, a.instance_id)
        # Same name, either arena — but only enemy units, and never a differently
        # named one.
        assert state.find_instance(a.instance_id)[1].damage == 2
        assert state.find_instance(b.instance_id)[1].damage == 2
        assert state.find_instance(other.instance_id)[1].damage == 0
        assert state.find_instance(friendly_twin.instance_id)[1].damage == 0

    def test_TWI_151_on_attack_repeats_the_strike(self, repo):
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        resolute = _place(state, "P0", _get_card(repo, "TWI", "151"), "space")
        state = _fire_on_attack(state, resolute, a)
        state = _choose_target(state, a.instance_id)
        assert state.find_instance(a.instance_id)[1].damage == 2
        assert state.find_instance(b.instance_id)[1].damage == 2


# ── twi-set:04 — Direct damage & removal ──────────────────────────────────────


def _decline(state):
    from swu.engine.actions import legal_actions, apply, DeclineTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, DeclineTrigger)))


class TestMisterBonesTwi154:
    """TWI_154 — "On Attack: If you have no cards in your hand, you may deal 3
    damage to a ground unit"."""

    def _attack(self, repo, hand_cards):
        state = _make_state()
        bones = _place(state, "P0", _get_card(repo, "TWI", "154"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        for _ in range(hand_cards):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        return _fire_on_attack(state, bones, target), target

    def test_TWI_154_empty_hand_offers_3_damage_to_a_ground_unit(self, repo):
        state, target = self._attack(repo, 0)
        state = _accept(state)
        state = _choose_target(state, target.instance_id)
        assert state.find_instance(target.instance_id)[1].damage == 3

    def test_TWI_154_silent_with_a_card_in_hand(self, repo):
        state, target = self._attack(repo, 1)
        assert state.pending_decisions == []
        assert state.find_instance(target.instance_id)[1].damage == 0

    def test_TWI_154_only_ground_units_are_candidates(self, repo):
        state = _make_state()
        bones = _place(state, "P0", _get_card(repo, "TWI", "154"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, bones, ground)
        state = _accept(state)
        ids = _target_ids(state)
        assert ground.instance_id in ids and space.instance_id not in ids


class TestTwiceThePrideTwi155:
    """TWI_155 — "When Played: Deal 2 damage to attached unit"."""

    def test_TWI_155_damages_its_own_host_on_attach(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "155"), "P0")
        state = _fire_upgrade_played(state, up, host)
        assert state.find_instance(host.instance_id)[1].damage == 2

    def test_TWI_155_hits_an_enemy_host_too(self, repo):
        """The upgrade damages whatever it is attached to, not "a friendly unit"."""
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "155"), "P0")
        state = _fire_upgrade_played(state, up, host)
        assert state.find_instance(host.instance_id)[1].damage == 2


class TestUnlimitedPowerTwi156:
    """TWI_156 — "Deal 4 damage to a unit, 3 to a second, 2 to a third, and 1 to a
    fourth.  (All damage is dealt simultaneously.)"."""

    def test_TWI_156_hits_four_distinct_units_for_4_3_2_1(self, repo):
        state = _make_state()
        units = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                 for _ in range(4)]
        state, _evt = _play_event_from_hand(state, repo, "TWI", "156", resources=20)
        for u in units:
            # Each already-chosen unit drops out of the next step's candidates.
            assert u.instance_id in _target_ids(state)
            state = _choose_target(state, u.instance_id)
        damages = [state.find_instance(u.instance_id)[1].damage for u in units]
        assert damages == [4, 3, 2, 1]

    def test_TWI_156_damage_lands_simultaneously(self, repo):
        """A unit killed by the 4 is still a *distinct* earlier target — the later
        choices are made before any damage is applied, so all four still land."""
        state = _make_state()
        frail = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        others = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                  for _ in range(3)]
        state, _evt = _play_event_from_hand(state, repo, "TWI", "156", resources=20)
        state = _choose_target(state, frail.instance_id)
        # The doomed unit is still on the board while the rest are chosen.
        assert frail.instance_id in {
            c.instance_id for c in state.player_by_id("P1").ground_arena}
        for u in others:
            state = _choose_target(state, u.instance_id)
        assert frail.instance_id not in {
            c.instance_id for c in state.player_by_id("P1").ground_arena}
        assert [state.find_instance(u.instance_id)[1].damage for u in others] == [3, 2, 1]

    def test_TWI_156_fizzles_the_extra_steps_with_fewer_units(self, repo):
        state = _make_state()
        only = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "156", resources=20)
        state = _choose_target(state, only.instance_id)
        assert state.find_instance(only.instance_id)[1].damage == 4
        assert state.pending_decisions == []


class TestDisaffectedSenatorTwi157:
    """TWI_157 — "Action [2 resources, Exhaust]: Deal 2 damage to a base"."""

    def test_TWI_157_action_burns_a_base_for_2(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "157"), "ground")
        senator.exhausted = False
        _give_resources(state, "P0", 5)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == senator.instance_id)
        state = apply(state, act)
        enemy_base = state.player_by_id("P1").base_instance
        state = _choose_target(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_instance.damage == 2
        assert state.find_instance(senator.instance_id)[1].exhausted
        assert sum(1 for r in state.player_by_id("P0").resources if r.exhausted) == 2

    def test_TWI_157_unavailable_without_2_resources(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "157"), "ground")
        senator.exhausted = False
        _give_resources(state, "P0", 1)
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility)
                    and a.source_id == senator.instance_id]


class TestVanguardDroidBomberTwi160:
    """TWI_160 — "When Played: If you control another Separatist unit, deal 2 damage
    to an enemy base"."""

    def test_TWI_160_burns_the_enemy_base_with_separatist_backup(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "131"), "ground")   # Separatist
        bomber = _place(state, "P0", _get_card(repo, "TWI", "160"), "space")
        state = _fire_when_played(state, bomber)
        enemy_base = state.player_by_id("P1").base_instance
        # "an ENEMY base" — the controller's own base is never a candidate.
        assert _target_ids(state) == {enemy_base.instance_id}
        state = _choose_target(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_TWI_160_does_not_count_itself(self, repo):
        """"ANOTHER Separatist unit" — the bomber is Separatist, but alone it is not
        enough."""
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "TWI", "160"), "space")
        state = _fire_when_played(state, bomber)
        assert state.pending_decisions == []
        assert state.player_by_id("P1").base_instance.damage == 0


class TestRecklessTorrentTwi162:
    """TWI_162 — "Coordinate — When Played: You may deal 2 damage to a friendly unit
    and 2 damage to an enemy unit in the same arena"."""

    def _played(self, repo, extra_friendly=2):
        state = _make_state()
        for _ in range(extra_friendly):
            _filler(state, "P0", repo)
        torrent = _place(state, "P0", _get_card(repo, "TWI", "162"), "space")
        return state, torrent

    def test_TWI_162_pairs_a_friendly_and_enemy_hit_in_one_arena(self, repo):
        state, torrent = self._played(repo)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        enemy_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        enemy_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, torrent)
        state = _accept(state)
        state = _choose_target(state, friendly.instance_id)
        # Only the enemy unit sharing the chosen unit's arena is a candidate.
        assert _target_ids(state) == {enemy_space.instance_id}
        state = _choose_target(state, enemy_space.instance_id)
        assert state.find_instance(friendly.instance_id)[1].damage == 2
        assert state.find_instance(enemy_space.instance_id)[1].damage == 2
        assert state.find_instance(enemy_ground.instance_id)[1].damage == 0

    def test_TWI_162_needs_coordinate(self, repo):
        state, torrent = self._played(repo, extra_friendly=0)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_when_played(state, torrent)
        assert state.pending_decisions == []

    def test_TWI_162_is_declinable(self, repo):
        state, torrent = self._played(repo)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        state = _fire_when_played(state, torrent)
        state = _decline(state)
        assert state.find_instance(friendly.instance_id)[1].damage == 0


class TestKitFistoTwi165:
    """TWI_165 — "Coordinate — On Attack: You may deal 3 damage to a ground unit"."""

    def test_TWI_165_coordinate_on_attack_burns_a_ground_unit(self, repo):
        state = _make_state()
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        kit = _place(state, "P0", _get_card(repo, "TWI", "165"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, kit, victim)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        assert state.find_instance(victim.instance_id)[1].damage == 3

    def test_TWI_165_silent_below_three_units(self, repo):
        state = _make_state()
        kit = _place(state, "P0", _get_card(repo, "TWI", "165"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, kit, victim)
        assert state.pending_decisions == []
        assert state.find_instance(victim.instance_id)[1].damage == 0


# ── twi-set:05 — Direct damage & removal ─────────────────────────────────────


def _mill_top(state, owner_id, card_def):
    """Put ``card_def`` on top of a player's deck (the next card milled/drawn)."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:5]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DECK,
    )
    state.player_by_id(owner_id).deck.insert(0, ci)
    return ci


def _board_damage(state):
    """Total damage marked on every unit and base in play."""
    total = 0
    for p in state.players:
        for u in p.ground_arena + p.space_arena:
            total += u.damage
        if p.base_instance is not None:
            total += p.base_instance.damage
    return total


class TestHeavyPersuaderTankTwi167:
    """TWI_167 — Exploit 2 (keyword engine) + "When Played: You may deal 2 damage to
    a ground unit"."""

    def test_TWI_167_when_played_may_burn_a_ground_unit(self, repo):
        state = _make_state()
        tank = _place(state, "P0", _get_card(repo, "TWI", "167"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, tank)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        assert state.find_instance(victim.instance_id)[1].damage == 2

    def test_TWI_167_may_decline_the_damage(self, repo):
        state = _make_state()
        tank = _place(state, "P0", _get_card(repo, "TWI", "167"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, tank)
        state = _decline(state)
        assert state.find_instance(victim.instance_id)[1].damage == 0


class TestBloodSportTwi173:
    """TWI_173 — "Deal 2 damage to each ground unit"."""

    def test_TWI_173_hits_every_ground_unit_on_both_sides(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spacer = _place(state, "P1", _get_card(repo, "TWI", "58"), "space")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "173", resources=10)
        assert state.pending_decisions == []            # no prompt — fixed targets
        assert state.find_instance(mine.instance_id)[1].damage == 2
        assert state.find_instance(theirs.instance_id)[1].damage == 2
        assert state.find_instance(spacer.instance_id)[1].damage == 0


class TestGuerillaInsurgencyTwi177:
    """TWI_177 — "Each player defeats a resource they control and discards 2 cards
    from their hand.  Deal 4 damage to each ground unit"."""

    def _played(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
            _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        _give_resources(state, "P1", 4)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "177", resources=20)
        return state, mine, theirs

    def test_TWI_177_defeats_a_resource_each_and_burns_the_ground(self, repo):
        state, mine, theirs = self._played(repo)
        # 20 given, minus the one defeated by the event (playing it only exhausts).
        assert len(state.player_by_id("P0").resources) == 19
        assert len(state.player_by_id("P1").resources) == 3
        assert state.find_instance(mine.instance_id)[1].damage == 4
        assert state.find_instance(theirs.instance_id)[1].damage == 4

    def test_TWI_177_each_player_discards_two_of_their_choice(self, repo):
        from swu.engine.actions import (legal_actions, apply,
                                        SelectExcessHandCardToDiscard)
        state, _mine, _theirs = self._played(repo)
        assert state.pending_decisions[-1].kind == "discard_excess_from_hand"
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        seen = []
        while (state.pending_decisions
               and state.pending_decisions[-1].kind == "discard_excess_from_hand"):
            seen.append(state.pending_decisions[-1].deciding_player_id)
            act = next(a for a in legal_actions(state)
                       if isinstance(a, SelectExcessHandCardToDiscard))
            state = apply(state, act)
        # Two picks each, the controller first — "each player discards 2 cards".
        assert seen == ["P0", "P0", "P1", "P1"]
        assert len(state.player_by_id("P0").hand) == 1
        assert len(state.player_by_id("P1").hand) == 1
        assert len(state.player_by_id("P0").discard) >= 2


class TestSabineWrenTwi195:
    """TWI_195 — "While this unit is exhausted, she can't be attacked (unless she
    gains Sentinel)" + "On Attack: You may discard a card from your deck.  If it
    doesn't share an aspect with your base, deal 2 damage to a ground unit"."""

    def _face_off(self, repo):
        """P0 attacker vs an enemy Sabine, both ready."""
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        sabine = _place(state, "P1", _get_card(repo, "TWI", "195"), "ground")
        sabine.exhausted = False
        return state, attacker, sabine

    def _attacks_on(self, state, attacker, target):
        from swu.engine.actions import legal_actions, AttackWithUnit
        return [a for a in legal_actions(state)
                if isinstance(a, AttackWithUnit)
                and a.attacker_id == attacker.instance_id
                and a.defender_id == target.instance_id]

    def _base_attacks(self, state, attacker):
        from swu.engine.actions import legal_actions, AttackWithUnit
        return [a for a in legal_actions(state)
                if isinstance(a, AttackWithUnit)
                and a.attacker_id == attacker.instance_id
                and a.defender_id is None]

    def test_TWI_195_cannot_be_attacked_while_exhausted(self, repo):
        state, attacker, sabine = self._face_off(repo)
        assert self._attacks_on(state, attacker, sabine)      # ready → attackable
        sabine.exhausted = True
        assert not self._attacks_on(state, attacker, sabine)
        assert self._base_attacks(state, attacker)            # the base still is

    def test_TWI_195_sentinel_overrides_the_exhausted_protection(self, repo):
        from swu.engine.state import Modifier
        state, attacker, sabine = self._face_off(repo)
        sabine.exhausted = True
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=sabine.instance_id,
            target_instance_id=sabine.instance_id,
            kind="keyword_grant",
            value={"keyword": "Sentinel", "value": 0},
            duration="this_phase",
        ))
        assert self._attacks_on(state, attacker, sabine)
        # And, being attackable again, she forces the attack as a Sentinel.
        assert not self._base_attacks(state, attacker)

    def test_TWI_195_on_attack_mills_and_burns_an_off_aspect_card(self, repo):
        state = _make_state()
        sabine = _place(state, "P0", _get_card(repo, "TWI", "195"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        milled = _mill_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_on_attack(state, sabine)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        assert state.find_instance(victim.instance_id)[1].damage == 2
        ps = state.player_by_id("P0")
        assert milled.instance_id in {c.instance_id for c in ps.discard}
        assert milled.instance_id not in {c.instance_id for c in ps.deck}

    def test_TWI_195_no_damage_when_the_milled_card_shares_a_base_aspect(self, repo):
        from dataclasses import replace
        state = _make_state()
        sabine = _place(state, "P0", _get_card(repo, "TWI", "195"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        stormtrooper = _get_card(repo, "SOR", "128")   # Villainy / Aggression
        _mill_top(state, "P0", stormtrooper)
        base = state.player_by_id("P0").base_instance
        base.card_def = replace(base.card_def, aspects=stormtrooper.aspects)
        state = _fire_on_attack(state, sabine)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        assert state.find_instance(victim.instance_id)[1].damage == 0
        assert len(state.player_by_id("P0").discard) == 1   # still milled


class TestJarJarBinksTwi202:
    """TWI_202 — "On Attack: Deal 2 damage to a random unit or base"."""

    def test_TWI_202_deals_2_to_a_random_unit_or_base(self, repo):
        state = _make_state()
        jar_jar = _place(state, "P0", _get_card(repo, "TWI", "202"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, jar_jar)
        assert state.pending_decisions == []      # nobody chooses — it is random
        assert _board_damage(state) == 2

    def test_TWI_202_random_pick_is_seeded_and_reproducible(self, repo):
        import copy
        state = _make_state()
        jar_jar = _place(state, "P0", _get_card(repo, "TWI", "202"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        def _victim(s):
            s = _fire_on_attack(copy.deepcopy(s), jar_jar)
            hits = [c.instance_id for p in s.players
                    for c in (p.ground_arena + p.space_arena) if c.damage]
            if s.player_by_id("P0").base_instance.damage:
                hits.append("P0_base")
            if s.player_by_id("P1").base_instance.damage:
                hits.append("P1_base")
            return hits

        assert _victim(state) == _victim(state)


class TestFreelanceAssassinTwi212:
    """TWI_212 — "When Played: You may pay 2 resources.  If you do, deal 2 damage to
    a unit"."""

    def test_TWI_212_pays_two_resources_to_deal_2(self, repo):
        state = _make_state()
        assassin = _place(state, "P0", _get_card(repo, "TWI", "212"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 4)
        state = _fire_when_played(state, assassin)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        assert state.find_instance(victim.instance_id)[1].damage == 2
        assert _ready_resources(state, "P0") == 2

    def test_TWI_212_not_offered_without_two_ready_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        assassin = _place(state, "P0", _get_card(repo, "TWI", "212"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 1)
        state = _fire_when_played(state, assassin)
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert state.find_instance(victim.instance_id)[1].damage == 0


class TestExecuteOrder66Twi239:
    """TWI_239 — "Deal 6 damage to each Jedi unit.  For each unit defeated this way,
    its controller creates a Clone Trooper token"."""

    def _tokens(self, state, pid):
        return [u for u in state.player_by_id(pid).ground_arena
                if u.card_def.display_name == "Clone Trooper"]

    def test_TWI_239_wipes_jedi_and_pays_their_controllers_a_token(self, repo):
        state = _make_state()
        my_jedi = _place(state, "P0", _get_card(repo, "LOF", "94"), "ground")   # 1/4
        their_jedi = _place(state, "P1", _get_card(repo, "LOF", "94"), "ground")
        bystander = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "239", resources=10)
        assert state.find_instance(my_jedi.instance_id) is None or \
            my_jedi.instance_id not in {u.instance_id
                                        for u in state.player_by_id("P0").ground_arena}
        assert their_jedi.instance_id not in {
            u.instance_id for u in state.player_by_id("P1").ground_arena}
        # Non-Jedi are untouched — "each JEDI unit".
        assert state.find_instance(bystander.instance_id)[1].damage == 0
        assert len(self._tokens(state, "P0")) == 1
        assert len(self._tokens(state, "P1")) == 1

    def test_TWI_239_a_surviving_jedi_makes_no_token(self, repo):
        state = _make_state()
        tough = _place(state, "P1", _get_card(repo, "LOF", "49"), "ground")  # 4/8
        state, _evt = _play_event_from_hand(state, repo, "TWI", "239", resources=10)
        assert state.find_instance(tough.instance_id)[1].damage == 6
        assert self._tokens(state, "P1") == []


class TestHoldOutBlasterTwi256:
    """TWI_256 — "When Played: You may have attached unit deal 1 damage to a ground
    unit"."""

    def _armed(self, repo, host_owner="P0"):
        state = _make_state()
        host = _place(state, host_owner, _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(
            state, host, _get_card(repo, "TWI", "256"), "P0")
        return state, host, up

    def test_TWI_256_deals_1_to_a_chosen_ground_unit(self, repo):
        state, host, up = self._armed(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, up, host)
        state = _accept(state)
        state = _choose_target(state, enemy.instance_id)
        assert state.find_instance(enemy.instance_id)[1].damage == 1
        assert state.find_instance(host.instance_id)[1].damage == 0

    def test_TWI_256_may_decline_and_only_ground_units_are_candidates(self, repo):
        state, host, up = self._armed(repo)
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_upgrade_played(state, up, host)
        state = _accept(state)
        ids = _target_ids(state)
        assert ground.instance_id in ids and space.instance_id not in ids
        # "a ground unit" is not restricted to enemies — the host itself is legal.
        assert host.instance_id in ids

    def test_TWI_256_declining_the_may_deals_nothing(self, repo):
        state, host, up = self._armed(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, up, host)
        state = _decline(state)
        assert state.find_instance(enemy.instance_id)[1].damage == 0

    def test_TWI_256_damage_is_attributed_to_the_attached_unit(self, repo):
        """"Have ATTACHED UNIT deal" — the shot comes from the host, not the gun."""
        from swu.engine.events import DamageDealt
        state, host, up = self._armed(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, up, host)
        state = _accept(state)
        state = _choose_target(state, enemy.instance_id)
        hits = [e for e in state.event_log
                if isinstance(e, DamageDealt)
                and e.target_instance_id == enemy.instance_id]
        assert hits and hits[-1].source_name == host.card_def.display_name


# ── twi-set:07 — Card advantage & disruption ─────────────────────────────────

def _mark_unit_defeated_this_phase(state, controller_id="P1"):
    """Record that a unit controlled by ``controller_id`` was defeated this phase
    (the ledger both ANY_UNIT_DEFEATED_THIS_PHASE and ENEMY_UNIT_DEFEATED_THIS_PHASE
    read)."""
    state.game_memory.defeated_controllers_this_round.append(controller_id)


def _swap_base(state, owner_id, card_def):
    """Replace ``owner_id``'s Base instance with one of ``card_def`` (so a Base-side
    ability is registered on the board)."""
    from swu.engine.state import CardInstance, Zone
    from swu.cards.models import Base
    ps = state.player_by_id(owner_id)
    ps.base_zone = [ci for ci in ps.base_zone if not isinstance(ci.card_def, Base)]
    ci = CardInstance(
        instance_id=f"{owner_id}_base_twi",
        card_def=card_def, owner_id=owner_id, zone=Zone.BASE_ZONE,
    )
    ps.base_zone.insert(0, ci)
    return ci


def _fire_leader_deployed(state, leader_ci):
    """Fire the LeaderDeployed event for ``leader_ci`` (the deploy trigger site)."""
    from swu.engine.events import LeaderDeployed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = LeaderDeployed(
        player_id=leader_ci.owner_id,
        instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name,
        arena="Ground",
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _fire_regroup_start(state):
    """Fire the "regroup phase starts" PhaseStartTrigger site."""
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    evt = PhaseChanged(new_phase="REGROUP", round_number=state.round_number)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _stack_deck(state, owner_id, card_defs):
    """Put ``card_defs`` on top of ``owner_id``'s deck, first one on top."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    for cd in reversed(card_defs):
        ps.deck.insert(0, CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
            card_def=cd, owner_id=owner_id, zone=Zone.DECK,
        ))


class TestYodaTwi4:
    """TWI_4 — Yoda, Sensing Darkness.  Undeployed "Action [Exhaust]: If a unit left
    play this phase, draw a card, then put a card from your hand on the top or bottom
    of your deck"; deployed "When Deployed: You may discard a card from your deck.  If
    you do, defeat an enemy non-leader unit that costs the same as or less than the
    discarded card"."""

    def _use(self, state, leader_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        return apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id))

    def test_TWI_4_action_is_offered_only_after_a_unit_left_play(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        yoda = _place_leader(state, "P0", _get_card(repo, "TWI", "4"))
        _add_deck_cards(state, "P0", repo, 3)
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))

        def _offered(s):
            return any(isinstance(a, UseAbility) and a.source_id == yoda.instance_id
                       for a in legal_actions(s))

        assert _offered(state) is False        # nothing has left play yet
        _mark_unit_defeated_this_phase(state, "P0")   # "a unit" — either side's
        assert _offered(state) is True

    def test_TWI_4_draws_then_puts_a_hand_card_on_top_or_bottom(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectHandCardToBottom, SelectHandCardToTop)
        state = _make_state()
        yoda = _place_leader(state, "P0", _get_card(repo, "TWI", "4"))
        _add_deck_cards(state, "P0", repo, 3)
        held = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _mark_unit_defeated_this_phase(state)

        state = self._use(state, yoda)
        # Drew 1 (hand 2), and now must place one of them back on the deck.
        assert len(state.player_by_id("P0").hand) == 2
        acts = legal_actions(state)
        assert {a.instance_id for a in acts if isinstance(a, SelectHandCardToBottom)} \
            == {c.instance_id for c in state.player_by_id("P0").hand}
        # The new allow_top option offers each card in BOTH placements.
        top_act = next(a for a in acts if isinstance(a, SelectHandCardToTop)
                       and a.instance_id == held.instance_id)
        state = apply(state, top_act)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 1
        assert ps.deck[0].instance_id == held.instance_id   # it went on TOP
        assert not state.pending_decisions

    def test_TWI_4_when_deployed_mills_then_defeats_a_cheap_enough_enemy(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects, ChooseTarget)
        state = _make_state()
        yoda = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "4"))
        # Mill a cost-3 card; SOR_46 (cost 3) is defeatable, SOR_51 (cost 6) is not.
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "46")])
        cheap = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        pricey = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_leader_deployed(state, yoda)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AutoResolveEffects)))
        assert len(state.player_by_id("P0").discard) == 1      # the milled card
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {cheap.instance_id}, (
            "only enemy non-leader units at or below the discarded card's cost")
        assert friendly.instance_id not in offered
        assert pricey.instance_id not in offered
        state = apply(state, ChooseTarget(cheap.instance_id))
        assert state.find_instance(cheap.instance_id)[1].zone.name == "DISCARD"

    def test_TWI_4_when_deployed_declined_discards_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        yoda = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "4"))
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "46")])
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_leader_deployed(state, yoda)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").discard == []
        assert state.find_instance(enemy.instance_id)[1].zone.name == "GROUND_ARENA"


class TestPadmeAmidalaTwi8:
    """TWI_8 — Padmé Amidala, Serving the Republic.  Both sides: "Coordinate —
    Search the top 3 cards of your deck for a Republic card, reveal it, and draw
    it"."""

    def test_TWI_8_action_needs_coordinate_and_draws_a_republic_card(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, SelectSearchCard)
        state = _make_state()
        padme = _place_leader(state, "P0", _get_card(repo, "TWI", "8"))
        _give_resources(state, "P0", 3)
        republic = _get_card(repo, "TWI", "35")      # Imperial/Official — NOT Republic
        assert "Republic" not in (republic.traits or ())
        target = _get_card(repo, "TWI", "47")        # Satine Kryze — Mandalorian
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "128")] * 3)

        def _offered(s):
            return any(isinstance(a, UseAbility) and a.source_id == padme.instance_id
                       for a in legal_actions(s))

        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert _offered(state) is False               # Coordinate: only 2 units
        _filler(state, "P0", repo)
        assert _offered(state) is True                # 3 units

        # Put a real Republic card on top so the search finds one.
        _stack_deck(state, "P0", [_get_card(repo, "TWI", "11")])   # Ahsoka — Republic
        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == padme.instance_id))
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert len(picks) == 1, "only the Republic card in the top 3 is a candidate"
        state = apply(state, picks[0])
        assert any(c.card_def.display_name.startswith("Ahsoka")
                   for c in state.player_by_id("P0").hand)

    def test_TWI_8_on_attack_searches_only_with_coordinate(self, repo):
        state = _make_state()
        padme = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "8"))
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "128")] * 3)
        state = _fire_on_attack(state, padme)
        assert not state.pending_decisions, "below 3 units the trigger isn't collected"

        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                    # +Padmé herself = 3 units
        state = _fire_on_attack(state, padme)
        assert state.pending_decisions[-1].kind == "deck_search"


class TestShadowCollectiveCampTwi25:
    """TWI_25 — Shadow Collective Camp (Base): "When you deploy a leader: Draw a
    card"."""

    def test_TWI_25_draws_when_its_owner_deploys_a_leader(self, repo):
        state = _make_state()
        _swap_base(state, "P0", _get_card(repo, "TWI", "25"))
        _add_deck_cards(state, "P0", repo, 3)
        leader = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "4"))
        before = len(state.player_by_id("P0").hand)
        state = _fire_leader_deployed(state, leader)
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_TWI_25_ignores_an_opponents_leader_deploy(self, repo):
        state = _make_state()
        _swap_base(state, "P0", _get_card(repo, "TWI", "25"))
        _add_deck_cards(state, "P0", repo, 3)
        enemy_leader = _place_deployed_leader(state, "P1", _get_card(repo, "TWI", "4"))
        before = len(state.player_by_id("P0").hand)
        state = _fire_leader_deployed(state, enemy_leader)
        assert len(state.player_by_id("P0").hand) == before, (
            "'when YOU deploy a leader' — the observer is controller-scoped")


class TestMorganElsbethTwi35:
    """TWI_35 — "On Attack: You may defeat another friendly unit.  If you do, draw a
    card"."""

    def test_TWI_35_defeats_another_friendly_unit_and_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        morgan = _place(state, "P0", _get_card(repo, "TWI", "35"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_deck_cards(state, "P0", repo, 2)

        state = _fire_on_attack(state, morgan)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {friend.instance_id}, (
            "'another friendly unit' — not Morgan herself, not the enemy")
        assert enemy.instance_id not in offered
        state = apply(state, ChooseTarget(friend.instance_id))
        assert state.find_instance(friend.instance_id)[1].zone.name == "DISCARD"
        assert len(state.player_by_id("P0").hand) == 1

    def test_TWI_35_declining_defeats_nothing_and_draws_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        morgan = _place(state, "P0", _get_card(repo, "TWI", "35"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_deck_cards(state, "P0", repo, 2)
        state = _fire_on_attack(state, morgan)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.find_instance(friend.instance_id)[1].zone.name == "GROUND_ARENA"
        assert state.player_by_id("P0").hand == []


class TestAFineAdditionTwi40:
    """TWI_40 — "If an enemy unit was defeated this phase, play an upgrade from your
    hand or from any player's discard pile, ignoring its aspect penalty"."""

    def _setup(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # a host
        hand_upgrade = _put_in_hand(state, "P0", _get_card(repo, "SOR", "69"))
        # An upgrade sitting in the OPPONENT's discard pile.
        from swu.engine.state import CardInstance, Zone
        foreign = CardInstance(
            instance_id="P1_disc_up", card_def=_get_card(repo, "SOR", "120"),
            owner_id="P1", zone=Zone.DISCARD,
        )
        state.player_by_id("P1").discard.append(foreign)
        return state, hand_upgrade, foreign

    def test_TWI_40_does_nothing_unless_an_enemy_unit_was_defeated(self, repo):
        state, _hand_upgrade, _foreign = self._setup(repo)
        # The event itself costs 0 + 4 aspect penalty here; 1 resource is left over.
        state, _evt = _play_event_from_hand(state, repo, "TWI", "40",
                                            owner="P0", resources=5)
        assert not state.pending_decisions, (
            "the leading 'If an enemy unit was defeated this phase' gate")

    def test_TWI_40_offers_hand_and_any_discard_ignoring_the_aspect_penalty(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        # Exactly 1 resource: SOR_69 Resilient costs 1 but carries an unmatched
        # Vigilance pip (+2) against this base — only the waived penalty makes it
        # affordable at all.
        state, hand_upgrade, foreign = self._setup(repo)
        _mark_unit_defeated_this_phase(state, "P1")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "40",
                                            owner="P0", resources=5)
        assert state.pending_decisions[-1].kind == "play_upgrade_from_hand"
        offered = {a.upgrade_id for a in legal_actions(state)
                   if isinstance(a, PlayUpgradeFromHand)}
        assert hand_upgrade.instance_id in offered, "from your hand"
        assert foreign.instance_id not in offered, (
            "SOR_120 costs 2 + an unmatched pip — unaffordable on 1 resource")

        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayUpgradeFromHand)
                   and a.upgrade_id == hand_upgrade.instance_id)
        state = apply(state, act)
        host = state.find_instance(act.host_id)[1]
        assert hand_upgrade.instance_id in {u.instance_id
                                            for u in host.attached_upgrades}
        assert state.player_by_id("P0").available_resources == 0

    def test_TWI_40_can_play_an_upgrade_out_of_an_opponents_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        state, _hand_upgrade, foreign = self._setup(repo)
        _mark_unit_defeated_this_phase(state, "P1")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "40",
                                            owner="P0", resources=6)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayUpgradeFromHand)
                   and a.upgrade_id == foreign.instance_id)
        state = apply(state, act)
        host = state.find_instance(act.host_id)[1]
        assert foreign.instance_id in {u.instance_id for u in host.attached_upgrades}
        assert host.owner_id == "P0", "attached to a unit its new controller chose"
        assert state.player_by_id("P1").discard == [], "it left the opponent's discard"


class TestForesightTwi68:
    """TWI_68 — "Attached unit gains: 'When the regroup phase starts: Name a card,
    then look at the top card of your deck.  If it's the named card, you may reveal
    and draw it.'"  The name is chosen by the engine (the naming is information-free,
    so the optimal guess is the most numerous remaining name)."""

    def _armed(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "68"), "P0")
        return state, host

    def test_TWI_68_draws_the_top_card_when_the_guess_hits(self, repo):
        state, _host = self._armed(repo)
        # Two copies of SOR_128 (the modal name) with one on top ⇒ the guess hits.
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "128"),
                                  _get_card(repo, "SOR", "46"),
                                  _get_card(repo, "SOR", "128")])
        state = _fire_regroup_start(state)
        hand = state.player_by_id("P0").hand
        assert len(hand) == 1
        assert hand[0].card_def.display_name \
            == _get_card(repo, "SOR", "128").display_name

    def test_TWI_68_draws_nothing_when_the_top_card_is_not_the_named_one(self, repo):
        state, _host = self._armed(repo)
        # SOR_46 is a singleton on top; SOR_128 (x2) is the modal name that is named.
        _stack_deck(state, "P0", [_get_card(repo, "SOR", "46"),
                                  _get_card(repo, "SOR", "128"),
                                  _get_card(repo, "SOR", "128")])
        state = _fire_regroup_start(state)
        assert state.player_by_id("P0").hand == []
        assert len(state.player_by_id("P0").deck) == 3

# ── twi-set:07 residual — the aura-granted ACTIVATED ability seam ─────────────

class TestSatineKryzeTwi47:
    """TWI_47 — Satine Kryze: "Each unit (including enemy units) gains: 'Action
    [Exhaust]: Discard cards from an opponent's deck equal to half this unit's
    remaining HP, rounded up.'"

    The ``AuraGrantedAbility``-wrapping-an-``ActivatedAbility`` seam: one source
    arms MANY units, so each offer names both the source (the spec's address) and
    the ``actor_id`` (the unit using it)."""

    @staticmethod
    def _aura_actions(state, actor_id=None):
        from swu.engine.actions import legal_actions, UseAbility
        return [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.actor_id is not None
                and (actor_id is None or a.actor_id == actor_id)]

    def test_TWI_47_arms_every_unit_the_active_player_controls(self, repo):
        """The Action is offered once per unit its user controls — Satine herself
        included — and never for a unit the active player does not control."""
        state = _make_state()
        satine = _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        mine = _filler(state, "P0", repo)
        theirs = _filler(state, "P1", repo)
        _add_deck_cards(state, "P1", repo, 6)

        armed = {a.actor_id for a in self._aura_actions(state)}
        assert armed == {satine.instance_id, mine.instance_id}
        # Every offer addresses Satine's spec, not the acting unit's registry.
        assert all(a.source_id == satine.instance_id for a in self._aura_actions(state))

        # The enemy unit is armed too — but for ITS controller, on their turn.
        state.active_player_index = 1
        _add_deck_cards(state, "P0", repo, 6)
        assert {a.actor_id for a in self._aura_actions(state)} == {theirs.instance_id}

    def test_TWI_47_mills_half_remaining_hp_rounded_up_and_exhausts_the_actor(self, repo):
        """Satine is 0/6, so her own copy discards 3; the exhaust cost falls on the
        ACTING unit and the mill hits the actor's opponent."""
        from swu.engine.actions import apply
        state = _make_state()
        satine = _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        _add_deck_cards(state, "P1", repo, 6)

        act = self._aura_actions(state, satine.instance_id)[0]
        state = apply(state, act)

        p1 = state.player_by_id("P1")
        assert len(p1.deck) == 3 and len(p1.discard) == 3
        assert _find_instance(state, satine.instance_id).exhausted is True
        assert len(state.player_by_id("P0").deck) == 0     # own deck untouched
        # Exhausted, so the ability is no longer affordable for her.
        state.active_player_index = 0
        assert self._aura_actions(state, satine.instance_id) == []

    def test_TWI_47_mill_shrinks_as_the_acting_unit_takes_damage(self, repo):
        """"Half this unit's REMAINING HP" — 6 HP with 3 damage leaves 3, and 3
        halved and rounded up is 2."""
        from swu.engine.actions import apply
        state = _make_state()
        satine = _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        satine.damage = 3
        _add_deck_cards(state, "P1", repo, 6)

        state = apply(state, self._aura_actions(state, satine.instance_id)[0])
        assert len(state.player_by_id("P1").discard) == 2

    def test_TWI_47_an_enemy_unit_uses_it_against_satines_own_controller(self, repo):
        """"An opponent's deck" follows the ACTOR, so a unit Satine armed on the
        other side of the table mills Satine's controller."""
        from swu.engine.actions import apply
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _add_deck_cards(state, "P0", repo, 6)
        _add_deck_cards(state, "P1", repo, 6)
        state.active_player_index = 1

        state = apply(state, self._aura_actions(state, theirs.instance_id)[0])
        assert len(state.player_by_id("P0").discard) == 4   # ceil(7 / 2)
        assert len(state.player_by_id("P1").discard) == 0

    def test_TWI_47_grant_ends_when_satine_leaves_play(self, repo):
        """The aura is read off the board, so defeating Satine disarms everyone."""
        from swu.engine import actions as A
        state = _make_state()
        satine = _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        mine = _filler(state, "P0", repo)
        _add_deck_cards(state, "P1", repo, 6)
        assert self._aura_actions(state, mine.instance_id) != []

        A._defeat_unit(state, state.player_by_id("P0"), satine)
        assert self._aura_actions(state) == []

    def test_TWI_47_mill_stops_at_an_empty_deck(self, repo):
        """A deck shorter than the mill is emptied, not over-drawn."""
        from swu.engine.actions import apply
        state = _make_state()
        satine = _place(state, "P0", _get_card(repo, "TWI", "47"), "ground")
        _add_deck_cards(state, "P1", repo, 1)

        state = apply(state, self._aura_actions(state, satine.instance_id)[0])
        p1 = state.player_by_id("P1")
        assert p1.deck == [] and len(p1.discard) == 1

# ── twi-set:08 — card advantage & disruption ──────────────────────────────────

def _pick_bottom(state, instance_id):
    """Select one discard card in a pending bottom_from_discard decision."""
    from swu.engine.actions import legal_actions, apply, SelectBottomDiscardCard
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, SelectBottomDiscardCard)
                             and a.instance_id == instance_id))


def _finish_bottom(state):
    from swu.engine.actions import legal_actions, apply, FinishBottomFromDiscard
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, FinishBottomFromDiscard)))


class TestReprocessTwi88:
    """TWI_88 — "Choose up to 4 units in your discard pile.  Put them on the bottom
    of your deck in a random order and create that many Battle Droid tokens"."""

    def _played(self, repo):
        state = _make_state()
        mine_a = _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))
        mine_b = _put_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        not_a_unit = _put_in_discard(state, "P0", _get_card(repo, "TWI", "175"))
        theirs = _put_in_discard(state, "P1", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "88", resources=10)
        return state, mine_a, mine_b, not_a_unit, theirs

    def test_TWI_88_offers_only_units_in_your_own_discard(self, repo):
        state, mine_a, mine_b, not_a_unit, theirs = self._played(repo)
        top = state.pending_decisions[-1]
        assert top.kind == "bottom_from_discard"
        # The event card just played is in the discard too — and, being an event,
        # is no more eligible than the enemy's unit.
        assert set(top.context["candidate_ids"]) == {mine_a.instance_id,
                                                     mine_b.instance_id}
        assert not_a_unit.instance_id not in top.context["candidate_ids"]
        assert theirs.instance_id not in top.context["candidate_ids"]

    def test_TWI_88_bottoms_the_picks_and_creates_a_droid_for_each(self, repo):
        state, mine_a, mine_b, _nu, _th = self._played(repo)
        state = _pick_bottom(state, mine_a.instance_id)
        state = _pick_bottom(state, mine_b.instance_id)
        state = _finish_bottom(state)

        ps = state.player_by_id("P0")
        assert {c.instance_id for c in ps.deck[-2:]} == {mine_a.instance_id,
                                                         mine_b.instance_id}
        assert mine_a.instance_id not in {c.instance_id for c in ps.discard}
        assert len(_battle_droids(state)) == 2

    def test_TWI_88_choosing_none_creates_no_tokens(self, repo):
        """"Up to 4" includes 0 — and then "that many" is none."""
        state, mine_a, _b, _nu, _th = self._played(repo)
        state = _finish_bottom(state)
        assert _battle_droids(state) == []
        assert mine_a.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}


class TestPetitionTheSenateTwi100:
    """TWI_100 — "If you control 3 or more Official units, draw 3 cards"."""

    def _officials(self, state, repo, n):
        for num in ("43", "56", "105")[:n]:
            _place(state, "P0", _get_card(repo, "TWI", num), "ground")

    def test_TWI_100_draws_3_with_three_official_units(self, repo):
        state = _make_state()
        self._officials(state, repo, 3)
        _add_deck_cards(state, "P0", repo, 5)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "100", resources=10)
        assert len(state.player_by_id("P0").hand) == 3

    def test_TWI_100_draws_nothing_with_two_officials_or_wrong_trait(self, repo):
        state = _make_state()
        self._officials(state, repo, 2)
        _filler(state, "P0", repo)            # a third unit, but not an Official
        _place(state, "P1", _get_card(repo, "TWI", "43"), "ground")  # enemy Official
        _add_deck_cards(state, "P0", repo, 5)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "100", resources=10)
        assert state.player_by_id("P0").hand == []
        assert len(state.player_by_id("P0").deck) == 5


class TestMasAmeddaTwi101:
    """TWI_101 — "When you play another unit: You may exhaust this unit.  If you do,
    search the top 4 cards of your deck for a unit, reveal it, and draw it"."""

    def _board(self, repo):
        state = _make_state()
        mas = _place(state, "P0", _get_card(repo, "TWI", "101"), "ground")
        mas.exhausted = False
        played = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        return state, mas, played

    def test_TWI_101_exhausts_to_search_the_top_4_for_a_unit(self, repo):
        state, mas, played = self._board(repo)
        _stack_deck(state, "P0", [
            _get_card(repo, "TWI", "175"),      # an event — not searchable
            _get_card(repo, "SOR", "46"),       # the unit, inside the window
            _get_card(repo, "TWI", "175"),
            _get_card(repo, "TWI", "175"),
            _get_card(repo, "SOR", "128"),      # 5th — outside the window
        ])
        state = _fire_card_played(state, "P0", played)
        state = _accept(state)

        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert _find_instance(state, mas.instance_id).exhausted is True
        # Only the unit inside the 4-card window is takeable.
        assert len(top.context["candidate_ids"]) == 1

    def test_TWI_101_is_not_offered_while_he_is_exhausted(self, repo):
        """Gated SOURCE_READY — the trigger isn't even collected, so no prompt."""
        state, mas, played = self._board(repo)
        mas.exhausted = True
        _add_deck_cards(state, "P0", repo, 5)
        state = _fire_card_played(state, "P0", played)
        assert state.pending_decisions == []

    def test_TWI_101_ignores_his_own_play_and_non_unit_plays(self, repo):
        """"Another UNIT" — an upgrade play and his own arrival both pass him by."""
        state, mas, _played = self._board(repo)
        _add_deck_cards(state, "P0", repo, 5)
        state = _fire_card_played(state, "P0", mas)
        assert state.pending_decisions == []
        upgrade = _put_in_hand(state, "P0", _get_card(repo, "TWI", "168"))
        state = _fire_card_played(state, "P0", upgrade)
        assert state.pending_decisions == []


class TestMaceWindusLightsaberTwi152:
    """TWI_152 — "When Played: If attached unit is Mace Windu, draw 2 cards"."""

    def _play_on(self, state, repo, host):
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "152"), "P0")
        return _fire_upgrade_played(state, up, host)

    def test_TWI_152_draws_2_on_mace_windu(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        mace = _place(state, "P0", _get_card(repo, "SOR", "149"), "ground")
        state = self._play_on(state, repo, mace)
        assert len(state.player_by_id("P0").hand) == 2

    def test_TWI_152_draws_nothing_on_any_other_host(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = self._play_on(state, repo, other)
        assert state.player_by_id("P0").hand == []
        assert state.pending_decisions == []      # not even collected


class TestOldAccessCodesTwi168:
    """TWI_168 — "When Played: If an opponent controls more units than you, draw a
    card"."""

    def _play(self, state, repo, host):
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "168"), "P0")
        return _fire_upgrade_played(state, up, host)

    def test_TWI_168_draws_when_the_opponent_is_ahead_on_units(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 3)
        host = _filler(state, "P0", repo)
        _filler(state, "P1", repo)
        _filler(state, "P1", repo)                 # 2 enemy units vs 1
        state = self._play(state, repo, host)
        assert len(state.player_by_id("P0").hand) == 1

    def test_TWI_168_draws_nothing_when_level_or_ahead(self, repo):
        """Not the negation of "you control more" — equal counts satisfy neither."""
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 3)
        host = _filler(state, "P0", repo)
        _filler(state, "P1", repo)                 # 1 v 1
        state = self._play(state, repo, host)
        assert state.player_by_id("P0").hand == []


class TestStrategicAnalysisTwi175:
    """TWI_175 — "Draw 3 cards"."""

    def test_TWI_175_draws_3_cards(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "175", resources=10)
        assert len(state.player_by_id("P0").hand) == 3
        assert len(state.player_by_id("P0").deck) == 2


class TestCadBaneTwi187:
    """TWI_187 — "When Played: This unit captures up to 3 enemy non-leader units with
    a total of 8 or less remaining HP" + "On Attack: The defending player may rescue
    a card they own guarded by this unit.  If they do, draw 2 cards"."""

    @staticmethod
    def _capture(state, target_id):
        from swu.engine.actions import (legal_actions, apply,
                                        SelectUnitToCaptureCombined)
        return apply(state, next(a for a in legal_actions(state)
                                 if isinstance(a, SelectUnitToCaptureCombined)
                                 and a.target_id == target_id))

    def test_TWI_187_captures_at_most_three_enemy_units(self, repo):
        """Four 1-HP preys fit the 8-HP budget, but "up to 3" stops at three — and
        the cap resolves the decision on its own."""
        state = _make_state()
        bane = _place(state, "P0", _get_card(repo, "TWI", "187"), "ground")
        preys = [_place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
                 for _ in range(4)]                     # 3/1 each
        state = _fire_when_played(state, bane)
        assert state.pending_decisions[-1].kind == "capture_combined_hp"
        for prey in preys[:3]:
            state = self._capture(state, prey.instance_id)
        assert state.pending_decisions == []            # cap reached → auto-finish
        assert len(state.player_by_id("P0").capture_pile) == 3
        assert _find_instance(state, preys[3].instance_id) is not None

    def test_TWI_187_capture_budget_is_total_remaining_hp(self, repo):
        """Two 3-HP preys spend 6 of the 8; a 3-HP third no longer fits."""
        state = _make_state()
        bane = _place(state, "P0", _get_card(repo, "TWI", "187"), "ground")
        preys = [_place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
                 for _ in range(3)]                     # 3/3 each
        state = _fire_when_played(state, bane)
        state = self._capture(state, preys[0].instance_id)
        state = self._capture(state, preys[1].instance_id)
        assert state.pending_decisions == []            # nothing else affordable
        assert len(state.player_by_id("P0").capture_pile) == 2
        assert _find_instance(state, preys[2].instance_id) is not None

    def test_TWI_187_damage_frees_a_prey_that_would_not_otherwise_fit(self, repo):
        """It is REMAINING HP that is spent, so a damaged unit is cheaper prey."""
        state = _make_state()
        bane = _place(state, "P0", _get_card(repo, "TWI", "187"), "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        big.damage = 6                                   # 1 remaining
        state = _fire_when_played(state, bane)
        ids = {a.target_id for a in _capture_options(state)}
        assert big.instance_id in ids

    def _guarding(self, repo):
        """Cad Bane in play guarding one card owned by each player."""
        from swu.engine.actions import _apply_capture
        state = _make_state()
        bane = _place(state, "P0", _get_card(repo, "TWI", "187"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _apply_capture(state, bane.instance_id, theirs.instance_id)
        _apply_capture(state, bane.instance_id, mine.instance_id)
        _add_deck_cards(state, "P0", repo, 5)
        return state, bane, theirs, mine

    def test_TWI_187_on_attack_offers_the_rescue_to_the_defending_player(self, repo):
        """The decision shifts seats, and only the DECIDER's own captive is offered
        (the card says "a card THEY own")."""
        from swu.engine.actions import legal_actions, RescueGuardedCard, DeclineRescue
        state, bane, theirs, mine = self._guarding(repo)
        state = _fire_on_attack(state, bane)

        top = state.pending_decisions[-1]
        assert top.kind == "rescue_guarded"
        assert top.deciding_player_id == "P1"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, RescueGuardedCard)}
        assert offered == {theirs.instance_id}
        assert mine.instance_id not in offered
        assert any(isinstance(a, DeclineRescue) for a in legal_actions(state))

    def test_TWI_187_rescuing_returns_the_card_and_draws_the_attacker_2(self, repo):
        from swu.engine.actions import legal_actions, apply, RescueGuardedCard
        state, bane, theirs, _mine = self._guarding(repo)
        state = _fire_on_attack(state, bane)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, RescueGuardedCard)))

        # Rescue returns the card to its OWNER'S HAND (not to the arena, the way a
        # leave-play release does).
        assert theirs.instance_id in {c.instance_id
                                      for c in state.player_by_id("P1").hand}
        assert _find_instance(state, theirs.instance_id) is None
        assert len(state.player_by_id("P0").hand) == 2        # "draw 2 cards"
        assert len(state.player_by_id("P0").capture_pile) == 1  # P0's own captive stays

    def test_TWI_187_declining_the_rescue_draws_nobody_anything(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineRescue
        state, bane, theirs, _mine = self._guarding(repo)
        state = _fire_on_attack(state, bane)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineRescue)))
        assert state.player_by_id("P0").hand == []
        assert len(state.player_by_id("P0").capture_pile) == 2

    def test_TWI_187_no_rescue_prompt_when_the_defender_owns_no_captive(self, repo):
        from swu.engine.actions import _apply_capture
        state = _make_state()
        bane = _place(state, "P0", _get_card(repo, "TWI", "187"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _apply_capture(state, bane.instance_id, mine.instance_id)
        state = _fire_on_attack(state, bane)
        assert state.pending_decisions == []      # only a decline would be possible


def _capture_options(state):
    from swu.engine.actions import legal_actions, SelectUnitToCaptureCombined
    return [a for a in legal_actions(state)
            if isinstance(a, SelectUnitToCaptureCombined)]


# ── twi-set:09/10 — card advantage & disruption ──────────────────────────────


def _append_deck_card(state, owner_id, card_def):
    """Append one card to the bottom of a player's deck.  Returns the instance."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_dk_{uuid.uuid4().hex[:5]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DECK,
    )
    state.player_by_id(owner_id).deck.append(ci)
    return ci


def _defeat_units(state, owner_id, units):
    """Defeat units through the engine so the defeat ledgers are fed."""
    from swu.engine.actions import _defeat_unit
    ps = state.player_by_id(owner_id)
    for ci in units:
        _defeat_unit(state, ps, ci)
    return state


class TestWartimeProfiteeringTwi188:
    """TWI_188 — "Look at cards from the top of your deck equal to the number of
    units that were defeated this phase.  Draw 1 and put the others on the bottom of
    your deck in a random order"."""

    def test_TWI_188_window_scales_with_units_defeated_this_phase(self, repo):
        state = _make_state()
        dead = [_filler(state, "P1", repo) for _ in range(3)]
        _defeat_units(state, "P1", dead)
        _add_deck_cards(state, "P0", repo, 6)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "188", resources=10)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["window"] == 3          # three units died this phase
        assert top.context["max_select"] == 1      # "Draw 1"
        assert top.context["up_to"] is False       # the draw is mandatory

    def test_TWI_188_draws_one_and_bottoms_the_rest(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        _defeat_units(state, "P1", [_filler(state, "P1", repo) for _ in range(2)])
        _add_deck_cards(state, "P0", repo, 5)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "188", resources=10)
        deck_before = len(state.player_by_id("P0").deck)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard))
        state = apply(state, pick)
        ps = state.player_by_id("P0")
        assert any(c.instance_id == pick.instance_id for c in ps.hand)
        assert len(ps.deck) == deck_before - 1     # only the drawn card left the deck
        assert not state.pending_decisions

    def test_TWI_188_no_defeats_looks_at_nothing(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 5)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "188", resources=10)
        assert not state.pending_decisions                       # no search pushed
        assert len(state.player_by_id("P0").hand) == 0           # and no draw


class TestAidFromTheInnocentTwi201:
    """TWI_201 — "Search the top 10 cards of your deck for 2 Heroism non-unit cards
    and discard them.  For this phase, you may play the discarded cards, and they
    each cost 2 resources less"."""

    def _searched(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 9)                    # filler units
        medal = _append_deck_card(state, "P0", _get_card(repo, "SOR", "245"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "201", resources=10)
        return state, medal

    def test_TWI_201_offers_only_heroism_non_unit_cards(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard
        state, medal = self._searched(repo)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["window"] == 10
        assert top.context["disposition"] == "discard_play_discount"
        picks = [a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)]
        assert picks == [medal.instance_id]   # the filler units are all ineligible

    def test_TWI_201_discards_the_card_and_grants_a_2_cheaper_replay(self, repo):
        from swu.engine.actions import (legal_actions, apply, SelectSearchCard,
                                        FinishSearch)
        state, medal = self._searched(repo)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectSearchCard)))
        if any(isinstance(a, FinishSearch) for a in legal_actions(state)):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, FinishSearch)))
        ps = state.player_by_id("P0")
        assert any(c.instance_id == medal.instance_id for c in ps.discard)
        assert (state.game_memory.discard_play_discount_this_phase[
            medal.instance_id] == 2)

    def test_TWI_201_discarded_card_is_playable_from_discard_for_2_less(self, repo):
        from swu.engine.actions import (legal_actions, apply, SelectSearchCard,
                                        FinishSearch, PlayFromDiscard, _play_cost)
        state, medal = self._searched(repo)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectSearchCard)))
        if any(isinstance(a, FinishSearch) for a in legal_actions(state)):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, FinishSearch)))
        state.active_player_index = 0            # back to the controller's turn
        ps = state.player_by_id("P0")
        full = _play_cost(state, next(c for c in ps.discard
                                      if c.instance_id == medal.instance_id), ps)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == medal.instance_id)
        assert play.discount == 2
        ready_before = sum(1 for r in ps.resources if not r.exhausted)
        state = apply(state, play)
        ps2 = state.player_by_id("P0")
        spent = ready_before - sum(1 for r in ps2.resources if not r.exhausted)
        assert spent == max(0, full - 2)
        # the one-shot permission is consumed, so the discount can't be spent twice
        assert medal.instance_id not in state.game_memory.discard_play_discount_this_phase


class TestFavorableDelegateTwi208:
    """TWI_208 — "When Played: Draw a card.  When Defeated: Discard a card from your
    hand"."""

    def test_TWI_208_when_played_draws(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P0", repo, 3)
        ci = _place(state, "P0", _get_card(repo, "TWI", "208"), "ground")
        state = _fire_when_played(state, ci)
        assert len(state.player_by_id("P0").hand) == 1

    def test_TWI_208_when_defeated_discards_a_card(self, repo):
        state = _make_state()
        ci = _place(state, "P0", _get_card(repo, "TWI", "208"), "ground")
        held = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        state = _defeat_and_fire(state, ci, "P0")
        ps = state.player_by_id("P0")
        assert not ps.hand
        assert any(c.instance_id == held.instance_id for c in ps.discard)


class TestGeonosisPatrolFighterTwi215:
    """TWI_215 — "When Played: You may return a non-leader unit that costs 3 or less
    to its owner's hand" (Exploit 2 is the keyword engine's)."""

    def test_TWI_215_returns_a_cheap_unit_to_its_owners_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "TWI", "215"), "space")
        cheap = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 2
        pricey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state = _fire_when_played(state, fighter)
        state = _accept(state)
        choices = [a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)]
        assert cheap.instance_id in choices
        assert pricey.instance_id not in choices      # costs more than 3
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == cheap.instance_id))
        ps1 = state.player_by_id("P1")
        assert any(c.instance_id == cheap.instance_id for c in ps1.hand)
        assert not any(c.instance_id == cheap.instance_id for c in ps1.ground_arena)

    def test_TWI_215_declines_when_no_cheap_unit_exists(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "TWI", "215"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # cost 4 only
        state = _fire_when_played(state, fighter)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestFivesTwi216:
    """TWI_216 — "When you play an event: You may put a Clone unit from your discard
    pile on the bottom of your deck.  If you do, draw a card"."""

    def _played_event(self, repo):
        state = _make_state()
        fives = _place(state, "P0", _get_card(repo, "TWI", "216"), "ground")
        clone = _put_in_discard(state, "P0", _get_card(repo, "TWI", "241"))
        other = _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))
        theirs = _put_in_discard(state, "P1", _get_card(repo, "TWI", "241"))
        _add_deck_cards(state, "P0", repo, 3)
        evt = _put_in_discard(state, "P0", _get_card(repo, "TWI", "175"))
        state = _fire_card_played(state, "P0", evt)
        return state, fives, clone, other, theirs

    def test_TWI_216_offers_only_your_own_clone_units(self, repo):
        from swu.engine.actions import legal_actions, SelectBottomDiscardCard
        state, _fives, clone, other, theirs = self._played_event(repo)
        state = _accept(state)
        assert state.pending_decisions[-1].kind == "bottom_from_discard"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)}
        assert offered == {clone.instance_id}
        assert other.instance_id not in offered      # not a Clone
        assert theirs.instance_id not in offered     # not YOUR discard pile

    def test_TWI_216_bottoming_a_clone_draws_a_card(self, repo):
        state, _fives, clone, _o, _t = self._played_event(repo)
        state = _accept(state)
        hand_before = len(state.player_by_id("P0").hand)
        state = _pick_bottom(state, clone.instance_id)
        ps = state.player_by_id("P0")
        assert not any(c.instance_id == clone.instance_id for c in ps.discard)
        assert ps.deck[-1].instance_id == clone.instance_id      # bottom of deck
        assert len(ps.hand) == hand_before + 1                   # "If you do, draw"

    def test_TWI_216_bottoming_nothing_draws_nothing(self, repo):
        state, _fives, _c, _o, _t = self._played_event(repo)
        state = _accept(state)
        hand_before = len(state.player_by_id("P0").hand)
        state = _finish_bottom(state)
        assert len(state.player_by_id("P0").hand) == hand_before


class TestShadowedIntentionsTwi220:
    """TWI_220 — "Attached unit gains: 'This unit can't be captured, defeated, or
    returned to its owner's hand by enemy card abilities.'\""""

    def test_TWI_220_host_immune_to_enemy_capture_defeat_and_bounce(self, repo):
        from swu.engine.actions import _apply_capture
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import (
            DefeatUnit as _DU, ReturnToHand as _RTH, TargetSpec as _TS)
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "220"), "P1")
        enemy_src = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        tid = host.instance_id

        s2 = execute_effect(state, _DU(target=_TS(controller="enemy", kind="unit")),
                            enemy_src, tid, {})
        assert s2.find_instance(tid) is not None
        s3 = execute_effect(state, _RTH(_TS(controller="enemy", kind="unit")),
                            enemy_src, tid, {})
        assert any(c.instance_id == tid
                   for c in s3.player_by_id("P1").ground_arena)
        s4 = _apply_capture(state, enemy_src.instance_id, tid)
        assert not s4.player_by_id("P0").capture_pile

    def test_TWI_220_does_not_block_a_friendly_ability(self, repo):
        """Only ENEMY card abilities are blocked (the Protection convention)."""
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import DefeatUnit as _DU, TargetSpec as _TS
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "220"), "P1")
        friendly_src = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        s2 = execute_effect(state, _DU(target=_TS(controller="friendly", kind="unit")),
                            friendly_src, host.instance_id, {})
        assert not any(c.instance_id == host.instance_id
                       for c in s2.player_by_id("P1").ground_arena)


class TestUnmaskingTheConspiracyTwi223:
    """TWI_223 — "Discard a card from your hand.  If you do, look at an opponent's
    hand and discard a card from it"."""

    def test_TWI_223_discards_then_strips_a_card_from_the_opponent_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        mine = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        theirs = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "223", resources=10)
        p0 = state.player_by_id("P0")
        assert any(c.instance_id == mine.instance_id for c in p0.discard)
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard"
        assert [r["card_name"] for r in top.context["revealed_hand"]] == [
            theirs.card_def.display_name]
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, NameAndDiscard)))
        p1 = state.player_by_id("P1")
        assert not p1.hand
        assert any(c.instance_id == theirs.instance_id for c in p1.discard)

    def test_TWI_223_empty_hand_pays_nothing_and_looks_at_nothing(self, repo):
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state, evt = _play_event_from_hand(state, repo, "TWI", "223", resources=10)
        # the event itself is the only card that reached the discard
        assert [c.instance_id for c in state.player_by_id("P0").discard] == [
            evt.instance_id]
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == 1


class TestAggrievedParliamentarianTwi252:
    """TWI_252 — "When Played: Choose an opponent.  They shuffle their discard pile
    and put it on the bottom of their deck"."""

    def test_TWI_252_bottoms_the_opponents_whole_discard_pile(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P1", repo, 2)
        dumped = [_put_in_discard(state, "P1", _get_card(repo, "SOR", "128"))
                  for _ in range(3)]
        mine = _put_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        ci = _place(state, "P0", _get_card(repo, "TWI", "252"), "ground")
        deck_before = len(state.player_by_id("P1").deck)
        state = _fire_when_played(state, ci)
        p1 = state.player_by_id("P1")
        assert not p1.discard
        assert len(p1.deck) == deck_before + 3
        assert {c.instance_id for c in p1.deck[-3:]} == {d.instance_id for d in dumped}
        assert all(c.zone.name == "DECK" for c in p1.deck)
        # the controller's own discard pile is untouched
        assert any(c.instance_id == mine.instance_id
                   for c in state.player_by_id("P0").discard)

    def test_TWI_252_empty_discard_is_a_clean_no_op(self, repo):
        state = _make_state()
        _add_deck_cards(state, "P1", repo, 2)
        ci = _place(state, "P0", _get_card(repo, "TWI", "252"), "ground")
        state = _fire_when_played(state, ci)
        assert len(state.player_by_id("P1").deck) == 2
        assert not state.player_by_id("P1").discard


# ── twi-set:11 — leaders: combat tricks, buffs & tempo ───────────────────────


def _get_leader(repo, set_code, num):
    """``_get_card`` for a LEADER — (set, number) is not unique, and TWI 1/2 each
    collide with a same-numbered token unit."""
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=? AND type='Leader'",
            (set_code, str(int(num)))).fetchone()
        from tests.dbpath import require_row
        row = require_row(row, f"leader {set_code}_{num}")
        return repo._hydrate(con, row)


def _use_ability(state, source_ci, idx=0):
    from swu.engine.actions import legal_actions, apply, UseAbility
    act = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id)
    return apply(state, act)


def _ability_offered(state, source_ci):
    from swu.engine.actions import legal_actions, UseAbility
    return any(isinstance(a, UseAbility) and a.source_id == source_ci.instance_id
               for a in legal_actions(state))


def _drain(state):
    """Resolve the FORCED steps a mandatory ability leaves pending: an
    AutoResolveEffects step, or a step whose only legal action is the single
    remaining choice (a one-candidate ChooseTarget is not a decision)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    guard = 0
    while state.pending_decisions and guard < 10:
        guard += 1
        acts = legal_actions(state)
        auto = [a for a in acts if isinstance(a, AutoResolveEffects)]
        if auto:
            state = apply(state, auto[0])
        elif len(acts) == 1:
            state = apply(state, acts[0])
        else:
            break
    return state


def _resolve_attack(state, attacker_id, defender_id, *, accept=True):
    """Drive an attack to full resolution, answering trigger prompts along the way."""
    from swu.engine.actions import (legal_actions, apply, AttackWithUnit,
                                    AcceptTrigger, DeclineTrigger, ContinueAttack)
    state = apply(state, AttackWithUnit(attacker_id, defender_id))
    guard = 0
    while state.pending_decisions and guard < 20:
        guard += 1
        top = state.pending_decisions[-1]
        acts = legal_actions(state)
        if top.kind == "trigger_option":
            want = AcceptTrigger if accept else DeclineTrigger
            state = apply(state, next(a for a in acts if isinstance(a, want)))
        elif top.kind == "pre_attack":
            state = apply(state, next(a for a in acts if isinstance(a, ContinueAttack)))
        else:
            state = apply(state, acts[0])
    return state


class TestNalaSeTwi1:
    """TWI_1 — "Ignore the aspect penalty on Clone units you play" (both sides) and
    the deployed aura "Each friendly Clone unit gains: 'When Defeated: Heal 2 damage
    from your base.'\""""

    def test_TWI_1_waives_the_aspect_penalty_on_clone_units_only(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        clone = _put_in_hand(state, "P0", _get_card(repo, "TWI", "241"))  # 2, Heroism
        other = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))   # 4, Vig/Her
        assert _play_cost(state, clone, ps) == 4          # 2 + one unmatched pip
        # Nala Se is Vigilance/Villainy, so she matches neither of the Clone's pips —
        # any drop is the waiver, not her aspects.
        _place_leader(state, "P0", _get_leader(repo, "TWI", "1"))
        assert _play_cost(state, clone, ps) == 2          # penalty waived entirely
        assert _play_cost(state, other, ps) == 6          # non-Clone: Heroism still taxed

    def test_TWI_1_friendly_clone_heals_your_base_when_defeated(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        nala = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "1"))
        assert nala.deployed
        base = state.player_by_id("P0").base_instance
        base.damage = 5
        clone = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), clone)
        state = _drain(state)          # the granted heal is mandatory — no prompt
        assert state.player_by_id("P0").base_instance.damage == 3

    def test_TWI_1_grants_nothing_to_a_non_clone_unit(self, repo):
        from swu.engine.actions import _defeat_unit, legal_actions, AcceptTrigger
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "1"))
        state.player_by_id("P0").base_instance.damage = 5
        plain = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), plain)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert state.player_by_id("P0").base_instance.damage == 5


class TestWatTamborTwi6:
    """TWI_6 — both sides: "If a friendly unit was defeated this phase, give
    a(nother) unit +2/+2 for this phase"."""

    def test_TWI_6_undeployed_action_needs_a_friendly_defeat(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        wat = _place_leader(state, "P0", _get_leader(repo, "TWI", "6"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P1"),
                     _place(state, "P1", _get_card(repo, "SOR", "128"), "ground"))
        assert not _ability_offered(state, wat)        # only an ENEMY unit died
        _defeat_unit(state, state.player_by_id("P0"),
                     _place(state, "P0", _get_card(repo, "SOR", "128"), "ground"))
        assert _ability_offered(state, wat)

    def test_TWI_6_undeployed_action_gives_a_unit_plus_2_2(self, repo):
        from swu.engine.actions import (legal_actions, apply, ChooseTarget,
                                        compute_power, compute_hp, _defeat_unit)
        state = _make_state()
        wat = _place_leader(state, "P0", _get_leader(repo, "TWI", "6"))
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P0"),
                     _place(state, "P0", _get_card(repo, "SOR", "128"), "ground"))
        before = (compute_power(state, target), compute_hp(state, target))
        state = _use_ability(state, wat)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == target.instance_id))
        tgt = _find_instance(state, target.instance_id)
        assert (compute_power(state, tgt), compute_hp(state, tgt)) == (
            before[0] + 2, before[1] + 2)

    def test_TWI_6_deployed_on_attack_only_fires_after_a_friendly_defeat(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger, _defeat_unit
        state = _make_state()
        wat = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "6"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # "another unit"
        s1 = _fire_on_attack(state, wat)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(s1))
        _defeat_unit(state, state.player_by_id("P0"),
                     _place(state, "P0", _get_card(repo, "SOR", "128"), "ground"))
        s2 = _fire_on_attack(state, wat)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(s2))


class TestCaptainRexTwi7:
    """TWI_7 — undeployed "Action [2 resources, Exhaust]: If a friendly unit attacked
    this phase, create a Clone Trooper token"; deployed "When Deployed: create a Clone
    Trooper token" + "Each other friendly Trooper unit gets +0/+1"."""

    def test_TWI_7_undeployed_action_needs_a_friendly_attacker(self, repo):
        state = _make_state()
        rex = _place_leader(state, "P0", _get_leader(repo, "TWI", "7"))
        _give_resources(state, "P0", 5)
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_attacked_this_round.add(theirs.instance_id)
        assert not _ability_offered(state, rex)        # an ENEMY unit attacked
        state.game_memory.units_attacked_this_round.add(mine.instance_id)
        assert _ability_offered(state, rex)
        state = _use_ability(state, rex)
        ps = state.player_by_id("P0")
        assert any(u.card_def.name == "Clone Trooper"
                   for u in ps.ground_arena), "a Clone Trooper token is created"

    def test_TWI_7_deployed_creates_a_token_and_buffs_other_troopers(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        rex = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "7"))
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Trooper
        assert compute_hp(state, trooper) == 8                      # 7 + Rex's +0/+1
        assert compute_hp(state, rex) == 6                          # "each OTHER"
        state = _fire_when_deployed(state, rex)
        assert any(u.card_def.name == "Clone Trooper"
                   for u in state.player_by_id("P0").ground_arena)


class TestMaulTwi9:
    """TWI_9 — undeployed "Action [Exhaust]: Attack with a unit.  It gains Overwhelm
    for this attack"; deployed "Each other friendly unit gains Overwhelm"."""

    def test_TWI_9_undeployed_action_grants_overwhelm_for_the_attack(self, repo):
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "TWI", "9"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _use_ability(state, maul)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert "Overwhelm" in (top.context.get("grant_keywords") or [])

    def test_TWI_9_deployed_gives_other_friendly_units_overwhelm(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        maul = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "9"))
        mine = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        assert has_keyword(state, mine, Keyword.OVERWHELM)
        assert not has_keyword(state, theirs, Keyword.OVERWHELM)


class TestAnakinSkywalkerTwi12:
    """TWI_12 — undeployed "Action [Exhaust, deal 2 damage to your base]: Attack with
    a unit.  If it's attacking a unit, it gets +2/+0"; deployed "+1/+0 for every 5
    damage on your base"."""

    def test_TWI_12_undeployed_action_costs_2_base_damage(self, repo):
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_leader(repo, "TWI", "12"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _use_ability(state, anakin)
        assert state.player_by_id("P0").base_instance.damage == 2
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 2
        assert top.context["bonus_if_defender_unit"] is True

    def test_TWI_12_deployed_scales_with_damage_on_your_base(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        anakin = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "12"))
        base = state.player_by_id("P0").base_instance
        assert compute_power(state, anakin) == 4
        base.damage = 4
        assert compute_power(state, anakin) == 4          # every FIVE damage
        base.damage = 5
        assert compute_power(state, anakin) == 5
        base.damage = 12
        assert compute_power(state, anakin) == 6


class TestAsajjVentressTwi14:
    """TWI_14 — both sides key on "If you played an event this phase"; deployed she
    also "deals combat damage before the defender" (First Strike)."""

    def test_TWI_14_undeployed_bonus_only_after_an_event(self, repo):
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "TWI", "14"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        s1 = _use_ability(state, asajj)
        assert s1.pending_decisions[-1].context["power_bonus"] == 0
        state.game_memory.events_played_this_round.add("P0")
        s2 = _use_ability(state, asajj)
        assert s2.pending_decisions[-1].context["power_bonus"] == 1

    def test_TWI_14_deployed_on_attack_needs_an_event_this_phase(self, repo):
        """The clause is mandatory-if-able, so it simply doesn't fire without an
        event this phase — the condition gates trigger COLLECTION."""
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        asajj = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "14"))
        s1 = _drain(_fire_on_attack(state, asajj))
        me1 = _find_instance(s1, asajj.instance_id)
        assert compute_power(s1, me1) == 3
        assert not has_keyword(s1, me1, Keyword.FIRST_STRIKE)

    def test_TWI_14_deployed_gains_first_strike_and_plus_1_power(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        asajj = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "14"))
        state.game_memory.events_played_this_round.add("P0")
        state = _drain(_fire_on_attack(state, asajj))
        me = _find_instance(state, asajj.instance_id)
        assert compute_power(state, me) == 4                       # 3 + 1
        assert has_keyword(state, me, Keyword.FIRST_STRIKE)


class TestJangoFettTwi16:
    """TWI_16 — both sides: "When a friendly unit deals damage to an enemy unit: …
    exhaust that unit" (the undeployed side first exhausting Jango himself)."""

    def _board(self, repo, deployed):
        state = _make_state()
        leader = _get_leader(repo, "TWI", "16")
        jango = (_place_deployed_leader(state, "P0", leader) if deployed
                 else _place_leader(state, "P0", leader))
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.exhausted = False
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        return state, jango, mine, theirs

    def test_TWI_16_deployed_exhausts_the_damaged_enemy_unit(self, repo):
        state, jango, mine, theirs = self._board(repo, deployed=True)
        state = _resolve_attack(state, mine.instance_id, theirs.instance_id)
        victim = _find_instance(state, theirs.instance_id)
        assert victim is not None and victim.exhausted

    def test_TWI_16_deployed_trigger_is_optional(self, repo):
        state, jango, mine, theirs = self._board(repo, deployed=True)
        state = _resolve_attack(state, mine.instance_id, theirs.instance_id,
                                accept=False)
        victim = _find_instance(state, theirs.instance_id)
        assert victim is not None and not victim.exhausted

    def test_TWI_16_undeployed_exhausts_this_leader_and_the_enemy(self, repo):
        state, jango, mine, theirs = self._board(repo, deployed=False)
        state = _resolve_attack(state, mine.instance_id, theirs.instance_id)
        assert state.find_instance(jango.instance_id)[1].exhausted   # in base_zone
        assert _find_instance(state, theirs.instance_id).exhausted

    def test_TWI_16_undeployed_not_offered_while_already_exhausted(self, repo):
        from swu.engine.actions import legal_actions
        state, jango, mine, theirs = self._board(repo, deployed=False)
        jango.exhausted = True
        from swu.engine.actions import apply, AttackWithUnit
        state = apply(state, AttackWithUnit(mine.instance_id, theirs.instance_id))
        seen_trigger = False
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            top = state.pending_decisions[-1]
            acts = legal_actions(state)
            if top.kind == "trigger_option":
                seen_trigger = True
            state = apply(state, acts[0])
        assert not seen_trigger
        assert not _find_instance(state, theirs.instance_id).exhausted

# ── twi-set:12 — combat tricks, buffs & tempo ────────────────────────────────

def _set_base(state, owner_id, base_def):
    """Swap in a real Base card as ``owner_id``'s base (``_make_state`` seeds a
    synthetic ability-free one).  Returns the new CardInstance."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ps = state.player_by_id(owner_id)
    ps.base_zone = [ci for ci in ps.base_zone
                    if not ci.card_def.__class__.__name__ == "Base"]
    ci = CardInstance(
        instance_id=f"{owner_id}_base_{_u.uuid4().hex[:5]}",
        card_def=base_def, owner_id=owner_id, zone=Zone.BASE_ZONE,
    )
    ps.base_zone.append(ci)
    return ci


def _choose_target(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, act)


class TestPauCityTwi19:
    """TWI_19 — "Each leader unit you control gets +0/+1" (a BASE's constant)."""

    def test_TWI_19_buffs_only_friendly_leader_units(self, repo):
        from swu.engine.actions import compute_hp, compute_power
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TWI", "19"))
        leader = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "11"))
        assert compute_hp(state, leader) == 7          # printed 3/6 → +0/+1
        assert compute_power(state, leader) == 3       # power untouched
        # A friendly NON-leader unit and an enemy leader are both unaffected.
        grunt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert compute_hp(state, grunt) == 7           # printed 3/7
        enemy_leader = _place_deployed_leader(state, "P1", _get_leader(repo, "TWI", "11"))
        assert compute_hp(state, enemy_leader) == 6

    def test_TWI_19_only_applies_while_it_is_the_base_in_play(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        leader = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "11"))
        assert compute_hp(state, leader) == 6          # synthetic base → no buff
        _set_base(state, "P0", _get_card(repo, "TWI", "19"))
        assert compute_hp(state, leader) == 7


class TestPetranakiArenaTwi28:
    """TWI_28 — "Each leader unit you control gets +1/+0"."""

    def test_TWI_28_buffs_friendly_leader_unit_power(self, repo):
        from swu.engine.actions import compute_hp, compute_power
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TWI", "28"))
        leader = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "11"))
        assert compute_power(state, leader) == 4       # printed 3/6 → +1/+0
        assert compute_hp(state, leader) == 6
        grunt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, grunt) == 3        # non-leader untouched


class TestCalculatingMagnaGuardTwi33:
    """TWI_33 — "When Played/When a friendly unit is defeated: This unit gains
    Sentinel for this phase.\""""

    def test_TWI_33_gains_sentinel_when_played(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        mg = _place(state, "P0", _get_card(repo, "TWI", "33"), "ground")
        # The printed (mistagged) Sentinel is stripped — the ability owns it.
        assert not has_keyword(state, mg, Keyword.SENTINEL)
        state = _drain(_fire_when_played(state, mg))
        assert has_keyword(state, mg, Keyword.SENTINEL)

    def test_TWI_33_gains_sentinel_when_a_friendly_unit_is_defeated(self, repo):
        # ``_defeat_and_fire`` homes the dying unit in the discard BEFORE firing, so
        # a kind="unit" filter can't match it; the engine's own ``_defeat_unit``
        # keeps the arena zone until the triggers have fired (the aura gotcha).
        from swu.engine.actions import _defeat_unit
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        mg = _place(state, "P0", _get_card(repo, "TWI", "33"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P1"), enemy)
        assert not has_keyword(state, mg, Keyword.SENTINEL)   # enemy defeat: no
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), friend)
        assert has_keyword(state, mg, Keyword.SENTINEL)


class TestBarrissOfeeTwi42:
    """TWI_42 — "Each friendly unit that was healed this phase gets +1/+0.\""""

    def test_TWI_42_buffs_a_unit_healed_this_phase(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        barriss = _place(state, "P0", _get_card(repo, "TWI", "42"), "ground")
        wounded = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        wounded.damage = 2
        assert compute_power(state, wounded) == 3        # not yet healed
        # Heal it through a real card: Obi-Wan TWI_3 undeployed "Action [Exhaust]:
        # Heal 1 damage from a unit".
        obi = _place_leader(state, "P0", _get_leader(repo, "TWI", "3"))
        state = _use_ability(state, obi)
        state = _choose_target(state, wounded.instance_id)
        # ``apply`` returns a fresh state — re-fetch the instances from it.
        wounded = state.find_instance(wounded.instance_id)[1]
        barriss = state.find_instance(barriss.instance_id)[1]
        assert wounded.damage == 1
        assert compute_power(state, wounded) == 4        # +1/+0 from Barriss
        assert compute_power(state, barriss) == 1        # she wasn't healed

    def test_TWI_42_does_not_buff_an_enemy_or_an_unhealed_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "42"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.damage = 2
        obi = _place_leader(state, "P0", _get_leader(repo, "TWI", "3"))
        state = _use_ability(state, obi)
        state = _choose_target(state, enemy.instance_id)
        enemy = state.find_instance(enemy.instance_id)[1]
        assert enemy.damage == 1
        assert compute_power(state, enemy) == 3          # enemy: not "friendly"


class TestOutspokenRepresentativeTwi43:
    """TWI_43 — conditional Sentinel while you control another Republic unit, and
    "When Defeated: Create a Clone Trooper token.\""""

    def test_TWI_43_sentinel_needs_another_republic_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        rep = _place(state, "P0", _get_card(repo, "TWI", "43"), "ground")
        assert not has_keyword(state, rep, Keyword.SENTINEL)   # only itself
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # non-Republic
        assert not has_keyword(state, rep, Keyword.SENTINEL)
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # Republic
        assert has_keyword(state, rep, Keyword.SENTINEL)

    def test_TWI_43_when_defeated_creates_a_clone_trooper(self, repo):
        state = _make_state()
        rep = _place(state, "P0", _get_card(repo, "TWI", "43"), "ground")
        state = _drain(_defeat_and_fire(state, rep, "P0"))
        names = [c.card_def.name for c in state.player_by_id("P0").ground_arena]
        assert names == ["Clone Trooper"]


class Test41stEliteCorpsTwi45:
    """TWI_45 — "Coordinate — This unit gets +0/+3.\""""

    def test_TWI_45_coordinate_hp_buff_toggles(self, repo):
        from swu.engine.actions import compute_hp, compute_power
        state = _make_state()
        corps = _place(state, "P0", _get_card(repo, "TWI", "45"), "ground")
        _filler(state, "P0", repo)
        assert compute_hp(state, corps) == 3            # 2 units → off
        _filler(state, "P0", repo)
        assert compute_hp(state, corps) == 6            # 3 units → +0/+3
        assert compute_power(state, corps) == 3


class TestLuminaraUnduliTwi50:
    """TWI_50 — "Coordinate — Grit.  When Played: Choose a base.  Heal 1 damage from
    it for each unit you control.\""""

    def test_TWI_50_coordinate_grants_grit(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        lum = _place(state, "P0", _get_card(repo, "TWI", "50"), "ground")
        lum.damage = 3
        assert not has_keyword(state, lum, Keyword.GRIT)
        assert compute_power(state, lum) == 4           # printed 4/9, no Grit
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)
        assert has_keyword(state, lum, Keyword.GRIT)
        assert compute_power(state, lum) == 7           # +1 per damage

    def test_TWI_50_when_played_heals_a_base_per_unit_controlled(self, repo):
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 8
        lum = _place(state, "P0", _get_card(repo, "TWI", "50"), "ground")
        _filler(state, "P0", repo)                      # 2 friendly units
        state = _fire_when_played(state, lum)
        state = _choose_target(state, base.instance_id)
        assert state.player_by_id("P0").base_instance.damage == 6   # one per unit

# ── twi-set:13 — combat tricks, buffs & tempo ────────────────────────────────

class TestForTheRepublicTwi51:
    """TWI_51 — "If you control 3 or more Republic units, this upgrade costs 2
    resources less to play.  Attached unit gains: 'Coordinate — Restore 2.'\""""

    def test_TWI_51_costs_2_less_with_three_republic_units(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        up = CardInstance(instance_id="P0_ftr", card_def=_get_card(repo, "TWI", "51"),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(up)
        host = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # Republic
        # The synthetic base matches no aspect, so the absolute cost carries an
        # aspect penalty — assert the DISCOUNT, which is what the card grants.
        full = _play_cost(state, up, ps, target_host_id=host.instance_id)
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        assert _play_cost(state, up, ps, target_host_id=host.instance_id) == full
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # 3 Republic
        assert _play_cost(state, up, ps, target_host_id=host.instance_id) == full - 2

    def test_TWI_51_grants_restore_2_only_while_coordinating(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "51"), "P0")
        assert not has_keyword(state, host, Keyword.RESTORE)   # 1 unit → no
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                             # 3 units
        assert has_keyword(state, host, Keyword.RESTORE)
        assert keyword_value(state, host, Keyword.RESTORE) == 2


class TestDuchesssChampionTwi54:
    """TWI_54 — "While an opponent controls 3 or more units, this unit gains
    Sentinel.\""""

    def test_TWI_54_sentinel_tracks_the_opponents_unit_count(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        champ = _place(state, "P0", _get_card(repo, "TWI", "54"), "ground")
        # The printed (mistagged) Sentinel is stripped — the ability owns it.
        assert not has_keyword(state, champ, Keyword.SENTINEL)
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)          # FRIENDLY units don't count
        assert not has_keyword(state, champ, Keyword.SENTINEL)
        _filler(state, "P1", repo)
        _filler(state, "P1", repo)
        assert not has_keyword(state, champ, Keyword.SENTINEL)   # 2 enemy units
        _filler(state, "P1", repo, arena="space")
        assert has_keyword(state, champ, Keyword.SENTINEL)       # 3 (both arenas)


class TestCompassionateSenatorTwi56:
    """TWI_56 — "Action [2 resources, Exhaust]: Heal 2 damage from a unit or base.\""""

    def test_TWI_56_action_heals_a_damaged_unit(self, repo):
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "56"), "ground")
        _give_resources(state, "P0", 2)
        wounded = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        wounded.damage = 3
        state = _use_ability(state, senator)
        state = _choose_target(state, wounded.instance_id)
        assert state.find_instance(wounded.instance_id)[1].damage == 1
        assert state.find_instance(senator.instance_id)[1].exhausted is True
        assert state.player_by_id("P0").available_resources == 0

    def test_TWI_56_action_not_offered_without_resources(self, repo):
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "56"), "ground")
        wounded = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        wounded.damage = 3
        assert not _ability_offered(state, senator)      # 0 resources
        _give_resources(state, "P0", 2)
        assert _ability_offered(state, senator)


class TestPadawanStarfighterTwi58:
    """TWI_58 — "While you control a Force unit or a Force upgrade, this unit gets
    +1/+1.\""""

    def test_TWI_58_buffed_by_a_friendly_force_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "TWI", "58"), "ground")
        assert compute_power(state, fighter) == 1 and compute_hp(state, fighter) == 3
        _place(state, "P1", _get_card(repo, "TWI", "62"), "ground")   # ENEMY Force
        assert compute_power(state, fighter) == 1
        _place(state, "P0", _get_card(repo, "TWI", "62"), "ground")   # Force/Night
        assert compute_power(state, fighter) == 2 and compute_hp(state, fighter) == 4

    def test_TWI_58_buffed_by_a_friendly_force_upgrade(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "TWI", "58"), "ground")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, fighter) == 1
        # Bolstered Endurance LOF_74 is a Force UPGRADE on a non-Force host.
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "74"), "P0")
        assert compute_power(state, fighter) == 2


class TestDaughterOfDathomirTwi62:
    """TWI_62 — "While this unit is undamaged, it gains Restore 2.\""""

    def test_TWI_62_restore_only_while_undamaged(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        night = _place(state, "P0", _get_card(repo, "TWI", "62"), "ground")
        assert has_keyword(state, night, Keyword.RESTORE)
        assert keyword_value(state, night, Keyword.RESTORE) == 2
        night.damage = 1
        assert not has_keyword(state, night, Keyword.RESTORE)
        assert keyword_value(state, night, Keyword.RESTORE) == 0


class TestTheZilloBeastTwi67:
    """TWI_67 — "When Played: Give each enemy ground unit −5/−0 for this phase.
    When the regroup phase starts: Heal 5 damage from this unit.\""""

    def test_TWI_67_when_played_debuffs_each_enemy_ground_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        zillo = _place(state, "P0", _get_card(repo, "TWI", "67"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _drain(_fire_when_played(state, zillo))
        assert compute_power(state, ground) == 0        # 3 − 5, floored at 0
        assert compute_power(state, space) == 3         # space arena untouched
        assert compute_power(state, friend) == 3        # friendly untouched

    def test_TWI_67_heals_itself_when_the_regroup_phase_starts(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        zillo = _place(state, "P0", _get_card(repo, "TWI", "67"), "ground")
        zillo.damage = 8
        _enter_regroup(state)
        assert state.find_instance(zillo.instance_id)[1].damage == 3


class TestPerilousPositionTwi70:
    """TWI_70 — "When Played: Exhaust attached unit.\""""

    def test_TWI_70_exhausts_its_host_on_play(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        host.exhausted = False
        up = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "70"), "P0")
        state = _drain(_fire_upgrade_played(state, up, host))
        assert state.find_instance(host.instance_id)[1].exhausted is True


# ══════════════════════════════════════════════════════════════════════════════
# twi-set:14 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestUnshakeableWillTwi71:
    """TWI_71 — Upgrade: "Attached unit gains Sentinel.\""""

    def test_TWI_71_host_gains_sentinel_and_taunts_the_arena(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        plain = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        state.active_player_index = 1
        # Before the upgrade: the base and both P0 units are attackable.
        before = {a.defender_id for a in legal_actions(state)
                  if isinstance(a, AttackWithUnit)
                  and a.attacker_id == attacker.instance_id}
        assert plain.instance_id in before and None in before
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "71"), "P0")
        assert has_keyword(state, host, Keyword.SENTINEL) is True
        after = {a.defender_id for a in legal_actions(state)
                 if isinstance(a, AttackWithUnit)
                 and a.attacker_id == attacker.instance_id}
        assert after == {host.instance_id}      # Sentinel soaks up every attack


class TestGrievousReassemblyTwi73:
    """TWI_73 — Event: "Heal 3 damage from a unit. Create a Battle Droid token.\""""

    def test_TWI_73_heals_the_chosen_unit_and_creates_a_droid(self, repo):
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 5
        state, _ = _play_event_from_hand(state, repo, "TWI", "73")
        state = _drain(_choose_target(state, hurt.instance_id))
        assert state.find_instance(hurt.instance_id)[1].damage == 2
        droids = [u for u in state.player_by_id("P0").ground_arena
                  if "Battle Droid" in u.card_def.display_name]
        assert len(droids) == 1


class TestGuardingTheWayTwi74:
    """TWI_74 — Event: "Give a unit Sentinel for this phase. If you have the
    initiative, also give that unit +2/+2 for this phase.\""""

    def test_TWI_74_with_initiative_grants_sentinel_and_the_buff(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()                       # initiative_holder = 0 (P0)
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _ = _play_event_from_hand(state, repo, "TWI", "74")
        state = _drain(_choose_target(state, unit.instance_id))
        live = state.find_instance(unit.instance_id)[1]
        assert has_keyword(state, live, Keyword.SENTINEL) is True
        assert compute_power(state, live) == 5 and compute_hp(state, live) == 9

    def test_TWI_74_without_initiative_grants_sentinel_only(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        state.initiative_holder = 1                 # the opponent holds it
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "74")
        state = _drain(_choose_target(state, unit.instance_id))
        live = state.find_instance(unit.instance_id)[1]
        assert has_keyword(state, live, Keyword.SENTINEL) is True
        assert compute_power(state, live) == 3 and compute_hp(state, live) == 7


class TestDroidCommandoTwi81:
    """TWI_81 — "While you control another Separatist unit, this unit gains
    Ambush.\""""

    def test_TWI_81_gains_ambush_only_beside_another_separatist(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        commando = _place(state, "P0", _get_card(repo, "TWI", "81"), "ground")
        assert has_keyword(state, commando, Keyword.AMBUSH) is False
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # not Separatist
        assert has_keyword(state, commando, Keyword.AMBUSH) is False
        _place(state, "P0", _get_card(repo, "TWI", "85"), "ground")    # Kalani, Separatist
        assert has_keyword(state, commando, Keyword.AMBUSH) is True


class TestKalaniTwi85:
    """TWI_85 — "On Attack: You may choose another unit. If you have the initiative,
    you may choose up to 2 other units instead. Give each chosen unit +2/+2 for this
    phase.\""""

    def _setup(self, repo, initiative=0):
        state = _make_state()
        state.initiative_holder = initiative
        kalani = _place(state, "P0", _get_card(repo, "TWI", "85"), "ground")
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        b = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        return state, kalani, a, b

    def test_TWI_85_with_initiative_buffs_up_to_two_other_units(self, repo):
        from swu.engine.actions import (legal_actions, apply, compute_power,
                                        compute_hp, SelectTokenTarget)
        state, kalani, a, b = self._setup(repo, initiative=0)
        state = _fire_on_attack(state, kalani)
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.context["remaining"] == 2
        # "another unit" — Kalani herself is never offered.
        offered = {act.target_id for act in legal_actions(state)
                   if isinstance(act, SelectTokenTarget)}
        assert kalani.instance_id not in offered
        for uid in (a.instance_id, b.instance_id):
            state = apply(state, next(act for act in legal_actions(state)
                                      if isinstance(act, SelectTokenTarget)
                                      and act.target_id == uid))
        assert not state.pending_decisions
        assert compute_power(state, state.find_instance(a.instance_id)[1]) == 5
        assert compute_hp(state, state.find_instance(b.instance_id)[1]) == 3
        assert compute_power(state, state.find_instance(kalani.instance_id)[1]) == 5

    def test_TWI_85_without_initiative_buffs_only_one(self, repo):
        state, kalani, _a, _b = self._setup(repo, initiative=1)
        state = _fire_on_attack(state, kalani)
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.context["remaining"] == 1

    def test_TWI_85_may_decline_every_choice(self, repo):
        from swu.engine.actions import legal_actions, apply, compute_power, FinishSelectToken
        state, kalani, a, _b = self._setup(repo, initiative=0)
        state = _fire_on_attack(state, kalani)
        state = apply(state, next(act for act in legal_actions(state)
                                  if isinstance(act, FinishSelectToken)))
        assert not state.pending_decisions
        assert compute_power(state, state.find_instance(a.instance_id)[1]) == 3


class TestRepublicDefenseCarrierTwi98:
    """TWI_98 — "This unit costs 1 resource less to play for each unit controlled by
    the opponent who controls the most units.\""""

    def test_TWI_98_discount_scales_with_the_opponents_board(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci = _put_in_hand(state, "P0", _get_card(repo, "TWI", "98"))
        ps = state.player_by_id("P0")
        full = _play_cost(state, ci, ps)          # absolute cost carries an aspect
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # penalty on a
        _place(state, "P1", _get_card(repo, "SOR", "128"), "space")   # synthetic base
        assert _play_cost(state, ci, ps) == full - 2
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # ours don't count
        assert _play_cost(state, ci, ps) == full - 2

    def test_TWI_98_cost_is_floored_at_zero(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci = _put_in_hand(state, "P0", _get_card(repo, "TWI", "98"))
        ps = state.player_by_id("P0")
        for _ in range(20):
            _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        assert _play_cost(state, ci, ps) == 0


class TestSteadfastSenatorTwi105:
    """TWI_105 — "Action [2 resources, Exhaust]: Attack with a unit. It gets +2/+0
    for this attack.\""""

    def test_TWI_105_action_costs_two_resources_and_grants_a_buffed_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        senator = _place(state, "P0", _get_card(repo, "TWI", "105"), "ground")
        senator.exhausted = False
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert not any(isinstance(a, UseAbility)
                       and a.source_id == senator.instance_id
                       for a in legal_actions(state))     # can't afford it yet
        _give_resources(state, "P0", 2)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == senator.instance_id)
        state = apply(state, act)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 2 and top.context["hp_bonus"] == 0
        assert state.find_instance(senator.instance_id)[1].exhausted is True
        assert sum(1 for r in state.player_by_id("P0").resources if not r.exhausted) == 0


# ── twi-set:15 — Combat tricks, buffs & tempo ─────────────────────────────────


class TestNamelessValorTwi119:
    """TWI_119 — "Attach to a token unit.  Attached unit gains Overwhelm.\""""

    def _token(self, state, owner_id="P0"):
        from swu.engine.actions import _create_token_units
        ps = state.player_by_id(owner_id)
        return _create_token_units(state, ps, "Clone Trooper", 1)[0]

    def test_TWI_119_only_a_token_unit_is_a_legal_host(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        token = self._token(state)
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _put_in_hand(state, "P0", _get_card(repo, "TWI", "119"))
        _give_resources(state, "P0", 10)
        hosts = {a.upgrade_target_id for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == upg.instance_id}
        assert hosts == {token.instance_id}
        assert plain.instance_id not in hosts

    def test_TWI_119_grants_overwhelm_to_its_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        token = self._token(state)
        # The upgrade's own printed Overwhelm never transfers on its own — only the
        # registered upgrade-SELF KeywordGrant does.
        assert has_keyword(state, token, Keyword.OVERWHELM) is False
        _attach_upgrade_directly(state, token, _get_card(repo, "TWI", "119"), "P0")
        assert has_keyword(state, token, Keyword.OVERWHELM) is True


class TestStrategicAcumenTwi120:
    """TWI_120 — "Attached unit gains: 'Action [Exhaust]: Play a unit from your
    hand.  It costs 1 resource less.'\""""

    def _setup(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        host.exhausted = False
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "120"), "P0")
        _give_resources(state, "P0", 10)
        return state, host, upg

    def test_TWI_120_action_is_not_offered_with_no_playable_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state, _host, upg = self._setup(repo)
        assert not any(isinstance(a, UseAbility) and a.source_id == upg.instance_id
                       for a in legal_actions(state))

    def test_TWI_120_exhausts_the_host_and_plays_a_unit_at_one_off(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state, host, upg = self._setup(repo)
        _put_in_hand(state, "P0", _get_card(repo, "TWI", "241"))   # a 2-cost unit
        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == upg.instance_id)
        state = apply(state, act)
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert top.context["cost_reduction"] == 1
        # "Exhaust" is the HOST's exhaust, not the upgrade's.
        assert state.find_instance(host.instance_id)[1].exhausted is True


class TestSquadSupportTwi122:
    """TWI_122 — "Attached unit gains: 'This unit gets +1/+1 for each Trooper unit
    you control.'\""""

    def test_TWI_122_scales_with_the_controllers_trooper_count(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7 Trooper
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "122"), "P0")
        # "each Trooper unit you control" is not "each other" — the host counts itself.
        assert compute_power(state, host) == 4 and compute_hp(state, host) == 8
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")          # 2nd Trooper
        assert compute_power(state, host) == 5 and compute_hp(state, host) == 9
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")          # enemy: no
        assert compute_power(state, host) == 5
        _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")           # non-Trooper
        assert compute_power(state, host) == 5


class TestInDefenseOfKaminoTwi129:
    """TWI_129 — "For this phase, each friendly Republic unit gains Restore 2 and:
    'When Defeated: Create a Clone Trooper token.'\""""

    def _defeat(self, state, ci, controller_id):
        """Defeat through the real engine path — ``_defeat_and_fire`` homes the
        dying unit in the discard first, which would fail the aura's arena match."""
        from swu.engine.actions import _defeat_unit
        _defeat_unit(state, state.player_by_id(controller_id), ci)
        return state

    def test_TWI_129_grants_restore_2_to_friendly_republic_units_only(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        rep = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")    # Republic
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        enemy = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "129")
        assert keyword_value(state, _find_instance(state, rep.instance_id),
                             Keyword.RESTORE) == 2
        assert has_keyword(state, _find_instance(state, other.instance_id),
                           Keyword.RESTORE) is False
        assert has_keyword(state, _find_instance(state, enemy.instance_id),
                           Keyword.RESTORE) is False

    def test_TWI_129_defeated_republic_unit_creates_a_clone_trooper(self, repo):
        state = _make_state()
        rep = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        state, evt = _play_event_from_hand(state, repo, "TWI", "129")
        assert evt.instance_id in state.game_memory.phase_aura_sources
        before = len(_clone_troopers(state, "P0"))
        state = self._defeat(state, _find_instance(state, rep.instance_id), "P0")
        assert len(_clone_troopers(state, "P0")) == before + 1

    def test_TWI_129_grant_is_phase_scoped_and_skips_non_republic(self, repo):
        state = _make_state()
        imp = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # Imperial
        rep = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "129")
        state = self._defeat(state, _find_instance(state, imp.instance_id), "P0")
        assert _clone_troopers(state, "P0") == []      # not a Republic unit
        state.game_memory.clear_phase()                # "for this phase" ends here
        state = self._defeat(state, _find_instance(state, rep.instance_id), "P0")
        assert _clone_troopers(state, "P0") == []


class TestBoKatanKryzeTwi130:
    """TWI_130 — "While you control another Mandalorian unit, this unit gains
    Overwhelm and Saboteur.  While you control another Trooper unit, this unit gets
    +1/+0.\""""

    def test_TWI_130_each_clause_needs_another_unit_of_that_trait(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import compute_power
        state = _make_state()
        bo = _place(state, "P0", _get_card(repo, "TWI", "130"), "ground")
        # Bo-Katan is herself Mandalorian AND Trooper; "another" excludes her, and
        # the sanitiser strips her printed keywords because we grant them here.
        assert has_keyword(state, bo, Keyword.OVERWHELM) is False
        assert has_keyword(state, bo, Keyword.SABOTEUR) is False
        assert compute_power(state, bo) == 2
        # A Mandalorian non-Trooper turns on both keywords, but not the buff.
        _place(state, "P0", _get_card(repo, "TWI", "54"), "ground")
        assert has_keyword(state, bo, Keyword.OVERWHELM) is True
        assert has_keyword(state, bo, Keyword.SABOTEUR) is True
        assert compute_power(state, bo) == 2
        # A Trooper turns on the +1/+0.
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        assert compute_power(state, bo) == 3

    def test_TWI_130_enemy_units_of_those_traits_do_not_count(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import compute_power
        state = _make_state()
        bo = _place(state, "P0", _get_card(repo, "TWI", "130"), "ground")
        _place(state, "P1", _get_card(repo, "TWI", "54"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        assert has_keyword(state, bo, Keyword.OVERWHELM) is False
        assert compute_power(state, bo) == 2


class TestAsajjVentressTwi134:
    """TWI_134 — "On Attack: If you've attacked with another Separatist unit this
    phase, this unit gets +3/+0 for this phase.\""""

    def test_TWI_134_no_buff_without_a_prior_separatist_attacker(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "TWI", "134"), "ground")
        asajj.exhausted = False
        state = _fire_on_attack(state, asajj)
        assert compute_power(state, _find_instance(state, asajj.instance_id)) == 2

    def test_TWI_134_buffs_after_another_separatist_attacked(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "TWI", "134"), "ground")
        asajj.exhausted = False
        ally = _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")  # Separatist
        ally.exhausted = False
        state = _resolve_attack(state, ally.instance_id, None)   # ally hits the base
        state = _fire_on_attack(state, _find_instance(state, asajj.instance_id))
        assert compute_power(state, _find_instance(state, asajj.instance_id)) == 5

    def test_TWI_134_a_non_separatist_attacker_does_not_arm_it(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "TWI", "134"), "ground")
        asajj.exhausted = False
        ally = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        ally.exhausted = False
        state = _resolve_attack(state, ally.instance_id, None)
        state = _fire_on_attack(state, _find_instance(state, asajj.instance_id))
        assert compute_power(state, _find_instance(state, asajj.instance_id)) == 2


class TestSavageOpressTwi137:
    """TWI_137 — "When Played: If you control fewer units (including this one) than
    an opponent, ready this unit.\""""

    def test_TWI_137_does_not_ready_when_unit_counts_are_equal(self, repo):
        state = _make_state()
        savage = _place(state, "P0", _get_card(repo, "TWI", "137"), "ground")
        savage.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")   # 1 vs 1
        state = _fire_when_played(state, savage)
        assert _find_instance(state, savage.instance_id).exhausted is True

    def test_TWI_137_readies_itself_when_the_opponent_has_more_units(self, repo):
        state = _make_state()
        savage = _place(state, "P0", _get_card(repo, "TWI", "137"), "ground")
        savage.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")   # 1 vs 2
        state = _fire_when_played(state, savage)
        assert _find_instance(state, savage.instance_id).exhausted is False



# ── twi-set:16 — Combat tricks, buffs & tempo ────────────────────────────────


def _select_token_options(state):
    """Instance ids currently offered by a pending ``select_token`` decision."""
    from swu.engine.actions import legal_actions, SelectTokenTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, SelectTokenTarget)}


def _select_token(state, instance_id):
    from swu.engine.actions import legal_actions, apply, SelectTokenTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, SelectTokenTarget) and a.target_id == instance_id)
    return apply(state, act)


class TestCornerThePreyTwi139:
    """TWI_139 — "Attack with a unit.  It gets +1/+0 for this attack for each damage
    on the defender at the start of this attack.\""""

    def test_TWI_139_bonus_scales_with_damage_already_on_the_defender(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # 3/2
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        defender.damage = 3          # 4 remaining HP
        state, _evt = _play_event_from_hand(state, repo, "TWI", "139")
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = _resolve_attack(state, attacker.instance_id, defender.instance_id)
        # 3 power + 3 (one per damage already on it) = 6 ≥ the 4 remaining HP.
        assert _find_instance(state, defender.instance_id) is None
        assert state.find_instance(defender.instance_id)[1].zone == Zone.DISCARD

    def test_TWI_139_undamaged_defender_grants_no_bonus(self, repo):
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # 3/2
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        state, _evt = _play_event_from_hand(state, repo, "TWI", "139")
        state = _resolve_attack(state, attacker.instance_id, defender.instance_id)
        survivor = _find_instance(state, defender.instance_id)
        assert survivor is not None and survivor.damage == 3   # bare power, no bonus


class TestJynErsoTwi143:
    """TWI_143 — "While an enemy unit has been defeated this phase, this unit gets
    +1/+0 and gains Saboteur.\""""

    def test_TWI_143_buff_and_saboteur_arm_on_an_enemy_defeat(self, repo):
        from swu.engine.actions import compute_power, _defeat_unit
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        jyn = _place(state, "P0", _get_card(repo, "TWI", "143"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        # The printed Saboteur is stripped by the sanitiser — we model it as a
        # conditional self-grant, so it is OFF until an enemy dies.
        assert has_keyword(state, jyn, Keyword.SABOTEUR) is False
        assert compute_power(state, jyn) == 3
        _defeat_unit(state, state.player_by_id("P1"), enemy)
        jyn = _find_instance(state, jyn.instance_id)
        assert has_keyword(state, jyn, Keyword.SABOTEUR) is True
        assert compute_power(state, jyn) == 4

    def test_TWI_143_a_friendly_defeat_does_not_arm_it(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        jyn = _place(state, "P0", _get_card(repo, "TWI", "143"), "ground")
        _mark_unit_defeated_this_phase(state, "P0")     # one of OUR units died
        assert has_keyword(state, jyn, Keyword.SABOTEUR) is False
        assert compute_power(state, jyn) == 3


class TestBoldResistanceTwi153:
    """TWI_153 — "Choose up to 3 units that share the same Trait.  Each of those
    units gets +2/+0 for this phase.\""""

    def _board(self, repo):
        state = _make_state()
        clone = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # Rep/Clone/Trooper
        consular = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper
        drone = _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")   # Separatist
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # Imperial/Trooper
        return state, clone, consular, drone, enemy

    def test_TWI_153_later_picks_must_share_a_trait_with_the_first(self, repo):
        state, clone, consular, drone, enemy = self._board(repo)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "153")
        assert state.pending_decisions[-1].kind == "select_token"
        # Nothing is chosen yet, so every unit on the board is a legal first pick
        # (the text says "units", not "friendly units").
        assert _select_token_options(state) == {
            clone.instance_id, consular.instance_id,
            drone.instance_id, enemy.instance_id}
        state = _select_token(state, clone.instance_id)
        # Republic/Clone/Trooper — only the two other Troopers still qualify.
        assert _select_token_options(state) == {consular.instance_id,
                                                enemy.instance_id}

    def test_TWI_153_buffs_each_chosen_unit_and_stops_at_three(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state, clone, consular, drone, enemy = self._board(repo)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "153")
        state = _select_token(state, clone.instance_id)
        state = _select_token(state, consular.instance_id)
        state = _select_token(state, enemy.instance_id)
        # Third pick hits the cap — the decision resolves itself.
        assert not state.pending_decisions
        assert compute_power(state, _find_instance(state, clone.instance_id)) == 5
        assert compute_hp(state, _find_instance(state, clone.instance_id)) == 2
        assert compute_power(state, _find_instance(state, consular.instance_id)) == 5
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 5
        assert compute_power(state, _find_instance(state, drone.instance_id)) == 1


class TestRelentlessRocketDroidTwi163:
    """TWI_163 — "While you control another Trooper unit, this unit gets +2/+0.\""""

    def test_TWI_163_needs_another_friendly_trooper(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "TWI", "163"), "ground")  # 3/5 Trooper
        # It is itself a Trooper, but "another" excludes the source.
        assert compute_power(state, droid) == 3
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")   # enemy Trooper
        assert compute_power(state, droid) == 3
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # friendly Trooper
        assert compute_power(state, droid) == 5


class TestAurraSingTwi166:
    """TWI_166 — "When an enemy ground unit attacks your base: Ready this unit.\""""

    def test_TWI_166_readies_when_an_enemy_ground_unit_attacks_your_base(self, repo):
        state = _make_state()
        aurra = _place(state, "P0", _get_card(repo, "TWI", "166"), "ground")
        aurra.exhausted = True
        attacker = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, attacker)       # base attack (defender None)
        state = _drain(state)
        assert _find_instance(state, aurra.instance_id).exhausted is False

    def test_TWI_166_a_space_attacker_leaves_her_exhausted(self, repo):
        state = _make_state()
        aurra = _place(state, "P0", _get_card(repo, "TWI", "166"), "ground")
        aurra.exhausted = True
        attacker = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        state = _fire_on_attack(state, attacker)
        state = _drain(state)
        assert _find_instance(state, aurra.instance_id).exhausted is True

    def test_TWI_166_your_own_base_attack_does_not_ready_her(self, repo):
        state = _make_state()
        aurra = _place(state, "P0", _get_card(repo, "TWI", "166"), "ground")
        aurra.exhausted = True
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, friendly)       # WE are attacking THEIR base
        state = _drain(state)
        assert _find_instance(state, aurra.instance_id).exhausted is True


class TestCloneCohortTwi169:
    """TWI_169 — "Attached unit gains Raid 2 and: 'When Defeated: Create a Clone
    Trooper token.'\""""

    def test_TWI_169_grants_raid_2_to_its_host(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, host, Keyword.RAID) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "169"), "P0")
        assert has_keyword(state, host, Keyword.RAID) is True
        assert keyword_value(state, host, Keyword.RAID) == 2
        # The grant is host-scoped, not an aura.
        assert has_keyword(state, other, Keyword.RAID) is False

    def test_TWI_169_defeated_host_creates_a_clone_trooper(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "169"), "P0")
        before = len(_clone_troopers(state, "P0"))
        _defeat_unit(state, state.player_by_id("P0"), host)
        state = _drain(state)
        # The granted When Defeated is collected from the just-detached upgrade.
        assert len(_clone_troopers(state, "P0")) == before + 1

    def test_TWI_169_a_bare_host_creates_nothing(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), host)
        state = _drain(state)
        assert _clone_troopers(state, "P0") == []


class TestGrimResolveTwi172:
    """TWI_172 — "Attack with a non-leader unit.  It gains Grit for this attack.\""""

    def test_TWI_172_only_non_leader_units_are_offered(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        leader = _place_deployed_leader(state, "P0", _get_card(repo, "TWI", "11"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "172")
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert unit.instance_id in attackers
        assert leader.instance_id not in attackers

    def test_TWI_172_grants_grit_for_that_attack(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        attacker.damage = 3                       # Grit turns it into a 6-power hit
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        defender.damage = 1                       # 6 remaining HP
        state, _evt = _play_event_from_hand(state, repo, "TWI", "172")
        state = _resolve_attack(state, attacker.instance_id, defender.instance_id)
        # 3 base + 3 from Grit = 6, exactly lethal on the chipped defender.
        assert _find_instance(state, defender.instance_id) is None
        assert state.find_instance(defender.instance_id)[1].zone == Zone.DISCARD



# ── twi-set:17 — Combat tricks, buffs & tempo ────────────────────────────────


def _exhaust_all_resources(state, owner_id):
    for r in state.player_by_id(owner_id).resources:
        r.exhausted = True


class TestPlanetaryInvasionTwi178:
    """TWI_178 — "Ready up to 3 units.  Each of those units gets +1/+0 and gains
    Overwhelm for this phase.\""""

    def test_TWI_178_readies_buffs_and_grants_overwhelm_per_pick(self, repo):
        from swu.engine.actions import compute_power, apply, ExploitCommit
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # 3/2
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # 3/7
        idle = _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")  # untouched
        for ci in (a, b, idle):
            ci.exhausted = True
        state, _evt = _play_event_from_hand(state, repo, "TWI", "178", resources=15)
        # Exploit 3 asks first ("defeat up to 3 units you control") — commit with
        # no sacrifices and pay full price; the payoff half is what we're testing.
        assert state.pending_decisions[-1].kind == "exploit"
        state = apply(state, ExploitCommit())
        assert state.pending_decisions[-1].kind == "select_token"
        state = _select_token(state, a.instance_id)
        state = _select_token(state, b.instance_id)
        for chosen, base_power in ((a, 3), (b, 3)):
            ci = _find_instance(state, chosen.instance_id)
            assert ci.exhausted is False
            assert compute_power(state, ci) == base_power + 1
            assert has_keyword(state, ci, Keyword.OVERWHELM) is True
        # An unchosen unit gets none of the three payoffs.
        untouched = _find_instance(state, idle.instance_id)
        assert untouched.exhausted is True
        assert compute_power(state, untouched) == 1
        assert has_keyword(state, untouched, Keyword.OVERWHELM) is False


class TestRushClovisTwi183:
    """TWI_183 — "On Attack: If the defending player controls no ready resources,
    create a Battle Droid token.\""""

    def test_TWI_183_no_droid_while_the_defender_has_a_ready_resource(self, repo):
        state = _make_state()
        clovis = _place(state, "P0", _get_card(repo, "TWI", "183"), "ground")
        _give_resources(state, "P1", 2)
        state = _drain(_fire_on_attack(state, clovis))
        assert _battle_droids(state, "P0") == []

    def test_TWI_183_creates_a_droid_against_a_tapped_out_defender(self, repo):
        state = _make_state()
        clovis = _place(state, "P0", _get_card(repo, "TWI", "183"), "ground")
        _give_resources(state, "P1", 2)
        _exhaust_all_resources(state, "P1")
        state = _drain(_fire_on_attack(state, clovis))
        assert len(_battle_droids(state, "P0")) == 1


class TestZiroTheHuttTwi185:
    """TWI_185 — "When Played: … you may exhaust a unit that player controls." /
    "On Attack: … you may exhaust a resource that player controls.\""""

    def test_TWI_185_when_played_may_exhaust_an_enemy_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        ziro = _place(state, "P0", _get_card(repo, "TWI", "185"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, ziro)
        state = _accept(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {enemy.instance_id}        # "a unit that player controls"
        assert friendly.instance_id not in offered
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)))
        assert _find_instance(state, enemy.instance_id).exhausted is True

    def test_TWI_185_on_attack_exhausts_an_enemy_resource(self, repo):
        state = _make_state()
        ziro = _place(state, "P0", _get_card(repo, "TWI", "185"), "ground")
        _give_resources(state, "P1", 3)
        _give_resources(state, "P0", 3)
        state = _fire_on_attack(state, ziro)
        state = _accept(state)
        assert state.player_by_id("P1").available_resources == 2
        assert state.player_by_id("P0").available_resources == 3   # only theirs

    def test_TWI_185_on_attack_may_be_declined(self, repo):
        state = _make_state()
        ziro = _place(state, "P0", _get_card(repo, "TWI", "185"), "ground")
        _give_resources(state, "P1", 3)
        state = _fire_on_attack(state, ziro)
        state = _decline(state)
        assert state.player_by_id("P1").available_resources == 3


class TestSanHillTwi186:
    """TWI_186 — "On Attack: For each friendly unit that was defeated this phase,
    ready a friendly resource.\""""

    def test_TWI_186_readies_one_resource_per_friendly_unit_lost(self, repo):
        state = _make_state()
        hill = _place(state, "P0", _get_card(repo, "TWI", "186"), "ground")
        _give_resources(state, "P0", 4)
        _exhaust_all_resources(state, "P0")
        _mark_unit_defeated_this_phase(state, "P0")
        _mark_unit_defeated_this_phase(state, "P0")
        _mark_unit_defeated_this_phase(state, "P1")   # an ENEMY loss doesn't count
        state = _drain(_fire_on_attack(state, hill))
        assert state.player_by_id("P0").available_resources == 2

    def test_TWI_186_readies_nothing_with_no_friendly_losses(self, repo):
        state = _make_state()
        hill = _place(state, "P0", _get_card(repo, "TWI", "186"), "ground")
        _give_resources(state, "P0", 3)
        _exhaust_all_resources(state, "P0")
        state = _drain(_fire_on_attack(state, hill))
        assert state.player_by_id("P0").available_resources == 0


class TestAhsokaTanoTwi194:
    """TWI_194 — conditional Ambush + "Action [2 resources]: Return this unit and
    each upgrade on her to their owners' hands.\""""

    def test_TWI_194_ambush_only_while_behind_on_units(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "TWI", "194"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        # 1 vs 1 — the printed Ambush is stripped by the sanitiser and the
        # conditional grant is OFF (the mirror condition, not its negation).
        assert has_keyword(state, ahsoka, Keyword.AMBUSH) is False
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        assert has_keyword(state, ahsoka, Keyword.AMBUSH) is True

    def test_TWI_194_action_returns_her_and_her_upgrades_to_hand(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "TWI", "194"), "ground")
        upg = _attach_upgrade_directly(state, ahsoka, _get_card(repo, "SHD", "74"), "P0")
        _give_resources(state, "P0", 2)
        state = _drain(_use_ability(state, ahsoka))
        hand_ids = {ci.instance_id for ci in state.player_by_id("P0").hand}
        assert ahsoka.instance_id in hand_ids
        # The upgrade goes to HAND, not the discard the default detach rule uses.
        assert upg.instance_id in hand_ids
        assert state.find_instance(upg.instance_id)[1].zone == Zone.HAND
        assert _find_instance(state, ahsoka.instance_id) is None


class TestRepublicAttackPodTwi197:
    """TWI_197 — "If you control 3 or more units, this unit costs 1 resource
    less to play.\""""

    def test_TWI_197_costs_one_less_with_three_units_in_play(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        pod = _put_in_hand(state, "P0", _get_card(repo, "TWI", "197"))
        full = _play_cost(state, pod, ps)          # aspect penalty included
        for _ in range(2):
            _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        assert _play_cost(state, pod, ps) == full  # 2 units — not yet
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        assert _play_cost(state, pod, ps) == full - 1


class TestCreativeThinkingTwi200:
    """TWI_200 — "Exhaust a non-unique unit.  Create a Clone Trooper token.\""""

    def test_TWI_200_exhausts_a_non_unique_unit_and_makes_a_token(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        plain = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        unique = _place(state, "P1", _get_card(repo, "TWI", "143"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "200")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert plain.instance_id in offered
        assert unique.instance_id not in offered
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == plain.instance_id))
        state = _drain(state)
        assert _find_instance(state, plain.instance_id).exhausted is True
        assert len(_clone_troopers(state, "P0")) == 1



# ── twi-set:18 — Combat tricks, buffs & tempo ────────────────────────────────


def _choose_modal_target(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseModalTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, ChooseModalTarget) and a.target_id == target_id)
    return apply(state, act)


def _controller_of(state, instance_id):
    """The player whose arena currently HOLDS the instance (= its controller)."""
    for ps in state.players:
        for ci in ps.ground_arena + ps.space_arena:
            if ci.instance_id == instance_id:
                return ps.player_id
    return None


class TestChancellorPalpatineTwi203:
    """TWI_203 — "Each token unit you create enters play ready." / "On Attack: If a
    unit left play this phase, create a Clone Trooper token.\""""

    def test_TWI_203_tokens_you_create_enter_ready(self, repo):
        from swu.engine.actions import _create_token_units
        state = _make_state()
        ps = state.player_by_id("P0")
        # Without him, the default: a created token enters EXHAUSTED.
        assert _create_token_units(state, ps, "Clone Trooper", 1)[0].exhausted is True
        _place(state, "P0", _get_card(repo, "TWI", "203"), "ground")
        assert _create_token_units(state, ps, "Clone Trooper", 1)[0].exhausted is False
        # Controller-scoped: the opponent's tokens are unaffected.
        opp = state.player_by_id("P1")
        assert _create_token_units(state, opp, "Clone Trooper", 1)[0].exhausted is True

    def test_TWI_203_on_attack_creates_a_token_only_after_a_defeat(self, repo):
        state = _make_state()
        palp = _place(state, "P0", _get_card(repo, "TWI", "203"), "ground")
        state = _drain(_fire_on_attack(state, palp))
        assert _clone_troopers(state, "P0") == []
        _mark_unit_defeated_this_phase(state, "P1")   # "a unit left play" — either side
        state = _drain(_fire_on_attack(state, _find_instance(state, palp.instance_id)))
        troopers = _clone_troopers(state, "P0")
        assert len(troopers) == 1
        assert troopers[0].exhausted is False         # …and his own marker readies it


class TestImproprietyAmongThievesTwi204:
    """TWI_204 — "Choose a ready non-leader unit controlled by each player. … each
    player takes control of the chosen unit controlled by the player to their
    right.  At the start of the regroup phase, [they revert].\""""

    def test_TWI_204_swaps_control_of_the_two_chosen_units(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        exhausted = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        exhausted.exhausted = True
        state, _evt = _play_event_from_hand(state, repo, "TWI", "204")
        # Only READY non-leader units are offered on the enemy side.
        offered = _target_ids(state)
        assert theirs.instance_id in offered
        assert exhausted.instance_id not in offered
        state = _choose_target(state, theirs.instance_id)
        state = _choose_target(state, mine.instance_id)
        assert _controller_of(state, theirs.instance_id) == "P0"
        assert _controller_of(state, mine.instance_id) == "P1"
        # Ownership never moves — only occupancy.
        assert state.find_instance(theirs.instance_id)[1].owner_id == "P1"

    def test_TWI_204_both_units_go_home_at_regroup(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_deck_cards(state, "P0", repo, 4)
        _add_deck_cards(state, "P1", repo, 4)
        state, _evt = _play_event_from_hand(state, repo, "TWI", "204")
        state = _choose_target(state, theirs.instance_id)
        state = _choose_target(state, mine.instance_id)
        _enter_regroup(state)
        assert _controller_of(state, theirs.instance_id) == "P1"
        assert _controller_of(state, mine.instance_id) == "P0"


class TestLuxBonteriTwi210:
    """TWI_210 — "When an opponent plays a card: If that opponent paid less than the
    card's cost to play it, ready or exhaust a unit.\""""

    def _play_for(self, state, repo, set_code, num, owner, paid):
        """Fire the CardPlayed observer for a card the opponent played at ``paid``."""
        from swu.engine.events import CardPlayed
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.state import CardInstance, Zone
        card = _get_card(repo, set_code, num)
        ci = CardInstance(f"{owner}_played_{num}", card, owner, Zone.GROUND_ARENA)
        state.player_by_id(owner).ground_arena.append(ci)
        evt = CardPlayed(player_id=owner, instance_id=ci.instance_id,
                         card_name=card.display_name, cost_paid=paid)
        state.event_log.append(evt)
        fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx={})
        return state, ci

    def test_TWI_210_no_trigger_when_the_opponent_paid_full_price(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "210"), "ground")
        state, _ci = self._play_for(state, repo, "SOR", "46", "P1", 4)   # printed 4
        assert not state.pending_decisions

    def test_TWI_210_discounted_play_offers_ready_or_exhaust(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "210"), "ground")
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        mine.exhausted = True
        state, _ci = self._play_for(state, repo, "SOR", "46", "P1", 2)   # 2 < 4
        state = _drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "modal"
        modes = {a.mode for a in legal_actions(state)
                 if isinstance(a, ChooseModalOption)}
        assert "ready_unit" in modes and "exhaust_unit" in modes
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseModalOption)
                                  and a.mode == "ready_unit"))
        state = _choose_modal_target(state, mine.instance_id)
        assert _find_instance(state, mine.instance_id).exhausted is False


class TestSlyMooreTwi211:
    """TWI_211 — "When Played: Take control of an enemy token unit and ready it.  At
    the start of the regroup phase, that token unit's owner takes control of it.\""""

    def _enemy_token(self, state):
        from swu.engine.actions import _create_token_units
        return _create_token_units(state, state.player_by_id("P1"), "Clone Trooper", 1)[0]

    def test_TWI_211_steals_and_readies_an_enemy_token(self, repo):
        state = _make_state()
        token = self._enemy_token(state)
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        sly = _place(state, "P0", _get_card(repo, "TWI", "211"), "ground")
        state = _fire_when_played(state, sly)
        offered = _target_ids(state)
        assert offered == {token.instance_id}       # token units only
        assert plain.instance_id not in offered
        state = _choose_target(state, token.instance_id)
        assert _controller_of(state, token.instance_id) == "P0"
        assert state.find_instance(token.instance_id)[1].exhausted is False
        assert state.find_instance(token.instance_id)[1].owner_id == "P1"

    def test_TWI_211_the_token_goes_home_at_regroup(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        token = self._enemy_token(state)
        sly = _place(state, "P0", _get_card(repo, "TWI", "211"), "ground")
        _add_deck_cards(state, "P0", repo, 4)
        _add_deck_cards(state, "P1", repo, 4)
        state = _fire_when_played(state, sly)
        state = _choose_target(state, token.instance_id)
        _enter_regroup(state)
        assert _controller_of(state, token.instance_id) == "P1"


class TestBreakingInTwi224:
    """TWI_224 — "Attack with a unit.  It gets +2/+0 and gains Saboteur for this
    attack.\""""

    def test_TWI_224_attacker_gets_two_power_and_saboteur(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # 3/2
        # A Sentinel would normally force the attack onto it; Saboteur ignores it.
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        defender.damage = 2                       # 5 remaining HP
        state, _evt = _play_event_from_hand(state, repo, "TWI", "224")
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = _resolve_attack(state, attacker.instance_id, defender.instance_id)
        assert _find_instance(state, defender.instance_id) is None   # 3+2 = 5, lethal
        assert state.find_instance(defender.instance_id)[1].zone == Zone.DISCARD


class TestHeroesOnBothSidesTwi249:
    """TWI_249 — "Choose up to 1 Republic unit and up to 1 Separatist unit.  Give
    each chosen unit +2/+2 and Saboteur for this phase.\""""

    def test_TWI_249_buffs_one_unit_of_each_trait(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        rep = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # Republic 3/2
        sep = _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")    # Separatist 1/4
        neither = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        state, _evt = _play_event_from_hand(state, repo, "TWI", "249")
        # First choice: only Republic units are offered.
        assert _target_ids(state) == {rep.instance_id}
        state = _choose_target(state, rep.instance_id)
        assert _target_ids(state) == {sep.instance_id}
        state = _choose_target(state, sep.instance_id)
        for ci, p, h in ((rep, 5, 4), (sep, 3, 6)):
            buffed = _find_instance(state, ci.instance_id)
            assert compute_power(state, buffed) == p
            assert compute_hp(state, buffed) == h
            assert has_keyword(state, buffed, Keyword.SABOTEUR) is True
        untouched = _find_instance(state, neither.instance_id)
        assert has_keyword(state, untouched, Keyword.SABOTEUR) is False
        assert compute_power(state, untouched) == 3


class TestVolunteerSoldierTwi254:
    """TWI_254 — "If you control a Trooper unit, this unit costs 1 resource less to
    play.\""""

    def test_TWI_254_costs_one_less_beside_a_trooper(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        soldier = _put_in_hand(state, "P0", _get_card(repo, "TWI", "254"))
        full = _play_cost(state, soldier, ps)
        _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")     # not a Trooper
        assert _play_cost(state, soldier, ps) == full
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")    # Trooper
        assert _play_cost(state, soldier, ps) == full - 1


# ── twi-set:19 — Miscellaneous abilities ─────────────────────────────────────


def _play_card_from_hand(state, ci):
    """Play ``ci`` from its owner's hand through the ordinary PlayCard path."""
    from swu.engine.actions import apply, PlayCard
    return apply(state, PlayCard(ci.instance_id))


class TestNuteGunrayTwi2:
    """TWI_2 — undeployed "Action [Exhaust]: If 2 or more friendly units were
    defeated this phase, create a Battle Droid token"; deployed "On Attack: Create a
    Battle Droid token\"."""

    def test_TWI_2_action_needs_two_friendly_defeats(self, repo):
        state = _make_state()
        nute = _place_leader(state, "P0", _get_leader(repo, "TWI", "2"))
        assert _ability_offered(state, nute) is False
        _mark_unit_defeated_this_phase(state, "P0")
        assert _ability_offered(state, nute) is False      # one is not enough
        _mark_unit_defeated_this_phase(state, "P1")        # an ENEMY loss doesn't count
        assert _ability_offered(state, nute) is False
        _mark_unit_defeated_this_phase(state, "P0")
        assert _ability_offered(state, nute) is True
        state = _drain(_use_ability(state, nute))
        assert len(_battle_droids(state, "P0")) == 1

    def test_TWI_2_deployed_on_attack_creates_a_droid(self, repo):
        state = _make_state()
        nute = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "2"))
        state = _drain(_fire_on_attack(state, nute))
        assert len(_battle_droids(state, "P0")) == 1

    def test_TWI_2_clone_trooper_token_does_not_inherit_the_leader_action(self, repo):
        """(TWI, "2") is also the Clone Trooper token's registry key — the token must
        not offer Nute's undeployed action from the arena."""
        from swu.engine.actions import _create_token_units
        state = _make_state()
        _mark_unit_defeated_this_phase(state, "P0")
        _mark_unit_defeated_this_phase(state, "P0")
        token = _create_token_units(state, state.player_by_id("P0"), "Clone Trooper", 1)[0]
        token.exhausted = False
        assert token.card_def.card_number == "2"          # the collision is real
        assert _ability_offered(state, token) is False


class TestCountDookuTwi5:
    """TWI_5 — undeployed "Action [Exhaust]: Play a Separatist card from your hand.
    It gains Exploit 1"; deployed "On Attack: The next Separatist card you play this
    phase gains Exploit 3\"."""

    def test_TWI_5_on_attack_grants_exploit_to_the_next_separatist_play(self, repo):
        state = _make_state()
        dooku = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "5"))
        vulture = _put_in_hand(state, "P0", _get_card(repo, "TWI", "63"))  # Separatist
        _give_resources(state, "P0", 12)
        state = _drain(_fire_on_attack(state, dooku))
        # A card with NO printed Exploit gains one from the pending grant.
        state = _play_card_from_hand(state, vulture)
        top = state.pending_decisions[-1]
        assert top.kind == "exploit"
        assert top.context["max_remaining"] == 3

    def test_TWI_5_grant_is_one_shot_and_separatist_only(self, repo):
        state = _make_state()
        dooku = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "5"))
        trooper = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))  # Imperial
        _give_resources(state, "P0", 12)
        state = _drain(_fire_on_attack(state, dooku))
        state = _play_card_from_hand(state, trooper)
        assert not state.pending_decisions          # not Separatist — grant untouched
        assert len(state.game_memory.pending_exploit_grants) == 1

    def test_TWI_5_action_plays_a_separatist_card_exploiting_one_unit(self, repo):
        from swu.engine.actions import (legal_actions, apply, _play_cost,
                                        SelectCombinedPowerUnit,
                                        FinishCombinedPowerPlay, PlayFromHand)
        state = _make_state()
        dooku = _place_leader(state, "P0", _get_leader(repo, "TWI", "5"))
        fodder = _filler(state, "P0", repo)
        vulture = _put_in_hand(state, "P0", _get_card(repo, "TWI", "63"))
        _give_resources(state, "P0", 12)
        full = _play_cost(state, vulture, state.player_by_id("P0"))
        ready_before = state.player_by_id("P0").available_resources
        state = _use_ability(state, dooku)
        assert state.pending_decisions[-1].kind == "combined_power_play"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectCombinedPowerUnit)
                                  and a.unit_id == fodder.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishCombinedPowerPlay)))
        assert state.pending_decisions[-1].kind == "play_from_hand"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)
                                  and a.instance_id == vulture.instance_id))
        # Exploit 1 = the sacrificed unit buys 2 resources off the price…
        spent = ready_before - state.player_by_id("P0").available_resources
        assert spent == full - 2
        # …and the exploited unit is gone, while the played unit is in play.
        assert _find_instance(state, fodder.instance_id) is None
        assert _find_instance(state, vulture.instance_id) is not None

    def test_TWI_5_action_plays_at_full_price_with_nothing_to_exploit(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        dooku = _place_leader(state, "P0", _get_leader(repo, "TWI", "5"))
        _put_in_hand(state, "P0", _get_card(repo, "TWI", "63"))
        _give_resources(state, "P0", 12)
        state = _use_ability(state, dooku)
        # No friendly unit to give up — the play is offered directly.
        assert state.pending_decisions[-1].kind == "play_from_hand"
        assert any(isinstance(a, PlayFromHand) for a in legal_actions(state))


class TestDroidManufactoryTwi22:
    """TWI_22 (Base) — "When you deploy a leader: Create 2 Battle Droid tokens\"."""

    def test_TWI_22_deploying_your_leader_makes_two_droids(self, repo):
        state = _make_state()
        _swap_base(state, "P0", _get_card(repo, "TWI", "22"))
        leader = _place_deployed_leader(state, "P0", _get_leader(repo, "TWI", "2"))
        state = _drain(_fire_leader_deployed(state, leader))
        assert len(_battle_droids(state, "P0")) == 2
        assert len(_battle_droids(state, "P1")) == 0

    def test_TWI_22_an_enemy_leader_deploy_does_nothing(self, repo):
        state = _make_state()
        _swap_base(state, "P0", _get_card(repo, "TWI", "22"))
        leader = _place_deployed_leader(state, "P1", _get_leader(repo, "TWI", "2"))
        state = _drain(_fire_leader_deployed(state, leader))
        assert len(_battle_droids(state, "P0")) == 0


class TestRuneHaakoTwi31:
    """TWI_31 — "When Played: If a friendly unit was defeated this phase, you may
    give a unit –1/–1 for this phase\"."""

    def test_TWI_31_no_trigger_without_a_friendly_defeat(self, repo):
        state = _make_state()
        haako = _place(state, "P0", _get_card(repo, "TWI", "31"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _mark_unit_defeated_this_phase(state, "P1")     # enemy loss only
        state = _fire_when_played(state, haako)
        assert not state.pending_decisions

    def test_TWI_31_debuffs_a_unit_after_a_friendly_defeat(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        haako = _place(state, "P0", _get_card(repo, "TWI", "31"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _mark_unit_defeated_this_phase(state, "P0")
        state = _drain(_accept(_fire_when_played(state, haako)))
        state = _choose_target(state, victim.instance_id)
        buffed = _find_instance(state, victim.instance_id)
        assert compute_power(state, buffed) == 2 and compute_hp(state, buffed) == 6


class TestWartimeTradeOfficialTwi32:
    """TWI_32 — "When Defeated: Create a Battle Droid token\"."""

    def test_TWI_32_leaves_a_droid_behind(self, repo):
        state = _make_state()
        official = _place(state, "P0", _get_card(repo, "TWI", "32"), "ground")
        state = _drain(_defeat_and_fire(state, official, "P0"))
        assert len(_battle_droids(state, "P0")) == 1


class TestProvidenceDestroyerTwi38:
    """TWI_38 — "On Attack: Give an enemy space unit –2/–2 for this phase\"."""

    def test_TWI_38_only_enemy_space_units_are_offered(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        prov = _place(state, "P0", _get_card(repo, "TWI", "38"), "space")
        space = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")   # 3/3
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "TWI", "60"), "space")
        state = _fire_on_attack(state, prov)
        offered = _target_ids(state)
        assert offered == {space.instance_id}
        assert ground.instance_id not in offered and friendly.instance_id not in offered
        state = _choose_target(state, space.instance_id)
        hit = _find_instance(state, space.instance_id)
        assert compute_power(state, hit) == 1 and compute_hp(state, hit) == 1


class TestMalevolenceTwi39:
    """TWI_39 — "When Played: Give an enemy unit –4/–0 for this phase.  It can't
    attack for this phase\"."""

    def test_TWI_39_debuffs_and_grounds_the_chosen_enemy(self, repo):
        from swu.engine.actions import compute_power, compute_hp, legal_actions, AttackWithUnit
        state = _make_state()
        mal = _place(state, "P0", _get_card(repo, "TWI", "39"), "space")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        other = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        state = _fire_when_played(state, mal)
        state = _drain(_choose_target(state, victim.instance_id))
        hit = _find_instance(state, victim.instance_id)
        assert compute_power(state, hit) == 0        # 3 - 4, floored at 0
        assert compute_hp(state, hit) == 7           # -4/-0 leaves HP alone
        # It is the chosen unit that can't attack — its neighbour still can.
        state.active_player_index = 1
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert victim.instance_id not in attackers
        assert other.instance_id in attackers


# ── twi-set:20 — Miscellaneous abilities ─────────────────────────────────────


def _fire_attack_ends_twi(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for a surviving attacker (Finn TWI_53)."""
    from swu.engine.events import AttackDeclared
    from swu.abilities.resolver import fire_triggered_abilities
    evt = AttackDeclared(
        attacker_player_id=attacker_ci.owner_id,
        attacker_instance_id=attacker_ci.instance_id,
        attacker_name=attacker_ci.card_def.display_name,
        defender_instance_id=None, defender_name="Base",
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=0,
        event_ctx={"attack_ended_survivor": attacker_ci.instance_id})


class TestCaptainTyphoTwi46:
    """TWI_46 — "When Played/On Attack: Give a unit Sentinel for this phase\"."""

    def test_TWI_46_both_windows_grant_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        typho = _place(state, "P0", _get_card(repo, "TWI", "46"), "ground")
        ally = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        # When Played
        state = _fire_when_played(state, typho)
        state = _drain(_choose_target(state, ally.instance_id))
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL) is True
        # On Attack — the same effect at the second window, on a different unit.
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, _find_instance(state, typho.instance_id))
        state = _drain(_choose_target(state, other.instance_id))
        assert has_keyword(state, _find_instance(state, other.instance_id),
                           Keyword.SENTINEL) is True


class TestKnightOfTheRepublicTwi49:
    """TWI_49 — "When this unit is attacked: Create a Clone Trooper token\"."""

    def test_TWI_49_being_attacked_creates_a_trooper(self, repo):
        state = _make_state()
        knight = _place(state, "P0", _get_card(repo, "TWI", "49"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state.active_player_index = 1
        state = _drain(_resolve_attack(state, attacker.instance_id, knight.instance_id))
        assert len(_clone_troopers(state, "P0")) == 1
        assert len(_clone_troopers(state, "P1")) == 0


class TestHelloThereTwi52:
    """TWI_52 — "Choose a unit that entered play this phase.  It gets –4/–4 for this
    phase\"."""

    def test_TWI_52_only_units_that_entered_play_this_phase(self, repo):
        from swu.engine.actions import compute_power, compute_hp, _create_token_units
        state = _make_state()
        veteran = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        newcomer = _place(state, "P1", _get_card(repo, "TWI", "49"), "ground")  # 4/7
        state.game_memory.units_played_this_phase.add(newcomer.instance_id)
        # A created token entered play this phase too (the same ledger).
        token = _create_token_units(state, state.player_by_id("P1"), "Clone Trooper", 1)[0]
        state, _evt = _play_event_from_hand(state, repo, "TWI", "52")
        offered = _target_ids(state)
        assert offered == {newcomer.instance_id, token.instance_id}
        assert veteran.instance_id not in offered
        state = _choose_target(state, newcomer.instance_id)
        hit = _find_instance(state, newcomer.instance_id)
        assert compute_power(state, hit) == 0 and compute_hp(state, hit) == 3


class TestFinnTwi53:
    """TWI_53 — "When this unit completes an attack: Choose a unique unit.  For this
    phase, if damage would be dealt to that unit, prevent 1 of that damage\"."""

    def test_TWI_53_prevents_one_of_every_damage_instance(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        finn = _place(state, "P0", _get_card(repo, "TWI", "53"), "ground")
        unique = _place(state, "P0", _get_card(repo, "TWI", "96"), "ground")   # unique
        plain = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # not
        state = _fire_attack_ends_twi(state, finn)
        offered = _target_ids(state)
        assert unique.instance_id in offered and finn.instance_id in offered
        assert plain.instance_id not in offered      # only unique units qualify
        state = _drain(_choose_target(state, unique.instance_id))
        # Every instance is reduced by 1, not just the first.
        _apply_deal_damage(state, unique.instance_id, 3)
        _apply_deal_damage(state, unique.instance_id, 1)
        assert _find_instance(state, unique.instance_id).damage == 2


class TestEqualizeTwi55:
    """TWI_55 — "Give a unit –2/–2 for this phase.  Then, if you control fewer units
    than that unit's controller, give another unit –2/–2 for this phase\"."""

    def test_TWI_55_second_debuff_only_when_outnumbered(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        second = _place(state, "P1", _get_card(repo, "TWI", "49"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "55")
        state = _choose_target(state, theirs.instance_id)
        # P0 controls 1 unit, P1 controls 2 → the follow-up is offered, minus the
        # unit already chosen.
        offered = _target_ids(state)
        assert theirs.instance_id not in offered
        assert second.instance_id in offered and mine.instance_id in offered
        state = _drain(_choose_target(state, second.instance_id))
        assert compute_power(state, _find_instance(state, theirs.instance_id)) == 1
        assert compute_power(state, _find_instance(state, second.instance_id)) == 2

    def test_TWI_55_fizzles_the_follow_up_when_not_outnumbered(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "55")
        state = _drain(_choose_target(state, theirs.instance_id))
        # 2 units vs 1 → no second prompt at all.
        assert not state.pending_decisions
        assert compute_power(state, _find_instance(state, theirs.instance_id)) == 1


class TestTradeFederationShuttleTwi60:
    """TWI_60 — "When Played: If you control a damaged unit, create a Battle Droid
    token\"."""

    def test_TWI_60_needs_a_friendly_damaged_unit(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "TWI", "60"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.damage = 2                       # an ENEMY damaged unit doesn't count
        state = _drain(_fire_when_played(state, shuttle))
        assert len(_battle_droids(state, "P0")) == 0
        ally = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        ally.damage = 1
        state = _drain(_fire_when_played(state, _find_instance(state, shuttle.instance_id)))
        assert len(_battle_droids(state, "P0")) == 1


class TestVultureInterceptorWingTwi63:
    """TWI_63 — "On Attack: Give an enemy unit –1/–1 for this phase\"."""

    def test_TWI_63_debuffs_an_enemy_unit_in_either_arena(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "TWI", "63"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        friendly = _place(state, "P0", _get_card(repo, "TWI", "60"), "space")
        state = _fire_on_attack(state, wing)
        offered = _target_ids(state)
        assert ground.instance_id in offered          # the debuff is not arena-bound
        assert friendly.instance_id not in offered
        state = _choose_target(state, ground.instance_id)
        hit = _find_instance(state, ground.instance_id)
        assert compute_power(state, hit) == 2 and compute_hp(state, hit) == 6


# ── twi-set:21 — Miscellaneous abilities ─────────────────────────────────────


def _choose_modal_mode(state, mode):
    from swu.engine.actions import legal_actions, apply, ChooseModalOption
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, ChooseModalOption) and a.mode == mode))


class TestMultiTroopTransportTwi66:
    """TWI_66 — "On Attack: Create a Battle Droid token" (Exploit is the keyword
    layer)."""

    def test_TWI_66_attacking_makes_a_droid(self, repo):
        state = _make_state()
        mtt = _place(state, "P0", _get_card(repo, "TWI", "66"), "ground")
        state = _drain(_fire_on_attack(state, mtt))
        assert len(_battle_droids(state, "P0")) == 1


class TestRogerRogerTwi69:
    """TWI_69 (Upgrade) — "When Defeated: Attach this upgrade to a friendly Battle
    Droid token\"."""

    def test_TWI_69_hops_to_a_battle_droid_when_its_host_dies(self, repo):
        from swu.engine.actions import _defeat_unit, _create_token_units
        from swu.engine.state import Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "69"), "P0")
        droid = _create_token_units(state, ps, "Battle Droid", 1)[0]
        _defeat_unit(state, ps, host)
        state = _drain(state)
        new_host = _find_instance(state, droid.instance_id)
        assert [u.instance_id for u in new_host.attached_upgrades] == [upg.instance_id]
        moved = state.find_instance(upg.instance_id)[1]
        assert moved.zone != Zone.DISCARD
        assert moved not in state.player_by_id("P0").discard

    def test_TWI_69_fizzles_without_a_friendly_battle_droid_token(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        ps = state.player_by_id("P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "69"), "P0")
        # A printed Battle Droid unit is not a Battle Droid TOKEN.
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        _defeat_unit(state, ps, host)
        state = _drain(state)
        assert state.find_instance(upg.instance_id)[1] in state.player_by_id("P0").discard


class TestIHaveTheHighGroundTwi72:
    """TWI_72 — "Choose a friendly unit.  Each enemy unit gets –4/–0 while attacking
    that unit this phase\"."""

    def test_TWI_72_only_blunts_attacks_against_the_chosen_unit(self, repo):
        state = _make_state()
        chosen = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # 3/2
        bystander = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "TWI", "72")
        state = _drain(_choose_target(state, chosen.instance_id))
        # Attacking the protected unit: 3 - 4 → 0 power, so it survives untouched.
        state.active_player_index = 1
        after = _resolve_attack(state, attacker.instance_id, chosen.instance_id)
        survivor = _find_instance(after, chosen.instance_id)
        assert survivor is not None and survivor.damage == 0
        # Attacking anyone else is a normal 3-power swing — lethal on a 3/2.
        state.active_player_index = 1
        other = _resolve_attack(state, attacker.instance_id, bystander.instance_id)
        assert _find_instance(other, bystander.instance_id) is None


class TestDisruptiveBurstTwi75:
    """TWI_75 — "Give each enemy unit –1/–1 for this phase\"."""

    def test_TWI_75_hits_every_enemy_unit_and_no_friendly_one(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # 3/2
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")       # 3/7
        b = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")        # 3/3
        state, _evt = _play_event_from_hand(state, repo, "TWI", "75")
        state = _drain(state)
        for ci, p, h in ((a, 2, 6), (b, 2, 2)):
            hit = _find_instance(state, ci.instance_id)
            assert compute_power(state, hit) == p and compute_hp(state, hit) == h
        untouched = _find_instance(state, mine.instance_id)
        assert compute_power(state, untouched) == 3 and compute_hp(state, untouched) == 2


class TestPeltaSupplyFrigateTwi95:
    """TWI_95 — "Coordinate — When Played: Create a Clone Trooper token\"."""

    def test_TWI_95_token_only_while_coordinating(self, repo):
        state = _make_state()
        pelta = _place(state, "P0", _get_card(repo, "TWI", "95"), "space")
        state = _drain(_fire_when_played(state, pelta))
        assert _clone_troopers(state, "P0") == []        # 1 unit — no Coordinate
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                        # 3 units, incl. this one
        state = _drain(_fire_when_played(state, _find_instance(state, pelta.instance_id)))
        assert len(_clone_troopers(state, "P0")) == 1


class TestAaylaSecuraTwi96:
    """TWI_96 — "Coordinate — On Attack: Prevent all combat damage that would be
    dealt to this unit for this attack\"."""

    def test_TWI_96_takes_no_combat_damage_while_coordinating(self, repo):
        state = _make_state()
        aayla = _place(state, "P0", _get_card(repo, "TWI", "96"), "ground")   # 6/5
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                        # 3 units → Coordinate
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _resolve_attack(state, aayla.instance_id, defender.instance_id)
        assert _find_instance(state, aayla.instance_id).damage == 0
        assert _find_instance(state, defender.instance_id).damage == 6

    def test_TWI_96_takes_damage_normally_without_coordinate(self, repo):
        state = _make_state()
        aayla = _place(state, "P0", _get_card(repo, "TWI", "96"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _resolve_attack(state, aayla.instance_id, defender.instance_id)
        assert _find_instance(state, aayla.instance_id).damage == 3


class TestManufacturedSoldiersTwi102:
    """TWI_102 — "Choose one: Create 2 Clone Trooper tokens / Create 3 Battle Droid
    tokens\"."""

    def test_TWI_102_offers_both_token_modes(self, repo):
        from swu.engine.actions import legal_actions, ChooseModalOption
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "TWI", "102")
        assert state.pending_decisions[-1].kind == "modal"
        modes = {a.mode for a in legal_actions(state)
                 if isinstance(a, ChooseModalOption)}
        assert modes == {"create_clone_troopers_2", "create_battle_droids_3"}
        state = _choose_modal_mode(state, "create_battle_droids_3")
        assert len(_battle_droids(state, "P0")) == 3
        assert _clone_troopers(state, "P0") == []

    def test_TWI_102_clone_trooper_mode(self, repo):
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "TWI", "102")
        state = _choose_modal_mode(state, "create_clone_troopers_2")
        assert len(_clone_troopers(state, "P0")) == 2
        assert _battle_droids(state, "P0") == []


# ── twi-set:22 — Miscellaneous abilities ─────────────────────────────────────


def _play_unit_with_exploit(state, ci):
    """Play a printed-Exploit unit from hand, committing with no sacrifices (so it
    pays full price).  Returns the state with the When Played step pending."""
    from swu.engine.actions import apply, PlayCard, ExploitCommit
    state = apply(state, PlayCard(ci.instance_id))
    if state.pending_decisions and state.pending_decisions[-1].kind == "exploit":
        state = apply(state, ExploitCommit())
    return state


class TestOsiSobeckTwi115:
    """TWI_115 — "When Played: This unit captures an enemy non-leader ground unit
    with cost equal to or less than the number of resources paid to play this
    unit\"."""

    def test_TWI_115_capture_ceiling_is_the_resources_paid(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        sobeck = _put_in_hand(state, "P0", _get_card(repo, "TWI", "115"))
        _give_resources(state, "P0", 12)
        paid = _play_cost(state, sobeck, ps)
        assert 4 <= paid < 9          # the two probe costs below bracket it
        cheap = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 4
        dear = _place(state, "P1", _get_card(repo, "TWI", "235"), "ground")    # 9
        spacer = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")    # 3
        state = _drain(_play_unit_with_exploit(state, sobeck))
        # Only the cheap ground unit was ever eligible, so the capture lands there:
        # the dear one costs more than was paid and the space one is out of arena.
        assert [c.instance_id for c in state.player_by_id("P0").capture_pile] == [
            cheap.instance_id]
        assert _find_instance(state, cheap.instance_id) is None
        assert _find_instance(state, dear.instance_id) is not None
        assert _find_instance(state, spacer.instance_id) is not None

    def test_TWI_115_captures_nothing_when_everything_costs_more(self, repo):
        state = _make_state()
        sobeck = _put_in_hand(state, "P0", _get_card(repo, "TWI", "115"))
        _give_resources(state, "P0", 12)
        big = _place(state, "P1", _get_card(repo, "TWI", "235"), "ground")   # 9
        state = _drain(_play_unit_with_exploit(state, sobeck))
        assert state.player_by_id("P0").capture_pile == []
        assert _find_instance(state, big.instance_id) is not None


class TestCloneTwi116:
    """TWI_116 — "You may have this unit enter play as a copy of a non-leader,
    non-Vehicle unit in play, except it gains the Clone trait and is not unique\"."""

    def test_TWI_116_copies_a_units_printed_profile_and_gains_clone(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        clone = _place(state, "P0", _get_card(repo, "TWI", "116"), "ground")  # 0/0
        model = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        vehicle = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")  # Vehicle
        state = _accept(_fire_when_played(state, clone))   # "You may …"
        offered = _target_ids(state)
        assert model.instance_id in offered
        assert vehicle.instance_id not in offered      # "non-Vehicle"
        state = _drain(_choose_target(state, model.instance_id))
        copied = _find_instance(state, clone.instance_id)
        assert compute_power(state, copied) == 3 and compute_hp(state, copied) == 7
        assert copied.card_def.name == model.card_def.name
        assert "Clone" in copied.card_def.traits
        assert copied.card_def.is_unique is False

    def test_TWI_116_declining_leaves_the_printed_body(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        clone = _place(state, "P0", _get_card(repo, "TWI", "116"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _decline(_fire_when_played(state, clone))
        still = _find_instance(state, clone.instance_id)
        assert still.card_def.name == "Clone"
        assert compute_power(state, still) == 0


class TestTheCloneWarsTwi125:
    """TWI_125 — "Pay any number of resources.  Create that many Clone Trooper
    tokens.  Each opponent creates that many Battle Droid tokens\"."""

    def test_TWI_125_pays_two_and_arms_both_sides(self, repo):
        from swu.engine.actions import (legal_actions, apply, PayResourceForToken,
                                        FinishPayResources)
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "TWI", "125", resources=10)
        assert state.pending_decisions[-1].kind == "pay_resources_for_tokens"
        for _ in range(2):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, PayResourceForToken)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishPayResources)))
        assert len(_clone_troopers(state, "P0")) == 2
        assert len(_battle_droids(state, "P1")) == 2
        assert _battle_droids(state, "P0") == []
        assert _clone_troopers(state, "P1") == []

    def test_TWI_125_paying_nothing_creates_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishPayResources
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "TWI", "125", resources=10)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishPayResources)))
        assert _clone_troopers(state, "P0") == [] and _battle_droids(state, "P1") == []


class TestConfederateTriFighterTwi132:
    """TWI_132 — "Bases can't be healed\"."""

    def test_TWI_132_locks_both_players_bases_while_in_play(self, repo):
        from swu.engine.actions import _apply_restore, _defeat_unit
        state = _make_state()
        for pid in ("P0", "P1"):
            state.player_by_id(pid).base_instance.damage = 5
        tri = _place(state, "P0", _get_card(repo, "TWI", "132"), "space")
        for pid in ("P0", "P1"):
            _apply_restore(state, state.player_by_id(pid), 3)
            assert state.player_by_id(pid).base_instance.damage == 5
        # The lock lifts the instant it leaves play.
        _defeat_unit(state, state.player_by_id("P0"), tri)
        _apply_restore(state, state.player_by_id("P0"), 3)
        assert state.player_by_id("P0").base_instance.damage == 2


class TestDarthMaulTwi135:
    """TWI_135 — "This unit can attack 2 units instead of 1\"."""

    def test_TWI_135_attacks_two_units_at_once(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackTwoUnits
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "TWI", "135"), "ground")  # 5/6
        maul.exhausted = False
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")      # 3/7
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")      # 3/7
        assert any(x for x in legal_actions(state) if isinstance(x, AttackTwoUnits)
                   and x.attacker_id == maul.instance_id)
        state = _drain(apply(state, AttackTwoUnits(maul.instance_id,
                                                   a.instance_id, b.instance_id)))
        # He deals his 5 power to EACH defender and takes the SUM of theirs (3+3=6),
        # which is exactly lethal on a 5/6 — the whole trade the card offers.
        assert _find_instance(state, a.instance_id).damage == 5
        assert _find_instance(state, b.instance_id).damage == 5
        assert _find_instance(state, maul.instance_id) is None


class TestJesseTwi145:
    """TWI_145 — "When Played: An opponent creates 2 Battle Droid tokens\"."""

    def test_TWI_145_gives_the_opponent_the_droids(self, repo):
        state = _make_state()
        jesse = _place(state, "P0", _get_card(repo, "TWI", "145"), "ground")
        state = _drain(_fire_when_played(state, jesse))
        assert len(_battle_droids(state, "P1")) == 2
        assert _battle_droids(state, "P0") == []


class TestSenatorialCorvetteTwi148:
    """TWI_148 — "When Defeated: Each opponent discards a card from their hand\"."""

    def test_TWI_148_opponent_discards_on_defeat(self, repo):
        state = _make_state()
        corvette = _place(state, "P0", _get_card(repo, "TWI", "148"), "space")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state = _drain(_fire_when_defeated(state, corvette))
        assert len(state.player_by_id("P1").hand) == 0
        assert len(state.player_by_id("P1").discard) == 1
        assert len(state.player_by_id("P0").hand) == 1     # the controller keeps theirs


# ── twi-set:23 — Miscellaneous abilities ─────────────────────────────────────


class TestCaughtInTheCrossfireTwi176:
    """TWI_176 — "Choose 2 enemy units in the same arena.  Each of those units deals
    damage equal to its power to the other.\""""

    def test_TWI_176_the_pair_shoot_each_other_simultaneously(self, repo):
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        b = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")    # 3/2
        far = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")    # other arena
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # friendly
        state, _evt = _play_event_from_hand(state, repo, "TWI", "176")
        offered = _target_ids(state)
        assert mine.instance_id not in offered            # enemy units only
        state = _choose_target(state, a.instance_id)
        second = _target_ids(state)
        assert far.instance_id not in second              # "in the same arena"
        assert a.instance_id not in second                # two distinct units
        assert b.instance_id in second
        state = _drain(_choose_target(state, b.instance_id))
        # b dies to a's 3 power, but still deals its own 3 first (simultaneous).
        assert _find_instance(state, b.instance_id) is None
        assert _find_instance(state, a.instance_id).damage == 3

    def test_TWI_176_fizzles_with_a_lone_enemy_unit(self, repo):
        state = _make_state()
        alone = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "176")
        state = _drain(_choose_target(state, alone.instance_id))
        assert _find_instance(state, alone.instance_id).damage == 0
        assert not state.pending_decisions


class TestPadmeAmidalaTwi192:
    """TWI_192 — "Coordinate — On Attack: Give an enemy unit –3/–0 for this
    phase.\""""

    def test_TWI_192_debuff_only_while_coordinating(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        padme = _place(state, "P0", _get_card(repo, "TWI", "192"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 3/7
        state = _fire_on_attack(state, padme)
        assert not state.pending_decisions            # 1 unit — no Coordinate
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                    # 3 units → Coordinate
        state = _fire_on_attack(state, _find_instance(state, padme.instance_id))
        state = _drain(_choose_target(state, foe.instance_id))
        assert compute_power(state, _find_instance(state, foe.instance_id)) == 0


class TestClearTheFieldTwi199:
    """TWI_199 — "Choose a non-leader unit that costs 3 or less.  Return it and each
    enemy non-leader unit with the same name as it to their owners' hands.\""""

    def test_TWI_199_bounces_the_pick_and_every_enemy_copy(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # cost 2
        theirs_a = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")
        theirs_b = _place(state, "P1", _get_card(repo, "TWI", "241"), "space")
        other = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # cost 4
        state, _evt = _play_event_from_hand(state, repo, "TWI", "199")
        offered = _target_ids(state)
        assert other.instance_id not in offered          # costs more than 3
        assert {mine.instance_id, theirs_a.instance_id,
                theirs_b.instance_id} <= offered         # either controller
        state = _drain(_choose_target(state, mine.instance_id))
        for gone in (mine, theirs_a, theirs_b):
            assert _find_instance(state, gone.instance_id) is None
        assert len(state.player_by_id("P0").hand) == 1    # each to its OWN owner
        assert len(state.player_by_id("P1").hand) == 2
        assert _find_instance(state, other.instance_id) is not None


class TestCloneDiveTrooperTwi205:
    """TWI_205 — "Coordinate — While this unit is attacking, the defender gets
    –2/–0.\""""

    def test_TWI_205_blunts_only_the_unit_it_attacks(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "TWI", "205"), "ground")  # 2/1
        other = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        _filler(state, "P0", repo)                        # 3 units → Coordinate
        foe = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")      # 3/2
        # Mid-combat, and only while THIS trooper is the attacker.
        assert compute_power(state, foe, is_defending=True,
                             attacker_id=trooper.instance_id) == 1
        assert compute_power(state, foe, is_defending=True,
                             attacker_id=other.instance_id) == 3
        assert compute_power(state, foe) == 3             # outside combat entirely

    def test_TWI_205_no_debuff_without_coordinate(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "TWI", "205"), "ground")
        foe = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")      # 3/2
        assert compute_power(state, foe, is_defending=True,
                             attacker_id=trooper.instance_id) == 3


class TestSanctionersShuttleTwi213:
    """TWI_213 — "Coordinate — When Played: This unit captures an enemy non-leader
    unit that costs 3 or less.\""""

    def test_TWI_213_captures_only_while_coordinating(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "TWI", "213"), "space")
        cheap = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")  # 2
        dear = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 4
        state = _drain(_fire_when_played(state, shuttle))
        assert state.player_by_id("P0").capture_pile == []      # 1 unit — no Coordinate
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                              # 3 units
        state = _drain(_fire_when_played(
            state, _find_instance(state, shuttle.instance_id)))
        assert [c.instance_id for c in state.player_by_id("P0").capture_pile] == [
            cheap.instance_id]
        assert _find_instance(state, dear.instance_id) is not None


class TestOnTopOfThingsTwi219:
    """TWI_219 (Upgrade) — "When Played: Attached unit can't be attacked this phase
    (unless it has Sentinel).\""""

    def test_TWI_219_host_drops_out_of_the_eligible_defenders(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        bystander = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        attacker.exhausted = False
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "219"), "P1")
        state = _drain(_fire_upgrade_played(state, upg, host))
        defenders = {a.defender_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)
                     and a.attacker_id == attacker.instance_id}
        assert host.instance_id not in defenders
        assert bystander.instance_id in defenders

    def test_TWI_219_yields_to_sentinel(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        from swu.engine.state import Modifier
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        attacker.exhausted = False
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "TWI", "219"), "P1")
        state = _drain(_fire_upgrade_played(state, upg, host))
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=host.instance_id,
            target_instance_id=host.instance_id,
            kind="keyword_grant", value={"keyword": "Sentinel", "value": 0},
            duration="this_phase"))
        defenders = {a.defender_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)
                     and a.attacker_id == attacker.instance_id}
        assert host.instance_id in defenders


class TestNowThereAreTwoOfThemTwi225:
    """TWI_225 — "If you control exactly one unit, play a non-Vehicle unit from your
    hand that shares a Trait with the unit you control.  It costs 5 resources
    less.\""""

    def test_TWI_225_offers_only_trait_sharing_non_vehicles(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # Clone/Republic
        share = _put_in_hand(state, "P0", _get_card(repo, "TWI", "145"))   # Clone, 3
        vehicle = _put_in_hand(state, "P0", _get_card(repo, "TWI", "247"))  # Vehicle
        stranger = _put_in_hand(state, "P0", _get_card(repo, "TWI", "115"))  # Separatist
        state, _evt = _play_event_from_hand(state, repo, "TWI", "225", resources=12)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert offered == {share.instance_id}
        assert vehicle.instance_id not in offered
        assert stranger.instance_id not in offered

    def test_TWI_225_needs_exactly_one_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")   # two units
        _put_in_hand(state, "P0", _get_card(repo, "TWI", "145"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "225", resources=12)
        assert not state.pending_decisions

    def test_TWI_225_discounts_the_played_unit_by_five(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand, _play_cost
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")
        share = _put_in_hand(state, "P0", _get_card(repo, "TWI", "247"))  # Vehicle: no
        big = _put_in_hand(state, "P0", _get_card(repo, "TWI", "94"))     # Republic
        full = _play_cost(state, big, state.player_by_id("P0"))
        state, _evt = _play_event_from_hand(state, repo, "TWI", "225", resources=12)
        before = state.player_by_id("P0").available_resources
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayFromHand) and a.instance_id == big.instance_id)
        state = _drain(apply(state, act))
        spent = before - state.player_by_id("P0").available_resources
        assert spent == max(0, full - 5)       # the 5-resource discount
        assert _find_instance(state, big.instance_id) is not None
        assert _find_instance(state, share.instance_id) is None   # never offered


# ── twi-set:24 — Miscellaneous abilities ─────────────────────────────────────


class TestPrisonerOfWarTwi227:
    """TWI_227 — "A friendly unit captures an enemy non-leader, non-Vehicle unit.
    If the enemy unit costs less than the friendly unit, create 2 Battle Droid
    tokens.\""""

    def test_TWI_227_cheaper_prey_pays_two_droids(self, repo):
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 4
        prey = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")    # 2
        vehicle = _place(state, "P1", _get_card(repo, "TWI", "63"), "space")   # Vehicle
        state, _evt = _play_event_from_hand(state, repo, "TWI", "227")
        state = _choose_target(state, captor.instance_id)
        offered = _target_ids(state)
        assert prey.instance_id in offered
        assert vehicle.instance_id not in offered        # "non-Vehicle"
        state = _drain(_choose_target(state, prey.instance_id))
        assert [c.instance_id for c in state.player_by_id("P0").capture_pile] == [
            prey.instance_id]
        assert len(_battle_droids(state, "P0")) == 2

    def test_TWI_227_no_droids_when_the_prey_is_not_cheaper(self, repo):
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # 2
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # 4
        state, _evt = _play_event_from_hand(state, repo, "TWI", "227")
        state = _choose_target(state, captor.instance_id)
        state = _drain(_choose_target(state, prey.instance_id))
        assert len(state.player_by_id("P0").capture_pile) == 1
        assert _battle_droids(state, "P0") == []


class TestBattleDroidLegionTwi235:
    """TWI_235 — "When Defeated: Create 3 Battle Droid tokens.\""""

    def test_TWI_235_leaves_three_droids_behind(self, repo):
        state = _make_state()
        legion = _place(state, "P0", _get_card(repo, "TWI", "235"), "ground")
        state = _drain(_fire_when_defeated(state, legion))
        assert len(_battle_droids(state, "P0")) == 3
        assert _battle_droids(state, "P1") == []


class TestAtTeVanguardTwi247:
    """TWI_247 — "When Defeated: Create 2 Clone Trooper tokens.\""""

    def test_TWI_247_leaves_two_troopers_behind(self, repo):
        state = _make_state()
        atte = _place(state, "P0", _get_card(repo, "TWI", "247"), "ground")
        state = _drain(_fire_when_defeated(state, atte))
        assert len(_clone_troopers(state, "P0")) == 2


class TestSwordAndShieldManeuverTwi250:
    """TWI_250 — "Give each friendly Trooper unit Raid 1 for this phase.  Give each
    friendly Jedi unit Sentinel for this phase.\""""

    def test_TWI_250_grants_each_trait_its_own_keyword(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "TWI", "241"), "ground")  # Clone/Trooper
        jedi = _place(state, "P0", _get_card(repo, "TWI", "96"), "ground")      # Jedi
        enemy = _place(state, "P1", _get_card(repo, "TWI", "241"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "TWI", "250")
        state = _drain(state)
        tr = _find_instance(state, trooper.instance_id)
        jd = _find_instance(state, jedi.instance_id)
        assert keyword_value(state, tr, Keyword.RAID) == 1
        assert has_keyword(state, tr, Keyword.SENTINEL) is False
        assert has_keyword(state, jd, Keyword.SENTINEL) is True
        assert keyword_value(state, jd, Keyword.RAID) == 0
        # Friendly only.
        foe = _find_instance(state, enemy.instance_id)
        assert keyword_value(state, foe, Keyword.RAID) == 0


class TestBrainInvadersTwi255:
    """TWI_255 — "Each leader loses all abilities except for epic actions and can't
    gain abilities.\""""

    def test_TWI_255_switches_off_an_undeployed_leaders_action(self, repo):
        state = _make_state()
        # Nute Gunray's undeployed Action needs 2 friendly defeats this phase.
        nute = _place_leader(state, "P0", _get_leader(repo, "TWI", "2"))
        _mark_unit_defeated_this_phase(state, "P0")
        _mark_unit_defeated_this_phase(state, "P0")
        assert _ability_offered(state, nute) is True
        brain = _place(state, "P1", _get_card(repo, "TWI", "255"), "ground")
        assert _ability_offered(state, nute) is False      # an ENEMY unit, as printed
        # …and it lifts the instant Brain Invaders leaves play.
        from swu.engine.actions import _defeat_unit
        _defeat_unit(state, state.player_by_id("P1"), brain)
        assert _ability_offered(state, nute) is True

    def test_TWI_255_silences_a_deployed_leaders_constant_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        # Ahsoka TWI_11 deployed: "Coordinate — this unit gets +2/+0."
        ahsoka = _place(state, "P0", _get_card(repo, "TWI", "11"), "ground")
        ahsoka.deployed = True
        _filler(state, "P0", repo)
        _filler(state, "P0", repo)                     # 3 units → Coordinate
        assert compute_power(state, ahsoka) == 5
        _place(state, "P0", _get_card(repo, "TWI", "255"), "ground")
        # Brain Invaders is symmetric — it silences its own controller's leader too.
        assert compute_power(state, ahsoka) == 3

    def test_TWI_255_leaves_non_leader_units_alone(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        echo = _place(state, "P0", _get_card(repo, "TWI", "90"), "ground")  # +2/+2
        _filler(state, "P0", repo)
        _place(state, "P0", _get_card(repo, "TWI", "255"), "ground")        # 3 units
        assert compute_power(state, echo) == 4        # its own Coordinate still works
