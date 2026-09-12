# jtl-set:14 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:14`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_71 | CR90 Relief Runner | Unit | 6 | 4/6 | Restore |
| JTL_72 | Wing Guard Security Team | Unit | 6 | 4/4 | Sentinel |
| JTL_73 | Grim Valor | Upgrade | 1 |  |  |
| JTL_76 | Covering the Wing | Event | 2 |  |  |
| JTL_77 | In the Heat of Battle | Event | 2 |  | Saboteur, Sentinel |
| JTL_81 | First Order TIE Fighter | Unit | 1 | 2/1 | Raid |
| JTL_86 | Wingman Victor Three | Unit | 3 | 4/3 | Piloting |

## Per-card analysis & acceptance criteria

### JTL_71 — CR90 Relief Runner

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> When Defeated: Heal up to 3 damage from a unit or base.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_72 — Wing Guard Security Team

**Type/Stats:** Unit, cost 6, 4/4  |  Traits: Fringe, Trooper

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> When Played: Give a Shield token to each of up to 2 Fringe units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_73 — Grim Valor

**Type/Stats:** Upgrade, cost 1  |  Traits: Innate

**Rules text:**

> Attached unit gains: “When Defeated: You may exhaust a unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_76 — Covering the Wing

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Create an X-Wing token. You may give a Shield token to another unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_77 — In the Heat of Battle

**Type/Stats:** Event, cost 2  |  Traits: Disaster

**Rules text:**

> Each unit gains Sentinel and loses Saboteur for this phase.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_81 — First Order TIE Fighter

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Fighter, First Order, Vehicle

**Rules text:**

> While you control a token unit, this unit gains Raid 1. (It gets +1/+0 while attacking.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_86 — Wingman Victor Three

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Imperial, Pilot

**Rules text:**

> Piloting [1 resource Command Villainy] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> When played as an upgrade: You may give an Experience token to another unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

