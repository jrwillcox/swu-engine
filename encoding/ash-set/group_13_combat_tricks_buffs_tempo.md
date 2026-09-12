# ash-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_13 | Ezra Bridger | Leader | 5 | 3/6 | Saboteur |
| ASH_15 | Emperor Palpatine | Leader | 7 | 4/8 |  |
| ASH_16 | Shin Hati | Leader | 6 | 4/6 |  |
| ASH_17 | Greef Karga | Leader | 6 | 4/7 |  |
| ASH_30 | Marrok | Unit | 3 | 2/6 | Saboteur, Sentinel |
| ASH_31 | Hera Syndulla | Unit | 3 | 3/4 |  |
| ASH_39 | Baylan Skoll | Unit | 6 | 6/6 | Overwhelm |

## Per-card analysis & acceptance criteria

### ASH_13 — Ezra Bridger

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Jedi, Rebel, Spectre

**Rules text:**

> When a friendly unit's attack ends: If it dealt 3 or more combat damage to a base, you may exhaust this leader. If you do, give an Advantage token to a different unit.
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When a friendly unit's attack ends: If it dealt 3 or more combat damage to a base, you may give an Advantage token to a different unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_15 — Emperor Palpatine

**Type/Stats:** Leader, cost 7, 4/8  |  Traits: Force, Imperial, Official, Sith

**Rules text:**

> Action [Exhaust]: Choose an exhausted friendly unit. Give an Advantage token to it for each other friendly unit.
> On Attack: You may choose another exhausted friendly unit. If you do, give an Advantage token to it for each other friendly unit.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_16 — Shin Hati

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Force

**Rules text:**

> When a friendly unit's attack ends: You may exhaust this leader. If you do, exhaust a unit that costs less than the amount of combat damage dealt to a base this attack.
> When a friendly unit's attack ends: You may exhaust a unit that costs less than the amount of combat damage dealt to a base this attack. Use this ability only once each round.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_17 — Greef Karga

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Official

**Rules text:**

> When you play or create a unit: You may exhaust this leader. If you do, give an Advantage token to that unit.
> When you play or create a unit: Give an Advantage token to that unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_30 — Marrok

**Type/Stats:** Unit, cost 3, 2/6  |  Traits: Force, Inquisitor

**Rules text:**

> Sentinel
> While this unit is upgraded, he loses Sentinel and gains Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_31 — Hera Syndulla

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: New Republic, Spectre, Twi'lek

**Rules text:**

> When Attack Ends: If this unit dealt combat damage to a base, heal that much damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_39 — Baylan Skoll

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Force

**Rules text:**

> Overwhelm
> When Played/When Attack Ends: If an enemy base was damaged this phase, give an Advantage token to a unit. If a friendly upgrade was defeated this phase, you may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

