// The explorer's data layer: the labels and colours the views share, the
// browsing-preference storage, the sort comparator, and the deck-identity and
// optimistic-update helpers.  No JSX here, which is what makes the sorting and
// copy-limit rules straightforward to test on their own.
// Human-readable labels for the cosmetic alternate-art printings. Keys match the
// backend's variant_type values (card_variants table / image endpoint).
import type { CustomDeck, ExplorerCard } from "../../api/types";

export const VARIANT_LABELS: Record<string, string> = {
  hyperspace: "Hyperspace",
  hyperspace_foil: "Hyperspace Foil",
  showcase: "Showcase",
};
export const PAGE = 120; // how many tiles to render before "Load more" (2600+ cards total)
// List rows are ~1/12th the height of a thumbnail, so the details view shows a
// far bigger window before paging.
export const LIST_PAGE = 500;
// Aspect chip colours (mirrors the printed pips; card_aspects.color in the DB).
export const ASPECT_COLOR: Record<string, string> = {
  Vigilance: "#4073d4",
  Command: "#0b992d",
  Aggression: "#d30808",
  Cunning: "#f4c518",
  Heroism: "#e9e29a",
  Villainy: "#6b6f76",
};
export type Availability = "all" | "yes" | "no";
// How the results are drawn: "grid" = card thumbnails, "list" = a sortable
// details table (Windows Explorer's "Details" view). Persisted per browser —
// it's a browsing preference, not a game setting, so it lives here and not in
// SettingsPanel.
export type ViewMode = "grid" | "list";
export const VIEW_KEY = "swu.explorerView";

export function loadView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "grid";
  } catch {
    return "grid";
  }
}
// ── list-view sorting ───────────────────────────────────────────────────────
// Every column is sortable. The three stat columns sort numerically (and cards
// with no such stat — leaders, events, bases — always sink to the bottom, in
// both directions, so a "sort by Power" never buries the units under blanks);
// everything else sorts as text, numeric-aware so "SOR 9" precedes "SOR 10".
export type SortKey =
  | "code"
  | "name"
  | "subtitle"
  | "type"
  | "arena"
  | "cost"
  | "power"
  | "hp"
  | "aspects"
  | "keywords"
  | "traits"
  | "rarity"
  | "playable";

export interface Sort {
  key: SortKey;
  dir: 1 | -1;
}
// What "Reset" puts the details table back to, alongside the filters.
export const DEFAULT_SORT: Sort = { key: "name", dir: 1 };

export const NUMERIC_KEYS: SortKey[] = ["cost", "power", "hp"];

export function codeOf(c: ExplorerCard): string {
  return `${c.set_code} ${c.card_number}`;
}
export function sortText(c: ExplorerCard, key: SortKey): string {
  switch (key) {
    case "code":
      return codeOf(c);
    case "name":
      return c.name;
    case "subtitle":
      return c.subtitle ?? "";
    case "type":
      return c.type;
    case "arena":
      return c.arenas.join("/");
    case "aspects":
      return c.aspects.join(", ");
    case "keywords":
      return c.keywords.join(", ");
    case "traits":
      return c.traits.join(", ");
    case "rarity":
      return c.rarity ?? "";
    case "playable":
      return c.playable ? "0" : "1"; // available first ascending
    default:
      return "";
  }
}
export function compareCards(a: ExplorerCard, b: ExplorerCard, { key, dir }: Sort): number {
  if (NUMERIC_KEYS.includes(key)) {
    const av = a[key as "cost" | "power" | "hp"];
    const bv = b[key as "cost" | "power" | "hp"];
    // Blanks last whichever way the column is pointing.
    if (av === null && bv !== null) return 1;
    if (bv === null && av !== null) return -1;
    if (av !== null && bv !== null && av !== bv) return (av - bv) * dir;
  } else {
    const d = sortText(a, key).localeCompare(sortText(b, key), undefined, { numeric: true });
    if (d !== 0) return d * dir;
  }
  // Stable, direction-independent tie-break so equal rows keep a sane order.
  return (
    a.name.localeCompare(b.name) || codeOf(a).localeCompare(codeOf(b), undefined, { numeric: true })
  );
}
// Which slot a card fills in a custom deck.
export type CardKind = "leader" | "base" | "pool";
export function cardKind(card: ExplorerCard): CardKind {
  if (card.type === "Leader") return "leader";
  if (card.type === "Base") return "base";
  return "pool";
}
// The copy-limit identity of a card = its title + subtitle, NOT its DB id. Two
// different printings of the same card (a reprint/promo, same name+subtitle but
// different id) share ONE copy cap, so you cannot exceed 3 by mixing printings.
// This mirrors the backend rule in swu.cards.deckrules.deck_errors.
export function groupKey(card: { name: string; subtitle?: string | null }): string {
  return `${card.name}\u0000${card.subtitle ?? ""}`;
}
// Per-card add/remove state for the deck currently selected in "Adding to".
// `addTitle` explains why `+` is disabled. Card add/remove is only offered while
// a deck is selected — with none chosen the explorer is browse-only.
export interface Cell {
  count: number;
  canAdd: boolean;
  canRemove: boolean;
  addTitle: string;
}
// Optimistic reducers over a CustomDeck (the server is the source of truth, but
// these give instant feedback before the write round-trips).
export function withPoolDelta(deck: CustomDeck, cardId: number, delta: number): CustomDeck {
  const key = String(cardId);
  const cards = { ...deck.cards };
  const next = (cards[key] ?? 0) + delta;
  if (next > 0) cards[key] = next;
  else delete cards[key];
  const count = Object.values(cards).reduce((a, b) => a + b, 0);
  return { ...deck, cards, count };
}
