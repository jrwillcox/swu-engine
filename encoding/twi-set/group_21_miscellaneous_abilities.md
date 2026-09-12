# twi-set:21 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_66 | Multi-Troop Transport | Unit | 7 | 3/6 | Exploit |
| TWI_69 | Roger Roger | Upgrade | 1 |  |  |
| TWI_72 | I Have the High Ground | Event | 1 |  |  |
| TWI_75 | Disruptive Burst | Event | 3 |  |  |
| TWI_95 | Pelta Supply Frigate | Unit | 5 | 3/6 | Coordinate |
| TWI_96 | Aayla Secura | Unit | 5 | 6/5 | Coordinate |
| TWI_102 | Manufactured Soldiers | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### TWI_66 — Multi-Troop Transport

**Type/Stats:** Unit, cost 7, 3/6  |  Traits: Separatist, Tank, Vehicle

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> On Attack: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_69 — Roger Roger

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> When Defeated: Attach this upgrade to a friendly Battle Droid token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_72 — I Have the High Ground

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Choose a friendly unit. Each enemy unit gets –4/–0 while attacking that unit this phase.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_75 — Disruptive Burst

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give each enemy unit –1/–1 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_95 — Pelta Supply Frigate

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> Coordinate — When Played: Create a Clone Trooper token. (Gain this ability while you control 3 or more units, including this one.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_96 — Aayla Secura

**Type/Stats:** Unit, cost 5, 6/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Coordinate — On Attack: Prevent all combat damage that would be dealt to this unit for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_102 — Manufactured Soldiers

**Type/Stats:** Event, cost 3  |  Traits: Supply

**Rules text:**

> Choose one:
> <bullet>Create 2 Clone Trooper tokens.
> Create 3 Battle Droid tokens.</bullet>

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_modal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

