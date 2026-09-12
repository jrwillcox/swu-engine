# lof-set:01 — Direct damage & removal

- **Group id (paste this):** `lof-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_11 | Kit Fisto | Leader | 5 | 1/6 | Saboteur |
| LOF_12 | Rey | Leader | 7 | 6/8 |  |
| LOF_71 | Grappling Guardian | Unit | 7 | 3/9 |  |
| LOF_79 | Shatterpoint | Event | 4 |  |  |
| LOF_91 | Craving Power | Upgrade | 5 |  |  |
| LOF_133 | Purge Trooper | Unit | 3 | 4/2 |  |
| LOF_134 | Heavy Missile Gunship | Unit | 4 | 4/3 |  |

## Per-card analysis & acceptance criteria

### LOF_11 — Kit Fisto

**Type/Stats:** Leader, cost 5, 1/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [1 resource, Exhaust]: If you attacked with a Jedi unit this phase, deal 2 damage to a unit.
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> This unit gets +1/+0 for each other friendly Jedi unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_12 — Rey

**Type/Stats:** Leader, cost 7, 6/8  |  Traits: Force, Resistance

**Rules text:**

> Action [Exhaust]: If you played a non-unit Force card this phase, deal 1 damage to a unit.
> When Deployed: You may discard your hand. If you do, draw 2 cards.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'draw', 'discard'].

**Existing primitives that should suffice:** DealDamage, DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_71 — Grappling Guardian

**Type/Stats:** Unit, cost 7, 3/9  |  Traits: Creature

**Rules text:**

> When Played: You may defeat a space unit with 6 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_79 — Shatterpoint

**Type/Stats:** Event, cost 4  |  Traits: Force

**Rules text:**

> Choose one:
> Defeat a non-leader unit with 3 or less remaining HP.
> Use the Force (lose your Force token). If you do, defeat a non-leader unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, push_modal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_91 — Craving Power

**Type/Stats:** Upgrade, cost 5  |  Traits: Innate

**Rules text:**

> Attach to a friendly unit.
> When Played: Deal damage to an enemy unit equal to attached unit's power.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_133 — Purge Trooper

**Type/Stats:** Unit, cost 3, 4/2  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: You may deal 2 damage to a Force unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_134 — Heavy Missile Gunship

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Droid, Separatist, Transport, Vehicle

**Rules text:**

> Action [Exhaust]: Deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

