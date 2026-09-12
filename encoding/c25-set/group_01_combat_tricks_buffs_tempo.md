# c25-set:01 — Combat tricks, buffs & tempo

- **Group id (paste this):** `c25-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| C25_5 | C-3PO | Unit | 1 | 1/3 |  |

## Per-card analysis & acceptance criteria

### C25_5 — C-3PO

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Republic

**Rules text:**

> Action [exhaust, return this unit to its owner's hand]: Give a unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

