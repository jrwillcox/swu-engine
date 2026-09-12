# twi-set:22 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_115 | Osi Sobeck | Unit | 6 | 3/6 | Exploit |
| TWI_116 | Clone | Unit | 7 | 0/0 |  |
| TWI_125 | The Clone Wars | Event | 2 |  |  |
| TWI_132 | Confederate Tri-Fighter | Unit | 3 | 3/3 |  |
| TWI_135 | Darth Maul | Unit | 5 | 5/6 |  |
| TWI_145 | Jesse | Unit | 3 | 4/4 | Raid |
| TWI_148 | Senatorial Corvette | Unit | 5 | 5/4 | Saboteur |

## Per-card analysis & acceptance criteria

### TWI_115 — Osi Sobeck

**Type/Stats:** Unit, cost 6, 3/6  |  Traits: Separatist

**Rules text:**

> Exploit 3
> When Played: This unit captures an enemy non-leader ground unit with cost equal to or less than the number of resources paid to play this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_116 — Clone

**Type/Stats:** Unit, cost 7, 0/0  |  Traits: Clone

**Rules text:**

> You may have this unit enter play as a copy of a non-leader, non-Vehicle unit in play, except it gains the Clone trait and is not unique. (Only the card's printed attributes are copied.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_125 — The Clone Wars

**Type/Stats:** Event, cost 2  |  Traits: Disaster

**Rules text:**

> Pay any number of resources. Create that many Clone Trooper tokens. Each opponent creates that many Battle Droid tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_132 — Confederate Tri-Fighter

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Droid, Fighter, Separatist, Vehicle

**Rules text:**

> Bases can't be healed.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_135 — Darth Maul

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Force, Sith

**Rules text:**

> This unit can attack 2 units instead of 1.  (This unit deals its combat damage to both defenders and they both deal their combat damage to this unit. All damage is dealt simultaneously.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_145 — Jesse

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: An opponent creates 2 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_148 — Senatorial Corvette

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Defeated: Each opponent discards a card from their hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

