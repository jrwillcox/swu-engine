# ts26-set:01 — Direct damage & removal

- **Group id (paste this):** `ts26-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_3 | Maul | Leader | 7 | 5/9 |  |
| TS26_11 | Executioner's Arena | Base |  | None/27 |  |
| TS26_12 | Sundari Palace | Base |  | None/27 |  |
| TS26_15 | C-3P0 | Unit | 2 | 2/5 |  |
| TS26_19 | Coleman Trebor | Unit | 1 | 2/2 | Hidden |
| TS26_23 | Assault Lander LAAT | Unit | 4 | 3/5 |  |
| TS26_24 | Sundari Gauntlet | Unit | 5 | 6/5 | Sentinel |

## Per-card analysis & acceptance criteria

### TS26_3 — Maul

**Type/Stats:** Leader, cost 7, 5/9  |  Traits: Force, Underworld

**Rules text:**

> Action [Exhaust]: Choose a unit. If it has more different keywords than it has Experience tokens on it, give an Experience token to it and deal 1 damage to it.
> When Deployed/On Attack: Choose a unit. If it has more different keywords than it has Experience tokens on it, give an Experience token to it and deal 1 damage to it.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_11 — Executioner's Arena

**Type/Stats:** Base

**Rules text:**

> Epic Action: For each friendly leader unit, you may deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_12 — Sundari Palace

**Type/Stats:** Base

**Rules text:**

> Epic Action: For each friendly leader unit, you may resource a card from your hand and ready it. If you do, defeat that many friendly resources at the start of the regroup phase.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['defeat', 'ready_exhaust', 'ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_15 — C-3P0

**Type/Stats:** Unit, cost 2, 2/5  |  Traits: Droid

**Rules text:**

> When Played: An opponent takes control of this unit.
> Action [Exhaust]: Deal damage equal to this unit's power to another ground unit. Only opponents may use this ability.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_19 — Coleman Trebor

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Force, Jedi, Republic

**Rules text:**

> Hidden (This unit can't be attacked if he was played this phase.)
> When Played: Deal 1 damage to each enemy base. Heal 1 damage from your base for each damage dealt this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_23 — Assault Lander LAAT

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: Create 2 Clone Trooper tokens.
> When the regroup phase starts: Deal 4 damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_24 — Sundari Gauntlet

**Type/Stats:** Unit, cost 5, 6/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> On Defense: Deal 1 damage to your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

