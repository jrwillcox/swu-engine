# lof-set:05 — Card advantage & disruption

- **Group id (paste this):** `lof-set:05`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_1 | Kylo Ren | Leader | 7 | 5/5 | Sentinel |
| LOF_36 | Old Daka | Unit | 5 | 6/6 |  |
| LOF_57 | Owen Lars | Unit | 1 | 0/3 | Restore |
| LOF_65 | Watto | Unit | 3 | 1/6 |  |
| LOF_68 | Luthen Rael | Unit | 4 | 4/5 |  |
| LOF_83 | Captain Enoch | Unit | 3 | 1/5 |  |
| LOF_115 | Dagoyan Master | Unit | 5 | 5/5 |  |

## Per-card analysis & acceptance criteria

### LOF_1 — Kylo Ren

**Type/Stats:** Leader, cost 7, 5/5  |  Traits: First Order, Force

**Rules text:**

> Action [Exhaust]: Discard a card from your hand. If you discarded an upgrade this way, draw a card.
> Sentinel
> When Deployed: Play any number of upgrades from your discard pile on this unit (one at a time, paying their costs).
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_36 — Old Daka

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Force, Night

**Rules text:**

> When Played: You may defeat a friendly Night unit not named Old Daka. Then, you may play that unit from your discard pile for free.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_57 — Owen Lars

**Type/Stats:** Unit, cost 1, 0/3  |  Traits: Fringe

**Rules text:**

> Restore 2
> When Defeated: Search the top 5 cards of your deck for a Force unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_65 — Watto

**Type/Stats:** Unit, cost 3, 1/6  |  Traits: Fringe

**Rules text:**

> On Attack: An opponent chooses one:
> You give an Experience token to a friendly unit.
> You draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards, GiveToken, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_68 — Luthen Rael

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Rebel

**Rules text:**

> On Attack: Search the top 5 cards of your deck for an Item upgrade, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_83 — Captain Enoch

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Imperial, Trooper

**Rules text:**

> This unit gets +1/+0 for each Trooper unit in your discard pile.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_115 — Dagoyan Master

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Force

**Rules text:**

> When Played/When Defeated: You may use the Force (lose your Force token). If you do, search the top 5 cards of your deck for a Force unit, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

