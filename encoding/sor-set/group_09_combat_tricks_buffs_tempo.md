# sor-set:09 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:09`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_1 | Director Krennic | Leader | 5 | 2/7 | Restore |
| SOR_2 | Iden Versio | Leader | 6 | 4/4 | Shielded |
| SOR_3 | Chewbacca | Leader | 7 | 2/9 | Grit, Sentinel |
| SOR_4 | Chirrut Îmwe | Leader | 5 | 3/5 |  |
| SOR_7 | Grand Moff Tarkin | Leader | 5 | 2/7 |  |
| SOR_8 | Hera Syndulla | Leader | 6 | 4/6 |  |
| SOR_9 | Leia Organa | Leader | 5 | 3/6 | Raid |

## Per-card analysis & acceptance criteria

### SOR_1 — Director Krennic

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Imperial, Official

**Rules text:**

> Each friendly damaged unit gets +1/+0. 
> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> 
> Each friendly damaged unit gets +1/+0.
> Epic Action: If you control 5 or more resources, deploy this leader. 

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_2 — Iden Versio

**Type/Stats:** Leader, cost 6, 4/4  |  Traits: Imperial, Trooper

**Rules text:**

> Action [Exhaust]: If an enemy unit was defeated this phase, heal 1 damage from your base.
> Shielded (When you deploy this leader, give her a Shield token.)
> 
> When an enemy unit is defeated: Heal 1 damage from your base.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_3 — Chewbacca

**Type/Stats:** Leader, cost 7, 2/9  |  Traits: Underworld, Wookiee

**Rules text:**

> Action [exhaust]: Play a unit that costs 3 or less from your hand (paying its cost). It gains Sentinel for this phase.
> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> Grit (This unit gains +1/+0 for each damage on it.)
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_4 — Chirrut Îmwe

**Type/Stats:** Leader, cost 5, 3/5  |  Traits: Force, Rebel

**Rules text:**

> Action [Exhaust]: Give a unit +0/+2 for this phase.
> During the action phase, this unit isn't defeated by having no remaining HP. (During the regroup phase, if he has no remaining HP, defeat him.)
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_7 — Grand Moff Tarkin

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Imperial, Official

**Rules text:**

> Action [1 resource, exhaust]: Give an Experience token to an Imperial unit.
> On Attack: You may give an Experience token to another Imperial unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_8 — Hera Syndulla

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Rebel, Spectre, Twi'lek

**Rules text:**

> Ignore the aspect penalty on SPECTRE cards you play.
> Ignore the aspect penalty on SPECTRE cards you play.
> 
> On Attack: You may give an Experience token to another unique unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_9 — Leia Organa

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Official, Rebel

**Rules text:**

> Action [exhaust]: Attack with a Rebel unit. Then, you may attack with another Rebel unit.
> Raid 1 (This unit gets +1/+0 while attacking.)
> 
> When this unit completes an attack: You may attack with another Rebel unit. 
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

