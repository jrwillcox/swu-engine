"""``actor_of(state, ci)`` — "you" for an ability of ``ci`` — importable at module
scope from anywhere, including card modules.

``swu.engine.state`` is still initialising when the card modules load (the engine
package imports them), so this leaf module imports it lazily; the real function and
its rules live in ``swu.engine.state.actor_of``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import CardInstance, GameState


def actor_of(state: "GameState", ci: "CardInstance") -> str:
    """The player an ability of ``ci`` resolves for (see ``swu.engine.state``)."""
    from swu.engine.state import actor_of as _actor_of
    return _actor_of(state, ci)
