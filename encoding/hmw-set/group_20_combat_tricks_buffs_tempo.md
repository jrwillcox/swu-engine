# hmw-set:20 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_234 | Ritual Dragon | Unit | 8 | 6/9 | Saboteur |
| HMW_255 | C-3PO | Unit | 2 | 2/3 |  |
| HMW_256 | Jedi Interceptor | Unit | 2 | 2/2 |  |
| HMW_257 | Ewok Archers | Unit | 3 | 2/5 | Ambush |
| HMW_259 | Pack Guardian | Unit | 4 | 5/4 | Sentinel |
| HMW_261 | Ben Kenobi | Unit | 5 | 5/5 |  |
| HMW_264 | Heroic Bravery | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### HMW_234 — Ritual Dragon

**Type/Stats:** Unit, cost 8, 6/9  |  Traits: Creature

**Rules text:**

> Saboteur
> While you control a Tatooine base, friendly units enter play ready (including this one).

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_255 — C-3PO

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Droid, Rebel

**Rules text:**

> When Played: You may give an Ewok unit +2/+2 for this phase. You may give a Rebel unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_256 — Jedi Interceptor

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> While you control 6 or more resources, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_257 — Ewok Archers

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Ewok

**Rules text:**

> While you control another unit that costs 3 or less, this unit gains Ambush. (When you play this unit, it may attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_259 — Pack Guardian

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Creature

**Rules text:**

> While this unit is ready, it gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust', 'keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_261 — Ben Kenobi

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Force, Fringe, Jedi

**Rules text:**

> When Played: You may exhaust a unit with 3 or less power.
> On Attack: You may heal 3 damage from another unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'ready_exhaust'].

**Existing primitives that should suffice:** Heal, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_264 — Heroic Bravery

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: If attached unit is a Heroism unit, give a Shield token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

