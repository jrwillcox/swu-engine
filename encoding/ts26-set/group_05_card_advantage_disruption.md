# ts26-set:05 — Card advantage & disruption

- **Group id (paste this):** `ts26-set:05`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_68 | Arms Deal | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TS26_68 — Arms Deal

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> You and an opponent each draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

