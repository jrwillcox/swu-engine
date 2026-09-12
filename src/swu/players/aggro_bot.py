"""
AggroBot — always attacks the opponent's base when possible.
Steers games toward base-race end-states (low-HP finishes).

Priority:
  1. AttackWithUnit(defender_id=None)  — direct base attacks
  2. AttackWithLeader                  — undeployed leader base attack
  3. Everything else (random)
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.views import PlayerView


class AggroBot:
    def __init__(self, player_id: str, seed: int | None = None) -> None:
        self.player_id = player_id
        self._rng = random.Random(seed)

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        # Tier 1: unit attacks targeting the base
        base_attacks = [
            a for a in legal
            if type(a).__name__ == "AttackWithUnit"
            and getattr(a, "defender_id", "sentinel") is None
        ]
        if base_attacks:
            return self._rng.choice(base_attacks)

        # Tier 2: undeployed leader base attack
        leader_attacks = [a for a in legal if type(a).__name__ == "AttackWithLeader"]
        if leader_attacks:
            return self._rng.choice(leader_attacks)

        return self._rng.choice(legal)

    def observe(self, state: object, action: object, actor_id: str) -> None:
        pass
