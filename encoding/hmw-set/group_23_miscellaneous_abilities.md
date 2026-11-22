# hmw-set:23 — Miscellaneous abilities

- **Group id (paste this):** `hmw-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_154 | Dooku's Solar Sailer | Unit | 3 | 3/3 |  |
| HMW_161 | Raze to Ruin | Event | 2 |  |  |
| HMW_162 | Teebo | Unit | 1 | 3/1 | Hidden |
| HMW_192 | Volley Fire | Event | 1 |  | Raid |
| HMW_218 | New Tactics | Event | 5 |  |  |
| HMW_221 | Teeka | Unit | 1 | 2/2 | Sentinel |
| HMW_223 | Therm Scissorpunch | Unit | 2 | 5/5 |  |

## Per-card analysis & acceptance criteria

### HMW_154 — Dooku's Solar Sailer

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played: If you control a unit that costs 1 or less, each opponent discards a card from their hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_161 — Raze to Ruin

**Type/Stats:** Event, cost 2  |  Traits: Disaster, Plan

**Rules text:**

> Each player discards all but 3 cards from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_162 — Teebo

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Ewok

**Rules text:**

> Hidden (This unit can't be attacked if he was played this phase.)
> Other friendly Ewok units gain Hidden.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_192 — Volley Fire

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> A friendly unit deals damage equal to its Raid to an enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_218 — New Tactics

**Type/Stats:** Event, cost 5  |  Traits: Learned, Tactic

**Rules text:**

> Choose a non-leader unit. Its owner puts it on the top or bottom of their deck. (It isn't defeated.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_221 — Teeka

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Jawa

**Rules text:**

> When Played: Choose one:
> Give a unit Sentinel for this phase.
> A unit loses Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_223 — Therm Scissorpunch

**Type/Stats:** Unit, cost 2, 5/5  |  Traits: Underworld

**Rules text:**

> When the action phase starts: Reveal the top card of your deck and an opponent's deck. For each card that costs 3 or more revealed this way, this unit gets –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

