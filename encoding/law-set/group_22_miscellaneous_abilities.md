# law-set:22 — Miscellaneous abilities

- **Group id (paste this):** `law-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_155 | Getaway Freighter | Unit | 3 | 1/4 |  |
| LAW_156 | Hunter For Hire | Unit | 3 | 4/4 |  |
| LAW_161 | Partisan U-Wing | Unit | 5 | 3/5 |  |
| LAW_169 | Payroll Heist | Event | 4 |  |  |
| LAW_197 | Shifty Suspects | Unit | 4 | 4/5 |  |
| LAW_204 | Every Day, More Lies | Event | 1 |  |  |
| LAW_219 | Anakin's Podracer | Unit | 3 | 3/2 | Ambush |

## Per-card analysis & acceptance criteria

### LAW_155 — Getaway Freighter

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Transport, Vehicle

**Rules text:**

> On Attack: If you control a ground unit, create a Credit token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_156 — Hunter For Hire

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Action [defeat a friendly Credit token]: Take control of this unit. Any player may use this ability.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_161 — Partisan U-Wing

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Played: If a friendly unit was defeated this phase, create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_169 — Payroll Heist

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> For this phase, each friendly unit gains: “On Attack: Create a Credit token.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_197 — Shifty Suspects

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> On Attack: Bases can't be healed for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_204 — Every Day, More Lies

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> Each player discards a card from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_219 — Anakin's Podracer

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Speeder, Vehicle

**Rules text:**

> Ambush
> While attacking, if no other units have attacked this phase, this unit deals combat damage before the defending unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

