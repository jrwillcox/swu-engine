# lof-set:20 — Miscellaneous abilities

- **Group id (paste this):** `lof-set:20`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_44 | Loth-Wolf | Unit | 2 | 3/3 | Sentinel |
| LOF_73 | Mythosaur | Unit | 9 | 10/10 | Shielded |
| LOF_78 | Whirlwind of Power | Event | 3 |  |  |
| LOF_94 | Jedi Consular | Unit | 2 | 1/4 |  |
| LOF_103 | Following the Path | Event | 1 |  |  |
| LOF_114 | Kaadu | Unit | 4 | 4/4 | Overwhelm |
| LOF_123 | Directed by the Force | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### LOF_44 — Loth-Wolf

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Creature

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> This unit can't attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_73 — Mythosaur

**Type/Stats:** Unit, cost 9, 10/10  |  Traits: Creature, Mandalorian

**Rules text:**

> Shielded
> Friendly upgraded units can't be exhausted or returned to hand by enemy card abilities.
> Friendly leaders gain the Mandalorian trait.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_78 — Whirlwind of Power

**Type/Stats:** Event, cost 3  |  Traits: Force

**Rules text:**

> Give a unit –2/–2 for this phase. If you control a Force unit, give it –3/–3 instead.

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_94 — Jedi Consular

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Force, Jedi

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Play a unit from your hand. It costs 2 resources less.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** force-token, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_103 — Following the Path

**Type/Stats:** Event, cost 1  |  Traits: Plan

**Rules text:**

> Search the top 8 cards of your deck for up to 2 Force units, reveal them, and put them on top of your deck in any order. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_114 — Kaadu

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Creature

**Rules text:**

> When Played: You may give another friendly unit Overwhelm for this phase. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_123 — Directed by the Force

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> The Force is with you (create your Force token). You may play a unit from your hand (paying its cost).

**Mechanical analysis:** trigger archetype `event`; effect families ['—'].

**Existing primitives that should suffice:** push_play_from_hand, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

