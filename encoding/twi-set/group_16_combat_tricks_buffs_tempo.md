# twi-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_139 | Corner the Prey | Event | 1 |  |  |
| TWI_143 | Jyn Erso | Unit | 2 | 3/2 | Saboteur |
| TWI_153 | Bold Resistance | Event | 3 |  |  |
| TWI_163 | Relentless Rocket Droid | Unit | 4 | 3/5 |  |
| TWI_166 | Aurra Sing | Unit | 7 | 7/6 | Overwhelm |
| TWI_169 | Clone Cohort | Upgrade | 2 |  | Raid |
| TWI_172 | Grim Resolve | Event | 2 |  | Grit |

## Per-card analysis & acceptance criteria

### TWI_139 — Corner the Prey

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gets +1/+0 for this attack for each damage on the defender at the start of this attack.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_143 — Jyn Erso

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Rebel

**Rules text:**

> While an enemy unit has been defeated this phase, this unit gets +1/+0 and gains Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_153 — Bold Resistance

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Choose up to 3 units that share the same Trait. Each of those units gets +2/+0 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_163 — Relentless Rocket Droid

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> While you control another Trooper unit, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_166 — Aurra Sing

**Type/Stats:** Unit, cost 7, 7/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When an enemy ground unit attacks your base: Ready this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_169 — Clone Cohort

**Type/Stats:** Upgrade, cost 2  |  Traits: Supply

**Rules text:**

> Attached unit gains Raid 2 and: “When Defeated: Create a Clone Trooper token.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_172 — Grim Resolve

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a non-leader unit. It gains Grit for this attack. (It gets +1/+0 for each damage on it.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

