# shd-set:04 — Direct damage & removal

- **Group id (paste this):** `shd-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_158 | Wild Rancor | Unit | 6 | 6/8 | Overwhelm |
| SHD_163 | Migs Mayfeld | Unit | 2 | 2/2 |  |
| SHD_167 | Wanted Insurgents | Unit | 3 | 4/4 | Bounty |
| SHD_170 | IG-11 | Unit | 5 | 6/5 |  |
| SHD_171 | Covetous Rivals | Unit | 6 | 5/5 | Bounty, Grit |
| SHD_172 | Krayt Dragon | Unit | 9 | 10/10 | Overwhelm |
| SHD_173 | Guild Target | Upgrade | 0 |  | Bounty |

## Per-card analysis & acceptance criteria

### SHD_158 — Wild Rancor

**Type/Stats:** Unit, cost 6, 6/8  |  Traits: Creature

**Rules text:**

> Overwhelm
> When Played: Deal 2 damage to each other ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_163 — Migs Mayfeld

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Underworld

**Rules text:**

> When a player discards a card from their hand: You may deal 2 damage to a unit or base. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_167 — Wanted Insurgents

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Rebel

**Rules text:**

> Bounty — Deal 2 damage to a unit. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_170 — IG-11

**Type/Stats:** Unit, cost 5, 6/5  |  Traits: Bounty Hunter, Droid

**Rules text:**

> If this unit would be captured, defeat him and deal 3 damage to each enemy ground unit instead.
> On Attack: You may deal 3 damage to a damaged ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_171 — Covetous Rivals

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Bounty Hunter

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played/On Attack: You may deal 2 damage to a unit with a Bounty.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_172 — Krayt Dragon

**Type/Stats:** Unit, cost 9, 10/10  |  Traits: Creature

**Rules text:**

> Overwhelm
> When an opponent plays a card: You may deal damage equal to that card's cost to their base or a ground unit they control.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_173 — Guild Target

**Type/Stats:** Upgrade, cost 0  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Deal 2 damage to a base. If this unit is unique, deal 3 damage instead.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

