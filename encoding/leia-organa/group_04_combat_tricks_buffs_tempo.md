# leia-organa:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `leia-organa:04`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_111 | Leia's Disguise | Upgrade | 2 |  |  |
| LAW_142 | Scarif Lieutenant | Unit | 1 | 2/1 |  |
| LAW_147 | Jaunty Light Freighter | Unit | 4 | 1/1 |  |
| LAW_152 | C-3PO | Unit | 2 | 1/4 |  |
| LAW_167 | Common Cause | Event | 2 |  |  |
| SEC_252 | Maarva Andor | Unit | 3 | 3/4 |  |

## Per-card analysis & acceptance criteria

### LAW_111 — Leia's Disguise

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains the Underworld trait.
> When Played: If attached unit is Leia Organa, give a Shield token to a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_142 — Scarif Lieutenant

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Rebel, Trooper

**Rules text:**

> When Defeated: Give an Experience token to a friendly Rebel unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_147 — Jaunty Light Freighter

**Type/Stats:** Unit, cost 4, 1/1  |  Traits: Transport, Vehicle

**Rules text:**

> When Played: Give an Experience token to this unit for each different aspect among units you control.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_152 — C-3PO

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Droid, Rebel, Underworld

**Rules text:**

> On Attack: You may give an Experience token to another non-leader unit that shares a Trait with a friendly leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_167 — Common Cause

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Give a unit +1/+1 for this phase for each different aspect among units you control.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_252 — Maarva Andor

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Rebel

**Rules text:**

> When Defeated: Give an Experience token to each friendly Rebel unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

