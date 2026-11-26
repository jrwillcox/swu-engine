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


class TestDarthSidiousIC27_26:
    """"Restore 3.  When you heal damage from your base: Deal that much damage to an
    enemy unit." """

    def _setup(self, repo, base_damage):
        state = _make_state()
        sidious = _place(state, "P0", _ic27(repo, "26"))
        state.player_by_id("P0").base_instance.damage = base_damage
        state.active_player_index = 0
        return state, sidious

    def test_IC27_26_restore_deals_3_before_combat_damage(self, repo):
        state, sidious = self._setup(repo, base_damage=5)
        # 5 power, 3 HP: survives nothing, but hits Sidious hard if it gets to strike.
        brute = _place(state, "P1", _unit("Brute", "51", power=5, hp=3))
        state = _attack(state, _live(state, sidious), brute,
                        picker=_accept_and_target(brute.instance_id))
        assert state.player_by_id("P0").base_instance.damage == 2      # Restore 3
        assert state.find_instance(brute.instance_id)[1].zone.name == "DISCARD"
        # The trigger landed in the On Attack window: no combat damage came back.
        assert _live(state, sidious).damage == 0
        assert not state.pending_decisions

    def test_IC27_26_deals_only_as_much_as_was_healed(self, repo):
        state, sidious = self._setup(repo, base_damage=1)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=6))
        bystander = _place(state, "P1", _unit("Bystander", "52", power=0, hp=6))
        state = _attack(state, _live(state, sidious), foe,
                        picker=_accept_and_target(bystander.instance_id))
        assert state.player_by_id("P0").base_instance.damage == 0
        assert _live(state, bystander).damage == 1                    # "that much"
        assert _live(state, foe).damage == 5                          # combat only

    def test_IC27_26_undamaged_base_heals_nothing_so_no_trigger(self, repo):
        state, sidious = self._setup(repo, base_damage=0)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=9))
        other = _place(state, "P1", _unit("Other", "52", power=0, hp=9))
        state = _attack(state, _live(state, sidious), foe)
        assert _live(state, other).damage == 0
        assert _live(state, foe).damage == 5

    def test_IC27_26_base_attack_still_hits_the_base(self, repo):
        state, sidious = self._setup(repo, base_damage=4)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=6))
        state = _attack(state, _live(state, sidious),
                        picker=_accept_and_target(foe.instance_id))
        assert _live(state, foe).damage == 3
        assert state.player_by_id("P1").base_instance.damage == 5
        assert state.player_by_id("P0").base_instance.damage == 1

    def test_IC27_26_heal_outside_an_attack_fires_at_the_settle_point(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state, sidious = self._setup(repo, base_damage=5)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=6))
        state, _ = _play_event_from_hand(state, repo, "SHD", "252", resources=20)
        if state.pending_decisions:     # the trigger's target choice
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, ChooseTarget)
                                      and a.target_id == foe.instance_id))
        state = _drive(state)
        assert state.player_by_id("P0").base_instance.damage == 2      # healed 3
        assert _live(state, foe).damage == 3

    def test_IC27_26_ignores_the_opponents_base_heal(self, repo):
        from swu.engine.actions import note_base_healed, _fire_base_heal_observers
        state, sidious = self._setup(repo, base_damage=0)
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=6))
        enemy_base = state.player_by_id("P1").base_instance
        enemy_base.damage = 3
        enemy_base.damage -= 3
        note_base_healed(state, enemy_base, 3)
        state = _drive(_fire_base_heal_observers(state))
        assert _live(state, foe).damage == 0
        assert not state.game_memory.base_heal_events

    def test_IC27_26_ledger_survives_serialisation(self, repo):
        from swu.engine.state import GameMemory
        gm = GameMemory()
        gm.base_heal_events.append(["P0", 3])
        assert GameMemory.from_dict(gm.to_dict()).base_heal_events == [["P0", 3]]


def _pick_option(idx):
    """Select modal option ``idx`` (an ability index) when offered."""
    def _pick(state, acts):
        from swu.engine.actions import SelectModalOption
        return next((a for a in acts if isinstance(a, SelectModalOption)
                     and a.option_idx == idx), None)
    return _pick


def _then(*pickers):
    def _pick(state, acts):
        for p in pickers:
            hit = p(state, acts)
            if hit is not None:
                return hit
        return None
    return _pick


class TestR2D2IC27_151:

    def test_IC27_151_deal_1_to_a_ground_unit(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        r2 = _place(state, "P0", _ic27(repo, "151"))
        foe = _place(state, "P1", _unit("Foe", "51", hp=4))
        state = _drive(_fire_on_attack(state, r2),
                       _then(_pick_option(2), _accept_and_target(foe.instance_id)))
        assert _live(state, foe).damage == 1

    def test_IC27_151_ready_a_resource(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        r2 = _place(state, "P0", _ic27(repo, "151"))
        _give_resources(state, "P0", 2)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _drive(_fire_on_attack(state, r2), _pick_option(1))
        assert sum(not r.exhausted for r in state.player_by_id("P0").resources) == 1

    def test_IC27_151_peek_may_discard_the_top_card(self, repo):
        from tests.test_sor_cards import _fire_on_attack, _push_deck_top
        from swu.engine.actions import DiscardTopCard
        state = _make_state()
        r2 = _place(state, "P0", _ic27(repo, "151"))
        top = _push_deck_top(state, "P0", _unit("Top", "53"))
        state = _drive(_fire_on_attack(state, r2), _then(
            _pick_option(3),
            lambda s, acts: next((a for a in acts if isinstance(a, DiscardTopCard)), None)))
        assert state.find_instance(top.instance_id)[1].zone.name == "DISCARD"


class TestIAmYourFatherIC27_185:

    def test_IC27_185_saying_no_draws_3(self, repo):
        from tests.test_sor_cards import _play_event_from_hand, _push_deck_top
        from swu.engine.actions import SayNo
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "51", hp=9))
        for i in range(4):
            _push_deck_top(state, "P0", _unit(f"Card{i}", f"6{i}"))
        hand_before = len(state.player_by_id("P0").hand)
        state, _ = _play_event_from_hand(state, repo, "IC27", "185")
        state = _drive(state, _then(
            _accept_and_target(foe.instance_id),
            lambda s, acts: next((a for a in acts if isinstance(a, SayNo)), None)))
        assert _live(state, foe).damage == 0
        assert len(state.player_by_id("P0").hand) == hand_before + 3

    def test_IC27_185_allowing_deals_7(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import AllowEffect
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "51", hp=9))
        state, _ = _play_event_from_hand(state, repo, "IC27", "185")
        state = _drive(state, _then(
            _accept_and_target(foe.instance_id),
            lambda s, acts: next((a for a in acts if isinstance(a, AllowEffect)), None)))
        assert _live(state, foe).damage == 7


def _hand(state, pid, card_def):
    from tests.test_hmw_cards import _to_hand
    return _to_hand(state, pid, card_def)


def _stock_deck(state, pid, n=4):
    from tests.test_sor_cards import _push_deck_top
    return [_push_deck_top(state, pid, _unit(f"Deck{i}", f"7{i}")) for i in range(n)]


def _select_discard(state, acts):
    from swu.engine.actions import SelectDiscardCard
    return next((a for a in acts if isinstance(a, SelectDiscardCard)), None)


class TestKyloRenIC27_3:

    def test_IC27_3_discard_to_give_an_experience_token(self, repo):
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_leader(repo, "IC27", "3"))
        pal = _place(state, "P0", _unit("Pal", "51"))
        pitch = _hand(state, "P0", _unit("Pitch", "52"))
        state = _drive(_use_ability(state, kylo.instance_id),
                       _accept_and_target(pal.instance_id))
        assert _token_names(state, pal) == ["Experience"]
        assert state.find_instance(pitch.instance_id)[1].zone.name == "DISCARD"
        assert _live(state, kylo).exhausted

    def test_IC27_3_needs_a_card_in_hand(self, repo):
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_leader(repo, "IC27", "3"))
        _place(state, "P0", _unit("Pal", "51"))
        assert not _offers_ability(state, kylo.instance_id)

    def test_IC27_3_when_deployed_returns_a_unit_from_discard(self, repo):
        from swu.engine.actions import apply, DeployLeader
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "IC27", "3"))
        dead = _discard(state, "P0", _unit("Dead", "51"))
        _give_resources(state, "P0", 5)
        state.active_player_index = 0
        state = _drive(apply(state, DeployLeader()),
                       _then(_select_discard, _accept_and_target()))
        assert dead.instance_id in {c.instance_id for c in state.player_by_id("P0").hand}


class TestLukeSkywalkerIC27_6:

    def test_IC27_6_draws_2_more_in_the_starting_hand(self, repo):
        from swu.engine.actions import _starting_hand_size
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "IC27", "6"))
        assert _starting_hand_size(state.player_by_id("P0")) == 8
        assert _starting_hand_size(state.player_by_id("P1")) == 6

    def test_IC27_6_on_attack_discard_for_plus_2(self, repo):
        state, luke = _deploy(repo, "6", resources=6)
        _hand(state, "P0", _unit("Pitch", "52"))
        foe = _place(state, "P1", _unit("Foe", "51", power=0, hp=20))
        state = _attack(state, _live(state, luke), foe, picker=_accept_and_target())
        assert _live(state, foe).damage == 6           # 4 power + 2 for this attack
        assert not state.player_by_id("P0").hand


