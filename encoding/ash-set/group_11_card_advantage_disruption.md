# ash-set:11 — Card advantage & disruption

- **Group id (paste this):** `ash-set:11`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_232 | Full of Surprises | Event | 2 |  |  |
| ASH_235 | Sense Through the Force | Event | 2 |  |  |
| ASH_236 | Far Far Away | Event | 3 |  |  |
| ASH_246 | Exploit Advantage | Event | 2 |  |  |
| ASH_247 | One Must Destroy to Create | Event | 3 |  |  |
| ASH_260 | Mos Espa Watermonger | Unit | 2 | 1/3 |  |

## Per-card analysis & acceptance criteria

### ASH_232 — Full of Surprises

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Return an upgrade that costs 2 or less to its owner's hand.
> Give a Shield token to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'token'].

**Existing primitives that should suffice:** ReturnToHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_235 — Sense Through the Force

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Choose a number, then search the top 5 cards of your deck for a card, reveal it, and draw it. If its cost is the chosen number, you may give 3 Advantage tokens to a Force unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_236 — Far Far Away

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Return a friendly non-leader unit to its owner's hand. If you do, return an enemy non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_246 — Exploit Advantage

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Defeat a friendly upgrade. If you do, draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'defeat'].

**Existing primitives that should suffice:** DrawCards, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_247 — One Must Destroy to Create

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Defeat a friendly non-leader unit. Then, you may play that unit from your discard pile for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_260 — Mos Espa Watermonger

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fringe

**Rules text:**

> When Played: You may draw a card. If you do, discard a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

