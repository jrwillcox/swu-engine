# ahsoka-tano:06 — New primitive: scaling-magnitude

- **Group id (paste this):** `ahsoka-tano:06`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** scaling-magnitude — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_99 | Synchronized Strike | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TWI_99 — Synchronized Strike

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Deal damage to an enemy unit equal to the number of units you control in its arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** scaling-magnitude. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

