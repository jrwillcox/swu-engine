# twi-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_51 | For The Republic | Upgrade | 3 |  | Coordinate, Restore |
| TWI_54 | Duchess's Champion | Unit | 4 | 1/8 | Sentinel |
| TWI_56 | Compassionate Senator | Unit | 1 | 0/4 |  |
| TWI_58 | Padawan Starfighter | Unit | 2 | 1/3 |  |
| TWI_62 | Daughter of Dathomir | Unit | 4 | 3/5 | Restore |
| TWI_67 | The Zillo Beast | Unit | 9 | 10/10 |  |
| TWI_70 | Perilous Position | Upgrade | 3 |  |  |

## Per-card analysis & acceptance criteria

### TWI_51 — For The Republic

**Type/Stats:** Upgrade, cost 3  |  Traits: Republic

**Rules text:**

> If you control 3 or more Republic units, this upgrade costs 2 resources less to play.
> Attached unit gains: “Coordinate — Restore 2.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_54 — Duchess's Champion

**Type/Stats:** Unit, cost 4, 1/8  |  Traits: Mandalorian

**Rules text:**

> While an opponent controls 3 or more units, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_56 — Compassionate Senator

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Official, Republic

**Rules text:**

> Action [2 resources, Exhaust]: Heal 2 damage from a unit or base.

**Mechanical analysis:** trigger archetype `activated`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_58 — Padawan Starfighter

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> While you control a Force unit or a Force upgrade, this unit gets +1/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_62 — Daughter of Dathomir

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Night

**Rules text:**

> While this unit is undamaged, it gains Restore 2. (When this unit attacks, heal 2 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_67 — The Zillo Beast

**Type/Stats:** Unit, cost 9, 10/10  |  Traits: Creature

**Rules text:**

> When Played: Give each enemy ground unit –5/–0 for this phase.
> When the regroup phase starts: Heal 5 damage from this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_70 — Perilous Position

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> When Played: Exhaust attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

