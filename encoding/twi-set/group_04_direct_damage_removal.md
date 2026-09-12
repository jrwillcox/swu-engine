# twi-set:04 — Direct damage & removal

- **Group id (paste this):** `twi-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_154 | Mister Bones | Unit | 1 | 3/1 |  |
| TWI_155 | Twice the Pride | Upgrade | 2 |  |  |
| TWI_156 | Unlimited Power | Event | 6 |  |  |
| TWI_157 | Disaffected Senator | Unit | 1 | 0/4 |  |
| TWI_160 | Vanguard Droid Bomber | Unit | 2 | 2/2 |  |
| TWI_162 | Reckless Torrent | Unit | 3 | 3/1 | Coordinate |
| TWI_165 | Kit Fisto | Unit | 6 | 7/6 | Coordinate, Saboteur |

## Per-card analysis & acceptance criteria

### TWI_154 — Mister Bones

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Droid, Fringe

**Rules text:**

> On Attack: If you have no cards in your hand, you may deal 3 damage to a ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_155 — Twice the Pride

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: Deal 2 damage to attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_156 — Unlimited Power

**Type/Stats:** Event, cost 6  |  Traits: Force

**Rules text:**

> Deal 4 damage to a unit, 3 damage to a second unit, 2 damage to a third unit, and 1 damage to a fourth unit. (All damage is dealt simultaneously.)

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_157 — Disaffected Senator

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Official, Separatist

**Rules text:**

> Action [2 resources, Exhaust]: Deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_160 — Vanguard Droid Bomber

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Droid, Fighter, Separatist, Vehicle

**Rules text:**

> When Played: If you control another Separatist unit, deal 2 damage to an enemy base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_162 — Reckless Torrent

**Type/Stats:** Unit, cost 3, 3/1  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> Coordinate — When Played: You may deal 2 damage to a friendly unit and 2 damage to an enemy unit in the same arena. (Gain this ability while you control 3 or more units, including this one.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_165 — Kit Fisto

**Type/Stats:** Unit, cost 6, 7/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Saboteur
> Coordinate — On Attack: You may deal 3 damage to a ground unit. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

