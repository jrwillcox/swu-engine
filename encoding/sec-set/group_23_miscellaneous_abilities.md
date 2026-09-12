# sec-set:23 — Miscellaneous abilities

- **Group id (paste this):** `sec-set:23`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_191 | Trade Federation Delegates | Unit | 5 | 3/4 |  |
| SEC_192 | Grand Moff Tarkin | Unit | 6 | 2/6 |  |
| SEC_194 | Fully Armed and Operational | Event | 1 |  | Ambush, Plot |
| SEC_195 | Arrest | Event | 2 |  |  |
| SEC_203 | Tala Durith | Unit | 3 | 3/3 | Hidden, Plot |
| SEC_206 | Emissaries from Ryloth | Unit | 5 | 4/6 |  |
| SEC_210 | Stolen Starpath Unit | Upgrade | 1 |  |  |

## Per-card analysis & acceptance criteria

### SEC_191 — Trade Federation Delegates

**Type/Stats:** Unit, cost 5, 3/4  |  Traits: Official, Republic

**Rules text:**

> When Played: Create 2 Spy tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_192 — Grand Moff Tarkin

**Type/Stats:** Unit, cost 6, 2/6  |  Traits: Imperial, Official

**Rules text:**

> When Played: Take control of an enemy non-leader Vehicle unit. When this unit leaves play, that unit's owner takes control of that unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_194 — Fully Armed and Operational

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> If an opponent attacked your base during their previous action this phase, play a unit from your hand. Give it Ambush for this phase.
> Plot

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_195 — Arrest

**Type/Stats:** Event, cost 2  |  Traits: Law

**Rules text:**

> Your base captures an enemy non-leader unit. At the start of the regroup phase, its owner rescues it.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_203 — Tala Durith

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Rebel

**Rules text:**

> Each other friendly unit gains Hidden.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_206 — Emissaries from Ryloth

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Official, Republic, Twi'lek

**Rules text:**

> When Played: You may give a unit –3/–0 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_210 — Stolen Starpath Unit

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Modification

**Rules text:**

> Attached unit gains: “On Attack: Name a card. The defending player reveals their hand. For each card in their hand with that name, create a Spy token.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

