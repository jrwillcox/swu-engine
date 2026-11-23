"""HMW (Homeworlds) card tests â€” one focused test (or two) per encoded card.

Every test name embeds the card id (``HMW_<n>``) so the ``verify_encoding`` ``-k``
gate selects it.  Most of ``hmw-set:01`` is Fortify upgrades, which sit on their
controller's base; ``_attach_to_base`` puts one there directly (no triggers) and a
real ``PlayCard`` is used wherever the When Played matters.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import (
    repo,  # noqa: F401 â€” pytest fixture
    _get_card, _get_leader, _make_state, _place, _place_leader,
    _give_resources, _fire_when_played,
)
from tests.test_fortify import (
    _unit_def, _to_hand, _attach_to_base, _deck, _drain, _check_invariants,
)


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _drive(state, picker=None, limit=40):
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while state.pending_decisions and guard < limit:
        guard += 1
        acts = legal_actions(state)
        choice = picker(state, acts) if picker else None
        state = apply(state, choice or acts[0])
    return state


def _accept_and_target(target_id=None):
    from swu.engine.actions import AcceptTrigger, ChooseTarget

    def _pick(state, acts):
        for a in acts:
            if isinstance(a, AcceptTrigger):
                return a
        chooses = [a for a in acts if isinstance(a, ChooseTarget)
                   and getattr(a, "target_id", None)]
        if chooses:
            for a in chooses:
                if target_id is not None and a.target_id == target_id:
                    return a
            return chooses[0]
        return None
    return _pick


def _fire_phase(state, phase):
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, PhaseChanged(new_phase=phase, round_number=1), after_all_player_idx=0)


def _base(state, pid):
    return state.player_by_id(pid).base_instance


def _play_upgrade(state, upg_ci):
    from swu.engine.actions import apply, PlayCard
    return apply(state, PlayCard(upg_ci.instance_id,
                                 _base(state, upg_ci.owner_id).instance_id))


def _use_ability(state, source_id):
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_id)
    return apply(state, use)


def _offers_ability(state, source_id) -> bool:
    from swu.engine.actions import legal_actions, UseAbility
    return any(isinstance(a, UseAbility) and a.source_id == source_id
               for a in legal_actions(state))


def _discard(state, pid, card_def):
    from swu.engine.state import CardInstance, Zone
    import uuid
    ci = CardInstance(instance_id=f"{pid}_disc_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=pid, zone=Zone.DISCARD)
    state.player_by_id(pid).discard.append(ci)
    return ci


def _offers_accept(state) -> bool:
    from swu.engine.actions import legal_actions, AcceptTrigger
    return any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:01 â€” Fortify residual text
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestGrandMoffTarkinHMW_4:

    def test_HMW_4_waives_aspect_penalty_on_fortify_upgrades(self, repo):
        from swu.engine.actions import _play_cost
        tank = _get_card(repo, "HMW", "37")
        state = _make_state()
        ps = state.player_by_id("P0")
        ci = _to_hand(state, "P0", tank)
        base_id = _base(state, "P0").instance_id
        before = _play_cost(state, ci, ps, target_host_id=base_id)
        assert before > tank.cost  # the plain test base matches no aspect
        _place_leader(state, "P0", _get_leader(repo, "HMW", "4"))
        assert _play_cost(state, ci, ps, target_host_id=base_id) == tank.cost

    def test_HMW_4_waiver_ignores_non_fortify_cards(self, repo):
        from swu.cards.models import AspectPip
        from swu.engine.actions import _play_cost
        heroic = (AspectPip(position=0, name="Heroism", color="White",
                            is_duplicate=False),)
        unit = dataclasses.replace(_unit_def(), aspects=heroic)
        state = _make_state()
        ps = state.player_by_id("P0")
        _place_leader(state, "P0", _get_leader(repo, "HMW", "4"))
        ci = _to_hand(state, "P0", unit)
        assert _play_cost(state, ci, ps) == unit.cost + 2

    def test_HMW_4_deployed_regroup_defeats_a_low_base(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "4"))
        _base(state, "P1").damage = 20          # 10 remaining of 30
        state = _drive(_fire_phase(state, "REGROUP"), _accept_and_target())
        assert state.is_terminal()
        assert state.player_by_id("P1").is_eliminated

    def test_HMW_4_no_offer_while_bases_are_healthy(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "4"))
        _base(state, "P1").damage = 19          # 11 remaining
        state = _fire_phase(state, "REGROUP")
        assert not _offers_accept(state)
        assert not state.is_terminal()


class TestBactaTankHMW_37:

    def test_HMW_37_when_played_heals_a_non_vehicle_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 8)
        hurt = _place(state, "P0", _unit_def(hp=5))
        hurt.damage = 4
        tank = _to_hand(state, "P0", _get_card(repo, "HMW", "37"))
        state = _drive(_play_upgrade(state, tank), _accept_and_target(hurt.instance_id))
        unit = state.find_instance(hurt.instance_id)[1]
        assert unit.damage == 1
        assert [u.instance_id for u in _base(state, "P0").attached_upgrades] == [
            tank.instance_id]

    def test_HMW_37_action_puts_a_unit_from_discard_on_top(self, repo):
        state = _make_state()
        _deck(state, "P0", 3)
        tank = _attach_to_base(state, "P0", _get_card(repo, "HMW", "37"))
        dead = _discard(state, "P0", _unit_def(name="Fallen"))
        state = _drive(_use_ability(state, tank.instance_id))
        ps = state.player_by_id("P0")
        assert ps.deck[0].instance_id == dead.instance_id
        assert tank.instance_id in [c.instance_id for c in ps.discard]
        assert not ps.base_instance.attached_upgrades
        _check_invariants(state)


def test_HMW_70_dark_sanctum_regroup_draws_and_hurts_base(repo):
    state = _make_state()
    _deck(state, "P0", 3)
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "70"))
    state = _drive(_fire_phase(state, "REGROUP"))
    ps = state.player_by_id("P0")
    assert len(ps.hand) == 1
    assert ps.base_instance.damage == 2


class TestAllianceShieldGeneratorHMW_81:

    def test_HMW_81_prevents_5_damage_then_defeats_and_draws(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _deck(state, "P0", 2)
        gen = _attach_to_base(state, "P0", _get_card(repo, "HMW", "81"))
        _apply_deal_damage(state, _base(state, "P0").instance_id, 6, "Test")
        ps = state.player_by_id("P0")
        assert ps.base_instance.damage == 0
        assert not ps.base_instance.attached_upgrades
        assert [c.instance_id for c in ps.discard] == [gen.instance_id]
        assert len(ps.hand) == 1

    def test_HMW_81_lets_smaller_damage_through(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _deck(state, "P0", 2)
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "81"))
        _apply_deal_damage(state, _base(state, "P0").instance_id, 4, "Test")
        ps = state.player_by_id("P0")
        assert ps.base_instance.damage == 4
        assert len(ps.base_instance.attached_upgrades) == 1
        assert not ps.hand


def test_HMW_95_carbonite_chamber_unit_skips_next_ready(repo):
    from swu.engine.actions.turn import _ready_all_cards
    state = _make_state()
    chamber = _attach_to_base(state, "P0", _get_card(repo, "HMW", "95"))
    foe = _place(state, "P1", _unit_def())
    foe.exhausted = True
    other = _place(state, "P1", _unit_def(name="Other", number="51"))
    other.exhausted = True
    state = _drive(_use_ability(state, chamber.instance_id),
                   _accept_and_target(foe.instance_id))
    assert not _base(state, "P0").attached_upgrades
    _ready_all_cards(state)
    assert state.find_instance(foe.instance_id)[1].exhausted
    assert not state.find_instance(other.instance_id)[1].exhausted


def test_HMW_112_military_academy_grants_friendly_overwhelm(repo):
    from swu.engine.keywords import has_keyword, Keyword, Keyword
    state = _make_state()
    mine = _place(state, "P0", _unit_def())
    theirs = _place(state, "P1", _unit_def(name="Foe", number="51"))
    assert not has_keyword(state, mine, Keyword.OVERWHELM)
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "112"))
    assert has_keyword(state, mine, Keyword.OVERWHELM)
    assert not has_keyword(state, theirs, Keyword.OVERWHELM)


def test_HMW_113_sinister_war_memorial_heals_on_friendly_defeat(repo):
    from swu.engine.actions import _defeat_unit
    state = _make_state()
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "113"))
    _base(state, "P0").damage = 5
    unit = _place(state, "P0", _unit_def())
    _defeat_unit(state, state.player_by_id("P0"), unit)
    state = _drain(state)
    assert _base(state, "P0").damage == 4


def test_HMW_126_verdant_fortress_grants_friendly_raid_1(repo):
    from swu.engine.actions import compute_power
    from swu.engine.keywords import keyword_value, Keyword
    state = _make_state()
    mine = _place(state, "P0", _unit_def(power=2))
    theirs = _place(state, "P1", _unit_def(name="Foe", number="51", power=2))
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "126"))
    assert keyword_value(state, mine, Keyword.RAID) == 1
    assert compute_power(state, mine, is_attacking=True) == 3
    assert compute_power(state, mine) == 2
    assert keyword_value(state, theirs, Keyword.RAID) == 0


class TestBeastLairHMW_147:

    def test_HMW_147_action_phase_discard_creates_beast(self, repo):
        state = _make_state()
        pitched = _to_hand(state, "P0", _unit_def(name="Pitched"))
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "147"))
        state = _drive(_fire_phase(state, "ACTION"), _accept_and_target())
        ps = state.player_by_id("P0")
        assert not ps.hand
        assert [c.instance_id for c in ps.discard] == [pitched.instance_id]
        beasts = [u for u in ps.ground_arena if u.card_def.name == "Beast"]
        assert len(beasts) == 1
        from swu.engine.actions import compute_power, compute_hp
        assert (compute_power(state, beasts[0]), compute_hp(state, beasts[0])) == (3, 3)
        _check_invariants(state)

    def test_HMW_147_not_offered_with_empty_hand(self, repo):
        state = _make_state()
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "147"))
        state = _fire_phase(state, "ACTION")
        assert not _offers_accept(state)
        assert not state.player_by_id("P0").ground_arena


class TestNoxiousRefineryHMW_160:

    def _aggro_def(self, repo, aggressive):
        from swu.cards.models import AspectPip
        pips = (AspectPip(position=0, name="Aggression", color="Red",
                          is_duplicate=False),) if aggressive else ()
        return dataclasses.replace(_unit_def(name="Top", number="52"), aspects=pips)

    def test_HMW_160_aggression_top_card_pings_enemy(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        top = _push_deck_top(state, "P0", self._aggro_def(repo, True))
        foe = _place(state, "P1", _unit_def(hp=3))
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "160"))
        state = _drive(_fire_phase(state, "REGROUP"), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 1
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id

    def test_HMW_160_other_top_card_does_nothing(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        _push_deck_top(state, "P0", self._aggro_def(repo, False))
        foe = _place(state, "P1", _unit_def(hp=3))
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "160"))
        state = _drive(_fire_phase(state, "REGROUP"))
        assert state.find_instance(foe.instance_id)[1].damage == 0


class TestTrapFieldHMW_171:

    def test_HMW_171_springs_on_an_enemy_ground_token(self, repo):
        from swu.engine.actions import _create_token_units
        from swu.engine.actions.observers import _fire_unit_entry_observers
        state = _make_state()
        trap = _attach_to_base(state, "P0", _get_card(repo, "HMW", "171"))
        (tok,) = _create_token_units(state, state.player_by_id("P1"), "Beast", 1)
        state = _fire_unit_entry_observers(state)
        state = _drive(state, _accept_and_target())
        assert state.find_instance(tok.instance_id) is None \
            or state.find_instance(tok.instance_id)[1].damage == 3
        ps = state.player_by_id("P0")
        assert not ps.base_instance.attached_upgrades
        assert [c.instance_id for c in ps.discard] == [trap.instance_id]

    def test_HMW_171_ignores_space_units(self, repo):
        from swu.engine.actions.observers import _fire_unit_entry_observers
        state = _make_state()
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "171"))
        flier = _place(state, "P1", _unit_def(), arena="space")
        state.game_memory.unit_entries.append(
            {"instance_id": flier.instance_id, "player_id": "P1"})
        state = _fire_unit_entry_observers(state)
        assert not _offers_accept(state)
        assert len(_base(state, "P0").attached_upgrades) == 1


def test_HMW_172_heavy_ion_cannon_draws_and_grants_once_per_phase_shot(repo):
    state = _make_state()
    _give_resources(state, "P0", 10)
    _deck(state, "P0", 3)
    cannon = _to_hand(state, "P0", _get_card(repo, "HMW", "172"))
    state = _drive(_play_upgrade(state, cannon))
    assert len(state.player_by_id("P0").hand) == 1          # drew a card
    foe = _place(state, "P1", _unit_def(hp=5))
    state.active_player_index = 0
    state = _drive(_use_ability(state, cannon.instance_id),
                   _accept_and_target(foe.instance_id))
    assert state.find_instance(foe.instance_id)[1].damage == 2
    assert not state.player_by_id("P0").hand                 # the cost
    state.active_player_index = 0
    _to_hand(state, "P0", _unit_def(name="More"))
    assert not _offers_ability(state, cannon.instance_id)


def test_HMW_205_intelligence_agency_looks_at_opponent_hand(repo):
    state = _make_state()
    _give_resources(state, "P0", 8)
    _to_hand(state, "P1", _unit_def(name="Secret"))
    agency = _to_hand(state, "P0", _get_card(repo, "HMW", "205"))
    state = _play_upgrade(state, agency)
    kinds = [d.kind for d in state.pending_decisions]
    assert "name_and_discard" in kinds


class TestTheTarkinDoctrineHMW_206:

    def test_HMW_206_with_tarkin_debuffs_an_enemy(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _give_resources(state, "P0", 8)
        _place_leader(state, "P0", _get_leader(repo, "HMW", "4"))
        foe = _place(state, "P1", _unit_def(power=4))
        doc = _to_hand(state, "P0", _get_card(repo, "HMW", "206"))
        state = _drive(_play_upgrade(state, doc), _accept_and_target(foe.instance_id))
        assert compute_power(state, state.find_instance(foe.instance_id)[1]) == 1

    def test_HMW_206_without_tarkin_no_debuff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _give_resources(state, "P0", 8)
        foe = _place(state, "P1", _unit_def(power=4))
        doc = _to_hand(state, "P0", _get_card(repo, "HMW", "206"))
        state = _drive(_play_upgrade(state, doc))
        assert compute_power(state, state.find_instance(foe.instance_id)[1]) == 4

    def test_HMW_206_fortification_play_exhausts_an_enemy(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 8)
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "206"))
        foe = _place(state, "P1", _unit_def())
        chamber = _to_hand(state, "P0", _get_card(repo, "HMW", "95"))
        state = _drive(_play_upgrade(state, chamber), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].exhausted


class TestInsurgentCampHMW_216:

    def _play_unit(self, state, ci):
        from swu.engine.actions import apply, PlayCard
        return apply(state, PlayCard(ci.instance_id))

    def test_HMW_216_readies_a_small_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 8)
        camp = _attach_to_base(state, "P0", _get_card(repo, "HMW", "216"))
        small = _to_hand(state, "P0", _unit_def(power=2))
        state = _drive(self._play_unit(state, small), _accept_and_target())
        assert not state.find_instance(small.instance_id)[1].exhausted
        assert camp.instance_id in [c.instance_id
                                    for c in state.player_by_id("P0").discard]

    def test_HMW_216_ignores_a_big_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 8)
        _attach_to_base(state, "P0", _get_card(repo, "HMW", "216"))
        big = _to_hand(state, "P0", _unit_def(power=4))
        state = self._play_unit(state, big)
        assert not _offers_accept(state)
        assert state.find_instance(big.instance_id)[1].exhausted


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:02 â€” Direct damage & removal
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def _ready_count(state, pid):
    return sum(1 for r in state.player_by_id(pid).resources if not r.exhausted)


class TestJarJarBinksHMW_5:

    def test_HMW_5_action_needs_a_token_upgrade_given_this_phase(self, repo):
        from swu.engine import tokens
        state = _make_state()
        _give_resources(state, "P0", 3)
        jj = _place_leader(state, "P0", _get_leader(repo, "HMW", "5"))
        mine = _place(state, "P0", _unit_def(hp=5))
        assert not _offers_ability(state, jj.instance_id)
        tokens.attach_token(state, state.player_by_id("P0"), mine, "Experience")
        assert _offers_ability(state, jj.instance_id)

    def test_HMW_5_action_pings_a_unit_and_heals_a_base(self, repo):
        from swu.engine import tokens
        state = _make_state()
        _give_resources(state, "P0", 3)
        jj = _place_leader(state, "P0", _get_leader(repo, "HMW", "5"))
        mine = _place(state, "P0", _unit_def(hp=5))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
        tokens.attach_token(state, state.player_by_id("P0"), mine, "Experience")
        _base(state, "P0").damage = 4
        base_id = _base(state, "P0").instance_id

        def _pick(state, acts):
            from swu.engine.actions import ChooseTarget
            for want in (foe.instance_id, base_id):
                for a in acts:
                    if isinstance(a, ChooseTarget) and a.target_id == want:
                        return a
            return None
        state = _drive(_use_ability(state, jj.instance_id), _pick)
        assert state.find_instance(foe.instance_id)[1].damage == 1
        assert _base(state, "P0").damage == 3
        assert _ready_count(state, "P0") == 2
        assert state.player_by_id("P0").leader_instance.exhausted

    def test_HMW_5_ledger_clears_at_phase_rollover(self, repo):
        from swu.engine import tokens
        state = _make_state()
        mine = _place(state, "P0", _unit_def())
        tokens.attach_token(state, state.player_by_id("P0"), mine, "Shield")
        assert "P0" in state.game_memory.token_upgrades_given_this_phase
        state.game_memory.clear_phase()
        assert not state.game_memory.token_upgrades_given_this_phase


class TestKelnaccaHMW_36:

    def test_HMW_36_pay_three_deals_power_to_an_enemy(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 4)
        kel = _place(state, "P0", _get_card(repo, "HMW", "36"))
        foe = _place(state, "P1", _unit_def(hp=9))
        state = _drive(_fire_when_played(state, kel), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 4
        assert _ready_count(state, "P0") == 1

    def test_HMW_36_six_ready_resources_allow_two_strikes(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 6)
        kel = _place(state, "P0", _get_card(repo, "HMW", "36"))
        foe = _place(state, "P1", _unit_def(hp=20))
        state = _drive(_fire_when_played(state, kel), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 8
        assert _ready_count(state, "P0") == 0

    def test_HMW_36_not_offered_below_three_ready(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 2)
        kel = _place(state, "P0", _get_card(repo, "HMW", "36"))
        _place(state, "P1", _unit_def(hp=9))
        state = _fire_when_played(state, kel)
        assert not _offers_accept(state)


class TestDarthVaderHMW_43:

    def test_HMW_43_plays_two_cheap_units_free_and_damages_them(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        ps = state.player_by_id("P0")
        _deck(state, "P0", 3)                       # 2/3 cost-2 units
        big = dataclasses.replace(_unit_def(name="Big", number="58", hp=9), cost=5)
        from tests.test_sor_cards import _push_deck_top
        _push_deck_top(state, "P0", big)
        vader = _place(state, "P0", _get_card(repo, "HMW", "43"))
        state = _fire_when_played(state, vader)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert len(top.context["candidate_ids"]) == 3   # Big (cost 5) excluded
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            acts = legal_actions(state)
            state = apply(state, acts[0])
        ps = state.player_by_id("P0")
        # each 2/3 took 2 damage and survived; Vader + 2 played
        played = [u for u in ps.ground_arena if u.instance_id != vader.instance_id]
        assert len(played) == 2
        assert all(u.damage == 2 for u in played)
        _check_invariants(state)


class TestKrrsantanHMW_46:

    def test_HMW_46_deals_resources_minus_three_to_a_ground_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 7)
        krr = _place(state, "P0", _get_card(repo, "HMW", "46"))
        foe = _place(state, "P1", _unit_def(hp=9))
        state = _drive(_fire_when_played(state, krr), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 4

    def test_HMW_46_not_offered_at_three_resources(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 3)
        krr = _place(state, "P0", _get_card(repo, "HMW", "46"))
        _place(state, "P1", _unit_def(hp=9))
        state = _fire_when_played(state, krr)
        assert not _offers_accept(state)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:03 â€” Direct damage & removal
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def _select_damage(state, target_id):
    from swu.engine.actions import apply, SelectDamageTarget
    return apply(state, SelectDamageTarget(target_id))


class TestThirdSisterHMW_51:

    def test_HMW_51_damage_hands_off_and_escalates(self, repo):
        state = _make_state()
        sis = _place(state, "P0", _get_card(repo, "HMW", "51"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
        mine = _place(state, "P0", _unit_def(name="Mine", number="52", hp=9))
        from tests.test_sec_cards import _drain as _sec_drain
        state = _sec_drain(_fire_when_played(state, sis))
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage" and top.deciding_player_id == "P0"
        state = _select_damage(state, foe.instance_id)          # P0 deals 2 to P1's unit
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage" and top.deciding_player_id == "P1"
        assert top.context["amount_each"] == 3
        state = _select_damage(state, mine.instance_id)         # P1 deals 3 to P0's unit
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P0" and top.context["amount_each"] == 4
        state = _select_damage(state, foe.instance_id)          # P0 deals 4 more
        assert not any(d.kind == "select_damage" for d in state.pending_decisions)
        assert state.find_instance(foe.instance_id)[1].damage == 6
        assert state.find_instance(mine.instance_id)[1].damage == 3

    def test_HMW_51_declining_ends_the_chain(self, repo):
        from swu.engine.actions import apply, FinishSelectDamage
        state = _make_state()
        sis = _place(state, "P0", _get_card(repo, "HMW", "51"))
        foe = _place(state, "P1", _unit_def(hp=9))
        from tests.test_sec_cards import _drain as _sec_drain
        state = _sec_drain(_fire_when_played(state, sis))
        assert state.pending_decisions[-1].kind == "select_damage"
        state = apply(state, FinishSelectDamage())
        assert not any(d.kind == "select_damage" for d in state.pending_decisions)
        assert state.find_instance(foe.instance_id)[1].damage == 0


class TestSeismicDetonationHMW_54:

    def test_HMW_54_hits_each_enemy_unit_in_the_chosen_arena_at_regroup(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from tests.test_sec_cards import _pick_modal, _drain as _sec_drain
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        foe_g = _place(state, "P1", _unit_def(name="G", number="51", hp=5))
        foe_s = _place(state, "P1", _unit_def(name="S", number="52", hp=5), arena="space")
        mine = _place(state, "P0", _unit_def(name="M", number="53", hp=5))
        state, _ = _play_event_from_hand(state, repo, "HMW", "54", resources=30)
        state = _sec_drain(state)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        state = _pick_modal(state, 1)                            # ground
        assert state.find_instance(foe_g.instance_id)[1].damage == 0   # not yet
        _enter_regroup(state)
        assert state.find_instance(foe_g.instance_id)[1].damage == 3
        assert state.find_instance(foe_s.instance_id)[1].damage == 0
        assert state.find_instance(mine.instance_id)[1].damage == 0
        assert not state.game_memory.damage_at_regroup


def test_HMW_64_scorch_pings_only_upgraded_units(repo):
    from swu.engine import tokens
    from tests.test_sor_cards import _fire_on_attack
    state = _make_state()
    scorch = _place(state, "P0", _get_card(repo, "HMW", "64"))
    plain = _place(state, "P1", _unit_def(name="Plain", number="51", hp=5))
    dressed = _place(state, "P1", _unit_def(name="Dressed", number="52", hp=5))
    tokens.attach_token(state, state.player_by_id("P1"), dressed, "Experience")
    state = _fire_on_attack(state, scorch)
    from swu.engine.actions import legal_actions, ChooseTarget
    offered = {a.target_id for a in legal_actions(_drive_to_target(state))
               if isinstance(a, ChooseTarget)}
    assert dressed.instance_id in offered and plain.instance_id not in offered


def _drive_to_target(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
    for _ in range(10):
        acts = legal_actions(state)
        if any(isinstance(a, ChooseTarget) for a in acts):
            return state
        acc = next((a for a in acts if isinstance(a, AcceptTrigger)), None)
        if acc is None:
            return state
        state = apply(state, acc)
    return state


class TestImperialCommandosHMW_68:

    def test_HMW_68_defeats_a_small_non_leader_unit(self, repo):
        state = _make_state()
        cmd = _place(state, "P0", _get_card(repo, "HMW", "68"))
        small = _place(state, "P1", _unit_def(name="Small", number="51", power=4, hp=9))
        big = _place(state, "P1", _unit_def(name="Big", number="52", power=5, hp=9))
        state = _fire_when_played(state, cmd)
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {a.target_id for a in legal_actions(_drive_to_target(state))
                   if isinstance(a, ChooseTarget)}
        assert small.instance_id in offered and big.instance_id not in offered
        state = _drive(state, _accept_and_target(small.instance_id))
        assert small.instance_id not in [u.instance_id
                                         for u in state.player_by_id("P1").ground_arena]


class TestQuiGonJinnHMW_78:

    def test_HMW_78_defeats_a_unit_that_attacked_your_base(self, repo):
        state = _make_state()
        qgj = _place(state, "P0", _get_card(repo, "HMW", "78"))
        raider = _place(state, "P1", _unit_def(name="Raider", number="51", hp=9))
        bystander = _place(state, "P1", _unit_def(name="By", number="52", hp=9))
        state.game_memory.base_attackers_this_round["P0"] = [raider.instance_id]
        state = _fire_when_played(state, qgj)
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {a.target_id for a in legal_actions(_drive_to_target(state))
                   if isinstance(a, ChooseTarget)}
        assert offered == {raider.instance_id}
        state = _drive(state, _accept_and_target(raider.instance_id))
        ground = [u.instance_id for u in state.player_by_id("P1").ground_arena]
        assert raider.instance_id not in ground and bystander.instance_id in ground
        assert qgj.instance_id in [u.instance_id
                                   for u in state.player_by_id("P0").ground_arena]

    def test_HMW_78_defeating_a_leader_costs_qui_gon(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        qgj = _place(state, "P0", _get_card(repo, "HMW", "78"))
        boss = _place_deployed_leader(state, "P1", _get_leader(repo, "HMW", "13"))
        state.game_memory.base_attackers_this_round["P0"] = [boss.instance_id]
        state = _drive(_fire_when_played(state, qgj), _accept_and_target(boss.instance_id))
        assert not state.player_by_id("P1").ground_arena
        assert qgj.instance_id not in [u.instance_id
                                       for u in state.player_by_id("P0").ground_arena]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:04 â€” Direct damage & removal
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def _offered_targets(state):
    from swu.engine.actions import legal_actions, ChooseTarget
    return {a.target_id for a in legal_actions(_drive_to_target(state))
            if isinstance(a, ChooseTarget)}


def _creature(name, number, cost, power=3, hp=3):
    return dataclasses.replace(_unit_def(name=name, number=number, power=power, hp=hp),
                               cost=cost, traits=("Creature",))


class TestRadiantVIIHMW_79:

    def test_HMW_79_takes_three_and_gains_a_shield(self, repo):
        from swu.engine.keywords import shields_on
        state = _make_state()
        rad = _place(state, "P0", _get_card(repo, "HMW", "79"), arena="space")
        state = _drive(_fire_when_played(state, rad), _accept_and_target())
        me = state.find_instance(rad.instance_id)[1]
        assert me.damage == 3
        assert shields_on(me) == 1

    def test_HMW_79_an_existing_shield_eats_the_damage_so_no_new_shield(self, repo):
        from swu.engine import tokens
        state = _make_state()
        rad = _place(state, "P0", _get_card(repo, "HMW", "79"), arena="space")
        tokens.attach_token(state, state.player_by_id("P0"), rad, "Shield")
        state = _drive(_fire_when_played(state, rad), _accept_and_target())
        me = state.find_instance(rad.instance_id)[1]
        assert me.damage == 0
        from swu.engine.keywords import shields_on
        assert shields_on(me) == 0


def test_HMW_86_n1_patroller_defeats_a_nearly_dead_non_leader(repo):
    state = _make_state()
    n1 = _place(state, "P0", _get_card(repo, "HMW", "86"), arena="space")
    weak = _place(state, "P1", _unit_def(name="Weak", number="51", hp=3))
    weak.damage = 2
    sturdy = _place(state, "P1", _unit_def(name="Sturdy", number="52", hp=3))
    state = _fire_when_played(state, n1)
    assert _offered_targets(state) == {weak.instance_id}
    state = _drive(state, _accept_and_target(weak.instance_id))
    assert [u.instance_id for u in state.player_by_id("P1").ground_arena] == [
        sturdy.instance_id]


class TestAlwaysABiggerFishHMW_99:

    def test_HMW_99_trades_up_to_a_bigger_creature_for_free(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        small = _place(state, "P0", _creature("Small", "51", cost=2))
        big = _to_hand(state, "P0", _creature("Big", "52", cost=5))
        huge = _to_hand(state, "P0", _creature("Huge", "53", cost=6))
        state, _ = _play_event_from_hand(state, repo, "HMW", "99", resources=20)
        from swu.engine.actions import ChooseTarget
        for _ in range(5):
            if state.pending_decisions[-1].kind == "play_from_hand":
                break
            acts = legal_actions(state)
            state = apply(state, next((a for a in acts if isinstance(a, ChooseTarget)
                                       and a.target_id == small.instance_id), acts[0]))
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        acts = legal_actions(state)
        names = {getattr(a, "instance_id", None) for a in acts}
        assert big.instance_id in names and huge.instance_id not in names
        play = next(a for a in acts if getattr(a, "instance_id", None) == big.instance_id)
        state = apply(state, play)
        p0 = state.player_by_id("P0")
        ground = [u.instance_id for u in p0.ground_arena]
        assert big.instance_id in ground and small.instance_id not in ground


def test_HMW_102_dragons_might_defeats_a_small_non_leader(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    small = _place(state, "P1", _unit_def(name="Small", number="51", power=4, hp=9))
    big = _place(state, "P1", _unit_def(name="Big", number="52", power=5, hp=9))
    state, _ = _play_event_from_hand(state, repo, "HMW", "102", resources=20)
    assert _offered_targets(state) == {small.instance_id}
    state = _drive(state, _accept_and_target(small.instance_id))
    assert [u.instance_id for u in state.player_by_id("P1").ground_arena] == [
        big.instance_id]


class TestBreachHMW_114:

    def _play(self, repo, state, mine, foe):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state, _ = _play_event_from_hand(state, repo, "HMW", "114", resources=20)
        for want in (mine.instance_id, foe.instance_id):
            for _ in range(5):
                acts = legal_actions(state)
                pick = next((a for a in acts if isinstance(a, ChooseTarget)
                             and a.target_id == want), None)
                if pick is not None:
                    state = apply(state, pick)
                    break
                state = apply(state, acts[0])
        return _drive(state)

    def test_HMW_114_friendly_unit_deals_its_power_in_its_arena(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _unit_def(name="Mine", number="51", power=3, hp=5))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=5))
        flier = _place(state, "P1", _unit_def(name="Fly", number="53", hp=5), arena="space")
        state = self._play(repo, state, mine, foe)
        assert state.find_instance(foe.instance_id)[1].damage == 3
        assert state.find_instance(flier.instance_id)[1].damage == 0
        assert _base(state, "P1").damage == 0

    def test_HMW_114_overwhelm_sends_the_excess_to_the_enemy_base(self, repo):
        from swu.engine.keywords import has_keyword, Keyword, Keyword
        state = _make_state()
        brute = dataclasses.replace(
            _unit_def(name="Brute", number="51", power=6, hp=5),
            text="Overwhelm", keywords=("Overwhelm",))
        mine = _place(state, "P0", brute)
        assert has_keyword(state, mine, Keyword.OVERWHELM)
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=4))
        foe.damage = 2
        state = self._play(repo, state, mine, foe)
        assert foe.instance_id not in [u.instance_id
                                       for u in state.player_by_id("P1").ground_arena]
        assert _base(state, "P1").damage == 4


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:05 â€” Direct damage & removal
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestEmerieKarrHMW_130:

    def test_HMW_130_pinging_a_friendly_unit_discounts_the_next_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        emerie = _place(state, "P0", _get_card(repo, "HMW", "130"))
        mine = _place(state, "P0", _unit_def(name="Mine", number="51", hp=5))
        nxt = _to_hand(state, "P0", _unit_def(name="Next", number="52"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, nxt, ps)
        state = _drive(_fire_when_played(state, emerie), _accept_and_target(mine.instance_id))
        assert state.find_instance(mine.instance_id)[1].damage == 1
        assert _play_cost(state, state.find_instance(nxt.instance_id)[1],
                          state.player_by_id("P0")) == before - 1

    def test_HMW_130_pinging_an_enemy_gives_no_discount(self, repo):
        state = _make_state()
        emerie = _place(state, "P0", _get_card(repo, "HMW", "130"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
        state = _drive(_fire_when_played(state, emerie), _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 1
        assert not state.game_memory.pending_play_discounts


def test_HMW_158_battle_scarred_destroyer_hurts_a_friendly_unit(repo):
    state = _make_state()
    bsd = _place(state, "P0", _get_card(repo, "HMW", "158"), arena="space")
    foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
    state = _fire_when_played(state, bsd)
    offered = _offered_targets(state)
    assert bsd.instance_id in offered and foe.instance_id not in offered
    state = _drive(state, _accept_and_target(bsd.instance_id))
    assert state.find_instance(bsd.instance_id)[1].damage == 4


class TestGeneralGrievousHMW_159:

    def test_HMW_159_when_played_hits_a_base(self, repo):
        state = _make_state()
        gg = _place(state, "P0", _get_card(repo, "HMW", "159"))
        enemy_base = _base(state, "P1").instance_id
        state = _drive(_fire_when_played(state, gg), _accept_and_target(enemy_base))
        assert _base(state, "P1").damage == 4

    def test_HMW_159_bases_cannot_be_healed(self, repo):
        from swu.engine.actions import _bases_cannot_heal
        state = _make_state()
        assert not _bases_cannot_heal(state)
        _place(state, "P0", _get_card(repo, "HMW", "159"))
        assert _bases_cannot_heal(state)


class TestArenaNexuHMW_182:

    def test_HMW_182_feeds_a_creature_and_readies_once_per_round(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        nexu = _place(state, "P0", _get_card(repo, "HMW", "182"))
        nexu.exhausted = True
        state = _drive(_fire_on_attack(state, nexu), _accept_and_target(nexu.instance_id))
        me = state.find_instance(nexu.instance_id)[1]
        assert me.damage == 3 and not me.exhausted
        me.exhausted = True
        state = _fire_on_attack(state, me)
        assert not _offers_accept(state)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# hmw-set:06 â€” Direct damage & removal
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def test_HMW_186_mining_guild_trespasser_hits_a_base_and_an_enemy(repo):
    state = _make_state()
    mgt = _place(state, "P0", _get_card(repo, "HMW", "186"))
    foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
    enemy_base = _base(state, "P1").instance_id

    def _pick(state, acts):
        from swu.engine.actions import AcceptTrigger, ChooseTarget
        for a in acts:
            if isinstance(a, AcceptTrigger):
                return a
        for want in (enemy_base, foe.instance_id):
            for a in acts:
                if isinstance(a, ChooseTarget) and a.target_id == want:
                    return a
        return None
    state = _drive(_fire_when_played(state, mgt), _pick)
    assert _base(state, "P1").damage == 2
    assert state.find_instance(foe.instance_id)[1].damage == 2


def test_HMW_207_maim_damages_and_exhausts(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
    foe.exhausted = False
    state, _ = _play_event_from_hand(state, repo, "HMW", "207", resources=20)
    state = _drive(state, _accept_and_target(foe.instance_id))
    unit = state.find_instance(foe.instance_id)[1]
    assert unit.damage == 1 and unit.exhausted


def test_HMW_217_dont_touch_anything_hits_one_random_enemy(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    a = _place(state, "P1", _unit_def(name="A", number="51", hp=5))
    b = _place(state, "P1", _unit_def(name="B", number="52", hp=5), arena="space")
    mine = _place(state, "P0", _unit_def(name="M", number="53", hp=5))
    state, _ = _play_event_from_hand(state, repo, "HMW", "217", resources=20)
    state = _drive(state)
    dmg = sorted(state.find_instance(u.instance_id)[1].damage for u in (a, b))
    assert dmg == [0, 3]
    assert state.find_instance(mine.instance_id)[1].damage == 0


class TestSeparatistHarbingerHMW_244:

    def _run(self, state):
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, ConfirmOpponentDamage)
        from tests.test_sec_cards import _drain as _sec_drain
        state = _sec_drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target" and top.deciding_player_id == "P1"
        pick = next(a for a in legal_actions(state) if isinstance(a, ChooseOwnTarget))
        state = apply(state, pick)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ConfirmOpponentDamage)))
        return state, pick.target_id

    def test_HMW_244_when_played_opponent_picks_then_two_damage(self, repo):
        state = _make_state()
        harb = _place(state, "P0", _get_card(repo, "HMW", "244"), arena="space")
        state, tid = self._run(_fire_when_played(state, harb))
        assert state.find_instance(tid)[1].damage == 2

    def test_HMW_244_on_attack_too(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        harb = _place(state, "P0", _get_card(repo, "HMW", "244"), arena="space")
        state, tid = self._run(_fire_on_attack(state, harb))
        assert state.find_instance(tid)[1].damage == 2


def test_HMW_271_landing_pad_buffs_friendly_space_units(repo):
    from swu.engine.actions import compute_power
    state = _make_state()
    flier = _place(state, "P0", _unit_def(power=2), arena="space")
    walker = _place(state, "P0", _unit_def(name="Walker", number="51", power=2))
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=2), arena="space")
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "271"))
    assert compute_power(state, flier) == 3
    assert compute_power(state, walker) == 2
    assert compute_power(state, foe) == 2


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Base-planet cards ("If you control a Naboo/Endor base")
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_NABOO = "20"     # Great Grass Plains
_ENDOR = "29"     # Dendroid Wilds
_KASHYYYK = "21"  # Kachirho


def _set_base(state, repo, pid, number):
    """Swap ``pid``'s synthetic test base for a real HMW base (planet printed on
    its art; see swu/cards/base_planets.py)."""
    _base(state, pid).card_def = _get_card(repo, "HMW", number)


def _to_decision(state, kind):
    """Auto-resolve the wrapper resolve_effects decisions until ``kind`` is on top."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(10):
        if not state.pending_decisions or state.pending_decisions[-1].kind == kind:
            return state
        acts = legal_actions(state)
        auto = next((a for a in acts if isinstance(a, AutoResolveEffects)), None)
        if auto is None:
            return state
        state = apply(state, auto)
    return state


