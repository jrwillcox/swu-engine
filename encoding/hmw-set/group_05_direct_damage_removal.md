# hmw-set:05 — Direct damage & removal

- **Group id (paste this):** `hmw-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_130 | Emerie Karr | Unit | 1 | 2/1 |  |
| HMW_156 | Arena Acklay | Unit | 5 | 5/6 |  |
| HMW_158 | Battle-Scarred Destroyer | Unit | 6 | 7/8 |  |
| HMW_159 | General Grievous | Unit | 7 | 8/5 |  |
| HMW_169 | Crosshair | Unit | 5 | 5/6 |  |
| HMW_177 | Adamant Ewoks | Unit | 2 | 3/2 |  |
| HMW_182 | Arena Nexu | Unit | 4 | 2/6 | Grit |

## Per-card analysis & acceptance criteria

### HMW_130 — Emerie Karr

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Clone, Imperial

**Rules text:**

> When Played: You may deal 1 damage to another ground unit. If you control that unit, the next unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_156 — Arena Acklay

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Creature

**Rules text:**

> When this unit is dealt damage and survives: Deal 2 damage to each enemy base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_158 — Battle-Scarred Destroyer

**Type/Stats:** Unit, cost 6, 7/8  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: Deal 4 damage to a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_159 — General Grievous

**Type/Stats:** Unit, cost 7, 8/5  |  Traits: Official, Separatist

**Rules text:**

> Bases can't be healed.
> When Played: Deal 4 damage to a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_169 — Crosshair

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Clone

**Rules text:**

> When this unit is dealt damage and survives: Each player draws a card.
> When an opponent draws 1 or more cards during the action phase: Deal 2 damage to their base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_177 — Adamant Ewoks

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Ewok

**Rules text:**

> When Played: If you control another Ewok unit or an Endor base, you may deal 1 damage to a base and 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_182 — Arena Nexu

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Creature

**Rules text:**

> Grit
> On Attack: You may deal 3 damage to a friendly Creature unit (including this one) and ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

