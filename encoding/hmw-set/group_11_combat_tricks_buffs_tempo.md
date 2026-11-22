# hmw-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `hmw-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_1 | Asajj Ventress | Leader | 5 | 3/6 | Raid, Restore |
| HMW_6 | Omega | Leader | 5 | 2/7 | Grit |
| HMW_7 | Darth Vader | Leader | 6 | 5/5 | Raid |
| HMW_8 | General Grievous | Leader | 5 | 3/6 |  |
| HMW_9 | Chewbacca | Leader | 5 | 3/6 |  |
| HMW_17 | Osha | Leader | 6 | 5/6 | Saboteur |
| HMW_35 | Hunter | Unit | 6 | 4/7 |  |

## Per-card analysis & acceptance criteria

### HMW_1 — Asajj Ventress

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Night

**Rules text:**

> Action [Exhaust]: Attack with a unit. For this attack, replace any Raid it has or gains with Restore, or vice versa.
> Restore 2
> Action: Attack with a unit. For this attack, replace any Raid it has or gains with Restore, or vice versa.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_6 — Omega

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Clone

**Rules text:**

> Action [1 resource, Exhaust]: Attack with a Heroism unit. It gains Grit for this attack. (It gets +1/+0 for each damage on it.)
> Other friendly Heroism units gain Grit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_7 — Darth Vader

**Type/Stats:** Leader, cost 6, 5/5  |  Traits: Force, Imperial, Sith

**Rules text:**

> Friendly units that cost 3 or more gain Raid 1.
> Raid 1
> Other friendly units that cost 3 or more gain Raid 1.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_8 — General Grievous

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Official, Separatist

**Rules text:**

> Action [Exhaust]: Play 2 units from your hand (one at a time, paying their costs).
> While you control more units than an opponent, this unit gets +3/+0.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_9 — Chewbacca

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Rebel, Wookiee

**Rules text:**

> Action [2 resources, Exhaust]: Attack with a unit, even if it's exhausted. It can't attack bases for this attack.
> Action: Attack with a unit, even if it's exhausted. It can't attack bases for this attack. Use this ability only once each round.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_17 — Osha

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force

**Rules text:**

> Action [Exhaust]: If a friendly Heroism unit was defeated this phase, play a Villainy unit from your resources, ignoring its Villainy aspect penalties. If you do, you may resource a card from your hand.
> Saboteur
> Action: Play a Villainy unit from your resources, ignoring its Villainy aspect penalties. If you do, you may resource a card from your hand.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_35 — Hunter

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Clone

**Rules text:**

> When Played: Choose two. You may choose the same option more than once:
> Give a Shield token to a unit.
> Attack with a unit, even if it's exhausted. It can't attack bases for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token', 'attack_grant'].

**Existing primitives that should suffice:** GiveToken, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

