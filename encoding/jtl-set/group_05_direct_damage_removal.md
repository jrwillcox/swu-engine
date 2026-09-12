# jtl-set:05 — Direct damage & removal

- **Group id (paste this):** `jtl-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_168 | Insurgent Saboteurs | Unit | 6 | 6/5 | Saboteur |
| JTL_170 | War Juggernaut | Unit | 6 | 3/7 |  |
| JTL_172 | Twin Laser Turret | Upgrade | 2 |  |  |
| JTL_173 | Fight Fire With Fire | Event | 1 |  |  |
| JTL_174 | Hotshot Maneuver | Event | 1 |  |  |
| JTL_175 | System Shock | Event | 1 |  |  |
| JTL_180 | Piercing Shot | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_168 — Insurgent Saboteurs

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Rebel, Trooper

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: You may defeat an upgrade.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_170 — War Juggernaut

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Republic, Tank, Vehicle

**Rules text:**

> This unit gets +1/+0 for each damaged unit.
> When Played: Deal 1 damage to each of any number of units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_172 — Twin Laser Turret

**Type/Stats:** Upgrade, cost 2  |  Traits: Modification, Weapon

**Rules text:**

> Attach to a Vehicle unit.
> Attached unit gains: “On Attack: Deal 1 damage to each of up to 2 units in this arena.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_173 — Fight Fire With Fire

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Choose a friendly unit and an enemy unit in the same arena. If you do, deal 3 damage to each of them.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_174 — Hotshot Maneuver

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Choose a friendly unit. For each of its “On Attack” abilities, deal 2 damage to a different enemy unit. Then, attack with the chosen unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'attack_grant'].

**Existing primitives that should suffice:** DealDamage, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_175 — System Shock

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Defeat a non-leader upgrade attached to a unit. If you do, deal 1 damage to that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_180 — Piercing Shot

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Defeat all Shield tokens on a unit. Deal 3 damage to that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

