"""IC27 (Icons 2027 Edition) card tests — one focused test (or two) per encoded card.

Every test name embeds the card id (``IC27_<n>``) so the ``verify_encoding`` ``-k``
gate selects it.  The helpers are borrowed from the HMW tests.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _get_leader, _make_state, _place, _place_leader,
    _give_resources, _fire_when_played,
)
from tests.test_hmw_cards import (
    _accept_and_target, _attack, _discard, _drive, _live, _offers_ability,
    _token_names, _unit, _use_ability, _with_aspect,
)


def _ic27(repo, number):
    return _get_card(repo, "IC27", number)


def _deploy(repo, number, resources):
    from swu.engine.actions import apply, DeployLeader
    state = _make_state()
    leader = _place_leader(state, "P0", _get_leader(repo, "IC27", number))
    _give_resources(state, "P0", resources)
    state.active_player_index = 0
    state = _drive(apply(state, DeployLeader()), _accept_and_target())
    state.active_player_index = 0
    return state, leader


class TestDarthMaulIC27_5:

    def test_IC27_5_action_pays_1_and_exhausts_to_ping_a_unit(self, repo):
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "IC27", "5"))
        foe = _place(state, "P1", _unit("Foe", "51", hp=3))
        _give_resources(state, "P0", 1)
        state = _drive(_use_ability(state, maul.instance_id),
                       _accept_and_target(foe.instance_id))
        assert _live(state, foe).damage == 1 and _live(state, maul).exhausted
        assert all(r.exhausted for r in state.player_by_id("P0").resources)

    def test_IC27_5_action_needs_a_resource(self, repo):
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "IC27", "5"))
        _place(state, "P1", _unit("Foe", "51"))
        assert not _offers_ability(state, maul.instance_id)

    def test_IC27_5_deployed_on_attack_may_ping_a_unit(self, repo):
        state, maul = _deploy(repo, "5", resources=5)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=4), arena="space")
        state = _attack(state, _live(state, maul), picker=_accept_and_target(foe.instance_id))
        assert _live(state, foe).damage == 1


class TestDrydenVosIC27_14:

    def test_IC27_14_survivor_gets_an_experience_token(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        dryden = _place(state, "P0", _ic27(repo, "14"))
        buddy = _place(state, "P0", _unit("Buddy", "51", hp=3))
        state = _drive(_fire_on_attack(state, dryden), _accept_and_target(buddy.instance_id))
        assert _live(state, buddy).damage == 1
        assert _token_names(state, buddy) == ["Experience"]

    def test_IC27_14_a_unit_that_dies_gets_nothing(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        dryden = _place(state, "P0", _ic27(repo, "14"))
        frail = _place(state, "P0", _unit("Frail", "51", hp=1))
        state = _drive(_fire_on_attack(state, dryden), _accept_and_target(frail.instance_id))
        hit = state.find_instance(frail.instance_id)
        assert hit is None or hit[1].zone.name == "DISCARD"
        assert not state.player_by_id("P0").discard or all(
            not getattr(c, "attached_upgrades", None) for c in state.player_by_id("P0").discard)


class TestBB8IC27_31:

    def test_IC27_31_heals_a_friendly_unit_then_pings_an_enemy(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        bb8 = _place(state, "P0", _ic27(repo, "31"))
        hurt = _place(state, "P0", _unit("Hurt", "51", hp=4))
        hurt.damage = 2
        foe = _place(state, "P1", _unit("Foe", "52", hp=4))

        def pick(state, acts):
            from swu.engine.actions import ChooseTarget
            for want in (hurt.instance_id, foe.instance_id):
                hit = next((a for a in acts if isinstance(a, ChooseTarget)
                            and a.target_id == want), None)
                if hit:
                    return hit
            return None
        state = _drive(_fire_on_attack(state, bb8), pick)
        assert _live(state, hurt).damage == 1 and _live(state, foe).damage == 1

    def test_IC27_31_no_damaged_friendly_unit_means_no_ping(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        bb8 = _place(state, "P0", _ic27(repo, "31"))
        foe = _place(state, "P1", _unit("Foe", "52", hp=4))
        state = _drive(_fire_on_attack(state, bb8))
        assert _live(state, foe).damage == 0


class TestAhsokaTanoIC27_39:

    def test_IC27_39_defeats_a_unit_costing_3_or_less(self, repo):
        state = _make_state()
        cheap = _place(state, "P1", _unit("Cheap", "51", cost=3))
        dear = _place(state, "P1", _unit("Dear", "52", cost=4))
        ahsoka = _place(state, "P0", _ic27(repo, "39"))
        seen = []

        def pick(state, acts):
            from swu.engine.actions import ChooseTarget
            seen.extend(a.target_id for a in acts if isinstance(a, ChooseTarget))
            return _accept_and_target(cheap.instance_id)(state, acts)
        state = _drive(_fire_when_played(state, ahsoka), pick)
        assert dear.instance_id not in seen
        assert state.find_instance(cheap.instance_id)[1].zone.name == "DISCARD"
        assert state.find_instance(dear.instance_id)[1].zone.name == "GROUND_ARENA"


class TestMotherTalzinIC27_66:

    def _setup(self, repo, traits, cost=3, aspect="Villainy"):
        state = _make_state()
        talzin = _place(state, "P0", _ic27(repo, "66"))
        fallen = _discard(state, "P0", _with_aspect(
            _unit("Fallen", "51", hp=5, cost=cost, traits=traits), aspect))
        return state, talzin, fallen

    def _raise(self, state, talzin, fallen):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _fire_when_played(state, talzin)
        plays = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert plays == {fallen.instance_id}
        return _drive(apply(state, PlayFromHand(fallen.instance_id)))

    def test_IC27_66_free_replay_damages_talzin_by_its_cost(self, repo):
        state, talzin, fallen = self._setup(repo, ("Trooper",))
        state = self._raise(state, talzin, fallen)
        assert state.find_instance(fallen.instance_id)[1].zone.name == "GROUND_ARENA"
        assert _live(state, talzin).damage == 3

    def test_IC27_66_a_night_unit_costs_talzin_nothing(self, repo):
        state, talzin, fallen = self._setup(repo, ("Night",))
        state = self._raise(state, talzin, fallen)
        assert _live(state, talzin).damage == 0

    def test_IC27_66_ignores_heroism_and_expensive_units(self, repo):
        state, talzin, _ = self._setup(repo, ("Trooper",), aspect="Heroism")
        _discard(state, "P0", _with_aspect(_unit("Big", "52", cost=5), "Villainy"))
        state = _fire_when_played(state, talzin)
        assert not state.pending_decisions


class TestThirdSisterIC27_102:

    def test_IC27_102_pings_a_friendly_and_an_enemy_ground_unit(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        sister = _place(state, "P0", _ic27(repo, "102"))
        buddy = _place(state, "P0", _unit("Buddy", "51", hp=4))
        foe = _place(state, "P1", _unit("Foe", "52", hp=4))
        flyer = _place(state, "P1", _unit("Flyer", "53", hp=4), arena="space")

        def pick(state, acts):
            from swu.engine.actions import ChooseTarget
            for want in (buddy.instance_id, foe.instance_id):
                hit = next((a for a in acts if isinstance(a, ChooseTarget)
                            and a.target_id == want), None)
                if hit:
                    return hit
            return None
        state = _drive(_fire_on_attack(state, sister), pick)
        assert _live(state, buddy).damage == 1 and _live(state, foe).damage == 1
        assert _live(state, flyer).damage == 0 and _live(state, sister).damage == 0


# ── ic27-set:02 ───────────────────────────────────────────────────────────────

def _target(want):
    """Picker: accept, choose ``want`` when offered, else the engine default."""
    def _pick(state, acts):
        from swu.engine.actions import ChooseTarget
        hit = next((a for a in acts if isinstance(a, ChooseTarget)
                    and a.target_id == want), None)
        return hit or _accept_and_target(want)(state, acts)
    return _pick


def test_IC27_107_aurra_sing_exhausts_to_deal_4(repo):
    state = _make_state()
    aurra = _place(state, "P0", _ic27(repo, "107"))
    foe = _place(state, "P1", _unit("Foe", "51", hp=6))
    state.active_player_index = 0
    state = _drive(_use_ability(state, aurra.instance_id), _target(foe.instance_id))
    assert _live(state, foe).damage == 4 and _live(state, aurra).exhausted


def test_IC27_109_snoke_hits_each_other_unit_and_draws_per_friendly_loss(repo):
    from tests.test_hmw_cards import _deck_card
    state = _make_state()
    for i in range(3):
        _deck_card(state, "P0", _unit(f"Card{i}", f"6{i}"))
    snoke = _place(state, "P0", _ic27(repo, "109"))
    weak_mine = [_place(state, "P0", _unit(f"Weak{i}", f"5{i}", hp=4)) for i in range(2)]
    tough_mine = _place(state, "P0", _unit("Tough", "55", hp=6))
    foe = _place(state, "P1", _unit("Foe", "56", hp=3))
    state = _drive(_fire_when_played(state, snoke))
    assert all(state.find_instance(u.instance_id)[1].zone.name == "DISCARD"
               for u in weak_mine + [foe])
    assert _live(state, tough_mine).damage == 4 and _live(state, snoke).damage == 0
    assert len(state.player_by_id("P0").hand) == 2


def test_IC27_110_supremacy_halves_a_bases_remaining_hp(repo):
    from tests.test_hmw_cards import _base
    state = _make_state()
    supremacy = _place(state, "P0", _ic27(repo, "110"), arena="space")
    base = _base(state, "P1")
    base.damage = 5
    expect = (base.card_def.hp - 5) // 2
    state = _drive(_fire_when_played(state, supremacy), _target(base.instance_id))
    assert _base(state, "P1").damage == 5 + expect


class TestHeraSyndullaIC27_117:

    def _play(self, repo, traits):
        from tests.test_hmw_cards import _base, _play_from_hand
        state = _make_state()
        _place(state, "P0", _ic27(repo, "117"))
        target = _base(state, "P1").instance_id
        state, _ = _play_from_hand(state, _unit("Ally", "51", traits=traits),
                                   picker=_target(target))
        return _base(state, "P1").damage

    def test_IC27_117_another_rebel_card_pings_a_base(self, repo):
        assert self._play(repo, ("Rebel",)) == 1

    def test_IC27_117_a_non_rebel_card_does_nothing(self, repo):
        assert self._play(repo, ("Trooper",)) == 0

    def test_IC27_117_hera_herself_does_not_count(self, repo):
        from tests.test_hmw_cards import _base, _play_from_hand
        state = _make_state()
        state, _ = _play_from_hand(state, _ic27(repo, "117"))
        assert _base(state, "P1").damage == 0 and _base(state, "P0").damage == 0


class TestSabineWrenIC27_119:

    def _setup(self, repo, costs):
        from tests.test_hmw_cards import _deck_card
        state = _make_state()
        cards = [_deck_card(state, "P1", _unit(f"Top{i}", f"6{i}", cost=c))
                 for i, c in enumerate(costs)]
        sabine = _place(state, "P0", _ic27(repo, "119"))
        foe = _place(state, "P1", _unit("Foe", "51", hp=6))
        return state, sabine, foe, cards

    def test_IC27_119_mills_the_chosen_deck_and_deals_the_cost_gap(self, repo):
        from tests.test_sec_cards import _pick_modal
        from tests.test_hmw_cards import _deck_card
        state, sabine, foe, milled = self._setup(repo, (5, 1))
        _deck_card(state, "P0", _unit("Mine", "70"))
        state = _fire_when_played(state, sabine)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        state = _drive(_pick_modal(state, 2), _target(foe.instance_id))
        assert all(state.find_instance(c.instance_id)[1].zone.name == "DISCARD"
                   for c in milled[:2])
        assert _live(state, foe).damage == 4

    def test_IC27_119_one_deck_skips_the_choice_and_equal_costs_deal_nothing(self, repo):
        state, sabine, foe, _ = self._setup(repo, (3, 3))
        state = _drive(_fire_when_played(state, sabine), _target(foe.instance_id))
        assert len(state.player_by_id("P1").discard) == 2
        assert _live(state, foe).damage == 0


def test_IC27_124_k2so_blasts_each_enemy_unit_and_base(repo):
    from tests.test_sor_cards import _fire_when_defeated
    from tests.test_hmw_cards import _base
    state = _make_state()
    k2 = _place(state, "P0", _ic27(repo, "124"))
    foe = _place(state, "P1", _unit("Foe", "51", hp=7))
    flyer = _place(state, "P1", _unit("Flyer", "52", hp=7), arena="space")
    mine = _place(state, "P0", _unit("Mine", "53", hp=7))
    state = _drive(_fire_when_defeated(state, k2))
    assert _live(state, foe).damage == 5 and _live(state, flyer).damage == 5
    assert _base(state, "P1").damage == 5
    assert _live(state, mine).damage == 0 and _base(state, "P0").damage == 0


def test_IC27_127_act_of_aggression_draws_hits_and_buffs(repo):
    from tests.test_sor_cards import _play_event_from_hand
    from tests.test_hmw_cards import _deck_card, _kw, _power
    state = _make_state()
    _deck_card(state, "P0", _unit("Drawn", "60"))
    mine = _place(state, "P0", _unit("Mine", "51", power=2, hp=4))
    foe = _place(state, "P1", _unit("Foe", "52", hp=5))

    def pick(state, acts):
        from swu.engine.actions import ChooseTarget
        top = state.pending_decisions[-1] if state.pending_decisions else None
        want = foe.instance_id
        if top is not None and int(top.context.get("effect_idx", 0) or 0) >= 2:
            want = mine.instance_id
        hit = next((a for a in acts if isinstance(a, ChooseTarget)
                    and a.target_id == want), None)
        return hit or _accept_and_target(want)(state, acts)
    state, _ = _play_event_from_hand(state, repo, "IC27", "127", resources=10)
    state = _drive(state, pick)
    assert [c.card_def.name for c in state.player_by_id("P0").hand] == ["Drawn"]
    assert _live(state, foe).damage == 3
    assert _power(state, mine) == 5 and _kw(state, mine, "Overwhelm")
