# hmw-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_66 | Carrion Spike | Unit | 5 | 3/5 | Restore, Shielded |
| HMW_72 | Grand Army Marine | Unit | 2 | 2/2 |  |
| HMW_73 | Peppi Bow | Unit | 2 | 2/3 | Restore |
| HMW_74 | Yord Fandar | Unit | 2 | 2/4 | Sentinel |
| HMW_80 | Fambaa Shield Team | Unit | 7 | 4/7 |  |
| HMW_83 | Batcher | Unit | 2 | 2/3 | Restore |
| HMW_84 | Gunga City Guard | Unit | 2 | 2/1 | Restore, Shielded |

## Per-card analysis & acceptance criteria

### HMW_66 — Carrion Spike

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Shielded
> For each upgrade on your base, this unit gets +1/+0 and gains Restore 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_72 — Grand Army Marine

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Gungan, Trooper

**Rules text:**

> When Played: Give a Shield token to a friendly Gungan unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_73 — Peppi Bow

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Gungan

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> While this unit is upgraded, she gets +1/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_74 — Yord Fandar

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Force, Jedi

**Rules text:**

> While a base has 15 or more damage on it, this unit gains Sentinel.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_80 — Fambaa Shield Team

**Type/Stats:** Unit, cost 7, 4/7  |  Traits: Creature, Gungan

**Rules text:**

> When Played: Give a Shield token to each friendly ground unit without a Shield token on it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_83 — Batcher

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Creature

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> This unit gets +1/+0 while defending.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_84 — Gunga City Guard

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Gungan

**Rules text:**

> Restore 1
> While you control another Gungan unit or a Naboo base, this unit gains Shielded.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

