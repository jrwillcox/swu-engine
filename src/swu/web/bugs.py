"""
Bug reports & two-way threaded messaging — the file-backed store + payload models.

A player (any whitelisted user) files a bug from any screen; an admin,
out of band via Claude, answers / asks for more detail / marks it resolved.  This
module owns the on-disk contract and the store; ``app.py`` wires the HTTP routes.

On-disk layout (the contract for out-of-band Claude processing) — one folder per
report under ``data/bug_reports/`` so it lands in the right instance and survives
``deploy.ps1`` (which mirrors code only, never ``data/``)::

    data/bug_reports/
      <id>/                      # id = "<YYYY-MM-DD>-<hhmm>-<slug>"
        thread.json
        screenshot.png           # best-effort; may be absent
        game.json                # replay bundle; present only for game-screen reports
      archive/<id>/              # same shape; the admin moves finished threads here

Two independent "done" concepts (never conflated):
  * ``reporter_archived`` — a cosmetic per-thread flag letting a reporter tidy their own
    inbox.  Never moves folders.
  * moving a folder into ``archive/`` — the admin's disk-level triage housekeeping.
Status changes NEVER move folders; the reporter inbox reads BOTH directories so
archiving drops a thread from the admin's triage without hiding it from the reporter.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from swu.web.paths import data_dir

# ── status lifecycle ──────────────────────────────────────────────────────────
#   new → needs_info ↔ (reporter replies) → investigating → resolved
STATUSES = {"new", "needs_info", "investigating", "resolved"}

# The automated/dev side signs its messages with this sender; a reporter's inbox
# renders any message that isn't their own as "Dev Team".
CLAUDE_FROM = "claude"


# ── payload models ────────────────────────────────────────────────────────────

class CreateBugRequest(BaseModel):
    title: str
    expected: str = ""
    actual: str = ""
    # Freeform capture context (screen, app_version, game_id, your_turn,
    # pending_decision, last_action, …); stored verbatim in thread.json.
    context: dict[str, Any] = {}
    # Best-effort screenshot, base64 PNG (optional "data:image/png;base64," prefix
    # tolerated).  Decoded → screenshot.png; a bad value never fails the report.
    screenshot_b64: Optional[str] = None
    # Replay bundle + snapshot + pending decision; written to game.json.
    game: Optional[dict[str, Any]] = None


class ReplyRequest(BaseModel):
    text: str


class StatusRequest(BaseModel):
    status: str


class ReporterArchiveRequest(BaseModel):
    """The reporter's cosmetic inbox archive toggle (never moves the folder)."""
    archived: bool


def _reporter_archived(thread: dict) -> bool:
    """Read the reporter's cosmetic archive flag from a stored thread.

    The key was renamed from ``sam_archived`` to ``reporter_archived``; threads
    written before the rename still carry the old name, so fall back to it rather
    than silently un-archiving them. New writes only ever use the new key.
    """
    if "reporter_archived" in thread:
        return bool(thread["reporter_archived"])
    return bool(thread.get("sam_archived", False))


class BugMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    ts: str
    read_by: list[str] = []
    # Replies carry ``text``; the initial report carries the three form fields.
    text: Optional[str] = None
    title: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None


class BugThread(BaseModel):
    id: str
    title: str
    status: str
    author: str
    created: str
    reporter_archived: bool = False
    # True when the folder lives under ``archive/`` (the admin's disk housekeeping),
    # independent of ``reporter_archived``.
    archived: bool = False
    context: dict[str, Any] = {}
    has_screenshot: bool = False
    has_game: bool = False
    messages: list[BugMessage] = []


class BugSummary(BaseModel):
    id: str
    title: str
    status: str
    author: str
    created: str
    updated: str          # ts of the latest message
    last_from: str        # raw sender of the latest message
    unread: int           # unread messages for the requesting user
    reporter_archived: bool
    archived: bool
    has_screenshot: bool
    has_game: bool
    # The reporter's original submission (first message), surfaced so the triage
    # list can show the gist without opening the thread.
    expected: str = ""
    actual: str = ""


