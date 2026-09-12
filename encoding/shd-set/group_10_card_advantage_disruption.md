# shd-set:10 — Card advantage & disruption

- **Group id (paste this):** `shd-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_191 | Xanadu Blood | Unit | 6 | 4/6 | Raid |
| SHD_194 | Triple Dark Raid | Event | 3 |  |  |
| SHD_198 | Omega | Unit | 2 | 2/2 |  |
| SHD_203 | Zorii Bliss | Unit | 5 | 4/7 | Smuggle |
| SHD_207 | A New Adventure | Event | 2 |  |  |
| SHD_209 | Criminal Muscle | Unit | 1 | 2/1 |  |
| SHD_214 | Frontier Trader | Unit | 3 | 2/2 |  |

## Per-card analysis & acceptance criteria

### SHD_191 — Xanadu Blood

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Raid 2
> When Played/On Attack: You may return another friendly non-leader Underworld unit to its owner's hand. If you do, exhaust an enemy unit or resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_194 — Triple Dark Raid

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Search the top 7 cards of your deck for a Vehicle and play it. (Put the other cards on the bottom of your deck in a random order.) It costs 5 resources less and enters play ready. Return it to its owner's hand at the end of the phase.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['return_hand', 'ready_exhaust'].

**Existing primitives that should suffice:** ReturnToHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_198 — Omega

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Clone, Fringe

**Rules text:**

> Ignore the aspect penalty on the first Clone unit you play each round.
> When Played: Search the top 5 cards of your deck for a Clone card, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_203 — Zorii Bliss

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Underworld

**Rules text:**

> On Attack: Draw a card. At the start of the regroup phase, discard a card from your hand.
> Smuggle [6 resources Cunning Heroism]

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_207 — A New Adventure

**Type/Stats:** Event, cost 2  |  Traits: Gambit

**Rules text:**

> Return a non-leader unit that costs 6 or less to its owner's hand. Then, its owner may play it for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_209 — Criminal Muscle

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Underworld

**Rules text:**

> When Played: You may return a non-unique upgrade to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_214 — Frontier Trader

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Fringe, Jawa

**Rules text:**

> When Played: You may return a resource you control to its owner's hand. If you do, you may put the top card of your deck into play as a resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

