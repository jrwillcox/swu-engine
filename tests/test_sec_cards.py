"""SEC (Secrets of Power) card ability tests — the all-sets ``sec-set`` campaign.

SEC cards belonging to a *precon deck* are tested in that deck's module
(``test_chancellor_palpatine_cards.py``, ``test_padme_amidala_cards.py``,
``test_law_cards.py``); this module holds the set-sweep groups.  Method names embed
the card number so the encoding verifier's ``-k`` gate selects them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_when_defeated,
    _fire_upgrade_played,
    _fire_on_attack, _find_instance, _give_resources, _play_event_from_hand,
    _push_deck_top, _place_leader, _accept_optional_and_run,
)
from tests.test_shd_cards import _put_in_hand, _attach_upgrade_directly


def _deploy(state, owner, leader_def, arena="ground"):
    """Place a leader directly into an arena as a DEPLOYED leader unit (ready)."""
    ci = _place(state, owner, leader_def, arena)
    ci.deployed = True
    ci.exhausted = False
    return ci


def _use(state, source_ci, idx=None):
    """Apply the ``UseAbility`` offered for ``source_ci`` (optionally the one whose
    ability_idx is ``idx``)."""
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility)
               and a.source_id == source_ci.instance_id
               and (idx is None or a.ability_idx == idx))
    return apply(state, use)


def _choose(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, act)


def _drain(state):
    """Auto-resolve any AutoResolveEffects / auto-continuations left on the stack."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(12):
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        if auto is None:
            return state
        state = apply(state, auto)
    return state


# ── sec-set:01 — Direct damage & removal ──────────────────────────────────────

class TestJabbaTheHutt_SEC_2:
    """Undeployed Action: a friendly damaged unit deals 1 (2 if it has 3+ damage)
    to an enemy unit.  Deployed: once each round, a friendly unit dealt combat
    damage that survives may deal that much to an enemy unit."""

    def test_SEC_2_damaged_friendly_deals_1_to_enemy(self, repo):
        state = _make_state()
        jabba = _place_leader(state, "P0", _get_card(repo, "SEC", "2"))
        _give_resources(state, "P0", 3)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly.damage = 1
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, jabba)
        state = _choose(state, friendly.instance_id)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_SEC_2_three_damage_friendly_deals_2(self, repo):
        state = _make_state()
        jabba = _place_leader(state, "P0", _get_card(repo, "SEC", "2"))
        _give_resources(state, "P0", 3)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly.damage = 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, jabba)
        state = _choose(state, friendly.instance_id)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_SEC_2_only_damaged_friendlies_are_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        jabba = _place_leader(state, "P0", _get_card(repo, "SEC", "2"))
        _give_resources(state, "P0", 3)
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 2
        healthy = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, jabba)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert hurt.instance_id in offered
        assert healthy.instance_id not in offered

    def test_SEC_2_deployed_retaliates_for_combat_damage(self, repo):
        """A friendly unit dealt 3 combat damage that survives may deal 3 back."""
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        jabba = _deploy(state, "P0", _get_card(repo, "SEC", "2"))
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to": hurt.instance_id,
                       "combat_damage_amount": 3})
        state = _accept_optional_and_run(state)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 3
        # The round's single use is now spent — a second hit offers nothing.
        state2 = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to": hurt.instance_id,
                       "combat_damage_amount": 2})
        from swu.engine.actions import legal_actions, AcceptTrigger
        assert not any(isinstance(a, AcceptTrigger)
                       and a.source_id == jabba.instance_id
                       for a in legal_actions(state2))


class TestLamaSu_SEC_3:
    """Undeployed Action: play an upgrade from hand on a friendly non-Vehicle unit
    for 1 less; if you do, deal 1 damage to it."""

    def test_SEC_3_plays_hand_upgrade_discounted_and_damages_host(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        state = _make_state()
        lama = _place_leader(state, "P0", _get_card(repo, "SEC", "3"))
        _give_resources(state, "P0", 10)
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # non-Vehicle
        upg = _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))       # an upgrade
        state = _use(state, lama)
        state = _choose(state, host.instance_id)
        top = state.pending_decisions[-1]
        assert top.kind == "play_upgrade_from_hand"
        assert top.context["cost_reduction"] == 1
        assert top.context["then_damage_host"] == 1
        assert top.context["host_id"] == host.instance_id
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayUpgradeFromHand)
                    and a.upgrade_id == upg.instance_id)
        state = apply(state, play)
        assert _find_instance(state, host.instance_id).damage == 1

    def test_SEC_3_only_non_vehicle_friendlies_are_hosts(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        lama = _place_leader(state, "P0", _get_card(repo, "SEC", "3"))
        _give_resources(state, "P0", 10)
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))
        ok = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, "SOR", "232"), "ground")  # AT-ST
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, lama)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ok.instance_id in offered
        assert vehicle.instance_id not in offered
        assert enemy.instance_id not in offered

    def test_SEC_3_deployed_plays_upgrade_from_discard(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        lama = _deploy(state, "P0", _get_card(repo, "SEC", "3"))
        _give_resources(state, "P0", 10)
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        disc = CardInstance("P0_disc_upg", _get_card(repo, "SOR", "53"), "P0",
                            Zone.DISCARD)
        state.player_by_id("P0").discard.append(disc)
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_ended_survivor": lama.instance_id})
        state = _accept_optional_and_run(state)
        state = _choose(state, host.instance_id)
        top = state.pending_decisions[-1]
        assert top.kind == "play_upgrade_from_hand"
        assert top.context["from_discard_only"] is True
        assert top.context["cost_reduction"] == 1


class TestSatineKryze_SEC_5:
    """Undeployed Action: heal up to 2 from a unit, then deal that much to your base."""

    def test_SEC_5_heals_2_and_self_damages_base(self, repo):
        state = _make_state()
        satine = _place_leader(state, "P0", _get_card(repo, "SEC", "5"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit.damage = 4
        base_before = state.player_by_id("P0").base_instance.damage
        state = _use(state, satine)
        state = _choose(state, unit.instance_id)
        assert _find_instance(state, unit.instance_id).damage == 2
        assert state.player_by_id("P0").base_instance.damage == base_before + 2

    def test_SEC_5_heals_only_what_is_there(self, repo):
        """A unit with 1 damage heals 1, so the base takes only 1."""
        state = _make_state()
        satine = _place_leader(state, "P0", _get_card(repo, "SEC", "5"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit.damage = 1
        base_before = state.player_by_id("P0").base_instance.damage
        state = _use(state, satine)
        state = _choose(state, unit.instance_id)
        assert _find_instance(state, unit.instance_id).damage == 0
        assert state.player_by_id("P0").base_instance.damage == base_before + 1

    def test_SEC_5_undamaged_units_are_not_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        satine = _place_leader(state, "P0", _get_card(repo, "SEC", "5"))
        healthy = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 2
        state = _use(state, satine)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert hurt.instance_id in offered
        assert healthy.instance_id not in offered


class TestDedraMeero_SEC_10:
    """Undeployed Action: an enemy unit's controller may deal 2 damage to it; if
    they don't, you draw.  Deployed: Raid 2 while you hold more cards."""

    def test_SEC_10_opponent_allows_and_takes_2(self, repo):
        from swu.engine.actions import legal_actions, apply, AllowEffect
        state = _make_state()
        dedra = _place_leader(state, "P0", _get_card(repo, "SEC", "10"))
        _give_resources(state, "P0", 3)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, dedra)
        state = _choose(state, enemy.instance_id)
        assert state.pending_decisions[-1].kind == "say_no"
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        allow = next(a for a in legal_actions(state) if isinstance(a, AllowEffect))
        state = apply(state, allow)
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_SEC_10_opponent_refuses_and_controller_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, SayNo
        state = _make_state()
        dedra = _place_leader(state, "P0", _get_card(repo, "SEC", "10"))
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hand_before = len(state.player_by_id("P0").hand)
        state = _use(state, dedra)
        state = _choose(state, enemy.instance_id)
        refuse = next(a for a in legal_actions(state) if isinstance(a, SayNo))
        state = apply(state, refuse)
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert len(state.player_by_id("P0").hand) == hand_before + 1

    def test_SEC_10_deployed_raid_2_only_with_a_bigger_hand(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        dedra = _deploy(state, "P0", _get_card(repo, "SEC", "10"))
        filler = _get_card(repo, "SOR", "46")
        _put_in_hand(state, "P1", filler)
        assert keyword_value(state, dedra, Keyword.RAID) == 0, "equal/smaller hand"
        for _ in range(2):
            _put_in_hand(state, "P0", filler)
        assert keyword_value(state, dedra, Keyword.RAID) == 2


class TestLuthenRael_SEC_13:
    """Both sides trigger on a friendly unit defeated WHILE ATTACKING."""

    def _frail(self, state, ci):
        """Pre-damage ``ci`` to 1 remaining HP so any combat kills it."""
        from swu.engine.actions import compute_hp
        ci.damage = compute_hp(state, ci) - 1
        return ci

    def _attack_into_death(self, state, attacker, defender):
        """Attack with ``attacker`` into a defender big enough to kill it, driving
        the real combat pipeline so the while-attacking flag is stamped."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        return apply(state, act)

    def test_SEC_13_undeployed_exhausts_and_deals_1(self, repo):
        state = _make_state()
        luthen = _place_leader(state, "P0", _get_card(repo, "SEC", "13"))
        attacker = self._frail(
            state, _place(state, "P0", _get_card(repo, "SOR", "46"), "ground"))
        killer = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._attack_into_death(state, attacker, killer)
        assert _find_instance(state, attacker.instance_id) is None, "attacker died"
        state = _accept_optional_and_run(state)
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 1
        live_luthen = next(c for c in state.player_by_id("P0").base_zone
                           if c.instance_id == luthen.instance_id)
        assert live_luthen.exhausted is True, "the leader paid its exhaust"

    def test_SEC_13_deployed_deals_2(self, repo):
        state = _make_state()
        _deploy(state, "P0", _get_card(repo, "SEC", "13"))
        attacker = self._frail(
            state, _place(state, "P0", _get_card(repo, "SOR", "46"), "ground"))
        killer = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._attack_into_death(state, attacker, killer)
        state = _accept_optional_and_run(state)
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 2

    def test_SEC_13_does_not_fire_for_a_defender_death(self, repo):
        """A friendly unit defeated while DEFENDING is not "while attacking"."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        luthen = _place_leader(state, "P0", _get_card(repo, "SEC", "13"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # P1 attacks and kills a friendly (P0) defender.
        state.active_player_index = 1
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        defender = self._frail(
            state, _place(state, "P0", _get_card(repo, "SOR", "46"), "ground"))
        state = self._attack_into_death(state, attacker, defender)
        assert _find_instance(state, defender.instance_id) is None
        assert not any(isinstance(a, AcceptTrigger)
                       and a.source_id == luthen.instance_id
                       for a in legal_actions(state))


class TestSlyMoore_SEC_14:
    """Undeployed Action: 4+ exhausted units in play → create a Spy token.
    Deployed: On Attack, you may deal 2 damage to an exhausted unit."""

    def _spy_count(self, state, owner="P0"):
        ps = state.player_by_id(owner)
        return sum(1 for u in ps.ground_arena + ps.space_arena
                   if u.card_def.name == "Spy")

    def test_SEC_14_creates_spy_with_four_exhausted_units(self, repo):
        state = _make_state()
        sly = _place_leader(state, "P0", _get_card(repo, "SEC", "14"))
        _give_resources(state, "P0", 3)
        filler = _get_card(repo, "SOR", "46")
        for owner in ("P0", "P0", "P1", "P1"):
            _place(state, owner, filler, "ground").exhausted = True
        before = self._spy_count(state)
        state = _drain(_use(state, sly))
        assert self._spy_count(state) == before + 1

    def test_SEC_14_no_spy_below_the_threshold(self, repo):
        """Three exhausted units — the Action is still legal but creates nothing."""
        state = _make_state()
        sly = _place_leader(state, "P0", _get_card(repo, "SEC", "14"))
        _give_resources(state, "P0", 3)
        filler = _get_card(repo, "SOR", "46")
        for owner in ("P0", "P0", "P1"):
            _place(state, owner, filler, "ground").exhausted = True
        state = _drain(_use(state, sly))
        assert self._spy_count(state) == 0

    def test_SEC_14_deployed_damages_only_exhausted_units(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        sly = _deploy(state, "P0", _get_card(repo, "SEC", "14"))
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        fresh = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, sly)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {tired.instance_id}
        state = _choose(state, tired.instance_id)
        assert _find_instance(state, tired.instance_id).damage == 2
        assert _find_instance(state, fresh.instance_id).damage == 0


class TestCreditorsClaim_SEC_39:
    """Attached unit gains: 'When Defeated: You may defeat a unit with 3 or less
    remaining HP.'"""

    def test_SEC_39_host_defeat_offers_a_low_hp_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "39"), "P0")
        frail = _place(state, "P1", _get_card(repo, "SOR", "197"), "ground")
        frail.damage = max(0, frail.card_def.hp - 3)
        state = _fire_when_defeated(state, host)
        state = _accept_optional_and_run(state)
        state = _choose(state, frail.instance_id)
        assert _find_instance(state, frail.instance_id) is None

    def test_SEC_39_ignores_units_above_3_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "39"), "P0")
        frail = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        frail.damage = max(0, frail.card_def.hp - 3)
        beefy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, host)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert frail.instance_id in offered
        assert beefy.instance_id not in offered

    def test_SEC_39_no_trigger_without_the_upgrade(self, repo):
        """The ability is granted BY the upgrade — a bare host has none."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        frail = _place(state, "P1", _get_card(repo, "SOR", "197"), "ground")
        frail.damage = max(0, frail.card_def.hp - 3)
        state = _fire_when_defeated(state, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── sec-set:02 — Direct damage & removal ──────────────────────────────────────

class TestCassianAndor_SEC_42:
    """While defending, the attacker gets -2/-0.  Enemy card-ability damage to him
    is reduced by 2."""

    def test_SEC_42_attacker_gets_minus_2_while_he_defends(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        cassian = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert compute_power(state, attacker) == 3
        assert compute_power(state, attacker, defender_id=cassian.instance_id) == 1

    def test_SEC_42_prevents_2_of_enemy_ability_damage(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        cassian = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _apply_deal_damage(state, cassian.instance_id, 3, "Enemy",
                                   dealer_id=enemy.instance_id)
        assert _find_instance(state, cassian.instance_id).damage == 1

    def test_SEC_42_friendly_ability_damage_is_not_prevented(self, repo):
        """"an ENEMY card ability" — a friendly source is unaffected."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        cassian = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _apply_deal_damage(state, cassian.instance_id, 1, "Friend",
                                   dealer_id=friend.instance_id)
        assert _find_instance(state, cassian.instance_id).damage == 1

    def test_SEC_42_combat_damage_is_not_prevented(self, repo):
        """His rules insert: combat damage is not a card ability."""
        from swu.engine.actions import _deal_damage_with_shield
        state = _make_state()
        cassian = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")
        _deal_damage_with_shield(state, state.player_by_id("P0"), cassian, 2,
                                 is_combat=True)
        assert cassian.damage == 2


