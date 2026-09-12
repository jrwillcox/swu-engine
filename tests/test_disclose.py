"""Tests for the disclose primitive — the ``disclose`` decision kind (Stage 4
batch 21 framework escalation).

"You may disclose <aspects> (reveal cards from your hand with these aspect icons
among them). If you do, <payoff>."  Serves Karis Nemik SEC_148 ("When Defeated:
disclose Aggression+Heroism → create a Spy token and ready it") and Syril Karn
SEC_133 ("On Attack: disclose Aggression×2+Villainy → choose a unit; deal 2 to it
unless its controller discards a card").  The payoffs reuse existing seams
(create-token-unit; may_discard-else-damage); the disclose gate is the primitive.

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.
"""
from __future__ import annotations

import uuid

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_on_attack, _defeat_and_fire,
)


# ── local helpers ──────────────────────────────────────────────────────────────

def _add_hand(state, owner, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner}_hand_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner, zone=Zone.HAND,
    )
    state.player_by_id(owner).hand.append(ci)
    return ci


def _settle(state, *, decline_disclose=False, discard_to_prevent=False):
    """Drive AutoResolveEffects / disclose / may_discard to quiescence."""
    from swu.engine.actions import (
        legal_actions, apply, AutoResolveEffects,
        DiscloseSelectCard, DeclineDisclose, DiscardRandomCard, DeclineDiscard)
    for _ in range(80):
        if not state.pending_decisions:
            break
        acts = legal_actions(state)
        auto = next((x for x in acts if isinstance(x, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
            continue
        kind = state.pending_decisions[-1].kind
        if kind == "disclose":
            if not decline_disclose:
                pick = next((x for x in acts if isinstance(x, DiscloseSelectCard)),
                            None)
                if pick is not None:
                    state = apply(state, pick)
                    continue
            state = apply(state, next(x for x in acts
                                      if isinstance(x, DeclineDisclose)))
            continue
        if kind == "may_discard":
            if discard_to_prevent:
                d = next((x for x in acts if isinstance(x, DiscardRandomCard)), None)
                if d is not None:
                    state = apply(state, d)
                    continue
            state = apply(state, next(x for x in acts
                                      if isinstance(x, DeclineDiscard)))
            continue
        break
    return state


def _spies(state, pid):
    ps = state.player_by_id(pid)
    return [c for c in ps.ground_arena + ps.space_arena if c.card_def.name == "Spy"]


def _find(state, pid, iid):
    ps = state.player_by_id(pid)
    for c in ps.ground_arena + ps.space_arena:
        if c.instance_id == iid:
            return c
    return None


# Concrete hand cards carrying the needed aspect icons.
def _agg_vil(repo):   # SOR_131 Fifth Brother — Aggression + Villainy
    return _get_card(repo, "SOR", "131")
def _her(repo):       # SOR_103 Rebel Assault — Command + Heroism
    return _get_card(repo, "SOR", "103")
def _agg2(repo):      # SOR_128 Death Star Stormtrooper — Villainy + Aggression
    return _get_card(repo, "SOR", "128")
def _neutral(repo):   # SOR_58 Vigilance — mono-Vigilance (no Aggression/Heroism)
    return _get_card(repo, "SOR", "58")


# ── Karis Nemik SEC_148 (WhenDefeated, disclose Agg+Heroism → Spy token+ready) ──

class TestKarisNemik:
    def _setup(self, repo, with_aspects=True):
        state = _make_state()
        karis = _place(state, "P0", _get_card(repo, "SEC", "148"), "ground")
        if with_aspects:
            _add_hand(state, "P0", _agg_vil(repo))   # Aggression
            _add_hand(state, "P0", _her(repo))       # Heroism
        return state, karis

    def test_sec_148_disclose_creates_ready_spy(self, repo):
        state, karis = self._setup(repo)
        state = _defeat_and_fire(state, karis, "P0")
        # A disclose decision should surface (discloser = P0).
        state2 = state
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        for _ in range(10):
            a = next((x for x in legal_actions(state2)
                      if isinstance(x, AutoResolveEffects)), None)
            if a is None:
                break
            state2 = apply(state2, a)
        assert state2.pending_decisions[-1].kind == "disclose"
        assert state2.pending_decisions[-1].deciding_player_id == "P0"
        state = _settle(state)
        assert not state.pending_decisions
        spies = _spies(state, "P0")
        assert len(spies) == 1
        assert spies[0].exhausted is False   # created AND readied

    def test_sec_148_decline_disclose_no_token(self, repo):
        state, karis = self._setup(repo)
        state = _defeat_and_fire(state, karis, "P0")
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert _spies(state, "P0") == []

    def test_sec_148_cannot_disclose_with_no_matching_cards(self, repo):
        # Empty hand → the discloser cannot cover the requirement → no prompt.
        state, karis = self._setup(repo, with_aspects=False)
        state = _defeat_and_fire(state, karis, "P0")
        state = _settle(state)
        assert not state.pending_decisions
        assert _spies(state, "P0") == []

    def test_sec_148_neutral_hand_cannot_disclose(self, repo):
        # A hand with cards that bear neither Aggression nor Heroism → no prompt.
        state = _make_state()
        karis = _place(state, "P0", _get_card(repo, "SEC", "148"), "ground")
        _add_hand(state, "P0", _neutral(repo))
        _add_hand(state, "P0", _neutral(repo))
        state = _defeat_and_fire(state, karis, "P0")
        state = _settle(state)
        assert not state.pending_decisions
        assert _spies(state, "P0") == []


# ── Syril Karn SEC_133 (On Attack, disclose AAV → deal 2 unless controller discards) ──

class TestSyrilKarn:
    def _setup(self, repo, *, p1_hand=1):
        state = _make_state()
        syril = _place(state, "P0", _get_card(repo, "SEC", "133"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 5/7
        _add_hand(state, "P0", _agg_vil(repo))   # Aggression + Villainy
        _add_hand(state, "P0", _agg2(repo))      # Aggression (covers 2nd)
        for _ in range(p1_hand):
            _add_hand(state, "P1", _neutral(repo))
        return state, syril, enemy

    def _fire_and_target(self, state, syril, enemy):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _fire_on_attack(state, syril, defender_ci=enemy)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        return apply(state, pick)

    def test_sec_133_disclose_then_controller_declines_takes_damage(self, repo):
        state, syril, enemy = self._setup(repo, p1_hand=1)
        state = self._fire_and_target(state, syril, enemy)
        # After targeting, disclosing pushes a may_discard (P1 decides).
        state = _settle(state, discard_to_prevent=False)
        assert not state.pending_decisions
        assert _find(state, "P1", enemy.instance_id).damage == 2

    def test_sec_133_controller_discards_to_prevent_damage(self, repo):
        state, syril, enemy = self._setup(repo, p1_hand=2)
        before = len(state.player_by_id("P1").hand)
        state = self._fire_and_target(state, syril, enemy)
        state = _settle(state, discard_to_prevent=True)
        assert not state.pending_decisions
        assert _find(state, "P1", enemy.instance_id).damage == 0
        assert len(state.player_by_id("P1").hand) == before - 1

    def test_sec_133_empty_hand_controller_takes_damage_inline(self, repo):
        # P1 has no card to discard → the damage lands with no may_discard decision.
        state, syril, enemy = self._setup(repo, p1_hand=0)
        state = self._fire_and_target(state, syril, enemy)
        state = _settle(state)
        assert not state.pending_decisions
        assert _find(state, "P1", enemy.instance_id).damage == 2

    def test_sec_133_decline_disclose_no_effect(self, repo):
        state, syril, enemy = self._setup(repo, p1_hand=1)
        state = self._fire_and_target(state, syril, enemy)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert _find(state, "P1", enemy.instance_id).damage == 0
        assert len(state.player_by_id("P1").hand) == 1   # no discard
