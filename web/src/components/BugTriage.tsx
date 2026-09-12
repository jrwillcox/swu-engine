// Admin bug triage (the admin's primary surface) — rendered inside the admin-gated
// AdminPanel alongside "Manage users". Backed by GET /api/admin/bugs, which
// returns every user's ACTIVE threads bucketed on the one signal the admin triages on:
// "does this need me to prompt Claude?".
//
//   NEEDS YOU           — the worklist (new, or the reporter answered last)
//   WAITING ON REPORTER — the admin asked for more and is waiting
//   RESOLVED            — done (still shown until the folder is archived)
//
// Thread detail: the full messages (real sender names — this is the dev side), the
// screenshot, the capture `context` block, a button to open the reported game in
// the ReplayViewer (via /api/replay), a status control, a reply box (posts as the
// admin), and an Archive button that declutters the triage view without hiding the
// thread from the reporter. See src/swu/web/bugs.py for the on-disk contract.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AdminTriage, BugSummary, BugThread, ReplayResponse } from "../api/types";

const STATUSES: { value: string; label: string }[] = [
  { value: "new", label: "New" },
  { value: "needs_info", label: "Needs info" },
  { value: "investigating", label: "Investigating" },
  { value: "resolved", label: "Resolved" },
];

const STATUS_META: Record<string, { label: string; cls: string }> = {
  new: { label: "New", cls: "new" },
  needs_info: { label: "Needs info", cls: "needs" },
  investigating: { label: "Investigating", cls: "investigating" },
  resolved: { label: "Resolved", cls: "resolved" },
};

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, cls: "new" };
}

// Friendly relative age from an ISO-8601 (UTC "Z") timestamp; falls back to the
// raw string so a bad value never blanks the row (mirrors BugInbox).
function timeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso || "";
  const secs = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (secs < 45) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(t).toLocaleDateString();
}

const msgOf = (e: unknown) =>
  e instanceof ApiError ? e.message : "Something went wrong — try again.";

export function BugTriage({
  onWatchReplay,
}: {
  /** Open the reported game in the ReplayViewer (takes over the whole screen). */
  onWatchReplay?: (replay: ReplayResponse) => void;
}) {
  const [triage, setTriage] = useState<AdminTriage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setTriage(await api.bugs.adminList());
      setError(null);
    } catch (e) {
      setError(msgOf(e));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (selected) {
    return (
      <TriageThread
        id={selected}
        onBack={() => setSelected(null)}
        onChanged={reload}
        onArchived={() => {
          setSelected(null);
          void reload();
        }}
        onWatchReplay={onWatchReplay}
      />
    );
  }

  if (error) return <p className="bug-error">{error}</p>;
  if (triage === null) return <p className="bug-inbox-empty">Loading…</p>;

  const total =
    triage.needs_you.length + triage.waiting_on_reporter.length + triage.resolved.length;
  if (total === 0) {
    return (
      <p className="bug-inbox-empty">No reports yet. When players send bugs they land here.</p>
    );
  }

  return (
    <div className="triage">
      <Bucket
        title="Needs you"
        hint="New, or the reporter replied last — prompt Claude with these."
        tone="needs-you"
        rows={triage.needs_you}
        onOpen={setSelected}
      />
      <Bucket
        title="Waiting on reporter"
        hint="You asked for more detail; waiting on a reply."
        tone="waiting"
        rows={triage.waiting_on_reporter}
        onOpen={setSelected}
      />
      <Bucket
        title="Resolved"
        hint="Fixed. Archive to declutter (stays in the reporter's inbox)."
        tone="resolved"
        rows={triage.resolved}
        onOpen={setSelected}
      />
    </div>
  );
}

function Bucket({
  title,
  hint,
  tone,
  rows,
  onOpen,
}: {
  title: string;
  hint: string;
  tone: string;
  rows: BugSummary[];
  onOpen: (id: string) => void;
}) {
  return (
    <section className={`triage-bucket ${tone}`}>
      <div className="triage-bucket-head">
        <h3>
          {title} <span className="triage-count">{rows.length}</span>
        </h3>
        <p className="triage-hint">{hint}</p>
      </div>
      {rows.length === 0 ? (
        <p className="triage-empty">Nothing here.</p>
      ) : (
        <ul className="bug-thread-list">
          {rows.map((s) => (
            <TriageRow key={s.id} s={s} onOpen={() => onOpen(s.id)} />
          ))}
        </ul>
      )}
    </section>
  );
}

