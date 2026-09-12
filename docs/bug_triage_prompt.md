# Bug triage — the paste-ready out-of-band prompt

A reusable prompt the maintainer pastes into a fresh Claude session to process a
player's bug report **out of band** — not through the app. Claude reads the report
folder and edits `thread.json` directly on disk.

Reports land in the `data/bug_reports/<id>/` directory of whichever instance the
player is using. If you run a separate deployed copy, reports live in that copy's
`data/` while code fixes belong in your development tree — investigate and fix in
the dev tree, then ship with your normal deploy step.

---

## How to use it

1. In the AdminPanel **Bug Triage** view, look at the **NEEDS YOU** bucket — those
   are the reports waiting on you. Note the report **id** (the folder name, e.g.
   `2026-07-14-1532-boba-attack`).
2. Start a fresh Claude session in the repository root.
3. Paste the prompt below, filling in the report id on the last line.
4. When Claude finishes, refresh AdminPanel: the thread shows the reply and the new
   status. If code changed, deploy it so the fix reaches the player.

---

## The prompt (copy from here)

```
You are triaging a player's bug report for the SWU game, out of band.

AUDIENCE. Reports often come from non-technical players, sometimes children.
Write any message to the reporter in short, kind, plain language — no code, stack
traces or jargon. Note the UI contract: the reporter's own messages render as
"You" and every dev-side message renders under the shared "Dev Team" label, so
messages are unsigned by design — do not add a signature, because the app already
attributes it.

REPORT LOCATION:
  data/bug_reports/<ID>/
    thread.json      # the conversation + form fields + context + status
    screenshot.png   # optional — the screen at the moment of reporting
    game.json        # optional — replay bundle, present only for in-game reports

STEP 1 — READ.
  - Read thread.json. The FIRST message carries the three form fields (title,
    expected, actual); later messages carry `text`. The `context` block says which
    screen (game/start/explorer/replay/inbox), game_id, whose turn, pending
    decision, last action.
  - Look at screenshot.png if present.
  - If game.json is present, it is a deterministic replay bundle. To scrub to the
    bug, drive it through the replay path (session.replay_to_state / the
    scripts/replay.py + POST /api/replay reconstruction) or read the action
    history + seed directly. Reproduce the reported moment before theorising.

STEP 2 — DECIDE. Is the bug clear enough to act on?

  CLEAR (report + replay make the cause obvious):
    - Investigate and FIX it, following CLAUDE.md's recipes. Add/adjust tests; run
      the fast tier (see CLAUDE.md) before claiming a fix. If it's an engine or
      card bug, add a regression test.
    - Append a `claude` message to thread.json: confirm what went wrong in plain
      words and that it's fixed (or will be after the next update).
    - Set "status": "resolved".
    - If the player is on a separately deployed copy, the fix only reaches them
      after a deploy. In that case say "in the next update" rather than implying
      it is already live, and end your run by saying a deploy is needed.

  NOT CLEAR (can't reproduce, ambiguous, missing detail):
    - Do NOT guess-fix. Append a `claude` message asking SPECIFIC, answerable
      questions (e.g. "Which card did you tap right before it froze?" not "Can you
      give more detail?"). One or two questions, phrased simply.
    - Set "status": "needs_info".
    - If you're mid-investigation but need a code change shipped before it can be
      confirmed, you may use "status": "investigating" instead and say so.

STEP 3 — WRITE BACK. Edit thread.json in place, preserving every existing field:
  - Append to "messages" an object exactly of this shape:
      {
        "from": "claude",
        "ts": "<current UTC time as YYYY-MM-DDTHH:MM:SSZ>",
        "read_by": [],
        "text": "<your message to the reporter>"
      }
    `read_by` MUST be [] so the reporter sees it as unread (drives their inbox
    badge).
  - Set the top-level "status" to the value you chose. Change nothing else
    (id, author, created, context, reporter_archived, earlier messages stay
    intact).
  - Keep it valid JSON (2-space indent, matching the file). Do not touch
    screenshot.png or game.json.

STEP 4 — SUMMARISE for the maintainer: which report, what you found, what you
changed in code (files + whether tests pass), the status you set, and whether a
deploy is needed to ship the fix.

The report id is: <ID>
```

---

## Notes / refine over time

- The wording of the reporter-facing message is the part most worth tuning after a
  few real reports — keep it warm and jargon-free.
- Claude edits `thread.json` on disk; the reporter's inbox and the maintainer's
  AdminPanel both read the same file, so the reply and status show up on the next
  poll / refresh with no extra step.
- Reports never move folders on a status change. When a thread is finished, hit
  **Archive** in AdminPanel (moves the folder into `bug_reports/archive/`), which
  drops it from triage but keeps it in the reporter's inbox.
