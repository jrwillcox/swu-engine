# ash-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_41 | Outcast | Unit | 2 | 1/4 |  |
| ASH_44 | Barriss Offee | Unit | 3 | 3/4 |  |
| ASH_49 | Shin Hati | Unit | 5 | 6/6 | Sentinel |
| ASH_51 | Reinforcing Light Cruiser | Unit | 6 | 5/5 | Restore |
| ASH_52 | Chimaera | Unit | 7 | 6/6 |  |
| ASH_57 | Lothal E-Wing | Unit | 2 | 2/3 | Restore |
| ASH_64 | The Armorer | Unit | 6 | 5/5 | Shielded |

## Per-card analysis & acceptance criteria

### ASH_41 — Outcast

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When a friendly unit enters play (including this one): It gets +1/+0 for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_44 — Barriss Offee

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Fringe

**Rules text:**

> When Played: Heal up to 2 damage from a unit. Give an Advantage token to it for each damage healed this way.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_49 — Shin Hati

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Force

**Rules text:**

> While this is the only friendly non-leader ground unit, she gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_51 — Reinforcing Light Cruiser

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> When Played: You may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_52 — Chimaera

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may choose a friendly unit and an enemy non-leader unit. If you do, defeat those units.
> When an enemy unit is defeated: Heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'defeat'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_57 — Lothal E-Wing

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fighter, New Republic, Vehicle

**Rules text:**

> While an enemy unit is upgraded, this unit gains Restore 2. (When this unit attacks, heal 2 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_64 — The Armorer

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Mandalorian

**Rules text:**

> Shielded (When you play this unit, give a Shield token to her.)
> When Played: Give a Shield token to each friendly unit with Shielded (including this one).

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

