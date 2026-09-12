# law-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_133 | Lost and Forgotten | Event | 6 |  |  |
| LAW_139 | Admiral Motti | Unit | 5 | 4/5 |  |
| LAW_140 | Intimidator | Unit | 11 | 11/11 |  |
| LAW_144 | Phantom | Unit | 2 | 2/2 |  |
| LAW_148 | Smuggler's YT-2400 | Unit | 5 | 4/5 | Ambush |
| LAW_150 | Fulcrum | Upgrade | 5 |  |  |
| LAW_151 | Profiteering Hunter | Unit | 1 | 1/3 |  |

## Per-card analysis & acceptance criteria

### LAW_133 — Lost and Forgotten

**Type/Stats:** Event, cost 6  |  Traits: Innate

**Rules text:**

> Defeat a non-leader unit. If you do, heal 3 damage from your base.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'defeat'].

**Existing primitives that should suffice:** Heal, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_139 — Admiral Motti

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Imperial, Official

**Rules text:**

> Friendly leader units get +2/+2.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_140 — Intimidator

**Type/Stats:** Unit, cost 11, 11/11  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: Return any number of friendly resources to their owners' hands. For each resource returned this way, create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_144 — Phantom

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Rebel, Spectre, Transport, Vehicle

**Rules text:**

> When Played: You may play a Heroism unit from your hand (paying its cost) and give an Experience token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_148 — Smuggler's YT-2400

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played: You may pay 1 resource. If you do, this unit gets +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'ramp'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_150 — Fulcrum

**Type/Stats:** Upgrade, cost 5  |  Traits: Rebel

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains the Rebel trait and “Each other friendly Rebel unit gets +2/+2.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_151 — Profiteering Hunter

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: Another friendly unit gets +1/+1 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

