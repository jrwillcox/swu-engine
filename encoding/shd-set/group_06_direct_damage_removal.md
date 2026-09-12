# shd-set:06 — Direct damage & removal

- **Group id (paste this):** `shd-set:06`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_255 | Lady Proxima | Unit | 1 | 0/4 |  |

## Per-card analysis & acceptance criteria

### SHD_255 — Lady Proxima

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Underworld

**Rules text:**

> When you play another Underworld card: You may deal 1 damage to a base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

