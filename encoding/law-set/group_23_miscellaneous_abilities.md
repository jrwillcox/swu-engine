# law-set:23 — Miscellaneous abilities

- **Group id (paste this):** `law-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_221 | Lieutenant Gorn | Unit | 3 | 4/4 |  |
| LAW_228 | Canyon Frontrunner | Unit | 2 | 3/2 |  |
| LAW_232 | Champion's KT9 Podracer | Unit | 3 | 2/3 |  |
| LAW_235 | Lady Proxima | Unit | 3 | 1/5 |  |
| LAW_243 | Transmission Jamming | Event | 1 |  |  |
| LAW_248 | Windfall | Event | 5 |  |  |
| LAW_256 | Fire Across the Galaxy | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### LAW_221 — Lieutenant Gorn

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Imperial, Rebel

**Rules text:**

> On Attack: Take control of an enemy Credit token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_228 — Canyon Frontrunner

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Speeder, Vehicle

**Rules text:**

> On Attack: If no other units have attacked this phase (including enemy units), you may give a unit –2/–0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_232 — Champion's KT9 Podracer

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Speeder, Vehicle

**Rules text:**

> When Played: Create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_235 — Lady Proxima

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Create a Credit token.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_243 — Transmission Jamming

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Name a card. Cards with that name can't be played this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_248 — Windfall

**Type/Stats:** Event, cost 5  |  Traits: Supply

**Rules text:**

> Create 3 Credit tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_256 — Fire Across the Galaxy

**Type/Stats:** Event, cost 6  |  Traits: Spectre

**Rules text:**

> Use any number of “When Played” abilities on friendly Spectre units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

