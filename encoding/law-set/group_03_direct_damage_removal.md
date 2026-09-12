# law-set:03 — Direct damage & removal

- **Group id (paste this):** `law-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_77 | Shadow of Stygeon Prime | Upgrade | 4 |  |  |
| LAW_78 | Sabine Wren | Unit | 3 | 3/3 | Ambush |
| LAW_85 | You Hold This | Event | 1 |  |  |
| LAW_99 | Governor's Shuttle | Unit | 5 | 2/4 |  |
| LAW_102 | Choke on Aspirations | Event | 1 |  |  |
| LAW_106 | Defiant Scrapper | Unit | 3 | 3/4 |  |
| LAW_124 | Industrious Team | Unit | 8 | 4/7 |  |

## Per-card analysis & acceptance criteria

### LAW_77 — Shadow of Stygeon Prime

**Type/Stats:** Upgrade, cost 4  |  Traits: Condition

**Rules text:**

> Attach to a non-leader unit.
> Attached unit can't ready. It gains: “When the regroup phase starts: Deal 2 damage to your base.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_78 — Sabine Wren

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Mandalorian, Rebel, Spectre

**Rules text:**

> Ambush (When you play this unit, she may attack an enemy unit.)
> When Played: You may defeat a non-<uq> upgrade. If you control a Vigilance or Command unit, you may defeat an upgrade instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_85 — You Hold This

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Choose a friendly non-leader unit. An opponent takes control of it. If they do, deal 4 damage to another unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_99 — Governor's Shuttle

**Type/Stats:** Unit, cost 5, 2/4  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> When Played: Each player chooses a unit they control. Defeat those units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_102 — Choke on Aspirations

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Deal up to 5 damage to a friendly non-Vehicle unit. If it survives, heal damage from your base equal to the damage dealt this way.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_106 — Defiant Scrapper

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fringe

**Rules text:**

> When Played: You may defeat an enemy Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_124 — Industrious Team

**Type/Stats:** Unit, cost 8, 4/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: You may defeat a non-leader unit with 4 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