class TestSandoAquaMonsterHMW_94:

    def test_HMW_94_naboo_base_defeats_ground_units_within_its_power(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectCombinedPowerUnit, FinishCombinedPowerPlay)
        state = _make_state()
        _set_base(state, repo, "P0", _NABOO)
        sando = _place(state, "P0", _get_card(repo, "HMW", "94"))
        three = _place(state, "P1", _unit_def(name="Three", number="51", power=3))
        two = _place(state, "P1", _unit_def(name="Two", number="52", power=2))
        four = _place(state, "P1", _unit_def(name="Four", number="53", power=4))
        flier = _place(state, "P1", _unit_def(name="Flier", number="54", power=1),
                       arena="space")
        state = _to_decision(_fire_when_played(state, sando), "combined_power_play")
        assert state.pending_decisions[-1].kind == "combined_power_play"

        def offered(state):
            return {a.unit_id for a in legal_actions(state)
                    if isinstance(a, SelectCombinedPowerUnit)}
        assert offered(state) == {three.instance_id, two.instance_id, four.instance_id}
        state = apply(state, SelectCombinedPowerUnit(three.instance_id))
        assert offered(state) == {two.instance_id}      # 3 + 4 would exceed 5
        state = apply(state, SelectCombinedPowerUnit(two.instance_id))
        state = apply(state, FinishCombinedPowerPlay())
        p1 = state.player_by_id("P1")
        assert {u.instance_id for u in p1.ground_arena} == {four.instance_id}
        assert {u.instance_id for u in p1.space_arena} == {flier.instance_id}
        assert {c.instance_id for c in p1.discard} == {three.instance_id, two.instance_id}
        assert state.find_instance(sando.instance_id)[1].damage == 5

    def test_HMW_94_does_nothing_without_a_naboo_base(self, repo):
        state = _make_state()
        _set_base(state, repo, "P0", _ENDOR)
        sando = _place(state, "P0", _get_card(repo, "HMW", "94"))
        _place(state, "P1", _unit_def(name="Two", number="52", power=2))
        state = _drain(_fire_when_played(state, sando))
        assert len(state.player_by_id("P1").ground_arena) == 1
        assert state.find_instance(sando.instance_id)[1].damage == 0


