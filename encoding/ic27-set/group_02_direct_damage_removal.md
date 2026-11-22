# ic27-set:02 — Direct damage & removal

- **Group id (paste this):** `ic27-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_107 | Aurra Sing | Unit | 6 | 1/7 | Hidden |
| IC27_109 | Supreme Leader Snoke | Unit | 8 | 8/6 | Overwhelm |
| IC27_110 | Supremacy | Unit | 10 | 10/10 |  |
| IC27_117 | Hera Syndulla | Unit | 3 | 4/3 |  |
| IC27_119 | Sabine Wren | Unit | 4 | 5/4 | Saboteur |
| IC27_124 | K-2SO | Unit | 9 | 10/5 |  |
| IC27_127 | Act of Aggression | Event | 4 |  | Overwhelm |

## Per-card analysis & acceptance criteria

### IC27_107 — Aurra Sing

**Type/Stats:** Unit, cost 6, 1/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Hidden (This unit can't be attacked if she was played this phase.)
> Action [Exhaust]: Deal 4 damage to a unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_109 — Supreme Leader Snoke

**Type/Stats:** Unit, cost 8, 8/6  |  Traits: First Order, Force, Official

**Rules text:**

> Overwhelm
> When Played: Deal 4 damage to each other unit. Draw a card for each friendly unit defeated this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_110 — Supremacy

**Type/Stats:** Unit, cost 10, 10/10  |  Traits: Capital Ship, First Order, Vehicle

**Rules text:**

> When Played: Deal damage to a base equal to half its remaining HP, rounded down.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_117 — Hera Syndulla

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Rebel, Spectre, Twi'lek

**Rules text:**

> When you play another Rebel card: Deal 1 damage to a base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_119 — Sabine Wren

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Mandalorian, Rebel, Spectre

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: Discard 2 cards from a deck. You may deal damage to a unit equal to the difference in those cards' costs.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_124 — K-2SO

**Type/Stats:** Unit, cost 9, 10/5  |  Traits: Droid, Rebel

**Rules text:**

> When Defeated: Deal 5 damage to each enemy unit and each enemy base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_127 — Act of Aggression

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Draw a card.
> You may deal 3 damage to a unit.
> Give a friendly unit +3/+0 and Overwhelm for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'draw', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, DrawCards, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

