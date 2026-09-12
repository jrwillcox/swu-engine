# ash-set:02 — Direct damage & removal

- **Group id (paste this):** `ash-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_4 | Grand Admiral Thrawn | Leader | 8 | 5/8 | Restore |
| ASH_11 | Cad Bane | Leader | 6 | 4/7 | Overwhelm |
| ASH_12 | Vane | Leader | 5 | 3/6 |  |
| ASH_27 | Enoch | Unit | 4 | 4/5 |  |
| ASH_32 | Rancor Keeper | Unit | 2 | 2/4 |  |
| ASH_35 | Tatooine Repulsor Train | Unit | 7 | 8/7 |  |
| ASH_38 | Purrgil Ultra | Unit | 8 | 6/10 |  |

## Per-card analysis & acceptance criteria

### ASH_4 — Grand Admiral Thrawn

**Type/Stats:** Leader, cost 8, 5/8  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Attack with a unit. It gains Restore 2 for this attack if you control the same number of units as the defending player.
> Restore 2
> On Attack: If you control more units than the defending player, you may defeat a non-leader unit they control.
> Epic Action: If you control 8 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_11 — Cad Bane

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Action [Exhaust]: Deal 1 damage to a unit with 2 or more remaining HP.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> On Attack: You may deal 1 damage to a unit with 2 or more remaining HP.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_12 — Vane

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Underworld

**Rules text:**

> Action [Exhaust, defeat a friendly upgrade]: Deal 2 damage to a base.
> On Attack: You may defeat a friendly upgrade. If you do, deal 2 damage to the defending unit or a base.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_27 — Enoch

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Imperial, Trooper

**Rules text:**

> When Defeated: You may deal up to 6 damage to your base. The next unit you play this phase costs 1 resource less for every 2 damage dealt this way.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_32 — Rancor Keeper

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Underworld

**Rules text:**

> When a friendly unit is dealt damage and survives: Deal 1 damage to any number of bases. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_35 — Tatooine Repulsor Train

**Type/Stats:** Unit, cost 7, 8/7  |  Traits: Speeder, Underworld, Vehicle

**Rules text:**

> This unit can't be attacked while you control 2 or more exhausted units (unless it gains Sentinel).
> On Attack: Deal 2 damage to a ground unit for each friendly exhausted unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_38 — Purrgil Ultra

**Type/Stats:** Unit, cost 8, 6/10  |  Traits: Creature

**Rules text:**

> When Played/When Defeated: You may return another friendly non-leader unit to its owner's hand. If you do, deal damage to a unit equal to the returned unit's cost.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'return_hand'].

**Existing primitives that should suffice:** DealDamage, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

