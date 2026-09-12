"""
ChaosBot — prefers the *rarest* action kinds it has seen this game.

Explicitly hunts unexercised code paths by up-weighting action types that
have been chosen least often so far.  The inverse-frequency weighting means
that as soon as a kind fires once it gets less priority, nudging the bot to
explore other branches.

Special high-priority kinds that are often skipped by random bots:
  ClaimInitiative, UseAbility, AcceptTrigger, DeployLeader
are given a base bonus so they get meaningful representation even when rare.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.views import PlayerView

# Base frequency bonus for kinds that are structurally rare but important.
_BONUS: dict[str, int] = {
    "ClaimInitiative": 3,
    "UseAbility": 3,
    "AcceptTrigger": 3,
    "DeployLeader": 2,
    "DeclineTrigger": 1,
}


class ChaosBot:
    def __init__(self, player_id: str, seed: int | None = None) -> None:
        self.player_id = player_id
        self._rng = random.Random(seed)
        # kind_name -> times this bot has chosen this kind
        self._kind_counts: defaultdict[str, int] = defaultdict(int)

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        # Weight = 1 / (chosen_count + 1), boosted by per-kind bonuses
        def weight(a: "Action") -> float:
            kind = type(a).__name__
            bonus = _BONUS.get(kind, 0)
            return (1.0 + bonus) / (self._kind_counts[kind] + 1)

        weights = [weight(a) for a in legal]
        chosen = self._rng.choices(legal, weights=weights, k=1)[0]
        self._kind_counts[type(chosen).__name__] += 1
        return chosen

    def observe(self, state: object, action: object, actor_id: str) -> None:
        pass
