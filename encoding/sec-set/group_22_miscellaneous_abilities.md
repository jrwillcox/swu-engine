# sec-set:22 — Miscellaneous abilities

- **Group id (paste this):** `sec-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_145 | Confidence in Victory | Event | 10 |  |  |
| SEC_153 | Luthen's Haulcraft | Unit | 5 | 5/3 |  |
| SEC_159 | Chairman Papanoida | Unit | 3 | 2/6 |  |
| SEC_175 | Ambition's Reward | Upgrade | 2 |  |  |
| SEC_178 | Pursue the Lead | Event | 2 |  |  |
| SEC_181 | Unauthorized Investigation | Event | 3 |  |  |
| SEC_185 | Screeching TIE Fighter | Unit | 1 | 2/1 |  |

## Per-card analysis & acceptance criteria

### SEC_145 — Confidence in Victory

**Type/Stats:** Event, cost 10  |  Traits: Gambit

**Rules text:**

> Play only as your first action in the action phase.
> Choose an arena. At the start of the regroup phase, if you are the only player who controls units in that arena, you win the game.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_153 — Luthen's Haulcraft

**Type/Stats:** Unit, cost 5, 5/3  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Defeated: You may choose an opponent and disclose AggressionAggressionHeroism (reveal cards from your hand with these aspect icons among them). If you do, that opponent discards 2 cards from their hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_159 — Chairman Papanoida

**Type/Stats:** Unit, cost 3, 2/6  |  Traits: Official, Republic

**Rules text:**

> When a player draws 1 or more cards during the action phase: You may disclose AggressionAggression (reveal cards from your hand with these aspect icons among them). If you do, create a Spy token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** disclose, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_175 — Ambition's Reward

**Type/Stats:** Upgrade, cost 2  |  Traits: Law

**Rules text:**

> When Played: Create a Spy token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_178 — Pursue the Lead

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Choose a player. That player discards a card from their hand. If it costs 3 or less, create a Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_181 — Unauthorized Investigation

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Create a Spy token.
> You may disclose Aggression (reveal a card from your hand with this aspect icon). If you do, create another Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** disclose, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_185 — Screeching TIE Fighter

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> On Attack: You may choose a ground unit. If you do, it loses its keywords (and can't gain keywords) for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

