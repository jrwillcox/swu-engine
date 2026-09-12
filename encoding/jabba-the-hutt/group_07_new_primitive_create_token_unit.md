# jabba-the-hutt:07 — New primitive: create-token-unit

- **Group id (paste this):** `jabba-the-hutt:07`
- **Kind:** ability
- **Cards:** 4
- **⚠ New primitives suspected:** create-token-unit — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_15 | Jabba the Hutt | Leader | 6 | 3/9 | Ambush |
| LAW_134 | Bib Fortuna | Unit | 2 | 3/2 |  |
| LAW_244 | Unmarked Credits | Event | 1 |  |  |
| LAW_252 | Fett's Firespray | Unit | 6 | 4/6 | Ambush |

## Per-card analysis & acceptance criteria

### LAW_15 — Jabba the Hutt

**Type/Stats:** Leader, cost 6, 3/9  |  Traits: Hutt, Underworld

**Rules text:**

> Action [1 resource, Exhaust, return a friendly Underworld unit to its owner's hand]: Create a Credit token.
> Action: Play an Underworld unit from your hand. If you defeated a Credit while paying its cost, that unit gains Ambush for this phase.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_play_from_hand.

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_134 — Bib Fortuna

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Twi'lek, Underworld

**Rules text:**

> When Played: If you control another Underworld unit, create a Credit token.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_244 — Unmarked Credits

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Create a Credit token.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_252 — Fett's Firespray

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> Ambush
> When Attack Ends: If the defending unit was defeated, create a Credit token.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**⚠ Suspected NEW primitive:** create-token-unit. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

