# ash-set:06 — Direct damage & removal

- **Group id (paste this):** `ash-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_147 | The Cyborg Mech | Unit | 6 | 3/7 | Grit |
| ASH_148 | Ninth Sister | Unit | 7 | 8/7 | Overwhelm |
| ASH_151 | Operation Cinder | Event | 6 |  |  |
| ASH_153 | Green Leader | Unit | 2 | 3/1 |  |
| ASH_158 | Han Solo | Unit | 4 | 3/7 | Saboteur |
| ASH_161 | Zeb Orrelios | Unit | 7 | 5/7 |  |
| ASH_163 | Reckless Sacrifice | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### ASH_147 — The Cyborg Mech

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Fringe

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: Either deal 2 damage to an undamaged ground unit or 5 damage to a damaged ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_148 — Ninth Sister

**Type/Stats:** Unit, cost 7, 8/7  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Overwhelm
> When Played: An opponent discards a card from their hand. You may deal damage equal to its cost divided as you choose among any number of units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_151 — Operation Cinder

**Type/Stats:** Event, cost 6  |  Traits: Disaster, Plan

**Rules text:**

> Deal 5 damage to your base. Then, deal 5 damage to each unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_153 — Green Leader

**Type/Stats:** Unit, cost 2, 3/1  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Defeated: You may deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_158 — Han Solo

**Type/Stats:** Unit, cost 4, 3/7  |  Traits: Official, Rebel

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: Deal 3 damage to this unit. Give 3 Advantage tokens to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_161 — Zeb Orrelios

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Rebel, Spectre

**Rules text:**

> When Played: Give 3 Advantage tokens to another unit.
> When a friendly upgrade is defeated: Deal 1 damage to a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_163 — Reckless Sacrifice

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Discard a unit from your hand. Deal 5 damage to a unit that costs more than the discarded card.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

