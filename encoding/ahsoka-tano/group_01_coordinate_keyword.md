# ahsoka-tano:01 — Coordinate keyword

- **Group id (paste this):** `ahsoka-tano:01`
- **Kind:** keyword
- **Cards:** 9

## Keyword group: **Coordinate**

Implement the **Coordinate** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Coordinate` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_11 | Ahsoka Tano | Leader | 5 | 3/6 | Coordinate |
| TWI_90 | Echo | Unit | 2 | 2/2 | Coordinate |
| TWI_106 | Coruscant Guard | Unit | 2 | 3/2 | Ambush, Coordinate |
| TWI_114 | Clone Commander Cody | Unit | 5 | 4/4 | Coordinate, Overwhelm |
| TWI_147 | Anakin Skywalker | Unit | 5 | 6/6 | Coordinate |
| TWI_158 | Clone Heavy Gunner | Unit | 2 | 1/3 | Coordinate |
| TWI_164 | Hevy | Unit | 4 | 4/4 | Coordinate, Raid |
| TWI_240 | 332nd Stalwart | Unit | 1 | 1/2 | Coordinate |
| TWI_243 | Republic Commando | Unit | 3 | 2/5 | Coordinate, Saboteur |

## Per-card analysis & acceptance criteria

### TWI_11 — Ahsoka Tano

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Coordinate — Action [Exhaust]: Attack with a unit. It gets +1/+0 for this attack. (Gain this ability while you control 3 or more units.)
> Coordinate — This unit gets +2/+0.
> Epic Action: If you control 5 or more resources, deploy this leader. (Flip her, ready her, and move her to the ground arena.)

**Residual text (needs separate ability after keyword):** Epic Action: If you control 5 or more resources, deploy this leader. (Flip her, ready her, and move her to the ground arena.)

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_90 — Echo

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — This unit gets +2/+2. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_106 — Coruscant Guard

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — Ambush (Gain this keyword while you control 3 or more units, including this one. When you play this unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_114 — Clone Commander Cody

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> Coordinate — Each other friendly unit gets +1/+1 and gains Overwhelm. (Gain this ability while you control 3 or more units.)

**Residual text (needs separate ability after keyword):** Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_147 — Anakin Skywalker

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Coordinate — On Attack: Draw a card. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_158 — Clone Heavy Gunner

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — This unit gets +2/+0. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_164 — Hevy

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — Raid 2 (Gain this keyword while you control 3 or more units. This unit gets +2/+0 while attacking.)
> When Defeated: Deal 1 damage to each enemy ground unit.

**Residual text (needs separate ability after keyword):** When Defeated: Deal 1 damage to each enemy ground unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_240 — 332nd Stalwart

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — This unit gets +1/+1. (Gain this ability while you control 3 or more units.)

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_243 — Republic Commando

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Coordinate — Saboteur (Gain this keyword while you control 3 or more units. When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

