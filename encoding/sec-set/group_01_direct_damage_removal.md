# sec-set:01 — Direct damage & removal

- **Group id (paste this):** `sec-set:01`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_2 | Jabba the Hutt | Leader | 5 | 2/8 |  |
| SEC_3 | Lama Su | Leader | 6 | 3/7 |  |
| SEC_5 | Satine Kryze | Leader | 5 | 0/8 | Restore |
| SEC_10 | Dedra Meero | Leader | 4 | 2/5 | Raid |
| SEC_13 | Luthen Rael | Leader | 5 | 2/7 |  |
| SEC_14 | Sly Moore | Leader | 5 | 3/6 |  |
| SEC_39 | Creditor's Claim | Upgrade | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_2 — Jabba the Hutt

**Type/Stats:** Leader, cost 5, 2/8  |  Traits: Hutt, Underworld

**Rules text:**

> Action [1 resource, Exhaust]: A friendly damaged unit deals 1 damage to an enemy unit. If the friendly unit has 3 or more damage on it, it deals 2 damage instead.
> When another friendly unit is dealt damage and survives: You may have that unit deal that much damage to an enemy unit. Use this ability only once each round.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_3 — Lama Su

**Type/Stats:** Leader, cost 6, 3/7  |  Traits: Kaminoan, Official

**Rules text:**

> Action [Exhaust]: Play an upgrade from your hand on a friendly non-Vehicle unit. It costs 1 resource less. If you do, deal 1 damage to that unit.
> When this unit completes an attack (and survives): You may play an upgrade from your discard pile on a friendly non-Vehicle unit. It costs 1 resource less.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'discard', 'ramp'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_5 — Satine Kryze

**Type/Stats:** Leader, cost 5, 0/8  |  Traits: Mandalorian, Official

**Rules text:**

> Action [Exhaust]: Heal up to 2 damage from a unit. If you do, deal that much damage to your base.
> Restore 4
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_10 — Dedra Meero

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Imperial, Official

**Rules text:**

> Action [1 resource, Exhaust]: Choose an enemy unit. Its controller may deal 2 damage to it. If they don't, draw a card.
> While you have more cards in hand than an opponent, this unit gains Raid 2. (She gets +2/+0 while attacking.)
> Epic Action: If you control 4 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'draw', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, DrawCards, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_13 — Luthen Rael

**Type/Stats:** Leader, cost 5, 2/7  |  Traits: Rebel

**Rules text:**

> When a friendly unit is defeated while attacking: You may exhaust this leader. If you do, deal 1 damage to a unit or base.
> When a friendly unit is defeated while attacking: You may deal 2 damage to a unit or base.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_14 — Sly Moore

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Imperial, Official

**Rules text:**

> Action [1 resource, Exhaust]: If there are 4 or more exhausted units in play, create a Spy token.
> On Attack: You may deal 2 damage to an exhausted unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_39 — Creditor's Claim

**Type/Stats:** Upgrade, cost 3  |  Traits: Supply

**Rules text:**

> Attached unit gains: “When Defeated: You may defeat a unit with 3 or less remaining HP.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

