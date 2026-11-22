# hmw-set:03 — Direct damage & removal

- **Group id (paste this):** `hmw-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_49 | Greater Sarlacc | Unit | 9 | 9/8 | Overwhelm |
| HMW_51 | Third Sister | Unit | 4 | 6/3 | Overwhelm |
| HMW_54 | Seismic Detonation | Event | 6 |  |  |
| HMW_60 | Vice Admiral Rampart | Unit | 2 | 1/5 |  |
| HMW_64 | Scorch | Unit | 3 | 3/5 |  |
| HMW_68 | Imperial Commandos | Unit | 6 | 4/4 |  |
| HMW_78 | Qui-Gon Jinn | Unit | 5 | 2/5 | Grit |

## Per-card analysis & acceptance criteria

### HMW_49 — Greater Sarlacc

**Type/Stats:** Unit, cost 9, 9/8  |  Traits: Creature

**Rules text:**

> Overwhelm
> While playing this unit, you may defeat any number of ready resources you control. For each resource defeated this way, this unit costs 3 resources less to play.

**Mechanical analysis:** trigger archetype `constant`; effect families ['defeat', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_51 — Third Sister

**Type/Stats:** Unit, cost 4, 6/3  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Overwhelm
> When Played: You may deal 2 damage to a unit. If you do, that unit's controller may deal 3 damage to a unit. If they do, that unit's controller may deal 4 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_54 — Seismic Detonation

**Type/Stats:** Event, cost 6  |  Traits: Tactic

**Rules text:**

> Choose an arena. At the start of the next regroup phase, deal 3 damage to each enemy unit in that arena.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_60 — Vice Admiral Rampart

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Imperial, Official

**Rules text:**

> If an upgrade on your base would be defeated, you may defeat this unit instead.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_64 — Scorch

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> On Attack: You may deal 1 damage to an upgraded unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_68 — Imperial Commandos

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> When Played: You may defeat a non-leader unit with 4 or less power.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_78 — Qui-Gon Jinn

**Type/Stats:** Unit, cost 5, 2/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Grit
> When Played: You may defeat a unit that attacked your base this phase. If it's a leader unit, defeat this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

