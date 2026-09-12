# jtl-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_2 | Grand Admiral Thrawn | Leader | 6 | 4/7 |  |
| JTL_3 | Lando Calrissian | Leader | 7 | 5/7 | Sentinel |
| JTL_4 | Rose Tico | Leader | 5 | 4/6 |  |
| JTL_5 | Admiral Piett | Leader | 5 | 2/7 |  |
| JTL_7 | Admiral Holdo | Leader | 6 | 3/8 |  |
| JTL_8 | Wedge Antilles | Leader | 5 | 3/6 | Piloting |
| JTL_11 | Major Vonreg | Leader | 4 | 2/5 |  |

## Per-card analysis & acceptance criteria

### JTL_2 — Grand Admiral Thrawn

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Imperial, Official

**Rules text:**

> When you use a “When Defeated” ability: You may exhaust this leader. If you do, use that ability again.
> When you use a “When Defeated” ability: You may use that ability again. Use this ability only once each round.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_3 — Lando Calrissian

**Type/Stats:** Leader, cost 7, 5/7  |  Traits: Official, Pilot, Rebel

**Rules text:**

> Action [1 resource, Exhaust]: Play a unit from your hand (paying its cost). If you do and you control a ground unit and a space unit, give a Shield token to a unit.
> Sentinel
> Attached unit is a leader unit. 
> Attached unit gains Sentinel.
> When deployed as an upgrade: You may give a Shield token to a unit in a different arena.
> 
> Epic Action: If you control 7 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'keyword_grant'].

**Existing primitives that should suffice:** GiveToken, GrantKeyword, push_play_from_hand, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_4 — Rose Tico

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Resistance

**Rules text:**

> Action [Exhaust]: Heal 2 damage from a Vehicle unit that attacked this phase.
> On Attack: You may heal 2 damage from a Vehicle unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_5 — Admiral Piett

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Play a Capital Ship unit from your hand. It costs 1 resource less.
> Each Capital Ship unit you play costs 2 resources less.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_7 — Admiral Holdo

**Type/Stats:** Leader, cost 6, 3/8  |  Traits: Official, Resistance

**Rules text:**

> Action [1 resource, Exhaust]: Give a Resistance unit or a unit with a Resistance upgrade on it +2/+2 for this phase.
> On Attack: You may give another Resistance unit or a unit with a Resistance upgrade on it +2/+2 for this phase.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_8 — Wedge Antilles

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Pilot, Rebel

**Rules text:**

> Action [Exhaust]: Play a card from your hand using Piloting. It costs 1 resource less.
> 
> Attached unit is a leader unit. It gains: “On Attack: The next Pilot card you play this phase costs 1 resource less. (This includes Piloting costs.)”
> 
> Epic Action: If you control 5 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_11 — Major Vonreg

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: First Order, Pilot

**Rules text:**

> Action [Exhaust]: Play a Vehicle unit from your hand (paying its cost). If you do, give another unit +1/+0 for this phase.
> 
> Attached unit is a leader unit. It gains: “On Attack: You may give another unit in this arena +1/+0 for this phase.”
> 
> Epic Action: If you control 4 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_play_from_hand, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

