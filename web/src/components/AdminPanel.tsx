// Admin-only screen. Rendered as a modal overlay with two tabs:
//   • Bug triage  — the primary surface (all users' reports, bucketed) — Stage 4
//   • Manage users — reset another user's password
// The triage tab can open the reported game in the ReplayViewer, which takes over
// the whole screen (via onWatchReplay threaded down from App).
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ReplayResponse, UserSummary } from "../api/types";
import { BugTriage } from "./BugTriage";

type Tab = "bugs" | "users";

export function AdminPanel({
  onClose,
  onWatchReplay,
}: {
  onClose: () => void;
  onWatchReplay?: (replay: ReplayResponse) => void;
}) {
  const [tab, setTab] = useState<Tab>("bugs");

  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal panel admin-panel" onClick={(e) => e.stopPropagation()}>
        <div className="bug-inbox-head">
          <h2>Admin</h2>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close admin">
            ✕
          </button>
        </div>

        <div className="bug-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === "bugs"}
            className={tab === "bugs" ? "active" : ""}
            onClick={() => setTab("bugs")}
          >
            Bug triage
          </button>
          <button
            role="tab"
            aria-selected={tab === "users"}
            className={tab === "users" ? "active" : ""}
            onClick={() => setTab("users")}
          >
            Manage users
          </button>
        </div>

        {tab === "bugs" ? <BugTriage onWatchReplay={onWatchReplay} /> : <ManageUsers />}
      </div>
    </div>
  );
}

function ManageUsers() {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const msg = (e: unknown) =>
    e instanceof ApiError ? e.message : "Something went wrong — try again.";

  useEffect(() => {
    api.auth
      .users()
      .then(setUsers)
      .catch((e) => setError(msg(e)));
  }, []);

  async function reset() {
    if (!selected || !password) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await api.auth.reset(selected, password);
      setDone(`${selected}'s password was reset.`);
      setPassword("");
      setSelected(null);
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p className="meta">Reset a player's password.</p>

      <div className="save-list" style={{ marginTop: 10 }}>
        {users.map((u) => (
          <button
            key={u.username}
            className={`btn save-slot ${selected === u.username ? "sel" : ""}`}
            disabled={!u.registered}
            title={u.registered ? "" : "Hasn't signed up yet"}
            onClick={() => {
              setSelected(u.username);
              setDone(null);
            }}
          >
            {u.username}
            {u.admin ? " (admin)" : ""}
            {u.registered ? "" : " — not set up"}
          </button>
        ))}
      </div>

      {selected && (
        <div className="start-row" style={{ marginTop: 14 }}>
          <input
            className="seed-input"
            style={{ flex: 1 }}
            type="password"
            aria-label={`New password for ${selected}`}
            placeholder={`New password for ${selected}`}
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && reset()}
          />
          <button className="btn btn-primary" disabled={busy || !password} onClick={reset}>
            Reset
          </button>
        </div>
      )}

      {done && <p style={{ color: "var(--ok, var(--ink))", marginTop: 12 }}>{done}</p>}
      {error && <p style={{ color: "var(--danger)", marginTop: 12 }}>{error}</p>}
    </>
  );
}
