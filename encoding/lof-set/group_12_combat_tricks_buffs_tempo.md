# lof-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_87 | Eighth Brother | Unit | 6 | 5/7 | Ambush |
| LOF_89 | Supremacy | Unit | 12 | 12/12 | Ambush |
| LOF_92 | Point Rain Reclaimer | Unit | 1 | 1/2 |  |
| LOF_95 | Lor San Tekka | Unit | 2 | 3/2 |  |
| LOF_97 | Eeth Koth | Unit | 4 | 5/4 |  |
| LOF_102 | Yoda's Lightsaber | Upgrade | 2 |  |  |
| LOF_105 | Oppo Rancisis | Unit | 3 | 3/5 | Ambush, Grit, Hidden, Overwhelm, Raid, Restore, Saboteur, Sentinel, Shielded |

## Per-card analysis & acceptance criteria

### LOF_87 — Eighth Brother

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Ambush (When you play this unit, it may attack an enemy unit.)
> When you play another unit: You may use the Force (lose your Force token). If you do, give a unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_89 — Supremacy

**Type/Stats:** Unit, cost 12, 12/12  |  Traits: Capital Ship, First Order, Vehicle

**Rules text:**

> Ambush
> Other friendly Vehicle units get +6/+6.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_92 — Point Rain Reclaimer

**Type/Stats:** Unit, cost 1, 1/2  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When Played: If you control a Jedi unit, you may give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_95 — Lor San Tekka

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Resistance

**Rules text:**

> When Defeated: You may give an Experience token to a <uq> (unique) unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_97 — Eeth Koth

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Defeated: You may use the Force. If you do, put this card into play as a resource.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ramp'].

**Existing primitives that should suffice:** force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_102 — Yoda's Lightsaber

**Type/Stats:** Upgrade, cost 2  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a non-Vehicle unit.
> When Played: You may use the Force (lose your Force token). If you do, heal 3 damage from a base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_105 — Oppo Rancisis

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> This unit gains Ambush while another friendly unit has Ambush. The same is true for Grit, Hidden, Overwhelm, Saboteur, Sentinel, and Shielded.
> This unit gains Raid 2 while another friendly unit has Raid. The same is true for Restore.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

