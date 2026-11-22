# hmw-set:21 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:21`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_266 | Familiar Strategem | Event | 1 |  |  |
| HMW_267 | Renew | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### HMW_266 — Familiar Strategem

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a unit. If it shares a Trait with another friendly unit, it gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_267 — Renew

**Type/Stats:** Event, cost 2  |  Traits: Innate

**Rules text:**

> You may defeat a Condition upgrade.
> Heal 3 damage from your base.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'defeat'].

**Existing primitives that should suffice:** Heal, DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

