# darth-maul:04 — New primitive: force-token

- **Group id (paste this):** `darth-maul:04`
- **Kind:** ability
- **Cards:** 7
- **⚠ New primitives suspected:** force-token — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_9 | Darth Maul | Leader | 6 | 5/6 |  |
| LOF_21 | Shadowed Undercity | Base |  | None/28 |  |
| LOF_31 | Karis | Unit | 2 | 2/4 |  |
| LOF_35 | Talzin's Assassin | Unit | 4 | 4/4 |  |
| LOF_39 | Darth Sidious | Unit | 8 | 6/8 | Restore |
| LOF_41 | Drain Essence | Event | 2 |  |  |
| LOF_67 | Chirrut Îmwe | Unit | 4 | 3/5 | Sentinel |

## Per-card analysis & acceptance criteria

### LOF_9 — Darth Maul

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Sith

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Deal 1 damage to a unit and 1 damage to a different unit.
> On Attack: Deal 1 damage to a unit and 1 damage to a different unit.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_21 — Shadowed Undercity

**Type/Stats:** Base

**Rules text:**

> When a friendly Force unit attacks: The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_31 — Karis

**Type/Stats:** Unit, cost 2, 2/4  |  Traits: Force, Night

**Rules text:**

> When Defeated: You may use the Force (lose your Force token). If you do, give a unit –2/–2 for this phase.

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_35 — Talzin's Assassin

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Force, Night

**Rules text:**

> When Played: You may use the Force (lose your Force token). If you do, give a unit –3/–3 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_39 — Darth Sidious

**Type/Stats:** Unit, cost 8, 6/8  |  Traits: Force, Separatist, Sith

**Rules text:**

> Restore 2 (When this unit attacks, heal 2 damage from your base.)
> When Played: You may use the Force. If you do, defeat each non-Sith unit with 3 or less remaining HP.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_41 — Drain Essence

**Type/Stats:** Event, cost 2  |  Traits: Force

**Rules text:**

> Deal 2 damage to a unit. The Force is with you (create your Force token).

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_67 — Chirrut Îmwe

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Force, Fringe

**Rules text:**

> Sentinel
> When this unit is attacked (before damage is dealt): You may use the Force (lose your Force token). If you do, the attacker gets –2/–0 for this attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**⚠ Suspected NEW primitive:** force-token. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