// A one-line gist of the reporter's submission for the triage list ("what
// happened" is the bug; fall back to "expected" if that's all they filled in).
function reportPreview(s: BugSummary): string {
  if (s.actual) return `“${s.actual}”`;
  if (s.expected) return `Expected: ${s.expected}`;
  return "";
}

function TriageRow({ s, onOpen }: { s: BugSummary; onOpen: () => void }) {
  const meta = statusMeta(s.status);
  // Whose turn is it? The reporter is waiting when the dev side spoke last.
  const reporterLast = s.last_from === s.author;
  const preview = reportPreview(s);
  return (
    <li>
      <button className="bug-thread-row" onClick={onOpen}>
        <span className="bug-thread-main">
          <span className="bug-thread-title">{s.title || "(untitled)"}</span>
          {preview && <span className="triage-preview">{preview}</span>}
          <span className="triage-id" title="Bug ID">
            {s.id}
          </span>
          <span className="bug-thread-sub">
            <span className="triage-author">{s.author}</span>
            <span className={`bug-status ${meta.cls}`}>{meta.label}</span>
            <span className="triage-lastfrom">
              {reporterLast ? "reporter replied" : `${s.last_from} replied`}
            </span>
            <span className="bug-thread-age">{timeAgo(s.updated || s.created)}</span>
          </span>
        </span>
      </button>
    </li>
  );
}

