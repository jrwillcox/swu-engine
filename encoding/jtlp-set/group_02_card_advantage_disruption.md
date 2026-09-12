# jtlp-set:02 — Card advantage & disruption

- **Group id (paste this):** `jtlp-set:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTLP_4 | Cassian Andor | Unit | 3 | 3/4 | Piloting |
| JTLP_8 | General Hux | Unit | 2 | 1/4 | Raid |
| JTLP_16 | Anakin Skywalker | Unit | 2 | 2/3 | Piloting |

## Per-card analysis & acceptance criteria

### JTLP_4 — Cassian Andor

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Pilot, Rebel

**Rules text:**

> Piloting [2 resources Vigilance Heroism]
> Attached unit gains: “On Attack: Discard a card from the defending player's deck. If that card costs 3 or less, draw a card.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTLP_8 — General Hux

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: First Order, Official

**Rules text:**

> Each other friendly First Order unit gains Raid 1.
> Action [Exhaust]: If you played a First Order card this phase, draw a card.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw', 'keyword_grant'].

**Existing primitives that should suffice:** DrawCards, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTLP_16 — Anakin Skywalker

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Force, Fringe, Pilot

**Rules text:**

> Piloting [2 resources Cunning Heroism]: You may return this upgrade to its owner's hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

