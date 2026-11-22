# hmw-set:26 — New primitive: weakness-token

- **Group id (paste this):** `hmw-set:26`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** weakness-token, beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_67 | The Great Progenitor | Unit | 5 | 4/7 |  |
| HMW_71 | Ravage | Event | 4 |  |  |
| HMW_87 | Venomous Wyyyshokk | Unit | 3 | 3/4 |  |
| HMW_97 | Dire Prowess | Upgrade | 2 |  |  |
| HMW_100 | Torrent | Event | 2 |  |  |
| HMW_109 | Tireless Magnaguard | Unit | 4 | 5/3 |  |
| HMW_110 | Emperor Palpatine | Unit | 5 | 3/2 |  |

## Per-card analysis & acceptance criteria

### HMW_67 — The Great Progenitor

**Type/Stats:** Unit, cost 5, 4/7  |  Traits: Creature

**Rules text:**

> When Attack Ends: You may give a Weakness token to this unit. If you do, create a Beast token for each Weakness token on this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** create-token-unit.

**⚠ Suspected NEW primitive:** weakness-token, beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_71 — Ravage

**Type/Stats:** Event, cost 4  |  Traits: Disaster, Tactic

**Rules text:**

> Distribute up to 3 Weakness tokens among any number of units.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_87 — Venomous Wyyyshokk

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Creature

**Rules text:**

> When Defeated: You may give a Weakness token to a damaged unit.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_97 — Dire Prowess

**Type/Stats:** Upgrade, cost 2  |  Traits: Learned

**Rules text:**

> When Played: You may give a Weakness token to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_100 — Torrent

**Type/Stats:** Event, cost 2  |  Traits: Disaster

**Rules text:**

> Give a Weakness token to a unit. If you control a Naboo base, give 2 Weakness tokens to that unit instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_109 — Tireless Magnaguard

**Type/Stats:** Unit, cost 4, 5/3  |  Traits: Droid, Separatist

**Rules text:**

> When Defeated: If this unit had 5 or more power, for this phase you may play this unit from your discard pile for free and give 2 Weakness tokens to it.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_110 — Emperor Palpatine

**Type/Stats:** Unit, cost 5, 3/2  |  Traits: Force, Imperial, Official, Sith

**Rules text:**

> When Played: You may take control of an enemy non-leader unit that costs 3 or less. If you do, give 2 Weakness tokens to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**⚠ Suspected NEW primitive:** weakness-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

