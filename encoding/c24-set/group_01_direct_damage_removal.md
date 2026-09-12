# c24-set:01 — Direct damage & removal

- **Group id (paste this):** `c24-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| C24_1 | Count Dooku | Unit | 7 | 5/4 | Shielded |

## Per-card analysis & acceptance criteria

### C24_1 — Count Dooku

**Type/Stats:** Unit, cost 7, 5/4  |  Traits: Force, Separatist, Sith

**Rules text:**

> Shielded
> 
> When Played: You may defeat a unit with 4 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

