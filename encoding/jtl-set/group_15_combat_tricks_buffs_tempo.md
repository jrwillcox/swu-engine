# jtl-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_88 | Captain Phasma | Unit | 5 | 5/6 |  |
| JTL_92 | Scramble Fighters | Event | 7 |  |  |
| JTL_94 | Luke Skywalker | Unit | 2 | 3/2 | Piloting |
| JTL_101 | Red Leader | Unit | 4 | 3/4 |  |
| JTL_106 | Unity of Purpose | Event | 6 |  |  |
| JTL_107 | Bunker Defender | Unit | 1 | 2/1 | Sentinel |
| JTL_109 | Jarek Yeager | Unit | 2 | 2/3 | Piloting, Sentinel |

## Per-card analysis & acceptance criteria

### JTL_88 — Captain Phasma

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: First Order, Trooper

**Rules text:**

> When Played/On Attack: You may give another First Order unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_92 — Scramble Fighters

**Type/Stats:** Event, cost 7  |  Traits: Supply

**Rules text:**

> Create 8 TIE Fighter tokens and ready them. They can't attack bases for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_94 — Luke Skywalker

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Force, Pilot, Rebel

**Rules text:**

> Piloting [3 resources Command Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> If this upgrade would be defeated, you may instead move him to the ground arena as a unit and exhaust him.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_101 — Red Leader

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> This unit costs 1 resource less to play for each friendly Pilot unit and upgrade.
> When a Pilot upgrade attaches to this unit: Create an X-Wing token.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_106 — Unity of Purpose

**Type/Stats:** Event, cost 6  |  Traits: Plan

**Rules text:**

> For each friendly unit with a different name, give each unit you control +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_107 — Bunker Defender

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Imperial, Trooper

**Rules text:**

> While you control a Vehicle unit, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_109 — Jarek Yeager

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Pilot, Resistance

**Rules text:**

> Piloting [2 resources Command] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> While you control a ground unit and a space unit, attached unit gains Sentinel.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

