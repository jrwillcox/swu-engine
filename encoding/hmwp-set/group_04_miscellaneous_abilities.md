# hmwp-set:04 — Miscellaneous abilities

- **Group id (paste this):** `hmwp-set:04`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMWP_9 | Zam Wesell | Unit | 2 | 2/4 | Hidden |
| HMWP_12 | Teebo | Unit | 1 | 3/1 | Hidden |
| HMWP_18 | New Tactics | Event | 5 |  |  |

## Per-card analysis & acceptance criteria

### HMWP_9 — Zam Wesell

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Hidden
> This unit gains each friendly leader's traits except Force, even while she's not in play.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_12 — Teebo

**Type/Stats:** Unit, cost 1, 3/1  |  Traits: Ewok

**Rules text:**

> Hidden 
> Other friendly Ewok units gain Hidden.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMWP_18 — New Tactics

**Type/Stats:** Event, cost 5  |  Traits: Learned, Tactic

**Rules text:**

> Choose a non-leader unit. Its owner puts it on the top or bottom of their deck. 

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

