# ic27-set:15 — Miscellaneous abilities

- **Group id (paste this):** `ic27-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_19 | Soulless One | Unit | 4 | 3/5 |  |
| IC27_22 | Moff Gideon | Unit | 5 | 3/6 |  |
| IC27_35 | Yoda | Unit | 3 | 3/4 |  |
| IC27_43 | Raddus | Unit | 9 | 8/9 | Restore |
| IC27_57 | Director Krennic | Unit | 2 | 0/4 |  |
| IC27_68 | Devastator | Unit | 10 | 9/9 | Overwhelm |
| IC27_104 | The Inquisitor's TIE | Unit | 4 | 4/5 |  |

## Per-card analysis & acceptance criteria

### IC27_19 — Soulless One

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Fighter, Separatist, Vehicle

**Rules text:**

> When Played: Choose an enemy ground unit. While this unit is in play, the chosen unit gets –3/–0.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_22 — Moff Gideon

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial, Official

**Rules text:**

> If a friendly unit was defeated this phase, this unit costs 2 resources less to play.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_35 — Yoda

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> On Attack: You may choose an enemy unit. Prevent all combat damage that would be dealt to and dealt by that unit for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_43 — Raddus

**Type/Stats:** Unit, cost 9, 8/9  |  Traits: Capital Ship, Resistance, Vehicle

**Rules text:**

> Restore 3 (When this unit attacks, heal 3 damage from your base.)
> While this unit is exhausted, cards your opponents play cost 3 resources more.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_57 — Director Krennic

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Play a unit that costs 7 or more from your hand. It costs 2 resources less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_68 — Devastator

**Type/Stats:** Unit, cost 10, 9/9  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Overwhelm
> When Played: Search the top 5 cards of your deck for a Villainy unit that costs 12 or less and play it for free. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_104 — The Inquisitor's TIE

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Fighter, Imperial, Inquisitor, Vehicle

**Rules text:**

> On Attack: Each player with 4 or more cards in their hand discards a card from their hand.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

