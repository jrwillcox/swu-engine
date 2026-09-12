# jtlp-set:01 — Direct damage & removal

- **Group id (paste this):** `jtlp-set:01`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTLP_11 | Red Squadron Y-Wing | Unit | 2 | 1/3 |  |
| JTLP_18 | Fett's Firespray | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### JTLP_11 — Red Squadron Y-Wing

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> On Attack: Deal 3 indirect damage to the defending player.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTLP_18 — Fett's Firespray

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played/On Attack: Deal 1 indirect damage to a player. If you control Boba Fett

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

