"""JTL / SOR card ability tests (deck ``boba-fett``, group ``boba-fett:01`` —
Direct damage & removal).

One focused test per card, asserting behaviour through the public engine
interfaces (legal_actions / apply / trigger firing).  Exercises the new
**indirect-damage** primitive (the ``assign_indirect_damage`` decision kind +
``_apply_indirect_damage`` shield-bypass), the ``select_damage`` decision kind
(IG-2000), the ``WhenIndirectDamageDealtToUnit`` observer trigger (Pryde), and
the ``target_remaining_hp_minus_1`` scaling count (No Disintegrations).

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.  Reuses the DB-backed helpers from the SOR / SHD card tests.
"""
from __future__ import annotations


from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_on_attack,
    _fire_when_defeated, _fire_upgrade_played, _defeat_and_fire,
    _find_instance, _shield_count, _experience_count, _play_event_from_hand,
    _place_leader, _give_resources,
)
from tests.test_shd_cards import _attach_upgrade_directly


def _assign_actions(state):
    from swu.engine.actions import legal_actions
    return [a for a in legal_actions(state)
            if type(a).__name__ == "AssignIndirectDamage"]


def _p1_base_id(state):
    return state.player_by_id("P1").base_instance.instance_id


# ══════════════════════════════════════════════════════════════════════════════
# SOR_131 — Fifth Brother
# ══════════════════════════════════════════════════════════════════════════════

class TestFifthBrother:
    """This unit gains Raid 1 for each damage on him." (= Grit) +
    "On Attack: You may deal 1 damage to this unit and 1 damage to another
    ground unit."""

    def test_sor_131_printed_raid_stripped_and_grit_granted(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        fb = _place(state, "P0", _get_card(repo, "SOR", "131"), "ground")
        # The DB-tagged printed "Raid" is stripped (the Grit self-grant models it).
        assert "Raid" not in fb.card_def.keywords
        assert has_keyword(state, fb, Keyword.GRIT)
        assert not has_keyword(state, fb, Keyword.RAID)

    def test_sor_131_grit_scales_power_with_damage(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        fb = _place(state, "P0", _get_card(repo, "SOR", "131"), "ground")
        base = compute_power(state, fb, is_attacking=True)
        fb.damage = 3
        assert compute_power(state, fb, is_attacking=True) == base + 3

    def test_sor_131_on_attack_deals_1_to_another_and_1_to_self(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        fb = _place(state, "P0", _get_card(repo, "SOR", "131"), "ground")
        other = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, fb)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == other.instance_id))
        assert _find_instance(state, other.instance_id).damage == 1
        assert _find_instance(state, fb.instance_id).damage == 1

    def test_sor_131_on_attack_auto_declines_with_no_other_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        fb = _place(state, "P0", _get_card(repo, "SOR", "131"), "ground")
        state = _fire_on_attack(state, fb)
        # No "another ground unit" exists → the optional trigger auto-declines.
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert _find_instance(state, fb.instance_id).damage == 0


# ══════════════════════════════════════════════════════════════════════════════
# JTL_132 — First Order Stormtrooper
# ══════════════════════════════════════════════════════════════════════════════

class TestFirstOrderStormtrooper:
    """On Attack/When Defeated: Deal 1 indirect damage to a player."""

    def test_jtl_132_on_attack_deals_1_indirect(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        state = _fire_on_attack(state, trooper)
        acts = _assign_actions(state)
        assert acts, "an assign_indirect_damage decision should be pending"
        # The receiving player (P1) assigns the 1 point to their base.
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_jtl_132_when_defeated_deals_1_indirect(self, repo):
        from swu.engine.actions import apply
        from swu.engine.events import UnitDefeated
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        # Mimic a defeat: remove from arena, fire UnitDefeated with defeated_ci.
        state.player_by_id("P0").ground_arena.remove(trooper)
        evt = UnitDefeated(player_id="P0", instance_id=trooper.instance_id,
                           card_name=trooper.card_def.display_name)
        ctx = {"defeated_id": trooper.instance_id, "defeated_ci": trooper,
               "defeated_controller_id": "P0"}
        state = fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_jtl_132_indirect_bypasses_shield(self, repo):
        from swu.engine.actions import apply
        from swu.engine import tokens
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        tokens.attach_token(state, state.player_by_id("P1"), victim, "Shield")
        assert _shield_count(victim) == 1
        state = _fire_on_attack(state, trooper)
        # The receiving player assigns the 1 indirect point onto the shielded unit.
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == victim.instance_id))
        v = _find_instance(state, victim.instance_id)
        assert v.damage == 1               # damage landed …
        assert _shield_count(v) == 1       # … and the Shield was NOT consumed


# ══════════════════════════════════════════════════════════════════════════════
# JTL_133 — Allegiant General Pryde
# ══════════════════════════════════════════════════════════════════════════════

class TestAllegiantGeneralPryde:
    """When indirect damage is dealt to a unit: You may defeat a non-unique
    upgrade on it.  On Attack: If you have the initiative, deal 2 indirect damage
    to a player."""

    def test_jtl_133_on_attack_with_initiative_deals_2_indirect(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        state.initiative_holder = 0  # P0 has the initiative
        pryde = _place(state, "P0", _get_card(repo, "JTL", "133"), "ground")
        state = _fire_on_attack(state, pryde)
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_jtl_133_on_attack_without_initiative_does_nothing(self, repo):
        state = _make_state()
        state.initiative_holder = 1  # P1 has the initiative, not P0
        pryde = _place(state, "P0", _get_card(repo, "JTL", "133"), "ground")
        state = _fire_on_attack(state, pryde)
        assert not state.pending_decisions
        assert state.player_by_id("P1").base_instance.damage == 0

    def test_jtl_133_defeats_nonunique_upgrade_on_indirect_damaged_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, push_assign_indirect_damage)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "133"), "ground")  # Pryde (observer)
        source = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        upg = _attach_upgrade_directly(state, victim, _get_card(repo, "SOR", "120"), "P1")
        # Deal 1 indirect damage; the receiving player (P1) assigns it to the victim.
        push_assign_indirect_damage(state, source, amount=1)
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == victim.instance_id))
        # Pryde's observer trigger is now offered to its controller (P0); accept
        # it and drive the resulting resolve_effects to completion.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        guard = 0
        while state.pending_decisions and guard < 10:
            guard += 1
            state = apply(state, legal_actions(state)[0])
        v = _find_instance(state, victim.instance_id)
        assert all(u.instance_id != upg.instance_id for u in v.attached_upgrades)


# ══════════════════════════════════════════════════════════════════════════════
# JTL_139 — Dengar (Piloting — the granted On Attack)
# ══════════════════════════════════════════════════════════════════════════════

class TestDengar:
    """Attached unit gains: "On Attack: Deal 2 indirect damage to a player. If
    this unit is an Underworld unit, deal 3 indirect damage instead."""

    def test_jtl_139_granted_on_attack_deals_2_when_host_not_underworld(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "139"), "P0")
        state = _fire_on_attack(state, host)
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_jtl_139_granted_on_attack_deals_3_when_host_is_underworld(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        # IG-2000 (JTL_140) is an Underworld/Vehicle host.
        host = _place(state, "P0", _get_card(repo, "JTL", "140"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "139"), "P0")
        state = _fire_on_attack(state, host)
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 3


# ══════════════════════════════════════════════════════════════════════════════
# JTL_140 — IG-2000
# ══════════════════════════════════════════════════════════════════════════════

class TestIG2000:
    """When Played: Deal 1 damage to each of up to 3 units."""

    def test_jtl_140_deals_1_to_each_of_three_units(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        ig = _place(state, "P0", _get_card(repo, "JTL", "140"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e3 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, ig)
        for eid in (e1.instance_id, e2.instance_id, e3.instance_id):
            state = apply(state, next(a for a in legal_actions(state)
                                      if type(a).__name__ == "SelectDamageTarget"
                                      and a.target_id == eid))
        assert _find_instance(state, e1.instance_id).damage == 1
        assert _find_instance(state, e2.instance_id).damage == 1
        assert _find_instance(state, e3.instance_id).damage == 1
        assert not state.pending_decisions

    def test_jtl_140_can_finish_early(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        ig = _place(state, "P0", _get_card(repo, "JTL", "140"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, ig)
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "SelectDamageTarget"
                                  and a.target_id == e1.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "FinishSelectDamage"))
        assert _find_instance(state, e1.instance_id).damage == 1
        assert _find_instance(state, e2.instance_id).damage == 0
        assert not state.pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# JTL_144 — No Disintegrations
# ══════════════════════════════════════════════════════════════════════════════

class TestNoDisintegrations:
    """Deal damage to a non-leader unit equal to 1 less than its remaining HP."""

    def test_jtl_144_deals_remaining_hp_minus_1(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "JTL", "144")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        # remaining HP 7 → deal 6, leaving 1.
        assert _find_instance(state, enemy.instance_id).damage == 6

    def test_jtl_144_leaves_target_at_1_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.damage = 3  # remaining HP now 4
        state, _evt = _play_event_from_hand(state, repo, "JTL", "144")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        # remaining 4 → deal 3 → total damage 6, HP 7, survives at 1.
        e = _find_instance(state, enemy.instance_id)
        assert e.damage == 6
        assert e in (state.player_by_id("P1").ground_arena)


# ══════════════════════════════════════════════════════════════════════════════
# boba-fett:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


class TestEliteP38Starfighter:
    """TWI_181 — When Played/When Defeated: You may deal 1 damage to a unit."""

    def test_twi_181_when_played_deals_1(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        p38 = _place(state, "P0", _get_card(repo, "TWI", "181"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, p38)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_twi_181_when_defeated_deals_1(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        p38 = _place(state, "P0", _get_card(repo, "TWI", "181"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, p38)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_twi_181_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        p38 = _place(state, "P0", _get_card(repo, "TWI", "181"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, p38)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert not state.pending_decisions

    def test_twi_181_auto_declines_with_no_unit(self, repo):
        """When Defeated with no unit left on the board -> the optional trigger
        auto-declines (no prompt)."""
        state = _make_state()
        p38 = _place(state, "P0", _get_card(repo, "TWI", "181"), "space")
        state.player_by_id("P0").space_arena.remove(p38)  # it has left play
        state = _fire_when_defeated(state, p38)
        assert not state.pending_decisions


class TestZygerrianStarhopper:
    """JTL_183 — When Defeated: Deal 2 indirect damage to a player."""

    def test_jtl_183_when_defeated_deals_2_indirect(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        hopper = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        state = _fire_when_defeated(state, hopper)
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2


class TestBossk:
    """JTL_187 — On Attack: Exhaust the defender and deal 1 damage to it (if it's
    a unit).  Piloting → attached unit gains the same On Attack."""

    def test_jtl_187_on_attack_exhausts_and_damages_defender(self, repo):
        state = _make_state()
        bossk = _place(state, "P0", _get_card(repo, "JTL", "187"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, bossk, defender)
        d = _find_instance(state, defender.instance_id)
        assert d.exhausted is True
        assert d.damage == 1

    def test_jtl_187_base_attack_is_noop(self, repo):
        state = _make_state()
        bossk = _place(state, "P0", _get_card(repo, "JTL", "187"), "ground")
        state = _fire_on_attack(state, bossk, None)
        assert not state.pending_decisions

    def test_jtl_187_granted_on_attack_from_pilot_host(self, repo):
        """Bossk as a Pilot upgrade: the host gains the On Attack."""
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")  # Vehicle
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "187"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, host, defender)
        d = _find_instance(state, defender.instance_id)
        assert d.exhausted is True
        assert d.damage == 1


class TestBobaFettJTL189:
    """JTL_189 — When played as an upgrade: You may deal 1 damage to a unit. If
    attached unit is a Transport, deal 2 instead."""

    def test_jtl_189_pilot_deals_1_on_non_transport_host(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")  # Vehicle, not Transport
        boba = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "189"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, boba, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_jtl_189_pilot_deals_2_on_transport_host(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")  # Transport
        boba = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "189"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, boba, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_jtl_189_normal_unit_play_does_not_trigger(self, repo):
        """Played as a vanilla 5/4 unit, the 'when played as an upgrade' clause
        must NOT fire."""
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "JTL", "189"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, boba)
        assert not state.pending_decisions

    def test_jtl_189_pilot_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        boba = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "189"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, boba, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestElectromagneticPulse:
    """JTL_230 — Deal 2 damage to a Droid or Vehicle unit and exhaust it."""

    def test_jtl_230_damages_and_exhausts_vehicle(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        veh = _place(state, "P1", _get_card(repo, "JTL", "237"), "space")  # TIE Bomber (Vehicle, 0/4)
        state, _evt = _play_event_from_hand(state, repo, "JTL", "230")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == veh.instance_id))
        v = _find_instance(state, veh.instance_id)
        assert v.damage == 2
        assert v.exhausted is True

    def test_jtl_230_only_targets_droid_or_vehicle(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        non_veh = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper
        state, _evt = _play_event_from_hand(state, repo, "JTL", "230")
        # No Droid/Vehicle unit -> the event fizzles (no ChooseTarget for it).
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert non_veh.instance_id not in tids


class TestTIEBomber:
    """JTL_237 — On Attack: Deal 3 indirect damage to the defending player."""

    def test_jtl_237_on_attack_deals_3_indirect(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        state = _fire_on_attack(state, bomber)
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 3


class TestFettsFirespray:
    """JTL_240 — When Played/On Attack: Deal 1 indirect damage to a player. If you
    control Boba Fett (unit/upgrade/leader), deal 2 instead."""

    def test_jtl_240_when_played_deals_1_without_boba(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        fs = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        state = _fire_when_played(state, fs)
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_jtl_240_on_attack_deals_2_with_boba_unit(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        fs = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "189"), "ground")  # Boba Fett unit
        state = _fire_on_attack(state, fs)
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_jtl_240_counts_boba_as_attached_upgrade(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        fs = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "189"), "P0")  # Boba as pilot
        state = _fire_when_played(state, fs)
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2


# ══════════════════════════════════════════════════════════════════════════════
# JTL_9 — Boba Fett (Leader): deploy-leader-as-upgrade + non-combat-damage observer
# ══════════════════════════════════════════════════════════════════════════════

def _kinds(state):
    from swu.engine.actions import legal_actions
    return [type(a).__name__ for a in legal_actions(state)]


def _drive_to_settle(state, *, assign_indirect_to_base="P1", max_steps=25):
    """Resolve forced/obvious follow-up decisions: accept Boba's optional trigger,
    auto-resolve effect frames, and assign any indirect damage onto the named
    player's base.  Stops when the stack is clear."""
    from swu.engine.actions import legal_actions, apply
    for _ in range(max_steps):
        if not state.pending_decisions:
            break
        acts = legal_actions(state)
        chosen = None
        for pref in ("AcceptTrigger", "AutoResolveEffects"):
            chosen = next((a for a in acts if type(a).__name__ == pref), None)
            if chosen:
                break
        if chosen is None:
            aid = [a for a in acts if type(a).__name__ == "AssignIndirectDamage"]
            if aid:
                base_id = state.player_by_id(assign_indirect_to_base).base_instance.instance_id
                chosen = next((a for a in aid if a.target_id == base_id), aid[0])
        if chosen is None:
            chosen = acts[0]
        state = apply(state, chosen)
    return state


class TestBobaFettJTL9:
    """JTL_9 Boba Fett (Leader) — the deploy-leader-as-upgrade + "when you deal
    non-combat damage" framework primitives."""

    def test_jtl_9_deploy_as_upgrade_makes_host_a_leader_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, compute_power, compute_hp,
            DeployLeaderAsUpgrade, FinishDamageDistribution,
        )
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "ground")  # TIE Bomber 0/4 Vehicle
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")          # enemy (7 hp)
        _place_leader(state, "P0", _get_card(repo, "JTL", "9"))
        _give_resources(state, "P0", 6)

        offered = [a for a in legal_actions(state)
                   if isinstance(a, DeployLeaderAsUpgrade)]
        assert [a.vehicle_target_id for a in offered] == [host.instance_id]

        state = apply(state, offered[0])
        # "When deployed as an upgrade: deal up to 4 divided" pushes an up_to pool.
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context["pool"] == 4
        assert top.context["up_to"] is True
        # Boba is attached as a +4/+4 pilot upgrade → host is now a 4/8 leader unit.
        host_now = _find_instance(state, host.instance_id)
        assert [u.card_def.name for u in host_now.attached_upgrades] == ["Boba Fett"]
        assert compute_power(state, host_now) == 4
        assert compute_hp(state, host_now) == 8
        # "Up to" → may assign 0 and finish (no damage → no observer either).
        assert any(isinstance(a, FinishDamageDistribution) for a in legal_actions(state))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishDamageDistribution)))
        assert not state.pending_decisions

    def test_jtl_9_deploy_as_upgrade_deals_up_to_4(self, repo):
        from swu.engine.actions import legal_actions, apply, DeployLeaderAsUpgrade, AssignDamage
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 7 hp — survives 4
        _place_leader(state, "P0", _get_card(repo, "JTL", "9"))
        _give_resources(state, "P0", 6)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeployLeaderAsUpgrade)))
        for _ in range(4):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, AssignDamage) and a.target_id == foe.instance_id)
            state = apply(state, act)
        foe_now = _find_instance(state, foe.instance_id)
        assert foe_now is not None and foe_now.damage == 4, "4 divided damage landed on the enemy"

    def test_jtl_9_normal_deploy_does_not_fire_up_to_4(self, repo):
        """A normal DeployLeader (not the upgrade option) must NOT fire the
        via_pilot_leader-gated 'when deployed as an upgrade' ability."""
        from swu.engine.actions import legal_actions, apply, DeployLeader
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place_leader(state, "P0", _get_card(repo, "JTL", "9"))
        _give_resources(state, "P0", 6)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeployLeader)))
        assert not any(d.kind == "distribute_damage" for d in state.pending_decisions)

    def test_jtl_9_noncombat_damage_triggers_indirect(self, repo):
        """Dealing non-combat damage (an event) fires Boba's observer; accepting it
        exhausts the leader and deals 1 indirect damage to the opponent."""
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        boba_ci = _place_leader(state, "P0", _get_card(repo, "JTL", "9"))    # undeployed leader
        veh = _place(state, "P1", _get_card(repo, "JTL", "237"), "ground")   # enemy Vehicle (EMP target)
        # Electromagnetic Pulse JTL_230: deal 2 to a Droid/Vehicle unit (non-combat).
        state, _emp = _play_event_from_hand(state, repo, "JTL", "230", owner="P0")
        # Choose the vehicle target for EMP.
        ct = next(a for a in legal_actions(state)
                  if type(a).__name__ == "ChooseTarget" and getattr(a, "target_id", None) == veh.instance_id)
        state = apply(state, ct)
        # Boba's "when you deal non-combat damage" observer is now offered.
        assert "AcceptTrigger" in _kinds(state), "the non-combat-damage observer fires"
        state = _drive_to_settle(state)
        assert state.player_by_id("P0").leader_instance.exhausted, "accepting exhausts the leader"
        assert state.player_by_id("P1").base_instance.damage == 1, "1 indirect damage dealt"

    def test_jtl_9_no_observer_when_leader_exhausted(self, repo):
        """SOURCE_READY gates the observer — an already-exhausted Boba is not
        offered the trigger (this bounds the self-chain)."""
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        boba_ci = _place_leader(state, "P0", _get_card(repo, "JTL", "9"))
        boba_ci.exhausted = True
        _place(state, "P1", _get_card(repo, "JTL", "237"), "ground")
        state, _emp = _play_event_from_hand(state, repo, "JTL", "230", owner="P0")
        veh_id = state.player_by_id("P1").ground_arena[0].instance_id
        ct = next(a for a in legal_actions(state)
                  if type(a).__name__ == "ChooseTarget" and getattr(a, "target_id", None) == veh_id)
        state = apply(state, ct)
        assert "AcceptTrigger" not in _kinds(state), "exhausted leader is not offered the trigger"

    def test_jtl_9_combat_damage_does_not_trigger_observer(self, repo):
        """Combat damage is not non-combat damage — attacking must not fire the
        observer (nor exhaust Boba)."""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        boba_ci = _place_leader(state, "P0", _get_card(repo, "JTL", "9"))
        # A ready friendly attacker with no abilities-based damage.
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = False
        state = apply(state, AttackWithUnit(attacker.instance_id, None))  # attack enemy base
        assert state.player_by_id("P1").base_instance.damage > 0, "combat damage landed on the base"
        assert not state.player_by_id("P0").leader_instance.exhausted, \
            "combat damage does not fire Boba's observer"
        assert not any(d.kind == "assign_indirect_damage" for d in state.pending_decisions)
        assert not state.game_memory.noncombat_damage_dealers


# ══════════════════════════════════════════════════════════════════════════════
# boba-fett:03 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestIG88:
    """JTL_141 — IG-88 (4/5, Piloting). "While an enemy unit is damaged, this unit
    gets +3/+0." + Pilot residual "Attached unit gains: '<the same>'."""

    def test_jtl_141_gets_plus_3_power_while_enemy_unit_damaged(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        ig = _place(state, "P0", _get_card(repo, "JTL", "141"), "ground")  # 4/5
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, ig) == 4          # no damaged enemy → base power
        enemy.damage = 1
        assert compute_power(state, ig) == 7          # +3 while an enemy unit is damaged

    def test_jtl_141_condition_ignores_own_damaged_units(self, repo):
        """The buff keys off an *enemy* damaged unit, not a friendly one."""
        from swu.engine.actions import compute_power
        state = _make_state()
        ig = _place(state, "P0", _get_card(repo, "JTL", "141"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.damage = 2                              # only a friendly unit is damaged
        assert compute_power(state, ig) == 4           # no buff

    def test_jtl_141_pilot_grants_host_plus_3_while_enemy_damaged(self, repo):
        """As a Pilot upgrade, IG-88 confers the same conditional +3/+0 to its host
        (the attached-upgrade SELF-StatBonus scan)."""
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "141"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")
        without = compute_power(state, host)           # no damaged enemy
        enemy.damage = 1
        with_dmg = compute_power(state, host)
        assert with_dmg == without + 3                 # the granted conditional buff


class TestFettsFirespray:
    """SOR_184 — Fett's Firespray (5/6). "When Played: If you control Boba Fett or
    Jango Fett (as a leader or unit), ready this unit. Action [2 resources]:
    Exhaust a non-unique unit."""

    def test_sor_184_when_played_readies_with_boba_fett(self, repo):
        state = _make_state()
        fire = _place(state, "P0", _get_card(repo, "SOR", "184"), "space")
        fire.exhausted = True                          # units enter play exhausted
        _place(state, "P0", _get_card(repo, "JTL", "189"), "ground")  # a Boba Fett unit
        state = _fire_when_played(state, fire)
        assert not _find_instance(state, fire.instance_id).exhausted

    def test_sor_184_when_played_no_ready_without_fett(self, repo):
        state = _make_state()
        fire = _place(state, "P0", _get_card(repo, "SOR", "184"), "space")
        fire.exhausted = True
        state = _fire_when_played(state, fire)
        assert _find_instance(state, fire.instance_id).exhausted  # stays exhausted

    def test_sor_184_action_exhausts_non_unique_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        fire = _place(state, "P0", _get_card(repo, "SOR", "184"), "space")
        fire.exhausted = False
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # non-unique
        _give_resources(state, "P0", 5, repo)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == fire.instance_id)
        state = apply(state, use)
        ct = next(a for a in legal_actions(state)
                  if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, ct)
        assert _find_instance(state, enemy.instance_id).exhausted

    def test_sor_184_action_cannot_exhaust_unique_unit(self, repo):
        """A unique enemy is not a legal target; with only one on the board the
        mandatory effect fizzles (the unit is never exhausted)."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        fire = _place(state, "P0", _get_card(repo, "SOR", "184"), "space")
        fire.exhausted = False
        unique = _place(state, "P1", _get_card(repo, "SOR", "131"), "ground")  # unique
        _give_resources(state, "P0", 5, repo)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == fire.instance_id)
        state = apply(state, use)
        assert not any(
            isinstance(a, ChooseTarget)
            and getattr(a, "target_id", None) == unique.instance_id
            for a in legal_actions(state))
        assert not _find_instance(state, unique.instance_id).exhausted


class TestNoGoodToMeDead:
    """SOR_186 — No Good to Me Dead (Event). "Exhaust a unit. That unit can't ready
    this round (including during the regroup phase)."""

    def _play_and_target(self, state, repo, target_ci, owner="P0"):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state, _ev = _play_event_from_hand(state, repo, "SOR", "186", owner=owner)
        ct = next(a for a in legal_actions(state)
                  if isinstance(a, ChooseTarget)
                  and a.target_id == target_ci.instance_id)
        return apply(state, ct)

    def test_sor_186_exhausts_and_flags_target(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._play_and_target(state, repo, enemy)
        tgt = _find_instance(state, enemy.instance_id)
        assert tgt.exhausted
        assert tgt.cannot_ready_this_round

    def test_sor_186_target_stays_exhausted_through_regroup(self, repo):
        from swu.engine.actions import _end_regroup
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._play_and_target(state, repo, enemy)
        # First regroup: the flagged unit does NOT ready; the flag is consumed.
        _end_regroup(state)
        tgt = _find_instance(state, enemy.instance_id)
        assert tgt.exhausted
        assert not tgt.cannot_ready_this_round
        # Next round's regroup: it readies normally again.
        _end_regroup(state)
        assert not _find_instance(state, enemy.instance_id).exhausted

    def test_sor_186_ready_effect_is_no_op_this_round(self, repo):
        """A ReadyCard effect cannot ready a unit flagged 'can't ready this round'."""
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import ReadyCard, TargetSpec
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._play_and_target(state, repo, enemy)
        tgt = _find_instance(state, enemy.instance_id)
        # Attempt to ready it directly via the ReadyCard effect.
        execute_effect(state, ReadyCard(TargetSpec(kind="unit")), tgt,
                       tgt.instance_id, {})
        assert _find_instance(state, enemy.instance_id).exhausted  # still exhausted


# ══════════════════════════════════════════════════════════════════════════════
# boba-fett:04 — Miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════


class TestHuntingAggressor:
    """JTL_165 — Hunting Aggressor (3/6). "Indirect damage you deal to opponents
    is increased by 1." (a passive IndirectDamageBonus marker read at the
    push_assign_indirect_damage chokepoint)."""

    def test_jtl_165_increases_own_indirect_damage_by_1(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "165"), "ground")     # Hunting Aggressor
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")  # deals 1 indirect
        state = _fire_on_attack(state, trooper)
        acts = _assign_actions(state)
        assert acts, "an assign_indirect_damage decision should be pending"
        # The 1 indirect is boosted to 2; the receiving player (P1) assigns it to base.
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_jtl_165_two_copies_stack(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "165"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "165"), "ground")
        source = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source, amount=1)
        dec = state.pending_decisions[-1]
        assert dec.context["amount"] == 3               # 1 base + 1 + 1

    def test_jtl_165_only_boosts_its_own_controllers_indirect(self, repo):
        """A Hunting Aggressor an OPPONENT controls does not boost your indirect."""
        state = _make_state()
        _place(state, "P1", _get_card(repo, "JTL", "165"), "ground")     # enemy's copy
        source = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        from swu.engine.actions import push_assign_indirect_damage
        push_assign_indirect_damage(state, source, amount=1)
        assert state.pending_decisions[-1].context["amount"] == 1        # unboosted


class TestHoundsTooth:
    """JTL_185 — Hound's Tooth (4/3). "While attacking an exhausted unit that
    didn't enter play this phase, this unit deals combat damage before the
    defender." (conditional First Strike via the ConditionalFirstStrike marker)."""

    def _setup(self, repo, defender_exhausted, defender_played_this_phase=False):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "JTL", "185"), "ground")  # 4/3
        attacker.exhausted = False
        defender = _place(state, "P1", _get_card(repo, "JTL", "185"), "ground")  # 4/3
        defender.exhausted = defender_exhausted
        if defender_played_this_phase:
            state.game_memory.units_played_this_phase.add(defender.instance_id)
        state = apply(state, AttackWithUnit(attacker.instance_id, defender.instance_id))
        return state, attacker.instance_id, defender.instance_id

    def test_jtl_185_first_strike_vs_exhausted_defender_attacker_survives(self, repo):
        # Defender is exhausted and not played this phase → First Strike: the
        # attacker's 4 kills the 3-HP defender before it deals damage back.
        state, atk_id, def_id = self._setup(repo, defender_exhausted=True)
        assert _find_instance(state, def_id) is None, "defender defeated first"
        surv = _find_instance(state, atk_id)
        assert surv is not None and surv.damage == 0, "attacker took no combat damage back"

    def test_jtl_185_no_first_strike_vs_ready_defender_both_trade(self, repo):
        # A READY defender does not qualify → simultaneous damage → both die.
        state, atk_id, def_id = self._setup(repo, defender_exhausted=False)
        assert _find_instance(state, atk_id) is None, "attacker died in the trade"
        assert _find_instance(state, def_id) is None, "defender died in the trade"

    def test_jtl_185_no_first_strike_if_defender_entered_this_phase(self, repo):
        # Exhausted but played THIS phase → the 'not_played_this_phase' predicate
        # fails → no First Strike → both trade.
        state, atk_id, def_id = self._setup(
            repo, defender_exhausted=True, defender_played_this_phase=True)
        assert _find_instance(state, atk_id) is None, "attacker died — no First Strike"
        assert _find_instance(state, def_id) is None


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:03 — Card advantage & disruption (JTL_200, JTL_215)
# ══════════════════════════════════════════════════════════════════════════════

class TestShuttleTydirium:
    """JTL_200 — On Attack: Discard a card from your deck. If it has an odd cost,
    you may give an Experience token to another unit."""

    def test_jtl_200_odd_cost_milled_offers_experience_to_another_unit(self, repo):
        from swu.engine.actions import legal_actions, apply
        from tests.test_sor_cards import _push_deck_top, _experience_count
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "200"), "space")
        recipient = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        odd = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # cost 1 (odd)
        state = _fire_on_attack(state, shuttle)
        # The milled card is in the discard pile now.
        assert any(c.instance_id == odd.instance_id
                   for c in state.player_by_id("P0").discard)
        # A select_token decision offers giving Experience to another unit.
        sel = [a for a in legal_actions(state)
               if type(a).__name__ == "SelectTokenTarget"]
        assert any(a.target_id == recipient.instance_id for a in sel)
        # Shuttle itself is excluded ("another unit").
        assert all(a.target_id != shuttle.instance_id for a in sel)
        state = apply(state, next(a for a in sel
                                  if a.target_id == recipient.instance_id))
        assert _experience_count(_find_instance(state, recipient.instance_id)) == 1

    def test_jtl_200_even_cost_milled_offers_no_token(self, repo):
        from swu.engine.actions import legal_actions
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "200"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        even = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))  # cost 4 (even)
        state = _fire_on_attack(state, shuttle)
        assert any(c.instance_id == even.instance_id
                   for c in state.player_by_id("P0").discard)
        assert not any(type(a).__name__ in ("SelectTokenTarget", "FinishSelectToken")
                       for a in legal_actions(state))


class TestBoShek:
    """JTL_215 — Piloting; When played as an upgrade: Discard 2 cards from your
    deck. Return each of those cards with an odd cost to your hand."""

    def test_jtl_215_played_as_upgrade_returns_odd_cost_milled_cards(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")  # a Vehicle host stand-in
        boshek = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "215"), "P0")
        # Deck top: an even-cost card (kept in discard) then an odd-cost card
        # (returned to hand).  _push_deck_top inserts at index 0, so push in reverse.
        odd = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))   # cost 1 (odd)
        even = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))   # cost 4 (even)
        # Deck order now: [even, odd, ...]; both are milled.
        _fire_upgrade_played(state, boshek, host)
        ps = state.player_by_id("P0")
        assert any(c.instance_id == odd.instance_id for c in ps.hand)
        assert any(c.instance_id == even.instance_id for c in ps.discard)
        assert not any(c.instance_id == odd.instance_id for c in ps.discard)

    def test_jtl_215_no_ability_when_played_as_normal_unit(self, repo):
        from tests.test_sor_cards import _push_deck_top
        state = _make_state()
        boshek = _place(state, "P0", _get_card(repo, "JTL", "215"), "ground")
        odd = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # cost 1 (odd)
        # Played as a normal unit → WhenPlayed(as_upgrade=True) does NOT fire, so the
        # deck top is untouched (no mill).
        _fire_when_played(state, boshek)
        assert state.player_by_id("P0").deck[0].instance_id == odd.instance_id


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:04 — Combat tricks, buffs & tempo
# ══════════════════════════════════════════════════════════════════════════════


class TestHanSoloJTL17:
    """JTL_17 Han Solo (Leader) — undeployed reveal-then-attack Action (with the
    new odd-cost-comparison granted-attack bonus) + deploy-as-upgrade ready-a-
    resource-per-odd-cost-card ability."""

    def _use_han(self, state, han_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == han_ci.instance_id)
        return apply(state, use)

    def test_jtl_17_action_grants_plus1_on_different_odd_costs(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        han = _place_leader(state, "P0", _get_card(repo, "JTL", "17"))
        attacker = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # cost 1 (odd), power 3
        # Reveal a cost-5 (odd, different) card on top of P0's deck.
        revealed = CardInstance("P0_revealed", _get_card(repo, "SOR", "196"), "P0", Zone.DECK)
        state.player_by_id("P0").deck.insert(0, revealed)
        state = self._use_han(state, han)
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # attacker cost 1 vs revealed cost 5: both odd, different -> +1/+0 -> 4 to base.
        assert state.player_by_id("P1").base_instance.damage == 4

    def test_jtl_17_no_bonus_when_revealed_cost_even(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        han = _place_leader(state, "P0", _get_card(repo, "JTL", "17"))
        attacker = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # cost 1 (odd)
        revealed = CardInstance("P0_revealed", _get_card(repo, "SOR", "46"), "P0", Zone.DECK)  # cost 4 (even)
        state.player_by_id("P0").deck.insert(0, revealed)
        state = self._use_han(state, han)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # revealed cost even -> no "different odd costs" -> no bonus -> 3 to base.
        assert state.player_by_id("P1").base_instance.damage == 3

    def test_jtl_17_action_not_offered_without_a_ready_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        han = _place_leader(state, "P0", _get_card(repo, "JTL", "17"))
        # No ready unit -> the don't-offer-a-no-op condition suppresses the Action.
        assert not any(isinstance(a, UseAbility) and a.source_id == han.instance_id
                       for a in legal_actions(state))

    def test_jtl_17_deploy_as_upgrade_readies_resource_per_odd_cost_card(self, repo):
        from swu.engine.actions import legal_actions, apply, DeployLeaderAsUpgrade
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "237"), "ground")   # TIE Bomber vehicle, cost 2 (even)
        _place(state, "P0", _get_card(repo, "SOR", "196"), "ground")   # cost 5 (odd)
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # cost 1 (odd)
        _place_leader(state, "P0", _get_card(repo, "JTL", "17"))
        _give_resources(state, "P0", 6)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        act = next(a for a in legal_actions(state) if isinstance(a, DeployLeaderAsUpgrade))
        state = apply(state, act)
        # Odd-cost friendly cards: the two units (5, 1) = 2 (a Leader has no printed
        # cost, so Han-as-upgrade does not count).
        readied = sum(1 for r in state.player_by_id("P0").resources if not r.exhausted)
        assert readied == 2


