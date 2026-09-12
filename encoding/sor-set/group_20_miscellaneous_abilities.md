# sor-set:20 — Miscellaneous abilities

- **Group id (paste this):** `sor-set:20`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_224 | Change of Heart | Event | 6 |  |  |
| SOR_248 | Volunteer Soldier | Unit | 3 | 2/3 | Raid |

## Per-card analysis & acceptance criteria

### SOR_224 — Change of Heart

**Type/Stats:** Event, cost 6  |  Traits: Gambit

**Rules text:**

> Take control of a non-leader unit. At the start of the regroup phase, its owner takes control of it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_248 — Volunteer Soldier

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Trooper

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> 
> If you control a TROOPER unit, this unit costs [1 resource] less to play.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

