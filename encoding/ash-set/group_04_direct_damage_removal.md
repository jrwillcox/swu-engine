# ash-set:04 — Direct damage & removal

- **Group id (paste this):** `ash-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_85 | Grav Charge | Upgrade | 1 |  |  |
| ASH_90 | Reforge | Event | 2 |  |  |
| ASH_92 | Foundling Rescue | Event | 4 |  |  |
| ASH_94 | Moff Jerjerrod | Unit | 2 | 1/3 |  |
| ASH_102 | Ravager | Unit | 9 | 8/10 | Restore |
| ASH_103 | Long Live the Empire | Event | 2 |  |  |
| ASH_110 | Admiral Ackbar | Unit | 5 | 6/6 |  |

## Per-card analysis & acceptance criteria

### ASH_85 — Grav Charge

**Type/Stats:** Upgrade, cost 1  |  Traits: Condition, Item, Weapon

**Rules text:**

> When attached unit's attack ends: Deal 4 damage to it and defeat this upgrade.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_90 — Reforge

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Defeat an upgrade on a friendly unit. If you do, search the top 8 cards of your deck for an upgrade that can attach to that unit, reveal it, and play it on that unit. It costs 4 resources less.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_92 — Foundling Rescue

**Type/Stats:** Event, cost 4  |  Traits: Plan

**Rules text:**

> You may defeat a unit with 2 or less remaining HP.
> Create a Mandalorian token.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_94 — Moff Jerjerrod

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Imperial, Official

**Rules text:**

> If you would create a number of tokens, you may defeat this unit. If you do, create twice that number of tokens instead.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_102 — Ravager

**Type/Stats:** Unit, cost 9, 8/10  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Restore 2
> When you play a unit: You may have it deal damage equal to its power to a unit in the same arena.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_103 — Long Live the Empire

**Type/Stats:** Event, cost 2  |  Traits: Imperial

**Rules text:**

> Defeat a friendly Imperial unit. If you do, resource the top card of your deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'ramp'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_110 — Admiral Ackbar

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Official, Rebel

**Rules text:**

> When Played: You may defeat this unit. If you do, search the top 10 cards of your deck for any number of space units with combined cost 5 or less and play each of them for free.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

