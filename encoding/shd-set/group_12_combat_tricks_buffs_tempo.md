# shd-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_4 | Rey | Leader | 6 | 2/6 | Restore |
| SHD_5 | Hondo Ohnaka | Leader | 6 | 3/7 | Raid, Smuggle |
| SHD_6 | Jabba the Hutt | Leader | 7 | 2/12 | Bounty |
| SHD_8 | Boba Fett | Leader | 6 | 4/7 |  |
| SHD_11 | Kylo Ren | Leader | 4 | 5/4 |  |
| SHD_32 | Lom Pyke | Unit | 4 | 4/6 | Smuggle |
| SHD_34 | Supercommando Squad | Unit | 5 | 4/4 | Sentinel, Shielded |

## Per-card analysis & acceptance criteria

### SHD_4 — Rey

**Type/Stats:** Leader, cost 6, 2/6  |  Traits: Force, Fringe

**Rules text:**

> Action [1 resource, Exhaust]: Give an Experience token to a unit with 2 or less power.
> Restore 3 (When this unit attacks, heal 3 damage from your base.)
> On Attack: You may give an Experience token to a unit with 2 or less power.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_5 — Hondo Ohnaka

**Type/Stats:** Leader, cost 6, 3/7  |  Traits: Underworld

**Rules text:**

> When you play a card using Smuggle: You may exhaust this leader. If you do, give an Experience token to a unit.
> Raid 1 (This unit gets +1/+0 while attacking.)
> When you play a card using Smuggle: You may give an Experience token to a unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_6 — Jabba the Hutt

**Type/Stats:** Leader, cost 7, 2/12  |  Traits: Hutt, Underworld

**Rules text:**

> Action [Exhaust]: Choose a unit. For this phase, it gains: “Bounty — The next unit you play this phase costs 1 resource less.”
> When Deployed: Another friendly unit captures an enemy non-leader unit.
> Action [Exhaust]: Choose a unit. For this phase, it gains: “Bounty — The next unit you play this phase costs 2 resources less.”
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_8 — Boba Fett

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Underworld

**Rules text:**

> When you play a unit that has 1 or more keywords: You may exhaust this leader. If you do, give a friendly unit +1/+0 for this phase.
> Each other friendly unit that has 1 or more keywords gets +1/+0.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_11 — Kylo Ren

**Type/Stats:** Leader, cost 4, 5/4  |  Traits: First Order, Force

**Rules text:**

> Action [Exhaust, discard a card from your hand]: Give a unit +2/+0 for this phase.
> This unit gets –1/–0 for each card in your hand.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_32 — Lom Pyke

**Type/Stats:** Unit, cost 4, 4/6  |  Traits: Underworld

**Rules text:**

> On Attack: You may give a Shield token to an enemy unit. If you do, give a Shield token to a friendly unit.
> Smuggle [5 resources Vigilance Villainy]

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_34 — Supercommando Squad

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Imperial, Mandalorian, Trooper

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> While this unit is upgraded, it gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

