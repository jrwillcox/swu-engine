# lof-set:09 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_15 | Cal Kestis | Leader | 4 | 3/4 |  |
| LOF_17 | Darth Revan | Leader | 5 | 3/6 | Restore |
| LOF_33 | Nameless Terror | Unit | 3 | 3/3 |  |
| LOF_47 | T-6 Shuttle 1974 | Unit | 3 | 3/4 |  |
| LOF_48 | Itinerant Warrior | Unit | 4 | 4/4 | Shielded |
| LOF_49 | Jedi Guardian | Unit | 5 | 4/8 |  |
| LOF_50 | Plo Koon | Unit | 6 | 6/8 | Grit |

## Per-card analysis & acceptance criteria

### LOF_15 — Cal Kestis

**Type/Stats:** Leader, cost 4, 3/4  |  Traits: Force, Fringe

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: An opponent chooses a ready unit they control. Exhaust that unit.
> On Attack: An opponent chooses a ready unit they control. Exhaust that unit.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** force-token, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_17 — Darth Revan

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Sith

**Rules text:**

> When a friendly unit attacks and defeats a unit: You may exhaust this leader. If you do, give an Experience token to that friendly unit.
> Restore 1
> When a friendly unit attacks and defeats a unit: You may give an Experience token to that friendly unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_33 — Nameless Terror

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Creature

**Rules text:**

> When Played: You may exhaust a Force unit.
> On Attack: Each enemy unit loses the Force trait for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_47 — T-6 Shuttle 1974

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> When this unit is attacked (before damage is dealt): You may give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_48 — Itinerant Warrior

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Force, Jedi

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> When Played: You may use the Force (lose your Force token). If you do, heal 3 damage from a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_49 — Jedi Guardian

**Type/Stats:** Unit, cost 5, 4/8  |  Traits: Force, Jedi

**Rules text:**

> While this unit is defending, it gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_50 — Plo Koon

**Type/Stats:** Unit, cost 6, 6/8  |  Traits: Force, Jedi, Republic

**Rules text:**

> While the Force is with you, this unit gains Grit. (He gets +1/+0 for each damage on him.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

