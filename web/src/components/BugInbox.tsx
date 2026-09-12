// Reporter inbox (reporter-facing) — the two-way messaging surface reachable from the
// HUD envelope. A reporter sees only their own threads (the backend scopes by the
// bearer-token username); replies from the dev side render as "Dev Team" (the
// individual helper's identity is not surfaced) and their own messages as "You".
//
// Two views: a thread LIST (with Active / Archived tabs, read/unread dots, a
// status chip, and a "Dev Team replied" highlight for unread) and a THREAD view
// (messages, the screenshot, a text-only reply box). Opening a thread marks its
// messages read. The Archive toggle flips the cosmetic `reporter_archived` flag — the
// reporter tidies their own inbox without touching the admin's triage view.
//
// See src/swu/web/bugs.py for the on-disk contract behind all of this.
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { api, ApiError } from "../api/client";
import type { BugMessage, BugSummary, BugThread } from "../api/types";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  new: { label: "New", cls: "new" },
  needs_info: { label: "Needs your reply", cls: "needs" },
  investigating: { label: "Investigating", cls: "investigating" },
  resolved: { label: "Resolved", cls: "resolved" },
};

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, cls: "new" };
}

// Friendly relative age from an ISO-8601 (UTC "Z") timestamp. Falls back to the
// raw string if it can't be parsed, so a bad value never blanks the row.
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

// A message that isn't the reporter's own is the "Dev Team" (hides the helper).
function senderLabel(from: string, username: string): string {
  return from === username ? "You" : "Dev Team";
}

