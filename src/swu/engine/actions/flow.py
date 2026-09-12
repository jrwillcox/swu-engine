"""Turn flow primitives: whose turn it is, what phase we are in, and is it over.

Three functions, and they are here rather than in ``turn`` because of who calls
them: thirteen Action classes spread across every decision family end their
``apply`` by handing the turn to the opponent.  That makes ``_switch_active_player``
a low-level primitive, not part of game setup, and putting it in a leaf module is
what keeps those families from having to import a higher layer.

``_switch_active_player`` is also the only correct way to pass the turn, because
passing it is not just an index flip — initiative, pass tracking and
this-turn-scoped modifier expiry all hang off it.

``_assert_phase`` is the guard every phase-restricted action shares, and
``_check_game_over`` is evaluated after damage rather than on a schedule, so that a
game ends the moment a base falls rather than at the end of a turn.
"""
from __future__ import annotations


from swu.engine.events import (
    GameOver,
)
from swu.engine.state import (
    GameState, Phase,
)

from swu.engine.actions.base import (
    IllegalActionError,
)


# ── Attack pipeline helpers ───────────────────────────────────────────────────

def _check_game_over(s: GameState) -> None:
    if s.is_terminal():
        winner = s.players[0] if s.players[1].is_eliminated else s.players[1]
        loser = s.players[1] if winner is s.players[0] else s.players[0]
        s.event_log.append(GameOver(
            winner_player_id=winner.player_id,
            loser_player_id=loser.player_id,
        ))


# ── Internal helpers ──────────────────────────────────────────────────────────

def _assert_phase(state: GameState, expected: Phase) -> None:
    if state.phase != expected:
        raise IllegalActionError(f"Expected phase {expected}, got {state.phase}")


# ── Player-directed damage distribution push helpers ──────────────────────────

def _switch_active_player(s: GameState) -> None:
    other = 1 - s.active_player_index
    if other not in s.passed_players:
        s.active_player_index = other
