# hmw-set:31 — New primitive: beast-token

- **Group id (paste this):** `hmw-set:31`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_250 | Imperial Cavalry | Unit | 6 | 4/4 |  |
| HMW_262 | Mylaya Rider | Unit | 6 | 4/4 |  |
| HMW_272 | Growth | Event | 5 |  |  |

## Per-card analysis & acceptance criteria

### HMW_250 — Imperial Cavalry

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: Create a Beast token and deal 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_262 — Mylaya Rider

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Creature, Wookiee

**Rules text:**

> When Played: Create a Beast token and heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_272 — Growth

**Type/Stats:** Event, cost 5  |  Traits: Innate

**Rules text:**

> Create a Beast token.
> Heal 3 damage from your base.
> Draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'draw'].

**Existing primitives that should suffice:** Heal, DrawCards, create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

