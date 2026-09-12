# ash-set:20 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_184 | Follow Me | Event | 1 |  |  |
| ASH_188 | Galvanized Leap | Event | 4 |  |  |
| ASH_197 | Executor | Unit | 8 | 5/12 |  |
| ASH_198 | Nowhere to Hide | Upgrade | 2 |  | Sentinel |
| ASH_204 | Blade Three | Unit | 3 | 2/4 |  |
| ASH_205 | Inspiring Veteran | Unit | 3 | 3/3 |  |
| ASH_206 | Kelleran Beq | Unit | 4 | 3/5 | Ambush |

## Per-card analysis & acceptance criteria

### ASH_184 — Follow Me

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a unit. After completing the attack, give 3 Advantage tokens to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_188 — Galvanized Leap

**Type/Stats:** Event, cost 4  |  Traits: Force

**Rules text:**

> Ready a unit that was damaged this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_197 — Executor

**Type/Stats:** Unit, cost 8, 5/12  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> This unit gets +1/+0 for each upgrade on other friendly units.
> When Played: Give an Advantage token to each other friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_198 — Nowhere to Hide

**Type/Stats:** Upgrade, cost 2  |  Traits: Condition

**Rules text:**

> Attached unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_204 — Blade Three

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When your base is dealt damage: Give an Advantage token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_205 — Inspiring Veteran

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Resistance, Trooper

**Rules text:**

> When Played: Give an Advantage token to each of up to 3 exhausted units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_206 — Kelleran Beq

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Jedi

**Rules text:**

> Ambush
> This unit gets +1/+0 for each other unit (friendly and enemy) with 0 power.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

