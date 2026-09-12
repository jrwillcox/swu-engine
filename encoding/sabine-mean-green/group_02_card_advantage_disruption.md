# sabine-mean-green:02 — Card advantage & disruption

- **Group id (paste this):** `sabine-mean-green:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_99 | Bright Hope | Unit | 4 | 2/6 | Sentinel |

## Per-card analysis & acceptance criteria

### SOR_99 — Bright Hope

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> When Played: You may return a friendly non-leader ground unit to its owner's hand. If you do, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'return_hand'].

**Existing primitives that should suffice:** DrawCards, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

