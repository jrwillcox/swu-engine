# jtl-set:02 — Direct damage & removal

- **Group id (paste this):** `jtl-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_51 | Red Squadron X-Wing | Unit | 3 | 3/4 |  |
| JTL_55 | You're All Clear, Kid | Event | 2 |  |  |
| JTL_62 | Silver Angel | Unit | 2 | 2/3 |  |
| JTL_78 | Direct Hit | Event | 4 |  |  |
| JTL_80 | Nebula Ignition | Event | 9 |  |  |
| JTL_91 | Apology Accepted | Event | 1 |  |  |
| JTL_102 | Resistance Blue Squadron | Unit | 4 | 3/4 |  |

## Per-card analysis & acceptance criteria

### JTL_51 — Red Squadron X-Wing

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to this unit. If you do, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_55 — You're All Clear, Kid

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Defeat an enemy space unit with 3 or less remaining HP. If you do and an opponent controls no space units, you may give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_62 — Silver Angel

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> When 1 or more damage is healed from this unit: You may deal 1 damage to a space unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_78 — Direct Hit

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a non-leader Vehicle unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_80 — Nebula Ignition

**Type/Stats:** Event, cost 9  |  Traits: Disaster

**Rules text:**

> Defeat each unit that isn't upgraded.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_91 — Apology Accepted

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Defeat a friendly unit. You may give 2 Experience tokens to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_102 — Resistance Blue Squadron

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> When Played: You may deal damage to a unit equal to the number of friendly space units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

