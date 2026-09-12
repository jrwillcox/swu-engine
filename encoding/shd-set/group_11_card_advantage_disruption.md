# shd-set:11 — Card advantage & disruption

- **Group id (paste this):** `shd-set:11`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_222 | Enticing Reward | Upgrade | 1 |  | Bounty |
| SHD_228 | Bounty Posting | Event | 1 |  |  |
| SHD_233 | Evacuate | Event | 6 |  |  |
| SHD_243 | Altering the Deal | Event | 1 |  |  |
| SHD_244 | No Bargain | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SHD_222 — Enticing Reward

**Type/Stats:** Upgrade, cost 1  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Search the top 10 cards of your deck for 2 non-unit cards, reveal them, and draw them. (Put the other cards on the bottom of your deck in a random order.) Then, if this unit isn't unique, discard a card from your hand.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_228 — Bounty Posting

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Search your deck for a Bounty upgrade, reveal it, and draw it. (Shuffle your deck.) 
> You may play that upgrade (paying its cost).

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'search'].

**Existing primitives that should suffice:** DrawCards, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_233 — Evacuate

**Type/Stats:** Event, cost 6  |  Traits: Tactic

**Rules text:**

> Return each non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_243 — Altering the Deal

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Discard a captured card guarded by a friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_244 — No Bargain

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Each opponent discards a card from their hand. Draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

