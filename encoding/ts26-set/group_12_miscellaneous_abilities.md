# ts26-set:12 — Miscellaneous abilities

- **Group id (paste this):** `ts26-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_14 | Yoda | Unit | 5 | 4/4 | Sentinel |
| TS26_27 | Fortune and Glory | Unit | 4 | 3/5 | Bounty |
| TS26_34 | Fives | Unit | 6 | 6/6 | Sentinel |
| TS26_36 | Tribunal | Unit | 10 | 6/8 |  |
| TS26_43 | Wartime Refugee | Unit | 1 | 2/3 |  |
| TS26_48 | Vanquish the Legion | Event | 4 |  |  |
| TS26_56 | Galactic Escalation | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TS26_14 — Yoda

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> If you control 7 or more resources, this unit costs 2 resources less to play.
> When Played/When Defeated: Create a Clone Trooper token and give it Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_27 — Fortune and Glory

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: This unit captures a non‑leader unit.
> Bounty — A friendly unit captures a non‑leader unit. (When this unit is defeated or captured, your opponent collects its bounty.) 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_34 — Fives

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Sentinel
> You may have this unit enter play with the ”When Played” abilities of another unit in play.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_36 — Tribunal

**Type/Stats:** Unit, cost 10, 6/8  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> This unit costs 2 resources less to play for each other card you played this phase.
> When Played: Give each other unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_43 — Wartime Refugee

**Type/Stats:** Unit, cost 1, 2/3  |  Traits: Twi'lek

**Rules text:**

> On Attack: An opponent heals 1 damage from their base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_48 — Vanquish the Legion

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Give each enemy ground unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_56 — Galactic Escalation

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Each player resources the top card of their deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

