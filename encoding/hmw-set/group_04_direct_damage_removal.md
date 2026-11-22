# hmw-set:04 — Direct damage & removal

- **Group id (paste this):** `hmw-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_79 | Radiant VII | Unit | 6 | 5/7 |  |
| HMW_86 | N-1 Patroller | Unit | 3 | 2/2 |  |
| HMW_94 | Sando Aqua Monster | Unit | 8 | 5/9 | Grit |
| HMW_99 | Always a Bigger Fish | Event | 2 |  |  |
| HMW_102 | Dragon's Might | Event | 4 |  |  |
| HMW_114 | Breach | Event | 2 |  | Overwhelm |
| HMW_125 | The Marauder | Unit | 7 | 5/7 |  |

## Per-card analysis & acceptance criteria

### HMW_79 — Radiant VII

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: You may deal 3 damage to this unit. If you do, give a Shield token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_86 — N-1 Patroller

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Fighter, Naboo, Vehicle

**Rules text:**

> When Played: You may defeat a non-leader unit with 1 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_94 — Sando Aqua Monster

**Type/Stats:** Unit, cost 8, 5/9  |  Traits: Creature

**Rules text:**

> Grit
> When Played: If you control a Naboo base, you may defeat any number of ground units with combined power equal to or less than this unit's power. Deal damage to this unit equal to the combined power of the defeated units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_99 — Always a Bigger Fish

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Defeat a friendly Creature unit. If you do, play a Creature unit that costs up to 3 more than the defeated unit from your hand for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_102 — Dragon's Might

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Defeat a non-leader unit with 4 or less power.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_114 — Breach

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> A friendly unit deals damage equal to its power to an enemy unit in its arena. If the friendly unit has Overwhelm, deal the excess damage to an enemy base.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_125 — The Marauder

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Transport, Vehicle

**Rules text:**

> While playing this unit, you may choose any number of friendly units. Deal 1 damage to each of them. For each unit chosen this way, this unit costs 1 resource less.

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

