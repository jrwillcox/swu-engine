# shd-han-solo:05 — New primitive: play-from-hand-act-on-result

- **Group id (paste this):** `shd-han-solo:05`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** play-from-hand-act-on-result — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_13 | Han Solo | Leader | 5 | 3/6 |  |

## Per-card analysis & acceptance criteria

### SHD_13 — Han Solo

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Underworld

**Rules text:**

> Action [Exhaust]: Play a unit from your hand. It costs 1 resource less. Deal 2 damage to it.
> Action: Play a unit from your hand. It costs 1 resource less. Deal 2 damage to it.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, push_play_from_hand, CostReduction.

**⚠ Suspected NEW primitive:** play-from-hand-act-on-result. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

