# hmwp-set:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmwp-set:03`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_4 | Batcher | Unit | 2 | 2/3 | Restore |
| HMWP_5 | Gunga City Guard | Unit | 2 | 2/1 | Restore, Shielded |
| HMWP_7 | Invasion Lander | Unit | 6 | 3/7 |  |
| HMWP_13 | Chief Chirpa | Unit | 2 | 1/5 |  |

## Per-card analysis & acceptance criteria

### HMWP_4 — Batcher

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Creature

**Rules text:**

> Restore 1 
> This unit gets +1/+0 while defending.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_5 — Gunga City Guard

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Gungan

**Rules text:**

> Restore 1
> While you control another Gungan unit or a Naboo base, this unit gains Shielded.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_7 — Invasion Lander

**Type/Stats:** Unit, cost 6, 3/7  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> When Played: Give each other friendly unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_13 — Chief Chirpa

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Ewok

**Rules text:**

> This unit gets +1/+0 for each other friendly Ewok unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

