# chancellor-palpatine:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `chancellor-palpatine:04`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_124 | Budget Scheming | Event | 2 |  |  |
| SEC_245 | When Has Become Now | Event | 1 |  | Plot |

## Per-card analysis & acceptance criteria

### SEC_124 — Budget Scheming

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> Give an Experience token to each of up to 3 Official units.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_245 — When Has Become Now

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Play a card with Plot from your resources (paying its cost). Put the top card of your deck into play as a resource.

**Mechanical analysis:** trigger archetype `event`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