class TestAdamantEwoksHMW_177:

    def test_HMW_177_endor_base_hits_a_base_and_an_enemy(self, repo):
        state = _make_state()
        _set_base(state, repo, "P0", _ENDOR)
        ewoks = _place(state, "P0", _get_card(repo, "HMW", "177"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
        enemy_base = _base(state, "P1").instance_id

        def _pick(state, acts):
            from swu.engine.actions import AcceptTrigger, ChooseTarget
            for a in acts:
                if isinstance(a, AcceptTrigger):
                    return a
            for want in (enemy_base, foe.instance_id):
                for a in acts:
                    if isinstance(a, ChooseTarget) and a.target_id == want:
                        return a
            return None
        state = _drive(_fire_when_played(state, ewoks), _pick)
        assert _base(state, "P1").damage == 1
        assert state.find_instance(foe.instance_id)[1].damage == 1

    def test_HMW_177_no_offer_without_endor_base_or_another_ewok(self, repo):
        state = _make_state()
        _set_base(state, repo, "P0", _NABOO)
        ewoks = _place(state, "P0", _get_card(repo, "HMW", "177"))
        _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
        state = _fire_when_played(state, ewoks)
        assert not _offers_accept(state)


class TestGiantGoraxHMW_188:

    def _choice(self, state):
        state = _to_decision(state, "choose_two_modal")
        top = state.pending_decisions[-1]
        assert top.kind == "choose_two_modal" and top.deciding_player_id == "P1"
        return state

    def test_HMW_188_on_attack_opponent_discards_and_loses_a_resource(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        _set_base(state, repo, "P0", _ENDOR)
        gorax = _place(state, "P0", _get_card(repo, "HMW", "188"))
        p1 = state.player_by_id("P1")
        _give_resources(state, "P1", 3)
        _to_hand(state, "P1", _unit_def(name="Held", number="51"))
        hand, res = len(p1.hand), len(p1.resources)
        state = self._choice(_fire_on_attack(state, gorax))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectModalOption)
                                  and a.option_idx == 3))
        state = _drain(state)
        p1 = state.player_by_id("P1")
        assert len(p1.hand) == hand - 1
        assert len(p1.resources) == res - 1

    def test_HMW_188_when_defeated_opponent_takes_3_on_their_base(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption, ChooseTarget
        from tests.test_sor_cards import _fire_when_defeated
        state = _make_state()
        _set_base(state, repo, "P0", _ENDOR)
        gorax = _place(state, "P0", _get_card(repo, "HMW", "188"))
        state = self._choice(_fire_when_defeated(state, gorax))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectModalOption)
                                  and a.option_idx == 2))
        enemy_base = _base(state, "P1").instance_id
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy_base))
        state = _drain(state)
        assert _base(state, "P1").damage == 3

    def test_HMW_188_no_choice_without_endor_base(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        _set_base(state, repo, "P0", _NABOO)
        gorax = _place(state, "P0", _get_card(repo, "HMW", "188"))
        state = _fire_on_attack(state, gorax)
        assert not any(d.kind == "choose_two_modal" for d in state.pending_decisions)


class TestNightfallHMW_193:

    def _cast(self, repo, base_number):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        _set_base(state, repo, "P0", base_number)
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=5))
        attacker = _place(state, "P0", _unit_def(name="Mine", number="52", power=2))
        attacker.exhausted = False
        from swu.engine.actions import legal_actions, apply
        state, _ = _play_event_from_hand(state, repo, "HMW", "193", resources=20)
        pick = _accept_and_target(foe.instance_id)
        for _ in range(10):         # stop AT the granted attack, without taking it
            if (not state.pending_decisions
                    or state.pending_decisions[-1].kind == "granted_attack"):
                break
            acts = legal_actions(state)
            state = apply(state, pick(state, acts) or acts[0])
        return state, foe

    def test_HMW_193_endor_base_damages_then_grants_an_attack(self, repo):
        state, foe = self._cast(repo, _ENDOR)
        assert state.find_instance(foe.instance_id)[1].damage == 1
        assert state.pending_decisions[-1].kind == "granted_attack"

    def test_HMW_193_without_endor_base_only_damages(self, repo):
        state, foe = self._cast(repo, _NABOO)
        assert state.find_instance(foe.instance_id)[1].damage == 1
        assert not state.pending_decisions


class TestSurveillanceCruiserHMW_247:

    def _play(self, repo, enemy_base):
        state = _make_state()
        _set_base(state, repo, "P1", enemy_base)
        _deck(state, "P0")
        cruiser = _place(state, "P0", _get_card(repo, "HMW", "247"), arena="space")
        hand = len(state.player_by_id("P0").hand)
        state = _drain(_fire_when_played(state, cruiser))
        return len(state.player_by_id("P0").hand) - hand

    def test_HMW_247_draws_against_a_homeworld_base(self, repo):
        assert self._play(repo, _KASHYYYK) == 1

    def test_HMW_247_no_draw_against_another_base(self, repo):
        state = _make_state()
        _deck(state, "P0")
        cruiser = _place(state, "P0", _get_card(repo, "HMW", "247"), arena="space")
        state = _drain(_fire_when_played(state, cruiser))   # synthetic TST base
        assert len(state.player_by_id("P0").hand) == 0


def test_HMW_84_gunga_city_guard_shielded_with_naboo_base_or_another_gungan(repo):
    from swu.engine.keywords import has_keyword, Keyword
    state = _make_state()
    guard = _place(state, "P0", _get_card(repo, "HMW", "84"))
    assert not has_keyword(state, guard, Keyword.SHIELDED)
    _set_base(state, repo, "P0", _NABOO)
    assert has_keyword(state, guard, Keyword.SHIELDED)
    _set_base(state, repo, "P0", _ENDOR)
    assert not has_keyword(state, guard, Keyword.SHIELDED)
    _place(state, "P0", dataclasses.replace(_unit_def(name="Gungan", number="51"),
                                            traits=("Gungan",)))
    assert has_keyword(state, guard, Keyword.SHIELDED)


def test_HMW_90_opee_sea_killer_has_grit_only_with_naboo_base(repo):
    from swu.engine.keywords import has_keyword, Keyword
    state = _make_state()
    opee = _place(state, "P0", _get_card(repo, "HMW", "90"))
    _set_base(state, repo, "P0", _KASHYYYK)
    assert not has_keyword(state, opee, Keyword.GRIT)
    _set_base(state, repo, "P0", _NABOO)
    assert has_keyword(state, opee, Keyword.GRIT)


# ══════════════════════════════════════════════════════════════════════════════
# "When damage is dealt" cards (WhenDamageDealt)
# ══════════════════════════════════════════════════════════════════════════════


def _attack(state, attacker, defender=None, picker=None):
    """A real attack through ``apply`` — the settle point drains the damage ledger."""
    from swu.engine.actions import apply, AttackWithUnit
    attacker.exhausted = False
    state = apply(state, AttackWithUnit(attacker.instance_id,
                                        defender.instance_id if defender else None))
    return _drive(state, picker)


def _maim(state, repo, target_id, picker=None):
    """Play Maim HMW_207 (1 non-combat damage + exhaust) at ``target_id``."""
    from tests.test_sor_cards import _play_event_from_hand
    state, _ = _play_event_from_hand(state, repo, "HMW", "207", resources=20)
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, ChooseTarget) and a.target_id == target_id))
    return _drive(state, picker)


def _decline_all(state, acts):
    from swu.engine.actions import DeclineTrigger
    return next((a for a in acts if isinstance(a, DeclineTrigger)), None)


class TestDarthSidiousHMW_11:

    def test_HMW_11_undeployed_4_damage_pings_a_different_target(self, repo):
        state = _make_state()
        sid = _place_leader(state, "P0", _get_leader(repo, "HMW", "11"))
        hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=4, hp=9))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=1, hp=9))
        enemy_base = _base(state, "P1").instance_id
        seen = {}

        def _pick(state, acts):
            from swu.engine.actions import AcceptTrigger, ChooseTarget
            for a in acts:
                if isinstance(a, AcceptTrigger):
                    return a
            targets = {a.target_id for a in acts if isinstance(a, ChooseTarget)}
            if targets:
                seen["targets"] = targets
                return next(a for a in acts if isinstance(a, ChooseTarget)
                            and a.target_id == enemy_base)
            return None
        state = _attack(state, hitter, foe, _pick)
        assert state.find_instance(foe.instance_id)[1].damage == 4
        assert foe.instance_id not in seen["targets"]     # "a DIFFERENT unit or base"
        assert _base(state, "P1").damage == 1
        assert state.find_instance(sid.instance_id)[1].exhausted

    def test_HMW_11_ignores_damage_under_4(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "HMW", "11"))
        hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=3, hp=9))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=1, hp=9))
        state = _attack(state, hitter, foe)
        assert not _offers_accept(state)
        assert _base(state, "P1").damage == 0


class TestChamSyndullaHMW_13:

    def test_HMW_13_noncombat_damage_to_friendly_pings_an_enemy(self, repo):
        state = _make_state()
        cham = _place_leader(state, "P0", _get_leader(repo, "HMW", "13"))
        mine = _place(state, "P0", _unit_def(name="Mine", number="51", hp=5))
        enemy_base = _base(state, "P1").instance_id
        state = _maim(state, repo, mine.instance_id, _accept_and_target(enemy_base))
        assert _base(state, "P1").damage == 1
        assert state.find_instance(cham.instance_id)[1].exhausted

    def test_HMW_13_combat_damage_does_not_count(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "HMW", "13"))
        mine = _place(state, "P0", _unit_def(name="Mine", number="51", power=1, hp=9))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=2, hp=9))
        state = _attack(state, mine, foe)
        assert not _offers_accept(state)
        assert _base(state, "P1").damage == 0


def test_HMW_45_logray_pings_when_a_cheap_friendly_is_damaged(repo):
    state = _make_state()
    _place(state, "P0", _get_card(repo, "HMW", "45"))
    cheap = _place(state, "P0", _unit_def(name="Cheap", number="51", hp=5))   # cost 2
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=5))
    state = _maim(state, repo, cheap.instance_id, _accept_and_target(foe.instance_id))
    assert state.find_instance(foe.instance_id)[1].damage == 1


class TestArenaAcklayHMW_156:

    def test_HMW_156_survives_combat_damage_hits_each_enemy_base(self, repo):
        state = _make_state()
        hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=2, hp=9))
        acklay = _place(state, "P1", _get_card(repo, "HMW", "156"))
        state = _attack(state, hitter, acklay)
        assert state.find_instance(acklay.instance_id)[1].damage == 2
        assert _base(state, "P0").damage == 2      # P1's Acklay hits ITS enemy base

    def test_HMW_156_no_trigger_when_defeated(self, repo):
        state = _make_state()
        hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=9, hp=9))
        acklay = _place(state, "P1", _get_card(repo, "HMW", "156"))
        state = _attack(state, hitter, acklay)
        assert acklay.instance_id not in {u.instance_id
                                          for u in state.player_by_id("P1").ground_arena}
        assert _base(state, "P0").damage == 0


def test_HMW_169_crosshair_survives_each_draws_then_punishes_the_draw(repo):
    state = _make_state()
    _deck(state, "P0")
    _deck(state, "P1")
    hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=2, hp=9))
    cross = _place(state, "P1", _get_card(repo, "HMW", "169"))
    state = _attack(state, hitter, cross)
    assert len(state.player_by_id("P0").hand) == 1
    assert len(state.player_by_id("P1").hand) == 1
    # P0 (Crosshair's opponent) drew during the action phase: 2 to P0's base.
    assert _base(state, "P0").damage == 2


def test_HMW_166_gungi_discards_to_ready_after_surviving(repo):
    state = _make_state()
    gungi = _place(state, "P0", _get_card(repo, "HMW", "166"))
    gungi.exhausted = False
    held = _to_hand(state, "P0", _unit_def(name="Held", number="51"))
    state = _maim(state, repo, gungi.instance_id, _accept_and_target())
    me = state.find_instance(gungi.instance_id)[1]
    assert me.damage == 1 and not me.exhausted          # Maim exhausted it; readied
    assert held.instance_id in {c.instance_id for c in state.player_by_id("P0").discard}


def test_HMW_211_tech_exhausts_a_unit_after_surviving(repo):
    state = _make_state()
    tech = _place(state, "P0", _get_card(repo, "HMW", "211"))
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=5))
    foe.exhausted = False
    state = _maim(state, repo, tech.instance_id, _accept_and_target(foe.instance_id))
    assert state.find_instance(foe.instance_id)[1].exhausted


def test_HMW_13_bot_declines_the_deployed_cham_mirror_loop(repo):
    """Two deployed Chams would ping each other for ever; the bot declines."""
    from tests.test_sor_cards import _place_deployed_leader
    from swu.engine.actions import legal_actions, AcceptTrigger
    from swu.players.heuristic_bot import HeuristicBot
    cham = _get_leader(repo, "HMW", "13")
    state = _make_state()
    _place_deployed_leader(state, "P0", cham)
    mine = _place(state, "P0", _unit_def(name="Mine", number="51", hp=5))
    from tests.test_sor_cards import _play_event_from_hand
    from swu.engine.actions import apply, ChooseTarget
    state, _ = _play_event_from_hand(state, repo, "HMW", "207", resources=20)
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, ChooseTarget)
                              and a.target_id == mine.instance_id))
    for _ in range(10):                       # stop AT Cham's offer
        acts = legal_actions(state)
        if not state.pending_decisions or any(isinstance(a, AcceptTrigger) for a in acts):
            break
        state = apply(state, acts[0])
    # No mirror: the bot accepts its own ping.
    assert _offers_accept(state)
    bot = HeuristicBot("P0")
    view = state.view_for(state.pending_decisions[-1].deciding_player_id)
    assert type(bot.choose_action(view, legal_actions(state))).__name__ == "AcceptTrigger"
    # With a deployed Cham across the table, it declines.
    _place_deployed_leader(state, "P1", cham)
    view = state.view_for(state.pending_decisions[-1].deciding_player_id)
    assert type(bot.choose_action(view, legal_actions(state))).__name__ == "DeclineTrigger"


# ══════════════════════════════════════════════════════════════════════════════
# "While playing this unit" cost routes (CostRoute → the cost_route decision)
# ══════════════════════════════════════════════════════════════════════════════


def _plays(state, ci) -> bool:
    from swu.engine.actions import legal_actions, PlayCard
    return any(isinstance(a, PlayCard) and a.instance_id == ci.instance_id
               for a in legal_actions(state))


def _kinds(state) -> set:
    from swu.engine.actions import legal_actions
    return {type(a).__name__ for a in legal_actions(state)}


