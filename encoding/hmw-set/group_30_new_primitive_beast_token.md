# hmw-set:30 — New primitive: beast-token

- **Group id (paste this):** `hmw-set:30`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_150 | Migrate | Event | 3 |  |  |
| HMW_152 | Babwa Venomor | Unit | 2 | 4/4 | Overwhelm |
| HMW_153 | Poacher's Starfighter | Unit | 2 | 3/1 |  |
| HMW_168 | Ezra Bridger | Unit | 4 | 5/4 |  |
| HMW_194 | Run Amok | Event | 3 |  |  |
| HMW_195 | Catch the Scent | Event | 5 |  |  |
| HMW_241 | Howl | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### HMW_150 — Migrate

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> For every 3 resources you control, create a Beast token.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_152 — Babwa Venomor

**Type/Stats:** Unit, cost 2, 4/4  |  Traits: Imperial

**Rules text:**

> Overwhelm
> When Played: An opponent creates a Beast token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_153 — Poacher's Starfighter

**Type/Stats:** Unit, cost 2, 3/1  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: You may defeat this unit. If you do, create a Beast token and deal 1 damage to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_168 — Ezra Bridger

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Force, Rebel, Spectre

**Rules text:**

> When you take the initiative: You may deal 3 damage to your base. If you do, create a Beast token.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_194 — Run Amok

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> Create a Beast token.
> Deal 1 damage to a friendly ground unit and 1 damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_195 — Catch the Scent

**Type/Stats:** Event, cost 5  |  Traits: Innate

**Rules text:**

> Create 2 Beast tokens and ready 1 of them.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_241 — Howl

**Type/Stats:** Event, cost 6  |  Traits: Innate

**Rules text:**

> Create a Beast token.
> You may return a non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand, create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

