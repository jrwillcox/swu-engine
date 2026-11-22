# hmw-set:08 — Card advantage & disruption

- **Group id (paste this):** `hmw-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_14 | Wicket | Leader | 4 | 2/5 |  |
| HMW_16 | Maul | Leader | 7 | 5/6 | Shielded |
| HMW_41 | Keeper of Skara Nal | Unit | 6 | 5/8 | Overwhelm, Restore |
| HMW_48 | Vernestra Rwoh | Unit | 6 | 5/5 | Sentinel |
| HMW_61 | Director Krennic | Unit | 3 | 3/4 |  |
| HMW_85 | Remote Scout | Unit | 2 | 1/3 |  |
| HMW_101 | Trust Yourself | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### HMW_14 — Wicket

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Ewok

**Rules text:**

> When a friendly unit attacks a unit that costs more than it: You may exhaust this leader. If you do, draw a card.
> On Attack: If you control a unit that costs 3 or less, draw a card.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'ready_exhaust'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_16 — Maul

**Type/Stats:** Leader, cost 7, 5/6  |  Traits: Force, Fringe

**Rules text:**

> Action [Exhaust]: Play a unit from your hand. It costs 1 resource less. Then, defeat it. (When Played abilities resolve after the unit is defeated.)
> Shielded
> When Deployed: You may play a unit that was defeated this phase from your discard pile. It costs 5 resources less.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'defeat', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_41 — Keeper of Skara Nal

**Type/Stats:** Unit, cost 6, 5/8  |  Traits: Droid, Vehicle, Walker

**Rules text:**

> Restore 2
> On Attack: You may discard 2 cards named Keeper of Skara Nal from your hand. If you do, this unit gets +15/+0 and gains Overwhelm for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus, GrantKeyword, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_48 — Vernestra Rwoh

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Force, Jedi

**Rules text:**

> Sentinel
> As an additional cost to play this unit, put up to 2 units that each cost 5 or less from your discard pile on the bottom of your deck. This unit gains those units' “When Played” abilities for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_61 — Director Krennic

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Imperial, Official

**Rules text:**

> On Attack: If your base is upgraded, draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_85 — Remote Scout

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: Search the top 8 cards of your deck for an upgrade, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_101 — Trust Yourself

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> Give a Shield token to a unit.
> Search the top 3 cards of your deck for a card and draw it. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'token'].

**Existing primitives that should suffice:** DrawCards, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

