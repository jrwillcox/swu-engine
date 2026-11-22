# ic27-set:05 — Card advantage & disruption

- **Group id (paste this):** `ic27-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_78 | Anakin Skywalker | Unit | 5 | 7/4 |  |
| IC27_84 | Negotiator | Unit | 9 | 9/7 | Sentinel |
| IC27_87 | Issue a Command | Event | 4 |  |  |
| IC27_116 | Black One | Unit | 3 | 2/2 |  |
| IC27_122 | The Ghost | Unit | 7 | 7/7 | Overwhelm |
| IC27_144 | Jango Fett | Unit | 4 | 4/4 | Ambush |
| IC27_145 | Poggle the Lesser | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### IC27_78 — Anakin Skywalker

**Type/Stats:** Unit, cost 5, 7/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Defeated: Search your deck for a card named Darth Vader, reveal it, and draw it.
> While this unit is in your discard pile, ignore the aspect penalties on cards you play named Darth Vader.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw', 'discard', 'search'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_84 — Negotiator

**Type/Stats:** Unit, cost 9, 9/7  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> On Attack/When Defeated: Resource the top card of your deck. Then, you may return a friendly resource to its owner's hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_87 — Issue a Command

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> Reveal the top card of your deck. If it's a unit, draw it.
> Give an Experience token to a friendly unit.
> Resource this event.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'token', 'ramp'].

**Existing primitives that should suffice:** DrawCards, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_116 — Black One

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> When Played/When Defeated: Draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_122 — The Ghost

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Rebel, Spectre, Transport, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When a friendly unit deals damage to an enemy base: If you have 7 or fewer cards in your hand, draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_144 — Jango Fett

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Bounty Hunter, Separatist

**Rules text:**

> Ambush
> When Defeated: You may discard a card from your hand. If you do, return an event from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_145 — Poggle the Lesser

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Official, Separatist

**Rules text:**

> On Attack: You may pay 1 resource and discard a card from your hand. If you do, the next card you play this phase costs 3 resources less.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

