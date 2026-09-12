// Admin bug triage (Stage 4): the three buckets, the thread detail (full messages
// with real sender names, the context block, status control, reply, archive), and
// the "open game in replay viewer" path (game.json → /api/replay → onWatchReplay).
// Also the AdminPanel tab shell. All API calls mocked — no network.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  adminList,
  get,
  adminSetStatus,
  reply,
  adminArchive,
  screenshotObjectUrl,
  game,
  replay,
  users,
} = vi.hoisted(() => ({
  adminList: vi.fn(),
  get: vi.fn(),
  adminSetStatus: vi.fn(),
  reply: vi.fn(),
  adminArchive: vi.fn(),
  screenshotObjectUrl: vi.fn(async () => null),
  game: vi.fn(),
  replay: vi.fn(),
  users: vi.fn(async () => []),
}));

vi.mock("../src/api/client", () => ({
  api: {
    bugs: { adminList, get, adminSetStatus, reply, adminArchive, screenshotObjectUrl, game },
    replay,
    auth: { users },
  },
  ApiError: class ApiError extends Error {},
}));

import { BugTriage } from "../src/components/BugTriage";
import { AdminPanel } from "../src/components/AdminPanel";
import type { AdminTriage, BugSummary, BugThread } from "../src/api/types";

function summary(over: Partial<BugSummary>): BugSummary {
  return {
    id: "id1",
    title: "Boba attack did nothing",
    status: "new",
    author: "Bob",
    created: "2026-07-01T12:00:00Z",
    updated: "2026-07-01T12:00:00Z",
    last_from: "Bob",
    unread: 0,
    reporter_archived: false,
    archived: false,
    has_screenshot: false,
    has_game: false,
    ...over,
  };
}

function triage(over: Partial<AdminTriage> = {}): AdminTriage {
  return { needs_you: [], waiting_on_reporter: [], resolved: [], ...over };
}

function thread(over: Partial<BugThread>): BugThread {
  return {
    id: "id1",
    title: "Boba attack did nothing",
    status: "new",
    author: "Bob",
    created: "2026-07-01T12:00:00Z",
    reporter_archived: false,
    archived: false,
    context: { screen: "game", game_id: "g1", your_turn: true },
    has_screenshot: false,
    has_game: true,
    messages: [
      {
        from: "Bob",
        ts: "2026-07-01T12:00:00Z",
        read_by: ["Bob"],
        title: "Boba attack did nothing",
        expected: "3 damage",
        actual: "nothing",
      },
    ],
    ...over,
  };
}

beforeEach(() => {
  adminList.mockReset();
  get.mockReset();
  adminSetStatus.mockReset();
  reply.mockReset();
  adminArchive.mockReset();
  screenshotObjectUrl.mockReset();
  screenshotObjectUrl.mockResolvedValue(null);
  game.mockReset();
  replay.mockReset();
});

