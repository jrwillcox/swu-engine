"""Human player — prints the current view and reads a numbered choice from stdin."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.state import GameState
    from swu.engine.views import CardView, PlayerView

# Keywords shown inline on unit cards (subset relevant to combat decisions)
_INLINE_KEYWORDS = frozenset({
    "Sentinel", "Overwhelm", "Raid", "Saboteur",
    "Grit", "Shielded", "Ambush", "Restore",
})


def _fmt_unit(c: "CardView") -> str:
    """Format a unit card for CLI display."""
    exh = "[X]" if c.exhausted else "[ ]"
    hp_left = c.effective_hp - c.damage
    stat = f"{c.effective_power}/{hp_left}hp"

    # Keyword tags: show inline keywords
    kw_tags = [kw for kw in c.keywords if kw in _INLINE_KEYWORDS]

    # Token tags: Shield and Experience from attached_upgrades
    shields = sum(1 for u in c.attached_upgrades if u.card_name == "Shield")
    exp = sum(1 for u in c.attached_upgrades if u.card_name == "Experience")
    token_tags = []
    if shields:
        token_tags.append(f"Shield×{shields}" if shields > 1 else "Shield")
    if exp:
        token_tags.append(f"Exp×{exp}" if exp > 1 else "Exp")

    suffix_parts = kw_tags + token_tags
    suffix = "  " + " ".join(f"[{t}]" for t in suffix_parts) if suffix_parts else ""
    return f"{c.card_name}{exh}({stat}){suffix}"


class HumanPlayer:
    def __init__(self, player_id: str) -> None:
        self.player_id = player_id

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        print(f"\n--- {self.player_id}'s turn  Phase:{view.phase}  Round:{view.round_number} ---")
        my = view.my
        opp = view.opponent

        base_ci = next((c for c in my.base_zone if c.card_type == "Base"), None)
        base_hp = base_ci.effective_hp if base_ci else "?"
        base_dmg = base_ci.damage if base_ci else 0
        opp_base = next((c for c in opp.base_zone if c.card_type == "Base"), None)
        opp_hp = opp_base.effective_hp if opp_base else "?"
        opp_dmg = opp_base.damage if opp_base else 0
        print(f"Your base: {base_hp - base_dmg}/{base_hp}  "
              f"Opp base: {opp_hp - opp_dmg}/{opp_hp}  "
              f"Resources: {my.available_resources}/{my.resource_count}  "
              f"Opp hand: {opp.hand_count}")

        if my.hand:
            print("Hand: " + ", ".join(c.card_name for c in my.hand))

        # Pending decisions (shown before actions for clarity)
        if view.pending_decisions:
            d = view.pending_decisions[-1]
            if d.is_mine:
                print(f"  *** Decision: {d.kind.upper()} — choose from actions below ***")

        for arena_name, units in (("Ground", my.ground_arena), ("Space", my.space_arena)):
            if units:
                parts = []
                for c in units:
                    parts.append(_fmt_unit(c))
                print(f"Your {arena_name}: " + ", ".join(parts))
        for arena_name, units in (("Ground", opp.ground_arena), ("Space", opp.space_arena)):
            if units:
                parts = []
                for c in units:
                    parts.append(_fmt_unit(c))
                print(f"Opp  {arena_name}: " + ", ".join(parts))

        print("Actions:")
        for i, act in enumerate(legal):
            print(f"  {i}: {act.describe()}")

        while True:
            try:
                raw = input("Choose: ").strip()
                idx = int(raw)
                if 0 <= idx < len(legal):
                    return legal[idx]
                print(f"Enter 0–{len(legal)-1}")
            except (ValueError, EOFError):
                return legal[0]

    def observe(self, state: "GameState", action: "Action", actor_id: str) -> None:
        pass
