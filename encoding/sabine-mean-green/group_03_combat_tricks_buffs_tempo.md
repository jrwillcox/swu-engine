# sabine-mean-green:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sabine-mean-green:03`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_103 | Rebel Assault | Event | 1 |  |  |
| SHD_126 | The Darksaber | Upgrade | 4 |  |  |
| SOR_144 | Red Three | Unit | 3 | 2/3 | Raid |
| SOR_245 | Medal Ceremony | Event | 0 |  |  |

## Per-card analysis & acceptance criteria

### SOR_103 — Rebel Assault

**Type/Stats:** Event, cost 1  |  Traits: Rebel, Tactic

**Rules text:**

> Attack with a REBEL unit. It gets +1/+0 for this attack.
> 
> Then, attack with another REBEL unit. It gets +1/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_126 — The Darksaber

**Type/Stats:** Upgrade, cost 4  |  Traits: Item, Mandalorian, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> While playing this upgrade on a Mandalorian unit, ignore its aspect penalty.
> Attached unit gains, “On Attack: Give an Experience token to each other friendly Mandalorian unit.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_144 — Red Three

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> 
> Each other friendly [Heroism] unit gains Raid 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_245 — Medal Ceremony

**Type/Stats:** Event, cost 0  |  Traits: Rebel

**Rules text:**

> Give an Experience token to each of up to 3 REBEL units that attacked this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

