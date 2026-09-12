# law-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_39 | Latts Razzi | Unit | 3 | 2/1 |  |
| LAW_43 | Shadow Cloaking | Event | 5 |  |  |
| LAW_46 | Chirrut Îmwe | Unit | 6 | 8/6 | Saboteur |
| LAW_55 | Chopper | Unit | 2 | 1/2 | Raid |
| LAW_59 | Highsinger | Unit | 3 | 4/2 |  |
| LAW_61 | Asajj Ventress | Unit | 5 | 3/3 |  |
| LAW_69 | The Ghost | Unit | 6 | 4/4 |  |

## Per-card analysis & acceptance criteria

### LAW_39 — Latts Razzi

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: Give a Shield token or an Experience token to this unit. Then, she deals damage equal to her power to an enemy ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_43 — Shadow Cloaking

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Ready a unit and give a Shield token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_46 — Chirrut Îmwe

**Type/Stats:** Unit, cost 6, 8/6  |  Traits: Force, Rebel

**Rules text:**

> Saboteur
> When Attack Ends: If this unit dealt combat damage to a base, you may heal 4 damage from another unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_55 — Chopper

**Type/Stats:** Unit, cost 2, 1/2  |  Traits: Droid, Rebel, Spectre

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: Give an Experience token to this unit. If you control a Cunning or Vigilance unit, give 2 Experience tokens to him instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_59 — Highsinger

**Type/Stats:** Unit, cost 3, 4/2  |  Traits: Bounty Hunter, Droid, Underworld

**Rules text:**

> When Played: Give an Experience token to another friendly Command unit.
> When Defeated: Give an Experience token to a friendly Aggression unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_61 — Asajj Ventress

**Type/Stats:** Unit, cost 5, 3/3  |  Traits: Bounty Hunter, Force, Underworld

**Rules text:**

> When Played: You may ready another Bounty Hunter unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_69 — The Ghost

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Rebel, Spectre, Transport, Vehicle

**Rules text:**

> When Played: You may give an Experience token and a Shield token to a unit. If you control a Vigilance or Aggression unit, you may give an Experience token and a Shield token to each of up to 2 units instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

