"""TS26 card ability tests — the 2026 two-player starter set.

Method names embed the set+number so the encoding verifier's ``-k`` gate selects
them.  Reuses the DB-backed helpers from the SOR/SHD card tests.

⚠️ TS26 prints tokens at numbers 1–4, so a LEADER at one of those numbers must be
fetched with ``_get_leader`` (the by-type fetch) — plain ``_get_card`` may return
the token row.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _get_leader, _make_state, _place, _place_leader,
    _fire_when_played, _fire_when_defeated, _fire_on_attack, _find_instance,
    _give_resources, _play_event_from_hand, _push_deck_top,
)
from tests.test_shd_cards import _put_in_hand


def _drive(state, picker=None, limit=40):
    """Apply actions until nothing is pending (first legal action unless picked)."""
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while state.pending_decisions and guard < limit:
        guard += 1
        acts = legal_actions(state)
        choice = picker(state, acts) if picker else None
        state = apply(state, choice or acts[0])
    return state


def _accept_and_target(target_ci=None):
    from swu.engine.actions import AcceptTrigger, ChooseTarget

    def _pick(state, acts):
        for a in acts:
            if isinstance(a, AcceptTrigger):
                return a
        chooses = [a for a in acts if isinstance(a, ChooseTarget)
                   and getattr(a, "target_id", None)]
        if chooses:
            if target_ci is not None:
                for a in chooses:
                    if a.target_id == target_ci.instance_id:
                        return a
            return chooses[0]
        return None
    return _pick


def _decline_triggers():
    """Picker that declines every optional trigger / target it is offered."""
    from swu.engine.actions import DeclineTrigger, ChooseTarget

    def _pick(state, acts):
        for a in acts:
            if isinstance(a, DeclineTrigger):
                return a
        for a in acts:
            if isinstance(a, ChooseTarget) and getattr(a, "target_id", None) is None:
                return a
        return None
    return _pick


def _drive_event(state, repo, set_code, number):
    """Play an event from hand and drive to quiescence, returning (state, event)."""
    state, ev = _play_event_from_hand(state, repo, set_code, number)
    return _drive(state), ev


def _set_base(state, pid, base_def):
    """Swap in a real Base card for a player (``_make_state`` builds a plain one)."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(pid)
    ci = CardInstance(instance_id=f"{pid}_realbase", card_def=base_def,
                      owner_id=pid, zone=Zone.BASE_ZONE)
    ps.base_zone[:] = [ci]
    return ci


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:01 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


class TestMaulTS26_3:
    """Choose a unit; if it has more different keywords than Experience tokens on
    it, give it an Experience token and deal 1 damage to it."""

    def test_TS26_3_undeployed_action_tokens_and_damages_a_keyworded_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "TS26", "3"))
        # Redemption SOR_52 prints Sentinel + Restore, so ≥1 distinct keyword.
        victim = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == maul.instance_id)
        state = apply(state, use)
        state = apply(state, ChooseTarget(victim.instance_id))
        after = _find_instance(state, victim.instance_id)
        assert after.damage == 1
        assert sum(1 for u in after.attached_upgrades
                   if u.card_def.display_name == "Experience") == 1
        assert _find_instance(state, maul.instance_id) is None  # he's a leader
        assert state.find_instance(maul.instance_id)[1].exhausted   # cost paid

    def test_TS26_3_does_nothing_to_a_keywordless_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        maul = _place_leader(state, "P0", _get_leader(repo, "TS26", "3"))
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # no kw
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == maul.instance_id)
        state = apply(state, use)
        # The unit is still a legal CHOICE ("Choose a unit") — only the payoff is gated.
        assert any(isinstance(a, ChooseTarget) and a.target_id == plain.instance_id
                   for a in legal_actions(state))
        state = apply(state, ChooseTarget(plain.instance_id))
        after = _find_instance(state, plain.instance_id)
        assert after.damage == 0
        assert not after.attached_upgrades

    def test_TS26_3_registers_only_token_safe_spec_kinds(self, repo):
        """TS26_3 is ALSO the Experience token upgrade's (set, number)."""
        from swu.abilities.registry import (
            get_abilities, ActivatedAbility, TriggerAbility, WhenDeployed)
        specs = get_abilities("TS26", "3")
        for spec in specs:
            if isinstance(spec, ActivatedAbility):
                assert spec.undeployed_only
            else:
                assert isinstance(spec, TriggerAbility)
                assert spec.deployed_only or isinstance(spec.trigger, WhenDeployed)


class TestExecutionersArenaTS26_11:
    """Epic Action: for each friendly leader unit, you may deal 2 damage to a unit."""

    def test_TS26_11_epic_action_deals_2_per_leader_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, SelectDamageTarget)
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TS26", "11"))
        leader = _place(state, "P0", _get_leader(repo, "TS26", "3"), "ground")
        leader.deployed = True
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "select_damage"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectDamageTarget)
                    and a.target_id == victim.instance_id)
        state = _drive(apply(state, pick))
        assert _find_instance(state, victim.instance_id).damage == 2

    def test_TS26_11_not_offered_without_a_friendly_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TS26", "11"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not any(isinstance(a, UseAbility) for a in legal_actions(state))


class TestSundariPalaceTS26_12:
    """Epic Action: per friendly leader unit, you may resource a card from hand and
    ready it; if you do, defeat that many friendly resources at regroup."""

    def test_TS26_12_resources_a_hand_card_ready_and_schedules_the_defeat(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, SelectHandCardToResource)
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TS26", "12"))
        leader = _place(state, "P0", _get_leader(repo, "TS26", "3"), "ground")
        leader.deployed = True
        card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "resource_from_hand"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectHandCardToResource)
                    and a.instance_id == card.instance_id)
        state = apply(state, pick)
        ps = state.player_by_id("P0")
        assert card.instance_id in {r.instance_id for r in ps.resources}
        assert not next(r for r in ps.resources
                        if r.instance_id == card.instance_id).exhausted
        assert state.game_memory.defeat_resources_at_regroup.get("P0") == 1

    def test_TS26_12_declining_schedules_nothing(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, FinishResourceFromHand)
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "TS26", "12"))
        leader = _place(state, "P0", _get_leader(repo, "TS26", "3"), "ground")
        leader.deployed = True
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = apply(state, use)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishResourceFromHand)))
        assert not state.pending_decisions
        assert not state.game_memory.defeat_resources_at_regroup

    def test_TS26_12_scheduled_resources_are_defeated_at_regroup(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        _give_resources(state, "P0", 4)
        state.game_memory.defeat_resources_at_regroup["P0"] = 2
        before = len(state.player_by_id("P0").resources)
        _enter_regroup(state)
        assert len(state.player_by_id("P0").resources) == before - 2
        assert not state.game_memory.defeat_resources_at_regroup


class TestC3P0TS26_15:
    """When Played: an opponent takes control of this unit.  Action [Exhaust]: deal
    damage equal to this unit's power to another ground unit."""

    def test_TS26_15_when_played_hands_the_unit_to_the_opponent(self, repo):
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "TS26", "15"), "ground")
        state = _drive(_fire_when_played(state, c3po))
        ps, ci = state.find_instance(c3po.instance_id)
        assert ps.player_id == "P1"        # control moved
        assert ci.owner_id == "P0"         # ownership did not

    def test_TS26_15_action_deals_power_to_another_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "TS26", "15"), "ground")  # 2/5
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == c3po.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert c3po.instance_id not in offered      # "another"
        state = apply(state, ChooseTarget(victim.instance_id))
        assert _find_instance(state, victim.instance_id).damage == 2


