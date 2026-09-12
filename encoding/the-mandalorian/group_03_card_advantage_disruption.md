# the-mandalorian:03 — Card advantage & disruption

- **Group id (paste this):** `the-mandalorian:03`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_41 | Kuiil | Unit | 2 | 2/3 | Restore |
| SHD_44 | Razor Crest | Unit | 4 | 3/4 | Restore |
| SHD_206 | Spare the Target | Event | 3 |  |  |
| SHD_245 | Greef Karga | Unit | 2 | 2/2 |  |
| SHD_253 | This Is The Way | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SHD_41 — Kuiil

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fringe

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> On Attack: Discard a card from your deck. If it shares an aspect with your base, return it to your hand.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_44 — Razor Crest

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> 
> When Played: You may return an upgrade from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_206 — Spare the Target

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Return an enemy non-leader unit to its owner's hand. Collect that unit's Bounties.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_245 — Greef Karga

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fringe, Official

**Rules text:**

> When Played: Search the top 5 cards of your deck for an upgrade, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_253 — This Is The Way

**Type/Stats:** Event, cost 2  |  Traits: Mandalorian

**Rules text:**

> Search the top 8 cards of your deck for up to 2 Mandalorian and/or upgrade cards, reveal them, and draw them. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

