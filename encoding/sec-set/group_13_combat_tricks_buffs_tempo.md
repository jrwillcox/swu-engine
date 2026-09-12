# sec-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_89 | PreMor Personnel Carrier | Unit | 8 | 6/6 | Overwhelm |
| SEC_91 | Corporate Warmongering | Event | 4 |  |  |
| SEC_95 | Theed Security | Unit | 2 | 2/3 |  |
| SEC_102 | Renowned Dignitaries | Unit | 6 | 5/6 | Overwhelm |
| SEC_104 | Figure of Unity | Upgrade | 3 |  | Overwhelm, Raid, Restore |
| SEC_107 | Chancellor Valorum | Unit | 5 | 3/7 |  |
| SEC_108 | Senator's Aide | Unit | 1 | 0/3 |  |

## Per-card analysis & acceptance criteria

### SEC_89 — PreMor Personnel Carrier

**Type/Stats:** Unit, cost 8, 6/6  |  Traits: Transport, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: Give this unit an Experience token for each ground unit you control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_91 — Corporate Warmongering

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> Give a friendly unit +3/+3 for this phase. Give each other friendly unit +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_95 — Theed Security

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Naboo, Trooper

**Rules text:**

> When Played: If an opponent controls an upgrade, give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_102 — Renowned Dignitaries

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: New Republic, Official

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: Heal 2 damage from your base for each friendly Official unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_104 — Figure of Unity

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> Attach to a <uq> unit.
> Attached unit gains: “While this unit is ready, each other friendly unit gains Overwhelm, Raid 1, and Restore 1.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust', 'keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_107 — Chancellor Valorum

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Official, Republic

**Rules text:**

> When this unit completes an attack: You may disclose CommandCommandCommand (reveal cards from your hand with these aspect icons among them). If you do, put the top card of your deck into play as a resource.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_108 — Senator's Aide

**Type/Stats:** Unit, cost 1, 0/3  |  Traits: Official, Republic

**Rules text:**

> While you have the initiative, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

