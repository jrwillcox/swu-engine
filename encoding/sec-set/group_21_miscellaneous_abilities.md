# sec-set:21 — Miscellaneous abilities

- **Group id (paste this):** `sec-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_61 | Willrow Hood | Unit | 3 | 2/5 |  |
| SEC_67 | Umbaran Mobile Cannon | Unit | 6 | 7/3 |  |
| SEC_97 | Beloved Orator | Unit | 3 | 2/3 |  |
| SEC_126 | Trade Route Taxation | Event | 2 |  | Plot |
| SEC_131 | Let's Talk | Event | 9 |  |  |
| SEC_132 | Imperial Occupier | Unit | 2 | 2/2 |  |
| SEC_141 | The Galleon | Unit | 7 | 6/6 |  |

## Per-card analysis & acceptance criteria

### SEC_61 — Willrow Hood

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Fringe

**Rules text:**

> While this unit has exactly 1 friendly upgrade on it, that upgrade can't be defeated or returned to hand by enemy card abilities.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_67 — Umbaran Mobile Cannon

**Type/Stats:** Unit, cost 6, 7/3  |  Traits: Fringe, Vehicle, Walker

**Rules text:**

> The first time this unit would take damage each phase, prevent that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_97 — Beloved Orator

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: New Republic, Official

**Rules text:**

> When Played: Create a Spy token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_126 — Trade Route Taxation

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> Choose an opponent. If you control more units than that opponent, they can't play events for this phase.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_131 — Let's Talk

**Type/Stats:** Event, cost 9  |  Traits: Trick

**Rules text:**

> If a friendly unit left play this phase, this event costs 3 resources less to play.
> Each friendly unit captures an enemy non-leader unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_132 — Imperial Occupier

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Trooper

**Rules text:**

> When Defeated: Create a Spy token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_141 — The Galleon

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: You may disclose AggressionAggressionVillainy (reveal cards from your hand with these aspect icons among them). If you do, create 3 Spy tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** disclose, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