class TestColemanTreborTS26_19:
    """When Played: deal 1 to each enemy base; heal 1 from your base."""

    def test_TS26_19_hits_enemy_base_and_heals_own(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 4
        coleman = _place(state, "P0", _get_card(repo, "TS26", "19"), "ground")
        state = _drive(_fire_when_played(state, coleman))
        assert state.player_by_id("P1").base_instance.damage == 1
        assert state.player_by_id("P0").base_instance.damage == 3


class TestAssaultLanderLAATTS26_23:
    """When Played: create 2 Clone Trooper tokens.  Regroup start: deal 4 to self."""

    def test_TS26_23_creates_two_clone_troopers(self, repo):
        state = _make_state()
        laat = _place(state, "P0", _get_card(repo, "TS26", "23"), "ground")
        state = _drive(_fire_when_played(state, laat))
        clones = [u for u in state.player_by_id("P0").ground_arena
                  if u.card_def.display_name == "Clone Trooper"]
        assert len(clones) == 2

    def test_TS26_23_takes_4_damage_at_the_start_of_regroup(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.events import PhaseChanged
        state = _make_state()
        laat = _place(state, "P0", _get_card(repo, "TS26", "23"), "ground")
        evt = PhaseChanged(new_phase="REGROUP", round_number=1)
        state.event_log.append(evt)
        state = _drive(fire_triggered_abilities(state, evt, after_all_player_idx=0))
        assert _find_instance(state, laat.instance_id).damage == 4


class TestSundariGauntletTS26_24:
    """Sentinel | On Defense: deal 1 damage to your base."""

    def test_TS26_24_on_defense_damages_own_base(self, repo):
        state = _make_state()
        gauntlet = _place(state, "P0", _get_card(repo, "TS26", "24"), "space")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _drive(_fire_on_attack(state, attacker, defender_ci=gauntlet))
        assert state.player_by_id("P0").base_instance.damage == 1
        assert state.player_by_id("P1").base_instance.damage == 0

    def test_TS26_24_has_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        gauntlet = _place(state, "P0", _get_card(repo, "TS26", "24"), "space")
        assert has_keyword(state, gauntlet, Keyword.SENTINEL)


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:02 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


class TestFieryAllianceTS26_25:
    """When Played: you may deal 1 damage to ANOTHER friendly unit and attack with it."""

    def test_TS26_25_excludes_the_attached_host_and_attacks_with_the_target(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, AttackWithUnit
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")   # 2/3
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upgrade = _place(state, "P0", _get_card(repo, "TS26", "25"), "ground")
        host.attached_upgrades.append(upgrade)
        state = _fire_upgrade_played(state, upgrade, host)
        state = _drive(state, _accept_and_target(ally), limit=1)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert host.instance_id not in offered      # "another" — not the host
        assert ally.instance_id in offered
        state = apply(state, ChooseTarget(ally.instance_id))
        assert _find_instance(state, ally.instance_id).damage == 1
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {ally.instance_id}      # pinned to the chosen unit


class TestZitonMojTS26_29:
    """On Attack: for each player, deal 1 damage to a unit that player controls."""

    def test_TS26_29_damages_one_unit_of_each_player(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        ziton = _place(state, "P0", _get_card(repo, "TS26", "29"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, ziton, defender_ci=theirs)
        state = apply(state, ChooseTarget(mine.instance_id))
        state = apply(state, ChooseTarget(theirs.instance_id))
        assert _find_instance(state, mine.instance_id).damage == 1
        assert _find_instance(state, theirs.instance_id).damage == 1


class TestRecklessLandingTS26_32:
    """Play a unit from your hand for 4 less; deal 4 damage to it."""

    def test_TS26_32_plays_a_discounted_unit_and_burns_it(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))   # cost 4, 3/7
        state, _ev = _play_event_from_hand(state, repo, "TS26", "32", resources=30)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = _drive(apply(state, play))
        in_play = _find_instance(state, unit.instance_id)
        assert in_play is not None
        assert in_play.damage == 4


class TestBackedByThePykesTS26_58:
    """Give an Experience token to a friendly unit; you may deal damage equal to the
    number of Experience tokens on friendly units."""

    def test_TS26_58_damage_counts_the_token_it_just_gave(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        from swu.engine.tokens import attach_token
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        attach_token(state, state.player_by_id("P0"), other, "Experience")
        victim = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "58")
        state = apply(state, ChooseTarget(mine.instance_id))
        state = apply(state, ChooseTarget(victim.instance_id))
        # One pre-existing token + the one just given = 2.
        assert _find_instance(state, victim.instance_id).damage == 2


class TestR2D2TS26_62:
    """When Played: you may deal 2 damage to a base; if you do, its controller draws."""

    def test_TS26_62_damages_a_base_and_its_controller_draws(self, repo):
        state = _make_state()
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "128"))
        r2 = _place(state, "P0", _get_card(repo, "TS26", "62"), "ground")
        enemy_base = state.player_by_id("P1").base_instance
        state = _fire_when_played(state, r2)
        state = _drive(state, _accept_and_target(enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 2
        assert len(state.player_by_id("P1").hand) == 1


class TestUrgentMissionTS26_64:
    """Deal 2 damage to your base.  Draw 2 cards."""

    def test_TS26_64_self_base_damage_and_two_draws(self, repo):
        state = _make_state()
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "64")
        state = _drive(state)
        assert state.player_by_id("P0").base_instance.damage == 2
        assert len(state.player_by_id("P0").hand) == 2


class TestRupingRiderTS26_67:
    """When Played: if your base has 15+ damage, deal 2 damage to a base."""

    def test_TS26_67_fires_at_15_damage(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 15
        rider = _place(state, "P0", _get_card(repo, "TS26", "67"), "ground")
        enemy_base = state.player_by_id("P1").base_instance
        state = _fire_when_played(state, rider)
        state = _drive(state, _accept_and_target(enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_TS26_67_silent_below_the_threshold(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 14
        rider = _place(state, "P0", _get_card(repo, "TS26", "67"), "ground")
        state = _fire_when_played(state, rider)
        assert not state.pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:03 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


class TestRemoveTheChipTS26_69:
    """Deal 2 damage to a unit.  If it's a Clone, ready it."""

    def test_TS26_69_readies_a_damaged_clone(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        clone = _place(state, "P0", _get_card(repo, "TS26", "39"), "ground")  # Clone 2/5
        clone.exhausted = True
        state, _ev = _play_event_from_hand(state, repo, "TS26", "69")
        state = _drive(apply(state, ChooseTarget(clone.instance_id)))
        after = _find_instance(state, clone.instance_id)
        assert after.damage == 2
        assert not after.exhausted

    def test_TS26_69_does_not_ready_a_non_clone(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other.exhausted = True
        state, _ev = _play_event_from_hand(state, repo, "TS26", "69")
        state = _drive(apply(state, ChooseTarget(other.instance_id)))
        after = _find_instance(state, other.instance_id)
        assert after.damage == 2
        assert after.exhausted


class TestBackedByBlackSunTS26_70:
    """Deal 1 to an enemy unit; you may deal damage equal to the damaged enemy units."""

    def test_TS26_70_scales_off_damaged_enemy_units(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")   # 6/9
        b = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        b.damage = 1                                    # already damaged
        _place(state, "P0", _get_card(repo, "SOR", "52"), "space")       # friendly, damaged
        state.player_by_id("P0").space_arena[0].damage = 3
        state, _ev = _play_event_from_hand(state, repo, "TS26", "70")
        state = apply(state, ChooseTarget(a.instance_id))    # now 2 damaged enemies
        state = apply(state, ChooseTarget(b.instance_id))
        # Friendly damaged units are NOT counted.
        assert _find_instance(state, b.instance_id).damage == 1 + 2


class TestTakeActionTS26_71:
    """Costs 1 less per friendly leader unit; deal 3 damage to a unit."""

    def test_TS26_71_costs_one_less_per_friendly_leader_unit(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "TS26", "71")
        ci = CardInstance("P0_take_action", card, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        ps = state.player_by_id("P0")
        base_cost = _play_cost(state, ci, ps)
        leader = _place(state, "P0", _get_leader(repo, "TS26", "3"), "ground")
        leader.deployed = True
        assert _play_cost(state, ci, ps) == base_cost - 1

    def test_TS26_71_undeployed_leader_gives_no_discount(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "TS26", "71")
        ci = CardInstance("P0_take_action2", card, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        ps = state.player_by_id("P0")
        base_cost = _play_cost(state, ci, ps)
        _place_leader(state, "P0", _get_leader(repo, "TS26", "3"))
        assert _play_cost(state, ci, ps) == base_cost

    def test_TS26_71_deals_3_damage(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "71")
        state = _drive(apply(state, ChooseTarget(victim.instance_id)))
        assert _find_instance(state, victim.instance_id).damage == 3


class TestFervorTS26_72:
    """Ready a unit.  Deal 3 damage to a unit."""

    def test_TS26_72_readies_one_unit_and_burns_another(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        tired = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        tired.exhausted = True
        fresh = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "72")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert tired.instance_id in offered
        assert fresh.instance_id not in offered      # never a no-op ready
        state = apply(state, ChooseTarget(tired.instance_id))
        state = _drive(apply(state, ChooseTarget(victim.instance_id)))
        assert not _find_instance(state, tired.instance_id).exhausted
        assert _find_instance(state, victim.instance_id).damage == 3


class TestMoraloEvalTS26_73:
    """When your base is dealt combat damage: you may deal 1 damage to a unit."""

    def test_TS26_73_fires_when_an_enemy_unit_hits_your_base(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.events import AttackDeclared
        state = _make_state()
        moralo = _place(state, "P0", _get_card(repo, "TS26", "73"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        evt = AttackDeclared(attacker_player_id="P1",
                             attacker_instance_id=attacker.instance_id,
                             attacker_name=attacker.card_def.display_name,
                             defender_instance_id=None, defender_name="Base")
        state.event_log.append(evt)
        state = fire_triggered_abilities(
            state, evt, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": attacker.instance_id,
                       "base_combat_damage_amount": 3})
        state = _drive(state, _accept_and_target(victim))
        assert _find_instance(state, victim.instance_id).damage == 1


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:04 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


class TestAhsokaTanoTS26_8:
    """Undeployed: when you play an event, you may exhaust her to peek the top card.
    Deployed: Raid 1 | When Attack Ends: peek, and a play costs 1 less."""

    def test_TS26_8_undeployed_event_trigger_exhausts_and_peeks(self, repo):
        from swu.engine.actions import AcceptTrigger, apply, legal_actions
        state = _make_state()
        ahsoka = _place_leader(state, "P0", _get_leader(repo, "TS26", "8"))
        for _ in range(6):        # Arms Deal draws 2, so leave the deck non-empty
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "68")   # Arms Deal
        accept = next((a for a in legal_actions(state)
                       if isinstance(a, AcceptTrigger)), None)
        assert accept is not None
        state = _drive(apply(state, accept), limit=1)
        assert state.pending_decisions[-1].kind == "peek_top"
        assert state.find_instance(ahsoka.instance_id)[1].exhausted

    def test_TS26_8_not_offered_while_already_exhausted(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        ahsoka = _place_leader(state, "P0", _get_leader(repo, "TS26", "8"))
        ahsoka.exhausted = True
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "68")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_TS26_8_deployed_attack_end_peeks_at_a_discount(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.events import AttackDeclared
        state = _make_state()
        ahsoka = _place(state, "P0", _get_leader(repo, "TS26", "8"), "ground")
        ahsoka.deployed = True
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        evt = AttackDeclared(attacker_player_id="P0",
                             attacker_instance_id=ahsoka.instance_id,
                             attacker_name="Ahsoka Tano",
                             defender_instance_id=None, defender_name="Base")
        state.event_log.append(evt)
        state = fire_triggered_abilities(
            state, evt, after_all_player_idx=0,
            event_ctx={"attack_ended_survivor": ahsoka.instance_id,
                       "attacker_id": ahsoka.instance_id})
        assert state.pending_decisions[-1].kind == "peek_top"
        assert state.pending_decisions[-1].context.get("cost_reduction") == 1

    def test_TS26_8_has_raid_1_when_deployed(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        ahsoka = _place(state, "P0", _get_leader(repo, "TS26", "8"), "ground")
        ahsoka.deployed = True
        assert has_keyword(state, ahsoka, Keyword.RAID)
        assert keyword_value(state, ahsoka, Keyword.RAID) == 1


class TestMotherTalzinTS26_26:
    """When Defeated: look at an opponent's hand, discard a card, they draw; a
    discarded UNIT becomes playable from their discard this phase."""

    def test_TS26_26_discards_a_unit_and_unlocks_the_foreign_discard_play(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        talzin = _place(state, "P0", _get_card(repo, "TS26", "26"), "ground")
        victim_card = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "128"))
        state = _fire_when_defeated(state, talzin)
        name = next(a for a in legal_actions(state) if isinstance(a, NameAndDiscard))
        state = apply(state, name)
        p1 = state.player_by_id("P1")
        assert victim_card.instance_id in {c.instance_id for c in p1.discard}
        assert len(p1.hand) == 1                              # they drew
        unlocked = state.game_memory.foreign_discard_play_this_phase.get("P0", [])
        assert victim_card.instance_id in unlocked

    def test_TS26_26_a_non_unit_discard_unlocks_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        talzin = _place(state, "P0", _get_card(repo, "TS26", "26"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "TS26", "68"))   # an EVENT
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "128"))
        state = _fire_when_defeated(state, talzin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, NameAndDiscard)))
        assert not state.game_memory.foreign_discard_play_this_phase


class TestKouhunAssassinationTS26_33:
    """An opponent may discard a card; if they do, give a non-Vehicle unit -8/-8."""

    def test_TS26_33_discarding_applies_the_debuff(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, DiscardRandomCard, compute_power)
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "33")
        state = apply(state, ChooseTarget(victim.instance_id))
        assert state.pending_decisions[-1].kind == "may_discard"
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DiscardRandomCard)))
        # compute_power floors at 0, so assert the modifier itself as well.
        assert any(m.target_instance_id == victim.instance_id and m.kind == "stats"
                   and m.value.get("power") == -8 and m.value.get("hp") == -8
                   for m in state.modifiers)
        after = _find_instance(state, victim.instance_id)
        assert after is None or compute_power(state, after) == 0
        assert len(state.player_by_id("P1").hand) == 0      # they discarded

    def test_TS26_33_declining_does_nothing(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, DeclineDiscard, compute_power)
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "33")
        state = apply(state, ChooseTarget(victim.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineDiscard)))
        assert compute_power(state, _find_instance(state, victim.instance_id)) == 3
        assert len(state.player_by_id("P1").hand) == 1

    def test_TS26_33_does_not_offer_a_vehicle(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        vehicle = _place(state, "P1", _get_card(repo, "TS26", "24"), "space")  # Vehicle
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "33")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert vehicle.instance_id not in offered
        assert plain.instance_id in offered


class TestAbandonedTheOrderTS26_37:
    """Attached unit loses Jedi and gains Restore 1.  When Played: you may bounce a
    non-leader unit."""

    def test_TS26_37_strips_jedi_and_grants_restore(self, repo):
        from swu.engine.traits import has_trait
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        jedi = _place(state, "P0", _get_card(repo, "TS26", "19"), "ground")  # Jedi
        assert has_trait(state, jedi, "Jedi")
        upgrade = _place(state, "P0", _get_card(repo, "TS26", "37"), "ground")
        jedi.attached_upgrades.append(upgrade)
        state = _fire_upgrade_played(state, upgrade, jedi)
        # DECLINE the separate optional bounce — accepting it would return the very
        # host we are asserting about.
        state = _drive(state, _decline_triggers())
        host = _find_instance(state, jedi.instance_id)
        assert not has_trait(state, host, "Jedi")
        assert has_keyword(state, host, Keyword.RESTORE)
        assert keyword_value(state, host, Keyword.RESTORE) == 1

    def test_TS26_37_may_return_a_non_leader_unit(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        upgrade = _place(state, "P0", _get_card(repo, "TS26", "37"), "ground")
        host.attached_upgrades.append(upgrade)
        state = _fire_upgrade_played(state, upgrade, host)
        state = _drive(state, _accept_and_target(target))
        assert _find_instance(state, target.instance_id) is None
        assert any(c.instance_id == target.instance_id
                   for c in state.player_by_id("P1").hand)


class TestCaptainVaughnTS26_39:
    """When Defeated: search the top 3 and draw one; then put a hand card on top."""

    def test_TS26_39_search_resolves_before_the_top_placement(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard, SelectHandCardToTop)
        state = _make_state()
        vaughn = _place(state, "P0", _get_card(repo, "TS26", "39"), "ground")
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_when_defeated(state, vaughn)
        assert state.pending_decisions[-1].kind == "deck_search"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard))
        state = apply(state, pick)
        # The drawn card is now in hand, and the placement decision is what's left.
        assert state.pending_decisions[-1].kind == "bottom_from_hand"
        tops = [a for a in legal_actions(state)
                if isinstance(a, SelectHandCardToTop)]
        assert tops and any(a.instance_id == pick.instance_id for a in tops)
        state = apply(state, tops[0])
        assert not state.pending_decisions
        assert state.player_by_id("P0").deck[0].instance_id == tops[0].instance_id


class TestSecretMarriageTS26_46:
    """Shield up to 2 non-Vehicle units; draw if one of them was an enemy."""

    def test_TS26_46_draws_when_an_enemy_unit_gets_a_shield(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken)
        state = _make_state()
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "46")
        assert state.pending_decisions[-1].kind == "select_token"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == theirs.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishSelectToken)))
        assert len(state.player_by_id("P0").hand) == 1
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, theirs.instance_id).attached_upgrades)

    def test_TS26_46_friendly_only_picks_draw_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "46")
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, SelectTokenTarget)
                                         and a.target_id == mine.instance_id)))
        assert not state.player_by_id("P0").hand
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, mine.instance_id).attached_upgrades)


