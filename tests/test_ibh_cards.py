"""IBH card ability tests — the batch-18 easy-encode reprint sweep.

Every IBH card composes from existing engine primitives (no new decision kind).
Method names embed the card number so the reprint/encoding tooling's ``-k`` gate
selects them.  Reuses the DB-backed helpers from the SOR/SHD card tests.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_when_defeated,
    _fire_on_attack, _find_instance, _give_resources, _play_event_from_hand,
    _push_deck_top,
)
from tests.test_shd_cards import _put_in_hand


def _deck_units(state, owner, repo, n):
    """Push n draw-able cards onto owner's deck top."""
    for _ in range(n):
        _push_deck_top(state, owner, _get_card(repo, "SOR", "128"))


# ── Events ────────────────────────────────────────────────────────────────────

class TestWereInTrouble:
    """IBH_61 — Deal 3 damage to a unit."""

    def test_ibh_61_deals_3_to_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _ = _play_event_from_hand(state, repo, "IBH", "61")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert not state.pending_decisions


class TestTargetTheMainGenerator:
    """IBH_59 — Deal 2 damage to a base."""

    def test_ibh_59_deals_2_to_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy_base = state.player_by_id("P1").base_instance
        state, _ = _play_event_from_hand(state, repo, "IBH", "59")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy_base.instance_id))
        assert state.player_by_id("P1").base_instance.damage == 2


class TestTooStrongForBlasters:
    """IBH_66 — Heal 2 damage from a unit."""

    def test_ibh_66_heals_2_from_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        u = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u.damage = 3
        state, _ = _play_event_from_hand(state, repo, "IBH", "66")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == u.instance_id))
        assert _find_instance(state, u.instance_id).damage == 1


class TestGoForTheLegs:
    """IBH_18 — Exhaust an enemy ground unit."""

    def test_ibh_18_exhausts_enemy_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "IBH", "18")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert enemy.instance_id in offered
        assert friendly.instance_id not in offered  # "enemy" ground unit only
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted


class TestIllCoverForYou:
    """IBH_5 — Deal 1 to an enemy unit and 1 to another enemy unit."""

    def test_ibh_5_deals_1_to_two_distinct_enemy_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "IBH", "5")
        # First damage → e1.
        state = apply(state, ChooseTarget(e1.instance_id))
        # Second must be "another" enemy unit — e1 is no longer offered.
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert e2.instance_id in offered
        assert e1.instance_id not in offered
        state = apply(state, ChooseTarget(e2.instance_id))
        assert _find_instance(state, e1.instance_id).damage == 1
        assert _find_instance(state, e2.instance_id).damage == 1

    def test_ibh_5_only_one_enemy_unit_deals_1(self, repo):
        """With a single enemy unit the second effect has no 'another' target."""
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "IBH", "5")
        state = apply(state, ChooseTarget(e1.instance_id))
        # No second target available → fizzles to quiescence.
        assert not state.pending_decisions
        assert _find_instance(state, e1.instance_id).damage == 1


class TestImprovisedDetonation:
    """IBH_21 — Attack with a unit. It gets +2/+0 for this attack."""

    def test_ibh_21_grants_attack_with_bonus(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        u = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "IBH", "21")
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert u.instance_id in attackers


class TestIWantProofNotLeads:
    """IBH_74 — Draw 2 cards, then discard a card from your hand."""

    def test_ibh_74_draws_two_then_discards_one(self, repo):
        state = _make_state()
        filler = _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _deck_units(state, "P0", repo, 3)
        disc_before = len(state.player_by_id("P0").discard)
        state, _ = _play_event_from_hand(state, repo, "IBH", "74")
        # hand: [filler] + drew 2 - discarded 1 = 2
        assert len(state.player_by_id("P0").hand) == 2
        # discard grew by the played event + the discarded card = 2.
        assert len(state.player_by_id("P0").discard) == disc_before + 2
        assert not state.pending_decisions


