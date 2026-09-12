// Screen chrome: the pieces framing a game rather than participating in it.
import { useEffect, useState, type ReactNode } from "react";
import { motion } from "motion/react";
import type { PlayerViewModel } from "../../api/types";
import type { LogLine } from "../../game/format";

// Full-screen toggle. Uses the standard Fullscreen API (whole document), so it
// works on Windows/desktop browsers and Android Chrome. It feature-detects and
// renders nothing on iOS Safari, where the API is unavailable for page content
// (there the way to go full-screen is Add to Home Screen / PWA standalone).
// Browsers only allow requestFullscreen() from a user gesture, so this is a
// button — there is no way to auto-trigger it on load.
export function FullscreenButton() {
  const [supported] = useState(
    () =>
      typeof document !== "undefined" &&
      typeof document.documentElement.requestFullscreen === "function",
  );
  const [isFull, setIsFull] = useState(false);
  useEffect(() => {
    if (!supported) return;
    const onChange = () => setIsFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, [supported]);
  if (!supported) return null;
  const toggle = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen?.();
    } else {
      void document.documentElement.requestFullscreen?.().catch(() => {});
    }
  };
  return (
    <button
      className="btn btn-ghost"
      onClick={toggle}
      title={isFull ? "Exit full screen" : "Full screen"}
      aria-label={isFull ? "Exit full screen" : "Full screen"}
    >
      <span className={isFull ? "fs-icon on" : "fs-icon"}>⛶</span>
    </button>
  );
}
// Single top bar: status pills (left), the action prompt + buttons (middle,
// passed as children), and the turn flag + settings (right).
export function Hud({
  view,
  awaiting,
  onSettings,
  onSave,
  onToggleLog,
  children,
}: {
  view: PlayerViewModel;
  awaiting: string;
  onSettings: () => void;
  onSave?: () => void;
  onToggleLog?: () => void;
  children?: ReactNode;
}) {
  const yourTurn = awaiting === "human";
  const initYou = view.initiative_holder_id === "human";
  return (
    <div className="topbar panel">
      <div className="topbar-pills">
        <span className="pill phase">{view.phase.replace(/_/g, " ")}</span>
        <span className="pill">Round {view.round_number}</span>
        <span className={`pill init`}>◈ Init: {initYou ? "You" : "Opp"}</span>
      </div>
      <div className="topbar-mid">{children}</div>
      <span className={`turn-flag ${yourTurn ? "you" : "foe"}`}>
        {awaiting === "terminal" ? "Game over" : yourTurn ? "Your turn" : "Opponent"}
      </span>
      {onSave && awaiting !== "terminal" && (
        <button className="btn btn-ghost" onClick={onSave} title="Save game">
          💾
        </button>
      )}
      {onToggleLog && (
        <button className="btn btn-ghost log-toggle" onClick={onToggleLog} title="Battle log">
          📜
        </button>
      )}
      <FullscreenButton />
      <button className="btn btn-ghost" onClick={onSettings} title="Settings">
        ⚙
      </button>
    </div>
  );
}
// Portrait hint for touch devices. Rendered always; CSS shows it only when a
// coarse-pointer device is held in portrait, so the board never appears cramped.
export function RotateHint() {
  return (
    <div className="rotate-hint" role="img" aria-label="Rotate your device to landscape">
      <div className="rotate-hint-icon">⟳</div>
      <h2>Rotate to landscape</h2>
      <p>This game plays best with your iPad turned sideways.</p>
    </div>
  );
}
// A brief auto-dismissing confirmation (e.g. "Game saved"). Cosmetic only.
export function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <motion.div
      className="toast"
      role="status"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
    >
      {message}
    </motion.div>
  );
}
// B2 pacing gate: when a new round has begun and control is back with the human,
// hold the board behind a dismissable "start" card so a fast burst of opponent
// plays + regroup doesn't blow past unnoticed. Click anywhere or press Space.
export function TurnGate({ round, onStart }: { round: number; onStart: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        onStart();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onStart]);
  return (
    <div className="scrim turn-gate" onClick={onStart}>
      <motion.div
        className="modal panel turn-gate-card"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.92, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <div className="turn-gate-round">Round {round}</div>
        <h2>Round {round} begins</h2>
        <p className="turn-gate-prompt">Take a moment, then start when you're ready.</p>
        <button className="btn btn-primary" onClick={onStart}>
          Start round ▶
        </button>
      </motion.div>
    </div>
  );
}
export function LogPanel({ log }: { log: LogLine[] }) {
  // Newest first: the most recent action sits just under the header, so the
  // current state of play is visible without scrolling; scroll down for history.
  const recent = log.slice(-60).reverse();
  return (
    <div className="log-panel panel scroll">
      <h4>Battle Log</h4>
      {log.length === 0 && <div className="log-line">Awaiting first move…</div>}
      {recent.map((l, i) =>
        l.divider ? (
          <div key={log.length - i} className="log-divider">
            <span>{l.text}</span>
          </div>
        ) : (
          <div key={log.length - i} className={`log-line ${l.tone}`}>
            {l.text}
          </div>
        ),
      )}
    </div>
  );
}
export function EndScreen({
  won,
  onPlayAgain,
  onExportReplay,
}: {
  won: boolean;
  onPlayAgain: () => void;
  onExportReplay?: () => void;
}) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), 400);
    return () => clearTimeout(t);
  }, []);
  if (!show) return null;
  return (
    <motion.div className="end-screen" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <motion.div
        className={`end-card panel ${won ? "win" : "lose"}`}
        initial={{ scale: 0.7, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
      >
        <h1>{won ? "Victory" : "Defeat"}</h1>
        <p>{won ? "Your base held the line." : "Your base was destroyed."}</p>
        <div className="end-actions">
          {onExportReplay && (
            <button className="btn btn-ghost" onClick={onExportReplay}>
              Export replay
            </button>
          )}
          <button className="btn btn-primary" onClick={onPlayAgain}>
            Play again
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
