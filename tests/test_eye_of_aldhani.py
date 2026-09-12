"""Tests for the two primitives that encode The Eye of Aldhani SEC_73/SECP_5 — the
LAST needs_encoding reprint group, completing the whole reprint-duplicate sweep.

The card (1-cost Vigilance Event): "At the start of the next action phase, for each
enemy unit, its controller must pay 1 resource or exhaust that unit."  Two composed
primitives:

  * A DELAYED ACTION-PHASE-START SCHEDULER — the event resolves in ACTION and goes to
    discard (no in-play host for a PhaseStartTrigger), so it records a serialised
    entry in ``GameState.scheduled_action_phase_effects``, drained once at the next
    action-phase start (``_fire_scheduled_action_phase_effects``, called from
    ``_regroup_rollover`` / ``_start_action_phase``).
  * A PER-ENEMY PAY-OR-EXHAUST decision — a multi-unit sibling of the regroup_upkeep
    decision (Millennium Falcon SOR_193), but the DECIDER is the enemy (each unit's
    controller) and the consequence is exhaust, not bounce.

Scenario cards (all real): SOR_46 Consular Security Force (3/7 vanilla unit) is the
plain enemy unit; the SEC_73 event is played from P0's hand, so its enemies are P1's
units and the decision is addressed to P1.
"""
from __future__ import annotations


from tests.test_sor_cards import (  # noqa: F401
    repo, _get_card, _make_state, _place, _give_resources, _play_event_from_hand,
)


