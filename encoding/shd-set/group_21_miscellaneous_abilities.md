# shd-set:21 — Miscellaneous abilities

- **Group id (paste this):** `shd-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_106 | Rule with Respect | Event | 4 |  |  |
| SHD_109 | Endless Legions | Event | 14 |  |  |
| SHD_123 | Bounty Hunter's Quarry | Upgrade | 1 |  | Bounty |
| SHD_132 | Choose Sides | Event | 7 |  |  |
| SHD_187 | Lurking TIE Phantom | Unit | 3 | 2/2 | Raid |
| SHD_192 | Dryden Vos | Unit | 7 | 5/7 | Shielded |
| SHD_202 | Qi'ra | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### SHD_106 — Rule with Respect

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> A friendly unit captures each enemy non-leader unit that attacked your base this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_109 — Endless Legions

**Type/Stats:** Event, cost 14  |  Traits: Supply

**Rules text:**

> Reveal any number of resources you control. Play each unit revealed this way for free (one at a time).

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_123 — Bounty Hunter's Quarry

**Type/Stats:** Upgrade, cost 1  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Search the top 5 cards of your deck, or 10 cards instead if this unit is unique, for a unit that costs 3 or less and play it for free.” (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_132 — Choose Sides

**Type/Stats:** Event, cost 7  |  Traits: Plan

**Rules text:**

> Choose a friendly non-leader unit and an enemy non-leader unit. Exchange control of those units.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_187 — Lurking TIE Phantom

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> This unit can't be captured, damaged, or defeated by enemy card abilities.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_192 — Dryden Vos

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Underworld

**Rules text:**

> Shielded
> When Played: Choose a captured card guarded by a unit you control. You may play it for free under your control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_202 — Qi'ra

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Underworld

**Rules text:**

> When Played: Look at an opponent's hand, then name a card. While this unit is in play, each card with that name costs 3 resources more for your opponents to play.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

