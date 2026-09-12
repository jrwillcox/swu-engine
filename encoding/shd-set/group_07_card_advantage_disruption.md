# shd-set:07 — Card advantage & disruption

- **Group id (paste this):** `shd-set:07`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_1 | Gar Saxon | Leader | 6 | 4/7 |  |
| SHD_9 | Hunter | Leader | 7 | 5/8 | Overwhelm |
| SHD_15 | Doctor Aphra | Leader | 5 | 2/5 |  |
| SHD_27 | Hylobon Enforcer | Unit | 1 | 1/4 | Bounty, Grit |
| SHD_38 | Brutal Traditions | Upgrade | 2 |  |  |
| SHD_53 | Second Chance | Upgrade | 4 |  |  |
| SHD_94 | Palpatine's Return | Event | 6 |  |  |

## Per-card analysis & acceptance criteria

### SHD_1 — Gar Saxon

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Imperial, Mandalorian, Official

**Rules text:**

> Each friendly upgraded unit gets +1/+0.
> Each friendly upgraded unit gets +1/+0 and gains: “When Defeated: You may return an upgrade that was attached to this unit to its owner's hand.”
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['return_hand', 'stat_buff'].

**Existing primitives that should suffice:** ReturnToHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_9 — Hunter

**Type/Stats:** Leader, cost 7, 5/8  |  Traits: Clone, Fringe

**Rules text:**

> Action [1 resource, Exhaust]: Reveal a resource you control. If it shares a name with a friendly unique unit, return the resource to its owner's hand and put the top card of your deck into play as a resource.
> Overwhelm
> On Attack: You may reveal a resource you control. If it shares a name with a friendly unique unit, return the resource to its owner's hand and put the top card of your deck into play as a resource.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['return_hand', 'ramp'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_15 — Doctor Aphra

**Type/Stats:** Leader, cost 5, 2/5  |  Traits: Fringe

**Rules text:**

> When the regroup phase starts: Discard a card from your deck.
> While there are 5 or more different costs among cards in your discard pile, this unit gets +3/+0.
> When Deployed: Choose 3 cards in your discard pile with different names. If you do, return 1 of them at random to your hand.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'return_hand', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_27 — Hylobon Enforcer

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Underworld

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> Bounty — Draw a card. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_38 — Brutal Traditions

**Type/Stats:** Upgrade, cost 2  |  Traits: Learned

**Rules text:**

> Action: If an enemy unit was defeated this phase, play this upgrade from your discard pile (paying its cost).

**Mechanical analysis:** trigger archetype `activated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_53 — Second Chance

**Type/Stats:** Upgrade, cost 4  |  Traits: Gambit

**Rules text:**

> Attach to a non-leader unit.
> Attached unit gains: “When Defeated: For this phase, this unit's owner may play it from their discard pile for free.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_94 — Palpatine's Return

**Type/Stats:** Event, cost 6  |  Traits: Force, Plan

**Rules text:**

> Play a unit from your discard pile. 
> It costs 6 resources less. If it's a Force unit, 
> it costs 8 resources less instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

