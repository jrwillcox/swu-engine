import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useGame } from "./game/useGame";
import { LogPanel, RotateHint } from "./components/ui";
import { NewGameScreen } from "./components/NewGameScreen";
import { CardExplorer } from "./components/CardExplorer";
import { DeckManager } from "./components/DeckManager";
import { Table } from "./components/Table";
import { TutorialScreen } from "./components/tutorial/TutorialScreen";
import { ReplayViewer } from "./components/ReplayViewer";
import { LoginScreen } from "./components/LoginScreen";
import { BugHud, type ScreenId } from "./components/ReportBug";
import { BugInbox } from "./components/BugInbox";
import { api } from "./api/client";
import { useUser } from "./game/auth";
import type { ReplayResponse } from "./api/types";

// How often the HUD envelope badge re-polls the unread count (plan default).
const UNREAD_POLL_MS = 20_000;

export default function App() {
  const auth = useUser();
  const game = useGame();
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [explorer, setExplorer] = useState(false);
  const [deckManager, setDeckManager] = useState(false);
  const [tutorial, setTutorial] = useState(false);
  // Touch/narrow layouts: the battle log slides in as a drawer (toggled from the
  // HUD). On a wide desktop the same element is just the fixed right column and
  // this open/closed state has no visible effect (see .log-rail media queries).
  const [logOpen, setLogOpen] = useState(false);
  // Reporter inbox (Stage 3): the HUD envelope opens it; a badge shows unread.
  const [inboxOpen, setInboxOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  const signedIn = auth.ready && !!auth.user;

  // Drive the HUD badge: poll the unread count on mount + every 20s while signed
  // in, and refresh on demand (after the inbox marks things read / a new report).
  const refreshUnread = useCallback(() => {
    if (!signedIn) return;
    api.bugs
      .unreadCount()
      .then(setUnread)
      .catch(() => {
        /* best-effort — a failed poll just leaves the last count */
      });
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    refreshUnread();
    const t = setInterval(refreshUnread, UNREAD_POLL_MS);
    return () => clearInterval(t);
  }, [signedIn, refreshUnread]);

  // Login gate (the front door). Wait for the remembered token to validate to
  // avoid a login flash, then require a signed-in user before anything renders.
  if (!auth.ready) return null;
  if (!auth.user) return <LoginScreen />;

  // Resolve the current screen + its content once, so the persistent Report-Bug
  // HUD can render on top of ALL of them (outside this switch) and know which
  // screen the report was filed from.
  let screen: ScreenId;
  let content: ReactNode;
  if (replay) {
    // Watching a recorded replay takes over the screen until the viewer exits.
    screen = "replay";
    content = <ReplayViewer replay={replay} onExit={() => setReplay(null)} />;
  } else if (explorer && !game.snapshot) {
    // The card explorer is reachable from the start screen and takes over.
    screen = "explorer";
    content = <CardExplorer onBack={() => setExplorer(false)} />;
  } else if (deckManager && !game.snapshot) {
    // The Deck Manager (custom decks) is reachable from the start screen.
    screen = "decks";
    content = <DeckManager onBack={() => setDeckManager(false)} />;
  } else if (tutorial && !game.snapshot) {
    // The interactive "How to Play" tutorial takes over the screen.
    screen = "start";
    content = <TutorialScreen onExit={() => setTutorial(false)} />;
  } else if (!game.snapshot) {
    screen = "start";
    content = (
      <NewGameScreen
        onStart={game.newGame}
        busy={game.busy}
        error={game.error}
        onLoad={game.loadSaved}
        onWatchReplay={setReplay}
        onOpenExplorer={() => setExplorer(true)}
        onOpenDecks={() => setDeckManager(true)}
        onOpenTutorial={() => setTutorial(true)}
        user={auth.user}
        onSignOut={auth.logout}
      />
    );
  } else {
    screen = "game";
    content = (
      <div className="app-shell">
        <Table game={game} onToggleLog={() => setLogOpen((o) => !o)} />
        {logOpen && <div className="log-backdrop" onClick={() => setLogOpen(false)} />}
        <aside className={`log-rail ${logOpen ? "open" : ""}`}>
          <LogPanel log={game.log} />
        </aside>
        <RotateHint />
      </div>
    );
  }

  const lastAction = game.log.length ? game.log[game.log.length - 1].text : null;

  return (
    <>
      {content}
      {!tutorial && (
        <BugHud
          screen={screen}
          gameId={game.gameId}
          snapshot={screen === "game" ? game.snapshot : null}
          lastAction={lastAction}
          onOpenInbox={() => setInboxOpen(true)}
          unreadCount={unread}
        />
      )}
      {inboxOpen && (
        <BugInbox
          username={auth.user.username}
          onClose={() => setInboxOpen(false)}
          onChanged={refreshUnread}
        />
      )}
    </>
  );
}
