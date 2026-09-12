# jtl-set:07 — Direct damage & removal

- **Group id (paste this):** `jtl-set:07`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_239 | TIE Dagger Vanguard | Unit | 3 | 2/2 |  |
| JTL_248 | Dilapidated Ski Speeder | Unit | 3 | 3/7 |  |

## Per-card analysis & acceptance criteria

### JTL_239 — TIE Dagger Vanguard

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Fighter, First Order, Sith, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to a damaged unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_248 — Dilapidated Ski Speeder

**Type/Stats:** Unit, cost 3, 3/7  |  Traits: Resistance, Speeder, Vehicle

**Rules text:**

> When Played: Deal 3 damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

