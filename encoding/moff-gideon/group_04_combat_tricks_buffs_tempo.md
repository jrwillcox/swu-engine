# moff-gideon:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `moff-gideon:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_7 | Moff Gideon | Leader | 5 | 3/6 | Overwhelm |
| SHD_81 | General Tagge | Unit | 2 | 2/2 |  |
| SHD_82 | Outland TIE Vanguard | Unit | 2 | 2/1 |  |
| SHD_83 | Seasoned Shoretrooper | Unit | 2 | 2/3 |  |
| SHD_84 | Phase-III Dark Trooper | Unit | 3 | 3/3 | Sentinel |
| SHD_85 | Superlaser Technician | Unit | 3 | 2/1 |  |
| SHD_113 | Privateer Crew | Unit | 2 | 2/2 | Smuggle |

## Per-card analysis & acceptance criteria

### SHD_7 — Moff Gideon

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Imperial, Official

**Rules text:**

> Action [exhaust]: Attack with a unit that costs 3 or less. If it's attacking a unit, it gets +1/+0 for this attack.
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> 
> Each friendly unit that costs 3 or less gets +1/+0 and gains Overwhelm while attacking an enemy unit.
> Epic Action: If you control 5 or more resources, deploy this leader. (Flip him, ready him, and move him to the ground arena.)

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_81 — General Tagge

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Official

**Rules text:**

> When Played: Give an Experience token to each of up to 3 Trooper units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_82 — Outland TIE Vanguard

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> When Played: You may give an Experience token to another unit that costs 3 or less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_83 — Seasoned Shoretrooper

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Imperial, Trooper

**Rules text:**

> While you control 6 or more resources, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_84 — Phase-III Dark Trooper

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Droid, Imperial, Trooper

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> When combat damage is dealt to this unit: Give an Experience token to this unit (if it survives the damage).

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_85 — Superlaser Technician

**Type/Stats:** Unit, cost 3, 2/1  |  Traits: Imperial

**Rules text:**

> When Defeated: You may put this unit into play as a resource and ready it.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust', 'ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_113 — Privateer Crew

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Underworld

**Rules text:**

> Smuggle [6 resources, command] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)
> 
> When played using Smuggle: Give 3 Experience tokens to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

