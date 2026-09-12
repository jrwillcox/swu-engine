# law-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_3 | Agent Kallus | Leader | 5 | 3/6 |  |
| LAW_6 | Vel Sartha | Leader | 6 | 4/7 |  |
| LAW_7 | Boba Fett | Leader | 5 | 3/6 | Raid |
| LAW_14 | Enfys Nest | Leader | 5 | 3/7 |  |
| LAW_16 | The Client | Leader | 5 | 4/4 | Shielded |
| LAW_19 | Alliance Outpost | Base |  | None/26 |  |
| LAW_31 | Bossk | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### LAW_3 — Agent Kallus

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Imperial, Trooper

**Rules text:**

> Action [1 resource, Exhaust]: Play a card from your hand, ignoring its aspect penalties.
> Action [1 resource]: Play a card from your hand, ignoring its aspect penalties.
> When you play a Heroism card: Heal 2 damage from your base.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_6 — Vel Sartha

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Rebel

**Rules text:**

> Action [Exhaust]: Give an Experience token to a unit. An opponent creates a Credit token.
> On Attack: You may give an Experience token to a unit. If you do, an opponent creates a Credit token.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_7 — Boba Fett

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When a friendly Bounty Hunter unit's attack ends: If the defending unit was defeated, you may exhaust this leader. If you do, create a Credit token.
> Raid 1 (This unit gets +1/+0 while attacking.)
> When a friendly Bounty Hunter unit's attack ends: If the defending unit was defeated, create a Credit token.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_14 — Enfys Nest

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Underworld

**Rules text:**

> When you use an “On Attack” ability: You may pay 2 resources and exhaust this leader. If you do, use that ability again.
> When you use an “On Attack” ability: You may use that ability again. Use this ability only once each round.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_16 — The Client

**Type/Stats:** Leader, cost 5, 4/4  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: If you created a token this phase, exhaust an enemy unit.
> Shielded (When you deploy this leader, give him a Shield token.)
> On Attack: If you created a token this phase, exhaust an enemy unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_19 — Alliance Outpost

**Type/Stats:** Base

**Rules text:**

> Epic Action [defeat a friendly token]: Give an Experience or Shield token to a unit, or create a Credit token.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_31 — Bossk

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> On Attack: Give a unit +1/+1 for this phase. You may give a unit –1/–1 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

