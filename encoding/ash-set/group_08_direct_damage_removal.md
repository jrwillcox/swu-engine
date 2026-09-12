# ash-set:08 — Direct damage & removal

- **Group id (paste this):** `ash-set:08`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_186 | Treacherous Minefield | Event | 2 |  |  |
| ASH_187 | Reckoning | Event | 3 |  |  |
| ASH_194 | Snub Fighter Squadron | Unit | 4 | 4/3 | Ambush |
| ASH_196 | Gorian Shard's Corsair | Unit | 6 | 6/5 |  |
| ASH_210 | DDC Defender | Upgrade | 1 |  |  |
| ASH_259 | LEP Ratcatcher | Unit | 1 | 1/1 |  |

## Per-card analysis & acceptance criteria

### ASH_186 — Treacherous Minefield

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Choose an arena. For this phase, each unit in that arena gains: “On Attack: Deal 2 damage to this unit.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_187 — Reckoning

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Deal damage to a unit equal to the total amount of damage on all units you control.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_194 — Snub Fighter Squadron

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played: Deal 1 damage to a space unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_196 — Gorian Shard's Corsair

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Capital Ship, Underworld, Vehicle

**Rules text:**

> Damage dealt by friendly Underworld cards is unpreventable.
> When Played/On Attack: You may deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_210 — DDC Defender

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Defense: You may deal 1 damage to a unit in this unit's arena and exhaust it.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_259 — LEP Ratcatcher

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Droid

**Rules text:**

> When Played: You may deal 1 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

