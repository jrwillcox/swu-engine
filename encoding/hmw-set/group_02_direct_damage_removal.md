# hmw-set:02 — Direct damage & removal

- **Group id (paste this):** `hmw-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_5 | Jar Jar Binks | Leader | 6 | 4/5 | Shielded |
| HMW_11 | Darth Sidious | Leader | 6 | 4/5 | Hidden |
| HMW_13 | Cham Syndulla | Leader | 6 | 3/8 |  |
| HMW_36 | Kelnacca | Unit | 4 | 4/5 | Restore |
| HMW_43 | Darth Vader | Unit | 9 | 9/8 | Saboteur |
| HMW_45 | Logray | Unit | 2 | 1/5 |  |
| HMW_46 | Krrsantan | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### HMW_5 — Jar Jar Binks

**Type/Stats:** Leader, cost 6, 4/5  |  Traits: Gungan

**Rules text:**

> Action [1 resource, Exhaust]: If you gave a token upgrade to a unit this phase, deal 1 damage to a unit and heal 1 damage from a base.
> Shielded (When you deploy this leader, give a Shield token to him.)
> On Attack: If you gave a token upgrade to a unit this phase, you may deal 1 damage to a unit and heal 1 damage from a base.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal'].

**Existing primitives that should suffice:** DealDamage, Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_11 — Darth Sidious

**Type/Stats:** Leader, cost 6, 4/5  |  Traits: Force, Sith

**Rules text:**

> When you deal 4 or more damage to a unit or base: You may exhaust this leader. If you do, deal 1 damage to a different unit or base.
> Hidden (This unit can't be attacked if he was deployed this phase.)
> When you deal 4 or more damage to a unit or base: You may deal 1 damage to a different unit or base.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_13 — Cham Syndulla

**Type/Stats:** Leader, cost 6, 3/8  |  Traits: Twi'lek

**Rules text:**

> When non-combat damage is dealt to a friendly unit or base: You may exhaust this leader. If you do, deal 1 damage to an enemy unit or base.
> When non-combat damage is dealt to a friendly unit or base: You may deal 1 damage to an enemy unit or base.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_36 — Kelnacca

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Force, Jedi, Wookiee

**Rules text:**

> Restore 2
> When Played: You may pay any number of resources. For every 3 resources paid this way, deal damage equal to this unit's power to an enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_43 — Darth Vader

**Type/Stats:** Unit, cost 9, 9/8  |  Traits: Force, Imperial, Sith

**Rules text:**

> Saboteur
> When Played: Search the top 8 cards of your deck for up to 2 units that each cost 4 or less, play them for free, and deal 2 damage to each of them.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_45 — Logray

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Ewok

**Rules text:**

> When another friendly unit that costs 3 or less is dealt damage: You may deal 1 damage to an enemy unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_46 — Krrsantan

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Underworld, Wookiee

**Rules text:**

> When Played: You may deal damage equal to the number of resources you control minus 3 to a ground unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

