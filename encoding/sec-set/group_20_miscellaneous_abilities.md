# sec-set:20 — Miscellaneous abilities

- **Group id (paste this):** `sec-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_12 | Cassian Andor | Leader | 6 | 6/2 | Overwhelm |
| SEC_38 | Condemn | Upgrade | 3 |  |  |
| SEC_45 | Senator Chuchi | Unit | 3 | 2/5 | Restore |
| SEC_46 | Galen Erso | Unit | 4 | 3/5 | Plot |
| SEC_48 | Captain Rex | Unit | 6 | 7/7 | Sentinel |
| SEC_52 | Diplomatic Immunity | Upgrade | 2 |  |  |
| SEC_56 | Escape Pod | Unit | 1 | 0/3 |  |

## Per-card analysis & acceptance criteria

### SEC_12 — Cassian Andor

**Type/Stats:** Leader, cost 6, 6/2  |  Traits: Rebel

**Rules text:**

> Friendly units that have damaged an opponent's base this phase can't be attacked (unless they have Sentinel).
> Overwhelm
> While you have the initiative, this unit isn't defeated by having no remaining HP and can't be defeated by enemy card abilities.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_38 — Condemn

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> While attached unit is attacking, it gains: “On Attack: The defending player may disclose VigilanceVillainy. If they do, this unit gets –6/–0 for this attack” and loses all other abilities.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_45 — Senator Chuchi

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Official, Republic

**Rules text:**

> Restore 1 (When this unit attacks, heal 1 damage from your base.)
> On Attack: Give another friendly Official unit Restore 2 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_46 — Galen Erso

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Imperial

**Rules text:**

> When Played: Name a card. While this unit is in play, each non-leader card an opponent owns with that name, including those not in play, loses all abilities (and can't gain abilities).
> Plot

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_48 — Captain Rex

**Type/Stats:** Unit, cost 6, 7/7  |  Traits: Clone, Republic, Trooper

**Rules text:**

> When Played/When this unit completes an attack: Give this unit and an enemy unit Sentinel for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_52 — Diplomatic Immunity

**Type/Stats:** Upgrade, cost 2  |  Traits: Law

**Rules text:**

> Attached unit gains: “When this unit is attacked: You may disclose VigilanceVigilanceHeroismHeroism (reveal cards from your hand with these aspect icons among them). If you do, the attacker gets –2/–0 for this attack.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Existing primitives that should suffice:** disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_56 — Escape Pod

**Type/Stats:** Unit, cost 1, 0/3  |  Traits: Transport, Vehicle

**Rules text:**

> When Played: You may have this unit capture a friendly non-Vehicle, non-leader unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** capture.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

