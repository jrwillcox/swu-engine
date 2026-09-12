# lof-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_180 | Deceptive Shade | Unit | 2 | 2/3 | Ambush |
| LOF_191 | BD-1 | Unit | 1 | 1/3 | Hidden, Saboteur |
| LOF_195 | Vernestra Rwoh | Unit | 3 | 3/4 |  |
| LOF_203 | Premonition of Doom | Event | 3 |  |  |
| LOF_205 | Force Speed | Event | 1 |  |  |
| LOF_206 | Babu Frik | Unit | 1 | 1/4 |  |
| LOF_212 | Life Wind Sage | Unit | 4 | 3/5 | Raid |

## Per-card analysis & acceptance criteria

### LOF_180 — Deceptive Shade

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Sith, Undead

**Rules text:**

> When Defeated: The next unit you play this phase gains Ambush for this phase.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_191 — BD-1

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Fringe

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When Played: Choose another friendly unit. While this unit is in play, the chosen unit gets +1/+0 and gains Saboteur.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_195 — Vernestra Rwoh

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi

**Rules text:**

> When Played: You may use the Force (lose your Force token). If you do, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_203 — Premonition of Doom

**Type/Stats:** Event, cost 3  |  Traits: Force

**Rules text:**

> The next time you take the initiative this phase, exhaust all units.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_205 — Force Speed

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Attack with a unit. For this attack, it gains: “On Attack: Return any number of non-<uq> (non-unique) upgrades attached to the defender to their owners' hands.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_206 — Babu Frik

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: You may attack with a friendly Droid unit. For this attack, it deals damage equal to its remaining HP instead of its power.

**Mechanical analysis:** trigger archetype `activated`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_212 — Life Wind Sage

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force

**Rules text:**

> While an enemy unit is exhausted, this unit gains Raid 2. (This unit gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

