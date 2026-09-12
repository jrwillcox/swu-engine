# jtl-set:19 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_199 | Blade Squadron B-Wing | Unit | 3 | 3/3 |  |
| JTL_202 | Black Squadron Scout Wing | Unit | 5 | 4/6 |  |
| JTL_206 | Fly Casual | Event | 1 |  |  |
| JTL_211 | Independent Smuggler | Unit | 1 | 1/1 | Piloting, Raid |
| JTL_228 | Barrel Roll | Event | 1 |  |  |
| JTL_231 | Punch It | Event | 1 |  |  |
| JTL_238 | Sith Trooper | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### JTL_199 — Blade Squadron B-Wing

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Played: If another player controls 3 or more exhausted units, give a Shield token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_202 — Black Squadron Scout Wing

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> When you play an upgrade on this unit: You may attack with this unit. It gets +1/+0 for this attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_206 — Fly Casual

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Ready a Vehicle unit. It can't attack bases for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_211 — Independent Smuggler

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Pilot, Underworld

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> Piloting [1 resource Cunning] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains Raid 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_228 — Barrel Roll

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a space unit. After completing this attack, you may exhaust a space unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust', 'attack_grant'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_231 — Punch It

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a Vehicle unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_238 — Sith Trooper

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: First Order, Sith, Trooper

**Rules text:**

> On Attack: This unit gets +1/+0 for this attack for each damaged unit the defending player controls.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

