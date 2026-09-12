# sor-set:17 — Miscellaneous abilities

- **Group id (paste this):** `sor-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_34 | Del Meeko | Unit | 3 | 3/3 | Restore |
| SOR_54 | Jedi Lightsaber | Upgrade | 3 |  |  |
| SOR_56 | Bendu | Unit | 6 | 4/7 | Sentinel |
| SOR_61 | Guardian of the Whills | Unit | 2 | 2/2 |  |
| SOR_62 | Regional Governor | Unit | 2 | 1/4 |  |
| SOR_71 | Electrostaff | Upgrade | 2 |  |  |
| SOR_72 | Entrenched | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### SOR_34 — Del Meeko

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Trooper

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> 
> Each event an opponent plays costs [1 resource] more.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_54 — Jedi Lightsaber

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-VEHICLE unit.
> 
> If attached unit is a FORCE unit, it gains: “On Attack: Give the defender –2/–2 for this phase.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_56 — Bendu

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Creature, Force

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> On Attack: The next non-[Heroism], non-[Villainy] card you play this phase costs [2 resources] less.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_61 — Guardian of the Whills

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Fringe

**Rules text:**

> The first upgrade you play on this unit each round costs [1 resource] less.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_62 — Regional Governor

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Imperial, Official

**Rules text:**

> When Played: Name a card. While this unit is in play, opponents can't play the named card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_71 — Electrostaff

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-VEHICLE unit. 
> 
> While attached unit is defending, the attacker gets –1/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_72 — Entrenched

**Type/Stats:** Upgrade, cost 2  |  Traits: Condition

**Rules text:**

> Attached unit can't attack bases.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

