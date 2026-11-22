# hmw-set:29 — New primitive: beast-token

- **Group id (paste this):** `hmw-set:29`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_10 | Tarfful | Leader | 6 | 3/7 | Sentinel |
| HMW_12 | Poggle the Lesser | Leader | 5 | 1/6 |  |
| HMW_38 | Bestial Bond | Upgrade | 3 |  |  |
| HMW_47 | Eravana | Unit | 5 | 1/7 |  |
| HMW_58 | Mysterious Disappearance | Event | 2 |  |  |
| HMW_77 | Boss Nass | Unit | 4 | 4/6 |  |
| HMW_144 | Howler Pack | Unit | 6 | 3/3 |  |

## Per-card analysis & acceptance criteria

### HMW_10 — Tarfful

**Type/Stats:** Leader, cost 6, 3/7  |  Traits: Rebel, Wookiee

**Rules text:**

> Action [2 resources, Exhaust, discard a card from your hand]: Create a Beast token.
> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> On Attack: You may pay 1 resource. If you do, create a Beast token.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ramp'].

**Existing primitives that should suffice:** create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_12 — Poggle the Lesser

**Type/Stats:** Leader, cost 5, 1/6  |  Traits: Official, Separatist

**Rules text:**

> Action [1 resource, Exhaust]: Ready a friendly Creature unit and deal 1 damage to it.
> When Deployed: Create a Beast token.
> On Attack: You may ready a friendly Creature unit and deal 1 damage to it.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, ExhaustCard/ReadyCard, create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_38 — Bestial Bond

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> When Played: If attached unit is a Creature or a Force unit, create a Beast token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_47 — Eravana

**Type/Stats:** Unit, cost 5, 1/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> On Attack: Create a Beast token and ready it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_58 — Mysterious Disappearance

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> A player chooses a non-leader unit they control. You may defeat that unit. If you do, that player creates a Beast token.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_77 — Boss Nass

**Type/Stats:** Unit, cost 4, 4/6  |  Traits: Gungan, Official

**Rules text:**

> When Played/On Attack: You may defeat a Shield token on a friendly Gungan unit. If you do, create a Beast token and give a Shield token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken, create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_144 — Howler Pack

**Type/Stats:** Unit, cost 6, 3/3  |  Traits: Creature

**Rules text:**

> When Played/When Defeated: Create a Beast token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit, beast-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

