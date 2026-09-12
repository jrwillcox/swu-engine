# general-grievous:05 — New primitive: create-token-unit

- **Group id (paste this):** `general-grievous:05`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** create-token-unit — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_79 | Confederate Courier | Unit | 2 | 2/1 |  |
| TWI_80 | Poggle the Lesser | Unit | 2 | 1/4 |  |
| TWI_83 | General's Guardian | Unit | 4 | 4/4 |  |
| TWI_84 | Kraken | Unit | 5 | 2/5 |  |
| TWI_112 | Subjugating Starfighter | Unit | 4 | 3/3 | Ambush |
| TWI_190 | On the Doorstep | Event | 4 |  |  |
| TWI_218 | Droid Cohort | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### TWI_79 — Confederate Courier

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> When Defeated: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_80 — Poggle the Lesser

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Official, Separatist

**Rules text:**

> When you play another unit: You may exhaust this unit. If you do, create a Battle Droid token.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_83 — General's Guardian

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Droid, Separatist

**Rules text:**

> When this unit is attacked: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_84 — Kraken

**Type/Stats:** Unit, cost 5, 2/5  |  Traits: Droid, Separatist

**Rules text:**

> When Played: Create 2 Battle Droid tokens.
> On Attack: Give each friendly token unit +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_112 — Subjugating Starfighter

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may ready and attack an enemy unit.)
> When Played: If you have the initiative, create a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_190 — On the Doorstep

**Type/Stats:** Event, cost 4  |  Traits: Supply

**Rules text:**

> Create 3 Battle Droid tokens and ready them.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_218 — Droid Cohort

**Type/Stats:** Upgrade, cost 1  |  Traits: Supply

**Rules text:**

> Attached unit gains, “When Defeated: Create a Battle Droid token.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

