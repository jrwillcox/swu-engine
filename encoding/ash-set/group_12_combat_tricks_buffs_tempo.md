# ash-set:12 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:12`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_1 | The Armorer | Leader | 5 | 4/6 |  |
| ASH_2 | Fennec Shand | Leader | 4 | 3/4 | Saboteur |
| ASH_3 | Baylan Skoll | Leader | 5 | 4/6 | Sentinel |
| ASH_5 | Luke Skywalker | Leader | 7 | 6/7 |  |
| ASH_6 | Sabine Wren | Leader | 5 | 3/5 | Shielded |
| ASH_7 | Grand Admiral Sloane | Leader | 5 | 4/5 | Overwhelm, Sentinel |
| ASH_10 | Bo-Katan Kryze | Leader | 10 | 4/7 |  |

## Per-card analysis & acceptance criteria

### ASH_1 — The Armorer

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Mandalorian

**Rules text:**

> Action [Exhaust]: Play an upgrade from your resources on a unit that entered play this phase (paying its cost). If you do, resource the top card of your deck.
> When Attack Ends: You may play an upgrade from your resources on a friendly unit. If you do, resource the top card of your deck.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_2 — Fennec Shand

**Type/Stats:** Leader, cost 4, 3/4  |  Traits: Underworld

**Rules text:**

> Action [1 resource, Exhaust, exhaust a friendly unit]: Play a unit from your hand (paying its cost). It enters play ready.
> Saboteur
> Action [1 resource, exhaust a friendly unit]: Play a unit from your hand. It enters play ready.
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_3 — Baylan Skoll

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Force

**Rules text:**

> Action [1 resource, Exhaust]: Give a friendly unit +2/+2 for this phase if it's the only unit you control in its arena.
> On Attack: You may give a friendly unit +2/+2 and Sentinel for this phase if it's the only non-leader unit you control in its arena. (Enemy units in its arena must attack a Sentinel when they attack you.)
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_5 — Luke Skywalker

**Type/Stats:** Leader, cost 7, 6/7  |  Traits: Force, Jedi, Rebel

**Rules text:**

> When a friendly unit's attack ends: You may exhaust this leader. If you do, heal 1 damage from that unit.
> When a friendly unit's attack ends: Heal 2 damage from that unit or from your base.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['heal', 'ready_exhaust'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_6 — Sabine Wren

**Type/Stats:** Leader, cost 5, 3/5  |  Traits: Jedi, Mandalorian, Spectre

**Rules text:**

> Action [Exhaust]: An opponent gives 2 Advantage tokens to a unit they control. If they do, the next unit you play this phase gains Shielded for this phase. (When you play that unit, give a Shield token to it.)
> On Attack: The next unit you play this phase gains Shielded for this phase.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_7 — Grand Admiral Sloane

**Type/Stats:** Leader, cost 5, 4/5  |  Traits: Imperial, Official

**Rules text:**

> Action [Exhaust]: Choose one:
> Give each ground unit Sentinel and Overwhelm for this phase.
> Give each space unit Sentinel and Overwhelm for this phase.
> 
> Overwhelm
> Each other friendly unit gains Overwhelm and Sentinel.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_10 — Bo-Katan Kryze

**Type/Stats:** Leader, cost 10, 4/7  |  Traits: Mandalorian

**Rules text:**

> Action [2 resources, Exhaust]: If you control a unit in each arena, create a Mandalorian token.
> Other friendly Mandalorian units get +1/+0.
> On Attack: If you control a unit in each arena, create a Mandalorian token.
> Epic Action: If the number of resources you control plus the number of friendly Mandalorian units is 10 or more, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

