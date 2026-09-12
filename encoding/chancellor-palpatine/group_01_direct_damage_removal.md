# chancellor-palpatine:01 — Direct damage & removal

- **Group id (paste this):** `chancellor-palpatine:01`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_34 | Cad Bane | Unit | 5 | 4/5 | Plot |
| SEC_76 | Charged with Murder | Event | 4 |  |  |
| SEC_77 | Retaliation | Event | 5 |  |  |
| LOF_82 | Vaneé | Unit | 2 | 2/4 |  |
| SEC_241 | Political Bully | Unit | 3 | 2/3 |  |

## Per-card analysis & acceptance criteria

### SEC_34 — Cad Bane

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When Played: You may defeat a unit with 2 or less remaining HP.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_76 — Charged with Murder

**Type/Stats:** Event, cost 4  |  Traits: Law

**Rules text:**

> You may disclose VigilanceVigilance (reveal cards from your hand with these aspect icons among them). If you do, defeat a damaged non-leader unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_77 — Retaliation

**Type/Stats:** Event, cost 5  |  Traits: Tactic

**Rules text:**

> Defeat a unit that dealt damage to a base this phase.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_82 — Vaneé

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Imperial, Official, Sith

**Rules text:**

> When Played/On Attack: You may defeat an Experience token on a friendly unit. If you do, give an Experience token to a friendly unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_241 — Political Bully

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Official, Republic

**Rules text:**

> When Played: If you control another Official unit, you may deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

