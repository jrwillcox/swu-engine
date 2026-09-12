# han-solo:05 — Combat tricks, buffs & tempo

- **Group id (paste this):** `han-solo:05`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_210 | The Mandalorian | Unit | 5 | 5/6 | Piloting |
| JTL_217 | Death Space Skirmisher | Unit | 3 | 3/3 |  |
| JTL_249 | Millennium Falcon | Unit | 3 | 3/4 |  |

## Per-card analysis & acceptance criteria

### JTL_210 — The Mandalorian

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Bounty Hunter, Mandalorian, Pilot

**Rules text:**

> When played as a unit: Exhaust up to 2 ground units.
> Piloting [2 resources Cunning]
> When played as an upgrade: Exhaust an enemy unit in this arena.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_217 — Death Space Skirmisher

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: If you control another space unit, you may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_249 — Millennium Falcon

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> You may play or deploy 1 additional Pilot on this unit.
> This unit gets +1/+0 for each Pilot on it.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

