# sec-set:02 — Direct damage & removal

- **Group id (paste this):** `sec-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_42 | Cassian Andor | Unit | 2 | 2/2 |  |
| SEC_50 | Vigil | Unit | 7 | 5/9 | Plot |
| SEC_53 | One in a Million | Event | 1 |  | Plot |
| SEC_78 | Hyperspace Disaster | Event | 7 |  |  |
| SEC_136 | Arihnda Pryce | Unit | 4 | 4/4 |  |
| SEC_139 | Miraj Scintel | Unit | 5 | 3/7 | Overwhelm |
| SEC_143 | The Elite Squad | Unit | 8 | 6/8 | Grit |

## Per-card analysis & acceptance criteria

### SEC_42 — Cassian Andor

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fringe

**Rules text:**

> While this unit is defending, the attacker gets –2/–0.
> If an enemy card ability would deal damage to this unit, prevent 2 of that damage.

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_50 — Vigil

**Type/Stats:** Unit, cost 7, 5/9  |  Traits: Capital Ship, Resistance, Vehicle

**Rules text:**

> If damage would be dealt to another friendly unit, prevent 1 of that damage.
> If damage would be dealt to this unit by another card, deal that much damage plus 1 instead.
> Plot

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_53 — One in a Million

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> This card can't be played from your hand.
> Defeat a unit with power and remaining HP both equal to the number of ready resources you control.
> Plot

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_78 — Hyperspace Disaster

**Type/Stats:** Event, cost 7  |  Traits: Disaster

**Rules text:**

> Defeat all space units.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_136 — Arihnda Pryce

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Imperial

**Rules text:**

> When Defeated: You may defeat another friendly unit. If you do, deal 4 damage to each enemy base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_139 — Miraj Scintel

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Official, Separatist

**Rules text:**

> While a friendly unit is attacking a damaged unit, the attacker gains Overwhelm.
> When Played: You may deal 3 damage to an undamaged unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_143 — The Elite Squad

**Type/Stats:** Unit, cost 8, 6/8  |  Traits: Imperial, Trooper

**Rules text:**

> Grit
> When Played/When damage is dealt to this unit: You may deal 2 damage to another <uq> (unique) unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

