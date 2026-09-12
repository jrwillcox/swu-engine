// CardExplorer "List" view: the Cards/List toggle on the filter row, the details
// table's columns, and its sortable headings (text, numeric, blanks-last).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ExplorerCard, ExplorerResponse } from "../src/api/types";

function card(c: Partial<ExplorerCard> & { id: number; name: string }): ExplorerCard {
  return {
    set_code: "SOR",
    card_number: String(c.id),
    subtitle: null,
    type: "Unit",
    rarity: "Common",
    cost: null,
    power: null,
    hp: null,
    unique: false,
    aspects: [],
    keywords: [],
    traits: [],
    arenas: [],
    status: "implemented",
    playable: true,
    decks: [],
    image_url: null,
    back_image_url: null,
    ...c,
  };
}

const CATALOG: ExplorerResponse = {
  cards: [
    card({
      id: 1,
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
      traits: ["Force"],
      arenas: ["Ground"],
    }),
    card({
      id: 2,
      card_number: "9",
      name: "Cobb Vanth",
      cost: 3,
      power: 2,
      hp: 4,
      rarity: "Rare",
      aspects: ["Cunning"],
      keywords: ["Ambush"],
      arenas: ["Ground"],
      playable: false,
      status: "text-bearing",
    }),
    // No power/HP at all — an Event must sink to the bottom of a stat sort
    // whichever way that column points.
    card({
      id: 3,
      card_number: "20",
      name: "Vanquish",
      type: "Event",
      cost: 5,
      aspects: ["Vigilance"],
    }),
    card({
      id: 4,
      card_number: "31",
      name: "Green Squadron A-Wing",
      cost: 2,
      power: 3,
      hp: 3,
      keywords: ["Raid 1"],
      arenas: ["Space"],
    }),
  ],
  sets: [{ code: "SOR", name: "Spark of Rebellion" }],
  types: ["Event", "Leader", "Unit"],
  aspects: ["Cunning", "Heroism", "Vigilance"],
  keywords: ["Ambush", "Raid 1"],
  traits: ["Force"],
  decks: [],
};

vi.mock("../src/api/client", () => ({
  api: { catalog: vi.fn(async () => CATALOG) },
}));

import { CardExplorer } from "../src/components/CardExplorer";
import { SettingsProvider } from "../src/game/settings";

beforeEach(() => localStorage.clear());

async function renderExplorer(showAvailability = false) {
  if (showAvailability) localStorage.setItem("swu.showAvail", "true");
  render(
    <SettingsProvider>
      <CardExplorer onBack={vi.fn()} />
    </SettingsProvider>,
  );
  await waitFor(() => expect(screen.getByText("Vanquish")).toBeInTheDocument());
}

const listBtn = () => screen.getByRole("button", { name: /List/ });
const cardsBtn = () => screen.getByRole("button", { name: /Cards/ });
// Column headings, scoped to the table — several share a name with a filter
// dropdown ("Type", "Cost", …) sitting in the filter row above.
const head = (label: string) =>
  within(document.querySelector(".xlist thead") as HTMLElement).getByRole("button", {
    name: new RegExp(`^${label}`),
  });
const noHead = (label: string) =>
  within(document.querySelector(".xlist thead") as HTMLElement).queryByRole("button", {
    name: new RegExp(`^${label}`),
  });

// Row order, by the name column (the ◆ unique marker lives in that cell too).
const names = () =>
  [...document.querySelectorAll(".xlist-name")].map((e) => e.textContent!.replace("◆", "").trim());

// One row's cells, in column order.
function row(name: string): string[] {
  const cell = [...document.querySelectorAll(".xlist-name")].find(
    (e) => e.textContent!.replace("◆", "").trim() === name,
  );
  return [...cell!.closest("tr")!.querySelectorAll("td")].map((td) =>
    td.textContent!.replace("◆", "").trim(),
  );
}

