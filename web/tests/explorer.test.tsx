// CardExplorer: filters narrow the grid, the availability badge reflects the
// playable flag, and the per-card stepper caps copies at 3 (deck-builder seam).
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ExplorerResponse } from "../src/api/types";

const CATALOG: ExplorerResponse = {
  cards: [
    {
      id: 1,
      set_code: "SOR",
      card_number: "5",
      name: "Luke Skywalker",
      subtitle: "Faithful Friend",
      type: "Leader",
      rarity: "Special",
      cost: 6,
      power: 4,
      hp: 7,
      unique: true,
      aspects: ["Heroism"],
      keywords: [],
      traits: ["Force"],
      arenas: ["Ground"],
      status: "implemented",
      playable: true,
      decks: ["luke"],
      image_url: null,
      back_image_url: "/api/cards/1/image?face=back",
      variants: {
        hyperspace: {
          image_url: "/api/cards/1/image?face=front&variant=hyperspace",
          back_image_url: "/api/cards/1/image?face=back&variant=hyperspace",
        },
      },
    },
    {
      id: 2,
      set_code: "SOR",
      card_number: "9",
      name: "Cobb Vanth",
      subtitle: null,
      type: "Unit",
      rarity: "Rare",
      cost: 3,
      power: 2,
      hp: 4,
      unique: true,
      aspects: ["Cunning"],
      keywords: ["Ambush"],
      traits: [],
      arenas: ["Ground"],
      status: "text-bearing",
      playable: false,
      decks: [],
      image_url: null,
      back_image_url: null,
    },
  ],
  sets: [{ code: "SOR", name: "Spark of Rebellion" }],
  types: ["Leader", "Unit"],
  aspects: ["Cunning", "Heroism"],
  keywords: ["Ambush"],
  traits: ["Force"],
  decks: [{ key: "luke", label: "Luke starter" }],
};

vi.mock("../src/api/client", () => ({
  api: { catalog: vi.fn(async () => CATALOG) },
}));

import { CardExplorer } from "../src/components/CardExplorer";
import { SettingsProvider } from "../src/game/settings";

beforeEach(() => localStorage.clear());

// `showAvailability` (Settings → Card availability) is OFF by default; pass true
// to render the explorer as it looks with the availability UI switched on.
async function renderExplorer(showAvailability = false) {
  if (showAvailability) localStorage.setItem("swu.showAvail", "true");
  render(
    <SettingsProvider>
      <CardExplorer onBack={vi.fn()} />
    </SettingsProvider>,
  );
  await waitFor(() => expect(screen.getByText("Luke Skywalker")).toBeInTheDocument());
}

describe("CardExplorer", () => {
  it("lists all cards and the available-to-play badge", async () => {
    await renderExplorer(true);
    expect(screen.getByText("Luke Skywalker")).toBeInTheDocument();
    expect(screen.getByText("Cobb Vanth")).toBeInTheDocument();
    // One playable, one not.
    expect(screen.getByText("● Playable")).toBeInTheDocument();
    expect(screen.getByText("○ Not yet")).toBeInTheDocument();
  });

  it("hides the availability filter and badges by default", async () => {
    await renderExplorer();
    expect(screen.queryByLabelText("Available")).not.toBeInTheDocument();
    expect(screen.queryByText("● Playable")).not.toBeInTheDocument();
    expect(screen.queryByText("○ Not yet")).not.toBeInTheDocument();
    // Nothing is filtered out: both cards still show.
    expect(screen.getByText("Luke Skywalker")).toBeInTheDocument();
    expect(screen.getByText("Cobb Vanth")).toBeInTheDocument();
  });

  it("filters by availability", async () => {
    await renderExplorer(true);
    fireEvent.change(screen.getByLabelText("Available"), { target: { value: "yes" } });
    expect(screen.getByText("Luke Skywalker")).toBeInTheDocument();
    expect(screen.queryByText("Cobb Vanth")).not.toBeInTheDocument();
  });

  it("filters by keyword via the multi-select", async () => {
    await renderExplorer();
    fireEvent.click(screen.getByLabelText("Keyword"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Ambush" }));
    expect(screen.queryByText("Luke Skywalker")).not.toBeInTheDocument();
    expect(screen.getByText("Cobb Vanth")).toBeInTheDocument();
  });

  it("filters by trait via the multi-select (OR across selected traits)", async () => {
    await renderExplorer();
    // Open the Trait dropdown and tick "Force" — only the Force card survives.
    fireEvent.click(screen.getByLabelText("Trait"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Force" }));
    expect(screen.getByText("Luke Skywalker")).toBeInTheDocument();
    expect(screen.queryByText("Cobb Vanth")).not.toBeInTheDocument();
    // Clearing restores the full list.
    fireEvent.click(screen.getByRole("button", { name: /Clear/ }));
    expect(screen.getByText("Cobb Vanth")).toBeInTheDocument();
  });

  it("flips a leader to its back and switches art variants in the zoom", async () => {
    await renderExplorer();
    // Open the zoom for the leader (which has a back + a hyperspace variant).
    fireEvent.click(screen.getByTitle("Luke Skywalker"));
    const img = () => document.querySelector(".xzoom-art img") as HTMLImageElement | null;
    // Flip + variant controls are offered for a double-faced card with variants.
    expect(screen.getByText("Show back ⟳")).toBeInTheDocument();
    expect(screen.getByLabelText("Variant")).toBeInTheDocument();

    // Flip to the standard back.
    fireEvent.click(screen.getByText("Show back ⟳"));
    expect(img()!.getAttribute("src")).toBe("/api/cards/1/image?face=back");

    // Switch to the hyperspace variant — the back follows the variant's own art.
    fireEvent.change(screen.getByLabelText("Variant"), { target: { value: "hyperspace" } });
    expect(img()!.getAttribute("src")).toBe("/api/cards/1/image?face=back&variant=hyperspace");

    // Flip to the variant front.
    fireEvent.click(screen.getByText("Show front"));
    expect(img()!.getAttribute("src")).toBe("/api/cards/1/image?face=front&variant=hyperspace");
  });

  it("offers no flip or variant control for a single-faced card with no variants", async () => {
    await renderExplorer();
    fireEvent.click(screen.getByTitle("Cobb Vanth"));
    expect(screen.queryByText(/Show back/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Variant")).not.toBeInTheDocument();
  });

  it("offers no add/remove stepper while no deck is selected in 'Adding to'", async () => {
    await renderExplorer();
    // Browse-only: with no deck chosen, cards cannot be added to / removed from
    // anything, so the per-tile +/− stepper is absent entirely.
    expect(screen.queryByLabelText("Add copy")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Remove copy")).not.toBeInTheDocument();
  });
});
