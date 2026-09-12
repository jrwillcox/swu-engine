# qui-gon-jinn:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `qui-gon-jinn:04`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_255 | Curious Flock | Unit | 1 | 1/1 |  |

## Per-card analysis & acceptance criteria

### LOF_255 — Curious Flock

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Creature

**Rules text:**

> When Played: Pay up to 6 resources. For each resource paid this way, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

