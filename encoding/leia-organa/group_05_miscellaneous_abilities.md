# leia-organa:05 — Miscellaneous abilities

- **Group id (paste this):** `leia-organa:05`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_20 | Daimyo's Palace | Base |  | None/27 |  |
| LAW_104 | Bodhi Rook | Unit | 2 | 2/4 | Sentinel |
| LAW_108 | Lando Calrissian | Unit | 5 | 4/5 | Sentinel |

## Per-card analysis & acceptance criteria

### LAW_20 — Daimyo's Palace

**Type/Stats:** Base

**Rules text:**

> Epic Action: Play a card from your hand, ignoring 1 of its Vigilance, Command, Aggression, or Cunning aspect penalties.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_104 — Bodhi Rook

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Rebel

**Rules text:**

> On Attack: You may give a friendly Rebel unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_108 — Lando Calrissian

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Rebel, Underworld

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> While this unit is defending, the attacker gets –1/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

