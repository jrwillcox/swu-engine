# ic27-set:07 — Card advantage & disruption

- **Group id (paste this):** `ic27-set:07`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_194 | You're My Only Hope | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### IC27_194 — You're My Only Hope

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Look at the top card of your deck. You may play it. It costs 5 resources less. If your base has 5 or less remaining HP, you may play it for free instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['search'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

