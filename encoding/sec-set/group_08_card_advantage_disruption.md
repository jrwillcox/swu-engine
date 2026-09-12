# sec-set:08 — Card advantage & disruption

- **Group id (paste this):** `sec-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_125 | Reconnaissance | Event | 2 |  |  |
| SEC_128 | Convene the Senate | Event | 3 |  |  |
| SEC_187 | General Grievous | Unit | 2 | 3/3 | Hidden |
| SEC_200 | Junior Senator | Unit | 2 | 3/2 |  |
| SEC_205 | Obi-Wan Kenobi | Unit | 4 | 4/5 |  |
| SEC_211 | Faith in Your Friends | Event | 2 |  |  |
| SEC_218 | Cikatro Vizago | Unit | 3 | 3/4 |  |

## Per-card analysis & acceptance criteria

### SEC_125 — Reconnaissance

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> If you control a ground unit and a space unit, draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_128 — Convene the Senate

**Type/Stats:** Event, cost 3  |  Traits: Law

**Rules text:**

> Search the top 8 cards of your deck for up to 2 Official units, reveal them, and draw them. (Put the other cards on the bottom of your deck in a random order.)
> Create a Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_187 — General Grievous

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Official, Separatist

**Rules text:**

> Hidden (This unit can't be attacked if he was played this phase.)
> When this unit is attacked: Return him to his owner's hand (before damage is dealt).

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_200 — Junior Senator

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Official, Republic

**Rules text:**

> When Played: You may return an upgrade that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_205 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> When this unit deals combat damage to a base: Discard a card from the defending player's deck. For this phase, you may play that card from their discard pile, ignoring its aspect penalties.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_211 — Faith in Your Friends

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Search the top 3 cards of your deck for a card and draw it. Then, you may disclose CunningCunningCunningHeroismHeroism (reveal cards from your hand with these aspect icons among them). If you do, create 2 Spy tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, disclose, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_218 — Cikatro Vizago

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Underworld

**Rules text:**

> On Attack: Reveal the top card of your deck. An opponent may pay 1 resource. If they don't, draw that card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

