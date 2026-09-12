// ReplayViewer — scrub a recorded game forward/back.  The backend hands us one
// board snapshot per recorded action (`/api/replay`); we render the post-step
// truth with the same read-only zone components the live table uses, and play
// each step's events through the existing EffectsLayer when we land on it.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ActiveEvent } from "../game/useGame";
import type { CardModel, ReplayResponse } from "../api/types";
import { formatEvent } from "../game/format";
import { ArenaBand, BaseCluster, MyHand, OppHand, Pile, ResourceRow, type SlotFns } from "./zones";
import { CardZoom } from "./ui";
import { EffectsLayer } from "./EffectsLayer";

const STEP_EVENT_MS = 420; // per-event delay while a step's effects play

export function ReplayViewer({ replay, onExit }: { replay: ReplayResponse; onExit: () => void }) {
  const steps = replay.steps;
  const last = steps.length - 1;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [hover, setHover] = useState<CardModel | null>(null);
  const [active, setActive] = useState<ActiveEvent | null>(null);
  const keyRef = useRef(0);
  const timers = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);

  // When we land on a step, play its events through the EffectsLayer in order.
  useEffect(() => {
    clearTimers();
    setActive(null);
    const evs = steps[index]?.events ?? [];
    evs.forEach((ev, i) => {
      timers.current.push(
        window.setTimeout(() => setActive({ ev, key: keyRef.current++ }), i * STEP_EVENT_MS),
      );
    });
    return clearTimers;
  }, [index, steps, clearTimers]);

  // Auto-advance while playing.
  useEffect(() => {
    if (!playing) return;
    if (index >= last) {
      setPlaying(false);
      return;
    }
    const evCount = steps[index]?.events?.length ?? 0;
    const dwell = Math.max(600, evCount * STEP_EVENT_MS + 250);
    const t = window.setTimeout(() => setIndex((i) => Math.min(last, i + 1)), dwell);
    return () => window.clearTimeout(t);
  }, [playing, index, last, steps]);

  const step = steps[index];
  const view = step.view;

  const slot: SlotFns = {
    hl: () => null,
    onClick: () => {},
    onHover: (c) => setHover(c),
    defeated: () => false,
  };

  const go = (i: number) => {
    setPlaying(false);
    setIndex(Math.max(0, Math.min(last, i)));
  };

  const stepLog = (step.events ?? [])
    .map(formatEvent)
    .filter((l): l is NonNullable<typeof l> => l !== null);

  return (
    <div className="replay-viewer">
      <div className="replay-bar panel">
        <button className="btn btn-ghost" onClick={onExit}>
          ← Menu
        </button>
        <span className="spacer" style={{ flex: 1 }} />
        <button
          className="btn"
          onClick={() => go(index - 1)}
          disabled={index === 0}
          aria-label="Previous step"
        >
          ◀ Prev
        </button>
        <button
          className="btn btn-primary"
          onClick={() => setPlaying((p) => !p)}
          disabled={index >= last}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button
          className="btn"
          onClick={() => go(index + 1)}
          disabled={index >= last}
          aria-label="Next step"
        >
          Next ▶
        </button>
        <input
          className="replay-slider"
          type="range"
          min={0}
          max={last}
          value={index}
          aria-label="Replay position"
          onChange={(e) => go(Number(e.target.value))}
        />
        <span className="replay-counter">
          Step {index} / {last}
        </span>
      </div>

      <div className="replay-body">
        <div className="board replay-board">
          <div className="rail opp panel">
            <OppHand count={view.opponent.hand_count} />
            <BaseCluster zone={view.opponent} mine={false} slot={slot} />
            <ResourceRow zone={view.opponent} />
            <span className="spacer" />
            <div className="piles">
              <Pile label="Deck" count={view.opponent.deck_count} />
              <Pile
                label="Discard"
                count={view.opponent.discard.length}
                topCard={view.opponent.discard.slice(-1)[0]}
                onHover={(c) => setHover(c)}
              />
            </div>
          </div>

          <div className="arenas">
            <ArenaBand
              arena="ground"
              label="Ground"
              oppUnits={view.opponent.ground_arena}
              myUnits={view.my.ground_arena}
              slot={slot}
              isTargetZone={false}
            />
            <ArenaBand
              arena="space"
              label="Space"
              oppUnits={view.opponent.space_arena}
              myUnits={view.my.space_arena}
              slot={slot}
              isTargetZone={false}
            />
          </div>

          <div className="rail panel">
            <BaseCluster zone={view.my} mine={true} slot={slot} />
            <ResourceRow zone={view.my} />
            <span className="spacer" />
            <div className="piles">
              <Pile label="Deck" count={view.my.deck_count} />
              <Pile
                label="Discard"
                count={view.my.discard.length}
                topCard={view.my.discard.slice(-1)[0]}
                onHover={(c) => setHover(c)}
              />
            </div>
          </div>

          <MyHand zone={view.my} slot={slot} />
        </div>

        <div className="replay-side panel scroll">
          <h4>This step</h4>
          {index === 0 && <div className="log-line">Opening position.</div>}
          {stepLog.length === 0 && index > 0 && <div className="log-line">(no visible effect)</div>}
          {stepLog.map((l, i) => (
            <div key={i} className={`log-line ${l.tone}`}>
              {l.text}
            </div>
          ))}
          {index === last && step.winner && (
            <div className="log-line good" style={{ marginTop: 10 }}>
              Winner: {step.winner === replay.human_id ? "You" : "Opponent"}
            </div>
          )}
        </div>
      </div>

      <EffectsLayer active={active} />
      <CardZoom card={hover} />
    </div>
  );
}
