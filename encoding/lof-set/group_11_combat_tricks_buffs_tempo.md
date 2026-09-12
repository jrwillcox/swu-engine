# lof-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_64 | Tauntaun | Unit | 3 | 3/3 |  |
| LOF_72 | Priestesses of the Force | Unit | 7 | 6/8 |  |
| LOF_75 | Cure Wounds | Event | 1 |  |  |
| LOF_76 | Soresu Stance | Event | 1 |  |  |
| LOF_81 | Sith Legionnaire | Unit | 2 | 2/2 |  |
| LOF_85 | Praetorian Guard | Unit | 3 | 2/5 | Sentinel |
| LOF_86 | Drengir Spawn | Unit | 4 | 3/3 | Overwhelm |

## Per-card analysis & acceptance criteria

### LOF_64 — Tauntaun

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Creature

**Rules text:**

> When Defeated: You may give a Shield token to a damaged non-Vehicle unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_72 — Priestesses of the Force

**Type/Stats:** Unit, cost 7, 6/8  |  Traits: Force

**Rules text:**

> When Played: You may use the Force (lose your Force token). If you do, give a Shield token to each of up to 5 units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_75 — Cure Wounds

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Use the Force (lose your Force token). If you do, heal 6 damage from a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_76 — Soresu Stance

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Play a Force unit from your hand (paying its cost) and give a Shield token to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_81 — Sith Legionnaire

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Sith, Trooper

**Rules text:**

> While you control another Villainy unit, this unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_85 — Praetorian Guard

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: First Order

**Rules text:**

> While you control a unit with 4 or more power, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_86 — Drengir Spawn

**Type/Stats:** Unit, cost 4, 3/3  |  Traits: Creature

**Rules text:**

> Overwhelm
> When this unit attacks and defeats a unit: Give a number of Experience tokens to this unit equal to the defeated unit's cost.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