class TestGreaterSarlaccHMW_49:

    def _setup(self, repo, ready):
        from swu.engine.actions import _play_cost
        state = _make_state()
        sarlacc = _to_hand(state, "P0", _get_card(repo, "HMW", "49"))
        cost = _play_cost(state, sarlacc, state.player_by_id("P0"))  # incl. penalty
        _give_resources(state, "P0", ready(cost))
        return state, sarlacc, cost

    def test_HMW_49_defeat_ready_resources_to_play_it(self, repo):
        from swu.engine.actions import apply, PlayCard, PayCostRoute, CommitCostRoute
        state, sarlacc, cost = self._setup(repo, lambda c: -(-c // 3))  # ceil(c/3)
        ps = state.player_by_id("P0")
        start = len(ps.resources)
        assert start < cost and _plays(state, sarlacc)
        state = apply(state, PlayCard(sarlacc.instance_id))
        assert state.pending_decisions[-1].kind == "cost_route"
        paid = 0
        while "CommitCostRoute" not in _kinds(state):
            state = apply(state, PayCostRoute(None))
            paid += 1
        state = apply(state, CommitCostRoute())
        state = _drive(state)
        ps = state.player_by_id("P0")
        assert sarlacc.instance_id in {u.instance_id for u in ps.ground_arena}
        assert len(ps.resources) == start - paid
        assert max(0, cost - 3 * paid) <= start - paid

    def test_HMW_49_not_offered_when_no_route_affords_it(self, repo):
        # With R ready resources the best case is R defeated (cost - 3R ≤ 0), so
        # R < cost/3 can never pay.
        state, sarlacc, cost = self._setup(repo, lambda c: c // 3 - 1)
        assert not _plays(state, sarlacc)


class TestTheMarauderHMW_125:

    def _setup(self, repo, units):
        from swu.engine.actions import _play_cost
        state = _make_state()
        marauder = _to_hand(state, "P0", _get_card(repo, "HMW", "125"))
        cost = _play_cost(state, marauder, state.player_by_id("P0"))
        _give_resources(state, "P0", cost - 2)
        mine = [_place(state, "P0", _unit_def(name=f"M{i}", number=str(51 + i), hp=3))
                for i in range(units)]
        return state, marauder, mine

    def test_HMW_125_damage_two_friendly_units_to_pay_2_less(self, repo):
        from swu.engine.actions import apply, PlayCard, PayCostRoute, CommitCostRoute
        state, marauder, (a, b) = self._setup(repo, 2)
        assert _plays(state, marauder)
        state = apply(state, PlayCard(marauder.instance_id))
        assert "CommitCostRoute" not in _kinds(state)
        state = apply(state, PayCostRoute(a.instance_id))
        assert "CommitCostRoute" not in _kinds(state)
        state = apply(state, PayCostRoute(b.instance_id))
        state = apply(state, CommitCostRoute())
        state = _drive(state)
        ps = state.player_by_id("P0")
        assert marauder.instance_id in {u.instance_id for u in ps.space_arena + ps.ground_arena}
        assert [state.find_instance(u.instance_id)[1].damage for u in (a, b)] == [1, 1]
        assert ps.available_resources == 0

    def test_HMW_125_not_offered_without_enough_friendly_units(self, repo):
        state, marauder, _ = self._setup(repo, 1)
        assert not _plays(state, marauder)


# ══════════════════════════════════════════════════════════════════════════════
# Replacement effects without a replacement system
# ══════════════════════════════════════════════════════════════════════════════


class TestTyYorrickHMW_185:

    def test_HMW_185_friendly_ability_damage_to_enemies_gets_plus_1(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "HMW", "185"))
        mgt = _place(state, "P0", _get_card(repo, "HMW", "186"))   # 2 to a base + unit
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
        enemy_base = _base(state, "P1").instance_id

        def _pick(state, acts):
            from swu.engine.actions import AcceptTrigger, ChooseTarget
            for a in acts:
                if isinstance(a, AcceptTrigger):
                    return a
            for want in (enemy_base, foe.instance_id):
                for a in acts:
                    if isinstance(a, ChooseTarget) and a.target_id == want:
                        return a
            return None
        state = _drive(_fire_when_played(state, mgt), _pick)
        assert _base(state, "P1").damage == 3
        assert state.find_instance(foe.instance_id)[1].damage == 3

    def test_HMW_185_not_on_friendly_targets_or_combat(self, repo):
        state = _make_state()
        ty = _place(state, "P0", _get_card(repo, "HMW", "185"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=1, hp=9))
        state = _attack(state, ty, foe, _decline_all)
        assert state.find_instance(foe.instance_id)[1].damage == 4   # printed power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "HMW", "185"))
        mine = _place(state, "P0", _unit_def(name="Mine", number="51", hp=9))
        state = _maim(state, repo, mine.instance_id)
        assert state.find_instance(mine.instance_id)[1].damage == 1


class TestViceAdmiralRampartHMW_60:

    def _defeat_upgrade_by(self, repo, state, actor, upgrade_id):
        """Clan Vizsla Soldier ASH_165's When Defeated ("You may defeat an
        upgrade"), controlled by ``actor``."""
        from tests.test_sor_cards import _fire_when_defeated
        soldier = _place(state, actor, _get_card(repo, "ASH", "165"))
        return _drive(_fire_when_defeated(state, soldier), _accept_and_target(upgrade_id))

    def test_HMW_60_rampart_is_defeated_instead_of_a_base_upgrade(self, repo):
        state = _make_state()
        rampart = _place(state, "P1", _get_card(repo, "HMW", "60"))
        pad = _attach_to_base(state, "P1", _get_card(repo, "HMW", "271"))
        state = self._defeat_upgrade_by(repo, state, "P0", pad.instance_id)
        assert pad.instance_id in {u.instance_id for u in _base(state, "P1").attached_upgrades}
        assert rampart.instance_id not in {u.instance_id
                                           for u in state.player_by_id("P1").ground_arena}

    def test_HMW_60_never_replaces_a_friendly_defeat(self, repo):
        state = _make_state()
        rampart = _place(state, "P1", _get_card(repo, "HMW", "60"))
        pad = _attach_to_base(state, "P1", _get_card(repo, "HMW", "271"))
        state = self._defeat_upgrade_by(repo, state, "P1", pad.instance_id)
        assert pad.instance_id not in {u.instance_id
                                       for u in _base(state, "P1").attached_upgrades}
        assert rampart.instance_id in {u.instance_id
                                       for u in state.player_by_id("P1").ground_arena}


def test_damage_ledger_is_dropped_without_an_observer_on_board(repo):
    """The gate: an ordinary board never reaches fire_triggered_abilities."""
    state = _make_state()
    hitter = _place(state, "P0", _unit_def(name="Hitter", number="51", power=2, hp=9))
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", power=1, hp=9))
    state = _attack(state, hitter, foe)
    assert state.game_memory.damage_events == []


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:07 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _attach_card(host, card_def, owner_id):
    """Attach a real upgrade card to ``host`` directly (no triggers)."""
    import uuid
    from swu.engine.state import CardInstance
    ci = CardInstance(instance_id=f"{owner_id}_u_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=host.zone)
    host.attached_upgrades.append(ci)
    return ci


def _arena_ids(state, pid):
    ps = state.player_by_id(pid)
    return {u.instance_id for u in ps.ground_arena + ps.space_arena}


def test_HMW_249_frenzied_tri_fighters_defeats_a_cheap_upgrade(repo):
    state = _make_state()
    tri = _place(state, "P0", _get_card(repo, "HMW", "249"), arena="space")
    foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
    cheap_def = _get_card(repo, "HMW", "252")                     # cost 2
    cheap = _attach_card(foe, cheap_def, "P1")
    pricey = _attach_card(foe, dataclasses.replace(cheap_def, cost=4), "P1")
    state = _fire_when_played(state, tri)
    assert _offered_targets(state) == {cheap.instance_id}
    state = _drive(state, _accept_and_target(cheap.instance_id))
    left = {u.instance_id for u in state.find_instance(foe.instance_id)[1].attached_upgrades}
    assert left == {pricey.instance_id}


class TestVillainousAmbitionHMW_252:

    def _host(self, aspect):
        from swu.cards.models import AspectPip
        return dataclasses.replace(_unit_def(name="Host", number="51", hp=9),
                                   aspects=(AspectPip(0, aspect, None, False),))

    def test_HMW_252_villainy_host_deals_2_damage(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", self._host("Villainy"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=9))
        upg = _attach_card(host, _get_card(repo, "HMW", "252"), "P0")
        state = _drive(_fire_upgrade_played(state, upg, host),
                       _accept_and_target(foe.instance_id))
        assert state.find_instance(foe.instance_id)[1].damage == 2

    def test_HMW_252_non_villainy_host_does_nothing(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", self._host("Heroism"))
        _place(state, "P1", _unit_def(name="Foe", number="52", hp=9))
        upg = _attach_card(host, _get_card(repo, "HMW", "252"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        assert not state.pending_decisions


class TestForcedPacificationHMW_253:

    def _board(self, n_enemies):
        state = _make_state()
        mine = [_place(state, "P0", _unit_def(name=f"Mine{i}", number=str(51 + i)))
                for i in range(2)]
        foes = [_place(state, "P1", _unit_def(name=f"Foe{i}", number=str(60 + i)))
                for i in range(n_enemies)]
        return state, mine, foes

    def test_HMW_253_one_defeat_exhausts_two_chosen_enemies(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import (legal_actions, apply, SelectCullCard,
                                        FinishCull, ChooseCullDamageTarget)
        state, mine, foes = self._board(4)
        state, _ = _play_event_from_hand(state, repo, "HMW", "253")
        state = apply(state, SelectCullCard(mine[0].instance_id))
        state = apply(state, FinishCull())
        picks = [a for a in legal_actions(state) if isinstance(a, ChooseCullDamageTarget)]
        assert {a.target_id for a in picks} == {f.instance_id for f in foes}
        state = apply(state, ChooseCullDamageTarget(foes[0].instance_id))
        state = apply(state, ChooseCullDamageTarget(foes[2].instance_id))
        assert not state.pending_decisions
        exhausted = {f.instance_id for f in foes
                     if state.find_instance(f.instance_id)[1].exhausted}
        assert exhausted == {foes[0].instance_id, foes[2].instance_id}
        assert _arena_ids(state, "P0") == {mine[1].instance_id}

    def test_HMW_253_enough_defeats_exhaust_every_enemy_unprompted(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import apply, SelectCullCard
        state, mine, foes = self._board(3)
        state, _ = _play_event_from_hand(state, repo, "HMW", "253")
        state = apply(state, SelectCullCard(mine[0].instance_id))
        state = apply(state, SelectCullCard(mine[1].instance_id))   # pool empties
        assert not state.pending_decisions
        assert all(state.find_instance(f.instance_id)[1].exhausted for f in foes)
        assert not _arena_ids(state, "P0")


def test_HMW_263_wrecker_each_player_picks_a_unit_for_3_damage(repo):
    from swu.engine.actions import legal_actions, apply, ChooseUnitToDefeat
    state = _make_state()
    wrecker = _place(state, "P0", _get_card(repo, "HMW", "263"))
    pal = _place(state, "P0", _unit_def(name="Pal", number="51", hp=9))
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=9))
    other = _place(state, "P1", _unit_def(name="Other", number="53", hp=9))
    state = _fire_when_played(state, wrecker)
    offered = {a.target_id for a in legal_actions(state)
               if isinstance(a, ChooseUnitToDefeat)}
    assert offered == {wrecker.instance_id, pal.instance_id}
    state = apply(state, ChooseUnitToDefeat(pal.instance_id))
    state = apply(state, ChooseUnitToDefeat(foe.instance_id))
    dmg = {ci.instance_id: state.find_instance(ci.instance_id)[1].damage
           for ci in (wrecker, pal, foe, other)}
    assert dmg == {wrecker.instance_id: 0, pal.instance_id: 3,
                   foe.instance_id: 3, other.instance_id: 0}


def test_HMW_270_wild_space_wanderer_defeats_only_a_base_upgrade(repo):
    state = _make_state()
    wsw = _place(state, "P0", _get_card(repo, "HMW", "270"), arena="space")
    pad = _attach_to_base(state, "P1", _get_card(repo, "HMW", "271"))
    foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
    _attach_card(foe, _get_card(repo, "HMW", "252"), "P1")
    state = _fire_when_played(state, wsw)
    assert _offered_targets(state) == {pad.instance_id}
    state = _drive(state, _accept_and_target(pad.instance_id))
    assert not _base(state, "P1").attached_upgrades


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:08 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _costed(name, number, cost, power=2, hp=3):
    return dataclasses.replace(_unit_def(name=name, number=number, power=power, hp=hp),
                               cost=cost)


def _deck_card(state, owner_id, card_def, top=True):
    import uuid
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_dk_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.DECK)
    deck = state.player_by_id(owner_id).deck
    deck.insert(0, ci) if top else deck.append(ci)
    return ci


def _hand_ids(state, pid):
    return {c.instance_id for c in state.player_by_id(pid).hand}


class TestWicketHMW_14:

    def test_HMW_14_undeployed_exhausts_to_draw_when_attacking_up(self, repo):
        from tests.test_sor_cards import _place_leader, _fire_on_attack
        state = _make_state()
        _deck(state, "P0")
        wicket = _place_leader(state, "P0", _get_leader(repo, "HMW", "14"))
        small = _place(state, "P0", _costed("Small", "51", 1))
        big = _place(state, "P1", _costed("Big", "52", 5))
        before = len(state.player_by_id("P0").hand)
        state = _drive(_fire_on_attack(state, small, big), _accept_and_target())
        assert len(state.player_by_id("P0").hand) == before + 1
        assert state.find_instance(wicket.instance_id)[1].exhausted

    def test_HMW_14_no_offer_against_a_cheaper_unit(self, repo):
        from tests.test_sor_cards import _place_leader, _fire_on_attack
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "HMW", "14"))
        mid = _place(state, "P0", _costed("Mid", "51", 3))
        cheap = _place(state, "P1", _costed("Cheap", "52", 2))
        state = _fire_on_attack(state, mid, cheap)
        assert not state.pending_decisions

    def test_HMW_14_deployed_on_attack_draws_with_a_cheap_unit(self, repo):
        from tests.test_sor_cards import _place_deployed_leader, _fire_on_attack
        state = _make_state()
        _deck(state, "P0")
        wicket = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "14"))
        before = len(state.player_by_id("P0").hand)
        assert not _drive(_fire_on_attack(state, wicket)).player_by_id("P0").hand
        _place(state, "P0", _costed("Ewok", "51", 3))
        state = _drive(_fire_on_attack(state, wicket))
        assert len(state.player_by_id("P0").hand) == before + 1


class TestMaulHMW_16:

    def test_HMW_16_plays_a_unit_for_1_less_then_defeats_it_when_played_still_resolves(
            self, repo):
        from tests.test_sor_cards import _place_leader
        from swu.engine.actions import apply, PlayFromHand
        from swu.engine.actions.costs import _effective_cost
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "HMW", "16"))
        scout = _to_hand(state, "P0", _get_card(repo, "HMW", "85"))
        upg = _deck_card(state, "P0", _get_card(repo, "HMW", "252"))
        # Measure the full price first (``_make_state``'s base has no aspects).
        full = _effective_cost(scout.card_def, state.player_by_id("P0"), state)
        _give_resources(state, "P0", full - 1)
        assert _offers_ability(state, maul.instance_id)
        state = _use_ability(state, maul.instance_id)
        state = _drive(apply(state, PlayFromHand(scout.instance_id)))
        p0 = state.player_by_id("P0")
        assert not any(not r.exhausted for r in p0.resources)   # paid exactly full - 1
        assert scout.instance_id in {c.instance_id for c in p0.discard}
        assert scout.instance_id not in _arena_ids(state, "P0")
        assert upg.instance_id in _hand_ids(state, "P0")      # its When Played ran
        assert state.find_instance(maul.instance_id)[1].exhausted

    def test_HMW_16_when_deployed_replays_a_unit_defeated_this_phase(self, repo):
        from tests.test_sor_cards import _place_leader
        from swu.engine.actions import (legal_actions, apply, deploy_leader_as_effect,
                                        PlayFromHand)
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "HMW", "16"))
        fallen = _discard(state, "P0", _costed("Fallen", "51", 6))
        old = _discard(state, "P0", _costed("Old", "52", 1))
        state.game_memory.units_defeated_this_round.add(fallen.instance_id)
        _give_resources(state, "P0", 1)
        state = deploy_leader_as_effect(state, maul.instance_id)
        plays = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert plays == {fallen.instance_id}
        state = apply(state, PlayFromHand(fallen.instance_id))
        assert fallen.instance_id in _arena_ids(state, "P0")
        assert old.instance_id in {c.instance_id for c in state.player_by_id("P0").discard}


class TestKeeperOfSkaraNalHMW_41:

    def test_HMW_41_discarding_two_copies_gives_plus_15_and_overwhelm(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        keeper_def = _get_card(repo, "HMW", "41")
        keeper = _place(state, "P0", keeper_def)
        copies = [_to_hand(state, "P0", keeper_def) for _ in range(2)]
        state = _drive(_fire_on_attack(state, keeper), _accept_and_target())
        me = state.find_instance(keeper.instance_id)[1]
        assert compute_power(state, me) == 20
        assert has_keyword(state, me, Keyword.OVERWHELM)
        assert {c.instance_id for c in copies} <= {
            c.instance_id for c in state.player_by_id("P0").discard}

    def test_HMW_41_one_copy_is_not_enough(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        keeper_def = _get_card(repo, "HMW", "41")
        keeper = _place(state, "P0", keeper_def)
        _to_hand(state, "P0", keeper_def)
        assert not _fire_on_attack(state, keeper).pending_decisions


def test_HMW_48_vernestra_bottoms_units_and_gains_their_when_played(repo):
    from swu.engine.actions import (legal_actions, apply, SelectBottomDiscardCard,
                                    FinishBottomFromDiscard)
    state = _make_state()
    _deck(state, "P0")
    vern = _place(state, "P0", _get_card(repo, "HMW", "48"))
    scout = _discard(state, "P0", _get_card(repo, "HMW", "85"))       # cost 2
    pricey = _discard(state, "P0", _costed("Pricey", "51", 6))
    upg = _deck_card(state, "P0", _get_card(repo, "HMW", "252"))
    state = _fire_when_played(state, vern)
    offered = {a.instance_id for a in legal_actions(state)
               if isinstance(a, SelectBottomDiscardCard)}
    assert offered == {scout.instance_id}
    state = apply(state, SelectBottomDiscardCard(scout.instance_id))
    state = _drive(apply(state, FinishBottomFromDiscard()))
    p0 = state.player_by_id("P0")
    assert p0.deck[-1].instance_id == scout.instance_id or scout.instance_id in {
        c.instance_id for c in p0.deck}
    assert upg.instance_id in _hand_ids(state, "P0")         # Scout's search, as Vernestra
    assert pricey.instance_id in {c.instance_id for c in p0.discard}


def test_HMW_61_krennic_draws_only_with_an_upgraded_base(repo):
    from tests.test_sor_cards import _fire_on_attack
    state = _make_state()
    _deck(state, "P0")
    krennic = _place(state, "P0", _get_card(repo, "HMW", "61"))
    assert not _drive(_fire_on_attack(state, krennic)).player_by_id("P0").hand
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "271"))
    assert len(_drive(_fire_on_attack(state, krennic)).player_by_id("P0").hand) == 1


def test_HMW_85_remote_scout_draws_an_upgrade_from_the_top_8(repo):
    state = _make_state()
    _deck(state, "P0", n=7)
    upg = _deck_card(state, "P0", _get_card(repo, "HMW", "252"), top=False)  # 8th card
    scout = _place(state, "P0", _get_card(repo, "HMW", "85"))
    state = _drive(_fire_when_played(state, scout))
    assert _hand_ids(state, "P0") == {upg.instance_id}


def test_HMW_101_trust_yourself_shields_a_unit_and_draws_from_top_3(repo):
    from tests.test_sor_cards import _play_event_from_hand
    from swu.engine.keywords import shields_on
    state = _make_state()
    _deck(state, "P0", n=5)
    ally = _place(state, "P0", _unit_def(name="Ally", number="51"))
    top3 = [c.instance_id for c in state.player_by_id("P0").deck[:3]]
    state, _ = _play_event_from_hand(state, repo, "HMW", "101")
    state = _drive(state, _accept_and_target(ally.instance_id))
    assert shields_on(state.find_instance(ally.instance_id)[1]) == 1
    hand = _hand_ids(state, "P0")
    assert len(hand) == 1 and hand <= set(top3)


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:09 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def test_HMW_103_disposable_b1_draws_after_another_friendly_entry(repo):
    state = _make_state()
    _deck(state, "P0")
    b1 = _place(state, "P0", _get_card(repo, "HMW", "103"))
    state.game_memory.units_played_this_phase.add(b1.instance_id)
    assert not _drive(_fire_when_played(state, b1)).player_by_id("P0").hand
    pal = _place(state, "P0", _unit_def(name="Pal", number="51"))
    state.game_memory.units_played_this_phase.add(pal.instance_id)
    foe = _place(state, "P1", _unit_def(name="Foe", number="52"))
    state.game_memory.units_played_this_phase.add(foe.instance_id)
    assert len(_drive(_fire_when_played(state, b1)).player_by_id("P0").hand) == 1


class TestBogaHMW_122:

    def _board(self, repo):
        state = _make_state()
        boga = _place(state, "P0", _get_card(repo, "HMW", "122"))
        ally = _discard(state, "P0", _costed("Ally", "51", 3))
        tank = _discard(state, "P0", dataclasses.replace(
            _costed("Tank", "52", 3), traits=("Vehicle",)))
        twin = _discard(state, "P0", _get_card(repo, "HMW", "122"))
        return state, boga, ally, tank, twin

    def test_HMW_122_when_played_grants_a_discounted_replay_this_phase(self, repo):
        from swu.engine.actions import (legal_actions, apply, SelectBottomDiscardCard,
                                        FinishBottomFromDiscard, PlayFromDiscard)
        state, boga, ally, tank, twin = self._board(repo)
        state = _fire_when_played(state, boga)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)}
        assert offered == {ally.instance_id}
        state = apply(state, SelectBottomDiscardCard(ally.instance_id))
        if state.pending_decisions:
            state = apply(state, FinishBottomFromDiscard())
        assert ally.instance_id in {c.instance_id for c in state.player_by_id("P0").discard}
        _give_resources(state, "P0", 2)                       # 3 - 1
        state.active_player_index = 0                         # P0's next action
        plays =[a for a in legal_actions(state) if isinstance(a, PlayFromDiscard)]
        assert [(a.instance_id, a.discount) for a in plays] == [(ally.instance_id, 1)]
        state = apply(state, plays[0])
        assert ally.instance_id in _arena_ids(state, "P0")

    def test_HMW_122_when_defeated_also_chooses(self, repo):
        from tests.test_sor_cards import _fire_when_defeated
        from swu.engine.actions import legal_actions, SelectBottomDiscardCard
        state, boga, ally, _tank, _twin = self._board(repo)
        state = _fire_when_defeated(state, boga)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)}
        assert offered == {ally.instance_id}


class TestLocalSupportHMW_148:

    def _play(self, repo, top_traits):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _unit_def(name="Trooper", number="51"))  # Trooper
        top = _deck_card(state, "P0", dataclasses.replace(
            _unit_def(name="Top", number="52"), traits=top_traits))
        upg = _attach_card(host, _get_card(repo, "HMW", "148"), "P0")
        return _drive(_fire_upgrade_played(state, upg, host)), top

    def test_HMW_148_draws_a_top_card_sharing_a_trait(self, repo):
        state, top = self._play(repo, ("Trooper", "Rebel"))
        assert _hand_ids(state, "P0") == {top.instance_id}

    def test_HMW_148_leaves_an_unrelated_top_card(self, repo):
        state, top = self._play(repo, ("Creature",))
        assert not state.player_by_id("P0").hand
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id


