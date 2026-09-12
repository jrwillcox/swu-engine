# law-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_73 | Patient Hunter | Unit | 4 | 3/3 |  |
| LAW_74 | Maz Kanata | Unit | 5 | 4/4 |  |
| LAW_87 | Jango Fett | Unit | 6 | 6/5 | Shielded |
| LAW_88 | Anakin Skywalker | Unit | 2 | 2/4 |  |
| LAW_91 | Val | Unit | 2 | 2/4 |  |
| LAW_95 | Finn | Unit | 6 | 6/5 | Ambush |
| LAW_97 | Imperial Door Technician | Unit | 1 | 2/2 |  |

## Per-card analysis & acceptance criteria

### LAW_73 — Patient Hunter

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Bounty Hunter

**Rules text:**

> When the regroup phase starts: You may give an Experience token to a non-leader unit. If you do, that unit can't ready during this regroup phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_74 — Maz Kanata

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Underworld

**Rules text:**

> When Attack Ends: If this unit survived, search the top 5 cards of your deck for an Underworld unit and play it. It costs 4 resources less and enters play ready. At the start of the regroup phase, put that unit on the bottom of your deck (if it is still in play).

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_87 — Jango Fett

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> On Attack: If this unit is upgraded, exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_88 — Anakin Skywalker

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Force

**Rules text:**

> When a friendly unit's attack ends: If no other units have attacked this phase, you may return it to its owner's hand. If you do, heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal', 'return_hand'].

**Existing primitives that should suffice:** Heal, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_91 — Val

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Underworld

**Rules text:**

> When Played: Give a Shield token to another friendly unit.
> When Defeated: Give a Shield token to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_95 — Finn

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Resistance

**Rules text:**

> Ambush (When you play this unit, he may attack an enemy unit.)
> On Attack: You may give a Shield token to a non-<uq> unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_97 — Imperial Door Technician

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Imperial, Trooper

**Rules text:**

> When Defeated: Heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

