# han-solo:02 — Direct damage & removal

- **Group id (paste this):** `han-solo:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_204 | Greedo | Unit | 1 | 3/1 |  |

## Per-card analysis & acceptance criteria

### SOR_204 — Greedo

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Defeated: You may discard a card from your deck. If it's not a unit, deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

