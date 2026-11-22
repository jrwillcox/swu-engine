# ic27-set:09 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_24 | Grand Admiral Thrawn | Unit | 6 | 4/4 | Sentinel |
| IC27_29 | Chimaera | Unit | 10 | 8/8 | Shielded |
| IC27_34 | Obi-Wan's Interceptor | Unit | 2 | 2/3 |  |
| IC27_37 | Finn | Unit | 4 | 4/5 | Restore, Sentinel |
| IC27_40 | Rose Tico | Unit | 6 | 6/6 | Shielded |
| IC27_45 | Qi'ra | Unit | 3 | 1/1 |  |
| IC27_46 | Vigilant Defense | Event | 4 |  | Sentinel |

## Per-card analysis & acceptance criteria

### IC27_24 — Grand Admiral Thrawn

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Imperial, Official

**Rules text:**

> When Played/On Attack/When Defeated:  You may give an Experience token to another friendly unit. It gains Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'keyword_grant'].

**Existing primitives that should suffice:** GiveToken, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_29 — Chimaera

**Type/Stats:** Unit, cost 10, 8/8  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Shielded
> When Played: Give an Experience token to each friendly unit for each upgrade on it. Then, heal 1 damage from your base for each friendly upgrade.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_34 — Obi-Wan's Interceptor

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> Other friendly Republic units get +0/+1.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_37 — Finn

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Resistance

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> While this unit is upgraded, he gains Restore 2. (When he attacks, heal 2 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_40 — Rose Tico

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Resistance

**Rules text:**

> Shielded (When you play this unit, give a Shield token to her.)
> On Attack: You may give a Shield token to another Resistance unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_45 — Qi'ra

**Type/Stats:** Unit, cost 3, 1/1  |  Traits: Underworld

**Rules text:**

> When Played: Give 2 Experience tokens to this unit.
> When Defeated: Choose a unit. You may give an Experience token to it for each Experience token that was on this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_46 — Vigilant Defense

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Give a friendly unit +0/+3 and Sentinel for this phase.
> Heal 3 damage from a friendly unit or base.
> Defeat an enemy unit with 3 or less remaining HP.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'defeat', 'stat_buff'].

**Existing primitives that should suffice:** Heal, DefeatUnit/Upgrade, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

