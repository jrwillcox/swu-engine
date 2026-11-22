# ic27-set:04 — Card advantage & disruption

- **Group id (paste this):** `ic27-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_3 | Kylo Ren | Leader | 5 | 5/3 |  |
| IC27_6 | Luke Skywalker | Leader | 6 | 4/6 | Overwhelm |
| IC27_8 | Princess Leia | Leader | 6 | 4/7 |  |
| IC27_38 | Admiral Holdo | Unit | 5 | 3/7 |  |
| IC27_42 | Obi-Wan Kenobi | Unit | 8 | 5/9 |  |
| IC27_63 | Kylo's TIE Silencer | Unit | 4 | 4/4 | Restore |
| IC27_70 | C-3PO | Unit | 1 | 1/3 |  |

## Per-card analysis & acceptance criteria

### IC27_3 — Kylo Ren

**Type/Stats:** Leader, cost 5, 5/3  |  Traits: First Order, Force, Official

**Rules text:**

> Action [Exhaust, discard a card from your hand]: Give an Experience token to a unit.
> When Deployed: You may return a unit from your discard pile to your hand.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'return_hand', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_6 — Luke Skywalker

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Force, Jedi, Rebel

**Rules text:**

> Draw 2 more cards in your starting hand.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> On Attack: You may discard a card from your hand. If you do, this unit gets +2/+0 for this attack.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard', 'stat_buff'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand, ModifyStats/StatBonus, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_8 — Princess Leia

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Official, Rebel

**Rules text:**

> Action [1 resource, Exhaust]: Draw a card, 
> then put a card from your hand on the top or bottom of your deck.
> On Attack: Draw a card, then put a card from your hand on the top or bottom of your deck.
> Epic Action: If you control 6 or more resources, deploy this leader. (Flip her, ready her, and move her to the ground arena.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'ready_exhaust'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_38 — Admiral Holdo

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Official, Resistance

**Rules text:**

> Draw 1 more card during the regroup phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_42 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 8, 5/9  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: You may choose one:
> Play a unit that was defeated this phase from your discard pile. It costs 5 resources less.
> Choose a unit that entered play this phase. It gets –5/–5 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_63 — Kylo's TIE Silencer

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> When this unit is discarded from your hand: For this phase, you may play it from your discard pile (paying its cost).

**Mechanical analysis:** trigger archetype `static`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_70 — C-3PO

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Rebel

**Rules text:**

> Action [Exhaust]: Give an Experience token to another unit. Then, if it has 6 or more power, draw a card.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

