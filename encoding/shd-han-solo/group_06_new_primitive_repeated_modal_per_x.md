# shd-han-solo:06 — New primitive: repeated-modal-per-X

- **Group id (paste this):** `shd-han-solo:06`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** repeated-modal-per-X — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_153 | Poe Dameron | Unit | 5 | 6/6 |  |

## Per-card analysis & acceptance criteria

### SHD_153 — Poe Dameron

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Resistance

**Rules text:**

> On Attack: Discard up to 3 cards from your hand. For each card discarded this way, choose a different option:
> <bullet>Deal 2 damage to a unit or base.
> Defeat an upgrade.
> An opponent discards a card from their hand.</bullet>

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard', 'defeat'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, DefeatUnit/Upgrade.

**⚠ Suspected NEW primitive:** repeated-modal-per-X. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

