# hmw-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_115 | Leia Organa | Unit | 1 | 2/3 |  |
| HMW_117 | Chewbacca | Unit | 3 | 0/5 | Overwhelm, Raid |
| HMW_118 | Ryyk Blademaster | Unit | 4 | 5/4 | Ambush, Overwhelm |
| HMW_119 | Saw Gerrera | Unit | 4 | 3/6 |  |
| HMW_121 | Hijacked AT-ST | Unit | 5 | 7/7 | Overwhelm |
| HMW_123 | King Grakchawwaa | Unit | 6 | 6/6 |  |
| HMW_124 | Luminara Unduli | Unit | 7 | 7/7 |  |

## Per-card analysis & acceptance criteria

### HMW_115 — Leia Organa

**Type/Stats:** Unit, cost 1, 2/3  |  Traits: Official, Rebel

**Rules text:**

> When you play another unit that costs 3 or less: Heal 1 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_117 — Chewbacca

**Type/Stats:** Unit, cost 3, 0/5  |  Traits: Wookiee

**Rules text:**

> This unit gains Raid 1 for each exhausted resource you control.
> While each resource you control is exhausted, this unit gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant', 'ramp'].

**Existing primitives that should suffice:** GrantKeyword, grant-keyword-to-resources.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_118 — Ryyk Blademaster

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Wookiee

**Rules text:**

> While you control 6 or more resources, this unit gains Ambush and Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, grant-keyword-to-resources.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_119 — Saw Gerrera

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Rebel

**Rules text:**

> When an opponent plays an event: Resource the top card of your deck.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_121 — Hijacked AT-ST

**Type/Stats:** Unit, cost 5, 7/7  |  Traits: Rebel, Vehicle, Walker

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: This unit doesn't ready during the next regroup phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_123 — King Grakchawwaa

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Official, Wookiee

**Rules text:**

> When Played: For each other friendly Wookiee unit, resource the top card of your deck. Ready each card resourced this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_124 — Luminara Unduli

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> When you play a unit (including this one): You may attack with a unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

