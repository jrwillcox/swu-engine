# jabba-the-hutt:06 — Miscellaneous abilities

- **Group id (paste this):** `jabba-the-hutt:06`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_212 | Malakili | Unit | 2 | 2/4 |  |
| LAW_215 | Vermillion | Unit | 6 | 5/7 |  |

## Per-card analysis & acceptance criteria

### LAW_212 — Malakili

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Underworld

**Rules text:**

> Each friendly Creature unit and each Creature unit you own that isn't in play gains the Underworld trait.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_215 — Vermillion

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Capital Ship, Underworld, Vehicle

**Rules text:**

> When Attack Ends: If this unit survived, reveal the top card of a deck, then choose a player. They may play the revealed card for free. If they do, a different player creates Credit tokens equal to that card's cost.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

