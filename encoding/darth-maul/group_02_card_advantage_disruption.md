# darth-maul:02 — Card advantage & disruption

- **Group id (paste this):** `darth-maul:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_59 | Nightsister Warrior | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### LOF_59 — Nightsister Warrior

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Night

**Rules text:**

> When Defeated: Draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

