# ash-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_82 | Trexler Armored Marauder | Unit | 6 | 5/6 | Grit |
| ASH_86 | Durasteel Plating | Upgrade | 2 |  |  |
| ASH_88 | The Conflict Within | Upgrade | 3 |  |  |
| ASH_89 | Perseverance | Event | 2 |  |  |
| ASH_93 | Captain Pellaeon | Unit | 2 | 2/4 | Raid |
| ASH_98 | AT-ST Raider | Unit | 4 | 4/5 | Ambush |
| ASH_100 | Gallius Rax | Unit | 6 | 4/7 |  |

## Per-card analysis & acceptance criteria

### ASH_82 — Trexler Armored Marauder

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Imperial, Tank, Vehicle

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: You may give a Shield token to a unit that costs 3 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_86 — Durasteel Plating

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor

**Rules text:**

> When Played: Give a Shield token to attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_88 — The Conflict Within

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> Attached unit gains: “When this unit readies: You may pay 3 resources. If you don't, exhaust this unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_89 — Perseverance

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Heal 3 damage from a unit and give a Shield token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_93 — Captain Pellaeon

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Imperial, Official

**Rules text:**

> While a leader unit has been defeated this phase, this unit gains Raid 3. (He gets +3/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_98 — AT-ST Raider

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Vehicle, Walker

**Rules text:**

> While you control another non-<uq> unit, this unit gains Ambush. (When you play this unit, it may attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_100 — Gallius Rax

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Imperial, Official

**Rules text:**

> Other friendly units with 2 or more different keywords get +2/+2.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

