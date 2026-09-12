# sor-set:05 — Card advantage & disruption

- **Group id (paste this):** `sor-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_31 | Inferno Four | Unit | 2 | 2/3 |  |
| SOR_42 | Search Your Feelings | Event | 4 |  |  |
| SOR_67 | Rugged Survivors | Unit | 5 | 3/5 | Grit |
| SOR_91 | The Emperor's Legion | Event | 2 |  |  |
| SOR_96 | Mon Mothma | Unit | 2 | 1/3 |  |
| SOR_101 | Rogue Squadron Skirmisher | Unit | 6 | 4/6 | Ambush |
| SOR_102 | Home One | Unit | 8 | 7/7 | Restore |

## Per-card analysis & acceptance criteria

### SOR_31 — Inferno Four

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> When Played/When Defeated: Look at the top 2 cards of your deck. Put any number of them on the bottom of your deck and the rest on top in any order.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['search'].

**Existing primitives that should suffice:** deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_42 — Search Your Feelings

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Search your deck for a card and draw it. (Then, shuffle your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'search'].

**Existing primitives that should suffice:** DrawCards, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_67 — Rugged Survivors

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Fringe

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> 
> On Attack: If you control a leader unit, you may draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_91 — The Emperor's Legion

**Type/Stats:** Event, cost 2  |  Traits: Imperial, Supply

**Rules text:**

> Return each unit in your discard pile that was defeated this phase to your hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_96 — Mon Mothma

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Official, Rebel

**Rules text:**

> When Played: Search the top 5 cards of your deck for a REBEL card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_101 — Rogue Squadron Skirmisher

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel, Speeder, Vehicle

**Rules text:**

> Ambush (After you play this unit, it may ready and attack an enemy unit.)
> 
> When Played: Return a unit that costs 2 or less from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_102 — Home One

**Type/Stats:** Unit, cost 8, 7/7  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Restore 2
> 
> Each other friendly unit gains Restore 1.
> 
> When Played: Play a [Heroism] unit from your discard pile. It costs [3 resources] less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'keyword_grant'].

**Existing primitives that should suffice:** DiscardFromHand, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

