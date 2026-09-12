# sec-set:07 — Card advantage & disruption

- **Group id (paste this):** `sec-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_17 | Sabé | Leader | 5 | 3/6 | Raid |
| SEC_62 | Bardottan Ornithopter | Unit | 4 | 3/4 |  |
| SEC_72 | Scour the Archives | Event | 1 |  |  |
| SEC_75 | Knowledge and Defense | Event | 3 |  |  |
| SEC_90 | Director Krennic | Unit | 9 | 8/10 | Sentinel |
| SEC_105 | Renewed Friendship | Event | 4 |  |  |
| SEC_112 | Orn Free Taa | Unit | 2 | 0/4 |  |

## Per-card analysis & acceptance criteria

### SEC_17 — Sabé

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Naboo

**Rules text:**

> When a friendly unit deals combat damage to a base: You may exhaust this leader. If you do, look at the top 2 cards of the defending player's deck. Discard 1 of those cards. (Put the other back on top.)
> Raid 1
> When this unit deals combat damage to a base: Look at the defending player's hand. You may discard a card from it. If you do, that player draws a card.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'ready_exhaust', 'search'].

**Existing primitives that should suffice:** DiscardFromHand, deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_62 — Bardottan Ornithopter

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> When Played: You may disclose Vigilance (reveal a card from your hand with this aspect icon). If you do, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_72 — Scour the Archives

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Search the top 8 cards of your deck for an upgrade, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_75 — Knowledge and Defense

**Type/Stats:** Event, cost 3  |  Traits: Learned

**Rules text:**

> Give a unit –2/–2 for this phase.
> Draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_90 — Director Krennic

**Type/Stats:** Unit, cost 9, 8/10  |  Traits: Imperial, Official

**Rules text:**

> Sentinel
> When this unit is attacked: Discard a card from your deck. If it's a unit, you may return it to your hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_105 — Renewed Friendship

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Return a unit from your discard pile to your hand.
> Create 2 Spy tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_112 — Orn Free Taa

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Official, Republic, Twi'lek

**Rules text:**

> This unit gets +1/+0 for each Law card in your discard pile.
> When Played: Search the top 10 cards of your deck for a Law card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard', 'stat_buff'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

