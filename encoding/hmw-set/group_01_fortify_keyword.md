# hmw-set:01 — Fortify keyword

- **Group id (paste this):** `hmw-set:01`
- **Kind:** keyword
- **Cards:** 16
- **⚠ New primitives suspected:** beast-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Keyword group: **Fortify**

Implement the **Fortify** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and add `Fortify` to the keyword list in `docs/dev/engine_seams.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_4 | Grand Moff Tarkin | Leader | 9 | 2/12 | Fortify |
| HMW_37 | Bacta Tank | Upgrade | 1 |  | Fortify |
| HMW_70 | Dark Sanctum | Upgrade | 3 |  | Fortify |
| HMW_81 | Alliance Shield Generator | Upgrade | 2 |  | Fortify |
| HMW_95 | Carbonite Chamber | Upgrade | 1 |  | Fortify |
| HMW_112 | Military Academy | Upgrade | 1 |  | Fortify, Overwhelm |
| HMW_113 | Sinister War Memorial | Upgrade | 2 |  | Fortify |
| HMW_126 | Verdant Fortress | Upgrade | 2 |  | Fortify, Raid |
| HMW_147 | Beast Lair | Upgrade | 2 |  | Fortify |
| HMW_160 | Noxious Refinery | Upgrade | 4 |  | Fortify |
| HMW_171 | Trap Field | Upgrade | 2 |  | Fortify |
| HMW_172 | Heavy Ion Cannon | Upgrade | 3 |  | Fortify |
| HMW_205 | Intelligence Agency | Upgrade | 1 |  | Fortify |
| HMW_206 | The Tarkin Doctrine | Upgrade | 1 |  | Fortify |
| HMW_216 | Insurgent Camp | Upgrade | 1 |  | Fortify |
| HMW_271 | Landing Pad | Upgrade | 3 |  | Fortify |

## Per-card analysis & acceptance criteria

### HMW_4 — Grand Moff Tarkin

**Type/Stats:** Leader, cost 9, 2/12  |  Traits: Imperial, Official

**Rules text:**

> Ignore the aspect penalties on upgrades with Fortify you play.
> Ignore the aspect penalties on upgrades with Fortify you play.
> When the regroup phase starts: You may defeat a base with 10 or less remaining HP.
> Epic Action: If you control 9 or more resources, deploy this leader.

**Residual text (needs separate ability after keyword):** When the regroup phase starts: You may defeat a base with 10 or less remaining HP. Epic Action: If you control 9 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_37 — Bacta Tank

**Type/Stats:** Upgrade, cost 1  |  Traits: Fortification

**Rules text:**

> Fortify
> When Played: Heal up to 3 damage from a non‑Vehicle unit.
> Action [defeat this upgrade]: Put a non‑Vehicle unit from your discard pile on top of your deck.

**Residual text (needs separate ability after keyword):** When Played: Heal up to 3 damage from a non‑Vehicle unit. Action [defeat this upgrade]: Put a non‑Vehicle unit from your discard pile on top of your deck.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'discard'].

**Existing primitives that should suffice:** Heal, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_70 — Dark Sanctum

**Type/Stats:** Upgrade, cost 3  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “When the regroup phase starts: Draw a card and deal 2 damage to this base.”

**Residual text (needs separate ability after keyword):** Attached base gains: “When the regroup phase starts: Draw a card and deal 2 damage to this base.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_81 — Alliance Shield Generator

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> If attached base would be dealt 5 or more damage, prevent that damage. If you do, defeat this upgrade and draw a card.

**Residual text (needs separate ability after keyword):** If attached base would be dealt 5 or more damage, prevent that damage. If you do, defeat this upgrade and draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw', 'defeat'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_95 — Carbonite Chamber

**Type/Stats:** Upgrade, cost 1  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Action [defeat this upgrade]: Choose a non‑Vehicle unit. It doesn't ready during the next regroup phase.

**Residual text (needs separate ability after keyword):** Action [defeat this upgrade]: Choose a non‑Vehicle unit. It doesn't ready during the next regroup phase.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_112 — Military Academy

**Type/Stats:** Upgrade, cost 1  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “Friendly units gain Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)”

**Residual text (needs separate ability after keyword):** Attached base gains: “Friendly units gain Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)”

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_113 — Sinister War Memorial

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “When a friendly unit is defeated: Heal 1 damage from this base.”

**Residual text (needs separate ability after keyword):** Attached base gains: “When a friendly unit is defeated: Heal 1 damage from this base.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_126 — Verdant Fortress

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “Friendly units gain Raid 1. (They get +1/+0 while attacking.)”

**Residual text (needs separate ability after keyword):** Attached base gains: “Friendly units gain Raid 1. (They get +1/+0 while attacking.)”

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_147 — Beast Lair

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “When the action phase starts: You may discard a card from your hand. If you do, create a Beast token.”

**Residual text (needs separate ability after keyword):** Attached base gains: “When the action phase starts: You may discard a card from your hand. If you do, create a Beast token.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand, create-token-unit.

**⚠ Suspected NEW primitive:** beast-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_160 — Noxious Refinery

**Type/Stats:** Upgrade, cost 4  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “When the regroup phase starts: Reveal the top card of your deck. If it's Aggression, deal 1 damage to an enemy unit.”

**Residual text (needs separate ability after keyword):** Attached base gains: “When the regroup phase starts: Reveal the top card of your deck. If it's Aggression, deal 1 damage to an enemy unit.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_171 — Trap Field

**Type/Stats:** Upgrade, cost 2  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> When a non-leader ground unit enters play (including token units): You may defeat this upgrade. If you do, deal 3 damage to that unit.

**Residual text (needs separate ability after keyword):** When a non-leader ground unit enters play (including token units): You may defeat this upgrade. If you do, deal 3 damage to that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage', 'defeat'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_172 — Heavy Ion Cannon

**Type/Stats:** Upgrade, cost 3  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> When Played: Draw a card.
> Attached base gains: “Action [discard a card from your hand]: Deal 2 damage to a unit. Use this ability only once each phase.”

**Residual text (needs separate ability after keyword):** When Played: Draw a card. Attached base gains: “Action [discard a card from your hand]: Deal 2 damage to a unit. Use this ability only once each phase.”

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_205 — Intelligence Agency

**Type/Stats:** Upgrade, cost 1  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “You may look at the top card of your deck at any time.”
> When Played: Look at an opponent's hand. You may discard a card from it. If you do, they draw a card.

**Residual text (needs separate ability after keyword):** Attached base gains: “You may look at the top card of your deck at any time.” When Played: Look at an opponent's hand. You may discard a card from it. If you do, they draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard', 'search'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_206 — The Tarkin Doctrine

**Type/Stats:** Upgrade, cost 1  |  Traits: Law

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “When you play a Fortification upgrade: Exhaust an enemy unit.”
> When Played: If you control Grand Moff Tarkin, give an enemy unit –3/–0 for this phase.

**Residual text (needs separate ability after keyword):** Attached base gains: “When you play a Fortification upgrade: Exhaust an enemy unit.” When Played: If you control Grand Moff Tarkin, give an enemy unit –3/–0 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_216 — Insurgent Camp

**Type/Stats:** Upgrade, cost 1  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> When you play a unit with 3 or less power: You may defeat this upgrade. If you do, ready that unit.

**Residual text (needs separate ability after keyword):** When you play a unit with 3 or less power: You may defeat this upgrade. If you do, ready that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['defeat', 'ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_271 — Landing Pad

**Type/Stats:** Upgrade, cost 3  |  Traits: Fortification

**Rules text:**

> Fortify (Attach this to your base, not a unit.)
> Attached base gains: “Friendly space units get +1/+0.”

**Residual text (needs separate ability after keyword):** Attached base gains: “Friendly space units get +1/+0.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

