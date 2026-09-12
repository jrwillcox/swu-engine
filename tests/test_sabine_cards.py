"""
sabine-mean-green:01 — Direct damage & removal card tests.

One focused test per card, asserting behaviour through the public engine
interfaces (legal_actions / apply / trigger firing).  Reuses the DB-backed
game-state helpers from the SOR card tests.

Cards: Sabine Wren leader (SOR_14), Sabine Wren unit (SOR_142), Fighters for
Freedom (SOR_143), K-2SO (SOR_145), Ketsu Onyo (SHD_147), For a Cause I
Believe In (SOR_152).
"""
from __future__ import annotations

import uuid

import pytest

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _place_leader,
    _fire_when_defeated, _fire_on_attack, _fire_when_played,
    _find_instance, _give_resources,
)


# ── SOR_14 Sabine Wren (Leader) ───────────────────────────────────────────────

class TestSabineWrenLeader:
    def test_14_undeployed_action_damages_both_bases(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        sabine = _get_card(repo, "SOR", "14")
        state = _make_state()
        sabine_ci = _place_leader(state, "P0", sabine)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == sabine_ci.instance_id)
        state = apply(state, use)
        assert not state.pending_decisions, "deal-to-each-base resolves inline"
        assert state.players[0].base_instance.damage == 1, "own base takes 1"
        assert state.players[1].base_instance.damage == 1, "enemy base takes 1"
        assert state.players[0].leader_instance.exhausted, "exhaust cost paid"

    def test_14_deployed_on_attack_hits_only_enemy_base(self, repo):
        from swu.engine.state import Zone
        sabine = _get_card(repo, "SOR", "14")
        state = _make_state()
        sabine_ci = _place_leader(state, "P0", sabine)
        # Move the leader into the ground arena as a deployed leader-unit.
        state.players[0].base_zone.remove(sabine_ci)
        sabine_ci.deployed = True
        sabine_ci.zone = Zone.GROUND_ARENA
        state.players[0].ground_arena.append(sabine_ci)
        state = _fire_on_attack(state, sabine_ci, defender_ci=None)
        assert not state.pending_decisions, "deal-to-each-enemy-base resolves inline"
        assert state.players[1].base_instance.damage == 1, "enemy base takes 1"
        assert state.players[0].base_instance.damage == 0, "own base untouched"


# ── SOR_142 Sabine Wren (Unit) ────────────────────────────────────────────────

