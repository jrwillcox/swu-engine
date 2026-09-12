# lof-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_152 | Focus Determines Reality | Event | 2 |  | Raid, Saboteur |
| LOF_153 | Paz Vizsla | Unit | 5 | 3/6 |  |
| LOF_166 | Blockade Runner | Unit | 5 | 4/4 | Saboteur |
| LOF_169 | Invasion Control Ship | Unit | 7 | 5/9 | Raid |
| LOF_173 | Unleash Rage | Event | 1 |  |  |
| LOF_174 | Ataru Onslaught | Event | 2 |  |  |
| LOF_178 | Adept of Anger | Unit | 1 | 1/3 |  |

## Per-card analysis & acceptance criteria

### LOF_152 — Focus Determines Reality

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Each friendly Force unit gains Raid 1 and Saboteur for this phase.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_153 — Paz Vizsla

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Mandalorian

**Rules text:**

> This unit gets +2/+0 for each damage on him.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_166 — Blockade Runner

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When this unit deals combat damage to a base: You may give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_169 — Invasion Control Ship

**Type/Stats:** Unit, cost 7, 5/9  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> Friendly Droid units gain Raid 2.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_173 — Unleash Rage

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Use the Force (lose your Force token). If you do, give a friendly unit +3/+0 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_174 — Ataru Onslaught

**Type/Stats:** Event, cost 2  |  Traits: Learned

**Rules text:**

> Ready a Force unit with 4 or less power.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_178 — Adept of Anger

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Force, Fringe

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Exhaust a unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** force-token, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

