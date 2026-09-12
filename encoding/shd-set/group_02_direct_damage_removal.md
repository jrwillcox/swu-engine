# shd-set:02 — Direct damage & removal

- **Group id (paste this):** `shd-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_45 | Rose Tico | Unit | 4 | 2/6 | Shielded |
| SHD_50 | Chewbacca | Unit | 8 | 4/10 | Grit, Smuggle |
| SHD_58 | Val | Unit | 2 | 2/4 | Bounty |
| SHD_79 | Rival's Fall | Event | 6 |  |  |
| SHD_80 | Salacious Crumb | Unit | 1 | 1/3 |  |
| SHD_91 | Jabba's Rancor | Unit | 8 | 9/9 |  |
| SHD_107 | Enterprising Lackeys | Unit | 4 | 5/5 | Smuggle |

## Per-card analysis & acceptance criteria

### SHD_45 — Rose Tico

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Resistance

**Rules text:**

> Shielded (When you play this unit, give a Shield token to her.)
> On Attack: You may defeat a Shield token on a friendly unit. If you do, give 2 Experience tokens to that unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_50 — Chewbacca

**Type/Stats:** Unit, cost 8, 4/10  |  Traits: Underworld, Wookiee

**Rules text:**

> Grit
> When Played: You may defeat a unit with 5 or less remaining HP.
> Smuggle [9 resources Aggression Heroism]

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_58 — Val

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Underworld

**Rules text:**

> Bounty — Deal 3 damage to a unit.
> When Defeated: Give 2 Experience tokens to a friendly unit. (The active player chooses the order of Val's abilities.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_79 — Rival's Fall

**Type/Stats:** Event, cost 6  |  Traits: Tactic

**Rules text:**

> Defeat a unit.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_80 — Salacious Crumb

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Creature, Underworld

**Rules text:**

> When Played: Heal 1 damage from your base.
> Action [Exhaust, return this unit to his owner's hand]: Deal 1 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_91 — Jabba's Rancor

**Type/Stats:** Unit, cost 8, 9/9  |  Traits: Creature, Underworld

**Rules text:**

> If you control Jabba the Hutt (as a leader or unit), this unit costs 1 resource less to play.
> When Played/On Attack: Deal 3 damage to another friendly ground unit and 3 damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_107 — Enterprising Lackeys

**Type/Stats:** Unit, cost 4, 5/5  |  Traits: Underworld

**Rules text:**

> When Defeated: You may defeat a friendly resource. If you do, put this unit into play as a resource.
> Smuggle [6 resources Command Command]

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['defeat', 'ramp'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