class TestIveFoundThem:
    """IBH_9 — Reveal top 3, draw a unit, discard the other revealed cards."""

    def test_ibh_9_draws_a_unit_discards_rest(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        # Top 3: unit, event (non-unit), unit.
        unit_a = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))   # unit
        event = _push_deck_top(state, "P0", _get_card(repo, "IBH", "61"))     # We're In Trouble (event)
        unit_b = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))    # unit
        # deck top order now: unit_b, event, unit_a
        officer = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # source
        state, _ = _play_event_from_hand(state, repo, "IBH", "9")
        assert state.pending_decisions[-1].kind == "deck_search"
        selects = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)}
        assert selects == {unit_a.instance_id, unit_b.instance_id}  # only units
        state = apply(state, SelectSearchCard(unit_b.instance_id))
        assert not state.pending_decisions  # cap 1 auto-finishes
        ps = state.player_by_id("P0")
        hand_ids = {c.instance_id for c in ps.hand}
        disc_ids = {c.instance_id for c in ps.discard}
        assert unit_b.instance_id in hand_ids
        # The other two revealed cards were discarded, not bottomed.
        assert unit_a.instance_id in disc_ids
        assert event.instance_id in disc_ids
        assert unit_a.instance_id not in {c.instance_id for c in ps.deck}


# ── Unit triggers ─────────────────────────────────────────────────────────────

class TestAdmiralOzzel:
    """IBH_82 — When Defeated: Each opponent discards a card from their hand."""

    def test_ibh_82_when_defeated_opponent_discards(self, repo):
        state = _make_state()
        ozzel = _place(state, "P0", _get_card(repo, "IBH", "82"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "128"))
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        before = len(state.player_by_id("P1").hand)
        state = _fire_when_defeated(state, ozzel)
        assert len(state.player_by_id("P1").hand) == before - 1


class TestAdmiralPiett:
    """IBH_60 — On Attack: If you control an Aggression unit, draw a card."""

    def test_ibh_60_draws_with_aggression_unit(self, repo):
        state = _make_state()
        piett = _place(state, "P0", _get_card(repo, "IBH", "60"), "ground")   # Vigilance
        _place(state, "P0", _get_card(repo, "IBH", "68"), "ground")           # Veers = Aggression
        _deck_units(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, piett)
        assert len(state.player_by_id("P0").hand) == before + 1
        assert not state.pending_decisions

    def test_ibh_60_no_draw_without_aggression_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        piett = _place(state, "P0", _get_card(repo, "IBH", "60"), "ground")
        _deck_units(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, piett)
        assert len(state.player_by_id("P0").hand) == before
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestC3PO:
    """IBH_19 — When Played: If you control a Cunning unit, draw a card."""

    def test_ibh_19_draws_with_cunning_unit(self, repo):
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "IBH", "19"), "ground")    # Command/Heroism
        _place(state, "P0", _get_card(repo, "IBH", "11"), "ground")           # R2-D2 = Cunning
        _deck_units(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, c3po)
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_ibh_19_no_draw_without_cunning_unit(self, repo):
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "IBH", "19"), "ground")
        _deck_units(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, c3po)
        assert len(state.player_by_id("P0").hand) == before


class TestGeneralVeers:
    """IBH_68 — When Played: If you control a Vigilance unit, deal 2 to an enemy
    base and heal 2 from your base."""

    def test_ibh_68_deals_and_heals_with_vigilance_unit(self, repo):
        state = _make_state()
        p0base = state.player_by_id("P0").base_instance
        p1base = state.player_by_id("P1").base_instance
        p0base.damage = 3
        veers = _place(state, "P0", _get_card(repo, "IBH", "68"), "ground")   # Aggression/Villainy
        _place(state, "P0", _get_card(repo, "IBH", "60"), "ground")           # Piett = Vigilance
        state = _fire_when_played(state, veers)
        assert state.player_by_id("P1").base_instance.damage == 2
        assert state.player_by_id("P0").base_instance.damage == 1
        assert not state.pending_decisions

    def test_ibh_68_no_effect_without_vigilance_unit(self, repo):
        state = _make_state()
        p1base = state.player_by_id("P1").base_instance
        veers = _place(state, "P0", _get_card(repo, "IBH", "68"), "ground")
        state = _fire_when_played(state, veers)
        assert state.player_by_id("P1").base_instance.damage == 0


class TestR2D2:
    """IBH_11 — On Attack: If you control a Command unit, exhaust an enemy ground
    unit that costs 4 or less."""

    def test_ibh_11_exhausts_cheap_enemy_ground_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        r2 = _place(state, "P0", _get_card(repo, "IBH", "11"), "ground")      # Cunning/Heroism
        _place(state, "P0", _get_card(repo, "IBH", "19"), "ground")           # C-3PO = Command
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 2
        state = _fire_on_attack(state, r2)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted

    def test_ibh_11_no_exhaust_without_command_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        r2 = _place(state, "P0", _get_card(repo, "IBH", "11"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, r2)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert not state.pending_decisions


class TestRebellionYWing:
    """IBH_6 — On Attack: Deal 1 damage to a base."""

    def test_ibh_6_deals_1_to_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        ywing = _place(state, "P0", _get_card(repo, "IBH", "6"), "space")
        enemy_base = state.player_by_id("P1").base_instance
        state = _fire_on_attack(state, ywing)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy_base.instance_id))
        assert state.player_by_id("P1").base_instance.damage == 1


