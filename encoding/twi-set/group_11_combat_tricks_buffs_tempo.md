# twi-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_1 | Nala Se | Leader | 4 | 1/7 |  |
| TWI_6 | Wat Tambor | Leader | 5 | 3/6 |  |
| TWI_7 | Captain Rex | Leader | 5 | 2/6 |  |
| TWI_9 | Maul | Leader | 6 | 6/6 | Overwhelm |
| TWI_12 | Anakin Skywalker | Leader | 6 | 4/7 |  |
| TWI_14 | Asajj Ventress | Leader | 4 | 3/4 |  |
| TWI_16 | Jango Fett | Leader | 5 | 3/7 |  |

## Per-card analysis & acceptance criteria

### TWI_1 — Nala Se

**Type/Stats:** Leader, cost 4, 1/7  |  Traits: Kaminoan

**Rules text:**

> Ignore the aspect penalty on Clone units you play.
> Ignore the aspect penalty on Clone units you play.
> Each friendly Clone unit gains: “When Defeated: Heal 2 damage from your base.”
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_6 — Wat Tambor

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Official, Separatist

**Rules text:**

> Action [Exhaust]: If a friendly unit was defeated this phase, give a unit +2/+2 for this phase.
> On Attack: If a friendly unit was defeated this phase, you may give another unit +2/+2 for this phase.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_7 — Captain Rex

**Type/Stats:** Leader, cost 5, 2/6  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Action [2 resources, Exhaust]: If a friendly unit attacked this phase, create a Clone Trooper token.
> When Deployed: Create a Clone Trooper token.
> Each other friendly Trooper unit gets +0/+1.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_9 — Maul

**Type/Stats:** Leader, cost 6, 6/6  |  Traits: Force, Underworld

**Rules text:**

> Action [Exhaust]: Attack with a unit. It gains Overwhelm for this attack. (When attacking an enemy unit, deal excess damage to the opponent's base.)
> Overwhelm
> Each other friendly unit gains Overwhelm.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_12 — Anakin Skywalker

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust, deal 2 damage to your base]: Attack with a unit. If it's attacking a unit, it gets +2/+0 for this attack.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> This unit gets +1/+0 for every 5 damage on your base.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_14 — Asajj Ventress

**Type/Stats:** Leader, cost 4, 3/4  |  Traits: Force, Separatist, Sith

**Rules text:**

> Action [Exhaust]: Attack with a unit. If you played an event this phase, it gets +1/+0 for this attack.
> On Attack: If you played an event this phase, this unit gets +1/+0 for this attack and deals combat damage before the defender. (If the defender is defeated, it deals no combat damage.)
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_16 — Jango Fett

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When a friendly unit deals damage to an enemy unit: You may exhaust this leader. If you do, exhaust that enemy unit.
> When a friendly unit deals damage to an enemy unit: You may exhaust that unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

