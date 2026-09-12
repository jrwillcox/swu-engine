# SWU — a Star Wars: Unlimited rules engine

A complete, tested implementation of the *Star Wars: Unlimited* trading card game:
a deterministic rules engine, a declarative card-encoding framework covering the
full card pool, three tiers of computer opponent, a FastAPI backend and a React
front end you can actually play in a browser.

> **Unofficial fan project.** Not affiliated with, endorsed by, or sponsored by
> Lucasfilm, Disney, Fantasy Flight Games or Asmodee. All card text, artwork,
> rules and trademarks belong to their respective owners. **No card data or
> artwork is distributed in this repository** — the pipeline in `scripts/` builds
> the card database locally from the publisher's public API. The code is MIT
> licensed; see [LICENSE](LICENSE).

![The game board — two arenas, leaders, bases, resources and hand](docs/images/game-board.png)

## What's here

| | |
|---|---|
| **Card coverage** | **2,636 / 2,636 playable (100%)** — 2,176 registered in the ability framework, the rest fully handled by the keyword and vanilla layers. **0 escape hatches**, 0 keyword-deferred. Measured by `scripts/audit_coverage.py`, written to [`docs/coverage_report.md`](docs/coverage_report.md). |
| **Tests** | 4,427 test functions across 74 files → **5,638 passing, 6 skipped** with parametrisation, plus 138 front-end tests and 2 Playwright e2e specs. |
| **Engine** | ~101k lines of Python across `src/swu/`; ~8k lines of TypeScript in `web/src/`. |
| **Opponents** | A transparent weighted-heuristic bot, an LLM-backed bot (Claude) that degrades visibly to the heuristic, and random/aggro/chaos bots for soak testing. |

## Quick start

Requires **Python ≥ 3.11** and **Node ≥ 20.19** (Vite 7). Windows PowerShell and
POSIX commands are both given; from a fresh clone:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,web]"
```

### 1. Build the card database (~1.5 hours, once)

The repository ships no card data. Rebuild it from the official API — the steps
are resumable, so an interrupted run picks up where it left off:

```bash
python scripts/discover.py        # sample the API schema and sanity-check it
python scripts/fetch_metadata.py  # ~60-90 min, resumable, writes data/raw/pages/
python scripts/build_db.py        # parse pages -> data/swu.db (idempotent)
python scripts/validate.py        # summary table; non-zero exit on a critical fail
```

That is everything the engine, the bots and the test suite need.

**Card art is optional.** It only affects how the web UI looks — the app serves a
text fallback when an image is missing.

```bash
python scripts/fetch_images.py    # ~3 hours, ~700 MB; then fix_image_collisions.py
```

> **Please keep the harvester polite.** It sets a descriptive `User-Agent`, waits
> 1.5 s between requests and backs off on HTTP 429. A public repo multiplies
> whatever these scripts do by everyone who runs them, so treat those defaults as
> an obligation rather than a preference, and check the site's terms before
> running a full harvest.

### 2. Play

```bash
python -m swu.web                 # backend on 127.0.0.1:8000
cd web && npm install && npm run dev   # front end on :5173, proxies /api
```

Open <http://localhost:5173>, register an account and pick a deck. By default the
only username permitted to register is `player`; set `SWU_ALLOWED_USERS` to change
that (see [`.env.example`](.env.example)).

**No Anthropic API key is required.** *Easy* is a pure heuristic and never calls
an API. *Normal* and *Hard* use a small Claude model but fall back to the
heuristic — visibly, in the in-game log — on a missing key, a network hiccup or a
bad response. Set `ANTHROPIC_API_KEY` in the environment to enable them.

There is also a terminal driver:

```bash
python -m swu.cli --p0 random --p1 random --seed 7
```

## Architecture

```
        legal_actions(state) ──► every legal move, fully enumerated
                │
  Action ──► apply(state, action) ──► (new state, events[])
                │                              │
                │                              └─► the event log doubles
                │                                  as the UI's animation script
                ▼
      invariants.check(state)   ◄── 17 invariants, run after every move in soak
