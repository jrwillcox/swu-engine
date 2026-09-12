# sor-set:04 — Direct damage & removal

- **Group id (paste this):** `sor-set:04`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_173 | Bombing Run | Event | 5 |  |  |
| SOR_179 | Boba Fett | Unit | 3 | 3/5 |  |
| SOR_182 | Bossk | Unit | 5 | 4/5 | Ambush |
| SOR_223 | Don't Get Cocky | Event | 4 |  |  |
| SOR_235 | Galactic Ambition | Event | 7 |  |  |

## Per-card analysis & acceptance criteria

### SOR_173 — Bombing Run

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Choose an arena (ground or space). Deal 3 damage to each unit in that arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_179 — Boba Fett

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> On Attack: If this unit is attacking an exhausted unit that didn't enter play this round, deal 3 damage to the defender.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_182 — Bossk

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Ambush (After you play this unit, he may ready and attack an enemy unit.)
> 
> When you play an event: You may deal 2 damage to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_223 — Don't Get Cocky

**Type/Stats:** Event, cost 4  |  Traits: Gambit

**Rules text:**

> Choose a unit. One at a time, reveal cards from your deck until you choose to stop or have revealed 7 cards. If the combined cost of the revealed cards is 7 or less, deal that much damage to the chosen unit. Put the revealed cards on the bottom of your deck in a random order.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_235 — Galactic Ambition

**Type/Stats:** Event, cost 7  |  Traits: Innate

**Rules text:**

> Play a non-[Heroism] unit from your hand for free. Deal damage to your base equal to its cost.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

