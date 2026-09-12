# ash-set:23 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_240 | Mandalorian Super Commandos | Unit | 3 | 2/5 |  |
| ASH_245 | Eye of Sion | Unit | 7 | 5/8 |  |
| ASH_248 | Neel | Unit | 1 | 1/4 |  |
| ASH_251 | Zealous Soldier | Unit | 2 | 2/3 |  |
| ASH_255 | Anakin Skywalker | Unit | 5 | 6/4 | Hidden, Saboteur |
| ASH_257 | Choose Your Path | Event | 2 |  |  |
| ASH_262 | Faith in the Empire | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### ASH_240 — Mandalorian Super Commandos

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Mandalorian, Trooper

**Rules text:**

> While you control a leader unit, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_245 — Eye of Sion

**Type/Stats:** Unit, cost 7, 5/8  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> Action [Exhaust]: Search the top 8 cards of your deck for a unit that costs the same as or less than this unit's power. Play it for free. It enters play ready.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_248 — Neel

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Fringe

**Rules text:**

> When Played/On Attack: The next unit you play this phase with 1 or less power enters play ready.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_251 — Zealous Soldier

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Rebel, Trooper

**Rules text:**

> When Played: Give an Advantage token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_255 — Anakin Skywalker

**Type/Stats:** Unit, cost 5, 6/4  |  Traits: Force, Jedi

**Rules text:**

> Hidden
> Saboteur
> When Played: Give a Shield token to another friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_257 — Choose Your Path

**Type/Stats:** Event, cost 2  |  Traits: Force, Mandalorian

**Rules text:**

> Choose one:
> If you control a Force unit, heal 5 damage from your base.
> If you control a Mandalorian unit, create a Mandalorian token and give an Advantage token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal, push_modal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_262 — Faith in the Empire

**Type/Stats:** Upgrade, cost 2  |  Traits: Imperial

**Rules text:**

> This upgrade costs 1 resource less to play on an Imperial unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

