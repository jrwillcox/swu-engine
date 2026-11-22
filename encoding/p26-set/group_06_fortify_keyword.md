# p26-set:06 — Fortify keyword

- **Group id (paste this):** `p26-set:06`
- **Kind:** keyword
- **Cards:** 1

## Keyword group: **Fortify**

Implement the **Fortify** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and add `Fortify` to the keyword list in `docs/dev/engine_seams.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

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

