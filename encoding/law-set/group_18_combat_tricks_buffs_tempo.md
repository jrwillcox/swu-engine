# law-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:18`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_202 | Commence the Festivities | Event | 1 |  | Saboteur |
| LAW_223 | Rose Tico | Unit | 5 | 5/5 |  |
| LAW_227 | Rookie Rocket-jumper | Unit | 1 | 2/1 |  |
| LAW_233 | Galen Erso | Unit | 3 | 0/5 | Raid, Saboteur |
| LAW_257 | Hidden Hand Supplier | Unit | 1 | 1/2 |  |

## Per-card analysis & acceptance criteria

### LAW_202 — Commence the Festivities

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Attack with a unit. It gains Saboteur for this attack. If you control fewer resources than an opponent, it gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_223 — Rose Tico

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Resistance

**Rules text:**

> If you control a non-<uq> unit, this unit enters play ready.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_227 — Rookie Rocket-jumper

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Twi'lek, Underworld

**Rules text:**

> When Played: You may pay 1 resource. If you do, give a Shield token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_233 — Galen Erso

**Type/Stats:** Unit, cost 3, 0/5  |  Traits: Imperial

**Rules text:**

> When Played: You may have an opponent take control of this unit.
> Enemy units gain Raid 1 and Saboteur.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_257 — Hidden Hand Supplier

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Underworld

**Rules text:**

> When Played: You may pay 1 resource. If you do, give an Experience token to another unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

