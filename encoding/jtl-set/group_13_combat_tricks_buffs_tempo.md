# jtl-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_45 | Hera Syndulla | Unit | 2 | 2/3 | Piloting, Restore |
| JTL_50 | Phantom II | Unit | 3 | 3/3 | Grit |
| JTL_57 | Astromech Pilot | Unit | 1 | 1/3 | Piloting |
| JTL_58 | Academy Graduate | Unit | 2 | 1/2 | Piloting, Sentinel |
| JTL_66 | Trace Martez | Unit | 3 | 2/5 | Piloting |
| JTL_67 | Cloaked StarViper | Unit | 4 | 3/2 |  |
| JTL_70 | U-Wing Lander | Unit | 5 | 2/2 |  |

## Per-card analysis & acceptance criteria

### JTL_45 — Hera Syndulla

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Pilot, Rebel, Spectre, Twi'lek

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> Piloting [2 resources Vigilance Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains Restore 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_50 — Phantom II

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Rebel, Spectre, Transport, Vehicle

**Rules text:**

> Grit
> Action [1 resource]: If this card is a unit, attach it as an upgrade to The Ghost. (It's no longer a unit. Defeat all upgrades on it and remove all damage from it.)
> Attached unit gets +3/+3 and gains Grit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_57 — Astromech Pilot

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Pilot

**Rules text:**

> Piloting [2 resources Vigilance] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: You may heal 2 damage from a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_58 — Academy Graduate

**Type/Stats:** Unit, cost 2, 1/2  |  Traits: Imperial, Pilot

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> Piloting [2 resources Vigilance] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains Sentinel.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_66 — Trace Martez

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Fringe, Pilot

**Rules text:**

> Piloting [1 resource Vigilance] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains: “On Attack: You may heal 2 total damage from any number of units.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_67 — Cloaked StarViper

**Type/Stats:** Unit, cost 4, 3/2  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: Give 2 Shield tokens to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_70 — U-Wing Lander

**Type/Stats:** Unit, cost 5, 2/2  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Played: Give 3 Experience tokens to this unit.
> When this unit completes an attack (and survives): You may attach an upgrade on this unit to another eligible friendly Vehicle unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

