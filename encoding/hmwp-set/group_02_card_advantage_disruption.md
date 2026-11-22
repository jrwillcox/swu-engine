# hmwp-set:02 — Card advantage & disruption

- **Group id (paste this):** `hmwp-set:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_8 | Boga | Unit | 6 | 6/6 |  |

## Per-card analysis & acceptance criteria

### HMWP_8 — Boga

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Creature

**Rules text:**

> When Played/When Defeated: Choose a non-vehicle unit in your discard pile not named Boga. For this phase, you may play that unit from your discard pile. It costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

