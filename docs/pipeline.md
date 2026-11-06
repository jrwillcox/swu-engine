# Building the card database

The repository ships **no card database**, only a small test fixture. `data/` is
gitignored: the card corpus and artwork are the publisher's intellectual
property, and redistributing them is not something a fan project should do.
Instead, the pipeline below rebuilds everything locally from the official API.

Budget roughly **1.5 hours** for a playable engine, plus an optional ~3 hours for
card art.

> **You don't need any of this to run the tests.** A few hundred card definitions
> ship as a test fixture (`tests/fixtures/swu_fixture.db`, built by
> `scripts/make_fixture_db.py`), so `pytest` on a fresh clone runs the engine,
> keyword, web and regression tiers for real — about 1,600 tests in ~1.5 min. Build the
> database when you want to *play*, or to run the per-set card suites and the
> corpus-wide audits.

> **Keep the harvester polite.** The scripts set a descriptive `User-Agent`, wait
> 1.5 s between requests and back off on HTTP 429. A public repository multiplies
> whatever these scripts do by everyone who runs them, so treat those defaults as
> an obligation rather than a preference — and check the site's terms before
> running a full harvest.

## The stages

Run from the repository root with the virtualenv active.

### 1. Discovery — confirm the schema before committing to a long run

```bash
python scripts/discover.py
```

Fetches two cards and prints the attribute keys for each card type, writing
`data/raw/discovery_sample.json`. Read the output. If the upstream field names
have moved, reconcile them with the parser in `scripts/build_db.py` **before**
starting the harvest — otherwise you spend 90 minutes collecting pages that will
not parse.

### 2. Harvest — 60–90 minutes, resumable

```bash
python scripts/fetch_metadata.py              # first run
python scripts/fetch_metadata.py              # re-run: resumes from the last complete page
python scripts/fetch_metadata.py --refresh    # start over (use when a new set releases)
```

Writes `data/raw/pages/page_NNNN.json` and, on completion, `data/raw/manifest.json`.
The manifest is the proof that the harvest finished; the next stage refuses to run
without it.

An interrupted run is safe — re-running picks up at the last complete page.

### 3. Build — parse pages into SQLite

```bash
python scripts/build_db.py
```

Parses every raw page into `data/swu.db`. Idempotent: it drops and rebuilds, so
re-running is always safe.

### 4. Validate

```bash
python scripts/validate.py
```

Prints a summary table and exits non-zero if a critical check fails. At this point
the engine, the bots and the test suite are fully functional.

### 5. Images — optional, ~3 hours, ~700 MB

```bash
python scripts/fetch_images.py            # resumable; skips files already present
python scripts/fix_image_collisions.py    # (set, number) is not unique — see below
python scripts/audit_images.py            # report any gaps
```

Images affect **only** how the web UI looks. The backend returns 404 for a missing
image and the front end falls back to a text rendering, so everything works
without them.

Files land in `data/images/{SET_CODE}/{id}_{side}{ext}`, keyed by the database
`id` rather than the card number — because `(set_code, card_number)` is **not**
unique: every Leader collides with a same-numbered Token. An earlier
number-keyed layout caused leaders to render as their same-numbered token, which
is what `fix_image_collisions.py` exists to repair.

## All at once

```bash
python -m swu.pipeline run
python -m swu.pipeline run --skip-fetch --skip-images    # rebuild the DB only
```

## Where the data comes from

The official Strapi v4 API:

```
https://admin.starwarsunlimited.com/api/card-list
```

`filters[variantOf][id][$null]=true` restricts results to standard printings —
no hyperspace, foil or showcase variants. Variants are harvested separately for
the card explorer.

## Refreshing after a new set

See [`new_releases.md`](dev/new_releases.md) for the full runbook — detecting new
cards with a count probe, re-harvesting, re-auditing coverage, sweeping reprints,
and planning the encoding work for the new set.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `build_db.py` refuses to run | No `data/raw/manifest.json` — the harvest did not finish. Re-run `fetch_metadata.py`. |
| Tests all skip | No `data/swu.db`. The suite skips DB-backed tests by design rather than failing. |
| `Cannot locate swu.db` | Set `SWU_DB` to the database path, or run from the repository root. |
| Cards render as the wrong art | Run `fix_image_collisions.py`, then `audit_images.py`. |
