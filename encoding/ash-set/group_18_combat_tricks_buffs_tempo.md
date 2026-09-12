# ash-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ash-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| ASH_127 | The Twins | Unit | 4 | 2/7 | Sentinel |
| ASH_133 | Trask Walker | Unit | 8 | 5/9 |  |
| ASH_136 | Display of Strength | Event | 2 |  |  |
| ASH_144 | Vane's Snub Fighter | Unit | 3 | 2/4 |  |
| ASH_155 | Grogu | Unit | 3 | 2/6 |  |
| ASH_157 | Danger Squadron Wingmen | Unit | 4 | 4/5 |  |
| ASH_159 | Alphabet Squadron U-Wing | Unit | 5 | 5/6 | Overwhelm |

## Per-card analysis & acceptance criteria

### ASH_127 — The Twins

**Type/Stats:** Unit, cost 4, 2/7  |  Traits: Hutt, Underworld

**Rules text:**

> When Played/On Attack: You may give another friendly unit Sentinel for this phase.
> When another friendly unit is defeated: Heal 1 damage from your base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_133 — Trask Walker

**Type/Stats:** Unit, cost 8, 5/9  |  Traits: Vehicle, Walker

**Rules text:**

> When Played/On Attack: Choose a unit in your discard pile that costs 7 or less. Either put that card on the bottom of your deck and heal 3 damage from your base or return it to your hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['heal', 'discard', 'return_hand'].

**Existing primitives that should suffice:** Heal, DiscardFromHand, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_136 — Display of Strength

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Give a unit +3/+3 for this phase.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_144 — Vane's Snub Fighter

**Type/Stats:** Unit, cost 3, 2/4  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When a friendly unit's attack ends: If it dealt combat damage to a base, give an Advantage token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_155 — Grogu

**Type/Stats:** Unit, cost 3, 2/6  |  Traits: Droid, Force

**Rules text:**

> When you take the initiative: You may attack with a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_157 — Danger Squadron Wingmen

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Fighter, Rebel, Vehicle

**Rules text:**

> On Attack: You may give an Advantage token to another unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### ASH_159 — Alphabet Squadron U-Wing

**Type/Stats:** Unit, cost 5, 5/6  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> Overwhelm (When attacking an enemy unit, deal excess damage to the opponent's base.)
> When the regroup phase starts: Give an Advantage token to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

