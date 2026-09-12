# ts26-set:10 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ts26-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_55 | Jedi General | Unit | 5 | 2/3 | Ambush |
| TS26_59 | Brothers | Event | 3 |  |  |
| TS26_60 | Take Charge | Event | 3 |  |  |
| TS26_61 | Encircle | Event | 5 |  |  |
| TS26_63 | Rex's DC-17s | Upgrade | 3 |  |  |
| TS26_75 | Jango Fett | Unit | 5 | 5/5 | Ambush |
| TS26_76 | Wartime Profiteer | Unit | 2 | 3/3 |  |

## Per-card analysis & acceptance criteria

### TS26_55 — Jedi General

**Type/Stats:** Unit, cost 5, 2/3  |  Traits: Force, Jedi, Republic

**Rules text:**

> Ambush
> When Played: For each Republic leader you control (as a leader or unit), create a Clone Trooper token and give an Experience token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_59 — Brothers

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> Attack with up to 2 <uq> units (one at a time). Prevent all combat damage that would be dealt to each of them for these attacks.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_60 — Take Charge

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> This event costs 1 resource less to play for each friendly leader unit.
> Give an Experience token to each of up to 3 units.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_61 — Encircle

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> This event costs 1 resource less to play for each friendly unit.
> A friendly unit captures an enemy non-leader unit in the same arena. (Put the captured card facedown under that unit until that unit leaves play.)

**Mechanical analysis:** trigger archetype `event`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_63 — Rex's DC-17s

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “When an enemy unit readies during the action phase: Ready this unit. Use this ability only once each round.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_75 — Jango Fett

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Bounty Hunter, Separatist

**Rules text:**

> While an enemy unit has attacked your base this phase, this unit gains Ambush. (When you play this unit, he may attack an enemy unit.)
> On Attack: Give an enemy unit –3/–0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_76 — Wartime Profiteer

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Underworld

**Rules text:**

> When Defeated: Each opponent may ready a resource.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

