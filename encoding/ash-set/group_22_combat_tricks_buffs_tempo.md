# ash-set:22 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_224 | Elzar Mann | Unit | 6 | 3/7 |  |
| ASH_227 | Heightened Awareness | Upgrade | 1 |  |  |
| ASH_228 | Preparation | Upgrade | 1 |  |  |
| ASH_231 | Diplomatic Pageantry | Event | 1 |  |  |
| ASH_233 | Keep Them Talking | Event | 2 |  |  |
| ASH_234 | Masterstroke | Event | 2 |  |  |
| ASH_237 | Mouse Droid | Unit | 1 | 1/1 | Raid |

## Per-card analysis & acceptance criteria

### ASH_224 — Elzar Mann

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Force, Jedi

**Rules text:**

> While you control a Force leader, this unit enters play ready.
> When Played: Distribute up to 5 Advantage tokens among other friendly units. Then, an opponent searches twice that many cards from the top of their deck for an event, reveals it, and draws it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_227 — Heightened Awareness

**Type/Stats:** Upgrade, cost 1  |  Traits: Force

**Rules text:**

> Attached unit gains: “When the regroup phase starts: Give an Advantage token to this unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_228 — Preparation

**Type/Stats:** Upgrade, cost 1  |  Traits: Plan

**Rules text:**

> When Played: Exhaust attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_231 — Diplomatic Pageantry

**Type/Stats:** Event, cost 1  |  Traits: Law

**Rules text:**

> Exhaust a friendly unit and an enemy unit. If you do, give 2 Advantage tokens to that friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_233 — Keep Them Talking

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Exhaust up to 2 units that each cost 3 or less.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_234 — Masterstroke

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gets +1/+0 for this attack for each unit the defending player controls in its arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_237 — Mouse Droid

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Droid, Imperial

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: The next Imperial unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

