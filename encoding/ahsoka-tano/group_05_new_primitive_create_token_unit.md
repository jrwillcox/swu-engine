# ahsoka-tano:05 — New primitive: create-token-unit

- **Group id (paste this):** `ahsoka-tano:05`
- **Kind:** ability
- **Cards:** 4
- **⚠ New primitives suspected:** create-token-unit — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_94 | Shaak Ti | Unit | 4 | 3/4 |  |
| TWI_97 | Captain Rex | Unit | 6 | 4/4 |  |
| TWI_144 | Batch Brothers | Unit | 3 | 2/1 |  |
| TWI_251 | Drop In | Event | 4 |  |  |

## Per-card analysis & acceptance criteria

### TWI_94 — Shaak Ti

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> Each friendly token unit gets +1/+0.
> On Attack: Create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_97 — Captain Rex

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When Played: Create 2 Clone Trooper tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_144 — Batch Brothers

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When Played: Create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_251 — Drop In

**Type/Stats:** Event, cost 4  |  Traits: Supply

**Rules text:**

> Create 2 Clone Trooper tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

