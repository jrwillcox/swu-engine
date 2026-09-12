// useGame — owns the live Snapshot and the event-animation queue.
//
// Model (per the brief): the UI animates the event stream, it does not diff
// state. Each engine step returns the post-step truth (`view`) plus the events
// it produced. We render the truth immediately (Motion handles enter/exit/move
// animations) and play the events through an interruptible queue that drives
// decorative effects and locks input until it drains.
//
// The frontend knows no rules: it only POSTs the action_id the backend assigned
// and chains a bot `advance` after the human's events have finished animating.
import { useCallback, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { GameEvent, NewGameRequest, Snapshot } from "../api/types";
import { formatEvent, type LogLine } from "./format";
import { useSettings } from "./settings";

// Base per-event display durations (ms), before the speed factor.
const DURATIONS: Record<string, number> = {
  AttackDeclared: 460,
  DamageDealt: 520,
  OverwhelmDamage: 520,
  UnitDefeated: 640,
  ShieldDefeated: 440,
  TokenAttached: 420,
  CardPlayed: 360,
  UnitEntersPlay: 360,
  UpgradePlayed: 360,
  LeaderDeployed: 420,
  LeaderReturnedToBase: 420,
  RestoreHealing: 360,
};
const DEFAULT_DURATION = 150;

export interface ActiveEvent {
  ev: GameEvent;
  key: number;
}

export interface Game {
  snapshot: Snapshot | null;
  busy: boolean;
  error: string | null;
  /** Event currently being shown by the effects layer (null when idle). */
  active: ActiveEvent | null;
  /** True while the animation queue is draining — input is locked. */
  playing: boolean;
  /** Recently-defeated instance ids, so exiting cards pick the defeat variant. */
  defeated: Set<string>;
  /** Human-readable rolling log built from the event stream. */
  log: LogLine[];
  locked: boolean;
  gameId: string | null;
  /** Round number to "start" when a new round has begun, else null (B2 gate). */
  turnGate: number | null;
  newGame: (req: NewGameRequest) => Promise<void>;
  loadSaved: (slot: string) => Promise<void>;
  save: (slot?: string) => Promise<string | null>;
  act: (actionId: string) => Promise<void>;
  /** Commit a set of hand cards to resources in one confirmed batch (two-stage). */
  resourceCards: (instanceIds: string[]) => Promise<void>;
  dismissTurnGate: () => void;
  skipAnimations: () => void;
  reset: () => void;
}

export function useGame(): Game {
  const { factor } = useSettings();
  const factorRef = useRef(factor);
  factorRef.current = factor;

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<ActiveEvent | null>(null);
  const [playing, setPlaying] = useState(false);
  const [defeated, setDefeated] = useState<Set<string>>(new Set());
  const [log, setLog] = useState<LogLine[]>([]);
  const [turnGate, setTurnGate] = useState<number | null>(null);

  const queue = useRef<GameEvent[]>([]);
  const running = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const keyCounter = useRef(0);
  const idleResolvers = useRef<Array<() => void>>([]);
  // Resolves when the human dismisses the round-start gate, letting the bot
  // loop proceed into the new round's plays.
  const gateResolver = useRef<(() => void) | null>(null);
  const gameId = useRef<string | null>(null);
  // Latest snapshot, readable synchronously (state lags during async chains).
  const snapshotRef = useRef<Snapshot | null>(null);
  // Highest round we've already "started", so the B2 gate fires once per round.
  const lastRoundRef = useRef(0);

  // Single write point for the live snapshot — keeps the synchronous ref in sync.
  const commit = useCallback((s: Snapshot | null) => {
    snapshotRef.current = s;
    setSnapshot(s);
  }, []);

  const resolveIdle = useCallback(() => {
    const rs = idleResolvers.current;
    idleResolvers.current = [];
    rs.forEach((r) => r());
  }, []);

  const durationFor = useCallback((ev: GameEvent) => {
    const base = DURATIONS[ev.type] ?? DEFAULT_DURATION;
    return Math.max(1, Math.round(base * factorRef.current));
  }, []);

  const pump = useCallback(() => {
    const next = queue.current.shift();
    if (!next) {
      running.current = false;
      setActive(null);
      setPlaying(false);
      resolveIdle();
      return;
    }
    if (next.type === "UnitDefeated") {
      const id = next.data.instance_id as string;
      setDefeated((prev) => new Set(prev).add(id));
    }
    setActive({ ev: next, key: keyCounter.current++ });
    timer.current = window.setTimeout(pump, durationFor(next));
  }, [durationFor, resolveIdle]);

  const enqueue = useCallback(
    (events: GameEvent[]) => {
      if (!events.length) return;
      const lines = events.map(formatEvent).filter((l): l is LogLine => l !== null);
      if (lines.length) setLog((prev) => [...prev, ...lines].slice(-200));
      queue.current.push(...events);
      if (!running.current) {
        running.current = true;
        setPlaying(true);
        pump();
      }
    },
    [pump],
  );

  const whenIdle = useCallback((): Promise<void> => {
    if (!running.current) return Promise.resolve();
    return new Promise((resolve) => idleResolvers.current.push(resolve));
  }, []);

  // When `snap` is the first state of a round we haven't started yet, hold the
  // board behind the round-start gate. We let everything up to the round
  // boundary finish animating, then block until the human dismisses — BEFORE
  // any of the new round's events animate. Crucially this is keyed off the
  // round number, not whose turn it is: when the opponent holds initiative the
  // bot plays first in the new round, so gating "once control is back on the
  // human" would let the bot's opening plays slip past unnoticed.
  const gateIfNewRound = useCallback(
    async (snap: Snapshot): Promise<void> => {
      if (snap.view.round_number <= lastRoundRef.current) return;
      lastRoundRef.current = snap.view.round_number;
      if (snap.awaiting === "terminal") return;
      await whenIdle();
      await new Promise<void>((resolve) => {
        gateResolver.current = resolve;
        setTurnGate(snap.view.round_number);
      });
    },
    [whenIdle],
  );

  const skipAnimations = useCallback(() => {
    queue.current = [];
    if (timer.current) window.clearTimeout(timer.current);
    running.current = false;
    setActive(null);
    setPlaying(false);
    resolveIdle();
  }, [resolveIdle]);

  // Drive consecutive bot turns after a human action's events have animated.
  // Returns the final snapshot. When `gate` is set, raises the new-round gate
  // at the round boundary — before the new round's first action animates.
  const continueBot = useCallback(
    async (snap: Snapshot, gate = false): Promise<Snapshot> => {
      let cur = snap;
      // The round may have already rolled over in the action that produced
      // `snap`: when the bot holds initiative, the human's own regroup choice
      // ends the round, so we must gate here before driving the bot's plays.
      if (gate) await gateIfNewRound(cur);
      while (cur.awaiting === "bot" && gameId.current) {
        await whenIdle();
        const r = await api.advance(gameId.current);
        commit(r);
        enqueue(r.events);
        cur = r;
        // Or it rolls over inside the loop: when the human holds initiative the
        // bot's regroup choice ends the round and control returns to the human.
        if (gate) await gateIfNewRound(cur);
      }
      return cur;
    },
    [commit, enqueue, gateIfNewRound, whenIdle],
  );

  const newGame = useCallback(
    async (req: NewGameRequest) => {
      setBusy(true);
      setError(null);
      skipAnimations();
      setDefeated(new Set());
      setTurnGate(null);
      gateResolver.current = null;
      try {
        const res = await api.newGame(req);
        gameId.current = res.game_id;
        setLog([]);
        commit(res);
        const final = await continueBot(res);
        // Don't gate the opening round — start counting from wherever we land.
        lastRoundRef.current = final.view.round_number;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [commit, continueBot, skipAnimations],
  );

  const loadSaved = useCallback(
    async (slot: string) => {
      setBusy(true);
      setError(null);
      skipAnimations();
      setDefeated(new Set());
      setTurnGate(null);
      gateResolver.current = null;
      try {
        const res = await api.loadGame(slot);
        gameId.current = res.game_id;
        setLog([]);
        commit(res);
        const final = await continueBot(res);
        lastRoundRef.current = final.view.round_number;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [commit, continueBot, skipAnimations],
  );

  const save = useCallback(async (slot?: string): Promise<string | null> => {
    if (!gameId.current) return null;
    try {
      const res = await api.saveGame(gameId.current, slot);
      return res.slot;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, []);

  const act = useCallback(
    async (actionId: string) => {
      if (!gameId.current || busy) return;
      setBusy(true);
      setError(null);
      try {
        const res = await api.applyAction(gameId.current, actionId);
        commit(res);
        enqueue(res.events);
        await continueBot(res, true);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        // Resync so the UI never sits on a state the server rejected.
        if (gameId.current) {
          try {
            commit(await api.state(gameId.current));
          } catch {
            /* ignore */
          }
        }
      } finally {
        setBusy(false);
      }
    },
    [busy, commit, continueBot, enqueue],
  );

  // Two-stage resourcing: the human stages cards locally, then confirms. The
  // engine takes one ResourceCard at a time and re-issues action ids after each,
  // so we resolve every staged card's *current* action id from the freshest
  // snapshot before dispatching it.
  const resourceCards = useCallback(
    async (instanceIds: string[]) => {
      if (!gameId.current || busy || !instanceIds.length) return;
      setBusy(true);
      setError(null);
      try {
        let cur = snapshotRef.current;
        for (const id of instanceIds) {
          const a = cur?.actions.find(
            (x) => x.kind === "ResourceCard" && x.params.instance_id === id,
          );
          if (!a) continue; // already resourced or no longer legal — skip
          const res = await api.applyAction(gameId.current, a.action_id);
          commit(res);
          enqueue(res.events);
          cur = res;
        }
        if (cur) await continueBot(cur, true);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        if (gameId.current) {
          try {
            commit(await api.state(gameId.current));
          } catch {
            /* ignore */
          }
        }
      } finally {
        setBusy(false);
      }
    },
    [busy, commit, continueBot, enqueue],
  );

  const dismissTurnGate = useCallback(() => {
    setTurnGate(null);
    const release = gateResolver.current;
    gateResolver.current = null;
    release?.();
  }, []);

  const reset = useCallback(() => {
    skipAnimations();
    gameId.current = null;
    commit(null);
    setDefeated(new Set());
    setLog([]);
    setError(null);
    setTurnGate(null);
    gateResolver.current = null;
    lastRoundRef.current = 0;
  }, [commit, skipAnimations]);

  const locked =
    busy || playing || turnGate !== null || (snapshot !== null && snapshot.awaiting !== "human");

  return {
    snapshot,
    busy,
    error,
    active,
    playing,
    defeated,
    log,
    locked,
    gameId: gameId.current,
    turnGate,
    newGame,
    loadSaved,
    save,
    act,
    resourceCards,
    dismissTurnGate,
    skipAnimations,
    reset,
  };
}
