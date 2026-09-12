# ash-set:01 — Support keyword

- **Group id (paste this):** `ash-set:01`
- **Kind:** keyword
- **Cards:** 29

## Keyword group: **Support**

Implement the **Support** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Support` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_8 | Moff Gideon | Leader | 7 | 5/8 | Ambush, Grit, Hidden, Overwhelm, Saboteur, Sentinel, Shielded, Support |
| ASH_9 | Ahsoka Tano | Leader | 6 | 5/6 | Support |
| ASH_14 | The Mandalorian | Leader | 6 | 4/6 | Support |
| ASH_33 | Grand Admiral Thrawn | Unit | 7 | 5/7 | Support |
| ASH_36 | Rukh | Unit | 3 | 1/5 | Support |
| ASH_37 | Red Leader | Unit | 7 | 6/6 | Support |
| ASH_46 | Scion Shuttle | Unit | 2 | 1/3 | Support |
| ASH_50 | Morgan Elsbeth | Unit | 6 | 5/6 | Support |
| ASH_59 | Leia Organa | Unit | 3 | 3/4 | Support |
| ASH_68 | Domesticated Loth-Cat | Unit | 1 | 1/3 | Ambush, Support |
| ASH_72 | Doctor Pershing | Unit | 2 | 0/4 | Support |
| ASH_74 | Mos Eisley Modifier | Unit | 3 | 1/4 | Grit, Support |
| ASH_95 | Remnant Interceptor | Unit | 2 | 2/2 | Restore, Support |
| ASH_99 | Gozanti Assault Carrier | Unit | 5 | 4/6 | Sentinel, Support |
| ASH_101 | The Great Mothers | Unit | 7 | 6/7 | Support |
| ASH_121 | Blurrg | Unit | 3 | 3/4 | Overwhelm, Support |
| ASH_130 | Fang Fighter Squadron | Unit | 5 | 5/5 | Support |
| ASH_154 | Honorable Nite Owl | Unit | 2 | 2/2 | Raid, Support |
| ASH_156 | R5-D4 | Unit | 3 | 3/4 | Support |
| ASH_168 | Migs Mayfeld | Unit | 2 | 2/3 | Support |
| ASH_189 | Emperor's Messenger | Unit | 1 | 0/3 | Support |
| ASH_202 | Carson Teva | Unit | 2 | 1/4 | Support |
| ASH_203 | Mando's N-1 Starfighter | Unit | 2 | 1/3 | Support |
| ASH_209 | Ezra Bridger | Unit | 6 | 6/6 | Support |
| ASH_215 | Flanking TIE Interceptor | Unit | 2 | 2/2 | Support |
| ASH_222 | Unsanctioned Patrol | Unit | 4 | 4/4 | Saboteur, Support |
| ASH_223 | Halo | Unit | 5 | 4/4 | Support |
| ASH_241 | Marrok's Fiend Fighter | Unit | 3 | 3/2 | Overwhelm, Support |
| ASH_253 | Yellow Aces Bomber | Unit | 3 | 2/4 | Support |

## Per-card analysis & acceptance criteria

### ASH_8 — Moff Gideon

**Type/Stats:** Leader, cost 7, 5/8  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: If a friendly Imperial unit was defeated this phase, play a unit from your hand. It costs 1 resource less.
> This unit gains each of the following keywords if it is on an Imperial unit in your discard pile: Ambush, Grit, Hidden, Overwhelm, Saboteur, Sentinel, Shielded, Support.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Residual text (needs separate ability after keyword):** Action [Exhaust]: If a friendly Imperial unit was defeated this phase, play a unit from your hand. It costs 1 resource less. This unit gains each of the following keywords if it is on an Imperial unit in your discard pile: Ambush, Grit, Hidden, Overwhelm, Saboteur, Sentinel, Shielded, Support. Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['discard', 'keyword_grant', 'ramp'].

**Existing primitives that should suffice:** DiscardFromHand, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_9 — Ahsoka Tano

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Jedi

**Rules text:**

> Action [Exhaust]: Choose a unit with less power than a friendly unit. It gets +2/+0 for this phase.
> Support (When you deploy this leader, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: You may give a unit with less power than this unit +2/+0 for this phase.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Residual text (needs separate ability after keyword):** Action [Exhaust]: Choose a unit with less power than a friendly unit. It gets +2/+0 for this phase. On Attack: You may give a unit with less power than this unit +2/+0 for this phase. Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_14 — The Mandalorian

**Type/Stats:** Leader, cost 6, 4/6  |  Traits: Mandalorian

**Rules text:**

> When you take the initiative: You may pay 1 resource. If you do, draw a card.
> Support (When you deploy this leader, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: If you have the initiative, you may draw a card.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Residual text (needs separate ability after keyword):** When you take the initiative: You may pay 1 resource. If you do, draw a card. On Attack: If you have the initiative, you may draw a card. Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw', 'ramp'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_33 — Grand Admiral Thrawn

**Type/Stats:** Unit, cost 7, 5/7  |  Traits: Imperial, Official

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> When Attack Ends: If the defending unit was defeated, ready this unit.

**Residual text (needs separate ability after keyword):** When Attack Ends: If the defending unit was defeated, ready this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_36 — Rukh

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Imperial

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> When Attack Ends: If the defending unit was defeated, you may give 3 Advantage tokens to a unit.

**Residual text (needs separate ability after keyword):** When Attack Ends: If the defending unit was defeated, you may give 3 Advantage tokens to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_37 — Red Leader

**Type/Stats:** Unit, cost 7, 6/6  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> This unit may attack units in either arena.

**Residual text (needs separate ability after keyword):** This unit may attack units in either arena.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_46 — Scion Shuttle

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Imperial, Transport, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> While this unit is attacking, the defending unit gets –1/–1.

**Residual text (needs separate ability after keyword):** While this unit is attacking, the defending unit gets –1/–1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_50 — Morgan Elsbeth

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Force, Night

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> When Defeated: You may give a unit –2/–2 for this phase.

**Residual text (needs separate ability after keyword):** When Defeated: You may give a unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_59 — Leia Organa

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Official, Rebel

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: You may deal 1 damage to this unit. If you do, heal 2 damage from your base.

**Residual text (needs separate ability after keyword):** On Attack: You may deal 1 damage to this unit. If you do, heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_68 — Domesticated Loth-Cat

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Creature

**Rules text:**

> Enemy units lose Ambush and Support.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_72 — Doctor Pershing

**Type/Stats:** Unit, cost 2, 0/4  |  Traits: New Republic

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: If this unit has 3 or more remaining HP, draw a card.

**Residual text (needs separate ability after keyword):** On Attack: If this unit has 3 or more remaining HP, draw a card.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_74 — Mos Eisley Modifier

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Fringe

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> Grit (This unit gets +1/+0 for each damage on it.)

**Residual text (needs separate ability after keyword):** Grit (This unit gets +1/+0 for each damage on it.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_95 — Remnant Interceptor

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> Restore 1 (When this unit attacks, heal 1 damage from your base.)

**Residual text (needs separate ability after keyword):** Restore 1 (When this unit attacks, heal 1 damage from your base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_99 — Gozanti Assault Carrier

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: This unit gains Sentinel for this phase.

**Residual text (needs separate ability after keyword):** On Attack: This unit gains Sentinel for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_101 — The Great Mothers

**Type/Stats:** Unit, cost 7, 6/7  |  Traits: Force, Night

**Rules text:**

> Support
> When Attack Ends: If this unit dealt combat damage to 1 or more non-leader units, defeat those units.

**Residual text (needs separate ability after keyword):** When Attack Ends: If this unit dealt combat damage to 1 or more non-leader units, defeat those units.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_121 — Blurrg

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Creature

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Residual text (needs separate ability after keyword):** Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_130 — Fang Fighter Squadron

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_154 — Honorable Nite Owl

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Mandalorian, Trooper

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> Raid 1 (This unit gets +1/+0 while attacking.)

**Residual text (needs separate ability after keyword):** Raid 1 (This unit gets +1/+0 while attacking.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_156 — R5-D4

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Droid

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: Defeat all upgrades on the defending unit.

**Residual text (needs separate ability after keyword):** On Attack: Defeat all upgrades on the defending unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_168 — Migs Mayfeld

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Fringe

**Rules text:**

> Support
> On Attack: Deal 1 damage to the defending unit. If this unit is upgraded, deal 2 damage to the defending unit instead.

**Residual text (needs separate ability after keyword):** On Attack: Deal 1 damage to the defending unit. If this unit is upgraded, deal 2 damage to the defending unit instead.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_189 — Emperor's Messenger

**Type/Stats:** Unit, cost 1, 0/3  |  Traits: Droid, Imperial

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: Ready a resource.

**Residual text (needs separate ability after keyword):** On Attack: Ready a resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_202 — Carson Teva

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: New Republic

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> While attacking, this unit deals combat damage before the defender.

**Residual text (needs separate ability after keyword):** While attacking, this unit deals combat damage before the defender.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_203 — Mando's N-1 Starfighter

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Mandalorian, Vehicle

**Rules text:**

> Support
> On Attack: You may exhaust a friendly (non-upgrade) leader. If you do, this unit gets +2/+0 for this attack.

**Residual text (needs separate ability after keyword):** On Attack: You may exhaust a friendly (non-upgrade) leader. If you do, this unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_209 — Ezra Bridger

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Force, Jedi, Spectre

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: If this unit is upgraded, you may give a unit –3/–0 for this phase.

**Residual text (needs separate ability after keyword):** On Attack: If this unit is upgraded, you may give a unit –3/–0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_215 — Flanking TIE Interceptor

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_222 — Unsanctioned Patrol

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Fighter, Resistance, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Residual text (needs separate ability after keyword):** Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_223 — Halo

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> When Attack Ends: If the defending unit was defeated, give a Shield token to this unit.

**Residual text (needs separate ability after keyword):** When Attack Ends: If the defending unit was defeated, give a Shield token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_241 — Marrok's Fiend Fighter

**Type/Stats:** Unit, cost 3, 3/2  |  Traits: Fighter, Vehicle

**Rules text:**

> Support
> Overwhelm
> This unit gets +2/+0 while attacking a damaged unit.

**Residual text (needs separate ability after keyword):** Overwhelm This unit gets +2/+0 while attacking a damaged unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_253 — Yellow Aces Bomber

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Fighter, New Republic, Vehicle

**Rules text:**

> Support (When you play this unit, you may attack with another unit. It gains this unit's other abilities for this attack.)
> On Attack: If this unit is upgraded, deal 2 damage to a base.

**Residual text (needs separate ability after keyword):** On Attack: If this unit is upgraded, deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

