# Bug Reporting & Two-Way Messaging — Implementation Plan

A system for players (any whitelisted user) to report bugs from any screen on
the iPad, and for the maintainer — via Claude, out of band — to answer, request more detail,
or mark bugs resolved. Two-way threaded messaging, with an admin triage surface in
the existing AdminPanel.

This document is **staged** so it can be implemented across separate sessions. Read
"Shared design" first (every stage depends on it), then implement stages in order.
Stages 2/3/4 can be done in any order once Stage 1 is in.

---

## Shared design (read before any stage)

### Roles & multi-user
- Every report is attributed to `author` = the **authenticated username** from the
  bearer token (never hardcoded). This makes the whole system multi-user for free.
- Adding a reporter = adding a username to `ALLOWED` in `src/swu/web/auth.py`.
- **Non-admin users** see only their **own** threads in their inbox.
- **Admin** (`admin: true`, already surfaced to the frontend via
  `AuthUser.admin`) sees **all** users' threads in the AdminPanel triage view.
- Replies from the automated/dev side use `from: "claude"`. In a reporter's inbox,
  any message that isn't their own renders as **"Dev Team"** (the individual
  helper's identity is not surfaced). The reporter's own messages render as **"You"**.

### The two "done" concepts (do not conflate)
- **Reporter housekeeping** — a cosmetic `reporter_archived` flag on the thread. Lets a
  reporter tidy their *own* inbox whenever they're satisfied. Never moves folders.
  (Inbox-management is an intentional teaching element.)
- **Admin decluttering** — moving a finished thread's folder from `bug_reports/`
  into `bug_reports/archive/`. This is the maintainer's disk-level triage housekeeping and is
  independent of the reporter's view.

**Critical rule:** status changes NEVER move folders automatically. The inbox
endpoints read from **both** `bug_reports/` and `bug_reports/archive/`, so the maintainer can
archive a folder to drop it from his triage list without hiding anything from the
reporter.

### Status lifecycle
`new` → `needs_info` ↔ (reporter replies) → `investigating` → `resolved`

The signal the maintainer actually triages on is **"does this need me to prompt Claude?"**,
which is derived, not raw status:
- **NEEDS YOU** = `status == "new"`, OR (`status in {needs_info, investigating}`
  AND the latest message is from the reporter).
- **WAITING ON REPORTER** = latest message is from `claude`/admin AND
  `status == "needs_info"`.
- **RESOLVED** = `status == "resolved"`.

### On-disk file format (the contract for out-of-band Claude processing)
```
data/bug_reports/
  <id>/                      # id = "<YYYY-MM-DD>-<hhmm>-<slug>"
    thread.json
    screenshot.png           # best-effort; may be absent
    game.json                # replay bundle + view snapshot + pending decision;
                             #   present only for reports filed from a game screen
  archive/<id>/              # same shape; the maintainer moves finished threads here
```

`thread.json`:
```jsonc
{
  "id": "2026-07-14-1532-boba-attack",
  "title": "Boba Fett attack did nothing",
  "status": "new",
  "author": "bob",
  "created": "2026-07-14T15:32:11Z",
  "reporter_archived": false,     // reporter's cosmetic archive
  "context": {
    "screen": "game",             // game | start | explorer | replay | inbox
    "app_version": "…",           // optional build marker
    "game_id": "…",               // if screen == game
    "your_turn": true,
    "pending_decision": "choose_target",
    "last_action": "played Boba Fett"
  },
  "messages": [
    {
      "from": "bob",
      "ts": "2026-07-14T15:32:11Z",
      "read_by": ["bob"],
      "title": "Boba Fett attack did nothing",   // first message only
      "expected": "Boba should deal 3 damage",    // first message only
      "actual": "Nothing happened when I tapped attack"  // first message only
    },
    { "from": "claude", "ts": "…", "read_by": [], "text": "…" }
  ]
}
```
- The **initial report** is the first message: it carries the three form fields
  (`title`, `expected`, `actual`) instead of `text`.
- **Replies** (both directions) carry `text`.
- **Unread for user X** = any message where `X` is not in `read_by`.

