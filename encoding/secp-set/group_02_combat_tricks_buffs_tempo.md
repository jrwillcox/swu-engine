# secp-set:02 — Combat tricks, buffs & tempo

- **Group id (paste this):** `secp-set:02`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SECP_1 | Cantwell Arrestor Cruiser | Unit | 7 | 6/7 |  |
| SECP_8 | Jar Jar Binks | Unit | 2 | 2/1 | Plot |
| SECP_13 | Kazuda Xiono | Unit | 4 | 2/6 | Raid |
| SECP_16 | Lurking Snub Fighter | Unit | 3 | 2/3 | Plot |

## Per-card analysis & acceptance criteria

### SECP_1 — Cantwell Arrestor Cruiser

**Type/Stats:** Unit, cost 7, 6/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may disclose VigilanceVigilanceVillainy . If you do, exhaust an enemy unit. That unit can't ready while this unit is in play.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SECP_8 — Jar Jar Binks

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Gungan, Naboo, Official, Republic

**Rules text:**

> When Played: You may give another friendly unit +2/+2 for this phase.
> Plot 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SECP_13 — Kazuda Xiono

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Resistance

**Rules text:**

> Raid 2 
> While you control fewer resources than an opponent, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SECP_16 — Lurking Snub Fighter

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: You may exhaust a unit.
> Plot 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

