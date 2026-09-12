# the-mandalorian:08 — Combat tricks, buffs & tempo

- **Group id (paste this):** `the-mandalorian:08`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_231 | Surprise Strike | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### SHD_231 — Surprise Strike

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with a unit. It gets +3/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

