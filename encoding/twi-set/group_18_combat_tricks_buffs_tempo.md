# twi-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_203 | Chancellor Palpatine | Unit | 4 | 2/6 |  |
| TWI_204 | Impropriety Among Thieves | Event | 4 |  |  |
| TWI_210 | Lux Bonteri | Unit | 2 | 3/2 |  |
| TWI_211 | Sly Moore | Unit | 3 | 3/3 |  |
| TWI_224 | Breaking In | Event | 2 |  | Saboteur |
| TWI_249 | Heroes on Both Sides | Event | 2 |  | Saboteur |
| TWI_254 | Volunteer Soldier | Unit | 3 | 2/3 | Raid |

## Per-card analysis & acceptance criteria

### TWI_203 — Chancellor Palpatine

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Official, Republic

**Rules text:**

> Each token unit you create enters play ready.
> On Attack: If a unit left play this phase, create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_204 — Impropriety Among Thieves

**Type/Stats:** Event, cost 4  |  Traits: Trick

**Rules text:**

> Choose a ready non-leader unit controlled by each player. If you do, each player takes control of the chosen unit controlled by the player to their right. At the start of the regroup phase, each player takes control of each unit they own that was chosen for this ability.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_210 — Lux Bonteri

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Separatist

**Rules text:**

> When an opponent plays a card: If that opponent paid less than the card's cost to play it, ready or exhaust a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_211 — Sly Moore

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Official, Republic

**Rules text:**

> When Played: Take contol of an enemy token unit and ready it. At the start of the regroup phase, that token unit's owner takes control of it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_224 — Breaking In

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gets +2/+0 and gains Saboteur for this attack. (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_249 — Heroes on Both Sides

**Type/Stats:** Event, cost 2  |  Traits: Republic, Separatist

**Rules text:**

> Choose up to 1 Republic unit and up to 1 Separatist unit. Give each chosen unit +2/+2 and Saboteur for this phase. (When either of those units attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_254 — Volunteer Soldier

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Trooper

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> If you control a Trooper unit, this unit costs 1 resource less to play.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

