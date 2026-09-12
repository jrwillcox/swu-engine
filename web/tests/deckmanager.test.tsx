// DeckManager (Stage 4): renders the user's decks with a Complete/Draft pill,
// creates via POST, renames via PATCH, and deletes behind a confirm dialog.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CustomDeck, CustomDeckSummary } from "../src/api/types";

// ── mock the API client ──────────────────────────────────────────────────────
const listFn = vi.fn();
const getFn = vi.fn();
const createFn = vi.fn();
const patchFn = vi.fn();
const deleteFn = vi.fn();
const catalogFn = vi.fn();

vi.mock("../src/api/client", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message);
    }
  },
  api: {
    customDecks: {
      list: (...a: unknown[]) => listFn(...a),
      get: (...a: unknown[]) => getFn(...a),
      create: (...a: unknown[]) => createFn(...a),
      patch: (...a: unknown[]) => patchFn(...a),
      delete: (...a: unknown[]) => deleteFn(...a),
    },
    catalog: (...a: unknown[]) => catalogFn(...a),
  },
}));

import { DeckManager } from "../src/components/DeckManager";

// ── fixtures ─────────────────────────────────────────────────────────────────
const SUMMARIES: CustomDeckSummary[] = [
  { id: "d1", name: "Aggro Rush", count: 50, required: 50, complete: true },
  { id: "d2", name: "Draft Pile", count: 12, required: 50, complete: false },
];

const FULL: Record<string, CustomDeck> = {
  d1: {
    id: "d1",
    name: "Aggro Rush",
    owner: "bob",
    leader_id: 100,
    base_id: 200,
    cards: { "300": 3, "301": 2 },
    created: "2026-07-02T10:00:00Z",
    updated: "2026-07-02T10:00:00Z",
    count: 50,
    required: 50,
    complete: true,
    errors: [],
  },
  d2: {
    id: "d2",
    name: "Draft Pile",
    owner: "bob",
    leader_id: null,
    base_id: null,
    cards: { "300": 12 },
    created: "2026-07-01T10:00:00Z",
    updated: "2026-07-01T10:00:00Z",
    count: 12,
    required: 50,
    complete: false,
    errors: ["No Leader chosen.", "No Base chosen.", "Deck has 12 cards; needs exactly 50."],
  },
};

const CATALOG = {
  cards: [
    { id: 100, name: "Luke Skywalker" },
    { id: 200, name: "Administrator's Tower" },
    { id: 300, name: "Battle Droid" },
    { id: 301, name: "Vanguard" },
  ],
  sets: [],
  types: [],
  aspects: [],
  keywords: [],
  traits: [],
  decks: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  listFn.mockResolvedValue(SUMMARIES);
  getFn.mockImplementation(async (id: string) => FULL[id]);
  catalogFn.mockResolvedValue(CATALOG);
  createFn.mockResolvedValue({ ...FULL.d2, id: "d3", name: "Fresh Deck" });
  patchFn.mockImplementation(async (id: string) => FULL[id]);
  deleteFn.mockResolvedValue({ ok: true });
});

async function renderManager() {
  render(<DeckManager onBack={vi.fn()} />);
  // Wait for the async load (list + per-deck get) to paint the rows.
  await screen.findByText("Aggro Rush");
}

describe("DeckManager", () => {
  it("renders the user's decks with Complete/Draft pills and counts", async () => {
    await renderManager();
    expect(screen.getByText("Aggro Rush")).toBeInTheDocument();
    expect(screen.getByText("Draft Pile")).toBeInTheDocument();
    // Pill logic: complete deck → "Complete", draft → "Draft".
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("50/50")).toBeInTheDocument();
    expect(screen.getByText("12/50")).toBeInTheDocument();
  });

  it("creates a deck via POST when a name is entered", async () => {
    await renderManager();
    fireEvent.change(screen.getByLabelText("New deck name"), {
      target: { value: "Fresh Deck" },
    });
    fireEvent.click(screen.getByRole("button", { name: "New deck" }));
    await waitFor(() => expect(createFn).toHaveBeenCalledWith("Fresh Deck"));
  });

  it("renames a deck via PATCH", async () => {
    await renderManager();
    fireEvent.click(screen.getByRole("button", { name: "Rename Aggro Rush" }));
    const input = screen.getByLabelText("Deck name") as HTMLInputElement;
    expect(input.value).toBe("Aggro Rush");
    fireEvent.change(input, { target: { value: "Aggro Rush 2" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patchFn).toHaveBeenCalledWith("d1", { name: "Aggro Rush 2" }));
  });

  it("deletes a deck only after confirming", async () => {
    await renderManager();
    fireEvent.click(screen.getByRole("button", { name: "Delete Aggro Rush" }));
    // The confirm dialog appears; nothing deleted yet.
    expect(screen.getByText("Delete deck?")).toBeInTheDocument();
    expect(deleteFn).not.toHaveBeenCalled();
    // Confirm → the destructive button in the dialog.
    const dialog = screen.getByText("Delete deck?").closest(".confirm-dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteFn).toHaveBeenCalledWith("d1"));
  });

  it("opens a deck to show its read-only contents", async () => {
    await renderManager();
    fireEvent.click(screen.getByText("Aggro Rush"));
    // Detail view: leader/base slot names resolved via the catalog.
    expect(await screen.findByText("Luke Skywalker")).toBeInTheDocument();
    expect(screen.getByText("Administrator's Tower")).toBeInTheDocument();
    // Pool entries with ×count.
    expect(screen.getByText("Battle Droid")).toBeInTheDocument();
    expect(screen.getByText("×3")).toBeInTheDocument();
  });
});
