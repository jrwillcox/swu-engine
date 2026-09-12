# sabine-mean-green:04 — Miscellaneous abilities

- **Group id (paste this):** `sabine-mean-green:04`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_22 | Energy Conversion Lab | Base |  | None/25 | Ambush |
| SHD_129 | Timely Intervention | Event | 1 |  | Ambush, Smuggle |

## Per-card analysis & acceptance criteria

### SOR_22 — Energy Conversion Lab

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a unit that costs 6 resources or less from your hand. Give it AMBUSH for this phase.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_129 — Timely Intervention

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Play a unit from your hand. Give it Ambush for this phase. (When you play it, it may ready and attack an enemy unit.)
> 
> Smuggle [2 resources, command] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

