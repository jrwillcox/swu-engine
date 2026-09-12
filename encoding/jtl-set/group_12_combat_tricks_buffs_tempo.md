# jtl-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtl-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_15 | Rio Durant | Leader | 5 | 3/5 | Saboteur |
| JTL_16 | Admiral Ackbar | Leader | 6 | 3/8 |  |
| JTL_32 | Director Krennic | Unit | 2 | 2/2 | Shielded |
| JTL_34 | Interceptor Ace | Unit | 3 | 2/3 | Grit, Piloting |
| JTL_36 | Iden Versio | Unit | 4 | 4/3 | Piloting, Shielded |
| JTL_42 | Power from Pain | Event | 3 |  |  |
| JTL_44 | Echo Base Engineer | Unit | 2 | 2/3 |  |

## Per-card analysis & acceptance criteria

### JTL_15 — Rio Durant

**Type/Stats:** Leader, cost 5, 3/5  |  Traits: Pilot, Underworld

**Rules text:**

> Action [1 resource, Exhaust]: Attack with a space unit. It gets +1/+0 and gains Saboteur for this attack. (Ignore Sentinel and defeat the defender's Shields.)
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> Attached unit is a leader unit. It gains Saboteur. If it's a Transport, it also gets +1/+0.
> 
> Epic Action: If you control 5 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_modal, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_16 — Admiral Ackbar

**Type/Stats:** Leader, cost 6, 3/8  |  Traits: Official, Rebel

**Rules text:**

> Action [1 resource, Exhaust]: Exhaust a non-leader unit. If you do, its controller creates an X-Wing token.
> On Attack: You may exhaust a unit. If you do, its controller creates an X-Wing token.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_32 — Director Krennic

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Imperial, Official

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> The first unit you play each round that has a “When Defeated” ability costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_34 — Interceptor Ace

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Imperial, Pilot

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> Piloting [3 resources Vigilance Villainy] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains Grit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_36 — Iden Versio

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Imperial, Pilot

**Rules text:**

> Shielded
> Piloting [3 resources Vigilance Villainy]
> When this upgrade attaches to a unit: Give a Shield token to that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_42 — Power from Pain

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Give a unit +1/+0 for this phase for each damage on it.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_44 — Echo Base Engineer

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Rebel

**Rules text:**

> When Played: You may give a Shield token to a damaged Vehicle unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

