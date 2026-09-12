# twi-set:08 — Card advantage & disruption

- **Group id (paste this):** `twi-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_88 | Reprocess | Event | 3 |  |  |
| TWI_100 | Petition the Senate | Event | 3 |  |  |
| TWI_101 | Mas Amedda | Unit | 2 | 0/4 |  |
| TWI_152 | Mace Windu's Lightsaber | Upgrade | 2 |  |  |
| TWI_168 | Old Access Codes | Upgrade | 1 |  |  |
| TWI_175 | Strategic Analysis | Event | 5 |  |  |
| TWI_187 | Cad Bane | Unit | 7 | 7/7 |  |

## Per-card analysis & acceptance criteria

### TWI_88 — Reprocess

**Type/Stats:** Event, cost 3  |  Traits: Supply

**Rules text:**

> Choose up to 4 units in your discard pile. Put them on the bottom of your deck in a random order and create that many Battle Droid tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_100 — Petition the Senate

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> If you control 3 or more Official units, draw 3 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_101 — Mas Amedda

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Official, Republic

**Rules text:**

> When you play another unit: You may exhaust this unit. If you do, search the top 4 cards of your deck for a unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `static`; effect families ['draw', 'ready_exhaust'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_152 — Mace Windu's Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: If attached unit is Mace Windu, draw 2 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_168 — Old Access Codes

**Type/Stats:** Upgrade, cost 1  |  Traits: Item

**Rules text:**

> When Played: If an opponent controls more units than you, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_175 — Strategic Analysis

**Type/Stats:** Event, cost 5  |  Traits: Plan

**Rules text:**

> Draw 3 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_187 — Cad Bane

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: This unit captures up to 3 enemy non-leader units with a total of 8 or less remaining HP.
> On Attack: The defending player may rescue a card they own guarded by this unit. If they do, draw 2 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

