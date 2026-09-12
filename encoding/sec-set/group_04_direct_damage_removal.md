# sec-set:04 — Direct damage & removal

- **Group id (paste this):** `sec-set:04`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_163 | Outer Rim Constable | Unit | 2 | 3/1 |  |
| SEC_164 | Warrior of Clan Ordo | Unit | 2 | 3/3 |  |
| SEC_165 | Academy Disciplinarian | Unit | 3 | 3/4 |  |
| SEC_168 | Ziton Moj | Unit | 4 | 4/5 |  |
| SEC_169 | AAT Incinerator | Unit | 5 | 3/6 |  |
| SEC_171 | Punishing One | Unit | 5 | 3/5 | Raid |
| SEC_180 | Let's Call It War | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### SEC_163 — Outer Rim Constable

**Type/Stats:** Unit, cost 2, 3/1  |  Traits: Fringe, Official

**Rules text:**

> When Played: You may defeat an upgrade.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_164 — Warrior of Clan Ordo

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Mandalorian

**Rules text:**

> On Attack: You may disclose Aggression (reveal a card from your hand with this aspect icon). If you don't, deal 2 damage to your base.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_165 — Academy Disciplinarian

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Imperial, Official

**Rules text:**

> When Played: You may deal 1 damage to a friendly unit with 2 or less power and ready it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_168 — Ziton Moj

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Underworld

**Rules text:**

> When you take the initiative: Deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_169 — AAT Incinerator

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial, Tank, Vehicle

**Rules text:**

> When Played: Deal 1 damage to each of up to 4 other ground units. If no friendly units were damaged by this ability, deal 2 damage to your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_171 — Punishing One

**Type/Stats:** Unit, cost 5, 3/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> This unit gains Raid 1 for each damaged enemy unit.
> When Played/On Attack: You may deal 1 damage to a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'keyword_grant'].

**Existing primitives that should suffice:** DealDamage, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_180 — Let's Call It War

**Type/Stats:** Event, cost 3  |  Traits: Tactic

**Rules text:**

> Deal 3 damage to a unit. Then, if you have the initiative, you may deal 2 damage to another unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

