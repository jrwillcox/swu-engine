# jabba-the-hutt:02 — Hidden keyword

- **Group id (paste this):** `jabba-the-hutt:02`
- **Kind:** keyword
- **Cards:** 1
- **⚠ New primitives suspected:** opponent-chooses-target — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Keyword group: **Hidden**

Implement the **Hidden** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Hidden` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_216 | Jabba's Rancor | Unit | 7 | 7/7 | Hidden |

## Per-card analysis & acceptance criteria

### LAW_216 — Jabba's Rancor

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Creature, Underworld

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> On Attack: An opponent chooses a ground unit they control. You may deal 7 damage to that unit.

**Residual text (needs separate ability after keyword):** On Attack: An opponent chooses a ground unit they control. You may deal 7 damage to that unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** opponent-chooses-target. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

