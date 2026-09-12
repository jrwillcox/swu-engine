# twi-set:20 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_46 | Captain Typho | Unit | 3 | 2/4 | Sentinel |
| TWI_49 | Knight of the Republic | Unit | 6 | 4/7 |  |
| TWI_52 | Hello There | Event | 3 |  |  |
| TWI_53 | Finn | Unit | 3 | 3/4 |  |
| TWI_55 | Equalize | Event | 3 |  |  |
| TWI_60 | Trade Federation Shuttle | Unit | 3 | 2/3 |  |
| TWI_63 | Vulture Interceptor Wing | Unit | 4 | 3/3 |  |

## Per-card analysis & acceptance criteria

### TWI_46 — Captain Typho

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Naboo, Republic, Trooper

**Rules text:**

> When Played/On Attack: Give a unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_49 — Knight of the Republic

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> When this unit is attacked: Create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_52 — Hello There

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Choose a unit that entered play this phase. It gets –4/–4 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_53 — Finn

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fringe, Trooper

**Rules text:**

> When this unit completes an attack: Choose a unique unit. For this phase, if damage would be dealt to that unit, prevent 1 of that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_55 — Equalize

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give a unit –2/–2 for this phase. Then, if you control fewer units than that unit's controller, give another unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_60 — Trade Federation Shuttle

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played: If you control a damaged unit, create a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_63 — Vulture Interceptor Wing

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Droid, Fighter, Separatist, Vehicle

**Rules text:**

> On Attack: Give an enemy unit –1/–1 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

