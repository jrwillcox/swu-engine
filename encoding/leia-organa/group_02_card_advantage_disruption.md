# leia-organa:02 — Card advantage & disruption

- **Group id (paste this):** `leia-organa:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_119 | Rogue One | Unit | 3 | 3/3 |  |
| LAW_145 | R2-D2 | Unit | 2 | 1/3 |  |
| LAW_166 | Putting a Team Together | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### LAW_119 — Rogue One

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When a friendly unit is defeated: Look at the top 2 cards of your deck. Put any number of them on the bottom of your deck and the rest on top in any order.

**Mechanical analysis:** trigger archetype `static`; effect families ['search'].

**Existing primitives that should suffice:** deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_145 — R2-D2

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Droid, Rebel

**Rules text:**

> When Played: Search the top 5 cards of your deck for a unit that shares an aspect with a friendly unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_166 — Putting a Team Together

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Search the top 8 cards of your deck for a Vigilance, Aggression, or Cunning unit, reveal it, and draw it. (Put the rest of the cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

