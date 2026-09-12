# qui-gon-jinn:02 — Card advantage & disruption

- **Group id (paste this):** `qui-gon-jinn:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_104 | Luminous Beings | Event | 6 |  |  |
| TWI_193 | R2-D2 | Unit | 2 | 2/4 |  |
| LOF_194 | J-Type Nubian Starship | Unit | 3 | 2/4 |  |

## Per-card analysis & acceptance criteria

### LOF_104 — Luminous Beings

**Type/Stats:** Event, cost 6  |  Traits: Force

**Rules text:**

> Put up to 3 Force units from your discard pile on the bottom of your deck in a random order. Give that many units +4/+4 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_193 — R2-D2

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Droid, Republic

**Rules text:**

> When Played: You may discard a card from your hand. If you do, search the top 3 cards of your deck for a card and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_194 — J-Type Nubian Starship

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Naboo, Transport, Vehicle

**Rules text:**

> When Played: Draw a card.
> When Defeated: Discard a card from your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

