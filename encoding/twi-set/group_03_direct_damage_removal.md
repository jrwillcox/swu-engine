# twi-set:03 — Direct damage & removal

- **Group id (paste this):** `twi-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_103 | Pyrrhic Assault | Event | 3 |  |  |
| TWI_131 | OOM-Series Officer | Unit | 2 | 2/1 |  |
| TWI_140 | Self-Destruct | Event | 2 |  |  |
| TWI_146 | Steela Gerrera | Unit | 4 | 4/3 |  |
| TWI_149 | Low Altitude Gunship | Unit | 6 | 6/5 | Overwhelm |
| TWI_150 | Saw Gerrera | Unit | 6 | 4/8 | Raid |
| TWI_151 | Resolute | Unit | 10 | 8/8 |  |

## Per-card analysis & acceptance criteria

### TWI_103 — Pyrrhic Assault

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> For this phase, each friendly unit gains: “When Defeated: Deal 2 damage to an enemy unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_131 — OOM-Series Officer

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Droid, Separatist

**Rules text:**

> When Defeated: Deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_140 — Self-Destruct

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Defeat a friendly unit. If you do, deal 4 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_146 — Steela Gerrera

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Fringe

**Rules text:**

> When Played/When Defeated: You may deal 2 damage to your base. If you do, search the top 8 cards of your deck for a Tactic card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_149 — Low Altitude Gunship

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: Choose an enemy unit. Deal 1 damage to it for each friendly Republic unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_150 — Saw Gerrera

**Type/Stats:** Unit, cost 6, 4/8  |  Traits: Fringe, Trooper

**Rules text:**

> Raid 2
> On Attack: If your base has 15 or more damage on it, deal 1 damage to each enemy ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_151 — Resolute

**Type/Stats:** Unit, cost 10, 8/8  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> This unit costs 1 resource less to play for every 5 damage on your base.
> When Played/On Attack: Deal 2 damage to an enemy unit and each other enemy unit with the same name as that unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

