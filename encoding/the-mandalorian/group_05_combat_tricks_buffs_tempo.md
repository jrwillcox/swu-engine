# the-mandalorian:05 — Combat tricks, buffs & tempo

- **Group id (paste this):** `the-mandalorian:05`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_196 | Grogu | Unit | 2 | 0/5 |  |
| SHD_223 | Snapshot Reflexes | Upgrade | 1 |  |  |
| SHD_258 | Mandalorian Warrior | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### SHD_196 — Grogu

**Type/Stats:** Unit, cost 2, 0/5  |  Traits: Force

**Rules text:**

> Action [exhaust]: Exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `activated`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_223 — Snapshot Reflexes

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> When Played: You may attack with attached unit. (It can only attack if it's ready.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_258 — Mandalorian Warrior

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Mandalorian

**Rules text:**

> When Played: You may give an Experience token to another Mandalorian unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

