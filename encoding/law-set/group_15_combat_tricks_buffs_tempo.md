# law-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_109 | Tantive IV | Unit | 7 | 5/8 | Restore |
| LAW_110 | Phoenix Squadron Fighters | Unit | 8 | 6/6 |  |
| LAW_112 | Boonta Eve Flagbearer | Unit | 1 | 1/3 |  |
| LAW_113 | Shield Drive Outfitter | Unit | 1 | 1/3 |  |
| LAW_127 | Kill Switch | Upgrade | 2 |  |  |
| LAW_128 | Veiled Strength | Upgrade | 3 |  | Grit |
| LAW_129 | Mastery | Upgrade | 4 |  |  |

## Per-card analysis & acceptance criteria

### LAW_109 — Tantive IV

**Type/Stats:** Unit, cost 7, 5/8  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> When Played: If a friendly unit was defeated this phase, heal 4 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_110 — Phoenix Squadron Fighters

**Type/Stats:** Unit, cost 8, 6/6  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> This unit costs 1 resource less to play for each friendly damaged unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_112 — Boonta Eve Flagbearer

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Fringe

**Rules text:**

> When a friendly unit attacks: If no other units have attacked this phase (including enemy units), heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_113 — Shield Drive Outfitter

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Underworld

**Rules text:**

> When Played: You may pay 1 resource. If you do, give a Shield token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_127 — Kill Switch

**Type/Stats:** Upgrade, cost 2  |  Traits: Condition

**Rules text:**

> When Played: Exhaust attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_128 — Veiled Strength

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> Attach to a non-leader unit.
> Attached unit gains Grit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_129 — Mastery

**Type/Stats:** Upgrade, cost 4  |  Traits: Learned

**Rules text:**

> This upgrade costs 1 resource less to play on a <uq> unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

