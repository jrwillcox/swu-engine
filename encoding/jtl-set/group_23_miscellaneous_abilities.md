# jtl-set:23 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_60 | Desperate Commando | Unit | 2 | 2/2 |  |
| JTL_74 | Close the Shield Gate | Event | 1 |  |  |
| JTL_79 | Out the Airlock | Event | 5 |  |  |
| JTL_82 | Kijimi Patrollers | Unit | 2 | 1/1 |  |
| JTL_83 | Pantoran Starship Thief | Unit | 2 | 2/2 |  |
| JTL_84 | Wingman Victor Two | Unit | 2 | 3/2 | Piloting |
| JTL_87 | TIE Ambush Squadron | Unit | 4 | 2/3 | Ambush |

## Per-card analysis & acceptance criteria

### JTL_60 — Desperate Commando

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Resistance, Trooper

**Rules text:**

> When Defeated: You may give a unit –1/–1 for this phase.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_74 — Close the Shield Gate

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Choose a base. The next time damage would be dealt to it this phase, prevent that damage.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_79 — Out the Airlock

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Give a unit –5/–5 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_82 — Kijimi Patrollers

**Type/Stats:** Unit, cost 2, 1/1  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> When Played: Create a TIE Fighter token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_83 — Pantoran Starship Thief

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Pilot, Underworld

**Rules text:**

> When Played: You may pay 3 resources. If you do, attach this unit as an upgrade to a Fighter or Transport unit without a Pilot on it. Take control of that unit.
> When this upgrade detaches from a unit: That unit's owner takes control of it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_84 — Wingman Victor Two

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Imperial, Pilot

**Rules text:**

> Piloting [1 resource Command Villainy] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: Create a TIE Fighter token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_87 — TIE Ambush Squadron

**Type/Stats:** Unit, cost 4, 2/3  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played/When Defeated: Create a TIE Fighter token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

