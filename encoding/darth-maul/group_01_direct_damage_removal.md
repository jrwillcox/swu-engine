# darth-maul:01 — Direct damage & removal

- **Group id (paste this):** `darth-maul:01`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_38 | Pong Krell | Unit | 7 | 2/9 | Grit |
| SOR_137 | Fallen Lightsaber | Upgrade | 3 |  |  |
| LOF_138 | Sith Holocron | Upgrade | 1 |  |  |
| TWI_138 | Count Dooku | Unit | 8 | 6/6 | Exploit, Overwhelm |
| LOF_160 | Merrin | Unit | 3 | 2/5 |  |

## Per-card analysis & acceptance criteria

### LOF_38 — Pong Krell

**Type/Stats:** Unit, cost 7, 2/9  |  Traits: Force, Jedi, Republic

**Rules text:**

> Grit
> When this unit completes an attack (and survives): You may defeat a unit with less remaining HP than this unit's power.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_137 — Fallen Lightsaber

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit. 
> 
> If attached unit is a Force unit, it gains: "On Attack: Deal 1 damage to each ground unit the defending player controls."

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_138 — Sith Holocron

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Sith

**Rules text:**

> Attach to a Force unit.
> Attached unit gains: “On Attack: You may deal 2 damage to a friendly unit. If you do, this unit gets +2/+0 for this attack.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'stat_buff'].

**Existing primitives that should suffice:** DealDamage, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_138 — Count Dooku

**Type/Stats:** Unit, cost 8, 6/6  |  Traits: Force, Separatist, Sith

**Rules text:**

> Exploit 2
> Overwhelm
> When Played: For each unit you exploited while playing this card, you may deal damage to an enemy unit equal to the power of the exploited unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_160 — Merrin

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Force, Night

**Rules text:**

> On Attack: You may discard a card from your hand. If you do, deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