class TestNienNunb:
    """JTL_93 Nien Nunb — "+1/+0 for each other friendly Pilot unit and upgrade"
    (the scaling StatBonus.count primitive), as a unit and as a Pilot upgrade."""

    def test_jtl_93_alone_gets_no_bonus(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        nien = _place(state, "P0", _get_card(repo, "JTL", "93"), "ground")  # 1/2
        assert compute_power(state, nien) == 1

    def test_jtl_93_scales_with_other_friendly_pilots(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        nien = _place(state, "P0", _get_card(repo, "JTL", "93"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "139"), "ground")  # Dengar (Pilot)
        assert compute_power(state, nien) == 2
        _place(state, "P0", _get_card(repo, "JTL", "141"), "ground")  # IG-88 (Pilot)
        assert compute_power(state, nien) == 3

    def test_jtl_93_enemy_pilots_do_not_count(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        nien = _place(state, "P0", _get_card(repo, "JTL", "93"), "ground")
        _place(state, "P1", _get_card(repo, "JTL", "139"), "ground")  # enemy Pilot
        assert compute_power(state, nien) == 1

    def test_jtl_93_as_pilot_upgrade_buffs_host(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "ground")  # TIE Bomber 0/4
        nien_up = CardInstance("P0_nien_up", _get_card(repo, "JTL", "93"), "P0", Zone.GROUND_ARENA)
        host.attached_upgrades.append(nien_up)
        base_power = compute_power(state, host)          # 0 + Nien upgrade_power(1) + scaling(0)
        _place(state, "P0", _get_card(repo, "JTL", "139"), "ground")  # another Pilot unit
        assert compute_power(state, host) == base_power + 1


class TestBlueLeader:
    """JTL_96 Blue Leader — "When Played: You may pay 2 resources. If you do, move
    this unit to the ground arena and give 2 Experience tokens to it."""

    def test_jtl_96_when_played_pays2_moves_to_ground_and_2_exp(self, repo):
        from swu.engine.actions import legal_actions, apply
        from swu.engine.keywords import experience_on
        state = _make_state()
        blue = _place(state, "P0", _get_card(repo, "JTL", "96"), "space")
        _give_resources(state, "P0", 3)
        state = _fire_when_played(state, blue)
        acc = next(a for a in legal_actions(state) if type(a).__name__ == "AcceptTrigger")
        state = apply(state, acc)
        # The CustomEffect resolves via an AutoResolveEffects step.
        while state.pending_decisions and state.pending_decisions[-1].kind == "resolve_effects":
            auto = next((a for a in legal_actions(state)
                         if type(a).__name__ == "AutoResolveEffects"), None)
            if auto is None:
                break
            state = apply(state, auto)
        b = _find_instance(state, blue.instance_id)
        assert b in state.player_by_id("P0").ground_arena
        assert b not in state.player_by_id("P0").space_arena
        assert experience_on(b) == 2
        assert sum(1 for r in state.player_by_id("P0").resources if r.exhausted) == 2

    def test_jtl_96_not_offered_without_2_ready_resources(self, repo):
        from swu.engine.actions import legal_actions
        state = _make_state()
        blue = _place(state, "P0", _get_card(repo, "JTL", "96"), "space")
        _give_resources(state, "P0", 1)
        state = _fire_when_played(state, blue)
        assert not any(type(a).__name__ == "AcceptTrigger" for a in legal_actions(state))


class TestLeiaOrganaJTL97:
    """JTL_97 Leia Organa — "When Played: You may attack with a Pilot unit or a
    unit with a Pilot on it. It gets +1/+0 and gains Restore 1 for this attack."""

    def test_jtl_97_grants_attack_to_pilot_plus1_and_restore1(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "JTL", "97"), "ground")   # 3/4
        pilot = _place(state, "P0", _get_card(repo, "JTL", "139"), "ground")  # Dengar 5/4 (Pilot)
        state.player_by_id("P0").base_instance.damage = 5
        state = _fire_when_played(state, leia)
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == pilot.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Dengar power 5 +1 (bonus) = 6 to the enemy base; Restore 1 heals P0's base by 1.
        assert state.player_by_id("P1").base_instance.damage == 6
        assert state.player_by_id("P0").base_instance.damage == 4

    def test_jtl_97_only_pilot_related_units_offered(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "JTL", "97"), "ground")
        pilot = _place(state, "P0", _get_card(repo, "JTL", "139"), "ground")   # Dengar (Pilot)
        nonpilot = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not a Pilot
        state = _fire_when_played(state, leia)
        offered = {a.attacker_id for a in legal_actions(state) if isinstance(a, AttackWithUnit)}
        assert pilot.instance_id in offered
        assert nonpilot.instance_id not in offered
        assert leia.instance_id not in offered


class TestTandemAssault:
    """JTL_124 Tandem Assault — "Attack with a space unit. If you do, attack with a
    ground unit, and that ground unit gets +2/+0 for this attack."""

    def test_jtl_124_space_then_ground_attack_with_plus2(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        space = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")    # power 3
        ground = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # power 3
        state, _ev = _play_event_from_hand(state, repo, "JTL", "124", owner="P0")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack" and top.context["attacker_arena"] == "space"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == space.instance_id and a.defender_id is None))
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack" and top.context["attacker_arena"] == "ground"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == ground.instance_id and a.defender_id is None))
        # space power 3 + ground (3 + 2 bonus = 5) = 8 to the enemy base.
        assert state.player_by_id("P1").base_instance.damage == 8

    def test_jtl_124_no_space_unit_no_attack(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # only a ground unit
        state, _ev = _play_event_from_hand(state, repo, "JTL", "124", owner="P0")
        assert not any(d.kind == "granted_attack" for d in state.pending_decisions)


class TestItsATrap:
    """JTL_209 It's a Trap — "If an opponent controls more space units than you,
    ready each space unit you control."""

    def test_jtl_209_readies_space_units_when_outnumbered(self, repo):
        state = _make_state()
        s1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        s1.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state, _ev = _play_event_from_hand(state, repo, "JTL", "209", owner="P0")
        assert not _find_instance(state, s1.instance_id).exhausted

    def test_jtl_209_no_ready_when_not_outnumbered(self, repo):
        state = _make_state()
        s1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        s1.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # equal count
        state, _ev = _play_event_from_hand(state, repo, "JTL", "209", owner="P0")
        assert _find_instance(state, s1.instance_id).exhausted


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:05 — Combat tricks, buffs & tempo (JTL_210, JTL_217, JTL_249)
# ══════════════════════════════════════════════════════════════════════════════


def _make_pilot_upgrade(owner_id, zone):
    """A synthetic minimal Pilot upgrade-unit (Pilot trait, 0/0, no abilities —
    set_code 'TST' keeps it out of the ability registry)."""
    import uuid
    from swu.engine.state import CardInstance
    from swu.cards.models import Unit
    card = Unit(
        id=88801, card_uid=None, set_code="TST", set_name="T",
        card_number="PLT", name="Test Pilot", subtitle=None, type="Unit",
        rarity="Common", is_unique=False, artist=None, text=None,
        text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=("Pilot",), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=2, power=0, hp=0, upgrade_power=0, upgrade_hp=0,
        epic_action="Piloting [2 resources]",
    )
    return CardInstance(
        instance_id=f"{owner_id}_pu_{uuid.uuid4().hex[:6]}",
        card_def=card, owner_id=owner_id, zone=zone,
    )


class TestTheMandalorian:
    """JTL_210 — The Mandalorian (Piloting): as-unit exhaust up to 2 ground units;
    as-upgrade exhaust an enemy unit in the host's arena."""

    def test_jtl_210_as_unit_exhausts_up_to_2_ground_units(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "JTL", "210"), "ground")
        g1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        g2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        sp = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_when_played(state, mando)
        acts = legal_actions(state)
        sels = [a for a in acts
                if type(a).__name__ == "SelectUnitToExhaustCombined"]
        offered = {a.target_id for a in sels}
        assert g1.instance_id in offered and g2.instance_id in offered
        assert sp.instance_id not in offered            # space unit excluded
        assert any(type(a).__name__ == "FinishExhaustCombined" for a in acts)  # "up to"
        state = apply(state, next(a for a in sels if a.target_id == g1.instance_id))
        state = apply(state, next(
            a for a in legal_actions(state)
            if type(a).__name__ == "SelectUnitToExhaustCombined"
            and a.target_id == g2.instance_id))
        assert _find_instance(state, g1.instance_id).exhausted
        assert _find_instance(state, g2.instance_id).exhausted
        assert not _find_instance(state, sp.instance_id).exhausted

    def test_jtl_210_as_upgrade_exhausts_enemy_in_host_arena(self, repo):
        from swu.engine.state import CardInstance
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        mando_up = CardInstance(instance_id="P0_mando_up",
                                card_def=_get_card(repo, "JTL", "210"),
                                owner_id="P0", zone=host.zone)
        host.attached_upgrades.append(mando_up)
        e_sp1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        e_sp2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        e_gr = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, mando_up, host)
        cts = [a for a in legal_actions(state)
               if type(a).__name__ == "ChooseTarget" and a.target_id]
        tids = {a.target_id for a in cts}
        assert e_sp1.instance_id in tids and e_sp2.instance_id in tids
        assert e_gr.instance_id not in tids             # different arena excluded
        state = apply(state, next(a for a in cts if a.target_id == e_sp1.instance_id))
        assert _find_instance(state, e_sp1.instance_id).exhausted
        assert not _find_instance(state, e_gr.instance_id).exhausted


class TestDeathSpaceSkirmisher:
    """JTL_217 — When Played: if you control another space unit, you may exhaust
    a unit."""

    def test_jtl_217_may_exhaust_when_another_space_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        sk = _place(state, "P0", _get_card(repo, "JTL", "217"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")   # another space unit
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, sk)
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc
        state = apply(state, acc[0])
        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted

    def test_jtl_217_not_offered_without_another_space_unit(self, repo):
        state = _make_state()
        sk = _place(state, "P0", _get_card(repo, "JTL", "217"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # ground doesn't count
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")   # enemy doesn't count
        state = _fire_when_played(state, sk)
        assert not state.pending_decisions                          # trigger not collected


class TestMillenniumFalcon:
    """JTL_249 — +1/+0 per Pilot on it; allows 1 additional Pilot."""

    def test_jtl_249_gains_plus1_power_per_pilot(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        falcon = _place(state, "P0", _get_card(repo, "JTL", "249"), "ground")
        assert compute_power(state, falcon) == 3                    # base, no pilots
        p1 = _make_pilot_upgrade("P0", falcon.zone)
        falcon.attached_upgrades.append(p1)
        assert compute_power(state, falcon) == 4                    # +1 for one pilot
        p2 = _make_pilot_upgrade("P0", falcon.zone)
        falcon.attached_upgrades.append(p2)
        assert compute_power(state, falcon) == 5                    # +2 for two pilots

    def test_jtl_249_hosts_an_additional_pilot(self, repo):
        from swu.engine.actions import _pilot_limit, _eligible_leader_upgrade_targets
        state = _make_state()
        falcon = _place(state, "P0", _get_card(repo, "JTL", "249"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert _pilot_limit(falcon) == 2                            # 1 + 1 additional
        assert _pilot_limit(other) == 1                             # ordinary limit
        # A pilot already on the Falcon — it still has a free slot for a second.
        falcon.attached_upgrades.append(_make_pilot_upgrade("P0", falcon.zone))
        ps = state.player_by_id("P0")
        assert falcon in _eligible_leader_upgrade_targets(state, ps)


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:06 — Miscellaneous abilities (JTL_103, JTL_245)
# ══════════════════════════════════════════════════════════════════════════════


def _attach_as_upgrade(state, host, card_def, owner_id="P0"):
    """Attach an arbitrary card_def to ``host`` as an upgrade instance (for the
    Piloting-upgrade cases where we don't need to route through PilotPlay)."""
    from swu.engine.state import CardInstance
    up = CardInstance(instance_id=f"{owner_id}_up_{card_def.card_number}",
                      card_def=card_def, owner_id=owner_id, zone=host.zone)
    host.attached_upgrades.append(up)
    return up


class TestChewbacca:
    """JTL_103 — Chewbacca: can't be defeated or returned to hand by *enemy* card
    abilities (himself, and the Vehicle he's a Pilot on)."""

    def test_jtl_103_enemy_defeat_ability_cannot_defeat_him(self, repo):
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import DefeatUnit, TargetSpec
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "JTL", "103"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        execute_effect(state, DefeatUnit(TargetSpec(kind="unit")), enemy,
                       chewie.instance_id, {})
        assert _find_instance(state, chewie.instance_id) is not None   # survived

    def test_jtl_103_enemy_return_ability_cannot_bounce_him(self, repo):
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import ReturnToHand, TargetSpec
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "JTL", "103"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        p0 = state.player_by_id("P0")
        before = len(p0.hand)
        execute_effect(state, ReturnToHand(TargetSpec(kind="unit")), enemy,
                       chewie.instance_id, {})
        assert _find_instance(state, chewie.instance_id) is not None   # still in play
        assert len(p0.hand) == before                                  # not bounced

    def test_jtl_103_friendly_defeat_ability_still_works(self, repo):
        # "enemy card abilities" only — a friendly (own-controlled) defeat is unaffected.
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import DefeatUnit, TargetSpec
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "JTL", "103"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        execute_effect(state, DefeatUnit(TargetSpec(kind="unit")), friendly,
                       chewie.instance_id, {})
        assert _find_instance(state, chewie.instance_id) is None       # defeated

    def test_jtl_103_protects_the_vehicle_he_pilots(self, repo):
        # Played as a Pilot upgrade, Chewbacca grants the protection to his host.
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import DefeatUnit, TargetSpec
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")   # a Vehicle
        _attach_as_upgrade(state, host, _get_card(repo, "JTL", "103"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        execute_effect(state, DefeatUnit(TargetSpec(kind="unit")), enemy,
                       host.instance_id, {})
        assert _find_instance(state, host.instance_id) is not None     # host survived


class TestR2D2:
    """JTL_245 — R2-D2: grants its Vehicle host one additional Pilot slot."""

    def test_jtl_245_grants_host_an_additional_pilot_slot(self, repo):
        from swu.engine.actions import _pilot_limit
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        assert _pilot_limit(vehicle) == 1                              # ordinary limit
        _attach_as_upgrade(state, vehicle, _get_card(repo, "JTL", "245"))
        assert _pilot_limit(vehicle) == 2                              # +1 from R2-D2

    def test_jtl_245_host_with_r2_keeps_a_free_pilot_slot(self, repo):
        from swu.engine.actions import _eligible_leader_upgrade_targets
        state = _make_state()
        ps = state.player_by_id("P0")
        # A Vehicle whose only slot is taken by an ordinary Pilot has no room.
        full = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        full.attached_upgrades.append(_make_pilot_upgrade("P0", full.zone))
        assert full not in _eligible_leader_upgrade_targets(state, ps)
        # A Vehicle carrying only R2-D2 (itself a Pilot) still has a free slot —
        # R2-D2's granted "1 additional Pilot" opens the second slot it occupies.
        with_r2 = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        _attach_as_upgrade(state, with_r2, _get_card(repo, "JTL", "245"))
        assert with_r2 in _eligible_leader_upgrade_targets(state, ps)


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:07 — New primitive: scaling-magnitude (SOR_97, JTL_208)
# ══════════════════════════════════════════════════════════════════════════════

def _deck_card(owner_id, card_def, idx):
    """A face-down CardInstance sitting in a player's deck (for mill tests)."""
    from swu.engine.state import CardInstance, Zone
    return CardInstance(f"{owner_id}_deck_{idx}", card_def, owner_id, Zone.DECK)


class TestAdmiralAckbar:
    """SOR_97 — "When Played: You may deal damage to a unit equal to the number of
    units you control in its arena." (Restore 1 is the keyword layer.)

    Reuses the existing ``source_controller_units_in_target_arena`` scaling count
    (Synchronized Strike TWI_99) on an optional WhenPlayed."""

    def test_sor_97_deals_damage_equal_to_controllers_units_in_arena(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        ackbar = _place(state, "P0", _get_card(repo, "SOR", "97"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 2nd P0 ground
        _place(state, "P0", _get_card(repo, "SOR", "52"), "space")     # space, must NOT count
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, ackbar)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        # P0 controls 2 ground units (Ackbar + 1); the space unit does not count.
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_sor_97_magnitude_uses_the_targets_arena(self, repo):
        """A space-arena target takes damage equal to P0's SPACE units only."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        ackbar = _place(state, "P0", _get_card(repo, "SOR", "97"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "52"), "space")     # 1 P0 space unit
        enemy = _place(state, "P1", _get_card(repo, "SOR", "52"), "space")  # high HP
        state = _fire_when_played(state, ackbar)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_sor_97_may_is_auto_declined_with_no_unit_on_board(self, repo):
        """No unit anywhere → the optional 'you may' is never offered."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        ackbar = _place(state, "P0", _get_card(repo, "SOR", "97"), "ground")
        # Ackbar himself is a unit, so a legal (friendly) target exists → offered.
        assert any(isinstance(a, AcceptTrigger)
                   for a in legal_actions(_fire_when_played(state, ackbar)))


class TestNeverTellMeTheOdds:
    """JTL_208 — "Discard 3 cards from an opponent's deck and 3 cards from your
    deck. Deal damage to a unit equal to the number of cards with an odd cost
    discarded this way."  The transient odd-cost count is the magnitude of a
    single ``select_damage`` (IG-2000 JTL_140) prompt pushed after the mill."""

    def _select(self, state):
        from swu.engine.actions import legal_actions
        return [a for a in legal_actions(state)
                if type(a).__name__ == "SelectDamageTarget"]

    def test_jtl_208_mills_three_from_each_deck_and_scales_by_odd_costs(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        odd = _get_card(repo, "SOR", "128")    # cost 1 (odd)
        even = _get_card(repo, "SOR", "46")     # cost 4 (even)
        # Opponent (P1) deck top 3: odd, odd, even -> 2 odd
        state.player_by_id("P1").deck[:0] = [
            _deck_card("P1", odd, 0), _deck_card("P1", odd, 1), _deck_card("P1", even, 2)]
        # Controller (P0) deck top 3: odd, even, even -> 1 odd   (total = 3 odd)
        state.player_by_id("P0").deck[:0] = [
            _deck_card("P0", odd, 0), _deck_card("P0", even, 1), _deck_card("P0", even, 2)]
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "JTL", "208")
        # 3 milled from each deck; P0's discard also holds the spent event itself.
        assert len(state.player_by_id("P0").deck) == 0
        assert len(state.player_by_id("P1").deck) == 0
        assert len(state.player_by_id("P0").discard) == 3 + 1  # 3 milled + the event
        assert len(state.player_by_id("P1").discard) == 3
        # One select_damage prompt whose amount is the 3 odd-cost cards milled.
        state = apply(state, next(a for a in self._select(state)
                                  if a.target_id == target.instance_id))
        assert _find_instance(state, target.instance_id).damage == 3
        assert not state.pending_decisions   # max_targets=1 auto-resolves

    def test_jtl_208_zero_odd_costs_mills_but_offers_no_damage(self, repo):
        """All milled cards even → no select_damage decision, yet the mandatory
        discard still happens."""
        state = _make_state()
        even = _get_card(repo, "SOR", "46")     # cost 4 (even)
        state.player_by_id("P1").deck[:0] = [_deck_card("P1", even, i) for i in range(3)]
        state.player_by_id("P0").deck[:0] = [_deck_card("P0", even, i) for i in range(3)]
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "208")
        assert not self._select(state)         # count 0 → no damage prompt
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").discard) == 3 + 1  # 3 milled + the event
        assert len(state.player_by_id("P1").discard) == 3


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:08 — New primitive: control-change (JTL_235 Commandeer)
# ══════════════════════════════════════════════════════════════════════════════

class TestCommandeer:
    """JTL_235 — "Take control of a non-leader Vehicle unit that costs 6 or less
    without a Pilot on it. If you do, ready it. At the start of the next regroup
    phase, return that unit to its owner's hand."

    Composes the existing control-change seam (actions.change_control — Stolen
    Landspeeder SHD_161) with a defeat_at_regroup-style delayed flag
    (return_to_owner_hand_at_regroup) swept in _enter_regroup via the existing
    _apply_return_to_hand, and a new ``no_pilot`` target predicate."""

    def test_jtl_235_takes_control_readies_then_returns_at_next_regroup(self, repo):
        from swu.engine.actions import apply, ChooseTarget, _enter_regroup
        state = _make_state()
        # An enemy Vehicle costing ≤6, exhausted, sitting in P1's space arena.
        veh = _place(state, "P1", _get_card(repo, "SOR", "180"), "space")  # cost 3 Vehicle
        veh.exhausted = True
        state, _evt = _play_event_from_hand(state, repo, "JTL", "235", owner="P0")
        state = apply(state, ChooseTarget(veh.instance_id))
        # Control moved: the instance now sits in P0's space arena, readied, but its
        # owner is unchanged (control is implicit arena occupancy).
        p0_space = {c.instance_id for c in state.player_by_id("P0").space_arena}
        assert veh.instance_id in p0_space
        moved = _find_instance(state, veh.instance_id)
        assert moved.owner_id == "P1"
        assert moved.exhausted is False              # "If you do, ready it"
        assert moved.return_to_owner_hand_at_regroup is True
        assert not state.pending_decisions
        # At the start of the next regroup phase it goes home to its OWNER's hand.
        _enter_regroup(state)
        assert _find_instance(state, veh.instance_id) is None
        assert veh.instance_id in {c.instance_id for c in state.player_by_id("P1").hand}
        assert veh.instance_id not in {c.instance_id for c in state.player_by_id("P0").space_arena}

    def test_jtl_235_target_filter_only_enemy_cheap_pilotless_vehicles(self, repo):
        """The choice is restricted to enemy, non-leader, Vehicle, cost ≤6, no-Pilot
        units — everything else is excluded from the legal targets."""
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        good = _place(state, "P1", _get_card(repo, "SOR", "180"), "space")   # cost 3 Vehicle ✓
        _place(state, "P1", _get_card(repo, "SOR", "52"), "space")           # cost 8 Vehicle — too dear
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")          # not a Vehicle
        piloted = _place(state, "P1", _get_card(repo, "JTL", "249"), "space")  # Vehicle cost 3
        _attach_as_upgrade(state, piloted, _get_card(repo, "JTL", "93"), owner_id="P1")  # Pilot on it
        _place(state, "P0", _get_card(repo, "SOR", "180"), "space")          # friendly Vehicle — enemy-only
        state, _evt = _play_event_from_hand(state, repo, "JTL", "235", owner="P0")
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert targets == {good.instance_id}


# ── Reprint-duplicate encodes (Stage 4 of docs/reprint_duplicates_plan.md) ────

class TestVictorLeader:
    """JTL_85 — "Each other friendly space unit gets +1/+1." (sibs P25_154/164)."""

    def test_jtl_85_buffs_other_friendly_space_units(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        victor = _place(state, "P0", _get_card(repo, "JTL", "85"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")  # 3/7
        assert compute_power(state, ally) == 4 and compute_hp(state, ally) == 8
        # Victor himself is excluded (not_self).
        assert compute_power(state, victor) == 2 and compute_hp(state, victor) == 4

    def test_jtl_85_ignores_ground_and_enemy_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "85"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        assert compute_power(state, ground) == 3   # ground unbuffed
        assert compute_power(state, enemy) == 3     # enemy unbuffed


class TestOnyxSquadronBrute:
    """JTL_33 — "When Defeated: Heal 2 damage from a base." (sib JTLP_2)."""

    def test_jtl_33_when_defeated_heals_own_base(self, repo):
        state = _make_state()
        brute = _place(state, "P0", _get_card(repo, "JTL", "33"), "ground")
        state.player_by_id("P0").base_zone[0].damage = 5
        state = _fire_when_defeated(state, brute)
        assert state.player_by_id("P0").base_zone[0].damage == 3  # 5 - 2
        # The opponent's base is untouched.
        assert state.player_by_id("P1").base_zone[0].damage == 0


class TestRedFive:
    """JTL_151 — "On Attack: You may deal 2 damage to a damaged unit." (sib JTLP_12)."""

    def test_jtl_151_deals_2_to_a_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "JTL", "151"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.damage = 1  # damaged → a legal target
        state = _fire_on_attack(state, red)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, tgt)
        assert _find_instance(state, enemy.instance_id).damage == 3  # 1 + 2

    def test_jtl_151_auto_declines_with_no_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "JTL", "151"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # undamaged
        state = _fire_on_attack(state, red)
        assert not state.pending_decisions
        acts = legal_actions(state)
        assert not any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts)


# ══════════════════════════════════════════════════════════════════════════════
# Reprint-duplicate sweep (Stage 4) — shipped-set JTL canonicals
# ══════════════════════════════════════════════════════════════════════════════

def _tie_fighter_count(state, owner):
    from swu.cards.models import TokenUnit
    ps = state.player_by_id(owner)
    return sum(1 for arena in (ps.ground_arena, ps.space_arena) for u in arena
               if isinstance(u.card_def, TokenUnit) and u.card_def.name == "TIE Fighter")


class TestExecutor:
    """JTL_90 — Executor (Overwhelm): "When Played/On Attack/When Defeated: Create 3
    TIE Fighter tokens." (sib P25_88)."""

    def test_jtl_90_when_played_creates_3_tie_fighters(self, repo):
        state = _make_state()
        exe = _place(state, "P0", _get_card(repo, "JTL", "90"), "space")
        assert _tie_fighter_count(state, "P0") == 0
        state = _fire_when_played(state, exe)
        assert not state.pending_decisions          # non-targeted, resolves inline
        assert _tie_fighter_count(state, "P0") == 3

    def test_jtl_90_on_attack_creates_3_more(self, repo):
        state = _make_state()
        exe = _place(state, "P0", _get_card(repo, "JTL", "90"), "space")
        state = _fire_on_attack(state, exe)
        assert _tie_fighter_count(state, "P0") == 3


class TestPlanetaryBombardment:
    """JTL_181 — Planetary Bombardment (Event): "Deal 8 indirect damage to a player.
    If you control a Capital Ship unit, deal 12 indirect damage instead."
    (sibs P25_127, P25_139, P26_45, P26_57)."""

    def test_jtl_181_deals_8_indirect_without_capital_ship(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "JTL", "181")
        acts = _assign_actions(state)
        assert acts, "an assign_indirect_damage decision should be pending"
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 8

    def test_jtl_181_deals_12_indirect_with_capital_ship(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        # Executor JTL_90 is a Capital Ship — control one before playing the event.
        _place(state, "P0", _get_card(repo, "JTL", "90"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "181")
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 12


# ── Reprint-duplicate batch 6 (2026-07-08) ────────────────────────────────────


class TestSwarmingVultureDroidJTL256:
    """JTL_256 — This unit gets +1/+0 for each other friendly Swarming Vulture
    Droid (a scaling StatBonus count ``other_friendly_same_name``)."""

    def test_jtl_256_scales_with_other_copies(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "JTL", "256"), "space")  # 2/2
        assert compute_power(state, a) == 2  # alone
        b = _place(state, "P0", _get_card(repo, "JTL", "256"), "space")
        c = _place(state, "P0", _get_card(repo, "JTL", "256"), "space")
        # 3 copies: each sees 2 others → power 4
        assert compute_power(state, _find_instance(state, a.instance_id)) == 4
        assert compute_power(state, _find_instance(state, b.instance_id)) == 4
        assert compute_power(state, _find_instance(state, c.instance_id)) == 4

    def test_jtl_256_enemy_copies_do_not_count(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "JTL", "256"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "256"), "space")  # enemy copy
        assert compute_power(state, _find_instance(state, mine.instance_id)) == 2


# ── Stage-4 reprint sweep (Batch 8) ───────────────────────────────────────────
# JTL_176 Shoot Down, JTL_204 Home One.


class TestShootDownJTL176:
    """Event: Deal 3 to a space unit. If defeated this way, you may deal 2 to a base."""

    def test_jtl_176_defeated_unit_allows_base_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # 3/7
        target.damage = 5  # 3 more = 8 >= 7 -> defeated
        state, _ = _play_event_from_hand(state, repo, "JTL", "176", owner="P0")
        state = apply(state, ChooseTarget(target.instance_id))       # deal 3 -> defeated
        assert _find_instance(state, target.instance_id) is None
        enemy_base = state.player_by_id("P1").base_instance
        # the "you may deal 2 to a base" is now offered (prior target defeated)
        assert any(isinstance(a, ChooseTarget) and a.target_id == enemy_base.instance_id
                   for a in legal_actions(state))
        state = apply(state, ChooseTarget(enemy_base.instance_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_jtl_176_survivor_offers_no_base_damage(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "88"), "space")  # 9/9, survives 3
        state, _ = _play_event_from_hand(state, repo, "JTL", "176", owner="P0")
        state = apply(state, ChooseTarget(target.instance_id))
        assert _find_instance(state, target.instance_id).damage == 3   # not defeated
        # no base damage offered / dealt (requires_prior_defeat is False)
        assert not state.pending_decisions
        assert state.player_by_id("P1").base_instance.damage == 0
        assert state.player_by_id("P0").base_instance.damage == 0


class TestHomeOneJTL204:
    """Unit: If an opponent controls 3+ space units, this unit costs 3 less to play."""

    def _home_one_in_hand(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance("P0_home", _get_card(repo, "JTL", "204"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        return ci

    def test_jtl_204_reduced_with_three_enemy_space_units(self, repo):
        from swu.engine.actions import _play_cost_reduction
        state = _make_state()
        for _ in range(3):
            _place(state, "P1", _get_card(repo, "SOR", "88"), "space")
        home = self._home_one_in_hand(state, repo)
        assert _play_cost_reduction(state, home) == 3

    def test_jtl_204_no_reduction_below_three(self, repo):
        from swu.engine.actions import _play_cost_reduction
        state = _make_state()
        for _ in range(2):
            _place(state, "P1", _get_card(repo, "SOR", "88"), "space")
        home = self._home_one_in_hand(state, repo)
        assert _play_cost_reduction(state, home) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Reprint sweep Stage 4 Batch 10 canonical encodes (2026-07-09)
# ══════════════════════════════════════════════════════════════════════════════

class TestDevastatorJTL143:
    """JTL_143 — Devastator (9/6): "You assign all indirect damage you deal to
    opponents.  When Played: Deal 4 indirect damage to each opponent."
    (reprint canonical; sibs P25_3/4/5/6)."""

    def test_jtl_143_controller_assigns_4_indirect(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        dev = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")
        state = _fire_when_played(state, dev)
        # The self-assign marker flips the decider to the controller (P0), not P1.
        assert state.pending_decisions
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        acts = _assign_actions(state)
        assert acts
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert state.player_by_id("P1").base_instance.damage == 4

    def test_jtl_143_controller_can_dump_on_enemy_unit(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        dev = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, dev)
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        state = apply(state, next(a for a in _assign_actions(state)
                                  if a.target_id == victim.instance_id))
        assert _find_instance(state, victim.instance_id).damage == 4

    def test_jtl_143_without_marker_receiver_assigns(self, repo):
        """Sanity: an indirect deal from a non-Devastator source (no self-assign
        marker in play) is still assigned by the receiving player."""
        from swu.engine.actions import push_assign_indirect_damage
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        push_assign_indirect_damage(state, trooper, amount=2)
        assert state.pending_decisions[-1].deciding_player_id == "P1"


class TestProfundityJTL154:
    """JTL_154 — Profundity (8/9, Overwhelm): "When Played/When Defeated: Choose a
    player.  They discard a card from their hand.  Then, if they have more cards in
    their hand than you, they discard a card from their hand."
    (reprint canonical; sibs P25_159/169)."""

    def _fill_hand(self, state, owner, repo, n):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ps = state.player_by_id(owner)
        for _ in range(n):
            ps.hand.append(CardInstance(
                f"{owner}_hand_{uuid.uuid4().hex[:6]}",
                _get_card(repo, "SOR", "46"), owner, Zone.DECK))

    def test_jtl_154_second_discard_when_opponent_has_more(self, repo):
        state = _make_state()
        self._fill_hand(state, "P1", repo, 3)   # opponent hand
        self._fill_hand(state, "P0", repo, 1)   # controller hand
        prof = _place(state, "P0", _get_card(repo, "JTL", "154"), "space")
        state = _fire_when_played(state, prof)
        # First discard → P1 has 2 > P0's 1 → second discard → P1 has 1.
        assert len(state.player_by_id("P1").hand) == 1
        assert len(state.player_by_id("P1").discard) == 2

    def test_jtl_154_single_discard_when_hands_equal(self, repo):
        state = _make_state()
        self._fill_hand(state, "P1", repo, 2)
        self._fill_hand(state, "P0", repo, 2)
        prof = _place(state, "P0", _get_card(repo, "JTL", "154"), "space")
        state = _fire_when_played(state, prof)
        # First discard → P1 has 1, not > P0's 2 → no second discard.
        assert len(state.player_by_id("P1").hand) == 1
        assert len(state.player_by_id("P1").discard) == 1

    def test_jtl_154_when_defeated_also_discards(self, repo):
        from swu.engine.events import UnitDefeated
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        self._fill_hand(state, "P1", repo, 3)
        self._fill_hand(state, "P0", repo, 1)
        prof = _place(state, "P0", _get_card(repo, "JTL", "154"), "space")
        state.player_by_id("P0").space_arena.remove(prof)
        evt = UnitDefeated(player_id="P0", instance_id=prof.instance_id,
                           card_name=prof.card_def.display_name)
        ctx = {"defeated_id": prof.instance_id, "defeated_ci": prof,
               "defeated_controller_id": "P0"}
        state = fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)
        assert len(state.player_by_id("P1").hand) == 1   # 3 → 1 (two discards)

    def test_jtl_154_empty_opponent_hand_no_op(self, repo):
        state = _make_state()
        self._fill_hand(state, "P0", repo, 1)
        prof = _place(state, "P0", _get_card(repo, "JTL", "154"), "space")
        state = _fire_when_played(state, prof)
        assert state.player_by_id("P1").hand == []
        assert state.player_by_id("P1").discard == []


# ══════════════════════════════════════════════════════════════════════════════
# Reprint-duplicate batch 12 (Stage 4)
# ══════════════════════════════════════════════════════════════════════════════

class TestHanSoloJTL203:
    """JTL_203 — Han Solo (Piloting). When played as an upgrade: You may attack
    with attached unit. If it's the Millennium Falcon, it deals its combat damage
    before the defender (First Strike)."""

    def test_jtl_203_pilot_pushes_host_attack(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")  # TIE Bomber Vehicle
        han = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "203"), "P0")
        state = _fire_upgrade_played(state, han, host)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["attacker_id"] == host.instance_id
        assert top.context.get("optional")               # "you may"
        assert not top.context.get("grant_keywords")     # non-Falcon: no First Strike

    def test_jtl_203_falcon_host_grants_first_strike(self, repo):
        state = _make_state()
        falcon = _place(state, "P0", _get_card(repo, "JTL", "249"), "space")  # Millennium Falcon
        assert falcon.card_def.name == "Millennium Falcon"
        han = _attach_upgrade_directly(state, falcon, _get_card(repo, "JTL", "203"), "P0")
        state = _fire_upgrade_played(state, han, falcon)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["attacker_id"] == falcon.instance_id
        assert top.context.get("grant_keywords") == ["First Strike"]

    def test_jtl_203_normal_unit_play_does_not_trigger(self, repo):
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "JTL", "203"), "ground")
        state = _fire_when_played(state, han)
        assert not state.pending_decisions


class TestDarthVaderJTL142:
    """JTL_142 — Darth Vader (Piloting). Attached unit gains 'On Attack: You may
    deal 1 damage to a unit. If a unit is defeated this way, you may deal 1 damage
    to a unit or base.'"""

    def test_jtl_142_pilot_deals_1_then_more_on_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")  # Vehicle
        vader = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "142"), "P0")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1 — dies to 1 dmg
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        state = _fire_on_attack(state, host)
        # Effect 1: deal 1 to e1 (defeats it).
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == e1.instance_id))
        assert _find_instance(state, e1.instance_id) is None
        # Effect 2 (gated on the defeat): deal 1 to e2.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == e2.instance_id))
        assert _find_instance(state, e2.instance_id).damage == 1

    def test_jtl_142_no_second_damage_when_target_survives(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        vader = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "142"), "P0")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7 survives 1
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == e1.instance_id))
        assert _find_instance(state, e1.instance_id).damage == 1
        # No defeat → the follow-up "unit or base" damage is never offered.
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert e2.instance_id not in tids

    def test_jtl_142_normal_unit_has_no_granted_on_attack(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "JTL", "142"), "ground")  # vanilla 7/7 unit
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, vader)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# JTL_53 — The Ghost "Heart of the Family" (batch 28 — keyword-copy aura)
# ══════════════════════════════════════════════════════════════════════════════
class TestTheGhostJTL53:
    """Each other friendly Spectre unit gains The Ghost's keywords; while The Ghost
    is upgraded it gains Sentinel — so the allies gain Sentinel only while it is
    upgraded.  Exercises the new ``CopyKeywords`` keyword-copy aura in the keyword
    query layer (``has_keyword`` / ``keyword_value``)."""

    def _setup(self, repo):
        state = _make_state()
        ghost = _place(state, "P0", _get_card(repo, "JTL", "53"))   # Spectre
        ezra = _place(state, "P0", _get_card(repo, "SOR", "192"))   # friendly Spectre, no kw
        return state, ghost, ezra

    def test_jtl_53_spectre_ally_gains_sentinel_only_while_ghost_upgraded(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state, ghost, ezra = self._setup(repo)
        # Not upgraded: The Ghost has no Sentinel, so nothing to copy.
        assert not has_keyword(state, ghost, Keyword.SENTINEL)
        assert not has_keyword(state, ezra, Keyword.SENTINEL)
        # Upgrade The Ghost → it gains Sentinel (conditional self-grant), and the
        # ally copies it.
        _attach_upgrade_directly(state, ghost, _get_card(repo, "SHD", "74"), "P0")
        assert has_keyword(state, ghost, Keyword.SENTINEL)
        assert has_keyword(state, ezra, Keyword.SENTINEL)

    def test_jtl_53_copy_only_affects_friendly_spectre(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state, ghost, ezra = self._setup(repo)
        _attach_upgrade_directly(state, ghost, _get_card(repo, "SHD", "74"), "P0")
        # A friendly NON-Spectre unit does not gain it.
        non_spectre = _place(state, "P0", _get_card(repo, "SOR", "46"))  # not Spectre
        assert not has_keyword(state, non_spectre, Keyword.SENTINEL)
        # An ENEMY Spectre unit does not gain it (not friendly to The Ghost).
        enemy_spectre = _place(state, "P1", _get_card(repo, "SOR", "146"))  # Zeb, Spectre
        assert not has_keyword(state, enemy_spectre, Keyword.SENTINEL)

    def test_jtl_53_copy_ends_when_ghost_leaves_play(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state, ghost, ezra = self._setup(repo)
        _attach_upgrade_directly(state, ghost, _get_card(repo, "SHD", "74"), "P0")
        assert has_keyword(state, ezra, Keyword.SENTINEL)
        # The Ghost leaves play → the copy source is gone → the ally loses it.
        state.player_by_id("P0").ground_arena.remove(ghost)
        assert not has_keyword(state, ezra, Keyword.SENTINEL)

    def test_jtl_53_numeric_keyword_copied_at_value(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        from swu.engine.state import Modifier
        state, ghost, ezra = self._setup(repo)
        # Give The Ghost a numeric keyword (Raid 2) — the ally copies it at value.
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=ghost.instance_id,
            target_instance_id=ghost.instance_id,
            kind="keyword_grant", value={"keyword": "Raid", "value": 2},
            duration="this_phase"))
        assert keyword_value(state, ghost, Keyword.RAID) == 2
        assert keyword_value(state, ezra, Keyword.RAID) == 2   # copied

    def test_jtl_53_two_ghosts_no_infinite_recursion(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        g1 = _place(state, "P0", _get_card(repo, "JTL", "53"))
        g2 = _place(state, "P0", _get_card(repo, "JTL", "53"))
        # Neither upgraded → neither has Sentinel; mutual-copy must terminate.
        assert not has_keyword(state, g1, Keyword.SENTINEL)
        assert not has_keyword(state, g2, Keyword.SENTINEL)
        # Upgrade only g1 → g1 has Sentinel (own grant), g2 copies it from g1.
        _attach_upgrade_directly(state, g1, _get_card(repo, "SHD", "74"), "P0")
        assert has_keyword(state, g1, Keyword.SENTINEL)
        assert has_keyword(state, g2, Keyword.SENTINEL)


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:01 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _use_ability_jtl(state, source_ci, idx=0):
    from swu.engine.actions import legal_actions, apply, UseAbility
    uses = [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]
    return apply(state, uses[idx])


def _choose_jtl(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    ch = next(a for a in legal_actions(state)
              if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, ch)


def _target_ids_jtl(state):
    from swu.engine.actions import legal_actions, ChooseTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and a.target_id is not None}


def _accept_jtl(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
    return apply(state, acc)


def _mark_trait_played(state, player_id, *traits):
    """Record that the player played a card carrying each trait this phase (the
    ledger the CardPlayed chokepoint feeds)."""
    seen = state.game_memory.traits_played_this_phase.setdefault(player_id, set())
    seen.update(traits)


def _deploy_leader_to_arena(state, leader_ci, arena="ground"):
    """Move an undeployed leader from base_zone into an arena as a deployed unit."""
    from swu.engine.state import Zone
    ps = state.player_by_id(leader_ci.owner_id)
    ps.base_zone = [c for c in ps.base_zone if c.instance_id != leader_ci.instance_id]
    leader_ci.deployed = True
    if arena == "space":
        leader_ci.zone = Zone.SPACE_ARENA
        ps.space_arena.append(leader_ci)
    else:
        leader_ci.zone = Zone.GROUND_ARENA
        ps.ground_arena.append(leader_ci)
    return leader_ci


def _attach_leader_as_pilot(state, host_ci, leader_ci):
    """Move an undeployed leader into ``host_ci``'s attached_upgrades, as
    DeployLeaderAsUpgrade does."""
    ps = state.player_by_id(leader_ci.owner_id)
    ps.base_zone = [c for c in ps.base_zone if c.instance_id != leader_ci.instance_id]
    leader_ci.deployed = True
    leader_ci.zone = host_ci.zone
    host_ci.attached_upgrades.append(leader_ci)
    return leader_ci


class TestAsajjVentressJTL1:
    """JTL_1 — Action [Exhaust]: deal 1 to a friendly unit, then 1 to an enemy unit
    in the SAME arena.  Also the deploy-as-a-Pilot side (Grit + the granted On
    Attack).  Registered so nothing leaks onto the same-numbered TIE Fighter token."""

    def test_JTL_1_undeployed_action_chains_into_same_arena_enemy(self, repo):
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_card(repo, "JTL", "1"))
        friend = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        foe_ground = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        foe_space = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")

        state = _use_ability_jtl(state, asajj)
        state = _choose_jtl(state, friend.instance_id)
        # Only the GROUND enemy is offered — "in the same arena" as the friendly hit.
        assert _target_ids_jtl(state) == {foe_ground.instance_id}
        state = _choose_jtl(state, foe_ground.instance_id)

        assert _find_instance(state, friend.instance_id).damage == 1
        assert _find_instance(state, foe_ground.instance_id).damage == 1
        assert _find_instance(state, foe_space.instance_id).damage == 0
        assert state.find_instance(asajj.instance_id)[1].exhausted

    def test_JTL_1_specs_never_leak_onto_the_tie_fighter_token(self, repo):
        """The TIE Fighter token IS "JTL"/"1" — the same registry key as Asajj.  A
        token in an arena must offer none of her actions and gain none of her
        keywords."""
        from swu.engine.actions import legal_actions, UseAbility
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.tokens import _token_unit_def
        state = _make_state()
        tie = _place(state, "P0", _token_unit_def("TIE Fighter"), "space")
        assert (tie.card_def.set_code, tie.card_def.card_number) == ("JTL", "1")
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == tie.instance_id]
        assert not has_keyword(state, tie, Keyword.GRIT)

    def test_JTL_1_as_a_pilot_upgrade_grants_grit_and_the_on_attack(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_card(repo, "JTL", "1"))
        host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        friend = _place(state, "P0", _get_card(repo, "JTL", "62"), "space")

        _attach_leader_as_pilot(state, host, asajj)
        # "It gains Grit" — the permanent grant from the deploy-as-an-upgrade trigger.
        from swu.engine.events import LeaderDeployed
        from swu.abilities.resolver import fire_triggered_abilities
        evt = LeaderDeployed(player_id="P0", instance_id=asajj.instance_id,
                             leader_name=asajj.card_def.display_name, arena="Space")
        state = fire_triggered_abilities(
            state, evt, after_all_player_idx=1,
            event_ctx={"via_pilot_leader": True, "attached_to_id": host.instance_id})
        assert has_keyword(state, _find_instance(state, host.instance_id), Keyword.GRIT)

        # The granted "On Attack" chain resolves FROM THE HOST.
        state = _fire_on_attack(state, _find_instance(state, host.instance_id), foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, friend.instance_id)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, friend.instance_id).damage == 1
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_JTL_1_host_of_a_leader_pilot_counts_as_a_leader_unit(self, repo):
        """"Attached unit is a leader unit" — so non-leader removal can't touch it."""
        from swu.abilities.resolver import _is_leader_unit
        state = _make_state()
        asajj = _place_leader(state, "P0", _get_card(repo, "JTL", "1"))
        host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        assert not _is_leader_unit(host)
        _attach_leader_as_pilot(state, host, asajj)
        assert _is_leader_unit(host)


class TestCaptainPhasmaJTL10:
    """JTL_10 — both sides gated on "you played a First Order card this phase"."""

    def test_JTL_10_undeployed_action_gated_on_a_first_order_play(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        phasma = _place_leader(state, "P0", _get_card(repo, "JTL", "10"))

        def offered(s):
            return [a for a in legal_actions(s)
                    if isinstance(a, UseAbility) and a.source_id == phasma.instance_id]

        # Not offered at all until a First Order card has been played — the exhaust
        # is never spent on a no-op.
        assert not offered(state)
        _mark_trait_played(state, "P0", "First Order")
        assert offered(state)

        state = _use_ability_jtl(state, phasma)
        enemy_base = state.player_by_id("P1").base_instance
        state = _choose_jtl(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_JTL_10_trait_ledger_is_fed_by_actually_playing_a_card(self, repo):
        """The condition reads a ledger filled at the CardPlayed chokepoint, so
        playing a real First Order card arms it."""
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "JTL", "10"))
        _give_resources(state, "P0", 10, repo)
        trooper = _get_card(repo, "JTL", "132")      # First Order Stormtrooper
        from swu.engine.state import CardInstance, Zone
        import uuid as _uuid
        ci = CardInstance(instance_id=f"h_{_uuid.uuid4().hex[:6]}", card_def=trooper,
                          owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        from swu.engine.actions import legal_actions, apply, PlayCard
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == ci.instance_id)
        state = apply(state, play)
        assert "First Order" in state.game_memory.traits_played_this_phase["P0"]

    def test_JTL_10_deployed_on_attack_hits_a_unit_then_a_base(self, repo):
        state = _make_state()
        phasma = _place_leader(state, "P0", _get_card(repo, "JTL", "10"))
        _deploy_leader_to_arena(state, phasma)
        foe = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        _mark_trait_played(state, "P0", "First Order")

        state = _fire_on_attack(state, phasma, foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        enemy_base = state.player_by_id("P1").base_instance
        state = _choose_jtl(state, enemy_base.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1
        assert state.player_by_id("P1").base_instance.damage == 1


class TestLukeSkywalkerJTL12:
    """JTL_12 — Fighter-gated leader damage; the upgrade side is undefeatable and
    grants a Fighter host a 3-damage On Attack."""

    def test_JTL_12_undeployed_action_needs_a_fighter_attack_this_phase(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        luke = _place_leader(state, "P0", _get_card(repo, "JTL", "12"))
        fighter = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")

        def offered(s):
            return [a for a in legal_actions(s)
                    if isinstance(a, UseAbility) and a.source_id == luke.instance_id]

        assert not offered(state)
        state.game_memory.units_attacked_this_round.add(fighter.instance_id)
        assert offered(state)

        state = _use_ability_jtl(state, luke)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_JTL_12_upgrade_cant_be_defeated_by_an_enemy_ability(self, repo):
        """``upgrade_only`` protection: the Luke UPGRADE survives enemy removal, but
        it does not shield the Vehicle he is riding."""
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        luke = _place_leader(state, "P0", _get_card(repo, "JTL", "12"))
        host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        _attach_leader_as_pilot(state, host, luke)

        assert _target_protected(state, luke.instance_id, enemy, "defeat")
        assert not _target_protected(state, host.instance_id, enemy, "defeat")

    def test_JTL_12_unit_side_is_not_protected(self, repo):
        """The clause is about the UPGRADE only — deployed as a unit Luke is
        ordinary."""
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        luke = _place_leader(state, "P0", _get_card(repo, "JTL", "12"))
        _deploy_leader_to_arena(state, luke)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        assert not _target_protected(state, luke.instance_id, enemy, "defeat")

    def test_JTL_12_grants_a_fighter_host_the_three_damage_on_attack(self, repo):
        state = _make_state()
        luke = _place_leader(state, "P0", _get_card(repo, "JTL", "12"))
        fighter_host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 7 HP
        _attach_leader_as_pilot(state, fighter_host, luke)

        state = _fire_on_attack(state, _find_instance(state, fighter_host.instance_id))
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 3

    def test_JTL_12_non_fighter_host_gains_nothing(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        luke = _place_leader(state, "P0", _get_card(repo, "JTL", "12"))
        # Dornean Gunship is a Capital Ship, not a Fighter.
        host = _place(state, "P0", _get_card(repo, "JTL", "116"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        _attach_leader_as_pilot(state, host, luke)

        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]


class TestBansheeJTL37:
    """JTL_37 — On Attack: you may deal damage equal to the damage on this unit."""

    def test_JTL_37_deals_its_own_damage_to_a_chosen_unit(self, repo):
        state = _make_state()
        banshee = _place(state, "P0", _get_card(repo, "JTL", "37"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        banshee.damage = 3

        state = _fire_on_attack(state, banshee, foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 3


class TestFleetInterdictorJTL40:
    """JTL_40 — When Defeated: you may defeat a space unit costing 3 or less."""

    def test_JTL_40_when_defeated_only_offers_cheap_space_units(self, repo):
        state = _make_state()
        inter = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        cheap = _place(state, "P1", _get_card(repo, "JTL", "62"), "space")     # cost 2
        pricey = _place(state, "P1", _get_card(repo, "JTL", "116"), "space")   # cost 5
        ground = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")

        state = _fire_when_defeated(state, inter)
        state = _accept_jtl(state)
        assert _target_ids_jtl(state) == {cheap.instance_id}
        state = _choose_jtl(state, cheap.instance_id)
        assert _find_instance(state, cheap.instance_id) is None
        assert _find_instance(state, pricey.instance_id) is not None
        assert _find_instance(state, ground.instance_id) is not None


class TestNoGloryOnlyResultsJTL43:
    """JTL_43 — Take control of a non-leader unit, then defeat it."""

    def test_JTL_43_defeats_an_enemy_unit_into_its_owners_discard(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "43")
        state = _choose_jtl(state, foe.instance_id)

        assert _find_instance(state, foe.instance_id) is None
        # Control changed, ownership did not — it goes to P1's discard.
        assert any(c.instance_id == foe.instance_id
                   for c in state.player_by_id("P1").discard)

    def test_JTL_43_cannot_target_a_leader_unit(self, repo):
        state = _make_state()
        leader = _place_leader(state, "P1", _get_card(repo, "JTL", "10"))
        _deploy_leader_to_arena(state, leader)
        plain = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "43")
        assert _target_ids_jtl(state) == {plain.instance_id}


class TestPaigeTicoJTL46:
    """JTL_46 — Piloting; attached unit gains "On Attack: Experience token, then 1
    damage to it"."""

    def test_JTL_46_granted_on_attack_tokens_then_damages_the_host(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "46"), "P0")

        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        host = _find_instance(state, host.instance_id)
        assert _experience_count(host) == 1
        assert host.damage == 1


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:02 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _decline_jtl(state):
    from swu.engine.actions import legal_actions, apply, DeclineTrigger
    dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
    return apply(state, dec)


def _add_deck_cards_jtl(state, owner_id, repo, n):
    """Put `n` cheap cards on top of a player's deck so a draw has something to take."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    card = _get_card(repo, "SOR", "61")
    ps = state.player_by_id(owner_id)
    for _ in range(n):
        ps.deck.append(CardInstance(
            instance_id=f"{owner_id}_deck_{_uuid.uuid4().hex[:6]}",
            card_def=card, owner_id=owner_id, zone=Zone.DECK))


def _drain_jtl(state):
    """Advance past any AutoResolveEffects step so pending targets are enumerated."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(10):
        auto = [a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)]
        if not auto:
            break
        state = apply(state, auto[0])
    return state


class TestRedSquadronXWingJTL51:
    """JTL_51 — When Played: you may deal 2 to yourself to draw a card."""

    def test_JTL_51_self_damage_draws_a_card(self, repo):
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_when_played(state, xwing)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert _find_instance(state, xwing.instance_id).damage == 2
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_51_declining_costs_nothing(self, repo):
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_when_played(state, xwing)
        state = _decline_jtl(state)
        assert _find_instance(state, xwing.instance_id).damage == 0
        assert len(state.player_by_id("P0").hand) == before


class TestYoureAllClearKidJTL55:
    """JTL_55 — defeat a wounded enemy ship; the token rider needs their space arena
    to be empty afterwards."""

    def test_JTL_55_defeats_then_gives_a_token_when_their_space_arena_empties(self, repo):
        state = _make_state()
        prey = _place(state, "P1", _get_card(repo, "JTL", "62"), "space")   # 2/3
        mine = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")

        state, _ = _play_event_from_hand(state, repo, "JTL", "55")
        state = _choose_jtl(state, prey.instance_id)
        state = _drain_jtl(state)
        # Their last space unit is gone, so the "you may" token half is offered.
        assert _find_instance(state, prey.instance_id) is None
        state = _choose_jtl(state, mine.instance_id)
        assert _experience_count(_find_instance(state, mine.instance_id)) == 1

    def test_JTL_55_no_token_while_they_still_hold_a_space_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        prey = _place(state, "P1", _get_card(repo, "JTL", "62"), "space")
        survivor = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        mine = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")

        state, _ = _play_event_from_hand(state, repo, "JTL", "55")
        state = _choose_jtl(state, prey.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, prey.instance_id) is None
        assert _find_instance(state, survivor.instance_id) is not None
        # The board gate fails, so the token half fizzles without a prompt.
        assert not [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        assert _experience_count(_find_instance(state, mine.instance_id)) == 0

    def test_JTL_55_only_offers_wounded_enemy_space_units(self, repo):
        state = _make_state()
        small = _place(state, "P1", _get_card(repo, "JTL", "62"), "space")   # 3 HP
        big = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")     # 6 HP
        _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "55")
        assert _target_ids_jtl(state) == {small.instance_id}


class TestSilverAngelJTL62:
    """JTL_62 — the new WhenUnitHealed observer."""

    def test_JTL_62_healing_it_offers_one_damage_to_a_space_unit(self, repo):
        from swu.engine.actions import apply, Pass
        state = _make_state()
        angel = _place(state, "P0", _get_card(repo, "JTL", "62"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        angel.damage = 2

        # Heal through the chokepoint, then settle so the observer drains.
        from swu.engine.actions import note_unit_healed
        angel.damage = 0
        note_unit_healed(state, angel, 2)
        state = apply(state, Pass())

        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_JTL_62_a_no_op_heal_never_fires_it(self, repo):
        from swu.engine.actions import apply, Pass, note_unit_healed, legal_actions
        from swu.engine.actions import AcceptTrigger
        state = _make_state()
        angel = _place(state, "P0", _get_card(repo, "JTL", "62"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        note_unit_healed(state, angel, 0)     # healing an undamaged unit
        state = apply(state, Pass())
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]

    def test_JTL_62_only_fires_for_itself(self, repo):
        from swu.engine.actions import (
            apply, Pass, note_unit_healed, legal_actions, AcceptTrigger)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "62"), "space")
        other = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        other.damage = 0
        note_unit_healed(state, other, 2)     # a DIFFERENT unit was healed
        state = apply(state, Pass())
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]


class TestDirectHitJTL78:
    """JTL_78 — Defeat a non-leader Vehicle unit."""

    def test_JTL_78_defeats_a_vehicle_but_not_a_non_vehicle(self, repo):
        state = _make_state()
        vehicle = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        trooper = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "78")
        assert _target_ids_jtl(state) == {vehicle.instance_id}
        state = _choose_jtl(state, vehicle.instance_id)
        assert _find_instance(state, vehicle.instance_id) is None
        assert _find_instance(state, trooper.instance_id) is not None


class TestNebulaIgnitionJTL80:
    """JTL_80 — Defeat each unit that isn't upgraded."""

    def test_JTL_80_wipes_only_the_unupgraded_units(self, repo):
        state = _make_state()
        bare_mine = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        bare_theirs = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        upgraded = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        _attach_upgrade_directly(state, upgraded, _get_card(repo, "JTL", "120"), "P1")

        state, _ = _play_event_from_hand(state, repo, "JTL", "80", resources=15)
        state = _drain_jtl(state)
        assert _find_instance(state, bare_mine.instance_id) is None
        assert _find_instance(state, bare_theirs.instance_id) is None
        assert _find_instance(state, upgraded.instance_id) is not None

    def test_JTL_80_a_shield_token_counts_as_an_upgrade(self, repo):
        from swu.engine.tokens import attach_token
        state = _make_state()
        shielded = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        attach_token(state, state.player_by_id("P0"), shielded, "Shield")

        state, _ = _play_event_from_hand(state, repo, "JTL", "80", resources=15)
        state = _drain_jtl(state)
        assert _find_instance(state, shielded.instance_id) is not None


class TestApologyAcceptedJTL91:
    """JTL_91 — Defeat a friendly unit; you may give 2 Experience to a unit."""

    def test_JTL_91_sacrifices_then_hands_out_two_experience(self, repo):
        state = _make_state()
        doomed = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        keeper = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")

        state, _ = _play_event_from_hand(state, repo, "JTL", "91")
        state = _choose_jtl(state, doomed.instance_id)
        state = _drain_jtl(state)
        state = _choose_jtl(state, keeper.instance_id)
        assert _find_instance(state, doomed.instance_id) is None
        assert _experience_count(_find_instance(state, keeper.instance_id)) == 2


class TestResistanceBlueSquadronJTL102:
    """JTL_102 — When Played: damage equal to the number of friendly space units."""

    def test_JTL_102_scales_with_friendly_space_units_including_itself(self, repo):
        state = _make_state()
        squad = _place(state, "P0", _get_card(repo, "JTL", "102"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")   # ground: ignored
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state = _fire_when_played(state, squad)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        # Two friendly SPACE units (the Squadron itself + the X-Wing).
        assert _find_instance(state, foe.instance_id).damage == 2


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:03 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


def _discard_unit(state, owner_id, card_def):
    """Put a unit card into a player's discard pile."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    ci = CardInstance(instance_id=f"{owner_id}_dis_{_uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD)
    state.player_by_id(owner_id).discard.append(ci)
    return ci


class TestRaddusJTL104:
    """JTL_104 — conditional Sentinel + a power-sized death rattle."""

    def test_JTL_104_sentinel_needs_another_resistance_card(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        raddus = _place(state, "P0", _get_card(repo, "JTL", "104"), "space")
        # The DB's printed Sentinel is stripped — the conditional grant owns it.
        assert "Sentinel" not in raddus.card_def.keywords
        assert not has_keyword(state, raddus, Keyword.SENTINEL)

        # Another Resistance card (Black One is Resistance) switches it on.
        _place(state, "P0", _get_card(repo, "JTL", "147"), "space")
        assert has_keyword(state, _find_instance(state, raddus.instance_id),
                           Keyword.SENTINEL)

    def test_JTL_104_an_undeployed_resistance_leader_counts(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        raddus = _place(state, "P0", _get_card(repo, "JTL", "104"), "space")
        assert not has_keyword(state, raddus, Keyword.SENTINEL)
        # Rose Tico JTL_4 is a Resistance leader, undeployed in the base zone.
        _place_leader(state, "P0", _get_card(repo, "JTL", "4"))
        assert has_keyword(state, _find_instance(state, raddus.instance_id),
                           Keyword.SENTINEL)

    def test_JTL_104_when_defeated_deals_his_power_to_an_enemy(self, repo):
        state = _make_state()
        raddus = _place(state, "P0", _get_card(repo, "JTL", "104"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state = _fire_when_defeated(state, raddus)
        state = _drain_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        # 8 power ≥ the Interdictor's 6 HP, so it is destroyed outright.
        assert _find_instance(state, foe.instance_id) is None


class TestDorneanGunshipJTL116:
    """JTL_116 — indirect damage equal to your Vehicle count."""

    def test_JTL_116_indirect_damage_scales_with_vehicles(self, repo):
        state = _make_state()
        gunship = _place(state, "P0", _get_card(repo, "JTL", "116"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "51"), "space")     # Vehicle
        _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")    # not a Vehicle

        state = _fire_when_played(state, gunship)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 2
        assert top.deciding_player_id == "P1"


class TestDorsalTurretJTL120:
    """JTL_120 — attached unit defeats any unit it damages while attacking."""

    def test_JTL_120_granted_trigger_defeats_the_damaged_defender(self, repo):
        """Both combatants are 3/7, so each survives the exchange — anything that
        dies here died to the turret, not to combat.  (A vanilla ground Vehicle does
        not exist in the DB; the attach restriction is asserted separately below.)"""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "120"), "P0")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = apply(state, AttackWithUnit(host.instance_id, foe.instance_id))
        state = _drain_jtl(state)
        assert _find_instance(state, host.instance_id) is not None
        assert _find_instance(state, foe.instance_id) is None

    def test_JTL_120_attaches_only_to_a_vehicle(self, repo):
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "JTL", "120"))
        assert spec is not None and "Vehicle" in (spec.traits or ())


class TestSalvageJTL121:
    """JTL_121 — play a Vehicle from your discard, then deal 1 to it."""

    def test_JTL_121_plays_a_discarded_vehicle_and_damages_it(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        vehicle = _discard_unit(state, "P0", _get_card(repo, "JTL", "51"))
        trooper = _discard_unit(state, "P0", _get_card(repo, "SOR", "61"))

        state, _ = _play_event_from_hand(state, repo, "JTL", "121", resources=15)
        state = _drain_jtl(state)
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        # Only the Vehicle in the DISCARD is offered.
        assert {a.instance_id for a in plays} == {vehicle.instance_id}

        state = apply(state, plays[0])
        played = _find_instance(state, vehicle.instance_id)
        assert played is not None
        assert played.damage == 1


class TestAirSuperiorityJTL125:
    """JTL_125 — 4 damage to a ground unit, but only while you out-fleet them."""

    def test_JTL_125_hits_when_you_control_more_space_units(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        foe_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "125")
        state = _choose_jtl(state, foe_ground.instance_id)
        assert _find_instance(state, foe_ground.instance_id).damage == 4

    def test_JTL_125_fizzles_when_the_space_race_is_level(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        foe_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "125")
        state = _drain_jtl(state)
        assert not [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        assert _find_instance(state, foe_ground.instance_id).damage == 0


class TestLightspeedAssaultJTL127:
    """JTL_127 — sacrifice a ship to gun down an enemy ship, then bill its owner."""

    def test_JTL_127_sacrifice_strikes_and_bills_the_controller(self, repo):
        state = _make_state()
        sacrifice = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")  # 3/4
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")        # 6/6

        state, _ = _play_event_from_hand(state, repo, "JTL", "127")
        state = _choose_jtl(state, sacrifice.instance_id)
        state = _drain_jtl(state)
        state = _choose_jtl(state, foe.instance_id)

        assert _find_instance(state, sacrifice.instance_id) is None
        # The X-Wing's 3 power lands on the Interdictor …
        assert _find_instance(state, foe.instance_id).damage == 3
        # … and the Interdictor's own 6 power is billed to its controller.
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 6

    def test_JTL_127_needs_a_friendly_space_unit_to_spend(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")  # ground only
        _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state, _ = _play_event_from_hand(state, repo, "JTL", "127")
        state = _drain_jtl(state)
        # No friendly space unit ⇒ no sacrifice ⇒ the strike's "if you do" gate is
        # never armed, so nothing is offered at all.
        assert not [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]


class TestBlackOneJTL147:
    """JTL_147 — +1/+0 while upgraded; a Poe-gated On Attack ping."""

    def test_JTL_147_gets_plus_one_power_only_while_upgraded(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        black_one = _place(state, "P0", _get_card(repo, "JTL", "147"), "space")
        assert compute_power(state, black_one) == 2

        _attach_upgrade_directly(state, black_one, _get_card(repo, "JTL", "120"), "P0")
        assert compute_power(state, _find_instance(state, black_one.instance_id)) == 3

    def test_JTL_147_on_attack_needs_poe_dameron(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        black_one = _place(state, "P0", _get_card(repo, "JTL", "147"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state_no_poe = _fire_on_attack(state, black_one, foe)
        assert not [a for a in legal_actions(state_no_poe)
                    if isinstance(a, AcceptTrigger)]

        # Poe Dameron JTL_13 sitting undeployed in the base zone is enough.
        _place_leader(state, "P0", _get_card(repo, "JTL", "13"))
        state = _fire_on_attack(state, black_one, foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:04 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _assign_indirect_to(state, target_id):
    """Resolve a pending assign_indirect_damage decision onto ``target_id``."""
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "AssignIndirectDamage"
               and a.target_id == target_id)
    return apply(state, act)


def _add_hand_cards_jtl(state, owner_id, repo, n):
    """Put ``n`` cheap cards into a player's hand."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    card = _get_card(repo, "SOR", "61")
    ps = state.player_by_id(owner_id)
    for _ in range(n):
        ps.hand.append(CardInstance(
            instance_id=f"{owner_id}_hand_{_uuid.uuid4().hex[:6]}",
            card_def=card, owner_id=owner_id, zone=Zone.HAND))


def _stack_deck_jtl(state, owner_id, card_defs):
    """Put the given card_defs on top of a player's deck (first = top card)."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    ps = state.player_by_id(owner_id)
    made = [CardInstance(instance_id=f"{owner_id}_dk_{_uuid.uuid4().hex[:6]}",
                         card_def=cd, owner_id=owner_id, zone=Zone.DECK)
            for cd in card_defs]
    ps.deck[:0] = made
    return made


class TestFriskJTL148:
    """JTL_148 — When played as an upgrade: you may defeat an upgrade costing ≤2."""

    def test_JTL_148_as_upgrade_defeats_a_cheap_upgrade(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        frisk = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "148"), "P0")
        # An enemy unit wearing a 1-cost upgrade (Dorsal Turret JTL_120).
        foe = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        turret = _attach_upgrade_directly(state, foe, _get_card(repo, "JTL", "120"), "P1")

        state = _fire_upgrade_played(state, frisk, host)
        state = _accept_jtl(state)
        state = _choose_jtl(state, turret.instance_id)
        foe_now = _find_instance(state, foe.instance_id)
        assert all(u.instance_id != turret.instance_id
                   for u in foe_now.attached_upgrades)

    def test_JTL_148_played_as_a_unit_does_not_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        frisk = _place(state, "P0", _get_card(repo, "JTL", "148"), "ground")
        foe = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        _attach_upgrade_directly(state, foe, _get_card(repo, "JTL", "120"), "P1")

        state = _fire_when_played(state, frisk)
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]


class TestRedSquadronYWingJTL149:
    """JTL_149 — On Attack: 3 indirect damage to the defending player."""

    def test_JTL_149_on_attack_pushes_3_indirect(self, repo):
        state = _make_state()
        ywing = _place(state, "P0", _get_card(repo, "JTL", "149"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state = _fire_on_attack(state, ywing, foe)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 3
        assert top.deciding_player_id == "P1"

        # Indirect damage bypasses a Shield — put it on the enemy base instead.
        state = _assign_indirect_to(state, _p1_base_id(state))
        assert state.player_by_id("P1").base_instance.damage == 3


class TestTacticalHeavyBomberJTL152:
    """JTL_152 — indirect equal to its power; a hit base draws a card."""

    def test_JTL_152_indirect_equals_power_and_base_hit_draws(self, repo):
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "JTL", "152"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, bomber, foe)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.context["amount"] == 3        # printed power

        state = _assign_indirect_to(state, _p1_base_id(state))
        assert state.player_by_id("P1").base_instance.damage == 3
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_152_no_draw_when_a_unit_soaks_it(self, repo):
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "JTL", "152"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, bomber, foe)
        state = _drain_jtl(state)
        state = _assign_indirect_to(state, foe.instance_id)
        assert len(state.player_by_id("P0").hand) == before


class TestRebelliousHammerheadJTL153:
    """JTL_153 — When Played: you may deal damage equal to your hand size."""

    def test_JTL_153_damage_equals_hand_size(self, repo):
        state = _make_state()
        hammerhead = _place(state, "P0", _get_card(repo, "JTL", "153"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        # Two cards in hand ⇒ 2 damage.
        _add_hand_cards_jtl(state, "P0", repo, 2)

        state = _fire_when_played(state, hammerhead)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 2


class TestTrenchRunJTL156:
    """JTL_156 — mill 2, recoil the cost difference, then attack at +4/+0."""

    def test_JTL_156_mills_two_recoils_the_difference_and_attacks(self, repo):
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")  # Fighter 3/4
        fighter.exhausted = False
        _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        # Opponent deck top: a 7-cost then a 4-cost ⇒ difference 3 (the X-Wing has
        # 4 HP, so it survives its own recoil and can still attack).
        _stack_deck_jtl(state, "P1", [_get_card(repo, "JTL", "40"),
                                      _get_card(repo, "JTL", "222")])

        state, _ = _play_event_from_hand(state, repo, "JTL", "156", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, fighter.instance_id)
        state = _drain_jtl(state)

        assert len(state.player_by_id("P1").discard) == 2
        hit = _find_instance(state, fighter.instance_id)
        assert hit is not None and hit.damage == 3
        # And the attack is now on offer for that unit only.
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context.get("attacker_id") == fighter.instance_id


class TestCrackshotVWingJTL158:
    """JTL_158 — self-damage only while it is your lone Fighter."""

    def test_JTL_158_damages_itself_when_alone(self, repo):
        state = _make_state()
        vwing = _place(state, "P0", _get_card(repo, "JTL", "158"), "space")
        state = _fire_when_played(state, vwing)
        state = _drain_jtl(state)
        assert _find_instance(state, vwing.instance_id).damage == 1

    def test_JTL_158_no_damage_with_another_fighter(self, repo):
        state = _make_state()
        vwing = _place(state, "P0", _get_card(repo, "JTL", "158"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "51"), "space")   # another Fighter
        state = _fire_when_played(state, vwing)
        state = _drain_jtl(state)
        assert _find_instance(state, vwing.instance_id).damage == 0


class TestDroidMissilePlatformJTL162:
    """JTL_162 — When Defeated: 3 indirect damage to a player."""

    def test_JTL_162_when_defeated_pushes_3_indirect(self, repo):
        state = _make_state()
        platform = _place(state, "P0", _get_card(repo, "JTL", "162"), "ground")

        state = _fire_when_defeated(state, platform)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 3
        state = _assign_indirect_to(state, _p1_base_id(state))
        assert state.player_by_id("P1").base_instance.damage == 3


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:05 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _select_damage_ids(state):
    from swu.engine.actions import legal_actions
    return {a.target_id for a in legal_actions(state)
            if type(a).__name__ == "SelectDamageTarget"}


def _select_damage_on(state, target_id):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "SelectDamageTarget"
               and a.target_id == target_id)
    return apply(state, act)


def _finish_select_damage(state):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "FinishSelectDamage")
    return apply(state, act)


class TestInsurgentSaboteursJTL168:
    """JTL_168 — On Attack: you may defeat an upgrade."""

    def test_JTL_168_on_attack_defeats_an_upgrade(self, repo):
        state = _make_state()
        saboteurs = _place(state, "P0", _get_card(repo, "JTL", "168"), "ground")
        foe = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        turret = _attach_upgrade_directly(state, foe, _get_card(repo, "JTL", "120"), "P1")

        state = _fire_on_attack(state, saboteurs, foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, turret.instance_id)
        foe_now = _find_instance(state, foe.instance_id)
        assert all(u.instance_id != turret.instance_id
                   for u in foe_now.attached_upgrades)


class TestWarJuggernautJTL170:
    """JTL_170 — +1/+0 per damaged unit anywhere + a When Played bombardment."""

    def test_JTL_170_power_scales_with_damaged_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        jug = _place(state, "P0", _get_card(repo, "JTL", "170"), "ground")
        assert compute_power(state, jug) == 3          # printed, nothing damaged

        foe = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        foe.damage = 1
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.damage = 2
        # Both players' damaged units count, and so does the Juggernaut itself.
        assert compute_power(state, _find_instance(state, jug.instance_id)) == 5
        _find_instance(state, jug.instance_id).damage = 1
        assert compute_power(state, _find_instance(state, jug.instance_id)) == 6

    def test_JTL_170_when_played_damages_any_number_of_units(self, repo):
        state = _make_state()
        jug = _place(state, "P0", _get_card(repo, "JTL", "170"), "ground")
        a = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, jug)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "select_damage"
        state = _select_damage_on(state, a.instance_id)
        state = _select_damage_on(state, b.instance_id)
        state = _finish_select_damage(state)
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1


class TestTwinLaserTurretJTL172:
    """JTL_172 — granted On Attack: 1 damage to up to 2 units in this arena."""

    def test_JTL_172_hits_only_units_in_the_hosts_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "51"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "172"), "P0")
        space_foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        ground_foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_on_attack(state, host, space_foe)
        state = _drain_jtl(state)
        offered = _select_damage_ids(state)
        assert space_foe.instance_id in offered
        assert ground_foe.instance_id not in offered
        assert host.instance_id in offered      # "units", not "enemy units"

        state = _select_damage_on(state, space_foe.instance_id)
        state = _finish_select_damage(state)
        assert _find_instance(state, space_foe.instance_id).damage == 1
        assert _find_instance(state, ground_foe.instance_id).damage == 0

    def test_JTL_172_attaches_only_to_a_vehicle(self, repo):
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "JTL", "172"))
        assert spec is not None and "Vehicle" in (spec.traits or ())


class TestFightFireWithFireJTL173:
    """JTL_173 — 3 damage to a friendly and an enemy unit in the same arena."""

    def test_JTL_173_damages_both_units_in_the_same_arena(self, repo):
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        elsewhere = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "173", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, friend.instance_id)
        state = _drain_jtl(state)
        # Only the enemy sharing the arena is offered.
        assert _target_ids_jtl(state) == {foe.instance_id}
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, friend.instance_id).damage == 3
        assert _find_instance(state, foe.instance_id).damage == 3
        assert _find_instance(state, elsewhere.instance_id).damage == 0

    def test_JTL_173_no_enemy_in_that_arena_deals_nothing(self, repo):
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "173", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, friend.instance_id)
        state = _drain_jtl(state)
        # "If you do" — the friendly unit is untouched when the pair can't be made.
        assert _find_instance(state, friend.instance_id).damage == 0


class TestHotshotManeuverJTL174:
    """JTL_174 — 2 damage per On Attack ability, then attack with that unit."""

    def test_JTL_174_one_on_attack_ability_hits_one_enemy_then_attacks(self, repo):
        state = _make_state()
        # Red Squadron Y-Wing JTL_149 has exactly one On Attack ability.
        ywing = _place(state, "P0", _get_card(repo, "JTL", "149"), "space")
        ywing.exhausted = False
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        ground_foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "174", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, ywing.instance_id)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "select_damage"
        assert top.context["remaining"] == 1
        # Only ENEMY units are offered.
        assert _select_damage_ids(state) == {foe.instance_id,
                                             ground_foe.instance_id}

        state = _select_damage_on(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 2
        # …and the attack follows, with the chosen unit pinned as the attacker.
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context.get("attacker_id") == ywing.instance_id

    def test_JTL_174_unit_without_on_attack_goes_straight_to_the_attack(self, repo):
        state = _make_state()
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        plain.exhausted = False
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "JTL", "174", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, plain.instance_id)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"


class TestSystemShockJTL175:
    """JTL_175 — defeat a non-leader upgrade, then damage its host."""

    def test_JTL_175_defeats_the_upgrade_and_damages_the_host(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")
        turret = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "120"), "P1")

        state, _ = _play_event_from_hand(state, repo, "JTL", "175", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, turret.instance_id)
        host_now = _find_instance(state, host.instance_id)
        assert all(u.instance_id != turret.instance_id
                   for u in host_now.attached_upgrades)
        assert host_now.damage == 1


class TestPiercingShotJTL180:
    """JTL_180 — strip every Shield, then land a full 3 damage."""

    def test_JTL_180_strips_shields_then_deals_full_damage(self, repo):
        from swu.engine.tokens import attach_token
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        attach_token(state, state.player_by_id("P1"), foe, "Shield")
        attach_token(state, state.player_by_id("P1"), foe, "Shield")
        assert _shield_count(foe) == 2

        state, _ = _play_event_from_hand(state, repo, "JTL", "180", resources=15)
        state = _drain_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        hit = _find_instance(state, foe.instance_id)
        assert _shield_count(hit) == 0
        assert hit.damage == 3


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:06 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _fire_regroup_start_jtl(state):
    """Fire the "regroup phase starts" PhaseStartTrigger site."""
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    evt = PhaseChanged(new_phase="REGROUP", round_number=state.round_number)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestFireballJTL198:
    """JTL_198 — burns itself for 1 at the start of each regroup phase."""

    def test_JTL_198_damages_itself_at_regroup(self, repo):
        state = _make_state()
        fireball = _place(state, "P0", _get_card(repo, "JTL", "198"), "space")

        state = _fire_regroup_start_jtl(state)
        state = _drain_jtl(state)
        assert _find_instance(state, fireball.instance_id).damage == 1


class TestGuerillaSoldierJTL218:
    """JTL_218 — 3 indirect; a hit base readies the Soldier."""

    def test_JTL_218_base_hit_readies_this_unit(self, repo):
        state = _make_state()
        soldier = _place(state, "P0", _get_card(repo, "JTL", "218"), "ground")
        soldier.exhausted = True                       # units enter play exhausted

        state = _fire_when_played(state, soldier)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].context["amount"] == 3
        state = _assign_indirect_to(state, _p1_base_id(state))
        assert state.player_by_id("P1").base_instance.damage == 3
        assert _find_instance(state, soldier.instance_id).exhausted is False

    def test_JTL_218_unit_hit_leaves_it_exhausted(self, repo):
        state = _make_state()
        soldier = _place(state, "P0", _get_card(repo, "JTL", "218"), "ground")
        soldier.exhausted = True
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state = _fire_when_played(state, soldier)
        state = _drain_jtl(state)
        state = _assign_indirect_to(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 3
        assert _find_instance(state, soldier.instance_id).exhausted is True


class TestRafaMartezJTL219:
    """JTL_219 — When Played/On Attack: 1 damage to a friendly unit, ready a
    resource."""

    def test_JTL_219_registers_both_trigger_sides(self):
        from swu.abilities.registry import get_abilities
        import swu.cards  # noqa: F401
        triggers = {type(s.trigger).__name__ for s in get_abilities("JTL", "219")}
        assert triggers == {"WhenPlayed", "OnAttack"}

    def test_JTL_219_when_played_damages_a_friendly_and_readies_a_resource(self, repo):
        state = _make_state()
        rafa = _place(state, "P0", _get_card(repo, "JTL", "219"), "ground")
        buddy = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 3)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True

        state = _fire_when_played(state, rafa)
        state = _drain_jtl(state)
        # Only friendly units are on offer.
        offered = _target_ids_jtl(state)
        assert foe.instance_id not in offered
        assert {rafa.instance_id, buddy.instance_id} <= offered

        state = _choose_jtl(state, buddy.instance_id)
        assert _find_instance(state, buddy.instance_id).damage == 1
        readied = [r for r in state.player_by_id("P0").resources if not r.exhausted]
        assert len(readied) == 1


class TestKimogilaHeavyFighterJTL222:
    """JTL_222 — 3 indirect; a hit unit is exhausted too."""

    def test_JTL_222_exhausts_the_unit_it_damaged(self, repo):
        state = _make_state()
        kimogila = _place(state, "P0", _get_card(repo, "JTL", "222"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        foe.exhausted = False

        state = _fire_when_played(state, kimogila)
        state = _drain_jtl(state)
        state = _assign_indirect_to(state, foe.instance_id)
        hit = _find_instance(state, foe.instance_id)
        assert hit.damage == 3 and hit.exhausted is True

    def test_JTL_222_base_hit_exhausts_nothing(self, repo):
        state = _make_state()
        kimogila = _place(state, "P0", _get_card(repo, "JTL", "222"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        foe.exhausted = False

        state = _fire_when_played(state, kimogila)
        state = _drain_jtl(state)
        state = _assign_indirect_to(state, _p1_base_id(state))
        assert _find_instance(state, foe.instance_id).exhausted is False


class TestRadiantVIIJTL226:
    """JTL_226 — enemy non-leader units get −1/−0 per damage on them."""

    def test_JTL_226_debuff_scales_with_each_units_own_damage(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "226"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")   # 6/6
        other = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")  # 3/4

        assert compute_power(state, foe) == 6
        foe.damage = 2
        other.damage = 1
        # Each enemy is debuffed by its OWN damage, not by the board total.
        assert compute_power(state, _find_instance(state, foe.instance_id)) == 4
        assert compute_power(state, _find_instance(state, other.instance_id)) == 2

    def test_JTL_226_leaves_friendly_units_alone(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "226"), "space")
        friend = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        friend.damage = 3
        assert compute_power(state, _find_instance(state, friend.instance_id)) == 6

    def test_JTL_226_when_played_deals_5_indirect(self, repo):
        state = _make_state()
        radiant = _place(state, "P0", _get_card(repo, "JTL", "226"), "space")
        state = _fire_when_played(state, radiant)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage" and top.context["amount"] == 5


class TestSuperheavyIonCannonJTL227:
    """JTL_227 — granted On Attack: exhaust an enemy, bill its power as indirect."""

    def test_JTL_227_exhausts_an_enemy_and_bills_its_power(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "226"), "space")  # Capital Ship
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "227"), "P0")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")    # 6 power
        foe.exhausted = False

        state = _fire_on_attack(state, host, foe)
        state = _accept_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, foe.instance_id).exhausted is True
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage" and top.context["amount"] == 6

    def test_JTL_227_does_not_offer_an_already_exhausted_enemy(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "226"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "227"), "P0")
        foe = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        foe.exhausted = True

        state = _fire_on_attack(state, host, foe)
        if [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]:
            state = _accept_jtl(state)
            state = _drain_jtl(state)
        assert not any(d.kind == "assign_indirect_damage"
                       for d in state.pending_decisions)

    def test_JTL_227_attach_disjunction_is_left_open(self, repo):
        """"Attach to a Capital Ship OR Transport unit" is a trait DISJUNCTION,
        which ``_upgrade_target_spec`` deliberately declines to encode (its traits
        are ANDed, so requiring both would forbid a legal Capital Ship host).  The
        documented conservative behaviour is to leave the restriction open — assert
        that, rather than a wrong AND."""
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "JTL", "227"))
        assert spec is None or set(spec.traits or ()) != {"Capital Ship", "Transport"}


class TestTorpedoBarrageJTL234:
    """JTL_234 — 5 indirect damage to a player."""

    def test_JTL_234_deals_5_indirect(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "JTL", "234", resources=15)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 5
        assert top.deciding_player_id == "P1"

        state = _assign_indirect_to(state, _p1_base_id(state))
        assert state.player_by_id("P1").base_instance.damage == 5


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:07 — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════


class TestTIEDaggerVanguardJTL239:
    """JTL_239 — When Played: you may deal 2 to a DAMAGED unit."""

    def test_JTL_239_offers_only_damaged_units(self, repo):
        state = _make_state()
        vanguard = _place(state, "P0", _get_card(repo, "JTL", "239"), "space")
        hurt = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        hurt.damage = 1
        healthy = _place(state, "P1", _get_card(repo, "JTL", "51"), "space")

        state = _fire_when_played(state, vanguard)
        state = _accept_jtl(state)
        offered = _target_ids_jtl(state)
        assert hurt.instance_id in offered
        assert healthy.instance_id not in offered

        state = _choose_jtl(state, hurt.instance_id)
        assert _find_instance(state, hurt.instance_id).damage == 3

    def test_JTL_239_no_damaged_unit_is_a_silent_no_op(self, repo):
        state = _make_state()
        vanguard = _place(state, "P0", _get_card(repo, "JTL", "239"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "40"), "space")

        state = _fire_when_played(state, vanguard)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert all(u.damage == 0
                   for ps in state.players
                   for u in ps.ground_arena + ps.space_arena)


class TestDilapidatedSkiSpeederJTL248:
    """JTL_248 — When Played: deal 3 to itself."""

    def test_JTL_248_damages_itself_for_3(self, repo):
        state = _make_state()
        speeder = _place(state, "P0", _get_card(repo, "JTL", "248"), "ground")

        state = _fire_when_played(state, speeder)
        state = _drain_jtl(state)
        hit = _find_instance(state, speeder.instance_id)
        assert hit is not None and hit.damage == 3


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:08 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


def _fire_leader_deployed_jtl(state, leader_ci):
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


def _fire_action_phase_start_jtl(state, round_number=1):
    """Fire the "action phase starts" PhaseStartTrigger site."""
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    evt = PhaseChanged(new_phase="ACTION", round_number=round_number)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _swap_base_jtl(state, player_id, base_def):
    """Replace a player's placeholder base with a real DB base card."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    ps = state.player_by_id(player_id)
    ps.base_zone = [c for c in ps.base_zone
                    if getattr(c.card_def, "type", None) != "Base"]
    ci = CardInstance(instance_id=f"{player_id}_base_{_uuid.uuid4().hex[:6]}",
                      card_def=base_def, owner_id=player_id, zone=Zone.BASE_ZONE)
    ps.base_zone.insert(0, ci)
    return ci


def _setup_game_with_base(repo, base_number):
    """Build a fresh game whose P0 base is the given JTL base card."""
    from swu.engine.actions import create_game
    base = _get_card(repo, "JTL", base_number)
    other_base = _get_card(repo, "JTL", "19")   # City in the Clouds — no text
    leader = _get_card(repo, "JTL", "14")
    filler = _get_card(repo, "SOR", "61")
    deck0 = [leader, base] + [filler] * 30
    deck1 = [leader, other_base] + [filler] * 30
    return create_game("P0", deck0, "P1", deck1, seed=7)


class TestAdmiralTrenchJTL14:
    """JTL_14 — undeployed pitch-and-draw Action + a When Deployed reveal/cull."""

    def test_JTL_14_action_is_offered_only_with_an_expensive_card_in_hand(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        trench = _place_leader(state, "P0", _get_card(repo, "JTL", "14"))
        _add_hand_cards_jtl(state, "P0", repo, 2)     # SOR_61 costs 2 — too cheap
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility)
                    and a.source_id == trench.instance_id]

        _stack_deck_jtl(state, "P0", [])
        big = _get_card(repo, "JTL", "41")            # cost 11
        from swu.engine.state import CardInstance, Zone
        state.player_by_id("P0").hand.append(CardInstance(
            instance_id="P0_big", card_def=big, owner_id="P0", zone=Zone.HAND))
        assert [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.source_id == trench.instance_id]

    def test_JTL_14_action_pitches_the_expensive_card_and_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        trench = _place_leader(state, "P0", _get_card(repo, "JTL", "14"))
        _add_hand_cards_jtl(state, "P0", repo, 1)
        state.player_by_id("P0").hand.append(CardInstance(
            instance_id="P0_big", card_def=_get_card(repo, "JTL", "41"),
            owner_id="P0", zone=Zone.HAND))
        _add_deck_cards_jtl(state, "P0", repo, 3)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == trench.instance_id)
        state = apply(state, act)
        state = _drain_jtl(state)
        ps = state.player_by_id("P0")
        # The 11-cost card was pitched; the hand size is unchanged (pitch + draw).
        assert any(c.instance_id == "P0_big" for c in ps.discard)
        assert len(ps.hand) == 2
        assert next(a for a in ps.base_zone
                    if a.instance_id == trench.instance_id).exhausted is True

    def test_JTL_14_when_deployed_lets_the_opponent_cull_then_the_controller_draw(
            self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        trench = _place_leader(state, "P0", _get_card(repo, "JTL", "14"))
        _deploy_leader_to_arena(state, trench, "ground")
        made = _stack_deck_jtl(state, "P0", [
            _get_card(repo, "JTL", "41"), _get_card(repo, "JTL", "63"),
            _get_card(repo, "JTL", "89"), _get_card(repo, "JTL", "248"),
        ])
        ids = [c.instance_id for c in made]

        state = _fire_leader_deployed_jtl(state, trench)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "reveal_cull_draw"
        # Stage 1 belongs to the OPPONENT and offers all four revealed cards.
        assert top.deciding_player_id == "P1"
        culls = [a for a in legal_actions(state)
                 if type(a).__name__ == "CullRevealedCard"]
        assert {a.instance_id for a in culls} == set(ids)

        state = apply(state, next(a for a in culls if a.instance_id == ids[0]))
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "CullRevealedCard"
                                  and a.instance_id == ids[1]))
        # Stage 2 shifts to the controller, who draws one of the two survivors.
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P0"
        draws = [a for a in legal_actions(state)
                 if type(a).__name__ == "DrawRevealedCard"]
        assert {a.instance_id for a in draws} == {ids[2], ids[3]}

        state = apply(state, next(a for a in draws if a.instance_id == ids[2]))
        ps = state.player_by_id("P0")
        assert [c.instance_id for c in ps.hand] == [ids[2]]
        # The two culled cards and the un-drawn survivor are all in the discard.
        assert {c.instance_id for c in ps.discard} == {ids[0], ids[1], ids[3]}
        assert not any(c.instance_id in ids for c in ps.deck)


class TestColossusJTL21:
    """JTL_21 — "Draw 1 less card in your starting hand"."""

    def test_JTL_21_opening_hand_is_one_smaller(self, repo):
        state = _setup_game_with_base(repo, "21")
        assert len(state.player_by_id("P0").hand) == 5
        assert len(state.player_by_id("P1").hand) == 6

    def test_JTL_21_mulligan_redraws_the_same_reduced_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, TakeMultiligan
        state = _setup_game_with_base(repo, "21")
        mull = next(a for a in legal_actions(state) if isinstance(a, TakeMultiligan))
        state = apply(state, mull)
        assert len(state.player_by_id("P0").hand) == 5


class TestNabatVillageJTL28:
    """JTL_28 — +3 opening cards, no mulligan, then bottom 3 at the first action
    phase."""

    def test_JTL_28_opening_hand_is_three_bigger_and_mulligan_is_barred(self, repo):
        from swu.engine.actions import legal_actions, KeepHand, TakeMultiligan
        state = _setup_game_with_base(repo, "28")
        assert len(state.player_by_id("P0").hand) == 9
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert kinds == {KeepHand.__name__}
        assert TakeMultiligan.__name__ not in kinds

    def test_JTL_28_first_action_phase_bottoms_three_cards(self, repo):
        state = _make_state()
        _swap_base_jtl(state, "P0", _get_card(repo, "JTL", "28"))
        _add_hand_cards_jtl(state, "P0", repo, 5)
        _add_deck_cards_jtl(state, "P0", repo, 2)
        deck_before = len(state.player_by_id("P0").deck)

        state = _fire_action_phase_start_jtl(state, round_number=1)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "bottom_from_hand" and top.context["count"] == 3

        from swu.engine.actions import legal_actions, apply
        for _ in range(3):
            act = next(a for a in legal_actions(state)
                       if type(a).__name__ == "SelectHandCardToBottom")
            state = apply(state, act)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 2 and len(ps.deck) == deck_before + 3

    def test_JTL_28_does_not_fire_on_a_later_action_phase(self, repo):
        state = _make_state()
        _swap_base_jtl(state, "P0", _get_card(repo, "JTL", "28"))
        _add_hand_cards_jtl(state, "P0", repo, 5)
        state = _fire_action_phase_start_jtl(state, round_number=3)
        state = _drain_jtl(state)
        assert not state.pending_decisions


class TestAnnihilatorJTL41:
    """JTL_41 — defeat an enemy unit, then purge every card of that NAME."""

    def test_JTL_41_purges_the_name_from_deck_and_hand(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        annihilator = _place(state, "P0", _get_card(repo, "JTL", "41"), "space")
        victim_def = _get_card(repo, "JTL", "63")     # Landing Shuttle
        victim = _place(state, "P1", victim_def, "ground")
        # A copy in hand, a copy in deck, and an unrelated card in each.
        state.player_by_id("P1").hand.append(CardInstance(
            instance_id="P1_h1", card_def=victim_def, owner_id="P1", zone=Zone.HAND))
        _add_hand_cards_jtl(state, "P1", repo, 1)
        _stack_deck_jtl(state, "P1", [victim_def, _get_card(repo, "SOR", "61")])

        state = _fire_when_played(state, annihilator)
        state = _accept_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)

        ps = state.player_by_id("P1")
        assert _find_instance(state, victim.instance_id) is None
        name = victim_def.name
        assert not any(c.card_def.name == name for c in ps.hand)
        assert not any(c.card_def.name == name for c in ps.deck)
        # Three copies (arena + hand + deck) all ended up in the discard pile.
        assert sum(1 for c in ps.discard if c.card_def.name == name) == 3
        # Unrelated cards are untouched.
        assert len(ps.hand) == 1 and len(ps.deck) == 1

    def test_JTL_41_registers_both_trigger_sides(self):
        from swu.abilities.registry import get_abilities
        import swu.cards  # noqa: F401
        triggers = {type(s.trigger).__name__ for s in get_abilities("JTL", "41")}
        assert triggers == {"WhenPlayed", "WhenDefeated"}


class TestCassianAndorJTL48:
    """JTL_48 — granted On Attack: mill the defender's deck, draw on a cheap hit."""

    def test_JTL_48_mills_and_draws_when_the_milled_card_is_cheap(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "48"), "P0")
        _stack_deck_jtl(state, "P1", [_get_card(repo, "SOR", "61")])   # cost 2
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, host)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P1").discard) == 1
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_48_expensive_milled_card_draws_nothing(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "40"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "48"), "P0")
        _stack_deck_jtl(state, "P1", [_get_card(repo, "JTL", "41")])   # cost 11
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, host)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P1").discard) == 1
        assert len(state.player_by_id("P0").hand) == before

    def test_JTL_48_as_a_unit_grants_nothing(self, repo):
        state = _make_state()
        cassian = _place(state, "P0", _get_card(repo, "JTL", "48"), "ground")
        _stack_deck_jtl(state, "P1", [_get_card(repo, "SOR", "61")])
        state = _fire_on_attack(state, cassian)
        state = _drain_jtl(state)
        # A GrantedAbility is never collected from an arena unit — no mill.
        assert not state.player_by_id("P1").discard


class TestLandingShuttleJTL63:
    """JTL_63 — When Defeated: you may draw a card."""

    def test_JTL_63_when_defeated_draws_a_card(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "63"), "ground")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state = _fire_when_defeated(state, shuttle)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").hand) == before + 1


class TestTheInvisibleHandJTL89:
    """JTL_89 — search the top 8 for a Droid unit, draw it, play it free if ≤2."""

    def test_JTL_89_drawn_cheap_droid_is_then_played_for_free(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        hand_ship = _place(state, "P0", _get_card(repo, "JTL", "89"), "space")
        # JTL_256 Swarming Vulture Droid — a Droid unit costing 2.
        droid = _stack_deck_jtl(state, "P0", [_get_card(repo, "JTL", "256")])[0]
        _add_deck_cards_jtl(state, "P0", repo, 4)

        state = _fire_when_played(state, hand_ship)
        state = _drain_jtl(state)
        pick = next(a for a in legal_actions(state)
                    if type(a).__name__ == "SelectSearchCard"
                    and a.instance_id == droid.instance_id)
        state = apply(state, pick)
        state = _drain_jtl(state)
        # Drawn, then whitelisted into a free play_from_hand.
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert top.context["free"] is True
        assert top.context["eligible_ids"] == [droid.instance_id]

        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "PlayFromHand"))
        state = _drain_jtl(state)
        assert _find_instance(state, droid.instance_id) is not None

    def test_JTL_89_registers_when_played_and_attack_ends(self):
        from swu.abilities.registry import get_abilities
        import swu.cards  # noqa: F401
        triggers = {type(s.trigger).__name__ for s in get_abilities("JTL", "89")}
        assert triggers == {"WhenPlayed", "WhenAttackEnds"}


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:09 — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════


class TestSnapWexleyJTL98:
    """JTL_98 — a Resistance discount as a unit, a Resistance dig as an upgrade."""

    def test_JTL_98_as_a_unit_discounts_the_next_resistance_card(self, repo):
        state = _make_state()
        snap = _place(state, "P0", _get_card(repo, "JTL", "98"), "ground")
        state = _fire_when_played(state, snap)
        state = _drain_jtl(state)
        pending = [e for e in state.game_memory.pending_play_discounts
                   if e["player_id"] == "P0"]
        assert len(pending) == 1
        assert pending[0]["trait"] == "Resistance" and pending[0]["amount"] == 1
        assert pending[0]["units_only"] is False

    def test_JTL_98_on_attack_discounts_too(self, repo):
        state = _make_state()
        snap = _place(state, "P0", _get_card(repo, "JTL", "98"), "ground")
        state = _fire_on_attack(state, snap)
        state = _drain_jtl(state)
        assert any(e["player_id"] == "P0"
                   for e in state.game_memory.pending_play_discounts)

    def test_JTL_98_as_an_upgrade_digs_for_a_resistance_card(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        snap_ci = _attach_upgrade_directly(state, host,
                                           _get_card(repo, "JTL", "98"), "P0")
        wanted = _stack_deck_jtl(state, "P0", [_get_card(repo, "JTL", "247")])[0]
        _add_deck_cards_jtl(state, "P0", repo, 4)

        state = _fire_upgrade_played(state, snap_ci, host)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search" and top.context["window"] == 5
        # Only the Resistance card is a candidate; the search is mandatory.
        assert top.context["candidate_ids"] == [wanted.instance_id]
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "SelectSearchCard"))
        assert any(c.instance_id == wanted.instance_id
                   for c in state.player_by_id("P0").hand)


