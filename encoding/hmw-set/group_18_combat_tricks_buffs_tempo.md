# hmw-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_170 | Han Solo | Unit | 5 | 4/7 |  |
| HMW_176 | Village Troublemaker | Unit | 1 | 2/2 | Hidden, Saboteur |
| HMW_184 | Aggrocrab | Unit | 5 | 6/4 |  |
| HMW_190 | Enraged | Upgrade | 2 |  | Raid |
| HMW_191 | Hunter's Instinct | Upgrade | 3 |  | Grit |
| HMW_203 | Victor Squadron | Unit | 6 | 5/5 |  |
| HMW_208 | Luke Skywalker | Unit | 1 | 1/3 | Raid |

## Per-card analysis & acceptance criteria

### HMW_170 — Han Solo

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Official, Rebel

**Rules text:**

> Action [Exhaust]: Ready another unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_176 — Village Troublemaker

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Ewok

**Rules text:**

> While you control an Endor base, this unit gains Hidden and Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_184 — Aggrocrab

**Type/Stats:** Unit, cost 5, 6/4  |  Traits: Creature

**Rules text:**

> While you have the initiative, this unit costs 1 resource less to play.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_190 — Enraged

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> Attached unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_191 — Hunter's Instinct

**Type/Stats:** Upgrade, cost 3  |  Traits: Innate

**Rules text:**

> If attached unit is a Creature, it gains Grit. (It gets +1/+0 for each damage on it.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_203 — Victor Squadron

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> This unit enters play ready.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_208 — Luke Skywalker

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Force, Fringe

**Rules text:**

> Raid 1
> While it's the first round of the game, this unit enters play ready.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

