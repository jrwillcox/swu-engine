# hmw-set:27 — New primitive: weakness-token

- **Group id (paste this):** `hmw-set:27`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** weakness-token, beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_196 | Qimir | Unit | 1 | 3/1 |  |
| HMW_197 | Cid Scaleback | Unit | 2 | 2/2 |  |
| HMW_199 | Geonosian Picador | Unit | 3 | 2/2 |  |
| HMW_200 | Rish Loo | Unit | 4 | 3/2 | Hidden |
| HMW_202 | Inferno Squad | Unit | 5 | 3/6 |  |
| HMW_231 | Dragonboat Freighter | Unit | 6 | 5/5 |  |
| HMW_237 | Easy Prey | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### HMW_196 — Qimir

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Force

**Rules text:**

> When Defeated: You may discard the top card of your deck. If it's not Villainy, give a Weakness token to an enemy unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_197 — Cid Scaleback

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Underworld

**Rules text:**

> When Played: An opponent chooses a unit they control. Give a Weakness token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** opponent-chooses-target.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_199 — Geonosian Picador

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Separatist

**Rules text:**

> When Played: Create a Beast token. Then, give a Weakness token to a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** weakness-token, beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_200 — Rish Loo

**Type/Stats:** Unit, cost 4, 3/2  |  Traits: Gungan, Official, Separatist

**Rules text:**

> Hidden
> When Played: Take control of an enemy non‑leader unit with a Weakness token on it. At the start of the next regroup phase, its owner takes control of it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_202 — Inferno Squad

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial, Trooper

**Rules text:**

> When Played/When Defeated: You may deal 1 damage to a unit and give a Weakness token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_231 — Dragonboat Freighter

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: You may give a Weakness token to a unit. If it's a <uq> unit, exhaust it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ready_exhaust'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_237 — Easy Prey

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> Create a Beast token.
> An opponent creates a Beast token. Give a Weakness token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** weakness-token, beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

