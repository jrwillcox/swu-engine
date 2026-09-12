# ash-set:29 — Miscellaneous abilities

- **Group id (paste this):** `ash-set:29`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_200 | Rehabilitation | Event | 5 |  |  |
| ASH_211 | Fateful Goodbye | Event | 2 |  |  |
| ASH_212 | Peli Motto | Unit | 1 | 1/1 | Shielded |
| ASH_218 | Ferry Droid | Unit | 3 | 1/5 |  |
| ASH_238 | Attendant Navigator | Unit | 2 | 2/3 |  |
| ASH_250 | Imperial Defector | Unit | 2 | 3/2 |  |
| ASH_254 | Gallofree Transport | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### ASH_200 — Rehabilitation

**Type/Stats:** Event, cost 5  |  Traits: Learned

**Rules text:**

> Choose a non-leader unit. Give that unit –3/–0 for this phase, then take control of it. At the start of the regroup phase, its owner takes control of it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_211 — Fateful Goodbye

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> If a friendly unit left play this phase, distribute 3 Advantage tokens among friendly units. If a friendly leader unit left play this phase, distribute 5 Advantage tokens instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_212 — Peli Motto

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Fringe

**Rules text:**

> Shielded
> Ignore the aspect penalties of the first non‑unit card you play each phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_218 — Ferry Droid

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Droid

**Rules text:**

> When Played: Give 4 Advantage tokens to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_238 — Attendant Navigator

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: First Order

**Rules text:**

> When Played: You may give 2 Advantage tokens to a space unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_250 — Imperial Defector

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Imperial, Rebel

**Rules text:**

> When Played: Look at an opponent's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_254 — Gallofree Transport

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Defeated: Give 2 Advantage tokens to a friendly unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

