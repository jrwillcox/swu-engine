# jtl-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_146 | Massassi Tactical Officer | Unit | 1 | 0/4 |  |
| JTL_150 | Biggs Darklighter | Unit | 3 | 3/4 | Grit, Overwhelm, Piloting |
| JTL_157 | Relentless Firespray | Unit | 6 | 4/6 |  |
| JTL_160 | Supporting Eta-2 | Unit | 2 | 2/2 |  |
| JTL_161 | Captain Tarkin | Unit | 3 | 2/5 | Overwhelm |
| JTL_163 | AT-DP Occupier | Unit | 4 | 3/4 | Overwhelm |
| JTL_164 | Cham Syndulla | Unit | 4 | 5/4 |  |

## Per-card analysis & acceptance criteria

### JTL_146 — Massassi Tactical Officer

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Rebel

**Rules text:**

> Action [Exhaust]: Attack with a Fighter unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_150 — Biggs Darklighter

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Pilot, Rebel

**Rules text:**

> Piloting [1 resource Aggression Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> If attached unit is a Fighter, it gains Overwhelm.
> If attached unit is a Transport, it gets +0/+1.
> If attached unit is a Speeder, it gains Grit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_157 — Relentless Firespray

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> On Attack: Ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_160 — Supporting Eta-2

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> On Attack: You may give a ground unit +2/+0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_161 — Captain Tarkin

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Official, Republic

**Rules text:**

> Each friendly Vehicle unit gets +1/+0 and gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_163 — AT-DP Occupier

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Imperial, Vehicle, Walker

**Rules text:**

> This unit costs 1 resource less to play for each damaged ground unit.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_164 — Cham Syndulla

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Rebel, Twi'lek

**Rules text:**

> When Played: If an opponent controls more resources than you, you may put the top card of your deck into play as a resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

