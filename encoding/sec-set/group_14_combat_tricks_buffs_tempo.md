# sec-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_109 | Diplomatic Envoy | Unit | 2 | 2/2 | Ambush |
| SEC_110 | GNK Power Droid | Unit | 2 | 1/3 |  |
| SEC_119 | Crucible | Unit | 6 | 5/5 |  |
| SEC_122 | Vuutun Palaa | Unit | 9 | 7/7 |  |
| SEC_134 | Hunting Assassin Droid | Unit | 3 | 3/4 | Raid |
| SEC_135 | Muckraker Crab Droid | Unit | 3 | 4/3 |  |
| SEC_137 | Dryden Vos | Unit | 4 | 2/5 |  |

## Per-card analysis & acceptance criteria

### SEC_109 — Diplomatic Envoy

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> When Played: You may disclose Command (reveal a card from your hand with this aspect icon). If you do, the next unit you play this phase gains Ambush for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_110 — GNK Power Droid

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Droid

**Rules text:**

> On Attack: The next unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_119 — Crucible

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Jedi, Transport, Vehicle

**Rules text:**

> When Played/When Defeated: Give an Experience token to each other friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_122 — Vuutun Palaa

**Type/Stats:** Unit, cost 9, 7/7  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> This unit costs 1 resource less to play for each friendly Droid unit.
> Each friendly Droid unit may be exhausted to pay costs as if it were a resource.

**Mechanical analysis:** trigger archetype `static`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_134 — Hunting Assassin Droid

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Bounty Hunter, Droid, Underworld

**Rules text:**

> While an enemy unit is damaged, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_135 — Muckraker Crab Droid

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Droid, Separatist

**Rules text:**

> While this unit is ready, it can't be attacked.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_137 — Dryden Vos

**Type/Stats:** Unit, cost 4, 2/5  |  Traits: Underworld

**Rules text:**

> On Attack: You may double this unit's power for this attack. If you do, this unit doesn't ready during the next regroup phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