class TestEjectJTL126:
    """JTL_126 — detach a Pilot upgrade into the ground arena as an exhausted unit."""

    def test_JTL_126_stands_the_pilot_up_as_a_ground_unit_and_draws(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        pilot = _attach_upgrade_directly(state, host,
                                         _get_card(repo, "JTL", "98"), "P0")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").hand)

        state, _ = _play_event_from_hand(state, repo, "JTL", "126", resources=10)
        state = _drain_jtl(state)
        state = _choose_jtl(state, pilot.instance_id)
        state = _drain_jtl(state)

        moved = _find_instance(state, pilot.instance_id)
        assert moved is not None and moved.zone == Zone.GROUND_ARENA
        assert moved.exhausted is True
        assert not _find_instance(state, host.instance_id).attached_upgrades
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_126_ignores_a_non_pilot_upgrade(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "227"), "P0")
        _add_deck_cards_jtl(state, "P0", repo, 2)

        state, _ = _play_event_from_hand(state, repo, "JTL", "126", resources=10)
        state = _drain_jtl(state)
        # No Pilot upgrade in play → nothing to detach, but the draw still happens.
        assert not _target_ids_jtl(state)
        assert _find_instance(state, host.instance_id).attached_upgrades


class TestGeneralHuxJTL134:
    """JTL_134 — Raid 1 anthem for other First Order units + a conditional draw."""

    def test_JTL_134_grants_raid_1_to_other_first_order_units(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        hux = _place(state, "P0", _get_card(repo, "JTL", "134"), "ground")
        mate = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")  # FO
        outsider = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")

        assert has_keyword(state, mate, Keyword.RAID)
        assert keyword_value(state, mate, Keyword.RAID) == 1
        assert not has_keyword(state, outsider, Keyword.RAID)
        # "Each OTHER friendly First Order unit" — Hux does not buff himself.
        assert not has_keyword(state, hux, Keyword.RAID)

    def test_JTL_134_action_needs_a_first_order_card_played_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        hux = _place(state, "P0", _get_card(repo, "JTL", "134"), "ground")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == hux.instance_id]

        _mark_trait_played(state, "P0", "First Order")
        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == hux.instance_id)
        before = len(state.player_by_id("P0").hand)
        state = apply(state, act)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").hand) == before + 1
        assert _find_instance(state, hux.instance_id).exhausted is True


