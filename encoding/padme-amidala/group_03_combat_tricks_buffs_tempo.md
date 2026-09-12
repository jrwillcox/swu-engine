# padme-amidala:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `padme-amidala:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_129 | With Thunderous Applause | Event | 3 |  |  |
| SEC_201 | Anakin Skywalker | Unit | 3 | 3/4 | Hidden, Raid |
| SEC_234 | Bog Down in Procedure | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_129 — With Thunderous Applause

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Give a unit +2/+2 for this phase.
> You may disclose Command (reveal a card from your hand with this aspect icon). If you do, give another unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_201 — Anakin Skywalker

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> Hidden (This unit can't be attacked if he was played this phase.)
> While you control Padmé Amidala (as a leader or unit), this unit gains Raid 2.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_234 — Bog Down in Procedure

**Type/Stats:** Event, cost 3  |  Traits: Law

**Rules text:**

> Exhaust a unit.
> You may disclose Cunning (reveal a card from your hand with this aspect icon). If you do, exhaust another unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

