# shd-set:03 — Direct damage & removal

- **Group id (paste this):** `shd-set:03`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_114 | Scanning Officer | Unit | 2 | 2/3 | Smuggle |
| SHD_133 | Dengar | Unit | 1 | 2/2 |  |
| SHD_139 | Krrsantan | Unit | 5 | 3/7 | Bounty |
| SHD_142 | Pre Vizsla | Unit | 7 | 8/7 |  |
| SHD_143 | Ruthlessness | Upgrade | 1 |  |  |
| SHD_144 | Give In to Your Anger | Event | 1 |  |  |
| SHD_150 | Koska Reeves | Unit | 4 | 4/5 |  |

## Per-card analysis & acceptance criteria

### SHD_114 — Scanning Officer

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Imperial, Official

**Rules text:**

> When Played: Reveal 3 enemy resources. Defeat each resource with the Smuggle keyword revealed this way. For each resource defeated this way, its controller puts the top card of their deck into play as a resource.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat', 'ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_133 — Dengar

**Type/Stats:** Unit, cost 1, 2/2  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> When you play an upgrade on a unit: You may deal 1 damage to that unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_139 — Krrsantan

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Bounty Hunter, Underworld, Wookiee

**Rules text:**

> When Played: If an enemy unit has a Bounty, you may ready this unit.
> On Attack: Choose a ground unit. You may deal 1 damage to it for each damage on this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_142 — Pre Vizsla

**Type/Stats:** Unit, cost 7, 8/7  |  Traits: Mandalorian, Trooper

**Rules text:**

> When Played/On Attack: You may pay the cost of an upgrade attached to another non-Vehicle unit. If you do, take control of that upgrade and attach it to this unit, if able. If it can't attach to this unit, defeat it instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['defeat'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_143 — Ruthlessness

**Type/Stats:** Upgrade, cost 1  |  Traits: Innate

**Rules text:**

> Attached unit gains: “When this unit attacks and defeats a unit: Deal 2 damage to the defending player's base.”

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_144 — Give In to Your Anger

**Type/Stats:** Event, cost 1  |  Traits: Innate

**Rules text:**

> Deal 1 damage to an enemy unit. Its controller's next action this phase must be an attack action with that unit, if able. It must attack a unit, if able.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_150 — Koska Reeves

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Mandalorian, Trooper

**Rules text:**

> On Attack: If this unit is upgraded, you may deal 2 damage to a ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

