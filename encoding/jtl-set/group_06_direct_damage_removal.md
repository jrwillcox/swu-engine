# jtl-set:06 — Direct damage & removal

- **Group id (paste this):** `jtl-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_198 | Fireball | Unit | 2 | 3/3 | Ambush |
| JTL_218 | Guerilla Soldier | Unit | 3 | 2/3 |  |
| JTL_219 | Rafa Martez | Unit | 3 | 3/3 |  |
| JTL_222 | Kimogila Heavy Fighter | Unit | 4 | 3/4 |  |
| JTL_226 | Radiant VII | Unit | 7 | 5/6 |  |
| JTL_227 | Superheavy Ion Cannon | Upgrade | 2 |  |  |
| JTL_234 | Torpedo Barrage | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_198 — Fireball

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When the regroup phase starts: Deal 1 damage to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_218 — Guerilla Soldier

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fringe, Trooper, Twi'lek

**Rules text:**

> When Played: Deal 3 indirect damage to a player. If a base is damaged this way, ready this unit. (That player assigns 3 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_219 — Rafa Martez

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Underworld

**Rules text:**

> When Played/On Attack: Deal 1 damage to a friendly unit and ready a resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** DealDamage, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_222 — Kimogila Heavy Fighter

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: Deal 3 indirect damage to a player. Exhaust each unit damaged this way. (That player assigns 3 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_226 — Radiant VII

**Type/Stats:** Unit, cost 7, 5/6  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> Each enemy non-leader unit gets –1/–0 for each damage on it.
> When Played: Deal 5 indirect damage to a player.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_227 — Superheavy Ion Cannon

**Type/Stats:** Upgrade, cost 2  |  Traits: Modification, Weapon

**Rules text:**

> Attach to a Capital Ship or Transport unit.
> Attached unit gains: “On Attack: You may exhaust a non-leader unit the defending player controls. If you do, deal indirect damage equal to its power to that player.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_234 — Torpedo Barrage

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Deal 5 indirect damage to a player. (They assign 5 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

