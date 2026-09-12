# lofp-set:02 — Card advantage & disruption

- **Group id (paste this):** `lofp-set:02`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOFP_1 | Luthen Rael | Unit | 4 | 4/5 |  |
| LOFP_12 | Do or Do Not | Event | 2 |  |  |

## Per-card analysis & acceptance criteria

### LOFP_1 — Luthen Rael

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Rebel

**Rules text:**

> On Attack: Search the top 5 cards of your deck for an Item upgrade, reveal it, and draw it. 

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOFP_12 — Do or Do Not

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> You may use the Force . If you do, draw 2 cards. If you do not, draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