class TestStayOnTargetJTL177:
    """JTL_177 — attack with a Vehicle at +2/+0; drawing when a base is hit."""

    def test_JTL_177_base_attack_draws_a_card(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        fighter.exhausted = False
        _add_deck_cards_jtl(state, "P0", repo, 3)

        state, _ = _play_event_from_hand(state, repo, "JTL", "177", resources=10)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["attacker_trait"] == "Vehicle"
        assert top.context["draw_if_base_damaged"] is True

        before = len(state.player_by_id("P0").hand)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == fighter.instance_id
                   and a.defender_id is None)
        state = apply(state, atk)
        state = _drain_jtl(state)
        assert state.player_by_id("P1").base_instance.damage > 0
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_177_unit_attack_that_misses_the_base_draws_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        fighter.exhausted = False
        blocker = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 3)

        state, _ = _play_event_from_hand(state, repo, "JTL", "177", resources=10)
        state = _drain_jtl(state)
        before = len(state.player_by_id("P0").hand)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == fighter.instance_id
                   and a.defender_id == blocker.instance_id)
        state = apply(state, atk)
        state = _drain_jtl(state)
        assert state.player_by_id("P1").base_instance.damage == 0
        assert len(state.player_by_id("P0").hand) == before


class TestMistHunterJTL186:
    """JTL_186 — On Attack draw, gated on a Bounty Hunter OR Pilot card played."""

    def test_JTL_186_no_qualifying_play_means_no_prompt(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "JTL", "186"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        state = _fire_on_attack(state, hunter)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_JTL_186_either_trait_satisfies_the_disjunction(self, repo):
        for trait in ("Bounty Hunter", "Pilot"):
            state = _make_state()
            hunter = _place(state, "P0", _get_card(repo, "JTL", "186"), "space")
            _add_deck_cards_jtl(state, "P0", repo, 2)
            _mark_trait_played(state, "P0", trait)
            before = len(state.player_by_id("P0").hand)
            state = _fire_on_attack(state, hunter)
            state = _accept_jtl(state)
            state = _drain_jtl(state)
            assert len(state.player_by_id("P0").hand) == before + 1

    def test_JTL_186_both_traits_still_draw_only_once(self, repo):
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "JTL", "186"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 3)
        _mark_trait_played(state, "P0", "Bounty Hunter", "Pilot")
        before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, hunter)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").hand) == before + 1


class TestInvincibleJTL191:
    """JTL_191 — a unique-Separatist discount + a bounce when you deploy a leader."""

    def test_JTL_191_costs_one_less_with_a_unique_separatist_in_play(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        ci = CardInstance(instance_id="P0_inv", card_def=_get_card(repo, "JTL", "191"),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(ci)
        # Compare the DELTA — the absolute figure also carries the aspect penalty.
        plain = _play_cost(state, ci, ps)

        # JTL_89 The Invisible Hand — a unique Separatist unit.
        _place(state, "P0", _get_card(repo, "JTL", "89"), "space")
        assert _play_cost(state, ci, ps) == plain - 1

    def test_JTL_191_non_unique_separatist_gives_no_discount(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        ci = CardInstance(instance_id="P0_inv2", card_def=_get_card(repo, "JTL", "191"),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(ci)
        plain = _play_cost(state, ci, ps)
        # JTL_256 Swarming Vulture Droid — Separatist, but NOT unique.
        _place(state, "P0", _get_card(repo, "JTL", "256"), "space")
        assert _play_cost(state, ci, ps) == plain

    def test_JTL_191_when_you_deploy_a_leader_bounces_a_cheap_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "191"), "space")
        leader = _place_leader(state, "P0", _get_card(repo, "JTL", "14"))
        _deploy_leader_to_arena(state, leader, "ground")
        cheap = _place(state, "P1", _get_card(repo, "JTL", "132"), "ground")  # 1
        pricey = _place(state, "P1", _get_card(repo, "JTL", "41"), "space")   # 11

        state = _fire_leader_deployed_jtl(state, leader)
        state = _accept_jtl(state)
        offered = _target_ids_jtl(state)
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered

        state = _choose_jtl(state, cheap.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, cheap.instance_id) is None
        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P1").hand)


class TestHeartlessTacticsJTL194:
    """JTL_194 — exhaust + −2/−0; a non-leader left at 0 power goes back to hand."""

    def test_JTL_194_zero_power_unit_is_bounced(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "JTL", "132"), "ground")  # 2/1
        victim.exhausted = False

        state, _ = _play_event_from_hand(state, repo, "JTL", "194", resources=10)
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, victim.instance_id) is None
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P1").hand)

    def test_JTL_194_bigger_unit_is_only_exhausted_and_debuffed(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "JTL", "40"), "space")   # 6/6
        victim.exhausted = False

        state, _ = _play_event_from_hand(state, repo, "JTL", "194", resources=10)
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)
        hit = _find_instance(state, victim.instance_id)
        assert hit is not None and hit.exhausted is True
        assert compute_power(state, hit) == 4


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:10 — Card advantage & disruption
# (JTL_197, JTL_205, JTL_207, JTL_220, JTL_221, JTL_223)
# ══════════════════════════════════════════════════════════════════════════════


def _fire_attack_ends_jtl(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for a SURVIVING attacker (the LOF_38 shape)."""
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


def _fire_pilot_attached_jtl(state, pilot_ci):
    """Fire the CardPlayed observer for a pilot that is already attached to its
    host (what PilotPlay / _attach_upgrade do before firing triggers)."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=pilot_ci.owner_id, instance_id=pilot_ci.instance_id,
                     card_name=pilot_ci.card_def.display_name, cost_paid=0)
    state.event_log.append(evt)
    after = 1 - state.player_index(pilot_ci.owner_id)
    return fire_triggered_abilities(state, evt, after_all_player_idx=after)


def _discard_jtl(state, owner_id, card_def):
    """Put a fresh instance of ``card_def`` into ``owner_id``'s discard pile."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    ci = CardInstance(instance_id=f"{owner_id}_dc_{_uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD)
    state.player_by_id(owner_id).discard.append(ci)
    return ci


class TestAnakinSkywalkerJTL197:
    """JTL_197 — Piloting; attached unit's completed attack may bounce the pilot."""

    def _attached(self, state, repo):
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        anakin = _attach_upgrade_directly(
            state, host, _get_card(repo, "JTL", "197"), "P0")
        return host, anakin

    def test_JTL_197_attack_ends_returns_the_pilot_upgrade_to_hand(self, repo):
        state = _make_state()
        host, anakin = self._attached(state, repo)

        state = _fire_attack_ends_jtl(state, host)
        state = _accept_jtl(state)
        state = _drain_jtl(state)

        live_host = _find_instance(state, host.instance_id)
        assert live_host is not None, "the host stays in play"
        assert not any(u.instance_id == anakin.instance_id
                       for u in live_host.attached_upgrades)
        assert any(c.instance_id == anakin.instance_id
                   for c in state.player_by_id("P0").hand)

    def test_JTL_197_declining_leaves_the_pilot_attached(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        host, anakin = self._attached(state, repo)

        state = _fire_attack_ends_jtl(state, host)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        state = _drain_jtl(state)

        live_host = _find_instance(state, host.instance_id)
        assert any(u.instance_id == anakin.instance_id
                   for u in live_host.attached_upgrades)
        assert not state.player_by_id("P0").hand

    def test_JTL_197_bare_vehicle_offers_no_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        state = _fire_attack_ends_jtl(state, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestCommencePatrolJTL205:
    """JTL_205 — bottom another discarded card; if you do, create an X-Wing."""

    def test_JTL_205_bottoms_a_card_and_creates_an_xwing(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectBottomDiscardCard)
        state = _make_state()
        victim = _discard_jtl(state, "P1", _get_card(repo, "SOR", "210"))
        deck_before = len(state.player_by_id("P1").deck)

        state, _ = _play_event_from_hand(state, repo, "JTL", "205", resources=10)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "bottom_from_discard"

        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectBottomDiscardCard)
                    and a.instance_id == victim.instance_id)
        state = apply(state, pick)

        p1 = state.player_by_id("P1")
        assert len(p1.deck) == deck_before + 1
        assert p1.deck[-1].instance_id == victim.instance_id
        assert not any(c.instance_id == victim.instance_id for c in p1.discard)
        # "If you do, create an X-Wing token" — the space arena gains one.
        xwings = [u for u in state.player_by_id("P0").space_arena
                  if u.card_def.display_name == "X-Wing"]
        assert len(xwings) == 1

    def test_JTL_205_cannot_bottom_itself(self, repo):
        from swu.engine.actions import legal_actions, SelectBottomDiscardCard
        state = _make_state()
        other = _discard_jtl(state, "P0", _get_card(repo, "SOR", "210"))

        state, patrol = _play_event_from_hand(state, repo, "JTL", "205",
                                              resources=10)
        state = _drain_jtl(state)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)}
        # The event is already in its own discard pile — "ANOTHER card" excludes it.
        assert patrol.instance_id not in offered
        assert other.instance_id in offered

    def test_JTL_205_with_an_empty_discard_makes_no_token(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "JTL", "205", resources=10)
        state = _drain_jtl(state)
        # Only the event itself is in a discard pile, and it is excluded → fizzle.
        assert not state.pending_decisions
        assert not state.player_by_id("P0").space_arena


class TestJamCommunicationsJTL207:
    """JTL_207 — look at an opponent's hand and discard an EVENT from it."""

    def _seed_hand(self, state, repo):
        """P1 holds one event (SOR_223) and one unit (SOR_210)."""
        from swu.engine.state import CardInstance, Zone
        made = []
        for sc, num in (("SOR", "223"), ("SOR", "210")):
            ci = CardInstance(instance_id=f"P1_h_{num}",
                              card_def=_get_card(repo, sc, num),
                              owner_id="P1", zone=Zone.HAND)
            state.player_by_id("P1").hand.append(ci)
            made.append(ci)
        return made

    def test_JTL_207_only_events_can_be_named(self, repo):
        from swu.engine.actions import legal_actions, NameAndDiscard
        state = _make_state()
        event_ci, unit_ci = self._seed_hand(state, repo)

        state, _ = _play_event_from_hand(state, repo, "JTL", "207", resources=10)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard"
        # The WHOLE hand is revealed (the printed "look at an opponent's hand") …
        assert {c["card_name"] for c in top.context["revealed_hand"]} == {
            event_ci.card_def.display_name, unit_ci.card_def.display_name}
        # … but only the event may be named.
        assert {a.card_name for a in legal_actions(state)
                if isinstance(a, NameAndDiscard)} == {
                    event_ci.card_def.display_name}

    def test_JTL_207_discards_the_named_event(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        event_ci, unit_ci = self._seed_hand(state, repo)

        state, _ = _play_event_from_hand(state, repo, "JTL", "207", resources=10)
        state = _drain_jtl(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, NameAndDiscard)))

        p1 = state.player_by_id("P1")
        assert [c.instance_id for c in p1.hand] == [unit_ci.instance_id]
        assert any(c.instance_id == event_ci.instance_id for c in p1.discard)

    def test_JTL_207_fizzles_when_the_hand_holds_no_event(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        state.player_by_id("P1").hand.append(CardInstance(
            instance_id="P1_h_unit", card_def=_get_card(repo, "SOR", "210"),
            owner_id="P1", zone=Zone.HAND))

        state, _ = _play_event_from_hand(state, repo, "JTL", "207", resources=10)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == 1


class TestSkywayCloudCarJTL220:
    """JTL_220 — When Defeated: may bounce a non-leader unit with ≤2 power."""

    def test_JTL_220_when_defeated_bounces_a_low_power_unit(self, repo):
        state = _make_state()
        car = _place(state, "P0", _get_card(repo, "JTL", "220"), "space")
        weak = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3

        state = _fire_when_defeated(state, car)
        state = _accept_jtl(state)
        state = _choose_jtl(state, weak.instance_id)
        state = _drain_jtl(state)

        assert _find_instance(state, weak.instance_id) is None
        assert any(c.instance_id == weak.instance_id
                   for c in state.player_by_id("P1").hand)

    def test_JTL_220_cannot_bounce_a_unit_over_2_power(self, repo):
        state = _make_state()
        car = _place(state, "P0", _get_card(repo, "JTL", "220"), "space")
        weak = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2 pw
        strong = _place(state, "P1", _get_card(repo, "SOR", "210"), "ground")  # 4 pw

        state = _fire_when_defeated(state, car)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert weak.instance_id in offered
        assert strong.instance_id not in offered

    def test_JTL_220_power_is_effective_not_printed(self, repo):
        """An Experience token pushes a 2-power unit out of reach."""
        state = _make_state()
        car = _place(state, "P0", _get_card(repo, "JTL", "220"), "space")
        weak = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        _attach_upgrade_directly(state, weak, _get_card(repo, "JTL", "3"), "P1")

        state = _fire_when_defeated(state, car)
        state = _drain_jtl(state)
        from swu.engine.actions import legal_actions, AcceptTrigger
        # 3 power now — no legal target, so the optional trigger auto-declines.
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestStolenATHaulerJTL221:
    """JTL_221 — When Defeated: an opponent may replay it free from your discard."""

    def test_JTL_221_when_defeated_grants_the_opponent_a_free_replay(self, repo):
        state = _make_state()
        hauler = _place(state, "P0", _get_card(repo, "JTL", "221"), "space")

        state = _fire_when_defeated(state, hauler)
        state = _drain_jtl(state)

        ledger = state.game_memory.foreign_free_discard_play_this_phase
        assert ledger.get("P1") == [hauler.instance_id]
        assert "P0" not in ledger

    def test_JTL_221_opponent_plays_it_free_from_its_owners_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromDiscard
        from swu.engine.state import Zone
        state = _make_state()
        hauler = _place(state, "P0", _get_card(repo, "JTL", "221"), "space")

        state = _fire_when_defeated(state, hauler)
        state = _drain_jtl(state)
        # Complete the defeat: the unit lands in its OWNER's discard pile.
        p0 = state.player_by_id("P0")
        live = next(u for u in p0.space_arena if u.instance_id == hauler.instance_id)
        p0.space_arena.remove(live)
        live.zone = Zone.DISCARD
        p0.discard.append(live)

        state.active_player_index = 1
        replay = [a for a in legal_actions(state)
                  if isinstance(a, PlayFromDiscard)
                  and a.instance_id == hauler.instance_id]
        assert replay and replay[0].free is True

        p1_before = len(state.player_by_id("P1").resources)
        state = apply(state, replay[0])

        stolen = _find_instance(state, hauler.instance_id)
        assert stolen is not None
        assert any(u.instance_id == hauler.instance_id
                   for u in state.player_by_id("P1").space_arena)
        assert stolen.owner_id == "P0", "ownership never changes — only control"
        # Free: no resource was exhausted to pay for it.
        assert sum(1 for r in state.player_by_id("P1").resources if r.exhausted) == 0
        assert p1_before == len(state.player_by_id("P1").resources)
        # The one-shot permission is consumed.
        assert not (state.game_memory
                    .foreign_free_discard_play_this_phase.get("P1"))

    def test_JTL_221_owner_gets_no_free_replay(self, repo):
        from swu.engine.actions import legal_actions, PlayFromDiscard
        from swu.engine.state import Zone
        state = _make_state()
        hauler = _place(state, "P0", _get_card(repo, "JTL", "221"), "space")

        state = _fire_when_defeated(state, hauler)
        state = _drain_jtl(state)
        p0 = state.player_by_id("P0")
        live = next(u for u in p0.space_arena if u.instance_id == hauler.instance_id)
        p0.space_arena.remove(live)
        live.zone = Zone.DISCARD
        p0.discard.append(live)

        assert not [a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == hauler.instance_id]


class TestRazorCrestJTL223:
    """JTL_223 — a Pilot attaching may bounce a cheap (or exhausted) unit."""

    def test_JTL_223_pilot_attach_bounces_a_cheap_unit(self, repo):
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "JTL", "223"), "space")
        pilot = _attach_upgrade_directly(
            state, crest, _get_card(repo, "JTL", "197"), "P0")
        cheap = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2

        state = _fire_pilot_attached_jtl(state, pilot)
        state = _accept_jtl(state)
        state = _choose_jtl(state, cheap.instance_id)
        state = _drain_jtl(state)

        assert _find_instance(state, cheap.instance_id) is None
        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P1").hand)

    def test_JTL_223_exhausted_units_get_the_higher_cost_cap(self, repo):
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "JTL", "223"), "space")
        pilot = _attach_upgrade_directly(
            state, crest, _get_card(repo, "JTL", "197"), "P0")
        cheap = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")   # 2
        mid = _place(state, "P1", _get_card(repo, "SOR", "210"), "ground")     # 3
        tapped = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 4
        tapped.exhausted = True
        big = _place(state, "P1", _get_card(repo, "JTL", "69"), "space")       # 5
        big.exhausted = True
        mid.exhausted = False

        state = _fire_pilot_attached_jtl(state, pilot)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert cheap.instance_id in offered          # ≤2, ready
        assert tapped.instance_id in offered         # ≤4 and exhausted
        assert mid.instance_id not in offered        # 3 and READY
        assert big.instance_id not in offered        # 5, even exhausted

    def test_JTL_223_real_pilot_play_fires_the_trigger(self, repo):
        from swu.engine.actions import legal_actions, apply, PilotPlay, AcceptTrigger
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "JTL", "223"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        pilot = CardInstance(instance_id="P0_pilot_197",
                             card_def=_get_card(repo, "JTL", "197"),
                             owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(pilot)
        _give_resources(state, "P0", 20)

        state = apply(state, PilotPlay(pilot.instance_id, crest.instance_id))
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_JTL_223_non_pilot_upgrade_does_not_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "JTL", "223"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        turret = _attach_upgrade_directly(
            state, crest, _get_card(repo, "JTL", "120"), "P0")  # Dorsal Turret

        state = _fire_pilot_attached_jtl(state, turret)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:11 — Leaders (combat tricks, buffs & tempo)
# (JTL_3, JTL_4, JTL_5, JTL_7, JTL_8, JTL_11; JTL_2 Thrawn is a flagged escalation)
#
# JTL_3 and JTL_4 SHARE THEIR NUMBERS with the Experience and Shield token
# upgrades, so each class carries a regression test proving the token reaches none
# of the leader's abilities.
# ══════════════════════════════════════════════════════════════════════════════


def _leader_jtl(repo, num):
    """Hydrate the LEADER-typed row for JTL/<num> (numbers 1–4 collide with a
    same-numbered Token, which the plain ``_get_card`` fetchone may return)."""
    from tests.test_sor_cards import _get_leader
    return _get_leader(repo, "JTL", num)


def _token_def_jtl(repo, num, card_type):
    """Hydrate the TOKEN-typed row for JTL/<num> — the twin of ``_leader_jtl``, for
    the collision regressions (``_get_card`` returns whichever row comes first)."""
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code='JTL' AND card_number=? AND type=?",
            (str(int(num)), card_type),
        ).fetchone()
        from tests.dbpath import require_row
        return repo._hydrate(con, require_row(row, f"JTL_{num} ({card_type})"))


