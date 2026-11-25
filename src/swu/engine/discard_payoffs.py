"""Named payoffs for "Discard a card.  If you do, …" (``push_discard_of_choice``).

A payoff that depends on a discard CHOICE has to wait for the choice, and a
decision's context must stay plain data (states are deep-copied and serialised), so
the payoff travels as a NAME plus JSON-able args and is looked up here when the
discard resolves.  Card modules register theirs at import::

    @discard_payoff("bail_organa_spy")
    def _bail_payoff(state, source_id, discarded, args): ...

``discarded`` is the list of CardInstances actually discarded (now in a discard
pile), possibly empty — the payoff owns its own "if you do".

A leaf module with no engine imports, so card modules can import it at module
scope without touching the ``swu.engine.actions`` import cycle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from swu.engine.state import GameState

DiscardPayoff = Callable[["GameState", Optional[str], list, dict], None]
_DISCARD_PAYOFFS: dict[str, DiscardPayoff] = {}


def discard_payoff(name: str) -> Callable[[DiscardPayoff], DiscardPayoff]:
    """Register ``fn(state, source_id, discarded_cards, args)`` as payoff ``name``."""
    def deco(fn: DiscardPayoff) -> DiscardPayoff:
        if name in _DISCARD_PAYOFFS and _DISCARD_PAYOFFS[name] is not fn:
            raise ValueError(f"discard payoff {name!r} registered twice")
        _DISCARD_PAYOFFS[name] = fn
        return fn
    return deco


def get_discard_payoff(name: str) -> DiscardPayoff:
    try:
        return _DISCARD_PAYOFFS[name]
    except KeyError:
        raise KeyError(f"unregistered discard payoff {name!r}") from None
