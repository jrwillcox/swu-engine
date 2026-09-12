# sor-set:01 — Direct damage & removal

- **Group id (paste this):** `sor-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_6 | Emperor Palpatine | Leader | 8 | 4/10 |  |
| SOR_11 | Grand Inquisitor | Leader | 6 | 3/6 |  |
| SOR_13 | Cassian Andor | Leader | 6 | 4/6 | Saboteur |
| SOR_17 | Han Solo | Leader | 6 | 4/6 |  |
| SOR_25 | Tarkintown | Base |  | None/25 |  |
| SOR_38 | Count Dooku | Unit | 7 | 5/4 | Shielded |
| SOR_41 | Power of the Dark Side | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SOR_6 — Emperor Palpatine

**Type/Stats:** Leader, cost 8, 4/10  |  Traits: Force, Imperial, Official, Sith

**Rules text:**

> Action [1 resource, exhaust, defeat a friendly unit]: Deal 1 damage to a unit and draw a card.
> When Deployed: Take control of a damaged non-leader unit.
> 
> On Attack: You may defeat another friendly unit. If you do, deal 1 damage to a unit and draw a card.
> Epic Action: If you control 8 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'draw', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DrawCards, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_11 — Grand Inquisitor

**Type/Stats:** Leader, cost 6, 3/6  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Action [exhaust]: Deal 2 damage to a friendly unit with 3 or less power and ready it.
> On Attack: You may deal 1 damage to another friendly unit with 3 or less power and ready it.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_13 — Cassian Andor

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Rebel

**Rules text:**

> Action [1 resource, Exhaust]: If you've dealt 3 or more damage to an enemy base this phase, draw a card.
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> When you deal damage to an enemy base: You may draw a card. Use this ability only once each round.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_17 — Han Solo

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Underworld

**Rules text:**

> Action [exhaust]: Put a card from your hand into play as a resource and ready it. At the start of the next action phase, defeat a resource you control.
> On Attack: Put the top card of your deck into play as a resource and ready it. At the start of the next action phase, defeat a resource you control.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_25 — Tarkintown

**Type/Stats:** Base

**Rules text:**

> Epic Action: Deal 3 damage to a damaged non-leader unit.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_38 — Count Dooku

**Type/Stats:** Unit, cost 7, 5/4  |  Traits: Force, Separatist, Sith

**Rules text:**

> Shielded (When you play this unit, give him a Shield token.)
> 
> When Played: You may defeat a unit with 4 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_41 — Power of the Dark Side

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> An opponent chooses a unit they control. Defeat that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

