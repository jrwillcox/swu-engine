# moff-gideon:05 — Combat tricks, buffs & tempo

- **Group id (paste this):** `moff-gideon:05`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_118 | Kihraxz Heavy Fighter | Unit | 4 | 3/3 | Overwhelm |
| SHD_128 | Outflank | Event | 1 |  |  |
| SHD_130 | Moment of Glory | Event | 3 |  |  |
| SHD_236 | Snowtrooper Lieutenant | Unit | 2 | 2/2 |  |

## Per-card analysis & acceptance criteria

### SHD_118 — Kihraxz Heavy Fighter

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Fighter, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> On Attack: You may exhaust another friendly unit. If you do, this unit gets +3/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_128 — Outflank

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with 2 units (one at a time).

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_130 — Moment of Glory

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give a unit +4/+4 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_236 — Snowtrooper Lieutenant

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Trooper

**Rules text:**

> When Played: You may attack with a unit. If it's an Imperial unit, it gets +2/+0 for this attack. (You can only attack with a ready friendly unit.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

