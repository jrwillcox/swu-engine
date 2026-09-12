# ts26-set:09 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_47 | Take Cover | Event | 3 |  |  |
| TS26_49 | Separatist Council | Unit | 4 | 2/6 |  |
| TS26_50 | General Grievous | Unit | 5 | 0/0 | Sentinel |
| TS26_51 | Lom Pyke | Unit | 5 | 5/5 |  |
| TS26_52 | Sith Traditions | Upgrade | 2 |  |  |
| TS26_53 | Coruscanti Spy | Unit | 1 | 0/2 | Raid |
| TS26_54 | Wartime Mercenaries | Unit | 4 | 5/5 |  |

## Per-card analysis & acceptance criteria

### TS26_47 — Take Cover

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> This event costs 1 resource less to play for each friendly leader unit.
> Heal up to 3 damage from a unit and give a Shield token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'token', 'ramp'].

**Existing primitives that should suffice:** Heal, GiveToken, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_49 — Separatist Council

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Official, Separatist

**Rules text:**

> When Played/On Attack: Choose one:
> Create a Battle Droid token.
> Give 2 Experience tokens to a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, push_modal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_50 — General Grievous

**Type/Stats:** Unit, cost 5, 0/0  |  Traits: Official, Separatist

**Rules text:**

> This unit gets +1/+1 for each resource you control.
> While this unit is undamaged, he gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'ramp'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_51 — Lom Pyke

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Underworld

**Rules text:**

> When Played: In player order, each opponent may heal 5 damage from their base. For each player that does, give 2 Experience tokens to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_52 — Sith Traditions

**Type/Stats:** Upgrade, cost 2  |  Traits: Learned, Sith

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack: Give an Experience token to this unit.” and “When Defeated: Give an Experience token to a friendly unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_53 — Coruscanti Spy

**Type/Stats:** Unit, cost 1, 0/2  |  Traits: Official

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> When Played: Heal 2 damage from each of any number of bases.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_54 — Wartime Mercenaries

**Type/Stats:** Unit, cost 4, 5/5  |  Traits: Trooper

**Rules text:**

> When Defeated: An opponent may give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

