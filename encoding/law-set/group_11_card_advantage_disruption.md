# law-set:11 — Card advantage & disruption

- **Group id (paste this):** `law-set:11`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_241 | The Blade Wing | Unit | 6 | 3/3 |  |
| LAW_242 | Improvise | Event | 1 |  |  |
| LAW_245 | Salvaged Materials | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### LAW_241 — The Blade Wing

**Type/Stats:** Unit, cost 6, 3/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Played: You may return a non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_242 — Improvise

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Look at the top card of your deck. You may play it. It costs 1 resource less. If you don't, you may discard it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'ramp', 'search'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_245 — Salvaged Materials

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Play an Item upgrade from your discard pile. It costs 3 resources less. At the start of the next regroup phase, defeat it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