class TestTauntaunMount:
    """IBH_15 — When Defeated: Heal 2 damage from your base."""

    def test_ibh_15_when_defeated_heals_own_base(self, repo):
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = 3
        mount = _place(state, "P0", _get_card(repo, "IBH", "15"), "ground")
        state = _fire_when_defeated(state, mount)
        assert state.player_by_id("P0").base_instance.damage == 1
        assert not state.pending_decisions


class TestHothLieutenant:
    """IBH_64 — When Played: You may attack with another unit. +2/+0."""

    def test_ibh_64_grants_optional_attack_excluding_self(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        state = _make_state()
        hoth = _place(state, "P0", _get_card(repo, "IBH", "64"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, hoth)
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        attackers = {a.attacker_id for a in acts if isinstance(a, AttackWithUnit)}
        assert ally.instance_id in attackers
        assert hoth.instance_id not in attackers  # "another" unit
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)  # "you may"


# ── Activated abilities ───────────────────────────────────────────────────────

class TestIonCannon:
    """IBH_16 — Action [Exhaust]: Deal 3 damage to a space unit."""

    def test_ibh_16_deals_3_to_space_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        cannon = _place(state, "P0", _get_card(repo, "IBH", "16"), "space")
        space_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        ground_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == cannon.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert space_enemy.instance_id in offered
        assert ground_enemy.instance_id not in offered  # space units only
        state = apply(state, ChooseTarget(space_enemy.instance_id))
        assert _find_instance(state, space_enemy.instance_id).damage == 3
        assert _find_instance(state, cannon.instance_id).exhausted


class TestImperialDeckOfficer:
    """IBH_62 — Action [Exhaust]: Heal 2 damage from a Villainy unit."""

    def test_ibh_62_heals_villainy_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        officer = _place(state, "P0", _get_card(repo, "IBH", "62"), "ground")
        villain = _place(state, "P0", _get_card(repo, "IBH", "82"), "ground")  # Ozzel = Villainy
        villain.damage = 1  # Ozzel is 3/1, so max 1 damage before defeat
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == officer.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert villain.instance_id in offered
        state = apply(state, ChooseTarget(villain.instance_id))
        assert _find_instance(state, villain.instance_id).damage == 0
        assert _find_instance(state, officer.instance_id).exhausted


class TestGeneralRieekan:
    """IBH_23 — Action [Exhaust]: Attack with another Heroism unit. +2/+0."""

    def test_ibh_23_grants_attack_to_other_heroism_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        state = _make_state()
        rieekan = _place(state, "P0", _get_card(repo, "IBH", "23"), "ground")  # source
        heroism = _place(state, "P0", _get_card(repo, "IBH", "11"), "ground")  # R2-D2 = Heroism
        villain = _place(state, "P0", _get_card(repo, "IBH", "82"), "ground")  # Ozzel = Villainy
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == rieekan.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert heroism.instance_id in attackers
        assert villain.instance_id not in attackers   # Heroism only
        assert rieekan.instance_id not in attackers    # "another" unit
        assert _find_instance(state, rieekan.instance_id).exhausted  # cost paid


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:01 — direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

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


class TestLukeSkywalkerIBH20:
    """Restore 2 | When Played: You may deal 3 damage to a ground unit."""

    def test_IBH_20_deals_3_to_a_chosen_ground_unit(self, repo):
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "IBH", "20"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        _place(state, "P1", _get_card(repo, "JTL", "95"), "space")
        state = _fire_when_played(state, luke)
        state = _drive(state, _accept_and_target(victim))
        assert _find_instance(state, victim.instance_id).damage == 3

    def test_IBH_20_has_restore(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "IBH", "20"), "ground")
        assert has_keyword(state, luke, Keyword.RESTORE)
        assert keyword_value(state, luke, Keyword.RESTORE) == 2