class TestPrincessLeiaIC27_8:

    def test_IC27_8_action_draws_then_puts_a_card_back(self, repo):
        state = _make_state()
        leia = _place_leader(state, "P0", _get_leader(repo, "IC27", "8"))
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P0", 1)
        state = _drive(_use_ability(state, leia.instance_id))
        ps = state.player_by_id("P0")
        assert len(ps.deck) == 3 and not ps.hand      # drew 1, put 1 back
        assert _live(state, leia).exhausted and all(r.exhausted for r in ps.resources)

    def test_IC27_8_deployed_on_attack_draws_then_puts_back(self, repo):
        state, leia = _deploy(repo, "8", resources=6)
        _stock_deck(state, "P0", 3)
        hand_before = len(state.player_by_id("P0").hand)
        state = _attack(state, _live(state, leia))
        ps = state.player_by_id("P0")
        assert len(ps.deck) == 3 and len(ps.hand) == hand_before


class TestAdmiralHoldoIC27_38:

    def test_IC27_38_draws_one_more_in_the_regroup_phase(self, repo):
        from swu.engine.actions import _regroup_draw_count
        state = _make_state()
        _place(state, "P0", _ic27(repo, "38"))
        assert _regroup_draw_count(state, state.player_by_id("P0")) == 3
        assert _regroup_draw_count(state, state.player_by_id("P1")) == 2

    def test_IC27_38_regroup_draw_through_the_phase_change(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        _place(state, "P0", _ic27(repo, "38"))
        _stock_deck(state, "P0", 5)
        _stock_deck(state, "P1", 5)
        _enter_regroup(state)
        assert len(state.player_by_id("P0").hand) == 3
        assert len(state.player_by_id("P1").hand) == 2


class TestObiWanKenobiIC27_42:

    def test_IC27_42_minus_5_to_a_unit_that_entered_play(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        foe = _place(state, "P1", _unit("Fresh", "51", power=6, hp=9))
        state.game_memory.units_played_this_phase.add(foe.instance_id)
        obi = _place(state, "P0", _ic27(repo, "42"))
        state = _drive(_fire_when_played(state, obi),
                       _then(_pick_option(2), _accept_and_target(foe.instance_id)))
        live = _live(state, foe)
        assert compute_power(state, live) == 1 and compute_hp(state, live) == 4

    def test_IC27_42_replays_a_unit_defeated_this_phase_for_5_less(self, repo):
        from swu.engine.actions import PlayFromHand
        state = _make_state()
        dead = _discard(state, "P0", _unit("Dead", "51", cost=6))
        state.game_memory.units_defeated_this_round.add(dead.instance_id)
        _give_resources(state, "P0", 1)
        obi = _place(state, "P0", _ic27(repo, "42"))

        def pick(state, acts):
            return _then(_accept_and_target(), _pick_option(1))(state, acts) or next(
                (a for a in acts if isinstance(a, PlayFromHand)
                 and a.instance_id == dead.instance_id), None)
        state = _drive(_fire_when_played(state, obi), pick)
        assert state.find_instance(dead.instance_id)[1].zone.name == "GROUND_ARENA"


class TestKylosTieSilencerIC27_63:

    def test_IC27_63_playable_from_discard_after_being_discarded(self, repo):
        from swu.engine.actions import legal_actions, PlayFromDiscard, note_hand_or_deck_discard
        state = _make_state()
        tie = _discard(state, "P0", _ic27(repo, "63"))
        _give_resources(state, "P0", 10)          # cost 4 + aspect penalties
        state.active_player_index = 0
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state))
        note_hand_or_deck_discard(state, tie)
        assert any(isinstance(a, PlayFromDiscard) and a.instance_id == tie.instance_id
                   for a in legal_actions(state))


class TestC3POIC27_70:

    def test_IC27_70_token_reaches_6_power_and_draws(self, repo):
        state = _make_state()
        c3po = _place(state, "P0", _ic27(repo, "70"))
        big = _place(state, "P0", _unit("Big", "51", power=5, hp=5))
        _stock_deck(state, "P0", 2)
        state = _drive(_use_ability(state, c3po.instance_id),
                       _accept_and_target(big.instance_id))
        assert _token_names(state, big) == ["Experience"]
        assert len(state.player_by_id("P0").hand) == 1

    def test_IC27_70_no_draw_below_6_power(self, repo):
        state = _make_state()
        c3po = _place(state, "P0", _ic27(repo, "70"))
        small = _place(state, "P0", _unit("Small", "51", power=2, hp=5))
        _stock_deck(state, "P0", 2)
        state = _drive(_use_ability(state, c3po.instance_id),
                       _accept_and_target(small.instance_id))
        assert _token_names(state, small) == ["Experience"]
        assert not state.player_by_id("P0").hand


def _defeat(state, ci):
    """Defeat ``ci`` through the engine's defeat path, then drain triggers."""
    from swu.abilities.resolver import _apply_defeat_unit
    _apply_defeat_unit(state, ci.instance_id, "test")
    return state


class TestAnakinSkywalkerIC27_78:

    def test_IC27_78_when_defeated_draws_darth_vader(self, repo):
        from tests.test_sor_cards import _push_deck_top
        from swu.engine.actions import _fire_damage_observers  # noqa: F401
        state = _make_state()
        ani = _place(state, "P0", _ic27(repo, "78"))
        _push_deck_top(state, "P0", _unit("Filler", "61"))
        vader = _push_deck_top(state, "P0", _unit("Darth Vader", "62"))
        _push_deck_top(state, "P0", _unit("Filler", "63"))
        state = _drive(_defeat(state, ani), _accept_and_target(vader.instance_id))
        assert vader.instance_id in {c.instance_id for c in state.player_by_id("P0").hand}

    def test_IC27_78_waives_vader_aspect_penalty_only_from_discard(self, repo):
        from swu.engine.actions import _controller_waives_aspect_penalty
        from tests.test_hmw_cards import _with_aspect
        state = _make_state()
        ps = state.player_by_id("P0")
        vader = _hand(state, "P0", _with_aspect(_unit("Darth Vader", "62", cost=5),
                                                "Villainy"))
        other = _hand(state, "P0", _with_aspect(_unit("Someone", "63", cost=5),
                                                "Villainy"))
        in_play = _place(state, "P0", _ic27(repo, "78"))
        assert _controller_waives_aspect_penalty(state, vader, ps) == 0   # in play
        ps.ground_arena.remove(in_play)
        _discard(state, "P0", _ic27(repo, "78"))
        assert _controller_waives_aspect_penalty(state, vader, ps) > 0
        assert _controller_waives_aspect_penalty(state, other, ps) == 0


class TestNegotiatorIC27_84:

    def test_IC27_84_on_attack_ramps_then_may_return_a_resource(self, repo):
        state = _make_state()
        neg = _place(state, "P0", _ic27(repo, "84"), arena="space")
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P0", 2)
        state = _attack(state, _live(state, neg), picker=_accept_and_target())
        ps = state.player_by_id("P0")
        assert len(ps.resources) == 2 and len(ps.hand) == 1 and len(ps.deck) == 2

    def test_IC27_84_declining_the_return_keeps_the_ramp(self, repo):
        state = _make_state()
        neg = _place(state, "P0", _ic27(repo, "84"), arena="space")
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P0", 2)
        from tests.test_hmw_cards import _decline_all
        state = _attack(state, _live(state, neg), picker=_decline_all)
        ps = state.player_by_id("P0")
        assert len(ps.resources) == 3 and not ps.hand


class TestIssueACommandIC27_87:

    def test_IC27_87_draws_a_unit_tokens_and_resources_itself(self, repo):
        from tests.test_sor_cards import _play_event_from_hand, _push_deck_top
        state = _make_state()
        pal = _place(state, "P0", _unit("Pal", "51"))
        top = _push_deck_top(state, "P0", _unit("TopUnit", "61"))
        state, evt = _play_event_from_hand(state, repo, "IC27", "87")
        state = _drive(state, _accept_and_target(pal.instance_id))
        ps = state.player_by_id("P0")
        assert top.instance_id in {c.instance_id for c in ps.hand}
        assert _token_names(state, pal) == ["Experience"]
        res = next(r for r in ps.resources if r.instance_id == evt.instance_id)
        assert res.exhausted and res.face_down

    def test_IC27_87_a_non_unit_stays_on_top(self, repo):
        from tests.test_sor_cards import _play_event_from_hand, _push_deck_top
        state = _make_state()
        _place(state, "P0", _unit("Pal", "51"))
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "233"))   # an event
        state, _ = _play_event_from_hand(state, repo, "IC27", "87")
        state = _drive(state, _accept_and_target())
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id


class TestBlackOneIC27_116:

    def test_IC27_116_draws_when_played_and_when_defeated(self, repo):
        state = _make_state()
        _stock_deck(state, "P0", 3)
        b1 = _place(state, "P0", _ic27(repo, "116"), arena="space")
        state = _drive(_fire_when_played(state, b1))
        assert len(state.player_by_id("P0").hand) == 1
        state = _drive(_defeat(state, _live(state, b1)))
        assert len(state.player_by_id("P0").hand) == 2


