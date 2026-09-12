# law-set:01 — Direct damage & removal

- **Group id (paste this):** `law-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_1 | Saw Gerrera | Leader | 6 | 4/7 | Overwhelm |
| LAW_4 | Aurra Sing | Leader | 7 | 3/7 |  |
| LAW_11 | Darth Vader | Leader | 7 | 6/8 |  |
| LAW_13 | Chewbacca | Leader | 4 | 5/6 |  |
| LAW_17 | Han Solo | Leader | 5 | 4/5 | Saboteur |
| LAW_40 | Taramyn Barcona | Unit | 5 | 4/6 |  |
| LAW_44 | Single Reactor Ignition | Event | 8 |  |  |

## Per-card analysis & acceptance criteria

### LAW_1 — Saw Gerrera

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Rebel

**Rules text:**

> Action [Exhaust]: Attack with a unit. It gets +2/+0 and gains Overwhelm for this attack. After completing this attack, defeat it.
> When Attack Ends: If this unit survived, you may attack with another unit. It gets +2/+0 and gains Overwhelm for this attack. After completing this attack, defeat it.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['defeat', 'stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_4 — Aurra Sing

**Type/Stats:** Leader, cost 7, 3/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Action [Exhaust]: Defeat a non‑leader unit with 1 or less remaining HP.
> When Deployed: You may defeat a non‑leader unit with 5 or less remaining HP.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_11 — Darth Vader

**Type/Stats:** Leader, cost 7, 6/8  |  Traits: Force, Imperial, Sith

**Rules text:**

> Action [Exhaust, discard a card from your hand]: Deal 1 damage to a unit or base.
> On Attack: Discard any number of cards from your hand. Deal damage to a unit or base equal to the number of cards discarded this way.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_13 — Chewbacca

**Type/Stats:** Leader, cost 4, 5/6  |  Traits: Underworld, Wookiee

**Rules text:**

> Action [1 resource, Exhaust, defeat a friendly resource]: Deal 2 damage to a unit and create a Credit token.
> On Attack: You may defeat a friendly resource. If you do, deal 2 damage to a unit and create a Credit token.
> Epic Action [4 resources]: Deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'defeat', 'ramp'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade, create-token-unit, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_17 — Han Solo

**Type/Stats:** Leader, cost 5, 4/5  |  Traits: Underworld

**Rules text:**

> Action [Exhaust, defeat a friendly token]: Deal 1 damage to a unit.
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: Defeat any number of friendly tokens. Deal damage to a unit equal to the number of tokens defeated this way.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_40 — Taramyn Barcona

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Rebel, Trooper

**Rules text:**

> When Played: You may defeat a Credit token (belonging to any player). If you do, give an Experience token to this unit and another friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_44 — Single Reactor Ignition

**Type/Stats:** Event, cost 8  |  Traits: Disaster, Tactic

**Rules text:**

> Defeat all units. For each enemy unit defeated this way, deal 1 damage to its controller's base.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

