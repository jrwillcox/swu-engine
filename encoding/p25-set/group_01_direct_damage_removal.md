# p25-set:01 — Direct damage & removal

- **Group id (paste this):** `p25-set:01`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P25_39 | Admiral Ackbar | Unit | 3 | 1/4 | Restore |
| P25_54 | Kit Fisto | Unit | 6 | 7/6 | Coordinate, Saboteur |
| P25_74 | Darth Vader | Leader | 7 | 5/8 |  |

## Per-card analysis & acceptance criteria

### P25_39 — Admiral Ackbar

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Official, Rebel

**Rules text:**

> Restore 1 
> 
> When Played: You may deal damage to a unit equal to the number of units you control in its arena. 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_54 — Kit Fisto

**Type/Stats:** Unit, cost 6, 7/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Saboteur
> Coordinate — On Attack: You may deal 3 damage to a ground unit. 

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_74 — Darth Vader

**Type/Stats:** Leader, cost 7, 5/8  |  Traits: Force, Imperial, Sith

**Rules text:**

> Action [1 resource, exhaust]: If you played a [Villainy] card this phase, deal 1 damage to a unit and 1 damage to a base.
> On Attack: You may deal 2 damage to a unit.
> Epic Action: If you control 7 or more resources, deploy this leader. 

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

