# ts26-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:11`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_77 | Deployed Droideka | Unit | 4 | 4/3 | Ambush |
| TS26_78 | Barriss Offee | Unit | 5 | 5/6 | Hidden |
| TS26_81 | Mislead | Event | 2 |  |  |
| TS26_82 | Evade Arrest | Event | 3 |  |  |
| TS26_83 | Take Aim | Event | 3 |  | Saboteur |
| TS26_84 | Fearless Attack | Event | 4 |  |  |

## Per-card analysis & acceptance criteria

### TS26_77 — Deployed Droideka

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Droid, Separatist

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played: You may pay 2 resources. If you do, give an Experience token and a Shield token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_78 — Barriss Offee

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Hidden (This unit can't be attacked if she was played this phase.)
> When an enemy unit attacks: You may give an Experience token to that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_81 — Mislead

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Give a Shield token to a unit.
> Give a unit –3/–0 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_82 — Evade Arrest

**Type/Stats:** Event, cost 3  |  Traits: Trick

**Rules text:**

> Exhaust any number of non-<uq> units.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_83 — Take Aim

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> This event costs 1 resource less to play for each friendly leader unit.
> Attack with a unit. It gets +2/+0 and gains Saboteur for this attack. (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'ramp', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, CostReduction, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_84 — Fearless Attack

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gets +1/+0 for this attack for each unit controlled by the defending player.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

