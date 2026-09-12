# the-mandalorian:06 — Miscellaneous abilities

- **Group id (paste this):** `the-mandalorian:06`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_64 | Survivors' Gauntlet | Unit | 5 | 4/6 |  |
| SHD_69 | Foundling | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### SHD_64 — Survivors' Gauntlet

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> When Played/On Attack: You may attach an upgrade on a unit to another eligible unit controlled by the same player.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_69 — Foundling

**Type/Stats:** Upgrade, cost 1  |  Traits: Mandalorian

**Rules text:**

> Attached unit gains the Mandalorian trait.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

