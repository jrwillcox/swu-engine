# ash-set:24 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:24`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_263 | The Way of the Mand'alor | Upgrade | 2 |  |  |
| ASH_264 | A New Order | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### ASH_263 — The Way of the Mand'alor

**Type/Stats:** Upgrade, cost 2  |  Traits: Mandalorian

**Rules text:**

> This upgrade costs 1 resource less to play on a Mandalorian unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_264 — A New Order

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Give an Advantage token to each of up to 2 units.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

