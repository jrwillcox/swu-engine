# hmw-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_141 | Rex | Unit | 5 | 5/6 |  |
| HMW_142 | Wookiee Rangers | Unit | 5 | 5/6 | Sentinel |
| HMW_145 | Origin Tree Shyyyo | Unit | 6 | 4/8 | Restore |
| HMW_149 | Log Trap | Event | 2 |  |  |
| HMW_151 | Overgrowth | Event | 5 |  |  |
| HMW_164 | Chief Chirpa | Unit | 2 | 1/5 |  |
| HMW_165 | Commandeered Tour Shuttle | Unit | 3 | 2/2 |  |

## Per-card analysis & acceptance criteria

### HMW_141 — Rex

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Clone, Fringe

**Rules text:**

> Friendly units with no abilities get +1/+1.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_142 — Wookiee Rangers

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Wookiee

**Rules text:**

> While you control another Wookiee unit or a Kashyyyk base, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_145 — Origin Tree Shyyyo

**Type/Stats:** Unit, cost 6, 4/8  |  Traits: Creature

**Rules text:**

> Restore 1
> While you control a Kashyyyk base, the first, second, and third units you play each round cost 1 resource less, 2 resources less, and 3 resources less, respectively.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_149 — Log Trap

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Attack with a friendly unit. Then attack with it again, even if it's exhausted. It can't attack bases for the second attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_151 — Overgrowth

**Type/Stats:** Event, cost 5  |  Traits: Disaster

**Rules text:**

> If you control a Kashyyyk base, a friendly unit deals damage equal to its power to an enemy unit.
> Resource this card.

**Mechanical analysis:** trigger archetype `event`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_164 — Chief Chirpa

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Ewok

**Rules text:**

> This unit gets +1/+0 for each other friendly Ewok unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_165 — Commandeered Tour Shuttle

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Played: You may ready another unit with 3 or less power.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

