# the-mandalorian:02 — Direct damage & removal

- **Group id (paste this):** `the-mandalorian:02`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_78 | Fell the Dragon | Event | 4 |  |  |
| SHD_220 | Fennec Shand | Unit | 7 | 4/6 | Ambush |

## Per-card analysis & acceptance criteria

### SHD_78 — Fell the Dragon

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a non-leader unit with 5 or more power.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_220 — Fennec Shand

**Type/Stats:** Unit, cost 7, 4/6  |  Traits: Underworld

**Rules text:**

> Ambush (When you play this unit, it may ready and attack an enemy unit.)
> On Attack: Deal 1 damage to the defender (if it's a unit) for each different cost among cards in your discard pile.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