def test_HMW_173_rebel_operation_discounts_per_rebel_unit_and_leader(repo):
    from tests.test_sor_cards import _place_leader
    from swu.engine.actions.costs import _play_cost
    state = _make_state()
    op = _to_hand(state, "P0", _get_card(repo, "HMW", "173"))
    ps = state.player_by_id("P0")
    # The leader's aspects move the base price, so measure with it already placed.
    leader = _place_leader(state, "P0", _get_leader(repo, "HMW", "14"))     # an Ewok
    _place(state, "P0", _unit_def(name="Imp", number="52"))           # not Rebel
    base_cost = _play_cost(state, op, ps)
    _place(state, "P0", dataclasses.replace(_unit_def(name="Reb", number="51"),
                                            traits=("Rebel",)))
    leader.card_def = dataclasses.replace(leader.card_def, traits=("Rebel",))
    assert base_cost - _play_cost(state, op, ps) == 2
    _deck(state, "P0")
    from tests.test_sor_cards import _play_event_from_hand
    state, _ = _play_event_from_hand(state, repo, "HMW", "173")
    assert len(state.player_by_id("P0").hand) >= 2


class TestStormchaserHMW_180:

    def _disaster(self):
        return dataclasses.replace(_unit_def(name="Quake", number="51"),
                                   traits=("Disaster",))

    def test_HMW_180_draws_with_a_disaster_in_the_discard(self, repo):
        state = _make_state()
        _deck(state, "P0")
        sc = _place(state, "P0", _get_card(repo, "HMW", "180"))
        _discard(state, "P0", self._disaster())
        assert len(_drive(_fire_when_played(state, sc)).player_by_id("P0").hand) == 1

    def test_HMW_180_no_draw_without_a_disaster(self, repo):
        state = _make_state()
        _deck(state, "P0")
        sc = _place(state, "P0", _get_card(repo, "HMW", "180"))
        assert not _drive(_fire_when_played(state, sc)).player_by_id("P0").hand


def test_HMW_189_neebray_manta_draws_three(repo):
    state = _make_state()
    _deck(state, "P0")
    manta = _place(state, "P0", _get_card(repo, "HMW", "189"), arena="space")
    assert len(_drive(_fire_when_played(state, manta)).player_by_id("P0").hand) == 3


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:10 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def test_HMW_204_nightbrother_replays_a_discard_unit_ready_for_3_less(repo):
    from swu.engine.actions import legal_actions, apply, PlayFromHand
    state = _make_state()
    nb = _place(state, "P0", _get_card(repo, "HMW", "204"), arena="space")
    fallen = _discard(state, "P0", _costed("Fallen", "51", 5))
    _give_resources(state, "P0", 2)
    state = _fire_when_played(state, nb)
    plays = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
    assert plays == {fallen.instance_id}
    state = apply(state, PlayFromHand(fallen.instance_id))
    unit = state.find_instance(fallen.instance_id)[1]
    assert fallen.instance_id in _arena_ids(state, "P0") and not unit.exhausted


class TestL337HMW_215:

    def _play_cheap_event(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        _place(state, "P0", _get_card(repo, "HMW", "215"))
        for i in range(2):
            _place(state, "P1", _costed(f"Big{i}", str(51 + i), 6, power=6, hp=9))
        state, evt = _play_event_from_hand(state, repo, "HMW", "238")   # cost 2
        return _drive(state, _accept_and_target()), evt

    def test_HMW_215_grants_a_free_replay_once_per_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromDiscard
        state, evt = self._play_cheap_event(repo)
        state.active_player_index = 0
        replay = [a for a in legal_actions(state)
                  if isinstance(a, PlayFromDiscard) and a.instance_id == evt.instance_id]
        assert replay and replay[0].free
        state = _drive(apply(state, replay[0]), _accept_and_target())
        assert len(state.player_by_id("P1").hand) == 2             # both bounced
        assert evt.instance_id not in state.game_memory.free_discard_play_this_phase

    def test_HMW_215_ignores_an_expensive_event(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        _place(state, "P0", _get_card(repo, "HMW", "215"))
        _deck(state, "P0")
        _place(state, "P0", dataclasses.replace(_unit_def(name="Reb", number="51"),
                                                traits=("Rebel",)))
        state, _ = _play_event_from_hand(state, repo, "HMW", "173")   # costs 4
        state = _drive(state)
        assert not state.game_memory.free_discard_play_this_phase


class TestSandcrawlerSalesTeamHMW_222:

    def test_HMW_222_tatooine_base_bounces_a_cheap_upgrade(self, repo):
        state = _make_state()
        _set_base(state, repo, "P0", "19")                        # Tatooine
        sst = _place(state, "P0", _get_card(repo, "HMW", "222"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
        upg = _attach_card(foe, _get_card(repo, "HMW", "252"), "P1")
        state = _drive(_fire_when_played(state, sst), _accept_and_target(upg.instance_id))
        assert upg.instance_id in _hand_ids(state, "P1")

    def test_HMW_222_no_offer_without_tatooine(self, repo):
        state = _make_state()
        sst = _place(state, "P0", _get_card(repo, "HMW", "222"))
        foe = _place(state, "P1", _unit_def(name="Foe", number="51", hp=9))
        _attach_card(foe, _get_card(repo, "HMW", "252"), "P1")
        assert not _fire_when_played(state, sst).pending_decisions


class TestMonCalCruiserHMW_232:

    def _modes(self, repo, opp_hand=True):
        from swu.engine.actions import legal_actions, ChooseModalOption
        state = _make_state()
        mc = _place(state, "P0", _get_card(repo, "HMW", "232"), arena="space")
        _place(state, "P0", _unit_def(name="Striker", number="51"))
        _place(state, "P1", _unit_def(name="Foe", number="52", hp=9))
        if opp_hand:
            _to_hand(state, "P1", _unit_def(name="Secret", number="53"))
        state = _to_decision(_fire_when_played(state, mc), "modal")
        return state, {a.mode for a in legal_actions(state)
                       if isinstance(a, ChooseModalOption)}

    def test_HMW_232_attack_mode_grants_an_attack(self, repo):
        from swu.engine.actions import apply, ChooseModalOption
        state, modes = self._modes(repo)
        assert modes == {"attack_plus_2", "peek_hand_discard_draw"}
        state = apply(state, ChooseModalOption("attack_plus_2"))
        assert state.pending_decisions[-1].kind == "granted_attack"

    def test_HMW_232_peek_mode_looks_at_the_hand(self, repo):
        from swu.engine.actions import apply, ChooseModalOption
        state, _ = self._modes(repo)
        state = apply(state, ChooseModalOption("peek_hand_discard_draw"))
        assert state.pending_decisions[-1].kind == "name_and_discard"

    def test_HMW_232_peek_mode_needs_an_opponent_hand(self, repo):
        _, modes = self._modes(repo, opp_hand=False)
        assert modes == {"attack_plus_2"}


def test_HMW_236_booma_ball_returns_a_cheap_upgrade(repo):
    from tests.test_sor_cards import _fire_upgrade_played
    state = _make_state()
    host = _place(state, "P0", _unit_def(name="Host", number="51", hp=9))
    foe = _place(state, "P1", _unit_def(name="Foe", number="52", hp=9))
    target = _attach_card(foe, _get_card(repo, "HMW", "252"), "P1")
    ball = _attach_card(host, _get_card(repo, "HMW", "236"), "P0")
    state = _drive(_fire_upgrade_played(state, ball, host),
                   _accept_and_target(target.instance_id))
    assert target.instance_id in _hand_ids(state, "P1")


def test_HMW_238_exploit_confidence_bounces_a_6_power_non_leader(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    big = _place(state, "P1", _costed("Big", "51", 6, power=6, hp=9))
    _place(state, "P1", _costed("Mid", "52", 5, power=5, hp=9))
    state, _ = _play_event_from_hand(state, repo, "HMW", "238")
    from swu.engine.actions import legal_actions, ChooseTarget
    offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
    assert offered <= {big.instance_id}
    state = _drive(state, _accept_and_target(big.instance_id))
    assert big.instance_id in _hand_ids(state, "P1")


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:11 — the HMW leader block + Hunter
# ══════════════════════════════════════════════════════════════════════════════


def _with_aspect(card_def, *aspects):
    from swu.cards.models import AspectPip
    pips = tuple(AspectPip(position=i, name=a, color="", is_duplicate=False)
                 for i, a in enumerate(aspects))
    return dataclasses.replace(card_def, aspects=pips)


def _kw_unit(name, number, text, keywords, power=2, hp=5):
    return dataclasses.replace(_unit_def(name=name, number=number, power=power, hp=hp),
                               text=text, keywords=keywords)


def _resource_card(state, owner_id, card_def, exhausted=False):
    import uuid
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.RESOURCES)
    ci.face_down = True
    ci.exhausted = exhausted
    state.player_by_id(owner_id).resources.append(ci)
    return ci


def _step_to(state, kind, picker=None, limit=10):
    """Resolve decisions (via ``picker``, else the first legal action) until one of
    ``kind`` is on top; fails if the stack drains first."""
    from swu.engine.actions import legal_actions, apply
    for _ in range(limit):
        assert state.pending_decisions, f"stack drained before a {kind} decision"
        if state.pending_decisions[-1].kind == kind:
            return state
        acts = legal_actions(state)
        state = apply(state, (picker(state, acts) if picker else None) or acts[0])
    raise AssertionError(f"no {kind} decision within {limit} steps")


def _granted_attack(state, attacker_id, defender_id=None):
    from swu.engine.actions import apply, AttackWithUnit
    assert state.pending_decisions[-1].kind == "granted_attack"
    return apply(state, AttackWithUnit(attacker_id, defender_id))


class TestAsajjVentressHMW_1:

    def test_HMW_1_raid_becomes_restore_for_the_attack(self, repo):
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "HMW", "1"))
        raider = _place(state, "P0", _kw_unit("Raider", "51", "Raid 2", ("Raid",)))
        _base(state, "P0").damage = 5
        state = _granted_attack(_use_ability(state, asajj.instance_id),
                                raider.instance_id)
        state = _drive(state)
        assert _base(state, "P1").damage == 2       # no Raid bonus
        assert _base(state, "P0").damage == 3       # Restore 2 instead

    def test_HMW_1_restore_becomes_raid_and_the_swap_lapses(self, repo):
        from swu.engine.keywords import Keyword, has_keyword
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "HMW", "1"))
        healer = _place(state, "P0", _kw_unit("Healer", "51", "Restore 2", ("Restore",)))
        _base(state, "P0").damage = 5
        state = _drive(_granted_attack(_use_ability(state, asajj.instance_id),
                                       healer.instance_id))
        assert _base(state, "P1").damage == 4       # Raid 2
        assert _base(state, "P0").damage == 5       # no Restore
        unit = state.find_instance(healer.instance_id)[1]
        assert has_keyword(state, unit, Keyword.RESTORE)
        assert not has_keyword(state, unit, Keyword.RAID)

    def test_HMW_1_deployed_has_restore_2_and_a_free_action(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        from swu.engine.keywords import Keyword, has_keyword, keyword_value
        state = _make_state()
        asajj = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "1"))
        assert keyword_value(state, asajj, Keyword.RESTORE) == 2
        assert not has_keyword(state, asajj, Keyword.RAID)
        assert _offers_ability(state, asajj.instance_id)
        asajj.exhausted = True                       # nothing left able to attack
        assert not _offers_ability(state, asajj.instance_id)


class TestOmegaHMW_6:

    def test_HMW_6_attack_with_a_heroism_unit_that_gains_grit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 1)
        omega = _place_leader(state, "P0", _get_leader(repo, "HMW", "6"))
        hero = _place(state, "P0", _with_aspect(_unit_def("Hero", "51", power=1, hp=9),
                                                "Heroism"))
        hero.damage = 3
        plain = _place(state, "P0", _unit_def("Plain", "52"))
        state = _use_ability(state, omega.instance_id)
        from swu.engine.actions import legal_actions, AttackWithUnit
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert hero.instance_id in attackers and plain.instance_id not in attackers
        state = _drive(_granted_attack(state, hero.instance_id))
        assert _base(state, "P1").damage == 4       # 1 power + Grit 3

    def test_HMW_6_deployed_gives_other_heroism_units_grit(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        from swu.engine.keywords import Keyword, has_keyword
        state = _make_state()
        omega = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "6"))
        hero = _place(state, "P0", _with_aspect(_unit_def("Hero", "51"), "Heroism"))
        plain = _place(state, "P0", _unit_def("Plain", "52"))
        assert has_keyword(state, hero, Keyword.GRIT)
        assert not has_keyword(state, plain, Keyword.GRIT)
        assert not has_keyword(state, omega, Keyword.GRIT)


class TestDarthVaderHMW_7:

    def test_HMW_7_undeployed_gives_cost_3_plus_units_raid_1(self, repo):
        from swu.engine.keywords import Keyword, keyword_value
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "HMW", "7"))
        big = _place(state, "P0", _costed("Big", "51", 3))
        small = _place(state, "P0", _costed("Small", "52", 2))
        assert keyword_value(state, big, Keyword.RAID) == 1
        assert keyword_value(state, small, Keyword.RAID) == 0

    def test_HMW_7_deployed_raid_1_and_aura_for_others(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        from swu.engine.keywords import Keyword, keyword_value
        state = _make_state()
        vader = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "7"))
        big = _place(state, "P0", _costed("Big", "51", 4))
        assert keyword_value(state, vader, Keyword.RAID) == 1   # not 2
        assert keyword_value(state, big, Keyword.RAID) == 1


class TestGeneralGrievousHMW_8:

    def test_HMW_8_plays_two_units_one_at_a_time(self, repo):
        from swu.engine.actions import apply, legal_actions, PlayFromHand
        state = _make_state()
        _give_resources(state, "P0", 4)
        gg = _place_leader(state, "P0", _get_leader(repo, "HMW", "8"))
        a = _to_hand(state, "P0", _costed("A", "51", 2))
        b = _to_hand(state, "P0", _costed("B", "52", 2))
        state = _use_ability(state, gg.instance_id)
        state = apply(state, PlayFromHand(a.instance_id))
        nxt = [x for x in legal_actions(state) if isinstance(x, PlayFromHand)]
        assert [x.instance_id for x in nxt] == [b.instance_id]
        state = _drive(apply(state, nxt[0]))
        assert {a.instance_id, b.instance_id} <= _arena_ids(state, "P0")

    def test_HMW_8_deployed_gets_plus_3_with_more_units(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        from swu.engine.actions import compute_power
        state = _make_state()
        gg = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "8"))
        foe = _place(state, "P1", _unit_def("Foe", "52"))
        assert compute_power(state, gg) == 3
        state.player_by_id("P1").ground_arena.remove(foe)
        assert compute_power(state, gg) == 6


class TestChewbaccaHMW_9:

    def test_HMW_9_exhausted_unit_attacks_but_not_a_base(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        _give_resources(state, "P0", 2)
        chewie = _place_leader(state, "P0", _get_leader(repo, "HMW", "9"))
        tired = _place(state, "P0", _unit_def("Tired", "51"))
        tired.exhausted = True
        foe = _place(state, "P1", _unit_def("Foe", "52", hp=9))
        state = _use_ability(state, chewie.instance_id)
        opts = {(a.attacker_id, a.defender_id) for a in legal_actions(state)
                if isinstance(a, AttackWithUnit)}
        assert opts == {(tired.instance_id, foe.instance_id)}

    def test_HMW_9_deployed_action_once_each_round(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        chewie = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "9"))
        tired = _place(state, "P0", _unit_def("Tired", "51"))
        tired.exhausted = True
        foe = _place(state, "P1", _unit_def("Foe", "52", hp=9))
        state = _drive(_granted_attack(_use_ability(state, chewie.instance_id),
                                       tired.instance_id, foe.instance_id))
        state.active_player_index = 0
        assert not _offers_ability(state, chewie.instance_id)


class TestOshaHMW_17:

    def _setup(self, repo, villain_cost=2):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        osha = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "17"))
        villain = _resource_card(state, "P0", _with_aspect(
            _costed("Villain", "51", villain_cost), "Villainy"))
        _give_resources(state, "P0", 2)
        return state, osha, villain

    def test_HMW_17_plays_a_villainy_resource_then_may_resource(self, repo):
        from swu.engine.actions import apply, PlayFromHand, SelectHandCardToResource
        state, osha, villain = self._setup(repo)
        spare = _to_hand(state, "P0", _unit_def("Spare", "53"))
        state = _use_ability(state, osha.instance_id)
        # Villainy penalty (+2) waived: cost 2 from the two OTHER resources.
        state = apply(state, PlayFromHand(villain.instance_id))
        assert villain.instance_id in _arena_ids(state, "P0")
        ps = state.player_by_id("P0")
        assert all(r.exhausted for r in ps.resources)
        assert state.pending_decisions[-1].kind == "resource_from_hand"
        state = apply(state, SelectHandCardToResource(spare.instance_id))
        res = next(r for r in state.player_by_id("P0").resources
                   if r.instance_id == spare.instance_id)
        assert res.exhausted

    def test_HMW_17_not_offered_when_the_card_cannot_pay_for_itself(self, repo):
        # Cost 3 vs 2 OTHER ready resources: the ready Villain can't fund itself.
        state, osha, villain = self._setup(repo, villain_cost=3)
        assert not _offers_ability(state, osha.instance_id)
        villain.exhausted = True       # same budget, so still nothing playable
        assert not _offers_ability(state, osha.instance_id)
        _give_resources(state, "P0", 1)
        assert _offers_ability(state, osha.instance_id)

    def test_HMW_17_not_offered_without_a_villainy_resource(self, repo):
        from tests.test_sor_cards import _place_deployed_leader
        state = _make_state()
        osha = _place_deployed_leader(state, "P0", _get_leader(repo, "HMW", "17"))
        _resource_card(state, "P0", _costed("Neutral", "51", 1))
        _give_resources(state, "P0", 3)
        assert not _offers_ability(state, osha.instance_id)

    def test_HMW_17_undeployed_needs_a_defeated_heroism_unit(self, repo):
        state = _make_state()
        osha = _place_leader(state, "P0", _get_leader(repo, "HMW", "17"))
        _resource_card(state, "P0", _with_aspect(_costed("Villain", "51", 2), "Villainy"))
        _give_resources(state, "P0", 2)
        assert not _offers_ability(state, osha.instance_id)
        state.game_memory.defeated_aspects_this_round["P0"] = ["Heroism"]
        assert _offers_ability(state, osha.instance_id)


class TestHunterHMW_35:

    def _modal(self, repo):
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "HMW", "35"))
        hunter.exhausted = True
        state = _fire_when_played(state, hunter)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        return state, hunter

    def test_HMW_35_the_same_option_twice_gives_two_shields(self, repo):
        from swu.engine.actions import apply, SelectModalOption
        state, hunter = self._modal(repo)
        state = apply(state, SelectModalOption(1))
        state = apply(state, SelectModalOption(1))   # repeat is allowed
        state = _drive(state, _accept_and_target(hunter.instance_id))
        unit = state.find_instance(hunter.instance_id)[1]
        assert sum(1 for u in unit.attached_upgrades
                   if u.card_def.name == "Shield") == 2

    def test_HMW_35_attack_option_lets_exhausted_hunter_hit_a_unit(self, repo):
        from swu.engine.actions import apply, legal_actions, SelectModalOption, AttackWithUnit
        state, hunter = self._modal(repo)
        foe = _place(state, "P1", _unit_def("Foe", "52", hp=9))
        state = apply(state, SelectModalOption(2))
        state = apply(state, SelectModalOption(2))
        for _ in range(5):
            if not state.pending_decisions:
                break
            if state.pending_decisions[-1].kind == "granted_attack":
                break
            state = apply(state, legal_actions(state)[0])
        opts = {(a.attacker_id, a.defender_id) for a in legal_actions(state)
                if isinstance(a, AttackWithUnit)}
        assert opts == {(hunter.instance_id, foe.instance_id)}


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:12 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def test_HMW_39_mother_talzin_gives_others_restore_1(repo):
    from swu.engine.keywords import Keyword, keyword_value
    state = _make_state()
    talzin = _place(state, "P0", _get_card(repo, "HMW", "39"))
    other = _place(state, "P0", _unit_def("Other", "51"))
    foe = _place(state, "P1", _unit_def("Foe", "52"))
    assert keyword_value(state, other, Keyword.RESTORE) == 1
    assert keyword_value(state, foe, Keyword.RESTORE) == 0
    assert keyword_value(state, talzin, Keyword.RESTORE) == 0
    assert keyword_value(state, talzin, Keyword.RAID) == 1


