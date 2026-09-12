# boba-fett:01 — Direct damage & removal

- **Group id (paste this):** `boba-fett:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_9 | Boba Fett | Leader | 6 | 4/7 |  |
| SOR_131 | Fifth Brother | Unit | 3 | 2/4 | Raid |
| JTL_132 | First Order Stormtrooper | Unit | 1 | 2/1 |  |
| JTL_133 | Allegiant General Pryde | Unit | 2 | 2/3 |  |
| JTL_139 | Dengar | Unit | 4 | 5/4 | Piloting |
| JTL_140 | IG-2000 | Unit | 4 | 3/4 | Overwhelm |
| JTL_144 | No Disintegrations | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_9 — Boba Fett

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Bounty Hunter, Pilot, Underworld

**Rules text:**

> When you deal non-combat damage: You may exhaust this leader. If you do, deal 1 indirect damage to a player. (That player assigns 1 unpreventable damage among their base and units.)
> 
> Attached unit is a leader unit.
> When deployed as an upgrade: Deal up to 4 damage divided as you choose among any number of units.
> 
> Epic Action: If you control 6 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_131 — Fifth Brother

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> This unit gains Raid 1 for each damage on him. (He gets +1/+0 while attacking for each damage on him.)
> 
> On Attack: You may deal 1 damage to this unit and 1 damage to another ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_132 — First Order Stormtrooper

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: First Order, Trooper

**Rules text:**

> On Attack/When Defeated: Deal 1 indirect damage to a player. (They assign 1 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_133 — Allegiant General Pryde

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: First Order, Official

**Rules text:**

> When indirect damage is dealt to a unit: You may defeat a non-unique upgrade on it.
> On Attack: If you have the initiative, deal 2 indirect damage to a player.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_139 — Dengar

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Bounty Hunter, Pilot, Underworld

**Rules text:**

> Piloting [2 resources Aggression Villainy]
> Attached unit gains: “On Attack: Deal 2 indirect damage to a player. If this unit is an Underworld unit, deal 3 indirect damage instead.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_140 — IG-2000

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Overwhelm
> When Played: Deal 1 damage to each of up to 3 units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_144 — No Disintegrations

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Deal damage to a non-leader unit equal to 1 less than its remaining HP.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

