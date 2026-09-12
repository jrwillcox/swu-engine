# padme-amidala:04 — Miscellaneous abilities

- **Group id (paste this):** `padme-amidala:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_106 | Dismantle the Conspiracy | Event | 6 |  |  |
| SEC_115 | Taylander Shuttle | Unit | 3 | 2/4 |  |
| SEC_120 | Naboo Security Force | Unit | 6 | 5/7 | Sentinel |
| SEC_127 | Charged with Corruption | Event | 3 |  |  |
| SEC_208 | Hunter | Unit | 6 | 7/6 | Saboteur |
| SEC_248 | B2EMO | Unit | 1 | 0/4 | Restore, Sentinel |
| SEC_256 | Moral Authority | Upgrade | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_106 — Dismantle the Conspiracy

**Type/Stats:** Event, cost 6  |  Traits: Tactic

**Rules text:**

> A friendly unit captures any number of enemy non-leader units with a total of 7 or less remaining HP.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_115 — Taylander Shuttle

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> On Attack: If you have the initiative, create a Spy token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_120 — Naboo Security Force

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Naboo, Trooper

**Rules text:**

> When Played/When Defeated: You may disclose Command (reveal a card from your hand with this aspect icon). If you do, give a friendly unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_127 — Charged with Corruption

**Type/Stats:** Event, cost 3  |  Traits: Law

**Rules text:**

> You may disclose CommandCommand (reveal cards from your hand with these aspect icons among them). If you do, a friendly unit captures an enemy non-leader unit. (Put the captured card facedown under that unit until that unit leaves play.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** disclose, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_208 — Hunter

**Type/Stats:** Unit, cost 6, 7/6  |  Traits: Clone, Fringe

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: If the defender is exhausted, it gets –4/–0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_248 — B2EMO

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Droid, Fringe

**Rules text:**

> Restore 1
> On Attack: You may disclose HeroismHeroism (reveal cards from your hand with these aspect icons among them). If you do, give a unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_256 — Moral Authority

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> Attach to a friendly <uq> (unique) unit.
> When Played: Attached unit captures an enemy non-leader unit with less remaining HP than it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

