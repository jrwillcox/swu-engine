# ic27-set:01 — Direct damage & removal

- **Group id (paste this):** `ic27-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_5 | Darth Maul | Leader | 5 | 4/5 |  |
| IC27_14 | Dryden Vos | Unit | 2 | 1/4 |  |
| IC27_26 | Darth Sidious | Unit | 7 | 5/8 | Restore |
| IC27_31 | BB-8 | Unit | 1 | 0/4 |  |
| IC27_39 | Ahsoka Tano | Unit | 5 | 4/5 |  |
| IC27_66 | Mother Talzin | Unit | 7 | 5/5 |  |
| IC27_102 | Third Sister | Unit | 3 | 3/5 |  |

## Per-card analysis & acceptance criteria

### IC27_5 — Darth Maul

**Type/Stats:** Leader, cost 5, 4/5  |  Traits: Force, Sith

**Rules text:**

> Action [1 resource, Exhaust]: Deal 1 damage to a unit.
> On Attack: You may deal 1 damage to a unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_14 — Dryden Vos

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Underworld

**Rules text:**

> On Attack: You may deal 1 damage to a friendly unit. If it survives, give an Experience token to it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'token'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_26 — Darth Sidious

**Type/Stats:** Unit, cost 7, 5/8  |  Traits: Force, Separatist, Sith

**Rules text:**

> Restore 3 (When this unit attacks, heal 3 damage from your base.)
> When you heal damage from your base: Deal that much damage to an enemy unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_31 — BB-8

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Droid, Resistance

**Rules text:**

> On Attack: Heal 1 damage from a friendly unit. If you do, deal 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_39 — Ahsoka Tano

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: You may defeat a unit that costs 3 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_66 — Mother Talzin

**Type/Stats:** Unit, cost 7, 5/5  |  Traits: Force, Night

**Rules text:**

> When Played: You may play a Villainy unit that costs 4 or less from your discard pile for free. If it's not a Night or Undead unit, deal damage equal to its cost to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_102 — Third Sister

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> On Attack: Deal 1 damage to a friendly ground unit and 1 damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

