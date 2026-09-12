# shd-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `shd-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_145 | Headhunting | Event | 2 |  |  |
| SHD_151 | Valiant Assault Ship | Unit | 4 | 3/4 | Saboteur |
| SHD_155 | Heroic Resolve | Upgrade | 1 |  | Overwhelm |
| SHD_169 | Clan Challengers | Unit | 5 | 3/6 | Overwhelm, Raid |
| SHD_182 | Bravado | Event | 5 |  |  |
| SHD_183 | Kintan Intimidator | Unit | 1 | 1/4 |  |
| SHD_185 | Doctor Evazan | Unit | 2 | 3/3 | Bounty, Shielded |

## Per-card analysis & acceptance criteria

### SHD_145 — Headhunting

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Attack with up to 3 units (one at a time). They can't attack bases for these attacks. Each Bounty Hunter that attacks this way gets +2/+0 for its attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_151 — Valiant Assault Ship

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Fringe, Transport, Vehicle

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: If the defending player controls more resources than you, this unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_155 — Heroic Resolve

**Type/Stats:** Upgrade, cost 1  |  Traits: Innate

**Rules text:**

> Attached unit gains: “Action [2 resources, defeat a Heroic Resolve on this unit]: Attack with this unit. It gets +4/+0 and gains Overwhelm for this attack.”

**Mechanical analysis:** trigger archetype `activated`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_169 — Clan Challengers

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Mandalorian, Trooper

**Rules text:**

> Raid 3 (This unit gets +3/+0 while attacking.)
> While this unit is upgraded, it gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_182 — Bravado

**Type/Stats:** Event, cost 5  |  Traits: Innate

**Rules text:**

> If you've defeated an enemy unit this phase, this event costs 2 resources less to play.
> Ready a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_183 — Kintan Intimidator

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Underworld

**Rules text:**

> On Attack: Exhaust the defender.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_185 — Doctor Evazan

**Type/Stats:** Unit, cost 2, 3/3  |  Traits: Underworld

**Rules text:**

> Shielded (When you play this unit, give a Shield token to him.)
> Bounty — Ready up to 12 resources. (When this unit is defeated or captured, your opponent collects his bounty.)

**Mechanical analysis:** trigger archetype `static`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

