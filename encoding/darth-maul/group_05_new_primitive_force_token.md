# darth-maul:05 — New primitive: force-token

- **Group id (paste this):** `darth-maul:05`
- **Kind:** ability
- **Cards:** 5
- **⚠ New primitives suspected:** force-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_129 | Acolyte of the Beyond | Unit | 2 | 2/3 |  |
| LOF_137 | Savage Opress | Unit | 6 | 9/6 | Overwhelm |
| LOF_156 | Infused Brawler | Unit | 2 | 2/2 |  |
| LOF_229 | Kylo Ren | Unit | 2 | 2/3 | Overwhelm |
| LOF_231 | Darth Tyranus | Unit | 4 | 4/3 | Ambush, Shielded |

## Per-card analysis & acceptance criteria

### LOF_129 — Acolyte of the Beyond

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Sith

**Rules text:**

> On Attack/When Defeated: The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_137 — Savage Opress

**Type/Stats:** Unit, cost 6, 9/6  |  Traits: Force, Night

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When Played/When Defeated: You may use the Force (lose your Force token). If you don't, deal 9 damage to your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_156 — Infused Brawler

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Force, Night

**Rules text:**

> When Played: You may use the Force (lose your Force token). If you do, give 2 Experience tokens to this unit.
> When this unit completes an attack: Defeat an Experience token on it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'token'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, GiveToken.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_229 — Kylo Ren

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: First Order, Force

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When you play an upgrade on this unit: You may use the Force (lose your Force token). If you do, draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_231 — Darth Tyranus

**Type/Stats:** Unit, cost 4, 4/3  |  Traits: Force, Separatist, Sith

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> While the Force is with you, this unit gains Ambush. (When you play this unit, he may attack an enemy unit.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

