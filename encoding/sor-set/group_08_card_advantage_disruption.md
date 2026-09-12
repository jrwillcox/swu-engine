# sor-set:08 — Card advantage & disruption

- **Group id (paste this):** `sor-set:08`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_202 | Cantina Bouncer | Unit | 5 | 3/5 |  |
| SOR_206 | Mining Guild TIE Fighter | Unit | 1 | 1/2 |  |
| SOR_209 | Pirated Starfighter | Unit | 2 | 2/4 | Raid |
| SOR_246 | You're My Only Hope | Event | 3 |  |  |
| SOR_252 | Restock | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SOR_202 — Cantina Bouncer

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Fringe

**Rules text:**

> When Played: You may return a non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_206 — Mining Guild TIE Fighter

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> On Attack: You may pay [2 resources]. If you do, draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_209 — Pirated Starfighter

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> 
> When Played: Return a friendly non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_246 — You're My Only Hope

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Look at the top card of your deck. You may play it. It costs [5 resources] less. If your base has 5 or less remaining HP, you may play it for free instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['search'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_252 — Restock

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Choose up to 4 cards in a discard pile. Put them on the bottom of their owner's deck in a random order.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

