# ash-set:27 — Miscellaneous abilities

- **Group id (paste this):** `ash-set:27`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_111 | Children of the Watch | Unit | 6 | 3/3 |  |
| ASH_119 | Greef Karga | Unit | 2 | 2/3 |  |
| ASH_123 | Lang | Unit | 3 | 2/5 |  |
| ASH_124 | Protectorate Fighter | Unit | 3 | 2/1 |  |
| ASH_134 | Warrior's Legacy | Upgrade | 3 |  |  |
| ASH_135 | The Darksaber | Upgrade | 4 |  |  |
| ASH_139 | Hold Them Off | Event | 4 |  |  |

## Per-card analysis & acceptance criteria

### ASH_111 — Children of the Watch

**Type/Stats:** Unit, cost 6, 3/3  |  Traits: Mandalorian

**Rules text:**

> When Played: Create 2 Mandalorian tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_119 — Greef Karga

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Official

**Rules text:**

> Action [1 resource, Exhaust]: If your base was attacked this phase, create a Mandalorian token.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_123 — Lang

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Fringe

**Rules text:**

> Action [Exhaust]: This unit deals damage equal to his power to a ground unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_124 — Protectorate Fighter

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Fighter, Mandalorian, Vehicle

**Rules text:**

> When Played: If you control a <uq> unit, create a Mandalorian token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_134 — Warrior's Legacy

**Type/Stats:** Upgrade, cost 3  |  Traits: Learned

**Rules text:**

> Attached unit gains: “When Defeated: Create a Mandalorian token.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_135 — The Darksaber

**Type/Stats:** Upgrade, cost 4  |  Traits: Item, Mandalorian, Weapon

**Rules text:**

> Attach to a <uq> non-Vehicle unit.
> Attached unit is a leader unit and gains the Mandalorian trait.
> Attached unit gains: “While you are paying costs, this unit provides its aspect icons.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_139 — Hold Them Off

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Choose a friendly unit. That unit deals damage equal to its power divided as you choose among any number of units in its arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

