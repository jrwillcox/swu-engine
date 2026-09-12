# padme-amidala:01 — Card advantage & disruption

- **Group id (paste this):** `padme-amidala:01`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_94 | Mina Bonteri | Unit | 2 | 2/4 | Restore |
| SEC_197 | Furtive Handmaiden | Unit | 1 | 2/2 |  |

## Per-card analysis & acceptance criteria

### SEC_94 — Mina Bonteri

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Official, Separatist

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> When Defeated: You may disclose CommandCommandHeroism (reveal cards from your hand with these aspect icons among them). If you do, draw a card.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_197 — Furtive Handmaiden

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Naboo

**Rules text:**

> On Attack: You may discard a card from your hand. If you do, draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'discard'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

