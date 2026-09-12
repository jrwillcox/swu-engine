# p25-set:05 — Miscellaneous abilities

- **Group id (paste this):** `p25-set:05`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P25_43 | Han Solo | Unit | 7 | 6/6 | Ambush |

## Per-card analysis & acceptance criteria

### P25_43 — Han Solo

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Underworld

**Rules text:**

> Ambush 
> 
> While attacking, this unit deals combat damage before the defender.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