class TestVigil_SEC_50:
    """Prevent 1 of damage to another friendly unit; take 1 extra from other cards."""

    def test_SEC_50_prevents_1_for_another_friendly_unit(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "50"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _apply_deal_damage(state, friend.instance_id, 3, "Boom")
        assert _find_instance(state, friend.instance_id).damage == 2

    def test_SEC_50_does_not_protect_enemy_units(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "50"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _apply_deal_damage(state, enemy.instance_id, 3, "Boom")
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_SEC_50_takes_one_extra_itself(self, repo):
        """"another friendly unit" excludes Vigil, and its own clause adds 1."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        vigil = _place(state, "P0", _get_card(repo, "SEC", "50"), "space")
        other = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        state = _apply_deal_damage(state, vigil.instance_id, 3, "Boom",
                                   dealer_id=other.instance_id)
        assert _find_instance(state, vigil.instance_id).damage == 4

    def test_SEC_50_self_dealt_damage_is_not_amplified(self, repo):
        """"by another card" — Vigil damaging itself takes the plain amount."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        vigil = _place(state, "P0", _get_card(repo, "SEC", "50"), "space")
        state = _apply_deal_damage(state, vigil.instance_id, 3, "Vigil",
                                   dealer_id=vigil.instance_id)
        assert _find_instance(state, vigil.instance_id).damage == 3


class TestOneInAMillion_SEC_53:
    """Can't be played from hand; defeats a unit whose power AND remaining HP both
    equal your ready-resource count."""

    def test_SEC_53_is_not_offered_from_hand(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        ci = _put_in_hand(state, "P0", _get_card(repo, "SEC", "53"))
        _give_resources(state, "P0", 10)
        assert not any(isinstance(a, PlayCard) and a.instance_id == ci.instance_id
                       for a in legal_actions(state))

    def test_SEC_53_plot_play_defeats_only_the_matching_unit(self, repo):
        """End to end through the real Plot route (its only legal route): put One in
        a Million in the resource zone, deploy a leader, play it, and the defeat
        offers exactly the unit whose power AND remaining HP equal the ready-resource
        count left after paying."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlotPlay
        from tests.test_plot import _add_leader, _deploy as _deploy_leader, _synthetic_leader
        from tests.test_smuggle import _add_resource, _fill_resources, _add_deck_card
        state = _make_state()
        plot = _add_resource(state, "P0", _get_card(repo, "SEC", "53"))
        _fill_resources(state, "P0", 7, repo)   # leaves exactly 3 ready after
        for _ in range(3):                      # deploy (2) + One in a Million (5)
            _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))
        good = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 3/7
        good.damage = 4                        # power 3, remaining HP 3 — a match
        wrong_hp = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        wrong_power = _place(state, "P1", _get_card(repo, "SOR", "232"), "ground")
        wrong_power.damage = 4                 # 6 power, 3 HP left — power differs
        state = _deploy_leader(state)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == plot.instance_id)
        state = apply(state, play)
        assert sum(1 for r in state.player_by_id("P0").resources
                   if not r.exhausted) == 3
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {good.instance_id}
        assert wrong_hp.instance_id not in offered
        assert wrong_power.instance_id not in offered
        state = apply(state, ChooseTarget(good.instance_id))
        assert _find_instance(state, good.instance_id) is None


class TestHyperspaceDisaster_SEC_78:
    """Defeat all space units."""

    def test_SEC_78_clears_both_space_arenas_only(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "86"), "space")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "78", resources=12)
        state = _drain(state)
        assert _find_instance(state, mine.instance_id) is None
        assert _find_instance(state, theirs.instance_id) is None
        assert _find_instance(state, ground.instance_id) is not None


class TestArihndaPryce_SEC_136:
    """When Defeated: you may defeat another friendly unit; if you do, 4 to each
    enemy base."""

    def test_SEC_136_sacrifice_burns_the_enemy_base(self, repo):
        state = _make_state()
        pryce = _place(state, "P0", _get_card(repo, "SEC", "136"), "ground")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_base_before = state.player_by_id("P1").base_instance.damage
        own_base_before = state.player_by_id("P0").base_instance.damage
        state = _fire_when_defeated(state, pryce)
        state = _accept_optional_and_run(state)
        state = _choose(state, pal.instance_id)
        assert _find_instance(state, pal.instance_id) is None
        assert state.player_by_id("P1").base_instance.damage == enemy_base_before + 4
        assert state.player_by_id("P0").base_instance.damage == own_base_before

    def test_SEC_136_only_friendly_units_are_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        pryce = _place(state, "P0", _get_card(repo, "SEC", "136"), "ground")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, pryce)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {pal.instance_id}
        assert foe.instance_id not in offered

    def test_SEC_136_no_friendly_unit_means_no_offer(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        pryce = _place(state, "P0", _get_card(repo, "SEC", "136"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, pryce)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestMirajScintel_SEC_139:
    """Friendly attackers gain Overwhelm; When Played, 3 damage to an undamaged unit."""

    def test_SEC_139_grants_overwhelm_to_friendly_units(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "139"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, friend, Keyword.OVERWHELM)
        assert not has_keyword(state, foe, Keyword.OVERWHELM)

    def test_SEC_139_when_played_hits_only_undamaged_units(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        miraj = _place(state, "P0", _get_card(repo, "SEC", "139"), "ground")
        fresh = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hurt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 1
        state = _fire_when_played(state, miraj)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert fresh.instance_id in offered
        assert hurt.instance_id not in offered
        state = _choose(state, fresh.instance_id)
        assert _find_instance(state, fresh.instance_id).damage == 3


class TestTheEliteSquad_SEC_143:
    """When Played / when dealt combat damage: you may deal 2 to another unique unit."""

    def test_SEC_143_when_played_hits_a_unique_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        squad = _place(state, "P0", _get_card(repo, "SEC", "143"), "ground")
        unique = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")   # Luke
        common = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, squad)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert unique.instance_id in offered
        assert common.instance_id not in offered
        state = _choose(state, unique.instance_id)
        assert _find_instance(state, unique.instance_id).damage == 2

    def test_SEC_143_fires_again_on_combat_damage(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        squad = _place(state, "P0", _get_card(repo, "SEC", "143"), "ground")
        unique = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to": squad.instance_id,
                       "combat_damage_amount": 2})
        state = _accept_optional_and_run(state)
        state = _choose(state, unique.instance_id)
        assert _find_instance(state, unique.instance_id).damage == 2


# ── sec-set:03 — Direct damage & removal ──────────────────────────────────────

class TestTempestAssault_SEC_144:
    """If you dealt base damage this phase, 2 to each enemy space unit."""

    def test_SEC_144_hits_enemy_space_units_after_base_damage(self, repo):
        state = _make_state()
        foe_space = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        foe_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine_space = _place(state, "P0", _get_card(repo, "SOR", "86"), "space")
        state.game_memory.base_damage_dealt_this_phase["P0"] = 3
        state, _ = _play_event_from_hand(state, repo, "SEC", "144", resources=14)
        state = _drain(state)
        assert _find_instance(state, foe_space.instance_id).damage == 2
        assert _find_instance(state, foe_ground.instance_id).damage == 0
        assert _find_instance(state, mine_space.instance_id).damage == 0

    def test_SEC_144_does_nothing_without_base_damage(self, repo):
        state = _make_state()
        foe_space = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        state, _ = _play_event_from_hand(state, repo, "SEC", "144", resources=14)
        state = _drain(state)
        assert _find_instance(state, foe_space.instance_id).damage == 0


class TestKaydelConnix_SEC_149:
    """When Played: you may defeat all non-unique upgrades on a unit."""

    def test_SEC_149_strips_only_non_unique_upgrades(self, repo):
        state = _make_state()
        kaydel = _place(state, "P0", _get_card(repo, "SEC", "149"), "ground")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        uniq = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "53"), "P1")
        plain = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "39"), "P1")
        assert uniq.card_def.is_unique and not plain.card_def.is_unique
        state = _fire_when_played(state, kaydel)
        state = _accept_optional_and_run(state)
        state = _choose(state, host.instance_id)
        left = {u.instance_id
                for u in _find_instance(state, host.instance_id).attached_upgrades}
        assert plain.instance_id not in left
        assert uniq.instance_id in left

    def test_SEC_149_not_offered_with_no_strippable_upgrade(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        kaydel = _place(state, "P0", _get_card(repo, "SEC", "149"), "ground")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "53"), "P1")
        state = _fire_when_played(state, kaydel)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestValiantCommando_SEC_150:
    """When it deals combat damage to a base: you may defeat it for 3 more."""

    def test_SEC_150_self_defeat_burns_the_base_for_3(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        cmdo = _place(state, "P0", _get_card(repo, "SEC", "150"), "ground")
        before = state.player_by_id("P1").base_instance.damage
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": cmdo.instance_id,
                       "base_combat_damage_amount": 3})
        state = _accept_optional_and_run(state)
        assert _find_instance(state, cmdo.instance_id) is None
        assert state.player_by_id("P1").base_instance.damage == before + 3

    def test_SEC_150_does_not_fire_for_another_unit(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        cmdo = _place(state, "P0", _get_card(repo, "SEC", "150"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": other.instance_id,
                       "base_combat_damage_amount": 3})
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert _find_instance(state, cmdo.instance_id) is not None


class TestStrikeForceXWing_SEC_152:
    """When Played: you may deal 2 damage to a READY unit."""

    def test_SEC_152_only_ready_units_are_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "SEC", "152"), "space")
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        state = _fire_when_played(state, xwing)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ready.instance_id in offered
        assert tired.instance_id not in offered
        state = _choose(state, ready.instance_id)
        assert _find_instance(state, ready.instance_id).damage == 2


class TestAlexsandrKallus_SEC_155:
    """Initiative anthem for other unique friendlies; When Played spreads 2 damage."""

    def test_SEC_155_anthem_needs_initiative_and_uniqueness(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        kallus = _place(state, "P0", _get_card(repo, "SEC", "155"), "ground")
        uniq = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")   # Luke
        common = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.initiative_holder = state.player_index("P1")
        assert keyword_value(state, uniq, Keyword.RAID) == 0
        state.initiative_holder = state.player_index("P0")
        assert keyword_value(state, uniq, Keyword.RAID) == 2
        assert keyword_value(state, common, Keyword.RAID) == 0

    def test_SEC_155_when_played_spreads_2_to_up_to_3_ground_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectDamageTarget, FinishSelectDamage,
        )
        state = _make_state()
        kallus = _place(state, "P0", _get_card(repo, "SEC", "155"), "ground")
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        state = _fire_when_played(state, kallus)
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage"
        assert top.context["amount_each"] == 2
        offered = {act.target_id for act in legal_actions(state)
                   if isinstance(act, SelectDamageTarget)}
        assert space.instance_id not in offered, "ground units only"
        for u in (a, b):
            state = apply(state, next(act for act in legal_actions(state)
                                      if isinstance(act, SelectDamageTarget)
                                      and act.target_id == u.instance_id))
        state = apply(state, next(act for act in legal_actions(state)
                                  if isinstance(act, FinishSelectDamage)))
        assert _find_instance(state, a.instance_id).damage == 2
        assert _find_instance(state, b.instance_id).damage == 2
        assert _find_instance(state, space.instance_id).damage == 0


class TestNemiksManifesto_SEC_156:
    """Host gains the Rebel trait and a scaling When Defeated base burn."""

    def test_SEC_156_grants_the_rebel_trait_to_the_host(self, repo):
        from swu.engine.traits import get_traits
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "232"), "ground")  # AT-ST
        assert "Rebel" not in get_traits(state, host)
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "156"), "P0")
        assert "Rebel" in get_traits(state, host)

    def test_SEC_156_when_defeated_scales_with_other_rebels(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "232"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "156"), "P0")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # enemy Rebel
        before = state.player_by_id("P1").base_instance.damage
        own_before = state.player_by_id("P0").base_instance.damage
        state = _fire_when_defeated(state, host)
        state = _drain(state)
        assert state.player_by_id("P1").base_instance.damage == before + 2
        assert state.player_by_id("P0").base_instance.damage == own_before


class TestCrosshair_SEC_162:
    """On Attack: 1 to another friendly unit, then 2 to the enemy base."""

    def test_SEC_162_friendly_fire_then_base_burn(self, repo):
        state = _make_state()
        cross = _place(state, "P0", _get_card(repo, "SEC", "162"), "ground")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        before = state.player_by_id("P1").base_instance.damage
        state = _fire_on_attack(state, cross)
        state = _accept_optional_and_run(state)
        state = _choose(state, pal.instance_id)
        assert _find_instance(state, pal.instance_id).damage == 1
        assert state.player_by_id("P1").base_instance.damage == before + 2

    def test_SEC_162_never_targets_itself_or_enemies(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        cross = _place(state, "P0", _get_card(repo, "SEC", "162"), "ground")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, cross)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {pal.instance_id}

    def test_SEC_162_not_offered_alone(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        cross = _place(state, "P0", _get_card(repo, "SEC", "162"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, cross)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── sec-set:04 — Direct damage & removal ──────────────────────────────────────

class TestOuterRimConstable_SEC_163:
    """When Played: you may defeat an upgrade."""

    def test_SEC_163_defeats_a_chosen_upgrade(self, repo):
        state = _make_state()
        cop = _place(state, "P0", _get_card(repo, "SEC", "163"), "ground")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "53"), "P1")
        state = _fire_when_played(state, cop)
        state = _accept_optional_and_run(state)
        state = _choose(state, upg.instance_id)
        left = {u.instance_id
                for u in _find_instance(state, host.instance_id).attached_upgrades}
        assert upg.instance_id not in left

    def test_SEC_163_not_offered_with_no_upgrade(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        cop = _place(state, "P0", _get_card(repo, "SEC", "163"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, cop)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestWarriorOfClanOrdo_SEC_164:
    """On Attack: you may disclose Aggression; if you DON'T, take 2 on your base."""

    def test_SEC_164_declining_burns_your_own_base(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        warrior = _place(state, "P0", _get_card(repo, "SEC", "164"), "ground")
        before = state.player_by_id("P0").base_instance.damage
        state = _fire_on_attack(state, warrior)
        assert state.pending_decisions[-1].kind == "disclose"
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineDisclose))
        state = apply(state, decline)
        assert state.player_by_id("P0").base_instance.damage == before + 2

    def test_SEC_164_disclosing_costs_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DiscloseSelectCard
        state = _make_state()
        warrior = _place(state, "P0", _get_card(repo, "SEC", "164"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "155"))  # Aggression card
        before = state.player_by_id("P0").base_instance.damage
        state = _fire_on_attack(state, warrior)
        picks = [a for a in legal_actions(state) if isinstance(a, DiscloseSelectCard)]
        assert picks, "an Aggression card in hand can be disclosed"
        state = apply(state, picks[0])
        assert state.player_by_id("P0").base_instance.damage == before

    def test_SEC_164_still_prompts_with_an_uncoverable_hand(self, repo):
        """``always_offer`` — an empty hand cannot disclose, but the penalty must
        still be reachable, so the decision is pushed with only the Decline."""
        from swu.engine.actions import legal_actions, DiscloseSelectCard, DeclineDisclose
        state = _make_state()
        warrior = _place(state, "P0", _get_card(repo, "SEC", "164"), "ground")
        state = _fire_on_attack(state, warrior)
        acts = legal_actions(state)
        assert not any(isinstance(a, DiscloseSelectCard) for a in acts)
        assert any(isinstance(a, DeclineDisclose) for a in acts)


class TestAcademyDisciplinarian_SEC_165:
    """When Played: you may deal 1 to a friendly unit with power <= 2 and ready it."""

    def test_SEC_165_damages_and_readies_the_chosen_unit(self, repo):
        state = _make_state()
        disc = _place(state, "P0", _get_card(repo, "SEC", "165"), "ground")
        weak = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")   # 2/2
        weak.exhausted = True
        state = _fire_when_played(state, disc)
        state = _accept_optional_and_run(state)
        state = _choose(state, weak.instance_id)
        live = _find_instance(state, weak.instance_id)
        assert live.damage == 1
        assert live.exhausted is False

    def test_SEC_165_only_low_power_friendlies_are_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        disc = _place(state, "P0", _get_card(repo, "SEC", "165"), "ground")
        weak = _place(state, "P0", _get_card(repo, "SEC", "42"), "ground")   # 2 power
        strong = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3 power
        foe = _place(state, "P1", _get_card(repo, "SEC", "42"), "ground")
        state = _fire_when_played(state, disc)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {weak.instance_id}
        assert strong.instance_id not in offered and foe.instance_id not in offered


class TestZitonMoj_SEC_168:
    """When you take the initiative: deal 2 damage to a base."""

    def test_SEC_168_fires_on_claim_initiative(self, repo):
        from swu.engine.actions import legal_actions, apply, ClaimInitiative
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "168"), "ground")
        before = state.player_by_id("P1").base_instance.damage
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ClaimInitiative)))
        enemy_base = state.player_by_id("P1").base_instance.instance_id
        state = _choose(state, enemy_base)
        assert state.player_by_id("P1").base_instance.damage == before + 2

    def test_SEC_168_does_not_fire_for_the_opponents_claim(self, repo):
        from swu.engine.actions import legal_actions, apply, ClaimInitiative, ChooseTarget
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SEC", "168"), "ground")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ClaimInitiative)))
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


class TestAATIncinerator_SEC_169:
    """When Played: 1 to each of up to 4 OTHER ground units; if none was friendly,
    2 to your own base."""

    def test_SEC_169_never_offers_itself(self, repo):
        from swu.engine.actions import legal_actions, SelectDamageTarget
        state = _make_state()
        aat = _place(state, "P0", _get_card(repo, "SEC", "169"), "ground")
        other = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, aat)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectDamageTarget)}
        assert aat.instance_id not in offered
        assert other.instance_id in offered

    def test_SEC_169_self_burn_when_only_enemies_are_hit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectDamageTarget, FinishSelectDamage,
        )
        state = _make_state()
        aat = _place(state, "P0", _get_card(repo, "SEC", "169"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = state.player_by_id("P0").base_instance.damage
        state = _fire_when_played(state, aat)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectDamageTarget)
                                  and a.target_id == foe.instance_id))
        fin = next((a for a in legal_actions(state)
                    if isinstance(a, FinishSelectDamage)), None)
        if fin is not None:      # with no candidate left the pick auto-resolves
            state = apply(state, fin)
        assert _find_instance(state, foe.instance_id).damage == 1
        assert state.player_by_id("P0").base_instance.damage == before + 2

    def test_SEC_169_no_self_burn_when_a_friendly_is_hit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectDamageTarget, FinishSelectDamage,
        )
        state = _make_state()
        aat = _place(state, "P0", _get_card(repo, "SEC", "169"), "ground")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        before = state.player_by_id("P0").base_instance.damage
        state = _fire_when_played(state, aat)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectDamageTarget)
                                  and a.target_id == pal.instance_id))
        fin = next((a for a in legal_actions(state)
                    if isinstance(a, FinishSelectDamage)), None)
        if fin is not None:
            state = apply(state, fin)
        assert _find_instance(state, pal.instance_id).damage == 1
        assert state.player_by_id("P0").base_instance.damage == before


