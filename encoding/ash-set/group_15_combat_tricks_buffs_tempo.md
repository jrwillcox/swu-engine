# ash-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_65 | Home One | Unit | 8 | 7/10 | Sentinel |
| ASH_66 | Luke's Jedi Lightsaber | Upgrade | 3 |  | Sentinel |
| ASH_73 | Palace Chef Droid | Unit | 2 | 0/3 | Sentinel |
| ASH_75 | Pit Droid Team | Unit | 3 | 3/3 |  |
| ASH_78 | B-Wing Rearguard | Unit | 4 | 3/5 | Sentinel |
| ASH_79 | Koska Reeves | Unit | 4 | 4/4 | Sentinel |
| ASH_81 | Nebulon-C Frigate | Unit | 5 | 3/6 |  |

## Per-card analysis & acceptance criteria

### ASH_65 — Home One

**Type/Stats:** Unit, cost 8, 7/10  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> When Played: Heal all damage from each friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_66 — Luke's Jedi Lightsaber

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> If attached unit is Luke Skywalker, he gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_73 — Palace Chef Droid

**Type/Stats:** Unit, cost 2, 0/3  |  Traits: Droid, Underworld

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> This unit gets +2/+0 while defending.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_75 — Pit Droid Team

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Droid

**Rules text:**

> The first upgrade you play on another friendly unit each phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_78 — B-Wing Rearguard

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> While you control a ground unit, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_79 — Koska Reeves

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Mandalorian

**Rules text:**

> While you control a token unit, this unit gains Sentinel.
> When Played: If a friendly unit was defeated this phase, create a Mandalorian token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_81 — Nebulon-C Frigate

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Capital Ship, New Republic, Vehicle

**Rules text:**

> When Played: You may heal 3 damage from a unit or base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

