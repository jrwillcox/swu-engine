# p26-set:01 — Direct damage & removal

- **Group id (paste this):** `p26-set:01`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_34 | Qui-Gon Jinn | Unit | 5 | 2/5 | Grit |
| P26_249 | Adamant Ewoks | Unit | 2 | 3/2 |  |

## Per-card analysis & acceptance criteria

### P26_34 — Qui-Gon Jinn

**Type/Stats:** Unit, cost 5, 2/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Grit
> When Played: You may defeat a unit that attacked your base this phase. If it's a leader unit, defeat this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_249 — Adamant Ewoks

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Ewok

**Rules text:**

> When Played: If you control another Ewok unit or an Endor base, you may deal 1 damage to a base and 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