class TestTheGhostIC27_122:

    def test_IC27_122_draws_when_a_friendly_unit_hits_the_enemy_base(self, repo):
        state = _make_state()
        _place(state, "P0", _ic27(repo, "122"), arena="space")
        raider = _place(state, "P0", _unit("Raider", "51", power=2, hp=3))
        _stock_deck(state, "P0", 3)
        state = _attack(state, _live(state, raider))
        assert len(state.player_by_id("P0").hand) == 1

    def test_IC27_122_no_draw_with_8_cards_in_hand(self, repo):
        state = _make_state()
        _place(state, "P0", _ic27(repo, "122"), arena="space")
        raider = _place(state, "P0", _unit("Raider", "51", power=2, hp=3))
        _stock_deck(state, "P0", 3)
        for i in range(8):
            _hand(state, "P0", _unit(f"H{i}", f"8{i}"))
        state = _attack(state, _live(state, raider))
        assert len(state.player_by_id("P0").hand) == 8

    def test_IC27_122_an_event_hitting_the_base_draws_nothing(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        _place(state, "P0", _ic27(repo, "122"), arena="space")
        _stock_deck(state, "P0", 3)
        # Daring Raid SHD_178 — "Deal 2 damage to a unit or base."
        state, _ = _play_event_from_hand(state, repo, "SHD", "178")
        enemy_base = state.player_by_id("P1").base_instance
        state = _drive(state, _accept_and_target(enemy_base.instance_id))
        assert state.player_by_id("P1").base_instance.damage == 2
        assert not state.player_by_id("P0").hand


class TestJangoFettIC27_144:

    def test_IC27_144_discard_to_return_an_event(self, repo):
        state = _make_state()
        jango = _place(state, "P0", _ic27(repo, "144"))
        old = _discard(state, "P0", _get_card(repo, "SOR", "233"))
        _hand(state, "P0", _unit("Pitch", "52"))
        state = _drive(_defeat(state, jango), _then(
            _accept_and_target(),
            lambda s, acts: next((a for a in acts if type(a).__name__ ==
                                  "SelectDiscardCard"), None)))
        assert old.instance_id in {c.instance_id for c in state.player_by_id("P0").hand}


class TestPoggleTheLesserIC27_145:

    def test_IC27_145_pay_and_discard_for_a_3_discount(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        poggle = _place(state, "P0", _ic27(repo, "145"))
        _hand(state, "P0", _unit("Pitch", "52"))
        _give_resources(state, "P0", 2)
        state = _drive(_fire_on_attack(state, poggle), _accept_and_target())
        ps = state.player_by_id("P0")
        assert not ps.hand and sum(r.exhausted for r in ps.resources) == 1
        assert any(d["amount"] == 3 and d["player_id"] == "P0"
                   for d in state.game_memory.pending_play_discounts)

    def test_IC27_145_not_offered_without_a_ready_resource(self, repo):
        from tests.test_sor_cards import _fire_on_attack
        state = _make_state()
        poggle = _place(state, "P0", _ic27(repo, "145"))
        _hand(state, "P0", _unit("Pitch", "52"))
        state = _fire_on_attack(state, poggle)
        assert not state.pending_decisions


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


# ── ic27-set:06 ───────────────────────────────────────────────────────────────


def _pick_class(name, **fields):
    def _pick(state, acts):
        return next((a for a in acts if type(a).__name__ == name
                     and all(getattr(a, k, None) == v for k, v in fields.items())),
                    None)
    return _pick


class TestHanSoloIC27_155:

    def test_IC27_155_searches_10_draws_then_discards_at_random(self, repo):
        state = _make_state()
        deck = _stock_deck(state, "P0", 12)
        wanted = deck[-1]                      # the most recently pushed = top card
        keep = _hand(state, "P0", _unit("Keep", "52"))
        han = _place(state, "P0", _ic27(repo, "155"))
        state = _drive(_fire_when_played(state, han),
                       _pick_class("SelectSearchCard", instance_id=wanted.instance_id))
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 1 and len(ps.discard) == 1 and len(ps.deck) == 11
        assert {c.instance_id for c in ps.hand + ps.discard} == {
            wanted.instance_id, keep.instance_id}

    def test_IC27_155_empty_deck_still_discards_at_random(self, repo):
        state = _make_state()
        state.player_by_id("P0").deck.clear()
        _hand(state, "P0", _unit("Keep", "52"))
        han = _place(state, "P0", _ic27(repo, "155"))
        state = _drive(_fire_when_played(state, han))
        ps = state.player_by_id("P0")
        assert not ps.hand and len(ps.discard) == 1


class TestMillenniumFalconIC27_158:

    def _setup(self, repo, resources):
        state = _make_state()
        falcon = _place(state, "P0", _ic27(repo, "158"), arena="space")
        cheap = _place(state, "P0", _unit("Cheap", "51", cost=2))
        _place(state, "P0", _unit("Pricey", "53", cost=4))
        _give_resources(state, "P0", resources)
        state.active_player_index = 0
        return state, falcon, cheap

    def test_IC27_158_pays_1_bounces_and_replays_for_free(self, repo):
        state, falcon, cheap = self._setup(repo, resources=2)
        state = _attack(state, _live(state, falcon),
                        picker=_then(_accept_and_target(cheap.instance_id),
                                     _pick_class("PlayFromHand")))
        ps = state.player_by_id("P0")
        live = state.find_instance(cheap.instance_id)
        assert live is not None and live[1].zone.name == "GROUND_ARENA"
        assert sum(r.exhausted for r in ps.resources) == 1      # the 1, not its cost

    def test_IC27_158_only_cheap_units_and_needs_a_resource(self, repo):
        state, falcon, cheap = self._setup(repo, resources=0)
        state = _attack(state, _live(state, falcon), picker=_accept_and_target())
        assert _live(state, cheap).zone.name == "GROUND_ARENA"
        assert len(state.player_by_id("P0").hand) == 0


class TestIveGotABadFeelingIC27_166:

    def test_IC27_166_bounces_a_unit_and_shields_a_friendly(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        pal = _place(state, "P0", _unit("Pal", "51"))
        foe = _place(state, "P1", _unit("Foe", "52"))
        state, _ = _play_event_from_hand(state, repo, "IC27", "166")
        state = _drive(state, _then(_accept_and_target(foe.instance_id)))
        assert foe.instance_id in {c.instance_id for c in state.player_by_id("P1").hand}
        assert _token_names(state, pal) == ["Shield"]


class TestLandoCalrissianIC27_167:

    def test_IC27_167_returns_3_resources_then_may_resource_up_to_3(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 5)
        ps = state.player_by_id("P0")
        for r in ps.resources[:2]:
            r.exhausted = True
        exhausted_ids = {r.instance_id for r in ps.resources[:2]}
        lando = _place(state, "P0", _ic27(repo, "167"))
        state = _fire_when_played(state, lando)
        ps = state.player_by_id("P0")
        assert len(ps.resources) == 2 and len(ps.hand) == 3
        assert exhausted_ids <= {c.instance_id for c in ps.hand}   # spent ones first
        picks = iter([c.instance_id for c in ps.hand][:2])
        state = _drive(state, lambda s, acts: next(
            (a for a in acts if type(a).__name__ == "SelectHandCardToResource"
             and a.instance_id == next(picks, None)), None)
            or next(a for a in acts if type(a).__name__ == "FinishResourceFromHand"))
        ps = state.player_by_id("P0")
        assert len(ps.resources) == 4 and len(ps.hand) == 1


class TestCunningPloyIC27_168:

    def test_IC27_168_discards_from_hand_exhausts_and_attacks_plus_3(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        state = _make_state()
        pal = _place(state, "P0", _unit("Pal", "51", power=2, hp=5))
        foe = _place(state, "P1", _unit("Foe", "52", power=1, hp=9))
        victim = _hand(state, "P1", _unit("Victim", "53"))
        _stock_deck(state, "P1", 2)
        state, _ = _play_event_from_hand(state, repo, "IC27", "168")
        state = _drive(state, _then(
            _pick_class("NameAndDiscard"),
            _accept_and_target(foe.instance_id),
            _pick_class("AttackWithUnit", attacker_id=pal.instance_id, defender_id=None)))
        p1 = state.player_by_id("P1")
        assert victim.instance_id in {c.instance_id for c in p1.discard}
        assert len(p1.hand) == 1                                   # drew a replacement
        assert _live(state, foe).exhausted
        assert p1.base_instance.damage == 5                        # 2 + 3


class TestMorganElsbethIC27_179:

    def test_IC27_179_draws_a_6_cost_top_card_else_discards_it(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        morgan = _place(state, "P0", _ic27(repo, "179"))
        cheap = _push_deck_top(state, "P0", _unit("Cheap", "61", cost=5))
        big = _push_deck_top(state, "P0", _unit("Big", "62", cost=6))
        state = _attack(state, _live(state, morgan))
        ps = state.player_by_id("P0")
        assert big.instance_id in {c.instance_id for c in ps.hand}
        state.active_player_index = 0
        state = _attack(state, _live(state, morgan))
        ps = state.player_by_id("P0")
        assert cheap.instance_id in {c.instance_id for c in ps.discard}


class TestJarJarBinksIC27_187:

    def test_IC27_187_mills_and_a_6_cost_card_gives_plus_4(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        jj = _place(state, "P0", _ic27(repo, "187"))
        _push_deck_top(state, "P0", _unit("Cheap", "61", cost=2))
        big = _push_deck_top(state, "P0", _unit("Big", "62", cost=7))
        state = _attack(state, _live(state, jj))
        assert big.instance_id in {c.instance_id for c in state.player_by_id("P0").discard}
        assert state.player_by_id("P1").base_instance.damage == 5       # 1 + 4
        state.active_player_index = 0
        state = _attack(state, _live(state, jj))
        assert state.player_by_id("P1").base_instance.damage == 6       # +1 only



class TestYoureMyOnlyHopeIC27_194:

    def test_IC27_194_plays_the_top_card_5_cheaper(self, repo):
        from tests.test_sor_cards import _play_event_from_hand, _push_deck_top
        from swu.engine.actions import legal_actions, apply, PlayTopCard
        state = _make_state()
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state, _ = _play_event_from_hand(state, repo, "IC27", "194")
        dec = state.pending_decisions[-1]
        assert dec.kind == "peek_top" and dec.context["cost_reduction"] == 5
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayTopCard)))
        assert _live(state, top).zone.name in ("GROUND_ARENA", "SPACE_ARENA")



# ── ic27-set:08 ───────────────────────────────────────────────────────────────


class TestDarthVaderIC27_1:

    def test_IC27_1_action_defeats_a_friendly_draws_and_heals_2(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_leader(repo, "IC27", "1"))
        fodder = _place(state, "P0", _unit("Fodder", "51"))
        _stock_deck(state, "P0", 2)
        state.player_by_id("P0").base_instance.damage = 3
        _give_resources(state, "P0", 1)
        state = _drive(_use_ability(state, vader.instance_id),
                       _accept_and_target(fodder.instance_id))
        ps = state.player_by_id("P0")
        assert state.find_instance(fodder.instance_id)[1].zone.name == "DISCARD"
        assert len(ps.hand) == 1 and ps.base_instance.damage == 1
        assert _live(state, vader).exhausted

    def test_IC27_1_action_needs_a_unit_to_defeat(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_leader(repo, "IC27", "1"))
        _give_resources(state, "P0", 1)
        assert not _offers_ability(state, vader.instance_id)

    def test_IC27_1_deployed_on_attack_may_defeat_another_friendly(self, repo):
        state, vader = _deploy(repo, "1", resources=7)
        fodder = _place(state, "P0", _unit("Fodder", "51"))
        _stock_deck(state, "P0", 2)
        state.player_by_id("P0").base_instance.damage = 3
        state = _attack(state, _live(state, vader),
                        picker=_accept_and_target(fodder.instance_id))
        ps = state.player_by_id("P0")
        assert state.find_instance(fodder.instance_id)[1].zone.name == "DISCARD"
        assert len(ps.hand) == 1 and ps.base_instance.damage == 1


class TestReyIC27_2:

    def test_IC27_2_action_gives_experience_to_a_damaged_unit(self, repo):
        state = _make_state()
        rey = _place_leader(state, "P0", _get_leader(repo, "IC27", "2"))
        _place(state, "P0", _unit("Fresh", "51"))
        hurt = _place(state, "P1", _unit("Hurt", "52", hp=5))
        hurt.damage = 1
        _give_resources(state, "P0", 1)
        state = _drive(_use_ability(state, rey.instance_id), _accept_and_target())
        assert _token_names(state, hurt) == ["Experience"]

    def test_IC27_2_action_needs_a_damaged_unit(self, repo):
        state = _make_state()
        rey = _place_leader(state, "P0", _get_leader(repo, "IC27", "2"))
        _place(state, "P1", _unit("Fresh", "52"))
        _give_resources(state, "P0", 1)
        assert not _offers_ability(state, rey.instance_id)

    def test_IC27_2_deployed_on_attack_may_give_experience(self, repo):
        state, rey = _deploy(repo, "2", resources=5)
        hurt = _place(state, "P0", _unit("Hurt", "52", hp=5))
        hurt.damage = 2
        state = _attack(state, _live(state, rey), picker=_accept_and_target())
        assert _token_names(state, hurt) == ["Experience"]


class TestMaceWinduIC27_4:

    def test_IC27_4_action_attacks_with_restore_2(self, repo):
        state = _make_state()
        mace = _place_leader(state, "P0", _get_leader(repo, "IC27", "4"))
        pal = _place(state, "P0", _unit("Pal", "51", power=3))
        state.player_by_id("P0").base_instance.damage = 4
        _give_resources(state, "P0", 1)
        state = _drive(_use_ability(state, mace.instance_id),
                       _pick_class("AttackWithUnit", attacker_id=pal.instance_id,
                                   defender_id=None))
        assert state.player_by_id("P0").base_instance.damage == 2
        assert state.player_by_id("P1").base_instance.damage == 3

    def test_IC27_4_when_deployed_resources_the_top_card(self, repo):
        from tests.test_sor_cards import _push_deck_top
        from swu.engine.actions import apply, DeployLeader
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "IC27", "4"))
        top = _push_deck_top(state, "P0", _unit("Top", "61"))
        _give_resources(state, "P0", 6)
        state.active_player_index = 0
        state = _drive(apply(state, DeployLeader()))
        ps = state.player_by_id("P0")
        assert top.instance_id in {r.instance_id for r in ps.resources}


class TestAsajjVentressIC27_7:

    def _setup(self, repo):
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "IC27", "7"))
        _give_resources(state, "P0", 2)
        state.player_by_id("P0").resources[0].exhausted = True
        return state, asajj

    def test_IC27_7_action_attack_then_ready_a_resource_if_it_survived(self, repo):
        state, asajj = self._setup(repo)
        pal = _place(state, "P0", _unit("Pal", "51", power=3))
        state = _drive(_use_ability(state, asajj.instance_id),
                       _pick_class("AttackWithUnit", attacker_id=pal.instance_id,
                                   defender_id=None))
        assert state.player_by_id("P1").base_instance.damage == 3
        assert not any(r.exhausted for r in state.player_by_id("P0").resources)

    def test_IC27_7_no_ready_when_the_attacker_died(self, repo):
        state, asajj = self._setup(repo)
        pal = _place(state, "P0", _unit("Pal", "51", power=1, hp=1))
        wall = _place(state, "P1", _unit("Wall", "52", power=5, hp=9))
        state = _drive(_use_ability(state, asajj.instance_id),
                       _pick_class("AttackWithUnit", attacker_id=pal.instance_id,
                                   defender_id=wall.instance_id))
        assert state.find_instance(pal.instance_id)[1].zone.name == "DISCARD"
        assert sum(r.exhausted for r in state.player_by_id("P0").resources) == 1

    def test_IC27_7_deployed_on_attack_readies_a_resource(self, repo):
        state, asajj = _deploy(repo, "7", resources=6)
        ps = state.player_by_id("P0")
        for r in ps.resources:
            r.exhausted = True
        state = _attack(state, _live(state, asajj))
        assert sum(not r.exhausted for r in state.player_by_id("P0").resources) == 1


