# hmw-set:06 — Direct damage & removal

- **Group id (paste this):** `hmw-set:06`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_185 | Ty Yorrick | Unit | 5 | 4/5 |  |
| HMW_186 | Mining Guild Trespasser | Unit | 6 | 5/5 |  |
| HMW_188 | Giant Gorax | Unit | 7 | 7/7 | Overwhelm |
| HMW_193 | Nightfall | Event | 2 |  |  |
| HMW_207 | Maim | Event | 1 |  |  |
| HMW_217 | Don't Touch Anything | Event | 2 |  |  |
| HMW_244 | Separatist Harbinger | Unit | 3 | 1/4 |  |

## Per-card analysis & acceptance criteria

### HMW_185 — Ty Yorrick

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Bounty Hunter, Force

**Rules text:**

> If a friendly ability would deal damage, you may have that ability deal that much damage plus 1 instead.
> On Attack: You may deal 1 damage to a Creature unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_186 — Mining Guild Trespasser

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Transport, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to a base and 2 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_188 — Giant Gorax

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Creature

**Rules text:**

> Overwhelm
> On Attack/When Defeated: If you control an Endor base, each opponent chooses one:
> You deal 3 damage to a unit or base they control.
> They discard a card from their hand and defeat a resource they control.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage', 'discard', 'defeat', 'ramp'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, DefeatUnit/Upgrade, sacrifice-resource-cost.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_193 — Nightfall

**Type/Stats:** Event, cost 2  |  Traits: Disaster

**Rules text:**

> Deal 1 damage to an enemy unit.
> If you control an Endor base, you may attack with a unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_207 — Maim

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Deal 1 damage to a unit and exhaust it.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_217 — Don't Touch Anything

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Deal 3 damage to a random enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_244 — Separatist Harbinger

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played/On Attack: An opponent chooses a unit or base they control. You may deal 2 damage to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

