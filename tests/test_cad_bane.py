"""Tests for the defeat-Credits-for-a-scaling-payoff primitive (Stage 4 batch 22
framework escalation).

The existing ``pay_resources_for_tokens`` decision kind (Curious Flock LOF_255) is
generalised with a ``cost_source="credit"`` cost item and an unbounded cap, so a
unit can "Defeat any number of friendly Credit tokens. Give an Experience token to
this unit for each Credit defeated this way." — Cad Bane LAW_32 (+ the reprints
C26_5 / P26_80 / P26_96, all byte-identical faces).

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_on_attack, _experience_count,
)


def _add_credits(state, pid, n):
    from swu.engine.tokens import create_credit_token
    ps = state.player_by_id(pid)
    for _ in range(n):
        create_credit_token(state, ps)


def _exp(state, iid):
    """Experience tokens on the (re-found, post-deepcopy) instance ``iid``."""
    res = state.find_instance(iid)
    return _experience_count(res[1]) if res is not None else 0


def _settle(state, *, defeat_credits):
    """Drive the pay_resources_for_tokens decision: spend ``defeat_credits`` credits
    (each granting an Experience token), then finish."""
    from swu.engine.actions import (
        legal_actions, apply, AutoResolveEffects,
        PayResourceForToken, FinishPayResources)
    spent = 0
    for _ in range(60):
        if not state.pending_decisions:
            break
        acts = legal_actions(state)
        auto = next((x for x in acts if isinstance(x, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
            continue
        if state.pending_decisions[-1].kind != "pay_resources_for_tokens":
            break
        pay = next((x for x in acts if isinstance(x, PayResourceForToken)), None)
        if spent < defeat_credits and pay is not None:
            state = apply(state, pay)
            spent += 1
            continue
        state = apply(state, next(x for x in acts
                                  if isinstance(x, FinishPayResources)))
    return state


class TestCadBane:
    def _setup(self, repo, credits):
        state = _make_state()
        cad = _place(state, "P0", _get_card(repo, "LAW", "32"), "ground")
        _add_credits(state, "P0", credits)
        return state, cad

    def test_law_32_defeat_all_credits_gives_experience(self, repo):
        state, cad = self._setup(repo, credits=3)
        state = _fire_on_attack(state, cad)
        assert state.pending_decisions[-1].kind == "pay_resources_for_tokens"
        state = _settle(state, defeat_credits=3)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").credits) == 0   # all 3 defeated
        assert _exp(state, cad.instance_id) == 3                  # one token each

    def test_law_32_defeat_some_credits(self, repo):
        state, cad = self._setup(repo, credits=3)
        state = _fire_on_attack(state, cad)
        state = _settle(state, defeat_credits=1)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").credits) == 2   # 2 remain
        assert _exp(state, cad.instance_id) == 1

    def test_law_32_finish_immediately_no_effect(self, repo):
        # "Any number" includes 0 — declining every credit is legal, no tokens.
        state, cad = self._setup(repo, credits=3)
        state = _fire_on_attack(state, cad)
        state = _settle(state, defeat_credits=0)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").credits) == 3   # untouched
        assert _exp(state, cad.instance_id) == 0

    def test_law_32_no_credits_no_decision(self, repo):
        # With no Credit token the push no-ops — the mandatory trigger fizzles.
        state, cad = self._setup(repo, credits=0)
        state = _fire_on_attack(state, cad)
        # Drain any resolve_effects, then assert no pay decision surfaced.
        state = _settle(state, defeat_credits=0)
        assert not state.pending_decisions
        assert _exp(state, cad.instance_id) == 0

    def test_law_32_auto_resolves_when_credits_exhausted(self, repo):
        # Spending the last credit auto-resolves the decision (no ready cost item
        # remains), so no explicit FinishPayResources is needed.
        state, cad = self._setup(repo, credits=2)
        state = _fire_on_attack(state, cad)
        from swu.engine.actions import legal_actions, apply, PayResourceForToken
        # Spend both credits explicitly; the second should pop the decision.
        for _ in range(2):
            acts = legal_actions(state)
            pay = next(x for x in acts if isinstance(x, PayResourceForToken))
            state = apply(state, pay)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").credits) == 0
        assert _exp(state, cad.instance_id) == 2
