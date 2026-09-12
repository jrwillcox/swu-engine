# sec-set:10 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sec-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_4 | Leia Organa | Leader | 6 | 4/7 |  |
| SEC_6 | Colonel Yularen | Leader | 5 | 4/6 |  |
| SEC_7 | Dryden Vos | Leader | 7 | 5/7 | Ambush, Overwhelm |
| SEC_8 | Bail Organa | Leader | 4 | 3/3 |  |
| SEC_9 | Mon Mothma | Leader | 5 | 3/7 |  |
| SEC_11 | Governor Pryce | Leader | 6 | 4/6 |  |
| SEC_15 | C-3PO | Leader | 4 | 1/6 |  |

## Per-card analysis & acceptance criteria

### SEC_4 — Leia Organa

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: New Republic, Official

**Rules text:**

> Action [1 resource, Exhaust]: Disclose Vigilance, Command, Aggression, Cunning, or Heroism (reveal a card from your hand with this aspect icon). If you do, give an Experience token to a unit that doesn't share an aspect with the disclosed card.
> On Attack: You may disclose Vigilance, Command, Aggression, Cunning, or Heroism. If you do, give an Experience token to a unit that doesn't share an aspect with the disclosed card.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_6 — Colonel Yularen

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Attack with a unit. Then, you may attack with another unit that costs less than it.
> When this unit completes an attack (and survives): You may attack with another unit that costs 4 or less.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_7 — Dryden Vos

**Type/Stats:** Leader, cost 7, 5/7  |  Traits: Underworld

**Rules text:**

> Action [Exhaust, discard a card that costs 6 or more from your hand]: Play a unit that costs 5 or less from your hand (paying its cost). It gains Ambush for this phase.
> Overwhelm
> Action [discard a card from your hand]: Play a unit from your hand (paying its cost). It gains Ambush for this phase.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_8 — Bail Organa

**Type/Stats:** Leader, cost 4, 3/3  |  Traits: Official, Republic

**Rules text:**

> Action [1 resource, Exhaust]: If a friendly unit was defeated this phase, return a friendly resource to its owner's hand. If you do, put the top card of your deck into play as a resource.
> When you play a card from your resources: Heal 1 damage from your base.
> Action [Exhaust, discard 2 cards from your hand]: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `activated`; effect families ['heal', 'return_hand', 'ramp'].

**Existing primitives that should suffice:** Heal, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_9 — Mon Mothma

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Official, Republic

**Rules text:**

> Ignore the aspect penalties on non-Villainy Official units you play.
> Ignore the aspect penalties on non‑Villainy Official units you play.
> Each other friendly Official unit gets +0/+1.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_11 — Governor Pryce

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Imperial, Official

**Rules text:**

> Action [1 resource, Exhaust]: Ready a token unit.
> This unit gets +1/+0 for each ready friendly token unit.
> On Attack: Create a Spy token.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_15 — C-3PO

**Type/Stats:** Leader, cost 4, 1/6  |  Traits: Droid, Rebel

**Rules text:**

> Action [1 resource, Exhaust]: If you control an exhausted unit, exhaust a unit.
> On Attack: If you control another exhausted unit, you may exhaust a unit.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

