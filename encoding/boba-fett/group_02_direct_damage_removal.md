# boba-fett:02 — Direct damage & removal

- **Group id (paste this):** `boba-fett:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_181 | Elite P-38 Starfighter | Unit | 3 | 3/2 |  |
| JTL_183 | Zygerrian Starhopper | Unit | 2 | 2/3 |  |
| JTL_187 | Bossk | Unit | 4 | 4/4 | Piloting |
| JTL_189 | Boba Fett | Unit | 5 | 5/4 | Piloting, Shielded |
| JTL_230 | Electromagnetic Pulse | Event | 1 |  |  |
| JTL_237 | TIE Bomber | Unit | 2 | 0/4 |  |
| JTL_240 | Fett's Firespray | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### TWI_181 — Elite P-38 Starfighter

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> When Played/When Defeated: You may deal 1 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_183 — Zygerrian Starhopper

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Defeated: Deal 2 indirect damage to a player. (They assign 2 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_187 — Bossk

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Bounty Hunter, Pilot, Underworld

**Rules text:**

> On Attack: Exhaust the defender and deal 1 damage to it (if it's a unit).
> Piloting [2 resources Cunning Villainy]
> Attached unit gains: “On Attack: Exhaust the defender and deal 1 damage to it (if it's a unit).”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_189 — Boba Fett

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Bounty Hunter, Pilot, Underworld

**Rules text:**

> Shielded
> Piloting [2 resources Cunning Villainy] 
> When played as an upgrade: You may deal 1 damage to a unit. If attached unit is a Transport, you may deal 2 damage instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_230 — Electromagnetic Pulse

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Deal 2 damage to a Droid or Vehicle unit and exhaust it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_237 — TIE Bomber

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> On Attack: Deal 3 indirect damage to the defending player. (They assign 3 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_240 — Fett's Firespray

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played/On Attack: Deal 1 indirect damage to a player. If you control Boba Fett (as a unit, upgrade, or leader), deal 2 indirect damage instead. (They assign unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

