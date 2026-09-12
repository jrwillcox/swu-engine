# twi-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_19 | Pau City | Base |  | None/26 |  |
| TWI_28 | Petranaki Arena | Base |  | None/26 |  |
| TWI_33 | Calculating MagnaGuard | Unit | 3 | 3/4 | Sentinel |
| TWI_42 | Barriss Offee | Unit | 1 | 1/1 |  |
| TWI_43 | Outspoken Representative | Unit | 2 | 0/3 | Sentinel |
| TWI_45 | 41st Elite Corps | Unit | 3 | 3/3 | Coordinate |
| TWI_50 | Luminara Unduli | Unit | 7 | 4/9 | Coordinate, Grit |

## Per-card analysis & acceptance criteria

### TWI_19 — Pau City

**Type/Stats:** Base

**Rules text:**

> Each leader unit you control gets +0/+1.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_28 — Petranaki Arena

**Type/Stats:** Base

**Rules text:**

> Each leader unit you control gets +1/+0.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_33 — Calculating MagnaGuard

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Droid, Separatist

**Rules text:**

> When Played/When a friendly unit is defeated: This unit gains Sentinel for this phase. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_42 — Barriss Offee

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Force, Jedi, Republic

**Rules text:**

> Each friendly unit that was healed this phase gets +1/+0.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_43 — Outspoken Representative

**Type/Stats:** Unit, cost 2, 0/3  |  Traits: Official, Republic

**Rules text:**

> While you control another Republic unit, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)
> When Defeated: Create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_45 — 41st Elite Corps

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — This unit gets +0/+3. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_50 — Luminara Unduli

**Type/Stats:** Unit, cost 7, 4/9  |  Traits: Force, Jedi, Republic

**Rules text:**

> Coordinate — Grit (Gain this keyword while you control 3 or more units. This unit gets +1/+0 for each damage on her.)
> When Played: Choose a base. Heal 1 damage from it for each unit you control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

