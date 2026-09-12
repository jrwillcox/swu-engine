"""The decision-kind dispatch table, and the correspondence that keeps it honest.

``_decision_legal_actions`` used to be a 601-line ``if top.kind == "…"`` chain over
75 kinds. It is now a lookup in ``actions.dispatch``, populated by
``register_decisions({...})`` blocks at module scope.

That swap is proved separately and mechanically by
``scripts/refactor_parity.py --decision-arms``, which compares every handler body
against the arm it replaced. What a *static* gate cannot check is that registration
actually happens at import time — a family module that stops being imported would
leave its kinds unclaimed, and the only symptom would be decisions quietly resolving
to the unknown-kind fallback instead of raising. So these tests exercise the real,
imported table.

The load-bearing one is
``test_every_decision_kind_the_engine_can_push_has_a_handler``. A chain made the
relationship between "kind pushed" and "kind handled" invisible: forget an arm and
the decision silently falls through to ``[AnswerTestDecision("unknown")]``, which
looks like a legal-actions bug a long way from its cause. A table makes both sides
enumerable, so the correspondence can simply be asserted.
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
KINDS_FILE = FIXTURES / "actions_decision_kinds.json"

# Registered, but never pushed from ``src/``: the engine's own test hook, which
# exists so unit tests can put a decision on the stack without a card that makes
# one. It is pushed from tests only, and the original chain carried the same note
# ("for unit-test infrastructure only").
TEST_ONLY_KINDS = {"test"}


@pytest.fixture(scope="module")
def table():
    from swu.engine.actions import dispatch
    return dispatch


def _pushed_kinds() -> set[str]:
    """Every literal ``kind`` any ``PendingDecision(...)`` in ``src/`` constructs.

    Parsed rather than imported so this stays a cheap, database-free check. The one
    non-literal construction in the tree is ``decisions.py``'s ``kind=d["kind"]``,
    which rebuilds a decision from a saved game and so cannot introduce a kind that
    was not pushed somewhere else first.
    """
    kinds: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "PendingDecision"):
                continue
            for kw in node.keywords:
                if kw.arg == "kind" and isinstance(kw.value, ast.Constant):
                    kinds.add(kw.value.value)
    return kinds


def test_every_decision_kind_the_engine_can_push_has_a_handler(table):
    """No pushed kind may fall to the unknown-kind fallback.

    This is the check the if-chain could not support, and it is the real reason to
    prefer a table: a missing handler is now a failing test rather than a decision
    that resolves to a single meaningless action.
    """
    unhandled = sorted(_pushed_kinds() - table.registered_kinds())
    assert not unhandled, (
        "these decision kinds are pushed by the engine but no module claims them, so "
        "they would resolve to [AnswerTestDecision('unknown')]:\n  "
        + "\n  ".join(unhandled)
        + "\nAdd each to a register_decisions({...}) block alongside its handler."
    )


def test_no_handler_is_registered_for_a_kind_nothing_pushes(table):
    """The reverse direction: a handler for a kind that can never arrive is dead code.

    Catches a kind left registered after its card mechanic was removed or renamed —
    which a chain would have kept executing harmlessly forever.
    """
    orphans = sorted(table.registered_kinds() - _pushed_kinds() - TEST_ONLY_KINDS)
    assert not orphans, (
        "these kinds have handlers but nothing in src/ ever pushes them:\n  "
        + "\n  ".join(orphans)
        + f"\nEither something stopped pushing them, or they belong in "
          f"TEST_ONLY_KINDS ({sorted(TEST_ONLY_KINDS)}) with a reason."
    )


def test_the_registered_kinds_match_the_golden_set(table):
    """Pin the set, so adding or losing a kind is a deliberate act.

    The golden file was generated from the 75 kinds the pre-split chain handled, so
    a diff here is either a new mechanic (update it, in the same commit) or a
    registration that silently stopped happening.
    """
    expected = set(json.loads(KINDS_FILE.read_text(encoding="utf-8"))["kinds"])
    actual = table.registered_kinds()
    assert actual == expected, (
        f"lost: {sorted(expected - actual)}\nnew: {sorted(actual - expected)}"
    )


def test_every_handler_takes_exactly_state_and_top(table):
    """One uniform signature, which the dispatcher relies on.

    Not an arbitrary convention: 28 of the 75 kinds were already dispatched as a bare
    ``return NAME(state, top)``, so the pre-existing handlers chose it. A handler
    with a third required parameter would raise TypeError only when that decision
    actually came up — potentially a rare card, in a player's game.
    """
    wrong = []
    for kind in sorted(table.registered_kinds()):
        handler = table.decision_handler(kind)
        params = list(inspect.signature(handler).parameters.values())
        required = [p for p in params
                    if p.default is inspect.Parameter.empty
                    and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(required) != 2:
            wrong.append(f"{kind}: {handler.__name__}"
                         f"{inspect.signature(handler)}")
    assert not wrong, "handlers must take (state, top):\n  " + "\n  ".join(wrong)


def test_registering_a_kind_twice_is_an_error(table):
    """A collision must fail loudly rather than let the last import win.

    The chain resolved a duplicated kind by running whichever arm came first. A plain
    dict would resolve it by import order, which is arbitrary and silent — so
    ``register_decisions`` rejects it. Without this, two family modules could
    disagree about who owns a kind and the winner would depend on import order.
    """
    def other_handler(state, top):  # pragma: no cover - never called
        return []

    existing = sorted(table.registered_kinds())[0]
    with pytest.raises(ValueError, match="already handled by"):
        table.register_decisions({existing: other_handler})

    # Re-registering the *same* function is a harmless no-op (a module imported
    # twice under different names), and must not raise.
    table.register_decisions({existing: table.decision_handler(existing)})


def test_an_unknown_kind_still_reaches_the_fallback():
    """The chain's final ``return [AnswerTestDecision("unknown")]`` is preserved.

    Nothing should ever push an unregistered kind — the first test here enforces
    that — but a saved game from a future version could carry one, and the behaviour
    on that path must not change from "one inert action" to KeyError.
    """
    from swu.engine.actions import dispatch
    assert dispatch.decision_handler("no_such_kind_exists") is None
