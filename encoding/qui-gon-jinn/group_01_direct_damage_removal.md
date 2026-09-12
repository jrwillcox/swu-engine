# qui-gon-jinn:01 — Direct damage & removal

- **Group id (paste this):** `qui-gon-jinn:01`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_198 | Stinger Mantis | Unit | 5 | 4/6 |  |
| SOR_219 | Sneak Attack | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LOF_198 — Stinger Mantis

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to an exhausted unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_219 — Sneak Attack

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Play a unit from your hand. It costs [3 resources] less and enters play ready. At the start of the regroup phase, defeat it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

