# ic27-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_92 | Resupply Carrier | Unit | 6 | 4/5 |  |
| IC27_99 | Eighth Brother | Unit | 2 | 3/1 |  |
| IC27_101 | General Hux | Unit | 3 | 3/4 | Overwhelm |
| IC27_103 | Grand Inquisitor | Unit | 4 | 3/6 | Raid, Saboteur |
| IC27_106 | Kylo Ren | Unit | 5 | 5/5 | Hidden |
| IC27_115 | Poe Dameron | Unit | 2 | 2/4 |  |
| IC27_120 | Rey | Unit | 5 | 6/6 |  |

## Per-card analysis & acceptance criteria

### IC27_92 — Resupply Carrier

**Type/Stats:** Unit, cost 6, 4/5  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_99 — Eighth Brother

**Type/Stats:** Unit, cost 2, 3/1  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> When Defeated: You may ready an Imperial unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_101 — General Hux

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: First Order, Official

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> Each other friendly First Order unit gets +1/+0 and gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_103 — Grand Inquisitor

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> While this unit is damaged, he gains Raid 3 and Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_106 — Kylo Ren

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: First Order, Force

**Rules text:**

> Hidden
> On Attack: If this is the first time this unit has attacked this phase, ready him.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_115 — Poe Dameron

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Resistance

**Rules text:**

> When you play another Resistance card: This unit gets +1/+0 for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_120 — Rey

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Force

**Rules text:**

> Action [1 resource, discard a card from your hand]: Attack with a unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