```

The engine is a pure `GameState → GameState` function: deep-copy then mutate,
seeded and deterministic, JSON round-trippable. Everything else is built on that
one contract.

- **`src/swu/engine/`** — state, actions, combat, keywords, the decision stack,
  the invariant oracle, and `views.py`, which redacts a state down to what one
  player may see.
- **`src/swu/abilities/`** — the card DSL. `registry.py` defines ability specs
  (triggers, effects, targets, conditions, durations); `resolver.py` interprets
  them against a state.
- **`src/swu/cards/<set>/abilities.py`** — the encodings themselves. **These are
  data, not logic** — large, flat files of declarations, which is why they are big.
- **`src/swu/players/`** — the `Player` protocol and every bot.
- **`src/swu/web/`** — FastAPI. `session.py` hands the client opaque action ids, so
  the front end cannot forge an illegal move.
- **`web/src/`** — React. **The front end knows no game rules**: it renders the
  redacted view, shows the legal actions the backend assigned, and animates the
  event stream.

Two files look alarming and are deliberate: `engine/actions.py` is one large
module (~25k lines) organised into ~96 labelled sections, each naming the card
that motivated it; and `benchmarks/heuristic_baseline.py` is a frozen copy of the
heuristic bot, kept so `scripts/bot_arena.py` can A/B against a fixed reference.

Deeper notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
[`docs/ability_framework.md`](docs/ability_framework.md) ·
[`docs/README.md`](docs/README.md) (index).

## What's interesting here

- **Cards as data.** 2,176 cards are declarations composed from a fixed
  vocabulary of effect primitives, with **zero** escape hatches — no card falls
  back to bespoke imperative code.
- **An invariant oracle** (`src/swu/engine/invariants.py`): card conservation by
  instance identity, zone/tag consistency, decision-stack wellformedness,
  semantic modifier expiry, and **hidden-information leak detection** — it
  serialises `view_for(player)` and string-scans it to prove the opponent's hand
  never leaks. Run after every action in soak mode.
- **Property-based testing that shrinks.** `tests/test_hypothesis_engine.py`
  drives whole games one legal action at a time and runs that same oracle after
  every move, shrinking any failure to a minimal reproducer. Where the campaign
  runner waits for a bad state, this searches for one.
- **Variance-reduced bot benchmarking.** `scripts/bot_arena.py` plays every
  (deck-pair, seed) twice with the bots swapped, so seat and deck advantage
  cancel exactly and a 2–3 point win-rate change is signal rather than noise.
- **A resumable data pipeline** that samples the API schema before committing to
  a 90-minute harvest, and gates the database build on a manifest proving the
  harvest completed.

## Tests

```bash
pytest                       # fast tier (~8 min with the full card database)
pytest -m slow               # soak + Hypothesis stateful machine (~6 min)
ruff check . && mypy         # lint, then typecheck the typed core
cd web && npm run lint && npm run typecheck && npm test     # front end
cd web && npx playwright test               # e2e (starts its own servers)
```

**A fresh clone runs the tests for real, without building the card database.**
`tests/fixtures/swu_fixture.db` is committed — a few hundred card definitions
(text and stats only, no artwork), built by
[`scripts/make_fixture_db.py`](scripts/make_fixture_db.py) from exactly the cards
the engine, keyword, web and regression suites load. On a clone with no `data/`:

| | tests run | wall clock |
|---|---|---|
| No database at all | 1,550 | ~50 s |
| Committed fixture (the default) | **2,260** | ~90 s |
| Full corpus, after the pipeline | **5,638** | ~7.5 min |

What the fixture can't cover skips with a reason rather than failing: the per-set
card suites (one test per printed card across 24 sets), the coverage audit, the
reprint sweep and the per-deck gates all need the real corpus.
[`tests/fixture_scope.py`](tests/fixture_scope.py) draws that line in one place,
and `scripts/make_fixture_db.py --record` re-derives the fixture's contents by
instrumenting the suite rather than trusting a hand-maintained list.

```bash
python scripts/soak.py --games 10000 --jobs 8   # overnight campaign
python scripts/replay.py failures/<bundle>.json # reproduce a failure
python scripts/shrink.py failures/<bundle>.json # minimise it
```

## How this was built

This project was built with heavy use of Claude Code, and the machinery for doing
that safely is part of the repository rather than hidden: a deterministic offline
planner that clusters unimplemented cards into dependency-ordered work groups
(`scripts/plan_encoding.py`), per-card acceptance criteria for each group
(`encoding/*/MANIFEST.md`), and an automated release gate
(`scripts/verify_encoding.py --graduate`) that refuses to ship a deck below 100%
coverage with green suites. See [`docs/methodology.md`](docs/methodology.md).

## Licence

Code: MIT ([LICENSE](LICENSE)). Card text, artwork and trademarks are not covered
by that licence and are not redistributed here.
