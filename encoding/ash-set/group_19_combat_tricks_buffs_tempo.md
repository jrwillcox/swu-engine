# ash-set:19 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_160 | Kachirho Militia | Unit | 5 | 4/6 | Hidden |
| ASH_162 | Rash Action | Event | 2 |  |  |
| ASH_167 | Flarestar Attack Shuttle | Unit | 2 | 2/1 |  |
| ASH_178 | Knobby White Ice Spider | Unit | 7 | 5/7 | Hidden |
| ASH_180 | Bokken Saber | Upgrade | 1 |  |  |
| ASH_181 | Mark My Words | Upgrade | 1 |  | Overwhelm |
| ASH_182 | Unfettered Ambition | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### ASH_160 — Kachirho Militia

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Trooper, Wookiee

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When an enemy ground unit attacks your base: Ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_162 — Rash Action

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. For this attack, it gets +1/+0 and gains: “When Attack Ends: If this unit dealt combat damage to an opponent's base, that opponent discards a card.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_167 — Flarestar Attack Shuttle

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played/When Defeated: You may give an Advantage token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_178 — Knobby White Ice Spider

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Creature

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When Played: For each enemy unit, give an Advantage token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_180 — Bokken Saber

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “When Attack Ends: Give an Advantage token to this unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_181 — Mark My Words

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attach to a damaged unit.
> Attached unit gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_182 — Unfettered Ambition

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: For each upgrade on attached unit not named Advantage (including this one), give an Advantage token to attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

