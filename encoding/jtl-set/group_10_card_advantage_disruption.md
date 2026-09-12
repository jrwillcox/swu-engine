# jtl-set:10 — Card advantage & disruption

- **Group id (paste this):** `jtl-set:10`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_197 | Anakin Skywalker | Unit | 2 | 2/3 | Piloting |
| JTL_205 | Commence Patrol | Event | 1 |  |  |
| JTL_207 | Jam Communications | Event | 1 |  |  |
| JTL_220 | Skyway Cloud Car | Unit | 3 | 3/3 |  |
| JTL_221 | Stolen AT-Hauler | Unit | 3 | 4/5 |  |
| JTL_223 | Razor Crest | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### JTL_197 — Anakin Skywalker

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Force, Fringe, Pilot

**Rules text:**

> Piloting [2 resources Cunning Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When attached unit completes an attack (and survives): You may return this upgrade to its owner's hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_205 — Commence Patrol

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Put another card in a discard pile on the bottom of its owner's deck. If you do, create an X-Wing token.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_207 — Jam Communications

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Look at an opponent's hand and discard an event from it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_220 — Skyway Cloud Car

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> When Defeated: You may return a non-leader unit with 2 or less power to its owner's hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_221 — Stolen AT-Hauler

**Type/Stats:** Unit, cost 3, 4/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Defeated: Choose an opponent. For this phase, they may play this unit from its owner's discard pile for free.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_223 — Razor Crest

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> When a Pilot attaches to this unit: You may return a non-leader unit that costs 2 or less or an exhausted non-leader unit that costs 4 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

