# sor-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_191 | Vanguard Ace | Unit | 2 | 1/1 |  |
| SOR_208 | Outer Rim Headhunter | Unit | 2 | 1/3 | Raid |
| SOR_211 | Gamorrean Guards | Unit | 4 | 4/4 | Sentinel |
| SOR_214 | Smuggling Compartment | Upgrade | 1 |  |  |
| SOR_215 | Snapshot Reflexes | Upgrade | 1 |  |  |
| SOR_221 | Outmaneuver | Event | 3 |  |  |
| SOR_249 | Frontier AT-RT | Unit | 4 | 3/5 | Ambush |

## Per-card analysis & acceptance criteria

### SOR_191 — Vanguard Ace

**Type/Stats:** Unit, cost 2, 1/1  |  Traits: Fighter, New Republic, Vehicle

**Rules text:**

> When Played: For each other card you played this phase, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_208 — Outer Rim Headhunter

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> 
> On Attack: If you control a leader unit, you may exhaust a non-leader unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_211 — Gamorrean Guards

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Underworld

**Rules text:**

> While you control another [Cunning] unit, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_214 — Smuggling Compartment

**Type/Stats:** Upgrade, cost 1  |  Traits: Modification

**Rules text:**

> Attach to a VEHICLE unit.
> 
> Attached unit gains: "On Attack: Ready a resource."

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_215 — Snapshot Reflexes

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> When Played: You may attack with attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_221 — Outmaneuver

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Choose an arena (ground or space). Exhaust each unit in that arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_249 — Frontier AT-RT

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Vehicle, Walker

**Rules text:**

> While you control another VEHICLE unit, this unit gains Ambush. (After you play this unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

