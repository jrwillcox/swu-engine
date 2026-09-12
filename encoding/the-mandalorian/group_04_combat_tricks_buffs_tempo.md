# the-mandalorian:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `the-mandalorian:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_18 | The Mandalorian | Leader | 6 | 4/7 |  |
| SHD_40 | Clan Wren Rescuer | Unit | 2 | 1/2 |  |
| SHD_47 | The Armorer | Unit | 5 | 3/5 |  |
| SHD_56 | Follower of The Way | Unit | 2 | 1/3 |  |
| SHD_66 | Cargo Juggernaut | Unit | 6 | 4/6 | Shielded |
| SHD_73 | Mandalorian Armor | Upgrade | 2 |  |  |
| SHD_74 | Vambrace Grappleshot | Upgrade | 2 |  |  |

## Per-card analysis & acceptance criteria

### SHD_18 — The Mandalorian

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Bounty Hunter, Mandalorian

**Rules text:**

> When you play an upgrade: You may exhaust this leader. If you do, exhaust an enemy unit with 4 or less remaining HP.
> When you play an upgrade: You may exhaust an enemy unit with 6 or less remaining HP.
> Epic Action: If you control 6 or more resources, deploy this leader. (Flip him, ready him, and move him to the ground arena.)

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_40 — Clan Wren Rescuer

**Type/Stats:** Unit, cost 2, 1/2  |  Traits: Mandalorian, Trooper

**Rules text:**

> When Played: Give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_47 — The Armorer

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Mandalorian

**Rules text:**

> When Played: Give a Shield token to each of up to 3 Mandalorian units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_56 — Follower of The Way

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Mandalorian

**Rules text:**

> While this unit is upgraded, it gets +1/+1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_66 — Cargo Juggernaut

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Tank, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> When Played: If you control another Vigilance unit, heal 4 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_73 — Mandalorian Armor

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: If attached unit is a Mandalorian, give a Shield token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_74 — Vambrace Grappleshot

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack: Exhaust the defender.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