class TestPunishingOne_SEC_171:
    """Raid 1 per damaged enemy unit; When Played / On Attack, 1 damage to a unit."""

    def test_SEC_171_raid_scales_with_damaged_enemies(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        po = _place(state, "P0", _get_card(repo, "SEC", "171"), "space")
        assert keyword_value(state, po, Keyword.RAID) == 0,             "the bare printed Raid is sanitised away — the dynamic grant owns it"
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, po, Keyword.RAID) == 0, "undamaged enemies"
        a.damage = 1
        assert keyword_value(state, po, Keyword.RAID) == 1
        b.damage = 2
        assert keyword_value(state, po, Keyword.RAID) == 2

    def test_SEC_171_damaged_friendlies_do_not_count(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        po = _place(state, "P0", _get_card(repo, "SEC", "171"), "space")
        pal = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        pal.damage = 3
        assert keyword_value(state, po, Keyword.RAID) == 0

    def test_SEC_171_on_attack_deals_1(self, repo):
        state = _make_state()
        po = _place(state, "P0", _get_card(repo, "SEC", "171"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, po)
        state = _accept_optional_and_run(state)
        state = _choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1


class TestLetsCallItWar_SEC_180:
    """3 to a unit; then, with the initiative, you may deal 2 to another unit in the
    same arena."""

    def test_SEC_180_second_hit_needs_initiative_and_same_arena(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        state.initiative_holder = state.player_index("P0")
        first = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        same_arena = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        other_arena = _place(state, "P1", _get_card(repo, "SOR", "86"), "space")
        state, _ = _play_event_from_hand(state, repo, "SEC", "180", resources=14)
        state = _choose(state, first.instance_id)
        assert _find_instance(state, first.instance_id).damage == 3
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert same_arena.instance_id in offered
        assert other_arena.instance_id not in offered
        assert first.instance_id not in offered, "another unit"
        state = _choose(state, same_arena.instance_id)
        assert _find_instance(state, same_arena.instance_id).damage == 2

    def test_SEC_180_without_initiative_only_the_first_hit_lands(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        state.initiative_holder = state.player_index("P1")
        first = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        bystander = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "180", resources=14)
        state = _choose(state, first.instance_id)
        state = _drain(state)
        assert _find_instance(state, first.instance_id).damage == 3
        assert _find_instance(state, bystander.instance_id).damage == 0
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ── sec-set:05 — Direct damage & removal ──────────────────────────────────────

def _disclose_all(state):
    """Drive a pending 'disclose' decision to a successful disclose (pick cards
    until the requirement is covered and the decision resolves)."""
    from swu.engine.actions import legal_actions, apply, DiscloseSelectCard
    for _ in range(6):
        if not state.pending_decisions or state.pending_decisions[-1].kind != "disclose":
            return state
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, DiscloseSelectCard))
        state = apply(state, pick)
    return state


class TestChargedWithTreason_SEC_182:
    """You may disclose Aggression x2; if you do, deal 5 damage to a unit."""

    def test_SEC_182_disclosing_deals_5_to_the_chosen_unit(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "155"))   # Aggression
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "155"))   # Aggression
        state, _ = _play_event_from_hand(state, repo, "SEC", "182")
        state = _choose(state, victim.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        assert _find_instance(state, victim.instance_id).damage == 5

    def test_SEC_182_declining_deals_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "155"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "155"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "182")
        state = _choose(state, victim.instance_id)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineDisclose))
        state = apply(state, decline)
        assert _find_instance(state, victim.instance_id).damage == 0


class TestToppleTheSummit_SEC_183:
    """Deal 3 damage to each damaged unit."""

    def test_SEC_183_hits_every_damaged_unit_only(self, repo):
        state = _make_state()
        hurt_friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt_friend.damage = 1
        hurt_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        hurt_enemy.damage = 2
        healthy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "183")
        assert _find_instance(state, hurt_friend.instance_id).damage == 4
        assert _find_instance(state, hurt_enemy.instance_id).damage == 5
        assert _find_instance(state, healthy.instance_id).damage == 0


class TestHuttCartelStarfighter_SEC_240:
    """When Played: deal 2 damage to this unit."""

    def test_SEC_240_damages_itself_on_entry(self, repo):
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "SEC", "240"), "space")
        state = _fire_when_played(state, fighter)
        state = _drain(state)
        assert _find_instance(state, fighter.instance_id).damage == 2


class TestEliaKane_SEC_242:
    """When Played: you may defeat an enemy resource; if you do, they replace it
    from the top of their deck (ready)."""

    def test_SEC_242_defeats_a_resource_and_ramps_the_replacement(self, repo):
        state = _make_state()
        elia = _place(state, "P0", _get_card(repo, "SEC", "242"), "ground")
        _give_resources(state, "P1", 3)
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        before_discard = len(state.player_by_id("P1").discard)
        state = _fire_when_played(state, elia)
        state = _accept_optional_and_run(state)
        opp = state.player_by_id("P1")
        assert len(opp.resources) == 3           # one defeated, one ramped back
        assert len(opp.discard) == before_discard + 1
        assert opp.deck == []                    # the replacement came off the top
        assert not any(r.exhausted for r in opp.resources)

    def test_SEC_242_not_offered_when_the_opponent_has_no_resource(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        elia = _place(state, "P0", _get_card(repo, "SEC", "242"), "ground")
        state = _fire_when_played(state, elia)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestContemptForCulture_SEC_246:
    """Deal 2 damage to a non-Vehicle unit.  Create a Spy token."""

    def test_SEC_246_damages_a_non_vehicle_and_makes_a_spy(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        vehicle = _place(state, "P1", _get_card(repo, "SOR", "244"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "246")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert victim.instance_id in offered
        assert vehicle.instance_id not in offered
        state = _choose(state, victim.instance_id)
        state = _drain(state)
        assert _find_instance(state, victim.instance_id).damage == 2
        p0 = state.player_by_id("P0")
        assert any(u.card_def.name == "Spy" for u in p0.ground_arena)


class TestEvilIsEverywhere_SEC_247:
    """Defeat a unit costing <= the number of Villainy icons among friendly units."""

    def test_SEC_247_cap_is_the_friendly_villainy_icon_count(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        # Two friendly Villainy units => cap 2.
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        cheap = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")   # cost 1
        pricey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state, _ = _play_event_from_hand(state, repo, "SEC", "247")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered
        state = _choose(state, cheap.instance_id)
        assert _find_instance(state, cheap.instance_id) is None

    def test_SEC_247_no_villainy_means_nothing_is_targetable(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state, _ = _play_event_from_hand(state, repo, "SEC", "247")
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ── sec-set:06 — Direct damage & removal ──────────────────────────────────────

class TestHeroicArc170_SEC_254:
    """When Played: if you control a damaged unit, you may deal 2 to an enemy."""

    def test_SEC_254_deals_2_when_you_control_a_damaged_unit(self, repo):
        state = _make_state()
        arc = _place(state, "P0", _get_card(repo, "SEC", "254"), "space")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 1
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, arc)
        state = _accept_optional_and_run(state)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_SEC_254_not_offered_without_a_damaged_friendly(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        arc = _place(state, "P0", _get_card(repo, "SEC", "254"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, arc)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestAssassinProbe_SEC_263:
    """When Defeated: deal 1 to each exhausted enemy ground unit."""

    def test_SEC_263_hits_only_exhausted_enemy_ground_units(self, repo):
        state = _make_state()
        probe = _place(state, "P0", _get_card(repo, "SEC", "263"), "ground")
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        space.exhausted = True
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly.exhausted = True
        state = _fire_when_defeated(state, probe)
        state = _drain(state)
        assert _find_instance(state, tired.instance_id).damage == 1
        assert _find_instance(state, ready.instance_id).damage == 0
        assert _find_instance(state, space.instance_id).damage == 0
        assert _find_instance(state, friendly.instance_id).damage == 0


class TestClandestineConnections_SEC_264:
    """Attached unit gains: "On Attack: you may pay 2 to deal 2 to a base"."""

    def test_SEC_264_pays_two_and_damages_the_chosen_base(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "264"), "P0")
        _give_resources(state, "P0", 3)
        enemy_base = state.player_by_id("P1").base_instance
        state = _fire_on_attack(state, host)
        state = _accept_optional_and_run(state)
        state = _choose(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_instance.damage == 2
        ps = state.player_by_id("P0")
        assert sum(1 for r in ps.resources if r.exhausted) == 2

    def test_SEC_264_not_offered_without_two_ready_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "264"), "P0")
        _give_resources(state, "P0", 1)
        state = _fire_on_attack(state, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── sec-set:07 — Card advantage & disruption ──────────────────────────────────

def _fire_base_combat_damage(state, dealer_ci, amount=3):
    """Fire the 'dealt combat damage to a base' observer window for ``dealer_ci``."""
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, None, after_all_player_idx=0,
        event_ctx={"dealt_combat_damage_to_base": dealer_ci.instance_id,
                   "base_combat_damage_amount": amount})


class TestSabe_SEC_17:
    """Undeployed: exhaust to mill 1 of the defender's top 2.  Deployed: look at
    their hand, may discard a card, and if you do they draw."""

    def test_SEC_17_undeployed_exhausts_and_discards_one_of_top_two(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        sabe = _place_leader(state, "P0", _get_card(repo, "SEC", "17"))
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        second = _push_deck_top(state, "P1", _get_card(repo, "JTL", "212"))
        first = _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_base_combat_damage(state, attacker)
        state = _accept_optional_and_run(state)
        assert state.pending_decisions[-1].kind == "deck_search"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard) and a.instance_id == first.instance_id)
        state = apply(state, pick)
        opp = state.player_by_id("P1")
        assert [c.instance_id for c in opp.discard] == [first.instance_id]
        assert [c.instance_id for c in opp.deck] == [second.instance_id]
        assert _find_instance(state, sabe.instance_id) is None  # she is in base_zone
        leader = state.find_instance(sabe.instance_id)[1]
        assert leader.exhausted

    def test_SEC_17_undeployed_not_offered_while_exhausted(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        sabe = _place_leader(state, "P0", _get_card(repo, "SEC", "17"))
        sabe.exhausted = True
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_base_combat_damage(state, attacker)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_SEC_17_deployed_strips_a_card_and_they_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        sabe = _deploy(state, "P0", _get_card(repo, "SEC", "17"))
        victim = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        _push_deck_top(state, "P1", _get_card(repo, "JTL", "212"))
        state = _fire_base_combat_damage(state, sabe)
        assert state.pending_decisions[-1].kind == "name_and_discard"
        name = next(a for a in legal_actions(state) if isinstance(a, NameAndDiscard))
        state = apply(state, name)
        opp = state.player_by_id("P1")
        assert victim.instance_id in {c.instance_id for c in opp.discard}
        assert len(opp.hand) == 1        # discarded one, drew one


class TestBardottanOrnithopter_SEC_62:
    """When Played: you may disclose Vigilance; if you do, draw a card."""

    def test_SEC_62_disclosing_draws(self, repo):
        state = _make_state()
        orni = _place(state, "P0", _get_card(repo, "SEC", "62"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))   # Vigilance/Heroism
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, orni)
        state = _disclose_all(state)
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_SEC_62_no_prompt_without_a_vigilance_card(self, repo):
        state = _make_state()
        orni = _place(state, "P0", _get_card(repo, "SEC", "62"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "JTL", "212"))  # Cunning
        state = _fire_when_played(state, orni)
        state = _drain(state)
        assert not any(d.kind == "disclose" for d in state.pending_decisions)


class TestScourTheArchives_SEC_72:
    """Search the top 8 for an upgrade and draw it."""

    def test_SEC_72_draws_the_upgrade_and_bottoms_the_rest(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        upg = _push_deck_top(state, "P0", _get_card(repo, "SOR", "53"))  # an upgrade
        state, _ = _play_event_from_hand(state, repo, "SEC", "72")
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert [a.instance_id for a in picks] == [upg.instance_id]
        state = apply(state, picks[0])
        p0 = state.player_by_id("P0")
        assert upg.instance_id in {c.instance_id for c in p0.hand}
        assert len(p0.deck) == 3


class TestKnowledgeAndDefense_SEC_75:
    """Give a unit -2/-2 for this phase.  Draw a card."""

    def test_SEC_75_debuffs_the_chosen_unit_and_draws(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "75")
        before = len(state.player_by_id("P0").hand)
        state = _choose(state, victim.instance_id)
        state = _drain(state)
        assert compute_power(state, _find_instance(state, victim.instance_id)) == 1
        assert len(state.player_by_id("P0").hand) == before + 1


class TestDirectorKrennic_SEC_90:
    """When attacked: mill your top card; if it's a unit you may return it."""

    def test_SEC_90_returns_the_milled_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        krennic = _place(state, "P0", _get_card(repo, "SEC", "90"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        milled = _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state = _fire_on_attack(state, attacker, krennic)   # Krennic is attacked
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectDiscardCard))
        assert pick.instance_id == milled.instance_id
        state = apply(state, pick)
        assert milled.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").hand}

    def test_SEC_90_non_unit_mill_offers_nothing(self, repo):
        state = _make_state()
        krennic = _place(state, "P0", _get_card(repo, "SEC", "90"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        milled = _push_deck_top(state, "P0", _get_card(repo, "SEC", "72"))  # an event
        state = _fire_on_attack(state, attacker, krennic)
        state = _drain(state)
        assert not any(d.kind == "return_from_discard" for d in state.pending_decisions)
        assert milled.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}


class TestRenewedFriendship_SEC_105:
    """Return a unit from your discard to hand.  Create 2 Spy tokens."""

    def test_SEC_105_returns_a_unit_and_makes_two_spies(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        dead = CardInstance("P0_dead", _get_card(repo, "JTL", "212"), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(dead)
        state, _ = _play_event_from_hand(state, repo, "SEC", "105")
        p0 = state.player_by_id("P0")
        assert sum(1 for u in p0.ground_arena if u.card_def.name == "Spy") == 2
        pick = next(a for a in legal_actions(state) if isinstance(a, SelectDiscardCard))
        state = apply(state, pick)
        assert dead.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").hand}


class TestOrnFreeTaa_SEC_112:
    """+1/+0 per Law card in your discard; When Played search the top 10 for a Law
    card."""

    def test_SEC_112_scales_with_law_cards_in_the_discard(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        orn = _place(state, "P0", _get_card(repo, "SEC", "112"), "ground")
        assert compute_power(state, orn) == 0
        ps = state.player_by_id("P0")
        for i, (sc, num) in enumerate((("SEC", "92"), ("SEC", "128"))):  # Law events
            ps.discard.append(CardInstance(f"P0_law{i}", _get_card(repo, sc, num),
                                           "P0", Zone.DISCARD))
        assert compute_power(state, orn) == 2

    def test_SEC_112_when_played_searches_for_a_law_card(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        orn = _place(state, "P0", _get_card(repo, "SEC", "112"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        law = _push_deck_top(state, "P0", _get_card(repo, "SEC", "92"))
        state = _fire_when_played(state, orn)
        state = _drain(state)
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert [a.instance_id for a in picks] == [law.instance_id]
        state = apply(state, picks[0])
        assert law.instance_id in {c.instance_id
                                   for c in state.player_by_id("P0").hand}


# ── sec-set:08 — Card advantage & disruption ──────────────────────────────────

class TestReconnaissance_SEC_125:
    """If you control a ground unit and a space unit, draw 2."""

    def test_SEC_125_draws_two_with_both_arenas_covered(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "125")
        state = _drain(state)
        assert len(state.player_by_id("P0").hand) == 2

    def test_SEC_125_draws_nothing_with_only_ground(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "125")
        state = _drain(state)
        assert state.player_by_id("P0").hand == []


class TestConveneTheSenate_SEC_128:
    """Search the top 8 for up to 2 Official units; create a Spy token."""

    def test_SEC_128_draws_officials_and_makes_a_spy(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard, FinishSearch)
        state = _make_state()
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))     # not Official
        official = _push_deck_top(state, "P0", _get_card(repo, "SEC", "112"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "128")
        p0 = state.player_by_id("P0")
        assert any(u.card_def.name == "Spy" for u in p0.ground_arena)
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert [a.instance_id for a in picks] == [official.instance_id]
        state = apply(state, picks[0])
        finish = next(a for a in legal_actions(state) if isinstance(a, FinishSearch))
        state = apply(state, finish)
        assert official.instance_id in {c.instance_id
                                        for c in state.player_by_id("P0").hand}


class TestJuniorSenator_SEC_200:
    """When Played: you may return an upgrade costing 3 or less."""

    def test_SEC_200_returns_a_cheap_upgrade_only(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        cheap = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "264"), "P1")
        pricey = _attach_upgrade_directly(state, host, _get_card(repo, "SHD", "53"), "P1")
        senator = _place(state, "P0", _get_card(repo, "SEC", "200"), "ground")
        state = _fire_when_played(state, senator)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered
        state = _choose(state, cheap.instance_id)
        host_after = _find_instance(state, host.instance_id)
        assert cheap.instance_id not in {u.instance_id
                                         for u in host_after.attached_upgrades}
        assert cheap.instance_id in {c.instance_id
                                     for c in state.player_by_id("P1").hand}


class TestObiWanKenobi_SEC_205:
    """Base combat damage mills the defender's top card and lets you play it from
    their discard pile this phase, aspect penalties waived."""

    def test_SEC_205_mills_and_permits_a_paid_cross_pile_play(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromDiscard
        from swu.engine.state import Phase
        state = _make_state()
        obiwan = _place(state, "P0", _get_card(repo, "SEC", "205"), "ground")
        milled = _push_deck_top(state, "P0" if False else "P1",
                                _get_card(repo, "JTL", "212"))  # cost 1, Cunning
        state = _fire_base_combat_damage(state, obiwan)
        state = _drain(state)
        opp = state.player_by_id("P1")
        assert milled.instance_id in {c.instance_id for c in opp.discard}
        assert milled.instance_id in state.game_memory.foreign_discard_play_this_phase["P0"]
        # P0 may now play it out of P1's pile, paying its (penalty-waived) cost.
        state.phase = Phase.ACTION
        state.active_player_index = 0
        _give_resources(state, "P0", 5)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == milled.instance_id)
        # JTL_212 is off-aspect for the TST test base, so the waiver is real.
        assert play.discount == 2
        state = apply(state, play)
        assert _find_instance(state, milled.instance_id) is not None
        assert state.game_memory.foreign_discard_play_this_phase["P0"] == []


class TestFaithInYourFriends_SEC_211:
    """Search the top 3 for a card and draw it; then you may disclose for 2 Spies."""

    def test_SEC_211_searches_then_discloses_for_two_spies(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        wanted = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        # A hand that covers Cunning x3 + Heroism x2 (SOR_218 is Cunning, SOR_46 is
        # Vigilance/Heroism).
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "218"))
        for _ in range(2):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "211")
        assert state.pending_decisions[-1].kind == "deck_search"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard) and a.instance_id == wanted.instance_id)
        state = apply(state, pick)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        p0 = state.player_by_id("P0")
        assert sum(1 for u in p0.ground_arena if u.card_def.name == "Spy") == 2
        assert wanted.instance_id in {c.instance_id for c in p0.hand}


class TestCikatroVizago_SEC_218:
    """On Attack: reveal your top card; an opponent may pay 1 to deny the draw."""

    def test_SEC_218_opponent_pays_to_deny_the_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, SayNo
        state = _make_state()
        vizago = _place(state, "P0", _get_card(repo, "SEC", "218"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        _give_resources(state, "P1", 2)
        state = _fire_on_attack(state, vizago)
        assert state.pending_decisions[-1].kind == "say_no"
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        no = next(a for a in legal_actions(state) if isinstance(a, SayNo))
        state = apply(state, no)
        assert state.player_by_id("P0").hand == []
        assert sum(1 for r in state.player_by_id("P1").resources if r.exhausted) == 1

    def test_SEC_218_you_draw_when_they_do_not_pay(self, repo):
        from swu.engine.actions import legal_actions, apply, AllowEffect
        state = _make_state()
        vizago = _place(state, "P0", _get_card(repo, "SEC", "218"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        _give_resources(state, "P1", 2)
        state = _fire_on_attack(state, vizago)
        allow = next(a for a in legal_actions(state) if isinstance(a, AllowEffect))
        state = apply(state, allow)
        assert top.instance_id in {c.instance_id
                                   for c in state.player_by_id("P0").hand}

    def test_SEC_218_refusal_is_not_offered_without_a_ready_resource(self, repo):
        from swu.engine.actions import legal_actions, SayNo
        state = _make_state()
        vizago = _place(state, "P0", _get_card(repo, "SEC", "218"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state = _fire_on_attack(state, vizago)
        assert not any(isinstance(a, SayNo) for a in legal_actions(state))


# ── sec-set:09 — Card advantage & disruption ──────────────────────────────────

class TestChargedWithEspionage_SEC_230:
    """Disclose Cunning x2 -> look at their hand and discard a unit from it."""

    def test_SEC_230_discloses_then_strips_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        for _ in range(2):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "218"))   # Cunning
        unit = _put_in_hand(state, "P1", _get_card(repo, "JTL", "212"))
        _put_in_hand(state, "P1", _get_card(repo, "SEC", "72"))        # an event
        state, _ = _play_event_from_hand(state, repo, "SEC", "230")
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        assert state.pending_decisions[-1].kind == "name_and_discard"
        names = [a.card_name for a in legal_actions(state)
                 if isinstance(a, NameAndDiscard)]
        assert names == [unit.card_def.display_name]   # units only
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, NameAndDiscard)))
        assert unit.instance_id in {c.instance_id
                                    for c in state.player_by_id("P1").discard}


class TestKreiasWhispers_SEC_232:
    """Draw 3, then one hand card to the top and another to the bottom."""

    def test_SEC_232_draws_three_then_places_top_then_bottom(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectHandCardToTop, SelectHandCardToBottom)
        state = _make_state()
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "232")
        p0 = state.player_by_id("P0")
        assert len(p0.hand) == 3
        # First decision: TOP only.
        acts = legal_actions(state)
        assert all(isinstance(a, SelectHandCardToTop) for a in acts)
        to_top = acts[0].instance_id
        state = apply(state, acts[0])
        assert state.player_by_id("P0").deck[0].instance_id == to_top
        # Second decision: BOTTOM only.
        acts = legal_actions(state)
        assert all(isinstance(a, SelectHandCardToBottom) for a in acts)
        to_bottom = acts[0].instance_id
        state = apply(state, acts[0])
        p0 = state.player_by_id("P0")
        assert p0.deck[-1].instance_id == to_bottom
        assert len(p0.hand) == 1


class TestBeguile_SEC_233:
    """Look at an opponent's hand, then bounce a non-leader unit costing <= 6."""

    def test_SEC_233_looks_then_bounces_the_chosen_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AckLookHand, ChooseTarget
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "JTL", "212"))
        cheap = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # cost 4
        state, _ = _play_event_from_hand(state, repo, "SEC", "233")
        assert state.pending_decisions[-1].kind == "look_hand"
        ack = next(a for a in legal_actions(state) if isinstance(a, AckLookHand))
        state = apply(state, ack)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in offered
        state = _choose(state, cheap.instance_id)
        assert _find_instance(state, cheap.instance_id) is None
        assert cheap.instance_id in {c.instance_id
                                     for c in state.player_by_id("P1").hand}

    def test_SEC_233_expensive_units_are_not_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget, AckLookHand, apply
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "JTL", "212"))
        big = _place(state, "P1", _get_card(repo, "SEC", "90"), "ground")   # cost 9
        state, _ = _play_event_from_hand(state, repo, "SEC", "233")
        ack = next(a for a in legal_actions(state) if isinstance(a, AckLookHand))
        state = apply(state, ack)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert big.instance_id not in offered


# ── sec-set:10 — Combat tricks, buffs & tempo (the SEC leaders) ───────────────

class TestLeiaOrgana_SEC_4:
    """Disclose one of five aspects -> Experience to a unit sharing no aspect."""

    def test_SEC_4_undeployed_discloses_and_tokens_an_off_aspect_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, DiscloseSelectCard, SelectTokenTarget)
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "SEC", "4"))
        _give_resources(state, "P0", 3)
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "218"))    # Cunning
        offaspect = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, leia)
        assert state.pending_decisions[-1].kind == "disclose"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, DiscloseSelectCard))
        state = apply(state, pick)      # one card satisfies the "or"
        assert state.pending_decisions[-1].kind == "select_token"
        give = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == offaspect.instance_id)
        state = apply(state, give)
        host = _find_instance(state, offaspect.instance_id)
        assert any(u.card_def.name == "Experience" for u in host.attached_upgrades)

    def test_SEC_4_a_shared_aspect_unit_is_not_offered(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, DiscloseSelectCard, SelectTokenTarget)
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "SEC", "4"))
        _give_resources(state, "P0", 3)
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "218"))    # Cunning
        shared = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # Cunning
        state = _use(state, leia)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, DiscloseSelectCard))
        state = apply(state, pick)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert shared.instance_id not in offered


