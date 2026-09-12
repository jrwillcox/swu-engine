# jtl-set:03 — Direct damage & removal

- **Group id (paste this):** `jtl-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_104 | Raddus | Unit | 7 | 8/6 | Sentinel |
| JTL_116 | Dornean Gunship | Unit | 5 | 4/6 |  |
| JTL_120 | Dorsal Turret | Upgrade | 1 |  |  |
| JTL_121 | Salvage | Event | 0 |  |  |
| JTL_125 | Air Superiority | Event | 2 |  |  |
| JTL_127 | Lightspeed Assault | Event | 2 |  |  |
| JTL_147 | Black One | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### JTL_104 — Raddus

**Type/Stats:** Unit, cost 7, 8/6  |  Traits: Capital Ship, Resistance, Vehicle

**Rules text:**

> While you control another Resistance card (unit, upgrade, or leader), this unit gains Sentinel.
> When Defeated: Deal damage equal to this unit's power to an enemy unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_116 — Dornean Gunship

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> When Played: Deal indirect damage to a player equal to the number of Vehicle units you control. (That player assigns that much unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_120 — Dorsal Turret

**Type/Stats:** Upgrade, cost 1  |  Traits: Modification, Weapon

**Rules text:**

> Attach to a Vehicle unit.
> Attached unit gains: “When this unit deals combat damage to a unit while attacking: Defeat that unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_121 — Salvage

**Type/Stats:** Event, cost 0  |  Traits: Supply

**Rules text:**

> Play a Vehicle unit from your discard pile (paying its cost). Then, deal 1 damage to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_125 — Air Superiority

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> If you control more space units than an opponent, deal 4 damage to a ground unit that opponent controls.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_127 — Lightspeed Assault

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Defeat a friendly space unit and deal damage equal to its power to an enemy space unit. If you do, deal indirect damage equal to the enemy unit's power to its controller.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_147 — Black One

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> While this unit is upgraded, it gets +1/+0.
> On Attack: If you control Poe Dameron (as a unit, upgrade, or leader), you may deal 1 damage to a unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

