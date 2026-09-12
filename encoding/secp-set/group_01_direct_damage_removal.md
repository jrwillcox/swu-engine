# secp-set:01 — Direct damage & removal

- **Group id (paste this):** `secp-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SECP_11 | The Elite Squad | Unit | 8 | 6/8 | Grit |

## Per-card analysis & acceptance criteria

### SECP_11 — The Elite Squad

**Type/Stats:** Unit, cost 8, 6/8  |  Traits: Imperial, Trooper

**Rules text:**

> Grit
> When Played/When damage is dealt to this unit: You may deal 2 damage to another <uq>  unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

