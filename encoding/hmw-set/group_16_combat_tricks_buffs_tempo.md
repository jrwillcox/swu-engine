# hmw-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_127 | Chewbacca's Bowcaster | Upgrade | 3 |  |  |
| HMW_129 | Child of Dathomir | Unit | 1 | 1/2 |  |
| HMW_131 | Soaring Can-Cell | Unit | 2 | 1/4 | Ambush, Raid |
| HMW_133 | Wroshyr Rebel | Unit | 2 | 0/4 |  |
| HMW_136 | Lifetree Caravan | Unit | 3 | 2/1 |  |
| HMW_137 | V-19 Skirmisher | Unit | 3 | 3/3 | Sentinel |
| HMW_138 | Commander Gree | Unit | 4 | 3/6 | Raid |

## Per-card analysis & acceptance criteria

### HMW_127 — Chewbacca's Bowcaster

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: If attached unit is Chewbacca, resource the top card of your deck. (It enters play exhausted.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_129 — Child of Dathomir

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Night

**Rules text:**

> While you control 3 or more units (including this one), this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_131 — Soaring Can-Cell

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Creature

**Rules text:**

> Raid 1
> While you control a Kashyyyk base, this unit gains Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_133 — Wroshyr Rebel

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Rebel, Wookiee

**Rules text:**

> This unit gets +1/+0 for every 2 resources you control.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_136 — Lifetree Caravan

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Ewok

**Rules text:**

> When Played: If you control 3 or more units (including this one), you may resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_137 — V-19 Skirmisher

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> While you control 3 or more units, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_138 — Commander Gree

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Clone, Republic, Trooper

**Rules text:**

> While there are 3 or more Command aspect icons among friendly units (including this one) and upgrades, this unit gains Raid 4.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

