# sor-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_60 | Distant Patroller | Unit | 2 | 2/1 |  |
| SOR_65 | Baze Malbus | Unit | 4 | 2/5 | Grit, Sentinel |
| SOR_68 | Cargo Juggernaut | Unit | 6 | 4/6 | Shielded |
| SOR_70 | Devotion | Upgrade | 2 |  | Restore |
| SOR_73 | Moment of Peace | Event | 1 |  |  |
| SOR_76 | Make an Opening | Event | 3 |  |  |
| SOR_80 | General Tagge | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### SOR_60 — Distant Patroller

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> When Defeated: You may give a Shield token to a [Vigilance] unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_65 — Baze Malbus

**Type/Stats:** Unit, cost 4, 2/5  |  Traits: Fringe

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on him.)
> 
> While you have the initiative, this unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_68 — Cargo Juggernaut

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Tank, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> When Played: If you control another [Vigilance] unit, heal 4 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_70 — Devotion

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> Attached unit gains Restore 2. (When this unit attacks, heal 2 damage from its controller's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_73 — Moment of Peace

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> Give a Shield token to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_76 — Make an Opening

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give a unit –2/–2 for this phase. Heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_80 — General Tagge

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Official

**Rules text:**

> When Played: Give an Experience token to each of up to 3 TROOPER units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

