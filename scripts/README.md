# scripts/

Three different kinds of thing live here. This is the map.

## Data pipeline

Building `data/swu.db` from the publisher's API. Run in this order on a fresh
clone — see [`../docs/pipeline.md`](../docs/pipeline.md) for detail and timings.

| Script | Purpose |
|---|---|
| `discover.py` | Sample the API schema and sanity-check it before a long harvest |
| `fetch_metadata.py` | The harvest itself — 60–90 min, resumable |
| `build_db.py` | Parse the raw pages into SQLite (idempotent; needs the manifest) |
| `validate.py` | Summary table; non-zero exit on a critical failure |
| `fetch_images.py` | Optional card art (~3 h, ~700 MB) |
| `fix_image_collisions.py` | Repair number-keyed image filenames — `(set, number)` is not unique |
| `audit_images.py` | Report missing or mismatched art |

`python -m swu.pipeline run` drives the whole sequence.

## Quality and measurement

Used continuously during development; the coverage audit and the graduation gate
are what the project's correctness claims rest on.

| Script | Purpose |
|---|---|
| `audit_coverage.py` | **The coverage audit.** Independently classifies every card and writes `docs/coverage_report.md`. Also `--deck <path>` for one decklist. |
| `soak.py` | Campaign runner — thousands of bot games with the invariant oracle after every action; writes a replayable bundle on failure |
| `replay.py` | Re-run a failure bundle deterministically |
| `shrink.py` | Delta-debug a failure bundle to a minimal reproducer |
| `bot_arena.py` | Paired-seat round-robin bot benchmarking against the frozen baseline |
| `bot_blunders.py` | Named-misplay census for the heuristic bot |
| `bot_winrate.py` | Quick head-to-head win rates |
| `find_reprints.py` | Detect reprint groups; `--check` fails if a mirror gap is unaliased |
| `make_fixture_db.py` | Build `tests/fixtures/swu_fixture.db`, the committed card subset that lets the test suite run without the corpus. `--record` re-derives which cards it needs by instrumenting the suite |

## Encoding campaign

The workflow described in [`../docs/methodology.md`](../docs/methodology.md).
These exist to make a few thousand small changes safe, not to build the game.

| Script | Purpose |
|---|---|
| `plan_encoding.py` | Offline, deterministic planner — clusters unimplemented cards into dependency-ordered groups with acceptance criteria |
| `next_group.py` | Stateless walker over the remaining queue |
| `verify_encoding.py` | Per-group verification, and `--graduate`: the release gate (100% coverage + green suites + a clean deck soak) |
| `audit_keyword_params.py` | Cross-check keyword parameters against the database |
| `merge_ui_decks.py` | Merge the playable-deck registry |

## A note on `--graduate`

`verify_encoding.py --graduate` shells out to `pytest`. Any test that exercises it
must mock `_run` — otherwise, once a deck is fully playable, the gate recursively
invokes the test suite from inside a test and the run hangs. Diagnose suspected
hangs with `pytest -o faulthandler_timeout=60`.
