"""
STUB — Player protocol.

All player types (human, LLM, random) implement this interface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from swu.engine.actions import Action
from swu.engine.state import GameState


@runtime_checkable
class Player(Protocol):
    """A player that can choose an action given the current game state."""

    player_id: str

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        """
        Select one action from legal_actions given the current game state.
        Must return an element of legal_actions — not a new object.
        """
        ...

    def observe(self, state: GameState, action: Action, actor_id: str) -> None:
        """
        Called after every action (including the opponent's) so the player
        can update its internal model.  Optional — default implementation
        does nothing.
        """
        ...
