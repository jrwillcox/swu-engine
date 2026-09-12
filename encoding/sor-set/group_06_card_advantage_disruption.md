# sor-set:06 — Card advantage & disruption

- **Group id (paste this):** `sor-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_105 | General Krell | Unit | 5 | 5/4 |  |
| SOR_115 | Agent Kallus | Unit | 5 | 4/4 | Ambush |
| SOR_147 | Black One | Unit | 6 | 4/4 |  |
| SOR_150 | Heroic Sacrifice | Event | 1 |  |  |
| SOR_163 | Star Wing Scout | Unit | 3 | 4/1 |  |
| SOR_171 | Mission Briefing | Event | 3 |  |  |
| SOR_175 | Forced Surrender | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### SOR_105 — General Krell

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> Each other friendly unit gains: “When Defeated: You may draw a card.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_115 — Agent Kallus

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Imperial, Trooper

**Rules text:**

> Ambush (After you play this unit, he may ready and attack an enemy unit.)
> 
> When another unique unit is defeated: You may draw a card. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_147 — Black One

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> When Played/When Defeated: You may discard your hand. If you do, draw 3 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_150 — Heroic Sacrifice

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Draw a card, then attack with a unit. For this attack, it gets +2/+0 and gains: "When this unit deals combat damage: Defeat it."

**Mechanical analysis:** trigger archetype `constant`; effect families ['draw', 'defeat', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DrawCards, ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_163 — Star Wing Scout

**Type/Stats:** Unit, cost 3, 4/1  |  Traits: Fighter, Vehicle

**Rules text:**

> When Defeated: If you have the initiative, draw 2 cards.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_171 — Mission Briefing

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Choose a player. They draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_175 — Forced Surrender

**Type/Stats:** Event, cost 6  |  Traits: Plan

**Rules text:**

> Draw 2 cards. Each opponent whose base you've damaged this phase discards 2 cards from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

