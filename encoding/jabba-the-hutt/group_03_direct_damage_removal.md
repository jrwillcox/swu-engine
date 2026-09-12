# jabba-the-hutt:03 — Direct damage & removal

- **Group id (paste this):** `jabba-the-hutt:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_163 | The Sarlacc of Carkoon | Unit | 8 | 8/9 |  |
| LAW_214 | Boba Fett | Unit | 5 | 6/5 |  |
| JTL_216 | Contracted Hunter | Unit | 3 | 4/4 | Ambush |

## Per-card analysis & acceptance criteria

### LAW_163 — The Sarlacc of Carkoon

**Type/Stats:** Unit, cost 8, 8/9  |  Traits: Creature

**Rules text:**

> On Attack: Put a unit from your discard pile on the bottom of your deck. Deal damage equal to that unit's power to an enemy ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_214 — Boba Fett

**Type/Stats:** Unit, cost 5, 6/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played/On Attack: You may pay 1 resource. If you do, deal 3 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_216 — Contracted Hunter

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When the regroup phase starts: Defeat this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

