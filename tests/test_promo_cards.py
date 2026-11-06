"""Promo / anthology reprint-duplicate tests — the batch-19 easy-encode sweep.

Every card composes from existing engine primitives (no new decision kind; the
one seam is a scaling ``StatBonus`` count for Qi'ra).  Method names embed the
card number so the reprint/encoding tooling's ``-k`` gate selects them.  Reuses
the DB-backed helpers from the SOR/SHD/LOF card tests.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _place_leader, _fire_when_played,
    _fire_on_attack, _defeat_and_fire, _find_instance, _give_resources,
    _experience_count,
)
from tests.test_shd_cards import _put_in_hand, _fire_card_played, _deploy_leader_as_unit
from tests.test_sor_cards import (
    _play_aspect_event, _pick_option, _choose, _auto_resolve,
)
from tests.test_jtl_cards import _fire_attack_ends_jtl as _fire_attack_ends
from tests.test_twi_cards import _resolve_attack


def _drain(state):
    """Apply AutoResolveEffects to quiescence (for no-target CustomEffects that do
    not auto-run on AcceptTrigger — the batch-18 gotcha)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(20):
        act = next((a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects)), None)
        if act is None:
            break
        state = apply(state, act)
    return state


def _accept(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, AcceptTrigger)))


def _attach_upgrade(state, host_ci, upgrade_def, owner_id):
    from swu.engine.state import CardInstance
    up = CardInstance(
        instance_id=f"{owner_id}_up_{upgrade_def.set_code}_{upgrade_def.card_number}",
        card_def=upgrade_def, owner_id=owner_id, zone=host_ci.zone,
    )
    host_ci.attached_upgrades.append(up)
    return up


# ── Plain triggers / constants ────────────────────────────────────────────────

class TestHanSoloP2681:
    """P26_81 — On Attack: Give an Experience token to this unit."""

    def test_p26_81_on_attack_gives_self_experience(self, repo):
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "P26", "81"), "ground")
        state = _fire_on_attack(state, han)
        state = _drain(state)
        assert _experience_count(_find_instance(state, han.instance_id)) == 1


class TestBosskP251:
    """P25_1 — On Attack: Exhaust the defender and deal 1 damage to it."""

    def test_p25_1_on_attack_exhausts_and_damages_defender(self, repo):
        state = _make_state()
        bossk = _place(state, "P0", _get_card(repo, "P25", "1"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, bossk, defender)
        state = _drain(state)
        d = _find_instance(state, defender.instance_id)
        assert d.exhausted and d.damage == 1


class TestChewbaccaJTLP7:
    """JTLP_7 — can't be defeated/returned by ENEMY card abilities (Protection)."""

    def test_jtlp_7_enemy_defeat_is_blocked_friendly_is_not(self, repo):
        from swu.abilities.resolver import _target_protected
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "JTLP", "7"), "ground")
        enemy_src = CardInstance(instance_id="P1_src",
                                 card_def=_get_card(repo, "SOR", "46"),
                                 owner_id="P1", zone=Zone.GROUND_ARENA)
        friend_src = CardInstance(instance_id="P0_src",
                                  card_def=_get_card(repo, "SOR", "46"),
                                  owner_id="P0", zone=Zone.GROUND_ARENA)
        assert _target_protected(state, chewie.instance_id, enemy_src, "defeat")
        assert _target_protected(state, chewie.instance_id, enemy_src, "return")
        assert not _target_protected(state, chewie.instance_id, friend_src, "defeat")


class TestDarthVaderASH243:
    """ASH_243 — While this unit is ready, he gains Sentinel."""

    def test_ash_243_sentinel_only_while_ready(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "ASH", "243"), "ground")
        vader.exhausted = False
        assert has_keyword(state, vader, Keyword.SENTINEL)
        vader.exhausted = True
        assert not has_keyword(state, vader, Keyword.SENTINEL)


class TestDarthTyranusP2596:
    """P25_96 — While the Force is with you, this unit gains Ambush."""

    def test_p25_96_ambush_only_with_force_token(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tyr = _place(state, "P0", _get_card(repo, "P25", "96"), "ground")
        state.player_by_id("P0").has_force_token = False
        assert not has_keyword(state, tyr, Keyword.AMBUSH)
        state.player_by_id("P0").has_force_token = True
        assert has_keyword(state, tyr, Keyword.AMBUSH)


class TestObiWanG253:
    """G25_3 — When you play a Force unit: gains Sentinel for this phase."""

    def test_g25_3_gains_sentinel_when_force_unit_played(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from tests.test_lof_cards import _fire_card_played
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "G25", "3"), "ground")
        assert not has_keyword(state, obi, Keyword.SENTINEL)
        other = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # Force
        state = _fire_card_played(state, other)
        state = _drain(state)
        assert has_keyword(state, _find_instance(state, obi.instance_id),
                           Keyword.SENTINEL)


