# boba-fett:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `boba-fett:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_141 | IG-88 | Unit | 5 | 4/5 | Piloting |
| SOR_184 | Fett's Firespray | Unit | 6 | 5/6 |  |
| SOR_186 | No Good to Me Dead | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### JTL_141 — IG-88

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Bounty Hunter, Droid, Pilot, Underworld

**Rules text:**

> While an enemy unit is damaged, this unit gets +3/+0.
> Piloting [2 resources Aggression Villainy] 
> Attached unit gains: “While an enemy unit is damaged, this unit gets +3/+0.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_184 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: If you control Boba Fett or Jango Fett (as a leader or unit), ready this unit.
> 
> Action [2 resources]: Exhaust a non-unique unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_186 — No Good to Me Dead

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Exhaust a unit. That unit can't ready this round (including during the regroup phase).

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

