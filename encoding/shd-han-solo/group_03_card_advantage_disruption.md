# shd-han-solo:03 — Card advantage & disruption

- **Group id (paste this):** `shd-han-solo:03`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_249 | Wookiee Warrior | Unit | 4 | 2/5 | Grit |

## Per-card analysis & acceptance criteria

### SHD_249 — Wookiee Warrior

**Type/Stats:** Unit, cost 4, 2/5  |  Traits: Wookiee

**Rules text:**

> Grit (This unit gets +1/+0 for each damage on it.)
> When Played: If you control another Wookiee unit, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