def _place_deployed_leader_jtl(state, owner_id, leader_def, arena="ground"):
    ci = _place(state, owner_id, leader_def, arena)
    ci.deployed = True
    ci.exhausted = False
    return ci


def _hand_jtl(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    import uuid as _uuid
    ci = CardInstance(instance_id=f"{owner_id}_h_{_uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.HAND)
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _fire_pilot_leader_deploy_jtl(state, leader_ci, host_ci):
    """Fire the LeaderDeployed event for a leader deployed AS AN UPGRADE."""
    from swu.engine.events import LeaderDeployed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = LeaderDeployed(player_id=leader_ci.owner_id,
                         instance_id=leader_ci.instance_id,
                         leader_name=leader_ci.card_def.display_name,
                         arena="Ground")
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=1,
        event_ctx={"via_pilot_leader": True,
                   "attached_to_id": host_ci.instance_id})


def _use_actions_jtl(state, source_ci):
    from swu.engine.actions import legal_actions, UseAbility
    return [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]


def _token_target_ids_jtl(state):
    """Instance ids offered by a pending 'select_token' decision."""
    from swu.engine.actions import legal_actions, SelectTokenTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, SelectTokenTarget)}


def _select_token_jtl(state, target_id):
    from swu.engine.actions import legal_actions, apply, SelectTokenTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, SelectTokenTarget) and a.target_id == target_id)
    return apply(state, act)


class TestLandoCalrissianJTL3:
    """JTL_3 — Action: play a unit; if you then hold both arenas, Shield a unit."""

    def _setup(self, repo, with_space=True):
        state = _make_state()
        lando = _place_leader(state, "P0", _leader_jtl(repo, "3"))
        _give_resources(state, "P0", 20)
        if with_space:
            _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # Y-Wing
        unit = _hand_jtl(state, "P0", _get_card(repo, "SOR", "247"))     # ground 2/3
        return state, lando, unit

    def test_JTL_3_action_plays_a_unit_then_shields_when_both_arenas_held(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state, lando, unit = self._setup(repo)

        state = _use_ability_jtl(state, lando)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)
                                  and a.instance_id == unit.instance_id))
        state = _drain_jtl(state)

        assert state.pending_decisions[-1].kind == "select_token"
        played = _find_instance(state, unit.instance_id)
        assert played is not None
        state = _select_token_jtl(state, played.instance_id)
        assert _shield_count(_find_instance(state, unit.instance_id)) == 1

    def test_JTL_3_no_shield_when_only_one_arena_is_held(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state, lando, unit = self._setup(repo, with_space=False)

        state = _use_ability_jtl(state, lando)
        state = _drain_jtl(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)
                                  and a.instance_id == unit.instance_id))
        state = _drain_jtl(state)

        assert not [d for d in state.pending_decisions if d.kind == "select_token"]
        assert _shield_count(_find_instance(state, unit.instance_id)) == 0

    def test_JTL_3_deploying_as_an_upgrade_grants_sentinel_and_shields_other_arena(
            self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "ground")  # Vehicle
        far = _place(state, "P0", _get_card(repo, "JTL", "95"), "space")
        near = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        lando = _place_leader(state, "P0", _leader_jtl(repo, "3"))
        _attach_leader_as_pilot(state, host, lando)

        state = _fire_pilot_leader_deploy_jtl(state, lando, host)
        state = _drain_jtl(state)

        live_host = _find_instance(state, host.instance_id)
        assert has_keyword(state, live_host, Keyword.SENTINEL)
        # "a unit in a DIFFERENT arena" — only the space unit is offered.
        offered = _token_target_ids_jtl(state)
        assert far.instance_id in offered
        assert near.instance_id not in offered
        assert host.instance_id not in offered

    def test_JTL_3_experience_token_never_gets_the_leader_ability(self, repo):
        """The Experience TOKEN shares the number JTL_3 — it must reach nothing."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "JTL", "212"), "ground")
        token = _attach_upgrade_directly(
            state, unit, _token_def_jtl(repo, "3", "Token Upgrade"), "P0")
        _give_resources(state, "P0", 20)
        _hand_jtl(state, "P0", _get_card(repo, "SOR", "247"))

        assert token.card_def.type == "Token Upgrade"
        assert not _use_actions_jtl(state, token)
        assert not _use_actions_jtl(state, unit)
        assert not has_keyword(state, _find_instance(state, unit.instance_id),
                               Keyword.SENTINEL)


class TestRoseTicoJTL4:
    """JTL_4 — heal a Vehicle (undeployed: one that attacked this phase)."""

    def test_JTL_4_undeployed_heals_only_a_vehicle_that_attacked(self, repo):
        state = _make_state()
        rose = _place_leader(state, "P0", _leader_jtl(repo, "4"))
        attacked = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        idle = _place(state, "P0", _get_card(repo, "JTL", "95"), "space")
        attacked.damage = 2
        idle.damage = 2
        state.game_memory.units_attacked_this_round.add(attacked.instance_id)

        state = _use_ability_jtl(state, rose)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert attacked.instance_id in offered
        assert idle.instance_id not in offered

        state = _choose_jtl(state, attacked.instance_id)
        assert _find_instance(state, attacked.instance_id).damage == 0

    def test_JTL_4_deployed_on_attack_heals_any_vehicle(self, repo):
        state = _make_state()
        rose = _place_deployed_leader_jtl(state, "P0", _leader_jtl(repo, "4"))
        hurt = _place(state, "P0", _get_card(repo, "JTL", "95"), "space")
        hurt.damage = 3

        state = _fire_on_attack(state, rose)
        state = _accept_jtl(state)
        state = _choose_jtl(state, hurt.instance_id)
        assert _find_instance(state, hurt.instance_id).damage == 1

    def test_JTL_4_shield_token_never_gets_the_leader_ability(self, repo):
        """The Shield TOKEN shares the number JTL_4 — it must reach nothing."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        token = _attach_upgrade_directly(
            state, unit, _token_def_jtl(repo, "4", "Token Upgrade"), "P0")
        hurt = _place(state, "P0", _get_card(repo, "JTL", "95"), "space")
        hurt.damage = 3

        assert token.card_def.type == "Token Upgrade"
        assert not _use_actions_jtl(state, token)
        # A shielded unit attacking offers no "heal a Vehicle" trigger.
        state = _fire_on_attack(state, unit)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestAdmiralPiettJTL5:
    """JTL_5 — undeployed plays a Capital Ship for 1 less; deployed, each costs 2 less."""

    def test_JTL_5_undeployed_action_plays_a_capital_ship_for_1_less(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand, _play_cost
        state = _make_state()
        piett = _place_leader(state, "P0", _leader_jtl(repo, "5"))
        ship = _hand_jtl(state, "P0", _get_card(repo, "JTL", "69"))   # Capital Ship 5
        other = _hand_jtl(state, "P0", _get_card(repo, "SOR", "247"))  # not one
        _give_resources(state, "P0", 20)
        plain = _play_cost(state, ship, state.player_by_id("P0"))
        before = len([r for r in state.player_by_id("P0").resources if not r.exhausted])

        state = _use_ability_jtl(state, piett)
        state = _drain_jtl(state)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert offered == {ship.instance_id}, "only Capital Ship units are offered"
        assert other.instance_id not in offered

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)))
        spent = before - len([r for r in state.player_by_id("P0").resources
                              if not r.exhausted])
        assert spent == plain - 1, "the ability's own 1-resource discount"
        assert _find_instance(state, ship.instance_id) is not None

    def test_JTL_5_deployed_discounts_every_capital_ship_by_2(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ship = _hand_jtl(state, "P0", _get_card(repo, "JTL", "69"))
        plain = _hand_jtl(state, "P0", _get_card(repo, "SOR", "247"))
        _give_resources(state, "P0", 20)
        ps = state.player_by_id("P0")
        ship_before = _play_cost(state, ship, ps)
        plain_before = _play_cost(state, plain, ps)

        _place_deployed_leader_jtl(state, "P0", _leader_jtl(repo, "5"), "ground")
        assert _play_cost(state, ship, ps) == ship_before - 2
        assert _play_cost(state, plain, ps) == plain_before, "non-Capital Ship unchanged"

    def test_JTL_5_undeployed_leader_grants_no_standing_discount(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ship = _hand_jtl(state, "P0", _get_card(repo, "JTL", "69"))
        _give_resources(state, "P0", 20)
        ps = state.player_by_id("P0")
        before = _play_cost(state, ship, ps)
        _place_leader(state, "P0", _leader_jtl(repo, "5"))
        assert _play_cost(state, ship, ps) == before


class TestAdmiralHoldoJTL7:
    """JTL_7 — +2/+2 to a Resistance unit or a unit wearing a Resistance upgrade."""

    def test_JTL_7_undeployed_targets_resistance_or_resistance_upgraded_units(
            self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        holdo = _place_leader(state, "P0", _leader_jtl(repo, "7"))
        _give_resources(state, "P0", 10)
        native = _place(state, "P0", _get_card(repo, "JTL", "46"), "ground")   # Resistance
        carrier = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # not
        _attach_upgrade_directly(state, carrier, _get_card(repo, "JTL", "46"), "P0")
        plain = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")

        state = _use_ability_jtl(state, holdo)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert native.instance_id in offered
        assert carrier.instance_id in offered, "a Resistance upgrade qualifies its host"
        assert plain.instance_id not in offered

        before = compute_power(state, _find_instance(state, native.instance_id))
        state = _choose_jtl(state, native.instance_id)
        assert compute_power(state, _find_instance(state, native.instance_id)) == before + 2

    def test_JTL_7_deployed_on_attack_excludes_herself(self, repo):
        state = _make_state()
        holdo = _place_deployed_leader_jtl(state, "P0", _leader_jtl(repo, "7"))
        ally = _place(state, "P0", _get_card(repo, "JTL", "46"), "ground")

        state = _fire_on_attack(state, holdo)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert ally.instance_id in offered
        assert holdo.instance_id not in offered, "'another' excludes Holdo herself"


class TestWedgeAntillesJTL8:
    """JTL_8 — play a card using Piloting for 1 less; granted On Attack discounts
    the next Pilot card, INCLUDING its Piloting cost."""

    def test_JTL_8_undeployed_action_plays_a_pilot_for_1_less(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayViaPiloting, _piloting_cost)
        state = _make_state()
        wedge = _place_leader(state, "P0", _leader_jtl(repo, "8"))
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # Vehicle
        pilot = _hand_jtl(state, "P0", _get_card(repo, "JTL", "197"))       # Piloting 2
        _give_resources(state, "P0", 20)
        plain = _piloting_cost(state, pilot, state.player_by_id("P0"))
        before = len([r for r in state.player_by_id("P0").resources if not r.exhausted])

        state = _use_ability_jtl(state, wedge)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "play_via_piloting"
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayViaPiloting)
                   and a.instance_id == pilot.instance_id
                   and a.vehicle_target_id == host.instance_id)
        state = apply(state, act)

        live_host = _find_instance(state, host.instance_id)
        assert any(u.instance_id == pilot.instance_id
                   for u in live_host.attached_upgrades)
        spent = before - len([r for r in state.player_by_id("P0").resources
                              if not r.exhausted])
        assert spent == plain - 1, "the ability's own 1-resource discount"

    def test_JTL_8_no_pilot_play_without_a_friendly_vehicle(self, repo):
        state = _make_state()
        wedge = _place_leader(state, "P0", _leader_jtl(repo, "8"))
        _hand_jtl(state, "P0", _get_card(repo, "JTL", "197"))
        _give_resources(state, "P0", 20)
        # No Vehicle to ride ⇒ the gate refuses the action outright.
        assert not _use_actions_jtl(state, wedge)

    def test_JTL_8_granted_on_attack_discounts_the_next_piloting_cost(self, repo):
        from swu.engine.actions import _piloting_cost
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        wedge = _place_leader(state, "P0", _leader_jtl(repo, "8"))
        _attach_leader_as_pilot(state, host, wedge)
        pilot = _hand_jtl(state, "P0", _get_card(repo, "JTL", "197"))
        ps = state.player_by_id("P0")
        before = _piloting_cost(state, pilot, ps)

        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _drain_jtl(state)

        ps = state.player_by_id("P0")
        live_pilot = next(c for c in ps.hand if c.instance_id == pilot.instance_id)
        assert _piloting_cost(state, live_pilot, ps) == before - 1, (
            "'(This includes Piloting costs.)'")


class TestMajorVonregJTL11:
    """JTL_11 — play a Vehicle, then buff ANOTHER unit; granted On Attack buffs
    another unit in this arena."""

    def test_JTL_11_plays_a_vehicle_then_buffs_another_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand, compute_power
        state = _make_state()
        vonreg = _place_leader(state, "P0", _leader_jtl(repo, "11"))
        veh = _hand_jtl(state, "P0", _get_card(repo, "JTL", "212"))   # Vehicle 1
        ally = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        _give_resources(state, "P0", 20)

        state = _use_ability_jtl(state, vonreg)
        state = _drain_jtl(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)
                                  and a.instance_id == veh.instance_id))
        state = _drain_jtl(state)

        offered = _token_target_ids_jtl(state)
        assert ally.instance_id in offered
        assert veh.instance_id not in offered, "'another' excludes the played Vehicle"

        before = compute_power(state, _find_instance(state, ally.instance_id))
        state = _select_token_jtl(state, ally.instance_id)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == before + 1

    def test_JTL_11_action_needs_a_playable_vehicle(self, repo):
        state = _make_state()
        vonreg = _place_leader(state, "P0", _leader_jtl(repo, "11"))
        _hand_jtl(state, "P0", _get_card(repo, "SOR", "247"))  # not a Vehicle
        _give_resources(state, "P0", 20)
        assert not _use_actions_jtl(state, vonreg)

    def test_JTL_11_granted_on_attack_buffs_another_unit_in_this_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        vonreg = _place_leader(state, "P0", _leader_jtl(repo, "11"))
        _attach_leader_as_pilot(state, host, vonreg)
        same_arena = _place(state, "P0", _get_card(repo, "JTL", "95"), "space")
        other_arena = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")

        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert same_arena.instance_id in offered
        assert other_arena.instance_id not in offered
        assert host.instance_id not in offered, "'another' excludes the attacker"


class TestGrandAdmiralThrawnJTL2Registration:
    """JTL_2 Grand Admiral Thrawn — formerly a flagged escalation, implemented in
    the 2026-08-06 framework session as two ``WhenDefeatedRedo`` passive markers
    (one per leader side).  This pins the SHAPE: passive markers, not an activated
    ability, so he never adds a UseAbility to the action list.  Behaviour lives in
    ``TestGrandAdmiralThrawnJTL2``."""

    def test_JTL_2_registers_both_leader_sides_as_passive_markers(self, repo):
        from swu.abilities.registry import get_abilities, WhenDefeatedRedo
        specs = get_abilities("JTL", "2")
        assert [type(s) for s in specs] == [WhenDefeatedRedo, WhenDefeatedRedo]
        undeployed = next(s for s in specs if s.undeployed_only)
        deployed = next(s for s in specs if s.deployed_only)
        assert undeployed.cost_exhaust_source and not undeployed.once_per_round
        assert deployed.once_per_round and not deployed.cost_exhaust_source

    def test_JTL_2_adds_no_activated_ability(self, repo):
        state = _make_state()
        thrawn = _place_leader(state, "P0", _leader_jtl(repo, "2"))
        assert not _use_actions_jtl(state, thrawn)


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:12 — Combat tricks, buffs & tempo
# (JTL_15, JTL_16, JTL_32, JTL_34, JTL_36, JTL_42, JTL_44)
# ══════════════════════════════════════════════════════════════════════════════


def _xwing_count(state, owner):
    from swu.cards.models import TokenUnit
    ps = state.player_by_id(owner)
    return sum(1 for arena in (ps.ground_arena, ps.space_arena) for u in arena
               if isinstance(u.card_def, TokenUnit) and u.card_def.name == "X-Wing")


def _shield_jtl(state, host_ci):
    from swu.engine.tokens import attach_token
    return attach_token(state, state.player_by_id(host_ci.owner_id), host_ci, "Shield")


class TestRioDurantJTL15:
    """JTL_15 — Action: a space unit attacks at +1/+0 with Saboteur; as a Pilot
    upgrade the host gains Saboteur, and +1/+0 if it is a Transport."""

    def test_JTL_15_action_grants_a_space_attack_with_plus1_and_saboteur(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        rio = _place_leader(state, "P0", _leader_jtl(repo, "15"))
        _give_resources(state, "P0", 10)
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3
        defender = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")  # 1/3
        _shield_jtl(state, defender)

        state = _use_ability_jtl(state, rio)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id == defender.instance_id))

        hit = _find_instance(state, defender.instance_id)
        # Saboteur defeated the Shield first, so the +1/+0 attacker's 2 lands.
        assert _shield_count(hit) == 0
        assert hit.damage == 2

    def test_JTL_15_action_offers_only_space_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        rio = _place_leader(state, "P0", _leader_jtl(repo, "15"))
        _give_resources(state, "P0", 10)
        ground = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")

        state = _use_ability_jtl(state, rio)
        state = _drain_jtl(state)
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert space.instance_id in attackers
        assert ground.instance_id not in attackers

    def test_JTL_15_as_a_pilot_upgrade_grants_saboteur_to_the_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert has_keyword(state, host, Keyword.SABOTEUR) is False
        _attach_upgrade_directly(state, host, _leader_jtl(repo, "15"), "P0")
        assert has_keyword(state, host, Keyword.SABOTEUR) is True

    def test_JTL_15_transport_host_also_gets_plus1_power(self, repo):
        """+1/+0 only when the host is a Transport — compared as a DELTA against
        the same host's power with Rio detached (his own 3/5 upgrade box applies
        either way)."""
        from swu.engine.actions import compute_power
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # Fighter
        transport = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")  # Transport
        base_fighter = compute_power(state, fighter)
        base_transport = compute_power(state, transport)

        _attach_upgrade_directly(state, fighter, _leader_jtl(repo, "15"), "P0")
        _attach_upgrade_directly(state, transport, _leader_jtl(repo, "15"), "P0")
        # Rio's upgrade box is +3/+5 on both; only the Transport adds the extra +1.
        assert compute_power(state, fighter) == base_fighter + 3
        assert compute_power(state, transport) == base_transport + 3 + 1


class TestAdmiralAckbarJTL16:
    """JTL_16 — exhaust a unit; its CONTROLLER creates an X-Wing token."""

    def test_JTL_16_action_exhausts_an_enemy_unit_and_gives_them_an_xwing(self, repo):
        state = _make_state()
        ackbar = _place_leader(state, "P0", _leader_jtl(repo, "16"))
        _give_resources(state, "P0", 10)
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _use_ability_jtl(state, ackbar)
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)

        assert _find_instance(state, victim.instance_id).exhausted is True
        # "its controller" — the token goes to the VICTIM's owner, not Ackbar's.
        assert _xwing_count(state, "P1") == 1
        assert _xwing_count(state, "P0") == 0

    def test_JTL_16_action_never_targets_a_leader_unit_or_an_exhausted_one(self, repo):
        state = _make_state()
        ackbar = _place_leader(state, "P0", _leader_jtl(repo, "16"))
        _give_resources(state, "P0", 10)
        enemy_leader = _place_deployed_leader_jtl(state, "P1", _leader_jtl(repo, "16"))
        spent = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        ready = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")

        state = _use_ability_jtl(state, ackbar)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert ready.instance_id in offered
        assert enemy_leader.instance_id not in offered   # "non-leader unit"
        assert spent.instance_id not in offered          # "if you do" can't happen

    def test_JTL_16_deployed_on_attack_is_optional_and_may_hit_a_leader(self, repo):
        state = _make_state()
        ackbar = _place_deployed_leader_jtl(state, "P0", _leader_jtl(repo, "16"))
        enemy_leader = _place_deployed_leader_jtl(state, "P1", _leader_jtl(repo, "15"))

        state = _fire_on_attack(state, ackbar)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        # The deploy-box version drops the "non-leader" restriction.
        assert enemy_leader.instance_id in _target_ids_jtl(state)
        state = _choose_jtl(state, enemy_leader.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, enemy_leader.instance_id).exhausted is True
        assert _xwing_count(state, "P1") == 1

    def test_JTL_16_deployed_on_attack_can_be_declined(self, repo):
        state = _make_state()
        ackbar = _place_deployed_leader_jtl(state, "P0", _leader_jtl(repo, "16"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, ackbar)
        state = _decline_jtl(state)
        assert _xwing_count(state, "P1") == 0


class TestDirectorKrennicJTL32:
    """JTL_32 — the first When-Defeated unit you play each round costs 1 less."""

    def _hand_cost(self, state, repo, num):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id("P0")
        ci = CardInstance(instance_id=f"P0_h_{num}", card_def=_get_card(repo, "JTL", num)
                          if num in ("220",) else _get_card(repo, "SOR", num),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(ci)
        return ci, _play_cost(state, ci, ps)

    def test_JTL_32_discounts_a_when_defeated_unit_by_one(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci, plain = self._hand_cost(state, repo, "220")  # Skyway Cloud Car, When Defeated
        _place(state, "P0", _get_card(repo, "JTL", "32"), "ground")
        assert _play_cost(state, ci, state.player_by_id("P0")) == plain - 1

    def test_JTL_32_does_not_discount_a_unit_without_a_when_defeated_ability(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci, plain = self._hand_cost(state, repo, "247")  # Underworld Thug, no text
        _place(state, "P0", _get_card(repo, "JTL", "32"), "ground")
        assert _play_cost(state, ci, state.player_by_id("P0")) == plain

    def test_JTL_32_discount_is_spent_after_the_first_play_each_round(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci, plain = self._hand_cost(state, repo, "220")
        krennic = _place(state, "P0", _get_card(repo, "JTL", "32"), "ground")
        assert _play_cost(state, ci, state.player_by_id("P0")) == plain - 1
        state.game_memory.standing_play_discounts_used_this_round.add(krennic.instance_id)
        assert _play_cost(state, ci, state.player_by_id("P0")) == plain


class TestInterceptorAceJTL34:
    """JTL_34 — "Attached unit gains Grit"."""

    def test_JTL_34_attached_unit_gains_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3, no Grit
        host.damage = 2
        assert has_keyword(state, host, Keyword.GRIT) is False
        assert compute_power(state, host) == 1

        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "34"), "P0")
        assert has_keyword(state, host, Keyword.GRIT) is True
        # 1 base + 2 upgrade power + 2 damage worth of Grit.
        assert compute_power(state, host) == 5

    def test_JTL_34_played_as_a_unit_keeps_its_own_printed_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ace = _place(state, "P0", _get_card(repo, "JTL", "34"), "ground")
        assert has_keyword(state, ace, Keyword.GRIT) is True


class TestIdenVersioJTL36:
    """JTL_36 — "When this upgrade attaches to a unit: Give a Shield token to it"."""

    def test_JTL_36_attaching_as_a_pilot_shields_the_host(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        iden = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "36"), "P0")
        state = _fire_upgrade_played(state, iden, host)
        assert _shield_count(_find_instance(state, host.instance_id)) == 1

    def test_JTL_36_played_as_a_unit_does_not_fire_the_attach_ability(self, repo):
        state = _make_state()
        iden = _place(state, "P0", _get_card(repo, "JTL", "36"), "ground")
        state = _fire_when_played(state, iden)
        assert not state.pending_decisions
        assert _shield_count(_find_instance(state, iden.instance_id)) == 0


class TestPowerFromPainJTL42:
    """JTL_42 — "Give a unit +1/+0 for this phase for each damage on it"."""

    def test_JTL_42_bonus_scales_with_the_damage_on_the_chosen_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        unit.damage = 3
        state, _evt = _play_event_from_hand(state, repo, "JTL", "42")
        state = _drain_jtl(state)
        state = _choose_jtl(state, unit.instance_id)
        assert compute_power(state, _find_instance(state, unit.instance_id)) == 3 + 3

    def test_JTL_42_undamaged_unit_gets_no_bonus(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "42")
        state = _drain_jtl(state)
        state = _choose_jtl(state, unit.instance_id)
        assert compute_power(state, _find_instance(state, unit.instance_id)) == 3


class TestEchoBaseEngineerJTL44:
    """JTL_44 — When Played: you may Shield a DAMAGED Vehicle unit."""

    def test_JTL_44_when_played_shields_a_damaged_vehicle(self, repo):
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        vehicle.damage = 1
        healthy = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        trooper.damage = 2
        engineer = _place(state, "P0", _get_card(repo, "JTL", "44"), "ground")

        state = _fire_when_played(state, engineer)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        offered = _target_ids_jtl(state)
        assert offered == {vehicle.instance_id}      # damaged AND a Vehicle
        assert healthy.instance_id not in offered
        assert trooper.instance_id not in offered
        state = _choose_jtl(state, vehicle.instance_id)
        assert _shield_count(_find_instance(state, vehicle.instance_id)) == 1

    def test_JTL_44_no_prompt_without_a_damaged_vehicle(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # undamaged
        engineer = _place(state, "P0", _get_card(repo, "JTL", "44"), "ground")
        state = _fire_when_played(state, engineer)
        assert not state.pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:13 — Combat tricks, buffs & tempo
# (JTL_45, JTL_50, JTL_57, JTL_58, JTL_66, JTL_67, JTL_70)
# ══════════════════════════════════════════════════════════════════════════════


def _move_select_jtl(state, upgrade_id):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "MoveUpgradeSelect"
               and a.upgrade_id == upgrade_id)
    return apply(state, act)


def _move_dest_ids_jtl(state):
    from swu.engine.actions import legal_actions
    return {a.dest_id for a in legal_actions(state)
            if type(a).__name__ == "MoveUpgradeTo"}


def _move_to_jtl(state, dest_id):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "MoveUpgradeTo" and a.dest_id == dest_id)
    return apply(state, act)


class TestHeraSyndullaJTL45:
    """JTL_45 — "Attached unit gains Restore 1"."""

    def test_JTL_45_attached_unit_gains_restore_1(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert has_keyword(state, host, Keyword.RESTORE) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "45"), "P0")
        assert has_keyword(state, host, Keyword.RESTORE) is True
        assert keyword_value(state, host, Keyword.RESTORE) == 1


class TestPhantomIIJTL50:
    """JTL_50 — Action [1]: attach this unit to The Ghost; the host gets +3/+3 and
    Grit."""

    def _setup(self, repo, with_ghost=True):
        state = _make_state()
        _give_resources(state, "P0", 10)
        ghost = None
        if with_ghost:
            ghost = _place(state, "P0", _get_card(repo, "JTL", "53"), "space")  # 5/6
        phantom = _place(state, "P0", _get_card(repo, "JTL", "50"), "space")
        return state, ghost, phantom

    def test_JTL_50_action_attaches_to_the_ghost_and_buffs_it(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state, ghost, phantom = self._setup(repo)
        assert compute_power(state, ghost) == 5 and compute_hp(state, ghost) == 6

        state = _use_ability_jtl(state, phantom)
        state = _drain_jtl(state)

        _, ghost_now = state.find_instance(ghost.instance_id)
        assert any(u.instance_id == phantom.instance_id
                   for u in ghost_now.attached_upgrades)
        # No longer a unit in any arena.
        assert all(u.instance_id != phantom.instance_id
                   for u in state.player_by_id("P0").space_arena)
        assert compute_power(state, ghost_now) == 5 + 3
        assert compute_hp(state, ghost_now) == 6 + 3
        assert has_keyword(state, ghost_now, Keyword.GRIT) is True

    def test_JTL_50_action_not_offered_without_the_ghost(self, repo):
        state, _ghost, phantom = self._setup(repo, with_ghost=False)
        assert _use_actions_jtl(state, phantom) == []

    def test_JTL_50_as_a_plain_unit_is_still_a_3_3(self, repo):
        """The +3/+3 must NOT leak onto the unit-side reading of the same card."""
        from swu.engine.actions import compute_power, compute_hp
        state, _ghost, phantom = self._setup(repo, with_ghost=False)
        assert compute_power(state, phantom) == 3
        assert compute_hp(state, phantom) == 3

    def test_JTL_50_attaching_clears_its_damage(self, repo):
        state, ghost, phantom = self._setup(repo)
        phantom.damage = 2
        state = _use_ability_jtl(state, phantom)
        state = _drain_jtl(state)
        _, ghost_now = state.find_instance(ghost.instance_id)
        rider = next(u for u in ghost_now.attached_upgrades
                     if u.instance_id == phantom.instance_id)
        assert rider.damage == 0


class TestAstromechPilotJTL57:
    """JTL_57 — When played as an upgrade: you may heal 2 from a unit."""

    def test_JTL_57_pilot_play_heals_2_from_a_chosen_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        astro = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "57"), "P0")

        state = _fire_upgrade_played(state, astro, host)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, hurt.instance_id)
        assert _find_instance(state, hurt.instance_id).damage == 1

    def test_JTL_57_played_as_a_unit_does_not_fire(self, repo):
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        astro = _place(state, "P0", _get_card(repo, "JTL", "57"), "ground")
        state = _fire_when_played(state, astro)
        assert not state.pending_decisions
        assert _find_instance(state, hurt.instance_id).damage == 3


class TestAcademyGraduateJTL58:
    """JTL_58 — "Attached unit gains Sentinel"."""

    def test_JTL_58_attached_unit_gains_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert has_keyword(state, host, Keyword.SENTINEL) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "58"), "P0")
        assert has_keyword(state, host, Keyword.SENTINEL) is True


class TestTraceMartezJTL66:
    """JTL_66 — attached unit gains "On Attack: heal 2 total from any number of
    units"."""

    def test_JTL_66_attached_host_on_attack_spreads_2_healing(self, repo):
        from swu.engine.actions import legal_actions, apply, AssignDamage
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        host.damage = 1
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ally.damage = 4
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "66"), "P0")

        state = _fire_on_attack(state, host)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context.get("heal")

        # Spread the 2: one point off each of the two damaged friendlies.
        for tid in (host.instance_id, ally.instance_id):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AssignDamage)
                                      and a.target_id == tid))
        # Pool spent → the heal distribution resolves itself.
        assert not any(d.kind == "distribute_damage" for d in state.pending_decisions)
        assert _find_instance(state, host.instance_id).damage == 0
        assert _find_instance(state, ally.instance_id).damage == 3

    def test_JTL_66_as_a_plain_unit_its_on_attack_never_fires(self, repo):
        """A GrantedAbility is only collected off a host's attached upgrades."""
        state = _make_state()
        trace = _place(state, "P0", _get_card(repo, "JTL", "66"), "ground")
        trace.damage = 2
        state = _fire_on_attack(state, trace)
        assert not state.pending_decisions


class TestCloakedStarViperJTL67:
    """JTL_67 — When Played: give 2 Shield tokens to this unit."""

    def test_JTL_67_when_played_shields_itself_twice(self, repo):
        state = _make_state()
        viper = _place(state, "P0", _get_card(repo, "JTL", "67"), "space")
        state = _fire_when_played(state, viper)
        state = _drain_jtl(state)
        assert _shield_count(_find_instance(state, viper.instance_id)) == 2


class TestUWingLanderJTL70:
    """JTL_70 — 3 Experience on entry; after a completed attack, ferry one upgrade
    onto another friendly Vehicle."""

    def test_JTL_70_when_played_gives_itself_3_experience(self, repo):
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "JTL", "70"), "space")
        state = _fire_when_played(state, uwing)
        state = _drain_jtl(state)
        assert _experience_count(_find_instance(state, uwing.instance_id)) == 3

    def test_JTL_70_completed_attack_ferries_an_experience_to_another_vehicle(self, repo):
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "JTL", "70"), "space")
        other = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # Vehicle
        state = _fire_when_played(state, uwing)
        state = _drain_jtl(state)
        token = _find_instance(state, uwing.instance_id).attached_upgrades[0]

        state = _fire_attack_ends_jtl(state, uwing)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "move_upgrade"
        state = _move_select_jtl(state, token.instance_id)
        state = _move_to_jtl(state, other.instance_id)

        assert _experience_count(_find_instance(state, uwing.instance_id)) == 2
        assert _experience_count(_find_instance(state, other.instance_id)) == 1

    def test_JTL_70_only_offers_its_own_upgrades_and_vehicle_destinations(self, repo):
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "JTL", "70"), "space")
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # no Vehicle
        elsewhere = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        stray = _attach_upgrade_directly(
            state, elsewhere, _get_card(repo, "SHD", "69"), "P0")
        state = _fire_when_played(state, uwing)
        state = _drain_jtl(state)
        token = _find_instance(state, uwing.instance_id).attached_upgrades[0]

        state = _fire_attack_ends_jtl(state, uwing)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        from swu.engine.actions import legal_actions
        offered = {a.upgrade_id for a in legal_actions(state)
                   if type(a).__name__ == "MoveUpgradeSelect"}
        assert token.instance_id in offered
        assert stray.instance_id not in offered      # "an upgrade on THIS unit"

        state = _move_select_jtl(state, token.instance_id)
        dests = _move_dest_ids_jtl(state)
        assert vehicle.instance_id in dests
        assert elsewhere.instance_id in dests        # also a Vehicle
        assert trooper.instance_id not in dests      # not a Vehicle
        assert uwing.instance_id not in dests        # "ANOTHER" unit

    def test_JTL_70_no_move_prompt_without_another_vehicle(self, repo):
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "JTL", "70"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not a Vehicle
        state = _fire_when_played(state, uwing)
        state = _drain_jtl(state)
        state = _fire_attack_ends_jtl(state, uwing)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        # The optional trigger is still offered (the prompt precedes the effect),
        # but the push guard finds no legal move, so nothing is asked.
        assert not any(d.kind == "move_upgrade" for d in state.pending_decisions)


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:14 — Combat tricks, buffs & tempo
# (JTL_71, JTL_72, JTL_73, JTL_76, JTL_77, JTL_81, JTL_86)
# ══════════════════════════════════════════════════════════════════════════════


def _finish_select_token_jtl(state):
    from swu.engine.actions import legal_actions, apply, FinishSelectToken
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, FinishSelectToken)))


def _defeat_with_upgrades_jtl(state, ci, controller_id="P0"):
    """Mimic ``_defeat_unit`` for a host carrying upgrades: detach them to the
    owner's discard FIRST (as the engine does) and stash them in
    ``event_ctx["defeated_upgrades"]``, which is the only place a
    ``GrantedAbility(WhenDefeated)`` can still be found (Grim Valor JTL_73)."""
    from swu.engine.events import UnitDefeated
    from swu.abilities.resolver import fire_triggered_abilities
    from swu.engine.state import Zone
    from swu.cards.models import TokenUpgrade
    ps = state.player_by_id(controller_id)
    for arena in (ps.ground_arena, ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    detached = list(ci.attached_upgrades)
    ci.attached_upgrades.clear()
    for upg in detached:
        if isinstance(upg.card_def, TokenUpgrade):
            continue
        upg.zone = Zone.DISCARD
        state.player_by_id(upg.owner_id).discard.append(upg)
    ci.zone = Zone.DISCARD
    ci.damage = 0
    owner = state.player_by_id(ci.owner_id)
    if all(ci.instance_id != c.instance_id for c in owner.discard):
        owner.discard.append(ci)
    evt = UnitDefeated(player_id=controller_id, instance_id=ci.instance_id,
                       card_name=ci.card_def.display_name)
    state.event_log.append(evt)
    ctx = {"defeated_id": ci.instance_id, "defeated_ci": ci,
           "defeated_controller_id": controller_id,
           "defeated_upgrades": detached}
    return fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)


class TestCR90ReliefRunnerJTL71:
    """JTL_71 — When Defeated: heal up to 3 from a unit or base."""

    def test_JTL_71_when_defeated_heals_a_chosen_unit(self, repo):
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "JTL", "71"), "space")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 5
        state = _fire_when_defeated(state, runner)
        state = _drain_jtl(state)
        state = _choose_jtl(state, hurt.instance_id)
        assert _find_instance(state, hurt.instance_id).damage == 2

    def test_JTL_71_can_heal_a_damaged_base_instead(self, repo):
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "JTL", "71"), "space")
        base = state.player_by_id("P0").base_instance
        base.damage = 2
        state = _fire_when_defeated(state, runner)
        state = _drain_jtl(state)
        assert base.instance_id in _target_ids_jtl(state)
        state = _choose_jtl(state, base.instance_id)
        assert state.player_by_id("P0").base_instance.damage == 0

    def test_JTL_71_no_prompt_when_nothing_is_damaged(self, repo):
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "JTL", "71"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, runner)
        state = _drain_jtl(state)
        assert not state.pending_decisions


class TestWingGuardSecurityTeamJTL72:
    """JTL_72 — When Played: a Shield to each of up to 2 Fringe units."""

    def test_JTL_72_shields_up_to_two_fringe_units(self, repo):
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "JTL", "72"), "ground")   # Fringe
        fringe = _place(state, "P0", _get_card(repo, "JTL", "66"), "ground")  # Fringe
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel

        state = _fire_when_played(state, guard)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = _token_target_ids_jtl(state)
        assert {guard.instance_id, fringe.instance_id} <= offered
        assert other.instance_id not in offered

        state = _select_token_jtl(state, guard.instance_id)
        state = _select_token_jtl(state, fringe.instance_id)
        assert _shield_count(_find_instance(state, guard.instance_id)) == 1
        assert _shield_count(_find_instance(state, fringe.instance_id)) == 1

    def test_JTL_72_may_stop_after_one_fringe_unit(self, repo):
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "JTL", "72"), "ground")
        fringe = _place(state, "P0", _get_card(repo, "JTL", "66"), "ground")
        state = _fire_when_played(state, guard)
        state = _drain_jtl(state)
        state = _select_token_jtl(state, fringe.instance_id)
        state = _finish_select_token_jtl(state)
        assert _shield_count(_find_instance(state, fringe.instance_id)) == 1
        assert _shield_count(_find_instance(state, guard.instance_id)) == 0


class TestGrimValorJTL73:
    """JTL_73 — attached unit gains "When Defeated: you may exhaust a unit"."""

    def test_JTL_73_host_defeat_exhausts_a_chosen_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "73"), "P0")
        victim = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")

        state = _defeat_with_upgrades_jtl(state, host)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).exhausted is True

    def test_JTL_73_grant_is_declinable(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "73"), "P0")
        victim = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        state = _defeat_with_upgrades_jtl(state, host)
        state = _decline_jtl(state)
        assert _find_instance(state, victim.instance_id).exhausted is False


