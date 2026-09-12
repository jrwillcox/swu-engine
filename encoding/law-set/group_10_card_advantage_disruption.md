# law-set:10 — Card advantage & disruption

- **Group id (paste this):** `law-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_224 | Liberty | Unit | 8 | 9/7 | Sentinel |
| LAW_225 | Han's Golden Dice | Upgrade | 1 |  |  |
| LAW_229 | The Master Codebreaker | Unit | 2 | 1/4 |  |
| LAW_236 | Bix Caleen | Unit | 4 | 4/5 |  |
| LAW_237 | Qui-Gon Jinn | Unit | 4 | 3/5 | Sentinel |
| LAW_238 | Scavenging Sandcrawler | Unit | 4 | 1/7 |  |
| LAW_240 | Milodon Rider | Unit | 6 | 5/6 | Ambush |

## Per-card analysis & acceptance criteria

### LAW_224 — Liberty

**Type/Stats:** Unit, cost 8, 9/7  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Sentinel
> When Played/On Attack: Exhaust an enemy unit and return all upgrades on it that cost 4 or less to their owner's hands.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** ReturnToHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_225 — Han's Golden Dice

**Type/Stats:** Upgrade, cost 1  |  Traits: Item

**Rules text:**

> Attached unit gains: “On Attack: Discard a card from your deck. If its cost is odd, create a Credit token.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_229 — The Master Codebreaker

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Underworld

**Rules text:**

> The first Gambit card you play each round costs 1 resource less.
> When Played: Search the top 8 cards of your deck for a Gambit card, reveal it, and draw it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_236 — Bix Caleen

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Fringe

**Rules text:**

> When Played/On Attack: You may discard a card from your hand. If you do, create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_237 — Qui-Gon Jinn

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Sentinel
> When Played/On Attack: Look at the top 3 cards of your deck. You may discard 1 of them. Put the rest back on top in any order.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'search'].

**Existing primitives that should suffice:** DiscardFromHand, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_238 — Scavenging Sandcrawler

**Type/Stats:** Unit, cost 4, 1/7  |  Traits: Transport, Vehicle

**Rules text:**

> On Attack: You may put a card from your discard pile on the bottom of your deck. If you do, create a Credit token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_240 — Milodon Rider

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Creature, Fringe

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played: You may return another friendly non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

