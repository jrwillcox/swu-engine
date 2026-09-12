# lof-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_106 | Acclamator Assault Ship | Unit | 7 | 5/8 |  |
| LOF_118 | Terentatek | Unit | 5 | 5/5 | Ambush |
| LOF_124 | Niman Strike | Event | 1 |  |  |
| LOF_126 | Overpower | Event | 3 |  | Overwhelm |
| LOF_127 | Rampage | Event | 3 |  |  |
| LOF_135 | Scythe | Unit | 4 | 3/5 |  |
| LOF_150 | Cin Drallig | Unit | 8 | 5/6 |  |

## Per-card analysis & acceptance criteria

### LOF_106 — Acclamator Assault Ship

**Type/Stats:** Unit, cost 7, 5/8  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> On Attack: You may give another unit +5/+5 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_118 — Terentatek

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Creature

**Rules text:**

> While an opponent controls a Force unit, this unit gains Ambush. (When you play this unit, it may attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_124 — Niman Strike

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Attack with a Force unit, even if it's exhausted. It gets +1/+0 and can't attack bases for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_126 — Overpower

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> Give a unit +3/+3 and Overwhelm for this phase. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_127 — Rampage

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> Each friendly Creature unit gets +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_135 — Scythe

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Imperial, Inquisitor, Transport, Vehicle

**Rules text:**

> On Attack: You may give another friendly Inquisitor unit +2/+0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_150 — Cin Drallig

**Type/Stats:** Unit, cost 8, 5/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: You may play a Lightsaber upgrade from your hand for free on this unit. If you do, ready him.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

