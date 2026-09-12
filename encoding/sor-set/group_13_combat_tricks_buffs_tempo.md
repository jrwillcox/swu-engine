# sor-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_82 | Emperor's Royal Guard | Unit | 3 | 3/4 | Sentinel |
| SOR_94 | Bail Organa | Unit | 1 | 1/2 |  |
| SOR_100 | Wedge Antilles | Unit | 5 | 5/5 | Ambush |
| SOR_106 | Attack Pattern Delta | Event | 3 |  |  |
| SOR_108 | Vanguard Infantry | Unit | 1 | 1/2 |  |
| SOR_109 | Colonel Yularen | Unit | 2 | 2/3 |  |
| SOR_110 | Frontline Shuttle | Unit | 2 | 1/3 |  |

## Per-card analysis & acceptance criteria

### SOR_82 — Emperor's Royal Guard

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Imperial

**Rules text:**

> While you control an OFFICIAL unit, this unit gains Sentinel.
> 
> While you control Emperor Palpatine (as a leader or unit), this unit gets +0/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_94 — Bail Organa

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Official, Rebel

**Rules text:**

> Action [Exhaust]: Give an Experience token to another friendly unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_100 — Wedge Antilles

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Rebel

**Rules text:**

> Each friendly VEHICLE unit gets +1/+1 and gains Ambush. (After you play that unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_106 — Attack Pattern Delta

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give a friendly unit +3/+3 for this phase.
> 
> Give another friendly unit +2/+2 for this phase.
> 
> Give a third friendly unit +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_108 — Vanguard Infantry

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Trooper

**Rules text:**

> When Defeated: You may give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_109 — Colonel Yularen

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Imperial, Official

**Rules text:**

> When you play a [Command] unit (including this one): Heal 1 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_110 — Frontline Shuttle

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Transport, Vehicle

**Rules text:**

> Action [defeat this unit]: Attack with a unit, even if it's exhausted. It can't attack bases for this attack.

**Mechanical analysis:** trigger archetype `activated`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

