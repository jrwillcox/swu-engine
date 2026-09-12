// CardExplorer add-to-deck mode (Stage 5): choosing a custom deck in the "Adding
// to" selector reveals +/- steppers that live-edit that server deck; with no deck
// chosen the explorer is browse-only; caps disable +; a Leader card fills the
// leader slot; and the live deck rail totals update.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CustomDeck, CustomDeckSummary, ExplorerResponse } from "../src/api/types";

// A tiny catalog: a Leader, a Base, a normal pool unit (cap 3), and a capped-at-1
// pool unit (to exercise the copy-cap disabling of +).
const CATALOG: ExplorerResponse = {
  cards: [
    {
      id: 100,
      set_code: "SOR",
      card_number: "1",
      name: "Test Leader",
      subtitle: null,
      type: "Leader",
      rarity: null,
      cost: 6,
      power: 4,
      hp: 7,
      unique: true,
      aspects: ["Command"],
      keywords: [],
      traits: [],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 3,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
    {
      id: 200,
      set_code: "SOR",
      card_number: "2",
      name: "Test Base",
      subtitle: null,
      type: "Base",
      rarity: null,
      cost: null,
      power: null,
      hp: 30,
      unique: false,
      aspects: [],
      keywords: [],
      traits: [],
      arenas: [],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 3,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
    {
      id: 300,
      set_code: "SOR",
      card_number: "10",
      name: "Rebel Trooper",
      subtitle: null,
      type: "Unit",
      rarity: "Common",
      cost: 2,
      power: 2,
      hp: 2,
      unique: false,
      aspects: ["Command"],
      keywords: [],
      traits: ["Trooper"],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 3,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
    {
      id: 301,
      set_code: "SOR",
      card_number: "11",
      name: "Solo Special",
      subtitle: null,
      type: "Unit",
      rarity: "Legendary",
      cost: 5,
      power: 5,
      hp: 5,
      unique: true,
      aspects: ["Cunning"],
      keywords: [],
      traits: [],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 1,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
    // Two DIFFERENT printings of the SAME card (same name+subtitle, different id)
    // — a reprint/promo. The copy cap is by title+subtitle, so 3 total across BOTH.
    {
      id: 400,
      set_code: "SHD",
      card_number: "49",
      name: "Mando",
      subtitle: "Wherever I Go He Goes",
      type: "Unit",
      rarity: "Rare",
      cost: 4,
      power: 3,
      hp: 6,
      unique: true,
      aspects: ["Command"],
      keywords: [],
      traits: ["Mandalorian"],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 3,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
    {
      id: 401,
      set_code: "P25",
      card_number: "101",
      name: "Mando",
      subtitle: "Wherever I Go He Goes",
      type: "Unit",
      rarity: "Special",
      cost: 4,
      power: 3,
      hp: 6,
      unique: true,
      aspects: ["Command"],
      keywords: [],
      traits: ["Mandalorian"],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      deckbuild_max_copies: 3,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
  ],
  sets: [{ code: "SOR", name: "Spark of Rebellion" }],
  types: ["Base", "Leader", "Unit"],
  aspects: ["Command", "Cunning"],
  keywords: [],
  traits: ["Trooper"],
  decks: [],
};

const SUMMARIES: CustomDeckSummary[] = [
  { id: "d1", name: "My Deck", count: 0, required: 50, complete: false },
];

// A stateful in-memory deck the mocked cards()/patch() mutate, so the UI reflects
// "server truth" like the real backend. `required` is server-derived from the base
// (50 by default, 60 under Data Vault) — the UI must never assume 50.
let deckState: CustomDeck;
function resetDeck() {
  deckState = {
    id: "d1",
    name: "My Deck",
    owner: "bob",
    leader_id: null,
    base_id: null,
    cards: {},
    created: "",
    updated: "",
    count: 0,
    required: 50,
    complete: false,
    errors: [],
  };
}
function snapshot(): CustomDeck {
  const count = Object.values(deckState.cards).reduce((a, b) => a + b, 0);
  return { ...deckState, cards: { ...deckState.cards }, count };
}

const catalogFn = vi.fn(async () => CATALOG);
const listFn = vi.fn(async () => SUMMARIES);
const getFn = vi.fn(async () => snapshot());
const cardsFn = vi.fn(async (_id: string, cardId: number, delta: number) => {
  const key = String(cardId);
  const next = (deckState.cards[key] ?? 0) + delta;
  if (next > 0) deckState.cards[key] = next;
  else delete deckState.cards[key];
  return snapshot();
});
const patchFn = vi.fn(
  async (_id: string, req: { leader_id?: number | null; base_id?: number | null }) => {
    if ("leader_id" in req) deckState.leader_id = req.leader_id ?? null;
    if ("base_id" in req) deckState.base_id = req.base_id ?? null;
    return snapshot();
  },
);

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
    catalog: (...a: unknown[]) => catalogFn(...(a as [])),
    customDecks: {
      list: (...a: unknown[]) => listFn(...(a as [])),
      get: (...a: unknown[]) => getFn(...(a as [])),
      cards: (...a: [string, number, number]) => cardsFn(...a),
      patch: (...a: [string, { leader_id?: number | null; base_id?: number | null }]) =>
        patchFn(...a),
    },
  },
}));

import { CardExplorer } from "../src/components/CardExplorer";
import { SettingsProvider } from "../src/game/settings";

function tileFor(name: string): HTMLElement {
  return screen.getByText(name).closest(".xtile") as HTMLElement;
}

// Two printings share a name, so find their tiles by the unique "SET NUM" code.
function tileForCode(code: string): HTMLElement {
  return screen.getByText(code).closest(".xtile") as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  resetDeck();
});

// `total` is the rail readout to wait for, so a test that pre-seeds `deckState`
// can settle on its own count rather than the empty "0/50".
async function renderAndSelectDeck(total = "0/50") {
  render(
    <SettingsProvider>
      <CardExplorer onBack={vi.fn()} />
    </SettingsProvider>,
  );
  await waitFor(() => expect(screen.getByText("Rebel Trooper")).toBeInTheDocument());
  // The "Adding to" selector appears once the caller's decks load.
  const selector = await screen.findByLabelText("Adding to deck");
  fireEvent.change(selector, { target: { value: "d1" } });
  // The live deck rail loads and shows the expected total.
  await waitFor(() => expect(getFn).toHaveBeenCalledWith("d1"));
  await screen.findByText(total);
}

describe("CardExplorer add-to-deck mode", () => {
  it("shows the deck selector and enters add mode with a live rail", async () => {
    await renderAndSelectDeck();
    // The rail names the deck and shows empty slots + total.
    expect(screen.getByText("My Deck")).toBeInTheDocument();
    expect(screen.getByText("0/50")).toBeInTheDocument();
    expect(screen.getByText("50 to go")).toBeInTheDocument();
    expect(screen.getByText("No leader")).toBeInTheDocument();
    expect(screen.getByText("No base")).toBeInTheDocument();
    // The anonymous "selected" chip is hidden in add mode.
    expect(screen.queryByText(/🃏 .* selected/)).not.toBeInTheDocument();
  });

  it("adds a pool card via the granular /cards API and updates the rail total", async () => {
    await renderAndSelectDeck();
    const add = within(tileFor("Rebel Trooper")).getByLabelText("Add copy");
    fireEvent.click(add);
    await waitFor(() => expect(cardsFn).toHaveBeenCalledWith("d1", 300, 1));
    // Rail total climbs and the pool lists the card.
    await screen.findByText("1/50");
    expect(screen.getByText("49 to go")).toBeInTheDocument();
    const rail = document.querySelector(".deck-panel") as HTMLElement;
    expect(within(rail).getByText("Rebel Trooper")).toBeInTheDocument();
    expect(within(rail).getByText("×1")).toBeInTheDocument();
  });

  it("removes a pool card via a negative delta", async () => {
    await renderAndSelectDeck();
    const tile = tileFor("Rebel Trooper");
    fireEvent.click(within(tile).getByLabelText("Add copy"));
    await screen.findByText("1/50");
    fireEvent.click(within(tile).getByLabelText("Remove copy"));
    await waitFor(() => expect(cardsFn).toHaveBeenLastCalledWith("d1", 300, -1));
    await screen.findByText("0/50");
  });

  it("disables + at a card's copy cap", async () => {
    await renderAndSelectDeck();
    const tile = tileFor("Solo Special"); // deckbuild_max_copies = 1
    fireEvent.click(within(tile).getByLabelText("Add copy"));
    await screen.findByText("1/50");
    // At its cap of 1, + is disabled with an explanatory title.
    await waitFor(() => expect(within(tile).getByLabelText("Add copy")).toBeDisabled());
    expect(within(tile).getByLabelText("Add copy").getAttribute("title")).toBe(
      "Max 1 copies (incl. other printings)",
    );
  });

  it("caps copies by title+subtitle across printings (reprints share one cap)", async () => {
    await renderAndSelectDeck();
    // Two printings of the same card: The Mandalorian (SHD 49) and (P25 101).
    const shd = tileForCode("SHD 49");
    const p25 = tileForCode("P25 101");
    // Add 3 copies of the SHD printing — reaching the shared cap of 3.
    fireEvent.click(within(shd).getByLabelText("Add copy"));
    await screen.findByText("1/50");
    fireEvent.click(within(shd).getByLabelText("Add copy"));
    await screen.findByText("2/50");
    fireEvent.click(within(shd).getByLabelText("Add copy"));
    await screen.findByText("3/50");
    // Now BOTH printings' + are disabled — the cap is by title+subtitle, not id,
    // so you cannot dodge the 3-copy limit by mixing printings.
    await waitFor(() => expect(within(shd).getByLabelText("Add copy")).toBeDisabled());
    expect(within(p25).getByLabelText("Add copy")).toBeDisabled();
    expect(within(p25).getByLabelText("Add copy").getAttribute("title")).toBe(
      "Max 3 copies (incl. other printings)",
    );
  });

  it("takes the pool target from the deck's `required`, not a hardcoded 50", async () => {
    // Regression for the reported "The Data Vault doesn't work" (2026-08-06): a base
    // that raises the minimum deck size to 60 must raise the rail's target AND
    // the deck-full guard with it, or the deck can never be finished — the
    // backend keeps calling it a Draft while + refuses to add card 51.
    // (Filler sits on an id outside the catalog so no COPY cap is in play here.)
    deckState.required = 60;
    deckState.cards["9999"] = 50;
    await renderAndSelectDeck("50/60");

    // The rail counts toward 60 and still has 10 to go...
    expect(screen.getByText("10 to go")).toBeInTheDocument();
    // ...and + is still live at 50, rather than "Deck full (50)".
    expect(within(tileFor("Rebel Trooper")).getByLabelText("Add copy")).not.toBeDisabled();
  });

  it("reports the deck full at `required`, not at 50", async () => {
    deckState.required = 60;
    deckState.cards["9999"] = 60;
    await renderAndSelectDeck("60/60");
    const add = within(tileFor("Rebel Trooper")).getByLabelText("Add copy");
    expect(add).toBeDisabled();
    expect(add.getAttribute("title")).toBe("Deck full (60)");
  });

  it("fills the leader slot via PATCH when a Leader card is added", async () => {
    await renderAndSelectDeck();
    const add = within(tileFor("Test Leader")).getByLabelText("Add copy");
    fireEvent.click(add);
    await waitFor(() => expect(patchFn).toHaveBeenCalledWith("d1", { leader_id: 100 }));
    // The rail's leader slot now shows the card (and the empty label is gone).
    const rail = document.querySelector(".deck-panel") as HTMLElement;
    expect(await within(rail).findByText("Test Leader")).toBeInTheDocument();
    expect(screen.queryByText("No leader")).not.toBeInTheDocument();
  });

  it("is browse-only when no deck is chosen", async () => {
    render(
      <SettingsProvider>
        <CardExplorer onBack={vi.fn()} />
      </SettingsProvider>,
    );
    await waitFor(() => expect(screen.getByText("Rebel Trooper")).toBeInTheDocument());
    // With nothing selected in "Adding to" the explorer offers no add/remove
    // controls at all — see the Cell contract in CardExplorer.tsx. Cards still
    // render, so browsing works; there is just nothing to edit and therefore no
    // server call.
    expect(within(tileFor("Rebel Trooper")).queryByLabelText("Add copy")).toBeNull();
    expect(within(tileFor("Rebel Trooper")).queryByLabelText("Remove copy")).toBeNull();
    expect(cardsFn).not.toHaveBeenCalled();
  });
});
