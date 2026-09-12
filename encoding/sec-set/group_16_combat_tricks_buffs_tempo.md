# sec-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_179 | Aggressive Negotiations | Event | 3 |  |  |
| SEC_190 | Soulless One | Unit | 3 | 3/3 |  |
| SEC_196 | No One Ever Knew | Event | 2 |  |  |
| SEC_202 | Rebel Propagandist | Unit | 3 | 2/4 | Saboteur |
| SEC_204 | Blue Ace | Unit | 4 | 4/5 | Ambush |
| SEC_207 | Lightmaker | Unit | 5 | 3/4 | Raid |
| SEC_212 | Libertine | Unit | 4 | 3/7 |  |

## Per-card analysis & acceptance criteria

### SEC_179 — Aggressive Negotiations

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Attack with a unit. For this attack, it gets +1/+0 for each card in your hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_190 — Soulless One

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> On Attack: You may disclose CunningCunningVillainy (reveal cards from your hand with these aspect icons among them). If you do, ready 2 resources.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_196 — No One Ever Knew

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> For each friendly Official unit, exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_202 — Rebel Propagandist

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Official, Rebel

**Rules text:**

> When Played/When Defeated: Give another friendly unit +1/+0 and Saboteur for this phase. (When that unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_204 — Blue Ace

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> Ambush
> On Attack: Ready an exhausted enemy unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_207 — Lightmaker

**Type/Stats:** Unit, cost 5, 3/4  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Raid 4
> When Defeated: Choose an arena. Exhaust each enemy unit in that arena.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_212 — Libertine

**Type/Stats:** Unit, cost 4, 3/7  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> This unit gets +1/+0 for each captured card it's guarding.
> When Played: Choose an enemy unit and a non-leader friendly unit. The enemy unit captures the friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

