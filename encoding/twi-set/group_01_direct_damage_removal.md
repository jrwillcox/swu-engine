# twi-set:01 — Direct damage & removal

- **Group id (paste this):** `twi-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_3 | Obi-Wan Kenobi | Leader | 6 | 4/7 | Sentinel |
| TWI_10 | Pre Vizsla | Leader | 5 | 4/6 |  |
| TWI_13 | Mace Windu | Leader | 7 | 5/8 |  |
| TWI_17 | Chancellor Palpatine | Leader |  |  |  |
| TWI_18 | Quinlan Vos | Leader | 5 | 3/7 |  |
| TWI_34 | General Grievous | Unit | 3 | 4/4 |  |
| TWI_36 | Devastating Gunship | Unit | 5 | 3/5 | Grit |

## Per-card analysis & acceptance criteria

### TWI_3 — Obi-Wan Kenobi

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust]: Heal 1 damage from a unit.
> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> On Attack: Heal 1 damage from a unit. If you do, deal 1 damage to a different unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_10 — Pre Vizsla

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Mandalorian, Trooper

**Rules text:**

> Action [1 resource, Exhaust]: Deal damage to a unit equal to the number of cards you've drawn this phase. (This doesn't include cards drawn in the regroup phase.)
> While you have 3 or more cards in your hand, this unit gains Saboteur.
> While you have 6 or more cards in your hand, this unit gets +2/+0.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus, GrantKeyword, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_13 — Mace Windu

**Type/Stats:** Leader, cost 7, 5/8  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [1 resource, Exhaust]: Deal 1 damage to a damaged enemy unit. Then, if it has 5 or more damage on it, deal 1 damage to it.
> When Deployed: Deal 2 damage to each damaged enemy unit.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_17 — Chancellor Palpatine

**Type/Stats:** Leader  |  Traits: Official, Republic

**Rules text:**

> This leader starts the game with this side faceup.
> Action [Exhaust]: If a friendly Heroism unit was defeated this phase, draw a card, heal 2 damage from your base, then flip this leader.
> Action [Exhaust]: If you played a Villainy card this phase, create a Clone Trooper token, deal 2 damage to each enemy base, then flip this leader.

**Mechanical analysis:** trigger archetype `activated`; effect families ['damage', 'heal', 'draw'].

**Existing primitives that should suffice:** DealDamage, Heal, DrawCards, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_18 — Quinlan Vos

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> When you play a unit: You may exhaust this leader. If you do, deal 1 damage to an enemy unit that costs the same as the played unit.
> When you play a unit: You may deal 1 damage to an enemy unit that costs the same as or less than the played unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_34 — General Grievous

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Official, Separatist

**Rules text:**

> Ignore the aspect penalty on each Lightsaber upgrade you play on this unit.
> On Attack: If this unit has 4 or more Lightsaber upgrades attached to him, defeat 4 enemy units.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_36 — Devastating Gunship

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Droid, Separatist, Transport, Vehicle

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: Defeat an enemy unit with 2 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

