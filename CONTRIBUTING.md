# Contributing

This is a personal project, but it is laid out so someone else can find their way
around. If you are reading the code rather than changing it, start with
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,web]"
```

That is enough to run the tests: `tests/fixtures/swu_fixture.db` is committed, so
the engine, keyword, web and regression suites run on a fresh clone (about 1,600
tests, ~1.5 min). Build the real card database — see [`docs/pipeline.md`](docs/pipeline.md) —
to run the remaining 4,000 or so, which are the per-set card suites, the coverage audit
and the reprint sweep; those need the whole corpus and skip with a reason without
it.

If you add a test that loads a card the fixture doesn't carry, re-record it:

```bash
python scripts/make_fixture_db.py --record   # needs the real database
```

`tests/fixture_scope.py` decides which suites may use the fixture at all.

## The rules that matter

**1. Everything is an `Action`.** If you are adding a way for a player to change
the game, it goes through `legal_actions` / `apply`. There is no second path, and
adding one would break the bots, the web layer's anti-cheat, and replay.

**2. `apply()` deep-copies first.** Never mutate the input state.

**3. All randomness comes from `state.make_rng()`.** A bare `random.*` call
destroys determinism and makes soak failures unreproducible.

**4. Never string-match card text at the point of use.** Ask the keyword layer
(`engine/keywords.py`). Text matching is how a rules engine rots.

**5. Cards are data.** A new card is a declaration composed from the vocabulary in
`abilities/registry.py`. If it cannot be expressed there, **stop** — the fix is a
new primitive designed in its own session, with its own tests, not bespoke
per-card logic. See [`docs/methodology.md`](docs/methodology.md).

**6. Update conservation together.** Adding a zone means touching the `Zone` enum,
`PlayerState`, `all_instances()`, `all_instances_for_player()` and the JSON
helpers. The invariants assume all five agree.

## Tests

```bash
pytest                    # fast tier — run this before every commit
pytest -m slow            # soak + Hypothesis stateful machine (~6 min)
ruff check .              # lint
mypy                      # typecheck the typed core (see [tool.mypy])

cd web && npm run lint && npm run format:check
cd web && npm run typecheck && npm test
cd web && npx playwright test        # e2e; starts its own servers
```

CI runs all of these, but against the committed fixture rather than the full
corpus, so the per-set card suites and corpus-wide audits only run here.

A new card ability needs a focused test named for the card, asserting behaviour
through the public engine interfaces (`legal_actions` / `apply`) rather than by
poking at internals. An engine bug fix needs a regression test.

If you change engine behaviour, run the slow tier too — the invariant oracle
catches a class of breakage the unit tests do not.

## Reproducing a soak failure

```bash
python scripts/soak.py --games 1000 --jobs 4       # run a campaign
python scripts/replay.py failures/<bundle>.json    # re-run the failing game
python scripts/shrink.py failures/<bundle>.json    # minimise it
```

## Style

Run `ruff check .` and `mypy` — both configured in `pyproject.toml` and both
deliberately narrow: ruff enforces correctness rules rather than formatting
opinions, and mypy checks only `src/swu/abilities/` and `engine/state.py`, the
fully-typed core. In `web/`, Prettier owns formatting (`npm run format`) and
ESLint is likewise conservative; the react-compiler-era hook rules are warnings,
not errors, so `npm run lint` stays green while the list stays visible. Beyond
that, match the surrounding code. The codebase comments *why* rather than *what*, and cites the
specific card that motivated a piece of machinery; that convention is load-bearing
in a domain with several thousand special cases, so please keep it up.
