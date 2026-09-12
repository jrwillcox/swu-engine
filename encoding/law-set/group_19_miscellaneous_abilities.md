# law-set:19 — Miscellaneous abilities

- **Group id (paste this):** `law-set:19`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_8 | Director Krennic | Leader | 7 | 4/9 |  |
| LAW_9 | Hera Syndulla | Leader | 5 | 3/6 | Restore |
| LAW_21 | Coaxium Mine | Base |  | None/27 |  |
| LAW_22 | Aldhani Garrison | Base |  | None/27 |  |
| LAW_24 | Imperial Command Complex | Base |  | None/27 |  |
| LAW_25 | Contested Caverns | Base |  | None/27 |  |
| LAW_27 | Stygeon Spire | Base |  | None/27 |  |

## Per-card analysis & acceptance criteria

### LAW_8 — Director Krennic

**Type/Stats:** Leader, cost 7, 4/9  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust, defeat a friendly unit]: Create a Credit token.
> When Deployed: Another friendly unit deals damage equal to its power to an enemy unit.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_9 — Hera Syndulla

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Rebel, Spectre, Twi'lek

**Rules text:**

> While you control 2 or more units, ignore the aspect penalties on Heroism units you play.
> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> While you control 2 or more units, ignore the aspect penalties on Heroism units you play.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_21 — Coaxium Mine

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_22 — Aldhani Garrison

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_24 — Imperial Command Complex

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_25 — Contested Caverns

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_27 — Stygeon Spire

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

