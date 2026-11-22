# ic27-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:14`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_150 | Frozen in Carbonite | Upgrade | 3 |  |  |
| IC27_159 | Princess Leia | Unit | 5 | 5/5 |  |
| IC27_160 | Tantive IV | Unit | 5 | 3/5 | Raid, Saboteur |
| IC27_162 | Chewbacca | Unit | 6 | 4/6 | Sentinel |
| IC27_175 | Shoot First | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### IC27_150 — Frozen in Carbonite

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> Attach to a non–leader unit.
> Attached unit can't ready.
> When Played: Exhaust attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_159 — Princess Leia

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Official, Rebel

**Rules text:**

> When Played/On Attack: Exhaust up to 2 units in the same arena with combined cost 4 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_160 — Tantive IV

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Each other friendly Rebel unit gains Raid 2 and Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_162 — Chewbacca

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel, Wookiee

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> While this unit is damaged, he gets +4/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_175 — Shoot First

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Attack with a unit. It gets +1/+0 for this attack and deals its combat damage before the defending unit. (If the defending unit is defeated, it deals no combat damage.)

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

