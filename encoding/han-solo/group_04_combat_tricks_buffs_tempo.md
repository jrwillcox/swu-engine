# han-solo:04 — Combat tricks, buffs & tempo

- **Group id (paste this):** `han-solo:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_17 | Han Solo | Leader | 5 | 3/7 |  |
| JTL_93 | Nien Nunb | Unit | 1 | 1/2 | Piloting |
| JTL_96 | Blue Leader | Unit | 3 | 3/3 | Ambush |
| JTL_97 | Leia Organa | Unit | 3 | 3/4 | Restore |
| TWI_110 | Huyang | Unit | 3 | 2/4 |  |
| JTL_124 | Tandem Assault | Event | 1 |  |  |
| JTL_209 | It's a Trap | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### JTL_17 — Han Solo

**Type/Stats:** Leader, cost 5, 3/7  |  Traits: Pilot, Rebel

**Rules text:**

> Action [Exhaust]: Reveal the top card of your deck, then attack with a unit. If the revealed card and that unit have different odd costs, that unit gets +1/+0 for this attack.
> 
> Attached unit is a leader unit.
> When deployed as an upgrade: For each friendly unit or upgrade that has an odd cost, ready a resource.
> 
> Epic Action: If you control 5 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust', 'stat_buff', 'ramp', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard, push_modal, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_93 — Nien Nunb

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Pilot, Rebel

**Rules text:**

> This unit gets +1/+0 for each other friendly Pilot unit and upgrade.
> Piloting [1 resource Command Heroism] 
> Attached unit gets +1/+0 for each other friendly Pilot unit and upgrade.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_96 — Blue Leader

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When Played: You may pay 2 resources. If you do, move this unit to the ground arena and give 2 Experience tokens to it. (It's a ground unit.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_97 — Leia Organa

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Official, Rebel

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> When Played: You may attack with a Pilot unit or a unit with a Pilot on it. It gets +1/+0 and gains Restore 1 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_110 — Huyang

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Droid, Jedi

**Rules text:**

> When Played: Choose another friendly unit. While this unit is in play, the chosen unit gets +2/+2.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_124 — Tandem Assault

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a space unit. If you do, attack with a ground unit, and that ground unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_209 — It's a Trap

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> If an opponent controls more space units than you, ready each space unit you control.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