class TestColonelYularen_SEC_6:
    """Attack with a unit, then optionally with a cheaper one."""

    def test_SEC_6_undeployed_follow_up_is_capped_by_the_first_cost(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        yularen = _place_leader(state, "P0", _get_card(repo, "SEC", "6"))
        big = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # cost 4
        small = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # cost 1
        state = _use(state, yularen)
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit) and a.attacker_id == big.instance_id)
        state = apply(state, atk)
        # The follow-up only offers the cheaper unit.
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {small.instance_id}

    def test_SEC_6_deployed_offers_a_cheap_follow_up_attack(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        yularen = _deploy(state, "P0", _get_card(repo, "SEC", "6"))
        cheap = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # cost 1
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_ended_survivor": yularen.instance_id,
                       "attacker_id": yularen.instance_id})
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert cheap.instance_id in attackers


class TestDrydenVos_SEC_7:
    """Discard a card to play a unit from hand with Ambush."""

    def test_SEC_7_undeployed_needs_an_expensive_discard(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        dryden = _place_leader(state, "P0", _get_card(repo, "SEC", "7"))
        _give_resources(state, "P0", 6)
        _put_in_hand(state, "P0", _get_card(repo, "JTL", "212"))   # cost 1 — too cheap
        assert not any(isinstance(a, UseAbility) and a.source_id == dryden.instance_id
                       for a in legal_actions(state))
        pricey = _put_in_hand(state, "P0", _get_card(repo, "SEC", "90"))  # cost 9
        assert any(isinstance(a, UseAbility) and a.source_id == dryden.instance_id
                   for a in legal_actions(state))
        state = _use(state, dryden)
        # The 9-cost card was the discard; the 1-cost unit is the play.
        assert pricey.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}
        assert state.pending_decisions[-1].kind == "play_from_hand"

    def test_SEC_7_played_unit_gains_ambush(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        dryden = _place_leader(state, "P0", _get_card(repo, "SEC", "7"))
        _give_resources(state, "P0", 6)
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "90"))    # the 9-cost discard
        unit = _put_in_hand(state, "P0", _get_card(repo, "JTL", "212"))
        state = _use(state, dryden)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        in_play = _find_instance(state, unit.instance_id)
        assert in_play is not None
        assert has_keyword(state, in_play, Keyword.AMBUSH)


class TestBailOrgana_SEC_8:
    """Recycle a resource after a friendly death; heal on a Smuggle play."""

    def test_SEC_8_undeployed_recycles_a_resource(self, repo):
        state = _make_state()
        bail = _place_leader(state, "P0", _get_card(repo, "SEC", "8"))
        _give_resources(state, "P0", 4)
        state.game_memory.defeated_controllers_this_round.append("P0")
        _push_deck_top(state, "P0", _get_card(repo, "JTL", "212"))
        state = _use(state, bail)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 1          # one resource came back to hand
        assert len(ps.resources) == 4     # and was replaced off the deck
        assert ps.deck == []

    def test_SEC_8_undeployed_not_offered_without_a_friendly_death(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        bail = _place_leader(state, "P0", _get_card(repo, "SEC", "8"))
        _give_resources(state, "P0", 4)
        assert not any(isinstance(a, UseAbility) and a.source_id == bail.instance_id
                       for a in legal_actions(state))

    def test_SEC_8_deployed_heals_on_a_smuggle_play(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.events import CardPlayed
        state = _make_state()
        _deploy(state, "P0", _get_card(repo, "SEC", "8"))
        base = state.player_by_id("P0").base_instance
        base.damage = 3
        evt = CardPlayed(player_id="P0", instance_id="x", card_name="Whatever",
                         cost_paid=1)
        state = fire_triggered_abilities(state, evt, after_all_player_idx=0,
                                         event_ctx={"via_smuggle": True})
        state = _drain(state)
        assert state.player_by_id("P0").base_instance.damage == 2


class TestMonMothma_SEC_9:
    """Waive aspect penalties on non-Villainy Official units; +0/+1 anthem."""

    def test_SEC_9_waives_the_penalty_on_an_official_unit(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SEC", "9"))
        ps = state.player_by_id("P0")
        official = CardInstance("P0_off", _get_card(repo, "SEC", "112"), "P0", Zone.HAND)
        ps.hand.append(official)
        _give_resources(state, "P0", 10)
        # SEC_112 costs 2 and is off-aspect for the test base, so the waiver shows.
        assert _play_cost(state, official, ps) == 2

    def test_SEC_9_deployed_buffs_other_official_units(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        mothma = _deploy(state, "P0", _get_card(repo, "SEC", "9"))
        other = _place(state, "P0", _get_card(repo, "SEC", "112"), "ground")  # Official
        plain = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert compute_hp(state, other) == 5     # 4 + 1
        assert compute_hp(state, plain) == 3
        assert compute_hp(state, mothma) == 7    # "each OTHER" — not herself


class TestGovernorPryce_SEC_11:
    """Ready a token unit; scale with ready tokens; make a Spy on attack."""

    def test_SEC_11_undeployed_readies_an_exhausted_token(self, repo):
        from swu.engine.actions import _create_token_units
        state = _make_state()
        pryce = _place_leader(state, "P0", _get_card(repo, "SEC", "11"))
        _give_resources(state, "P0", 3)
        token = _create_token_units(state, state.player_by_id("P0"), "Spy", 1)[0]
        token.exhausted = True
        state = _use(state, pryce)
        state = _choose(state, token.instance_id)
        assert not _find_instance(state, token.instance_id).exhausted

    def test_SEC_11_deployed_scales_with_ready_tokens_and_makes_a_spy(self, repo):
        from swu.engine.actions import compute_power, _create_token_units
        state = _make_state()
        pryce = _deploy(state, "P0", _get_card(repo, "SEC", "11"))
        base_power = compute_power(state, pryce)
        tokens = _create_token_units(state, state.player_by_id("P0"), "Spy", 2)
        for t in tokens:
            t.exhausted = False
        assert compute_power(state, pryce) == base_power + 2
        tokens[0].exhausted = True
        assert compute_power(state, pryce) == base_power + 1
        state = _fire_on_attack(state, pryce)
        state = _drain(state)
        spies = [u for u in state.player_by_id("P0").ground_arena
                 if u.card_def.name == "Spy"]
        assert len(spies) == 3


class TestC3PO_SEC_15:
    """Exhaust a unit while you control an(other) exhausted unit."""

    def test_SEC_15_undeployed_exhausts_a_unit(self, repo):
        state = _make_state()
        threepio = _place_leader(state, "P0", _get_card(repo, "SEC", "15"))
        _give_resources(state, "P0", 3)
        tired = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _use(state, threepio)
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).exhausted

    def test_SEC_15_undeployed_not_offered_without_an_exhausted_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        threepio = _place_leader(state, "P0", _get_card(repo, "SEC", "15"))
        _give_resources(state, "P0", 3)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert not any(isinstance(a, UseAbility) and a.source_id == threepio.instance_id
                       for a in legal_actions(state))

    def test_SEC_15_deployed_needs_ANOTHER_exhausted_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        threepio = _deploy(state, "P0", _get_card(repo, "SEC", "15"))
        threepio.exhausted = True          # attacking exhausted him
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, threepio)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state2 = _make_state()
        t2 = _deploy(state2, "P0", _get_card(repo, "SEC", "15"))
        t2.exhausted = True
        friend = _place(state2, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.exhausted = True
        _place(state2, "P1", _get_card(repo, "SOR", "46"), "ground")
        state2 = _fire_on_attack(state2, t2)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state2))


# ── sec-set:11 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestDJ_SEC_18:
    """Undeployed: choose a friendly unit, play a unit 1 cheaper, it captures it."""

    def test_SEC_18_played_unit_is_captured_by_the_chosen_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        dj = _place_leader(state, "P0", _get_card(repo, "SEC", "18"))
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        prey = _put_in_hand(state, "P0", _get_card(repo, "JTL", "212"))
        _give_resources(state, "P0", 6)
        state = _use(state, dj)
        state = _choose(state, captor.instance_id)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == prey.instance_id)
        state = apply(state, play)
        state = _drain(state)
        captives = [c for p in state.players for c in p.capture_pile]
        assert [c.instance_id for c in captives] == [prey.instance_id]
        assert captives[0].captured_by == captor.instance_id

    def test_SEC_18_play_is_one_resource_cheaper(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        dj = _place_leader(state, "P0", _get_card(repo, "SEC", "18"))
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        prey = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))   # cost 4
        _give_resources(state, "P0", 8)
        state = _use(state, dj)
        state = _choose(state, captor.instance_id)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == prey.instance_id)
        state = apply(state, play)
        # cost 4 + 4 aspect penalty (two unmatched pips vs the test base), less the
        # 1-resource discount => 7.
        assert sum(1 for r in state.player_by_id("P0").resources if r.exhausted) == 7


class TestZamWesell_SEC_29:
    """While upgraded, she gains Grit."""

    def test_SEC_29_grit_only_while_upgraded(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        zam = _place(state, "P0", _get_card(repo, "SEC", "29"), "ground")
        assert not has_keyword(state, zam, Keyword.GRIT)
        _attach_upgrade_directly(state, zam, _get_card(repo, "SOR", "53"), "P0")
        assert has_keyword(state, zam, Keyword.GRIT)


class TestKyloRensCommandShuttle_SEC_32:
    """Each friendly ground unit with Sentinel gets +0/+2."""

    def test_SEC_32_buffs_only_sentinel_ground_units(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "32"), "space")
        sentinel = _place(state, "P0", _get_card(repo, "SEC", "41"), "ground")  # 1/4
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        # SEC_41 gains Sentinel only after the trigger, so grant it directly here.
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id="test", target_instance_id=sentinel.instance_id,
            kind="keyword_grant", value={"keyword": "Sentinel", "value": 0},
            duration="this_phase"))
        assert compute_hp(state, sentinel) == 6      # 4 + 2
        assert compute_hp(state, plain) == 7


class TestEmergencyPowers_SEC_40:
    """Choose a non-leader unit; each resource paid buys it an Experience token."""

    def test_SEC_40_tokens_scale_with_resources_paid(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PayResourceForToken, FinishPayResources)
        state = _make_state()
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "40", resources=10)
        state = _choose(state, target.instance_id)
        assert state.pending_decisions[-1].kind == "pay_resources_for_tokens"
        for _ in range(2):
            pay = next(a for a in legal_actions(state)
                       if isinstance(a, PayResourceForToken))
            state = apply(state, pay)
        stop = next(a for a in legal_actions(state)
                    if isinstance(a, FinishPayResources))
        state = apply(state, stop)
        host = _find_instance(state, target.instance_id)
        assert sum(1 for u in host.attached_upgrades
                   if u.card_def.name == "Experience") == 2


