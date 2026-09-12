# general-grievous:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `general-grievous:04`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_206 | Independent Senator | Unit | 1 | 0/4 |  |
| TWI_217 | Tri-Droid Suppressor | Unit | 7 | 4/7 | Exploit |
| TWI_221 | In Pursuit | Event | 0 |  |  |
| TWI_236 | Grievous's Wheel Bike | Upgrade | 4 |  | Overwhelm |

## Per-card analysis & acceptance criteria

### TWI_206 — Independent Senator

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Official, Separatist

**Rules text:**

> Action [2 resources, Exhaust]: Exhaust a unit with 4 or less power.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_217 — Tri-Droid Suppressor

**Type/Stats:** Unit, cost 7, 4/7  |  Traits: Droid, Separatist, Vehicle, Walker

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> When Played: Exhaust an enemy ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_221 — In Pursuit

**Type/Stats:** Event, cost 0  |  Traits: Tactic

**Rules text:**

> Exhaust a friendly unit. If you do, exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_236 — Grievous's Wheel Bike

**Type/Stats:** Upgrade, cost 4  |  Traits: Vehicle

**Rules text:**

> While playing this upgrade on General Grievous, it costs 2 resources less to play.
> Attach to a non-Vehicle unit.
> Attached unit gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

