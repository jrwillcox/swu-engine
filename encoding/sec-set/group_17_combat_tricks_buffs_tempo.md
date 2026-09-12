# sec-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_215 | Emissary's Sheathipede | Unit | 2 | 2/4 |  |
| SEC_216 | Regulations Bureaucrat | Unit | 2 | 0/5 |  |
| SEC_219 | Ebon Hawk | Unit | 3 | 3/3 |  |
| SEC_220 | Hired Slicer | Unit | 3 | 3/4 |  |
| SEC_221 | Unruly Astromech | Unit | 3 | 3/2 | Hidden |
| SEC_225 | Synara San | Unit | 7 | 7/7 | Hidden |
| SEC_228 | Accelerate Our Plans | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SEC_215 — Emissary's Sheathipede

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Defeated: Each opponent may ready a resource.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_216 — Regulations Bureaucrat

**Type/Stats:** Unit, cost 2, 0/5  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Exhaust a resource.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_219 — Ebon Hawk

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> On Attack: You may disclose Heroism and/or Villainy. If you disclosed Heroism, this unit gets +2/+0 for this attack. If you disclosed Villainy, give the defender –4/–0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_220 — Hired Slicer

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fringe

**Rules text:**

> On Attack: Reveal the top 2 cards of a deck. If you do, you may exhaust a unit that shares a Trait with one of those cards. Put those cards on the bottom of that deck in a random order.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_221 — Unruly Astromech

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Droid

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When Defeated: Exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_225 — Synara San

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Underworld

**Rules text:**

> Hidden
> On Attack: For each friendly unit, ready a friendly resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_228 — Accelerate Our Plans

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Exhaust a friendly unit. If you do, attack with another unit. It gets +3/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

