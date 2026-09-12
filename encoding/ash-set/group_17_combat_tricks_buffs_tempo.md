# ash-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_105 | Bo-Katan Kryze | Unit | 2 | 2/4 | Raid |
| ASH_109 | T-6 Shuttle 1974 | Unit | 4 | 2/6 | Sentinel |
| ASH_113 | Mandalorian Flagship | Unit | 7 | 4/8 | Ambush |
| ASH_114 | Sabine's Lightsaber | Upgrade | 2 |  | Restore |
| ASH_115 | The Student Guides the Master | Event | 1 |  |  |
| ASH_120 | Warrior of Clan Kryze | Unit | 2 | 2/3 | Sentinel |
| ASH_125 | Stolen Eta Shuttle | Unit | 4 | 3/5 | Hidden |

## Per-card analysis & acceptance criteria

### ASH_105 — Bo-Katan Kryze

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Mandalorian

**Rules text:**

> While you control another Mandalorian unit, this unit gains Raid 2.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_109 — T-6 Shuttle 1974

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Jedi, Transport, Vehicle

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> Action [Exhaust]: Give another unit +2/+2 for this phase. You may attack with that unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_113 — Mandalorian Flagship

**Type/Stats:** Unit, cost 7, 4/8  |  Traits: Capital Ship, Mandalorian, Vehicle

**Rules text:**

> While you control a leader unit, this unit gains Ambush. (When you play this unit, it may attack an enemy unit.)
> This unit gets +1/+0 for each other friendly Mandalorian unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_114 — Sabine's Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> If attached unit is Sabine Wren or a Force unit, it gains Restore 2.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_115 — The Student Guides the Master

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Give a friendly unit +1/+0 for this phase for each other friendly unit with less power than it.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_120 — Warrior of Clan Kryze

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Mandalorian, Trooper

**Rules text:**

> While you control another exhausted unit, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_125 — Stolen Eta Shuttle

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Transport, Vehicle

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> While you have the initiative, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

