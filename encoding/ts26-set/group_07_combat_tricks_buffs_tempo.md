# ts26-set:07 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_10 | Dooku's Palace | Base |  | None/27 |  |
| TS26_13 | Darth Sidious | Unit | 6 | 4/6 | Hidden |
| TS26_16 | King Katuunko | Unit | 2 | 2/4 | Restore |
| TS26_18 | Jendirian Valley | Unit | 4 | 1/5 | Restore |
| TS26_20 | 501st Veteran | Unit | 2 | 0/4 | Grit, Raid, Sentinel |
| TS26_22 | The Darksaber | Upgrade | 4 |  | Sentinel |
| TS26_28 | Prime Minister Almec | Unit | 4 | 2/4 | Saboteur |

## Per-card analysis & acceptance criteria

### TS26_10 — Dooku's Palace

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a unit from your hand. It costs 1 resource less for each friendly leader unit.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_13 — Darth Sidious

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Force, Separatist, Sith

**Rules text:**

> Hidden
> Each other friendly Separatist unit gets +1/+0.
> When a non-token unit is defeated: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_16 — King Katuunko

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Official

**Rules text:**

> When Played: All units (including enemy units) gain Restore 1 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_18 — Jendirian Valley

**Type/Stats:** Unit, cost 4, 1/5  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> Restore 1
> When Played: Search the top 8 cards of your deck for a card and resource it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_20 — 501st Veteran

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Grit
> Raid 1
> While this unit is undamaged it gains Sentinel.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_22 — The Darksaber

**Type/Stats:** Upgrade, cost 4  |  Traits: Item, Mandalorian, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains Sentinel.
> When Played: If there are 4 or more different keywords among friendly units, ready attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_28 — Prime Minister Almec

**Type/Stats:** Unit, cost 4, 2/4  |  Traits: Mandalorian, Official

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: Give a friendly unit +2/+2 for this phase. Exhaust each enemy unit in its arena with less power than it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

