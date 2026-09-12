# general-grievous:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `general-grievous:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_15 | General Grievous | Leader | 6 | 4/8 | Sentinel |
| TWI_82 | MagnaGuard Wing Leader | Unit | 3 | 3/4 |  |
| TWI_104 | Obedient Vanguard | Unit | 1 | 1/1 | Raid |
| TWI_124 | Tactical Advantage | Event | 1 |  |  |
| TWI_179 | Soulless One | Unit | 1 | 1/2 |  |
| TWI_180 | Separatist Commando | Unit | 2 | 2/3 | Raid |
| TWI_184 | Tactical Droid Commander | Unit | 5 | 4/4 | Exploit |

## Per-card analysis & acceptance criteria

### TWI_15 — General Grievous

**Type/Stats:** Leader, cost 6, 4/8  |  Traits: Official, Separatist

**Rules text:**

> Action [Exhaust]: Give a Droid unit Sentinel for this phase. (Units in its arena can't attack your non-Sentinel units or your base.)
> On Attack: You may give a Droid unit +1/+0 and Sentinel for this phase.
> Epic Action: If you control 6 or more resources, deploy this leader. (Flip him, ready him, and move him to the ground arena.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_82 — MagnaGuard Wing Leader

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> Action: Attack with a Droid unit. Then, attack with another Droid unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `activated`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_104 — Obedient Vanguard

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Defeated: You may give a Trooper unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_124 — Tactical Advantage

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Give a unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_179 — Soulless One

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> On Attack: You may exhaust a friendly Droid unit or General Grievous (leader or unit). If you do, this unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_180 — Separatist Commando

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Droid, Separatist, Trooper

**Rules text:**

> While you control another Separatist unit, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_184 — Tactical Droid Commander

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Droid, Separatist

**Rules text:**

> Exploit 2
> When you play another Separatist unit: You may exhaust a unit that costs the same as or less than the played unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

