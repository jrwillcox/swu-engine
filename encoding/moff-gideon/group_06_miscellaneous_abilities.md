# moff-gideon:06 — Miscellaneous abilities

- **Group id (paste this):** `moff-gideon:06`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_234 | Incinerator Trooper | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### SHD_234 — Incinerator Trooper

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Trooper

**Rules text:**

> While attacking, this unit deals combat damage before the defender. (If the defender is defeated, it deals no combat damage.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

