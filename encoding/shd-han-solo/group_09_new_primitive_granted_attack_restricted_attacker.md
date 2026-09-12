# shd-han-solo:09 — New primitive: granted-attack-restricted-attacker

- **Group id (paste this):** `shd-han-solo:09`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** granted-attack-restricted-attacker — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_179 | Desperate Attack | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SHD_179 — Desperate Attack

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a damaged unit. It gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**⚠ Suspected NEW primitive:** granted-attack-restricted-attacker. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

