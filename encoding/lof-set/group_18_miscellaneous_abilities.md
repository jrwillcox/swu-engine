# lof-set:18 — Miscellaneous abilities

- **Group id (paste this):** `lof-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_2 | Mother Talzin | Leader | 5 | 3/7 |  |
| LOF_3 | Ahsoka Tano | Leader | 6 | 5/6 | Sentinel |
| LOF_10 | Third Sister | Leader | 5 | 5/4 | Hidden |
| LOF_18 | Anakin Skywalker | Leader | 5 | 4/6 |  |
| LOF_19 | Vergence Temple | Base |  | None/25 |  |
| LOF_20 | Nightsister Lair | Base |  | None/28 |  |
| LOF_22 | Mystic Monastery | Base |  | None/25 |  |

## Per-card analysis & acceptance criteria

### LOF_2 — Mother Talzin

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Force, Night

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Give a unit –1/–1 for this phase.
> On Attack: You may give a unit –1/–1 for this phase.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_3 — Ahsoka Tano

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Fringe

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Give a friendly unit Sentinel for this phase. (Enemy units in its arena must attack a sentinel when they attack you.)
> On Attack: You may give a friendly unit Sentinel for this phase.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_10 — Third Sister

**Type/Stats:** Leader, cost 5, 5/4  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Action [Exhaust]: Play a unit from your hand. It gains Hidden for this phase. (It can't be attacked for this phase unless it has Sentinel.)
> Hidden (This unit can't be attacked if she was deployed this phase.)
> On Attack: The next unit you play this phase gains Hidden.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_18 — Anakin Skywalker

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Play a Villainy non-unit card from your hand, ignoring its aspect penalties.
> Action [use the Force]: Play a Villainy non-unit card from your hand, ignoring its aspect penalties.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** force-token, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_19 — Vergence Temple

**Type/Stats:** Base

**Rules text:**

> When the regroup phase starts: If you control a unit with 4 or more remaining HP, the Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_20 — Nightsister Lair

**Type/Stats:** Base

**Rules text:**

> When a friendly Force unit attacks: The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_22 — Mystic Monastery

**Type/Stats:** Base

**Rules text:**

> Action: The Force is with you (create your Force token). Use this ability no more than 3 times each game.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

