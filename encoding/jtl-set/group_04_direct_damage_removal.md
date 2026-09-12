# jtl-set:04 — Direct damage & removal

- **Group id (paste this):** `jtl-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_148 | Frisk | Unit | 2 | 3/2 | Piloting |
| JTL_149 | Red Squadron Y-Wing | Unit | 2 | 1/3 |  |
| JTL_152 | Tactical Heavy Bomber | Unit | 5 | 3/5 |  |
| JTL_153 | Rebellious Hammerhead | Unit | 6 | 5/7 |  |
| JTL_156 | Trench Run | Event | 1 |  |  |
| JTL_158 | Crackshot V-Wing | Unit | 1 | 2/2 |  |
| JTL_162 | Droid Missile Platform | Unit | 3 | 4/2 |  |

## Per-card analysis & acceptance criteria

### JTL_148 — Frisk

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: New Republic, Pilot

**Rules text:**

> Piloting [2 resources Aggression Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: You may defeat an upgrade that costs 2 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_149 — Red Squadron Y-Wing

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> On Attack: Deal 3 indirect damage to the defending player. (They assign 3 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_152 — Tactical Heavy Bomber

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Resistance, Transport, Vehicle

**Rules text:**

> On Attack: Deal indirect damage equal to this unit's power to the defending player. If a base is damaged this way, draw a card. (That player assigns that much unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_153 — Rebellious Hammerhead

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> When Played: You may deal damage to a unit equal to the number of cards in your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_156 — Trench Run

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Attack with a Fighter unit. For this attack, it gets +4/+0 and gains: “On Attack: Discard 2 cards from the defending player's deck. Deal unpreventable damage equal to the difference in the discarded cards' costs to this unit.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_158 — Crackshot V-Wing

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Fighter, Republic, Vehicle

**Rules text:**

> When Played: If you control no other Fighter units, deal 1 damage to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_162 — Droid Missile Platform

**Type/Stats:** Unit, cost 3, 4/2  |  Traits: Droid, Separatist, Transport, Vehicle

**Rules text:**

> When Defeated: Deal 3 indirect damage to a player. (They assign 3 unpreventable damage among their base and units.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

