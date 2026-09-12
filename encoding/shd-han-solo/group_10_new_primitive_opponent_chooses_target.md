# shd-han-solo:10 — New primitive: opponent-chooses-target

- **Group id (paste this):** `shd-han-solo:10`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** opponent-chooses-target — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_246 | Grey Squadron Y-Wing | Unit | 2 | 1/3 |  |

## Per-card analysis & acceptance criteria

### SHD_246 — Grey Squadron Y-Wing

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> On Attack: An opponent chooses a unit or base they control. You may deal 2 damage to it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** opponent-chooses-target. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