class TestDarthVaderIBH53:
    """Undeployed Action [1 resource, Exhaust]: Deal 1 to a base | Deployed On Attack:
    Deal 2 damage to a base."""

    def test_IBH_53_undeployed_action_deals_1_to_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        from tests.test_sor_cards import _place_leader
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "IBH", "53"))
        _give_resources(state, "P0", 5)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == vader.instance_id)
        state = apply(state, use)
        enemy_base = state.player_by_id("P1").base_instance
        state = apply(state, ChooseTarget(enemy_base.instance_id))
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_IBH_53_deployed_on_attack_deals_2_to_a_base(self, repo):
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "IBH", "53"), "ground")
        vader.deployed = True
        state = _fire_on_attack(state, vader)
        enemy_base = state.player_by_id("P1").base_instance
        state = _drive(state, _accept_and_target(enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 2


class TestAvengerIBH72:
    """When Played: Deal 1 damage to each other unit (including friendly units)."""

    def test_IBH_72_hits_every_other_unit_but_not_itself(self, repo):
        state = _make_state()
        avenger = _place(state, "P0", _get_card(repo, "IBH", "72"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "JTL", "95"), "space")
        state = _drive(_fire_when_played(state, avenger))
        assert _find_instance(state, ally.instance_id).damage == 1
        assert _find_instance(state, enemy.instance_id).damage == 1
        assert _find_instance(state, avenger.instance_id).damage == 0


class TestYouHaveFailedMeIBH95:
    """Defeat a friendly unit.  If you do, ready a friendly unit with 5 or less
    power."""

    def test_IBH_95_defeats_then_readies_a_low_power_friendly(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        sacrifice = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        readied = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        readied.exhausted = True
        big = _place(state, "P0", _get_card(repo, "IBH", "72"), "space")          # 8/6
        big.exhausted = True
        state, _ev = _play_event_from_hand(state, repo, "IBH", "95")
        state = apply(state, ChooseTarget(sacrifice.instance_id))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert readied.instance_id in offered
        assert big.instance_id not in offered            # 8 power > 5
        state = _drive(apply(state, ChooseTarget(readied.instance_id)))
        assert _find_instance(state, sacrifice.instance_id) is None
        assert not _find_instance(state, readied.instance_id).exhausted

    def test_IBH_95_no_friendly_unit_means_no_ready_prompt(self, repo):
        state = _make_state()
        exhausted_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        exhausted_enemy.exhausted = True
        state, _ev = _play_event_from_hand(state, repo, "IBH", "95")
        state = _drive(state)
        assert _find_instance(state, exhausted_enemy.instance_id).exhausted


class TestBlizzardOneIBH99:
    """When Played: You may defeat a non-leader ground unit with 3 or less remaining
    HP."""

    def test_IBH_99_only_offers_low_remaining_hp_ground_units(self, repo):
        state = _make_state()
        blizzard = _place(state, "P0", _get_card(repo, "IBH", "99"), "ground")
        weak = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")   # 2/3
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        state = _fire_when_played(state, blizzard)
        state = _drive(state, _accept_and_target(weak))
        assert _find_instance(state, weak.instance_id) is None
        assert _find_instance(state, tough.instance_id) is not None


class TestTheDesolationOfHothIBH104:
    """Defeat up to 2 enemy units that each cost 3 or less."""

    def test_IBH_104_defeats_two_cheap_enemies_and_spares_the_expensive(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        cheap_a = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # cost 2
        cheap_b = _place(state, "P1", _get_card(repo, "JTL", "95"), "space")
        pricey = _place(state, "P1", _get_card(repo, "IBH", "72"), "space")     # cost 8
        state, _ev = _play_event_from_hand(state, repo, "IBH", "104")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert pricey.instance_id not in offered
        state = apply(state, ChooseTarget(cheap_a.instance_id))
        state = _drive(state, _accept_and_target(cheap_b))
        assert _find_instance(state, cheap_a.instance_id) is None
        assert _find_instance(state, cheap_b.instance_id) is None
        assert _find_instance(state, pricey.instance_id) is not None


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:02 — card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

class TestWatchThisIBH52:
    """Return a non-leader unit that costs 6 or less to its owner's hand.  Exhaust
    each other enemy unit in the same arena."""

    def test_IBH_52_bounces_then_exhausts_that_arena(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        bounced = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        same_arena = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        other_arena = _place(state, "P1", _get_card(repo, "JTL", "95"), "space")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "IBH", "52")
        state = _drive(apply(state, ChooseTarget(bounced.instance_id)))
        assert _find_instance(state, bounced.instance_id) is None
        assert any(c.instance_id == bounced.instance_id
                   for c in state.player_by_id("P1").hand)
        assert _find_instance(state, same_arena.instance_id).exhausted
        assert not _find_instance(state, other_arena.instance_id).exhausted
        assert not _find_instance(state, friendly.instance_id).exhausted

    def test_IBH_52_does_not_offer_a_unit_costing_more_than_6(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        pricey = _place(state, "P1", _get_card(repo, "IBH", "72"), "space")   # cost 8
        cheap = _place(state, "P1", _get_card(repo, "JTL", "95"), "space")
        state, _ev = _play_event_from_hand(state, repo, "IBH", "52")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered


# ══════════════════════════════════════════════════════════════════════════════
# ibh-set:03 — combat tricks, buffs & tempo   /   ibh-set:04 — misc abilities
# ══════════════════════════════════════════════════════════════════════════════


class TestLeiaOrganaIBH1:
    """Undeployed Action [1 resource, Exhaust]: Heal 1 from a friendly unit |
    Deployed On Attack: Heal 1 from a friendly unit and 1 from ANOTHER."""

    def test_IBH_1_undeployed_action_heals_a_damaged_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        from tests.test_sor_cards import _place_leader
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "IBH", "1"))
        _give_resources(state, "P0", 5)
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        fine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leia.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert hurt.instance_id in offered
        assert fine.instance_id not in offered      # never offered as a no-op
        state = apply(state, ChooseTarget(hurt.instance_id))
        assert _find_instance(state, hurt.instance_id).damage == 2

    def test_IBH_1_action_not_offered_with_no_damaged_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        from tests.test_sor_cards import _place_leader
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "IBH", "1"))
        _give_resources(state, "P0", 5)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # undamaged
        assert not any(isinstance(a, UseAbility) and a.source_id == leia.instance_id
                       for a in legal_actions(state))

    def test_IBH_1_deployed_on_attack_heals_two_different_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "IBH", "1"), "ground")
        leia.deployed = True
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        a.damage = 2
        b.damage = 2
        state = _fire_on_attack(state, leia)
        state = apply(state, ChooseTarget(a.instance_id))
        # The first heal must have removed A from the second effect's candidates.
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, ChooseTarget) and x.target_id}
        assert a.instance_id not in offered
        assert b.instance_id in offered
        state = apply(state, ChooseTarget(b.instance_id))
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1


