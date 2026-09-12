# ash-set:28 — Miscellaneous abilities

- **Group id (paste this):** `ash-set:28`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_140 | Stronger Together | Event | 4 |  |  |
| ASH_149 | Eviscerator | Unit | 8 | 9/7 |  |
| ASH_150 | Deadly Vulnerability | Upgrade | 1 |  | Overwhelm |
| ASH_177 | Onyx Cinder | Unit | 6 | 6/6 | Hidden |
| ASH_191 | Shin Hati's Fiend Fighter | Unit | 2 | 3/1 |  |
| ASH_195 | Helgait | Unit | 5 | 6/4 |  |
| ASH_199 | There Is No Conflict | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### ASH_140 — Stronger Together

**Type/Stats:** Event, cost 4  |  Traits: Learned

**Rules text:**

> Create 2 Mandalorian tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_149 — Eviscerator

**Type/Stats:** Unit, cost 8, 9/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Advantage tokens on friendly units lose all abilities. (They aren't defeated after combat.)
> When Played/On Attack: Give 2 Advantage tokens to each other friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_150 — Deadly Vulnerability

**Type/Stats:** Upgrade, cost 1  |  Traits: Condition

**Rules text:**

> If attached unit would take damage, it takes twice as much damage instead.
> While attached unit is defending, the attacker loses Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_177 — Onyx Cinder

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Transport, Vehicle

**Rules text:**

> Hidden
> Other friendly units gain Hidden.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_191 — Shin Hati's Fiend Fighter

**Type/Stats:** Unit, cost 2, 3/1  |  Traits: Fighter, Vehicle

**Rules text:**

> When Defeated: You may give 2 Advantage tokens to a unit. If this unit wasn't defeated by combat damage, you may give 3 Advantage tokens to that unit instead.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_195 — Helgait

**Type/Stats:** Unit, cost 5, 6/4  |  Traits: Separatist

**Rules text:**

> When Defeated: You may distribute a number of Advantage tokens equal to this unit's power among friendly units (divided as you choose).

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_199 — There Is No Conflict

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> When Played: Return any number of other upgrades on attached unit to their owners' hands.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

