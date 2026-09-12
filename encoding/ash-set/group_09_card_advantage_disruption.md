# ash-set:09 — Card advantage & disruption

- **Group id (paste this):** `ash-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_45 | Reanimated Night Trooper | Unit | 1 | 2/2 |  |
| ASH_55 | Blade of Talzin | Upgrade | 2 |  |  |
| ASH_87 | Cybernetic Enhancements | Upgrade | 3 |  |  |
| ASH_97 | Moff Gideon | Unit | 3 | 2/5 | Sentinel |
| ASH_104 | Dathomiri Magicks | Event | 6 |  |  |
| ASH_107 | Clan Wren Loyalist | Unit | 3 | 3/2 |  |
| ASH_116 | Ant Droid | Unit | 1 | 1/2 |  |

## Per-card analysis & acceptance criteria

### ASH_45 — Reanimated Night Trooper

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Imperial, Night, Trooper, Undead

**Rules text:**

> When Defeated: Look at the top card of a deck. You may discard it.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'search'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_55 — Blade of Talzin

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Night, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Defeated: If this upgrade was on a friendly Night unit, return this upgrade from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_87 — Cybernetic Enhancements

**Type/Stats:** Upgrade, cost 3  |  Traits: Modification

**Rules text:**

> When Played: Draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_97 — Moff Gideon

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Imperial, Official

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> When Defeated: You may return a non-<uq> Imperial unit from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_104 — Dathomiri Magicks

**Type/Stats:** Event, cost 6  |  Traits: Force

**Rules text:**

> If you control a Force unit, this event costs 1 resource less to play.
> Play up to 3 non-Vehicle units that each cost 2 or less from your discard pile for free.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_107 — Clan Wren Loyalist

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Mandalorian, Trooper

**Rules text:**

> When Played: Search the top 5 cards of your deck for a card that shares a Trait with a unit you control, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_116 — Ant Droid

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Droid

**Rules text:**

> When Defeated: Draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

