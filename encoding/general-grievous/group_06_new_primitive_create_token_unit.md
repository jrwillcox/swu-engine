# general-grievous:06 — New primitive: create-token-unit

- **Group id (paste this):** `general-grievous:06`
- **Kind:** ability
- **Cards:** 4
- **⚠ New primitives suspected:** create-token-unit — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_222 | Political Pressure | Event | 1 |  |  |
| TWI_229 | Battle Droid Escort | Unit | 3 | 1/1 |  |
| TWI_234 | The Invisible Hand | Unit | 8 | 4/7 |  |
| TWI_237 | Droid Deployment | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TWI_222 — Political Pressure

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Choose an opponent. They may discard a random card from their hand. If they don't, create 2 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_229 — Battle Droid Escort

**Type/Stats:** Unit, cost 3, 1/1  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> When Played/When Defeated: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_234 — The Invisible Hand

**Type/Stats:** Unit, cost 8, 4/7  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> When Played: Create 4 Battle Droid tokens.
> On Attack: Exhaust any number of friendly Separatist units. Deal 1 damage to the defending player's base for each unit exhausted this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_237 — Droid Deployment

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Create 2 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

