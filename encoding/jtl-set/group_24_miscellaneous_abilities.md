# jtl-set:24 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:24`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_99 | Veteran Fleet Officer | Unit | 3 | 2/1 |  |
| JTL_100 | Poe Dameron | Unit | 4 | 3/3 | Piloting |
| JTL_105 | The Starhawk | Unit | 9 | 6/9 | Ambush |
| JTL_117 | General Draven | Unit | 5 | 2/5 |  |
| JTL_129 | Focus Fire | Event | 4 |  |  |
| JTL_130 | Timely Reinforcements | Event | 5 |  | Sentinel |
| JTL_131 | Turbolaser Salvo | Event | 7 |  |  |

## Per-card analysis & acceptance criteria

### JTL_99 — Veteran Fleet Officer

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Resistance

**Rules text:**

> When Played: Create an X-Wing token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_100 — Poe Dameron

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Pilot, Resistance

**Rules text:**

> When played as a unit: Create an X-Wing token. You may attach this unit as an upgrade to a friendly Vehicle unit without a Pilot on it.
> Piloting [2 resources Command Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_105 — The Starhawk

**Type/Stats:** Unit, cost 9, 6/9  |  Traits: Capital Ship, New Republic, Vehicle

**Rules text:**

> Ambush
> While paying costs, you pay half as many resources, rounded up.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_117 — General Draven

**Type/Stats:** Unit, cost 5, 2/5  |  Traits: Official, Rebel

**Rules text:**

> When Played/On Attack: Create an X-Wing token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_129 — Focus Fire

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Choose a unit. Each friendly Vehicle unit in the same arena deals damage equal to its power to that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_130 — Timely Reinforcements

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Choose an opponent. For every 2 resources they control, create an X-Wing token and give it Sentinel for this phase. (Units in its arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_131 — Turbolaser Salvo

**Type/Stats:** Event, cost 7  |  Traits: Tactic

**Rules text:**

> Choose an arena. A friendly space unit deals damage equal to its power to each enemy unit in that arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

