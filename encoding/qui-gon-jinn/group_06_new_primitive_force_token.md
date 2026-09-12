# qui-gon-jinn:06 — New primitive: force-token

- **Group id (paste this):** `qui-gon-jinn:06`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** force-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_16 | Qui-Gon Jinn | Leader | 6 | 4/7 |  |
| LOF_23 | Jedi Temple | Base |  | None/28 |  |
| LOF_193 | Youngling Padawan | Unit | 2 | 2/3 |  |
| LOF_196 | Jedi Sentinel | Unit | 4 | 5/4 | Sentinel |
| LOF_218 | Impossible Escape | Event | 1 |  |  |
| LOF_227 | The Will of the Force | Event | 4 |  |  |
| LOF_249 | Luke Skywalker | Unit | 4 | 3/5 |  |

## Per-card analysis & acceptance criteria

### LOF_16 — Qui-Gon Jinn

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Return a friendly non-leader unit to its owner's hand. Play a non-Villainy unit that costs less than the returned unit from your hand for free.
> When this unit completes an attack (and survives): You may return a friendly non-leader unit to its owner's hand. Play a non-Villainy unit that costs less than the returned unit from your hand for free.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand, push_play_from_hand.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_23 — Jedi Temple

**Type/Stats:** Base

**Rules text:**

> When a friendly Force unit attacks: The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_193 — Youngling Padawan

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Force, Jedi

**Rules text:**

> When Played: The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_196 — Jedi Sentinel

**Type/Stats:** Unit, cost 4, 5/4  |  Traits: Force, Jedi

**Rules text:**

> While the Force is with you, this unit gains Sentinel. (Enemy units in this arena must attack a Sentinel when they attack you.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_218 — Impossible Escape

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> You may either exhaust a friendly unit or use the Force (lose your Force token). If you do either, exhaust an enemy unit and draw a card.

**Mechanical analysis:** trigger archetype `event`; effect families ['draw', 'ready_exhaust'].

**Existing primitives that should suffice:** DrawCards, ExhaustCard/ReadyCard.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_227 — The Will of the Force

**Type/Stats:** Event, cost 4  |  Traits: Force

**Rules text:**

> Return a non-leader unit to its owner's hand. You may use the Force (lose your Force token). If you do, that player discards a random card from their hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_249 — Luke Skywalker

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Fringe

**Rules text:**

> When you play another <uq> (unique) unit: You may use the Force (lose your Force token). If you do, give an Experience token and a Shield token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