class TestNuteGunrayIC27_13:

    def test_IC27_13_other_separatists_gain_restore_1(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        nute = _place(state, "P0", _ic27(repo, "13"))
        sep = _place(state, "P0", _unit("Droid", "51", traits=("Separatist",)))
        other = _place(state, "P0", _unit("Rebel", "52", traits=("Rebel",)))
        assert keyword_value(state, _live(state, sep), Keyword.RESTORE) == 1
        assert keyword_value(state, _live(state, other), Keyword.RESTORE) == 0
        # "Each OTHER" — and the upstream Restore tag is a grant, not his own.
        assert keyword_value(state, _live(state, nute), Keyword.RESTORE) == 0


class TestGeneralGrievousIC27_21:

    def test_IC27_21_each_option_once_per_phase(self, repo):
        from tests.test_fortify import _upgrade_def
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        gg = _place(state, "P0", _ic27(repo, "21"))
        _stock_deck(state, "P0", 3)
        seen = []

        def _pick(state, acts):
            opts = [a.option_idx for a in acts if type(a).__name__ == "SelectModalOption"]
            if opts:
                seen.append(opts)
            return _pick_option(3)(state, acts) or _pick_option(1)(state, acts)

        state, _ = _play_from_hand(state, _upgrade_def("Kit", "1", fortify=False),
                                   host=gg, picker=_pick)
        assert len(state.player_by_id("P0").hand) == 1           # drew (option 3)
        state.active_player_index = 0
        state, _ = _play_from_hand(state, _upgrade_def("Kit2", "2", fortify=False),
                                   host=_live(state, gg), picker=_pick)
        assert seen == [[1, 2, 3], [1, 2]]                       # draw already used
        assert "Experience" in _token_names(state, gg)


class TestGrandMoffTarkinIC27_23:

    def test_IC27_23_friendly_sentinels_get_plus_1_plus_1(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        tarkin = _place(state, "P0", _ic27(repo, "23"))
        guard = _place(state, "P0", _unit("Guard", "51", power=2, hp=3,
                                           keywords=("Sentinel",)))
        plain = _place(state, "P0", _unit("Plain", "52", power=2, hp=3))
        foe = _place(state, "P1", _unit("FoeGuard", "53", power=2, hp=3,
                                         keywords=("Sentinel",)))
        assert (compute_power(state, _live(state, guard)),
                compute_hp(state, _live(state, guard))) == (3, 4)
        assert compute_power(state, _live(state, plain)) == 2
        assert compute_power(state, _live(state, foe)) == 2
        # No printed Sentinel (the upstream tag is sanitised), so no self-buff.
        assert compute_power(state, _live(state, tarkin)) == 3


# ── IC27_147 Asajj Ventress — FromHandAttackerSwap ───────────────────────────

def _asajj_setup(repo, resources=9):
    """P0 holds Asajj; a 2-power friendly unit is about to attack P1's base.
    ``_make_state``'s base has no aspects, so her price is 5 + 4 (two pips)."""
    state = _make_state()
    asajj = _hand(state, "P0", _ic27(repo, "147"))
    attacker = _place(state, "P0", _unit("Raider", "60", power=2, hp=3))
    _give_resources(state, "P0", resources)
    return state, asajj, attacker


def _swap_offer(state):
    from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
    acts = legal_actions(state)
    return (next((a for a in acts if isinstance(a, AcceptTrigger)), None),
            next((a for a in acts if isinstance(a, DeclineTrigger)), None))


def _start_base_attack(state, attacker):
    from swu.engine.actions import apply, AttackWithUnit
    attacker.exhausted = False
    return apply(state, AttackWithUnit(attacker.instance_id, None))


class TestAsajjVentressIC27_147:
    def test_IC27_147_swaps_in_and_deals_her_damage(self, repo):
        from swu.engine.actions import apply
        state, asajj, attacker = _asajj_setup(repo)
        state = _start_base_attack(state, attacker)
        accept, decline = _swap_offer(state)
        assert accept is not None and decline is not None
        state = _drive(apply(state, accept))
        p0, p1 = state.players
        assert p1.base_instance.damage == 5            # Asajj's power, not 2
        assert any(c.instance_id == attacker.instance_id for c in p0.hand)
        live = next(u for u in p0.ground_arena if u.instance_id == asajj.instance_id)
        assert live.exhausted
        assert all(r.exhausted for r in p0.resources)   # paid 5 + 4 penalty
        assert not any(c.instance_id == asajj.instance_id for c in p0.hand)

    def test_IC27_147_decline_keeps_the_original_attack(self, repo):
        from swu.engine.actions import apply
        state, asajj, attacker = _asajj_setup(repo)
        state = _start_base_attack(state, attacker)
        _, decline = _swap_offer(state)
        state = _drive(apply(state, decline))
        p0, p1 = state.players
        assert p1.base_instance.damage == 2
        assert any(c.instance_id == asajj.instance_id for c in p0.hand)
        assert not any(r.exhausted for r in p0.resources)

    def test_IC27_147_not_offered_when_unaffordable_or_vs_unit(self, repo):
        state, _, attacker = _asajj_setup(repo, resources=8)
        state = _start_base_attack(state, attacker)
        assert _swap_offer(state) == (None, None)
        assert state.players[1].base_instance.damage == 2
        # A unit attack is not "attacking a base".
        state, _, attacker = _asajj_setup(repo)
        foe = _place(state, "P1", _unit("Foe", "61", power=1, hp=5))
        attacker.exhausted = False
        from swu.engine.actions import apply, AttackWithUnit
        state = apply(state, AttackWithUnit(attacker.instance_id, foe.instance_id))
        assert _swap_offer(state) == (None, None)


# ── ic27-set:09 ───────────────────────────────────────────────────────────────

def _xp(state, ci, n=1, token="Experience"):
    """Attach ``n`` real token upgrades to ``ci`` through the engine."""
    from swu.abilities.registry import GiveToken, TargetSpec
    from swu.abilities.resolver import execute_effect
    return execute_effect(state, GiveToken(token, TargetSpec(), count=n), ci,
                          ci.instance_id, {})


def _n_tokens(state, ci, name="Experience"):
    return sum(1 for u in _live(state, ci).attached_upgrades
               if getattr(u.card_def, "name", None) == name)


def _pick_ids(*ids):
    """Accept optionals; choose targets from ``ids`` in order, each once."""
    queue = list(ids)

    def _pick(state, acts):
        from swu.engine.actions import AcceptTrigger, ChooseTarget
        for a in acts:
            if isinstance(a, AcceptTrigger):
                return a
        if queue:
            for a in acts:
                if isinstance(a, ChooseTarget) and a.target_id == queue[0]:
                    queue.pop(0)
                    return a
        return None
    return _pick


class TestGrandAdmiralThrawnIC27_24:
    def test_IC27_24_when_played_gives_xp_and_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        thrawn = _place(state, "P0", _ic27(repo, "24"))
        ally = _place(state, "P0", _unit("Ally", "62"))
        state = _drive(_fire_when_played(state, thrawn), _pick_ids(ally.instance_id))
        assert _n_tokens(state, ally) == 1
        assert has_keyword(state, _live(state, ally), Keyword.SENTINEL)
        assert _n_tokens(state, thrawn) == 0


class TestChimaeraIC27_29:
    def test_IC27_29_xp_per_upgrade_then_heal_per_upgrade(self, repo):
        state = _make_state()
        a = _place(state, "P0", _unit("A", "63"))
        b = _place(state, "P0", _unit("B", "64"))
        state = _xp(state, a, 2)                     # a: 2 upgrades -> +2 XP
        state.players[0].base_instance.damage = 10
        chim = _place(state, "P0", _ic27(repo, "29"), arena="space")
        state = _drive(_fire_when_played(state, chim))
        assert _n_tokens(state, a) == 4
        assert _n_tokens(state, b) == 0
        # 4 friendly upgrades after the tokens -> heal 4.
        assert state.players[0].base_instance.damage == 6


class TestObiWansInterceptorIC27_34:
    def test_IC27_34_other_republic_units_get_plus_hp(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        inter = _place(state, "P0", _ic27(repo, "34"), arena="space")
        rep = _place(state, "P0", _unit("Rep", "65", hp=3, traits=("Republic",)))
        other = _place(state, "P0", _unit("Other", "66", hp=3))
        assert compute_hp(state, _live(state, rep)) == 4
        assert compute_hp(state, _live(state, other)) == 3
        assert compute_hp(state, _live(state, inter)) == 3


class TestFinnIC27_37:
    def test_IC27_37_restore_2_only_while_upgraded(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        finn = _place(state, "P0", _ic27(repo, "37"))
        assert keyword_value(state, _live(state, finn), Keyword.RESTORE) == 0
        state = _xp(state, finn)
        assert keyword_value(state, _live(state, finn), Keyword.RESTORE) == 2


class TestRoseTicoIC27_40:
    def test_IC27_40_on_attack_shields_another_resistance_unit(self, repo):
        state = _make_state()
        rose = _place(state, "P0", _ic27(repo, "40"))
        res = _place(state, "P0", _unit("Res", "67", traits=("Resistance",)))
        _place(state, "P0", _unit("NotRes", "68"))
        state = _attack(state, rose, picker=_pick_ids(res.instance_id))
        assert _n_tokens(state, res, "Shield") == 1


class TestQiraIC27_45:
    def test_IC27_45_xp_on_play_then_passed_on_at_defeat(self, repo):
        state = _make_state()
        qira = _place(state, "P0", _ic27(repo, "45"))
        heir = _place(state, "P0", _unit("Heir", "69"))
        state = _drive(_fire_when_played(state, qira))
        assert _n_tokens(state, qira) == 2
        state = _drive(_defeat(state, _live(state, qira)), _pick_ids(heir.instance_id))
        assert _n_tokens(state, heir) == 2


class TestVigilantDefenseIC27_46:
    def test_IC27_46_buff_heal_and_defeat(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from swu.engine.actions import compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        mine = _place(state, "P0", _unit("Mine", "70", hp=5))
        hurt = _place(state, "P0", _unit("Hurt", "71", hp=6))
        hurt.damage = 4
        weak = _place(state, "P1", _unit("Weak", "72", hp=5))
        weak.damage = 2                                  # 3 HP left
        _place(state, "P1", _unit("Tough", "73", hp=5))  # 5 left: not a target
        state, _ = _play_event_from_hand(state, repo, "IC27", "46")
        state = _drive(state, _pick_ids(mine.instance_id, hurt.instance_id,
                                        weak.instance_id))
        assert compute_hp(state, _live(state, mine)) == 8
        assert has_keyword(state, _live(state, mine), Keyword.SENTINEL)
        assert _live(state, hurt).damage == 1
        assert all(u.instance_id != weak.instance_id
                   for u in state.players[1].ground_arena)


# ── ic27-set:10 ───────────────────────────────────────────────────────────────

class TestDexterJettsterIC27_49:
    def test_IC27_49_pay_1_to_look_at_top_3(self, repo):
        from swu.engine.actions import apply, legal_actions, AcceptTrigger
        state = _make_state()
        dex = _place(state, "P0", _ic27(repo, "49"))
        _stock_deck(state, "P0", 4)
        _give_resources(state, "P0", 1)
        dex.exhausted = False
        from swu.engine.actions import AttackWithUnit
        state = apply(state, AttackWithUnit(dex.instance_id, None))
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        while state.pending_decisions[-1].kind == "resolve_effects":
            state = apply(state, legal_actions(state)[0])
        assert state.pending_decisions[-1].kind == "reveal_top"
        assert all(r.exhausted for r in state.players[0].resources)
        state = _drive(state)
        assert len(state.players[0].deck) == 4

    def test_IC27_49_not_offered_without_a_ready_resource(self, repo):
        from swu.engine.actions import apply, legal_actions, AcceptTrigger, AttackWithUnit
        state = _make_state()
        dex = _place(state, "P0", _ic27(repo, "49"))
        _stock_deck(state, "P0", 4)
        dex.exhausted = False
        state = apply(state, AttackWithUnit(dex.instance_id, None))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestAllegiantGeneralPrydeIC27_56:
    def test_IC27_56_when_defeated_xp_to_strongest(self, repo):
        state = _make_state()
        pryde = _place(state, "P0", _ic27(repo, "56"))
        small = _place(state, "P0", _unit("Small", "74", power=1))
        big = _place(state, "P0", _unit("Big", "75", power=5))
        state = _drive(_defeat(state, _live(state, pryde)))
        assert _n_tokens(state, big) == 1
        assert _n_tokens(state, small) == 0


class TestJabbaTheHuttIC27_60:
    def test_IC27_60_attacker_gets_plus_4_vs_marked_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        jabba = _place(state, "P0", _ic27(repo, "60"))
        hitter = _place(state, "P0", _unit("Hitter", "76", power=2, hp=9))
        marked = _place(state, "P1", _unit("Marked", "77", power=1, hp=9))
        other = _place(state, "P1", _unit("Other", "78", power=1, hp=9))
        state = _drive(_use_ability(state, jabba.instance_id),
                       _pick_ids(marked.instance_id))
        assert _live(state, jabba).exhausted
        h = _live(state, hitter)
        assert compute_power(state, h, is_attacking=True, attacking_unit=True,
                             defender_id=marked.instance_id) == 6
        assert compute_power(state, h, is_attacking=True, attacking_unit=True,
                             defender_id=other.instance_id) == 2
        state.active_player_index = 0          # the action passed the turn
        state = _attack(state, _live(state, hitter), _live(state, marked))
        assert _live(state, marked).damage == 6


class TestAdmiralMottiIC27_62:
    def test_IC27_62_on_attack_xp_to_other_imperials(self, repo):
        state = _make_state()
        motti = _place(state, "P0", _ic27(repo, "62"))
        imp = _place(state, "P0", _unit("Imp", "79", traits=("Imperial",)))
        reb = _place(state, "P0", _unit("Reb", "80", traits=("Rebel",)))
        state = _attack(state, motti)
        assert _n_tokens(state, imp) == 1
        assert _n_tokens(state, reb) == 0
        assert _n_tokens(state, motti) == 0


class TestDarthVaderIC27_67:
    def test_IC27_67_other_friendly_units_gain_ambush(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _place(state, "P0", _ic27(repo, "67"))
        ally = _place(state, "P0", _unit("Ally", "81"))
        foe = _place(state, "P1", _unit("Foe", "82"))
        assert has_keyword(state, _live(state, ally), Keyword.AMBUSH)
        assert not has_keyword(state, _live(state, foe), Keyword.AMBUSH)


class TestAvarKrissIC27_71:
    def test_IC27_71_raid_grows_with_other_friendly_units(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        avar = _place(state, "P0", _ic27(repo, "71"))
        base_raid = keyword_value(state, _live(state, avar), Keyword.RAID)
        _place(state, "P0", _unit("A", "83"))
        _place(state, "P0", _unit("B", "84"), arena="space")
        _place(state, "P1", _unit("Foe", "85"))
        assert keyword_value(state, _live(state, avar), Keyword.RAID) == base_raid + 2


class TestCloneCommanderCodyIC27_76:
    def test_IC27_76_republic_unit_entering_gets_xp(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        cody = _place(state, "P0", _ic27(repo, "76"))
        state, rep = _play_from_hand(state, _unit("Rep", "86", cost=1,
                                                  traits=("Republic",)))
        state, plain = _play_from_hand(state, _unit("Plain", "87", cost=1))
        assert _n_tokens(state, rep) == 1
        assert _n_tokens(state, plain) == 0
        assert _n_tokens(state, cody) == 0


# ── ic27-set:11 ───────────────────────────────────────────────────────────────

class TestMazKanataIC27_89:

    @staticmethod
    def _regroup(state):
        from swu.engine.state import Phase
        state.phase = Phase.REGROUP
        state.active_player_index = 0
        for ps in state.players:
            ps.regroup_done = False
        return state

    def test_IC27_89_regroup_resource_gives_experience(self, repo):
        from swu.engine.actions import apply, ResourceCard
        state = self._regroup(_make_state())
        maz = _place(state, "P0", _ic27(repo, "89"))
        card = _hand(state, "P0", _unit("Filler", "901", cost=1))
        state = apply(state, ResourceCard(card.instance_id))
        assert _n_tokens(state, maz) == 1
        assert not state.game_memory.resource_events

    def test_IC27_89_opponent_resourcing_does_not_fire(self, repo):
        from swu.engine.actions import apply, ResourceCard
        state = self._regroup(_make_state())
        maz = _place(state, "P0", _ic27(repo, "89"))
        state.player_by_id("P0").regroup_done = True
        state.active_player_index = 1
        card = _hand(state, "P1", _unit("Filler", "902", cost=1))
        state = apply(state, ResourceCard(card.instance_id))
        assert _n_tokens(state, maz) == 0

    def test_IC27_89_action_phase_ramp_gives_experience(self, repo):
        from tests.test_hmw_cards import _decline_all
        state = _make_state()
        maz = _place(state, "P0", _ic27(repo, "89"))
        neg = _place(state, "P0", _ic27(repo, "84"), arena="space")
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P0", 2)
        state = _attack(state, _live(state, neg), picker=_decline_all)
        assert len(state.player_by_id("P0").resources) == 3
        assert _n_tokens(state, maz) == 1


class TestIC27Group12:

    def test_IC27_92_when_played_may_resource_top_card(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        _stock_deck(state, "P0", 3)
        state, _ = _play_from_hand(state, _ic27(repo, "92"), picker=_accept_and_target())
        ps = state.player_by_id("P0")
        assert len(ps.resources) == 13 and len(ps.deck) == 2

    def test_IC27_99_when_defeated_readies_an_imperial_unit(self, repo):
        state = _make_state()
        eighth = _place(state, "P0", _ic27(repo, "99"))
        ally = _place(state, "P0", _unit("Officer", "910", traits=("Imperial",)))
        rebel = _place(state, "P0", _unit("Rebel", "911", traits=("Rebel",)))
        ally.exhausted = rebel.exhausted = True
        foe = _place(state, "P1", _unit("Wall", "912", power=3, hp=9))
        offered = []

        def pick(st, acts):
            from swu.engine.actions import ChooseTarget
            offered.extend(a.target_id for a in acts if isinstance(a, ChooseTarget))
            return _accept_and_target(ally.instance_id)(st, acts)
        state = _attack(state, _live(state, eighth), foe, picker=pick)
        assert state.find_instance(eighth.instance_id)[1].zone.name == "DISCARD"
        assert not _live(state, ally).exhausted and _live(state, rebel).exhausted
        assert rebel.instance_id not in offered

    def test_IC27_101_other_first_order_units_get_plus1_and_overwhelm(self, repo):
        from tests.test_hmw_cards import _power, _kw
        state = _make_state()
        hux = _place(state, "P0", _ic27(repo, "101"))
        fo = _place(state, "P0", _unit("Trooper", "913", traits=("First Order",)))
        other = _place(state, "P0", _unit("Pilot", "914", traits=("Resistance",)))
        assert _power(state, fo) == 3 and _kw(state, fo, "Overwhelm")
        assert _power(state, other) == 2 and not _kw(state, other, "Overwhelm")
        assert _power(state, hux) == 3

    def test_IC27_103_damaged_gains_raid_3_and_saboteur(self, repo):
        from swu.engine.keywords import Keyword, keyword_value
        from tests.test_hmw_cards import _kw
        state = _make_state()
        gi = _place(state, "P0", _ic27(repo, "103"))
        assert not _kw(state, gi, "Saboteur") and not _kw(state, gi, "Raid")
        _live(state, gi).damage = 1
        assert _kw(state, gi, "Saboteur")
        assert keyword_value(state, _live(state, gi), Keyword.RAID) == 3

    def test_IC27_106_readies_only_after_first_attack(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        from tests.test_hmw_cards import _drive
        state = _make_state()
        kylo = _place(state, "P0", _ic27(repo, "106"))
        state = _attack(state, _live(state, kylo))
        assert not _live(state, kylo).exhausted
        state.active_player_index = 0
        state = _drive(apply(state, AttackWithUnit(kylo.instance_id, None)))
        assert _live(state, kylo).exhausted

    def test_IC27_115_gets_plus1_when_another_resistance_card_played(self, repo):
        from tests.test_hmw_cards import _play_from_hand, _power
        state = _make_state()
        poe = _place(state, "P0", _ic27(repo, "115"))
        state, _ = _play_from_hand(state, _unit("Other", "915", traits=("Rebel",)))
        assert _power(state, poe) == 2
        state.active_player_index = 0
        state, _ = _play_from_hand(state, _unit("Ally", "916", traits=("Resistance",)))
        assert _power(state, poe) == 3

    def test_IC27_120_action_discards_pays_1_and_attacks_with_plus2(self, repo):
        from tests.test_hmw_cards import _use_ability, _drive
        state = _make_state()
        rey = _place(state, "P0", _ic27(repo, "120"))
        hitter = _place(state, "P0", _unit("Hitter", "917", power=2, hp=5))
        _hand(state, "P0", _unit("Fodder", "918"))
        _give_resources(state, "P0", 1)
        state.active_player_index = 0
        base_before = state.player_by_id("P1").base_instance.damage
        state = _use_ability(state, rey.instance_id)

        def pick(st, acts):
            for a in acts:
                if (getattr(a, "attacker_id", None) == hitter.instance_id
                        or getattr(a, "target_id", None) == hitter.instance_id):
                    return a
            return None
        state = _drive(state, pick)
        ps = state.player_by_id("P0")
        assert not ps.hand and len(ps.discard) == 1
        assert state.player_by_id("P1").base_instance.damage - base_before == 4
        assert _live(state, hitter).exhausted and not _live(state, rey).exhausted


class TestIC27Group13:

    def test_IC27_123_readies_up_to_3_within_cost_7_with_saboteur(self, repo):
        from swu.engine.actions import SelectUnitToExhaustCombined
        from tests.test_hmw_cards import _play_from_hand, _kw
        state = _make_state()
        a = _place(state, "P0", _unit("A", "920", cost=3))
        b = _place(state, "P0", _unit("B", "921", cost=4))
        c = _place(state, "P0", _unit("C", "922", cost=2))
        for u in (a, b, c):
            u.exhausted = True
        order = [b.instance_id, a.instance_id, c.instance_id]
        seen = []

        def pick(st, acts):
            ids = [x.target_id for x in acts if isinstance(x, SelectUnitToExhaustCombined)]
            seen.append(ids)
            for want in order:
                if want in ids:
                    return next(x for x in acts if getattr(x, "target_id", None) == want)
            return None
        state, _ = _play_from_hand(state, _ic27(repo, "123"), picker=pick)
        assert not _live(state, b).exhausted and not _live(state, a).exhausted
        assert _live(state, c).exhausted          # 4 + 3 = 7 leaves no budget
        assert _kw(state, a, "Saboteur") and _kw(state, b, "Saboteur")
        assert not _kw(state, c, "Saboteur")
        assert c.instance_id in seen[0]

    def test_IC27_131_ramps_only_when_behind_on_resources(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P1", 20)
        state, _ = _play_from_hand(state, _ic27(repo, "131"), picker=_accept_and_target())
        assert len(state.player_by_id("P0").resources) == 13

    def test_IC27_137_on_attack_exhausts_the_defender(self, repo):
        state = _make_state()
        kintan = _place(state, "P0", _ic27(repo, "137"))
        foe = _place(state, "P1", _unit("Foe", "923", power=1, hp=9))
        state = _attack(state, _live(state, kintan), foe)
        assert _live(state, foe).exhausted

    def test_IC27_139_exhausts_to_play_an_event_for_1_less(self, repo):
        from tests.test_hmw_cards import _offers_ability
        from swu.engine.actions import legal_actions, apply, PlayEventFromHand, _play_cost
        from tests.test_hmw_cards import _use_ability
        state = _make_state()
        bib = _place(state, "P0", _ic27(repo, "139"))
        state.active_player_index = 0
        assert not _offers_ability(state, bib.instance_id)   # no event in hand
        ev = _hand(state, "P0", _get_card(repo, "SOR", "171"))  # Mission Briefing, 3
        _stock_deck(state, "P0", 3)
        _give_resources(state, "P0", 10)
        before = state.player_by_id("P0").available_resources
        expected = max(0, _play_cost(state, ev, state.player_by_id("P0")) - 1)
        state = _use_ability(state, bib.instance_id)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayEventFromHand) and a.instance_id == ev.instance_id)
        state = apply(state, play)
        ps = state.player_by_id("P0")
        assert _live(state, bib).exhausted
        assert any(c.instance_id == ev.instance_id for c in ps.discard)
        assert before - ps.available_resources == expected

    def test_IC27_143_when_played_may_attack_with_a_unit(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        hitter = _place(state, "P0", _unit("Hitter", "924", power=3, hp=5))

        def pick(st, acts):
            from swu.engine.actions import AcceptTrigger
            for x in acts:
                if isinstance(x, AcceptTrigger) or getattr(x, "attacker_id", None) == hitter.instance_id:
                    return x
            return None
        state, _ = _play_from_hand(state, _ic27(repo, "143"), picker=pick)
        assert state.player_by_id("P1").base_instance.damage == 3

    def test_IC27_146_readies_2_resources_when_defender_defeated(self, repo):
        state = _make_state()
        boba = _place(state, "P0", _ic27(repo, "146"))
        _give_resources(state, "P0", 3)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        weak = _place(state, "P1", _unit("Weak", "925", power=1, hp=2))
        state = _attack(state, _live(state, boba), weak)
        ready = [r for r in state.player_by_id("P0").resources if not r.exhausted]
        assert len(ready) == 2

    def test_IC27_148_caps_opponent_regroup_ready_and_may_exhaust(self, repo):
        from swu.engine.actions.turn import _ready_all_cards
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "926"))
        state, dooku = _play_from_hand(state, _ic27(repo, "148"),
                                       picker=_pick_ids(foe.instance_id))
        assert _live(state, foe).exhausted
        big = _place(state, "P1", _unit("Big", "927", cost=6))
        small = _place(state, "P1", _unit("Small", "928", cost=1))
        ship = _place(state, "P1", _unit("Ship", "929", cost=2), arena="space")
        mine = _place(state, "P0", _unit("Mine", "930"))
        for u in (big, small, ship, mine):
            u.exhausted = True
        _ready_all_cards(state)
        assert not _live(state, big).exhausted and not _live(state, ship).exhausted
        assert _live(state, small).exhausted and _live(state, foe).exhausted
        assert not _live(state, mine).exhausted


class TestIC27Group14:

    def test_IC27_150_exhausts_host_and_it_cannot_ready(self, repo):
        from swu.engine.actions.turn import _ready_all_cards
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "940"))
        state, _ = _play_from_hand(state, _ic27(repo, "150"), host=foe)
        assert _live(state, foe).exhausted
        _ready_all_cards(state)
        assert _live(state, foe).exhausted

    def test_IC27_159_exhausts_up_to_2_in_the_same_arena(self, repo):
        from swu.engine.actions import SelectUnitToExhaustCombined
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        g1 = _place(state, "P1", _unit("G1", "941", cost=2))
        g2 = _place(state, "P1", _unit("G2", "942", cost=2))
        sp = _place(state, "P1", _unit("Sp", "943", cost=1), arena="space")
        offered_after_first = []

        def pick(st, acts):
            ids = [x.target_id for x in acts if isinstance(x, SelectUnitToExhaustCombined)]
            if not ids:
                return None
            if st.pending_decisions[-1].context["chosen"]:
                offered_after_first.extend(ids)
            want = g1.instance_id if g1.instance_id in ids else g2.instance_id
            return next(x for x in acts if getattr(x, "target_id", None) == want)
        state, _ = _play_from_hand(state, _ic27(repo, "159"), picker=pick)
        assert _live(state, g1).exhausted and _live(state, g2).exhausted
        assert not _live(state, sp).exhausted
        assert sp.instance_id not in offered_after_first

    def test_IC27_160_other_rebels_gain_raid_2_and_saboteur(self, repo):
        from swu.engine.keywords import Keyword, keyword_value
        from tests.test_hmw_cards import _kw
        state = _make_state()
        tantive = _place(state, "P0", _ic27(repo, "160"), arena="space")
        rebel = _place(state, "P0", _unit("Rebel", "944", traits=("Rebel",)))
        other = _place(state, "P0", _unit("Other", "945", traits=("Imperial",)))
        assert _kw(state, rebel, "Saboteur")
        assert keyword_value(state, _live(state, rebel), Keyword.RAID) == 2
        assert not _kw(state, other, "Saboteur") and not _kw(state, tantive, "Saboteur")

    def test_IC27_162_damaged_gets_plus_4_power(self, repo):
        from tests.test_hmw_cards import _power
        state = _make_state()
        chewie = _place(state, "P0", _ic27(repo, "162"))
        assert _power(state, chewie) == 4
        _live(state, chewie).damage = 1
        assert _power(state, chewie) == 8

    def test_IC27_175_attacks_with_plus1_and_strikes_first(self, repo):
        from tests.test_sor_cards import _play_event_from_hand
        from tests.test_hmw_cards import _drive
        state = _make_state()
        hitter = _place(state, "P0", _unit("Hitter", "946", power=2, hp=1))
        foe = _place(state, "P1", _unit("Foe", "947", power=5, hp=3))
        state, _ = _play_event_from_hand(state, repo, "IC27", "175", resources=5)

        def pick(st, acts):
            for x in acts:
                if getattr(x, "attacker_id", None) == hitter.instance_id and \
                        getattr(x, "defender_id", None) == foe.instance_id:
                    return x
                if getattr(x, "target_id", None) in (hitter.instance_id, foe.instance_id):
                    return x
            return None
        state = _drive(state, pick)
        assert state.find_instance(foe.instance_id)[1].zone.name == "DISCARD"
        assert state.find_instance(hitter.instance_id)[1].zone.name == "GROUND_ARENA"


class TestIC27Group15:

    def test_IC27_19_chosen_enemy_ground_unit_gets_minus3_while_in_play(self, repo):
        from tests.test_hmw_cards import _play_from_hand, _power
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "950", power=5))
        state, soulless = _play_from_hand(state, _ic27(repo, "19"),
                                          picker=_pick_ids(foe.instance_id))
        assert _power(state, foe) == 2
        ps = state.player_by_id("P0")
        ps.space_arena = [c for c in ps.space_arena if c.instance_id != soulless.instance_id]
        assert _power(state, foe) == 5

    def test_IC27_22_costs_2_less_after_a_friendly_unit_died(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        gideon = _hand(state, "P0", _ic27(repo, "22"))
        ps = state.player_by_id("P0")
        full = _play_cost(state, gideon, ps)
        doomed = _place(state, "P0", _unit("Doomed", "951", hp=1))
        foe = _place(state, "P1", _unit("Foe", "952", power=3, hp=9))
        state = _attack(state, _live(state, doomed), foe)
        state.active_player_index = 0
        ps = state.player_by_id("P0")
        live_gideon = next(c for c in ps.hand if c.instance_id == gideon.instance_id)
        assert _play_cost(state, live_gideon, ps) == full - 2

    def test_IC27_35_prevents_combat_damage_to_and_by_chosen_enemy(self, repo):
        state = _make_state()
        yoda = _place(state, "P0", _ic27(repo, "35"))
        foe = _place(state, "P1", _unit("Foe", "953", power=9, hp=3))
        state = _attack(state, _live(state, yoda), foe,
                        picker=_pick_ids(foe.instance_id))
        assert _live(state, foe).damage == 0
        assert _live(state, yoda).damage == 0

    def test_IC27_43_opponent_cards_cost_3_more_while_exhausted(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        raddus = _place(state, "P0", _ic27(repo, "43"), arena="space")
        card = _hand(state, "P1", _unit("Theirs", "954", cost=2))
        ps1 = state.player_by_id("P1")
        raddus.exhausted = False
        ready_cost = _play_cost(state, card, ps1)
        raddus.exhausted = True
        assert _play_cost(state, card, ps1) == ready_cost + 3
        mine = _hand(state, "P0", _unit("Mine", "955", cost=2))
        assert _play_cost(state, mine, state.player_by_id("P0")) <= ready_cost

    def test_IC27_57_plays_a_7_plus_unit_for_2_less(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        from tests.test_hmw_cards import _offers_ability, _use_ability
        state = _make_state()
        krennic = _place(state, "P0", _ic27(repo, "57"))
        small = _hand(state, "P0", _unit("Small", "956", cost=3))
        state.active_player_index = 0
        _give_resources(state, "P0", 10)
        assert not _offers_ability(state, krennic.instance_id)
        big = _hand(state, "P0", _unit("Big", "957", cost=7))
        state = _use_ability(state, krennic.instance_id)
        offered = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert offered == {big.instance_id} and small.instance_id not in offered

    def test_IC27_68_searches_top_5_for_villainy_unit_played_free(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        villain = _with_aspect(_unit("Villain", "958", cost=12), "Villainy")
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id("P0")
        ps.deck = [CardInstance(f"P0_dk_{i}", _unit("Filler", f"96{i}"), "P0", Zone.DECK)
                   for i in range(4)]
        ps.deck.insert(2, CardInstance("P0_villain", villain, "P0", Zone.DECK))
        state, _ = _play_from_hand(state, _ic27(repo, "68"), resources=20,
                                   picker=_pick_ids("P0_villain"))
        assert any(c.instance_id == "P0_villain"
                   for c in state.player_by_id("P0").ground_arena)

    def test_IC27_104_players_with_4_plus_cards_discard_one(self, repo):
        state = _make_state()
        tie = _place(state, "P0", _ic27(repo, "104"), arena="space")
        for i in range(4):
            _hand(state, "P0", _unit("Mine", f"97{i}"))
        for i in range(3):
            _hand(state, "P1", _unit("Theirs", f"98{i}"))
        state = _attack(state, _live(state, tie))
        assert len(state.player_by_id("P0").hand) == 3
        assert len(state.player_by_id("P1").hand) == 3


class TestIC27Group16:

    def test_IC27_113_gives_another_heroism_unit_raid_2(self, repo):
        from swu.engine.keywords import Keyword, keyword_value
        state = _make_state()
        ezra = _place(state, "P0", _ic27(repo, "113"))
        hero = _place(state, "P0", _with_aspect(_unit("Hero", "990"), "Heroism"))
        state = _attack(state, _live(state, ezra), picker=_pick_ids(hero.instance_id))
        assert keyword_value(state, _live(state, hero), Keyword.RAID) == 2

    def test_IC27_126_may_double_another_units_power(self, repo):
        from tests.test_hmw_cards import _power
        state = _make_state()
        saw = _place(state, "P0", _ic27(repo, "126"))
        ally = _place(state, "P0", _unit("Ally", "991", power=3))
        state = _attack(state, _live(state, saw), picker=_pick_ids(ally.instance_id))
        assert _power(state, ally) == 6

    def test_IC27_138_may_put_a_non_unit_on_top(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        banshee = _place(state, "P0", _ic27(repo, "138"), arena="space")
        ev = _get_card(repo, "SOR", "171")
        ps = state.player_by_id("P0")
        ps.deck = [CardInstance(f"P0_dk_{i}", _unit("Filler", f"99{i}"), "P0", Zone.DECK)
                   for i in range(4)]
        ps.deck.insert(3, CardInstance("P0_event", ev, "P0", Zone.DECK))

        def pick(st, acts):
            for a in acts:
                if any(getattr(a, f, None) == "P0_event"
                       for f in ("instance_id", "card_id", "target_id")):
                    return a
            return None
        state = _attack(state, _live(state, banshee), picker=pick)
        assert state.player_by_id("P0").deck[0].instance_id == "P0_event"

    def test_IC27_142_deals_combat_damage_last(self, repo):
        state = _make_state()
        greedo = _place(state, "P0", _ic27(repo, "142"))      # 5/3
        foe = _place(state, "P1", _unit("Foe", "992", power=3, hp=5))
        state = _attack(state, _live(state, greedo), foe)
        # The defender strikes first and defeats Greedo, who deals nothing back.
        assert state.find_instance(greedo.instance_id)[1].zone.name == "DISCARD"
        assert _live(state, foe).damage == 0

    def test_IC27_149_next_card_costs_9_less(self, repo):
        from swu.engine.actions import _play_cost
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        big = _hand(state, "P0", _unit("Big", "993", cost=10))
        full = _play_cost(state, big, state.player_by_id("P0"))
        state, _ = _play_from_hand(state, _ic27(repo, "149"), resources=20)
        ps = state.player_by_id("P0")
        live_big = next(c for c in ps.hand if c.instance_id == big.instance_id)
        assert _play_cost(state, live_big, ps) == full - 9

    def test_IC27_157_exhausted_defender_gets_minus_4(self, repo):
        state = _make_state()
        mando = _place(state, "P0", _ic27(repo, "157"))       # 5/3
        foe = _place(state, "P1", _unit("Foe", "994", power=4, hp=9))
        foe.exhausted = True
        state = _attack(state, _live(state, mando), foe)
        assert _live(state, mando).damage == 0
        assert _live(state, foe).damage == 5

    def test_IC27_161_defender_gets_minus_2(self, repo):
        state = _make_state()
        han = _place(state, "P0", _ic27(repo, "161"))         # 4/6
        foe = _place(state, "P1", _unit("Foe", "995", power=3, hp=9))
        state = _attack(state, _live(state, han), foe)
        assert _live(state, han).damage == 1


class TestIC27Group17:

    def test_IC27_163_each_enemy_unit_gets_minus_7(self, repo):
        from tests.test_hmw_cards import _play_from_hand, _power
        state = _make_state()
        foe = _place(state, "P1", _unit("Foe", "1001", power=9))
        ship = _place(state, "P1", _unit("Ship", "1002", power=3), arena="space")
        mine = _place(state, "P0", _unit("Mine", "1003", power=2))
        state, _ = _play_from_hand(state, _ic27(repo, "163"))
        assert _power(state, foe) == 2 and _power(state, ship) == 0
        assert _power(state, mine) == 2

    def test_IC27_165_bottoms_enemy_unit_and_its_owner_draws_2(self, repo):
        from tests.test_hmw_cards import _play_from_hand
        state = _make_state()
        _stock_deck(state, "P1", 3)
        foe = _place(state, "P1", _unit("Foe", "1004"))
        state, _ = _play_from_hand(state, _ic27(repo, "165"),
                                   picker=_pick_ids(foe.instance_id))
        p1 = state.player_by_id("P1")
        assert p1.deck[-1].instance_id == foe.instance_id
        assert len(p1.hand) == 2 and not p1.ground_arena

    def test_IC27_172_units_lose_when_defeated_abilities(self, repo):
        def run(with_crest):
            state = _make_state()
            if with_crest:
                _place(state, "P0", _ic27(repo, "172"), arena="space")
            dying = _place(state, "P0", _ic27(repo, "56"))   # When Defeated: Experience
            ally = _place(state, "P0", _unit("Ally", "1005", power=6, hp=9))
            foe = _place(state, "P1", _unit("Foe", "1006", power=9, hp=9))
            state = _attack(state, _live(state, dying), foe)
            return _n_tokens(state, ally)
        assert run(False) == 1
        assert run(True) == 0


class TestMonMothmaIC27_77:
    def test_IC27_77_exhausted_ally_attacks_unit_with_overwhelm(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        mon = _place(state, "P0", _ic27(repo, "77"))
        ally = _place(state, "P0", _unit("Ally", "88", power=5, hp=5))
        ally.exhausted = True
        foe = _place(state, "P1", _unit("Foe", "89", power=1, hp=1))
        state = _fire_when_played(state, mon)
        attacks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        assert attacks and all(a.defender_id is not None for a in attacks)
        assert all(a.attacker_id != mon.instance_id for a in attacks)
        pick = next(a for a in attacks if a.attacker_id == ally.instance_id
                    and a.defender_id == foe.instance_id)
        from swu.engine.actions import apply
        state = _drive(apply(state, pick))
        assert state.players[1].base_instance.damage == 4   # Overwhelm excess


class TestQuiGonJinnIC27_79:
    def test_IC27_79_another_friendly_unit_plus_2_2(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        qgj = _place(state, "P0", _ic27(repo, "79"))
        ally = _place(state, "P0", _unit("Ally", "90", power=1, hp=1))
        state = _drive(_fire_when_played(state, qgj), _pick_ids(ally.instance_id))
        a = _live(state, ally)
        assert (compute_power(state, a), compute_hp(state, a)) == (3, 3)


class TestMaceWinduIC27_81:
    def test_IC27_81_on_attack_xp_to_self(self, repo):
        state = _make_state()
        mace = _place(state, "P0", _ic27(repo, "81"))
        state = _attack(state, mace)
        assert _n_tokens(state, mace) == 1
        assert state.players[1].base_instance.damage == 6


class TestPadmeAmidalaIC27_83:
    def test_IC27_83_other_heroism_units_plus_3_3(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        padme = _place(state, "P0", _ic27(repo, "83"))
        hero = _place(state, "P0", _with_aspect(_unit("Hero", "91", power=1),
                                                "Heroism"))
        plain = _place(state, "P0", _unit("Plain", "92", power=1))
        assert compute_power(state, _live(state, hero)) == 4
        assert compute_power(state, _live(state, plain)) == 1
        assert compute_power(state, _live(state, padme)) == 5


class TestInspiringMentorIC27_85:
    def test_IC27_85_on_attack_and_when_defeated_give_xp(self, repo):
        from tests.test_hmw_cards import _attach
        state = _make_state()
        host = _place(state, "P0", _unit("Host", "93", power=1, hp=9))
        _attach(state, host, _ic27(repo, "85"))
        other = _place(state, "P0", _unit("Other", "94"))
        state = _attack(state, host, picker=_pick_ids(other.instance_id))
        assert _n_tokens(state, other) == 1
        state = _drive(_defeat(state, _live(state, host)),
                       _pick_ids(other.instance_id))
        assert _n_tokens(state, other) == 2


class TestEnfysNestIC27_86:
    def _fight(self, repo, foe_cost):
        state = _make_state()
        enfys = _place(state, "P0", _ic27(repo, "86"))
        foe = _place(state, "P1", _unit("Foe", "95", power=0, hp=3, cost=foe_cost))
        state = _attack(state, enfys, foe)
        return state.players[1].base_instance.damage

    def test_IC27_86_plus_2_and_overwhelm_vs_cheap_unit(self, repo):
        assert self._fight(repo, 3) == 3      # 6 power - 3 HP spills over
        assert self._fight(repo, 4) == 0      # 4 power, no Overwhelm