class TestPopulistAdvisor_SEC_41:
    """When an enemy unit deals combat damage to your base, gain Sentinel."""

    def test_SEC_41_gains_sentinel_for_the_phase(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        advisor = _place(state, "P0", _get_card(repo, "SEC", "41"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not has_keyword(state, advisor, Keyword.SENTINEL)
        state = _fire_base_combat_damage(state, attacker)
        state = _drain(state)
        assert has_keyword(state, _find_instance(state, advisor.instance_id),
                           Keyword.SENTINEL)

    def test_SEC_41_does_not_fire_for_a_friendly_attacker(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        advisor = _place(state, "P0", _get_card(repo, "SEC", "41"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_base_combat_damage(state, friend)
        state = _drain(state)
        assert not has_keyword(state, _find_instance(state, advisor.instance_id),
                               Keyword.SENTINEL)


class TestCoronet_SEC_47:
    """Each other friendly unit gains Restore 1 (and she keeps her own)."""

    def test_SEC_47_grants_restore_to_others_and_keeps_her_own(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        coronet = _place(state, "P0", _get_card(repo, "SEC", "47"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, friend, Keyword.RESTORE) == 1
        assert keyword_value(state, coronet, Keyword.RESTORE) == 1
        assert not has_keyword(state, enemy, Keyword.RESTORE)


class TestExiledFromTheForce_SEC_54:
    """Attached unit loses Force and all abilities except a granted Grit."""

    def test_SEC_54_strips_force_trait_and_abilities_but_grants_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.traits import has_trait
        from swu.engine.state import ability_suppressed
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SEC", "205"), "ground")  # Force/Jedi
        assert has_trait(state, host, "Force")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "54"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        state = _drain(state)
        host2 = _find_instance(state, host.instance_id)
        assert not has_trait(state, host2, "Force")
        assert ability_suppressed(state, host2)
        assert has_keyword(state, host2, Keyword.GRIT)


# ── sec-set:12 — Combat tricks, buffs & tempo ─────────────────────────────────


def _vigilance_card(repo):
    """SOR_58 — mono-Vigilance, the disclose fodder used across this group."""
    return _get_card(repo, "SOR", "58")


class TestSenateWarden_SEC_59:
    """When Defeated: disclose Vigilance → give an Experience token to a unit."""

    def test_SEC_59_disclosing_gives_an_experience_token(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        warden = _place(state, "P0", _get_card(repo, "SEC", "59"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P0", _vigilance_card(repo))
        state = _fire_when_defeated(state, warden)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        assert state.pending_decisions[-1].kind == "select_token"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == friend.instance_id)
        state = apply(state, pick)
        host = _find_instance(state, friend.instance_id)
        assert any(u.card_def.name == "Experience" for u in host.attached_upgrades)

    def test_SEC_59_no_prompt_without_a_vigilance_card(self, repo):
        state = _make_state()
        warden = _place(state, "P0", _get_card(repo, "SEC", "59"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, warden)
        state = _drain(state)
        assert not any(d.kind == "disclose" for d in state.pending_decisions)


class TestRotundaSenateGuards_SEC_63:
    """While undamaged, it gains Sentinel."""

    def test_SEC_63_sentinel_only_while_undamaged(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guards = _place(state, "P0", _get_card(repo, "SEC", "63"), "ground")
        assert has_keyword(state, guards, Keyword.SENTINEL)
        guards.damage = 1
        assert not has_keyword(state, guards, Keyword.SENTINEL)


class TestCongressOfMalastare_SEC_64:
    """The first upgrade you play each phase costs 1 resource less."""

    def test_SEC_64_only_the_first_upgrade_is_discounted(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "64"), "ground")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        first = _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))
        second = _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))
        _give_resources(state, "P0", 20)

        def _spent(s):
            return sum(1 for r in s.player_by_id("P0").resources if r.exhausted)

        state = apply(state, PlayCard(first.instance_id,
                                      upgrade_target_id=host.instance_id))
        after_first = _spent(state)
        state.active_player_index = 0        # skip the opponent's turn
        state = apply(state, PlayCard(second.instance_id,
                                      upgrade_target_id=host.instance_id))
        after_second = _spent(state)
        # Same card twice: the second play costs exactly 1 more (discount spent).
        assert after_second - after_first == after_first + 1


class TestNalaSe_SEC_65:
    """On Attack: disclose Vigilance x2 → heal up to 4 from among OTHER units."""

    def test_SEC_65_heals_other_units_of_either_player(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AssignDamage, FinishDamageDistribution)
        state = _make_state()
        nala = _place(state, "P0", _get_card(repo, "SEC", "65"), "ground")
        nala.damage = 3
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.damage = 2
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.damage = 2
        _put_in_hand(state, "P0", _vigilance_card(repo))
        _put_in_hand(state, "P0", _vigilance_card(repo))
        state = _fire_on_attack(state, nala)
        state = _drain(state)
        state = _disclose_all(state)
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context["heal"]
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, AssignDamage)}
        assert offered == {friend.instance_id, enemy.instance_id}  # "other" units
        for tid in (friend.instance_id, enemy.instance_id):
            state = apply(state, AssignDamage(tid))
        stop = next(a for a in legal_actions(state)
                    if isinstance(a, FinishDamageDistribution))
        state = apply(state, stop)
        assert _find_instance(state, friend.instance_id).damage == 1
        assert _find_instance(state, enemy.instance_id).damage == 1
        assert _find_instance(state, nala.instance_id).damage == 3   # never healed


class TestNimbleProwess_SEC_69:
    """When Played: you may exhaust a unit in attached unit's arena."""

    def test_SEC_69_exhausts_a_unit_in_the_hosts_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        far = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "69"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        state = _accept_optional_and_run(state)
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert far.instance_id not in offered          # wrong arena
        assert victim.instance_id in offered
        state = _choose(state, victim.instance_id)
        state = _drain(state)
        assert _find_instance(state, victim.instance_id).exhausted


class TestDisciplesDevotion_SEC_71:
    """While attached unit is exhausted, it gains Sentinel."""

    def test_SEC_71_sentinel_only_while_the_host_is_exhausted(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "71"), "P0")
        host.exhausted = False
        assert not has_keyword(state, host, Keyword.SENTINEL)
        host.exhausted = True
        assert has_keyword(state, host, Keyword.SENTINEL)


class TestReliefRequest_SEC_74:
    """Heal 3 from a unit; disclose Vigilance → heal 3 from another unit."""

    def test_SEC_74_disclosing_heals_a_second_unit(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        a.damage = 4
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b.damage = 5
        _put_in_hand(state, "P0", _vigilance_card(repo))
        state, _ = _play_event_from_hand(state, repo, "SEC", "74")
        state = _choose(state, a.instance_id)
        state = _choose(state, b.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 2

    def test_SEC_74_declining_heals_only_the_first_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        a.damage = 4
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b.damage = 5
        _put_in_hand(state, "P0", _vigilance_card(repo))
        state, _ = _play_event_from_hand(state, repo, "SEC", "74")
        state = _choose(state, a.instance_id)
        state = _choose(state, b.instance_id)
        decline = next(a2 for a2 in legal_actions(state)
                       if isinstance(a2, DeclineDisclose))
        state = apply(state, decline)
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 5


# ── sec-set:13 — Combat tricks, buffs & tempo ─────────────────────────────────


def _command_card(repo):
    """SOR_107 "Command" — mono-Command, the disclose fodder for SEC_107."""
    return _get_card(repo, "SOR", "107")


def _fire_attack_ends(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for an attacker that survived."""
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, None, after_all_player_idx=0,
        event_ctx={"attack_ended_survivor": attacker_ci.instance_id,
                   "attacker_id": attacker_ci.instance_id})


class TestPreMorPersonnelCarrier_SEC_89:
    """When Played: an Experience token per friendly ground unit."""

    def test_SEC_89_one_experience_per_friendly_ground_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")    # not ground
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # not friendly
        carrier = _place(state, "P0", _get_card(repo, "SEC", "89"), "ground")
        state = _fire_when_played(state, carrier)
        state = _drain(state)
        host = _find_instance(state, carrier.instance_id)
        # The Carrier + one other friendly ground unit = 2.
        assert sum(1 for u in host.attached_upgrades
                   if u.card_def.name == "Experience") == 2


class TestCorporateWarmongering_SEC_91:
    """+3/+3 to a friendly unit, +1/+1 to each OTHER friendly unit."""

    def test_SEC_91_buffs_the_chosen_unit_more_than_the_rest(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        star = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "91")
        state = _choose(state, star.instance_id)
        state = _drain(state)
        assert compute_power(state, _find_instance(state, star.instance_id)) == 6
        assert compute_power(state, _find_instance(state, other.instance_id)) == 4
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 3


class TestTheedSecurity_SEC_95:
    """When Played: if an opponent controls an upgrade, give a unit Experience."""

    def test_SEC_95_gives_a_token_when_an_enemy_unit_is_upgraded(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, enemy, _get_card(repo, "SOR", "53"), "P1")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theed = _place(state, "P0", _get_card(repo, "SEC", "95"), "ground")
        state = _fire_when_played(state, theed)
        state = _choose(state, friend.instance_id)
        state = _drain(state)
        host = _find_instance(state, friend.instance_id)
        assert any(u.card_def.name == "Experience" for u in host.attached_upgrades)

    def test_SEC_95_no_trigger_without_an_enemy_upgrade(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        theed = _place(state, "P0", _get_card(repo, "SEC", "95"), "ground")
        state = _fire_when_played(state, theed)
        assert not [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]


class TestRenownedDignitaries_SEC_102:
    """When Played: heal 2 from your base per friendly Official unit."""

    def test_SEC_102_heals_two_per_official(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 9
        _place(state, "P0", _get_card(repo, "SEC", "108"), "ground")   # Official
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # not Official
        dignitaries = _place(state, "P0", _get_card(repo, "SEC", "102"), "ground")
        state = _fire_when_played(state, dignitaries)
        state = _drain(state)
        # Senator's Aide + the Dignitaries themselves = 2 Officials → heal 4.
        assert state.player_by_id("P0").base_instance.damage == 5


class TestFigureOfUnity_SEC_104:
    """Attached unit: while ready, each OTHER friendly unit gains Overwhelm/Raid 1/
    Restore 1."""

    def test_SEC_104_grants_the_aura_only_while_the_host_is_ready(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "104"), "P0")
        host.exhausted = False
        assert has_keyword(state, friend, Keyword.OVERWHELM)
        assert keyword_value(state, friend, Keyword.RAID) == 1
        assert keyword_value(state, friend, Keyword.RESTORE) == 1
        assert not has_keyword(state, enemy, Keyword.OVERWHELM)   # not friendly
        assert not has_keyword(state, host, Keyword.OVERWHELM)    # "each OTHER"
        host.exhausted = True
        assert not has_keyword(state, friend, Keyword.OVERWHELM)  # only while ready


class TestChancellorValorum_SEC_107:
    """When attack ends: disclose Command x3 → resource off the top of your deck."""

    def test_SEC_107_disclosing_ramps_a_resource(self, repo):
        state = _make_state()
        valorum = _place(state, "P0", _get_card(repo, "SEC", "107"), "ground")
        for _ in range(3):
            _put_in_hand(state, "P0", _command_card(repo))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        before = len(state.player_by_id("P0").resources)
        state = _fire_attack_ends(state, valorum)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        assert len(state.player_by_id("P0").resources) == before + 1

    def test_SEC_107_no_prompt_without_three_command_icons(self, repo):
        state = _make_state()
        valorum = _place(state, "P0", _get_card(repo, "SEC", "107"), "ground")
        _put_in_hand(state, "P0", _command_card(repo))
        state = _fire_attack_ends(state, valorum)
        state = _drain(state)
        assert not any(d.kind == "disclose" for d in state.pending_decisions)


class TestSenatorsAide_SEC_108:
    """While you have the initiative, +2/+0."""

    def test_SEC_108_plus_two_power_only_with_initiative(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        aide = _place(state, "P0", _get_card(repo, "SEC", "108"), "ground")
        state.initiative_holder = state.player_index("P0")
        assert compute_power(state, aide) == 2
        state.initiative_holder = state.player_index("P1")
        assert compute_power(state, aide) == 0


# ── sec-set:14 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestDiplomaticEnvoy_SEC_109:
    """When Played: disclose Command → next unit you play gains Ambush."""

    def test_SEC_109_arms_ambush_for_the_next_unit_played(self, repo):
        state = _make_state()
        envoy = _place(state, "P0", _get_card(repo, "SEC", "109"), "ground")
        _put_in_hand(state, "P0", _command_card(repo))
        state = _fire_when_played(state, envoy)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        armed = state.game_memory.pending_keyword_grants
        assert [e["keyword"] for e in armed] == ["Ambush"]
        assert armed[0]["player_id"] == "P0"

    def test_SEC_109_declining_arms_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        envoy = _place(state, "P0", _get_card(repo, "SEC", "109"), "ground")
        _put_in_hand(state, "P0", _command_card(repo))
        state = _fire_when_played(state, envoy)
        state = _drain(state)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineDisclose))
        state = apply(state, decline)
        assert not state.game_memory.pending_keyword_grants


class TestGNKPowerDroid_SEC_110:
    """On Attack: the next unit you play this phase costs 1 less."""

    def test_SEC_110_discounts_the_next_unit_played(self, repo):
        from swu.engine.actions import apply, PlayCard

        def _spend(with_gnk):
            state = _make_state()
            if with_gnk:
                gnk = _place(state, "P0", _get_card(repo, "SEC", "110"), "ground")
            unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
            _give_resources(state, "P0", 20)
            if with_gnk:
                state = _drain(_fire_on_attack(state, gnk))
                assert state.game_memory.pending_play_discounts
            state = apply(state, PlayCard(unit.instance_id))
            return sum(1 for r in state.player_by_id("P0").resources if r.exhausted)

        assert _spend(True) == _spend(False) - 1


class TestCrucible_SEC_119:
    """When Played / When Defeated: an Experience token to each OTHER friendly."""

    def test_SEC_119_when_played_tokens_other_friendlies_only(self, repo):
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        crucible = _place(state, "P0", _get_card(repo, "SEC", "119"), "space")
        state = _fire_when_played(state, crucible)
        state = _drain(state)

        def _xp(ci):
            return sum(1 for u in _find_instance(state, ci.instance_id).attached_upgrades
                       if u.card_def.name == "Experience")

        assert _xp(friend) == 1
        assert _xp(enemy) == 0
        assert _xp(crucible) == 0        # "each OTHER friendly unit"

    def test_SEC_119_fires_again_when_defeated(self, repo):
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        crucible = _place(state, "P0", _get_card(repo, "SEC", "119"), "space")
        state = _fire_when_defeated(state, crucible)
        state = _drain(state)
        host = _find_instance(state, friend.instance_id)
        assert sum(1 for u in host.attached_upgrades
                   if u.card_def.name == "Experience") == 1


class TestVuutunPalaa_SEC_122:
    """Costs 1 less per friendly Droid; friendly Droids can be exhausted to pay."""

    def test_SEC_122_costs_one_less_per_friendly_droid(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        palaa = _put_in_hand(state, "P0", _get_card(repo, "SEC", "122"))
        ps = state.player_by_id("P0")
        base = _play_cost(state, palaa, ps)
        _place(state, "P0", _get_card(repo, "SEC", "110"), "ground")   # Droid
        _place(state, "P0", _get_card(repo, "SEC", "135"), "ground")   # Droid
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # not a Droid
        assert _play_cost(state, palaa, ps) == base - 2

    def test_SEC_122_friendly_droids_pay_like_resources(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "122"), "space")    # the marker
        droid = _place(state, "P0", _get_card(repo, "SEC", "135"), "ground")
        droid.exhausted = False
        card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        ps = state.player_by_id("P0")
        cost = _play_cost_of(state, ps, card)
        _give_resources(state, "P0", cost - 1)          # one short on resources
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == card.instance_id)
        state = apply(state, play)
        # Every resource exhausted, and the Droid tapped for the last point.
        ps = state.player_by_id("P0")
        assert all(r.exhausted for r in ps.resources)
        assert _find_instance(state, droid.instance_id).exhausted


def _play_cost_of(state, ps, ci):
    from swu.engine.actions import _play_cost
    return _play_cost(state, ci, ps)


class TestHuntingAssassinDroid_SEC_134:
    """While an enemy unit is damaged, this unit gains Raid 2."""

    def test_SEC_134_raid_two_only_while_an_enemy_is_damaged(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "SEC", "134"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, droid, Keyword.RAID) == 0
        enemy.damage = 1
        assert keyword_value(state, droid, Keyword.RAID) == 2


class TestMuckrakerCrabDroid_SEC_135:
    """While ready, it can't be attacked."""

    def test_SEC_135_cannot_be_attacked_while_ready(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        crab = _place(state, "P1", _get_card(repo, "SEC", "135"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False

        def _defenders():
            return {a.defender_id for a in legal_actions(state)
                    if isinstance(a, AttackWithUnit)
                    and a.attacker_id == attacker.instance_id}

        crab.exhausted = False
        assert crab.instance_id not in _defenders()
        crab.exhausted = True
        assert crab.instance_id in _defenders()


class TestDrydenVos_SEC_137:
    """On Attack: you may double his power; if you do, he doesn't ready."""

    def test_SEC_137_doubles_power_and_locks_the_ready(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        dryden = _place(state, "P0", _get_card(repo, "SEC", "137"), "ground")
        assert compute_power(state, dryden) == 2
        state = _fire_on_attack(state, dryden)
        state = _accept_optional_and_run(state)
        state = _drain(state)
        after = _find_instance(state, dryden.instance_id)
        assert compute_power(state, after) == 4
        assert after.cannot_ready_this_round

    def test_SEC_137_declining_changes_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, compute_power, DeclineTrigger
        state = _make_state()
        dryden = _place(state, "P0", _get_card(repo, "SEC", "137"), "ground")
        state = _fire_on_attack(state, dryden)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        after = _find_instance(state, dryden.instance_id)
        assert compute_power(state, after) == 2
        assert not after.cannot_ready_this_round


# ── sec-set:15 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestHondoOhnaka_SEC_140:
    """Each OTHER friendly unit gains Raid 1."""

    def test_SEC_140_grants_raid_one_to_other_friendlies_only(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "SEC", "140"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, friend, Keyword.RAID) == 1
        assert keyword_value(state, enemy, Keyword.RAID) == 0
        # "each OTHER friendly unit" — and Hondo's printed "Raid" bar is the usual
        # upstream mis-tag off his own grant text, which the sanitiser strips.
        assert keyword_value(state, hondo, Keyword.RAID) == 0


class TestKazudaXiono_SEC_151:
    """While you control fewer resources than an opponent, +2/+0."""

    def test_SEC_151_buffed_only_while_behind_on_resources(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        kaz = _place(state, "P0", _get_card(repo, "SEC", "151"), "ground")
        _give_resources(state, "P0", 3)
        _give_resources(state, "P1", 3)
        assert compute_power(state, kaz) == 2
        _give_resources(state, "P1", 2)          # opponent now has more
        assert compute_power(state, kaz) == 4


class TestInnerRimCoalition_SEC_154:
    """When Defeated: you may ready a unit that costs 5 or less."""

    def test_SEC_154_readies_only_cheap_units(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        coalition = _place(state, "P0", _get_card(repo, "SEC", "154"), "ground")
        cheap = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # cost 4
        cheap.exhausted = True
        dear = _place(state, "P0", _get_card(repo, "SEC", "122"), "space")    # cost 9
        dear.exhausted = True
        state = _fire_when_defeated(state, coalition)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert dear.instance_id not in offered
        state = _choose(state, cheap.instance_id)
        state = _drain(state)
        assert not _find_instance(state, cheap.instance_id).exhausted


class TestOneWayOut_SEC_157:
    """Attack with a unit: +1/+0, Overwhelm, and the defender loses its abilities."""

    def test_SEC_157_defender_loses_abilities_for_the_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        # Rotunda Senate Guards SEC_63 has Sentinel only through an ability.
        defender = _place(state, "P1", _get_card(repo, "SEC", "63"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "157")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 1
        assert "Overwhelm" in top.context["grant_keywords"]
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = apply(state, atk)
        state = _drain(state)
        # The defender took 3 (power) + 1 (the granted bonus) = 4 damage.
        after = _find_instance(state, defender.instance_id)
        assert after is not None and after.damage == 4

    def test_SEC_157_defender_abilities_go_dark_for_the_attack(self, repo):
        """Senate Warden SEC_59 (2/2) has a When Defeated ability that normally
        offers its controller a disclose; killed under One Way Out it must not."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit

        def _warden_ability_fired(with_event):
            state = _make_state()
            attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
            attacker.exhausted = False
            warden = _place(state, "P1", _get_card(repo, "SEC", "59"), "ground")
            _put_in_hand(state, "P1", _vigilance_card(repo))
            if with_event:
                state, _ = _play_event_from_hand(state, repo, "SEC", "157")
            atk = next(a for a in legal_actions(state)
                       if isinstance(a, AttackWithUnit)
                       and a.attacker_id == attacker.instance_id
                       and a.defender_id == warden.instance_id)
            state = _drain(apply(state, atk))
            return any(d.kind == "disclose" for d in state.pending_decisions)

        assert _warden_ability_fired(False)
        assert not _warden_ability_fired(True)


class TestCintaKaz_SEC_172:
    """When Played: you may attack with a unit."""

    def test_SEC_172_offers_an_optional_attack(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        state = _make_state()
        ready = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ready.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        cinta = _place(state, "P0", _get_card(repo, "SEC", "172"), "ground")
        state = _fire_when_played(state, cinta)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)
        assert ready.instance_id in {a.attacker_id for a in acts
                                     if isinstance(a, AttackWithUnit)}


class TestSawGerrerasUWing_SEC_174:
    """When attack ends: you may attack with another Aggression unit."""

    def test_SEC_174_offers_only_other_aggression_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "SEC", "174"), "space")
        uwing.exhausted = False
        aggro = _place(state, "P0", _get_card(repo, "SOR", "155"), "ground")  # Aggression
        aggro.exhausted = False
        other = _place(state, "P0", _get_card(repo, "SEC", "108"), "ground")  # not Aggression
        other.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_attack_ends(state, uwing)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert aggro.instance_id in attackers
        assert other.instance_id not in attackers
        assert uwing.instance_id not in attackers          # "ANOTHER"


class TestItsNotOverYet_SEC_177:
    """Ready a unit that didn't attack or enter play this phase; create a Spy."""

    def test_SEC_177_readies_an_idle_unit_and_makes_a_spy(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        idle = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        idle.exhausted = True
        busy = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        busy.exhausted = True
        state.game_memory.units_attacked_this_round.add(busy.instance_id)
        fresh = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        fresh.exhausted = True
        state.game_memory.units_played_this_phase.add(fresh.instance_id)
        state, _ = _play_event_from_hand(state, repo, "SEC", "177")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert idle.instance_id in offered
        assert busy.instance_id not in offered
        assert fresh.instance_id not in offered
        state = _choose(state, idle.instance_id)
        state = _drain(state)
        assert not _find_instance(state, idle.instance_id).exhausted
        ps = state.player_by_id("P0")
        assert any(u.card_def.name == "Spy"
                   for u in ps.ground_arena + ps.space_arena)


# ── sec-set:16 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestAggressiveNegotiations_SEC_179:
    """Attack with a unit; +1/+0 per card in your hand."""

    def test_SEC_179_bonus_equals_hand_size(self, repo):
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "58"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "179")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 3     # the event has left the hand


class TestSoullessOne_SEC_190:
    """On Attack: disclose Cunning/Cunning/Villainy → ready 2 resources."""

    def test_SEC_190_disclosing_readies_two_resources(self, repo):
        state = _make_state()
        soulless = _place(state, "P0", _get_card(repo, "SEC", "190"), "space")
        # SOR_203 is mono-Cunning; SEC_190's own aspects are Cunning+Villainy.
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "203"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "203"))
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "190"))
        _give_resources(state, "P0", 4)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _fire_on_attack(state, soulless)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_all(state)
        ready = sum(1 for r in state.player_by_id("P0").resources
                    if not r.exhausted)
        assert ready == 2


class TestNoOneEverKnew_SEC_196:
    """For each friendly Official unit, exhaust an enemy unit."""

    def test_SEC_196_exhausts_one_enemy_per_official(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "108"), "ground")   # Official
        _place(state, "P0", _get_card(repo, "SEC", "102"), "ground")   # Official
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")     # not Official
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        for e in (e1, e2):
            e.exhausted = False
        state, _ = _play_event_from_hand(state, repo, "SEC", "196")
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.context["remaining"] == 2
        for e in (e1, e2):
            pick = next(a for a in legal_actions(state)
                        if isinstance(a, SelectTokenTarget) and a.target_id == e.instance_id)
            state = apply(state, pick)
        assert _find_instance(state, e1.instance_id).exhausted
        assert _find_instance(state, e2.instance_id).exhausted

    def test_SEC_196_fizzles_with_no_official(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "196")
        assert not any(d.kind == "select_token" for d in state.pending_decisions)


class TestRebelPropagandist_SEC_202:
    """When Played / When Defeated: another friendly gets +1/+0 and Saboteur."""

    def test_SEC_202_buffs_another_friendly_with_saboteur(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        prop = _place(state, "P0", _get_card(repo, "SEC", "202"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, prop)
        state = _choose(state, friend.instance_id)
        state = _drain(state)
        buffed = _find_instance(state, friend.instance_id)
        assert compute_power(state, buffed) == 4
        assert has_keyword(state, buffed, Keyword.SABOTEUR)

    def test_SEC_202_fires_again_when_defeated(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        prop = _place(state, "P0", _get_card(repo, "SEC", "202"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, prop)
        state = _choose(state, friend.instance_id)
        state = _drain(state)
        assert compute_power(state, _find_instance(state, friend.instance_id)) == 4


class TestBlueAce_SEC_204:
    """On Attack: ready an exhausted enemy unit."""

    def test_SEC_204_readies_an_exhausted_enemy(self, repo):
        state = _make_state()
        ace = _place(state, "P0", _get_card(repo, "SEC", "204"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        state = _fire_on_attack(state, ace)
        state = _choose(state, enemy.instance_id)
        state = _drain(state)
        assert not _find_instance(state, enemy.instance_id).exhausted

    def test_SEC_204_fizzles_when_no_enemy_is_exhausted(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        ace = _place(state, "P0", _get_card(repo, "SEC", "204"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = False
        state = _fire_on_attack(state, ace)
        state = _drain(state)
        assert not [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]


class TestLightmaker_SEC_207:
    """When Defeated: choose an arena; exhaust each enemy unit in it."""

    def test_SEC_207_exhausts_every_enemy_in_the_chosen_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        light = _place(state, "P0", _get_card(repo, "SEC", "207"), "space")
        g1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        g2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        sp = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        for u in (g1, g2, sp, friend):
            u.exhausted = False
        state = _fire_when_defeated(state, light)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        ground = next(a for a in legal_actions(state)
                      if isinstance(a, SelectModalOption) and a.option_idx == 1)
        state = apply(state, ground)
        state = _drain(state)
        assert _find_instance(state, g1.instance_id).exhausted
        assert _find_instance(state, g2.instance_id).exhausted
        assert not _find_instance(state, sp.instance_id).exhausted    # other arena
        assert not _find_instance(state, friend.instance_id).exhausted  # not enemy


class TestLibertine_SEC_212:
    """+1/+0 per captive guarded; When Played an enemy captures a friendly unit."""

    def test_SEC_212_enemy_unit_captures_the_chosen_friendly(self, repo):
        state = _make_state()
        libertine = _place(state, "P0", _get_card(repo, "SEC", "212"), "space")
        captor = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        prey = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, libertine)
        state = _choose(state, captor.instance_id)
        state = _choose(state, prey.instance_id)
        state = _drain(state)
        captives = [c for p in state.players for c in p.capture_pile]
        assert [c.instance_id for c in captives] == [prey.instance_id]
        assert captives[0].captured_by == captor.instance_id

    def test_SEC_212_gains_power_per_guarded_captive(self, repo):
        from swu.engine.actions import compute_power, _apply_capture
        state = _make_state()
        libertine = _place(state, "P0", _get_card(repo, "SEC", "212"), "space")
        assert compute_power(state, libertine) == 3
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _apply_capture(state, libertine.instance_id, prey.instance_id)
        assert compute_power(state, _find_instance(state, libertine.instance_id)) == 4


# ── sec-set:17 — Combat tricks, buffs & tempo ─────────────────────────────────

def _exhaust_all_resources(state, pid):
    for r in state.player_by_id(pid).resources:
        r.exhausted = True


class TestEmissarysSheathipede_SEC_215:
    """When Defeated: each opponent readies a resource."""

    def test_SEC_215_opponent_readies_one_resource(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "SEC", "215"), "space")
        _give_resources(state, "P0", 3)
        _give_resources(state, "P1", 3)
        _exhaust_all_resources(state, "P0")
        _exhaust_all_resources(state, "P1")
        state = _fire_when_defeated(state, ship)
        state = _drain(state)
        assert sum(1 for r in state.player_by_id("P1").resources
                   if not r.exhausted) == 1
        assert all(r.exhausted for r in state.player_by_id("P0").resources)


class TestRegulationsBureaucrat_SEC_216:
    """Action [Exhaust]: exhaust an enemy resource."""

    def test_SEC_216_exhausts_one_enemy_resource(self, repo):
        state = _make_state()
        clerk = _place(state, "P0", _get_card(repo, "SEC", "216"), "ground")
        clerk.exhausted = False
        _give_resources(state, "P0", 2)
        _give_resources(state, "P1", 3)
        state = _use(state, clerk)
        state = _drain(state)
        assert sum(1 for r in state.player_by_id("P1").resources
                   if r.exhausted) == 1
        assert all(not r.exhausted for r in state.player_by_id("P0").resources)
        assert _find_instance(state, clerk.instance_id).exhausted   # the cost


class TestEbonHawk_SEC_219:
    """On Attack: disclose Heroism and/or Villainy for two separate payoffs."""

    def test_SEC_219_heroism_buffs_the_hawk_villainy_debuffs_the_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        hawk = _place(state, "P0", _get_card(repo, "SEC", "219"), "space")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))    # Heroism
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "190"))   # Villainy
        state = _fire_on_attack(state, hawk, defender)
        state = _drain(state)
        # Heroism is offered first (pushed last), then Villainy.
        state = _disclose_all(state)
        state = _disclose_all(state)
        assert compute_power(state, _find_instance(state, hawk.instance_id)) == 5
        assert compute_power(state, _find_instance(state, defender.instance_id)) == 0

    def test_SEC_219_only_offers_the_icons_you_hold(self, repo):
        state = _make_state()
        hawk = _place(state, "P0", _get_card(repo, "SEC", "219"), "space")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))    # Heroism only
        state = _fire_on_attack(state, hawk, defender)
        state = _drain(state)
        assert sum(1 for d in state.pending_decisions if d.kind == "disclose") == 1


class TestHiredSlicer_SEC_220:
    """On Attack: reveal a deck's top 2; may exhaust a unit sharing a Trait."""

    def test_SEC_220_offers_only_units_sharing_a_revealed_trait(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        slicer = _place(state, "P0", _get_card(repo, "SEC", "220"), "ground")
        # SOR_46 is a Rebel/Trooper unit; SEC_190 is a Fighter/Separatist/Vehicle.
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        match = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        match.exhausted = False
        miss = _place(state, "P1", _get_card(repo, "SEC", "190"), "space")
        miss.exhausted = False
        state = _fire_on_attack(state, slicer)
        state = _drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert match.instance_id in offered
        assert miss.instance_id not in offered
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == match.instance_id))
        assert _find_instance(state, match.instance_id).exhausted
        assert len(state.player_by_id("P1").deck) == 2      # both went to the bottom


class TestUnrulyAstromech_SEC_221:
    """When Defeated: exhaust an enemy unit."""

    def test_SEC_221_exhausts_an_enemy_unit(self, repo):
        state = _make_state()
        astro = _place(state, "P0", _get_card(repo, "SEC", "221"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = False
        state = _fire_when_defeated(state, astro)
        state = _choose(state, enemy.instance_id)
        state = _drain(state)
        assert _find_instance(state, enemy.instance_id).exhausted


class TestSynaraSan_SEC_225:
    """On Attack: ready a friendly resource per friendly unit."""

    def test_SEC_225_readies_one_resource_per_friendly_unit(self, repo):
        state = _make_state()
        synara = _place(state, "P0", _get_card(repo, "SEC", "225"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # not friendly
        _give_resources(state, "P0", 5)
        _exhaust_all_resources(state, "P0")
        state = _fire_on_attack(state, synara)
        state = _drain(state)
        assert sum(1 for r in state.player_by_id("P0").resources
                   if not r.exhausted) == 2


class TestAccelerateOurPlans_SEC_228:
    """Exhaust a friendly unit; if you do, another unit attacks with +3/+0."""

    def test_SEC_228_exhausts_then_grants_a_buffed_attack(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        fodder = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        fodder.exhausted = False
        striker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        striker.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "228")
        state = _choose(state, fodder.instance_id)
        state = _drain(state)
        assert _find_instance(state, fodder.instance_id).exhausted
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack" and top.context["power_bonus"] == 3
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert striker.instance_id in attackers
        assert fodder.instance_id not in attackers      # "ANOTHER unit"


# ── sec-set:18 — Combat tricks, buffs & tempo ─────────────────────────────────
# (SEC_231 Implicate is escalated — no test here; see the module note.)

class TestCatchUnawares_SEC_229:
    """Attack with a unit; the defender gets -4/-0 for this attack."""

    def test_SEC_229_defender_is_debuffed_for_the_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        attacker.exhausted = False
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _ = _play_event_from_hand(state, repo, "SEC", "229")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["defender_power_bonus"] == -4
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = _drain(apply(state, atk))
        # The defender's power went 3 → 0, so the attacker took nothing back.
        assert _find_instance(state, attacker.instance_id).damage == 0
        assert _find_instance(state, defender.instance_id).damage == 3


class TestTheWrongRide_SEC_235:
    """Exhaust 2 enemy resources."""

    def test_SEC_235_exhausts_two_enemy_resources_only(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 5)
        _give_resources(state, "P1", 4)
        state, _ = _play_event_from_hand(state, repo, "SEC", "235", resources=5)
        state = _drain(state)
        assert sum(1 for r in state.player_by_id("P1").resources
                   if r.exhausted) == 2


class TestUndercoverOperation_SEC_236:
    """Ready a unit played this phase; a Spy token if it costs 3 or less."""

    def test_SEC_236_readies_and_makes_a_spy_for_a_cheap_unit(self, repo):
        state = _make_state()
        cheap = _place(state, "P0", _get_card(repo, "SEC", "221"), "ground")  # cost 3
        cheap.exhausted = True
        state.game_memory.units_played_this_phase.add(cheap.instance_id)
        state, _ = _play_event_from_hand(state, repo, "SEC", "236")
        state = _choose(state, cheap.instance_id)
        state = _drain(state)
        assert not _find_instance(state, cheap.instance_id).exhausted
        ps = state.player_by_id("P0")
        assert any(u.card_def.name == "Spy" for u in ps.ground_arena + ps.space_arena)

    def test_SEC_236_no_spy_for_an_expensive_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        dear = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # cost 4
        dear.exhausted = True
        state.game_memory.units_played_this_phase.add(dear.instance_id)
        idle = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        state, _ = _play_event_from_hand(state, repo, "SEC", "236")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert idle.instance_id not in offered      # wasn't played this phase
        state = _choose(state, dear.instance_id)
        state = _drain(state)
        assert not _find_instance(state, dear.instance_id).exhausted
        ps = state.player_by_id("P0")
        assert not any(u.card_def.name == "Spy"
                       for u in ps.ground_arena + ps.space_arena)


class TestFNTrooperCorps_SEC_243:
    """When Played: an Experience token to ANOTHER friendly unit."""

    def test_SEC_243_tokens_another_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        corps = _place(state, "P0", _get_card(repo, "SEC", "243"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, corps)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {friend.instance_id}     # friendly, and not itself
        state = _choose(state, friend.instance_id)
        state = _drain(state)
        host = _find_instance(state, friend.instance_id)
        assert any(u.card_def.name == "Experience" for u in host.attached_upgrades)


class TestHighCommandCouncilor_SEC_249:
    """While you control another Official unit, Raid 2."""

    def test_SEC_249_raid_two_needs_a_second_official(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        councilor = _place(state, "P0", _get_card(repo, "SEC", "249"), "ground")
        assert keyword_value(state, councilor, Keyword.RAID) == 0
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Official
        assert keyword_value(state, councilor, Keyword.RAID) == 0
        _place(state, "P0", _get_card(repo, "SEC", "108"), "ground")  # Official
        assert keyword_value(state, councilor, Keyword.RAID) == 2


class TestRestoreFreedom_SEC_257:
    """Play a unit from hand, 1 cheaper per Heroism icon among friendly units."""

    def test_SEC_257_discount_scales_with_heroism_icons(self, repo):
        state = _make_state()
        # SOR_46 is Vigilance/Heroism — one Heroism pip each.
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # not friendly
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "257")
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert top.context["cost_reduction"] == 2

    def test_SEC_257_plays_the_chosen_unit_from_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "257", resources=20)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = _drain(apply(state, play))
        ps = state.player_by_id("P0")
        assert any(u.instance_id == unit.instance_id
                   for u in ps.ground_arena + ps.space_arena)


# ── sec-set:19 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestInspectorsShuttle_SEC_260:
    """When Played: name a card; an Experience token per copy of it in an
    opponent's hand."""

    def test_SEC_260_experience_per_named_copy_in_opponent_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard
        from swu.engine.keywords import experience_on
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "260"), "space")
        prey = _get_card(repo, "SOR", "46")
        _put_in_hand(state, "P1", prey)
        _put_in_hand(state, "P1", prey)
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "237"))
        state = _drain(_fire_when_played(state, shuttle))
        assert state.pending_decisions[-1].kind == "name_a_card"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, NameCard) and a.name == prey.name)
        state = _drain(apply(state, pick))
        assert experience_on(_find_instance(state, shuttle.instance_id)) == 2

    def test_SEC_260_naming_a_singleton_gives_one_token(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard
        from swu.engine.keywords import experience_on
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "260"), "space")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        other = _get_card(repo, "SOR", "237")
        _put_in_hand(state, "P1", other)
        state = _drain(_fire_when_played(state, shuttle))
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, NameCard) and a.name == other.name)
        state = _drain(apply(state, pick))
        assert experience_on(_find_instance(state, shuttle.instance_id)) == 1

    def test_SEC_260_no_prompt_when_the_opponent_hand_is_empty(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "260"), "space")
        state = _drain(_fire_when_played(state, shuttle))
        assert not state.pending_decisions


class TestInspiringSenator_SEC_261:
    """When Defeated: the next Official unit you play this phase costs 1 less."""

    @staticmethod
    def _cost_of_playing(state, unit_ci):
        from swu.engine.actions import legal_actions, apply, PlayCard
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayCard)
                   and a.instance_id == unit_ci.instance_id)
        before = sum(1 for r in state.player_by_id("P0").resources if r.exhausted)
        after = apply(state, act)
        return sum(1 for r in after.player_by_id("P0").resources
                   if r.exhausted) - before

    def test_SEC_261_next_official_unit_costs_one_less(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 20)
        official = _put_in_hand(state, "P0", _get_card(repo, "SEC", "45"))
        undiscounted = self._cost_of_playing(state, official)

        senator = _place(state, "P0", _get_card(repo, "SEC", "261"), "ground")
        state = _drain(_fire_when_defeated(state, senator))
        assert self._cost_of_playing(state, official) == undiscounted - 1

    def test_SEC_261_does_not_discount_a_non_official_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 20)
        other = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        undiscounted = self._cost_of_playing(state, other)

        senator = _place(state, "P0", _get_card(repo, "SEC", "261"), "ground")
        state = _drain(_fire_when_defeated(state, senator))
        assert self._cost_of_playing(state, other) == undiscounted


