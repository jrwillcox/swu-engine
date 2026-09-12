// Shared deckbuilding constants for the custom deck builder (Stages 4–6).
// Mirrors src/swu/cards/deckrules.py — the backend is the source of truth for
// rule enforcement; these are for display (count/50, cap messaging) only.

/** The DEFAULT number of non-leader/base cards a *complete* deck holds.
 *
 * A base can shift it (Data Vault JTL_24 → 60, Thermal Oscillator JTL_25 → 45),
 * so this is only a fallback: anywhere a real deck is in hand, read its
 * `required` field (the backend's `deckrules.deck_size_for`) instead. */
export const DECK_SIZE = 50;

/** The default per-card copy cap (some cards raise it via printed text). */
export const DEFAULT_MAX_COPIES = 3;
