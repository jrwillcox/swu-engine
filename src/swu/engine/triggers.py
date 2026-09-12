"""
Trigger bus — empty for Phase 1.

Phase 2/3 keywords and abilities register listeners here. Currently zero
listeners are registered; fire() is a no-op but is called at the right
hook points so adding keywords later requires no changes to the action loop.

Hook points called from actions.py:
  on_play          — after a card enters play (unit, upgrade, event)
  on_attack_declared — after attacker is declared, before damage
  on_defeated      — after a unit/leader is moved to discard
  on_round_start   — first thing in each new round
  on_regroup       — during the regroup phase, after draw
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from swu.engine.state import GameState
    from swu.engine.events import GameEvent


TriggerCallback = Callable[["GameState", "GameEvent"], "GameState"]


class TriggerBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[TriggerCallback]] = {}

    def register(self, event_type: str, callback: TriggerCallback) -> None:
        self._listeners.setdefault(event_type, []).append(callback)

    def fire(self, state: "GameState", event: "GameEvent") -> "GameState":
        for cb in self._listeners.get(type(event).__name__, []):
            state = cb(state, event)
        return state


_bus = TriggerBus()


def get_bus() -> TriggerBus:
    return _bus