class TestDookuHMW_42:

    def test_HMW_42_readies_a_unit_and_heals_its_cost(self, repo):
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "HMW", "42"))
        tired = _place(state, "P0", _costed("Tired", "51", 4))
        tired.exhausted = True
        _base(state, "P0").damage = 10
        state = _drive(_fire_when_played(state, dooku),
                       _accept_and_target(tired.instance_id))
        assert not state.find_instance(tired.instance_id)[1].exhausted
        assert _base(state, "P0").damage == 6

    def test_HMW_42_ready_units_are_not_offered(self, repo):
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "HMW", "42"))
        _place(state, "P0", _costed("Fresh", "51", 4))
        state = _fire_when_played(state, dooku)
        assert not state.pending_decisions


class TestImaGunDiHMW_44:

    def _defeat(self, repo, my_res, their_res):
        from tests.test_sor_cards import _defeat_and_fire
        state = _make_state()
        _give_resources(state, "P0", my_res)
        _give_resources(state, "P1", their_res)
        _deck(state, "P0")
        spare = _to_hand(state, "P0", _unit_def("Spare", "53"))
        ima = _place(state, "P0", _get_card(repo, "HMW", "44"))
        return _defeat_and_fire(state, ima, "P0"), spare

    def test_HMW_44_behind_on_resources_ramps_two(self, repo):
        from swu.engine.actions import apply, legal_actions, SelectHandCardToResource
        state, spare = self._defeat(repo, 2, 4)
        state = _step_to(state, "resource_from_hand")
        state = apply(state, SelectHandCardToResource(spare.instance_id))
        while state.pending_decisions:
            state = apply(state, legal_actions(state)[0])
        res = state.player_by_id("P0").resources
        assert len(res) == 4
        assert all(r.exhausted for r in res[-2:])

    def test_HMW_44_no_ramp_when_not_behind(self, repo):
        state, _ = self._defeat(repo, 4, 4)
        state = _drive(state, _accept_and_target())
        assert len(state.player_by_id("P0").resources) == 4


class TestLowAltitudeCombatHMW_50:

    def test_HMW_50_moves_a_space_unit_then_offers_a_ground_attack(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        flyer = _place(state, "P1", _unit_def("Flyer", "51"), arena="space")
        mine = _place(state, "P0", _unit_def("Mine", "52", power=2))
        state, _ = _play_event_from_hand(state, repo, "HMW", "50")
        state = _step_to(state, "granted_attack", _accept_and_target(flyer.instance_id))
        p1 = state.player_by_id("P1")
        assert flyer.instance_id in {u.instance_id for u in p1.ground_arena}
        assert not p1.space_arena
        opts = {(a.attacker_id, a.defender_id) for a in legal_actions(state)
                if isinstance(a, AttackWithUnit)}
        assert (mine.instance_id, flyer.instance_id) in opts
        state = _granted_attack(state, mine.instance_id, flyer.instance_id)
        state = _drive(state)
        assert flyer.instance_id in {c.instance_id for c in  # 4 damage ≥ 3 HP
                                     state.player_by_id("P1").discard}

    def test_HMW_50_no_space_unit_no_attack(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        _place(state, "P0", _unit_def("Mine", "52"))
        state, _ = _play_event_from_hand(state, repo, "HMW", "50")
        state = _drive(state)
        assert not state.pending_decisions
        assert _base(state, "P1").damage == 0


def test_HMW_52_a_koba_gives_plus_2_for_the_phase(repo):
    from swu.engine.actions import compute_power
    state = _make_state()
    akoba = _place(state, "P0", _get_card(repo, "HMW", "52"))
    ally = _place(state, "P0", _unit_def("Ally", "51", power=2))
    state = _drive(_fire_when_played(state, akoba), _accept_and_target(ally.instance_id))
    assert compute_power(state, state.find_instance(ally.instance_id)[1]) == 4


class TestYodaHMW_56:

    def test_HMW_56_returns_to_deck_top_and_heals(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        state = _make_state()
        _deck(state, "P0")
        yoda = _place(state, "P0", _get_card(repo, "HMW", "56"))
        _base(state, "P0").damage = 5
        state = _defeat_and_fire(state, yoda, "P0")
        state = _drive(state, _accept_and_target(_base(state, "P0").instance_id))
        ps = state.player_by_id("P0")
        assert ps.deck[0].instance_id == yoda.instance_id
        assert yoda.instance_id not in {c.instance_id for c in ps.discard}
        assert _base(state, "P0").damage == 3


class TestRhoMedicalShuttleHMW_63:

    def test_HMW_63_when_played_heals_another_unit(self, repo):
        state = _make_state()
        rho = _place(state, "P0", _get_card(repo, "HMW", "63"))
        rho.damage = 1
        hurt = _place(state, "P0", _unit_def("Hurt", "51", hp=5))
        hurt.damage = 2
        state = _fire_when_played(state, rho)
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _drive(state, lambda s, acts: next(
            (a for a in acts if type(a).__name__ == "AcceptTrigger"), None))
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert rho.instance_id not in offered
        state = _drive(state, _accept_and_target(hurt.instance_id))
        assert state.find_instance(hurt.instance_id)[1].damage == 1

    def test_HMW_63_on_attack_heals_a_base(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        rho = _place(state, "P0", _get_card(repo, "HMW", "63"))
        _base(state, "P0").damage = 3
        state = _drive(_fire_on_attack(state, rho),
                       _accept_and_target(_base(state, "P0").instance_id))
        assert _base(state, "P0").damage == 2


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:13 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def test_HMW_66_carrion_spike_scales_with_base_upgrades(repo):
    from swu.engine.actions import compute_power
    from swu.engine.keywords import Keyword, has_keyword, keyword_value
    state = _make_state()
    spike = _place(state, "P0", _get_card(repo, "HMW", "66"), arena="space")
    assert compute_power(state, spike) == 3
    assert keyword_value(state, spike, Keyword.RESTORE) == 0
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "37"))
    _attach_to_base(state, "P0", _get_card(repo, "HMW", "95"))
    _attach_to_base(state, "P1", _get_card(repo, "HMW", "70"))   # enemy base: no
    assert compute_power(state, spike) == 5
    assert keyword_value(state, spike, Keyword.RESTORE) == 2
    assert has_keyword(state, spike, Keyword.SHIELDED)


def test_HMW_72_grand_army_marine_shields_a_friendly_gungan(repo):
    from swu.engine.actions import legal_actions, ChooseTarget
    state = _make_state()
    marine = _place(state, "P0", _get_card(repo, "HMW", "72"))
    _place(state, "P0", _unit_def("Trooper", "51"))
    state = _fire_when_played(state, marine)
    offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
    assert offered <= {marine.instance_id}
    state = _drive(state, _accept_and_target(marine.instance_id))
    unit = state.find_instance(marine.instance_id)[1]
    assert any(u.card_def.name == "Shield" for u in unit.attached_upgrades)


def test_HMW_73_peppi_bow_gets_plus_1_plus_1_while_upgraded(repo):
    from swu.engine.actions import compute_power, compute_hp
    from swu.engine.tokens import attach_token
    state = _make_state()
    peppi = _place(state, "P0", _get_card(repo, "HMW", "73"))
    assert (compute_power(state, peppi), compute_hp(state, peppi)) == (2, 3)
    attach_token(state, state.player_by_id("P0"), peppi, "Shield")
    assert (compute_power(state, peppi), compute_hp(state, peppi)) == (3, 4)


def test_HMW_74_yord_fandar_sentinel_at_15_base_damage(repo):
    from swu.engine.keywords import Keyword, has_keyword
    state = _make_state()
    yord = _place(state, "P0", _get_card(repo, "HMW", "74"))
    assert not has_keyword(state, yord, Keyword.SENTINEL)
    _base(state, "P1").damage = 15                   # EITHER base counts
    assert has_keyword(state, yord, Keyword.SENTINEL)


def test_HMW_80_fambaa_shields_each_unshielded_friendly_ground_unit(repo):
    from swu.engine.tokens import attach_token
    state = _make_state()
    fambaa = _place(state, "P0", _get_card(repo, "HMW", "80"))
    bare = _place(state, "P0", _unit_def("Bare", "51"))
    shielded = _place(state, "P0", _unit_def("Shielded", "52"))
    attach_token(state, state.player_by_id("P0"), shielded, "Shield")
    flyer = _place(state, "P0", _unit_def("Flyer", "53"), arena="space")
    foe = _place(state, "P1", _unit_def("Foe", "54"))
    state = _drive(_fire_when_played(state, fambaa))

    def shields(ci):
        unit = state.find_instance(ci.instance_id)[1]
        return sum(1 for u in unit.attached_upgrades if u.card_def.name == "Shield")
    assert (shields(fambaa), shields(bare), shields(shielded),
            shields(flyer), shields(foe)) == (1, 1, 1, 0, 0)


def test_HMW_83_batcher_gets_plus_1_while_defending(repo):
    from swu.engine.actions import apply, AttackWithUnit
    state = _make_state()
    batcher = _place(state, "P0", _get_card(repo, "HMW", "83"))
    foe = _place(state, "P1", _unit_def("Foe", "51", power=1, hp=9))
    state.active_player_index = 1
    state = _drive(apply(state, AttackWithUnit(foe.instance_id, batcher.instance_id)))
    assert state.find_instance(foe.instance_id)[1].damage == 3   # 2 + 1


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:14–20 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════

_TATOOINE = "19"


def _hmw(repo, number):
    return _get_card(repo, "HMW", number)


def _pip(name):
    from swu.cards.models import AspectPip
    return AspectPip(position=0, name=name, color="White", is_duplicate=False)


def _unit(name="Trooper", number="50", power=2, hp=3, **kw):
    return dataclasses.replace(_unit_def(name, number, power=power, hp=hp), **kw)


def _play_from_hand(state, card_def, owner="P0", host=None, picker=None, resources=12):
    """A real ``PlayCard`` from hand (resources supplied), then drive decisions."""
    from swu.engine.actions import apply, PlayCard
    ci = _to_hand(state, owner, card_def)
    _give_resources(state, owner, resources)
    state.active_player_index = state.player_index(owner)
    state = apply(state, PlayCard(ci.instance_id, host.instance_id if host else None))
    return _drive(state, picker), ci


def _live(state, ci):
    return state.find_instance(ci.instance_id)[1]


def _power(state, ci):
    from swu.engine.actions import compute_power
    return compute_power(state, _live(state, ci))


def _kw(state, ci, name):
    from swu.engine.keywords import has_keyword, Keyword
    return has_keyword(state, _live(state, ci), Keyword[name.upper()])


def _attach(state, host, card_def):
    from swu.engine.state import CardInstance
    import uuid
    up = CardInstance(instance_id=f"{host.owner_id}_u_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=host.owner_id, zone=host.zone)
    host.attached_upgrades.append(up)
    return up


def _picker_attack(attacker_id, defender_id=None):
    """Pick ``AttackWithUnit(attacker, defender)`` when offered, else default."""
    from swu.engine.actions import AttackWithUnit

    def _pick(state, acts):
        for a in acts:
            if (isinstance(a, AttackWithUnit) and a.attacker_id == attacker_id
                    and a.defender_id == defender_id):
                return a
        return _accept_and_target()(state, acts)
    return _pick


# ── hmw-set:14 ────────────────────────────────────────────────────────────────


def test_HMW_91_pelta_heals_base_and_a_friendly_unit(repo):
    state = _make_state()
    _base(state, "P0").damage = 5
    hurt = _place(state, "P0", _unit(hp=6))
    hurt.damage = 3
    state, _ = _play_from_hand(state, _hmw(repo, "91"), picker=_accept_and_target(hurt.instance_id))
    assert _base(state, "P0").damage == 3
    assert _live(state, hurt).damage == 1


def test_HMW_92_purrgil_may_exhaust_a_unit(repo):
    state = _make_state()
    foe = _place(state, "P1", _unit("Foe", "51"))
    state, _ = _play_from_hand(state, _hmw(repo, "92"), picker=_accept_and_target(foe.instance_id))
    assert _live(state, foe).exhausted


class TestResonateHMW_98:

    def _setup(self, repo, unit_def):
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "HMW", "9"))  # Chewbacca: Wookiee
        _place(state, "P0", unit_def)
        _base(state, "P0").damage = 6
        return state

    def test_HMW_98_heals_4_when_a_unit_shares_a_leader_trait(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = self._setup(repo, _hmw(repo, "133"))  # Wroshyr Rebel: Wookiee
        state, _ = _play_event_from_hand(state, repo, "HMW", "98")
        state = _drive(state, _accept_and_target(_base(state, "P0").instance_id))
        assert _base(state, "P0").damage == 2

    def test_HMW_98_fizzles_without_a_shared_trait(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = self._setup(repo, _unit())  # Trooper
        state, _ = _play_event_from_hand(state, repo, "HMW", "98")
        state = _drive(state)
        assert _base(state, "P0").damage == 6


class TestGarnacHMW_104:

    def test_HMW_104_hidden_only_while_opponent_has_a_unique_unit(self, repo):
        state = _make_state()
        garnac = _place(state, "P0", _hmw(repo, "104"))
        _place(state, "P1", _unit("Foe", "51"))
        assert not _kw(state, garnac, "Hidden")
        _place(state, "P1", _hmw(repo, "115"))  # Leia Organa, unique
        assert _kw(state, garnac, "Hidden")

    def test_HMW_104_attack_ends_offers_another_units_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        garnac = _place(state, "P0", _hmw(repo, "104"))
        garnac.exhausted = False
        buddy = _place(state, "P0", _unit("Buddy", "52"))
        buddy.exhausted = False
        state = apply(state, AttackWithUnit(garnac.instance_id, None))
        state = _to_decision(state, "granted_attack")
        assert state.pending_decisions[-1].kind == "granted_attack"
        offered = {a.attacker_id for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)}
        assert offered == {buddy.instance_id}


def test_HMW_107_patrol_gets_plus_2_with_another_3_cost_unit(repo):
    state = _make_state()
    patrol = _place(state, "P0", _hmw(repo, "107"))
    _place(state, "P0", _unit(cost=2))
    assert _power(state, patrol) == 2
    _place(state, "P0", _unit("Big", "53", cost=3))
    assert _power(state, patrol) == 4


def test_HMW_111_invasion_lander_buffs_each_other_friendly_unit(repo):
    from swu.engine.actions import compute_hp
    state = _make_state()
    a = _place(state, "P0", _unit(power=1, hp=1))
    foe = _place(state, "P1", _unit("Foe", "51", power=1, hp=1))
    state, lander = _play_from_hand(state, _hmw(repo, "111"))
    assert (_power(state, a), compute_hp(state, _live(state, a))) == (3, 3)
    assert _power(state, foe) == 1
    assert _power(state, lander) == 3   # not itself


# ── hmw-set:15 ────────────────────────────────────────────────────────────────


def test_HMW_115_leia_heals_base_when_a_cheap_unit_is_played(repo):
    state = _make_state()
    _place(state, "P0", _hmw(repo, "115"))
    _base(state, "P0").damage = 4
    state, _ = _play_from_hand(state, _unit("Big", "53", cost=4))
    assert _base(state, "P0").damage == 4
    state, _ = _play_from_hand(state, _unit(cost=3))
    assert _base(state, "P0").damage == 3


def test_HMW_117_chewbacca_raid_per_exhausted_resource_and_overwhelm(repo):
    from swu.engine.keywords import keyword_value, Keyword
    state = _make_state()
    chewie = _place(state, "P0", _hmw(repo, "117"))
    _give_resources(state, "P0", 3)
    res = state.player_by_id("P0").resources
    res[0].exhausted = res[1].exhausted = True
    assert keyword_value(state, chewie, Keyword.RAID) == 2
    assert not _kw(state, chewie, "Overwhelm")
    res[2].exhausted = True
    assert keyword_value(state, chewie, Keyword.RAID) == 3
    assert _kw(state, chewie, "Overwhelm")


def test_HMW_118_ryyk_gains_ambush_and_overwhelm_at_6_resources(repo):
    state = _make_state()
    ryyk = _place(state, "P0", _hmw(repo, "118"))
    _give_resources(state, "P0", 5)
    assert not _kw(state, ryyk, "Ambush") and not _kw(state, ryyk, "Overwhelm")
    _give_resources(state, "P0", 1)
    assert _kw(state, ryyk, "Ambush") and _kw(state, ryyk, "Overwhelm")


def test_HMW_119_saw_resources_when_an_opponent_plays_an_event(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    _place(state, "P1", _hmw(repo, "119"))
    _deck(state, "P1", 3)
    top = state.player_by_id("P1").deck[0].instance_id
    state, _ = _play_event_from_hand(state, repo, "HMW", "98")  # Resonate fizzles
    state = _drive(state)
    p1 = state.player_by_id("P1")
    assert [r.instance_id for r in p1.resources] == [top]
    assert p1.resources[0].exhausted


def test_HMW_121_hijacked_at_st_does_not_ready_next_regroup(repo):
    state = _make_state()
    state, atst = _play_from_hand(state, _hmw(repo, "121"))
    assert _live(state, atst).cannot_ready_this_round


def test_HMW_123_grakchawwaa_ramps_ready_per_other_wookiee(repo):
    state = _make_state()
    _place(state, "P0", _hmw(repo, "133"))   # Wookiee
    _place(state, "P0", _hmw(repo, "118"))   # Wookiee
    _place(state, "P0", _unit())             # not a Wookiee
    _deck(state, "P0", 5)
    deck_ids = {c.instance_id for c in state.player_by_id("P0").deck}
    state, _ = _play_from_hand(state, _hmw(repo, "123"))
    ramped = [r for r in state.player_by_id("P0").resources if r.instance_id in deck_ids]
    assert len(ramped) == 2 and not any(r.exhausted for r in ramped)


def test_HMW_124_luminara_offers_a_plus_2_attack_including_herself(repo):
    state = _make_state()
    from swu.engine.actions import apply, PlayCard
    ally = _place(state, "P0", _unit())
    ally.exhausted = False
    lum = _to_hand(state, "P0", _hmw(repo, "124"))
    _give_resources(state, "P0", 12)
    state = apply(state, PlayCard(lum.instance_id))
    state = _to_decision(state, "granted_attack")
    assert state.pending_decisions[-1].kind == "granted_attack"
    assert state.pending_decisions[-1].context["power_bonus"] == 2


# ── hmw-set:16 ────────────────────────────────────────────────────────────────


class TestBowcasterHMW_127:

    def _play(self, repo, host_def):
        state = _make_state()
        host = _place(state, "P0", host_def)
        _deck(state, "P0", 3)
        before = len(state.player_by_id("P0").deck)
        state, _ = _play_from_hand(state, _hmw(repo, "127"), host=host)
        return state, before

    def test_HMW_127_on_chewbacca_resources_the_top_card_exhausted(self, repo):
        state, before = self._play(repo, _hmw(repo, "117"))
        ps = state.player_by_id("P0")
        assert len(ps.deck) == before - 1
        assert ps.resources[-1].exhausted and ps.resources[-1].instance_id.startswith("P0_d")

    def test_HMW_127_on_anyone_else_does_nothing(self, repo):
        state, before = self._play(repo, _unit())
        assert len(state.player_by_id("P0").deck) == before


def test_HMW_129_child_of_dathomir_plus_2_with_3_units(repo):
    state = _make_state()
    child = _place(state, "P0", _hmw(repo, "129"))
    _place(state, "P0", _unit())
    assert _power(state, child) == 1
    _place(state, "P0", _unit("B", "52"))
    assert _power(state, child) == 3


def test_HMW_131_can_cell_ambush_with_kashyyyk_base(repo):
    state = _make_state()
    cell = _place(state, "P0", _hmw(repo, "131"))
    assert not _kw(state, cell, "Ambush")
    _set_base(state, repo, "P0", _KASHYYYK)
    assert _kw(state, cell, "Ambush")


def test_HMW_133_wroshyr_rebel_plus_1_per_2_resources(repo):
    state = _make_state()
    rebel = _place(state, "P0", _hmw(repo, "133"))
    _give_resources(state, "P0", 5)
    assert _power(state, rebel) == 2


class TestLifetreeCaravanHMW_136:

    def test_HMW_136_may_resource_with_3_units(self, repo):
        state = _make_state()
        _place(state, "P0", _unit())
        _place(state, "P0", _unit("B", "52"))
        _deck(state, "P0", 3)
        before = len(state.player_by_id("P0").deck)
        state, _ = _play_from_hand(state, _hmw(repo, "136"), picker=_accept_and_target())
        assert len(state.player_by_id("P0").deck) == before - 1

    def test_HMW_136_not_offered_with_fewer_units(self, repo):
        state = _make_state()
        _place(state, "P0", _unit())
        _deck(state, "P0", 3)
        before = len(state.player_by_id("P0").deck)
        state, _ = _play_from_hand(state, _hmw(repo, "136"), picker=_accept_and_target())
        assert len(state.player_by_id("P0").deck) == before


def test_HMW_137_v19_sentinel_with_3_units(repo):
    state = _make_state()
    v19 = _place(state, "P0", _hmw(repo, "137"), arena="space")
    _place(state, "P0", _unit())
    assert not _kw(state, v19, "Sentinel")
    _place(state, "P0", _unit("B", "52"))
    assert _kw(state, v19, "Sentinel")


def test_HMW_138_gree_raid_4_with_3_command_icons_on_units_and_upgrades(repo):
    from swu.engine.keywords import keyword_value, Keyword
    state = _make_state()
    gree = _place(state, "P0", _hmw(repo, "138"))
    own = sum(1 for a in gree.card_def.aspects if a.name == "Command")
    assert own == 1 and keyword_value(state, gree, Keyword.RAID) == 0
    cmd_unit = _place(state, "P0", _unit(aspects=(_pip("Command"),)))
    assert keyword_value(state, gree, Keyword.RAID) == 0          # 2 icons
    _attach(state, cmd_unit, _unit("Gear", "54", aspects=(_pip("Command"),)))
    assert keyword_value(state, gree, Keyword.RAID) == 4          # 3rd on an upgrade


# ── hmw-set:17 ────────────────────────────────────────────────────────────────


def test_HMW_141_rex_buffs_friendly_units_with_no_abilities(repo):
    from swu.engine.actions import compute_hp
    state = _make_state()
    rex = _place(state, "P0", _hmw(repo, "141"))
    vanilla = _place(state, "P0", _unit(power=2, hp=3))
    texty = _place(state, "P0", _hmw(repo, "133"))   # 0/4 with text (no resources)
    foe = _place(state, "P1", _unit("Foe", "51", power=2, hp=3))
    assert (_power(state, vanilla), compute_hp(state, vanilla)) == (3, 4)
    assert (_power(state, texty), compute_hp(state, texty)) == (0, 4)
    assert _power(state, rex) == 5
    assert _power(state, foe) == 2


def test_HMW_142_rangers_sentinel_with_another_wookiee_or_kashyyyk(repo):
    state = _make_state()
    rangers = _place(state, "P0", _hmw(repo, "142"))
    assert not _kw(state, rangers, "Sentinel")
    _set_base(state, repo, "P0", _KASHYYYK)
    assert _kw(state, rangers, "Sentinel")
    state2 = _make_state()
    r2 = _place(state2, "P0", _hmw(repo, "142"))
    _place(state2, "P0", _hmw(repo, "133"))   # Wookiee
    assert _kw(state2, r2, "Sentinel")


def test_HMW_145_shyyyo_discounts_first_units_1_then_2(repo):
    from swu.engine.actions import _play_cost
    state = _make_state()
    _place(state, "P0", _hmw(repo, "145"))
    ps = state.player_by_id("P0")
    first = _to_hand(state, "P0", _unit(cost=5))
    second = _to_hand(state, "P0", _unit("B", "52", cost=5))
    full = _play_cost(state, second, ps)
    _set_base(state, repo, "P0", _KASHYYYK)
    assert _play_cost(state, first, ps) == full - 1
    from swu.engine.actions import apply, PlayCard
    _give_resources(state, "P0", 12)
    state = _drive(apply(state, PlayCard(first.instance_id)))
    ps = state.player_by_id("P0")
    assert _play_cost(state, _live(state, second), ps) == full - 2


def test_HMW_149_log_trap_attacks_twice_second_not_at_bases(repo):
    from swu.engine.actions import legal_actions, apply, AttackWithUnit
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    me = _place(state, "P0", _unit(power=3, hp=20))
    me.exhausted = False
    foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=20))
    state, _ = _play_event_from_hand(state, repo, "HMW", "149")
    state = _to_decision(state, "granted_attack")
    state = apply(state, AttackWithUnit(me.instance_id, foe.instance_id))
    state = _to_decision(state, "granted_attack")
    second = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
    assert second and {a.attacker_id for a in second} == {me.instance_id}
    assert all(a.defender_id is not None for a in second)   # no base attack
    state = _drive(apply(state, AttackWithUnit(me.instance_id, foe.instance_id)))
    assert _live(state, foe).damage == 6


class TestOvergrowthHMW_151:

    def _play(self, repo, kashyyyk):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        if kashyyyk:
            _set_base(state, repo, "P0", _KASHYYYK)
        shooter = _place(state, "P0", _unit(power=3, hp=5))
        foe = _place(state, "P1", _unit("Foe", "51", power=1, hp=9))
        state, evt = _play_event_from_hand(state, repo, "HMW", "151")
        return _drive(state, _accept_and_target()), shooter, foe, evt

    def test_HMW_151_unit_deals_its_power_and_event_is_resourced(self, repo):
        state, _, foe, evt = self._play(repo, kashyyyk=True)
        assert _live(state, foe).damage == 3
        res = [r for r in state.player_by_id("P0").resources
               if r.instance_id == evt.instance_id]
        assert res and res[0].exhausted

    def test_HMW_151_without_kashyyyk_only_resources(self, repo):
        state, _, foe, evt = self._play(repo, kashyyyk=False)
        assert _live(state, foe).damage == 0
        assert any(r.instance_id == evt.instance_id
                   for r in state.player_by_id("P0").resources)


def test_HMW_164_chirpa_plus_1_per_other_ewok(repo):
    state = _make_state()
    chirpa = _place(state, "P0", _hmw(repo, "164"))
    _place(state, "P0", _hmw(repo, "136"))   # Ewok
    _place(state, "P0", _hmw(repo, "176"))   # Ewok
    _place(state, "P0", _unit())
    assert _power(state, chirpa) == 3


def test_HMW_165_shuttle_readies_another_unit_with_3_or_less_power(repo):
    from swu.engine.actions import ChooseTarget
    state = _make_state()
    small = _place(state, "P0", _unit(power=3))
    big = _place(state, "P0", _unit("Big", "53", power=5))
    small.exhausted = big.exhausted = True
    seen = []

    def _pick(s, acts):
        seen.extend(a.target_id for a in acts if isinstance(a, ChooseTarget))
        return _accept_and_target(small.instance_id)(s, acts)
    state, _ = _play_from_hand(state, _hmw(repo, "165"), picker=_pick)
    assert not _live(state, small).exhausted
    assert big.instance_id not in seen


# ── hmw-set:18 ────────────────────────────────────────────────────────────────


def test_HMW_170_han_readies_another_unit_only_when_one_is_exhausted(repo):
    state = _make_state()
    han = _place(state, "P0", _hmw(repo, "170"))
    han.exhausted = False
    tired = _place(state, "P0", _unit())
    tired.exhausted = False
    assert not _offers_ability(state, han.instance_id)
    tired.exhausted = True
    state = _drive(_use_ability(state, han.instance_id), _accept_and_target(tired.instance_id))
    assert not _live(state, tired).exhausted and _live(state, han).exhausted


def test_HMW_176_troublemaker_hidden_and_saboteur_with_endor(repo):
    state = _make_state()
    ewok = _place(state, "P0", _hmw(repo, "176"))
    assert not _kw(state, ewok, "Hidden") and not _kw(state, ewok, "Saboteur")
    _set_base(state, repo, "P0", _ENDOR)
    assert _kw(state, ewok, "Hidden") and _kw(state, ewok, "Saboteur")


def test_HMW_184_aggrocrab_costs_1_less_with_initiative(repo):
    from swu.engine.actions import _play_cost
    state = _make_state()
    ps = state.player_by_id("P0")
    crab = _to_hand(state, "P0", _hmw(repo, "184"))
    state.initiative_holder = 1
    without = _play_cost(state, crab, ps)
    state.initiative_holder = 0
    assert _play_cost(state, crab, ps) == without - 1


def test_HMW_190_enraged_grants_raid_2(repo):
    from swu.engine.keywords import keyword_value, Keyword
    state = _make_state()
    host = _place(state, "P0", _unit())
    _attach(state, host, _hmw(repo, "190"))
    assert keyword_value(state, host, Keyword.RAID) == 2


def test_HMW_191_hunters_instinct_grit_only_on_a_creature(repo):
    state = _make_state()
    beast = _place(state, "P0", _hmw(repo, "92"))   # Creature
    trooper = _place(state, "P0", _unit())
    _attach(state, beast, _hmw(repo, "191"))
    _attach(state, trooper, _hmw(repo, "191"))
    assert _kw(state, beast, "Grit") and not _kw(state, trooper, "Grit")


def test_HMW_203_victor_squadron_enters_ready(repo):
    state = _make_state()
    state, ci = _play_from_hand(state, _hmw(repo, "203"))
    assert not _live(state, ci).exhausted


def test_HMW_208_luke_enters_ready_only_in_the_first_round(repo):
    state = _make_state()
    state.round_number = 1
    s1, luke = _play_from_hand(state, _hmw(repo, "208"))
    assert not _live(s1, luke).exhausted
    state = _make_state()
    state.round_number = 2
    s2, luke2 = _play_from_hand(state, _hmw(repo, "208"))
    assert _live(s2, luke2).exhausted


# ── hmw-set:19 ────────────────────────────────────────────────────────────────


def test_HMW_209_corona_x_wing_readies_a_resource_on_attack(repo):
    state = _make_state()
    xw = _place(state, "P0", _hmw(repo, "209"), arena="space")
    _give_resources(state, "P0", 2)
    for r in state.player_by_id("P0").resources:
        r.exhausted = True
    state = _attack(state, xw, picker=_accept_and_target())
    assert sum(1 for r in state.player_by_id("P0").resources if not r.exhausted) == 1


def test_HMW_210_sol_gains_sentinel_when_attacking(repo):
    state = _make_state()
    sol = _place(state, "P0", _hmw(repo, "210"))
    assert not _kw(state, sol, "Sentinel")
    state = _attack(state, sol, picker=_accept_and_target())
    assert _kw(state, sol, "Sentinel")


class TestChieftainHMW_212:

    def test_HMW_212_raid_1_per_other_friendly_tusken(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        chief = _place(state, "P0", _hmw(repo, "212"))
        _place(state, "P0", _hmw(repo, "230"))
        _place(state, "P0", _hmw(repo, "230"))
        assert keyword_value(state, chief, Keyword.RAID) == 2

    def test_HMW_212_defending_tusken_gets_its_raid_as_power(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        _place(state, "P0", _hmw(repo, "212"))
        party = _place(state, "P0", _hmw(repo, "230"))   # 0/6, Raid 6
        foe = _place(state, "P1", _unit("Foe", "51", power=1, hp=20))
        state.active_player_index = 1
        state = _drive(apply(state, AttackWithUnit(foe.instance_id, party.instance_id)))
        assert _live(state, foe).damage == 6


class TestPheeGenoaHMW_214:

    def _deploy(self, repo):
        from swu.engine.actions import apply, DeployLeader
        state = _make_state()
        _place(state, "P1", _hmw(repo, "214"))
        leader = _place_leader(state, "P0", _get_leader(repo, "HMW", "9"))
        _give_resources(state, "P0", 8)
        state.active_player_index = 0
        state = apply(state, DeployLeader())
        return state, leader

    def test_HMW_214_unpaid_deploy_exhausts_the_leader(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptExhaust
        state, leader = self._deploy(repo)
        state = _to_decision(state, "pay_or_exhaust")
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptExhaust)))
        assert _live(state, leader).exhausted

    def test_HMW_214_paying_2_keeps_it_ready(self, repo):
        from swu.engine.actions import legal_actions, apply, PayToAvoidExhaust
        state, leader = self._deploy(repo)
        state = _to_decision(state, "pay_or_exhaust")
        ready_before = state.player_by_id("P0").available_resources
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PayToAvoidExhaust)))
        assert not _live(state, leader).exhausted
        assert state.player_by_id("P0").available_resources == ready_before - 2


