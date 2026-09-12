# sor-set:18 — Miscellaneous abilities

- **Group id (paste this):** `sor-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_93 | Alliance Dispatcher | Unit | 1 | 1/2 |  |
| SOR_104 | U-Wing Reinforcement | Event | 7 |  |  |
| SOR_122 | Traitorous | Upgrade | 5 |  |  |
| SOR_127 | Strike True | Event | 3 |  |  |
| SOR_140 | SpecForce Soldier | Unit | 1 | 2/2 |  |
| SOR_151 | Karabast | Event | 2 |  |  |
| SOR_160 | Wolffe | Unit | 2 | 3/2 | Saboteur |

## Per-card analysis & acceptance criteria

### SOR_93 — Alliance Dispatcher

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Rebel

**Rules text:**

> Action [exhaust]: Play a unit from your hand. It costs [1 resource] less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_104 — U-Wing Reinforcement

**Type/Stats:** Event, cost 7  |  Traits: Supply

**Rules text:**

> Search the top 10 cards of your deck for up to 3 units with combined cost 7 or less and play each of them for free. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_122 — Traitorous

**Type/Stats:** Upgrade, cost 5  |  Traits: Innate

**Rules text:**

> When this upgrade becomes attached to a non‑leader unit that costs 3 or less: Take control of that unit.
> 
> When this upgrade becomes unattached from a unit: That unit's owner takes control of it.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_127 — Strike True

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> A friendly unit deals damage equal to its power to an enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_140 — SpecForce Soldier

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Rebel, Trooper

**Rules text:**

> When Played: A unit loses Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_151 — Karabast

**Type/Stats:** Event, cost 2  |  Traits: Spectre

**Rules text:**

> A friendly unit deals damage to an enemy unit equal to the amount of damage on the friendly unit plus 1.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_160 — Wolffe

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Clone, Fringe

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> When Played/On Attack: Bases can't be healed for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

