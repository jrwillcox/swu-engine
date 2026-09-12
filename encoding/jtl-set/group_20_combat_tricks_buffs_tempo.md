# jtl-set:20 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:20`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_247 | Resistance X-Wing | Unit | 2 | 2/2 |  |
| JTL_253 | Coordinated Front | Event | 2 |  |  |
| JTL_257 | Flanking Fang Fighter | Unit | 3 | 2/3 | Raid |
| JTL_261 | Attack Run | Event | 1 |  |  |
| JTL_262 | Evasive Maneuver | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### JTL_247 — Resistance X-Wing

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> While this unit has a Pilot on it, it gets +1/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_253 — Coordinated Front

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> You may give a ground unit +2/+2 for this phase.
> You may give a space unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_257 — Flanking Fang Fighter

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fighter, Mandalorian, Vehicle

**Rules text:**

> While you control another Fighter unit, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_261 — Attack Run

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with 2 space units (one at a time).

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_262 — Evasive Maneuver

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Exhaust a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

