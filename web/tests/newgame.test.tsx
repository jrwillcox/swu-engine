// NewGameScreen: the difficulty selector renders, persists to / restores from
// localStorage, defaults to Normal, and is included in the start request; the two
// deck dropdowns group Official / Custom (Stage 6) and post the selected key.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Stub the API client so the screen can load its deck list without a network.
vi.mock("../src/api/client", () => ({
  api: {
    decks: vi.fn(async () => [
      {
        key: "luke",
        label: "Luke",
        leader_name: "Luke Skywalker",
        base_name: "Tower",
        kind: "official",
      },
      {
        key: "vader",
        label: "Vader",
        leader_name: "Darth Vader",
        base_name: "Command",
        kind: "official",
      },
      {
        key: "custom:alice:20260702-1200-my-deck",
        label: "My Deck (custom)",
        leader_name: "Han Solo",
        base_name: "Chopper Base",
        kind: "custom",
      },
    ]),
  },
}));

import { NewGameScreen } from "../src/components/NewGameScreen";

beforeEach(() => {
  localStorage.clear();
});

async function renderScreen(onStart = vi.fn()) {
  render(<NewGameScreen onStart={onStart} busy={false} error={null} />);
  // Wait for the deck list to load so "Start game" is enabled.
  await waitFor(() => expect(screen.getByText("Start game")).not.toBeDisabled());
  return onStart;
}

describe("NewGameScreen difficulty selector", () => {
  it("renders all three difficulties and defaults to Normal", async () => {
    await renderScreen();
    const select = screen.getByLabelText("Difficulty") as HTMLSelectElement;
    const labels = Array.from(select.options).map((o) => o.textContent);
    expect(labels).toEqual(["Easy", "Normal", "Hard"]);
    expect(select.value).toBe("normal");
  });

  it("posts the selected difficulty in the start request", async () => {
    const onStart = await renderScreen();
    fireEvent.change(screen.getByLabelText("Difficulty"), {
      target: { value: "hard" },
    });
    fireEvent.click(screen.getByText("Start game"));
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onStart.mock.calls[0][0]).toMatchObject({ difficulty: "hard" });
  });

  it("persists the choice to localStorage", async () => {
    await renderScreen();
    fireEvent.change(screen.getByLabelText("Difficulty"), {
      target: { value: "easy" },
    });
    expect(localStorage.getItem("swu.difficulty")).toBe("easy");
  });

  it("restores the persisted choice on next load", async () => {
    localStorage.setItem("swu.difficulty", "hard");
    const onStart = await renderScreen();
    // Pre-selected from storage…
    expect((screen.getByLabelText("Difficulty") as HTMLSelectElement).value).toBe("hard");
    // …and sent without re-selecting.
    fireEvent.click(screen.getByText("Start game"));
    expect(onStart.mock.calls[0][0]).toMatchObject({ difficulty: "hard" });
  });

  it("falls back to Normal when storage holds garbage", async () => {
    localStorage.setItem("swu.difficulty", "bogus");
    await renderScreen();
    expect((screen.getByLabelText("Difficulty") as HTMLSelectElement).value).toBe("normal");
  });
});

describe("NewGameScreen deck dropdowns", () => {
  it("groups Official and Custom decks in both dropdowns", async () => {
    await renderScreen();
    const you = screen.getByLabelText("Your deck") as HTMLSelectElement;
    const groups = you.querySelectorAll("optgroup");
    expect(Array.from(groups).map((g) => g.label)).toEqual(["Official", "Custom"]);
    // Officials first, then the custom.
    const opts = Array.from(you.options).map((o) => o.value);
    expect(opts).toEqual(["luke", "vader", "custom:alice:20260702-1200-my-deck"]);
  });

  it("defaults You to the first deck and Opponent to the second", async () => {
    await renderScreen();
    expect((screen.getByLabelText("Your deck") as HTMLSelectElement).value).toBe("luke");
    expect((screen.getByLabelText("Opponent deck") as HTMLSelectElement).value).toBe("vader");
  });

  it("posts the selected custom deck key for either seat", async () => {
    const onStart = await renderScreen();
    fireEvent.change(screen.getByLabelText("Your deck"), {
      target: { value: "custom:alice:20260702-1200-my-deck" },
    });
    fireEvent.click(screen.getByText("Start game"));
    expect(onStart.mock.calls[0][0]).toMatchObject({
      human: { kind: "human", deck: "custom:alice:20260702-1200-my-deck" },
      bot: { kind: "weighted_bot", deck: "vader" },
    });
  });
});
