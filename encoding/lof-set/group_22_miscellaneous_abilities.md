# lof-set:22 — Miscellaneous abilities

- **Group id (paste this):** `lof-set:22`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_248 | Jocasta Nu | Unit | 3 | 3/4 |  |
| LOF_262 | Go Into Hiding | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LOF_248 — Jocasta Nu

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: You may attach a friendly upgrade on a friendly unit to a different eligible unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_262 — Go Into Hiding

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Choose a unit. It can't be attacked this phase (unless it has Sentinel).

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

