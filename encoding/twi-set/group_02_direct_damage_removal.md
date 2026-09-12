# twi-set:02 — Direct damage & removal

- **Group id (paste this):** `twi-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_41 | Lethal Crackdown | Event | 4 |  |  |
| TWI_44 | Kashyyyk Defender | Unit | 2 | 0/5 | Grit |
| TWI_48 | Obi-Wan's Aethersprite | Unit | 5 | 4/6 |  |
| TWI_59 | Royal Guard Attaché | Unit | 2 | 2/5 |  |
| TWI_76 | Death by Droids | Event | 5 |  |  |
| TWI_78 | The Invasion of Christophsis | Event | 15 |  | Exploit |
| TWI_89 | Consolidation of Power | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### TWI_41 — Lethal Crackdown

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a non-leader unit. Deal damage to your base equal to that unit's power.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_44 — Kashyyyk Defender

**Type/Stats:** Unit, cost 2, 0/5  |  Traits: Wookiee

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: Heal up to 2 damage from another unit and deal that much damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_48 — Obi-Wan's Aethersprite

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> When Played/On Attack: You may deal 1 damage to this unit and 2 damage to another space unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_59 — Royal Guard Attaché

**Type/Stats:** Unit, cost 2, 2/5  |  Traits: Naboo, Trooper

**Rules text:**

> When Played: Deal 2 damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_76 — Death by Droids

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Defeat a unit that costs 3 or less. Create 2 Battle Droid tokens.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_78 — The Invasion of Christophsis

**Type/Stats:** Event, cost 15  |  Traits: Plan, Separatist

**Rules text:**

> Exploit 4
> Choose an opponent. Defeat each unit that player controls.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_89 — Consolidation of Power

**Type/Stats:** Event, cost 6  |  Traits: Plan

**Rules text:**

> Choose any number of friendly units. You may play a unit from your hand if its cost is less than or equal to the combined power of the chosen units for free. Then, defeat the chosen units.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

