// The enlarged hover/inspect zoom surfaces the aspect-cost penalty: a "+N" pill
// on the art and a labelled "Aspect cost penalty" chip beneath it.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CardZoom } from "../src/components/ui";
import { SettingsProvider } from "../src/game/settings";
import { card } from "./fixtures";

function renderZoom(c: ReturnType<typeof card>) {
  // anchored=false renders the centred (touch) zoom — no DOM positioning needed.
  return render(
    <SettingsProvider>
      <CardZoom card={c} anchored={false} />
    </SettingsProvider>,
  );
}

describe("CardZoom aspect-cost penalty", () => {
  it("shows the +N pill and the labelled chip for an off-aspect card", () => {
    renderZoom(card({ instance_id: "h1", card_name: "Jyn Erso", cost: 2, aspect_penalty: 2 }));
    // The "+2" appears twice (pill on the art + badge in the chip).
    expect(screen.getAllByText("+2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Aspect cost penalty")).toBeInTheDocument();
  });

  it("shows nothing extra for an on-aspect card", () => {
    renderZoom(card({ instance_id: "h2", card_name: "On Aspect", cost: 1, aspect_penalty: 0 }));
    expect(screen.queryByText("Aspect cost penalty")).not.toBeInTheDocument();
    expect(screen.queryByText("+0")).not.toBeInTheDocument();
  });

  it("shows a labelled Smuggle cost chip (base + red +N) for a smuggle resource", () => {
    renderZoom(
      card({ instance_id: "r1", card_name: "Hotshot DL-44", smuggle_base: 3, smuggle_penalty: 2 }),
    );
    expect(screen.getByText("Smuggle cost")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // base bracket cost
    expect(screen.getByText("+2")).toBeInTheDocument(); // aspect surcharge
  });

  it("omits the surcharge badge for an on-aspect smuggle resource", () => {
    renderZoom(
      card({ instance_id: "r2", card_name: "Privateer Crew", smuggle_base: 6, smuggle_penalty: 0 }),
    );
    expect(screen.getByText("Smuggle cost")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.queryByText("+0")).not.toBeInTheDocument();
  });
});
