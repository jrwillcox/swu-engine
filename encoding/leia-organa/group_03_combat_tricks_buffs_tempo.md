# leia-organa:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `leia-organa:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_10 | Leia Organa | Leader | 5 | 2/2 | Overwhelm |
| LAW_35 | Ezra Bridger | Unit | 4 | 4/5 | Raid |
| LAW_37 | Han Solo | Unit | 1 | 1/1 | Shielded |
| LAW_67 | Jyn Erso | Unit | 2 | 2/2 |  |
| SEC_93 | C-3PO | Unit | 1 | 1/3 |  |
| SEC_103 | Mon Mothma | Unit | 7 | 5/8 | Restore |
| LAW_105 | Cinta Kaz | Unit | 3 | 3/5 | Sentinel |

## Per-card analysis & acceptance criteria

### LAW_10 — Leia Organa

**Type/Stats:** Leader, cost 5, 2/2  |  Traits: Rebel

**Rules text:**

> Action [2 resources, Exhaust]: For this phase, give a unit +1/+1 for each different aspect it has.
> Overwhelm
> When Deployed: Choose a unit. Give an Experience token to that unit for each different aspect among units you control.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'stat_buff'].

**Existing primitives that should suffice:** GiveToken, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_35 — Ezra Bridger

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Force, Rebel, Spectre

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: You may heal 2 damage from a unit. If you control a Aggression or Cunning unit, you may heal 4 damage from a unit instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_37 — Han Solo

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Rebel

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> On Attack: Give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_67 — Jyn Erso

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Rebel

**Rules text:**

> When Played: Either give an Experience token to a unit or exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_93 — C-3PO

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Republic

**Rules text:**

> Action [Exhaust, return this unit to its owner's hand]: Give a unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_103 — Mon Mothma

**Type/Stats:** Unit, cost 7, 5/8  |  Traits: Official, Rebel

**Rules text:**

> Restore 3
> When Played: You may attack with any number of other units (one at a time), even if those units are exhausted. They can't attack bases for these attacks.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_105 — Cinta Kaz

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Rebel

**Rules text:**

> While this unit is upgraded, she gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

