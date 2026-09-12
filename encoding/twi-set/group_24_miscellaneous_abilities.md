# twi-set:24 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:24`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_227 | Prisoner of War | Event | 4 |  |  |
| TWI_235 | Battle Droid Legion | Unit | 9 | 6/5 | Exploit |
| TWI_247 | AT-TE Vanguard | Unit | 8 | 6/9 | Restore |
| TWI_250 | Sword and Shield Maneuver | Event | 2 |  | Raid, Sentinel |
| TWI_255 | Brain Invaders | Unit | 4 | 2/4 |  |

## Per-card analysis & acceptance criteria

### TWI_227 — Prisoner of War

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> A friendly unit captures an enemy non-leader, non-Vehicle unit. If the enemy unit costs less than the friendly unit, create 2 Battle Droid tokens. (Put the captured card facedown under the friendly unit until that unit leaves play.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** capture, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_235 — Battle Droid Legion

**Type/Stats:** Unit, cost 9, 6/5  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> When Defeated: Create 3 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_247 — AT-TE Vanguard

**Type/Stats:** Unit, cost 8, 6/9  |  Traits: Republic, Vehicle, Walker

**Rules text:**

> Restore 3 (When this unit attacks, heal 3 damage from your base.)
> When Defeated: Create 2 Clone Trooper tokens.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_250 — Sword and Shield Maneuver

**Type/Stats:** Event, cost 2  |  Traits: Jedi, Republic, Tactic

**Rules text:**

> Give each friendly Trooper unit Raid 1 for this phase.
> Give each friendly Jedi unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_255 — Brain Invaders

**Type/Stats:** Unit, cost 4, 2/4  |  Traits: Fringe

**Rules text:**

> Each leader loses all abilities except for epic actions and can't gain abilities.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