describe("Admin bug triage", () => {
  it("shows the three buckets with their rows", async () => {
    adminList.mockResolvedValue(
      triage({
        needs_you: [summary({ id: "a", title: "Needs one", author: "Bob" })],
        waiting_on_reporter: [summary({ id: "b", title: "Waiting one", last_from: "Alice" })],
        resolved: [summary({ id: "c", title: "Resolved one", status: "resolved" })],
      }),
    );
    render(<BugTriage />);

    expect(await screen.findByText("Needs one")).toBeInTheDocument();
    expect(screen.getByText("Waiting one")).toBeInTheDocument();
    expect(screen.getByText("Resolved one")).toBeInTheDocument();
    // The bucket headings.
    expect(screen.getByText(/Needs you/i)).toBeInTheDocument();
    expect(screen.getByText(/Waiting on reporter/i)).toBeInTheDocument();
  });

  it("shows the reporter's comment preview and the bug id in each row", async () => {
    adminList.mockResolvedValue(
      triage({
        needs_you: [
          summary({
            id: "2026-07-01-1932-scimitar",
            title: "The scimitar doesn't work",
            actual: "It did 3 damage and the ability didn't work",
          }),
        ],
      }),
    );
    render(<BugTriage />);

    // The submitted comment is visible without opening the thread…
    expect(
      await screen.findByText(/It did 3 damage and the ability didn't work/),
    ).toBeInTheDocument();
    // …and so is the bug id (copy/paste target).
    expect(screen.getByText("2026-07-01-1932-scimitar")).toBeInTheDocument();
  });

  it("shows a copyable bug id chip in the opened thread", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(thread({ id: "id1" }));
    render(<BugTriage />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    const chip = await screen.findByRole("button", { name: /copy bug id/i });
    fireEvent.click(chip);

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("id1"));
    expect(await screen.findByText(/copied/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no reports", async () => {
    adminList.mockResolvedValue(triage());
    render(<BugTriage />);
    expect(await screen.findByText(/No reports yet/i)).toBeInTheDocument();
  });

  it("opens a thread and renders full messages with real sender names", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(
      thread({
        messages: [
          {
            from: "Bob",
            ts: "2026-07-01T12:00:00Z",
            read_by: ["Bob"],
            title: "t",
            expected: "3 damage",
            actual: "nothing",
          },
          { from: "Alice", ts: "2026-07-01T13:00:00Z", read_by: ["Alice"], text: "On it." },
        ],
      }),
    );
    render(<BugTriage />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    await screen.findByText("On it.");
    // Real sender names (dev-side view), not "Dev Team".
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getAllByText("Bob").length).toBeGreaterThan(0);
    // The capture context block is rendered. Only the game id is surfaced here
    // (labelled "Game"); the rest of the context lives in the game.json replay
    // bundle, reachable via "Open game in replay viewer".
    expect(screen.getByText("Game")).toBeInTheDocument();
    expect(screen.getByText("g1")).toBeInTheDocument();
  });

  it("changes status via the control", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(thread({}));
    adminSetStatus.mockResolvedValue(thread({ status: "investigating" }));
    render(<BugTriage />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    const select = await screen.findByLabelText(/set status/i);
    fireEvent.change(select, { target: { value: "investigating" } });

    await waitFor(() => expect(adminSetStatus).toHaveBeenCalledWith("id1", "investigating"));
  });

  it("sends a reply as the admin", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(thread({}));
    reply.mockResolvedValue(thread({}));
    render(<BugTriage />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    const send = await screen.findByRole("button", { name: /send reply/i });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/write a reply/i), {
      target: { value: "Which card was it?" },
    });
    fireEvent.click(send);

    await waitFor(() => expect(reply).toHaveBeenCalledWith("id1", "Which card was it?"));
  });

  it("archives a thread and returns to the list", async () => {
    adminList.mockResolvedValue(triage({ resolved: [summary({ id: "id1", status: "resolved" })] }));
    get.mockResolvedValue(thread({ status: "resolved" }));
    adminArchive.mockResolvedValue(thread({ archived: true }));
    render(<BugTriage />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    fireEvent.click(await screen.findByRole("button", { name: "Archive" }));

    await waitFor(() => expect(adminArchive).toHaveBeenCalledWith("id1"));
  });

  it("opens the reported game in the replay viewer", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(thread({ has_game: true }));
    const bundle = { format: 1, seed: 7 };
    game.mockResolvedValue({ replay: bundle });
    const replayResponse = { human_id: "p0", steps: [] };
    replay.mockResolvedValue(replayResponse);
    const onWatchReplay = vi.fn();
    render(<BugTriage onWatchReplay={onWatchReplay} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    fireEvent.click(await screen.findByRole("button", { name: /open game in replay/i }));

    await waitFor(() => expect(replay).toHaveBeenCalledWith(bundle));
    await waitFor(() => expect(onWatchReplay).toHaveBeenCalledWith(replayResponse));
  });

  it("reports when a game report has no replay bundle", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ id: "id1" })] }));
    get.mockResolvedValue(thread({ has_game: true }));
    game.mockResolvedValue({ replay: null });
    render(<BugTriage onWatchReplay={vi.fn()} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    fireEvent.click(await screen.findByRole("button", { name: /open game in replay/i }));

    expect(await screen.findByText(/no replay bundle/i)).toBeInTheDocument();
    expect(replay).not.toHaveBeenCalled();
  });
});

describe("AdminPanel shell", () => {
  it("defaults to bug triage and can switch to Manage users", async () => {
    adminList.mockResolvedValue(triage({ needs_you: [summary({ title: "A report" })] }));
    render(<AdminPanel onClose={() => {}} />);

    // Bug triage is the default tab.
    expect(await screen.findByText("A report")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /manage users/i }));
    expect(await screen.findByText(/Reset a player's password/i)).toBeInTheDocument();
  });
});