export function BugInbox({
  username,
  onClose,
  onChanged,
}: {
  username: string;
  onClose: () => void;
  /** Called after any change that can move the unread count (App re-polls). */
  onChanged?: () => void;
}) {
  const [summaries, setSummaries] = useState<BugSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"active" | "archived">("active");
  const [selected, setSelected] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setSummaries(await api.bugs.list());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load your messages.");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // A change inside a thread (read/reply/archive) refreshes the list here AND
  // bubbles up so the HUD badge re-polls.
  const bubble = useCallback(() => {
    void reload();
    onChanged?.();
  }, [reload, onChanged]);

  const active = (summaries ?? []).filter((s) => !s.reporter_archived);
  const archived = (summaries ?? []).filter((s) => s.reporter_archived);
  const shown = tab === "active" ? active : archived;

  return (
    <div className="scrim" onClick={onClose}>
      <motion.div
        className="modal panel bug-inbox"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        {selected ? (
          <ThreadView
            id={selected}
            username={username}
            onBack={() => setSelected(null)}
            onChanged={bubble}
          />
        ) : (
          <>
            <div className="bug-inbox-head">
              <h2>Your messages</h2>
              <button className="btn btn-ghost" onClick={onClose} aria-label="Close inbox">
                ✕
              </button>
            </div>

            <div className="bug-tabs" role="tablist">
              <button
                role="tab"
                aria-selected={tab === "active"}
                className={tab === "active" ? "active" : ""}
                onClick={() => setTab("active")}
              >
                Inbox{active.length ? ` (${active.length})` : ""}
              </button>
              <button
                role="tab"
                aria-selected={tab === "archived"}
                className={tab === "archived" ? "active" : ""}
                onClick={() => setTab("archived")}
              >
                Archived{archived.length ? ` (${archived.length})` : ""}
              </button>
            </div>

            {error && <p className="bug-error">{error}</p>}

            {summaries === null ? (
              <p className="bug-inbox-empty">Loading…</p>
            ) : shown.length === 0 ? (
              <p className="bug-inbox-empty">
                {tab === "active"
                  ? "No messages yet. Reports you send show up here."
                  : "Nothing archived."}
              </p>
            ) : (
              <ul className="bug-thread-list">
                {shown.map((s) => (
                  <ThreadRow key={s.id} s={s} onOpen={() => setSelected(s.id)} />
                ))}
              </ul>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
}

function ThreadRow({ s, onOpen }: { s: BugSummary; onOpen: () => void }) {
  const meta = statusMeta(s.status);
  // A reply the reporter hasn't read yet, from the dev side → celebrate it.
  const devReplied = s.unread > 0 && s.last_from !== s.author;
  const resolved = s.status === "resolved";
  return (
    <li>
      <button
        className={`bug-thread-row${s.unread > 0 ? " unread" : ""}${resolved ? " resolved" : ""}`}
        onClick={onOpen}
      >
        <span className={`bug-dot${s.unread > 0 ? " on" : ""}`} aria-hidden="true" />
        <span className="bug-thread-main">
          <span className="bug-thread-title">{s.title || "(untitled)"}</span>
          <span className="bug-thread-sub">
            <span className={`bug-status ${meta.cls}`}>{meta.label}</span>
            {devReplied && <span className="bug-flag">Dev Team replied</span>}
            {resolved && !devReplied && <span className="bug-flag done">Resolved 🎉</span>}
            <span className="bug-thread-age">{timeAgo(s.updated || s.created)}</span>
          </span>
        </span>
      </button>
    </li>
  );
}

function ThreadView({
  id,
  username,
  onBack,
  onChanged,
}: {
  id: string;
  username: string;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [thread, setThread] = useState<BugThread | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [shotUrl, setShotUrl] = useState<string | null>(null);

  // Load the thread and mark it read on open. mark_read returns the updated
  // thread, so we show that (all messages now read) and let the badge re-poll.
  useEffect(() => {
    let cancelled = false;
    setThread(null);
    api.bugs
      .markRead(id)
      .then((t) => {
        if (cancelled) return;
        setThread(t);
        onChanged();
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Couldn't open this message.");
      });
    return () => {
      cancelled = true;
    };
    // onChanged is stable enough; opening is keyed on the thread id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  async function send() {
    const text = reply.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    try {
      const t = await api.bugs.reply(id, text);
      setThread(t);
      setReply("");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send your reply — try again.");
    } finally {
      setSending(false);
    }
  }

  async function toggleArchive() {
    if (!thread) return;
    try {
      const t = await api.bugs.setArchived(id, !thread.reporter_archived);
      setThread(t);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update — try again.");
    }
  }

  const meta = thread ? statusMeta(thread.status) : null;

  return (
    <div className="bug-thread-view">
      <div className="bug-inbox-head">
        <button className="btn btn-ghost" onClick={onBack} aria-label="Back to inbox">
          ← Back
        </button>
        {thread && (
          <button className="btn btn-ghost bug-archive-btn" onClick={toggleArchive}>
            {thread.reporter_archived ? "Unarchive" : "Archive"}
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
          </div>

          {thread.status === "resolved" && (
            <div className="bug-resolved-banner">
              🎉 The Dev Team marked this fixed. Thanks for the great report!
            </div>
          )}

          <div className="bug-thread-body">
            <div className="bug-thread-main-col">
              <div className="bug-messages">
                {thread.messages.map((m, i) => (
                  <MessageBubble key={i} m={m} username={username} />
                ))}
              </div>

              <div className="bug-reply">
                <textarea
                  className="bug-input bug-textarea"
                  aria-label="Write a reply"
                  placeholder="Write a reply to the Dev Team…"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <div className="bug-actions">
                  <button
                    className="btn btn-primary"
                    onClick={send}
                    disabled={!reply.trim() || sending}
                  >
                    {sending ? "Sending…" : "Send reply"}
                  </button>
                </div>
              </div>
            </div>

            {shotUrl && (
              <div className="bug-shot-col">
                <div className="bug-shot">
                  <span className="bug-shot-cap">Screenshot</span>
                  <img src={shotUrl} alt="Screenshot from the report" />
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// One message. The initial report carries the three form fields; replies carry
// `text`. Own messages are "You", everything else is "Dev Team".
function MessageBubble({ m, username }: { m: BugMessage; username: string }) {
  const mine = m.from === username;
  const isReport = m.text == null && (m.expected != null || m.actual != null || m.title != null);
  return (
    <div className={`bug-msg${mine ? " mine" : " dev"}`}>
      <div className="bug-msg-meta">
        <span className="bug-msg-who">{senderLabel(m.from, username)}</span>
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
