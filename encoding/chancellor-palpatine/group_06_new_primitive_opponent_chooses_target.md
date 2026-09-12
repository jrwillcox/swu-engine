# chancellor-palpatine:06 — New primitive: opponent-chooses-target

- **Group id (paste this):** `chancellor-palpatine:06`
- **Kind:** ability
- **Cards:** 1
- **⚠ New primitives suspected:** opponent-chooses-target — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_43 | The Tragedy of Plagueis | Event | 5 |  |  |

## Per-card analysis & acceptance criteria

### LOF_43 — The Tragedy of Plagueis

**Type/Stats:** Event, cost 5  |  Traits: Learned

**Rules text:**

> Choose a friendly unit. For this phase, it can't be defeated by having no remaining HP.
> An opponent chooses a unit they control. Defeat that unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat'].

**⚠ Suspected NEW primitive:** opponent-chooses-target. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

