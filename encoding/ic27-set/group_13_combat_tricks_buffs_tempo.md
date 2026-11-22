# ic27-set:13 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:13`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_123 | Jyn Erso | Unit | 8 | 8/7 | Saboteur |
| IC27_131 | Cham Syndulla | Unit | 4 | 5/4 |  |
| IC27_137 | Kintan Intimidator | Unit | 1 | 1/4 |  |
| IC27_139 | Bib Fortuna | Unit | 2 | 1/3 | Shielded |
| IC27_143 | Wat Tambor | Unit | 3 | 4/2 | Sentinel |
| IC27_146 | Boba Fett | Unit | 5 | 4/7 |  |
| IC27_148 | Count Dooku | Unit | 7 | 8/7 |  |

## Per-card analysis & acceptance criteria

### IC27_123 — Jyn Erso

**Type/Stats:** Unit, cost 8, 8/7  |  Traits: Rebel

**Rules text:**

> Saboteur
> When Played: Ready up to 3 units with combined cost 7 or less. They each gain Saboteur for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust', 'keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_131 — Cham Syndulla

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Rebel, Twi'lek

**Rules text:**

> When Played: If you control fewer resources than an opponent, you may resource the top card of your deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_137 — Kintan Intimidator

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Underworld

**Rules text:**

> On Attack: Exhaust the defending unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_139 — Bib Fortuna

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Twi'lek, Underworld

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> Action [Exhaust]: Play an event from your hand. It costs 1 resource less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_143 — Wat Tambor

**Type/Stats:** Unit, cost 3, 4/2  |  Traits: Official, Separatist

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> When Played: You may attack with a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_146 — Boba Fett

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Attack Ends: If the defending unit was defeated, you may ready 2 resources.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_148 — Count Dooku

**Type/Stats:** Unit, cost 7, 8/7  |  Traits: Force, Official, Separatist, Sith

**Rules text:**

> Each opponent can't ready more than 1 ground unit and 1 space unit during the regroup phase.
> When Played: You may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

