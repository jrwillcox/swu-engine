# han-solo:07 — New primitive: scaling-magnitude

- **Group id (paste this):** `han-solo:07`
- **Kind:** ability
- **Cards:** 2
- **⚠ New primitives suspected:** scaling-magnitude — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_97 | Admiral Ackbar | Unit | 3 | 1/4 | Restore |
| JTL_208 | Never Tell Me the Odds | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SOR_97 — Admiral Ackbar

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Official, Rebel

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> 
> When Played: You may deal damage to a unit equal to the number of units you control in its arena. 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** scaling-magnitude. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_208 — Never Tell Me the Odds

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Discard 3 cards from an opponent's deck and 3 cards from your deck. Deal damage to a unit equal to the number of cards with an odd cost discarded this way.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**⚠ Suspected NEW primitive:** scaling-magnitude. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

