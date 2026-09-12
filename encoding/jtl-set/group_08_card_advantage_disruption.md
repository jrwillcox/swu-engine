# jtl-set:08 — Card advantage & disruption

- **Group id (paste this):** `jtl-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_14 | Admiral Trench | Leader | 6 | 4/5 |  |
| JTL_21 | Colossus | Base |  | None/35 |  |
| JTL_28 | Nabat Village | Base |  | None/27 |  |
| JTL_41 | Annihilator | Unit | 11 | 12/12 |  |
| JTL_48 | Cassian Andor | Unit | 3 | 3/4 | Piloting |
| JTL_63 | Landing Shuttle | Unit | 3 | 2/4 |  |
| JTL_89 | The Invisible Hand | Unit | 6 | 6/6 |  |

## Per-card analysis & acceptance criteria

### JTL_14 — Admiral Trench

**Type/Stats:** Leader, cost 6, 4/5  |  Traits: Official, Separatist

**Rules text:**

> Action [Exhaust]: Discard a card that costs 3 or more from your hand. If you do, draw a card.
> When Deployed: Reveal the top 4 cards of your deck. An opponent discards 2 of them. Draw 1 of the remaining cards and discard the other.
> Action [3 resources, Exhaust]: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_21 — Colossus

**Type/Stats:** Base

**Rules text:**

> Draw 1 less card in your starting hand.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_28 — Nabat Village

**Type/Stats:** Base

**Rules text:**

> Draw 3 more cards in your starting hand. You can't take a mulligan.
> When the first action phase starts: Put 3 cards from your hand on the bottom of your deck in any order.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_41 — Annihilator

**Type/Stats:** Unit, cost 11, 12/12  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played/When Defeated: You may defeat an enemy unit. If you do, search its controller's deck and hand for each card with that unit's name and discard them. (They shuffle their deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'defeat'].

**Existing primitives that should suffice:** DiscardFromHand, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_48 — Cassian Andor

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Pilot, Rebel

**Rules text:**

> Piloting [2 resources Vigilance Heroism] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains: “On Attack: Discard a card from the defending player's deck. If that card costs 3 or less, draw a card.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_63 — Landing Shuttle

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> When Defeated: You may draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_89 — The Invisible Hand

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> When Played/When this unit completes an attack (and survives): You may search the top 8 cards of your deck for a Droid unit, reveal it, and draw it. If it costs 2 or less, you may play it for free. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