def _drain(state):
    """Apply any pending AutoResolveEffects to quiescence (resume a buried
    resolve_effects decision)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(25):
        if not state.pending_decisions:
            break
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        if auto is None:
            break
        state = apply(state, auto)
    return state


def _enemy_setup(repo, *, n_units=2, ready=True, resources=5):
    """P1 (the enemy of caster P0) fields ``n_units`` ground units and ``resources``
    ready resources; the SEC_73 schedule is queued for P0.  Returns (state, units)."""
    state = _make_state()
    units = []
    for _ in range(n_units):
        u = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        u.exhausted = not ready
        units.append(u)
    if resources:
        _give_resources(state, "P1", resources)
    state.scheduled_action_phase_effects.append(
        {"kind": "eye_of_aldhani", "controller_id": "P0"})
    return state, units


# ── Registration + the completed reprint group ───────────────────────────────

class TestEyeOfAldhaniRegistration:
    def test_sec_73_registered_as_event_ability(self, repo):
        from swu.abilities.registry import get_abilities, EventAbility
        specs = get_abilities("SEC", "73")
        assert any(isinstance(s, EventAbility) for s in specs)

    def test_sec_73_secp_5_alias_to_canonical(self, repo):
        from tests.dbpath import skip_on_fixture
        skip_on_fixture("reprint aliasing needs every printing in the DB")
        from swu.abilities.registry import get_abilities
        assert get_abilities("SECP", "5") is get_abilities("SEC", "73")


# ── The delayed scheduler ─────────────────────────────────────────────────────

class TestEyeOfAldhaniScheduler:
    def test_sec_73_play_schedules_effect_for_the_caster(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "SEC", "73", owner="P0")
        state = _drain(state)
        sched = state.scheduled_action_phase_effects
        assert len(sched) == 1
        assert sched[0]["kind"] == "eye_of_aldhani"
        assert sched[0]["controller_id"] == "P0"

    def test_sec_73_regroup_rollover_fires_and_clears_schedule(self, repo):
        from swu.engine.actions import _regroup_rollover
        state, units = _enemy_setup(repo)
        _regroup_rollover(state)
        # The one-shot schedule is drained (won't re-fire next round) …
        assert state.scheduled_action_phase_effects == []
        # … into a pay_or_exhaust decision addressed to the enemy P1.
        top = state.pending_decisions[-1]
        assert top.kind == "pay_or_exhaust"
        assert top.deciding_player_id == "P1"


# ── The per-enemy pay-or-exhaust decision ─────────────────────────────────────

class TestEyeOfAldhaniPayOrExhaust:
    def test_sec_73_fires_decision_to_enemy_with_ready_units(self, repo):
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state, units = _enemy_setup(repo)
        _fire_scheduled_action_phase_effects(state)
        top = state.pending_decisions[-1]
        assert top.kind == "pay_or_exhaust"
        assert top.deciding_player_id == "P1"          # each unit's controller decides
        assert set(top.context["pending_ids"]) == {u.instance_id for u in units}

    def test_sec_73_pay_1_resource_keeps_unit_ready(self, repo):
        from swu.engine.actions import (
            _fire_scheduled_action_phase_effects, legal_actions, apply,
            PayToAvoidExhaust)
        state, units = _enemy_setup(repo, n_units=1)
        _fire_scheduled_action_phase_effects(state)
        ready_before = sum(1 for r in state.player_by_id("P1").resources
                           if not r.exhausted)
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PayToAvoidExhaust))
        state = apply(state, act)
        # One resource paid; the unit stayed ready; the decision is done.
        ready_after = sum(1 for r in state.player_by_id("P1").resources
                          if not r.exhausted)
        assert ready_after == ready_before - 1
        _, u = state.find_instance(units[0].instance_id)
        assert not u.exhausted
        assert not state.pending_decisions

    def test_sec_73_decline_exhausts_the_unit(self, repo):
        from swu.engine.actions import (
            _fire_scheduled_action_phase_effects, legal_actions, apply, AcceptExhaust)
        state, units = _enemy_setup(repo, n_units=1)
        _fire_scheduled_action_phase_effects(state)
        act = next(a for a in legal_actions(state) if isinstance(a, AcceptExhaust))
        state = apply(state, act)
        _, u = state.find_instance(units[0].instance_id)
        assert u.exhausted
        assert not state.pending_decisions

    def test_sec_73_resolves_each_unit_then_pops(self, repo):
        from swu.engine.actions import (
            _fire_scheduled_action_phase_effects, legal_actions, apply, AcceptExhaust)
        state, units = _enemy_setup(repo, n_units=2)
        _fire_scheduled_action_phase_effects(state)
        after_idx = state.pending_decisions[-1].after_resolve_player_index
        # Exhaust both, one at a time — the decision stays up until all are decided.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptExhaust)))
        assert state.pending_decisions[-1].kind == "pay_or_exhaust"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptExhaust)))
        assert not state.pending_decisions
        assert state.active_player_index == after_idx
        assert all(state.find_instance(u.instance_id)[1].exhausted for u in units)

    def test_sec_73_no_decision_without_a_ready_enemy_unit(self, repo):
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state, _ = _enemy_setup(repo, n_units=2, ready=False)   # all exhausted
        _fire_scheduled_action_phase_effects(state)
        assert not any(d.kind == "pay_or_exhaust" for d in state.pending_decisions)

    def test_sec_73_skips_already_exhausted_units(self, repo):
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state, units = _enemy_setup(repo, n_units=2)
        units[1].exhausted = True    # only units[0] is ready
        _fire_scheduled_action_phase_effects(state)
        top = state.pending_decisions[-1]
        assert top.context["pending_ids"] == [units[0].instance_id]

    def test_sec_73_pay_not_offered_without_a_ready_resource(self, repo):
        from swu.engine.actions import (
            _fire_scheduled_action_phase_effects, legal_actions,
            PayToAvoidExhaust, AcceptExhaust)
        state, units = _enemy_setup(repo, n_units=1, resources=0)
        _fire_scheduled_action_phase_effects(state)
        acts = legal_actions(state)
        assert not any(isinstance(a, PayToAvoidExhaust) for a in acts)
        assert any(isinstance(a, AcceptExhaust) for a in acts)

    def test_sec_73_only_enemy_units_targeted_not_own(self, repo):
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state, units = _enemy_setup(repo, n_units=1)
        own = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # caster's unit
        _fire_scheduled_action_phase_effects(state)
        top = state.pending_decisions[-1]
        assert own.instance_id not in top.context["pending_ids"]
        assert top.context["pending_ids"] == [units[0].instance_id]


# ── Serialisation + invariants ────────────────────────────────────────────────

class TestEyeOfAldhaniRobustness:
    def test_sec_73_scheduled_effect_serialises(self, repo):
        from swu.engine.state import GameState
        state, _ = _enemy_setup(repo)
        restored = GameState.from_json(state.to_json())
        assert restored.scheduled_action_phase_effects == \
            state.scheduled_action_phase_effects

    def test_sec_73_serialises_across_pending_decision(self, repo):
        from swu.engine.state import GameState
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state, units = _enemy_setup(repo)
        _fire_scheduled_action_phase_effects(state)
        restored = GameState.from_json(state.to_json())
        top = restored.pending_decisions[-1]
        assert top.kind == "pay_or_exhaust"
        assert set(top.context["pending_ids"]) == {u.instance_id for u in units}

    def test_sec_73_invariants_hold_across_resolution(self, repo):
        from swu.engine.actions import (
            _fire_scheduled_action_phase_effects, legal_actions, apply, AcceptExhaust)
        from swu.engine.invariants import CheckContext, check
        state, units = _enemy_setup(repo, n_units=2)
        ctx = CheckContext.from_state(state)
        _fire_scheduled_action_phase_effects(state)
        check(state, ctx)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptExhaust)))
        check(state, ctx)
