# lofp-set:01 — Direct damage & removal

- **Group id (paste this):** `lofp-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOFP_11 | Infused Brawler | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### LOFP_11 — Infused Brawler

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Night

**Rules text:**

> When Played: You may use the Force . If you do, give 2 Experience tokens to this unit.
> When this unit completes an attack: Defeat an Experience token on it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