class TestMechanizeTS26_57:
    """Play a non-Vehicle unit from your discard (paying its cost) + an Experience."""

    def test_TS26_57_replays_a_discarded_unit_with_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from tests.test_sor_cards import _discard_unit
        state = _make_state()
        dead = _discard_unit(state, "P0", _get_card(repo, "SOR", "46"))
        vehicle = _discard_unit(state, "P0", _get_card(repo, "TS26", "24"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "57", resources=20)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert dead.instance_id in offered
        assert vehicle.instance_id not in offered      # non-Vehicle only
        state = _drive(apply(state, PlayFromHand(dead.instance_id)))
        back = _find_instance(state, dead.instance_id)
        assert back is not None
        assert any(u.card_def.display_name == "Experience"
                   for u in back.attached_upgrades)


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:05 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


class TestArmsDealTS26_68:
    """You and an opponent each draw 2 cards."""

    def test_TS26_68_both_players_draw_two(self, repo):
        state = _make_state()
        for pid in ("P0", "P1"):
            for _ in range(3):
                _push_deck_top(state, pid, _get_card(repo, "SOR", "128"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "68")
        state = _drive(state)
        assert len(state.player_by_id("P0").hand) == 2
        assert len(state.player_by_id("P1").hand) == 2


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:06 — the TS26 leader block (+ First Battle Memorial)
# ══════════════════════════════════════════════════════════════════════════════


def _deploy(state, leader_ci):
    """Deploy an undeployed leader into its arena through the real engine path, so
    ``units_played_this_phase`` and the deploy triggers all fire."""
    from swu.engine.actions import _deploy_leader_into_arena
    ps = state.player_by_id(leader_ci.owner_id)
    return _deploy_leader_into_arena(state, ps, leader_ci)


def _use_ability(state, source_ci):
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id)
    return apply(state, use)


class TestCountDookuTS26_1:
    """Undeployed: both players heal 1 from their base and create a Battle Droid.
    Deployed On Attack: create 2 Battle Droid tokens."""

    def test_TS26_1_undeployed_action_aids_both_players(self, repo):
        state = _make_state()
        dooku = _place_leader(state, "P0", _get_leader(repo, "TS26", "1"))
        for pid in ("P0", "P1"):
            state.player_by_id(pid).base_instance.damage = 4
        state = _drive(_use_ability(state, dooku))
        for pid in ("P0", "P1"):
            ps = state.player_by_id(pid)
            assert ps.base_instance.damage == 3          # healed exactly 1
            assert sum(1 for u in ps.ground_arena
                       if u.card_def.display_name == "Battle Droid") == 1

    def test_TS26_1_deployed_on_attack_creates_two_battle_droids(self, repo):
        state = _make_state()
        dooku = _place_leader(state, "P0", _get_leader(repo, "TS26", "1"))
        state = _deploy(state, dooku)
        state = _drive(state)
        unit = state.find_instance(dooku.instance_id)[1]
        state = _drive(_fire_on_attack(state, unit))
        droids = [u for u in state.player_by_id("P0").ground_arena
                  if u.card_def.display_name == "Battle Droid"]
        assert len(droids) == 2


class TestAnakinSkywalkerTS26_2:
    """Undeployed: shield one of ≥2 units that entered play this phase.
    Deployed On Attack: shield another unit that entered play this phase."""

    def test_TS26_2_undeployed_action_shields_an_entrant(self, repo):
        from swu.engine.actions import apply, legal_actions, SelectTokenTarget
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_leader(repo, "TS26", "2"))
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")
        state.game_memory.units_played_this_phase.update(
            {a.instance_id, b.instance_id})
        state = _use_ability(state, anakin)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, SelectTokenTarget)}
        assert offered == {a.instance_id, b.instance_id}
        state = _drive(apply(state, SelectTokenTarget(a.instance_id)))
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, a.instance_id).attached_upgrades)

    def test_TS26_2_undeployed_action_is_usable_but_inert_below_two_entrants(
            self, repo):
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_leader(repo, "TS26", "2"))
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_played_this_phase.add(a.instance_id)
        # The card's rules note: the Action is still usable, it just does nothing.
        state = _drive(_use_ability(state, anakin))
        assert not state.pending_decisions
        assert not _find_instance(state, a.instance_id).attached_upgrades
        assert state.find_instance(anakin.instance_id)[1].exhausted

    def test_TS26_2_deploying_a_leader_counts_as_entering_play_this_phase(self, repo):
        """"including tokens and LEADERS" — the deploy path records the leader."""
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_leader(repo, "TS26", "2"))
        state = _drive(_deploy(state, anakin))
        assert anakin.instance_id in state.game_memory.units_played_this_phase