class AdminTriage(BaseModel):
    """All users' active threads, bucketed on the signal the admin triages on:
    "does this need me to prompt Claude?"."""
    needs_you: list[BugSummary] = []
    waiting_on_reporter: list[BugSummary] = []
    resolved: list[BugSummary] = []


class UnreadCount(BaseModel):
    count: int


# ── errors ────────────────────────────────────────────────────────────────────

class BugError(Exception):
    """Base for bug-store failures."""


class BugNotFound(BugError):
    """No thread with that id (in either directory)."""


class BadStatus(BugError):
    """Status not in the lifecycle set."""


class BadId(BugError):
    """An id that fails the containment guard (path traversal attempt)."""


# ── helpers ───────────────────────────────────────────────────────────────────

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s[:40] or "report"


def _decode_png(b64: str) -> Optional[bytes]:
    """Decode a base64 PNG (tolerating a data-URL prefix).  None on any failure —
    the screenshot is best-effort and must never fail the report."""
    try:
        if "," in b64 and b64.strip().lower().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        return base64.b64decode(b64, validate=False)
    except Exception:
        return None


# ── the store ─────────────────────────────────────────────────────────────────

class BugStore:
    """File-backed bug reports.  All public methods are thread-safe.

    ``root`` is overridable for tests; production uses ``data_dir()/bug_reports``
    so reports land in the right instance and survive deploys.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root is not None else data_dir() / "bug_reports"
        self._lock = threading.RLock()

    # -- path resolution / containment guard -----------------------------------

    @property
    def _archive_root(self) -> Path:
        return self._root / "archive"

    def _check_id(self, bug_id: str) -> None:
        if not bug_id or not _ID_RE.match(bug_id) or bug_id == "archive":
            raise BadId(bug_id)

    def _dir_for(self, bug_id: str) -> tuple[Path, bool] | None:
        """Locate ``bug_id``'s folder → (path, archived) or None.  Searches the
        active dir first, then ``archive/``."""
        self._check_id(bug_id)
        active = self._root / bug_id
        if (active / "thread.json").exists():
            return active, False
        archived = self._archive_root / bug_id
        if (archived / "thread.json").exists():
            return archived, True
        return None

    # -- (de)serialisation -----------------------------------------------------

    @staticmethod
    def _read_thread(dir_path: Path) -> dict:
        with (dir_path / "thread.json").open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_thread(dir_path: Path, thread: dict) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        tmp = dir_path / "thread.json.tmp"
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(thread, f, indent=2)
        tmp.replace(dir_path / "thread.json")  # atomic-ish swap

    @staticmethod
    def _thread_model(dir_path: Path, thread: dict, archived: bool) -> BugThread:
        return BugThread(
            id=thread["id"],
            title=thread.get("title", ""),
            status=thread.get("status", "new"),
            author=thread.get("author", ""),
            created=thread.get("created", ""),
            reporter_archived=_reporter_archived(thread),
            archived=archived,
            context=thread.get("context", {}) or {},
            has_screenshot=(dir_path / "screenshot.png").exists(),
            has_game=(dir_path / "game.json").exists(),
            messages=[BugMessage(**m) for m in thread.get("messages", [])],
        )

    @staticmethod
    def _unread_for(thread: dict, username: str) -> int:
        return sum(
            1 for m in thread.get("messages", []) if username not in m.get("read_by", [])
        )

    def _summary(self, dir_path: Path, thread: dict, archived: bool, username: str) -> BugSummary:
        msgs = thread.get("messages", [])
        latest = msgs[-1] if msgs else {}
        report = msgs[0] if msgs else {}  # the initial submission (form fields)
        return BugSummary(
            id=thread["id"],
            title=thread.get("title", ""),
            status=thread.get("status", "new"),
            author=thread.get("author", ""),
            created=thread.get("created", ""),
            updated=latest.get("ts", thread.get("created", "")),
            last_from=latest.get("from", ""),
            unread=self._unread_for(thread, username),
            reporter_archived=_reporter_archived(thread),
            archived=archived,
            has_screenshot=(dir_path / "screenshot.png").exists(),
            has_game=(dir_path / "game.json").exists(),
            expected=report.get("expected") or "",
            actual=report.get("actual") or "",
        )

    def _iter_threads(self, *, include_archived: bool):
        """Yield (dir_path, thread_dict, archived) for every valid thread."""
        roots: list[tuple[Path, bool]] = [(self._root, False)]
        if include_archived:
            roots.append((self._archive_root, True))
        for base, archived in roots:
            if not base.exists():
                continue
            for child in sorted(base.iterdir()):
                if not child.is_dir() or (not archived and child.name == "archive"):
                    continue
                tj = child / "thread.json"
                if not tj.exists():
                    continue
                try:
                    yield child, self._read_thread(child), archived
                except (json.JSONDecodeError, OSError):
                    continue

    # -- create ----------------------------------------------------------------

    def create(
        self,
        *,
        author: str,
        title: str,
        expected: str = "",
        actual: str = "",
        context: dict[str, Any] | None = None,
        screenshot_b64: Optional[str] = None,
        game: Optional[dict[str, Any]] = None,
    ) -> BugThread:
        now = _now()
        ts = _ts(now)
        base_id = f"{now:%Y-%m-%d}-{now:%H%M}-{_slugify(title)}"
        with self._lock:
            # Uniquify against a same-minute, same-slug collision.
            bug_id = base_id
            n = 2
            while (self._root / bug_id).exists() or (self._archive_root / bug_id).exists():
                bug_id = f"{base_id}-{n}"
                n += 1
            dir_path = self._root / bug_id
            dir_path.mkdir(parents=True, exist_ok=True)

            thread = {
                "id": bug_id,
                "title": title,
                "status": "new",
                "author": author,
                "created": ts,
                "reporter_archived": False,
                "context": context or {},
                "messages": [
                    {
                        "from": author,
                        "ts": ts,
                        "read_by": [author],
                        "title": title,
                        "expected": expected,
                        "actual": actual,
                    }
                ],
            }
            self._write_thread(dir_path, thread)

            if screenshot_b64:
                png = _decode_png(screenshot_b64)
                if png:
                    (dir_path / "screenshot.png").write_bytes(png)
            if game is not None:
                with (dir_path / "game.json").open("w", encoding="utf-8") as f:
                    json.dump(game, f)

            return self._thread_model(dir_path, thread, archived=False)

    # -- read ------------------------------------------------------------------

    def get(self, bug_id: str) -> BugThread:
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            return self._thread_model(dir_path, self._read_thread(dir_path), archived)

    def list_for_user(self, username: str) -> list[BugSummary]:
        """A reporter's inbox: their own threads across BOTH active and archive/,
        newest first."""
        with self._lock:
            out = [
                self._summary(dp, th, arch, username)
                for dp, th, arch in self._iter_threads(include_archived=True)
                if th.get("author") == username
            ]
        out.sort(key=lambda s: s.created, reverse=True)
        return out

    def unread_count(self, username: str) -> int:
        with self._lock:
            return sum(
                self._unread_for(th, username)
                for _, th, _ in self._iter_threads(include_archived=True)
                if th.get("author") == username
            )

    def list_all_bucketed(self, username: str) -> AdminTriage:
        """Admin triage: ALL users' ACTIVE threads (archived ones drop off), each
        placed in a derived bucket.  ``username`` = the admin, for the unread count."""
        triage = AdminTriage()
        with self._lock:
            rows = [
                (self._summary(dp, th, arch, username), self._bucket(th))
                for dp, th, arch in self._iter_threads(include_archived=False)
            ]
        for summary, bucket in rows:
            getattr(triage, bucket).append(summary)
        for lst in (triage.needs_you, triage.waiting_on_reporter, triage.resolved):
            lst.sort(key=lambda s: s.updated, reverse=True)
        return triage

    @staticmethod
    def _bucket(thread: dict) -> str:
        """Derive the admin's triage bucket (see the plan's status-lifecycle section).

        NEEDS YOU = new, OR (needs_info/investigating AND latest is from the
        reporter).  WAITING ON REPORTER = latest from dev/admin AND needs_info.
        RESOLVED = resolved.  An investigating thread whose latest is from the dev
        side falls through to NEEDS YOU (the admin set it investigating — keep it on the
        list rather than lose it).
        """
        status = thread.get("status", "new")
        if status == "resolved":
            return "resolved"
        msgs = thread.get("messages", [])
        latest_from = msgs[-1].get("from") if msgs else thread.get("author")
        reporter_latest = latest_from == thread.get("author")
        if status == "new" or reporter_latest:
            return "needs_you"
        if status == "needs_info":
            return "waiting_on_reporter"
        return "needs_you"

    # -- mutate ----------------------------------------------------------------

    def add_message(self, bug_id: str, *, sender: str, text: str) -> BugThread:
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            thread = self._read_thread(dir_path)
            thread.setdefault("messages", []).append(
                {"from": sender, "ts": _ts(_now()), "read_by": [sender], "text": text}
            )
            self._write_thread(dir_path, thread)
            return self._thread_model(dir_path, thread, archived)

    def set_status(self, bug_id: str, status: str) -> BugThread:
        if status not in STATUSES:
            raise BadStatus(status)
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            thread = self._read_thread(dir_path)
            thread["status"] = status
            self._write_thread(dir_path, thread)
            return self._thread_model(dir_path, thread, archived)

    def set_reporter_archived(self, bug_id: str, value: bool) -> BugThread:
        """The reporter's cosmetic inbox archive — never moves the folder."""
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            thread = self._read_thread(dir_path)
            thread["reporter_archived"] = bool(value)
            self._write_thread(dir_path, thread)
            return self._thread_model(dir_path, thread, archived)

    def mark_read(self, bug_id: str, username: str) -> BugThread:
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            thread = self._read_thread(dir_path)
            changed = False
            for m in thread.get("messages", []):
                rb = m.setdefault("read_by", [])
                if username not in rb:
                    rb.append(username)
                    changed = True
            if changed:
                self._write_thread(dir_path, thread)
            return self._thread_model(dir_path, thread, archived)

    def archive(self, bug_id: str) -> BugThread:
        """The admin's disk-level declutter: move the folder into ``archive/``.  A no-op
        if already archived.  Independent of status and ``reporter_archived``."""
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, archived = found
            if archived:
                return self._thread_model(dir_path, self._read_thread(dir_path), True)
            self._archive_root.mkdir(parents=True, exist_ok=True)
            dest = self._archive_root / bug_id
            shutil.move(str(dir_path), str(dest))
            return self._thread_model(dest, self._read_thread(dest), True)

    # -- artifacts -------------------------------------------------------------

    def screenshot_path(self, bug_id: str) -> Optional[Path]:
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, _ = found
            p = dir_path / "screenshot.png"
            return p if p.exists() else None

    def game_path(self, bug_id: str) -> Optional[Path]:
        """The replay bundle written for a game-screen report (game.json), or None
        if the report was filed from a non-game screen.  The admin opens this in the
        ReplayViewer via the /api/replay reconstruction endpoint."""
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, _ = found
            p = dir_path / "game.json"
            return p if p.exists() else None

    def author_of(self, bug_id: str) -> str:
        with self._lock:
            found = self._dir_for(bug_id)
            if found is None:
                raise BugNotFound(bug_id)
            dir_path, _ = found
            return self._read_thread(dir_path).get("author", "")
