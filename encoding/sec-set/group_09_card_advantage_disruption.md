# sec-set:09 — Card advantage & disruption

- **Group id (paste this):** `sec-set:09`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_230 | Charged with Espionage | Event | 2 |  |  |
| SEC_232 | Kreia's Whispers | Event | 2 |  |  |
| SEC_233 | Beguile | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_230 — Charged with Espionage

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> You may disclose CunningCunning (reveal cards from your hand with these aspect icons among them). If you do, look at an opponent's hand and discard a unit from it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_232 — Kreia's Whispers

**Type/Stats:** Event, cost 2  |  Traits: Force, Learned

**Rules text:**

> Draw 3 cards, then put a card from your hand on the top of your deck and another card from your hand on the bottom of your deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_233 — Beguile

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Look at an opponent's hand. Then, choose a non-leader unit that opponent controls that costs 6 or less and return it to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

