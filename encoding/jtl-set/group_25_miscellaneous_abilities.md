# jtl-set:25 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:25`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_155 | They Hate That Ship | Event | 1 |  |  |
| JTL_169 | Shadow Caster | Unit | 6 | 4/7 |  |
| JTL_171 | Targeting Computer | Upgrade | 1 |  |  |
| JTL_213 | Sidon Ithano | Unit | 2 | 2/2 |  |
| JTL_229 | Diversion | Event | 1 |  | Sentinel |
| JTL_232 | Jump to Lightspeed | Event | 2 |  |  |
| JTL_233 | Sweep the Area | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_155 — They Hate That Ship

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> An opponent creates 2 TIE Fighter tokens and readies them. Then, play a Vehicle unit from your hand. It costs 3 resources less.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_169 — Shadow Caster

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When a friendly unit is defeated: You may use all of its “When Defeated” abilities again.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_171 — Targeting Computer

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Modification

**Rules text:**

> Attached unit gains: “You assign all indirect damage dealt by this unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_213 — Sidon Ithano

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Pilot, Underworld

**Rules text:**

> When played as a unit: You may attach this unit as an upgrade to an enemy Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_229 — Diversion

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Give a unit Sentinel for this phase. (Units in its arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_232 — Jump to Lightspeed

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Return a friendly space unit and any number of non-leader upgrades on it to their owners' hands. The next time you play a copy of that unit this phase, you may play it for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_233 — Sweep the Area

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Return up to 2 non-leader units in the same arena with a combined cost 3 or less to their owners' hands.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

