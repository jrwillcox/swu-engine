// TutorialScreen: the on-rails C-3PO tutorial advances through its scripted
// steps, gates the "choose 2 resources" step until two cards are tapped, handles
// the mulligan choice, supports Back, and exits via Skip / the final step. Also
// checks the "How to Play" button wires up on NewGameScreen.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// NewGameScreen loads its deck list from the API; stub it (empty is fine here).
vi.mock("../src/api/client", () => ({ api: { decks: vi.fn(async () => []) } }));

import { TutorialScreen } from "../src/components/tutorial/TutorialScreen";
import { STEPS } from "../src/components/tutorial/steps";
import { NewGameScreen } from "../src/components/NewGameScreen";

// Click whichever advance control the current step offers (Next / Place / Start).
function advance() {
  const btn = screen.queryByRole("button", { name: /Next|Place resources|Start playing/ });
  if (btn) fireEvent.click(btn);
  return btn;
}
function advanceUntil(found: () => boolean, cap = 40) {
  for (let n = 0; n < cap && !found(); n++) advance();
}
function keepHand() {
  fireEvent.click(screen.getByRole("button", { name: /Keep hand/ }));
}
function pickTwoResources() {
  fireEvent.click(screen.getByAltText("Death Star Stormtrooper"));
  fireEvent.click(screen.getByAltText("Snowtrooper Lieutenant"));
}

describe("TutorialScreen", () => {
  it("opens on the C-3PO intro and advances on Next", () => {
    render(<TutorialScreen onExit={vi.fn()} />);
    expect(screen.getByText(/cyborg relations/)).toBeInTheDocument();
    expect(screen.getByText("Tutorial · Welcome")).toBeInTheDocument();
    advance();
    expect(screen.getByText("Tutorial · Step 1 of 15")).toBeInTheDocument();
  });

  it("disables Back on the first step and re-enables it after advancing", () => {
    render(<TutorialScreen onExit={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Back/ })).toBeDisabled();
    advance();
    expect(screen.getByRole("button", { name: /Back/ })).not.toBeDisabled();
  });

  it("gates the resource step until two cards are tapped, then advances", () => {
    render(<TutorialScreen onExit={vi.fn()} />);
    advanceUntil(() => !!screen.queryByRole("button", { name: /Keep hand/ }));
    keepHand(); // → resources step
    expect(screen.getByText(/choose! Tap/)).toBeInTheDocument();
    // no advance control until two cards are chosen
    expect(screen.queryByRole("button", { name: /Place resources/ })).toBeNull();
    fireEvent.click(screen.getByAltText("Death Star Stormtrooper"));
    expect(screen.queryByRole("button", { name: /Place resources/ })).toBeNull();
    fireEvent.click(screen.getByAltText("Snowtrooper Lieutenant"));
    fireEvent.click(screen.getByRole("button", { name: /Place resources/ }));
    expect(screen.getByText(/costs 2/)).toBeInTheDocument(); // the "play a unit" step
  });

  it("plays through every step and exits via the final 'Start playing'", () => {
    const onExit = vi.fn();
    render(<TutorialScreen onExit={onExit} />);
    for (let n = 0; n <= STEPS.length; n++) {
      if (screen.queryByRole("button", { name: /Keep hand/ })) {
        keepHand();
        continue;
      }
      if (
        screen.queryByText(/choose! Tap/) &&
        !screen.queryByRole("button", { name: /Place resources/ })
      ) {
        pickTwoResources();
      }
      advance();
    }
    expect(onExit).toHaveBeenCalled();
    expect(screen.getByText(/Vader leads the assault/)).toBeInTheDocument();
  });

  it("Back returns to the previous step", () => {
    render(<TutorialScreen onExit={vi.fn()} />);
    advance();
    advance();
    expect(screen.getByText("Tutorial · Step 2 of 15")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(screen.getByText("Tutorial · Step 1 of 15")).toBeInTheDocument();
  });

  it("exits when Skip is clicked", () => {
    const onExit = vi.fn();
    render(<TutorialScreen onExit={onExit} />);
    fireEvent.click(screen.getByRole("button", { name: /Skip tutorial/ }));
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("reaches the Sentinel keyword lesson", () => {
    render(<TutorialScreen onExit={vi.fn()} />);
    advanceUntil(() => !!screen.queryByRole("button", { name: /Keep hand/ }));
    keepHand();
    pickTwoResources();
    advanceUntil(() => !!screen.queryByText(/be attacked before/));
    expect(screen.getByText(/be attacked before/)).toBeInTheDocument();
    expect(screen.getAllByText(/C-3PO/).length).toBeGreaterThan(0);
  });
});

describe("NewGameScreen Tutorial button", () => {
  it("calls onOpenTutorial when clicked", () => {
    const onOpenTutorial = vi.fn();
    render(
      <NewGameScreen onStart={vi.fn()} busy={false} error={null} onOpenTutorial={onOpenTutorial} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Tutorial/ }));
    expect(onOpenTutorial).toHaveBeenCalledTimes(1);
  });
});
