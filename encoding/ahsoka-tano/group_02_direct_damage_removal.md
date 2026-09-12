# ahsoka-tano:02 — Direct damage & removal

- **Group id (paste this):** `ahsoka-tano:02`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_171 | Grenade Strike | Event | 2 |  |  |
| TWI_174 | Open Fire | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### TWI_171 — Grenade Strike

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Deal 2 damage to a unit. You may deal 1 damage to another unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_174 — Open Fire

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Deal 4 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

