# padme-amidala:05 — New primitive: reveal-or-discard-trigger

- **Group id (paste this):** `padme-amidala:05`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** reveal-or-discard-trigger — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_16 | Padmé Amidala | Leader | 6 | 3/8 |  |

## Per-card analysis & acceptance criteria

### SEC_16 — Padmé Amidala

**Type/Stats:** Leader, cost 6, 3/8  |  Traits: Naboo, Official, Republic

**Rules text:**

> When you reveal or discard 1 or more cards from your hand: You may exhaust this leader. If you do, deal 1 damage to a unit.
> When you reveal or discard 1 or more cards from your hand: You may deal 1 damage to a unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'discard', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand.

**⚠ Suspected NEW primitive:** reveal-or-discard-trigger. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

