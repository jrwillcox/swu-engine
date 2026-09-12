# twi-set:06 — Direct damage & removal

- **Group id (paste this):** `twi-set:06`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_256 | Hold-Out Blaster | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### TWI_256 — Hold-Out Blaster

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: You may have attached unit deal 1 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

