# jabba-the-hutt:08 — New primitive: control-change

- **Group id (paste this):** `jabba-the-hutt:08`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** control-change — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_170 | Double-Cross | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### LAW_170 — Double-Cross

**Type/Stats:** Event, cost 6  |  Traits: Trick

**Rules text:**

> Choose a friendly non-leader unit and an enemy non-leader unit. Exchange control of those units. The player who takes control of the lower-cost unit creates Credit tokens equal to the difference between those units' costs.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**⚠ Suspected NEW primitive:** control-change. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