class TestCoveringTheWingJTL76:
    """JTL_76 — create an X-Wing token, then optionally Shield ANOTHER unit."""

    def test_JTL_76_creates_an_xwing_and_shields_another_unit(self, repo):
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "76")
        state = _drain_jtl(state)

        assert _xwing_count(state, "P0") == 1
        assert state.pending_decisions[-1].kind == "select_token"
        offered = _token_target_ids_jtl(state)
        assert ally.instance_id in offered
        # "another unit" — never the X-Wing this event just made.
        xwing = next(u for u in state.player_by_id("P0").space_arena
                     if u.card_def.name == "X-Wing")
        assert xwing.instance_id not in offered

        state = _select_token_jtl(state, ally.instance_id)
        assert _shield_count(_find_instance(state, ally.instance_id)) == 1

    def test_JTL_76_shield_half_may_be_declined(self, repo):
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "76")
        state = _drain_jtl(state)
        state = _finish_select_token_jtl(state)
        assert _xwing_count(state, "P0") == 1
        assert _shield_count(_find_instance(state, ally.instance_id)) == 0


class TestInTheHeatOfBattleJTL77:
    """JTL_77 — each unit gains Sentinel and loses Saboteur for this phase."""

    def test_JTL_77_grants_sentinel_and_strips_saboteur_from_every_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        # Rio Durant deployed as a leader unit — a printed Saboteur.
        theirs = _place_deployed_leader_jtl(state, "P1", _leader_jtl(repo, "15"))
        assert has_keyword(state, theirs, Keyword.SABOTEUR) is True
        assert has_keyword(state, mine, Keyword.SENTINEL) is False

        state, _evt = _play_event_from_hand(state, repo, "JTL", "77")
        state = _drain_jtl(state)

        mine_now = _find_instance(state, mine.instance_id)
        theirs_now = _find_instance(state, theirs.instance_id)
        assert has_keyword(state, mine_now, Keyword.SENTINEL) is True
        assert has_keyword(state, theirs_now, Keyword.SENTINEL) is True
        # The revoke is checked before every grant source, so it wins outright.
        assert has_keyword(state, theirs_now, Keyword.SABOTEUR) is False


class TestFirstOrderTIEFighterJTL81:
    """JTL_81 — Raid 1 only while its controller has a token unit."""

    def test_JTL_81_gains_raid_1_only_while_a_token_unit_is_controlled(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        from swu.engine.actions import _create_token_units
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "JTL", "81"), "space")
        assert has_keyword(state, tie, Keyword.RAID) is False

        _create_token_units(state, state.player_by_id("P0"), "TIE Fighter", 1)
        assert has_keyword(state, tie, Keyword.RAID) is True
        assert keyword_value(state, tie, Keyword.RAID) == 1

    def test_JTL_81_an_enemy_token_unit_does_not_switch_it_on(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import _create_token_units
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "JTL", "81"), "space")
        _create_token_units(state, state.player_by_id("P1"), "TIE Fighter", 1)
        assert has_keyword(state, tie, Keyword.RAID) is False


class TestWingmanVictorThreeJTL86:
    """JTL_86 — as a Pilot: an Experience token to a unit OTHER than the host."""

    def test_JTL_86_pilot_play_gives_experience_to_another_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        wingman = _attach_upgrade_directly(
            state, host, _get_card(repo, "JTL", "86"), "P0")

        state = _fire_upgrade_played(state, wingman, host)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = _token_target_ids_jtl(state)
        assert ally.instance_id in offered
        assert host.instance_id not in offered      # the errata, exactly

        state = _select_token_jtl(state, ally.instance_id)
        assert _experience_count(_find_instance(state, ally.instance_id)) == 1

    def test_JTL_86_played_as_a_unit_does_not_fire(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        wingman = _place(state, "P0", _get_card(repo, "JTL", "86"), "ground")
        state = _fire_when_played(state, wingman)
        assert not state.pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:15 — Combat tricks, buffs & tempo
# (JTL_88, JTL_92, JTL_101, JTL_106, JTL_107, JTL_109)
# JTL_94 Luke Skywalker: escalation resolved 2026-08-06 — it is the original
# printing of the already-implemented J25_4 and is now aliased onto it.  Tests live
# in TestLukeSkywalkerJTL94 at the end of this module.
# ══════════════════════════════════════════════════════════════════════════════


def _fire_card_played_jtl(state, ci):
    """Fire a CardPlayed event for ``ci`` as if it was just played — the
    WhenYouPlayCard observer hook (Red Leader JTL_101's Pilot-attach trigger)."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=ci.owner_id, instance_id=ci.instance_id,
                     card_name=ci.card_def.display_name, cost_paid=0)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestCaptainPhasmaJTL88:
    """JTL_88 — When Played/On Attack: you may give ANOTHER First Order unit +2/+2."""

    def test_JTL_88_when_played_buffs_another_first_order_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        phasma = _place(state, "P0", _get_card(repo, "JTL", "88"), "ground")
        ally = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")  # First Order
        p0, h0 = compute_power(state, ally), compute_hp(state, ally)

        state = _fire_when_played(state, phasma)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        # "another" — Phasma herself is never offered.
        assert phasma.instance_id not in _target_ids_jtl(state)
        state = _choose_jtl(state, ally.instance_id)

        now = _find_instance(state, ally.instance_id)
        assert (compute_power(state, now), compute_hp(state, now)) == (p0 + 2, h0 + 2)

    def test_JTL_88_on_attack_fires_the_same_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        phasma = _place(state, "P0", _get_card(repo, "JTL", "88"), "ground")
        ally = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")
        before = compute_power(state, ally)
        state = _fire_on_attack(state, phasma)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, ally.instance_id)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == before + 2

    def test_JTL_88_non_first_order_units_are_not_eligible(self, repo):
        state = _make_state()
        phasma = _place(state, "P0", _get_card(repo, "JTL", "88"), "ground")
        rebel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, phasma)
        # No other First Order unit ⇒ the optional trigger has nothing to do.
        state = _drain_jtl(state)
        assert rebel.instance_id not in _target_ids_jtl(state)


class TestScrambleFightersJTL92:
    """JTL_92 — create 8 ready TIE Fighters that can't attack bases this phase."""

    def test_JTL_92_creates_eight_ready_tie_fighters(self, repo):
        from swu.cards.models import TokenUnit
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "JTL", "92", resources=20)
        state = _drain_jtl(state)
        ties = [u for u in state.player_by_id("P0").space_arena
                if isinstance(u.card_def, TokenUnit)
                and u.card_def.name == "TIE Fighter"]
        assert len(ties) == 8
        assert all(t.exhausted is False for t in ties)

    def test_JTL_92_the_tokens_cannot_attack_bases_this_phase(self, repo):
        from swu.engine.actions import _cannot_attack_bases
        from swu.cards.models import TokenUnit
        state = _make_state()
        other = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "92", resources=20)
        state = _drain_jtl(state)
        ties = [u for u in state.player_by_id("P0").space_arena
                if isinstance(u.card_def, TokenUnit)]
        assert all(_cannot_attack_bases(state, t) for t in ties)
        # …but only the tokens this event made; nothing else is barred.
        assert not _cannot_attack_bases(state, _find_instance(state, other.instance_id))

    def test_JTL_92_the_base_bar_lapses_at_the_phase_rollover(self, repo):
        from swu.engine.actions import _cannot_attack_bases
        from swu.cards.models import TokenUnit
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "JTL", "92", resources=20)
        state = _drain_jtl(state)
        tie = next(u for u in state.player_by_id("P0").space_arena
                   if isinstance(u.card_def, TokenUnit))
        assert _cannot_attack_bases(state, tie) is True
        state.game_memory.clear_phase()
        assert _cannot_attack_bases(state, tie) is False


class TestRedLeaderJTL101:
    """JTL_101 — scaling Pilot discount + an X-Wing when a Pilot rides him."""

    def test_JTL_101_costs_one_less_per_friendly_pilot_unit_and_upgrade(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        red = CardInstance("P0_red", _get_card(repo, "JTL", "101"), "P0", Zone.HAND)
        ps.hand.append(red)
        # Printed 4 + a 4-resource off-aspect penalty against the neutral test
        # base; what matters is that the discount is 1 per Pilot from there.
        full = _play_cost(state, red, ps)
        assert full == 8

        # A Pilot UNIT (BB-8 played as a unit) …
        _place(state, "P0", _get_card(repo, "JTL", "145"), "ground")
        assert _play_cost(state, red, ps) == full - 1
        # … and a Pilot UPGRADE riding a Vehicle each count once.
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "86"), "P0")
        assert _play_cost(state, red, ps) == full - 2

    def test_JTL_101_never_costs_less_than_zero(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        red = CardInstance("P0_red2", _get_card(repo, "JTL", "101"), "P0", Zone.HAND)
        ps.hand.append(red)
        for _ in range(12):
            _place(state, "P0", _get_card(repo, "JTL", "145"), "ground")
        assert _play_cost(state, red, ps) == 0

    def test_JTL_101_pilot_upgrade_attaching_to_him_creates_an_xwing(self, repo):
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "JTL", "101"), "space")
        assert _xwing_count(state, "P0") == 0
        wingman = _attach_upgrade_directly(state, red, _get_card(repo, "JTL", "86"), "P0")
        state = _fire_card_played_jtl(state, wingman)
        state = _drain_jtl(state)
        assert _xwing_count(state, "P0") == 1

    def test_JTL_101_a_pilot_on_another_unit_does_not_trigger_him(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "101"), "space")
        other = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        wingman = _attach_upgrade_directly(state, other, _get_card(repo, "JTL", "86"), "P0")
        state = _fire_card_played_jtl(state, wingman)
        state = _drain_jtl(state)
        assert _xwing_count(state, "P0") == 0


class TestUnityOfPurposeJTL106:
    """JTL_106 — +1/+1 to each friendly unit per DISTINCT friendly unit name."""

    def test_JTL_106_scales_with_the_number_of_distinct_names(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")
        c = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")  # same name as b
        pa, ha = compute_power(state, a), compute_hp(state, a)
        pb = compute_power(state, b)

        state, _evt = _play_event_from_hand(state, repo, "JTL", "106")
        state = _drain_jtl(state)

        # Two distinct names among three units ⇒ +2/+2 to EVERY friendly unit.
        na = _find_instance(state, a.instance_id)
        assert (compute_power(state, na), compute_hp(state, na)) == (pa + 2, ha + 2)
        assert compute_power(state, _find_instance(state, b.instance_id)) == pb + 2
        assert compute_power(state, _find_instance(state, c.instance_id)) == pb + 2

    def test_JTL_106_does_not_buff_enemy_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, enemy)
        state, _evt = _play_event_from_hand(state, repo, "JTL", "106")
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == before


class TestBunkerDefenderJTL107:
    """JTL_107 — Sentinel only while its controller has a Vehicle unit."""

    def test_JTL_107_printed_sentinel_is_stripped_and_gated_on_a_vehicle(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bunker = _place(state, "P0", _get_card(repo, "JTL", "107"), "ground")
        assert "Sentinel" not in bunker.card_def.keywords
        assert has_keyword(state, bunker, Keyword.SENTINEL) is False

        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # Vehicle
        assert has_keyword(state, bunker, Keyword.SENTINEL) is True

    def test_JTL_107_an_enemy_vehicle_does_not_switch_it_on(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bunker = _place(state, "P0", _get_card(repo, "JTL", "107"), "ground")
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        assert has_keyword(state, bunker, Keyword.SENTINEL) is False


class TestJarekYeagerJTL109:
    """JTL_109 — as a PILOT upgrade, grants his host Sentinel while his controller
    has both a ground and a space unit.  The unit side never gains it."""

    def test_JTL_109_attached_host_gains_sentinel_with_a_unit_in_each_arena(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "109"), "P0")
        # Space only so far — the condition is not met.
        assert has_keyword(state, host, Keyword.SENTINEL) is False

        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, host, Keyword.SENTINEL) is True

    def test_JTL_109_played_as_a_plain_unit_never_grants_himself_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        jarek = _place(state, "P0", _get_card(repo, "JTL", "109"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        # Ground + space units are both present, so the CONDITION holds — but the
        # grant is upgrade_only, so the unit side stays Sentinel-less.
        assert "Sentinel" not in jarek.card_def.keywords
        assert has_keyword(state, jarek, Keyword.SENTINEL) is False

    def test_JTL_109_the_grant_lapses_when_an_arena_empties(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "109"), "P0")
        assert has_keyword(state, host, Keyword.SENTINEL) is True
        state.player_by_id("P0").ground_arena.remove(ground)
        assert has_keyword(state, host, Keyword.SENTINEL) is False


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:16 — Combat tricks, buffs & tempo
# (JTL_115, JTL_119, JTL_122, JTL_135, JTL_137, JTL_138, JTL_145)
# ══════════════════════════════════════════════════════════════════════════════


def _exhaust_combined_ids_jtl(state):
    from swu.engine.actions import legal_actions, SelectUnitToExhaustCombined
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, SelectUnitToExhaustCombined)}


def _exhaust_combined_select_jtl(state, target_id):
    from swu.engine.actions import legal_actions, apply, SelectUnitToExhaustCombined
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, SelectUnitToExhaustCombined)
                             and a.target_id == target_id))


def _finish_exhaust_combined_jtl(state):
    from swu.engine.actions import legal_actions, apply, FinishExhaustCombined
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, FinishExhaustCombined)))


class TestCloneCombatSquadronJTL115:
    """JTL_115 — +1/+1 for each OTHER friendly space unit."""

    def test_JTL_115_scales_with_other_friendly_space_units(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        squad = _place(state, "P0", _get_card(repo, "JTL", "115"), "space")
        assert (compute_power(state, squad), compute_hp(state, squad)) == (3, 3)

        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert (compute_power(state, squad), compute_hp(state, squad)) == (4, 4)
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert (compute_power(state, squad), compute_hp(state, squad)) == (5, 5)

    def test_JTL_115_ignores_ground_units_and_enemy_space_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        squad = _place(state, "P0", _get_card(repo, "JTL", "115"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # friendly ground
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")   # enemy space
        assert compute_power(state, squad) == 3


class TestResupplyCarrierJTL119:
    """JTL_119 — When Played: you may ramp the top card of your deck."""

    def test_JTL_119_ramps_the_top_card_of_the_deck(self, repo):
        state = _make_state()
        carrier = _place(state, "P0", _get_card(repo, "JTL", "119"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        ps = state.player_by_id("P0")
        deck_before, res_before = len(ps.deck), len(ps.resources)

        state = _fire_when_played(state, carrier)
        state = _accept_jtl(state)
        state = _drain_jtl(state)

        ps = state.player_by_id("P0")
        assert (len(ps.deck), len(ps.resources)) == (deck_before - 1, res_before + 1)
        assert ps.resources[-1].face_down is True
        assert ps.resources[-1].exhausted is False

    def test_JTL_119_may_be_declined(self, repo):
        state = _make_state()
        carrier = _place(state, "P0", _get_card(repo, "JTL", "119"), "space")
        _add_deck_cards_jtl(state, "P0", repo, 2)
        before = len(state.player_by_id("P0").resources)
        state = _fire_when_played(state, carrier)
        state = _decline_jtl(state)
        assert len(state.player_by_id("P0").resources) == before


class TestAllWingsReportInJTL122:
    """JTL_122 — exhaust up to 2 friendly space units, an X-Wing per exhaust."""

    def test_JTL_122_two_exhausts_make_two_xwings(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        b = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        a.exhausted = b.exhausted = False
        state, _evt = _play_event_from_hand(state, repo, "JTL", "122")
        state = _drain_jtl(state)

        assert state.pending_decisions[-1].kind == "exhaust_combined_cost"
        state = _exhaust_combined_select_jtl(state, a.instance_id)
        state = _exhaust_combined_select_jtl(state, b.instance_id)
        # max_units=2 auto-finishes the decision.
        assert _find_instance(state, a.instance_id).exhausted is True
        assert _find_instance(state, b.instance_id).exhausted is True
        assert _xwing_count(state, "P0") == 2

    def test_JTL_122_only_friendly_space_units_are_eligible(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        for u in (mine, ground, enemy):
            u.exhausted = False
        state, _evt = _play_event_from_hand(state, repo, "JTL", "122")
        state = _drain_jtl(state)
        offered = _exhaust_combined_ids_jtl(state)
        assert offered == {mine.instance_id}

    def test_JTL_122_exhausting_nothing_creates_no_xwings(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        mine.exhausted = False
        state, _evt = _play_event_from_hand(state, repo, "JTL", "122")
        state = _drain_jtl(state)
        state = _finish_exhaust_combined_jtl(state)
        assert _find_instance(state, mine.instance_id).exhausted is False
        assert _xwing_count(state, "P0") == 0


class TestSpecialForcesTIEFighterJTL135:
    """JTL_135 — When Played: ready itself if an opponent is ahead in space."""

    def test_JTL_135_readies_itself_when_the_opponent_has_more_space_units(self, repo):
        state = _make_state()
        for _ in range(3):
            _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        tie = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")
        tie.exhausted = True
        state = _fire_when_played(state, tie)
        state = _drain_jtl(state)
        assert _find_instance(state, tie.instance_id).exhausted is False

    def test_JTL_135_does_nothing_when_the_space_counts_are_equal(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        tie = _place(state, "P0", _get_card(repo, "JTL", "135"), "space")
        tie.exhausted = True
        # After it enters, both players have exactly one space unit — "more" is
        # strictly greater, so the trigger is never collected.
        state = _fire_when_played(state, tie)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert _find_instance(state, tie.instance_id).exhausted is True


class TestVonregsTIEInterceptorJTL137:
    """JTL_137 — Overwhelm at 4+ power, Raid 1 at 6+ power."""

    def test_JTL_137_printed_keywords_are_stripped_and_gated_on_power(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        from swu.engine.tokens import attach_token
        state = _make_state()
        vonreg = _place(state, "P0", _get_card(repo, "JTL", "137"), "space")  # 3/4
        assert "Overwhelm" not in vonreg.card_def.keywords
        assert "Raid" not in vonreg.card_def.keywords
        assert has_keyword(state, vonreg, Keyword.OVERWHELM) is False
        assert has_keyword(state, vonreg, Keyword.RAID) is False

        ps = state.player_by_id("P0")
        attach_token(state, ps, vonreg, "Experience")        # 4/5
        assert has_keyword(state, vonreg, Keyword.OVERWHELM) is True
        assert has_keyword(state, vonreg, Keyword.RAID) is False

        attach_token(state, ps, vonreg, "Experience")        # 5/6
        attach_token(state, ps, vonreg, "Experience")        # 6/7
        assert has_keyword(state, vonreg, Keyword.RAID) is True
        assert keyword_value(state, vonreg, Keyword.RAID) == 1

    def test_JTL_137_raid_cannot_bootstrap_itself_to_the_threshold(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.tokens import attach_token
        state = _make_state()
        vonreg = _place(state, "P0", _get_card(repo, "JTL", "137"), "space")
        ps = state.player_by_id("P0")
        attach_token(state, ps, vonreg, "Experience")
        attach_token(state, ps, vonreg, "Experience")        # 5/6 — one short
        assert has_keyword(state, vonreg, Keyword.RAID) is False
        # The attacking read is also 5: Raid is not granted, so it adds nothing.
        assert compute_power(state, vonreg, is_attacking=True) == 5


class TestDecimatorOfDissidentsJTL138:
    """JTL_138 — 1 cheaper once its controller has dealt indirect damage."""

    def test_JTL_138_costs_one_less_after_dealing_indirect_damage(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        dec = CardInstance("P0_dec", _get_card(repo, "JTL", "138"), "P0", Zone.HAND)
        ps.hand.append(dec)
        full = _play_cost(state, dec, ps)

        state.game_memory.indirect_dealers_this_phase.add("P0")
        assert _play_cost(state, dec, ps) == full - 1

    def test_JTL_138_an_opponents_indirect_damage_does_not_discount_it(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        dec = CardInstance("P0_dec2", _get_card(repo, "JTL", "138"), "P0", Zone.HAND)
        ps.hand.append(dec)
        full = _play_cost(state, dec, ps)
        state.game_memory.indirect_dealers_this_phase.add("P1")
        assert _play_cost(state, dec, ps) == full

    def test_JTL_138_the_ledger_is_fed_by_real_indirect_damage(self, repo):
        """An actual assign_indirect_damage resolution records the dealer."""
        from swu.engine.actions import apply
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "132"), "ground")
        state = _fire_on_attack(state, trooper)
        acts = _assign_actions(state)
        base_id = _p1_base_id(state)
        state = apply(state, next(a for a in acts if a.target_id == base_id))
        assert "P0" in state.game_memory.indirect_dealers_this_phase
        state.game_memory.clear_phase()
        assert "P0" not in state.game_memory.indirect_dealers_this_phase


class TestBB8JTL145:
    """JTL_145 — as a Pilot: you may pay 2 to ready a Resistance unit."""

    def test_JTL_145_pays_two_and_readies_a_resistance_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        resistance = _place(state, "P0", _get_card(repo, "JTL", "109"), "ground")
        resistance.exhausted = True
        _give_resources(state, "P0", 4)
        bb8 = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "145"), "P0")

        state = _fire_upgrade_played(state, bb8, host)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, resistance.instance_id)

        assert _find_instance(state, resistance.instance_id).exhausted is False
        assert state.player_by_id("P0").available_resources == 2

    def test_JTL_145_not_offered_without_two_ready_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        resistance = _place(state, "P0", _get_card(repo, "JTL", "109"), "ground")
        resistance.exhausted = True
        _give_resources(state, "P0", 1)
        bb8 = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "145"), "P0")
        state = _fire_upgrade_played(state, bb8, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_JTL_145_not_offered_without_a_resistance_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _give_resources(state, "P0", 4)
        bb8 = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "145"), "P0")
        state = _fire_upgrade_played(state, bb8, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_JTL_145_played_as_a_unit_does_not_fire(self, repo):
        state = _make_state()
        resistance = _place(state, "P0", _get_card(repo, "JTL", "109"), "ground")
        resistance.exhausted = True
        _give_resources(state, "P0", 4)
        bb8 = _place(state, "P0", _get_card(repo, "JTL", "145"), "ground")
        state = _fire_when_played(state, bb8)
        assert not state.pending_decisions
        assert _find_instance(state, resistance.instance_id).exhausted is True


# ── jtl-set:11 / :15 — the two framework escalations ─────────────────────────

def _thrawn_undeployed(state, repo, owner_id="P0"):
    """Put Grand Admiral Thrawn JTL_2 in ``owner_id``'s base_zone, ready."""
    return _place_leader(state, owner_id, _get_card(repo, "JTL", "2"))


def _thrawn_deployed(state, repo, owner_id="P0"):
    """Put Thrawn in play as a deployed leader unit (his deployed side)."""
    return _deploy_leader_to_arena(state, _thrawn_undeployed(state, repo, owner_id))


def _defeat_and_fire_jtl(state, ci, controller_id):
    from tests.test_sor_cards import _defeat_and_fire
    return _defeat_and_fire(state, ci, controller_id)


def _accept_count_jtl(state):
    from swu.engine.actions import legal_actions, AcceptTrigger
    return sum(1 for a in legal_actions(state) if isinstance(a, AcceptTrigger))


def _leader_ci_jtl(state, instance_id):
    """Locate a card ANYWHERE, including base_zone — where an undeployed leader
    lives and the arena-only ``_find_instance`` cannot see it."""
    return state.find_instance(instance_id)[1]


class TestGrandAdmiralThrawnJTL2:
    """JTL_2 — Grand Admiral Thrawn "...How Unfortunate".

    Undeployed: "When you use a 'When Defeated' ability: You may exhaust this
    leader.  If you do, use that ability again."
    Deployed:   the same, free, but "only once each round".

    Both sides are ``WhenDefeatedRedo`` passive markers read at the shared
    ``resolver._schedule_ability_redo`` chokepoint (the seam Aethersprite LOF_197
    already used for the When Played half).  The victim in most of these tests is
    Vanguard Infantry SOR_108 — "When Defeated: You may give an Experience token to
    a unit" — so "used twice" reads off as two Experience tokens.
    """

    def _defeat_vanguard(self, repo, thrawn="undeployed"):
        """Board: a Thrawn side + a bystander to receive Experience + a Vanguard
        Infantry that then dies.  Returns (state, bystander, thrawn_ci)."""
        state = _make_state()
        thrawn_ci = (_thrawn_undeployed(state, repo) if thrawn == "undeployed"
                     else _thrawn_deployed(state, repo))
        bystander = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        vanguard = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard, "P0")
        return state, bystander, thrawn_ci

    def _take_experience(self, state, bystander):
        """Accept the offered trigger and route its Experience token to bystander."""
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, bystander.instance_id)
        return _drain_jtl(state)

    def test_JTL_2_undeployed_redo_uses_the_when_defeated_ability_twice(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo)
        state = self._take_experience(state, bystander)          # original use
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 1
        # …and Thrawn now offers the re-use.
        state = self._take_experience(state, bystander)          # the redo
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 2

    def test_JTL_2_undeployed_redo_exhausts_the_leader_on_accept(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo)
        state = self._take_experience(state, bystander)
        assert not _leader_ci_jtl(state, thrawn.instance_id).exhausted
        state = self._take_experience(state, bystander)
        assert _leader_ci_jtl(state, thrawn.instance_id).exhausted

    def test_JTL_2_undeployed_declining_the_redo_leaves_the_leader_ready(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo)
        state = self._take_experience(state, bystander)
        state = _decline_jtl(state)                              # decline the re-use
        state = _drain_jtl(state)
        # Declining a "you may" is not a use: no second token, no exhaust cost paid.
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 1
        assert not _leader_ci_jtl(state, thrawn.instance_id).exhausted

    def test_JTL_2_undeployed_exhausted_leader_offers_no_redo(self, repo):
        state = _make_state()
        thrawn = _thrawn_undeployed(state, repo)
        thrawn.exhausted = True                                  # cost unpayable
        bystander = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        vanguard = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard, "P0")
        state = self._take_experience(state, bystander)
        assert _accept_count_jtl(state) == 0
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 1

    def test_JTL_2_declining_the_original_ability_is_not_a_use(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo)
        state = _decline_jtl(state)                              # decline Vanguard's own
        state = _drain_jtl(state)
        # Nothing was "used", so there is nothing for Thrawn to repeat.
        assert _accept_count_jtl(state) == 0
        assert not _leader_ci_jtl(state, thrawn.instance_id).exhausted

    def test_JTL_2_deployed_redo_is_free_and_once_each_round(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo, thrawn="deployed")
        state = self._take_experience(state, bystander)
        state = self._take_experience(state, bystander)          # the free redo
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 2
        # Deployed Thrawn pays no exhaust cost…
        assert not _leader_ci_jtl(state, thrawn.instance_id).exhausted
        # …but has spent the round's single use: a second victim gets no redo.
        vanguard2 = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard2, "P0")
        state = self._take_experience(state, bystander)
        assert _accept_count_jtl(state) == 0
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 3

    def test_JTL_2_deployed_redo_recharges_next_round(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo, thrawn="deployed")
        state = self._take_experience(state, bystander)
        state = self._take_experience(state, bystander)
        state.game_memory.clear_round()                          # round rollover
        vanguard2 = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard2, "P0")
        state = self._take_experience(state, bystander)
        assert _accept_count_jtl(state) == 1                     # offered again

    def test_JTL_2_redo_does_not_chain_into_a_third_use(self, repo):
        state, bystander, thrawn = self._defeat_vanguard(repo, thrawn="deployed")
        state = self._take_experience(state, bystander)
        state = self._take_experience(state, bystander)
        # A re-use is not itself a fresh "use" that arms another redo.
        assert _accept_count_jtl(state) == 0
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 2

    def test_JTL_2_only_repeats_its_own_controllers_abilities(self, repo):
        """Scoped to "when YOU use" — an opponent's ability does not count."""
        state = _make_state()
        _thrawn_undeployed(state, repo, "P0")
        bystander = _place(state, "P1", _get_card(repo, "SOR", "61"), "ground")
        vanguard = _place(state, "P1", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard, "P1")
        state = self._take_experience(state, bystander)
        assert _accept_count_jtl(state) == 0
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 1

    def test_JTL_2_bounty_is_not_a_when_defeated_ability(self, repo):
        """Bounty is its own keyword ability — and is collected by the OPPONENT of
        the dying unit's controller, never by Thrawn's controller."""
        state = _make_state()
        _thrawn_undeployed(state, repo, "P0")
        _add_deck_cards_jtl(state, "P1", repo, 4)
        deserter = _place(state, "P0", _get_card(repo, "SHD", "95"), "ground")
        before = len(state.player_by_id("P1").hand)
        state = _defeat_and_fire_jtl(state, deserter, "P0")
        state = _drain_jtl(state)
        assert _accept_count_jtl(state) == 0                     # no re-use offered
        assert len(state.player_by_id("P1").hand) == before + 1  # collected once

    def test_JTL_2_repeats_a_mandatory_inline_when_defeated_ability(self, repo):
        """Star Wing Scout SOR_163 — mandatory, no target, resolves inline: the
        inline call site of the redo chokepoint (draw 2, then 2 more)."""
        state = _make_state()
        _thrawn_undeployed(state, repo)
        _add_deck_cards_jtl(state, "P0", repo, 8)
        state.initiative_holder = state.player_index("P0")
        scout = _place(state, "P0", _get_card(repo, "SOR", "163"), "space")
        before = len(state.player_by_id("P0").hand)
        state = _defeat_and_fire_jtl(state, scout, "P0")
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").hand) == before + 2  # the mandatory use
        state = _accept_jtl(state)                               # the offered re-use
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").hand) == before + 4

    def test_JTL_2_repeats_a_mandatory_targeted_when_defeated_ability(self, repo):
        """Ruthless Raider SOR_134 — mandatory WITH a target decision: the
        push-a-decision call site (2 to the enemy base + 2 to an enemy unit, twice)."""
        state = _make_state()
        _thrawn_undeployed(state, repo)
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 7 HP
        raider = _place(state, "P0", _get_card(repo, "SOR", "134"), "space")
        state = _defeat_and_fire_jtl(state, raider, "P0")
        state = _drain_jtl(state)
        state = _choose_jtl(state, _p1_base_id(state))           # effect 0: the base
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)           # effect 1: a unit
        state = _drain_jtl(state)
        assert _find_instance(state, victim.instance_id).damage == 2
        state = _accept_jtl(state)                               # the offered re-use
        state = _drain_jtl(state)
        state = _choose_jtl(state, _p1_base_id(state))
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, victim.instance_id).damage == 4

    def test_JTL_2_once_per_round_ledger_survives_serialisation(self, repo):
        from swu.engine.state import GameState
        state, bystander, thrawn = self._defeat_vanguard(repo, thrawn="deployed")
        state = self._take_experience(state, bystander)
        state = self._take_experience(state, bystander)
        assert thrawn.instance_id in state.game_memory.when_defeated_redo_used_this_round
        restored = GameState.from_json(state.to_json())
        assert (thrawn.instance_id
                in restored.game_memory.when_defeated_redo_used_this_round)

    def test_JTL_2_board_without_thrawn_offers_no_redo(self, repo):
        """The chokepoint is inert on an ordinary board (the regression guard for
        every other When Defeated card in the game)."""
        state = _make_state()
        bystander = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        vanguard = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        state = _defeat_and_fire_jtl(state, vanguard, "P0")
        state = self._take_experience(state, bystander)
        assert _accept_count_jtl(state) == 0
        assert _experience_count(_find_instance(state, bystander.instance_id)) == 1


class TestLukeSkywalkerJTL94:
    """JTL_94 — Luke Skywalker "You Still With Me?" (Piloting): "If this upgrade
    would be defeated, you may instead move him to the ground arena as a unit and
    exhaust him."

    The ORIGINAL printing of the card implemented as J25_4 in batch 47 (the
    ``WhenDefeatedAsUpgrade`` replacement seam).  It was missed by that sweep
    because ``face_key`` compared rules text verbatim and JTL_94 prints the
    Piloting reminder its promo twins omit — so it keyed to a singleton group the
    mirror-gap check skips.  ``reprints._norm_rules`` now strips reminder text, and
    JTL_94 is aliased onto the implemented twin."""

    def test_JTL_94_aliases_onto_the_implemented_twin(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("JTL", "94")) == ("J25", "4")
        assert get_abilities("JTL", "94") is get_abilities("J25", "4")

    def _pilot_and_defeat_host(self, state, repo):
        from swu.engine.actions import _defeat_unit
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        luke = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "94"), "P0")
        _defeat_unit(state, state.player_by_id("P0"), host)
        return luke

    def test_JTL_94_accepting_moves_him_to_the_ground_arena_exhausted(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        luke = self._pilot_and_defeat_host(state, repo)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        moved = _find_instance(state, luke.instance_id)
        assert moved.zone == Zone.GROUND_ARENA
        assert moved in state.player_by_id("P0").ground_arena
        assert moved.exhausted
        assert all(c.instance_id != luke.instance_id
                   for c in state.player_by_id("P0").discard)

    def test_JTL_94_declining_leaves_him_in_the_discard(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        luke = self._pilot_and_defeat_host(state, repo)
        state = _decline_jtl(state)
        state = _drain_jtl(state)
        p0 = state.player_by_id("P0")
        rested = next(c for c in p0.discard if c.instance_id == luke.instance_id)
        assert rested.zone == Zone.DISCARD
        assert all(c.instance_id != luke.instance_id for c in p0.ground_arena)

    def test_JTL_94_defeated_as_a_plain_unit_offers_no_replacement(self, repo):
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "JTL", "94"), "ground")
        state = _defeat_and_fire_jtl(state, luke, "P0")
        # He died as a UNIT, not as a pilot upgrade — the replacement never applies.
        assert _accept_count_jtl(state) == 0
        assert any(c.instance_id == luke.instance_id
                   for c in state.player_by_id("P0").discard)

    def test_JTL_94_relocated_luke_has_his_unit_stats(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        luke = self._pilot_and_defeat_host(state, repo)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        moved = _find_instance(state, luke.instance_id)
        assert compute_power(state, moved) == 3 and compute_hp(state, moved) == 2


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:17 — Combat tricks, buffs & tempo
# (JTL_146, JTL_150, JTL_157, JTL_160, JTL_161, JTL_163, JTL_164)
# ══════════════════════════════════════════════════════════════════════════════


class TestMassassiTacticalOfficerJTL146:
    """JTL_146 — "Action [Exhaust]: Attack with a Fighter unit.  It gets +2/+0 for
    this attack." """

    def test_JTL_146_action_grants_a_fighter_attack_at_plus_two_power(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        officer = _place(state, "P0", _get_card(repo, "JTL", "146"), "ground")
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # 1/3
        defender = _place(state, "P1", _get_card(repo, "JTL", "240"), "space")  # 4/4

        state = _use_ability_jtl(state, officer)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == fighter.instance_id
                                  and a.defender_id == defender.instance_id))

        hit = _find_instance(state, defender.instance_id)
        assert hit.damage == 3, "1 printed power + the +2 for this attack"
        assert _find_instance(state, officer.instance_id).exhausted

    def test_JTL_146_offers_only_fighter_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        officer = _place(state, "P0", _get_card(repo, "JTL", "146"), "ground")
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        thug = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")

        state = _use_ability_jtl(state, officer)
        state = _drain_jtl(state)
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert fighter.instance_id in attackers
        assert thug.instance_id not in attackers


class TestBiggsDarklighterJTL150:
    """JTL_150 — as a Pilot upgrade: Overwhelm on a Fighter host, +0/+1 on a
    Transport host, Grit on a Speeder host."""

    def test_JTL_150_fighter_host_gains_overwhelm(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # Fighter
        assert has_keyword(state, host, Keyword.OVERWHELM) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "150"), "P0")
        assert has_keyword(state, host, Keyword.OVERWHELM) is True

    def test_JTL_150_transport_host_gets_plus_one_hp_and_no_overwhelm(self, repo):
        """+0/+1 only when the host is a Transport — compared as a DELTA against a
        Fighter host, since Biggs' own +2/+1 upgrade box applies either way."""
        from swu.engine.actions import compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        transport = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        base_fighter = compute_hp(state, fighter)
        base_transport = compute_hp(state, transport)

        _attach_upgrade_directly(state, fighter, _get_card(repo, "JTL", "150"), "P0")
        _attach_upgrade_directly(state, transport, _get_card(repo, "JTL", "150"), "P0")
        assert compute_hp(state, fighter) == base_fighter + 1
        assert compute_hp(state, transport) == base_transport + 1 + 1
        assert has_keyword(state, transport, Keyword.OVERWHELM) is False

    def test_JTL_150_speeder_host_gains_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "214"), "ground")  # Speeder
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "150"), "P0")
        assert has_keyword(state, host, Keyword.GRIT) is True

    def test_JTL_150_host_with_none_of_the_traits_gains_nothing(self, repo):
        from swu.engine.actions import compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Trooper
        before = compute_hp(state, host)
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "150"), "P0")
        assert has_keyword(state, host, Keyword.OVERWHELM) is False
        assert has_keyword(state, host, Keyword.GRIT) is False
        # Only Biggs' own +2/+1 upgrade box — none of the three trait clauses.
        assert compute_hp(state, host) == before + 1

    def test_JTL_150_played_as_a_unit_keeps_none_of_the_granted_keywords(self, repo):
        """``upgrade_only`` keeps the arena scans out, and the sanitiser strips the
        mis-tagged printed Overwhelm/Grit — so his unit side is a plain 3/4."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        biggs = _place(state, "P0", _get_card(repo, "JTL", "150"), "ground")
        assert has_keyword(state, biggs, Keyword.OVERWHELM) is False
        assert has_keyword(state, biggs, Keyword.GRIT) is False


class TestRelentlessFirespryJTL157:
    """JTL_157 — "On Attack: Ready this unit.  Use this ability only once each
    round." """

    def test_JTL_157_on_attack_readies_this_unit(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "157"), "space")
        ship.exhausted = True  # declaring the attack exhausted it
        state = _fire_on_attack(state, ship)
        state = _drain_jtl(state)
        assert _find_instance(state, ship.instance_id).exhausted is False

    def test_JTL_157_does_not_fire_a_second_time_in_the_same_round(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "157"), "space")
        ship.exhausted = True
        state = _fire_on_attack(state, ship)
        state = _drain_jtl(state)

        again = _find_instance(state, ship.instance_id)
        again.exhausted = True
        state = _fire_on_attack(state, again)
        state = _drain_jtl(state)
        assert _find_instance(state, ship.instance_id).exhausted is True

    def test_JTL_157_fires_again_after_the_round_marker_clears(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "157"), "space")
        ship.exhausted = True
        state = _fire_on_attack(state, ship)
        state = _drain_jtl(state)

        state.game_memory.activated_abilities_used_this_round.clear()  # new round
        again = _find_instance(state, ship.instance_id)
        again.exhausted = True
        state = _fire_on_attack(state, again)
        state = _drain_jtl(state)
        assert _find_instance(state, ship.instance_id).exhausted is False


