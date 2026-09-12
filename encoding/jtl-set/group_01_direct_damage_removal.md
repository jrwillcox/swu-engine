# jtl-set:01 — Direct damage & removal

- **Group id (paste this):** `jtl-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_1 | Asajj Ventress | Leader | 6 | 4/6 | Grit |
| JTL_10 | Captain Phasma | Leader | 5 | 4/6 |  |
| JTL_12 | Luke Skywalker | Leader | 6 | 5/6 |  |
| JTL_37 | Banshee | Unit | 5 | 4/5 |  |
| JTL_40 | Fleet Interdictor | Unit | 7 | 6/6 | Sentinel |
| JTL_43 | No Glory, Only Results | Event | 5 |  |  |
| JTL_46 | Paige Tico | Unit | 2 | 3/2 | Piloting |

## Per-card analysis & acceptance criteria

### JTL_1 — Asajj Ventress

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Bounty Hunter, Force, Night, Pilot

**Rules text:**

> Action [Exhaust]: Deal 1 damage to a friendly unit. If you do, deal 1 damage to an enemy unit in the same arena.
> Grit
> Attached unit is a leader unit. It gains Grit and: “On Attack: You may deal 1 damage to a friendly unit. If you do, deal 1 damage to an enemy unit in the same arena.”
> 
> Epic Action: If you control 6 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_10 — Captain Phasma

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: First Order, Trooper

**Rules text:**

> Action [Exhaust]: If you played a First Order card this phase, deal 1 damage to a base.
> On Attack: If you played another First Order card this phase, you may deal 1 damage to a unit. If you do, deal 1 damage to a base.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_12 — Luke Skywalker

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Pilot, Rebel

**Rules text:**

> Action [Exhaust]: If you attacked with a Fighter unit this phase, deal 1 damage to a unit.
> 
> This upgrade can't be defeated by enemy card abilities.
> Attached unit is a leader unit. If it's a Fighter, it gains: “On Attack: You may deal 3 damage to a unit.”
> 
> Epic Action: If you control 6 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_37 — Banshee

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> On Attack: You may deal damage to a unit equal to the amount of damage on this unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_40 — Fleet Interdictor

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> When Defeated: You may defeat a space unit that costs 3 or less.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_43 — No Glory, Only Results

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Take control of a non-leader unit, then defeat it.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_46 — Paige Tico

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Pilot, Resistance

**Rules text:**

> Piloting [2 resources Vigilance Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains: “On Attack: Give an Experience token to this unit, then deal 1 damage to it.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

