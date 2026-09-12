# jtl-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_178 | Face Off | Event | 3 |  |  |
| JTL_179 | Koiogran Turn | Event | 3 |  |  |
| JTL_182 | Rampart | Unit | 2 | 3/3 |  |
| JTL_188 | Moff Gideon | Unit | 4 | 5/4 |  |
| JTL_192 | In Debt to Crimson Dawn | Upgrade | 2 |  |  |
| JTL_193 | I Have You Now | Event | 1 |  |  |
| JTL_195 | Cat and Mouse | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_178 — Face Off

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> If no player has taken the initiative this phase, you may ready an enemy unit. If you do, ready a friendly unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_179 — Koiogran Turn

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Ready a Fighter or Transport unit with 6 or less power.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_182 — Rampart

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> This unit doesn't ready during the regroup phase unless its power is 4 or more.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_188 — Moff Gideon

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Imperial, Official

**Rules text:**

> When this unit deals combat damage to an opponent's base: Each unit that opponent plays this phase costs 1 resource more.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_192 — In Debt to Crimson Dawn

**Type/Stats:** Upgrade, cost 2  |  Traits: Condition

**Rules text:**

> When attached unit readies: Exhaust it unless its controller pays 2 resources.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_193 — I Have You Now

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a Vehicle unit. Prevent all damage that would be dealt to it during this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_195 — Cat and Mouse

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Exhaust an enemy unit. If you do, ready a friendly unit in the same arena with power equal to or less than that enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

