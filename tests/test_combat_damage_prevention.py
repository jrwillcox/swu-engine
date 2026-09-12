"""Framework tests for the interactive combat-damage prevention primitive (the
replacement-effect framework's COMBAT-damage half; Queen Amidala SEC_101).

Amidala herself is NOT yet registered (her full "if damage would be dealt to this
unit" replacement also needs the deferred ability/indirect-damage half), so these
exercise the primitive through the public ``legal_actions`` / ``apply`` interface
with the ``InteractiveDamagePrevention`` marker registered on a stand-in card
(``SOR_46``), plus the single combat sink ``_deal_damage_with_shield`` directly.

Scenario cards (all real, so ``compute_power``/traits are exact):
  * SOR_46 Consular Security Force — 3/7, traits Rebel/Trooper, no Sentinel, no
    abilities (the marked, protected "Amidala" stand-in AND its trait-sharing
    sacrifice — a second copy shares all traits).
  * SOR_68 Cargo Juggernaut — 4/6, traits Vehicle/Tank, no Sentinel, no abilities
    (a plain no-marker attacker/defender; its traits do not overlap SOR_46, so it
    is never a sacrifice candidate).
"""
from __future__ import annotations

import pytest

import swu.abilities.registry as _registry
from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401


@pytest.fixture
def amidala_marker():
    """Temporarily register the InteractiveDamagePrevention marker on SOR_46 (the
    Amidala stand-in), restoring the registry afterwards."""
    key = ("SOR", "46")
    prev = _registry._REGISTRY.get(key)
    _registry._REGISTRY[key] = [_registry.InteractiveDamagePrevention()]
    try:
        yield
    finally:
        if prev is None:
            _registry._REGISTRY.pop(key, None)
        else:
            _registry._REGISTRY[key] = prev


def _combat_setup(repo, *, with_sacrifice=True):
    """P0 attacker (SOR_68 Cargo Juggernaut, 4 power, no marker) vs P1 defender
    (SOR_46, marked, 3/7); P1 may also hold a friendly Rebel/Trooper sacrifice
    (a second SOR_46 sharing traits with the defender)."""
    state = _make_state()
    attacker = _place(state, "P0", _get_card(repo, "SOR", "68"), "ground")
    defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
    sacrifice = None
    if with_sacrifice:
        sacrifice = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
    return state, attacker, defender, sacrifice


# ── The combat sink flag (unit-level) ──────────────────────────────────────────

class TestPreventNextCombatDamageFlag:
    def test_sec_101_flag_drops_one_combat_instance_and_disarms(self, repo):
        from swu.engine.actions import _deal_damage_with_shield
        from swu.engine.events import CombatDamagePrevented
        state = _make_state()
        unit = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        unit.prevent_next_combat_damage = True
        ps = state.player_by_id("P1")

        dealt = _deal_damage_with_shield(state, ps, unit, 4)

        assert dealt == 0
        assert unit.damage == 0
        assert unit.prevent_next_combat_damage is False  # one-shot, now disarmed
        assert any(isinstance(e, CombatDamagePrevented) for e in state.event_log)
        # A subsequent instance lands normally (the flag was consumed).
        assert _deal_damage_with_shield(state, ps, unit, 2) == 2
        assert unit.damage == 2


# ── The end-to-end checkpoint + decision ────────────────────────────────────────

