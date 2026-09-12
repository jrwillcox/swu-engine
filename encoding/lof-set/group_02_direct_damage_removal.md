# lof-set:02 — Direct damage & removal

- **Group id (paste this):** `lof-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_141 | Death Field | Event | 4 |  |  |
| LOF_142 | Adi Gallia | Unit | 2 | 2/4 |  |
| LOF_144 | Jedi Starfighter | Unit | 2 | 1/4 |  |
| LOF_145 | Jedi Knight | Unit | 3 | 3/3 |  |
| LOF_147 | Kit Fisto's Aethersprite | Unit | 5 | 4/5 | Saboteur |
| LOF_149 | Mace Windu | Unit | 6 | 6/6 | Overwhelm |
| LOF_155 | DRK-1 Probe Droid | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### LOF_141 — Death Field

**Type/Stats:** Event, cost 4  |  Traits: Force

**Rules text:**

> Deal 2 damage to each non-Vehicle enemy unit. If you control a Force unit, draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_142 — Adi Gallia

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When an opponent plays an event: Deal 1 damage to that player's base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_144 — Jedi Starfighter

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> On Attack: You may deal 1 damage to a space unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_145 — Jedi Knight

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Force, Jedi

**Rules text:**

> When Played: If you have the initiative, deal 2 damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_147 — Kit Fisto's Aethersprite

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> Saboteur
> When Played: You may defeat any number of upgrades on a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_149 — Mace Windu

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: You may use the Force (lose your Force token). If you do, deal 4 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_155 — DRK-1 Probe Droid

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Droid

**Rules text:**

> When Played: You may defeat a non-<uq> (non-unique) upgrade.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

