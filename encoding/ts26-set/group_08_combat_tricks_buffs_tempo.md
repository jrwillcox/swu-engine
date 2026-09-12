# ts26-set:08 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_30 | Maul | Unit | 4 | 5/4 | Sentinel |
| TS26_31 | Chaotic Diversion | Event | 1 |  |  |
| TS26_35 | Ahsoka's Lightsabers | Upgrade | 4 |  |  |
| TS26_38 | Dooku's Solar Sailer | Unit | 3 | 2/4 |  |
| TS26_40 | Obi-Wan Kenobi | Unit | 3 | 4/4 | Restore |
| TS26_41 | Twilight | Unit | 3 | 3/4 |  |
| TS26_42 | Relief Frigate | Unit | 5 | 3/7 |  |

## Per-card analysis & acceptance criteria

### TS26_30 — Maul

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Force, Underworld

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> When Played: You may attack with another unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_31 — Chaotic Diversion

**Type/Stats:** Event, cost 1  |  Traits: Tactic, Trick

**Rules text:**

> Ready an enemy unit. If you do, it can't attack your base or units you control for this phase.
> Give a Shield token to a friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_35 — Ahsoka's Lightsabers

**Type/Stats:** Upgrade, cost 4  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack/When Defeated: You may give a Shield token to an enemy unit. If you do, the next event you play this phase costs 2 resources less.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_38 — Dooku's Solar Sailer

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played/On Attack: If a base was healed this phase, give an Experience token to another Separatist unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_40 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> Other friendly Republic units gain Restore 1. (When they attack, heal 1 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_41 — Twilight

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: If there are 5 or more cards in your discard pile, heal 3 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'discard'].

**Existing primitives that should suffice:** Heal, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_42 — Relief Frigate

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> When Played: Choose a base. Heal 3 damage from each other base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

