# hmw-set:07 — Direct damage & removal

- **Group id (paste this):** `hmw-set:07`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_249 | Frenzied Tri-Fighters | Unit | 5 | 5/3 |  |
| HMW_252 | Villainous Ambition | Upgrade | 2 |  |  |
| HMW_253 | Forced Pacification | Event | 2 |  |  |
| HMW_263 | Wrecker | Unit | 6 | 6/6 |  |
| HMW_270 | Wild Space Wanderer | Unit | 3 | 3/2 |  |

## Per-card analysis & acceptance criteria

### HMW_249 — Frenzied Tri-Fighters

**Type/Stats:** Unit, cost 5, 5/3  |  Traits: Droid, Fighter, Separatist, Vehicle

**Rules text:**

> When Played: You may defeat an upgrade that costs 3 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_252 — Villainous Ambition

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: If attached unit is a Villainy unit, you may deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_253 — Forced Pacification

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Defeat any number of friendly units. For each friendly unit defeated this way, exhaust 2 enemy units.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_263 — Wrecker

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Clone

**Rules text:**

> When Played: Each player chooses a unit they control. Deal 3 damage to each chosen unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_270 — Wild Space Wanderer

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> When Played: You may defeat an upgrade on a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

