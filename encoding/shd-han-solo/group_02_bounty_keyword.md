# shd-han-solo:02 — Bounty keyword

- **Group id (paste this):** `shd-han-solo:02`
- **Kind:** keyword
- **Cards:** 2
- **⚠ New primitives suspected:** control-change — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Keyword group: **Bounty**

Implement the **Bounty** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Bounty` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_161 | Stolen Landspeeder | Unit | 1 | 3/2 | Bounty |
| SHD_165 | Unlicensed Headhunter | Unit | 2 | 3/2 | Bounty, Saboteur |

## Per-card analysis & acceptance criteria

### SHD_161 — Stolen Landspeeder

**Type/Stats:** Unit, cost 1, 3/2  |  Traits: Speeder, Underworld, Vehicle

**Rules text:**

> When Played: If you played this unit from your hand, an opponent takes control of it.
> Bounty — If you own this unit, play it from your discard pile for free and give an Experience token to it.

**Residual text (needs separate ability after keyword):** When Played: If you played this unit from your hand, an opponent takes control of it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, GiveToken.

**⚠ Suspected NEW primitive:** control-change. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_165 — Unlicensed Headhunter

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Saboteur
> While this unit is exhausted, it gains: “Bounty — Heal 5 damage from your base.” (When this unit is defeated or captured, your opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Saboteur While this unit is exhausted, it gains: “Bounty — Heal 5 damage from your base.” (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

