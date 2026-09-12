# ibh-set:02 — Card advantage & disruption

- **Group id (paste this):** `ibh-set:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IBH_52 | Watch This | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### IBH_52 — Watch This

**Type/Stats:** Event, cost 6  |  Traits: Gambit

**Rules text:**

> Return a non-leader unit that costs 6 or less to its owner's hand. Exhaust each other enemy unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

