// Reporter inbox (Stage 3): the thread list (Active / Archived tabs, unread dots,
// "Dev Team replied" highlight), the thread view (You vs Dev Team, mark-read on
// open, text-only reply), and the cosmetic Archive toggle. All API calls are
// mocked — no network, no real screenshot fetch.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { list, get, markRead, reply, setArchived, screenshotObjectUrl } = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  markRead: vi.fn(),
  reply: vi.fn(),
  setArchived: vi.fn(),
  screenshotObjectUrl: vi.fn(async () => null),
}));

vi.mock("../src/api/client", () => ({
  api: { bugs: { list, get, markRead, reply, setArchived, screenshotObjectUrl } },
  ApiError: class ApiError extends Error {},
}));

import { BugInbox } from "../src/components/BugInbox";
import type { BugSummary, BugThread } from "../src/api/types";

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

function thread(over: Partial<BugThread>): BugThread {
  return {
    id: "id1",
    title: "Boba attack did nothing",
    status: "investigating",
    author: "Bob",
    created: "2026-07-01T12:00:00Z",
    reporter_archived: false,
    archived: false,
    context: {},
    has_screenshot: false,
    has_game: false,
    messages: [
      {
        from: "Bob",
        ts: "2026-07-01T12:00:00Z",
        read_by: ["Bob"],
        title: "Boba attack did nothing",
        expected: "3 damage",
        actual: "nothing",
      },
      { from: "claude", ts: "2026-07-01T13:00:00Z", read_by: ["Bob"], text: "Looking into it!" },
    ],
    ...over,
  };
}

beforeEach(() => {
  list.mockReset();
  get.mockReset();
  markRead.mockReset();
  reply.mockReset();
  setArchived.mockReset();
  screenshotObjectUrl.mockReset();
  screenshotObjectUrl.mockResolvedValue(null);
});

describe("Reporter inbox", () => {
  it("lists own threads and flags an unread dev reply", async () => {
    list.mockResolvedValue([
      summary({ id: "a", title: "Unread one", unread: 2, last_from: "claude" }),
      summary({ id: "b", title: "Read one", unread: 0, last_from: "Bob" }),
    ]);
    render(<BugInbox username="Bob" onClose={() => {}} />);

    await screen.findByText("Unread one");
    expect(screen.getByText("Read one")).toBeInTheDocument();
    // The unread dev reply gets the highlight; the read one does not.
    expect(screen.getByText("Dev Team replied")).toBeInTheDocument();
  });

  it("separates Active and Archived by reporter_archived", async () => {
    list.mockResolvedValue([
      summary({ id: "a", title: "Active thread", reporter_archived: false }),
      summary({ id: "b", title: "Archived thread", reporter_archived: true }),
    ]);
    render(<BugInbox username="Bob" onClose={() => {}} />);

    await screen.findByText("Active thread");
    expect(screen.queryByText("Archived thread")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /archived/i }));
    expect(await screen.findByText("Archived thread")).toBeInTheDocument();
    expect(screen.queryByText("Active thread")).not.toBeInTheDocument();
  });

  it("opens a thread, marks it read, and renders You vs Dev Team", async () => {
    list.mockResolvedValue([summary({ id: "id1", unread: 1, last_from: "claude" })]);
    markRead.mockResolvedValue(thread({}));
    const onChanged = vi.fn();
    render(<BugInbox username="Bob" onClose={() => {}} onChanged={onChanged} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));

    await waitFor(() => expect(markRead).toHaveBeenCalledWith("id1"));
    expect(onChanged).toHaveBeenCalled();
    // The reporter's own report shows "You"; the dev reply shows "Dev Team".
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("Dev Team")).toBeInTheDocument();
    expect(screen.getByText("Looking into it!")).toBeInTheDocument();
  });

  it("sends a text-only reply", async () => {
    list.mockResolvedValue([summary({ id: "id1" })]);
    markRead.mockResolvedValue(thread({}));
    reply.mockResolvedValue(
      thread({
        messages: [
          ...thread({}).messages,
          { from: "Bob", ts: "z", read_by: ["Bob"], text: "the game screen" },
        ],
      }),
    );
    render(<BugInbox username="Bob" onClose={() => {}} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    await screen.findByText("Looking into it!");

    const send = screen.getByRole("button", { name: /send reply/i });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/write a reply/i), {
      target: { value: "the game screen" },
    });
    expect(send).not.toBeDisabled();
    fireEvent.click(send);

    await waitFor(() => expect(reply).toHaveBeenCalledWith("id1", "the game screen"));
  });

  it("archives a thread from the thread view", async () => {
    list.mockResolvedValue([summary({ id: "id1" })]);
    markRead.mockResolvedValue(thread({}));
    setArchived.mockResolvedValue(thread({ reporter_archived: true }));
    render(<BugInbox username="Bob" onClose={() => {}} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    const archive = await screen.findByRole("button", { name: "Archive" });
    fireEvent.click(archive);

    await waitFor(() => expect(setArchived).toHaveBeenCalledWith("id1", true));
    expect(await screen.findByRole("button", { name: "Unarchive" })).toBeInTheDocument();
  });

  it("celebrates a resolved thread", async () => {
    list.mockResolvedValue([summary({ id: "id1", status: "resolved" })]);
    markRead.mockResolvedValue(thread({ status: "resolved" }));
    render(<BugInbox username="Bob" onClose={() => {}} />);

    fireEvent.click(await screen.findByText("Boba attack did nothing"));
    expect(await screen.findByText(/marked this fixed/i)).toBeInTheDocument();
  });
});
