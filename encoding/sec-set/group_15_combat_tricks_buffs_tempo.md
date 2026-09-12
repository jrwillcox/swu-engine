# sec-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_140 | Hondo Ohnaka | Unit | 6 | 6/5 | Plot, Raid |
| SEC_151 | Kazuda Xiono | Unit | 4 | 2/6 | Raid |
| SEC_154 | Inner Rim Coalition | Unit | 6 | 6/5 |  |
| SEC_157 | One Way Out | Event | 1 |  | Overwhelm |
| SEC_172 | Cinta Kaz | Unit | 6 | 5/5 | Plot |
| SEC_174 | Saw Gerrera's U-Wing | Unit | 6 | 4/8 | Saboteur |
| SEC_177 | It's Not Over Yet | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SEC_140 — Hondo Ohnaka

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Underworld

**Rules text:**

> Each other friendly unit gains Raid 1.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_151 — Kazuda Xiono

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Resistance

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> While you control fewer resources than an opponent, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_154 — Inner Rim Coalition

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Official, Republic

**Rules text:**

> When Defeated: You may ready a unit that costs 5 or less.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_157 — One Way Out

**Type/Stats:** Event, cost 1  |  Traits: Gambit

**Rules text:**

> Attack with a unit. It gets +1/+0 and gains Overwhelm for this attack. If it attacks a unit, the defender loses all abilities for this attack.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_172 — Cinta Kaz

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Rebel

**Rules text:**

> When Played: You may attack with a unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_174 — Saw Gerrera's U-Wing

**Type/Stats:** Unit, cost 6, 4/8  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> Saboteur
> When this unit completes an attack (and survives): You may attack with another Aggression unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_177 — It's Not Over Yet

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> You may ready a unit that didn't attack or enter play this phase.
> Create a Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

