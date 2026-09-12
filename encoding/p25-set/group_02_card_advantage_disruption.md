# p25-set:02 — Card advantage & disruption

- **Group id (paste this):** `p25-set:02`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P25_40 | Agent Kallus | Unit | 5 | 4/4 | Ambush |
| P25_44 | Obi-Wan Kenobi | Unit | 6 | 4/6 | Sentinel |
| P25_67 | Razor Crest | Unit | 4 | 3/4 | Restore |
| P25_72 | Kylo Ren | Unit | 2 | 2/3 | Overwhelm |
| P25_78 | The Invisible Hand | Unit | 6 | 6/6 |  |

## Per-card analysis & acceptance criteria

### P25_40 — Agent Kallus

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Imperial, Trooper

**Rules text:**

> Ambush 
> 
> When another unique unit is defeated: You may draw a card. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_44 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Force, Jedi

**Rules text:**

> Sentinel 
> 
> When Defeated: Give 2 Experience tokens to another friendly unit. If it's a Force unit, draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_67 — Razor Crest

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Restore 2 
> 
> When Played: You may return an upgrade from your discard pile to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'return_hand'].

**Existing primitives that should suffice:** DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_72 — Kylo Ren

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: First Order, Force

**Rules text:**

> Overwhelm 
> When you play an upgrade on this unit: You may use the Force . If you do, draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P25_78 — The Invisible Hand

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> When Played/When this unit completes an attack : You may search the top 8 cards of your deck for a Droid unit, reveal it, and draw it. If it costs 2 or less, you may play it for free. 

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

