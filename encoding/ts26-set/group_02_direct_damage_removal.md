# ts26-set:02 — Direct damage & removal

- **Group id (paste this):** `ts26-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_25 | Fiery Alliance | Upgrade | 2 |  |  |
| TS26_29 | Ziton Moj | Unit | 4 | 4/4 | Ambush |
| TS26_32 | Reckless Landing | Event | 2 |  |  |
| TS26_58 | Backed by the Pykes | Event | 3 |  |  |
| TS26_62 | R2-D2 | Unit | 2 | 1/3 | Raid |
| TS26_64 | Urgent Mission | Event | 2 |  |  |
| TS26_67 | Ruping Rider | Unit | 4 | 3/4 | Grit |

## Per-card analysis & acceptance criteria

### TS26_25 — Fiery Alliance

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: You may deal 1 damage to another friendly unit and attack with it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'attack_grant'].

**Existing primitives that should suffice:** DealDamage, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_29 — Ziton Moj

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Underworld

**Rules text:**

> Ambush (When you play this unit, he may attack an enemy unit.)
> On Attack: For each player, deal 1 damage to a unit that player controls.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_32 — Reckless Landing

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Play a unit from your hand. It costs 4 resources less. Deal 4 damage to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, push_play_from_hand, CostReduction, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_58 — Backed by the Pykes

**Type/Stats:** Event, cost 3  |  Traits: Supply

**Rules text:**

> Give an Experience token to a friendly unit.
> You may deal damage to a unit equal to the number of Experience tokens on friendly units.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_62 — R2-D2

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Droid, Republic

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> When Played: You may deal 2 damage to a base. If you do, that base's controller draws a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_64 — Urgent Mission

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Deal 2 damage to your base.
> Draw 2 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_67 — Ruping Rider

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Creature, Trooper

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: If your base has 15 or more damage on it, deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

