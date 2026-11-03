---
name: encode-next
description: Encode the next batch of unimplemented Star Wars Unlimited cards. Run for the gap-filling campaign — pulls the next N groups from the global queue, implements them declaratively, tests them, and stops at a clean boundary. Use when the user types /encode-next [N].
argument-hint: "[N groups, default 3]"
---

# Encode the next campaign batch

You are filling card-implementation gaps in the SWU engine, group by group, across
all sets. **Everything you need is on disk** — the queue walker re-derives the whole
campaign state every run, so this works identically mid-session, after /compact,
after /clear, or after a restart. There is nothing to "remember" or resume.

**All commands run from `swu-game/`.** Python is `.venv/Scripts/python.exe`.
`N` = the argument (default **3**; `/encode-next 1` = one group; `/encode-next 2`
when usage is tight).

## Command shapes — keep the batch prompt-free

A batch must run **start to finish without a permission prompt**. Prompts come from
command SHAPE, not from the allow-list: Claude Code will not apply a `Bash(foo:*)`
prefix rule to any command containing `|`, `>`, `<<`, `$(...)` or backticks, because
the rule cannot vouch for what follows. In one measured batch, 149 of 153 bash calls
contained one of those. So:

- **Never use a heredoc** (`python - <<'PY'`). To run throwaway Python, `Write` the
  script into the scratchpad directory and run `python <path>` — one clean prefix.
- **Never pipe into `head`/`wc`/`sort`, and never redirect.** Use the dedicated tools
  instead: `Grep` (it has `-n`, `-A/-B/-C`, `head_limit`, `output_mode`) and `Read`
  (it has `offset`/`limit`). These are faster and cheaper than shelling out anyway.
- **Don't prefix with `cd "…" &&`.** Pass an absolute path to the interpreter —
  `"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe"` on Windows,
  `"$CLAUDE_PROJECT_DIR/.venv/bin/python"` on macOS/Linux.
  For pytest, add `-c` / rootdir args rather than chaining a `cd`.
- A `PreToolUse` hook (`.claude/hooks/auto_allow.py`) auto-approves project work and
  is the primary defence — but it only covers this machine, so keep commands in these
  shapes regardless. If a prompt ever does appear, that is a bug: say so in the batch
  report so the hook's denylist can be adjusted.

## Step 1 — Pull the queue

```
.venv/Scripts/python.exe scripts/next_group.py --n N
```

Work **only** the printed `NEXT1..NEXTk` groups, **in order**. Each line gives the
group id, spec path, remaining `cards=`, and a ready-to-run `VERIFY:` command.
Honor the flag:

- **`[ESCALATION]`** — needs a not-yet-existing primitive. This *one group is the
  whole batch*. Follow the escalation rule (below); do NOT co-mingle other groups.
- **`[KEYWORD-ENGINE]`** (Support) — implement the keyword **engine-side once**;
  this one group is the whole batch. No residual card text this run (see Step 2).
- **`[KEYWORD-RESIDUAL]`** — the keyword already works; encode **only** the listed
  `cards=` (residual text).
- **no flag** — an ordinary ability batch; encode the listed `cards=`.

If the queue prints `QUEUE EMPTY`, the campaign is done — report that and stop.

## Step 2 — Per group (in order)

1. **Read the spec file** at the printed `spec=` path (self-contained: card text,
   mechanical analysis, suggested primitives, acceptance criteria).
2. **Read** `docs/engine_seams.md` (reuse patterns and decision kinds **by name**)
   and `docs/encoding_guide.md` (the recipe). For a named precedent, `grep`
   `docs/history/seams_log.md` and `docs/history/encoding_history.md` for the card
   id; never read those in full.
3. **Implement declaratively** in `src/swu/cards/<set>/abilities.py` with
   `@card_ability(SET, NUM)`. If the set module doesn't exist yet, create it and add
   its import to `src/swu/cards/__init__.py`. **Reuse** existing primitives and
   decision kinds; prefer a TargetSpec/Condition tweak over new machinery.
4. **One focused test per card** in `tests/test_<set>_cards.py`. Every test method
   name MUST embed the set+number (e.g. `test_SOR_6_...`) — the `-k` VERIFY gate
   keys on the number. Assert behavior through public interfaces
   (`legal_actions` / `apply`), not internals.
5. **escape_hatch=True only when irreducible** — and say so in the report.
6. **KEYWORD-ENGINE (Support)**: implement the keyword in the engine once, with
   synthetic tests; then move `"Support"` from `PHASE3_KEYWORDS` to
   `PHASE2_KEYWORDS` in `scripts/audit_coverage.py`, and update the keyword list in
   `docs/engine_seams.md`. Encode no residual card text this invocation.
7. **Escalation rule** (`docs/engine_seams.md`): a primitive that touches core
   resolution, the trigger system or decision machinery → **STOP, implement nothing,
   flag it** for a dedicated framework session. A small, self-contained primitive may
   land inline; a new decision kind must follow "Adding a decision kind" there.
8. **Run the printed `VERIFY:` command** for the group. It must pass before you move
   to the next group.

## Step 3 — Batch end

1. **One fast suite** (the only full run this batch):
   ```
   .venv/Scripts/python.exe -m pytest -q
   ```
   Fix regressions. A stand-in test that rots because you just encoded its
   placeholder card → refresh the stand-in. A regression that resists two fix
   attempts → **revert that one card** and flag it; don't sink the batch.
2. **Refresh the queue + peek next**: `.venv/Scripts/python.exe scripts/next_group.py --n 1`.
3. **On a `MILESTONE:` line** (a set just completed): run the medium tier
   (`.venv/Scripts/python.exe -m pytest -m slow -q`) and
   `.venv/Scripts/python.exe scripts/audit_coverage.py` (regenerates
   `docs/coverage_report.md`). Do NOT `--graduate` a `*-set` slug and do NOT soak it
   (sets aren't decks).

## Step 4 — Report (≤15 lines) then HARD STOP

Report: per-group result (cards done / escape-hatches / escalations flagged),
fast-suite result, the `CAMPAIGN:` line, and the next group id. Then **stop** —
never auto-start another batch. If context is getting long, stop early at a clean,
fully-tested group boundary. Remind the user to watch `/usage`; every invocation
ends at a clean, tested boundary, so it's always safe to stop.

## Doc & memory discipline (keeps context lean — follow exactly)

- **Do NOT write per-card or per-group notes anywhere.** Two exceptions: a genuinely
  NEW primitive → **one row** in `docs/engine_seams.md` plus an entry in
  `docs/history/seams_log.md`; a keyword completing → the keyword-list update.
  Never add to `CLAUDE.md`.
- **No per-batch history document.** Progress lives in the generated
  `encoding/<slug>-set/manifest.json` + `MANIFEST.md` and `docs/coverage_report.md`
  (all machine-regenerated). Add **no** campaign entries to `docs/history/encoding_history.md`.
  The batch report is ephemeral chat output.
- **Memory: one file, in place.** Update the campaign memory topic file
  `project_gap_campaign.md` (in your persistent memory dir — the path is in your
  session's memory system-reminder) by **overwriting** its STATUS line, and only on a
  durable change (a milestone, a new seam, a workflow correction) — never append,
  never create per-set/per-batch memory files. Touch `MEMORY.md` only if that one
  index line's hook actually changes.
