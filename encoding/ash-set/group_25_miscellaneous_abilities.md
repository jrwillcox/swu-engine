# ash-set:25 — Miscellaneous abilities

- **Group id (paste this):** `ash-set:25`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_28 | Paz Vizsla | Unit | 5 | 4/7 | Sentinel |
| ASH_34 | Wicket | Unit | 1 | 3/3 | Saboteur |
| ASH_40 | Poe Dameron | Unit | 2 | 3/3 | Sentinel |
| ASH_47 | Gar Saxon | Unit | 3 | 3/4 |  |
| ASH_54 | Pointless to Resist | Upgrade | 1 |  |  |
| ASH_56 | Huyang | Unit | 2 | 2/4 |  |
| ASH_58 | Duchess's Protector | Unit | 3 | 2/3 |  |

## Per-card analysis & acceptance criteria

### ASH_28 — Paz Vizsla

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Mandalorian

**Rules text:**

> Sentinel
> When Defeated: If this unit wasn't defeated by combat damage, create 2 Mandalorian tokens.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_34 — Wicket

**Type/Stats:** Unit, cost 1, 3/3  |  Traits: Ewok

**Rules text:**

> Saboteur
> This unit can't attack bases.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_40 — Poe Dameron

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Resistance

**Rules text:**

> All units lose Sentinel.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_47 — Gar Saxon

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Mandalorian, Trooper

**Rules text:**

> When you play an upgrade on this unit: You may create a Mandalorian token. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_54 — Pointless to Resist

**Type/Stats:** Upgrade, cost 1  |  Traits: Condition

**Rules text:**

> Attached unit gets –3/–0 while attacking a base.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_56 — Huyang

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Droid, Jedi

**Rules text:**

> On Attack: You may give an upgraded unit –4/–0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_58 — Duchess's Protector

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Mandalorian

**Rules text:**

> When Defeated: Create a Mandalorian token.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

