# law-set:09 — Card advantage & disruption

- **Group id (paste this):** `law-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_138 | Undercity Hunting Team | Unit | 5 | 5/5 |  |
| LAW_159 | Expendable Mercenary | Unit | 4 | 3/3 |  |
| LAW_176 | Sebulba's Podracer | Unit | 3 | 3/3 |  |
| LAW_192 | Bracca Shipbreaker | Unit | 3 | 4/3 |  |
| LAW_194 | Doctor Aphra | Unit | 4 | 4/5 |  |
| LAW_200 | Salvaged Blaster | Upgrade | 2 |  |  |
| LAW_217 | Hold For Questioning | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### LAW_138 — Undercity Hunting Team

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: Search the top 5 cards of your deck for a Bounty Hunter unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_159 — Expendable Mercenary

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Defeated: You may resource this unit from its owner's discard pile.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_176 — Sebulba's Podracer

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Speeder, Vehicle

**Rules text:**

> When you discard a card from your deck: You may ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard', 'ready_exhaust'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_192 — Bracca Shipbreaker

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Fringe

**Rules text:**

> On Attack: Discard a card from your deck.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_194 — Doctor Aphra

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Underworld

**Rules text:**

> On Attack: Discard 3 cards from your deck. You may return an Underworld card discarded this way to your hand.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_200 — Salvaged Blaster

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Action: If this upgrade was discarded from your hand or deck this phase, play it from your discard pile (paying its cost).

**Mechanical analysis:** trigger archetype `activated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_217 — Hold For Questioning

**Type/Stats:** Event, cost 3  |  Traits: Law

**Rules text:**

> Exhaust an enemy unit. If you do, look at its controller's hand and discard a card from it that shares an aspect with that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'ready_exhaust'].

**Existing primitives that should suffice:** DiscardFromHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

