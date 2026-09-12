# c25-set:02 — Miscellaneous abilities

- **Group id (paste this):** `c25-set:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| C25_1 | L3-37 | Unit | 3 | 3/3 | Piloting |

## Per-card analysis & acceptance criteria

### C25_1 — L3-37

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Droid, Pilot, Underworld

**Rules text:**

> If this unit would be defeated, you may instead attach her as an upgrade to a friendly Vehicle unit without a Pilot on it. 
> Piloting [3 resources Vigilance Heroism]

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

