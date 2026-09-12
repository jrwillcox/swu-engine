# sec-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_229 | Catch Unawares | Event | 2 |  |  |
| SEC_231 | Implicate | Event | 2 |  | Sentinel |
| SEC_235 | The Wrong Ride | Event | 3 |  | Plot |
| SEC_236 | Undercover Operation | Event | 3 |  |  |
| SEC_243 | FN Trooper Corps | Unit | 5 | 4/5 | Plot |
| SEC_249 | High Command Councilor | Unit | 2 | 1/4 | Raid |
| SEC_257 | Restore Freedom | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SEC_229 — Catch Unawares

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. The defender gets –4/–0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_231 — Implicate

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Choose a unit. For this phase, it gains Sentinel and: “When this unit is attacked: Create a Spy token.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_235 — The Wrong Ride

**Type/Stats:** Event, cost 3  |  Traits: Disaster

**Rules text:**

> Exhaust 2 enemy resources.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_236 — Undercover Operation

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Ready a unit that was played this phase. If it costs 3 or less, create a Spy token.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_243 — FN Trooper Corps

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: First Order, Trooper

**Rules text:**

> When Played: Give an Experience token to another friendly unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_249 — High Command Councilor

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Official, Rebel

**Rules text:**

> While you control another Official unit, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_257 — Restore Freedom

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Play a unit from your hand. It costs 1 resource less for each Heroism aspect icon among friendly units.

**Mechanical analysis:** trigger archetype `event`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

