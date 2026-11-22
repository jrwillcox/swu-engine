# hmw-set:25 — New primitive: weakness-token

- **Group id (paste this):** `hmw-set:25`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** weakness-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_2 | Maz Kanata | Leader | 6 | 4/4 | Hidden |
| HMW_3 | Doctor Hemlock | Leader | 6 | 3/6 |  |
| HMW_15 | Bossk | Leader | 5 | 4/5 |  |
| HMW_40 | Talzin's Shuttle | Unit | 3 | 2/4 | Raid |
| HMW_59 | Clone X Assassin | Unit | 2 | 1/3 |  |
| HMW_62 | Nuvo Vindi | Unit | 3 | 1/4 |  |
| HMW_65 | Clone of the Zillo Beast | Unit | 4 | 6/6 |  |

## Per-card analysis & acceptance criteria

### HMW_2 — Maz Kanata

**Type/Stats:** Leader, cost 6, 4/4  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Play a Fringe or Underworld unit from your hand. It costs 1 resource less. Give a Weakness token to it.
> Hidden (This unit can't be attacked if she was deployed this phase.)
> Action: Play a Fringe or Underworld unit from your hand. It costs 1 resource less. Give a Weakness token to it.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_3 — Doctor Hemlock

**Type/Stats:** Leader, cost 6, 3/6  |  Traits: Imperial, Official

**Rules text:**

> Action [1 resource, Exhaust]: Give a Weakness token to a unit without a Weakness token on it.
> On Attack: You may give a Weakness token to a unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_15 — Bossk

**Type/Stats:** Leader, cost 5, 4/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Action [Exhaust]: Heal 1 damage from a damaged enemy unit and give a Weakness token to it.
> On Attack: You may deal 2 damage to a unit with a token upgrade on it. (Shield and Weakness tokens are token upgrades.)
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal', 'token'].

**Existing primitives that should suffice:** DealDamage, Heal.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_40 — Talzin's Shuttle

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Night, Transport, Vehicle

**Rules text:**

> Raid 1 (This unit gets +1/+0 while attacking.)
> When Played: If an opponent played 2 or more cards this phase, you may give 2 Weakness tokens to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_59 — Clone X Assassin

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Clone, Imperial, Trooper

**Rules text:**

> When Defeated: You may give a Weakness token to a unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_62 — Nuvo Vindi

**Type/Stats:** Unit, cost 3, 1/4  |  Traits: Separatist

**Rules text:**

> When Played: You may give a Weakness token to a unit.
> When an enemy unit with a Weakness token on it is defeated: You may give a Weakness token to a unit. Use this ability only once each round.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_65 — Clone of the Zillo Beast

**Type/Stats:** Unit, cost 4, 6/6  |  Traits: Clone, Creature

**Rules text:**

> Other friendly units get –2/–2.
> On Attack: You may give a Weakness token to a unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

