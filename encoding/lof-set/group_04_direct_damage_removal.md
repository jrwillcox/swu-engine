# lof-set:04 — Direct damage & removal

- **Group id (paste this):** `lof-set:04`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_213 | The Legacy Run | Unit | 5 | 3/3 |  |
| LOF_239 | Consumed by the Dark Side | Event | 2 |  |  |
| LOF_259 | Ravening Gundark | Unit | 5 | 5/4 |  |
| LOF_260 | The Father | Unit | 8 | 5/10 |  |
| LOF_264 | It's Worse | Event | 7 |  |  |

## Per-card analysis & acceptance criteria

### LOF_213 — The Legacy Run

**Type/Stats:** Unit, cost 5, 3/3  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Defeated: Deal 6 damage divided as you choose among enemy units.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_239 — Consumed by the Dark Side

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Give 2 Experience tokens to a unit, then deal 2 damage to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_259 — Ravening Gundark

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Creature

**Rules text:**

> When Played: Deal 1 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_260 — The Father

**Type/Stats:** Unit, cost 8, 5/10  |  Traits: Force

**Rules text:**

> When you use the Force: You may deal 1 damage to this unit. If you do, the Force is with you.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_264 — It's Worse

**Type/Stats:** Event, cost 7  |  Traits: Trick

**Rules text:**

> Defeat a non-leader unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

