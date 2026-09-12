# shd-han-solo:07 — New primitive: sacrifice-resource-cost

- **Group id (paste this):** `shd-han-solo:07`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** sacrifice-resource-cost — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_154 | Wrecker | Unit | 6 | 7/6 | Overwhelm |

## Per-card analysis & acceptance criteria

### SHD_154 — Wrecker

**Type/Stats:** Unit, cost 6, 7/6  |  Traits: Clone, Fringe

**Rules text:**

> Overwhelm
> When Played: You may defeat a friendly resource. If you do, deal 5 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'defeat', 'ramp'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**⚠ Suspected NEW primitive:** sacrifice-resource-cost. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

