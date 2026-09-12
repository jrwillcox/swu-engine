# jabba-the-hutt:04 — Card advantage & disruption

- **Group id (paste this):** `jabba-the-hutt:04`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_23 | Great Pit of Carkoon | Base |  | None/27 |  |
| LAW_136 | Syndicate Spice Runner | Unit | 2 | 2/2 |  |
| LAW_246 | The Axe Forgets | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LAW_23 — Great Pit of Carkoon

**Type/Stats:** Base

**Rules text:**

> Epic Action [discard a unit from your hand]: Search your deck for a card named The Sarlacc of Carkoon, reveal it, and draw it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['draw', 'search'].

**Existing primitives that should suffice:** DrawCards, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_136 — Syndicate Spice Runner

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Underworld

**Rules text:**

> When Played: Search the top 3 cards of your deck for an Underworld unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_246 — The Axe Forgets

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Return a non-leader unit that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