function TriageThread({
  id,
  onBack,
  onChanged,
  onArchived,
  onWatchReplay,
}: {
  id: string;
  onBack: () => void;
  onChanged: () => void;
  onArchived: () => void;
  onWatchReplay?: (replay: ReplayResponse) => void;
}) {
  const [thread, setThread] = useState<BugThread | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [shotUrl, setShotUrl] = useState<string | null>(null);
  const [openingReplay, setOpeningReplay] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setThread(null);
    api.bugs
      .get(id)
      .then((t) => !cancelled && setThread(t))
      .catch((e) => !cancelled && setError(msgOf(e)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Fetch the screenshot with the bearer header (can't be a bare <img src>), and
  // revoke the object URL when the thread changes / on unmount.
  const urlRef = useRef<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!thread?.has_screenshot) {
      setShotUrl(null);
      return;
    }
    api.bugs.screenshotObjectUrl(id).then((u) => {
      if (cancelled) {
        if (u) URL.revokeObjectURL(u);
        return;
      }
      urlRef.current = u;
      setShotUrl(u);
    });
    return () => {
      cancelled = true;
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
  }, [id, thread?.has_screenshot]);

  async function setStatus(status: string) {
    setError(null);
    try {
      setThread(await api.bugs.adminSetStatus(id, status));
      onChanged();
    } catch (e) {
      setError(msgOf(e));
    }
  }

  async function send() {
    const text = reply.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      setThread(await api.bugs.reply(id, text));
      setReply("");
      onChanged();
    } catch (e) {
      setError(msgOf(e));
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    setError(null);
    try {
      await api.bugs.adminArchive(id);
      onArchived();
    } catch (e) {
      setError(msgOf(e));
    }
  }

  // Open the reported game in the ReplayViewer: pull game.json, reconstruct the
  // per-step snapshots via /api/replay, then hand the result up to App.
  async function openReplay() {
    if (openingReplay || !onWatchReplay) return;
    setOpeningReplay(true);
    setError(null);
    try {
      const g = await api.bugs.game(id);
      if (!g.replay) {
        setError("This report has no replay bundle to open.");
        return;
      }
      const resp = await api.replay(g.replay);
      onWatchReplay(resp);
    } catch (e) {
      setError(msgOf(e));
    } finally {
      setOpeningReplay(false);
    }
  }

  const meta = thread ? statusMeta(thread.status) : null;
  // Keep the pre-conversation chrome minimal so the thread gets the height: show
  // only the game id here (the rest of the capture context lives in the game.json
  // replay bundle, reachable via "Open game in replay viewer").
  const gameId = thread?.context?.game_id;

  return (
    <div className="bug-thread-view">
      <div className="bug-inbox-head">
        <button className="btn btn-ghost" onClick={onBack} aria-label="Back to triage">
          ← Back
        </button>
        {thread && (
          <button className="btn btn-ghost bug-archive-btn" onClick={archive}>
            Archive
          </button>
        )}
      </div>

      {error && <p className="bug-error">{error}</p>}

      {!thread ? (
        <p className="bug-inbox-empty">Loading…</p>
      ) : (
        <>
          <div className="bug-thread-header">
            <h2>{thread.title || "(untitled)"}</h2>
            {meta && <span className={`bug-status ${meta.cls}`}>{meta.label}</span>}
            <span className="triage-author">{thread.author}</span>
          </div>

          <BugIdChip id={thread.id} />

          <div className="triage-controls">
            <label className="triage-status-ctl">
              <span>Status</span>
              <select
                aria-label="Set status"
                value={thread.status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            {thread.has_game && (
              <button
                className="btn"
                onClick={openReplay}
                disabled={openingReplay || !onWatchReplay}
              >
                {openingReplay ? "Loading replay…" : "▶ Open game in replay viewer"}
              </button>
            )}
          </div>

          {gameId != null && gameId !== "" && (
            <div className="triage-gameid">
              <span className="triage-gameid-key">Game</span>
              <span className="triage-gameid-val">{String(gameId)}</span>
            </div>
          )}

          {/* Two-column body (mirrors the reporter inbox): the conversation gets a
              flexible column that scrolls internally, so it's always readable, while
              the large screenshot sits alongside in its own column. */}
          <div className="bug-thread-body">
            <div className="bug-thread-main-col">
              <div className="bug-messages">
                {thread.messages.map((m, i) => (
                  <TriageMessage key={i} m={m} author={thread.author} />
                ))}
              </div>

              <div className="bug-reply">
                <textarea
                  className="bug-input bug-textarea"
                  aria-label="Write a reply"
                  placeholder="Reply to the reporter…"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <div className="bug-actions">
                  <button
                    className="btn btn-primary"
                    onClick={send}
                    disabled={!reply.trim() || busy}
                  >
                    {busy ? "Sending…" : "Send reply"}
                  </button>
                </div>
              </div>
            </div>

            {shotUrl && (
              <div className="bug-shot-col">
                <div className="bug-shot">
                  <span className="bug-shot-cap">Screenshot</span>
                  <a
                    href={shotUrl}
                    target="_blank"
                    rel="noreferrer"
                    title="Open screenshot full size"
                  >
                    <img src={shotUrl} alt="Screenshot from the report" />
                  </a>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// The bug's folder id, shown so the admin can copy it and paste it to a triage tool out of
// band (it's the name of the on-disk report folder). Click to copy.
function BugIdChip({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be unavailable — the id is still visible to select by hand */
    }
  }
  return (
    <button
      type="button"
      className="bug-id-chip"
      onClick={copy}
      title="Copy bug ID"
      aria-label={`Copy bug ID ${id}`}
    >
      <span className="bug-id-text">{id}</span>
      <span className="bug-id-copy">{copied ? "✓ Copied" : "Copy"}</span>
    </button>
  );
}

// One message in the dev-side view — full fidelity, real sender names. The initial
// report carries the three form fields; replies carry `text`.
function TriageMessage({ m, author }: { m: BugThread["messages"][number]; author: string }) {
  const fromReporter = m.from === author;
  const isReport = m.text == null && (m.expected != null || m.actual != null || m.title != null);
  return (
    <div className={`bug-msg${fromReporter ? " dev" : " mine"}`}>
      <div className="bug-msg-meta">
        <span className="bug-msg-who">{m.from}</span>
        <span className="bug-msg-ts">{timeAgo(m.ts)}</span>
      </div>
      {isReport ? (
        <div className="bug-msg-report">
          {m.expected && (
            <p>
              <strong>Expected:</strong> {m.expected}
            </p>
          )}
          {m.actual && (
            <p>
              <strong>What happened:</strong> {m.actual}
            </p>
          )}
          {!m.expected && !m.actual && <p>{m.title}</p>}
        </div>
      ) : (
        <div className="bug-msg-text">{m.text}</div>
      )}
    </div>
  );
}
