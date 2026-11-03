# New Releases — detecting and implementing new cards, sets, keywords and decks

**Status:** the card database is complete as of the last harvest recorded in
`data/raw/manifest.json` (see its `timestamp` / `total_cards`). Every card in it is
playable, `PHASE3_KEYWORDS` is empty, and the encoding queue is empty
(`scripts/next_group.py` prints `QUEUE EMPTY`).

This document is the runbook for the *next* time that stops being true: a new
expansion, a promo drop, an errata pass, a new keyword, or a new preconstructed
deck. It has three parts:

1. **[Detection](#part-1--detection)** — how to find out that something new exists.
2. **[Implementation](#part-2--implementation)** — how to get it into the engine.
3. **[Publishing hygiene](#part-3--publishing-hygiene)** — what must be true before
   this repository is pushed to a public host.

All paths are relative to the `swu-game/` project directory. `python` below means
the project virtualenv's interpreter (`.venv/Scripts/python.exe` on Windows,
`.venv/bin/python` elsewhere) — the global interpreter will be missing dependencies.

---

## Part 1 — Detection

There are five *distinct* kinds of "new", and they are found in different ways.
Only two of them are detected automatically today.

| Kind | Source of truth | Detected by |
|---|---|---|
| New cards (new set, or additions to an existing one) | the upstream card API | comparing the API's card total against `data/raw/manifest.json` (manual probe) |
| Errata / changed text on existing cards | the upstream card API | a full re-harvest + diff (nothing is automatic) |
| New keyword | the card DB | **automatic** — `scripts/audit_coverage.py` labels it `keyword-deferred` |
| New set code | the card DB | **automatic-ish** — a set code missing from `SET_ORDER` is silently skipped, so check explicitly (§1.3) |
| New preconstructed / starter deck | product announcements | **manual only** — decklists are not in the card API |

### 1.1 New cards — the card-count probe

The pipeline's harvest writes `data/raw/manifest.json` on completion, recording
`total_cards`, `page_count` and the exact `query_params` used. That file is the
high-water mark. The API reports its own total in `meta.pagination.total` on any
page, so a single request is enough to know whether anything has been added.

There is **no script for this yet** — it is one cheap request, and a good first
thing to add. The recipe (run from `swu-game/`):

```python
# scripts/check_new_cards.py  (suggested; ~30 lines)
#   1. read data/raw/manifest.json           -> known_total, query_params
#   2. GET page 1 with those same params      -> meta.pagination.total
#   3. print DIFF and exit non-zero if they disagree
```

Reuse `scripts/fetch_metadata.py`'s `_fetch_page_raw(page, query_params)` — it
already carries the correct headers, the retry/back-off policy and the 429
handling, so the probe stays as polite as the harvest. Do **not** hand-roll a
second `requests.get` with different headers.

Run the same probe against the variant params (`fetch_metadata.VARIANT_QUERY_PARAMS`
vs `data/raw/variant_manifest.json`) if you also track Hyperspace/Showcase art.

Two caveats:

- **A changed total is a strictly stronger signal than an unchanged one.** Errata
  that rewrites a card's text does not change the count. If a rules update is
  announced, re-harvest regardless of the probe.
- **The count can go *down*** (upstream depublishing a card). Treat any
  disagreement as "re-harvest and diff", not just "additions".

### 1.2 New keywords — already automatic

`scripts/audit_coverage.py` classifies every card, and any keyword outside
`ALL_KNOWN_KEYWORDS` (= `PHASE2_KEYWORDS | PHASE3_KEYWORDS`) makes its card
`keyword-deferred`. Since `PHASE3_KEYWORDS` is currently empty, **any
`keyword-deferred` row in a fresh audit is a brand-new keyword.** The report at
`docs/coverage_report.md` names it in the keyword tables.

So: after every rebuild, run `python scripts/audit_coverage.py` and read the
`Kw-Deferred` column. Non-zero ⇒ new keyword ⇒ §2.6.

### 1.3 New set codes

A new expansion arrives as a `set_code` the campaign machinery has never seen.
Two places must learn about it, and **neither errors if you forget** — they just
quietly skip the set:

- `SET_ORDER` in `scripts/next_group.py` — the campaign queue only walks codes
  listed there.
- `src/swu/cards/__init__.py` — the per-set ability module import.

After a rebuild, list what the DB actually holds and compare:

```bash
python -c "import sqlite3;print(sorted({r[0] for r in sqlite3.connect('data/swu.db').execute('SELECT DISTINCT set_code FROM cards')}))"
```

Anything in that list but not in `SET_ORDER` is invisible to `/encode-next`. This
is the single easiest thing to get wrong after a release — a set can look "done"
purely because nothing ever planned it.

### 1.4 New decks

Preconstructed decks, two-player starters and the like are **not** in the card
API — only their constituent cards are. Detection is human: a product
announcement, a decklist published by the vendor or a community site.

A deck is "new content" in a much weaker sense than a set: its cards are already
in the DB, and most or all of them are usually already implemented. What a new
deck actually needs is a fixture (§2.7) and a graduation run.

The engine also accepts arbitrary user decklists at runtime
(`src/swu/web/swudb_import.py`, the custom deck builder), so a new deck is only
worth *shipping* as a fixture when it should appear on the new-game screen.

### 1.5 Suggested cadence

- **Quarterly, or on any set-release announcement:** run the card-count probe (§1.1).
- **On any rules/errata announcement:** re-harvest and diff, probe or no probe.
- **Never on a schedule you have to remember by hand** if it can be a scheduled
  job — the probe is one request and safe to automate.

---

## Part 2 — Implementation

The order below matters: data first, then classification, then encoding. Each
stage has a cheap check that gates the next one.

### 2.1 Re-harvest the card data

**A new set requires `--refresh`, not a resume.** The harvest paginates over a
sorted query (`type.sortValue:asc, expansion.sortValue:desc, cardNumber:asc`), so
a new expansion inserts rows into the *middle* of the sequence and shifts every
page after it. Resuming would silently interleave old and new pages.

```bash
python scripts/fetch_metadata.py --refresh              # base cards (~1–1.5 h at the default delay)
python scripts/fetch_metadata.py --variants-only --refresh   # art variants, if tracked
```

Keep the default `--delay 1.5`. The script already backs off on 429 and honours
`Retry-After`; do not lower the delay to speed up a public API.

Raw pages land in `data/raw/pages/`, and `manifest.json` is rewritten on
completion — that file is the proof-of-complete-harvest that `build_db.py`
requires, so an interrupted run cannot poison the DB.

### 2.2 Rebuild the database and images

```bash
python scripts/build_db.py                 # full rebuild: DROPS and rebuilds the cards table
python scripts/fetch_images.py             # resumable; skips files already on disk
python scripts/fix_image_collisions.py     # MUST run after any full rebuild
python scripts/audit_images.py             # gate: exits non-zero on collisions / missing files
python scripts/validate.py                 # gate: overall DB sanity
```

Three things that bite here:

- **A full `build_db.py` drops the cards table, and with it every `image_*_path`.**
  The `--variants-only` mode exists precisely to avoid that when you only want to
  add art variants to an existing, fully-worked DB. Use it when that is all you
  are doing.
- **`(set_code, card_number)` is not unique.** Every Leader (numbered 1, 2, 3, …)
  collides with a low-numbered Token. `fetch_images.py` names files by number, so
  colliding cards point at the same physical file — the "Leader renders as a
  Shield token" bug. `fix_image_collisions.py` gives each colliding card an
  id-based filename and repoints the DB; `audit_images.py` is the repeatable proof
  the repair held. **The true unique key is the DB `id`.** Run both after every
  rebuild, and after any new set (a new set adds new Leaders ⇒ new collisions).
- Both image scripts are idempotent and resumable — interrupt freely.

### 2.3 Re-audit coverage

```bash
python scripts/audit_coverage.py           # regenerates docs/coverage_report.md
```

Read the summary table:

- **`Text-Bearing` > 0** ⇒ ordinary encoding gaps → §2.5.
- **`Kw-Deferred` > 0** ⇒ a new keyword → §2.6 **first** (it may unlock many
  cards for free, and encoding residual text before the keyword exists wastes work).
- **`Escape-Hatch` > 0** ⇒ stubs worth revisiting, not blockers.

Classification is a single canonical rule — `audit_coverage.has_functional_text` —
which the planner, verifier and deck-coverage test all delegate to. Do not add a
second notion of "has text" anywhere.

### 2.4 Sweep reprints before encoding anything

Many "new" promo/anthology cards are exact printed-face duplicates of cards
already implemented, and are made playable for free by aliasing:

```bash
python scripts/find_reprints.py            # writes docs/reprints_worklist.json
python scripts/find_reprints.py --check    # exits non-zero on an unaliased mirror gap
```

`mirror` groups (≥1 member registered, ≥1 not) are free wins — add the alias to
`REPRINT_ALIASES` in `src/swu/cards/reprints.py`. `needs_encoding` groups fall
through to the normal queue.

⚠ **A green `--check` is only as good as the identity function.** `face_key`
compares printed faces; it has twice been too strict (once over parenthesised
reminder text, once over letter case), which keyed identical twins into invisible
singleton groups that the worklist builder skips — so `--check` stayed green while
implemented cards sat unplayable beside identical twins. If a new set adds cards
that *look* like reprints but aren't detected, suspect `face_key` before suspecting
the data. Widening the identity is always safe; **measure which groups merge before
you widen it**, and confirm each merged group is genuinely one card name. A twin
whose DB text is *truncated* is an upstream defect, not a formatting difference —
register it importing the canonical's function rather than aliasing it.

### 2.5 Plan and encode a new set

**Step 1 — register the set.** Add the new code to `SET_ORDER` in
`scripts/next_group.py` (in release order, before the promo tail), create
`src/swu/cards/<setcode>/` with an `__init__.py` and `abilities.py`, and add its
import to `src/swu/cards/__init__.py`. That import must sit **above** the
`reprints.apply_reprint_aliases()` call at the bottom — aliasing runs last, after
every set module has registered.

**Step 2 — plan it.** Deterministic, offline, free, and re-runnable:

```bash
python scripts/plan_encoding.py --set NEW
```

This writes `encoding/new-set/{MANIFEST.md, manifest.json, group_NN_*.md}`,
clustering every gap into ordered groups of three kinds:

- `keyword` — blocked only by a deferred keyword (implement it once, engine-side,
  and every listed card unlocks),
- `ability` — text-bearing cards clustered by mechanical bucket, capped at 7,
- one escalation group **per** suspected new primitive, ordered last.

Group ids are stable across re-runs, and a re-run never clobbers a spec whose
cards are all playable.

**Step 3 — encode, batch by batch.** The queue walker holds no state; it
re-derives the whole campaign from the DB, the registry and the manifests on every
run, so it behaves identically after a restart:

```bash
python scripts/next_group.py --n 3         # the next batch
```

Then work the printed groups in order. The `/encode-next [N]` skill automates
exactly this loop (pull queue → read spec → implement declaratively → focused test
per card → run the printed `VERIFY:` command → one fast suite for the batch →
stop at a clean boundary).

Per-card mechanics:

- [`encoding_guide.md`](encoding_guide.md): the step-by-step recipe.
- [`engine_seams.md`](engine_seams.md): the reusable patterns and decision kinds.
  **If a card looks like an existing pattern, copy it; don't invent a new one.**
- For the reasoning behind a pattern, grep `docs/history/seams_log.md` and
  `docs/history/encoding_history.md` for a card id (e.g. `SOR_135`). Never read them
  whole.

**Step 4 — respect the escalation rule.** A small, self-contained new primitive may
land with a card, with synthetic-card tests; a new decision kind follows "Adding a
decision kind" in `engine_seams.md`. Anything touching **core resolution, the
trigger/decision machinery, or needing a replacement-effect system must stop and be
flagged for a dedicated framework session.** The planner flags suspected new
primitives as their own one-card groups, so this is visible before you start.

**Step 5 — cadence.** Focused `-k` test per group; **one** fast suite per batch
(not per group); medium tier plus a fresh `audit_coverage.py` only at a set
milestone. Never `--graduate` or soak a `*-set` slug — sets are not decks.

### 2.6 Implement a new keyword

A new keyword is engine work, not card work, and it comes first.

1. Implement it engine-side once, with synthetic-card tests (the keyword layer
   handles pure-keyword cards without any per-card registration).
2. Move the keyword name from `PHASE3_KEYWORDS` into `PHASE2_KEYWORDS` in
   `scripts/audit_coverage.py`. (Add it to `PHASE3_KEYWORDS` first if you want the
   audit to name it explicitly while the work is in flight; an unlisted keyword is
   already reported as `keyword-deferred` either way.)
3. Update the keyword list in `docs/engine_seams.md`.
4. Re-run `audit_coverage.py` — every pure-keyword card carrying it flips to
   playable for free.
5. Only *then* encode the residual ability text on cards that have both the
   keyword and extra text, as a separate batch.

Also check `src/swu/cards/keyword_sanitizer.py`: it strips upstream-mistagged
"grants-to-others" keywords from Unit/Leader cards (10 rules today, including
granted-only and lose-only, reading `deploy_box` so it covers Leaders). If a new
card appears to have a keyword it shouldn't, look there before debugging the
engine. Conversely, a card that *grants* a new keyword rather than having it may
need a new sanitiser rule.

### 2.7 Add a new deck

1. **Write the fixture** — `tests/fixtures/<deck_slug>.json`, SWUDB JSON format:
   ```json
   { "leader": {"id": "SET_5"}, "base": {"id": "SET_24"},
     "deck": [ {"id": "SET_153", "count": 3}, … ] }
   ```
   `id` is `{SET_CODE}_{card_number}`; zero-padding is tolerated and normalised.
   The loader (`src/swu/cards/decklist.py`) also accepts a flat list with
   leader/base inferred by card type.
2. **Plan it** — `python scripts/plan_encoding.py --deck tests/fixtures/<deck>.json`.
   With the DB fully encoded this will often report 52/52 already playable and
   plan nothing; that is the expected happy path for a deck built from shipped sets.
3. **Encode any gaps** exactly as in §2.5, using the deck slug.
4. **Verify / graduate:**
   ```bash
   python scripts/verify_encoding.py <deck-slug>              # progress + what's left
   python scripts/verify_encoding.py <deck-slug> --group 03   # focused tests for a group
   python scripts/verify_encoding.py <deck-slug> --graduate   # the full gate
   ```
   The gate requires: 100% of cards `implemented`+, every per-card test green, fast
   **and** medium suites passing, and a clean seeded soak using that exact deck. On
   a full pass it marks the deck shippable in `docs/decks_status.md` **and**
   registers it on the web start screen via `swu.web.decks.register_ui_deck` — so a
   graduated deck is selectable without a code edit. The manual UI smoke pass
   remains the human's sign-off.

   ⚠ `--graduate` shells out to `pytest tests/`, which means it can recurse from
   inside a test once a deck is 100% playable. Tests that exercise it must mock
   `_run`. If a suite hangs, diagnose with `-o faulthandler_timeout=N`.

5. **A soak catches what an audit cannot.** A 100%-playable audit only proves every
   card is *registered*; the deck soak has caught real card bugs on decks that
   needed zero new encoding. Always soak.

### 2.8 Regression gates

| Tier | Command | When |
|---|---|---|
| fast | `pytest` | every batch |
| slow | `pytest -m slow` | set milestone, before a release |
| campaign | `python scripts/soak.py --games 10000 --jobs 8 --decks starter,vanilla,keyword` | manual / overnight |

Additional whole-DB checks worth running after a release lands:
`scripts/audit_coverage.py`, `scripts/audit_images.py`, `scripts/audit_keyword_params.py`,
`scripts/find_reprints.py --check --verify-playable`.

If the heuristic bot's behaviour is in question after new cards land, measure it
with `scripts/bot_arena.py` / `scripts/bot_blunders.py` against the frozen
baseline in `benchmarks/` — **never by taste**.

### 2.9 Release checklist

```
[ ] card-count probe shows the API and manifest agree again
[ ] validate.py green
[ ] audit_images.py green (0 collisions, 0 missing)
[ ] audit_coverage.py: 0 text-bearing, 0 keyword-deferred, escape-hatches accounted for
[ ] find_reprints.py --check green
[ ] fast + medium suites green
[ ] soak clean for any newly graduated deck
[ ] new set code present in SET_ORDER and in src/swu/cards/__init__.py
[ ] docs/coverage_report.md and docs/decks_status.md regenerated
[ ] manual UI smoke pass
```

---

## Part 3 — Publishing hygiene

This project is intended to become a public repository. Card data, images and
deployment configuration all carry things that must not be published — some
personal, some legal, some merely embarrassing. Work through this **before** the
first push, and re-check it whenever a new document is added (including this one).

### 3.1 What is already excluded

`swu-game/.gitignore` excludes `data/`, `.venv/`, `__pycache__/`, `*.egg-info/`,
`dist/`, `build/`, `.pytest_cache/` and `*.log`. That single `data/` rule is doing
a great deal of work — it is what keeps the following out of git:

- `data/swu.db` and `data/raw/` — the harvested card corpus,
- `data/images/` — all card art,
- `data/users.json` — usernames, salted password hashes, bearer tokens,
- `data/bug_reports/` — player-submitted reports, screenshots and game replays,
- `data/custom_decks/`, `data/imported/`, `data/ui_decks.json`,
- `data/pipeline.log`, `data/llm.log*` — logs that can contain prompt content.

**Verify this holds before the first push** rather than trusting it:
`git status --porcelain` and `git check-ignore -v data/users.json` after `git init`.
There is no repository-root `.gitignore` today — add one covering `node_modules/`
and any deployment staging directories, or the push will be enormous.

### 3.2 What must be removed or parameterised

| Where | What | Fix |
|---|---|---|
| `_common.ps1` | Real SSH username and hostname of the home server (the file says outright that it is the only place they appear) | Replace with placeholders read from environment variables or an untracked `_common.local.ps1`; commit only an example file |
| `RUNNING.md`, `deploy-server.ps1`, `setup-server.ps1` | Home-server hostnames, WSL paths under a personal home directory, SSH invocations | Generalise to `<server-host>` / `<user>`, or exclude the deployment scripts from the public repo entirely |
| `compose.swu.yml` | Default hostname in `SWU_ALLOWED_HOSTS` | Leave the env var, drop the personal default |
| `README.md`, `CLAUDE.md`, `docs/*` | Absolute paths beginning with a personal home directory | Rewrite as repo-relative paths |
| `src/swu/web/auth.py` | `ALLOWED` — a hard-coded whitelist of two real first names, one flagged admin | Move to configuration (env var or an untracked config file) with an empty or example default |
| `docs/bug_triage_prompt.md`, `docs/soak_*.md`, `docs/phase6b_llm_handoff.md`, `encoding/*/MANIFEST.md` | Incidental personal names, hostnames, machine paths | Grep and scrub (§3.4) |
| `.claude/` | Hooks and skills referencing absolute personal paths; `settings.local.json` | Parameterise the skill's paths; never commit `settings.local.json` |
| `web/screenshots/`, `web/test-results/`, `swu-game/failures/` | Local artefacts that may embed paths or player data | Add to `.gitignore` |

### 3.3 Legal and courtesy constraints

These matter more than the personal details, because they affect whether the
project can exist publicly at all.

- **Do not redistribute card data or art.** The card corpus and images are the
  publisher's intellectual property. They are already gitignored — keep it that
  way, and make sure no fixture, test snapshot, doc or artifact smuggles bulk card
  text or images back in. The pipeline exists so a fresh clone can rebuild
  everything locally; that is the correct distribution model.
- **State the project's status plainly in the README:** an unofficial,
  non-commercial fan project, not affiliated with or endorsed by the publisher or
  rights holders, with all trademarks belonging to their owners. Add a licence for
  *your own code* that does not purport to license the card content.
- **Keep the API client polite and identifiable.** The harvest sets a descriptive
  `User-Agent`; keep one (a project name and URL is ideal), keep the 1.5 s default
  delay, keep the 429 back-off, and document in the README that users must not
  lower the delay. A public repo multiplies whatever the scripts do by the number
  of people who run them — the politeness settings become a shared obligation, not
  a personal preference. Consider whether the upstream site's terms permit the
  harvest at all before advertising it.
- **No API keys, ever.** The LLM opponent reads `ANTHROPIC_API_KEY` from the
  environment only, and the test suite stubs it out for every non-`live` test.
  Confirm no key literal is committed, and keep the README's guidance to set it via
  the environment.

### 3.4 Pre-push scan

Run these from the repository root and read every hit. Extend the pattern list
with anything specific to your setup (surname, other hostnames, LAN subnets):

```bash
git grep -nI -i -E "<your-username>|<your-surname>|@[a-z]+\.(com|net)|<server-host>|homeserver|192\.168\.|10\.0\.|sk-ant-|BEGIN [A-Z ]*PRIVATE KEY"
git grep -nI -E "C:\\\\Users\\\\|/home/[a-z]+/|/Users/[a-z]+/"
git ls-files | grep -E "\.log$|users\.json|bug_reports/|settings\.local\.json"
```

`git grep` only searches tracked files — which is the point: it tells you what
would actually be published. Do this **after** `git add`, before the first commit,
and remember that a secret committed once stays in history: if something slips
through, rewrite history or start a fresh repository rather than deleting it in a
later commit.

### 3.5 Making the repo usable by others

A public clone gets no `data/` directory, so the first-run experience is the
pipeline. Make sure the README leads with that:

1. create venv, `pip install -e ".[dev]"`
2. `python scripts/discover.py` (schema sanity check)
3. `python scripts/fetch_metadata.py` (long; resumable)
4. `python scripts/build_db.py`
5. `python scripts/fetch_images.py` → `fix_image_collisions.py` → `audit_images.py`
6. `python scripts/validate.py`
7. `pytest` (fast tier)

Anything in the test suite that requires a populated `data/swu.db` should skip
cleanly rather than fail when it is absent — worth verifying explicitly, since it
is the very first thing a new contributor will hit. Note also that the `repo` test
fixture resolves `data/swu.db` relative to the project directory, so tests must be
run from `swu-game/`.

---

## Quick reference

```bash
# Detect
python scripts/check_new_cards.py                 # (to be written — §1.1)
python scripts/audit_coverage.py                  # new keywords, remaining gaps
python -c "import sqlite3;print(sorted({r[0] for r in sqlite3.connect('data/swu.db').execute('SELECT DISTINCT set_code FROM cards')}))"

# Rebuild
python scripts/fetch_metadata.py --refresh
python scripts/build_db.py
python scripts/fetch_images.py && python scripts/fix_image_collisions.py
python scripts/audit_images.py && python scripts/validate.py

# Plan & encode
python scripts/plan_encoding.py --set NEW
python scripts/next_group.py --n 3                # or the /encode-next skill
python scripts/verify_encoding.py <slug> --group NN

# Ship a deck
python scripts/verify_encoding.py <deck-slug> --graduate
```
