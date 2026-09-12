"""Property-based engine soak via a Hypothesis stateful machine.

Where the campaign runner drives the engine with *random* bots and waits for a
bad state to turn up, this test *searches*: Hypothesis drives a sequence of
legal actions and, on any invariant violation or crash, automatically shrinks
the action sequence to a minimal reproducer.  It runs the full invariant module
(``swu.engine.invariants.check``) after every move — the same oracle the
campaign uses — so it guards the same properties but hunts for counterexamples
instead of stumbling onto them.

Tier: medium (CI).  Kept to a bounded number of examples/steps so it stays well
under a minute; the overnight campaign runner remains the scale tool.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

# hypothesis ships in the [dev] extra. Skip rather than error if only a subset of
# the extras is installed, so a partial environment still gets a green run.
pytest.importorskip("hypothesis", reason="hypothesis not installed (pip install -e '.[dev]')")

from hypothesis import settings, strategies as st        # noqa: E402
from hypothesis.stateful import (                        # noqa: E402
    RuleBasedStateMachine, rule, initialize, invariant,
)

from swu.cards.repository import CardRepository
from swu.cards.decklist import load_decklist
from swu.engine.actions import create_game, legal_actions, apply
from swu.engine.invariants import CheckContext, check

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_DB = str(Path(__file__).resolve().parent.parent / "data" / "swu.db")

# The decklists are built at IMPORT time (see below), so a missing card DB has to
# be handled here rather than in a fixture: CardRepository raises FileNotFoundError
# in its constructor, which at module scope is a pytest *collection error* — a
# fresh clone has no data/ (it is rebuilt by the pipeline, see README), and a red
# traceback there would be the first thing a new contributor sees. Skip the module
# instead, matching how the shared ``repo`` fixture in conftest.py behaves.
if not Path(_DB).exists():
    pytest.skip(
        "swu.db not found — build it with scripts/build_db.py (see README)",
        allow_module_level=True,
    )

# Build the two starter decklists once at import; deep-copied per game so
# create_game never sees a mutated input.  CardDefs are frozen and return self
# on deepcopy, so the clone is cheap (just the list wrappers).
_REPO = CardRepository(_DB)
_DECK_A = load_decklist(_FIXTURES / "starter_vader.json", _REPO)
_DECK_B = load_decklist(_FIXTURES / "starter_luke.json", _REPO)

# Medium tier: ~30-45s, so it is excluded from the default (fast) run alongside
# the soak tests. Run it with `pytest -m slow`.
pytestmark = pytest.mark.slow

_MAX_STEPS = 600  # generous per-game cap; empty-deck damage guarantees a finish


class SWUEngineMachine(RuleBasedStateMachine):
    """Drive a full game one legal action at a time, checking invariants."""

    @initialize(seed=st.integers(min_value=0, max_value=100_000))
    def start_game(self, seed):
        self.gs = create_game(
            "P0", copy.deepcopy(_DECK_A), "P1", copy.deepcopy(_DECK_B), seed=seed
        )
        self.ctx = CheckContext.from_state(self.gs)
        self.steps = 0

    @rule(pick=st.integers(min_value=0, max_value=1_000_000))
    def play_legal_action(self, pick):
        gs = getattr(self, "gs", None)
        if gs is None or gs.is_terminal() or self.steps >= _MAX_STEPS:
            return
        acts = legal_actions(gs)
        if not acts:
            return
        # Deterministic pick from the *current* legal set; shrinks cleanly.
        self.gs = apply(gs, acts[pick % len(acts)])
        self.steps += 1

    @invariant()
    def invariants_hold(self):
        gs = getattr(self, "gs", None)
        if gs is not None:
            check(gs, self.ctx)


# Bounded so the medium tier stays fast; the campaign runner does the scale.
SWUEngineMachine.TestCase.settings = settings(
    max_examples=60,
    stateful_step_count=150,
    deadline=None,
)
TestSWUEngine = SWUEngineMachine.TestCase
