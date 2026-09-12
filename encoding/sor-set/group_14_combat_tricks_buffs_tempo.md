# sor-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_114 | Escort Skiff | Unit | 4 | 4/4 | Ambush |
| SOR_116 | Steadfast Battalion | Unit | 5 | 5/5 | Overwhelm |
| SOR_118 | 97th Legion | Unit | 7 | 0/0 |  |
| SOR_119 | Reinforcement Walker | Unit | 8 | 6/9 |  |
| SOR_148 | Guerilla Attack Pod | Unit | 6 | 4/6 | Grit |
| SOR_149 | Mace Windu | Unit | 7 | 5/7 | Ambush |
| SOR_154 | Rallying Cry | Event | 3 |  | Raid |

## Per-card analysis & acceptance criteria

### SOR_114 — Escort Skiff

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Speeder, Underworld, Vehicle

**Rules text:**

> While you control another [Command] unit, this unit gains Ambush. (After you play this unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_116 — Steadfast Battalion

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Trooper

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> 
> On Attack: If you control a leader unit, give a friendly unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_118 — 97th Legion

**Type/Stats:** Unit, cost 7, 0/0  |  Traits: Imperial, Trooper

**Rules text:**

> This unit gets +1/+1 for each resource you control.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff', 'ramp'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_119 — Reinforcement Walker

**Type/Stats:** Unit, cost 8, 6/9  |  Traits: Vehicle, Walker

**Rules text:**

> When Played/On Attack: Look at the top card of your deck. Either draw that card or discard it and heal 3 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'draw', 'discard', 'search'].

**Existing primitives that should suffice:** Heal, DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_148 — Guerilla Attack Pod

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel, Vehicle, Walker

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)  
> 
> When Played: If a base has 15 or more damage on it, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_149 — Mace Windu

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Ambush
> 
> When this unit attacks and defeats a unit: Ready him.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_154 — Rallying Cry

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Each friendly unit gains Raid 2 this phase. (They get +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