# ── sec-set:20 — Miscellaneous abilities ──────────────────────────────────────

def _disclose_fully(state):
    """Apply DiscloseSelectCard until the disclose decision resolves."""
    from swu.engine.actions import legal_actions, apply, DiscloseSelectCard
    for _ in range(8):
        if not state.pending_decisions or state.pending_decisions[-1].kind != "disclose":
            return state
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, DiscloseSelectCard))
        state = apply(state, pick)
    return state


class TestCassianAndor_SEC_12:
    """Undeployed: friendly units that damaged a base this phase can't be attacked.
    Deployed: while you hold initiative he survives 0 HP and enemy defeat effects."""

    def test_SEC_12_base_damager_cannot_be_attacked(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SEC", "12"))
        raider = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        state.active_player_index = 1
        assert any(isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == raider.instance_id
                   for a in legal_actions(state))
        state.game_memory.units_dealt_base_damage_this_round.add(raider.instance_id)
        assert not any(isinstance(a, AttackWithUnit)
                       and a.defender_id == raider.instance_id
                       for a in legal_actions(state))

    def test_SEC_12_sentinel_beats_the_aura(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SEC", "12"))
        raider = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")  # Sentinel
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        state.active_player_index = 1
        state.game_memory.units_dealt_base_damage_this_round.add(raider.instance_id)
        assert any(isinstance(a, AttackWithUnit)
                   and a.defender_id == raider.instance_id
                   for a in legal_actions(state))

    def test_SEC_12_no_aura_once_he_deploys(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        _deploy(state, "P0", _get_card(repo, "SEC", "12"))
        raider = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        state.active_player_index = 1
        state.game_memory.units_dealt_base_damage_this_round.add(raider.instance_id)
        assert any(isinstance(a, AttackWithUnit)
                   and a.defender_id == raider.instance_id
                   for a in legal_actions(state))

    def test_SEC_12_deployed_survives_no_remaining_hp_with_initiative(self, repo):
        from swu.engine.actions import legal_actions, apply, Pass
        state = _make_state()
        cassian = _deploy(state, "P0", _get_card(repo, "SEC", "12"))
        cassian.damage = 99
        state.initiative_holder = 0
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, Pass)))
        assert _find_instance(state, cassian.instance_id) is not None

    def test_SEC_12_deployed_dies_without_initiative(self, repo):
        from swu.engine.actions import legal_actions, apply, Pass
        state = _make_state()
        cassian = _deploy(state, "P0", _get_card(repo, "SEC", "12"))
        cassian.damage = 99
        state.initiative_holder = 1
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, Pass)))
        assert _find_instance(state, cassian.instance_id) is None