class TestRecoveryIBH13:
    """IBH_13 — Heal 5 damage from a unit."""

    def test_IBH_13_heals_5_from_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        u = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")   # 6/9
        u.damage = 7
        state, _ev = _play_event_from_hand(state, repo, "IBH", "13")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == u.instance_id))
        assert _find_instance(state, u.instance_id).damage == 2


class TestMillenniumFalconIBH31:
    """IBH_31 — When Played: if your base is more damaged than an enemy base, ready."""

    def test_IBH_31_readies_when_own_base_is_more_damaged(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 8
        state.player_by_id("P1").base_instance.damage = 3
        falcon = _place(state, "P0", _get_card(repo, "IBH", "31"), "space")
        falcon.exhausted = True
        state = _fire_when_played(state, falcon)
        state = _drive(state)
        assert not _find_instance(state, falcon.instance_id).exhausted

    def test_IBH_31_does_not_ready_when_bases_are_level(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 5
        state.player_by_id("P1").base_instance.damage = 5
        falcon = _place(state, "P0", _get_card(repo, "IBH", "31"), "space")
        falcon.exhausted = True
        state = _fire_when_played(state, falcon)
        state = _drive(state)
        # STRICT comparison — an equal count satisfies neither reading.
        assert _find_instance(state, falcon.instance_id).exhausted


class TestHanSoloNerfHerderIBH42:
    """IBH_42 / IBH_10 — Raid 2 | On Attack: the defender gets -2/-0 this attack."""

    def test_IBH_42_defender_loses_2_power_for_this_attack(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "IBH", "42"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        before = compute_power(state, defender)
        state = _fire_on_attack(state, han, defender_ci=defender)
        state = _drive(state)
        after = compute_power(state, _find_instance(state, defender.instance_id))
        assert after == before - 2

    def test_IBH_42_has_raid_2(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "IBH", "42"), "ground")
        assert has_keyword(state, han, Keyword.RAID)
        assert keyword_value(state, han, Keyword.RAID) == 2

    def test_IBH_10_is_the_same_card_and_debuffs_the_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "IBH", "10"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, defender)
        state = _fire_on_attack(state, han, defender_ci=defender)
        state = _drive(state)
        after = compute_power(state, _find_instance(state, defender.instance_id))
        assert after == before - 2
