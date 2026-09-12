# j24-set:01 — Direct damage & removal

- **Group id (paste this):** `j24-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| J24_5 | Wrecker | Unit | 6 | 7/6 | Overwhelm |

## Per-card analysis & acceptance criteria

### J24_5 — Wrecker

**Type/Stats:** Unit, cost 6, 7/6  |  Traits: Clone, Fringe

**Rules text:**

> Overwhelm
> When Played: You may defeat a friendly resource. If you do, deal 5 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'defeat', 'ramp'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

