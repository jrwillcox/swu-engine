# lof-set:03 — Direct damage & removal

- **Group id (paste this):** `lof-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_158 | Hyena Bomber | Unit | 3 | 2/2 |  |
| LOF_167 | Saesee Tiin | Unit | 5 | 4/6 |  |
| LOF_170 | Bendu | Unit | 8 | 10/10 |  |
| LOF_171 | Heavy Blaster Cannon | Upgrade | 4 |  |  |
| LOF_172 | Sorcerous Blast | Event | 1 |  |  |
| LOF_176 | Lightsaber Throw | Event | 2 |  |  |
| LOF_177 | Time of Crisis | Event | 4 |  |  |

## Per-card analysis & acceptance criteria

### LOF_158 — Hyena Bomber

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Droid, Fighter, Separatist, Vehicle

**Rules text:**

> When Played: If you control another Aggression unit, you may deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_167 — Saesee Tiin

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: If you have the initiative, deal 1 damage to each of up to 3 units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_170 — Bendu

**Type/Stats:** Unit, cost 8, 10/10  |  Traits: Creature, Force

**Rules text:**

> On Attack: Deal 3 damage to each other unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_171 — Heavy Blaster Cannon

**Type/Stats:** Upgrade, cost 4  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: You may deal 1 damage to a ground unit. Then, deal 1 damage to the same unit. Then, deal 1 damage to the same unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_172 — Sorcerous Blast

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Use the Force (lose your Force token). If you do, deal 3 damage to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_176 — Lightsaber Throw

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Discard a Lightsaber card from your hand. If you do, deal 4 damage to a ground unit and draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'draw', 'discard'].

**Existing primitives that should suffice:** DealDamage, DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_177 — Time of Crisis

**Type/Stats:** Event, cost 4  |  Traits: Disaster

**Rules text:**

> Each player chooses a unit they control. Deal 3 damage to each unit not chosen this way.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