### API surface (all resolve current user from the bearer token, like `/api/auth/me`)
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/bugs` | any user | create a report |
| GET | `/api/bugs` | any user | list **own** active+archived threads (reporter inbox) |
| GET | `/api/bugs/{id}` | owner or admin | full thread |
| POST | `/api/bugs/{id}/reply` | owner or admin | append a text message |
| POST | `/api/bugs/{id}/read` | any participant | mark messages read by current user |
| GET | `/api/bugs/unread-count` | any user | badge number for current user |
| GET | `/api/bugs/{id}/screenshot` | owner or admin | serve the PNG |
| GET | `/api/admin/bugs` | admin only | ALL users' threads, bucketed for triage |
| POST | `/api/admin/bugs/{id}/status` | admin only | set status |
| POST | `/api/admin/bugs/{id}/archive` | admin only | move folder → `archive/` |

### Build/deploy note
Build & test in **dev** (`swu-game/`, ports :8001 / :5174). Ship with `deploy.ps1`
(code-only; `data/bug_reports/` on the deployed side persists across deploys). A player
plays on the **deployed** instance, so real reports land in
`swu-game-deployed/data/bug_reports/`; out-of-band Claude processing reads/writes
there.

---

## Stage 1 — Backend: BugStore + endpoints
**Depends on:** nothing. **Do first.**

- New `src/swu/web/bugs.py` with a `BugStore` over `data_dir()/bug_reports/`
  (reuse `swu.web.paths.data_dir` so it lands in the right instance and survives
  deploys). Methods: `create`, `list_for_user`, `get`, `add_message`, `set_status`,
  `mark_read`, `unread_count`, `archive`, and an admin `list_all_bucketed`.
- Pydantic models (in `models.py` or `bugs.py`): `CreateBugRequest`,
  `BugMessage`, `BugThread`, `BugSummary`, `ReplyRequest`, `StatusRequest`,
  `AdminTriage` (three buckets).
- Wire the routes into `app.py` per the API table above. Reuse the existing
  token→user resolution used by `/api/auth/me`; add an admin guard for the
  `/api/admin/bugs*` routes.
- Screenshot arrives as base64 PNG in the JSON body → decode → write
  `screenshot.png`. `game` (replay bundle + snapshot + pending decision) written to
  `game.json`. Both optional.
- Id generation, atomic-ish writes, containment guard (never read/write outside
  `bug_reports/`, mirroring `resolve_image`'s guard).

**Acceptance:** unit tests in `tests/` cover create → list → get → reply →
mark-read → unread-count → status → archive, including the multi-user rule (user A
cannot GET user B's thread; admin can) and that inbox listing spans both
`bug_reports/` and `archive/`. Full suite green (run via the venv; use
`--basetemp` override per the users.json test note).

---

## Stage 2 — Report Bug flow (capture + modal + persistent HUD)
**Depends on:** Stage 1.

- Add `html-to-image` to `web/package.json`.
- **Persistent HUD** component rendered in `web/src/App.tsx` **after the auth gate
  but outside the screen switch**, so "Report Bug" + an inbox envelope (with unread
  badge) appear on every screen (start, explorer, game, replay). It needs the
  current screen id + active game id (thread through from App's existing state).
- **Capture-then-open:** clicking Report Bug first grabs the screenshot of the
  current screen (`html-to-image`, best-effort, never blocking) and, if a game is
  live, fetches the replay bundle via `/api/games/{id}/replay` plus the current
  snapshot / pending decision — *then* opens the form pre-loaded with those
  artifacts. (Avoids any hide/re-show dance.)
- **`ReportBugModal`** with three labelled fields — **Title**, **"What did you
  expect to happen?"**, **"What actually happened?"** — light non-empty validation.
  Submit POSTs text + context + screenshot_b64 + game to `/api/bugs`.
- Client additions in `web/src/api/client.ts` + `types.ts`.

**Acceptance:** A reporter can submit from any screen; a `<id>/` folder appears on disk
with `thread.json`, `screenshot.png` (when capture succeeded), and `game.json` (from
a game). Submission never blocks on a failed screenshot.

---

## Stage 3 — Reporter inbox (reporter-facing)
**Depends on:** Stage 1 (works without Stage 2, but pair them for a demo).

- Inbox overlay reachable from the HUD envelope: thread list with read/unread dots,
  status chip, and a "Dev Team replied" highlight for resolved/unread.
- Thread view: messages (own = "You", others = "Dev Team"), the screenshot, and a
  **text-only** reply box. Opening a thread marks its messages read.
- Reporter housekeeping: an **Archive** toggle (`reporter_archived`) + an "Archived" tab
  so tidying their own inbox is a first-class, teachable action.
- Poll `/api/bugs/unread-count` on mount + every 20s to drive the HUD badge.

**Acceptance:** A reporter sees replies, can reply, sees resolved items celebrated, and can
archive/unarchive their own threads without affecting the maintainer's view.

---

## Stage 4 — Admin triage in AdminPanel (the maintainer's primary surface)
**Depends on:** Stage 1.

- Extend `web/src/components/AdminPanel.tsx` (already admin-gated) with a **Bug
  Triage** section alongside "Manage users", backed by `GET /api/admin/bugs`.
- Show the three buckets — **NEEDS YOU**, **WAITING ON REPORTER**, **RESOLVED** —
  each thread row showing `author`, `title`, status, age, and last-message-from.
  The NEEDS YOU bucket is the maintainer's worklist (the ones to prompt Claude with).
- Thread detail: full messages, the screenshot, the `context` block, a link/button
  to **open `game.json` in the existing `ReplayViewer`** (via the `/api/replay`
  reconstruction endpoint) so the maintainer can scrub to the bug, a **status** control, an
  optional **reply** box (posts as the admin), and an **Archive** button
  (`/api/admin/bugs/{id}/archive`).

**Acceptance:** The maintainer, from the app, sees every user's threads correctly bucketed,
can open the reported game in the replay viewer, change status, optionally reply,
and archive to declutter — with archived threads dropping off triage but remaining
in the reporter's inbox.

---

## Stage 5 — Operational: reusable step-4 prompt + docs
**Depends on:** Stages 1–4 landed.

- Draft `docs/bug_triage_prompt.md` — the reusable prompt the maintainer pastes to have Claude
  process a report out of band: read `swu-game-deployed/data/bug_reports/<id>/`;
  if the report + replay make the bug clear, investigate/fix, append a `claude`
  message written for a **non-developer** audience, and set `status: resolved`; if
  not, append **specific** clarifying questions and set `status: needs_info`. Refine
  wording together after the plumbing is proven.
- Update `CLAUDE.md` (feature overview + where reports live + the two-archive model)
  and `RUNNING.md` if operational steps change.

**Acceptance:** The maintainer has a paste-ready prompt and the docs describe the end-to-end
loop.

---

## Open/minor decisions (defaults chosen; override anytime)
- Unread poll interval: **20s**.
- Helper display name in reporter inbox: **"Dev Team"**.
- Replies are **text-only** in v1 (no fresh screenshot on reply).
- `bugs.ps1` triage script: **dropped** — superseded by the Stage 4 AdminPanel view.
