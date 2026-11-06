// Render test: drive <Table/> from a recorded snapshot (no network) and assert
// the zones, a real card, and a legal action all surface.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Table } from "../src/components/Table";
import type { Game } from "../src/game/useGame";
import type { ActionModel } from "../src/api/types";
import { api } from "../src/api/client";
import { SettingsProvider } from "../src/game/settings";
import { action, card, snapshot, view, zone } from "./fixtures";

function fakeGame(over: Partial<Game> = {}): Game {
  return {
    snapshot: snapshot({
      view: view({
        my: zone("human", {
          ground_arena: [card({ instance_id: "g1", card_name: "Rebel Trooper" })],
        }),
      }),
      actions: [
        action("Pass", {}, "a0", "Pass"),
        action("AttackWithUnit", { attacker_id: "g1", defender_id: null }, "a1", "Attack base"),
      ],
    }),
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

function renderTable(game: Game) {
  return render(
    <SettingsProvider>
      <Table game={game} />
    </SettingsProvider>,
  );
}

describe("Leave game", () => {
  function openLeave(game: Game) {
    renderTable(game);
    fireEvent.click(screen.getByTitle("Settings"));
    fireEvent.click(screen.getByRole("button", { name: "Leave game" }));
  }

  it("asks first; confirming frees the game and returns to the start screen", () => {
    const del = vi.spyOn(api, "deleteGame").mockResolvedValue();
    const reset = vi.fn();
    openLeave(fakeGame({ reset }));
    const dialog = screen.getByText("Leave this game?").closest(".modal") as HTMLElement;
    expect(reset).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Leave game" }));
    expect(reset).toHaveBeenCalledOnce();
    expect(del).toHaveBeenCalledWith("g-test");
    del.mockRestore();
  });

  it("cancelling keeps the game", () => {
    const del = vi.spyOn(api, "deleteGame").mockResolvedValue();
    const reset = vi.fn();
    openLeave(fakeGame({ reset }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Leave this game?")).not.toBeInTheDocument();
    expect(reset).not.toHaveBeenCalled();
    expect(del).not.toHaveBeenCalled();
    del.mockRestore();
  });

  it("is not offered once the game is over", () => {
    renderTable(fakeGame({ snapshot: snapshot({ awaiting: "terminal", winner: "human" }) }));
    fireEvent.click(screen.getByTitle("Settings"));
    expect(screen.queryByRole("button", { name: "Leave game" })).not.toBeInTheDocument();
  });
});

describe("Table", () => {
  it("renders zone labels and a unit card", () => {
    renderTable(fakeGame());
    expect(screen.getByText(/Your Base/)).toBeInTheDocument();
    expect(screen.getByText(/Enemy Base/)).toBeInTheDocument();
    expect(screen.getByAltText("Rebel Trooper")).toBeInTheDocument();
  });

  it("shows the credit chip with a tooltip only when credits > 0", () => {
    const { rerender } = renderTable(fakeGame());
    // No credits -> no chip.
    expect(screen.queryByText(/🪙/)).not.toBeInTheDocument();
    // Holding credits -> chip with count + an explanatory tooltip.
    rerender(
      <SettingsProvider>
        <Table
          game={fakeGame({
            snapshot: snapshot({ view: view({ my: zone("human", { credits: 3 }) }) }),
          })}
        />
      </SettingsProvider>,
    );
    const chip = screen.getByText(/🪙\s*3/);
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveAttribute("title", expect.stringMatching(/Credit/i));
  });

  it("offers the Pass control and routes it to act()", () => {
    const act = vi.fn();
    renderTable(fakeGame({ act }));
    fireEvent.click(screen.getByRole("button", { name: "Pass" }));
    expect(act).toHaveBeenCalledWith("a0");
  });

  it("clicking a legal attacker with one base target attacks immediately", () => {
    const act = vi.fn();
    renderTable(fakeGame({ act }));
    // The unit is the subject of a single base-attack action -> direct execute.
    const unit = document.querySelector('[data-instance="g1"]') as HTMLElement;
    fireEvent.click(unit);
    expect(act).toHaveBeenCalledWith("a1");
  });

  // An upgrade in hand that can attach to a friendly unit (g1) or an enemy
  // unit (e1) — the latter is legal but almost always a misclick.
  function upgradeGame(act = vi.fn()): Game {
    return fakeGame({
      act,
      snapshot: snapshot({
        view: view({
          my: zone("human", {
            ground_arena: [card({ instance_id: "g1", card_name: "Rebel Trooper" })],
            hand: [
              card({
                instance_id: "u1",
                card_name: "Resilient",
                card_type: "Upgrade",
                zone: "HAND",
                upgrade_hp: 3, // a beneficial (+0/+3) upgrade — gated on enemy
              }),
            ],
          }),
          opponent: zone("bot", {
            ground_arena: [card({ instance_id: "e1", card_name: "Stormtrooper", owner_id: "bot" })],
          }),
        }),
        actions: [
          action(
            "PlayCard",
            { instance_id: "u1", upgrade_target_id: "g1" },
            "af",
            "Play on Rebel Trooper",
          ),
          action(
            "PlayCard",
            { instance_id: "u1", upgrade_target_id: "e1" },
            "ae",
            "Play on Stormtrooper",
          ),
        ],
      }),
    });
  }

  it("attaching an upgrade to an enemy unit asks for confirmation first", () => {
    const act = vi.fn();
    renderTable(upgradeGame(act));
    fireEvent.click(document.querySelector('[data-instance="u1"]') as HTMLElement);
    fireEvent.click(document.querySelector('[data-instance="e1"]') as HTMLElement);
    // No action yet — a confirm gate is shown instead.
    expect(act).not.toHaveBeenCalled();
    expect(screen.getByText(/Attach to an enemy unit\?/)).toBeInTheDocument();
    // Confirming dispatches the enemy-target action.
    fireEvent.click(screen.getByRole("button", { name: "Attach to enemy" }));
    expect(act).toHaveBeenCalledWith("ae");
  });

  it("cancelling the enemy-attach confirmation dispatches nothing", () => {
    const act = vi.fn();
    renderTable(upgradeGame(act));
    fireEvent.click(document.querySelector('[data-instance="u1"]') as HTMLElement);
    fireEvent.click(document.querySelector('[data-instance="e1"]') as HTMLElement);
    const dialog = screen
      .getByText(/Attach to an enemy unit\?/)
      .closest(".confirm-dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(act).not.toHaveBeenCalled();
    expect(screen.queryByText(/Attach to an enemy unit\?/)).not.toBeInTheDocument();
  });

  it("attaching a net-neutral (Bounty) upgrade to an enemy acts immediately, no prompt", () => {
    // A statless upgrade (e.g. a Bounty) on an enemy is the intended play, so the
    // enemy-attach confirm is skipped.
    const act = vi.fn();
    const game = fakeGame({
      act,
      snapshot: snapshot({
        view: view({
          my: zone("human", {
            hand: [
              card({
                instance_id: "b1",
                card_name: "Public Enemy",
                card_type: "Upgrade",
                zone: "HAND",
              }),
            ],
          }),
          opponent: zone("bot", {
            ground_arena: [card({ instance_id: "e1", card_name: "Stormtrooper", owner_id: "bot" })],
          }),
        }),
        actions: [
          action(
            "PlayCard",
            { instance_id: "b1", upgrade_target_id: "e1" },
            "abe",
            "Play on Stormtrooper",
          ),
        ],
      }),
    });
    renderTable(game);
    fireEvent.click(document.querySelector('[data-instance="b1"]') as HTMLElement);
    fireEvent.click(document.querySelector('[data-instance="e1"]') as HTMLElement);
    expect(act).toHaveBeenCalledWith("abe");
    expect(screen.queryByText(/Attach to an enemy unit\?/)).not.toBeInTheDocument();
  });

  it("attaching an upgrade to a friendly unit acts immediately, no prompt", () => {
    const act = vi.fn();
    renderTable(upgradeGame(act));
    fireEvent.click(document.querySelector('[data-instance="u1"]') as HTMLElement);
    fireEvent.click(document.querySelector('[data-instance="g1"]') as HTMLElement);
    expect(act).toHaveBeenCalledWith("af");
    expect(screen.queryByText(/Attach to an enemy unit\?/)).not.toBeInTheDocument();
  });

  // Smuggle: a resource carrying the Smuggle keyword is playable from the
  // resource zone. The resource row stays face-down, but the smuggleable card
  // lights up as a legal subject and clicking it dispatches the SmugglePlay.
  function smuggleGame(act = vi.fn()): Game {
    return fakeGame({
      act,
      snapshot: snapshot({
        view: view({
          my: zone("human", {
            resources: [
              card({
                instance_id: "r1",
                card_name: "Cassian Andor",
                zone: "RESOURCES",
                face_down: true,
              }),
              card({ instance_id: "r2", card_name: "Vanilla", zone: "RESOURCES", face_down: true }),
            ],
          }),
        }),
        actions: [
          action("Pass", {}, "a0", "Pass"),
          action(
            "SmugglePlay",
            { instance_id: "r1", upgrade_target_id: null },
            "s1",
            "Smuggle Cassian Andor",
          ),
        ],
      }),
    });
  }

  it("highlights only the smuggleable resource and dispatches SmugglePlay on click", () => {
    const act = vi.fn();
    renderTable(smuggleGame(act));
    const r1 = document.querySelector('[data-instance="r1"]') as HTMLElement;
    const r2 = document.querySelector('[data-instance="r2"]') as HTMLElement;
    // The Smuggle subject is highlighted + clickable; the plain resource is not.
    expect(r1.className).toContain("hl-legal");
    expect(r1.className).toContain("clickable");
    expect(r2.className).not.toContain("hl-legal");
    // A single smuggle action -> clicking the resource executes it immediately.
    fireEvent.click(r1);
    expect(act).toHaveBeenCalledWith("s1");
  });

  // Two-stage resourcing: SETUP_RESOURCES offers a ResourceCard per hand card;
  // clicking stages locally and only Confirm commits the batch.
  function resourceGame(resourceCards = vi.fn()): Game {
    return fakeGame({
      resourceCards,
      snapshot: snapshot({
        view: view({
          phase: "SETUP_RESOURCES",
          round_number: 1,
          my: zone("human", {
            hand: [
              card({ instance_id: "h1", card_name: "Card One", zone: "HAND" }),
              card({ instance_id: "h2", card_name: "Card Two", zone: "HAND" }),
              card({ instance_id: "h3", card_name: "Card Three", zone: "HAND" }),
            ],
          }),
        }),
        actions: [
          action("ResourceCard", { instance_id: "h1" }, "r1"),
          action("ResourceCard", { instance_id: "h2" }, "r2"),
          action("ResourceCard", { instance_id: "h3" }, "r3"),
        ],
      }),
    });
  }

  it("staging resources commits nothing until Confirm, then dispatches the batch", () => {
    const resourceCards = vi.fn();
    const act = vi.fn();
    renderTable(resourceGame(resourceCards));
    // Click two hand cards — they should stage, not commit.
    fireEvent.click(document.querySelector('[data-instance="h1"]') as HTMLElement);
    fireEvent.click(document.querySelector('[data-instance="h3"]') as HTMLElement);
    expect(resourceCards).not.toHaveBeenCalled();
    expect(act).not.toHaveBeenCalled();
    // Both staged cards carry the pending-resource highlight.
    expect(document.querySelectorAll(".card.hl-staged")).toHaveLength(2);
    // Confirm now dispatches exactly the staged ids, in click order.
    fireEvent.click(screen.getByRole("button", { name: /confirm resources \(2\/2\)/i }));
    expect(resourceCards).toHaveBeenCalledWith(["h1", "h3"]);
  });

  it("Confirm is disabled until the required number of cards are staged", () => {
    renderTable(resourceGame());
    const confirm = () =>
      screen.getByRole("button", { name: /confirm resources/i }) as HTMLButtonElement;
    expect(confirm()).toBeDisabled();
    fireEvent.click(document.querySelector('[data-instance="h1"]') as HTMLElement);
    expect(confirm()).toBeDisabled(); // 1/2
    fireEvent.click(document.querySelector('[data-instance="h2"]') as HTMLElement);
    expect(confirm()).toBeEnabled(); // 2/2
  });

  it("clicking a staged card again un-stages it", () => {
    renderTable(resourceGame());
    const h1 = () => document.querySelector('[data-instance="h1"]') as HTMLElement;
    fireEvent.click(h1());
    expect(h1().className).toContain("hl-staged");
    fireEvent.click(h1());
    expect(h1().className).not.toContain("hl-staged");
  });

  it("renders the new-round turn gate and routes Start to dismissTurnGate", () => {
    const dismissTurnGate = vi.fn();
    renderTable(fakeGame({ turnGate: 3, dismissTurnGate }));
    expect(screen.getByRole("heading", { name: "Round 3 begins" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /start round/i }));
    expect(dismissTurnGate).toHaveBeenCalled();
  });

  // reveal_top (For a Cause I Believe In): the overlay shows the revealed cards
  // with per-card Keep/Discard buttons instead of a spill-over row of opaque
  // "keep human_41 on top" controls.
  function revealGame(act = vi.fn()): Game {
    return fakeGame({
      act,
      snapshot: snapshot({
        prompt: "Revealed cards — discard any, then keep the rest on top.",
        view: view({
          pending_decisions: [
            {
              deciding_player_id: "human",
              kind: "reveal_top",
              is_mine: true,
              context: {
                revealed: [
                  { instance_id: "d1", card_id: 11, card_name: "R2-D2" },
                  { instance_id: "d2", card_id: 12, card_name: "Open Fire" },
                ],
                pending: ["d1", "d2"],
                kept_order: [],
              },
            },
          ],
        }),
        actions: [
          action("KeepRevealed", { card_id: "d1" }, "k1", "Keep R2-D2 on top"),
          action("DiscardRevealed", { card_id: "d1" }, "x1", "Discard R2-D2"),
          action("KeepRevealed", { card_id: "d2" }, "k2", "Keep Open Fire on top"),
          action("DiscardRevealed", { card_id: "d2" }, "x2", "Discard Open Fire"),
        ],
      }),
    });
  }

  it("renders the reveal_top overlay with the actual revealed cards", () => {
    renderTable(revealGame());
    expect(screen.getByRole("heading", { name: /Top 2 cards of your deck/ })).toBeInTheDocument();
    expect(screen.getByAltText("R2-D2")).toBeInTheDocument();
    expect(screen.getByAltText("Open Fire")).toBeInTheDocument();
  });

  it("routes a per-card Keep to the matching action id", () => {
    const act = vi.fn();
    renderTable(revealGame(act));
    // Two "Keep on top" buttons (one per pending card); the first is R2-D2's.
    const keeps = screen.getAllByRole("button", { name: "Keep on top" });
    expect(keeps).toHaveLength(2);
    fireEvent.click(keeps[0]);
    expect(act).toHaveBeenCalledWith("k1");
  });

  it("shows the opponent-turn waiting state and no action buttons", () => {
    renderTable(
      fakeGame({
        snapshot: snapshot({ awaiting: "bot", actor_id: "bot" }),
        locked: true,
      }),
    );
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
  });

  it("shows a +N aspect-penalty pill on an off-aspect hand card, none on an on-aspect one", () => {
    renderTable(
      fakeGame({
        snapshot: snapshot({
          view: view({
            my: zone("human", {
              hand: [
                card({
                  instance_id: "h1",
                  card_name: "Jyn Erso",
                  zone: "HAND",
                  cost: 2,
                  aspect_penalty: 2,
                }),
                card({
                  instance_id: "h2",
                  card_name: "On Aspect",
                  zone: "HAND",
                  cost: 1,
                  aspect_penalty: 0,
                }),
              ],
            }),
          }),
        }),
      }),
    );
    // The off-aspect card surfaces a "+2" surcharge pill; the on-aspect one does not.
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.queryByText("+0")).not.toBeInTheDocument();
  });

  it("shows a smuggle-cost badge (base + red +N) on an off-aspect smuggle resource", () => {
    renderTable(
      fakeGame({
        snapshot: snapshot({
          view: view({
            my: zone("human", {
              // Off-aspect smuggle (3 base + 2 penalty) and a plain resource.
              resources: [
                card({
                  instance_id: "r1",
                  zone: "RESOURCES",
                  face_down: true,
                  smuggle_base: 3,
                  smuggle_penalty: 2,
                }),
                card({ instance_id: "r2", zone: "RESOURCES", face_down: true }),
              ],
            }),
          }),
        }),
      }),
    );
    expect(screen.getByText("3")).toBeInTheDocument(); // base smuggle cost
    expect(screen.getByText("+2")).toBeInTheDocument(); // aspect surcharge
  });

  function decisionGame(
    decision: { kind: string; context: Record<string, unknown> },
    actions: ActionModel[],
    act = vi.fn(),
  ): Game {
    return fakeGame({
      act,
      snapshot: snapshot({
        view: view({
          pending_decisions: [{ deciding_player_id: "human", is_mine: true, ...decision }],
        }),
        actions,
      }),
    });
  }

  it("shows the opponent's hand for a look_hand decision and acks it", () => {
    const act = vi.fn();
    renderTable(
      decisionGame(
        {
          kind: "look_hand",
          context: {
            revealed_hand: [
              { card_id: 5, card_name: "Sneaky Plan" },
              { card_id: 6, card_name: "Hidden Threat" },
            ],
          },
        },
        [action("AckLookHand", {}, "a0", "Done looking")],
        act,
      ),
    );
    expect(screen.getByText(/Opponent's hand/)).toBeInTheDocument();
    expect(screen.getByAltText("Sneaky Plan")).toBeInTheDocument();
    expect(screen.getByAltText("Hidden Threat")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(act).toHaveBeenCalledWith("a0");
  });

  it("shows deck_search candidates and routes a pick", () => {
    const act = vi.fn();
    renderTable(
      decisionGame(
        {
          kind: "deck_search",
          context: {
            candidates: [{ instance_id: "d1", card_id: 9, card_name: "Tutored Unit" }],
          },
        },
        [
          action("SelectSearchCard", { instance_id: "d1" }, "a0", "Take Tutored Unit"),
          action("FinishSearch", {}, "a1", "Finish"),
        ],
        act,
      ),
    );
    fireEvent.click(screen.getByTitle("Tutored Unit"));
    expect(act).toHaveBeenCalledWith("a0");
  });

  it("shows return_from_discard candidates and routes a pick", () => {
    const act = vi.fn();
    renderTable(
      decisionGame(
        {
          kind: "return_from_discard",
          context: {
            candidates: [{ instance_id: "x1", card_id: 4, card_name: "Old Upgrade" }],
          },
        },
        [
          action("SelectDiscardCard", { instance_id: "x1" }, "a0", "Return Old Upgrade"),
          action("FinishReturnFromDiscard", {}, "a1", "Done"),
        ],
        act,
      ),
    );
    fireEvent.click(screen.getByTitle("Old Upgrade"));
    expect(act).toHaveBeenCalledWith("a0");
  });

  it("shows a discard-played play_from_hand candidate (Gideon's Light Cruiser)", () => {
    const act = vi.fn();
    renderTable(
      decisionGame(
        {
          kind: "play_from_hand",
          context: {
            discard_candidates: [{ instance_id: "p1", card_id: 7, card_name: "Free Villain" }],
          },
        },
        [action("PlayFromHand", { instance_id: "p1" }, "a0", "Play Free Villain")],
        act,
      ),
    );
    fireEvent.click(screen.getByTitle("Free Villain"));
    expect(act).toHaveBeenCalledWith("a0");
  });
});
