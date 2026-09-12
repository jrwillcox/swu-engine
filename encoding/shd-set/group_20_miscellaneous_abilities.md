# shd-set:20 — Miscellaneous abilities

- **Group id (paste this):** `shd-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_16 | Fennec Shand | Leader | 5 | 4/4 | Ambush, Saboteur |
| SHD_51 | Mystic Reflection | Event | 1 |  |  |
| SHD_67 | Fenn Rau | Unit | 6 | 5/6 |  |
| SHD_72 | Imprisoned | Upgrade | 2 |  |  |
| SHD_77 | Evidence of the Crime | Event | 3 |  |  |
| SHD_88 | Ephant Mon | Unit | 5 | 4/6 |  |
| SHD_92 | Finalizer | Unit | 11 | 11/11 | Overwhelm |

## Per-card analysis & acceptance criteria

### SHD_16 — Fennec Shand

**Type/Stats:** Leader, cost 5, 4/4  |  Traits: Underworld

**Rules text:**

> Action [1 resource, Exhaust]: Play a unit that costs 4 or less from your hand (paying its cost). Give it Ambush for this phase. (After you play the unit, it may ready and attack an enemy unit.)
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> Action: Play a unit that costs 4 or less from your hand (paying its cost). Give it Ambush for this phase.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_51 — Mystic Reflection

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Give an enemy unit –2/–0 for this phase. If you control a Force unit, give the enemy unit –2/–2 for this phase instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_67 — Fenn Rau

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Mandalorian

**Rules text:**

> When Played: You may play an upgrade from your hand. It costs 2 resources less.
> When you play an upgrade on this unit: Give an enemy unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_72 — Imprisoned

**Type/Stats:** Upgrade, cost 2  |  Traits: Condition, Law

**Rules text:**

> Attach to a non-leader unit.
> Attached unit loses its current abilities and can't gain abilities.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_77 — Evidence of the Crime

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Take control of an upgrade that costs 3 or less and attach it to an eligible unit of your choice.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_88 — Ephant Mon

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Underworld

**Rules text:**

> On Attack: Choose an enemy non-leader unit that attacked your base this phase. A friendly unit in the same arena captures that unit. (Put the captured card facedown under the friendly unit until the friendly unit leaves play.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_92 — Finalizer

**Type/Stats:** Unit, cost 11, 11/11  |  Traits: Capital Ship, First Order, Vehicle

**Rules text:**

> Overwhelm
> When Played: Choose any number of friendly units. Each of those units captures an enemy non-leader unit in the same arena.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