class TestPadmeAmidalaTS26_4:
    """Attack with a unit that entered play this phase, even if exhausted."""

    def test_TS26_4_undeployed_action_attacks_with_an_exhausted_entrant(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        padme = _place_leader(state, "P0", _get_leader(repo, "TS26", "4"))
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")
        a.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_played_this_phase.update(
            {a.instance_id, b.instance_id})
        state = _use_ability(state, padme)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {x.attacker_id for x in legal_actions(state)
                     if isinstance(x, AttackWithUnit)}
        assert a.instance_id in attackers          # exhausted, still offered
        assert b.instance_id in attackers
        # "It can't attack bases for this attack" — no base target is offered.
        assert all(x.defender_id is not None for x in legal_actions(state)
                   if isinstance(x, AttackWithUnit))

    def test_TS26_4_undeployed_action_needs_two_entrants(self, repo):
        state = _make_state()
        padme = _place_leader(state, "P0", _get_leader(repo, "TS26", "4"))
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_played_this_phase.add(a.instance_id)
        state = _drive(_use_ability(state, padme))
        assert not state.pending_decisions


class TestSavageOpressTS26_5:
    """Undeployed: the most-powerful friendly units gain Overwhelm.
    Deployed: each OTHER friendly unit gains Overwhelm."""

    def test_TS26_5_undeployed_aura_reaches_only_the_most_powerful(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))
        big = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")   # 4 power
        small = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, big, Keyword.OVERWHELM)
        assert not has_keyword(state, small, Keyword.OVERWHELM)
        # An enemy unit is never "friendly", however big.
        enemy = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        assert not has_keyword(state, enemy, Keyword.OVERWHELM)

    def test_TS26_5_undeployed_aura_is_inert_once_he_deploys(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        savage = _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))
        big = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        assert has_keyword(state, big, Keyword.OVERWHELM)
        state = _drive(_deploy(state, savage))
        big = _find_instance(state, big.instance_id)
        # Now the DEPLOYED aura covers it instead ("each other friendly unit"), so
        # it still has Overwhelm — but a NON-top-power unit proves which aura is on.
        small = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, big, Keyword.OVERWHELM)
        assert has_keyword(state, small, Keyword.OVERWHELM)

    def test_TS26_5_keeps_his_printed_overwhelm(self, repo):
        """Sanitiser rule 1 must not strip a keyword printed as its own deploy-box
        line just because the undeployed box also grants it."""
        assert "Overwhelm" in _get_leader(repo, "TS26", "5").keywords
        assert "Raid" in _get_leader(repo, "TS26", "5").keywords


class TestRexTS26_6:
    """Ready an exhausted enemy unit; the next event costs less."""

    def test_TS26_6_undeployed_action_readies_and_discounts_the_next_event(
            self, repo):
        from swu.engine.actions import apply, ChooseTarget, _play_cost
        state = _make_state()
        rex = _place_leader(state, "P0", _get_leader(repo, "TS26", "6"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        ev = _put_in_hand(state, "P0", _get_card(repo, "SOR", "173"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, ev, ps)
        state = _drive(apply(_use_ability(state, rex),
                             ChooseTarget(enemy.instance_id)))
        assert not _find_instance(state, enemy.instance_id).exhausted
        ev = next(c for c in state.player_by_id("P0").hand
                  if c.instance_id == ev.instance_id)
        assert _play_cost(state, ev, state.player_by_id("P0")) == before - 1

    def test_TS26_6_undeployed_action_is_hidden_with_no_exhausted_enemy(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        rex = _place_leader(state, "P0", _get_leader(repo, "TS26", "6"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # ready
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == rex.instance_id]

    def test_TS26_6_discount_applies_to_events_only(self, repo):
        from swu.engine.actions import apply, ChooseTarget, _play_cost
        state = _make_state()
        rex = _place_leader(state, "P0", _get_leader(repo, "TS26", "6"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        before = _play_cost(state, unit, state.player_by_id("P0"))
        state = _drive(apply(_use_ability(state, rex),
                             ChooseTarget(enemy.instance_id)))
        unit = next(c for c in state.player_by_id("P0").hand
                    if c.instance_id == unit.instance_id)
        assert _play_cost(state, unit,
                          state.player_by_id("P0")) == before   # not discounted


class TestAsajjVentressTS26_7:
    """Attack with a token unit (+1/+0); +2/+0 once you have."""

    def test_TS26_7_undeployed_action_only_offers_token_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "TS26", "7"))
        from swu.engine.actions import _create_token_units
        tokens = _create_token_units(state, state.player_by_id("P0"),
                                     "Battle Droid", 1, enters_ready=True)
        real = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drive(state)
        state = _use_ability(state, _find_instance(state, asajj.instance_id)
                             or state.find_instance(asajj.instance_id)[1])
        attackers = {x.attacker_id for x in legal_actions(state)
                     if isinstance(x, AttackWithUnit)}
        assert tokens[0].instance_id in attackers
        assert real.instance_id not in attackers

    def test_TS26_7_deployed_gets_plus_two_after_a_token_attacked(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_leader(repo, "TS26", "7"))
        state = _drive(_deploy(state, asajj))
        unit = state.find_instance(asajj.instance_id)[1]
        before = compute_power(state, unit)
        state.game_memory.token_unit_attackers_this_round.add("P0")
        assert compute_power(state, unit) == before + 2
        # An OPPONENT's token attack does not turn it on.
        state.game_memory.token_unit_attackers_this_round = {"P1"}
        assert compute_power(state, unit) == before

    def test_TS26_7_a_dead_token_still_counts(self, repo):
        """The ledger records the CONTROLLER at declare, so a token defeated in the
        attack it made (and thus gone from the game) still satisfies the clause."""
        from swu.engine.actions import note_token_unit_attacked, _create_token_units
        state = _make_state()
        tokens = _create_token_units(state, state.player_by_id("P0"),
                                     "Battle Droid", 1, enters_ready=True)
        state = _drive(state)
        note_token_unit_attacked(state, tokens[0])
        ps = state.player_by_id("P0")
        ps.ground_arena[:] = [u for u in ps.ground_arena
                              if u.instance_id != tokens[0].instance_id]
        assert state.find_instance(tokens[0].instance_id) is None
        assert "P0" in state.game_memory.token_unit_attackers_this_round


class TestFirstBattleMemorialTS26_9:
    """Epic Action: an Experience token per friendly leader unit."""

    def test_TS26_9_gives_one_experience_per_leader_unit(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "TS26", "9"))
        leader = _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))
        state = _drive(_deploy(state, leader))
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _use_ability(state, base)
        assert state.pending_decisions[-1].kind == "select_token"
        state = _drive(apply(state, SelectTokenTarget(target.instance_id)))
        got = _find_instance(state, target.instance_id)
        assert sum(1 for u in got.attached_upgrades
                   if u.card_def.display_name == "Experience") == 1

    def test_TS26_9_is_not_offered_without_a_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "TS26", "9"))
        _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))   # undeployed
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == base.instance_id]


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:07 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestDookusPalaceTS26_10:
    """Epic Action: play a unit, 1 less per friendly leader unit."""

    def test_TS26_10_discounts_by_the_friendly_leader_unit_count(self, repo):
        from swu.engine.actions import apply, PlayFromHand
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "TS26", "10"))
        leader = _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))
        state = _drive(_deploy(state, leader))
        from swu.engine.actions import _play_cost
        card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "47"))
        _give_resources(state, "P0", 20)
        undiscounted = _play_cost(state, card, state.player_by_id("P0"))
        before = state.player_by_id("P0").available_resources
        state = _use_ability(state, base)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        state = _drive(apply(state, PlayFromHand(card.instance_id)))
        spent = before - state.player_by_id("P0").available_resources
        assert spent == undiscounted - 1     # one deployed leader unit

    def test_TS26_10_is_not_offered_with_nothing_playable(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "TS26", "10"))
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == base.instance_id]


class TestDarthSidiousTS26_13:
    """Other friendly Separatist units get +1/+0; a non-token defeat makes a droid."""

    def test_TS26_13_buffs_other_separatists_only(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        sidious = _place(state, "P0", _get_card(repo, "TS26", "13"), "ground")
        # TS26_77 Deployed Droideka is a plain Separatist unit.
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        assert compute_power(state, friend) == friend.card_def.power + 1
        assert compute_power(state, sidious) == sidious.card_def.power   # "other"

    def test_TS26_13_creates_a_droid_when_a_non_token_unit_dies(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TS26", "13"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P1"), victim)
        state = _drive(state)
        assert sum(1 for u in state.player_by_id("P0").ground_arena
                   if u.card_def.display_name == "Battle Droid") == 1

    def test_TS26_13_a_dying_token_makes_nothing(self, repo):
        from swu.engine.actions import _defeat_unit, _create_token_units
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TS26", "13"), "ground")
        tok = _create_token_units(state, state.player_by_id("P1"),
                                  "Battle Droid", 1)[0]
        state = _drive(state)
        _defeat_unit(state, state.player_by_id("P1"), tok)
        state = _drive(state)
        assert not [u for u in state.player_by_id("P0").ground_arena
                    if u.card_def.display_name == "Battle Droid"]


