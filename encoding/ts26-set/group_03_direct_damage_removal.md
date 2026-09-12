# ts26-set:03 — Direct damage & removal

- **Group id (paste this):** `ts26-set:03`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_69 | Remove the Chip | Event | 2 |  |  |
| TS26_70 | Backed by Black Sun | Event | 3 |  |  |
| TS26_71 | Take Action | Event | 3 |  |  |
| TS26_72 | Fervor | Event | 5 |  |  |
| TS26_73 | Moralo Eval | Unit | 3 | 3/2 | Shielded |

## Per-card analysis & acceptance criteria

### TS26_69 — Remove the Chip

**Type/Stats:** Event, cost 2  |  Traits: Modification

**Rules text:**

> Deal 2 damage to a unit. If it's a Clone, ready it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_70 — Backed by Black Sun

**Type/Stats:** Event, cost 3  |  Traits: Supply

**Rules text:**

> Deal 1 damage to an enemy unit.
> You may deal damage to a unit equal to the number of damaged enemy units.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_71 — Take Action

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> This event costs 1 resource less to play for each friendly leader unit.
> Deal 3 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_72 — Fervor

**Type/Stats:** Event, cost 5  |  Traits: Innate

**Rules text:**

> Ready a unit.
> Deal 3 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_73 — Moralo Eval

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Underworld

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> When your base is dealt combat damage: You may deal 1 damage to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

