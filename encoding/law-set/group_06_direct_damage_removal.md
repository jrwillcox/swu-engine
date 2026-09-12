# law-set:06 — Direct damage & removal

- **Group id (paste this):** `law-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_198 | Dogged Pursuers | Unit | 5 | 5/5 |  |
| LAW_201 | Thermal Detonator | Upgrade | 3 |  |  |
| LAW_205 | Flash the Vents | Event | 1 |  | Overwhelm |
| LAW_206 | That's a Rock | Event | 1 |  |  |
| LAW_207 | Attack From All Sides | Event | 3 |  |  |
| LAW_208 | Collateral Damage | Event | 3 |  |  |
| LAW_213 | Cutthroat Podracer | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### LAW_198 — Dogged Pursuers

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: You may pay 1 resource. If you do, deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_201 — Thermal Detonator

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “When Defeated: If this unit was ready, deal 2 damage to each enemy ground unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_205 — Flash the Vents

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Attack with a unit. It gets +2/+0 and gains Overwhelm for this attack. After completing this attack, if that unit damaged a base, defeat that unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['defeat', 'stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_206 — That's a Rock

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Deal 1 damage to a unit.
> When this event is discarded from your hand or deck: You may deal 1 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_207 — Attack From All Sides

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Deal 3 damage to a unit. If there are 4 or more different aspects among friendly units, you may deal 5 damage to that unit instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_208 — Collateral Damage

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> Deal 2 damage to a unit. Then, deal 2 damage to a base or another unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_213 — Cutthroat Podracer

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Speeder, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to an exhausted ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

