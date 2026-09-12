# shd-set:08 — Card advantage & disruption

- **Group id (paste this):** `shd-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_99 | Echo | Unit | 4 | 4/4 | Restore |
| SHD_102 | The Marauder | Unit | 5 | 4/5 | Ambush |
| SHD_105 | Spark of Hope | Event | 2 |  |  |
| SHD_108 | Enforced Loyalty | Event | 2 |  |  |
| SHD_115 | Cobb Vanth | Unit | 3 | 3/2 |  |
| SHD_127 | Commission | Event | 1 |  | Smuggle |
| SHD_134 | Guavian Antagonizer | Unit | 1 | 2/3 | Bounty, Saboteur |

## Per-card analysis & acceptance criteria

### SHD_99 — Echo

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Clone, Fringe

**Rules text:**

> Restore 2
> When Played: You may discard a card from your hand. Give 2 Experience tokens to a unit in play with the same name as the discarded card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_102 — The Marauder

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> Ambush
> When Played: Choose a card in your discard pile. Put it into play as a resource if it shares a name with a unit you control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_105 — Spark of Hope

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Choose a unit in your discard pile. If it was defeated this phase, put it into play as a resource.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_108 — Enforced Loyalty

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> Defeat a friendly unit. If you do, draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'defeat'].

**Existing primitives that should suffice:** DrawCards, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_115 — Cobb Vanth

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Fringe, Official

**Rules text:**

> When Defeated: Search the top 10 cards of your deck for a unit that costs 2 or less and discard it. For this phase, you may play that card from your discard pile for free.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_127 — Commission

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Search the top 10 cards of your deck for a Bounty Hunter, Item, or Transport card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)
> Smuggle [3 resources Command]

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_134 — Guavian Antagonizer

**Type/Stats:** Unit, cost 1, 2/3  |  Traits: Trooper, Underworld

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> Bounty — Draw a card. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

