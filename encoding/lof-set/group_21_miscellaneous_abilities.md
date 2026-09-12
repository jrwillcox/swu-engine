# lof-set:21 — Miscellaneous abilities

- **Group id (paste this):** `lof-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_128 | Protect the Pod | Event | 4 |  |  |
| LOF_159 | Jedi In Hiding | Unit | 3 | 3/3 | Hidden |
| LOF_186 | Marchion Ro | Unit | 6 | 6/7 | Raid |
| LOF_189 | Liberated by Darkness | Event | 5 |  |  |
| LOF_209 | Tusken Tracker | Unit | 3 | 2/4 | Hidden, Raid |
| LOF_211 | Dooku | Unit | 4 | 5/4 | Hidden |
| LOF_217 | Force Slow | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### LOF_128 — Protect the Pod

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> A friendly non-Vehicle unit deals damage equal to its remaining HP to an enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_159 — Jedi In Hiding

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Force, Jedi

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When Defeated: You may use the Force (lose your Force token). If you do, each opponent discards a card from their hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_186 — Marchion Ro

**Type/Stats:** Unit, cost 6, 6/7  |  Traits: Nihil, Underworld

**Rules text:**

> Each friendly unit's Raid is doubled.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_189 — Liberated by Darkness

**Type/Stats:** Event, cost 5  |  Traits: Force

**Rules text:**

> Use the Force (lose your Force token). If you do, take control of a non-leader unit. At the start of the regroup phase, its owner takes control of it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['—'].

**Existing primitives that should suffice:** control-change, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_209 — Tusken Tracker

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Tusken

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> When Played: Each enemy unit loses Hidden for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_211 — Dooku

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Force, Jedi

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> When Played: Each friendly unit with Hidden can't be attacked for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_217 — Force Slow

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Give an exhausted unit –8/–0 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

