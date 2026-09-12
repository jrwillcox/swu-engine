# jtl-set:09 — Card advantage & disruption

- **Group id (paste this):** `jtl-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_98 | Snap Wexley | Unit | 3 | 2/5 | Piloting |
| JTL_126 | Eject | Event | 2 |  |  |
| JTL_134 | General Hux | Unit | 2 | 1/4 | Raid |
| JTL_177 | Stay on Target | Event | 2 |  |  |
| JTL_186 | Mist Hunter | Unit | 3 | 3/4 |  |
| JTL_191 | Invincible | Unit | 6 | 6/6 |  |
| JTL_194 | Heartless Tactics | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### JTL_98 — Snap Wexley

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Pilot, Resistance

**Rules text:**

> When played as a unit/On Attack: The next Resistance card you play this phase costs 1 resource less.
> Piloting [2 resources Command Heroism]
> When played as an upgrade: Search the top 5 cards of your deck for a Resistance card, reveal it, and draw it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_126 — Eject

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Detach a Pilot upgrade, move it to the ground arena as a unit, and exhaust it. Draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'ready_exhaust'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_134 — General Hux

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: First Order, Official

**Rules text:**

> Each other friendly First Order unit gains Raid 1. (They get +1/+0 while attacking.)
> Action [Exhaust]: If you played a First Order card this phase, draw a card.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw', 'keyword_grant'].

**Existing primitives that should suffice:** DrawCards, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_177 — Stay on Target

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a Vehicle unit. For this attack, it gets +2/+0 and gains: “When this unit deals damage to a base: Draw a card.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['draw', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DrawCards, ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_186 — Mist Hunter

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> On Attack: If you played a Bounty Hunter or Pilot card this phase, you may draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_191 — Invincible

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> If you control a unique Separatist card, this unit costs 1 resource less to play.
> When you deploy a leader: You may return a non-leader unit that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_194 — Heartless Tactics

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Exhaust a unit and give it –2/–0 for this phase. Then, if it has 0 power and isn't a leader, you may return it to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** ReturnToHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

