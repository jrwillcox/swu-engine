# shd-set:01 — Direct damage & removal

- **Group id (paste this):** `shd-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_2 | Qi'ra | Leader | 5 | 0/8 | Grit |
| SHD_3 | Finn | Leader | 5 | 4/6 |  |
| SHD_10 | Bossk | Leader | 5 | 4/6 | Bounty |
| SHD_12 | Bo-Katan Kryze | Leader | 6 | 4/7 |  |
| SHD_14 | Cad Bane | Leader | 6 | 2/8 | Raid |
| SHD_17 | Lando Calrissian | Leader | 4 | 2/5 | Smuggle |
| SHD_33 | Synara San | Unit | 4 | 3/6 | Bounty, Grit |

## Per-card analysis & acceptance criteria

### SHD_2 — Qi'ra

**Type/Stats:** Leader, cost 5, 0/8  |  Traits: Underworld

**Rules text:**

> Action [1 resource, Exhaust]: Deal 2 damage to a friendly unit. Then, give a Shield token to it.
> Grit (This unit gets +1/+0 for each damage on her.)
> When Deployed: Heal all damage from each unit. Then, deal damage to each unit equal to half its remaining HP, rounded down.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'heal', 'token'].

**Existing primitives that should suffice:** DealDamage, Heal, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_3 — Finn

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Fringe, Trooper

**Rules text:**

> Action [Exhaust]: Defeat a friendly upgrade on a unit. If you do, give a Shield token to that unit.
> On Attack: You may defeat a friendly upgrade on a unit. If you do, give a Shield token to that unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_10 — Bossk

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Action [Exhaust]: Deal 1 damage to a unit with a Bounty. You may give it +1/+0 for this phase.
> When you collect a bounty: You may collect that bounty again. Use this ability only once each round.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_12 — Bo-Katan Kryze

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Mandalorian

**Rules text:**

> Action [Exhaust]: If you attacked with a Mandalorian unit this phase, deal 1 damage to a unit.
> On Attack: You may deal 1 damage to a unit. If you attacked with another Mandalorian unit this phase, you may deal 1 damage to a unit. (The same unit or a different unit.)
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_14 — Cad Bane

**Type/Stats:** Leader, cost 6, 2/8  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When you play an Underworld card: You may exhaust this leader. If you do, an opponent chooses a unit they control. Deal 1 damage to it.
> Raid 2 (This unit gets +2/+0 while attacking.)
> When you play an Underworld card: You may choose an opponent. They choose a unit they control. Deal 2 damage to it. Use this ability only once each round.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_17 — Lando Calrissian

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Play a card using Smuggle. It costs 2 resources less. Defeat a resource you own and control.
> Action: Play a card using Smuggle. It costs 2 resources less. Defeat a resource you own and control. Use this ability only once each round.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['defeat', 'ramp'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, CostReduction, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_33 — Synara San

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Underworld

**Rules text:**

> Grit
> While this unit is exhausted, she gains, “Bounty — Deal 5 damage to a base.” (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

