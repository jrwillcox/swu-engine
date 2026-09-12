# law-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `law-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_157 | Target Tagger | Unit | 3 | 3/3 |  |
| LAW_165 | Combat Exercise | Event | 1 |  |  |
| LAW_171 | Stockpile | Event | 6 |  |  |
| LAW_182 | Weazel | Unit | 2 | 2/3 | Raid |
| LAW_185 | Ben Solo | Unit | 9 | 8/8 | Hidden |
| LAW_186 | Enfys Nest's Helmet | Upgrade | 2 |  |  |
| LAW_193 | Mid Rim Sharpshooter | Unit | 3 | 3/3 | Saboteur |

## Per-card analysis & acceptance criteria

### LAW_157 — Target Tagger

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Bounty Hunter

**Rules text:**

> When Played: You may attack with a unit. If it's a Bounty Hunter, it gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_165 — Combat Exercise

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Exhaust a friendly unit. If you do, give 2 Experience tokens to it.

**Mechanical analysis:** trigger archetype `event`; effect families ['token', 'ready_exhaust'].

**Existing primitives that should suffice:** GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_171 — Stockpile

**Type/Stats:** Event, cost 6  |  Traits: Supply

**Rules text:**

> Resource this event and the top card of your deck.

**Mechanical analysis:** trigger archetype `event`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_182 — Weazel

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Underworld

**Rules text:**

> On Attack: Another friendly unit gains Raid 2 for this phase. (It gets +2/+0 while attacking.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_185 — Ben Solo

**Type/Stats:** Unit, cost 9, 8/8  |  Traits: Force

**Rules text:**

> Hidden
> When Played/When Defeated: Ready another friendly unit. It can't be attacked this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_186 — Enfys Nest's Helmet

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack: You may give another unit +3/+0 for this phase.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_193 — Mid Rim Sharpshooter

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Underworld

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: You may pay 1 resource. If you do, an opponent discards a card from their hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

