# ash-set:05 — Direct damage & removal

- **Group id (paste this):** `ash-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_112 | Luke Skywalker | Unit | 6 | 5/5 | Restore |
| ASH_118 | 8D8 | Unit | 2 | 1/4 | Hidden |
| ASH_132 | Queen Soruna | Unit | 6 | 5/7 |  |
| ASH_137 | Wipe Them Out | Event | 2 |  |  |
| ASH_138 | Turning the Tide | Event | 3 |  |  |
| ASH_142 | Mortar Trooper | Unit | 2 | 1/4 |  |
| ASH_146 | Justifier | Unit | 5 | 4/5 |  |

## Per-card analysis & acceptance criteria

### ASH_112 — Luke Skywalker

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Force, Jedi

**Rules text:**

> Restore 1
> When Played: If you control at least 4 units, deal 3 damage to each enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_118 — 8D8

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Droid, Underworld

**Rules text:**

> Hidden
> Action [Exhaust]: Deal 1 damage to another friendly unit. If you do, search the top 5 cards of your deck for a unit, reveal it, and draw it.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_132 — Queen Soruna

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Naboo, Official

**Rules text:**

> When Played/On Attack: You may reveal a unit from your hand. If you do, deal 3 damage to a unit with the same cost as the revealed unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_137 — Wipe Them Out

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. For this attack, you may deal its excess damage to another unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'attack_grant'].

**Existing primitives that should suffice:** DealDamage, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_138 — Turning the Tide

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Choose a unit. Deal 1 damage to it for each friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_142 — Mortar Trooper

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Imperial, Trooper

**Rules text:**

> Action [Exhaust]: Deal 1 damage to each of up to 3 ground units.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_146 — Justifier

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played/On Attack: You may deal 1 damage to a unit. If that unit is defeated this way, give an Advantage token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

