# twi-set:10 — Card advantage & disruption

- **Group id (paste this):** `twi-set:10`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_252 | Aggrieved Parliamentarian | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### TWI_252 — Aggrieved Parliamentarian

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Official, Separatist

**Rules text:**

> When Played: Choose an opponent. They shuffle their discard pile and put it on the bottom of their deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

