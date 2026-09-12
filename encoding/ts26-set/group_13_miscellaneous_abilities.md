# ts26-set:13 — Miscellaneous abilities

- **Group id (paste this):** `ts26-set:13`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_66 | Wartime Pirate | Unit | 3 | 4/4 |  |
| TS26_80 | Reveal Intentions | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### TS26_66 — Wartime Pirate

**Type/Stats:** Unit, cost 3, 4/4  |  Traits: Capital Ship, Underworld, Vehicle

**Rules text:**

> On Attack: An opponent deals 1 damage to a unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_80 — Reveal Intentions

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Each player reveals their hand.
> In player order, each player discards a card from the hand of the player to their right. Then, each player draws a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