class TestCondemn_SEC_38:
    """While the attached unit attacks it loses all other abilities, and the
    defending player may disclose Vigilance+Villainy to give it −6/−0."""

    def test_SEC_38_attacking_host_loses_its_keywords(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "38"), "P0")
        assert has_keyword(state, host, Keyword.SENTINEL)
        state = _drain(_fire_on_attack(state, host))
        host = _find_instance(state, host.instance_id)
        assert not has_keyword(state, host, Keyword.SENTINEL)

    def test_SEC_38_defender_discloses_for_minus_six(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "168"), "ground")  # 8/5
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "38"), "P0")
        _put_in_hand(state, "P1", _get_card(repo, "SEC", "38"))  # Vigilance+Villainy
        state = _drain(_fire_on_attack(state, host))
        top = state.pending_decisions[-1]
        assert top.kind == "disclose" and top.deciding_player_id == "P1"
        state = _disclose_fully(state)
        assert compute_power(state, _find_instance(state, host.instance_id)) == 2

    def test_SEC_38_no_disclose_prompt_when_the_defender_cannot_cover(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "38"), "P0")
        state = _drain(_fire_on_attack(state, host))
        assert not state.pending_decisions


class TestSenatorChuchi_SEC_45:
    """On Attack: give another friendly Official unit Restore 2 for this phase."""

    def test_SEC_45_grants_restore_2_to_another_official(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        chuchi = _place(state, "P0", _get_card(repo, "SEC", "45"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SEC", "261"), "ground")  # Official
        state = _drain(_fire_on_attack(state, chuchi))
        state = _choose(state, ally.instance_id) if state.pending_decisions else state
        state = _drain(state)
        assert keyword_value(state, _find_instance(state, ally.instance_id),
                             Keyword.RESTORE) == 2

    def test_SEC_45_keeps_her_own_printed_restore_1(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        chuchi = _place(state, "P0", _get_card(repo, "SEC", "45"), "ground")
        assert keyword_value(state, chuchi, Keyword.RESTORE) == 1


class TestCaptainRex_SEC_48:
    """When Played / when he completes an attack: he and an enemy unit gain
    Sentinel for this phase."""

    def test_SEC_48_no_printed_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        rex = _place(state, "P0", _get_card(repo, "SEC", "48"), "ground")
        assert not has_keyword(state, rex, Keyword.SENTINEL)

    def test_SEC_48_when_played_gives_both_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        rex = _place(state, "P0", _get_card(repo, "SEC", "48"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drain(_fire_when_played(state, rex))
        state = _drain(_choose(state, foe.instance_id))
        assert has_keyword(state, _find_instance(state, rex.instance_id),
                           Keyword.SENTINEL)
        assert has_keyword(state, _find_instance(state, foe.instance_id),
                           Keyword.SENTINEL)


class TestDiplomaticImmunity_SEC_52:
    """Attached unit gains: when attacked, you may disclose VVHH to give the
    attacker −2/−0 for this attack."""

    def test_SEC_52_disclose_debuffs_the_attacker(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "52"), "P0")
        for _ in range(2):  # each copy carries Vigilance + Heroism
            _put_in_hand(state, "P0", _get_card(repo, "SEC", "52"))
        attacker = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        before = compute_power(state, attacker)
        state = _drain(_fire_on_attack(state, attacker, host))
        assert state.pending_decisions[-1].kind == "disclose"
        state = _disclose_fully(state)
        assert compute_power(state, _find_instance(
            state, attacker.instance_id)) == before - 2

    def test_SEC_52_no_prompt_with_an_uncoverable_hand(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "52"), "P0")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        state = _drain(_fire_on_attack(state, attacker, host))
        assert not state.pending_decisions


class TestEscapePod_SEC_56:
    """When Played: you may have this unit capture a friendly non-Vehicle,
    non-leader unit."""

    def test_SEC_56_captures_a_friendly_non_vehicle(self, repo):
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "SEC", "56"), "space")
        prey = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, pod)
        state = _accept_optional_and_run(state)
        if state.pending_decisions:
            state = _drain(_choose(state, prey.instance_id))
        assert _find_instance(state, prey.instance_id) is None
        assert prey.instance_id in {
            c.instance_id for c in state.player_by_id("P0").capture_pile}

    def test_SEC_56_never_offers_a_vehicle(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "SEC", "56"), "space")
        _place(state, "P0", _get_card(repo, "SEC", "260"), "space")  # Vehicle
        state = _fire_when_played(state, pod)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── sec-set:21 — Miscellaneous abilities ──────────────────────────────────────

def _spy_count(state, player_id):
    ps = state.player_by_id(player_id)
    return sum(1 for u in ps.ground_arena + ps.space_arena
               if u.card_def.name == "Spy")


class TestWillrowHood_SEC_61:
    """While he carries exactly 1 friendly upgrade, that upgrade can't be defeated
    or returned to hand by enemy card abilities."""

    def test_SEC_61_sole_upgrade_is_protected(self, repo):
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        hood = _place(state, "P0", _get_card(repo, "SEC", "61"), "ground")
        upg = _attach_upgrade_directly(state, hood, _get_card(repo, "SOR", "53"), "P0")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert _target_protected(state, upg.instance_id, foe, "defeat") is True
        assert _target_protected(state, upg.instance_id, foe, "return") is True

    def test_SEC_61_two_upgrades_break_the_exactly_one_clause(self, repo):
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        hood = _place(state, "P0", _get_card(repo, "SEC", "61"), "ground")
        upg = _attach_upgrade_directly(state, hood, _get_card(repo, "SOR", "53"), "P0")
        _attach_upgrade_directly(state, hood, _get_card(repo, "SOR", "136"), "P0")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert _target_protected(state, upg.instance_id, foe, "defeat") is False

    def test_SEC_61_does_not_protect_another_units_upgrade(self, repo):
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "61"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_directly(state, other, _get_card(repo, "SOR", "53"), "P0")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert _target_protected(state, upg.instance_id, foe, "defeat") is False


class TestUmbaranMobileCannon_SEC_67:
    """The first damage instance each phase is prevented outright."""

    @staticmethod
    def _attack(state, attacker, defender):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state.active_player_index = 1
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        return _drain(apply(state, act))

    def test_SEC_67_first_damage_this_phase_is_prevented(self, repo):
        state = _make_state()
        cannon = _place(state, "P0", _get_card(repo, "SEC", "67"), "ground")
        a1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        a1.exhausted = False
        state = self._attack(state, a1, cannon)
        survivor = _find_instance(state, cannon.instance_id)
        assert survivor is not None and survivor.damage == 0

    def test_SEC_67_the_second_instance_lands(self, repo):
        state = _make_state()
        cannon = _place(state, "P0", _get_card(repo, "SEC", "67"), "ground")
        a1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        a2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        a1.exhausted = False
        a2.exhausted = False
        state = self._attack(state, a1, cannon)
        state = self._attack(state, a2, cannon)
        assert _find_instance(state, cannon.instance_id) is None


class TestBelovedOrator_SEC_97:
    def test_SEC_97_creates_a_spy_token(self, repo):
        state = _make_state()
        orator = _place(state, "P0", _get_card(repo, "SEC", "97"), "ground")
        state = _drain(_fire_when_played(state, orator))
        assert _spy_count(state, "P0") == 1


class TestTradeRouteTaxation_SEC_126:
    """If you control more units than the chosen opponent, they can't play events
    for this phase."""

    def test_SEC_126_locks_the_opponents_events(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        their_event = _put_in_hand(state, "P1", _get_card(repo, "SEC", "126"))
        _give_resources(state, "P1", 20)
        state, _ = _play_event_from_hand(state, repo, "SEC", "126", resources=20)
        state = _drain(state)
        state.active_player_index = 1
        assert not any(isinstance(a, PlayCard)
                       and a.instance_id == their_event.instance_id
                       for a in legal_actions(state))

    def test_SEC_126_does_nothing_without_a_unit_advantage(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        their_event = _put_in_hand(state, "P1", _get_card(repo, "SEC", "126"))
        _give_resources(state, "P1", 20)
        state, _ = _play_event_from_hand(state, repo, "SEC", "126", resources=20)
        state = _drain(state)
        state.active_player_index = 1
        assert any(isinstance(a, PlayCard)
                   and a.instance_id == their_event.instance_id
                   for a in legal_actions(state))


class TestLetsTalk_SEC_131:
    """Each friendly unit captures an enemy non-leader unit in the same arena;
    3 cheaper if a friendly unit left play this phase."""

    def test_SEC_131_every_friendly_unit_must_capture(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, CaptureWithUnit, FinishMultiCapture,
        )
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "237"), "space")
        prey_g = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        prey_s = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")
        state, _ = _play_event_from_hand(state, repo, "SEC", "131", resources=30)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "multi_capture_pairing"
        assert not any(isinstance(a, FinishMultiCapture)
                       for a in legal_actions(state)), "mandatory: no opt-out"
        for _ in range(2):
            pick = next(a for a in legal_actions(state)
                        if isinstance(a, CaptureWithUnit))
            state = apply(state, pick)
        captured = {c.instance_id for c in state.player_by_id("P0").capture_pile}
        assert {prey_g.instance_id, prey_s.instance_id} == captured

    def test_SEC_131_costs_three_less_after_a_friendly_unit_died(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard
        def _cost(with_death):
            state = _make_state()
            _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
            _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
            evt = _put_in_hand(state, "P0", _get_card(repo, "SEC", "131"))
            _give_resources(state, "P0", 30)
            if with_death:
                state.game_memory.defeated_controllers_this_round.append("P0")
            act = next(a for a in legal_actions(state)
                       if isinstance(a, PlayCard) and a.instance_id == evt.instance_id)
            after = apply(state, act)
            return sum(1 for r in after.player_by_id("P0").resources if r.exhausted)
        assert _cost(True) == _cost(False) - 3


class TestImperialOccupier_SEC_132:
    def test_SEC_132_creates_a_spy_token_on_defeat(self, repo):
        state = _make_state()
        occupier = _place(state, "P0", _get_card(repo, "SEC", "132"), "ground")
        state = _drain(_fire_when_defeated(state, occupier))
        assert _spy_count(state, "P0") == 1


class TestTheGalleon_SEC_141:
    """When Played: you may disclose AAV to create 3 Spy tokens."""

    def test_SEC_141_disclosing_creates_three_spies(self, repo):
        state = _make_state()
        galleon = _place(state, "P0", _get_card(repo, "SEC", "141"), "space")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "132"))  # Aggression+Villainy
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "175"))  # Aggression
        state = _drain(_fire_when_played(state, galleon))
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drain(_disclose_fully(state))
        assert _spy_count(state, "P0") == 3

    def test_SEC_141_declining_creates_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        galleon = _place(state, "P0", _get_card(repo, "SEC", "141"), "space")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "132"))
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "175"))
        state = _drain(_fire_when_played(state, galleon))
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineDisclose))
        state = _drain(apply(state, decline))
        assert _spy_count(state, "P0") == 0


