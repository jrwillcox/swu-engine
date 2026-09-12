# ash-set:21 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_207 | Heroic Purrgil | Unit | 5 | 3/6 | Ambush |
| ASH_208 | Sabine Wren | Unit | 5 | 4/5 | Shielded |
| ASH_214 | Amnesty Officer | Unit | 2 | 2/2 |  |
| ASH_216 | Mandalorian Scout | Unit | 2 | 3/3 |  |
| ASH_217 | Mayor's Majordomo | Unit | 2 | 1/4 |  |
| ASH_219 | Jod Na Nawood | Unit | 3 | 4/3 | Sentinel |
| ASH_221 | Helix Starfighter | Unit | 4 | 3/3 |  |

## Per-card analysis & acceptance criteria

### ASH_207 — Heroic Purrgil

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Creature

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> While attacking using Ambush, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_208 — Sabine Wren

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Jedi, Mandalorian, Spectre

**Rules text:**

> Shielded (When you play this unit, give a Shield token to her.)
> When 1 or more upgrades attach to this unit (including from Shielded): You may exhaust a ground unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_214 — Amnesty Officer

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: New Republic, Official

**Rules text:**

> When Played: You may exhaust a unit with one or more keywords.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_216 — Mandalorian Scout

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Mandalorian

**Rules text:**

> When Defeated: Exhaust a ready friendly resource.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_217 — Mayor's Majordomo

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Official

**Rules text:**

> Action [Exhaust, discard a card from your hand]: Exhaust a unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_219 — Jod Na Nawood

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Force, Underworld

**Rules text:**

> Sentinel
> When Played: You may pay 4 resources. If you do, choose an arena. Exhaust each unit in that arena.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_221 — Helix Starfighter

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: If an opponent controls a space unit, give a Shield token to this unit. Otherwise, give 2 Advantage tokens to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

