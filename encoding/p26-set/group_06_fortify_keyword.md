# p26-set:06 — Fortify keyword

- **Group id (paste this):** `p26-set:06`
- **Kind:** keyword
- **Cards:** 1

## Keyword group: **Fortify** (residual text)

The **Fortify** keyword is already implemented engine-side; do NOT implement it again.  Its design notes are in `docs/dev/engine_seams.md` (search for `Fortify`).  Encode only each card's *residual* ability text below, as an ordinary ability batch.  A card whose only text is the keyword is already playable and needs nothing.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_267 | Verdant Fortress | Upgrade | 2 |  | Fortify, Raid |

## Per-card analysis & acceptance criteria

### P26_267 — Verdant Fortress

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify 
> Attached base gains: “Friendly units gain Raid 1. ”

**Residual text (needs separate ability after keyword):** Attached base gains: “Friendly units gain Raid 1. ”

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

