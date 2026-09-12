// The scripted "deck" for the tutorial — real SOR Luke-vs-Vader starter cards, so
// the art, stats and keywords are ones the player will actually meet in a game.
// The player controls Vader (Imperial); the opponent is Luke (Rebel), whose side
// naturally carries the Sentinel guard. Card art is served by DB id at
// /api/cards/{id}/image — the printed face already shows cost / power / HP /
// keywords, so we only overlay tutorial affordances (glow, exhausted, picked, …).

export type Arena = "ground" | "space";

export interface TutCard {
  id: number; // DB card id → image endpoint
  name: string;
  type: "Leader" | "Base" | "Unit";
  arena?: Arena; // units only
  img: string;
  back?: string; // leaders / bases are double-faced (landscape)
  landscape?: boolean; // Leader/Base art is landscape
}

const img = (id: number) => `/api/cards/${id}/image`;
const back = (id: number) => `/api/cards/${id}/image?face=back`;

function unit(id: number, name: string, arena: Arena): TutCard {
  return { id, name, type: "Unit", arena, img: img(id) };
}
function bigCard(id: number, name: string, type: "Leader" | "Base"): TutCard {
  return { id, name, type, img: img(id), back: back(id), landscape: true };
}

// ── Player side (Vader / Imperial) ──────────────────────────────────────────
export const CARDS = {
  // permanents
  vaderLeader: bigCard(6, "Darth Vader", "Leader"),
  commandCenter: bigCard(95, "Command Center", "Base"),
  // the unit the player plays round one — a real 2-cost Ground unit with Overwhelm
  snowtrooper: unit(353, "First Legion Snowtrooper", "ground"),
  // hand cards that stay (used to teach Space + Raid); dimmed during the resource pick
  tie: unit(35, "TIE/ln Fighter", "space"),
  rogue: unit(373, "Rogue Operative", "ground"), // Raid 1
  // three "spare" hand cards the player taps to place as resources
  sp1: unit(351, "Death Star Stormtrooper", "ground"),
  sp2: unit(150, "Snowtrooper Lieutenant", "ground"),
  sp3: unit(155, "Viper Probe Droid", "ground"),

  // ── Opponent side (Luke / Rebel) ──────────────────────────────────────────
  lukeLeader: bigCard(5, "Luke Skywalker", "Leader"),
  adminTower: bigCard(55, "Administrator's Tower", "Base"),
  guard: unit(321, "Cloud City Wing Guard", "ground"), // Sentinel
} as const;

export type CardKey = keyof typeof CARDS;

// The three hand cards the player is allowed to resource (real free choice of 2).
export const SPARE_KEYS: CardKey[] = ["sp1", "sp2", "sp3"];
