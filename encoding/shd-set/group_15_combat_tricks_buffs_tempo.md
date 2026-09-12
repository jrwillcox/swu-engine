# shd-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_104 | Inspiring Mentor | Upgrade | 2 |  |  |
| SHD_112 | Gamorrean Retainer | Unit | 2 | 3/2 | Sentinel |
| SHD_116 | Outlaw Corona | Unit | 3 | 3/5 | Bounty |
| SHD_117 | Reputable Hunter | Unit | 3 | 3/4 | Bounty |
| SHD_122 | Arquitens Assault Cruiser | Unit | 8 | 7/8 | Ambush |
| SHD_137 | Punishing One | Unit | 3 | 3/4 |  |
| SHD_140 | Trandoshan Hunters | Unit | 5 | 6/4 | Bounty, Overwhelm |

## Per-card analysis & acceptance criteria

### SHD_104 — Inspiring Mentor

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains, “On Attack/When Defeated: Give an Experience token to another friendly unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_112 — Gamorrean Retainer

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Underworld

**Rules text:**

> While you control another Command unit, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_116 — Outlaw Corona

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Capital Ship, Underworld, Vehicle

**Rules text:**

> Bounty — Put the top card of your deck into play as a resource. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_117 — Reputable Hunter

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Bounty Hunter

**Rules text:**

> If an enemy unit has a Bounty, this unit costs 1 resource less to play.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_122 — Arquitens Assault Cruiser

**Type/Stats:** Unit, cost 8, 7/8  |  Traits: Capital Ship, Vehicle

**Rules text:**

> Ambush
> When this unit attacks and defeats a non-leader unit: Put the defeated unit into play as a resource under your control.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_137 — Punishing One

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When an upgraded enemy unit is defeated: You may ready this unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_140 — Trandoshan Hunters

**Type/Stats:** Unit, cost 5, 6/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played: If an enemy unit has a Bounty, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

