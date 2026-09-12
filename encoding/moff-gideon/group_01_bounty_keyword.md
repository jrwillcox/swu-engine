# moff-gideon:01 — Bounty keyword

- **Group id (paste this):** `moff-gideon:01`
- **Kind:** keyword
- **Cards:** 3

## Keyword group: **Bounty**

Implement the **Bounty** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Bounty` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_31 | The Client | Unit | 3 | 2/5 | Bounty, Shielded |
| SHD_71 | Top Target | Upgrade | 1 |  | Bounty |
| SHD_125 | Price on Your Head | Upgrade | 2 |  | Bounty |

## Per-card analysis & acceptance criteria

### SHD_31 — The Client

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Imperial, Official

**Rules text:**

> Shielded
> Action [Exhaust]: Choose a unit. For this phase, it gains: “Bounty — Heal 5 damage from a base.” (When that unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Shielded Action [Exhaust]: Choose a unit. For this phase, it gains: “Bounty — Heal 5 damage from a base.” (When that unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `activated`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_71 — Top Target

**Type/Stats:** Upgrade, cost 1  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Heal 4 damage from a unit or base. If this unit is unique, heal 6 damage instead.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “Bounty — Heal 4 damage from a unit or base. If this unit is unique, heal 6 damage instead.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_125 — Price on Your Head

**Type/Stats:** Upgrade, cost 2  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Put the top card of your deck into play as a resource.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “Bounty — Put the top card of your deck into play as a resource.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

