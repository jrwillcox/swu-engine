# twi-set:09 — Card advantage & disruption

- **Group id (paste this):** `twi-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_188 | Wartime Profiteering | Event | 1 |  |  |
| TWI_201 | Aid from the Innocent | Event | 5 |  |  |
| TWI_208 | Favorable Delegate | Unit | 2 | 1/5 |  |
| TWI_215 | Geonosis Patrol Fighter | Unit | 5 | 3/2 | Exploit |
| TWI_216 | Fives | Unit | 5 | 5/5 | Saboteur |
| TWI_220 | Shadowed Intentions | Upgrade | 3 |  |  |
| TWI_223 | Unmasking the Conspiracy | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### TWI_188 — Wartime Profiteering

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Look at cards from the top of your deck equal to the number of units that were defeated this phase. Draw 1 and put the others on the bottom of your deck in a random order.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_201 — Aid from the Innocent

**Type/Stats:** Event, cost 5  |  Traits: Gambit

**Rules text:**

> Search the top 10 cards of your deck for 2 Heroism non-unit cards and discard them. (Put the other cards on the bottom of your deck in a random order.)
> For this phase, you may play the discarded cards, and they each cost 2 resources less.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_208 — Favorable Delegate

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Official, Republic

**Rules text:**

> When Played: Draw a card.
> When Defeated: Discard a card from your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_215 — Geonosis Patrol Fighter

**Type/Stats:** Unit, cost 5, 3/2  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> When Played: You may return a non-leader unit that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_216 — Fives

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Saboteur
> When you play an event: You may put a Clone unit from your discard pile on the bottom of your deck. If you do, draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_220 — Shadowed Intentions

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> Attached unit gains: “This unit can't be captured, defeated, or returned to its owner's hand by enemy card abilities.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_223 — Unmasking the Conspiracy

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Discard a card from your hand. If you do, look at an opponent's hand and discard a card from it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

