# han-solo:03 — Card advantage & disruption

- **Group id (paste this):** `han-solo:03`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_191 | Wolf Pack Escort | Unit | 1 | 2/1 |  |
| SOR_192 | Ezra Bridger | Unit | 3 | 3/4 |  |
| JTL_200 | Shuttle Tydirium | Unit | 3 | 2/4 |  |
| JTL_215 | BoShek | Unit | 3 | 3/4 | Piloting |

## Per-card analysis & acceptance criteria

### TWI_191 — Wolf Pack Escort

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> When Played: You may return a friendly non-leader, non-Vehicle unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_192 — Ezra Bridger

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Rebel, Spectre

**Rules text:**

> When this unit completes an attack: Look at the top card of your deck. You may play it, discard it, or leave it on top of your deck.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard', 'search'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_200 — Shuttle Tydirium

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> On Attack: Discard a card from your deck. If it has an odd cost, you may give an Experience token to another unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_215 — BoShek

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fringe, Pilot

**Rules text:**

> Piloting [2 resources Cunning] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: Discard 2 cards from your deck. Return each of those cards with an odd cost to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

