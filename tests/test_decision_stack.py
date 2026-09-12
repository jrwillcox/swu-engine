"""
Tests for the generic pending-decision infrastructure.

These tests verify the decision stack works correctly INDEPENDENT of any
specific keyword, using the test-only 'test' decision kind.  They cover
the properties listed in the Phase 2 spec:
  * serialisation round-trip mid-decision
  * determinism with decisions in the action log
  * view_for shows decision is pending; only decider sees context
  * illegal decision answers rejected
  * random bot picks from legal_actions transparently
"""
from __future__ import annotations

import pytest

from tests.dbpath import db_path, require_db

_DB = db_path()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_action_state(seed=42):
    """Return a minimal ACTION-phase GameState using vanilla decks."""
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import build_vanilla_deck
    from swu.engine.actions import create_game
    repo = CardRepository(_DB)
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    from conftest import run_through_setup
    return run_through_setup(create_game("P0", da, "P1", db, seed=seed))


def _push_test_decision(state, deciding_pid, after_idx, options=None):
    """Directly inject a 'test' pending decision onto state (no deepcopy)."""
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    if options is None:
        options = ["yes", "no"]
    d = PendingDecision(
        deciding_player_id=deciding_pid,
        kind="test",
        context={"options": options},
        after_resolve_player_index=after_idx,
    )
    state.pending_decisions.append(d)
    state.active_player_index = state.player_index(deciding_pid)
    state.event_log.append(DecisionPushed(
        deciding_player_id=deciding_pid,
        kind="test",
    ))


# ── Decision-stack infrastructure tests ──────────────────────────────────────

def test_legal_actions_returns_decision_options_not_normal_actions():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["yes", "no"])
    from swu.engine.actions import legal_actions, AnswerTestDecision
    acts = legal_actions(state)
    # Must be ONLY the test-decision options — no PlayCard / Pass / etc.
    assert len(acts) == 2
    assert AnswerTestDecision("yes") in acts
    assert AnswerTestDecision("no") in acts


def test_answering_decision_restores_normal_actions():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["yes", "no"])
    from swu.engine.actions import apply, legal_actions, AnswerTestDecision, Pass
    state2 = apply(state, AnswerTestDecision("yes"))
    assert not state2.pending_decisions
    acts = legal_actions(state2)
    assert any(isinstance(a, Pass) for a in acts)


def test_decision_suspends_turn_alternation():
    """Active player stays on the deciding player while decision is pending."""
    state = _make_action_state()
    orig_active = state.active_player_index
    _push_test_decision(state, "P0", after_idx=1 - orig_active, options=["yes"])
    assert state.active_player_index == state.player_index("P0")


def test_after_resolve_switches_active_player():
    state = _make_action_state()
    state.active_player_index = 0
    _push_test_decision(state, "P0", after_idx=1, options=["yes"])
    from swu.engine.actions import apply, AnswerTestDecision
    state2 = apply(state, AnswerTestDecision("yes"))
    assert state2.active_player_index == 1


def test_illegal_answer_rejected():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["yes", "no"])
    from swu.engine.actions import apply, AnswerTestDecision
    with pytest.raises(Exception):  # IllegalActionError or via apply() check
        apply(state, AnswerTestDecision("maybe"))


def test_no_decision_no_interference_with_normal_actions():
    state = _make_action_state()
    from swu.engine.actions import legal_actions, Pass
    acts = legal_actions(state)
    # Normal actions available — at minimum Pass
    assert any(isinstance(a, Pass) for a in acts)
    # No decision actions present
    from swu.engine.actions import AnswerTestDecision
    assert not any(isinstance(a, AnswerTestDecision) for a in acts)


# ── Serialisation round-trip mid-decision ─────────────────────────────────────

def test_serialise_roundtrip_mid_decision():
    require_db()  # engine token lookup / from_json needs the card database
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["go", "stop"])
    json_str = state.to_json()
    from swu.engine.state import GameState
    restored = GameState.from_json(json_str)
    assert len(restored.pending_decisions) == 1
    top = restored.pending_decisions[0]
    assert top.kind == "test"
    assert top.deciding_player_id == "P0"
    assert top.after_resolve_player_index == 1
    assert top.context["options"] == ["go", "stop"]


def test_serialise_preserves_active_player_index():
    require_db()  # engine token lookup / from_json needs the card database
    state = _make_action_state()
    state.active_player_index = 0
    _push_test_decision(state, "P0", after_idx=1, options=["a"])
    json_str = state.to_json()
    from swu.engine.state import GameState
    restored = GameState.from_json(json_str)
    assert restored.active_player_index == 0
    assert restored.pending_decisions


# ── view_for redaction ─────────────────────────────────────────────────────────

def test_view_shows_pending_decision_to_both_players():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["yes"])
    view_p0 = state.view_for("P0")
    view_p1 = state.view_for("P1")
    assert len(view_p0.pending_decisions) == 1
    assert len(view_p1.pending_decisions) == 1


def test_view_context_visible_only_to_decider():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["secret"])
    view_p0 = state.view_for("P0")
    view_p1 = state.view_for("P1")
    # Decider sees context
    assert view_p0.pending_decisions[0].is_mine is True
    assert view_p0.pending_decisions[0].context != {}
    # Opponent does NOT see context
    assert view_p1.pending_decisions[0].is_mine is False
    assert view_p1.pending_decisions[0].context == {}


# ── Random bot transparency ────────────────────────────────────────────────────

def test_random_bot_handles_decision():
    """Random bot calls legal_actions() and picks; must work mid-decision."""
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["yes", "no"])
    from swu.players.random_bot import RandomBot
    from swu.engine.actions import legal_actions, apply
    bot = RandomBot("P0", seed=0)
    acts = legal_actions(state)
    view = state.view_for("P0")
    chosen = bot.choose_action(view, acts)
    state2 = apply(state, chosen)
    assert not state2.pending_decisions


# ── Stacked decisions ─────────────────────────────────────────────────────────

def test_stacked_decisions_resolve_lifo():
    state = _make_action_state()
    _push_test_decision(state, "P0", after_idx=1, options=["outer"])
    _push_test_decision(state, "P1", after_idx=0, options=["inner"])
    from swu.engine.actions import legal_actions, apply, AnswerTestDecision
    # Top of stack is P1's decision
    acts = legal_actions(state)
    assert any(isinstance(a, AnswerTestDecision) and a.choice == "inner" for a in acts)
    state2 = apply(state, AnswerTestDecision("inner"))
    # Now P0's decision is on top
    acts2 = legal_actions(state2)
    assert any(isinstance(a, AnswerTestDecision) and a.choice == "outer" for a in acts2)
    state3 = apply(state2, AnswerTestDecision("outer"))
    assert not state3.pending_decisions
