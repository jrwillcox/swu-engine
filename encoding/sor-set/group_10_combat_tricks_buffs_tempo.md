# sor-set:10 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_12 | IG-88 | Leader | 5 | 5/4 | Raid |
| SOR_15 | Boba Fett | Leader | 5 | 4/7 |  |
| SOR_16 | Grand Admiral Thrawn | Leader | 6 | 3/9 |  |
| SOR_18 | Jyn Erso | Leader | 6 | 4/7 |  |
| SOR_19 | Security Complex | Base |  | None/25 |  |
| SOR_28 | Jedha City | Base |  | None/25 |  |
| SOR_35 | Lieutenant Childsen | Unit | 4 | 2/2 | Sentinel |

## Per-card analysis & acceptance criteria

### SOR_12 — IG-88

**Type/Stats:** Leader, cost 5, 5/4  |  Traits: Bounty Hunter, Droid, Underworld

**Rules text:**

> Action [Exhaust]: Attack with a unit. If you control more units than the defending player, the attacker gets +1/+0 for this attack.
> Each other friendly unit gains Raid 1. (They get +1/+0 while attacking.)
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_15 — Boba Fett

**Type/Stats:** Leader, cost 5, 4/7  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When an enemy unit leaves play: You may exhaust this leader. If you do, ready a resource.
> When this unit completes an attack: If an enemy unit left play this phase, ready up to 2 resources.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_16 — Grand Admiral Thrawn

**Type/Stats:** Leader, cost 6, 3/9  |  Traits: Imperial, Official

**Rules text:**

> When the action phase starts: Look at the top card of each player's deck.
> 
> Action [1 resource, exhaust]: Reveal the top card of any player's deck. Exhaust a unit that costs the same as or less than the revealed card.
> When the action phase starts: Look at the top card of each player's deck.
> 
> On Attack: You may reveal the top card of any player's deck. Exhaust a unit that costs the same as or less than the revealed card.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'search'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_18 — Jyn Erso

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Rebel

**Rules text:**

> Action [Exhaust]: Attack with a unit. The defender gets -1/-0 for this attack.
> While a friendly unit is attacking, the defender gets -1/-0.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_19 — Security Complex

**Type/Stats:** Base

**Rules text:**

> Epic Action: Give a Shield token to a non-leader unit.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_28 — Jedha City

**Type/Stats:** Base

**Rules text:**

> Epic Action: Give a non-leader unit -4/-0 for this phase.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_35 — Lieutenant Childsen

**Type/Stats:** Unit, cost 4, 2/2  |  Traits: Imperial, Official

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> When Played: Reveal up to 4 [Vigilance] cards from your hand. For each card revealed this way, give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

