# j25-set:01 — Combat tricks, buffs & tempo

- **Group id (paste this):** `j25-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| J25_14 | Luke Skywalker | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### J25_14 — Luke Skywalker

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Fringe

**Rules text:**

> When you play another <uq>  unit: You may use the Force . If you do, give an Experience token and a Shield token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

