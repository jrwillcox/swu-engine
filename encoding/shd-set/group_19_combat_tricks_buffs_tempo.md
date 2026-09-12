# shd-set:19 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:19`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_217 | Tobias Beckett | Unit | 4 | 4/5 | Smuggle |
| SHD_227 | Look the Other Way | Event | 0 |  |  |
| SHD_230 | Swoop Down | Event | 1 |  | Saboteur |
| SHD_232 | Relentless Pursuit | Event | 3 |  |  |
| SHD_241 | Kragan Gorr | Unit | 6 | 6/6 |  |

## Per-card analysis & acceptance criteria

### SHD_217 — Tobias Beckett

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Underworld

**Rules text:**

> When you play a non-unit card: You may exhaust a unit that costs the same as or less than the card you played. Use this ability only once each round.
> Smuggle [5 resources Vigilance]

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_227 — Look the Other Way

**Type/Stats:** Event, cost 0  |  Traits: Trick

**Rules text:**

> Exhaust a unit unless its controller pays 2 resources.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_230 — Swoop Down

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a space unit. It gains Saboteur and can attack ground units for this attack. If it attacks a ground unit, it gets +2/+0 and the defender gets –2/–0 for this attack.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_232 — Relentless Pursuit

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Choose a friendly unit. It captures an enemy non-leader unit that costs the same as or less than it. If the friendly unit is a Bounty Hunter, give a Shield token to it. (Put the captured card facedown under the friendly unit until it leaves play.)

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_241 — Kragan Gorr

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Underworld

**Rules text:**

> When an enemy unit attacks your base: Give a Shield token to a friendly unit in the same arena as the attacker.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

