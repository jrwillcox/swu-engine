# p26-set:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `p26-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_246 | Garnac | Unit | 1 | 3/1 | Hidden |
| P26_248 | Grand Inquisitor | Unit | 4 | 3/6 | Raid, Saboteur |
| P26_250 | Victor Squadron | Unit | 6 | 5/5 |  |
| P26_251 | Luke Skywalker | Unit | 1 | 1/3 | Raid |
| P26_264 | Ima-Gun Di | Unit | 3 | 5/3 |  |
| P26_265 | Nuvo Vindi | Unit | 3 | 1/4 |  |
| P26_271 | Luminara Unduli | Unit | 7 | 7/7 |  |

## Per-card analysis & acceptance criteria

### P26_246 — Garnac

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Underworld

**Rules text:**

> While an opponent controls a <uq> unit, this unit gains Hidden.
> When Attack Ends: You may attack with another unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_248 — Grand Inquisitor

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> While this unit is damaged, he gains Raid 3 and Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_250 — Victor Squadron

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> This unit enters play ready.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_251 — Luke Skywalker

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Force, Fringe

**Rules text:**

> Raid 1
> While it's the first round of the game, this unit enters play ready.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_264 — Ima-Gun Di

**Type/Stats:** Unit, cost 3, 5/3  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Defeated: If you control fewer resources than an opponent, you may resource a card from your hand. If you do, resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_265 — Nuvo Vindi

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Separatist

**Rules text:**

> When Played: You may give a Weakness token to a unit.
> When an enemy unit with a Weakness token on it is defeated: You may give a Weakness token to a unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** weakness-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_271 — Luminara Unduli

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> When you play a unit : You may attack with a unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

