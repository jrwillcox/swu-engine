# ic27-set:06 — Card advantage & disruption

- **Group id (paste this):** `ic27-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_155 | Han Solo | Unit | 3 | 5/3 | Saboteur |
| IC27_158 | Millennium Falcon | Unit | 4 | 4/4 |  |
| IC27_166 | I've Got A Bad Feeling | Event | 4 |  |  |
| IC27_167 | Lando Calrissian | Unit | 3 | 4/4 |  |
| IC27_168 | Cunning Ploy | Event | 4 |  |  |
| IC27_179 | Morgan Elsbeth | Unit | 2 | 1/5 |  |
| IC27_187 | Jar Jar Binks | Unit | 2 | 1/5 |  |

## Per-card analysis & acceptance criteria

### IC27_155 — Han Solo

**Type/Stats:** Unit, cost 3, 5/3  |  Traits: Rebel

**Rules text:**

> Saboteur
> When Played: Search the top 10 cards of your deck for a card and draw it, then discard a random card from your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_158 — Millennium Falcon

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Attack Ends: You may pay 1 resource. If you do, return a friendly unit that costs 3 or less to its owner's hand. If it's returned to your hand, you may play it for free.

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_166 — I've Got A Bad Feeling

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Return a non–leader unit to its owner's hand.
> Give a Shield token to a friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'token'].

**Existing primitives that should suffice:** ReturnToHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_167 — Lando Calrissian

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Official

**Rules text:**

> When Played: Return 3 friendly resources to their owners' hands. Then, you may resource up to 3 cards from your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_168 — Cunning Ploy

**Type/Stats:** Event, cost 4  |  Traits: Trick

**Rules text:**

> Look at an opponent's hand. You may discard a card from it. If you do, that player draws a card.
> Exhaust an enemy unit.
> You may attack with a unit. It gets +3/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'ready_exhaust', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus, ExhaustCard/ReadyCard, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_179 — Morgan Elsbeth

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Force, Imperial, Night

**Rules text:**

> On Attack: Reveal the top card of your deck. If it costs 6 or more, draw it. Otherwise, discard it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_187 — Jar Jar Binks

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Gungan, Official, Republic

**Rules text:**

> On Attack: Discard a card from your deck. If it costs 6 or more, this unit gets +4/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

