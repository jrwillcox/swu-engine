# moff-gideon:03 — Card advantage & disruption

- **Group id (paste this):** `moff-gideon:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_28 | Doctor Pershing | Unit | 2 | 0/5 |  |
| SHD_93 | Remnant Reserves | Event | 4 |  |  |
| SHD_242 | Gideon's Light Cruiser | Unit | 8 | 7/8 | Overwhelm |

## Per-card analysis & acceptance criteria

### SHD_28 — Doctor Pershing

**Type/Stats:** Unit, cost 2, 0/5  |  Traits: Imperial

**Rules text:**

> Action [Exhaust, deal 1 damage to a friendly unit]: Draw a card.

**Mechanical analysis:** trigger archetype `activated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_93 — Remnant Reserves

**Type/Stats:** Event, cost 4  |  Traits: Supply

**Rules text:**

> Search the top 5 cards of your deck for up to 3 units, reveal them, and draw them. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_242 — Gideon's Light Cruiser

**Type/Stats:** Unit, cost 8, 7/8  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> 
> When Played: If you control Moff Gideon (as a leader or unit), play a [villainy] unit that costs 3 or less from your hand or discard pile for free.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