class TestKingKatuunkoTS26_16:
    """When Played: all units gain Restore 1 for this phase."""

    def test_TS26_16_grants_restore_to_every_unit(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        king = _place(state, "P0", _get_card(repo, "TS26", "16"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drive(_fire_when_played(state, king))
        assert keyword_value(state, _find_instance(state, mine.instance_id),
                             Keyword.RESTORE) == 1
        assert keyword_value(state, _find_instance(state, theirs.instance_id),
                             Keyword.RESTORE) == 1


class TestJendirianValleyTS26_18:
    """When Played: search the top 8 and RESOURCE the chosen card."""

    def test_TS26_18_resources_the_chosen_card_exhausted(self, repo):
        from swu.engine.actions import apply, SelectSearchCard
        state = _make_state()
        valley = _place(state, "P0", _get_card(repo, "TS26", "18"), "space")
        wanted = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "47"))
        before = len(state.player_by_id("P0").resources)
        state = _fire_when_played(state, valley)
        assert state.pending_decisions[-1].kind == "deck_search"
        state = _drive(apply(state, SelectSearchCard(wanted.instance_id)))
        ps = state.player_by_id("P0")
        assert len(ps.resources) == before + 1
        got = next(r for r in ps.resources if r.instance_id == wanted.instance_id)
        assert got.exhausted and got.face_down     # CR default + the card's note
        assert wanted.instance_id not in {c.instance_id for c in ps.hand}


class TestVeteran501stTS26_20:
    """While undamaged it gains Sentinel."""

    def test_TS26_20_sentinel_only_while_undamaged(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        vet = _place(state, "P0", _get_card(repo, "TS26", "20"), "ground")
        assert has_keyword(state, vet, Keyword.SENTINEL)
        vet.damage = 1
        assert not has_keyword(state, vet, Keyword.SENTINEL)
        # …and the printed bar was stripped, so the grant really owns it.
        assert "Sentinel" not in _get_card(repo, "TS26", "20").keywords


class TestTheDarksaberTS26_22:
    """Attached unit gains Sentinel; ready it on 4+ different friendly keywords."""

    def test_TS26_22_readies_the_host_on_four_distinct_keywords(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "TS26", "20"), "ground")  # Grit+Raid
        host.exhausted = True
        # Redemption SOR_52 prints Sentinel and Jendirian Valley TS26_18 prints
        # Restore, so the friendly union is Grit/Raid/Sentinel/Restore = 4.
        _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        _place(state, "P0", _get_card(repo, "TS26", "18"), "space")
        saber = CardInstance("saber1", _get_card(repo, "TS26", "22"), "P0",
                             Zone.GROUND_ARENA)
        host.attached_upgrades.append(saber)
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.events import UpgradePlayed
        evt = UpgradePlayed(player_id="P0", instance_id=saber.instance_id,
                            card_name=saber.card_def.display_name,
                            attached_to_instance_id=host.instance_id)
        state = _drive(fire_triggered_abilities(
            state, evt, after_all_player_idx=0,
            event_ctx={"attached_to_id": host.instance_id}))
        assert not _find_instance(state, host.instance_id).exhausted

    def test_TS26_22_grants_sentinel_to_its_host(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert not has_keyword(state, host, Keyword.SENTINEL)
        host.attached_upgrades.append(
            CardInstance("saber2", _get_card(repo, "TS26", "22"), "P0",
                         Zone.GROUND_ARENA))
        assert has_keyword(state, host, Keyword.SENTINEL)


class TestPrimeMinisterAlmecTS26_28:
    """+2/+2 to a friendly unit, then exhaust weaker enemies in its arena."""

    def test_TS26_28_buffs_then_exhausts_weaker_same_arena_enemies(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        almec = _place(state, "P0", _get_card(repo, "TS26", "28"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        strong = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")
        state = _drive(apply(_fire_when_played(state, almec),
                             ChooseTarget(mine.instance_id)))
        buffed = _find_instance(state, mine.instance_id)
        assert compute_power(state, buffed) == mine.card_def.power + 2
        assert _find_instance(state, weak.instance_id).exhausted     # same arena
        assert not _find_instance(state, strong.instance_id).exhausted  # space


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:08 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestMaulTS26_30:
    """When Played: you may attack with another unit."""

    def test_TS26_30_offers_an_attack_by_another_unit(self, repo):
        from swu.engine.actions import (legal_actions, AttackWithUnit)
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "TS26", "30"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, maul)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {x.attacker_id for x in legal_actions(state)
                     if isinstance(x, AttackWithUnit)}
        assert other.instance_id in attackers
        assert maul.instance_id not in attackers      # "another unit"


class TestChaoticDiversionTS26_31:
    """Ready an enemy unit but lock it out of attacking; shield a friendly."""

    def test_TS26_31_readies_and_locks_the_enemy_then_shields_a_friendly(self, repo):
        from swu.engine.actions import apply, ChooseTarget, legal_actions
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        mine = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "31")
        # LIFO: the second ability's Shield choice is on top, the ready below it.
        for _ in range(6):
            if not state.pending_decisions:
                break
            acts = [a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id]
            state = apply(state, acts[0] if acts else legal_actions(state)[0])
        after = _find_instance(state, enemy.instance_id)
        assert not after.exhausted
        assert any(m.kind == "cannot_attack"
                   and m.target_instance_id == enemy.instance_id
                   for m in state.modifiers)
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, mine.instance_id).attached_upgrades)


class TestAhsokasLightsabersTS26_35:
    """Shield an enemy unit; if you do, the next event costs 2 less."""

    def test_TS26_35_on_attack_shields_an_enemy_and_discounts_an_event(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        host.attached_upgrades.append(
            CardInstance("sabers1", _get_card(repo, "TS26", "35"), "P0",
                         Zone.GROUND_ARENA))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drive(_fire_on_attack(state, host, enemy),
                       _accept_and_target(enemy))
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, enemy.instance_id).attached_upgrades)
        ev = _put_in_hand(state, "P0", _get_card(repo, "SOR", "173"))
        discounted = _play_cost(state, ev, state.player_by_id("P0"))
        state.game_memory.pending_play_discounts.clear()
        assert discounted == _play_cost(
            state, ev, state.player_by_id("P0")) - 2


class TestDookusSolarSailerTS26_38:
    """Experience to another Separatist unit, but only if a base was healed."""

    def test_TS26_38_needs_a_base_heal_this_phase(self, repo):
        state = _make_state()
        sailer = _place(state, "P0", _get_card(repo, "TS26", "38"), "space")
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        state = _drive(_fire_when_played(state, sailer))
        assert not _find_instance(state, friend.instance_id).attached_upgrades

    def test_TS26_38_gives_experience_after_a_base_heal(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        sailer = _place(state, "P0", _get_card(repo, "TS26", "38"), "space")
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        # A real heal through the engine's own chokepoint feeds the ledger.
        from swu.abilities.resolver import _apply_heal
        state.player_by_id("P1").base_instance.damage = 3
        _apply_heal(state, sailer,
                    state.player_by_id("P1").base_instance.instance_id, 2)
        assert state.game_memory.bases_healed_this_phase
        state = _drive(apply(_fire_when_played(state, sailer),
                             ChooseTarget(friend.instance_id)))
        assert any(u.card_def.display_name == "Experience"
                   for u in _find_instance(state, friend.instance_id).attached_upgrades)

    def test_TS26_38_restore_feeds_the_base_heal_ledger(self, repo):
        """Restore is the way this card is meant to be switched on."""
        from swu.engine.actions import _apply_restore
        state = _make_state()
        ps = state.player_by_id("P0")
        ps.base_instance.damage = 4
        _apply_restore(state, ps, 2, "test")
        assert ps.base_instance.instance_id in state.game_memory.bases_healed_this_phase


class TestObiWanKenobiTS26_40:
    """Other friendly Republic units gain Restore 1."""

    def test_TS26_40_grants_restore_to_other_republic_units_only(self, repo):
        from swu.engine.keywords import keyword_value, has_keyword, Keyword
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "TS26", "40"), "ground")
        rep = _place(state, "P0", _get_card(repo, "TS26", "18"), "space")  # Republic
        other = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        assert keyword_value(state, rep, Keyword.RESTORE) >= 1
        assert not has_keyword(state, other, Keyword.RESTORE)
        # He grants it, he does not have it — the printed bar was sanitised away.
        assert not has_keyword(state, obi, Keyword.RESTORE)


class TestTwilightTS26_41:
    """When Played: heal 3 from your base if your discard holds 5+ cards."""

    def test_TS26_41_heals_only_with_five_cards_in_the_discard(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        twilight = _place(state, "P0", _get_card(repo, "TS26", "41"), "space")
        ps = state.player_by_id("P0")
        ps.base_instance.damage = 6
        state = _drive(_fire_when_played(state, twilight))
        assert state.player_by_id("P0").base_instance.damage == 6   # gate failed
        for i in range(5):
            ps.discard.append(CardInstance(f"d{i}", _get_card(repo, "SOR", "46"),
                                           "P0", Zone.DISCARD))
        state = _drive(_fire_when_played(state, twilight))
        assert state.player_by_id("P0").base_instance.damage == 3


class TestReliefFrigateTS26_42:
    """Choose a base; heal 3 from each OTHER base."""

    def test_TS26_42_heals_every_base_except_the_chosen_one(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        frigate = _place(state, "P0", _get_card(repo, "TS26", "42"), "space")
        for pid in ("P0", "P1"):
            state.player_by_id(pid).base_instance.damage = 5
        chosen = state.player_by_id("P0").base_instance
        state = _drive(apply(_fire_when_played(state, frigate),
                             ChooseTarget(chosen.instance_id)))
        assert state.player_by_id("P0").base_instance.damage == 5   # excluded
        assert state.player_by_id("P1").base_instance.damage == 2


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:09 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestTakeCoverTS26_47:
    """Costs 1 less per friendly leader unit; heal up to 3 from a unit + Shield it."""

    def test_TS26_47_heals_and_shields_the_same_unit_from_one_prompt(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 4
        other.damage = 4
        state, _ev = _play_event_from_hand(state, repo, "TS26", "47")
        state = _drive(apply(state, ChooseTarget(hurt.instance_id)))
        healed = _find_instance(state, hurt.instance_id)
        assert healed.damage == 1                       # 4 - 3
        assert any(u.card_def.display_name == "Shield"
                   for u in healed.attached_upgrades)
        # ONE prompt: the other unit is untouched, so the halves cannot split.
        untouched = _find_instance(state, other.instance_id)
        assert untouched.damage == 4 and not untouched.attached_upgrades

    def test_TS26_47_costs_one_less_per_friendly_leader_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "47"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, card, ps)
        leader = _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))
        ps.base_zone.remove(leader)
        leader.deployed = True
        ps.ground_arena.append(leader)
        assert _play_cost(state, card, ps) == before - 1


