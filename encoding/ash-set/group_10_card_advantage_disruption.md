# ash-set:10 — Card advantage & disruption

- **Group id (paste this):** `ash-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_128 | Bothan-5 | Unit | 5 | 4/5 |  |
| ASH_169 | Axe Woves | Unit | 3 | 2/4 |  |
| ASH_172 | Razor Crest | Unit | 4 | 3/5 | Saboteur |
| ASH_185 | Intimidation | Event | 2 |  |  |
| ASH_220 | Remnant Lookouts | Unit | 3 | 3/3 |  |
| ASH_229 | Camtono | Upgrade | 2 |  |  |
| ASH_230 | Improvised Identity | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### ASH_128 — Bothan-5

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: New Republic, Transport, Vehicle

**Rules text:**

> When another friendly non-Vehicle unit is defeated: You may have this unit capture that unit from your discard pile. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_169 — Axe Woves

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Mandalorian

**Rules text:**

> When you draw 1 or more cards (including during the regroup phase): Give an Advantage token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_172 — Razor Crest

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: You may discard a card from your hand. If you do, this unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_185 — Intimidation

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> If you control a unit with 4 or more power, draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_220 — Remnant Lookouts

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: Look at an opponent's hand. You may discard a card from it. If you do, they draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_229 — Camtono

**Type/Stats:** Upgrade, cost 2  |  Traits: Item

**Rules text:**

> Attached unit gains: “When Attack Ends: Look at the top card of your deck. If it costs 2 or less, you may play it for free.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['search'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_230 — Improvised Identity

**Type/Stats:** Upgrade, cost 2  |  Traits: Gambit

**Rules text:**

> Attach to a ground unit.
> Attached unit gains: “Action: Search the top 3 cards of your deck for a ground unit and discard it. Then, you may attack with this unit. For this attack, this unit gains the discarded unit's abilities. Use this ability only once each round.”

**Mechanical analysis:** trigger archetype `activated`; effect families ['discard', 'attack_grant'].

**Existing primitives that should suffice:** DiscardFromHand, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