class TestCombatDamagePreventionDecision:
    def test_sec_101_prevention_offered_to_defender_controller(self, repo, amidala_marker):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            ChoosePreventionSacrifice, DeclineCombatPrevention,
        )
        state, attacker, defender, sacrifice = _combat_setup(repo)
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))

        top = state.pending_decisions[-1]
        assert top.kind == "combat_damage_prevention"
        assert top.deciding_player_id == "P1"  # the protected unit's controller
        acts = legal_actions(state)
        assert any(isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == sacrifice.instance_id for a in acts)
        assert any(isinstance(a, DeclineCombatPrevention) for a in acts)

    def test_sec_101_accept_defeats_friendly_and_prevents_damage(self, repo, amidala_marker):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            ChoosePreventionSacrifice, ContinueAttack,
        )
        state, attacker, defender, sacrifice = _combat_setup(repo)
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))

        sac = next(a for a in legal_actions(state)
                   if isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == sacrifice.instance_id)
        state = apply(state, sac)

        # The sacrifice was defeated to its owner's discard.
        assert any(c.instance_id == sacrifice.instance_id
                   for c in state.player_by_id("P1").discard)
        # The pre_attack continuation is now exposed — resume combat.
        cont = next(a for a in legal_actions(state) if isinstance(a, ContinueAttack))
        state = apply(state, cont)

        # Defender took NO combat damage (prevented); attacker took the defender's 3.
        _, defn = state.find_instance(defender.instance_id)
        _, atk = state.find_instance(attacker.instance_id)
        assert defn.damage == 0
        assert atk.damage == 3
        assert defn.prevent_next_combat_damage is False  # consumed
        assert not state.pending_decisions

    def test_sec_101_decline_lets_combat_damage_land(self, repo, amidala_marker):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            DeclineCombatPrevention, ContinueAttack,
        )
        state, attacker, defender, sacrifice = _combat_setup(repo)
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineCombatPrevention)))
        # Sacrifice survives (not defeated).
        assert any(c.instance_id == sacrifice.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ContinueAttack)))

        _, defn = state.find_instance(defender.instance_id)
        assert defn.damage == 4  # attacker's full power landed

    def test_sec_101_not_offered_without_trait_sharing_friendly(self, repo, amidala_marker):
        from swu.engine.actions import apply, AttackWithUnit
        # No sacrifice on the board → the checkpoint does not arm.
        state, attacker, defender, _ = _combat_setup(repo, with_sacrifice=False)
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))
        # No prevention decision; combat resolved straight through — defender took 4.
        assert not any(d.kind == "combat_damage_prevention"
                       for d in state.pending_decisions)
        _, defn = state.find_instance(defender.instance_id)
        assert defn.damage == 4

    def test_sec_101_not_offered_when_shielded(self, repo, amidala_marker):
        from swu.engine.actions import apply, AttackWithUnit
        from swu.engine.tokens import attach_token
        state, attacker, defender, sacrifice = _combat_setup(repo)
        attach_token(state, state.player_by_id("P1"), defender, "Shield")
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))
        # Shield already prevents the damage — no prevention decision offered, and the
        # trait-sharing friendly is NOT sacrificed.
        assert not any(d.kind == "combat_damage_prevention"
                       for d in state.pending_decisions)

    def test_sec_101_attacker_side_prevention(self, repo, amidala_marker):
        """The protected unit is the ATTACKER — the decision is offered to its own
        controller, and its incoming (the defender's) combat damage is prevented."""
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            ChoosePreventionSacrifice, ContinueAttack,
        )
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # marked
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel sac
        defender = _place(state, "P1", _get_card(repo, "SOR", "68"), "ground")  # 4 power

        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))
        top = state.pending_decisions[-1]
        assert top.kind == "combat_damage_prevention"
        assert top.deciding_player_id == "P0"  # the attacker's controller decides
        sac = next(a for a in legal_actions(state)
                   if isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == friendly.instance_id)
        state = apply(state, sac)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ContinueAttack)))

        # Attacker (SOR_46) took NO combat damage (defender's 4 prevented); the
        # defender took the attacker's 3.
        _, atk = state.find_instance(attacker.instance_id)
        _, defn = state.find_instance(defender.instance_id)
        assert atk.damage == 0
        assert defn.damage == 3

    def test_sec_101_serialises_across_pending_decision(self, repo, amidala_marker):
        from swu.engine.actions import apply, AttackWithUnit
        from swu.engine.state import GameState
        state, attacker, defender, sacrifice = _combat_setup(repo)
        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))
        assert state.pending_decisions[-1].kind == "combat_damage_prevention"
        # Full JSON round-trip mid-decision (the flag + decision must survive).
        restored = GameState.from_json(state.to_json())
        assert restored.pending_decisions[-1].kind == "combat_damage_prevention"

    def test_sec_101_invariants_hold_across_prevention(self, repo, amidala_marker):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            ChoosePreventionSacrifice, ContinueAttack,
        )
        from swu.engine.invariants import CheckContext, check
        state, attacker, defender, sacrifice = _combat_setup(repo)
        ctx = CheckContext.from_state(state)

        state = apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=defender.instance_id))
        check(state, ctx)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChoosePreventionSacrifice)))
        check(state, ctx)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ContinueAttack)))
        check(state, ctx)