def test_HMW_228_lakeside_shaaks_readies_a_resource(repo):
    state = _make_state()
    _give_resources(state, "P0", 1)
    state.player_by_id("P0").resources[0].exhausted = True
    shaaks = _place(state, "P0", _hmw(repo, "228"))
    state = _drive(_fire_when_played(state, shaaks))
    assert not state.player_by_id("P0").resources[0].exhausted


class TestRaidingPartyHMW_230:

    def test_HMW_230_with_tatooine_may_exhaust_a_ground_unit(self, repo):
        state = _make_state()
        _set_base(state, repo, "P0", _TATOOINE)
        foe = _place(state, "P1", _unit("Foe", "51"))
        state, _ = _play_from_hand(state, _hmw(repo, "230"),
                                   picker=_accept_and_target(foe.instance_id))
        assert _live(state, foe).exhausted

    def test_HMW_230_without_tusken_or_tatooine_is_not_offered(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "51"))
        state, _ = _play_from_hand(state, _hmw(repo, "230"),
                                   picker=_accept_and_target(foe.instance_id))
        assert not _live(state, foe).exhausted


# ── hmw-set:20 ────────────────────────────────────────────────────────────────


def test_HMW_234_ritual_dragon_friendly_units_enter_ready_with_tatooine(repo):
    state = _make_state()
    _set_base(state, repo, "P0", _TATOOINE)
    state, dragon = _play_from_hand(state, _hmw(repo, "234"), resources=12)
    assert not _live(state, dragon).exhausted          # including this one
    state, grunt = _play_from_hand(state, _unit())
    assert not _live(state, grunt).exhausted
    state, foe = _play_from_hand(state, _unit("Foe", "51"), owner="P1")
    assert _live(state, foe).exhausted                 # friendly units only


def test_HMW_255_c3po_buffs_an_ewok_and_a_rebel(repo):
    from swu.engine.actions import compute_hp
    state = _make_state()
    ewok = _place(state, "P0", _hmw(repo, "136"))     # Ewok 2/1
    rebel = _place(state, "P0", _hmw(repo, "133"))    # Rebel/Wookiee 0/4

    def _pick(s, acts):
        from swu.engine.actions import ChooseTarget
        ids = {a.target_id for a in acts if isinstance(a, ChooseTarget)}
        for want in (ewok.instance_id, rebel.instance_id):
            if want in ids and _power(s, ewok if want == ewok.instance_id else rebel) < 3:
                return next(a for a in acts if isinstance(a, ChooseTarget)
                            and a.target_id == want)
        return _accept_and_target()(s, acts)
    state, _ = _play_from_hand(state, _hmw(repo, "255"), picker=_pick)
    assert compute_hp(state, _live(state, ewok)) == 3
    assert compute_hp(state, _live(state, rebel)) == 6


def test_HMW_256_jedi_interceptor_plus_2_at_6_resources(repo):
    state = _make_state()
    jet = _place(state, "P0", _hmw(repo, "256"), arena="space")
    _give_resources(state, "P0", 5)
    assert _power(state, jet) == 2
    _give_resources(state, "P0", 1)
    assert _power(state, jet) == 4


def test_HMW_257_ewok_archers_ambush_with_another_cheap_unit(repo):
    state = _make_state()
    archers = _place(state, "P0", _hmw(repo, "257"))
    _place(state, "P0", _unit("Big", "53", cost=4))
    assert not _kw(state, archers, "Ambush")
    _place(state, "P0", _unit(cost=3))
    assert _kw(state, archers, "Ambush")


def test_HMW_259_pack_guardian_sentinel_while_ready(repo):
    state = _make_state()
    guard = _place(state, "P0", _hmw(repo, "259"))
    guard.exhausted = False
    assert _kw(state, guard, "Sentinel")
    guard.exhausted = True
    assert not _kw(state, guard, "Sentinel")


class TestBenKenobiHMW_261:

    def test_HMW_261_when_played_exhausts_a_unit_with_3_or_less_power(self, repo):
        from swu.engine.actions import ChooseTarget
        state = _make_state()
        small = _place(state, "P1", _unit("Foe", "51", power=3))
        big = _place(state, "P1", _unit("Big", "53", power=4))
        seen = []

        def _pick(s, acts):
            seen.extend(a.target_id for a in acts if isinstance(a, ChooseTarget))
            return _accept_and_target(small.instance_id)(s, acts)
        state, _ = _play_from_hand(state, _hmw(repo, "261"), picker=_pick)
        assert _live(state, small).exhausted and big.instance_id not in seen

    def test_HMW_261_on_attack_heals_another_unit(self, repo):
        state = _make_state()
        ben = _place(state, "P0", _hmw(repo, "261"))
        hurt = _place(state, "P0", _unit(hp=9))
        hurt.damage = 4
        state = _attack(state, ben, picker=_accept_and_target(hurt.instance_id))
        assert _live(state, hurt).damage == 1


class TestHeroicBraveryHMW_264:

    def test_HMW_264_shields_a_heroism_host(self, repo):
        from swu.cards.models import TokenUpgrade
        state = _make_state()
        hero = _place(state, "P0", _unit(aspects=(_pip("Heroism"),)))
        state, _ = _play_from_hand(state, _hmw(repo, "264"), host=hero)
        assert any(isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Shield"
                   for u in _live(state, hero).attached_upgrades)

    def test_HMW_264_no_shield_on_a_non_heroism_host(self, repo):
        from swu.cards.models import TokenUpgrade
        state = _make_state()
        plain = _place(state, "P0", _unit())
        state, _ = _play_from_hand(state, _hmw(repo, "264"), host=plain)
        assert not any(isinstance(u.card_def, TokenUpgrade)
                       for u in _live(state, plain).attached_upgrades)


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:21–24 — the last combat tricks + miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


def _pick_kind(cls_name, **fields):
    """Picker: the first legal action of class ``cls_name`` whose fields match,
    else accept/first-target, else the engine default."""
    def _pick(state, acts):
        for a in acts:
            if type(a).__name__ == cls_name and all(
                    getattr(a, k, None) == v for k, v in fields.items()):
                return a
        return _accept_and_target()(state, acts)
    return _pick


def _token_names(state, ci):
    from swu.cards.models import TokenUpgrade
    return [u.card_def.name for u in _live(state, ci).attached_upgrades
            if isinstance(u.card_def, TokenUpgrade)]


# ── hmw-set:21 ────────────────────────────────────────────────────────────────


class TestFamiliarStrategemHMW_266:

    def _attack_base(self, repo, buddy_traits):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        me = _place(state, "P0", _unit(power=2))
        me.exhausted = False
        _place(state, "P0", _unit("Buddy", "52", traits=buddy_traits))
        state, _ = _play_event_from_hand(state, repo, "HMW", "266")
        state = _drive(state, _pick_kind("AttackWithUnit", attacker_id=me.instance_id,
                                         defender_id=None))
        return _base(state, "P1").damage

    def test_HMW_266_plus_2_when_it_shares_a_trait(self, repo):
        assert self._attack_base(repo, ("Trooper",)) == 4

    def test_HMW_266_no_bonus_without_a_shared_trait(self, repo):
        assert self._attack_base(repo, ("Droid",)) == 2


