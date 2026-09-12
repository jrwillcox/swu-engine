# lof-set:07 — Card advantage & disruption

- **Group id (paste this):** `lof-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_184 | Second Sister | Unit | 4 | 3/6 |  |
| LOF_188 | As I Have Foreseen | Event | 1 |  |  |
| LOF_204 | Zuckuss | Unit | 5 | 4/7 |  |
| LOF_219 | Psychometry | Event | 1 |  |  |
| LOF_222 | A Precarious Predicament | Event | 2 |  |  |
| LOF_226 | Tip the Scale | Event | 2 |  |  |
| LOF_243 | Caretaker Matron | Unit | 2 | 0/4 |  |

## Per-card analysis & acceptance criteria

### LOF_184 — Second Sister

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> On Attack: You may discard 2 cards from your deck. For each Force card discarded this way, ready a resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_188 — As I Have Foreseen

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Look at the top card of your deck. You may use the Force (lose your Force token). If you do, play that card. It costs 4 resources less.

**Mechanical analysis:** trigger archetype `event`; effect families ['search'].

**Existing primitives that should suffice:** CostReduction, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_204 — Zuckuss

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Bounty Hunter, Force

**Rules text:**

> On Attack: Name a card, then discard the top card of the defending player's deck. If a card with that name is discarded, this unit gets +4/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_219 — Psychometry

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Choose another card in your discard pile. Search the top 5 cards of your deck for a card that shares a trait with the chosen card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_222 — A Precarious Predicament

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Return an enemy non-leader unit to its owner's hand unless its controller says, “It could be worse.” If they do, you may play a card named It's Worse from your hand or resources for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand, push_play_from_hand, push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_226 — Tip the Scale

**Type/Stats:** Event, cost 2  |  Traits: Force, Trick

**Rules text:**

> Look at an opponent's hand and discard a non-unit card from it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_243 — Caretaker Matron

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Fringe

**Rules text:**

> Action [Exhaust]: If you played a Force card this phase, draw a card.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

