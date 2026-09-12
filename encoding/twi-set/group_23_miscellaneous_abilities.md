# twi-set:23 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_176 | Caught in the Crossfire | Event | 6 |  |  |
| TWI_192 | Padmé Amidala | Unit | 2 | 1/4 | Coordinate |
| TWI_199 | Clear the Field | Event | 2 |  |  |
| TWI_205 | Clone Dive Trooper | Unit | 1 | 2/1 | Coordinate |
| TWI_213 | Sanctioner's Shuttle | Unit | 3 | 2/3 | Coordinate |
| TWI_219 | On Top of Things | Upgrade | 2 |  |  |
| TWI_225 | Now There Are Two of Them | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### TWI_176 — Caught in the Crossfire

**Type/Stats:** Event, cost 6  |  Traits: Disaster

**Rules text:**

> Choose 2 enemy units in the same arena. Each of those units deals damage equal to its power to the other.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_192 — Padmé Amidala

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Naboo, Official, Republic

**Rules text:**

> Coordinate — On Attack: Give an enemy unit –3/–0 for this phase. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_199 — Clear the Field

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Choose a non-leader unit that costs 3 or less. Return it and each enemy non-leader unit with the same name as it to their owners' hands.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_205 — Clone Dive Trooper

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — While this unit is attacking, the defender gets –2/–0. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_213 — Sanctioner's Shuttle

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> Coordinate — When Played: This unit captures an enemy non-leader unit that costs 3 or less. (Gain this ability while you control 3 or more units, including this one.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_219 — On Top of Things

**Type/Stats:** Upgrade, cost 2  |  Traits: Trick

**Rules text:**

> When Played: Attached unit can't be attacked this phase (unless it has Sentinel).

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_225 — Now There Are Two of Them

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> If you control exactly one unit, play a non-Vehicle unit from your hand that shares a Trait with the unit you control. It costs 5 resources less.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