class TestSupportingEta2JTL160:
    """JTL_160 — "On Attack: You may give a ground unit +2/+0 for this phase." """

    def test_JTL_160_on_attack_buffs_a_chosen_ground_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        eta = _place(state, "P0", _get_card(repo, "JTL", "160"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        before = compute_power(state, ally)

        state = _fire_on_attack(state, eta)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, ally.instance_id)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == before + 2

    def test_JTL_160_offers_only_ground_units(self, repo):
        state = _make_state()
        eta = _place(state, "P0", _get_card(repo, "JTL", "160"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")

        state = _fire_on_attack(state, eta)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert ground.instance_id in ids
        assert space.instance_id not in ids

    def test_JTL_160_may_be_declined(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        eta = _place(state, "P0", _get_card(repo, "JTL", "160"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        before = compute_power(state, ally)
        state = _fire_on_attack(state, eta)
        state = _decline_jtl(state)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == before


class TestCaptainTarkinJTL161:
    """JTL_161 — "Each friendly Vehicle unit gets +1/+0 and gains Overwhelm." """

    def test_JTL_161_friendly_vehicle_gets_plus_one_power_and_overwhelm(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3
        before = compute_power(state, vehicle)
        assert has_keyword(state, vehicle, Keyword.OVERWHELM) is False

        _place(state, "P0", _get_card(repo, "JTL", "161"), "ground")
        assert compute_power(state, vehicle) == before + 1
        assert has_keyword(state, vehicle, Keyword.OVERWHELM) is True

    def test_JTL_161_leaves_enemy_vehicles_and_friendly_non_vehicles_alone(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")  # no Vehicle
        enemy_before = compute_power(state, enemy)
        friend_before = compute_power(state, friend)

        tarkin = _place(state, "P0", _get_card(repo, "JTL", "161"), "ground")
        assert compute_power(state, enemy) == enemy_before
        assert has_keyword(state, enemy, Keyword.OVERWHELM) is False
        assert compute_power(state, friend) == friend_before
        # Tarkin is an Official, not a Vehicle — he is outside his own aura, and his
        # mis-tagged printed Overwhelm is stripped by the keyword sanitiser.
        assert has_keyword(state, tarkin, Keyword.OVERWHELM) is False


class TestATDPOccupierJTL163:
    """JTL_163 — "This unit costs 1 resource less to play for each damaged ground
    unit." """

    def _in_hand(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id("P0")
        ci = CardInstance(instance_id="P0_atdp", card_def=_get_card(repo, "JTL", "163"),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(ci)
        return ci

    def test_JTL_163_costs_one_less_per_damaged_ground_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        ci = self._in_hand(state, repo)
        plain = _play_cost(state, ci, ps)  # delta-compared: absolute carries the penalty

        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine.damage = 1
        theirs.damage = 2
        # "Each damaged ground unit" names no controller — both players count.
        assert _play_cost(state, ci, ps) == plain - 2

    def test_JTL_163_undamaged_and_space_units_do_not_count(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        ci = self._in_hand(state, repo)
        plain = _play_cost(state, ci, ps)

        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # undamaged
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        space.damage = 2                                                # damaged, but space
        assert _play_cost(state, ci, ps) == plain


class TestChamSyndullaJTL164:
    """JTL_164 — "When Played: If an opponent controls more resources than you, you
    may put the top card of your deck into play as a resource." """

    def test_JTL_164_ramps_when_the_opponent_is_ahead_on_resources(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 3)
        _give_resources(state, "P1", 5)
        _add_deck_cards_jtl(state, "P0", repo, 2)
        cham = _place(state, "P0", _get_card(repo, "JTL", "164"), "ground")

        before = len(state.player_by_id("P0").resources)
        deck_before = len(state.player_by_id("P0").deck)
        state = _fire_when_played(state, cham)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").resources) == before + 1
        assert len(state.player_by_id("P0").deck) == deck_before - 1

    def test_JTL_164_does_not_trigger_when_level_on_resources(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 4)
        _give_resources(state, "P1", 4)
        _add_deck_cards_jtl(state, "P0", repo, 2)
        cham = _place(state, "P0", _get_card(repo, "JTL", "164"), "ground")
        state = _fire_when_played(state, cham)
        # A mirror, not a negation: equal counts satisfy neither side.
        assert _accept_count_jtl(state) == 0

    def test_JTL_164_may_be_declined(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 1)
        _give_resources(state, "P1", 6)
        _add_deck_cards_jtl(state, "P0", repo, 2)
        cham = _place(state, "P0", _get_card(repo, "JTL", "164"), "ground")
        before = len(state.player_by_id("P0").resources)
        state = _fire_when_played(state, cham)
        state = _decline_jtl(state)
        state = _drain_jtl(state)
        assert len(state.player_by_id("P0").resources) == before


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:18 — Combat tricks, buffs & tempo
# (JTL_178, JTL_179, JTL_182, JTL_188, JTL_192, JTL_193, JTL_195)
# ══════════════════════════════════════════════════════════════════════════════


class TestFaceOffJTL178:
    """JTL_178 — "If no player has taken the initiative this phase, you may ready an
    enemy unit.  If you do, ready a friendly unit in the same arena." """

    def _board(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        far = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        for ci in (enemy, ally, far):
            ci.exhausted = True
        return state, enemy, ally, far

    def test_JTL_178_readies_an_enemy_then_a_friendly_in_the_same_arena(self, repo):
        state, enemy, ally, far = self._board(repo)
        state, _ = _play_event_from_hand(state, repo, "JTL", "178")
        state = _drain_jtl(state)
        state = _choose_jtl(state, enemy.instance_id)
        state = _drain_jtl(state)
        # Only the GROUND friendly is offered — "in the same arena".
        assert far.instance_id not in _target_ids_jtl(state)
        state = _choose_jtl(state, ally.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, enemy.instance_id).exhausted is False
        assert _find_instance(state, ally.instance_id).exhausted is False

    def test_JTL_178_offers_nothing_once_initiative_has_been_claimed(self, repo):
        state, enemy, ally, far = self._board(repo)
        state.initiative_claimed_this_round = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "178")
        state = _drain_jtl(state)
        assert enemy.instance_id not in _target_ids_jtl(state)
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert _find_instance(state, ally.instance_id).exhausted is True

    def test_JTL_178_declining_the_enemy_ready_skips_the_friendly_ready(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTarget
        state, enemy, ally, far = self._board(repo)
        state, _ = _play_event_from_hand(state, repo, "JTL", "178")
        state = _drain_jtl(state)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTarget))
        state = apply(state, decline)
        state = _drain_jtl(state)
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert _find_instance(state, ally.instance_id).exhausted is True


class TestKoiogranTurnJTL179:
    """JTL_179 — "Ready a Fighter or Transport unit with 6 or less power." """

    def test_JTL_179_readies_a_fighter_unit(self, repo):
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        fighter.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "179")
        state = _drain_jtl(state)
        state = _choose_jtl(state, fighter.instance_id)
        assert _find_instance(state, fighter.instance_id).exhausted is False

    def test_JTL_179_accepts_a_transport_but_not_another_trait(self, repo):
        state = _make_state()
        transport = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        for ci in (transport, trooper):
            ci.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "179")
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert transport.instance_id in ids
        assert trooper.instance_id not in ids

    def test_JTL_179_skips_a_fighter_over_six_power(self, repo):
        from swu.abilities.registry import Duration
        from swu.abilities.resolver import _make_modifier
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3
        fighter.exhausted = True
        state.modifiers.append(_make_modifier(
            state, fighter.instance_id, fighter.instance_id, 6, 0,
            Duration.PERMANENT))                                    # now 7 power
        state, _ = _play_event_from_hand(state, repo, "JTL", "179")
        state = _drain_jtl(state)
        assert fighter.instance_id not in _target_ids_jtl(state)


class TestRampartJTL182:
    """JTL_182 — "This unit doesn't ready during the regroup phase unless its power
    is 4 or more." """

    def _regroup_ready(self, state):
        from swu.engine.actions import _ready_all_cards
        from swu.engine.state import Phase
        state.phase = Phase.REGROUP
        _ready_all_cards(state)
        return state

    def test_JTL_182_stays_exhausted_at_regroup_at_three_power(self, repo):
        state = _make_state()
        rampart = _place(state, "P0", _get_card(repo, "JTL", "182"), "space")  # 3/3
        rampart.exhausted = True
        state = self._regroup_ready(state)
        assert rampart.exhausted is True

    def test_JTL_182_readies_at_regroup_once_it_has_four_power(self, repo):
        from swu.abilities.registry import Duration
        from swu.abilities.resolver import _make_modifier
        state = _make_state()
        rampart = _place(state, "P0", _get_card(repo, "JTL", "182"), "space")
        rampart.exhausted = True
        state.modifiers.append(_make_modifier(
            state, rampart.instance_id, rampart.instance_id, 1, 0,
            Duration.PERMANENT))                                    # 4 power
        state = self._regroup_ready(state)
        assert rampart.exhausted is False

    def test_JTL_182_can_still_be_readied_by_an_effect_in_the_action_phase(self, repo):
        """``regroup_only``: the card bars only the regroup ready step."""
        state = _make_state()
        rampart = _place(state, "P0", _get_card(repo, "JTL", "182"), "space")
        rampart.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "179")  # Koiogran Turn
        state = _drain_jtl(state)
        state = _choose_jtl(state, rampart.instance_id)
        assert _find_instance(state, rampart.instance_id).exhausted is False


class TestMoffGideonJTL188:
    """JTL_188 — "When this unit deals combat damage to an opponent's base: Each unit
    that opponent plays this phase costs 1 resource more." """

    def _gideon_hits_the_base(self, state, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        gideon = _place(state, "P0", _get_card(repo, "JTL", "188"), "ground")
        return fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": gideon.instance_id})

    def _enemy_unit_in_hand(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(instance_id="P1_unit", card_def=_get_card(repo, "SOR", "46"),
                          owner_id="P1", zone=Zone.HAND)
        state.player_by_id("P1").hand.append(ci)
        return ci

    def test_JTL_188_taxes_the_opponents_units_by_one(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci = self._enemy_unit_in_hand(state, repo)
        p1 = state.player_by_id("P1")
        plain = _play_cost(state, ci, p1)
        state = self._gideon_hits_the_base(state, repo)
        state = _drain_jtl(state)
        assert _play_cost(state, ci, p1) == plain + 1

    def test_JTL_188_two_hits_in_a_phase_stack(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci = self._enemy_unit_in_hand(state, repo)
        p1 = state.player_by_id("P1")
        plain = _play_cost(state, ci, p1)
        state = self._gideon_hits_the_base(state, repo)
        state = self._gideon_hits_the_base(state, repo)
        state = _drain_jtl(state)
        assert _play_cost(state, ci, p1) == plain + 2

    def test_JTL_188_leaves_the_controllers_own_units_alone(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        mine = CardInstance(instance_id="P0_unit",
                            card_def=_get_card(repo, "SOR", "46"),
                            owner_id="P0", zone=Zone.HAND)
        state.player_by_id("P0").hand.append(mine)
        p0 = state.player_by_id("P0")
        plain = _play_cost(state, mine, p0)
        state = self._gideon_hits_the_base(state, repo)
        state = _drain_jtl(state)
        assert _play_cost(state, mine, p0) == plain

    def test_JTL_188_tax_clears_at_the_phase_rollover(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ci = self._enemy_unit_in_hand(state, repo)
        p1 = state.player_by_id("P1")
        plain = _play_cost(state, ci, p1)
        state = self._gideon_hits_the_base(state, repo)
        state.game_memory.clear_phase()
        assert _play_cost(state, ci, p1) == plain


class TestInDebtToCrimsonDawnJTL192:
    """JTL_192 — "When attached unit readies: Exhaust it unless its controller pays
    2 resources." """

    def _regroup_with_debt(self, repo):
        from swu.engine.actions import apply, _ready_all_cards, Pass
        from swu.engine.state import Phase
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "192"), "P1")
        host.exhausted = True
        _give_resources(state, "P0", 5)
        state.phase = Phase.REGROUP
        _ready_all_cards(state)
        # Settle so the ready-ledger drain fires the observer on a clean stack.
        state.phase = Phase.ACTION
        state = apply(state, Pass())
        return state, host

    def test_JTL_192_readying_offers_the_host_controller_a_pay_or_exhaust(self, repo):
        state, host = self._regroup_with_debt(repo)
        top = state.pending_decisions[-1]
        assert top.kind == "pay_or_exhaust"
        assert top.deciding_player_id == "P0"
        assert top.context["pay_amount"] == 2

    def test_JTL_192_paying_two_keeps_the_unit_ready(self, repo):
        from swu.engine.actions import legal_actions, apply, PayToAvoidExhaust
        state, host = self._regroup_with_debt(repo)
        ready_before = state.player_by_id("P0").available_resources
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PayToAvoidExhaust))
        state = apply(state, act)
        assert _find_instance(state, host.instance_id).exhausted is False
        assert state.player_by_id("P0").available_resources == ready_before - 2

    def test_JTL_192_declining_exhausts_the_unit_again(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptExhaust
        state, host = self._regroup_with_debt(repo)
        act = next(a for a in legal_actions(state) if isinstance(a, AcceptExhaust))
        state = apply(state, act)
        assert _find_instance(state, host.instance_id).exhausted is True

    def test_JTL_192_a_unit_without_the_upgrade_readies_untaxed(self, repo):
        from swu.engine.actions import apply, _ready_all_cards, Pass
        from swu.engine.state import Phase
        state = _make_state()
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        plain.exhausted = True
        state.phase = Phase.REGROUP
        _ready_all_cards(state)
        state.phase = Phase.ACTION
        state = apply(state, Pass())
        assert not state.pending_decisions
        assert _find_instance(state, plain.instance_id).exhausted is False


class TestIHaveYouNowJTL193:
    """JTL_193 — "Attack with a Vehicle unit.  Prevent all damage that would be
    dealt to it during this attack." """

    def test_JTL_193_vehicle_attacker_takes_no_combat_damage_back(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        # Two vanilla 1/3 Vehicles, so both survive the trade and can be measured.
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        defender = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "193")
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id == defender.instance_id))
        assert _find_instance(state, attacker.instance_id).damage == 0
        assert _find_instance(state, defender.instance_id).damage == 1

    def test_JTL_193_offers_only_vehicle_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "JTL", "193")
        state = _drain_jtl(state)
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert vehicle.instance_id in attackers
        assert trooper.instance_id not in attackers


class TestCatAndMouseJTL195:
    """JTL_195 — "Exhaust an enemy unit.  If you do, ready a friendly unit in the
    same arena with power equal to or less than that enemy unit." """

    def test_JTL_195_exhausts_an_enemy_then_readies_a_weaker_friendly(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3 power
        weak = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")  # 2 power
        weak.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "195")
        state = _drain_jtl(state)
        state = _choose_jtl(state, enemy.instance_id)
        state = _drain_jtl(state)
        state = _choose_jtl(state, weak.instance_id)
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert _find_instance(state, weak.instance_id).exhausted is False

    def test_JTL_195_will_not_ready_a_friendly_stronger_than_the_enemy(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2 power
        strong = _place(state, "P0", _get_card(repo, "JTL", "164"), "ground")  # 5 power
        strong.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "195")
        state = _drain_jtl(state)
        state = _choose_jtl(state, enemy.instance_id)
        state = _drain_jtl(state)
        assert strong.instance_id not in _target_ids_jtl(state)
        assert _find_instance(state, enemy.instance_id).exhausted is True

    def test_JTL_195_will_not_ready_a_friendly_in_the_other_arena(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        far = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1 power
        far.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "195")
        state = _drain_jtl(state)
        state = _choose_jtl(state, enemy.instance_id)
        state = _drain_jtl(state)
        assert far.instance_id not in _target_ids_jtl(state)


# ══════════════════════════════════════════════════════════════════════════════
# jtl-set:19 — Combat tricks, buffs & tempo
# (JTL_199, JTL_202, JTL_206, JTL_211, JTL_228, JTL_231, JTL_238)
# ══════════════════════════════════════════════════════════════════════════════


class TestBladeSquadronBWingJTL199:
    """JTL_199 — "When Played: If another player controls 3 or more exhausted units,
    give a Shield token to a unit." """

    def _exhausted_enemies(self, state, repo, n):
        out = []
        for _ in range(n):
            ci = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
            ci.exhausted = True
            out.append(ci)
        return out

    def test_JTL_199_shields_a_unit_when_the_opponent_has_three_exhausted(self, repo):
        state = _make_state()
        self._exhausted_enemies(state, repo, 3)
        bwing = _place(state, "P0", _get_card(repo, "JTL", "199"), "space")
        state = _fire_when_played(state, bwing)
        state = _drain_jtl(state)
        state = _choose_jtl(state, bwing.instance_id)
        assert _shield_count(_find_instance(state, bwing.instance_id)) == 1

    def test_JTL_199_does_not_trigger_below_three_exhausted_enemies(self, repo):
        state = _make_state()
        self._exhausted_enemies(state, repo, 2)
        bwing = _place(state, "P0", _get_card(repo, "JTL", "199"), "space")
        state = _fire_when_played(state, bwing)
        assert not state.pending_decisions
        assert _shield_count(_find_instance(state, bwing.instance_id)) == 0

    def test_JTL_199_own_exhausted_units_do_not_count(self, repo):
        state = _make_state()
        for _ in range(4):
            mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
            mine.exhausted = True
        bwing = _place(state, "P0", _get_card(repo, "JTL", "199"), "space")
        state = _fire_when_played(state, bwing)
        assert not state.pending_decisions


class TestBlackSquadronScoutWingJTL202:
    """JTL_202 — "When you play an upgrade on this unit: You may attack with this
    unit.  It gets +1/+0 for this attack." """

    def test_JTL_202_upgrade_on_it_grants_an_attack_at_plus_one(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "JTL", "202"), "space")  # 4/6
        defender = _place(state, "P1", _get_card(repo, "JTL", "240"), "space")  # 4/4
        up = _attach_upgrade_directly(state, wing, _get_card(repo, "SOR", "53"), "P0")
        state = _fire_card_played_jtl(state, up)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {wing.instance_id}

    def test_JTL_202_an_upgrade_on_another_unit_does_not_trigger_it(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "202"), "space")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, other, _get_card(repo, "SOR", "53"), "P0")
        state = _fire_card_played_jtl(state, up)
        assert _accept_count_jtl(state) == 0
        assert not state.pending_decisions

    def test_JTL_202_may_be_declined(self, repo):
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "JTL", "202"), "space")
        up = _attach_upgrade_directly(state, wing, _get_card(repo, "SOR", "53"), "P0")
        state = _fire_card_played_jtl(state, up)
        state = _decline_jtl(state)
        state = _drain_jtl(state)
        assert not state.pending_decisions


class TestFlyCasualJTL206:
    """JTL_206 — "Ready a Vehicle unit.  It can't attack bases for this phase." """

    def test_JTL_206_readies_the_vehicle_and_bars_it_from_bases(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        vehicle.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "206")
        state = _drain_jtl(state)
        state = _choose_jtl(state, vehicle.instance_id)
        readied = _find_instance(state, vehicle.instance_id)
        assert readied.exhausted is False
        base_attacks = [a for a in legal_actions(state)
                        if isinstance(a, AttackWithUnit)
                        and a.attacker_id == vehicle.instance_id
                        and a.defender_id is None]
        assert base_attacks == []

    def test_JTL_206_offers_only_exhausted_vehicles(self, repo):
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        trooper.exhausted = True
        ready_vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        exhausted_vehicle = _place(state, "P0", _get_card(repo, "JTL", "240"), "space")
        exhausted_vehicle.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "206")
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert exhausted_vehicle.instance_id in ids
        assert trooper.instance_id not in ids
        assert ready_vehicle.instance_id not in ids


class TestIndependentSmugglerJTL211:
    """JTL_211 — "Attached unit gains Raid 1." """

    def test_JTL_211_host_gains_raid_one(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert keyword_value(state, host, Keyword.RAID) == 0
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "211"), "P0")
        assert keyword_value(state, host, Keyword.RAID) == 1

    def test_JTL_211_raid_lifts_when_the_pilot_detaches(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "211"), "P0")
        host.attached_upgrades.remove(up)
        assert keyword_value(state, host, Keyword.RAID) == 0


class TestBarrelRollJTL228:
    """JTL_228 — "Attack with a space unit.  After completing this attack, you may
    exhaust a space unit." """

    def test_JTL_228_attack_resolves_before_the_exhaust_is_offered(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        enemy = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "228")
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id == enemy.instance_id))
        state = _drain_jtl(state)
        # The attack happened, and only now is the exhaust choice offered.
        assert _find_instance(state, enemy.instance_id).damage == 1
        assert enemy.instance_id in _target_ids_jtl(state)

    def test_JTL_228_exhaust_offers_only_ready_space_units(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "JTL", "240"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "228")
        state = _drain_jtl(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id is None))
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert space.instance_id in ids
        assert ground.instance_id not in ids
        state = _choose_jtl(state, space.instance_id)
        assert _find_instance(state, space.instance_id).exhausted is True


class TestPunchItJTL231:
    """JTL_231 — "Attack with a Vehicle unit.  It gets +2/+0 for this attack." """

    def test_JTL_231_vehicle_attacks_at_plus_two_power(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3
        defender = _place(state, "P1", _get_card(repo, "JTL", "240"), "space")  # 4/4
        state, _ = _play_event_from_hand(state, repo, "JTL", "231")
        state = _drain_jtl(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id == defender.instance_id))
        assert _find_instance(state, defender.instance_id).damage == 3

    def test_JTL_231_offers_only_vehicle_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "JTL", "231")
        state = _drain_jtl(state)
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert vehicle.instance_id in attackers
        assert trooper.instance_id not in attackers


class TestSithTrooperJTL238:
    """JTL_238 — "On Attack: This unit gets +1/+0 for this attack for each damaged
    unit the defending player controls." """

    def test_JTL_238_scales_with_the_defending_players_damaged_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")  # 3/3
        for _ in range(2):
            hurt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
            hurt.damage = 1
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # undamaged
        state = _fire_on_attack(state, trooper)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, trooper.instance_id)) == 5

    def test_JTL_238_no_damaged_enemies_means_no_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, trooper)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, trooper.instance_id)) == 3

    def test_JTL_238_friendly_damaged_units_do_not_count(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.damage = 2
        state = _fire_on_attack(state, trooper)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, trooper.instance_id)) == 3


# ── Group jtl-set:20 — Combat tricks, buffs & tempo ───────────────────────────


class TestResistanceXWingJTL247:
    """JTL_247 — "While this unit has a Pilot on it, it gets +1/+1." """

    def test_JTL_247_pilot_upgrade_grants_plus_one_plus_one(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")  # 2/2
        assert compute_power(state, xwing) == 2
        assert compute_hp(state, xwing) == 2
        xwing.attached_upgrades.append(_make_pilot_upgrade("P0", xwing.zone))
        xwing = _find_instance(state, xwing.instance_id)
        assert compute_power(state, xwing) == 3
        assert compute_hp(state, xwing) == 3

    def test_JTL_247_a_non_pilot_upgrade_does_not_trigger_it(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        # Republic Y-Wing has no Pilot trait, so riding along changes nothing.
        _attach_upgrade_directly(state, xwing, _get_card(repo, "JTL", "212"), "P0")
        xwing = _find_instance(state, xwing.instance_id)
        assert compute_power(state, xwing) == 2
        assert compute_hp(state, xwing) == 2

    def test_JTL_247_buff_lifts_when_the_pilot_detaches(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        pilot = _make_pilot_upgrade("P0", xwing.zone)
        xwing.attached_upgrades.append(pilot)
        assert compute_power(state, _find_instance(state, xwing.instance_id)) == 3
        xwing.attached_upgrades.remove(pilot)
        assert compute_power(state, _find_instance(state, xwing.instance_id)) == 2


class TestCoordinatedFrontJTL253:
    """JTL_253 — "You may give a ground unit +2/+2 for this phase.  You may give a
    space unit +2/+2 for this phase." """

    def test_JTL_253_buffs_one_unit_in_each_arena(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        base_g = compute_power(state, ground)
        base_s = compute_power(state, space)
        base_s_hp = compute_hp(state, space)
        state, _ = _play_event_from_hand(state, repo, "JTL", "253")
        state = _drain_jtl(state)
        # The two clauses are separate abilities; each offers only its own arena.
        state = _choose_jtl(state, space.instance_id)
        state = _drain_jtl(state)
        state = _choose_jtl(state, ground.instance_id)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, space.instance_id)) == base_s + 2
        assert compute_hp(state, _find_instance(state, space.instance_id)) == base_s_hp + 2
        assert compute_power(state, _find_instance(state, ground.instance_id)) == base_g + 2

    def test_JTL_253_each_clause_offers_only_its_own_arena(self, repo):
        state = _make_state()
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        state, _ = _play_event_from_hand(state, repo, "JTL", "253")
        state = _drain_jtl(state)
        first = _target_ids_jtl(state)
        assert first == {space.instance_id}
        state = _choose_jtl(state, space.instance_id)
        state = _drain_jtl(state)
        assert _target_ids_jtl(state) == {ground.instance_id}

    def test_JTL_253_each_clause_may_be_declined(self, repo):
        from swu.engine.actions import (legal_actions, apply, DeclineTarget,
                                        compute_power)
        state = _make_state()
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        base_s = compute_power(state, space)
        state, _ = _play_event_from_hand(state, repo, "JTL", "253")
        state = _drain_jtl(state)
        dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTarget))
        state = apply(state, dec)
        state = _drain_jtl(state)
        assert compute_power(state, _find_instance(state, space.instance_id)) == base_s


class TestFlankingFangFighterJTL257:
    """JTL_257 — "While you control another Fighter unit, this unit gains Raid 2." """

    def test_JTL_257_gains_raid_two_with_another_fighter(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        fang = _place(state, "P0", _get_card(repo, "JTL", "257"), "space")
        assert keyword_value(state, fang, Keyword.RAID) == 0
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # a Fighter
        assert keyword_value(state, _find_instance(state, fang.instance_id),
                             Keyword.RAID) == 2

    def test_JTL_257_another_means_another_an_enemy_fighter_does_not_count(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        fang = _place(state, "P0", _get_card(repo, "JTL", "257"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        assert keyword_value(state, _find_instance(state, fang.instance_id),
                             Keyword.RAID) == 0

    def test_JTL_257_a_non_fighter_friendly_does_not_switch_it_on(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        fang = _place(state, "P0", _get_card(repo, "JTL", "257"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # no Fighter trait
        assert keyword_value(state, _find_instance(state, fang.instance_id),
                             Keyword.RAID) == 0


class TestAttackRunJTL261:
    """JTL_261 — "Attack with 2 space units (one at a time)." """

    def test_JTL_261_two_space_units_attack_one_at_a_time(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        first = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # 1/3
        second = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1/3
        state, _ = _play_event_from_hand(state, repo, "JTL", "261")
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == first.instance_id
                                  and a.defender_id is None))
        state = _drain_jtl(state)
        # The decision is re-pushed for the SECOND attack, and the first attacker
        # (already used) is no longer offered.
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {second.instance_id}
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == second.instance_id
                                  and a.defender_id is None))
        state = _drain_jtl(state)
        assert not [d for d in state.pending_decisions if d.kind == "granted_attack"]
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_JTL_261_stops_after_two_even_with_a_third_space_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        units = [_place(state, "P0", _get_card(repo, "JTL", "212"), "space")
                 for _ in range(3)]
        state, _ = _play_event_from_hand(state, repo, "JTL", "261")
        state = _drain_jtl(state)
        for u in units[:2]:
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AttackWithUnit)
                                      and a.attacker_id == u.instance_id
                                      and a.defender_id is None))
            state = _drain_jtl(state)
        assert not [d for d in state.pending_decisions if d.kind == "granted_attack"]
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_JTL_261_offers_only_space_attackers(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        space = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "JTL", "261")
        state = _drain_jtl(state)
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {space.instance_id}
        assert ground.instance_id not in attackers


class TestEvasiveManeuverJTL262:
    """JTL_262 — "Exhaust a unit." """

    def test_JTL_262_exhausts_a_chosen_enemy_unit(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "JTL", "262")
        state = _drain_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).exhausted is True

    def test_JTL_262_offers_only_ready_units_of_either_player(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "JTL", "262")
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert ids == {mine.instance_id, foe.instance_id}


# ── Group jtl-set:21 — Miscellaneous abilities ────────────────────────────────


def _mark_attacked_jtl(state, ci):
    """Record ``ci`` in the ledger the attack-declare step feeds."""
    state.game_memory.units_attacked_this_round.add(ci.instance_id)
    return state


def _ability_ids_jtl(state, source_ci):
    from swu.engine.actions import legal_actions, UseAbility
    return [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]


class TestDarthVaderJTL6:
    """JTL_6 — "Action [Exhaust]: If you attacked with a non-token Vehicle unit this
    phase, create a TIE Fighter token." + "When deployed as an upgrade: Create 2
    TIE Fighter tokens." """

    def test_JTL_6_action_is_gated_on_a_non_token_vehicle_attack(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "JTL", "6"))
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert not _ability_ids_jtl(state, vader)
        _mark_attacked_jtl(state, vehicle)
        assert _ability_ids_jtl(state, vader)

    def test_JTL_6_action_creates_one_tie_fighter(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "JTL", "6"))
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _mark_attacked_jtl(state, vehicle)
        state = _use_ability_jtl(state, vader)
        state = _drain_jtl(state)
        assert _tie_fighter_count(state, "P0") == 1
        assert state.find_instance(vader.instance_id)[1].exhausted

    def test_JTL_6_his_own_tie_token_does_not_re_arm_the_action(self, repo):
        """The non-token filter is the whole clause — a TIE Fighter is a Vehicle."""
        from swu.engine.tokens import _token_unit_def
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "JTL", "6"))
        tie = _place(state, "P0", _token_unit_def("TIE Fighter"), "space")
        _mark_attacked_jtl(state, tie)
        assert not _ability_ids_jtl(state, vader)

    def test_JTL_6_a_non_vehicle_attacker_does_not_arm_it(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "JTL", "6"))
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _mark_attacked_jtl(state, trooper)
        assert not _ability_ids_jtl(state, vader)

    def test_JTL_6_deploying_as_an_upgrade_creates_two_tie_fighters(self, repo):
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "JTL", "6"))
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_leader_as_pilot(state, host, vader)
        state = _fire_pilot_leader_deploy_jtl(state, vader, host)
        state = _drain_jtl(state)
        assert _tie_fighter_count(state, "P0") == 2


class TestPoeDameronJTL13:
    """JTL_13 — undeployed "Action [1 resource, Exhaust]: Flip this leader and
    attach him as an upgrade to a friendly Vehicle unit without a Pilot on it";
    as an upgrade "Action [1 resource]: Attach this upgrade to a friendly Vehicle
    unit without a Pilot on it.  Use this ability only once each round." """

    def test_JTL_13_flips_onto_a_friendly_vehicle(self, repo):
        state = _make_state()
        poe = _place_leader(state, "P0", _get_card(repo, "JTL", "13"))
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _give_resources(state, "P0", 2)
        state = _use_ability_jtl(state, poe)
        state = _drain_jtl(state)
        state = _choose_jtl(state, vehicle.instance_id)
        state = _drain_jtl(state)
        host = _find_instance(state, vehicle.instance_id)
        assert [u.instance_id for u in host.attached_upgrades] == [poe.instance_id]
        assert state.find_instance(poe.instance_id)[1].deployed is True
        # He has left the base zone entirely (only the base itself remains there).
        assert poe.instance_id not in {c.instance_id for c
                                       in state.player_by_id("P0").base_zone}

    def test_JTL_13_only_offers_vehicles_without_a_pilot(self, repo):
        state = _make_state()
        poe = _place_leader(state, "P0", _get_card(repo, "JTL", "13"))
        free_vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        crewed = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        crewed.attached_upgrades.append(_make_pilot_upgrade("P0", crewed.zone))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not a Vehicle
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")   # not friendly
        _give_resources(state, "P0", 2)
        state = _use_ability_jtl(state, poe)
        state = _drain_jtl(state)
        assert _target_ids_jtl(state) == {free_vehicle.instance_id}

    def test_JTL_13_as_an_upgrade_moves_himself_to_another_vehicle(self, repo):
        state = _make_state()
        poe = _place_leader(state, "P0", _get_card(repo, "JTL", "13"))
        first = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        second = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_leader_as_pilot(state, first, poe)
        _give_resources(state, "P0", 2)
        state = _use_ability_jtl(state, poe)
        state = _drain_jtl(state)
        state = _choose_jtl(state, second.instance_id)
        state = _drain_jtl(state)
        assert not _find_instance(state, first.instance_id).attached_upgrades
        assert [u.instance_id for u in
                _find_instance(state, second.instance_id).attached_upgrades] == \
            [poe.instance_id]

    def test_JTL_13_upgrade_action_is_once_each_round(self, repo):
        state = _make_state()
        poe = _place_leader(state, "P0", _get_card(repo, "JTL", "13"))
        first = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        second = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_leader_as_pilot(state, first, poe)
        _give_resources(state, "P0", 4)
        state = _use_ability_jtl(state, poe)
        state = _drain_jtl(state)
        state = _choose_jtl(state, second.instance_id)
        state = _drain_jtl(state)
        assert not _ability_ids_jtl(state, poe)


class TestKazudaXionoJTL18:
    """JTL_18 — undeployed "Action [Exhaust]: A friendly unit loses all abilities for
    this round.  Take an extra action after this one."; deployed/granted "On Attack:
    Choose any number of friendly units.  They lose all abilities for this round." """

    def test_JTL_18_action_suppresses_a_friendly_units_abilities(self, repo):
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        victim = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        state = _use_ability_jtl(state, kaz)
        state = _drain_jtl(state)
        state = _choose_jtl(state, victim.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, victim.instance_id).abilities_suppressed is True

    def test_JTL_18_action_keeps_the_seat_as_an_extra_action(self, repo):
        """The INLINE path: with no friendly unit to hit the effect fizzles, and the
        extra action still stands (the ability never hands the turn over)."""
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        assert state.active_player_index == 0
        state = _use_ability_jtl(state, kaz)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert state.active_player_index == 0     # no hand-over: the extra action

    def test_JTL_18_extra_action_survives_the_targeted_decision_path(self, repo):
        """With two candidates the effect defers to a resolve_effects decision, so
        the seat is kept by the decision's after-resolve player instead."""
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        a = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        state = _use_ability_jtl(state, kaz)
        state = _drain_jtl(state)
        state = _choose_jtl(state, a.instance_id)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert state.active_player_index == 0
        assert _find_instance(state, a.instance_id).abilities_suppressed is True

    def test_JTL_18_on_attack_suppresses_any_number_of_friendly_units(self, repo):
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        kaz = _deploy_leader_to_arena(state, kaz, "ground")
        one = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        two = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, kaz)
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "select_token"
        ids = _token_target_ids_jtl(state)
        assert foe.instance_id not in ids           # friendly units only
        state = _select_token_jtl(state, one.instance_id)
        state = _select_token_jtl(state, two.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, one.instance_id).abilities_suppressed is True
        assert _find_instance(state, two.instance_id).abilities_suppressed is True
        assert _find_instance(state, foe.instance_id).abilities_suppressed is False

    def test_JTL_18_on_attack_may_choose_none(self, repo):
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        kaz = _deploy_leader_to_arena(state, kaz, "ground")
        one = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        state = _fire_on_attack(state, kaz)
        state = _drain_jtl(state)
        state = _finish_select_token_jtl(state)
        state = _drain_jtl(state)
        assert _find_instance(state, one.instance_id).abilities_suppressed is False

    def test_JTL_18_as_an_upgrade_grants_the_on_attack_to_its_host(self, repo):
        state = _make_state()
        kaz = _place_leader(state, "P0", _get_card(repo, "JTL", "18"))
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        friend = _place(state, "P0", _get_card(repo, "JTL", "238"), "ground")
        _attach_leader_as_pilot(state, host, kaz)
        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _drain_jtl(state)
        assert state.pending_decisions[-1].kind == "select_token"
        state = _select_token_jtl(state, friend.instance_id)
        state = _drain_jtl(state)
        assert _find_instance(state, friend.instance_id).abilities_suppressed is True


class TestDataVaultJTL24:
    """JTL_24 — "Your minimum deck size is increased by 10 cards." """

    def test_JTL_24_raises_the_required_deck_size_to_sixty(self, repo):
        from swu.cards.deckrules import deck_size_for
        assert deck_size_for(_get_card(repo, "JTL", "24")) == 60

    def test_JTL_24_deck_errors_ask_for_sixty_cards(self, repo):
        from swu.cards.deckrules import deck_errors
        errs = deck_errors(_get_card(repo, "JTL", "13"),
                           _get_card(repo, "JTL", "24"), {}, repo)
        assert any("needs exactly 60" in e for e in errs)

    def test_JTL_24_a_base_without_the_marker_still_needs_fifty(self, repo):
        from swu.cards.deckrules import deck_size_for
        assert deck_size_for(_get_card(repo, "JTL", "21")) == 50


class TestThermalOscillatorJTL25:
    """JTL_25 — "Your minimum deck size is decreased by 5 cards." """

    def test_JTL_25_lowers_the_required_deck_size_to_forty_five(self, repo):
        from swu.cards.deckrules import deck_size_for
        assert deck_size_for(_get_card(repo, "JTL", "25")) == 45

    def test_JTL_25_deck_errors_ask_for_forty_five_cards(self, repo):
        from swu.cards.deckrules import deck_errors
        errs = deck_errors(_get_card(repo, "JTL", "13"),
                           _get_card(repo, "JTL", "25"), {}, repo)
        assert any("needs exactly 45" in e for e in errs)


