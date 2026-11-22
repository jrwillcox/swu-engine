# hmwp-set:01 — Direct damage & removal

- **Group id (paste this):** `hmwp-set:01`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_2 | Scorch | Unit | 3 | 3/5 |  |
| HMWP_6 | Always a Bigger Fish | Event | 2 |  |  |
| HMWP_10 | Arena Acklay | Unit | 5 | 5/6 |  |
| HMWP_11 | General Grievous | Unit | 7 | 8/5 |  |
| HMWP_14 | Adamant Ewoks | Unit | 2 | 3/2 |  |
| HMWP_17 | Don't Touch Anything | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### HMWP_2 — Scorch

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> On Attack: You may deal 1 damage to an upgraded unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_6 — Always a Bigger Fish

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Defeat a friendly Creature unit. If you do, play a Creature unit that costs up to 3 more than the defeated unit from your hand for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_10 — Arena Acklay

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Creature

**Rules text:**

> When this unit is dealt damage and survives: Deal 2 damage to each enemy base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_11 — General Grievous

**Type/Stats:** Unit, cost 7, 8/5  |  Traits: Official, Separatist

**Rules text:**

> Bases can't be healed.
> When Played: Deal 4 damage to a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_14 — Adamant Ewoks

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Ewok

**Rules text:**

> When Played: If you control another Ewok unit or an Endor base, you may deal 1 damage to a base and 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_17 — Don't Touch Anything

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Deal 3 damage to a random enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

