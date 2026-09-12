// Regression: the round-start gate must fire at the round boundary — BEFORE
// the new round's first action animates — even when the opponent holds
// initiative and so plays first in the new round.
//
// Bug: the gate was only raised once control settled back on the human (after
// the bot loop), so an initiative-holding bot's opening plays (e.g. deploying
// Admiral Piett) animated first and the "start round N" popup arrived late.
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const advance = vi.fn();
const applyAction = vi.fn();
const newGameApi = vi.fn();

vi.mock("../src/api/client", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    advance: (...a: unknown[]) => advance(...a),
    applyAction: (...a: unknown[]) => applyAction(...a),
    newGame: (...a: unknown[]) => newGameApi(...a),
    loadGame: vi.fn(),
    state: vi.fn(),
    saveGame: vi.fn(),
  },
}));

import { useGame } from "../src/game/useGame";
import { SettingsProvider } from "../src/game/settings";
import { snapshot, view } from "./fixtures";

function wrapper({ children }: { children: ReactNode }) {
  return <SettingsProvider>{children}</SettingsProvider>;
}

beforeEach(() => {
  advance.mockReset();
  applyAction.mockReset();
  newGameApi.mockReset();
  // Reduced motion → near-instant animation queue so timing is deterministic.
  localStorage.clear();
  localStorage.setItem("swu.reduced", JSON.stringify(true));
});

describe("round-start gate timing", () => {
  it("gates on the round boundary before driving the initiative-holding bot", async () => {
    // Bootstrap a mid-round-2 game with the human to act (no bot loop), so the
    // gate's "last started round" baseline lands on 2.
    newGameApi.mockResolvedValue(
      snapshot({ view: view({ round_number: 2 }), awaiting: "human" }) as never,
    );
    // The human's regroup choice ends round 2: the response is the first
    // round-3 state and it's the bot's turn (the bot holds initiative).
    applyAction.mockResolvedValue(
      snapshot({
        view: view({ round_number: 3 }),
        awaiting: "bot",
        actor_id: "bot",
        events: [{ type: "RoundStarted", data: { round_number: 3 } }],
      } as never),
    );
    // If the bot loop runs, it would deploy a unit and hand control back.
    advance.mockResolvedValue(
      snapshot({
        view: view({ round_number: 3 }),
        awaiting: "human",
        actor_id: "human",
        events: [{ type: "UnitEntersPlay", data: { instance_id: "piett" } }],
      } as never),
    );

    const { result } = renderHook(() => useGame(), { wrapper });

    await act(async () => {
      await result.current.newGame({ difficulty: "normal" } as never);
    });

    // Fire the human action but do NOT await it — act() awaits the bot loop,
    // which is now parked behind the gate until we dismiss it.
    let actDone!: Promise<void>;
    await act(async () => {
      actDone = result.current.act("a0");
    });

    // Gate is up for round 3 and the bot has NOT been advanced.
    await waitFor(() => expect(result.current.turnGate).toBe(3));
    expect(advance).not.toHaveBeenCalled();

    // Dismissing releases the parked bot loop, which now advances.
    await act(async () => {
      result.current.dismissTurnGate();
      await actDone;
    });
    expect(advance).toHaveBeenCalledTimes(1);
    expect(result.current.turnGate).toBeNull();
  });
});
