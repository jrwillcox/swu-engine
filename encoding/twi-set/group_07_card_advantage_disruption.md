# twi-set:07 — Card advantage & disruption

- **Group id (paste this):** `twi-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_4 | Yoda | Leader | 7 | 4/9 | Restore |
| TWI_8 | Padmé Amidala | Leader | 5 | 2/7 | Coordinate, Restore |
| TWI_25 | Shadow Collective Camp | Base |  | None/25 |  |
| TWI_35 | Morgan Elsbeth | Unit | 4 | 3/6 | Restore |
| TWI_40 | A Fine Addition | Event | 0 |  |  |
| TWI_47 | Satine Kryze | Unit | 4 | 0/6 |  |
| TWI_68 | Foresight | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### TWI_4 — Yoda

**Type/Stats:** Leader, cost 7, 4/9  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust]: If a unit left play this phase, draw a card, then put a card from your hand on the top or bottom of your deck.
> Restore 2
> When Deployed: You may discard a card from your deck. If you do, defeat an enemy non-leader unit that costs the same as or less than the discarded card.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['draw', 'discard', 'defeat'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_8 — Padmé Amidala

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Naboo, Official, Republic

**Rules text:**

> Coordinate — Action [1 resource, Exhaust]: Search the top 3 cards of your deck for a Republic card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order. Gain this ability while you control 3 or more units.)
> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> Coordinate — On Attack: Search the top 3 cards of your deck for a Republic card, reveal it, and draw it.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_25 — Shadow Collective Camp

**Type/Stats:** Base

**Rules text:**

> When you deploy a leader: Draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_35 — Morgan Elsbeth

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Force, Imperial, Official

**Rules text:**

> Restore 1
> On Attack: You may defeat another friendly unit. If you do, draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'defeat'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_40 — A Fine Addition

**Type/Stats:** Event, cost 0  |  Traits: Supply

**Rules text:**

> If an enemy unit was defeated this phase, play an upgrade from your hand or from any player's discard pile, ignoring its aspect penalty.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_47 — Satine Kryze

**Type/Stats:** Unit, cost 4, 0/6  |  Traits: Mandalorian, Official

**Rules text:**

> Each unit (including enemy units) gains: “Action [Exhaust]: Discard cards from an opponent's deck equal to half this unit's remaining HP, rounded up.”

**Mechanical analysis:** trigger archetype `activated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_68 — Foresight

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attached unit gains: “When the regroup phase starts (before drawing cards): Name a card, then look at the top card of your deck. If it's the named card, you may reveal and draw it.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['draw', 'search'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

