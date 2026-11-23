# hmw-set:28 — New primitive: weakness-token

- **Group id (paste this):** `hmw-set:28`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_240 | Sandstorm | Event | 3 |  |  |
| HMW_242 | Occupation Officer | Unit | 2 | 3/2 |  |
| HMW_248 | Defoliator Tank | Unit | 5 | 4/6 | Overwhelm |

## Per-card analysis & acceptance criteria

### HMW_240 — Sandstorm

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> While you control a Tatooine base, this event costs 1 resource less to play.
> Choose an arena. Give a Weakness token to each exhausted enemy unit in that arena.

**Mechanical analysis:** trigger archetype `constant`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** CostReduction, weakness-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_242 — Occupation Officer

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Imperial

**Rules text:**

> When Played: If you control 6 or more resources, you may give a Weakness token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** weakness-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_248 — Defoliator Tank

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Separatist, Tank, Vehicle

**Rules text:**

> Overwhelm
> On Attack: If the defending unit isn't a Droid or Vehicle, you may pay 2 resources. If you do, give 2 Weakness tokens to it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** weakness-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

