# moff-gideon:07 — New primitive: capture

- **Group id (paste this):** `moff-gideon:07`
- **Kind:** ability
- **Cards:** 2
- **⚠ New primitives suspected:** capture — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_120 | Discerning Veteran | Unit | 5 | 3/4 |  |
| SHD_124 | Legal Authority | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### SHD_120 — Discerning Veteran

**Type/Stats:** Unit, cost 5, 3/4  |  Traits: Bounty Hunter

**Rules text:**

> When Played: This unit captures an enemy non-leader ground unit. (Put the captured card facedown under this unit until this unit leaves play.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** capture. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_124 — Legal Authority

**Type/Stats:** Upgrade, cost 2  |  Traits: Law

**Rules text:**

> Attach to a friendly unit.
> When Played: Attached unit captures an enemy non-leader unit with less power than it. (Put the captured card facedown under attached unit until attached unit leaves play.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** capture. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

