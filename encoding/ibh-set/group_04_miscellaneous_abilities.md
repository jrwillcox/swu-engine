# ibh-set:04 — Miscellaneous abilities

- **Group id (paste this):** `ibh-set:04`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IBH_10 | Han Solo | Unit | 6 | 4/6 | Raid |

## Per-card analysis & acceptance criteria

### IBH_10 — Han Solo

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> On Attack:The defender gets –2/–0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

