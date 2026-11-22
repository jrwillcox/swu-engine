# hmw-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_90 | Opee Sea Killer | Unit | 5 | 5/6 | Grit |
| HMW_91 | Pelta Relief Frigate | Unit | 5 | 5/4 |  |
| HMW_92 | Starlit Purrgil | Unit | 6 | 4/5 | Restore |
| HMW_98 | Resonate | Event | 1 |  |  |
| HMW_104 | Garnac | Unit | 1 | 3/1 | Hidden |
| HMW_107 | Stormtrooper Patrol | Unit | 3 | 2/4 | Sentinel |
| HMW_111 | Invasion Lander | Unit | 6 | 3/7 |  |

## Per-card analysis & acceptance criteria

### HMW_90 — Opee Sea Killer

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Creature

**Rules text:**

> While you control a Naboo base, this unit gains Grit. (This unit gets +1/+0 for each damage on it.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_91 — Pelta Relief Frigate

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: Heal 2 damage from a friendly base and 2 damage from a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_92 — Starlit Purrgil

**Type/Stats:** Unit, cost 6, 4/5  |  Traits: Creature

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> When Played: You may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_98 — Resonate

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> If a friendly non-leader unit shares a Trait with a friendly leader, heal 4 damage from a unit or base.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_104 — Garnac

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Underworld

**Rules text:**

> While an opponent controls a <uq> unit, this unit gains Hidden.
> When Attack Ends: You may attack with another unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_107 — Stormtrooper Patrol

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Imperial, Trooper

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> While you control another unit that costs 3 or more, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_111 — Invasion Lander

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played: Give each other friendly unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