class TestSeparatistCouncilTS26_49:
    """When Played/On Attack: choose one — create a Battle Droid, or 2 Experience
    onto a Battle Droid token."""

    def test_TS26_49_mode_one_creates_a_battle_droid_token(self, repo):
        from swu.engine.actions import apply, SelectModalOption
        state = _make_state()
        council = _place(state, "P0", _get_card(repo, "TS26", "49"), "ground")
        state = _fire_when_played(state, council)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        # With no Battle Droid on the board only the create mode is offered.
        assert state.pending_decisions[-1].context["option_indices"] == [2]
        state = _drive(apply(state, SelectModalOption(option_idx=2)))
        assert any(u.card_def.display_name == "Battle Droid"
                   for u in state.player_by_id("P0").ground_arena)

    def test_TS26_49_mode_two_offered_once_a_battle_droid_exists(self, repo):
        from swu.engine.actions import apply, SelectModalOption, ChooseTarget
        from swu.engine.actions import _create_token_units
        state = _make_state()
        council = _place(state, "P0", _get_card(repo, "TS26", "49"), "ground")
        made = _create_token_units(state, state.player_by_id("P0"),
                                   "Battle Droid", 1)
        state = _fire_when_played(state, council)
        assert state.pending_decisions[-1].context["option_indices"] == [2, 3]
        state = apply(state, SelectModalOption(option_idx=3))
        state = _drive(apply(state, ChooseTarget(made[0].instance_id)))
        droid = _find_instance(state, made[0].instance_id)
        assert sum(1 for u in droid.attached_upgrades
                   if u.card_def.display_name == "Experience") == 2


class TestGeneralGrievousTS26_50:
    """+1/+1 per resource you control; Sentinel while undamaged."""

    def test_TS26_50_scales_with_resources_and_loses_sentinel_when_damaged(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "TS26", "50"), "ground")
        assert compute_power(state, grievous) == 0        # printed 0/0
        _give_resources(state, "P0", 4)
        assert compute_power(state, grievous) == 4
        assert compute_hp(state, grievous) == 4
        assert has_keyword(state, grievous, Keyword.SENTINEL)
        grievous.damage = 1
        assert not has_keyword(state, grievous, Keyword.SENTINEL)