# ── sec-set:22 — Miscellaneous abilities ──────────────────────────────────────

def _pick_modal(state, idx):
    from swu.engine.actions import legal_actions, apply, SelectModalOption
    act = next(a for a in legal_actions(state)
               if isinstance(a, SelectModalOption) and a.option_idx == idx)
    return _drain(apply(state, act))


class TestConfidenceInVictory_SEC_145:
    """First action only; choose an arena; sole control of it at regroup wins."""

    def test_SEC_145_sole_control_of_the_arena_wins_at_regroup(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "145", resources=30)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        state = _pick_modal(state, 1)  # ground
        assert state.game_memory.win_at_regroup_sole_arena
        from swu.engine.actions import _enter_regroup
        _enter_regroup(state)
        assert state.is_terminal()
        assert state.player_by_id("P1").base_instance.damage >= \
            state.player_by_id("P1").base_instance.card_def.hp

    def test_SEC_145_a_contested_arena_wins_nothing(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "145", resources=30)
        state = _pick_modal(_drain(state), 1)
        from swu.engine.actions import _enter_regroup
        _enter_regroup(state)
        assert not state.is_terminal()
        assert not state.game_memory.win_at_regroup_sole_arena

    def test_SEC_145_not_playable_after_your_first_action(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        evt = _put_in_hand(state, "P0", _get_card(repo, "SEC", "145"))
        _give_resources(state, "P0", 30)
        assert any(isinstance(a, PlayCard) and a.instance_id == evt.instance_id
                   for a in legal_actions(state))
        state.game_memory.actions_taken_this_phase["P0"] = 1
        assert not any(isinstance(a, PlayCard) and a.instance_id == evt.instance_id
                       for a in legal_actions(state))


class TestLuthensHaulcraft_SEC_153:
    """When Defeated: disclose AAH to make an opponent discard 2."""

    def test_SEC_153_disclosing_discards_two_enemy_cards(self, repo):
        state = _make_state()
        craft = _place(state, "P0", _get_card(repo, "SEC", "153"), "space")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "132"))  # Aggression+Villainy
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "153"))  # Aggression+Heroism
        for _ in range(3):
            _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _drain(_fire_when_defeated(state, craft))
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drain(_disclose_fully(state))
        assert len(state.player_by_id("P1").hand) == 1

    def test_SEC_153_no_prompt_without_the_icons(self, repo):
        state = _make_state()
        craft = _place(state, "P0", _get_card(repo, "SEC", "153"), "space")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _drain(_fire_when_defeated(state, craft))
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == 1


class TestChairmanPapanoida_SEC_159:
    """When ANY player draws in the action phase: disclose AA → a Spy token."""

    def test_SEC_159_fires_when_the_opponent_draws(self, repo):
        state = _make_state()
        chairman = _place(state, "P0", _get_card(repo, "SEC", "159"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "175"))  # Aggression
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "181"))  # Aggression
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        _draw_cards(state, state.player_by_id("P1"), 1)
        state = _fire_draw_observers(state)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drain(_disclose_fully(state))
        assert _spy_count(state, "P0") == 1
        assert chairman.instance_id

    def test_SEC_159_fires_when_its_own_controller_draws(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "159"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "175"))
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "181"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        _draw_cards(state, state.player_by_id("P0"), 1)
        state = _fire_draw_observers(state)
        state = _drain(_disclose_fully(state))
        assert _spy_count(state, "P0") == 1


class TestAmbitionsReward_SEC_175:
    def test_SEC_175_creates_a_spy_token(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "175"), "P0")
        state = _drain(_fire_upgrade_played(state, upg, host))
        assert _spy_count(state, "P0") == 1


class TestPursueTheLead_SEC_178:
    """Choose a player; they discard a card; a Spy token if it cost 3 or less."""

    def test_SEC_178_opponent_discards_and_a_cheap_card_pays_off(self, repo):
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "237"))  # cost 2
        state, _ = _play_event_from_hand(state, repo, "SEC", "178", resources=20)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        state = _pick_modal(state, 2)  # the opponent
        assert len(state.player_by_id("P1").hand) == 0
        assert _spy_count(state, "P0") == 1

    def test_SEC_178_an_expensive_discard_makes_no_token(self, repo):
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "LOF", "168"))  # cost 6
        state, _ = _play_event_from_hand(state, repo, "SEC", "178", resources=20)
        state = _pick_modal(_drain(state), 2)
        assert len(state.player_by_id("P1").hand) == 0
        assert _spy_count(state, "P0") == 0

    def test_SEC_178_you_may_choose_yourself(self, repo):
        state = _make_state()
        mine = _put_in_hand(state, "P0", _get_card(repo, "SOR", "237"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "178", resources=20)
        state = _pick_modal(_drain(state), 1)  # yourself
        assert mine.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").discard}
        assert _spy_count(state, "P0") == 1


class TestUnauthorizedInvestigation_SEC_181:
    def test_SEC_181_makes_one_spy_and_a_second_on_disclose(self, repo):
        state = _make_state()
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "175"))  # Aggression
        state, _ = _play_event_from_hand(state, repo, "SEC", "181", resources=20)
        state = _drain(state)
        assert _spy_count(state, "P0") == 1
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drain(_disclose_fully(state))
        assert _spy_count(state, "P0") == 2

    def test_SEC_181_makes_one_spy_with_no_aggression_card(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "SEC", "181", resources=20)
        state = _drain(state)
        assert _spy_count(state, "P0") == 1
        assert not state.pending_decisions


class TestScreechingTIEFighter_SEC_185:
    """On Attack: a chosen ground unit loses (and can't gain) keywords this phase."""

    def test_SEC_185_target_loses_its_printed_keywords(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "SEC", "185"), "space")
        guard = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        assert has_keyword(state, guard, Keyword.SENTINEL)
        state = _fire_on_attack(state, tie)
        state = _accept_optional_and_run(state)
        state = _drain(_choose(state, guard.instance_id))
        assert not has_keyword(state, _find_instance(state, guard.instance_id),
                               Keyword.SENTINEL)

    def test_SEC_185_target_cannot_gain_keywords_either(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import Modifier
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "SEC", "185"), "space")
        guard = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, tie)
        state = _accept_optional_and_run(state)
        state = _drain(_choose(state, guard.instance_id))
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=tie.instance_id,
            target_instance_id=guard.instance_id,
            kind="keyword_grant", value={"keyword": "Sentinel", "value": 0},
            duration="this_phase"))
        assert not has_keyword(state, _find_instance(state, guard.instance_id),
                               Keyword.SENTINEL)


# ── sec-set:23 — Miscellaneous abilities ──────────────────────────────────────

class TestTradeFederationDelegates_SEC_191:
    def test_SEC_191_creates_two_spy_tokens(self, repo):
        state = _make_state()
        delegates = _place(state, "P0", _get_card(repo, "SEC", "191"), "ground")
        state = _drain(_fire_when_played(state, delegates))
        assert _spy_count(state, "P0") == 2


class TestGrandMoffTarkin_SEC_192:
    """When Played: take control of an enemy non-leader Vehicle; it goes home when
    he leaves play."""

    def test_SEC_192_takes_control_of_an_enemy_vehicle(self, repo):
        state = _make_state()
        tarkin = _place(state, "P0", _get_card(repo, "SEC", "192"), "ground")
        vehicle = _place(state, "P1", _get_card(repo, "SEC", "260"), "space")
        state = _drain(_fire_when_played(state, tarkin))
        state = _drain(_choose(state, vehicle.instance_id))
        mine = state.player_by_id("P0")
        assert vehicle.instance_id in {u.instance_id
                                       for u in mine.ground_arena + mine.space_arena}

    def test_SEC_192_owner_reclaims_it_when_he_leaves_play(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        tarkin = _place(state, "P0", _get_card(repo, "SEC", "192"), "ground")
        vehicle = _place(state, "P1", _get_card(repo, "SEC", "260"), "space")
        state = _drain(_fire_when_played(state, tarkin))
        state = _drain(_choose(state, vehicle.instance_id))
        live = state.find_instance(tarkin.instance_id)[1]
        _defeat_unit(state, state.player_by_id("P0"), live)
        theirs = state.player_by_id("P1")
        assert vehicle.instance_id in {u.instance_id
                                       for u in theirs.ground_arena + theirs.space_arena}

    def test_SEC_192_never_targets_a_non_vehicle(self, repo):
        state = _make_state()
        tarkin = _place(state, "P0", _get_card(repo, "SEC", "192"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # not a Vehicle
        state = _drain(_fire_when_played(state, tarkin))
        assert not state.pending_decisions


class TestFullyArmedAndOperational_SEC_194:
    """If an opponent attacked your base this phase, play a unit from hand with
    Ambush."""

    def test_SEC_194_plays_a_unit_after_your_base_was_attacked(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state.game_memory.base_attackers_this_round["P0"] = ["enemy_1"]
        state, _ = _play_event_from_hand(state, repo, "SEC", "194", resources=20)
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == unit.instance_id)
        state = _drain(apply(state, play))
        ps = state.player_by_id("P0")
        assert any(u.instance_id == unit.instance_id
                   for u in ps.ground_arena + ps.space_arena)

    def test_SEC_194_fizzles_if_your_base_was_untouched(self, repo):
        state = _make_state()
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _ = _play_event_from_hand(state, repo, "SEC", "194", resources=20)
        state = _drain(state)
        assert not state.pending_decisions


class TestArrest_SEC_195:
    """Your base captures an enemy non-leader unit; its owner rescues it at the
    start of the regroup phase."""

    def test_SEC_195_base_captures_then_regroup_rescues(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "195", resources=20)
        state = _drain(state)
        state = _drain(_choose(state, victim.instance_id))
        base = state.player_by_id("P0").base_instance
        assert victim.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").capture_pile}
        assert state.find_instance(victim.instance_id)[1].captured_by == \
            base.instance_id
        _enter_regroup(state)
        assert victim.instance_id in {c.instance_id
                                      for c in state.player_by_id("P1").hand}
        assert not state.game_memory.rescue_at_regroup


class TestTalaDurith_SEC_203:
    """Each other friendly unit gains Hidden."""

    def test_SEC_203_grants_hidden_to_other_friendly_units(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tala = _place(state, "P0", _get_card(repo, "SEC", "203"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, ally, Keyword.HIDDEN)
        assert not has_keyword(state, foe, Keyword.HIDDEN)
        assert not has_keyword(state, tala, Keyword.HIDDEN)


class TestEmissariesFromRyloth_SEC_206:
    def test_SEC_206_gives_a_unit_minus_three_power(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        emissaries = _place(state, "P0", _get_card(repo, "SEC", "206"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")  # 8/5
        state = _fire_when_played(state, emissaries)
        state = _accept_optional_and_run(state)
        state = _drain(_choose(state, foe.instance_id))
        assert compute_power(state, _find_instance(state, foe.instance_id)) == 5


class TestStolenStarpathUnit_SEC_210:
    """Attached unit gains: On Attack, name a card; a Spy token per copy in the
    defending player's hand."""

    def test_SEC_210_spy_token_per_named_copy(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "210"), "P0")
        prey = _get_card(repo, "SOR", "237")
        _put_in_hand(state, "P1", prey)
        _put_in_hand(state, "P1", prey)
        state = _drain(_fire_on_attack(state, host))
        assert state.pending_decisions[-1].kind == "name_a_card"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, NameCard) and a.name == prey.name)
        state = _drain(apply(state, pick))
        assert _spy_count(state, "P0") == 2

    def test_SEC_210_no_prompt_against_an_empty_hand(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "210"), "P0")
        state = _drain(_fire_on_attack(state, host))
        assert not state.pending_decisions
        assert _spy_count(state, "P0") == 0


# ── sec-set:24 — Miscellaneous abilities ──────────────────────────────────────

class TestDuchesssInvestigators_SEC_223:
    """When Played: disclose Cunning → each opponent discards a random card."""

    def test_SEC_223_disclosing_costs_the_opponent_a_card(self, repo):
        state = _make_state()
        investigators = _place(state, "P0", _get_card(repo, "SEC", "223"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "223"))  # Cunning
        for _ in range(3):
            _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _drain(_fire_when_played(state, investigators))
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drain(_disclose_fully(state))
        assert len(state.player_by_id("P1").hand) == 2

    def test_SEC_223_declining_costs_them_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineDisclose
        state = _make_state()
        investigators = _place(state, "P0", _get_card(repo, "SEC", "223"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SEC", "223"))
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _drain(_fire_when_played(state, investigators))
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineDisclose))
        state = _drain(apply(state, decline))
        assert len(state.player_by_id("P1").hand) == 1


class TestVelSartha_SEC_224:
    """Each exhausted enemy unit gets −2/−0 while defending."""

    def test_SEC_224_exhausted_defender_is_weakened(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "224"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")  # 8/5
        foe.exhausted = True
        assert compute_power(state, foe, is_defending=True) == 6
        assert compute_power(state, foe) == 8

    def test_SEC_224_a_ready_defender_is_untouched(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "224"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")
        foe.exhausted = False
        assert compute_power(state, foe, is_defending=True) == 8


class TestSpecialModifications_SEC_227:
    """When Played on a Transport, you may create a Spy token."""

    def test_SEC_227_transport_host_offers_the_token(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SEC", "260"), "space")  # Transport
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "227"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        state = _accept_optional_and_run(state)
        state = _drain(state)
        assert _spy_count(state, "P0") == 1

    def test_SEC_227_non_transport_host_is_never_offered(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SEC", "67"), "ground")  # no Transport
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SEC", "227"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestCovertOperative_SEC_253:
    """When Played: capture an enemy non-leader unit costing 2 or less."""

    def test_SEC_253_captures_a_cheap_enemy(self, repo):
        state = _make_state()
        operative = _place(state, "P0", _get_card(repo, "SEC", "253"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")  # cost 2
        state = _drain(_fire_when_played(state, operative))
        if state.pending_decisions:
            state = _drain(_choose(state, prey.instance_id))
        assert _find_instance(state, prey.instance_id) is None
        assert prey.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").capture_pile}

    def test_SEC_253_fizzles_against_an_expensive_board(self, repo):
        state = _make_state()
        operative = _place(state, "P0", _get_card(repo, "SEC", "253"), "ground")
        pricey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state = _drain(_fire_when_played(state, operative))
        assert not state.pending_decisions
        assert _find_instance(state, pricey.instance_id) is not None


class TestRemoteEscortTank_SEC_255:
    """When Played: give a unit Sentinel for this phase (and it has no printed
    Sentinel of its own)."""

    def test_SEC_255_has_no_printed_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tank = _place(state, "P0", _get_card(repo, "SEC", "255"), "ground")
        assert not has_keyword(state, tank, Keyword.SENTINEL)

    def test_SEC_255_grants_sentinel_to_a_chosen_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tank = _place(state, "P0", _get_card(repo, "SEC", "255"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _drain(_fire_when_played(state, tank))
        state = _drain(_choose(state, ally.instance_id))
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL)


# -- sec-set:18 -- framework session: the PINNED PHASE AURA (Implicate SEC_231) --


class TestImplicate_SEC_231:
    """"Choose a unit.  For this phase, it gains Sentinel and: 'When this unit is
    attacked: Create a Spy token.'"  One choice, two halves: the Sentinel modifier
    is also what pins the ongoing aura to the chosen unit."""

    def _cast_on(self, repo, state, unit_ci):
        state, evt = _play_event_from_hand(state, repo, "SEC", "231", resources=30)
        state = _drain(state)
        state = _drain(_choose(state, unit_ci.instance_id))
        return state, evt

    def test_SEC_231_chosen_unit_gains_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = self._cast_on(repo, state, ally)
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL)

    def test_SEC_231_chosen_unit_makes_a_spy_when_attacked(self, repo):
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")
        state, _ = self._cast_on(repo, state, ally)
        assert _spy_count(state, "P0") == 0
        state = _drain(_fire_on_attack(state, foe, _find_instance(state, ally.instance_id)))
        assert _spy_count(state, "P0") == 1

    def test_SEC_231_an_unchosen_unit_is_untouched(self, repo):
        """The aura is pinned to ONE unit — the other friendly unit neither gains
        Sentinel nor makes a token when it is attacked."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")
        state, _ = self._cast_on(repo, state, ally)
        other_now = _find_instance(state, other.instance_id)
        assert not has_keyword(state, other_now, Keyword.SENTINEL)
        state = _drain(_fire_on_attack(state, foe, other_now))
        assert _spy_count(state, "P0") == 0

    def test_SEC_231_an_enemy_unit_may_be_chosen_and_makes_its_own_spy(self, repo):
        """"Choose a unit" is either controller's; the granted ability is the chosen
        unit's own, so ITS controller creates the Spy token."""
        state = _make_state()
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "LOF", "168"), "ground")
        state, _ = self._cast_on(repo, state, prey)
        state = _drain(_fire_on_attack(state, attacker,
                                       _find_instance(state, prey.instance_id)))
        assert _spy_count(state, "P1") == 1
        assert _spy_count(state, "P0") == 0

    def test_SEC_231_the_grant_lapses_at_the_phase_rollover(self, repo):
        """Both halves are phase-scoped: clearing the phase drops the aura source, so
        the very same attack no longer makes a token."""
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "LOF", "168"), "ground")
        state, _ = self._cast_on(repo, state, ally)
        state.game_memory.clear_phase()
        assert state.game_memory.phase_aura_sources == []
        state = _drain(_fire_on_attack(state, foe,
                                       _find_instance(state, ally.instance_id)))
        assert _spy_count(state, "P0") == 0
