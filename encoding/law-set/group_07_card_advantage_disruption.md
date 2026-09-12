# law-set:07 — Card advantage & disruption

- **Group id (paste this):** `law-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_2 | Tobias Beckett | Leader | 5 | 4/6 |  |
| LAW_5 | Jyn Erso | Leader | 5 | 3/6 |  |
| LAW_12 | Sebulba | Leader | 4 | 2/5 | Raid |
| LAW_18 | Lando Calrissian | Leader | 6 | 4/7 |  |
| LAW_26 | Shipbreaking Yard | Base |  | None/26 |  |
| LAW_29 | Citadel Research Center | Base |  | None/26 |  |
| LAW_48 | Chio Fain | Unit | 2 | 2/4 |  |

## Per-card analysis & acceptance criteria

### LAW_2 — Tobias Beckett

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Choose a friendly unit. An opponent takes control of it. If they do, create a Credit token.
> When Deployed: Defeat any number of units you own but don't control. For each unit defeated this way, create a Credit token and draw a card.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['draw', 'defeat'].

**Existing primitives that should suffice:** DrawCards, create-token-unit, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_5 — Jyn Erso

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Rebel

**Rules text:**

> Action [1 resource, Exhaust]: If a friendly Rebel unit was defeated this phase, search the top 3 cards of your deck for a card and draw it. (Put the other cards on the bottom of your deck in a random order.)
> On Attack: If a friendly Rebel unit was defeated this phase, search the top 3 cards of your deck for a card and draw it.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_12 — Sebulba

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Fringe

**Rules text:**

> Action [Exhaust, discard a card from your deck]: A friendly unit gains Raid 1 for this phase.
> Raid 1
> On Attack: Discard a card from your deck.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'keyword_grant'].

**Existing primitives that should suffice:** DiscardFromHand, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_18 — Lando Calrissian

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Underworld

**Rules text:**

> Action [1 resource, Exhaust]: Choose an aspect, then discard a card from a deck. If it has the chosen aspect, create a Credit token.
> When Deployed: You may defeat a friendly Credit token. If you do, create 3 Credit tokens.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, DefeatUnit/Upgrade, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_26 — Shipbreaking Yard

**Type/Stats:** Base

**Rules text:**

> Epic Action: Discard 3 cards from your deck. You may return a card discarded this way to the top of your deck.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_29 — Citadel Research Center

**Type/Stats:** Base

**Rules text:**

> Epic Action [1 resource]: Return a friendly resource to its owner's hand. If you do, resource the top card of your deck.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_48 — Chio Fain

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> On Attack: You may choose 2 players. If you do, they each draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

