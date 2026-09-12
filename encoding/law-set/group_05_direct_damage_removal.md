# law-set:05 — Direct damage & removal

- **Group id (paste this):** `law-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_181 | Cloud-Rider Veteran | Unit | 2 | 1/4 |  |
| LAW_183 | B-Wing Skirmisher | Unit | 4 | 4/4 |  |
| LAW_184 | Aerie | Unit | 6 | 3/7 |  |
| LAW_187 | “Staccato Lightning” Repeater | Upgrade | 3 |  |  |
| LAW_189 | Cavern Angels X-Wing | Unit | 2 | 2/1 |  |
| LAW_191 | Arvel Skeen | Unit | 3 | 4/3 |  |
| LAW_195 | Overcharged Transport | Unit | 4 | 4/3 |  |

## Per-card analysis & acceptance criteria

### LAW_181 — Cloud-Rider Veteran

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Underworld

**Rules text:**

> On Attack: Deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_183 — B-Wing Skirmisher

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Played: Deal 1 damage to each of up to 2 space units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_184 — Aerie

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> On Attack: Deal 2 damage to an enemy ground unit and 2 damage to a base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_187 — “Staccato Lightning” Repeater

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: Deal 1 damage to each of up to 3 different ground units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_189 — Cavern Angels X-Wing

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Defeated: Deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_191 — Arvel Skeen

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Rebel

**Rules text:**

> When Played/On Attack: You may defeat a Credit token (belonging to any player). If you do, deal 1 damage to a unit or base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_195 — Overcharged Transport

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Transport, Vehicle

**Rules text:**

> When Played/When Defeated: You may defeat an upgrade attached to a space unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

