# han-solo:08 — New primitive: control-change

- **Group id (paste this):** `han-solo:08`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** control-change — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_235 | Commandeer | Event | 5 |  |  |

## Per-card analysis & acceptance criteria

### JTL_235 — Commandeer

**Type/Stats:** Event, cost 5  |  Traits: Trick

**Rules text:**

> Take control of a non-leader Vehicle unit that costs 6 or less without a Pilot on it. If you do, ready it. At the start of the next regroup phase, return that unit to its owner's hand.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** ReturnToHand.

**⚠ Suspected NEW primitive:** control-change. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

