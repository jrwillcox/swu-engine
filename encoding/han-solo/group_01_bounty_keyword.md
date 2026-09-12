# han-solo:01 — Bounty keyword

- **Group id (paste this):** `han-solo:01`
- **Kind:** keyword
- **Cards:** 2

## Keyword group: **Bounty**

Implement the **Bounty** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Bounty` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_95 | Clone Deserter | Unit | 1 | 2/3 | Bounty, Restore |
| SHD_195 | Cartel Turncoat | Unit | 1 | 2/3 | Bounty |

## Per-card analysis & acceptance criteria

### SHD_95 — Clone Deserter

**Type/Stats:** Unit, cost 1, 2/3  |  Traits: Clone, Fringe

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> Bounty — Draw a card. (When this unit is defeated or captured, your opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Restore 1 (When this unit attacks, heal 1 damage from your base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_195 — Cartel Turncoat

**Type/Stats:** Unit, cost 1, 2/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Bounty — Draw a card. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

