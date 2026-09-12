# shd-set:09 — Card advantage & disruption

- **Group id (paste this):** `shd-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_135 | Kylo's TIE Silencer | Unit | 2 | 3/2 |  |
| SHD_138 | Jango Fett | Unit | 4 | 3/6 | Bounty, Overwhelm |
| SHD_156 | Cripple Authority | Event | 2 |  |  |
| SHD_157 | Bo-Katan Kryze | Unit | 2 | 3/3 |  |
| SHD_176 | Death Mark | Upgrade | 2 |  | Bounty |
| SHD_181 | Pillage | Event | 4 |  |  |
| SHD_184 | Bazine Netal | Unit | 2 | 1/3 | Smuggle |

## Per-card analysis & acceptance criteria

### SHD_135 — Kylo's TIE Silencer

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> Action: If this unit was discarded from your hand or deck this phase, play it from your discard pile (paying its cost).

**Mechanical analysis:** trigger archetype `activated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_138 — Jango Fett

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> While attacking a unit with a Bounty, this unit gets +3/+0 and gains Overwhelm.
> When this unit attacks and defeats a unit: Draw a card.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['draw', 'stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** DrawCards, ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_156 — Cripple Authority

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Draw a card. Each opponent who controls more resources than you discards a card from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_157 — Bo-Katan Kryze

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Mandalorian, Trooper

**Rules text:**

> When Defeated: For each player with 15 or more damage on their base, draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_176 — Death Mark

**Type/Stats:** Upgrade, cost 2  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Draw 2 cards.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_181 — Pillage

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Choose a player. They discard 2 cards from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_184 — Bazine Netal

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Underworld

**Rules text:**

> When Played: Look at an opponent's hand. You may discard 1 of those cards. If you do, that player draws a card.
> Smuggle [4 resources Cunning Villainy]

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

