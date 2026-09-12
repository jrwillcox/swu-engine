import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { pickVariant, artFor, type VariantMode } from "../src/game/variants";
import { Card } from "../src/components/Card";
import { SettingsProvider } from "../src/game/settings";
import type { CardModel } from "../src/api/types";

function card(overrides: Partial<CardModel> = {}): CardModel {
  return {
    instance_id: "human_7",
    card_id: 1,
    card_name: "Test",
    card_type: "Unit",
    owner_id: "human",
    zone: "ground",
    exhausted: false,
    damage: 0,
    face_down: false,
    deployed: false,
    epic_action_spent: false,
    effective_power: 2,
    effective_hp: 3,
    cost: 2,
    attached_upgrades: [],
    keywords: [],
    image_url: "/std-front",
    back_image_url: null,
    ...overrides,
  };
}

const ALL_VARIANTS = {
  hyperspace: { image_url: "/hyp-front", back_image_url: "/hyp-back" },
  hyperspace_foil: { image_url: "/hypfoil-front", back_image_url: null },
  showcase: { image_url: "/show-front", back_image_url: "/show-back" },
};

describe("pickVariant", () => {
  it("standard mode always uses base art (null)", () => {
    expect(pickVariant(card({ variants: ALL_VARIANTS }), "standard")).toBeNull();
  });

  it("a card with no variants returns null in every mode", () => {
    const modes: VariantMode[] = ["standard", "best", "random", "lottery"];
    for (const m of modes) expect(pickVariant(card(), m)).toBeNull();
  });

  it("best picks showcase > hyperspace_foil > hyperspace", () => {
    expect(pickVariant(card({ variants: ALL_VARIANTS }), "best")).toBe(ALL_VARIANTS.showcase);
    const noShowcase = {
      hyperspace: ALL_VARIANTS.hyperspace,
      hyperspace_foil: ALL_VARIANTS.hyperspace_foil,
    };
    expect(pickVariant(card({ variants: noShowcase }), "best")).toBe(ALL_VARIANTS.hyperspace_foil);
    const onlyHyp = { hyperspace: ALL_VARIANTS.hyperspace };
    expect(pickVariant(card({ variants: onlyHyp }), "best")).toBe(ALL_VARIANTS.hyperspace);
  });

  it("random/lottery are stable per instance id", () => {
    for (const mode of ["random", "lottery"] as VariantMode[]) {
      const c = card({ instance_id: "human_42", variants: ALL_VARIANTS });
      const a = pickVariant(c, mode);
      const b = pickVariant({ ...c }, mode);
      expect(a).toBe(b);
    }
  });

  it("lottery heavily favours standard but still yields rare variants", () => {
    let standard = 0;
    let fancy = 0;
    for (let i = 0; i < 2000; i++) {
      const chosen = pickVariant(
        card({ instance_id: `id_${i}`, variants: ALL_VARIANTS }),
        "lottery",
      );
      if (chosen === null) standard++;
      else fancy++;
    }
    // ~85% standard by design; just assert the strong skew + non-zero treats.
    expect(standard).toBeGreaterThan(fancy);
    expect(fancy).toBeGreaterThan(0);
  });

  it("artFor falls back to base urls when no variant chosen", () => {
    const c = card({
      image_url: "/std-front",
      back_image_url: "/std-back",
      variants: ALL_VARIANTS,
    });
    expect(artFor(c, "standard")).toEqual({ front: "/std-front", back: "/std-back" });
    expect(artFor(c, "best")).toEqual({ front: "/show-front", back: "/show-back" });
  });
});

describe("Card leader-back rendering", () => {
  const renderCard = (c: CardModel) =>
    render(
      <SettingsProvider>
        <Card card={c} />
      </SettingsProvider>,
    );

  it("a deployed leader showing its back is NOT landscape (portrait unit side)", () => {
    const leader = card({
      card_type: "Leader",
      deployed: true,
      image_url: "/leader-front",
      back_image_url: "/leader-back",
    });
    const { container } = renderCard(leader);
    const el = container.querySelector(".card")!;
    expect(el.classList.contains("landscape")).toBe(false);
    expect(container.querySelector("img.card-img")!.getAttribute("src")).toBe("/leader-back");
  });

  it("an undeployed leader keeps the landscape front", () => {
    const leader = card({
      card_type: "Leader",
      deployed: false,
      image_url: "/leader-front",
      back_image_url: "/leader-back",
    });
    const { container } = renderCard(leader);
    const el = container.querySelector(".card")!;
    expect(el.classList.contains("landscape")).toBe(true);
    expect(container.querySelector("img.card-img")!.getAttribute("src")).toBe("/leader-front");
  });
});
