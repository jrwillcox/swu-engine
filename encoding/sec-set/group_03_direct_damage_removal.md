# sec-set:03 — Direct damage & removal

- **Group id (paste this):** `sec-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_144 | Tempest Assault | Event | 4 |  |  |
| SEC_149 | Kaydel Connix | Unit | 3 | 3/2 | Plot |
| SEC_150 | Valiant Commando | Unit | 3 | 3/3 |  |
| SEC_152 | Strike Force X-Wing | Unit | 4 | 3/2 | Plot |
| SEC_155 | Alexsandr Kallus | Unit | 7 | 6/6 | Raid |
| SEC_156 | Nemik's Manifesto | Upgrade | 1 |  |  |
| SEC_162 | Crosshair | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### SEC_144 — Tempest Assault

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> If you've dealt damage to an enemy base this phase, deal 2 damage to each enemy space unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_149 — Kaydel Connix

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Resistance

**Rules text:**

> When Played: You may defeat all non-<uq> (non-unique) upgrades on a unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_150 — Valiant Commando

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Rebel, Trooper

**Rules text:**

> When this unit deals combat damage to a base: You may defeat this unit. If you do, deal 3 damage to that base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_152 — Strike Force X-Wing

**Type/Stats:** Unit, cost 4, 3/2  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> When Played: You may deal 2 damage to a ready unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_155 — Alexsandr Kallus

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Rebel, Spectre

**Rules text:**

> While you have the initiative, each other friendly <uq> (unique) unit gains Raid 2.
> When Played: Deal 2 damage to each of up to 3 ground units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_156 — Nemik's Manifesto

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Rebel

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains the Rebel trait and: “When Defeated: Deal 1 damage to each enemy base for each other friendly Rebel unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_162 — Crosshair

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> On Attack: You may deal 1 damage to another friendly unit. If you do, deal 2 damage to the defending player's base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

