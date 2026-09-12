# shd-han-solo:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-han-solo:04`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_168 | Hunting Nexu | Unit | 4 | 4/4 | Raid |
| SHD_247 | Protector of the Throne | Unit | 3 | 2/4 | Sentinel |

## Per-card analysis & acceptance criteria

### SHD_168 — Hunting Nexu

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Creature

**Rules text:**

> While you control another Aggression unit, this unit gains Raid 2. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_247 — Protector of the Throne

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Mandalorian

**Rules text:**

> While this unit is upgraded, it gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

