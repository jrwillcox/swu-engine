# chancellor-palpatine:05 — Miscellaneous abilities

- **Group id (paste this):** `chancellor-palpatine:05`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_31 | Nute Gunray | Unit | 3 | 3/4 | Grit, Sentinel |
| SEC_33 | Sly Moore | Unit | 4 | 2/6 | Plot |
| SEC_83 | ISB Shuttle | Unit | 3 | 3/2 |  |
| SEC_87 | Dedra Meero | Unit | 6 | 5/5 | Ambush |
| SEC_92 | I Am the Senate | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### SEC_31 — Nute Gunray

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Official, Separatist

**Rules text:**

> Grit
> When Played/On Attack: You may give another friendly Official unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_33 — Sly Moore

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Official, Republic

**Rules text:**

> When Played: For this phase, each enemy unit gets –2/–0 while it's attacking a base.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_83 — ISB Shuttle

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> When Played: If a friendly unit was defeated this phase, create a Spy token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_87 — Dedra Meero

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Imperial, Official

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> On Attack: Create a Spy token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_92 — I Am the Senate

**Type/Stats:** Event, cost 6  |  Traits: Law

**Rules text:**

> Create 5 Spy tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

