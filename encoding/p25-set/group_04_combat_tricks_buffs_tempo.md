# p25-set:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `p25-set:04`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P25_107 | Yoda's Lightsaber | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### P25_107 — Yoda's Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: You may use the Force . If you do, heal 3 damage from a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