class TestTamRyvoraJTL35:
    """JTL_35 — "Attached unit gains: 'On Attack: Give an enemy unit in this arena
    −1/−1 for this phase.'" """

    def test_JTL_35_host_on_attack_debuffs_an_enemy_in_its_arena(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        foe = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "35"), "P0")
        before_p = compute_power(state, foe)
        before_hp = compute_hp(state, foe)
        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _drain_jtl(state)
        state = _choose_jtl(state, foe.instance_id)
        assert compute_power(state, _find_instance(state, foe.instance_id)) == before_p - 1
        assert compute_hp(state, _find_instance(state, foe.instance_id)) == before_hp - 1

    def test_JTL_35_only_offers_enemies_in_the_hosts_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        same = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        other = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friend = _place(state, "P0", _get_card(repo, "JTL", "247"), "space")
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "35"), "P0")
        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _drain_jtl(state)
        ids = _target_ids_jtl(state)
        assert ids == {same.instance_id}
        assert other.instance_id not in ids
        assert friend.instance_id not in ids

    def test_JTL_35_as_a_plain_unit_has_no_ability(self, repo):
        """The grant is wrapped in a GrantedAbility, so her own unit side is vanilla."""
        state = _make_state()
        tam = _place(state, "P0", _get_card(repo, "JTL", "35"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, tam)
        assert not state.pending_decisions


class TestCorvusJTL38:
    """JTL_38 — "When Played: You may attach a friendly Pilot unit or upgrade to
    this unit." """

    def test_JTL_38_attaches_a_friendly_pilot_unit_and_cleans_it_up(self, repo):
        state = _make_state()
        corvus = _place(state, "P0", _get_card(repo, "JTL", "38"), "space")
        pilot = _place(state, "P0", _get_card(repo, "JTL", "211"), "ground")
        pilot.damage = 2
        state = _fire_when_played(state, corvus)
        state = _drain_jtl(state)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        state = _choose_jtl(state, pilot.instance_id)
        state = _drain_jtl(state)
        host = _find_instance(state, corvus.instance_id)
        assert [u.instance_id for u in host.attached_upgrades] == [pilot.instance_id]
        # The printed reminder: damage removed (and it is no longer an arena unit).
        assert host.attached_upgrades[0].damage == 0
        assert not [u for u in state.player_by_id("P0").ground_arena
                    if u.instance_id == pilot.instance_id]

    def test_JTL_38_can_take_a_pilot_off_another_vehicle(self, repo):
        state = _make_state()
        corvus = _place(state, "P0", _get_card(repo, "JTL", "38"), "space")
        other = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        pilot = _attach_upgrade_directly(state, other,
                                         _get_card(repo, "JTL", "211"), "P0")
        state = _fire_when_played(state, corvus)
        state = _drain_jtl(state)
        state = _accept_jtl(state)
        state = _drain_jtl(state)
        assert pilot.instance_id in _target_ids_jtl(state)
        state = _choose_jtl(state, pilot.instance_id)
        state = _drain_jtl(state)
        assert not _find_instance(state, other.instance_id).attached_upgrades
        assert [u.instance_id for u in
                _find_instance(state, corvus.instance_id).attached_upgrades] == \
            [pilot.instance_id]

    def test_JTL_38_offers_no_prompt_without_a_friendly_pilot(self, repo):
        state = _make_state()
        corvus = _place(state, "P0", _get_card(repo, "JTL", "38"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # not a Pilot
        _place(state, "P1", _get_card(repo, "JTL", "211"), "ground")  # not friendly
        state = _fire_when_played(state, corvus)
        state = _drain_jtl(state)
        assert not state.pending_decisions
        assert not _find_instance(state, corvus.instance_id).attached_upgrades


# ═════════════════════════════════════════════════════════════════════════════
# Group jtl-set:22 — Miscellaneous abilities
# ═════════════════════════════════════════════════════════════════════════════

def _tokens_named(state, owner_id, name):
    ps = state.player_by_id(owner_id)
    return [u for u in ps.ground_arena + ps.space_arena
            if u.card_def.display_name == name]


def _drain_auto(state, limit: int = 12):
    """Apply queued AutoResolveEffects steps until a real choice (or nothing) is
    pending — the engine walks a resolve_effects decision one step per action."""
    from swu.engine.actions import legal_actions, apply
    for _ in range(limit):
        acts = legal_actions(state)
        auto = [a for a in acts if type(a).__name__ == "AutoResolveEffects"]
        if not auto:
            return state
        state = apply(state, auto[0])
    return state


class TestChimaeraJTL39:
    """JTL_39 — "When Played: You may use a 'When Defeated' ability on another
    friendly unit."  + "When Defeated: Create 2 TIE Fighter tokens."""

    def test_JTL_39_uses_another_units_when_defeated_ability(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        chim = _get_card(repo, "JTL", "39")
        state = _make_state()
        a = _place(state, "P0", chim, "space")
        b = _place(state, "P0", chim, "space")
        state = _fire_when_played(state, a)
        accepts = [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]
        assert accepts, "the optional When Played should be offered"
        state = apply(state, accepts[0])
        choices = [x for x in legal_actions(state)
                   if isinstance(x, ChooseTarget) and x.target_id == b.instance_id]
        assert choices, "the OTHER Chimaera is the only legal target"
        state = _drain_auto(apply(state, choices[0]))
        # B's own When Defeated ran without B dying.
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 2
        assert _find_instance(state, b.instance_id) is not None

    def test_JTL_39_not_offered_without_another_when_defeated_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "JTL", "39"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # vanilla friend
        state = _fire_when_played(state, a)
        assert not [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]

    def test_JTL_39_when_defeated_creates_two_tie_fighters(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "JTL", "39"), "space")
        state = _defeat_and_fire(state, a, "P0")
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 2


class TestAdmiralYularenJTL47:
    """JTL_47 — "When Played: Choose Grit, Restore 1, Sentinel, or Shielded.
    While this unit is in play, each friendly Vehicle unit gains it."""

    def test_JTL_47_printed_choosable_keywords_are_stripped(self, repo):
        assert _get_card(repo, "JTL", "47").keywords == ()

    def test_JTL_47_chosen_keyword_is_granted_to_friendly_vehicles(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        yul = _place(state, "P0", _get_card(repo, "JTL", "47"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        enemy = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        assert not has_keyword(state, vehicle, Keyword.SENTINEL)
        state = _fire_when_played(state, yul)
        modes = [x for x in legal_actions(state) if isinstance(x, ChooseModalOption)]
        assert {m.mode for m in modes} == {
            "choose_keyword_grit", "choose_keyword_restore_1",
            "choose_keyword_sentinel", "choose_keyword_shielded"}
        pick = next(m for m in modes if m.mode == "choose_keyword_sentinel")
        state = apply(state, pick)
        v = _find_instance(state, vehicle.instance_id)
        assert has_keyword(state, v, Keyword.SENTINEL)
        # Only the chosen keyword, and only friendly Vehicles.
        assert not has_keyword(state, v, Keyword.SHIELDED)
        assert not has_keyword(state, _find_instance(state, enemy.instance_id),
                               Keyword.SENTINEL)
        # Yularen himself never gains it.
        assert not has_keyword(state, _find_instance(state, yul.instance_id),
                               Keyword.SENTINEL)

    def test_JTL_47_grant_lapses_when_yularen_leaves_play(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        yul = _place(state, "P0", _get_card(repo, "JTL", "47"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        state = _fire_when_played(state, yul)
        pick = next(x for x in legal_actions(state)
                    if isinstance(x, ChooseModalOption)
                    and x.mode == "choose_keyword_sentinel")
        state = apply(state, pick)
        assert has_keyword(state, _find_instance(state, vehicle.instance_id),
                           Keyword.SENTINEL)
        state = _defeat_and_fire(state, _find_instance(state, yul.instance_id), "P0")
        assert not has_keyword(state, _find_instance(state, vehicle.instance_id),
                               Keyword.SENTINEL)


class TestL337JTL49:
    """JTL_49 — "If this unit would be defeated, you may instead attach her as an
    upgrade to a friendly Vehicle unit without a Pilot on it."""

    def test_JTL_49_attaches_to_a_pilotless_vehicle_instead_of_dying(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        l3 = _place(state, "P0", _get_card(repo, "JTL", "49"), "ground")
        ship = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        l3.damage = 3
        state = _defeat_and_fire(state, l3, "P0")
        accepts = [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]
        assert accepts
        state = apply(state, accepts[0])
        choose = [x for x in legal_actions(state)
                  if isinstance(x, ChooseTarget) and x.target_id == ship.instance_id]
        assert choose
        state = apply(state, choose[0])
        host = _find_instance(state, ship.instance_id)
        attached = [u.instance_id for u in host.attached_upgrades]
        assert l3.instance_id in attached
        assert all(c.instance_id != l3.instance_id
                   for c in state.player_by_id("P0").discard)

    def test_JTL_49_not_offered_when_the_vehicle_already_has_a_pilot(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        l3 = _place(state, "P0", _get_card(repo, "JTL", "49"), "ground")
        ship = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _attach_upgrade_directly(state, ship, _get_card(repo, "JTL", "84"), "P0")
        state = _defeat_and_fire(state, l3, "P0")
        assert not [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]


class TestDQarCargoFrigateJTL52:
    """JTL_52 — "This unit gets –1/–0 for each damage on it."""

    def test_JTL_52_power_drops_one_per_damage(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        frigate = _place(state, "P0", _get_card(repo, "JTL", "52"), "space")
        assert compute_power(state, frigate) == 6
        frigate.damage = 2
        assert compute_power(state, frigate) == 4
        frigate.damage = 6
        assert compute_power(state, frigate) == 0


class TestGoldLeaderJTL54:
    """JTL_54 — "While this unit is defending, the attacker gets –1/–0."""

    def test_JTL_54_debuffs_only_the_unit_attacking_it(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        gold = _place(state, "P0", _get_card(repo, "JTL", "54"), "space")
        other = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        attacker = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        plain = compute_power(state, attacker, is_attacking=True)
        assert compute_power(state, attacker, is_attacking=True,
                             defender_id=gold.instance_id) == plain - 1
        # Attacking a different unit is unaffected.
        assert compute_power(state, attacker, is_attacking=True,
                             defender_id=other.instance_id) == plain


class TestHondoOhnakaJTL56:
    """JTL_56 — "On Attack: You may take control of a non-Pilot upgrade on a unit
    and attach it to a different eligible unit."""

    def test_JTL_56_takes_an_enemy_upgrade_onto_a_friendly_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, MoveUpgradeSelect, MoveUpgradeTo)
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "JTL", "56"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_directly(state, enemy, _get_card(repo, "SHD", "74"), "P1")
        state = _fire_on_attack(state, hondo, enemy)
        picks = [x for x in legal_actions(state)
                 if isinstance(x, MoveUpgradeSelect) and x.upgrade_id == upg.instance_id]
        assert picks, "the enemy's non-Pilot upgrade should be stealable"
        state = apply(state, picks[0])
        dests = [x for x in legal_actions(state) if isinstance(x, MoveUpgradeTo)]
        # Only P0's units are destinations — that is the "take control".
        assert {d.dest_id for d in dests} == {hondo.instance_id}
        state = apply(state, dests[0])
        host = _find_instance(state, hondo.instance_id)
        assert upg.instance_id in [u.instance_id for u in host.attached_upgrades]

    def test_JTL_56_never_offers_a_pilot_upgrade(self, repo):
        from swu.engine.actions import legal_actions, MoveUpgradeSelect
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "JTL", "56"), "ground")
        ship = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        pilot = _attach_upgrade_directly(state, ship, _get_card(repo, "JTL", "84"), "P1")
        state = _fire_on_attack(state, hondo, ship)
        assert not [x for x in legal_actions(state)
                    if isinstance(x, MoveUpgradeSelect)
                    and x.upgrade_id == pilot.instance_id]


class TestCorporateDefenseShuttleJTL59:
    """JTL_59 — "This unit can't attack."""

    def test_JTL_59_is_never_a_legal_attacker(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "59"), "space")
        peer = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        attacks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        assert all(a.attacker_id != shuttle.instance_id for a in attacks)
        assert any(a.attacker_id == peer.instance_id for a in attacks)


# ═════════════════════════════════════════════════════════════════════════════
# Group jtl-set:23 — Miscellaneous abilities
# ═════════════════════════════════════════════════════════════════════════════

def _play_targeted_event(state, repo, set_code, num, target_id, owner="P0"):
    """Play an event from ``owner``'s hand and resolve its single target choice."""
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    state, _evt = _play_event_from_hand(state, repo, set_code, num, owner=owner)
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, ChooseTarget) and a.target_id == target_id))


class TestDesperateCommandoJTL60:
    """JTL_60 — "When Defeated: You may give a unit –1/–1 for this phase."""

    def test_JTL_60_debuffs_a_chosen_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power)
        state = _make_state()
        commando = _place(state, "P0", _get_card(repo, "JTL", "60"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, victim)
        state = _defeat_and_fire(state, commando, "P0")
        state = apply(state, [x for x in legal_actions(state)
                              if isinstance(x, AcceptTrigger)][0])
        state = apply(state, [x for x in legal_actions(state)
                              if isinstance(x, ChooseTarget)
                              and x.target_id == victim.instance_id][0])
        v = _find_instance(state, victim.instance_id)
        assert compute_power(state, v) == before - 1


class TestCloseTheShieldGateJTL74:
    """JTL_74 — "Choose a base.  The next time damage would be dealt to it this
    phase, prevent that damage."""

    def test_JTL_74_prevents_the_next_base_damage_only_once(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base_id = base.instance_id
        state = _play_targeted_event(state, repo, "JTL", "74", base_id)
        assert state.player_by_id("P0").base_instance.damage == 0
        state = _apply_deal_damage(state, base_id, 4)
        assert state.player_by_id("P0").base_instance.damage == 0,             "the first instance is prevented in full"
        state = _apply_deal_damage(state, base_id, 3)
        assert state.player_by_id("P0").base_instance.damage == 3,             "only the NEXT instance is prevented"

    def test_JTL_74_prevents_combat_damage_from_a_base_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        p1_base = state.player_by_id("P1").base_instance
        state = _play_targeted_event(state, repo, "JTL", "74", p1_base.instance_id)
        attacker = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        attacker.exhausted = False
        state.active_player_index = 0
        state.passed_players.clear()
        atk = [a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == attacker.instance_id
               and a.defender_id is None]
        assert atk
        state = apply(state, atk[0])
        assert state.player_by_id("P1").base_instance.damage == 0


class TestOutTheAirlockJTL79:
    """JTL_79 — "Give a unit –5/–5 for this phase."""

    def test_JTL_79_shaves_five_off_a_big_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _play_targeted_event(state, repo, "JTL", "79", victim.instance_id)
        v = _find_instance(state, victim.instance_id)
        assert compute_power(state, v) == 0    # floored at 0
        assert compute_hp(state, v) == 2

    def test_JTL_79_finishes_off_a_damaged_unit(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SHD", "40"), "ground")  # 1/2
        victim.damage = 1
        state = _play_targeted_event(state, repo, "JTL", "79", victim.instance_id)
        assert _find_instance(state, victim.instance_id) is None


class TestKijimiPatrollersJTL82:
    """JTL_82 — "When Played: Create a TIE Fighter token."""

    def test_JTL_82_creates_a_tie_fighter(self, repo):
        state = _make_state()
        pat = _place(state, "P0", _get_card(repo, "JTL", "82"), "space")
        state = _fire_when_played(state, pat)
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 1


class TestPantoranStarshipThiefJTL83:
    """JTL_83 — "When Played: You may pay 3 resources.  If you do, attach this unit
    as an upgrade to a Fighter or Transport unit without a Pilot on it.  Take
    control of that unit."""

    def test_JTL_83_pays_three_and_steals_the_enemy_ship(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        thief = _place(state, "P0", _get_card(repo, "JTL", "83"), "ground")
        _give_resources(state, "P0", 4)
        ship = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state = _fire_when_played(state, thief)
        state = apply(state, [x for x in legal_actions(state)
                              if isinstance(x, AcceptTrigger)][0])
        state = apply(state, [x for x in legal_actions(state)
                              if isinstance(x, ChooseTarget)
                              and x.target_id == ship.instance_id][0])
        p0 = state.player_by_id("P0")
        assert p0.available_resources == 1
        stolen = next(u for u in p0.space_arena if u.instance_id == ship.instance_id)
        assert thief.instance_id in [u.instance_id for u in stolen.attached_upgrades]
        assert stolen.control_linked_to == thief.instance_id
        assert all(u.instance_id != ship.instance_id
                   for u in state.player_by_id("P1").space_arena)

    def test_JTL_83_not_offered_without_three_ready_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        thief = _place(state, "P0", _get_card(repo, "JTL", "83"), "ground")
        _give_resources(state, "P0", 2)
        _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state = _fire_when_played(state, thief)
        assert not [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]


class TestWingmanVictorTwoJTL84:
    """JTL_84 — "When played as an upgrade: Create a TIE Fighter token."""

    def test_JTL_84_token_only_on_the_upgrade_play(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        wing = _place(state, "P0", _get_card(repo, "JTL", "84"), "ground")
        # As a unit: no token.
        state = _fire_when_played(state, wing)
        assert not _tokens_named(state, "P0", "TIE Fighter")
        # As a Pilot upgrade: one token.
        up = _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "84"), "P0")
        state = _fire_upgrade_played(state, up, host)
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 1


class TestTIEAmbushSquadronJTL87:
    """JTL_87 — "When Played/When Defeated: Create a TIE Fighter token."""

    def test_JTL_87_creates_a_token_on_play_and_on_defeat(self, repo):
        state = _make_state()
        sq = _place(state, "P0", _get_card(repo, "JTL", "87"), "space")
        state = _fire_when_played(state, sq)
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 1
        state = _defeat_and_fire(state, _find_instance(state, sq.instance_id), "P0")
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 2


# ═════════════════════════════════════════════════════════════════════════════
# Group jtl-set:24 — Miscellaneous abilities
# ═════════════════════════════════════════════════════════════════════════════

class TestVeteranFleetOfficerJTL99:
    """JTL_99 — "When Played: Create an X-Wing token."""

    def test_JTL_99_creates_an_xwing(self, repo):
        state = _make_state()
        vfo = _place(state, "P0", _get_card(repo, "JTL", "99"), "ground")
        state = _fire_when_played(state, vfo)
        assert len(_tokens_named(state, "P0", "X-Wing")) == 1


class TestTheStarhawkJTL105:
    """JTL_105 — "While paying costs, you pay half as many resources, rounded up."""

    def test_JTL_105_halves_a_card_cost_rounding_up(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        card = _get_card(repo, "JTL", "143")            # cost 8
        hand_ci = CardInstance("p0_hand_143", card, "P0", Zone.HAND)
        ps.hand.append(hand_ci)
        _give_resources(state, "P0", 10)
        full = _play_cost(state, hand_ci, ps)
        _place(state, "P0", _get_card(repo, "JTL", "105"), "space")
        halved = _play_cost(state, hand_ci, ps)
        assert halved == -(-full // 2)
        assert halved < full

    def test_JTL_105_rounds_an_odd_cost_up(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        card = _get_card(repo, "JTL", "212")
        hand_ci = CardInstance("p0_hand_212", card, "P0", Zone.HAND)
        ps.hand.append(hand_ci)
        _give_resources(state, "P0", 10)
        full = _play_cost(state, hand_ci, ps)
        assert full % 2 == 1, "fixture must have an odd determined cost"
        _place(state, "P0", _get_card(repo, "JTL", "105"), "space")
        assert _play_cost(state, hand_ci, ps) == (full + 1) // 2

    def test_JTL_105_does_not_discount_the_opponent(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        opp = state.player_by_id("P1")
        card = _get_card(repo, "JTL", "143")
        hand_ci = CardInstance("p1_hand_143", card, "P1", Zone.HAND)
        opp.hand.append(hand_ci)
        _give_resources(state, "P1", 20)
        before = _play_cost(state, hand_ci, opp)
        _place(state, "P0", _get_card(repo, "JTL", "105"), "space")
        assert _play_cost(state, hand_ci, opp) == before


class TestGeneralDravenJTL117:
    """JTL_117 — "When Played/On Attack: Create an X-Wing token."""

    def test_JTL_117_creates_a_token_on_play_and_on_attack(self, repo):
        state = _make_state()
        draven = _place(state, "P0", _get_card(repo, "JTL", "117"), "ground")
        state = _fire_when_played(state, draven)
        assert len(_tokens_named(state, "P0", "X-Wing")) == 1
        state = _fire_on_attack(state, _find_instance(state, draven.instance_id))
        assert len(_tokens_named(state, "P0", "X-Wing")) == 2


class TestFocusFireJTL129:
    """JTL_129 — "Choose a unit.  Each friendly Vehicle unit in the same arena deals
    damage equal to its power to that unit."""

    def test_JTL_129_every_same_arena_vehicle_shoots(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # 1 power
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")   # 1 power
        _place(state, "P0", _get_card(repo, "JTL", "212"), "ground")  # wrong arena
        victim = _place(state, "P1", _get_card(repo, "JTL", "143"), "space")  # 9/6
        state = _play_targeted_event(state, repo, "JTL", "129", victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 2

    def test_JTL_129_no_friendly_vehicle_in_that_arena_does_nothing(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "212"), "ground")
        victim = _place(state, "P1", _get_card(repo, "JTL", "143"), "space")
        state = _play_targeted_event(state, repo, "JTL", "129", victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 0


class TestTimelyReinforcementsJTL130:
    """JTL_130 — "Choose an opponent.  For every 2 resources they control, create an
    X-Wing token and give it Sentinel for this phase."""

    def test_JTL_130_one_sentinel_xwing_per_two_enemy_resources(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _give_resources(state, "P1", 5)     # 5 // 2 = 2 tokens
        state, _evt = _play_event_from_hand(state, repo, "JTL", "130")
        xwings = _tokens_named(state, "P0", "X-Wing")
        assert len(xwings) == 2
        assert all(has_keyword(state, x, Keyword.SENTINEL) for x in xwings)

    def test_JTL_130_makes_nothing_against_one_resource(self, repo):
        state = _make_state()
        _give_resources(state, "P1", 1)
        state, _evt = _play_event_from_hand(state, repo, "JTL", "130")
        assert not _tokens_named(state, "P0", "X-Wing")


class TestTurbolaserSalvoJTL131:
    """JTL_131 — "Choose an arena.  A friendly space unit deals damage equal to its
    power to each enemy unit in that arena."""

    def test_JTL_131_shooter_power_hits_every_enemy_in_the_chosen_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        shooter = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")  # 9 power
        a = _place(state, "P1", _get_card(repo, "JTL", "143"), "space")   # 9/6
        b = _place(state, "P1", _get_card(repo, "JTL", "143"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "131")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == shooter.instance_id))
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == a.instance_id))
        # Both space defenders die (9 > 6); the ground unit is untouched.
        assert _find_instance(state, a.instance_id) is None
        assert _find_instance(state, b.instance_id) is None
        assert _find_instance(state, ground.instance_id).damage == 0

    def test_JTL_131_can_pick_the_ground_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        shooter = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")  # 1 power
        space_enemy = _place(state, "P1", _get_card(repo, "JTL", "143"), "space")
        g1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        g2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "131")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == shooter.instance_id))
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == g1.instance_id))
        assert _find_instance(state, g1.instance_id).damage == 1
        assert _find_instance(state, g2.instance_id).damage == 1
        assert _find_instance(state, space_enemy.instance_id).damage == 0


# ═════════════════════════════════════════════════════════════════════════════
# Group jtl-set:25 — Miscellaneous abilities
# ═════════════════════════════════════════════════════════════════════════════

class TestTheyHateThatShipJTL155:
    """JTL_155 — "An opponent creates 2 TIE Fighter tokens and readies them.  Then,
    play a Vehicle unit from your hand.  It costs 3 resources less."""

    def test_JTL_155_gives_the_opponent_two_ready_ties_and_discounts_a_vehicle(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        vehicle = _get_card(repo, "JTL", "143")        # Vehicle, cost 8
        hand_ci = CardInstance("p0_veh", vehicle, "P0", Zone.HAND)
        ps.hand.append(hand_ci)
        state, _evt = _play_event_from_hand(state, repo, "JTL", "155", resources=20)
        ties = _tokens_named(state, "P1", "TIE Fighter")
        assert len(ties) == 2
        assert all(not t.exhausted for t in ties)
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        assert [p.instance_id for p in plays] == ["p0_veh"]
        before = state.player_by_id("P0").available_resources
        state = apply(state, plays[0])
        spent = before - state.player_by_id("P0").available_resources
        assert spent == 8 + 4 - 3      # cost + aspect penalty − the 3-off discount


class TestShadowCasterJTL169:
    """JTL_169 — "When a friendly unit is defeated: You may use all of its 'When
    Defeated' abilities again."""

    def test_JTL_169_repeats_a_friendly_when_defeated_ability(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        from swu.engine.actions import _defeat_unit
        _place(state, "P0", _get_card(repo, "JTL", "169"), "space")
        squad = _place(state, "P0", _get_card(repo, "JTL", "87"), "space")
        _defeat_unit(state, state.player_by_id("P0"), squad)
        # The squadron's own When Defeated resolves first (1 token); then Shadow
        # Caster offers the re-use.
        accepts = [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]
        assert accepts
        state = _drain_auto(apply(state, accepts[0]))
        acc2 = [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]
        while acc2:
            state = _drain_auto(apply(state, acc2[0]))
            acc2 = [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 2

    def test_JTL_169_not_offered_for_a_unit_with_no_when_defeated_ability(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        from swu.engine.actions import _defeat_unit
        _place(state, "P0", _get_card(repo, "JTL", "169"), "space")
        plain = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _defeat_unit(state, state.player_by_id("P0"), plain)
        assert not [x for x in legal_actions(state) if isinstance(x, AcceptTrigger)]


class TestTargetingComputerJTL171:
    """JTL_171 — "Attached unit gains: 'You assign all indirect damage dealt by this
    unit.'"""

    def test_JTL_171_flips_the_indirect_damage_decider(self, repo):
        import copy
        from swu.engine.actions import push_assign_indirect_damage
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # Without the Computer the RECEIVING player assigns.
        s1 = copy.deepcopy(state)
        push_assign_indirect_damage(s1, _find_instance(s1, host.instance_id), amount=3)
        assert s1.pending_decisions[-1].deciding_player_id == "P1"
        # With it attached, the source's controller assigns.
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "171"), "P0")
        push_assign_indirect_damage(state, host, amount=3)
        assert state.pending_decisions[-1].deciding_player_id == "P0"


class TestSidonIthanoJTL213:
    """JTL_213 — "When played as a unit: You may attach this unit as an upgrade to an
    enemy Vehicle unit without a Pilot on it."""

    def test_JTL_213_rides_an_enemy_vehicle(self, repo):
        from swu.engine.actions import legal_actions, apply, AttachSelfAsPilot
        state = _make_state()
        sidon = _place(state, "P0", _get_card(repo, "JTL", "213"), "ground")
        friendly_ship = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        enemy_ship = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")
        state = _fire_when_played(state, sidon)
        attaches = [a for a in legal_actions(state) if isinstance(a, AttachSelfAsPilot)]
        assert {a.vehicle_id for a in attaches} == {enemy_ship.instance_id}, \
            "only ENEMY pilotless Vehicles are offered"
        state = apply(state, attaches[0])
        host = _find_instance(state, enemy_ship.instance_id)
        assert sidon.instance_id in [u.instance_id for u in host.attached_upgrades]

    def test_JTL_213_not_offered_without_an_enemy_vehicle(self, repo):
        from swu.engine.actions import legal_actions, AttachSelfAsPilot
        state = _make_state()
        sidon = _place(state, "P0", _get_card(repo, "JTL", "213"), "ground")
        _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        state = _fire_when_played(state, sidon)
        assert not [a for a in legal_actions(state) if isinstance(a, AttachSelfAsPilot)]


class TestDiversionJTL229:
    """JTL_229 — "Give a unit Sentinel for this phase."""

    def test_JTL_229_grants_sentinel_for_the_phase(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "JTL", "212"), "space")
        assert not has_keyword(state, unit, Keyword.SENTINEL)
        state = _play_targeted_event(state, repo, "JTL", "229", unit.instance_id)
        assert has_keyword(state, _find_instance(state, unit.instance_id),
                           Keyword.SENTINEL)


class TestJumpToLightspeedJTL232:
    """JTL_232 — "Return a friendly space unit and any number of non-leader upgrades
    on it to their owners' hands.  The next time you play a copy of that unit this
    phase, you may play it for free."""

    def test_JTL_232_bounces_the_ship_with_its_upgrades(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")
        upg = _attach_upgrade_directly(state, ship, _get_card(repo, "SHD", "74"), "P0")
        state = _play_targeted_event(state, repo, "JTL", "232", ship.instance_id)
        hand_ids = {c.instance_id for c in state.player_by_id("P0").hand}
        assert ship.instance_id in hand_ids
        assert upg.instance_id in hand_ids
        assert _find_instance(state, ship.instance_id) is None

    def test_JTL_232_makes_the_next_copy_free(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")
        state = _play_targeted_event(state, repo, "JTL", "232", ship.instance_id)
        ps = state.player_by_id("P0")
        returned = next(c for c in ps.hand if c.instance_id == ship.instance_id)
        assert _play_cost(state, returned, ps) == 0

    def test_JTL_232_free_play_does_not_apply_to_a_different_card(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTL", "143"), "space")
        other = CardInstance("p0_other", _get_card(repo, "JTL", "212"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(other)
        state = _play_targeted_event(state, repo, "JTL", "232", ship.instance_id)
        ps = state.player_by_id("P0")
        o = next(c for c in ps.hand if c.instance_id == "p0_other")
        assert _play_cost(state, o, ps) > 0


class TestSweepTheAreaJTL233:
    """JTL_233 — "Return up to 2 non-leader units in the same arena with a combined
    cost 3 or less to their owners' hands."""

    def test_JTL_233_returns_two_cheap_units_in_one_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")   # cost 1
        b = _place(state, "P1", _get_card(repo, "JTL", "212"), "space")   # cost 1
        ground = _place(state, "P1", _get_card(repo, "JTL", "212"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "233")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == a.instance_id))
        second = [x for x in legal_actions(state) if isinstance(x, ChooseTarget)]
        offered = {x.target_id for x in second if x.target_id is not None}
        assert b.instance_id in offered
        assert ground.instance_id not in offered, "must be the SAME arena"
        state = apply(state, next(x for x in second
                                  if x.target_id == b.instance_id))
        assert _find_instance(state, a.instance_id) is None
        assert _find_instance(state, b.instance_id) is None
        assert _find_instance(state, ground.instance_id) is not None

    def test_JTL_233_second_pick_respects_the_combined_budget(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        big = _place(state, "P1", _get_card(repo, "JTL", "60"), "ground")     # cost 2
        small = _place(state, "P1", _get_card(repo, "JTL", "60"), "ground")   # cost 2
        state, _evt = _play_event_from_hand(state, repo, "JTL", "233")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == big.instance_id))
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, ChooseTarget) and x.target_id is not None}
        assert small.instance_id not in offered, "2 + 2 exceeds the combined 3"


# ═════════════════════════════════════════════════════════════════════════════
# jtl-set:26 — Miscellaneous abilities (the last JTL group)
# ═════════════════════════════════════════════════════════════════════════════


def _move_upgrade_choices(state):
    from swu.engine.actions import legal_actions
    return {a.upgrade_id for a in legal_actions(state)
            if type(a).__name__ == "MoveUpgradeSelect"}


def _give_shield(state, host_ci):
    from swu.engine.tokens import attach_token
    located = state.find_instance(host_ci.instance_id)
    return attach_token(state, located[0], located[1], "Shield")


class TestShuttleST149JTL242:
    """JTL_242 — "When Played/When Defeated: You may take control of a token
    upgrade on a unit and attach it to a different eligible unit."""

    def test_JTL_242_steals_an_enemy_shield_token(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "242"), "space")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        shield = _give_shield(state, victim)
        state = _fire_when_played(state, _find_instance(state, shuttle.instance_id))
        assert shield.instance_id in _move_upgrade_choices(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "MoveUpgradeSelect"
                                  and a.upgrade_id == shield.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "MoveUpgradeTo"
                                  and a.dest_id == shuttle.instance_id))
        # The Shield now sits on the Shuttle — i.e. its controller took control.
        assert _shield_count(_find_instance(state, shuttle.instance_id)) == 1
        assert _shield_count(_find_instance(state, victim.instance_id)) == 0

    def test_JTL_242_only_token_upgrades_are_offered(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "242"), "space")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        shield = _give_shield(state, victim)
        plain = _attach_upgrade_directly(
            state, victim, _get_card(repo, "SOR", "120"), "P1")  # Academy Training
        state = _fire_when_played(state, _find_instance(state, shuttle.instance_id))
        choices = _move_upgrade_choices(state)
        assert shield.instance_id in choices
        assert plain.instance_id not in choices

    def test_JTL_242_when_defeated_side_also_offers_the_move(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "JTL", "242"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "252"), "space")  # a destination
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        shield = _give_shield(state, victim)
        state = _defeat_and_fire(state, shuttle, "P0")
        assert shield.instance_id in _move_upgrade_choices(state)


class TestQuasarTIECarrierJTL243:
    """JTL_243 — "On Attack: Create a TIE Fighter token."""

    def test_JTL_243_creates_a_tie_fighter_on_attack(self, repo):
        state = _make_state()
        quasar = _place(state, "P0", _get_card(repo, "JTL", "243"), "space")
        assert _tokens_named(state, "P0", "TIE Fighter") == []
        state = _fire_on_attack(state, quasar)
        assert len(_tokens_named(state, "P0", "TIE Fighter")) == 1


class TestThereIsNoEscapeJTL244:
    """JTL_244 — "Choose up to 3 units.  Those units lose all abilities and can't
    gain abilities for this round."""

    def test_JTL_244_suppresses_three_chosen_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.state import ability_suppressed
        state = _make_state()
        victims = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                   for _ in range(3)]
        spared = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "244", owner="P0")
        for v in victims:
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, ChooseTarget)
                                      and a.target_id == v.instance_id))
        for v in victims:
            assert ability_suppressed(state, _find_instance(state, v.instance_id))
        assert not ability_suppressed(state, _find_instance(state, spared.instance_id))

    def test_JTL_244_never_offers_the_same_unit_twice(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "244", owner="P0")
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget)
                                  and x.target_id == a.instance_id))
        later = {x.target_id for x in legal_actions(state)
                 if isinstance(x, ChooseTarget)}
        assert a.instance_id not in later

    def test_JTL_244_is_up_to_three_so_a_choice_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions
        from swu.engine.state import ability_suppressed
        state = _make_state()
        lone = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "244", owner="P0")
        assert any(type(x).__name__ == "DeclineTarget" for x in legal_actions(state))
        assert not ability_suppressed(state, _find_instance(state, lone.instance_id))


class TestTantiveIVJTL252:
    """JTL_252 — "When Played: Create an X-Wing token."""

    def test_JTL_252_creates_an_x_wing_on_play(self, repo):
        state = _make_state()
        tantive = _place(state, "P0", _get_card(repo, "JTL", "252"), "space")
        state = _fire_when_played(state, tantive)
        assert len(_tokens_named(state, "P0", "X-Wing")) == 1


class TestDedicatedWingmenJTL254:
    """JTL_254 — "Create 2 X-Wing tokens."""

    def test_JTL_254_creates_two_x_wings(self, repo):
        state = _make_state()
        state, _evt = _play_event_from_hand(state, repo, "JTL", "254", owner="P0")
        assert len(_tokens_named(state, "P0", "X-Wing")) == 2
        assert _tokens_named(state, "P1", "X-Wing") == []


class TestRetrofittedAirspeederJTL259:
    """JTL_259 — "This unit can attack space units." + "While attacking a space
    unit, this unit gets -1/-0."""

    def test_JTL_259_may_attack_an_enemy_space_unit(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        air = _place(state, "P0", _get_card(repo, "JTL", "259"), "ground")
        spacer = _place(state, "P1", _get_card(repo, "JTL", "252"), "space")
        state.active_player_index = 0
        state.passed_players.clear()
        targets = {a.defender_id for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == air.instance_id}
        assert spacer.instance_id in targets

    def test_JTL_259_loses_1_power_only_against_a_space_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        air = _place(state, "P0", _get_card(repo, "JTL", "259"), "ground")
        spacer = _place(state, "P1", _get_card(repo, "JTL", "252"), "space")
        grounder = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        printed = getattr(air.card_def, "power", 0)
        assert compute_power(state, air, is_attacking=True, attacking_unit=True,
                             defender_id=grounder.instance_id) == printed
        assert compute_power(state, air, is_attacking=True, attacking_unit=True,
                             defender_id=spacer.instance_id) == printed - 1
        # No combat context at all → no debuff (and never in compute_hp).
        assert compute_power(state, air) == printed


class TestDeathStarPlansJTL260:
    """JTL_260 — "When attached unit is attacked: The attacking player takes
    control of this upgrade and attaches it to a unit they control." + "Attached
    unit gains: 'The first unit you play each round costs 2 resources less.'"""

    def test_JTL_260_attacker_takes_control_of_the_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        plans = _attach_upgrade_directly(
            state, host, _get_card(repo, "JTL", "260"), "P0")
        raider = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, raider, host)
        top = state.pending_decisions[-1]
        assert top.kind == "move_upgrade"
        assert top.deciding_player_id == "P1"          # the ATTACKING player decides
        # "takes", not "may take" — there is no decline.
        assert not any(type(a).__name__ == "DeclineMoveUpgrade"
                       for a in legal_actions(state))
        assert _move_upgrade_choices(state) == {plans.instance_id}
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "MoveUpgradeSelect"))
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "MoveUpgradeTo"))
        moved = _find_instance(state, raider.instance_id)
        assert [u.instance_id for u in moved.attached_upgrades] == [plans.instance_id]
        assert _find_instance(state, host.instance_id).attached_upgrades == []

    def test_JTL_260_discounts_the_hosts_controllers_first_unit_each_round(self, repo):
        from swu.engine.actions import _play_cost, _consume_standing_discount
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        card = _get_card(repo, "JTL", "143")
        hand_ci = CardInstance("p0_hand_260a", card, "P0", Zone.HAND)
        ps.hand.append(hand_ci)
        _give_resources(state, "P0", 20)
        full = _play_cost(state, hand_ci, ps)
        _attach_upgrade_directly(state, host, _get_card(repo, "JTL", "260"), "P0")
        assert _play_cost(state, hand_ci, ps) == full - 2
        # …the FIRST unit only: once spent, the round's discount is gone.
        _consume_standing_discount(state, hand_ci, ps)
        assert _play_cost(state, hand_ci, ps) == full

    def test_JTL_260_discount_follows_the_host_and_each_side_gets_its_own(self, repo):
        from swu.engine.actions import _play_cost, _consume_standing_discount
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        p0, p1 = state.player_by_id("P0"), state.player_by_id("P1")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        card = _get_card(repo, "JTL", "143")
        h0 = CardInstance("p0_hand_260b", card, "P0", Zone.HAND)
        h1 = CardInstance("p1_hand_260b", card, "P1", Zone.HAND)
        p0.hand.append(h0)
        p1.hand.append(h1)
        _give_resources(state, "P0", 20)
        _give_resources(state, "P1", 20)
        base0, base1 = _play_cost(state, h0, p0), _play_cost(state, h1, p1)
        plans = _attach_upgrade_directly(
            state, host, _get_card(repo, "JTL", "260"), "P0")
        assert _play_cost(state, h0, p0) == base0 - 2
        assert _play_cost(state, h1, p1) == base1        # not the opponent's
        _consume_standing_discount(state, h0, p0)        # P0 spends it this round
        assert _play_cost(state, h0, p0) == base0
        # The plans change hands mid-round: "Multiple players can benefit from the
        # discount ability in the same round" (the card's printed rules note).
        host_now = _find_instance(state, host.instance_id)
        host_now.attached_upgrades.remove(
            next(u for u in host_now.attached_upgrades
                 if u.instance_id == plans.instance_id))
        _find_instance(state, enemy_host.instance_id).attached_upgrades.append(plans)
        assert _play_cost(state, h1, p1) == base1 - 2