class TestLomPykeTS26_51:
    """When Played: the opponent may heal 5 from their base; if they do, give 2
    Experience to a unit."""

    def test_TS26_51_opponent_accepts_and_the_controller_collects(self, repo):
        from swu.engine.actions import apply, AllowEffect, SelectTokenTarget
        state = _make_state()
        pyke = _place(state, "P0", _get_card(repo, "TS26", "51"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P1").base_instance.damage = 8
        state = _fire_when_played(state, pyke)
        top = state.pending_decisions[-1]
        assert top.kind == "say_no" and top.deciding_player_id == "P1"
        state = apply(state, AllowEffect())
        assert state.player_by_id("P1").base_instance.damage == 3
        assert state.pending_decisions[-1].kind == "select_token"
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        state = _drive(apply(state, SelectTokenTarget(friend.instance_id)))
        assert sum(1 for u in _find_instance(state, friend.instance_id).attached_upgrades
                   if u.card_def.display_name == "Experience") == 2

    def test_TS26_51_declining_heals_nothing_and_pays_nothing(self, repo):
        from swu.engine.actions import apply, SayNo
        state = _make_state()
        pyke = _place(state, "P0", _get_card(repo, "TS26", "51"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P1").base_instance.damage = 8
        state = _drive(apply(_fire_when_played(state, pyke), SayNo()))
        assert state.player_by_id("P1").base_instance.damage == 8
        assert not _find_instance(state, friend.instance_id).attached_upgrades


class TestSithTraditionsTS26_52:
    """Attached unit gains On Attack + When Defeated Experience clauses."""

    def test_TS26_52_on_attack_tokens_the_host(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        saber = _place(state, "P0", _get_card(repo, "TS26", "52"), "ground")
        state.player_by_id("P0").ground_arena.remove(saber)
        host.attached_upgrades.append(saber)
        state = _drive(_fire_on_attack(state, host))
        assert any(u.card_def.display_name == "Experience"
                   for u in _find_instance(state, host.instance_id).attached_upgrades)

    def test_TS26_52_when_defeated_tokens_a_friendly_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        saber = _place(state, "P0", _get_card(repo, "TS26", "52"), "ground")
        state.player_by_id("P0").ground_arena.remove(saber)
        host.attached_upgrades.append(saber)
        state = _fire_when_defeated(state, host)
        state = _drive(apply(state, ChooseTarget(friend.instance_id)))
        assert any(u.card_def.display_name == "Experience"
                   for u in _find_instance(state, friend.instance_id).attached_upgrades)


class TestCoruscantiSpyTS26_53:
    """When Played: heal 2 from each of any number of bases."""

    def test_TS26_53_can_heal_both_bases_in_one_resolution(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        spy = _place(state, "P0", _get_card(repo, "TS26", "53"), "ground")
        for pid in ("P0", "P1"):
            state.player_by_id(pid).base_instance.damage = 5
        mine = state.player_by_id("P0").base_instance.instance_id
        theirs = state.player_by_id("P1").base_instance.instance_id
        state = _fire_when_played(state, spy)
        state = apply(state, ChooseTarget(mine))
        state = _drive(apply(state, ChooseTarget(theirs)))
        assert state.player_by_id("P0").base_instance.damage == 3
        assert state.player_by_id("P1").base_instance.damage == 3

    def test_TS26_53_second_step_cannot_re_pick_the_first_base(self, repo):
        from swu.engine.actions import apply, ChooseTarget, legal_actions
        state = _make_state()
        spy = _place(state, "P0", _get_card(repo, "TS26", "53"), "ground")
        for pid in ("P0", "P1"):
            state.player_by_id(pid).base_instance.damage = 5
        mine = state.player_by_id("P0").base_instance.instance_id
        state = apply(_fire_when_played(state, spy), ChooseTarget(mine))
        assert not any(isinstance(a, ChooseTarget) and a.target_id == mine
                       for a in legal_actions(state))


class TestWartimeMercenariesTS26_54:
    """When Defeated: an opponent may give an Experience token to a unit."""

    def test_TS26_54_hands_the_choice_to_the_opponent(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget
        state = _make_state()
        merc = _place(state, "P0", _get_card(repo, "TS26", "54"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, merc)
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.deciding_player_id == "P1"
        state = _drive(apply(state, SelectTokenTarget(theirs.instance_id)))
        assert any(u.card_def.display_name == "Experience"
                   for u in _find_instance(state, theirs.instance_id).attached_upgrades)


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:10 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


def _deploy_into_arena(state, leader_ci):
    """Move an already-placed leader out of the base zone and into the ground arena."""
    ps = state.player_by_id(leader_ci.owner_id)
    ps.base_zone.remove(leader_ci)
    leader_ci.deployed = True
    ps.ground_arena.append(leader_ci)
    return leader_ci


def _ready_unit_at_the_chokepoint(state, unit_ci):
    """Ready ``unit_ci`` through ``note_unit_readied`` (the ledger chokepoint the
    ReadyCard arm and the regroup mass-ready both use), then settle so the drain
    fires the observer on a clean stack."""
    from swu.engine.actions import note_unit_readied, apply, Pass
    note_unit_readied(state, unit_ci)      # called BEFORE clearing `exhausted`
    unit_ci.exhausted = False
    return apply(state, Pass())


class TestJediGeneralTS26_55:
    """When Played: per Republic leader you control, a Clone Trooper + Experience."""

    def test_TS26_55_creates_one_tokened_clone_per_republic_leader(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "TS26", "4"))   # Padmé, Republic
        general = _place(state, "P0", _get_card(repo, "TS26", "55"), "ground")
        state = _drive(_fire_when_played(state, general))
        clones = [u for u in state.player_by_id("P0").ground_arena
                  if u.card_def.display_name == "Clone Trooper"]
        assert len(clones) == 1
        assert sum(1 for up in clones[0].attached_upgrades
                   if up.card_def.display_name == "Experience") == 1

    def test_TS26_55_counts_a_deployed_republic_leader_as_a_unit(self, repo):
        state = _make_state()
        padme = _place_leader(state, "P0", _get_leader(repo, "TS26", "4"))
        _deploy_into_arena(state, padme)
        general = _place(state, "P0", _get_card(repo, "TS26", "55"), "ground")
        state = _drive(_fire_when_played(state, general))
        assert sum(1 for u in state.player_by_id("P0").ground_arena
                   if u.card_def.display_name == "Clone Trooper") == 1

    def test_TS26_55_makes_nothing_without_a_republic_leader(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_leader(repo, "TS26", "5"))   # Savage, not Republic
        general = _place(state, "P0", _get_card(repo, "TS26", "55"), "ground")
        state = _drive(_fire_when_played(state, general))
        assert not any(u.card_def.display_name == "Clone Trooper"
                       for u in state.player_by_id("P0").ground_arena)


class TestBrothersTS26_59:
    """Attack with up to 2 unique units; prevent all combat damage to them."""

    def test_TS26_59_offers_only_unique_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        uniq = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")   # unique
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not
        for u in (uniq, plain):
            u.exhausted = False
        state, _ev = _play_event_from_hand(state, repo, "TS26", "59")
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert uniq.instance_id in attackers
        assert plain.instance_id not in attackers

    def test_TS26_59_attacker_takes_no_combat_damage_and_repeats_once(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        uniq = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")   # 4/5
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        uniq.exhausted = False
        state, _ev = _play_event_from_hand(state, repo, "TS26", "59")
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == uniq.instance_id
                   and a.defender_id == defender.instance_id)
        state = _drive(apply(state, act), _decline_triggers())
        survivor = _find_instance(state, uniq.instance_id)
        assert survivor is not None and survivor.damage == 0   # 3 combat damage prevented
        assert _find_instance(state, defender.instance_id).damage == 4  # his hit lands


class TestTakeChargeTS26_60:
    """Costs 1 less per friendly leader unit; Experience to up to 3 units."""

    def test_TS26_60_tokens_up_to_three_units(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "60")
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.context["remaining"] == 3
        state = apply(state, SelectTokenTarget(a.instance_id))
        # Two units on the board, so the second pick exhausts the pool and the
        # decision auto-resolves ? no FinishSelectToken is offered (or legal).
        state = _drive(apply(state, SelectTokenTarget(b.instance_id)))
        for ci in (a, b):
            assert any(u.card_def.display_name == "Experience"
                       for u in _find_instance(state, ci.instance_id).attached_upgrades)

    def test_TS26_60_costs_one_less_per_friendly_leader_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "60"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, card, ps)
        _deploy_into_arena(state, _place_leader(state, "P0",
                                                _get_leader(repo, "TS26", "5")))
        assert _play_cost(state, card, ps) == before - 1


class TestEncircleTS26_61:
    """Costs 1 less per friendly unit; a friendly unit captures a same-arena enemy."""

    def test_TS26_61_costs_one_less_for_each_friendly_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "61"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, card, ps)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "TS26", "18"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # enemy: no help
        assert _play_cost(state, card, ps) == before - 2

    def test_TS26_61_captures_a_same_arena_enemy_under_a_friendly_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        prey = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        _place(state, "P1", _get_card(repo, "TS26", "18"), "space")   # wrong arena
        state, _ev = _play_event_from_hand(state, repo, "TS26", "61")
        state = apply(state, ChooseTarget(captor.instance_id))
        state = _drive(apply(state, ChooseTarget(prey.instance_id)))
        assert _find_instance(state, prey.instance_id) is None
        assert any(c.instance_id == prey.instance_id
                   for c in state.player_by_id("P0").capture_pile)


class TestRexsDC17sTS26_63:
    """Attached unit gains: when an enemy unit readies in the action phase, ready
    this unit — once each round."""

    def _armed(self, repo):
        from swu.engine.state import Phase
        state = _make_state()
        state.phase = Phase.ACTION
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        saber = _place(state, "P0", _get_card(repo, "TS26", "63"), "ground")
        state.player_by_id("P0").ground_arena.remove(saber)
        host.attached_upgrades.append(saber)
        host.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        enemy.exhausted = True
        return state, host, enemy

    def test_TS26_63_readies_the_host_when_an_enemy_unit_readies(self, repo):
        state, host, enemy = self._armed(repo)
        state = _ready_unit_at_the_chokepoint(state, enemy)
        assert _find_instance(state, host.instance_id).exhausted is False

    def test_TS26_63_only_fires_once_each_round(self, repo):
        state, host, enemy = self._armed(repo)
        state = _ready_unit_at_the_chokepoint(state, enemy)
        host2 = _find_instance(state, host.instance_id)
        host2.exhausted = True
        enemy2 = _find_instance(state, enemy.instance_id)
        enemy2.exhausted = True
        state = _ready_unit_at_the_chokepoint(state, enemy2)
        assert _find_instance(state, host.instance_id).exhausted is True

    def test_TS26_63_ignores_a_regroup_ready(self, repo):
        """The mass-ready is drained AFTER the rollover into ACTION, so the phase
        must be read off the ledger entry rather than at drain time."""
        from swu.engine.state import Phase
        state, host, enemy = self._armed(repo)
        state.phase = Phase.REGROUP
        from swu.engine.actions import note_unit_readied
        note_unit_readied(state, enemy)
        enemy.exhausted = False
        state.phase = Phase.ACTION
        from swu.engine.actions import apply, Pass
        state = apply(state, Pass())
        assert _find_instance(state, host.instance_id).exhausted is True

    def test_TS26_63_ignores_a_friendly_unit_readying(self, repo):
        state, host, _enemy = self._armed(repo)
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        friend.exhausted = True
        state = _ready_unit_at_the_chokepoint(state, friend)
        assert _find_instance(state, host.instance_id).exhausted is True


class TestJangoFettTS26_75:
    """Ambush while an enemy unit attacked your base this phase; On Attack −3/−0."""

    def test_TS26_75_gains_ambush_only_after_your_base_is_attacked(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        jango = _place(state, "P0", _get_card(repo, "TS26", "75"), "ground")
        assert not has_keyword(state, jango, Keyword.AMBUSH)
        state.game_memory.base_attackers_this_round.setdefault("P0", []).append("x")
        assert has_keyword(state, jango, Keyword.AMBUSH)

    def test_TS26_75_on_attack_debuffs_an_enemy_unit_for_the_phase(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        jango = _place(state, "P0", _get_card(repo, "TS26", "75"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, victim)
        state = _drive(apply(_fire_on_attack(state, jango),
                             ChooseTarget(victim.instance_id)))
        after = _find_instance(state, victim.instance_id)
        assert compute_power(state, after) == max(0, before - 3)


class TestWartimeProfiteerTS26_76:
    """When Defeated: each opponent may ready a resource."""

    def test_TS26_76_readies_one_opponent_resource(self, repo):
        state = _make_state()
        merc = _place(state, "P0", _get_card(repo, "TS26", "76"), "ground")
        _give_resources(state, "P1", 3)
        _give_resources(state, "P0", 3)
        for ps in state.players:
            for r in ps.resources:
                r.exhausted = True
        state = _drive(_fire_when_defeated(state, merc))
        assert state.player_by_id("P1").available_resources == 1
        assert state.player_by_id("P0").available_resources == 0   # not the controller


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:11 — combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestDeployedDroidekaTS26_77:
    """When Played: you may pay 2; if you do, an Experience + a Shield on itself."""

    def test_TS26_77_paying_two_tokens_itself(self, repo):
        from swu.engine.actions import apply, AcceptTrigger, legal_actions
        state = _make_state()
        droideka = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        _give_resources(state, "P0", 4)
        state = _fire_when_played(state, droideka)
        act = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = _drive(apply(state, act))
        after = _find_instance(state, droideka.instance_id)
        names = [u.card_def.display_name for u in after.attached_upgrades]
        assert "Experience" in names and "Shield" in names
        assert state.player_by_id("P0").available_resources == 2

    def test_TS26_77_not_offered_without_two_ready_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        droideka = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        _give_resources(state, "P0", 1)
        state = _fire_when_played(state, droideka)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not _find_instance(state, droideka.instance_id).attached_upgrades


class TestBarrissOfeeTS26_78:
    """When an enemy unit attacks: you may give an Experience token to that unit."""

    def test_TS26_78_offers_a_token_to_the_attacking_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TS26", "78"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        attacker.exhausted = False
        state.active_player_index = state.player_index("P1")
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id is None)
        state = apply(state, act)
        accept = next((a for a in legal_actions(state)
                       if isinstance(a, AcceptTrigger)), None)
        assert accept is not None
        state = _drive(apply(state, accept))
        assert any(u.card_def.display_name == "Experience"
                   for u in _find_instance(state, attacker.instance_id).attached_upgrades)

    def test_TS26_78_does_not_fire_for_a_friendly_attacker(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "TS26", "78"), "ground")
        friend = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        friend.exhausted = False
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == friend.instance_id
                   and a.defender_id is None)
        state = apply(state, act)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestMisleadTS26_81:
    """Give a Shield to a unit.  Give a unit -3/-0 for this phase."""

    def test_TS26_81_shields_one_unit_and_debuffs_another(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        before = compute_power(state, theirs)
        state, _ev = _play_event_from_hand(state, repo, "TS26", "81")
        state = apply(state, ChooseTarget(mine.instance_id))
        state = _drive(apply(state, ChooseTarget(theirs.instance_id)))
        assert any(u.card_def.display_name == "Shield"
                   for u in _find_instance(state, mine.instance_id).attached_upgrades)
        assert compute_power(state, _find_instance(state, theirs.instance_id)) == (
            max(0, before - 3))


class TestEvadeArrestTS26_82:
    """Exhaust any number of non-unique units."""

    def test_TS26_82_exhausts_only_non_unique_units(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget, legal_actions
        state = _make_state()
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        uniq = _place(state, "P1", _get_card(repo, "SOR", "47"), "ground")
        for u in (plain, uniq):
            u.exhausted = False
        state, _ev = _play_event_from_hand(state, repo, "TS26", "82")
        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert plain.instance_id in offered and uniq.instance_id not in offered
        state = _drive(apply(state, SelectTokenTarget(plain.instance_id)))
        assert _find_instance(state, plain.instance_id).exhausted is True
        assert _find_instance(state, uniq.instance_id).exhausted is False


class TestTakeAimTS26_83:
    """Costs 1 less per friendly leader unit; attack at +2/+0 with Saboteur."""

    def test_TS26_83_grants_saboteur_and_two_power_for_the_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        defender = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        from swu.engine.tokens import attach_token
        attach_token(state, state.player_by_id("P1"), defender, "Shield")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "83")
        assert state.pending_decisions[-1].kind == "granted_attack"
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = _drive(apply(state, act), _decline_triggers())
        # 3 + 2 = 5 power, Saboteur strips the Shield first, so the 3hp unit dies.
        assert _find_instance(state, defender.instance_id) is None

    def test_TS26_83_costs_one_less_per_friendly_leader_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "83"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, card, ps)
        _deploy_into_arena(state, _place_leader(state, "P0",
                                                _get_leader(repo, "TS26", "5")))
        assert _play_cost(state, card, ps) == before - 1


class TestFearlessAttackTS26_84:
    """Attack with a unit; +1/+0 per unit the defending player controls."""

    def test_TS26_84_scales_with_the_defending_players_whole_board(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        attacker.exhausted = False
        # Three enemy units, one of them in the OTHER arena — "the defending
        # PLAYER", not "that arena", so all three count.
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        _place(state, "P1", _get_card(repo, "TS26", "18"), "space")
        state, _ev = _play_event_from_hand(state, repo, "TS26", "84")
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = _drive(apply(state, act), _decline_triggers())
        # 3 base + 3 (three enemy units) = 6 damage on a 7hp defender.
        assert _find_instance(state, defender.instance_id).damage == 6


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:12 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


class TestYodaTS26_14:
    """Costs 2 less at 7+ resources; When Played/When Defeated a Sentinel clone."""

    def test_TS26_14_when_played_makes_a_sentinel_clone_trooper(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        yoda = _place(state, "P0", _get_card(repo, "TS26", "14"), "ground")
        state = _drive(_fire_when_played(state, yoda))
        clones = [u for u in state.player_by_id("P0").ground_arena
                  if u.card_def.display_name == "Clone Trooper"]
        assert len(clones) == 1
        assert has_keyword(state, clones[0], Keyword.SENTINEL)

    def test_TS26_14_when_defeated_makes_one_too(self, repo):
        state = _make_state()
        yoda = _place(state, "P0", _get_card(repo, "TS26", "14"), "ground")
        state = _drive(_fire_when_defeated(state, yoda))
        assert sum(1 for u in state.player_by_id("P0").ground_arena
                   if u.card_def.display_name == "Clone Trooper") == 1

    def test_TS26_14_costs_two_less_at_seven_resources(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "14"))
        ps = state.player_by_id("P0")
        _give_resources(state, "P0", 6)
        before = _play_cost(state, card, ps)
        _give_resources(state, "P0", 1)
        assert _play_cost(state, card, ps) == before - 2


class TestFortuneAndGloryTS26_27:
    """When Played: this unit captures a non-leader unit.  Bounty: a friendly unit
    captures a non-leader unit."""

    def test_TS26_27_when_played_captures_under_itself(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "TS26", "27"), "space")
        prey = _place(state, "P1", _get_card(repo, "TS26", "77"), "ground")
        state = _drive(apply(_fire_when_played(state, ship),
                             ChooseTarget(prey.instance_id)))
        assert _find_instance(state, prey.instance_id) is None
        assert any(c.instance_id == prey.instance_id
                   for c in state.player_by_id("P0").capture_pile)

    def test_TS26_27_bounty_captures_for_the_opponent(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "TS26", "27"), "space")
        collector_unit = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P0", _get_card(repo, "TS26", "77"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), ship)
        state = _drive(state)
        # The bounty resolves for P1: their unit captures P0's non-leader unit.
        assert _find_instance(state, victim.instance_id) is None
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P1").capture_pile)
        assert collector_unit.instance_id is not None


class TestFivesTS26_34:
    """Enter play with another unit in play's When Played abilities."""

    def test_TS26_34_borrows_another_units_when_played_ability(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        fives = _place(state, "P0", _get_card(repo, "TS26", "34"), "ground")
        # Twilight TS26_41: "When Played: if 5+ cards in your discard, heal 3 from
        # your base" — a no-target When Played whose effect is easy to observe.
        lender = _place(state, "P0", _get_card(repo, "TS26", "41"), "space")
        ps = state.player_by_id("P0")
        ps.base_instance.damage = 6
        from swu.engine.state import CardInstance, Zone
        for i in range(5):
            ps.discard.append(CardInstance(f"dd{i}", _get_card(repo, "SOR", "46"),
                                           "P0", Zone.DISCARD))
        state = _fire_when_played(state, fives)
        act = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, act)
        state = _drive(apply(state, ChooseTarget(lender.instance_id)))
        assert state.player_by_id("P0").base_instance.damage == 3

    def test_TS26_34_only_offers_units_that_have_a_when_played_ability(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        fives = _place(state, "P0", _get_card(repo, "TS26", "34"), "ground")
        lender = _place(state, "P0", _get_card(repo, "TS26", "41"), "space")
        vanilla = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, fives)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert lender.instance_id in offered
        assert vanilla.instance_id not in offered
        assert fives.instance_id not in offered      # "ANOTHER unit in play"


class TestTribunalTS26_36:
    """Costs 2 less per other card played this phase; When Played each other unit
    gets -2/-2."""

    def test_TS26_36_costs_two_less_per_other_card_played_this_phase(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        card = _put_in_hand(state, "P0", _get_card(repo, "TS26", "36"))
        ps = state.player_by_id("P0")
        before = _play_cost(state, card, ps)
        state.game_memory.cards_played_this_phase["P0"] = 3
        assert _play_cost(state, card, ps) == before - 6

    def test_TS26_36_debuffs_every_other_unit_but_not_itself(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        tribunal = _place(state, "P0", _get_card(repo, "TS26", "36"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drive(_fire_when_played(state, tribunal))
        for ci in (friend, enemy):
            after = _find_instance(state, ci.instance_id)
            assert compute_power(state, after) == 1 and compute_hp(state, after) == 5
        me = _find_instance(state, tribunal.instance_id)
        assert compute_power(state, me) == 6


class TestWartimeRefugeeTS26_43:
    """On Attack: an opponent heals 1 from their base."""

    def test_TS26_43_heals_the_opponents_base_on_attack(self, repo):
        state = _make_state()
        refugee = _place(state, "P0", _get_card(repo, "TS26", "43"), "ground")
        state.player_by_id("P1").base_instance.damage = 4
        state.player_by_id("P0").base_instance.damage = 4
        state = _drive(_fire_on_attack(state, refugee))
        assert state.player_by_id("P1").base_instance.damage == 3
        assert state.player_by_id("P0").base_instance.damage == 4   # not yours


class TestVanquishTheLegionTS26_48:
    """Give each enemy ground unit -2/-2 for this phase."""

    def test_TS26_48_hits_only_enemy_ground_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        space = _place(state, "P1", _get_card(repo, "TS26", "18"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        space_before = compute_power(state, space)
        state, _ev = _drive_event(state, repo, "TS26", "48")
        assert compute_power(state, _find_instance(state, ground.instance_id)) == 1
        assert compute_power(state, _find_instance(state, space.instance_id)) == (
            space_before)
        assert compute_power(state, _find_instance(state, friend.instance_id)) == 3


class TestGalacticEscalationTS26_56:
    """Each player resources the top card of their deck."""

    def test_TS26_56_ramps_both_players(self, repo):
        """Asserted by IDENTITY, not by row size: _play_event_from_hand hands
        the controller resources to pay the cost."""
        state = _make_state()
        tops = {pid: _push_deck_top(state, pid, _get_card(repo, "SOR", "46"))
                for pid in ("P0", "P1")}
        state, _ev = _drive_event(state, repo, "TS26", "56")
        for pid, top in tops.items():
            ps = state.player_by_id(pid)
            tid = top.instance_id if hasattr(top, "instance_id") else top
            landed = [r for r in ps.resources if r.instance_id == tid]
            assert len(landed) == 1 and landed[0].face_down
            assert all(c.instance_id != tid for c in ps.deck)


# ══════════════════════════════════════════════════════════════════════════════
# ts26-set:13 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


class TestWartimePirateTS26_66:
    """On Attack: an opponent deals 1 damage to a unit."""

    def test_TS26_66_hands_the_damage_choice_to_the_opponent(self, repo):
        from swu.engine.actions import apply, SelectDamageTarget
        state = _make_state()
        pirate = _place(state, "P0", _get_card(repo, "TS26", "66"), "space")
        victim = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, pirate)
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage" and top.deciding_player_id == "P1"
        state = _drive(apply(state, SelectDamageTarget(victim.instance_id)))
        assert _find_instance(state, victim.instance_id).damage == 1


class TestRevealIntentionsTS26_80:
    """Each player discards a card from the other's hand, then each draws."""

    def test_TS26_80_each_player_strips_the_other_and_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        for pid in ("P0", "P1"):
            for _i in range(2):
                _put_in_hand(state, pid, _get_card(repo, "SOR", "46"))
            _push_deck_top(state, pid, _get_card(repo, "TS26", "77"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "80")
        # The controller names first (LIFO: pushed in reverse seat order).
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard" and top.deciding_player_id == "P0"
        act = next(a for a in legal_actions(state) if isinstance(a, NameAndDiscard))
        state = apply(state, act)
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard" and top.deciding_player_id == "P1"
        act = next(a for a in legal_actions(state) if isinstance(a, NameAndDiscard))
        state = _drive(apply(state, act))
        for pid in ("P0", "P1"):
            ps = state.player_by_id(pid)
            # Started with 2 in hand (P0 also had the event, now spent), lost one to
            # the opponent's pick and drew one back.
            assert len(ps.discard) >= 1
            assert any(c.card_def.display_name == "Deployed Droideka"
                       for c in ps.hand)

    def test_TS26_80_fizzles_a_seat_whose_opponent_has_no_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state, _ev = _play_event_from_hand(state, repo, "TS26", "80")
        # P0's hand is empty once the event is spent, so only P0's own pick is
        # pushed — P1 has nothing to name.
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard" and top.deciding_player_id == "P0"
        state = _drive(apply(state, next(
            a for a in legal_actions(state) if isinstance(a, NameAndDiscard))))
        assert not any(d.kind == "name_and_discard" for d in state.pending_decisions)
        assert len(state.player_by_id("P1").hand) == 0
