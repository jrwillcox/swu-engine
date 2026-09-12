"""
Difficulty levels and the opponent **bot factory** — the single extension point
for swapping in different opponent intelligences.

This module is *the* seam Phase 6B depends on.  In 6A every level maps to the
heuristic bot.  In 6B, ``make_opponent`` is the only thing that changes: Normal
and Hard return ``LLMPlayer(fallback=<heuristic>, style=...)`` while Easy stays a
pure heuristic forever.  Nothing else in the backend or UI needs to know which
kind of bot it received — they all satisfy the same ``Player`` protocol
(``choose_action(view, legal) -> Action``).

Difficulty intent
-----------------
* **EASY**  — a deliberately weakened heuristic (``mistake_rate`` > 0).  This is
  the level a young child plays at: instant, free, beatable, never crashes.
  By design EASY **never** reaches an LLM path — 6B must keep it heuristic.
* **NORMAL** — 6A: the standard heuristic.  6B: an LLM playing casually, with the
  heuristic as fallback.
* **HARD** — 6A: the standard heuristic with slightly sharper targeting.  6B: an
  LLM playing to win, heuristic fallback.

Determinism note
----------------
The heuristic is seed-deterministic: a given ``(seed, difficulty, decks)`` replays
identically.  6B's LLM will NOT be deterministic — that is expected and the LLM
path's tests must not assume determinism.  Easy/Normal/Hard remain deterministic
in 6A because all three are heuristics here.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING, Optional

from swu.players.heuristic_bot import HeuristicBot

if TYPE_CHECKING:
    from swu.players.base import Player


class Difficulty(str, Enum):
    """Selectable opponent difficulty.  ``str`` mixin so it serialises as its
    value (``"normal"``) over JSON and compares equal to that string."""

    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"

    @classmethod
    def coerce(cls, value: "Difficulty | str | None") -> "Difficulty":
        """Best-effort parse from a request string; defaults to NORMAL.

        Unknown/empty values fall back to NORMAL rather than raising, so a stale
        or malformed client value can never break game creation.
        """
        if value is None:
            return cls.NORMAL
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.NORMAL


# Per-difficulty heuristic tuning.  EASY plays a deliberately worse — but still
# coherent — main-phase line this fraction of the time (see
# ``HeuristicBot._random_mistake``); NORMAL plays its preferred line; HARD plays
# its preferred line and targets slightly sharper.
#
# Raised 0.25 → 0.35 when Easy's blunder branch stopped picking uniformly at
# random.  The old branch could throw a unit into a defender that killed it for
# nothing (~0.6 suicidal attacks per game, measured with
# ``scripts/bot_blunders.py``); removing that made Easy noticeably stronger, and
# 0.35 restores the same beatability it had before — measured at 51.6% over 800
# paired games against the previous Easy — while the moves it does make no longer
# look broken.  That is the whole point of the change: same difficulty, sane play.
_EASY_MISTAKE_RATE = 0.35


def make_opponent(
    difficulty: "Difficulty | str | None",
    *,
    player_id: str,
    seed: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> "Player":
    """Build the opponent ``Player`` for a difficulty level.

    Parameters
    ----------
    difficulty
        ``Difficulty`` (or a string that coerces to one; unknown → NORMAL).
    player_id
        The seat id the bot will control (e.g. ``"bot"``).
    seed
        Optional seed for the bot's RNG; threads determinism through the
        heuristic.  Ignored when ``rng`` is supplied.
    rng
        An explicit ``random.Random`` to use instead of constructing one from
        ``seed`` (handy in tests).

    Returns
    -------
    A ``Player``-protocol instance.

    6B EDIT POINT
    -------------
    To add the LLM opponent, change ONLY the NORMAL and HARD branches below to::

        from swu.players.llm_player import LLMPlayer
        return LLMPlayer(player_id, fallback=HeuristicBot(player_id, rng=rng),
                         style="casual" | "competitive")

    Leave EASY as a pure heuristic.  Do not touch the call sites — they only need
    a ``Player``.
    """
    diff = Difficulty.coerce(difficulty)
    bot_rng = rng if rng is not None else random.Random(seed)

    if diff is Difficulty.EASY:
        # EASY is a pure heuristic forever — it must NEVER reach an LLM path.
        return HeuristicBot(
            player_id,
            rng=bot_rng,
            mistake_rate=_EASY_MISTAKE_RATE,
            sharp_targeting=False,
        )

    # NORMAL and HARD (Phase 6B): an LLM plays the strategic choice, backed by a
    # bulletproof heuristic fallback for any failed/illegal/timed-out decision.
    # The model defaults to the smallest fast tier (claude-haiku-4-5) and is
    # overridable via the LLMPlayer ``model`` arg or the SWU_LLM_MODEL env var,
    # so Hard can be pointed at a stronger model later without code changes.
    from swu.players.llm_player import LLMPlayer, Style

    if diff is Difficulty.HARD:
        return LLMPlayer(
            player_id,
            fallback=HeuristicBot(player_id, rng=bot_rng, sharp_targeting=True),
            style=Style.COMPETITIVE,
        )
    # NORMAL (default)
    return LLMPlayer(
        player_id,
        fallback=HeuristicBot(player_id, rng=bot_rng),
        style=Style.CASUAL,
    )
