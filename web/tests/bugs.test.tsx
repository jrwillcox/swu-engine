// Report-a-bug flow: the HUD captures artifacts then opens the form; submitting
// POSTs title + context + screenshot + game to /api/bugs. Covers the game screen
// (screenshot + game state attached), the start screen (no game), and the
// best-effort screenshot rule (a capture failure never blocks the report).
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// vi.mock factories are hoisted above the file, so build the spies via vi.hoisted.
const { create, exportReplay, toPng } = vi.hoisted(() => ({
  create: vi.fn(async (_req: any) => ({ id: "2026-07-01-1200-x" })),
  exportReplay: vi.fn(async () => ({ format: 1, kind: "mirror", action_history: [] })),
  // html-to-image is dynamically imported inside the component; mock the module
  // so no real DOM rasterisation is attempted under jsdom.
  toPng: vi.fn(async () => "data:image/png;base64,AAAA"),
}));

vi.mock("../src/api/client", () => ({
  api: { bugs: { create }, exportReplay },
  ApiError: class ApiError extends Error {},
}));

vi.mock("html-to-image", () => ({ toPng }));

import { BugHud } from "../src/components/ReportBug";
import { snapshot } from "./fixtures";

async function openForm() {
  fireEvent.click(screen.getByRole("button", { name: /^🐞 report$/i }));
  // Capture-then-open is async; wait for the modal heading (defaults to Bug).
  await screen.findByRole("heading", { name: "Report a bug" });
}

beforeEach(() => {
  create.mockClear();
  exportReplay.mockClear();
  toPng.mockClear();
  toPng.mockResolvedValue("data:image/png;base64,AAAA");
});

describe("Report-a-bug HUD", () => {
  it("captures screenshot + game state on the game screen and submits", async () => {
    const snap = snapshot();
    render(<BugHud screen="game" gameId="g1" snapshot={snap} lastAction="played Boba Fett" />);

    await openForm();
    expect(exportReplay).toHaveBeenCalledWith("g1");
    expect(screen.getByText(/Game state attached/i)).toBeInTheDocument();

    // Title is required — Send is disabled until it's filled.
    const send = screen.getByRole("button", { name: /send report/i });
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Boba Fett attack did nothing" },
    });
    fireEvent.change(screen.getByLabelText("What did you expect to happen?"), {
      target: { value: "3 damage" },
    });
    expect(send).not.toBeDisabled();
    fireEvent.click(send);

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const req = create.mock.calls[0][0];
    expect(req.title).toBe("Boba Fett attack did nothing");
    expect(req.expected).toBe("3 damage");
    expect(req.screenshot_b64).toBe("data:image/png;base64,AAAA");
    expect(req.context).toMatchObject({
      screen: "game",
      game_id: "g1",
      your_turn: true,
      last_action: "played Boba Fett",
    });
    expect(req.game).toBeTruthy();
    expect(req.game.snapshot).toEqual(snap.view);
  });

  it("attaches no game bundle on a non-game screen", async () => {
    render(<BugHud screen="start" gameId={null} snapshot={null} />);
    await openForm();
    expect(exportReplay).not.toHaveBeenCalled();
    expect(screen.queryByText(/Game state attached/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Login is odd" } });
    fireEvent.click(screen.getByRole("button", { name: /send report/i }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const req = create.mock.calls[0][0];
    expect(req.context).toMatchObject({ screen: "start" });
    expect(req.game).toBeNull();
  });

  it("still submits when the screenshot capture fails (best-effort)", async () => {
    toPng.mockRejectedValueOnce(new Error("tainted canvas"));
    render(<BugHud screen="start" gameId={null} snapshot={null} />);
    await openForm();

    expect(screen.getByText(/No screenshot/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "No shot" } });
    fireEvent.click(screen.getByRole("button", { name: /send report/i }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0][0].screenshot_b64).toBeNull();
  });

  it("files a feature request: tags the title and stamps context.report_type", async () => {
    render(<BugHud screen="start" gameId={null} snapshot={null} />);
    await openForm();

    // Type defaults to Bug; switch to Feature Request (the first field).
    const type = screen.getByLabelText("Type") as HTMLSelectElement;
    expect(type.value).toBe("bug");
    fireEvent.change(type, { target: { value: "feature" } });
    // Heading follows the choice.
    expect(screen.getByRole("heading", { name: "Request a feature" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Card sorting" } });
    fireEvent.click(screen.getByRole("button", { name: /send report/i }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const req = create.mock.calls[0][0];
    expect(req.title).toBe("[Feature] Card sorting");
    expect(req.context).toMatchObject({ screen: "start", report_type: "feature" });
  });

  it("shows the inbox envelope with an unread badge only when wired", async () => {
    const { rerender } = render(<BugHud screen="start" gameId={null} snapshot={null} />);
    expect(screen.queryByLabelText(/open your messages/i)).not.toBeInTheDocument();

    rerender(
      <BugHud
        screen="start"
        gameId={null}
        snapshot={null}
        onOpenInbox={() => {}}
        unreadCount={3}
      />,
    );
    expect(screen.getByLabelText(/open your messages/i)).toBeInTheDocument();
    expect(screen.getByLabelText("3 unread")).toHaveTextContent("3");
  });
});
