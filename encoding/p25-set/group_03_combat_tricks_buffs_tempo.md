# p25-set:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `p25-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P25_41 | Red Three | Unit | 3 | 2/3 | Raid |
| P25_42 | Chewbacca | Unit | 5 | 3/6 | Sentinel |
| P25_46 | Kylo Ren | Unit | 6 | 6/7 |  |
| P25_55 | Fett's Firespray | Unit | 6 | 5/6 |  |
| P25_73 | Luke Skywalker | Leader | 6 | 4/7 |  |
| P25_83 | Ahsoka Tano | Unit | 3 | 3/4 | Ambush |
| P25_105 | Heirloom Lightsaber | Upgrade | 2 |  | Restore |

## Per-card analysis & acceptance criteria

### P25_41 — Red Three

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> Raid 1 
> 
> Each other friendly [Heroism] unit gains Raid 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_42 — Chewbacca

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Underworld, Wookiee

**Rules text:**

> Sentinel 
> 
> When this unit is attacked: Ready him.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_46 — Kylo Ren

**Type/Stats:** Unit, cost 6, 6/7  |  Traits: First Order, Force

**Rules text:**

> While playing this unit, ignore his Villainy aspect penalty if you control Rey.
> On Attack: Give a unit +2/+0 for this phase. If it?s a non-Villainy unit, also give an Experience token to it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token', 'stat_buff'].

**Existing primitives that should suffice:** GiveToken, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_55 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: If you control Boba Fett or Jango Fett , ready this unit.
> 
> Action [2 resources]: Exhaust a non-unique unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_73 — Luke Skywalker

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Rebel

**Rules text:**

> Action [1 resource, exhaust]: Give a Shield token to a [Heroism] unit you played this phase. 
> On Attack: You may give another unit a Shield token. 
> Epic Action: If you control 6 or more resources, deploy this leader. 

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_83 — Ahsoka Tano

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> While you control fewer units than an opponent , this unit gains Ambush.
> Action [2 resources]: Return this unit and each upgrade on her to their owners' hands.

**Mechanical analysis:** trigger archetype `activated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_105 — Heirloom Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> If attached unit is a Force unit, it gains Restore 1. 

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

