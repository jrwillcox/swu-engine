# lof-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_237 | The Son | Unit | 7 | 6/8 |  |
| LOF_241 | In the Shadows | Event | 2 |  | Hidden |
| LOF_244 | Jedi Vector | Unit | 2 | 1/3 |  |
| LOF_250 | Medical Frigate | Unit | 4 | 3/6 |  |
| LOF_252 | The Daughter | Unit | 5 | 4/6 |  |
| LOF_258 | Peli Motto | Unit | 2 | 1/4 |  |
| LOF_263 | Last Words | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LOF_237 — The Son

**Type/Stats:** Unit, cost 7, 6/8  |  Traits: Force

**Rules text:**

> While the Force is with you, each friendly unit gets +2/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_241 — In the Shadows

**Type/Stats:** Event, cost 2  |  Traits: Plan

**Rules text:**

> Give an Experience token to each of up to 3 friendly units with Hidden.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_244 — Jedi Vector

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Fighter, Jedi, Vehicle

**Rules text:**

> This unit gets +1/+0 if you control another Jedi unit and +1/+0 if you control a Lightsaber upgrade.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_250 — Medical Frigate

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Capital Ship, Republic, Vehicle

**Rules text:**

> On Attack: You may heal 2 damage from another unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_252 — The Daughter

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Force

**Rules text:**

> When damage is dealt to your base: You may use the Force (lose your Force token). If you do, heal 2 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_258 — Peli Motto

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Fringe

**Rules text:**

> On Attack: Give an Experience token to a friendly Vehicle or Droid unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_263 — Last Words

**Type/Stats:** Event, cost 2  |  Traits: Learned

**Rules text:**

> If a friendly unit was defeated this phase, give 2 Experience tokens to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

