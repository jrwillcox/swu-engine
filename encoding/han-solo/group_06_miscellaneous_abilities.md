# han-solo:06 — Miscellaneous abilities

- **Group id (paste this):** `han-solo:06`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_103 | Chewbacca | Unit | 5 | 5/6 | Piloting |
| JTL_245 | R2-D2 | Unit | 1 | 1/4 | Piloting |

## Per-card analysis & acceptance criteria

### JTL_103 — Chewbacca

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Pilot, Rebel, Wookiee

**Rules text:**

> This unit can't be defeated or returned to hand by enemy card abilities.
> Piloting [3 resources Command Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains: “This unit can't be defeated or returned to hand by enemy card abilities.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_245 — R2-D2

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Droid, Pilot, Rebel

**Rules text:**

> Piloting [0 resources Heroism]
> This upgrade can be played on a friendly Vehicle unit with a Pilot on it.
> Attached unit gains: “You may play or deploy 1 additional Pilot on this unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

