# hmwp-set:06 — New primitive: weakness-token

- **Group id (paste this):** `hmwp-set:06`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** weakness-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_15 | Inferno Squad | Unit | 5 | 3/6 |  |

## Per-card analysis & acceptance criteria

### HMWP_15 — Inferno Squad

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial, Trooper

**Rules text:**

> When Played/When Defeated: You may deal 1 damage to a unit and give a Weakness token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

