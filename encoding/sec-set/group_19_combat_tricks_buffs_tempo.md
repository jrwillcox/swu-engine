# sec-set:19 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:19`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_260 | Inspector's Shuttle | Unit | 2 | 1/3 |  |
| SEC_261 | Inspiring Senator | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### SEC_260 — Inspector's Shuttle

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: Name a card, then an opponent reveals their hand. For each copy of the named card in their hand, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_261 — Inspiring Senator

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Official, Republic

**Rules text:**

> When Defeated: The next Official unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

