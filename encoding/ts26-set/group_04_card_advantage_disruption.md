# ts26-set:04 — Card advantage & disruption

- **Group id (paste this):** `ts26-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TS26_8 | Ahsoka Tano | Leader | 5 | 3/6 | Raid |
| TS26_26 | Mother Talzin | Unit | 5 | 5/4 | Sentinel |
| TS26_33 | Kouhun Assassination | Event | 3 |  |  |
| TS26_37 | Abandoned the Order | Upgrade | 4 |  | Restore |
| TS26_39 | Captain Vaughn | Unit | 3 | 2/5 | Grit |
| TS26_46 | Secret Marriage | Event | 2 |  | Plot |
| TS26_57 | Mechanize | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### TS26_8 — Ahsoka Tano

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force

**Rules text:**

> When you play an event: You may exhaust this leader. If you do, look at the top card of your deck. You may play it (paying its cost), discard it, or leave it on top of your deck.
> Raid 1 (This unit gets +1/+0 while attacking.)
> When Attack Ends: Look at the top card of your deck. You may play it, discard it, or leave it on top of your deck. If you play it, it costs 1 resource less.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'ready_exhaust', 'ramp', 'search'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_26 — Mother Talzin

**Type/Stats:** Unit, cost 5, 5/4  |  Traits: Force, Night

**Rules text:**

> Sentinel
> When Defeated: Look at an opponent's hand and discard a card from it. If you do, they draw a card. If the discarded card is a unit, for this phase you may play it from their discard pile, ignoring its aspect penalties.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_33 — Kouhun Assassination

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> An opponent (of your choice) may discard a card from their hand. If they do, give a non-Vehicle unit –8/–8 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_37 — Abandoned the Order

**Type/Stats:** Upgrade, cost 4  |  Traits: Learned

**Rules text:**

> Attached unit loses the Jedi trait and gains Restore 1.
> When Played: You may return a non-leader unit to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand', 'keyword_grant'].

**Existing primitives that should suffice:** ReturnToHand, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_39 — Captain Vaughn

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Clone, Republic, Trooper

**Rules text:**

> Grit
> When Defeated: Search the top 3 cards of your deck for a card and draw it. Then, put a card from your hand on top of your deck. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_46 — Secret Marriage

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Give a Shield token to each of up to 2 non-Vehicle units. If you give a Shield to an enemy unit this way, draw a card.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TS26_57 — Mechanize

**Type/Stats:** Event, cost 2  |  Traits: Supply

**Rules text:**

> Play a non-Vehicle unit from your discard pile (paying its cost) and give an Experience token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'token'].

**Existing primitives that should suffice:** DiscardFromHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

