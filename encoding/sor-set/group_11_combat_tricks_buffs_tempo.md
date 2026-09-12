# sor-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `sor-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SOR_36 | Gideon Hask | Unit | 5 | 5/5 |  |
| SOR_37 | Academy Defense Walker | Unit | 6 | 5/5 | Sentinel |
| SOR_39 | AT-AT Suppressor | Unit | 8 | 8/8 |  |
| SOR_47 | Kanan Jarrus | Unit | 4 | 4/5 |  |
| SOR_50 | The Ghost | Unit | 6 | 5/5 | Shielded |
| SOR_55 | The Force Is With Me | Event | 4 |  |  |
| SOR_57 | Protector | Upgrade | 1 |  | Sentinel |

## Per-card analysis & acceptance criteria

### SOR_36 — Gideon Hask

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Imperial, Trooper

**Rules text:**

> When an enemy unit is defeated: Give an Experience token to a friendly unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_37 — Academy Defense Walker

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Imperial, Vehicle, Walker

**Rules text:**

> Sentinel (Units in this arena can't attack your non-Sentinel units or your base.)
> 
> When Played: Give an Experience token to each friendly damaged unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_39 — AT-AT Suppressor

**Type/Stats:** Unit, cost 8, 8/8  |  Traits: Imperial, Vehicle, Walker

**Rules text:**

> When Played: Exhaust all ground units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_47 — Kanan Jarrus

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Force, Jedi, Rebel, Spectre

**Rules text:**

> On Attack: You may discard 1 card from the defending player's deck for each friendly SPECTRE unit. Heal 1 damage from your base for each different aspect among the discarded cards.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal', 'discard'].

**Existing primitives that should suffice:** Heal, DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_50 — The Ghost

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Rebel, Spectre, Transport, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> 
> When Played/On Attack: You may give a Shield token to another SPECTRE unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_55 — The Force Is With Me

**Type/Stats:** Event, cost 4  |  Traits: Force

**Rules text:**

> Choose a friendly unit and give 2 Experience tokens to it. If you control a FORCE unit, also give a Shield token to the chosen unit. You may attack with the chosen unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'attack_grant'].

**Existing primitives that should suffice:** GiveToken, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SOR_57 — Protector

**Type/Stats:** Upgrade, cost 1  |  Traits: Innate

**Rules text:**

> Attached unit gains Sentinel. (Units in this arena can't attack your non-Sentinel units or your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