def test_HMW_267_renew_defeats_a_condition_upgrade_and_heals_base(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    foe = _place(state, "P1", _unit("Foe", "51"))
    cond = _attach(state, foe, dataclasses.replace(_hmw(repo, "190"), traits=("Condition",)))
    _base(state, "P0").damage = 5
    state, _ = _play_event_from_hand(state, repo, "HMW", "267")
    state = _drive(state, _accept_and_target(cond.instance_id))
    assert not _live(state, foe).attached_upgrades
    assert _base(state, "P0").damage == 2


# ── hmw-set:22 ────────────────────────────────────────────────────────────────


class TestTheWarriorHMW_18:

    def test_HMW_18_plays_a_low_power_unit_with_ambush(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        warrior = _place_leader(state, "P0", _get_leader(repo, "HMW", "18"))
        small = _to_hand(state, "P0", _unit(power=2, cost=2))
        big = _to_hand(state, "P0", _unit("Big", "53", power=5, cost=2))
        _give_resources(state, "P0", 3)
        state = _use_ability(state, warrior.instance_id)
        state = _to_decision(state, "play_from_hand")
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert offered == {small.instance_id} and big.instance_id not in offered
        state = _drive(state, _pick_kind("PlayFromHand", instance_id=small.instance_id))
        assert _kw(state, small, "Ambush")

    def test_HMW_18_not_offered_when_the_unit_is_unaffordable_after_its_cost(self, repo):
        state = _make_state()
        warrior = _place_leader(state, "P0", _get_leader(repo, "HMW", "18"))
        _to_hand(state, "P0", _unit(power=2, cost=2))
        _give_resources(state, "P0", 2)   # 1 for the Action leaves 1 < 2
        assert not _offers_ability(state, warrior.instance_id)


def test_HMW_53_fetts_firespray_lets_ambush_hit_a_base(repo):
    from swu.engine.actions import apply, PlayCard
    state = _make_state()
    fs = _to_hand(state, "P0", _hmw(repo, "53"))   # Ambush, 6/6
    _give_resources(state, "P0", 12)
    state = apply(state, PlayCard(fs.instance_id))
    state = _to_decision(state, "ambush")
    assert state.pending_decisions and state.pending_decisions[-1].kind == "ambush"
    state = _drive(state, _pick_kind("UseAmbush",
                                     target_id=_base(state, "P1").instance_id))
    assert _base(state, "P1").damage == 6


def test_HMW_57_boss_lyonie_copies_a_token_on_another_unit(repo):
    from swu.engine import tokens
    state = _make_state()
    ally = _place(state, "P0", _unit())
    tokens.attach_token(state, state.player_by_id("P0"), ally, "Experience")
    state, _ = _play_from_hand(state, _hmw(repo, "57"),
                               picker=_accept_and_target(ally.instance_id))
    assert _token_names(state, ally).count("Experience") == 2


def test_HMW_88_numa_prevents_1_of_each_damage(repo):
    from swu.engine.actions import apply, AttackWithUnit
    state = _make_state()
    numa = _place(state, "P0", _hmw(repo, "88"))
    foe = _place(state, "P1", _unit("Foe", "51", power=3, hp=20))
    state.active_player_index = 1
    state = _drive(apply(state, AttackWithUnit(foe.instance_id, numa.instance_id)))
    assert _live(state, numa).damage == 2


def test_HMW_105_nute_deals_1_to_a_different_enemy_unit_per_friendly_unit(repo):
    state = _make_state()
    _place(state, "P0", _unit())
    foes = [_place(state, "P1", _unit("Foe", str(80 + i), hp=5)) for i in range(3)]

    def _pick(s, acts):
        chosen = set(s.pending_decisions[-1].context.get("chosen", [])) \
            if s.pending_decisions else set()
        for a in acts:
            if type(a).__name__ == "SelectDamageTarget" and a.target_id not in chosen:
                return a
        return _accept_and_target()(s, acts)
    state, _ = _play_from_hand(state, _hmw(repo, "105"), picker=_pick)
    # Nute + 1 other friendly unit = 2 hits on 2 different enemy units
    assert sorted(_live(state, f).damage for f in foes) == [0, 1, 1]


def test_HMW_108_first_legion_strips_a_named_trait_from_enemy_cards(repo):
    from swu.engine.traits import has_trait
    state = _make_state()
    legion = _place(state, "P0", _hmw(repo, "108"))
    mine = _place(state, "P0", _unit("Mine", "52"))   # Trooper, friendly
    foe = _place(state, "P1", _unit("Foe", "51"))     # Trooper
    in_hand = _to_hand(state, "P1", _unit("Held", "54"))
    state = _attack(state, legion, picker=_pick_kind("NameCard", name="Trooper"))
    assert not has_trait(state, _live(state, foe), "Trooper")
    assert not has_trait(state, _live(state, in_hand), "Trooper")
    assert has_trait(state, _live(state, mine), "Trooper")
    assert _live(state, legion).named_card is None   # not a Galen-style card name


def test_HMW_134_zam_gains_leader_traits_except_force_in_any_zone(repo):
    from swu.engine.traits import has_trait
    state = _make_state()
    _place_leader(state, "P0", _get_leader(repo, "HMW", "9"))   # Chewbacca
    zam = _place(state, "P0", _hmw(repo, "134"))
    held = _to_hand(state, "P0", _hmw(repo, "134"))
    assert has_trait(state, zam, "Wookiee") and has_trait(state, held, "Wookiee")
    state2 = _make_state()
    leader = _place_leader(state2, "P0", _get_leader(repo, "HMW", "17"))   # Osha
    zam2 = _place(state2, "P0", _hmw(repo, "134"))
    assert "Force" in leader.card_def.traits
    assert not has_trait(state2, zam2, "Force")


# ── hmw-set:23 ────────────────────────────────────────────────────────────────


class TestDookusSolarSailerHMW_154:

    def _play(self, repo, cheap):
        state = _make_state()
        if cheap:
            _place(state, "P0", _unit(cost=1))
        for i in range(2):
            _to_hand(state, "P1", _unit("H", str(80 + i)))
        state, _ = _play_from_hand(state, _hmw(repo, "154"))
        return len(state.player_by_id("P1").hand)

    def test_HMW_154_opponent_discards_with_a_1_cost_unit(self, repo):
        assert self._play(repo, cheap=True) == 1

    def test_HMW_154_nothing_without_one(self, repo):
        assert self._play(repo, cheap=False) == 2


def test_HMW_161_raze_to_ruin_each_player_keeps_3(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    for i in range(5):
        _to_hand(state, "P0", _unit("A", str(80 + i)))
    for i in range(4):
        _to_hand(state, "P1", _unit("B", str(85 + i)))
    state, _ = _play_event_from_hand(state, repo, "HMW", "161")
    state = _drive(state)
    assert [len(p.hand) for p in state.players] == [3, 3]


def test_HMW_162_teebo_grants_hidden_to_other_friendly_ewoks(repo):
    state = _make_state()
    _place(state, "P0", _hmw(repo, "162"))
    ewok = _place(state, "P0", _hmw(repo, "136"))
    trooper = _place(state, "P0", _unit())
    enemy_ewok = _place(state, "P1", _hmw(repo, "136"))
    assert _kw(state, ewok, "Hidden")
    assert not _kw(state, trooper, "Hidden") and not _kw(state, enemy_ewok, "Hidden")


def test_HMW_192_volley_fire_deals_the_units_raid(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    party = _place(state, "P0", _hmw(repo, "230"))   # Raid 6
    _place(state, "P0", _unit())                     # no Raid: not a shooter
    foe = _place(state, "P1", _unit("Foe", "51", hp=9))
    state, _ = _play_event_from_hand(state, repo, "HMW", "192")
    state = _drive(state, _accept_and_target())
    assert _live(state, foe).damage == 6 and _live(state, party).damage == 0


def test_HMW_218_new_tactics_owner_puts_unit_on_their_deck(repo):
    from tests.test_sor_cards import _play_event_from_hand
    state = _make_state()
    foe = _place(state, "P1", _unit("Foe", "51"))
    state, _ = _play_event_from_hand(state, repo, "HMW", "218")
    state = _to_decision(state, "put_on_deck") if state.pending_decisions else state
    state = _drive(state, _pick_kind("PutOnDeckBottom"))
    p1 = state.player_by_id("P1")
    assert not p1.ground_arena and p1.deck[-1].instance_id == foe.instance_id


def test_HMW_221_teeka_can_make_a_unit_lose_sentinel(repo):
    state = _make_state()
    patrol = _place(state, "P1", _hmw(repo, "107"))   # Sentinel
    assert _kw(state, patrol, "Sentinel")
    state, _ = _play_from_hand(state, _hmw(repo, "221"),
                               picker=_pick_kind("SelectModalOption", option_idx=2))
    assert not _kw(state, patrol, "Sentinel")


def test_HMW_223_therm_shrinks_per_revealed_card_costing_3_or_more(repo):
    from swu.engine.actions import compute_hp
    state = _make_state()
    therm = _place(state, "P0", _hmw(repo, "223"))
    _deck(state, "P0", 1)
    _deck(state, "P1", 1)
    state.player_by_id("P0").deck[0].card_def = _unit(cost=5)
    state.player_by_id("P1").deck[0].card_def = _unit(cost=1)
    state = _drive(_fire_phase(state, "action"))
    assert (_power(state, therm), compute_hp(state, _live(state, therm))) == (3, 3)


# ── hmw-set:24 ────────────────────────────────────────────────────────────────


def test_HMW_225_boba_arms_an_entering_ambush_unit(repo):
    from swu.engine.actions import apply, PlayCard
    from swu.engine.keywords import keyword_value, Keyword
    state = _make_state()
    _place(state, "P0", _hmw(repo, "225"))
    _place(state, "P1", _unit("Foe", "51", hp=20))
    fs = _to_hand(state, "P0", _hmw(repo, "53"))   # Ambush
    _give_resources(state, "P0", 12)
    state = apply(state, PlayCard(fs.instance_id))
    state = _to_decision(state, "ambush")
    assert state.pending_decisions[-1].kind == "ambush"
    assert _kw(state, fs, "Saboteur")
    assert keyword_value(state, _live(state, fs), Keyword.RAID) == 1


def test_HMW_233_exogorth_debuffs_the_defender(repo):
    state = _make_state()
    exo = _place(state, "P0", _hmw(repo, "233"))
    foe = _place(state, "P1", _unit("Foe", "51", power=4, hp=20))
    state = _attack(state, exo, foe)
    assert _live(state, exo).damage == 1


def test_HMW_243_sun_fac_gives_grit(repo):
    state = _make_state()
    ally = _place(state, "P0", _unit())
    state, _ = _play_from_hand(state, _hmw(repo, "243"),
                               picker=_accept_and_target(ally.instance_id))
    assert _kw(state, ally, "Grit")


def test_HMW_246_pyke_sarisa_gives_sentinel(repo):
    state = _make_state()
    ally = _place(state, "P0", _unit())
    state, _ = _play_from_hand(state, _hmw(repo, "246"),
                               picker=_accept_and_target(ally.instance_id))
    assert _kw(state, ally, "Sentinel")


def test_HMW_251_blockade_ship_shrinks_enemy_ground_attackers(repo):
    from swu.engine.actions import apply, AttackWithUnit
    state = _make_state()
    _place(state, "P0", _hmw(repo, "251"), arena="space")
    foe = _place(state, "P1", _unit("Foe", "51", power=3))
    foe.exhausted = False
    assert _power(state, foe) == 3          # not attacking: no debuff
    state.active_player_index = 1
    state = _drive(apply(state, AttackWithUnit(foe.instance_id, None)))
    assert _base(state, "P0").damage == 2


def test_HMW_260_queen_amidala_costs_2_less_with_an_upgraded_base(repo):
    from swu.engine.actions import _play_cost
    state = _make_state()
    ps = state.player_by_id("P0")
    queen = _to_hand(state, "P0", _hmw(repo, "260"))
    before = _play_cost(state, queen, ps)
    _attach_to_base(state, "P0", _hmw(repo, "37"))
    assert _play_cost(state, queen, ps) == before - 2


def test_HMW_265_kalikori_plays_twilek_units_from_the_deck(repo):
    state = _make_state()
    numa = _place(state, "P0", _hmw(repo, "88"))   # Twi'lek
    _deck(state, "P0", 4)
    deck = state.player_by_id("P0").deck
    deck[1].card_def = _unit("Lek", "55", cost=2, traits=("Twi'lek",))
    state, _ = _play_from_hand(state, _hmw(repo, "265"), host=numa,
                               picker=_accept_and_target())
    assert any(u.instance_id == deck[1].instance_id
               for u in state.player_by_id("P0").ground_arena)


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:25 — the first Weakness-token cards
# ══════════════════════════════════════════════════════════════════════════════


def _weak(state, ci):
    return _token_names(state, ci).count("Weakness")


class TestMazKanataHMW_2:

    def test_HMW_2_plays_an_underworld_unit_1_cheaper_with_a_weakness(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        maz = _place_leader(state, "P0", _get_leader(repo, "HMW", "2"))
        thug = _to_hand(state, "P0", _unit("Thug", "57", power=3, hp=3, cost=3,
                                           traits=("Underworld",)))
        trooper = _to_hand(state, "P0", _unit(cost=1))
        _give_resources(state, "P0", 2)          # 3 − 1 = 2: affordable only via Maz
        state = _to_decision(_use_ability(state, maz.instance_id), "play_from_hand")
        offered = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert offered == {thug.instance_id} and trooper.instance_id not in offered
        state = _drive(state, _pick_kind("PlayFromHand", instance_id=thug.instance_id))
        assert _weak(state, thug) == 1
        assert _power(state, thug) == 2

    def test_HMW_2_an_attached_weakness_token_offers_no_action(self, repo):
        state = _make_state()
        unit = _place(state, "P0", _unit())
        from swu.engine import tokens
        tok = tokens.attach_token(state, state.player_by_id("P0"), unit, "Weakness")
        _to_hand(state, "P0", _unit("Thug", "57", cost=1, traits=("Underworld",)))
        _give_resources(state, "P0", 5)
        assert not _offers_ability(state, tok.instance_id)
        assert not _offers_ability(state, unit.instance_id)


class TestDoctorHemlockHMW_3:

    def test_HMW_3_weakens_a_unit_without_a_weakness(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        from swu.engine import tokens
        state = _make_state()
        hemlock = _place_leader(state, "P0", _get_leader(repo, "HMW", "3"))
        weak = _place(state, "P1", _unit("Weak", "51"))
        fresh = _place(state, "P1", _unit("Fresh", "52"))
        tokens.attach_token(state, state.player_by_id("P1"), weak, "Weakness")
        _give_resources(state, "P0", 2)
        state = _use_ability(state, hemlock.instance_id)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert weak.instance_id not in targets
        state = _drive(state, _accept_and_target(fresh.instance_id))
        assert _weak(state, fresh) == 1

    def test_HMW_3_a_beast_token_does_not_offer_hemlocks_action(self, repo):
        from swu.engine.actions import _create_token_units
        state = _make_state()
        beast = _create_token_units(state, state.player_by_id("P0"), "Beast", 1)[0]
        beast.exhausted = False
        _place(state, "P1", _unit("Foe", "51"))
        _give_resources(state, "P0", 3)
        assert not _offers_ability(state, beast.instance_id)


class TestBosskHMW_15:

    def test_HMW_15_heals_a_damaged_enemy_and_weakens_it(self, repo):
        state = _make_state()
        bossk = _place_leader(state, "P0", _get_leader(repo, "HMW", "15"))
        foe = _place(state, "P1", _unit("Foe", "51", hp=5))
        foe.damage = 2
        state = _drive(_use_ability(state, bossk.instance_id),
                       _accept_and_target(foe.instance_id))
        assert _live(state, foe).damage == 1 and _weak(state, foe) == 1

    def test_HMW_15_not_offered_without_a_damaged_enemy(self, repo):
        state = _make_state()
        bossk = _place_leader(state, "P0", _get_leader(repo, "HMW", "15"))
        _place(state, "P1", _unit("Foe", "51"))
        assert not _offers_ability(state, bossk.instance_id)


class TestTalzinsShuttleHMW_40:

    def _play(self, repo, opp_plays):
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "51", hp=5))
        state.game_memory.cards_played_this_phase["P1"] = opp_plays
        state, _ = _play_from_hand(state, _hmw(repo, "40"),
                                   picker=_accept_and_target(foe.instance_id))
        return _weak(state, foe)

    def test_HMW_40_two_weakness_after_two_opponent_plays(self, repo):
        assert self._play(repo, 2) == 2

    def test_HMW_40_nothing_after_one(self, repo):
        assert self._play(repo, 1) == 0


def test_HMW_59_clone_x_assassin_weakens_on_defeat(repo):
    from swu.engine.actions import apply, AttackWithUnit
    state = _make_state()
    assassin = _place(state, "P0", _hmw(repo, "59"))      # 1/3
    foe = _place(state, "P1", _unit("Foe", "51", power=5, hp=9))
    state.active_player_index = 1
    state = apply(state, AttackWithUnit(foe.instance_id, assassin.instance_id))
    state = _drive(state, _accept_and_target(foe.instance_id))
    assert _weak(state, foe) == 1


class TestNuvoVindiHMW_62:

    def test_HMW_62_when_played_may_give_a_weakness(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "51"))
        state, _ = _play_from_hand(state, _hmw(repo, "62"),
                                   picker=_accept_and_target(foe.instance_id))
        assert _weak(state, foe) == 1

    def test_HMW_62_a_weakened_enemy_dying_passes_a_weakness_on_once(self, repo):
        from swu.engine import tokens
        state = _make_state()
        _place(state, "P0", _hmw(repo, "62"))
        hitter = _place(state, "P0", _unit("Hitter", "52", power=5, hp=9))
        doomed = _place(state, "P1", _unit("Doomed", "53", power=0, hp=3))
        heir = _place(state, "P1", _unit("Heir", "54", hp=9))
        tokens.attach_token(state, state.player_by_id("P1"), doomed, "Weakness")
        state = _attack(state, hitter, doomed, picker=_accept_and_target(heir.instance_id))
        assert _weak(state, heir) == 1
        # Once each round: a second weakened enemy dying does nothing more.
        doomed2 = _place(state, "P1", _unit("Doomed2", "55", power=0, hp=3))
        tokens.attach_token(state, state.player_by_id("P1"), doomed2, "Weakness")
        state = _attack(state, _live(state, hitter), doomed2,
                        picker=_accept_and_target(heir.instance_id))
        assert _weak(state, heir) == 1

    def test_HMW_62_an_unweakened_enemy_dying_does_nothing(self, repo):
        state = _make_state()
        _place(state, "P0", _hmw(repo, "62"))
        hitter = _place(state, "P0", _unit("Hitter", "52", power=5, hp=9))
        doomed = _place(state, "P1", _unit("Doomed", "53", power=0, hp=3))
        heir = _place(state, "P1", _unit("Heir", "54", hp=9))
        state = _attack(state, hitter, doomed, picker=_accept_and_target(heir.instance_id))
        assert _weak(state, heir) == 0


class TestCloneOfTheZilloBeastHMW_65:

    def test_HMW_65_other_friendly_units_get_minus_2_and_can_die(self, repo):
        state = _make_state()
        _place(state, "P0", _unit("Stout", "52", power=4, hp=5))
        frail = _place(state, "P0", _unit("Frail", "53", power=2, hp=2))
        enemy = _place(state, "P1", _unit("Foe", "51", power=2, hp=2))
        state, zillo = _play_from_hand(state, _hmw(repo, "65"))
        ps = state.player_by_id("P0")
        assert all(u.instance_id != frail.instance_id for u in ps.ground_arena)  # 0 HP
        assert _power(state, zillo) == 6
        assert any(u.instance_id == enemy.instance_id
                   for u in state.player_by_id("P1").ground_arena)

    def test_HMW_65_on_attack_may_give_a_weakness(self, repo):
        state = _make_state()
        zillo = _place(state, "P0", _hmw(repo, "65"))
        foe = _place(state, "P1", _unit("Foe", "51", hp=9))
        state = _attack(state, zillo, picker=_accept_and_target(foe.instance_id))
        assert _weak(state, foe) == 1
