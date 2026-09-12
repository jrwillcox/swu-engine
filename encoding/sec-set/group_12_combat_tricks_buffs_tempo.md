# sec-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_59 | Senate Warden | Unit | 2 | 2/2 |  |
| SEC_63 | Rotunda Senate Guards | Unit | 4 | 4/5 | Sentinel |
| SEC_64 | Congress of Malastare | Unit | 5 | 5/5 |  |
| SEC_65 | Nala Se | Unit | 5 | 4/7 |  |
| SEC_69 | Nimble Prowess | Upgrade | 1 |  |  |
| SEC_71 | Disciples' Devotion | Upgrade | 3 |  | Sentinel |
| SEC_74 | Relief Request | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SEC_59 — Senate Warden

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Republic, Trooper

**Rules text:**

> When Defeated: You may disclose Vigilance (reveal a card from your hand with this aspect icon). If you do, give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_63 — Rotunda Senate Guards

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Republic, Trooper

**Rules text:**

> While this unit is undamaged, it gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_64 — Congress of Malastare

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Official, Republic

**Rules text:**

> The first upgrade you play each phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_65 — Nala Se

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Kaminoan

**Rules text:**

> On Attack: You may disclose VigilanceVigilance (reveal cards from your hand with these aspect icons among them). If you do, heal up to 4 damage from among other units.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_69 — Nimble Prowess

**Type/Stats:** Upgrade, cost 1  |  Traits: Innate

**Rules text:**

> Attach to a friendly unit.
> When Played: You may exhaust a unit in attached unit's arena.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_71 — Disciples' Devotion

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> While attached unit is exhausted, it gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_74 — Relief Request

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> Heal 3 damage from a unit.
> You may disclose Vigilance (reveal a card from your hand with this aspect icon). If you do, heal 3 damage from another unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

