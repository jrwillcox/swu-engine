# twi-set:05 — Direct damage & removal

- **Group id (paste this):** `twi-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_167 | Heavy Persuader Tank | Unit | 7 | 6/5 | Exploit |
| TWI_173 | Blood Sport | Event | 3 |  |  |
| TWI_177 | Guerilla Insurgency | Event | 8 |  |  |
| TWI_195 | Sabine Wren | Unit | 4 | 4/4 |  |
| TWI_202 | Jar Jar Binks | Unit | 2 | 2/3 |  |
| TWI_212 | Freelance Assassin | Unit | 3 | 4/2 |  |
| TWI_239 | Execute Order 66 | Event | 4 |  |  |

## Per-card analysis & acceptance criteria

### TWI_167 — Heavy Persuader Tank

**Type/Stats:** Unit, cost 7, 6/5  |  Traits: Droid, Separatist, Tank, Vehicle

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> When Played: You may deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_173 — Blood Sport

**Type/Stats:** Event, cost 3  |  Traits: Fringe

**Rules text:**

> Deal 2 damage to each ground unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_177 — Guerilla Insurgency

**Type/Stats:** Event, cost 8  |  Traits: Tactic

**Rules text:**

> Each player defeats a resource they control and discards 2 cards from their hand. Deal 4 damage to each ground unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_195 — Sabine Wren

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Fringe, Mandalorian, Spectre

**Rules text:**

> While this unit is exhausted, she can't be attacked (unless she gains Sentinel).
> On Attack: You may discard a card from your deck. If it doesn't share an aspect with your base, deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_202 — Jar Jar Binks

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Gungan

**Rules text:**

> On Attack: Deal 2 damage to a random unit or base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_212 — Freelance Assassin

**Type/Stats:** Unit, cost 3, 4/2  |  Traits: Underworld

**Rules text:**

> When Played: You may pay 2 resources. If you do, deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_239 — Execute Order 66

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> Deal 6 damage to each Jedi unit. For each unit defeated this way, its controller creates a Clone Trooper token.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

