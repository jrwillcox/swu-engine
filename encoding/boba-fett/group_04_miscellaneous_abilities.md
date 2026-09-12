# boba-fett:04 — Miscellaneous abilities

- **Group id (paste this):** `boba-fett:04`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_165 | Hunting Aggressor | Unit | 4 | 3/6 |  |
| JTL_185 | Hound's Tooth | Unit | 3 | 4/3 |  |

## Per-card analysis & acceptance criteria

### JTL_165 — Hunting Aggressor

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Indirect damage you deal to opponents is increased by 1.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_185 — Hound's Tooth

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> While attacking an exhausted unit that didn't enter play this phase, this unit deals combat damage before the defender.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

