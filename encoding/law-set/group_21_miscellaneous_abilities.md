# law-set:21 — Miscellaneous abilities

- **Group id (paste this):** `law-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_92 | Two-Faced Troig | Unit | 3 | 2/4 | Sentinel |
| LAW_116 | Rodian Bondsman | Unit | 2 | 2/3 |  |
| LAW_117 | Conveyex Security Captain | Unit | 3 | 2/4 |  |
| LAW_121 | Canto Bight Security | Unit | 5 | 3/5 | Sentinel |
| LAW_126 | Adventurer Sniper Rifle | Upgrade | 2 |  |  |
| LAW_141 | Targeted For Removal | Upgrade | 3 |  |  |
| LAW_149 | Rey | Unit | 8 | 9/9 |  |

## Per-card analysis & acceptance criteria

### LAW_92 — Two-Faced Troig

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Underworld

**Rules text:**

> Sentinel
> When Played: You may have an opponent take control of this unit. If you do, create 2 Credit tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_116 — Rodian Bondsman

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Bounty Hunter

**Rules text:**

> When Defeated: Each player creates a Credit token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_117 — Conveyex Security Captain

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Imperial, Trooper

**Rules text:**

> Enemy Credit tokens lose all abilities.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_121 — Canto Bight Security

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Fringe

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> On Defense: Create a Credit token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_126 — Adventurer Sniper Rifle

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “Action [Exhaust]: Choose an undamaged non-leader ground unit. Its printed HP is considered to be 1 for this phase.”

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_141 — Targeted For Removal

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> Attached unit gains: “When Defeated: An opponent creates Credit tokens equal to this unit's cost.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_149 — Rey

**Type/Stats:** Unit, cost 8, 9/9  |  Traits: Force, Jedi, Resistance

**Rules text:**

> Opponents can't take control of this unit.
> This unit can't be defeated by enemy card abilities.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

