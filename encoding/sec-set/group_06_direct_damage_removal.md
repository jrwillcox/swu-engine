# sec-set:06 — Direct damage & removal

- **Group id (paste this):** `sec-set:06`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_254 | Heroic ARC-170 | Unit | 4 | 4/3 |  |
| SEC_263 | Assassin Probe | Unit | 5 | 4/4 |  |
| SEC_264 | Clandestine Connections | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### SEC_254 — Heroic ARC-170

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> When Played: If you control a damaged unit, you may deal 2 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_263 — Assassin Probe

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Droid, Separatist

**Rules text:**

> When Defeated: Deal 1 damage to each exhausted enemy ground unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_264 — Clandestine Connections

**Type/Stats:** Upgrade, cost 2  |  Traits: Supply

**Rules text:**

> Attached unit gains: “On Attack: You may pay 2 resources. If you do, deal 2 damage to a base.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