class TestSabineWrenUnit:
    def test_142_targets_defender_or_a_base_only(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        sabine = _get_card(repo, "SOR", "142")
        state = _make_state()
        sabine_ci = _place(state, "P0", sabine, "ground")
        def_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        state = _fire_on_attack(state, sabine_ci, defender_ci=def_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert def_ci.instance_id in targets, "the defender is targetable"
        assert state.players[0].base_instance.instance_id in targets
        assert state.players[1].base_instance.instance_id in targets
        assert other.instance_id not in targets, "a non-defender unit is NOT targetable"
        state = apply(state, ChooseTarget(def_ci.instance_id))
        assert _find_instance(state, def_ci.instance_id).damage == 1

    def test_142_only_bases_when_attacking_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        sabine = _get_card(repo, "SOR", "142")
        state = _make_state()
        sabine_ci = _place(state, "P0", sabine, "ground")
        state = _fire_on_attack(state, sabine_ci, defender_ci=None)  # attacking base
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert targets == {state.players[0].base_instance.instance_id,
                           state.players[1].base_instance.instance_id}


# ── SOR_143 Fighters for Freedom ──────────────────────────────────────────────

class TestFightersForFreedom:
    def _play_from_hand(self, state, repo, set_code, num, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        card = _get_card(repo, set_code, num)
        ci = CardInstance(f"{owner}_play_{num}_{uuid.uuid4().hex[:4]}", card, owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return apply(state, PlayCard(ci.instance_id)), ci

    def test_143_triggers_on_another_aggression_card(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "143"), "ground")
        _give_resources(state, "P0", 5)
        state, _ = self._play_from_hand(state, repo, "SOR", "128")  # Aggression unit
        accept = next((a for a in legal_actions(state) if isinstance(a, AcceptTrigger)), None)
        assert accept is not None, "FFF triggers on another Aggression card"
        state = apply(state, accept)
        state = apply(state, ChooseTarget(state.players[1].base_instance.instance_id))
        assert state.players[1].base_instance.damage == 1

    def test_143_no_trigger_on_non_aggression_card(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "143"), "ground")
        _give_resources(state, "P0", 5)
        state, _ = self._play_from_hand(state, repo, "SOR", "59")  # Vigilance unit
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_143_no_trigger_on_itself(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, AcceptTrigger
        state = _make_state()
        _give_resources(state, "P0", 10)
        ci = CardInstance("P0_fff", _get_card(repo, "SOR", "143"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        state = apply(state, PlayCard(ci.instance_id))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── SOR_145 K-2SO ─────────────────────────────────────────────────────────────

class TestK2SO:
    def test_145_choose_damage_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        state = _make_state()
        k2_ci = _place(state, "P0", _get_card(repo, "SOR", "145"), "ground")
        state = _fire_when_defeated(state, k2_ci)
        assert state.pending_decisions[-1].kind == "modal"
        opt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseModalOption) and a.mode == "kaytoo_damage_base")
        state = apply(state, opt)
        assert not state.pending_decisions, "fungible mode resolves immediately"
        assert state.players[1].base_instance.damage == 3

    def test_145_choose_discard(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        state = _make_state()
        k2_ci = _place(state, "P0", _get_card(repo, "SOR", "145"), "ground")
        opp = state.player_by_id("P1")
        opp.hand.append(CardInstance("P1_h", _get_card(repo, "SOR", "59"), "P1", Zone.HAND))
        state = _fire_when_defeated(state, k2_ci)
        opt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseModalOption) and a.mode == "kaytoo_discard")
        state = apply(state, opt)
        assert len(state.player_by_id("P1").hand) == 0
        assert len(state.player_by_id("P1").discard) == 1

    def test_145_discard_mode_absent_when_opponent_hand_empty(self, repo):
        from swu.engine.actions import legal_actions, ChooseModalOption
        state = _make_state()
        k2_ci = _place(state, "P0", _get_card(repo, "SOR", "145"), "ground")
        state = _fire_when_defeated(state, k2_ci)
        modes = {a.mode for a in legal_actions(state) if isinstance(a, ChooseModalOption)}
        assert modes == {"kaytoo_damage_base"}, "no card to discard → only damage mode"


# ── SHD_147 Ketsu Onyo ────────────────────────────────────────────────────────

class TestKetsuOnyo:
    def test_147_defeats_upgrade_after_base_combat(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger, ChooseTarget
        state = _make_state()
        ketsu_ci = _place(state, "P0", _get_card(repo, "SHD", "147"), "ground")
        ketsu_ci.exhausted = False
        # Enemy unit hosting a cost-2 upgrade.
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upg = CardInstance(f"up_{uuid.uuid4().hex[:4]}", _get_card(repo, "SOR", "53"),
                           "P1", Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg)
        state = apply(state, AttackWithUnit(ketsu_ci.instance_id, None))  # attack base
        assert state.players[1].base_instance.damage == 3, "Ketsu's power hits the base"
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == upg.instance_id)
        state = apply(state, choose)
        host_after = _find_instance(state, host.instance_id)
        assert all(u.instance_id != upg.instance_id for u in host_after.attached_upgrades)
        assert state.active_player_index == 1, "turn passes to the opponent"

    def test_147_no_trigger_without_eligible_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger
        state = _make_state()
        ketsu_ci = _place(state, "P0", _get_card(repo, "SHD", "147"), "ground")
        ketsu_ci.exhausted = False
        state = apply(state, AttackWithUnit(ketsu_ci.instance_id, None))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), (
            "no upgrade in play → optional trigger auto-skipped"
        )
        assert state.active_player_index == 1, "turn passes normally"


# ── SOR_152 For a Cause I Believe In ──────────────────────────────────────────

class TestForACauseIBelieveIn:
    def _deck(self, state, repo, owner, specs):
        from swu.engine.state import CardInstance, Zone
        out = []
        for sc, num in specs:
            ci = CardInstance(f"{owner}_d_{num}_{uuid.uuid4().hex[:4]}",
                              _get_card(repo, sc, num), owner, Zone.DECK)
            state.player_by_id(owner).deck.append(ci)
            out.append(ci)
        return out

    def test_152_heroism_damage_and_reorder(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard, DiscardRevealed, KeepRevealed
        state = _make_state()
        _give_resources(state, "P0", 10)
        # top 4: R2-D2 (Heroism), Open Fire (no), C-3PO (Heroism), 2-1B (no)
        r2, openfire, c3po, droid = self._deck(
            state, repo, "P0",
            [("SOR", "236"), ("SOR", "172"), ("SOR", "238"), ("SOR", "59")])
        event = CardInstance("P0_evt", _get_card(repo, "SOR", "152"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(event)
        state = apply(state, PlayCard(event.instance_id))

        assert state.players[1].base_instance.damage == 2, "2 Heroism → 2 damage"
        assert state.pending_decisions[-1].kind == "reveal_top"
        state = apply(state, DiscardRevealed(openfire.instance_id))
        state = apply(state, KeepRevealed(c3po.instance_id))
        state = apply(state, KeepRevealed(r2.instance_id))
        state = apply(state, KeepRevealed(droid.instance_id))
        assert not state.pending_decisions
        deck = state.player_by_id("P0").deck
        assert [c.instance_id for c in deck[:3]] == [
            c3po.instance_id, r2.instance_id, droid.instance_id], "kept order on top"
        assert any(c.instance_id == openfire.instance_id
                   for c in state.player_by_id("P0").discard), "Open Fire discarded"
        assert state.active_player_index == 1, "turn passes to the opponent"

    def test_152_context_exposes_revealed_card_identities(self, repo):
        """The reveal_top context carries each revealed card's identity (in
        top→down order) so the UI can show the actual cards, not opaque ids."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        _give_resources(state, "P0", 10)
        r2, openfire, c3po, droid = self._deck(
            state, repo, "P0",
            [("SOR", "236"), ("SOR", "172"), ("SOR", "238"), ("SOR", "59")])
        event = CardInstance("P0_evt", _get_card(repo, "SOR", "152"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(event)
        state = apply(state, PlayCard(event.instance_id))

        ctx = state.pending_decisions[-1].context
        revealed = ctx["revealed"]
        assert [r["instance_id"] for r in revealed] == [
            r2.instance_id, openfire.instance_id,
            c3po.instance_id, droid.instance_id], "revealed order = top→down"
        assert all(r["card_id"] >= 0 and r["card_name"] for r in revealed)
        assert revealed[0]["card_name"] == r2.card_def.display_name

    def test_152_no_heroism_no_damage(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        _give_resources(state, "P0", 10)
        self._deck(state, repo, "P0", [("SOR", "172"), ("SOR", "59")])  # neither Heroism
        event = CardInstance("P0_evt", _get_card(repo, "SOR", "152"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(event)
        state = apply(state, PlayCard(event.instance_id))
        assert state.players[1].base_instance.damage == 0
        assert state.pending_decisions[-1].kind == "reveal_top"


# ── SOR_99 Bright Hope ────────────────────────────────────────────────────────

class TestBrightHope:
    """When Played: You may return a friendly non-leader ground unit to its
    owner's hand. If you do, draw a card."""

    def _deck_card(self, state, repo, pid="P0"):
        """Put one card in a player's deck so a draw is observable."""
        from swu.engine.state import CardInstance, Zone
        filler = _get_card(repo, "SOR", "46")
        state.player_by_id(pid).deck.append(
            CardInstance(f"{pid}_deck_top", filler, pid, Zone.DECK))

    def test_99_return_ground_unit_then_draw(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget,
        )
        bright = _get_card(repo, "SOR", "99")
        ground = _get_card(repo, "SOR", "46")  # friendly non-leader ground unit
        state = _make_state()
        bright_ci = _place(state, "P0", bright, "space")   # Bright Hope is a space unit
        ground_ci = _place(state, "P0", ground, "ground")
        self._deck_card(state, repo)
        deck_before = len(state.players[0].deck)

        state = _fire_when_played(state, bright_ci)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)
                      and a.target_id == ground_ci.instance_id)
        state = apply(state, choose)

        assert _find_instance(state, ground_ci.instance_id) is None, "unit left the arena"
        hand_ids = {ci.instance_id for ci in state.players[0].hand}
        assert ground_ci.instance_id in hand_ids, "returned to owner's hand"
        assert len(state.players[0].deck) == deck_before - 1, "drew exactly one card"

    def test_99_cannot_target_self_or_space_units(self, repo):
        """The return is restricted to friendly *ground* non-leaders — Bright Hope
        (a space unit) is never an eligible target."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget,
        )
        bright = _get_card(repo, "SOR", "99")
        ground = _get_card(repo, "SOR", "46")
        state = _make_state()
        bright_ci = _place(state, "P0", bright, "space")
        ground_ci = _place(state, "P0", ground, "ground")

        state = _fire_when_played(state, bright_ci)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        target_ids = {a.target_id for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)}
        assert ground_ci.instance_id in target_ids
        assert bright_ci.instance_id not in target_ids, "space unit not eligible"

    def test_99_no_ground_unit_auto_declines_no_draw(self, repo):
        """With no friendly ground unit the optional trigger is auto-declined —
        no prompt, and (crucially) no card is drawn."""
        bright = _get_card(repo, "SOR", "99")
        state = _make_state()
        bright_ci = _place(state, "P0", bright, "space")
        self._deck_card(state, repo)
        deck_before = len(state.players[0].deck)

        state = _fire_when_played(state, bright_ci)
        assert not state.pending_decisions, "no prompt when nothing can be returned"
        assert len(state.players[0].deck) == deck_before, "no return → no draw"

    def test_99_decline_does_not_draw(self, repo):
        """Declining the 'may' returns nothing and draws nothing."""
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        bright = _get_card(repo, "SOR", "99")
        ground = _get_card(repo, "SOR", "46")
        state = _make_state()
        bright_ci = _place(state, "P0", bright, "space")
        ground_ci = _place(state, "P0", ground, "ground")
        self._deck_card(state, repo)
        deck_before = len(state.players[0].deck)

        state = _fire_when_played(state, bright_ci)
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        assert not state.pending_decisions
        assert _find_instance(state, ground_ci.instance_id) is not None, "unit stayed in play"
        assert len(state.players[0].deck) == deck_before, "declined → no draw"


# ── SOR_103 Rebel Assault ─────────────────────────────────────────────────────

class TestRebelAssault:
    """Attack with a REBEL unit (+1/+0), then attack with another REBEL unit
    (+1/+0)."""

    def _play_event(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        _give_resources(state, "P0", 5)
        evt = CardInstance("P0_rebel_assault", _get_card(repo, "SOR", "103"),
                           "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(evt)
        return apply(state, PlayCard(evt.instance_id))

    def test_103_two_rebel_attacks_each_plus_one(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel 3/7
        b = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # Rebel 3/3
        state = self._play_event(state, repo)

        # First granted attack: attack the enemy base with unit a (3 power +1).
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk_a = next(x for x in legal_actions(state)
                     if isinstance(x, AttackWithUnit) and x.attacker_id == a.instance_id
                     and x.defender_id is None)
        state = apply(state, atk_a)
        assert state.players[1].base_instance.damage == 4, "3 power +1 bonus"

        # Second granted attack still pending: attack base with unit b (3 +1).
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk_b = next(x for x in legal_actions(state)
                     if isinstance(x, AttackWithUnit) and x.attacker_id == b.instance_id
                     and x.defender_id is None)
        state = apply(state, atk_b)
        assert state.players[1].base_instance.damage == 8, "both attacks +1 each"
        assert not state.pending_decisions
        assert state.active_player_index == 1, "turn passes after both attacks"

    def test_103_only_rebel_units_offered(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        rebel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # Rebel
        nonrebel = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        state = self._play_event(state, repo)
        attacker_ids = {x.attacker_id for x in legal_actions(state)
                        if isinstance(x, AttackWithUnit)}
        assert rebel.instance_id in attacker_ids
        assert nonrebel.instance_id not in attacker_ids, "non-Rebel not eligible"

    def test_103_fizzles_without_rebel_units(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # only Imperial
        state = self._play_event(state, repo)
        # Both granted attacks fizzle: only a decline is offered each time.
        assert state.pending_decisions[-1].kind == "granted_attack"
        decline = next(x for x in legal_actions(state)
                       if isinstance(x, DeclineGrantedAttack))
        state = apply(state, decline)
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, DeclineGrantedAttack)))
        assert not state.pending_decisions
        assert state.players[1].base_instance.damage == 0


# ── SOR_144 Red Three ─────────────────────────────────────────────────────────

class TestRedThree:
    """Each other friendly [Heroism] unit gains Raid 1 (Red Three keeps its own
    printed Raid 1)."""

    def test_144_grants_raid_to_other_heroism_units(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "SOR", "144"), "space")
        ally_heroism = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Heroism
        ally_plain = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")    # no Heroism
        enemy_heroism = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # enemy Heroism

        assert keyword_value(state, ally_heroism, Keyword.RAID) == 1, "other friendly Heroism gains Raid 1"
        assert keyword_value(state, ally_plain, Keyword.RAID) == 0, "non-Heroism unaffected"
        assert keyword_value(state, enemy_heroism, Keyword.RAID) == 0, "enemy unaffected"
        assert keyword_value(state, red, Keyword.RAID) == 1, "Red Three keeps its own printed Raid 1 (not_self)"

    def test_144_grant_disappears_when_red_three_leaves(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "SOR", "144"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, ally, Keyword.RAID) == 1
        state.players[0].space_arena.remove(red)
        assert keyword_value(state, ally, Keyword.RAID) == 0, "grant winks off with the source"


# ── SHD_126 The Darksaber ─────────────────────────────────────────────────────

class TestTheDarksaber:
    """Attached unit gains 'On Attack: Give an Experience token to each other
    friendly Mandalorian unit.'"""

    def _attach(self, state, host_ci, repo):
        from swu.engine.state import CardInstance
        upg = _get_card(repo, "SHD", "126")
        up_ci = CardInstance(f"darksaber_{uuid.uuid4().hex[:4]}", upg,
                             host_ci.owner_id, host_ci.zone)
        host_ci.attached_upgrades.append(up_ci)
        return up_ci

    def test_126_tokens_each_other_friendly_mandalorian(self, repo):
        from swu.engine.keywords import experience_on
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # non-Mandalorian host
        mando1 = _place(state, "P0", _get_card(repo, "SHD", "136"), "ground")  # friendly Mandalorian
        mando2 = _place(state, "P0", _get_card(repo, "SHD", "162"), "ground")  # friendly Mandalorian
        non_mando = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy_mando = _place(state, "P1", _get_card(repo, "SHD", "136"), "ground")
        self._attach(state, host, repo)

        state = _fire_on_attack(state, host)
        assert not state.pending_decisions, "EACH_FRIENDLY auto-targets — resolves inline"
        assert experience_on(_find_instance(state, mando1.instance_id)) == 1
        assert experience_on(_find_instance(state, mando2.instance_id)) == 1
        assert experience_on(_find_instance(state, non_mando.instance_id)) == 0, "non-Mandalorian unaffected"
        assert experience_on(_find_instance(state, enemy_mando.instance_id)) == 0, "enemy unaffected"

    def test_126_host_itself_excluded_when_mandalorian(self, repo):
        """A Mandalorian host does not give itself a token ('each OTHER')."""
        from swu.engine.keywords import experience_on
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SHD", "136"), "ground")   # Mandalorian host
        ally = _place(state, "P0", _get_card(repo, "SHD", "162"), "ground")   # other Mandalorian
        self._attach(state, host, repo)
        state = _fire_on_attack(state, host)
        assert experience_on(_find_instance(state, host.instance_id)) == 0, "not_self excludes the host"
        assert experience_on(_find_instance(state, ally.instance_id)) == 1


# ── SOR_245 Medal Ceremony ────────────────────────────────────────────────────

class TestMedalCeremony:
    """Give an Experience token to each of up to 3 REBEL units that attacked this
    phase."""

    def _play_event(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        _give_resources(state, "P0", 3)
        evt = CardInstance("P0_medal", _get_card(repo, "SOR", "245"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(evt)
        return apply(state, PlayCard(evt.instance_id))

    def _mark_attacked(self, state, *cis):
        for ci in cis:
            state.game_memory.units_attacked_this_round.add(ci.instance_id)

    def test_245_eligibility_rebel_and_attacked_only(self, repo):
        from swu.engine.actions import legal_actions, SelectTokenTarget
        state = _make_state()
        rebel_atk = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel, attacked
        rebel_idle = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Rebel, did not attack
        nonrebel_atk = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # non-Rebel, attacked
        self._mark_attacked(state, rebel_atk, nonrebel_atk)
        state = self._play_event(state, repo)

        assert state.pending_decisions[-1].kind == "select_token"
        eligible = {a.target_id for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)}
        assert eligible == {rebel_atk.instance_id}, "only the Rebel unit that attacked"

    def test_245_gives_tokens_to_chosen_distinct_units(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        from swu.engine.keywords import experience_on
        state = _make_state()
        r1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        r2 = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        self._mark_attacked(state, r1, r2)
        state = self._play_event(state, repo)

        state = apply(state, SelectTokenTarget(r1.instance_id))
        # After one pick, r1 is no longer offered (distinct units).
        remaining = {a.target_id for a in legal_actions(state)
                     if isinstance(a, SelectTokenTarget)}
        assert remaining == {r2.instance_id}
        state = apply(state, SelectTokenTarget(r2.instance_id))
        # No more eligible units → decision auto-resolves.
        assert not state.pending_decisions
        assert experience_on(_find_instance(state, r1.instance_id)) == 1
        assert experience_on(_find_instance(state, r2.instance_id)) == 1
        assert state.active_player_index == 1, "turn passes after the event"

    def test_245_caps_at_three(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        from swu.engine.keywords import experience_on
        state = _make_state()
        rebels = [_place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
                  for _ in range(4)]
        self._mark_attacked(state, *rebels)
        state = self._play_event(state, repo)
        for _ in range(3):
            pick = next(a for a in legal_actions(state)
                        if isinstance(a, SelectTokenTarget))
            state = apply(state, pick)
        assert not state.pending_decisions, "decision pops after the 3rd token (cap)"
        tokened = sum(1 for r in rebels
                      if experience_on(_find_instance(state, r.instance_id)) == 1)
        assert tokened == 3, "exactly 3 units received a token"

    def test_245_finish_early(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget, FinishSelectToken
        from swu.engine.keywords import experience_on
        state = _make_state()
        r1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        r2 = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        self._mark_attacked(state, r1, r2)
        state = self._play_event(state, repo)
        state = apply(state, SelectTokenTarget(r1.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishSelectToken)))
        assert not state.pending_decisions
        assert experience_on(_find_instance(state, r1.instance_id)) == 1
        assert experience_on(_find_instance(state, r2.instance_id)) == 0, "stopped early"

    def test_245_no_eligible_units_fizzles(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Rebel but did not attack
        state = self._play_event(state, repo)
        assert not state.pending_decisions, "no eligible unit → no prompt, fizzles cleanly"


# ── SOR_22 Energy Conversion Lab ──────────────────────────────────────────────

class TestEnergyConversionLab:
    """Epic Action: Play a unit that costs 6 resources or less from your hand.
    Give it Ambush for this phase.

    A once-per-game activated ability on a *base* — exercises the new base_zone
    activated-ability enumeration plus the play-from-hand cost_max / grant_keyword
    seams."""

    def _setup_base(self, state, repo, owner="P0"):
        """Make ``owner``'s base the Energy Conversion Lab. Returns its instance."""
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_ecl", _get_card(repo, "SOR", "22"), owner, Zone.BASE_ZONE)
        state.player_by_id(owner).base_zone = [ci]
        return ci

    def _hand(self, state, repo, sc, num, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_h_{num}_{uuid.uuid4().hex[:4]}",
                          _get_card(repo, sc, num), owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def test_22_epic_plays_unit_and_grants_ambush(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ecl_ci = self._setup_base(state, repo)
        unit_ci = self._hand(state, repo, "SOR", "46")           # cost-4 ground unit
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # Ambush target
        _give_resources(state, "P0", 15)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == ecl_ci.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        assert ecl_ci.instance_id in state.game_memory.epic_actions_spent, "epic spent (once per game)"

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit_ci.instance_id)
        state = apply(state, play)

        played = _find_instance(state, unit_ci.instance_id)
        assert played is not None, "the chosen unit is now in play"
        assert has_keyword(state, played, Keyword.AMBUSH), "it gained Ambush for this phase"
        assert state.pending_decisions[-1].kind == "ambush", "granted Ambush triggers on entry"

    def test_22_excludes_units_costing_more_than_6(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        state = _make_state()
        ecl_ci = self._setup_base(state, repo)
        small = self._hand(state, repo, "SOR", "46")    # cost 4 → eligible
        big = self._hand(state, repo, "SOR", "118")     # cost 7 → excluded
        _give_resources(state, "P0", 20)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == ecl_ci.instance_id)
        state = apply(state, use)
        offered = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert small.instance_id in offered
        assert big.instance_id not in offered, "cost-7 unit excluded by cost_max=6"

    def test_22_epic_not_offered_without_eligible_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        ecl_ci = self._setup_base(state, repo)
        self._hand(state, repo, "SOR", "118")  # only a cost-7 unit in hand
        _give_resources(state, "P0", 20)
        assert not any(isinstance(a, UseAbility) and a.source_id == ecl_ci.instance_id
                       for a in legal_actions(state)), "epic gated off — no unit ≤6 to play"


# ── SHD_129 Timely Intervention ───────────────────────────────────────────────

class TestTimelyIntervention:
    """Play a unit from your hand. Give it Ambush for this phase. (Smuggle is
    handled by the keyword engine.)"""

    def _play_event(self, state, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        evt = CardInstance(f"P0_ti_{uuid.uuid4().hex[:4]}",
                           _get_card(repo, "SHD", "129"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(evt)
        return apply(state, PlayCard(evt.instance_id))

    def _hand_unit(self, state, repo, sc, num):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"P0_u_{num}_{uuid.uuid4().hex[:4]}",
                          _get_card(repo, sc, num), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(ci)
        return ci

    def test_129_plays_unit_and_grants_ambush(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _give_resources(state, "P0", 15)
        unit_ci = self._hand_unit(state, repo, "SOR", "46")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # Ambush target
        state = self._play_event(state, repo)

        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit_ci.instance_id)
        state = apply(state, play)

        played = _find_instance(state, unit_ci.instance_id)
        assert played is not None and has_keyword(state, played, Keyword.AMBUSH)
        assert state.pending_decisions[-1].kind == "ambush", "granted Ambush triggers on entry"

    def test_129_has_no_cost_cap(self, repo):
        """Unlike Energy Conversion Lab, Timely Intervention plays *any* affordable
        unit — a cost-7 unit is offered."""
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        _give_resources(state, "P0", 20)
        big = self._hand_unit(state, repo, "SOR", "118")  # cost 7
        state = self._play_event(state, repo)
        offered = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert big.instance_id in offered, "no cost cap on Timely Intervention"


# ── Registration smoke ────────────────────────────────────────────────────────

class TestSabineGroupRegistration:
    @pytest.mark.parametrize("sc,num", [
        ("SOR", "14"), ("SOR", "142"), ("SOR", "143"),
        ("SOR", "145"), ("SOR", "152"), ("SOR", "99"), ("SHD", "147"),
        ("SOR", "103"), ("SHD", "126"), ("SOR", "144"), ("SOR", "245"),
        ("SOR", "22"), ("SHD", "129"),
    ])
    def test_registered_and_not_escape_hatch(self, sc, num):
        import swu.cards  # noqa: F401
        from swu.abilities.registry import get_abilities, is_escape_hatch
        assert get_abilities(sc, num), f"{sc}_{num} should be registered"
        assert not is_escape_hatch(sc, num), f"{sc}_{num} should not be an escape hatch"
