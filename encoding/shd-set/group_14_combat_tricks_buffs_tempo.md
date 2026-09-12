# shd-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_75 | Covert Strength | Event | 1 |  | Smuggle |
| SHD_76 | Unexpected Escape | Event | 1 |  |  |
| SHD_86 | Warbird Stowaway | Unit | 3 | 2/3 | Smuggle |
| SHD_87 | Crosshair | Unit | 4 | 2/6 |  |
| SHD_97 | Freetown Backup | Unit | 2 | 1/4 | Smuggle |
| SHD_101 | Adelphi Patrol Wing | Unit | 5 | 4/6 |  |
| SHD_103 | General Rieekan | Unit | 6 | 5/7 | Sentinel |

## Per-card analysis & acceptance criteria

### SHD_75 — Covert Strength

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Heal 2 damage from a unit and give an Experience token to it.
> Smuggle [3 resources Vigilance] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `event`; effect families ['heal', 'token'].

**Existing primitives that should suffice:** Heal, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_76 — Unexpected Escape

**Type/Stats:** Event, cost 1  |  Traits: Trick

**Rules text:**

> Exhaust a unit. You may rescue a captured card guarded by that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_86 — Warbird Stowaway

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Underworld

**Rules text:**

> While you have the initiative, this unit gets +2/+0.
> Smuggle [4 resources Command Villainy] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_87 — Crosshair

**Type/Stats:** Unit, cost 4, 2/6  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> Action [2 resources]: This unit gets +1/+0 for this phase.
> Action [Exhaust]: This unit deals damage equal to his power to an enemy ground unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_97 — Freetown Backup

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Fringe

**Rules text:**

> On Attack: Give another friendly unit +2/+2 for this phase.
> Smuggle [4 resources Command Heroism] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_101 — Adelphi Patrol Wing

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Fighter, New Republic, Vehicle

**Rules text:**

> When Played: You may attack with a unit. If you have the initiative, it gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_103 — General Rieekan

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Official, Rebel

**Rules text:**

> When Played/On Attack: Choose a friendly unit. If it has Sentinel, give an Experience token to it. Otherwise, it gains Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'keyword_grant'].

**Existing primitives that should suffice:** GiveToken, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

