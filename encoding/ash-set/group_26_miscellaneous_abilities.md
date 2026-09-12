# ash-set:26 — Miscellaneous abilities

- **Group id (paste this):** `ash-set:26`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_63 | Bo-Katan's Gauntlet | Unit | 5 | 4/5 | Restore |
| ASH_70 | At Attin Safety Droid | Unit | 2 | 1/4 |  |
| ASH_77 | Ryder Azadi | Unit | 3 | 2/5 | Restore |
| ASH_80 | Covert Believers | Unit | 5 | 4/5 |  |
| ASH_84 | Arcana Star Map | Upgrade | 1 |  |  |
| ASH_91 | Buy Time | Event | 3 |  | Sentinel |
| ASH_108 | Crix Madine | Unit | 3 | 3/2 |  |

## Per-card analysis & acceptance criteria

### ASH_63 — Bo-Katan's Gauntlet

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Restore 1
> Each other friendly non-token unit gains: “When Defeated: Create a Mandalorian token.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_70 — At Attin Safety Droid

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Droid, Republic

**Rules text:**

> If your base would be dealt more than 4 damage, prevent all but 4 of that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_77 — Ryder Azadi

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: New Republic, Official

**Rules text:**

> Restore 1
> When Played: Name a card. While this unit is in play, opponents can't play cards with that name.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_80 — Covert Believers

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Mandalorian

**Rules text:**

> When Defeated: Create a Mandalorian token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_84 — Arcana Star Map

**Type/Stats:** Upgrade, cost 1  |  Traits: Item

**Rules text:**

> Attached unit gains: “If you would search a number of cards from your deck, search twice that number of cards instead.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_91 — Buy Time

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Create a Mandalorian token and give it Sentinel for this phase. (Enemy units in its arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_108 — Crix Madine

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Official, Rebel

**Rules text:**

> When Played: You may play a Heroism unit from your hand. It costs 2 resources less for each arena in which you control the most units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

