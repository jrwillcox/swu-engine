# lof-set:06 — Card advantage & disruption

- **Group id (paste this):** `lof-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_117 | Sifo-Dyas | Unit | 5 | 4/4 |  |
| LOF_121 | The Purrgil King | Unit | 8 | 4/12 | Restore |
| LOF_122 | Pillio Star Compass | Upgrade | 2 |  |  |
| LOF_125 | The Burden of Masters | Event | 1 |  |  |
| LOF_139 | Battle Fury | Upgrade | 2 |  |  |
| LOF_146 | Ki-Adi-Mundi | Unit | 4 | 4/4 |  |
| LOF_175 | Do or Do Not | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LOF_117 — Sifo-Dyas

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Defeated: Search the top 8 cards of your deck for any number of Clone units with combined cost 4 or less and discard them. (Put the other cards on the bottom of your deck in a random order.) For this phase, you may play those cards from your discard pile for free.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_121 — The Purrgil King

**Type/Stats:** Unit, cost 8, 4/12  |  Traits: Creature

**Rules text:**

> Restore 4
> When Played: Draw a card for each friendly unit with 7 or more remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_122 — Pillio Star Compass

**Type/Stats:** Upgrade, cost 2  |  Traits: Item

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: Search the top 3 cards of your deck for a unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order).

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_125 — The Burden of Masters

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Put a Force unit from your discard pile on the bottom of your deck. If you do, play a unit from your hand and give 2 Experience tokens to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, GiveToken, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_139 — Battle Fury

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> Attached unit gains: “On Attack: Discard a card from your hand.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_146 — Ki-Adi-Mundi

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: You may use the Force (lose your Force token). If you do, draw 2 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_175 — Do or Do Not

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> You may use the Force (lose your Force token). If you do, draw 2 cards. If you do not, draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

