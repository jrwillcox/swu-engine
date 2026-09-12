# shd-han-solo:08 — New primitive: scaling-magnitude

- **Group id (paste this):** `shd-han-solo:08`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** scaling-magnitude — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_159 | The Chaos of War | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SHD_159 — The Chaos of War

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Deal damage to each player's base equal to the number of cards in that player's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** scaling-magnitude. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

