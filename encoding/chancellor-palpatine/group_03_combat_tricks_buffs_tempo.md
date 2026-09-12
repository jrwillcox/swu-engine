# chancellor-palpatine:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `chancellor-palpatine:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_27 | The Chancellor's Shuttle | Unit | 2 | 1/3 | Restore |
| SEC_37 | Cantwell Arrestor Cruiser | Unit | 7 | 6/7 |  |
| SEC_55 | Dhani Pilgrim | Unit | 1 | 1/3 |  |
| SEC_79 | Corrupt Politician | Unit | 1 | 2/2 | Sentinel |
| SEC_81 | Major Partagaz | Unit | 2 | 0/6 | Overwhelm |
| SEC_84 | Mas Amedda | Unit | 4 | 3/4 | Plot |
| SEC_85 | Vice Admiral Rampart | Unit | 4 | 3/6 |  |

## Per-card analysis & acceptance criteria

### SEC_27 — The Chancellor's Shuttle

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Republic, Transport, Vehicle

**Rules text:**

> Restore 1
> When Defeated: If you control Chancellor Palpatine (as a leader or unit), you may give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_37 — Cantwell Arrestor Cruiser

**Type/Stats:** Unit, cost 7, 6/7  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may disclose VigilanceVigilanceVillainy (reveal cards from your hand with these aspect icons among them). If you do, exhaust an enemy unit. That unit can't ready while this unit is in play.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_55 — Dhani Pilgrim

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Fringe

**Rules text:**

> When Played/When Defeated: Heal 1 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_79 — Corrupt Politician

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Official, Republic

**Rules text:**

> While you control more units than an opponent, this unit gains Sentinel.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_81 — Major Partagaz

**Type/Stats:** Unit, cost 2, 0/6  |  Traits: Imperial, Official

**Rules text:**

> Overwhelm
> When another friendly Official unit attacks: This unit gets +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_84 — Mas Amedda

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Official, Republic

**Rules text:**

> When Played: Give an Experience token to each of up to 2 other Official units.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_85 — Vice Admiral Rampart

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Imperial, Official

**Rules text:**

> On Attack: You may disclose CommandCommandVillainy (reveal cards from your hand with these aspect icons among them). If you do, give an Experience token to each of up to 2 other units.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

