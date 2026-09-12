# jtl-set:26 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:26`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_242 | Shuttle ST-149 | Unit | 4 | 3/4 | Shielded |
| JTL_243 | Quasar TIE Carrier | Unit | 6 | 5/7 |  |
| JTL_244 | There Is No Escape | Event | 2 |  |  |
| JTL_252 | Tantive IV | Unit | 7 | 5/7 | Sentinel |
| JTL_254 | Dedicated Wingmen | Event | 4 |  |  |
| JTL_259 | Retrofitted Airspeeder | Unit | 5 | 3/6 | Ambush |
| JTL_260 | Death Star Plans | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### JTL_242 — Shuttle ST-149

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> When Played/When Defeated: You may take control of a token upgrade on a unit and attach it to a different eligible unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_243 — Quasar TIE Carrier

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> On Attack: Create a TIE Fighter token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_244 — There Is No Escape

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Choose up to 3 units. Those units lose all abilities and can't gain abilities for this round.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_252 — Tantive IV

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> When Played: Create an X-Wing token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_254 — Dedicated Wingmen

**Type/Stats:** Event, cost 4  |  Traits: Supply

**Rules text:**

> Create 2 X-Wing tokens.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_259 — Retrofitted Airspeeder

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Speeder, Vehicle

**Rules text:**

> Ambush
> This unit can attack space units.
> While attacking a space unit, this unit gets –1/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_260 — Death Star Plans

**Type/Stats:** Upgrade, cost 2  |  Traits: Item

**Rules text:**

> When attached unit is attacked: The attacking player takes control of this upgrade and attaches it to a unit they control.
> Attached unit gains: “The first unit you play each round costs 2 resources less.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction, control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

