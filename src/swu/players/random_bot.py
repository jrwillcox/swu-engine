"""Random-action bot — chooses uniformly at random from legal_actions."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.state import GameState
    from swu.engine.views import PlayerView


class RandomBot:
    def __init__(self, player_id: str, seed: int | None = None) -> None:
        self.player_id = player_id
        self._rng = random.Random(seed)

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        return self._rng.choice(legal)

    def observe(self, state: "GameState", action: "Action", actor_id: str) -> None:
        pass
