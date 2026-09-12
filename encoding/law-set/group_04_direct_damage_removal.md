# law-set:04 — Direct damage & removal

- **Group id (paste this):** `law-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_130 | Betrayed Trust | Event | 2 |  |  |
| LAW_132 | The Tree Remembers | Event | 4 |  |  |
| LAW_137 | Ruthless Duo | Unit | 4 | 3/5 |  |
| LAW_173 | BT-1 | Unit | 2 | 2/4 |  |
| LAW_174 | 0-0-0 | Unit | 3 | 4/4 |  |
| LAW_178 | Persecutor | Unit | 9 | 9/7 |  |
| LAW_179 | Fear and Dead Men | Event | 7 |  |  |

## Per-card analysis & acceptance criteria

### LAW_130 — Betrayed Trust

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Choose an enemy unit. For this phase, that unit can't deal combat damage.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_132 — The Tree Remembers

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> An enemy unit loses all abilities for this phase. If it costs 3 or less, defeat it.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_137 — Ruthless Duo

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: If you control another Villainy unit, you may deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_173 — BT-1

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Droid, Underworld

**Rules text:**

> On Attack: Discard a card from your deck. If it's Aggression, you may deal 1 damage to a ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_174 — 0-0-0

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Droid, Underworld

**Rules text:**

> On Attack: You may put a Aggression card from your discard pile on the bottom of your deck. If you do, deal 1 damage to each enemy base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_178 — Persecutor

**Type/Stats:** Unit, cost 9, 9/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played/On Attack: Choose an arena. You may deal 3 damage to each unit in that arena.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_179 — Fear and Dead Men

**Type/Stats:** Event, cost 7  |  Traits: Tactic

**Rules text:**

> This card costs 1 resource less to play for each card discarded from your hand this phase.
> Deal 4 damage to each enemy ground unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

