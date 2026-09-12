# lofp-set:03 — Miscellaneous abilities

- **Group id (paste this):** `lofp-set:03`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOFP_5 | Jedi Consular | Unit | 2 | 1/4 |  |
| LOFP_8 | Acolyte of the Beyond | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### LOFP_5 — Jedi Consular

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Force, Jedi

**Rules text:**

> Action [Exhaust, use the Force ]: Play a unit from your hand. It costs 2 resources less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** force-token, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOFP_8 — Acolyte of the Beyond

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Sith

**Rules text:**

> On Attack/When Defeated: The Force is with you .

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

