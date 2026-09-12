# lawp-set:01 — Direct damage & removal

- **Group id (paste this):** `lawp-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAWP_17 | Jabba's Rancor | Unit | 7 | 7/7 | Hidden |

## Per-card analysis & acceptance criteria

### LAWP_17 — Jabba's Rancor

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Creature, Underworld

**Rules text:**

> Hidden 
> On Attack: An opponent chooses a ground unit they control. You may deal 7 damage to that unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

