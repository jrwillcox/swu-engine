// Part D UI tests: mulligan "moment", save button, and the start-screen tools
// (resume / import / watch replay), plus the replay viewer scrubbing.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Game } from "../src/game/useGame";
import type { ReplayResponse } from "../src/api/types";
import { SettingsProvider } from "../src/game/settings";
import { Table } from "../src/components/Table";
import { ReplayViewer } from "../src/components/ReplayViewer";
import { action, card, snapshot, view, zone } from "./fixtures";

function fakeGame(over: Partial<Game> = {}): Game {
  return {
    snapshot: snapshot(),
    busy: false,
    error: null,
    active: null,
    playing: false,
    defeated: new Set(),
    log: [],
    locked: false,
    gameId: "g-test",
    turnGate: null,
    newGame: vi.fn(),
    loadSaved: vi.fn(),
    save: vi.fn(async () => "quicksave"),
    act: vi.fn(),
    resourceCards: vi.fn(),
    dismissTurnGate: vi.fn(),
    skipAnimations: vi.fn(),
    reset: vi.fn(),
    ...over,
  };
}

const renderTable = (game: Game) =>
  render(
    <SettingsProvider>
      <Table game={game} />
    </SettingsProvider>,
  );

describe("Mulligan moment", () => {
  function mulliganGame(act = vi.fn()): Game {
    return fakeGame({
      act,
      snapshot: snapshot({
        view: view({
          phase: "SETUP_MULLIGAN",
          my: zone("human", {
            hand: [
              card({ instance_id: "h1", card_name: "Alpha", zone: "HAND" }),
              card({ instance_id: "h2", card_name: "Beta", zone: "HAND" }),
            ],
          }),
        }),
        actions: [
          action("KeepHand", {}, "a0", "Keep hand"),
          action("TakeMultiligan", {}, "a1", "Take mulligan (redraw 6)"),
        ],
      }),
    });
  }

  it("shows the opening hand overlay with Keep / Mulligan", () => {
    renderTable(mulliganGame());
    expect(screen.getByText(/Your opening hand/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Keep this hand/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mulligan/ })).toBeInTheDocument();
  });

  it("routes Keep to act()", () => {
    const act = vi.fn();
    renderTable(mulliganGame(act));
    fireEvent.click(screen.getByRole("button", { name: /Keep this hand/ }));
    expect(act).toHaveBeenCalledWith("a0");
  });
});

describe("Save button", () => {
  it("calls save('quicksave') and shows a toast", async () => {
    const save = vi.fn(async () => "quicksave");
    renderTable(fakeGame({ save }));
    fireEvent.click(screen.getByTitle("Save game"));
    expect(save).toHaveBeenCalledWith("quicksave");
    expect(await screen.findByText(/Game saved/)).toBeInTheDocument();
  });
});

// ── Start-screen tools ──────────────────────────────────────────────────────

const REPORT = {
  ok: false,
  legal: true,
  errors: [],
  total_cards: 52,
  playable_cards: 40,
  unimplemented: [
    { id: "SHD_160", name: "Reckless Gunslinger", label: "keyword-deferred", count: 3 },
  ],
  fixture_path: "data/imported/demo.json",
  planner_hint: "python scripts/plan_encoding.py --deck data/imported/demo.json",
};

vi.mock("../src/api/client", () => ({
  api: {
    decks: vi.fn(async () => [
      { key: "luke", label: "Luke", leader_name: "Luke Skywalker", base_name: "Tower" },
      { key: "vader", label: "Vader", leader_name: "Darth Vader", base_name: "Command" },
    ]),
    listSaves: vi.fn(async () => ["quicksave", "round-7"]),
    importSwudb: vi.fn(async () => REPORT),
    replay: vi.fn(async () => ({ human_id: "human", steps: [] })),
  },
}));

import { NewGameScreen } from "../src/components/NewGameScreen";

async function renderMenu(props: Partial<Parameters<typeof NewGameScreen>[0]> = {}) {
  const onStart = vi.fn();
  const onLoad = vi.fn();
  const onWatchReplay = vi.fn();
  render(
    <NewGameScreen
      onStart={onStart}
      busy={false}
      error={null}
      onLoad={onLoad}
      onWatchReplay={onWatchReplay}
      {...props}
    />,
  );
  await waitFor(() => expect(screen.getByText("Start game")).not.toBeDisabled());
  return { onStart, onLoad, onWatchReplay };
}

// HIDDEN 2026-09-01: the start-screen tools (Resume a saved game / Watch a replay /
// Import a deck) are commented out in NewGameScreen.tsx. Un-skip with them.
describe.skip("Start-screen tools", () => {
  it("lists saved games and resumes one", async () => {
    const { onLoad } = await renderMenu();
    await screen.findByText("Resume a saved game");
    const slot = await screen.findByRole("button", { name: "round-7" });
    fireEvent.click(slot);
    expect(onLoad).toHaveBeenCalledWith("round-7");
  });

  it("imports a SWUDB deck and reports gaps", async () => {
    await renderMenu();
    fireEvent.change(screen.getByLabelText("SWUDB decklist JSON"), {
      target: { value: '{"leader":{"id":"SHD_13"},"base":{"id":"SHD_24"},"deck":[]}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check deck" }));
    expect(await screen.findByText(/40\/52 cards playable/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/1 card\(s\) not yet playable/));
    expect(screen.getByText(/Reckless Gunslinger/)).toBeInTheDocument();
  });

  it("rejects invalid import JSON without calling the API", async () => {
    await renderMenu();
    fireEvent.change(screen.getByLabelText("SWUDB decklist JSON"), {
      target: { value: "not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check deck" }));
    expect(await screen.findByText(/isn't valid JSON/)).toBeInTheDocument();
  });

  it("offers a replay file input", async () => {
    await renderMenu();
    expect(screen.getByLabelText("Replay file")).toBeInTheDocument();
  });
});

// ── Replay viewer ───────────────────────────────────────────────────────────

function replayFixture(): ReplayResponse {
  return {
    human_id: "human",
    steps: [
      { view: view({ round_number: 1 }), events: [], winner: null },
      { view: view({ round_number: 2 }), events: [], winner: null },
      { view: view({ round_number: 3 }), events: [], winner: "human" },
    ],
  };
}

describe("ReplayViewer", () => {
  it("renders the board and scrubs forward and back", () => {
    const onExit = vi.fn();
    render(
      <SettingsProvider>
        <ReplayViewer replay={replayFixture()} onExit={onExit} />
      </SettingsProvider>,
    );
    expect(screen.getByText("Step 0 / 2")).toBeInTheDocument();
    expect(screen.getByText(/Opening position/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(screen.getByText("Step 1 / 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Prev/ }));
    expect(screen.getByText("Step 0 / 2")).toBeInTheDocument();
  });

  it("jumps to the end via the slider and shows the winner", () => {
    render(
      <SettingsProvider>
        <ReplayViewer replay={replayFixture()} onExit={vi.fn()} />
      </SettingsProvider>,
    );
    fireEvent.change(screen.getByLabelText("Replay position"), { target: { value: "2" } });
    expect(screen.getByText("Step 2 / 2")).toBeInTheDocument();
    expect(screen.getByText(/Winner: You/)).toBeInTheDocument();
  });

  it("exits via the menu button", () => {
    const onExit = vi.fn();
    render(
      <SettingsProvider>
        <ReplayViewer replay={replayFixture()} onExit={onExit} />
      </SettingsProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Menu/ }));
    expect(onExit).toHaveBeenCalled();
  });
});
