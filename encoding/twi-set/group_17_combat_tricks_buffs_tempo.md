# twi-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_178 | Planetary Invasion | Event | 12 |  | Exploit, Overwhelm |
| TWI_183 | Rush Clovis | Unit | 4 | 3/5 | Raid |
| TWI_185 | Ziro the Hutt | Unit | 5 | 2/8 |  |
| TWI_186 | San Hill | Unit | 6 | 3/7 | Exploit |
| TWI_194 | Ahsoka Tano | Unit | 3 | 3/4 | Ambush |
| TWI_197 | Republic Attack Pod | Unit | 6 | 6/7 |  |
| TWI_200 | Creative Thinking | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TWI_178 — Planetary Invasion

**Type/Stats:** Event, cost 12  |  Traits: Plan, Separatist

**Rules text:**

> Exploit 3
> Ready up to 3 units. Each of those units gets +1/+0 and gains Overwhelm for this phase.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust', 'stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_183 — Rush Clovis

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Official, Separatist

**Rules text:**

> Raid 2
> On Attack: If the defending player controls no ready resources, create a Battle Droid token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_185 — Ziro the Hutt

**Type/Stats:** Unit, cost 5, 2/8  |  Traits: Hutt, Underworld

**Rules text:**

> When Played: For each opponent, you may exhaust a unit that player controls.
> On Attack: For each opponent, you may exhaust a resource that player controls.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_186 — San Hill

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Official, Separatist

**Rules text:**

> Exploit 3 (While playing this card, defeat up to 3 units you control. This card costs 2 resources less for each unit defeated this way.)
> On Attack: For each friendly unit that was defeated this phase, ready a friendly resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_194 — Ahsoka Tano

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> While you control fewer units than an opponent (including this unit), this unit gains Ambush.
> Action [2 resources]: Return this unit and each upgrade on her to their owners' hands.

**Mechanical analysis:** trigger archetype `activated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_197 — Republic Attack Pod

**Type/Stats:** Unit, cost 6, 6/7  |  Traits: Republic, Vehicle, Walker

**Rules text:**

> If you control 3 or more units, this unit costs 1 resource less to play.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_200 — Creative Thinking

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Exhaust a non-unique unit.
> Create a Clone Trooper token.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

