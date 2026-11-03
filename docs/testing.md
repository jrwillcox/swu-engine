# Testing

## Test tiers

| Tier | Command | Time |
|---|---|---|
| Fast (the default) | `python -m pytest` | ~10 min with the full database |
| Slow, also called "medium": soak tests and the Hypothesis state machine | `python -m pytest -m slow` | ~6 min |
| Everything | `python -m pytest -m ""` | |
| Front end (`web/`) | `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test` | ~1 min |
| End to end | `cd web && npx playwright test` | |
| Soak campaign | `python scripts/soak.py --games 10000 --jobs 8` | overnight |

CI runs ruff, mypy, the fast tier and the front-end checks on every pull request.

**Which database the tests use.** `data/swu.db` if you have built it (see
[`pipeline.md`](pipeline.md)), or another path set in `SWU_DB`. Otherwise the
committed `tests/fixtures/swu_fixture.db`, a small subset that runs about 2,300
tests; the rest skip with a reason. `tests/fixture_scope.py` defines which tests
need the full database.

## The invariant oracle

`src/swu/engine/invariants.py` checks the state after every action in soak runs:
card conservation, zone consistency, a well-formed decision stack, modifier expiry,
phase and pass bookkeeping, terminal quiescence, JSON round-trips, and that a
player's view never leaks hidden information.

```python
from swu.engine.invariants import CheckContext, check
ctx = CheckContext.from_state(initial_state)   # once per game
check(state, ctx)                               # after every apply()
```

## Soak campaigns

`scripts/soak.py` plays bot-vs-bot games in parallel and writes a report to
`soak_reports/soak_report.json` and `.md`, which are gitignored (change with
`--report`). Past campaigns are summarised in [soak_results.md](soak_results.md).

- Pick bots and decks with `--bots heuristic,easy,random,…` and
  `--decks starter,vanilla,keyword`.
- **Determinism check:** `--determinism-sample N` replays every Nth game from the
  same seed and requires an identical result.
- **The report's anomaly banner** flags lopsided seat win rates, unusual game
  lengths, abilities that fire but never hit a target, games near the action cap,
  non-determinism, and abilities that never fire. An empty banner means a clean run.
- Every failure is saved as a replayable bundle in `failures/`.

```bash
python scripts/replay.py failures/<bundle>.json --verbose   # reproduce
python scripts/shrink.py failures/<bundle>.json --timeout 120   # minimise
```

## Regressions

Each engine bug found by a soak or a player gets a permanent test in
`tests/regressions/`, one file per bug, named for the behaviour it protects.
