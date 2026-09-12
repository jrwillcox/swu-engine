# ahsoka-tano:03 — Card advantage & disruption

- **Group id (paste this):** `ahsoka-tano:03`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_107 | Patrolling V-Wing | Unit | 2 | 1/1 |  |
| TWI_246 | Tranquility | Unit | 7 | 7/6 |  |

## Per-card analysis & acceptance criteria

### TWI_107 — Patrolling V-Wing

**Type/Stats:** Unit, cost 2, 1/1  |  Traits: Fighter, Vehicle

**Rules text:**

> When Played: Draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_246 — Tranquility

**Type/Stats:** Unit, cost 7, 7/6  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> When Played: You may return a Republic unit from your discard pile to your hand.
> On Attack: Each of the next 3 Republic cards you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

