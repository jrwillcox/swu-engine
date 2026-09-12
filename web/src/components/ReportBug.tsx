// Report-a-bug flow — a persistent HUD (rendered once in App, after the auth gate
// and OUTSIDE the screen switch) so "Report Bug" is reachable from every screen
// (start, explorer, game, replay). Clicking it CAPTURES first (screenshot +, when
// a game is live, the replay bundle / snapshot / pending decision), THEN opens the
// form pre-loaded with those artifacts — no hide/re-show dance.
//
// The screenshot is best-effort: a capture failure never blocks the report. The
// game bundle is attached only from a live game screen. See src/swu/web/bugs.py
// for the on-disk contract this feeds.
import { useCallback, useState } from "react";
import { motion } from "motion/react";
import { api, ApiError } from "../api/client";
import type { CreateBugRequest, Snapshot } from "../api/types";
import { Toast } from "./ui";

// Optional build marker baked in at build time (see vite define); omitted if unset.
const APP_VERSION = (import.meta.env.VITE_APP_VERSION as string | undefined) ?? undefined;

export type ScreenId = "game" | "start" | "explorer" | "decks" | "replay" | "inbox";

// Best-effort DOM → PNG data URL. Dynamically imports html-to-image so it stays
// out of the initial bundle, and skips the HUD chrome itself. Any failure → null.
async function captureScreenshot(): Promise<string | null> {
  try {
    const { toPng } = await import("html-to-image");
    return await toPng(document.body, {
      cacheBust: true,
      pixelRatio: 1,
      filter: (node) => !(node instanceof HTMLElement && node.dataset && "bugHud" in node.dataset),
    });
  } catch {
    return null; // never block the report on a failed screenshot
  }
}

interface Artifacts {
  screenshot_b64: string | null;
  game: Record<string, unknown> | null;
  context: Record<string, unknown>;
}

