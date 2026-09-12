# ibh-set:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ibh-set:03`
- **Kind:** ability
- **Cards:** 4

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IBH_1 | Leia Organa | Leader | 5 | 3/7 |  |
| IBH_13 | Recovery | Event | 3 |  |  |
| IBH_31 | Millennium Falcon | Unit | 7 | 5/6 |  |
| IBH_42 | Han Solo | Unit | 6 | 4/6 | Raid |

## Per-card analysis & acceptance criteria

### IBH_1 — Leia Organa

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Official, Rebel

**Rules text:**

> Action [1 resource, Exhaust]: Heal 1 damage from a friendly unit.
> On Attack: Heal 1 damage from a friendly unit and 1 damage from another friendly unit.
> Epic Action: If you control 5 or more resources, deploy this leader. (Flip her, ready her, and move her to the ground arena.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_13 — Recovery

**Type/Stats:** Event, cost 3  |  Traits: Plan

**Rules text:**

> Heal 5 damage from a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_31 — Millennium Falcon

**Type/Stats:** Unit, cost 7, 5/6  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> When Played: If your base has more damage on it than an enemy base, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IBH_42 — Han Solo

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> On Attack:The defender gets -2/-0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

