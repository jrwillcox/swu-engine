# sor-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_156 | Benthic "Two Tubes" | Unit | 1 | 2/2 | Raid |
| SOR_159 | Partisan Insurgent | Unit | 2 | 1/4 | Raid |
| SOR_161 | Ardent Sympathizer | Unit | 3 | 3/3 |  |
| SOR_166 | Infiltrator's Skill | Upgrade | 1 |  | Saboteur |
| SOR_168 | Precision Fire | Event | 1 |  | Saboteur |
| SOR_169 | Keep Fighting | Event | 2 |  |  |
| SOR_178 | Cartel Spacer | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### SOR_156 — Benthic "Two Tubes"

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Rebel, Trooper

**Rules text:**

> On Attack: Another friendly [Aggression] unit gains Raid 2 for this phase. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_159 — Partisan Insurgent

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Rebel, Trooper

**Rules text:**

> While you control another [Aggression] unit, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_161 — Ardent Sympathizer

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Trooper

**Rules text:**

> While you have the initiative, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_166 — Infiltrator's Skill

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attached unit gains Saboteur. (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_168 — Precision Fire

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gains Saboteur for this attack. If it's a TROOPER, it also gets +2/+0 for this attack. (Ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_169 — Keep Fighting

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Ready a unit with 3 or less power.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_178 — Cartel Spacer

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: If you control another [Cunning] unit, exhaust an enemy unit that costs 4 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

