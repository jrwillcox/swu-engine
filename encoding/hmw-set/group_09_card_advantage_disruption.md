# hmw-set:09 — Card advantage & disruption

- **Group id (paste this):** `hmw-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_103 | Disposable B1 | Unit | 1 | 2/1 |  |
| HMW_122 | Boga | Unit | 6 | 6/6 |  |
| HMW_148 | Local Support | Upgrade | 2 |  |  |
| HMW_166 | Gungi | Unit | 3 | 2/5 | Grit |
| HMW_173 | Rebel Operation | Event | 4 |  |  |
| HMW_180 | Stormchaser | Unit | 2 | 3/2 |  |
| HMW_189 | Neebray Manta | Unit | 8 | 7/6 |  |

## Per-card analysis & acceptance criteria

### HMW_103 — Disposable B1

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> When Played: If another friendly unit entered play this phase (including leader and token units), draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_122 — Boga

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Creature

**Rules text:**

> When Played/When Defeated: Choose a non-vehicle unit in your discard pile not named Boga. For this phase, you may play that unit from your discard pile. It costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_148 — Local Support

**Type/Stats:** Upgrade, cost 2  |  Traits: Supply

**Rules text:**

> When Played: Reveal the top card of your deck. If it shares a trait with a friendly unit, draw it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_166 — Gungi

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Force, Jedi, Wookiee

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on him.)
> When this unit is dealt damage and survives: You may discard a card from your hand. If you do, ready this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard', 'ready_exhaust'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_173 — Rebel Operation

**Type/Stats:** Event, cost 4  |  Traits: Plan, Rebel

**Rules text:**

> This card costs 1 resource less to play for each friendly Rebel unit and leader.
> Draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_180 — Stormchaser

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Tusken

**Rules text:**

> When Played: You may reveal a Disaster card from your hand. If you do or if there's a Disaster card in your discard pile, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_189 — Neebray Manta

**Type/Stats:** Unit, cost 8, 7/6  |  Traits: Creature

**Rules text:**

> When Played: Draw 3 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

