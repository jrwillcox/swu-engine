# law-set:20 — Miscellaneous abilities

- **Group id (paste this):** `law-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_28 | Canto Bight | Base |  | None/27 |  |
| LAW_30 | Partisan Hideout | Base |  | None/27 |  |
| LAW_36 | Obi-Wan Kenobi | Unit | 7 | 7/7 | Sentinel |
| LAW_53 | Dengar | Unit | 3 | 4/3 |  |
| LAW_63 | L3-37 | Unit | 6 | 3/2 | Hidden |
| LAW_66 | Tear This Ship Apart | Event | 7 |  |  |
| LAW_71 | The Max Rebo Band | Unit | 3 | 1/5 |  |

## Per-card analysis & acceptance criteria

### LAW_28 — Canto Bight

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_30 — Partisan Hideout

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_36 — Obi-Wan Kenobi

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Sentinel
> While you control 7 or more units, their printed power is considered to be 7 and printed HP is considered to be 7.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_53 — Dengar

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When a unit with the highest cost among enemy units is defeated: Create a Credit token. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_63 — L3-37

**Type/Stats:** Unit, cost 6, 3/2  |  Traits: Droid, Underworld

**Rules text:**

> Hidden
> When Played: Search the top 10 cards of your deck for any number of Droid units with combined cost 5 or less and play each of them for free.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_66 — Tear This Ship Apart

**Type/Stats:** Event, cost 7  |  Traits: Tactic

**Rules text:**

> Look at all of an opponent's resources. You may play 1 of those cards for free. If you do, that opponent resources the top card of their deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_71 — The Max Rebo Band

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Musician, Underworld

**Rules text:**

> When the regroup phase starts: Create a Credit token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

