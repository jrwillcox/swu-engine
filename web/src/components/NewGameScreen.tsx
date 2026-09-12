import { useEffect, useState } from "react";
import { api } from "../api/client";
import { AdminPanel } from "./AdminPanel";
import type { AuthUser } from "../game/auth";
import type {
  DeckChoice,
  Difficulty,
  // ImportReport, // HIDDEN (SWUDB import)
  NewGameRequest,
  ReplayResponse,
} from "../api/types";

// The chosen difficulty persists across sessions in localStorage. This is a real
// local web app (not a sandboxed artifact), so localStorage is appropriate here.
const DIFFICULTY_KEY = "swu.difficulty";

const DIFFICULTIES: { key: Difficulty; label: string }[] = [
  { key: "easy", label: "Easy" },
  { key: "normal", label: "Normal" },
  { key: "hard", label: "Hard" },
];

function loadDifficulty(): Difficulty {
  try {
    const v = localStorage.getItem(DIFFICULTY_KEY);
    if (v === "easy" || v === "normal" || v === "hard") return v;
  } catch {
    /* ignore */
  }
  return "normal";
}

export function NewGameScreen({
  onStart,
  busy,
  error,
  onLoad,
  onWatchReplay,
  onOpenExplorer,
  onOpenDecks,
  onOpenTutorial,
  user,
  onSignOut,
}: {
  onStart: (req: NewGameRequest) => void;
  busy: boolean;
  error: string | null;
  onLoad?: (slot: string) => void;
  onWatchReplay?: (replay: ReplayResponse) => void;
  onOpenExplorer?: () => void;
  onOpenDecks?: () => void;
  onOpenTutorial?: () => void;
  user?: AuthUser | null;
  onSignOut?: () => void;
}) {
  const [showAdmin, setShowAdmin] = useState(false);
  const [decks, setDecks] = useState<DeckChoice[]>([]);
  const [human, setHuman] = useState("luke");
  const [bot, setBot] = useState("vader");
  const [seed, setSeed] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>(loadDifficulty);
  const [loadError, setLoadError] = useState<string | null>(null);

  // HIDDEN 2026-09-01: Resume a saved game / Watch a replay / Import a deck (SWUDB) are hidden from the start screen. Uncomment every block marked HIDDEN to bring them back.
  // const [saves, setSaves] = useState<string[]>([]);
  // const [importText, setImportText] = useState("");
  // const [importName, setImportName] = useState("");
  // const [importReport, setImportReport] = useState<ImportReport | null>(null);
  // const [importErr, setImportErr] = useState<string | null>(null);
  // const [replayErr, setReplayErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .decks()
      .then((d) => {
        setDecks(d);
        if (d.length) {
          setHuman(d[0].key);
          setBot(d[1]?.key ?? d[0].key);
        }
      })
      .catch((e) => setLoadError(String(e)));
    // HIDDEN: saved-game list
    // if (onLoad) api.listSaves().then(setSaves).catch(() => setSaves([]));
  }, [onLoad]);

  // HIDDEN: handlers for the replay + SWUDB import tools
  // async function doImport() {
  //   setImportErr(null);
  //   setImportReport(null);
  //   let deck: unknown;
  //   try {
  //     deck = JSON.parse(importText);
  //   } catch {
  //     setImportErr("That isn't valid JSON. Paste a SWUDB decklist export.");
  //     return;
  //   }
  //   try {
  //     const report = await api.importSwudb({ deck, name: importName || "imported" });
  //     setImportReport(report);
  //   } catch (e) {
  //     setImportErr(String(e));
  //   }
  // }
  //
  // async function onReplayFile(file: File) {
  //   setReplayErr(null);
  //   try {
  //     const bundle = JSON.parse(await file.text());
  //     const replay = await api.replay(bundle);
  //     onWatchReplay?.(replay);
  //   } catch (e) {
  //     setReplayErr(`Could not load replay: ${e}`);
  //   }
  // }

  // Remember the player's difficulty choice for next time.
  useEffect(() => {
    try {
      localStorage.setItem(DIFFICULTY_KEY, difficulty);
    } catch {
      /* ignore */
    }
  }, [difficulty]);

  const start = () => {
    onStart({
      human: { kind: "human", deck: human },
      bot: { kind: "weighted_bot", deck: bot },
      seed: seed.trim() === "" ? null : Number(seed),
      difficulty,
    });
  };

  // Split the catalog into the two dropdown groups. A missing `kind` is an older
  // backend / back-compat → treat it as official.
  const official = decks.filter((d) => (d.kind ?? "official") === "official");
  const custom = decks.filter((d) => d.kind === "custom");

  // "Leader · Base" sub-label, when the backend supplied one (an empty or "—"
  // leader name means it couldn't resolve — omit it).
  const deckMeta = (key: string): string | null => {
    const d = decks.find((x) => x.key === key);
    if (!d || !d.leader_name || d.leader_name === "—") return null;
    return `${d.leader_name} · ${d.base_name}`;
  };

  const deckSelect = (title: string, label: string, value: string, set: (k: string) => void) => {
    const meta = deckMeta(value);
    return (
      <div className="deck-col">
        <h3>{title}</h3>
        <select
          className="deck-select"
          aria-label={label}
          value={value}
          onChange={(e) => set(e.target.value)}
        >
          <optgroup label="Official">
            {official.map((d) => (
              <option key={d.key} value={d.key} title={deckMeta(d.key) ?? undefined}>
                {d.label}
              </option>
            ))}
          </optgroup>
          {custom.length > 0 && (
            <optgroup label="Custom">
              {custom.map((d) => (
                <option key={d.key} value={d.key} title={deckMeta(d.key) ?? undefined}>
                  {d.label}
                </option>
              ))}
            </optgroup>
          )}
        </select>
        {meta && <div className="deck-col-meta meta">{meta}</div>}
      </div>
    );
  };

  return (
    <div className="start-screen">
      {user && (
        <div className="account-bar">
          <span className="meta">Signed in as {user.username}</span>
          {user.admin && (
            <button className="btn btn-ghost" onClick={() => setShowAdmin(true)}>
              Manage users
            </button>
          )}
          {onSignOut && (
            <button className="btn btn-ghost" onClick={onSignOut}>
              Sign out
            </button>
          )}
        </div>
      )}
      {showAdmin && (
        <AdminPanel onClose={() => setShowAdmin(false)} onWatchReplay={onWatchReplay} />
      )}

      <div className="start-card panel">
        <h1>Star Wars: Unlimited</h1>
        <div className="sub">Pick a deck for each side and a difficulty level.</div>

        {(onOpenExplorer || (onOpenDecks && user) || onOpenTutorial) && (
          <div className="start-row" style={{ marginTop: 0 }}>
            {onOpenExplorer && (
              <button className="btn btn-ghost" onClick={onOpenExplorer}>
                🔍 Card Explorer
              </button>
            )}
            {onOpenDecks && user && (
              <button className="btn btn-ghost" onClick={onOpenDecks}>
                🃏 My Decks
              </button>
            )}
            {onOpenTutorial && (
              <button className="btn btn-ghost" onClick={onOpenTutorial}>
                📖 Tutorial
              </button>
            )}
          </div>
        )}

        {loadError && (
          <p style={{ color: "var(--danger)" }}>
            Could not reach the backend ({loadError}). Is it running on :8000?
          </p>
        )}

        <div className="deck-pick">
          {deckSelect("You", "Your deck", human, setHuman)}
          {deckSelect("Opponent (bot)", "Opponent deck", bot, setBot)}
        </div>

        <div className="difficulty-pick">
          <h3>Difficulty</h3>
          <select
            className="difficulty-select"
            aria-label="Difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as Difficulty)}
          >
            {DIFFICULTIES.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        <div className="start-row">
          <label className="meta" style={{ color: "var(--ink-dim)" }}>
            Seed (optional)
          </label>
          <input
            className="seed-input"
            placeholder="random"
            value={seed}
            onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ""))}
          />
          <span className="spacer" style={{ flex: 1 }} />
          <button className="btn btn-primary" disabled={busy || decks.length === 0} onClick={start}>
            {busy ? "Dealing…" : "Start game"}
          </button>
        </div>

        {error && <p style={{ color: "var(--danger)", marginTop: 14 }}>{error}</p>}
      </div>

      {/* HIDDEN 2026-09-01: start-screen tools (Resume a saved game / Watch a replay /
          Import a deck (SWUDB)). Uncomment this block plus the HIDDEN state, effect
          line and handlers above to bring them back.
      {(onLoad || onWatchReplay) && (
        <div className="start-tools">
          {onLoad && (
            <div className="tool-card panel">
              <h3>Resume a saved game</h3>
              {saves.length === 0 ? (
                <p className="meta">No saved games yet — use 💾 during a game.</p>
              ) : (
                <div className="save-list">
                  {saves.map((s) => (
                    <button key={s} className="btn save-slot" onClick={() => onLoad(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {onWatchReplay && (
            <div className="tool-card panel">
              <h3>Watch a replay</h3>
              <p className="meta">Load a replay file exported from a finished game.</p>
              <input
                type="file"
                accept="application/json,.json"
                aria-label="Replay file"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onReplayFile(f);
                }}
              />
              {replayErr && <p style={{ color: "var(--danger)" }}>{replayErr}</p>}
            </div>
          )}

          <div className="tool-card panel">
            <h3>Import a deck (SWUDB)</h3>
            <p className="meta">
              Paste a SWUDB decklist export to check which cards are playable yet.
            </p>
            <input
              className="seed-input"
              placeholder="Name (optional)"
              aria-label="Import name"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
            />
            <textarea
              className="import-text"
              aria-label="SWUDB decklist JSON"
              placeholder='{"leader": {"id": "SHD_13"}, "base": {...}, "deck": [...]}'
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={4}
            />
            <button className="btn" disabled={!importText.trim()} onClick={doImport}>
              Check deck
            </button>
            {importErr && <p style={{ color: "var(--danger)" }}>{importErr}</p>}
            {importReport && (
              <div className="import-report">
                <div className={importReport.ok ? "ok" : "warn"}>
                  {importReport.playable_cards}/{importReport.total_cards} cards playable
                  {importReport.ok ? " — fully ready!" : ""}
                </div>
                {!importReport.legal && (
                  <div className="warn">Deck legality: {importReport.errors.join("; ")}</div>
                )}
                {importReport.unimplemented.length > 0 && (
                  <details>
                    <summary>
                      {importReport.unimplemented.length} card(s) not yet playable
                    </summary>
                    <ul>
                      {importReport.unimplemented.map((u) => (
                        <li key={u.id}>
                          {u.name} ({u.id}) — {u.label}
                          {u.count > 1 ? ` ×${u.count}` : ""}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {importReport.planner_hint && (
                  <code className="planner-hint">{importReport.planner_hint}</code>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      */}
    </div>
  );
}
