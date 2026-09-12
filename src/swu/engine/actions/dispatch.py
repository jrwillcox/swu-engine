"""The decision-kind dispatch table: which handler enumerates a decision's actions.

When a decision is on the stack, the legal actions are whatever that *kind* of
decision allows. Until now that mapping was a 601-line ``if top.kind == "…"`` chain
over 75 kinds inside ``_decision_legal_actions``. The chain worked, but it meant one
function had to name a handler from every mechanic in the game, so the module holding
it transitively depended on all of them — which is a large part of why
``actions.py`` could not be split into per-mechanic modules at all. Measured: the
dispatcher accounted for **148** of the 289 cross-family references.

This inverts that edge. Each module declares the kinds it owns:

    register_decisions({
        "ambush": _ambush_actions,
        "exploit": _exploit_actions,
    })

and the dispatcher only ever consults this table. A family module now depends on
``dispatch`` (which depends on nothing) instead of the dispatcher depending on every
family, so families can move out one at a time.

**The handler signature is ``(state, top) -> list[Action]``**, which is not a choice
so much as an observation: 27 of the 74 arms were already a bare
``return _x_actions(state, top)`` and *all 27* used exactly those two parameters. The
10 arms that also wanted the deciding player recompute it with
``state.player_by_id(top.deciding_player_id)`` as their first line.

Replacing the chain with a table is **exactly** equivalent here rather than
approximately, and that rests on two measured facts, both of which
``scripts/refactor_parity.py --decision-arms`` re-checks on every run:

* **No arm fell through.** All 74 returned on every path, so no kind depended on
  reaching a *later* arm. Had even one fallen through, first-match-wins ordering
  would have been load-bearing and a dict lookup would have silently skipped it.
* **No kind was handled twice.** 73 arms tested one kind each and one tested two
  (``combat_damage_prevention``/``ability_damage_prevention``, which share a
  handler), with no duplicates — so "first match" and "the match" were the same
  thing.

Because ordering was *not* load-bearing, registration order is irrelevant, and
``register_decisions`` refuses a duplicate rather than letting the last import win.
That is stricter than the chain was: silently shadowing a kind is the one way this
table could diverge from the code it replaces, so it is an error, not a precedence
rule.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Mapping

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, types only
    from swu.engine.actions.base import Action
    from swu.engine.decisions import PendingDecision
    from swu.engine.state import GameState

# A handler enumerates the legal actions for one kind of pending decision. It is
# given the whole state and the decision on top of the stack, and returns the
# actions the deciding player may take. It must not mutate the state.
DecisionHandler = Callable[["GameState", "PendingDecision"], "list[Action]"]

_HANDLERS: dict[str, DecisionHandler] = {}


def register_decisions(handlers: Mapping[str, DecisionHandler]) -> None:
    """Claim a set of decision kinds for this module's handlers.

    Called at module scope, so importing the package is what populates the table —
    the same arrangement as ``abilities/registry.py``'s ``@card_ability``.

    Raises ``ValueError`` on a kind that is already claimed. The chain this replaces
    resolved a duplicate by running whichever arm came first; a dict would resolve it
    by keeping whichever module imported last, which is both arbitrary and invisible.
    Neither is a behaviour worth having, so a collision is a hard error.
    """
    for kind, handler in handlers.items():
        existing = _HANDLERS.get(kind)
        if existing is not None and existing is not handler:
            raise ValueError(
                f"decision kind {kind!r} is already handled by "
                f"{existing.__module__}.{existing.__qualname__}; "
                f"{handler.__module__}.{handler.__qualname__} cannot also claim it. "
                "Two modules disagree about who owns this kind — merge the handlers "
                "or give one of them a distinct kind."
            )
        _HANDLERS[kind] = handler


def decision_handler(kind: str) -> DecisionHandler | None:
    """The handler for ``kind``, or ``None`` if no module claims it."""
    return _HANDLERS.get(kind)


def registered_kinds() -> frozenset[str]:
    """Every decision kind with a handler. Used by the tests that pin the surface."""
    return frozenset(_HANDLERS)
