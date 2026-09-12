# shd-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_35 | Clan Saxon Gauntlet | Unit | 6 | 4/5 | Sentinel |
| SHD_36 | First Light | Unit | 7 | 4/7 | Grit, Smuggle |
| SHD_42 | Concord Dawn Interceptors | Unit | 3 | 1/4 | Sentinel |
| SHD_48 | Gentle Giant | Unit | 6 | 2/8 | Grit |
| SHD_52 | Sugi | Unit | 4 | 4/6 | Sentinel, Smuggle |
| SHD_54 | Midnight Repairs | Event | 2 |  |  |
| SHD_59 | Embo | Unit | 3 | 3/4 |  |

## Per-card analysis & acceptance criteria

### SHD_35 — Clan Saxon Gauntlet

**Type/Stats:** Unit, cost 6, 4/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> When this unit is attacked: You may give an Experience token to a unit (before damage is dealt).

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_36 — First Light

**Type/Stats:** Unit, cost 7, 4/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Grit
> Each other friendly non-leader unit gains Grit.
> Smuggle [7 resources Vigilance Villainy, deal 4 damage to a friendly unit]

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_42 — Concord Dawn Interceptors

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Fighter, Mandalorian, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> This unit gets +2/+0 while defending.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_48 — Gentle Giant

**Type/Stats:** Unit, cost 6, 2/8  |  Traits: Wookiee

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> On Attack: You may heal damage from another unit equal to the damage on this unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_52 — Sugi

**Type/Stats:** Unit, cost 4, 4/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> While an enemy unit is upgraded, this unit gains Sentinel.
> Smuggle [6 resources Vigilance] (If this card is a resource, you may play her for her smuggle cost. Replace her with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_54 — Midnight Repairs

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Heal up to 8 total damage from any number of units.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_59 — Embo

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When this unit completes an attack: If the defender was defeated, heal up to 2 damage from a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

