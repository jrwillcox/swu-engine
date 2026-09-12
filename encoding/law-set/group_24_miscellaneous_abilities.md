# law-set:24 — Miscellaneous abilities

- **Group id (paste this):** `law-set:24`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_258 | Criminal Contact | Unit | 2 | 1/4 |  |
| LAW_262 | Bank Job Fugitives | Unit | 6 | 4/6 |  |
| LAW_264 | From a Certain Point of View | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### LAW_258 — Criminal Contact

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Underworld

**Rules text:**

> On Attack: You may pay 2 resources. If you do, create a Credit token.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_262 — Bank Job Fugitives

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Underworld

**Rules text:**

> When Played: Create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_264 — From a Certain Point of View

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Play a card from your hand, ignoring its aspect penalties.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

