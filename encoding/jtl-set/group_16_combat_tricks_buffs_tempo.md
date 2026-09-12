# jtl-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_115 | Clone Combat Squadron | Unit | 4 | 3/3 |  |
| JTL_119 | Resupply Carrier | Unit | 6 | 4/5 |  |
| JTL_122 | All Wings Report In | Event | 1 |  |  |
| JTL_135 | Special Forces TIE Fighter | Unit | 2 | 2/3 |  |
| JTL_137 | Vonreg's TIE Interceptor | Unit | 3 | 3/4 | Overwhelm, Raid |
| JTL_138 | Decimator of Dissidents | Unit | 4 | 3/5 | Overwhelm |
| JTL_145 | BB-8 | Unit | 1 | 1/4 | Piloting |

## Per-card analysis & acceptance criteria

### JTL_115 — Clone Combat Squadron

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> This unit gets +1/+1 for each other friendly space unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_119 — Resupply Carrier

**Type/Stats:** Unit, cost 6, 4/5  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may put the top card of your deck into play as a resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_122 — All Wings Report In

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Exhaust up to 2 friendly space units. For each unit exhausted this way, create an X-Wing token.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_135 — Special Forces TIE Fighter

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> When Played: If an opponent controls more space units than you, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_137 — Vonreg's TIE Interceptor

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> While this unit has 4 or more power, it gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)
> While this unit has 6 or more power, it gains Raid 1. (It gets +1/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_138 — Decimator of Dissidents

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> If you dealt indirect damage this phase, this unit costs 1 resource less to play.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_145 — BB-8

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Droid, Pilot, Resistance

**Rules text:**

> Piloting [1 resource Aggression Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: You may pay 2 resources. If you do, ready a Resistance unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

