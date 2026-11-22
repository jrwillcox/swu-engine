# hmw-set:19 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_209 | Corona Squadron X-Wing | Unit | 2 | 2/2 |  |
| HMW_210 | Sol | Unit | 2 | 2/2 | Sentinel, Shielded |
| HMW_211 | Tech | Unit | 3 | 3/5 |  |
| HMW_212 | The Chieftain | Unit | 3 | 2/5 | Raid |
| HMW_214 | Phee Genoa | Unit | 4 | 5/4 | Hidden |
| HMW_228 | Lakeside Shaaks | Unit | 4 | 4/4 |  |
| HMW_230 | Raiding Party | Unit | 5 | 0/6 | Raid |

## Per-card analysis & acceptance criteria

### HMW_209 — Corona Squadron X-Wing

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, New Republic, Vehicle

**Rules text:**

> On Attack: You may ready a resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_210 — Sol

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Jedi

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> On Attack: This unit gains Sentinel for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_211 — Tech

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Clone

**Rules text:**

> When this unit is dealt damage and survives: You may exhaust a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_212 — The Chieftain

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Tusken

**Rules text:**

> This unit gains Raid 1 for each other friendly Tusken unit.
> While a friendly Tusken unit is defending, it gets +1/+0 for each Raid it has.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_214 — Phee Genoa

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Underworld

**Rules text:**

> Hidden
> When an enemy leader deploys: Its controller may pay 2 resources. If they don't, exhaust that leader.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_228 — Lakeside Shaaks

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Creature

**Rules text:**

> When Played: Ready a friendly resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_230 — Raiding Party

**Type/Stats:** Unit, cost 5, 0/6  |  Traits: Tusken

**Rules text:**

> Raid 6 (This unit gets +6/+0 while attacking.)
> When Played: If you control another Tusken unit or a Tatooine base, you may exhaust a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

