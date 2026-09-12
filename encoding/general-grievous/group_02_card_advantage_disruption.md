# general-grievous:02 — Card advantage & disruption

- **Group id (paste this):** `general-grievous:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_86 | Admiral Trench | Unit | 7 | 5/5 | Exploit |
| TWI_226 | Waylay | Event | 3 |  |  |
| TWI_257 | Private Manufacturing | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TWI_86 — Admiral Trench

**Type/Stats:** Unit, cost 7, 5/5  |  Traits: Official, Separatist

**Rules text:**

> Exploit 1 
> When Played: Return up to 3 units that were defeated this phase from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_226 — Waylay

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Return a non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_257 — Private Manufacturing

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Draw 2 cards. If you control no token units, put 2 cards from your hand on the bottom of your deck in any order.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

