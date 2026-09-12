# sec-set:05 — Direct damage & removal

- **Group id (paste this):** `sec-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_182 | Charged with Treason | Event | 4 |  |  |
| SEC_183 | Topple the Summit | Event | 5 |  | Plot |
| SEC_240 | Hutt Cartel Starfighter | Unit | 3 | 3/5 |  |
| SEC_242 | Elia Kane | Unit | 4 | 3/6 | Raid |
| SEC_244 | Darth Nihilus | Unit | 7 | 6/6 |  |
| SEC_246 | Contempt for Culture | Event | 2 |  |  |
| SEC_247 | Evil is Everywhere | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_182 — Charged with Treason

**Type/Stats:** Event, cost 4  |  Traits: Law

**Rules text:**

> You may disclose AggressionAggression (reveal cards from your hand with these aspect icons among them). If you do, deal 5 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_183 — Topple the Summit

**Type/Stats:** Event, cost 5  |  Traits: Plan

**Rules text:**

> Deal 3 damage to each damaged unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_240 — Hutt Cartel Starfighter

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: Deal 2 damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_242 — Elia Kane

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Imperial, New Republic

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: Look at 3 enemy resources. You may defeat 1 of them. If you do, its controller puts the top card of their deck into play as a resource and readies it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_244 — Darth Nihilus

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Force, Sith

**Rules text:**

> When Played/On Attack: Deal 3 damage to the unit with the least remaining HP among other units. (If multiple units are tied, choose one.). If it's a non-Vehicle unit, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_246 — Contempt for Culture

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Deal 2 damage to a non-Vehicle unit.
> Create a Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_247 — Evil is Everywhere

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> Defeat a unit with cost equal to or less than the number of Villainy aspect icons among friendly units.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

