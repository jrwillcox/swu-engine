# sor-set:07 — Card advantage & disruption

- **Group id (paste this):** `sor-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_181 | Jabba the Hutt | Unit | 4 | 2/8 |  |
| SOR_183 | Bounty Hunter Crew | Unit | 6 | 4/4 | Ambush |
| SOR_187 | I Had No Choice | Event | 7 |  |  |
| SOR_188 | Chopper | Unit | 1 | 1/3 | Raid |
| SOR_199 | Bamboozle | Event | 2 |  |  |
| SOR_200 | Spark of Rebellion | Event | 2 |  |  |
| SOR_201 | Bodhi Rook | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### SOR_181 — Jabba the Hutt

**Type/Stats:** Unit, cost 4, 2/8  |  Traits: Hutt, Underworld

**Rules text:**

> Each TRICK event you play costs [1 resource] less. 
> 
> When Played: Search the top 8 cards of your deck for a TRICK event, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_183 — Bounty Hunter Crew

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Ambush (After you play this unit, it may ready and attack an enemy unit.)
> 
> When Played: You may return an event from a discard pile to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_187 — I Had No Choice

**Type/Stats:** Event, cost 7  |  Traits: Trick

**Rules text:**

> Choose up to 2 non-leader units. An opponent chooses 1 of those units. Return that unit to its owner's hand and put the other on the bottom of its owner's deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_188 — Chopper

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Rebel, Spectre

**Rules text:**

> While you control another SPECTRE unit, this unit gains Raid 1.
> 
> On Attack: Discard a card from the defending player's deck. If it's an event, exhaust a resource that player controls.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'ready_exhaust', 'keyword_grant', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, GrantKeyword, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_199 — Bamboozle

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> You may discard a [Cunning] card from your hand instead of paying this event's cost. 
> Exhaust a unit and return each upgrade on it to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_200 — Spark of Rebellion

**Type/Stats:** Event, cost 2  |  Traits: Spectre

**Rules text:**

> Look at an opponent's hand and discard a card from it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_201 — Bodhi Rook

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Rebel

**Rules text:**

> When Played: Look at an opponent's hand and discard a non-unit card from it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

