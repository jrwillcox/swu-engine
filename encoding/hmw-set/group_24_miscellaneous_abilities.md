# hmw-set:24 — Miscellaneous abilities

- **Group id (paste this):** `hmw-set:24`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_225 | Boba Fett | Unit | 3 | 1/5 | Ambush, Raid, Saboteur |
| HMW_233 | Awakened Exogorth | Unit | 7 | 7/7 | Hidden |
| HMW_243 | Sun Fac | Unit | 2 | 2/3 | Grit |
| HMW_246 | Pyke Sarisa | Unit | 4 | 4/3 | Sentinel |
| HMW_251 | Blockade Ship | Unit | 8 | 5/8 | Sentinel |
| HMW_260 | Queen Amidala | Unit | 4 | 4/4 | Restore |
| HMW_265 | Twi'lek Kalikori | Upgrade | 4 |  |  |

## Per-card analysis & acceptance criteria

### HMW_225 — Boba Fett

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Tusken

**Rules text:**

> Ambush
> When a friendly unit with Ambush enters play: Give it Raid 1 and Saboteur for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_233 — Awakened Exogorth

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Creature

**Rules text:**

> Hidden (This unit can't be attacked if it was played this phase.)
> While this unit is attacking, the defending unit gets –3/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_243 — Sun Fac

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Separatist

**Rules text:**

> When Played: Give a unit Grit for this phase. (It gets +1/+0 for each damage on it.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_246 — Pyke Sarisa

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: Give a unit Sentinel for this phase. (Enemy units in its arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_251 — Blockade Ship

**Type/Stats:** Unit, cost 8, 5/8  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> Enemy ground units get –1/–0 while attacking.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_260 — Queen Amidala

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Naboo, Official

**Rules text:**

> If you control an upgraded base, this unit costs 2 resources less to play.
> Restore 2

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_265 — Twi'lek Kalikori

**Type/Stats:** Upgrade, cost 4  |  Traits: Item

**Rules text:**

> When Played: If attached unit is a Twi'lek, search the top 8 cards of your deck for any number of Twi'lek units with combined cost 5 or less and play each of them for free.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

