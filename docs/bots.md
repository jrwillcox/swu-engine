# Bots

Every bot implements one method, `choose_action(view, legal) -> Action`: a choice
from the redacted `PlayerView` and the enumerated legal actions. Bots need no rules
knowledge of their own.

## Difficulty levels

`make_opponent()` in `src/swu/players/difficulty.py` is the only place that maps a
difficulty to a bot.

| Level | Bot |
|---|---|
| Easy | `HeuristicBot` with `mistake_rate=0.35`. Never calls an API. |
| Normal | `LLMPlayer` (casual style), falling back to `HeuristicBot` |
| Hard | `LLMPlayer` (competitive style), falling back to `HeuristicBot(sharp_targeting=True)` |

## Heuristic bot

`src/swu/players/heuristic_bot.py` scores every legal action with named, weighted
rules (not search) and plays the best. Its design rationale is at the top of the
file.

- **It never raises.** Any failure falls back to a safe default, which makes it a
  dependable fallback for the LLM bot.
- **It reads an effect's intent from the card registry.** A heal or buff goes on a
  friendly unit and damage on an enemy. With only the wrong side available, it
  declines rather than helping the opponent.
- **Easy's mistakes are sane.** It drops its best move and picks among the remaining
  sensible ones; forced choices (such as targeting) always use the best option.
- **Weights are per instance**: `HeuristicBot(weights={...})`, with the names in
  `TUNABLE_WEIGHTS`. That lets two tunings play each other in one process.

## LLM bot

`src/swu/players/llm_player.py`:

- Forces a single `choose_action` tool call; one retry if the chosen id is illegal.
- Falls back to the heuristic on any error, timeout, truncation or second illegal
  choice. The fallback shows in the in-game log ("Opponent fell back …").
- Builds its prompt only from the player's redacted view, so hidden information
  can't leak. A test asserts this.
- Skips the API when only one action is legal.
- Model: `claude-haiku-4-5` by default. Override with `SWU_LLM_MODEL`; set the
  timeout with `SWU_LLM_TIMEOUT` (default 20 s). Calls are logged to `data/llm.log`.
- It is not deterministic, so soak tests use the heuristic.

Tests mock the client and run offline; an autouse fixture strips
`ANTHROPIC_API_KEY`. `pytest --live` runs the one opt-in test against the real API.

## Measuring a change

Judge bot changes by measurement, never by taste. Both harnesses compare against
`benchmarks/heuristic_baseline.py`, a frozen copy of the bot from before the
2026-08 overhaul.

- **`scripts/bot_arena.py --a <bot> --b <bot>`**: head-to-head strength with a 95%
  interval. Each deck pair is played with seats and decks swapped, so only bot skill
  remains. Two identical bots score about 50%.
- **`scripts/bot_blunders.py --bot <bot>`**: counts named misplays (`buff_enemy`,
  `harm_self`, `upgrade_enemy`, `suicide_attack`, `whiff_attack`,
  `fizzled_event`). Each counts only when a better move was legal.

Two traps when analysing a board:

- A card's side is its **controller** (whose row it is in), not `owner_id`.
- Use `compute_power`/`compute_hp`, not `ci.effective_power()`.

**Known latent issue:** `AttackWithLeader` is scored from the view's deployed power,
but the engine deals `leader_power`. Every current leader has `leader_power == 0`,
so the action is never offered. If one ever isn't, surface `leader_power` in the
base-zone `CardView`.

## Soak bots

Random, weighted, aggro and chaos bots (`src/swu/players/`) exist to stress the
engine in soak campaigns, not to play well. See [`testing.md`](testing.md).
