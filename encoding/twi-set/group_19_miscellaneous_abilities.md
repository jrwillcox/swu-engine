# twi-set:19 — Miscellaneous abilities

- **Group id (paste this):** `twi-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_2 | Nute Gunray | Leader | 6 | 2/8 |  |
| TWI_5 | Count Dooku | Leader | 7 | 5/9 | Exploit |
| TWI_22 | Droid Manufactory | Base |  | None/24 |  |
| TWI_31 | Rune Haako | Unit | 2 | 3/2 |  |
| TWI_32 | Wartime Trade Official | Unit | 2 | 1/3 |  |
| TWI_38 | Providence Destroyer | Unit | 8 | 5/7 | Exploit |
| TWI_39 | Malevolence | Unit | 9 | 7/7 | Exploit, Restore |

## Per-card analysis & acceptance criteria

### TWI_2 — Nute Gunray

**Type/Stats:** Leader, cost 6, 2/8  |  Traits: Official, Separatist

**Rules text:**

> Action [Exhaust]: If 2 or more friendly units were defeated this phase, create a Battle Droid token.
> On Attack: Create a Battle Droid token.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_5 — Count Dooku

**Type/Stats:** Leader, cost 7, 5/9  |  Traits: Force, Separatist, Sith

**Rules text:**

> Action [Exhaust]: Play a Separatist card from your hand. It gains Exploit 1. (You may defeat 1 unit you control. If you do, that card costs 2 resources less.)
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> On Attack: The next Separatist card you play this phase gains Exploit 3.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_22 — Droid Manufactory

**Type/Stats:** Base

**Rules text:**

> When you deploy a leader: Create 2 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_31 — Rune Haako

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Official, Separatist

**Rules text:**

> When Played: If a friendly unit was defeated this phase, you may give a unit –1/–1 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_32 — Wartime Trade Official

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Official, Separatist

**Rules text:**

> When Defeated: Create a Battle Droid token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_38 — Providence Destroyer

**Type/Stats:** Unit, cost 8, 5/7  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> On Attack: Give an enemy space unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_39 — Malevolence

**Type/Stats:** Unit, cost 9, 7/7  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> Exploit 4
> Restore 2
> When Played: Give an enemy unit –4/–0 for this phase. It can't attack for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

