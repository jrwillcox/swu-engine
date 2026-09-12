# ash-set:07 — Direct damage & removal

- **Group id (paste this):** `ash-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_165 | Clan Vizsla Soldier | Unit | 2 | 2/3 |  |
| ASH_170 | Desert Sharpshooter | Unit | 3 | 3/3 |  |
| ASH_171 | Pegasus Tri-Wing | Unit | 3 | 3/2 |  |
| ASH_174 | StarFortress Heavy Bomber | Unit | 5 | 3/3 |  |
| ASH_176 | Imposing Scout Walker | Unit | 6 | 4/6 |  |
| ASH_179 | Boba Fett's Rancor | Unit | 8 | 8/9 |  |
| ASH_183 | Whistling Birds | Upgrade | 3 |  |  |

## Per-card analysis & acceptance criteria

### ASH_165 — Clan Vizsla Soldier

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Mandalorian, Trooper

**Rules text:**

> When Defeated: You may defeat an upgrade.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_170 — Desert Sharpshooter

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Bounty Hunter, Twi'lek

**Rules text:**

> When Played: You may deal 2 damage to an upgraded ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_171 — Pegasus Tri-Wing

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Fighter, Vehicle

**Rules text:**

> When Played: You may defeat a friendly upgrade. If you do, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_174 — StarFortress Heavy Bomber

**Type/Stats:** Unit, cost 5, 3/3  |  Traits: Resistance, Transport, Vehicle

**Rules text:**

> When Played: You may deal 6 damage to a non-<uq> ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_176 — Imposing Scout Walker

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Imperial, Vehicle, Walker

**Rules text:**

> When Played: You may deal 3 damage to a ground unit. If it's defeated this way, give 3 Advantage tokens to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_179 — Boba Fett's Rancor

**Type/Stats:** Unit, cost 8, 8/9  |  Traits: Creature, Underworld

**Rules text:**

> When Played: Deal 5 damage to your base. Then, deal 5 damage to an enemy ground unit. Then, deal 5 damage to the same unit.
> On Attack: You may deal 1 damage to a base for every 5 damage on your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_183 — Whistling Birds

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “When Attack Ends: If this unit dealt combat damage to an opponent's base, deal 2 damage to each unit that opponent controls in this unit's arena.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

