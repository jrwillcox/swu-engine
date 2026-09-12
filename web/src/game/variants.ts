// Cosmetic card-art variant selection. Pure presentation — never touches game
// logic. Given a card and the user's display mode, decide which printing's art
// (standard / hyperspace / hyperspace foil / showcase) to show.
//
// random/lottery pick a STABLE variant per card instance: a deterministic hash
// of the instance_id, so a card keeps the same art for the whole game (and
// across re-renders/reloads) but gets a fresh "pull" each new game (new shuffle
// → new instance ids). No state is stored.
import type { CardModel } from "../api/types";

export type VariantMode = "standard" | "best" | "random" | "lottery";

// Display-quality priority for "best available" (highest first).
const BEST_ORDER = ["showcase", "hyperspace_foil", "hyperspace"] as const;

// Approximate wild pull-rates for "lottery" mode. Weights are relative; only
// the variants a given card actually has are considered (plus standard), then
// renormalised. Tweak freely — these just make rare arts an occasional treat.
const LOTTERY_WEIGHTS: Record<string, number> = {
  standard: 0.85,
  hyperspace: 0.1,
  showcase: 0.03,
  hyperspace_foil: 0.02,
};

export interface ChosenArt {
  image_url: string | null;
  back_image_url: string | null;
}

// FNV-1a over the instance id, salted per mode, → a stable float in [0, 1).
function stableUnit(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  // >>> 0 → unsigned; divide by 2^32 for [0,1).
  return (h >>> 0) / 0x100000000;
}

/**
 * Resolve which art to show for `card` under `mode`. Returns null to mean "use
 * the card's standard image_url/back_image_url" (so callers fall back cleanly).
 */
export function pickVariant(card: CardModel, mode: VariantMode): ChosenArt | null {
  const variants = card.variants;
  if (mode === "standard" || !variants || Object.keys(variants).length === 0) {
    return null;
  }

  const available = Object.keys(variants);

  if (mode === "best") {
    const best = BEST_ORDER.find((v) => available.includes(v));
    return best ? variants[best] : null;
  }

  // random / lottery: build a weighted choice over {standard} ∪ available.
  const options = ["standard", ...available];
  const weights = options.map((opt) => (mode === "lottery" ? (LOTTERY_WEIGHTS[opt] ?? 0.01) : 1));
  const total = weights.reduce((a, b) => a + b, 0);
  let roll = stableUnit(card.instance_id + ":" + mode) * total;
  for (let i = 0; i < options.length; i++) {
    roll -= weights[i];
    if (roll < 0) {
      const opt = options[i];
      return opt === "standard" ? null : variants[opt];
    }
  }
  return null; // floating-point fallthrough → standard
}

/** Convenience: the effective front/back URLs for a card under a mode. */
export function artFor(
  card: CardModel,
  mode: VariantMode,
): { front: string | null; back: string | null } {
  const chosen: ChosenArt | null = pickVariant(card, mode);
  return {
    front: chosen?.image_url ?? card.image_url,
    back: chosen?.back_image_url ?? card.back_image_url,
  };
}
