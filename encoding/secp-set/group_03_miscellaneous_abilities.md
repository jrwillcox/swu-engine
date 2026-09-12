# secp-set:03 — Miscellaneous abilities

- **Group id (paste this):** `secp-set:03`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SECP_19 | B2EMO | Unit | 1 | 0/4 | Restore, Sentinel |

## Per-card analysis & acceptance criteria

### SECP_19 — B2EMO

**Type/Stats:** Unit, cost 1, 0/4  |  Traits: Droid, Fringe

**Rules text:**

> Restore 1
> On Attack: You may disclose HeroismHeroism . If you do, give a unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

