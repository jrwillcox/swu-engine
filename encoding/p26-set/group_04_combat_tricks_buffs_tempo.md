# p26-set:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `p26-set:04`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_275 | Chewbacca | Unit | 3 | 0/5 | Overwhelm, Raid |

## Per-card analysis & acceptance criteria

### P26_275 — Chewbacca

**Type/Stats:** Unit, cost 3, 0/5  |  Traits: Wookiee

**Rules text:**

> This unit gains Raid 1 for each exhausted resource you control.
> While each resource you control is exhausted, this unit gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant', 'ramp'].

**Existing primitives that should suffice:** GrantKeyword, grant-keyword-to-resources.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

