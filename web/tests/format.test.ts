import { describe, expect, it } from "vitest";
import { formatEvent } from "../src/game/format";

describe("event formatting", () => {
  it("renders a defeat as a 'bad' line", () => {
    const l = formatEvent({ type: "UnitDefeated", data: { card_name: "Stormtrooper" } });
    expect(l?.tone).toBe("bad");
    expect(l?.text).toMatch(/Stormtrooper/);
  });

  it("translates player ids to You/Opponent", () => {
    const mine = formatEvent({
      type: "CardPlayed",
      data: { player_id: "human", card_name: "X-Wing", cost_paid: 3 },
    });
    const theirs = formatEvent({
      type: "CardPlayed",
      data: { player_id: "bot", card_name: "TIE", cost_paid: 2 },
    });
    expect(mine?.text).toMatch(/^You/);
    expect(theirs?.text).toMatch(/^Opponent/);
  });

  it("suppresses noisy bookkeeping events", () => {
    expect(formatEvent({ type: "DecisionPushed", data: {} })).toBeNull();
    expect(formatEvent({ type: "HandDrawn", data: {} })).toBeNull();
  });
});
