# ts26-set:06 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_1 | Count Dooku | Leader | 7 | 6/7 | Restore |
| TS26_2 | Anakin Skywalker | Leader | 5 | 4/5 | Sentinel |
| TS26_4 | Padmé Amidala | Leader | 6 | 5/6 |  |
| TS26_5 | Savage Opress | Leader | 6 | 3/7 | Overwhelm, Raid |
| TS26_6 | Rex | Leader | 6 | 5/6 |  |
| TS26_7 | Asajj Ventress | Leader | 5 | 3/5 | Hidden |
| TS26_9 | First Battle Memorial | Base |  | None/27 |  |

## Per-card analysis & acceptance criteria

### TS26_1 — Count Dooku

**Type/Stats:** Leader, cost 7, 6/7  |  Traits: Force, Official, Separatist, Sith

**Rules text:**

> Action [Exhaust]: Choose 2 players. They each heal 1 damage from their base and create a Battle Droid token.
> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> On Attack: Create 2 Battle Droid tokens.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_2 — Anakin Skywalker

**Type/Stats:** Leader, cost 5, 4/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust]: If 2 or more friendly units entered play this phase (including tokens and leaders), give a Shield token to 1 of them.
> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> On Attack: Give a Shield token to another friendly unit that entered play this phase.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_4 — Padmé Amidala

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Naboo, Official, Republic

**Rules text:**

> Action [Exhaust]: If 2 or more friendly units entered play this phase (including tokens and leaders) , attack with 1 of them, even if it's exhausted. It can't attack bases for this attack.
> When Attack Ends: You may attack with another friendly unit that entered play this phase, even if it's exhausted. It can't attack bases for this attack.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_5 — Savage Opress

**Type/Stats:** Leader, cost 6, 3/7  |  Traits: Force, Underworld

**Rules text:**

> Each friendly unit with the most power among friendly units gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)
> Raid 3 (This unit gets +3/+0 while attacking.)
> Overwhelm
> Each other friendly unit gains Overwhelm.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_6 — Rex

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Clone, Trooper

**Rules text:**

> Action [Exhaust, ready an exhausted enemy unit]: The next event you play this phase costs 1 resource less.
> On Attack: You may ready an exhausted enemy unit. If you do, the next event you play this phase costs 2 resources less.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_7 — Asajj Ventress

**Type/Stats:** Leader, cost 5, 3/5  |  Traits: Force, Separatist, Sith

**Rules text:**

> Action [Exhaust]: Attack with a token unit. It gets +1/+0 for this attack.
> Hidden (This unit can't be attacked if she was deployed this phase.) 
> While you've attacked with a token unit this phase, this unit gets +2/+0.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_9 — First Battle Memorial

**Type/Stats:** Base

**Rules text:**

> Epic Action: For each friendly leader unit, give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

