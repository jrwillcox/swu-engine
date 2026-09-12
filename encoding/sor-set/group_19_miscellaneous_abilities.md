# sor-set:19 — Miscellaneous abilities

- **Group id (paste this):** `sor-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_174 | Smoke and Cinders | Event | 5 |  |  |
| SOR_177 | Bib Fortuna | Unit | 2 | 1/3 | Shielded |
| SOR_185 | Chimaera | Unit | 8 | 8/7 | Shielded |
| SOR_190 | Lothal Insurgent | Unit | 2 | 3/2 |  |
| SOR_197 | Lando Calrissian | Unit | 6 | 6/5 | Saboteur |
| SOR_212 | Strafing Gunship | Unit | 4 | 3/4 |  |
| SOR_216 | Disarm | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SOR_174 — Smoke and Cinders

**Type/Stats:** Event, cost 5  |  Traits: Disaster

**Rules text:**

> Each player discards all but 2 cards (of their choice) from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_177 — Bib Fortuna

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Twi'lek, Underworld

**Rules text:**

> Shielded (When you play this unit, give him a Shield token.)
> 
> Action [Exhaust]: Play an event from your hand. It costs [1 resource] less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_185 — Chimaera

**Type/Stats:** Unit, cost 8, 8/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> 
> On Attack: Name a card. An opponent reveals their hand and discards a card with that name from it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_190 — Lothal Insurgent

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Rebel

**Rules text:**

> When Played: If you played another card this phase, each opponent draws a card then discards a random card from their hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_197 — Lando Calrissian

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Fringe, Official

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> 
> When Played: Return up to 2 friendly resources to their owners' hands.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_212 — Strafing Gunship

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> This unit can attack units in the ground arena. While this unit is attacking a ground unit, the defender gets –2/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_216 — Disarm

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Give an enemy unit –4/–0 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

