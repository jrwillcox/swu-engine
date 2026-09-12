# sabine-mean-green:01 — Direct damage & removal

- **Group id (paste this):** `sabine-mean-green:01`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_14 | Sabine Wren | Leader | 4 | 2/5 |  |
| SOR_142 | Sabine Wren | Unit | 2 | 2/3 |  |
| SOR_143 | Fighters for Freedom | Unit | 3 | 3/4 | Saboteur |
| SOR_145 | K-2SO | Unit | 4 | 4/4 | Overwhelm |
| SHD_147 | Ketsu Onyo | Unit | 2 | 3/2 | Saboteur |
| SOR_152 | For a Cause I Believe In | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SOR_14 — Sabine Wren

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Mandalorian, Rebel, Spectre

**Rules text:**

> Action [exhaust]: Deal 1 damage to each base.
> On Attack: Deal 1 damage to each enemy base.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_142 — Sabine Wren

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Mandalorian, Rebel, Spectre

**Rules text:**

> While there are at least 3 aspects among other friendly units, this unit can't be attacked (unless she gains Sentinel).
> 
> On Attack: You may deal 1 damage to the defender or to a base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_143 — Fighters for Freedom

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Rebel, Trooper

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> When you play another [Aggression] card: You may deal 1 damage to a base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_145 — K-2SO

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Droid, Rebel

**Rules text:**

> Overwhelm
> 
> When Defeated: For each opponent, choose one: either deal 3 damage to that player's base, or that player discards a card from their hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_147 — Ketsu Onyo

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Bounty Hunter, Mandalorian, Underworld

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When this unit deals combat damage to a base: You may defeat an upgrade that costs 2 or less.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_152 — For a Cause I Believe In

**Type/Stats:** Event, cost 3  |  Traits: Innate

**Rules text:**

> Reveal the top 4 cards of your deck. For each [Heroism] card revealed this way, deal 1 damage to an enemy base. You may discard any of the revealed cards and put the rest back on top of your deck in any order.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

