"""HMW (Homeworlds) card tests — one focused test (or two) per encoded card.

Every test name embeds the card id (``HMW_<n>``) so the ``verify_encoding`` ``-k``
gate selects it.  Most of ``hmw-set:01`` is Fortify upgrades, which sit on their
controller's base; ``_attach_to_base`` puts one there directly (no triggers) and a
real ``PlayCard`` is used wherever the When Played matters.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _get_leader, _make_state, _place, _place_leader,
    _give_resources,
)
from tests.test_fortify import (
    _unit_def, _to_hand, _attach_to_base, _deck, _drain, _check_invariants,
)


# ── helpers ───────────────────────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════════════════
# hmw-set:01 — Fortify residual text
# ══════════════════════════════════════════════════════════════════════════════


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
    from swu.engine.keywords import has_keyword, Keyword
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
