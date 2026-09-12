# moff-gideon:02 — Direct damage & removal

- **Group id (paste this):** `moff-gideon:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_30 | Death Trooper | Unit | 3 | 3/3 |  |
| SHD_39 | Calculated Lethality | Event | 4 |  |  |
| SHD_262 | Confiscate | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SHD_30 — Death Trooper

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: Deal 2 damage to a friendly ground unit and 2 damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_39 — Calculated Lethality

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Defeat a non-leader unit that costs 3 or less. For each upgrade that was on that unit, give an Experience token to a friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_262 — Confiscate

**Type/Stats:** Event, cost 1  |  Traits: Law

**Rules text:**

> Defeat an upgrade.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

