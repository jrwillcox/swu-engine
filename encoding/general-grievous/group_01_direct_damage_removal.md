# general-grievous:01 — Direct damage & removal

- **Group id (paste this):** `general-grievous:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_238 | Merciless Contest | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### TWI_238 — Merciless Contest

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Each player chooses a non-leader unit they control. Defeat those units.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

