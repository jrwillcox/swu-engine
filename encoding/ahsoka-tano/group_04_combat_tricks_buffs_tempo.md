# ahsoka-tano:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ahsoka-tano:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_91 | Republic Tactical Officer | Unit | 2 | 1/4 |  |
| TWI_92 | Admiral Yularen | Unit | 3 | 2/5 | Restore |
| TWI_109 | 501st Liberator | Unit | 3 | 3/3 |  |
| TWI_123 | Outflank | Event | 1 |  |  |
| TWI_126 | Encouraging Leadership | Event | 3 |  |  |
| TWI_142 | Anakin's Interceptor | Unit | 2 | 2/3 |  |
| TWI_248 | Ahsoka's Padawan Lightsaber | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### TWI_91 — Republic Tactical Officer

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Clone, Republic

**Rules text:**

> When Played: You may attack with a Republic unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_92 — Admiral Yularen

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Official, Republic

**Rules text:**

> Restore 1
> Each other friendly Heroism unit gets +0/+1.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_109 — 501st Liberator

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When Played: If you control another Republic unit, you may heal 3 damage from a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_123 — Outflank

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with 2 units (one at a time).

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_126 — Encouraging Leadership

**Type/Stats:** Event, cost 3  |  Traits: Learned

**Rules text:**

> Give each friendly unit +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_142 — Anakin's Interceptor

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> While your base has 15 or more damage on it, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_248 — Ahsoka's Padawan Lightsaber

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: If attached unit is Ahsoka Tano, you may attack with a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

