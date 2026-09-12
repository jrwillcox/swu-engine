# shd-set:05 — Direct damage & removal

- **Group id (paste this):** `shd-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_177 | Vambrace Flamethrower | Upgrade | 3 |  |  |
| SHD_180 | Detention Block Rescue | Event | 3 |  |  |
| SHD_225 | Jetpack | Upgrade | 2 |  | Smuggle |
| SHD_226 | Unrefusable Offer | Upgrade | 2 |  | Bounty |
| SHD_229 | Ma Klounkee | Event | 1 |  |  |
| SHD_235 | Ruthless Assassin | Unit | 2 | 3/3 | Overwhelm |
| SHD_239 | Toro Calican | Unit | 3 | 3/5 |  |

## Per-card analysis & acceptance criteria

### SHD_177 — Vambrace Flamethrower

**Type/Stats:** Upgrade, cost 3  |  Traits: Armor, Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack: You may deal 3 damage divided as you choose among enemy ground units.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_180 — Detention Block Rescue

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Deal 3 damage to a unit. If that unit is guarding any captured cards, deal 6 damage instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_225 — Jetpack

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: Give a Shield token to attached unit. At the start of the regroup phase, defeat that token.
> Smuggle [4 resources Cunning]

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_226 — Unrefusable Offer

**Type/Stats:** Upgrade, cost 2  |  Traits: Bounty, Condition

**Rules text:**

> Attach to a non-leader unit.
> Attached unit gains: “Bounty — Play this unit for free (under your control). It enters play ready. At the start of the regroup phase, defeat it.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['defeat', 'ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_229 — Ma Klounkee

**Type/Stats:** Event, cost 1  |  Traits: Trick, Underworld

**Rules text:**

> Return a friendly non-leader Underworld unit to its owner's hand. If you do, deal 3 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'return_hand'].

**Existing primitives that should suffice:** DealDamage, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_235 — Ruthless Assassin

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: Deal 2 damage to a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_239 — Toro Calican

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Bounty Hunter

**Rules text:**

> When you play another Bounty Hunter unit: You may deal 1 damage to it. If you do, ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

