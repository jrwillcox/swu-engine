# ic27-set:17 — Miscellaneous abilities

- **Group id (paste this):** `ic27-set:17`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_163 | Bo-Katan Kryze | Unit | 7 | 7/6 | Shielded |
| IC27_165 | Luke Skywalker | Unit | 8 | 9/9 |  |
| IC27_172 | Razor Crest | Unit | 3 | 2/5 |  |

## Per-card analysis & acceptance criteria

### IC27_163 — Bo-Katan Kryze

**Type/Stats:** Unit, cost 7, 7/6  |  Traits: Mandalorian

**Rules text:**

> Shielded (When you play this unit, give a Shield token to her.)
> When Played: Give each enemy unit –7/–0 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_165 — Luke Skywalker

**Type/Stats:** Unit, cost 8, 9/9  |  Traits: Force, Rebel

**Rules text:**

> When Played: You may put an enemy non-leader unit on the bottom of its owner's deck. Its owner draws 2 cards.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_172 — Razor Crest

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Each unit (including friendly units) loses all “When Defeated” abilities.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

