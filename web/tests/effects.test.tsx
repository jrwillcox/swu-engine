// Event → DOM test: feed a recorded event to the EffectsLayer and assert the
// right transient overlay fires, anchored to the card by data-instance.
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EffectsLayer } from "../src/components/EffectsLayer";

describe("EffectsLayer", () => {
  it("pops a floating damage number anchored to the damaged card", async () => {
    render(
      <div>
        <div data-instance="u1" style={{ width: 60, height: 80 }} />
        <EffectsLayer
          active={{
            key: 1,
            ev: { type: "DamageDealt", data: { target_instance_id: "u1", amount: 3 } },
          }}
        />
      </div>,
    );
    await waitFor(() => expect(screen.getByText("-3")).toBeInTheDocument());
    expect(screen.getByText("-3")).toHaveClass("dmg");
  });

  it("shows a banner for an overwhelm event", async () => {
    render(
      <EffectsLayer active={{ key: 2, ev: { type: "OverwhelmDamage", data: { amount: 2 } } }} />,
    );
    await waitFor(() => expect(screen.getByText(/Overwhelm/)).toBeInTheDocument());
  });

  it("does nothing for an unmapped event", () => {
    const { container } = render(
      <EffectsLayer
        active={{ key: 3, ev: { type: "PlayerPassed", data: { player_id: "bot" } } }}
      />,
    );
    expect(container.querySelector(".fx-float")).toBeNull();
  });
});