class TestGeneralGrievousJ2518:
    """J25_18 — When this unit is attacked: Return him to his owner's hand."""

    def test_j25_18_returns_self_to_hand_when_attacked(self, repo):
        state = _make_state()
        grievous = _place(state, "P0", _get_card(repo, "J25", "18"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, attacker, grievous)
        state = _drain(state)
        assert _find_instance(state, grievous.instance_id) is None
        assert any(c.instance_id == grievous.instance_id
                   for c in state.player_by_id("P0").hand)


class TestEmperorPalpatineC243:
    """C24_3 — When Played: Deal 6 damage divided among enemy units."""

    def test_c24_3_pushes_distribute_damage(self, repo):
        state = _make_state()
        palp = _place(state, "P0", _get_card(repo, "C24", "3"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, palp)
        assert state.pending_decisions[-1].kind == "distribute_damage"


class TestNabooRoyalStarshipP2675:
    """P26_75 — Each friendly leader unit gains Raid 2 and Overwhelm."""

    def test_p26_75_grants_raid2_overwhelm_to_leader_units(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "P26", "75"), "ground")  # Naboo (Vehicle)
        leader = _place(state, "P0", _get_card(repo, "SOR", "5"), "ground")  # Luke leader
        leader.deployed = True
        lu = _find_instance(state, leader.instance_id)
        assert keyword_value(state, lu, Keyword.RAID) == 2
        assert has_keyword(state, lu, Keyword.OVERWHELM)


class TestBlackOneP257:
    """P25_7 — While upgraded +1/+0; On Attack: if you control Poe Dameron, may
    deal 1 to a unit."""

    def test_p25_7_plus_one_power_while_upgraded(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        black = _place(state, "P0", _get_card(repo, "P25", "7"), "space")  # 2/3
        assert compute_power(state, black) == 2
        _attach_upgrade(state, black, _get_card(repo, "SOR", "63"), "P0")
        assert compute_power(state, _find_instance(state, black.instance_id)) == 3

    def test_p25_7_on_attack_needs_poe_dameron(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        black = _place(state, "P0", _get_card(repo, "P25", "7"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state_no_poe = _fire_on_attack(state, black)
        assert not any(isinstance(a, AcceptTrigger)
                       for a in legal_actions(state_no_poe))
        # With Poe Dameron in play the optional trigger is offered.
        state2 = _make_state()
        black2 = _place(state2, "P0", _get_card(repo, "P25", "7"), "space")
        _place(state2, "P0", _get_card(repo, "SHD", "153"), "space")  # Poe Dameron
        _place(state2, "P1", _get_card(repo, "SOR", "46"), "ground")
        state2 = _fire_on_attack(state2, black2)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state2))

    def test_p25_157_registered_same_mechanic(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        black = _place(state, "P0", _get_card(repo, "P25", "157"), "space")
        assert compute_power(state, black) == 2
        _attach_upgrade(state, black, _get_card(repo, "SOR", "63"), "P0")
        assert compute_power(state, _find_instance(state, black.instance_id)) == 3


# ── "You may use the Force" cards ─────────────────────────────────────────────

class TestMaceWinduLOFP10:
    """LOFP_10 — When Played: you may use the Force → deal 4 to a unit."""

    def test_lofp_10_use_force_deals_4(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        mace = _place(state, "P0", _get_card(repo, "LOFP", "10"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, mace)
        state = _accept(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4
        assert not state.player_by_id("P0").has_force_token

    def test_lofp_10_decline_keeps_token(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        mace = _place(state, "P0", _get_card(repo, "LOFP", "10"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, mace)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").has_force_token

    def test_lofp_10_no_token_no_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        mace = _place(state, "P0", _get_card(repo, "LOFP", "10"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, mace)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestVernestraRwohP25129:
    """P25_129 — When Played: you may use the Force → ready this unit."""

    def test_p25_129_use_force_readies_self(self, repo):
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        vern = _place(state, "P0", _get_card(repo, "P25", "129"), "ground")
        vern.exhausted = True
        state = _fire_when_played(state, vern)
        state = _accept(state)
        state = _drain(state)
        assert not _find_instance(state, vern.instance_id).exhausted
        assert not state.player_by_id("P0").has_force_token


class TestKarisP25151:
    """P25_151 — When Defeated: you may use the Force → give a unit -2/-2."""

    def test_p25_151_use_force_debuffs_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        karis = _place(state, "P0", _get_card(repo, "P25", "151"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _defeat_and_fire(state, karis, "P0")
        state = _accept(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 1
        assert not state.player_by_id("P0").has_force_token


class TestDarthSidiousG252:
    """G25_2 — When Played: you may use the Force → defeat each non-Sith unit with
    3 or less remaining HP."""

    def test_g25_2_use_force_wipes_low_hp_non_sith(self, repo):
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        sid = _place(state, "P0", _get_card(repo, "G25", "2"), "ground")  # Sith
        weak = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, sid)
        state = _accept(state)
        state = _drain(state)
        assert _find_instance(state, weak.instance_id) is None       # defeated
        assert _find_instance(state, tough.instance_id) is not None  # survives
        assert _find_instance(state, sid.instance_id) is not None    # Sith, spared
        assert not state.player_by_id("P0").has_force_token


# ── Qi'ra: scaling self-debuff + discard-then-deal ────────────────────────────

class TestQiraASH226:
    """ASH_226 — -1/-0 per card in hand; When Played: may discard → deal 3."""

    def test_ash_226_power_scales_down_with_hand(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        qira = _place(state, "P0", _get_card(repo, "ASH", "226"), "ground")  # 9/7
        state.player_by_id("P0").hand = []
        assert compute_power(state, qira) == 9
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        assert compute_power(state, _find_instance(state, qira.instance_id)) == 7

    def test_ash_226_discard_deals_3(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        qira = _place(state, "P0", _get_card(repo, "ASH", "226"), "ground")
        state.player_by_id("P0").hand = []
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "128"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, qira)
        state = _accept(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert len(state.player_by_id("P0").hand) == hand_before - 1


# ── BB-8: play-as-upgrade pay-then-ready ──────────────────────────────────────

class TestBB8C252:
    """C25_2 — When played as an upgrade: you may pay 2 → ready a Resistance unit."""

    def test_c25_2_as_upgrade_pays_and_readies_resistance(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        _give_resources(state, "P0", 3, repo)
        host = _place(state, "P0", _get_card(repo, "SHD", "153"), "space")  # Poe (Resist)
        host.exhausted = True
        bb8 = _attach_upgrade(state, host, _get_card(repo, "C25", "2"), "P0")
        ready_before = sum(1 for r in state.player_by_id("P0").resources
                           if not r.exhausted)
        state = _fire_upgrade_played(state, bb8, host)
        state = _accept(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == host.instance_id))
        assert not _find_instance(state, host.instance_id).exhausted
        ready_after = sum(1 for r in state.player_by_id("P0").resources
                          if not r.exhausted)
        assert ready_after == ready_before - 2

    def test_c25_2_not_offered_without_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SHD", "153"), "space")
        host.exhausted = True
        bb8 = _attach_upgrade(state, host, _get_card(repo, "C25", "2"), "P0")
        state = _fire_upgrade_played(state, bb8, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── Stage 4 batch 26 — the select_extreme "least remaining HP" target selector ──

class TestDarthNihilusP2679:
    """P26_79 — "When Played/On Attack: Deal 3 damage to the unit with the least
    remaining HP among other units. If it's a non-Vehicle unit, give an Experience
    token to this unit."  The keystone is the new
    ``TargetSpec.select_extreme="least_remaining_hp"`` set-relative selector."""

    def _ct_ids(self, state):
        from swu.engine.actions import legal_actions, ChooseTarget
        return {a.target_id for a in legal_actions(state)
                if isinstance(a, ChooseTarget)}

    def _choose(self, state, target_id):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        return apply(state, next(a for a in legal_actions(state)
                                 if isinstance(a, ChooseTarget)
                                 and a.target_id == target_id))

    def test_p26_79_when_played_hits_only_least_remaining_hp(self, repo):
        state = _make_state()
        nih = _place(state, "P0", _get_card(repo, "P26", "79"), "ground")
        high = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        high.damage = 0                                                     # remaining 7
        low = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        low.damage = 3                                                      # remaining 4 (min)
        state = _fire_when_played(state, nih)
        # Only the least-remaining-HP unit is offered.
        assert self._ct_ids(state) == {low.instance_id}
        state = self._choose(state, low.instance_id)
        assert _find_instance(state, low.instance_id).damage == 6           # 3 + 3, survives
        assert _find_instance(state, high.instance_id).damage == 0          # untouched
        # Non-Vehicle target → Nihilus gains an Experience token.
        assert _experience_count(_find_instance(state, nih.instance_id)) == 1

    def test_p26_79_ties_offer_every_minimum(self, repo):
        state = _make_state()
        nih = _place(state, "P0", _get_card(repo, "P26", "79"), "ground")
        tie_a = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # 3/3, remaining 3
        tie_b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        tie_b.damage = 4                                                     # remaining 3 (ties tie_a)
        higher = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground") # remaining 7
        state = _fire_when_played(state, nih)
        assert self._ct_ids(state) == {tie_a.instance_id, tie_b.instance_id}
        assert higher.instance_id not in self._ct_ids(state)

    def test_p26_79_excludes_self_and_includes_friendly(self, repo):
        state = _make_state()
        nih = _place(state, "P0", _get_card(repo, "P26", "79"), "ground")  # 6/6
        nih.damage = 5                                                     # remaining 1 (lowest overall)
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # remaining 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # remaining 7
        state = _fire_when_played(state, nih)
        # "Among OTHER units" — Nihilus is never a target despite the lowest HP;
        # the friendly (min among others) is offered, the higher-HP enemy is not.
        assert self._ct_ids(state) == {friendly.instance_id}
        state = self._choose(state, friendly.instance_id)
        assert _find_instance(state, friendly.instance_id) is None          # 3/3 takes 3 → defeated
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert _experience_count(_find_instance(state, nih.instance_id)) == 1

    def test_p26_79_vehicle_target_gives_no_experience(self, repo):
        state = _make_state()
        nih = _place(state, "P0", _get_card(repo, "P26", "79"), "ground")
        veh = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")   # TIE Fighter 2/1, Vehicle
        state = _fire_when_played(state, nih)
        assert self._ct_ids(state) == {veh.instance_id}
        state = self._choose(state, veh.instance_id)
        assert _find_instance(state, veh.instance_id) is None               # defeated
        # Vehicle target → NO Experience.
        assert _experience_count(_find_instance(state, nih.instance_id)) == 0

    def test_p26_79_on_attack_also_fires(self, repo):
        state = _make_state()
        nih = _place(state, "P0", _get_card(repo, "P26", "79"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7, remaining 7
        state = _fire_on_attack(state, nih)                                  # attacking the base
        assert self._ct_ids(state) == {enemy.instance_id}
        state = self._choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert _experience_count(_find_instance(state, nih.instance_id)) == 1


# ── Stage 4 batch 27 — permanent keyword-grant that ends when its source leaves ─
#    play (the keyword-layer mirror of Huyang TWI_110's permanent stat modifier) ──

class TestBD1C254:
    """C25_4 — "When Played: Choose another friendly unit. While this unit is in
    play, the chosen unit gets +1/+0 and gains Saboteur."  Two ``permanent``
    modifiers sourced by BD-1; the granted Saboteur exercises the new keyword-layer
    source-in-play guard (``has_keyword``/``keyword_value``)."""

    def _ct_ids(self, state):
        from swu.engine.actions import legal_actions, ChooseTarget
        return {a.target_id for a in legal_actions(state)
                if isinstance(a, ChooseTarget)}

    def _choose(self, state, target_id):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        return apply(state, next(a for a in legal_actions(state)
                                 if isinstance(a, ChooseTarget)
                                 and a.target_id == target_id))

    def test_c25_4_grants_stat_and_saboteur_while_in_play(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bd1 = _place(state, "P0", _get_card(repo, "C25", "4"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert compute_power(state, ally) == 3
        assert not has_keyword(state, ally, Keyword.SABOTEUR)
        state = _fire_when_played(state, bd1)
        state = self._choose(state, ally.instance_id)
        ally2 = _find_instance(state, ally.instance_id)
        assert compute_power(state, ally2) == 4                    # +1/+0
        assert has_keyword(state, ally2, Keyword.SABOTEUR)         # granted keyword

    def test_c25_4_buff_ends_when_bd1_leaves_play(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bd1 = _place(state, "P0", _get_card(repo, "C25", "4"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bd1)
        state = self._choose(state, ally.instance_id)
        # BD-1 leaves play → both permanent modifiers wink off (source-in-play guard).
        state = _defeat_and_fire(state, _find_instance(state, bd1.instance_id), "P0")
        ally2 = _find_instance(state, ally.instance_id)
        assert compute_power(state, ally2) == 3
        assert not has_keyword(state, ally2, Keyword.SABOTEUR)

    def test_c25_4_targets_only_another_friendly_unit(self, repo):
        state = _make_state()
        bd1 = _place(state, "P0", _get_card(repo, "C25", "4"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bd1)
        # "another friendly unit" — not BD-1 itself, not the enemy.
        assert self._ct_ids(state) == {ally.instance_id}

    def test_c25_4_no_other_friendly_unit_is_a_no_op(self, repo):
        from swu.engine.actions import ChooseTarget, legal_actions
        state = _make_state()
        bd1 = _place(state, "P0", _get_card(repo, "C25", "4"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # only an enemy
        state = _fire_when_played(state, bd1)
        state = _drain(state)
        # Mandatory targeted effect with no legal friendly target → fizzles cleanly.
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert not state.modifiers

    def test_c25_4_grant_survives_serialization(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import GameState
        state = _make_state()
        bd1 = _place(state, "P0", _get_card(repo, "C25", "4"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bd1)
        state = self._choose(state, ally.instance_id)
        state = GameState.from_json(state.to_json())
        ally2 = _find_instance(state, ally.instance_id)
        assert compute_power(state, ally2) == 4
        assert has_keyword(state, ally2, Keyword.SABOTEUR)


# ── Stage 4 batch 29 — deploy-leader-as-effect (Grogu ASH_18) ──────────────────

class TestGroguASH18:
    """ASH_18 — Grogu "Charming Companion" (Leader). "When you play a unique unit
    that costs 4 or more: If this leader is ready, you may deploy him." The optional
    undeployed WhenYouPlayCard trigger deploys the source leader for free."""

    def _play_unit(self, state, card, arena="ground"):
        """Place a unit in P0's arena and fire its CardPlayed (mirrors a play)."""
        ci = _place(state, "P0", card, arena)
        return _fire_card_played(state, "P0", ci), ci

    def test_ash_18_deploys_grogu_on_unique_4plus_play(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        grogu = _place_leader(state, "P0", _get_card(repo, "ASH", "18"))
        state, _ = self._play_unit(state, _get_card(repo, "JTL", "53"))  # unique, cost 5
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger) and a.source_id == grogu.instance_id)
        state = apply(state, accept)
        state = _drain(state)
        _, leader = state.find_instance(grogu.instance_id)
        assert leader.deployed is True
        assert leader.exhausted is False   # a deployed leader enters ready
        assert leader not in state.player_by_id("P0").base_zone
        assert leader in (state.player_by_id("P0").ground_arena
                          + state.player_by_id("P0").space_arena)

    def test_ash_18_not_offered_for_non_unique_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "ASH", "18"))
        state, _ = self._play_unit(state, _get_card(repo, "SOR", "116"))  # non-unique, cost 5
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_ash_18_not_offered_for_cheap_unique_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "ASH", "18"))
        state, _ = self._play_unit(state, _get_card(repo, "SOR", "192"))  # unique, cost 3 (<4)
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_ash_18_not_offered_when_leader_exhausted(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        grogu = _place_leader(state, "P0", _get_card(repo, "ASH", "18"))
        grogu.exhausted = True  # SOURCE_READY gate should suppress the trigger
        state, _ = self._play_unit(state, _get_card(repo, "JTL", "53"))
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_ash_18_decline_leaves_grogu_undeployed(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, DeclineTrigger
        state = _make_state()
        grogu = _place_leader(state, "P0", _get_card(repo, "ASH", "18"))
        state, _ = self._play_unit(state, _get_card(repo, "JTL", "53"))
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        _, leader = state.find_instance(grogu.instance_id)
        assert leader.deployed is False
        assert leader in state.player_by_id("P0").base_zone

    def test_ash_18_not_offered_once_deployed(self, repo):
        """undeployed_only: a deployed Grogu (now a unit) does not re-trigger."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _deploy_leader_as_unit(state, "P0", _get_card(repo, "ASH", "18"), "ground")
        state, _ = self._play_unit(state, _get_card(repo, "JTL", "53"), "space")
        assert not state.pending_decisions
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── Stage 4 batch 30 (2026-07-13) — trivial straggler: Shatterpoint P25_153 ────

class TestShatterpointP25153:
    """Shatterpoint P25_153 (Event) — "Choose one: Defeat a non-leader unit with 3
    or less remaining HP. / Use the Force. If you do, defeat a non-leader unit."

    Zero new engine code — the choose_two_modal pick=1 selector (options idx 1/2)
    + DefeatUnit(hp_remaining_max) for opt 1, and the spend_force_token /
    requires_prior_target "If you do" gate for opt 2.  Siblings P25_163 / P26_74 /
    P26_90 are byte-identical reprint faces aliased to it.
    """

    def test_p25_153_opt1_defeats_only_low_hp_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        weak = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")   # 3/1
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        _play_aspect_event(state, repo, "P25", "153")
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        state = _pick_option(state, 1)   # opt 1: defeat a ≤3-remaining-HP unit
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert weak.instance_id in offered
        assert tough.instance_id not in offered      # 7 remaining HP > 3
        state = _choose(state, weak.instance_id)
        assert _find_instance(state, weak.instance_id) is None      # defeated
        assert _find_instance(state, tough.instance_id) is not None

    def test_p25_153_opt1_no_eligible_unit_fizzles(self, repo):
        state = _make_state()
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        _play_aspect_event(state, repo, "P25", "153")
        state = _pick_option(state, 1)
        state = _drain(state)
        assert not state.pending_decisions
        assert _find_instance(state, tough.instance_id) is not None  # survived

    def test_p25_153_opt2_with_force_defeats_any_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        _play_aspect_event(state, repo, "P25", "153")
        state = _pick_option(state, 2)   # opt 2: Use the Force → defeat any non-leader
        state = _auto_resolve(state)     # effect 0 spends the Force token
        assert state.player_by_id("P0").has_force_token is False
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert tough.instance_id in offered          # ANY non-leader, even 7 HP
        state = _choose(state, tough.instance_id)
        assert _find_instance(state, tough.instance_id) is None      # defeated

    def test_p25_153_opt2_without_force_does_nothing(self, repo):
        state = _make_state()
        assert state.player_by_id("P0").has_force_token is False
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _play_aspect_event(state, repo, "P25", "153")
        state = _pick_option(state, 2)
        state = _drain(state)                        # no token → prior_target unset
        assert not state.pending_decisions
        assert _find_instance(state, tough.instance_id) is not None  # no Force → no defeat

    def test_p25_153_reprint_faces_registered(self):
        from tests.dbpath import require_reprint_aliases
        require_reprint_aliases()
        from swu.abilities.registry import get_abilities
        canon = get_abilities("P25", "153")
        for s, n in [("P25", "163"), ("P26", "74"), ("P26", "90")]:
            assert get_abilities(s, n) is canon


# ── Batch 31: Director Krennic JTLP_1 — standing per-round play-cost discount ──

class TestDirectorKrennicJTLP1:
    """JTLP_1 — Shielded. The first unit you play each round that has a 'When
    Defeated' ability costs 1 resource less.  A StandingPlayDiscount marker read at
    the play-cost seam (_play_cost via _standing_play_discount), once-per-round.
    Reprint sibling P25_65 aliased to it."""

    def _setup(self, repo, with_krennic=True):
        state = _make_state()
        if with_krennic:
            _place(state, "P0", _get_card(repo, "JTLP", "1"), "ground")
        return state

    def test_jtlp_1_discounts_a_when_defeated_unit(self, repo):
        from swu.engine.actions import _standing_play_discount, _play_cost
        state = self._setup(repo)
        ps = state.player_by_id("P0")
        wd = _put_in_hand(state, "P0", _get_card(repo, "SOR", "108"))  # Vanguard Infantry: When Defeated
        assert _standing_play_discount(state, wd, ps) == 1
        # And it actually lowers the play cost by 1 vs no Krennic on the board.
        base_state = self._setup(repo, with_krennic=False)
        base_ps = base_state.player_by_id("P0")
        wd2 = _put_in_hand(base_state, "P0", _get_card(repo, "SOR", "108"))
        assert _play_cost(state, wd, ps) == _play_cost(base_state, wd2, base_ps) - 1

    def test_jtlp_1_no_discount_for_unit_without_when_defeated(self, repo):
        from swu.engine.actions import _standing_play_discount
        state = self._setup(repo)
        ps = state.player_by_id("P0")
        vanilla = _put_in_hand(state, "P0", _get_card(repo, "SOR", "95"))  # Battlefield Marine (no ability)
        assert _standing_play_discount(state, vanilla, ps) == 0

    def test_jtlp_1_no_discount_without_krennic_in_play(self, repo):
        from swu.engine.actions import _standing_play_discount
        state = self._setup(repo, with_krennic=False)
        ps = state.player_by_id("P0")
        wd = _put_in_hand(state, "P0", _get_card(repo, "SOR", "108"))
        assert _standing_play_discount(state, wd, ps) == 0

    def test_jtlp_1_only_first_play_each_round_then_resets(self, repo):
        from swu.engine.actions import _standing_play_discount, _consume_standing_discount
        state = self._setup(repo)
        ps = state.player_by_id("P0")
        first = _put_in_hand(state, "P0", _get_card(repo, "SOR", "108"))   # When Defeated
        second = _put_in_hand(state, "P0", _get_card(repo, "SOR", "226"))  # Admiral Motti: When Defeated
        assert _standing_play_discount(state, first, ps) == 1
        # Playing the first spends Krennic's per-round discount.
        _consume_standing_discount(state, first, ps)
        assert _standing_play_discount(state, second, ps) == 0
        # Round rollover re-arms it.
        state.game_memory.clear_round()
        assert _standing_play_discount(state, second, ps) == 1

    def test_jtlp_1_end_to_end_playcard_pays_one_less_and_consumes(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, _play_cost
        state = self._setup(repo)
        ps = state.player_by_id("P0")
        wd = _put_in_hand(state, "P0", _get_card(repo, "SOR", "226"))  # When Defeated
        expected = _play_cost(state, wd, ps)  # already discounted
        _give_resources(state, "P0", expected + 3, repo)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == wd.instance_id)
        state = apply(state, play)
        ps = state.player_by_id("P0")
        assert sum(1 for r in ps.resources if r.exhausted) == expected
        # Krennic's discount is now spent for the round.
        assert state.game_memory.standing_play_discounts_used_this_round

    def test_jtlp_1_reprint_p25_65_aliases_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities, StandingPlayDiscount
        canon = get_abilities("JTLP", "1")
        assert get_abilities("P25", "65") is canon
        assert isinstance(canon[0], StandingPlayDiscount)


# ── Batch 34: attach an in-play unit as a Pilot upgrade (Poe Dameron JTLP_6) ───

class TestPoeDameronJTLP6:
    """JTLP_6 — When played as a unit: Create an X-Wing token.  You may attach
    this unit as an upgrade to a friendly Vehicle unit without a Pilot on it."""

    def _play_poe(self, state, repo):
        """Place Poe and fire his When-Played (as a unit); returns (state, poe_id)."""
        poe = _place(state, "P0", _get_card(repo, "JTLP", "6"), "space")
        state = _fire_when_played(state, poe)
        return state, poe.instance_id

    def _xwing(self, state):
        ps = state.player_by_id("P0")
        for ci in ps.ground_arena + ps.space_arena:
            if ci.card_def.display_name == "X-Wing":
                return ci
        return None

    def test_jtlp_6_played_as_unit_creates_xwing_and_offers_attach(self, repo):
        state = _make_state()
        state, _poe = self._play_poe(state, repo)
        # X-Wing token created, and the pilot_self_attach decision is pending.
        assert self._xwing(state) is not None
        assert state.pending_decisions[-1].kind == "pilot_self_attach"

    def test_jtlp_6_attach_onto_xwing_makes_poe_a_pilot(self, repo):
        from swu.engine.actions import legal_actions, apply, AttachSelfAsPilot, compute_power
        from swu.engine.actions import compute_hp
        state = _make_state()
        state, poe_id = self._play_poe(state, repo)
        xwing = self._xwing(state)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttachSelfAsPilot) and a.vehicle_id == xwing.instance_id)
        state = apply(state, act)
        # Poe left the arena and now rides the X-Wing as a Pilot upgrade.
        assert _find_instance(state, poe_id) is None
        xw = _find_instance(state, xwing.instance_id)
        assert any(u.instance_id == poe_id for u in xw.attached_upgrades)
        # Poe's 2/3 upgrade stats buff the 2/2 X-Wing → 4/5.
        assert compute_power(state, xw) == 4
        assert compute_hp(state, xw) == 5
        assert not state.pending_decisions

    def test_jtlp_6_decline_keeps_poe_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineAttachSelfAsPilot
        state = _make_state()
        state, poe_id = self._play_poe(state, repo)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, DeclineAttachSelfAsPilot))
        state = apply(state, act)
        assert _find_instance(state, poe_id) is not None  # still a unit
        assert self._xwing(state) is not None
        assert not state.pending_decisions

    def test_jtlp_6_no_vehicle_host_pushes_no_decision(self, repo):
        """The push helper auto-skips (does nothing) with no eligible Vehicle host."""
        from swu.engine.actions import push_attach_unit_as_pilot
        state = _make_state()
        poe = _place(state, "P0", _get_card(repo, "JTLP", "6"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # a non-Vehicle ally
        push_attach_unit_as_pilot(state, poe)
        assert not state.pending_decisions

    def test_jtlp_6_host_defeat_sends_poe_to_owner_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, AttachSelfAsPilot, _defeat_unit
        state = _make_state()
        state, poe_id = self._play_poe(state, repo)
        xwing = self._xwing(state)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, AttachSelfAsPilot) and a.vehicle_id == xwing.instance_id)
        state = apply(state, act)
        # Defeat the host X-Wing (a token — it ceases to exist; its Pilot Poe, a real
        # Unit, goes to its owner's discard).
        ps = state.player_by_id("P0")
        xw = _find_instance(state, xwing.instance_id)
        _defeat_unit(state, ps, xw)
        assert any(c.instance_id == poe_id for c in state.player_by_id("P0").discard)

    def test_jtlp_6_reprint_p25_90_aliases_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("P25", "90")) == ("JTLP", "6")
        assert get_abilities("P25", "90") == get_abilities("JTLP", "6")


class TestJabbaTheHuttASH42:
    """ASH_42 Jabba the Hutt — Restore 2 (keyword layer) + "When Played: You may
    return an upgrade to its owner's hand.  If it's returned to your hand, you may
    play it for free."  The batch-43 `play_upgrade_from_hand` decision kind (the
    upgrade sibling of the units-only play_from_hand subsystem) + the completed
    `_apply_return_to_hand` upgrade-detach branch."""

    def _drive_when_played(self, state, upgrade_id):
        """Accept the optional WhenPlayed, choose the upgrade target, and drain to
        the play_upgrade_from_hand decision (or quiescence)."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects)
        for _ in range(30):
            la = legal_actions(state)
            acc = next((a for a in la if isinstance(a, AcceptTrigger)), None)
            if acc is not None:
                state = apply(state, acc); continue
            ct = next((a for a in la if isinstance(a, ChooseTarget)
                       and a.target_id == upgrade_id), None)
            if ct is not None:
                state = apply(state, ct); continue
            ar = next((a for a in la if isinstance(a, AutoResolveEffects)), None)
            if ar is not None:
                state = apply(state, ar); continue
            break
        return state

    def test_ash_42_return_to_hand_detaches_an_upgrade(self, repo):
        # Unit test of the completed _apply_return_to_hand upgrade branch: an
        # attached upgrade detaches from its host and lands in its OWNER's hand,
        # clean (no damage/exhaust), not double-homed in the arena.
        from swu.abilities.resolver import _apply_return_to_hand
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        upg = _attach_upgrade(state, host, _get_card(repo, "SOR", "120"), "P0")  # Academy Training
        state = _apply_return_to_hand(state, upg.instance_id)
        host_now = _find_instance(state, host.instance_id)
        assert all(u.instance_id != upg.instance_id for u in host_now.attached_upgrades)
        hand_ids = {c.instance_id for c in state.player_by_id("P0").hand}
        assert upg.instance_id in hand_ids

    def test_ash_42_returns_own_upgrade_then_free_replays_onto_a_host(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        from swu.engine.events import UpgradePlayed
        state = _make_state()
        jabba = _place(state, "P0", _get_card(repo, "ASH", "42"), "ground")
        old_host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade(state, old_host, _get_card(repo, "SOR", "120"), "P0")
        new_host = _place(state, "P0", _get_card(repo, "SOR", "88"), "ground")  # a 9/9
        state = _fire_when_played(state, jabba)
        state = self._drive_when_played(state, upg.instance_id)
        # The upgrade was returned to P0's hand and a free-replay decision is up.
        assert any(isinstance(a, PlayUpgradeFromHand) for a in legal_actions(state))
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayUpgradeFromHand) and a.host_id == new_host.instance_id)
        state = apply(state, act)
        # It re-attached to the new host (re-firing UpgradePlayed) and left hand.
        nh = _find_instance(state, new_host.instance_id)
        assert any(u.instance_id == upg.instance_id for u in nh.attached_upgrades)
        assert all(c.instance_id != upg.instance_id for c in state.player_by_id("P0").hand)
        assert any(isinstance(e, UpgradePlayed) and e.instance_id == upg.instance_id
                   for e in state.event_log)

    def test_ash_42_may_decline_the_free_replay(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclinePlayUpgradeFromHand
        state = _make_state()
        jabba = _place(state, "P0", _get_card(repo, "ASH", "42"), "ground")
        old_host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade(state, old_host, _get_card(repo, "SOR", "120"), "P0")
        state = _fire_when_played(state, jabba)
        state = self._drive_when_played(state, upg.instance_id)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, DeclinePlayUpgradeFromHand))
        state = apply(state, act)
        # Declining leaves the upgrade in P0's hand, attached to nobody.
        assert any(c.instance_id == upg.instance_id for c in state.player_by_id("P0").hand)
        oh = _find_instance(state, old_host.instance_id)
        assert all(u.instance_id != upg.instance_id for u in oh.attached_upgrades)

    def test_ash_42_enemy_owned_upgrade_gets_no_free_replay(self, repo):
        # "If it's returned to YOUR hand" — an opponent-owned upgrade goes to the
        # opponent's hand, so no play_upgrade_from_hand is offered.
        from swu.engine.actions import legal_actions, PlayUpgradeFromHand
        state = _make_state()
        jabba = _place(state, "P0", _get_card(repo, "ASH", "42"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade(state, enemy, _get_card(repo, "SOR", "120"), "P1")  # P1 owns it
        state = _fire_when_played(state, jabba)
        state = self._drive_when_played(state, upg.instance_id)
        assert not any(isinstance(a, PlayUpgradeFromHand) for a in legal_actions(state))
        assert any(c.instance_id == upg.instance_id for c in state.player_by_id("P1").hand)

    def test_ash_42_no_upgrade_in_play_auto_declines(self, repo):
        # With no non-token upgrade in play the optional WhenPlayed has no legal
        # target → it auto-declines with no decision and no error.
        from swu.engine.actions import legal_actions, PlayUpgradeFromHand
        state = _make_state()
        jabba = _place(state, "P0", _get_card(repo, "ASH", "42"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # a bare unit
        state = _fire_when_played(state, jabba)
        state = _drain(state)
        assert not any(isinstance(a, PlayUpgradeFromHand) for a in legal_actions(state))

    def test_ash_42_reprint_c26_6_aliases_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("C26", "6")) == ("ASH", "42")
        assert get_abilities("C26", "6") is get_abilities("ASH", "42")


class TestDarthMaulC246:
    """C24_6 — "This unit can attack 2 units instead of 1" (the multi-defender
    attack primitive).  Canonical for the (C24_6, J25_5, P25_91) group."""

    def _attack_two(self, state, attacker, d1, d2):
        from swu.engine.actions import legal_actions, apply, AttackTwoUnits
        act = next(
            a for a in legal_actions(state)
            if isinstance(a, AttackTwoUnits)
            and a.attacker_id == attacker.instance_id
            and {a.defender1_id, a.defender2_id} == {d1.instance_id, d2.instance_id})
        return apply(state, act)

    def test_c24_6_offers_attack_two_units_only_with_two_defenders(self, repo):
        from swu.engine.actions import legal_actions, AttackTwoUnits
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        d1 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        # One defender → no two-unit attack possible.
        assert not any(isinstance(a, AttackTwoUnits) for a in legal_actions(state))
        d2 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        two = [a for a in legal_actions(state) if isinstance(a, AttackTwoUnits)]
        assert len(two) == 1
        assert {two[0].defender1_id, two[0].defender2_id} == {d1.instance_id, d2.instance_id}

    def test_c24_6_not_offered_for_a_normal_unit(self, repo):
        from swu.engine.actions import legal_actions, AttackTwoUnits
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # no marker
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        assert not any(isinstance(a, AttackTwoUnits) for a in legal_actions(state))

    def test_c24_6_deals_power_to_both_defenders_and_takes_the_sum(self, repo):
        # Maul (5/6) vs two 3/7 units: both take 5 (survive); Maul takes 3+3=6 → dies.
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        d1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        d2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = self._attack_two(state, maul, d1, d2)
        assert _find_instance(state, d1.instance_id).damage == 5
        assert _find_instance(state, d2.instance_id).damage == 5
        assert _find_instance(state, maul.instance_id) is None  # took 6, defeated

    def test_c24_6_kills_both_defenders_and_survives(self, repo):
        # Maul (5/6) vs two 2/3 Thugs: both defeated (5>=3); Maul takes 2+2=4 → lives.
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        d1 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        d2 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        state = self._attack_two(state, maul, d1, d2)
        assert _find_instance(state, d1.instance_id) is None
        assert _find_instance(state, d2.instance_id) is None
        m = _find_instance(state, maul.instance_id)
        assert m is not None and m.damage == 4 and m.exhausted

    def test_c24_6_overwhelm_spills_combined_excess_to_base(self, repo):
        # Grant Maul Overwhelm: 5 power vs two 2/3 Thugs → 2 excess each = 4 to base.
        from swu.engine.state import Modifier
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=maul.instance_id,
            target_instance_id=maul.instance_id,
            kind="keyword_grant",
            value={"keyword": "Overwhelm", "value": 0},
            duration="permanent",
        ))
        d1 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        d2 = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # 2/3
        base_before = state.player_by_id("P1").base_instance.damage
        state = self._attack_two(state, maul, d1, d2)
        assert state.player_by_id("P1").base_instance.damage == base_before + 4

    def test_c24_6_sentinel_forces_both_to_be_sentinels(self, repo):
        from swu.engine.actions import legal_actions, AttackTwoUnits
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        sent = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # Sentinel
        thug = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # non-sent
        # One Sentinel + one non-Sentinel → the pair can't be formed (both must be
        # Sentinels), so no two-unit attack is offered.
        assert not any(isinstance(a, AttackTwoUnits) for a in legal_actions(state))
        # A second Sentinel makes the (Sentinel, Sentinel) pair legal.
        sent2 = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        two = [a for a in legal_actions(state) if isinstance(a, AttackTwoUnits)]
        assert len(two) == 1
        assert {two[0].defender1_id, two[0].defender2_id} == {sent.instance_id, sent2.instance_id}

    def test_c24_6_serialises_through_state_round_trip(self, repo):
        from swu.engine.state import GameState
        state = _make_state()
        _place(state, "P0", _get_card(repo, "C24", "6"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")
        restored = GameState.from_json(state.to_json())
        from swu.engine.actions import legal_actions, AttackTwoUnits
        assert any(isinstance(a, AttackTwoUnits) for a in legal_actions(restored))

    def test_c24_6_reprints_j25_5_p25_91_alias_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("J25", "5")) == ("C24", "6")
        assert REPRINT_ALIASES.get(("P25", "91")) == ("C24", "6")
        assert get_abilities("J25", "5") is get_abilities("C24", "6")
        assert get_abilities("P25", "91") is get_abilities("C24", "6")


class TestGalenErsoP2531:
    """P25_31 — Galen Erso "When Played: Name a card.  While this unit is in play,
    each non-leader card an opponent owns with that name, including those not in play,
    loses all abilities." + Plot.  The name-based persistent ability-suppression
    primitive: a name_a_card decision + CardInstance.named_card + state.is_name_suppressed
    woven into batch-44's ability-read guards.  Canonical for the (P25_31, P26_38,
    P26_50) group."""

    def test_p25_31_when_played_offers_name_a_card_from_opponent_public_cards(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # Cell Block Guard
        state = _fire_when_played(state, galen)
        state = _drain(state)
        names = [a.name for a in legal_actions(state) if isinstance(a, NameCard)]
        assert "Cell Block Guard" in names
        act = next(a for a in legal_actions(state)
                   if isinstance(a, NameCard) and a.name == "Cell Block Guard")
        state = apply(state, act)
        assert not state.pending_decisions
        assert _find_instance(state, galen.instance_id).named_card == "Cell Block Guard"

    def test_p25_31_named_enemy_unit_loses_its_keyword(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        guard = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # Sentinel
        assert has_keyword(state, guard, Keyword.SENTINEL)      # before naming
        galen.named_card = "Cell Block Guard"
        assert not has_keyword(state, guard, Keyword.SENTINEL)  # loses all abilities

    def test_p25_31_named_enemy_unit_loses_its_constant_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        scim = _place(state, "P1", _get_card(repo, "LOF", "233"), "ground")  # 3/4, +3/+0 while damaged
        scim.damage = 1
        assert compute_power(state, scim) == 6   # self-constant applies
        galen.named_card = "Scimitar"
        assert compute_power(state, scim) == 3   # constant source suppressed

    def test_p25_31_out_of_play_copy_played_later_enters_suppressed(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        galen.named_card = "Cell Block Guard"  # named before any copy is in play
        # A copy entering play afterwards is suppressed by NAME ("including those not
        # in play" — out-of-play application falls out of the name-based read).
        later = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        assert not has_keyword(state, later, Keyword.SENTINEL)

    def test_p25_31_suppression_lifts_when_galen_leaves_play(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        guard = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        galen.named_card = "Cell Block Guard"
        assert not has_keyword(state, guard, Keyword.SENTINEL)
        state.player_by_id("P0").ground_arena.remove(galen)     # Galen leaves play
        assert has_keyword(state, guard, Keyword.SENTINEL)       # persistence lifts

    def test_p25_31_only_opponent_owned_copies_are_suppressed(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        galen.named_card = "Cell Block Guard"
        own = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")    # namer's own copy
        enemy = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # opponent's copy
        assert has_keyword(state, own, Keyword.SENTINEL)         # own copy keeps it
        assert not has_keyword(state, enemy, Keyword.SENTINEL)   # only the opponent's is suppressed

    def test_p25_31_leader_card_is_never_suppressed(self, repo):
        from swu.engine.state import is_name_suppressed
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        leader_def = next(c for c in repo.iter_all() if c.type == "Leader")
        leader_ci = _place(state, "P1", leader_def, "ground")
        galen.named_card = leader_def.name   # "each NON-leader card" — a leader is exempt
        assert not is_name_suppressed(state, leader_ci)

    def test_p25_31_serialises_named_card(self, repo):
        from swu.engine.state import GameState
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "P25", "31"), "ground")
        galen.named_card = "Cell Block Guard"
        restored = GameState.from_json(state.to_json())
        assert _find_instance(restored, galen.instance_id).named_card == "Cell Block Guard"

    def test_p25_31_reprints_p26_38_p26_50_alias_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("P26", "38")) == ("P25", "31")
        assert REPRINT_ALIASES.get(("P26", "50")) == ("P25", "31")
        assert get_abilities("P26", "38") is get_abilities("P25", "31")
        assert get_abilities("P26", "50") is get_abilities("P25", "31")


class TestLukeSkywalkerJ254:
    """J25_4 — Luke Skywalker "You Still With Me?" (Piloting): "If this upgrade
    would be defeated, you may instead move him to the ground arena as a unit and
    exhaust him."  A defeat-replacement on the Pilot form, modelled as an optional
    ``WhenDefeatedAsUpgrade`` trigger relocating him discard → ground arena (batch
    47's replacement-effect framework, defeat half)."""

    def _attach_pilot_and_defeat_host(self, state, repo):
        """Attach Luke as a pilot upgrade on a P0 host, then defeat the host via the
        real ``_defeat_unit`` — which detaches Luke to discard and fires the
        ``defeated_upgrades`` scan that collects his WhenDefeatedAsUpgrade trigger."""
        from swu.engine.actions import _defeat_unit
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7 host
        luke = _attach_upgrade(state, host, _get_card(repo, "J25", "4"), "P0")
        _defeat_unit(state, state.player_by_id("P0"), host)
        return luke

    def test_j25_4_pilot_defeat_accept_moves_luke_to_ground(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        luke = self._attach_pilot_and_defeat_host(state, repo)
        state = _accept(state)          # the optional WhenDefeatedAsUpgrade trigger
        state = _drain(state)
        moved = _find_instance(state, luke.instance_id)
        assert moved.zone == Zone.GROUND_ARENA
        assert moved in state.player_by_id("P0").ground_arena
        assert moved.exhausted                                  # "exhaust him"
        assert moved not in state.player_by_id("P0").discard

    def test_j25_4_relocated_luke_has_unit_stats(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        luke = self._attach_pilot_and_defeat_host(state, repo)
        state = _accept(state)
        state = _drain(state)
        moved = _find_instance(state, luke.instance_id)
        assert compute_power(state, moved) == 3 and compute_hp(state, moved) == 2

    def test_j25_4_pilot_defeat_decline_leaves_luke_in_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        from swu.engine.state import Zone
        state = _make_state()
        luke = self._attach_pilot_and_defeat_host(state, repo)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        state = _drain(state)
        p0 = state.player_by_id("P0")
        rested = next(c for c in p0.discard if c.instance_id == luke.instance_id)
        assert rested.zone == Zone.DISCARD
        assert all(c.instance_id != luke.instance_id for c in p0.ground_arena)

    def test_j25_4_defeated_as_normal_unit_offers_no_replacement(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "J25", "4"), "ground")
        state = _defeat_and_fire(state, luke, "P0")
        # He died as a UNIT, not a pilot upgrade — no WhenDefeatedAsUpgrade offered.
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert any(c.instance_id == luke.instance_id
                   for c in state.player_by_id("P0").discard)

    def test_j25_4_serialises_across_pending_replacement(self, repo):
        from swu.engine.state import GameState
        state = _make_state()
        luke = self._attach_pilot_and_defeat_host(state, repo)
        restored = GameState.from_json(state.to_json())  # pending optional trigger survives
        restored = _accept(restored)
        restored = _drain(restored)
        assert _find_instance(restored, luke.instance_id) in restored.player_by_id("P0").ground_arena

    def test_j25_4_reprint_p25_89_alias_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("P25", "89")) == ("J25", "4")
        assert get_abilities("P25", "89") is get_abilities("J25", "4")


# ── p25-set:03 / jtlp-set:01 residuals ────────────────────────────────────────


class TestKyloRenP25_46:
    """While playing him, ignore his Villainy aspect penalty if you control Rey.
    On Attack: +2/+0, and an Experience token if the target is non-Villainy."""

    def test_P25_46_villainy_penalty_waived_only_while_you_control_rey(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        kylo = _put_in_hand(state, "P0", _get_card(repo, "P25", "46"))
        ps = state.player_by_id("P0")
        # The test base has no aspects, so Aggression + Villainy both cost +2.
        without_rey = _play_cost(state, kylo, ps)
        _place(state, "P0", _get_card(repo, "SHD", "46"), "ground")   # Rey
        with_rey = _play_cost(state, kylo, ps)
        # ONLY the Villainy pip is waived — the Aggression one is still paid.
        assert with_rey == without_rey - 2
        assert with_rey == kylo.card_def.cost + 2

    def test_P25_46_on_attack_buffs_and_tokens_a_non_villainy_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "P25", "46"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Heroism
        before = compute_power(state, target)
        state = apply(_fire_on_attack(state, kylo),
                      ChooseTarget(target.instance_id))
        after = _find_instance(state, target.instance_id)
        # +2 from the modifier and +1 more from the Experience token it also got.
        assert compute_power(state, after) == before + 3
        assert _experience_count(after) == 1

    def test_P25_46_a_villainy_target_gets_the_buff_but_no_token(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "P25", "46"), "ground")
        villain = _place(state, "P1", _get_card(repo, "P25", "46"), "ground")
        before = compute_power(state, villain)
        state = _fire_on_attack(state, kylo)
        state = apply(state, ChooseTarget(villain.instance_id))
        after = _find_instance(state, villain.instance_id)
        assert compute_power(state, after) == before + 2
        assert _experience_count(after) == 0


class TestFettsFirespray_JTLP_18:
    """When Played/On Attack: 1 indirect damage to a player, 2 if you control Boba
    Fett — the prerelease printing of JTL_240 (whose DB text is truncated)."""

    def test_JTLP_18_deals_one_indirect_without_boba(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTLP", "18"), "space")
        state = _fire_when_played(state, ship)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 1

    def test_JTLP_18_deals_two_indirect_with_boba_fett_in_play(self, repo):
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "JTLP", "18"), "space")
        _place(state, "P0", _get_card(repo, "JTL", "189"), "ground")   # Boba Fett
        state = _fire_on_attack(state, ship)
        top = state.pending_decisions[-1]
        assert top.kind == "assign_indirect_damage"
        assert top.context["amount"] == 2


# ── The last four cards of the gap-filling campaign ───────────────────────────
#
# jtlp-set:02, j24-set:01, c24-set:02, c25-set:01 — one one-card group each.
# THREE of them turned out to need no card logic at all: they are exact reprints
# of an implemented card whose only difference is LETTER CASE ("SEPARATIST",
# "[exhaust,"), which the printed-face identity (``reprints._norm``) did not fold
# until this batch — so each keyed to a singleton group and the mirror sweep could
# not see it.  They are aliased in ``reprints.REPRINT_ALIASES``; the tests below
# drive the ALIASED behaviour through the public interfaces, which is the real
# evidence that the alias points at the right card.  Only JTLP_16, whose DB text
# is defective rather than merely cased differently, carries a registration.


class TestAnakinSkywalker_JTLP_16:
    """JTLP_16 — Piloting; "When attached unit completes an attack (and survives):
    You may return this upgrade to its owner's hand" — the prerelease printing of
    JTL_197, whose DB ``epic_action`` lost the trigger clause outright."""

    def test_JTLP_16_attack_ends_may_return_the_pilot_upgrade_to_hand(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        anakin = _attach_upgrade(state, host, _get_card(repo, "JTLP", "16"), "P0")

        state = _fire_attack_ends(state, host)
        state = _accept(state)
        state = _drain(state)

        live_host = _find_instance(state, host.instance_id)
        assert live_host is not None, "the host survives its own attack"
        assert not any(u.instance_id == anakin.instance_id
                       for u in live_host.attached_upgrades)
        assert any(c.instance_id == anakin.instance_id
                   for c in state.player_by_id("P0").hand)

    def test_JTLP_16_declining_leaves_the_pilot_attached(self, repo):
        """The printed "you may" — and the guard that the trigger really is
        optional rather than a mandatory bounce."""
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "JTL", "237"), "space")
        anakin = _attach_upgrade(state, host, _get_card(repo, "JTLP", "16"), "P0")

        state = _fire_attack_ends(state, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        state = _drain(state)

        live_host = _find_instance(state, host.instance_id)
        assert any(u.instance_id == anakin.instance_id
                   for u in live_host.attached_upgrades)
        assert not state.player_by_id("P0").hand


class TestWrecker_J24_5:
    """J24_5 — Overwhelm; "When Played: You may defeat a friendly resource.  If you
    do, deal 5 damage to a ground unit."  An exact reprint of Wrecker SHD_154
    (differing only in letter case), so it is ALIASED, not re-registered."""

    def test_J24_5_shares_shd_154s_registration(self):
        from tests.dbpath import require_reprint_aliases
        require_reprint_aliases()
        from swu.abilities.registry import get_abilities
        assert get_abilities("J24", "5") is get_abilities("SHD", "154")

    def test_J24_5_sacrifices_a_resource_to_deal_5(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SacrificeResource, ChooseSacrificeTarget,
        )
        state = _make_state()
        wrecker = _place(state, "P0", _get_card(repo, "J24", "5"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _give_resources(state, "P0", 2, repo)
        res_before = len(state.player_by_id("P0").resources)

        state = _fire_when_played(state, wrecker)
        assert state.pending_decisions[-1].kind == "sacrifice_resource"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SacrificeResource)))
        assert len(state.player_by_id("P0").resources) == res_before - 1

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseSacrificeTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 5


class TestAsajjVentress_C24_5:
    """C24_5 — Exploit 2; "On Attack: If you've attacked with another SEPARATIST
    unit this phase, this unit gets +3/+0 for this phase."  An exact reprint of
    Asajj Ventress TWI_134 (which prints the trait in title case), so it is
    ALIASED, not re-registered."""

    def test_C24_5_shares_twi_134s_registration(self):
        from tests.dbpath import require_reprint_aliases
        require_reprint_aliases()
        from swu.abilities.registry import get_abilities
        assert get_abilities("C24", "5") is get_abilities("TWI", "134")

    def test_C24_5_buffs_only_after_another_separatist_attacked(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "C24", "5"), "ground")
        asajj.exhausted = False
        # Nothing else has attacked yet: the clause is unmet, so she is a plain 2/4.
        state = _fire_on_attack(state, asajj)
        assert compute_power(state, _find_instance(state, asajj.instance_id)) == 2

        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "C24", "5"), "ground")
        asajj.exhausted = False
        ally = _place(state, "P0", _get_card(repo, "TWI", "57"), "ground")  # Separatist
        ally.exhausted = False
        state = _resolve_attack(state, ally.instance_id, None)   # ally hits the base
        state = _fire_on_attack(state, _find_instance(state, asajj.instance_id))
        assert compute_power(state, _find_instance(state, asajj.instance_id)) == 5


class TestC3PO_C25_5:
    """C25_5 — "Action [exhaust, return this unit to its owner's hand]: Give a unit
    +2/+2 for this phase."  An exact reprint of C-3PO SEC_93 (which capitalises the
    Exhaust cost), so it is ALIASED, not re-registered."""

    def test_C25_5_shares_sec_93s_registration(self):
        from tests.dbpath import require_reprint_aliases
        require_reprint_aliases()
        from swu.abilities.registry import get_abilities
        assert get_abilities("C25", "5") is get_abilities("SEC", "93")

    def test_C25_5_buffs_another_unit_and_returns_itself_to_hand(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget, compute_power, compute_hp,
        )
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "C25", "5"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        power_before = compute_power(state, target)
        hp_before = compute_hp(state, target)

        state = apply(state, next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == c3po.instance_id))
        # The printed cost bounces C-3PO before the buff lands, so he can never be
        # the buffed unit (``not_self``).
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert c3po.instance_id not in offered

        state = apply(state, ChooseTarget(target.instance_id))
        state = _drain(state)

        now = _find_instance(state, target.instance_id)
        assert compute_power(state, now) == power_before + 2
        assert compute_hp(state, now) == hp_before + 2
        assert _find_instance(state, c3po.instance_id) is None
        assert any(c.instance_id == c3po.instance_id
                   for c in state.player_by_id("P0").hand)
