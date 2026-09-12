# sor-set:02 — Direct damage & removal

- **Group id (paste this):** `sor-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_52 | Redemption | Unit | 8 | 6/9 | Sentinel |
| SOR_75 | It Binds All Things | Event | 2 |  |  |
| SOR_77 | Takedown | Event | 4 |  |  |
| SOR_85 | Rukh | Unit | 5 | 3/6 | Shielded |
| SOR_90 | Devastator | Unit | 10 | 10/10 | Overwhelm, Sentinel |
| SOR_121 | Hardpoint Heavy Blaster | Upgrade | 2 |  |  |
| SOR_133 | Seventh Sister | Unit | 5 | 3/6 | Saboteur |

## Per-card analysis & acceptance criteria

### SOR_52 — Redemption

**Type/Stats:** Unit, cost 8, 6/9  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> When Played: Heal up to 8 total damage from any number of units and/or bases. Deal that much damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_75 — It Binds All Things

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Heal up to 3 damage from a unit. If you control a FORCE unit, you may deal that much damage to another unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_77 — Takedown

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a unit with 5 or less remaining HP.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_85 — Rukh

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> 
> When this unit deals combat damage to a non-leader unit while attacking: Defeat that unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_90 — Devastator

**Type/Stats:** Unit, cost 10, 10/10  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Sentinel
> 
> Overwhelm
> 
> When Played: You may deal damage to a unit equal to the number of resources you control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_121 — Hardpoint Heavy Blaster

**Type/Stats:** Upgrade, cost 2  |  Traits: Modification, Weapon

**Rules text:**

> Attach to a VEHICLE unit.
> 
> Attached unit gains: "On Attack: If this unit isn't attacking a base, you may deal 2 damage to a unit in the defender's arena."

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_133 — Seventh Sister

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> When this unit deals combat damage to an opponent's base: You may deal 3 damage to a ground unit that opponent controls.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

