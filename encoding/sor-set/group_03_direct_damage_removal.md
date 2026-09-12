# sor-set:03 — Direct damage & removal

- **Group id (paste this):** `sor-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_134 | Ruthless Raider | Unit | 6 | 4/6 |  |
| SOR_138 | Force Lightning | Event | 1 |  |  |
| SOR_146 | Zeb Orrelios | Unit | 5 | 5/5 |  |
| SOR_153 | Saw Gerrera | Unit | 4 | 5/4 |  |
| SOR_158 | Jedha Agitator | Unit | 2 | 2/1 | Saboteur |
| SOR_167 | Force Throw | Event | 1 |  |  |
| SOR_170 | Power Failure | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SOR_134 — Ruthless Raider

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played/When Defeated: Deal 2 damage to an enemy base and 2 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_138 — Force Lightning

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Choose a unit. It loses all abilities for this phase. Then, if you control a FORCE unit, pay any number of resources and deal 2 damage to the chosen unit for each resource paid this way.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_146 — Zeb Orrelios

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Rebel, Spectre

**Rules text:**

> When this unit completes an attack: If the defender was defeated, you may deal 4 damage to a ground unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_153 — Saw Gerrera

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Rebel

**Rules text:**

> As an additional cost for each opponent to play an event, they must deal 2 damage to their base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_158 — Jedha Agitator

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Rebel

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> On Attack: If you control a leader unit, deal 2 damage to a ground unit or a base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_167 — Force Throw

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Choose a player. That player discards a card from their hand. Then, if you control a FORCE unit, you may deal damage to a unit equal to the cost of the discarded card.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_170 — Power Failure

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Defeat any number of upgrades on a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

