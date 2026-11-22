# hmw-set:22 — Miscellaneous abilities

- **Group id (paste this):** `hmw-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_18 | The Warrior | Leader | 5 | 3/6 | Ambush, Raid |
| HMW_53 | Fett's Firespray | Unit | 6 | 6/6 | Ambush |
| HMW_57 | Boss Lyonie | Unit | 5 | 5/5 |  |
| HMW_88 | Numa | Unit | 4 | 4/4 | Restore |
| HMW_105 | Nute Gunray | Unit | 2 | 2/2 |  |
| HMW_108 | The First Legion | Unit | 4 | 5/5 |  |
| HMW_134 | Zam Wesell | Unit | 2 | 2/4 | Hidden |

## Per-card analysis & acceptance criteria

### HMW_18 — The Warrior

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Tusken

**Rules text:**

> Action [1 resource, Exhaust]: Play a unit with 3 or less power from your hand (paying its cost) and give it Ambush for this phase.
> Ambush (When you deploy this leader, she may immediately attack an enemy unit.)
> Raid 1 (This unit gets +1/+0 while attacking.)
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_53 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Friendly units can attack bases while using Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_57 — Boss Lyonie

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Gungan, Official

**Rules text:**

> When Played/On Attack: You may choose a token upgrade attached to another unit. Give another one of those tokens to that unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_88 — Numa

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Rebel, Twi'lek

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> If this unit would be dealt damage, prevent 1 of that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_105 — Nute Gunray

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Official, Separatist

**Rules text:**

> When Played: Each friendly unit (including this one) deals 1 damage to a different enemy unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_108 — The First Legion

**Type/Stats:** Unit, cost 4, 5/5  |  Traits: Imperial, Trooper

**Rules text:**

> On Attack: Name a trait. Enemy cards, including those not in play, lose that trait for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_134 — Zam Wesell

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Hidden
> This unit gains each friendly leader's traits except Force, even while she's not in play.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