export function BugHud({
  screen,
  gameId,
  snapshot,
  lastAction,
  onOpenInbox,
  unreadCount,
}: {
  screen: ScreenId;
  gameId: string | null;
  /** The live game snapshot (only meaningful on the game screen). */
  snapshot: Snapshot | null;
  /** Last human-readable log line, for the report's `last_action` context. */
  lastAction?: string | null;
  /** Opens the reporter inbox (Stage 3). The envelope shows only when provided. */
  onOpenInbox?: () => void;
  /** Unread badge number for the envelope (driven by the poll in App). */
  unreadCount?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const inGame = screen === "game" && !!gameId && !!snapshot;

  // Capture-then-open: grab artifacts up front, then show the form.
  const openReport = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const screenshot_b64 = await captureScreenshot();

      const topPending = snapshot?.view.pending_decisions.slice(-1)[0];
      const context: Record<string, unknown> = { screen };
      if (APP_VERSION) context.app_version = APP_VERSION;
      if (inGame) {
        context.game_id = gameId;
        context.your_turn = snapshot!.awaiting === "human";
        if (topPending) context.pending_decision = topPending.kind;
      }
      if (lastAction) context.last_action = lastAction;

      let game: Record<string, unknown> | null = null;
      if (inGame) {
        // Replay bundle lets the admin scrub to the moment in the ReplayViewer
        // (Stage 4); the snapshot/pending decision pin the exact state.
        let replay: unknown = null;
        try {
          replay = await api.exportReplay(gameId!);
        } catch {
          /* best-effort — a missing bundle must not block the report */
        }
        game = {
          replay,
          snapshot: snapshot!.view,
          awaiting: snapshot!.awaiting,
          winner: snapshot!.winner,
          pending_decision: topPending?.kind ?? null,
        };
      }

      setArtifacts({ screenshot_b64, game, context });
    } finally {
      setBusy(false);
    }
  }, [busy, screen, gameId, snapshot, inGame, lastAction]);

  const showEnvelope = !!onOpenInbox;

  return (
    <>
      <div className="bug-hud" data-bug-hud="1">
        {showEnvelope && (
          <button
            className="bug-hud-btn envelope"
            onClick={onOpenInbox}
            title="Your messages"
            aria-label="Open your messages"
          >
            ✉
            {!!unreadCount && unreadCount > 0 && (
              <span className="bug-badge" aria-label={`${unreadCount} unread`}>
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>
        )}
        <button
          className="bug-hud-btn report"
          onClick={openReport}
          disabled={busy}
          title="Report a bug or request a feature"
        >
          {busy ? "Capturing…" : "🐞 Report"}
        </button>
      </div>

      {artifacts && (
        <ReportBugModal
          artifacts={artifacts}
          onClose={() => setArtifacts(null)}
          onSubmitted={() => {
            setArtifacts(null);
            setToast("Bug reported — thank you! You'll get a reply in your inbox.");
          }}
        />
      )}

      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </>
  );
}

function ReportBugModal({
  artifacts,
  onClose,
  onSubmitted,
}: {
  artifacts: Artifacts;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  // Bug (default) vs Feature Request. Carried on the report so the admin can triage it:
  // stored structured in context.report_type, and — since the triage list keys off
  // the title — a feature request also gets a "[Feature] " title prefix so it stands
  // out at a glance with no backend model change.
  const [reportType, setReportType] = useState<"bug" | "feature">("bug");
  const [title, setTitle] = useState("");
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isFeature = reportType === "feature";
  const canSubmit = title.trim().length > 0 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const cleanTitle = title.trim();
      const req: CreateBugRequest = {
        title: isFeature ? `[Feature] ${cleanTitle}` : cleanTitle,
        expected: expected.trim(),
        actual: actual.trim(),
        context: { ...artifacts.context, report_type: reportType },
        screenshot_b64: artifacts.screenshot_b64,
        game: artifacts.game,
      };
      await api.bugs.create(req);
      onSubmitted();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send the report — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scrim" onClick={onClose}>
      <motion.div
        className="modal panel bug-modal"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <h2>{isFeature ? "Request a feature" : "Report a bug"}</h2>
        <p className="bug-modal-sub">
          {isFeature ? "Tell us what you'd like to see." : "Tell us what went wrong."} We grabbed a
          screenshot
          {artifacts.game ? " and your game state" : ""} to help.
        </p>

        <label className="bug-field">
          <span>Type</span>
          <select
            className="bug-input"
            aria-label="Type"
            value={reportType}
            onChange={(e) => setReportType(e.target.value as "bug" | "feature")}
          >
            <option value="bug">Bug</option>
            <option value="feature">Feature Request</option>
          </select>
        </label>

        <label className="bug-field">
          <span>Title</span>
          <input
            className="bug-input"
            aria-label="Title"
            placeholder="A short summary (e.g. Boba Fett attack did nothing)"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>

        <label className="bug-field">
          <span>What did you expect to happen?</span>
          <textarea
            className="bug-input bug-textarea"
            aria-label="What did you expect to happen?"
            placeholder="What should have happened?"
            value={expected}
            onChange={(e) => setExpected(e.target.value)}
          />
        </label>

        <label className="bug-field">
          <span>What actually happened?</span>
          <textarea
            className="bug-input bug-textarea"
            aria-label="What actually happened?"
            placeholder="What did you see instead?"
            value={actual}
            onChange={(e) => setActual(e.target.value)}
          />
        </label>

        <div className="bug-attachments">
          <span className={artifacts.screenshot_b64 ? "on" : "off"}>
            {artifacts.screenshot_b64 ? "📷 Screenshot attached" : "📷 No screenshot"}
          </span>
          {artifacts.game && <span className="on">🎮 Game state attached</span>}
        </div>

        {error && <p className="bug-error">{error}</p>}

        <div className="bug-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={submit} disabled={!canSubmit}>
            {busy ? "Sending…" : "Send report"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
