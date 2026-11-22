# hmwp-set:05 — New primitive: beast-token

- **Group id (paste this):** `hmwp-set:05`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_1 | Eravana | Unit | 5 | 1/7 |  |

## Per-card analysis & acceptance criteria

### HMWP_1 — Eravana

**Type/Stats:** Unit, cost 5, 1/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> On Attack: Create a Beast token and ready it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

