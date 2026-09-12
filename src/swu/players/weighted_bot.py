"""
WeightedBot — biased toward playing cards, attacking, deploying leaders,
and using abilities.  Produces denser, more realistic board states than
a pure random bot.

Action-kind weights (higher = more likely to be chosen):
  PlayCard          8
  AttackWithUnit    6
  DeployLeader      5
  AttackWithLeader  4
  UseAbility        4
  AcceptTrigger     4
  ClaimInitiative   2
  ExploitCommit     5
  ExploitSacrifice  4
  KeepHand          3   (prefer keeping over mulliganing in setup)
  ResourceCard      3
  everything else   1
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.views import PlayerView

_WEIGHTS: dict[str, int] = {
    "PlayCard": 8,
    "AttackWithUnit": 6,
    "DeployLeader": 5,
    "AttackWithLeader": 4,
    "UseAbility": 4,
    "AcceptTrigger": 4,
    "ExploitCommit": 5,
    "ExploitSacrifice": 4,
    "KeepHand": 3,
    "ResourceCard": 3,
    "ClaimInitiative": 2,
}


class WeightedBot:
    def __init__(self, player_id: str, seed: int | None = None) -> None:
        self.player_id = player_id
        self._rng = random.Random(seed)

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        weights = [_WEIGHTS.get(type(a).__name__, 1) for a in legal]
        return self._rng.choices(legal, weights=weights, k=1)[0]

    def observe(self, state: object, action: object, actor_id: str) -> None:
        pass
