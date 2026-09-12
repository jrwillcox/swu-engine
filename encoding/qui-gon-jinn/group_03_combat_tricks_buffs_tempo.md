# qui-gon-jinn:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `qui-gon-jinn:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_96 | Obi-Wan Kenobi | Unit | 3 | 3/5 | Sentinel |
| SHD_96 | Maz Kanata | Unit | 1 | 1/1 |  |
| LOF_99 | Paladin Training Corvette | Unit | 5 | 3/5 |  |
| LOF_111 | Maz Kanata | Unit | 3 | 3/4 |  |
| JTL_201 | Ahsoka Tano | Unit | 4 | 3/5 |  |
| LOF_201 | Qui-Gon Jinn's Lightsaber | Upgrade | 2 |  |  |
| LOF_242 | Refugee of The Path | Unit | 1 | 0/3 | Sentinel |

## Per-card analysis & acceptance criteria

### LOF_96 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> When you play a Force unit (including this one): This unit gains Sentinel for this phase. 

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_96 — Maz Kanata

**Type/Stats:** Unit, cost 1, 1/1  |  Traits: Underworld

**Rules text:**

> When you play another unit: Give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_99 — Paladin Training Corvette

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Capital Ship, Jedi, Republic, Vehicle

**Rules text:**

> When Played: You may give an Experience token to each of up to 3 Force units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_111 — Maz Kanata

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Underworld

**Rules text:**

> When Played: You may attack with a Force unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_201 — Ahsoka Tano

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Fringe

**Rules text:**

> When Played: An opponent discards a card from their hand. If it's a unit, you may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_201 — Qui-Gon Jinn's Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a friendly non-Vehicle unit.
> When Played: If attached unit is Qui-Gon Jinn, you may exhaust any number of units with combined cost 6 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_242 — Refugee of The Path

**Type/Stats:** Unit, cost 1, 0/3  |  Traits: Force, Fringe

**Rules text:**

> When Played: You may give a Shield token to a unit with Sentinel.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

