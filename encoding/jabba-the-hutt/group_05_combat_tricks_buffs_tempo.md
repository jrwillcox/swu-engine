# jabba-the-hutt:05 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jabba-the-hutt:05`
- **Kind:** ability
- **Cards:** 6

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_65 | 4-LOM | Unit | 5 | 4/5 |  |
| LAW_158 | Khetanna | Unit | 3 | 2/4 |  |
| LAW_168 | Haymaker | Event | 4 |  |  |
| LAW_210 | Salacious Crumb | Unit | 1 | 0/2 | Raid |
| LAW_231 | Weequay Pirate | Unit | 2 | 2/3 | Saboteur |
| LAW_249 | Black Sun Cabalist | Unit | 2 | 1/3 |  |

## Per-card analysis & acceptance criteria

### LAW_65 — 4-LOM

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Bounty Hunter, Droid, Underworld

**Rules text:**

> When Played: You may attack with a friendly Bounty Hunter unit, even if it's exhausted. It can't attack bases for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_158 — Khetanna

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Speeder, Underworld, Vehicle

**Rules text:**

> When Played/On Attack: The next Underworld unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_168 — Haymaker

**Type/Stats:** Event, cost 4  |  Traits: Tactic

**Rules text:**

> Give an Experience token to a friendly unit. That unit deals damage equal to its power to an enemy unit in the same arena.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_210 — Salacious Crumb

**Type/Stats:** Unit, cost 1, 0/2  |  Traits: Creature, Underworld

**Rules text:**

> Raid 2
> If you control Jabba the Hutt (as a leader or unit), this unit enters play ready.

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_231 — Weequay Pirate

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Underworld

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: If no resources were paid to play this unit, give an Experience token to it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_249 — Black Sun Cabalist

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Underworld

**Rules text:**

> When Played: Give an Experience token to another friendly Underworld unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

