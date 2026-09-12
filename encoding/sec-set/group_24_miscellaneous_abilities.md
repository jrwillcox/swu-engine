# sec-set:24 — Miscellaneous abilities

- **Group id (paste this):** `sec-set:24`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_223 | Duchess's Investigators | Unit | 5 | 4/4 |  |
| SEC_224 | Vel Sartha | Unit | 5 | 4/6 | Raid |
| SEC_227 | Special Modifications | Upgrade | 2 |  |  |
| SEC_253 | Covert Operative | Unit | 4 | 2/4 |  |
| SEC_255 | Remote Escort Tank | Unit | 6 | 5/5 | Plot, Sentinel |

## Per-card analysis & acceptance criteria

### SEC_223 — Duchess's Investigators

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Mandalorian

**Rules text:**

> When Played: You may disclose Cunning (reveal a card from your hand with this aspect icon). If you do, each opponent discards a random card from their hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_224 — Vel Sartha

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Rebel

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> Each exhausted enemy unit gets –2/–0 while defending.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_227 — Special Modifications

**Type/Stats:** Upgrade, cost 2  |  Traits: Modification

**Rules text:**

> Attach to a Vehicle unit.
> When Played: If attached unit is a Transport, you may create a Spy token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_253 — Covert Operative

**Type/Stats:** Unit, cost 4, 2/4  |  Traits: Rebel

**Rules text:**

> When Played: This unit captures an enemy non-leader unit that costs 2 or less. (Put the captured card facedown under this unit until this unit leaves play.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_255 — Remote Escort Tank

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Republic, Tank, Vehicle

**Rules text:**

> When Played: Give a unit Sentinel for this phase.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

