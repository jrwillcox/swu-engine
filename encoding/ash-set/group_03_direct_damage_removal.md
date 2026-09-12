# ash-set:03 — Direct damage & removal

- **Group id (paste this):** `ash-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_43 | Corona Four | Unit | 2 | 2/3 |  |
| ASH_53 | Pre Vizsla | Unit | 8 | 6/6 |  |
| ASH_60 | Cobb Vanth | Unit | 4 | 2/6 | Grit |
| ASH_62 | The Mandalorian | Unit | 4 | 5/4 | Shielded |
| ASH_67 | Get Lost | Event | 4 |  |  |
| ASH_71 | Battered Haulcraft | Unit | 2 | 2/3 |  |
| ASH_83 | Summa-verminoth | Unit | 12 | 15/15 | Sentinel |

## Per-card analysis & acceptance criteria

### ASH_43 — Corona Four

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> On Attack: You may give a unit –2/–0 for this phase.
> When Defeated: You may defeat a non‑leader unit with 0 power.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_53 — Pre Vizsla

**Type/Stats:** Unit, cost 8, 6/6  |  Traits: Mandalorian, Official

**Rules text:**

> When Played: Defeat any number of non‑leader units with a total of 6 or less remaining HP. Create a Mandalorian token for each unit defeated this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_60 — Cobb Vanth

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Official

**Rules text:**

> Grit
> When you play another unit: You may deal 2 damage to this unit. If you do, give a Shield token to that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_62 — The Mandalorian

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Mandalorian

**Rules text:**

> Shielded
> If damage would be dealt to another friendly unit, you may defeat a Shield token on this unit. If you do, prevent that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_67 — Get Lost

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat an upgraded non-leader unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_71 — Battered Haulcraft

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Transport, Vehicle

**Rules text:**

> When Played: Deal 1 damage to this unit and 1 damage to an enemy space unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_83 — Summa-verminoth

**Type/Stats:** Unit, cost 12, 15/15  |  Traits: Creature

**Rules text:**

> Sentinel
> On Attack: Defeat all other space units.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

