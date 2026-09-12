# sec-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_18 | DJ | Leader | 6 | 4/6 | Saboteur |
| SEC_29 | Zam Wesell | Unit | 2 | 1/5 | Grit |
| SEC_32 | Kylo Ren's Command Shuttle | Unit | 4 | 3/5 | Sentinel |
| SEC_40 | Emergency Powers | Event | 1 |  |  |
| SEC_41 | Populist Advisor | Unit | 1 | 1/4 | Sentinel |
| SEC_47 | Coronet | Unit | 5 | 4/6 | Restore |
| SEC_54 | Exiled from the Force | Upgrade | 1 |  | Grit |

## Per-card analysis & acceptance criteria

### SEC_18 — DJ

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Choose a friendly unit. If you do, play a unit from your hand. It costs 1 resource less. The chosen unit captures it. (When Played abilities resolve after the unit is captured.)
> Saboteur
> Friendly units that are rescued enter play ready.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_29 — Zam Wesell

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> While this unit is upgraded, she gains Grit. (She gets +1/+0 for each damage on her.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_32 — Kylo Ren's Command Shuttle

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: First Order, Transport, Vehicle

**Rules text:**

> Each friendly ground unit with Sentinel gets +0/+2.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_40 — Emergency Powers

**Type/Stats:** Event, cost 1  |  Traits: Law

**Rules text:**

> Choose a non-leader unit and pay any number of resources. For each resource paid this way, give an Experience token to the chosen unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_41 — Populist Advisor

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: New Republic, Official

**Rules text:**

> When an enemy unit deals combat damage to your base: This unit gains Sentinel for this phase. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_47 — Coronet

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> Each other friendly unit gains Restore 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_54 — Exiled from the Force

**Type/Stats:** Upgrade, cost 1  |  Traits: Condition

**Rules text:**

> Attached unit loses the Force trait and all abilities except for Grit.
> Attached unit gains Grit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

