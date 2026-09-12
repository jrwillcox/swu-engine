"""
Pending decision system.

When an action resolution needs additional player input (Ambush, Exploit,
etc.), a PendingDecision is pushed onto GameState.pending_decisions.

While the stack is non-empty:
  * legal_actions() returns only the top decision's options for the
    deciding player.  Normal turn alternation is suspended.
  * active_player_index is updated to point at the deciding player so
    the game loop and view system remain consistent.
  * The random bot works without modification — it already picks from
    legal_actions(), which now returns decision options.

When the last decision is popped, active_player_index is restored to
after_resolve_player_index and normal play resumes.

Serialisation: kind is a plain string; context is a dict of primitives
(str/int/list/bool) so the whole thing round-trips through JSON.

Phase 3 will reuse this for every "choose a target / choose an order /
may do X" in card text.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PendingDecision:
    """A single pending choice waiting for a player to resolve.

    Fields
    ------
    deciding_player_id
        The player who must make the choice.
    kind
        String tag identifying decision logic (e.g. ``"ambush"``,
        ``"exploit"``).
    context
        Serialisable payload: card ids, counts, etc.  Interpretation is
        specific to ``kind``.
    after_resolve_player_index
        Index of the player who becomes active once this decision (and any
        decisions stacked on top of it) resolves.  Usually the opponent.
    """
    deciding_player_id: str
    kind: str
    context: dict
    after_resolve_player_index: int

    def to_dict(self) -> dict:
        return {
            "deciding_player_id": self.deciding_player_id,
            "kind": self.kind,
            "context": self.context,
            "after_resolve_player_index": self.after_resolve_player_index,
        }

    @staticmethod
    def from_dict(d: dict) -> "PendingDecision":
        return PendingDecision(
            deciding_player_id=d["deciding_player_id"],
            kind=d["kind"],
            context=d["context"],
            after_resolve_player_index=d["after_resolve_player_index"],
        )