describe("CardExplorer list view", () => {
  it("starts in thumbnail mode and switches to the details table", async () => {
    await renderExplorer();
    expect(document.querySelector(".explorer-grid")).toBeInTheDocument();
    expect(document.querySelector(".xlist")).not.toBeInTheDocument();

    fireEvent.click(listBtn());
    expect(document.querySelector(".xlist")).toBeInTheDocument();
    expect(document.querySelector(".explorer-grid")).not.toBeInTheDocument();
    expect(listBtn()).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(cardsBtn());
    expect(document.querySelector(".explorer-grid")).toBeInTheDocument();
  });

  it("remembers the chosen view across mounts", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    expect(localStorage.getItem("swu.explorerView")).toBe("list");

    screen.getByRole("button", { name: "← Back" }); // sanity: same screen
    document.body.innerHTML = "";
    await renderExplorer();
    expect(document.querySelector(".xlist")).toBeInTheDocument();
  });

  it("shows cost/power/HP and the rest of the stats per row", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    for (const label of [
      "Set №",
      "Name",
      "Subtitle",
      "Type",
      "Arena",
      "Cost",
      "Power",
      "HP",
      "Aspects",
      "Keywords",
      "Traits",
      "Rarity",
    ]) {
      expect(head(label)).toBeInTheDocument();
    }
    expect(document.querySelectorAll(".xlist tbody tr")).toHaveLength(4);
    expect(row("Luke Skywalker")).toEqual([
      "SOR 5",
      "Luke Skywalker",
      "Faithful Friend",
      "Leader",
      "Ground",
      "6",
      "4",
      "7",
      "Heroism",
      "",
      "Force",
      "Special",
    ]);
    // A statless Event leaves the numeric cells blank rather than printing 0.
    expect(row("Vanquish").slice(5, 8)).toEqual(["5", "", ""]);
  });

  it("sorts by name by default and flips the column on a second click", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    expect(names()).toEqual(["Cobb Vanth", "Green Squadron A-Wing", "Luke Skywalker", "Vanquish"]);
    fireEvent.click(head("Name"));
    expect(names()).toEqual(["Vanquish", "Luke Skywalker", "Green Squadron A-Wing", "Cobb Vanth"]);
  });

  it("sorts the stat columns numerically, blanks always last", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());

    fireEvent.click(head("Cost"));
    expect(names()).toEqual(["Green Squadron A-Wing", "Cobb Vanth", "Vanquish", "Luke Skywalker"]);

    fireEvent.click(head("Power"));
    expect(names()).toEqual(["Cobb Vanth", "Green Squadron A-Wing", "Luke Skywalker", "Vanquish"]);
    fireEvent.click(head("Power")); // descending — the powerless Event still sinks
    expect(names()).toEqual(["Luke Skywalker", "Green Squadron A-Wing", "Cobb Vanth", "Vanquish"]);
  });

  it("keeps every filter working in list mode", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    fireEvent.click(screen.getByLabelText("Keyword"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Ambush" }));
    expect(names()).toEqual(["Cobb Vanth"]);
  });

  it("resets the sort along with the filters, staying in list mode", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    fireEvent.click(head("Cost"));
    fireEvent.click(head("Cost")); // most expensive first
    fireEvent.click(screen.getByLabelText("Keyword"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Ambush" }));
    expect(names()).toEqual(["Cobb Vanth"]);

    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(document.querySelector(".xlist")).toBeInTheDocument();
    expect(names()).toEqual(["Cobb Vanth", "Green Squadron A-Wing", "Luke Skywalker", "Vanquish"]);
    expect(head("Name").closest("th")).toHaveAttribute("aria-sort", "ascending");
    expect(head("Cost").closest("th")).toHaveAttribute("aria-sort", "none");
  });

  it("shows the availability column only when that setting is on", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    expect(noHead("Available")).not.toBeInTheDocument();

    document.body.innerHTML = "";
    await renderExplorer(true);
    fireEvent.click(listBtn());
    expect(head("Available")).toBeInTheDocument();
    const cobb = row("Cobb Vanth");
    expect(cobb[cobb.length - 1]).toBe("○ Not yet");
    const luke = row("Luke Skywalker");
    expect(luke[luke.length - 1]).toBe("● Playable");
  });

  it("opens the card zoom when a row is clicked", async () => {
    await renderExplorer();
    fireEvent.click(listBtn());
    fireEvent.click(document.querySelector(".xlist tbody tr")!);
    expect(document.querySelector(".xzoom")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Cobb Vanth/ })).toBeInTheDocument();
  });
});
