# shd-set:17 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:17`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_186 | Hunter of the Haxion Brood | Unit | 3 | 4/3 | Bounty, Shielded |
| SHD_188 | 4-LOM | Unit | 4 | 4/4 | Ambush |
| SHD_189 | Slaver's Freighter | Unit | 5 | 4/5 |  |
| SHD_190 | Zuckuss | Unit | 5 | 6/6 | Saboteur |
| SHD_193 | Frozen in Carbonite | Upgrade | 3 |  |  |
| SHD_197 | L3-37 | Unit | 2 | 2/2 | Smuggle |
| SHD_199 | Coruscant Dissident | Unit | 3 | 3/4 |  |

## Per-card analysis & acceptance criteria

### SHD_186 — Hunter of the Haxion Brood

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> While an enemy unit has a Bounty, this unit gains Shielded. (When you play this unit, give a Shield token to it.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_188 — 4-LOM

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Bounty Hunter, Droid, Underworld

**Rules text:**

> Ambush (When you play this unit, it may ready and attack an enemy unit.)
> Each friendly unit named Zuckuss gets +1/+1 and gains Ambush.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_189 — Slaver's Freighter

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: You may ready another unit with power equal to or less than the number of upgrades on enemy units.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_190 — Zuckuss

**Type/Stats:** Unit, cost 5, 6/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> Each friendly unit named 4-LOM gets +1/+1 and gains Saboteur.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_193 — Frozen in Carbonite

**Type/Stats:** Upgrade, cost 3  |  Traits: Condition

**Rules text:**

> Attach to a non-leader unit.
> Attached unit can't ready.
> When Played: Exhaust attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_197 — L3-37

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Droid, Underworld

**Rules text:**

> When Played: You may rescue a captured card. If you don't, give a Shield token to this unit.
> Smuggle [4 resources Cunning Heroism] (If this card is a resource, you may play her for her smuggle cost. Replace her with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_199 — Coruscant Dissident

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Twi'lek, Underworld

**Rules text:**

> On Attack: You may ready a resource.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

