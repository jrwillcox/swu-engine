# twi-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_71 | Unshakeable Will | Upgrade | 4 |  | Sentinel |
| TWI_73 | Grievous Reassembly | Event | 2 |  |  |
| TWI_74 | Guarding the Way | Event | 2 |  | Sentinel |
| TWI_81 | Droid Commando | Unit | 3 | 4/3 | Ambush |
| TWI_85 | Kalani | Unit | 6 | 5/7 |  |
| TWI_98 | Republic Defense Carrier | Unit | 11 | 6/7 | Sentinel |
| TWI_105 | Steadfast Senator | Unit | 1 | 0/4 |  |

## Per-card analysis & acceptance criteria

### TWI_71 — Unshakeable Will

**Type/Stats:** Upgrade, cost 4  |  Traits: Innate

**Rules text:**

> Attached unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_73 — Grievous Reassembly

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Heal 3 damage from a unit. Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_74 — Guarding the Way

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Give a unit Sentinel for this phase. (Units in its arena can't attack your non-Sentinel units or your base.)
> If you have the initiative, also give that unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_81 — Droid Commando

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> While you control another Separatist unit, this unit gains Ambush. (When you play this unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_85 — Kalani

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Droid, Separatist

**Rules text:**

> On Attack: You may choose another unit. If you have the initiative, you may choose up to 2 other units instead. Give each chosen unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_98 — Republic Defense Carrier

**Type/Stats:** Unit, cost 11, 6/7  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> This unit costs 1 resource less to play for each unit controlled by the opponent who controls the most units.
> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_105 — Steadfast Senator

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Official, Republic

**Rules text:**

> Action [2 resources, Exhaust]: Attack with a unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

