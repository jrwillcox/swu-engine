# hmw-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_39 | Mother Talzin | Unit | 3 | 3/4 | Raid, Restore |
| HMW_42 | Dooku | Unit | 8 | 8/7 | Overwhelm |
| HMW_44 | Ima-Gun Di | Unit | 3 | 5/3 |  |
| HMW_50 | Low Altitude Combat | Event | 2 |  |  |
| HMW_52 | A'Koba | Unit | 2 | 1/4 | Raid |
| HMW_56 | Yoda | Unit | 3 | 4/4 | Hidden |
| HMW_63 | Rho Medical Shuttle | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### HMW_39 — Mother Talzin

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Night

**Rules text:**

> Raid 1
> Each other friendly unit gains Restore 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_42 — Dooku

**Type/Stats:** Unit, cost 8, 8/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Overwhelm
> When Played: You may ready another unit. If you do, heal damage from a base equal to that unit's cost.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'ready_exhaust'].

**Existing primitives that should suffice:** Heal, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_44 — Ima-Gun Di

**Type/Stats:** Unit, cost 3, 5/3  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Defeated: If you control fewer resources than an opponent, you may resource a card from your hand. If you do, resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_50 — Low Altitude Combat

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Move a space unit to the ground arena (it's now a ground unit). If you do, you may attack with a ground unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_52 — A'Koba

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Tusken

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: Give a unit +2/+0 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_56 — Yoda

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Force, Fringe, Jedi

**Rules text:**

> Hidden
> When Defeated: You may put this card from your discard pile on top of your deck. If you do, heal 2 damage from a base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['heal', 'discard'].

**Existing primitives that should suffice:** Heal, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_63 — Rho Medical Shuttle

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> When Played/On Attack: You may heal 1 damage from another unit or base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

