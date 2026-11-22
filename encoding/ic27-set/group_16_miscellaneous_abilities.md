# ic27-set:16 — Miscellaneous abilities

- **Group id (paste this):** `ic27-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_113 | Ezra Bridger | Unit | 2 | 1/3 | Raid |
| IC27_126 | Saw Gerrera | Unit | 5 | 6/5 |  |
| IC27_138 | Banshee | Unit | 2 | 2/3 |  |
| IC27_142 | Greedo | Unit | 3 | 5/3 | Ambush |
| IC27_149 | The Invisible Hand | Unit | 10 | 9/9 |  |
| IC27_157 | The Mandalorian | Unit | 4 | 5/3 | Shielded |
| IC27_161 | Han Solo | Unit | 6 | 4/6 | Raid |

## Per-card analysis & acceptance criteria

### IC27_113 — Ezra Bridger

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Force, Jedi, Rebel, Spectre

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> On Attack: Give another friendly Heroism unit Raid 2 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_126 — Saw Gerrera

**Type/Stats:** Unit, cost 5, 6/5  |  Traits: Rebel

**Rules text:**

> On Attack: You may double another friendly unit's power for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_138 — Banshee

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> On Attack: You may search the top 5 cards of your deck for a non-unit card, reveal it, and put it on top of your deck. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_142 — Greedo

**Type/Stats:** Unit, cost 3, 5/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Ambush (When you play this unit, he may attack an enemy unit.)
> While attacking or defending, this unit deals combat damage after the other attacking or defending unit.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_149 — The Invisible Hand

**Type/Stats:** Unit, cost 10, 9/9  |  Traits: Capital Ship, Separatist, Vehicle

**Rules text:**

> When Played/When Defeated: The next card you play this phase costs 9 resources less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_157 — The Mandalorian

**Type/Stats:** Unit, cost 4, 5/3  |  Traits: Bounty Hunter, Mandalorian

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> On Attack: If the defending unit is exhausted, it gets –4/–0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_161 — Han Solo

**Type/Stats:** Unit, cost 6, 4/6  |  Traits: Rebel

**Rules text:**

> Raid 2 (This unit gets +2/+0 while attacking.)
> On Attack: The defending unit gets –2/–0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

