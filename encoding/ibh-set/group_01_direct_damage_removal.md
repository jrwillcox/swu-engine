# ibh-set:01 — Direct damage & removal

- **Group id (paste this):** `ibh-set:01`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IBH_20 | Luke Skywalker | Unit | 7 | 6/6 | Restore |
| IBH_53 | Darth Vader | Leader | 6 | 3/8 |  |
| IBH_72 | Avenger | Unit | 8 | 8/6 |  |
| IBH_95 | You Have Failed Me | Event | 4 |  |  |
| IBH_99 | Blizzard One | Unit | 7 | 5/7 |  |
| IBH_104 | The Desolation of Hoth | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### IBH_20 — Luke Skywalker

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Force, Rebel

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> When Played: You may deal 3 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_53 — Darth Vader

**Type/Stats:** Leader, cost 6, 3/8  |  Traits: Force, Imperial, Sith

**Rules text:**

> Action [1 resource, Exhaust]: Deal 1 damage to a base.
> On Attack: Deal 2 damage to a base.
> Epic Action: If you control 6 or more resources, deploy this leader. (Flip him, ready him, and move him to the ground arena.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_72 — Avenger

**Type/Stats:** Unit, cost 8, 8/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: Deal 1 damage to each other unit (including friendly units).

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_95 — You Have Failed Me

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a friendly unit. If you do, ready a friendly unit with 5 or less power.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_99 — Blizzard One

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Imperial, Vehicle, Walker

**Rules text:**

> When Played: You may defeat a non-leader ground unit with 3 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_104 — The Desolation of Hoth

**Type/Stats:** Event, cost 6  |  Traits: Disaster

**Rules text:**

> Defeat up to 2 enemy units that each cost 3 or less.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

