# lof-set:10 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_52 | Jedi Trials | Upgrade | 1 |  |  |
| LOF_53 | Heirloom Lightsaber | Upgrade | 2 |  | Restore |
| LOF_54 | Calm in the Storm | Event | 2 |  |  |
| LOF_55 | Dume | Unit | 4 | 2/7 |  |
| LOF_56 | Size Matters Not | Upgrade | 3 |  |  |
| LOF_58 | Guardian of the Whills | Unit | 2 | 2/2 |  |
| LOF_60 | Padawan Starfighter | Unit | 2 | 1/3 |  |

## Per-card analysis & acceptance criteria

### LOF_52 — Jedi Trials

**Type/Stats:** Upgrade, cost 1  |  Traits: Jedi, Learned

**Rules text:**

> Attach to a Force unit.
> Attached unit gains: “On Attack: Give an Experience token to this unit.”
> While attached unit has 4 or more upgrades on it, it gains the Jedi trait.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_53 — Heirloom Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> If attached unit is a Force unit, it gains Restore 1. (When this unit attacks, heal 1 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_54 — Calm in the Storm

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Exhaust a friendly unit. If you do, give a Shield token and 2 Experience tokens to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_55 — Dume

**Type/Stats:** Unit, cost 4, 2/7  |  Traits: Creature, Force

**Rules text:**

> When the regroup phase starts: Give an Experience token to each other friendly non-Vehicle unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_56 — Size Matters Not

**Type/Stats:** Upgrade, cost 3  |  Traits: Force

**Rules text:**

> If you control a Force unit, this upgrade costs 1 resource less to play.
> Attached unit's printed power is considered to be 5 and its printed HP is considered to be 5.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_58 — Guardian of the Whills

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Fringe

**Rules text:**

> The first upgrade you play on this unit each round costs 1 resource less.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_60 — Padawan Starfighter

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> While you control a Force unit or upgrade, this unit gets +1/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

