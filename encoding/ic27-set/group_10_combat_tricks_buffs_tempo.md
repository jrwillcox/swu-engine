# ic27-set:10 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_49 | Dexter Jettster | Unit | 3 | 2/6 |  |
| IC27_56 | Allegiant General Pryde | Unit | 1 | 2/2 |  |
| IC27_60 | Jabba the Hutt | Unit | 3 | 0/8 |  |
| IC27_62 | Admiral Motti | Unit | 4 | 2/6 | Hidden |
| IC27_67 | Darth Vader | Unit | 8 | 8/8 | Ambush |
| IC27_71 | Avar Kriss | Unit | 2 | 0/5 | Raid |
| IC27_76 | Clone Commander Cody | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### IC27_49 — Dexter Jettster

**Type/Stats:** Unit, cost 3, 2/6  |  Traits: Fringe

**Rules text:**

> On Attack: You may pay 1 resource. If you do, look at the top 3 cards of your deck. Put any number of them on the bottom of your deck and the rest on top in any order.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ramp', 'search'].

**Existing primitives that should suffice:** deck_search.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_56 — Allegiant General Pryde

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: First Order, Official

**Rules text:**

> When Defeated: Give an Experience token to the friendly unit with the most power. (If multiple units are tied, choose one.)

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_60 — Jabba the Hutt

**Type/Stats:** Unit, cost 3, 0/8  |  Traits: Hutt, Underworld

**Rules text:**

> Action [Exhaust]: Choose an enemy unit. For this phase, while that unit is defending, the attacker gets +4/+0.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_62 — Admiral Motti

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Imperial, Official

**Rules text:**

> Hidden (This unit can't be attacked if he was played this phase.)
> On Attack: Give an Experience token to each other friendly Imperial unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_67 — Darth Vader

**Type/Stats:** Unit, cost 8, 8/8  |  Traits: Force, Imperial, Sith

**Rules text:**

> Ambush
> Each other friendly unit gains Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_71 — Avar Kriss

**Type/Stats:** Unit, cost 2, 0/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> This unit gains Raid 1 for each other friendly unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_76 — Clone Commander Cody

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When another friendly Republic unit enters play: Give an Experience token to it.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

