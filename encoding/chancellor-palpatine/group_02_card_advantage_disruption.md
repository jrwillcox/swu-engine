# chancellor-palpatine:02 — Card advantage & disruption

- **Group id (paste this):** `chancellor-palpatine:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_1 | Chancellor Palpatine | Leader | 7 | 6/8 | Plot |

## Per-card analysis & acceptance criteria

### SEC_1 — Chancellor Palpatine

**Type/Stats:** Leader, cost 7, 6/8  |  Traits: Official, Republic

**Rules text:**

> Action [1 resource, Exhaust]: Search the top 5 cards of your deck for a card with Plot, reveal it, and draw it. (Put the other cards on the bottom of your deck in a random order.)
> When Deployed: The next card you play using Plot this phase costs 3 resources less.
> Epic Action: If you control 7 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

