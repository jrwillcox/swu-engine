# shd-set:18 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:18`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_201 | Principled Outlaw | Unit | 4 | 4/4 | Smuggle |
| SHD_204 | Millennium Falcon | Unit | 6 | 5/5 | Ambush, Smuggle |
| SHD_205 | Let the Wookiee Win | Event | 2 |  |  |
| SHD_208 | Final Showdown | Event | 6 |  |  |
| SHD_211 | Fugitive Wookiee | Unit | 2 | 3/3 | Bounty |
| SHD_212 | Privateer Scyk | Unit | 2 | 2/2 | Shielded |
| SHD_213 | DJ | Unit | 3 | 3/5 | Smuggle |

## Per-card analysis & acceptance criteria

### SHD_201 — Principled Outlaw

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Underworld

**Rules text:**

> On Attack: You may exhaust a ground unit.
> Smuggle [6 resources Cunning Heroism] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_204 — Millennium Falcon

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> If you play this unit from your hand, it gains Ambush.
> Smuggle [6 resources Cunning Heroism] (If this card is a resource, you may play her for her smuggle cost. Replace her with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_205 — Let the Wookiee Win

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> An opponent chooses one:
> <bullet>You ready up to 6 resources.
> You ready a friendly unit. If it's a Wookiee unit, attack with it. It gets +2/+0 for this attack.</bullet>

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, ExhaustCard/ReadyCard, push_granted_attack, opponent-chooses-target.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_208 — Final Showdown

**Type/Stats:** Event, cost 6  |  Traits: Gambit

**Rules text:**

> Ready each unit you control. At the start of the regroup phase, you lose the game.

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_211 — Fugitive Wookiee

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Wookiee

**Rules text:**

> Bounty — Exhaust a unit. (When this unit is defeated or captured, your opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_212 — Privateer Scyk

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Fighter, Fringe, Vehicle

**Rules text:**

> While you control another Cunning unit, this unit gains Shielded. (When you play this unit, give a Shield token to it.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_213 — DJ

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Underworld

**Rules text:**

> Smuggle [7 resources Cunning Cunning]
> When played using Smuggle: Take control of an enemy resource. When this unit leaves play, that resource's owner takes control of it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ramp'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

