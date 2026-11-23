# p26-set:05 — Miscellaneous abilities

- **Group id (paste this):** `p26-set:05`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_28 | Emperor Palpatine | Unit | 5 | 3/2 |  |
| P26_32 | Fett's Firespray | Unit | 6 | 6/6 | Ambush |
| P26_241 | Fett's Firespray | Unit | 6 | 6/6 | Ambush |
| P26_272 | Boba Fett | Unit | 3 | 1/5 | Ambush, Raid, Saboteur |

## Per-card analysis & acceptance criteria

### P26_28 — Emperor Palpatine

**Type/Stats:** Unit, cost 5, 3/2  |  Traits: Force, Imperial, Official, Sith

**Rules text:**

> When Played: You may take control of an enemy non-leader unit that costs 3 or less. If you do, give 2 Weakness tokens to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change, weakness-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_32 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Friendly units can attack bases while using Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_241 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Friendly units can attack bases while using Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_272 — Boba Fett

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Tusken

**Rules text:**

> Ambush
> When a friendly unit with Ambush enters play: Give it Raid 1 and Saboteur for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

