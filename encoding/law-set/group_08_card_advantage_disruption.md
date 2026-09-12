# law-set:08 — Card advantage & disruption

- **Group id (paste this):** `law-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_83 | Broken Horn | Unit | 5 | 5/4 |  |
| LAW_84 | Krrsantan | Unit | 8 | 7/7 | Ambush, Overwhelm |
| LAW_94 | Hondo Ohnaka | Unit | 5 | 3/7 |  |
| LAW_96 | Rhydonium Detonation | Event | 7 |  |  |
| LAW_103 | Display Piece | Event | 4 |  |  |
| LAW_107 | Swoop Bike Marauder | Unit | 4 | 4/4 |  |
| LAW_125 | Watchful | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### LAW_83 — Broken Horn

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: If you have fewer cards in hand than an opponent, draw a card. If you control fewer resources than an opponent, resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_84 — Krrsantan

**Type/Stats:** Unit, cost 8, 7/7  |  Traits: Bounty Hunter, Underworld, Wookiee

**Rules text:**

> Ambush
> Overwhelm
> Action [discard 2 cards from your hand]: Return this unit to your hand (from play).

**Mechanical analysis:** trigger archetype `activated`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_94 — Hondo Ohnaka

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Underworld

**Rules text:**

> You may look at the top card of your deck at any time.
> Action: Play the top card of your deck (paying its cost). Use this ability only once each round.

**Mechanical analysis:** trigger archetype `activated`; effect families ['search'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_96 — Rhydonium Detonation

**Type/Stats:** Event, cost 7  |  Traits: Tactic

**Rules text:**

> Each player may return a non-leader unit to its owner's hand. Then, defeat all non-leader units.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'defeat'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_103 — Display Piece

**Type/Stats:** Event, cost 4  |  Traits: Supply

**Rules text:**

> Defeat an enemy non-leader unit. Its controller resources it from its owner's discard pile.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_107 — Swoop Bike Marauder

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Underworld

**Rules text:**

> On Attack: Draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_125 — Watchful

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attached unit gains: “On Attack: Look at the top card of a deck. You may put it on the bottom of that deck. (Otherwise, leave it on top.)”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['search'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

