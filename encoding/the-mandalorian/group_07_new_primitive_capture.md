# the-mandalorian:07 — New primitive: capture

- **Group id (paste this):** `the-mandalorian:07`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** capture — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_251 | The Mandalorian's Rifle | Upgrade | 3 |  |  |

## Per-card analysis & acceptance criteria

### SHD_251 — The Mandalorian's Rifle

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a friendly non-VEHICLE unit.
> 
> When Played: If attached unit is The Mandalorian, he captures an exhausted enemy non-leader unit. (Put the captured card facedown under him until he leaves play.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** capture. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

