"""
SHD (Shadows of the Galaxy) card ability tests.

One focused test per card, asserting behaviour through the public engine
interfaces (legal_actions / apply / trigger firing).  Encoded in the Phase 7
dry run for group ``shd-han-solo:03`` (Direct damage & removal).

Reuses the DB-backed game-state helpers from the SOR card tests.
"""
from __future__ import annotations


from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_when_defeated,
    _fire_on_attack, _fire_upgrade_played, _place_leader, _find_instance,
    _experience_count, _shield_count, _defeat_and_fire, _play_event_from_hand,
    _push_deck_top,
)


def _put_in_hand(state, owner_id, card_def):
    """Put card_def into owner's hand. Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _give_resources(state, owner_id, n, repo):
    """Give `owner_id` n ready resources (a cheap real card as filler)."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    filler = _get_card(repo, "SOR", "46")  # Consular Security Force
    ps = state.player_by_id(owner_id)
    for _ in range(n):
        ps.resources.append(CardInstance(
            instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:6]}",
            card_def=filler, owner_id=owner_id, zone=Zone.RESOURCES,
        ))


class TestRhokaiGunship:
    def test_when_defeated_deals_1_damage(self, repo):
        """SHD_164 When Defeated: Deal 1 damage to a unit or base (mandatory)."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        gunship = _get_card(repo, "SHD", "164")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        gunship_ci = _place(state, "P0", gunship, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_defeated(state, gunship_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 1


class TestDisablingFangFighter:
    def test_no_upgrade_auto_declines(self, repo):
        """SHD_166 When Played: with no upgrade in play, the optional trigger is
        skipped silently."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        fang = _get_card(repo, "SHD", "166")
        state = _make_state()
        fang_ci = _place(state, "P0", fang, "space")
        state = _fire_when_played(state, fang_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_may_defeat_an_upgrade(self, repo):
        """SHD_166 When Played: You may defeat an upgrade."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        import uuid
        fang = _get_card(repo, "SHD", "166")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SOR", "53")  # Luke's Lightsaber (a real Upgrade)
        state = _make_state()
        fang_ci = _place(state, "P0", fang, "space")
        host_ci = _place(state, "P1", host, "ground")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id="P1", zone=Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(up_ci)

        state = _fire_when_played(state, fang_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == up_ci.instance_id)
        state = apply(state, choose)
        # Upgrade is gone from its host.
        _, host_after = state.find_instance(host_ci.instance_id)
        assert all(u.instance_id != up_ci.instance_id for u in host_after.attached_upgrades)


class TestTheChaosOfWar:
    def test_159_each_base_damaged_by_its_owners_hand_size(self, repo):
        """SHD_159 — Deal damage to each player's base equal to that player's hand
        size.  The scaling magnitude differs per base; the just-played event is
        already in discard, so it does not count toward the controller's hand."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        chaos = _get_card(repo, "SHD", "159")  # Event, cost 3 Aggression
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()

        chaos_ci = CardInstance(
            instance_id=f"chaos_{uuid.uuid4().hex[:6]}", card_def=chaos,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(chaos_ci)
        # P0 keeps 2 cards in hand after playing Chaos (Chaos itself moves to
        # discard before resolving, so it is not counted).
        for _ in range(2):
            _put_in_hand(state, "P0", filler)
        # P1 holds 4 cards.
        for _ in range(4):
            _put_in_hand(state, "P1", filler)
        _give_resources(state, "P0", 6, repo)  # cost 3 + 2 off-aspect = 5

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == chaos_ci.instance_id)
        state = apply(state, play)

        assert state.player_by_id("P0").base_instance.damage == 2
        assert state.player_by_id("P1").base_instance.damage == 4

    def test_159_empty_hand_takes_no_damage(self, repo):
        """A player with an empty hand takes 0 (the amount==0 branch is a no-op)."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        chaos = _get_card(repo, "SHD", "159")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        chaos_ci = CardInstance(
            instance_id=f"chaos_{uuid.uuid4().hex[:6]}", card_def=chaos,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(chaos_ci)  # P0's only card
        for _ in range(3):
            _put_in_hand(state, "P1", filler)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == chaos_ci.instance_id)
        state = apply(state, play)

        assert state.player_by_id("P0").base_instance.damage == 0  # empty hand
        assert state.player_by_id("P1").base_instance.damage == 3


class TestDaringRaid:
    def test_event_deals_2_damage(self, repo):
        """SHD_178 Daring Raid — Deal 2 damage to a unit or base (played from hand)."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        raid = _get_card(repo, "SHD", "178")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        enemy_ci = _place(state, "P1", enemy, "ground")
        raid_ci = CardInstance(
            instance_id=f"raid_{uuid.uuid4().hex[:6]}", card_def=raid,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(raid_ci)
        # _make_state's base carries no aspects, so the Aggression pip adds the
        # +2 off-aspect penalty (cost 1 -> 3); give enough ready resources.
        _give_resources(state, "P0", 5, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == raid_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2


# ── Smuggle group (shd-han-solo:01) ───────────────────────────────────────────

from tests.test_smuggle import (  # noqa: E402
    _add_resource, _add_deck_card, _fill_resources, _synthetic_unit,
)


class TestNiteOwlSkirmisher:
    def test_pure_smuggle_card_playable_from_resources(self, repo):
        """SHD_149 — pure Smuggle keyword: playable from the resource zone, no
        residual ability (enters play exhausted as a normal unit)."""
        from swu.engine.actions import legal_actions, apply, SmugglePlay
        nite = _get_card(repo, "SHD", "149")  # Smuggle [5 resources Aggression Heroism]
        state = _make_state()
        smug = _add_resource(state, "P0", nite)
        _fill_resources(state, "P0", 9, repo)  # cost 5 + 4 off-aspect penalty = 9
        _add_deck_card(state, "P0", repo)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)
        _, unit = state.find_instance(smug.instance_id)
        assert unit.zone.name == "GROUND_ARENA"
        assert unit.exhausted  # no "ready" residual


class TestCassianAndor:
    def test_readies_when_played_via_smuggle(self, repo):
        """SHD_148 — When played using Smuggle: Ready this unit."""
        from swu.engine.actions import legal_actions, apply, SmugglePlay
        cassian = _get_card(repo, "SHD", "148")  # Smuggle [5 resources Aggression Heroism]
        state = _make_state()
        smug = _add_resource(state, "P0", cassian)
        _fill_resources(state, "P0", 9, repo)  # cost 9 after off-aspect penalty
        _add_deck_card(state, "P0", repo)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)
        _, unit = state.find_instance(smug.instance_id)
        assert unit.zone.name == "GROUND_ARENA"
        assert not unit.exhausted  # readied by the smuggle trigger

    def test_not_readied_when_played_from_hand(self, repo):
        """The ready trigger is gated on Smuggle — a normal hand play stays
        exhausted."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        cassian = _get_card(repo, "SHD", "148")
        state = _make_state()
        ci = CardInstance(instance_id=f"c_{uuid.uuid4().hex[:6]}", card_def=cassian,
                          owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        _fill_resources(state, "P0", 9, repo)  # printed cost 3 + 4 off-aspect = 7

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id)
        state = apply(state, play)
        _, unit = state.find_instance(ci.instance_id)
        assert unit.exhausted  # entered play exhausted (no smuggle ready)


class TestRecklessGunslinger:
    def test_when_played_deals_1_to_each_base(self, repo):
        """SHD_160 — When Played: Deal 1 damage to each base (any play)."""
        reckless = _get_card(repo, "SHD", "160")
        state = _make_state()
        reckless_ci = _place(state, "P0", reckless, "ground")
        state = _fire_when_played(state, reckless_ci)
        for pid in ("P0", "P1"):
            base = state.player_by_id(pid).base_instance
            assert base.damage == 1


class TestSmugglersAid:
    def test_event_heals_3_from_own_base(self, repo):
        """SHD_252 — Smuggler's Aid: Heal 3 damage from your base."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        aid = _get_card(repo, "SHD", "252")  # Event, Smuggle [3 resources Heroism]
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 5
        ci = CardInstance(instance_id=f"aid_{uuid.uuid4().hex[:6]}", card_def=aid,
                          owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        _fill_resources(state, "P0", 3, repo)  # cost 1 + 2 off-aspect = 3

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id)
        state = apply(state, play)
        assert state.player_by_id("P0").base_instance.damage == 2


class TestTechGrantsSmuggle:
    def test_grants_smuggle_to_resources(self, repo):
        """SHD_248 — Each friendly resource gains Smuggle (cost = card cost + 2)."""
        from swu.engine.actions import legal_actions, apply, SmugglePlay
        tech = _get_card(repo, "SHD", "248")
        _place(state := _make_state(), "P0", tech, "ground")
        # A plain unit (no printed Smuggle) sitting as a resource.
        plain = _synthetic_unit(name="Plain", cost=1, smuggle_text="", aspects=())
        plain = type(plain)(**{**plain.__dict__, "keywords": ()})  # strip Smuggle kw
        smug = _add_resource(state, "P0", plain)
        _fill_resources(state, "P0", 4, repo)  # granted cost 1+2 = 3
        _add_deck_card(state, "P0", repo)

        acts = [a for a in legal_actions(state)
                if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id]
        assert len(acts) == 1
        state = apply(state, acts[0])
        _, unit = state.find_instance(smug.instance_id)
        assert unit.zone.name == "GROUND_ARENA"

    def test_no_grant_without_tech(self, repo):
        """Without Tech in play, a plain resource is not smuggleable."""
        from swu.engine.actions import legal_actions, SmugglePlay
        state = _make_state()
        plain = _synthetic_unit(name="Plain", cost=1, smuggle_text="", aspects=())
        plain = type(plain)(**{**plain.__dict__, "keywords": ()})
        _add_resource(state, "P0", plain)
        _fill_resources(state, "P0", 4, repo)
        _add_deck_card(state, "P0", repo)
        assert [a for a in legal_actions(state) if isinstance(a, SmugglePlay)] == []


class TestHotshotDL44Blaster:
    """SHD_174 — Upgrade.  When played using Smuggle: Attack with attached unit.
    (granted-attack-restricted-attacker primitive pinned to the host, group
    ``shd-han-solo:09`` follow-up; resolver collects an upgrade's
    WhenPlayedViaSmuggle trigger.)"""

    def _smuggle_onto_host(self, repo):
        """Place a ready non-Vehicle host, smuggle Hotshot onto it, return state."""
        from swu.engine.actions import legal_actions, apply, SmugglePlay
        host_def = _get_card(repo, "SOR", "46")  # Consular Security Force, power 3
        hotshot = _get_card(repo, "SHD", "174")   # Smuggle [3, Cunning]
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        smug = _add_resource(state, "P0", hotshot)
        _fill_resources(state, "P0", 9, repo)  # cost 3 + off-aspect penalty
        _add_deck_card(state, "P0", repo)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay)
                   and a.instance_id == smug.instance_id
                   and a.upgrade_target_id == host.instance_id)
        state = apply(state, act)
        return state, host, host_def

    def test_shd174_smuggle_grants_attack_with_host(self, repo):
        """The host (now carrying the +2/+0 blaster) attacks; only it may attack."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, compute_power
        state, host, host_def = self._smuggle_onto_host(repo)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attacker_ids = {a.attacker_id for a in legal_actions(state)
                        if isinstance(a, AttackWithUnit)}
        assert attacker_ids == {host.instance_id}

        _, host_now = state.find_instance(host.instance_id)
        expected = compute_power(state, host_now, is_attacking=True)
        assert expected == host_def.power + 2  # base power + blaster's +2
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == host.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == expected
        assert not state.pending_decisions

    def test_shd174_hand_play_grants_no_attack(self, repo):
        """Played normally from hand (not via Smuggle), the trigger does not fire."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        host_def = _get_card(repo, "SOR", "46")
        hotshot = _get_card(repo, "SHD", "174")
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        ci = CardInstance(instance_id=f"h_{uuid.uuid4().hex[:6]}", card_def=hotshot,
                          owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        _give_resources(state, "P0", 5, repo)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id
                    and a.upgrade_target_id == host.instance_id)
        state = apply(state, play)
        assert not any(d.kind == "granted_attack" for d in state.pending_decisions)


class TestArmedToTheTeeth:
    """SHD_175 — Upgrade.  Attached unit gains: "On Attack: Give another friendly
    unit +2/+0 for this phase."  Exercises the upgrade-grants-host-a-triggered-
    ability primitive (GrantedAbility): the granted OnAttack trigger fires when
    the HOST attacks and resolves from the host's perspective ("another friendly
    unit" = a friendly unit other than the attacker)."""

    def _attach(self, state, host_ci, repo):
        from swu.engine.state import CardInstance
        import uuid
        upgrade = _get_card(repo, "SHD", "175")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id=host_ci.owner_id, zone=host_ci.zone)
        host_ci.attached_upgrades.append(up_ci)
        return up_ci

    def test_grants_buff_to_another_friendly_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_power)
        unit = _get_card(repo, "SOR", "46")  # Consular Security Force
        state = _make_state()
        host = _place(state, "P0", unit, "ground")
        ally = _place(state, "P0", unit, "ground")
        enemy = _place(state, "P1", unit, "ground")
        self._attach(state, host, repo)

        ally_power_before = compute_power(state, ally)
        # The host carries the upgrade's printed +2/+0 at all times (independent
        # of the granted ability) — capture it to prove the granted buff does NOT
        # additionally land on the attacker.
        host_power_before = compute_power(state, host)
        assert host_power_before == unit.power + 2
        state = _fire_on_attack(state, host)

        # A mandatory resolve_effects decision offering only OTHER friendly units:
        # the attacking host itself and the enemy unit are not legal targets.
        assert state.pending_decisions[-1].kind == "resolve_effects"
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert targets == {ally.instance_id}

        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == ally.instance_id)
        state = apply(state, choose)
        assert not state.pending_decisions

        _, ally_now = state.find_instance(ally.instance_id)
        assert compute_power(state, ally_now) == ally_power_before + 2
        # The host (attacker) gets only its printed upgrade bonus — "another"
        # friendly unit got the granted buff, not the attacker.
        _, host_now = state.find_instance(host.instance_id)
        assert compute_power(state, host_now) == host_power_before

    def test_buff_expires_at_end_of_phase(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_power, _expire_modifiers)
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P0", unit, "ground")
        ally = _place(state, "P0", unit, "ground")
        self._attach(state, host, repo)

        state = _fire_on_attack(state, host)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget))
        state = apply(state, choose)
        _, ally_now = state.find_instance(ally.instance_id)
        assert compute_power(state, ally_now) == unit.power + 2

        _expire_modifiers(state, "this_phase")
        _, ally_after = state.find_instance(ally.instance_id)
        assert compute_power(state, ally_after) == unit.power

    def test_no_other_friendly_unit_fizzles(self, repo):
        """With only the host on the board, the granted trigger has no legal
        target and fizzles silently — no decision is pushed."""
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P0", unit, "ground")
        self._attach(state, host, repo)
        # An enemy unit is not a legal target ("friendly" only), so it cannot
        # keep the trigger alive.
        _place(state, "P1", unit, "ground")

        state = _fire_on_attack(state, host)
        assert not state.pending_decisions

    def test_no_longer_deferred(self):
        from swu.abilities.registry import is_escape_hatch, get_abilities, GrantedAbility
        import swu.cards.shd.abilities  # noqa: F401  (ensure registered)
        assert not is_escape_hatch("SHD", "175")
        specs = get_abilities("SHD", "175")
        assert specs and isinstance(specs[0], GrantedAbility)


# ── Bounty group (shd-han-solo:02) ────────────────────────────────────────────

class TestBountyKeywordSeam:
    """Framework-level test of the Bounty modelling seam, independent of any one
    card: the SOURCE_EXHAUSTED condition atom that gates a "while this unit is
    exhausted, it gains Bounty" ability."""

    def test_source_exhausted_condition(self, repo):
        from swu.abilities.registry import ConditionCheck, Condition
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        ci = _place(state, "P0", unit, "ground")
        cond = ConditionCheck(Condition.SOURCE_EXHAUSTED)

        ci.exhausted = False
        assert cond.evaluate(state, ci) is False
        ci.exhausted = True
        assert cond.evaluate(state, ci) is True


class TestUnlicensedHeadhunter:
    def test_bounty_heals_opponent_base_when_exhausted(self, repo):
        """SHD_165 — Bounty (while exhausted): when defeated, the OPPONENT heals 5
        damage from their base; the dying unit's own base is untouched."""
        headhunter = _get_card(repo, "SHD", "165")
        state = _make_state()
        hh_ci = _place(state, "P0", headhunter, "ground")
        hh_ci.exhausted = True
        state.player_by_id("P1").base_instance.damage = 5
        state.player_by_id("P0").base_instance.damage = 4

        state = _fire_when_defeated(state, hh_ci)
        assert not state.pending_decisions  # resolves inline, no prompt
        assert state.player_by_id("P1").base_instance.damage == 0  # collector healed
        assert state.player_by_id("P0").base_instance.damage == 4  # owner untouched

    def test_no_bounty_when_ready(self, repo):
        """The Bounty is only gained while exhausted — a unit defeated while
        ready collects no bounty."""
        headhunter = _get_card(repo, "SHD", "165")
        state = _make_state()
        hh_ci = _place(state, "P0", headhunter, "ground")
        hh_ci.exhausted = False
        state.player_by_id("P1").base_instance.damage = 5

        state = _fire_when_defeated(state, hh_ci)
        assert state.player_by_id("P1").base_instance.damage == 5  # no heal


class TestCloneDeserter:
    def test_shd_95_bounty_opponent_draws(self, repo):
        """SHD_95 — Bounty: when this P0 unit is defeated, the collector (P1) draws
        a card.  Resolves inline (no prompt)."""
        from swu.engine.state import CardInstance, Zone
        deserter = _get_card(repo, "SHD", "95")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        d_ci = _place(state, "P0", deserter, "ground")
        # Give the collector (P1) a deck card and the owner (P0) one too, so we can
        # tell exactly who drew.
        state.player_by_id("P1").deck.append(
            CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        state.player_by_id("P0").deck.append(
            CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = _fire_when_defeated(state, d_ci)
        assert not state.pending_decisions  # non-targeted draw resolves inline
        assert len(state.player_by_id("P1").deck) == 0, "collector (P1) drew"
        assert len(state.player_by_id("P1").hand) == p1_hand_before + 1
        assert len(state.player_by_id("P0").deck) == 1, "owner (P0) did not draw"


class TestCartelTurncoat:
    def test_shd_195_bounty_opponent_draws(self, repo):
        """SHD_195 — Bounty: when this P0 unit is defeated, the collector (P1)
        draws a card.  Resolves inline (no prompt)."""
        from swu.engine.state import CardInstance, Zone
        turncoat = _get_card(repo, "SHD", "195")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        t_ci = _place(state, "P0", turncoat, "ground")
        state.player_by_id("P1").deck.append(
            CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        state.player_by_id("P0").deck.append(
            CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = _fire_when_defeated(state, t_ci)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").deck) == 0, "collector (P1) drew"
        assert len(state.player_by_id("P1").hand) == p1_hand_before + 1
        assert len(state.player_by_id("P0").deck) == 1, "owner (P0) did not draw"


class TestBountyGuildInitiate:
    def test_no_other_bounty_hunter_no_trigger(self, repo):
        """SHD_254: the trigger is not even offered without ANOTHER Bounty Hunter."""
        from swu.engine.actions import legal_actions, AcceptTrigger, ChooseTarget
        initiate = _get_card(repo, "SHD", "254")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        init_ci = _place(state, "P0", initiate, "ground")
        _place(state, "P1", enemy, "ground")
        state = _fire_when_played(state, init_ci)
        assert not state.pending_decisions
        acts = legal_actions(state)
        assert not any(isinstance(a, (AcceptTrigger, ChooseTarget)) for a in acts)

    def test_with_other_bounty_hunter_may_deal_2(self, repo):
        """SHD_254: with another Bounty Hunter, may deal 2 to a ground unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        initiate = _get_card(repo, "SHD", "254")
        other_bh = _get_card(repo, "SHD", "254")  # also a Bounty Hunter
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        init_ci = _place(state, "P0", initiate, "ground")
        _place(state, "P0", other_bh, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_played(state, init_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2


# ── Card advantage & disruption (shd-han-solo:03) ─────────────────────────────

class TestWookieeWarrior:
    def test_shd249_draws_with_another_wookiee(self, repo):
        """SHD_249 — When Played: with another Wookiee unit in play, draw a card
        (mandatory, resolves inline)."""
        from tests.test_smuggle import _add_deck_card
        warrior = _get_card(repo, "SHD", "249")  # Wookiee
        state = _make_state()
        # Another friendly Wookiee unit already in play.
        _place(state, "P0", warrior, "ground")
        played_ci = _place(state, "P0", warrior, "ground")
        deck_ci = _add_deck_card(state, "P0", repo)[0]

        assert state.player_by_id("P0").hand == []
        state = _fire_when_played(state, played_ci)
        assert not state.pending_decisions  # mandatory draw, no prompt
        hand = state.player_by_id("P0").hand
        assert len(hand) == 1 and hand[0].instance_id == deck_ci.instance_id

    def test_shd249_no_draw_without_another_wookiee(self, repo):
        """SHD_249 — the only Wookiee in play is the source itself, so the
        'another Wookiee' condition fails and no draw happens (the source does
        not count itself)."""
        from tests.test_smuggle import _add_deck_card
        warrior = _get_card(repo, "SHD", "249")
        state = _make_state()
        played_ci = _place(state, "P0", warrior, "ground")
        _add_deck_card(state, "P0", repo)

        state = _fire_when_played(state, played_ci)
        assert not state.pending_decisions
        assert state.player_by_id("P0").hand == []  # no draw


# ── Combat tricks, buffs & tempo (shd-han-solo:04) ────────────────────────────

class TestHuntingNexu:
    def test_gains_raid_2_with_another_aggression_unit(self, repo):
        """SHD_168 — While you control another Aggression unit, this unit gains
        Raid 2 (read through the public keyword/stats layer)."""
        from swu.engine.keywords import keyword_value, Keyword
        from swu.engine.actions import compute_power
        nexu = _get_card(repo, "SHD", "168")          # 4/4, Aggression, no printed kw
        aggro = _get_card(repo, "SOR", "128")          # Death Star Stormtrooper (Aggression)
        state = _make_state()
        nexu_ci = _place(state, "P0", nexu, "ground")

        # Alone: no other Aggression unit -> no Raid, attacking power == base 4.
        assert keyword_value(state, nexu_ci, Keyword.RAID) == 0
        assert compute_power(state, nexu_ci, is_attacking=True) == 4

        # Add another friendly Aggression unit -> Raid 2 winks on (+2 attacking).
        _place(state, "P0", aggro, "ground")
        assert keyword_value(state, nexu_ci, Keyword.RAID) == 2
        assert compute_power(state, nexu_ci, is_attacking=True) == 6
        assert compute_power(state, nexu_ci, is_attacking=False) == 4  # not while defending

    def test_does_not_count_itself_or_enemy(self, repo):
        """The 'another Aggression unit' excludes the Nexu itself and does not
        count an opponent's Aggression unit."""
        from swu.engine.keywords import keyword_value, Keyword
        nexu = _get_card(repo, "SHD", "168")
        aggro = _get_card(repo, "SOR", "128")
        state = _make_state()
        nexu_ci = _place(state, "P0", nexu, "ground")
        # Enemy Aggression unit must not satisfy "you control another".
        _place(state, "P1", aggro, "ground")
        assert keyword_value(state, nexu_ci, Keyword.RAID) == 0


class TestProtectorOfTheThrone:
    def test_gains_sentinel_while_upgraded(self, repo):
        """SHD_247 — While this unit is upgraded, it gains Sentinel."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.keywords import has_keyword, Keyword
        import uuid
        protector = _get_card(repo, "SHD", "247")     # 2/4 Mandalorian, no printed kw
        upgrade = _get_card(repo, "SOR", "53")         # Luke's Lightsaber (real Upgrade)
        state = _make_state()
        prot_ci = _place(state, "P0", protector, "ground")

        # Bare: no upgrade -> no Sentinel.
        assert not has_keyword(state, prot_ci, Keyword.SENTINEL)

        # Attach an upgrade -> Sentinel switches on.
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id="P0", zone=Zone.GROUND_ARENA)
        prot_ci.attached_upgrades.append(up_ci)
        assert has_keyword(state, prot_ci, Keyword.SENTINEL)

        # Remove it -> Sentinel switches back off.
        prot_ci.attached_upgrades.clear()
        assert not has_keyword(state, prot_ci, Keyword.SENTINEL)


class TestHanSolo:
    """SHD_13 Han Solo — group ``shd-han-solo:05`` (new primitive:
    play-from-hand-act-on-result).

    Action [Exhaust] (undeployed) / Action (deployed): Play a unit from your
    hand. It costs 1 resource less. Deal 2 damage to it.
    """

    def _use_han(self, state, han_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == han_ci.instance_id
        )
        return apply(state, use)

    def _play_chosen(self, state, unit_ci):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        play = next(
            a for a in legal_actions(state)
            if isinstance(a, PlayFromHand) and a.instance_id == unit_ci.instance_id
        )
        return apply(state, play)

    def test_undeployed_plays_unit_discounted_and_damages(self, repo):
        """The undeployed action plays a hand unit at −1 cost, deals 2 to it,
        and exhausts Han."""
        from swu.engine.actions import _effective_cost
        han = _get_card(repo, "SHD", "13")
        unit = _get_card(repo, "SOR", "46")  # Consular Security Force, 3/7
        state = _make_state()
        han_ci = _place_leader(state, "P0", han)
        unit_ci = _put_in_hand(state, "P0", unit)
        _give_resources(state, "P0", 10, repo)

        ps0 = state.player_by_id("P0")
        full_cost = _effective_cost(unit, ps0)
        before = ps0.available_resources

        state = self._use_han(state, han_ci)
        # The activated ability pushed a play_from_hand decision.
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "play_from_hand"

        state = self._play_chosen(state, unit_ci)

        ps0 = state.player_by_id("P0")
        # Paid the discounted (−1) cost.
        assert before - ps0.available_resources == max(0, full_cost - 1)
        # Unit is now in play with 2 damage on it.
        _, in_play = state.find_instance(unit_ci.instance_id)
        assert in_play.zone.name == "GROUND_ARENA"
        assert in_play.damage == 2
        # Han paid the exhaust cost.
        _, han_now = state.find_instance(han_ci.instance_id)
        assert han_now.exhausted

    def test_discount_enables_otherwise_unaffordable_unit(self, repo):
        """With resources == effective cost − 1 the unit is unaffordable normally
        but the discount makes it playable via Han."""
        from swu.engine.actions import _effective_cost, legal_actions, PlayFromHand
        han = _get_card(repo, "SHD", "13")
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        han_ci = _place_leader(state, "P0", han)
        unit_ci = _put_in_hand(state, "P0", unit)

        ps0 = state.player_by_id("P0")
        full_cost = _effective_cost(unit, ps0)
        _give_resources(state, "P0", full_cost - 1, repo)

        state = self._use_han(state, han_ci)
        # Decision present and the (otherwise unaffordable) unit is offered.
        assert state.pending_decisions
        offered = [a for a in legal_actions(state)
                   if isinstance(a, PlayFromHand) and a.instance_id == unit_ci.instance_id]
        assert offered, "discounted unit should be playable"

    def test_not_offered_with_no_affordable_unit(self, repo):
        """The action is not even legal when no hand unit is affordable at the
        discount (errata: it cannot be used if it would not change the game
        state)."""
        from swu.engine.actions import legal_actions, UseAbility
        han = _get_card(repo, "SHD", "13")
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        han_ci = _place_leader(state, "P0", han)
        _put_in_hand(state, "P0", unit)
        # No resources at all -> even at −1 the unit (cost ≥ 3) is unaffordable.
        assert not any(
            isinstance(a, UseAbility) and a.source_id == han_ci.instance_id
            for a in legal_actions(state)
        )

    def test_not_offered_with_empty_hand(self, repo):
        """No units in hand -> the action is not offered (costless deployed side
        would otherwise be a legal no-op)."""
        from swu.engine.actions import legal_actions, UseAbility
        han = _get_card(repo, "SHD", "13")
        state = _make_state()
        han_ci = _place_leader(state, "P0", han)
        _give_resources(state, "P0", 10, repo)
        assert not any(
            isinstance(a, UseAbility) and a.source_id == han_ci.instance_id
            for a in legal_actions(state)
        )

    def test_deployed_side_plays_without_exhaust_cost(self, repo):
        """The deployed leader-unit side has no exhaust cost; it still plays a
        hand unit at −1 and deals 2 to it."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _effective_cost
        import uuid
        han = _get_card(repo, "SHD", "13")
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        # Deployed Han: in the ground arena, ready, deployed.
        han_ci = CardInstance(
            instance_id=f"P0_leader_{uuid.uuid4().hex[:6]}",
            card_def=han, owner_id="P0", zone=Zone.GROUND_ARENA)
        han_ci.deployed = True
        han_ci.exhausted = False
        state.player_by_id("P0").ground_arena.append(han_ci)
        unit_ci = _put_in_hand(state, "P0", unit)
        _give_resources(state, "P0", 10, repo)

        ps0 = state.player_by_id("P0")
        full_cost = _effective_cost(unit, ps0)
        before = ps0.available_resources

        state = self._use_han(state, han_ci)
        state = self._play_chosen(state, unit_ci)

        ps0 = state.player_by_id("P0")
        assert before - ps0.available_resources == max(0, full_cost - 1)
        _, in_play = state.find_instance(unit_ci.instance_id)
        assert in_play.damage == 2
        # Deployed side did not exhaust Han (no exhaust cost).
        _, han_now = state.find_instance(han_ci.instance_id)
        assert not han_now.exhausted


# ── New primitive: repeated-modal-per-X (shd-han-solo:06) ─────────────────────

class TestPoeDameron:
    """SHD_153 — On Attack: Discard up to 3 cards from your hand. For each card
    discarded this way, choose a different option: deal 2 damage to a unit or
    base / defeat an upgrade / an opponent discards a card."""

    def _attach_upgrade(self, state, host_ci, repo):
        from swu.engine.state import CardInstance
        import uuid
        upgrade = _get_card(repo, "SOR", "53")  # Luke's Lightsaber (a real Upgrade)
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id=host_ci.owner_id, zone=host_ci.zone)
        host_ci.attached_upgrades.append(up_ci)
        return up_ci

    def test_shd153_three_options_apply(self, repo):
        """Discard 3 cards, then take all three distinct options."""
        from swu.engine.actions import (
            legal_actions, apply, DiscardForModal, ChooseRepeatedMode,
            ChooseRepeatedTarget,
        )
        poe = _get_card(repo, "SHD", "153")
        enemy = _get_card(repo, "SOR", "46")  # sturdy enemy unit
        host = _get_card(repo, "SOR", "46")
        state = _make_state()
        poe_ci = _place(state, "P0", poe, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        host_ci = _place(state, "P1", host, "ground")
        up_ci = self._attach_upgrade(state, host_ci, repo)
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = _fire_on_attack(state, poe_ci, enemy_ci)
        top = state.pending_decisions[-1]
        assert top.kind == "repeated_modal"
        assert top.deciding_player_id == "P0"

        # Discard all 3 hand cards (cap reached → auto-advance to options).
        for _ in range(3):
            discard = next(a for a in legal_actions(state)
                           if isinstance(a, DiscardForModal))
            state = apply(state, discard)
        assert len(state.player_by_id("P0").hand) == 0

        # Option 1: deal 2 damage to the enemy unit.
        state = apply(state, ChooseRepeatedMode("deal_2_damage"))
        state = apply(state, ChooseRepeatedTarget(enemy_ci.instance_id))
        # Option 2: defeat the upgrade.
        state = apply(state, ChooseRepeatedMode("defeat_upgrade"))
        state = apply(state, ChooseRepeatedTarget(up_ci.instance_id))
        # Option 3: opponent discards (no target).
        state = apply(state, ChooseRepeatedMode("opponent_discards"))

        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2
        _, host_after = state.find_instance(host_ci.instance_id)
        assert all(u.instance_id != up_ci.instance_id
                   for u in host_after.attached_upgrades)
        assert len(state.player_by_id("P1").hand) == p1_hand_before - 1

    def test_shd153_up_to_allows_taking_fewer(self, repo):
        """"Up to 3": discard exactly 1, then choose exactly one option."""
        from swu.engine.actions import (
            legal_actions, apply, DiscardForModal, FinishModalDiscard,
            ChooseRepeatedMode, ChooseRepeatedTarget,
        )
        poe = _get_card(repo, "SHD", "153")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        poe_ci = _place(state, "P0", poe, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))

        state = _fire_on_attack(state, poe_ci, enemy_ci)
        # Discard one, then finish early.
        discard = next(a for a in legal_actions(state)
                       if isinstance(a, DiscardForModal))
        state = apply(state, discard)
        finish = next(a for a in legal_actions(state)
                      if isinstance(a, FinishModalDiscard))
        state = apply(state, finish)

        # Exactly one option to choose (one card discarded).
        modes = [a for a in legal_actions(state) if isinstance(a, ChooseRepeatedMode)]
        assert len(modes) == 3  # all three offered for the single pick
        state = apply(state, ChooseRepeatedMode("deal_2_damage"))
        state = apply(state, ChooseRepeatedTarget(enemy_ci.instance_id))

        # Only one option resolved; decision is finished.
        assert not any(d.kind == "repeated_modal" for d in state.pending_decisions)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2

    def test_shd153_options_are_distinct(self, repo):
        """A chosen option is not offered again on the next pick."""
        from swu.engine.actions import (
            legal_actions, apply, DiscardForModal, ChooseRepeatedMode,
            ChooseRepeatedTarget,
        )
        poe = _get_card(repo, "SHD", "153")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        poe_ci = _place(state, "P0", poe, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        for _ in range(2):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))

        state = _fire_on_attack(state, poe_ci, enemy_ci)
        for _ in range(2):
            discard = next(a for a in legal_actions(state)
                           if isinstance(a, DiscardForModal))
            state = apply(state, discard)

        # First pick: deal damage.
        state = apply(state, ChooseRepeatedMode("deal_2_damage"))
        state = apply(state, ChooseRepeatedTarget(enemy_ci.instance_id))
        # Second pick: deal_2_damage no longer offered.
        modes = {a.mode for a in legal_actions(state)
                 if isinstance(a, ChooseRepeatedMode)}
        assert "deal_2_damage" not in modes
        assert modes == {"defeat_upgrade", "opponent_discards"}

    def test_shd153_empty_hand_fizzles(self, repo):
        """No cards in hand → "discard up to 3" discards nothing → no decision."""
        poe = _get_card(repo, "SHD", "153")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        poe_ci = _place(state, "P0", poe, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_on_attack(state, poe_ci, enemy_ci)
        assert not any(d.kind == "repeated_modal" for d in state.pending_decisions)


class TestWrecker:
    """SHD_154 — Overwhelm. When Played: You may defeat a friendly resource. If
    you do, deal 5 damage to a ground unit.  (sacrifice-resource-cost primitive,
    group ``shd-han-solo:07``.)"""

    def test_shd154_sacrifice_then_deal_5(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SacrificeResource, ChooseSacrificeTarget,
        )
        wrecker = _get_card(repo, "SHD", "154")
        state = _make_state()
        wrecker_ci = _place(state, "P0", wrecker, "ground")
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 2, repo)
        res_before = len(state.player_by_id("P0").resources)

        state = _fire_when_played(state, wrecker_ci)
        top = state.pending_decisions[-1]
        assert top.kind == "sacrifice_resource"
        assert top.deciding_player_id == "P0"

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SacrificeResource)))
        assert len(state.player_by_id("P0").resources) == res_before - 1

        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseSacrificeTarget)
                   and a.target_id == enemy_ci.instance_id)
        state = apply(state, tgt)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 5

    def test_shd154_may_decline(self, repo):
        """"You may": declining keeps the resource and deals no damage."""
        from swu.engine.actions import legal_actions, apply, DeclineSacrifice
        wrecker = _get_card(repo, "SHD", "154")
        state = _make_state()
        wrecker_ci = _place(state, "P0", wrecker, "ground")
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 2, repo)
        res_before = len(state.player_by_id("P0").resources)

        state = _fire_when_played(state, wrecker_ci)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineSacrifice)))
        assert len(state.player_by_id("P0").resources) == res_before
        _, enemy = state.find_instance(enemy_ci.instance_id)
        assert enemy.damage == 0
        assert not any(d.kind == "sacrifice_resource" for d in state.pending_decisions)

    def test_shd154_no_resources_no_prompt(self, repo):
        """With no resources to spend the optional cost can't be paid — Wrecker
        enters play and the ability does nothing (no prompt)."""
        wrecker = _get_card(repo, "SHD", "154")
        state = _make_state()
        wrecker_ci = _place(state, "P0", wrecker, "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, wrecker_ci)
        assert not any(d.kind == "sacrifice_resource" for d in state.pending_decisions)


class TestDesperateAttack:
    """SHD_179 — Desperate Attack (Event): Attack with a damaged unit. It gets
    +2/+0 for this attack.  (granted-attack-restricted-attacker primitive,
    group ``shd-han-solo:09``.)"""

    def _setup(self, repo):
        """P0 has one damaged and one undamaged ready unit, plus the event in
        hand and resources to play it."""
        from swu.engine.actions import apply, PlayCard
        unit_def = _get_card(repo, "SOR", "46")  # Consular Security Force, power 3
        state = _make_state()
        damaged = _place(state, "P0", unit_def, "ground")
        damaged.damage = 1
        undamaged = _place(state, "P0", unit_def, "ground")
        event_ci = _put_in_hand(state, "P0", _get_card(repo, "SHD", "179"))
        _give_resources(state, "P0", 5, repo)
        state = apply(state, PlayCard(event_ci.instance_id))
        return state, damaged, undamaged, unit_def

    def test_shd179_only_damaged_unit_may_attack(self, repo):
        """The granted attack offers only the damaged unit as attacker."""
        from swu.engine.actions import legal_actions, AttackWithUnit
        state, damaged, undamaged, _ = self._setup(repo)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attacker_ids = {
            a.attacker_id for a in legal_actions(state)
            if isinstance(a, AttackWithUnit)
        }
        assert damaged.instance_id in attacker_ids
        assert undamaged.instance_id not in attacker_ids

    def test_shd179_damaged_attacker_gets_plus_2(self, repo):
        """Attacking base with the damaged unit deals power + 2."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state, damaged, _, unit_def = self._setup(repo)
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == damaged.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == unit_def.power + 2
        # The this-attack modifier must not linger after combat settles.
        assert not state.pending_decisions
        assert all(m.duration != "this_attack" for m in state.modifiers)

    def test_shd179_fizzles_with_no_damaged_unit(self, repo):
        """With no damaged unit, the mandatory attack fizzles (decline only)."""
        from swu.engine.actions import (
            apply, legal_actions, PlayCard, AttackWithUnit, DeclineGrantedAttack,
        )
        unit_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        _place(state, "P0", unit_def, "ground")  # undamaged only
        event_ci = _put_in_hand(state, "P0", _get_card(repo, "SHD", "179"))
        _give_resources(state, "P0", 5, repo)
        state = apply(state, PlayCard(event_ci.instance_id))
        acts = legal_actions(state)
        assert not any(isinstance(a, AttackWithUnit) for a in acts)
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)
        base_before = state.players[1].base_instance.damage
        state = apply(state, next(a for a in acts if isinstance(a, DeclineGrantedAttack)))
        assert not state.pending_decisions
        assert state.players[1].base_instance.damage == base_before


class TestGreySquadronYWing:
    """SHD_246 — On Attack: An opponent chooses a unit or base they control.
    You may deal 2 damage to it.  (opponent-chooses-target primitive, group
    ``shd-han-solo:10``.)"""

    def _attack(self, repo, *, enemy_units=1):
        """Place Grey Squadron in P0's space arena with `enemy_units` enemy units,
        fire its On Attack trigger, and return (state, gsy_ci, enemy_cis)."""
        gsy = _get_card(repo, "SHD", "246")
        state = _make_state()
        gsy_ci = _place(state, "P0", gsy, "space")
        enemies = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                   for _ in range(enemy_units)]
        state = _fire_on_attack(state, gsy_ci, None)
        return state, gsy_ci, enemies

    def test_shd246_opponent_picks_then_controller_deals_2(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, ConfirmOpponentDamage,
        )
        state, _, enemies = self._attack(repo, enemy_units=1)
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target"
        # Stage 1: the OPPONENT (P1) decides.
        assert top.deciding_player_id == "P1"
        assert top.context["stage"] == "choose"

        enemy_ci = enemies[0]
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseOwnTarget)
                    and a.target_id == enemy_ci.instance_id)
        state = apply(state, pick)

        # Stage 2: control returns to the source's controller (P0).
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P0"
        assert top.context["stage"] == "confirm"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ConfirmOpponentDamage)))
        assert not any(d.kind == "opponent_chooses_target"
                       for d in state.pending_decisions)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2

    def test_shd246_controller_may_decline(self, repo):
        """"You may": the controller can decline and deal no damage."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, DeclineOpponentDamage,
        )
        state, _, enemies = self._attack(repo, enemy_units=1)
        enemy_ci = enemies[0]
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseOwnTarget)
                                  and a.target_id == enemy_ci.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineOpponentDamage)))
        assert not any(d.kind == "opponent_chooses_target"
                       for d in state.pending_decisions)
        _, enemy = state.find_instance(enemy_ci.instance_id)
        assert enemy.damage == 0

    def test_shd246_choose_offers_all_opponent_cards_and_base(self, repo):
        """The opponent may choose any of their units or their base."""
        from swu.engine.actions import legal_actions, ChooseOwnTarget
        state, _, enemies = self._attack(repo, enemy_units=2)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseOwnTarget)}
        for e in enemies:
            assert e.instance_id in offered
        assert state.players[1].base_instance.instance_id in offered
        # Grey Squadron (the source) belongs to P0, so it is never offered.
        assert len([a for a in legal_actions(state)
                    if isinstance(a, ChooseOwnTarget)]) == 3

    def test_shd246_opponent_may_dump_on_base(self, repo):
        """The opponent can pick its base; the 2 damage lands there if dealt."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, ConfirmOpponentDamage,
        )
        state, _, _ = self._attack(repo, enemy_units=0)
        base_id = state.players[1].base_instance.instance_id
        base_before = state.players[1].base_instance.damage
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseOwnTarget)
                                  and a.target_id == base_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ConfirmOpponentDamage)))
        assert state.players[1].base_instance.damage - base_before == 2

    def test_shd246_lethal_damage_defeats_on_clean_stack(self, repo):
        """Dealing the 2 to a 1-HP unit defeats it (pop-then-deal: the defeat
        trigger lands after the decision is gone)."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, ConfirmOpponentDamage,
        )
        state, _, enemies = self._attack(repo, enemy_units=1)
        enemy_ci = enemies[0]
        # Pre-damage the enemy so 2 more is lethal.
        _, e = state.find_instance(enemy_ci.instance_id)
        from swu.engine.actions import compute_hp
        e.damage = compute_hp(state, e) - 2
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseOwnTarget)
                                  and a.target_id == enemy_ci.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ConfirmOpponentDamage)))
        assert _find_instance(state, enemy_ci.instance_id) is None
        assert not state.pending_decisions


# ── New primitive: control-change (shd-han-solo:02, Stolen Landspeeder) ───────

class TestControlChangeSeam:
    """Framework-level tests of the control-change primitive (actions.change_control)
    independent of any one card: a unit moves between players' arenas while its
    owner_id is preserved, and a defeated foreign-controlled unit goes to its
    OWNER's discard (not its controller's)."""

    def test_change_control_relocates_arena_keeps_owner(self, repo):
        from swu.engine.actions import change_control
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        ci = _place(state, "P0", unit, "ground")

        change_control(state, ci, "P1")

        assert ci.owner_id == "P0"                                   # owner unchanged
        assert ci not in state.player_by_id("P0").ground_arena       # left P0's arena
        assert ci in state.player_by_id("P1").ground_arena           # now P1 controls it
        # find_instance reports the controller (the holding player).
        ctrl_ps, found = state.find_instance(ci.instance_id)
        assert ctrl_ps.player_id == "P1"
        assert found is ci

    def test_change_control_noop_when_already_controlled(self, repo):
        from swu.engine.actions import change_control
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        ci = _place(state, "P0", unit, "ground")
        change_control(state, ci, "P0")
        assert ci in state.player_by_id("P0").ground_arena

    def test_defeated_foreign_unit_goes_to_owner_discard(self, repo):
        """A unit owned by P0 but controlled by P1, when defeated, is discarded
        to P0's (the owner's) pile — not P1's."""
        from swu.engine.actions import _defeat_unit
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        # Owned by P0, sitting in P1's arena (as if control-changed).
        ci = _place(state, "P1", unit, "ground")
        ci.owner_id = "P0"

        _defeat_unit(state, state.player_by_id("P1"), ci)

        assert ci in state.player_by_id("P0").discard           # owner's discard
        assert ci not in state.player_by_id("P1").discard
        assert _find_instance(state, ci.instance_id) is None    # no longer in play


class TestStolenLandspeeder:
    """SHD_161 — When Played (from hand): an opponent takes control of it.
    Bounty — If you own this unit, play it from your discard pile for free and
    give an Experience token to it.  (control-change escalation, group
    ``shd-han-solo:02``.)"""

    def test_when_played_from_hand_opponent_takes_control(self, repo):
        landspeeder = _get_card(repo, "SHD", "161")
        state = _make_state()
        ls_ci = _place(state, "P0", landspeeder, "ground")

        # _fire_when_played supplies no play_source → defaults to "hand".
        state = _fire_when_played(state, ls_ci)

        assert not state.pending_decisions                       # resolves inline
        assert ls_ci.owner_id == "P0"                            # still owned by P0
        assert ls_ci in state.player_by_id("P1").ground_arena    # opponent controls it
        assert ls_ci not in state.player_by_id("P0").ground_arena

    def test_no_control_change_when_not_from_hand(self, repo):
        """A replay-from-discard / Smuggle play does not re-hand the unit over."""
        from swu.engine.events import UnitEntersPlay
        from swu.abilities.resolver import fire_triggered_abilities
        landspeeder = _get_card(repo, "SHD", "161")
        state = _make_state()
        ls_ci = _place(state, "P0", landspeeder, "ground")
        evt = UnitEntersPlay(player_id="P0", instance_id=ls_ci.instance_id,
                             card_name=ls_ci.card_def.display_name, arena="Ground")
        state.event_log.append(evt)
        state = fire_triggered_abilities(state, evt, after_all_player_idx=0,
                                         event_ctx={"play_source": "discard"})
        assert ls_ci in state.player_by_id("P0").ground_arena    # control NOT changed

    def test_full_play_from_hand_steals_via_apply(self, repo):
        """End-to-end through PlayCard: playing Stolen Landspeeder from hand puts
        it under the opponent's control (play_source threaded as "hand")."""
        from swu.engine.actions import legal_actions, apply, PlayCard
        landspeeder = _get_card(repo, "SHD", "161")  # cost 1
        state = _make_state()
        ls_ci = _put_in_hand(state, "P0", landspeeder)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ls_ci.instance_id)
        state = apply(state, play)

        ctrl_ps, found = state.find_instance(ls_ci.instance_id)
        assert ctrl_ps.player_id == "P1"          # opponent now controls it
        assert found.owner_id == "P0"             # P0 still owns it

    def test_bounty_replays_from_owner_under_owner_control_with_experience(self, repo):
        """The full loop: a Stolen Landspeeder owned by P0 but controlled by P1,
        when defeated, is replayed for free under P0's control with an Experience
        token — and is NOT left in any discard pile."""
        from swu.engine.actions import _defeat_unit
        from swu.cards.models import TokenUpgrade
        landspeeder = _get_card(repo, "SHD", "161")
        state = _make_state()
        ls_ci = _place(state, "P1", landspeeder, "ground")   # P1 controls
        ls_ci.owner_id = "P0"                                # P0 owns
        ls_ci.damage = 1                                     # carries some damage

        _defeat_unit(state, state.player_by_id("P1"), ls_ci)

        # Back in play under the OWNER's (collector's) control, fresh.
        ctrl_ps, found = state.find_instance(ls_ci.instance_id)
        assert ctrl_ps.player_id == "P0"
        assert found is ls_ci
        assert found.damage == 0
        # Gained an Experience token (+1/+1).
        assert any(isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Experience"
                   for u in found.attached_upgrades)
        # Not stranded in either discard pile (no double-homing).
        assert ls_ci not in state.player_by_id("P0").discard
        assert ls_ci not in state.player_by_id("P1").discard
        assert not state.pending_decisions

    def test_bounty_no_replay_when_owner_controlled_at_death(self, repo):
        """When it dies under its OWNER's control, the collector (the opponent)
        does not own it, so the bounty does nothing and it goes to the owner's
        discard normally — no infinite self-replay."""
        from swu.engine.actions import _defeat_unit
        landspeeder = _get_card(repo, "SHD", "161")
        state = _make_state()
        ls_ci = _place(state, "P0", landspeeder, "ground")   # P0 owns AND controls

        _defeat_unit(state, state.player_by_id("P0"), ls_ci)

        assert _find_instance(state, ls_ci.instance_id) is None   # not replayed
        assert ls_ci in state.player_by_id("P0").discard          # owner's discard
        assert not state.pending_decisions


# ── Bounty keyword group (the-mandalorian:01) ─────────────────────────────────
# Three bounty-granting upgrades (Public Enemy SHD_68, Wanted SHD_221, Rich
# Reward SHD_261) and a combat-trick unit (Chain Code Collector SHD_216).  The
# bounty upgrades exercise the GrantedAbility(WhenDefeated) collection from a
# *defeated* unit's now-detached upgrades, resolving for the collector (the
# opponent of the dying unit's controller).

def _attach_bounty_upgrade(state, host_ci, upgrade_def, owner_id):
    """Attach an upgrade to host_ci, owned by owner_id (the collector for a bounty
    upgrade, which is typically played on an enemy unit)."""
    from swu.engine.state import CardInstance
    import uuid as _u
    up_ci = CardInstance(
        instance_id=f"up_{_u.uuid4().hex[:6]}", card_def=upgrade_def,
        owner_id=owner_id, zone=host_ci.zone)
    host_ci.attached_upgrades.append(up_ci)
    return up_ci


class TestPublicEnemy:
    """SHD_68 — when the host dies, the COLLECTOR (opponent of the host's
    controller) picks a unit to give a Shield token."""

    def test_bounty_lets_collector_shield_a_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _defeat_unit, SelectTokenTarget)
        from swu.engine.keywords import shields_on
        unit = _get_card(repo, "SOR", "46")
        pe = _get_card(repo, "SHD", "68")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")          # P1 controls the host
        collector_unit = _place(state, "P0", unit, "ground")
        _attach_bounty_upgrade(state, host, pe, "P0")        # P0 owns Public Enemy

        _defeat_unit(state, state.player_by_id("P1"), host)

        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        assert top.deciding_player_id == "P0"                # collector, not P1

        give = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == collector_unit.instance_id)
        state = apply(state, give)
        assert not state.pending_decisions
        _, shielded = state.find_instance(collector_unit.instance_id)
        assert shields_on(shielded) == 1

    def test_no_bounty_without_the_upgrade(self, repo):
        from swu.engine.actions import _defeat_unit
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        _place(state, "P0", unit, "ground")
        _defeat_unit(state, state.player_by_id("P1"), host)
        assert not state.pending_decisions


class TestWanted:
    """SHD_221 — the collector readies up to 2 of their own exhausted resources
    (deterministic, resolves inline)."""

    def test_bounty_readies_two_collector_resources(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.state import CardInstance, Zone
        unit = _get_card(repo, "SOR", "46")
        wanted = _get_card(repo, "SHD", "221")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        _attach_bounty_upgrade(state, host, wanted, "P0")    # P0 collects
        ps0 = state.player_by_id("P0")
        for i in range(3):
            r = CardInstance(instance_id=f"res{i}", card_def=unit,
                             owner_id="P0", zone=Zone.RESOURCES)
            r.exhausted = True
            ps0.resources.append(r)

        _defeat_unit(state, state.player_by_id("P1"), host)

        assert not state.pending_decisions                   # inline, no choice
        assert sum(1 for r in ps0.resources if not r.exhausted) == 2

    def test_only_collector_resources_readied(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.state import CardInstance, Zone
        unit = _get_card(repo, "SOR", "46")
        wanted = _get_card(repo, "SHD", "221")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        _attach_bounty_upgrade(state, host, wanted, "P0")
        ps1 = state.player_by_id("P1")
        for i in range(2):
            r = CardInstance(instance_id=f"p1res{i}", card_def=unit,
                             owner_id="P1", zone=Zone.RESOURCES)
            r.exhausted = True
            ps1.resources.append(r)

        _defeat_unit(state, state.player_by_id("P1"), host)
        assert all(r.exhausted for r in ps1.resources)       # P1's stay exhausted


class TestRichReward:
    """SHD_261 — the collector gives an Experience token to up to 2 units."""

    def test_bounty_collector_tokens_up_to_two(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _defeat_unit, SelectTokenTarget)
        unit = _get_card(repo, "SOR", "46")
        rr = _get_card(repo, "SHD", "261")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        a = _place(state, "P0", unit, "ground")
        b = _place(state, "P0", unit, "ground")
        _attach_bounty_upgrade(state, host, rr, "P0")

        _defeat_unit(state, state.player_by_id("P1"), host)
        top = state.pending_decisions[-1]
        assert top.kind == "select_token" and top.deciding_player_id == "P0"

        for u in (a, b):
            give = next(act for act in legal_actions(state)
                        if isinstance(act, SelectTokenTarget)
                        and act.target_id == u.instance_id)
            state = apply(state, give)
        assert not state.pending_decisions
        assert _experience_count(state.find_instance(a.instance_id)[1]) == 1
        assert _experience_count(state.find_instance(b.instance_id)[1]) == 1

    def test_collector_may_stop_early(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _defeat_unit, SelectTokenTarget, FinishSelectToken)
        unit = _get_card(repo, "SOR", "46")
        rr = _get_card(repo, "SHD", "261")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        a = _place(state, "P0", unit, "ground")
        _place(state, "P0", unit, "ground")
        _attach_bounty_upgrade(state, host, rr, "P0")

        _defeat_unit(state, state.player_by_id("P1"), host)
        give = next(act for act in legal_actions(state)
                    if isinstance(act, SelectTokenTarget) and act.target_id == a.instance_id)
        state = apply(state, give)
        finish = next(act for act in legal_actions(state) if isinstance(act, FinishSelectToken))
        state = apply(state, finish)
        assert not state.pending_decisions
        assert _experience_count(state.find_instance(a.instance_id)[1]) == 1


class TestUnrefusableOffer:
    """SHD_226 — the granted Bounty replays the defeated host unit under the
    COLLECTOR's control, ready, and flagged to be defeated at the next regroup."""

    def test_SHD_226_replays_host_under_collector_ready_and_defeat_at_regroup(self, repo):
        from swu.engine.actions import _defeat_unit
        unit = _get_card(repo, "SOR", "46")
        offer = _get_card(repo, "SHD", "226")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")           # P1 owns + controls host
        _attach_bounty_upgrade(state, host, offer, "P0")     # P0 collects
        ps0, ps1 = state.player_by_id("P0"), state.player_by_id("P1")

        _defeat_unit(state, ps1, host)

        assert not state.pending_decisions                   # inline, no player choice
        # Relocated into the collector's arena, ready, and never sent to discard.
        _, now = state.find_instance(host.instance_id)
        assert now in ps0.ground_arena
        assert host.instance_id not in {c.instance_id for c in ps1.discard}
        assert now.exhausted is False                        # "enters play ready"
        assert now.defeat_at_regroup is True
        assert now.owner_id == "P1"                           # owner unchanged

    def test_SHD_226_replayed_unit_defeated_at_regroup_to_owner_discard(self, repo):
        from swu.engine.actions import _defeat_unit, _enter_regroup
        unit = _get_card(repo, "SOR", "46")
        offer = _get_card(repo, "SHD", "226")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        _attach_bounty_upgrade(state, host, offer, "P0")
        ps0, ps1 = state.player_by_id("P0"), state.player_by_id("P1")

        _defeat_unit(state, ps1, host)
        assert state.find_instance(host.instance_id)[1] in ps0.ground_arena

        _enter_regroup(state)

        # The regroup sweep defeats it; a defeated card goes to its OWNER's (P1's)
        # discard, not the collector's.
        assert host.instance_id not in {c.instance_id for c in ps0.ground_arena}
        assert host.instance_id in {c.instance_id for c in ps1.discard}

    def test_SHD_226_no_bounty_without_the_upgrade(self, repo):
        from swu.engine.actions import _defeat_unit
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P1", unit, "ground")
        ps0, ps1 = state.player_by_id("P0"), state.player_by_id("P1")
        _defeat_unit(state, ps1, host)
        # Plain defeat: to the owner's discard, nothing relocated to P0.
        assert host.instance_id in {c.instance_id for c in ps1.discard}
        assert host.instance_id not in {c.instance_id for c in ps0.ground_arena}


class TestChainCodeCollector:
    """SHD_216 — On Attack: if the defender has a Bounty, it gets −4/−0 for this
    attack."""

    def test_minus_four_when_defender_has_printed_bounty(self, repo):
        from swu.engine.actions import compute_power
        chain = _get_card(repo, "SHD", "216")
        headhunter = _get_card(repo, "SHD", "165")  # printed Bounty keyword
        state = _make_state()
        atk = _place(state, "P0", chain, "ground")
        deff = _place(state, "P1", headhunter, "space")
        base = compute_power(state, deff)
        state = _fire_on_attack(state, atk, deff)
        assert not state.pending_decisions               # resolves inline
        _, now = state.find_instance(deff.instance_id)
        assert compute_power(state, now) == max(0, base - 4)

    def test_minus_four_when_defender_wears_bounty_upgrade(self, repo):
        from swu.engine.actions import compute_power
        chain = _get_card(repo, "SHD", "216")
        unit = _get_card(repo, "SOR", "46")
        public_enemy = _get_card(repo, "SHD", "68")
        state = _make_state()
        atk = _place(state, "P0", chain, "ground")
        deff = _place(state, "P1", unit, "ground")
        _attach_bounty_upgrade(state, deff, public_enemy, "P0")
        base = compute_power(state, deff)
        state = _fire_on_attack(state, atk, deff)
        _, now = state.find_instance(deff.instance_id)
        assert compute_power(state, now) == max(0, base - 4)

    def test_no_debuff_when_defender_has_no_bounty(self, repo):
        from swu.engine.actions import compute_power
        chain = _get_card(repo, "SHD", "216")
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        atk = _place(state, "P0", chain, "ground")
        deff = _place(state, "P1", unit, "ground")
        base = compute_power(state, deff)
        state = _fire_on_attack(state, atk, deff)
        _, now = state.find_instance(deff.instance_id)
        assert compute_power(state, now) == base


# ── Bounty keyword group (moff-gideon:01) ─────────────────────────────────────
# Top Target SHD_71 (heal collector's base, 6 if dying unit unique else 4),
# Price on Your Head SHD_125 (collector puts deck-top into play as a resource),
# and The Client SHD_31 (grants a chosen unit a phase-scoped "heal 5 from base"
# bounty via the new CardInstance.granted_bounties field, resolved inline at
# defeat for the collector).

class TestTopTarget:
    """SHD_71 — GrantedAbility(WhenDefeated): collector heals their base by 4
    (6 if the dying unit is unique)."""

    def test_shd71_heals_collector_base_four_for_nonunique_host(self, repo):
        from swu.engine.actions import _defeat_unit
        host_def = _get_card(repo, "SOR", "46")     # Consular Security Force (not unique)
        top_target = _get_card(repo, "SHD", "71")
        assert host_def.is_unique is False
        state = _make_state()
        host = _place(state, "P1", host_def, "ground")   # P1 controls → P0 collects
        _attach_bounty_upgrade(state, host, top_target, "P0")
        p0_base = state.player_by_id("P0").base_instance
        p0_base.damage = 10

        _defeat_unit(state, state.player_by_id("P1"), host)

        assert not state.pending_decisions               # deterministic, inline
        assert p0_base.damage == 6                        # healed 4

    def test_shd71_heals_six_when_host_unique(self, repo):
        from swu.engine.actions import _defeat_unit
        unique_host = _get_card(repo, "SHD", "31")  # The Client is unique
        top_target = _get_card(repo, "SHD", "71")
        assert unique_host.is_unique is True
        state = _make_state()
        host = _place(state, "P1", unique_host, "ground")
        _attach_bounty_upgrade(state, host, top_target, "P0")
        p0_base = state.player_by_id("P0").base_instance
        p0_base.damage = 10

        _defeat_unit(state, state.player_by_id("P1"), host)
        assert p0_base.damage == 4                         # healed 6


class TestPriceOnYourHead:
    """SHD_125 — GrantedAbility(WhenDefeated): the collector puts the top card of
    their own deck into play as a ready resource."""

    def test_shd125_collector_resources_deck_top(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.state import CardInstance, Zone
        host_def = _get_card(repo, "SOR", "46")
        price = _get_card(repo, "SHD", "125")
        state = _make_state()
        host = _place(state, "P1", host_def, "ground")     # P0 collects
        _attach_bounty_upgrade(state, host, price, "P0")
        ps0 = state.player_by_id("P0")
        top_card = CardInstance(instance_id="deck_top", card_def=host_def,
                                owner_id="P0", zone=Zone.DECK)
        ps0.deck.append(top_card)
        resources_before = len(ps0.resources)

        _defeat_unit(state, state.player_by_id("P1"), host)

        assert not state.pending_decisions
        assert len(ps0.resources) == resources_before + 1
        assert top_card in ps0.resources
        assert top_card.zone == Zone.RESOURCES
        assert top_card.face_down and not top_card.exhausted
        assert top_card not in ps0.deck

    def test_shd125_no_op_with_empty_deck(self, repo):
        from swu.engine.actions import _defeat_unit
        host_def = _get_card(repo, "SOR", "46")
        price = _get_card(repo, "SHD", "125")
        state = _make_state()
        host = _place(state, "P1", host_def, "ground")
        _attach_bounty_upgrade(state, host, price, "P0")
        ps0 = state.player_by_id("P0")
        assert not ps0.deck

        _defeat_unit(state, state.player_by_id("P1"), host)
        assert len(ps0.resources) == 0                     # nothing to put down


class TestTheClient:
    """SHD_31 — Action [Exhaust]: Choose a unit. For this phase it gains a Bounty
    that heals 5 from a base when it is defeated (collector = its opponent)."""

    def test_shd31_grants_phase_bounty_and_collector_heals_on_defeat(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget, _defeat_unit)
        client = _get_card(repo, "SHD", "31")
        enemy_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        client_ci = _place(state, "P0", client, "ground")
        enemy = _place(state, "P1", enemy_def, "ground")   # target an enemy unit

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == client_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        _, enemy_after = state.find_instance(enemy.instance_id)
        assert "heal_base:5" in enemy_after.granted_bounties
        _, client_after = state.find_instance(client_ci.instance_id)
        assert client_after.exhausted                      # paid ExhaustSelf

        # When the bountied enemy unit is defeated, P0 (its opponent) heals 5.
        p0_base = state.player_by_id("P0").base_instance
        p0_base.damage = 9
        _defeat_unit(state, state.player_by_id("P1"), enemy_after)
        assert p0_base.damage == 4

    def test_shd31_granted_bounty_clears_at_round_rollover(self, repo):
        """The "for this phase" grant must not linger forever."""
        from swu.engine.actions import _end_regroup
        client = _get_card(repo, "SHD", "31")
        enemy_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        _place(state, "P0", client, "ground")
        enemy = _place(state, "P1", enemy_def, "ground")
        enemy.granted_bounties.append("heal_base:5")

        _end_regroup(state)
        _, enemy_after = state.find_instance(enemy.instance_id)
        assert enemy_after.granted_bounties == []

    def test_shd31_no_collect_when_unbountied_unit_defeated(self, repo):
        from swu.engine.actions import _defeat_unit
        enemy_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        enemy = _place(state, "P1", enemy_def, "ground")
        p0_base = state.player_by_id("P0").base_instance
        p0_base.damage = 9
        _defeat_unit(state, state.player_by_id("P1"), enemy)
        assert p0_base.damage == 9                          # no bounty → no heal


# ── Direct damage & removal (the-mandalorian:02) ──────────────────────────────

def _put_in_discard(state, owner_id, card_def):
    """Append a CardInstance of card_def into owner's discard pile."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    ci = CardInstance(
        instance_id=f"{owner_id}_disc_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD,
    )
    state.player_by_id(owner_id).discard.append(ci)
    return ci


def _deploy_leader_as_unit(state, owner_id, leader_def, arena="ground"):
    """Place a deployed leader directly into an arena as a unit instance."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    zone = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
    ci = CardInstance(
        instance_id=f"{owner_id}_ldr_{uuid.uuid4().hex[:6]}",
        card_def=leader_def, owner_id=owner_id, zone=zone,
    )
    ci.deployed = True
    ci.exhausted = False
    state.player_by_id(owner_id).ground_arena.append(ci) if arena == "ground" \
        else state.player_by_id(owner_id).space_arena.append(ci)
    return ci


class TestFellTheDragon:
    """SHD_78 — Event: Defeat a non-leader unit with 5 or more power."""

    def test_defeats_only_high_power_non_leader(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        fell = _get_card(repo, "SHD", "78")          # Event, cost 4 Aggression
        strong = _get_card(repo, "SOR", "116")       # Steadfast Battalion, power 5
        weak = _get_card(repo, "SOR", "46")          # Consular Security Force, power 3
        vader = _get_card(repo, "SOR", "10")         # Leader, power 5 when deployed
        state = _make_state()
        strong_ci = _place(state, "P1", strong, "ground")
        weak_ci = _place(state, "P1", weak, "ground")
        leader_ci = _deploy_leader_as_unit(state, "P1", vader, "ground")
        fell_ci = CardInstance(
            instance_id=f"fell_{uuid.uuid4().hex[:6]}", card_def=fell,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(fell_ci)
        _give_resources(state, "P0", 6, repo)  # cost 4 + 2 off-aspect = 6

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == fell_ci.instance_id)
        state = apply(state, play)

        # Only the power-5 non-leader is a legal target: not the power-3 unit,
        # not the (also power-5) leader.
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert strong_ci.instance_id in targets
        assert weak_ci.instance_id not in targets
        assert leader_ci.instance_id not in targets

        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == strong_ci.instance_id)
        state = apply(state, choose)
        assert _find_instance(state, strong_ci.instance_id) is None  # defeated
        assert _find_instance(state, weak_ci.instance_id) is not None

    def test_fizzles_with_no_eligible_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        fell = _get_card(repo, "SHD", "78")
        weak = _get_card(repo, "SOR", "46")  # power 3 — never eligible
        state = _make_state()
        weak_ci = _place(state, "P1", weak, "ground")
        fell_ci = CardInstance(
            instance_id=f"fell_{uuid.uuid4().hex[:6]}", card_def=fell,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(fell_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == fell_ci.instance_id)
        state = apply(state, play)
        # No legal target → the event fizzles, no decision pending.
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert _find_instance(state, weak_ci.instance_id) is not None


class TestFennecShand:
    """SHD_220 — On Attack: Deal 1 damage to the defender for each different cost
    among cards in your discard pile."""

    def test_damage_scales_with_distinct_discard_costs(self, repo):
        fennec = _get_card(repo, "SHD", "220")
        defender = _get_card(repo, "SOR", "46")
        c_cost4 = _get_card(repo, "SOR", "46")   # cost 4
        c_cost1a = _get_card(repo, "SOR", "128")  # cost 1
        c_cost1b = _get_card(repo, "SOR", "140")  # cost 1 (duplicate cost)
        state = _make_state()
        atk = _place(state, "P0", fennec, "ground")
        deff = _place(state, "P1", defender, "ground")
        # Discard costs {4, 1, 1} → 2 distinct costs → 2 damage.
        _put_in_discard(state, "P0", c_cost4)
        _put_in_discard(state, "P0", c_cost1a)
        _put_in_discard(state, "P0", c_cost1b)

        state = _fire_on_attack(state, atk, deff)
        assert not state.pending_decisions          # resolves inline (fixed target)
        _, hit = state.find_instance(deff.instance_id)
        assert hit.damage == 2

    def test_empty_discard_deals_no_damage(self, repo):
        fennec = _get_card(repo, "SHD", "220")
        defender = _get_card(repo, "SOR", "46")
        state = _make_state()
        atk = _place(state, "P0", fennec, "ground")
        deff = _place(state, "P1", defender, "ground")
        state = _fire_on_attack(state, atk, deff)
        _, hit = state.find_instance(deff.instance_id)
        assert hit.damage == 0

    def test_no_defender_unit_when_attacking_base(self, repo):
        """Attacking a base (no defender unit) deals no damage — "if it's a unit"
        falls out of the fixed DEFENDER target resolving to nothing."""
        fennec = _get_card(repo, "SHD", "220")
        cost4 = _get_card(repo, "SOR", "46")
        state = _make_state()
        atk = _place(state, "P0", fennec, "ground")
        _put_in_discard(state, "P0", cost4)
        base_before = state.player_by_id("P1").base_instance.damage
        state = _fire_on_attack(state, atk, defender_ci=None)  # base attack
        assert not state.pending_decisions
        assert state.player_by_id("P1").base_instance.damage == base_before


# ── Card advantage & disruption (the-mandalorian:03) ──────────────────────────

def _put_on_deck(state, owner_id, card_defs):
    """Append CardInstances of card_defs onto owner's deck (first = top)."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    ps = state.player_by_id(owner_id)
    out = []
    for cd in card_defs:
        ci = CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
            card_def=cd, owner_id=owner_id, zone=Zone.DECK)
        ps.deck.append(ci)
        out.append(ci)
    return out


def _base_with_aspect(state, owner_id, aspect_name):
    """Replace owner's base with a Base carrying a single named aspect pip."""
    from swu.cards.models import Base, AspectPip
    from swu.engine.state import CardInstance, Zone
    import uuid
    bdef = Base(
        id=88888, card_uid=None, set_code="TST", set_name="T", card_number="B",
        name=f"Base {aspect_name}", subtitle=None, type="Base", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None,
        aspects=(AspectPip(position=0, name=aspect_name, color="x", is_duplicate=False),),
        keywords=(), traits=(), arenas=(), image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None, hp=30, epic_action=None)
    ps = state.player_by_id(owner_id)
    ps.base_zone = [ci for ci in ps.base_zone
                    if not ci.card_def.type == "Base"]
    ps.base_zone.append(CardInstance(
        instance_id=f"{owner_id}_base_{uuid.uuid4().hex[:4]}",
        card_def=bdef, owner_id=owner_id, zone=Zone.BASE_ZONE))


class TestGreefKarga:
    """SHD_245 — When Played: Search the top 5 for an upgrade, draw it (mandatory
    if able); bottom the rest in a random order."""

    def test_searches_and_draws_the_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply
        greef = _get_card(repo, "SHD", "245")
        upgrade = _get_card(repo, "SOR", "53")     # Luke's Lightsaber (Upgrade)
        filler = _get_card(repo, "SOR", "46")      # Consular Security Force (Unit)
        state = _make_state()
        greef_ci = _place(state, "P0", greef, "ground")
        _put_on_deck(state, "P0", [filler, filler, upgrade, filler, filler])

        state = _fire_when_played(state, greef_ci)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        # Mandatory-if-able: only the upgrade is a candidate, and no early finish
        # is offered while it remains (up_to=False).
        assert [type(a).__name__ for a in acts] == ["SelectSearchCard"]
        state = apply(state, acts[0])
        assert not state.pending_decisions
        hand = state.player_by_id("P0").hand
        assert any(ci.card_def.name == upgrade.name for ci in hand)

    def test_no_upgrade_in_window_draws_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishSearch
        greef = _get_card(repo, "SHD", "245")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        greef_ci = _place(state, "P0", greef, "ground")
        _put_on_deck(state, "P0", [filler, filler, filler])
        hand_before = len(state.player_by_id("P0").hand)

        state = _fire_when_played(state, greef_ci)
        # No eligible card → only a forced FinishSearch (the rest must still be
        # bottomed in random order).
        acts = legal_actions(state)
        assert [type(a).__name__ for a in acts] == ["FinishSearch"]
        state = apply(state, FinishSearch())
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == hand_before


class TestThisIsTheWay:
    """SHD_253 — Event: Search the top 8 for up to 2 Mandalorian and/or upgrade
    cards, draw them; bottom the rest in a random order."""

    def test_takes_up_to_two_eligible(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, SelectSearchCard, FinishSearch
        from swu.engine.state import CardInstance, Zone
        import uuid
        titw = _get_card(repo, "SHD", "253")       # Event, cost 2 Heroism
        mando = _get_card(repo, "SHD", "44")        # Razor Crest (Mandalorian unit)
        upgrade = _get_card(repo, "SHD", "73")      # Mandalorian Armor (Upgrade)
        filler = _get_card(repo, "SOR", "46")       # Rebel unit — neither eligible
        state = _make_state()
        titw_ci = CardInstance(
            instance_id=f"titw_{uuid.uuid4().hex[:6]}", card_def=titw,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(titw_ci)
        _put_on_deck(state, "P0", [mando, upgrade] + [filler] * 6)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == titw_ci.instance_id)
        state = apply(state, play)
        assert state.pending_decisions[-1].kind == "deck_search"
        # "up to" → a FinishSearch is always available; two eligible candidates.
        acts = legal_actions(state)
        assert any(isinstance(a, FinishSearch) for a in acts)
        sels = [a for a in acts if isinstance(a, SelectSearchCard)]
        assert len(sels) == 2
        state = apply(state, sels[0])
        state = apply(state, [a for a in legal_actions(state)
                              if isinstance(a, SelectSearchCard)][0])
        # Cap reached → auto-finished.
        assert not state.pending_decisions
        names = {ci.card_def.name for ci in state.player_by_id("P0").hand}
        assert mando.name in names and upgrade.name in names


class TestKuiil:
    """SHD_41 — On Attack: Discard the top card of your deck; if it shares an
    aspect with your base, return it to your hand."""

    def test_matching_aspect_returns_to_hand(self, repo):
        kuiil = _get_card(repo, "SHD", "41")
        match = _get_card(repo, "SOR", "46")   # Heroism, Vigilance
        state = _make_state()
        _base_with_aspect(state, "P0", "Heroism")
        atk = _place(state, "P0", kuiil, "ground")
        deck_ci = _put_on_deck(state, "P0", [match])[0]

        state = _fire_on_attack(state, atk, defender_ci=None)
        assert not state.pending_decisions          # inline, no decision
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == deck_ci.instance_id for ci in ps.hand)
        assert all(ci.instance_id != deck_ci.instance_id for ci in ps.discard)
        assert all(ci.instance_id != deck_ci.instance_id for ci in ps.deck)

    def test_non_matching_aspect_stays_in_discard(self, repo):
        kuiil = _get_card(repo, "SHD", "41")
        nonmatch = _get_card(repo, "SHD", "159")   # Aggression only
        state = _make_state()
        _base_with_aspect(state, "P0", "Heroism")
        atk = _place(state, "P0", kuiil, "ground")
        deck_ci = _put_on_deck(state, "P0", [nonmatch])[0]

        state = _fire_on_attack(state, atk, defender_ci=None)
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == deck_ci.instance_id for ci in ps.discard)
        assert all(ci.instance_id != deck_ci.instance_id for ci in ps.hand)

    def test_empty_deck_is_noop(self, repo):
        kuiil = _get_card(repo, "SHD", "41")
        state = _make_state()
        _base_with_aspect(state, "P0", "Heroism")
        atk = _place(state, "P0", kuiil, "ground")
        state = _fire_on_attack(state, atk, defender_ci=None)
        ps = state.player_by_id("P0")
        assert not ps.hand and not ps.discard


class TestRazorCrest:
    """SHD_44 — When Played: You may return an upgrade from your discard pile to
    your hand (the new return_from_discard decision kind)."""

    def test_returns_chosen_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard, FinishReturnFromDiscard
        crest = _get_card(repo, "SHD", "44")
        upgrade = _get_card(repo, "SOR", "53")   # Luke's Lightsaber (Upgrade)
        non_upgrade = _get_card(repo, "SOR", "46")
        state = _make_state()
        crest_ci = _place(state, "P0", crest, "space")
        up_ci = _put_in_discard(state, "P0", upgrade)
        _put_in_discard(state, "P0", non_upgrade)

        state = _fire_when_played(state, crest_ci)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        acts = legal_actions(state)
        sels = [a for a in acts if isinstance(a, SelectDiscardCard)]
        # Only the upgrade is an eligible candidate; a Finish is always offered.
        assert [a.instance_id for a in sels] == [up_ci.instance_id]
        assert any(isinstance(a, FinishReturnFromDiscard) for a in acts)
        state = apply(state, sels[0])
        # count=1 → auto-finishes after one pick.
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == up_ci.instance_id for ci in ps.hand)
        assert all(ci.instance_id != up_ci.instance_id for ci in ps.discard)

    def test_no_upgrade_in_discard_no_decision(self, repo):
        crest = _get_card(repo, "SHD", "44")
        non_upgrade = _get_card(repo, "SOR", "46")
        state = _make_state()
        crest_ci = _place(state, "P0", crest, "space")
        _put_in_discard(state, "P0", non_upgrade)
        state = _fire_when_played(state, crest_ci)
        # No eligible upgrade → effect fizzles, no decision pushed.
        assert not state.pending_decisions

    def test_may_decline(self, repo):
        from swu.engine.actions import apply, FinishReturnFromDiscard
        crest = _get_card(repo, "SHD", "44")
        upgrade = _get_card(repo, "SOR", "53")
        state = _make_state()
        crest_ci = _place(state, "P0", crest, "space")
        up_ci = _put_in_discard(state, "P0", upgrade)
        state = _fire_when_played(state, crest_ci)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        state = apply(state, FinishReturnFromDiscard())
        # Declined: the upgrade stays in the discard pile.
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == up_ci.instance_id for ci in ps.discard)
        assert all(ci.instance_id != up_ci.instance_id for ci in ps.hand)


class TestSpareTheTarget:
    """SHD_206 — Event: Return an enemy non-leader unit to its owner's hand.
    (The "Collect that unit's Bounties" rider is a documented deferred residual.)"""

    def test_returns_enemy_unit_to_owner_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        import uuid
        spare = _get_card(repo, "SHD", "206")     # Event, cost 3 Cunning/Heroism
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        enemy_ci = _place(state, "P1", enemy, "ground")
        spare_ci = CardInstance(
            instance_id=f"spare_{uuid.uuid4().hex[:6]}", card_def=spare,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(spare_ci)
        _give_resources(state, "P0", 9, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == spare_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        # The enemy unit left the arena and is in its owner's (P1) hand.
        assert _find_instance(state, enemy_ci.instance_id) is None
        assert any(ci.instance_id == enemy_ci.instance_id
                   for ci in state.player_by_id("P1").hand)

    def test_only_enemy_non_leader_targetable(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        import uuid
        spare = _get_card(repo, "SHD", "206")
        enemy_unit = _get_card(repo, "SOR", "46")
        friendly_unit = _get_card(repo, "SOR", "46")
        enemy_leader = _get_card(repo, "SOR", "10")   # Darth Vader leader
        state = _make_state()
        enemy_ci = _place(state, "P1", enemy_unit, "ground")
        _place(state, "P0", friendly_unit, "ground")
        leader_ci = _deploy_leader_as_unit(state, "P1", enemy_leader, "ground")
        spare_ci = CardInstance(
            instance_id=f"spare_{uuid.uuid4().hex[:6]}", card_def=spare,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(spare_ci)
        _give_resources(state, "P0", 9, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == spare_ci.instance_id)
        state = apply(state, play)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert targets == {enemy_ci.instance_id}


# ── Combat tricks, buffs & tempo (the-mandalorian:04) ─────────────────────────


def _fire_card_played(state, player_id, played_ci):
    """Fire a CardPlayed event for ``played_ci`` (must already be in a zone so
    find_instance can resolve its card type), mirroring the PlayCard hook that
    drives WhenYouPlayCard observers."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(
        player_id=player_id, instance_id=played_ci.instance_id,
        card_name=played_ci.card_def.display_name, cost_paid=0,
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _attach_upgrade_directly(state, host_ci, upgrade_def, owner_id):
    """Attach an upgrade instance to host_ci (no triggers). Returns the upgrade."""
    from swu.engine.state import CardInstance
    import uuid
    up = CardInstance(
        instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade_def,
        owner_id=owner_id, zone=host_ci.zone)
    host_ci.attached_upgrades.append(up)
    return up


class TestTheMandalorian:
    """SHD_18 — Leader. "When you play an upgrade" exhausts an enemy unit."""

    def test_undeployed_exhausts_enemy_and_leader(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        mando = _get_card(repo, "SHD", "18")
        host = _get_card(repo, "SOR", "46")           # friendly host for the upgrade
        upgrade = _get_card(repo, "SHD", "74")        # Vambrace (an upgrade)
        small_enemy = _get_card(repo, "SHD", "40")    # 1/2 -> 2 remaining HP (<=4)
        state = _make_state()
        leader_ci = _place_leader(state, "P0", mando)
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")
        enemy_ci = _place(state, "P1", small_enemy, "ground")

        state = _fire_card_played(state, "P0", up)
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger)
                      and a.source_id == leader_ci.instance_id)
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        _, enemy = state.find_instance(enemy_ci.instance_id)
        _, leader = state.find_instance(leader_ci.instance_id)
        assert enemy.exhausted is True
        assert leader.exhausted is True   # the self-exhaust cost was paid

    def test_undeployed_not_offered_when_leader_exhausted(self, repo):
        """SOURCE_READY gate - an already-exhausted leader cannot pay the cost."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        mando = _get_card(repo, "SHD", "18")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SHD", "74")
        small_enemy = _get_card(repo, "SHD", "40")
        state = _make_state()
        leader_ci = _place_leader(state, "P0", mando)
        leader_ci.exhausted = True
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")
        _place(state, "P1", small_enemy, "ground")

        state = _fire_card_played(state, "P0", up)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_undeployed_only_targets_low_hp_enemy(self, repo):
        """Only enemy units with <=4 remaining HP are eligible targets."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        mando = _get_card(repo, "SHD", "18")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SHD", "74")
        small_enemy = _get_card(repo, "SHD", "40")    # 1/2 -> 2 remaining (<=4)
        big_enemy = _get_card(repo, "SOR", "116")     # high-HP unit (>4 remaining)
        state = _make_state()
        _place_leader(state, "P0", mando)
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")
        small_ci = _place(state, "P1", small_enemy, "ground")
        big_ci = _place(state, "P1", big_enemy, "ground")

        state = _fire_card_played(state, "P0", up)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert small_ci.instance_id in targets
        assert big_ci.instance_id not in targets

    def test_deployed_exhausts_enemy_no_self_exhaust(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_hp)
        mando = _get_card(repo, "SHD", "18")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SHD", "74")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        leader_ci = _deploy_leader_as_unit(state, "P0", mando, "ground")
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.damage = max(0, compute_hp(state, enemy_ci) - 6)  # remaining <= 6

        state = _fire_card_played(state, "P0", up)
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger)
                      and a.source_id == leader_ci.instance_id)
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        _, hit = state.find_instance(enemy_ci.instance_id)
        _, leader = state.find_instance(leader_ci.instance_id)
        assert hit.exhausted is True
        assert leader.exhausted is False   # deployed side has no self-exhaust cost

    def test_deployed_not_offered_with_no_eligible_enemy(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        mando = _get_card(repo, "SHD", "18")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SHD", "74")
        state = _make_state()
        _deploy_leader_as_unit(state, "P0", mando, "ground")
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")
        # no enemy unit at all -> nothing with <=6 HP to exhaust

        state = _fire_card_played(state, "P0", up)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestClanWrenRescuer:
    def test_when_played_gives_experience(self, repo):
        """SHD_40 When Played: Give an Experience token to a unit."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        rescuer = _get_card(repo, "SHD", "40")
        ally = _get_card(repo, "SOR", "46")
        state = _make_state()
        rescuer_ci = _place(state, "P0", rescuer, "ground")
        ally_ci = _place(state, "P0", ally, "ground")
        state = _fire_when_played(state, rescuer_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == ally_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(ally_ci.instance_id)
        assert _experience_count(hit) == 1


class TestTheArmorer:
    def test_shields_up_to_three_mandalorians(self, repo):
        """SHD_47 When Played: Give a Shield token to each of up to 3 Mandalorian
        units (the Armorer itself is a Mandalorian)."""
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken)
        armorer = _get_card(repo, "SHD", "47")
        mando_b = _get_card(repo, "SHD", "40")    # Clan Wren Rescuer (Mandalorian)
        non_mando = _get_card(repo, "SOR", "46")  # not a Mandalorian
        state = _make_state()
        armorer_ci = _place(state, "P0", armorer, "ground")
        b_ci = _place(state, "P0", mando_b, "ground")
        nm_ci = _place(state, "P0", non_mando, "ground")

        state = _fire_when_played(state, armorer_ci)
        eligible = {a.target_id for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)}
        assert b_ci.instance_id in eligible
        assert armorer_ci.instance_id in eligible
        assert nm_ci.instance_id not in eligible

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == b_ci.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == armorer_ci.instance_id))
        if any(isinstance(a, FinishSelectToken) for a in legal_actions(state)):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, FinishSelectToken)))
        _, b = state.find_instance(b_ci.instance_id)
        _, arm = state.find_instance(armorer_ci.instance_id)
        assert _shield_count(b) == 1
        assert _shield_count(arm) == 1


class TestFollowerOfTheWay:
    def test_buff_only_while_upgraded(self, repo):
        """SHD_56 While this unit is upgraded, it gets +1/+1."""
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine import tokens
        follower = _get_card(repo, "SHD", "56")   # 1/3
        state = _make_state()
        f_ci = _place(state, "P0", follower, "ground")
        ps = state.player_by_id("P0")
        assert compute_power(state, f_ci) == 1
        assert compute_hp(state, f_ci) == 3
        # A Shield token counts as an upgrade (no stat bonus of its own).
        tokens.attach_token(state, ps, f_ci, "Shield")
        assert compute_power(state, f_ci) == 2
        assert compute_hp(state, f_ci) == 4


class TestCargoJuggernaut:
    def test_heals_with_another_vigilance_unit(self, repo):
        """SHD_66 When Played: If you control another Vigilance unit, heal 4 from
        your base."""
        jug = _get_card(repo, "SHD", "66")
        vig = _get_card(repo, "SHD", "56")   # Follower of The Way - Vigilance
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 6
        jug_ci = _place(state, "P0", jug, "ground")
        _place(state, "P0", vig, "ground")
        state = _fire_when_played(state, jug_ci)
        assert state.player_by_id("P0").base_instance.damage == 2

    def test_no_heal_without_another_vigilance_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        jug = _get_card(repo, "SHD", "66")
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 6
        jug_ci = _place(state, "P0", jug, "ground")
        state = _fire_when_played(state, jug_ci)
        assert state.player_by_id("P0").base_instance.damage == 6
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestMandalorianArmor:
    def test_shields_mandalorian_host(self, repo):
        """SHD_73 When Played: If attached unit is a Mandalorian, give it a Shield."""
        armor = _get_card(repo, "SHD", "73")
        mando_host = _get_card(repo, "SHD", "40")   # Clan Wren Rescuer (Mandalorian)
        state = _make_state()
        host_ci = _place(state, "P0", mando_host, "ground")
        up = _attach_upgrade_directly(state, host_ci, armor, "P0")
        state = _fire_upgrade_played(state, up, host_ci)
        _, host = state.find_instance(host_ci.instance_id)
        assert _shield_count(host) == 1

    def test_no_shield_on_non_mandalorian_host(self, repo):
        armor = _get_card(repo, "SHD", "73")
        non_mando = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", non_mando, "ground")
        up = _attach_upgrade_directly(state, host_ci, armor, "P0")
        state = _fire_upgrade_played(state, up, host_ci)
        _, host = state.find_instance(host_ci.instance_id)
        assert _shield_count(host) == 0


class TestVambraceGrappleshot:
    def test_on_attack_exhausts_defender(self, repo):
        """SHD_74 Attached unit gains On Attack: Exhaust the defender."""
        vambrace = _get_card(repo, "SHD", "74")
        host = _get_card(repo, "SOR", "46")
        defender = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        _attach_upgrade_directly(state, host_ci, vambrace, "P0")
        def_ci = _place(state, "P1", defender, "ground")

        state = _fire_on_attack(state, host_ci, def_ci)
        _, d = state.find_instance(def_ci.instance_id)
        assert d.exhausted is True

    def test_no_defender_on_base_attack_is_noop(self, repo):
        vambrace = _get_card(repo, "SHD", "74")
        host = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        _attach_upgrade_directly(state, host_ci, vambrace, "P0")
        state = _fire_on_attack(state, host_ci, None)
        assert not state.pending_decisions


# ── Miscellaneous abilities (the-mandalorian:06) ──────────────────────────────

class TestFoundling:
    """SHD_69 — Foundling (Upgrade): Attached unit gains the Mandalorian trait."""

    def test_shd_69_host_counts_as_mandalorian_for_trait_effects(self, repo):
        """A non-Mandalorian host with Foundling attached becomes a legal target
        of a Mandalorian-only token grant (The Armorer SHD_47, controller='any',
        traits=['Mandalorian']) — observable through legal_actions."""
        from swu.engine.actions import legal_actions
        foundling = _get_card(repo, "SHD", "69")
        armorer = _get_card(repo, "SHD", "47")
        non_mando = _get_card(repo, "SOR", "46")  # Rebel/Trooper, not Mandalorian
        state = _make_state()
        host_ci = _place(state, "P0", non_mando, "ground")
        _attach_upgrade_directly(state, host_ci, foundling, "P0")
        armorer_ci = _place(state, "P0", armorer, "ground")

        state = _fire_when_played(state, armorer_ci)
        target_ids = {a.target_id for a in legal_actions(state)
                      if type(a).__name__ == "SelectTokenTarget"}
        assert host_ci.instance_id in target_ids

    def test_shd_69_without_foundling_host_is_not_mandalorian(self, repo):
        """Control: the same non-Mandalorian host is NOT a Mandalorian-token
        target when no Foundling is attached."""
        from swu.engine.actions import legal_actions
        armorer = _get_card(repo, "SHD", "47")
        non_mando = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", non_mando, "ground")
        armorer_ci = _place(state, "P0", armorer, "ground")

        state = _fire_when_played(state, armorer_ci)
        target_ids = {a.target_id for a in legal_actions(state)
                      if type(a).__name__ == "SelectTokenTarget"}
        assert host_ci.instance_id not in target_ids


class TestSurvivorsGauntlet:
    """SHD_64 — When Played/On Attack: You may attach an upgrade on a unit to
    another eligible unit controlled by the same player."""

    def test_shd_64_when_played_moves_upgrade_to_other_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply
        gauntlet = _get_card(repo, "SHD", "64")
        foundling = _get_card(repo, "SHD", "69")   # upgrade with no attach restriction
        unit_a = _get_card(repo, "SOR", "46")
        unit_b = _get_card(repo, "SOR", "46")
        state = _make_state()
        g_ci = _place(state, "P0", gauntlet, "ground")
        a_ci = _place(state, "P0", unit_a, "ground")
        b_ci = _place(state, "P0", unit_b, "ground")
        up = _attach_upgrade_directly(state, a_ci, foundling, "P0")

        state = _fire_when_played(state, g_ci)
        assert state.pending_decisions
        top = state.pending_decisions[-1]
        assert top.kind == "move_upgrade"

        # pick_upgrade stage: select the upgrade to move
        select = next(a for a in legal_actions(state)
                      if type(a).__name__ == "MoveUpgradeSelect"
                      and a.upgrade_id == up.instance_id)
        state = apply(state, select)

        # pick_dest stage: B is a legal destination (A is the current host)
        to_b = next(a for a in legal_actions(state)
                    if type(a).__name__ == "MoveUpgradeTo"
                    and a.dest_id == b_ci.instance_id)
        state = apply(state, to_b)

        assert not state.pending_decisions
        _, a_now = state.find_instance(a_ci.instance_id)
        _, b_now = state.find_instance(b_ci.instance_id)
        assert all(u.instance_id != up.instance_id for u in a_now.attached_upgrades)
        assert any(u.instance_id == up.instance_id for u in b_now.attached_upgrades)

    def test_shd_64_decline_leaves_upgrade_in_place(self, repo):
        from swu.engine.actions import legal_actions, apply
        gauntlet = _get_card(repo, "SHD", "64")
        foundling = _get_card(repo, "SHD", "69")
        unit_a = _get_card(repo, "SOR", "46")
        unit_b = _get_card(repo, "SOR", "46")
        state = _make_state()
        g_ci = _place(state, "P0", gauntlet, "ground")
        a_ci = _place(state, "P0", unit_a, "ground")
        _place(state, "P0", unit_b, "ground")
        up = _attach_upgrade_directly(state, a_ci, foundling, "P0")

        state = _fire_on_attack(state, g_ci, None)
        assert state.pending_decisions[-1].kind == "move_upgrade"
        decline = next(a for a in legal_actions(state)
                       if type(a).__name__ == "DeclineMoveUpgrade")
        state = apply(state, decline)
        assert not state.pending_decisions
        _, a_now = state.find_instance(a_ci.instance_id)
        assert any(u.instance_id == up.instance_id for u in a_now.attached_upgrades)

    def test_shd_64_no_same_controller_destination_no_decision(self, repo):
        """An upgrade on an enemy's only unit cannot be moved (no same-controller
        alternative), so no move_upgrade decision is pushed — a clean no-op."""
        gauntlet = _get_card(repo, "SHD", "64")
        foundling = _get_card(repo, "SHD", "69")
        enemy_unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        g_ci = _place(state, "P0", gauntlet, "ground")
        enemy_ci = _place(state, "P1", enemy_unit, "ground")  # P1's only unit
        _attach_upgrade_directly(state, enemy_ci, foundling, "P1")

        state = _fire_when_played(state, g_ci)
        assert not state.pending_decisions


# ── New primitive: capture (the-mandalorian:07) ───────────────────────────────

def _place_deployed_leader(state, owner_id, leader_def):
    """Place a leader as a deployed unit in the owner's ground arena (ready)."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    ci = CardInstance(
        instance_id=f"{owner_id}_dep_{uuid.uuid4().hex[:6]}",
        card_def=leader_def, owner_id=owner_id, zone=Zone.GROUND_ARENA,
    )
    ci.deployed = True
    ci.exhausted = False
    state.player_by_id(owner_id).ground_arena.append(ci)
    return ci


class TestTheMandaloriansRifle:
    """SHD_251 — Upgrade.  When Played: If attached unit is The Mandalorian, he
    captures an exhausted enemy non-leader unit (facedown under him until he
    leaves play)."""

    def test_shd_251_mandalorian_captures_exhausted_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.state import Zone
        rifle = _get_card(repo, "SHD", "251")
        mando = _get_card(repo, "SHD", "18")          # leader "The Mandalorian"
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        mando_ci = _place_deployed_leader(state, "P0", mando)
        up = _attach_upgrade_directly(state, mando_ci, rifle, "P0")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.exhausted = True

        state = _fire_upgrade_played(state, up, mando_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        # The enemy unit has left P1's arena and sits facedown in P0's capture pile.
        assert all(c.instance_id != enemy_ci.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        cap = state.player_by_id("P0").capture_pile
        assert len(cap) == 1
        captured = cap[0]
        assert captured.instance_id == enemy_ci.instance_id
        assert captured.owner_id == "P1"           # owner unchanged
        assert captured.captured_by == mando_ci.instance_id
        assert captured.zone == Zone.CAPTURE_PILE
        assert captured.face_down is True

    def test_shd_251_captured_unit_returns_when_captor_leaves_play(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, _defeat_unit
        rifle = _get_card(repo, "SHD", "251")
        mando = _get_card(repo, "SHD", "18")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        mando_ci = _place_deployed_leader(state, "P0", mando)
        up = _attach_upgrade_directly(state, mando_ci, rifle, "P0")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.exhausted = True

        state = _fire_upgrade_played(state, up, mando_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        assert len(state.player_by_id("P0").capture_pile) == 1

        # The captor leaves play — the captured card returns to its owner's arena.
        _defeat_unit(state, state.player_by_id("P0"), mando_ci)
        assert state.player_by_id("P0").capture_pile == []
        p1_arena = state.player_by_id("P1").ground_arena
        returned = next(c for c in p1_arena if c.instance_id == enemy_ci.instance_id)
        assert returned.captured_by is None
        assert returned.face_down is False
        assert returned.exhausted is False         # returns ready (documented assumption)

    def test_shd_251_no_capture_when_host_is_not_the_mandalorian(self, repo):
        """The ATTACHED_HOST_NAMED gate: a non-Mandalorian host never captures."""
        rifle = _get_card(repo, "SHD", "251")
        host = _get_card(repo, "SOR", "46")           # not "The Mandalorian"
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, rifle, "P0")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.exhausted = True

        state = _fire_upgrade_played(state, up, host_ci)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []
        assert any(c.instance_id == enemy_ci.instance_id
                   for c in state.player_by_id("P1").ground_arena)

    def test_shd_251_fizzles_with_no_exhausted_enemy(self, repo):
        """Mandatory-if-able: a ready (un-exhausted) enemy is not a legal target,
        so the capture fizzles with no decision."""
        rifle = _get_card(repo, "SHD", "251")
        mando = _get_card(repo, "SHD", "18")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        mando_ci = _place_deployed_leader(state, "P0", mando)
        up = _attach_upgrade_directly(state, mando_ci, rifle, "P0")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.exhausted = False                    # ready → not capturable

        state = _fire_upgrade_played(state, up, mando_ci)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


# ── New primitive: capture (moff-gideon:07) ───────────────────────────────────

class TestDiscerningVeteran:
    """SHD_120 — Unit. "When Played: This unit captures an enemy non-leader ground
    unit." Captures via its own ability (no upgrade host)."""

    def test_shd_120_captures_enemy_ground_unit_under_itself(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.state import Zone
        veteran = _get_card(repo, "SHD", "120")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        vet_ci = _place(state, "P0", veteran, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_played(state, vet_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        # Enemy left P1's arena and sits facedown in P0's capture pile under the vet.
        assert all(c.instance_id != enemy_ci.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        cap = state.player_by_id("P0").capture_pile
        assert len(cap) == 1
        captured = cap[0]
        assert captured.instance_id == enemy_ci.instance_id
        assert captured.owner_id == "P1"
        assert captured.captured_by == vet_ci.instance_id
        assert captured.zone == Zone.CAPTURE_PILE
        assert captured.face_down is True

    def test_shd_120_does_not_target_leaders_or_space(self, repo):
        """Only enemy non-leader GROUND units are offered."""
        from swu.engine.actions import legal_actions, ChooseTarget
        veteran = _get_card(repo, "SHD", "120")
        ground = _get_card(repo, "SOR", "46")
        space = _get_card(repo, "SOR", "110")   # Frontline Shuttle (Space unit)
        leader = _get_card(repo, "SHD", "18")   # The Mandalorian
        state = _make_state()
        vet_ci = _place(state, "P0", veteran, "ground")
        ground_ci = _place(state, "P1", ground, "ground")
        _place(state, "P1", space, "space")
        _place_deployed_leader(state, "P1", leader)

        state = _fire_when_played(state, vet_ci)
        choices = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert choices == {ground_ci.instance_id}

    def test_shd_120_fizzles_with_no_enemy_ground_unit(self, repo):
        veteran = _get_card(repo, "SHD", "120")
        state = _make_state()
        vet_ci = _place(state, "P0", veteran, "ground")

        state = _fire_when_played(state, vet_ci)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


class TestLegalAuthority:
    """SHD_124 — Upgrade. "When Played: Attached unit captures an enemy non-leader
    unit with less power than it." The captor is the attached host."""

    def test_shd_124_captures_weaker_enemy_under_host(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.state import Zone
        authority = _get_card(repo, "SHD", "124")
        host = _get_card(repo, "SOR", "46")        # power 3 (the attached unit)
        weaker = _get_card(repo, "SOR", "108")     # Vanguard Infantry, power 1
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, authority, "P0")
        weak_ci = _place(state, "P1", weaker, "ground")

        state = _fire_upgrade_played(state, up, host_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == weak_ci.instance_id)
        state = apply(state, choose)

        cap = state.player_by_id("P0").capture_pile
        assert len(cap) == 1
        captured = cap[0]
        assert captured.instance_id == weak_ci.instance_id
        assert captured.captured_by == host_ci.instance_id
        assert captured.zone == Zone.CAPTURE_PILE

    def test_shd_124_does_not_offer_equal_or_higher_power_enemy(self, repo):
        """"less power than it": an enemy with power >= the host's is not a legal
        target."""
        from swu.engine.actions import legal_actions, ChooseTarget
        authority = _get_card(repo, "SHD", "124")
        host = _get_card(repo, "SOR", "46")        # power 3
        equal = _get_card(repo, "SOR", "46")       # power 3 (== host, not capturable)
        weaker = _get_card(repo, "SOR", "108")     # power 1 (capturable)
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, authority, "P0")
        equal_ci = _place(state, "P1", equal, "ground")
        weak_ci = _place(state, "P1", weaker, "ground")

        state = _fire_upgrade_played(state, up, host_ci)
        choices = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert weak_ci.instance_id in choices
        assert equal_ci.instance_id not in choices

    def test_shd_124_fizzles_with_no_weaker_enemy(self, repo):
        authority = _get_card(repo, "SHD", "124")
        host = _get_card(repo, "SOR", "108")       # power 1 host
        enemy = _get_card(repo, "SOR", "46")       # power 3 (>= host) → not capturable
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, authority, "P0")
        _place(state, "P1", enemy, "ground")

        state = _fire_upgrade_played(state, up, host_ci)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


# ── Combat tricks, buffs & tempo (the-mandalorian:05) ─────────────────────────

class TestGrogu:
    """SHD_196 — Unit. "Action [Exhaust]: Exhaust an enemy unit." """

    def test_shd196_exhausts_enemy_at_cost_of_self(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        grogu = _get_card(repo, "SHD", "196")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        grogu_ci = _place(state, "P0", grogu, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        assert not enemy_ci.exhausted

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == grogu_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        _, enemy_after = state.find_instance(enemy_ci.instance_id)
        _, grogu_after = state.find_instance(grogu_ci.instance_id)
        assert enemy_after.exhausted          # the enemy is exhausted
        assert grogu_after.exhausted          # Grogu paid its own exhaustion

    def test_shd196_not_offered_when_grogu_exhausted(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        grogu = _get_card(repo, "SHD", "196")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        grogu_ci = _place(state, "P0", grogu, "ground")
        grogu_ci.exhausted = True             # can't pay ExhaustSelf
        _place(state, "P1", enemy, "ground")
        assert not any(isinstance(a, UseAbility) and a.source_id == grogu_ci.instance_id
                       for a in legal_actions(state))


class TestSnapshotReflexes:
    """SHD_223 — Upgrade. "When Played: You may attack with attached unit." """

    def test_shd223_grants_optional_attack_with_host(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, DeclineGrantedAttack)
        snap = _get_card(repo, "SHD", "223")
        host_def = _get_card(repo, "SOR", "46")        # Consular Security Force, power 3
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")  # ready
        up = _attach_upgrade_directly(state, host, snap, "P0")

        state = _fire_upgrade_played(state, up, host)
        assert state.pending_decisions[-1].kind == "granted_attack"
        # Only the host may attack, plus a decline (the "you may").
        attacker_ids = {a.attacker_id for a in legal_actions(state)
                        if isinstance(a, AttackWithUnit)}
        assert attacker_ids == {host.instance_id}
        assert any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))

        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == host.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Host's power including the upgrade's printed +1 (Snapshot Reflexes is +1/+1).
        assert state.players[1].base_instance.damage - base_before == host_def.power + 1
        assert not state.pending_decisions

    def test_shd223_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        snap = _get_card(repo, "SHD", "223")
        host_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        up = _attach_upgrade_directly(state, host, snap, "P0")

        state = _fire_upgrade_played(state, up, host)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineGrantedAttack))
        base_before = state.players[1].base_instance.damage
        state = apply(state, decline)
        assert state.players[1].base_instance.damage == base_before
        assert not state.pending_decisions

    def test_shd223_exhausted_host_offers_only_decline(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        snap = _get_card(repo, "SHD", "223")
        host_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        host.exhausted = True                          # can only attack if ready
        up = _attach_upgrade_directly(state, host, snap, "P0")

        state = _fire_upgrade_played(state, up, host)
        assert not any(isinstance(a, AttackWithUnit) for a in legal_actions(state))
        assert any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))


class TestMandalorianWarrior:
    """SHD_258 — Unit. "When Played: You may give an Experience token to another
    Mandalorian unit." """

    def test_shd258_gives_experience_to_another_mandalorian(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        warrior = _get_card(repo, "SHD", "258")
        other_mando = _get_card(repo, "SHD", "40")     # Clan Wren Rescuer (Mandalorian)
        state = _make_state()
        warrior_ci = _place(state, "P0", warrior, "ground")
        mando_ci = _place(state, "P0", other_mando, "ground")

        state = _fire_when_played(state, warrior_ci)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        # The Warrior itself is excluded (not_self); only the other Mandalorian.
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert mando_ci.instance_id in targets
        assert warrior_ci.instance_id not in targets
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == mando_ci.instance_id))
        _, hit = state.find_instance(mando_ci.instance_id)
        assert _experience_count(hit) == 1

    def test_shd258_auto_declines_with_no_other_mandalorian(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        warrior = _get_card(repo, "SHD", "258")
        non_mando = _get_card(repo, "SOR", "46")       # not a Mandalorian
        state = _make_state()
        warrior_ci = _place(state, "P0", warrior, "ground")
        _place(state, "P0", non_mando, "ground")

        state = _fire_when_played(state, warrior_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestSurpriseStrike:
    """SHD_231 — Surprise Strike (Event): "Attack with a unit. It gets +3/+0 for
    this attack." Identical to Surprise Strike SOR_220 — reuses the granted_attack
    seam (push_granted_attack(power_bonus=3))."""

    def test_shd231_grants_attack_with_plus_3(self, repo):
        from swu.engine.actions import apply, legal_actions, PlayCard, AttackWithUnit

        ss = _get_card(repo, "SHD", "231")
        attacker_def = _get_card(repo, "SOR", "46")  # Consular Security Force, power 3
        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        ss_ci = _put_in_hand(state, "P0", ss)
        _give_resources(state, "P0", 10, repo)

        enemy_base = state.players[1].base_instance
        base_dmg_before = enemy_base.damage

        # Play the event — pushes a granted_attack decision, not a turn pass.
        state = apply(state, PlayCard(ss_ci.instance_id))
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "granted_attack"

        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id is None)
        state = apply(state, atk)

        # Base took base power (3) + Surprise Strike bonus (3) = 6.
        enemy_base = state.players[1].base_instance
        assert enemy_base.damage - base_dmg_before == attacker_def.power + 3
        # The this-attack modifier must not linger after combat settles.
        assert not state.pending_decisions
        assert all(m.duration != "this_attack" for m in state.modifiers)

    def test_shd231_fizzles_with_no_ready_unit(self, repo):
        """No ready unit to attack with → the mandatory grant fizzles cleanly
        (DeclineGrantedAttack), the event still resolves to discard."""
        from swu.engine.actions import apply, legal_actions, PlayCard, DeclineGrantedAttack

        ss = _get_card(repo, "SHD", "231")
        attacker_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        attacker.exhausted = True  # no ready unit able to attack
        ss_ci = _put_in_hand(state, "P0", ss)
        _give_resources(state, "P0", 10, repo)

        base_before = state.players[1].base_instance.damage
        state = apply(state, PlayCard(ss_ci.instance_id))
        # Only a decline is offered; resolving it leaves the board untouched.
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineGrantedAttack))
        state = apply(state, decline)
        assert not state.pending_decisions
        assert state.players[1].base_instance.damage == base_before


# ── moff-gideon:02 — Direct damage & removal ──────────────────────────────────

class TestDeathTrooper:
    def test_shd_30_deals_2_to_a_friendly_and_2_to_an_enemy(self, repo):
        """SHD_30 When Played: Deal 2 damage to a friendly ground unit and 2 to an
        enemy ground unit (two mandatory targeted DealDamage effects)."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        trooper = _get_card(repo, "SHD", "30")
        friendly = _get_card(repo, "SOR", "46")   # Consular Security Force, 7 hp
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        trooper_ci = _place(state, "P0", trooper, "ground")
        friendly_ci = _place(state, "P0", friendly, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_played(state, trooper_ci)
        # First effect: a friendly ground unit — pick the separate friendly unit.
        choose_f = next(a for a in legal_actions(state)
                        if isinstance(a, ChooseTarget) and a.target_id == friendly_ci.instance_id)
        state = apply(state, choose_f)
        # Second effect: an enemy ground unit.
        choose_e = next(a for a in legal_actions(state)
                        if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose_e)

        _, f_after = state.find_instance(friendly_ci.instance_id)
        _, e_after = state.find_instance(enemy_ci.instance_id)
        assert f_after.damage == 2
        assert e_after.damage == 2

    def test_shd_30_friendly_effect_offers_only_friendly_ground_units(self, repo):
        """The friendly-damage effect must not offer enemy units."""
        from swu.engine.actions import legal_actions, ChooseTarget
        trooper = _get_card(repo, "SHD", "30")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        trooper_ci = _place(state, "P0", trooper, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_played(state, trooper_ci)
        # First (friendly) effect: only Death Trooper itself is a friendly ground unit.
        friendly_choices = {a.target_id for a in legal_actions(state)
                            if isinstance(a, ChooseTarget)}
        assert friendly_choices == {trooper_ci.instance_id}
        assert enemy_ci.instance_id not in friendly_choices


class TestConfiscate:
    def test_shd_262_defeats_an_upgrade(self, repo):
        """SHD_262 (Event): Defeat an upgrade — removes a real upgrade from its host
        and sends it to the owner's discard."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayCard
        import uuid
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SOR", "53")   # Luke's Lightsaber (a real Upgrade)
        confiscate = _get_card(repo, "SHD", "262")
        state = _make_state()
        host_ci = _place(state, "P1", host, "ground")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id="P1", zone=Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(up_ci)
        conf_ci = _put_in_hand(state, "P0", confiscate)
        _give_resources(state, "P0", 5, repo)

        state = apply(state, PlayCard(conf_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == up_ci.instance_id)
        state = apply(state, choose)

        _, host_after = state.find_instance(host_ci.instance_id)
        assert all(u.instance_id != up_ci.instance_id for u in host_after.attached_upgrades)
        assert any(c.instance_id == up_ci.instance_id
                   for c in state.player_by_id("P1").discard)

    def test_shd_262_no_upgrade_fizzles(self, repo):
        """With no real upgrade in play, Confiscate resolves with no effect."""
        from swu.engine.actions import apply, PlayCard
        confiscate = _get_card(repo, "SHD", "262")
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # no upgrade
        conf_ci = _put_in_hand(state, "P0", confiscate)
        _give_resources(state, "P0", 5, repo)
        state = apply(state, PlayCard(conf_ci.instance_id))
        # Nothing to defeat -> no pending decision, event in discard.
        assert not state.pending_decisions
        assert any(c.instance_id == conf_ci.instance_id
                   for c in state.player_by_id("P0").discard)


class TestCalculatedLethality:
    def test_shd_39_defeats_unit_and_gives_experience_per_upgrade(self, repo):
        """SHD_39 (Event): Defeat a non-leader unit costing <= 3; for each upgrade
        that was on it, give an Experience token to a friendly unit."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (
            legal_actions, apply, PlayCard, ChooseTarget,
            SelectTokenTarget, AutoResolveEffects,
        )
        import uuid
        victim_def = _get_card(repo, "SOR", "128")    # Death Star Stormtrooper, cost 1
        upgrade = _get_card(repo, "SOR", "53")        # a real Upgrade
        friendly_def = _get_card(repo, "SOR", "46")
        lethality = _get_card(repo, "SHD", "39")
        state = _make_state()

        victim = _place(state, "P1", victim_def, "ground")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id="P1", zone=Zone.GROUND_ARENA)
        victim.attached_upgrades.append(up_ci)
        recipient = _place(state, "P0", friendly_def, "ground")
        leth_ci = _put_in_hand(state, "P0", lethality)
        _give_resources(state, "P0", 8, repo)

        # Play the event; choose the victim (cost <= 3, non-leader).
        state = apply(state, PlayCard(leth_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == victim.instance_id)
        state = apply(state, choose)

        # Victim is defeated (no longer in an arena).
        assert _find_instance(state, victim.instance_id) is None
        # A select_token decision is pending (1 upgrade -> 1 Experience token).
        assert state.pending_decisions[-1].kind == "select_token"
        give = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget) and a.target_id == recipient.instance_id)
        state = apply(state, give)

        # The select_token cap (1) is spent; settle the buried event decision.
        if state.pending_decisions:
            auto = next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects))
            state = apply(state, auto)
        assert not state.pending_decisions

        _, rec_after = state.find_instance(recipient.instance_id)
        assert _experience_count(rec_after) == 1

    def test_shd_39_token_recipients_are_friendly_only(self, repo):
        """The Experience-token recipients are restricted to friendly units."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (
            legal_actions, apply, PlayCard, ChooseTarget, SelectTokenTarget,
        )
        import uuid
        victim_def = _get_card(repo, "SOR", "128")
        upgrade = _get_card(repo, "SOR", "53")
        lethality = _get_card(repo, "SHD", "39")
        state = _make_state()

        victim = _place(state, "P1", victim_def, "ground")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=upgrade,
            owner_id="P1", zone=Zone.GROUND_ARENA)
        victim.attached_upgrades.append(up_ci)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        leth_ci = _put_in_hand(state, "P0", lethality)
        _give_resources(state, "P0", 8, repo)

        state = apply(state, PlayCard(leth_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == victim.instance_id)
        state = apply(state, choose)

        token_targets = {a.target_id for a in legal_actions(state)
                         if isinstance(a, SelectTokenTarget)}
        assert friendly.instance_id in token_targets
        assert enemy.instance_id not in token_targets

    def test_shd_39_no_upgrades_no_tokens(self, repo):
        """Defeating a unit with no upgrades gives no tokens (no select_token)."""
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        victim_def = _get_card(repo, "SOR", "128")
        lethality = _get_card(repo, "SHD", "39")
        state = _make_state()
        victim = _place(state, "P1", victim_def, "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        leth_ci = _put_in_hand(state, "P0", lethality)
        _give_resources(state, "P0", 8, repo)

        state = apply(state, PlayCard(leth_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == victim.instance_id)
        state = apply(state, choose)
        assert not state.pending_decisions
        assert _find_instance(state, victim.instance_id) is None


# ── moff-gideon:03 — Card advantage & disruption ──────────────────────────────

class TestDoctorPershing:
    """SHD_28 — Action [Exhaust, deal 1 damage to a friendly unit]: Draw a card.

    The "deal 1 damage to a friendly unit" half of the cost is modelled as a
    mandatory effect ahead of the draw."""

    def test_shd_28_exhaust_damage_friendly_then_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        pershing = _get_card(repo, "SHD", "28")
        ally_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        pershing_ci = _place(state, "P0", pershing, "ground")
        ally_ci = _place(state, "P0", ally_def, "ground")
        _put_on_deck(state, "P0", [_get_card(repo, "SOR", "46")])   # a card to draw
        before_hand = len(state.player_by_id("P0").hand)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == pershing_ci.instance_id)
        state = apply(state, use)
        # Cost is paid: the source is exhausted immediately.
        _, pershing_after = state.find_instance(pershing_ci.instance_id)
        assert pershing_after.exhausted
        # Choose the ally to take the 1 damage (Pershing is also a legal target).
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == ally_ci.instance_id)
        state = apply(state, choose)

        ps = state.player_by_id("P0")
        _, ally_after = state.find_instance(ally_ci.instance_id)
        assert ally_after.damage == 1
        assert len(ps.hand) == before_hand + 1            # drew a card


class TestRemnantReserves:
    """SHD_93 — Search the top 5 cards of your deck for up to 3 units, reveal and
    draw them; bottom the rest in a random order."""

    def test_shd_93_takes_up_to_three_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayCard, SelectSearchCard, FinishSearch)
        rr = _get_card(repo, "SHD", "93")
        unit1 = _get_card(repo, "SHD", "27")     # Hylobon Enforcer (Unit)
        unit2 = _get_card(repo, "SHD", "29")     # Pyke Sentinel (Unit)
        unit3 = _get_card(repo, "SHD", "30")     # Death Trooper (Unit)
        upgrade = _get_card(repo, "SOR", "53")   # Luke's Lightsaber (Upgrade — not a unit)
        event = _get_card(repo, "SHD", "159")    # The Chaos of War (Event — not a unit)
        state = _make_state()
        rr_ci = _put_in_hand(state, "P0", rr)
        _put_on_deck(state, "P0", [unit1, unit2, unit3, upgrade, event])
        _give_resources(state, "P0", 10, repo)   # cost 4 + aspect penalty

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == rr_ci.instance_id)
        state = apply(state, play)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        assert any(isinstance(a, FinishSearch) for a in acts)
        # Exactly the three units in the window are eligible (up to 3).
        assert len([a for a in acts if isinstance(a, SelectSearchCard)]) == 3
        for _ in range(3):
            sel = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)][0]
            state = apply(state, sel)
        # Cap of 3 reached → auto-finished.
        assert not state.pending_decisions
        names = {ci.card_def.name for ci in state.player_by_id("P0").hand}
        assert {unit1.name, unit2.name, unit3.name} <= names


class TestGideonsLightCruiser:
    """SHD_242 — When Played: If you control Moff Gideon, play a [villainy] unit
    that costs 3 or less from your hand or discard pile for free."""

    def test_shd_242_plays_villainy_unit_free_from_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        cruiser = _get_card(repo, "SHD", "242")
        gideon = _get_card(repo, "SHD", "7")        # Moff Gideon (Leader)
        villain = _get_card(repo, "SHD", "27")      # Hylobon Enforcer (Villainy, cost 1)
        nonvillain = _get_card(repo, "SOR", "46")   # not Villainy
        expensive = _get_card(repo, "SHD", "138")   # Jango Fett (Villainy, cost 4)
        state = _make_state()
        _place_leader(state, "P0", gideon)
        cruiser_ci = _place(state, "P0", cruiser, "space")
        v_ci = _put_in_hand(state, "P0", villain)
        _put_in_hand(state, "P0", nonvillain)
        _put_in_hand(state, "P0", expensive)
        # P0 has NO resources — proves the play is "for free".

        state = _fire_when_played(state, cruiser_ci)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        # Only the cheap Villainy unit is eligible (aspect + cost_max filters).
        assert [a.instance_id for a in plays] == [v_ci.instance_id]
        state = apply(state, plays[0])
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == v_ci.instance_id
                   for ci in ps.ground_arena + ps.space_arena)
        assert all(ci.instance_id != v_ci.instance_id for ci in ps.hand)

    def test_shd_242_plays_villainy_unit_from_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        cruiser = _get_card(repo, "SHD", "242")
        gideon = _get_card(repo, "SHD", "7")
        villain = _get_card(repo, "SHD", "27")
        state = _make_state()
        _place_leader(state, "P0", gideon)
        cruiser_ci = _place(state, "P0", cruiser, "space")
        v_ci = _put_in_discard(state, "P0", villain)

        state = _fire_when_played(state, cruiser_ci)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        assert [a.instance_id for a in plays] == [v_ci.instance_id]
        state = apply(state, plays[0])
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == v_ci.instance_id
                   for ci in ps.ground_arena + ps.space_arena)
        assert all(ci.instance_id != v_ci.instance_id for ci in ps.discard)

    def test_shd_242_no_gideon_no_play(self, repo):
        cruiser = _get_card(repo, "SHD", "242")
        villain = _get_card(repo, "SHD", "27")
        state = _make_state()
        cruiser_ci = _place(state, "P0", cruiser, "space")
        _put_in_hand(state, "P0", villain)
        # No Moff Gideon controlled → the gated trigger is never collected.
        state = _fire_when_played(state, cruiser_ci)
        assert not state.pending_decisions


# ── Combat tricks, buffs & tempo (moff-gideon:04) ─────────────────────────────


class TestMoffGideon:
    """SHD_7 — Moff Gideon (Leader, 3/6, Overwhelm)."""

    def test_shd7_action_restricts_attacker_to_cost_3_or_less(self, repo):
        """Undeployed Action: only friendly units costing ≤3 are offered as the
        granted attacker."""
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        gideon = _get_card(repo, "SHD", "7")
        cheap = _get_card(repo, "SOR", "95")   # Battlefield Marine, cost 2
        pricey = _get_card(repo, "SOR", "46")  # Consular Security Force, cost 4
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        cheap_ci = _place(state, "P0", cheap, "ground")
        _place(state, "P0", pricey, "ground")  # cost 4 — must not be offered
        _place(state, "P1", pricey, "ground")  # an enemy unit to target

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == gideon_ci.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attacker_ids = {a.attacker_id for a in legal_actions(state)
                        if isinstance(a, AttackWithUnit)}
        assert attacker_ids == {cheap_ci.instance_id}

    def test_shd7_plus_1_power_only_when_attacking_a_unit(self, repo):
        """The +1/+0 applies when the granted attack hits a unit, not a base."""
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        gideon = _get_card(repo, "SHD", "7")
        cheap = _get_card(repo, "SOR", "95")   # power 3, cost 2
        enemy = _get_card(repo, "SOR", "46")   # 3/7 — survives 4 damage

        # vs a unit: enemy takes power(3) + 1.
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        _place(state, "P0", cheap, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == gideon_ci.instance_id)
        state = apply(state, use)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit) and a.defender_id == enemy_ci.instance_id)
        state = apply(state, atk)
        _, enemy_after = state.find_instance(enemy_ci.instance_id)
        assert enemy_after.damage == cheap.power + 1

        # vs a base: no bonus (base takes power only).
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        _place(state, "P0", cheap, "ground")
        base_before = state.players[1].base_instance.damage
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == gideon_ci.instance_id)
        state = apply(state, use)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit) and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == cheap.power

    def test_shd7_deployed_constant_buffs_cheap_units_attacking_a_unit(self, repo):
        """Deployed: friendly cost-≤3 units get +1/+0 and Overwhelm while
        attacking an enemy unit; the buff is off otherwise and never hits a
        cost->3 unit."""
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        gideon = _get_card(repo, "SHD", "7")
        cheap = _get_card(repo, "SOR", "95")   # cost 2
        pricey = _get_card(repo, "SOR", "46")  # cost 4
        state = _make_state()
        gideon_ci = _place(state, "P0", gideon, "ground")
        gideon_ci.deployed = True
        cheap_ci = _place(state, "P0", cheap, "ground")
        pricey_ci = _place(state, "P0", pricey, "ground")

        # While attacking a unit: +1 power and Overwhelm on the cheap unit.
        assert compute_power(state, cheap_ci, is_attacking=True,
                             attacking_unit=True) == cheap.power + 1
        assert has_keyword(state, cheap_ci, Keyword.OVERWHELM)
        # Not attacking a unit (defending / attacking a base): no power buff.
        assert compute_power(state, cheap_ci, is_attacking=True,
                             attacking_unit=False) == cheap.power
        assert compute_power(state, cheap_ci) == cheap.power
        # A cost->3 friendly unit is never buffed.
        assert compute_power(state, pricey_ci, is_attacking=True,
                             attacking_unit=True) == pricey.power

    def test_shd7_undeployed_grants_no_constant(self, repo):
        """While undeployed (in base_zone), Gideon confers no constant buff."""
        from swu.engine.actions import compute_power
        gideon = _get_card(repo, "SHD", "7")
        cheap = _get_card(repo, "SOR", "95")
        state = _make_state()
        _place_leader(state, "P0", gideon)
        cheap_ci = _place(state, "P0", cheap, "ground")
        assert compute_power(state, cheap_ci, is_attacking=True,
                             attacking_unit=True) == cheap.power

    def test_shd7_action_not_offered_without_a_ready_cost3_unit(self, repo):
        """Regression: the undeployed Action pays an Exhaust cost up front, so it
        must NOT be a legal action when there is no ready cost-≤3 unit to attack
        with — otherwise activating it just exhausts Gideon for nothing (the
        round-1 self-exhaust bug).  Offered again once a ready cost-≤3 unit is in
        play."""
        from swu.engine.actions import legal_actions, UseAbility
        gideon = _get_card(repo, "SHD", "7")
        cheap = _get_card(repo, "SOR", "95")   # Battlefield Marine, cost 2
        pricey = _get_card(repo, "SOR", "46")  # Consular Security Force, cost 4

        def _gideon_action_offered(state, gideon_ci):
            return any(isinstance(a, UseAbility)
                       and a.source_id == gideon_ci.instance_id
                       for a in legal_actions(state))

        # No friendly units at all (round-1 board): not offered.
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        assert not _gideon_action_offered(state, gideon_ci)

        # Only a cost-4 unit: still not offered.
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        _place(state, "P0", pricey, "ground")
        assert not _gideon_action_offered(state, gideon_ci)

        # Only an EXHAUSTED cheap unit (cannot attack): still not offered.
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        exhausted_ci = _place(state, "P0", cheap, "ground")
        exhausted_ci.exhausted = True
        assert not _gideon_action_offered(state, gideon_ci)

        # A ready cost-≤3 unit present: offered.
        state = _make_state()
        gideon_ci = _place_leader(state, "P0", gideon)
        _place(state, "P0", cheap, "ground")
        assert _gideon_action_offered(state, gideon_ci)


class TestGeneralTagge:
    """SHD_81 — When Played: Give an Experience token to each of up to 3 Trooper
    units."""

    def test_shd81_tokens_up_to_3_trooper_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken)
        tagge = _get_card(repo, "SHD", "81")
        trooper = _get_card(repo, "SHD", "83")   # Seasoned Shoretrooper (Trooper)
        nontrooper = _get_card(repo, "SOR", "247")  # Underworld Thug — not a Trooper
        state = _make_state()
        tagge_ci = _place(state, "P0", tagge, "ground")
        t1 = _place(state, "P0", trooper, "ground")
        t2 = _place(state, "P0", trooper, "ground")
        t3 = _place(state, "P0", trooper, "ground")  # 3rd Trooper so we can stop early
        nt = _place(state, "P0", nontrooper, "ground")

        state = _fire_when_played(state, tagge_ci)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert {t1.instance_id, t2.instance_id, t3.instance_id} <= offered
        assert nt.instance_id not in offered  # non-Trooper excluded

        state = apply(state, SelectTokenTarget(t1.instance_id))
        state = apply(state, SelectTokenTarget(t2.instance_id))
        # Stop early (the "up to") — t3 gets nothing.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishSelectToken)))
        _, t1a = state.find_instance(t1.instance_id)
        _, t2a = state.find_instance(t2.instance_id)
        _, t3a = state.find_instance(t3.instance_id)
        assert _experience_count(t1a) == 1 and _experience_count(t2a) == 1
        assert _experience_count(t3a) == 0


class TestOutlandTieVanguard:
    """SHD_82 — When Played: You may give an Experience token to another unit
    that costs 3 or less."""

    def test_shd82_optional_token_to_cheap_other_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        tie = _get_card(repo, "SHD", "82")
        cheap = _get_card(repo, "SOR", "95")   # cost 2
        state = _make_state()
        tie_ci = _place(state, "P0", tie, "ground")
        cheap_ci = _place(state, "P0", cheap, "ground")

        state = _fire_when_played(state, tie_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert tie_ci.instance_id not in offered  # "another" unit excludes self
        assert cheap_ci.instance_id in offered
        state = apply(state, ChooseTarget(cheap_ci.instance_id))
        _, cheap_after = state.find_instance(cheap_ci.instance_id)
        assert _experience_count(cheap_after) == 1

    def test_shd82_no_eligible_target_auto_declines(self, repo):
        """No other cost-≤3 unit → the optional trigger is skipped silently."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        tie = _get_card(repo, "SHD", "82")
        pricey = _get_card(repo, "SOR", "46")  # cost 4 — not eligible
        state = _make_state()
        tie_ci = _place(state, "P0", tie, "ground")
        _place(state, "P0", pricey, "ground")
        state = _fire_when_played(state, tie_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestSeasonedShoretrooper:
    """SHD_83 — While you control 6 or more resources, this unit gets +2/+0."""

    def test_shd83_buff_active_at_6_resources(self, repo):
        from swu.engine.actions import compute_power
        shoretrooper = _get_card(repo, "SHD", "83")
        state = _make_state()
        ci = _place(state, "P0", shoretrooper, "ground")
        base_power = shoretrooper.power

        _give_resources(state, "P0", 5, repo)
        assert compute_power(state, ci) == base_power  # below threshold
        _give_resources(state, "P0", 1, repo)          # now 6
        assert compute_power(state, ci) == base_power + 2


class TestPhaseIIIDarkTrooper:
    """SHD_84 — When combat damage is dealt to this unit: Give an Experience
    token to it (if it survives)."""

    def test_shd84_experience_on_surviving_combat_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        dark = _get_card(repo, "SHD", "84")     # 3/3, Sentinel
        attacker_def = _get_card(repo, "SOR", "247")  # Underworld Thug, power 2
        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        dark_ci = _place(state, "P1", dark, "ground")

        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == dark_ci.instance_id)
        state = apply(state, atk)
        # Dark Trooper took 2 (survives hp 3) and earned one Experience token.
        _, dark_after = state.find_instance(dark_ci.instance_id)
        assert _experience_count(dark_after) == 1

    def test_shd84_no_token_when_defeated(self, repo):
        """Lethal combat damage → no token (the unit did not survive)."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        dark = _get_card(repo, "SHD", "84")     # 3/3
        attacker_def = _get_card(repo, "SOR", "46")  # power 3 → lethal to a 3/3
        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        dark_ci = _place(state, "P1", dark, "ground")
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == dark_ci.instance_id)
        state = apply(state, atk)
        assert _find_instance(state, dark_ci.instance_id) is None  # defeated
        in_discard = [c for c in state.player_by_id("P1").discard
                      if c.instance_id == dark_ci.instance_id]
        assert in_discard and _experience_count(in_discard[0]) == 0


class TestSuperlaserTechnician:
    """SHD_85 — When Defeated: You may put this unit into play as a resource and
    ready it."""

    def _kill_superlaser(self, repo):
        """P0 attacks and defeats P1's Superlaser Technician (2/1).  Returns the
        state mid-WhenDefeated-decision and the technician instance id."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        tech = _get_card(repo, "SHD", "85")      # 2/1
        attacker_def = _get_card(repo, "SOR", "95")  # power 3 → lethal
        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        tech_ci = _place(state, "P1", tech, "ground")
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == tech_ci.instance_id)
        state = apply(state, atk)
        return state, tech_ci.instance_id

    def test_shd85_accept_puts_unit_into_play_as_ready_resource(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects)
        state, tech_id = self._kill_superlaser(repo)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # The no-target CustomEffect resolves via AutoResolveEffects.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AutoResolveEffects)))
        ps = state.player_by_id("P1")
        res = [c for c in ps.resources if c.instance_id == tech_id]
        assert res, "the defeated unit should now be a resource"
        assert not res[0].exhausted          # readied
        assert res[0].zone.name == "RESOURCES"
        assert all(c.instance_id != tech_id for c in ps.discard)

    def test_shd85_decline_leaves_unit_in_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state, tech_id = self._kill_superlaser(repo)
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        ps = state.player_by_id("P1")
        assert any(c.instance_id == tech_id for c in ps.discard)
        assert all(c.instance_id != tech_id for c in ps.resources)


class TestPrivateerCrew:
    """SHD_113 — When played using Smuggle: Give 3 Experience tokens to this
    unit."""

    def test_shd113_three_experience_via_smuggle(self, repo):
        from swu.engine.actions import legal_actions, apply, SmugglePlay
        privateer = _get_card(repo, "SHD", "113")  # Smuggle [6, Command]
        state = _make_state()
        smug = _add_resource(state, "P0", privateer)
        _fill_resources(state, "P0", 12, repo)  # cost 6 + off-aspect penalty
        _add_deck_card(state, "P0", repo)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)
        _, unit = state.find_instance(smug.instance_id)
        assert _experience_count(unit) == 3

    def test_shd113_no_tokens_when_played_from_hand(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        import uuid
        privateer = _get_card(repo, "SHD", "113")
        state = _make_state()
        ci = CardInstance(instance_id=f"p_{uuid.uuid4().hex[:6]}", card_def=privateer,
                          owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        _give_resources(state, "P0", 10, repo)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id)
        state = apply(state, play)
        _, unit = state.find_instance(ci.instance_id)
        assert _experience_count(unit) == 0  # WhenPlayedViaSmuggle did not fire


# ── moff-gideon:05 — Combat tricks, buffs & tempo ─────────────────────────────

class TestKihraxzHeavyFighter:
    """SHD_118 — On Attack: You may exhaust another friendly unit. If you do, this
    unit gets +3/+0 for this attack."""

    def test_shd118_exhaust_another_unit_buffs_self(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power)
        kihraxz = _get_card(repo, "SHD", "118")    # 3/3
        friendly = _get_card(repo, "SOR", "95")    # Battlefield Marine (ready)
        state = _make_state()
        kihraxz_ci = _place(state, "P0", kihraxz, "space")
        friendly_ci = _place(state, "P0", friendly, "ground")
        base_power = compute_power(state, kihraxz_ci, is_attacking=True)

        state = _fire_on_attack(state, kihraxz_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Only the other friendly (ready) unit is offered — not Kihraxz itself.
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert offered == {friendly_ci.instance_id}
        state = apply(state, ChooseTarget(friendly_ci.instance_id))

        _, friendly_after = state.find_instance(friendly_ci.instance_id)
        assert friendly_after.exhausted                       # paid the cost
        assert compute_power(state, kihraxz_ci, is_attacking=True) == base_power + 3

    def test_shd118_no_other_ready_unit_auto_declines(self, repo):
        """Kihraxz alone (no other ready friendly unit) → optional trigger skipped."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        kihraxz = _get_card(repo, "SHD", "118")
        state = _make_state()
        kihraxz_ci = _place(state, "P0", kihraxz, "space")
        state = _fire_on_attack(state, kihraxz_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_shd118_exhausted_unit_not_offered(self, repo):
        """An already-exhausted friendly unit cannot be exhausted, so with only an
        exhausted other unit the trigger has no legal target and is skipped."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        kihraxz = _get_card(repo, "SHD", "118")
        friendly = _get_card(repo, "SOR", "95")
        state = _make_state()
        kihraxz_ci = _place(state, "P0", kihraxz, "space")
        friendly_ci = _place(state, "P0", friendly, "ground")
        friendly_ci.exhausted = True
        state = _fire_on_attack(state, kihraxz_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestOutflank:
    """SHD_128 — Attack with 2 units (one at a time)."""

    def test_shd128_grants_two_attacks(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, AttackWithUnit
        import uuid
        outflank = _get_card(repo, "SHD", "128")
        u1 = _get_card(repo, "SOR", "95")   # power 3
        u2 = _get_card(repo, "SOR", "247")  # power 2
        state = _make_state()
        u1_ci = _place(state, "P0", u1, "ground")
        u2_ci = _place(state, "P0", u2, "ground")
        of_ci = CardInstance(
            instance_id=f"of_{uuid.uuid4().hex[:6]}", card_def=outflank,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(of_ci)
        _give_resources(state, "P0", 5, repo)
        base_before = state.players[1].base_instance.damage

        state = apply(state, PlayCard(of_ci.instance_id))
        assert state.pending_decisions[-1].kind == "granted_attack"
        # First granted attack: u1 → base.
        atk1 = next(a for a in legal_actions(state)
                    if isinstance(a, AttackWithUnit)
                    and a.attacker_id == u1_ci.instance_id and a.defender_id is None)
        state = apply(state, atk1)
        # A second granted attack is still pending; the first attacker is exhausted.
        assert state.pending_decisions[-1].kind == "granted_attack"
        offered = {a.attacker_id for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)}
        assert u1_ci.instance_id not in offered      # exhausted by its attack
        assert u2_ci.instance_id in offered
        atk2 = next(a for a in legal_actions(state)
                    if isinstance(a, AttackWithUnit)
                    and a.attacker_id == u2_ci.instance_id and a.defender_id is None)
        state = apply(state, atk2)

        assert not state.pending_decisions
        assert state.players[1].base_instance.damage - base_before == u1.power + u2.power


class TestMomentOfGlory:
    """SHD_130 — Give a unit +4/+4 for this phase."""

    def test_shd130_buffs_a_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (
            legal_actions, apply, PlayCard, ChooseTarget, compute_power, compute_hp)
        import uuid
        glory = _get_card(repo, "SHD", "130")
        unit = _get_card(repo, "SOR", "95")   # 3/3
        state = _make_state()
        unit_ci = _place(state, "P0", unit, "ground")
        glory_ci = CardInstance(
            instance_id=f"glory_{uuid.uuid4().hex[:6]}", card_def=glory,
            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(glory_ci)
        _give_resources(state, "P0", 6, repo)
        p0 = compute_power(state, unit_ci)
        h0 = compute_hp(state, unit_ci)

        state = apply(state, PlayCard(glory_ci.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == unit_ci.instance_id))
        assert compute_power(state, unit_ci) == p0 + 4
        assert compute_hp(state, unit_ci) == h0 + 4


class TestSnowtrooperLieutenant:
    """SHD_236 — When Played: You may attack with a unit. If it's an Imperial unit,
    it gets +2/+0 for this attack."""

    def test_shd236_imperial_attacker_gets_plus_2(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        snow = _get_card(repo, "SHD", "236")
        imperial = _get_card(repo, "SHD", "83")   # Seasoned Shoretrooper, power 2, Imperial
        state = _make_state()
        snow_ci = _place(state, "P0", snow, "ground")
        imperial_ci = _place(state, "P0", imperial, "ground")
        base_before = state.players[1].base_instance.damage

        state = _fire_when_played(state, snow_ci)
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == imperial_ci.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Imperial unit: power 2 + 2 bonus = 4 to the base.
        assert state.players[1].base_instance.damage - base_before == imperial.power + 2

    def test_shd236_non_imperial_attacker_no_bonus(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        snow = _get_card(repo, "SHD", "236")
        rebel = _get_card(repo, "SOR", "46")   # Consular Security Force, power 3, Rebel
        state = _make_state()
        snow_ci = _place(state, "P0", snow, "ground")
        rebel_ci = _place(state, "P0", rebel, "ground")
        base_before = state.players[1].base_instance.damage

        state = _fire_when_played(state, snow_ci)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == rebel_ci.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Non-Imperial: power 3, no bonus.
        assert state.players[1].base_instance.damage - base_before == rebel.power

    def test_shd236_may_decline_the_attack(self, repo):
        """"You may attack" — a DeclineGrantedAttack is always offered."""
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        snow = _get_card(repo, "SHD", "236")
        imperial = _get_card(repo, "SHD", "83")
        state = _make_state()
        snow_ci = _place(state, "P0", snow, "ground")
        _place(state, "P0", imperial, "ground")
        state = _fire_when_played(state, snow_ci)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineGrantedAttack))
        state = apply(state, decline)
        assert not state.pending_decisions


class TestIncineratorTrooper:
    """SHD_234 — "While attacking, this unit deals combat damage before the
    defender. (If the defender is defeated, it deals no combat damage.)" =
    First Strike, modelled as a constant self-grant of the First Strike keyword."""

    def test_shd234_has_first_strike_keyword(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        trooper = _get_card(repo, "SHD", "234")
        state = _make_state()
        ci = _place(state, "P0", trooper, "ground")
        assert has_keyword(state, ci, Keyword.FIRST_STRIKE)

    def test_shd234_kills_first_and_takes_no_return_damage(self, repo):
        """Incinerator (2/2) attacks a 3/1 unit: its 2 damage defeats the defender
        before the defender's lethal 3 power is dealt, so it survives."""
        from swu.engine.actions import apply, AttackWithUnit
        trooper = _get_card(repo, "SHD", "234")     # power 2, hp 2
        defender = _get_card(repo, "SOR", "128")    # Death Star Stormtrooper (power 3, hp 1)
        state = _make_state()
        atk_ci = _place(state, "P0", trooper, "ground")
        def_ci = _place(state, "P1", defender, "ground")

        state = apply(state, AttackWithUnit(atk_ci.instance_id, def_ci.instance_id))

        assert _find_instance(state, def_ci.instance_id) is None, "defender defeated first"
        atk_now = _find_instance(state, atk_ci.instance_id)
        assert atk_now is not None and atk_now.damage == 0, \
            "first striker takes no return damage from a defeated defender"


# ── Reprint-duplicate encode (Stage 4 of docs/reprint_duplicates_plan.md) ─────

class TestSupremeLeaderSnoke:
    """SHD_37 — "Each enemy non-leader unit gets -2/-2." (sibs J24_3, P25_76)."""

    def test_shd_37_debuffs_enemy_non_leader_units(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "37"), "ground")  # Snoke
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert compute_power(state, enemy) == 1  # 3 - 2
        assert compute_hp(state, enemy) == 5     # 7 - 2

    def test_shd_37_leaves_friendly_units_alone(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "37"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, friendly) == 3
        assert compute_hp(state, friendly) == 7

    def test_shd_37_debuff_lifts_when_snoke_leaves(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        snoke = _place(state, "P0", _get_card(repo, "SHD", "37"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, enemy) == 1
        state.player_by_id("P0").ground_arena.remove(snoke)
        assert compute_power(state, enemy) == 3


class TestStreetGangRecruiter:
    """SHD_260 — When Played: You may return an Underworld card from your discard
    pile to your hand (reprint canonical; sib LAW_261)."""

    def test_shd_260_returns_underworld_card(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard, FinishReturnFromDiscard
        recruiter = _get_card(repo, "SHD", "260")            # Underworld
        underworld = _get_card(repo, "SHD", "260")           # another Underworld card
        non_underworld = _get_card(repo, "SOR", "46")        # Republic (ineligible)
        state = _make_state()
        rec_ci = _place(state, "P0", recruiter, "ground")
        uw_ci = _put_in_discard(state, "P0", underworld)
        _put_in_discard(state, "P0", non_underworld)

        state = _fire_when_played(state, rec_ci)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        acts = legal_actions(state)
        sels = [a for a in acts if isinstance(a, SelectDiscardCard)]
        assert [a.instance_id for a in sels] == [uw_ci.instance_id]  # only Underworld
        assert any(isinstance(a, FinishReturnFromDiscard) for a in acts)  # "you may"
        state = apply(state, sels[0])
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert any(ci.instance_id == uw_ci.instance_id for ci in ps.hand)

    def test_shd_260_no_underworld_no_decision(self, repo):
        recruiter = _get_card(repo, "SHD", "260")
        non_underworld = _get_card(repo, "SOR", "46")
        state = _make_state()
        rec_ci = _place(state, "P0", recruiter, "ground")
        _put_in_discard(state, "P0", non_underworld)
        state = _fire_when_played(state, rec_ci)
        assert not state.pending_decisions   # nothing eligible → fizzles


# ── Reprint-duplicate encode (Stage 4 batch 5) ────────────────────────────────

class TestTheMandalorianSHD49:
    """SHD_49 — Sentinel.  When Played: You may heal all damage from a unit that
    costs 2 or less and give 2 Shield tokens to it."""

    def test_shd_49_heals_all_and_gives_two_shields(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SHD", "49"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "236"), "ground")  # cost1, 1/4
        ally.damage = 3
        state = _fire_when_played(state, mando)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(ally.instance_id))
        healed = _find_instance(state, ally.instance_id)
        assert healed.damage == 0
        assert _shield_count(healed) == 2

    def test_shd_49_only_cheap_units_targetable(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SHD", "49"), "ground")
        cheap = _place(state, "P0", _get_card(repo, "SOR", "236"), "ground")  # cost 1
        pricey = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state = _fire_when_played(state, mando)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered

    def test_shd_49_auto_declines_with_no_cheap_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SHD", "49"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # cost 4 only
        state = _fire_when_played(state, mando)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestTakeCaptive:
    """SHD_131 (Event): "A friendly unit captures an enemy non-leader unit in the
    same arena."  Two dependent CustomEffect.targets + the capture primitive."""

    def test_shd_131_captures_enemy_in_same_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayCard
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # An enemy in the OTHER arena must not be a legal capture target.
        enemy_space = _place(state, "P1", _get_card(repo, "SOR", "40"), "space")
        ev = _put_in_hand(state, "P0", _get_card(repo, "SHD", "131"))
        _give_resources(state, "P0", 5, repo)

        state = apply(state, PlayCard(ev.instance_id))
        # Stage 1: pick the friendly captor.
        pick_captor = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget) and a.target_id == captor.instance_id)
        state = apply(state, pick_captor)
        # Stage 2: only the enemy in the captor's (ground) arena is offered.
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy_ground.instance_id in offered
        assert enemy_space.instance_id not in offered
        state = apply(state, ChooseTarget(enemy_ground.instance_id))

        # The enemy left P1's arena and sits facedown in P0's capture pile.
        assert all(u.instance_id != enemy_ground.instance_id
                   for u in state.player_by_id("P1").ground_arena)
        assert any(c.instance_id == enemy_ground.instance_id
                   for c in state.player_by_id("P0").capture_pile)

    def test_shd_131_fizzles_with_no_enemy_in_same_arena(self, repo):
        from swu.engine.actions import apply, ChooseTarget, PlayCard
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "40"), "space")  # enemy in other arena
        ev = _put_in_hand(state, "P0", _get_card(repo, "SHD", "131"))
        _give_resources(state, "P0", 5, repo)
        state = apply(state, PlayCard(ev.instance_id))
        state = apply(state, ChooseTarget(captor.instance_id))
        # No enemy in the ground arena → nothing captured.
        assert len(state.player_by_id("P0").capture_pile) == 0


class TestKyloRenSHD141:
    """SHD_141 On Attack: Give a unit +2/+0 this phase; if non-Villainy, also give
    it an Experience token."""

    def _experience_count(self, ci):
        from swu.cards.models import TokenUpgrade
        return sum(1 for u in ci.attached_upgrades
                   if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Experience")

    def test_shd_141_buffs_and_tokens_non_villainy_target(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "SHD", "141"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Heroism, non-Villainy
        base_power = compute_power(state, target)
        state = _fire_on_attack(state, kylo)
        state = apply(state, ChooseTarget(target.instance_id))
        _, t_after = state.find_instance(target.instance_id)
        # +2/+0 from the buff and +1/+1 from the Experience token → +3 power.
        assert compute_power(state, t_after) == base_power + 3
        assert self._experience_count(t_after) == 1

    def test_shd_141_no_token_for_villainy_target(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "SHD", "141"), "ground")
        # A Villainy enemy unit (Avenger SOR_40 is Vigilance/Villainy).
        target = _place(state, "P1", _get_card(repo, "SOR", "40"), "space")
        base_power = compute_power(state, target)
        state = _fire_on_attack(state, kylo)
        state = apply(state, ChooseTarget(target.instance_id))
        _, t_after = state.find_instance(target.instance_id)
        assert compute_power(state, t_after) == base_power + 2
        assert self._experience_count(t_after) == 0


class TestReySHD46:
    """SHD_46 On Attack (optional): heal 2 from a unit; if non-Heroism, give it a
    Shield token."""

    def _shield_count(self, ci):
        from swu.cards.models import TokenUpgrade
        return sum(1 for u in ci.attached_upgrades
                   if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Shield")

    def test_shd_46_heals_and_shields_non_heroism(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "SHD", "46"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "40"), "space")  # Villainy (non-Heroism)
        target.damage = 3
        state = _fire_on_attack(state, rey)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        _, t_after = state.find_instance(target.instance_id)
        assert t_after.damage == 1  # healed 2
        assert self._shield_count(t_after) == 1

    def test_shd_46_no_shield_for_heroism(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "SHD", "46"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Heroism
        target.damage = 3
        state = _fire_on_attack(state, rey)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        _, t_after = state.find_instance(target.instance_id)
        assert t_after.damage == 1
        assert self._shield_count(t_after) == 0

    def test_shd_46_is_optional(self, repo):
        from swu.engine.actions import legal_actions, DeclineTrigger
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "SHD", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, rey)
        assert any(isinstance(a, DeclineTrigger) for a in legal_actions(state))


# ── Maul SHD_90 (combat-damage redirect) ─────────────────────────────────────

class TestMaulSHD90:
    """SHD_90 — Maul (7/6 Ground, Underworld; Ambush/Overwhelm = keyword layer):
    "On Attack: You may choose another friendly Underworld unit. If you do, all
    combat damage that would be dealt to this unit during this attack is dealt to
    the chosen unit instead."

    Exercises the batch-38 combat-damage-redirect primitive (a this_attack
    ``combat_damage_redirect_to`` flag on the attacker, read at the combat step)."""

    def _resolve_attack(self, state, attacker_id, defender_id, *,
                        accept=True, redirect_id=None):
        """Drive apply(AttackWithUnit) to full combat resolution, resolving the
        redirect trigger (accept + choose redirect_id, or decline) and the
        pre_attack continuation along the way."""
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, AcceptTrigger, DeclineTrigger,
            ChooseTarget, ContinueAttack)
        state = apply(state, AttackWithUnit(attacker_id, defender_id))
        while state.pending_decisions:
            top = state.pending_decisions[-1]
            acts = legal_actions(state)
            if top.kind == "trigger_option":
                if accept:
                    state = apply(state, next(a for a in acts
                                              if isinstance(a, AcceptTrigger)))
                else:
                    state = apply(state, next(a for a in acts
                                              if isinstance(a, DeclineTrigger)))
            elif top.kind == "pre_attack":
                state = apply(state, next(a for a in acts
                                          if isinstance(a, ContinueAttack)))
            else:  # resolve_effects / choose_target for the redirect
                state = apply(state, next(
                    a for a in acts
                    if isinstance(a, ChooseTarget) and a.target_id == redirect_id))
        return state

    def test_shd_90_on_attack_sets_redirect_flag_and_serialises(self, repo):
        """The OnAttack chooses another friendly Underworld unit and records it on
        Maul's redirect flag; the flag survives a JSON round-trip."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        maul = _get_card(repo, "SHD", "90")
        thug = _get_card(repo, "SOR", "247")   # Underworld Thug (Underworld, 2/3)
        state = _make_state()
        maul_ci = _place(state, "P0", maul, "ground")
        thug_ci = _place(state, "P0", thug, "ground")

        state = _fire_on_attack(state, maul_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Only the OTHER friendly Underworld unit is offered — not Maul himself.
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert offered == {thug_ci.instance_id}
        state = apply(state, ChooseTarget(thug_ci.instance_id))

        _, maul_after = state.find_instance(maul_ci.instance_id)
        assert maul_after.combat_damage_redirect_to == thug_ci.instance_id

        from swu.engine.state import GameState
        restored = GameState.from_json(state.to_json())
        _, maul_r = restored.find_instance(maul_ci.instance_id)
        assert maul_r.combat_damage_redirect_to == thug_ci.instance_id

    def test_shd_90_redirects_return_damage_to_chosen_unit(self, repo):
        """Maul attacks; his return combat damage lands on the chosen Underworld
        unit (which survives), Maul takes none, and the flag is cleared afterward."""
        maul = _get_card(repo, "SHD", "90")
        thug = _get_card(repo, "SOR", "247")       # redirect sink (2/3)
        defender = _get_card(repo, "SOR", "247")   # enemy defender (power 2, 3 hp)
        state = _make_state()
        maul_ci = _place(state, "P0", maul, "ground")
        thug_ci = _place(state, "P0", thug, "ground")
        def_ci = _place(state, "P1", defender, "ground")

        state = self._resolve_attack(state, maul_ci.instance_id, def_ci.instance_id,
                                     accept=True, redirect_id=thug_ci.instance_id)

        _, maul_after = state.find_instance(maul_ci.instance_id)
        assert maul_after.damage == 0, "Maul takes no combat damage (redirected)"
        assert maul_after.combat_damage_redirect_to is None, "flag cleared post-attack"
        _, thug_after = state.find_instance(thug_ci.instance_id)
        assert thug_after.damage == 2, "chosen unit absorbs the defender's 2 power"
        # Maul (power 7) still killed the defender.
        assert _find_instance(state, def_ci.instance_id) is None

    def test_shd_90_no_other_underworld_unit_auto_declines(self, repo):
        """With no other friendly Underworld unit, the optional trigger is skipped and
        Maul takes his return combat damage normally (no redirect)."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        maul = _get_card(repo, "SHD", "90")
        defender = _get_card(repo, "SOR", "247")   # power 2
        state = _make_state()
        maul_ci = _place(state, "P0", maul, "ground")
        def_ci = _place(state, "P1", defender, "ground")

        # Firing OnAttack in isolation: no legal redirect target → no decision.
        s2 = _fire_on_attack(_make_state(), maul_ci)
        assert not s2.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(s2))

        state = self._resolve_attack(state, maul_ci.instance_id, def_ci.instance_id,
                                     accept=False)
        _, maul_after = state.find_instance(maul_ci.instance_id)
        assert maul_after.damage == 2, "no redirect → Maul takes the return damage"

    def test_shd_90_declined_redirect_leaves_maul_taking_damage(self, repo):
        """A present Underworld unit but a declined trigger → Maul takes the damage,
        the chosen unit is untouched, and no flag is set."""
        maul = _get_card(repo, "SHD", "90")
        thug = _get_card(repo, "SOR", "247")
        defender = _get_card(repo, "SOR", "247")   # power 2
        state = _make_state()
        maul_ci = _place(state, "P0", maul, "ground")
        thug_ci = _place(state, "P0", thug, "ground")
        def_ci = _place(state, "P1", defender, "ground")

        state = self._resolve_attack(state, maul_ci.instance_id, def_ci.instance_id,
                                     accept=False)
        _, maul_after = state.find_instance(maul_ci.instance_id)
        assert maul_after.damage == 2
        _, thug_after = state.find_instance(thug_ci.instance_id)
        assert thug_after.damage == 0

    def test_shd_90_redirect_unit_can_be_defeated_by_redirected_damage(self, repo):
        """A pre-damaged chosen unit is defeated when the redirected damage is lethal
        (homed by the post-action defeat sweep); Maul survives untouched."""
        maul = _get_card(repo, "SHD", "90")
        thug = _get_card(repo, "SOR", "247")       # 2/3
        defender = _get_card(repo, "SOR", "247")   # power 2
        state = _make_state()
        maul_ci = _place(state, "P0", maul, "ground")
        thug_ci = _place(state, "P0", thug, "ground")
        thug_ci.damage = 1                          # remaining 2; +2 redirected = lethal
        def_ci = _place(state, "P1", defender, "ground")

        state = self._resolve_attack(state, maul_ci.instance_id, def_ci.instance_id,
                                     accept=True, redirect_id=thug_ci.instance_id)

        assert _find_instance(state, thug_ci.instance_id) is None, "chosen unit defeated"
        _, maul_after = state.find_instance(maul_ci.instance_id)
        assert maul_after.damage == 0

    def test_shd_90_reprints_alias_to_canonical(self):
        """J24_4 / P25_155 / P25_165 alias to the shipped SHD_90 registration."""
        import swu.cards  # noqa: F401 — ensure aliases are applied
        from swu.abilities.registry import get_abilities
        canonical = get_abilities("SHD", "90")
        assert canonical, "SHD_90 must be registered"
        for sc, cn in (("J24", "4"), ("P25", "155"), ("P25", "165")):
            assert get_abilities(sc, cn) == canonical, f"{sc}_{cn} should alias SHD_90"


# ── shd-set:01 — Direct damage & removal (leaders + Synara San) ────────────────


def _fire_when_deployed(state, leader_ci):
    """Fire a LeaderDeployed trigger for a leader already a deployed unit in an
    arena (deployed=True)."""
    from swu.engine.events import LeaderDeployed
    from swu.abilities.resolver import fire_triggered_abilities
    arena = "Ground" if leader_ci.zone.name == "GROUND_ARENA" else "Space"
    evt = LeaderDeployed(
        player_id=leader_ci.owner_id, instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name, arena=arena,
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestQira:
    """SHD_2 — Qi'ra (Leader)."""

    def test_SHD_2_undeployed_deals_2_then_shields_same_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget, compute_hp)
        qira = _get_card(repo, "SHD", "2")
        unit = _get_card(repo, "SOR", "116")   # a friendly unit with ample HP
        state = _make_state()
        leader_ci = _place_leader(state, "P0", qira)
        _give_resources(state, "P0", 1, repo)
        target_ci = _place(state, "P0", unit, "ground")
        assert compute_hp(state, target_ci) > 2   # survives 2 damage

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)

        _, tgt = state.find_instance(target_ci.instance_id)
        assert tgt.damage == 2                  # dealt 2
        assert _shield_count(tgt) == 1          # then Shielded (same "it")

    def test_SHD_2_when_deployed_heals_all_then_halves(self, repo):
        from swu.engine.actions import compute_hp
        qira = _get_card(repo, "SHD", "2")
        friendly = _get_card(repo, "SOR", "116")
        enemy = _get_card(repo, "SOR", "116")
        state = _make_state()
        leader_ci = _place(state, "P0", qira, "ground")
        leader_ci.deployed = True
        f_ci = _place(state, "P0", friendly, "ground")
        f_ci.damage = 3
        e_ci = _place(state, "P1", enemy, "ground")
        e_ci.damage = 1
        fhp = compute_hp(state, f_ci)
        ehp = compute_hp(state, e_ci)

        state = _fire_when_deployed(state, leader_ci)

        f = _find_instance(state, f_ci.instance_id)
        e = _find_instance(state, e_ci.instance_id)
        # each was healed to 0 then dealt floor(remaining_hp / 2)
        assert f.damage == fhp // 2
        assert e.damage == ehp // 2


class TestFinn:
    """SHD_3 — Finn (Leader)."""

    def test_SHD_3_undeployed_defeats_upgrade_then_shields_host(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget)
        finn = _get_card(repo, "SHD", "3")
        host = _get_card(repo, "SOR", "116")
        upgrade = _get_card(repo, "SHD", "74")   # Vambrace (a real upgrade)
        state = _make_state()
        leader_ci = _place_leader(state, "P0", finn)
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, upgrade, "P0")

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == up.instance_id)
        state = apply(state, choose)

        _, host_after = state.find_instance(host_ci.instance_id)
        assert all(u.instance_id != up.instance_id for u in host_after.attached_upgrades)
        assert _shield_count(host_after) == 1   # host gained a Shield ("if you do")
        _, leader = state.find_instance(leader_ci.instance_id)
        assert leader.exhausted is True          # the ExhaustSelf cost was paid


class TestBoKatanKryze:
    """SHD_12 — Bo-Katan Kryze (Leader)."""

    def test_SHD_12_undeployed_gated_by_mandalorian_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        bo = _get_card(repo, "SHD", "12")
        mando = _get_card(repo, "SHD", "47")     # The Armorer (Mandalorian)
        enemy = _get_card(repo, "SOR", "116")
        state = _make_state()
        leader_ci = _place_leader(state, "P0", bo)
        mando_ci = _place(state, "P0", mando, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        # No Mandalorian attacked this phase -> the ability is not offered.
        assert not any(isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id
                       for a in legal_actions(state))

        # Record a friendly Mandalorian as having attacked this phase.
        state.game_memory.units_attacked_this_round.add(mando_ci.instance_id)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, enemy_after = state.find_instance(enemy_ci.instance_id)
        assert enemy_after.damage == 1


class TestCadBane:
    """SHD_14 — Cad Bane (Leader)."""

    def test_SHD_14_deployed_underworld_play_opponent_chooses_takes_2(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseOwnTarget, ConfirmOpponentDamage)
        cad = _get_card(repo, "SHD", "14")
        underworld = _get_card(repo, "SHD", "33")   # Synara San (Underworld)
        enemy = _get_card(repo, "SOR", "116")
        state = _make_state()
        leader_ci = _place(state, "P0", cad, "ground")
        leader_ci.deployed = True
        played = _place(state, "P0", underworld, "ground")   # the Underworld card played
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_card_played(state, "P0", played)
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger) and a.source_id == leader_ci.instance_id)
        state = apply(state, accept)
        # Resolve the (no-target) CustomEffect, which pushes the opponent decision.
        state = apply(state, next(
            a for a in legal_actions(state) if type(a).__name__ == "AutoResolveEffects"))
        # The opponent (P1) chooses their own unit.
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseOwnTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, pick)
        # The controller confirms the 2 damage.
        confirm = next(a for a in legal_actions(state)
                       if isinstance(a, ConfirmOpponentDamage))
        state = apply(state, confirm)

        _, enemy_after = state.find_instance(enemy_ci.instance_id)
        assert enemy_after.damage == 2


class TestSynaraSan:
    """SHD_33 — Synara San (Unit): conditional Bounty while exhausted."""

    def test_SHD_33_bounty_deals_5_to_base_only_while_exhausted(self, repo):
        synara = _get_card(repo, "SHD", "33")

        # Exhausted at defeat -> the Bounty fires: opponent (collector) deals 5 to
        # the owner's base.
        state = _make_state()
        syn_ci = _place(state, "P0", synara, "ground")
        syn_ci.exhausted = True
        base = state.player_by_id("P0").base_zone[0]
        _fire_when_defeated(state, syn_ci)
        assert base.damage == 5

        # Ready at defeat -> no Bounty (SOURCE_EXHAUSTED gate false).
        state2 = _make_state()
        syn2 = _place(state2, "P0", synara, "ground")
        syn2.exhausted = False
        base2 = state2.player_by_id("P0").base_zone[0]
        _fire_when_defeated(state2, syn2)
        assert base2.damage == 0


# ── shd-set:01 — leader escalations (Bossk SHD_10, Lando SHD_17) ───────────────

class TestBossk:
    def test_SHD_10_undeployed_targets_only_bounty_units(self, repo):
        """Undeployed Action [Exhaust]: Deal 1 damage to a unit with a Bounty — only
        a unit that currently carries a Bounty ability is a legal target."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        bossk = _get_card(repo, "SHD", "10")
        bounty_unit = _get_card(repo, "SHD", "95")   # Clone Deserter (printed Bounty)
        plain = _get_card(repo, "SOR", "46")          # no Bounty
        state = _make_state()
        bossk_ci = _place_leader(state, "P0", bossk)
        bunit = _place(state, "P1", bounty_unit, "ground")
        punit = _place(state, "P1", plain, "ground")

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == bossk_ci.instance_id)
        state = apply(state, use)
        targets = [a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        assert bunit.instance_id in targets
        assert punit.instance_id not in targets

        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == bunit.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(bunit.instance_id)
        assert hit.damage == 1

    def test_SHD_10_deployed_recollects_a_bounty(self, repo):
        """Deployed "When you collect a bounty: You may collect that bounty again."
        Defeating an enemy Bounty unit lets P0 (the collector, controlling Bossk)
        draw once for the bounty and once more for the re-collection — and the
        once-per-round is spent."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects,
        )
        from swu.engine import actions as A
        bossk = _get_card(repo, "SHD", "10")
        deserter = _get_card(repo, "SHD", "95")  # enemy: "Bounty — Draw a card"
        state = _make_state()
        bossk_ci = _place(state, "P0", bossk, "ground")
        bossk_ci.deployed = True
        _add_deck_card(state, "P0", repo, n=4)
        deck0 = len(state.player_by_id("P0").deck)
        deserter_ci = _place(state, "P1", deserter, "ground")

        # Defeat the enemy Bounty unit → the collector (P0) draws 1 (first collection).
        state = _defeat_and_fire(state, deserter_ci, "P1")
        assert len(state.player_by_id("P0").deck) == deck0 - 1

        # Drain the bounties-collected ledger → Bossk's optional WhenBountyCollected.
        state = A._fire_bounty_observers(state)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Resolve any pending auto-resolvable effects (Bossk's CustomEffect → the
        # re-collected bounty's DrawCards).
        for _ in range(6):
            if not state.pending_decisions:
                break
            auto = next((a for a in legal_actions(state)
                         if isinstance(a, AutoResolveEffects)), None)
            if auto is None:
                break
            state = apply(state, auto)

        # The bounty was collected a SECOND time → P0 drew again (2 total).
        assert len(state.player_by_id("P0").deck) == deck0 - 2
        assert bossk_ci.instance_id in state.game_memory.bounty_recollect_used_this_round


class TestLandoCalrissian:
    def test_SHD_17_undeployed_smuggles_for_2_less_then_defeats_a_resource(self, repo):
        """Undeployed Action [Exhaust]: Play a card using Smuggle (costs 2 less),
        then defeat a resource you own.  The smuggled unit enters play, only
        (smuggle_cost − 2) resources are exhausted to pay, and the net resource count
        drops by 1 (the replaced card minus the defeated resource)."""
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayViaSmuggle
        lando = _get_card(repo, "SHD", "17")
        smug_unit = _synthetic_unit(cost=3, smuggle_text="Smuggle [3 resources]")
        state = _make_state()
        lando_ci = _place_leader(state, "P0", lando)
        smug = _add_resource(state, "P0", smug_unit)      # the card to smuggle
        _fill_resources(state, "P0", 3, repo)             # 3 OTHER ready resources
        _add_deck_card(state, "P0", repo)                 # replacement for the zone
        ps0 = state.player_by_id("P0")
        res_before = len(ps0.resources)                    # 1 + 3 = 4

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == lando_ci.instance_id)
        state = apply(state, use)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayViaSmuggle) and a.instance_id == smug.instance_id)
        state = apply(state, play)

        ps0 = state.player_by_id("P0")
        # The smuggled unit is now in play (ground arena).
        assert any(u.instance_id == smug.instance_id for u in ps0.ground_arena)
        # Smuggle cost 3 − 2 = 1 resource paid (verified via the CardPlayed event, so
        # it's robust to which resource the "defeat a resource" step later removes).
        from swu.engine.events import CardPlayed
        played = next(e for e in state.event_log
                      if isinstance(e, CardPlayed) and e.instance_id == smug.instance_id)
        assert played.cost_paid == 1
        # Net resource count: 4 → (remove smug, add replacement = 4) → defeat 1 = 3.
        assert len(ps0.resources) == res_before - 1


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

class TestRoseTico:
    def test_SHD_45_on_attack_defeats_shield_for_2_experience(self, repo):
        """SHD_45 — On Attack: may defeat a Shield token on a friendly unit; if so,
        give 2 Experience tokens to that unit."""
        from swu.engine import tokens
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        rose = _get_card(repo, "SHD", "45")
        ally = _get_card(repo, "SOR", "46")
        state = _make_state()
        rose_ci = _place(state, "P0", rose, "ground")
        ally_ci = _place(state, "P0", ally, "ground")
        tokens.attach_token(state, state.player_by_id("P0"), ally_ci, "Shield")
        assert _shield_count(ally_ci) == 1

        state = _fire_on_attack(state, rose_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == ally_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(ally_ci.instance_id)
        assert _shield_count(hit) == 0, "Shield token defeated"
        assert _experience_count(hit) == 2, "gained 2 Experience tokens"


class TestChewbaccaShd50:
    def test_SHD_50_when_played_defeats_low_hp_unit(self, repo):
        """SHD_50 — When Played: may defeat a unit with 5 or less remaining HP."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        chewie = _get_card(repo, "SHD", "50")
        victim = _get_card(repo, "SOR", "46")
        state = _make_state()
        chewie_ci = _place(state, "P0", chewie, "ground")
        victim_ci = _place(state, "P1", victim, "ground")
        victim_ci.damage = victim.hp - 2  # remaining HP = 2 (<= 5)

        state = _fire_when_played(state, chewie_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == victim_ci.instance_id)
        state = apply(state, choose)
        assert _find_instance(state, victim_ci.instance_id) is None, "victim defeated"

    def test_SHD_50_no_target_when_hp_above_5(self, repo):
        """The optional trigger offers nothing when no unit has <= 5 remaining HP."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        chewie = _get_card(repo, "SHD", "50")
        tough = _get_card(repo, "SOR", "46")
        state = _make_state()
        chewie_ci = _place(state, "P0", chewie, "ground")
        tough_ci = _place(state, "P1", tough, "ground")
        assert tough.hp > 5 and tough_ci.damage == 0
        state = _fire_when_played(state, chewie_ci)
        # No legal target -> optional trigger auto-declines (no accept prompt).
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestVal:
    def test_SHD_58_bounty_collector_deals_3(self, repo):
        """SHD_58 — Bounty: the collector (opponent of the dying unit's controller)
        deals 3 damage to a unit of their choice."""
        from swu.engine.actions import (
            legal_actions, apply, SelectDamageTarget,
        )
        val = _get_card(repo, "SHD", "58")
        victim = _get_card(repo, "SOR", "46")
        state = _make_state()
        val_ci = _place(state, "P0", val, "ground")
        victim_ci = _place(state, "P1", victim, "ground")  # the only surviving unit

        # P0 has no other unit, so the "give 2 Experience" WhenDefeated fizzles;
        # only the Bounty remains, decided by the collector P1.
        state = _defeat_and_fire(state, val_ci, "P0")
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage"
        assert top.deciding_player_id == "P1", "collector decides the Bounty"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectDamageTarget)
                    and a.target_id == victim_ci.instance_id)
        state = apply(state, pick)
        _, hit = state.find_instance(victim_ci.instance_id)
        assert hit.damage == 3

    def test_SHD_58_when_defeated_gives_2_experience(self, repo):
        """SHD_58 — the separate When Defeated gives 2 Experience to a friendly unit
        of the OWNER."""
        val = _get_card(repo, "SHD", "58")
        ally = _get_card(repo, "SOR", "46")
        from swu.engine.actions import legal_actions, apply, ChooseTarget, FinishSelectDamage
        state = _make_state()
        val_ci = _place(state, "P0", val, "ground")
        ally_ci = _place(state, "P0", ally, "ground")  # owner's friendly unit
        state = _defeat_and_fire(state, val_ci, "P0")
        # Resolve any pending Bounty select_damage first (collector may finish w/o dealing).
        for _ in range(4):
            if not state.pending_decisions:
                break
            top = state.pending_decisions[-1]
            if top.kind == "select_damage":
                state = apply(state, FinishSelectDamage())
            elif top.kind == "resolve_effects":
                choose = next(a for a in legal_actions(state)
                              if isinstance(a, ChooseTarget) and a.target_id == ally_ci.instance_id)
                state = apply(state, choose)
            else:
                break
        _, ally_hit = state.find_instance(ally_ci.instance_id)
        assert _experience_count(ally_hit) == 2


class TestRivalsFall:
    def test_SHD_79_defeats_a_unit(self, repo):
        """SHD_79 — Rival's Fall (Event): Defeat a unit."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        rf = _get_card(repo, "SHD", "79")
        target = _get_card(repo, "SOR", "46")
        state = _make_state()
        target_ci = _place(state, "P1", target, "ground")
        rf_ci = CardInstance(instance_id=f"rf_{uuid.uuid4().hex[:6]}",
                             card_def=rf, owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(rf_ci)
        _give_resources(state, "P0", 9, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == rf_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == target_ci.instance_id)
        state = apply(state, choose)
        assert _find_instance(state, target_ci.instance_id) is None


class TestSalaciousCrumbShd80:
    def test_SHD_80_when_played_heals_base(self, repo):
        """SHD_80 — When Played: heal 1 damage from your base."""
        crumb = _get_card(repo, "SHD", "80")
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 3
        crumb_ci = _place(state, "P0", crumb, "ground")
        state = _fire_when_played(state, crumb_ci)
        assert state.player_by_id("P0").base_instance.damage == 2

    def test_SHD_80_action_returns_self_and_deals_1(self, repo):
        """SHD_80 — Action [Exhaust, return this unit to hand]: deal 1 to a ground
        unit."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        crumb = _get_card(repo, "SHD", "80")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        crumb_ci = _place(state, "P0", crumb, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        use = next((a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == crumb_ci.instance_id), None)
        assert use is not None, "Action ability available"
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 1
        # Crumb bounced back to its owner's hand.
        assert _find_instance(state, crumb_ci.instance_id) is None
        assert any(c.instance_id == crumb_ci.instance_id
                   for c in state.player_by_id("P0").hand)


class TestJabbasRancor:
    def test_SHD_91_when_played_deals_3_to_friendly_and_enemy(self, repo):
        """SHD_91 — When Played: deal 3 to another friendly ground unit and 3 to an
        enemy ground unit."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        rancor = _get_card(repo, "SHD", "91")
        friend = _get_card(repo, "SOR", "46")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        rancor_ci = _place(state, "P0", rancor, "ground")
        friend_ci = _place(state, "P0", friend, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_when_played(state, rancor_ci)
        # Two mandatory targeted DealDamage effects, resolved in order.
        for want in (friend_ci.instance_id, enemy_ci.instance_id):
            choose = next((a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget) and a.target_id == want), None)
            if choose is not None:
                state = apply(state, choose)
        _, f = state.find_instance(friend_ci.instance_id)
        _, e = state.find_instance(enemy_ci.instance_id)
        assert f.damage == 3 and e.damage == 3
        # Rancor itself ("another friendly") is untouched.
        _, r = state.find_instance(rancor_ci.instance_id)
        assert r.damage == 0

    def test_SHD_91_cost_reduction_gated_on_controlling_jabba(self, repo):
        """SHD_91 — costs 1 less while the controller controls Jabba the Hutt: the
        CostReduction's condition is false without Jabba, true with a Jabba unit."""
        from swu.abilities.registry import ConditionCheck, Condition
        state = _make_state()
        rancor_ci = _place(state, "P0", _get_card(repo, "SHD", "91"), "ground")
        cond = ConditionCheck(Condition.CONTROLLER_CONTROLS_NAMED, param="Jabba the Hutt")
        assert cond.evaluate(state, rancor_ci) is False
        _place(state, "P0", _get_card(repo, "SOR", "181"), "ground")  # Jabba the Hutt (Unit)
        assert cond.evaluate(state, rancor_ci) is True


class TestEnterprisingLackeys:
    def test_SHD_107_when_defeated_becomes_resource(self, repo):
        """SHD_107 — When Defeated: may defeat a friendly resource, then put this
        unit into play as a resource (real defeat path honours the relocation)."""
        from swu.abilities.resolver import _apply_deal_damage
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        lackeys = _get_card(repo, "SHD", "107")
        state = _make_state()
        lackeys_ci = _place(state, "P0", lackeys, "ground")
        _give_resources(state, "P0", 1, repo)
        sac_id = state.player_by_id("P0").resources[0].instance_id

        state = _apply_deal_damage(state, lackeys_ci.instance_id, lackeys.hp)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # The no-target CustomEffect resolves via AutoResolveEffects.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AutoResolveEffects)))

        ps = state.player_by_id("P0")
        res_ids = {r.instance_id for r in ps.resources}
        assert lackeys_ci.instance_id in res_ids, "unit relocated into resources"
        assert sac_id not in res_ids, "the sacrificed resource is gone"
        assert any(c.instance_id == sac_id for c in ps.discard), "sac'd resource in discard"
        assert all(c.instance_id != lackeys_ci.instance_id for c in ps.discard), \
            "the unit did NOT also home in discard"
        assert _find_instance(state, lackeys_ci.instance_id) is None, "not in an arena"


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:03 — Direct damage & removal
# (SHD_142 Pre Vizsla and SHD_144 Give In to Your Anger are escalations — unencoded)
# ══════════════════════════════════════════════════════════════════════════════

class TestScanningOfficer:
    def test_SHD_114_defeats_smuggle_resources_and_ramps(self, repo):
        """SHD_114 — When Played: reveal 3 enemy resources; defeat each with Smuggle
        and its controller ramps for each defeated."""
        from swu.engine.state import CardInstance, Zone
        import uuid
        officer = _get_card(repo, "SHD", "114")
        smug = _get_card(repo, "SHD", "50")   # has Smuggle
        plain = _get_card(repo, "SOR", "46")  # no Smuggle
        state = _make_state()
        officer_ci = _place(state, "P0", officer, "ground")
        p1 = state.player_by_id("P1")
        smug_res = CardInstance(f"sr_{uuid.uuid4().hex[:5]}", smug, "P1", Zone.RESOURCES)
        smug_res.face_down = True
        plain_res = CardInstance(f"pr_{uuid.uuid4().hex[:5]}", plain, "P1", Zone.RESOURCES)
        plain_res.face_down = True
        p1.resources.extend([smug_res, plain_res])
        p1.deck.append(CardInstance("p1d0", plain, "P1", Zone.DECK))
        res_before = len(p1.resources)

        state = _fire_when_played(state, officer_ci)
        p1 = state.player_by_id("P1")
        res_ids = {r.instance_id for r in p1.resources}
        assert smug_res.instance_id not in res_ids, "Smuggle resource defeated"
        assert plain_res.instance_id in res_ids, "non-Smuggle resource untouched"
        assert any(c.instance_id == smug_res.instance_id for c in p1.discard)
        # Net: -1 (smug defeated) +1 (ramp from deck) = same count.
        assert len(p1.resources) == res_before
        assert len(p1.deck) == 0, "controller ramped one card from deck"


class TestDengar:
    def test_SHD_133_deals_1_to_upgraded_unit(self, repo):
        """SHD_133 — When you play an upgrade on a unit: may deal 1 damage to that
        unit."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, AcceptTrigger, AutoResolveEffects
        import uuid
        dengar = _get_card(repo, "SHD", "133")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SOR", "69")  # Resilient — plain stat upgrade
        state = _make_state()
        _place(state, "P0", dengar, "ground")
        host_ci = _place(state, "P0", host, "ground")
        up_ci = CardInstance(f"up_{uuid.uuid4().hex[:5]}", upgrade, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(up_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == up_ci.instance_id
                    and getattr(a, "upgrade_target_id", None) == host_ci.instance_id)
        state = apply(state, play)
        # Dengar's optional observer offers accept.
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AutoResolveEffects)))
        _, hit = state.find_instance(host_ci.instance_id)
        assert hit.damage == 1


class TestKrrsantan:
    def test_SHD_139_on_attack_deals_damage_equal_to_own_damage(self, repo):
        """SHD_139 — On Attack: may deal 1 damage to a ground unit for each damage on
        this unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        krr = _get_card(repo, "SHD", "139")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        krr_ci = _place(state, "P0", krr, "ground")
        krr_ci.damage = 3
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_on_attack(state, krr_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 3

    def test_SHD_139_ready_gated_on_enemy_bounty(self, repo):
        """SHD_139 — When Played: readies self only when an enemy unit has a Bounty."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        krr = _get_card(repo, "SHD", "139")
        bounty_unit = _get_card(repo, "SHD", "58")  # Val — carries a Bounty
        plain = _get_card(repo, "SOR", "46")
        # No enemy bounty -> trigger not offered.
        state = _make_state()
        krr_ci = _place(state, "P0", krr, "ground")
        krr_ci.exhausted = True
        _place(state, "P1", plain, "ground")
        state = _fire_when_played(state, krr_ci)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        # With an enemy Bounty unit -> may ready.
        state = _make_state()
        krr_ci = _place(state, "P0", krr, "ground")
        krr_ci.exhausted = True
        _place(state, "P1", bounty_unit, "ground")
        state = _fire_when_played(state, krr_ci)
        from swu.engine.actions import AutoResolveEffects
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
        _, hit = state.find_instance(krr_ci.instance_id)
        assert hit.exhausted is False, "Krrsantan readied"


class TestRuthlessness:
    def test_SHD_143_deals_2_to_enemy_base_on_attack_defeat(self, repo):
        """SHD_143 — granted: When this unit attacks and defeats a unit, deal 2 to
        the defending player's base."""
        from swu.engine.state import CardInstance, Zone
        from swu.abilities.resolver import fire_triggered_abilities
        import uuid
        ruth = _get_card(repo, "SHD", "143")
        host = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        ruth_ci = CardInstance(f"ru_{uuid.uuid4().hex[:5]}", ruth, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(ruth_ci)
        assert state.player_by_id("P1").base_instance.damage == 0

        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": host_ci.instance_id})
        assert state.player_by_id("P1").base_instance.damage == 2


class TestKoskaReeves:
    def test_SHD_150_on_attack_deals_2_when_upgraded(self, repo):
        """SHD_150 — On Attack: if upgraded, may deal 2 to a ground unit."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        import uuid
        koska = _get_card(repo, "SHD", "150")
        upgrade = _get_card(repo, "SOR", "69")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        koska_ci = _place(state, "P0", koska, "ground")
        up_ci = CardInstance(f"up_{uuid.uuid4().hex[:5]}", upgrade, "P0", Zone.GROUND_ARENA)
        koska_ci.attached_upgrades.append(up_ci)
        enemy_ci = _place(state, "P1", enemy, "ground")

        state = _fire_on_attack(state, koska_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2

    def test_SHD_150_no_trigger_when_not_upgraded(self, repo):
        """SHD_150 — no trigger offered while Koska carries no upgrade."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        koska = _get_card(repo, "SHD", "150")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        koska_ci = _place(state, "P0", koska, "ground")
        _place(state, "P1", enemy, "ground")
        state = _fire_on_attack(state, koska_ci)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:04 — Direct damage & removal
# (SHD_163 Migs Mayfeld, SHD_170 IG-11, SHD_172 Krayt Dragon are escalations)
# ══════════════════════════════════════════════════════════════════════════════

class TestWildRancor:
    def test_SHD_158_when_played_hits_each_other_ground_unit(self, repo):
        """SHD_158 — When Played: deal 2 to each OTHER ground unit (not itself, not
        space)."""
        rancor = _get_card(repo, "SHD", "158")
        other = _get_card(repo, "SOR", "46")
        state = _make_state()
        rancor_ci = _place(state, "P0", rancor, "ground")
        friendly_ci = _place(state, "P0", other, "ground")
        enemy_ci = _place(state, "P1", other, "ground")
        space_ci = _place(state, "P1", other, "space")

        state = _fire_when_played(state, rancor_ci)
        assert not state.pending_decisions, "EACH_IN_PLAY auto-targets, no prompt"
        _, f = state.find_instance(friendly_ci.instance_id)
        _, e = state.find_instance(enemy_ci.instance_id)
        _, sp = state.find_instance(space_ci.instance_id)
        _, r = state.find_instance(rancor_ci.instance_id)
        assert f.damage == 2 and e.damage == 2
        assert sp.damage == 0, "space unit untouched"
        assert r.damage == 0, "the rancor itself untouched"


class TestWantedInsurgents:
    def test_SHD_167_bounty_collector_deals_2(self, repo):
        """SHD_167 — Bounty: the collector deals 2 damage to a unit of their choice."""
        from swu.engine.actions import legal_actions, apply, SelectDamageTarget
        wi = _get_card(repo, "SHD", "167")
        victim = _get_card(repo, "SOR", "46")
        state = _make_state()
        wi_ci = _place(state, "P0", wi, "ground")
        victim_ci = _place(state, "P1", victim, "ground")

        state = _defeat_and_fire(state, wi_ci, "P0")
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage" and top.deciding_player_id == "P1"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectDamageTarget)
                    and a.target_id == victim_ci.instance_id)
        state = apply(state, pick)
        _, hit = state.find_instance(victim_ci.instance_id)
        assert hit.damage == 2


class TestCovetousRivals:
    def test_SHD_171_when_played_deals_2_to_bounty_unit(self, repo):
        """SHD_171 — When Played: may deal 2 to a unit with a Bounty."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        rivals = _get_card(repo, "SHD", "171")
        bounty_unit = _get_card(repo, "SHD", "58")  # Val — carries a Bounty
        plain = _get_card(repo, "SOR", "46")
        state = _make_state()
        rivals_ci = _place(state, "P0", rivals, "ground")
        val_ci = _place(state, "P1", bounty_unit, "ground")
        _place(state, "P1", plain, "ground")  # no bounty -> not a legal target

        state = _fire_when_played(state, rivals_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        targets = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        # Only the Bounty-carrying unit is a legal target.
        assert all(a.target_id == val_ci.instance_id for a in targets if a.target_id)
        choose = next(a for a in targets if a.target_id == val_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(val_ci.instance_id)
        assert hit.damage == 2

    def test_SHD_171_no_trigger_without_bounty_unit(self, repo):
        """SHD_171 — optional trigger auto-declines with no Bounty unit in play."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        rivals = _get_card(repo, "SHD", "171")
        plain = _get_card(repo, "SOR", "46")
        state = _make_state()
        rivals_ci = _place(state, "P0", rivals, "ground")
        _place(state, "P1", plain, "ground")
        state = _fire_when_played(state, rivals_ci)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestGuildTarget:
    def test_SHD_173_bounty_deals_2_to_hosts_base(self, repo):
        """SHD_173 — granted Bounty: when the host dies, the collector (P0, who owns
        the upgrade) deals 2 to the host owner's (P1's) base (host non-unique)."""
        from swu.engine.actions import _defeat_unit
        gt = _get_card(repo, "SHD", "173")
        host = _get_card(repo, "SOR", "46")  # Consular Security Force — non-unique
        state = _make_state()
        host_ci = _place(state, "P1", host, "ground")   # P1 controls the host
        _attach_bounty_upgrade(state, host_ci, gt, "P0")  # P0 owns Guild Target
        assert state.player_by_id("P1").base_instance.damage == 0

        _defeat_unit(state, state.player_by_id("P1"), host_ci)
        assert state.player_by_id("P1").base_instance.damage == 2, \
            "host owner's base took 2 (host not unique)"


# ══════════════════════════════════════════════════════════════════════════════
# shd-set:03 / :04 / :05 — Direct damage & removal (continued)
# ══════════════════════════════════════════════════════════════════════════════

class TestIG11:
    def test_SHD_170_on_attack_deals_3_to_damaged_ground_unit(self, repo):
        """SHD_170 — On Attack: may deal 3 to a damaged ground unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        ig = _get_card(repo, "SHD", "170")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        ig_ci = _place(state, "P0", ig, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.damage = 1  # must be damaged to be a legal target

        state = _fire_on_attack(state, ig_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 4  # 1 + 3


class TestKraytDragon:
    def test_SHD_172_deals_opponent_card_cost_to_their_base(self, repo):
        """SHD_172 — When an opponent plays a card: may deal damage equal to that
        card's cost to their base or a ground unit they control."""
        from swu.engine.events import CardPlayed
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        krayt = _get_card(repo, "SHD", "172")
        played = _get_card(repo, "SOR", "46")  # a P1 unit; its printed cost is the payoff
        state = _make_state()
        _place(state, "P0", krayt, "ground")
        played_ci = _place(state, "P1", played, "ground")
        cost = played.cost
        assert cost and cost > 0
        base = state.player_by_id("P1").base_instance

        evt = CardPlayed(player_id="P1", instance_id=played_ci.instance_id,
                         card_name=played.display_name, cost_paid=cost)
        state.event_log.append(evt)
        state = fire_triggered_abilities(state, evt, after_all_player_idx=1, event_ctx={})
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == base.instance_id)
        state = apply(state, choose)
        assert state.player_by_id("P1").base_instance.damage == cost


class TestRuthlessAssassin:
    def test_SHD_235_when_played_deals_2_to_friendly_unit(self, repo):
        """SHD_235 — When Played: deal 2 damage to a friendly unit (mandatory drawback)."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        ra = _get_card(repo, "SHD", "235")
        buddy = _get_card(repo, "SOR", "46")
        state = _make_state()
        ra_ci = _place(state, "P0", ra, "ground")
        buddy_ci = _place(state, "P0", buddy, "ground")

        state = _fire_when_played(state, ra_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == buddy_ci.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(buddy_ci.instance_id)
        assert hit.damage == 2


class TestMaKlounkee:
    def test_SHD_229_returns_underworld_unit_then_deals_3(self, repo):
        """SHD_229 — Return a friendly non-leader Underworld unit; if you do, deal 3."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        mk = _get_card(repo, "SHD", "229")
        uw = _get_card(repo, "SHD", "235")  # Ruthless Assassin — Underworld, non-leader
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        uw_ci = _place(state, "P0", uw, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        mk_ci = CardInstance(f"mk_{uuid.uuid4().hex[:6]}", mk, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(mk_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == mk_ci.instance_id)
        state = apply(state, play)
        # Stage 1: return the Underworld unit.
        ret = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == uw_ci.instance_id)
        state = apply(state, ret)
        # Stage 2: deal 3 to a unit.
        dmg = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, dmg)
        assert _find_instance(state, uw_ci.instance_id) is None, "Underworld unit left play"
        assert any(c.instance_id == uw_ci.instance_id
                   for c in state.player_by_id("P0").hand), "returned to owner's hand"
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 3

    def test_SHD_229_no_underworld_unit_deals_no_damage(self, repo):
        """SHD_229 — "If you do" binding: with no returnable Underworld unit, the
        follow-up damage does not happen (requires_prior_target gate)."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        mk = _get_card(repo, "SHD", "229")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        enemy_ci = _place(state, "P1", enemy, "ground")
        mk_ci = CardInstance(f"mk_{uuid.uuid4().hex[:6]}", mk, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(mk_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == mk_ci.instance_id)
        state = apply(state, play)
        # No ChooseTarget for the enemy unit should ever be offered (event fizzled).
        assert not any(isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id
                       for a in legal_actions(state))
        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 0


class TestVambraceFlamethrower:
    def test_SHD_177_granted_on_attack_distributes_3_among_enemy_ground(self, repo):
        """SHD_177 — granted: On Attack, may deal 3 divided among enemy ground units."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        AutoResolveEffects, AssignDamage)
        import uuid
        vf = _get_card(repo, "SHD", "177")
        host = _get_card(repo, "SOR", "46")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        vf_ci = CardInstance(f"vf_{uuid.uuid4().hex[:5]}", vf, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(vf_ci)
        e1 = _place(state, "P1", enemy, "ground")

        state = _fire_on_attack(state, host_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
        for _ in range(3):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, AssignDamage) and a.target_id == e1.instance_id)
            state = apply(state, act)
        _, hit = state.find_instance(e1.instance_id)
        assert hit.damage == 3


class TestDetentionBlockRescue:
    def test_SHD_180_deals_3_normally_and_6_when_guarding(self, repo):
        """SHD_180 — Deal 3 to a unit; 6 if it is guarding captured cards."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        import uuid
        dbr = _get_card(repo, "SHD", "180")
        target = _get_card(repo, "SOR", "46")
        captive = _get_card(repo, "SOR", "128")

        def _play_at(guarding):
            state = _make_state()
            tgt_ci = _place(state, "P1", target, "ground")
            if guarding:
                cap = CardInstance(f"cap_{uuid.uuid4().hex[:5]}", captive, "P0",
                                   Zone.CAPTURE_PILE)
                cap.captured_by = tgt_ci.instance_id
                state.player_by_id("P1").capture_pile.append(cap)
            dbr_ci = CardInstance(f"dbr_{uuid.uuid4().hex[:5]}", dbr, "P0", Zone.HAND)
            state.player_by_id("P0").hand.append(dbr_ci)
            _give_resources(state, "P0", 5, repo)
            play = next(a for a in legal_actions(state)
                        if isinstance(a, PlayCard) and a.instance_id == dbr_ci.instance_id)
            state = apply(state, play)
            choose = next(a for a in legal_actions(state)
                          if isinstance(a, ChooseTarget) and a.target_id == tgt_ci.instance_id)
            state = apply(state, choose)
            return state, tgt_ci

        state, tgt = _play_at(guarding=False)
        _, hit = state.find_instance(tgt.instance_id)
        assert hit.damage == 3
        state, tgt = _play_at(guarding=True)
        _, hit = state.find_instance(tgt.instance_id)
        assert hit.damage == 6


class TestJetpack:
    def test_SHD_225_gives_shield_defeated_at_regroup(self, repo):
        """SHD_225 — When Played: give a Shield to attached unit; defeat that token at
        the start of the regroup phase."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _enter_regroup
        import uuid
        jp = _get_card(repo, "SHD", "225")
        host = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        jp_ci = CardInstance(f"jp_{uuid.uuid4().hex[:5]}", jp, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(jp_ci)

        state = _fire_upgrade_played(state, jp_ci, host_ci)
        assert _shield_count(host_ci) == 1, "host gained a Shield token"
        token = next(u for u in host_ci.attached_upgrades
                     if u.card_def.name == "Shield")
        assert token.defeat_at_regroup is True
        # The regroup sweep defeats (detaches) the flagged token.
        _enter_regroup(state)
        assert _shield_count(host_ci) == 0, "Shield token defeated at regroup"


class TestToroCalican:
    def test_SHD_239_readies_and_pings_on_bounty_hunter_play_once_per_round(self, repo):
        """SHD_239 — When you play another Bounty Hunter unit: may deal 1 to it and
        ready this unit; only once each round."""
        from swu.engine.events import CardPlayed
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        toro = _get_card(repo, "SHD", "239")
        bh = _get_card(repo, "SHD", "235")  # Ruthless Assassin — Bounty Hunter unit
        state = _make_state()
        toro_ci = _place(state, "P0", toro, "ground")
        toro_ci.exhausted = True
        bh_ci = _place(state, "P0", bh, "ground")

        def _fire_play(unit_ci):
            evt = CardPlayed(player_id="P0", instance_id=unit_ci.instance_id,
                             card_name=unit_ci.card_def.display_name,
                             cost_paid=unit_ci.card_def.cost)
            state.event_log.append(evt)
            return fire_triggered_abilities(
                state, evt, after_all_player_idx=1,
                event_ctx={"played_card_id": unit_ci.instance_id})

        state = _fire_play(bh_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
        _, played = state.find_instance(bh_ci.instance_id)
        assert played.damage == 1, "dealt 1 to the played Bounty Hunter"
        _, toro_now = state.find_instance(toro_ci.instance_id)
        assert toro_now.exhausted is False, "Toro readied"

        # Second Bounty Hunter play the same round: the once-per-round trigger is gone.
        toro_now.exhausted = True
        bh2_ci = _place(state, "P0", _get_card(repo, "SHD", "170"), "ground")  # IG-11 (BH)
        state = _fire_play(bh2_ci)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "once-per-round: not offered again"


class TestLadyProxima:
    def test_SHD_255_underworld_play_may_deal_1_to_a_base(self, repo):
        """SHD_255 — When you play another Underworld card: may deal 1 to a base."""
        from swu.engine.events import CardPlayed
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, DeclineTrigger, ChooseTarget)
        proxima = _get_card(repo, "SHD", "255")
        uw = _get_card(repo, "SHD", "235")  # Ruthless Assassin — Underworld unit
        state = _make_state()
        proxima_ci = _place(state, "P0", proxima, "ground")
        uw_ci = _place(state, "P0", uw, "ground")
        enemy_base = state.player_by_id("P1").base_instance
        assert enemy_base.damage == 0

        evt = CardPlayed(player_id="P0", instance_id=uw_ci.instance_id,
                         card_name=uw_ci.card_def.display_name,
                         cost_paid=uw_ci.card_def.cost)
        state.event_log.append(evt)
        state = fire_triggered_abilities(
            state, evt, after_all_player_idx=1,
            event_ctx={"played_card_id": uw_ci.instance_id})

        # Optional "you may": both accept and decline offered.
        assert any(isinstance(a, DeclineTrigger) for a in legal_actions(state))
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy_base.instance_id)
        state = apply(state, choose)
        assert state.player_by_id("P1").base_instance.damage == 1


class TestHylobonEnforcer:
    def test_SHD_27_bounty_opponent_draws(self, repo):
        """SHD_27 — Bounty: when this P0 unit is defeated, the collector (P1)
        draws a card (Grit is the keyword engine's; resolves inline)."""
        from swu.engine.state import CardInstance, Zone
        hylobon = _get_card(repo, "SHD", "27")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        h_ci = _place(state, "P0", hylobon, "ground")
        state.player_by_id("P1").deck.append(
            CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        state.player_by_id("P0").deck.append(
            CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = _fire_when_defeated(state, h_ci)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").deck) == 0, "collector (P1) drew"
        assert len(state.player_by_id("P1").hand) == p1_hand_before + 1
        assert len(state.player_by_id("P0").deck) == 1, "owner (P0) did not draw"


class TestPalpatinesReturn:
    """SHD_94 — play a unit from your discard; it costs 6 less, or 8 less if it is
    a Force unit.  Resource amounts are derived from ``_effective_cost`` so the
    assertions are robust to the aspectless-base penalty in ``_make_state``."""

    def _play_event(self, state, ev_ci):
        from swu.engine.actions import legal_actions, apply, PlayCard
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ev_ci.instance_id)
        return apply(state, play)

    def _setup(self, repo, unit_num, unit_set, resources_after_event):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _effective_cost
        import uuid
        event = _get_card(repo, "SHD", "94")
        unit = _get_card(repo, unit_set, unit_num)
        state = _make_state()
        ev_ci = CardInstance(f"ev_{uuid.uuid4().hex[:6]}", event, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ev_ci)
        u_ci = _put_in_discard(state, "P0", unit)
        ps0 = state.player_by_id("P0")
        _give_resources(
            state, "P0",
            _effective_cost(event, ps0) + resources_after_event, repo)
        return state, ev_ci, u_ci

    def test_SHD_94_force_unit_gets_8_off(self, repo):
        """A Force unit (Count Dooku SOR_38) needs exactly ``eff-8`` after the
        event — proving the −8 (not −6) reduction; playing it pays exactly, 0 left."""
        from swu.engine.actions import (
            legal_actions, apply, PlayFromHand, _effective_cost)
        # First measure the Force unit's effective cost against an aspectless base.
        dooku = _get_card(repo, "SOR", "38")
        probe = _make_state()
        eff = _effective_cost(dooku, probe.player_by_id("P0"))
        need = max(0, eff - 8)

        state, ev_ci, u_ci = self._setup(repo, "38", "SOR", need)
        state = self._play_event(state, ev_ci)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        plays = [a for a in legal_actions(state)
                 if isinstance(a, PlayFromHand) and a.instance_id == u_ci.instance_id]
        assert plays, "Force unit playable at eff-8"
        before = state.player_by_id("P0").available_resources
        assert before == need
        state = apply(state, plays[0])
        ps0 = state.player_by_id("P0")
        assert ps0.available_resources == 0, "paid exactly eff-8"
        assert any(ci.instance_id == u_ci.instance_id
                   for ci in ps0.ground_arena + ps0.space_arena)
        assert all(ci.instance_id != u_ci.instance_id for ci in ps0.discard)

    def test_SHD_94_non_force_gets_only_6_off(self, repo):
        """A non-Force unit (Han Solo SOR_198) given only ``eff-8`` worth of
        resources is NOT playable — proving it gets −6, not −8."""
        from swu.engine.actions import legal_actions, PlayFromHand, _effective_cost
        han = _get_card(repo, "SOR", "198")
        probe = _make_state()
        eff = _effective_cost(han, probe.player_by_id("P0"))
        state, ev_ci, u_ci = self._setup(repo, "198", "SOR", max(0, eff - 8))
        state = self._play_event(state, ev_ci)
        # eff-8 resources can't cover the true eff-6 cost → no candidate → fizzle.
        assert not any(
            isinstance(a, PlayFromHand) and a.instance_id == u_ci.instance_id
            for a in legal_actions(state))


class TestGuavianAntagonizer:
    def test_SHD_134_bounty_opponent_draws(self, repo):
        """SHD_134 — Bounty: when this P0 unit is defeated, the collector (P1)
        draws a card (Saboteur is the keyword engine's; resolves inline)."""
        from swu.engine.state import CardInstance, Zone
        guav = _get_card(repo, "SHD", "134")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        g_ci = _place(state, "P0", guav, "ground")
        state.player_by_id("P1").deck.append(
            CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        state.player_by_id("P0").deck.append(
            CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = _fire_when_defeated(state, g_ci)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").deck) == 0, "collector (P1) drew"
        assert len(state.player_by_id("P1").hand) == p1_hand_before + 1
        assert len(state.player_by_id("P0").deck) == 1, "owner (P0) did not draw"


class TestEnforcedLoyalty:
    def _play(self, state, repo, ev_ci):
        from swu.engine.actions import legal_actions, apply, PlayCard
        _give_resources(state, "P0", 6, repo)  # cost 2 + aspect-penalty headroom
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ev_ci.instance_id)
        return apply(state, play)

    def test_SHD_108_defeats_friendly_then_draws_2(self, repo):
        """SHD_108 — Defeat a friendly unit; if you do, draw 2."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        import uuid
        event = _get_card(repo, "SHD", "108")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        f_ci = _place(state, "P0", filler, "ground")
        ev_ci = CardInstance(f"ev_{uuid.uuid4().hex[:6]}", event, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ev_ci)
        for i in range(3):
            state.player_by_id("P0").deck.append(
                CardInstance(f"p0_deck_{i}", filler, "P0", Zone.DECK))

        state = self._play(state, repo, ev_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == f_ci.instance_id)
        state = apply(state, choose)
        ps0 = state.player_by_id("P0")
        assert all(u.instance_id != f_ci.instance_id for u in ps0.ground_arena), \
            "friendly unit defeated"
        assert any(c.instance_id == f_ci.instance_id for c in ps0.discard)
        assert len(ps0.deck) == 1, "drew 2 (3 -> 1)"
        assert not state.pending_decisions

    def test_SHD_108_no_friendly_unit_no_draw(self, repo):
        """With no friendly unit to defeat, the event fizzles — no free draw 2."""
        from swu.engine.state import CardInstance, Zone
        import uuid
        event = _get_card(repo, "SHD", "108")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        ev_ci = CardInstance(f"ev_{uuid.uuid4().hex[:6]}", event, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ev_ci)
        for i in range(3):
            state.player_by_id("P0").deck.append(
                CardInstance(f"p0_deck_{i}", filler, "P0", Zone.DECK))

        state = self._play(state, repo, ev_ci)
        assert state.player_by_id("P0").deck and len(
            state.player_by_id("P0").deck) == 3, "no defeat ⇒ no draw"


# ── shd-set:03 framework session: the two escalation cards ────────────────────

class TestPreVizsla:
    """SHD_142 — When Played/On Attack: You may pay the cost of an upgrade attached
    to another non-Vehicle unit; take control of it and attach to this unit, else
    defeat it (the pay_and_steal_upgrade decision kind)."""

    def test_SHD_142_when_played_pays_and_takes_control_of_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply
        pre = _get_card(repo, "SHD", "142")
        host_def = _get_card(repo, "SOR", "46")       # non-Vehicle enemy host
        upg_def = _get_card(repo, "SHD", "143")        # Ruthlessness, cost 1, no attach restr
        state = _make_state()
        pv = _place(state, "P0", pre, "ground")
        enemy = _place(state, "P1", host_def, "ground")
        up = _attach_upgrade_directly(state, enemy, upg_def, "P1")
        _give_resources(state, "P0", 4, repo)
        before = state.player_by_id("P0").available_resources

        state = _fire_when_played(state, pv)
        assert state.pending_decisions[-1].kind == "pay_and_steal_upgrade"
        steal = next(a for a in legal_actions(state)
                     if type(a).__name__ == "StealUpgrade"
                     and a.upgrade_id == up.instance_id)
        state = apply(state, steal)

        assert not state.pending_decisions
        _, pv_now = state.find_instance(pv.instance_id)
        _, enemy_now = state.find_instance(enemy.instance_id)
        assert any(u.instance_id == up.instance_id for u in pv_now.attached_upgrades), \
            "the stolen upgrade is now on Pre Vizsla"
        assert all(u.instance_id != up.instance_id for u in enemy_now.attached_upgrades)
        # Paid the upgrade's printed cost (1).
        assert state.player_by_id("P0").available_resources == before - 1

    def test_SHD_142_defeats_upgrade_that_cannot_attach(self, repo):
        from swu.engine.actions import legal_actions, apply
        pre = _get_card(repo, "SHD", "142")
        host_def = _get_card(repo, "SOR", "46")       # non-Vehicle enemy host (candidate)
        upg_def = _get_card(repo, "LOF", "74")         # Bolstered Endurance: "Attach to a Force unit"
        state = _make_state()
        pv = _place(state, "P0", pre, "ground")
        enemy = _place(state, "P1", host_def, "ground")
        up = _attach_upgrade_directly(state, enemy, upg_def, "P1")
        _give_resources(state, "P0", 4, repo)
        before = state.player_by_id("P0").available_resources

        state = _fire_when_played(state, pv)
        steal = next(a for a in legal_actions(state)
                     if type(a).__name__ == "StealUpgrade")
        state = apply(state, steal)

        assert not state.pending_decisions
        _, pv_now = state.find_instance(pv.instance_id)
        # Pre Vizsla is not a Force unit → the upgrade can't attach → it is defeated.
        assert all(u.instance_id != up.instance_id for u in pv_now.attached_upgrades)
        assert any(c.instance_id == up.instance_id
                   for c in state.player_by_id("P1").discard), "defeated to owner's discard"
        assert state.player_by_id("P0").available_resources == before - 1, "cost still paid"

    def test_SHD_142_not_offered_when_unaffordable(self, repo):
        """No ready resources → the affordable-candidate set is empty → no decision
        is pushed (a clean no-op)."""
        pre = _get_card(repo, "SHD", "142")
        host_def = _get_card(repo, "SOR", "46")
        upg_def = _get_card(repo, "SHD", "143")        # cost 1
        state = _make_state()
        pv = _place(state, "P0", pre, "ground")
        enemy = _place(state, "P1", host_def, "ground")
        _attach_upgrade_directly(state, enemy, upg_def, "P1")
        # P0 has zero resources.
        state = _fire_when_played(state, pv)
        assert not state.pending_decisions


class TestGiveInToYourAnger:
    """SHD_144 — Deal 1 to an enemy unit; its controller's next action this phase
    must be an attack with that unit (a unit target if able)."""

    def test_SHD_144_compels_damaged_unit_to_attack_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        import uuid
        give_in = _get_card(repo, "SHD", "144")
        p0_body = _get_card(repo, "SOR", "46")         # a target for P1's forced attack
        p1_body = _get_card(repo, "SOR", "46")         # the compelled unit
        state = _make_state()
        p0_unit = _place(state, "P0", p0_body, "ground")
        p1_unit = _place(state, "P1", p1_body, "ground")
        gi_ci = CardInstance(f"gi_{uuid.uuid4().hex[:5]}", give_in, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(gi_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == gi_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == p1_unit.instance_id)
        state = apply(state, choose)

        # 1 damage landed and the compulsion is armed for P1.
        _, p1_now = state.find_instance(p1_unit.instance_id)
        assert p1_now.damage == 1
        assert state.active_player.player_id == "P1"

        legal = legal_actions(state)
        kinds = {type(a).__name__ for a in legal}
        assert kinds == {"AttackWithUnit"}, "P1 is restricted to attacking"
        assert all(a.attacker_id == p1_unit.instance_id for a in legal)
        # "must attack a unit, if able" — the base (defender None) is NOT offered.
        assert all(a.defender_id == p0_unit.instance_id for a in legal)

        # Taking the forced attack consumes the compulsion.
        state = apply(state, legal[0])
        assert state.game_memory.forced_attack is None

    def test_SHD_144_vacuous_when_unit_cannot_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        import uuid
        give_in = _get_card(repo, "SHD", "144")
        p1_body = _get_card(repo, "SOR", "46")
        state = _make_state()
        p1_unit = _place(state, "P1", p1_body, "ground")
        p1_unit.exhausted = True                       # can't attack → compulsion vacuous
        gi_ci = CardInstance(f"gi_{uuid.uuid4().hex[:5]}", give_in, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(gi_ci)
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == gi_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == p1_unit.instance_id)
        state = apply(state, choose)

        # The unit is unable to attack, so P1's normal actions are offered (Pass).
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert "Pass" in kinds


class TestMigsMayfeld:
    """SHD_163 — Migs Mayfeld: "When a player discards a card from their hand: You
    may deal 2 damage to a unit or base.  Use this ability only once each round."
    Exercises the new WhenPlayerDiscardsFromHand any-player discard observer +
    discard-only ledger + the shared SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE limiter."""

    def test_SHD_163_fires_on_opponent_discard_deals_2_and_marks_used(self, repo):
        """An OPPONENT's hand-discard offers Migs's optional trigger (proving it is
        ANY player, not just the controller); accepting deals 2 to a chosen unit and
        spends the once-per-round use."""
        from swu.engine import actions as A
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects,
        )
        migs = _get_card(repo, "SHD", "163")
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        migs_ci = _place(state, "P0", migs, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")

        # The OPPONENT (P1) discards from hand → record + drain the discard-only ledger.
        A.record_hand_discard(state, "P1")
        assert state.game_memory.hand_discards == ["P1"]
        state = A._fire_hand_discard_observers(state)

        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        for _ in range(6):
            if not state.pending_decisions:
                break
            auto = next((a for a in legal_actions(state)
                         if isinstance(a, AutoResolveEffects)), None)
            if auto is None:
                break
            state = apply(state, auto)

        _, hit = state.find_instance(enemy_ci.instance_id)
        assert hit.damage == 2
        assert f"{migs_ci.instance_id}:trig" in state.game_memory.activated_abilities_used_this_round

    def test_SHD_163_once_per_round_not_offered_again(self, repo):
        """After Migs's use is spent this round, a second discard offers no trigger
        (the SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE gate is closed)."""
        from swu.engine import actions as A
        from swu.engine.actions import legal_actions, AcceptTrigger
        migs = _get_card(repo, "SHD", "163")
        state = _make_state()
        migs_ci = _place(state, "P0", migs, "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        # Pre-spend Migs's once-per-round use, then a fresh discard must offer nothing.
        state.game_memory.activated_abilities_used_this_round.add(
            f"{migs_ci.instance_id}:trig")
        A.record_hand_discard(state, "P0")
        state = A._fire_hand_discard_observers(state)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_SHD_163_reveal_does_not_fire(self, repo):
        """A Disclose *reveal* (kind="reveal") is not a discard — it never records into
        the discard-only ledger, so Migs's trigger is not offered."""
        from swu.engine import actions as A
        from swu.engine.actions import legal_actions, AcceptTrigger
        migs = _get_card(repo, "SHD", "163")
        state = _make_state()
        _place(state, "P0", migs, "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        A.record_hand_discard(state, "P0", kind="reveal")
        assert state.game_memory.hand_discards == []          # reveal skips this ledger
        assert state.game_memory.hand_reveal_discards == ["P0"]  # but feeds Padmé's
        state = A._fire_hand_discard_observers(state)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── shd-set:07 framework session — SHD_1 Gar Saxon (AuraGrantedAbility seam) ──
class TestGarSaxon:
    """SHD_1 Gar Saxon — the +1/+0 aura on friendly *upgraded* units, and the
    deployed-side AuraGrantedAbility 'Each friendly upgraded unit gains: When
    Defeated: return an upgrade attached to it to its owner's hand.'"""

    def _attach_real_upgrade(self, state, repo, host_ci, owner_id="P0"):
        from swu.engine.state import CardInstance, Zone
        import uuid
        up = _get_card(repo, "SOR", "120")  # Academy Training (+2/+2, no abilities)
        up_ci = CardInstance(
            instance_id=f"{owner_id}_up_{uuid.uuid4().hex[:6]}",
            card_def=up, owner_id=owner_id, zone=Zone.GROUND_ARENA,
        )
        host_ci.attached_upgrades.append(up_ci)
        return up_ci

    def test_SHD_1_upgraded_aura_only_hits_upgraded_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        gar_ci = _place(state, "P0", _get_card(repo, "SHD", "1"))
        gar_ci.deployed = True

        upgraded = _place(state, "P0", _get_card(repo, "SOR", "46"))
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"))
        self._attach_real_upgrade(state, repo, upgraded)

        # Isolate Gar's +1 by toggling him in/out of play.
        up_with = compute_power(state, upgraded)
        plain_with = compute_power(state, plain)
        state.player_by_id("P0").ground_arena.remove(gar_ci)
        assert compute_power(state, upgraded) == up_with - 1, "aura should give the upgraded unit exactly +1"
        assert compute_power(state, plain) == plain_with, "a non-upgraded unit gets no aura"

    def test_SHD_1_granted_when_defeated_returns_upgrade(self, repo):
        from swu.engine.actions import legal_actions, _defeat_unit, SelectDiscardCard
        state = _make_state()
        gar_ci = _place(state, "P0", _get_card(repo, "SHD", "1"))
        gar_ci.deployed = True

        host_ci = _place(state, "P0", _get_card(repo, "SOR", "46"))
        up_ci = self._attach_real_upgrade(state, repo, host_ci)

        # Defeat the upgraded friendly unit → Gar's aura-granted 'When Defeated'
        # fires and offers returning the just-detached upgrade to its owner's hand.
        _defeat_unit(state, state.player_by_id("P0"), host_ci)
        assert state.pending_decisions, "the granted When-Defeated should push a decision"
        assert state.pending_decisions[-1].kind == "return_from_discard"
        sel = [a for a in legal_actions(state)
               if isinstance(a, SelectDiscardCard) and a.instance_id == up_ci.instance_id]
        assert sel, "the detached upgrade should be a return candidate"
        state = sel[0].apply(state)
        assert any(c.instance_id == up_ci.instance_id
                   for c in state.player_by_id("P0").hand), "upgrade returns to owner's hand"

    def test_SHD_1_no_grant_without_upgrades(self, repo):
        """A friendly unit with no upgrades has nothing to return — its defeat pushes
        no return_from_discard decision (the grant self-limits)."""
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        gar_ci = _place(state, "P0", _get_card(repo, "SHD", "1"))
        gar_ci.deployed = True
        host_ci = _place(state, "P0", _get_card(repo, "SOR", "46"))

        _defeat_unit(state, state.player_by_id("P0"), host_ci)
        assert not any(d.kind == "return_from_discard" for d in state.pending_decisions)


class TestHunter:
    """SHD_9 Hunter — the reveal_resource_ramp seam: reveal a resource that shares a
    name with a friendly unique unit → return it to hand and ramp the deck top.
    Undeployed = a gated Action [1 resource, Exhaust]; deployed = a gated (may) On
    Attack trigger."""

    def _add_resource(self, state, owner_id, card_def):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(
            instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:6]}",
            card_def=card_def, owner_id=owner_id, zone=Zone.RESOURCES,
        )
        ci.face_down = True
        state.player_by_id(owner_id).resources.append(ci)
        return ci

    def _add_deck_top(self, state, owner_id, card_def):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
            card_def=card_def, owner_id=owner_id, zone=Zone.DECK,
        )
        state.player_by_id(owner_id).deck.insert(0, ci)
        return ci

    def test_SHD_9_undeployed_reveal_returns_resource_and_ramps(self, repo):
        """The undeployed Action reveals the name-matching resource: it returns to
        its owner's hand and the deck top enters play as a resource."""
        from swu.engine.actions import legal_actions, apply, UseAbility, \
            RevealResourceForRamp, DeclineRevealResource
        r2 = _get_card(repo, "SOR", "236")  # R2-D2 — a unique unit
        state = _make_state()
        hunter_ci = _place_leader(state, "P0", _get_card(repo, "SHD", "9"))
        _place(state, "P0", r2)                 # the friendly unique unit
        _give_resources(state, "P0", 1, repo)   # pays the Action's 1-resource cost
        match_res = self._add_resource(state, "P0", r2)  # shares R2-D2's name
        deck_top = self._add_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == hunter_ci.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "reveal_resource_ramp"
        # A mandatory (paid) Action — no decline offered.
        assert not any(isinstance(a, DeclineRevealResource) for a in legal_actions(state))
        reveal = next(a for a in legal_actions(state)
                      if isinstance(a, RevealResourceForRamp)
                      and a.resource_id == match_res.instance_id)
        state = apply(state, reveal)

        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == match_res.instance_id for c in ps0.hand), \
            "the revealed resource returns to its owner's hand"
        assert all(r.instance_id != match_res.instance_id for r in ps0.resources)
        assert any(r.instance_id == deck_top.instance_id for r in ps0.resources), \
            "the deck top ramps into play as a resource"

    def test_SHD_9_undeployed_not_offered_without_name_match(self, repo):
        """With no friendly unique unit sharing a resource's name, the Action is not
        even legal (its 1-resource + Exhaust cost is never wasted)."""
        from swu.engine.actions import legal_actions, UseAbility
        r2 = _get_card(repo, "SOR", "236")
        state = _make_state()
        hunter_ci = _place_leader(state, "P0", _get_card(repo, "SHD", "9"))
        _give_resources(state, "P0", 1, repo)
        self._add_resource(state, "P0", r2)     # matching resource but NO R2-D2 unit
        assert not any(
            isinstance(a, UseAbility) and a.source_id == hunter_ci.instance_id
            for a in legal_actions(state))

    def test_SHD_9_deployed_on_attack_may_reveal_and_ramp(self, repo):
        """Deployed, On Attack offers the reveal as a 'may' (decline available); the
        reveal returns the resource and ramps."""
        from swu.engine.actions import legal_actions, apply, \
            RevealResourceForRamp, DeclineRevealResource
        r2 = _get_card(repo, "SOR", "236")
        state = _make_state()
        hunter_ci = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "9"))
        _place(state, "P0", r2)
        match_res = self._add_resource(state, "P0", r2)
        deck_top = self._add_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

        state = _fire_on_attack(state, hunter_ci)
        assert state.pending_decisions[-1].kind == "reveal_resource_ramp"
        assert any(isinstance(a, DeclineRevealResource) for a in legal_actions(state)), \
            "the deployed On Attack reveal is a 'may'"
        reveal = next(a for a in legal_actions(state)
                      if isinstance(a, RevealResourceForRamp)
                      and a.resource_id == match_res.instance_id)
        state = apply(state, reveal)

        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == match_res.instance_id for c in ps0.hand)
        assert any(r.instance_id == deck_top.instance_id for r in ps0.resources)

    def test_SHD_9_deployed_on_attack_not_collected_without_match(self, repo):
        """Deployed, with no name match the On Attack trigger is gated out — no
        reveal decision is pushed at all."""
        state = _make_state()
        hunter_ci = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "9"))
        # A matching resource but no R2-D2 unit in play -> no unique-name match.
        self._add_resource(state, "P0", _get_card(repo, "SOR", "236"))
        state = _fire_on_attack(state, hunter_ci)
        assert not any(d.kind == "reveal_resource_ramp" for d in state.pending_decisions)


class TestDoctorAphra:
    """SHD_15 Doctor Aphra — regroup self-mill (deployed-only), the +3/+0 while ≥5
    distinct discard costs (CONTROLLER_DISCARD_DISTINCT_COSTS_MIN), and the When
    Deployed choose-3-distinct-names-return-1-at-random (select_distinct_return_random)."""

    def _add_discard(self, state, owner_id, card_def):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(
            instance_id=f"{owner_id}_dis_{uuid.uuid4().hex[:6]}",
            card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD,
        )
        state.player_by_id(owner_id).discard.append(ci)
        return ci

    def _add_deck_top(self, state, owner_id, card_def):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
            card_def=card_def, owner_id=owner_id, zone=Zone.DECK,
        )
        state.player_by_id(owner_id).deck.insert(0, ci)
        return ci

    def _fire_regroup(self, state):
        from swu.engine.events import PhaseChanged
        from swu.abilities.resolver import fire_triggered_abilities
        evt = PhaseChanged(new_phase="REGROUP", round_number=state.round_number)
        state.event_log.append(evt)
        return fire_triggered_abilities(state, evt, after_all_player_idx=0)

    def test_SHD_15_regroup_mills_top_of_deck(self, repo):
        """Deployed Aphra: when the regroup phase starts, the deck top is milled."""
        state = _make_state()
        _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "15"))
        deck_top = self._add_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = self._fire_regroup(state)
        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == deck_top.instance_id for c in ps0.discard), \
            "the deck top is discarded when the regroup phase starts"
        assert all(c.instance_id != deck_top.instance_id for c in ps0.deck)

    def test_SHD_15_regroup_mill_only_while_deployed(self, repo):
        """An undeployed Aphra (in the base zone) does NOT mill — deployed_only."""
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SHD", "15"))
        deck_top = self._add_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = self._fire_regroup(state)
        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == deck_top.instance_id for c in ps0.deck), \
            "an undeployed leader's regroup trigger is not collected"
        assert not ps0.discard

    def test_SHD_15_buff_active_with_five_distinct_costs(self, repo):
        """+3/+0 while ≥5 distinct printed costs sit in the discard pile; the buff
        drops the moment a fifth distinct cost is missing."""
        from swu.engine.actions import compute_power
        state = _make_state()
        aphra = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "15"))
        base = compute_power(state, aphra)  # Aphra is 2/5 → base power 2
        # Four distinct costs (1, 2, 4, 5) → no buff.
        for setc, num in (("SOR", "236"), ("SOR", "139"), ("SOR", "46"), ("SOR", "116")):
            self._add_discard(state, "P0", _get_card(repo, setc, num))
        assert compute_power(state, aphra) == base, "4 distinct costs is below the 5 threshold"
        # A fifth distinct cost (8) arms +3/+0.
        self._add_discard(state, "P0", _get_card(repo, "SOR", "52"))
        assert compute_power(state, aphra) == base + 3, "5 distinct costs grants +3/+0"

    def test_SHD_15_deploy_returns_one_of_three_at_random(self, repo):
        """When Deployed: choose 3 different-named discard cards, then one of them is
        returned to hand at random (the discard shrinks by exactly one)."""
        from swu.engine.actions import legal_actions, apply, SelectDistinctDiscardCard
        state = _make_state()
        aphra = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "15"))
        c1 = self._add_discard(state, "P0", _get_card(repo, "SOR", "236"))
        c2 = self._add_discard(state, "P0", _get_card(repo, "SOR", "139"))
        c3 = self._add_discard(state, "P0", _get_card(repo, "SOR", "46"))
        chosen_ids = {c1.instance_id, c2.instance_id, c3.instance_id}
        state = _fire_when_deployed(state, aphra)
        assert state.pending_decisions[-1].kind == "select_distinct_return_random"
        # Pick all three distinct-named cards; the engine auto-finishes at 3.
        for _ in range(3):
            sel = next(a for a in legal_actions(state)
                       if isinstance(a, SelectDistinctDiscardCard))
            state = apply(state, sel)
        ps0 = state.player_by_id("P0")
        assert not state.pending_decisions
        returned = [c for c in ps0.hand if c.instance_id in chosen_ids]
        assert len(returned) == 1, "exactly one chosen card returns to hand at random"
        assert len(ps0.discard) == 2, "the other two chosen cards stay in the discard"

    def test_SHD_15_deploy_distinct_name_filter(self, repo):
        """After a card is chosen, another discard card sharing its name is no longer
        offered — the three picks must be differently named."""
        from swu.engine.actions import legal_actions, apply, SelectDistinctDiscardCard
        state = _make_state()
        aphra = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "15"))
        dup_a = self._add_discard(state, "P0", _get_card(repo, "SOR", "236"))
        dup_b = self._add_discard(state, "P0", _get_card(repo, "SOR", "236"))  # same name
        self._add_discard(state, "P0", _get_card(repo, "SOR", "139"))
        self._add_discard(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_deployed(state, aphra)
        # Choose dup_a first; dup_b (same name) must drop out of the candidates.
        sel_a = next(a for a in legal_actions(state)
                     if isinstance(a, SelectDistinctDiscardCard)
                     and a.instance_id == dup_a.instance_id)
        state = apply(state, sel_a)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectDistinctDiscardCard)}
        assert dup_b.instance_id not in offered, "a same-named discard card is filtered out"

    def test_SHD_15_deploy_not_pushed_with_fewer_than_three_names(self, repo):
        """With only two distinct names in the discard, 'choose 3' cannot be met, so
        no decision is pushed (the effect does nothing)."""
        state = _make_state()
        aphra = _deploy_leader_as_unit(state, "P0", _get_card(repo, "SHD", "15"))
        self._add_discard(state, "P0", _get_card(repo, "SOR", "236"))
        self._add_discard(state, "P0", _get_card(repo, "SOR", "139"))
        state = _fire_when_deployed(state, aphra)
        assert not state.pending_decisions, "fewer than 3 distinct names → no choice pushed"


class TestBrutalTraditions:
    """SHD_38 — Upgrade (+1/+2), cost 2.  "Action: If an enemy unit was defeated
    this phase, play this upgrade from your discard pile (paying its cost)."

    The play-from-discard Action surfaces via the ``PlayFromDiscardAction`` seam
    (the discard pile as a legal-action source), gated on the existing
    ``ENEMY_UNIT_DEFEATED_THIS_PHASE`` condition."""

    def _setup(self, repo, *, enemy_defeated=True, resources=10):
        state = _make_state()
        bt = _put_in_discard(state, "P0", _get_card(repo, "SHD", "38"))
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", resources, repo)
        if enemy_defeated:
            # An enemy (P1-controlled) unit was defeated this phase.
            state.game_memory.defeated_controllers_this_round.append("P1")
        return state, bt, host

    def test_SHD_38_playable_from_discard_when_enemy_defeated(self, repo):
        """Offered as a PlayFromDiscard onto a legal host; playing it pays the cost,
        leaves the discard pile, and attaches (+1 power to the host)."""
        from swu.engine.actions import (
            legal_actions, apply, PlayFromDiscard, compute_power, _play_cost)
        state, bt, host = self._setup(repo)
        ps0 = state.player_by_id("P0")
        cost = _play_cost(state, bt, ps0, target_host_id=host.instance_id)
        power_before = compute_power(state, host)
        res_before = ps0.available_resources
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == bt.instance_id
                    and a.upgrade_target_id == host.instance_id)
        state = apply(state, play)
        ps0 = state.player_by_id("P0")
        assert all(c.instance_id != bt.instance_id for c in ps0.discard), \
            "the upgrade leaves the discard pile when replayed"
        host_now = next(c for c in ps0.ground_arena if c.instance_id == host.instance_id)
        assert any(u.instance_id == bt.instance_id for u in host_now.attached_upgrades), \
            "the upgrade attaches to the chosen host"
        assert compute_power(state, host_now) == power_before + 1, "+1/+2 stats apply"
        assert ps0.available_resources == res_before - cost, "its printed cost is paid"

    def test_SHD_38_not_offered_without_enemy_defeat(self, repo):
        """No enemy unit defeated this phase → the discard Action is not offered."""
        from swu.engine.actions import legal_actions, PlayFromDiscard
        state, bt, host = self._setup(repo, enemy_defeated=False)
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state)), \
            "the gate condition is unmet, so the play never appears"

    def test_SHD_38_not_offered_without_resources(self, repo):
        """One resource short of the cost → affordability drops the play from the
        legal actions even though the gate holds."""
        from swu.engine.actions import legal_actions, PlayFromDiscard, _play_cost
        state, bt, host = self._setup(repo, resources=0)
        ps0 = state.player_by_id("P0")
        cost = _play_cost(state, bt, ps0, target_host_id=host.instance_id)
        _give_resources(state, "P0", cost - 1, repo)  # one short of the cost
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state)), \
            "an unaffordable discard-play is not offered"


class TestSecondChance:
    """SHD_53 — Upgrade, cost 4, attach to a non-leader unit.  "Attached unit
    gains: 'When Defeated: For this phase, this unit's owner may play it from
    their discard pile for free.'"

    A GrantedAbility(WhenDefeated) that records a phase-scoped, per-instance
    free-replay permission, surfaced as a free ``PlayFromDiscard``."""

    def _setup_and_defeat(self, repo, owner="P0"):
        """Attach Second Chance to a friendly non-leader unit, then defeat the host
        through the real defeat path (so the granted WhenDefeated is collected)."""
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, owner, _get_card(repo, "SOR", "46"), "ground")
        _attach_bounty_upgrade(state, host, _get_card(repo, "SHD", "53"), owner)
        _defeat_unit(state, state.player_by_id(owner), host)
        return state, host

    def test_SHD_53_grants_free_discard_replay_on_defeat(self, repo):
        """On the host's defeat its owner may replay it from discard for free — with
        zero resources available — after which the unit is in play, gone from the
        discard, and the one-shot permission is spent."""
        from swu.engine.actions import legal_actions, apply, PlayFromDiscard
        state, host = self._setup_and_defeat(repo)
        ps0 = state.player_by_id("P0")
        assert not state.pending_decisions
        assert host.instance_id in state.game_memory.free_discard_play_this_phase
        assert any(c.instance_id == host.instance_id for c in ps0.discard)
        assert ps0.available_resources == 0, "the replay must be genuinely free"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == host.instance_id and a.free)
        state = apply(state, play)
        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == host.instance_id
                   for c in ps0.ground_arena + ps0.space_arena), "unit re-enters play"
        assert all(c.instance_id != host.instance_id for c in ps0.discard)
        assert host.instance_id not in state.game_memory.free_discard_play_this_phase, \
            "the free-replay permission is consumed by the play"

    def test_SHD_53_permission_expires_at_phase_end(self, repo):
        """The free replay is only "for this phase" — it lapses at the phase rollover."""
        from swu.engine.actions import legal_actions, PlayFromDiscard
        state, host = self._setup_and_defeat(repo)
        state.game_memory.clear_phase()  # the ACTION phase ends
        assert host.instance_id not in state.game_memory.free_discard_play_this_phase
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state)), \
            "no free replay survives past the phase it was granted in"

    def test_SHD_53_no_free_replay_without_the_upgrade(self, repo):
        """A unit defeated without Second Chance grants no permission and no replay."""
        from swu.engine.actions import legal_actions, PlayFromDiscard, _defeat_unit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), host)
        assert not state.game_memory.free_discard_play_this_phase
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state))


class TestGroup08CardAdvantage:
    """shd-set:08 — Echo, The Marauder, Spark of Hope, Cobb Vanth, Commission."""

    def _play_event(self, state, ev_ci):
        from swu.engine.actions import legal_actions, apply, PlayCard
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ev_ci.instance_id)
        return apply(state, play)

    # ── SHD_99 Echo ──────────────────────────────────────────────────────────
    def test_SHD_99_discard_matching_card_gives_2_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardForExperience
        echo = _get_card(repo, "SHD", "99")
        state = _make_state()
        echo_ci = _place(state, "P0", echo, "ground")       # friendly Echo in play
        hand_echo = _put_in_hand(state, "P0", echo)         # same-named hand card
        state = _fire_when_played(state, echo_ci)
        assert state.pending_decisions[-1].kind == "discard_for_experience"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectDiscardForExperience)
                   and a.instance_id == hand_echo.instance_id)
        state = apply(state, sel)
        ps = state.player_by_id("P0")
        assert all(c.instance_id != hand_echo.instance_id for c in ps.hand)
        assert any(c.instance_id == hand_echo.instance_id for c in ps.discard)
        inplay = next(c for c in ps.ground_arena
                      if c.card_def.display_name == echo.display_name)
        assert _experience_count(inplay) == 2

    def test_SHD_99_no_decision_without_a_same_named_hand_card(self, repo):
        # A hand card whose name matches no friendly unit gives no benefit → the
        # optional discard fizzles cleanly (no decision pushed).
        echo = _get_card(repo, "SHD", "99")
        other = _get_card(repo, "SOR", "140")
        state = _make_state()
        echo_ci = _place(state, "P0", echo, "ground")
        _put_in_hand(state, "P0", other)  # name != Echo
        state = _fire_when_played(state, echo_ci)
        assert not any(d.kind == "discard_for_experience"
                       for d in state.pending_decisions)

    # ── SHD_102 The Marauder ──────────────────────────────────────────────────
    def test_SHD_102_resources_matching_discard_card(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectResourceFromDiscard
        marauder = _get_card(repo, "SHD", "102")
        unit = _get_card(repo, "SOR", "140")
        state = _make_state()
        m_ci = _place(state, "P0", marauder, "ground")
        _place(state, "P0", unit, "ground")                 # friendly unit to name-match
        disc = _put_in_discard(state, "P0", unit)           # same name in discard
        state = _fire_when_played(state, m_ci)
        assert state.pending_decisions[-1].kind == "resource_from_discard"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectResourceFromDiscard)
                   and a.instance_id == disc.instance_id)
        state = apply(state, sel)
        ps = state.player_by_id("P0")
        res = next((r for r in ps.resources if r.instance_id == disc.instance_id), None)
        assert res is not None, "card put into play as a resource"
        assert res.exhausted and res.face_down, "facedown + exhausted (no ready it)"
        assert all(c.instance_id != disc.instance_id for c in ps.discard)

    def test_SHD_102_no_resource_when_no_name_match(self, repo):
        marauder = _get_card(repo, "SHD", "102")
        friendly = _get_card(repo, "SOR", "140")
        other = _get_card(repo, "SOR", "46")
        state = _make_state()
        m_ci = _place(state, "P0", marauder, "ground")
        _place(state, "P0", friendly, "ground")
        _put_in_discard(state, "P0", other)  # name doesn't match the friendly unit
        state = _fire_when_played(state, m_ci)
        assert not any(d.kind == "resource_from_discard"
                       for d in state.pending_decisions)

    # ── SHD_105 Spark of Hope ─────────────────────────────────────────────────
    def test_SHD_105_resources_unit_defeated_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectResourceFromDiscard
        spark = _get_card(repo, "SHD", "105")
        unit = _get_card(repo, "SOR", "140")
        state = _make_state()
        ev = _put_in_hand(state, "P0", spark)
        disc = _put_in_discard(state, "P0", unit)
        state.game_memory.units_defeated_this_round.add(disc.instance_id)
        _give_resources(state, "P0", 10, repo)
        state = self._play_event(state, ev)
        assert state.pending_decisions[-1].kind == "resource_from_discard"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectResourceFromDiscard)
                   and a.instance_id == disc.instance_id)
        state = apply(state, sel)
        ps = state.player_by_id("P0")
        assert any(r.instance_id == disc.instance_id for r in ps.resources)

    def test_SHD_105_no_resource_when_not_defeated_this_phase(self, repo):
        spark = _get_card(repo, "SHD", "105")
        unit = _get_card(repo, "SOR", "140")
        state = _make_state()
        ev = _put_in_hand(state, "P0", spark)
        disc = _put_in_discard(state, "P0", unit)  # NOT flagged defeated-this-phase
        _give_resources(state, "P0", 10, repo)
        state = self._play_event(state, ev)
        assert not any(d.kind == "resource_from_discard"
                       for d in state.pending_decisions)
        assert any(c.instance_id == disc.instance_id
                   for c in state.player_by_id("P0").discard)

    # ── SHD_115 Cobb Vanth ────────────────────────────────────────────────────
    def test_SHD_115_search_discards_cheap_unit_for_free_replay(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard, PlayFromDiscard)
        cobb = _get_card(repo, "SHD", "115")
        cheap = _get_card(repo, "SOR", "140")  # a unit costing 1 (<= 2)
        state = _make_state()
        cobb_ci = _place(state, "P0", cobb, "ground")
        deck = _put_on_deck(state, "P0", [cheap])
        state = _fire_when_defeated(state, cobb_ci)
        assert state.pending_decisions[-1].kind == "deck_search"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)
                   and a.instance_id == deck[0].instance_id)
        state = apply(state, sel)  # count=1, up_to=False -> auto-finishes
        ps = state.player_by_id("P0")
        assert any(c.instance_id == deck[0].instance_id for c in ps.discard), \
            "searched unit discarded, not drawn"
        assert deck[0].instance_id in state.game_memory.free_discard_play_this_phase
        # The free replay surfaces as a PlayFromDiscard(free=True) on P0's turn.
        state.active_player_index = 0
        assert any(isinstance(a, PlayFromDiscard) and a.free
                   and a.instance_id == deck[0].instance_id
                   for a in legal_actions(state))

    # ── SHD_127 Commission ────────────────────────────────────────────────────
    def test_SHD_127_searches_and_draws_trait_card(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        commission = _get_card(repo, "SHD", "127")
        match = _get_card(repo, "SHD", "102")   # a Transport card
        nonmatch = _get_card(repo, "SOR", "46")  # Rebel/Trooper - no matching trait
        state = _make_state()
        ev = _put_in_hand(state, "P0", commission)
        deck = _put_on_deck(state, "P0", [match, nonmatch])
        _give_resources(state, "P0", 6, repo)
        state = self._play_event(state, ev)
        assert state.pending_decisions[-1].kind == "deck_search"
        # Only the Transport card is an eligible candidate.
        cands = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert cands == {deck[0].instance_id}
        state = apply(state, SelectSearchCard(deck[0].instance_id))
        ps = state.player_by_id("P0")
        assert any(c.instance_id == deck[0].instance_id for c in ps.hand), "drawn"
        assert all(c.instance_id != deck[1].instance_id for c in ps.hand), "non-match not drawn"


class TestGroup09CardAdvantage:
    """shd-set:09 — Kylo's TIE Silencer, Jango Fett, Cripple Authority,
    Bo-Katan Kryze, Death Mark, Pillage, Bazine Netal."""

    def _play_event(self, state, ev_ci):
        from swu.engine.actions import legal_actions, apply, PlayCard
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ev_ci.instance_id)
        return apply(state, play)

    # ── SHD_135 Kylo's TIE Silencer ────────────────────────────────────────────
    def test_SHD_135_playable_from_discard_when_discarded_this_phase(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayFromDiscard, note_hand_or_deck_discard)
        kylo = _get_card(repo, "SHD", "135")
        state = _make_state()
        kylo_ci = _put_in_discard(state, "P0", kylo)
        _give_resources(state, "P0", 8, repo)
        # It was discarded from a hand/deck this phase (the marker the game feeds at
        # the self-discard / mill sites).
        note_hand_or_deck_discard(state, kylo_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == kylo_ci.instance_id)
        state = apply(state, play)
        ps0 = state.player_by_id("P0")
        assert any(c.instance_id == kylo_ci.instance_id
                   for c in ps0.ground_arena + ps0.space_arena), "Kylo enters play"
        assert all(c.instance_id != kylo_ci.instance_id for c in ps0.discard), \
            "it leaves the discard pile when replayed"

    def test_SHD_135_not_playable_without_a_this_phase_discard(self, repo):
        # In the discard pile but NOT discarded this phase → the gate is unmet, and
        # after a phase rollover the mark lapses ("this phase").
        from swu.engine.actions import (
            legal_actions, PlayFromDiscard, note_hand_or_deck_discard)
        kylo = _get_card(repo, "SHD", "135")
        state = _make_state()
        kylo_ci = _put_in_discard(state, "P0", kylo)
        _give_resources(state, "P0", 8, repo)
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state)), \
            "unmarked discard card is not offered"
        note_hand_or_deck_discard(state, kylo_ci)
        state.game_memory.clear_phase()
        assert not any(isinstance(a, PlayFromDiscard) for a in legal_actions(state)), \
            "the mark clears at the phase rollover"

    # ── SHD_138 Jango Fett ─────────────────────────────────────────────────────
    def test_SHD_138_plus_3_only_while_attacking_a_bounty_unit(self, repo):
        from swu.engine.actions import compute_power
        jango = _get_card(repo, "SHD", "138")
        plain = _get_card(repo, "SOR", "46")
        pe = _get_card(repo, "SHD", "68")           # Public Enemy = a Bounty upgrade
        state = _make_state()
        jango_ci = _place(state, "P0", jango, "ground")
        bounty_enemy = _place(state, "P1", plain, "ground")
        plain_enemy = _place(state, "P1", plain, "ground")
        _attach_bounty_upgrade(state, bounty_enemy, pe, "P0")
        # vs a unit WITH a Bounty → +3
        atk_bounty = compute_power(state, jango_ci, is_attacking=True,
                                   attacking_unit=True,
                                   defender_id=bounty_enemy.instance_id)
        atk_plain = compute_power(state, jango_ci, is_attacking=True,
                                  attacking_unit=True,
                                  defender_id=plain_enemy.instance_id)
        assert atk_bounty == atk_plain + 3, "+3/+0 only while attacking a Bounty unit"

    def test_SHD_138_draws_on_attack_and_defeat(self, repo):
        from swu.engine.actions import apply, AttackWithUnit, legal_actions
        from swu.engine.state import CardInstance, Zone
        import uuid
        jango = _get_card(repo, "SHD", "138")
        weak = _get_card(repo, "SOR", "46")
        state = _make_state()
        jango_ci = _place(state, "P0", jango, "ground")     # 3/6, ready
        # A 1-HP enemy Jango will defeat with its 3 power.
        weak_ci = _place(state, "P1", weak, "ground")
        weak_ci.damage = max(0, (getattr(weak, "hp", 1) or 1) - 1)  # leave 1 HP
        for _ in range(3):
            state.player_by_id("P0").deck.append(CardInstance(
                instance_id=f"jd_{uuid.uuid4().hex[:6]}", card_def=weak,
                owner_id="P0", zone=Zone.DECK))
        hand_before = len(state.player_by_id("P0").hand)
        state = apply(state, AttackWithUnit(jango_ci.instance_id, weak_ci.instance_id))
        while state.pending_decisions:
            state = apply(state, legal_actions(state)[0])
        assert len(state.player_by_id("P0").hand) == hand_before + 1, \
            "attacking and defeating a unit draws a card"

    # ── SHD_156 Cripple Authority ──────────────────────────────────────────────
    def test_SHD_156_draws_and_richer_opponent_discards(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ca = _get_card(repo, "SHD", "156")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        ca_ci = CardInstance(instance_id=f"ca_{uuid.uuid4().hex[:6]}", card_def=ca,
                             owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ca_ci)
        _give_resources(state, "P0", 8, repo)
        _give_resources(state, "P1", 10, repo)              # P1 controls more resources
        _put_in_hand(state, "P1", filler)
        for _ in range(2):
            state.player_by_id("P0").deck.append(CardInstance(
                instance_id=f"cd_{uuid.uuid4().hex[:6]}", card_def=filler,
                owner_id="P0", zone=Zone.DECK))
        p0_hand_before = len(state.player_by_id("P0").hand)  # includes the event
        p1_hand_before = len(state.player_by_id("P1").hand)
        state = self._play_event(state, ca_ci)
        # P0 drew 1 (net hand: -1 event played +1 drawn = unchanged from before-1)
        assert len(state.player_by_id("P0").hand) == p0_hand_before  # -1 event +1 draw
        assert len(state.player_by_id("P1").hand) == p1_hand_before - 1, \
            "the richer opponent discards a card"

    def test_SHD_156_no_discard_when_opponent_not_richer(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ca = _get_card(repo, "SHD", "156")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        ca_ci = CardInstance(instance_id=f"ca_{uuid.uuid4().hex[:6]}", card_def=ca,
                             owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ca_ci)
        _give_resources(state, "P0", 10, repo)
        _give_resources(state, "P1", 4, repo)               # fewer resources
        _put_in_hand(state, "P1", filler)
        state.player_by_id("P0").deck.append(CardInstance(
            instance_id=f"cd_{uuid.uuid4().hex[:6]}", card_def=filler,
            owner_id="P0", zone=Zone.DECK))
        p1_hand_before = len(state.player_by_id("P1").hand)
        state = self._play_event(state, ca_ci)
        assert len(state.player_by_id("P1").hand) == p1_hand_before, \
            "an opponent who isn't richer discards nothing"

    # ── SHD_157 Bo-Katan Kryze ─────────────────────────────────────────────────
    def test_SHD_157_draws_per_base_at_15_damage(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        bk = _get_card(repo, "SHD", "157")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        bk_ci = _place(state, "P0", bk, "ground")
        state.player_by_id("P0").base_instance.damage = 15
        state.player_by_id("P1").base_instance.damage = 20
        for _ in range(3):
            state.player_by_id("P0").deck.append(CardInstance(
                instance_id=f"bd_{uuid.uuid4().hex[:6]}", card_def=filler,
                owner_id="P0", zone=Zone.DECK))
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_when_defeated(state, bk_ci)
        assert len(state.player_by_id("P0").hand) == hand_before + 2, \
            "both bases at >=15 damage → draw 2"

    # ── SHD_176 Death Mark ─────────────────────────────────────────────────────
    def test_SHD_176_bounty_collector_draws_two(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.state import CardInstance, Zone
        import uuid
        dm = _get_card(repo, "SHD", "176")
        plain = _get_card(repo, "SOR", "46")
        state = _make_state()
        host = _place(state, "P1", plain, "ground")         # P1 controls the host
        _attach_bounty_upgrade(state, host, dm, "P0")        # P0 owns Death Mark
        for _ in range(3):
            state.player_by_id("P0").deck.append(CardInstance(
                instance_id=f"dd_{uuid.uuid4().hex[:6]}", card_def=plain,
                owner_id="P0", zone=Zone.DECK))
        hand_before = len(state.player_by_id("P0").hand)
        _defeat_unit(state, state.player_by_id("P1"), host)
        assert not state.pending_decisions, "the draw is deterministic (no decision)"
        assert len(state.player_by_id("P0").hand) == hand_before + 2, \
            "the collector draws 2 cards"

    # ── SHD_181 Pillage ────────────────────────────────────────────────────────
    def test_SHD_181_chosen_player_discards_two(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        pillage = _get_card(repo, "SHD", "181")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        pil_ci = CardInstance(instance_id=f"pil_{uuid.uuid4().hex[:6]}", card_def=pillage,
                              owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(pil_ci)
        _give_resources(state, "P0", 10, repo)
        for _ in range(3):
            _put_in_hand(state, "P1", filler)
        p1_hand_before = len(state.player_by_id("P1").hand)
        state = self._play_event(state, pil_ci)
        assert len(state.player_by_id("P1").hand) == p1_hand_before - 2, \
            "the opponent discards 2 cards"

    # ── SHD_184 Bazine Netal ───────────────────────────────────────────────────
    def test_SHD_184_discards_a_card_and_that_player_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        from swu.engine.state import CardInstance, Zone
        import uuid
        bazine = _get_card(repo, "SHD", "184")
        c1 = _get_card(repo, "SOR", "46")
        c2 = _get_card(repo, "SOR", "140")
        state = _make_state()
        bazine_ci = _place(state, "P0", bazine, "ground")
        _put_in_hand(state, "P1", c1)
        _put_in_hand(state, "P1", c2)
        state.player_by_id("P1").deck.append(CardInstance(
            instance_id=f"bz_{uuid.uuid4().hex[:6]}", card_def=c1,
            owner_id="P1", zone=Zone.DECK))
        state = _fire_when_played(state, bazine_ci)
        assert state.pending_decisions[-1].kind == "name_and_discard"
        p1_hand_before = len(state.player_by_id("P1").hand)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, NameAndDiscard) and a.card_name == c1.display_name)
        state = apply(state, pick)
        p1 = state.player_by_id("P1")
        # -1 discarded, +1 drawn = net unchanged, and the named card left the hand.
        assert len(p1.hand) == p1_hand_before, "discard then draw = net-neutral hand size"
        assert any(c.card_def.display_name == c1.display_name for c in p1.discard), \
            "the chosen card is discarded"

    def test_SHD_184_may_decline_the_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineNameAndDiscard
        bazine = _get_card(repo, "SHD", "184")
        c1 = _get_card(repo, "SOR", "46")
        state = _make_state()
        bazine_ci = _place(state, "P0", bazine, "ground")
        _put_in_hand(state, "P1", c1)
        state = _fire_when_played(state, bazine_ci)
        p1_hand_before = len(state.player_by_id("P1").hand)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineNameAndDiscard))
        state = apply(state, decline)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == p1_hand_before, \
            "declining discards nothing and grants no draw"


# ── shd-set:10 "Card advantage & disruption" ─────────────────────────────────

class TestGroup10CardAdvantageDisruption:
    """shd-set:10 — Omega, Zorii Bliss, A New Adventure, Criminal Muscle,
    Frontier Trader, Xanadu Blood, Triple Dark Raid."""

    # ── SHD_198 Omega ─────────────────────────────────────────────────────────
    def test_SHD_198_searches_and_draws_a_clone(self, repo):
        from swu.engine.actions import legal_actions, apply
        omega = _get_card(repo, "SHD", "198")
        clone = _get_card(repo, "SHD", "95")   # Clone Deserter (Clone unit)
        filler = _get_card(repo, "SOR", "46")  # non-Clone unit
        state = _make_state()
        omega_ci = _place(state, "P0", omega, "ground")
        _put_on_deck(state, "P0", [filler, filler, clone, filler, filler])

        state = _fire_when_played(state, omega_ci)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        # Mandatory-if-able: only the Clone is a candidate (up_to=False).
        assert [type(a).__name__ for a in acts] == ["SelectSearchCard"]
        state = apply(state, acts[0])
        assert not state.pending_decisions
        assert any(ci.card_def.name == clone.name
                   for ci in state.player_by_id("P0").hand)

    def test_SHD_198_no_clone_in_window_draws_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishSearch
        omega = _get_card(repo, "SHD", "198")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        omega_ci = _place(state, "P0", omega, "ground")
        _put_on_deck(state, "P0", [filler, filler, filler])
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, omega_ci)
        acts = legal_actions(state)
        assert [type(a).__name__ for a in acts] == ["FinishSearch"]
        state = apply(state, FinishSearch())
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == before

    # ── SHD_203 Zorii Bliss ───────────────────────────────────────────────────
    def test_SHD_203_draws_on_attack_and_schedules_regroup_discard(self, repo):
        zorii = _get_card(repo, "SHD", "203")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        zorii_ci = _place(state, "P0", zorii, "ground")
        # A deck to draw from + two hand cards to later discard.
        _put_on_deck(state, "P0", [filler] * 3)
        _put_in_hand(state, "P0", filler)
        _put_in_hand(state, "P0", filler)
        hand_before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, zorii_ci)
        # Drew a card now, and scheduled exactly one regroup discard on Zorii.
        assert len(state.player_by_id("P0").hand) == hand_before + 1
        _, z = state.find_instance(zorii_ci.instance_id)
        assert z.discard_from_hand_at_regroup == 1

    def test_SHD_203_regroup_sweep_discards_and_clears(self, repo):
        from swu.engine.actions import _enter_regroup
        zorii = _get_card(repo, "SHD", "203")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        zorii_ci = _place(state, "P0", zorii, "ground")
        # Both players need decks for the regroup's draw-2 step.
        _put_on_deck(state, "P0", [filler] * 4)
        _put_on_deck(state, "P1", [filler] * 4)
        z = state.find_instance(zorii_ci.instance_id)[1]
        z.discard_from_hand_at_regroup = 1
        discard_before = len(state.player_by_id("P0").discard)

        _enter_regroup(state)

        # One card left P0's hand for the discard pile; the counter is cleared.
        assert len(state.player_by_id("P0").discard) == discard_before + 1
        assert state.find_instance(zorii_ci.instance_id)[1].discard_from_hand_at_regroup == 0

    # ── SHD_207 A New Adventure ────────────────────────────────────────────────
    def test_SHD_207_returns_unit_and_owner_may_replay_free(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (legal_actions, apply, PlayCard, ChooseTarget,
                                        ReplayReturnedUnit)
        import uuid
        adv = _get_card(repo, "SHD", "207")     # Event, cost 2
        target = _get_card(repo, "SOR", "46")   # Consular Security Force (cost 3 unit)
        state = _make_state()
        adv_ci = CardInstance(instance_id=f"adv_{uuid.uuid4().hex[:6]}",
                              card_def=adv, owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(adv_ci)
        victim = _place(state, "P0", target, "ground")
        _give_resources(state, "P0", 6, repo)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == adv_ci.instance_id)
        state = apply(state, play)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == victim.instance_id)
        state = apply(state, choose)
        # Unit was returned to hand and its owner is offered a free replay.
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P0").hand)
        assert state.pending_decisions[-1].kind == "owner_may_replay"
        res_before_replay = state.player_by_id("P0").available_resources
        replay = next(a for a in legal_actions(state)
                      if isinstance(a, ReplayReturnedUnit))
        state = apply(state, replay)
        # Back in play, and the replay itself was free (no further resources spent).
        assert _find_instance(state, victim.instance_id) is not None
        assert state.player_by_id("P0").available_resources == res_before_replay

    # ── SHD_209 Criminal Muscle ────────────────────────────────────────────────
    def test_SHD_209_returns_a_non_unique_upgrade(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        import uuid
        muscle = _get_card(repo, "SHD", "209")
        host = _get_card(repo, "SOR", "46")
        upgrade = _get_card(repo, "SOR", "69")   # Resilient (non-unique upgrade)
        state = _make_state()
        muscle_ci = _place(state, "P0", muscle, "ground")
        host_ci = _place(state, "P1", host, "ground")
        up_ci = CardInstance(instance_id=f"up_{uuid.uuid4().hex[:6]}",
                             card_def=upgrade, owner_id="P1", zone=Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(up_ci)

        state = _fire_when_played(state, muscle_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == up_ci.instance_id)
        state = apply(state, choose)
        _, host_after = state.find_instance(host_ci.instance_id)
        assert all(u.instance_id != up_ci.instance_id
                   for u in host_after.attached_upgrades)
        assert any(c.instance_id == up_ci.instance_id
                   for c in state.player_by_id("P1").hand)

    def test_SHD_209_cannot_target_a_unique_upgrade(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, AcceptTrigger
        import uuid
        muscle = _get_card(repo, "SHD", "209")
        host = _get_card(repo, "SOR", "46")
        unique_up = _get_card(repo, "SOR", "53")  # Luke's Lightsaber (unique)
        state = _make_state()
        muscle_ci = _place(state, "P0", muscle, "ground")
        host_ci = _place(state, "P1", host, "ground")
        up_ci = CardInstance(instance_id=f"up_{uuid.uuid4().hex[:6]}",
                             card_def=unique_up, owner_id="P1", zone=Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(up_ci)
        state = _fire_when_played(state, muscle_ci)
        # Only a unique upgrade in play → no eligible target → optional auto-declines.
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    # ── SHD_214 Frontier Trader ────────────────────────────────────────────────
    def test_SHD_214_returns_a_resource_and_ramps(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        AutoResolveEffects)
        trader = _get_card(repo, "SHD", "214")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        trader_ci = _place(state, "P0", trader, "ground")
        _give_resources(state, "P0", 2, repo)
        _put_on_deck(state, "P0", [filler, filler])
        hand_before = len(state.player_by_id("P0").hand)
        res_before = len(state.player_by_id("P0").resources)
        deck_before = len(state.player_by_id("P0").deck)

        state = _fire_when_played(state, trader_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # The accepted trigger's non-targeted CustomEffect resolves automatically.
        if state.pending_decisions:
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AutoResolveEffects)))
        ps = state.player_by_id("P0")
        # Recovered a resource to hand (+1), ramped the deck top (-1 deck), net
        # resource count unchanged.
        assert len(ps.hand) == hand_before + 1
        assert len(ps.resources) == res_before
        assert len(ps.deck) == deck_before - 1

    # ── SHD_191 Xanadu Blood ───────────────────────────────────────────────────
    def test_SHD_191_returns_underworld_unit_and_exhausts_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        xanadu = _get_card(repo, "SHD", "191")
        underworld = _get_card(repo, "SHD", "209")  # Criminal Muscle (Underworld unit)
        enemy = _get_card(repo, "SOR", "46")
        state = _make_state()
        xanadu_ci = _place(state, "P0", xanadu, "space")
        friend_ci = _place(state, "P0", underworld, "ground")
        enemy_ci = _place(state, "P1", enemy, "ground")
        enemy_ci.exhausted = False

        state = _fire_when_played(state, xanadu_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friend_ci.instance_id)
        state = apply(state, choose)
        # Friendly Underworld unit returned; the enemy unit is exhausted.
        assert _find_instance(state, friend_ci.instance_id) is None
        assert any(c.instance_id == friend_ci.instance_id
                   for c in state.player_by_id("P0").hand)
        assert state.find_instance(enemy_ci.instance_id)[1].exhausted is True

    def test_SHD_191_cannot_return_self_only_underworld(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        xanadu = _get_card(repo, "SHD", "191")
        state = _make_state()
        # Xanadu is itself Underworld, but "another" excludes it → no eligible target.
        xanadu_ci = _place(state, "P0", xanadu, "space")
        state = _fire_when_played(state, xanadu_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    # ── SHD_194 Triple Dark Raid ───────────────────────────────────────────────
    def test_SHD_194_searches_vehicle_plays_ready_and_flags_return(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, SelectSearchCard
        import uuid
        raid = _get_card(repo, "SHD", "194")     # Event, cost 3
        vehicle = _get_card(repo, "JTL", "251")  # Jedi Light Cruiser (Vehicle, cost 6)
        filler = _get_card(repo, "SOR", "46")    # non-Vehicle unit
        state = _make_state()
        raid_ci = CardInstance(instance_id=f"raid_{uuid.uuid4().hex[:6]}",
                               card_def=raid, owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(raid_ci)
        _put_on_deck(state, "P0", [filler, vehicle, filler] + [filler] * 4)
        _give_resources(state, "P0", 10, repo)  # cost 3 event + the reduced vehicle

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == raid_ci.instance_id)
        state = apply(state, play)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        # Only the Vehicle is an eligible, affordable candidate.
        sels = [a for a in acts if isinstance(a, SelectSearchCard)]
        assert len(sels) == 1
        state = apply(state, sels[0])
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        played = [u for u in ps.ground_arena + ps.space_arena
                  if u.card_def.name == vehicle.name]
        assert len(played) == 1
        veh = played[0]
        assert veh.exhausted is False                       # enters play ready
        assert veh.return_to_owner_hand_at_regroup is True  # bounces at phase end


# ── shd-set:11 — Card advantage & disruption ──────────────────────────────────

class TestEnticingReward:
    """SHD_222 — bounty upgrade: collector searches THEIR deck for 2 non-unit
    cards and draws them, then (host non-unique) discards a card from hand."""

    def test_SHD_222_bounty_collector_searches_and_draws(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, _defeat_unit, SelectSearchCard)
        reward = _get_card(repo, "SHD", "222")
        unit = _get_card(repo, "SOR", "46")       # non-unique host + filler unit
        event_a = _get_card(repo, "SHD", "244")   # non-unit (Event)
        event_b = _get_card(repo, "SHD", "233")   # non-unit (Event)
        state = _make_state()
        host = _place(state, "P1", unit, "ground")            # P1 controls the host
        _attach_bounty_upgrade(state, host, reward, "P0")     # P0 collects
        # Top 10: exactly two non-unit (event) candidates among unit filler.
        _put_on_deck(state, "P0", [event_a, unit, event_b] + [unit] * 7)
        hand_filler = _put_in_hand(state, "P0", unit)         # the discard fodder

        _defeat_unit(state, state.player_by_id("P1"), host)

        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.deciding_player_id == "P0"
        # Host is non-unique → collector already discarded its one hand card.
        ps0 = state.player_by_id("P0")
        assert hand_filler.instance_id in {c.instance_id for c in ps0.discard}
        # Forced pick of the two non-unit cards (up_to=False, count=2).
        for _ in range(2):
            sel = next(a for a in legal_actions(state)
                       if isinstance(a, SelectSearchCard))
            state = apply(state, sel)
        assert not state.pending_decisions
        ps0 = state.player_by_id("P0")
        drawn = {c.card_def.name for c in ps0.hand}
        assert event_a.name in drawn and event_b.name in drawn


class TestBountyPosting:
    """SHD_228 — search the deck for a Bounty upgrade and draw it."""

    def test_SHD_228_searches_and_draws_a_bounty_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        bounty_upgrade = _get_card(repo, "SHD", "68")   # Public Enemy (Bounty upgrade)
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        _put_on_deck(state, "P0", [filler, filler, bounty_upgrade, filler])
        state, _evt = _play_event_from_hand(state, repo, "SHD", "228", owner="P0")

        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        sels = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert len(sels) == 1                            # only the Bounty upgrade
        state = apply(state, sels[0])
        assert not state.pending_decisions
        ps0 = state.player_by_id("P0")
        assert bounty_upgrade.name in {c.card_def.name for c in ps0.hand}


class TestEvacuate:
    """SHD_233 — return each non-leader unit to its owner's hand."""

    def test_SHD_233_bounces_all_non_leader_units(self, repo):
        unit = _get_card(repo, "SOR", "46")
        u0 = _place(state := _make_state(), "P0", unit, "ground")
        u1 = _place(state, "P1", unit, "space")
        state, _evt = _play_event_from_hand(state, repo, "SHD", "233", owner="P0")
        assert not state.pending_decisions
        assert u0.instance_id in {c.instance_id for c in state.player_by_id("P0").hand}
        assert u1.instance_id in {c.instance_id for c in state.player_by_id("P1").hand}
        # Both arenas cleared of the returned units.
        assert not state.player_by_id("P0").ground_arena
        assert not state.player_by_id("P1").space_arena


class TestAlteringTheDeal:
    """SHD_243 — discard a captured card guarded by a friendly unit."""

    def test_SHD_243_discards_a_guarded_captured_card(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        guard = _get_card(repo, "SOR", "46")
        captured_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        guard_ci = _place(state, "P0", guard, "ground")       # friendly guard
        cap = CardInstance(
            instance_id=f"cap_{uuid.uuid4().hex[:6]}", card_def=captured_def,
            owner_id="P1", zone=Zone.CAPTURE_PILE)
        cap.captured_by = guard_ci.instance_id
        state.player_by_id("P0").capture_pile.append(cap)

        state, _evt = _play_event_from_hand(state, repo, "SHD", "243", owner="P0")
        assert not state.pending_decisions
        # Captured card left the capture pile → owner's (P1) discard.
        assert cap.instance_id not in {c.instance_id for c in state.player_by_id("P0").capture_pile}
        assert cap.instance_id in {c.instance_id for c in state.player_by_id("P1").discard}


class TestNoBargain:
    """SHD_244 — each opponent discards a card; draw a card."""

    def test_SHD_244_opponent_discards_controller_draws(self, repo):
        unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        _put_in_hand(state, "P1", unit)
        _put_in_hand(state, "P1", unit)
        _put_on_deck(state, "P0", [unit, unit])
        p1_before = len(state.player_by_id("P1").hand)
        p0_hand_before = len(state.player_by_id("P0").hand)
        state, _evt = _play_event_from_hand(state, repo, "SHD", "244", owner="P0")
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == p1_before - 1
        # +1 drawn, and the event itself was played from hand (net accounting below).
        assert len(state.player_by_id("P0").hand) == p0_hand_before + 1


# ── shd-set:12 — Leaders & combat tricks ──────────────────────────────────────

def _mk_unit(name, keywords=(), power=3, hp=3, traits=("Trooper",)):
    from swu.cards.models import Unit
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="9", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None,
        rules=None, rules_styled=None, aspects=(),
        keywords=tuple(keywords), traits=tuple(traits), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=3, power=power, hp=hp,
    )


def _fire_card_played_ctx(state, player_id, played_ci, event_ctx):
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=player_id, instance_id=played_ci.instance_id,
                     card_name=played_ci.card_def.display_name, cost_paid=0)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0,
                                    event_ctx=event_ctx)


class TestReyShd4:
    def test_SHD_4_on_attack_experience_to_low_power_unit(self, repo):
        """SHD_4 deployed On Attack: give an Experience token to a unit with 2 or
        less power (power_max filter excludes a 3-power unit)."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        rey = _get_card(repo, "SHD", "4")
        state = _make_state()
        rey_ci = _place_deployed_leader(state, "P0", rey)         # power 2
        big = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # power 3
        state = _fire_on_attack(state, rey_ci)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        targs = {a.target_id for a in legal_actions(state)
                 if isinstance(a, ChooseTarget) and a.target_id}
        assert rey_ci.instance_id in targs        # power 2 ≤ 2 eligible
        assert big.instance_id not in targs        # power 3 excluded
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == rey_ci.instance_id)
        state = apply(state, pick)
        assert _experience_count(state.find_instance(rey_ci.instance_id)[1]) == 1


class TestHondoOhnaka:
    def test_SHD_5_deployed_smuggle_play_gives_experience(self, repo):
        """SHD_5 deployed: "When you play a card using Smuggle: you may give an
        Experience token to a unit" — the new WhenYouPlayCard(via_smuggle) filter."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        hondo = _get_card(repo, "SHD", "5")
        state = _make_state()
        hondo_ci = _place_deployed_leader(state, "P0", hondo)
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        played = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        state = _fire_card_played_ctx(state, "P0", played, {"via_smuggle": True})
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == unit.instance_id)
        state = apply(state, pick)
        assert _experience_count(state.find_instance(unit.instance_id)[1]) == 1

    def test_SHD_5_non_smuggle_play_no_trigger(self, repo):
        """A non-Smuggle play does not fire Hondo's observer."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        hondo = _get_card(repo, "SHD", "5")
        state = _make_state()
        _place_deployed_leader(state, "P0", hondo)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        played = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        state = _fire_card_played_ctx(state, "P0", played, {})   # no via_smuggle
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestJabbaTheHuttShd6:
    def test_SHD_6_grant_discount_bounty_then_defeat_discounts_collector(self, repo):
        """SHD_6 undeployed Action grants a unit "Bounty — next unit costs 1 less";
        defeating that unit gives the collector a pending NextPlayDiscount."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget, _defeat_unit
        jabba = _get_card(repo, "SHD", "6")
        state = _make_state()
        jabba_ci = _place_leader(state, "P0", jabba)             # undeployed, ready
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == jabba_ci.instance_id)
        state = apply(state, use)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, pick)
        _, enemy_after = state.find_instance(enemy.instance_id)
        assert enemy_after.granted_bounties == ["next_unit_discount:1"]
        _defeat_unit(state, state.player_by_id("P1"), enemy_after)
        entries = [e for e in state.game_memory.pending_play_discounts
                   if e.get("player_id") == "P0" and e.get("amount") == 1]
        assert len(entries) == 1

    def test_SHD_6_when_deployed_capture(self, repo):
        """SHD_6 deployed When Deployed: another friendly unit captures an enemy
        non-leader unit."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        jabba = _get_card(repo, "SHD", "6")
        state = _make_state()
        jabba_ci = _place_deployed_leader(state, "P0", jabba)
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_deployed(state, jabba_ci)
        # Stage 1: choose the friendly captor (not Jabba himself).
        pick_captor = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget) and a.target_id == captor.instance_id)
        state = apply(state, pick_captor)
        # Stage 2: choose the enemy non-leader to capture.
        pick_enemy = next(a for a in legal_actions(state)
                          if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, pick_enemy)
        assert enemy.instance_id in {c.instance_id
                                     for c in state.player_by_id("P0").capture_pile}


class TestBobaFettShd8:
    def test_SHD_8_deployed_aura_buffs_keyword_units(self, repo):
        """SHD_8 deployed: each other friendly unit with ≥1 keyword gets +1/+0."""
        from swu.engine.actions import compute_power
        boba = _get_card(repo, "SHD", "8")
        state = _make_state()
        _place_deployed_leader(state, "P0", boba)
        kw_unit = _place(state, "P0", _mk_unit("Keyworder", keywords=("Sentinel",), power=3), "ground")
        plain = _place(state, "P0", _mk_unit("Plain", keywords=(), power=3), "ground")
        assert compute_power(state, state.find_instance(kw_unit.instance_id)[1]) == 4
        assert compute_power(state, state.find_instance(plain.instance_id)[1]) == 3

    def test_SHD_8_undeployed_trigger_exhausts_and_buffs(self, repo):
        """SHD_8 undeployed: playing a unit with ≥1 keyword lets you exhaust Boba to
        give a friendly unit +1/+0 (the WhenYouPlayCard has_any_keyword filter)."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power
        boba = _get_card(repo, "SHD", "8")
        state = _make_state()
        boba_ci = _place_leader(state, "P0", boba)               # undeployed, ready
        played = _place(state, "P0", _mk_unit("Keyworder", keywords=("Raid",), power=3), "ground")
        state = _fire_card_played_ctx(state, "P0", played, {})
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == played.instance_id)
        state = apply(state, pick)
        _, boba_after = state.find_instance(boba_ci.instance_id)
        assert boba_after.exhausted is True
        assert compute_power(state, state.find_instance(played.instance_id)[1]) == 4

    def test_SHD_8_no_trigger_for_keywordless_unit(self, repo):
        """Playing a unit with no keywords does not offer Boba's trigger."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        boba = _get_card(repo, "SHD", "8")
        state = _make_state()
        _place_leader(state, "P0", boba)
        played = _place(state, "P0", _mk_unit("Plain", keywords=(), power=3), "ground")
        state = _fire_card_played_ctx(state, "P0", played, {})
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestKyloRenShd11:
    def test_SHD_11_undeployed_discard_cost_buffs_unit(self, repo):
        """SHD_11 undeployed Action [Exhaust, discard a card]: give a unit +2/+0.
        Exercises the new DiscardCardCost cost spec."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget, compute_power
        kylo = _get_card(repo, "SHD", "11")
        state = _make_state()
        kylo_ci = _place_leader(state, "P0", kylo)
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3 power
        fodder = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        hand_before = len(state.player_by_id("P0").hand)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == kylo_ci.instance_id)
        state = apply(state, use)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == target.instance_id)
        state = apply(state, pick)
        assert len(state.player_by_id("P0").hand) == hand_before - 1   # cost paid
        assert compute_power(state, state.find_instance(target.instance_id)[1]) == 5

    def test_SHD_11_no_ability_with_empty_hand(self, repo):
        """DiscardCardCost is unaffordable with an empty hand → ability not offered."""
        from swu.engine.actions import legal_actions, UseAbility
        kylo = _get_card(repo, "SHD", "11")
        state = _make_state()
        kylo_ci = _place_leader(state, "P0", kylo)
        state.player_by_id("P0").hand.clear()
        assert not any(isinstance(a, UseAbility) and a.source_id == kylo_ci.instance_id
                       for a in legal_actions(state))

    def test_SHD_11_deployed_self_debuff_scales_with_hand(self, repo):
        """SHD_11 deployed: this unit gets -1/-0 for each card in your hand."""
        from swu.engine.actions import compute_power
        kylo = _get_card(repo, "SHD", "11")
        state = _make_state()
        kylo_ci = _place_deployed_leader(state, "P0", kylo)       # base power 5
        state.player_by_id("P0").hand.clear()
        for _ in range(2):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        assert compute_power(state, state.find_instance(kylo_ci.instance_id)[1]) == 3


class TestLomPyke:
    def test_SHD_32_on_attack_shields_enemy_then_friendly(self, repo):
        """SHD_32 On Attack: give a Shield to an enemy unit; if you do, give a Shield
        to a friendly unit."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, SelectTokenTarget)
        from swu.engine.keywords import shields_on
        lom = _get_card(repo, "SHD", "32")
        state = _make_state()
        lom_ci = _place(state, "P0", lom, "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, lom_ci)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick_enemy = next(a for a in legal_actions(state)
                          if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, pick_enemy)
        # Friendly shield selection follows (select_token, max 1).
        give = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget) and a.target_id == friendly.instance_id)
        state = apply(state, give)
        assert shields_on(state.find_instance(enemy.instance_id)[1]) == 1
        assert shields_on(state.find_instance(friendly.instance_id)[1]) == 1


class TestSupercommandoSquad:
    def test_SHD_34_gains_sentinel_while_upgraded(self, repo):
        """SHD_34: while upgraded it gains Sentinel (SOURCE_UPGRADED)."""
        from swu.engine.keywords import has_keyword, Keyword
        squad = _get_card(repo, "SHD", "34")
        upgrade = _get_card(repo, "SOR", "53")   # a real Upgrade
        state = _make_state()
        squad_ci = _place(state, "P0", squad, "ground")
        assert not has_keyword(state, squad_ci, Keyword.SENTINEL)   # no upgrade yet
        _attach_upgrade_directly(state, squad_ci, upgrade, "P0")
        assert has_keyword(state, squad_ci, Keyword.SENTINEL)


# ── shd-set:13 — Combat tricks, buffs & tempo ─────────────────────────────────

def _fire_attack_defeats(state, attacker_ci):
    """Fire the OnAttackDefeatsUnit triggers for ``attacker_ci`` (mirrors the combat
    pipeline's post-combat fire when the attacker survives and the defender dies)."""
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, None, after_all_player_idx=0,
        event_ctx={"attack_defeated_unit": attacker_ci.instance_id})


class TestClanSaxonGauntlet:
    def test_SHD_35_when_attacked_gives_experience(self, repo):
        """SHD_35 When this unit is attacked: you may give an Experience token."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        gauntlet = _get_card(repo, "SHD", "35")
        attacker = _get_card(repo, "SOR", "46")
        state = _make_state()
        gauntlet_ci = _place(state, "P0", gauntlet, "ground")
        att_ci = _place(state, "P1", attacker, "ground")
        state = _fire_on_attack(state, att_ci, gauntlet_ci)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == gauntlet_ci.instance_id)
        state = apply(state, pick)
        assert _experience_count(state.find_instance(gauntlet_ci.instance_id)[1]) == 1


class TestFirstLight:
    def test_SHD_36_grants_grit_to_other_friendly_non_leaders(self, repo):
        """SHD_36 aura: each other friendly non-leader unit gains Grit."""
        from swu.engine.keywords import has_keyword, Keyword
        fl = _get_card(repo, "SHD", "36")
        state = _make_state()
        fl_ci = _place(state, "P0", fl, "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # no printed Grit
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, ally, Keyword.GRIT)          # granted
        assert not has_keyword(state, enemy, Keyword.GRIT)     # enemies unaffected
        assert has_keyword(state, fl_ci, Keyword.GRIT)         # First Light's own printed Grit


class TestConcordDawnInterceptors:
    def test_SHD_42_plus_two_power_while_defending(self, repo):
        """SHD_42: +2/+0 while defending (self-buff only when it is the defender)."""
        from swu.engine.actions import compute_power
        cdi = _get_card(repo, "SHD", "42")
        state = _make_state()
        cdi_ci = _place(state, "P0", cdi, "space")             # base power 1
        assert compute_power(state, cdi_ci) == 1
        assert compute_power(state, cdi_ci, is_defending=True) == 3


class TestGentleGiant:
    def test_SHD_48_on_attack_heals_by_own_damage(self, repo):
        """SHD_48 On Attack: heal another unit by the damage on this unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        giant = _get_card(repo, "SHD", "48")
        state = _make_state()
        giant_ci = _place(state, "P0", giant, "ground")
        giant_ci.damage = 3
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ally.damage = 5
        state = _fire_on_attack(state, giant_ci)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, pick)
        assert state.find_instance(ally.instance_id)[1].damage == 2   # 5 - 3


class TestSugi:
    def test_SHD_52_gains_sentinel_while_enemy_upgraded(self, repo):
        """SHD_52: while an enemy unit is upgraded, Sugi gains Sentinel."""
        from swu.engine.keywords import has_keyword, Keyword
        sugi = _get_card(repo, "SHD", "52")
        upgrade = _get_card(repo, "SOR", "53")
        state = _make_state()
        sugi_ci = _place(state, "P0", sugi, "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not has_keyword(state, sugi_ci, Keyword.SENTINEL)   # no enemy upgrade yet
        _attach_upgrade_directly(state, enemy, upgrade, "P1")
        assert has_keyword(state, sugi_ci, Keyword.SENTINEL)


class TestMidnightRepairs:
    def test_SHD_54_heals_units_only(self, repo):
        """SHD_54: heal up to 8 total from any number of units (no bases, no self)."""
        from swu.engine.actions import legal_actions, apply, AssignDamage, FinishDamageDistribution
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit.damage = 5
        base = state.players[0].base_instance
        base.damage = 4
        state, _evt = _play_event_from_hand(state, repo, "SHD", "54", owner="P0")
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context.get("heal")
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, AssignDamage)}
        assert unit.instance_id in targets
        assert base.instance_id not in targets            # include_bases=False
        for _ in range(5):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, AssignDamage) and a.target_id == unit.instance_id)
            state = apply(state, act)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishDamageDistribution)))
        assert not state.pending_decisions
        assert state.find_instance(unit.instance_id)[1].damage == 0


class TestEmbo:
    def test_SHD_59_heals_after_defeating_defender(self, repo):
        """SHD_59 When this unit completes an attack, if the defender was defeated:
        heal up to 2 from a unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        embo = _get_card(repo, "SHD", "59")
        state = _make_state()
        embo_ci = _place(state, "P0", embo, "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ally.damage = 5
        state = _fire_attack_defeats(state, embo_ci)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, pick)
        assert state.find_instance(ally.instance_id)[1].damage == 3   # 5 - 2

    def test_SHD_59_no_trigger_without_defeat(self, repo):
        """No OnAttackDefeatsUnit fire → no trigger offered."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        embo = _get_card(repo, "SHD", "59")
        state = _make_state()
        embo_ci = _place(state, "P0", embo, "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        # No defeat event fired → nothing pending.
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── shd-set:14 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestCovertStrength:
    def test_SHD_75_heals_and_gives_experience_to_same_unit(self, repo):
        """SHD_75: Heal 2 from a unit AND give it an Experience token."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit.damage = 3
        state, _ev = _play_event_from_hand(state, repo, "SHD", "75", owner="P0")
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == unit.instance_id)
        state = apply(state, pick)
        u = state.find_instance(unit.instance_id)[1]
        assert u.damage == 1                       # 3 - 2 healed
        assert _experience_count(u) == 1


class TestUnexpectedEscape:
    def test_SHD_76_exhausts_unit_and_rescues_captive_to_hand(self, repo):
        """SHD_76: exhaust the enemy captor and rescue your captured card to hand."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, _apply_capture
        state = _make_state()
        captor = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _apply_capture(state, captor.instance_id, victim.instance_id)
        # Victim is now facedown in P1's capture pile, owned by P0.
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P1").capture_pile)
        state, _ev = _play_event_from_hand(state, repo, "SHD", "76", owner="P0")
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == captor.instance_id)
        state = apply(state, pick)
        assert state.find_instance(captor.instance_id)[1].exhausted        # captor exhausted
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P0").hand)                  # rescued to hand
        assert not state.player_by_id("P1").capture_pile


class TestWarbirdStowaway:
    def test_SHD_86_plus_two_power_while_you_have_initiative(self, repo):
        """SHD_86: +2/+0 while its controller has the initiative."""
        from swu.engine.actions import compute_power
        wb = _get_card(repo, "SHD", "86")
        state = _make_state()          # initiative_holder = 0 (P0)
        wb_ci = _place(state, "P0", wb, "space")   # base power 2
        assert compute_power(state, wb_ci) == 4    # 2 + 2 (has initiative)
        state.initiative_holder = 1                # opponent now holds it
        assert compute_power(state, wb_ci) == 2    # bonus gone


class TestCrosshair:
    def test_SHD_87_pump_then_damage_equals_power(self, repo):
        """SHD_87: [2 res] +1/+0; [Exhaust] deal damage equal to power to an enemy
        ground unit (reads the buffed power)."""
        from swu.engine.actions import (legal_actions, apply, compute_power,
                                         UseAbility, ChooseTarget)
        # Buff branch.
        state = _make_state()
        cross = _place(state, "P0", _get_card(repo, "SHD", "87"), "ground")
        _give_resources(state, "P0", 5, repo)
        pump = next(a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == cross.instance_id
                    and a.ability_idx == 0)
        state = apply(state, pump)
        assert compute_power(state, state.find_instance(cross.instance_id)[1]) == 3

        # Damage branch (fresh state, base power 2).
        state = _make_state()
        cross = _place(state, "P0", _get_card(repo, "SHD", "87"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        shoot = next(a for a in legal_actions(state)
                     if isinstance(a, UseAbility) and a.source_id == cross.instance_id
                     and a.ability_idx == 1)
        state = apply(state, shoot)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, pick)
        assert state.find_instance(enemy.instance_id)[1].damage == 2      # = power


class TestFreetownBackup:
    def test_SHD_97_on_attack_buffs_another_friendly(self, repo):
        """SHD_97 On Attack: give another friendly unit +2/+2 for this phase."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        fb = _place(state, "P0", _get_card(repo, "SHD", "97"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, fb)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, pick)
        assert compute_power(state, state.find_instance(ally.instance_id)[1]) == 5   # 3 + 2


class TestAdelphiPatrolWing:
    def test_SHD_101_initiative_grants_plus_two(self, repo):
        """SHD_101 When Played: optional attack, +2/+0 only with the initiative."""
        adelphi = _get_card(repo, "SHD", "101")
        # With initiative (P0 holds it by default).
        state = _make_state()
        ad_ci = _place(state, "P0", adelphi, "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # an attacker
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # a defender
        state = _fire_when_played(state, ad_ci)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 2
        # Without initiative.
        state = _make_state()
        state.initiative_holder = 1
        ad_ci = _place(state, "P0", adelphi, "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, ad_ci)
        assert state.pending_decisions[-1].context["power_bonus"] == 0


class TestGeneralRieekan:
    def test_SHD_103_sentinel_unit_gets_experience_else_gains_sentinel(self, repo):
        """SHD_103 When Played: Sentinel unit → Experience; otherwise → Sentinel."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        rieekan = _get_card(repo, "SHD", "103")
        # Branch 1: a non-Sentinel ally gains Sentinel.
        state = _make_state()
        rk = _place(state, "P0", rieekan, "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert not has_keyword(state, ally, Keyword.SENTINEL)
        state = _fire_when_played(state, rk)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, pick)
        assert has_keyword(state, state.find_instance(ally.instance_id)[1], Keyword.SENTINEL)

        # Branch 2: a Sentinel unit (Rieekan itself) gets an Experience token.
        state = _make_state()
        rk = _place(state, "P0", rieekan, "ground")
        assert has_keyword(state, rk, Keyword.SENTINEL)   # printed Sentinel
        state = _fire_when_played(state, rk)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == rk.instance_id)
        state = apply(state, pick)
        assert _experience_count(state.find_instance(rk.instance_id)[1]) == 1


# ── shd-set:15 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestInspiringMentor:
    def test_SHD_104_on_attack_gives_experience_to_another_friendly(self, repo):
        """SHD_104 grants the host: On Attack → Experience token to another friendly."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SHD", "104"), "P0")
        ally = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, host)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, pick)
        assert _experience_count(state.find_instance(ally.instance_id)[1]) == 1


class TestGamorreanRetainer:
    def test_SHD_112_sentinel_while_control_other_command_unit(self, repo):
        """SHD_112: gains Sentinel while its controller has another Command unit."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        gam = _place(state, "P0", _get_card(repo, "SHD", "112"), "ground")
        assert not has_keyword(state, gam, Keyword.SENTINEL)   # no other Command unit
        _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")   # a Command unit
        assert has_keyword(state, gam, Keyword.SENTINEL)


class TestOutlawCorona:
    def test_SHD_116_bounty_ramps_collector_deck(self, repo):
        """SHD_116 Bounty: collector puts the top card of their deck into play as a
        resource when Outlaw Corona is defeated."""
        from swu.engine.state import Zone
        state = _make_state()
        corona = _place(state, "P1", _get_card(repo, "SHD", "116"), "space")
        _put_on_deck(state, "P0", [_get_card(repo, "SOR", "46")])   # collector deck
        before = len(state.player_by_id("P0").resources)
        state = _defeat_and_fire(state, corona, "P1")
        res = state.player_by_id("P0").resources
        assert len(res) == before + 1
        assert res[-1].zone == Zone.RESOURCES and res[-1].face_down


class TestReputableHunter:
    def test_SHD_117_costs_one_less_with_enemy_bounty(self, repo):
        """SHD_117: costs 1 less while an enemy unit has a Bounty (compare paid)."""
        from swu.engine.actions import apply, PlayCard

        def _paid(with_bounty):
            state = _make_state()
            hunter = _put_in_hand(state, "P0", _get_card(repo, "SHD", "117"))
            _give_resources(state, "P0", 12, repo)
            if with_bounty:
                _place(state, "P1", _get_card(repo, "SHD", "116"), "space")
            before = state.player_by_id("P0").available_resources
            state = apply(state, PlayCard(hunter.instance_id))
            return before - state.player_by_id("P0").available_resources

        assert _paid(with_bounty=True) == _paid(with_bounty=False) - 1


class TestArquitensAssaultCruiser:
    def test_SHD_122_resources_defeated_defender(self, repo):
        """SHD_122: on attacking and defeating a non-leader unit, put it into play as
        a resource under the attacker's control."""
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.state import CardInstance, Zone
        import uuid
        state = _make_state()
        arq = _place(state, "P0", _get_card(repo, "SHD", "122"), "space")
        victim = CardInstance(instance_id=f"vic_{uuid.uuid4().hex[:6]}",
                              card_def=_get_card(repo, "SOR", "46"),
                              owner_id="P1", zone=Zone.DISCARD)
        state.player_by_id("P1").discard.append(victim)   # the just-defeated defender
        before = len(state.player_by_id("P0").resources)
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": arq.instance_id,
                       "attack_defeated_defender": victim.instance_id})
        res = state.player_by_id("P0").resources
        assert len(res) == before + 1
        assert victim.instance_id in {r.instance_id for r in res}
        assert not state.player_by_id("P1").discard


class TestPunishingOne:
    def test_SHD_137_readies_when_upgraded_enemy_defeated(self, repo):
        """SHD_137: when an upgraded enemy unit is defeated, may ready this unit."""
        from swu.engine.actions import _defeat_unit, legal_actions, apply, AcceptTrigger
        state = _make_state()
        po = _place(state, "P0", _get_card(repo, "SHD", "137"), "space")
        po.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, enemy, _get_card(repo, "SOR", "53"), "P1")
        _defeat_unit(state, state.player_by_id("P1"), enemy)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        # Drive the no-target CustomEffect (ready + once-per-round mark) to resolution.
        while state.pending_decisions:
            state = apply(state, legal_actions(state)[0])
        assert not state.find_instance(po.instance_id)[1].exhausted   # readied

    def test_SHD_137_no_trigger_when_enemy_not_upgraded(self, repo):
        """No trigger when the defeated enemy unit had no upgrade."""
        from swu.engine.actions import _defeat_unit, legal_actions, AcceptTrigger
        state = _make_state()
        po = _place(state, "P0", _get_card(repo, "SHD", "137"), "space")
        po.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # no upgrade
        _defeat_unit(state, state.player_by_id("P1"), enemy)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestTrandoshanHunters:
    def test_SHD_140_experience_when_enemy_has_bounty(self, repo):
        """SHD_140 When Played: Experience token to itself if an enemy has a Bounty."""
        state = _make_state()
        th = _place(state, "P0", _get_card(repo, "SHD", "140"), "ground")
        _place(state, "P1", _get_card(repo, "SHD", "116"), "space")   # enemy Bounty unit
        state = _fire_when_played(state, th)
        assert _experience_count(state.find_instance(th.instance_id)[1]) == 1

    def test_SHD_140_no_experience_without_enemy_bounty(self, repo):
        """No token when no enemy unit has a Bounty."""
        state = _make_state()
        th = _place(state, "P0", _get_card(repo, "SHD", "140"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # no Bounty
        state = _fire_when_played(state, th)
        assert _experience_count(state.find_instance(th.instance_id)[1]) == 0


# ── shd-set:16 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestHeadhunting:
    def test_SHD_145_pushes_capped_no_base_bounty_hunter_attack(self, repo):
        """SHD_145: up to 3 attacks (no bases); Bounty Hunters get +2/+0."""
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # an attacker
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # a defender
        state, _ev = _play_event_from_hand(state, repo, "SHD", "145", owner="P0")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        ctx = top.context
        assert ctx["repeat"] and ctx["repeat_max"] == 3
        assert ctx["no_base"] and ctx["optional"]
        assert ctx["bonus_trait"] == "Bounty Hunter" and ctx["power_bonus"] == 2


class TestValiantAssaultShip:
    def test_SHD_151_plus_two_when_defender_has_more_resources(self, repo):
        """SHD_151 On Attack: +2/+0 if the defending player controls more resources."""
        from swu.engine.actions import compute_power
        valiant = _get_card(repo, "SHD", "151")
        # Opponent has more resources -> bonus applies.
        state = _make_state()
        v = _place(state, "P0", valiant, "space")
        _give_resources(state, "P0", 1, repo)
        _give_resources(state, "P1", 4, repo)
        state = _fire_on_attack(state, v)
        assert compute_power(state, state.find_instance(v.instance_id)[1]) == 5   # 3 + 2
        # Controller has at least as many -> no bonus.
        state = _make_state()
        v = _place(state, "P0", valiant, "space")
        _give_resources(state, "P0", 4, repo)
        _give_resources(state, "P1", 4, repo)
        state = _fire_on_attack(state, v)
        assert compute_power(state, state.find_instance(v.instance_id)[1]) == 3


class TestClanChallengers:
    def test_SHD_169_gains_overwhelm_while_upgraded(self, repo):
        """SHD_169: gains Overwhelm while it is upgraded."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        cc = _place(state, "P0", _get_card(repo, "SHD", "169"), "ground")
        assert not has_keyword(state, cc, Keyword.OVERWHELM)
        _attach_upgrade_directly(state, cc, _get_card(repo, "SOR", "53"), "P0")
        assert has_keyword(state, cc, Keyword.OVERWHELM)


class TestBravado:
    def test_SHD_182_readies_a_unit(self, repo):
        """SHD_182: Ready a unit (the always-present effect)."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        unit.exhausted = True
        state, _ev = _play_event_from_hand(state, repo, "SHD", "182", owner="P0")
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == unit.instance_id)
        state = apply(state, pick)
        assert not state.find_instance(unit.instance_id)[1].exhausted

    def test_SHD_182_costs_two_less_after_enemy_defeat(self, repo):
        """SHD_182: costs 2 less if an enemy unit was defeated this phase."""
        from swu.engine.actions import apply, PlayCard

        def _paid(enemy_defeated):
            state = _make_state()
            _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # a ready target
            ev = _put_in_hand(state, "P0", _get_card(repo, "SHD", "182"))
            _give_resources(state, "P0", 12, repo)
            if enemy_defeated:
                state.game_memory.defeated_controllers_this_round.append("P1")
            before = state.player_by_id("P0").available_resources
            state = apply(state, PlayCard(ev.instance_id))
            return before - state.player_by_id("P0").available_resources

        assert _paid(enemy_defeated=True) == _paid(enemy_defeated=False) - 2


class TestKintanIntimidator:
    def test_SHD_183_on_attack_exhausts_defender(self, repo):
        """SHD_183 On Attack: Exhaust the defender."""
        state = _make_state()
        kintan = _place(state, "P0", _get_card(repo, "SHD", "183"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not defender.exhausted
        state = _fire_on_attack(state, kintan, defender)
        assert state.find_instance(defender.instance_id)[1].exhausted


class TestDoctorEvazan:
    def test_SHD_185_bounty_readies_collector_resources(self, repo):
        """SHD_185 Bounty: collector readies up to 12 of their own resources."""
        state = _make_state()
        evazan = _place(state, "P1", _get_card(repo, "SHD", "185"), "ground")
        _give_resources(state, "P0", 4, repo)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _defeat_and_fire(state, evazan, "P1")
        assert all(not r.exhausted for r in state.player_by_id("P0").resources)


class TestHeroicResolve:
    """SHD_155 — an Upgrade that grants its host an ACTIVATED ability (the
    shd-set:16 framework session): "Action [2 resources, defeat a Heroic Resolve on
    this unit]: Attack with this unit. It gets +4/+0 and gains Overwhelm for this
    attack." """

    def test_SHD_155_granted_action_costs_and_defeats_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        host_def = _get_card(repo, "SOR", "46")  # Consular Security Force, power 3, ready
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SHD", "155"), "P0")
        _give_resources(state, "P0", 5, repo)

        # The granted Action is surfaced in legal_actions, addressed by the UPGRADE's id.
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == up.instance_id)
        res_before = state.player_by_id("P0").available_resources
        state = apply(state, use)

        # Cost paid: 2 resources exhausted, and THIS upgrade defeated to P0's discard.
        assert state.player_by_id("P0").available_resources == res_before - 2
        _, host_after = state.find_instance(host.instance_id)
        assert host_after.attached_upgrades == []
        assert any(c.instance_id == up.instance_id
                   for c in state.player_by_id("P0").discard)

        # Effect: a granted attack pinned to the host, +4/+0 and Overwhelm for it.
        dec = state.pending_decisions[-1]
        assert dec.kind == "granted_attack"
        assert dec.context["attacker_id"] == host.instance_id
        assert dec.context["power_bonus"] == 4
        assert dec.context["grant_keywords"] == ["Overwhelm"]

        # Resolve it against the enemy base: it lands host power + 4.
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == host.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == host_def.power + 4

    def test_SHD_155_overwhelm_carries_excess_to_base(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        host_def = _get_card(repo, "SOR", "46")   # power 3 -> 7 with +4
        enemy_def = _get_card(repo, "SHD", "40")  # a small enemy unit
        state = _make_state()
        host = _place(state, "P0", host_def, "ground")
        enemy = _place(state, "P1", enemy_def, "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SHD", "155"), "P0")
        _give_resources(state, "P0", 5, repo)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == up.instance_id)
        state = apply(state, use)

        # Attack the small enemy: the granted Overwhelm carries excess to the base.
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == host.instance_id
                   and a.defender_id == enemy.instance_id)
        state = apply(state, atk)
        # The enemy is defeated (no longer in its arena) and the excess spills over.
        assert enemy.instance_id not in {c.instance_id for c in state.players[1].ground_arena}
        excess = (host_def.power + 4) - enemy_def.hp
        assert state.players[1].base_instance.damage - base_before == excess


# ── Combat tricks, buffs & tempo (shd-set:17) ─────────────────────────────────

class TestHunterOfTheHaxionBrood:
    def test_SHD_186_shielded_only_while_enemy_has_bounty(self, repo):
        """SHD_186 — gains Shielded only while an enemy unit carries a Bounty."""
        from swu.engine.keywords import has_keyword, Keyword
        hunter = _get_card(repo, "SHD", "186")
        bounty_unit = _get_card(repo, "SHD", "95")  # Clone Deserter: registered Bounty ability
        state = _make_state()
        hunter_ci = _place(state, "P0", hunter, "ground")
        # No enemy bounty unit yet -> not Shielded.
        assert not has_keyword(state, hunter_ci, Keyword.SHIELDED)
        # An enemy Bounty unit switches the conditional Shielded on.
        _place(state, "P1", bounty_unit, "ground")
        assert has_keyword(state, hunter_ci, Keyword.SHIELDED)


class TestFourLomAndZuckuss:
    def test_SHD_188_buffs_named_zuckuss(self, repo):
        """SHD_188 — each friendly unit named Zuckuss gets +1/+1 and gains Ambush."""
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        four_lom = _get_card(repo, "SHD", "188")
        zuckuss = _get_card(repo, "SHD", "190")
        state = _make_state()
        z_ci = _place(state, "P0", zuckuss, "ground")
        # Zuckuss alone: base 6/6, no Ambush.
        assert compute_power(state, z_ci) == 6
        assert compute_hp(state, z_ci) == 6
        assert not has_keyword(state, z_ci, Keyword.AMBUSH)
        # Add 4-LOM -> the name-anthem buffs Zuckuss.
        _place(state, "P0", four_lom, "ground")
        assert compute_power(state, z_ci) == 7
        assert compute_hp(state, z_ci) == 7
        assert has_keyword(state, z_ci, Keyword.AMBUSH)

    def test_SHD_190_buffs_named_four_lom(self, repo):
        """SHD_190 — each friendly unit named 4-LOM gets +1/+1 and gains Saboteur."""
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        four_lom = _get_card(repo, "SHD", "188")
        zuckuss = _get_card(repo, "SHD", "190")
        state = _make_state()
        f_ci = _place(state, "P0", four_lom, "ground")
        # 4-LOM alone: base 4/4, no Saboteur.
        assert compute_power(state, f_ci) == 4
        assert compute_hp(state, f_ci) == 4
        assert not has_keyword(state, f_ci, Keyword.SABOTEUR)
        # Add Zuckuss -> the mirror anthem buffs 4-LOM.
        _place(state, "P0", zuckuss, "ground")
        assert compute_power(state, f_ci) == 5
        assert compute_hp(state, f_ci) == 5
        assert has_keyword(state, f_ci, Keyword.SABOTEUR)


class TestSlaversFreighter:
    def test_SHD_189_ready_power_capped_by_enemy_upgrades(self, repo):
        """SHD_189 — may ready another unit whose power <= the number of upgrades on
        enemy units; a higher-power unit is not an eligible target."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        freighter = _get_card(repo, "SHD", "189")
        low = _get_card(repo, "SOR", "46")   # Consular Security Force, power 3
        high = _get_card(repo, "SHD", "190")  # Zuckuss, power 6
        upg = _get_card(repo, "SOR", "53")   # a real upgrade to stack on the enemy
        state = _make_state()
        freighter_ci = _place(state, "P0", freighter, "space")
        low_ci = _place(state, "P0", low, "ground")
        low_ci.exhausted = True
        high_ci = _place(state, "P0", high, "ground")
        high_ci.exhausted = True
        enemy_ci = _place(state, "P1", _get_card(repo, "SHD", "40"), "ground")
        # Three upgrades on the enemy unit -> power cap = 3.
        for _ in range(3):
            _attach_upgrade_directly(state, enemy_ci, upg, "P1")

        state = _fire_when_played(state, freighter_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert low_ci.instance_id in targets       # power 3 <= 3
        assert high_ci.instance_id not in targets   # power 6 > 3
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == low_ci.instance_id)
        state = apply(state, choose)
        assert _find_instance(state, low_ci.instance_id).exhausted is False

    def test_SHD_189_no_enemy_upgrades_offers_nothing(self, repo):
        """With 0 upgrades on enemy units the cap is 0, so a power-3 unit can't be
        readied and the optional trigger is skipped silently."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        freighter = _get_card(repo, "SHD", "189")
        low = _get_card(repo, "SOR", "46")   # power 3 > 0
        state = _make_state()
        freighter_ci = _place(state, "P0", freighter, "space")
        low_ci = _place(state, "P0", low, "ground")
        low_ci.exhausted = True
        _place(state, "P1", _get_card(repo, "SHD", "40"), "ground")  # no upgrades
        state = _fire_when_played(state, freighter_ci)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestFrozenInCarbonite:
    def test_SHD_193_exhausts_host_and_forbids_ready(self, repo):
        """SHD_193 — When Played exhausts the host; the host then can't ready (the
        upgrade-granted ReadyRestriction holds through the regroup ready step)."""
        from swu.engine.actions import _ready_forbidden, _ready_all_cards
        frozen = _get_card(repo, "SHD", "193")
        host = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", host, "ground")
        up = _attach_upgrade_directly(state, host_ci, frozen, "P0")
        state = _fire_upgrade_played(state, up, host_ci)
        # When Played exhausted the host.
        assert host_ci.exhausted is True
        # The upgrade forbids the host from readying.
        assert _ready_forbidden(state, host_ci) is True
        # A regroup ready step leaves the frozen host exhausted.
        _ready_all_cards(state)
        assert host_ci.exhausted is True


class TestL337:
    def test_SHD_197_shield_when_no_captive(self, repo):
        """SHD_197 — When Played with nothing to rescue: give a Shield token to
        this unit."""
        from swu.engine.keywords import shields_on
        l337 = _get_card(repo, "SHD", "197")
        state = _make_state()
        l337_ci = _place(state, "P0", l337, "ground")
        state = _fire_when_played(state, l337_ci)
        assert shields_on(l337_ci) == 1

    def test_SHD_197_rescues_friendly_captive(self, repo):
        """SHD_197 — When Played rescues a friendly captured card to its owner's
        hand (and gives no shield)."""
        from swu.engine.keywords import shields_on
        from swu.engine.state import CardInstance, Zone
        import uuid
        l337 = _get_card(repo, "SHD", "197")
        captive_def = _get_card(repo, "SOR", "46")
        state = _make_state()
        l337_ci = _place(state, "P0", l337, "ground")
        captive = CardInstance(
            instance_id=f"cap_{uuid.uuid4().hex[:6]}", card_def=captive_def,
            owner_id="P0", zone=Zone.CAPTURE_PILE)
        captive.captured_by = "some_captor"
        captive.face_down = True
        state.player_by_id("P1").capture_pile.append(captive)

        state = _fire_when_played(state, l337_ci)
        # Captive returned to P0's hand; no shield given.
        assert any(c.instance_id == captive.instance_id
                   for c in state.player_by_id("P0").hand)
        assert captive not in state.player_by_id("P1").capture_pile
        assert shields_on(l337_ci) == 0


class TestCoruscantDissident:
    def test_SHD_199_readies_a_resource_on_attack(self, repo):
        """SHD_199 — On Attack: ready a resource (readies one exhausted resource)."""
        dissident = _get_card(repo, "SHD", "199")
        state = _make_state()
        d_ci = _place(state, "P0", dissident, "ground")
        _give_resources(state, "P0", 2, repo)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _fire_on_attack(state, d_ci)
        ready = [r for r in state.player_by_id("P0").resources if not r.exhausted]
        assert len(ready) == 1


# ── Combat tricks, buffs & tempo (shd-set:18) ─────────────────────────────────

class TestPrincipledOutlaw:
    def test_SHD_201_on_attack_may_exhaust_a_ground_unit(self, repo):
        """SHD_201 — On Attack: You may exhaust a ground unit."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        outlaw = _get_card(repo, "SHD", "201")
        state = _make_state()
        outlaw_ci = _place(state, "P0", outlaw, "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = False
        state = _fire_on_attack(state, outlaw_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        _, enemy_after = state.find_instance(enemy.instance_id)
        assert enemy_after.exhausted


class TestMillenniumFalcon:
    def test_SHD_204_gains_ambush_only_when_played_from_hand(self, repo):
        """SHD_204 — printed Ambush is stripped (the marker owns it); a hand play
        grants Ambush, a direct (non-hand) entry does not."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard
        from swu.engine.keywords import has_keyword, Keyword
        import uuid
        falcon = _get_card(repo, "SHD", "204")
        # Direct placement (not a hand play) → printed Ambush stripped, no grant.
        state = _make_state()
        direct = _place(state, "P0", falcon, "space")
        assert not has_keyword(state, direct, Keyword.AMBUSH)
        # A real hand play → the marker grants Ambush before the enter-play bus.
        state2 = _make_state()
        ci = CardInstance(instance_id=f"fal_{uuid.uuid4().hex[:6]}", card_def=falcon,
                          owner_id="P0", zone=Zone.HAND)
        state2.player_by_id("P0").hand.append(ci)
        _fill_resources(state2, "P0", 12, repo)  # cost 6 + 4 off-aspect penalty
        play = next(a for a in legal_actions(state2)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id)
        state2 = apply(state2, play)
        _, unit = state2.find_instance(ci.instance_id)
        assert has_keyword(state2, unit, Keyword.AMBUSH)


class TestFinalShowdown:
    def test_SHD_208_readies_all_and_loses_at_regroup(self, repo):
        """SHD_208 — Ready each unit you control; at the start of regroup, you lose."""
        from swu.engine.actions import _enter_regroup
        state, _evt = None, None
        state = _make_state()
        u1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        u1.exhausted = True
        u2.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "SHD", "208", owner="P0")
        # Both units readied and the controller is scheduled to lose.
        assert not _find_instance(state, u1.instance_id).exhausted
        assert not _find_instance(state, u2.instance_id).exhausted
        assert "P0" in state.game_memory.lose_at_regroup
        # Reaching regroup ends the game with P0 the loser.
        _enter_regroup(state)
        assert state.winner == "P1"


class TestFugitiveWookiee:
    def test_SHD_211_bounty_exhausts_a_unit_for_the_collector(self, repo):
        """SHD_211 — Bounty — Exhaust a unit (the collector auto-exhausts the best
        ready opposing unit)."""
        wookiee = _get_card(repo, "SHD", "211")
        state = _make_state()
        wookiee_ci = _place(state, "P0", wookiee, "ground")
        # A ready P0 unit the collector (P1) will exhaust when it collects the bounty.
        victim = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim.exhausted = False
        _defeat_and_fire(state, wookiee_ci, "P0")
        _, victim_after = state.find_instance(victim.instance_id)
        assert victim_after.exhausted


class TestPrivateerScyk:
    def test_SHD_212_shielded_while_controlling_another_cunning_unit(self, repo):
        """SHD_212 — While you control another Cunning unit, this unit gains Shielded."""
        from swu.engine.keywords import has_keyword, Keyword
        scyk = _get_card(repo, "SHD", "212")
        state = _make_state()
        scyk_ci = _place(state, "P0", scyk, "space")
        # No other Cunning unit → no Shielded (printed Shielded stripped).
        assert not has_keyword(state, scyk_ci, Keyword.SHIELDED)
        # Another Cunning unit (Principled Outlaw SHD_201) → Shielded now on.
        _place(state, "P0", _get_card(repo, "SHD", "201"), "ground")
        assert has_keyword(state, scyk_ci, Keyword.SHIELDED)


class TestLetTheWookieeWin:
    """SHD_205 — the new opponent-decided modal (the OPPONENT picks the mode, the
    CONTROLLER executes it)."""

    def test_SHD_205_opponent_ready_resources_mode(self, repo):
        """Opponent picks 'ready up to 6 resources' → the controller readies up to
        six of their own exhausted resources (and no more)."""
        from swu.engine.actions import legal_actions, apply, ChooseWookieeMode
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "SHD", "205", owner="P0")
        # Set up exactly eight exhausted resources for P0 (done after the play, whose
        # cost would otherwise exhaust a couple); only six may be readied.
        res = state.player_by_id("P0").resources
        assert len(res) >= 8
        for i, r in enumerate(res):
            r.exhausted = (i < 8)
        exhausted_before = sum(1 for r in res if r.exhausted)
        assert exhausted_before == 8
        top = state.pending_decisions[-1]
        assert top.kind == "let_wookiee_win" and top.deciding_player_id == "P1"
        mode = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseWookieeMode) and a.mode == "ready_resources")
        state = apply(state, mode)
        assert not state.pending_decisions
        exhausted_after = sum(1 for r in state.player_by_id("P0").resources if r.exhausted)
        assert exhausted_before - exhausted_after == 6  # "up to 6" — capped

    def test_SHD_205_opponent_ready_attack_wookiee_mode(self, repo):
        """Opponent picks 'ready a friendly unit; if Wookiee, attack +2/+0' → the
        controller readies a chosen Wookiee, which then attacks the base for
        power+2 (5 from a 3/3 Fugitive Wookiee)."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseWookieeMode, ChooseWookieeReadyUnit,
            AttackWithUnit)
        state = _make_state()
        wook = _place(state, "P0", _get_card(repo, "SHD", "211"), "ground")  # 3/3 Wookiee
        wook.exhausted = True
        base_before = state.player_by_id("P1").base_instance.damage
        state, _ = _play_event_from_hand(state, repo, "SHD", "205", owner="P0")
        # The opponent (P1) decides the mode.
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        mode = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseWookieeMode) and a.mode == "ready_attack")
        state = apply(state, mode)
        # Control shifts to the controller (P0) to ready a unit.
        top = state.pending_decisions[-1]
        assert top.kind == "let_wookiee_win" and top.deciding_player_id == "P0"
        ready = next(a for a in legal_actions(state)
                     if isinstance(a, ChooseWookieeReadyUnit)
                     and a.unit_id == wook.instance_id)
        state = apply(state, ready)
        _, wook_after = state.find_instance(wook.instance_id)
        assert not wook_after.exhausted  # readied
        # A granted attack pinned to the Wookiee is now pending for P0.
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == wook.instance_id and a.defender_id is None)
        state = apply(state, atk)
        dealt = state.player_by_id("P1").base_instance.damage - base_before
        assert dealt == 5  # 3 power + 2 for this attack


class TestDJ:
    def test_SHD_213_smuggle_steals_enemy_resource_and_reverts_on_leave_play(self, repo):
        """SHD_213 — When played using Smuggle: take control of an enemy resource;
        when DJ leaves play, that resource's owner takes it back."""
        from swu.engine.actions import (
            legal_actions, apply, SmugglePlay, _revert_orphaned_resource_control)
        dj = _get_card(repo, "SHD", "213")  # Smuggle [7 resources Cunning Cunning]
        state = _make_state()
        smug = _add_resource(state, "P0", dj)
        _fill_resources(state, "P0", 15, repo)   # cover smuggle cost 7 + off-aspect
        _add_deck_card(state, "P0", repo)        # replaces DJ in the resource zone
        # A ready P1 resource to be stolen.
        victim = _add_resource(state, "P1", _get_card(repo, "SOR", "46"))
        victim.exhausted = False

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)

        _, dj_unit = state.find_instance(smug.instance_id)
        assert dj_unit.zone.name in ("GROUND_ARENA", "SPACE_ARENA")
        p0_ids = {r.instance_id for r in state.player_by_id("P0").resources}
        p1_ids = {r.instance_id for r in state.player_by_id("P1").resources}
        assert victim.instance_id in p0_ids      # stolen to the controller
        assert victim.instance_id not in p1_ids
        stolen = next(r for r in state.player_by_id("P0").resources
                      if r.instance_id == victim.instance_id)
        assert stolen.control_linked_to == dj_unit.instance_id

        # DJ leaves play → the settle-time backstop reverts the resource to P1.
        _defeat_and_fire(state, dj_unit, "P0")
        _revert_orphaned_resource_control(state)
        p0_ids = {r.instance_id for r in state.player_by_id("P0").resources}
        p1_ids = {r.instance_id for r in state.player_by_id("P1").resources}
        assert victim.instance_id in p1_ids      # back to its owner
        assert victim.instance_id not in p0_ids
        reverted = next(r for r in state.player_by_id("P1").resources
                        if r.instance_id == victim.instance_id)
        assert reverted.control_linked_to is None


# ── shd-set:19 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestTobiasBeckett:
    def test_SHD_217_exhausts_le_cost_unit_once_per_round(self, repo):
        """When you play a NON-UNIT card: may exhaust a unit that costs ≤ that card;
        only once each round."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        tobias = _place(state := _make_state(), "P0",
                        _get_card(repo, "SHD", "217"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SHD", "40"), "ground")  # cost 2
        # Play a non-unit card (Relentless Pursuit event, cost 3) — put it in discard
        # so find_instance resolves its type/cost, then fire CardPlayed.
        evt = _put_in_hand(state, "P0", _get_card(repo, "SHD", "232"))
        from swu.engine.state import Zone
        state.player_by_id("P0").hand.remove(evt)
        evt.zone = Zone.DISCARD
        state.player_by_id("P0").discard.append(evt)
        state = _fire_card_played(state, "P0", evt)

        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger)
                      and a.source_id == tobias.instance_id)
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        _, hit = state.find_instance(enemy.instance_id)
        assert hit.exhausted is True

        # Second non-unit play this round: the once-per-round gate blocks the trigger.
        evt2 = _put_in_hand(state, "P0", _get_card(repo, "SHD", "227"))
        state.player_by_id("P0").hand.remove(evt2)
        evt2.zone = Zone.DISCARD
        state.player_by_id("P0").discard.append(evt2)
        state = _fire_card_played(state, "P0", evt2)
        assert not any(isinstance(a, AcceptTrigger)
                       and a.source_id == tobias.instance_id
                       for a in legal_actions(state))


class TestLookTheOtherWay:
    def test_SHD_227_controller_pays_two_to_avoid_exhaust(self, repo):
        """Exhaust a unit unless its controller pays 2 resources."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, PayToAvoidExhaust, AcceptExhaust)
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SHD", "40"), "ground")
        _give_resources(state, "P1", 3, repo)   # P1 can afford 2
        state, _ = _play_event_from_hand(state, repo, "SHD", "227", owner="P0")
        # Target the enemy unit.
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        # The decision is now addressed to P1 (the unit's controller): pay 2 or exhaust.
        top = state.pending_decisions[-1]
        assert top.kind == "pay_or_exhaust" and top.deciding_player_id == "P1"
        assert top.context["pay_amount"] == 2
        acts = legal_actions(state)
        assert any(isinstance(a, PayToAvoidExhaust) for a in acts)
        assert any(isinstance(a, AcceptExhaust) for a in acts)
        ready_before = sum(1 for r in state.player_by_id("P1").resources
                           if not r.exhausted)
        pay = next(a for a in acts if isinstance(a, PayToAvoidExhaust))
        state = apply(state, pay)
        _, kept = state.find_instance(enemy.instance_id)
        assert kept.exhausted is False   # paid → stays ready
        ready_after = sum(1 for r in state.player_by_id("P1").resources
                          if not r.exhausted)
        assert ready_before - ready_after == 2   # paid exactly 2


class TestSwoopDown:
    def test_SHD_230_space_unit_hits_ground_with_bonus(self, repo):
        """Attack with a space unit; it can attack ground units, and vs a ground
        unit it gets +2/+0 (cross_arena + bonus_if_defender_ground)."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")  # 2/1
        defender = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")  # 9/9
        state, _ = _play_event_from_hand(state, repo, "SHD", "230", owner="P0")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack" and top.deciding_player_id == "P0"
        # The space attacker may reach the enemy GROUND unit (cross-arena grant).
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = apply(state, atk)
        _, hit = state.find_instance(defender.instance_id)
        assert hit.damage == 4   # 2 power + 2 for attacking a ground unit


class TestRelentlessPursuit:
    def test_SHD_232_bounty_hunter_captor_gets_shield_and_captures(self, repo):
        """Choose a friendly unit; it captures an enemy non-leader costing ≤ it; a
        Bounty Hunter captor also gets a Shield."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SHD", "120"), "ground")  # BH, cost 5
        prey = _place(state, "P1", _get_card(repo, "SHD", "211"), "ground")    # cost 2
        state, _ = _play_event_from_hand(state, repo, "SHD", "232", owner="P0")
        # Stage 1: choose the friendly captor.
        pick_captor = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget)
                           and a.target_id == captor.instance_id)
        state = apply(state, pick_captor)
        _, captor_now = state.find_instance(captor.instance_id)
        assert _shield_count(captor_now) == 1   # Bounty Hunter → Shield
        # Stage 2: capture the ≤5-cost enemy.
        pick_prey = next(a for a in legal_actions(state)
                         if isinstance(a, ChooseTarget)
                         and a.target_id == prey.instance_id)
        state = apply(state, pick_prey)
        p1_arena_ids = {u.instance_id for u in state.player_by_id("P1").ground_arena}
        assert prey.instance_id not in p1_arena_ids   # left P1's arena
        cap = state.player_by_id("P0").capture_pile
        assert any(c.instance_id == prey.instance_id
                   and c.captured_by == captor.instance_id for c in cap)


# ── shd-set:20 — Miscellaneous abilities ─────────────────────────────────────

def _attach_upgrade_ci(state, host_ci, upgrade_def, owner_id):
    """Attach a fresh upgrade CardInstance directly onto ``host_ci``."""
    from swu.engine.state import CardInstance
    import uuid as _u
    up = CardInstance(
        instance_id=f"{owner_id}_up_{_u.uuid4().hex[:6]}",
        card_def=upgrade_def, owner_id=owner_id, zone=host_ci.zone)
    host_ci.attached_upgrades.append(up)
    return up


def _fire_card_played_evt(state, ci, cost_paid=0):
    """Fire a CardPlayed observer event for ``ci`` (WhenYouPlayCard hook)."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=ci.owner_id, instance_id=ci.instance_id,
                     card_name=ci.card_def.display_name, cost_paid=cost_paid)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestFennecShandLeader:
    """SHD_16 — undeployed Action [1 resource, Exhaust]: play a unit costing 4 or
    less from hand, giving it Ambush this phase."""

    def test_SHD_16_plays_le4_unit_with_ambush(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        fennec = _get_card(repo, "SHD", "16")
        cheap = _get_card(repo, "SOR", "46")    # cost 4 — eligible
        pricey = _get_card(repo, "SHD", "120")  # cost 5 — ineligible
        state = _make_state()
        fennec_ci = _place_leader(state, "P0", fennec)
        cheap_ci = _put_in_hand(state, "P0", cheap)
        pricey_ci = _put_in_hand(state, "P0", pricey)
        _give_resources(state, "P0", 8, repo)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility)
                   and a.source_id == fennec_ci.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert cheap_ci.instance_id in offered
        assert pricey_ci.instance_id not in offered   # cost 5 > 4

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == cheap_ci.instance_id)
        state = apply(state, play)
        _, in_play = state.find_instance(cheap_ci.instance_id)
        assert in_play.zone.name == "GROUND_ARENA"
        assert has_keyword(state, in_play, Keyword.AMBUSH)   # granted for the phase
        _, fennec_now = state.find_instance(fennec_ci.instance_id)
        assert fennec_now.exhausted


class TestMysticReflection:
    """SHD_51 — give an enemy unit −2/−0 (−2/−2 if you control a Force unit)."""

    def test_SHD_51_minus_two_two_with_force_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_power, compute_hp)
        target = _place(state := _make_state(), "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")  # a Force unit
        p0 = compute_power(state, target), compute_hp(state, target)
        state, _ = _play_event_from_hand(state, repo, "SHD", "51", owner="P0")
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget)
                    and a.target_id == target.instance_id)
        state = apply(state, pick)
        _, hit = state.find_instance(target.instance_id)
        assert compute_power(state, hit) == p0[0] - 2
        assert compute_hp(state, hit) == p0[1] - 2   # Force unit → also −2 hp

    def test_SHD_51_minus_two_zero_without_force_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_hp)
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # NOT a Force unit
        base_hp = compute_hp(state, target)
        state, _ = _play_event_from_hand(state, repo, "SHD", "51", owner="P0")
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget)
                    and a.target_id == target.instance_id)
        state = apply(state, pick)
        _, hit = state.find_instance(target.instance_id)
        assert compute_hp(state, hit) == base_hp   # no Force unit → hp unchanged


class TestFennRau:
    """SHD_67 — When Played: you may play an upgrade from hand at −2; When you play
    an upgrade on this unit: give an enemy unit −2/−2."""

    def test_SHD_67_plays_upgrade_from_hand_discounted(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayUpgradeFromHand, _play_cost)
        state = _make_state()
        fenn = _place(state, "P0", _get_card(repo, "SHD", "67"), "ground")
        upg = _put_in_hand(state, "P0", _get_card(repo, "SOR", "54"))  # cost 3 upgrade
        _give_resources(state, "P0", 12, repo)
        ps0 = state.player_by_id("P0")
        full = _play_cost(state, upg, ps0, target_host_id=fenn.instance_id)
        before = ps0.available_resources
        state = _fire_when_played(state, fenn)
        assert state.pending_decisions[-1].kind == "play_upgrade_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayUpgradeFromHand)
                    and a.upgrade_id == upg.instance_id
                    and a.host_id == fenn.instance_id)
        state = apply(state, play)
        _, host = state.find_instance(fenn.instance_id)
        assert any(u.instance_id == upg.instance_id for u in host.attached_upgrades)
        # Paid the −2 discounted cost.
        assert before - state.player_by_id("P0").available_resources == max(0, full - 2)

    def test_SHD_67_upgrade_on_self_debuffs_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        fenn = _place(state, "P0", _get_card(repo, "SHD", "67"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_ci(state, fenn, _get_card(repo, "SOR", "69"), "P0")
        base_power = compute_power(state, enemy)
        state = _fire_card_played_evt(state, upg)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget)
                    and a.target_id == enemy.instance_id)
        state = apply(state, pick)
        _, hit = state.find_instance(enemy.instance_id)
        assert compute_power(state, hit) == base_power - 2


class TestEvidenceOfTheCrime:
    """SHD_77 — take control of an upgrade costing ≤3 and attach it to an eligible
    unit of your choice."""

    def test_SHD_77_steals_upgrade_onto_chosen_host(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        my_unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        upg = _attach_upgrade_ci(state, enemy, _get_card(repo, "SOR", "69"), "P1")  # cost 1
        state, _ = _play_event_from_hand(state, repo, "SHD", "77", owner="P0")
        # Stage 1: choose the ≤3-cost upgrade.
        pick_up = next(a for a in legal_actions(state)
                       if isinstance(a, ChooseTarget)
                       and a.target_id == upg.instance_id)
        state = apply(state, pick_up)
        # Stage 2: attach it to my unit.
        pick_host = next(a for a in legal_actions(state)
                         if isinstance(a, ChooseTarget)
                         and a.target_id == my_unit.instance_id)
        state = apply(state, pick_host)
        _, mine = state.find_instance(my_unit.instance_id)
        _, foe = state.find_instance(enemy.instance_id)
        assert any(u.instance_id == upg.instance_id for u in mine.attached_upgrades)
        assert all(u.instance_id != upg.instance_id for u in foe.attached_upgrades)


class TestEphantMon:
    """SHD_88 — On Attack: choose an enemy non-leader unit that attacked your base
    this phase; a friendly unit in the same arena captures it."""

    def test_SHD_88_captures_base_attacker_via_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        ephant = _place(state, "P0", _get_card(repo, "SHD", "88"), "ground")
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        other = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")  # didn't attack
        # Seed the base-attacker record: prey attacked P0's base this phase.
        state.game_memory.base_attackers_this_round["P0"] = [prey.instance_id]

        state = _fire_on_attack(state, ephant)   # Ephant's On Attack (vs base)
        # Stage 1: only the recorded base-attacker is offered.
        prey_choices = {a.target_id for a in legal_actions(state)
                        if isinstance(a, ChooseTarget)}
        assert prey.instance_id in prey_choices
        assert other.instance_id not in prey_choices   # never attacked the base
        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and a.target_id == prey.instance_id))
        # Stage 2: a friendly ground unit captures it.
        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and a.target_id == captor.instance_id))
        assert prey.instance_id not in {
            u.instance_id for u in state.player_by_id("P1").ground_arena}
        cap = state.player_by_id("P0").capture_pile
        assert any(c.instance_id == prey.instance_id
                   and c.captured_by == captor.instance_id for c in cap)


class TestImprisoned:
    """SHD_72 — Imprisoned (Upgrade): the attached non-leader unit loses its current
    abilities and can't gain abilities; the suppression lifts when it leaves play."""

    def test_SHD_72_suppresses_and_restores_host_keyword(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import _upgrade_target_spec
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "130"), "ground")  # Overwhelm
        assert has_keyword(state, host, Keyword.OVERWHELM)   # printed keyword present
        # Attach Imprisoned — the host's abilities/keywords are read-suppressed.
        imp = _attach_upgrade_ci(state, host, _get_card(repo, "SHD", "72"), "P0")
        _, h = state.find_instance(host.instance_id)
        assert not has_keyword(state, h, Keyword.OVERWHELM)  # suppressed while attached
        # "Attach to a non-leader unit" is parsed into a non_leader restriction.
        spec = _upgrade_target_spec(_get_card(repo, "SHD", "72"))
        assert spec is not None and "non_leader" in spec.predicates
        # Remove the upgrade → suppression lifts immediately (derived, no stored flag).
        h.attached_upgrades.remove(imp)
        assert has_keyword(state, h, Keyword.OVERWHELM)


class TestFinalizer:
    """SHD_92 — When Played: choose any number of friendly units, each captures an
    enemy non-leader unit in the SAME arena."""

    def test_SHD_92_units_capture_same_arena_enemies(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, CaptureWithUnit, FinishMultiCapture)
        state = _make_state()
        fin = _place(state, "P0", _get_card(repo, "SHD", "92"), "space")
        g_captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        s_captor = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")
        g_prey = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        s_prey = _place(state, "P1", _get_card(repo, "SOR", "140"), "space")
        state = _fire_when_played(state, fin)
        assert state.pending_decisions[-1].kind == "multi_capture_pairing"

        pairs = {(a.captor_id, a.prey_id) for a in legal_actions(state)
                 if isinstance(a, CaptureWithUnit)}
        assert (g_captor.instance_id, g_prey.instance_id) in pairs
        assert (s_captor.instance_id, s_prey.instance_id) in pairs
        assert (g_captor.instance_id, s_prey.instance_id) not in pairs  # cross-arena

        # Capture the ground prey with the ground captor.
        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, CaptureWithUnit) and a.captor_id == g_captor.instance_id))
        # That captor is spent; only same-arena space pairs remain.
        remaining = {(a.captor_id, a.prey_id) for a in legal_actions(state)
                     if isinstance(a, CaptureWithUnit)}
        assert all(c != g_captor.instance_id for c, _ in remaining)

        # Finish ("any number") without taking the space prey.
        state = apply(state, next(
            a for a in legal_actions(state) if isinstance(a, FinishMultiCapture)))
        assert not state.pending_decisions
        assert g_prey.instance_id not in {
            u.instance_id for u in state.player_by_id("P1").ground_arena}
        cap = state.player_by_id("P0").capture_pile
        assert any(c.instance_id == g_prey.instance_id
                   and c.captured_by == g_captor.instance_id for c in cap)
        # Space prey was left in play (we chose not to capture it).
        assert s_prey.instance_id in {
            u.instance_id for u in state.player_by_id("P1").space_arena}


class TestKraganGorr:
    def test_SHD_241_shields_friendly_unit_in_attacker_arena(self, repo):
        """When an enemy unit attacks your base: give a Shield to a friendly unit in
        the SAME arena as the attacker."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "241"), "ground")          # Kragan
        ground_ally = _place(state, "P0", _get_card(repo, "SHD", "40"), "ground")
        space_ally = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # ground
        state = _fire_on_attack(state, attacker)   # base attack (defender None)
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P0"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ground_ally.instance_id in offered      # same arena as attacker
        assert space_ally.instance_id not in offered   # other arena — not eligible
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == ground_ally.instance_id)
        state = apply(state, choose)
        _, shielded = state.find_instance(ground_ally.instance_id)
        assert _shield_count(shielded) == 1


# ── shd-set:21 — Miscellaneous abilities ─────────────────────────────────────

class TestRuleWithRespect:
    def test_SHD_106_friendly_unit_captures_base_attackers(self, repo):
        """SHD_106 — a chosen friendly unit captures EACH enemy non-leader that
        attacked your base this phase; other enemies are untouched."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        bystander = _place(state, "P1", _get_card(repo, "SOR", "140"), "space")
        # P1's `attacker` declared an attack on P0's base this phase
        state.game_memory.base_attackers_this_round["P0"] = [attacker.instance_id]

        state, _evt = _play_event_from_hand(state, repo, "SHD", "106", owner="P0")
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == captor.instance_id)
        state = apply(state, choose)

        cp_ids = [c.instance_id for c in state.player_by_id("P0").capture_pile]
        assert attacker.instance_id in cp_ids            # captured
        assert bystander.instance_id not in cp_ids       # never attacked the base
        assert any(c.instance_id == bystander.instance_id
                   for c in state.player_by_id("P1").space_arena)


class TestChooseSides:
    def test_SHD_132_exchanges_control(self, repo):
        """SHD_132 — a chosen friendly non-leader and a chosen enemy non-leader swap
        controllers (owners unchanged)."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")

        state, _evt = _play_event_from_hand(state, repo, "SHD", "132", owner="P0")
        pick_f = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == mine.instance_id)
        state = apply(state, pick_f)
        pick_e = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == theirs.instance_id)
        state = apply(state, pick_e)

        p0_ids = [c.instance_id for c in state.player_by_id("P0").ground_arena]
        p1_ids = [c.instance_id for c in state.player_by_id("P1").ground_arena]
        assert theirs.instance_id in p0_ids   # enemy unit now under P0's control
        assert mine.instance_id in p1_ids     # friendly unit now under P1's control


class TestLurkingTiePhantom:
    def test_SHD_187_immune_to_enemy_ability_capture_damage_defeat(self, repo):
        """SHD_187 — can't be captured, damaged, or defeated by enemy CARD abilities
        (combat, which never routes through these effects, is unaffected)."""
        from swu.engine.actions import _apply_capture
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import (
            DealDamage as _DD, DefeatUnit as _DU, TargetSpec as _TS)
        state = _make_state()
        phantom = _place(state, "P1", _get_card(repo, "SHD", "187"), "space")
        enemy_src = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        tid = phantom.instance_id

        # ability damage from an enemy source is prevented
        s2 = execute_effect(state, _DD(amount=3, target=_TS(controller="enemy", kind="unit")),
                            enemy_src, tid, {})
        assert s2.find_instance(tid)[1].damage == 0
        # capture by an enemy unit is prevented
        s3 = _apply_capture(state, enemy_src.instance_id, tid)
        assert not s3.player_by_id("P0").capture_pile
        assert any(c.instance_id == tid for c in s3.player_by_id("P1").space_arena)
        # defeat by an enemy ability is prevented
        s4 = execute_effect(state, _DU(target=_TS(controller="enemy", kind="unit")),
                            enemy_src, tid, {})
        assert s4.find_instance(tid) is not None


class TestQira:
    def test_SHD_202_names_hand_card_and_taxes_opponent(self, repo):
        """SHD_202 — When Played looks at an opponent's hand and names one of its
        cards; that named card then costs 3 more for the opponent to play."""
        from swu.engine.actions import legal_actions, apply, NameCard, _play_cost
        state = _make_state()
        qira = _place(state, "P0", _get_card(repo, "SHD", "202"), "ground")
        taxed = _get_card(repo, "SOR", "128")
        taxed_ci = _put_in_hand(state, "P1", taxed)

        state = _fire_when_played(state, qira)
        top = state.pending_decisions[-1]
        assert top.kind == "name_a_card"
        assert taxed.name in top.context["names"]           # offers the looked-at hand

        p1 = state.player_by_id("P1")
        cost_before = _play_cost(state, taxed_ci, p1)        # not yet named

        name_act = next(a for a in legal_actions(state)
                        if isinstance(a, NameCard) and a.name == taxed.name)
        state = apply(state, name_act)

        p1 = state.player_by_id("P1")
        cost_after = _play_cost(state, taxed_ci, p1)
        assert cost_after == cost_before + 3                 # the named card is taxed +3


class TestBountyHuntersQuarry:
    def test_SHD_123_collector_searches_and_plays_unit_free(self, repo):
        """SHD_123 — Bounty: the collector searches the top 5 of THEIR deck for a
        unit costing 3 or less and plays it for free under their control."""
        from swu.engine.actions import (
            legal_actions, apply, _defeat_unit, SelectSearchCard)
        host_def = _get_card(repo, "SOR", "46")     # non-unique host → window 5
        bhq = _get_card(repo, "SHD", "123")
        state = _make_state()
        host = _place(state, "P1", host_def, "ground")   # P1 controls the guarded host
        _attach_bounty_upgrade(state, host, bhq, "P0")   # P0 collects
        cheap = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # cost 1

        _defeat_unit(state, state.player_by_id("P1"), host)

        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.deciding_player_id == "P0"
        assert top.context["disposition"] == "play"
        assert cheap.instance_id in top.context["candidate_ids"]

        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)
                   and a.instance_id == cheap.instance_id)
        state = apply(state, sel)   # max_select 1 → auto-finishes and plays it free

        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P0").ground_arena)

    def test_SHD_123_unique_host_widens_window_to_ten(self, repo):
        """SHD_123 — a UNIQUE guarded host searches the top 10 instead of 5."""
        from swu.engine.actions import _defeat_unit
        unique_host = _get_card(repo, "SOR", "196")   # Chewbacca — unique
        bhq = _get_card(repo, "SHD", "123")
        state = _make_state()
        host = _place(state, "P1", unique_host, "ground")
        _attach_bounty_upgrade(state, host, bhq, "P0")
        # depth-10 target: push it first (deepest), then 9 fillers on top of it.
        state.player_by_id("P0").deck.clear()
        target = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # cost 1 unit
        for _ in range(9):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "137"))       # upgrade filler
        _defeat_unit(state, state.player_by_id("P1"), host)
        top = state.pending_decisions[-1]
        assert top.context["window"] == 10
        assert target.instance_id in top.context["candidate_ids"]


class TestDrydenVos:
    def test_SHD_192_plays_a_captured_unit_free_under_control(self, repo):
        """SHD_192 — When Played may play a captured card (guarded by a friendly
        unit) for free under the controller's control; owner is unchanged."""
        from swu.engine.actions import (
            legal_actions, apply, SelectCapturedToPlay, _apply_capture)
        state = _make_state()
        dryden = _place(state, "P0", _get_card(repo, "SHD", "192"), "ground")
        captor = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _apply_capture(state, captor.instance_id, prey.instance_id)
        assert any(c.instance_id == prey.instance_id
                   for c in state.player_by_id("P0").capture_pile)

        state = _fire_when_played(state, dryden)
        top = state.pending_decisions[-1]
        assert top.kind == "play_captured_card"
        assert prey.instance_id in top.context["candidate_ids"]

        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectCapturedToPlay)
                   and a.instance_id == prey.instance_id)
        state = apply(state, sel)

        p0_units = (state.player_by_id("P0").ground_arena
                    + state.player_by_id("P0").space_arena)
        played = next((c for c in p0_units if c.instance_id == prey.instance_id), None)
        assert played is not None                 # now in play under P0's control
        assert played.owner_id == "P1"            # ownership unchanged
        assert prey.instance_id not in [
            c.instance_id for c in state.player_by_id("P0").capture_pile]


class TestEndlessLegions:
    def _add_resource(self, state, owner_id, card_def):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(
            instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:6]}",
            card_def=card_def, owner_id=owner_id, zone=Zone.RESOURCES)
        ci.face_down = True
        state.player_by_id(owner_id).resources.append(ci)
        return ci

    def test_SHD_109_plays_revealed_unit_resources_for_free_one_at_a_time(self, repo):
        """SHD_109 — reveal resources and play each revealed UNIT for free, one at a
        time: each play removes the resource from the row and enters the arena; the
        loop re-offers the rest; a non-unit resource is never a candidate."""
        from swu.engine.actions import (
            legal_actions, apply, SelectResourceUnitToPlay, DeclineResourceUnitPlay)
        state = _make_state()
        u1 = self._add_resource(state, "P0", _get_card(repo, "SOR", "128"))  # a Unit
        u2 = self._add_resource(state, "P0", _get_card(repo, "SOR", "140"))  # a Unit
        ev = self._add_resource(state, "P0", _get_card(repo, "SHD", "106"))  # an Event

        state, _evt = _play_event_from_hand(state, repo, "SHD", "109",
                                            owner="P0", resources=14)
        top = state.pending_decisions[-1]
        assert top.kind == "play_resource_units"
        cand = set(top.context["candidate_ids"])
        assert {u1.instance_id, u2.instance_id} <= cand   # both units offered
        assert ev.instance_id not in cand                 # a non-unit is never offered
        # The controller may always stop (the "any number", including zero).
        assert any(isinstance(a, DeclineResourceUnitPlay) for a in legal_actions(state))

        # Play the first unit for free: it enters P0's arena and leaves the resource row.
        sel1 = next(a for a in legal_actions(state)
                    if isinstance(a, SelectResourceUnitToPlay)
                    and a.instance_id == u1.instance_id)
        state = apply(state, sel1)
        p0 = state.player_by_id("P0")
        assert u1.instance_id in [c.instance_id
                                  for c in (p0.ground_arena + p0.space_arena)]
        assert all(r.instance_id != u1.instance_id for r in p0.resources)

        # The loop re-offers only the remaining unit (one at a time).
        top = state.pending_decisions[-1]
        assert top.kind == "play_resource_units"
        assert u2.instance_id in top.context["candidate_ids"]
        assert u1.instance_id not in top.context["candidate_ids"]

        sel2 = next(a for a in legal_actions(state)
                    if isinstance(a, SelectResourceUnitToPlay)
                    and a.instance_id == u2.instance_id)
        state = apply(state, sel2)
        p0 = state.player_by_id("P0")
        assert u2.instance_id in [c.instance_id
                                  for c in (p0.ground_arena + p0.space_arena)]
        # No unit resources remain → the loop fully resolves (no lingering decision).
        assert not any(d.kind == "play_resource_units" for d in state.pending_decisions)

    def test_SHD_109_no_unit_resources_fizzles(self, repo):
        """With no Unit among the controller's resources, the event resolves with no
        play_resource_units decision (it fizzles cleanly)."""
        state = _make_state()
        self._add_resource(state, "P0", _get_card(repo, "SHD", "106"))  # an Event only
        state, _evt = _play_event_from_hand(state, repo, "SHD", "109",
                                            owner="P0", resources=18)
        assert not any(d.kind == "play_resource_units" for d in state.pending_decisions)


# ── shd-set:22 — Miscellaneous abilities ──────────────────────────────────────

def _attach_upgrade(state, host, card_def, owner_id):
    """Attach card_def to ``host`` as an upgrade instance (no play routing needed)."""
    from swu.engine.state import CardInstance
    import uuid as _u
    up = CardInstance(instance_id=f"{owner_id}_up_{_u.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=host.zone)
    host.attached_upgrades.append(up)
    return up


class TestSmugglersStarfighter:
    """SHD_215 — When Played: If you control another Underworld unit, give an
    enemy unit -3/-0 for this phase."""

    def test_SHD_215_debuffs_enemy_with_another_underworld_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "257"), "ground")   # Underworld Thug
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        ship = _place(state, "P0", _get_card(repo, "SHD", "215"), "space")

        state = _fire_when_played(state, ship)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        _, hit = state.find_instance(enemy.instance_id)
        assert compute_power(state, hit) == 0   # 3 power - 3

    def test_SHD_215_no_trigger_without_another_underworld_unit(self, repo):
        """The condition gates trigger COLLECTION — no prompt at all when unmet."""
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        ship = _place(state, "P0", _get_card(repo, "SHD", "215"), "space")

        state = _fire_when_played(state, ship)
        assert not state.pending_decisions


class TestEnfysNest:
    """SHD_219 — While a friendly unit (including this one) is attacking using
    Ambush, the defender gets -3/-0."""

    def _setup(self, repo):
        state = _make_state()
        enfys = _place(state, "P0", _get_card(repo, "SHD", "219"), "ground")  # 5/4
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        return state, enfys, defender

    def test_SHD_219_ambush_attack_debuffs_the_defender(self, repo):
        from swu.engine.actions import apply, UseAmbush
        from swu.engine.decisions import PendingDecision
        state, enfys, defender = self._setup(repo)
        state.pending_decisions.append(PendingDecision(
            deciding_player_id="P0", kind="ambush",
            context={"unit_id": enfys.instance_id}, after_resolve_player_index=1))
        state.active_player_index = 0

        state = apply(state, UseAmbush(enfys.instance_id, defender.instance_id))

        _, enfys_after = state.find_instance(enfys.instance_id)
        _, def_after = state.find_instance(defender.instance_id)
        assert def_after.damage == 5          # Enfys hits for her full 5
        assert enfys_after.damage == 0        # defender's 3 power - 3 = 0
        # The debuff is combat-scoped and must not linger.
        assert all(m.duration != "this_attack" for m in state.modifiers)

    def test_SHD_219_normal_attack_is_unaffected(self, repo):
        """Only an attack *using Ambush* gets the debuff."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state, enfys, defender = self._setup(repo)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == enfys.instance_id
                   and a.defender_id == defender.instance_id)
        state = apply(state, atk)
        _, enfys_after = state.find_instance(enfys.instance_id)
        assert enfys_after.damage == 3        # full defender power, no debuff


class TestBobaFettsArmor:
    """SHD_224 — If attached unit is Boba Fett and damage would be dealt to him,
    prevent 2 of that damage."""

    def _attack_host(self, repo, host_card):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "IBH", "56"), "ground")  # 5/7
        host = _place(state, "P1", host_card, "ground")
        _attach_upgrade(state, host, _get_card(repo, "SHD", "224"), "P1")
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == host.instance_id)
        state = apply(state, atk)
        return state, host

    def test_SHD_224_prevents_2_damage_to_boba_fett(self, repo):
        state, host = self._attack_host(repo, _get_card(repo, "SOR", "179"))  # Boba Fett 3/5
        _, boba = state.find_instance(host.instance_id)
        assert boba.damage == 3               # 5 incoming - 2 prevented

    def test_SHD_224_does_nothing_on_a_host_who_isnt_boba_fett(self, repo):
        state, host = self._attack_host(repo, _get_card(repo, "SOR", "46"))  # 3/7
        _, other = state.find_instance(host.instance_id)
        assert other.damage == 5              # full damage


class TestTarfful:
    """SHD_250 — When a friendly Wookiee unit is dealt combat damage and isn't
    defeated: That unit deals that much damage to an enemy ground unit."""

    def test_SHD_250_observes_another_friendly_wookiee_taking_combat_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "250"), "ground")           # Tarfful
        slaves = _place(state, "P0", _get_card(repo, "SHD", "200"), "ground")  # Wookiee 3/5
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 3/7

        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == slaves.instance_id
                   and a.defender_id == enemy.instance_id)
        state = apply(state, atk)
        # Tarfful is not the damaged unit — he observes the Slaves taking 3 and
        # surviving, then deals that much to an enemy ground unit.
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        _, hit = state.find_instance(enemy.instance_id)
        assert hit.damage == 6                # 3 combat + 3 from Tarfful's trigger

    def test_SHD_250_no_trigger_for_a_non_wookiee_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SHD", "250"), "ground")           # Tarfful
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not a Wookiee
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == trooper.instance_id
                   and a.defender_id == enemy.instance_id)
        state = apply(state, atk)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        _, hit = state.find_instance(enemy.instance_id)
        assert hit.damage == 3                # combat damage only


class TestMercenaryGunship:
    """SHD_256 — Action [4 resources]: Take control of this unit.  Any player may
    use this ability."""

    def test_SHD_256_opponent_can_pay_4_to_take_control(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        gunship = _place(state, "P1", _get_card(repo, "SHD", "256"), "space")
        _give_resources(state, "P0", 4, repo)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == gunship.instance_id)
        state = apply(state, use)

        holder, moved = state.find_instance(gunship.instance_id)
        assert holder.player_id == "P0"       # control follows the arena that holds it
        assert moved.owner_id == "P1"         # ownership never changes
        assert state.player_by_id("P0").available_resources == 0

    def test_SHD_256_not_offered_without_the_4_resources(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        gunship = _place(state, "P1", _get_card(repo, "SHD", "256"), "space")
        _give_resources(state, "P0", 3, repo)
        assert not any(isinstance(a, UseAbility) and a.source_id == gunship.instance_id
                       for a in legal_actions(state))

