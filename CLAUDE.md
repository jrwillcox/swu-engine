# SWU engine: notes for Claude Code

A rules engine, bot opponents and web client for *Star Wars: Unlimited*. Every card
in the database is encoded, so most work now is bug fixes, new sets, and bot or UI
improvements. Start with the [README](README.md) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Commands

Run from this directory using the project venv (`.venv/Scripts/python.exe` on
Windows, `.venv/bin/python` elsewhere).

| Task | Command |
|---|---|
| Fast tests (the default tier) | `python -m pytest` |
| Slow tests (soak, Hypothesis) | `python -m pytest -m slow` |
| One card's tests | `python -m pytest tests/test_sor_cards.py -k SOR_59` |
| Lint and type-check | `ruff check .` then `mypy` |
| Front-end checks (`web/`) | `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test` |
| Card coverage | `python scripts/audit_coverage.py` |
| Run the app | `python -m swu.web`, then `cd web && npm run dev` |

CI runs all of these except the slow tier. Run them before pushing; `npm run format`
fixes Prettier failures.

## Git workflow

- `main` is protected. Work on a branch, open a PR (`gh pr create`), and let the
  owner review and squash-merge it.
- The repository is public. Keep personal names, hostnames and email addresses out
  of code, docs, tests and commit messages.

## Rules that are easy to break

- **Everything is an `Action`.** `apply()` deep-copies the state before mutating it.
- **Determinism.** Get randomness only from `state.make_rng()` (store
  `rng.getstate()` back) and modifier ids only from `state.alloc_modifier_id()`.
  Never use the global `random` module or `uuid`.
- **The wire protocol.** The front end uses each `Action`'s class name and field
  names. Never rename them.
- **Keywords and stats.** Use `has_keyword`/`keyword_value` and
  `compute_power`/`compute_hp`. Never string-match card text or read printed stats in
  game logic.
- **Card identity.** `(set_code, card_number)` is not unique, since leaders share
  numbers with tokens. The DB `id` is.
- **Layering.** A module in `engine/actions/` imports only from lower layers
  (`tests/test_actions_layering.py`). Put an `Action` beside the handler that emits
  it, and a decision kind's `register_decisions` row in its handler's module.
- **Cards are data.** Encode with the existing vocabulary. A new primitive that
  touches core resolution, the trigger or decision machinery, or needs replacement
  effects needs its own design session: stop and flag it.

## Where to look

| Need | Read |
|---|---|
| Engine contract, state model, adding a keyword, action or zone | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Encoding a card | [`docs/encoding_guide.md`](docs/encoding_guide.md) |
| Patterns, decision kinds, engine internals | [`docs/engine_seams.md`](docs/engine_seams.md) |
| Precedent for a card or primitive | Search [`docs/history/seams_log.md`](docs/history/seams_log.md) and [`docs/history/encoding_history.md`](docs/history/encoding_history.md) for the card id |
| Bots and measuring them | [`docs/bots.md`](docs/bots.md) |
| Tests, soak campaigns, invariants | [`docs/testing.md`](docs/testing.md) |
| A new set or card release | [`docs/new_releases.md`](docs/new_releases.md) |
| A player's bug report | [`docs/bug_triage_prompt.md`](docs/bug_triage_prompt.md) |
| Everything else | [`docs/README.md`](docs/README.md) |

## Keeping this file short

Claude Code reads this file at the start of every session. Add a rule here only if it
is easy to break and costly when broken. Put reference material in `docs/` and
history in `docs/history/`.
